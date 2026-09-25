"""Bounded diagnostic counters; no prices, target labels or replacement timestamps.

perf_counter_ns is monotonic and uses QPC on this Windows Python, unlike its
coarser time_ns/monotonic_ns clocks. It is still application timing, not wire timing.
"""

import argparse
import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from ai_trader.ingestion.capture_failure import failure_details, safe_error_type

PERIOD_NS = 50_000_000
SAMPLE_LIMIT = 32
MAX_REPORT_BYTES = 256 * 1024
BUCKETS_NS = (
    100_000,
    1_000_000,
    5_000_000,
    10_000_000,
    50_000_000,
    100_000_000,
    500_000_000,
    1_000_000_000,
)
METRICS = (
    "receipt_gap_wall",
    "receipt_gap_perf",
    "clock_gap_difference_abs",
    "queue_wait",
    "queue_wait_snapshot_buffer",
    "parse_write",
    "event_loop_lag",
    "depth_receipt_gap_wall",
    "depth_receipt_gap_perf",
)
ALERTS = {name: (500_000_000 if "receipt_gap" in name else 50_000_000) for name in METRICS}


def _nonnegative(value):
    if type(value) is not int or value < 0:
        raise ValueError("Timing values must be nonnegative integer nanoseconds/counts.")


@dataclass(slots=True)
class TimingMetric:
    count: int = 0
    total_ns: int = 0
    maximum_ns: int = 0
    buckets: list[int] = field(default_factory=lambda: [0] * (len(BUCKETS_NS) + 1))

    def add(self, value):
        _nonnegative(value)
        self.count += 1
        self.total_ns += value
        self.maximum_ns = max(self.maximum_ns, value)
        index = next((i for i, limit in enumerate(BUCKETS_NS) if value <= limit), len(BUCKETS_NS))
        self.buckets[index] += 1

    def summary(self):
        return {
            "count": self.count,
            "total_ns": self.total_ns,
            "maximum_ns": self.maximum_ns,
            "bucket_counts": list(self.buckets),
        }


class CaptureTiming:
    """Single-capture, event-loop-owned fixed histograms and capped anomaly samples."""

    def __init__(self):
        self.metrics = {name: TimingMetric() for name in METRICS}
        self.samples = {name: [] for name in METRICS}
        self.alert_counts = dict.fromkeys(METRICS, 0)
        self.received = self.enqueued = self.processed = self.queue_high_water = 0
        self.wall_regressions = self.equal_wall_receipts = self.depth_exchange_regressions = 0
        self.minimum_clock_gap_difference_ns = self.maximum_clock_gap_difference_ns = None
        self._last_receipt = self._last_depth = None
        self.snapshot_available_wall_ns = self.snapshot_available_perf_ns = None
        self._claimed = False

    def claim(self):
        if self._claimed or self.received or any(m.count for m in self.metrics.values()):
            raise ValueError("A new timing collector is required for each capture.")
        self._claimed = True

    def _observe(self, name, value, wall_ns, perf_ns, **context):
        self.metrics[name].add(value)
        if value > ALERTS[name]:
            self.alert_counts[name] += 1
            if len(self.samples[name]) < SAMPLE_LIMIT:
                self.samples[name].append(
                    {"wall_ns": wall_ns, "perf_ns": perf_ns, "value_ns": value, **context}
                )

    def receive(self, wall_ns, perf_ns):
        _nonnegative(wall_ns)
        _nonnegative(perf_ns)
        self.received += 1
        if self._last_receipt is not None:
            wall_gap = wall_ns - self._last_receipt[0]
            perf_gap = perf_ns - self._last_receipt[1]
            self._observe("receipt_gap_perf", perf_gap, wall_ns, perf_ns)
            self.wall_regressions += wall_gap < 0
            self.equal_wall_receipts += wall_gap == 0
            if wall_gap >= 0:
                self._observe("receipt_gap_wall", wall_gap, wall_ns, perf_ns)
            difference = wall_gap - perf_gap
            low, high = self.minimum_clock_gap_difference_ns, self.maximum_clock_gap_difference_ns
            self.minimum_clock_gap_difference_ns = (
                difference if low is None else min(low, difference)
            )
            self.maximum_clock_gap_difference_ns = (
                difference if high is None else max(high, difference)
            )
            self._observe("clock_gap_difference_abs", abs(difference), wall_ns, perf_ns)
        self._last_receipt = (wall_ns, perf_ns)

    def queued(self, size):
        _nonnegative(size)
        self.enqueued += 1
        self.queue_high_water = max(self.queue_high_water, size)

    def snapshot_available(self, wall_ns, perf_ns):
        _nonnegative(wall_ns)
        _nonnegative(perf_ns)
        if self.snapshot_available_wall_ns is not None:
            raise ValueError("Snapshot timing cannot be replaced within a session.")
        self.snapshot_available_wall_ns, self.snapshot_available_perf_ns = wall_ns, perf_ns

    def consumed(self, record, received_perf_ns, before_ns, after_ns, *, snapshot_pending=False):
        wall_ns = record["received_at_ns"]
        buffered = snapshot_pending or (
            self.snapshot_available_wall_ns is not None
            and wall_ns <= self.snapshot_available_wall_ns
        )
        wait_metric = "queue_wait_snapshot_buffer" if buffered else "queue_wait"
        self._observe(wait_metric, before_ns - received_perf_ns, wall_ns, received_perf_ns)
        self._observe(
            "parse_write",
            after_ns - before_ns,
            wall_ns,
            received_perf_ns,
            snapshot_buffered=buffered,
        )
        self.processed += 1
        if record["stream"] != "btcusdt@depth@100ms":
            return
        exchange_ms = record["event"]["E"]
        if self._last_depth is not None:
            old_wall, old_perf, old_exchange = self._last_depth
            gap = exchange_ms - old_exchange
            self.depth_exchange_regressions += gap < 0
            context = {"exchange_event_gap_ms": gap, "processed_event": self.processed}
            self._observe(
                "depth_receipt_gap_wall", wall_ns - old_wall, wall_ns, received_perf_ns, **context
            )
            self._observe(
                "depth_receipt_gap_perf",
                received_perf_ns - old_perf,
                wall_ns,
                received_perf_ns,
                **context,
            )
        self._last_depth = (wall_ns, received_perf_ns, exchange_ms)

    async def watch_loop(self, due_ns, *, clock=None, wall_clock=None, sleeper=None):
        """Measure late 50-ms wakeups; skip missed periods, never run a catch-up loop."""
        clock, wall_clock, sleeper = (
            clock or time.perf_counter_ns,
            wall_clock or time.time_ns,
            sleeper or asyncio.sleep,
        )
        while True:
            await sleeper(max(0, due_ns - clock()) / 1_000_000_000)
            now = clock()
            self._observe("event_loop_lag", max(0, now - due_ns), wall_clock(), now)
            due_ns = now + PERIOD_NS

    def summary(self):
        return {
            "clock_metadata": {
                name: vars(time.get_clock_info(name))
                for name in ("time", "monotonic", "perf_counter")
            },
            "timer_period_ns": PERIOD_NS,
            "sample_limit_per_metric": SAMPLE_LIMIT,
            "bucket_upper_bounds_ns": [*BUCKETS_NS, None],
            "metrics": {name: metric.summary() for name, metric in self.metrics.items()},
            "alert_thresholds_ns": dict(ALERTS),
            "alert_counts": dict(self.alert_counts),
            "first_alert_samples": {
                name: [dict(value) for value in values] for name, values in self.samples.items()
            },
            "received_events": self.received,
            "enqueued_events": self.enqueued,
            "processed_events": self.processed,
            "queue_high_water": self.queue_high_water,
            "snapshot_available_wall_ns": self.snapshot_available_wall_ns,
            "snapshot_available_perf_ns": self.snapshot_available_perf_ns,
            "wall_regressions": self.wall_regressions,
            "equal_wall_receipts": self.equal_wall_receipts,
            "depth_exchange_regressions": self.depth_exchange_regressions,
            "minimum_clock_gap_difference_ns": self.minimum_clock_gap_difference_ns,
            "maximum_clock_gap_difference_ns": self.maximum_clock_gap_difference_ns,
        }


async def capture_with_timing(*, output_dir, seconds, enable_public_capture=False):
    """One opt-in diagnostic session in a new directory; never resumes or retries."""
    from ai_trader.ingestion.collect_combined import DEFAULT_LIMITS, _validate_seconds, collect
    from ai_trader.ingestion.planned_capture import write_new
    from ai_trader.research.microstructure_trial import _environment
    from ai_trader.trading.capture_replay import _implementation_hash

    if enable_public_capture is not True:
        raise ValueError("Explicit public-capture opt-in required.")
    _validate_seconds(seconds)
    if seconds > 300:
        raise ValueError("Diagnostic capture is limited to 300 seconds.")
    output = Path(output_dir).resolve()
    output.mkdir()
    timing = CaptureTiming()
    intent = {
        "schema_version": 1,
        "kind": "capture_timing_intent_v1",
        "seconds": seconds,
        "implementation_sha256": _implementation_hash(),
        "environment_json": _environment(),
        "prepared_at_ns": time.time_ns(),
        "role": "diagnostic_research_only",
        "attempts": 1,
        "capture_path": str(output / "capture.jsonl"),
        "limits": {
            name: getattr(DEFAULT_LIMITS, name) for name in DEFAULT_LIMITS.__dataclass_fields__
        },
        "training_allowed": False,
        "promotion_allowed": False,
        "execution_allowed": False,
    }
    intent_sha = write_new(output / "intent.json", intent)
    status, source_sha, error_type, failure = "failed", None, None, None
    try:
        result = await collect(seconds, output_path=output / "capture.jsonl", timing=timing)
        with result[0].open("rb") as stream:
            raw = stream.read(DEFAULT_LIMITS.max_bytes + 1)
        if len(raw) > DEFAULT_LIMITS.max_bytes:
            raise ValueError("Diagnostic capture exceeds its byte budget.")
        source_sha = hashlib.sha256(raw).hexdigest()
        if (
            intent["implementation_sha256"] != _implementation_hash()
            or intent["environment_json"] != _environment()
        ):
            raise ValueError("Implementation or runtime changed during diagnostic capture.")
        status = "completed"
    except BaseException as error:
        error_type, failure = safe_error_type(error), failure_details(error)
        raise
    finally:
        report = {
            "schema_version": 1,
            "kind": "capture_timing_report_v1",
            "status": status,
            "intent_sha256": intent_sha,
            "source_sha256": source_sha,
            "error_type": error_type,
            "diagnostics": timing.summary(),
            "orders": 0,
            "model_calls": 0,
            "training_allowed": False,
            "promotion_allowed": False,
            "execution_allowed": False,
            "limitation": (
                "Application receipt diagnostics, not wire latency or root-cause proof. "
                "No timestamp replacement. Watchdog excludes offline validation and shutdown. "
                "Parse/write timing excludes footer flush/fsync."
            ),
        }
        if failure is not None:
            report["failure"] = failure
        # Same exclusive publication mechanism, with a separate bounded report budget.
        from ai_trader.training.microstructure_data import _publish

        _publish(report, output / "timing.json", payload_name="report", max_bytes=MAX_REPORT_BYTES)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seconds", type=int, required=True)
    parser.add_argument("--enable-public-capture", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(capture_with_timing(**vars(args)))
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    try:
        # Use the canonical module's class identity even when invoked with python -m.
        from ai_trader.ingestion.capture_timing import main as run_main

        run_main()
    except (Exception, KeyboardInterrupt) as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": safe_error_type(error),
                    "failure": failure_details(error),
                    "message": "Keep the diagnostic directory and partials; no retry.",
                }
            )
        )
        raise SystemExit(1) from None
