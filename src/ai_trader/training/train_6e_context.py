"""Two fixed context/control CPU trees on session-isolated exposed development data."""

from __future__ import annotations

import argparse
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ai_trader.training import causal_6e_context as context
from ai_trader.training import train_6e_microdepth_tree as tree

prior, data = context.prior, context.data
common, baseline = data.common, prior.baseline
MODELS = {"context_tree": context.FEATURES, "snapshot_tree": prior.FEATURES}
PURPOSE = "6e_causal_context_comparison_v1"
MAX_SECONDS = 1200
MAX_CASES = 50_000
MAX_REPORT_BYTES = 16 * 1024**2


def protocol() -> dict:
    return {
        "version": PURPOSE,
        "permission": {
            "purpose": PURPOSE,
            "training_permitted": True,
            "source_manifest": "Verified lineage and fixed roles only; new named permission here; "
            "original named-baseline permission and reports remain unchanged",
        },
        "context": context.protocol(),
        "split": data.protocol()["split"],
        "exposure": "All 2025 sessions exposed development; no untouched holdout claims",
        "fits": "Exactly two fixed CPU trees, same resolved causal training cases; no search, "
        "refit, retries, winner selection or threshold changes",
        "models": {name: list(features) for name, features in MODELS.items()},
        "tree": {
            "max_depth": tree.MAX_DEPTH,
            "minimum_leaf_rows": tree.MIN_LEAF,
            "minimum_leaf_sessions": tree.MIN_SESSIONS,
            "minimum_rows_per_supported_session": tree.MIN_SESSION_ROWS,
            "quantile_bins": tree.BINS,
        },
        "sampling": "Original causal 60s cases for fit; full original decision rows for context "
        "construction; all later one-second decisions for evaluation",
        "threshold_net_ticks": baseline.THRESHOLD,
        "execution": "Original 100ms entry, 15s hold, one position, cooldown and unknown outcomes",
        "costs": "Crossed quotes plus 1 extra tick; same closed selections recosted at 2/4 ticks; "
        "not measured cTrader EURUSD fills",
        "audit": "All accepted session reports: execution-credit conservation and support; "
        "warmup-inclusive counts, no raw-event reinterpretation or quality relaxation",
        "bounds": {"seconds": MAX_SECONDS, "training_cases": MAX_CASES},
        "qwen_training": False,
        "trading_enabled": False,
        "promotion_enabled": False,
        "reserved_outcomes_opened": False,
    }


def fingerprints() -> dict:
    return {
        **prior.fingerprints(),
        **tree.fingerprints(),
        **{
            path.name: common.hash_file(path, 1024**2)
            for path in (Path(context.__file__), Path(__file__))
        },
    }


def prepare(root: Path, manifest_path: Path, manifest_pin: str, path: Path) -> dict:
    manifest = data.load(root, manifest_path, manifest_pin)
    record = {
        "protocol": protocol(),
        "implementation_sha256": fingerprints(),
        "manifest": {"path": str(manifest_path.resolve()), "sha256": manifest_pin},
        "coverage": manifest["coverage"],
        "prepared_utc": datetime.now(UTC).isoformat(),
    }
    common._write_new(path, record)
    return record


def registration(root: Path, path: Path, pin: str) -> tuple[dict, dict]:
    frozen = data.review.pinned(path, pin)
    if frozen["protocol"] != protocol() or frozen["implementation_sha256"] != fingerprints():
        raise ValueError("Context protocol, permission or implementation changed")
    manifest = data.load(root, Path(frozen["manifest"]["path"]), frozen["manifest"]["sha256"])
    if manifest["coverage"] != frozen["coverage"]:
        raise ValueError("Context coverage differs from source manifest")
    return frozen, manifest


def audit_reports(root: Path, manifest: dict) -> dict:
    totals, support, sessions = Counter(), Counter(), []
    for entry in manifest["ledger"]:
        if entry["role"] not in data.ROLES:
            continue
        report = data.review.pinned(root / entry["report"]["path"], entry["report"]["sha256"])
        quality = report["quality"]["execution_flow"]
        if len(quality) != 1 or quality[0]["source_session"] != entry["utc_date"]:
            raise ValueError("Execution audit source session differs")
        values = quality[0]["audit_including_warmup"]
        if any(type(v) is not int or v < 0 for v in values.values()):
            raise ValueError("Execution audit requires nonnegative integer counts")
        data.census.study.audit_conservation(quality)
        totals.update(values)
        support.update(key for key, value in values.items() if value)
        sessions.append(entry["utc_date"])
    return {
        "sessions": sessions,
        "audit_including_warmup": dict(totals),
        "nonzero_sessions": dict(support),
        "conservation_verified": True,
        "confirmed_iceberg_labels": False,
    }


def training_cases(
    root: Path, manifest: dict, deadline=lambda: None
) -> tuple[np.ndarray, list, dict]:
    matrices, samples, sessions, statuses, summaries = [], [], [], Counter(), []
    for entry in manifest["ledger"]:
        if entry["role"] != "train":
            continue
        deadline()
        print(f"Constructing past-only training context {entry['utc_date']}", flush=True)
        rows = data.read_rows(root, entry, "rows")
        cases = data.read_rows(root, entry, "cases")
        if data.accounting(cases) != entry["case_accounting"] or [
            {k: v for k, v in row.items() if k != "path_horizons"} for row in cases
        ] != data.census.study.diagnostics.thin_causally(rows):
            raise ValueError("Context cases differ from original causal decision cohort")
        matrix, summary = context.transform(rows)
        indices = {row["decision_ts_ns"]: i for i, row in enumerate(rows)}
        matrices.append(matrix[[indices[row["decision_ts_ns"]] for row in cases]])
        sessions.append(entry["utc_date"])
        summaries.append(summary)
        for row in cases:
            status = row["outcome"]["status"]
            statuses[status] += 1
            samples.append(
                {
                    "source_session": row["source_session"],
                    "status": status,
                    "targets": row["net_targets_long_short_ticks"],
                }
            )
        if len(samples) > MAX_CASES:
            raise ValueError("Context training case bound exceeded")
    if not matrices:
        raise ValueError("No context training sessions")
    return (
        np.concatenate(matrices),
        samples,
        {
            "sessions": sessions,
            "cases": len(samples),
            "resolved": statuses["resolved"],
            "unknown": len(samples) - statuses["resolved"],
            "statuses": dict(statuses),
            "context": pool_context(summaries),
        },
    )


def fit_models(features: np.ndarray, samples: list[dict]) -> dict:
    x = baseline.validate_feature_matrix(features)
    if (
        len(x) != len(samples)
        or len(samples) > MAX_CASES
        or x.shape[1] != len(context.FEATURES)
        or any(data.role_for_day(row["source_session"]) != "train" for row in samples)
        or any(row["targets"] is not None for row in samples if row["status"] != "resolved")
    ):
        raise ValueError("Only aligned causal training cases may fit context models")
    resolved = np.array([row["status"] == "resolved" for row in samples])
    y = np.asarray([row["targets"] for row in samples if row["status"] == "resolved"])
    sessions = [row["source_session"] for row in samples if row["status"] == "resolved"]
    models = {}
    for name, names in MODELS.items():
        columns = [context.FEATURES.index(key) for key in names]
        model = tree.fit(x[resolved][:, columns], y, sessions)
        parameters = asdict(model)
        models[name] = {
            "parameters": parameters,
            "model_sha256": common.digest(parameters),
            "features": list(names),
            "fit_rows": len(y),
            "leaves": sum("feature" not in node for node in model.nodes),
        }
    return {"models": models}


def predictions(bundle: dict, features: np.ndarray, name: str) -> np.ndarray:
    spec = bundle["models"][name]
    x = baseline.validate_feature_matrix(features)
    if (
        spec["features"] != list(MODELS[name])
        or common.digest(spec["parameters"]) != spec["model_sha256"]
        or x.shape[1] != len(context.FEATURES)
    ):
        raise ValueError("Frozen context parameters or features changed")
    columns = [context.FEATURES.index(key) for key in MODELS[name]]
    return tree.CostTree(**spec["parameters"]).predict(x[:, columns])


def pool_context(items: list[dict]) -> dict:
    return {
        key: sum(item[key] for item in items)
        for key in ("rows", "causal_gap_resets", "no_prior_30s_samples", "incomplete_30s_span")
    }


def evaluate_day(bundle: dict, rows: list[dict]) -> dict:
    matrix, summary = context.transform(rows)
    resolved = np.array([row["outcome"]["status"] == "resolved" for row in rows])
    targets = np.asarray(
        [
            row["net_targets_long_short_ticks"]
            for row in rows
            if row["outcome"]["status"] == "resolved"
        ]
    )
    result = {
        "rows": len(rows),
        "eligible": sum(row["eligible"] for row in rows),
        "resolved": int(resolved.sum()),
        "statuses": dict(Counter(row["outcome"]["status"] for row in rows)),
        "context": summary,
        "models": {},
        "no_trade": prior.policy_summary(rows, np.zeros((len(rows), 2))),
    }
    for name in MODELS:
        forecast = predictions(bundle, matrix, name)
        result["models"][name] = {
            "mean_squared_error_long_short": ((forecast[resolved] - targets) ** 2)
            .mean(axis=0)
            .tolist()
            if resolved.any()
            else None,
            "policy": prior.policy_summary(rows, forecast),
        }
    return result


def aggregate(days: list[dict]) -> dict:
    result = {key: sum(day[key] for day in days) for key in ("rows", "eligible", "resolved")}
    result["sessions"] = len(days)
    result["unknown"] = result["rows"] - result["resolved"]
    result["context"] = pool_context([day["context"] for day in days])
    counts = Counter()
    for day in days:
        counts.update(day["statuses"])
    result["statuses"] = dict(counts)
    result["policies"] = {
        name: prior.pooled_policy([day["models"][name]["policy"] for day in days])
        for name in MODELS
    }
    result["policies"]["no_trade"] = prior.pooled_policy([day["no_trade"] for day in days])
    return result


def run(root: Path, path: Path, pin: str, output: Path) -> dict:
    if output.exists() or not output.resolve().is_relative_to((root / "data/processed").resolve()):
        raise ValueError("Context directory must be new and inside processed data")
    frozen, manifest = registration(root, path, pin)
    output.mkdir(parents=False, exist_ok=False)
    common._write_new(
        output / "attempt.json",
        {"registration_sha256": pin, "started_utc": datetime.now(UTC).isoformat()},
    )
    started = time.monotonic()

    def deadline():
        if time.monotonic() - started > MAX_SECONDS:
            raise TimeoutError("Context experiment time bound exceeded")

    try:
        audit = audit_reports(root, manifest)
        features, samples, training = training_cases(root, manifest, deadline)
        deadline()
        bundle = fit_models(features, samples)
        del features, samples
        content_pin = common.digest(bundle)
        common._write_new(output / "models.json", bundle)
        model_pin = common.hash_file(output / "models.json", MAX_REPORT_BYTES)
        print("Two fixed CPU trees fitted; evaluating later development sessions", flush=True)
        days, daily_pins = [], []
        for entry in manifest["ledger"]:
            if entry["role"] not in data.ROLES[1:]:
                continue
            deadline()
            print(f"Evaluating past-only context {entry['utc_date']}", flush=True)
            rows = data.read_rows(root, entry, "rows")
            result = {
                "source_session": entry["utc_date"],
                "role": entry["role"],
                **evaluate_day(bundle, rows),
            }
            del rows
            if common.digest(bundle) != content_pin:
                raise ValueError("Evaluation changed frozen context models")
            common._write_new(output / f"{entry['utc_date']}.json", result)
            days.append(result)
            daily_pins.append(
                {
                    "source_session": entry["utc_date"],
                    "sha256": common.hash_file(
                        output / f"{entry['utc_date']}.json", MAX_REPORT_BYTES
                    ),
                }
            )
        expected = [e["utc_date"] for e in manifest["ledger"] if e["role"] in data.ROLES[1:]]
        if [day["source_session"] for day in days] != expected:
            raise ValueError("Incomplete context evaluation; no successful subset")
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
        if audit_reports(root, manifest) != audit:
            raise ValueError("Execution audit changed during context experiment")
        data.review.checked_hash(output / "models.json", model_pin, MAX_REPORT_BYTES)
        for item in daily_pins:
            data.review.checked_hash(
                output / f"{item['source_session']}.json", item["sha256"], MAX_REPORT_BYTES
            )
        deadline()
        months = defaultdict(list)
        for day in days:
            months[day["source_session"][:7]].append(day)
        result = {
            "status": "completed_context_development_not_promoted",
            "registration_sha256": pin,
            "manifest_sha256": frozen["manifest"]["sha256"],
            "protocol": frozen["protocol"],
            "implementation_sha256": frozen["implementation_sha256"],
            "coverage": frozen["coverage"],
            "training": training,
            "execution_audit": audit,
            "models_content_sha256": content_pin,
            "models_file_sha256": model_pin,
            "daily_reports": daily_pins,
            "by_role": {
                role: aggregate([d for d in days if d["role"] == role]) for role in data.ROLES[1:]
            },
            "by_month": {month: aggregate(group) for month, group in months.items()},
            "completed_utc": datetime.now(UTC).isoformat(),
            "automatic_retry": False,
            "qwen_trained": False,
            "trading_enabled": False,
            "promotion_enabled": False,
            "reserved_outcomes_opened": False,
            "decision": "development_only_no_candidate_promotion",
            "limitations": [
                "All 2025 outcomes already exposed; no independent candidate evaluation",
                "Five-second normalized snapshots overlap; their means are not raw CVD totals",
                "Replenishment is a conservative proxy; no confirmed iceberg labels",
                "Unknown outcomes retained; quote proxies not broker fills or portfolio PnL",
                "Unmeasured cTrader costs, basis and clock alignment",
                "12_to_16_UTC_decision_scope_only",
            ],
        }
        if len(common.canonical(result)) + 1 > MAX_REPORT_BYTES:
            raise ValueError("Context completion exceeds report byte bound")
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
        print("New named permission frozen for two context/control fits; no trading")
    else:
        if args.registration_sha256 is None or args.output is None:
            parser.error("Registration pin and new output required")
        result = run(args.project_root, args.registration, args.registration_sha256, args.output)
        print(
            common.canonical({"status": result["status"], "training": result["training"]}).decode()
        )


if __name__ == "__main__":
    main()
