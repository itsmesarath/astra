"""Receipt-causal, session-local counterfactual labels; no fitting or execution.

Every emitted frame is retained. Only completed, costed outcomes have numeric
targets. A session boundary, unhealthy quote or processing cutoff never invents
a flat outcome, and strategy signal thresholds never select the examples.
"""

import argparse
import json
import os
import warnings
from collections import Counter
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from itertools import islice
from pathlib import Path

from ai_trader.research.microstructure_trial import _environment, load_registration
from ai_trader.trading.capture_replay import CaptureReplay, ReplayFrame, _implementation_hash
from ai_trader.trading.microstructure_policy import (
    DECIMAL_CONTEXT as OBSERVATION_CONTEXT,
)
from ai_trader.trading.microstructure_policy import _validate_observation
from ai_trader.trading.paper_lifecycle import _timestamp
from ai_trader.trading.trade_journal import _hash

LABEL_VERSION = "receipt_causal_spot_barriers_v1"
MAX_PENDING = 2000
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
DECIMAL_CONTEXT = Context(prec=100, rounding=ROUND_HALF_EVEN)
BPS = Decimal(10000)
FEATURE_SCHEMA_VERSION = "receipt_microstructure_features_v1"
FEATURE_UNITS = {
    "spread_bps": "bps_relative_to_bid",
    "book_imbalance": "fraction",
    "microprice_offset_bps": "bps_relative_to_midpoint",
    "bid_depth_btc": "BTC",
    "ask_depth_btc": "BTC",
    "rolling_buy_btc": "BTC",
    "rolling_sell_btc": "BTC",
    "rolling_cvd_btc": "BTC",
    "rolling_trade_count": "count",
    "ofi_btc": "BTC",
    "bid_band_depth_btc": "BTC",
    "ask_band_depth_btc": "BTC",
    "rolling_window_complete": "boolean",
    "evidence_interval_valid": "boolean",
    "bid_band_covered": "boolean",
    "ask_band_covered": "boolean",
    "bid_top_n_covered": "boolean",
    "ask_top_n_covered": "boolean",
    "unmatched_trade_count": "count",
    "pending_trade_count": "count",
    **{
        f"{side}_{name}": unit
        for side in ("bid", "ask")
        for name, unit in (
            ("aggressive_btc", "BTC"),
            ("replenishment_proxy_btc", "BTC"),
            ("absorption_candidate", "boolean"),
            ("replenishment_intervals", "count"),
            ("repeated_replenishment_candidate", "boolean"),
        )
    },
}


def _json(value):
    return json.dumps(value, sort_keys=True, default=str, allow_nan=False)


def _protocol(registration):
    p, g = registration.policy, registration.gateway
    return {
        "version": LABEL_VERSION,
        "sampling": "all_ready_unambiguous_depth_observations_not_strategy_signals",
        "entry": "first_healthy_depth_strictly_after_feature_before_exclusive_ttl",
        "brackets": "feature_bid_anchored_stop_then_target_then_horizon",
        "exit": "later_healthy_depth_at_actual_bid_less_slippage",
        "horizon": "from_entry_receipt_not_feature_time",
        "quality": "censor_on_first_fault_stale_quote_or_excessive_interquote_gap",
        "boundaries": "never_cross_source_session_or_processing_prefix",
        "target": "sign_of_net_unit_long_return_resolved_only",
        "entry_ttl_ns": p.entry_ttl_ns,
        "maximum_hold_ns": p.maximum_hold_ns,
        "stop_distance_bps": str(p.stop_distance_bps),
        "target_distance_bps": str(p.target_distance_bps),
        "maximum_spread_bps": str(p.maximum_spread_bps),
        "maximum_trade_age_ns": p.maximum_trade_age_ns,
        "maximum_quote_age_ns": g.max_quote_age_ns,
        "taker_fee_bps": str(g.costs.taker_fee_bps),
        "slippage_bps": str(g.costs.slippage_bps),
    }


def _features(row):
    """Model-input allowlist: no future outcomes, policy actions or portfolio state."""
    book = row.book
    result = {
        "spread_bps": book.spread * BPS / book.best_bid_price,
        "book_imbalance": book.imbalance,
        "microprice_offset_bps": (book.microprice - book.midpoint) * BPS / book.midpoint,
        "bid_depth_btc": book.bid_depth,
        "ask_depth_btc": book.ask_depth,
        "rolling_buy_btc": row.rolling_buy_base,
        "rolling_sell_btc": row.rolling_sell_base,
        "rolling_cvd_btc": row.rolling_cvd_base,
        "rolling_trade_count": row.rolling_trade_count,
        "ofi_btc": row.top_level_order_flow_imbalance,
        "bid_band_depth_btc": row.bid_band_depth,
        "ask_band_depth_btc": row.ask_band_depth,
        "rolling_window_complete": row.rolling_window_complete,
        "evidence_interval_valid": row.evidence_interval_valid,
        "bid_band_covered": row.bid_band_covered,
        "ask_band_covered": row.ask_band_covered,
        "bid_top_n_covered": row.bid_top_n_covered,
        "ask_top_n_covered": row.ask_top_n_covered,
        "unmatched_trade_count": row.unmatched_trade_count,
        "pending_trade_count": row.pending_trade_count,
    }
    for name in ("bid", "ask"):
        side = getattr(row, name)
        for field, suffix in (
            ("aggressive_volume_at_price", "aggressive_btc"),
            ("net_addition_proxy", "replenishment_proxy_btc"),
            ("absorption_candidate", "absorption_candidate"),
            ("consecutive_replenishment_intervals", "replenishment_intervals"),
            ("repeated_replenishment_candidate", "repeated_replenishment_candidate"),
        ):
            result[name + "_" + suffix] = None if side is None else getattr(side, field)
    if result.keys() != FEATURE_UNITS.keys():
        raise ValueError("Feature schema and extraction disagree.")
    return result


def _eligibility(frame, policy, gateway):
    tick, row = frame.tick, frame.observation
    if row is None:
        return "no_new_depth_observation"
    if not tick.book_synchronized:
        return "book_unsynchronized"
    if tick.observed_at_ns - tick.quote_received_at_ns > gateway.max_quote_age_ns:
        return "stale_quote"
    if not tick.features_ready or not all(
        (
            row.rolling_window_complete,
            row.evidence_interval_valid,
            row.bid_band_covered,
            row.ask_band_covered,
            row.bid_top_n_covered,
            row.ask_top_n_covered,
        )
    ):
        return "microstructure_not_ready"
    if row.unmatched_trade_count or row.pending_trade_count:
        return "ambiguous_trade_attribution"
    if tick.last_trade_received_at_ns is None or (
        tick.observed_at_ns - tick.last_trade_received_at_ns > policy.maximum_trade_age_ns
    ):
        return "stale_trades"
    if row.book.spread * BPS / row.book.best_bid_price > policy.maximum_spread_bps:
        return "spread_limit"
    return "eligible"


def _outcome(status, reason, known_at_ns):
    return {
        "status": status,
        "reason": reason,
        "known_at_ns": known_at_ns,
        "entry_at_ns": None,
        "entry_price_usdt": None,
        "horizon_at_ns": None,
        "exit_at_ns": None,
        "exit_price_usdt": None,
        "net_return_fraction": None,
        "direction": None,
    }


@dataclass(slots=True)
class _Pending:
    row: dict
    entry_deadline: int
    stop: Decimal
    target: Decimal

    def advance(self, frame, *, fault, policy, gateway):
        outcome, tick = self.row["outcome"], frame.tick
        now = tick.observed_at_ns
        if fault:
            outcome.update(status="censored", reason=fault, known_at_ns=now)
            return True
        if outcome["entry_at_ns"] is None and now >= self.entry_deadline:
            outcome.update(status="not_entered", reason="entry_expired", known_at_ns=now)
            return True
        after = outcome["entry_at_ns"]
        if after is None:
            after = self.row["feature_available_at_ns"]
        if frame.observation is None or now <= after:
            return False  # Trade-only or equal-receipt-time records cannot supply a future quote.
        slip = gateway.costs.slippage_bps / BPS
        fee = gateway.costs.taker_fee_bps / BPS
        if outcome["entry_at_ns"] is None:
            entry = tick.ask_usdt * (1 + slip)
            reason = None
            if tick.bid_usdt <= self.stop or entry >= self.target:
                reason = "entry_outside_bracket"
            elif (tick.ask_usdt - tick.bid_usdt) * BPS / tick.bid_usdt > policy.maximum_spread_bps:
                reason = "entry_spread_limit"
            if reason:
                outcome.update(status="not_entered", reason=reason, known_at_ns=now)
                return True
            horizon = now + policy.maximum_hold_ns
            _timestamp(horizon)
            outcome.update(entry_at_ns=now, entry_price_usdt=entry, horizon_at_ns=horizon)
            return False
        reason = (
            "stop"
            if tick.bid_usdt <= self.stop
            else "target"
            if tick.bid_usdt >= self.target
            else "horizon"
            if now >= outcome["horizon_at_ns"]
            else None
        )
        if reason is None:
            return False
        exit_price = tick.bid_usdt * (1 - slip)
        debit = outcome["entry_price_usdt"] * (1 + fee)
        net_return = (exit_price * (1 - fee) - debit) / debit
        outcome.update(
            status="resolved",
            reason=reason,
            known_at_ns=now,
            exit_at_ns=now,
            exit_price_usdt=exit_price,
            net_return_fraction=net_return,
            direction=1 if net_return > 0 else -1 if net_return < 0 else 0,
        )
        return True


def _label_replay(replay, registration, max_frames):
    policy, gateway = registration.policy, registration.gateway
    examples, pending, seen = [], [], set()
    prior_time, prior_line, last_quote = -1, 0, None
    record_count = replay.record_count
    for frame in islice(replay.frames(), max_frames):
        if type(frame) is not ReplayFrame:
            raise ValueError("Expected typed replay frame.")
        tick = frame.tick
        if (
            tick.source_session != replay.source_session
            or tick.tick_id in seen
            or tick.observed_at_ns < prior_time
            or frame.line_number <= prior_line
        ):
            raise ValueError("Label input must be one ordered, nonduplicated source session.")
        seen.add(tick.tick_id)
        prior_time, prior_line = tick.observed_at_ns, frame.line_number
        if frame.observation is not None:
            if frame.status != "observation":
                raise ValueError("Depth features must belong to a new depth observation.")
            with localcontext(OBSERVATION_CONTEXT):
                _validate_observation(frame.observation, tick, registration.replay.features)
        fault = None
        if frame.line_number == record_count:
            fault = "session_end"
        elif frame.status.startswith("resync_required:") or not tick.book_synchronized:
            fault = "market_fault"
        elif tick.observed_at_ns - tick.quote_received_at_ns > gateway.max_quote_age_ns:
            fault = "stale_quote"
        elif last_quote is not None and tick.observed_at_ns - last_quote > gateway.max_quote_age_ns:
            fault = "interquote_gap"
        pending = [
            p for p in pending if not p.advance(frame, fault=fault, policy=policy, gateway=gateway)
        ]
        if frame.observation is not None and tick.book_synchronized:
            last_quote = tick.quote_received_at_ns
        eligibility = _eligibility(frame, policy, gateway)
        features = None if frame.observation is None else _features(frame.observation)
        row = {
            "example_id": _hash(LABEL_VERSION + ":" + registration.sha256 + ":" + tick.tick_id),
            "source_session": replay.source_session,
            "source_line": frame.line_number,
            "tick_id": tick.tick_id,
            "feature_available_at_ns": tick.observed_at_ns,
            "observation_sha256": tick.observation_sha256,
            "frame_status": frame.status,
            "features": features,
            "features_sha256": _hash(_json(features)),
            "eligibility_reason": eligibility,
            "outcome": _outcome("excluded", eligibility, tick.observed_at_ns),
        }
        examples.append(row)
        if eligibility == "eligible":
            if len(pending) >= MAX_PENDING:
                raise ValueError("Pending-label budget exceeded; no dataset may be published.")
            deadline = tick.observed_at_ns + policy.entry_ttl_ns
            _timestamp(deadline)
            row["outcome"] = _outcome("pending", "awaiting_future_quote", None)
            pending.append(
                _Pending(
                    row,
                    deadline,
                    tick.bid_usdt * (1 - policy.stop_distance_bps / BPS),
                    tick.bid_usdt * (1 + policy.target_distance_bps / BPS),
                )
            )
    if not examples:
        raise ValueError("Cannot label an empty replay.")
    for p in pending:
        p.row["outcome"].update(
            status="censored", reason="processing_cutoff", known_at_ns=prior_time
        )
    return examples, prior_line == record_count


def _publish(dataset, output_path, *, payload_name="dataset", max_bytes=None):
    """Publish a complete checksum envelope exclusively; failed staging stays quarantined."""
    if payload_name not in ("dataset", "manifest", "report"):
        raise ValueError("Unsupported artifact envelope.")
    output_path = Path(output_path)
    payload = _json(dataset)
    raw = (_json({payload_name + "_sha256": _hash(payload), payload_name: dataset}) + "\n").encode()
    if len(raw) > (MAX_ARTIFACT_BYTES if max_bytes is None else max_bytes):
        raise ValueError("Event dataset exceeds artifact byte budget.")
    if output_path.exists():
        raise FileExistsError(output_path)
    staging = output_path.with_name(output_path.name + ".partial")
    with staging.open("xb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    os.link(staging, output_path)  # Atomic publication, never replaces an existing destination.
    try:
        staging.unlink()
    except OSError:
        warnings.warn(f"Published dataset; staging file retained at {staging}", stacklevel=2)


def _build_dataset(registration, replay, max_frames):
    """Shared deterministic derivation from already pinned bytes, never a second file read."""
    source = registration.research_source(replay.source_session)
    if source.source_sha256 != replay.source_sha256 or replay.config != registration.replay:
        raise ValueError("Replay does not match the registered source/configuration.")
    framing = replay._framing()
    if (framing[0]["started_at_ns"], framing[-1]["ended_at_ns"]) != (
        source.started_at_ns,
        source.ended_at_ns,
    ):
        raise ValueError("Capture times differ from registration.")
    with localcontext(DECIMAL_CONTEXT):
        examples, complete = _label_replay(replay, registration, max_frames)
    if (
        registration.implementation_sha256 != _implementation_hash()
        or registration.environment_json != _environment()
    ):
        raise ValueError("Source/environment changed during labeling; nothing published.")
    protocol = _protocol(registration)
    dataset = json.loads(
        _json(
            {
                "schema_version": 1,
                "artifact_type": "microstructure_event_labels",
                "label_version": LABEL_VERSION,
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "feature_units": FEATURE_UNITS,
                "registration_sha256": registration.sha256,
                "implementation_sha256": registration.implementation_sha256,
                "environment_json": registration.environment_json,
                "source_session": source.source_session,
                "source_sha256": source.source_sha256,
                "source_started_at_ns": source.started_at_ns,
                "source_ended_at_ns": source.ended_at_ns,
                "protocol": protocol,
                "protocol_sha256": _hash(_json(protocol)),
                "max_frames": max_frames,
                "frames_processed": len(examples),
                "session_consumed": complete,
                "market_fault_frames": sum(
                    r["frame_status"].startswith("resync_required:") for r in examples
                ),
                "outcome_counts": dict(Counter(r["outcome"]["status"] for r in examples)),
                "outcome_reason_counts": dict(Counter(r["outcome"]["reason"] for r in examples)),
                "examples": examples,
                "mode": "research_only",
                "promotion_allowed": False,
                "training_started": False,
                "live_trading_available": False,
                "limitation": (
                    "Overlapping unit-long sampled-quote counterfactuals, not portfolio trades. "
                    "Unknown outcomes are not neutral labels. "
                    "No depth/queue/impact/latency fill model. "
                    "Features alone are model inputs; "
                    "outcome/provenance fields must never be inputs. "
                    "Legacy candle/depth model loaders do not accept this artifact."
                ),
            }
        )
    )
    return dataset


def build_registered_event_dataset(
    *,
    registration_path: Path,
    capture_path: Path,
    source_session: str,
    max_frames: int,
    output_path: Path | None = None,
) -> dict:
    """Label one explicit research source. Does not open any journal or reserved source."""
    if type(max_frames) is not int or not 1 <= max_frames <= 10_000:
        raise ValueError("Frame budget must be an integer in [1, 10000].")
    registration = load_registration(registration_path)
    source = registration.research_source(source_session)  # Before capture or output IO.
    replay = CaptureReplay.from_path(
        capture_path,
        expected_sha256=source.source_sha256,
        source_session=source_session,
        config=registration.replay,
    )
    dataset = _build_dataset(registration, replay, max_frames)
    if output_path is not None:
        _publish(dataset, output_path)
    return dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--source-session", required=True)
    parser.add_argument("--max-frames", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dataset = build_registered_event_dataset(
        registration_path=args.registration,
        capture_path=args.capture,
        source_session=args.source_session,
        max_frames=args.max_frames,
        output_path=args.output,
    )
    print(json.dumps({k: v for k, v in dataset.items() if k != "examples"}, sort_keys=True))
    if not dataset["session_consumed"] or dataset["market_fault_frames"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
