"""Synthetic receipt-only checks for the unpromoted flow-pressure candidate."""

import hashlib
import json
from dataclasses import replace
from decimal import Decimal

import pytest
from test_microstructure_policy import bind, capture_rows, signal_frame

from ai_trader.research.flow_pressure_trial import (
    FlowPressureConfig,
    assess_flow_pressure,
    evaluate_flow_pressure,
    register_flow_pressure,
)
from ai_trader.trading.capture_replay import CaptureReplayConfig

D = Decimal


def candidate():
    return FlowPressureConfig(
        minimum_cvd_btc=D("1"),
        minimum_ofi_btc=D("1"),
        minimum_book_imbalance=D("0.2"),
        minimum_bid_ask_liquidity_ratio=D("1.5"),
        maximum_spread_bps=D("5"),
        maximum_trade_age_ns=200_000_000,
        maximum_quote_age_ns=200_000_000,
    )


def settings():
    return {
        "trial_id": "synthetic-flow-pressure-v1",
        "sources": [
            {"source_session": "synthetic-s0001", "role": "train"},
            {"source_session": "synthetic-s0002", "role": "validation"},
            {"source_session": "synthetic-s0003", "role": "reserved"},
        ],
        "candidate": {
            "minimum_cvd_btc": "1",
            "minimum_ofi_btc": "1",
            "minimum_book_imbalance": "0.2",
            "minimum_bid_ask_liquidity_ratio": "1.5",
            "maximum_spread_bps": "5",
            "maximum_trade_age_ns": 200_000_000,
            "maximum_quote_age_ns": 200_000_000,
        },
        "replay": {
            "features": {
                "levels": 1,
                "rolling_window_ms": 100,
                "liquidity_band_bps": "10",
                "maximum_evidence_interval_ms": 1000,
                "retained_depth_fraction": "0.8",
                "repeated_intervals": 3,
                "maximum_buffered_trades": 100000,
            },
            "max_event_lag_ns": 2_000_000_000,
            "max_future_skew_ns": 100_000_000,
        },
        "max_total_frames": 100,
    }


def _capture(offset_ms):
    rows = capture_rows()
    for row in rows:
        for key in ("started_at_ns", "requested_at_ns", "received_at_ns", "ended_at_ns"):
            if key in row:
                row[key] += offset_ms * 1_000_000
        if row.get("record_type") == "stream_event":
            row["event"]["E"] += offset_ms
            if "T" in row["event"]:
                row["event"]["T"] += offset_ms
    return b"".join(json.dumps(row).encode() + b"\n" for row in rows)


def _registered(tmp_path, *, spec=None):
    source = tmp_path / "settings.json"
    source.write_text(json.dumps(settings() if spec is None else spec), encoding="utf-8")
    plan = tmp_path / "plan.json"
    result = register_flow_pressure(source, plan)
    return plan, result


def test_flow_pressure_uses_cvd_ofi_liquidity_without_replenishment_gate():
    frame = signal_frame()
    replay = CaptureReplayConfig(features=settings_replay_features())
    result = assess_flow_pressure(frame, candidate=candidate(), replay=replay)
    assert result.qualifies and result.reason == "diagnostic_signal_only"
    assert result.bid_replenishment_observed
    no_bid_evidence = bind(frame, replace(frame.observation, bid=None))
    result = assess_flow_pressure(no_bid_evidence, candidate=candidate(), replay=replay)
    assert result.qualifies and not result.bid_replenishment_observed


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"maximum_trade_age_ns": 1}, "stale_trades"),
        ({"maximum_spread_bps": D("0.1")}, "spread_limit"),
        ({"minimum_cvd_btc": D("3")}, "cvd_below_threshold"),
        ({"minimum_ofi_btc": D("8")}, "ofi_below_threshold"),
        ({"minimum_book_imbalance": D("0.9")}, "book_imbalance_below_threshold"),
        ({"minimum_bid_ask_liquidity_ratio": D("100")}, "bid_liquidity_below_threshold"),
    ],
)
def test_first_veto_reason_is_explicit(change, reason):
    frame = signal_frame()
    result = assess_flow_pressure(
        frame,
        candidate=replace(candidate(), **change),
        replay=CaptureReplayConfig(features=settings_replay_features()),
    )
    assert not result.qualifies and result.reason == reason


def settings_replay_features():
    from ai_trader.features.microstructure import MicrostructureConfig

    return MicrostructureConfig(levels=1, rolling_window_ms=100)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"minimum_cvd_btc": D("0")}, "sign"),
        ({"minimum_ofi_btc": D("NaN")}, "finite"),
        ({"minimum_book_imbalance": D("1")}, "below one"),
        ({"minimum_bid_ask_liquidity_ratio": D("0.9")}, "ratio"),
        ({"maximum_spread_bps": D("10000")}, "spread"),
        ({"maximum_quote_age_ns": 0}, "positive"),
    ],
)
def test_invalid_candidate_refused(change, message):
    with pytest.raises(ValueError, match=message):
        replace(candidate(), **change)


def test_register_and_evaluate_complete_research_inventory(tmp_path):
    plan, registered = _registered(tmp_path)
    first, second = tmp_path / "first.jsonl", tmp_path / "second.jsonl"
    after_plan_ms = json.loads(plan.read_text())["plan"]["registered_at_ns"] // 1_000_000
    first.write_bytes(_capture(after_plan_ms))
    second.write_bytes(_capture(after_plan_ms + 1000))
    sources = (
        ("synthetic-s0001", first, hashlib.sha256(first.read_bytes()).hexdigest()),
        ("synthetic-s0002", second, hashlib.sha256(second.read_bytes()).hexdigest()),
    )
    output = tmp_path / "report.json"
    summary = evaluate_flow_pressure(plan, sources, output)
    assert not plan.with_name(plan.name + ".partial").exists()
    assert not output.with_name(output.name + ".partial").exists()
    report = json.loads(output.read_text())["report"]
    assert summary["status"] == "complete"
    assert (
        summary["report_sha256"]
        == hashlib.sha256(
            (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
        ).hexdigest()
    )
    assert registered["source_count"] == 3
    assert report["reserved_sources_opened"] == 0
    assert report["reserved_source_sessions"] == ["synthetic-s0003"]
    assert [row["role"] for row in report["sources"]] == ["train", "validation"]
    assert report["orders"] == report["training_steps"] == 0
    assert report["verified_capture_bytes"] == first.stat().st_size + second.stat().st_size
    assert report["total_frames"] == sum(row["frames"] for row in report["sources"])
    with pytest.raises(FileExistsError):
        evaluate_flow_pressure(plan, sources, output)


def test_existing_staging_file_is_never_overwritten(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings()), encoding="utf-8")
    plan_path = tmp_path / "plan.json"
    staging = tmp_path / "plan.json.partial"
    staging.write_bytes(b"uncertain prior write")
    with pytest.raises(FileExistsError):
        register_flow_pressure(settings_path, plan_path)
    assert staging.read_bytes() == b"uncertain prior write"
    assert not plan_path.exists()


def test_reserved_or_missing_source_refused_before_capture_io(tmp_path):
    plan, _ = _registered(tmp_path)
    missing = tmp_path / "must-never-open.jsonl"
    with pytest.raises(ValueError, match="every train/validation"):
        evaluate_flow_pressure(
            plan,
            (("synthetic-s0003", missing, "a" * 64),),
            tmp_path / "result.json",
        )
    assert not missing.exists()
    assert not (tmp_path / "result.json").exists()


def test_old_capture_and_budget_failure_do_not_publish_subset(tmp_path):
    plan, _ = _registered(tmp_path)
    first, second = tmp_path / "first.jsonl", tmp_path / "second.jsonl"
    first.write_bytes(_capture(0))
    second.write_bytes(_capture(1000))
    sources = (
        ("synthetic-s0001", first, hashlib.sha256(first.read_bytes()).hexdigest()),
        ("synthetic-s0002", second, hashlib.sha256(second.read_bytes()).hexdigest()),
    )
    output = tmp_path / "report.json"
    with pytest.raises(ValueError, match="predates"):
        evaluate_flow_pressure(plan, sources, output)
    assert not output.exists()
    spec = settings()
    spec["max_total_frames"] = 1
    other = tmp_path / "other"
    other.mkdir()
    second_plan, _ = _registered(other, spec=spec)
    after_plan_ms = json.loads(second_plan.read_text())["plan"]["registered_at_ns"] // 1_000_000
    first.write_bytes(_capture(after_plan_ms))
    second.write_bytes(_capture(after_plan_ms + 1000))
    sources = (
        ("synthetic-s0001", first, hashlib.sha256(first.read_bytes()).hexdigest()),
        ("synthetic-s0002", second, hashlib.sha256(second.read_bytes()).hexdigest()),
    )
    with pytest.raises(ValueError, match="frame budget"):
        evaluate_flow_pressure(second_plan, sources, output)
    assert not output.exists()


def test_role_mutation_and_plan_tampering_fail(tmp_path):
    spec = settings()
    spec["sources"][1]["role"] = "train"
    spec["sources"][0]["role"] = "validation"
    with pytest.raises(ValueError, match="chronological"):
        _registered(tmp_path, spec=spec)
    plan, _ = _registered(tmp_path, spec=settings())
    envelope = json.loads(plan.read_text())
    envelope["plan"]["candidate"]["minimum_cvd_btc"] = "0.1"
    plan.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        evaluate_flow_pressure(plan, (), tmp_path / "result.json")
