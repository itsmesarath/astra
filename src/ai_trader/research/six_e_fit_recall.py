"""Seen-fit recall diagnostic for the immutable 192-update context-v2 pilot, not validation."""

from __future__ import annotations

import argparse
import hashlib
import os
import statistics
import time
from collections import Counter
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, check_digest, digest, strict_json
from ai_trader.models.local_reviewer import _exchange
from ai_trader.research import six_e_context_eval as previous
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import _absolute
from ai_trader.training.lora_backend import adapter_manifest

controls, training, legacy = previous.controls, previous.training, previous.legacy
KIND = "six_e_context_v2_original_192_fit_recall_diagnostic"
WORKER = "ai_trader.models._six_e_fit_recall_worker"
CASES, MAX_PACKET_BYTES, MAX_BYTES, TIMEOUT_MS = 192, 64 * 1024, 2 * 1024**2, 1_800_000
FLAGS = dict(previous.FLAGS)
STATUS = "completed_original_seen_fit_recall_not_validation"
PACKET_FIELDS = (
    "kind",
    "protocol",
    "source_sha256",
    "registration_sha256",
    "enable_fit_diagnostic",
    *legacy.ASSET_PATHS,
    *legacy.ASSET_PINS,
    "output_dir",
    "cases",
    "feature_file",
)
REG_FIELDS = (
    "kind",
    "protocol",
    "source_sha256",
    "completed_comparison",
    "adapter_manifest",
    "ordered_examples_sha256",
    "feature_file",
    "fit_joint_counts",
    "training_trace",
    *FLAGS,
)


def protocol() -> dict:
    return {
        "kind": KIND,
        "scope": "ALL 192 unique examples used by the original pilot, in original update order. "
        "Seen train/inner-fit recall ONLY; not development, holdout, broker fills or PnL.",
        "selection": "Original completed training packet, bound to its frozen registration; "
        "no new sampling, outcome-based selection, class reweighting or optimizer updates.",
        "inference": training.protocol()["comparison"]["decoding"],
        "controls": ["no_opportunity", "inner_fit_joint_prior"],
        "trace": "Original online PRE-update loss by class; not post-fit loss or fit accuracy. "
        "The single reload probe is identified by its original first-example class.",
        "bounds": {
            "cases": CASES,
            "calls": 2 * CASES,
            "worker_seconds": TIMEOUT_MS // 1000,
            "packet_bytes": MAX_PACKET_BYTES,
            "artifact_bytes": MAX_BYTES,
            "line_bytes": controls.MAX_LINE,
        },
        "scoring": "Every paired prediction and all 771 durable journal events required; "
        "invalid outputs incorrect, never abstention. No retries or successful-subset scoring.",
        "durability": "Native result is saved and fsynced before transport/supervisor reporting. "
        "Report writer and pinned metadata reader both enforce the declared 2 MiB artifact limit.",
        "registration_authorizes_execution": False,
        **FLAGS,
    }


def source_sha256() -> str:
    root = Path(__file__).resolve().parents[1]
    return digest(
        {
            "immutable_completed_evaluation": previous.source_sha256(),
            **{
                name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in (
                    "research/six_e_fit_recall.py",
                    "models/_six_e_fit_recall_worker.py",
                )
            },
        }
    )


def write_artifact(path: Path, value: dict) -> None:
    """Exclusive durable metadata, bounded by this protocol rather than the legacy 1 MiB cap."""
    raw = (canonical(value) + "\n").encode("utf-8")
    if not 1 <= len(raw) <= MAX_BYTES:
        raise ValueError("Diagnostic artifact byte budget exceeded before write")
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def selected_fit(packet: dict, value: dict) -> list[dict]:
    # All membership gates precede any prompt/target reads, including serialization.
    selection = packet["selection"]
    if type(selection) is not list or len(selection) != CASES:
        raise ValueError("Every original training example required")
    for item in selection:
        row = item["example"]
        if (
            row["role"] != "train"
            or row["inner_partition"] != "fit"
            or row["source_session"] not in value["session_split"]["fit"]
        ):
            raise ValueError("Seen fit membership gate before prompt/target access")
    if canonical([i["spec"] for i in selection]) != canonical(value["selection"]):
        raise ValueError("Original ordered training selection differs")
    training.validate_packet(packet)
    return [i["example"] for i in selection]


def fit_gate(chosen: list[dict]) -> None:
    if type(chosen) is not list or len(chosen) != CASES:
        raise ValueError("All original seen-fit examples required")
    for row in chosen:
        if row["role"] != "train" or row["inner_partition"] != "fit":
            raise ValueError("Seen-fit scoring gate before prompt/target access")
    for row in chosen:
        previous.task.model_view(row, for_training=True)
    if len({row["case_id"] for row in chosen}) != CASES:
        raise ValueError("Unique original seen-fit examples required")


def trace_audit(chosen: list[dict], metrics: list[dict], reload: dict) -> dict:
    if len(chosen) != CASES or len(metrics) != CASES:
        raise ValueError("Every original pre-update metric required")
    fit_gate(chosen)
    groups = {}
    for state in training.STATES:
        values = [
            m["loss"]
            for row, m in zip(chosen, metrics, strict=True)
            if controls.state_of(row) == state
        ]
        training.finite_nonnegative(values)
        groups[state] = {
            "examples": len(values),
            "mean_pre_update_loss": statistics.mean(values) if values else None,
            "median_pre_update_loss": statistics.median(values) if values else None,
            "min_pre_update_loss": min(values) if values else None,
            "max_pre_update_loss": max(values) if values else None,
        }
    return {
        "interpretation": protocol()["trace"],
        "by_joint_state": groups,
        "reload_probe": {
            "case_id": chosen[0]["case_id"],
            "joint_state": controls.state_of(chosen[0]),
            **{
                k: reload[k]
                for k in ("probe_loss_before", "probe_loss_after", "probe_loss_absolute_tolerance")
            },
        },
    }


def verified_comparison(path: Path, pin: str, directory: Path, report_pin: str):
    registered, value, chosen, _, cpu = previous.registration(path, pin)
    report = previous.tokens.metadata(directory / "run.json", report_pin)
    _fields(
        report,
        (
            "status",
            "registration_sha256",
            "gpu_result",
            "examples",
            "source_sessions",
            "scores",
            "per_session_scores",
            "truth_joint_counts",
            "output_status_counts",
            "elapsed_seconds",
            "adapter_quarantined",
            *FLAGS,
        ),
    )
    if (
        directory.is_symlink()
        or report["status"] != "completed_full_inner_check_comparison_not_validation"
        or report["registration_sha256"] != pin
        or report["adapter_quarantined"] is not True
        or type(report["examples"]) is not int
        or report["examples"] != len(chosen)
        or type(report["source_sessions"]) is not int
        or report["source_sessions"] != len(value["session_split"]["check"])
        or any(report[k] is not v for k, v in FLAGS.items())
    ):
        raise ValueError("Verified complete development comparison required, never a subset")
    packet = previous.worker_packet(registered, value, pin, directory)
    saved = previous.tokens.metadata(
        directory / "request.json", controls.file_info(directory / "request.json")["sha256"]
    )
    if canonical(saved) != canonical(packet):
        raise ValueError("Completed comparison request differs")
    predictions = previous.validate_result(report["gpu_result"], packet, directory)
    for key, metric in previous.score(chosen, predictions, cpu).items():
        if canonical(report[key]) != canonical(metric):
            raise ValueError("Completed development metrics differ")
    training.finite_nonnegative([report["elapsed_seconds"]])
    return registered, value


def make_registration(path: Path, pin: str, directory: Path, report_pin: str):
    old, value = verified_comparison(path, pin, directory, report_pin)
    trial = old["training_trial"]
    trial_dir = _absolute(trial["directory"])
    packet = previous.tokens.metadata(trial_dir / "request.json", trial["request_sha256"])
    report = previous.tokens.metadata(trial_dir / "run.json", trial["report_sha256"])
    chosen = selected_fit(packet, value)
    metrics = training.validate_result(report["result"], packet, trial_dir)
    encode = previous.tokens.token_plan.load_tokenizer(
        Path(value["assets"]["tokenizer_json"]), value["assets"]["tokenizer_sha256"]
    )
    selection = previous.feature_selection(chosen, encode)
    info = previous.feature_info(selection)
    if info["bytes"] > MAX_BYTES:
        raise ValueError("Seen-fit feature byte budget exceeded")
    registered = {
        "kind": KIND,
        "protocol": protocol(),
        "source_sha256": source_sha256(),
        "completed_comparison": {
            "registration": str(path.resolve()),
            "registration_sha256": pin,
            "directory": str(directory.resolve()),
            "report_sha256": report_pin,
        },
        "adapter_manifest": old["adapter_manifest"],
        "ordered_examples_sha256": digest([digest(r) for r in chosen]),
        "feature_file": info,
        "fit_joint_counts": value["fit_joint_counts"],
        "training_trace": trace_audit(chosen, metrics, report["result"]["reload"]),
        **FLAGS,
    }
    return registered, value, chosen, selection, old


def protected(old: dict, path: Path, directory: Path) -> list[Path]:
    return [
        path,
        directory,
        Path(old["training_trial"]["directory"]),
        Path(old["controls_trial"]["directory"]),
        Path(old["controls_registration"]["path"]),
    ]


def freeze(path: Path, pin: str, directory: Path, report_pin: str, output: Path) -> dict:
    registered, value, _, _, old = make_registration(path, pin, directory, report_pin)
    previous.disjoint(output, value, protected(old, path, directory))
    write_artifact(output, registered)
    return registered


def registration(path: Path, pin: str):
    registered = previous.tokens.metadata(path, pin)
    _fields(registered, REG_FIELDS)
    if (
        registered["kind"] != KIND
        or registered["protocol"] != protocol()
        or registered["source_sha256"] != source_sha256()
    ):
        raise ValueError("Frozen original-fit diagnostic protocol/source required")
    item = registered["completed_comparison"]
    _fields(item, ("registration", "registration_sha256", "directory", "report_sha256"))
    result = make_registration(
        _absolute(item["registration"]),
        item["registration_sha256"],
        _absolute(item["directory"]),
        item["report_sha256"],
    )
    if canonical(result[0]) != canonical(registered):
        raise ValueError("Original-fit selection/trace/adapter/completed evidence drifted")
    return result


def worker_packet(registered: dict, value: dict, pin: str, output: Path, old: dict) -> dict:
    return {
        "kind": KIND,
        "protocol": protocol(),
        "source_sha256": source_sha256(),
        "registration_sha256": pin,
        "enable_fit_diagnostic": True,
        **value["assets"],
        "adapter": str(Path(old["training_trial"]["directory"]) / "adapter"),
        "adapter_manifest_sha256": digest(registered["adapter_manifest"]),
        "output_dir": str(output.resolve()),
        "cases": CASES,
        "feature_file": registered["feature_file"],
    }


def validate_packet(packet: dict, *, verify_assets=True):
    _fields(packet, PACKET_FIELDS)
    if (
        packet["kind"] != KIND
        or packet["protocol"] != protocol()
        or packet["source_sha256"] != source_sha256()
        or packet["enable_fit_diagnostic"] is not True
        or type(packet["cases"]) is not int
        or packet["cases"] != CASES
        or len(canonical(packet).encode()) > MAX_PACKET_BYTES
    ):
        raise ValueError("Fixed 192-case inference-only diagnostic and opt-in required")
    check_digest(packet["registration_sha256"])
    _fields(packet["feature_file"], ("bytes", "sha256"))
    check_digest(packet["feature_file"]["sha256"])
    if (
        type(packet["feature_file"]["bytes"]) is not int
        or not 1 <= packet["feature_file"]["bytes"] <= MAX_BYTES
    ):
        raise ValueError("Bounded pinned original-fit features required")
    pins, runtime = training.validate_assets(packet, verify_assets=verify_assets)
    output, adapter = _absolute(packet["output_dir"]), _absolute(packet["adapter"])
    check_digest(packet["adapter_manifest_sha256"])
    if (
        not output.parent.is_dir()
        or adapter.is_symlink()
        or output.is_relative_to(adapter)
        or adapter.is_relative_to(output)
    ):
        raise ValueError("Owned output must be disjoint from immutable adapter")
    if verify_assets and digest(adapter_manifest(adapter)) != packet["adapter_manifest_sha256"]:
        raise ValueError("Quarantined adapter changed")
    return pins, runtime


def read_selection(packet: dict) -> list[dict]:
    selection = controls.lines(
        Path(packet["output_dir"]) / "features.jsonl", packet["feature_file"]
    )
    previous.validate_selection(selection, CASES)
    return selection


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
        or result["completed_calls"] != 2 * CASES
        or result["parameters_frozen"] is not True
        or result["runtime"] != runtime
        or any(result[k] is not v for k, v in FLAGS.items())
        or (directory / "failure.json").exists()
        or str(directory.resolve()) != packet["output_dir"]
    ):
        raise ValueError("Every frozen paired original-fit prediction required; no subset score")
    previous.validate_resources(result["resources"])
    native_path = directory / "gpu_result.json"
    native_info = controls.file_info(native_path, MAX_BYTES)
    native = previous.tokens.metadata(native_path, native_info["sha256"])
    if canonical(native) != canonical(result):
        raise ValueError("Persisted complete native result differs from transported evidence")
    _fields(result["files"], ("predictions.jsonl", "events.jsonl"))
    for name, info in result["files"].items():
        if controls.file_info(directory / name, MAX_BYTES) != info:
            raise ValueError("Bounded pinned diagnostic output required")
    predictions = controls.lines(
        directory / "predictions.jsonl", result["files"]["predictions.jsonl"]
    )
    if len(predictions) != 2 * CASES:
        raise ValueError("All 384 predictions required")
    events = [
        {"event": "native_initialization_started"},
        {"event": "native_initialization_completed"},
    ]
    for index, item in enumerate(read_selection(packet)):
        for offset, mode in enumerate(legacy.MODES):
            call = 2 * index + offset + 1
            row, binding = predictions[call - 1], legacy.binding(call, mode, item)
            legacy.validate_prediction(row)
            if any(type(row[k]) is not type(v) or row[k] != v for k, v in binding.items()):
                raise ValueError("Original-fit prediction identity/mode/order differs")
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
        raise ValueError("All 771 durable diagnostic journal events required")
    return predictions


def score(chosen: list[dict], predictions: list[dict], counts: dict) -> dict:
    if len(chosen) != CASES or len(predictions) != 2 * CASES:
        raise ValueError("No successful-subset scores")
    fit_gate(chosen)
    parsed, reasons = {}, {}
    for offset, mode in enumerate(legacy.MODES):
        forecasts = []
        for i, row in enumerate(predictions[offset::2]):
            legacy.validate_prediction(row)
            binding = legacy.binding(2 * i + offset + 1, mode, chosen[i])
            if any(type(row[k]) is not type(v) or row[k] != v for k, v in binding.items()):
                raise ValueError("Exact ordered fit scoring binding required")
            forecasts.append(legacy.forecast(row))
        parsed[mode] = [forecast for forecast, _ in forecasts]
        reasons[mode] = dict(Counter(reason for _, reason in forecasts))
    _fields(counts, training.STATES)
    training.quotas(counts)
    prior = max(training.STATES, key=lambda state: counts[state])
    for name, state in (("no_opportunity", "NNN"), ("inner_fit_joint_prior", prior)):
        parsed[name] = [controls.balance.forecast(state)] * CASES
    metrics = controls.scores(chosen, parsed)
    by_cost = metrics["scores"]["adapter"]["by_cost"]
    calls = sum(v["directional_predictions"] for v in by_cost.values())
    correct = sum(v["correct_directional_predictions"] for v in by_cost.values())
    decision = (
        "invalid_outputs_prevent_recall_conclusion"
        if reasons["adapter"] != {"valid": CASES}
        else "collapse_on_seen_fit"
        if calls == 0
        else "directional_calls_without_correct_seen_fit_recall"
        if correct == 0
        else "some_seen_fit_recall_requires_separate_development_transfer"
    )
    return {**metrics, "output_status_counts": reasons, "diagnostic_conclusion": decision}


def run(path: Path, pin: str, output: Path, *, enable_fit_diagnostic=False) -> dict:
    if enable_fit_diagnostic is not True:
        raise ValueError("Explicit inference-only seen-fit diagnostic opt-in required")
    registered, value, chosen, selection, old = registration(path, pin)
    prior = registered["completed_comparison"]
    previous.disjoint(
        output,
        value,
        [path, *protected(old, Path(prior["registration"]), Path(prior["directory"]))],
    )
    packet = worker_packet(registered, value, pin, output, old)
    validate_packet(packet)
    output.mkdir(exist_ok=False)
    started, stage = time.monotonic(), "fit_recall_inference"
    try:
        write_artifact(output / "request.json", packet)
        with (output / "features.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for item in selection:
                controls._event(stream, item)
        read_selection(packet)
        result = strict_json(
            _exchange([packet["python_executable"], "-I", "-m", WORKER], packet, TIMEOUT_MS)
        )
        predictions = validate_result(result, packet, output)
        stage = "post_diagnostic_pins"
        if canonical(registration(path, pin)) != canonical(
            (registered, value, chosen, selection, old)
        ):
            raise ValueError("Frozen original-fit diagnostic inputs/evidence drifted")
        report = {
            "status": STATUS,
            "registration_sha256": pin,
            "gpu_result": result,
            "examples": CASES,
            "source_sessions": len({r["source_session"] for r in chosen}),
            **score(chosen, predictions, registered["fit_joint_counts"]),
            "training_trace": registered["training_trace"],
            "elapsed_seconds": time.monotonic() - started,
            "adapter_quarantined": True,
            **FLAGS,
        }
        write_artifact(output / "run.json", report)
        return report
    except BaseException as exc:
        if not (output / "run.json").exists():
            write_artifact(
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


def verify_run(path: Path, pin: str, directory: Path, report_pin: str) -> dict:
    """Recompute all completed evidence/scores without model calls or file writes."""
    registered, value, chosen, _, old = registration(path, pin)
    report = previous.tokens.metadata(directory / "run.json", report_pin)
    _fields(
        report,
        (
            "status",
            "registration_sha256",
            "gpu_result",
            "examples",
            "source_sessions",
            "scores",
            "per_session_scores",
            "truth_joint_counts",
            "output_status_counts",
            "diagnostic_conclusion",
            "training_trace",
            "elapsed_seconds",
            "adapter_quarantined",
            *FLAGS,
        ),
    )
    if (
        directory.is_symlink()
        or report["status"] != STATUS
        or report["registration_sha256"] != pin
        or report["adapter_quarantined"] is not True
        or type(report["examples"]) is not int
        or report["examples"] != CASES
        or type(report["source_sessions"]) is not int
        or report["source_sessions"] != len({row["source_session"] for row in chosen})
        or canonical(report["training_trace"]) != canonical(registered["training_trace"])
        or any(report[k] is not v for k, v in FLAGS.items())
    ):
        raise ValueError("Complete original seen-fit report required, never promotion")
    training.finite_nonnegative([report["elapsed_seconds"]])
    names = (
        "run.json",
        "request.json",
        "features.jsonl",
        "predictions.jsonl",
        "events.jsonl",
        "gpu_result.json",
    )
    before = {name: controls.file_info(directory / name, MAX_BYTES) for name in names}
    packet = worker_packet(registered, value, pin, directory, old)
    saved = previous.tokens.metadata(directory / "request.json", before["request.json"]["sha256"])
    if canonical(saved) != canonical(packet):
        raise ValueError("Persisted fit diagnostic request differs")
    predictions = validate_result(report["gpu_result"], packet, directory)
    for key, metric in score(chosen, predictions, registered["fit_joint_counts"]).items():
        if canonical(report[key]) != canonical(metric):
            raise ValueError("Original seen-fit report metrics differ")
    after = {name: controls.file_info(directory / name, MAX_BYTES) for name in names}
    if canonical(after) != canonical(before) or before["run.json"]["sha256"] != report_pin:
        raise ValueError("Completed diagnostic evidence drifted during verification")
    return {
        "status": "verified_seen_fit_diagnostic_not_validation",
        "files": after,
        "examples": CASES,
        "source_sessions": report["source_sessions"],
        "completed_calls": 2 * CASES,
        "journal_events": 4 * CASES + 3,
        "diagnostic_conclusion": report["diagnostic_conclusion"],
        "output_status_counts": report["output_status_counts"],
        **FLAGS,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "verify"))
    for name in ("completed-registration", "completed-directory", "registration", "output"):
        parser.add_argument("--" + name, type=Path, required=name == "output")
    for name in ("completed-registration-sha256", "completed-report-sha256", "registration-sha256"):
        parser.add_argument("--" + name)
    parser.add_argument("--report-sha256")
    parser.add_argument("--enable-fit-diagnostic", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        inputs = (
            args.completed_registration,
            args.completed_registration_sha256,
            args.completed_directory,
            args.completed_report_sha256,
        )
        if any(v is None for v in inputs):
            parser.error("Pinned verified full comparison required")
        result = freeze(*inputs, args.output)
    else:
        if args.registration is None or args.registration_sha256 is None:
            parser.error("Pinned original-fit diagnostic registration required")
        if args.action == "verify":
            if args.report_sha256 is None:
                parser.error("Pinned completed original-fit report required")
            result = verify_run(
                args.registration, args.registration_sha256, args.output, args.report_sha256
            )
        else:
            result = run(
                args.registration,
                args.registration_sha256,
                args.output,
                enable_fit_diagnostic=args.enable_fit_diagnostic,
            )
    print(canonical({"kind": KIND, "status": result.get("status", "registered_not_run")}))


if __name__ == "__main__":
    main()
