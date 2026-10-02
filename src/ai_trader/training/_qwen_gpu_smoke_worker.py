"""Private synthetic-token hardware check; production market-training gates stay separate."""

import contextlib
import os
import sys
from importlib.metadata import version
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, digest, strict_json
from ai_trader.training.advisory_training_run import _event, _write, runtime_manifest
from ai_trader.training.lora_backend import PeftBackend, trainable_adapters
from ai_trader.training.qwen_gpu_smoke import (
    KIND,
    MAX_REQUEST_BYTES,
    NO_AUTHORITY,
    STEPS,
    finite_nonnegative,
    synthetic_record,
    validate_request,
)


def create_backend(request):
    # Fixed child-only deterministic workspace; before native imports/CUDA initialization.
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = request["profile"]["cublas_workspace_config"]
    import torch

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise ValueError("CUDA BF16 required; no CPU or quantization fallback.")
    torch.cuda.reset_peak_memory_stats()
    return PeftBackend(
        Path(request["checkpoint"]), request["checkpoint_sha256"], request["profile"]
    )


def verify_frozen_parameters(backend):
    """Optimizer/trainable-set and frozen gradient/device guards; no 4B CPU tensor copy."""
    trainable_adapters(backend.model)
    if any(
        p.device.type != "cuda" or (not p.requires_grad and p.grad is not None)
        for p in backend.model.parameters()
    ):
        raise ValueError("CUDA placement or frozen parameter gradient guard failed.")


def resources(backend):
    torch = backend.torch
    torch.cuda.synchronize()
    return {
        "device": torch.cuda.get_device_name(),
        "total_bytes": torch.cuda.get_device_properties(0).total_memory,
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        "cuda_bf16": torch.cuda.is_bf16_supported(),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "tf32_enabled": torch.backends.cuda.matmul.allow_tf32,
    }


def respond(raw):
    if type(raw) is not bytes or len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("GPU capability request byte budget exceeded.")
    request = strict_json(raw)
    pins, runtime = validate_request(request, verify_assets=True)
    if (
        request["python_executable"] != str(Path(sys.executable).resolve())
        or runtime_manifest() != runtime
    ):
        raise ValueError("Worker runtime/interpreter differs from pinned metadata.")
    if any(version(name) != expected for name, expected in pins.items()):
        raise ValueError("Installed training version differs from full dependency lock.")
    if any(
        os.environ.get(name) != "1"
        for name in (
            "HF_HUB_OFFLINE",
            "TRANSFORMERS_OFFLINE",
            "HF_HUB_DISABLE_TELEMETRY",
            "DO_NOT_TRACK",
        )
    ):
        raise ValueError("Offline synthetic GPU environment required.")
    directory = Path(request["output_dir"])
    if (
        directory.is_symlink()
        or not directory.is_dir()
        or {p.name for p in directory.iterdir()} != {"request.json"}
    ):
        raise ValueError("Fresh supervisor-owned GPU output required.")
    saved = directory / "request.json"
    if (
        saved.is_symlink()
        or saved.stat().st_size > MAX_REQUEST_BYTES
        or strict_json(saved.read_bytes()) != request
    ):
        raise ValueError("Persisted GPU request mismatch.")
    stage, metrics = "native_initialization", []
    try:
        with (directory / "steps.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            _event(stream, {"event": "native_initialization_started"})
            backend = create_backend(request)
            verify_frozen_parameters(backend)
            parameters = sum(p.numel() for p in trainable_adapters(backend.model))
            _event(stream, {"event": "native_initialization_completed"})
            record = synthetic_record()
            for step in range(1, STEPS + 1):
                stage = f"optimizer_step_{step}"
                _event(stream, {"event": "step_intent", "step": step})
                metric = backend.step(record)
                finite_nonnegative(metric.values())
                verify_frozen_parameters(backend)
                metrics.append(metric)
                _event(stream, {"event": "step_completed", "step": step, **metric})
            stage = "save_reload"
            _event(stream, {"event": "save_reload_started"})
            reload = backend.save_reload(directory / "adapter", record)
            # Reload is inference-only, so trainable_adapters intentionally no longer applies.
            if any(
                p.requires_grad or p.grad is not None or p.device.type != "cuda"
                for p in backend.model.parameters()
            ):
                raise ValueError("Reload must be CUDA inference-only without gradients.")
            evidence = resources(backend)
            _event(stream, {"event": "save_reload_completed"})
        return {
            "kind": KIND,
            "request_sha256": digest(request),
            "steps": STEPS,
            "metrics": metrics,
            "runtime": runtime_manifest(),
            "resources": evidence,
            "trainable_parameters": parameters,
            "frozen_parameter_guards_passed": True,
            "reload": reload,
            **NO_AUTHORITY,
        }
    except BaseException as exc:
        _write(
            directory / "failure.json",
            {
                "stage": stage,
                "error_type": type(exc).__name__,
                "completed_steps_unverified": len(metrics),
                "adapter_quarantined": True,
                **NO_AUTHORITY,
            },
        )
        raise


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        with contextlib.redirect_stdout(sys.stderr):
            result = respond(raw)
        print(canonical(result))
        return 0
    except Exception as exc:
        print(f"synthetic_gpu_worker_failed:{type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
