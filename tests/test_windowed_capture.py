"""Synthetic-only window runtime, durability, time faults and recorder admission."""

import asyncio
import copy
import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest
from test_capture_replay import records
from test_capture_schedule import PREPARED, prepared, sha  # noqa: F401
from test_collect_combined import setup as socket_setup  # noqa: F401

from ai_trader.ingestion import capture_schedule, collect_combined, planned_capture
from ai_trader.ingestion import windowed_capture as module
from ai_trader.ingestion.capture_failure import failure_details

NS = module.NS


@pytest.fixture
def runtime(prepared, tmp_path, monkeypatch):  # noqa: F811
    args, _ = prepared
    schedule = capture_schedule.prepare_schedule(**args, runnable=True)
    path = tmp_path / "windows.json"
    pin = module.write_new(path, schedule)
    now = [PREPARED + NS, 100 * NS]
    calls, sleeps, cleanups = [], [], []
    monkeypatch.setattr(planned_capture.time, "time_ns", lambda: now[0])

    def advance(ns):
        now[0] += ns
        now[1] += ns

    async def sleeper(seconds):
        assert 0 < seconds <= 1
        sleeps.append(seconds)
        advance(round(seconds * NS))
        await asyncio.sleep(0)

    async def collector(seconds, *, output_path, limits, start_guard, **kwargs):
        calls.append(output_path)
        audit = [
            json.loads(line)
            for line in (output_path.parent / "audit.jsonl").read_text().splitlines()
        ]
        assert audit[-1]["status"] == "session_started"
        assert audit[-1]["filename"] == output_path.name
        advance(NS)
        start_guard(now[0])
        rows = records()
        offset = now[0] - rows[0]["started_at_ns"]
        rows[0]["started_at_ns"] += offset
        rows[1]["requested_at_ns"] += offset
        rows[1]["received_at_ns"] += offset
        for row in rows[2:-1]:
            row["received_at_ns"] += offset
            for name in ("E", "T"):
                if name in row["event"]:
                    row["event"][name] += offset // 1_000_000
        rows[-1]["ended_at_ns"] = now[0] + seconds * NS
        if "reserved" in output_path.name:
            assert not kwargs
        else:
            timing = kwargs["timing"]
            timing.claim()
            wall = rows[1]["received_at_ns"]
            timing.snapshot_available(wall, wall)
            timing._observe("event_loop_lag", 0, wall, wall)
            for row in rows[2:-1]:
                wall = row["received_at_ns"]
                timing.receive(wall, wall)
                timing.queued(1)
                timing.consumed(row, wall, wall, wall + 1)
        output_path.write_text("".join(json.dumps(r) + "\n" for r in rows))
        advance((seconds + 1) * NS)
        return output_path, 1, 2

    def run(**changes):
        options = dict(
            enable_public_capture=True,
            collector=collector,
            sleeper=sleeper,
            wall_clock=lambda: now[0],
            monotonic_clock=lambda: now[1],
        )

        async def task():
            try:
                return await module.run_schedule(path, pin, **(options | changes))
            finally:
                cleanups.append(asyncio.all_tasks() == {asyncio.current_task()})

        return asyncio.run(task())

    return dict(
        args=args,
        schedule=schedule,
        path=path,
        pin=pin,
        now=now,
        advance=advance,
        collector=collector,
        sleeper=sleeper,
        calls=calls,
        sleeps=sleeps,
        run=run,
        cleanups=cleanups,
        output=args["output_dir"],
    )


def test_v2_explicit_selection_and_v1_remains_unchanged(prepared, tmp_path):  # noqa: F811
    args, old = prepared
    assert old["schema_version"] == 1 and not old["runtime_available"]
    new = capture_schedule.prepare_schedule(**args, runnable=True)
    assert new["schema_version"] == 2 and new["runtime_available"] is True
    assert new["runtime"] == capture_schedule.RUNTIME
    assert new["authority"] == old["authority"]
    capture_schedule.validate_schedule(old)
    bad = copy.deepcopy(new)
    bad["runtime"]["completion_grace_ns"] += 1
    with pytest.raises(ValueError):
        capture_schedule.validate_schedule(bad)
    with pytest.raises(ValueError):
        capture_schedule.prepare_schedule(**args, runnable=1)


@pytest.mark.parametrize("opt_in", [False, None, True + 0, "yes"])
def test_explicit_opt_in_precedes_schedule_access(opt_in):
    with pytest.raises(ValueError, match="opt-in"):
        asyncio.run(module.run_schedule(Path("missing"), "a" * 64, enable_public_capture=opt_in))


def test_v1_cannot_be_run_even_with_capture_opt_in(prepared, tmp_path):  # noqa: F811
    path = tmp_path / "old.json"
    pin = module.write_new(path, prepared[1])
    with pytest.raises(ValueError, match="V2"):
        asyncio.run(module.run_schedule(path, pin, enable_public_capture=True))
    assert not prepared[0]["output_dir"].exists()


def test_complete_campaign_has_exact_all_slot_evidence_and_no_authority(runtime):
    result = runtime["run"]()
    assert result["status"] == "completed"
    assert len(runtime["calls"]) == 3
    assert len(runtime["sleeps"]) > 6000  # Virtual hours, not wall-clock waiting.
    assert all(runtime["cleanups"])
    assert result["model_calls"] == result["orders"] == result["optimization_steps"] == 0
    assert result["authority"] == module.AUTHORITY
    assert [s["split"] for s in result["sessions"]] == ["train", "validation", "reserved"]
    output = runtime["output"]
    assert not (output / "failure.json").exists()
    assert not (output / "plan.json").exists()  # No downgraded back-to-back receipt path.
    assert sha(output / "schedule.json") == result["schedule_copy_sha256"]
    audit = [json.loads(line) for line in (output / "audit.jsonl").read_text().splitlines()]
    assert [r["status"] for r in audit] == ["started"] + [
        "session_started",
        "session_connected",
        "session_completed",
    ] * 3 + ["receipt_prepared"]
    assert audit[-1]["receipt_sha256"] == sha(output / "receipt.json")
    for item, window in zip(result["sessions"], runtime["schedule"]["windows"], strict=True):
        evidence = item["window_evidence"]
        assert window["open_at_ns"] <= evidence["dispatched_at_ns"] <= window["last_dispatch_at_ns"]
        assert evidence["started_at_ns"] == item["source"]["started_at_ns"]
        if item["split"] == "reserved":
            assert item["timing"] is None
        else:
            report = json.loads((output / item["timing"]["filename"]).read_text())["report"]
            assert report["plan_sha256"] == runtime["pin"]
    before = {p: p.read_bytes() for p in output.iterdir()}
    with pytest.raises(FileExistsError):
        runtime["run"]()
    assert before == {p: p.read_bytes() for p in output.iterdir()}


def failure(runtime, reason, *, calls=0):
    output = runtime["output"]
    report = json.loads((output / "failure.json").read_text())
    assert report["status"] == "failed"
    assert report["failure"] == {"schema_version": 1, "stage": "schedule", "reason": reason}
    assert not (output / "receipt.json").exists()
    audit = [json.loads(line) for line in (output / "audit.jsonl").read_text().splitlines()]
    assert audit[-1]["failure"] == report["failure"]
    assert audit[-1]["timestamp_basis"] == "last_valid_clock_sample"
    assert len(runtime["calls"]) == calls
    assert all(runtime["cleanups"])
    return report


def test_starting_after_window_is_claimed_failed_not_caught_up(runtime):
    runtime["advance"](100 * NS)
    with pytest.raises(module.CaptureInterrupted):
        runtime["run"]()
    failure(runtime, "missed_window")
    with pytest.raises(FileExistsError):
        runtime["run"]()


def test_oversleep_misses_slot_without_replacement(runtime):
    async def oversleep(seconds):
        runtime["advance"](100 * NS)

    with pytest.raises(module.CaptureInterrupted):
        runtime["run"](sleeper=oversleep)
    failure(runtime, "missed_window")


@pytest.mark.parametrize("which", [0, 1])
def test_regressed_wall_or_monotonic_clock_preserves_failure(runtime, which):
    async def backward(seconds):
        runtime["now"][which] -= NS

    with pytest.raises(module.CaptureInterrupted):
        runtime["run"](sleeper=backward)
    failure(runtime, "clock_regression")


def test_stalled_monotonic_clock_does_not_busy_loop(runtime):
    async def stalled(seconds):
        pass

    with pytest.raises(module.CaptureInterrupted):
        runtime["run"](sleeper=stalled)
    failure(runtime, "clock_stalled")


def test_frozen_wall_clock_still_expires_against_monotonic_deadline(runtime):
    async def monotonic_only(seconds):
        runtime["now"][1] += NS

    with pytest.raises(module.CaptureInterrupted):
        runtime["run"](sleeper=monotonic_only)
    failure(runtime, "missed_window")


def test_wall_forward_jump_does_not_dispatch_before_monotonic_open(runtime):
    async def jump(seconds):
        runtime["now"][0] += 100 * NS
        runtime["now"][1] += NS

    with pytest.raises(module.CaptureInterrupted):
        runtime["run"](sleeper=jump)
    failure(runtime, "missed_window")


def test_cancellation_while_waiting_is_terminal(runtime):
    async def cancel(seconds):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        runtime["run"](sleeper=cancel)
    failure(runtime, "cancelled")


def test_late_connection_rejected_by_guard(runtime):
    async def late(*args, start_guard, **kwargs):
        runtime["advance"](11 * NS)
        start_guard(runtime["now"][0])
        pytest.fail("Late connection proceeded")

    with pytest.raises(ValueError):
        runtime["run"](collector=late)
    failure(runtime, "connected_late")


def test_collector_must_use_guard_before_a_success_can_publish(runtime):
    async def omitted(*args, **kwargs):
        return None

    with pytest.raises(module.CaptureInterrupted):
        runtime["run"](collector=omitted)
    failure(runtime, "start_guard_missing")


def test_deadline_cancels_and_drains_hanging_collector(runtime):
    cleaned = []

    async def hangs(*args, start_guard, **kwargs):
        runtime["advance"](NS)
        start_guard(runtime["now"][0])
        runtime["advance"](200 * NS)
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.append(True)

    with pytest.raises(module.CaptureInterrupted):
        runtime["run"](collector=hangs)
    assert cleaned == [True]
    failure(runtime, "completion_timeout")


def test_later_slot_failure_retains_success_without_using_a_subset(runtime):
    async def fail_second(*args, **kwargs):
        if runtime["calls"]:
            raise OSError("untrusted packet password must not be exported")
        return await runtime["collector"](*args, **kwargs)

    with pytest.raises(OSError):
        runtime["run"](collector=fail_second)
    output = runtime["output"]
    report = json.loads((output / "failure.json").read_text())
    assert [s["status"] for s in report["sessions"]] == ["completed", "failed", "not_started"]
    assert all("password" not in p.read_text() for p in output.iterdir())
    assert not (output / "receipt.json").exists()
    assert len(runtime["calls"]) == 1


def test_binding_drift_during_wait_prevents_collection(runtime, monkeypatch):
    async def changed(seconds):
        await runtime["sleeper"](seconds)
        monkeypatch.setattr(planned_capture, "_implementation_hash", lambda: "b" * 64)

    with pytest.raises(ValueError, match="runtime changed"):
        runtime["run"](sleeper=changed)
    assert not runtime["calls"]
    report = json.loads((runtime["output"] / "failure.json").read_text())
    assert report["failure"]["reason"] == "binding_mismatch"


@pytest.mark.parametrize("status", ["session_started", "session_connected"])
def test_durable_audit_stall_cannot_start_late_collection(runtime, monkeypatch, status):
    original, stalled = module.os.fsync, []

    def fsync(fd):
        original(fd)
        audit = runtime["output"] / "audit.jsonl"
        if audit.exists() and audit.stat().st_size and not stalled:
            last = json.loads(audit.read_text().splitlines()[-1])
            if last["status"] == status:
                stalled.append(True)
                runtime["advance"]((31 if status == "session_started" else 11) * NS)

    monkeypatch.setattr(module.os, "fsync", fsync)
    with pytest.raises(module.CaptureInterrupted):
        runtime["run"]()
    connected = status == "session_connected"
    failure(runtime, "connected_late" if connected else "missed_window", calls=int(connected))
    assert stalled == [True]
    assert not list(runtime["output"].glob("*-train.jsonl"))


def test_completion_publication_rechecks_deadline(runtime, monkeypatch):
    original = module._bounded_capture

    async def delayed(*args):
        result = await original(*args)
        runtime["advance"](200 * NS)
        return result

    monkeypatch.setattr(module, "_bounded_capture", delayed)
    with pytest.raises(module.CaptureInterrupted):
        runtime["run"]()
    failure(runtime, "completion_timeout", calls=1)


def test_cancellation_during_collection_drains_child(runtime):
    cleaned = []

    async def cancel(*args, start_guard, **kwargs):
        runtime["advance"](NS)
        start_guard(runtime["now"][0])
        try:
            raise asyncio.CancelledError
        finally:
            cleaned.append(True)

    with pytest.raises(asyncio.CancelledError):
        runtime["run"](collector=cancel)
    failure(runtime, "cancelled")
    assert cleaned == [True]


def test_concurrent_claims_allow_exactly_one_campaign(runtime):
    async def race():
        options = dict(
            enable_public_capture=True,
            collector=runtime["collector"],
            sleeper=runtime["sleeper"],
            wall_clock=lambda: runtime["now"][0],
            monotonic_clock=lambda: runtime["now"][1],
        )
        results = await asyncio.gather(
            *[module.run_schedule(runtime["path"], runtime["pin"], **options) for _ in range(2)],
            return_exceptions=True,
        )
        assert asyncio.all_tasks() == {asyncio.current_task()}
        return results

    results = asyncio.run(race())
    assert sum(type(r) is FileExistsError for r in results) == 1
    assert sum(type(r) is dict and r["status"] == "completed" for r in results) == 1
    assert len(runtime["calls"]) == 3
    assert not (runtime["output"] / "failure.json").exists()


def test_process_death_retains_durable_intent_and_prevents_resume(runtime):
    # A genuinely terminated child, not a caught exception, using no network/data source.
    script = """
import asyncio, os, sys
from ai_trader.ingestion import planned_capture, windowed_capture
planned_capture._implementation_hash = lambda: "a" * 64
planned_capture._environment = lambda: "synthetic-environment"
async def crash(*args, **kwargs):
    os._exit(23)
asyncio.run(windowed_capture.run_schedule(
    sys.argv[1], sys.argv[2], enable_public_capture=True, collector=crash,
    wall_clock=lambda: int(sys.argv[3]), monotonic_clock=lambda: 100_000_000_000,
))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(runtime["path"]),
            runtime["pin"],
            str(runtime["schedule"]["windows"][0]["open_at_ns"]),
        ],
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 23, result.stderr.decode(errors="replace")
    before = {p: p.read_bytes() for p in runtime["output"].iterdir()}
    audit = [
        json.loads(row) for row in (runtime["output"] / "audit.jsonl").read_text().splitlines()
    ]
    assert [row["status"] for row in audit] == ["started", "session_started"]
    assert not (runtime["output"] / "receipt.json").exists()
    assert not (runtime["output"] / "failure.json").exists()  # Abrupt death cannot log failure.
    with pytest.raises(FileExistsError):
        runtime["run"]()
    assert before == {p: p.read_bytes() for p in runtime["output"].iterdir()}


def test_receipt_publication_failure_quarantines_even_published_bytes(runtime, monkeypatch):
    original = module.write_new

    def fail_after_publication(path, value):
        result = original(path, value)
        if path.name == "receipt.json":
            raise OSError("private disk context")
        return result

    monkeypatch.setattr(module, "write_new", fail_after_publication)
    with pytest.raises(OSError):
        runtime["run"]()
    output = runtime["output"]
    assert (output / "receipt.json").exists()
    assert (output / "failure.json").exists()
    assert all("private disk context" not in p.read_text() for p in output.iterdir())
    from ai_trader.research.windowed_trial import load_completed_schedule

    with pytest.raises(ValueError, match="quarantined"):
        load_completed_schedule(
            schedule_path=runtime["path"],
            schedule_sha256=runtime["pin"],
            receipt_sha256=sha(output / "receipt.json"),
            audit_sha256=sha(output / "audit.jsonl"),
        )
    with pytest.raises(FileExistsError):
        runtime["run"]()


def test_real_collector_calls_guard_after_connection_before_snapshot_or_stream(
    socket_setup,  # noqa: F811
    tmp_path,
    monkeypatch,
):
    socket = socket_setup()
    invoked = []

    def forbidden():
        pytest.fail("Snapshot requested after rejected admission")

    def guard(started):
        invoked.append(started)
        raise module.mark_failure(module.CaptureInterrupted("secret"), "schedule.connected_late")

    monkeypatch.setattr(collect_combined, "fetch_snapshot", forbidden)
    path = tmp_path / "refused.jsonl"
    with pytest.raises(module.CaptureInterrupted) as error:
        asyncio.run(collect_combined.collect(1, output_path=path, start_guard=guard))
    assert failure_details(error.value)["reason"] == "connected_late"
    assert len(invoked) == 1 and socket.closed
    assert not socket.cleaned  # Receiver iterator was never started.
    assert path.with_suffix(".jsonl.partial").read_bytes() == b""
    assert not path.exists()


def test_real_collector_admitted_capture_retains_same_start_timestamp(socket_setup, tmp_path):  # noqa: F811
    socket_setup()
    starts = []
    path = tmp_path / "admitted.jsonl"
    asyncio.run(collect_combined.collect(1, output_path=path, start_guard=starts.append))
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert starts == [rows[0]["started_at_ns"]]


def test_cli_without_opt_in_refuses_without_network_or_raw_traceback(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["windowed_capture", "--schedule", "missing.json", "--schedule-sha256", "a" * 64],
    )
    monkeypatch.delitem(sys.modules, module.__name__)
    with pytest.raises(SystemExit) as error:
        runpy.run_module(module.__name__, run_name="__main__")
    assert error.value.code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "failed"
    assert "missing.json" not in json.dumps(output)
