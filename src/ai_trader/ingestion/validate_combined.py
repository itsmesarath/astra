"""Validate and replay a combined BTCUSDT raw-data session."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ai_trader.ingestion.agg_trade import AggTrade
from ai_trader.orderbook.depth_update import DepthUpdate
from ai_trader.orderbook.local_book import LocalOrderBook, SequenceGapError

SYMBOL = "BTCUSDT"
TRADE_STREAM = "btcusdt@aggTrade"
DEPTH_STREAM = "btcusdt@depth@100ms"
DEFAULT_DATA_DIRECTORY = Path("data/raw")
FILE_PATTERN = "btcusdt_combined_*.jsonl"


class CaptureValidationError(ValueError):
    """Raised when a combined capture violates its storage contract."""


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Summary of one successfully validated capture."""

    total_records: int
    snapshot_update_id: int
    trade_events: int
    depth_events: int
    stale_depth_events: int
    applied_depth_events: int
    first_trade_id: int | None
    last_trade_id: int | None
    final_book_update_id: int
    best_bid: Decimal
    best_ask: Decimal
    spread: Decimal
    minimum_delay_ms: float
    average_delay_ms: float
    maximum_delay_ms: float


def require(condition: bool, message: str) -> None:
    """Raise a clear validation error when a condition is false."""
    if not condition:
        raise CaptureValidationError(message)


def read_record(line: str, line_number: int) -> dict[str, object]:
    """Decode and validate one common JSONL record envelope."""
    try:
        record = json.loads(line)
    except json.JSONDecodeError as error:
        raise CaptureValidationError(f"Line {line_number} is not valid JSON.") from error

    if not isinstance(record, dict):
        raise CaptureValidationError(f"Line {line_number} must contain a JSON object.")

    require(
        record.get("schema_version") == 1,
        f"Line {line_number} has an unsupported schema version.",
    )
    return record


def find_latest_capture() -> Path:
    """Return the most recently modified combined capture."""
    captures = list(DEFAULT_DATA_DIRECTORY.glob(FILE_PATTERN))
    if not captures:
        raise FileNotFoundError("No combined captures were found.")

    return max(captures, key=lambda path: path.stat().st_mtime)


def validate_capture(path: Path) -> ValidationReport:
    """Stream, validate, and replay one combined capture."""
    trade_count = 0
    depth_count = 0
    stale_depth_count = 0
    applied_depth_count = 0

    previous_trade_id: int | None = None
    first_trade_id: int | None = None
    last_trade_id: int | None = None
    previous_depth_final_id: int | None = None
    previous_received_at_ns: int | None = None

    minimum_delay_ms = float("inf")
    maximum_delay_ms = float("-inf")
    delay_sum_ms = 0.0
    delay_count = 0

    with path.open(encoding="utf-8") as input_file:
        start_line = next(input_file, None)
        require(start_line is not None, "Capture is empty.")
        start_record = read_record(start_line, 1)

        require(
            start_record.get("record_type") == "session_start",
            "Line 1 must be a session_start record.",
        )
        require(
            start_record.get("symbol") == SYMBOL,
            f"Session symbol must be {SYMBOL}.",
        )
        require(
            start_record.get("streams") == [TRADE_STREAM, DEPTH_STREAM],
            "Session stream list is incorrect.",
        )

        snapshot_line = next(input_file, None)
        require(
            snapshot_line is not None,
            "Capture does not contain a depth snapshot.",
        )
        snapshot_record = read_record(snapshot_line, 2)

        require(
            snapshot_record.get("record_type") == "depth_snapshot",
            "Line 2 must be a depth_snapshot record.",
        )

        snapshot_event = snapshot_record.get("event")
        require(
            isinstance(snapshot_event, dict),
            "Depth snapshot event must be a JSON object.",
        )

        book = LocalOrderBook.from_snapshot(
            SYMBOL,
            snapshot_event,
        )
        snapshot_update_id = book.update_id

        end_record: dict[str, object] | None = None
        end_line_number = 0

        for line_number, line in enumerate(input_file, start=3):
            record = read_record(line, line_number)
            record_type = record.get("record_type")

            if record_type == "session_end":
                end_record = record
                end_line_number = line_number

                require(
                    next(input_file, None) is None,
                    "Records appear after session_end.",
                )
                break

            require(
                record_type == "stream_event",
                f"Line {line_number} has unexpected record type {record_type!r}.",
            )

            received_at_ns = record.get("received_at_ns")
            require(
                isinstance(received_at_ns, int),
                f"Line {line_number} has invalid receipt time.",
            )

            if previous_received_at_ns is not None:
                require(
                    received_at_ns >= previous_received_at_ns,
                    f"Line {line_number} reverses local receipt time.",
                )
            previous_received_at_ns = received_at_ns

            stream_name = record.get("stream")
            event = record.get("event")
            require(
                isinstance(event, dict),
                f"Line {line_number} event must be a JSON object.",
            )

            if stream_name == TRADE_STREAM:
                trade = AggTrade.from_event(event)
                trade_count += 1

                if first_trade_id is None:
                    first_trade_id = trade.aggregate_trade_id

                if previous_trade_id is not None:
                    require(
                        trade.aggregate_trade_id == previous_trade_id + 1,
                        f"Line {line_number} breaks aggregate-trade "
                        f"continuity after ID {previous_trade_id}.",
                    )

                previous_trade_id = trade.aggregate_trade_id
                last_trade_id = trade.aggregate_trade_id
                event_time_ms = trade.event_time_ms

            elif stream_name == DEPTH_STREAM:
                update = DepthUpdate.from_event(event)
                depth_count += 1

                if previous_depth_final_id is not None:
                    require(
                        update.first_update_id == previous_depth_final_id + 1,
                        f"Line {line_number} breaks depth continuity "
                        f"after ID {previous_depth_final_id}.",
                    )

                previous_depth_final_id = update.final_update_id
                event_time_ms = update.event_time_ms

                try:
                    applied = book.apply(update)
                except SequenceGapError as error:
                    raise CaptureValidationError(
                        f"Line {line_number} cannot be applied: {error}"
                    ) from error

                if applied:
                    applied_depth_count += 1
                else:
                    stale_depth_count += 1

            else:
                raise CaptureValidationError(
                    f"Line {line_number} has unexpected stream {stream_name!r}."
                )

            delay_ms = received_at_ns / 1_000_000 - event_time_ms
            minimum_delay_ms = min(minimum_delay_ms, delay_ms)
            maximum_delay_ms = max(maximum_delay_ms, delay_ms)
            delay_sum_ms += delay_ms
            delay_count += 1
        else:
            raise CaptureValidationError("Capture does not contain a session_end record.")

    require(end_record is not None, "Session end record is missing.")
    require(trade_count == end_record.get("trade_events"), "Trade count mismatch.")
    require(depth_count == end_record.get("depth_events"), "Depth count mismatch.")
    require(depth_count > 0, "Capture contains no depth events.")
    require(applied_depth_count > 0, "No depth event bridged the snapshot.")
    require(delay_count > 0, "Capture contains no stream events.")

    expected_total_records = trade_count + depth_count + 3
    require(
        end_line_number == expected_total_records,
        "Total record count does not match the session structure.",
    )

    return ValidationReport(
        total_records=end_line_number,
        snapshot_update_id=snapshot_update_id,
        trade_events=trade_count,
        depth_events=depth_count,
        stale_depth_events=stale_depth_count,
        applied_depth_events=applied_depth_count,
        first_trade_id=first_trade_id,
        last_trade_id=last_trade_id,
        final_book_update_id=book.update_id,
        best_bid=book.best_bid.price,
        best_ask=book.best_ask.price,
        spread=book.spread,
        minimum_delay_ms=minimum_delay_ms,
        average_delay_ms=delay_sum_ms / delay_count,
        maximum_delay_ms=maximum_delay_ms,
    )


def print_report(path: Path, report: ValidationReport) -> None:
    """Display a successful validation report."""
    print(f"File: {path.resolve()}")
    print(f"Total records: {report.total_records}")
    print(f"Snapshot update ID: {report.snapshot_update_id}")
    print(f"Trade events: {report.trade_events}")
    print(f"Depth events: {report.depth_events}")
    print(f"Stale depth events: {report.stale_depth_events}")
    print(f"Applied depth events: {report.applied_depth_events}")
    print(f"Aggregate-trade IDs: {report.first_trade_id}-{report.last_trade_id}")
    print(f"Final book update ID: {report.final_book_update_id}")
    print(f"Final best bid: {report.best_bid}")
    print(f"Final best ask: {report.best_ask}")
    print(f"Final spread: {report.spread}")
    print(
        "Receipt delay ms: "
        f"min={report.minimum_delay_ms:.1f}, "
        f"avg={report.average_delay_ms:.1f}, "
        f"max={report.maximum_delay_ms:.1f}"
    )
    print("Result: VALID")


def parse_args() -> argparse.Namespace:
    """Read an optional capture path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="Capture to validate; defaults to the newest combined file.",
    )
    return parser.parse_args()


def main() -> None:
    """Validate the selected or latest combined capture."""
    args = parse_args()
    path = args.path or find_latest_capture()

    try:
        report = validate_capture(path)
    except (
        CaptureValidationError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise SystemExit(f"Result: INVALID\nReason: {error}") from error

    print_report(path, report)


if __name__ == "__main__":
    main()
