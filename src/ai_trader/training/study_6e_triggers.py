"""Registered causal event hypotheses on exposed 6E development sessions; no fitting."""

from __future__ import annotations

import argparse
import math
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ai_trader.training import train_6e_context as lineage

data, common, prior = lineage.data, lineage.common, lineage.prior
SECOND = 1_000_000_000
PURPOSE = "6e_causal_trigger_study_v1"
QUANTILE = 0.9
MAX_UNKNOWN_FRACTION = 0.1
MAX_SECONDS = 1200
MAX_REPORT_BYTES = 16 * 1024**2
FAMILIES = ("activity", "burst", "sweep_proxy", "absorption_reload_proxy")
POLICIES = tuple(
    f"{family}_{rule}" for family in FAMILIES for rule in ("follow", "reverse", "queue")
)
CALIBRATION_KEYS = ("activity", "absolute_cvd", "held_passive")


def protocol() -> dict:
    return {
        "version": PURPOSE,
        "permission": {"purpose": PURPOSE, "research_only": True, "model_training": False},
        "lineage": "Original manifest used for verified sources and fixed whole-session roles only",
        "split": data.protocol()["split"],
        "exposure": "All 2025 outcomes exposed development, not independent holdouts",
        "calibration": {
            "sampling": "All original causal 60s training cases, including unknown outcomes",
            "quantile": QUANTILE,
            "method": "linear",
            "inputs": "log_known_trades_5s; abs(normalized_cvd_5s); both held-top passive sides",
            "held_passive": "Quantile of strictly positive side observations; "
            "absent support disables absorption",
            "targets_used": False,
        },
        "detector": {
            "activity": "positive known-trade activity >= early cutoff; "
            "unknown fraction <= bound; nonzero CVD",
            "burst": "activity and positive absolute CVD >= early cutoff",
            "sweep_proxy": "burst; CVD-aligned prior mid progress >=1 tick and OFI >0; "
            "NOT an observed multilevel sweep",
            "absorption_reload_proxy": "burst; abs(prior mid progress) <=1 tick; "
            "aggression-side held passive >= positive cutoff and other-id reload >0",
            "episodes": "One event on rising condition or CVD sign change, "
            "independently per family; no future eligibility filtering",
            "reset": "Fresh session/contract; clear previous conditions on decision gap >5s "
            "or causal prior quote gap >5s",
            "unknown_fraction_bound": MAX_UNKNOWN_FRACTION,
            "sampling": "Original completed-quote decisions >=1s apart; "
            "overlapping 5s feature snapshots",
        },
        "hypotheses": {
            "follow": "Direction equals current CVD sign at event",
            "reverse": "Direction opposes current CVD sign at same event",
            "queue": "Current queue sign at EXACT same event; zero queue abstains",
            "controls": "Activity-only episodes and same-event queue direction, "
            "not causal identification or matched future samples",
        },
        "policy": "Boolean direction adapter, NOT predicted net return; original eligible entry, "
        "100ms latency, 15s hold, one position and cooldown",
        "adapter_threshold": prior.baseline.THRESHOLD,
        "costs": "Original crossed quotes +1 extra tick; "
        "same closed selections recosted at 2/4 ticks",
        "bounds": {"seconds": MAX_SECONDS, "calibration_cases": lineage.MAX_CASES},
        "selection": "No best-rule selection, retuning, retries, model fit or promotion",
        "trading_enabled": False,
        "qwen_training": False,
        "reserved_outcomes_opened": False,
    }


def fingerprints() -> dict:
    return {
        **lineage.fingerprints(),
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
    }


def prepare(root: Path, manifest_path: Path, manifest_pin: str, path: Path) -> dict:
    manifest = data.load(root, manifest_path, manifest_pin)
    result = {
        "protocol": protocol(),
        "implementation_sha256": fingerprints(),
        "manifest": {"path": str(manifest_path.resolve()), "sha256": manifest_pin},
        "coverage": manifest["coverage"],
        "prepared_utc": datetime.now(UTC).isoformat(),
    }
    common._write_new(path, result)
    return result


def registration(root: Path, path: Path, pin: str) -> tuple[dict, dict]:
    frozen = data.review.pinned(path, pin)
    if frozen["protocol"] != protocol() or frozen["implementation_sha256"] != fingerprints():
        raise ValueError("Trigger protocol or implementation changed")
    manifest = data.load(root, Path(frozen["manifest"]["path"]), frozen["manifest"]["sha256"])
    if manifest["coverage"] != frozen["coverage"]:
        raise ValueError("Trigger coverage differs from verified manifest")
    return frozen, manifest


def causal_inputs(row: dict, session: str, contract: str) -> tuple[dict, dict]:
    """Strict projection. Outcomes, paths, targets and eligibility are never accessed."""
    data.role_for_day(session)  # Refuse reserved dates before looking at features.
    if (
        row["source_session"] != session
        or row["contract"] != contract
        or contract != data.census.dated_contract(session)
        or row["partition"] != "development"
    ):
        raise ValueError("Trigger cannot mix sessions, contracts or partitions")
    now = row["decision_ts_ns"]
    if type(now) is not int:
        raise ValueError("Trigger timestamp requires integer nanoseconds")
    stamp = datetime.fromtimestamp(now // SECOND, UTC)
    if stamp.date().isoformat() != session or not 12 <= stamp.hour < 16:
        raise ValueError("Trigger timestamp outside source decision window")
    f, e = row["features"], row["execution_features"]
    if (
        set(f) != set(data.census.study.data.FEATURES)
        or set(e) != set(data.census.study.flow.FEATURES)
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in f.values())
        or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in e.values())
        or f["log_known_trades_5s"] < 0
        or not 0 <= f["unknown_trade_fraction_5s"] <= 1
    ):
        raise ValueError("Trigger causal feature allowlist or values differ")
    return f, e


def calibrate(samples: list[dict]) -> dict:
    """Only feature-projected early cases may enter this unsupervised calibration."""
    if not samples or len(samples) > lineage.MAX_CASES:
        raise ValueError("Trigger calibration case bound exceeded")
    values = {key: [] for key in CALIBRATION_KEYS}
    sessions = Counter()
    last = None
    for row in samples:
        if data.role_for_day(row["source_session"]) != "train":
            raise ValueError("Only training sessions may calibrate trigger thresholds")
        if set(row) != {
            "source_session",
            "contract",
            "partition",
            "decision_ts_ns",
            "features",
            "execution_features",
        }:
            raise ValueError("Calibration accepts only causal projections, not outcomes")
        f, e = causal_inputs(row, row["source_session"], row["contract"])
        if last is not None and row["decision_ts_ns"] <= last:
            raise ValueError("Calibration cases must be unique and chronological")
        last = row["decision_ts_ns"]
        sessions[row["source_session"]] += 1
        values["activity"].append(f["log_known_trades_5s"])
        values["absolute_cvd"].append(abs(f["normalized_cvd_5s"]))
        values["held_passive"].extend(
            e[key] for key in ("bid_held_top_passive_5s", "ask_held_top_passive_5s") if e[key] > 0
        )
    return {
        "cutoffs": {
            key: float(np.quantile(items, QUANTILE, method="linear")) if items else None
            for key, items in values.items()
        },
        "calibration_cases": len(samples),
        "cases_by_session": dict(sessions),
        "positive_held_side_observations": len(values["held_passive"]),
        "targets_used": False,
    }


def calibration_cases(root: Path, manifest: dict, deadline=lambda: None) -> tuple[list[dict], dict]:
    samples, statuses = [], Counter()
    for entry in manifest["ledger"]:
        if entry["role"] != "train":
            continue
        deadline()
        rows = data.read_rows(root, entry, "cases")
        if data.accounting(rows) != entry["case_accounting"]:
            raise ValueError("Trigger calibration accounting differs from original cases")
        for row in rows:
            statuses[row["outcome"]["status"]] += 1
            samples.append(
                {
                    key: row[key]
                    for key in (
                        "source_session",
                        "contract",
                        "partition",
                        "decision_ts_ns",
                        "features",
                        "execution_features",
                    )
                }
            )
        if len(samples) > lineage.MAX_CASES:
            raise ValueError("Trigger calibration case bound exceeded")
    return samples, {
        "cases": len(samples),
        "statuses": dict(statuses),
        "resolved": statuses["resolved"],
        "unknown": len(samples) - statuses["resolved"],
    }


class TriggerState:
    def __init__(self, session: str, contract: str, bundle: dict):
        data.role_for_day(session)
        if contract != data.census.dated_contract(session):
            raise ValueError("Trigger contract differs from dated source")
        cutoffs = bundle["cutoffs"]
        if (
            set(cutoffs) != set(CALIBRATION_KEYS)
            or any(
                type(cutoffs[key]) not in (int, float)
                or not math.isfinite(cutoffs[key])
                or cutoffs[key] < 0
                for key in ("activity", "absolute_cvd")
            )
            or (
                cutoffs["held_passive"] is not None
                and (
                    type(cutoffs["held_passive"]) not in (int, float)
                    or not math.isfinite(cutoffs["held_passive"])
                    or cutoffs["held_passive"] <= 0
                )
            )
        ):
            raise ValueError("Frozen trigger cutoffs differ or are nonfinite")
        self.session, self.contract = session, contract
        self.cutoffs = dict(cutoffs)
        self.last_ts = None
        self.previous = dict.fromkeys(FAMILIES, 0)
        self.resets = 0

    def observe(self, row: dict) -> dict:
        f, e = causal_inputs(row, self.session, self.contract)
        now = row["decision_ts_ns"]
        if self.last_ts is not None and now - self.last_ts < SECOND:
            raise ValueError("Trigger decisions regress, duplicate or violate one-second sampling")
        if (self.last_ts is not None and now - self.last_ts > 5 * SECOND) or f[
            "log_prior_quote_gap_ms"
        ] > math.log1p(5000):
            self.previous = dict.fromkeys(FAMILIES, 0)
            self.resets += 1
        cvd = f["normalized_cvd_5s"]
        direction = int(np.sign(cvd))
        activity = (
            direction != 0
            and f["log_known_trades_5s"] > 0
            and f["log_known_trades_5s"] >= self.cutoffs["activity"]
            and f["unknown_trade_fraction_5s"] <= MAX_UNKNOWN_FRACTION
        )
        burst = activity and abs(cvd) >= self.cutoffs["absolute_cvd"]
        side = "ask" if direction > 0 else "bid"
        conditions = {
            "activity": activity,
            "burst": burst,
            "sweep_proxy": burst
            and direction * f["mid_change_5s_ticks"] >= 1
            and direction * f["normalized_ofi_5s"] > 0,
            "absorption_reload_proxy": burst
            and abs(f["mid_change_5s_ticks"]) <= 1
            and self.cutoffs["held_passive"] is not None
            and e[f"{side}_held_top_passive_5s"] >= self.cutoffs["held_passive"]
            and e[f"{side}_other_id_reload_5s"] > 0,
        }
        result = {
            family: direction if active and self.previous[family] != direction else 0
            for family, active in conditions.items()
        }
        self.previous = {
            family: direction if active else 0 for family, active in conditions.items()
        }
        self.last_ts = now
        return {**result, "queue": int(np.sign(f["queue_imbalance"]))}


def directions(rows: list[dict], bundle: dict) -> tuple[dict, dict]:
    if not rows or len(rows) > 14_400:
        raise ValueError("Triggers require a bounded complete source session")
    state = TriggerState(rows[0]["source_session"], rows[0]["contract"], bundle)
    observed = [state.observe(row) for row in rows]
    result = {}
    for family in FAMILIES:
        follow = np.array([item[family] for item in observed], dtype=np.int8)
        result[f"{family}_follow"] = follow
        result[f"{family}_reverse"] = -follow
        result[f"{family}_queue"] = np.array(
            [item["queue"] if item[family] else 0 for item in observed], dtype=np.int8
        )
    return result, {"causal_gap_resets": state.resets}


def trigger_summary(rows: list[dict], signs: np.ndarray, queue: np.ndarray) -> dict:
    """All detected episodes, including ineligible and unknown. Not portfolio results."""
    indices = np.flatnonzero(signs)
    statuses = Counter(rows[i]["outcome"]["status"] for i in indices)
    resolved = [i for i in indices if rows[i]["outcome"]["status"] == "resolved"]
    follow = [rows[i]["net_targets_long_short_ticks"][0 if signs[i] == 1 else 1] for i in resolved]
    reverse = [rows[i]["net_targets_long_short_ticks"][1 if signs[i] == 1 else 0] for i in resolved]
    return {
        "detected": len(indices),
        "eligible": sum(rows[i]["eligible"] for i in indices),
        "resolved": len(resolved),
        "unknown": len(indices) - len(resolved),
        "statuses": dict(statuses),
        "queue_ties": int((queue[indices] == 0).sum()),
        "follow_net_ticks_sum": sum(follow),
        "reverse_net_ticks_sum": sum(reverse),
        "follow_positive": sum(v > 0 for v in follow),
        "reverse_positive": sum(v > 0 for v in reverse),
        "neither_positive": sum(a <= 0 and b <= 0 for a, b in zip(follow, reverse, strict=True)),
    }


def evaluate_day(bundle: dict, rows: list[dict]) -> dict:
    signs, diagnostics = directions(rows, bundle)
    result = {
        "rows": len(rows),
        "eligible": sum(row["eligible"] for row in rows),
        "resolved": sum(row["outcome"]["status"] == "resolved" for row in rows),
        "diagnostics": diagnostics,
        "events": {},
        "policies": {},
    }
    for family in FAMILIES:
        result["events"][family] = trigger_summary(
            rows, signs[f"{family}_follow"], signs[f"{family}_queue"]
        )
    for name, values in signs.items():
        # This adapts a fixed hypothesis to the existing entry simulator, NOT a profit forecast.
        result["policies"][name] = prior.policy_summary(
            rows, np.column_stack((values > 0, values < 0)).astype(float)
        )
    result["policies"]["no_trade"] = prior.policy_summary(rows, np.zeros((len(rows), 2)))
    return result


def aggregate(days: list[dict]) -> dict:
    result = {key: sum(day[key] for day in days) for key in ("rows", "eligible", "resolved")}
    result.update(sessions=len(days), unknown=result["rows"] - result["resolved"])
    result["causal_gap_resets"] = sum(day["diagnostics"]["causal_gap_resets"] for day in days)
    result["events"] = {}
    for family in FAMILIES:
        items = [day["events"][family] for day in days]
        totals = {
            key: sum(item[key] for item in items)
            for key in (
                "detected",
                "eligible",
                "resolved",
                "unknown",
                "queue_ties",
                "follow_net_ticks_sum",
                "reverse_net_ticks_sum",
                "follow_positive",
                "reverse_positive",
                "neither_positive",
            )
        }
        statuses = Counter()
        for item in items:
            statuses.update(item["statuses"])
        totals["statuses"] = dict(statuses)
        totals["sessions_with_events"] = sum(item["detected"] > 0 for item in items)
        for rule in ("follow", "reverse"):
            totals[f"{rule}_mean_net_ticks"] = (
                totals[f"{rule}_net_ticks_sum"] / totals["resolved"] if totals["resolved"] else None
            )
        result["events"][family] = totals
    result["policies"] = {
        name: prior.pooled_policy([day["policies"][name] for day in days])
        for name in (*POLICIES, "no_trade")
    }
    for name, policy in result["policies"].items():
        items = [day["policies"][name] for day in days]
        active = [item for item in items if item["closed"]]
        policy["session_support"] = {
            "closed_sessions": len(active),
            "positive_closed_net_sessions": sum(
                item["total_closed_net_ticks"] > 0 for item in active
            ),
            "negative_closed_net_sessions": sum(
                item["total_closed_net_ticks"] < 0 for item in active
            ),
            "sessions_with_unknown_attempts": sum(
                item["selected"] > item["closed"] for item in items
            ),
            "minimum_closed_per_active_session": min(
                (item["closed"] for item in active), default=0
            ),
            "worst_closed_session_net_ticks": min(
                (item["total_closed_net_ticks"] for item in active), default=None
            ),
            "best_closed_session_net_ticks": max(
                (item["total_closed_net_ticks"] for item in active), default=None
            ),
        }
    return result


def run(root: Path, path: Path, pin: str, output: Path) -> dict:
    if output.exists() or not output.resolve().is_relative_to((root / "data/processed").resolve()):
        raise ValueError("Trigger output must be new and inside processed data")
    frozen, manifest = registration(root, path, pin)
    output.mkdir(parents=False, exist_ok=False)
    common._write_new(
        output / "attempt.json",
        {
            "registration_sha256": pin,
            "started_utc": datetime.now(UTC).isoformat(),
            "automatic_retry": False,
        },
    )
    started = time.monotonic()

    def deadline():
        if time.monotonic() - started > MAX_SECONDS:
            raise TimeoutError("Trigger study time bound exceeded")

    try:
        audit = lineage.audit_reports(root, manifest)
        samples, accounting = calibration_cases(root, manifest, deadline)
        bundle = calibrate(samples)
        del samples
        content_pin = common.digest(bundle)
        common._write_new(output / "thresholds.json", bundle)
        bundle_pin = common.hash_file(output / "thresholds.json", MAX_REPORT_BYTES)
        days, daily_pins = [], []
        for entry in manifest["ledger"]:
            if entry["role"] not in data.ROLES:
                continue
            deadline()
            print(f"Evaluating frozen causal triggers {entry['utc_date']}", flush=True)
            rows = data.read_rows(root, entry, "rows")
            day = {
                "source_session": entry["utc_date"],
                "role": entry["role"],
                **evaluate_day(bundle, rows),
            }
            del rows
            if common.digest(bundle) != content_pin:
                raise ValueError("Evaluation changed frozen trigger thresholds")
            common._write_new(output / f"{entry['utc_date']}.json", day)
            days.append(day)
            daily_pins.append(
                {
                    "source_session": entry["utc_date"],
                    "sha256": common.hash_file(
                        output / f"{entry['utc_date']}.json", MAX_REPORT_BYTES
                    ),
                }
            )
        expected = [
            entry["utc_date"] for entry in manifest["ledger"] if entry["role"] in data.ROLES
        ]
        if [day["source_session"] for day in days] != expected:
            raise ValueError("Incomplete trigger evaluation; no successful subset")
        registration(root, path, pin)
        for entry in manifest["ledger"]:
            if entry["role"] not in data.ROLES:
                continue
            for kind in ("rows", "cases") if entry["role"] == "train" else ("rows",):
                item = entry["artifacts"][kind]
                data.review.checked_hash(
                    data.artifact_path(root, item["path"]),
                    item["sha256"],
                    data.census.MAX_DAY_BYTES,
                )
        if lineage.audit_reports(root, manifest) != audit:
            raise ValueError("Execution audit changed during trigger study")
        data.review.checked_hash(output / "thresholds.json", bundle_pin, MAX_REPORT_BYTES)
        for item in daily_pins:
            data.review.checked_hash(
                output / f"{item['source_session']}.json", item["sha256"], MAX_REPORT_BYTES
            )
        deadline()
        months = defaultdict(list)
        for day in days:
            months[day["source_session"][:7]].append(day)
        result = {
            "status": "completed_trigger_development_not_promoted",
            "registration_sha256": pin,
            "manifest_sha256": frozen["manifest"]["sha256"],
            "protocol": frozen["protocol"],
            "implementation_sha256": frozen["implementation_sha256"],
            "coverage": frozen["coverage"],
            "calibration_accounting": accounting,
            "execution_audit": audit,
            "thresholds_content_sha256": content_pin,
            "thresholds_file_sha256": bundle_pin,
            "daily_reports": daily_pins,
            "by_role": {
                role: aggregate([day for day in days if day["role"] == role]) for role in data.ROLES
            },
            "by_month": {month: aggregate(group) for month, group in months.items()},
            "completed_utc": datetime.now(UTC).isoformat(),
            "automatic_retry": False,
            "model_fitted": False,
            "qwen_trained": False,
            "trading_enabled": False,
            "promotion_enabled": False,
            "reserved_outcomes_opened": False,
            "decision": "development_only_no_rule_selection_or_promotion",
            "limitations": [
                "All 2025 outcomes exposed; no independent evaluation",
                "Overlapping 5s snapshots and event families are dependent",
                "Sweep and absorption/reload are observable proxies, "
                "not confirmed sweeps or icebergs",
                "Unknowns retained; descriptive all-event outcomes are not portfolio PnL",
                "One-position policies use quote proxies, not measured cTrader fills, "
                "EURUSD basis or broker costs",
                "Decision scope 12_to_16_UTC only; no raw archive reinterpretation",
            ],
        }
        if len(common.canonical(result)) + 1 > MAX_REPORT_BYTES:
            raise ValueError("Trigger completion report byte bound exceeded")
        common._write_new(output / "completion.json", result)
        return result
    except Exception as exc:
        common._write_new(
            output / "failure.json",
            {"error": str(exc), "error_type": type(exc).__name__, "automatic_retry": False},
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--registration-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.prepare:
        if args.manifest is None or args.manifest_sha256 is None:
            parser.error("Pinned lineage manifest required")
        prepare(args.project_root, args.manifest, args.manifest_sha256, args.registration)
        print("Trigger protocol frozen; no model fitting or trading")
    else:
        if args.registration_sha256 is None or args.output is None:
            parser.error("Registration pin and new output required")
        result = run(args.project_root, args.registration, args.registration_sha256, args.output)
        print(
            common.canonical({"status": result["status"], "coverage": result["coverage"]}).decode()
        )


if __name__ == "__main__":
    main()
