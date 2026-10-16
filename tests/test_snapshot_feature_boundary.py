"""Independent replay oracle for the standalone feature export's snapshot boundary."""

import copy
import hashlib
import json
from dataclasses import asdict

import pytest
from test_build_microstructure import source
from test_capture_replay import records

from ai_trader.features import build_microstructure as builder
from ai_trader.features.microstructure import MicrostructureConfig
from ai_trader.research import capture_quality as quality
from ai_trader.trading.capture_replay import CaptureReplay, CaptureReplayConfig

MS = 1_000_000
CONFIG = MicrostructureConfig(levels=1, rolling_window_ms=100)


def buffered_records(available=1050 * MS):
    rows = records()
    rows[1]["received_at_ns"] = available
    rows[2]["event"]["b"] = [["100", "9"]]  # Book bridge must survive buffering.
    later_trade = copy.deepcopy(rows[3])
    later_trade["received_at_ns"] = 1150 * MS
    later_trade["event"].update(a=2, E=1150, T=1150, f=2, l=2, q="2")
    later_depth = copy.deepcopy(rows[4])
    later_depth["received_at_ns"] = 1200 * MS
    later_depth["event"].update(U=103, u=103, E=1200)
    rows[-1:-1] = [later_trade, later_depth]
    rows[-1].update(trade_events=2, depth_events=3, ended_at_ns=1300 * MS)
    return rows


def generate(tmp_path, rows):
    capture = source(tmp_path, rows)
    output = tmp_path / "features.jsonl"
    builder.build_microstructure_dataset(
        capture, output, source_session="boundary-test", config=CONFIG
    )
    decoded = [json.loads(line) for line in output.read_text().splitlines()]
    return capture, output, decoded


@pytest.mark.parametrize(
    "available",
    [999 * MS, 1000 * MS, 1025 * MS, 1050 * MS, 1050 * MS + 1, 1100 * MS, 1150 * MS, 1150 * MS + 1],
)
def test_all_exported_rows_equal_independent_paper_replay(tmp_path, available):
    rows = buffered_records(available)
    capture, output, decoded = generate(tmp_path, rows)
    replay = CaptureReplay.from_path(
        capture,
        expected_sha256=hashlib.sha256(capture.read_bytes()).hexdigest(),
        source_session="boundary-test",
        config=CaptureReplayConfig(features=CONFIG),
    )
    expected = [
        {"record_type": "observation", **asdict(frame.observation)}
        for frame in replay.frames()
        if frame.observation is not None
    ]
    assert quality._canonical(decoded[1:-1]) == quality._canonical(expected)
    assert all(row["received_at_ns"] > available for row in decoded[1:-1])
    assert decoded[0]["schema_version"] == 2
    assert decoded[0]["snapshot_received_at_ns"] == available
    assert decoded[0]["snapshot_policy"] == builder.SNAPSHOT_POLICY
    report = quality.assess_capture(capture, output)
    assert report.schema == "capture_quality_v2"
    assert report.snapshot_received_at_ns == available
    assert report.observations + report.snapshot_buffered_depth_updates == 3
    assert report.snapshot_buffered_trade_events == sum(
        row.get("stream") == "btcusdt@aggTrade" and row["received_at_ns"] <= available
        for row in rows[2:-1]
    )
    assert report.first_observation_received_at_ns > available


def test_buffered_and_equal_time_trades_do_not_seed_cvd_warmup_or_absorption(tmp_path):
    capture, output, decoded = generate(tmp_path, buffered_records())
    first, second = decoded[1:-1]
    assert first["received_at_ns"] == 1100 * MS
    assert first["book"]["bid_depth"] == "9"  # Top-one depth retains the buffered update.
    assert first["session_cvd_base"] == "0"
    assert first["rolling_trade_count"] == 0
    assert not first["rolling_window_complete"]
    assert first["ask"] is None and not first["evidence_interval_valid"]
    assert second["session_cvd_base"] == "2"
    assert second["rolling_trade_count"] == 1
    assert second["rolling_window_complete"]
    report = quality.assess_capture(capture, output)
    assert report.snapshot_buffered_depth_updates == 1
    assert report.snapshot_buffered_trade_events == 1
    assert report.trade_events == 2  # Total feed count is not post-snapshot CVD count.


def test_changing_excluded_trade_size_cannot_change_later_features(tmp_path):
    rows = buffered_records()
    capture, output, decoded = generate(tmp_path, rows)
    rows[3]["event"]["q"] = "999999"
    source(tmp_path, rows)
    second = tmp_path / "second.jsonl"
    builder.build_microstructure_dataset(
        capture, second, source_session="boundary-test", config=CONFIG
    )
    rebuilt = [json.loads(line) for line in second.read_text().splitlines()]
    assert decoded[1:-1] == rebuilt[1:-1]
    assert output.exists()  # Original artifact is retained, not overwritten.


@pytest.mark.parametrize(
    "index,field", [(0, "started_at_ns"), (1, "requested_at_ns"), (1, "received_at_ns")]
)
@pytest.mark.parametrize("value", [None, True, -1, 950000000.0])
def test_missing_or_untyped_availability_cannot_be_guessed(tmp_path, index, field, value):
    rows = buffered_records()
    if value is None:
        del rows[index][field]
    else:
        rows[index][field] = value
    capture = source(tmp_path, rows)
    output = tmp_path / "must-not-exist.jsonl"
    with pytest.raises(ValueError, match="availability"):
        builder.build_microstructure_dataset(
            capture, output, source_session="boundary-test", config=CONFIG
        )
    assert not output.exists()
    assert not list(tmp_path.glob(".microstructure-*.tmp"))


@pytest.mark.parametrize("requested,available", [(899 * MS, 1050 * MS), (1051 * MS, 1050 * MS)])
def test_out_of_order_availability_refused(tmp_path, requested, available):
    rows = buffered_records(available)
    rows[1]["requested_at_ns"] = requested
    with pytest.raises(ValueError, match="out of order"):
        generate(tmp_path, rows)
    assert not (tmp_path / "features.jsonl").exists()


def test_no_post_snapshot_depth_means_no_published_artifact(tmp_path):
    with pytest.raises(ValueError, match="no microstructure observations"):
        generate(tmp_path, buffered_records(1250 * MS))
    assert not (tmp_path / "features.jsonl").exists()


@pytest.mark.parametrize(
    "field,value",
    [("schema_version", 1), ("snapshot_policy", "legacy"), ("snapshot_received_at_ns", 0)],
)
def test_quality_rejects_legacy_or_falsified_snapshot_contract(tmp_path, field, value):
    capture, output, decoded = generate(tmp_path, buffered_records())
    decoded[0][field] = value
    output.write_text("".join(json.dumps(row) + "\n" for row in decoded))
    with pytest.raises(ValueError):
        quality.assess_capture(capture, output)


def test_quality_rejects_feature_claimed_at_snapshot_time(tmp_path):
    capture, output, decoded = generate(tmp_path, buffered_records())
    decoded[1]["received_at_ns"] = decoded[0]["snapshot_received_at_ns"]
    output.write_text("".join(json.dumps(row) + "\n" for row in decoded))
    with pytest.raises(ValueError, match="does not reproduce"):
        quality.assess_capture(capture, output)


@pytest.mark.parametrize(
    "change",
    [
        lambda rows: rows[3]["event"].update(T=-1),
        lambda rows: rows[3]["event"].update(q="Infinity"),
        lambda rows: rows[2]["event"].update(E=-1),
        lambda rows: rows[2]["event"].update(b=[["100", "9"], ["100", "8"]]),
        lambda rows: rows[5]["event"].update(T=1000),
    ],
)
def test_ignored_buffer_does_not_bypass_full_stream_validation(tmp_path, change):
    rows = buffered_records()
    change(rows)
    with pytest.raises(ValueError):
        generate(tmp_path, rows)
    assert not (tmp_path / "features.jsonl").exists()
    assert not list(tmp_path.glob(".microstructure-*.tmp"))
