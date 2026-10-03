"""Offline context-v2 natural-prior LoRA registration/runner; no evaluation or trades."""

from __future__ import annotations

import argparse
import hashlib
import math
import time
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path

from ai_trader.models.local_checkpoint import (
    canonical,
    check_digest,
    digest,
    inspect_checkpoint,
    strict_json,
)
from ai_trader.models.local_reviewer import _exchange
from ai_trader.training import six_e_balanced_lora as legacy
from ai_trader.training import six_e_context_forecast as task
from ai_trader.training import six_e_context_tokens as tokens
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import _absolute, _lock_pin, _runtime_shape, _write
from ai_trader.training.lora_backend import MAX_TRAINABLE_PARAMETERS, adapter_manifest
from ai_trader.training.qwen_gpu_smoke import finite_nonnegative

KIND = "six_e_context_v2_natural_192_update_lora"
WORKER = "ai_trader.training._six_e_context_worker"
STEPS, TIMEOUT_MS = 192, 1_800_000
MAX_REQUEST_BYTES, MAX_JOURNAL_BYTES = 1024**2 - 1, 256 * 1024
FLAGS = dict(legacy.FLAGS)
STATES, ASSET_PATHS, ASSET_PINS = legacy.balance.STATES, legacy.ASSET_PATHS, legacy.ASSET_PINS
SPEC_FIELDS = (*legacy.SPEC_FIELDS, "example_sha256")
PACKET_FIELDS = (
    "kind",
    "profile",
    "source_sha256",
    "registration_sha256",
    "dataset_completion_sha256",
    "token_preflight_sha256",
    "enable_research_training",
    *ASSET_PATHS,
    *ASSET_PINS,
    "output_dir",
    "session_split",
    "fit_joint_counts",
    "selection",
)
journal_info, binding, summarize = legacy.journal_info, legacy.binding, legacy.summarize


def profile() -> dict:
    return {
        **tokens.token_plan.proposed_recipe(),
        "purpose": KIND,
        "task": task.TASK,
        "schema_sha256": task.schema_sha256(),
        "max_optimizer_steps": STEPS,
        "max_wall_time_seconds": TIMEOUT_MS // 1000,
        "limits_enforced_by_training_worker": True,
        "cublas_workspace_config": ":4096:8",
        "eos_token_id": 151643,
        "pad_token_id": 151643,
        "initialization": "Fresh pinned base and fresh q/v LoRA; no adapter resume",
        "selection": "Natural fit joint-state largest-remainder quotas; session spread and even "
        "within-session ranks; 192 unique cases, no minority minimum or reweighting",
        "order": "Sort by SHA256 of seed 42 and case_id, independent of state and check labels",
        "evaluation": "None during training; save/reload probe on first selected fit case only",
    }


def protocol() -> dict:
    return {
        "kind": KIND,
        "profile": profile(),
        "registration_authorizes_execution": False,
        "packet": "Selected train/inner-fit examples and pinned asset/split/prior metadata only; "
        "no dataset paths, dense observations, check examples, CPU models or old adapters",
        "comparison": {
            "scope": "ALL original inner-check examples and sessions, no subset",
            "exposure": "Already-exposed within-training temporal development; NOT independent",
            "modes": ["base", "adapter"],
            "controls": ["no_opportunity", "inner_fit_joint_prior", "natural_context_joint_linear"],
            "prior": "Laplace-smoothed all-fit joint counts; fixed joint-state argmax tie order",
            "linear": {
                "columns": 79,
                "epochs": 200,
                "learning_rate": 0.05,
                "l2": 0.01,
                "standardized_clip": 10,
                "normalization": "All inner-fit only; constant scale one",
                "initialization": "Zero weights and Laplace-smoothed natural fit log priors",
                "weights": "None; no opportunity/wrong-side penalty or class weighting",
                "vector": "43 current then three [count/window,span,ten means] rows",
            },
            "decoding": legacy.balance.evaluation.protocol()["inference"],
            "metrics": "Strict valid/EOS coverage; pooled AND every session per-cost confusion, "
            "wrong-side/no-opportunity calls, directional precision/recall, missed opportunities, "
            "activity, class support. Invalid outputs incorrect, never recoded abstention.",
            "selection": "No outcome-based subset, threshold tuning, early stopping "
            "or winner search",
            "economics": "Quote-opportunity labels, not CFD fills, PnL or promotion",
            "evaluation_implemented": False,
            "run_now": False,
        },
        "bounds": {
            "updates": STEPS,
            "worker_seconds": TIMEOUT_MS // 1000,
            "request_bytes": MAX_REQUEST_BYTES,
            "registration_seconds": 600,
        },
        **FLAGS,
    }


def source_sha256() -> str:
    return digest(
        {
            "immutable_backend_and_prior_tools": legacy.source_sha256(),
            "immutable_context_token_pipeline": tokens.source_sha256(),
            **{
                name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ("six_e_context_lora.py", "_six_e_context_worker.py")
            },
        }
    )


def quotas(counts: dict) -> dict:
    _fields(counts, STATES)
    if any(type(v) is not int or v < 0 for v in counts.values()):
        raise ValueError("Nonnegative integer fit counts required")
    total = sum(counts.values())
    if not STEPS <= total <= task.snapshot.MAX_CASES:
        raise ValueError("At least 192 bounded unique inner-fit cases required")
    result = {state: STEPS * counts[state] // total for state in STATES}
    order = sorted(
        STATES, key=lambda state: (-(STEPS * counts[state] % total), STATES.index(state))
    )
    for state in order[: STEPS - sum(result.values())]:
        result[state] += 1
    return result


def order_key(row: dict) -> str:
    return digest({"seed": 42, "case_id": row["case_id"]})


def curriculum(rows: list[dict], split: dict) -> tuple[list[dict], dict]:
    pools = {state: defaultdict(list) for state in STATES}
    for index, row in enumerate(rows):
        # Inner-fit membership is checked BEFORE targets, state or prompt.
        if (
            row["role"] != "train"
            or row["inner_partition"] != "fit"
            or row["source_session"] not in split["fit"]
        ):
            raise ValueError("Only train/inner-fit pool may define the curriculum")
        task.model_view(row, for_training=True)
        pools[legacy.balance.state_of(row)][row["source_session"]].append(index)
    counts = {state: sum(map(len, groups.values())) for state, groups in pools.items()}
    allocation, selected = quotas(counts), []
    for state, groups in pools.items():
        quota = allocation[state]
        if not quota:
            continue
        sessions = sorted(groups)
        per_day = dict.fromkeys(sessions, 0)
        if len(sessions) >= quota:
            for index in legacy.balance.even_indices(len(sessions), quota):
                per_day[sessions[index]] = 1
        else:
            remaining = quota
            while remaining:
                for day in sessions:
                    if remaining and per_day[day] < len(groups[day]):
                        per_day[day] += 1
                        remaining -= 1
        for day, number in per_day.items():
            if number:
                selected.extend(
                    groups[day][i] for i in legacy.balance.even_indices(len(groups[day]), number)
                )
    selected.sort(key=lambda i: order_key(rows[i]))
    if len(selected) != STEPS or len({rows[i]["case_id"] for i in selected}) != STEPS:
        raise ValueError("Complete unique natural-prior curriculum required")
    return [
        {
            "example_index": i,
            "joint_state": legacy.balance.state_of(rows[i]),
            **{
                k: rows[i][k]
                for k in ("case_id", "source_session", "input_sha256", "target_sha256")
            },
            "example_sha256": digest(rows[i]),
        }
        for i in selected
    ], counts


def encoded(example: dict, encode) -> tuple[dict, dict]:
    prompt, answer = task.model_view(example, for_training=True)
    prompt_ids, answer_ids = encode(prompt), encode(answer)
    if any(type(t) is not int or not 0 <= t < 151936 for t in (*prompt_ids, *answer_ids)):
        raise ValueError("Pinned model vocabulary required")
    record = tokens.token_plan.completion_only_record(
        prompt_ids, answer_ids, eos_token_id=151643, pad_token_id=151643
    )
    return {
        "record_sha256": digest(record),
        "prompt_tokens": len(prompt_ids),
        "completion_with_eos_tokens": len(answer_ids) + 1,
        "active_tokens": sum(record["attention_mask"]),
    }, record


def validate_assets(packet: dict, *, verify_assets=True) -> tuple[dict, dict]:
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
        or Path(packet["tokenizer_json"]).resolve() != base / "tokenizer.json"
    ):
        raise ValueError("Disjoint output and exact base tokenizer required")
    for key in ASSET_PINS:
        check_digest(packet[key])
    pins = _lock_pin(Path(packet["dependency_lock"]), packet["dependency_lock_sha256"])
    runtime = tokens.metadata(Path(packet["runtime_manifest"]), packet["runtime_sha256"])
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
        task.snapshot.checked_file(
            Path(packet["tokenizer_json"]), packet["tokenizer_sha256"], 16 * 1024**2
        )
    return pins, runtime


def validate_split(split: dict) -> None:
    _fields(split, task.PARTITIONS)
    for sessions in split.values():
        if type(sessions) is not list or not sessions or sessions != sorted(set(sessions)):
            raise ValueError("Sorted unique session metadata required")
        if any(task.snapshot.role_for_session(day) != "train" for day in sessions):
            raise ValueError("Training calendar only")
    union = sorted([*split["fit"], *split["check"]])
    cut = len(union) - len(union) // 4
    if (
        len(union) < 8
        or len(union) != len(set(union))
        or split != {"fit": union[:cut], "check": union[cut:]}
    ):
        raise ValueError("Original disjoint chronological whole-session split required")


def validate_packet(packet: dict, *, verify_assets=True) -> tuple[dict, dict]:
    _fields(packet, PACKET_FIELDS)
    if (
        packet["kind"] != KIND
        or packet["profile"] != profile()
        or packet["source_sha256"] != source_sha256()
        or packet["enable_research_training"] is not True
        or len(canonical(packet).encode()) > MAX_REQUEST_BYTES
    ):
        raise ValueError("Bounded fixed source/profile and explicit training opt-in required")
    for key in (
        "source_sha256",
        "registration_sha256",
        "dataset_completion_sha256",
        "token_preflight_sha256",
    ):
        check_digest(packet[key])
    split = packet["session_split"]
    validate_split(split)
    expected = quotas(packet["fit_joint_counts"])
    if type(packet["selection"]) is not list or len(packet["selection"]) != STEPS:
        raise ValueError("Exactly 192 unique selected fit examples required")
    seen, indices, counts, order = set(), set(), Counter(), []
    for item in packet["selection"]:
        _fields(item, ("spec", "example"))
        spec, row = item["spec"], item["example"]
        _fields(spec, SPEC_FIELDS)
        if (
            row["role"] != "train"
            or row["inner_partition"] != "fit"
            or row["source_session"] not in split["fit"]
        ):
            raise ValueError("Inner check/nontrain refused before prompt or target")
        task.model_view(row, for_training=True)
        if (
            legacy.balance.state_of(row) != spec["joint_state"]
            or digest(row) != spec["example_sha256"]
            or any(
                spec[k] != row[k]
                for k in ("case_id", "source_session", "input_sha256", "target_sha256")
            )
            or row["case_id"] in seen
            or type(spec["example_index"]) is not int
            or not 0 <= spec["example_index"] < sum(packet["fit_joint_counts"].values())
            or spec["example_index"] in indices
            or any(
                type(spec[k]) is not int or spec[k] <= 0
                for k in ("prompt_tokens", "completion_with_eos_tokens", "active_tokens")
            )
            or spec["prompt_tokens"] > tokens.token_plan.MAX_PROMPT_TOKENS
            or spec["completion_with_eos_tokens"] > tokens.token_plan.MAX_COMPLETION_TOKENS
            or spec["active_tokens"] != spec["prompt_tokens"] + spec["completion_with_eos_tokens"]
            or spec["active_tokens"] > tokens.token_plan.MAX_SEQUENCE_TOKENS
        ):
            raise ValueError("Fixed curriculum example/token binding differs")
        check_digest(spec["record_sha256"])
        check_digest(spec["example_sha256"])
        seen.add(row["case_id"])
        indices.add(spec["example_index"])
        counts[spec["joint_state"]] += 1
        order.append(order_key(row))
    if {state: counts[state] for state in STATES} != expected or order != sorted(order):
        raise ValueError("Natural-prior quotas or fixed hash order differ")
    return validate_assets(packet, verify_assets=verify_assets)


def token_records(packet: dict, encode) -> list[dict]:
    records = []
    for item in packet["selection"]:
        info, record = encoded(item["example"], encode)
        if any(item["spec"][k] != v for k, v in info.items()):
            raise ValueError("Native tokenization or completion-only mask changed")
        records.append(record)
    return records


def verify_preflight(path: Path, pin: str, receipt: dict, receipt_pin: str, assets: dict) -> None:
    actual = tokens.metadata(path, pin)
    _fields(actual["by_partition"], task.PARTITIONS)
    expected = {
        "status": "passed_context_v2_token_preflight_not_training_approval",
        "task": task.TASK,
        "dataset_completion_sha256": receipt_pin,
        "dataset_source_sha256": receipt["source_sha256"],
        "token_pipeline_sha256": tokens.source_sha256(),
        "schema_sha256": task.schema_sha256(),
        "tokenizer_sha256": assets["tokenizer_sha256"],
        "tokenizer_version": version("tokenizers"),
        "eos_token_id": 151643,
        "pad_token_id": 151643,
        "by_partition": actual["by_partition"],
        "unavailable_examples_not_tokenized": receipt["files"]["unavailable.jsonl"]["count"],
        "limits": {"prompt": 2048, "completion_with_eos": 256, "sequence": 2304},
        "prompt_loss_masked": True,
        "completion_and_eos_supervised": True,
        "truncation": False,
        "model_weights_loaded": False,
        **tokens.FLAGS,
    }
    if canonical(actual) != canonical(expected):
        raise ValueError("All-example token preflight/version/schema/authority differs")
    for partition in task.PARTITIONS:
        stats = actual["by_partition"][partition]
        _fields(
            stats,
            (
                "examples",
                "max_prompt_tokens",
                "max_completion_with_eos_tokens",
                "max_active_tokens",
            ),
        )
        if (
            type(stats["examples"]) is not int
            or stats["examples"] != receipt["files"][partition + ".jsonl"]["count"]
        ):
            raise ValueError("Complete fit/check token coverage required")
        for key, limit in (
            ("max_prompt_tokens", 2048),
            ("max_completion_with_eos_tokens", 256),
            ("max_active_tokens", 2304),
        ):
            if type(stats[key]) is not int or not 1 <= stats[key] <= limit:
                raise ValueError("Token preflight bounds differ")


def make_registration(
    dataset: Path,
    dataset_pin: str,
    preflight: Path,
    preflight_pin: str,
    asset_registration: Path,
    asset_pin: str,
    reservation: Path,
    reservation_pin: str,
):
    started = time.monotonic()
    dataset = dataset.resolve()
    receipt = tokens.verified_receipt(dataset, dataset_pin)
    metadata = tokens.metadata(asset_registration, asset_pin)
    _fields(
        metadata,
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
            *legacy.FLAGS,
        ),
    )
    if (
        metadata["kind"] != legacy.KIND
        or metadata["source_sha256"] != legacy.source_sha256()
        or metadata["protocol"] != legacy.protocol()
        or metadata["session_split"] != receipt["session_split"]
        or any(metadata[k] is not v for k, v in legacy.FLAGS.items())
    ):
        raise ValueError("Frozen asset-registration identity/authority differs")
    assets = metadata["assets"]
    _fields(assets, (*ASSET_PATHS, *ASSET_PINS))
    validate_assets({**assets, "output_dir": str(dataset.parent / "asset-preflight-never-created")})
    protection = tokens.metadata(reservation, reservation_pin)
    legacy.trial.validate_reservation(
        protection, protection["dataset_completion_sha256"], protection["source_manifest_sha256"]
    )
    verify_preflight(preflight, preflight_pin, receipt, dataset_pin, assets)
    validate_split(receipt["session_split"])
    rows = {
        partition: [row for row, _, _ in tokens.read_examples(dataset, partition, receipt)]
        for partition in task.PARTITIONS
    }
    for name, info in receipt["files"].items():
        task.snapshot.checked_file(dataset / name, info["sha256"], tokens.MAX_OUTPUT_BYTES)
    chosen, counts = curriculum(rows["fit"], receipt["session_split"])
    encode = tokens.token_plan.load_tokenizer(
        Path(assets["tokenizer_json"]), assets["tokenizer_sha256"]
    )
    selection = [
        {**spec, **encoded(rows["fit"][spec["example_index"]], encode)[0]} for spec in chosen
    ]
    inputs = {
        "dataset": {"path": str(dataset.resolve()), "sha256": dataset_pin},
        "preflight": {"path": str(preflight.resolve()), "sha256": preflight_pin},
        "asset_registration": {"path": str(asset_registration.resolve()), "sha256": asset_pin},
        "reservation": {"path": str(reservation.resolve()), "sha256": reservation_pin},
    }
    for key, item in inputs.items():
        tokens.metadata(
            Path(item["path"]) / "completion.json" if key == "dataset" else Path(item["path"]),
            item["sha256"],
        )
    for name, info in receipt["files"].items():
        task.snapshot.checked_file(dataset / name, info["sha256"], tokens.MAX_OUTPUT_BYTES)
    tokens.deadline_guard(started + 600)
    value = {
        "kind": KIND,
        "protocol": protocol(),
        "source_sha256": source_sha256(),
        "inputs": inputs,
        "assets": assets,
        "session_split": receipt["session_split"],
        "fit_joint_counts": counts,
        "fit_examples": len(rows["fit"]),
        "selection": selection,
        "comparison": {
            "cases": len(rows["check"]),
            "sessions": len(receipt["session_split"]["check"]),
            "file": receipt["files"]["check.jsonl"],
            "ordered_examples_sha256": digest([digest(row) for row in rows["check"]]),
        },
        "preparation_registration_sha256": receipt["registration_sha256"],
        **FLAGS,
    }
    return value, rows["fit"]


def disjoint(output: Path, value: dict) -> None:
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("Fresh exclusive output and existing parent required")
    protected = [Path(item["path"]).resolve() for item in value["inputs"].values()]
    protected += [Path(value["assets"][key]).resolve() for key in ASSET_PATHS]
    for path in protected:
        if output.resolve().is_relative_to(path) or path.is_relative_to(output.resolve()):
            raise ValueError("Output cannot overlap frozen dataset or pinned assets/metadata")


def freeze(*args) -> dict:
    *inputs, output = args
    value, rows = make_registration(*inputs)
    disjoint(output, value)
    # Check the exact future request byte/vocabulary budget before publishing metadata.
    worker_packet(
        value, rows, "0" * 64, output.with_name(output.stem + "_request_preview_never_created")
    )
    _write(output, value)
    return value


def registration(path: Path, pin: str):
    value = tokens.metadata(path, pin)
    _fields(
        value,
        (
            "kind",
            "protocol",
            "source_sha256",
            "inputs",
            "assets",
            "session_split",
            "fit_joint_counts",
            "fit_examples",
            "selection",
            "comparison",
            "preparation_registration_sha256",
            *FLAGS,
        ),
    )
    if value["protocol"] != protocol() or value["source_sha256"] != source_sha256():
        raise ValueError("New context-v2 source-bound registration required")
    _fields(value["inputs"], ("dataset", "preflight", "asset_registration", "reservation"))
    args = []
    for name in ("dataset", "preflight", "asset_registration", "reservation"):
        item = value["inputs"][name]
        _fields(item, ("path", "sha256"))
        _absolute(item["path"])
        check_digest(item["sha256"])
        args.extend((Path(item["path"]), item["sha256"]))
    rebuilt, rows = make_registration(*args)
    if canonical(value) != canonical(rebuilt):
        raise ValueError("Frozen selection, complete comparison or authority changed")
    return value, rows


def worker_packet(value: dict, rows: list[dict], pin: str, output: Path) -> dict:
    packet = {
        "kind": KIND,
        "profile": profile(),
        "source_sha256": source_sha256(),
        "registration_sha256": pin,
        "dataset_completion_sha256": value["inputs"]["dataset"]["sha256"],
        "token_preflight_sha256": value["inputs"]["preflight"]["sha256"],
        "enable_research_training": True,
        **value["assets"],
        "output_dir": str(output.resolve()),
        "session_split": value["session_split"],
        "fit_joint_counts": value["fit_joint_counts"],
        "selection": [
            {"spec": spec, "example": rows[spec["example_index"]]} for spec in value["selection"]
        ],
    }
    validate_packet(packet)
    return packet


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
    value, rows = registration(path, pin)
    disjoint(output, value)
    if output.resolve().is_relative_to(path.resolve()) or path.resolve().is_relative_to(
        output.resolve()
    ):
        raise ValueError("Output cannot overlap its training registration")
    packet = worker_packet(value, rows, pin, output)
    output.mkdir(exist_ok=False)
    started = time.monotonic()
    try:
        _write(output / "request.json", packet)
        result = strict_json(
            _exchange([packet["python_executable"], "-I", "-m", WORKER], packet, TIMEOUT_MS)
        )
        metrics = validate_result(result, packet, output)
        final, final_rows = registration(path, pin)
        if final != value or final_rows != rows:
            raise ValueError("Frozen context inputs changed during training")
        report = {
            "status": "completed_192_update_context_v2_natural_trial_not_validated",
            "registration_sha256": pin,
            "result": result,
            "elapsed_seconds": time.monotonic() - started,
            "selected_training_examples": STEPS,
            "selected_training_sessions": len(
                {i["spec"]["source_session"] for i in packet["selection"]}
            ),
            "selected_joint_counts": dict(
                Counter(i["spec"]["joint_state"] for i in packet["selection"])
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
    for name in (
        "dataset",
        "token-preflight",
        "assets-registration",
        "reservation",
        "registration",
    ):
        parser.add_argument("--" + name, type=Path)
        parser.add_argument("--" + name + "-sha256")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enable-research-training", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        values = (
            args.dataset,
            args.dataset_sha256,
            args.token_preflight,
            args.token_preflight_sha256,
            args.assets_registration,
            args.assets_registration_sha256,
            args.reservation,
            args.reservation_sha256,
        )
        if any(v is None for v in values):
            parser.error(
                "Pinned context dataset, all-example preflight, asset registration "
                "and protection metadata required"
            )
        result = freeze(*values, args.output)
        print(
            canonical(
                {
                    "kind": result["kind"],
                    "training_examples": len(result["selection"]),
                    "comparison_cases": result["comparison"]["cases"],
                    "training_performed": False,
                }
            )
        )
    else:
        if args.registration is None or args.registration_sha256 is None:
            parser.error("Pinned new context-v2 registration required")
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
