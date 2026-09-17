"""Tests for raw aggregate-trade capture validation."""

import json
from pathlib import Path

from ai_trader.ingestion.validate_agg_trades import validate_capture


def make_record(aggregate_id: int, trade_time_ms: int) -> dict[str, object]:
    """Create a minimal valid raw-capture record."""
    return {
        "schema_version": 1,
        "source": "binance_spot",
        "stream": "btcusdt@aggTrade",
        "received_at_ns": trade_time_ms * 1_000_000,
        "event": {
            "e": "aggTrade",
            "E": trade_time_ms,
            "s": "BTCUSDT",
            "a": aggregate_id,
            "p": "76500.32",
            "q": "0.01",
            "f": aggregate_id,
            "l": aggregate_id,
            "T": trade_time_ms,
            "m": False,
            "M": True,
        },
    }


def write_capture(
    path: Path,
    records: list[dict[str, object]],
) -> None:
    """Write test records using the collector's JSONL format."""
    with path.open("w", encoding="utf-8", newline="\n") as output_file:
        for record in records:
            output_file.write(json.dumps(record) + "\n")


def test_accepts_continuous_capture(tmp_path: Path) -> None:
    """Consecutive IDs and timestamps should pass validation."""
    path = tmp_path / "valid.jsonl"
    write_capture(
        path,
        [
            make_record(10, 1000),
            make_record(11, 1001),
            make_record(12, 1002),
        ],
    )

    summary = validate_capture(path)

    assert summary.is_valid
    assert summary.valid_records == 3
    assert summary.first_id == 10
    assert summary.last_id == 12
    assert summary.missing_ids == 0


def test_detects_sequence_problems(tmp_path: Path) -> None:
    """Gaps, duplicates, ordering errors, and time reversal must be counted."""
    path = tmp_path / "invalid.jsonl"
    write_capture(
        path,
        [
            make_record(10, 1000),
            make_record(12, 1001),
            make_record(12, 1000),
            make_record(11, 1002),
        ],
    )

    summary = validate_capture(path)

    assert not summary.is_valid
    assert summary.missing_ids == 1
    assert summary.duplicate_ids == 1
    assert summary.out_of_order_ids == 1
    assert summary.timestamp_reversals == 1


def test_detects_malformed_envelope(tmp_path: Path) -> None:
    """Unexpected source metadata must invalidate the record."""
    path = tmp_path / "malformed.jsonl"
    record = make_record(10, 1000)
    record["source"] = "unknown"
    write_capture(path, [record])

    summary = validate_capture(path)

    assert not summary.is_valid
    assert summary.total_records == 1
    assert summary.valid_records == 0
    assert summary.malformed_records == 1
