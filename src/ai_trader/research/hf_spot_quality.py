"""Bounded, source-qualified checks for the pinned Hugging Face spot samples.

This module reports data quality only. It never emits labels, fits a model, or
opens the project's reserved captures.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

RABBIT_FILES = {
    "binance.btc_20260818T1100.v2.jsonl.zst": (
        18_176_917,
        "fe94b425ac8812b88ebbc7ca8c53a55fc41cee4d97301fe7491d5cdcd43dfeb0",
    ),
    "bybit.btc_20260818T1100.v2.jsonl.zst": (
        6_761_135,
        "3b8e8e04503e2b5acacb51ffa1ed9c0f6be4e5ef7f44806c7a7d9b11e3e22a5a",
    ),
    "okx.btc_20260818T1100.v2.jsonl.zst": (
        8_148_277,
        "6beb97be07b8afa1993bd435e4017dc208582e0de59b06c384922625aef22b0c",
    ),
    "coinbase.btc_20260818T1100.v2.jsonl.zst": (
        5_240_999,
        "794eb803ffe8587dacb6a47627b1f2034a161a13d80f1e4139d31f876ad42ebb",
    ),
}
RABBIT_BAR = (
    "binance.btc_20260818T1100.v2.1s.parquet",
    1_463_659,
    "bec17747b029dc138e5bb3ed19bedcef8fb95c498da95c12dc42c927268da07e",
)
LOKIMA_FILES = {
    "binance_spot.parquet": (
        172_894_015,
        "1fcdc822d4208ec2df63a8f17db58dd51858d34c2bba78c5c9583e229b4e62bb",
    ),
    "binance_depth_snap.parquet": (
        1_184_533,
        "d8f7fd6a3a18bf3050d85b98598c609660f8c748ee2aab4b294a7516a5fdbfe3",
    ),
}


def _hash_and_size(path: Path, expected: tuple[int, str]) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    actual = digest.hexdigest()
    return {
        "bytes": size,
        "sha256": actual,
        "matches_pin": size == expected[0] and actual == expected[1],
    }


def _rabbit_line(line: bytes) -> tuple[int, str, Any]:
    parts = line.rstrip(b"\r\n").split(b"|", 2)
    if len(parts) != 3:
        raise ValueError("expected receive_us|channel|payload")
    receive_us = int(parts[0])
    channel = parts[1].decode("ascii")
    raw_payload = parts[2].strip()
    if raw_payload in {b"ping", b"pong"}:
        return receive_us, channel, None
    payload = json.loads(raw_payload)
    if not isinstance(payload, (dict, list)):
        raise ValueError("payload must be an object or array")
    return receive_us, channel, payload


def _audit_rabbit(path: Path) -> dict[str, Any]:
    import pyarrow as pa

    counts: Counter[str] = Counter()
    first_us: int | None = None
    last_us: int | None = None
    malformed = 0
    regressions = 0
    largest_regression_us = 0
    spot_snapshots = 0
    with io.BufferedReader(pa.input_stream(path), buffer_size=1024 * 1024) as stream:
        for line in stream:
            counts["lines"] += 1
            try:
                receive_us, channel, payload = _rabbit_line(line)
            except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
                malformed += 1
                continue
            if first_us is None:
                first_us = receive_us
            if last_us is not None and receive_us < last_us:
                regressions += 1
                largest_regression_us = max(largest_regression_us, last_us - receive_us)
                if last_us - receive_us > 1_000:
                    counts["arrival_regressions_gt_1ms"] += 1
                if last_us - receive_us > 10_000:
                    counts["arrival_regressions_gt_10ms"] += 1
            last_us = receive_us
            if ".spot." in channel:
                counts["spot_lines"] += 1
                if payload is None:
                    counts["spot_heartbeats"] += 1
                if isinstance(payload, dict):
                    marker = payload.get("type", payload.get("action"))
                    if marker == "snapshot":
                        spot_snapshots += 1
                    for event in payload.get("events", []):
                        if isinstance(event, dict) and event.get("type") == "snapshot":
                            spot_snapshots += 1
            elif ".perp." in channel:
                counts["perpetual_lines"] += 1
                if payload is None:
                    counts["perpetual_heartbeats"] += 1
            else:
                counts["unclassified_lines"] += 1
    return {
        **dict(counts),
        "first_receive_us": first_us,
        "last_receive_us": last_us,
        "malformed_lines": malformed,
        "arrival_regressions": regressions,
        "largest_arrival_regression_us": largest_regression_us,
        "explicit_spot_snapshot_messages": spot_snapshots,
    }


def _check_quote(data: dict[str, Any]) -> bool:
    try:
        bid = float(data["b"])
        ask = float(data["a"])
        bid_qty = float(data["B"])
        ask_qty = float(data["A"])
    except (KeyError, TypeError, ValueError):
        return False
    return 0 < bid < ask and bid_qty >= 0 and ask_qty >= 0


def _audit_lokima(path: Path, *, depth: bool) -> dict[str, Any]:
    import pyarrow.parquet as pq

    columns = [
        "venue",
        "channel",
        "stream_seq",
        "t_arrival_ns",
        "t_arrival_mono_ns",
        "payload_raw",
    ]
    if depth:
        columns.extend(["sym", "http_status"])
    parquet = pq.ParquetFile(path)
    counts: Counter[str] = Counter()
    first_ns: int | None = None
    last_ns: int | None = None
    last_mono: int | None = None
    previous_trade_id: dict[str, int] = {}
    first_unclassified_payload: dict[str, Any] | None = None
    for batch in parquet.iter_batches(batch_size=16_384, columns=columns):
        for row in batch.to_pylist():
            counts["rows"] += 1
            sequence = row["stream_seq"]
            if sequence != counts["rows"]:
                counts["stream_sequence_faults"] += 1
            receive_ns = row["t_arrival_ns"]
            mono_ns = row["t_arrival_mono_ns"]
            if first_ns is None:
                first_ns = receive_ns
            if last_ns is not None and receive_ns < last_ns:
                counts["arrival_regressions"] += 1
            if last_mono is not None and mono_ns < last_mono:
                counts["monotonic_regressions"] += 1
            last_ns = receive_ns
            last_mono = mono_ns
            if row["venue"] != "binance_spot":
                counts["wrong_venue"] += 1
            try:
                payload = json.loads(row["payload_raw"])
            except (TypeError, ValueError, json.JSONDecodeError):
                if row["channel"] != "spot_combined" and not row["payload_raw"]:
                    counts["control_rows"] += 1
                else:
                    counts["malformed_payloads"] += 1
                    if first_unclassified_payload is None:
                        first_unclassified_payload = {
                            "stream_sequence": sequence,
                            "channel": row["channel"],
                            "reason": "invalid_json",
                        }
                continue
            if depth:
                counts["missing_symbol_metadata"] += row["sym"] is None
                if row["http_status"] != 200:
                    counts["bad_http_status"] += 1
                try:
                    bid = float(payload["bids"][0][0])
                    ask = float(payload["asks"][0][0])
                    if not (0 < bid < ask and payload["lastUpdateId"] > 0):
                        counts["invalid_books"] += 1
                except (KeyError, IndexError, TypeError, ValueError):
                    counts["invalid_books"] += 1
                continue
            if row["channel"] != "spot_combined":
                counts["control_rows"] += 1
                continue
            if not isinstance(payload, dict):
                counts["malformed_payloads"] += 1
                continue
            stream_name = payload.get("stream", "")
            data = payload.get("data")
            if not isinstance(data, dict) or not isinstance(stream_name, str):
                if "result" in payload and "id" in payload:
                    counts["subscription_ack_rows"] += 1
                else:
                    counts["malformed_payloads"] += 1
                    if first_unclassified_payload is None:
                        first_unclassified_payload = {
                            "stream_sequence": sequence,
                            "keys": sorted(payload),
                        }
                continue
            symbol = stream_name.split("@", 1)[0].upper()
            event = stream_name.split("@", 1)[-1]
            if symbol not in {"BTCUSDT", "ETHUSDT"} or data.get("s") != symbol:
                counts["symbol_mismatches"] += 1
                continue
            counts[f"{symbol}_{event}"] += 1
            if event == "bookTicker" and not _check_quote(data):
                counts["invalid_quotes"] += 1
            if event == "trade":
                trade_id = data.get("t")
                if not isinstance(trade_id, int):
                    counts["invalid_trade_ids"] += 1
                    continue
                previous = previous_trade_id.get(symbol)
                if previous is not None:
                    if trade_id <= previous:
                        counts["trade_id_duplicates_or_regressions"] += 1
                    elif trade_id > previous + 1:
                        counts["trade_id_forward_gaps"] += 1
                        counts["trade_ids_missing_lower_bound"] += trade_id - previous - 1
                previous_trade_id[symbol] = trade_id
    return {
        **dict(counts),
        "footer_rows": parquet.metadata.num_rows,
        "first_arrival_ns": first_ns,
        "last_arrival_ns": last_ns,
        "first_unclassified_payload": first_unclassified_payload,
    }


def run_quality_audit(rabbit_dir: Path, lokima_dir: Path) -> dict[str, Any]:
    import pyarrow.parquet as pq

    rabbit: dict[str, Any] = {}
    lokima: dict[str, Any] = {}
    for name, pin in RABBIT_FILES.items():
        path = rabbit_dir / name
        integrity = _hash_and_size(path, pin)
        rabbit[name] = {
            "integrity": integrity,
            "scan": _audit_rabbit(path) if integrity["matches_pin"] else None,
        }
    name, size, sha256 = RABBIT_BAR
    path = rabbit_dir / name
    integrity = _hash_and_size(path, (size, sha256))
    rabbit[name] = {
        "integrity": integrity,
        "footer_rows": pq.ParquetFile(path).metadata.num_rows if integrity["matches_pin"] else None,
    }
    for name, pin in LOKIMA_FILES.items():
        path = lokima_dir / name
        integrity = _hash_and_size(path, pin)
        lokima[name] = {
            "integrity": integrity,
            "scan": _audit_lokima(path, depth=name == "binance_depth_snap.parquet")
            if integrity["matches_pin"]
            else None,
        }
    return {
        "schema_version": 1,
        "kind": "hf_spot_market_data_quality",
        "rabbit_revision": "613c7b692c0de1fde2ca7e69934a9cc566bc2b8e",
        "rabbit_bar_revision": "4b2b4d65368e15c11900ab6b36ebca4379c8bab6",
        "lokima_revision": "97d05eac7324a410db4dabb4f06b25cc21aae23f",
        "rabbit": rabbit,
        "lokima": lokima,
        "training_gate": {
            "eligible": False,
            "reasons": [
                "No preregistered whole-session train/validation/reserved roles for these sources.",
                "The later one-hour tape mixes spot and perpetual streams.",
                "The eight-hour feed lacks depth diffs; snapshots lack explicit symbols.",
                "No causal feature/label and costed evaluation contract exists for these formats.",
                "Qwen lacks protected evaluation and grounded targets from these files.",
            ],
        },
        "training_started": False,
        "model_promoted": False,
        "live_trading_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rabbit-directory", type=Path, required=True)
    parser.add_argument("--lokima-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    report = run_quality_audit(args.rabbit_directory, args.lokima_directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(args.output), "training_started": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
