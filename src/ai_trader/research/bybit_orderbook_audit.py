"""Bounded, offline reconstruction audit for one pinned Bybit spot OB200 ZIP.

This reads source order without sorting, repairing, exporting features, or enabling
training/trading. A matching closing snapshot is required before claiming that
the archived 200-level book reconstructed successfully.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import zipfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

VERSION = "bybit_spot_ob200_archive_audit_v1"
TOPIC = "orderbook.200.BTCUSDT"
SYMBOL = "BTCUSDT"
MAX_ARCHIVE_BYTES = 80_000_000
MAX_DECODED_BYTES = 600_000_000
MAX_LINE_BYTES = 1_000_000
MAX_MESSAGES = 2_000_000
MAX_SECONDS = 120
MAX_BOUNDARY_MESSAGES = 10
MAX_BOUNDARY_SPILL_MS = 1_000
MAX_LEVELS = 200
MAX_DELTA_CHANGES_PER_SIDE = 1_000
MAX_NUMBER = Decimal("1e12")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _day_bounds(day: str) -> tuple[int, int]:
    if type(day) is not str or re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) is None:
        raise ValueError("Expected a UTC date in YYYY-MM-DD format.")
    start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UTC)
    return int(start.timestamp() * 1000), int((start + timedelta(days=1)).timestamp() * 1000)


def _levels(raw: object, *, side: str, snapshot: bool) -> tuple[tuple[Decimal, Decimal], ...]:
    limit = MAX_LEVELS if snapshot else MAX_DELTA_CHANGES_PER_SIDE
    if type(raw) is not list or len(raw) > limit:
        raise ValueError(f"Invalid {side} level count or type.")
    if snapshot and not raw:
        raise ValueError(f"Empty {side} snapshot.")
    parsed = []
    seen = set()
    for level in raw:
        if (
            type(level) is not list
            or len(level) != 2
            or any(type(value) is not str or len(value) > 64 for value in level)
        ):
            raise ValueError(f"Malformed {side} level.")
        try:
            price, size = (Decimal(value) for value in level)
        except InvalidOperation as error:
            raise ValueError(f"Invalid {side} numeric level.") from error
        if (
            not price.is_finite()
            or not size.is_finite()
            or not 0 < price <= MAX_NUMBER
            or not 0 <= size <= MAX_NUMBER
            or (snapshot and size == 0)
            or price in seen
        ):
            raise ValueError(f"Invalid or duplicate {side} price/size.")
        seen.add(price)
        parsed.append((price, size))
    if snapshot:
        prices = [price for price, _ in parsed]
        if prices != sorted(prices, reverse=side == "bid"):
            raise ValueError(f"Unsorted {side} snapshot.")
    return tuple(parsed)


def _int_field(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"Invalid {name}.")
    return value


def _parse(line: bytes) -> tuple[dict, int, int, int, tuple, tuple]:
    try:
        event = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Malformed order-book JSON line.") from error
    if type(event) is not dict or event.get("topic") != TOPIC:
        raise ValueError("Wrong order-book topic.")
    if event.get("type") not in ("snapshot", "delta"):
        raise ValueError("Unsupported order-book message type.")
    data = event.get("data")
    if type(data) is not dict or data.get("s") != SYMBOL:
        raise ValueError("Wrong order-book symbol.")
    timestamp = _int_field(event.get("ts"), "source timestamp")
    _int_field(event.get("cts"), "matching-engine timestamp")
    update_id = _int_field(data.get("u"), "update ID")
    sequence = _int_field(data.get("seq"), "cross sequence")
    snapshot = event["type"] == "snapshot"
    bids = _levels(data.get("b"), side="bid", snapshot=snapshot)
    asks = _levels(data.get("a"), side="ask", snapshot=snapshot)
    return event, timestamp, update_id, sequence, bids, asks


def _apply_side(
    levels: dict[Decimal, Decimal],
    changes: tuple[tuple[Decimal, Decimal], ...],
    best: Decimal,
    *,
    bid: bool,
) -> Decimal:
    for price, size in changes:
        if size == 0:
            levels.pop(price, None)
        else:
            levels[price] = size
            if (price > best) if bid else (price < best):
                best = price
    if not levels or len(levels) > MAX_LEVELS:
        raise ValueError("Reconstructed book is empty or exceeds 200 levels per side.")
    if best not in levels:
        best = max(levels) if bid else min(levels)
    return best


def audit_archive(archive_path: Path, expected_sha256: str, day: str) -> dict[str, object]:
    """Verify a single source-pinned archive and replay every OB200 message."""
    archive_path = Path(archive_path)
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("A 64-character source SHA256 pin is required.")
    start_ms, end_ms = _day_bounds(day)
    if not 0 < archive_path.stat().st_size <= MAX_ARCHIVE_BYTES:
        raise ValueError("Archive exceeds compressed-byte budget or is empty.")
    expected_sha256 = expected_sha256.lower()
    if _sha256(archive_path) != expected_sha256:
        raise ValueError("Archive differs from pinned SHA256.")

    deadline = time.monotonic() + MAX_SECONDS
    messages = snapshots = deltas = matched_snapshots = boundary_messages = 0
    decoded_bytes = first_ms = last_ms = last_u = last_seq = None
    bids = asks = None
    best_bid = best_ask = None
    closing_snapshot_matched = False
    max_bid_levels = max_ask_levels = 0
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        expected_member = archive_path.name.removesuffix(".zip")
        if (
            len(members) != 1
            or members[0].filename != expected_member
            or members[0].is_dir()
            or members[0].flag_bits & 1
            or not 0 < members[0].file_size <= MAX_DECODED_BYTES
        ):
            raise ValueError("Unsupported ZIP member identity, encryption, or size.")
        with archive.open(members[0]) as source:
            while line := source.readline(MAX_LINE_BYTES + 1):
                if len(line) > MAX_LINE_BYTES:
                    raise ValueError("Order-book message exceeds line-byte budget.")
                decoded_bytes = (decoded_bytes or 0) + len(line)
                messages += 1
                if messages > MAX_MESSAGES or decoded_bytes > MAX_DECODED_BYTES:
                    raise ValueError("Order-book message/decoded-byte budget exceeded.")
                if messages % 1024 == 0 and time.monotonic() >= deadline:
                    raise TimeoutError("Order-book audit exceeded elapsed-time budget.")
                event, timestamp, update_id, sequence, bid_levels, ask_levels = _parse(line)
                if timestamp < start_ms or timestamp > end_ms + MAX_BOUNDARY_SPILL_MS:
                    raise ValueError("Order-book timestamp outside bounded archive day.")
                if timestamp >= end_ms:
                    boundary_messages += 1
                    if boundary_messages > MAX_BOUNDARY_MESSAGES:
                        raise ValueError("Too many post-boundary messages.")
                elif boundary_messages:
                    raise ValueError("In-day event after post-boundary event.")
                if last_ms is not None and timestamp < last_ms:
                    raise ValueError("Order-book source time regressed.")
                if last_seq is not None and sequence < last_seq:
                    raise ValueError("Order-book cross sequence regressed.")
                if first_ms is None:
                    first_ms = timestamp
                if event["type"] == "snapshot":
                    snapshots += 1
                    if messages != 1:
                        if update_id != last_u or sequence != last_seq:
                            raise ValueError("Unbridged intermediate snapshot/reset.")
                        if bids != dict(bid_levels) or asks != dict(ask_levels):
                            raise ValueError("Snapshot differs from replayed book.")
                        matched_snapshots += 1
                        closing_snapshot_matched = True
                    bids, asks = dict(bid_levels), dict(ask_levels)
                    best_bid, best_ask = max(bids), min(asks)
                else:
                    deltas += 1
                    if bids is None or asks is None or update_id != last_u + 1:
                        raise ValueError("Missing snapshot or nonconsecutive delta update ID.")
                    best_bid = _apply_side(bids, bid_levels, best_bid, bid=True)
                    best_ask = _apply_side(asks, ask_levels, best_ask, bid=False)
                    closing_snapshot_matched = False
                if best_bid >= best_ask:
                    raise ValueError("Reconstructed book is locked or crossed.")
                max_bid_levels = max(max_bid_levels, len(bids))
                max_ask_levels = max(max_ask_levels, len(asks))
                last_ms, last_u, last_seq = timestamp, update_id, sequence
    if decoded_bytes != members[0].file_size:
        raise ValueError("Decoded byte count differs from ZIP member metadata.")
    if not closing_snapshot_matched or deltas == 0:
        raise ValueError("No matching closing snapshot after replayed deltas.")
    if time.monotonic() >= deadline or _sha256(archive_path) != expected_sha256:
        raise ValueError("Audit timed out or source changed during replay.")
    return {
        "schema_version": 1,
        "protocol": VERSION,
        "status": "reconstruction_verified_research_only",
        "archive_name": archive_path.name,
        "archive_sha256": expected_sha256,
        "archive_date_utc": day,
        "messages": messages,
        "snapshots": snapshots,
        "deltas": deltas,
        "matched_snapshots": matched_snapshots,
        "post_boundary_messages": boundary_messages,
        "first_source_timestamp_ms": first_ms,
        "last_source_timestamp_ms": last_ms,
        "last_update_id": last_u,
        "last_cross_sequence": last_seq,
        "max_levels_per_side": {"bid": max_bid_levels, "ask": max_ask_levels},
        "final_best_bid": str(best_bid),
        "final_best_ask": str(best_ask),
        "training_allowed": False,
        "paper_trading_allowed": False,
        "limitations": [
            "Reconstruction does not certify exchange completeness or causal receipt times.",
            "Boundary records remain visible; no trim, merge, or training split was performed.",
            "Trade alignment, feature validity, and execution outcomes were not evaluated.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit_archive(args.archive, args.sha256, args.date)
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
