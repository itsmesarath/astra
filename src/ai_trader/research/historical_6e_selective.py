"""Two fixed explanatory CPU fits on exposed development dates; never promotion."""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ai_trader.research import historical_6e_archive as census
from ai_trader.training import train_6e_microdepth_tree as tree

common, v1, study, baseline = census.common, census.v1, census.study, census.baseline
ROWS = "data/processed/6e_multimonth_development_v2_20261001_1_rows.jsonl"
ROWS_PIN = "9a2bb5fe5c32ea067c4d236f8245815bb8380b518bfdf26960b8954282efef84"
MODELS = {
    "cvd_only": ("normalized_cvd_5s",),
    "microstructure_37": (*study.data.FEATURES, *study.flow.FEATURES),
}


def protocol() -> dict:
    return {
        "version": "6e_selective_development_v1",
        "rows_sha256": ROWS_PIN,
        "input_report_sha256": census.PRIOR_REPORT_PIN,
        "train": list(v1.BLOCKS[0].sessions),
        "later_exposed_diagnostics": [s for b in v1.BLOCKS[1:] for s in b.sessions],
        "models": {k: list(v) for k, v in MODELS.items()},
        "model": "Two predetermined cost trees, one fit each; no tuning or winner selection",
        "depth": tree.MAX_DEPTH,
        "bins": tree.BINS,
        "minimum_leaf": tree.MIN_LEAF,
        "minimum_sessions_per_leaf": tree.MIN_SESSIONS,
        "minimum_rows_per_session_in_leaf": tree.MIN_SESSION_ROWS,
        "entry_threshold_net_ticks": baseline.THRESHOLD,
        "training": "April resolved outcomes only; quantile thresholds and leaves train-only",
        "evaluation": "All later eligible decisions including no-entry and unresolved; "
        "one position, latency, cooldown and costs unchanged; explicit no-trade control",
        "interpretation": "Explanatory decision-tree conditions are associations, not causes. "
        "Dates already exposed; no independent performance estimate or profitable promotion.",
        "qwen_training": False,
        "trading_enabled": False,
        "promotion_enabled": False,
    }


def fingerprints() -> dict:
    return {
        **census.fingerprints(),
        **{p.name: common.hash_file(p, 1024**2) for p in (Path(tree.__file__), Path(__file__))},
    }


def prepare(root: Path, path: Path) -> None:
    census.inventory(root)
    if common.hash_file(root / ROWS, v1.MAX_OUTPUT_BYTES) != ROWS_PIN:
        raise ValueError("Development rows differ")
    common._write_new(
        path,
        {
            "protocol": protocol(),
            "implementation_sha256": fingerprints(),
            "prepared_utc": datetime.now(UTC).isoformat(),
        },
    )


def registration(root: Path, path: Path, pin: str) -> dict:
    record = v1.read_pinned(path, pin)
    census.inventory(root)
    if record["protocol"] != protocol() or record["implementation_sha256"] != fingerprints():
        raise ValueError("Selective registration or implementation changed")
    return record


def load_rows(root: Path) -> list[dict]:
    path = root / ROWS
    if common.hash_file(path, v1.MAX_OUTPUT_BYTES) != ROWS_PIN:
        raise ValueError("Pinned development rows differ")
    rows, digest = [], hashlib.sha256()
    with path.open("rb") as handle:
        while raw := handle.readline(common.MAX_LINE + 1):
            if len(raw) > common.MAX_LINE or not raw.endswith(b"\n"):
                raise ValueError("Invalid bounded row")
            digest.update(raw)
            rows.append(common.loads(raw))
            if len(rows) > v1.MAX_ROWS:
                raise ValueError("Development row limit")
    if digest.hexdigest() != ROWS_PIN:
        raise ValueError("Rows changed while reading")
    sessions = tuple(s for b in v1.BLOCKS for s in b.sessions)
    baseline.validate_rows(rows, sessions=sessions, feature_names=study.data.FEATURES)
    for row in rows:
        block = next(b for b in v1.BLOCKS if row["source_session"] in b.sessions)
        if (
            row["partition"] != "development"
            or row["block"] != block.name
            or row["contract"] != block.contract
        ):
            raise ValueError("Unexpected source partition or contract")
    matrix(rows, MODELS["microstructure_37"])
    return rows


def matrix(rows: list[dict], features: tuple[str, ...]) -> np.ndarray:
    values = []
    for row in rows:
        if set(row["features"]) != set(study.data.FEATURES) or set(
            row["execution_features"]
        ) != set(study.flow.FEATURES):
            raise ValueError("Feature allowlist mismatch")
        allowed = {**row["features"], **row["execution_features"]}
        values.append([allowed[k] for k in features])
    return tree.validate_feature_matrix(values)


def policy(rows: list[dict], predictions: np.ndarray) -> dict:
    result = baseline.policy(rows, predictions)
    result.pop("selections")
    result["by_session"] = {}
    for session in dict.fromkeys(r["source_session"] for r in rows):
        mask = np.array([r["source_session"] == session for r in rows])
        one = baseline.policy(
            [r for r in rows if r["source_session"] == session], predictions[mask]
        )
        one.pop("selections")
        result["by_session"][session] = one
    return result


def leaf_explanations(model, features) -> list[dict]:
    result = []

    def visit(index, conditions):
        node = model.nodes[index]
        if "feature" in node:
            term = {"feature": features[node["feature"]], "threshold": node["threshold"]}
            visit(node["left"], [*conditions, {**term, "operator": "<="}])
            visit(node["right"], [*conditions, {**term, "operator": ">"}])
        else:
            result.append(
                {
                    "node": index,
                    "pre_entry_conditions": conditions,
                    "training_rows": node["rows"],
                    "training_sessions": node["session_counts"],
                    "training_mean_long_short_net_ticks": node["mean"],
                    "entry_direction": baseline.action(node["mean"]),
                }
            )

    visit(0, [])
    return result


def analyze(rows: list[dict]) -> dict:
    baseline.validate_rows(
        rows,
        sessions=tuple(s for b in v1.BLOCKS for s in b.sessions),
        feature_names=study.data.FEATURES,
    )
    if any(r.get("partition") != "development" for r in rows):
        raise ValueError("Only exposed development rows may be fitted")
    train = [
        r
        for r in rows
        if r["source_session"] in v1.BLOCKS[0].sessions and r["outcome"]["status"] == "resolved"
    ]
    later = [r for r in rows if r["source_session"] not in v1.BLOCKS[0].sessions]
    if not train or not later:
        raise ValueError("Both chronological development partitions required")
    results = {}
    for name, features in MODELS.items():
        model = tree.fit(
            matrix(train, features),
            np.array([r["net_targets_long_short_ticks"] for r in train]),
            [r["source_session"] for r in train],
        )
        model_before = tree.model_hash(model)
        results[name] = {
            "model": asdict(model),
            "model_sha256": model_before,
            "feature_names": list(features),
            "training_resolved": len(train),
            "conditions": leaf_explanations(model, features),
            "later_exposed_diagnostics": policy(later, model.predict(matrix(later, features))),
        }
        if tree.model_hash(model) != model_before:
            raise ValueError("Evaluation changed the fitted model")
    return {
        "models": results,
        "no_trade_control": policy(later, np.zeros((len(later), 2))),
        "cases_by_block": {
            b.name: census.case_associations([r for r in rows if r["source_session"] in b.sessions])
            for b in v1.BLOCKS
        },
        "decision": "diagnostic_candidates_only_no_adoption",
        "promotion_enabled": False,
    }


def run(root: Path, path: Path, pin: str, output: Path) -> dict:
    attempt, failure = path.with_suffix(".attempt.json"), path.with_suffix(".failure.json")
    if len({p.resolve() for p in (path, attempt, failure, output)}) != 4 or any(
        p.exists() for p in (attempt, failure, output)
    ):
        raise ValueError("Refusing reused or overlapping selective evidence")
    frozen = registration(root, path, pin)
    common._write_new(
        attempt,
        {
            "registration_sha256": pin,
            "automatic_retry": False,
            "started_utc": datetime.now(UTC).isoformat(),
        },
    )
    try:
        rows = load_rows(root)
        result = {"status": "completed", "registration_sha256": pin, **frozen, **analyze(rows)}
        registration(root, path, pin)
        if common.hash_file(root / ROWS, v1.MAX_OUTPUT_BYTES) != ROWS_PIN:
            raise ValueError("Input rows changed during fit")
        common._write_new(output, result)
        return result
    except Exception as exc:
        common._write_new(
            failure,
            {
                "status": "failed",
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
    parser.add_argument("--registration-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.project_root, args.registration)
        print("Two CPU fits registered; no training run yet.")
    else:
        if args.registration_sha256 is None or args.output is None:
            parser.error("Registration pin and new output path required")
        result = run(args.project_root, args.registration, args.registration_sha256, args.output)
        print(
            common.canonical({"status": result["status"], "decision": result["decision"]}).decode()
        )


if __name__ == "__main__":
    main()
