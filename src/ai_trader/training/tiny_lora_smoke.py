"""Supervised native-library check: fixed random tiny model, never a Qwen checkpoint fit."""

import argparse
import hashlib
import math
import sys
import time
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, digest, strict_json
from ai_trader.models.local_reviewer import _exchange
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import (
    _absolute,
    _lock_pin,
    _write,
    implementation_sha256,
)
from ai_trader.training.lora_backend import adapter_manifest

WORKER = "ai_trader.training._tiny_lora_worker"
MAX_REQUEST_BYTES = 8192
STEPS = 3
TIMEOUT_MS = 120_000
KIND = "tiny_random_lora_cpu_smoke_v1"
NO_AUTHORITY = {
    "qwen_checkpoint_loaded": False,
    "market_data_used": False,
    "held_out_evaluated": False,
    "promotion_allowed": False,
    "execution_allowed": False,
    "automatic_retry": False,
}


def source_sha256():
    root = Path(__file__).parent
    return digest(
        {
            "backend_and_transport": implementation_sha256(),
            **{
                name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in ("tiny_lora_smoke.py", "_tiny_lora_worker.py")
            },
        }
    )


def validate_request(request):
    _fields(
        request,
        (
            "enable_native_smoke",
            "python_executable",
            "output_dir",
            "dependency_lock",
            "dependency_lock_sha256",
            "source_sha256",
        ),
    )
    if request["enable_native_smoke"] is not True:
        raise ValueError("Explicit native smoke opt-in required.")
    python = _absolute(request["python_executable"])
    if python.is_symlink() or not python.is_file():
        raise ValueError("Regular explicit interpreter required.")
    _absolute(request["output_dir"])
    pins = _lock_pin(_absolute(request["dependency_lock"]), request["dependency_lock_sha256"])
    if request["source_sha256"] != source_sha256():
        raise ValueError("Native smoke source changed.")
    if len(canonical(request).encode()) > MAX_REQUEST_BYTES:
        raise ValueError("Native smoke request budget exceeded.")
    return pins


def validate_result(result, request, directory):
    _fields(
        result,
        (
            "kind",
            "request_sha256",
            "steps",
            "metrics",
            "runtime",
            "base_parameters",
            "trainable_parameters",
            "base_parameters_unchanged",
            "cuda_initialized",
            "reload",
            *NO_AUTHORITY,
        ),
    )
    if result["kind"] != KIND or result["request_sha256"] != digest(request):
        raise ValueError("Native smoke result binding mismatch.")
    if type(result["steps"]) is not int or result["steps"] != STEPS:
        raise ValueError("Incomplete native smoke.")
    if any(result[k] is not v for k, v in NO_AUTHORITY.items()):
        raise ValueError("Native smoke has no evaluation/trading authority.")
    if result["cuda_initialized"] is not False or result["base_parameters_unchanged"] is not True:
        raise ValueError("CPU/frozen-base verification failed.")
    for name, upper in (("base_parameters", 100_000), ("trainable_parameters", 4096)):
        if type(result[name]) is not int or not 1 <= result[name] <= upper:
            raise ValueError("Tiny parameter budget exceeded.")
    metrics = result["metrics"]
    if type(metrics) is not list or len(metrics) != STEPS:
        raise ValueError("Missing step metrics.")
    for metric in metrics:
        _fields(metric, ("loss", "gradient_norm"))
        if any(
            type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in metric.values()
        ):
            raise ValueError("Invalid native step metric.")
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
        reload[k] is not True
        for k in (
            "adapter_updated",
            "reload_state_equal",
            "base_checkpoint_unchanged",
        )
    ):
        raise ValueError("Adapter persistence check failed.")
    before, after = reload["probe_loss_before"], reload["probe_loss_after"]
    if (
        any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in (before, after))
        or reload["probe_loss_absolute_tolerance"] != 1e-5
        or not math.isclose(before, after, rel_tol=0, abs_tol=1e-5)
    ):
        raise ValueError("Native reload loss mismatch.")
    if adapter_manifest(directory / "adapter") != reload["adapter_manifest"]:
        raise ValueError("Native adapter artifact mismatch.")
    runtime = result["runtime"]
    # Child checks every lock entry; parent also verifies the reported critical versions/path.
    from ai_trader.training.advisory_training_run import _runtime_shape

    _runtime_shape(runtime)
    pins = validate_request(request)
    if runtime["python_executable"] != request["python_executable"] or any(
        runtime["packages"][name] != pins[name] for name in runtime["packages"]
    ):
        raise ValueError("Native runtime mismatch.")


def run(python, dependency_lock, lock_sha256, output_dir, *, enable_native_smoke=False):
    if enable_native_smoke is not True:
        raise ValueError("Explicit native smoke opt-in required.")
    request = {
        "enable_native_smoke": True,
        "python_executable": str(Path(python).resolve()),
        "output_dir": str(Path(output_dir).resolve()),
        "dependency_lock": str(Path(dependency_lock).resolve()),
        "dependency_lock_sha256": lock_sha256,
        "source_sha256": source_sha256(),
    }
    validate_request(request)
    directory = Path(request["output_dir"])
    directory.mkdir()  # Exclusive, no parent creation, overwrite, resume or retry.
    started = time.monotonic()
    try:
        _write(directory / "request.json", request)
        raw = _exchange([request["python_executable"], "-I", "-m", WORKER], request, TIMEOUT_MS)
        result = strict_json(raw)
        validate_result(result, request, directory)
        report = {
            "status": "passed",
            "result": result,
            "elapsed_seconds": time.monotonic() - started,
            **NO_AUTHORITY,
        }
        _write(directory / "run.json", report)
        return report
    except BaseException:
        # Partial outputs remain quarantined. A missing report is never success.
        if not (directory / "run.json").exists():
            _write(
                directory / "run.json",
                {
                    "status": "failed_or_interrupted",
                    "completed_steps": None,
                    **NO_AUTHORITY,
                },
            )
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--dependency-lock", required=True, type=Path)
    parser.add_argument("--dependency-lock-sha256", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--enable-native-smoke", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run(
            args.python,
            args.dependency_lock,
            args.dependency_lock_sha256,
            args.output_dir,
            enable_native_smoke=args.enable_native_smoke,
        )
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Native smoke failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(canonical(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
