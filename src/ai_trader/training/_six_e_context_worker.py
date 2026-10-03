"""Private selected-example worker; never opens datasets, check rows or old adapters."""

import contextlib
import os
import sys
import time
from importlib.metadata import version
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, digest, strict_json
from ai_trader.training import six_e_context_lora as trial
from ai_trader.training._qwen_gpu_smoke_worker import (
    create_backend,
    resources,
    verify_frozen_parameters,
)
from ai_trader.training.advisory_training_run import _event, _write, runtime_manifest
from ai_trader.training.lora_backend import trainable_adapters


def respond(raw: bytes) -> dict:
    started = time.monotonic()
    if type(raw) is not bytes or len(raw) > trial.MAX_REQUEST_BYTES:
        raise ValueError("Bounded selected-example request required")
    packet = strict_json(raw)
    pins, runtime = trial.validate_packet(packet)
    if (
        packet["python_executable"] != str(Path(sys.executable).resolve())
        or runtime_manifest() != runtime
        or any(version(name) != expected for name, expected in pins.items())
        or any(
            os.environ.get(name) != "1"
            for name in (
                "HF_HUB_OFFLINE",
                "TRANSFORMERS_OFFLINE",
                "HF_HUB_DISABLE_TELEMETRY",
                "DO_NOT_TRACK",
            )
        )
    ):
        raise ValueError("Pinned interpreter, installed runtime and offline environment required")
    directory = Path(packet["output_dir"])
    if (
        directory.is_symlink()
        or not directory.is_dir()
        or {p.name for p in directory.iterdir()} != {"request.json"}
    ):
        raise ValueError("Fresh supervisor-owned output required")
    saved = directory / "request.json"
    if saved.is_symlink() or saved.stat().st_size > trial.MAX_REQUEST_BYTES + 1:
        raise ValueError("Persisted native request differs")
    with saved.open("rb") as stream:
        persisted = stream.read(trial.MAX_REQUEST_BYTES + 2)
    if len(persisted) > trial.MAX_REQUEST_BYTES + 1 or strict_json(persisted) != packet:
        raise ValueError("Persisted native request differs")
    encode = trial.tokens.token_plan.load_tokenizer(
        Path(packet["tokenizer_json"]), packet["tokenizer_sha256"]
    )
    records = trial.token_records(packet, encode)
    stage, metrics = "native_initialization", []

    def guard_time():
        if time.monotonic() - started >= trial.TIMEOUT_MS / 1000:
            raise TimeoutError("Bounded native training deadline exhausted")

    try:
        with (directory / "steps.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            guard_time()
            _event(stream, {"event": "native_initialization_started"})
            backend = create_backend(packet)
            verify_frozen_parameters(backend)
            parameters = sum(p.numel() for p in trainable_adapters(backend.model))
            if not 1 <= parameters <= trial.MAX_TRAINABLE_PARAMETERS:
                raise ValueError("Trainable adapter parameter budget exceeded")
            _event(stream, {"event": "native_initialization_completed"})
            for step, (item, record) in enumerate(
                zip(packet["selection"], records, strict=True), 1
            ):
                guard_time()
                stage = f"optimizer_step_{step}"
                binding = trial.binding(step, item)
                _event(stream, {"event": "step_intent", **binding})
                metric = backend.step(record)
                trial._fields(metric, ("loss", "gradient_norm"))
                trial.finite_nonnegative(metric.values())
                verify_frozen_parameters(backend)
                metrics.append(metric)
                _event(stream, {"event": "step_completed", **binding, **metric})
            guard_time()
            stage = "save_reload"
            _event(stream, {"event": "save_reload_started"})
            reload = backend.save_reload(directory / "adapter", records[0])
            if any(
                p.requires_grad or p.grad is not None or p.device.type != "cuda"
                for p in backend.model.parameters()
            ):
                raise ValueError("Fresh reload must be CUDA inference-only without gradients")
            evidence = resources(backend)
            guard_time()
            _event(stream, {"event": "save_reload_completed"})
        return {
            "kind": trial.KIND,
            "request_sha256": digest(packet),
            "steps": trial.STEPS,
            "summary": trial.summarize(metrics),
            "journal": trial.journal_info(directory / "steps.jsonl"),
            "runtime": runtime_manifest(),
            "resources": evidence,
            "trainable_parameters": parameters,
            "frozen_parameter_guards_passed": True,
            "reload": reload,
            **trial.FLAGS,
        }
    except BaseException as exc:
        _write(
            directory / "failure.json",
            {
                "stage": stage,
                "error_type": type(exc).__name__,
                "completed_steps_unverified": len(metrics),
                "adapter_quarantined": True,
                **trial.FLAGS,
            },
        )
        raise


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(trial.MAX_REQUEST_BYTES + 1)
        with contextlib.redirect_stdout(sys.stderr):
            result = respond(raw)
        print(canonical(result))
        return 0
    except Exception as exc:
        print(f"six_e_context_worker_failed:{type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
