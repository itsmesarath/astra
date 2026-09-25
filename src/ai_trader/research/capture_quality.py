"""Read-only quality audit of an explicitly selected capture and derived artifact.

The report uses the whole session. It is retrospective dataset QA, never an
as-of trading input or evidence of strategy profitability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, DecimalException
from pathlib import Path

from ai_trader.features.build_microstructure import SNAPSHOT_POLICY, snapshot_available_at_ns
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


def _hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def _read(stream) -> dict:
    # Bound one record, not the total session, to support streaming long captures.
    line = stream.readline(2_000_001)
    if not line or len(line) > 2_000_000:
        raise ValueError("Missing or oversized artifact record.")
    record = json.loads(line, object_pairs_hook=_pairs, parse_constant=_constant)
    if not isinstance(record, dict):
        raise ValueError("Artifact record must be an object.")
    return record


def _canonical(record) -> str:
    def encode(value):
        if isinstance(value, Decimal):
            return str(value)
        raise TypeError("Unexpected artifact value")

    return json.dumps(record, default=encode, sort_keys=True, allow_nan=False)


def _config(value) -> MicrostructureConfig:
    if not isinstance(value, dict):
        raise ValueError("Artifact config must be an object.")
    value = dict(value)
    for key in ("liquidity_band_bps", "retained_depth_fraction"):
        if not isinstance(value.get(key), str):
            raise ValueError("Config Decimal values must be strings.")
        try:
            value[key] = Decimal(value[key])
        except DecimalException as error:
            raise ValueError("Invalid config Decimal.") from error
    if set(value) != set(MicrostructureConfig.__dataclass_fields__):
        raise ValueError("Incomplete or unsupported artifact config.")
    config = MicrostructureConfig(**value)
    config.validate()
    return config


@dataclass(frozen=True, slots=True)
class CaptureQualityReport:
    source_session: str
    source_sha256: str
    artifact_sha256: str
    producer_code_matches_current: bool
    observations: int
    applied_depth_events: int
    stale_depth_events: int
    trade_events: int
    first_observation_received_at_ns: int
    last_observation_received_at_ns: int
    max_observation_gap_ns: int
    rolling_warmup_observations: int
    invalid_evidence_intervals: int
    incomplete_band_observations: int
    incomplete_top_n_observations: int
    usable_observations: int
    unmatched_trades: int
    pending_trades_at_last_observation: int
    trades_after_last_observation: int
    snapshot_received_at_ns: int
    snapshot_buffered_depth_updates: int
    snapshot_buffered_trade_events: int
    schema: str = "capture_quality_v2"
    scope: str = "retrospective_dataset_qa_only"
    integrity: str = "verified_against_source"


def assess_capture(capture: Path, artifact: Path) -> CaptureQualityReport:
    """Reject partial/mismatched/modified artifacts; do not modify or select any files.

    Reproduce each observation rather than trust stored coverage/quality flags. Usable
    means warmed rolling window, valid evidence interval and both-side band/top-N
    coverage, not adequate statistical samples or authorization to trade.
    """
    source_hash, artifact_hash = _hash(capture), _hash(artifact)
    validation = validate_capture(capture)
    count = warmup = invalid = band = top_n = usable = unmatched = pending = trailing = 0
    buffered_depth = buffered_trades = 0
    first = previous = None
    max_gap = 0
    with artifact.open(encoding="utf-8") as derived:
        header = _read(derived)
        required = {
            "record_type": "artifact_start",
            "schema_version": 2,
            "feature_schema": "receipt_causal_microstructure_v1",
            "snapshot_policy": SNAPSHOT_POLICY,
            "source_sha256": source_hash,
            "execution_mode": "research_only",
            "decimal_policy": "precision_28_round_half_even",
            "time_policy": "receipt_order_rolling_window_left_open_right_closed",
            "matching_policy": "previous_depth_event_time_lt_trade_time_le_current_depth",
            "cvd_policy": "post_snapshot_aggregate_taker_buy_minus_sell_session_reset",
            "evidence_policy": "best_price_net_addition_and_retained_depth_proxies",
        }
        for key, expected in required.items():
            if _canonical(header.get(key)) != _canonical(expected):
                raise ValueError(f"Artifact header mismatch: {key}")
        manifest = header.get("implementation_sha256")
        if (
            not isinstance(manifest, dict)
            or not manifest
            or any(
                not isinstance(key, str)
                or not isinstance(value, str)
                or re.fullmatch(r"[0-9a-f]{64}", value) is None
                for key, value in manifest.items()
            )
        ):
            raise ValueError("Missing or invalid implementation manifest.")
        package_root = Path(__file__).resolve().parents[1]
        current_manifest = {
            path.relative_to(package_root).as_posix(): _hash(path)
            for path in sorted(package_root.rglob("*.py"))
        }
        session = header.get("source_session")
        if not isinstance(session, str) or not session.strip():
            raise ValueError("Artifact source session is missing.")
        config = _config(header.get("config"))
        with capture.open(encoding="utf-8") as raw:
            start = read_record(next(raw), 1)
            snapshot = read_record(next(raw), 2)
            available = snapshot_available_at_ns(start, snapshot)
            if _canonical(header.get("snapshot_received_at_ns")) != _canonical(available):
                raise ValueError("Artifact snapshot availability differs from capture.")
            book = LocalOrderBook.from_snapshot(SYMBOL, snapshot["event"])
            validation_engine = MicrostructureEngine(
                session, LocalOrderBook.from_snapshot(SYMBOL, snapshot["event"]), config
            )
            engine = None
            for number, line in enumerate(raw, 3):
                record = read_record(line, number)
                if record["record_type"] == "session_end":
                    break
                received = record["received_at_ns"]
                if type(received) is not int or received < start["started_at_ns"]:
                    raise ValueError("Invalid stream receipt time.")
                if engine is None and received > available:
                    engine = MicrostructureEngine(session, book, config)
                if record["stream"] == TRADE_STREAM:
                    trade = AggTrade.from_event(record["event"])
                    validation_engine.add_trade(trade, received_at_ns=received)
                    if received <= available:
                        buffered_trades += 1
                        continue
                    engine.add_trade(trade, received_at_ns=received)
                    trailing += 1
                    continue
                if record["stream"] != DEPTH_STREAM:
                    raise ValueError("Unexpected stream.")
                update = DepthUpdate.from_event(record["event"])
                validation_engine.apply_depth(update, received_at_ns=received)
                if received <= available:
                    buffered_depth += book.apply(update)
                    continue
                observation = engine.apply_depth(update, received_at_ns=received)
                if observation is None:
                    continue
                expected = {"record_type": "observation", **asdict(observation)}
                if _canonical(_read(derived)) != _canonical(expected):
                    raise ValueError(f"Observation {count + 1} does not reproduce from capture.")
                count += 1
                first = received if first is None else first
                max_gap = max(max_gap, 0 if previous is None else received - previous)
                previous = received
                warmup += not observation.rolling_window_complete
                invalid += not observation.evidence_interval_valid
                has_band = observation.bid_band_covered and observation.ask_band_covered
                has_top = observation.bid_top_n_covered and observation.ask_top_n_covered
                band += not has_band
                top_n += not has_top
                usable += bool(
                    observation.rolling_window_complete
                    and observation.evidence_interval_valid
                    and has_band
                    and has_top
                )
                unmatched += observation.unmatched_trade_count
                pending = observation.pending_trade_count
                trailing = 0
        expected_footer = {
            "record_type": "artifact_end",
            "status": "complete",
            "observation_count": count,
            "source_sha256": source_hash,
        }
        if _canonical(_read(derived)) != _canonical(expected_footer) or derived.read(1):
            raise ValueError("Invalid footer or trailing artifact data.")
    if not count or count + buffered_depth != validation.applied_depth_events:
        raise ValueError("Artifact observation count does not match capture.")
    if _hash(capture) != source_hash or _hash(artifact) != artifact_hash:
        raise ValueError("Input changed during quality assessment.")
    return CaptureQualityReport(
        session,
        source_hash,
        artifact_hash,
        manifest == current_manifest,
        count,
        validation.applied_depth_events,
        validation.stale_depth_events,
        validation.trade_events,
        first,
        previous,
        max_gap,
        warmup,
        invalid,
        band,
        top_n,
        usable,
        unmatched,
        pending,
        trailing,
        available,
        buffered_depth,
        buffered_trades,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    try:
        report = assess_capture(args.capture, args.artifact)
    except (ValueError, TypeError, OSError, KeyError, StopIteration, DecimalException) as error:
        print(json.dumps({"status": "REJECTED", "reason": str(error)}))
        raise SystemExit(2) from error
    print(json.dumps(asdict(report), indent=2))


if __name__ == "__main__":
    main()
