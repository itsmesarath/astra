"""Tests for synchronized feature-dataset generation."""

from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path

import pytest

from ai_trader.features.build_dataset import (
    CSV_COLUMNS,
    build_feature_dataset,
)


def make_capture_records() -> list[dict[str, object]]:
    """Create a valid capture with two synchronized feature rows."""
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
            "requested_at_ns": 1_010_000_000,
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
                "q": "0.50",
                "f": 500,
                "l": 501,
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
                "b": [["100.00", "3.00"]],
                "a": [["101.00", "2.00"]],
            },
        },
        {
            "schema_version": 1,
            "record_type": "stream_event",
            "stream": "btcusdt@depth@100ms",
            "received_at_ns": 1_103_000_000,
            "event": {
                "e": "depthUpdate",
                "E": 1003,
                "s": "BTCUSDT",
                "U": 102,
                "u": 102,
                "b": [["99.00", "2.00"]],
                "a": [],
            },
        },
        {
            "schema_version": 1,
            "record_type": "session_end",
            "ended_at_ns": 1_200_000_000,
            "trade_events": 1,
            "depth_events": 3,
        },
    ]


def write_capture(
    path: Path,
    records: list[dict[str, object]],
) -> None:
    """Write a capture using compact JSONL records."""
    with path.open("w", encoding="utf-8", newline="\n") as output_file:
        for record in records:
            output_file.write(json.dumps(record, separators=(",", ":")) + "\n")


def read_feature_rows(path: Path) -> list[dict[str, str]]:
    """Read all generated feature rows."""
    with path.open(encoding="utf-8", newline="") as input_file:
        return list(csv.DictReader(input_file))


def test_builds_causal_synchronized_feature_rows(
    tmp_path: Path,
) -> None:
    """Trades should appear only in the next synchronized book row."""
    capture_path = tmp_path / "capture.jsonl"
    output_path = tmp_path / "features.csv"
    write_capture(capture_path, make_capture_records())

    row_count = build_feature_dataset(
        capture_path,
        output_path,
        levels=2,
    )
    rows = read_feature_rows(output_path)

    assert row_count == 2
    assert len(rows) == 2
    assert list(rows[0]) == list(CSV_COLUMNS)

    first_row = rows[0]
    assert first_row["schema_version"] == "1"
    assert first_row["symbol"] == "BTCUSDT"
    assert first_row["update_id"] == "101"
    assert first_row["levels"] == "2"
    assert Decimal(first_row["midpoint"]) == Decimal("100.5")
    assert Decimal(first_row["microprice"]) == Decimal("100.6")
    assert Decimal(first_row["bid_depth"]) == Decimal("4")
    assert Decimal(first_row["ask_depth"]) == Decimal("3")
    assert Decimal(first_row["book_imbalance"]) == (Decimal("1") / Decimal("7"))
    assert first_row["aggregate_trade_count"] == "1"
    assert first_row["underlying_trade_count"] == "2"
    assert Decimal(first_row["buy_base_volume"]) == Decimal("0.50")
    assert Decimal(first_row["sell_base_volume"]) == Decimal("0")
    assert Decimal(first_row["buy_quote_volume"]) == Decimal("50.2500")
    assert Decimal(first_row["trade_imbalance"]) == Decimal("1")

    second_row = rows[1]
    assert second_row["update_id"] == "102"
    assert Decimal(second_row["bid_depth"]) == Decimal("5")
    assert Decimal(second_row["ask_depth"]) == Decimal("3")
    assert second_row["aggregate_trade_count"] == "0"
    assert second_row["underlying_trade_count"] == "0"
    assert Decimal(second_row["total_base_volume"]) == Decimal("0")
    assert Decimal(second_row["total_quote_volume"]) == Decimal("0")
    assert Decimal(second_row["trade_imbalance"]) == Decimal("0")


def test_rejects_nonpositive_feature_depth(tmp_path: Path) -> None:
    """Feature generation must reject invalid depth configuration."""
    with pytest.raises(
        ValueError,
        match="Feature depth must be greater than zero",
    ):
        build_feature_dataset(
            tmp_path / "missing.jsonl",
            tmp_path / "features.csv",
            levels=0,
        )
