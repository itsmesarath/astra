"""Predeclared, research-only BTCUSDT flow-pressure diagnostics.

This candidate deliberately has no order, sizing, PnL, model or promotion path.
It can be frozen before collecting new whole-session train/validation sources.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import warnings
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ai_trader.research.microstructure_trial import _decode_replay, _environment
from ai_trader.trading.capture_replay import (
    CaptureReplay,
    CaptureReplayConfig,
    ReplayFrame,
    _implementation_hash,
)
from ai_trader.trading.microstructure_policy import _validate_observation
from ai_trader.trading.paper_lifecycle import _money, _timestamp
from ai_trader.trading.trade_journal import _constant, _identifier, _pairs

VERSION = "flow_pressure_diagnostic_v1"
MAX_PLAN_BYTES = 100_000
MAX_REPORT_BYTES = 1_000_000
MAX_TOTAL_FRAMES = 10_000
MAX_INPUT_BYTES = 64 * 1024 * 1024
BPS = Decimal(10_000)


def _json(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path, limit: int) -> dict:
    with path.open("rb") as source:
        raw = source.read(limit + 1)
    if not raw or len(raw) > limit:
        raise ValueError("Empty or oversized research artifact.")
    value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    if not isinstance(value, dict):
        raise ValueError("Research artifact must be an object.")
    return value


def _write_new(path: Path, value: dict, limit: int) -> str:
    raw = _json(value)
    if len(raw) > limit:
        raise ValueError("Research artifact exceeds its byte budget.")
    staging = path.with_name(path.name + ".partial")
    if path.exists():
        raise FileExistsError(path)
    with staging.open("xb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    os.link(staging, path)
    try:
        staging.unlink()
    except OSError:
        warnings.warn(f"Published research artifact; staging retained at {staging}", stacklevel=2)
    return _sha(raw)


@dataclass(frozen=True, slots=True)
class FlowPressureConfig:
    minimum_cvd_btc: Decimal
    minimum_ofi_btc: Decimal
    minimum_book_imbalance: Decimal
    minimum_bid_ask_liquidity_ratio: Decimal
    maximum_spread_bps: Decimal
    maximum_trade_age_ns: int
    maximum_quote_age_ns: int

    def __post_init__(self):
        for name in (
            "minimum_cvd_btc",
            "minimum_ofi_btc",
            "minimum_book_imbalance",
            "minimum_bid_ask_liquidity_ratio",
            "maximum_spread_bps",
        ):
            value = getattr(self, name)
            _money(value)
            if value <= 0:
                raise ValueError("Flow thresholds must be positive finite Decimals.")
        if self.minimum_book_imbalance >= 1:
            raise ValueError("Book imbalance must be below one.")
        if self.minimum_bid_ask_liquidity_ratio < 1 or self.maximum_spread_bps >= BPS:
            raise ValueError("Liquidity ratio or spread bound invalid.")
        for value in (self.maximum_trade_age_ns, self.maximum_quote_age_ns):
            _timestamp(value)
            if value <= 0:
                raise ValueError("Age bounds must be positive.")


@dataclass(frozen=True, slots=True)
class FlowPressureResult:
    qualifies: bool
    reason: str
    bid_absorption_observed: bool
    bid_replenishment_observed: bool


def assess_flow_pressure(frame, *, candidate: FlowPressureConfig, replay: CaptureReplayConfig):
    """Inspect one receipt-causal frame, producing no trade intent or future label."""
    if type(frame) is not ReplayFrame or type(candidate) is not FlowPressureConfig:
        raise ValueError("Typed frame and flow-pressure candidate required.")
    if type(replay) is not CaptureReplayConfig:
        raise ValueError("Typed replay configuration required.")
    tick, row = frame.tick, frame.observation
    if row is not None:
        _validate_observation(row, tick, replay.features)
    support = FlowPressureResult(
        False,
        "",
        bool(row is not None and row.bid is not None and row.bid.absorption_candidate),
        bool(row is not None and row.bid is not None and row.bid.repeated_replenishment_candidate),
    )
    if not tick.book_synchronized:
        reason = "book_unsynchronized"
    elif row is None or frame.status != "observation":
        reason = "no_new_depth_observation"
    elif tick.observed_at_ns - tick.quote_received_at_ns > candidate.maximum_quote_age_ns:
        reason = "stale_quote"
    elif (
        tick.last_trade_received_at_ns is None
        or tick.observed_at_ns - tick.last_trade_received_at_ns > candidate.maximum_trade_age_ns
    ):
        reason = "stale_trades"
    elif not (
        tick.features_ready
        and row.rolling_window_complete
        and row.evidence_interval_valid
        and row.bid_band_covered
        and row.ask_band_covered
        and row.bid_top_n_covered
        and row.ask_top_n_covered
    ):
        reason = "microstructure_not_ready"
    elif row.unmatched_trade_count or row.pending_trade_count:
        reason = "ambiguous_trade_attribution"
    elif row.book.spread * BPS / row.book.best_bid_price > candidate.maximum_spread_bps:
        reason = "spread_limit"
    elif row.ask is not None and row.ask.absorption_candidate:
        reason = "opposing_ask_absorption"
    elif row.rolling_cvd_base < candidate.minimum_cvd_btc:
        reason = "cvd_below_threshold"
    elif (
        row.top_level_order_flow_imbalance is None
        or row.top_level_order_flow_imbalance < candidate.minimum_ofi_btc
    ):
        reason = "ofi_below_threshold"
    elif row.book.imbalance < candidate.minimum_book_imbalance:
        reason = "book_imbalance_below_threshold"
    elif (
        row.ask_band_depth <= 0
        or row.bid_band_depth < row.ask_band_depth * candidate.minimum_bid_ask_liquidity_ratio
    ):
        reason = "bid_liquidity_below_threshold"
    else:
        reason = "diagnostic_signal_only"
    return FlowPressureResult(
        reason == "diagnostic_signal_only",
        reason,
        support.bid_absorption_observed,
        support.bid_replenishment_observed,
    )


def _candidate(value: dict) -> FlowPressureConfig:
    names = set(FlowPressureConfig.__dataclass_fields__)
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError("Exact flow-pressure candidate fields required.")
    decimals = names - {"maximum_trade_age_ns", "maximum_quote_age_ns"}
    if any(type(value[name]) is not str for name in decimals):
        raise ValueError("Decimal thresholds must be strings.")
    return FlowPressureConfig(
        **{name: Decimal(value[name]) for name in decimals},
        maximum_trade_age_ns=value["maximum_trade_age_ns"],
        maximum_quote_age_ns=value["maximum_quote_age_ns"],
    )


def _roles(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list) or not 3 <= len(value) <= 32:
        raise ValueError("Declare 3-32 whole source sessions.")
    roles = []
    for row in value:
        if not isinstance(row, dict) or set(row) != {"source_session", "role"}:
            raise ValueError("Invalid source-role declaration.")
        session, role = row["source_session"], row["role"]
        _identifier(session)
        if role not in ("train", "validation", "reserved"):
            raise ValueError("Unknown source role.")
        roles.append((session, role))
    if len({session for session, _ in roles}) != len(roles):
        raise ValueError("Duplicate source session.")
    phases = {"train": 0, "validation": 1, "reserved": 2}
    values = [phases[role] for _, role in roles]
    if set(values) != {0, 1, 2} or values != sorted(values):
        raise ValueError("Require chronological train, validation, reserved groups.")
    return tuple(roles)


def register_flow_pressure(settings_path: Path, output_path: Path) -> dict:
    settings = _read(Path(settings_path), MAX_PLAN_BYTES)
    if set(settings) != {"trial_id", "sources", "candidate", "replay", "max_total_frames"}:
        raise ValueError("Invalid flow-pressure settings.")
    _identifier(settings["trial_id"])
    roles = _roles(settings["sources"])
    candidate = _candidate(settings["candidate"])
    replay = _decode_replay(settings["replay"])
    budget = settings["max_total_frames"]
    if type(budget) is not int or not 1 <= budget <= MAX_TOTAL_FRAMES:
        raise ValueError("Invalid total frame budget.")
    plan = {
        "version": VERSION,
        "trial_id": settings["trial_id"],
        "registered_at_ns": time.time_ns(),
        "sources": [{"source_session": s, "role": r} for s, r in roles],
        "candidate": {
            name: getattr(candidate, name)
            if name in ("maximum_trade_age_ns", "maximum_quote_age_ns")
            else str(getattr(candidate, name))
            for name in FlowPressureConfig.__dataclass_fields__
        },
        "replay": settings["replay"],
        "max_total_frames": budget,
        "implementation_sha256": _implementation_hash(),
        "environment_json": _environment(),
        "mode": "research_only",
        "orders_enabled": False,
        "model_training_enabled": False,
        "promotion_allowed": False,
    }
    # Validate the accepted replay object before writing a binding to its source representation.
    if type(replay) is not CaptureReplayConfig:
        raise ValueError("Invalid replay configuration.")
    digest = _sha(_json(plan))
    _write_new(Path(output_path), {"plan": plan, "plan_sha256": digest}, MAX_PLAN_BYTES)
    return {"plan_sha256": digest, "source_count": len(roles), "mode": "research_only"}


def _load_plan(path: Path) -> dict:
    value = _read(Path(path), MAX_PLAN_BYTES)
    if set(value) != {"plan", "plan_sha256"} or not isinstance(value["plan"], dict):
        raise ValueError("Invalid flow-pressure plan envelope.")
    plan = value["plan"]
    if _sha(_json(plan)) != value["plan_sha256"]:
        raise ValueError("Flow-pressure plan checksum mismatch.")
    if set(plan) != {
        "version",
        "trial_id",
        "registered_at_ns",
        "sources",
        "candidate",
        "replay",
        "max_total_frames",
        "implementation_sha256",
        "environment_json",
        "mode",
        "orders_enabled",
        "model_training_enabled",
        "promotion_allowed",
    }:
        raise ValueError("Invalid flow-pressure plan fields.")
    if (
        plan["version"] != VERSION
        or plan["mode"] != "research_only"
        or any(
            plan[key] is not False
            for key in ("orders_enabled", "model_training_enabled", "promotion_allowed")
        )
        or plan["implementation_sha256"] != _implementation_hash()
        or plan["environment_json"] != _environment()
    ):
        raise ValueError("Plan authority, source or environment changed.")
    _identifier(plan["trial_id"])
    _timestamp(plan["registered_at_ns"])
    _roles(plan["sources"])
    _candidate(plan["candidate"])
    _decode_replay(plan["replay"])
    budget = plan["max_total_frames"]
    if type(budget) is not int or not 1 <= budget <= MAX_TOTAL_FRAMES:
        raise ValueError("Invalid plan frame budget.")
    return value


def evaluate_flow_pressure(
    plan_path: Path,
    sources: tuple[tuple[str, Path, str], ...],
    output_path: Path,
) -> dict:
    """Replay all declared research sources, never opening a reserved source."""
    envelope = _load_plan(plan_path)
    plan = envelope["plan"]
    declared = [(r["source_session"], r["role"]) for r in plan["sources"]]
    research = [session for session, role in declared if role != "reserved"]
    if (
        type(sources) is not tuple
        or any(type(item) is not tuple or len(item) != 3 for item in sources)
        or [item[0] for item in sources] != research
    ):
        raise ValueError("Supply every train/validation source exactly once; no reserved source.")
    candidate = _candidate(plan["candidate"])
    replay_config = _decode_replay(plan["replay"])
    counts, used_bytes, seen_hashes, previous_end, reports = 0, 0, set(), None, []
    for session, path, digest in sources:
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
            or digest in seen_hashes
        ):
            raise ValueError("Supply distinct lowercase source SHA256 pins.")
        seen_hashes.add(digest)
        size = Path(path).stat().st_size
        used_bytes += size
        if size <= 0 or used_bytes > MAX_INPUT_BYTES:
            raise ValueError("Whole research inventory exceeds its capture-byte budget.")
        replay = CaptureReplay.from_path(
            Path(path), expected_sha256=digest, source_session=session, config=replay_config
        )
        framing = replay._framing()
        start, end = framing[0]["started_at_ns"], framing[-1]["ended_at_ns"]
        if start <= plan["registered_at_ns"]:
            raise ValueError("Capture predates the frozen flow-pressure plan.")
        if previous_end is not None and start <= previous_end:
            raise ValueError("Source sessions overlap or are reordered.")
        previous_end = end
        reasons, qualified, faults, absorption, replenishment, frames = Counter(), 0, 0, 0, 0, 0
        for frame in replay.frames():
            counts += 1
            frames += 1
            if counts > plan["max_total_frames"]:
                raise ValueError("Whole research inventory exceeds the frozen frame budget.")
            result = assess_flow_pressure(frame, candidate=candidate, replay=replay_config)
            reasons[result.reason] += 1
            qualified += result.qualifies
            absorption += result.bid_absorption_observed
            replenishment += result.bid_replenishment_observed
            faults += frame.status.startswith("resync_required:")
        reports.append(
            {
                "source_session": session,
                "role": next(role for name, role in declared if name == session),
                "source_sha256": digest,
                "started_at_ns": start,
                "ended_at_ns": end,
                "frames": frames,
                "market_fault_frames": faults,
                "qualified_diagnostic_frames": qualified,
                "bid_absorption_observed_frames": absorption,
                "bid_replenishment_observed_frames": replenishment,
                "reason_counts": dict(reasons),
            }
        )
    if (
        plan["implementation_sha256"] != _implementation_hash()
        or plan["environment_json"] != _environment()
    ):
        raise ValueError("Source or environment changed during evaluation.")
    report = {
        "version": VERSION,
        "plan_sha256": envelope["plan_sha256"],
        "status": "complete"
        if all(not row["market_fault_frames"] for row in reports)
        else "market_fault",
        "sources": reports,
        "reserved_source_sessions": [s for s, role in declared if role == "reserved"],
        "reserved_sources_opened": 0,
        "total_frames": counts,
        "verified_capture_bytes": used_bytes,
        "total_qualified_diagnostic_frames": sum(r["qualified_diagnostic_frames"] for r in reports),
        "orders": 0,
        "training_steps": 0,
        "mode": "research_only",
        "promotion_allowed": False,
        "limitation": (
            "Diagnostic signal counts only; no labels, economic returns, fills or trading edge."
        ),
    }
    report_sha = _sha(_json(report))
    _write_new(Path(output_path), {"report": report, "report_sha256": report_sha}, MAX_REPORT_BYTES)
    return {
        "status": report["status"],
        "report_sha256": report_sha,
        "total_qualified_diagnostic_frames": report["total_qualified_diagnostic_frames"],
        "reserved_sources_opened": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register")
    register.add_argument("--settings", type=Path, required=True)
    register.add_argument("--output", type=Path, required=True)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--plan", type=Path, required=True)
    evaluate.add_argument(
        "--source",
        nargs=3,
        action="append",
        required=True,
        metavar=("SESSION", "CAPTURE", "SHA256"),
    )
    evaluate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "register":
        result = register_flow_pressure(args.settings, args.output)
    else:
        result = evaluate_flow_pressure(
            args.plan,
            tuple((name, Path(path), digest) for name, path, digest in args.source),
            args.output,
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
