"""Private offline worker for the fixed 6E forecast trial; no raw/evaluation readers."""

import contextlib
import os
import sys
from importlib.metadata import version
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, digest, strict_json
from ai_trader.training._qwen_gpu_smoke_worker import (
    create_backend,
    resources,
    verify_frozen_parameters,
)
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import _event, _write, runtime_manifest
from ai_trader.training.lora_backend import trainable_adapters
from ai_trader.training.six_e_lora_trial import (
    KIND,
    MAX_REQUEST_BYTES,
    NO_AUTHORITY,
    STEPS,
    encode_selection,
    finite_nonnegative,
    token_plan,
    validate_request,
)


def respond(raw: bytes) -> dict:
    if type(raw) is not bytes or len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("Bounded trial request required")
    request = strict_json(raw)
    rows, pins, runtime = validate_request(request, verify_assets=True)
    if (
        request["python_executable"] != str(Path(sys.executable).resolve())
        or runtime_manifest() != runtime
        or any(version(name) != expected for name, expected in pins.items())
    ):
        raise ValueError("Worker runtime/installed versions differ")
    if any(
        os.environ.get(name) != "1"
        for name in (
            "HF_HUB_OFFLINE",
            "TRANSFORMERS_OFFLINE",
            "HF_HUB_DISABLE_TELEMETRY",
            "DO_NOT_TRACK",
        )
    ):
        raise ValueError("Offline research worker environment required")
    directory = Path(request["output_dir"])
    if (
        directory.is_symlink()
        or not directory.is_dir()
        or {p.name for p in directory.iterdir()} != {"request.json"}
    ):
        raise ValueError("Fresh supervisor-owned trial directory required")
    saved = directory / "request.json"
    if (
        saved.is_symlink()
        or saved.stat().st_size > MAX_REQUEST_BYTES
        or strict_json(saved.read_bytes()) != request
    ):
        raise ValueError("Persisted trial request differs")
    encode = token_plan.load_tokenizer(Path(request["tokenizer_json"]), request["tokenizer_sha256"])
    specs, records = encode_selection(request, rows, encode)
    if specs != request["selection"]:
        raise ValueError("Tokenized records differ from frozen supervisor selection")
    stage, metrics = "native_initialization", []
    try:
        with (directory / "steps.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            _event(stream, {"event": "native_initialization_started"})
            backend = create_backend(request)
            verify_frozen_parameters(backend)
            parameters = sum(p.numel() for p in trainable_adapters(backend.model))
            _event(stream, {"event": "native_initialization_completed"})
            for step, (spec, record) in enumerate(zip(specs, records, strict=True), 1):
                stage = f"optimizer_step_{step}"
                event = {
                    "step": step,
                    "case_id": spec["case_id"],
                    "record_sha256": spec["record_sha256"],
                }
                _event(stream, {"event": "step_intent", **event})
                metric = backend.step(record)
                _fields(metric, ("loss", "gradient_norm"))
                finite_nonnegative(metric.values())
                verify_frozen_parameters(backend)
                metrics.append(metric)
                _event(stream, {"event": "step_completed", **event, **metric})
            stage = "save_reload"
            _event(stream, {"event": "save_reload_started"})
            reload = backend.save_reload(directory / "adapter", records[0])
            if any(
                p.requires_grad or p.grad is not None or p.device.type != "cuda"
                for p in backend.model.parameters()
            ):
                raise ValueError("Reload must be CUDA inference-only without gradients")
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


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        with contextlib.redirect_stdout(sys.stderr):
            result = respond(raw)
        print(canonical(result))
        return 0
    except Exception as exc:
        print(f"six_e_lora_worker_failed:{type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
