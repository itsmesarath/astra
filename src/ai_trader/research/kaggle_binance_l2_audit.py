"""Read-only, source-qualified audit of the Kaggle Binance Spot L2 sample.

This is not the receipt-causal live capture format. Snapshot/diff update IDs
permit book reconstruction, but the publisher's ``received_at`` semantics are
unverified, so this module never exports model features or training rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np

FILES = {
    "trades": "trades_20260418.parquet",
    "snapshots": "orderbook_snapshots_20260418.parquet",
    "diffs": "orderbook_diffs_20260418.parquet",
}
MAX_BYTES = {"trades": 32_000_000, "snapshots": 32_000_000, "diffs": 250_000_000}
MAX_ROWS = {"trades": 2_500_000, "snapshots": 2_000, "diffs": 1_000_000}
TOP_LEVELS = 20
MAX_EXAMPLES = 20
MAX_SECONDS = 300


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_file(path: Path, expected_sha256: str, max_bytes: int) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Missing or linked source: {path.name}.")
    if path.stat().st_size > max_bytes:
        raise ValueError(f"Source exceeds byte budget: {path.name}.")
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise ValueError("Expected a lowercase SHA256 pin.")
    actual = _sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"Source differs from pinned SHA256: {path.name}.")
    return actual


def _int_column(table, name: str) -> np.ndarray:
    values = table[name].combine_chunks().to_numpy(zero_copy_only=False)
    if values.dtype.kind not in "iu" or np.any(table[name].is_null().to_numpy()):
        raise ValueError(f"Invalid integer column: {name}.")
    return values.astype(np.int64, copy=False)


def _time_column(table, name: str) -> np.ndarray:
    column = table[name].combine_chunks()
    if column.null_count or str(column.type) != "timestamp[ns, tz=UTC]":
        raise ValueError(f"Invalid UTC nanosecond timestamp: {name}.")
    return column.to_numpy(zero_copy_only=False).view("int64")


def _number(value: object, *, positive: bool) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("Book levels must contain decimal strings.")
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Invalid book decimal.") from error
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise ValueError("Invalid book price or quantity.")
    return number


def _parse_levels(raw: str, *, snapshot: bool) -> list[tuple[Decimal, Decimal]]:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid book JSON.") from error
    if not isinstance(value, list) or len(value) > 20_000:
        raise ValueError("Invalid book level count.")
    levels = []
    seen = set()
    for pair in value:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("Invalid book level pair.")
        price = _number(pair[0], positive=True)
        qty = _number(pair[1], positive=snapshot)
        if price in seen:
            raise ValueError("Duplicate price level in one book message.")
        seen.add(price)
        levels.append((price, qty))
    return levels


def _snapshot_book(bids_raw: str, asks_raw: str) -> tuple[dict, dict]:
    bids = dict(_parse_levels(bids_raw, snapshot=True))
    asks = dict(_parse_levels(asks_raw, snapshot=True))
    if not bids or not asks or max(bids) >= min(asks):
        raise ValueError("Empty or crossed snapshot book.")
    return bids, asks


def _apply(book: tuple[dict, dict], bids_raw: str, asks_raw: str) -> None:
    for side, raw in zip(book, (bids_raw, asks_raw), strict=True):
        for price, qty in _parse_levels(raw, snapshot=False):
            if qty == 0:
                side.pop(price, None)
            else:
                side[price] = qty


def _top(book: tuple[dict, dict]) -> tuple[tuple, tuple]:
    bids, asks = book
    if not bids or not asks:
        raise ValueError("Reconstructed book became empty.")
    bid_prices = sorted(bids, reverse=True)[:TOP_LEVELS]
    ask_prices = sorted(asks)[:TOP_LEVELS]
    if bid_prices[0] >= ask_prices[0]:
        raise ValueError("Reconstructed book crossed.")
    return (
        tuple((price, bids[price]) for price in bid_prices),
        tuple((price, asks[price]) for price in ask_prices),
    )


def _mismatch_detail(
    book: tuple[dict, dict], expected: tuple[dict, dict], prior: tuple[dict, dict]
) -> dict:
    """Mark differences plausibly caused by the prior 1,000-level depth limit."""
    wanted = _top(expected)
    missing_bids = [price for price, _ in wanted[0] if price not in book[0]]
    missing_asks = [price for price, _ in wanted[1] if price not in book[1]]
    observed_top = _top(book)
    observed_maps = tuple(dict(side) for side in observed_top)
    shared_quantity_difference = any(
        price in observed and observed[price] != quantity
        for wanted_side, observed in zip(wanted, observed_maps, strict=True)
        for price, quantity in wanted_side
    )
    outside = all(price < min(prior[0]) for price in missing_bids) and all(
        price > max(prior[1]) for price in missing_asks
    )
    return {
        "missing_expected_bid_levels": len(missing_bids),
        "missing_expected_ask_levels": len(missing_asks),
        "consistent_with_truncated_prior_snapshot": bool(
            (missing_bids or missing_asks) and outside and not shared_quantity_difference
        ),
    }


def _event_columns(batch) -> dict[str, object]:
    return {
        name: batch.column(batch.schema.get_field_index(name)).to_pylist()
        for name in ("symbol", "bids", "asks", "first_update_id", "final_update_id")
    } | {
        name: batch.column(batch.schema.get_field_index(name))
        .to_numpy(zero_copy_only=False)
        .view("int64")
        for name in ("time", "received_at")
    }


def _audit_trades(path: Path, parquet) -> dict:
    table = parquet.read_table(path, columns=["time", "received_at", "trade_id"])
    ids = _int_column(table, "trade_id")
    event = _time_column(table, "time")
    receipt = _time_column(table, "received_at")
    if len(ids) == 0 or np.any(ids < 0) or np.any(np.diff(event) < 0):
        raise ValueError("Trade IDs or timestamps are invalid.")
    order = np.argsort(ids)
    sorted_ids = ids[order]
    gaps = np.flatnonzero(np.diff(sorted_ids) > 1)
    if np.any(np.diff(sorted_ids) == 0):
        raise ValueError("Duplicate trade IDs.")
    return {
        "rows": len(ids),
        "first_event_ns": int(event[0]),
        "last_event_ns": int(event[-1]),
        "id_gap_count": len(gaps),
        "missing_id_positions": int(np.sum(np.diff(sorted_ids)[gaps] - 1)),
        "id_gaps": [
            {
                "after_id": int(sorted_ids[i]),
                "before_id": int(sorted_ids[i + 1]),
                "event_ns": int(event[order[i + 1]]),
            }
            for i in gaps[:MAX_EXAMPLES]
        ],
        "stored_order_id_regressions": int(np.count_nonzero(np.diff(ids) < 0)),
        "receipt_regressions": int(np.count_nonzero(np.diff(receipt) < 0)),
        "median_stored_receipt_minus_event_ms": float(np.median((receipt - event) / 1e6)),
    }


def audit(directory: Path, pins: dict[str, str]) -> dict:
    """Verify original bytes, sequence continuity and exact-ID top-20 snapshots."""
    import pyarrow.parquet as parquet

    if set(pins) != set(FILES):
        raise ValueError("Three explicit source pins are required.")
    paths = {kind: directory / name for kind, name in FILES.items()}
    hashes = {kind: _verify_file(paths[kind], pins[kind], MAX_BYTES[kind]) for kind in FILES}
    files = {kind: parquet.ParquetFile(path) for kind, path in paths.items()}
    for kind, source in files.items():
        if not 1 <= source.metadata.num_rows <= MAX_ROWS[kind]:
            raise ValueError(f"Invalid {kind} row count.")
    trades = _audit_trades(paths["trades"], parquet)
    snapshot_table = parquet.read_table(paths["snapshots"])
    snapshot_ids = _int_column(snapshot_table, "last_update_id")
    snapshot_times = _time_column(snapshot_table, "time")
    snapshot_receipts = _time_column(snapshot_table, "received_at")
    if np.any(np.diff(snapshot_ids) <= 0) or np.any(np.diff(snapshot_times) < 0):
        raise ValueError("Snapshots are not ordered.")
    if np.any(np.diff(snapshot_receipts) < 0):
        raise ValueError("Snapshot receipt values regressed.")
    symbols = snapshot_table["symbol"].to_pylist()
    if any(symbol != "BTCUSDT" for symbol in symbols):
        raise ValueError("Unexpected snapshot symbol.")
    snapshot_bids = snapshot_table["bids"].to_pylist()
    snapshot_asks = snapshot_table["asks"].to_pylist()
    snapshots = [
        _snapshot_book(bids, asks) for bids, asks in zip(snapshot_bids, snapshot_asks, strict=True)
    ]

    started = time.monotonic()
    book = (snapshots[0][0].copy(), snapshots[0][1].copy())
    current_id = int(snapshot_ids[0])
    next_snapshot = 1
    prev_first = prev_final = prev_event = prev_receipt = None
    gap_examples = []
    mismatches = []
    gap_count = mismatch_count = coverage_limited_count = 0
    matched = bridged = unverified = 0
    rows = 0
    for batch in files["diffs"].iter_batches(batch_size=4096):
        if time.monotonic() - started > MAX_SECONDS:
            raise TimeoutError("Historical L2 audit exceeded elapsed budget.")
        columns = _event_columns(batch)
        for i in range(batch.num_rows):
            rows += 1
            first, final = columns["first_update_id"][i], columns["final_update_id"][i]
            event, receipt = int(columns["time"][i]), int(columns["received_at"][i])
            if (
                columns["symbol"][i] != "BTCUSDT"
                or type(first) is not int
                or type(final) is not int
                or first < 0
                or final < first
                or (prev_final is not None and final <= prev_final)
                or (prev_event is not None and event < prev_event)
                or (prev_receipt is not None and receipt < prev_receipt)
            ):
                raise ValueError(f"Invalid depth row at {rows}.")
            bids_raw, asks_raw = columns["bids"][i], columns["asks"][i]
            if prev_final is not None and first > prev_final + 1:
                gap_count += 1
                if len(gap_examples) < MAX_EXAMPLES:
                    gap_examples.append(
                        {
                            "row": rows,
                            "event_ns": event,
                            "missing_id_positions": first - prev_final - 1,
                        }
                    )
                book = None
            elif prev_final is not None and first != prev_final + 1:
                raise ValueError(f"Overlapping depth ranges at {rows}.")
            prev_first, prev_final = first, final
            prev_event, prev_receipt = event, receipt

            if book is not None and final > current_id:
                if first > current_id + 1:
                    book = None
                else:
                    _apply(book, bids_raw, asks_raw)
                    current_id = final
            if book is None:
                # Still parse unanchored updates; a gap is not silently repaired.
                _parse_levels(bids_raw, snapshot=False)
                _parse_levels(asks_raw, snapshot=False)

            while next_snapshot < len(snapshot_ids) and snapshot_ids[next_snapshot] <= final:
                anchor = int(snapshot_ids[next_snapshot])
                if anchor == final and book is not None and current_id == anchor:
                    if _top(book) == _top(snapshots[next_snapshot]):
                        matched += 1
                    else:
                        mismatch_count += 1
                        detail = _mismatch_detail(
                            book, snapshots[next_snapshot], snapshots[next_snapshot - 1]
                        )
                        coverage_limited_count += int(
                            detail["consistent_with_truncated_prior_snapshot"]
                        )
                        if len(mismatches) < MAX_EXAMPLES:
                            mismatches.append(
                                {
                                    "snapshot_index": next_snapshot,
                                    "update_id": anchor,
                                    "snapshot_event_ns": int(snapshot_times[next_snapshot]),
                                    **detail,
                                }
                            )
                elif anchor < final:
                    bridged += 1
                else:
                    unverified += 1
                book = (
                    snapshots[next_snapshot][0].copy(),
                    snapshots[next_snapshot][1].copy(),
                )
                current_id = anchor
                if anchor < final:
                    if first <= anchor + 1 <= final:
                        _apply(book, bids_raw, asks_raw)
                        current_id = final
                    else:
                        book = None
                next_snapshot += 1

    return {
        "schema_version": 2,
        "status": "historical_l2_research_audit",
        "source": "kaggle_binance_btcusdt_20260418",
        "sha256": hashes,
        "trades": trades,
        "diffs": {
            "rows": rows,
            "last_first_update_id": int(prev_first) if prev_first is not None else None,
            "last_update_id": int(prev_final) if prev_final is not None else None,
            "forward_gap_count": gap_count,
            "forward_gaps": gap_examples,
        },
        "snapshots": {
            "rows": len(snapshot_ids),
            "matched_top20": matched,
            "bridged_nonexact": bridged,
            "unverified": unverified + len(snapshot_ids) - next_snapshot,
            "top20_mismatch_count": mismatch_count,
            "consistent_with_truncated_prior_snapshot_count": coverage_limited_count,
            "top20_mismatches": mismatches,
        },
        "time_policy": "publisher_received_at_semantics_unverified",
        "training_allowed": False,
        "paper_trading_allowed": False,
        "promotion_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--trades-sha256", required=True)
    parser.add_argument("--snapshots-sha256", required=True)
    parser.add_argument("--diffs-sha256", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Report already exists; refusing overwrite.")
    result = audit(
        args.directory,
        {
            "trades": args.trades_sha256,
            "snapshots": args.snapshots_sha256,
            "diffs": args.diffs_sha256,
        },
    )
    with args.report.open("x", encoding="utf-8") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write("\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
