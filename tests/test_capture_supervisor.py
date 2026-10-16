"""Finite reconnect budgets and durable audit outcomes, using injected collectors."""

import asyncio
import json

import pytest

from ai_trader.ingestion.capture_supervisor import capture_with_retries
from ai_trader.ingestion.collect_combined import CaptureInterrupted, CaptureQuotaExceeded


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_fresh_path_each_attempt_and_bounded_backoff(tmp_path):
    paths, sleeps = [], []
    manifest = tmp_path / "audit.jsonl"

    async def collect(seconds, *, output_path, limits):
        assert seconds == 30
        paths.append(output_path)
        if len(paths) == 1:
            output_path.with_suffix(".jsonl.partial").write_bytes(b"failed session")
            raise CaptureInterrupted("disconnect")
        output_path.write_bytes(b"synthetic published capture")
        return output_path, 1, 2

    async def sleep(seconds):
        sleeps.append(seconds)

    result = asyncio.run(
        capture_with_retries(
            manifest_path=manifest, seconds=30, max_attempts=3, collector=collect, sleeper=sleep
        )
    )
    assert result == (paths[1], 1, 2)
    assert len(set(paths)) == 2 and sleeps == [2]
    assert paths[0].with_suffix(".jsonl.partial").read_bytes() == b"failed session"
    assert [r["status"] for r in rows(manifest)] == [
        "started",
        "attempt_started",
        "attempt_failed",
        "attempt_started",
        "completed",
    ]


@pytest.mark.parametrize(
    "failure, attempts",
    [
        (CaptureInterrupted("disconnected"), 3),
        (CaptureQuotaExceeded("full"), 1),
        (OSError("disk full"), 1),
        (ValueError("programming/contract error"), 1),
    ],
)
def test_retry_only_known_transient_errors(tmp_path, failure, attempts):
    calls = []
    manifest = tmp_path / "audit.jsonl"

    async def collect(seconds, **kwargs):
        calls.append(kwargs["output_path"])
        raise failure

    with pytest.raises(type(failure)):
        asyncio.run(
            capture_with_retries(
                manifest_path=manifest,
                seconds=30,
                max_attempts=3,
                retry_delay_seconds=0,
                collector=collect,
            )
        )
    assert len(calls) == attempts
    assert rows(manifest)[-1]["status"] == "failed"


@pytest.mark.parametrize("during_backoff", [False, True])
def test_cancellation_records_terminal_audit_and_stops(tmp_path, during_backoff):
    manifest = tmp_path / "audit.jsonl"
    calls = []

    async def collect(seconds, **kwargs):
        calls.append(1)
        if during_backoff:
            raise CaptureInterrupted("mock disconnect")
        raise asyncio.CancelledError

    async def sleeper(seconds):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            capture_with_retries(
                manifest_path=manifest,
                seconds=30,
                max_attempts=3,
                collector=collect,
                sleeper=sleeper,
            )
        )
    assert len(calls) == 1
    assert rows(manifest)[-1]["status"] == "cancelled"


def test_existing_audit_never_overwritten_or_network_started(tmp_path):
    manifest = tmp_path / "audit.jsonl"
    manifest.write_bytes(b"old audit")

    async def forbidden(*args, **kwargs):
        pytest.fail("No collector call allowed.")

    with pytest.raises(FileExistsError):
        asyncio.run(capture_with_retries(manifest_path=manifest, seconds=30, collector=forbidden))
    assert manifest.read_bytes() == b"old audit"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"max_attempts": 6},
        {"max_attempts": True},
        {"retry_delay_seconds": -1},
        {"retry_delay_seconds": 61},
        {"seconds": 3601},
        {"limits": None},
    ],
)
def test_invalid_budget_has_no_side_effect(tmp_path, kwargs):
    args = {"manifest_path": tmp_path / "audit.jsonl", "seconds": 30, **kwargs}
    with pytest.raises(ValueError):
        asyncio.run(capture_with_retries(**args))
    assert not list(tmp_path.iterdir())
