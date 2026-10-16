"""Costed, source-local outcome labels using synthetic quotes only."""

import hashlib
import json
import socket
import sys
from dataclasses import replace
from decimal import Decimal, localcontext

import pytest
from test_microstructure_paper import MS, setup_run
from test_microstructure_policy import capture_rows, gateway_config, policy, signal_frame

from ai_trader.training import microstructure_data as module

D = Decimal


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Event labeling attempted network access.")

    monkeypatch.setattr(socket, "create_connection", forbidden)


def rows_with_quote(*, timestamp=1300, bid="100", ask="100.01", gap=False):
    rows = capture_rows()
    rows[1]["event"]["bids"][1][0] = "90"
    rows[1]["event"]["asks"][1][0] = "110"
    row = next(
        r
        for r in rows
        if r.get("event", {}).get("e") == "depthUpdate" and r["event"]["E"] == timestamp
    )
    row["event"]["b"] = [["100", "0"], [bid, "8"]] if bid != "100" else [[bid, "8"]]
    row["event"]["a"] = [["100.01", "0"], [ask, "3"]] if ask != "100.01" else [[ask, "3"]]
    if gap:
        row["event"].update(U=999, u=999)
    return rows


def setup(tmp_path, *, rows=None, settings=None, gateway=None):
    args, record = setup_run(
        tmp_path,
        rows=rows_with_quote() if rows is None else rows,
        settings=settings or replace(policy(), entry_ttl_ns=200 * MS, maximum_hold_ns=100 * MS),
        gateway=gateway,
    )
    del args["enable_paper_simulation"], args["journal_path"]
    return args, record


def example(dataset, when=1100):
    return next(r for r in dataset["examples"] if r["feature_available_at_ns"] == when * MS)


def test_horizon_outcome_uses_next_quote_costs_once_and_no_strategy_signal_filter(tmp_path):
    args, _ = setup(tmp_path)
    result = module.build_registered_event_dataset(**args)
    row = example(result)
    label = row["outcome"]
    assert row["eligibility_reason"] == "eligible"
    assert D(row["features"]["book_imbalance"]) < 0  # Current strategy would not approve.
    assert label["status"] == "resolved" and label["reason"] == "horizon"
    assert label["entry_at_ns"] == 1200 * MS
    assert label["exit_at_ns"] == label["known_at_ns"] == label["horizon_at_ns"] == 1300 * MS
    entry, exit_price = D("100.01") * D("1.0005"), D("100") * D("0.9995")
    with localcontext(module.DECIMAL_CONTEXT):
        debit = entry * D("1.001")
        expected = (exit_price * D("0.999") - debit) / debit
    assert D(label["net_return_fraction"]) == expected < 0 and label["direction"] == -1
    assert D(label["entry_price_usdt"]) == entry and D(label["exit_price_usdt"]) == exit_price
    assert result["frames_processed"] == len(result["examples"]) == 12
    assert result["outcome_counts"] == {"excluded": 9, "resolved": 1, "censored": 2}
    assert not result["training_started"] and not result["live_trading_available"]
    assert not (tmp_path / "paper.sqlite").exists()


@pytest.mark.parametrize(
    "bid,ask,reason,direction",
    [
        ("101.2", "101.21", "target", 1),
        ("99.7", "99.71", "stop", -1),
        ("99", "99.01", "stop", -1),
    ],
)
def test_barrier_precedence_and_price_gap_fill_at_actual_quote(
    tmp_path, bid, ask, reason, direction
):
    args, _ = setup(tmp_path, rows=rows_with_quote(bid=bid, ask=ask))
    outcome = example(module.build_registered_event_dataset(**args))["outcome"]
    assert outcome["reason"] == reason and outcome["direction"] == direction
    assert outcome["exit_at_ns"] == 1300 * MS
    assert D(outcome["exit_price_usdt"]) == D(bid) * D("0.9995")


def test_target_price_hit_can_still_be_negative_after_costs(tmp_path):
    gateway = gateway_config()
    gateway = replace(gateway, costs=replace(gateway.costs, taker_fee_bps=D("100")))
    args, _ = setup(tmp_path, rows=rows_with_quote(bid="101.2", ask="101.21"), gateway=gateway)
    outcome = example(module.build_registered_event_dataset(**args))["outcome"]
    assert outcome["reason"] == "target" and outcome["direction"] == -1
    assert D(outcome["net_return_fraction"]) < 0


def test_exact_breakeven_is_distinct_from_unknown(tmp_path):
    gateway = gateway_config()
    gateway = replace(gateway, costs=replace(gateway.costs, taker_fee_bps=D(0), slippage_bps=D(0)))
    args, _ = setup(tmp_path, rows=rows_with_quote(bid="100.01", ask="100.02"), gateway=gateway)
    outcome = example(module.build_registered_event_dataset(**args))["outcome"]
    assert outcome["status"] == "resolved"
    assert outcome["direction"] == 0 and D(outcome["net_return_fraction"]) == 0


def test_horizon_uses_first_later_depth_not_a_trade_or_invented_quote(tmp_path):
    args, _ = setup(
        tmp_path, settings=replace(policy(), entry_ttl_ns=200 * MS, maximum_hold_ns=50 * MS)
    )
    outcome = example(module.build_registered_event_dataset(**args))["outcome"]
    assert outcome["horizon_at_ns"] == 1250 * MS
    assert outcome["exit_at_ns"] == outcome["known_at_ns"] == 1300 * MS
    assert outcome["reason"] == "horizon"


def test_session_footer_never_provides_a_fake_horizon_exit(tmp_path):
    args, _ = setup(tmp_path)
    outcome = example(module.build_registered_event_dataset(**args), 1200)["outcome"]
    assert outcome["entry_at_ns"] == 1300 * MS and outcome["horizon_at_ns"] == 1400 * MS
    assert outcome["status"] == "censored" and outcome["reason"] == "session_end"
    assert outcome["known_at_ns"] == 1400 * MS
    assert outcome["exit_at_ns"] is None and outcome["net_return_fraction"] is None
    assert outcome["direction"] is None


@pytest.mark.parametrize("frames,entered", [(5, False), (8, True)])
def test_processing_cutoff_censors_even_a_funded_hypothetical_entry(tmp_path, frames, entered):
    args, _ = setup(tmp_path)
    result = module.build_registered_event_dataset(**(args | {"max_frames": frames}))
    outcome = example(result)["outcome"]
    assert not result["session_consumed"] and result["frames_processed"] == frames
    assert outcome["status"] == "censored" and outcome["reason"] == "processing_cutoff"
    assert (outcome["entry_at_ns"] is not None) is entered
    assert outcome["direction"] is None and outcome["net_return_fraction"] is None


def test_entry_expiry_is_exclusive_and_is_not_a_neutral_label(tmp_path):
    args, _ = setup(tmp_path, settings=replace(policy(), maximum_hold_ns=100 * MS))
    outcome = example(module.build_registered_event_dataset(**args))["outcome"]
    assert outcome["status"] == "not_entered" and outcome["reason"] == "entry_expired"
    assert outcome["known_at_ns"] == 1200 * MS
    assert outcome["entry_at_ns"] is None and outcome["direction"] is None


@pytest.mark.parametrize(
    "bid,ask,reason",
    [
        ("101.2", "101.21", "entry_outside_bracket"),
        ("99.7", "99.71", "entry_outside_bracket"),
        ("100", "100.5", "entry_spread_limit"),
    ],
)
def test_first_future_quote_cannot_enter_outside_original_bracket_or_spread(
    tmp_path, bid, ask, reason
):
    args, _ = setup(tmp_path, rows=rows_with_quote(timestamp=1200, bid=bid, ask=ask))
    outcome = example(module.build_registered_event_dataset(**args))["outcome"]
    assert outcome["status"] == "not_entered" and outcome["reason"] == reason
    assert outcome["entry_price_usdt"] is None and outcome["net_return_fraction"] is None


def test_trade_only_record_can_expire_entry_but_cannot_fill_it(tmp_path):
    args, _ = setup(tmp_path, settings=replace(policy(), entry_ttl_ns=30 * MS))
    outcome = example(module.build_registered_event_dataset(**args))["outcome"]
    assert outcome["reason"] == "entry_expired" and outcome["known_at_ns"] == 1140 * MS
    assert outcome["entry_at_ns"] is None


@pytest.mark.parametrize(
    "age,reason,when", [(50, "interquote_gap", 1200), (40, "stale_quote", 1150)]
)
def test_missing_quote_path_censors_before_future_price_can_resolve_label(
    tmp_path, age, reason, when
):
    gateway = replace(gateway_config(), max_quote_age_ns=age * MS)
    args, _ = setup(tmp_path, gateway=gateway)
    outcome = example(module.build_registered_event_dataset(**args))["outcome"]
    assert outcome["status"] == "censored" and outcome["reason"] == reason
    assert outcome["known_at_ns"] == when * MS and outcome["direction"] is None


def test_sequence_gap_censors_all_pending_examples_without_erasing_prior_features(tmp_path):
    args, _ = setup(tmp_path, rows=rows_with_quote(timestamp=1200, gap=True))
    result = module.build_registered_event_dataset(**args)
    outcome = example(result)["outcome"]
    assert result["session_consumed"] and result["market_fault_frames"] > 0
    assert outcome["reason"] == "market_fault" and outcome["known_at_ns"] == 1200 * MS
    assert outcome["direction"] is None and example(result)["features"] is not None


def test_future_quotes_change_targets_but_not_earlier_feature_vectors(tmp_path):
    positive, negative = tmp_path / "up", tmp_path / "down"
    positive.mkdir()
    negative.mkdir()
    up, _ = setup(positive, rows=rows_with_quote(bid="101.2", ask="101.21"))
    down, _ = setup(negative, rows=rows_with_quote(bid="99", ask="99.01"))
    a = example(module.build_registered_event_dataset(**up))
    b = example(module.build_registered_event_dataset(**down))
    assert a["features"] == b["features"] and a["features_sha256"] == b["features_sha256"]
    assert a["observation_sha256"] == b["observation_sha256"]
    assert a["outcome"]["direction"] == 1 and b["outcome"]["direction"] == -1
    assert (
        not {"direction", "net_return_fraction", "known_at_ns", "exit_price_usdt"}
        & a["features"].keys()
    )


def test_abstain_strategy_and_signal_thresholds_do_not_select_training_examples(tmp_path):
    args, _ = setup(
        tmp_path,
        settings=replace(
            policy(),
            rule="abstain",
            minimum_cvd_btc=D("999"),
            minimum_ofi_btc=D("999"),
            entry_ttl_ns=200 * MS,
            maximum_hold_ns=100 * MS,
        ),
    )
    result = module.build_registered_event_dataset(**args)
    assert example(result)["outcome"]["status"] == "resolved"


def test_negative_cvd_is_retained_and_feature_schema_is_explicit(tmp_path):
    rows = rows_with_quote()
    for row in rows:
        event = row.get("event", {})
        if event.get("e") == "aggTrade" and event["m"]:
            event["q"] = "10"
    args, _ = setup(tmp_path, rows=rows)
    dataset = module.build_registered_event_dataset(**args)
    row = example(dataset)
    assert D(row["features"]["rolling_cvd_btc"]) < 0
    assert row["outcome"]["status"] == "resolved"
    assert len(dataset["feature_units"]) == 30
    assert row["features"].keys() == dataset["feature_units"].keys()
    assert dataset["feature_units"]["rolling_cvd_btc"] == "BTC"
    assert dataset["feature_units"]["bid_absorption_candidate"] == "boolean"


def test_missing_passive_evidence_stays_null_not_false_or_zero():
    row = replace(signal_frame().observation, bid=None, ask=None)
    features = module._features(row)
    assert features["bid_absorption_candidate"] is None
    assert features["ask_replenishment_proxy_btc"] is None
    assert features["bid_replenishment_intervals"] is None


def test_equal_receipt_time_is_never_a_future_entry_or_exit_quote():
    frame = signal_frame()
    now = frame.tick.observed_at_ns
    row = {"feature_available_at_ns": now, "outcome": module._outcome("pending", "wait", None)}
    pending = module._Pending(row, now + MS, D("99"), D("102"))
    assert not pending.advance(frame, fault=None, policy=policy(), gateway=gateway_config())
    assert row["outcome"]["entry_at_ns"] is None
    row["outcome"].update(entry_at_ns=now, entry_price_usdt=D("100"), horizon_at_ns=now)
    assert not pending.advance(frame, fault=None, policy=policy(), gateway=gateway_config())
    assert row["outcome"]["exit_at_ns"] is None


@pytest.mark.parametrize("bad", ["other_session", "duplicate", "bad_observation"])
def test_input_identity_corruption_fails_before_publication(tmp_path, monkeypatch, bad):
    args, _ = setup(tmp_path)
    original = module.CaptureReplay.frames

    def changed(replay):
        for frame in original(replay):
            if bad == "other_session":
                yield replace(frame, tick=replace(frame.tick, source_session="another"))
            elif bad == "duplicate":
                yield frame
                yield frame
            elif frame.observation is not None:
                yield replace(
                    frame, observation=replace(frame.observation, rolling_cvd_base=D("999"))
                )
            else:
                yield frame

    monkeypatch.setattr(module.CaptureReplay, "frames", changed)
    output = tmp_path / "labels.json"
    with pytest.raises(ValueError):
        module.build_registered_event_dataset(**args, output_path=output)
    assert not output.exists() and not output.with_suffix(".json.partial").exists()


@pytest.mark.parametrize("source", ["reserved-one", "unknown"])
def test_reserved_or_unknown_source_refused_before_capture_io(tmp_path, monkeypatch, source):
    args, _ = setup(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("Protected source reached the capture reader.")

    monkeypatch.setattr(module.CaptureReplay, "from_path", forbidden)
    with pytest.raises(ValueError, match="registered research"):
        module.build_registered_event_dataset(**(args | {"source_session": source}))


@pytest.mark.parametrize("budget", [True, 0, -1, 10001, 1.0])
def test_invalid_budget_before_io(tmp_path, monkeypatch, budget):
    args, _ = setup(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid budget attempted IO.")

    monkeypatch.setattr(module, "load_registration", forbidden)
    with pytest.raises(ValueError, match="budget"):
        module.build_registered_event_dataset(**(args | {"max_frames": budget}))


def test_no_extra_frame_is_consumed_past_processing_budget(tmp_path, monkeypatch):
    args, _ = setup(tmp_path)
    original = module.CaptureReplay.frames

    def bounded(replay):
        for i, frame in enumerate(original(replay)):
            if i == 5:
                pytest.fail("Read beyond frame budget.")
            yield frame

    monkeypatch.setattr(module.CaptureReplay, "frames", bounded)
    assert (
        module.build_registered_event_dataset(**(args | {"max_frames": 5}))["frames_processed"] == 5
    )


def test_record_count_is_not_recomputed_by_resplitting_capture_per_frame(tmp_path, monkeypatch):
    args, _ = setup(tmp_path)
    original = module.CaptureReplay.record_count.fget
    reads = 0

    def counted(replay):
        nonlocal reads
        reads += 1
        return original(replay)

    monkeypatch.setattr(module.CaptureReplay, "record_count", property(counted))
    assert module.build_registered_event_dataset(**args)["session_consumed"]
    assert reads == 1


def test_reproducible_dataset_uses_fixed_decimal_context_and_leaves_inputs_unchanged(tmp_path):
    args, _ = setup(tmp_path)
    before = args["capture_path"].read_bytes(), args["registration_path"].read_bytes()
    first = module.build_registered_event_dataset(**args)
    with localcontext() as context:
        context.prec = 7
        assert module.build_registered_event_dataset(**args) == first
    assert before == (args["capture_path"].read_bytes(), args["registration_path"].read_bytes())


def test_checksum_envelope_is_exclusively_published_and_cannot_overwrite(tmp_path):
    args, _ = setup(tmp_path)
    output = tmp_path / "labels.json"
    dataset = module.build_registered_event_dataset(**args, output_path=output)
    envelope = json.loads(output.read_text())
    assert envelope["dataset"] == dataset
    assert envelope["dataset_sha256"] == hashlib.sha256(module._json(dataset).encode()).hexdigest()
    assert not output.with_suffix(".json.partial").exists()
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        module.build_registered_event_dataset(**args, output_path=output)
    assert output.read_bytes() == before


def test_failed_flush_leaves_only_quarantined_staging(tmp_path, monkeypatch):
    args, _ = setup(tmp_path)
    output = tmp_path / "labels.json"

    def failed(*args):
        raise OSError("synthetic fsync failure")

    monkeypatch.setattr(module.os, "fsync", failed)
    with pytest.raises(OSError, match="fsync"):
        module.build_registered_event_dataset(**args, output_path=output)
    assert not output.exists() and output.with_suffix(".json.partial").exists()


def test_existing_partial_is_never_reused_or_overwritten(tmp_path):
    args, _ = setup(tmp_path)
    output = tmp_path / "labels.json"
    partial = output.with_suffix(".json.partial")
    partial.write_bytes(b"quarantined earlier attempt")
    with pytest.raises(FileExistsError):
        module.build_registered_event_dataset(**args, output_path=output)
    assert not output.exists() and partial.read_bytes() == b"quarantined earlier attempt"


def test_publication_race_never_replaces_other_output(tmp_path, monkeypatch):
    args, _ = setup(tmp_path)
    output = tmp_path / "labels.json"
    original = module.os.link

    def racing(source, destination):
        destination.write_bytes(b"other writer")
        original(source, destination)

    monkeypatch.setattr(module.os, "link", racing)
    with pytest.raises(FileExistsError):
        module.build_registered_event_dataset(**args, output_path=output)
    assert output.read_bytes() == b"other writer"
    assert output.with_suffix(".json.partial").exists()


@pytest.mark.parametrize("limit", ["MAX_PENDING", "MAX_ARTIFACT_BYTES"])
def test_resource_limits_fail_without_a_published_artifact(tmp_path, monkeypatch, limit):
    args, _ = setup(tmp_path)
    monkeypatch.setattr(module, limit, 1)
    output = tmp_path / "labels.json"
    with pytest.raises(ValueError, match="budget"):
        module.build_registered_event_dataset(**args, output_path=output)
    assert not output.exists() and not output.with_suffix(".json.partial").exists()


def test_mid_build_source_drift_refuses_publication(tmp_path, monkeypatch):
    args, _ = setup(tmp_path)
    monkeypatch.setattr(module, "_implementation_hash", lambda: "a" * 64)
    output = tmp_path / "labels.json"
    with pytest.raises(ValueError, match="during labeling"):
        module.build_registered_event_dataset(**args, output_path=output)
    assert not output.exists()


@pytest.mark.parametrize("budget,gap,code", [(100, False, 0), (5, False, 2), (100, True, 2)])
def test_cli_status_and_compact_summary(tmp_path, monkeypatch, capsys, budget, gap, code):
    args, _ = setup(tmp_path, rows=rows_with_quote(timestamp=1200, gap=gap))
    output = tmp_path / "labels.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "labels",
            "--registration",
            str(args["registration_path"]),
            "--capture",
            str(args["capture_path"]),
            "--source-session",
            args["source_session"],
            "--max-frames",
            str(budget),
            "--output",
            str(output),
        ],
    )
    if code:
        with pytest.raises(SystemExit) as error:
            module.main()
        assert error.value.code == code
    else:
        module.main()
    summary = json.loads(capsys.readouterr().out)
    assert "examples" not in summary and summary["training_started"] is False
    assert output.exists()
