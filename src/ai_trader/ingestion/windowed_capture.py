"""Explicitly opted-in, single-use UTC-window public capture; never training or orders."""

import argparse
import asyncio
import hashlib
import os
import time
from pathlib import Path

from ai_trader.ingestion.capture_failure import (
    failure_details,
    failure_stage,
    mark_failure,
    safe_error_type,
)
from ai_trader.ingestion.capture_schedule import (
    CONNECTION_ALLOWANCE_NS,
    RUNTIME,
    load_schedule,
    validate_completion_times,
)
from ai_trader.ingestion.collect_combined import CaptureInterrupted, collect
from ai_trader.ingestion.planned_capture import (
    AUTHORITY,
    NS,
    _check_binding,
    _collect_slot,
    _integer,
    write_new,
)
from ai_trader.models.local_checkpoint import canonical

RECEIPT_KIND = "windowed_capture_receipt_v1"


def _refuse(code):
    raise mark_failure(CaptureInterrupted("Windowed acquisition stopped; retain evidence."), code)


class _Clock:
    """One process-local monotonic origin; wall-clock adjustments never extend a deadline."""

    def __init__(self, wall, monotonic, prepared_at_ns):
        self.wall, self.monotonic = wall, monotonic
        self.at_ns, self.elapsed_ns, self.last_perf = prepared_at_ns, 0, None
        self.origin_wall, self.origin_perf = None, None
        self.sample()
        if self.at_ns <= prepared_at_ns:
            _refuse("schedule.invalid_clock")

    def sample(self):
        with failure_stage("schedule.invalid_clock"):
            wall, perf = self.wall(), self.monotonic()
            _integer(wall, 1, 2**63 - 1)
            _integer(perf, 0, 2**63 - 1)
        if wall < self.at_ns or (self.last_perf is not None and perf < self.last_perf):
            _refuse("schedule.clock_regression")
        if self.origin_wall is None:
            self.origin_wall, self.origin_perf = wall, perf
        self.at_ns, self.last_perf = wall, perf
        self.elapsed_ns = perf - self.origin_perf
        return wall

    def relative(self, wall_deadline):
        return wall_deadline - self.origin_wall

    def check_dispatch(self, window):
        self.sample()
        if self.at_ns > window["last_dispatch_at_ns"] or self.elapsed_ns > self.relative(
            window["last_dispatch_at_ns"]
        ):
            _refuse("schedule.missed_window")
        return self.at_ns >= window["open_at_ns"] and self.elapsed_ns >= self.relative(
            window["open_at_ns"]
        )


async def _wait_window(window, clock, sleeper):
    while not clock.check_dispatch(window):
        delay_ns = max(
            window["open_at_ns"] - clock.at_ns,
            clock.relative(window["open_at_ns"]) - clock.elapsed_ns,
        )
        before = clock.elapsed_ns
        await sleeper(max(0.001, min(RUNTIME["wait_poll_ns"], delay_ns) / NS))
        clock.sample()
        if clock.elapsed_ns <= before:
            _refuse("schedule.clock_stalled")


def _check_completion_deadline(window, clock):
    clock.sample()
    end = window["latest_capture_end_ns"] + RUNTIME["completion_grace_ns"]
    if clock.at_ns > end or clock.elapsed_ns > clock.relative(end):
        _refuse("schedule.completion_timeout")


async def _bounded_capture(operation, window, clock):
    """Cooperative timeout/clock watchdog, including collector cleanup and verification.

    A stuck OS call/event loop cannot be killed here. The claimed directory prevents
    implicit restart; cancellation is drained to avoid an orphaned receiver task.
    """
    task = asyncio.create_task(operation)
    try:
        while True:
            _check_completion_deadline(window, clock)
            if task.done():
                return task.result()
            await asyncio.wait((task,), timeout=RUNTIME["wait_poll_ns"] / NS)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def _receipt(schedule, pin, clock):
    return {
        "schema_version": 1,
        "kind": RECEIPT_KIND,
        "schedule_sha256": pin,
        "campaign_id": schedule["acquisition"]["campaign_id"],
        "clock_origin_wall_ns": clock.origin_wall,
        "status": "running",
        "sessions": [{**a, "status": "not_started"} for a in schedule["acquisition"]["sessions"]],
        "reserved_integrity_only": True,
        "independence_authenticated": False,
        "model_calls": 0,
        "optimization_steps": 0,
        "orders": 0,
        "authority": dict(AUTHORITY),
    }


async def run_schedule(
    schedule_path,
    schedule_sha256,
    *,
    enable_public_capture=False,
    collector=None,
    sleeper=None,
    wall_clock=None,
    monotonic_clock=None,
):
    """Claim once, retain every failure, never retry/resume/select a successful subset.

    Injection is for synthetic tests. The CLI uses the real fixed public-only collector.
    No research preparation, labeling, model call, optimization or order follows capture.
    """
    if enable_public_capture is not True:
        raise ValueError("Explicit public-capture opt-in required before reading the schedule.")
    schedule = load_schedule(schedule_path, schedule_sha256)
    if schedule["schema_version"] != 2:
        raise ValueError("A fresh runnable V2 window plan is required; V1 remains metadata-only.")
    acquisition = schedule["acquisition"]
    clock = _Clock(
        wall_clock or time.time_ns,
        monotonic_clock or time.perf_counter_ns,
        acquisition["prepared_at_ns"],
    )
    collector, sleeper = collector or collect, sleeper or asyncio.sleep
    output = Path(acquisition["output_dir"])
    output.mkdir()  # Exclusive ownership, including after a crash or canceled run.
    receipt = _receipt(schedule, schedule_sha256, clock)
    with (output / "audit.jsonl").open("x", encoding="utf-8", newline="\n") as audit:

        def record(status, **fields):
            # Never resample during failure publication: a regressed/invalid clock
            # must not prevent retaining its last valid sample and fixed error code.
            audit.write(
                canonical(
                    {
                        "status": status,
                        "at_ns": clock.at_ns,
                        "elapsed_ns": clock.elapsed_ns,
                        **fields,
                    }
                )
                + "\n"
            )
            audit.flush()
            os.fsync(audit.fileno())

        active = None
        try:
            with failure_stage("schedule.failed"):
                receipt["schedule_copy_sha256"] = write_new(output / "schedule.json", schedule)
                clock.sample()
                record(
                    "started",
                    schedule_sha256=schedule_sha256,
                    schedule_copy_sha256=receipt["schedule_copy_sha256"],
                    clock_origin_wall_ns=clock.origin_wall,
                )
                for index, (assignment, window) in enumerate(
                    zip(
                        acquisition["sessions"],
                        schedule["windows"],
                        strict=True,
                    )
                ):
                    active = index
                    await _wait_window(window, clock, sleeper)
                    with failure_stage("campaign.binding_mismatch"):
                        _check_binding(acquisition)
                    if not clock.check_dispatch(window):
                        _refuse("schedule.missed_window")
                    intent_at_ns = clock.at_ns
                    record("session_started", **assignment)
                    receipt["sessions"][index]["status"] = "started"
                    guard = {}

                    async def guarded_collect(
                        *args, window=window, guard=guard, assignment=assignment, **kwargs
                    ):
                        # Recheck after durable intent IO and immediately before
                        # calling the collector, not only before its task was queued.
                        if not clock.check_dispatch(window):
                            _refuse("schedule.missed_window")
                        guard.update(
                            dispatched_at_ns=clock.at_ns, dispatch_elapsed_ns=clock.elapsed_ns
                        )

                        def connected(started_at_ns):
                            if "started_at_ns" in guard:
                                _refuse("schedule.completion_mismatch")
                            clock.sample()
                            with failure_stage("schedule.connected_late"):
                                _integer(
                                    started_at_ns,
                                    guard["dispatched_at_ns"] + 1,
                                    guard["dispatched_at_ns"] + CONNECTION_ALLOWANCE_NS,
                                )
                            if (
                                started_at_ns > clock.at_ns
                                or clock.at_ns > guard["dispatched_at_ns"] + CONNECTION_ALLOWANCE_NS
                                or clock.elapsed_ns - guard["dispatch_elapsed_ns"]
                                > CONNECTION_ALLOWANCE_NS
                            ):
                                _refuse("schedule.connected_late")
                            with failure_stage("campaign.binding_mismatch"):
                                _check_binding(acquisition)
                            guard.update(
                                started_at_ns=started_at_ns,
                                connected_at_ns=clock.at_ns,
                                connected_elapsed_ns=clock.elapsed_ns,
                            )
                            record(
                                "session_connected",
                                source_session=assignment["source_session"],
                                **guard,
                            )
                            # Hashing/audit fsync can itself stall. Do not start the
                            # snapshot/receiver on an admission that expired during IO.
                            clock.sample()
                            if (
                                clock.at_ns > guard["dispatched_at_ns"] + CONNECTION_ALLOWANCE_NS
                                or clock.elapsed_ns - guard["dispatch_elapsed_ns"]
                                > CONNECTION_ALLOWANCE_NS
                            ):
                                _refuse("schedule.connected_late")

                        result = await collector(*args, **kwargs, start_guard=connected)
                        if "started_at_ns" not in guard:
                            _refuse("schedule.start_guard_missing")
                        return result

                    item = await _bounded_capture(
                        _collect_slot(
                            acquisition,
                            schedule_sha256,
                            assignment,
                            collector=guarded_collect,
                            earliest_ns=intent_at_ns,
                            clock=clock.sample,
                        ),
                        window,
                        clock,
                    )
                    if guard["started_at_ns"] != item["source"]["started_at_ns"]:
                        _refuse("schedule.completion_mismatch")
                    # Validate the same frozen time contract on each completed slot
                    # without inventing claims for the still-unstarted sources.
                    start, end = item["source"]["started_at_ns"], item["source"]["ended_at_ns"]
                    if end > window["latest_capture_end_ns"] or start <= intent_at_ns:
                        _refuse("schedule.completion_mismatch")
                    item["window_evidence"] = {"intent_at_ns": intent_at_ns, **guard}
                    _check_completion_deadline(window, clock)
                    record("session_completed", session=item)
                    receipt["sessions"][index] = item
                    active = None
                with failure_stage("schedule.completion_mismatch"):
                    validate_completion_times(
                        schedule,
                        tuple(
                            {
                                "source_session": item["source_session"],
                                "dispatched_at_ns": item["window_evidence"]["dispatched_at_ns"],
                                "started_at_ns": item["source"]["started_at_ns"],
                                "ended_at_ns": item["source"]["ended_at_ns"],
                            }
                            for item in receipt["sessions"]
                        ),
                    )
                with failure_stage("campaign.binding_mismatch"):
                    _check_binding(acquisition)
                receipt["status"] = "completed"
                receipt_sha = hashlib.sha256((canonical(receipt) + "\n").encode()).hexdigest()
                clock.sample()
                record("receipt_prepared", receipt_sha256=receipt_sha)
                write_new(output / "receipt.json", receipt)
        except BaseException as error:
            if active is not None:
                receipt["sessions"][active]["status"] = "failed"
            receipt.update(
                status="failed", error_type=safe_error_type(error), failure=failure_details(error)
            )
            record(
                "failed",
                active_session=active,
                error_type=safe_error_type(error),
                failure=failure_details(error),
                timestamp_basis="last_valid_clock_sample",
            )
            write_new(output / "failure.json", receipt)
            raise
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--schedule-sha256", required=True)
    parser.add_argument("--enable-public-capture", action="store_true")
    args = parser.parse_args()
    print(
        canonical(
            asyncio.run(
                run_schedule(
                    args.schedule,
                    args.schedule_sha256,
                    enable_public_capture=args.enable_public_capture,
                )
            )
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(
            canonical(
                {
                    "status": "failed",
                    "error_type": safe_error_type(error),
                    "failure": failure_details(error),
                    "message": "Windowed capture stopped. Retain all evidence; do not resume.",
                }
            )
        )
        raise SystemExit(1) from None
