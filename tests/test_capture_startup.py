"""Offline startup bursts: no network, existing captures, models or trades."""

import asyncio
import hashlib
import io
import json

import pytest
from test_capture_replay import records

from ai_trader.features.microstructure import MicrostructureConfig
from ai_trader.ingestion import collect_combined as module
from ai_trader.ingestion.capture_failure import failure_details
from ai_trader.ingestion.capture_timing import CaptureTiming
from ai_trader.trading.capture_replay import CaptureReplay, CaptureReplayConfig


@pytest.fixture
def startup(monkeypatch):
    async def quiet_watch(self, due_ns):
        await asyncio.Event().wait()

    monkeypatch.setattr(CaptureTiming, "watch_loop", quiet_watch)

    def no_network(*args, **kwargs):
        pytest.fail("Network forbidden in startup regressions.")

    monkeypatch.setattr(module.urllib.request, "urlopen", no_network)

    def install(count=1024, *, blocked=False, fault=None, trades=False):
        processed, available, hold = asyncio.Event(), asyncio.Event(), asyncio.Event()
        state = {
            "wall": 1_000_000_000,
            "parsed": 0,
            "snapshot_returned": False,
            "processed_signal": processed,
            "snapshot_cancelled": False,
        }
        receipts = []
        parse = module.parse_stream_record

        def wall():
            state["wall"] += 1_000_000
            if state["snapshot_returned"]:
                available.set()
            return state["wall"]

        def parse_record(*args):
            result = parse(*args)
            state["parsed"] += 1
            receipts.append(args[0])
            if state["parsed"] == count + int(trades):
                processed.set()
            return result

        def trade(number, quantity):
            row = records()[3]
            stamp = state["wall"] // 1_000_000 + 1
            row["event"].update(a=number, f=number, l=number, q=quantity, E=stamp, T=stamp)
            return json.dumps({"stream": row["stream"], "data": row["event"]})

        class Socket:
            closed = False

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                self.closed = True

            async def __aiter__(self):
                if trades:
                    yield trade(1, "999999")
                for number in range(count + 1):
                    if number == count:
                        await available.wait()
                    row = records()[2]
                    row["event"].update(
                        U=101 + number, u=101 + number, E=state["wall"] // 1_000_000 + 1
                    )
                    if fault == "stale" and number == 0:
                        row["event"]["E"] = 0
                        state["wall"] += 3_000_000_000
                    if fault == "malformed" and number == 0:
                        yield "not json"
                    yield json.dumps({"stream": row["stream"], "data": row["event"]})
                if trades:
                    yield trade(2, "2")
                    row["event"].update(
                        U=102 + count, u=102 + count, E=state["wall"] // 1_000_000 + 1
                    )
                    yield json.dumps({"stream": row["stream"], "data": row["event"]})
                await hold.wait()

        async def snapshot():
            try:
                await processed.wait()
                if blocked:
                    await hold.wait()
                if fault == "snapshot":
                    raise OSError("Synthetic snapshot failure")
                state["snapshot_returned"] = True
                return dict(records()[1]["event"], lastUpdateId=100 + count)
            finally:
                state["snapshot_cancelled"] = True

        socket = Socket()
        monkeypatch.setattr(module, "connect", lambda *args, **kwargs: socket)
        monkeypatch.setattr(module, "_snapshot_with_failure_code", snapshot)
        monkeypatch.setattr(module, "parse_stream_record", parse_record)
        monkeypatch.setattr(module.time, "time_ns", wall)
        return socket, state, receipts

    return install


@pytest.mark.parametrize("timed", [False, True])
@pytest.mark.parametrize("count", [257, 1024, 4096])
def test_snapshot_pending_burst_is_recorded_with_original_receipts(tmp_path, startup, timed, count):
    socket, state, receipts = startup(count)
    timing = CaptureTiming() if timed else None
    path = tmp_path / "startup.jsonl"

    async def run():
        assert await module.collect(1, output_path=path, timing=timing) == (path, 0, count + 1)
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert socket.closed and state["parsed"] == count + 1
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["record_type"] for r in rows[:2]] == ["session_start", "depth_snapshot"]
    assert [r["received_at_ns"] for r in rows[2:-1]] == receipts
    assert [r["event"]["u"] for r in rows[2:-1]] == list(range(101, 102 + count))
    assert receipts[-2] < rows[1]["received_at_ns"] < receipts[-1]
    assert list(tmp_path.iterdir()) == [path]
    module._validate_complete(path)
    if timing is not None:
        assert timing.received == timing.enqueued == timing.processed == count + 1
        assert timing.queue_high_water < 256
        assert timing.metrics["queue_wait_snapshot_buffer"].count == count
        assert timing.metrics["queue_wait"].count == 1


@pytest.mark.parametrize("case", ["blocked", "snapshot", "malformed", "events", "bytes", "stale"])
def test_startup_failures_preserve_evidence_without_publication(tmp_path, startup, case):
    socket, state, _ = startup(blocked=case == "blocked", fault=case)
    timing, path = CaptureTiming(), tmp_path / "failure.jsonl"
    limits = module.CaptureLimits(
        max_events=100 if case == "events" else 99_997,
        max_bytes=1000 if case == "bytes" else 32 * 1024 * 1024,
    )

    async def run():
        with pytest.raises((module.CaptureInterrupted, module.CaptureQuotaExceeded)) as error:
            await module.collect(1, output_path=path, limits=limits, timing=timing)
        assert (
            failure_details(error.value)["reason"]
            == {
                "blocked": "acquisition_timeout",
                "snapshot": "failed",
                "malformed": "invalid_message",
                "events": "event_limit",
                "bytes": "byte_limit",
                "stale": "stale_event",
            }[case]
        )
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert socket.closed and state["snapshot_cancelled"] and not path.exists()
    assert path.with_suffix(".jsonl.partial").exists()
    assert path.with_suffix(".jsonl.stream.partial").exists()
    assert sum(p.stat().st_size for p in tmp_path.iterdir()) <= limits.max_bytes
    if case == "blocked":
        assert timing.processed == 1024 and timing.snapshot_available_wall_ns is None


def test_cancel_during_startup_retains_staged_receipts_and_cleans_tasks(tmp_path, startup):
    socket, state, _ = startup(blocked=True)
    path = tmp_path / "cancel.jsonl"

    async def run():
        task = asyncio.create_task(module.collect(10, output_path=path))
        await asyncio.wait_for(state["processed_signal"].wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    assert socket.closed and state["snapshot_cancelled"] and not path.exists()
    staged = path.with_suffix(".jsonl.stream.partial").read_bytes()
    assert len(staged.splitlines()) == 1024
    assert b"session_end" not in path.with_suffix(".jsonl.partial").read_bytes()


def test_staged_startup_trades_cannot_seed_post_snapshot_cvd(tmp_path, startup):
    startup(512, trades=True)
    path = tmp_path / "causal.jsonl"
    assert asyncio.run(module.collect(1, output_path=path)) == (path, 2, 514)
    raw = path.read_bytes()
    replay = CaptureReplay(
        raw,
        expected_sha256=hashlib.sha256(raw).hexdigest(),
        source_session="startup-causal",
        config=CaptureReplayConfig(features=MicrostructureConfig(levels=1)),
    )
    observations = [f.observation for f in replay.frames() if f.observation is not None]
    assert [o.session_cvd_base for o in observations] == [0, 2]
    assert [o.rolling_trade_count for o in observations] == [0, 1]


def test_existing_staging_file_refused_before_connection(tmp_path, monkeypatch):
    path = tmp_path / "existing.jsonl"
    staging = path.with_suffix(".jsonl.stream.partial")
    staging.write_bytes(b"retained evidence")
    monkeypatch.setattr(module, "connect", lambda *a, **k: pytest.fail("Must not connect"))
    with pytest.raises(FileExistsError):
        asyncio.run(module.collect(1, output_path=path))
    assert staging.read_bytes() == b"retained evidence" and not path.exists()


def test_acquisition_intake_refuses_residual_staging(tmp_path, startup):
    from ai_trader.ingestion.planned_capture import _capture_metadata

    startup(257)
    path = tmp_path / "intake.jsonl"
    asyncio.run(module.collect(1, output_path=path))
    assignment = {"source_session": "intake", "filename": path.name, "split": "train"}
    assert _capture_metadata(path, assignment, earliest_ns=1, seconds=1)["depth_events"] == 258
    path.with_suffix(".jsonl.stream.partial").write_bytes(b"retained evidence")
    with pytest.raises(ValueError, match="completely published"):
        _capture_metadata(path, assignment, earliest_ns=1, seconds=1)


def test_staging_and_copy_share_original_byte_budget():
    output, staged = io.BytesIO(), io.BytesIO()
    row = {"synthetic": "receipt"}
    length = len((json.dumps(row, separators=(",", ":")) + "\n").encode())
    recording = module._CaptureRecording(output, staged, module.CaptureLimits(max_bytes=4 * length))
    recording.write(row)  # Header.
    recording.write(row, event=True)  # Reserve one staging and one final copy.
    recording.write(row)  # Snapshot: budget now fully reserved.
    with pytest.raises(module.CaptureQuotaExceeded):
        recording.write(row, event=True)
    assert staged.tell() == length
    asyncio.run(recording.assemble())
    assert len(output.getvalue()) + len(staged.getvalue()) == 4 * length
    with pytest.raises(module.CaptureQuotaExceeded):
        recording.write(row)  # No silent extra footer budget.


@pytest.mark.parametrize("fault", ["truncate", "extend", "read_error", "short_write", "cancel"])
def test_assembly_is_bounded_cancellable_and_rejects_incomplete_io(fault):
    class Staged(io.BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 64 * 1024
            if fault == "read_error":
                raise OSError("Synthetic disk read error")
            return super().read(size)

    class Output(io.BytesIO):
        def write(self, data):
            if fault == "short_write":
                return super().write(data[:-1])
            result = super().write(data)
            if fault == "cancel":
                asyncio.current_task().cancel()
            return result

    staged, output = Staged(), Output()
    recording = module._CaptureRecording(output, staged, module.DEFAULT_LIMITS)
    recording.write({"data": "x" * 140_000}, event=True)
    if fault == "truncate":
        staged.truncate(0)
    if fault == "extend":
        staged.write(b"extra")

    async def run():
        task = asyncio.create_task(recording.assemble())
        with pytest.raises(asyncio.CancelledError if fault == "cancel" else OSError):
            await task
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(run())
    if fault == "cancel":
        assert len(output.getvalue()) == 64 * 1024
