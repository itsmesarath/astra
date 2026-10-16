"""Explicit one-call synthetic Qwen inference measurement, never a trading/training loop."""

import argparse
import contextlib
import sys
import time
from decimal import Decimal
from pathlib import Path

from ai_trader.models._local_review_worker import decode_request, respond
from ai_trader.models.local_checkpoint import canonical, digest, strict_json
from ai_trader.models.local_reviewer import (
    MAX_REQUEST_BYTES,
    LocalReviewerConfig,
    LocalReviewError,
    _exchange,
    build_request,
)
from ai_trader.models.review_contracts import LEGACY_V1
from ai_trader.research.council import Evidence, ResearchSnapshot, parse_role_report


def _measurement_worker(raw):
    config, request = decode_request(raw)
    if config.backend != "transformers" or config.device != "cuda":
        raise ValueError("This measurement requires explicit CUDA Transformers inference.")
    # These optional imports happen only in the isolated child, never in the core parent.
    import psutil
    import torch

    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    response = respond(raw)
    torch.cuda.synchronize()
    memory = psutil.Process().memory_info()
    return {
        **response,
        "metrics": {
            "inference_and_hashing_seconds": time.monotonic() - started,
            "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
            "process_peak_working_set_bytes": getattr(memory, "peak_wset", None),
            "torch_version": torch.__version__,
            "cuda_version": torch.version.cuda,
        },
    }


def run_smoke(config, *, enable_local_inference=False):
    if enable_local_inference is not True:
        raise ValueError("Explicit local inference opt-in required.")
    if (
        type(config) is not LocalReviewerConfig
        or config.backend != "transformers"
        or config.model_id != "Qwen/Qwen3-4B-Base"
        or config.device != "cuda"
        or config.source_session != "synthetic-qwen-smoke"
        or config.max_calls != 1
        or config.review_contract != LEGACY_V1
    ):
        raise ValueError("Explicit single-call CUDA Base-model smoke configuration required.")
    snapshot = ResearchSnapshot(
        "BTCUSDT",
        1000,
        tuple(
            Evidence(eid, "BTCUSDT", config.source_session, metric, Decimal(value), 900, 950)
            for eid, metric, value in (
                ("cvd", "rolling_cvd_btc", "2.5"),
                ("imbalance", "top5_bid_ask_imbalance", "0.15"),
                ("cost", "estimated_round_trip_cost_bps", "12"),
            )
        ),
    )
    request = build_request(config, "analyst", snapshot, ())
    result = {
        "schema_version": 1,
        "kind": "synthetic_qwen_smoke",
        "request_sha256": digest(request),
        "configuration": request["configuration"],
        "prompt_sha256": request["prompt_sha256"],
        "generation_completed": False,
        "report_valid": False,
        "raw_response": None,
        "metrics": None,
        "orders": 0,
        "training_started": False,
        "promotion_allowed": False,
    }
    started = time.monotonic()
    try:
        stdout = _exchange(
            [str(config.python_executable), "-I", "-m", "ai_trader.models.qwen_smoke", "--worker"],
            request,
            min(config.timeout_ms, config.reply_ttl_ms),
        )
        response = strict_json(stdout)
        if (
            type(response) is not dict
            or set(response) != {"request_sha256", "raw_response", "metrics"}
            or response["request_sha256"] != digest(request)
            or type(response["raw_response"]) is not str
            or len(response["raw_response"]) > 2048
            or type(response["metrics"]) is not dict
        ):
            raise ValueError("Invalid measurement response.")
        result.update(
            generation_completed=True,
            raw_response=response["raw_response"],
            metrics=response["metrics"],
        )
        parse_role_report(response["raw_response"], "analyst", snapshot)
        if (time.monotonic() - started) * 1000 >= config.reply_ttl_ms:
            raise LocalReviewError("expired_review")
        result.update(report_valid=True, status="validated_advisory")
    except Exception as error:
        result["status"] = (
            str(error) if type(error) is LocalReviewError else "invalid_measurement_or_report"
        )
    result.update(elapsed_seconds=time.monotonic() - started, available_at_ns=time.time_ns())
    return result


def main():
    if sys.argv[1:] == ["--worker"]:
        try:
            raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
            with contextlib.redirect_stdout(sys.stderr):
                response = _measurement_worker(raw)
            print(canonical(response))
            return 0
        except Exception:
            print("local_smoke_worker_failed", file=sys.stderr)
            return 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--python-executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enable-local-inference", action="store_true", required=True)
    args = parser.parse_args()
    config = LocalReviewerConfig(
        "synthetic-qwen-smoke",
        backend="transformers",
        model_id="Qwen/Qwen3-4B-Base",
        checkpoint_path=args.checkpoint,
        checkpoint_sha256=args.checkpoint_sha256,
        python_executable=args.python_executable,
        device="cuda",
        timeout_ms=120000,
        reply_ttl_ms=120000,
        max_calls=1,
    )
    # Refuse an existing report BEFORE inference, rather than accidentally repeating a run.
    with args.output.open("x", encoding="utf-8") as stream:
        result = run_smoke(config, enable_local_inference=args.enable_local_inference)
        stream.write(canonical(result) + "\n")
    print(canonical(result))
    return 0 if result["report_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
