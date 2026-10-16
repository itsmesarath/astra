"""Early event-loop timer wakeups must not become premature capture timeouts."""

import asyncio
import time
from types import SimpleNamespace

import pytest
from test_collect_combined import setup as socket_setup  # noqa: F401

from ai_trader.ingestion import collect_combined as module


def test_early_timer_wakeup_keeps_same_pending_get(monkeypatch):
    original = asyncio.wait
    watched_tasks = []

    async def early_once(tasks, **kwargs):
        watched_tasks.append(tuple(tasks))
        if len(watched_tasks) == 1:
            await asyncio.sleep(0)
            return set(), set(tasks)
        return await original(tasks, **kwargs)

    monkeypatch.setattr(module.asyncio, "wait", early_once)

    async def run():
        queue = asyncio.Queue()
        receiver = asyncio.create_task(asyncio.Event().wait())

        async def deliver():
            await asyncio.sleep(0.005)
            queue.put_nowait("one packet")

        producer = asyncio.create_task(deliver())
        try:
            assert await module._while_receiving(queue.get(), receiver, 0.1) == "one packet"
            assert queue.empty()
        finally:
            receiver.cancel()
            await asyncio.gather(receiver, producer, return_exceptions=True)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert len(watched_tasks) == 2
    assert watched_tasks[0] == watched_tasks[1]


def test_early_wakeup_does_not_reset_budget_or_spin(monkeypatch):
    clock, waits = [0.0], []
    monkeypatch.setattr(module.time, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(module.time, "get_clock_info", lambda _: SimpleNamespace(resolution=0.016))

    async def early_then_expired(tasks, *, timeout, **kwargs):
        waits.append(timeout)
        clock[0] = 0.099 if len(waits) == 1 else 0.12
        return set(), set(tasks)

    monkeypatch.setattr(module.asyncio, "wait", early_then_expired)

    async def run():
        receiver = asyncio.create_task(asyncio.Event().wait())
        try:
            with pytest.raises(module._CaptureWaitTimeout):
                await module._while_receiving(asyncio.Event().wait(), receiver, 0.1)
        finally:
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert waits == [0.1, 0.016]


@pytest.mark.parametrize("source", ["receiver", "observer", "operation"])
def test_dependency_timeout_is_not_our_elapsed_budget(source):
    async def fail():
        raise TimeoutError("dependency failed")

    async def run():
        receiver = asyncio.create_task(fail() if source == "receiver" else asyncio.Event().wait())
        observer = asyncio.create_task(fail() if source == "observer" else asyncio.Event().wait())
        operation = fail() if source == "operation" else asyncio.Event().wait()
        try:
            with pytest.raises(TimeoutError, match="dependency failed") as error:
                await module._while_receiving(operation, receiver, 1, observer)
            assert not isinstance(error.value, module._CaptureWaitTimeout)
        finally:
            receiver.cancel()
            observer.cancel()
            await asyncio.gather(receiver, observer, return_exceptions=True)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())


def test_expired_wait_cleans_pending_operation():
    async def run():
        receiver = asyncio.create_task(asyncio.Event().wait())
        try:
            with pytest.raises(module._CaptureWaitTimeout):
                await module._while_receiving(asyncio.Event().wait(), receiver, 0)
        finally:
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())


@pytest.mark.parametrize("observer", [False, True])
def test_real_capture_survives_early_timer_without_shortening(
    tmp_path,
    socket_setup,  # noqa: F811
    monkeypatch,
    observer,
):
    socket = socket_setup()
    original = asyncio.wait
    early = []

    async def early_wait(tasks, **kwargs):
        # Simulate a near-deadline early loop wakeup once, after the stream drained.
        if not early and kwargs["timeout"] < 0.97:
            early.append(True)
            return set(), set(tasks)
        return await original(tasks, **kwargs)

    monkeypatch.setattr(module.asyncio, "wait", early_wait)
    path = tmp_path / "capture.jsonl"
    start = time.perf_counter()
    asyncio.run(
        module.collect(1, output_path=path, timing=module.CaptureTiming() if observer else None)
    )
    assert time.perf_counter() - start >= 1
    assert early and socket.closed and socket.cleaned
    assert path.exists() and not path.with_suffix(".jsonl.partial").exists()
    module._validate_complete(path)


def test_cancel_after_early_wakeup_cleans_pending_get(monkeypatch):
    original = asyncio.wait
    early = asyncio.Event()

    async def early_once(tasks, **kwargs):
        if not early.is_set():
            early.set()
            return set(), set(tasks)
        return await original(tasks, **kwargs)

    monkeypatch.setattr(module.asyncio, "wait", early_once)

    async def run():
        receiver = asyncio.create_task(asyncio.Event().wait())
        waiter = asyncio.create_task(module._while_receiving(asyncio.Queue().get(), receiver, 1))
        await early.wait()
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        receiver.cancel()
        await asyncio.gather(receiver, return_exceptions=True)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
