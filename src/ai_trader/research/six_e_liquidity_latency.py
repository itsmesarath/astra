"""Bounded synthetic CPU prediction timing, never feed or execution latency."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

from ai_trader.research import six_e_liquidity_status as status
from ai_trader.training import six_e_liquidity as rules
from ai_trader.training import standardize

WARMUP, REPETITIONS, MAX_SECONDS = 10, 1000, 30


def prediction_source_pins() -> dict:
    return {
        Path(module.__file__).name: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        for module in (rules, standardize)
    }


def measure(model: rules.Model) -> dict:
    """Exactly 1,010 synthetic one-row calls; no fitting, targets or scores."""
    x = np.zeros((1, len(rules.FEATURES)), dtype=np.float64)
    started = time.perf_counter()
    timings = []
    for i in range(WARMUP + REPETITIONS):
        if time.perf_counter() - started > MAX_SECONDS:
            raise TimeoutError("CPU timing deadline exceeded; no partial latency result")
        before = time.perf_counter_ns()
        prediction = model.predict(x)
        elapsed = time.perf_counter_ns() - before
        if prediction.shape != (1, 3) or not np.isfinite(prediction).all():
            raise ValueError("CPU timing received invalid predictions")
        if i >= WARMUP:
            timings.append(elapsed / 1_000_000)
    if time.perf_counter() - started > MAX_SECONDS:
        raise TimeoutError("CPU timing deadline exceeded; no partial latency result")
    return {
        "warmup_calls": WARMUP,
        "measured_calls": len(timings),
        "input": "One synthetic all-zero float64 row of 37 columns; not a market snapshot",
        "prediction_milliseconds": {
            "minimum": min(timings),
            "median": float(np.median(timings)),
            "p95": float(np.quantile(timings, 0.95)),
            "p99": float(np.quantile(timings, 0.99)),
            "maximum": max(timings),
        },
        "limitations": "Measures only Model.predict including its numerical guards and "
        "standardization; no raw decoding, feature construction, policy, risk, journal, "
        "feed, broker, order or Qwen timing. Shared-computer load can affect measurements. "
        "Not an end-to-end SLA, profitability evidence or permission to alter delays.",
        "end_to_end_latency_measured": False,
        "fixed_entry_exit_delay_changed": False,
        **dict.fromkeys(status.FALSE_FLAGS, False),
        "cpu_training": False,
    }


def benchmark(
    root: Path, registration: Path, pin: str, output: Path, completion_pin: str, destination: Path
) -> dict:
    destination = status._inside(root, destination, "data/processed")
    if destination.suffix != ".json" or destination.is_relative_to(output.resolve()):
        raise ValueError("CPU timing belongs in separate JSON, not the owned evaluation")
    if destination.exists():
        raise FileExistsError("CPU timing output is already claimed")
    checked = status.snapshot(root, registration, pin, output, completion_pin)
    if (
        checked["status"] != "pinned_receipt_matches_metadata_not_revalidated"
        or checked["phase"] != "cpu_evaluation"
    ):
        raise ValueError("CPU timing requires complete pinned candidate metadata and receipt")
    completed, actual = status._json(root, output / "completion.json")
    if actual != completion_pin:
        raise ValueError("CPU timing completion pin changed")
    code_pins = prediction_source_pins()
    if any(completed["implementation_sha256"].get(k) != v for k, v in code_pins.items()):
        raise ValueError("CPU timing prediction or standardization source differs")
    saved, model_pin = status._json(root, output / "model.json", bound=1024**2)
    if (
        model_pin != completed["model_sha256"]
        or saved["flags"] != completed["flags"]
        or saved["fit_accounting"] != completed["fit_accounting"]
    ):
        raise ValueError("CPU timing original candidate pin or accounting differs")
    result = {
        "status": "completed_synthetic_cpu_timing_not_execution_evidence",
        "registration_sha256": pin,
        "evaluation_completion_sha256": completion_pin,
        "model_sha256": model_pin,
        "timing_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "prediction_source_sha256": code_pins,
        "numpy_version": np.__version__,
        "measurement": measure(rules.Model(**saved["model"])),
    }
    if prediction_source_pins() != code_pins:
        raise ValueError("CPU timing prediction source differs after measurement")
    if (
        status.snapshot(root, registration, pin, output, completion_pin) != checked
        or status._json(root, output / "model.json", bound=1024**2)[1] != model_pin
    ):
        raise ValueError("CPU timing metadata or candidate changed during measurement")
    raw = (
        json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    )
    if len(raw) > status.MAX_JSON:
        raise ValueError("CPU timing output exceeds bound")
    with destination.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {
        "status": result["status"],
        "sha256": hashlib.sha256(raw).hexdigest(),
        "measurement": result["measurement"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", required=True, type=Path)
    parser.add_argument("--registration-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--completion-sha256", required=True)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            benchmark(
                Path(__file__).resolve().parents[3],
                args.registration,
                args.registration_sha256,
                args.output,
                args.completion_sha256,
                args.destination,
            )
        )
    )


if __name__ == "__main__":
    main()
