"""Bounded public BTCUSDT capture; incomplete sessions remain .partial files."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import zlib
from contextlib import AsyncExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, PayloadTooBig, WebSocketException

from ai_trader.ingestion.agg_trade import AggTrade
from ai_trader.ingestion.capture_failure import (
    failure_details,
    failure_stage,
    mark_failure,
    safe_error_type,
)
from ai_trader.ingestion.capture_timing import PERIOD_NS, CaptureTiming
from ai_trader.orderbook.depth_update import DepthUpdate
from ai_trader.orderbook.snapshot import PartialDepthSnapshot

SYMBOL = "BTCUSDT"
TRADE_STREAM = "btcusdt@aggTrade"
DEPTH_STREAM = "btcusdt@depth@100ms"
STREAM_URL = f"wss://data-stream.binance.vision/stream?streams={TRADE_STREAM}/{DEPTH_STREAM}"
SNAPSHOT_URL = "https://data-api.binance.vision/api/v3/depth?symbol=BTCUSDT&limit=1000"
SNAPSHOT_LIMIT = 1000
OUTPUT_DIRECTORY = Path("data/raw")
MAX_SNAPSHOT_BYTES = 1_900_000  # Independent wire and decoded-response ceilings.
# Cooperative scheduling limits, not larger buffers or throughput promises.
WRITE_BURST_EVENTS = 64
WRITE_BURST_SECONDS = 0.005


class CaptureInterrupted(RuntimeError):
    """A fresh connection AND snapshot are required; never append to this session."""


class CaptureQuotaExceeded(RuntimeError):
    """Recording resource limit reached; do not automatically retry."""


class SnapshotTimeout(TimeoutError):
    """Preserve sanitized phase evidence across asyncio's executor bridge.

    Python 3.12 copies exact TimeoutError instances when adapting Futures and
    loses their custom attributes. A subclass is preserved, with no raw message.
    """


@dataclass(frozen=True, slots=True)
class CaptureLimits:
    queue_capacity: int = 256
    max_message_bytes: int = 256 * 1024
    max_events: int = 99_997
    max_bytes: int = 32 * 1024 * 1024
    idle_timeout_seconds: int = 5

    def __post_init__(self):
        for name, ceiling in (
            ("queue_capacity", 1024),
            ("max_message_bytes", 1_900_000),
            ("max_events", 99_997),
            ("max_bytes", 32 * 1024 * 1024),
            ("idle_timeout_seconds", 60),
        ):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"{name} must be an integer in [1, {ceiling}].")
        if self.queue_capacity * self.max_message_bytes > 64 * 1024 * 1024:
            raise ValueError("Application receipt buffer budget exceeds 64 MiB.")


DEFAULT_LIMITS = CaptureLimits()


@dataclass(frozen=True, slots=True)
class DurableCaptureRecord:
    """Exact line bytes forced to disk before an opt-in consumer is called."""

    file_kind: str
    start_offset: int
    end_offset: int
    line_sha256: str


def _validate_seconds(seconds):
    if type(seconds) is not int or not 1 <= seconds <= 3600:
        raise ValueError("seconds must be an integer in [1, 3600].")


def create_output_path() -> Path:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    return OUTPUT_DIRECTORY / f"btcusdt_combined_{timestamp}.jsonl"


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"Nonfinite JSON constant: {value}")


def _json(message):
    return json.loads(message, object_pairs_hook=_pairs, parse_constant=_constant)


@contextmanager
def _snapshot_io(phase):
    """Classify only the observed IO phase; never inspect URLs, headers or text."""
    try:
        yield
    except SnapshotTimeout:
        raise  # Keep the stricter elapsed-deadline code if a check raised it.
    except urllib.error.HTTPError as error:
        with failure_stage("snapshot.close_error"):
            try:
                error.close()  # HTTPError owns a response body; never read it or retry.
            except TimeoutError:
                raise mark_failure(
                    SnapshotTimeout("Snapshot error-response cleanup timed out."),
                    "snapshot.close_error",
                ) from None
        mark_failure(error, "snapshot.http_error")
        raise
    except (TimeoutError, urllib.error.URLError) as error:
        reason = error.reason if isinstance(error, urllib.error.URLError) else error
        if isinstance(reason, TimeoutError):
            raise mark_failure(
                SnapshotTimeout(f"Public snapshot {phase} timed out."), f"snapshot.{phase}_timeout"
            ) from None
        mark_failure(error, f"snapshot.{phase}_transport_error")
        raise
    except OSError as error:
        mark_failure(error, f"snapshot.{phase}_transport_error")
        raise


def _check_snapshot_deadline(deadline):
    if time.monotonic() >= deadline:
        raise mark_failure(
            SnapshotTimeout("Snapshot response exceeded its read deadline."), "snapshot.deadline"
        )


def _snapshot_encoding(response):
    encodings = response.headers.get_all("Content-Encoding", [])
    if not encodings:
        return "identity"
    if len(encodings) == 1:
        encoding = encodings[0].strip().lower()
        if encoding in ("identity", "gzip"):
            return encoding
    raise mark_failure(
        ValueError("Unsupported snapshot content encoding."), "snapshot.invalid_response"
    )


def _decode_snapshot_body(body, encoding):
    """Bound expansion independently of wire size; accept one complete gzip member."""
    if encoding == "identity":
        return body
    try:
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        decoded = decoder.decompress(body, MAX_SNAPSHOT_BYTES + 1)
    except zlib.error:
        raise mark_failure(
            ValueError("Invalid compressed snapshot."), "snapshot.invalid_response"
        ) from None
    if len(decoded) > MAX_SNAPSHOT_BYTES:
        raise mark_failure(
            CaptureQuotaExceeded("Decoded snapshot exceeds byte limit."), "snapshot.byte_limit"
        )
    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise mark_failure(
            ValueError("Incomplete or trailing compressed snapshot."), "snapshot.invalid_response"
        )
    return decoded


def fetch_snapshot() -> dict[str, object]:
    """One public REST request; phase-specific failures, no retries or larger budgets.

    Negotiate gzip to reduce transfer size; identity remains a valid server choice.
    Wire bytes and decoded bytes are independently bounded by the original cap.
    Check the elapsed budget after blocking work too, including EOF/validation.
    This rejects late results but cannot interrupt a blocked OS/socket operation.
    """
    deadline = time.monotonic() + 10
    request = urllib.request.Request(SNAPSHOT_URL, headers={"Accept-Encoding": "gzip"})
    with _snapshot_io("open"):
        response = urllib.request.urlopen(request, timeout=10)
    with _snapshot_io("read"), response:
        _check_snapshot_deadline(deadline)
        encoding = _snapshot_encoding(response)
        body = bytearray()
        while True:
            _check_snapshot_deadline(deadline)
            # read1 does at most one underlying read: check the deadline between
            # chunks instead of letting a trickling response extend read(n) forever.
            chunk = response.read1(min(64 * 1024, MAX_SNAPSHOT_BYTES + 1 - len(body)))
            _check_snapshot_deadline(deadline)
            body.extend(chunk)
            if len(body) > MAX_SNAPSHOT_BYTES:
                raise mark_failure(
                    CaptureQuotaExceeded("Snapshot exceeds byte limit."), "snapshot.byte_limit"
                )
            if not chunk:
                break
    _check_snapshot_deadline(deadline)
    decoded = _decode_snapshot_body(body, encoding)
    _check_snapshot_deadline(deadline)
    payload = _json(decoded)
    if not isinstance(payload, dict):
        raise ValueError("Snapshot response must be a JSON object.")
    PartialDepthSnapshot.from_event(payload)
    _check_snapshot_deadline(deadline)
    return payload


async def _snapshot_with_failure_code():
    try:
        # Production IO phases survive the worker bridge via SnapshotTimeout.
        # Retain generic fallbacks for unclassified dependencies/test doubles.
        return await asyncio.to_thread(fetch_snapshot)
    except TimeoutError as error:
        mark_failure(error, "snapshot.timeout")
        raise
    except OSError as error:
        mark_failure(error, "snapshot.transport_error")
        raise
    except (ValueError, TypeError, KeyError, ArithmeticError) as error:
        mark_failure(error, "snapshot.invalid_response")
        raise


async def receive_messages(websocket, queue, limits=DEFAULT_LIMITS, *, timing=None) -> None:
    """Timestamp at application receipt; never silently drop or wait on a full queue."""
    previous = 0
    try:
        async for message in websocket:
            received_at_ns = time.time_ns()
            received_perf_ns = None
            if timing is not None:
                received_perf_ns = time.perf_counter_ns()
                timing.receive(received_at_ns, received_perf_ns)
            if received_at_ns < previous:
                raise mark_failure(
                    CaptureInterrupted("Receipt clock moved backwards."),
                    "receiver.receipt_clock_regression",
                )
            previous = received_at_ns
            size = len(message.encode("utf-8") if isinstance(message, str) else message)
            if size > limits.max_message_bytes:
                raise mark_failure(
                    CaptureQuotaExceeded("WebSocket message exceeds byte limit."),
                    "receiver.message_limit",
                )
            try:
                item = (received_at_ns, message)
                if timing is not None:
                    item += (received_perf_ns,)
                queue.put_nowait(item)
                if timing is not None:
                    timing.queued(queue.qsize())
            except asyncio.QueueFull as error:
                raise mark_failure(
                    CaptureInterrupted("Receipt buffer overflow; session quarantined."),
                    "receiver.queue_overflow",
                ) from error
            # A prebuffered WebSocket recv need not suspend. Give the writer,
            # observer and cancellation a turn after stamping/enqueuing each
            # receipt. This is not a blocking put: a full queue still fails.
            await asyncio.sleep(0)
    except ConnectionClosed as error:
        if any(close is not None and close.code == 1009 for close in (error.sent, error.rcvd)):
            raise mark_failure(
                CaptureQuotaExceeded("WebSocket protocol message-size limit exceeded."),
                "receiver.message_limit",
            ) from error
        raise mark_failure(
            CaptureInterrupted("Public stream transport failed."), "receiver.transport_error"
        ) from error
    except PayloadTooBig as error:
        raise mark_failure(
            CaptureQuotaExceeded("WebSocket protocol message-size limit exceeded."),
            "receiver.message_limit",
        ) from error
    except (OSError, TimeoutError, WebSocketException) as error:
        raise mark_failure(
            CaptureInterrupted("Public stream transport failed."), "receiver.transport_error"
        ) from error
    raise mark_failure(
        CaptureInterrupted("Public stream disconnected before the capture deadline."),
        "receiver.disconnected",
    )


def parse_stream_record(received_at_ns, message) -> tuple[dict[str, object], str]:
    wrapper = _json(message)
    if not isinstance(wrapper, dict):
        raise ValueError("Combined message must be a JSON object.")
    stream_name, event = wrapper.get("stream"), wrapper.get("data")
    if not isinstance(event, dict):
        raise ValueError("Combined message must contain event data.")
    if stream_name == TRADE_STREAM:
        AggTrade.from_event(event)
    elif stream_name == DEPTH_STREAM:
        DepthUpdate.from_event(event)
    else:
        raise ValueError(f"Unexpected stream: {stream_name}")
    return {
        "schema_version": 1,
        "record_type": "stream_event",
        "stream": stream_name,
        "received_at_ns": received_at_ns,
        "event": event,
    }, stream_name


class _CaptureWaitTimeout(TimeoutError):
    """Our elapsed wait budget, not a TimeoutError raised by a watched dependency."""


def _check_capture_tasks(receiver, observer=None):
    """Check completed dependencies even when draining an already-ready queue."""
    if observer is not None and observer.done():
        with failure_stage("observer.failed"):
            observer.result()
        raise mark_failure(
            CaptureInterrupted("Timing observer stopped unexpectedly."), "observer.stopped"
        )
    if receiver.done():
        receiver.result()


async def _while_receiving(awaitable, receiver, timeout, observer=None, *, writer=None):
    """Observe failures and keep one pending operation across early timer wakeups."""
    task = asyncio.ensure_future(awaitable)
    deadline = time.perf_counter() + max(0, timeout)
    wait_seconds = max(0, timeout)
    try:
        watched = (task, receiver) if observer is None else (task, receiver, observer)
        if writer is not None:
            watched += (writer,)
        while True:
            done, _ = await asyncio.wait(
                watched, timeout=wait_seconds, return_when=asyncio.FIRST_COMPLETED
            )
            _check_capture_tasks(receiver, observer)
            if writer is not None and writer.done():
                writer.result()  # A staging failure must interrupt snapshot acquisition.
            if task in done:
                return task.result()
            if writer is not None and writer.done():
                raise _CaptureWaitTimeout  # The acquisition deadline ended the writer.
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise _CaptureWaitTimeout
            # asyncio may release timers up to one loop-clock resolution early.
            # Keep the same get/snapshot task; a resolution-sized wait avoids a
            # sub-tick busy loop, while receiver/observer failures still wake it.
            wait_seconds = max(remaining, time.get_clock_info("monotonic").resolution)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def _write_stream(queue, receiver, write_event, *, deadline, idle_timeout, observer=None):
    """Drain ready receipts in bounded batches; watch dependencies while idle.

    The time quantum is checked between synchronous writes, not a hard timeout
    for a single parse/disk operation. No task or blocking put is added per ready
    item. Timestamped FIFO entries pass to the writer unchanged.
    """
    written = 0
    burst_deadline = time.perf_counter() + WRITE_BURST_SECONDS
    while True:
        _check_capture_tasks(receiver, observer)
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return
        try:
            item = queue.get_nowait()
        except asyncio.QueueEmpty:
            try:
                with failure_stage("stream.failed"):
                    item = await _while_receiving(
                        queue.get(), receiver, min(remaining, idle_timeout), observer
                    )
            except _CaptureWaitTimeout as error:
                if time.perf_counter() < deadline:
                    raise mark_failure(
                        CaptureInterrupted("Public stream idle timeout."), "stream.idle_timeout"
                    ) from error
                return
            # The watched wait already handed off to other tasks. Start a new
            # quantum, without charging time spent waiting against writer work.
            written = 0
            burst_deadline = time.perf_counter() + WRITE_BURST_SECONDS
            _check_capture_tasks(receiver, observer)
        write_event(item)
        written += 1
        if written >= WRITE_BURST_EVENTS or time.perf_counter() >= burst_deadline:
            await asyncio.sleep(0)
            written = 0
            burst_deadline = time.perf_counter() + WRITE_BURST_SECONDS


class _CaptureRecording:
    """Disk staging within the original byte budget, never a second memory queue.

    Reserve both the staged bytes and their eventual copy before every write.
    This is stricter than a final-file-only quota: staging cannot double disk use
    beyond max_bytes. All events are parsed once and retain their receipt order.
    """

    def __init__(self, output, staged, limits):
        self.output, self.staged, self.limits = output, staged, limits
        self.staged_bytes = 0
        self.assembling = False

    def write(self, record, *, event=False):
        encoded = (json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n").encode()
        staged_bytes = self.staged_bytes + (len(encoded) if event else 0)
        reserved = (1 if self.assembling else 2) * staged_bytes
        total = self.output.tell() + reserved + (0 if event else len(encoded))
        if len(encoded) > 2_000_000 or total > self.limits.max_bytes:
            raise mark_failure(
                CaptureQuotaExceeded("Recording and staging exceed byte limit."), "write.byte_limit"
            )
        with failure_stage("write.failed"):
            target = self.staged if event else self.output
            start_offset = target.tell()
            if target.write(encoded) != len(encoded):
                raise OSError("Incomplete capture write.")
        self.staged_bytes = staged_bytes
        return DurableCaptureRecord(
            "stream" if event else "metadata",
            start_offset,
            target.tell(),
            hashlib.sha256(encoded).hexdigest(),
        )

    async def assemble(self):
        """Called only after receiver/writer exit; copy bounded chunks, no reparsing."""
        self.assembling = True
        with failure_stage("finalize.failed"):
            self.staged.flush()
            self.staged.seek(0)
            remaining = self.staged_bytes
            while remaining:
                chunk = self.staged.read(min(64 * 1024, remaining))
                if not chunk:
                    raise OSError("Truncated capture staging file.")
                if self.output.tell() + self.staged_bytes + len(chunk) > self.limits.max_bytes:
                    raise CaptureQuotaExceeded("Capture assembly exceeds byte limit.")
                if self.output.write(chunk) != len(chunk):
                    raise OSError("Incomplete capture assembly write.")
                remaining -= len(chunk)
                await asyncio.sleep(0)
            if self.staged.read(1):
                raise OSError("Unexpected capture staging tail.")


def _validate_complete(path, *, config=None):
    # Reuse the receipt-causal consumer without a journal or order capability.
    from ai_trader.features.microstructure import MicrostructureConfig
    from ai_trader.trading.capture_replay import CaptureReplay, CaptureReplayConfig

    with path.open("rb") as source:
        data = source.read(32 * 1024 * 1024 + 1)
    if config is not None and type(config) is not CaptureReplayConfig:
        raise ValueError("Typed replay validation config required.")
    replay = CaptureReplay(
        data,
        expected_sha256=hashlib.sha256(data).hexdigest(),
        source_session=path.name,
        config=config or CaptureReplayConfig(features=MicrostructureConfig(levels=1)),
    )
    usable = False
    for frame in replay.frames():
        if frame.status.startswith("resync_required:StaleMarketEventError:"):
            raise mark_failure(
                CaptureInterrupted("Capture contains an event outside freshness bounds."),
                "integrity.stale_event",
            )
        if frame.status.startswith("resync_required:"):
            raise CaptureInterrupted(f"Capture integrity failure: {frame.status}")
        usable |= frame.observation is not None
    if not usable:
        raise CaptureInterrupted("No synchronized post-snapshot depth observation.")


async def collect(
    seconds: int,
    *,
    output_path: Path | None = None,
    limits: CaptureLimits = DEFAULT_LIMITS,
    timing: CaptureTiming | None = None,
    start_guard=None,
    on_durable_record=None,
    validation_config=None,
) -> tuple[Path, int, int]:
    """Capture once; failures retain .partial, only validated sessions publish .jsonl.

    Duration covers snapshot + stream, after connection establishment (10s timeout).
    Events are staged from connection onward, including while the snapshot is
    pending; the idle watchdog also covers startup. Staging plus assembly share
    max_bytes. Shutdown, assembly and bounded offline validation are additional.
    Cancelling to_thread cannot kill urllib's worker: it checks a 10s deadline
    between reads, each with a 10s socket timeout. OS DNS/disk stalls aren't
    hard real-time bounded.
    """
    _validate_seconds(seconds)
    if start_guard is not None and not callable(start_guard):
        raise ValueError("A synchronous start guard is required.")
    if on_durable_record is not None and not callable(on_durable_record):
        raise ValueError("A synchronous durable record callback is required.")
    if validation_config is not None:
        from ai_trader.trading.capture_replay import CaptureReplayConfig

        if type(validation_config) is not CaptureReplayConfig:
            raise ValueError("Typed replay validation config required.")
    if type(limits) is not CaptureLimits:
        raise ValueError("Typed capture limits required.")
    if timing is not None:
        if type(timing) is not CaptureTiming:
            raise ValueError("Typed capture timing collector required.")
        timing.claim()
    output_path = Path(output_path) if output_path is not None else create_output_path()
    if output_path.suffix != ".jsonl":
        raise ValueError("Capture destination must end in .jsonl.")
    if output_path.exists():
        raise FileExistsError(output_path)
    partial = output_path.with_suffix(".jsonl.partial")
    staged_path = output_path.with_suffix(".jsonl.stream.partial")
    queue = asyncio.Queue(maxsize=limits.queue_capacity)
    counts = {TRADE_STREAM: 0, DEPTH_STREAM: 0}
    with (
        failure_stage("recording.failed"),
        partial.open("xb") as output,
        staged_path.open("x+b") as staged,
    ):
        recording = _CaptureRecording(output, staged, limits)

        def write(record, *, event=False):
            receipt = recording.write(record, event=event)
            if on_durable_record is not None:
                with failure_stage("write.durable_callback"):
                    target = staged if event else output
                    target.flush()
                    os.fsync(target.fileno())
                    on_durable_record(record, receipt)

        snapshot_received = False

        def write_event(item):
            before_ns = time.perf_counter_ns() if timing is not None else None
            if sum(counts.values()) >= limits.max_events:
                raise mark_failure(
                    CaptureQuotaExceeded("Recording exceeds event limit."), "write.event_limit"
                )
            with failure_stage("parse.invalid_message"):
                record, stream = parse_stream_record(*item[:2])
            write(record, event=True)
            counts[stream] += 1
            if timing is not None:
                timing.consumed(
                    record,
                    item[2],
                    before_ns,
                    time.perf_counter_ns(),
                    snapshot_pending=not snapshot_received,
                )

        try:
            async with AsyncExitStack() as stack:
                try:
                    with failure_stage("connection.transport_error"):
                        websocket = await stack.enter_async_context(
                            connect(
                                STREAM_URL,
                                open_timeout=10,
                                close_timeout=2,
                                max_queue=16,
                                max_size=limits.max_message_bytes,
                            )
                        )
                except (OSError, TimeoutError, WebSocketException) as error:
                    raise mark_failure(
                        CaptureInterrupted("Public connection failed."),
                        "connection.transport_error",
                    ) from error
                deadline = time.perf_counter() + seconds
                started = time.time_ns()
                if start_guard is not None:
                    # A windowed campaign can refuse a late connection before any
                    # snapshot request, receiver task or market-data record starts.
                    if start_guard(started) is not None:
                        raise ValueError("Start guard must return None.")
                write(
                    {
                        "schema_version": 1,
                        "record_type": "session_start",
                        "started_at_ns": started,
                        "symbol": SYMBOL,
                        "streams": [TRADE_STREAM, DEPTH_STREAM],
                        "snapshot_limit": SNAPSHOT_LIMIT,
                    }
                )
                observer = (
                    None
                    if timing is None
                    else asyncio.create_task(timing.watch_loop(time.perf_counter_ns() + PERIOD_NS))
                )
                receiver = asyncio.create_task(
                    receive_messages(websocket, queue, limits, timing=timing)
                )
                writer = asyncio.create_task(
                    _write_stream(
                        queue,
                        receiver,
                        write_event,
                        deadline=deadline,
                        idle_timeout=limits.idle_timeout_seconds,
                        observer=observer,
                    )
                )
                try:
                    requested = time.time_ns()
                    try:
                        with failure_stage("snapshot.failed"):
                            snapshot = await _while_receiving(
                                _snapshot_with_failure_code(),
                                receiver,
                                deadline - time.perf_counter(),
                                observer,
                                writer=writer,
                            )
                            # A completed task can win the shared wait even after
                            # this deadline. Reject late snapshot success here,
                            # without dropping a queue.get receipt in that helper.
                            if time.perf_counter() >= deadline:
                                raise _CaptureWaitTimeout
                    except _CaptureWaitTimeout as error:
                        # This expiry belongs to snapshot acquisition, not stream idleness.
                        raise mark_failure(
                            CaptureInterrupted("Public snapshot failed or timed out."),
                            "snapshot.acquisition_timeout",
                        ) from error
                    except (OSError, TimeoutError, ValueError, TypeError, ArithmeticError) as error:
                        raise CaptureInterrupted("Public snapshot failed or timed out.") from error
                    available = time.time_ns()
                    if timing is not None:
                        timing.snapshot_available(available, time.perf_counter_ns())
                    snapshot_received = True
                    write(
                        {
                            "schema_version": 1,
                            "record_type": "depth_snapshot",
                            "requested_at_ns": requested,
                            "received_at_ns": available,
                            "event": snapshot,
                        }
                    )
                    await writer
                    _check_capture_tasks(receiver, observer)
                finally:
                    receiver.cancel()
                    writer.cancel()
                    if observer is not None:
                        observer.cancel()
                    await asyncio.gather(
                        *([receiver, writer] if observer is None else [receiver, writer, observer]),
                        return_exceptions=True,
                    )
                # Receiver is now cancelled: this final FIFO tail is bounded by
                # queue_capacity. Still cooperate between bounded write batches.
                tail_count = 0
                tail_deadline = time.perf_counter() + WRITE_BURST_SECONDS
                while not queue.empty():
                    write_event(queue.get_nowait())
                    tail_count += 1
                    if tail_count >= WRITE_BURST_EVENTS or time.perf_counter() >= tail_deadline:
                        await asyncio.sleep(0)
                        tail_count = 0
                        tail_deadline = time.perf_counter() + WRITE_BURST_SECONDS
                await recording.assemble()
                write(
                    {
                        "schema_version": 1,
                        "record_type": "session_end",
                        "ended_at_ns": time.time_ns(),
                        "trade_events": counts[TRADE_STREAM],
                        "depth_events": counts[DEPTH_STREAM],
                    }
                )
        except (
            ValueError,
            TypeError,
            KeyError,
            ArithmeticError,
            WebSocketException,
            TimeoutError,
        ) as error:
            raise CaptureInterrupted("Malformed data or interrupted public connection.") from error
        finally:
            with failure_stage("finalize.failed"):
                staged.flush()
                os.fsync(staged.fileno())
                output.flush()
                os.fsync(output.fileno())
    try:
        with failure_stage("integrity.rejected"):
            if validation_config is None:
                _validate_complete(partial)
            else:
                _validate_complete(partial, config=validation_config)
    except (ValueError, TypeError, KeyError, ArithmeticError) as error:
        raise CaptureInterrupted("Capture failed receipt-causal validation.") from error
    # Same-volume, no-overwrite publication. A crash may leave both hard links,
    # never a partially copied final file. Unsupported filesystems fail closed.
    with failure_stage("publication.failed"):
        # The validated, flushed partial now contains every staged event. Remove
        # only this redundant, owned staging file before publishing success.
        staged_path.unlink()
        os.link(partial, output_path)
        partial.unlink()
    return output_path, counts[TRADE_STREAM], counts[DEPTH_STREAM]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument(
        "--output", type=Path, help="New exact .jsonl destination; never overwritten."
    )
    args = parser.parse_args()
    try:
        _validate_seconds(args.seconds)
    except ValueError as error:
        parser.error(str(error))
    return args


def main() -> None:
    args = parse_args()
    path, trades, depths = asyncio.run(collect(args.seconds, output_path=args.output))
    print(f"Public data only. Trade events: {trades}; depth events: {depths}")
    print(f"Output: {path.resolve()}")


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
                    "message": "Capture stopped; retain partial files. No retry.",
                }
            )
        )
        raise SystemExit(1) from None
