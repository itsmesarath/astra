"""Private paired 80-case inference using the immutable frozen inference backend."""

import contextlib
import os
import sys
import time
from importlib.metadata import version
from pathlib import Path

from ai_trader.models._six_e_forecast_worker import InferenceBackend, InferenceBoundaryError
from ai_trader.models.local_checkpoint import canonical, digest, strict_json
from ai_trader.research import six_e_balanced_eval as evaluation
from ai_trader.training._qwen_gpu_smoke_worker import resources
from ai_trader.training.advisory_training_plan import load_tokenizer
from ai_trader.training.advisory_training_run import _event, _write, runtime_manifest


def create_backend(packet):
    return InferenceBackend(packet)


def respond(raw: bytes) -> dict:
    started = time.monotonic()
    if type(raw) is not bytes or len(raw) > evaluation.MAX_BYTES:
        raise ValueError("Bounded feature-only request required")
    packet = strict_json(raw)
    pins, runtime = evaluation.validate_gpu_packet(packet)
    if (
        packet["python_executable"] != str(Path(sys.executable).resolve())
        or runtime_manifest() != runtime
        or any(version(name) != pin for name, pin in pins.items())
        or any(
            os.environ.get(k) != "1"
            for k in (
                "HF_HUB_OFFLINE",
                "TRANSFORMERS_OFFLINE",
                "HF_HUB_DISABLE_TELEMETRY",
                "DO_NOT_TRACK",
            )
        )
    ):
        raise ValueError("Pinned installed GPU runtime and offline environment required")
    directory = Path(packet["output_dir"])
    if not directory.is_dir() or {p.name for p in directory.iterdir()} != {"request.json"}:
        raise ValueError("Fresh supervisor-owned output required")
    if canonical(
        evaluation.lines(
            directory / "request.json", evaluation.file_info(directory / "request.json")
        )
    ) != canonical([packet]):
        raise ValueError("Persisted request differs")
    encode = load_tokenizer(Path(packet["tokenizer_json"]), packet["tokenizer_sha256"])
    records = [encode(item["prompt"]) for item in packet["selection"]]
    if any(
        type(ids) is not list
        or len(ids) != item["prompt_tokens"]
        or any(type(t) is not int or not 0 <= t < 151936 or t == 151643 for t in ids)
        for item, ids in zip(packet["selection"], records, strict=True)
    ):
        raise ValueError("Original bounded prompt tokenization required, without truncation/EOS")
    stage, completed = "native_initialization", 0

    def deadline():
        if time.monotonic() - started >= evaluation.TIMEOUT_MS / 1000:
            raise TimeoutError("GPU comparison deadline exhausted")

    try:
        with (
            (directory / "events.jsonl").open("x", encoding="utf-8", newline="\n") as events,
            (directory / "predictions.jsonl").open(
                "x", encoding="utf-8", newline="\n"
            ) as predictions,
        ):
            deadline()
            _event(events, {"event": "native_initialization_started"})
            backend = create_backend(packet)
            backend.guard()
            _event(events, {"event": "native_initialization_completed"})
            for item, ids in zip(packet["selection"], records, strict=True):
                for mode in evaluation.legacy.MODES:
                    deadline()
                    current = evaluation.legacy.binding(completed + 1, mode, item)
                    stage = f"prediction_{completed + 1}"
                    _event(events, {"event": "prediction_intent", **current})
                    prediction = {**current, **backend.predict(ids, mode)}
                    evaluation.legacy.validate_prediction(prediction)
                    backend.guard()
                    _event(predictions, prediction)
                    _event(
                        events,
                        {
                            "event": "prediction_completed",
                            **current,
                            "prediction_sha256": digest(prediction),
                        },
                    )
                    completed += 1
            stage = "post_inference_pins"
            evaluation.validate_gpu_packet(packet)
            evidence = resources(backend)
            deadline()
            _event(events, {"event": "inference_completed"})
        return {
            "kind": evaluation.KIND,
            "request_sha256": digest(packet),
            "completed_calls": completed,
            "parameters_frozen": True,
            "runtime": runtime_manifest(),
            "resources": evidence,
            "files": {
                name: evaluation.file_info(directory / name)
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
        raw = sys.stdin.buffer.read(evaluation.MAX_BYTES + 1)
        with contextlib.redirect_stdout(sys.stderr):
            result = respond(raw)
        print(canonical(result))
        return 0
    except Exception as exc:
        print(f"six_e_balanced_eval_failed:{type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
