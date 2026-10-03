"""Fixed natural-prior CPU objective study, train-only and never a trading policy."""

from __future__ import annotations

import argparse
import hashlib
import time
from collections import deque
from pathlib import Path

import numpy as np

from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.training import six_e_balance_plan as balance
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import _write

task, evaluation, standardize = balance.task, balance.evaluation, balance.standardize
KIND = "six_e_train_only_direction_cost_v1"
MODES = {"natural_cross_entropy": 0.0, "natural_direction_penalty": 1.0}
PENALTIES = {"missed_opportunity": 1.0, "no_opportunity_overcall": 4.0, "wrong_side": 6.0}
EPOCHS, LEARNING_RATE, L2, CLIP = 200, 0.05, 0.01, 10.0
MAX_SECONDS = 600
WINDOWS, RESET_GAP_NS = (5, 15, 30), 5 * task.SECOND
FLAGS = dict(balance.FLAGS)


def cost_matrix() -> np.ndarray:
    """Rows are actual joint states; columns are predicted states, not cash losses."""
    return np.asarray(
        [
            [
                sum(
                    0.0
                    if actual == predicted
                    else PENALTIES[
                        "missed_opportunity"
                        if predicted == "N"
                        else "no_opportunity_overcall"
                        if actual == "N"
                        else "wrong_side"
                    ]
                    for actual, predicted in zip(truth, forecast, strict=True)
                )
                / len(balance.COST_KEYS)
                for forecast in balance.STATES
            ]
            for truth in balance.STATES
        ],
        dtype=np.float64,
    )


def protocol() -> dict:
    return {
        "kind": KIND,
        "task": task.TASK,
        "role": "train",
        "features": list(task.FEATURES),
        "states": list(balance.STATES),
        "split": balance.protocol()["split"],
        "exposure": "Already-exposed within-training temporal development, not a holdout",
        "fit": "Every inner-fit row once per full-batch epoch; natural frequencies, no class "
        "weights, quotas, repeated minority sampling or check-session normalization",
        "models": MODES,
        "objective": "Mean joint cross entropy + strength * expected class penalty + "
        "0.5 * l2 * squared weight norm; no bias regularization",
        "class_penalties": PENALTIES,
        "matrix_actual_by_predicted": cost_matrix().tolist(),
        "penalty_units": "Arbitrary research classification units, NOT ticks, money or PnL; "
        "average of the three cost-class errors, not three independent trade returns",
        "optimization": {
            "epochs": EPOCHS,
            "learning_rate": LEARNING_RATE,
            "l2": L2,
            "standardized_clip": CLIP,
            "initialization": "Zero weights and Laplace-smoothed natural inner-fit log priors",
            "standardization": "Inner-fit population means/std only; constant scale one",
        },
        "decisions": "Same coherent joint-state argmax and fixed tie order for both models; "
        "no cost-sensitive decision threshold, search, early stop or winner selection",
        "evaluation": "Every inner-check row; pooled/per-session existing class metrics, "
        "false no-opportunity calls, wrong-side calls, missed opportunities and penalty; "
        "include fixed no-opportunity and inner-fit-prior controls",
        "probabilities": "Risk-regularized softmax scores are not calibrated probabilities",
        "context_audit": {
            "windows_seconds": list(WINDOWS),
            "reset_gap_seconds": RESET_GAP_NS // task.SECOND,
            "inputs": "Training role and session/contract/timestamp only, no features or targets",
            "semantics": "Timestamp-only upper bound on prior observations in [now-window, "
            "now); fresh per session, clear on gap >5s, publish current after counting",
            "limitation": "The dense context engine also resets on causal prior-quote gaps; "
            "this audit cannot certify usable context, but zero proves none from these rows",
            "forbidden": "Interpolation, forward fill, cross-session history or claiming "
            "sparse snapshots are a dense LOB encoder",
        },
        "bounds": {"seconds": MAX_SECONDS, "examples": task.MAX_CASES},
        **FLAGS,
    }


def source_sha256() -> str:
    return digest(
        {
            "frozen_train_only_tools": balance.source_sha256(),
            Path(__file__).name: hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "causal_6e_context.py": hashlib.sha256(
                Path(__file__).with_name("causal_6e_context.py").read_bytes()
            ).hexdigest(),
        }
    )


def context_audit(rows: list[dict]) -> dict:
    if not rows or len(rows) > task.MAX_CASES:
        raise ValueError("Bounded training timestamps required")
    history = {window: deque() for window in WINDOWS}
    counts = dict.fromkeys(WINDOWS, 0)
    gaps, sessions, resets, previous, session = [], set(), 0, None, None
    for row in rows:
        if row["role"] != "train":  # Before any other payload access.
            raise ValueError("Only train-role context timestamps allowed")
        identity = task.identity(row)
        now, day = identity["decision_ts_ns"], identity["source_session"]
        if task.role_for_session(day) != "train":
            raise ValueError("Context date is not in training")
        if previous is not None and now - previous < task.SECOND:
            raise ValueError("Context timestamps regress, duplicate or violate 1s spacing")
        if day != session:
            sessions.add(day)
            for queue in history.values():
                queue.clear()
        else:
            gaps.append(now - previous)
            if now - previous > RESET_GAP_NS:
                resets += 1
                for queue in history.values():
                    queue.clear()
        for window, queue in history.items():
            while queue and queue[0] < now - window * task.SECOND:
                queue.popleft()
            counts[window] += bool(queue)
            queue.append(now)
        previous, session = now, day
    return {
        "rows": len(rows),
        "source_sessions": len(sessions),
        "same_session_intervals": len(gaps),
        "minimum_spacing_seconds": min(gaps) / task.SECOND if gaps else None,
        "median_spacing_seconds": float(np.median(gaps)) / task.SECOND if gaps else None,
        "maximum_spacing_seconds": max(gaps) / task.SECOND if gaps else None,
        "gap_resets": resets,
        "rows_with_prior_timestamp_upper_bound": {str(w): counts[w] for w in WINDOWS},
        "dense_context_reconstructed": False,
        "targets_accessed": False,
    }


def objective(logits, targets, strength: float) -> tuple[dict, np.ndarray]:
    """Stable loss and exact mean-loss derivative with respect to joint logits."""
    x = standardize.validate_feature_matrix(logits)
    y = np.asarray(targets)
    if (
        type(strength) is not float
        or strength not in MODES.values()
        or x.shape[1] != len(balance.STATES)
        or len(x) > task.MAX_CASES
        or y.shape != (len(x),)
        or y.dtype.kind not in "iu"
        or (y < 0).any()
        or (y >= len(balance.STATES)).any()
    ):
        raise ValueError("Fixed objective and aligned joint-state labels required")
    shifted = x - x.max(axis=1, keepdims=True)
    log_prob = shifted - np.log(np.exp(shifted).sum(axis=1, keepdims=True))
    p = np.exp(log_prob)
    costs = cost_matrix()[y]
    expected = (p * costs).sum(axis=1, keepdims=True)
    ce = float(-log_prob[np.arange(len(y)), y].mean())
    penalty = float(expected.mean())
    gradient = p.copy()
    gradient[np.arange(len(y)), y] -= 1.0
    gradient += strength * p * (costs - expected)
    gradient /= len(y)
    if not np.isfinite(gradient).all() or not np.isfinite([ce, penalty]).all():
        raise ValueError("Nonfinite objective or gradient")
    return {
        "cross_entropy": ce,
        "expected_class_penalty": penalty,
        "objective_without_l2": ce + strength * penalty,
    }, gradient


def fit(rows: list[dict], strength: float, *, deadline=None) -> dict:
    balance.validate_train(rows)
    if type(strength) is not float or strength not in MODES.values():
        raise ValueError("Only fixed objective controls allowed")
    x = np.asarray([balance.feature_values(row) for row in rows], dtype=np.float64)
    y = np.asarray([balance.STATES.index(balance.state_of(row)) for row in rows], dtype=np.int64)
    counts = np.bincount(y, minlength=len(balance.STATES))
    if (counts == 0).any():
        raise ValueError("Every joint state must occur in the inner-fit pool")
    scaler = standardize.fit_standardizer(x)
    x = np.clip(scaler.transform(x), -CLIP, CLIP)
    prior = (counts + 1) / (len(y) + len(counts))
    weights, bias = np.zeros((len(task.FEATURES), len(counts))), np.log(prior)
    for _ in range(EPOCHS):
        balance.deadline_guard(deadline)
        _, gradient = objective(x @ weights + bias, y, strength)
        weights -= LEARNING_RATE * (x.T @ gradient + L2 * weights)
        bias -= LEARNING_RATE * gradient.sum(axis=0)
    if not np.isfinite(weights).all() or not np.isfinite(bias).all():
        raise ValueError("Nonfinite fitted parameters")
    return {
        "strength": strength,
        "means": scaler.means.tolist(),
        "scales": scaler.scales.tolist(),
        "weights": weights.tolist(),
        "bias": bias.tolist(),
    }


def predict(model: dict, features) -> np.ndarray:
    _fields(model, ("strength", "means", "scales", "weights", "bias"))
    if type(model["strength"]) is not float or model["strength"] not in MODES.values():
        raise ValueError("Fixed objective control required")
    x = standardize.validate_feature_matrix(features)
    means, scales, weights, bias = (
        np.asarray(model[key], dtype=np.float64) for key in ("means", "scales", "weights", "bias")
    )
    columns = len(task.FEATURES)
    if (
        x.shape[1] != columns
        or len(x) > task.MAX_CASES
        or means.shape != (columns,)
        or scales.shape != (columns,)
        or weights.shape != (columns, len(balance.STATES))
        or bias.shape != (len(balance.STATES),)
        or any(not np.isfinite(v).all() for v in (means, scales, weights, bias))
        or (scales <= 0).any()
    ):
        raise ValueError("Bounded finite model/feature dimensions required")
    return balance.softmax(np.clip((x - means) / scales, -CLIP, CLIP) @ weights + bias)


def scores(rows: list[dict], probabilities: np.ndarray) -> dict:
    result = balance.scores(rows, probabilities)  # Validates probability bounds and alignment.
    actual = np.asarray([balance.STATES.index(balance.state_of(row)) for row in rows])
    predicted = probabilities.argmax(axis=1)
    by_cost = {}
    for index, key in enumerate(balance.COST_KEYS):
        pairs = [
            (balance.STATES[a][index], balance.STATES[p][index])
            for a, p in zip(actual, predicted, strict=True)
        ]
        counts = {
            "missed_opportunity": sum(a != "N" and p == "N" for a, p in pairs),
            "no_opportunity_overcall": sum(a == "N" and p != "N" for a, p in pairs),
            "wrong_side": sum(a != "N" and p != "N" and a != p for a, p in pairs),
        }
        by_cost[key] = {
            **counts,
            "incorrect_directional_calls": counts["no_opportunity_overcall"] + counts["wrong_side"],
            "mean_class_penalty": sum(PENALTIES[k] * v for k, v in counts.items()) / len(rows),
        }
    matrix = cost_matrix()
    result["class_penalty"] = {
        "by_cost": by_cost,
        "mean_argmax_penalty": float(matrix[actual, predicted].mean()),
        "mean_expected_penalty": float((probabilities * matrix[actual]).sum(axis=1).mean()),
        "units": "Research class-error units, not monetary returns",
    }
    return result


def make_plan(path: Path, pin: str) -> tuple[dict, dict, list[dict]]:
    prior, request, rows = balance.registration(path, pin)
    split = prior["session_split"]
    partitions = {}
    for name in ("fit", "check"):
        selected = [row for row in rows if row["source_session"] in split[name]]
        partitions[name] = {
            "examples": len(selected),
            "ordered_cases_sha256": digest([row["case_id"] for row in selected]),
            "counts": balance.audit(selected),
            "context": context_audit(selected),
        }
    return (
        {
            "kind": KIND,
            "protocol": protocol(),
            "source_sha256": source_sha256(),
            "cpu_runtime": balance.runtime(),
            "balance_registration": {"path": str(path.resolve()), "sha256": pin},
            "dataset": prior["dataset"],
            "session_split": split,
            "partitions": partitions,
            **FLAGS,
        },
        request,
        rows,
    )


def freeze(path: Path, pin: str, output: Path) -> dict:
    plan, request, _ = make_plan(path, pin)
    _disjoint(output, path, request, plan)
    _write(output, plan)
    return plan


def _disjoint(output: Path, registration_path: Path, request: dict, plan: dict) -> None:
    original = balance.trial.metadata(
        Path(plan["balance_registration"]["path"]), plan["balance_registration"]["sha256"]
    )["prior_trial"]["directory"]
    evaluation.disjoint(output, request, Path(original))
    if registration_path.resolve().is_relative_to(output.resolve()):
        raise ValueError("Output overlaps its registration")


def registration(path: Path, pin: str) -> tuple[dict, dict, list[dict]]:
    plan = balance.trial.metadata(path, pin)
    _fields(
        plan,
        (
            "kind",
            "protocol",
            "source_sha256",
            "cpu_runtime",
            "balance_registration",
            "dataset",
            "session_split",
            "partitions",
            *FLAGS,
        ),
    )
    _fields(plan["balance_registration"], ("path", "sha256"))
    prior = plan["balance_registration"]
    rebuilt, request, rows = make_plan(Path(prior["path"]), prior["sha256"])
    if canonical(plan) != canonical(rebuilt):
        raise ValueError("Frozen objective, inputs, split, context, runtime or authority changed")
    return plan, request, rows


def run(path: Path, pin: str, output: Path, *, enable_cpu_study=False) -> dict:
    if enable_cpu_study is not True:
        raise ValueError("Explicit offline CPU-study opt-in required")
    started = time.monotonic()
    deadline = started + MAX_SECONDS
    plan, request, rows = registration(path, pin)
    _disjoint(output, path, request, plan)
    output.mkdir(exist_ok=False)
    try:
        _write(
            output / "request.json",
            {
                "registration_sha256": pin,
                "source_sha256": source_sha256(),
                "cpu_runtime": balance.runtime(),
                **FLAGS,
            },
        )
        split = plan["session_split"]
        fit_rows = [row for row in rows if row["source_session"] in split["fit"]]
        check_rows = [row for row in rows if row["source_session"] in split["check"]]
        models = {
            name: fit(fit_rows, strength, deadline=deadline) for name, strength in MODES.items()
        }
        model_pin = digest(models)
        _write(output / "models.json", models)
        file_pin = evaluation.file_info(output / "models.json")
        x = np.asarray([balance.feature_values(row) for row in check_rows])
        probabilities = {name: predict(model, x) for name, model in models.items()}
        prior = np.asarray(
            [
                plan["partitions"]["fit"]["counts"]["joint_counts"][state] + 1
                for state in balance.STATES
            ],
            dtype=float,
        )
        prior /= prior.sum()
        probabilities["inner_fit_joint_prior"] = np.tile(prior, (len(check_rows), 1))
        probabilities["no_opportunity"] = np.tile(
            np.eye(len(balance.STATES))[0], (len(check_rows), 1)
        )
        pooled = {name: scores(check_rows, p) for name, p in probabilities.items()}
        per_session = {}
        for day in split["check"]:
            balance.deadline_guard(deadline)
            mask = np.asarray([row["source_session"] == day for row in check_rows])
            selected = [row for row, yes in zip(check_rows, mask, strict=True) if yes]
            per_session[day] = {
                name: scores(selected, p[mask]) for name, p in probabilities.items()
            }
        final_plan, _, final_rows = registration(path, pin)
        if (
            final_plan != plan
            or final_rows != rows
            or digest(models) != model_pin
            or evaluation.file_info(output / "models.json") != file_pin
        ):
            raise ValueError("Inputs or frozen model artifacts changed during study")
        balance.deadline_guard(deadline)
        result = {
            "status": "completed_train_only_direction_cost_study_not_validated",
            "registration_sha256": pin,
            "source_sha256": source_sha256(),
            "cpu_runtime": balance.runtime(),
            "models_file": file_pin,
            "models_content_sha256": model_pin,
            "fit_examples": len(fit_rows),
            "check_examples": len(check_rows),
            "fit_sessions": len(split["fit"]),
            "check_sessions": len(split["check"]),
            "scores": pooled,
            "per_session_scores": per_session,
            "context_audit": {name: value["context"] for name, value in plan["partitions"].items()},
            "elapsed_seconds": time.monotonic() - started,
            "cpu_controls_fitted": len(models),
            "models_quarantined": True,
            "winner_selected": False,
            "limitations": "Previously exposed resolved training labels only; observability "
            "selection bias remains. Penalized class scores are not calibrated probabilities, "
            "broker fills, PnL or a causal explanation. Abstention is not a trading edge.",
            **FLAGS,
        }
        _write(output / "run.json", result)
        return result
    except BaseException as exc:
        _write(
            output / "failure.json",
            {
                "status": "failed_no_partial_score",
                "error_type": type(exc).__name__,
                **FLAGS,
            },
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--balance-registration", type=Path)
    parser.add_argument("--balance-registration-sha256")
    parser.add_argument("--registration", type=Path)
    parser.add_argument("--registration-sha256")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enable-cpu-study", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        if args.balance_registration is None or args.balance_registration_sha256 is None:
            parser.error("Pinned original train-only balance registration required")
        result = freeze(args.balance_registration, args.balance_registration_sha256, args.output)
        print(canonical({"kind": result["kind"], "partitions": result["partitions"]}))
    else:
        if args.registration is None or args.registration_sha256 is None:
            parser.error("Pinned direction-cost registration required")
        result = run(
            args.registration,
            args.registration_sha256,
            args.output,
            enable_cpu_study=args.enable_cpu_study,
        )
        print(
            canonical(
                {
                    key: result[key]
                    for key in (
                        "status",
                        "fit_examples",
                        "check_examples",
                        "cpu_controls_fitted",
                        "elapsed_seconds",
                    )
                }
            )
        )


if __name__ == "__main__":
    main()
