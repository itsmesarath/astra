"""Build synchronized feature rows from a combined market-data capture."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from ai_trader.features.orderbook import OrderBookFeatures
from ai_trader.features.trade_flow import (
    TradeFlowAccumulator,
    TradeFlowFeatures,
)
from ai_trader.ingestion.agg_trade import AggTrade
from ai_trader.ingestion.validate_combined import (
    DEPTH_STREAM,
    SYMBOL,
    TRADE_STREAM,
    find_latest_capture,
    read_record,
    validate_capture,
)
from ai_trader.orderbook.depth_update import DepthUpdate
from ai_trader.orderbook.local_book import LocalOrderBook

DEFAULT_OUTPUT_DIRECTORY = Path("data/processed")
DEFAULT_LEVELS = 5

CSV_COLUMNS = (
    "schema_version",
    "symbol",
    "received_at_ns",
    "depth_event_time_ms",
    "update_id",
    "levels",
    "best_bid_price",
    "best_ask_price",
    "spread",
    "midpoint",
    "microprice",
    "bid_depth",
    "ask_depth",
    "book_imbalance",
    "aggregate_trade_count",
    "underlying_trade_count",
    "buy_base_volume",
    "sell_base_volume",
    "total_base_volume",
    "signed_base_volume",
    "buy_quote_volume",
    "sell_quote_volume",
    "total_quote_volume",
    "signed_quote_volume",
    "trade_imbalance",
)


def create_output_path(
    capture_path: Path,
    *,
    levels: int,
) -> Path:
    """Create the default processed-data path for one capture."""
    DEFAULT_OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    filename = f"{capture_path.stem}_features_l{levels}.csv"
    return DEFAULT_OUTPUT_DIRECTORY / filename


def create_feature_row(
    *,
    received_at_ns: int,
    event_time_ms: int,
    book_features: OrderBookFeatures,
    trade_features: TradeFlowFeatures,
) -> dict[str, str | int]:
    """Convert synchronized book and trade state into one CSV row."""
    return {
        "schema_version": 1,
        "symbol": book_features.symbol,
        "received_at_ns": received_at_ns,
        "depth_event_time_ms": event_time_ms,
        "update_id": book_features.update_id,
        "levels": book_features.levels,
        "best_bid_price": str(book_features.best_bid_price),
        "best_ask_price": str(book_features.best_ask_price),
        "spread": str(book_features.spread),
        "midpoint": str(book_features.midpoint),
        "microprice": str(book_features.microprice),
        "bid_depth": str(book_features.bid_depth),
        "ask_depth": str(book_features.ask_depth),
        "book_imbalance": str(book_features.imbalance),
        "aggregate_trade_count": trade_features.aggregate_trade_count,
        "underlying_trade_count": trade_features.underlying_trade_count,
        "buy_base_volume": str(trade_features.buy_base_volume),
        "sell_base_volume": str(trade_features.sell_base_volume),
        "total_base_volume": str(trade_features.total_base_volume),
        "signed_base_volume": str(trade_features.signed_base_volume),
        "buy_quote_volume": str(trade_features.buy_quote_volume),
        "sell_quote_volume": str(trade_features.sell_quote_volume),
        "total_quote_volume": str(trade_features.total_quote_volume),
        "signed_quote_volume": str(trade_features.signed_quote_volume),
        "trade_imbalance": str(trade_features.base_volume_imbalance),
    }


def build_feature_dataset(
    capture_path: Path,
    output_path: Path,
    *,
    levels: int,
) -> int:
    """Validate, replay, and convert one raw capture into feature rows."""
    if levels <= 0:
        raise ValueError("Feature depth must be greater than zero.")

    validate_capture(capture_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    trade_flow = TradeFlowAccumulator(symbol=SYMBOL)
    row_count = 0

    with (
        capture_path.open(encoding="utf-8") as input_file,
        output_path.open("w", encoding="utf-8", newline="") as output_file,
    ):
        start_line = next(input_file)
        read_record(start_line, 1)

        snapshot_line = next(input_file)
        snapshot_record = read_record(snapshot_line, 2)
        snapshot_event = snapshot_record.get("event")

        if not isinstance(snapshot_event, dict):
            raise TypeError("Depth snapshot event must be a JSON object.")

        book = LocalOrderBook.from_snapshot(
            SYMBOL,
            snapshot_event,
        )

        writer = csv.DictWriter(
            output_file,
            fieldnames=CSV_COLUMNS,
        )
        writer.writeheader()

        for line_number, line in enumerate(input_file, start=3):
            record = read_record(line, line_number)
            record_type = record.get("record_type")

            if record_type == "session_end":
                break

            stream_name = record.get("stream")
            event = record.get("event")
            received_at_ns = record.get("received_at_ns")

            if not isinstance(event, dict):
                raise TypeError(f"Line {line_number} event must be a JSON object.")
            if not isinstance(received_at_ns, int):
                raise TypeError(f"Line {line_number} receipt time must be an integer.")

            if stream_name == TRADE_STREAM:
                trade_flow.add(AggTrade.from_event(event))
                continue

            if stream_name != DEPTH_STREAM:
                raise ValueError(f"Line {line_number} has unexpected stream {stream_name!r}.")

            update = DepthUpdate.from_event(event)
            applied = book.apply(update)

            if not applied:
                continue

            book_features = OrderBookFeatures.from_book(
                book,
                levels=levels,
            )
            trade_features = trade_flow.snapshot()

            writer.writerow(
                create_feature_row(
                    received_at_ns=received_at_ns,
                    event_time_ms=update.event_time_ms,
                    book_features=book_features,
                    trade_features=trade_features,
                )
            )
            row_count += 1
            trade_flow.reset()

    if row_count == 0:
        raise ValueError("Capture produced no synchronized feature rows.")

    return row_count


def parse_args() -> argparse.Namespace:
    """Read command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="Raw capture path; defaults to the newest combined capture.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output CSV path.",
    )
    parser.add_argument(
        "--levels",
        type=int,
        default=DEFAULT_LEVELS,
        help=f"Order-book levels per side (default: {DEFAULT_LEVELS}).",
    )
    args = parser.parse_args()

    if args.levels <= 0:
        parser.error("--levels must be greater than zero")

    return args


def main() -> None:
    """Build a feature dataset from the selected capture."""
    args = parse_args()
    capture_path = args.path or find_latest_capture()
    output_path = args.output or create_output_path(
        capture_path,
        levels=args.levels,
    )

    print(f"Validating and replaying: {capture_path.resolve()}")

    row_count = build_feature_dataset(
        capture_path,
        output_path,
        levels=args.levels,
    )

    print(f"Feature depth: top {args.levels} levels per side")
    print(f"Rows written: {row_count}")
    print(f"Output: {output_path.resolve()}")


if __name__ == "__main__":
    main()
