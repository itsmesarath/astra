"""One registered CPU comparison of activity-gated cost models; never orders.

Fits use early development cases only. Later exposed development sessions are
quote-proxy diagnostics, not independent validation or a broker backtest.
"""

from __future__ import annotations

import argparse
import math
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ai_trader.training import historical_6e_manifest as data

common, baseline, census = data.common, data.census.baseline, data.census
FEATURES = (*census.study.data.FEATURES, *census.study.flow.FEATURES)
ACTIVITY_FEATURE = "log_quote_events_5s"
GATE_QUANTILE = 0.70
MODELS = {
    "activity_microstructure": FEATURES,
    "ungated_microstructure": FEATURES,
    "cvd_only": ("normalized_cvd_5s",),
    "queue_only": ("queue_imbalance",),
}
MIN_RESOLVED = 1000
MIN_GATED = 512
MIN_GATED_SESSIONS = 20
MAX_CASES = 50_000
MAX_SECONDS = 1200
MAX_REPORT_BYTES = 16 * 1024**2


def protocol() -> dict:
    return {
        "version": data.PURPOSE,
        "manifest_protocol": data.protocol(),
        "models": {k: list(v) for k, v in MODELS.items()},
        "fits": "Exactly four fixed CPU ridge fits; no tuning, retries, refit or model selection",
        "activity_gate": {
            "feature": ACTIVITY_FEATURE,
            "quantile": GATE_QUANTILE,
            "method": "linear",
            "comparison": ">=",
            "fit": "All causal training cases, including unavailable labels",
        },
        "main_fit": "Resolved training cases passing the causal activity gate",
        "controls_fit": "All resolved causal training cases; control scalers separately train-only",
        "ridge": baseline.RIDGE,
        "clip": baseline.CLIP,
        "prediction_threshold_net_ticks": baseline.THRESHOLD,
        "evaluation": "Every original one-second decision on later development sessions; "
        "entry 100ms, hold 15s, one position and original cooldown; unavailable attempts retained",
        "cost_sensitivity_extra_ticks": [1, 2, 4],
        "costs": "Crossed quotes plus extra ticks, not measured cTrader costs or fills",
        "minimum_support": {
            "resolved": MIN_RESOLVED,
            "gated": MIN_GATED,
            "gated_sessions": MIN_GATED_SESSIONS,
        },
        "bounds": {
            "training_cases": MAX_CASES,
            "seconds": MAX_SECONDS,
            "report_bytes": MAX_REPORT_BYTES,
        },
        "qwen_training": False,
        "trading_enabled": False,
        "promotion_enabled": False,
        "reserved_outcomes_opened": False,
    }


def fingerprints() -> dict:
    return {
        **data.fingerprints(),
        **baseline.fingerprints(),
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
    }


def matrix(rows: list[dict], features: tuple[str, ...]) -> np.ndarray:
    if not features or len(set(features)) != len(features) or not set(features) <= set(FEATURES):
        raise ValueError("Only the causal feature allowlist can enter the model")
    values = []
    for row in rows:
        if set(row["features"]) != set(census.study.data.FEATURES) or set(
            row["execution_features"]
        ) != set(census.study.flow.FEATURES):
            raise ValueError("Causal feature allowlist mismatch")
        allowed = {**row["features"], **row["execution_features"]}
        values.append([allowed[k] for k in features])
    return baseline.validate_feature_matrix(values)


def training_cases(root: Path, manifest: dict) -> tuple[list[dict], dict]:
    rows, statuses, sessions = [], Counter(), []
    for entry in manifest["ledger"]:
        if entry["role"] != "train":
            continue  # Do not open any later-session cases for parameter fitting.
        selected = data.read_rows(root, entry, "cases")
        if data.accounting(selected) != entry["case_accounting"]:
            raise ValueError("Training case accounting differs from manifest")
        sessions.append(entry["utc_date"])
        for row in selected:
            statuses[row["outcome"]["status"]] += 1
            # Future paths and metadata are never model inputs or resident training payloads.
            rows.append(
                {
                    k: row[k]
                    for k in (
                        "source_session",
                        "features",
                        "execution_features",
                        "outcome",
                        "net_targets_long_short_ticks",
                    )
                }
            )
        if len(rows) > MAX_CASES:
            raise ValueError("Training case bound exceeded")
    if not rows or tuple(dict.fromkeys(r["source_session"] for r in rows)) != tuple(sessions):
        raise ValueError("Training sessions are missing, repeated or nonchronological")
    return rows, {
        "sessions": sessions,
        "cases": len(rows),
        "statuses": dict(statuses),
        "resolved": statuses["resolved"],
        "unknown": len(rows) - statuses["resolved"],
    }


def fit_models(rows: list[dict]) -> dict:
    if (
        not rows
        or len(rows) > MAX_CASES
        or any(data.role_for_day(r["source_session"]) != "train" for r in rows)
    ):
        raise ValueError("Only bounded early training cases may fit parameters")
    activity = matrix(rows, (ACTIVITY_FEATURE,))[:, 0]
    cutoff = float(np.quantile(activity, GATE_QUANTILE, method="linear"))
    resolved = [r for r in rows if r["outcome"]["status"] == "resolved"]
    gated = [
        r
        for r, a in zip(rows, activity, strict=True)
        if a >= cutoff and r["outcome"]["status"] == "resolved"
    ]
    gate_sessions = Counter(r["source_session"] for r in gated)
    if (
        len(resolved) < MIN_RESOLVED
        or len(gated) < MIN_GATED
        or len(gate_sessions) < MIN_GATED_SESSIONS
    ):
        raise ValueError("Insufficient registered resolved/gated training support")
    models = {}
    for name, features in MODELS.items():
        fit_rows = gated if name == "activity_microstructure" else resolved
        model = baseline.fit(
            matrix(fit_rows, features),
            np.asarray([r["net_targets_long_short_ticks"] for r in fit_rows], dtype=np.float64),
        )
        models[name] = {
            "parameters": asdict(model),
            "model_sha256": common.digest(asdict(model)),
            "features": list(features),
            "fit_rows": len(fit_rows),
        }
    return {
        "activity_cutoff": cutoff,
        "gate_training_cases": int((activity >= cutoff).sum()),
        "gated_resolved_by_session": dict(gate_sessions),
        "models": models,
    }


def predictions(bundle: dict, rows: list[dict], name: str) -> tuple[np.ndarray, np.ndarray]:
    cutoff = bundle["activity_cutoff"]
    if type(cutoff) not in (int, float) or not math.isfinite(cutoff):
        raise ValueError("Frozen activity cutoff must be finite")
    spec = bundle["models"][name]
    if (
        spec["features"] != list(MODELS[name])
        or common.digest(spec["parameters"]) != spec["model_sha256"]
    ):
        raise ValueError("Frozen model parameters or feature order changed")
    model = baseline.CostModel(**spec["parameters"])
    raw = model.predict(matrix(rows, MODELS[name]))
    policy = raw.copy()
    if name == "activity_microstructure":
        active = matrix(rows, (ACTIVITY_FEATURE,))[:, 0] >= cutoff
        policy[~active] = 0.0
    return raw, policy


def policy_summary(rows: list[dict], forecasts: np.ndarray) -> dict:
    result = baseline.policy(rows, forecasts)
    selections = result.pop("selections")
    outcomes = {(r["source_session"], r["decision_ts_ns"]): r["outcome"] for r in rows}
    result["late_closed"] = sum(
        s["status"] == "resolved"
        and outcomes[(s["source_session"], s["decision_ts_ns"])].get("late_exit", False)
        for s in selections
    )
    closed = [s["net_ticks"] for s in selections if s["status"] == "resolved"]
    result["extra_cost_ticks"] = {
        str(cost): {
            "closed": len(closed),
            "total_closed_net_ticks": sum(x - cost + 1 for x in closed),
            "positive_closed": sum(x - cost + 1 > 0 for x in closed),
        }
        for cost in (1, 2, 4)
    }
    return result


def evaluate_day(bundle: dict, rows: list[dict]) -> dict:
    resolved = np.array([r["outcome"]["status"] == "resolved" for r in rows])
    targets = np.asarray(
        [r["net_targets_long_short_ticks"] for r in rows if r["outcome"]["status"] == "resolved"]
    )
    result = {
        "rows": len(rows),
        "statuses": dict(Counter(r["outcome"]["status"] for r in rows)),
        "eligible": sum(r["eligible"] for r in rows),
        "resolved": int(resolved.sum()),
        "models": {},
        "no_trade": policy_summary(rows, np.zeros((len(rows), 2))),
    }
    activity = matrix(rows, (ACTIVITY_FEATURE,))[:, 0]
    result["activity_gate_pass"] = int((activity >= bundle["activity_cutoff"]).sum())
    for name in MODELS:
        raw, policy = predictions(bundle, rows, name)
        result["models"][name] = {
            "mean_squared_error_long_short": ((raw[resolved] - targets) ** 2).mean(axis=0).tolist()
            if resolved.any()
            else None,
            "policy": policy_summary(rows, policy),
        }
    return result


def pooled_policy(items: list[dict]) -> dict:
    keys = (
        "selected",
        "closed",
        "total_closed_net_ticks",
        "positive_closed",
        "unresolved_entered",
        "inactivity_exposed_entered",
        "late_closed",
    )
    result = {k: sum(item[k] for item in items) for k in keys}
    result["mean_net_ticks"] = (
        result["total_closed_net_ticks"] / result["closed"] if result["closed"] else None
    )
    for key in ("statuses", "skips"):
        counts = Counter()
        for item in items:
            counts.update(item[key])
        result[key] = dict(counts)
    result["extra_cost_ticks"] = {}
    for cost in ("1", "2", "4"):
        costs = [item["extra_cost_ticks"][cost] for item in items]
        result["extra_cost_ticks"][cost] = {
            k: sum(item[k] for item in costs)
            for k in ("closed", "total_closed_net_ticks", "positive_closed")
        }
    return result


def aggregate(days: list[dict]) -> dict:
    result = {
        "sessions": len(days),
        "rows": sum(d["rows"] for d in days),
        "eligible": sum(d["eligible"] for d in days),
        "resolved": sum(d["resolved"] for d in days),
        "activity_gate_pass": sum(d["activity_gate_pass"] for d in days),
    }
    counts = Counter()
    for day in days:
        counts.update(day["statuses"])
    result["statuses"] = dict(counts)
    result["unknown"] = result["rows"] - result["resolved"]
    result["policies"] = {
        name: pooled_policy([d["models"][name]["policy"] for d in days]) for name in MODELS
    }
    result["policies"]["no_trade"] = pooled_policy([d["no_trade"] for d in days])
    return result


def prepare(root: Path, manifest_path: Path, manifest_pin: str, path: Path) -> dict:
    manifest = data.load(root, manifest_path, manifest_pin)
    result = {
        "protocol": protocol(),
        "implementation_sha256": fingerprints(),
        "manifest": {"path": str(manifest_path.resolve()), "sha256": manifest_pin},
        "manifest_coverage": manifest["coverage"],
        "prepared_utc": datetime.now(UTC).isoformat(),
    }
    common._write_new(path, result)
    return result


def registration(root: Path, path: Path, pin: str) -> tuple[dict, dict]:
    frozen = data.review.pinned(path, pin)
    if frozen["protocol"] != protocol() or frozen["implementation_sha256"] != fingerprints():
        raise ValueError("Training protocol or implementation differs")
    manifest = data.load(root, Path(frozen["manifest"]["path"]), frozen["manifest"]["sha256"])
    if manifest["coverage"] != frozen["manifest_coverage"]:
        raise ValueError("Manifest coverage changed")
    return frozen, manifest


def run(root: Path, path: Path, pin: str, output: Path) -> dict:
    if output.exists() or not output.resolve().is_relative_to((root / "data/processed").resolve()):
        raise ValueError("Training directory must be new and inside processed data")
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
            raise TimeoutError("Activity-direction experiment time bound exceeded")

    try:
        rows, training = training_cases(root, manifest)
        deadline()
        bundle = fit_models(rows)
        del rows
        bundle_pin = common.digest(bundle)
        common._write_new(output / "models.json", bundle)
        model_file_pin = common.hash_file(output / "models.json", MAX_REPORT_BYTES)
        print(
            f"Four CPU models fitted on {training['resolved']} resolved training cases", flush=True
        )
        days, daily_pins = [], []
        for entry in manifest["ledger"]:
            if entry["role"] not in data.ROLES[1:]:
                continue
            deadline()
            print(f"Evaluating exposed development session {entry['utc_date']}", flush=True)
            rows = data.read_rows(root, entry, "rows")
            result = {
                "source_session": entry["utc_date"],
                "role": entry["role"],
                **evaluate_day(bundle, rows),
            }
            del rows
            if common.digest(bundle) != bundle_pin:
                raise ValueError("Evaluation changed frozen model parameters")
            common._write_new(output / f"{entry['utc_date']}.json", result)
            daily_pins.append(
                {
                    "source_session": entry["utc_date"],
                    "sha256": common.hash_file(
                        output / f"{entry['utc_date']}.json", MAX_REPORT_BYTES
                    ),
                }
            )
            days.append(result)
        expected = [e["utc_date"] for e in manifest["ledger"] if e["role"] in data.ROLES[1:]]
        if [d["source_session"] for d in days] != expected:
            raise ValueError("Incomplete chronological evaluation; no subset success")
        by_role = {
            role: aggregate([d for d in days if d["role"] == role]) for role in data.ROLES[1:]
        }
        months = defaultdict(list)
        for day in days:
            months[day["source_session"][:7]].append(day)
        deadline()
        registration(root, path, pin)
        # Recheck every consumed shard, not just metadata, before publishing completion.
        for entry in manifest["ledger"]:
            if entry["role"] not in data.ROLES:
                continue
            kind = "cases" if entry["role"] == "train" else "rows"
            item = entry["artifacts"][kind]
            data.review.checked_hash(
                data.artifact_path(root, item["path"]), item["sha256"], census.MAX_DAY_BYTES
            )
        data.review.checked_hash(output / "models.json", model_file_pin, MAX_REPORT_BYTES)
        for item in daily_pins:
            data.review.checked_hash(
                output / f"{item['source_session']}.json", item["sha256"], MAX_REPORT_BYTES
            )
        deadline()
        result = {
            "status": "completed_development_experiment_not_promoted",
            "registration_sha256": pin,
            "manifest_sha256": frozen["manifest"]["sha256"],
            "implementation_sha256": frozen["implementation_sha256"],
            "protocol": frozen["protocol"],
            "training": training,
            "models_content_sha256": bundle_pin,
            "models_file_sha256": model_file_pin,
            "activity_cutoff": bundle["activity_cutoff"],
            "by_role": by_role,
            "by_month": {month: aggregate(group) for month, group in months.items()},
            "daily_reports": daily_pins,
            "completed_utc": datetime.now(UTC).isoformat(),
            "qwen_trained": False,
            "trading_enabled": False,
            "promotion_enabled": False,
            "reserved_outcomes_opened": False,
            "decision": "development_only_not_ready_for_promotion",
            "blockers": [
                "already_exposed_development_dates",
                "unknown_outcomes_retained",
                "quote_proxies_not_broker_fills",
                "unmeasured_cTrader_costs_and_clock_alignment",
                "12_to_16_UTC_scope_only",
                "no_independent_candidate_validation",
            ],
        }
        if len(common.canonical(result)) + 1 > MAX_REPORT_BYTES:
            raise ValueError("Training report byte bound exceeded")
        common._write_new(output / "completion.json", result)
        return result
    except Exception as exc:
        common._write_new(
            output / "failure.json",
            {
                "error_type": type(exc).__name__,
                "error": str(exc),
                "registration_sha256": pin,
                "automatic_retry": False,
            },
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
            parser.error("Pinned manifest required")
        prepare(args.project_root, args.manifest, args.manifest_sha256, args.registration)
        print("Four fixed CPU fits registered; no Qwen training or trading")
    else:
        if args.registration_sha256 is None or args.output is None:
            parser.error("Registration pin and new output directory required")
        result = run(args.project_root, args.registration, args.registration_sha256, args.output)
        print(
            common.canonical({"status": result["status"], "training": result["training"]}).decode()
        )


if __name__ == "__main__":
    main()
