"""Compare the pre-training frozen 80 inner-check cases; no tuning or deployment."""

from __future__ import annotations

import argparse
import hashlib
import time
from collections import Counter
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, check_digest, digest, strict_json
from ai_trader.models.local_reviewer import _exchange
from ai_trader.research import six_e_forecast_eval as legacy
from ai_trader.training import six_e_balanced_lora as training
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import _absolute, _write

balance, task = training.balance, training.task
KIND = "six_e_balanced_inner_check_comparison_v1"
CPU_KIND = KIND + "_cpu_controls"
GPU_WORKER = "ai_trader.models._six_e_balanced_eval_worker"
CPU_WORKER = "ai_trader.research._six_e_balanced_controls_worker"
CASES, TIMEOUT_MS, CPU_TIMEOUT_MS = 80, 600_000, 30_000
MAX_BYTES = 512 * 1024
FLAGS = dict(legacy.FLAGS)
REG_FIELDS = (
    "kind",
    "protocol",
    "source_sha256",
    "training_registration",
    "training_trial",
    "adapter_manifest",
    "cpu_runtime",
    "inner_fit_joint_counts",
    "comparison",
    *FLAGS,
)
GPU_FIELDS = (
    "kind",
    "protocol",
    "source_sha256",
    "registration_sha256",
    "enable_development_evaluation",
    *legacy.ASSET_PATHS,
    *legacy.ASSET_PINS,
    "output_dir",
    "selection",
)
CPU_FIELDS = (
    "kind",
    "protocol",
    "source_sha256",
    "registration_sha256",
    "enable_development_evaluation",
    "cpu_runtime",
    "models",
    "models_sha256",
    "output_dir",
    "selection",
)


def protocol() -> dict:
    return {
        "kind": KIND,
        "pre_training_comparison": training.protocol()["comparison"],
        "gpu_worker_seconds": TIMEOUT_MS // 1000,
        "cpu_worker_seconds": CPU_TIMEOUT_MS // 1000,
        "inputs": "Exactly the 80 pre-training frozen inner-check cases; workers receive "
        "causal prompts and identity/token metadata only, never labels, dates or dataset paths",
        "controls": "Frozen coefficients, evaluated in the original CPU study runtime. "
        "Joint argmax and fixed state tie order; no refitting or calibration",
        "scoring": "All 160 paired GPU predictions and all 160 CPU predictions required. "
        "Invalid Qwen outputs count as incorrect, not no-opportunity. Pooled/per-session "
        "strict class metrics at each cost; no PnL, threshold tuning or promotion",
        "registration_authorizes_execution": False,
        **FLAGS,
    }


def source_sha256() -> str:
    package = Path(__file__).resolve().parents[1]
    return digest(
        {
            "immutable_training_and_inference": training.source_sha256(),
            **{
                name: hashlib.sha256((package / name).read_bytes()).hexdigest()
                for name in (
                    "research/six_e_balanced_eval.py",
                    "models/_six_e_balanced_eval_worker.py",
                    "research/_six_e_balanced_controls_worker.py",
                )
            },
        }
    )


def candidate(path: Path, pin: str, directory: Path, request_pin: str, report_pin: str):
    value, request, rows = training.registration(path, pin)
    if directory.is_symlink() or not directory.is_dir() or (directory / "failure.json").exists():
        raise ValueError("Regular completed quarantined training trial required")
    packet = training.trial.metadata(directory / "request.json", request_pin)
    report = training.trial.metadata(directory / "run.json", report_pin)
    _fields(
        report,
        (
            "status",
            "registration_sha256",
            "result",
            "elapsed_seconds",
            "selected_training_examples",
            "selected_training_sessions",
            "metric_count",
            "full_training_epoch",
            "adapter_quarantined",
            "qwen_training_performed",
            "evaluation_performed",
            *training.FLAGS,
        ),
    )
    if (
        report["status"] != "completed_224_update_balanced_trial_not_validated"
        or report["registration_sha256"] != pin
        or report["adapter_quarantined"] is not True
        or report["full_training_epoch"] is not False
        or report["qwen_training_performed"] is not True
        or report["evaluation_performed"] is not False
        or any(report[k] is not v for k, v in training.FLAGS.items())
        or type(report["metric_count"]) is not int
        or report["metric_count"] != training.STEPS
        or type(report["selected_training_examples"]) is not int
        or report["selected_training_examples"] != training.STEPS
        or report["selected_training_sessions"]
        != len({i["source_session"] for i in value["selection"]})
        or canonical(packet) != canonical(training.worker_packet(value, rows, pin, directory))
    ):
        raise ValueError("Complete original 224-update trial/registration binding required")
    training.finite_nonnegative([report["elapsed_seconds"]])
    training.validate_result(report["result"], packet, directory)
    return value, request, rows, report


def selected(value: dict, rows: list[dict]) -> list[dict]:
    chosen = []
    for spec in value["comparison"]:
        row = rows[spec["example_index"]]
        if row["role"] != "train" or row["source_session"] not in value["session_split"]["check"]:
            raise ValueError("Inner-check role/session gate before outcome access")
        task.validate_example(row)
        if any(
            row[k] != spec[k]
            for k in ("case_id", "input_sha256", "target_sha256", "source_session")
        ):
            raise ValueError("Original pre-training comparison identity changed")
        chosen.append(row)
    if len(chosen) != CASES or len({r["case_id"] for r in chosen}) != CASES:
        raise ValueError("All eighty unique frozen comparison cases required")
    return chosen


def disjoint(output: Path, value: dict, request: dict, directory: Path) -> None:
    training.disjoint(output, request, value)
    legacy.disjoint(output, request, directory)


def make_registration(path, pin, directory, request_pin, report_pin):
    value, request, rows, report = candidate(path, pin, directory, request_pin, report_pin)
    selected(value, rows)
    plan = training.trial.metadata(
        Path(value["balance_plan"]["path"]), value["balance_plan"]["sha256"]
    )
    return (
        {
            "kind": KIND,
            "protocol": protocol(),
            "source_sha256": source_sha256(),
            "training_registration": {"path": str(path.resolve()), "sha256": pin},
            "training_trial": {
                "directory": str(directory.resolve()),
                "request_sha256": request_pin,
                "report_sha256": report_pin,
            },
            "adapter_manifest": report["result"]["reload"]["adapter_manifest"],
            "cpu_runtime": plan["cpu_runtime"],
            "inner_fit_joint_counts": plan["audits"]["inner_fit"]["joint_counts"],
            "comparison": value["comparison"],
            **FLAGS,
        },
        value,
        request,
        rows,
    )


def freeze(path, pin, directory, request_pin, report_pin, output):
    registration_value, value, request, _ = make_registration(
        path, pin, directory, request_pin, report_pin
    )
    disjoint(output, value, request, directory)
    if output.resolve() == path.resolve():
        raise ValueError("Pre-training registration cannot be overwritten")
    _write(output, registration_value)
    return registration_value


def registration(path: Path, pin: str):
    registered = training.trial.metadata(path, pin)
    _fields(registered, REG_FIELDS)
    if registered["source_sha256"] != source_sha256() or canonical(
        registered["protocol"]
    ) != canonical(protocol()):
        raise ValueError("New source-bound operational registration required")
    _fields(registered["training_registration"], ("path", "sha256"))
    _fields(registered["training_trial"], ("directory", "request_sha256", "report_sha256"))
    p, t = registered["training_registration"], registered["training_trial"]
    rebuilt, value, request, rows = make_registration(
        _absolute(p["path"]),
        p["sha256"],
        _absolute(t["directory"]),
        t["request_sha256"],
        t["report_sha256"],
    )
    if canonical(registered) != canonical(rebuilt):
        raise ValueError("Frozen selections/assets/CPU controls/runtime/authority changed")
    return registered, value, request, rows


def feature_selection(value: dict, chosen: list[dict]) -> list[dict]:
    return [
        {**item, "prompt_tokens": spec["prompt_tokens"]}
        for item, spec in zip(
            legacy.feature_selection(chosen),
            value["comparison"],
            strict=True,
        )
    ]


def gpu_packet(registered: dict, value: dict, chosen: list[dict], pin: str, output: Path) -> dict:
    packet = {
        "kind": KIND,
        "protocol": protocol(),
        "source_sha256": source_sha256(),
        "registration_sha256": pin,
        "enable_development_evaluation": True,
        **value["assets"],
        "adapter": str(Path(registered["training_trial"]["directory"]) / "adapter"),
        "adapter_manifest_sha256": digest(registered["adapter_manifest"]),
        "output_dir": str(output.resolve()),
        "selection": feature_selection(value, chosen),
    }
    validate_gpu_packet(packet)
    return packet


def cpu_packet(registered: dict, value: dict, chosen: list[dict], pin: str, output: Path) -> dict:
    models = training.trial.metadata(
        Path(value["controls"]["directory"]) / "models.json",
        value["controls"]["models_sha256"],
    )
    packet = {
        "kind": CPU_KIND,
        "protocol": protocol(),
        "source_sha256": source_sha256(),
        "registration_sha256": pin,
        "enable_development_evaluation": True,
        "cpu_runtime": registered["cpu_runtime"],
        "models": models,
        "models_sha256": value["controls"]["model_content_sha256"],
        "output_dir": str(output.resolve()),
        "selection": feature_selection(value, chosen),
    }
    validate_cpu_packet(packet, parent_required=False)
    return packet


def validate_selection(selection: list) -> None:
    if type(selection) is not list or len(selection) != CASES:
        raise ValueError("Exactly eighty selected feature-only cases required")
    identities = set()
    for item in selection:
        _fields(item, ("case_id", "input_sha256", "prompt", "prompt_tokens"))
        check_digest(item["case_id"])
        check_digest(item["input_sha256"])
        features = balance.feature_values(item)
        if (
            digest(dict(zip(task.FEATURES, features, strict=True))) != item["input_sha256"]
            or item["case_id"] in identities
            or type(item["prompt_tokens"]) is not int
            or not 1 <= item["prompt_tokens"] <= 2048
        ):
            raise ValueError("Unique pinned causal prompt/token count required")
        identities.add(item["case_id"])


def validate_common(packet: dict, kind: str, fields: tuple, *, parent_required=True) -> None:
    _fields(packet, fields)
    if (
        packet["kind"] != kind
        or canonical(packet["protocol"]) != canonical(protocol())
        or packet["source_sha256"] != source_sha256()
        or packet["enable_development_evaluation"] is not True
        or len(canonical(packet).encode()) > MAX_BYTES
    ):
        raise ValueError("Bounded fixed inference-only protocol/source/opt-in required")
    check_digest(packet["registration_sha256"])
    output = _absolute(packet["output_dir"])
    if output.is_symlink() or (parent_required and not output.parent.is_dir()):
        raise ValueError("Regular owned output with existing parent required")
    validate_selection(packet["selection"])


def validate_gpu_packet(packet: dict, *, verify_assets=True):
    validate_common(packet, KIND, GPU_FIELDS)
    output = Path(packet["output_dir"]).resolve()
    for name in legacy.ASSET_PATHS:
        path = _absolute(packet[name])
        if (
            path.is_symlink()
            or path.resolve().is_relative_to(output)
            or output.is_relative_to(path.resolve())
        ):
            raise ValueError("Pinned assets must be regular and disjoint from output")
    # Reuse the immutable asset verifier with a feature-only forty-case view. Native
    # inference still uses all eighty cases and the exact pre-training decoding recipe.
    view = {
        key: packet[key]
        for key in legacy.PACKET_FIELDS
        if key not in ("kind", "protocol", "source_sha256", "selection")
    }
    view.update(
        kind=legacy.KIND,
        protocol=legacy.protocol(),
        source_sha256=legacy.source_sha256(),
        selection=[
            {k: v for k, v in item.items() if k != "prompt_tokens"}
            for item in packet["selection"][: legacy.CASES]
        ],
    )
    return legacy.validate_packet(view, verify_assets=verify_assets)


def validate_cpu_packet(packet: dict, *, parent_required=True) -> None:
    validate_common(packet, CPU_KIND, CPU_FIELDS, parent_required=parent_required)
    _fields(packet["cpu_runtime"], tuple(balance.runtime()))
    executable = _absolute(packet["cpu_runtime"]["python_executable"])
    if (
        executable.is_symlink()
        or not executable.is_file()
        or executable.resolve().is_relative_to(Path(packet["output_dir"]).resolve())
    ):
        raise ValueError("Original CPU interpreter must be regular and disjoint")
    if (
        set(packet["models"]) != set(balance.MODES)
        or digest(packet["models"]) != packet["models_sha256"]
    ):
        raise ValueError("Exactly the two pinned frozen CPU models required")
    for name in balance.MODES:
        model = packet["models"][name]
        if type(model["weight_power"]) is not float or model["weight_power"] != balance.MODES[name]:
            raise ValueError("Frozen CPU model identity differs")
        balance.predict(model, [[0.0] * len(task.FEATURES)])


def file_info(path: Path) -> dict:
    return legacy.file_info(path, MAX_BYTES)


def lines(path: Path, info: dict) -> list[dict]:
    _fields(info, ("bytes", "sha256"))
    if file_info(path) != info:
        raise ValueError("Complete bounded artifact pin differs")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if (
        not raw.endswith(b"\n")
        or len(raw) > MAX_BYTES
        or hashlib.sha256(raw).hexdigest() != info["sha256"]
    ):
        raise ValueError("Complete bounded artifact framing required")
    return [strict_json(line) for line in raw.splitlines()]


def validate_gpu_result(result: dict, packet: dict, directory: Path) -> list[dict]:
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
        raise ValueError("All paired GPU predictions required; no subset scoring")
    _, runtime = validate_gpu_packet(packet)
    if result["runtime"] != runtime:
        raise ValueError("GPU runtime drift")
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
        raise ValueError("Frozen CUDA precision/resource guards differ")
    _fields(result["files"], ("predictions.jsonl", "events.jsonl"))
    predictions = lines(directory / "predictions.jsonl", result["files"]["predictions.jsonl"])
    if len(predictions) != 2 * CASES:
        raise ValueError("All 160 prediction receipts required")
    events = [
        {"event": "native_initialization_started"},
        {"event": "native_initialization_completed"},
    ]
    call = 0
    for item in packet["selection"]:
        for mode in legacy.MODES:
            call += 1
            row = predictions[call - 1]
            legacy.validate_prediction(row)
            binding = legacy.binding(call, mode, item)
            if any(type(row[k]) is not type(v) or row[k] != v for k, v in binding.items()):
                raise ValueError("GPU case/input/mode/order differs")
            events.extend(
                [
                    {"event": "prediction_intent", **binding},
                    {"event": "prediction_completed", **binding, "prediction_sha256": digest(row)},
                ]
            )
    events.append({"event": "inference_completed"})
    if canonical(lines(directory / "events.jsonl", result["files"]["events.jsonl"])) != canonical(
        events
    ):
        raise ValueError("Durable complete paired GPU journal required")
    return predictions


def validate_cpu_result(result: dict, packet: dict, directory: Path) -> list[dict]:
    _fields(
        result,
        (
            "kind",
            "request_sha256",
            "cpu_runtime",
            "models_sha256",
            "predictions",
            "completed_predictions",
            *FLAGS,
        ),
    )
    validate_cpu_packet(packet)
    if (
        result["kind"] != CPU_KIND
        or result["request_sha256"] != digest(packet)
        or result["cpu_runtime"] != packet["cpu_runtime"]
        or result["models_sha256"] != packet["models_sha256"]
        or type(result["completed_predictions"]) is not int
        or result["completed_predictions"] != 2 * CASES
        or any(result[k] is not v for k, v in FLAGS.items())
        or (directory / "failure.json").exists()
    ):
        raise ValueError("All predictions from the unchanged CPU controls required")
    predictions = lines(directory / "predictions.jsonl", result["predictions"])
    if len(predictions) != 2 * CASES:
        raise ValueError("Complete CPU control output required")
    for index, row in enumerate(predictions):
        _fields(row, ("case_id", "input_sha256", "control", "forecast"))
        item, name = packet["selection"][index // 2], tuple(balance.MODES)[index % 2]
        if row["control"] != name or any(row[k] != item[k] for k in ("case_id", "input_sha256")):
            raise ValueError("CPU control case/input/order differs")
        task.parse_completion(canonical(row["forecast"]))
    return predictions


def score(registered: dict, chosen: list[dict], gpu: list[dict], cpu: list[dict]) -> dict:
    truth = [task.parse_completion(row["completion"]) for row in chosen]
    parsed, status = {}, {}
    for mode in legacy.MODES:
        values = [legacy.forecast(row) for row in gpu if row["mode"] == mode]
        parsed[mode] = [forecast for forecast, _ in values]
        status[mode] = dict(Counter(reason for _, reason in values))
    parsed["no_opportunity"] = [dict.fromkeys(legacy.COST_KEYS, "neither_positive")] * CASES
    counts = registered["inner_fit_joint_counts"]
    state = max(balance.STATES, key=lambda name: counts[name])
    parsed["inner_fit_joint_prior"] = [balance.forecast(state)] * CASES
    for name in balance.MODES:
        parsed[name] = [row["forecast"] for row in cpu if row["control"] == name]
    pooled = {name: legacy.metrics(truth, values) for name, values in parsed.items()}
    per_session = {}
    for session in sorted({row["source_session"] for row in chosen}):
        indices = [i for i, row in enumerate(chosen) if row["source_session"] == session]
        per_session[session] = {
            name: legacy.metrics([truth[i] for i in indices], [values[i] for i in indices])
            for name, values in parsed.items()
        }
    return {"scores": pooled, "per_session_scores": per_session, "output_status_counts": status}


def run(path: Path, pin: str, output: Path, *, enable_development_evaluation=False) -> dict:
    if enable_development_evaluation is not True:
        raise ValueError("Explicit one-batch exposed-development opt-in required")
    registered, value, request, rows = registration(path, pin)
    directory = Path(registered["training_trial"]["directory"])
    disjoint(output, value, request, directory)
    if path.resolve().is_relative_to(output.resolve()):
        raise ValueError("Output cannot overlap operational registration")
    chosen = selected(value, rows)
    gpu_request = gpu_packet(registered, value, chosen, pin, output)
    cpu_request = cpu_packet(registered, value, chosen, pin, output / "controls")
    output.mkdir(exist_ok=False)
    started, stage = time.monotonic(), "gpu_comparison"
    try:
        _write(output / "request.json", gpu_request)
        gpu_result = strict_json(
            _exchange(
                [gpu_request["python_executable"], "-I", "-m", GPU_WORKER], gpu_request, TIMEOUT_MS
            )
        )
        predictions = validate_gpu_result(gpu_result, gpu_request, output)
        stage = "cpu_comparison"
        controls_output = output / "controls"
        controls_output.mkdir()
        _write(controls_output / "request.json", cpu_request)
        cpu_result = strict_json(
            _exchange(
                [cpu_request["cpu_runtime"]["python_executable"], "-I", "-m", CPU_WORKER],
                cpu_request,
                CPU_TIMEOUT_MS,
            )
        )
        controls = validate_cpu_result(cpu_result, cpu_request, controls_output)
        stage = "post_comparison_pins"
        final, final_value, _, final_rows = registration(path, pin)
        if canonical(final) != canonical(registered) or selected(final_value, final_rows) != chosen:
            raise ValueError("Frozen inputs/targets/candidate/controls drift during comparison")
        scores = score(registered, chosen, predictions, controls)
        report = {
            "status": "completed_frozen_inner_check_comparison_not_validation",
            "registration_sha256": pin,
            "gpu_result": gpu_result,
            "cpu_result": cpu_result,
            "examples": CASES,
            "source_sessions": len({r["source_session"] for r in chosen}),
            **scores,
            "elapsed_seconds": time.monotonic() - started,
            "adapter_quarantined": True,
            "limitations": "Eighty label-observable cases from already-exposed within-training "
            "development. Imbalanced and small support; no independent evidence, CFD fills, "
            "portfolio PnL, causal explanation, training or promotion.",
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
                    "stage": stage,
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
    for name in ("training-registration", "trial-directory", "registration", "output"):
        parser.add_argument("--" + name, type=Path, required=name == "output")
    for name in (
        "training-registration-sha256",
        "trial-request-sha256",
        "trial-report-sha256",
        "registration-sha256",
    ):
        parser.add_argument("--" + name)
    parser.add_argument("--enable-development-evaluation", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        values = (
            args.training_registration,
            args.training_registration_sha256,
            args.trial_directory,
            args.trial_request_sha256,
            args.trial_report_sha256,
        )
        if any(v is None for v in values):
            parser.error("Pinned pre-training registration and complete candidate required")
        result = freeze(*values, args.output)
        print(canonical({"kind": result["kind"], "cases": len(result["comparison"])}))
    else:
        if args.registration is None or args.registration_sha256 is None:
            parser.error("Pinned operational registration required")
        result = run(
            args.registration,
            args.registration_sha256,
            args.output,
            enable_development_evaluation=args.enable_development_evaluation,
        )
        print(
            canonical(
                {
                    "status": result["status"],
                    "examples": result["examples"],
                    "coverage": {k: v["coverage"] for k, v in result["scores"].items()},
                }
            )
        )


if __name__ == "__main__":
    main()
