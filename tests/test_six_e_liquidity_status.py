"""Status reads cannot turn progress or a matching receipt into authority."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from ai_trader.research import six_e_liquidity_status as s


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def run(tmp_path):
    (tmp_path / "logs").mkdir()
    output = tmp_path / "data/processed/run"
    output.mkdir(parents=True)
    registration = tmp_path / "logs/registration.json"
    protocol = {
        "version": "six_e_whole_liquidity_development_v1",
        **dict.fromkeys(s.FALSE_FLAGS, False),
    }
    sources = [{"entry": {"utc_date": day}} for day in ("2025-04-07", "2025-04-08")]
    frozen = {"sources": sources, "protocol": protocol, "implementation_sha256": {"x": "a" * 64}}
    pin = write(registration, frozen)
    request = {"registration_sha256": pin, "protocol": protocol}
    write(output / "request.json", request)
    return tmp_path, registration, pin, output, frozen, request


def progress(output, cpu=False):
    values = []
    for i, day in enumerate(("2025-04-07", "2025-04-08")):
        if not cpu:
            values.append(
                {
                    "event": "native_session_started",
                    "utc_date": day,
                    "utc": f"2026-10-04T16:0{i}:00Z",
                }
            )
        values.append(
            {
                "event": "cpu_session_completed" if cpu else "session_completed",
                "utc_date": day,
                "rows": 10,
                "utc": f"2026-10-04T16:0{i}:01Z",
            }
        )
    return values


def journal(output, values, partial=b""):
    (output / "progress.jsonl").write_bytes(
        b"".join(json.dumps(v).encode() + b"\n" for v in values) + partial
    )


def terminal(run, cpu=False):
    root, registration, pin, output, frozen, request = run
    if cpu:
        request.update(build=str(root / "data/processed/source"), build_sha256="b" * 64)
        write(output / "request.json", request)
    journal(output, progress(output, cpu))
    flags = {**dict.fromkeys(s.FALSE_FLAGS, False), "cpu_training": cpu}
    completed = {
        "status": s.STATES["cpu_evaluation" if cpu else "collection"][0],
        "registration_sha256": pin,
        "protocol": frozen["protocol"],
        "request_sha256": hashlib.sha256((output / "request.json").read_bytes()).hexdigest(),
        "implementation_sha256": frozen["implementation_sha256"],
        "flags": flags,
        "days": [
            {"utc_date": source["entry"]["utc_date"], "rows": 10} for source in frozen["sources"]
        ],
    }
    if cpu:
        completed["build_sha256"] = request["build_sha256"]
    completion_pin = write(output / "completion.json", completed)
    receipt = {
        "status": s.STATES["cpu_evaluation" if cpu else "collection"][1],
        "completion_sha256": completion_pin,
        "sessions": 2,
        "rows": 20,
        "flags": flags,
    }
    write(output / "verification.json", receipt)
    return completed, receipt, completion_pin


def snap(run, completion_pin=None):
    return s.snapshot(*run[:4], completion_pin)


def test_progress_is_not_liveness_or_permission(run):
    journal(run[3], progress(run[3])[:2])
    result = snap(run)
    assert result["completed_sessions"] == 1
    assert result["status"] == "progress_metadata_unverified"
    assert result["process_checked"] is False
    assert result["permission_to_start_or_resume"] is False
    assert result["full_content_verified_by_this_check"] is False


def test_partial_append_is_not_corruption(run):
    journal(run[3], progress(run[3])[:2], b'{"event":"native_')
    result = snap(run)
    assert result["completed_sessions"] == 1 and result["partial_tail"] is True
    (run[3] / "completion.json").write_bytes(b'{"status":')
    assert snap(run)["status"] == "concurrent_snapshot_unverified"


@pytest.mark.parametrize("cpu", [False, True])
def test_receipt_is_metadata_only_even_with_external_pin(run, monkeypatch, cpu):
    _, _, pin = terminal(run, cpu)
    original = Path.open
    allowed = {
        run[1].name,
        "request.json",
        "progress.jsonl",
        "completion.json",
        "verification.json",
    }

    def bounded_open(path, mode="r", *args, **kwargs):
        assert path.name in allowed and mode == "rb"
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", bounded_open)
    result = snap(run, pin)
    assert result["status"] == "pinned_receipt_matches_metadata_not_revalidated"
    assert result["rows"] == 20 and result["trading_enabled"] is False
    assert result["full_content_verified_by_this_check"] is False
    assert snap(run)["status"] == "unpinned_receipt_matches_metadata_not_revalidated"


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "skipped",
        "reversed_utc",
        "completion_without_start",
        "bool_rows",
        "unknown_event",
    ],
)
def test_bad_progress_prefix_is_refused(run, mutation):
    events = progress(run[3])
    if mutation == "duplicate":
        events.insert(2, deepcopy(events[1]))
    elif mutation == "skipped":
        events = events[2:]
    elif mutation == "reversed_utc":
        events[1]["utc"] = "2026-10-04T15:00:00Z"
    elif mutation == "completion_without_start":
        events = events[1:]
    elif mutation == "bool_rows":
        events[1]["rows"] = True
    else:
        events[0]["event"] = "training_started"
    journal(run[3], events)
    with pytest.raises(ValueError):
        snap(run)


@pytest.mark.parametrize(
    "mutation", ["flag", "cohort", "request", "source", "receipt", "external_pin"]
)
def test_repinning_metadata_cannot_create_authority(run, mutation):
    completed, receipt, pin = terminal(run)
    if mutation == "flag":
        completed["flags"]["promotion_allowed"] = True
    elif mutation == "cohort":
        completed["days"] = completed["days"][:1]
    elif mutation == "request":
        completed["request_sha256"] = "0" * 64
    elif mutation == "source":
        completed["implementation_sha256"] = {"x": "c" * 64}
    elif mutation == "receipt":
        receipt["rows"] = 19
    else:
        pin = "0" * 64
    if mutation != "external_pin":
        pin = write(run[3] / "completion.json", completed)
        receipt["completion_sha256"] = pin
        write(run[3] / "verification.json", receipt)
    with pytest.raises(ValueError):
        snap(run, pin)


def test_failure_wins_over_matching_completion(run):
    _, _, pin = terminal(run)
    write(
        run[3] / "failure.json",
        {
            "registration_sha256": run[2],
            "status": "failed_no_subset_or_retry",
            "exception": "TimeoutError",
            "message": "not echoed",
        },
    )
    result = snap(run, pin)
    assert result["status"] == "failure_metadata_present_no_retry"
    assert "message" not in result and result["exception"] == "TimeoutError"


def test_registration_pin_and_outside_paths_are_refused(run, tmp_path):
    with pytest.raises(ValueError, match="registration pin"):
        s.snapshot(run[0], run[1], "0" * 64, run[3])
    with pytest.raises(ValueError, match="scope"):
        s.snapshot(run[0], run[1], run[2], tmp_path.parent / "another_project")
    with pytest.raises(ValueError, match="scope"):
        s.snapshot(run[0], run[1], run[2], run[0] / "data/processed")


def test_oversized_or_duplicate_metadata_is_refused(run, monkeypatch):
    monkeypatch.setattr(s, "MAX_JOURNAL", 2)
    journal(run[3], progress(run[3]))
    with pytest.raises(ValueError, match="bound"):
        snap(run)
    with pytest.raises(ValueError, match="Duplicate"):
        s._decode(b'{"x":1,"x":2}')
    with pytest.raises(ValueError, match="Nonfinite"):
        s._decode(b'{"x":NaN}')


def test_missing_request_and_symlink_guard(run, monkeypatch):
    (run[3] / "request.json").unlink()
    assert snap(run)["status"] == "awaiting_request_unverified"
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda p: p == run[3].parent or original(p))
    with pytest.raises(ValueError, match="symlinks"):
        snap(run)


def test_read_stat_change_is_unverified(run, monkeypatch):
    original = os_fstat = s.os.fstat
    calls = 0

    def changed(fd):
        nonlocal calls
        value = original(fd)
        calls += 1
        if calls == 4:  # Second stat of request, not the immutable registration.

            class Stat:
                st_size = value.st_size
                st_mtime_ns = value.st_mtime_ns + 1

            return Stat()
        return value

    monkeypatch.setattr(s.os, "fstat", changed)
    assert snap(run)["status"] == "concurrent_snapshot_unverified"
    assert os_fstat is original
