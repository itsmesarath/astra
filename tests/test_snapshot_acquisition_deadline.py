"""Snapshot-only acquisition boundaries; shared queue waits retain their receipts."""

import asyncio

import pytest
from test_capture_replay import records
from test_collect_combined import setup as socket_setup  # noqa: F401

from ai_trader.ingestion import collect_combined as module
from ai_trader.ingestion.capture_failure import failure_details, mark_failure
from ai_trader.ingestion.capture_timing import CaptureTiming


def snapshot_at(monkeypatch, completed_at, *, error=None):
    clock = [0.0]
    monkeypatch.setattr(module.time, "perf_counter", lambda: clock[0])

    async def snapshot():
        clock[0] = completed_at
        if error is not None:
            raise error
        return records()[1]["event"]

    monkeypatch.setattr(module, "_snapshot_with_failure_code", snapshot)
    return clock


@pytest.mark.parametrize("completed_at", [1.0, 1.25])
def test_snapshot_completing_at_or_after_capture_deadline_is_not_available(
    tmp_path,
    monkeypatch,
    socket_setup,  # noqa: F811
    completed_at,
):
    socket = socket_setup()
    snapshot_at(monkeypatch, completed_at)
    timing, path = CaptureTiming(), tmp_path / "late.jsonl"

    async def run():
        with pytest.raises(module.CaptureInterrupted) as caught:
            await module.collect(1, output_path=path, timing=timing)
        assert failure_details(caught.value)["reason"] == "acquisition_timeout"
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert socket.closed and socket.cleaned
    assert timing.snapshot_available_wall_ns is None
    assert timing.snapshot_available_perf_ns is None
    assert not path.exists()
    assert path.with_suffix(".jsonl.stream.partial").exists()
    partial = path.with_suffix(".jsonl.partial").read_bytes()
    assert b"depth_snapshot" not in partial and b"session_end" not in partial


def test_snapshot_just_before_capture_deadline_remains_accepted(
    tmp_path,
    monkeypatch,
    socket_setup,  # noqa: F811
):
    socket = socket_setup()
    clock = snapshot_at(monkeypatch, 1 - 1e-9)
    parse, parsed = module.parse_stream_record, []

    def finish_after_receipts(*args):
        result = parse(*args)
        parsed.append(result)
        if len(parsed) == 3:
            clock[0] = 1.0
        return result

    monkeypatch.setattr(module, "parse_stream_record", finish_after_receipts)
    timing, path = CaptureTiming(), tmp_path / "accepted.jsonl"

    async def run():
        assert await module.collect(1, output_path=path, timing=timing) == (path, 1, 2)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert socket.closed and socket.cleaned
    assert timing.snapshot_available_wall_ns is not None
    assert timing.snapshot_available_perf_ns is not None
    assert list(tmp_path.iterdir()) == [path]
    module._validate_complete(path)


@pytest.mark.parametrize(
    ("dependency", "code"),
    [
        ("snapshot", "snapshot.open_timeout"),
        ("receiver", "receiver.transport_error"),
        ("writer", "write.failed"),
        ("observer", "observer.failed"),
    ],
)
def test_dependency_failure_precedes_late_snapshot_success_check(
    tmp_path,
    monkeypatch,
    socket_setup,  # noqa: F811
    dependency,
    code,
):
    socket = socket_setup()
    error = mark_failure(
        module.SnapshotTimeout("Synthetic timeout")
        if dependency == "snapshot"
        else RuntimeError("Synthetic dependency failure"),
        code,
    )
    snapshot_at(monkeypatch, 1.25, error=error if dependency == "snapshot" else None)

    async def fail(*args, **kwargs):
        raise error

    if dependency == "receiver":
        monkeypatch.setattr(module, "receive_messages", fail)
    elif dependency == "writer":
        monkeypatch.setattr(module, "_write_stream", fail)
    elif dependency == "observer":
        monkeypatch.setattr(CaptureTiming, "watch_loop", fail)
    timing, path = CaptureTiming(), tmp_path / "failed.jsonl"

    async def run():
        with pytest.raises((module.CaptureInterrupted, RuntimeError)) as caught:
            await module.collect(1, output_path=path, timing=timing)
        stage, reason = code.split(".")
        assert failure_details(caught.value) == {
            "schema_version": 1,
            "stage": stage,
            "reason": reason,
        }
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert socket.closed and not path.exists()
    assert timing.snapshot_available_wall_ns is None
    assert b"depth_snapshot" not in path.with_suffix(".jsonl.partial").read_bytes()
    assert path.with_suffix(".jsonl.stream.partial").exists()


def test_shared_wait_keeps_already_dequeued_receipt_at_final_boundary(monkeypatch):
    clock, receipt = [0.0], object()
    monkeypatch.setattr(module.time, "perf_counter", lambda: clock[0])

    async def late_completion(tasks, **kwargs):
        clock[0] = 2.0
        await asyncio.sleep(0)
        assert tasks[0].done()
        return {tasks[0]}, set(tasks[1:])

    monkeypatch.setattr(module.asyncio, "wait", late_completion)

    async def run():
        queue = asyncio.Queue()
        queue.put_nowait(receipt)
        receiver = asyncio.create_task(asyncio.Event().wait())
        try:
            assert await module._while_receiving(queue.get(), receiver, 1.0) is receipt
            assert queue.empty()
        finally:
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
