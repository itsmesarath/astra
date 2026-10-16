"""Offline burst scheduling: real assembler, synthetic messages, no network."""

import asyncio
import itertools
import json
import time

import pytest
from test_capture_replay import records
from websockets.asyncio.messages import Assembler
from websockets.frames import TEXT, Frame

from ai_trader.ingestion import collect_combined as module
from ai_trader.ingestion.capture_failure import failure_details, mark_failure
from ai_trader.ingestion.capture_timing import CaptureTiming


class ReceiptQueue(asyncio.Queue):
    def __init__(self):
        super().__init__(maxsize=module.DEFAULT_LIMITS.queue_capacity)
        self.receipts = []

    def put_nowait(self, item):
        super().put_nowait(item)
        self.receipts.append(item)

    async def put(self, item):
        pytest.fail("Receiver must not hide overflow with a blocking put.")


@pytest.mark.parametrize("count, bursts", [(257, 1), (1024, 1), (1024, 4)])
@pytest.mark.parametrize("timed", [False, True])
def test_prebuffered_bursts_use_production_writer_without_loss(monkeypatch, count, bursts, timed):
    wall = itertools.count(10**12, 1000)
    monkeypatch.setattr(module.time, "time_ns", lambda: next(wall))

    async def run():
        queue, consumed, flow = ReceiptQueue(), [], []
        delivered = [asyncio.Event() for _ in range(bursts)]
        ready, hold = asyncio.Event(), asyncio.Event()
        timing = CaptureTiming() if timed else None
        assembler = Assembler(high=16, pause=lambda: flow.append("pause"))

        async def source():
            await ready.wait()
            for burst in range(bursts):
                for index in range(count):
                    assembler.put(Frame(TEXT, str(burst * count + index).encode()))
                assert len(assembler.frames) == count > queue.maxsize
                for _ in range(count):
                    yield await assembler.get()  # Prebuffered: no guaranteed suspension.
                await delivered[burst].wait()
            await hold.wait()

        def write(item):
            consumed.append(item)
            if len(consumed) % count == 0:
                delivered[len(consumed) // count - 1].set()

        receiver = asyncio.create_task(module.receive_messages(source(), queue, timing=timing))
        writer = asyncio.create_task(
            module._write_stream(
                queue, receiver, write, deadline=time.perf_counter() + 5, idle_timeout=2
            )
        )
        complete = asyncio.create_task(delivered[-1].wait())
        try:
            for _ in range(4):
                await asyncio.sleep(0)  # Writer is already waiting when the burst arrives.
            ready.set()
            done, _ = await asyncio.wait(
                (receiver, writer, complete), timeout=3, return_when=asyncio.FIRST_COMPLETED
            )
            for task in (receiver, writer):
                if task in done:
                    task.result()
            assert complete in done and complete.result()
            assert queue.empty() and queue.maxsize == 256
            assert len(consumed) == count * bursts
            assert all(a is b for a, b in zip(queue.receipts, consumed, strict=True))
            assert [int(item[1]) for item in consumed] == list(range(count * bursts))
            assert [item[0] for item in consumed] == [
                10**12 + index * 1000 for index in range(count * bursts)
            ]
            assert len(flow) == bursts
            if timing is not None:
                assert timing.received == timing.enqueued == count * bursts
                assert 0 < timing.queue_high_water <= 256
                assert all(len(item) == 3 for item in consumed)
            else:
                assert all(len(item) == 2 for item in consumed)
        finally:
            for task in (receiver, writer, complete):
                task.cancel()
            await asyncio.gather(receiver, writer, complete, return_exceptions=True)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())


@pytest.mark.parametrize("slow_consumer", [False, True])
def test_overloaded_or_absent_consumer_still_fails_at_original_capacity(slow_consumer):
    async def run():
        queue, consumed, timing = ReceiptQueue(), [], CaptureTiming()

        async def source():
            for _ in range(1024):
                yield "{}"
            await asyncio.Event().wait()

        async def slow_write():
            while True:
                # Deliberately slower cooperative service, not a real disk benchmark.
                for _ in range(8):
                    await asyncio.sleep(0)
                if not queue.empty():
                    consumed.append(queue.get_nowait())

        receiver = asyncio.create_task(module.receive_messages(source(), queue, timing=timing))
        writer = asyncio.create_task(slow_write() if slow_consumer else asyncio.Event().wait())
        try:
            with pytest.raises(module.CaptureInterrupted, match="overflow") as error:
                await asyncio.wait_for(receiver, 2)
            assert failure_details(error.value)["reason"] == "queue_overflow"
            assert timing.queue_high_water == queue.maxsize == 256
            assert timing.received == timing.enqueued + 1
            assert timing.enqueued == len(consumed) + queue.qsize()
            assert bool(consumed) == slow_consumer
        finally:
            receiver.cancel()
            writer.cancel()
            await asyncio.gather(receiver, writer, return_exceptions=True)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())


@pytest.mark.parametrize("cost, expected_quantum", [(0, 64), (0.003, 2)])
def test_ready_queue_writer_hands_off_by_count_and_time(monkeypatch, cost, expected_quantum):
    clock, consumed, checkpoints = [0.0], [], []
    monkeypatch.setattr(module.time, "perf_counter", lambda: clock[0])

    async def unexpected_wait(*args, **kwargs):
        pytest.fail("A ready queue must not create a watched task per item.")

    monkeypatch.setattr(module, "_while_receiving", unexpected_wait)

    async def run():
        queue = ReceiptQueue()
        for number in range(256):
            queue.put_nowait(number)

        def write(item):
            consumed.append(item)
            clock[0] += cost
            if len(consumed) == 256:
                clock[0] = 10

        receiver = asyncio.create_task(asyncio.Event().wait())
        writer = asyncio.create_task(
            module._write_stream(queue, receiver, write, deadline=10, idle_timeout=1)
        )

        async def witness():
            while not writer.done():
                checkpoints.append(len(consumed))
                await asyncio.sleep(0)

        witness_task = asyncio.create_task(witness())
        try:
            await asyncio.wait_for(writer, 2)
            await witness_task
            assert consumed == list(range(256))
            assert checkpoints[0] == expected_quantum
            assert (
                max(b - a for a, b in zip([0, *checkpoints], checkpoints, strict=False))
                <= expected_quantum
            )
        finally:
            for task in (receiver, writer, witness_task):
                task.cancel()
            await asyncio.gather(receiver, writer, witness_task, return_exceptions=True)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["receiver", "observer_error", "observer_return"])
def test_ready_queue_does_not_mask_dependency_failures(monkeypatch, failure):
    monkeypatch.setattr(module.time, "perf_counter", lambda: 0)

    async def run():
        queue, consumed = ReceiptQueue(), []
        for number in range(256):
            queue.put_nowait(number)

        async def fail():
            if failure == "observer_return":
                return
            raise mark_failure(
                module.CaptureInterrupted("synthetic dependency failure"),
                "receiver.transport_error" if failure == "receiver" else "observer.failed",
            )

        # Start the writer first so its ready queue must yield to the failure.
        receiver = asyncio.get_running_loop().create_future()
        observer = asyncio.get_running_loop().create_future()
        writer = asyncio.create_task(
            module._write_stream(
                queue, receiver, consumed.append, deadline=10, idle_timeout=1, observer=observer
            )
        )

        async def deliver_failure():
            target = receiver if failure == "receiver" else observer
            try:
                target.set_result(await fail())
            except module.CaptureInterrupted as error:
                target.set_exception(error)

        delivery = asyncio.create_task(deliver_failure())
        try:
            with pytest.raises(module.CaptureInterrupted) as error:
                await asyncio.wait_for(writer, 2)
            assert len(consumed) == module.WRITE_BURST_EVENTS
            assert (
                failure_details(error.value)["reason"]
                == {
                    "receiver": "transport_error",
                    "observer_error": "failed",
                    "observer_return": "stopped",
                }[failure]
            )
        finally:
            for task in (receiver, observer, writer, delivery):
                task.cancel()
            await asyncio.gather(receiver, observer, writer, delivery, return_exceptions=True)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())


def test_ready_queue_checks_deadline_between_each_item(monkeypatch):
    clock, consumed = [0.0], []
    monkeypatch.setattr(module.time, "perf_counter", lambda: clock[0])

    async def run():
        queue = ReceiptQueue()
        for number in range(256):
            queue.put_nowait(number)
        receiver = asyncio.create_task(asyncio.Event().wait())

        def write(item):
            consumed.append(item)
            clock[0] = 10

        try:
            await module._write_stream(queue, receiver, write, deadline=10, idle_timeout=1)
            assert consumed == [0] and queue.qsize() == 255
        finally:
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())


def test_cancellation_interrupts_busy_writer_at_quantum(monkeypatch):
    monkeypatch.setattr(module.time, "perf_counter", lambda: 0)

    async def run():
        queue, consumed = ReceiptQueue(), []
        for number in range(256):
            queue.put_nowait(number)
        receiver = asyncio.create_task(asyncio.Event().wait())
        writer = asyncio.create_task(
            module._write_stream(queue, receiver, consumed.append, deadline=10, idle_timeout=1)
        )
        try:
            await asyncio.sleep(0)
            writer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await writer
            assert len(consumed) == module.WRITE_BURST_EVENTS
        finally:
            receiver.cancel()
            await asyncio.gather(receiver, writer, return_exceptions=True)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())


@pytest.fixture
def burst_capture(monkeypatch):
    async def quiet_watch(self, due_ns):
        # This fixture asserts exact receipt-clock calls, not watchdog timing.
        await asyncio.Event().wait()

    monkeypatch.setattr(CaptureTiming, "watch_loop", quiet_watch)

    def no_network(*args, **kwargs):
        pytest.fail("Real network access forbidden in burst tests.")

    monkeypatch.setattr(module.urllib.request, "urlopen", no_network)

    def install(count=1024, *, snapshot_blocked=False, malformed=False):
        ready, hold = asyncio.Event(), asyncio.Event()

        class Socket:
            closed = False

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                self.closed = True

            async def __aiter__(self):
                await ready.wait()
                for number in range(count):
                    row = records()[2]  # Sequential, valid depth updates above snapshot 100.
                    row["event"].update(U=101 + number, u=101 + number, E=1000 + number)
                    yield (
                        "not json"
                        if malformed and number == 100
                        else json.dumps({"stream": row["stream"], "data": row["event"]})
                    )
                await hold.wait()

        async def snapshot():
            if snapshot_blocked:
                ready.set()
                await hold.wait()
            return records()[1]["event"]

        wall = itertools.count(1_000_000_000, 1_000_000)

        def wall_time():
            value = next(wall)
            if value == 1_002_000_000:  # Snapshot application receipt, before stream delivery.
                ready.set()
            return value

        socket = Socket()
        monkeypatch.setattr(module.time, "time_ns", wall_time)
        monkeypatch.setattr(module, "connect", lambda *args, **kwargs: socket)
        monkeypatch.setattr(module, "_snapshot_with_failure_code", snapshot)
        return socket

    return install


@pytest.mark.parametrize("timed", [False, True])
def test_real_writer_burst_publishes_only_receipt_causal_capture(tmp_path, burst_capture, timed):
    socket = burst_capture()
    path = tmp_path / "burst.jsonl"
    timing = CaptureTiming() if timed else None

    async def run():
        assert await module.collect(1, output_path=path, timing=timing) == (path, 0, 1024)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert socket.closed and not path.with_suffix(".jsonl.partial").exists()
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["record_type"] for row in rows[:2]] == ["session_start", "depth_snapshot"]
    assert rows[-1]["record_type"] == "session_end"
    assert [row["received_at_ns"] for row in rows[2:-1]] == [
        1_003_000_000 + index * 1_000_000 for index in range(1024)
    ]
    assert [row["event"]["u"] for row in rows[2:-1]] == list(range(101, 1125))
    module._validate_complete(path)
    if timing is not None:
        assert timing.received == timing.enqueued == timing.processed == 1024
        assert timing.queue_high_water <= 256


@pytest.mark.parametrize("case", ["slow_snapshot", "malformed", "event_limit", "byte_limit"])
def test_burst_failure_never_publishes_or_leaks_tasks(tmp_path, burst_capture, case):
    socket = burst_capture(snapshot_blocked=case == "slow_snapshot", malformed=case == "malformed")
    path, timing = tmp_path / "failed.jsonl", CaptureTiming()
    limits = module.CaptureLimits(
        max_events=100 if case == "event_limit" else 99_997,
        max_bytes=1000 if case == "byte_limit" else 32 * 1024 * 1024,
    )

    async def run():
        with pytest.raises((module.CaptureInterrupted, module.CaptureQuotaExceeded)) as error:
            await asyncio.wait_for(
                module.collect(1, output_path=path, limits=limits, timing=timing), 3
            )
        assert (
            failure_details(error.value)["reason"]
            == {
                "slow_snapshot": "acquisition_timeout",
                "malformed": "invalid_message",
                "event_limit": "event_limit",
                "byte_limit": "byte_limit",
            }[case]
        )
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert socket.closed and not path.exists()
    assert b"session_end" not in path.with_suffix(".jsonl.partial").read_bytes()
    if case == "slow_snapshot":
        assert timing.received == timing.enqueued == timing.processed == 1024
        assert timing.snapshot_available_wall_ns is None


@pytest.mark.parametrize("cancel_tail", [False, True])
def test_shutdown_tail_is_bounded_ordered_and_cancellable(
    tmp_path, burst_capture, monkeypatch, cancel_tail
):
    socket = burst_capture(count=200)
    path, parsed, tail_sizes = tmp_path / "tail.jsonl", [], []
    parse = module.parse_stream_record
    monkeypatch.setattr(module.time, "perf_counter", lambda: 0)

    async def end_stream(queue, *args, **kwargs):
        # Simulate the acquisition deadline leaving a finite, already-received
        # tail. The receiver still must be cancelled before shutdown drains it.
        while queue.qsize() < 200:
            await asyncio.sleep(0)
        tail_sizes.append(queue.qsize())

    def parse_and_cancel(*args):
        result = parse(*args)
        parsed.append(result[0])
        if cancel_tail and len(parsed) == 1:
            asyncio.current_task().cancel()
        return result

    monkeypatch.setattr(module, "_write_stream", end_stream)
    monkeypatch.setattr(module, "parse_stream_record", parse_and_cancel)

    async def run():
        task = asyncio.create_task(module.collect(1, output_path=path))
        if cancel_tail:
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 2)
            assert len(parsed) == module.WRITE_BURST_EVENTS
        else:
            assert await asyncio.wait_for(task, 2) == (path, 0, 200)
            assert len(parsed) == 200
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert socket.closed and tail_sizes == [200]
    assert [row["event"]["u"] for row in parsed] == list(range(101, 101 + len(parsed)))
    assert path.exists() != cancel_tail
    if cancel_tail:
        assert b"session_end" not in path.with_suffix(".jsonl.partial").read_bytes()
    else:
        module._validate_complete(path)
