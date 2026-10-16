"""Research-only source-time alignment of pinned Bybit spot trades and OB200.

This is a metadata audit, not a market-data importer. It never emits joined
trade/book rows, features, labels, simulated orders, or training examples.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
import time
import zipfile
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ai_trader.research import bybit_orderbook_audit as book_audit

VERSION = "bybit_spot_trade_book_source_time_audit_v1"
TRADE_HEADER = ["id", "timestamp", "price", "volume", "side", "rpi"]
MAX_TRADE_ARCHIVE_BYTES = 20_000_000
MAX_TRADE_LINE_BYTES = 512
MAX_TRADE_ROWS = 2_000_000
MAX_SECONDS = 120


@dataclass(frozen=True, slots=True)
class BookStamp:
    ts: int
    cts: int
    update_id: int


def _book_stamps(path: Path):
    """Yield source-order timestamps from the independently reconstructed ZIP."""
    with zipfile.ZipFile(path) as archive:
        member = archive.infolist()[0]
        with archive.open(member) as source:
            while line := source.readline(book_audit.MAX_LINE_BYTES + 1):
                if len(line) > book_audit.MAX_LINE_BYTES:
                    raise ValueError("Order-book message exceeds line-byte budget.")
                item = json.loads(line)
                if (
                    item.get("topic") != book_audit.TOPIC
                    or item.get("data", {}).get("s") != "BTCUSDT"
                ):
                    raise ValueError("Wrong book source identity during alignment.")
                yield BookStamp(
                    ts=book_audit._int_field(item.get("ts"), "book source timestamp"),
                    cts=book_audit._int_field(item.get("cts"), "book engine timestamp"),
                    update_id=book_audit._int_field(item["data"].get("u"), "book update ID"),
                )


def _trade_rows(path: Path):
    """Read bounded source-order CSV rows without sorting or changing the archive."""
    with gzip.open(path, "rb") as source:
        header_line = source.readline(MAX_TRADE_LINE_BYTES + 1)
        if len(header_line) > MAX_TRADE_LINE_BYTES:
            raise ValueError("Trade CSV header exceeds line-byte budget.")
        try:
            header = next(csv.reader([header_line.decode("utf-8-sig")], strict=True))
        except (UnicodeDecodeError, csv.Error, StopIteration) as error:
            raise ValueError("Malformed Bybit spot trade CSV header.") from error
        if header != TRADE_HEADER:
            raise ValueError("Unexpected Bybit spot trade CSV header.")
        while line := source.readline(MAX_TRADE_LINE_BYTES + 1):
            if len(line) > MAX_TRADE_LINE_BYTES:
                raise ValueError("Trade CSV row exceeds line-byte budget.")
            try:
                row = next(csv.reader([line.decode("utf-8")], strict=True))
            except (UnicodeDecodeError, csv.Error, StopIteration) as error:
                raise ValueError("Malformed trade CSV row.") from error
            if len(row) != len(TRADE_HEADER):
                raise ValueError("Unexpected trade CSV column count.")
            yield row


def _trade(row: list[str]) -> tuple[int, int, str, str]:
    identifier, timestamp, price_raw, volume_raw, side, rpi = row
    if (
        re.fullmatch(r"[0-9]{1,20}", identifier) is None
        or re.fullmatch(r"[0-9]{1,20}", timestamp) is None
        or side not in ("buy", "sell")
        or rpi not in ("0", "1")
        or len(price_raw) > 64
        or len(volume_raw) > 64
    ):
        raise ValueError("Invalid trade identifier, timestamp, side, RPI, or numeric width.")
    try:
        price, volume = Decimal(price_raw), Decimal(volume_raw)
    except InvalidOperation as error:
        raise ValueError("Invalid trade price or volume.") from error
    if (
        not price.is_finite()
        or not volume.is_finite()
        or not 0 < price <= book_audit.MAX_NUMBER
        or not 0 < volume <= book_audit.MAX_NUMBER
    ):
        raise ValueError("Invalid trade price or volume.")
    return int(identifier), int(timestamp), side, rpi


def _age_bucket(age_ms: int) -> str:
    if age_ms <= 100:
        return "1_to_100_ms"
    if age_ms <= 500:
        return "101_to_500_ms"
    if age_ms <= 1_000:
        return "501_to_1000_ms"
    return "over_1000_ms"


def audit_alignment(
    trade_path: Path,
    trade_sha256: str,
    book_path: Path,
    book_sha256: str,
    day: str,
) -> dict[str, object]:
    """Count strict-prior source-time joins; never publish joined observations."""
    trade_path, book_path = Path(trade_path), Path(book_path)
    if re.fullmatch(r"[0-9a-fA-F]{64}", trade_sha256) is None:
        raise ValueError("A 64-character trade SHA256 pin is required.")
    start_ms, end_ms = book_audit._day_bounds(day)
    if not 0 < trade_path.stat().st_size <= MAX_TRADE_ARCHIVE_BYTES:
        raise ValueError("Trade archive exceeds compressed-byte budget or is empty.")
    trade_sha256 = trade_sha256.lower()
    if book_audit._sha256(trade_path) != trade_sha256:
        raise ValueError("Trade archive differs from pinned SHA256.")
    reconstructed = book_audit.audit_archive(book_path, book_sha256, day)
    deadline = time.monotonic() + MAX_SECONDS

    trade_count = no_prior_book = equal_timestamp_withheld = id_discontinuities = 0
    side_counts: Counter[str] = Counter()
    rpi_counts: Counter[str] = Counter()
    age_counts: Counter[str] = Counter()
    first_trade_ms = last_trade_ms = previous_trade_ms = previous_id = None
    min_age_ms = max_age_ms = None
    book_count = advanced_books = boundary_books = 0
    first_book_ms = last_book_ms = None
    min_book_ts_minus_cts = max_book_ts_minus_cts = None

    def advance_book(stamp: BookStamp) -> None:
        nonlocal book_count, boundary_books, first_book_ms, last_book_ms
        nonlocal min_book_ts_minus_cts, max_book_ts_minus_cts
        book_count += 1
        if first_book_ms is None:
            first_book_ms = stamp.ts
        last_book_ms = stamp.ts
        if stamp.ts >= end_ms:
            boundary_books += 1
        lag = stamp.ts - stamp.cts
        min_book_ts_minus_cts = (
            lag if min_book_ts_minus_cts is None else min(lag, min_book_ts_minus_cts)
        )
        max_book_ts_minus_cts = (
            lag if max_book_ts_minus_cts is None else max(lag, max_book_ts_minus_cts)
        )

    stamps = _book_stamps(book_path)
    upcoming = next(stamps, None)
    if upcoming is not None:
        advance_book(upcoming)
    preceding = None
    for row in _trade_rows(trade_path):
        trade_count += 1
        if trade_count > MAX_TRADE_ROWS:
            raise ValueError("Trade/book audit exceeded row budget.")
        if trade_count % 1024 == 0 and time.monotonic() >= deadline:
            raise TimeoutError("Trade/book audit exceeded elapsed-time budget.")
        identifier, timestamp, side, rpi = _trade(row)
        if not start_ms <= timestamp < end_ms:
            raise ValueError("Trade timestamp outside declared UTC archive day.")
        if previous_trade_ms is not None and timestamp < previous_trade_ms:
            raise ValueError("Trade source time regressed.")
        if previous_id is not None and identifier != previous_id + 1:
            id_discontinuities += 1
        if first_trade_ms is None:
            first_trade_ms = timestamp
        previous_trade_ms = last_trade_ms = timestamp
        previous_id = identifier
        side_counts[side] += 1
        rpi_counts[rpi] += 1
        while upcoming is not None and upcoming.ts < timestamp:
            preceding = upcoming
            advanced_books += 1
            upcoming = next(stamps, None)
            if upcoming is not None:
                advance_book(upcoming)
        if upcoming is not None and upcoming.ts == timestamp:
            equal_timestamp_withheld += 1
        if preceding is None:
            no_prior_book += 1
        else:
            age = timestamp - preceding.ts
            if age <= 0:
                raise ValueError("Nonpreceding book selected for trade.")
            age_counts[_age_bucket(age)] += 1
            min_age_ms = age if min_age_ms is None else min(min_age_ms, age)
            max_age_ms = age if max_age_ms is None else max(max_age_ms, age)

    for stamp in stamps:
        advance_book(stamp)
    if trade_count == 0 or book_count != reconstructed["messages"]:
        raise ValueError("Trade archive is empty or book scan differs from reconstruction.")
    if (
        first_book_ms != reconstructed["first_source_timestamp_ms"]
        or last_book_ms != reconstructed["last_source_timestamp_ms"]
    ):
        raise ValueError("Book timestamp coverage differs from reconstruction.")
    if boundary_books != reconstructed["post_boundary_messages"]:
        raise ValueError("Book boundary count differs from reconstruction.")
    if (
        time.monotonic() >= deadline
        or book_audit._sha256(trade_path) != trade_sha256
        or book_audit._sha256(book_path) != reconstructed["archive_sha256"]
    ):
        raise ValueError("Audit timed out or pinned source changed during alignment.")
    return {
        "schema_version": 1,
        "protocol": VERSION,
        "status": "source_time_alignment_audited_research_only",
        "archive_date_utc": day,
        "trade_archive_sha256": trade_sha256,
        "book_archive_sha256": reconstructed["archive_sha256"],
        "book_reconstruction_protocol": reconstructed["protocol"],
        "book_messages": book_count,
        "post_boundary_book_messages": boundary_books,
        "book_messages_strictly_before_last_trade": advanced_books,
        "book_messages_not_eligible_for_any_trade": book_count - advanced_books,
        "book_ts_minus_cts_min_ms": min_book_ts_minus_cts,
        "book_ts_minus_cts_max_ms": max_book_ts_minus_cts,
        "trade_rows": trade_count,
        "first_trade_timestamp_ms": first_trade_ms,
        "last_trade_timestamp_ms": last_trade_ms,
        "trade_id_discontinuities": id_discontinuities,
        "observed_side_counts": dict(side_counts),
        "observed_rpi_counts": dict(rpi_counts),
        "trades_without_strictly_prior_book": no_prior_book,
        "trades_with_equal_timestamp_book_withheld": equal_timestamp_withheld,
        "strictly_prior_book_age_counts": dict(age_counts),
        "strictly_prior_book_age_min_ms": min_age_ms,
        "strictly_prior_book_age_max_ms": max_age_ms,
        "join_rule": "latest_book_system_ts_strictly_less_than_trade_archive_timestamp",
        "training_allowed": False,
        "paper_trading_allowed": False,
        "limitations": [
            "Archive trade timestamp semantics were not independently documented in the CSV.",
            "Source-time order does not establish network receipt or executable availability.",
            "Equal-millisecond cross-stream order is unknown, so those book events are withheld.",
            "No joined rows, CVD, features, labels, or trading outcomes were produced.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", required=True, type=Path)
    parser.add_argument("--trade-sha256", required=True)
    parser.add_argument("--orderbook", required=True, type=Path)
    parser.add_argument("--orderbook-sha256", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit_alignment(
        args.trades, args.trade_sha256, args.orderbook, args.orderbook_sha256, args.date
    )
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    if len(payload) > 100_000:
        raise ValueError("Audit report exceeds metadata budget.")
    with args.output.open("xb") as destination:
        destination.write(payload)
        destination.flush()
        os.fsync(destination.fileno())
    print(json.dumps({"status": report["status"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
