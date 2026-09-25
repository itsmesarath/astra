"""Synthetic registered capture -> policy -> ledger-risk -> full quote fills only."""

import hashlib
import json
import socket
import sys
from dataclasses import replace
from decimal import Decimal

import pytest
from test_microstructure_policy import (
    capture_bytes,
    capture_rows,
    gateway_config,
    policy,
    replay_config,
)

from ai_trader.research.microstructure_trial import (
    SourceDeclaration,
    load_registration,
    register_trial,
)
from ai_trader.trading import microstructure_paper as module
from ai_trader.trading.capture_replay import CaptureReplay
from ai_trader.trading.durable_paper_gateway import DurablePaperGateway
from ai_trader.trading.trade_journal import JournalConflict, TradeJournal, _hash

D = Decimal
MS = 1_000_000
INITIAL_CASH = D("1000")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No networking allowed in paper strategy tests.")

    monkeypatch.setattr(socket, "create_connection", forbidden)


def rows_with_exit(bid="101.2", ask="101.21", gap=False):
    rows = capture_rows()
    rows[1]["event"]["bids"][1][0] = "90"
    rows[1]["event"]["asks"][1][0] = "110"
    rows.insert(
        -1,
        {
            "schema_version": 1,
            "record_type": "stream_event",
            "stream": "btcusdt@depth@100ms",
            "received_at_ns": 1500 * MS,
            "event": {
                "e": "depthUpdate",
                "s": "BTCUSDT",
                "E": 1500,
                "U": 200 if gap else 105,
                "u": 200 if gap else 105,
                "b": [["100", "0"], [bid, "8"]] if bid != "100" else [[bid, "8"]],
                "a": [["100.01", "0"], [ask, "3"]] if ask != "100.01" else [[ask, "3"]],
            },
        },
    )
    rows[-1].update(ended_at_ns=1600 * MS, depth_events=5)
    return rows


def setup_run(tmp_path, *, rows=None, settings=None, gateway=None, initial_cash=INITIAL_CASH):
    rows = rows_with_exit() if rows is None else rows
    data = capture_bytes(rows)
    declaration = SourceDeclaration(
        "research-one",
        hashlib.sha256(data).hexdigest(),
        rows[0]["started_at_ns"],
        rows[-1]["ended_at_ns"],
        "research",
    )
    reserved = SourceDeclaration("reserved-one", "f" * 64, 3000 * MS, 4000 * MS, "reserved")
    registration_path = tmp_path / "registration.json"
    record = register_trial(
        registration_path,
        trial_id="paper-experiment",
        sources=(declaration, reserved),
        policy=settings or policy(),
        replay=replay_config(),
        gateway=gateway or gateway_config(),
        initial_cash_usdt=initial_cash,
    )
    path = tmp_path / "capture.jsonl"
    path.write_bytes(data)
    args = dict(
        registration_path=registration_path,
        capture_path=path,
        source_session="research-one",
        journal_path=tmp_path / "paper.sqlite",
        max_frames=100,
        enable_paper_simulation=True,
    )
    return args, record


def open_journal(args):
    # Reconstruct run identity without executing or reevaluating a registration.
    checksum = json.loads(args["registration_path"].read_text())["registration_sha256"]
    run_id = "micro-paper-" + _hash(
        module.ADAPTER_VERSION + ":" + checksum + ":" + args["source_session"]
    )
    return TradeJournal(args["journal_path"], run_id=run_id, mode="paper")


def stored_cases(journal):
    return [
        journal.get_case(row[0])
        for row in journal._db.execute("SELECT case_id FROM cases ORDER BY rowid")
    ]


def test_full_round_trip_actual_ledger_accounting_and_no_same_tick_reentry(tmp_path):
    args, registration = setup_run(tmp_path)
    report = module.simulate_registered_capture(**args)
    assert report["mode"] == "offline_paper_simulation"
    assert report["session_consumed"] and report["market_fault_frames"] == 0
    assert len(report["entry_order_ids_in_prefix"]) == len(report["exit_order_ids_in_prefix"]) == 1
    assert report["ledger_order_count"] == 2 and report["position_btc"] == "0.000"
    assert report["promotion_allowed"] is False and report["live_trading_available"] is False
    quantity = D("0.998")
    entry = D("100.01") * D("1.0005")
    exit_price = D("101.2") * D("0.9995")
    expected_pnl = quantity * (exit_price * D("0.999") - entry * D("1.001"))
    assert D(report["realized_pnl_usdt"]) == expected_pnl
    assert D(report["cash_usdt"]) == D("1000") + expected_pnl
    assert D(report["fees_usdt"]) == quantity * (entry + exit_price) * D("0.001")
    with open_journal(args) as journal:
        cases = stored_cases(journal)
        assert len(cases) == report["frames_processed"] == 13
        assert all(c.mode == "paper" for c in cases)
        assert journal.get_order(report["exit_order_ids_in_prefix"][0]).reason == "take_profit"
        protective = next(c for c in cases if c.decision_at_ns == 1500 * MS)
        assert protective.risk_reason == "protective_exit_tick" and protective.action == "NO_ACTION"
        assert all(
            any(e.evidence_id == "paper_decision_context" for e in c.evidence) for c in cases
        )
    assert (
        load_registration(args["registration_path"]) == registration
    )  # Unchanged research record.


@pytest.mark.parametrize(
    "bid,ask,hold,reason",
    [
        ("99.7", "99.71", 10000, "stop_loss"),
        ("99", "99.01", 10000, "stop_loss"),
        ("100", "100.01", 100, "maximum_hold"),
    ],
)
def test_protection_with_stale_trades_and_gap_price_not_invented(tmp_path, bid, ask, hold, reason):
    args, _ = setup_run(
        tmp_path,
        rows=rows_with_exit(bid, ask),
        settings=replace(policy(), maximum_hold_ns=hold * MS),
    )
    report = module.simulate_registered_capture(**args)
    with open_journal(args) as journal:
        exit_id = report["exit_order_ids_in_prefix"][0]
        assert journal.get_order(exit_id).reason == reason
        fills = [e for e in journal.order_events(exit_id) if e.kind == "FILL"]
        assert fills[0].price_usdt == D(bid) * D("0.9995")
        assert journal.account_state().position_btc == 0


def test_open_inventory_is_not_liquidated_at_footer(tmp_path):
    args, _ = setup_run(tmp_path, rows=capture_rows())
    report = module.simulate_registered_capture(**args)
    assert report["session_consumed"] and D(report["position_btc"]) == D("0.998")
    assert report["ledger_order_count"] == 1 and report["exit_order_ids_in_prefix"] == []
    assert report["blocked_exit_entry_ids_at_prefix_end"] == report["entry_order_ids_in_prefix"]


def test_gap_blocks_protection_and_retains_position_instead_of_fake_fill(tmp_path):
    args, _ = setup_run(tmp_path, rows=rows_with_exit("99", "99.01", gap=True))
    report = module.simulate_registered_capture(**args)
    assert report["session_consumed"] and report["market_fault_frames"] == 2
    assert D(report["position_btc"]) == D("0.998")
    assert report["ledger_order_count"] == 1
    assert report["blocked_exit_entry_ids_at_prefix_end"]


def test_explicit_prefix_resume_reuses_cases_not_later_balances(tmp_path, monkeypatch):
    args, _ = setup_run(tmp_path)
    first = module.simulate_registered_capture(**{**args, "max_frames": 11})
    assert D(first["position_btc"]) == D("0.998")
    calls = []
    original = module._build_case

    def counting(registration, frame, context):
        calls.append(frame.line_number)
        return original(registration, frame, context)

    monkeypatch.setattr(module, "_build_case", counting)
    resumed = module.simulate_registered_capture(**args, resume=True)
    assert len(calls) == 2  # Only exit and footer, not historical entry with today's balance.
    calls.clear()
    assert module.simulate_registered_capture(**args, resume=True) == resumed
    assert calls == [] and resumed["ledger_order_count"] == 2
    small = module.simulate_registered_capture(**{**args, "max_frames": 2}, resume=True)
    assert small["ledger_order_count"] == 2 and small["cash_usdt"] == resumed["cash_usdt"]
    assert small["entry_order_ids_in_prefix"] == []


def test_kill_switch_survives_resume_and_new_cases_use_ledger_state(tmp_path):
    args, registration = setup_run(tmp_path)
    module.simulate_registered_capture(**{**args, "max_frames": 2})
    with open_journal(args) as journal:
        gateway = DurablePaperGateway(journal, registration.gateway)
        gateway.set_kill_switch(True, observed_at_ns=gateway.risk_checkpoint().observed_at_ns)
    report = module.simulate_registered_capture(**args, resume=True)
    assert report["kill_switch_active"] and report["ledger_order_count"] == 0
    assert report["case_reason_counts"]["risk_rejected:kill_switch_active"] == 1


def test_resume_still_requires_explicit_activation_and_does_not_change_ledger(tmp_path):
    args, _ = setup_run(tmp_path)
    first = module.simulate_registered_capture(**{**args, "max_frames": 11})
    with pytest.raises(ValueError, match="Explicit"):
        module.simulate_registered_capture(
            **{**args, "enable_paper_simulation": False}, resume=True
        )
    with open_journal(args) as journal:
        assert len(journal.order_ids()) == first["ledger_order_count"]
        assert journal.account_state().position_btc == D(first["position_btc"])


def test_retry_checks_full_frame_evidence_even_when_tick_is_unchanged(tmp_path, monkeypatch):
    args, _ = setup_run(tmp_path)
    first = module.simulate_registered_capture(**{**args, "max_frames": 11})
    original = CaptureReplay.frames

    def changed_frames(replay):
        for frame in original(replay):
            yield replace(frame, status=frame.status + ":changed")

    monkeypatch.setattr(CaptureReplay, "frames", changed_frames)
    with pytest.raises(JournalConflict, match="evidence"):
        module.simulate_registered_capture(**args, resume=True)
    with open_journal(args) as journal:
        assert len(journal.order_ids()) == first["ledger_order_count"]
        assert journal.account_state().position_btc == D(first["position_btc"])


def test_kill_switch_does_not_block_stop_exit_or_get_reset(tmp_path):
    args, registration = setup_run(tmp_path, rows=rows_with_exit("99.7", "99.71"))
    module.simulate_registered_capture(**{**args, "max_frames": 11})
    with open_journal(args) as journal:
        gateway = DurablePaperGateway(journal, registration.gateway)
        gateway.set_kill_switch(True, observed_at_ns=1300 * MS)
    report = module.simulate_registered_capture(**args, resume=True)
    assert report["kill_switch_active"] and D(report["position_btc"]) == 0
    assert len(report["exit_order_ids_in_prefix"]) == 1


def test_policy_not_called_on_protection_tick(tmp_path, monkeypatch):
    args, _ = setup_run(tmp_path)
    module.simulate_registered_capture(**{**args, "max_frames": 11})
    original = module.assess_microstructure

    def guarded(frame, **kwargs):
        if frame.tick.observed_at_ns == 1500 * MS:
            pytest.fail("Entry policy was invoked on a protective-exit tick.")
        return original(frame, **kwargs)

    monkeypatch.setattr(module, "assess_microstructure", guarded)
    report = module.simulate_registered_capture(**args, resume=True)
    assert D(report["position_btc"]) == 0


def test_small_account_and_hard_limits_retain_rejected_cases_without_orders(tmp_path):
    args, _ = setup_run(tmp_path, initial_cash=D("50"))
    report = module.simulate_registered_capture(**args)
    assert report["ledger_order_count"] == 0
    assert report["case_reason_counts"]["insufficient_spot_cash"] == 1


@pytest.mark.parametrize("activation", [False, None, "yes", 1])
def test_activation_required_before_any_io(tmp_path, monkeypatch, activation):
    def forbidden(*args, **kwargs):
        pytest.fail("Unactivated call attempted to read registration.")

    monkeypatch.setattr(module, "load_registration", forbidden)
    with pytest.raises(ValueError, match="Explicit"):
        module.simulate_registered_capture(
            registration_path=tmp_path / "missing.json",
            capture_path=tmp_path / "missing.jsonl",
            journal_path=tmp_path / "missing.sqlite",
            source_session="research-one",
            max_frames=1,
            enable_paper_simulation=activation,
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("source", ["reserved-one", "unknown"])
def test_reserved_and_unregistered_source_rejected_before_capture(tmp_path, monkeypatch, source):
    args, _ = setup_run(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("Reserved/unknown source reached capture loader.")

    monkeypatch.setattr(CaptureReplay, "from_path", forbidden)
    with pytest.raises(ValueError, match="registered research"):
        module.simulate_registered_capture(**{**args, "source_session": source})
    assert not args["journal_path"].exists()


def test_changed_registration_or_existing_destination_fails_closed(tmp_path):
    args, registration = setup_run(tmp_path)
    module.simulate_registered_capture(**{**args, "max_frames": 2})
    with pytest.raises(FileExistsError):
        module.simulate_registered_capture(**args)
    alternate = tmp_path / "alternate.json"
    register_trial(
        alternate,
        trial_id=registration.trial_id,
        sources=registration.sources,
        policy=replace(policy(), maximum_hold_ns=500 * MS),
        replay=registration.replay,
        gateway=registration.gateway,
        initial_cash_usdt=registration.initial_cash_usdt,
    )
    with pytest.raises(ValueError, match="identity"):
        module.simulate_registered_capture(**{**args, "registration_path": alternate}, resume=True)


def test_mid_invocation_failure_rolls_back_protection_but_preserves_previous_prefix(
    tmp_path, monkeypatch
):
    args, _ = setup_run(tmp_path)
    module.simulate_registered_capture(**{**args, "max_frames": 11})
    original = module._build_case

    def fail(registration, frame, context):
        if frame.tick.observed_at_ns == 1600 * MS:
            raise RuntimeError("crash after the exit tick")
        return original(registration, frame, context)

    monkeypatch.setattr(module, "_build_case", fail)
    with pytest.raises(RuntimeError, match="crash"):
        module.simulate_registered_capture(**args, resume=True)
    with open_journal(args) as journal:
        assert len(journal.order_ids()) == 1 and journal.account_state().position_btc == D("0.998")
        assert len(stored_cases(journal)) == 11


def test_new_run_failure_leaves_no_committed_account_case_or_order(tmp_path, monkeypatch):
    args, _ = setup_run(tmp_path)

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic initialization failure")

    monkeypatch.setattr(module, "_build_case", fail)
    with pytest.raises(RuntimeError):
        module.simulate_registered_capture(**args)
    with open_journal(args) as journal:
        assert journal.account_seed() is None and journal.order_ids() == ()
        assert stored_cases(journal) == []


def test_current_source_code_change_rolls_back_entire_simulation(tmp_path, monkeypatch):
    args, _ = setup_run(tmp_path)
    monkeypatch.setattr(module, "_implementation_hash", lambda: "a" * 64)
    with pytest.raises(ValueError, match="during simulation"):
        module.simulate_registered_capture(**args)
    with open_journal(args) as journal:
        assert journal.account_seed() is None and journal.order_ids() == ()


@pytest.mark.parametrize(
    "changes", [{"max_frames": 0}, {"max_frames": True}, {"max_frames": 10001}, {"resume": "yes"}]
)
def test_invalid_budget_or_resume_flag_before_io(tmp_path, monkeypatch, changes):
    args, _ = setup_run(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid configuration attempted IO.")

    monkeypatch.setattr(module, "load_registration", forbidden)
    with pytest.raises(ValueError):
        module.simulate_registered_capture(**(args | changes))


def test_no_trade_control_preserves_funds(tmp_path):
    args, _ = setup_run(tmp_path, settings=replace(policy(), rule="abstain"))
    report = module.simulate_registered_capture(**args)
    assert report["ledger_order_count"] == 0 and report["cash_usdt"] == "1000"
    assert report["case_reason_counts"] == {"no_trade_control": 13}


@pytest.mark.parametrize("gap", [False, True])
def test_cli_simulated_roundtrip_with_explicit_activation(tmp_path, monkeypatch, capsys, gap):
    args, _ = setup_run(tmp_path, rows=rows_with_exit(gap=gap))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "paper",
            "--registration",
            str(args["registration_path"]),
            "--capture",
            str(args["capture_path"]),
            "--source-session",
            "research-one",
            "--journal",
            str(args["journal_path"]),
            "--max-frames",
            "100",
            "--enable-paper-simulation",
        ],
    )
    if gap:
        with pytest.raises(SystemExit) as error:
            module.main()
        assert error.value.code == 2
    else:
        module.main()
    report = json.loads(capsys.readouterr().out)
    assert report["ledger_order_count"] == (1 if gap else 2)
    assert report["live_trading_available"] is False
    assert report["market_fault_frames"] == (2 if gap else 0)


def append_interval(rows, *, timestamp, bid, ask, before_bid, after_bid, after_ask):
    next_trade = rows[-1]["trade_events"] + 1
    next_depth = 101 + rows[-1]["depth_events"]
    for trade_id, when, qty, sell in [
        (next_trade, timestamp - 60, before_bid, True),
        (next_trade + 1, timestamp - 50, before_bid + 2, False),
    ]:
        rows.insert(
            -1,
            {
                "schema_version": 1,
                "record_type": "stream_event",
                "stream": "btcusdt@aggTrade",
                "received_at_ns": when * MS,
                "event": {
                    "e": "aggTrade",
                    "s": "BTCUSDT",
                    "E": when,
                    "T": when,
                    "a": trade_id,
                    "f": trade_id,
                    "l": trade_id,
                    "p": ask if not sell else bid,
                    "q": str(qty),
                    "m": sell,
                },
            },
        )
    rows.insert(
        -1,
        {
            "schema_version": 1,
            "record_type": "stream_event",
            "stream": "btcusdt@depth@100ms",
            "received_at_ns": timestamp * MS,
            "event": {
                "e": "depthUpdate",
                "s": "BTCUSDT",
                "E": timestamp,
                "U": next_depth,
                "u": next_depth,
                "b": [[bid, str(after_bid)]],
                "a": [[ask, str(after_ask)]],
            },
        },
    )
    rows[-1]["trade_events"] += 2
    rows[-1]["depth_events"] += 1
    rows[-1]["ended_at_ns"] = (timestamp + 100) * MS


def test_second_valid_signal_sees_existing_inventory_not_initial_flat_seed(tmp_path):
    rows = capture_rows()
    append_interval(
        rows, timestamp=1400, bid="100", ask="100.01", before_bid=8, after_bid=10, after_ask=1
    )
    args, _ = setup_run(tmp_path, rows=rows)
    report = module.simulate_registered_capture(**args)
    assert report["case_reason_counts"]["existing_inventory_or_unresolved_orders"] == 1
    assert len(report["entry_order_ids_in_prefix"]) == report["ledger_order_count"] == 1


def test_realized_loss_from_ledger_blocks_the_next_eligible_entry(tmp_path):
    rows = rows_with_exit("99.7", "99.71")
    for i in range(3):
        append_interval(
            rows,
            timestamp=1600 + i * 100,
            bid="99.7",
            ask="99.71",
            before_bid=8 + i * 2,
            after_bid=10 + i * 2,
            after_ask=[10, 9, 1][i],
        )
    config = gateway_config()
    config = replace(config, limits=replace(config.limits, max_daily_loss_usdt=D("0.5")))
    args, _ = setup_run(tmp_path, rows=rows, gateway=config)
    report = module.simulate_registered_capture(**args)
    assert report["ledger_order_count"] == 2 and D(report["realized_pnl_usdt"]) < D("-0.5")
    assert report["case_reason_counts"]["risk_rejected:daily_loss_limit_reached"] == 1
