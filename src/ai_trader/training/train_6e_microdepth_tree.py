"""One bounded CPU tree fit using causal depth features and whole-session holdouts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path

import numpy as np

from ai_trader.research import databento_6e_microdepth as data
from ai_trader.training import train_6e_cost_baseline as baseline
from ai_trader.training.standardize import validate_feature_matrix

MAX_DEPTH = 4
MIN_LEAF = 500
MIN_SESSIONS = 3
MIN_SESSION_ROWS = 50
BINS = 16


@dataclass(frozen=True)
class CostTree:
    feature_count: int
    thresholds: list[list[float]]
    nodes: list[dict]

    def predict(self, features: np.ndarray) -> np.ndarray:
        x = validate_feature_matrix(features)
        if x.shape[1] != self.feature_count:
            raise ValueError("Feature dimension differs from frozen tree")
        result = np.empty((len(x), 2), dtype=np.float64)

        def visit(node_id, indices):
            node = self.nodes[node_id]
            if "feature" not in node:
                result[indices] = node["mean"]
                return
            left = x[indices, node["feature"]] <= node["threshold"]
            visit(node["left"], indices[left])
            visit(node["right"], indices[~left])

        visit(0, np.arange(len(x)))
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite tree prediction")
        return result


def fit(features: np.ndarray, targets: np.ndarray, sessions: list[str]) -> CostTree:
    """Fixed root quantiles and supported shallow leaves; only training inputs accepted."""
    x = validate_feature_matrix(features)
    y = np.asarray(targets, dtype=np.float64)
    if y.shape != (len(x), 2) or not np.isfinite(y).all() or len(sessions) != len(x):
        raise ValueError("Expected finite two-sided targets and aligned sessions")
    session_names, ids = np.unique(sessions, return_inverse=True)

    def supported(indices):
        counts = np.bincount(ids[indices], minlength=len(session_names))
        return len(indices) >= MIN_LEAF and sum(counts >= MIN_SESSION_ROWS) >= MIN_SESSIONS

    if not supported(np.arange(len(x))):
        raise ValueError("Insufficient training rows or session support")
    edges = [
        np.unique(np.quantile(column, np.arange(1, BINS) / BINS, method="linear")).tolist()
        for column in x.T
    ]
    nodes = []

    def grow(indices, depth):
        node_id = len(nodes)
        target = y[indices]
        totals = target.sum(axis=0)
        node = {
            "rows": len(indices),
            "depth": depth,
            "mean": target.mean(axis=0).tolist(),
            "session_counts": {
                str(session_names[i]): int(n)
                for i, n in enumerate(np.bincount(ids[indices], minlength=len(session_names)))
                if n
            },
        }
        nodes.append(node)
        if depth == MAX_DEPTH or len(indices) < 2 * MIN_LEAF:
            return node_id
        parent_score = float(totals @ totals / len(indices))
        best_score, best = parent_score + 1e-9, None
        for feature, thresholds in enumerate(edges):
            for threshold in thresholds:
                mask = x[indices, feature] <= threshold
                nl = int(mask.sum())
                nr = len(indices) - nl
                if min(nl, nr) < MIN_LEAF:
                    continue
                left_sum = target[mask].sum(axis=0)
                right_sum = totals - left_sum
                score = float(left_sum @ left_sum / nl + right_sum @ right_sum / nr)
                if score > best_score and supported(indices[mask]) and supported(indices[~mask]):
                    best_score, best = score, (feature, threshold, mask)
        if best is not None:
            feature, threshold, mask = best
            node.update(
                feature=feature,
                threshold=threshold,
                squared_error_reduction=best_score - parent_score,
                left=grow(indices[mask], depth + 1),
                right=grow(indices[~mask], depth + 1),
            )
        return node_id

    grow(np.arange(len(x)), 0)
    return CostTree(x.shape[1], edges, nodes)


def model_hash(model: CostTree) -> str:
    return hashlib.sha256(
        json.dumps(asdict(model), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def train_once(rows: list[dict]) -> dict:
    baseline.validate_rows(rows, sessions=data.SESSIONS, feature_names=data.FEATURES)
    train = [
        r
        for r in rows
        if r["source_session"] in data.TRAIN and r["outcome"]["status"] == "resolved"
    ]
    x = baseline.feature_matrix(train, data.FEATURES)
    y = np.asarray([r["net_targets_long_short_ticks"] for r in train], dtype=np.float64)
    model = fit(x, y, [r["source_session"] for r in train])
    pin = model_hash(model)
    partitions = {}
    for name, sessions in (("validation", data.VALIDATION), ("test", data.TEST)):
        partitions[name] = baseline.evaluate(
            model,
            [r for r in rows if r["source_session"] in sessions],
            y.mean(axis=0),
            data.FEATURES,
        )
        if model_hash(model) != pin:
            raise ValueError("Tree changed during evaluation")
    return {
        "model_kind": "two_output_numpy_quantile_cost_tree_v1",
        "model": asdict(model),
        "model_sha256": pin,
        "feature_names": list(data.FEATURES),
        "target_order": ["long_net_ticks", "short_net_ticks"],
        "training": {
            "rows": len(train),
            "sessions": list(data.TRAIN),
            "mean_net_targets": y.mean(axis=0).tolist(),
            "max_depth": MAX_DEPTH,
            "minimum_leaf_rows": MIN_LEAF,
            "minimum_leaf_sessions": MIN_SESSIONS,
            "minimum_rows_per_supported_session": MIN_SESSION_ROWS,
            "quantile_bins": BINS,
            "prediction_threshold_ticks": baseline.THRESHOLD,
            "nodes": len(model.nodes),
            "leaves": sum("feature" not in n for n in model.nodes),
        },
        "session_split": {
            "train": list(data.TRAIN),
            "validation": list(data.VALIDATION),
            "test": list(data.TEST),
        },
        **partitions,
        **baseline.research_decision(partitions["test"]),
    }


def fingerprints() -> dict:
    paths = [Path(data.__file__), Path(__file__)]
    return {
        **baseline.fingerprints(),
        **{p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
    }


def run(*, project_root: Path, config_path: Path, rows_output: Path, report_output: Path) -> dict:
    if (
        rows_output.exists()
        or report_output.exists()
        or rows_output.resolve() == report_output.resolve()
    ):
        raise ValueError("Refusing to overwrite microdepth-training evidence")
    config, pin = data.load_config(config_path)
    sources = fingerprints()
    rows, evidence = data.build_targets(config, project_root)
    result = train_once(rows)
    if fingerprints() != sources or data.load_config(config_path)[1] != pin:
        raise ValueError("Frozen inputs changed during microdepth training")
    raw = b"".join(
        (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode() for row in rows
    )
    report = {
        "artifact_type": "databento_6eu5_microdepth_tree_v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": pin,
        "implementation_sha256": sources,
        "rows": len(rows),
        "rows_sha256": hashlib.sha256(raw).hexdigest(),
        **evidence,
        **result,
        "mode": "offline_research_only",
        "trading_connected": False,
        "qwen_trained": False,
        "runtime": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "databento_dbn": version("databento-dbn"),
            "zstandard": version("zstandard"),
        },
        "limitations": [
            "Reload and absorption are observable proxies, not verified iceberg detections.",
            "Small cohort, overlapping dependent labels, missing-outcome selection in fitting.",
            "Futures quote targets omit fills, size, impact and cTrader broker execution.",
            "One extra tick is an assumption, not measured broker cost.",
            "All dates become exposed after this run. No retuning on these validation/test days.",
            "No Qwen training, network access, model promotion or trading is connected.",
        ],
    }
    data.clock._publish(rows_output, report_output, raw, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--rows-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        project_root=args.project_root,
        config_path=args.config,
        rows_output=args.rows_output,
        report_output=args.report_output,
    )
    print(json.dumps({k: result[k] for k in ("decision", "blockers", "training")}))


if __name__ == "__main__":
    main()
