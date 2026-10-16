"""Explicit supervised LoRA smoke launch. No default fitting, evaluation, promotion or trading."""

import argparse
import hashlib
import math
import os
import platform
import random
import re
import sys
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, check_digest, digest, strict_json
from ai_trader.models.local_reviewer import _exchange
from ai_trader.models.review_contracts import SPOT_LONG_V2_PROMPT, base_review_prompt
from ai_trader.research.advisory_evaluation import load_suite, read_pinned
from ai_trader.training.advisory_curriculum import _fields, verify_candidate
from ai_trader.training.advisory_holdout import audit_reservation
from ai_trader.training.advisory_training_plan import (
    completion_only_record,
    load_tokenizer,
    proposed_recipe,
)
from ai_trader.training.lora_backend import adapter_manifest

WORKER = "ai_trader.training._local_training_worker"
MAX_REQUEST_BYTES = 32 * 1024
PACKAGES = ("torch", "transformers", "peft", "accelerate", "safetensors", "tokenizers", "numpy")
INPUTS = ("suite", "review", "candidate", "registry", "runtime", "dependency_lock")


def runtime_manifest():
    """Read installed-version metadata without importing native/model libraries."""
    packages = {}
    for name in PACKAGES:
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {
        "schema_version": 1,
        "kind": "qwen_lora_runtime_versions_v1",
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "packages": packages,
    }


def _absolute(value):
    if type(value) is not str or not value or len(value) > 2048 or not Path(value).is_absolute():
        raise ValueError("Explicit bounded absolute path required.")
    return Path(value)


def _pinned_file(value):
    _fields(value, ("path", "sha256"))
    check_digest(value["sha256"])
    return _absolute(value["path"])


def _lock_pin(path, pin):
    check_digest(pin)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Regular dependency lock required.")
    with path.open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    if not raw or len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError("Dependency lock size/SHA256 mismatch.")
    pins = {}
    text = raw.decode("utf-8").replace("\\\r\n", " ").replace("\\\n", " ")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(
            r"([A-Za-z0-9_.-]+)==([A-Za-z0-9.+!_-]+)(?:\s+--hash=sha256:[a-f0-9]{64})+", line
        )
        if match is None:
            raise ValueError(
                "Self-contained name==version/hash lock required; no includes or URLs."
            )
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        if name in pins:
            raise ValueError("Duplicate dependency lock entry.")
        pins[name] = match[2]
    if not set(PACKAGES) <= pins.keys():
        raise ValueError("Training dependency lock is incomplete.")
    return pins


def implementation_sha256():
    root = Path(__file__).resolve().parents[1]
    names = (
        "training/advisory_training_run.py",
        "training/_local_training_worker.py",
        "training/lora_backend.py",
        "training/advisory_training_plan.py",
        "training/advisory_curriculum.py",
        "training/advisory_holdout.py",
        "research/advisory_evaluation.py",
        "research/advisory_fact_audit.py",
        "research/spot_long_checks.py",
        "research/council.py",
        "models/local_checkpoint.py",
        "models/local_reviewer.py",
        "models/review_contracts.py",
    )
    return digest({name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names})


def _runtime_shape(runtime):
    _fields(runtime, runtime_manifest())
    if (
        type(runtime["schema_version"]) is not int
        or runtime["schema_version"] != 1
        or runtime["kind"] != "qwen_lora_runtime_versions_v1"
    ):
        raise ValueError("Invalid runtime manifest.")
    _fields(runtime["packages"], PACKAGES)
    if any(type(v) is not str or not v or len(v) > 128 for v in runtime["packages"].values()):
        raise ValueError("Every training dependency must have a pinned installed version.")
    if type(runtime["python_version"]) is not str or not runtime["python_version"].startswith(
        "3.12."
    ):
        raise ValueError("CPython 3.12 runtime required.")
    if not _absolute(runtime["python_executable"]).is_file():
        raise ValueError("Pinned training interpreter is missing.")


def prepare_run(inputs, checkpoint, checkpoint_sha256, tokenizer_sha256, output_dir):
    """Freeze launch metadata only after curriculum/candidate/reservation checks pass."""
    _fields(inputs, INPUTS)
    paths = {name: _pinned_file(value) for name, value in inputs.items()}
    suite = load_suite(paths["suite"], inputs["suite"]["sha256"])
    review = read_pinned(paths["review"], inputs["review"]["sha256"])
    candidate = verify_candidate(
        suite, review, read_pinned(paths["candidate"], inputs["candidate"]["sha256"])
    )
    registry = read_pinned(paths["registry"], inputs["registry"]["sha256"])
    if not audit_reservation(suite, registry)["reservation_complete"]:
        raise ValueError("Complete declared protected-evaluation reservation required.")
    runtime = read_pinned(paths["runtime"], inputs["runtime"]["sha256"])
    _runtime_shape(runtime)
    pins = _lock_pin(paths["dependency_lock"], inputs["dependency_lock"]["sha256"])
    if any(pins[name] != runtime["packages"][name] for name in PACKAGES):
        raise ValueError("Runtime versions differ from the dependency lock.")
    base, output = _absolute(checkpoint), _absolute(output_dir)
    if base.is_symlink() or not base.is_dir() or output.is_symlink():
        raise ValueError("Regular checkpoint/output paths required.")
    if output.resolve().is_relative_to(base.resolve()) or base.resolve().is_relative_to(
        output.resolve()
    ):
        raise ValueError("Output must not overlap the base checkpoint.")
    if not output.parent.is_dir():
        raise ValueError("Existing explicit output parent required.")
    check_digest(checkpoint_sha256)
    check_digest(tokenizer_sha256)
    recipe = {**proposed_recipe(), "limits_enforced_by_training_worker": True}
    result = {
        "schema_version": 1,
        "kind": "bounded_qwen_lora_launch_v1",
        "inputs": inputs,
        "checkpoint": checkpoint,
        "checkpoint_sha256": checkpoint_sha256,
        "tokenizer_sha256": tokenizer_sha256,
        "output_dir": str(output.resolve()),
        "python_executable": runtime["python_executable"],
        "worker_module": WORKER,
        "implementation_sha256": implementation_sha256(),
        "candidate_sha256": digest(candidate),
        "recipe": recipe,
        "heldout_evaluation_allowed": False,
        "promotion_allowed": False,
        "execution_allowed": False,
    }
    if len(canonical({"enable_local_training": True, "plan": result}).encode()) > MAX_REQUEST_BYTES:
        raise ValueError("Launch request byte budget exceeded.")
    return result


def validate_launch(plan):
    if type(plan) is not dict:
        raise ValueError("Launch object required.")
    _fields(
        plan,
        (
            "schema_version",
            "kind",
            "inputs",
            "checkpoint",
            "checkpoint_sha256",
            "tokenizer_sha256",
            "output_dir",
            "python_executable",
            "worker_module",
            "implementation_sha256",
            "candidate_sha256",
            "recipe",
            "heldout_evaluation_allowed",
            "promotion_allowed",
            "execution_allowed",
        ),
    )
    rebuilt = prepare_run(
        plan["inputs"],
        plan["checkpoint"],
        plan["checkpoint_sha256"],
        plan["tokenizer_sha256"],
        plan["output_dir"],
    )
    if canonical(rebuilt) != canonical(plan):
        raise ValueError("Launch bindings or fixed recipe changed.")


def _write(path, value):
    raw = canonical(value) + "\n"
    if len(raw.encode()) > 1024 * 1024:
        raise ValueError("Output artifact budget exceeded.")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _event(stream, value):
    stream.write(canonical(value) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def train_loop(backend, records, directory, recipe, *, deadline, clock=time.monotonic):
    """Durable intent before each step; the supervising process enforces stalls/timeouts."""
    if canonical(recipe) != canonical(
        {**proposed_recipe(), "limits_enforced_by_training_worker": True}
    ):
        raise ValueError("Only the fixed bounded smoke recipe is supported.")
    if not 1 <= len(records) <= 64:
        raise ValueError("Training record budget exceeded.")

    def check_time():
        if clock() >= deadline:
            raise TimeoutError("Training deadline.")

    order, generator = list(range(len(records))), random.Random(recipe["seed"])
    completed = 0
    with (directory / "steps.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for step in range(recipe["max_optimizer_steps"]):
            check_time()
            if step % len(order) == 0:
                generator.shuffle(order)
            index = order[step % len(order)]
            _event(stream, {"event": "step_started", "step": step + 1, "record_index": index})
            metrics = backend.step(records[index])
            _fields(metrics, ("loss", "gradient_norm"))
            if any(
                type(v) not in (int, float) or not math.isfinite(v) or v < 0
                for v in metrics.values()
            ):
                raise ValueError("Invalid optimization metrics.")
            completed += 1
            check_time()
            _event(stream, {"event": "step_completed", "step": completed, **metrics})
        check_time()
        _event(stream, {"event": "save_reload_started", "completed_steps": completed})
        reload = backend.save_reload(directory / "adapter", records[0])
        check_time()
        _event(stream, {"event": "save_reload_completed", "completed_steps": completed})
    return {"completed_steps": completed, "reload": reload}


def execute_worker(plan):
    """Private execution entry; public callers must use the supervised opt-in launcher."""
    deadline = time.monotonic() + 600
    validate_launch(plan)
    runtime = read_pinned(
        Path(plan["inputs"]["runtime"]["path"]), plan["inputs"]["runtime"]["sha256"]
    )
    if canonical(runtime_manifest()) != canonical(runtime):
        raise ValueError("Installed runtime differs from pinned versions/interpreter.")
    lock = plan["inputs"]["dependency_lock"]
    if any(
        version(name) != pin for name, pin in _lock_pin(Path(lock["path"]), lock["sha256"]).items()
    ):
        raise ValueError("Installed dependency differs from the self-contained lock.")
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        if os.environ.get(key) != "1":
            raise ValueError("Offline worker environment required.")
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    directory = Path(plan["output_dir"])
    if directory.is_symlink() or {p.name for p in directory.iterdir()} != {"launch.json"}:
        raise ValueError("Fresh supervisor-owned output directory required.")
    if (
        read_pinned(
            directory / "launch.json", hashlib.sha256((canonical(plan) + "\n").encode()).hexdigest()
        )
        != plan
    ):
        raise ValueError("Supervisor launch file mismatch.")
    encode = load_tokenizer(Path(plan["checkpoint"]) / "tokenizer.json", plan["tokenizer_sha256"])
    item = plan["inputs"]["candidate"]
    candidate = read_pinned(Path(item["path"]), item["sha256"])
    records = [
        completion_only_record(
            encode(base_review_prompt(SPOT_LONG_V2_PROMPT, e["input"])),
            encode(e["target_response"]),
            eos_token_id=151643,
            pad_token_id=151643,
        )
        for e in candidate["examples"]
    ]
    from ai_trader.training.lora_backend import PeftBackend

    backend = PeftBackend(Path(plan["checkpoint"]), plan["checkpoint_sha256"], plan["recipe"])
    result = train_loop(backend, records, directory, plan["recipe"], deadline=deadline)
    result.update(
        kind="qwen_lora_worker_result_v1",
        launch_sha256=digest(plan),
        heldout_contents_opened=False,
        promotion_allowed=False,
        execution_allowed=False,
    )
    _write(directory / "worker_result.json", result)
    return {
        "launch_sha256": digest(plan),
        "result_sha256": hashlib.sha256((canonical(result) + "\n").encode()).hexdigest(),
    }


def run(plan, *, enable_local_training=False):
    if enable_local_training is not True:
        raise ValueError("Explicit enable_local_training=True required.")
    validate_launch(plan)
    directory = Path(plan["output_dir"])
    directory.mkdir()  # Claim once. Failures leave partial artifacts, never automatically resume.
    _write(directory / "launch.json", plan)
    try:
        raw = _exchange(
            [plan["python_executable"], "-I", "-m", WORKER],
            {"enable_local_training": True, "plan": plan},
            600000,
        )
        response = strict_json(raw)
        _fields(response, ("launch_sha256", "result_sha256"))
        if response["launch_sha256"] != digest(plan):
            raise ValueError("Worker response binding mismatch.")
        result = read_pinned(directory / "worker_result.json", response["result_sha256"])
        _fields(
            result,
            (
                "kind",
                "launch_sha256",
                "completed_steps",
                "reload",
                "heldout_contents_opened",
                "promotion_allowed",
                "execution_allowed",
            ),
        )
        if result["kind"] != "qwen_lora_worker_result_v1" or any(
            result[k] is not False
            for k in ("heldout_contents_opened", "promotion_allowed", "execution_allowed")
        ):
            raise ValueError("Invalid worker result authority/schema.")
        if (
            result.get("launch_sha256") != digest(plan)
            or type(result.get("completed_steps")) is not int
            or result["completed_steps"] != 20
        ):
            raise ValueError("Incomplete or misbound training result.")
        for key in ("adapter_updated", "reload_state_equal", "base_checkpoint_unchanged"):
            if result["reload"][key] is not True:
                raise ValueError("Adapter verification failed.")
        _fields(
            result["reload"],
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
        losses = [result["reload"][key] for key in ("probe_loss_before", "probe_loss_after")]
        if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in losses) or (
            type(result["reload"]["probe_loss_absolute_tolerance"]) is not float
            or result["reload"]["probe_loss_absolute_tolerance"] != 1e-5
            or not math.isclose(*losses, rel_tol=0, abs_tol=1e-5)
        ):
            raise ValueError("Invalid reload probe comparison.")
        if result["reload"]["adapter_manifest"] != adapter_manifest(directory / "adapter"):
            raise ValueError("Adapter manifest mismatch.")
        summary = {
            "status": "completed_adapter_smoke",
            "launch_sha256": digest(plan),
            "completed_steps": 20,
            "promotion_allowed": False,
            "execution_allowed": False,
            "heldout_evaluated": False,
            "result_sha256": response["result_sha256"],
        }
    except BaseException:
        _write(
            directory / "run.json",
            {
                "status": "failed_or_interrupted",
                "launch_sha256": digest(plan),
                "completed_steps": None,
                "promotion_allowed": False,
                "execution_allowed": False,
                "automatic_retry_allowed": False,
            },
        )
        raise
    _write(directory / "run.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("runtime", "prepare", "run"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--source-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--enable-local-training", action="store_true")
    args = parser.parse_args()
    if args.action == "runtime":
        if args.source or args.source_sha256 or args.enable_local_training or not args.output:
            parser.error("Runtime capture accepts only --output.")
        _write(args.output, runtime_manifest())
        return 0
    if not args.source or not args.source_sha256:
        parser.error("Pinned local --source and --source-sha256 required.")
    data = read_pinned(args.source, args.source_sha256)
    if args.action == "prepare":
        if args.enable_local_training or not args.output:
            parser.error("Preparation needs --output and cannot enable training.")
        _fields(
            data, ("inputs", "checkpoint", "checkpoint_sha256", "tokenizer_sha256", "output_dir")
        )
        _write(args.output, prepare_run(**data))
        return 0
    if args.output or not args.enable_local_training:
        parser.error(
            "Run requires --enable-local-training and uses only the plan's new output directory."
        )
    print(canonical(run(data, enable_local_training=True)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
