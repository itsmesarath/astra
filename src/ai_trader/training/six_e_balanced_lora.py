"""Separate source-bound 224-update 6E research trial; no evaluation or trading."""

from __future__ import annotations

import argparse
import hashlib
import math
import time
from datetime import date
from importlib.metadata import distributions
from pathlib import Path

from ai_trader.models.local_checkpoint import (
    canonical,
    check_digest,
    digest,
    inspect_checkpoint,
    strict_json,
)
from ai_trader.models.local_reviewer import _exchange
from ai_trader.training import six_e_balance_plan as balance
from ai_trader.training import six_e_forecast as task
from ai_trader.training import six_e_lora_trial as trial
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import _absolute, _lock_pin, _runtime_shape, _write
from ai_trader.training.lora_backend import MAX_TRAINABLE_PARAMETERS, adapter_manifest
from ai_trader.training.qwen_gpu_smoke import finite_nonnegative

KIND = "six_e_balanced_224_update_lora_v1"
WORKER = "ai_trader.training._six_e_balanced_worker"
STEPS, COMPARISON_CASES, TIMEOUT_MS = 224, 80, 1_800_000
MAX_REQUEST_BYTES, MAX_JOURNAL_BYTES = 1024**2, 256 * 1024
FLAGS = {**trial.NO_AUTHORITY, "reserved_outcomes_opened": False, "trading_enabled": False}
ASSET_PATHS = (
    "python_executable",
    "checkpoint",
    "dependency_lock",
    "runtime_manifest",
    "tokenizer_json",
)
ASSET_PINS = (
    "checkpoint_sha256",
    "dependency_lock_sha256",
    "runtime_sha256",
    "tokenizer_sha256",
)
SPEC_FIELDS = (
    "example_index",
    "joint_state",
    "case_id",
    "source_session",
    "input_sha256",
    "target_sha256",
    "record_sha256",
    "prompt_tokens",
    "completion_with_eos_tokens",
    "active_tokens",
)
PACKET_FIELDS = (
    "kind",
    "profile",
    "source_sha256",
    "registration_sha256",
    "enable_research_training",
    *ASSET_PATHS,
    *ASSET_PINS,
    "output_dir",
    "session_split",
    "selection",
)


def profile() -> dict:
    return {
        **balance.protocol()["qwen_curriculum"]["recipe"],
        "purpose": KIND,
        "limits_enforced_by_training_worker": True,
        "cublas_workspace_config": ":4096:8",
        "eos_token_id": 151643,
        "pad_token_id": 151643,
        "initialization": "Fresh pinned base and fresh LoRA; no adapter path or resume",
        "selection": "Exactly the upstream 224 unique inner-fit cases, original round-robin order",
        "evaluation": "None during training; training-record save/reload probe only",
    }


def protocol() -> dict:
    return {
        "kind": KIND,
        "profile": profile(),
        "worker_timeout_seconds": TIMEOUT_MS // 1000,
        "packet": "Selected supervised training examples only; no dataset, upstream plan, "
        "CPU model or comparison paths/rows in native payload",
        "comparison": {
            "cases": COMPARISON_CASES,
            "selection": "Even rank indices of all inner check rows, fixed before this fit",
            "exposure": "Already-exposed within-training development, NOT independent",
            "modes": ["base", "adapter"],
            "controls": list(balance.protocol()["controls"]),
            "decoding": balance.evaluation.protocol()["inference"],
            "worker_timeout_seconds": 600,
            "metrics": "Strict output coverage, per-cost class/directional metrics and fixed "
            "controls; no PnL or deployment decision",
            "run_now": False,
        },
        "registration_authorizes_execution": False,
        "cpu_provenance": "Historical CPU Python/platform and installed NumPy metadata verified; "
        "GPU runtime separately pinned. Rebuild selection with integer/hash operations only; "
        "do not refit or reinterpret historical CPU scores in the GPU environment",
        **FLAGS,
    }


def source_sha256() -> str:
    return digest(
        {
            "immutable_balance_and_native_backend": balance.source_sha256(),
            **{
                name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                for name in ("six_e_balanced_lora.py", "_six_e_balanced_worker.py")
            },
        }
    )


def load_balance(path: Path, pin: str) -> tuple[dict, dict, list[dict]]:
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
            *balance.FLAGS,
        ),
    )
    if plan["protocol"] != balance.protocol() or plan["source_sha256"] != balance.source_sha256():
        raise ValueError("Immutable balance protocol/source changed")
    prior = plan["prior_trial"]
    _fields(prior, ("directory", "request_sha256", "report_sha256"))
    rebuilt, request, rows = balance.make_plan(
        Path(prior["directory"]), prior["request_sha256"], prior["report_sha256"]
    )
    # Selection/audits use integer/hash operations, not NumPy. Preserve and verify the
    # CPU fit's own runtime instead of equating it with the separately pinned GPU runtime.
    cpu = plan["cpu_runtime"]
    _fields(cpu, tuple(rebuilt["cpu_runtime"]))
    _absolute(cpu["python_executable"])
    executable = Path(cpu["python_executable"])
    if (
        executable.is_symlink()
        or not executable.is_file()
        or any(
            cpu[key] != rebuilt["cpu_runtime"][key]
            for key in ("python_version", "system", "machine")
        )
    ):
        raise ValueError("Original CPU provenance/runtime differs")
    if cpu["python_executable"] == rebuilt["cpu_runtime"]["python_executable"]:
        numpy_versions = [rebuilt["cpu_runtime"]["numpy"]]
    else:
        # Read distribution metadata only: never execute an upstream interpreter or import
        # its packages. This worker is deliberately restricted to the Windows venv layout.
        packages = executable.parent.parent / "Lib" / "site-packages"
        if executable.parent.name != "Scripts" or packages.is_symlink() or not packages.is_dir():
            raise ValueError("Known Windows CPU venv provenance required")
        numpy_versions = [
            dist.version
            for dist in distributions(path=[str(packages)])
            if dist.metadata["Name"].lower() == "numpy"
        ]
    if numpy_versions != [cpu["numpy"]]:
        raise ValueError("Original CPU NumPy provenance differs")
    rebuilt["cpu_runtime"] = cpu
    if canonical(plan) != canonical(rebuilt):
        raise ValueError("Frozen training-only split/curriculum/accounting/authority differs")
    return plan, request, rows


def controls(
    directory: Path, report_pin: str, model_pin: str, plan: dict, balance_pin: str
) -> dict:
    if directory.is_symlink() or not directory.is_dir() or (directory / "failure.json").exists():
        raise ValueError("Complete regular frozen CPU controls required")
    report = trial.metadata(directory / "run.json", report_pin)
    models = trial.metadata(directory / "models.json", model_pin)
    if (
        report["status"] != "completed_within_train_temporal_development_controls_not_validated"
        or report["registration_sha256"] != balance_pin
        or report["source_sha256"] != plan["source_sha256"]
        or report["cpu_runtime"] != plan["cpu_runtime"]
        or report["models_quarantined"] is not True
        or report["cpu_controls_fitted"] != 2
        or any(report[k] is not v for k, v in balance.FLAGS.items())
        or report["models_file"] != balance.evaluation.file_info(directory / "models.json")
        or report["models_file"]["sha256"] != model_pin
        or report["model_content_sha256"] != digest(models)
        or set(models) != set(balance.MODES)
        or any(
            report[pool + "_examples"] != plan["audits"]["inner_" + pool]["examples"]
            or report[pool + "_sessions"] != len(plan["session_split"][pool])
            for pool in ("fit", "check")
        )
    ):
        raise ValueError("CPU comparison controls/lineage changed")
    for name, model in models.items():
        if model["weight_power"] != balance.MODES[name]:
            raise ValueError("CPU control identity differs")
        balance.predict(model, [[0.0] * len(task.FEATURES)])
    return {
        "directory": str(directory.resolve()),
        "report_sha256": report_pin,
        "models_sha256": model_pin,
        "model_content_sha256": digest(models),
    }


def encoded(example: dict, encode) -> tuple[dict, dict]:
    text, answer = task.model_view(example, for_training=True)
    prompt, completion = encode(text), encode(answer)
    record = trial.token_plan.completion_only_record(
        prompt, completion, eos_token_id=151643, pad_token_id=151643
    )
    return {
        "record_sha256": digest(record),
        "prompt_tokens": len(prompt),
        "completion_with_eos_tokens": len(completion) + 1,
        "active_tokens": sum(record["attention_mask"]),
    }, record


def make_registration(
    balance_path: Path,
    balance_pin: str,
    control_directory: Path,
    control_report_pin: str,
    control_model_pin: str,
) -> tuple[dict, dict, list[dict]]:
    plan, request, rows = load_balance(balance_path, balance_pin)
    control = controls(control_directory, control_report_pin, control_model_pin, plan, balance_pin)
    encode = trial.token_plan.load_tokenizer(
        Path(request["tokenizer_json"]), request["tokenizer_sha256"]
    )
    selection = []
    for spec in plan["curriculum"]:
        example = rows[spec["example_index"]]
        token_info, _ = encoded(example, encode)
        selection.append({**spec, **token_info})
    check_rows = [
        (i, row)
        for i, row in enumerate(rows)
        if row["source_session"] in plan["session_split"]["check"]
    ]
    indices = balance.even_indices(len(check_rows), COMPARISON_CASES)
    comparison = []
    for index in indices:
        original_index, row = check_rows[index]
        prompt_tokens = encode(row["prompt"])
        if not 1 <= len(prompt_tokens) <= trial.token_plan.MAX_PROMPT_TOKENS or any(
            type(t) is not int or not 0 <= t < 151936 or t == 151643 for t in prompt_tokens
        ):
            raise ValueError("Bounded comparison prompt required; no truncation")
        comparison.append(
            {
                "check_index": index,
                "example_index": original_index,
                **{
                    k: row[k]
                    for k in ("case_id", "source_session", "input_sha256", "target_sha256")
                },
                "prompt_tokens": len(prompt_tokens),
            }
        )
    value = {
        "kind": KIND,
        "protocol": protocol(),
        "source_sha256": source_sha256(),
        "balance_plan": {"path": str(balance_path.resolve()), "sha256": balance_pin},
        "controls": control,
        "assets": {k: request[k] for k in (*ASSET_PATHS, *ASSET_PINS)},
        "session_split": plan["session_split"],
        "selection": selection,
        "comparison": comparison,
        **FLAGS,
    }
    return value, request, rows


def freeze(
    balance_path: Path,
    balance_pin: str,
    control_directory: Path,
    control_report_pin: str,
    control_model_pin: str,
    output: Path,
) -> dict:
    value, request, _ = make_registration(
        balance_path, balance_pin, control_directory, control_report_pin, control_model_pin
    )
    disjoint(output, request, value)
    _write(output, value)
    return value


def registration(path: Path, pin: str) -> tuple[dict, dict, list[dict]]:
    value = trial.metadata(path, pin)
    _fields(
        value,
        (
            "kind",
            "protocol",
            "source_sha256",
            "balance_plan",
            "controls",
            "assets",
            "session_split",
            "selection",
            "comparison",
            *FLAGS,
        ),
    )
    if value["protocol"] != protocol() or value["source_sha256"] != source_sha256():
        raise ValueError("New source-bound registration required")
    _fields(value["balance_plan"], ("path", "sha256"))
    _fields(
        value["controls"], ("directory", "report_sha256", "models_sha256", "model_content_sha256")
    )
    b, c = value["balance_plan"], value["controls"]
    rebuilt, request, rows = make_registration(
        Path(b["path"]), b["sha256"], Path(c["directory"]), c["report_sha256"], c["models_sha256"]
    )
    if canonical(value) != canonical(rebuilt):
        raise ValueError("Frozen assets, selections, comparisons or authority changed")
    return value, request, rows


def disjoint(output: Path, request: dict, value: dict) -> None:
    balance.evaluation.disjoint(output, request, Path(value["controls"]["directory"]))
    for protected in (Path(value["balance_plan"]["path"]), Path(request["output_dir"])):
        if output.resolve().is_relative_to(
            protected.resolve()
        ) or protected.resolve().is_relative_to(output.resolve()):
            raise ValueError("New output cannot overlap prior trial or frozen plan")


def worker_packet(value: dict, rows: list[dict], pin: str, output: Path) -> dict:
    packet = {
        "kind": KIND,
        "profile": profile(),
        "source_sha256": source_sha256(),
        "registration_sha256": pin,
        "enable_research_training": True,
        **value["assets"],
        "output_dir": str(output.resolve()),
        "session_split": value["session_split"],
        "selection": [
            {"spec": spec, "example": rows[spec["example_index"]]} for spec in value["selection"]
        ],
    }
    validate_packet(packet)
    return packet


def validate_packet(packet: dict, *, verify_assets=True) -> tuple[dict, dict]:
    _fields(packet, PACKET_FIELDS)
    if (
        packet["kind"] != KIND
        or canonical(packet["profile"]) != canonical(profile())
        or packet["source_sha256"] != source_sha256()
        or packet["enable_research_training"] is not True
        or len(canonical(packet).encode()) > MAX_REQUEST_BYTES
    ):
        raise ValueError("Bounded fixed source/profile and explicit training opt-in required")
    for key in (*ASSET_PATHS, "output_dir"):
        _absolute(packet[key])
        if Path(packet[key]).is_symlink():
            raise ValueError("Regular native paths required")
    output, base = Path(packet["output_dir"]).resolve(), Path(packet["checkpoint"]).resolve()
    if (
        output.is_relative_to(base)
        or base.is_relative_to(output)
        or any(
            Path(packet[k]).resolve().is_relative_to(output)
            for k in ASSET_PATHS
            if k != "checkpoint"
        )
        or not Path(packet["python_executable"]).is_file()
    ):
        raise ValueError("Native output must be disjoint from pinned assets")
    for key in (*ASSET_PINS, "registration_sha256", "source_sha256"):
        check_digest(packet[key])
    split = packet["session_split"]
    _fields(split, ("fit", "check"))
    for sessions in split.values():
        if type(sessions) is not list or not sessions or sessions != sorted(set(sessions)):
            raise ValueError("Sorted unique session metadata required")
        for day in sessions:
            if date.fromisoformat(day).isoformat() != day or task.role_for_session(day) != "train":
                raise ValueError("Training calendar only")
    union = sorted([*split["fit"], *split["check"]])
    cut = len(union) - len(union) // 4
    if (
        len(union) < 8
        or len(union) != len(set(union))
        or split != {"fit": union[:cut], "check": union[cut:]}
    ):
        raise ValueError("Original disjoint whole-session split required")
    if type(packet["selection"]) is not list or len(packet["selection"]) != STEPS:
        raise ValueError("Exactly 224 selected training examples required")
    seen, ranks = set(), set()
    for step, item in enumerate(packet["selection"]):
        _fields(item, ("spec", "example"))
        spec, row = item["spec"], item["example"]
        _fields(spec, SPEC_FIELDS)
        if row["role"] != "train" or row["source_session"] not in split["fit"]:
            raise ValueError("Inner check/nontrain row refused before prompt or label access")
        task.model_view(row, for_training=True)
        if (
            spec["joint_state"] != balance.STATES[step % len(balance.STATES)]
            or balance.state_of(row) != spec["joint_state"]
            or any(
                spec[k] != row[k]
                for k in ("case_id", "source_session", "input_sha256", "target_sha256")
            )
            or row["case_id"] in seen
            or type(spec["example_index"]) is not int
            or not 0 <= spec["example_index"] < task.MAX_CASES
            or spec["example_index"] in ranks
            or any(
                type(spec[k]) is not int or spec[k] <= 0
                for k in ("prompt_tokens", "completion_with_eos_tokens", "active_tokens")
            )
            or spec["prompt_tokens"] > trial.token_plan.MAX_PROMPT_TOKENS
            or spec["completion_with_eos_tokens"] > trial.token_plan.MAX_COMPLETION_TOKENS
            or spec["active_tokens"] != spec["prompt_tokens"] + spec["completion_with_eos_tokens"]
            or spec["active_tokens"] > trial.token_plan.MAX_SEQUENCE_TOKENS
        ):
            raise ValueError("Fixed unique curriculum identity/token bounds differ")
        check_digest(spec["record_sha256"])
        seen.add(row["case_id"])
        ranks.add(spec["example_index"])
    pins = _lock_pin(Path(packet["dependency_lock"]), packet["dependency_lock_sha256"])
    runtime = trial.metadata(Path(packet["runtime_manifest"]), packet["runtime_sha256"])
    _runtime_shape(runtime)
    if runtime["python_executable"] != packet["python_executable"] or any(
        runtime["packages"][k] != pins[k] for k in runtime["packages"]
    ):
        raise ValueError("Pinned native runtime/lock/interpreter differs")
    if verify_assets:
        assets = inspect_checkpoint(Path(packet["checkpoint"]), "Qwen/Qwen3-4B-Base")
        if (
            digest(assets) != packet["checkpoint_sha256"]
            or next(f["sha256"] for f in assets["files"] if f["name"] == "tokenizer.json")
            != packet["tokenizer_sha256"]
        ):
            raise ValueError("Fresh base/tokenizer asset pin differs")
        task.checked_file(Path(packet["tokenizer_json"]), packet["tokenizer_sha256"], 16 * 1024**2)
    return pins, runtime


def token_records(packet: dict, encode) -> list[dict]:
    records = []
    for item in packet["selection"]:
        info, record = encoded(item["example"], encode)
        if any(item["spec"][k] != v for k, v in info.items()):
            raise ValueError("Native tokenization or completion-only mask changed")
        records.append(record)
    return records


def journal_info(path: Path) -> dict:
    return balance.evaluation.file_info(path, MAX_JOURNAL_BYTES)


def binding(step: int, item: dict) -> dict:
    return {
        "step": step,
        "case_id": item["spec"]["case_id"],
        "record_sha256": item["spec"]["record_sha256"],
    }


def summarize(metrics: list[dict]) -> dict:
    return {
        "first_loss": metrics[0]["loss"],
        "last_loss": metrics[-1]["loss"],
        "minimum_loss": min(m["loss"] for m in metrics),
        "maximum_gradient_norm": max(m["gradient_norm"] for m in metrics),
    }


def validate_result(result: dict, packet: dict, directory: Path) -> list[dict]:
    _fields(
        result,
        (
            "kind",
            "request_sha256",
            "steps",
            "summary",
            "journal",
            "runtime",
            "resources",
            "trainable_parameters",
            "frozen_parameter_guards_passed",
            "reload",
            *FLAGS,
        ),
    )
    if (
        result["kind"] != KIND
        or result["request_sha256"] != digest(packet)
        or type(result["steps"]) is not int
        or result["steps"] != STEPS
        or result["frozen_parameter_guards_passed"] is not True
        or any(result[k] is not v for k, v in FLAGS.items())
        or type(result["trainable_parameters"]) is not int
        or not 1 <= result["trainable_parameters"] <= MAX_TRAINABLE_PARAMETERS
        or (directory / "failure.json").exists()
    ):
        raise ValueError("Complete quarantined native training evidence required")
    _, runtime = validate_packet(packet)
    if result["runtime"] != runtime:
        raise ValueError("Native runtime changed")
    journal = directory / "steps.jsonl"
    _fields(result["journal"], ("bytes", "sha256"))
    if journal_info(journal) != result["journal"]:
        raise ValueError("Durable journal pin differs")
    with journal.open("rb") as stream:
        raw = stream.read(MAX_JOURNAL_BYTES + 1)
    if (
        not raw.endswith(b"\n")
        or len(raw) > MAX_JOURNAL_BYTES
        or hashlib.sha256(raw).hexdigest() != result["journal"]["sha256"]
    ):
        raise ValueError("Complete bounded journal framing required")
    events = [strict_json(line) for line in raw.splitlines()]
    if (
        len(events) != 2 + 2 * STEPS + 2
        or events[:2]
        != [
            {"event": "native_initialization_started"},
            {"event": "native_initialization_completed"},
        ]
        or events[-2:] != [{"event": "save_reload_started"}, {"event": "save_reload_completed"}]
    ):
        raise ValueError("All native stages/updates required; no subset completion")
    metrics = []
    for step, item in enumerate(packet["selection"], 1):
        intent, completed = events[2 + (step - 1) * 2 : 4 + (step - 1) * 2]
        expected = binding(step, item)
        if intent != {"event": "step_intent", **expected}:
            raise ValueError("Durable update intent differs")
        _fields(completed, ("event", *expected, "loss", "gradient_norm"))
        metric = {k: completed[k] for k in ("loss", "gradient_norm")}
        finite_nonnegative(metric.values())
        if canonical(completed) != canonical({"event": "step_completed", **expected, **metric}):
            raise ValueError("Durable update completion differs")
        metrics.append(metric)
    if canonical(result["summary"]) != canonical(summarize(metrics)):
        raise ValueError("Native metric summary differs from all update receipts")
    reload = result["reload"]
    _fields(
        reload,
        (
            "adapter_manifest",
            "adapter_updated",
            "reload_state_equal",
            "probe_loss_before",
            "probe_loss_after",
            "probe_loss_absolute_tolerance",
            "base_checkpoint_unchanged",
        ),
    )
    finite_nonnegative([reload["probe_loss_before"], reload["probe_loss_after"]])
    if (
        any(
            reload[k] is not True
            for k in ("adapter_updated", "reload_state_equal", "base_checkpoint_unchanged")
        )
        or reload["probe_loss_absolute_tolerance"] != 1e-5
        or not math.isclose(
            reload["probe_loss_before"], reload["probe_loss_after"], rel_tol=0, abs_tol=1e-5
        )
        or adapter_manifest(directory / "adapter") != reload["adapter_manifest"]
    ):
        raise ValueError("Adapter persistence/fresh reload verification differs")
    r = result["resources"]
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
        raise ValueError("Native precision/resource guards differ")
    return metrics


def run(path: Path, pin: str, output: Path, *, enable_research_training=False) -> dict:
    if enable_research_training is not True:
        raise ValueError("Explicit bounded research-training opt-in required")
    value, request, rows = registration(path, pin)
    disjoint(output, request, value)
    packet = worker_packet(value, rows, pin, output)
    output.mkdir(exist_ok=False)
    started = time.monotonic()
    try:
        _write(output / "request.json", packet)
        result = strict_json(
            _exchange([packet["python_executable"], "-I", "-m", WORKER], packet, TIMEOUT_MS)
        )
        metrics = validate_result(result, packet, output)
        refreshed, _, final_rows = registration(path, pin)
        if refreshed != value or final_rows != rows:
            raise ValueError("Frozen input/selection/comparison drift during training")
        report = {
            "status": "completed_224_update_balanced_trial_not_validated",
            "registration_sha256": pin,
            "result": result,
            "elapsed_seconds": time.monotonic() - started,
            "selected_training_examples": STEPS,
            "selected_training_sessions": len(
                {i["spec"]["source_session"] for i in packet["selection"]}
            ),
            "metric_count": len(metrics),
            "full_training_epoch": False,
            "adapter_quarantined": True,
            "qwen_training_performed": True,
            "evaluation_performed": False,
            **FLAGS,
        }
        _write(output / "run.json", report)
        return report
    except BaseException as exc:
        if not (output / "run.json").exists():
            _write(
                output / "run.json",
                {
                    "status": "failed_or_interrupted_no_partial_success",
                    "error_type": type(exc).__name__,
                    "adapter_quarantined": True,
                    **FLAGS,
                },
            )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--balance-plan", type=Path)
    parser.add_argument("--balance-plan-sha256")
    parser.add_argument("--controls-directory", type=Path)
    parser.add_argument("--controls-report-sha256")
    parser.add_argument("--controls-models-sha256")
    parser.add_argument("--registration", type=Path)
    parser.add_argument("--registration-sha256")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enable-research-training", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        values = (
            args.balance_plan,
            args.balance_plan_sha256,
            args.controls_directory,
            args.controls_report_sha256,
            args.controls_models_sha256,
        )
        if any(v is None for v in values):
            parser.error("Pinned balance plan and frozen CPU controls required")
        result = freeze(*values, args.output)
        print(
            canonical(
                {
                    "kind": result["kind"],
                    "training_examples": len(result["selection"]),
                    "comparison_cases": len(result["comparison"]),
                }
            )
        )
    else:
        if args.registration is None or args.registration_sha256 is None:
            parser.error("Pinned new registration required")
        result = run(
            args.registration,
            args.registration_sha256,
            args.output,
            enable_research_training=args.enable_research_training,
        )
        print(
            canonical(
                {
                    "status": result["status"],
                    "training_examples": result["selected_training_examples"],
                    "evaluation_performed": False,
                }
            )
        )


if __name__ == "__main__":
    main()
