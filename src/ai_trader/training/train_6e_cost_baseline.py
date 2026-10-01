"""One frozen CPU ridge fit and cost-aware policy evaluation on whole sessions."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import numpy as np

from ai_trader.research import databento_6e_cost_targets as data
from ai_trader.training.standardize import fit_standardizer, validate_feature_matrix

THRESHOLD = 0.5
RIDGE = 1.0
CLIP = 10.0


def feature_matrix(rows: list[dict], feature_names: tuple[str, ...] = data.FEATURES) -> np.ndarray:
    if any(set(r["features"]) != set(feature_names) for r in rows):
        raise ValueError("Feature allowlist mismatch; targets and metadata are not model inputs")
    return validate_feature_matrix([[r["features"][key] for key in feature_names] for r in rows])


@dataclass(frozen=True)
class CostModel:
    means: list[float]
    scales: list[float]
    weights: list[list[float]]
    bias: list[float]

    def predict(self, features: np.ndarray) -> np.ndarray:
        x = validate_feature_matrix(features)
        if x.shape[1] != len(self.means):
            raise ValueError("Feature dimension differs from frozen cost model")
        result = np.clip((x - self.means) / self.scales, -CLIP, CLIP) @ self.weights + self.bias
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite cost prediction")
        return result


def fit(features: np.ndarray, targets: np.ndarray) -> CostModel:
    x = validate_feature_matrix(features)
    y = np.asarray(targets, dtype=np.float64)
    if y.shape != (len(x), 2) or not np.isfinite(y).all():
        raise ValueError("Expected finite two-sided targets aligned with features")
    scaler = fit_standardizer(x)
    x = np.clip(scaler.transform(x), -CLIP, CLIP)
    design = np.column_stack((np.ones(len(x)), x))
    penalty = np.eye(design.shape[1]) * RIDGE
    penalty[0, 0] = 0
    parameters = np.linalg.solve(design.T @ design / len(x) + penalty, design.T @ y / len(x))
    if not np.isfinite(parameters).all():
        raise ValueError("Nonfinite ridge parameters")
    return CostModel(
        scaler.means.tolist(),
        scaler.scales.tolist(),
        parameters[1:].tolist(),
        parameters[0].tolist(),
    )


def action(prediction) -> int:
    long, short = prediction
    if not np.isfinite([long, short]).all():
        raise ValueError("Nonfinite policy prediction")
    if max(long, short) <= THRESHOLD or long == short:
        return 0
    return 1 if long > short else -1


def policy(rows: list[dict], predictions: np.ndarray) -> dict:
    """Selections depend on current features; outcomes drive only subsequent position state."""
    if predictions.shape != (len(rows), 2):
        raise ValueError("Prediction/row shape mismatch")
    next_free, session = 0, None
    selections, counts = [], Counter()
    for row, prediction in zip(rows, predictions, strict=True):
        now = row["decision_ts_ns"]
        if row["source_session"] != session:
            session, next_free = row["source_session"], 0
        if not row["eligible"]:
            counts["ineligible"] += 1
            continue
        direction = action(prediction)
        if direction == 0:
            counts["predicted_no_trade"] += 1
            continue
        if now < next_free:
            counts["position_or_cooldown"] += 1
            continue
        outcome = row["outcome"]
        status = outcome["status"]
        selection = {
            "source_session": session,
            "decision_ts_ns": now,
            "direction": direction,
            "predicted_net_ticks": float(prediction[0 if direction == 1 else 1]),
            "status": status,
            "net_ticks": None,
            "inactivity_exposed": outcome.get("inactivity_exposed", False),
        }
        if status == "resolved":
            selection["net_ticks"] = row["net_targets_long_short_ticks"][0 if direction == 1 else 1]
            next_free = outcome["exit_ts_ns"] + data.clock.COOLDOWN_NS
        elif status == "no_entry_quote_timeout":
            next_free = outcome["entry_expiry_ts_ns"] + data.clock.COOLDOWN_NS
        elif status == "no_entry_spread_widened":
            next_free = outcome["entry_rejection_ts_ns"] + data.clock.COOLDOWN_NS
        elif status in {"unresolved_exit_window_end", "no_entry_window_end"}:
            next_free = (now // data.clock.DAY_NS + 1) * data.clock.DAY_NS
        else:
            raise ValueError("Eligible decision has an invalid target status")
        selections.append(selection)
    closed = [s["net_ticks"] for s in selections if s["status"] == "resolved"]
    return {
        "selected": len(selections),
        "statuses": dict(Counter(s["status"] for s in selections)),
        "skips": dict(counts),
        "closed": len(closed),
        "mean_net_ticks": float(np.mean(closed)) if closed else None,
        "total_closed_net_ticks": sum(closed),
        "positive_closed": sum(x > 0 for x in closed),
        "unresolved_entered": sum(s["status"] == "unresolved_exit_window_end" for s in selections),
        "inactivity_exposed_entered": sum(
            s["inactivity_exposed"] and s["status"] in {"resolved", "unresolved_exit_window_end"}
            for s in selections
        ),
        "selections": selections,
    }


def validate_rows(
    rows: list[dict],
    *,
    sessions: tuple[str, ...] = data.SESSIONS,
    feature_names: tuple[str, ...] = data.FEATURES,
) -> None:
    if tuple(dict.fromkeys(r["source_session"] for r in rows)) != sessions:
        raise ValueError("Source sessions must be exact, complete and chronological")
    if any(
        a["decision_ts_ns"] >= b["decision_ts_ns"] for a, b in zip(rows, rows[1:], strict=False)
    ):
        raise ValueError("Duplicate or nonchronological decisions")
    for row in rows:
        decision = row["decision_ts_ns"]
        stamp = datetime.fromtimestamp(decision // data.clock.SECOND_NS, UTC)
        if stamp.date().isoformat() != row["source_session"] or not 12 <= stamp.hour < 16:
            raise ValueError("Decision timestamp does not belong to its source session window")
        if row["outcome"]["status"] not in {
            "not_eligible",
            "resolved",
            "no_entry_quote_timeout",
            "no_entry_spread_widened",
            "no_entry_window_end",
            "unresolved_exit_window_end",
        }:
            raise ValueError("Unfinished or unknown target status")
        targets, label = data.observed_targets(row["outcome"])
        if targets != row["net_targets_long_short_ticks"] or label != row["hindsight_action"]:
            raise ValueError("Target arithmetic or unavailable-label mismatch")
        if not row["eligible"] and row["outcome"]["status"] != "not_eligible":
            raise ValueError("Ineligible row carries a future trade target")
        if row["outcome"]["status"] == "resolved":
            outcome = row["outcome"]
            if (
                not row["eligible"]
                or not decision + 100_000_000 <= outcome["entry_ts_ns"] <= decision + 1_100_000_000
                or outcome["exit_ts_ns"] < outcome["entry_ts_ns"] + data.clock.HOLD_NS
                or outcome["exit_ts_ns"]
                >= (decision // data.clock.DAY_NS) * data.clock.DAY_NS
                + 16 * 3600 * data.clock.SECOND_NS
                or outcome["entry_ask_nano"] - outcome["entry_bid_nano"] != data.clock.TICK
            ):
                raise ValueError("Target leaks through latency or session boundary")
    feature_matrix(rows, feature_names)


def evaluate(
    model: CostModel,
    rows: list[dict],
    train_mean: np.ndarray,
    feature_names: tuple[str, ...] = data.FEATURES,
) -> dict:
    predictions = model.predict(feature_matrix(rows, feature_names))
    resolved = np.array([r["outcome"]["status"] == "resolved" for r in rows])
    y = np.array(
        [r["net_targets_long_short_ticks"] for r in rows if r["outcome"]["status"] == "resolved"]
    )
    if not len(y):
        raise ValueError("Partition has no observed targets")
    policies = {
        "model": policy(rows, predictions),
        "always_no_trade": policy(rows, np.zeros_like(predictions)),
        "train_mean": policy(rows, np.tile(train_mean, (len(rows), 1))),
    }
    return {
        "rows": len(rows),
        "eligible": sum(r["eligible"] for r in rows),
        "resolved_targets": len(y),
        "target_statuses": dict(Counter(r["outcome"]["status"] for r in rows)),
        "hindsight_labels": dict(
            Counter(str(r["hindsight_action"]) for r in rows if r["hindsight_action"] is not None)
        ),
        "mean_squared_error_long_short": ((predictions[resolved] - y) ** 2).mean(axis=0).tolist(),
        "train_mean_squared_error_long_short": ((train_mean - y) ** 2).mean(axis=0).tolist(),
        "policies": policies,
        "by_session": [
            {
                "source_session": session,
                "model": policy(
                    [r for r in rows if r["source_session"] == session],
                    predictions[[r["source_session"] == session for r in rows]],
                ),
            }
            for session in dict.fromkeys(r["source_session"] for r in rows)
        ],
    }


def research_decision(test: dict) -> dict:
    primary = test["policies"]["model"]
    days = [d["model"] for d in test["by_session"]]
    blockers = []
    if primary["unresolved_entered"]:
        blockers.append("unresolved_test_positions")
    if primary["inactivity_exposed_entered"]:
        blockers.append("inactivity_exposed_test_positions")
    if (
        primary["closed"] < 100
        or len(days) != len(data.TEST)
        or any(d["closed"] < 20 for d in days)
    ):
        blockers.append("insufficient_test_trades")
    if any(d["mean_net_ticks"] is None or d["mean_net_ticks"] <= 0 for d in [primary, *days]):
        blockers.append("no_positive_cost_adjusted_evidence")
    return {
        "decision": "not_ready_for_promotion"
        if blockers
        else "requires_independent_replication_and_broker_validation",
        "blockers": blockers,
        "promotion_enabled": False,
    }


def train_once(rows: list[dict]) -> dict:
    validate_rows(rows)
    train = [
        r
        for r in rows
        if r["source_session"] in data.TRAIN and r["outcome"]["status"] == "resolved"
    ]
    train_x = feature_matrix(train)
    train_y = np.asarray([r["net_targets_long_short_ticks"] for r in train], dtype=np.float64)
    model = fit(train_x, train_y)
    model_raw = json.dumps(asdict(model), sort_keys=True, separators=(",", ":")).encode()
    frozen = hashlib.sha256(model_raw).hexdigest()
    partitions = {}
    for name, sessions in (("validation", data.VALIDATION), ("test", data.TEST)):
        partitions[name] = evaluate(
            model, [r for r in rows if r["source_session"] in sessions], train_y.mean(axis=0)
        )
        if (
            hashlib.sha256(
                json.dumps(asdict(model), sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            != frozen
        ):
            raise ValueError("Model changed during evaluation")
    return {
        "model_kind": "two_output_numpy_ridge_cost_baseline_v1",
        "model": asdict(model),
        "model_sha256": frozen,
        "feature_names": list(data.FEATURES),
        "target_order": ["long_net_ticks", "short_net_ticks"],
        "training": {
            "rows": len(train),
            "sessions": list(data.TRAIN),
            "ridge": RIDGE,
            "prediction_threshold_ticks": THRESHOLD,
            "standardized_clip": CLIP,
            "mean_net_targets": train_y.mean(axis=0).tolist(),
        },
        "session_split": {
            "train": list(data.TRAIN),
            "validation": list(data.VALIDATION),
            "test": list(data.TEST),
        },
        **partitions,
        **research_decision(partitions["test"]),
    }


def fingerprints() -> dict:
    paths = [Path(data.__file__), Path(__file__), Path(__file__).with_name("standardize.py")]
    return {
        **data.events.source_fingerprints(),
        **{p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
    }


def run(*, project_root: Path, config_path: Path, rows_output: Path, report_output: Path) -> dict:
    if (
        rows_output.exists()
        or report_output.exists()
        or rows_output.resolve() == report_output.resolve()
    ):
        raise ValueError("Refusing to overwrite cost-training evidence")
    config, config_sha = data.load_config(config_path)
    pins = fingerprints()
    rows, evidence = data.build_targets(config, project_root)
    result = train_once(rows)
    if pins != fingerprints() or data.load_config(config_path)[1] != config_sha:
        raise ValueError("Frozen inputs changed during cost training")
    raw = b"".join(
        (json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n").encode() for r in rows
    )
    report = {
        "artifact_type": "databento_6eu5_cost_baseline_v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": config_sha,
        "implementation_sha256": pins,
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
            "Overlapping targets are dependent; label metrics are not portfolio performance.",
            "Unavailable future outcomes are retained, not fabricated no-trade labels.",
            "Fit uses resolved targets, so missing-outcome selection remains a limitation.",
            "Quote targets omit fills, size, impact and cTrader broker-specific execution.",
            "One extra tick is an assumption, not a measured broker cost.",
            "No tuning on validation/test; all reported dates become exposed after this run.",
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
    print(
        json.dumps(
            {
                "decision": result["decision"],
                "blockers": result["blockers"],
                "training": result["training"],
                "evaluation": {
                    key: {
                        "rows": result[key]["rows"],
                        "model_policy": {
                            k: v
                            for k, v in result[key]["policies"]["model"].items()
                            if k != "selections"
                        },
                    }
                    for key in ("validation", "test")
                },
            }
        )
    )


if __name__ == "__main__":
    main()
