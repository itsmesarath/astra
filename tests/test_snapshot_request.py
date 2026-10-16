"""Snapshot request phases and late completion, using synthetic responses only."""

import asyncio
import json
from email.message import Message
from urllib.error import HTTPError, URLError

import pytest
from test_capture_replay import records
from test_collect_combined import setup as socket_setup  # noqa: F401

from ai_trader.ingestion import collect_combined as module
from ai_trader.ingestion.capture_failure import failure_details
from ai_trader.ingestion.capture_timing import capture_with_timing

SECRET = "private-url-or-header-must-not-be-exported"


@pytest.mark.parametrize("phase", ["open", "read"])
@pytest.mark.parametrize("via_thread", [False, True])
def test_snapshot_timeout_retains_phase_across_worker(monkeypatch, phase, via_thread):
    calls, closed = [], []

    class Response:
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.append(True)

        def read1(self, size):
            raise TimeoutError(SECRET)

    def open_response(url, *, timeout):
        calls.append((url, timeout))
        if phase == "open":
            raise TimeoutError(SECRET)
        return Response()

    monkeypatch.setattr(module.urllib.request, "urlopen", open_response)
    with pytest.raises(TimeoutError) as caught:
        if via_thread:
            asyncio.run(module._snapshot_with_failure_code())
        else:
            module.fetch_snapshot()
    assert failure_details(caught.value)["reason"] == phase + "_timeout"
    assert SECRET not in str(caught.value)
    assert len(calls) == 1 and calls[0][1] == 10
    assert calls[0][0].full_url == module.SNAPSHOT_URL
    assert calls[0][0].get_header("Accept-encoding") == "gzip"
    assert bool(closed) == (phase == "read")


@pytest.mark.parametrize("wrapped", [False, True])
def test_open_transport_errors_are_distinct_from_timeouts(monkeypatch, wrapped):
    def fail(*args, **kwargs):
        error = OSError(SECRET)
        raise URLError(error) if wrapped else error

    monkeypatch.setattr(module.urllib.request, "urlopen", fail)
    with pytest.raises(OSError) as caught:
        asyncio.run(module._snapshot_with_failure_code())
    assert failure_details(caught.value)["reason"] == "open_transport_error"


def test_wrapped_open_timeout_is_not_generic_transport_error(monkeypatch):
    def fail(*args, **kwargs):
        raise URLError(TimeoutError(SECRET))

    monkeypatch.setattr(module.urllib.request, "urlopen", fail)
    with pytest.raises(TimeoutError) as caught:
        asyncio.run(module._snapshot_with_failure_code())
    assert failure_details(caught.value)["reason"] == "open_timeout"
    assert SECRET not in str(caught.value)


def test_http_error_is_closed_and_exported_without_status_text(monkeypatch):
    closed = []

    class Body:
        def close(self):
            closed.append(True)

    def fail(*args, **kwargs):
        raise HTTPError(SECRET, 429, SECRET, {"private": SECRET}, Body())

    monkeypatch.setattr(module.urllib.request, "urlopen", fail)
    with pytest.raises(OSError) as caught:
        asyncio.run(module._snapshot_with_failure_code())
    assert failure_details(caught.value)["reason"] == "http_error"
    assert closed and SECRET not in json.dumps(failure_details(caught.value))


@pytest.mark.parametrize("late_phase", ["open", "last_chunk", "eof", "validation"])
@pytest.mark.parametrize("late_at", [10, 11])
def test_late_snapshot_completion_is_rejected(monkeypatch, late_phase, late_at):
    clock, calls, closed = [0.0], [], []
    payload = records()[1]["event"]
    chunks = iter([json.dumps(payload).encode(), b""])
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    validate = module.PartialDepthSnapshot.from_event

    def validation(event):
        result = validate(event)
        if late_phase == "validation":
            clock[0] = late_at
        return result

    class Response:
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.append(True)

        def read1(self, size):
            chunk = next(chunks)
            if (late_phase == "last_chunk" and chunk) or (late_phase == "eof" and not chunk):
                clock[0] = late_at
            return chunk

    def open_response(url, *, timeout):
        calls.append((url, timeout))
        if late_phase == "open":
            clock[0] = late_at
        return Response()

    monkeypatch.setattr(module.urllib.request, "urlopen", open_response)
    monkeypatch.setattr(module.PartialDepthSnapshot, "from_event", validation)
    with pytest.raises(TimeoutError) as caught:
        module.fetch_snapshot()
    assert failure_details(caught.value)["reason"] == "deadline"
    assert len(calls) == 1 and closed


@pytest.mark.parametrize("wrapped", [False, True])
def test_read_transport_failure_retains_phase_and_closes_response(monkeypatch, wrapped):
    closed = []

    class Response:
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.append(True)

        def read1(self, size):
            error = OSError(SECRET)
            raise URLError(error) if wrapped else error

    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *a, **k: Response())
    with pytest.raises(OSError) as caught:
        asyncio.run(module._snapshot_with_failure_code())
    assert failure_details(caught.value)["reason"] == "read_transport_error"
    assert closed


@pytest.mark.parametrize("error_type", [OSError, TimeoutError])
def test_http_error_cleanup_fault_is_not_hidden_by_original_status(monkeypatch, error_type):
    class Body:
        def close(self):
            raise error_type(SECRET)

    def fail(*args, **kwargs):
        raise HTTPError(SECRET, 500, SECRET, {}, Body())

    monkeypatch.setattr(module.urllib.request, "urlopen", fail)
    with pytest.raises(error_type) as caught:
        asyncio.run(module._snapshot_with_failure_code())
    assert failure_details(caught.value)["reason"] == "close_error"
    assert SECRET not in json.dumps(failure_details(caught.value))


@pytest.mark.parametrize(
    "fault", ["open_timeout", "read_timeout", "wrapped", "http_error", "read_transport_error"]
)
def test_real_timing_report_contains_safe_phase_and_does_not_retry(
    tmp_path,
    monkeypatch,
    socket_setup,  # noqa: F811
    fault,
):
    fetch = module.fetch_snapshot
    socket = socket_setup([])
    monkeypatch.setattr(module, "fetch_snapshot", fetch)
    calls, closed = [], []

    class Response:
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.append(True)

        def read1(self, size):
            if fault == "read_transport_error":
                raise OSError(SECRET)
            raise TimeoutError(SECRET)

    def fail(*args, **kwargs):
        calls.append(True)
        if fault == "open_timeout":
            raise TimeoutError(SECRET)
        if fault == "wrapped":
            raise URLError(TimeoutError(SECRET))
        if fault == "http_error":
            raise HTTPError(SECRET, 429, SECRET, {}, None)
        return Response()

    monkeypatch.setattr(module.urllib.request, "urlopen", fail)
    output = tmp_path / "new-diagnostic"

    async def run():
        with pytest.raises(module.CaptureInterrupted):
            await capture_with_timing(output_dir=output, seconds=1, enable_public_capture=True)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    raw_report = (output / "timing.json").read_text()
    report = json.loads(raw_report)["report"]
    assert report["failure"]["reason"] == ("open_timeout" if fault == "wrapped" else fault)
    assert report["status"] == "failed" and report["source_sha256"] is None
    assert report["orders"] == report["model_calls"] == 0
    assert all(
        report[key] is False
        for key in ("training_allowed", "promotion_allowed", "execution_allowed")
    )
    assert SECRET not in raw_report
    assert len(calls) == 1 and socket.closed
    assert not (output / "capture.jsonl").exists()
    assert (output / "capture.jsonl.partial").exists()
    assert (output / "capture.jsonl.stream.partial").exists()
    assert bool(closed) == fault.startswith("read_")


def test_valid_snapshot_just_before_deadline_keeps_payload_and_request_budget(monkeypatch):
    clock, calls = [0.0], []
    payload = records()[1]["event"]
    chunks = iter([json.dumps(payload).encode(), b""])
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    class Response:
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read1(self, count):
            assert 0 < count <= 64 * 1024
            chunk = next(chunks)
            if not chunk:
                clock[0] = 9.999
            return chunk

    def open_response(url, *, timeout):
        calls.append((url, timeout))
        return Response()

    monkeypatch.setattr(module.urllib.request, "urlopen", open_response)
    assert module.fetch_snapshot() == payload
    assert len(calls) == 1 and calls[0][1] == 10
    assert calls[0][0].full_url == module.SNAPSHOT_URL
    assert calls[0][0].get_header("Accept-encoding") == "gzip"
