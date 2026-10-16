"""Fixed failure evidence, exception preservation and leak-free acquisition artifacts."""

import asyncio
import json
import runpy
from pathlib import Path

import pytest
from test_collect_combined import setup as socket_setup  # noqa: F401
from test_planned_capture import setup as acquisition_setup  # noqa: F401
from test_planned_capture_timing import timed  # noqa: F401

from ai_trader.ingestion import capture_failure as module
from ai_trader.ingestion import capture_supervisor, capture_timing, collect_combined

SECRET = "private packet / token / response body must never appear"


@pytest.mark.parametrize("code", sorted(module.CODES))
def test_each_fixed_code_preserves_exception_and_serializes_only_constants(code):
    error = RuntimeError(SECRET)
    assert module.mark_failure(error, code) is error
    detail = module.failure_details(error)
    assert detail == dict(schema_version=1, stage=code.split(".")[0], reason=code.split(".")[1])
    assert SECRET not in json.dumps(detail)


@pytest.mark.parametrize("code", ["secret", "snapshot.arbitrary", {}, None, True])
def test_unsupported_codes_refused_before_operation(code):
    with pytest.raises(ValueError):
        with module.failure_stage(code):
            pytest.fail("Invalid code entered operation.")


def test_wrappers_preserve_inner_evidence_without_stringifying_errors():
    class DangerousError(Exception):
        def __str__(self):
            pytest.fail("Exception message inspected.")

    try:
        with module.failure_stage("recording.failed"):
            try:
                with module.failure_stage("parse.invalid_message"):
                    raise DangerousError(SECRET)
            except DangerousError as error:
                raise RuntimeError(SECRET) from error
    except RuntimeError as error:
        assert module.failure_details(error)["reason"] == "invalid_message"


def test_unknown_spoofed_or_cyclic_evidence_is_bounded_and_unclassified():
    error = type(SECRET, (Exception,), {})(SECRET)
    error._capture_failure_code = {"stage": SECRET}
    error.__cause__ = error
    assert module.safe_error_type(error) == "OtherError"
    assert module.failure_details(error) == {
        "schema_version": 1,
        "stage": "unclassified",
        "reason": "unexpected_error",
    }
    error._capture_failure_code = SECRET
    assert SECRET not in json.dumps(module.failure_details(error))


def test_cause_chain_has_fixed_depth_and_implicit_context_is_not_exported():
    inner = module.mark_failure(ValueError(SECRET), "parse.invalid_message")
    outer = RuntimeError(SECRET)
    outer.__context__ = inner
    assert module.failure_details(outer)["stage"] == "unclassified"
    for _ in range(8):
        wrapper = RuntimeError(SECRET)
        wrapper.__cause__ = inner
        inner = wrapper
    assert module.failure_details(inner)["stage"] == "unclassified"


@pytest.mark.parametrize("error_class", [asyncio.CancelledError, KeyboardInterrupt])
def test_cancellation_retains_stage_without_changing_exception(error_class):
    error = error_class(SECRET)
    with pytest.raises(error_class) as caught:
        with module.failure_stage("snapshot.failed"):
            raise error
    assert caught.value is error
    assert module.failure_details(error)["reason"] == "cancelled"
    assert module.failure_details(error)["stage"] == "snapshot"


@pytest.mark.parametrize(
    "fault,code",
    [
        ("connect", "connection.transport_error"),
        ("snapshot_timeout", "snapshot.timeout"),
        ("snapshot_transport", "snapshot.transport_error"),
        ("snapshot_invalid", "snapshot.invalid_response"),
        ("disconnect", "receiver.disconnected"),
        ("malformed", "parse.invalid_message"),
        ("quota", "write.byte_limit"),
        ("observer", "observer.failed"),
        ("idle", "stream.idle_timeout"),
        ("fsync", "finalize.failed"),
        ("integrity", "integrity.rejected"),
        ("publish", "publication.failed"),
    ],
)
def test_actual_collector_failure_branches(
    tmp_path,
    socket_setup,  # noqa: F811
    monkeypatch,
    fault,
    code,
):
    if fault == "disconnect":
        socket_setup([], disconnect=True)
    elif fault == "malformed":
        socket_setup([SECRET])
    else:
        socket_setup([] if fault == "idle" else None)

    def throw(error):
        def fail(*args, **kwargs):
            raise error

        return fail

    if fault == "connect":
        monkeypatch.setattr(collect_combined, "connect", throw(OSError(SECRET)))
    elif fault.startswith("snapshot_"):
        error_type = {
            "snapshot_timeout": TimeoutError,
            "snapshot_transport": OSError,
            "snapshot_invalid": ValueError,
        }[fault]
        monkeypatch.setattr(collect_combined, "fetch_snapshot", throw(error_type(SECRET)))
    elif fault == "fsync":
        monkeypatch.setattr(collect_combined.os, "fsync", throw(OSError(SECRET)))
    elif fault == "integrity":
        monkeypatch.setattr(collect_combined, "_validate_complete", throw(ValueError(SECRET)))
    elif fault == "publish":
        monkeypatch.setattr(collect_combined.os, "link", throw(OSError(SECRET)))
    elif fault == "observer":

        async def fail_observer(*args):
            raise RuntimeError(SECRET)

        monkeypatch.setattr(capture_timing.CaptureTiming, "watch_loop", fail_observer)
    options = {}
    if fault == "quota":
        options["limits"] = collect_combined.CaptureLimits(max_bytes=1)
    elif fault == "idle":
        options["limits"] = collect_combined.CaptureLimits(idle_timeout_seconds=1)
    elif fault == "observer":
        options["timing"] = capture_timing.CaptureTiming()
    path = tmp_path / "capture.jsonl"
    with pytest.raises(Exception) as caught:
        asyncio.run(
            collect_combined.collect(10 if fault == "idle" else 1, output_path=path, **options)
        )
    detail = module.failure_details(caught.value)
    assert detail["stage"] + "." + detail["reason"] == code
    assert SECRET not in json.dumps(detail)
    assert not path.exists() and path.with_suffix(".jsonl.partial").exists()


def test_timing_failure_matches_campaign_audit_and_never_retries(timed):  # noqa: F811
    plan, run, _, _, _, invoked, _ = timed

    async def fail(*args, **kwargs):
        invoked.append(kwargs["output_path"])
        raise module.mark_failure(
            collect_combined.CaptureInterrupted(SECRET), "stream.idle_timeout"
        )

    with pytest.raises(collect_combined.CaptureInterrupted):
        run(collector=fail)
    output = Path(plan["output_dir"])
    failure = json.loads((output / "failure.json").read_text())
    audit = json.loads((output / "audit.jsonl").read_text().splitlines()[-1])
    report = json.loads((output / (plan["sessions"][0]["filename"] + ".timing.json")).read_text())[
        "report"
    ]
    assert failure["failure"] == audit["failure"] == report["failure"]
    assert failure["failure"]["reason"] == "idle_timeout"
    assert len(invoked) == 1 and not (output / "receipt.json").exists()
    assert SECRET not in json.dumps([failure, audit, report])


def test_standalone_timing_exports_safe_failure(tmp_path, monkeypatch):
    async def fail(*args, **kwargs):
        raise module.mark_failure(
            collect_combined.CaptureInterrupted(SECRET), "receiver.disconnected"
        )

    monkeypatch.setattr(collect_combined, "collect", fail)
    output = tmp_path / "diagnostic"
    with pytest.raises(collect_combined.CaptureInterrupted):
        asyncio.run(
            capture_timing.capture_with_timing(
                output_dir=output, seconds=1, enable_public_capture=True
            )
        )
    report = json.loads((output / "timing.json").read_text())["report"]
    assert report["failure"]["reason"] == "disconnected"
    assert SECRET not in json.dumps(report)


@pytest.mark.parametrize("fault", ["interrupted", "unknown"])
def test_legacy_supervisor_no_longer_exports_raw_exception_text(tmp_path, fault):
    error = (
        module.mark_failure(collect_combined.CaptureInterrupted(SECRET), "receiver.transport_error")
        if fault == "interrupted"
        else type(SECRET, (Exception,), {})(SECRET)
    )

    async def fail(*args, **kwargs):
        raise error

    path = tmp_path / "audit.jsonl"
    with pytest.raises(type(error)):
        asyncio.run(
            capture_supervisor.capture_with_retries(
                manifest_path=path, seconds=1, max_attempts=1, collector=fail
            )
        )
    raw = path.read_text()
    assert SECRET not in raw
    last = json.loads(raw.splitlines()[-1])
    assert "error" not in last and "failure" in last
    if fault == "unknown":
        assert last["error_type"] == "OtherError"


def test_collector_cli_sanitizes_failure_without_traceback(tmp_path, monkeypatch, capsys):
    path = tmp_path / "private-path.jsonl"
    path.write_text(SECRET)
    monkeypatch.setattr("sys.argv", ["collect_combined", "--seconds", "1", "--output", str(path)])
    with pytest.warns(RuntimeWarning), pytest.raises(SystemExit) as error:
        runpy.run_module("ai_trader.ingestion.collect_combined", run_name="__main__")
    assert error.value.code == 1
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["status"] == "failed" and result["error_type"] == "FileExistsError"
    assert "Traceback" not in output.err and "failure" in result
    assert path.name not in output.out and SECRET not in output.out
