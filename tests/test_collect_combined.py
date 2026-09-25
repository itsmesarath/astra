"""Synthetic sockets/REST only; never connect to a real feed."""

import asyncio
import itertools
import json
import time
from dataclasses import replace
from email.message import Message

import pytest
from test_capture_replay import records
from websockets.exceptions import ConnectionClosedError
from websockets.frames import Close

from ai_trader.ingestion import collect_combined as module
from ai_trader.ingestion.collect_combined import (
    CaptureInterrupted,
    CaptureLimits,
    CaptureQuotaExceeded,
)


class Socket:
    def __init__(self, messages, *, disconnect=False):
        self.messages = messages
        self.disconnect = disconnect
        self.cleaned = False
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def __aiter__(self):
        try:
            for row in self.messages:
                await asyncio.sleep(0.02)
                if isinstance(row, str):
                    yield row
                else:
                    event = dict(row["event"], E=time.time_ns() // 1_000_000)
                    if "T" in event:
                        event["T"] = event["E"]
                    yield json.dumps({"stream": row["stream"], "data": event})
            if not self.disconnect:
                await asyncio.Event().wait()
        finally:
            self.cleaned = True


@pytest.fixture
def setup(monkeypatch):
    def no_network(*args, **kwargs):
        pytest.fail("Real network access forbidden in collector tests.")

    monkeypatch.setattr(module.urllib.request, "urlopen", no_network)

    def install(messages=None, **kwargs):
        socket = Socket(records()[2:-1] if messages is None else messages, **kwargs)

        def connect(url, **options):
            assert url == module.STREAM_URL
            assert options["max_queue"] == 16
            assert options["max_size"] <= 1_900_000
            assert options["open_timeout"] == 10
            return socket

        monkeypatch.setattr(module, "connect", connect)
        monkeypatch.setattr(module, "fetch_snapshot", lambda: records()[1]["event"])
        return socket

    return install


def test_complete_capture_publishes_only_validated_file(tmp_path, setup, monkeypatch):
    # This scenario requires snapshot-first delivery. Real wall-clock resolution
    # and worker scheduling cannot establish that ordering deterministically.
    available = asyncio.Event()
    wall = itertools.count(10**12, 10_000_000)
    receive = module.receive_messages

    def wall_time():
        value = next(wall)
        if value == 10**12 + 20_000_000:  # Start, request, then snapshot receipt.
            available.set()
        return value

    async def ordered_receive(*args, **kwargs):
        await available.wait()
        await receive(*args, **kwargs)

    monkeypatch.setattr(module.time, "time_ns", wall_time)
    monkeypatch.setattr(module, "receive_messages", ordered_receive)
    socket = setup()
    path = tmp_path / "session.jsonl"
    result = asyncio.run(module.collect(1, output_path=path))
    assert result == (path, 1, 2)
    assert socket.cleaned and socket.closed
    assert not path.with_suffix(".jsonl.partial").exists()
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[-1]["record_type"] == "session_end"
    assert rows[1]["received_at_ns"] < rows[2]["received_at_ns"]
    module._validate_complete(path)


@pytest.mark.parametrize("messages", [[], ["not json"], ['{"stream":null}']])
def test_early_disconnect_and_malformed_packets_quarantined(tmp_path, setup, messages):
    socket = setup(messages, disconnect=True)
    path = tmp_path / "session.jsonl"
    with pytest.raises(CaptureInterrupted):
        asyncio.run(module.collect(10, output_path=path))
    assert not path.exists()
    assert path.with_suffix(".jsonl.partial").exists()
    assert socket.cleaned and socket.closed


def test_snapshot_failure_cleans_receiver(tmp_path, setup, monkeypatch):
    socket = setup([])

    def broken():
        raise OSError("mock snapshot transport failure")

    monkeypatch.setattr(module, "fetch_snapshot", broken)
    with pytest.raises(CaptureInterrupted, match="snapshot"):
        asyncio.run(module.collect(10, output_path=tmp_path / "session.jsonl"))
    assert socket.cleaned and socket.closed


def test_snapshot_wait_observes_receiver_failure(tmp_path, setup, monkeypatch):
    socket = setup([], disconnect=True)
    cancelled = []

    async def blocked_thread(*args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    monkeypatch.setattr(module.asyncio, "to_thread", blocked_thread)
    with pytest.raises(CaptureInterrupted, match="disconnected"):
        asyncio.run(module.collect(10, output_path=tmp_path / "session.jsonl"))
    assert cancelled and socket.closed


def test_idle_stream_fails_promptly(tmp_path, setup):
    socket = setup([])
    with pytest.raises(CaptureInterrupted, match="idle timeout"):
        asyncio.run(
            module.collect(
                10,
                output_path=tmp_path / "session.jsonl",
                limits=CaptureLimits(idle_timeout_seconds=1),
            )
        )
    assert socket.cleaned and socket.closed


def test_cancel_retains_partial_and_no_background_tasks(tmp_path, setup):
    socket = setup([])
    path = tmp_path / "session.jsonl"

    async def run():
        task = asyncio.create_task(module.collect(10, output_path=path))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert socket.cleaned and socket.closed
    assert not path.exists()
    assert b"session_end" not in path.with_suffix(".jsonl.partial").read_bytes()


@pytest.mark.parametrize(
    "limits",
    [CaptureLimits(max_bytes=1), CaptureLimits(max_events=1), CaptureLimits(max_message_bytes=1)],
)
def test_quotas_fail_without_publishing(tmp_path, setup, limits):
    socket = setup()
    path = tmp_path / "session.jsonl"
    with pytest.raises(CaptureQuotaExceeded):
        asyncio.run(module.collect(1, output_path=path, limits=limits))
    assert socket.closed
    assert not path.exists()


def test_buffer_overflow_is_not_hidden_backpressure():
    async def messages():
        for _ in range(2):
            yield "{}"

    async def run():
        queue = asyncio.Queue(maxsize=1)
        with pytest.raises(CaptureInterrupted, match="overflow"):
            await module.receive_messages(messages(), queue)
        assert queue.qsize() == 1

    asyncio.run(run())


def test_receipt_clock_regression_fails(monkeypatch):
    clocks = iter([100, 99])
    monkeypatch.setattr(module.time, "time_ns", lambda: next(clocks))

    async def messages():
        yield "{}"
        yield "{}"

    async def run():
        with pytest.raises(CaptureInterrupted, match="clock"):
            await module.receive_messages(messages(), asyncio.Queue(maxsize=3))

    asyncio.run(run())


@pytest.mark.parametrize("suffix", [".jsonl", ".jsonl.partial"])
def test_existing_destinations_never_overwritten(tmp_path, setup, suffix):
    setup()
    path = tmp_path / "session.jsonl"
    existing = path.with_suffix(suffix)
    existing.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        asyncio.run(module.collect(1, output_path=path))
    assert existing.read_bytes() == b"keep"


def test_publication_race_never_overwrites(tmp_path, setup, monkeypatch):
    setup()
    path = tmp_path / "session.jsonl"
    validate = module._validate_complete

    def race(partial):
        validate(partial)
        path.write_bytes(b"other writer")

    monkeypatch.setattr(module, "_validate_complete", race)
    with pytest.raises(FileExistsError):
        asyncio.run(module.collect(1, output_path=path))
    assert path.read_bytes() == b"other writer"
    assert path.with_suffix(".jsonl.partial").exists()


def test_gap_never_publishes_as_complete(tmp_path, setup):
    rows = records()[2:-1]
    rows[-1]["event"].update(U=150, u=150)
    setup(rows)
    with pytest.raises(CaptureInterrupted, match="integrity"):
        asyncio.run(module.collect(1, output_path=tmp_path / "session.jsonl"))
    assert not (tmp_path / "session.jsonl").exists()


def test_connection_error_is_retryable(tmp_path, monkeypatch):
    class FailedConnection:
        async def __aenter__(self):
            raise OSError("mock connect failure")

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(module, "connect", lambda *args, **kwargs: FailedConnection())
    with pytest.raises(CaptureInterrupted, match="connection"):
        asyncio.run(module.collect(1, output_path=tmp_path / "session.jsonl"))


def test_snapshot_reads_are_bounded(monkeypatch):
    class Response:
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read1(self, count):
            assert 1 <= count <= 64 * 1024
            return b"x" * count

    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(CaptureQuotaExceeded):
        module.fetch_snapshot()


@pytest.mark.parametrize("body", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'])
def test_json_rejects_ambiguous_values(body):
    with pytest.raises(ValueError):
        module.parse_stream_record(1, body)


@pytest.mark.parametrize("seconds", [False, 0, -1, 3601, 1.5])
def test_duration_validation_before_io(tmp_path, seconds):
    with pytest.raises(ValueError):
        asyncio.run(module.collect(seconds, output_path=tmp_path / "session.jsonl"))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_events": True},
        {"queue_capacity": 0},
        {"max_bytes": 33 * 1024 * 1024},
        {"queue_capacity": 1024, "max_message_bytes": 1_900_000},
    ],
)
def test_limits_validation(kwargs):
    with pytest.raises(ValueError):
        replace(CaptureLimits(), **kwargs)


@pytest.mark.parametrize("fault", ["bad_json", "bad_decimal", "duplicate_key"])
def test_malformed_packet_while_socket_stays_open(tmp_path, setup, fault):
    row = records()[3]
    if fault == "bad_json":
        messages = ["not json"]
    elif fault == "bad_decimal":
        row["event"]["q"] = "NaN"
        messages = [row]
    else:
        messages = ['{"stream":"first","stream":"second","data":{}}']
    socket = setup(messages)
    with pytest.raises(CaptureInterrupted):
        asyncio.run(module.collect(1, output_path=tmp_path / "session.jsonl"))
    assert socket.cleaned and socket.closed
    assert not (tmp_path / "session.jsonl").exists()


def test_snapshot_deadline_checked_between_chunks(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    reads = []

    class Response:
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read1(self, count):
            reads.append(count)
            clock[0] = 11.0
            return b"{"

    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(TimeoutError, match="read deadline"):
        module.fetch_snapshot()
    assert reads == [64 * 1024]


def test_snapshot_chunked_success(monkeypatch):
    snapshot = records()[1]["event"]
    body = json.dumps(snapshot).encode()
    chunks = iter([body[:10], body[10:], b""])

    class Response:
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read1(self, count):
            return next(chunks)

    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    assert module.fetch_snapshot() == snapshot


def test_unsynchronized_session_never_published(tmp_path, setup):
    row = records()[2]
    row["event"].update(U=100, u=100)  # Already covered by snapshot, never bridges it.
    setup([row])
    with pytest.raises(CaptureInterrupted, match="No synchronized"):
        asyncio.run(module.collect(1, output_path=tmp_path / "session.jsonl"))
    assert not (tmp_path / "session.jsonl").exists()


def test_disk_flush_error_is_not_reclassified_as_retryable(tmp_path, setup, monkeypatch):
    socket = setup()

    def fail(fd):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(module.os, "fsync", fail)
    with pytest.raises(OSError, match="disk failure"):
        asyncio.run(module.collect(1, output_path=tmp_path / "session.jsonl"))
    assert socket.cleaned and socket.closed
    assert not (tmp_path / "session.jsonl").exists()


@pytest.mark.parametrize(
    "code, expected", [(1009, CaptureQuotaExceeded), (1006, CaptureInterrupted)]
)
def test_protocol_size_limit_is_not_a_retryable_disconnect(code, expected):
    async def messages():
        raise ConnectionClosedError(None, Close(code, "synthetic close"))
        yield  # Async generator, like the real WebSocket iterator.

    async def run():
        with pytest.raises(expected):
            await module.receive_messages(messages(), asyncio.Queue(maxsize=1))

    asyncio.run(run())
