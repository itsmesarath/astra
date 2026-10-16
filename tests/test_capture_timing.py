"""Synthetic timing/socket tests only; never connect to public feeds."""

import asyncio
import hashlib
import itertools
import json
import runpy

import pytest
from test_collect_combined import setup as socket_setup  # noqa: F401

from ai_trader.ingestion import capture_timing as module
from ai_trader.ingestion import collect_combined as recorder
from ai_trader.ingestion.capture_timing import CaptureTiming, TimingMetric

MS = 1_000_000


def depth(wall_ns, exchange_ms):
    return {"received_at_ns": wall_ns, "stream": recorder.DEPTH_STREAM, "event": {"E": exchange_ms}}


@pytest.mark.parametrize("value", [True, -1, 0.1, None, "1"])
def test_metric_refuses_invalid_duration(value):
    with pytest.raises(ValueError):
        TimingMetric().add(value)


def test_histogram_edges_are_exclusive_buckets():
    metric = TimingMetric()
    values = [0, *module.BUCKETS_NS, module.BUCKETS_NS[-1] + 1]
    for value in values:
        metric.add(value)
    result = metric.summary()
    assert result["count"] == len(values)
    assert sum(result["bucket_counts"]) == len(values)
    assert result["bucket_counts"][0] == 2
    assert result["bucket_counts"][-1] == 1
    assert result["total_ns"] == sum(values)
    assert result["maximum_ns"] == max(values)


def test_coarse_wall_clock_does_not_replace_perf_counter():
    timing = CaptureTiming()
    timing.receive(1000 * MS, 10 * MS)
    timing.receive(1000 * MS, 13 * MS)
    timing.receive(1015 * MS, 15 * MS)
    summary = timing.summary()
    assert summary["equal_wall_receipts"] == 1
    assert summary["metrics"]["receipt_gap_wall"]["total_ns"] == 15 * MS
    assert summary["metrics"]["receipt_gap_perf"]["total_ns"] == 5 * MS
    assert summary["minimum_clock_gap_difference_ns"] == -3 * MS
    assert summary["maximum_clock_gap_difference_ns"] == 13 * MS


def test_queue_wait_and_processing_are_separate_from_receipt_gap():
    timing = CaptureTiming()
    timing.receive(1000 * MS, 100 * MS)
    timing.queued(2)
    timing.consumed(depth(1000 * MS, 950), 100 * MS, 600 * MS, 670 * MS)
    timing.receive(1600 * MS, 700 * MS)
    timing.queued(1)
    timing.consumed(depth(1600 * MS, 1050), 700 * MS, 750 * MS, 751 * MS)
    result = timing.summary()
    assert result["received_events"] == result["enqueued_events"] == result["processed_events"] == 2
    assert result["queue_high_water"] == 2
    assert result["metrics"]["queue_wait"]["total_ns"] == 550 * MS
    assert result["metrics"]["parse_write"]["total_ns"] == 71 * MS
    assert result["metrics"]["receipt_gap_perf"]["maximum_ns"] == 600 * MS
    assert (
        result["first_alert_samples"]["depth_receipt_gap_perf"][0]["exchange_event_gap_ms"] == 100
    )


def test_anomaly_memory_is_capped_but_counts_include_all_samples():
    timing = CaptureTiming()
    for index in range(101):
        timing.receive(index * 1000 * MS, index * 1000 * MS)
    result = timing.summary()
    assert result["alert_counts"]["receipt_gap_perf"] == 100
    assert len(result["first_alert_samples"]["receipt_gap_perf"]) == module.SAMPLE_LIMIT
    assert result["metrics"]["receipt_gap_perf"]["count"] == 100
    assert len(json.dumps(result).encode()) < module.MAX_REPORT_BYTES


def test_summary_does_not_expose_mutable_internal_state():
    timing = CaptureTiming()
    timing.receive(0, 0)
    timing.receive(1000 * MS, 1000 * MS)
    before = timing.summary()
    changed = timing.summary()
    changed["first_alert_samples"]["receipt_gap_perf"][0]["value_ns"] = 1
    changed["alert_thresholds_ns"]["receipt_gap_perf"] = 1
    changed["metrics"]["receipt_gap_perf"]["bucket_counts"].clear()
    assert timing.summary() == before


@pytest.mark.parametrize("initial_lag", [0, 100 * MS])
def test_watchdog_measures_lag_without_busy_catchup(initial_lag):
    timing = CaptureTiming()
    now = [100 * MS + initial_lag]
    waits = []

    async def sleeper(seconds):
        if len(waits) == 3:
            raise asyncio.CancelledError
        waits.append(seconds)
        now[0] += round(seconds * 1_000_000_000) + 200 * MS

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            timing.watch_loop(
                100 * MS, clock=lambda: now[0], wall_clock=lambda: 1000 * MS, sleeper=sleeper
            )
        )
    assert waits == [0, 0.05, 0.05]
    result = timing.summary()
    assert result["metrics"]["event_loop_lag"]["count"] == 3
    assert result["metrics"]["event_loop_lag"]["maximum_ns"] == 200 * MS + initial_lag
    assert result["alert_counts"]["event_loop_lag"] == 3


def test_timing_is_single_capture_only():
    timing = CaptureTiming()
    timing.claim()
    with pytest.raises(ValueError, match="new timing"):
        timing.claim()
    dirty = CaptureTiming()
    dirty.receive(1, 1)
    with pytest.raises(ValueError, match="new timing"):
        dirty.claim()


def test_snapshot_buffer_wait_is_not_mistaken_for_streaming_backlog():
    timing = CaptureTiming()
    timing.snapshot_available(1000 * MS, 500 * MS)
    # Equality uses the same conservative wall-receipt boundary as causal replay.
    timing.consumed(depth(1000 * MS, 900), 100 * MS, 600 * MS, 610 * MS)
    timing.consumed(depth(1100 * MS, 1000), 610 * MS, 620 * MS, 621 * MS)
    result = timing.summary()
    assert result["metrics"]["queue_wait_snapshot_buffer"]["count"] == 1
    assert result["metrics"]["queue_wait_snapshot_buffer"]["maximum_ns"] == 500 * MS
    assert result["metrics"]["queue_wait"]["count"] == 1
    assert result["metrics"]["queue_wait"]["maximum_ns"] == 10 * MS
    assert result["snapshot_available_wall_ns"] == 1000 * MS
    assert result["snapshot_available_perf_ns"] == 500 * MS
    with pytest.raises(ValueError, match="replaced"):
        timing.snapshot_available(2000 * MS, 1500 * MS)


def test_perf_counter_regression_refuses_misleading_duration():
    timing = CaptureTiming()
    timing.receive(1, 10)
    with pytest.raises(ValueError):
        timing.receive(2, 9)


def test_wall_regression_is_recorded_before_existing_refusal(monkeypatch):
    timing = CaptureTiming()
    walls, counters = iter([1000, 999]), iter([100, 200])
    monkeypatch.setattr(recorder.time, "time_ns", lambda: next(walls))
    monkeypatch.setattr(recorder.time, "perf_counter_ns", lambda: next(counters))

    async def messages():
        yield "{}"
        yield "{}"

    async def run():
        with pytest.raises(recorder.CaptureInterrupted, match="clock"):
            await recorder.receive_messages(messages(), asyncio.Queue(maxsize=3), timing=timing)

    asyncio.run(run())
    assert timing.wall_regressions == 1 and timing.enqueued == 1


def test_receiver_retains_wall_receipt_and_enforces_queue_bound():
    timing = CaptureTiming()

    async def messages():
        yield "{}"
        yield "{}"

    async def run():
        queue = asyncio.Queue(maxsize=1)
        with pytest.raises(recorder.CaptureInterrupted, match="overflow"):
            await recorder.receive_messages(messages(), queue, timing=timing)
        wall, message, perf = queue.get_nowait()
        assert type(wall) is int and type(perf) is int and message == "{}"

    asyncio.run(run())
    assert timing.received == 2 and timing.enqueued == timing.queue_high_water == 1


def test_opt_in_timing_keeps_identical_raw_schema_and_bytes(tmp_path, socket_setup, monkeypatch):  # noqa: F811
    async def watch(self, due_ns):
        await asyncio.Event().wait()

    monkeypatch.setattr(CaptureTiming, "watch_loop", watch)
    outputs = []
    receive = recorder.receive_messages
    for diagnostics in (None, CaptureTiming()):
        snapshot_available = asyncio.Event()
        wall = itertools.count(10**12, 10 * MS)

        def wall_time(wall=wall, ready=snapshot_available):
            value = next(wall)
            # The collector's first three reads are start, request, snapshot receipt.
            # Hold synthetic stream delivery until that receipt so worker-thread
            # scheduling cannot swap snapshot/stream timestamps between captures.
            if value == 10**12 + 20 * MS:
                ready.set()
            return value

        async def ordered_receive(*args, ready=snapshot_available, **kwargs):
            await ready.wait()
            await receive(*args, **kwargs)

        monkeypatch.setattr(recorder.time, "time_ns", wall_time)
        monkeypatch.setattr(recorder, "receive_messages", ordered_receive)
        socket_setup()
        path = tmp_path / ("plain.jsonl" if diagnostics is None else "timed.jsonl")
        asyncio.run(recorder.collect(1, output_path=path, timing=diagnostics))
        outputs.append(path.read_bytes())
        if diagnostics is not None:
            assert diagnostics.received == diagnostics.processed == 3
    assert outputs[0] == outputs[1]
    assert b"perf" not in outputs[1] and b"timing" not in outputs[1]


def test_real_synthetic_capture_records_watchdog_and_cleans_tasks(tmp_path, socket_setup):  # noqa: F811
    socket = socket_setup()
    timing = CaptureTiming()

    async def run():
        result = await recorder.collect(1, output_path=tmp_path / "capture.jsonl", timing=timing)
        assert result[1:] == (1, 2)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert socket.cleaned and socket.closed
    assert timing.metrics["event_loop_lag"].count > 0
    assert timing.metrics["parse_write"].count == 3


def test_cancel_stops_receiver_and_timing_probe(tmp_path, socket_setup):  # noqa: F811
    socket = socket_setup([])

    async def run():
        task = asyncio.create_task(
            recorder.collect(10, output_path=tmp_path / "capture.jsonl", timing=CaptureTiming())
        )
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert socket.cleaned and socket.closed
    assert (tmp_path / "capture.jsonl.partial").exists()
    assert not (tmp_path / "capture.jsonl").exists()


@pytest.mark.parametrize("normal_exit", [False, True])
def test_observer_failure_or_early_exit_cannot_silently_succeed(
    tmp_path,
    socket_setup,  # noqa: F811
    monkeypatch,
    normal_exit,
):
    socket_setup([])

    async def broken(self, due):
        await asyncio.sleep(0.05)
        if not normal_exit:
            raise RuntimeError("mock observer failure")

    monkeypatch.setattr(CaptureTiming, "watch_loop", broken)
    with pytest.raises((RuntimeError, recorder.CaptureInterrupted)):
        asyncio.run(
            recorder.collect(1, output_path=tmp_path / "capture.jsonl", timing=CaptureTiming())
        )
    assert not (tmp_path / "capture.jsonl").exists()


@pytest.mark.parametrize("timing", [True, {}, object()])
def test_invalid_timing_refused_before_io(tmp_path, timing):
    with pytest.raises(ValueError, match="Typed capture timing"):
        asyncio.run(recorder.collect(1, output_path=tmp_path / "capture.jsonl", timing=timing))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "enabled,seconds", [(False, 60), (1, 60), (True, 0), (True, 301), (True, True)]
)
def test_diagnostic_limits_and_opt_in_before_io(tmp_path, enabled, seconds):
    with pytest.raises(ValueError):
        asyncio.run(
            module.capture_with_timing(
                output_dir=tmp_path / "new", seconds=seconds, enable_public_capture=enabled
            )
        )
    assert not list(tmp_path.iterdir())


@pytest.fixture
def fake_collector(monkeypatch):
    calls = []

    async def collect(seconds, *, output_path, timing):
        assert type(timing) is CaptureTiming
        assert (output_path.parent / "intent.json").exists()
        calls.append(output_path)
        output_path.write_bytes(b"synthetic validated capture")
        return output_path, 1, 2

    monkeypatch.setattr(recorder, "collect", collect)
    return calls


def test_wrapper_pins_source_and_records_no_authority(tmp_path, fake_collector):
    output = tmp_path / "diagnostic"
    result = asyncio.run(
        module.capture_with_timing(output_dir=output, seconds=60, enable_public_capture=True)
    )
    assert len(fake_collector) == 1 and result["status"] == "completed"
    assert (
        result["source_sha256"]
        == hashlib.sha256((output / "capture.jsonl").read_bytes()).hexdigest()
    )
    assert (
        result["intent_sha256"] == hashlib.sha256((output / "intent.json").read_bytes()).hexdigest()
    )
    assert result["orders"] == result["model_calls"] == 0
    assert (
        result["training_allowed"]
        is result["execution_allowed"]
        is result["promotion_allowed"]
        is False
    )
    assert json.loads((output / "timing.json").read_text())["report"] == result
    with pytest.raises(FileExistsError):
        asyncio.run(
            module.capture_with_timing(output_dir=output, seconds=60, enable_public_capture=True)
        )
    assert len(fake_collector) == 1


@pytest.mark.parametrize(
    "error", [recorder.CaptureInterrupted, recorder.CaptureQuotaExceeded, asyncio.CancelledError]
)
def test_wrapper_failure_is_recorded_without_retry_or_private_payload(tmp_path, monkeypatch, error):
    calls = []

    async def fail(seconds, *, output_path, timing):
        calls.append(1)
        timing.receive(1000, 100)
        output_path.with_suffix(".jsonl.partial").write_bytes(b"retained partial")
        raise error("SECRET MARKET PAYLOAD")

    monkeypatch.setattr(recorder, "collect", fail)
    output = tmp_path / "diagnostic"
    with pytest.raises(error):
        asyncio.run(
            module.capture_with_timing(output_dir=output, seconds=60, enable_public_capture=True)
        )
    text = (output / "timing.json").read_text()
    assert "SECRET MARKET PAYLOAD" not in text
    report = json.loads(text)["report"]
    assert report["status"] == "failed" and report["error_type"] == error.__name__
    assert report["diagnostics"]["received_events"] == 1
    assert len(calls) == 1 and (output / "capture.jsonl.partial").exists()
    assert not (output / "capture.jsonl").exists()


def test_sidecar_publication_failure_preserves_capture(tmp_path, fake_collector, monkeypatch):
    from ai_trader.training import microstructure_data

    def fail(*args, **kwargs):
        raise OSError("mock disk error")

    monkeypatch.setattr(microstructure_data, "_publish", fail)
    output = tmp_path / "diagnostic"
    with pytest.raises(OSError):
        asyncio.run(
            module.capture_with_timing(output_dir=output, seconds=60, enable_public_capture=True)
        )
    assert (output / "capture.jsonl").exists() and len(fake_collector) == 1


def test_drift_never_claims_success_and_preserves_completed_raw(
    tmp_path, fake_collector, monkeypatch
):
    from ai_trader.trading import capture_replay

    hashes = iter(["a" * 64, "b" * 64])
    monkeypatch.setattr(capture_replay, "_implementation_hash", lambda: next(hashes))
    output = tmp_path / "diagnostic"
    with pytest.raises(ValueError, match="changed"):
        asyncio.run(
            module.capture_with_timing(output_dir=output, seconds=60, enable_public_capture=True)
        )
    assert len(fake_collector) == 1 and (output / "capture.jsonl").exists()
    assert json.loads((output / "timing.json").read_text())["report"]["status"] == "failed"


def test_cli_uses_canonical_timing_class(tmp_path, fake_collector, monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "capture_timing",
            "--output-dir",
            str(tmp_path / "diagnostic"),
            "--seconds",
            "60",
            "--enable-public-capture",
        ],
    )
    runpy.run_path(module.__file__, run_name="__main__")
    assert len(fake_collector) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "completed"
