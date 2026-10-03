"""Private full-check inference: bounded owned feature sidecar, never targets or datasets."""

import contextlib
import os
import sys
import time
from importlib.metadata import version
from pathlib import Path

from ai_trader.models._six_e_forecast_worker import InferenceBackend, InferenceBoundaryError
from ai_trader.models.local_checkpoint import canonical, digest, strict_json
from ai_trader.research import six_e_context_eval as evaluation
from ai_trader.training._qwen_gpu_smoke_worker import resources
from ai_trader.training.advisory_training_plan import load_tokenizer
from ai_trader.training.advisory_training_run import _event, _write, runtime_manifest


def create_backend(packet):
    return InferenceBackend(packet)


def bounded_event(stream, value, *, limit=evaluation.controls.MAX_BYTES):
    raw_size = len(canonical(value).encode()) + 1
    if (
        type(limit) is not int
        or not 1 <= limit <= evaluation.controls.MAX_BYTES
        or raw_size > evaluation.controls.MAX_LINE
        or stream.tell() + raw_size > limit
    ):
        raise ValueError("Durable output byte budget exhausted before write")
    _event(stream, value)


def respond(raw: bytes) -> dict:
    started = time.monotonic()
    if type(raw) is not bytes or len(raw) > evaluation.MAX_PACKET_BYTES:
        raise ValueError("Bounded feature-only inference metadata required")
    packet = strict_json(raw)
    pins, runtime = evaluation.validate_packet(packet)
    if (
        packet["python_executable"] != str(Path(sys.executable).resolve())
        or runtime_manifest() != runtime
        or any(version(name) != pin for name, pin in pins.items())
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
        raise ValueError(
            "Pinned installed GPU runtime/interpreter and offline environment required"
        )
    directory = Path(packet["output_dir"])
    if (
        directory.is_symlink()
        or not directory.is_dir()
        or {p.name for p in directory.iterdir()} != {"request.json", "features.jsonl"}
    ):
        raise ValueError("Fresh supervisor-owned inference output required")
    info = evaluation.controls.file_info(
        directory / "request.json", evaluation.MAX_PACKET_BYTES + 1
    )
    if info["bytes"] > evaluation.MAX_PACKET_BYTES + 1:
        raise ValueError("Saved request byte bound exceeded")
    with (directory / "request.json").open("rb") as stream:
        saved = stream.read(evaluation.MAX_PACKET_BYTES + 2)
    if len(saved) > evaluation.MAX_PACKET_BYTES + 1 or strict_json(saved) != packet:
        raise ValueError("Persisted inference request changed")
    selection = evaluation.read_selection(packet)
    encode = load_tokenizer(Path(packet["tokenizer_json"]), packet["tokenizer_sha256"])
    records = []
    for item in selection:
        ids = encode(item["prompt"])
        if (
            type(ids) is not list
            or len(ids) != item["prompt_tokens"]
            or digest(ids) != item["prompt_ids_sha256"]
            or any(type(t) is not int or not 0 <= t < 151936 or t == 151643 for t in ids)
        ):
            raise ValueError("Original exact prompt tokenization required; no truncation/EOS")
        records.append(ids)
    stage, completed = "native_initialization", 0

    def deadline():
        if time.monotonic() - started >= evaluation.TIMEOUT_MS / 1000:
            raise TimeoutError("Full comparison worker deadline exhausted")

    try:
        with (
            (directory / "events.jsonl").open("x", encoding="utf-8", newline="\n") as events,
            (directory / "predictions.jsonl").open(
                "x", encoding="utf-8", newline="\n"
            ) as predictions,
        ):
            deadline()
            bounded_event(events, {"event": "native_initialization_started"})
            backend = create_backend(packet)
            backend.guard()
            bounded_event(events, {"event": "native_initialization_completed"})
            for item, ids in zip(selection, records, strict=True):
                for mode in evaluation.legacy.MODES:
                    deadline()
                    binding = evaluation.legacy.binding(completed + 1, mode, item)
                    stage = f"prediction_{completed + 1}"
                    bounded_event(events, {"event": "prediction_intent", **binding})
                    prediction = {**binding, **backend.predict(ids, mode)}
                    evaluation.legacy.validate_prediction(prediction)
                    backend.guard()
                    bounded_event(predictions, prediction)
                    bounded_event(
                        events,
                        {
                            "event": "prediction_completed",
                            **binding,
                            "prediction_sha256": digest(prediction),
                        },
                    )
                    completed += 1
            stage = "post_inference_pins"
            evaluation.validate_packet(packet)
            if evaluation.read_selection(packet) != selection:
                raise ValueError("Frozen feature sidecar changed during inference")
            evidence = resources(backend)
            evaluation.validate_resources(evidence)
            deadline()
            bounded_event(events, {"event": "inference_completed"})
        return {
            "kind": evaluation.KIND,
            "request_sha256": digest(packet),
            "completed_calls": completed,
            "parameters_frozen": True,
            "runtime": runtime_manifest(),
            "resources": evidence,
            "files": {
                name: evaluation.controls.file_info(directory / name)
                for name in ("predictions.jsonl", "events.jsonl")
            },
            **evaluation.FLAGS,
        }
    except BaseException as exc:
        _write(
            directory / "failure.json",
            {
                "stage": stage,
                "error_type": type(exc).__name__,
                "error_code": exc.code
                if isinstance(exc, InferenceBoundaryError)
                else "native_runtime_unclassified",
                "completed_calls_unverified": completed,
                "adapter_quarantined": True,
                **evaluation.FLAGS,
            },
        )
        raise


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(evaluation.MAX_PACKET_BYTES + 1)
        with contextlib.redirect_stdout(sys.stderr):
            result = respond(raw)
        print(canonical(result))
        return 0
    except Exception as exc:
        print(f"six_e_context_eval_failed:{type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
