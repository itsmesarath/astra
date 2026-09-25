"""A paper callback sees only bytes already flushed to the owned capture file."""

import asyncio
import hashlib
import itertools

import pytest
from test_capture_replay import records
from test_collect_combined import Socket

from ai_trader.ingestion import collect_combined as module


@pytest.fixture
def recorder(monkeypatch):
    available = asyncio.Event()
    wall = itertools.count(10**12, 10_000_000)
    receive = module.receive_messages

    def wall_time():
        value = next(wall)
        if value == 10**12 + 20_000_000:
            available.set()
        return value

    async def ordered_receive(*args, **kwargs):
        await available.wait()
        await receive(*args, **kwargs)

    socket = Socket(records()[2:-1])
    monkeypatch.setattr(module.time, "time_ns", wall_time)
    monkeypatch.setattr(module, "receive_messages", ordered_receive)
    monkeypatch.setattr(module, "connect", lambda *args, **kwargs: socket)
    monkeypatch.setattr(module, "fetch_snapshot", lambda: records()[1]["event"])
    return socket


def test_callback_receives_exact_durable_line_before_paper_work(tmp_path, recorder):
    path = tmp_path / "session.jsonl"
    observed = []

    def on_durable(record, receipt):
        source = path.with_suffix(
            ".jsonl.stream.partial" if receipt.file_kind == "stream" else ".jsonl.partial"
        )
        with source.open("rb") as capture:
            capture.seek(receipt.start_offset)
            line = capture.read(receipt.end_offset - receipt.start_offset)
        assert line.endswith(b"\n")
        assert hashlib.sha256(line).hexdigest() == receipt.line_sha256
        observed.append((record["record_type"], receipt.file_kind))

    result = asyncio.run(module.collect(1, output_path=path, on_durable_record=on_durable))
    assert result == (path, 1, 2)
    assert observed == [
        ("session_start", "metadata"),
        ("depth_snapshot", "metadata"),
        ("stream_event", "stream"),
        ("stream_event", "stream"),
        ("stream_event", "stream"),
        ("session_end", "metadata"),
    ]
    assert recorder.closed


def test_callback_failure_retains_partials_and_never_publishes(tmp_path, recorder):
    path = tmp_path / "session.jsonl"

    def reject_event(record, _receipt):
        if record["record_type"] == "stream_event":
            raise RuntimeError("paper journal unavailable")

    with pytest.raises(RuntimeError, match="paper journal unavailable"):
        asyncio.run(module.collect(1, output_path=path, on_durable_record=reject_event))
    assert not path.exists()
    assert path.with_suffix(".jsonl.partial").exists()
    assert path.with_suffix(".jsonl.stream.partial").exists()
    assert recorder.closed


def test_failed_fsync_does_not_deliver_event_to_paper_callback(tmp_path, recorder, monkeypatch):
    path = tmp_path / "session.jsonl"
    actual_fsync = module.os.fsync
    calls = [0]
    delivered = []

    def fail_third_fsync(fd):
        calls[0] += 1
        if calls[0] == 3:
            raise OSError("synthetic disk failure")
        return actual_fsync(fd)

    monkeypatch.setattr(module.os, "fsync", fail_third_fsync)
    with pytest.raises(OSError, match="synthetic disk failure"):
        asyncio.run(
            module.collect(
                1,
                output_path=path,
                on_durable_record=lambda record, receipt: delivered.append(record["record_type"]),
            )
        )
    assert delivered == ["session_start", "depth_snapshot"]
    assert not path.exists()
    assert path.with_suffix(".jsonl.partial").exists()
    assert recorder.closed


def test_invalid_callback_rejected_before_creating_files(tmp_path):
    path = tmp_path / "session.jsonl"
    with pytest.raises(ValueError, match="callback"):
        asyncio.run(module.collect(1, output_path=path, on_durable_record=object()))
    assert list(tmp_path.iterdir()) == []
