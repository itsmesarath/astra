"""Offline session-boundary continuity with synthetic capture bytes only."""

import hashlib
import json
import socket
import sys
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_microstructure_paper import MS, rows_with_exit
from test_microstructure_policy import (
    capture_bytes,
    capture_rows,
    gateway_config,
    policy,
    replay_config,
)

from ai_trader.research import campaign_evaluation as evaluation
from ai_trader.research.microstructure_trial import SourceDeclaration, register_trial
from ai_trader.trading import microstructure_campaign as module
from ai_trader.trading import microstructure_paper as single
from ai_trader.trading.durable_paper_gateway import DAY_NS, DurablePaperGateway
from ai_trader.trading.trade_journal import JournalError, TradeJournal

D = Decimal


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Campaign test attempted network access.")

    monkeypatch.setattr(socket, "create_connection", forbidden)


def shifted(rows, *, ms=1000, price="0"):
    rows = deepcopy(rows)
    delta = D(price)
    for row in rows:
        for key in ("started_at_ns", "requested_at_ns", "received_at_ns", "ended_at_ns"):
            if key in row:
                row[key] += ms * MS
        event = row.get("event", {})
        for key in ("E", "T"):
            if key in event:
                event[key] += ms
        for key in ("bids", "asks", "b", "a"):
            if not isinstance(event.get(key), list):
                continue  # Aggregate-trade 'a' is an ID, not depth ask levels.
            for level in event.get(key, []):
                level[0] = str(D(level[0]) + delta)
        if "p" in event:
            event["p"] = str(D(event["p"]) + delta)
    return rows


def recovery_rows(*, ms=1000, price="-1"):
    rows = capture_rows()[:3]
    rows.append(
        dict(
            schema_version=1,
            record_type="session_end",
            ended_at_ns=1100 * MS,
            trade_events=0,
            depth_events=1,
        )
    )
    return shifted(rows, ms=ms, price=price)


def setup_campaign(tmp_path, *, first=None, second=None, third=None, settings=None, config=None):
    captures = (
        capture_rows() if first is None else first,
        recovery_rows() if second is None else second,
    )
    if third is not None:
        captures += (third,)
    declarations, inputs = [], []
    for i, rows in enumerate(captures, 1):
        data = capture_bytes(rows)
        name = f"research-{i}"
        path = tmp_path / f"capture-{i}.jsonl"
        path.write_bytes(data)
        declarations.append(
            SourceDeclaration(
                name,
                hashlib.sha256(data).hexdigest(),
                rows[0]["started_at_ns"],
                rows[-1]["ended_at_ns"],
                "research",
            )
        )
        inputs.append(module.CampaignInput(name, path))
    end = declarations[-1].ended_at_ns
    declarations.append(
        SourceDeclaration("reserved", "f" * 64, end + MS, end + 100 * MS, "reserved")
    )
    registration_path = tmp_path / "registration.json"
    record = register_trial(
        registration_path,
        trial_id="synthetic-campaign",
        sources=tuple(declarations),
        policy=settings or policy(),
        replay=replay_config(),
        gateway=config or gateway_config(),
        initial_cash_usdt=D("1000"),
    )
    return dict(
        registration_path=registration_path,
        sources=tuple(inputs),
        journal_path=tmp_path / "campaign.sqlite",
        max_frames=100,
        enable_paper_simulation=True,
    ), record


def open_campaign(args, record, *, read_only=False):
    return TradeJournal(
        args["journal_path"],
        run_id=module.campaign_run_id(record),
        mode="paper",
        read_only=read_only,
    )


def evaluate(args):
    return evaluation.evaluate_registered_campaign(
        **{k: v for k, v in args.items() if k != "enable_paper_simulation"}
    )


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_carried_inventory_waits_for_fresh_bridge_then_stops_before_warmup(tmp_path, monkeypatch):
    args, record = setup_campaign(tmp_path)
    first = module.simulate_registered_campaign(**{**args, "max_frames": 12})
    assert D(first["position_btc"]) == D("0.998")
    assert first["source_sessions"][0]["session_consumed"]
    assert not first["source_sessions"][1]["session_consumed"]
    assert not first["campaign_consumed"]
    snapshot = module.simulate_registered_campaign(**{**args, "max_frames": 13}, resume=True)
    assert snapshot["ledger_order_count"] == 1 and snapshot["blocked_exit_entry_ids_at_prefix_end"]
    seen = []
    original = single._build_case

    def inspect(record, frame, context):
        seen.append((frame, context))
        return original(record, frame, context)

    monkeypatch.setattr(single, "_build_case", inspect)
    final = module.simulate_registered_campaign(**args, resume=True)
    assert final["campaign_consumed"] and final["frames_processed"] == 15
    assert D(final["position_btc"]) == 0 and final["ledger_order_count"] == 2
    frame, context = seen[0]
    assert frame.tick.source_session == "research-2"
    assert frame.tick.last_trade_received_at_ns is None and not frame.tick.features_ready
    assert frame.observation.rolling_cvd_base == 0
    assert context.protection_active and context.account.position_btc == 0
    with open_campaign(args, record) as journal:
        assert journal.get_order(final["exit_order_ids_in_prefix"][0]).reason == "stop_loss"
        assert journal.account_seed().initialized_at_ns == 950 * MS
        assert journal.account_seed().initial_cash_usdt == 1000
    assert D(final["cash_usdt"]) == D("1000") + D(final["realized_pnl_usdt"])
    audit = evaluate(args)
    assert audit["frames_evaluated"] == 15 and audit["campaign_consumed"]
    assert audit["closed_trades"] == 1 and audit["open_trades"] == 0
    assert audit["exposure_ns"] == 700 * MS  # Includes the unobservable disconnect interval.
    assert audit["unvalued_equity_samples"] == 4
    assert not audit["drawdown_path_fully_valued"]
    assert not audit["full_session_flat_comparison_available"]
    assert audit["net_pnl_usdt"] == final["realized_pnl_usdt"]


def test_cash_and_sampled_peak_are_not_reset_at_a_flat_session_boundary(tmp_path):
    args, record = setup_campaign(tmp_path, first=rows_with_exit(), second=recovery_rows(price="0"))
    first = module.simulate_registered_campaign(**{**args, "max_frames": 13})
    with open_campaign(args, record) as journal:
        prior = DurablePaperGateway(journal, record.gateway).risk_checkpoint()
    final = module.simulate_registered_campaign(**args, resume=True)
    with open_campaign(args, record) as journal:
        after = DurablePaperGateway(journal, record.gateway).risk_checkpoint()
    assert D(first["cash_usdt"]) > 1000 and first["cash_usdt"] == final["cash_usdt"]
    assert prior.peak_equity_usdt == after.peak_equity_usdt > 1000
    audit = evaluate(args)
    assert audit["full_session_flat_comparison_available"]
    assert D(audit["net_pnl_usdt"]) == D(final["cash_usdt"]) - 1000


def test_maximum_hold_includes_session_downtime(tmp_path):
    args, record = setup_campaign(
        tmp_path,
        second=recovery_rows(price="0"),
        settings=replace(policy(), maximum_hold_ns=500 * MS),
    )
    result = module.simulate_registered_campaign(**args)
    with open_campaign(args, record) as journal:
        exit_order = journal.get_order(result["exit_order_ids_in_prefix"][0])
        assert exit_order.reason == "maximum_hold" and exit_order.requested_at_ns == 2000 * MS


@pytest.mark.parametrize("next_day", [False, True])
def test_daily_loss_does_not_reset_on_session_boundary_only_on_utc_day(tmp_path, next_day):
    config = gateway_config()
    config = replace(config, limits=replace(config.limits, max_daily_loss_usdt=D("0.5")))
    args, record = setup_campaign(
        tmp_path,
        first=rows_with_exit("99.7", "99.71"),
        config=config,
        second=shifted(capture_rows(), ms=DAY_NS // MS if next_day else 1000),
    )
    result = module.simulate_registered_campaign(**args)
    assert D(result["realized_pnl_usdt"]) < D("-0.5")
    if next_day:
        assert len(result["entry_order_ids_in_prefix"]) == 2 and D(result["position_btc"]) > 0
    else:
        assert len(result["entry_order_ids_in_prefix"]) == 1
        assert result["case_reason_counts"]["risk_rejected:daily_loss_limit_reached"] == 1
    with open_campaign(args, record) as journal:
        checkpoint = DurablePaperGateway(journal, record.gateway).risk_checkpoint()
        assert checkpoint.peak_equity_usdt == 1000
        assert checkpoint.utc_day == int(next_day)
        assert checkpoint.day_start_realized_usdt == (
            D(result["realized_pnl_usdt"]) if next_day else 0
        )


def test_kill_survives_reconnect_and_day_rollover_but_does_not_block_exit(tmp_path):
    args, record = setup_campaign(tmp_path, second=recovery_rows(ms=DAY_NS // MS))
    module.simulate_registered_campaign(**{**args, "max_frames": 12})
    with open_campaign(args, record) as journal:
        DurablePaperGateway(journal, record.gateway).set_kill_switch(True, observed_at_ns=1400 * MS)
    result = module.simulate_registered_campaign(**args, resume=True)
    assert result["kill_switch_active"] and D(result["position_btc"]) == 0
    assert len(result["entry_order_ids_in_prefix"]) == len(result["exit_order_ids_in_prefix"]) == 1
    with open_campaign(args, record) as journal:
        assert DurablePaperGateway(journal, record.gateway).risk_checkpoint().utc_day == 1


def test_faulted_session_can_only_recover_in_the_next_declared_fresh_capture(tmp_path):
    args, _ = setup_campaign(tmp_path, first=rows_with_exit("99", "99.01", gap=True))
    result = module.simulate_registered_campaign(**args)
    assert result["market_fault_frames"] == 2 and result["ledger_order_count"] == 2
    assert result["source_sessions"][0]["market_fault_frames"] == 2
    assert result["source_sessions"][1]["market_fault_frames"] == 0
    assert D(result["position_btc"]) == 0
    assert not evaluate(args)["full_session_flat_comparison_available"]


def test_retries_do_not_call_policy_or_duplicate_orders_and_smaller_budget_is_refused(
    tmp_path, monkeypatch
):
    args, _ = setup_campaign(tmp_path)
    first = module.simulate_registered_campaign(**args)

    def forbidden(*args, **kwargs):
        pytest.fail("Exact retry reassessed historical policy.")

    monkeypatch.setattr(single, "_build_case", forbidden)
    assert module.simulate_registered_campaign(**args, resume=True) == first
    before = fingerprint(args["journal_path"])
    with pytest.raises(JournalError, match="cannot omit"):
        module.simulate_registered_campaign(**{**args, "max_frames": 12}, resume=True)
    assert fingerprint(args["journal_path"]) == before


@pytest.mark.parametrize("resume", [False, True])
def test_failure_rolls_back_new_batch_including_cross_session_protection(
    tmp_path, monkeypatch, resume
):
    args, record = setup_campaign(tmp_path)
    if resume:
        module.simulate_registered_campaign(**{**args, "max_frames": 12})
    original = single._build_case

    def crash(record, frame, context):
        if frame.tick.source_session == "research-2" and frame.status == "session_closed":
            assert context.account.position_btc == 0
            raise RuntimeError("synthetic failure after recovery exit")
        return original(record, frame, context)

    monkeypatch.setattr(single, "_build_case", crash)
    with pytest.raises(RuntimeError, match="recovery exit"):
        module.simulate_registered_campaign(**args, resume=resume)
    with open_campaign(args, record) as journal:
        if resume:
            assert len(journal.order_ids()) == 1 and journal.account_state().position_btc == D(
                "0.998"
            )
        else:
            assert journal.account_seed() is None and journal.order_ids() == ()


@pytest.mark.parametrize(
    "selection", ["reordered", "omitted", "duplicate", "reserved", "unknown", "list"]
)
def test_bad_source_scope_refused_before_capture_io(tmp_path, monkeypatch, selection):
    args, _ = setup_campaign(tmp_path)
    sources = args["sources"]
    if selection == "reordered":
        sources = sources[::-1]
    elif selection == "omitted":
        sources = sources[1:]
    elif selection == "duplicate":
        sources = (sources[0], sources[0])
    elif selection == "list":
        sources = list(sources)
    else:
        sources = (sources[0], module.CampaignInput(selection, tmp_path / "do-not-open"))

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid source selection reached capture IO.")

    monkeypatch.setattr(module.CaptureReplay, "from_path", forbidden)
    with pytest.raises(ValueError, match="every registered research"):
        module.simulate_registered_campaign(**{**args, "sources": sources})
    with pytest.raises(ValueError, match="every registered research"):
        evaluation.evaluate_registered_campaign(
            **{k: v for k, v in args.items() if k != "enable_paper_simulation"}
            | {"sources": sources}
        )
    assert not args["journal_path"].exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"enable_paper_simulation": False},
        {"enable_paper_simulation": 1},
        {"enable_paper_simulation": "yes"},
        {"resume": "yes"},
        {"max_frames": True},
        {"max_frames": 0},
        {"max_frames": 10001},
    ],
)
def test_activation_and_budget_validation_before_io(tmp_path, monkeypatch, changes):
    args, _ = setup_campaign(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid activation/budget attempted registration IO.")

    monkeypatch.setattr(module, "load_registration", forbidden)
    with pytest.raises(ValueError):
        module.simulate_registered_campaign(**(args | changes))


def test_resume_requires_activation_and_never_overwrites_or_converts_single_run(tmp_path):
    args, record = setup_campaign(tmp_path)
    source = args["sources"][0]
    single.simulate_registered_capture(
        registration_path=args["registration_path"],
        capture_path=source.capture_path,
        source_session=source.source_session,
        journal_path=args["journal_path"],
        max_frames=100,
        enable_paper_simulation=True,
    )
    with pytest.raises(FileExistsError):
        module.simulate_registered_campaign(**args)
    with pytest.raises(JournalError, match="identity"):
        module.simulate_registered_campaign(**args, resume=True)
    with pytest.raises(ValueError, match="Explicit"):
        module.simulate_registered_campaign(
            **(args | {"enable_paper_simulation": False}), resume=True
        )
    with pytest.raises(JournalError, match="identity"):
        evaluate(args)


def test_later_source_must_pass_hash_preflight_before_any_paper_write(tmp_path):
    args, _ = setup_campaign(tmp_path)
    args["sources"][1].capture_path.write_bytes(b"corrupt capture")
    with pytest.raises(ValueError, match="checksum"):
        module.simulate_registered_campaign(**args)
    assert not args["journal_path"].exists()


def test_aggregate_byte_budget_preflight(tmp_path, monkeypatch):
    args, _ = setup_campaign(tmp_path)
    monkeypatch.setattr(
        module, "MAX_CAMPAIGN_BYTES", args["sources"][0].capture_path.stat().st_size
    )
    with pytest.raises(ValueError, match="byte budget"):
        module.simulate_registered_campaign(**args)
    assert not args["journal_path"].exists()


def test_changed_implementation_during_campaign_rolls_back(tmp_path, monkeypatch):
    args, record = setup_campaign(tmp_path)
    monkeypatch.setattr(single, "_implementation_hash", lambda: "a" * 64)
    with pytest.raises(ValueError, match="during simulation"):
        module.simulate_registered_campaign(**args)
    with open_campaign(args, record) as journal:
        assert journal.account_seed() is None and journal.order_ids() == ()


def test_global_evaluation_is_read_only_stable_and_refuses_partial_ledger_selection(
    tmp_path, monkeypatch
):
    args, _ = setup_campaign(tmp_path)
    module.simulate_registered_campaign(**args)
    before = fingerprint(args["journal_path"])

    def forbidden(*args, **kwargs):
        pytest.fail("Evaluation attempted journal writes.")

    monkeypatch.setattr(TradeJournal, "_write", forbidden)
    first = evaluate(args)
    assert evaluate(args) == first and fingerprint(args["journal_path"]) == before
    assert len(first["source_sessions"]) == 2 and first["source_session"] is None
    with pytest.raises(JournalError, match="every committed tick"):
        evaluate(args | {"max_frames": 12})


def test_first_session_footer_is_not_campaign_completion_even_when_record_counts_match(tmp_path):
    args, _ = setup_campaign(tmp_path, second=shifted(capture_rows()))
    module.simulate_registered_campaign(**(args | {"max_frames": 12}))
    report = evaluate(args)
    assert report["source_sessions"][0]["session_consumed"]
    assert report["source_sessions"][1]["frames_evaluated"] == 0
    assert report["truncated"] and not report["campaign_consumed"]


@pytest.mark.parametrize(
    "command,frames,expected_code",
    [
        ("simulate", 100, 0),
        ("simulate", 12, 2),
        ("evaluate", 100, 0),
        ("evaluate", 12, 2),
    ],
)
def test_campaign_clis_use_explicit_ordered_paths(
    tmp_path, monkeypatch, capsys, command, frames, expected_code
):
    args, _ = setup_campaign(tmp_path, settings=replace(policy(), rule="abstain"))
    if command == "evaluate":
        module.simulate_registered_campaign(**(args | {"max_frames": frames}))
    argv = [
        command,
        "--registration",
        str(args["registration_path"]),
        "--journal",
        str(args["journal_path"]),
        "--max-frames",
        str(frames),
    ]
    for source in args["sources"]:
        argv += ["--source", source.source_session, str(source.capture_path)]
    if command == "simulate":
        argv += ["--enable-paper-simulation"]
    monkeypatch.setattr(sys, "argv", argv)
    main = module.main if command == "simulate" else evaluation.main
    if expected_code:
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == expected_code
    else:
        main()
    report = json.loads(capsys.readouterr().out)
    assert report["campaign_consumed"] is (expected_code == 0)
    assert report["live_trading_available"] is False


def test_kill_blocks_a_warmed_up_signal_in_a_later_session(tmp_path):
    args, record = setup_campaign(tmp_path, first=rows_with_exit(), second=shifted(capture_rows()))
    module.simulate_registered_campaign(**(args | {"max_frames": 13}))
    with open_campaign(args, record) as journal:
        DurablePaperGateway(journal, record.gateway).set_kill_switch(True, observed_at_ns=1600 * MS)
    result = module.simulate_registered_campaign(**args, resume=True)
    assert result["kill_switch_active"] and result["ledger_order_count"] == 2
    assert result["case_reason_counts"]["risk_rejected:kill_switch_active"] == 1


def test_three_sources_share_one_seed_and_completion_cannot_stop_after_two(tmp_path):
    args, record = setup_campaign(
        tmp_path, third=shifted(capture_rows(), ms=2000), settings=replace(policy(), rule="abstain")
    )
    prefix = module.simulate_registered_campaign(**(args | {"max_frames": 15}))
    assert [s["session_consumed"] for s in prefix["source_sessions"]] == [True, True, False]
    assert not prefix["campaign_consumed"] and evaluate(args)["truncated"]
    final = module.simulate_registered_campaign(**args, resume=True)
    assert final["campaign_consumed"] and final["frames_processed"] == 27
    assert final["cash_usdt"] == "1000" and final["ledger_order_count"] == 0
    with open_campaign(args, record) as journal:
        assert journal.account_seed().initialized_at_ns == 950 * MS
    assert evaluate(args)["full_campaign_flat_comparison_available"]


def test_aggregate_budget_rechecks_actual_bytes_not_just_stat(tmp_path, monkeypatch):
    args, _ = setup_campaign(tmp_path)
    paths = {s.capture_path for s in args["sources"]}
    size = sum(p.stat().st_size for p in paths)
    original = Path.stat

    def underestimated(path, *values, **kwargs):
        if path in paths:
            return SimpleNamespace(st_size=0)
        return original(path, *values, **kwargs)

    monkeypatch.setattr(Path, "stat", underestimated)
    monkeypatch.setattr(module, "MAX_CAMPAIGN_BYTES", size - 1)
    with pytest.raises(ValueError, match="byte budget"):
        module.simulate_registered_campaign(**args)
    assert not args["journal_path"].exists()


def test_changed_registration_cannot_resume_existing_funds(tmp_path):
    args, record = setup_campaign(tmp_path)
    module.simulate_registered_campaign(**(args | {"max_frames": 12}))
    alternate = tmp_path / "alternate.json"
    register_trial(
        alternate,
        trial_id=record.trial_id,
        sources=record.sources,
        policy=replace(record.policy, maximum_hold_ns=500 * MS),
        replay=record.replay,
        gateway=record.gateway,
        initial_cash_usdt=record.initial_cash_usdt,
    )
    before = fingerprint(args["journal_path"])
    with pytest.raises(JournalError, match="identity"):
        module.simulate_registered_campaign(
            **(args | {"registration_path": alternate}), resume=True
        )
    assert fingerprint(args["journal_path"]) == before


def test_corrupt_committed_tick_order_is_not_silently_adopted(tmp_path):
    args, record = setup_campaign(tmp_path)
    module.simulate_registered_campaign(**(args | {"max_frames": 12}))
    with open_campaign(args, record) as journal:
        journal._db.execute("DROP TRIGGER paper_runner_ticks_no_update")
        journal._db.execute("UPDATE paper_runner_ticks SET tick_id='unexpected' WHERE sequence=1")
    with pytest.raises(JournalError, match="registered prefix"):
        module.simulate_registered_campaign(**args, resume=True)


def test_evaluation_source_drift_has_no_success_report_or_ledger_write(tmp_path, monkeypatch):
    args, _ = setup_campaign(tmp_path)
    module.simulate_registered_campaign(**args)
    before = fingerprint(args["journal_path"])
    monkeypatch.setattr(evaluation, "_environment", lambda: "changed")
    with pytest.raises(ValueError, match="during campaign evaluation"):
        evaluate(args)
    assert fingerprint(args["journal_path"]) == before


def test_drawdown_limit_carries_into_later_session(tmp_path):
    config = gateway_config()
    config = replace(config, limits=replace(config.limits, max_drawdown_usdt=D("0.5")))
    args, record = setup_campaign(
        tmp_path,
        first=rows_with_exit("99.6", "99.61"),
        second=shifted(capture_rows()),
        config=config,
    )
    result = module.simulate_registered_campaign(**args)
    assert result["ledger_order_count"] == 2 and D(result["realized_pnl_usdt"]) < D("-0.5")
    assert result["case_reason_counts"]["risk_rejected:drawdown_limit_reached"] == 1
    with open_campaign(args, record) as journal:
        assert journal.get_order(result["exit_order_ids_in_prefix"][0]).reason == "drawdown_limit"


@pytest.mark.parametrize("budget", [True, 0, 10001])
def test_evaluation_budget_rejected_before_io(tmp_path, monkeypatch, budget):
    args, _ = setup_campaign(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid evaluation budget reached registration IO.")

    monkeypatch.setattr(evaluation, "load_registration", forbidden)
    with pytest.raises(ValueError, match="budget"):
        evaluate(args | {"max_frames": budget})
