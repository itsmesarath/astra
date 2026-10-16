"""Offline diagnosis only: synthetic frames, no files read, sockets or capture changes.

Run with the project Python 3.12 / websockets 17.1 environment. This characterizes
the CURRENT receiver, with production draining or scheduling-control consumers.
Historical pre-repair results and the old harness hash remain in the diagnosis
document. These new results must not be substituted for that historical run.

The optional source yield is a counterfactual scheduling experiment, not a patch
to the recorder and not a proposed change to receipt semantics.
"""

import asyncio
import json
import time

from websockets.asyncio.messages import Assembler
from websockets.frames import TEXT, Frame

from ai_trader.ingestion.capture_failure import failure_details
from ai_trader.ingestion.capture_timing import CaptureTiming
from ai_trader.ingestion.collect_combined import (
    CaptureInterrupted,
    _while_receiving,
    _write_stream,
    receive_messages,
)


async def scenario(count, *, yield_each=False, watched=False, blocked=False, draining=False):
    queue = asyncio.Queue(maxsize=256)
    start, consumed_all = asyncio.Event(), asyncio.Event()
    hold_open = asyncio.Event()
    timing, consumed, faults, flow = CaptureTiming(), [], [], []
    timing.claim()
    assembler = Assembler(high=16, pause=lambda: flow.append("pause"))
    # Emulate one already-parsed transport callback's frame batch. The installed
    # library's high-water mark requests a pause; it isn't a 16-frame hard cap.
    for number in range(count):
        assembler.put(Frame(TEXT, str(number).encode()))
    buffered_before = len(assembler.frames)

    async def source():
        await start.wait()
        for _ in range(count):
            yield await assembler.get()
            if yield_each:
                await asyncio.sleep(0)
        await hold_open.wait()  # No synthetic disconnect misclassified as overflow.

    async def producer():
        try:
            await receive_messages(source(), queue, timing=timing)
        except CaptureInterrupted as error:
            faults.append(
                {
                    "failure": failure_details(error),
                    "consumed_at_failure": len(consumed),
                    "pending_at_failure": queue.qsize(),
                }
            )
            raise

    receiver = asyncio.create_task(producer())

    async def consumer():
        if blocked:
            await hold_open.wait()
        if draining:

            def write(item):
                consumed.append(int(item[1]))
                if len(consumed) == count:
                    consumed_all.set()

            await _write_stream(
                queue, receiver, write, deadline=time.perf_counter() + 2, idle_timeout=2
            )
            return
        for _ in range(count):
            item = (
                await _while_receiving(queue.get(), receiver, 2) if watched else await queue.get()
            )
            consumed.append(int(item[1]))
        consumed_all.set()

    writer = asyncio.create_task(consumer())
    completed = asyncio.create_task(consumed_all.wait())
    try:
        # Allow the writer's empty queue.get (including the real watchdog helper)
        # to become pending before releasing the producer's prebuffered burst.
        for _ in range(4):
            await asyncio.sleep(0)
        start.set()
        done, _ = await asyncio.wait(
            (receiver, writer, completed), timeout=3, return_when=asyncio.FIRST_COMPLETED
        )
        if not done:
            raise AssertionError("Bounded synthetic diagnosis timed out")
        result = {
            "frames": count,
            "source_yields_each_message": yield_each,
            "consumer": (
                "blocked"
                if blocked
                else "production"
                if draining
                else "watched"
                if watched
                else "direct"
            ),
            "websocket_high_water": assembler.high,
            "buffered_frames_before": buffered_before,
            "transport_pause_requests": len(flow),
            "queue_capacity": queue.maxsize,
            "queue_high_water": timing.queue_high_water,
            "received": timing.received,
            "enqueued": timing.enqueued,
            "consumed": len(consumed),
            "ordered_prefix": consumed == list(range(len(consumed))),
            "all_consumed": consumed_all.is_set(),
            "faults": faults,
        }
        if not faults and not consumed_all.is_set():
            raise AssertionError("Unexpected synthetic task completion")
        return result
    finally:
        for task in (receiver, writer, completed):
            task.cancel()
        await asyncio.gather(receiver, writer, completed, return_exceptions=True)
        assert asyncio.all_tasks() == {asyncio.current_task()}


async def main():
    cases = [
        (256, {"draining": True}),
        (257, {"draining": True}),
        (1024, {"draining": True}),
        (4096, {"draining": True}),
        (257, {}),
        (1024, {"watched": True}),
        (257, {"blocked": True}),
    ]
    results = [await scenario(count, **options) for count, options in cases]
    for result in results[:5]:
        assert result["all_consumed"] and result["ordered_prefix"] and not result["faults"]
    assert results[-2]["faults"][0]["failure"]["reason"] == "queue_overflow"
    assert results[-1]["faults"][0]["failure"]["reason"] == "queue_overflow"
    print(json.dumps({"synthetic_only": True, "recorder": "bounded_burst_v1", "cases": results}))


if __name__ == "__main__":
    asyncio.run(main())
