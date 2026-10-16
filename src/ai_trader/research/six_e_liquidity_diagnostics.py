"""Descriptive session-level diagnostics of complete pinned research metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import date
from pathlib import Path

import numpy as np

from ai_trader.research import six_e_liquidity_status as status

POLICIES = (
    "cvd_follow",
    "liquidity_follow",
    "absorption_fade",
    "cpu_cost",
    "cpu_cost_liquidity",
    "no_trade",
)
PLANS = ("time_exit", "bracket_exit")
ROLES = ("train", "validation_development", "test_development")
SEED, BLOCK_SESSIONS, DRAWS = 20261004, 5, 2000
MIN_CLOSED_SESSIONS = 20
MAX_TOTAL_BYTES = 32 * 1024**2


def protocol() -> dict:
    return {
        "version": "six_e_liquidity_descriptive_diagnostics_v1",
        "scope": "All daily reports of the complete pinned CPU evaluation, no subset selection",
        "bootstrap": {
            "rng": "NumPy PCG64",
            "seed": SEED,
            "draws": DRAWS,
            "block_sessions": BLOCK_SESSIONS,
            "scheme": "Uniform overlapping noncircular blocks of five consecutive accepted "
            "sessions, concatenated and truncated to original cohort length",
            "estimand": "Pooled net ticks per CLOSED trade at fixed one/two/four extra costs; "
            "all accepted sessions are resampled, including no-trade and unknown-exit sessions",
            "interval": "2.5/97.5 percentile descriptive interval; neither independent "
            "validation, p-value, calibrated confidence nor multiple-testing protection",
            "minimum_sessions_with_closed": MIN_CLOSED_SESSIONS,
            "zero_closed_draw": "Interval unavailable if ANY resample has no closed trade; "
            "never discard zero-trade resamples or substitute a zero return",
        },
        "missing": "Unknown entered exits retained with counts; closed sums are incomplete "
        "economics, not zero imputation or complete strategy PnL",
        "risk": "No-trade zeros are observed only when no trade was entered; closed-session "
        "sums and path drawdown ignore unknown exit economics and are not account equity",
        "authority": "Metadata pins and receipt agreement only, not a fresh full verifier; "
        "no model fit, forecast, winner selection, threshold changes, promotion or orders",
        **dict.fromkeys(status.FALSE_FLAGS, False),
        "cpu_training": False,
    }


def _count(value, name: str, bound=14400) -> int:
    if type(value) is not int or not 0 <= value <= bound:
        raise ValueError(f"Invalid diagnostic count: {name}")
    return value


def _number(value, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"Invalid finite diagnostic value: {name}")
    return float(value)


def _role(day: str) -> str:
    if date.fromisoformat(day).isoformat() != day or not day.startswith("2025-"):
        raise ValueError("Diagnostic reports must be 2025 development sessions, never reserved")
    return ROLES[0] if day < "2025-09-01" else ROLES[1] if day < "2025-11-01" else ROLES[2]


def validate(days: list[dict]) -> None:
    if not days or len(days) > 366:
        raise ValueError("Diagnostic cohort must be nonempty and bounded")
    dates = [d["source_session"] for d in days]
    if dates != sorted(set(dates)):
        raise ValueError("Diagnostic sessions must be unique and chronological")
    allowed = {
        "resolved",
        "unresolved_exit_quote_timeout",
        "no_entry_spread_widened",
        "no_entry_quote_timeout",
    }
    for d in days:
        if d["role"] != _role(d["source_session"]) or not 0 < _count(d["rows"], "rows"):
            raise ValueError("Diagnostic session role or row count differs")
        if set(d["policies"]) != set(POLICIES):
            raise ValueError("Diagnostics cannot drop or add policies")
        for name in POLICIES:
            p = d["policies"][name]
            signals = _count(p["signals"], "signals", d["rows"])
            for plan in PLANS:
                m = p[plan]
                selected = _count(m["selected"], "selected", signals)
                closed = _count(m["closed"], "closed", selected)
                _count(m["positive_closed"], "positive_closed", closed)
                unknown = _count(m["unresolved_entered"], "unknown", 1)
                if set(m["statuses"]) - allowed or any(
                    not 0 < _count(v, "status", selected) for v in m["statuses"].values()
                ):
                    raise ValueError("Unexpected or empty diagnostic outcome status")
                if (
                    sum(m["statuses"].values()) != selected
                    or m["statuses"].get("resolved", 0) != closed
                    or m["statuses"].get("unresolved_exit_quote_timeout", 0) != unknown
                    or sum(_count(v, "skip", d["rows"]) for v in m["skips"].values()) + selected
                    != d["rows"]
                ):
                    raise ValueError("Diagnostic selected/closed/unknown accounting differs")
                net = _number(m["total_closed_net_ticks"], "closed net ticks")
                if (closed == 0 and (net != 0 or m["mean_net_ticks"] is not None)) or (
                    closed and _number(m["mean_net_ticks"], "mean net ticks") != net / closed
                ):
                    raise ValueError("Diagnostic mean must remain conditional on closed trades")
                if set(m["extra_cost_ticks"]) != {"1", "2", "4"}:
                    raise ValueError("Diagnostic fixed cost stresses differ")
                previous_positive = closed
                for cost in (1, 2, 4):
                    c = m["extra_cost_ticks"][str(cost)]
                    positive = _count(c["positive_closed"], "cost positives", closed)
                    total = _number(c["total_closed_net_ticks"], "cost net ticks")
                    if (
                        c["closed"] != closed
                        or type(c["closed"]) is not int
                        or total != net - (cost - 1) * closed
                        or positive > previous_positive
                    ):
                        raise ValueError("Diagnostic recost changed the closed selections")
                    previous_positive = positive
                if name == "no_trade" and (signals or selected or closed or unknown):
                    raise ValueError("Diagnostic idle control must not contain trades")


def indices(count: int) -> np.ndarray:
    """Preserve local session dependence without sampling individual trades."""
    if type(count) is not int or not BLOCK_SESSIONS <= count <= 366:
        raise ValueError("Diagnostic resampling needs a bounded five-session cohort")
    rng = np.random.Generator(np.random.PCG64(SEED))
    starts = rng.integers(
        0, count - BLOCK_SESSIONS + 1, size=(DRAWS, math.ceil(count / BLOCK_SESSIONS))
    )
    return (starts[:, :, None] + np.arange(BLOCK_SESSIONS)).reshape(DRAWS, -1)[:, :count]


def _summary(days: list[dict]) -> dict:
    sample = indices(len(days)) if len(days) >= BLOCK_SESSIONS else None
    policies = {}
    for name in POLICIES:
        p = [d["policies"][name] for d in days]
        plans = {}
        for plan in PLANS:
            m = [d[plan] for d in p]
            closed = np.array([d["closed"] for d in m], dtype=np.int64)
            net = np.array([d["total_closed_net_ticks"] for d in m], dtype=np.float64)
            unknown = sum(d["unresolved_entered"] for d in m)
            resampled_closed = closed[sample].sum(axis=1) if sample is not None else None
            support = int(np.count_nonzero(closed)) >= MIN_CLOSED_SESSIONS
            reason = "insufficient_sessions_with_closed" if not support else "available"
            if support and resampled_closed is not None and np.any(resampled_closed == 0):
                reason = "zero_closed_resample_no_subset"
            if support and sample is None:
                reason = "insufficient_accepted_sessions"
            costs = {}
            for cost in (1, 2, 4):
                cost_net = net - (cost - 1) * closed
                interval = None
                if reason == "available":
                    means = cost_net[sample].sum(axis=1) / resampled_closed
                    interval = np.quantile(means, [0.025, 0.975]).tolist()
                costs[str(cost)] = {
                    "total_closed_net_ticks": float(cost_net.sum()),
                    "mean_closed_net_ticks": float(cost_net.sum() / closed.sum())
                    if closed.sum()
                    else None,
                    "positive_closed": sum(
                        d["extra_cost_ticks"][str(cost)]["positive_closed"] for d in m
                    ),
                    "descriptive_closed_mean_interval": interval,
                    "interval_status": reason,
                }
            cumulative = np.concatenate(([0.0], np.cumsum(net)))
            peak = np.maximum.accumulate(cumulative)
            plans[plan] = {
                "selected": sum(d["selected"] for d in m),
                "closed": int(closed.sum()),
                "sessions_with_closed": int(np.count_nonzero(closed)),
                "sessions_without_closed": int(np.count_nonzero(closed == 0)),
                "sessions_with_unknown_entered_exit": sum(d["unresolved_entered"] > 0 for d in m),
                "unknown_entered_exits": unknown,
                "economics_incomplete": bool(unknown),
                "sessions_with_negative_closed_sum": int(np.count_nonzero(net < 0)),
                "sessions_with_positive_closed_sum": int(np.count_nonzero(net > 0)),
                "resolved_session_sequence_drawdown_ticks_not_equity": float(
                    np.max(peak - cumulative)
                ),
                "worst_resolved_session_sum_ticks": float(net.min()),
                "best_resolved_session_sum_ticks": float(net.max()),
                "costs": costs,
            }
        policies[name] = {
            "signals": sum(d["signals"] for d in p),
            "sessions_with_signals": sum(d["signals"] > 0 for d in p),
            **plans,
        }
    return {"sessions": len(days), "rows": sum(d["rows"] for d in days), "policies": policies}


def describe(days: list[dict]) -> dict:
    validate(days)
    return {
        "overall": _summary(days),
        "by_role": {
            role: _summary([d for d in days if d["role"] == role])
            for role in ROLES
            if any(d["role"] == role for d in days)
        },
    }


def report(
    root: Path, registration: Path, pin: str, output: Path, completion_pin: str, destination: Path
) -> dict:
    destination = status._inside(root, destination, "data/processed")
    if destination.suffix != ".json" or destination.is_relative_to(output.resolve()):
        raise ValueError("Diagnostics belong in a separate JSON file, never the owned evaluation")
    if destination.exists():
        raise FileExistsError("Diagnostic result is already claimed; no replacement")
    checked = status.snapshot(root, registration, pin, output, completion_pin)
    if (
        checked["status"] != "pinned_receipt_matches_metadata_not_revalidated"
        or checked["phase"] != "cpu_evaluation"
    ):
        raise ValueError("Diagnostics require complete pinned CPU metadata and its receipt")
    completed, actual = status._json(root, output / "completion.json")
    if actual != completion_pin:
        raise ValueError("Diagnostic completion pin changed")
    days, total_bytes = [], 0
    for evidence in completed["days"]:
        day = evidence["utc_date"]
        _role(day)  # Reject reserved before opening its daily metadata.
        path = output / f"{day}.json"
        raw = status._raw(root, path, status.MAX_JSON, "data/processed")
        total_bytes += len(raw)
        if (
            total_bytes > MAX_TOTAL_BYTES
            or hashlib.sha256(raw).hexdigest() != evidence["report_sha256"]
        ):
            raise ValueError("Diagnostic complete daily report pin or read budget differs")
        saved = status._decode(raw)
        if saved["source_session"] != day or saved["rows"] != evidence["rows"]:
            raise ValueError("Diagnostic daily report identity differs")
        days.append(saved)
    result = {
        "status": "completed_descriptive_metadata_diagnostics_not_validation",
        "protocol": protocol(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "registration_sha256": pin,
        "evaluation_completion_sha256": completion_pin,
        "verification_sha256": checked["verification_sha256"],
        "summaries": describe(days),
    }
    if status.snapshot(root, registration, pin, output, completion_pin) != checked:
        raise ValueError("Diagnostic metadata changed during analysis")
    raw = (
        json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    )
    if len(raw) > status.MAX_JSON:
        raise ValueError("Diagnostic result exceeds bound")
    with destination.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {
        "status": result["status"],
        "sha256": hashlib.sha256(raw).hexdigest(),
        "sessions": len(days),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", required=True, type=Path)
    parser.add_argument("--registration-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--completion-sha256", required=True)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            report(
                Path(__file__).resolve().parents[3],
                args.registration,
                args.registration_sha256,
                args.output,
                args.completion_sha256,
                args.destination,
            )
        )
    )


if __name__ == "__main__":
    main()
