"""Explicit, offline 20-update 6E forecast LoRA trial; never promotion or trading."""

from __future__ import annotations

import argparse
import hashlib
import math
import time
from collections import Counter
from datetime import date
from pathlib import Path

from ai_trader.models.local_checkpoint import (
    canonical,
    check_digest,
    digest,
    inspect_checkpoint,
    strict_json,
)
from ai_trader.models.local_reviewer import _exchange
from ai_trader.training import advisory_training_plan as token_plan
from ai_trader.training import six_e_forecast as task
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import (
    _absolute,
    _lock_pin,
    _runtime_shape,
    _write,
    implementation_sha256,
)
from ai_trader.training.lora_backend import MAX_TRAINABLE_PARAMETERS, adapter_manifest
from ai_trader.training.qwen_gpu_smoke import finite_nonnegative

KIND = "six_e_forecast_bounded_lora_trial_v1"
RESERVATION_KIND = "six_e_forecast_reserved_calendar_v1"
WORKER = "ai_trader.training._six_e_lora_worker"
STEPS, TIMEOUT_MS = 20, 600_000
MAX_REQUEST_BYTES, MAX_EVENTS_BYTES = 32 * 1024, 128 * 1024
CALENDAR = (
    ("validation_reserved", "2026-01-01", "2026-04-01"),
    ("test_reserved", "2026-04-01", "2026-07-01"),
    ("lockbox_reserved", "2026-07-01", "2026-09-26"),
)
NO_AUTHORITY = {
    "held_out_evaluated": False,
    "independent_performance_proven": False,
    "promotion_allowed": False,
    "execution_allowed": False,
    "adapter_approved_for_inference": False,
    "automatic_retry": False,
}
PATH_KEYS = (
    "python_executable",
    "checkpoint",
    "dependency_lock",
    "runtime_manifest",
    "dataset",
    "token_preflight",
    "tokenizer_json",
    "reservation",
    "output_dir",
)
PIN_KEYS = (
    "checkpoint_sha256",
    "dependency_lock_sha256",
    "runtime_sha256",
    "dataset_sha256",
    "token_preflight_sha256",
    "tokenizer_sha256",
    "reservation_sha256",
)
BASE_FIELDS = (*PATH_KEYS, *PIN_KEYS, "enable_research_training", "profile", "source_sha256")
SELECTION_FIELDS = (
    "example_index",
    "case_id",
    "source_session",
    "input_sha256",
    "target_sha256",
    "record_sha256",
    "active_tokens",
)


def profile() -> dict:
    return {
        **token_plan.proposed_recipe(),
        "purpose": KIND,
        "task": task.TASK,
        "limits_enforced_by_training_worker": True,
        "market_training_authorized": True,
        "selection": "20 evenly spaced rank indices across supervised train.jsonl; "
        "indices fixed from count before labels, no repetition, reweighting or sign selection",
        "fit_scope": "Tiny engineering trial, NOT a full epoch or a validated trading model",
        "cublas_workspace_config": ":4096:8",
        "eos_token_id": 151643,
        "pad_token_id": 151643,
        "evaluation": "None; save/reload probe uses a training record, not a holdout score",
    }


def source_sha256() -> str:
    root = Path(__file__).parent
    names = (
        "six_e_lora_trial.py",
        "_six_e_lora_worker.py",
        "six_e_forecast.py",
        "qwen_gpu_smoke.py",
        "_qwen_gpu_smoke_worker.py",
    )
    return digest(
        {
            "backend_transport_and_masks": implementation_sha256(),
            **{name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names},
        }
    )


def metadata(path: Path, pin: str) -> dict:
    task.checked_file(path, pin, task.MAX_METADATA_BYTES)
    value = strict_json(path.read_bytes())
    if type(value) is not dict:
        raise ValueError("Pinned metadata object required")
    return value


def partition(session: str) -> str:
    if type(session) is not str or date.fromisoformat(session).isoformat() != session:
        raise ValueError("Canonical reserved source session required")
    matches = [name for name, start, end in CALENDAR if start <= session < end]
    if len(matches) != 1:
        raise ValueError("Reserved calendar cannot overlap development or be expanded")
    return matches[0]


def validate_reservation(value: dict, dataset_pin: str, manifest_pin: str) -> None:
    _fields(
        value,
        (
            "kind",
            "task",
            "status",
            "dataset_completion_sha256",
            "source_manifest_sha256",
            "source_census_registration_sha256",
            "calendar",
            "sessions",
            "counts",
            "outcomes_opened",
            "evaluation_authorized",
            "external_nonexposure_proven",
            "training_authorized",
        ),
    )
    if (
        value["kind"] != RESERVATION_KIND
        or value["task"] != task.TASK
        or value["status"] != ("reserved_metadata_only_not_evaluated")
        or value["dataset_completion_sha256"] != dataset_pin
        or value["source_manifest_sha256"] != manifest_pin
        or (value["calendar"] != [list(item) for item in CALENDAR])
        or any(
            value[k] is not False
            for k in (
                "outcomes_opened",
                "evaluation_authorized",
                "external_nonexposure_proven",
                "training_authorized",
            )
        )
    ):
        raise ValueError("Reservation binding, calendar or authority differs")
    check_digest(value["source_census_registration_sha256"])
    sessions = value["sessions"]
    if type(sessions) is not list or not 3 <= len(sessions) <= 1000:
        raise ValueError("Complete bounded reserved metadata required")
    previous, counts = None, Counter()
    for item in sessions:
        _fields(
            item,
            (
                "source_session",
                "partition",
                "member_sha256",
                "member_bytes",
                "prior_access",
                "condition",
            ),
        )
        day = item["source_session"]
        if (
            item["partition"] != partition(day)
            or (previous is not None and day <= previous)
            or (item["prior_access"] != "no_replay_documented")
            or type(item["member_bytes"]) is not int
            or item["member_bytes"] <= 0
            or (type(item["condition"]) is not str or not 1 <= len(item["condition"]) <= 128)
        ):
            raise ValueError("Reserved membership, ordering or exposure record differs")
        check_digest(item["member_sha256"])
        previous = day
        counts[item["partition"]] += 1
    if dict(counts) != value["counts"] or any(not counts[name] for name, _, _ in CALENDAR):
        raise ValueError("All reserved calendar groups required")


def reserve(
    root: Path,
    dataset: Path,
    dataset_pin: str,
    registration: Path,
    registration_pin: str,
    output: Path,
) -> dict:
    """Lazy metadata-only producer, never imported by the GPU worker or opening raw members."""
    from ai_trader.training import prepare_6e_qwen_data as builder

    frozen, manifest = builder.registration(root, registration, registration_pin)
    receipt = metadata(dataset / "completion.json", dataset_pin)
    if (
        receipt["status"] != "prepared_6e_qwen_development_only"
        or receipt["protocol"] != task.protocol()
        or (receipt["manifest_sha256"] != frozen["manifest"]["sha256"])
        or receipt["registration_sha256"] != registration_pin
        or (dataset / "failure.json").exists()
    ):
        raise ValueError("Verified dataset lineage required before reservation")
    census = builder.data.census.registration(
        root, root / builder.data.diagnostic.REGISTRATION, builder.data.diagnostic.REGISTRATION_PIN
    )
    declared = {e["utc_date"]: e for e in manifest["ledger"]}
    sessions = []
    for entry in census["inventory"]["ledger"]:
        if entry["partition"] == "development":
            continue
        day = entry["utc_date"]
        original = declared[day]
        if (
            entry["planned_action"] != "reserved_metadata_only"
            or original["artifacts"] is not None
            or (
                original["role"] != entry["partition"]
                or original["disposition"] != "reserved_metadata_only"
            )
        ):
            raise ValueError("Original reserved scope or disposition differs")
        sessions.append(
            {
                "source_session": day,
                "partition": entry["partition"],
                "member_sha256": entry["sha256"],
                "member_bytes": entry["bytes"],
                "prior_access": entry["prior_access"],
                "condition": entry["condition"],
            }
        )
    if len(sessions) != manifest["coverage"]["dispositions"]["reserved_metadata_only"]:
        raise ValueError("No partial reserved calendar permitted")
    value = {
        "kind": RESERVATION_KIND,
        "task": task.TASK,
        "status": "reserved_metadata_only_not_evaluated",
        "dataset_completion_sha256": dataset_pin,
        "source_manifest_sha256": frozen["manifest"]["sha256"],
        "source_census_registration_sha256": builder.data.diagnostic.REGISTRATION_PIN,
        "calendar": [list(item) for item in CALENDAR],
        "sessions": sessions,
        "counts": dict(Counter(s["partition"] for s in sessions)),
        "outcomes_opened": False,
        "evaluation_authorized": False,
        "external_nonexposure_proven": False,
        "training_authorized": False,
    }
    validate_reservation(value, dataset_pin, frozen["manifest"]["sha256"])
    _write(output, value)
    return value


def indices(count: int) -> list[int]:
    if type(count) is not int or not STEPS <= count <= task.MAX_CASES:
        raise ValueError("At least 20 bounded training examples required")
    return [step * (count - 1) // (STEPS - 1) for step in range(STEPS)]


def selected_examples(request: dict, receipt: dict) -> list[tuple[int, dict]]:
    """Selection indices are computed before the first label is read. Train file only."""
    item = receipt["files"]["train.jsonl"]
    selected = set(indices(item["count"]))
    path = Path(request["dataset"]) / "train.jsonl"
    if path.is_symlink() or not path.is_file():
        raise ValueError("Regular training file required")
    checksum, size, count, previous, rows = hashlib.sha256(), 0, 0, None, []
    with path.open("rb") as handle:
        while raw := handle.readline(task.MAX_LINE + 1):
            checksum.update(raw)
            size += len(raw)
            if (
                len(raw) > task.MAX_LINE
                or not raw.endswith(b"\n")
                or size > task.MAX_DATA_BYTES
                or count >= item["count"]
            ):
                raise ValueError("Training file byte, count or framing bound exceeded")
            row = strict_json(raw)
            task.model_view(row, for_training=True)
            if previous is not None and row["decision_ts_ns"] <= previous:
                raise ValueError("Training cases must be unique and chronological")
            previous = row["decision_ts_ns"]
            if count in selected:
                rows.append((count, row))
            count += 1
    if (
        count != item["count"]
        or size != item["bytes"]
        or checksum.hexdigest() != item["sha256"]
        or len(rows) != STEPS
    ):
        raise ValueError("Training bytes/count differ; no partial curriculum")
    return rows


def validate_inputs(request: dict, *, verify_assets=False) -> tuple[dict, dict, dict]:
    if request["enable_research_training"] is not True:
        raise ValueError("Explicit research-training opt-in required")
    if (
        canonical(request["profile"]) != canonical(profile())
        or request["source_sha256"] != source_sha256()
    ):
        raise ValueError("Fixed trial profile or source changed")
    for name in PATH_KEYS:
        _absolute(request[name])
    for name in PIN_KEYS:
        check_digest(request[name])
    base, dataset, output = (Path(request[k]) for k in ("checkpoint", "dataset", "output_dir"))
    if (
        not Path(request["python_executable"]).is_file()
        or Path(request["python_executable"]).is_symlink()
        or (base.is_symlink() or not base.is_dir() or dataset.is_symlink() or not dataset.is_dir())
        or output.is_symlink()
        or not output.parent.is_dir()
        or any(
            output.resolve().is_relative_to(p.resolve())
            or p.resolve().is_relative_to(output.resolve())
            for p in (base, dataset)
        )
    ):
        raise ValueError("Explicit regular local inputs and disjoint new output required")
    pins = _lock_pin(Path(request["dependency_lock"]), request["dependency_lock_sha256"])
    runtime = metadata(Path(request["runtime_manifest"]), request["runtime_sha256"])
    _runtime_shape(runtime)
    if runtime["python_executable"] != request["python_executable"] or any(
        runtime["packages"][name] != pins[name] for name in runtime["packages"]
    ):
        raise ValueError("Training runtime differs from pinned lock/interpreter")
    receipt = metadata(dataset / "completion.json", request["dataset_sha256"])
    if (
        receipt["status"] != "prepared_6e_qwen_development_only"
        or receipt["protocol"] != task.protocol()
        or (dataset / "failure.json").exists()
        or receipt["implementation_sha256"]["six_e_forecast.py"]
        != hashlib.sha256(Path(task.__file__).read_bytes()).hexdigest()
        or receipt["implementation_sha256"]["advisory_training_plan.py"]
        != hashlib.sha256(Path(token_plan.__file__).read_bytes()).hexdigest()
        or any(
            receipt[k] is not False
            for k in (
                "training_authorized",
                "qwen_trained",
                "independent_holdout",
                "reserved_outcomes_opened",
                "trading_enabled",
                "promotion_enabled",
                "automatic_retry",
            )
        )
    ):
        raise ValueError("Dataset lineage or preparation-only authority changed")
    if set(receipt["files"]) != {
        *(f"{role}.jsonl" for role in task.ROLES),
        "unavailable.jsonl",
    } or (receipt["files"]["train.jsonl"]["count"] != receipt["by_role"]["train"]["supervised"]):
        raise ValueError("Training artifact allowlist/accounting differs")
    token = metadata(Path(request["token_preflight"]), request["token_preflight_sha256"])
    if (
        token["status"] != "passed_all_supervised_token_preflight_not_training_approval"
        or (
            token["dataset_completion_sha256"] != request["dataset_sha256"]
            or token["task"] != task.TASK
            or token["tokenizer_sha256"] != request["tokenizer_sha256"]
            or token["tokenizer_version"] != runtime["packages"]["tokenizers"]
            or token["eos_token_id"] != 151643
            or token["pad_token_id"] != 151643
            or token["by_role"]["train"]["examples"] != receipt["by_role"]["train"]["supervised"]
        )
        or any(
            token[k] is not value
            for k, value in {
                "prompt_loss_masked": True,
                "completion_and_eos_supervised": True,
                "truncation": False,
                "training_authorized": False,
                "model_weights_loaded": False,
                "qwen_trained": False,
                "independent_holdout": False,
                "trading_enabled": False,
                "promotion_enabled": False,
            }.items()
        )
    ):
        raise ValueError("Verified completion-only tokenizer preflight required")
    task.checked_file(Path(request["tokenizer_json"]), request["tokenizer_sha256"], 16 * 1024**2)
    reservation = metadata(Path(request["reservation"]), request["reservation_sha256"])
    validate_reservation(reservation, request["dataset_sha256"], receipt["manifest_sha256"])
    if verify_assets:
        assets = inspect_checkpoint(base, "Qwen/Qwen3-4B-Base")
        tokenizer = next(f for f in assets["files"] if f["name"] == "tokenizer.json")
        if (
            digest(assets) != request["checkpoint_sha256"]
            or tokenizer["sha256"] != request["tokenizer_sha256"]
        ):
            raise ValueError("Checkpoint or base tokenizer pin mismatch")
    return receipt, pins, runtime


def encode_selection(
    request: dict, rows: list[tuple[int, dict]], encode
) -> tuple[list[dict], list[dict]]:
    specs, records = [], []
    for index, row in rows:
        text, answer = task.model_view(row, for_training=True)
        record = token_plan.completion_only_record(
            encode(text), encode(answer), eos_token_id=151643, pad_token_id=151643
        )
        specs.append(
            {
                "example_index": index,
                **{
                    k: row[k]
                    for k in (
                        "case_id",
                        "source_session",
                        "input_sha256",
                        "target_sha256",
                    )
                },
                "record_sha256": digest(record),
                "active_tokens": sum(record["attention_mask"]),
            }
        )
        records.append(record)
    return specs, records


def validate_request(
    request: dict, *, verify_assets=False
) -> tuple[list[tuple[int, dict]], dict, dict]:
    _fields(request, (*BASE_FIELDS, "selection"))
    receipt, pins, runtime = validate_inputs(request, verify_assets=verify_assets)
    rows = selected_examples(request, receipt)
    if type(request["selection"]) is not list or len(request["selection"]) != STEPS:
        raise ValueError("Exactly 20 fixed training records required")
    for spec, (index, row) in zip(request["selection"], rows, strict=True):
        _fields(spec, SELECTION_FIELDS)
        if (
            type(spec["example_index"]) is not int
            or spec["example_index"] != index
            or any(
                spec[k] != row[k]
                for k in ("case_id", "source_session", "input_sha256", "target_sha256")
            )
            or type(spec["active_tokens"]) is not int
            or not 1 <= spec["active_tokens"] <= token_plan.MAX_SEQUENCE_TOKENS
        ):
            raise ValueError("Selected record identity/order differs")
        check_digest(spec["record_sha256"])
    if len(canonical(request).encode()) > MAX_REQUEST_BYTES:
        raise ValueError("Trial request byte ceiling exceeded")
    return rows, pins, runtime


def validate_result(result: dict, request: dict, directory: Path) -> None:
    _fields(
        result,
        (
            "kind",
            "request_sha256",
            "steps",
            "metrics",
            "runtime",
            "resources",
            "trainable_parameters",
            "frozen_parameter_guards_passed",
            "reload",
            *NO_AUTHORITY,
        ),
    )
    if (
        result["kind"] != KIND
        or result["request_sha256"] != digest(request)
        or (type(result["steps"]) is not int or result["steps"] != STEPS)
        or any(result[k] is not v for k, v in NO_AUTHORITY.items())
        or result["frozen_parameter_guards_passed"] is not True
        or (
            type(result["trainable_parameters"]) is not int
            or not 1 <= result["trainable_parameters"] <= MAX_TRAINABLE_PARAMETERS
        )
    ):
        raise ValueError("Trial completion/authority/adapter guards differ")
    metrics = result["metrics"]
    if type(metrics) is not list or len(metrics) != STEPS:
        raise ValueError("Exactly 20 native metrics required")
    expected = [
        {"event": "native_initialization_started"},
        {"event": "native_initialization_completed"},
    ]
    for step, (spec, metric) in enumerate(zip(request["selection"], metrics, strict=True), 1):
        _fields(metric, ("loss", "gradient_norm"))
        finite_nonnegative(metric.values())
        event = {"step": step, "case_id": spec["case_id"], "record_sha256": spec["record_sha256"]}
        expected.extend(
            [{"event": "step_intent", **event}, {"event": "step_completed", **event, **metric}]
        )
    expected.extend([{"event": "save_reload_started"}, {"event": "save_reload_completed"}])
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
    if any(
        reload[k] is not True
        for k in ("adapter_updated", "reload_state_equal", "base_checkpoint_unchanged")
    ) or (
        reload["probe_loss_absolute_tolerance"] != 1e-5
        or not math.isclose(
            reload["probe_loss_before"], reload["probe_loss_after"], rel_tol=0, abs_tol=1e-5
        )
        or adapter_manifest(directory / "adapter") != reload["adapter_manifest"]
    ):
        raise ValueError("Adapter persistence/reload verification failed")
    evidence = result["resources"]
    _fields(
        evidence,
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
        type(evidence["device"]) is not str
        or not 1 <= len(evidence["device"]) <= 128
        or any(
            type(evidence[k]) is not int or evidence[k] <= 0
            for k in ("total_bytes", "peak_allocated_bytes", "peak_reserved_bytes")
        )
        or not evidence["peak_allocated_bytes"]
        <= evidence["peak_reserved_bytes"]
        <= evidence["total_bytes"]
        or (
            evidence["cuda_bf16"] is not True
            or evidence["deterministic_algorithms"] is not True
            or evidence["tf32_enabled"] is not False
        )
    ):
        raise ValueError("Native GPU resource evidence differs")
    _, _, runtime = validate_request(request, verify_assets=True)
    if result["runtime"] != runtime:
        raise ValueError("Native runtime drift")
    journal = directory / "steps.jsonl"
    if journal.is_symlink() or not journal.is_file() or journal.stat().st_size > MAX_EVENTS_BYTES:
        raise ValueError("Regular bounded durable journal required")
    with journal.open("rb") as stream:
        raw = stream.read(MAX_EVENTS_BYTES + 1)
    if (
        len(raw) > MAX_EVENTS_BYTES
        or not raw.endswith(b"\n")
        or [strict_json(line) for line in raw.splitlines()] != expected
    ):
        raise ValueError("Durable optimizer journal differs from the frozen selection")


def run(base_request: dict) -> dict:
    _fields(base_request, BASE_FIELDS)
    receipt, _, _ = validate_inputs(base_request, verify_assets=True)
    rows = selected_examples(base_request, receipt)
    encode = token_plan.load_tokenizer(
        Path(base_request["tokenizer_json"]), base_request["tokenizer_sha256"]
    )
    specs, _ = encode_selection(base_request, rows, encode)
    request = {**base_request, "selection": specs}
    validate_request(request, verify_assets=True)
    directory = Path(request["output_dir"])
    directory.mkdir(exist_ok=False)
    started = time.monotonic()
    try:
        _write(directory / "request.json", request)
        result = strict_json(
            _exchange([request["python_executable"], "-I", "-m", WORKER], request, TIMEOUT_MS)
        )
        validate_result(result, request, directory)
        if (directory / "failure.json").exists():
            raise ValueError("Failure evidence prohibits trial completion")
        report = {
            "status": "completed_20_update_market_trial_not_validated",
            "result": result,
            "elapsed_seconds": time.monotonic() - started,
            "selected_training_examples": STEPS,
            "selected_training_sessions": len({s["source_session"] for s in specs}),
            "full_training_epoch": False,
            "adapter_quarantined": True,
            **NO_AUTHORITY,
        }
        _write(directory / "run.json", report)
        return report
    except BaseException as exc:
        if not (directory / "run.json").exists():
            _write(
                directory / "run.json",
                {
                    "status": "failed_or_interrupted",
                    "completed_steps": None,
                    "error_type": type(exc).__name__,
                    "adapter_quarantined": True,
                    **NO_AUTHORITY,
                },
            )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("reserve", "run"))
    for key in PATH_KEYS:
        parser.add_argument("--" + key.replace("_", "-"), type=Path)
    for key in PIN_KEYS:
        parser.add_argument("--" + key.replace("_", "-"))
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--dataset-registration", type=Path)
    parser.add_argument("--dataset-registration-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--enable-research-training", action="store_true")
    args = parser.parse_args()
    if args.action == "reserve":
        if any(
            v is None
            for v in (
                args.dataset,
                args.dataset_sha256,
                args.dataset_registration,
                args.dataset_registration_sha256,
                args.output,
            )
        ):
            parser.error(
                "Pinned dataset, lineage registration and exclusive reservation output required"
            )
        result = reserve(
            args.project_root,
            args.dataset,
            args.dataset_sha256,
            args.dataset_registration,
            args.dataset_registration_sha256,
            args.output,
        )
        print(canonical({"status": result["status"], "counts": result["counts"]}))
    else:
        if any(getattr(args, k) is None for k in (*PATH_KEYS, *PIN_KEYS)):
            parser.error("Every local input path and raw/content pin is required")
        request = {
            **{k: str(getattr(args, k).resolve()) for k in PATH_KEYS},
            **{k: getattr(args, k) for k in PIN_KEYS},
            "enable_research_training": args.enable_research_training,
            "profile": profile(),
            "source_sha256": source_sha256(),
        }
        result = run(request)
        print(
            canonical(
                {
                    "status": result["status"],
                    "steps": result["result"]["steps"],
                    "resources": result["result"]["resources"],
                }
            )
        )


if __name__ == "__main__":
    main()
