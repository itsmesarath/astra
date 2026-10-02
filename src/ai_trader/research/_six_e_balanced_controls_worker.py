"""Private CPU comparison: frozen coefficients and selected prompts only; never fit."""

import contextlib
import os
import sys
import time
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, digest, strict_json
from ai_trader.research import six_e_balanced_eval as evaluation
from ai_trader.training.advisory_training_run import _event, _write


def respond(raw: bytes) -> dict:
    started = time.monotonic()
    if type(raw) is not bytes or len(raw) > evaluation.MAX_BYTES:
        raise ValueError("Bounded CPU selected-input request required")
    packet = strict_json(raw)
    evaluation.validate_cpu_packet(packet)
    if (
        packet["cpu_runtime"] != evaluation.balance.runtime()
        or packet["cpu_runtime"]["python_executable"] != str(Path(sys.executable).resolve())
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
        raise ValueError("Original CPU runtime and offline environment required")
    directory = Path(packet["output_dir"])
    if not directory.is_dir() or {p.name for p in directory.iterdir()} != {"request.json"}:
        raise ValueError("Fresh supervisor-owned CPU output required")
    if canonical(
        evaluation.lines(
            directory / "request.json", evaluation.file_info(directory / "request.json")
        )
    ) != canonical([packet]):
        raise ValueError("Persisted CPU request differs")
    stage, completed = "control_prediction", 0

    def deadline():
        if time.monotonic() - started >= evaluation.CPU_TIMEOUT_MS / 1000:
            raise TimeoutError("CPU comparison deadline exhausted")

    try:
        features = [evaluation.balance.feature_values(item) for item in packet["selection"]]
        predictions = {}
        for name in evaluation.balance.MODES:
            deadline()
            probabilities = evaluation.balance.predict(packet["models"][name], features)
            predictions[name] = probabilities.argmax(axis=1).tolist()
        with (directory / "predictions.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for index, item in enumerate(packet["selection"]):
                deadline()
                for name in evaluation.balance.MODES:
                    row = {
                        "case_id": item["case_id"],
                        "input_sha256": item["input_sha256"],
                        "control": name,
                        "forecast": evaluation.balance.forecast(
                            evaluation.balance.STATES[predictions[name][index]]
                        ),
                    }
                    _event(stream, row)
                    completed += 1
        stage = "post_control_pins"
        evaluation.validate_cpu_packet(packet)
        if (
            digest(packet["models"]) != packet["models_sha256"]
            or evaluation.balance.runtime() != packet["cpu_runtime"]
        ):
            raise ValueError("Frozen CPU coefficients/runtime changed")
        deadline()
        return {
            "kind": evaluation.CPU_KIND,
            "request_sha256": digest(packet),
            "cpu_runtime": evaluation.balance.runtime(),
            "models_sha256": packet["models_sha256"],
            "completed_predictions": completed,
            "predictions": evaluation.file_info(directory / "predictions.jsonl"),
            **evaluation.FLAGS,
        }
    except BaseException as exc:
        _write(
            directory / "failure.json",
            {
                "stage": stage,
                "error_type": type(exc).__name__,
                "completed_predictions_unverified": completed,
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
        print(f"six_e_balanced_controls_failed:{type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
