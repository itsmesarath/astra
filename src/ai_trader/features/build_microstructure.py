"""Build a separate, versioned microstructure JSONL artifact from an explicit capture.

Offline processing only. Existing feature CSVs and model feature schemas are not
changed. Completion requires an artifact_end record; temporary files are never
published as completed artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import tempfile
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from ai_trader.features.microstructure import MicrostructureConfig, MicrostructureEngine
from ai_trader.ingestion.agg_trade import AggTrade
from ai_trader.ingestion.validate_combined import (
    DEPTH_STREAM,
    SYMBOL,
    TRADE_STREAM,
    read_record,
    validate_capture,
)
from ai_trader.orderbook.depth_update import DepthUpdate
from ai_trader.orderbook.local_book import LocalOrderBook

SNAPSHOT_POLICY = "strictly_after_snapshot_receipt_v1"


def snapshot_available_at_ns(start: dict, snapshot: dict) -> int:
    """Require recorded availability, never guess it from the first buffered event."""
    values = (
        start.get("started_at_ns"),
        snapshot.get("requested_at_ns"),
        snapshot.get("received_at_ns"),
    )
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("Explicit integer session/snapshot availability timestamps required.")
    if not values[0] <= values[1] <= values[2]:
        raise ValueError("Snapshot availability timestamps are out of order.")
    return values[2]


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _decimal(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError("Unsupported microstructure JSON value.")


def _line(record: dict) -> str:
    return json.dumps(record, default=_decimal, sort_keys=True, allow_nan=False) + "\n"


def build_microstructure_dataset(
    capture_path: Path,
    output_path: Path,
    *,
    source_session: str,
    config: MicrostructureConfig | None = None,
) -> int:
    """Validate capture and bind observations to unchanged source bytes.

    All observations use recorded receipt order. Validation inspects the full capture
    to reject bad sessions; it supplies no future values to the online feature engine.
    An exclusive hard link publishes a complete temporary file without overwriting a
    racing destination. The output filesystem must support hard links.
    """
    if output_path.exists():
        raise FileExistsError(output_path)
    config = config or MicrostructureConfig()
    config.validate()
    if not isinstance(source_session, str) or not source_session.strip():
        raise ValueError("Source session is required.")
    checksum = _sha256(capture_path)
    package_root = Path(__file__).resolve().parents[1]
    implementation = {
        path.relative_to(package_root).as_posix(): _sha256(path)
        for path in sorted(package_root.rglob("*.py"))
    }
    validate_capture(capture_path)
    if _sha256(capture_path) != checksum:
        raise ValueError("Capture changed during validation.")
    with capture_path.open(encoding="utf-8") as source:
        start, snapshot = read_record(next(source), 1), read_record(next(source), 2)
        available = snapshot_available_at_ns(start, snapshot)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    count = 0
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output_path.parent,
            prefix=".microstructure-",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary_path = Path(output.name)
            output.write(
                _line(
                    {
                        "record_type": "artifact_start",
                        "schema_version": 2,
                        "feature_schema": "receipt_causal_microstructure_v1",
                        "snapshot_policy": SNAPSHOT_POLICY,
                        "snapshot_received_at_ns": available,
                        "source_session": source_session,
                        "source_sha256": checksum,
                        "implementation_sha256": implementation,
                        "python_version": platform.python_version(),
                        "decimal_policy": "precision_28_round_half_even",
                        "config": asdict(config),
                        "execution_mode": "research_only",
                        "time_policy": "receipt_order_rolling_window_left_open_right_closed",
                        "matching_policy": (
                            "previous_depth_event_time_lt_trade_time_le_current_depth"
                        ),
                        "cvd_policy": "post_snapshot_aggregate_taker_buy_minus_sell_session_reset",
                        "evidence_policy": "best_price_net_addition_and_retained_depth_proxies",
                        "limitations": [
                            "not_confirmed_icebergs",
                            "no_order_identity_or_hidden_size",
                            "cross_stream_matching_heuristic",
                            "snapshot_depth_is_bounded",
                            "no_trading_signal_or_profitability_claim",
                        ],
                    }
                )
            )
            with capture_path.open(encoding="utf-8") as source:
                read_record(next(source), 1)
                snapshot = read_record(next(source), 2)
                book = LocalOrderBook.from_snapshot(SYMBOL, snapshot["event"])
                # Preserve full-stream numeric, chronology, coverage and buffer validation.
                # Its pre-availability state/rows are validation-only, never exported or reused
                # as causal CVD/warmup. The post-snapshot engine starts independently below.
                validation_engine = MicrostructureEngine(
                    source_session, LocalOrderBook.from_snapshot(SYMBOL, snapshot["event"]), config
                )
                subject = None
                for number, raw in enumerate(source, start=3):
                    record = read_record(raw, number)
                    if record.get("record_type") == "session_end":
                        break
                    if record.get("record_type") != "stream_event":
                        raise ValueError("Unexpected capture record type.")
                    received = record["received_at_ns"]
                    if type(received) is not int or received < start["started_at_ns"]:
                        raise ValueError("Invalid stream receipt time.")
                    if subject is None and received > available:
                        subject = MicrostructureEngine(source_session, book, config)
                    if record["stream"] == TRADE_STREAM:
                        trade = AggTrade.from_event(record["event"])
                        validation_engine.add_trade(trade, received_at_ns=received)
                        # Buffered trades must not seed CVD, warmup or attribution before the
                        # snapshot exists. Match CaptureReplay's equal-time exclusion as well.
                        if received > available:
                            subject.add_trade(trade, received_at_ns=received)
                    elif record["stream"] == DEPTH_STREAM:
                        update = DepthUpdate.from_event(record["event"])
                        validation_engine.apply_depth(update, received_at_ns=received)
                        if received <= available:
                            book.apply(update)  # Bridge the book only; never emit a feature.
                            continue
                        row = subject.apply_depth(update, received_at_ns=received)
                        if row is not None:
                            output.write(_line({"record_type": "observation", **asdict(row)}))
                            count += 1
                    else:
                        raise ValueError("Unexpected capture stream.")
            if not count:
                raise ValueError("Capture produced no microstructure observations.")
            if _sha256(capture_path) != checksum:
                raise ValueError("Capture changed during feature generation.")
            output.write(
                _line(
                    {
                        "record_type": "artifact_end",
                        "status": "complete",
                        "observation_count": count,
                        "source_sha256": checksum,
                    }
                )
            )
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary_path, output_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-session", required=True)
    parser.add_argument("--levels", type=int, default=5)
    parser.add_argument("--rolling-window-ms", type=int, default=10000)
    args = parser.parse_args()
    count = build_microstructure_dataset(
        args.capture,
        args.output,
        source_session=args.source_session,
        config=MicrostructureConfig(levels=args.levels, rolling_window_ms=args.rolling_window_ms),
    )
    print(f"Wrote {count} research-only observations to {args.output}")


if __name__ == "__main__":
    main()
