"""Offline prospective schedule checks: no public data or model calls."""

import asyncio
import copy
import hashlib
import json
import socket
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from ai_trader.ingestion import capture_schedule as module
from ai_trader.ingestion import planned_capture
from ai_trader.models.local_checkpoint import canonical
from ai_trader.training import train_event_baseline

NS = module.NS
PREPARED = module.parse_utc("2026-09-25T12:00:00Z")
SETTINGS = Path(__file__).resolve().parents[1] / "configs/prospective_event_trial_120s_v1.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def windows(count=3, *, first=PREPARED + 60 * NS, step=3600 * NS, width=30 * NS):
    return tuple(
        module.CaptureWindow(first + i * step, first + i * step + width) for i in range(count)
    )


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Schedule planning attempted network, collection or fitting.")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(planned_capture, "collect", forbidden)
    monkeypatch.setattr(train_event_baseline, "_fit", forbidden)
    monkeypatch.setattr(planned_capture.time, "time_ns", lambda: PREPARED)
    monkeypatch.setattr(planned_capture, "_implementation_hash", lambda: "a" * 64)
    monkeypatch.setattr(planned_capture, "_environment", lambda: "synthetic-environment")
    settings = tmp_path / "settings.json"
    settings.write_bytes(SETTINGS.read_bytes())
    args = dict(
        campaign_id="synthetic-windows",
        output_dir=tmp_path / "unstarted-campaign",
        settings_path=settings,
        settings_sha256=sha(settings),
        windows=windows(),
    )
    return args, module.prepare_schedule(**args)


def change_settings(args, change):
    value = json.loads(args["settings_path"].read_bytes())
    change(value)
    args["settings_path"].write_text(canonical(value), encoding="utf-8")
    args["settings_sha256"] = sha(args["settings_path"])


def completion(schedule):
    return tuple(
        dict(
            source_session=w["source_session"],
            dispatched_at_ns=w["open_at_ns"],
            started_at_ns=w["open_at_ns"] + NS,
            ended_at_ns=w["open_at_ns"] + NS + schedule["acquisition"]["seconds_per_session"] * NS,
        )
        for w in schedule["windows"]
    )


def test_preparation_reads_only_pinned_settings_and_creates_nothing(prepared, monkeypatch):
    args, expected = prepared
    source, opened = Path.open, []

    def guarded(path, *a, **kw):
        assert path == args["settings_path"]
        assert a == ("rb",) and not kw
        opened.append(path)
        return source(path, *a, **kw)

    monkeypatch.setattr(Path, "open", guarded)
    result = module.prepare_schedule(**args)
    assert result == expected
    assert opened == [args["settings_path"]]
    assert not args["output_dir"].exists()
    assert result["runtime_available"] is False
    assert result["authority"] == dict.fromkeys(module.AUTHORITY, False)
    assert result["research_settings_sha256"] == args["settings_sha256"]
    assert [w["split"] for w in result["windows"]] == ["train", "validation", "reserved"]
    assert result["budgets"]["maximum_research_frames"] == 10_000
    assert result["budgets"]["maximum_raw_capture_bytes"] == 3 * 32 * 1024**2
    assert result["budgets"]["maximum_stream_events"] == 3 * 99_997
    assert result["budgets"]["maximum_training_row_epochs"] == 500_000
    assert result["budgets"]["minimum_duration_planning_ns"] == 31 * NS


def test_round_trip_pins_verbatim_settings_and_never_overwrites(prepared, tmp_path):
    args, schedule = prepared
    original = args["settings_path"].read_bytes()
    path = tmp_path / "plan.json"
    pin = module.write_new(path, schedule)
    assert pin == sha(path)
    assert module.load_schedule(path, pin) == schedule
    args["settings_path"].write_text("edited later")
    assert module.load_schedule(path, pin)["research_settings_json"].encode() == original
    with pytest.raises(FileExistsError):
        module.write_new(path, schedule)
    assert sha(path) == pin


@pytest.mark.parametrize(
    "offset,state",
    [
        (-1, "waiting_for_first_window"),
        (0, "first_dispatch_window_open"),
        (30 * NS, "first_dispatch_window_open"),
        (30 * NS + 1, "expired_unstarted_campaign"),
        (86400 * NS, "expired_unstarted_campaign"),
    ],
)
def test_unstarted_schedule_exact_boundaries_do_not_shift_windows(prepared, offset, state):
    _, schedule = prepared
    before = copy.deepcopy(schedule)
    report = module.inspect_unstarted_schedule(
        schedule, at_ns=schedule["windows"][0]["open_at_ns"] + offset
    )
    assert report["state"] == state
    assert report["runtime_available"] is False and schedule == before
    assert report["authority"] == module.AUTHORITY
    assert report["distinct_utc_start_dates"] == 1  # Time spacing is not regime evidence.


def test_unstarted_clock_regression_refuses(prepared):
    with pytest.raises(ValueError, match="precedes plan"):
        module.inspect_unstarted_schedule(prepared[1], at_ns=PREPARED - 1)


@pytest.mark.parametrize(
    "text",
    [
        "2026-09-25T12:00:00",
        "2026-09-25T12:00:00+00:00",
        "2026-09-25 12:00:00Z",
        "2026-09-25T12:00:00.1Z",
        "2026-09-25T12:00:00z",
        "2026-02-30T12:00:00Z",
        "2026-09-25T12:00:60Z",
        "1969-12-31T23:59:59Z",
        "9999-12-31T23:59:59Z",
        None,
        1,
    ],
)
def test_only_unambiguous_supported_utc_is_accepted(text):
    with pytest.raises(ValueError):
        module.parse_utc(text)


def test_utc_conversion_and_frozen_windows():
    assert module.parse_utc("1970-01-01T00:00:00Z") == 0
    assert module.format_utc(PREPARED) == "2026-09-25T12:00:00Z"
    with pytest.raises(FrozenInstanceError):
        windows()[0].open_at_ns = 0
    with pytest.raises(ValueError):
        module.format_utc(PREPARED + 1)


@pytest.mark.parametrize(
    "opens,closes",
    [
        (True, NS),
        (NS, False),
        (-1, NS),
        (NS, 0),
        (0, 61 * NS),
        (NS + 1, 2 * NS),
        (NS, 2 * NS + 1),
        (NS, 2**63),
        (1.0, NS),
    ],
)
def test_window_integer_and_width_limits(opens, closes):
    with pytest.raises(ValueError):
        module.CaptureWindow(opens, closes)


@pytest.mark.parametrize(
    "values,message",
    [
        (windows(count=2), "exactly one"),
        (list(windows()), "exactly one"),
        (({}, {}, {}), "typed window"),
        (windows(first=PREPARED + 59 * NS), "lead time"),
        (windows(step=3599 * NS), "separation"),
        (tuple(reversed(windows())), "separation"),
        (windows(first=PREPARED + 7 * 86400 * NS), "seven days"),
    ],
)
def test_invalid_window_schedules_refuse_before_any_outputs(prepared, values, message):
    args, _ = prepared
    with pytest.raises(ValueError, match=message):
        module.prepare_schedule(**(args | {"windows": values}))
    assert not args["output_dir"].exists()


def test_zero_width_windows_and_seven_day_deadline_boundary(prepared):
    args, _ = prepared
    reserve = PREPARED + module.MAX_SPAN_NS - (10 + 120 + 5) * NS
    selected = (windows(width=0)[0], windows(width=0)[1], module.CaptureWindow(reserve, reserve))
    result = module.prepare_schedule(**(args | {"windows": selected}))
    assert result["campaign_deadline_ns"] == PREPARED + module.MAX_SPAN_NS
    bad = (*selected[:2], module.CaptureWindow(reserve + NS, reserve + NS))
    with pytest.raises(ValueError, match="seven days"):
        module.prepare_schedule(**(args | {"windows": bad}))


def test_additional_training_session_requires_a_bounded_fresh_recipe(prepared):
    args, _ = prepared
    options = args | {"train": 2, "windows": windows(4, step=86400 * NS)}
    with pytest.raises(ValueError, match="10000-frame"):
        module.prepare_schedule(**options)
    change_settings(args, lambda s: s["fold"].update(max_frames_per_session=3000))
    options.update(settings_sha256=args["settings_sha256"])
    result = module.prepare_schedule(**options)
    assert result["budgets"]["maximum_research_frames"] == 9000
    report = module.inspect_unstarted_schedule(result, at_ns=PREPARED)
    assert report["distinct_utc_start_dates"] == 4
    assert [w["split"] for w in result["windows"]] == ["train", "train", "validation", "reserved"]


def test_windowed_profile_changes_only_trial_identity_and_frame_quota(prepared):
    args, _ = prepared
    profile = SETTINGS.parent / "windowed_event_trial_v1.json"
    before, after = json.loads(SETTINGS.read_bytes()), json.loads(profile.read_bytes())
    assert after["trial_id"] != before["trial_id"]
    assert after["fold"]["max_frames_per_session"] == 3000
    after["trial_id"] = before["trial_id"]
    after["fold"]["max_frames_per_session"] = before["fold"]["max_frames_per_session"]
    assert after == before  # No cost, label, quality or optimizer retuning.
    result = module.prepare_schedule(
        **(
            args
            | {
                "settings_path": profile,
                "settings_sha256": sha(profile),
                "train": 2,
                "windows": windows(4, step=86400 * NS),
            }
        )
    )
    assert result["budgets"] == {
        "research_sessions": 3,
        "maximum_research_frames": 9000,
        "maximum_training_row_epochs": 600_000,
        "minimum_duration_planning_ns": 31 * NS,
        "maximum_raw_capture_bytes": 128 * 1024**2,
        "maximum_stream_events": 399_988,
        "planned_recording_seconds": 480,
        "frame_budget_is_cap_not_volume_forecast": True,
    }


def test_strict_worst_case_embargo_boundary_even_between_training_sources(prepared):
    args, schedule = prepared
    boundary = (
        schedule["windows"][1]["open_at_ns"] - schedule["windows"][0]["latest_capture_end_ns"]
    )
    change_settings(args, lambda s: s["fold"].update(embargo_ns=boundary))
    with pytest.raises(ValueError, match="strict gap/embargo"):
        module.prepare_schedule(**args)
    change_settings(args, lambda s: s["fold"].update(embargo_ns=boundary - 1))
    assert module.prepare_schedule(**args)


def test_plan_publication_is_exclusive_even_after_partial_failure(prepared, tmp_path):
    path = tmp_path / "schedule.json"
    staging = path.with_name(path.name + ".partial")
    staging.write_text("keep quarantined metadata")
    with pytest.raises(FileExistsError):
        module.write_new(path, prepared[1])
    assert staging.read_text() == "keep quarantined metadata"
    assert not path.exists()


def test_source_change_during_preparation_withholds_plan(prepared, monkeypatch):
    bindings = iter(("a" * 64, "b" * 64))
    monkeypatch.setattr(planned_capture, "_implementation_hash", lambda: next(bindings))
    with pytest.raises(ValueError, match="runtime changed"):
        module.prepare_schedule(**prepared[0])
    assert not prepared[0]["output_dir"].exists()


@pytest.mark.parametrize(
    "change,message",
    [
        (lambda s: s["policy"].update(rule="bid_replenishment_cvd"), "abstain"),
        (lambda s: s["policy"].update(maximum_hold_ns=200 * NS), "warmup"),
        (lambda s: s["replay"]["features"].update(rolling_window_ms=120_000), "warmup"),
        (lambda s: s["fold"].update(max_frames_per_session=5001), "10000-frame"),
        (lambda s: s["baseline"].update(epochs=401), "row-epoch"),
        (lambda s: s["fold"].update(minimum_resolved_per_session=5001), "Integer"),
        (lambda s: s["fold"].update(minimum_resolved_fraction="1.1"), "fraction"),
        (lambda s: s["fold"].update(embargo_ns=4000 * NS), "gap/embargo"),
        (lambda s: s["gateway"]["costs"].update(taker_fee_bps="NaN"), "finite"),
        (lambda s: s.update(credentials="not allowed"), "metadata fields"),
    ],
)
def test_research_preflight_rejects_incompatible_settings(prepared, change, message):
    args, _ = prepared
    change_settings(args, change)
    with pytest.raises(ValueError, match=message):
        module.prepare_schedule(**args)


def test_warmup_duration_strict_boundary(prepared):
    args, _ = prepared
    with pytest.raises(ValueError, match="warmup"):
        module.prepare_schedule(**(args | {"seconds_per_session": 31}))
    assert module.prepare_schedule(**(args | {"seconds_per_session": 32}))


def test_completion_times_are_pure_and_require_all_slots(prepared):
    _, schedule = prepared
    complete = completion(schedule)
    before = copy.deepcopy((schedule, complete))
    assert module.validate_completion_times(schedule, complete) is None
    assert (schedule, complete) == before
    assert not Path(schedule["acquisition"]["output_dir"]).exists()
    with pytest.raises(ValueError, match="no subsets"):
        module.validate_completion_times(schedule, complete[:1])


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_session", "reserved"),
        ("dispatched_at_ns", PREPARED),
        ("dispatched_at_ns", PREPARED + 90 * NS + 1),
        ("started_at_ns", True),
        ("started_at_ns", PREPARED + 60 * NS),
        ("started_at_ns", PREPARED + 71 * NS),
        ("ended_at_ns", PREPARED + 100 * NS),
        ("ended_at_ns", PREPARED + 1000 * NS),
    ],
)
def test_bad_declared_completions_refuse(prepared, field, value):
    schedule = prepared[1]
    complete = completion(schedule)
    complete[0][field] = value
    with pytest.raises(ValueError):
        module.validate_completion_times(schedule, complete)


def test_completion_reordering_duplicates_and_extra_attempts_refuse(prepared):
    schedule = prepared[1]
    complete = completion(schedule)
    for bad in (
        tuple(reversed(complete)),
        (complete[0], complete[0], complete[-1]),
        complete + complete[:1],
    ):
        with pytest.raises(ValueError):
            module.validate_completion_times(schedule, bad)


def test_latest_dispatch_connection_and_footer_tolerance_boundaries(prepared):
    schedule = prepared[1]
    completed = completion(schedule)
    for w, item in zip(schedule["windows"], completed, strict=True):
        item.update(
            dispatched_at_ns=w["last_dispatch_at_ns"],
            started_at_ns=w["last_dispatch_at_ns"] + module.CONNECTION_ALLOWANCE_NS,
            ended_at_ns=w["latest_capture_end_ns"],
        )
    module.validate_completion_times(schedule, completed)
    completed[-1]["ended_at_ns"] += 1
    with pytest.raises(ValueError):
        module.validate_completion_times(schedule, completed)


def test_first_slot_does_not_need_an_embargo_from_plan_creation(prepared):
    args, _ = prepared
    change_settings(args, lambda s: s["fold"].update(embargo_ns=120 * NS))
    result = module.prepare_schedule(**args)
    module.validate_completion_times(result, completion(result))


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(schema_version=True),
        lambda p: p.update(kind="old-plan"),
        lambda p: p.update(runtime_available=True),
        lambda p: p.update(runtime_available=0),
        lambda p: p["authority"].update(training_allowed=True),
        lambda p: p["authority"].update(execution_allowed=True),
        lambda p: p["failure_policy"].update(attempts_per_slot=2),
        lambda p: p["failure_policy"].update(window_shifting=True),
        lambda p: p["failure_policy"].update(successful_subset=True),
        lambda p: p["failure_policy"].update(process_restart="resume"),
        lambda p: p["windows"][0].update(split="validation"),
        lambda p: p["windows"][0].update(filename="../escape.jsonl"),
        lambda p: p["windows"][0].update(latest_capture_end_ns=1),
        lambda p: p["windows"].reverse(),
        lambda p: p["windows"].pop(),
        lambda p: p.update(campaign_deadline_ns=True),
        lambda p: p["budgets"].update(maximum_research_frames=10001),
        lambda p: p.update(research_settings_json=p["research_settings_json"] + " "),
        lambda p: p.update(research_settings_sha256="a" * 64),
        lambda p: p.update(extra=True),
        lambda p: p["acquisition"]["limits"].update(max_bytes=999999999),
    ],
)
def test_repinned_schedule_semantic_tampering_is_rejected(prepared, tmp_path, change):
    result = copy.deepcopy(prepared[1])
    change(result)
    path = tmp_path / "tampered.json"
    pin = module.write_new(path, result)
    with pytest.raises(ValueError):
        module.load_schedule(path, pin)


def test_old_back_to_back_runner_refuses_window_contract_before_capture(prepared, tmp_path):
    path = tmp_path / "schedule.json"
    pin = module.write_new(path, prepared[1])
    with pytest.raises(ValueError):
        asyncio.run(planned_capture.run_plan(path, pin, enable_public_capture=True))
    assert not prepared[0]["output_dir"].exists()


def test_current_code_and_environment_checks_are_not_optional(prepared, tmp_path, monkeypatch):
    schedule = prepared[1]
    path = tmp_path / "schedule.json"
    pin = module.write_new(path, schedule)
    monkeypatch.setattr(planned_capture, "_implementation_hash", lambda: "b" * 64)
    module.validate_schedule(schedule)  # Historical structural inspection only.
    with pytest.raises(ValueError, match="runtime changed"):
        module.load_schedule(path, pin)
    with pytest.raises(ValueError, match="runtime changed"):
        module.inspect_unstarted_schedule(schedule, at_ns=PREPARED)
    monkeypatch.setattr(planned_capture, "_implementation_hash", lambda: "a" * 64)
    monkeypatch.setattr(planned_capture, "_environment", lambda: "different")
    with pytest.raises(ValueError, match="runtime changed"):
        module.load_schedule(path, pin)


def test_partial_oversized_wrong_pin_and_duplicate_json_refuse(prepared, tmp_path):
    args, _ = prepared
    with pytest.raises(ValueError, match="SHA256"):
        module.prepare_schedule(**(args | {"settings_sha256": "b" * 64}))
    for name, raw in (
        ("input.partial", b"{}"),
        ("large.json", b" " * (module.MAX_METADATA_BYTES + 1)),
        ("duplicate.json", b'{"kind":1,"kind":2}'),
    ):
        path = tmp_path / name
        path.write_bytes(raw)
        with pytest.raises(ValueError):
            module.load_schedule(path, sha(path))


def test_cli_prepare_and_inspect_are_offline_and_offer_no_run_command(
    prepared, tmp_path, monkeypatch, capsys
):
    args, _ = prepared
    path = tmp_path / "cli.json"
    command = [
        "capture_schedule",
        "prepare",
        "--campaign-id",
        args["campaign_id"],
        "--output-dir",
        str(args["output_dir"]),
        "--settings",
        str(args["settings_path"]),
        "--settings-sha256",
        args["settings_sha256"],
        "--plan",
        str(path),
    ]
    for w in args["windows"]:
        command += [
            "--window",
            module.format_utc(w.open_at_ns),
            module.format_utc(w.last_dispatch_at_ns),
        ]
    monkeypatch.setattr(sys, "argv", command)
    module.main()
    result = json.loads(capsys.readouterr().out)
    assert result["plan_sha256"] == sha(path) and result["runtime_available"] is False
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "capture_schedule",
            "inspect",
            "--plan",
            str(path),
            "--plan-sha256",
            sha(path),
            "--at-utc",
            module.format_utc(PREPARED),
        ],
    )
    module.main()
    assert json.loads(capsys.readouterr().out)["state"] == "waiting_for_first_window"
    monkeypatch.setattr(sys, "argv", ["capture_schedule", "run"])
    with pytest.raises(SystemExit):
        module.main()
    assert not args["output_dir"].exists()
