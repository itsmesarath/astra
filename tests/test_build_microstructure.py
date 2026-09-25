"""Synthetic capture integration and safe artifact publication."""

import hashlib
import json
from pathlib import Path

import pytest

from ai_trader.features import build_microstructure as module
from ai_trader.features.microstructure import MicrostructureConfig


def capture_records():
    return [
        {
            "record_type": "session_start",
            "started_at_ns": 900000000,
            "symbol": "BTCUSDT",
            "streams": ["btcusdt@aggTrade", "btcusdt@depth@100ms"],
        },
        {
            "record_type": "depth_snapshot",
            "requested_at_ns": 910000000,
            "received_at_ns": 950000000,
            "event": {
                "lastUpdateId": 100,
                "bids": [["100", "2"], ["99", "3"]],
                "asks": [["101", "3"], ["102", "4"]],
            },
        },
        {
            "record_type": "stream_event",
            "stream": "btcusdt@depth@100ms",
            "received_at_ns": 1000000000,
            "event": {
                "e": "depthUpdate",
                "s": "BTCUSDT",
                "E": 1000,
                "U": 101,
                "u": 101,
                "b": [],
                "a": [],
            },
        },
        {
            "record_type": "stream_event",
            "stream": "btcusdt@aggTrade",
            "received_at_ns": 1050000000,
            "event": {
                "e": "aggTrade",
                "s": "BTCUSDT",
                "E": 1050,
                "T": 1050,
                "a": 1,
                "p": "101",
                "q": "3",
                "m": False,
                "f": 1,
                "l": 1,
            },
        },
        {
            "record_type": "stream_event",
            "stream": "btcusdt@depth@100ms",
            "received_at_ns": 1100000000,
            "event": {
                "e": "depthUpdate",
                "s": "BTCUSDT",
                "E": 1100,
                "U": 102,
                "u": 102,
                "b": [],
                "a": [],
            },
        },
        {"record_type": "session_end", "trade_events": 1, "depth_events": 2},
    ]


def source(tmp_path, records=None):
    path = tmp_path / "capture.jsonl"
    path.write_text(
        "".join(
            json.dumps({"schema_version": 1, **r}) + "\n" for r in (records or capture_records())
        ),
        encoding="utf-8",
    )
    return path


def build(path, output):
    return module.build_microstructure_dataset(
        path, output, source_session="synthetic-one", config=MicrostructureConfig(levels=1)
    )


def test_builds_versioned_cvd_and_absorption_artifact(tmp_path):
    path = source(tmp_path)
    output = tmp_path / "features.jsonl"
    assert build(path, output) == 2
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(records) == 4
    assert records[0]["source_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert records[0]["feature_schema"] == "receipt_causal_microstructure_v1"
    assert records[1]["ask"] is None
    assert records[2]["session_cvd_base"] == "3"
    assert records[2]["ask"]["absorption_candidate"] is True
    assert records[2]["source_session"] == "synthetic-one"
    assert records[-1]["status"] == "complete"
    assert records[-1]["observation_count"] == 2
    assert not list(tmp_path.glob(".microstructure-*.tmp"))


def test_existing_destination_is_not_overwritten(tmp_path):
    path = source(tmp_path)
    output = tmp_path / "features.jsonl"
    output.write_text("keep me", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build(path, output)
    assert output.read_text() == "keep me"


def test_failure_during_engine_processing_never_publishes_partial_artifact(tmp_path):
    records = capture_records()
    records[4]["event"]["E"] = 900
    path = source(tmp_path, records)
    output = tmp_path / "features.jsonl"
    with pytest.raises(ValueError, match="backwards"):
        build(path, output)
    assert not output.exists()
    assert not list(tmp_path.glob(".microstructure-*.tmp"))


def test_source_change_during_validation_fails_before_output(tmp_path, monkeypatch):
    path = source(tmp_path)
    output = tmp_path / "features.jsonl"
    original = module.validate_capture

    def changed(path):
        report = original(path)
        path.write_text(path.read_text() + "\n", encoding="utf-8")
        return report

    monkeypatch.setattr(module, "validate_capture", changed)
    with pytest.raises(ValueError, match="changed during validation"):
        build(path, output)
    assert not output.exists()


def test_racing_output_is_preserved_and_temporary_cleaned(tmp_path, monkeypatch):
    path = source(tmp_path)
    output = tmp_path / "features.jsonl"
    original = module.os.link

    def raced(src, destination):
        Path(destination).write_text("another writer", encoding="utf-8")
        original(src, destination)

    monkeypatch.setattr(module.os, "link", raced)
    with pytest.raises(FileExistsError):
        build(path, output)
    assert output.read_text() == "another writer"
    assert not list(tmp_path.glob(".microstructure-*.tmp"))


def test_appending_future_events_does_not_change_past_observations(tmp_path):
    records = capture_records()
    path = source(tmp_path, records)
    first = tmp_path / "first.jsonl"
    build(path, first)
    earlier = [json.loads(line) for line in first.read_text().splitlines()][1:3]
    records.insert(
        -1,
        {
            "record_type": "stream_event",
            "stream": "btcusdt@depth@100ms",
            "received_at_ns": 1200000000,
            "event": {
                "e": "depthUpdate",
                "s": "BTCUSDT",
                "E": 1200,
                "U": 103,
                "u": 103,
                "b": [["100", "8"]],
                "a": [],
            },
        },
    )
    records[-1]["depth_events"] = 3
    source(tmp_path, records)
    second = tmp_path / "second.jsonl"
    build(path, second)
    assert [json.loads(line) for line in second.read_text().splitlines()][1:3] == earlier


def test_source_change_during_generation_does_not_publish(tmp_path, monkeypatch):
    path = source(tmp_path)
    output = tmp_path / "features.jsonl"
    original = module.MicrostructureEngine.apply_depth
    changed = False

    def mutate(subject, update, **kwargs):
        nonlocal changed
        row = original(subject, update, **kwargs)
        if not changed:
            path.write_text(path.read_text() + "\n", encoding="utf-8")
            changed = True
        return row

    monkeypatch.setattr(module.MicrostructureEngine, "apply_depth", mutate)
    with pytest.raises(ValueError, match="changed during feature generation"):
        build(path, output)
    assert not output.exists()
    assert not list(tmp_path.glob(".microstructure-*.tmp"))
