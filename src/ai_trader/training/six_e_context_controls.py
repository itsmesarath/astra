"""Natural-prior context-v2 CPU controls on all inner-fit/check cases; never Qwen or orders."""

from __future__ import annotations

import argparse
import hashlib
import time
from collections import Counter
from pathlib import Path

import numpy as np

from ai_trader.models.local_checkpoint import canonical, check_digest, digest, strict_json
from ai_trader.research import six_e_forecast_eval as metrics_tool
from ai_trader.training import six_e_context_lora as training
from ai_trader.training import standardize
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import _absolute, _event, _write

task, tokens, balance = training.task, training.tokens, training.legacy.balance
KIND = "six_e_context_v2_natural_full_inner_check_controls"
LINEAR = "natural_context_joint_linear"
NAMES = ("no_opportunity", "inner_fit_joint_prior", LINEAR)
MAX_SECONDS, MAX_BYTES, MAX_LINE = 600, 32 * 1024**2, 32 * 1024
FLAGS = {k: v for k, v in metrics_tool.FLAGS.items() if k != "training_performed"}
FLAGS["qwen_training_performed"] = False


def specification() -> dict:
    return training.protocol()["comparison"]["linear"]


def protocol() -> dict:
    return {
        "kind": KIND,
        "pre_training_comparison": training.protocol()["comparison"],
        "cpu_seconds": MAX_SECONDS,
        "fit": "ALL inner-fit only, gate role/partition/session before prompt or target",
        "check": "ALL original inner-check examples, never subset or used by fit/scaler",
        "prediction": "Fixed seven-state argmax tie order; no calibration or threshold search",
        "outputs": "Durable 200-epoch journal, coefficients, every check/control prediction, "
        "pooled AND every-session metrics. Invalid predictions are not abstentions.",
        "registration_authorizes_execution": False,
        **FLAGS,
    }


def source_sha256() -> str:
    return digest(
        {
            "immutable_training": training.source_sha256(),
            "immutable_metrics": metrics_tool.source_sha256(),
            **{
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (Path(__file__), Path(standardize.__file__))
            },
        }
    )


def file_info(path: Path, limit=MAX_BYTES) -> dict:
    return metrics_tool.file_info(path, limit)


def lines(path: Path, info: dict) -> list[dict]:
    _fields(info, ("bytes", "sha256"))
    if file_info(path) != info:
        raise ValueError("Complete bounded artifact pin differs")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if (
        len(raw) > MAX_BYTES
        or not raw.endswith(b"\n")
        or hashlib.sha256(raw).hexdigest() != info["sha256"]
    ):
        raise ValueError("Complete bounded artifact framing required")
    if any(len(line) > MAX_LINE for line in raw.splitlines()):
        raise ValueError("Artifact line budget exceeded")
    return [strict_json(line) for line in raw.splitlines()]


def gate(rows: list[dict], partition: str, split: dict) -> None:
    if partition not in task.PARTITIONS or not 1 <= len(rows) <= task.snapshot.MAX_CASES:
        raise ValueError("Complete nonempty bounded inner partition required")
    ids, previous = set(), None
    for row in rows:
        if (
            row["role"] != "train"
            or row["inner_partition"] != partition
            or row["source_session"] not in split[partition]
        ):
            raise ValueError("Role/partition/session gate before feature or target access")
        task.model_view(row, for_training=(partition == "fit"))
        if row["case_id"] in ids or (previous is not None and row["decision_ts_ns"] <= previous):
            raise ValueError("Unique chronological full partition required")
        ids.add(row["case_id"])
        previous = row["decision_ts_ns"]
    if {r["source_session"] for r in rows} != set(split[partition]):
        raise ValueError("Every original inner session required")


def feature_values(row: dict) -> list[float]:
    # Never access target, role, date, future eligibility or exact contract here.
    value = task.payload_from_prompt(row["prompt"])
    return [
        *value["current"],
        *[
            item
            for window, past in zip(task.WINDOWS, value["past"], strict=True)
            for item in (past[0] / window, *past[1:])
        ],
    ]


def state_of(row: dict) -> str:
    return balance.state_of(row)


def detailed_metrics(truth: list[dict], forecasts: list[dict | None]) -> dict:
    value = metrics_tool.metrics(truth, forecasts)
    for score in value["by_cost"].values():
        matrix = score["confusion"]
        long, short, neither = task.snapshot.CLASSES
        wrong = matrix[long][short] + matrix[short][long]
        overcalls = matrix[neither][long] + matrix[neither][short]
        abstained = matrix[long][neither] + matrix[short][neither]
        invalid = matrix[long]["invalid"] + matrix[short]["invalid"]
        score.update(
            directional_predictions=sum(score["per_class"][c]["predicted"] for c in (long, short)),
            correct_directional_predictions=sum(
                score["per_class"][c]["true_positive"] for c in (long, short)
            ),
            wrong_side_predictions=wrong,
            no_opportunity_overcalls=overcalls,
            missed_opportunities=wrong + abstained + invalid,
            missed_as_no_opportunity=abstained,
            missed_as_invalid=invalid,
        )
    return value


def scores(rows: list[dict], predictions: dict[str, list[dict | None]]) -> dict:
    truth = [task.snapshot.parse_completion(r["completion"]) for r in rows]
    pooled = {name: detailed_metrics(truth, values) for name, values in predictions.items()}
    per_session = {}
    for session in sorted({r["source_session"] for r in rows}):
        indices = [i for i, r in enumerate(rows) if r["source_session"] == session]
        per_session[session] = {
            name: detailed_metrics([truth[i] for i in indices], [values[i] for i in indices])
            for name, values in predictions.items()
        }
    return {
        "scores": pooled,
        "per_session_scores": per_session,
        "truth_joint_counts": dict(Counter(state_of(r) for r in rows)),
    }


def guard(deadline: float | None) -> None:
    balance.deadline_guard(deadline)


def fit(rows: list[dict], split: dict, *, deadline=None, epoch_sink=None) -> dict:
    gate(rows, "fit", split)  # Gate all rows before any native feature/target tensor.
    spec = specification()
    x = np.asarray([feature_values(row) for row in rows], dtype=np.float64)
    y = np.asarray([balance.STATES.index(state_of(row)) for row in rows], dtype=np.int64)
    counts = np.bincount(y, minlength=len(balance.STATES))
    scaler = standardize.fit_standardizer(x)
    x = np.clip(scaler.transform(x), -spec["standardized_clip"], spec["standardized_clip"])
    prior = (counts + 1) / (len(y) + len(balance.STATES))
    weights, bias = np.zeros((spec["columns"], len(balance.STATES))), np.log(prior)
    for epoch in range(1, spec["epochs"] + 1):
        guard(deadline)
        if epoch_sink:
            epoch_sink({"event": "epoch_intent", "epoch": epoch})
        probabilities = balance.softmax(x @ weights + bias)
        loss = float(-np.log(np.maximum(probabilities[np.arange(len(y)), y], 1e-15)).mean())
        error = probabilities.copy()
        error[np.arange(len(y)), y] -= 1
        weights -= spec["learning_rate"] * (x.T @ error / len(y) + spec["l2"] * weights)
        bias -= spec["learning_rate"] * error.mean(axis=0)
        training.finite_nonnegative([loss])
        if not np.isfinite(weights).all() or not np.isfinite(bias).all():
            raise ValueError("Nonfinite fixed CPU fit")
        if epoch_sink:
            epoch_sink({"event": "epoch_completed", "epoch": epoch, "loss": loss})
    guard(deadline)
    model = {
        "specification": spec,
        "means": scaler.means.tolist(),
        "scales": scaler.scales.tolist(),
        "weights": weights.tolist(),
        "bias": bias.tolist(),
    }
    predict(model, [feature_values(rows[0])])
    return model


def predict(model: dict, features) -> np.ndarray:
    _fields(model, ("specification", "means", "scales", "weights", "bias"))
    if canonical(model["specification"]) != canonical(specification()):
        raise ValueError("Preregistered natural unweighted CPU specification required")
    x = standardize.validate_feature_matrix(features)
    means, scales, weights, bias = [
        np.asarray(model[k], dtype=np.float64) for k in ("means", "scales", "weights", "bias")
    ]
    columns, states = specification()["columns"], len(balance.STATES)
    if (
        x.shape[1] != columns
        or means.shape != (columns,)
        or scales.shape != (columns,)
        or weights.shape != (columns, states)
        or bias.shape != (states,)
        or any(not np.isfinite(a).all() for a in (means, scales, weights, bias))
        or (scales <= 0).any()
    ):
        raise ValueError("Finite fixed coefficient/scaler dimensions required")
    return balance.softmax(
        np.clip(
            (x - means) / scales,
            -specification()["standardized_clip"],
            specification()["standardized_clip"],
        )
        @ weights
        + bias
    )


def all_predictions(value: dict, model: dict, chosen: list[dict]) -> list[dict]:
    gate(chosen, "check", value["session_split"])
    probabilities = predict(model, [feature_values(r) for r in chosen])
    state = max(balance.STATES, key=lambda s: value["fit_joint_counts"][s] + 1)
    result = []
    for index, row in enumerate(chosen):
        forecasts = (
            balance.forecast("NNN"),
            balance.forecast(state),
            balance.forecast(balance.STATES[probabilities[index].argmax()]),
        )
        for name, forecast in zip(NAMES, forecasts, strict=True):
            result.append(
                {
                    "case_id": row["case_id"],
                    "input_sha256": row["input_sha256"],
                    "control": name,
                    "forecast": forecast,
                }
            )
    return result


def comparison_rows(value: dict) -> list[dict]:
    directory = Path(value["inputs"]["dataset"]["path"])
    receipt = tokens.verified_receipt(directory, value["inputs"]["dataset"]["sha256"])
    chosen = [r for r, _, _ in tokens.read_examples(directory, "check", receipt)]
    gate(chosen, "check", value["session_split"])
    expected = {
        "cases": len(chosen),
        "sessions": len(value["session_split"]["check"]),
        "file": receipt["files"]["check.jsonl"],
        "ordered_examples_sha256": digest([digest(r) for r in chosen]),
    }
    if canonical(expected) != canonical(value["comparison"]):
        raise ValueError("ALL original pre-training comparison cases required")
    return chosen


def make_registration(path: Path, pin: str) -> tuple[dict, dict, list[dict], list[dict]]:
    value, fit_rows = training.registration(path, pin)
    gate(fit_rows, "fit", value["session_split"])
    chosen = comparison_rows(value)
    return (
        {
            "kind": KIND,
            "protocol": protocol(),
            "source_sha256": source_sha256(),
            "training_registration": {"path": str(path.resolve()), "sha256": pin},
            "cpu_runtime": balance.runtime(),
            "fit_examples": len(fit_rows),
            "fit_joint_counts": value["fit_joint_counts"],
            "comparison": value["comparison"],
            **FLAGS,
        },
        value,
        fit_rows,
        chosen,
    )


def freeze(path: Path, pin: str, output: Path) -> dict:
    registered, value, _, _ = make_registration(path, pin)
    training.disjoint(output, value)
    if output.resolve() == path.resolve():
        raise ValueError("Training registration cannot be overwritten")
    _write(output, registered)
    return registered


def registration(path: Path, pin: str):
    registered = tokens.metadata(path, pin)
    _fields(
        registered,
        (
            "kind",
            "protocol",
            "source_sha256",
            "training_registration",
            "cpu_runtime",
            "fit_examples",
            "fit_joint_counts",
            "comparison",
            *FLAGS,
        ),
    )
    _fields(registered["training_registration"], ("path", "sha256"))
    parent = registered["training_registration"]
    rebuilt, value, fit_rows, chosen = make_registration(
        _absolute(parent["path"]), parent["sha256"]
    )
    if canonical(registered) != canonical(rebuilt):
        raise ValueError("Frozen CPU protocol/runtime/full inputs or authority changed")
    return registered, value, fit_rows, chosen


def run(path: Path, pin: str, output: Path, *, enable_cpu_controls=False) -> dict:
    if enable_cpu_controls is not True:
        raise ValueError("Explicit fixed offline CPU-controls opt-in required")
    registered, value, fit_rows, chosen = registration(path, pin)
    training.disjoint(output, value)
    if path.resolve().is_relative_to(output.resolve()):
        raise ValueError("Output cannot overlap controls registration")
    output.mkdir(exist_ok=False)
    started, stage = time.monotonic(), "cpu_fit"
    try:
        _write(
            output / "request.json", {"registration_sha256": pin, "source_sha256": source_sha256()}
        )
        with (output / "epochs.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            model = fit(
                fit_rows,
                value["session_split"],
                deadline=started + MAX_SECONDS,
                epoch_sink=lambda event: _event(stream, event),
            )
        _write(output / "model.json", model)
        stage = "full_check_controls"
        predictions = all_predictions(value, model, chosen)
        with (output / "predictions.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for row in predictions:
                guard(started + MAX_SECONDS)
                _event(stream, row)
        parsed = {
            name: [r["forecast"] for r in predictions if r["control"] == name] for name in NAMES
        }
        score = scores(chosen, parsed)
        stage = "post_run_pins"
        final, _, final_fit, final_chosen = registration(path, pin)
        if final != registered or final_fit != fit_rows or final_chosen != chosen:
            raise ValueError("Frozen inputs/runtime drift during fixed controls run")
        guard(started + MAX_SECONDS)
        report = {
            "status": "completed_full_inner_check_controls_not_validation",
            "registration_sha256": pin,
            "source_sha256": source_sha256(),
            "cpu_runtime": balance.runtime(),
            "cpu_fit_performed": True,
            "epochs": specification()["epochs"],
            "fit_examples": len(fit_rows),
            "check_examples": len(chosen),
            "source_sessions": len(value["session_split"]["check"]),
            "completed_predictions": len(predictions),
            "files": {
                name: file_info(output / name)
                for name in ("request.json", "model.json", "epochs.jsonl", "predictions.jsonl")
            },
            "elapsed_seconds": time.monotonic() - started,
            **score,
            **FLAGS,
        }
        _write(output / "run.json", report)
        return report
    except BaseException as exc:
        _write(
            output / "failure.json",
            {
                "status": "failed_no_partial_scores",
                "stage": stage,
                "error_type": type(exc).__name__,
                **FLAGS,
            },
        )
        raise


def verified_run(path: Path, pin: str, directory: Path, report_pin: str):
    registered, value, fit_rows, chosen = registration(path, pin)
    if directory.is_symlink() or (directory / "failure.json").exists():
        raise ValueError("Completed regular CPU controls run required")
    report = tokens.metadata(directory / "run.json", report_pin)
    _fields(
        report,
        (
            "status",
            "registration_sha256",
            "source_sha256",
            "cpu_runtime",
            "cpu_fit_performed",
            "epochs",
            "fit_examples",
            "check_examples",
            "source_sessions",
            "completed_predictions",
            "files",
            "elapsed_seconds",
            "scores",
            "per_session_scores",
            "truth_joint_counts",
            *FLAGS,
        ),
    )
    if (
        report["status"] != "completed_full_inner_check_controls_not_validation"
        or report["registration_sha256"] != pin
        or report["source_sha256"] != source_sha256()
        or report["cpu_runtime"] != registered["cpu_runtime"]
        or report["cpu_fit_performed"] is not True
        or canonical(
            [
                report[k]
                for k in (
                    "epochs",
                    "fit_examples",
                    "check_examples",
                    "source_sessions",
                    "completed_predictions",
                )
            ]
        )
        != canonical(
            [
                specification()["epochs"],
                len(fit_rows),
                len(chosen),
                len(value["session_split"]["check"]),
                len(NAMES) * len(chosen),
            ]
        )
        or any(report[k] is not v for k, v in FLAGS.items())
    ):
        raise ValueError("Complete unchanged fixed CPU execution required")
    training.finite_nonnegative([report["elapsed_seconds"]])
    _fields(report["files"], ("request.json", "model.json", "epochs.jsonl", "predictions.jsonl"))
    for name, info in report["files"].items():
        if file_info(directory / name) != info:
            raise ValueError("CPU output raw-file pins differ")
    request = tokens.metadata(directory / "request.json", report["files"]["request.json"]["sha256"])
    if request != {"registration_sha256": pin, "source_sha256": source_sha256()}:
        raise ValueError("CPU request binding changed")
    events = lines(directory / "epochs.jsonl", report["files"]["epochs.jsonl"])
    if len(events) != 2 * specification()["epochs"]:
        raise ValueError("All 200 CPU epochs required")
    for epoch in range(1, specification()["epochs"] + 1):
        intent, completed = events[2 * (epoch - 1) : 2 * epoch]
        _fields(completed, ("event", "epoch", "loss"))
        training.finite_nonnegative([completed["loss"]])
        if canonical(intent) != canonical({"event": "epoch_intent", "epoch": epoch}) or canonical(
            completed
        ) != canonical({"event": "epoch_completed", "epoch": epoch, "loss": completed["loss"]}):
            raise ValueError("Durable full CPU epoch journal differs")
    model = tokens.metadata(directory / "model.json", report["files"]["model.json"]["sha256"])
    predictions = lines(directory / "predictions.jsonl", report["files"]["predictions.jsonl"])
    if canonical(predictions) != canonical(all_predictions(value, model, chosen)):
        raise ValueError("Every control/case/input/order/prediction must match frozen coefficients")
    rebuilt = scores(
        chosen,
        {name: [r["forecast"] for r in predictions if r["control"] == name] for name in NAMES},
    )
    if canonical({k: report[k] for k in rebuilt}) != canonical(rebuilt):
        raise ValueError("Full pooled/per-session CPU scores differ")
    return registered, value, chosen, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--registration-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enable-cpu-controls", action="store_true")
    args = parser.parse_args()
    check_digest(args.registration_sha256)
    result = (
        freeze(args.registration, args.registration_sha256, args.output)
        if args.action == "freeze"
        else run(
            args.registration,
            args.registration_sha256,
            args.output,
            enable_cpu_controls=args.enable_cpu_controls,
        )
    )
    print(canonical({"kind": KIND, "status": result.get("status", "registered_not_run")}))


if __name__ == "__main__":
    main()
