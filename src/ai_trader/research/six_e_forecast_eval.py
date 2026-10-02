"""Frozen, paired 6E forecast diagnostics on exposed development only; never trading."""

from __future__ import annotations

import argparse
import hashlib
import time
from collections import Counter
from pathlib import Path

from ai_trader.models.local_checkpoint import (
    canonical,
    check_digest,
    digest,
    inspect_checkpoint,
    strict_json,
)
from ai_trader.models.local_reviewer import _exchange
from ai_trader.training import six_e_forecast as task
from ai_trader.training import six_e_lora_trial as trial
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import _absolute, _lock_pin, _runtime_shape, _write
from ai_trader.training.lora_backend import adapter_manifest

KIND = "six_e_forecast_exposed_development_eval_v1"
WORKER = "ai_trader.models._six_e_forecast_worker"
CASES, MAX_NEW_TOKENS, TIMEOUT_MS = 40, 48, 600_000
MAX_PACKET_BYTES, MAX_ARTIFACT_BYTES = 256 * 1024, 128 * 1024
MODES = ("base", "adapter")
COST_KEYS = tuple(f"extra_{c}_{'tick' if c == 1 else 'ticks'}" for c in task.EXTRA_COSTS)
FLAGS = {
    "training_performed": False,
    "independent_holdout": False,
    "reserved_outcomes_opened": False,
    "promotion_allowed": False,
    "trading_enabled": False,
    "adapter_approved_for_deployment": False,
    "automatic_retry": False,
}
ASSET_PATHS = (
    "python_executable",
    "checkpoint",
    "adapter",
    "dependency_lock",
    "runtime_manifest",
    "tokenizer_json",
)
ASSET_PINS = (
    "checkpoint_sha256",
    "adapter_manifest_sha256",
    "dependency_lock_sha256",
    "runtime_sha256",
    "tokenizer_sha256",
)
PACKET_FIELDS = (
    "kind",
    "protocol",
    "source_sha256",
    "registration_sha256",
    *ASSET_PATHS,
    *ASSET_PINS,
    "output_dir",
    "selection",
)


def protocol() -> dict:
    return {
        "kind": KIND,
        "task": task.TASK,
        "role": "validation_development",
        "exposure": "Previously exposed 2025 development; NOT an independent holdout",
        "cases": CASES,
        "selection": "Even rank indices from pinned supervised file count, before labels; "
        "no sign selection",
        "modes": list(MODES),
        "controls": ["no_opportunity", "training_joint_mode"],
        "prior_tie_order": ["neither_positive", "long_positive", "short_positive"],
        "inference": {
            "dtype": "bfloat16",
            "device": "cuda",
            "seed": 42,
            "do_sample": False,
            "num_beams": 1,
            "max_new_tokens": MAX_NEW_TOKENS,
            "use_cache": True,
            "eos_token_id": 151643,
            "pad_token_id": 151643,
            "attn_implementation": "eager",
            "cublas_workspace_config": ":4096:8",
            "max_prompt_tokens": 2048,
            "chat_template": False,
            "constrained_decoding": False,
            "adapter_toggle_policy": "Re-freeze only allowlisted q/v LoRA flags after base "
            "context exit; any actual gradient or trainable base weight is refused",
        },
        "parsing": "One strict JSON object, exact keys/classes and cost monotonicity; "
        "EOS required; no repairs or retries",
        "invalid_outputs": "Separate invalid confusion column; incorrect in overall accuracy, "
        "never relabeled no-opportunity",
        "metrics": "Coverage, overall/valid accuracy, per-class precision/recall/F1, balanced "
        "accuracy and macro F1 over supported classes; directional precision/recall",
        "economics": "Quote-opportunity class matching at 1/2/4 extra ticks only; "
        "no PnL, fills, orders or promotion",
        "worker_timeout_seconds": TIMEOUT_MS // 1000,
        **FLAGS,
    }


def source_sha256() -> str:
    package = Path(__file__).resolve().parents[1]
    return digest(
        {
            "training_and_transport": trial.source_sha256(),
            **{
                name: hashlib.sha256((package / name).read_bytes()).hexdigest()
                for name in (
                    "research/six_e_forecast_eval.py",
                    "models/_six_e_forecast_worker.py",
                )
            },
        }
    )


def file_info(path: Path, limit=MAX_ARTIFACT_BYTES) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Regular bounded artifact required")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if not raw or len(raw) > limit:
        raise ValueError("Artifact byte limit exceeded or empty")
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def bounded_lines(path: Path, info: dict) -> list[dict]:
    _fields(info, ("bytes", "sha256"))
    if file_info(path) != info:
        raise ValueError("Pinned output artifact differs")
    with path.open("rb") as stream:
        raw = stream.read(MAX_ARTIFACT_BYTES + 1)
    if (
        len(raw) > MAX_ARTIFACT_BYTES
        or hashlib.sha256(raw).hexdigest() != info["sha256"]
        or not raw.endswith(b"\n")
    ):
        raise ValueError("Output framing/pin differs")
    return [strict_json(line) for line in raw.splitlines()]


def verified_trial(directory: Path, request_pin: str, report_pin: str) -> tuple[dict, dict]:
    request = trial.metadata(directory / "request.json", request_pin)
    report = trial.metadata(directory / "run.json", report_pin)
    if (
        directory.is_symlink()
        or (directory / "failure.json").exists()
        or report["status"] != "completed_20_update_market_trial_not_validated"
        or report["adapter_quarantined"] is not True
        or report["full_training_epoch"] is not False
        or any(report[k] is not value for k, value in trial.NO_AUTHORITY.items())
        or request["output_dir"] != str(directory.resolve())
    ):
        raise ValueError("Completed quarantined engineering candidate required")
    trial.validate_result(report["result"], request, directory)
    receipt = trial.metadata(
        Path(request["dataset"]) / "completion.json", request["dataset_sha256"]
    )
    return request, receipt


def indices(count: int) -> list[int]:
    if type(count) is not int or not CASES <= count <= task.MAX_CASES:
        raise ValueError("At least forty bounded development examples required")
    return [i * (count - 1) // (CASES - 1) for i in range(CASES)]


def rows(directory: Path, role: str, receipt: dict):
    """Allowlisted streams only. Reserved/test/unavailable files cannot enter this reader."""
    if role not in ("train", "validation_development"):
        raise ValueError("Only train priors or exposed validation diagnostics permitted")
    item = receipt["files"][role + ".jsonl"]
    _fields(item, ("count", "bytes", "sha256"))
    if type(item["count"]) is not int or not 1 <= item["count"] <= task.MAX_CASES:
        raise ValueError("Bounded role count required")
    check_digest(item["sha256"])
    path = directory / (role + ".jsonl")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Regular development file required")
    count, size, previous, checksum = 0, 0, None, hashlib.sha256()
    with path.open("rb") as stream:
        while raw := stream.readline(task.MAX_LINE + 1):
            checksum.update(raw)
            size += len(raw)
            if (
                len(raw) > task.MAX_LINE
                or not raw.endswith(b"\n")
                or size > task.MAX_DATA_BYTES
                or count >= item["count"]
            ):
                raise ValueError("Development framing/count/byte bound exceeded")
            row = strict_json(raw)
            if row.get("role") != role:
                raise ValueError("Role gate failed before accessing prompt or target")
            task.validate_example(row)
            if previous is not None and row["decision_ts_ns"] <= previous:
                raise ValueError("Unique chronological development rows required")
            previous = row["decision_ts_ns"]
            count += 1
            yield row
    if count != item["count"] or size != item["bytes"] or checksum.hexdigest() != item["sha256"]:
        raise ValueError("No partial or changed development file permitted")


def training_prior(directory: Path, receipt: dict) -> dict:
    joint, by_cost = Counter(), {key: Counter() for key in COST_KEYS}
    for row in rows(directory, "train", receipt):
        forecast = task.parse_completion(row["completion"])
        joint[row["completion"]] += 1
        for key in COST_KEYS:
            by_cost[key][forecast[key]] += 1
    order = protocol()["prior_tie_order"]
    mode = min(
        joint,
        key=lambda text: (
            -joint[text],
            tuple(order.index(task.parse_completion(text)[k]) for k in COST_KEYS),
        ),
    )
    return {
        "examples": sum(joint.values()),
        "joint_mode": task.parse_completion(mode),
        "joint_mode_count": joint[mode],
        "class_counts": {key: {c: by_cost[key][c] for c in task.CLASSES} for key in COST_KEYS},
    }


def freeze(directory: Path, request_pin: str, report_pin: str, output: Path) -> dict:
    """Freeze protocol/indices/controls before reading any later-development labels."""
    request, receipt = verified_trial(directory, request_pin, report_pin)
    item = receipt["files"]["validation_development.jsonl"]
    value = {
        "kind": KIND,
        "protocol": protocol(),
        "source_sha256": source_sha256(),
        "trial_directory": str(directory.resolve()),
        "trial_request_sha256": request_pin,
        "trial_report_sha256": report_pin,
        "validation_file": item,
        "example_indices": indices(item["count"]),
        "training_prior": training_prior(Path(request["dataset"]), receipt),
        **FLAGS,
    }
    disjoint(output, request, directory)
    _write(output, value)
    return value


def disjoint(output: Path, request: dict, directory: Path) -> None:
    if (
        output.is_symlink()
        or not output.parent.is_dir()
        or any(
            output.resolve().is_relative_to(p.resolve())
            or p.resolve().is_relative_to(output.resolve())
            for p in (directory, Path(request["dataset"]), Path(request["checkpoint"]))
        )
    ):
        raise ValueError("New output must be disjoint from immutable training inputs")


def registration(path: Path, pin: str) -> tuple[dict, dict, dict]:
    value = trial.metadata(path, pin)
    _fields(
        value,
        (
            "kind",
            "protocol",
            "source_sha256",
            "trial_directory",
            "trial_request_sha256",
            "trial_report_sha256",
            "validation_file",
            "example_indices",
            "training_prior",
            *FLAGS,
        ),
    )
    if (
        value["kind"] != KIND
        or canonical(value["protocol"]) != canonical(protocol())
        or value["source_sha256"] != source_sha256()
        or any(value[k] is not v for k, v in FLAGS.items())
    ):
        raise ValueError("Frozen development protocol/source/authority changed")
    request, receipt = verified_trial(
        _absolute(value["trial_directory"]),
        value["trial_request_sha256"],
        value["trial_report_sha256"],
    )
    item = receipt["files"]["validation_development.jsonl"]
    if (
        value["validation_file"] != item
        or canonical(value["example_indices"]) != canonical(indices(item["count"]))
        or value["training_prior"] != training_prior(Path(request["dataset"]), receipt)
    ):
        raise ValueError("Frozen sample or training-only controls differ")
    return value, request, receipt


def selected_rows(value: dict, request: dict, receipt: dict) -> list[dict]:
    selected = set(value["example_indices"])
    chosen = [
        row
        for i, row in enumerate(rows(Path(request["dataset"]), "validation_development", receipt))
        if i in selected
    ]
    if len(chosen) != CASES:
        raise ValueError("All forty fixed cases required")
    return chosen


def feature_selection(chosen: list[dict]) -> list[dict]:
    # Never copy completion, target hash, date, contract, role or future values to the worker.
    return [{key: row[key] for key in ("case_id", "input_sha256", "prompt")} for row in chosen]


def worker_packet(
    request: dict, directory: Path, registration_pin: str, chosen: list[dict], output: Path
) -> dict:
    return {
        "kind": KIND,
        "protocol": protocol(),
        "source_sha256": source_sha256(),
        "registration_sha256": registration_pin,
        **{
            key: request[key]
            for key in (*ASSET_PATHS, *ASSET_PINS)
            if key not in ("adapter", "adapter_manifest_sha256")
        },
        "adapter": str((directory / "adapter").resolve()),
        "adapter_manifest_sha256": digest(adapter_manifest(directory / "adapter")),
        "output_dir": str(output.resolve()),
        "selection": feature_selection(chosen),
    }


def validate_packet(packet: dict, *, verify_assets=True) -> tuple[dict, dict]:
    _fields(packet, PACKET_FIELDS)
    if (
        packet["kind"] != KIND
        or canonical(packet["protocol"]) != canonical(protocol())
        or packet["source_sha256"] != source_sha256()
        or len(canonical(packet).encode()) > MAX_PACKET_BYTES
    ):
        raise ValueError("Bounded exact feature-only packet/protocol/source required")
    for key in (*ASSET_PATHS, "output_dir"):
        _absolute(packet[key])
    for key in (*ASSET_PINS, "registration_sha256", "source_sha256"):
        check_digest(packet[key])
    if type(packet["selection"]) is not list or len(packet["selection"]) != CASES:
        raise ValueError("Exactly forty feature-only cases required")
    identities = set()
    for item in packet["selection"]:
        _fields(item, ("case_id", "input_sha256", "prompt"))
        check_digest(item["case_id"])
        check_digest(item["input_sha256"])
        text = item["prompt"]
        if (
            type(text) is not str
            or not text.startswith(task.PREFIX)
            or not text.endswith(task.SUFFIX)
        ):
            raise ValueError("Fixed causal prompt required")
        features = strict_json(text[len(task.PREFIX) : -len(task.SUFFIX)])
        if (
            task.prompt(features) != text
            or digest(features) != item["input_sha256"]
            or item["case_id"] in identities
        ):
            raise ValueError("Causal prompt pin/unique case differs")
        identities.add(item["case_id"])
    pins = _lock_pin(Path(packet["dependency_lock"]), packet["dependency_lock_sha256"])
    runtime = trial.metadata(Path(packet["runtime_manifest"]), packet["runtime_sha256"])
    _runtime_shape(runtime)
    if runtime["python_executable"] != packet["python_executable"] or any(
        runtime["packages"][k] != pins[k] for k in runtime["packages"]
    ):
        raise ValueError("Runtime/lock/interpreter differs")
    if verify_assets:
        assets = inspect_checkpoint(Path(packet["checkpoint"]), "Qwen/Qwen3-4B-Base")
        if (
            digest(assets) != packet["checkpoint_sha256"]
            or digest(adapter_manifest(Path(packet["adapter"])))
            != packet["adapter_manifest_sha256"]
            or next(f["sha256"] for f in assets["files"] if f["name"] == "tokenizer.json")
            != packet["tokenizer_sha256"]
        ):
            raise ValueError("Pinned base/adapter/tokenizer assets differ")
        task.checked_file(Path(packet["tokenizer_json"]), packet["tokenizer_sha256"], 16 * 1024**2)
    return pins, runtime


def binding(call: int, mode: str, item: dict) -> dict:
    return {
        "call": call,
        "mode": mode,
        "case_id": item["case_id"],
        "input_sha256": item["input_sha256"],
    }


def validate_prediction(value: dict) -> None:
    _fields(
        value,
        (
            "call",
            "mode",
            "case_id",
            "input_sha256",
            "raw_response",
            "generated_tokens",
            "stop_reason",
        ),
    )
    if (
        type(value["raw_response"]) is not str
        or len(value["raw_response"].encode()) > 1024
        or type(value["generated_tokens"]) is not int
        or not 1 <= value["generated_tokens"] <= MAX_NEW_TOKENS
        or value["stop_reason"] not in ("eos", "token_limit")
        or (value["stop_reason"] == "token_limit" and value["generated_tokens"] != MAX_NEW_TOKENS)
    ):
        raise ValueError("Bounded native prediction evidence required")


def forecast(value: dict) -> tuple[dict | None, str]:
    if value["stop_reason"] != "eos":
        return None, "token_limit"
    try:
        return task.parse_completion(value["raw_response"]), "valid"
    except ValueError:
        return None, "invalid_json_or_contract"


def metrics(truth: list[dict], predictions: list[dict | None]) -> dict:
    if not truth or len(truth) != len(predictions):
        raise ValueError("Paired nonempty prediction/target lists required")
    for item in [*truth, *(p for p in predictions if p is not None)]:
        task.parse_completion(canonical(item))
    total, valid = len(truth), sum(p is not None for p in predictions)
    by_cost = {}
    for key in COST_KEYS:
        matrix = {actual: dict.fromkeys((*task.CLASSES, "invalid"), 0) for actual in task.CLASSES}
        for actual, predicted in zip(truth, predictions, strict=True):
            matrix[actual[key]][predicted[key] if predicted is not None else "invalid"] += 1
        classes = {}
        for c in task.CLASSES:
            support, called, tp = (
                sum(matrix[c].values()),
                sum(matrix[a][c] for a in task.CLASSES),
                matrix[c][c],
            )
            classes[c] = {
                "support": support,
                "predicted": called,
                "true_positive": tp,
                "precision": tp / called if called else None,
                "recall": tp / support if support else None,
                "f1": 2 * tp / (support + called) if support + called else None,
            }
        correct = sum(classes[c]["true_positive"] for c in task.CLASSES)
        supported = [c for c in task.CLASSES if classes[c]["support"]]
        directions = task.CLASSES[:2]
        called = sum(classes[c]["predicted"] for c in directions)
        actual = sum(classes[c]["support"] for c in directions)
        matched = sum(classes[c]["true_positive"] for c in directions)
        by_cost[key] = {
            "confusion": matrix,
            "per_class": classes,
            "correct": correct,
            "overall_accuracy": correct / total,
            "accuracy_on_valid": correct / valid if valid else None,
            "supported_classes": supported,
            "balanced_accuracy_over_supported_classes": sum(classes[c]["recall"] for c in supported)
            / len(supported),
            "macro_f1_over_supported_classes": sum(classes[c]["f1"] for c in supported)
            / len(supported),
            "directional_prediction_rate": called / total,
            "directional_precision": matched / called if called else None,
            "directional_recall": matched / actual if actual else None,
        }
    return {
        "examples": total,
        "valid_outputs": valid,
        "invalid_outputs": total - valid,
        "coverage": valid / total,
        "by_cost": by_cost,
    }


def validate_result(result: dict, packet: dict, directory: Path) -> list[dict]:
    _fields(
        result,
        (
            "kind",
            "request_sha256",
            "completed_calls",
            "parameters_frozen",
            "runtime",
            "resources",
            "files",
            *FLAGS,
        ),
    )
    if (
        result["kind"] != KIND
        or result["request_sha256"] != digest(packet)
        or type(result["completed_calls"]) is not int
        or result["completed_calls"] != 2 * CASES
        or result["parameters_frozen"] is not True
        or any(result[k] is not v for k, v in FLAGS.items())
        or (directory / "failure.json").exists()
    ):
        raise ValueError("Complete paired inference-only evidence required")
    _, runtime = validate_packet(packet)
    if result["runtime"] != runtime:
        raise ValueError("Worker runtime changed")
    resources = result["resources"]
    _fields(
        resources,
        (
            "device",
            "total_bytes",
            "peak_allocated_bytes",
            "peak_reserved_bytes",
            "cuda_bf16",
            "deterministic_algorithms",
            "tf32_enabled",
        ),
    )
    if (
        type(resources["device"]) is not str
        or not 1 <= len(resources["device"]) <= 128
        or any(
            type(resources[k]) is not int or resources[k] <= 0
            for k in ("total_bytes", "peak_allocated_bytes", "peak_reserved_bytes")
        )
        or not resources["peak_allocated_bytes"]
        <= resources["peak_reserved_bytes"]
        <= resources["total_bytes"]
        or resources["cuda_bf16"] is not True
        or resources["deterministic_algorithms"] is not True
        or resources["tf32_enabled"] is not False
    ):
        raise ValueError("Native resource/precision guards differ")
    _fields(result["files"], ("predictions.jsonl", "events.jsonl"))
    predictions = bounded_lines(
        directory / "predictions.jsonl", result["files"]["predictions.jsonl"]
    )
    if len(predictions) != 2 * CASES:
        raise ValueError("No successful subset scoring")
    events = [
        {"event": "native_initialization_started"},
        {"event": "native_initialization_completed"},
    ]
    call = 0
    for item in packet["selection"]:
        for mode in MODES:
            call += 1
            row = predictions[call - 1]
            validate_prediction(row)
            current = binding(call, mode, item)
            if any(type(row[k]) is not type(v) or row[k] != v for k, v in current.items()):
                raise ValueError("Prediction order/case/mode/input differs")
            events.extend(
                [
                    {"event": "prediction_intent", **current},
                    {"event": "prediction_completed", **current, "prediction_sha256": digest(row)},
                ]
            )
    events.append({"event": "inference_completed"})
    if bounded_lines(directory / "events.jsonl", result["files"]["events.jsonl"]) != events:
        raise ValueError("Durable paired inference journal differs")
    return predictions


def run(path: Path, pin: str, output: Path, *, enable_development_evaluation=False) -> dict:
    if enable_development_evaluation is not True:
        raise ValueError("Explicit exposed-development evaluation opt-in required")
    value, request, receipt = registration(path, pin)
    directory = Path(value["trial_directory"])
    disjoint(output, request, directory)
    chosen = selected_rows(value, request, receipt)
    packet = worker_packet(request, directory, pin, chosen, output)
    validate_packet(packet)
    output.mkdir(exist_ok=False)
    started = time.monotonic()
    try:
        _write(output / "request.json", packet)
        result = strict_json(
            _exchange([packet["python_executable"], "-I", "-m", WORKER], packet, TIMEOUT_MS)
        )
        predictions = validate_result(result, packet, output)
        _, final_request, final_receipt = registration(path, pin)
        refreshed = selected_rows(value, final_request, final_receipt)
        if refreshed != chosen:
            raise ValueError("Development inputs/targets changed during inference")
        truth = [task.parse_completion(row["completion"]) for row in chosen]
        scores, invalid_reasons = {}, {}
        for mode in MODES:
            parsed = [forecast(row) for row in predictions if row["mode"] == mode]
            scores[mode] = metrics(truth, [p for p, _ in parsed])
            invalid_reasons[mode] = dict(Counter(reason for _, reason in parsed))
        none = dict.fromkeys(COST_KEYS, "neither_positive")
        for name, control in (
            ("no_opportunity", none),
            ("training_joint_mode", value["training_prior"]["joint_mode"]),
        ):
            scores[name] = metrics(truth, [control] * CASES)
        report = {
            "status": "completed_exposed_development_diagnostic_not_validation",
            "registration_sha256": pin,
            "result": result,
            "examples": CASES,
            "source_sessions": len({row["source_session"] for row in chosen}),
            "scores": scores,
            "output_status_counts": invalid_reasons,
            "controls_identical": none == value["training_prior"]["joint_mode"],
            "adapter_minus_base_correct_cases": {
                key: scores["adapter"]["by_cost"][key]["correct"]
                - scores["base"]["by_cost"][key]["correct"]
                for key in COST_KEYS
            },
            "elapsed_seconds": time.monotonic() - started,
            "adapter_quarantined": True,
            "limitations": "Forty label-observable examples from exposed development only. "
            "Small/imbalanced support, no causal explanation, measured CFD execution, PnL, "
            "independent evidence or automatic training/promotion.",
            **FLAGS,
        }
        _write(output / "run.json", report)
        return report
    except BaseException as exc:
        if not (output / "run.json").exists():
            _write(
                output / "run.json",
                {
                    "status": "failed_or_interrupted_no_subset_score",
                    "error_type": type(exc).__name__,
                    "completed_calls": None,
                    "adapter_quarantined": True,
                    **FLAGS,
                },
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
    parser.add_argument("--enable-development-evaluation", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        if any(
            v is None
            for v in (args.trial_directory, args.trial_request_sha256, args.trial_report_sha256)
        ):
            parser.error("Completed trial directory and raw request/report pins required")
        value = freeze(
            args.trial_directory.resolve(),
            args.trial_request_sha256,
            args.trial_report_sha256,
            args.output.resolve(),
        )
        print(
            canonical(
                {
                    "status": "development_protocol_frozen_before_labels",
                    "cases": len(value["example_indices"]),
                }
            )
        )
    else:
        if args.registration is None or args.registration_sha256 is None:
            parser.error("Frozen evaluation registration and raw pin required")
        value = run(
            args.registration.resolve(),
            args.registration_sha256,
            args.output.resolve(),
            enable_development_evaluation=args.enable_development_evaluation,
        )
        print(
            canonical(
                {
                    "status": value["status"],
                    "examples": value["examples"],
                    "coverage": {k: v["coverage"] for k, v in value["scores"].items()},
                }
            )
        )


if __name__ == "__main__":
    main()
