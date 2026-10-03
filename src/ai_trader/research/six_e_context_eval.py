"""Full paired context-v2 development evaluation; labels stay outside the native worker."""

from __future__ import annotations

import argparse
import hashlib
import time
from collections import Counter
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, check_digest, digest, strict_json
from ai_trader.models.local_reviewer import _exchange
from ai_trader.research import six_e_forecast_eval as legacy
from ai_trader.training import six_e_context_controls as controls
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import _absolute, _write
from ai_trader.training.lora_backend import adapter_manifest

training, task, tokens = controls.training, controls.task, controls.tokens
KIND = "six_e_context_v2_full_inner_check_comparison"
WORKER = "ai_trader.models._six_e_context_eval_worker"
MAX_CASES, MAX_PACKET_BYTES, TIMEOUT_MS = 6000, 64 * 1024, 43_200_000
FLAGS = dict(legacy.FLAGS)
REG_FIELDS = (
    "kind",
    "protocol",
    "source_sha256",
    "controls_registration",
    "controls_trial",
    "training_trial",
    "adapter_manifest",
    "comparison",
    "feature_file",
    *FLAGS,
)
PACKET_FIELDS = (
    "kind",
    "protocol",
    "source_sha256",
    "registration_sha256",
    "enable_development_evaluation",
    *legacy.ASSET_PATHS,
    *legacy.ASSET_PINS,
    "output_dir",
    "cases",
    "feature_file",
)


def protocol() -> dict:
    return {
        "kind": KIND,
        "pre_training_comparison": training.protocol()["comparison"],
        "inputs": "ALL frozen inner-check causal prompts and case/input/token identities only; "
        "feature sidecar is owned, bounded and pinned. No dates, targets or dataset paths.",
        "bounds": {
            "cases": MAX_CASES,
            "packet_bytes": MAX_PACKET_BYTES,
            "sidecar_bytes": controls.MAX_BYTES,
            "artifact_line_bytes": controls.MAX_LINE,
            "worker_seconds": TIMEOUT_MS // 1000,
        },
        "scoring": "All paired predictions and complete durable intent/completion journals "
        "required before any GPU scores; invalid JSON/token-limit outputs remain incorrect. "
        "Same full set as independently verified frozen CPU controls; no subset or retries.",
        "registration_authorizes_execution": False,
        **FLAGS,
    }


def source_sha256() -> str:
    package = Path(__file__).resolve().parents[1]
    return digest(
        {
            "immutable_controls_training_and_inference": controls.source_sha256(),
            **{
                name: hashlib.sha256((package / name).read_bytes()).hexdigest()
                for name in (
                    "research/six_e_context_eval.py",
                    "models/_six_e_context_eval_worker.py",
                )
            },
        }
    )


def candidate(
    value: dict,
    fit_rows: list[dict],
    directory: Path,
    request_pin: str,
    report_pin: str,
    training_pin: str,
) -> dict:
    if directory.is_symlink() or not directory.is_dir() or (directory / "failure.json").exists():
        raise ValueError("Regular completed quarantined context-v2 pilot required")
    packet = tokens.metadata(directory / "request.json", request_pin)
    report = tokens.metadata(directory / "run.json", report_pin)
    _fields(
        report,
        (
            "status",
            "registration_sha256",
            "result",
            "elapsed_seconds",
            "selected_training_examples",
            "selected_training_sessions",
            "selected_joint_counts",
            "metric_count",
            "full_training_epoch",
            "adapter_quarantined",
            "qwen_training_performed",
            "evaluation_performed",
            *training.FLAGS,
        ),
    )
    expected = training.worker_packet(value, fit_rows, training_pin, directory)
    if (
        canonical(packet) != canonical(expected)
        or report["status"] != "completed_192_update_context_v2_natural_trial_not_validated"
        or report["registration_sha256"] != training_pin
        or report["adapter_quarantined"] is not True
        or report["full_training_epoch"] is not False
        or report["qwen_training_performed"] is not True
        or report["evaluation_performed"] is not False
        or any(report[k] is not v for k, v in training.FLAGS.items())
        or canonical(
            [
                report["selected_training_examples"],
                report["metric_count"],
                report["selected_training_sessions"],
                report["selected_joint_counts"],
            ]
        )
        != canonical(
            [
                training.STEPS,
                training.STEPS,
                len({i["spec"]["source_session"] for i in packet["selection"]}),
                dict(Counter(i["spec"]["joint_state"] for i in packet["selection"])),
            ]
        )
    ):
        raise ValueError("Complete original natural-context training binding required")
    training.finite_nonnegative([report["elapsed_seconds"]])
    training.validate_result(report["result"], packet, directory)
    return report


def feature_selection(chosen: list[dict], encode) -> list[dict]:
    # This function cannot read labels, dates, contract, partition or dataset paths.
    selection = []
    for row in chosen:
        item = {key: row[key] for key in ("case_id", "input_sha256", "prompt")}
        ids = encode(item["prompt"])
        if (
            type(ids) is not list
            or not 1 <= len(ids) <= 2048
            or any(type(t) is not int or not 0 <= t < 151936 or t == 151643 for t in ids)
        ):
            raise ValueError("Original bounded prompt tokens required; no truncation")
        selection.append({**item, "prompt_tokens": len(ids), "prompt_ids_sha256": digest(ids)})
    validate_selection(selection, len(chosen))
    return selection


def validate_selection(selection: list, cases: int) -> None:
    if (
        type(cases) is not int
        or not 1 <= cases <= MAX_CASES
        or type(selection) is not list
        or len(selection) != cases
    ):
        raise ValueError("Complete bounded check selection required")
    ids = set()
    for item in selection:
        _fields(item, ("case_id", "input_sha256", "prompt", "prompt_tokens", "prompt_ids_sha256"))
        for name in ("case_id", "input_sha256", "prompt_ids_sha256"):
            check_digest(item[name])
        if (
            digest(task.payload_from_prompt(item["prompt"])) != item["input_sha256"]
            or type(item["prompt_tokens"]) is not int
            or not 1 <= item["prompt_tokens"] <= 2048
            or item["case_id"] in ids
        ):
            raise ValueError("Unique feature-only pinned context/token input required")
        ids.add(item["case_id"])


def feature_info(selection: list[dict]) -> dict:
    checksum, size = hashlib.sha256(), 0
    for item in selection:
        raw = (canonical(item) + "\n").encode()
        if len(raw) > controls.MAX_LINE:
            raise ValueError("Feature sidecar line budget exceeded")
        checksum.update(raw)
        size += len(raw)
    if not 1 <= size <= controls.MAX_BYTES:
        raise ValueError("Full feature-only sidecar budget exceeded")
    return {"bytes": size, "sha256": checksum.hexdigest()}


def disjoint(output: Path, value: dict, protected: list[Path]) -> None:
    training.disjoint(output, value)
    for path in protected:
        if output.resolve().is_relative_to(path.resolve()) or path.resolve().is_relative_to(
            output.resolve()
        ):
            raise ValueError("Output overlaps immutable registrations or trial directories")


def make_registration(
    controls_path: Path,
    controls_pin: str,
    controls_dir: Path,
    controls_report_pin: str,
    trial_dir: Path,
    trial_request_pin: str,
    trial_report_pin: str,
):
    cpu, value, chosen, cpu_report = controls.verified_run(
        controls_path, controls_pin, controls_dir, controls_report_pin
    )
    _, fit_rows = training.registration(
        Path(cpu["training_registration"]["path"]), cpu["training_registration"]["sha256"]
    )
    report = candidate(
        value,
        fit_rows,
        trial_dir,
        trial_request_pin,
        trial_report_pin,
        cpu["training_registration"]["sha256"],
    )
    encode = tokens.token_plan.load_tokenizer(
        Path(value["assets"]["tokenizer_json"]), value["assets"]["tokenizer_sha256"]
    )
    selection = feature_selection(chosen, encode)
    registered = {
        "kind": KIND,
        "protocol": protocol(),
        "source_sha256": source_sha256(),
        "controls_registration": {"path": str(controls_path.resolve()), "sha256": controls_pin},
        "controls_trial": {
            "directory": str(controls_dir.resolve()),
            "report_sha256": controls_report_pin,
        },
        "training_trial": {
            "directory": str(trial_dir.resolve()),
            "request_sha256": trial_request_pin,
            "report_sha256": trial_report_pin,
        },
        "adapter_manifest": report["result"]["reload"]["adapter_manifest"],
        "comparison": value["comparison"],
        "feature_file": feature_info(selection),
        **FLAGS,
    }
    return registered, value, chosen, selection, cpu_report


def freeze(*args) -> dict:
    *inputs, output = args
    registered, value, _, _, _ = make_registration(*inputs)
    disjoint(output, value, [inputs[0], inputs[2], inputs[4]])
    _write(output, registered)
    return registered


def registration(path: Path, pin: str):
    registered = tokens.metadata(path, pin)
    _fields(registered, REG_FIELDS)
    if registered["source_sha256"] != source_sha256() or registered["protocol"] != protocol():
        raise ValueError("Fixed source-bound full-comparison registration required")
    _fields(registered["controls_registration"], ("path", "sha256"))
    _fields(registered["controls_trial"], ("directory", "report_sha256"))
    _fields(registered["training_trial"], ("directory", "request_sha256", "report_sha256"))
    c, d, t = (registered[k] for k in ("controls_registration", "controls_trial", "training_trial"))
    result = make_registration(
        _absolute(c["path"]),
        c["sha256"],
        _absolute(d["directory"]),
        d["report_sha256"],
        _absolute(t["directory"]),
        t["request_sha256"],
        t["report_sha256"],
    )
    if canonical(result[0]) != canonical(registered):
        raise ValueError("Full check inputs/targets/controls/adapter/authority changed")
    return result


def worker_packet(registered: dict, value: dict, pin: str, output: Path) -> dict:
    return {
        "kind": KIND,
        "protocol": protocol(),
        "source_sha256": source_sha256(),
        "registration_sha256": pin,
        "enable_development_evaluation": True,
        **value["assets"],
        "adapter": str(Path(registered["training_trial"]["directory"]) / "adapter"),
        "adapter_manifest_sha256": digest(registered["adapter_manifest"]),
        "output_dir": str(output.resolve()),
        "cases": registered["comparison"]["cases"],
        "feature_file": registered["feature_file"],
    }


def validate_packet(packet: dict, *, verify_assets=True):
    _fields(packet, PACKET_FIELDS)
    if (
        packet["kind"] != KIND
        or packet["protocol"] != protocol()
        or packet["source_sha256"] != source_sha256()
        or packet["enable_development_evaluation"] is not True
        or len(canonical(packet).encode()) > MAX_PACKET_BYTES
        or type(packet["cases"]) is not int
        or not 1 <= packet["cases"] <= MAX_CASES
    ):
        raise ValueError("Fixed complete inference-only request/protocol/source/opt-in required")
    check_digest(packet["registration_sha256"])
    _fields(packet["feature_file"], ("bytes", "sha256"))
    check_digest(packet["feature_file"]["sha256"])
    if (
        type(packet["feature_file"]["bytes"]) is not int
        or not 1 <= packet["feature_file"]["bytes"] <= controls.MAX_BYTES
    ):
        raise ValueError("Bounded pinned feature sidecar required")
    pins, runtime = training.validate_assets(packet, verify_assets=verify_assets)
    output = _absolute(packet["output_dir"])
    if not output.parent.is_dir():
        raise ValueError("Existing parent for owned output required")
    adapter = _absolute(packet["adapter"])
    check_digest(packet["adapter_manifest_sha256"])
    if (
        adapter.is_symlink()
        or output.resolve().is_relative_to(adapter)
        or adapter.is_relative_to(output.resolve())
    ):
        raise ValueError("Regular adapter must be disjoint from output")
    if verify_assets and digest(adapter_manifest(adapter)) != packet["adapter_manifest_sha256"]:
        raise ValueError("Pinned quarantined adapter changed")
    return pins, runtime


def read_selection(packet: dict) -> list[dict]:
    selection = controls.lines(
        Path(packet["output_dir"]) / "features.jsonl", packet["feature_file"]
    )
    validate_selection(selection, packet["cases"])
    return selection


def validate_resources(r: dict) -> None:
    _fields(
        r,
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
        type(r["device"]) is not str
        or not 1 <= len(r["device"]) <= 128
        or any(
            type(r[k]) is not int or r[k] <= 0
            for k in ("total_bytes", "peak_allocated_bytes", "peak_reserved_bytes")
        )
        or not r["peak_allocated_bytes"] <= r["peak_reserved_bytes"] <= r["total_bytes"]
        or r["cuda_bf16"] is not True
        or r["deterministic_algorithms"] is not True
        or r["tf32_enabled"] is not False
    ):
        raise ValueError("Native resource/precision guards differ")


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
    _, runtime = validate_packet(packet)
    if (
        result["kind"] != KIND
        or result["request_sha256"] != digest(packet)
        or type(result["completed_calls"]) is not int
        or result["completed_calls"] != 2 * packet["cases"]
        or result["parameters_frozen"] is not True
        or result["runtime"] != runtime
        or any(result[k] is not v for k, v in FLAGS.items())
        or (directory / "failure.json").exists()
        or str(directory.resolve()) != packet["output_dir"]
    ):
        raise ValueError("All paired frozen outputs required; no successful-subset scoring")
    validate_resources(result["resources"])
    _fields(result["files"], ("predictions.jsonl", "events.jsonl"))
    predictions = controls.lines(
        directory / "predictions.jsonl", result["files"]["predictions.jsonl"]
    )
    if len(predictions) != 2 * packet["cases"]:
        raise ValueError("Every paired prediction required")
    events = [
        {"event": "native_initialization_started"},
        {"event": "native_initialization_completed"},
    ]
    for index, item in enumerate(read_selection(packet)):
        for offset, mode in enumerate(legacy.MODES):
            call = 2 * index + offset + 1
            row = predictions[call - 1]
            legacy.validate_prediction(row)
            binding = legacy.binding(call, mode, item)
            if any(type(row[k]) is not type(v) or row[k] != v for k, v in binding.items()):
                raise ValueError("Paired prediction order/case/mode/input differs")
            events.extend(
                [
                    {"event": "prediction_intent", **binding},
                    {"event": "prediction_completed", **binding, "prediction_sha256": digest(row)},
                ]
            )
    events.append({"event": "inference_completed"})
    if canonical(
        controls.lines(directory / "events.jsonl", result["files"]["events.jsonl"])
    ) != canonical(events):
        raise ValueError("Complete durable inference journal differs")
    return predictions


def score(chosen: list[dict], predictions: list[dict], cpu_report: dict) -> dict:
    if len(predictions) != 2 * len(chosen):
        raise ValueError("No subset scores")
    parsed, reasons = {}, {}
    for mode in legacy.MODES:
        forecasts = [legacy.forecast(row) for row in predictions if row["mode"] == mode]
        parsed[mode] = [forecast for forecast, _ in forecasts]
        reasons[mode] = dict(Counter(reason for _, reason in forecasts))
    result = controls.scores(chosen, parsed)
    result["scores"].update(cpu_report["scores"])
    if set(result["per_session_scores"]) != set(cpu_report["per_session_scores"]):
        raise ValueError("Same complete CPU/GPU session set required")
    for session in result["per_session_scores"]:
        result["per_session_scores"][session].update(cpu_report["per_session_scores"][session])
    return {**result, "output_status_counts": reasons}


def run(path: Path, pin: str, output: Path, *, enable_development_evaluation=False) -> dict:
    if enable_development_evaluation is not True:
        raise ValueError("Explicit full-set local GPU evaluation opt-in required")
    registered, value, chosen, selection, cpu_report = registration(path, pin)
    disjoint(
        output,
        value,
        [
            path,
            Path(registered["controls_registration"]["path"]),
            Path(registered["controls_trial"]["directory"]),
            Path(registered["training_trial"]["directory"]),
        ],
    )
    packet = worker_packet(registered, value, pin, output)
    validate_packet(packet)
    output.mkdir(exist_ok=False)
    started, stage = time.monotonic(), "gpu_comparison"
    try:
        _write(output / "request.json", packet)
        with (output / "features.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for item in selection:
                controls._event(stream, item)
        read_selection(packet)
        result = strict_json(
            _exchange([packet["python_executable"], "-I", "-m", WORKER], packet, TIMEOUT_MS)
        )
        predictions = validate_result(result, packet, output)
        stage = "post_comparison_pins"
        final = registration(path, pin)
        if canonical(final) != canonical((registered, value, chosen, selection, cpu_report)):
            raise ValueError("Frozen full comparison/candidate/CPU artifacts drifted")
        report = {
            "status": "completed_full_inner_check_comparison_not_validation",
            "registration_sha256": pin,
            "gpu_result": result,
            "examples": len(chosen),
            "source_sessions": len(value["session_split"]["check"]),
            **score(chosen, predictions, cpu_report),
            "elapsed_seconds": time.monotonic() - started,
            "adapter_quarantined": True,
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
                    "adapter_quarantined": True,
                    **FLAGS,
                },
            )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    for name in (
        "controls-registration",
        "controls-directory",
        "trial-directory",
        "registration",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=name == "output")
    for name in (
        "controls-registration-sha256",
        "controls-report-sha256",
        "trial-request-sha256",
        "trial-report-sha256",
        "registration-sha256",
    ):
        parser.add_argument("--" + name)
    parser.add_argument("--enable-development-evaluation", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        inputs = (
            args.controls_registration,
            args.controls_registration_sha256,
            args.controls_directory,
            args.controls_report_sha256,
            args.trial_directory,
            args.trial_request_sha256,
            args.trial_report_sha256,
        )
        if any(v is None for v in inputs):
            parser.error("Pinned complete CPU controls and quarantined context-v2 pilot required")
        result = freeze(*inputs, args.output)
    else:
        if args.registration is None or args.registration_sha256 is None:
            parser.error("Pinned full-comparison registration required")
        result = run(
            args.registration,
            args.registration_sha256,
            args.output,
            enable_development_evaluation=args.enable_development_evaluation,
        )
    print(canonical({"kind": KIND, "status": result.get("status", "registered_not_run")}))


if __name__ == "__main__":
    main()
