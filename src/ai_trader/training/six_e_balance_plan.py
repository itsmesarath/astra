"""Train-only 6E imbalance study and CPU controls; Qwen recipe is planning only."""

from __future__ import annotations

import argparse
import hashlib
import platform
import sys
import time
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path

import numpy as np

from ai_trader.models.local_checkpoint import canonical, digest, strict_json
from ai_trader.research import six_e_forecast_eval as evaluation
from ai_trader.training import six_e_forecast as task
from ai_trader.training import six_e_lora_trial as trial
from ai_trader.training import standardize
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import _write

KIND = "six_e_train_only_joint_balance_study_v1"
COST_KEYS = evaluation.COST_KEYS
STATES = ("NNN", "LNN", "LLN", "LLL", "SNN", "SSN", "SSS")
LABELS = {"N": "neither_positive", "L": "long_positive", "S": "short_positive"}
SAMPLES_PER_STATE, EPOCHS, MAX_SECONDS = 32, 200, 600
LEARNING_RATE, L2, CLIP = 0.05, 0.01, 10.0
MODES = {"joint_linear_unweighted": 0.0, "joint_linear_inverse_sqrt": 0.5}
FLAGS = {
    "qwen_training_authorized": False,
    "qwen_training_performed": False,
    "independent_holdout": False,
    "reserved_outcomes_opened": False,
    "promotion_allowed": False,
    "trading_enabled": False,
    "adapter_approved_for_deployment": False,
    "automatic_retry": False,
}


def forecast(state: str) -> dict:
    if state not in STATES:
        raise ValueError("Only coherent joint cost states allowed")
    return dict(zip(COST_KEYS, (LABELS[c] for c in state), strict=True))


def state_of(row: dict) -> str:
    target = task.parse_completion(row["completion"])
    reverse = {v: k for k, v in LABELS.items()}
    state = "".join(reverse[target[key]] for key in COST_KEYS)
    if state not in STATES:
        raise ValueError("Unknown coherent target state")
    return state


def protocol() -> dict:
    return {
        "kind": KIND,
        "task": task.TASK,
        "role": "train",
        "joint_states": {state: forecast(state) for state in STATES},
        "features": list(task.FEATURES),
        "split": "Sorted whole training sessions: first n-floor(n/4) fit; last floor(n/4) check",
        "minimum_sessions": 8,
        "check_exposure": "Within-training temporal development, already exposed; NOT independent",
        "qwen_curriculum": {
            "examples_per_joint_state": SAMPLES_PER_STATE,
            "examples": len(STATES) * SAMPLES_PER_STATE,
            "pool": "Inner fit sessions ONLY; exclude every inner check session",
            "selection": "Training labels only. Spread quota over whole sessions, then even row "
            "ranks within each selected session; no duplicate cases or resampling",
            "order": "Round robin over fixed joint-state order",
            "initialization": "Fresh pinned base checkpoint; do NOT resume the twenty-update "
            "adapter, which has already seen some inner check sessions",
            "recipe": {
                **trial.token_plan.proposed_recipe(),
                "max_optimizer_steps": len(STATES) * SAMPLES_PER_STATE,
                "max_wall_time_seconds": 1800,
                "limits_enforced_by_training_worker": False,
            },
            "native_runner_implemented": False,
            "warning": "Uniform joint-state quotas change class priors and can increase false "
            "directional signals. This plan is not training or deployment approval.",
        },
        "cpu_controls": {
            "modes": MODES,
            "fit": "All inner fit rows, not the balanced Qwen subset",
            "epochs": EPOCHS,
            "learning_rate": LEARNING_RATE,
            "l2": L2,
            "standardized_clip": CLIP,
            "normalization": "Population mean/std from inner fit features only; constant scale 1",
            "initialization": "Zero weights, Laplace-smoothed weighted inner-fit class log prior",
            "weights": "(n/(7*class_count))**power, normalized to training mean one",
            "decisions": "Joint-state argmax; fixed tie order; no threshold tuning or early stop",
            "probabilities": "Reweighted scores are not calibrated market probabilities",
            "seconds": MAX_SECONDS,
        },
        "metrics": "Pooled and per-session cost-class metrics, joint log loss and Brier score; "
        "no quote magnitudes, broker execution economics, PnL or causal attribution",
        "controls": ["no_opportunity", "inner_fit_joint_prior", *MODES],
        **FLAGS,
    }


def source_sha256() -> str:
    return digest(
        {
            "frozen_forecast_tools": evaluation.source_sha256(),
            **{
                Path(module.__file__).name: hashlib.sha256(
                    Path(module.__file__).read_bytes()
                ).hexdigest()
                for module in (sys.modules[__name__], standardize)
            },
        }
    )


def runtime() -> dict:
    return {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "numpy": version("numpy"),
    }


def validate_train(rows: list[dict]) -> None:
    if not rows or len(rows) > task.MAX_CASES:
        raise ValueError("Complete bounded training examples required")
    previous = None
    for row in rows:
        task.model_view(row, for_training=True)  # Gate role before prompt or outcome access.
        if previous is not None and row["decision_ts_ns"] <= previous:
            raise ValueError("Unique chronological training examples required")
        previous = row["decision_ts_ns"]


def session_split(rows: list[dict]) -> dict:
    validate_train(rows)
    sessions = sorted({row["source_session"] for row in rows})
    if len(sessions) < 8:
        raise ValueError("At least eight whole training sessions required")
    cut = len(sessions) - len(sessions) // 4
    return {"fit": sessions[:cut], "check": sessions[cut:]}


def audit(rows: list[dict]) -> dict:
    counts = Counter(state_of(row) for row in rows)
    return {
        "examples": len(rows),
        "source_sessions": len({row["source_session"] for row in rows}),
        "joint_counts": {state: counts[state] for state in STATES},
        "joint_session_support": {
            state: len({row["source_session"] for row in rows if state_of(row) == state})
            for state in STATES
        },
        "by_cost": {
            key: {
                cls: sum(forecast(s)[key] == cls and counts[s] for s in STATES)
                for cls in task.CLASSES
            }
            for key in COST_KEYS
        },
    }


def even_indices(count: int, quota: int) -> list[int]:
    if type(count) is not int or type(quota) is not int or not 1 <= quota <= count:
        raise ValueError("Unique bounded rank selection required")
    return (
        [(count - 1) // 2] if quota == 1 else [i * (count - 1) // (quota - 1) for i in range(quota)]
    )


def curriculum(rows: list[dict], split: dict) -> list[dict]:
    validate_train(rows)
    if split != session_split(rows):
        raise ValueError("Frozen whole-session split differs")
    pools = {state: defaultdict(list) for state in STATES}
    for index, row in enumerate(rows):
        if row["source_session"] in split["fit"]:
            pools[state_of(row)][row["source_session"]].append((index, row))
    selections = {}
    for state, groups in pools.items():
        if sum(map(len, groups.values())) < SAMPLES_PER_STATE:
            raise ValueError("Every joint state needs thirty-two unique inner fit examples")
        sessions = sorted(groups)
        allocation = dict.fromkeys(sessions, 0)
        if len(sessions) >= SAMPLES_PER_STATE:
            for index in even_indices(len(sessions), SAMPLES_PER_STATE):
                allocation[sessions[index]] = 1
        else:
            remaining = SAMPLES_PER_STATE
            while remaining:
                for session in sessions:
                    if remaining and allocation[session] < len(groups[session]):
                        allocation[session] += 1
                        remaining -= 1
        selected = []
        for session, quota in allocation.items():
            if quota:
                selected.extend(
                    groups[session][i] for i in even_indices(len(groups[session]), quota)
                )
        selections[state] = [
            {
                "example_index": index,
                "joint_state": state,
                **{
                    key: row[key]
                    for key in ("case_id", "source_session", "input_sha256", "target_sha256")
                },
            }
            for index, row in selected
        ]
    result = [selections[state][i] for i in range(SAMPLES_PER_STATE) for state in STATES]
    if len({row["case_id"] for row in result}) != len(result):
        raise ValueError("Repeated curriculum cases refused")
    return result


def make_plan(directory: Path, request_pin: str, report_pin: str) -> tuple[dict, dict, list[dict]]:
    request, receipt = evaluation.verified_trial(directory, request_pin, report_pin)
    rows = list(evaluation.rows(Path(request["dataset"]), "train", receipt))
    split = session_split(rows)
    fit = [row for row in rows if row["source_session"] in split["fit"]]
    check = [row for row in rows if row["source_session"] in split["check"]]
    old_cases = {item["case_id"] for item in request["selection"]}
    plan = {
        "kind": KIND,
        "protocol": protocol(),
        "source_sha256": source_sha256(),
        "cpu_runtime": runtime(),
        "prior_trial": {
            "directory": str(directory.resolve()),
            "request_sha256": request_pin,
            "report_sha256": report_pin,
        },
        "dataset": {
            "directory": request["dataset"],
            "completion_sha256": request["dataset_sha256"],
            "train_file": receipt["files"]["train.jsonl"],
        },
        "session_split": split,
        "audits": {
            "all_train": audit(rows),
            "inner_fit": audit(fit),
            "inner_check": audit(check),
            "original_twenty": audit([row for row in rows if row["case_id"] in old_cases]),
        },
        "curriculum": curriculum(rows, split),
        **FLAGS,
    }
    return plan, request, rows


def freeze(directory: Path, request_pin: str, report_pin: str, output: Path) -> dict:
    plan, request, _ = make_plan(directory, request_pin, report_pin)
    evaluation.disjoint(output, request, directory)
    _write(output, plan)
    return plan


def registration(path: Path, pin: str) -> tuple[dict, dict, list[dict]]:
    plan = trial.metadata(path, pin)
    _fields(
        plan,
        (
            "kind",
            "protocol",
            "source_sha256",
            "cpu_runtime",
            "prior_trial",
            "dataset",
            "session_split",
            "audits",
            "curriculum",
            *FLAGS,
        ),
    )
    if plan["protocol"] != protocol() or plan["source_sha256"] != source_sha256():
        raise ValueError("Frozen train-only protocol or source changed")
    _fields(plan["prior_trial"], ("directory", "request_sha256", "report_sha256"))
    prior = plan["prior_trial"]
    rebuilt, request, rows = make_plan(
        Path(prior["directory"]), prior["request_sha256"], prior["report_sha256"]
    )
    if canonical(plan) != canonical(rebuilt):
        raise ValueError("Frozen curriculum, split, accounting, runtime or authority changed")
    return plan, request, rows


def feature_values(row: dict) -> list[float]:
    # A prediction input must not read completion, future fields, role, session or contract.
    text = row["prompt"]
    if type(text) is not str or not text.startswith(task.PREFIX) or not text.endswith(task.SUFFIX):
        raise ValueError("Fixed feature prompt required")
    values = strict_json(text[len(task.PREFIX) : -len(task.SUFFIX)])
    if text != task.prompt(values):
        raise ValueError("Canonical causal features required")
    return [values[key] for key in task.FEATURES]


def softmax(scores: np.ndarray) -> np.ndarray:
    probabilities = np.exp(scores - scores.max(axis=1, keepdims=True))
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    if not np.isfinite(probabilities).all():
        raise ValueError("Nonfinite joint probabilities")
    return probabilities


def deadline_guard(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("CPU study budget exhausted; no partial scores")


def fit(rows: list[dict], weight_power: float, *, deadline=None) -> dict:
    validate_train(rows)
    if type(weight_power) is not float or weight_power not in MODES.values():
        raise ValueError("Only preregistered class-weight controls allowed")
    x = np.asarray([feature_values(row) for row in rows], dtype=np.float64)
    y = np.asarray([STATES.index(state_of(row)) for row in rows], dtype=np.int64)
    counts = np.bincount(y, minlength=len(STATES))
    if (counts == 0).any():
        raise ValueError("Every joint state must occur in the inner fit pool")
    scaler = standardize.fit_standardizer(x)
    x = np.clip(scaler.transform(x), -CLIP, CLIP)
    class_weights = (len(y) / (len(STATES) * counts)) ** weight_power
    sample_weights = class_weights[y]
    sample_weights /= sample_weights.mean()
    prior = counts * class_weights + 1
    prior /= prior.sum()
    weights, bias = np.zeros((len(task.FEATURES), len(STATES))), np.log(prior)
    for _ in range(EPOCHS):
        deadline_guard(deadline)
        error = softmax(x @ weights + bias)
        error[np.arange(len(y)), y] -= 1
        error *= sample_weights[:, None]
        weights -= LEARNING_RATE * (x.T @ error / len(y) + L2 * weights)
        bias -= LEARNING_RATE * error.mean(axis=0)
    if not np.isfinite(weights).all() or not np.isfinite(bias).all():
        raise ValueError("Nonfinite fitted parameters")
    return {
        "weight_power": weight_power,
        "means": scaler.means.tolist(),
        "scales": scaler.scales.tolist(),
        "weights": weights.tolist(),
        "bias": bias.tolist(),
    }


def predict(model: dict, features) -> np.ndarray:
    _fields(model, ("weight_power", "means", "scales", "weights", "bias"))
    if type(model["weight_power"]) is not float or model["weight_power"] not in MODES.values():
        raise ValueError("Unexpected model control")
    x = standardize.validate_feature_matrix(features)
    means, scales, weights, bias = (
        np.asarray(model[k], dtype=np.float64) for k in ("means", "scales", "weights", "bias")
    )
    columns = len(task.FEATURES)
    if (
        x.shape[1] != columns
        or means.shape != (columns,)
        or scales.shape != (columns,)
        or weights.shape != (columns, len(STATES))
        or bias.shape != (len(STATES),)
        or any(not np.isfinite(a).all() for a in (means, scales, weights, bias))
        or (scales <= 0).any()
    ):
        raise ValueError("Bounded finite model/feature dimensions required")
    return softmax(np.clip((x - means) / scales, -CLIP, CLIP) @ weights + bias)


def scores(rows: list[dict], probabilities: np.ndarray) -> dict:
    if (
        probabilities.shape != (len(rows), len(STATES))
        or not np.isfinite(probabilities).all()
        or (probabilities < 0).any()
        or (probabilities > 1).any()
        or not np.allclose(probabilities.sum(axis=1), 1, rtol=0, atol=1e-12)
    ):
        raise ValueError("Aligned finite joint probabilities required")
    truth = [task.parse_completion(row["completion"]) for row in rows]
    y = np.asarray([STATES.index(state_of(row)) for row in rows], dtype=np.int64)
    predictions = [forecast(STATES[index]) for index in probabilities.argmax(axis=1)]
    return {
        **evaluation.metrics(truth, predictions),
        "joint_log_loss": float(
            -np.log(np.maximum(probabilities[np.arange(len(y)), y], 1e-15)).mean()
        ),
        "joint_brier_score": float(
            ((probabilities - np.eye(len(STATES))[y]) ** 2).sum(axis=1).mean()
        ),
    }


def run(path: Path, pin: str, output: Path, *, enable_cpu_controls=False) -> dict:
    if enable_cpu_controls is not True:
        raise ValueError("Explicit offline CPU-controls opt-in required")
    plan, request, rows = registration(path, pin)
    evaluation.disjoint(output, request, Path(plan["prior_trial"]["directory"]))
    output.mkdir(exist_ok=False)
    started = time.monotonic()
    deadline = started + MAX_SECONDS
    try:
        _write(
            output / "request.json", {"registration_sha256": pin, "source_sha256": source_sha256()}
        )
        split = plan["session_split"]
        fit_rows = [row for row in rows if row["source_session"] in split["fit"]]
        check_rows = [row for row in rows if row["source_session"] in split["check"]]
        x = np.asarray([feature_values(row) for row in check_rows], dtype=np.float64)
        models = {name: fit(fit_rows, power, deadline=deadline) for name, power in MODES.items()}
        probabilities = {name: predict(model, x) for name, model in models.items()}
        prior = np.asarray(
            [plan["audits"]["inner_fit"]["joint_counts"][s] + 1 for s in STATES], dtype=float
        )
        prior /= prior.sum()
        probabilities["inner_fit_joint_prior"] = np.tile(prior, (len(check_rows), 1))
        probabilities["no_opportunity"] = np.tile(np.eye(len(STATES))[0], (len(check_rows), 1))
        pooled = {name: scores(check_rows, p) for name, p in probabilities.items()}
        per_session = {}
        for session in split["check"]:
            mask = np.asarray([row["source_session"] == session for row in check_rows])
            selected = [row for row, yes in zip(check_rows, mask, strict=True) if yes]
            per_session[session] = {
                name: scores(selected, p[mask]) for name, p in probabilities.items()
            }
        final_plan, _, final_rows = registration(path, pin)
        deadline_guard(deadline)
        if final_plan != plan or final_rows != rows:
            raise ValueError("Training-only inputs changed during CPU study")
        _write(output / "models.json", models)
        report = {
            "status": "completed_within_train_temporal_development_controls_not_validated",
            "registration_sha256": pin,
            "source_sha256": source_sha256(),
            "cpu_runtime": runtime(),
            "cpu_controls_fitted": len(models),
            "fit_examples": len(fit_rows),
            "check_examples": len(check_rows),
            "fit_sessions": len(split["fit"]),
            "check_sessions": len(split["check"]),
            "models_file": evaluation.file_info(output / "models.json"),
            "model_content_sha256": digest(models),
            "scores": pooled,
            "per_session_scores": per_session,
            "elapsed_seconds": time.monotonic() - started,
            "models_quarantined": True,
            "limitations": "Only already-exposed training-partition labels. Class proxies, "
            "not PnL or calibrated broker probabilities. No Qwen fit or automatic promotion.",
            **FLAGS,
        }
        _write(output / "run.json", report)
        return report
    except BaseException as exc:
        _write(
            output / "failure.json",
            {"status": "failed_no_partial_score", "error_type": type(exc).__name__, **FLAGS},
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--trial-directory", type=Path)
    parser.add_argument("--trial-request-sha256")
    parser.add_argument("--trial-report-sha256")
    parser.add_argument("--registration", type=Path)
    parser.add_argument("--registration-sha256")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enable-cpu-controls", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        if any(
            v is None
            for v in (args.trial_directory, args.trial_request_sha256, args.trial_report_sha256)
        ):
            parser.error("Pinned original training trial required")
        result = freeze(
            args.trial_directory, args.trial_request_sha256, args.trial_report_sha256, args.output
        )
        print(canonical({"kind": result["kind"], "curriculum_examples": len(result["curriculum"])}))
    else:
        if args.registration is None or args.registration_sha256 is None:
            parser.error("Pinned training-only registration required")
        result = run(
            args.registration,
            args.registration_sha256,
            args.output,
            enable_cpu_controls=args.enable_cpu_controls,
        )
        print(
            canonical(
                {
                    key: result[key]
                    for key in ("status", "fit_examples", "check_examples", "cpu_controls_fitted")
                }
            )
        )


if __name__ == "__main__":
    main()
