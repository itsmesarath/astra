"""Validate a raw BTCUSDT aggregate-trade JSONL capture."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from ai_trader.ingestion.agg_trade import AggTrade

DEFAULT_DATA_DIRECTORY = Path("data/raw")
FILE_PATTERN = "btcusdt_aggtrade_*.jsonl"


@dataclass(slots=True)
class ValidationSummary:
    """Counters produced while validating one capture."""

    total_records: int = 0
    valid_records: int = 0
    malformed_records: int = 0
    missing_ids: int = 0
    duplicate_ids: int = 0
    out_of_order_ids: int = 0
    timestamp_reversals: int = 0
    first_id: int | None = None
    last_id: int | None = None

    @property
    def is_valid(self) -> bool:
        """Return whether the capture passed every integrity check."""
        return (
            self.total_records > 0
            and self.malformed_records == 0
            and self.missing_ids == 0
            and self.duplicate_ids == 0
            and self.out_of_order_ids == 0
            and self.timestamp_reversals == 0
        )


def find_latest_capture() -> Path:
    """Return the most recently modified aggregate-trade capture."""
    captures = list(DEFAULT_DATA_DIRECTORY.glob(FILE_PATTERN))
    if not captures:
        raise FileNotFoundError("No aggregate-trade captures were found.")
    return max(captures, key=lambda path: path.stat().st_mtime)


def validate_capture(path: Path) -> ValidationSummary:
    """Stream through a capture and calculate integrity statistics."""
    summary = ValidationSummary()
    previous_id: int | None = None
    previous_trade_time_ms: int | None = None

    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            summary.total_records += 1

            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise TypeError("Record must be a JSON object.")
                if record.get("schema_version") != 1:
                    raise ValueError("Unsupported schema version.")
                if record.get("source") != "binance_spot":
                    raise ValueError("Unexpected source.")
                if record.get("stream") != "btcusdt@aggTrade":
                    raise ValueError("Unexpected stream.")

                event = record.get("event")
                if not isinstance(event, dict):
                    raise TypeError("Event must be a JSON object.")

                trade = AggTrade.from_event(event)
            except (KeyError, TypeError, ValueError) as error:
                summary.malformed_records += 1
                print(f"Line {line_number}: {error}")
                continue

            summary.valid_records += 1

            if summary.first_id is None:
                summary.first_id = trade.aggregate_trade_id
            summary.last_id = trade.aggregate_trade_id

            if previous_id is not None:
                id_difference = trade.aggregate_trade_id - previous_id

                if id_difference == 0:
                    summary.duplicate_ids += 1
                elif id_difference < 0:
                    summary.out_of_order_ids += 1
                elif id_difference > 1:
                    summary.missing_ids += id_difference - 1

            if previous_trade_time_ms is not None and trade.trade_time_ms < previous_trade_time_ms:
                summary.timestamp_reversals += 1

            previous_id = trade.aggregate_trade_id
            previous_trade_time_ms = trade.trade_time_ms

    return summary


def print_summary(path: Path, summary: ValidationSummary) -> None:
    """Display a human-readable validation report."""
    print(f"File: {path.resolve()}")
    print(f"Total records: {summary.total_records}")
    print(f"Valid records: {summary.valid_records}")
    print(f"Malformed records: {summary.malformed_records}")
    print(f"First aggregate ID: {summary.first_id}")
    print(f"Last aggregate ID: {summary.last_id}")
    print(f"Missing aggregate IDs: {summary.missing_ids}")
    print(f"Duplicate aggregate IDs: {summary.duplicate_ids}")
    print(f"Out-of-order aggregate IDs: {summary.out_of_order_ids}")
    print(f"Trade-time reversals: {summary.timestamp_reversals}")
    print("Result: VALID" if summary.is_valid else "Result: INVALID")


def main() -> None:
    """Validate a selected capture, or the newest capture by default."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="JSONL capture to validate; defaults to the newest capture.",
    )
    args = parser.parse_args()

    path = args.path or find_latest_capture()
    summary = validate_capture(path)
    print_summary(path, summary)

    if not summary.is_valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
