"""Checkpoint-only synthetic CUDA LoRA capability check; never market-training approval."""

import argparse
import hashlib
import math
import sys
import time
from pathlib import Path

from ai_trader.models.local_checkpoint import (
    canonical,
    check_digest,
    digest,
    inspect_checkpoint,
    strict_json,
)
from ai_trader.models.local_reviewer import _exchange
from ai_trader.research.advisory_evaluation import read_pinned
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_plan import completion_only_record, proposed_recipe
from ai_trader.training.advisory_training_run import (
    _absolute,
    _lock_pin,
    _runtime_shape,
    _write,
    implementation_sha256,
)
from ai_trader.training.lora_backend import MAX_TRAINABLE_PARAMETERS, adapter_manifest

KIND = "qwen3_4b_synthetic_cuda_capability_v1"
WORKER = "ai_trader.training._qwen_gpu_smoke_worker"
MAX_REQUEST_BYTES = 16 * 1024
MAX_EVENTS_BYTES = 128 * 1024
STEPS = 3
TIMEOUT_MS = 600_000
NO_AUTHORITY = {
    "market_data_used": False,
    "curriculum_used": False,
    "held_out_evaluated": False,
    "promotion_allowed": False,
    "execution_allowed": False,
    "adapter_approved_for_inference": False,
    "automatic_retry": False,
}


def synthetic_record():
    """Full-length deterministic token IDs, not text, market labels or a curriculum."""
    return completion_only_record(
        [100 + i % 32 for i in range(2048)],
        [200 + i % 32 for i in range(255)],
        eos_token_id=151643,
        pad_token_id=151643,
    )


def profile():
    return {
        **proposed_recipe(),
        "purpose": KIND,
        "max_optimizer_steps": STEPS,
        "limits_enforced_by_training_worker": True,
        "synthetic_record_sha256": digest(synthetic_record()),
        "cublas_workspace_config": ":4096:8",
        "market_training_authorized": False,
    }


def source_sha256():
    root = Path(__file__).parent
    return digest(
        {
            "backend_and_transport": implementation_sha256(),
            **{
                name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in ("qwen_gpu_smoke.py", "_qwen_gpu_smoke_worker.py")
            },
        }
    )


def validate_request(request, *, verify_assets=False):
    _fields(
        request,
        (
            "enable_gpu_smoke",
            "python_executable",
            "output_dir",
            "checkpoint",
            "checkpoint_sha256",
            "dependency_lock",
            "dependency_lock_sha256",
            "runtime_manifest",
            "runtime_sha256",
            "source_sha256",
            "profile",
        ),
    )
    if request["enable_gpu_smoke"] is not True:
        raise ValueError("Explicit synthetic GPU smoke opt-in required.")
    if request["profile"] != profile() or request["source_sha256"] != source_sha256():
        raise ValueError("Fixed GPU capability profile or source changed.")
    python = _absolute(request["python_executable"])
    base, output = _absolute(request["checkpoint"]), _absolute(request["output_dir"])
    if python.is_symlink() or not python.is_file() or base.is_symlink() or not base.is_dir():
        raise ValueError("Regular local checkpoint and interpreter required.")
    if (
        output.is_symlink()
        or not output.parent.is_dir()
        or (
            output.resolve().is_relative_to(base.resolve())
            or base.resolve().is_relative_to(output.resolve())
        )
    ):
        raise ValueError("New output must not overlap the checkpoint.")
    for key in ("checkpoint_sha256", "dependency_lock_sha256", "runtime_sha256"):
        check_digest(request[key])
    pins = _lock_pin(_absolute(request["dependency_lock"]), request["dependency_lock_sha256"])
    runtime = read_pinned(_absolute(request["runtime_manifest"]), request["runtime_sha256"])
    _runtime_shape(runtime)
    if runtime["python_executable"] != str(python) or any(
        runtime["packages"][name] != pins[name] for name in runtime["packages"]
    ):
        raise ValueError("Training runtime differs from pinned lock/interpreter.")
    if len(canonical(request).encode()) > MAX_REQUEST_BYTES:
        raise ValueError("GPU capability request byte budget exceeded.")
    if (
        verify_assets
        and digest(inspect_checkpoint(base, "Qwen/Qwen3-4B-Base")) != request["checkpoint_sha256"]
    ):
        raise ValueError("Local Qwen checkpoint pin mismatch.")
    return pins, runtime


def finite_nonnegative(values):
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("Finite nonnegative native metrics required.")


def validate_result(result, request, directory):
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
    if result["kind"] != KIND or result["request_sha256"] != digest(request):
        raise ValueError("GPU result request binding mismatch.")
    if type(result["steps"]) is not int or result["steps"] != STEPS:
        raise ValueError("Incomplete GPU capability steps.")
    if any(result[key] is not value for key, value in NO_AUTHORITY.items()):
        raise ValueError("Synthetic smoke cannot grant evaluation or trading authority.")
    if result["frozen_parameter_guards_passed"] is not True or (
        type(result["trainable_parameters"]) is not int
        or not 1 <= result["trainable_parameters"] <= MAX_TRAINABLE_PARAMETERS
    ):
        raise ValueError("Frozen base/adapter budget guards failed.")
    metrics = result["metrics"]
    if type(metrics) is not list or len(metrics) != STEPS:
        raise ValueError("Three completed native metrics required.")
    for item in metrics:
        _fields(item, ("loss", "gradient_norm"))
        finite_nonnegative(item.values())
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
    if any(
        reload[key] is not True
        for key in ("adapter_updated", "reload_state_equal", "base_checkpoint_unchanged")
    ):
        raise ValueError("GPU adapter persistence verification failed.")
    finite_nonnegative([reload["probe_loss_before"], reload["probe_loss_after"]])
    if (
        reload["probe_loss_absolute_tolerance"] != 1e-5
        or not math.isclose(
            reload["probe_loss_before"], reload["probe_loss_after"], rel_tol=0, abs_tol=1e-5
        )
        or adapter_manifest(directory / "adapter") != reload["adapter_manifest"]
    ):
        raise ValueError("GPU adapter bytes/state/probe mismatch.")
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
    if type(resources["device"]) is not str or not 1 <= len(resources["device"]) <= 128:
        raise ValueError("Bounded CUDA device description required.")
    if (
        any(
            type(resources[k]) is not int or resources[k] <= 0
            for k in ("total_bytes", "peak_allocated_bytes", "peak_reserved_bytes")
        )
        or not (
            resources["peak_allocated_bytes"]
            <= resources["peak_reserved_bytes"]
            <= resources["total_bytes"]
        )
        or resources["cuda_bf16"] is not True
        or resources["deterministic_algorithms"] is not True
        or resources["tf32_enabled"] is not False
    ):
        raise ValueError("Invalid GPU resource/configuration evidence.")
    _, runtime = validate_request(request, verify_assets=True)
    if result["runtime"] != runtime:
        raise ValueError("Native runtime changed.")
    events_path = directory / "steps.jsonl"
    if events_path.is_symlink() or not events_path.is_file():
        raise ValueError("Regular durable step journal required.")
    with events_path.open("rb") as stream:
        raw = stream.read(MAX_EVENTS_BYTES + 1)
    if len(raw) > MAX_EVENTS_BYTES:
        raise ValueError("GPU step journal byte bound exceeded.")
    events = [strict_json(line) for line in raw.splitlines()]
    expected = [
        {"event": "native_initialization_started"},
        {"event": "native_initialization_completed"},
    ]
    for step, metric in enumerate(metrics, 1):
        expected.extend(
            [
                {"event": "step_intent", "step": step},
                {"event": "step_completed", "step": step, **metric},
            ]
        )
    expected.extend([{"event": "save_reload_started"}, {"event": "save_reload_completed"}])
    if events != expected:
        raise ValueError("GPU durable journal differs from completed steps.")


def run(
    python,
    checkpoint,
    checkpoint_sha256,
    dependency_lock,
    lock_sha256,
    runtime_manifest,
    runtime_sha256,
    output_dir,
    *,
    enable_gpu_smoke=False,
):
    if enable_gpu_smoke is not True:
        raise ValueError("Explicit synthetic GPU smoke opt-in required.")
    request = {
        "enable_gpu_smoke": True,
        "python_executable": str(Path(python).resolve()),
        "checkpoint": str(Path(checkpoint).resolve()),
        "checkpoint_sha256": checkpoint_sha256,
        "dependency_lock": str(Path(dependency_lock).resolve()),
        "dependency_lock_sha256": lock_sha256,
        "runtime_manifest": str(Path(runtime_manifest).resolve()),
        "runtime_sha256": runtime_sha256,
        "output_dir": str(Path(output_dir).resolve()),
        "source_sha256": source_sha256(),
        "profile": profile(),
    }
    validate_request(request, verify_assets=True)
    directory = Path(request["output_dir"])
    directory.mkdir()  # Exclusive; no resume, overwrite, replacement or retry.
    started = time.monotonic()
    try:
        _write(directory / "request.json", request)
        result = strict_json(
            _exchange([request["python_executable"], "-I", "-m", WORKER], request, TIMEOUT_MS)
        )
        validate_result(result, request, directory)
        if (directory / "failure.json").exists():
            raise ValueError("Failure evidence prohibits a passed GPU report.")
        report = {
            "status": "passed_synthetic_gpu_capability_only",
            "result": result,
            "elapsed_seconds": time.monotonic() - started,
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("python", "checkpoint", "dependency-lock", "runtime-manifest", "output-dir"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    for name in ("checkpoint-sha256", "dependency-lock-sha256", "runtime-sha256"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--enable-gpu-smoke", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run(
            args.python,
            args.checkpoint,
            args.checkpoint_sha256,
            args.dependency_lock,
            args.dependency_lock_sha256,
            args.runtime_manifest,
            args.runtime_sha256,
            args.output_dir,
            enable_gpu_smoke=args.enable_gpu_smoke,
        )
    except (ValueError, OSError, RuntimeError) as exc:
        print(
            f"GPU capability failed: {type(exc).__name__}; retained evidence, no retry",
            file=sys.stderr,
        )
        return 2
    print(
        canonical(
            {
                "status": report["status"],
                "steps": report["result"]["steps"],
                "resources": report["result"]["resources"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
