"""Opt-in, finite public capture retries, with a new snapshot/session on every attempt."""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from uuid import uuid4

from ai_trader.ingestion.capture_failure import failure_details, safe_error_type
from ai_trader.ingestion.collect_combined import (
    DEFAULT_LIMITS,
    CaptureInterrupted,
    CaptureLimits,
    _validate_seconds,
    collect,
)


async def capture_with_retries(
    *,
    manifest_path: Path,
    seconds: int,
    max_attempts: int = 1,
    retry_delay_seconds: int = 2,
    limits: CaptureLimits = DEFAULT_LIMITS,
    collector=None,
    sleeper=None,
) -> tuple[Path, int, int]:
    """Create a NEW audit file; retain all partials. No restart/overwrite or hidden loop.

    At most five attempts of at most one hour, plus connection/close, HTTP worker
    cleanup and finite local validation. OS stalls aren't hard real-time bounded.
    This is not an unattended campaign.
    Disk, quota and unexpected failures stop immediately, as does cancellation.
    """
    _validate_seconds(seconds)
    if type(max_attempts) is not int or not 1 <= max_attempts <= 5:
        raise ValueError("max_attempts must be an integer in [1, 5].")
    if type(retry_delay_seconds) is not int or not 0 <= retry_delay_seconds <= 60:
        raise ValueError("retry_delay_seconds must be an integer in [0, 60].")
    if type(limits) is not CaptureLimits:
        raise ValueError("Typed capture limits required.")
    collector, sleeper = collector or collect, sleeper or asyncio.sleep
    manifest_path = Path(manifest_path)
    attempt_paths = [
        manifest_path.parent / f"btcusdt_{uuid4().hex}_attempt_{n}.jsonl"
        for n in range(1, max_attempts + 1)
    ]
    with manifest_path.open("x", encoding="utf-8", newline="\n") as audit:

        def record(status, **values):
            audit.write(json.dumps({"status": status, "at_ns": time.time_ns(), **values}) + "\n")
            audit.flush()
            os.fsync(audit.fileno())

        record(
            "started",
            seconds=seconds,
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
            limits={name: getattr(limits, name) for name in limits.__dataclass_fields__},
        )
        attempt = 0
        try:
            for next_attempt, path in enumerate(attempt_paths, 1):
                if next_attempt > 1:
                    await sleeper(retry_delay_seconds)
                attempt = next_attempt
                record(
                    "attempt_started",
                    attempt=attempt,
                    capture_path=str(path.resolve()),
                    partial_path=str(path.with_suffix(".jsonl.partial").resolve()),
                )
                try:
                    result = await collector(seconds, output_path=path, limits=limits)
                except CaptureInterrupted as error:
                    record(
                        "attempt_failed",
                        attempt=attempt,
                        error_type=safe_error_type(error),
                        failure=failure_details(error),
                    )
                    if attempt == max_attempts:
                        raise
                    continue
                if result[0] != path:
                    raise ValueError("Collector returned an unexpected capture path.")
                record(
                    "completed",
                    attempt=attempt,
                    capture_path=str(path.resolve()),
                    trade_events=result[1],
                    depth_events=result[2],
                )
                return result
        except asyncio.CancelledError as error:
            record("cancelled", attempt=attempt, failure=failure_details(error))
            raise
        except Exception as error:
            record(
                "failed",
                attempt=attempt,
                error_type=safe_error_type(error),
                failure=failure_details(error),
            )
            raise
    raise AssertionError("Attempt budget exhausted without a terminal outcome.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="New audit JSONL file.")
    parser.add_argument("--seconds", type=int, required=True)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--retry-delay-seconds", type=int, default=2)
    args = parser.parse_args()
    path, trades, depths = asyncio.run(
        capture_with_retries(
            manifest_path=args.manifest,
            seconds=args.seconds,
            max_attempts=args.attempts,
            retry_delay_seconds=args.retry_delay_seconds,
        )
    )
    print(
        json.dumps(
            {
                "capture": str(path.resolve()),
                "trade_events": trades,
                "depth_events": depths,
                "mode": "public_data_only",
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": safe_error_type(error),
                    "failure": failure_details(error),
                    "message": "Stopped; inspect the audit and retained partial files.",
                }
            )
        )
        raise SystemExit(1) from None
