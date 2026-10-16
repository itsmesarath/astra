"""Tests for combined market-data capture validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ai_trader.ingestion.validate_combined import (
    CaptureValidationError,
    validate_capture,
)


def make_valid_records() -> list[dict[str, object]]:
    """Create a small, internally consistent combined capture."""
    return [
        {
            "schema_version": 1,
            "record_type": "session_start",
            "started_at_ns": 1_000_000_000,
            "symbol": "BTCUSDT",
            "streams": [
                "btcusdt@aggTrade",
                "btcusdt@depth@100ms",
            ],
            "snapshot_limit": 1000,
        },
        {
            "schema_version": 1,
            "record_type": "depth_snapshot",
            "received_at_ns": 1_050_000_000,
            "event": {
                "lastUpdateId": 100,
                "bids": [
                    ["100.00", "2.00"],
                    ["99.00", "1.00"],
                ],
                "asks": [
                    ["101.00", "3.00"],
                    ["102.00", "1.00"],
                ],
            },
        },
        {
            "schema_version": 1,
            "record_type": "stream_event",
            "stream": "btcusdt@depth@100ms",
            "received_at_ns": 1_100_000_000,
            "event": {
                "e": "depthUpdate",
                "E": 1000,
                "s": "BTCUSDT",
                "U": 99,
                "u": 100,
                "b": [],
                "a": [],
            },
        },
        {
            "schema_version": 1,
            "record_type": "stream_event",
            "stream": "btcusdt@aggTrade",
            "received_at_ns": 1_101_000_000,
            "event": {
                "e": "aggTrade",
                "E": 1001,
                "s": "BTCUSDT",
                "a": 10,
                "p": "100.50",
                "q": "0.25",
                "f": 500,
                "l": 500,
                "T": 1001,
                "m": False,
            },
        },
        {
            "schema_version": 1,
            "record_type": "stream_event",
            "stream": "btcusdt@depth@100ms",
            "received_at_ns": 1_102_000_000,
            "event": {
                "e": "depthUpdate",
                "E": 1002,
                "s": "BTCUSDT",
                "U": 101,
                "u": 101,
                "b": [["100.00", "2.50"]],
                "a": [["101.00", "2.50"]],
            },
        },
        {
            "schema_version": 1,
            "record_type": "stream_event",
            "stream": "btcusdt@aggTrade",
            "received_at_ns": 1_103_000_000,
            "event": {
                "e": "aggTrade",
                "E": 1003,
                "s": "BTCUSDT",
                "a": 11,
                "p": "100.50",
                "q": "0.10",
                "f": 501,
                "l": 501,
                "T": 1003,
                "m": True,
            },
        },
        {
            "schema_version": 1,
            "record_type": "session_end",
            "ended_at_ns": 1_200_000_000,
            "trade_events": 2,
            "depth_events": 2,
        },
    ]


def write_capture(
    path: Path,
    records: list[dict[str, object]],
) -> None:
    """Write records using the collector's JSONL format."""
    with path.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record, separators=(",", ":")) + "\n")


def test_validates_complete_combined_session(tmp_path: Path) -> None:
    """A continuous capture should validate and replay successfully."""
    capture_path = tmp_path / "valid.jsonl"
    write_capture(capture_path, make_valid_records())

    report = validate_capture(capture_path)

    assert report.total_records == 7
    assert report.snapshot_update_id == 100
    assert report.trade_events == 2
    assert report.depth_events == 2
    assert report.stale_depth_events == 1
    assert report.applied_depth_events == 1
    assert report.first_trade_id == 10
    assert report.last_trade_id == 11
    assert report.final_book_update_id == 101


def test_rejects_aggregate_trade_id_gap(tmp_path: Path) -> None:
    """A missing aggregate-trade ID should invalidate the capture."""
    records = copy.deepcopy(make_valid_records())
    records[5]["event"]["a"] = 12

    capture_path = tmp_path / "trade_gap.jsonl"
    write_capture(capture_path, records)

    with pytest.raises(
        CaptureValidationError,
        match="breaks aggregate-trade continuity",
    ):
        validate_capture(capture_path)


def test_rejects_depth_update_id_gap(tmp_path: Path) -> None:
    """A missing depth-update ID should invalidate the capture."""
    records = copy.deepcopy(make_valid_records())
    records[4]["event"]["U"] = 102
    records[4]["event"]["u"] = 102

    capture_path = tmp_path / "depth_gap.jsonl"
    write_capture(capture_path, records)

    with pytest.raises(
        CaptureValidationError,
        match="breaks depth continuity",
    ):
        validate_capture(capture_path)


def test_rejects_session_count_mismatch(tmp_path: Path) -> None:
    """Incorrect end-of-session counters should be detected."""
    records = copy.deepcopy(make_valid_records())
    records[6]["trade_events"] = 3

    capture_path = tmp_path / "wrong_count.jsonl"
    write_capture(capture_path, records)

    with pytest.raises(
        CaptureValidationError,
        match="Trade count mismatch",
    ):
        validate_capture(capture_path)
