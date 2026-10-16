"""Offline, write-once UTC acquisition windows and research-budget preflight.

Preparation is offline. V1 is metadata-only; explicit V2 plans can be passed to the
separate opt-in runner. Back-to-back runners must reject both window contracts.
"""

import argparse
import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from ai_trader.ingestion.planned_capture import (
    AUTHORITY,
    DEFAULT_LIMITS,
    NS,
    ROLES,
    _check_binding,
    _integer,
    _shape,
    prepare_plan,
    validate_plan,
    write_new,
)
from ai_trader.models.local_checkpoint import canonical, check_digest, digest, strict_json
from ai_trader.research.microstructure_trial import (
    _decode_gateway,
    _decode_policy,
    _decode_replay,
)
from ai_trader.trading.paper_lifecycle import _money, _timestamp
from ai_trader.trading.trade_journal import _decimal, _identifier
from ai_trader.training.event_training_data import MAX_TOTAL_FRAMES
from ai_trader.training.train_event_baseline import MAX_ROW_EPOCHS, _decode_config

KIND = "prospective_capture_windows_v1"
RUNNABLE_KIND = "prospective_capture_windows_v2"
MAX_METADATA_BYTES = 64 * 1024
MAX_SPAN_NS = 7 * 86400 * NS
MIN_LEAD_NS = 60 * NS
MIN_SEPARATION_NS = 3600 * NS
MAX_DISPATCH_WINDOW_NS = 60 * NS
CONNECTION_ALLOWANCE_NS = 10 * NS
SNAPSHOT_PLANNING_ALLOWANCE_NS = 10 * NS
FOOTER_TOLERANCE_NS = 5 * NS
RUNTIME = {
    "wait_poll_ns": NS,
    "completion_grace_ns": 30 * NS,
    "clock_contract": "nondecreasing_wall_and_monotonic_anchored_windows",
    "start_guard": "after_connection_before_snapshot_and_stream",
    "cancellation": "cooperative_no_hard_OS_deadline",
}
POLICY = {
    "attempts_per_slot": 1,
    "missed_window": "abort_entire_campaign",
    "capture_failure": "abort_entire_campaign",
    "clock_regression": "abort_entire_campaign",
    "process_restart": "no_resume_keep_claim_and_partials",
    "replacement_sessions": False,
    "successful_subset": False,
    "outcome_based_stopping": False,
    "window_shifting": False,
    "dispatch_boundaries": "inclusive_open_and_last_dispatch",
    "connection_allowance_ns": CONNECTION_ALLOWANCE_NS,
    "snapshot_planning_allowance_ns": SNAPSHOT_PLANNING_ALLOWANCE_NS,
    "footer_tolerance_ns": FOOTER_TOLERANCE_NS,
}


def parse_utc(value):
    """Exact UTC seconds only: no local timezone, floats or DST interpretation."""
    if (
        type(value) is not str
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is None
    ):
        raise ValueError("Use an explicit UTC time: YYYY-MM-DDTHH:MM:SSZ.")
    moment = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    elapsed = moment - datetime(1970, 1, 1, tzinfo=UTC)
    result = (elapsed.days * 86400 + elapsed.seconds) * NS
    _timestamp(result)
    return result


def format_utc(value):
    _timestamp(value)
    if value % NS:
        raise ValueError("Schedule times must be whole UTC seconds.")
    return datetime.fromtimestamp(value // NS, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True, slots=True)
class CaptureWindow:
    open_at_ns: int
    last_dispatch_at_ns: int

    def __post_init__(self):
        for value in (self.open_at_ns, self.last_dispatch_at_ns):
            _timestamp(value)
            if value % NS:
                raise ValueError("Schedule windows require whole UTC seconds.")
        if not 0 <= self.last_dispatch_at_ns - self.open_at_ns <= MAX_DISPATCH_WINDOW_NS:
            raise ValueError("Dispatch window width must be between zero and 60 seconds.")


def _read_metadata(path, sha256):
    check_digest(sha256)
    path = Path(path)
    if path.name.endswith(".partial") or path.is_symlink() or not path.is_file():
        raise ValueError("Expected explicit complete regular metadata file.")
    with path.open("rb") as source:
        raw = source.read(MAX_METADATA_BYTES + 1)
    if not raw or len(raw) > MAX_METADATA_BYTES or hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("Metadata byte budget or raw SHA256 mismatch.")
    return raw


def _research_preflight(settings, acquisition):
    """Validate real settings without inventing source hashes, captures or registrations."""
    _shape(
        settings,
        ("trial_id", "policy", "replay", "gateway", "initial_cash_usdt", "fold", "baseline"),
    )
    _identifier(settings["trial_id"])
    policy = _decode_policy(settings["policy"])
    replay = _decode_replay(settings["replay"])
    _decode_gateway(settings["gateway"])
    _money(_decimal(settings["initial_cash_usdt"]))
    baseline = _decode_config(settings["baseline"])
    if policy.rule != "abstain":
        raise ValueError("Windowed acquisition requires the abstain/no-order control.")
    fold = settings["fold"]
    _shape(
        fold,
        (
            "max_frames_per_session",
            "embargo_ns",
            "minimum_resolved_per_session",
            "minimum_resolved_fraction",
        ),
    )
    frames = fold["max_frames_per_session"]
    _integer(frames, 1, MAX_TOTAL_FRAMES)
    _timestamp(fold["embargo_ns"])
    _integer(fold["minimum_resolved_per_session"], 1, frames)
    fraction = _decimal(fold["minimum_resolved_fraction"])
    _money(fraction, zero=True)
    if fraction > 1:
        raise ValueError("Resolved fraction must be in [0, 1].")
    counts = acquisition["counts"]
    research_count = counts["train"] + counts["validation"]
    if frames * research_count > MAX_TOTAL_FRAMES:
        raise ValueError("Windowed research exceeds the existing 10000-frame aggregate cap.")
    row_epochs = frames * counts["train"] * baseline.epochs
    if row_epochs > MAX_ROW_EPOCHS:
        raise ValueError("Windowed research exceeds the existing row-epoch budget.")
    minimum_duration = (
        SNAPSHOT_PLANNING_ALLOWANCE_NS
        + replay.features.rolling_window_ms * 1_000_000
        + policy.entry_ttl_ns
        + policy.maximum_hold_ns
    )
    if acquisition["seconds_per_session"] * NS <= minimum_duration:
        raise ValueError("Duration must exceed snapshot allowance + warmup + entry TTL + horizon.")
    return {
        "research_sessions": research_count,
        "maximum_research_frames": frames * research_count,
        "maximum_training_row_epochs": row_epochs,
        "minimum_duration_planning_ns": minimum_duration,
        "maximum_raw_capture_bytes": len(acquisition["sessions"]) * DEFAULT_LIMITS.max_bytes,
        "maximum_stream_events": len(acquisition["sessions"]) * DEFAULT_LIMITS.max_events,
        "planned_recording_seconds": len(acquisition["sessions"])
        * acquisition["seconds_per_session"],
        "frame_budget_is_cap_not_volume_forecast": True,
    }


def _settings(schedule):
    raw = schedule["research_settings_json"]
    if type(raw) is not str or not 0 < len(raw.encode()) <= MAX_METADATA_BYTES:
        raise ValueError("Expected a bounded verbatim settings snapshot.")
    check_digest(schedule["research_settings_sha256"])
    if hashlib.sha256(raw.encode()).hexdigest() != schedule["research_settings_sha256"]:
        raise ValueError("Embedded research settings differ from the original raw-file pin.")
    return strict_json(raw)


def _windows(acquisition, windows, embargo_ns):
    if (
        type(windows) is not tuple
        or len(windows) != len(acquisition["sessions"])
        or any(type(w) is not CaptureWindow for w in windows)
    ):
        raise ValueError("Provide exactly one typed window per declared session, in order.")
    if windows[0].open_at_ns < acquisition["prepared_at_ns"] + MIN_LEAD_NS:
        raise ValueError("First window needs at least 60 seconds of preparation lead time.")
    result, last_open, last_end = [], None, None
    for assignment, window in zip(acquisition["sessions"], windows, strict=True):
        end = (
            window.last_dispatch_at_ns
            + CONNECTION_ALLOWANCE_NS
            + acquisition["seconds_per_session"] * NS
            + FOOTER_TOLERANCE_NS
        )
        _timestamp(end)
        if last_open is not None and (
            window.open_at_ns - last_open < MIN_SEPARATION_NS
            or last_end + max(embargo_ns, acquisition["pause_seconds"] * NS) >= window.open_at_ns
        ):
            raise ValueError("Windows violate one-hour separation or the strict gap/embargo.")
        result.append({**assignment, **asdict(window), "latest_capture_end_ns": end})
        last_open, last_end = window.open_at_ns, end
    if result[-1]["latest_capture_end_ns"] - acquisition["prepared_at_ns"] > MAX_SPAN_NS:
        raise ValueError("The full campaign deadline must fit within seven days of preparation.")
    return result


def validate_schedule(schedule):
    """Historical metadata validation only; no IO, replay, current-code guard or authority."""
    if type(schedule) is not dict or type(schedule.get("schema_version")) is not int:
        raise ValueError("Unsupported windowed acquisition contract.")
    version = schedule["schema_version"]
    if version not in (1, 2):
        raise ValueError("Unsupported windowed acquisition contract.")
    _shape(
        schedule,
        (
            "schema_version",
            "kind",
            "acquisition",
            "research_settings_json",
            "research_settings_sha256",
            "windows",
            "campaign_deadline_ns",
            "budgets",
            "failure_policy",
            "authority",
            "runtime_available",
            *(("runtime",) if version == 2 else ()),
        ),
    )
    if schedule["kind"] != (RUNNABLE_KIND if version == 2 else KIND):
        raise ValueError("Unsupported windowed acquisition contract.")
    acquisition = schedule["acquisition"]
    validate_plan(acquisition)
    if acquisition["schema_version"] != 2:
        raise ValueError("Windowed acquisition requires research-only timing metadata.")
    if (
        canonical(schedule["failure_policy"]) != canonical(POLICY)
        or canonical(schedule["authority"]) != canonical(AUTHORITY)
        or schedule["runtime_available"] is not (version == 2)
    ):
        raise ValueError("Window plans cannot authorize execution, resume, retries or a runtime.")
    if version == 2 and canonical(schedule["runtime"]) != canonical(RUNTIME):
        raise ValueError("Unsupported bounded capture runtime policy.")
    settings = _settings(schedule)
    budgets = _research_preflight(settings, acquisition)
    if type(schedule["windows"]) is not list or len(schedule["windows"]) != len(
        acquisition["sessions"]
    ):
        raise ValueError("Exactly one window per declared session is required.")
    typed = []
    for window in schedule["windows"]:
        _shape(
            window,
            (
                "source_session",
                "split",
                "filename",
                "open_at_ns",
                "last_dispatch_at_ns",
                "latest_capture_end_ns",
            ),
        )
        typed.append(CaptureWindow(window["open_at_ns"], window["last_dispatch_at_ns"]))
    expected = _windows(acquisition, tuple(typed), settings["fold"]["embargo_ns"])
    if (
        canonical(schedule["windows"]) != canonical(expected)
        or canonical(schedule["budgets"]) != canonical(budgets)
        or type(schedule["campaign_deadline_ns"]) is not int
        or schedule["campaign_deadline_ns"] != expected[-1]["latest_capture_end_ns"]
    ):
        raise ValueError("Schedule assignments, deadlines or budgets disagree with frozen inputs.")
    if len((canonical(schedule) + "\n").encode()) > MAX_METADATA_BYTES:
        raise ValueError("Windowed acquisition metadata exceeds its byte budget.")


def prepare_schedule(
    *,
    campaign_id,
    output_dir,
    settings_path,
    settings_sha256,
    windows,
    train=1,
    validation=1,
    reserved=1,
    seconds_per_session=120,
    pause_seconds=5,
    runnable=False,
):
    """Read one pinned settings file; create no directories, captures or registrations."""
    if type(runnable) is not bool:
        raise ValueError("Runnable plan selection must be an explicit boolean.")
    raw = _read_metadata(settings_path, settings_sha256)
    settings = strict_json(raw)
    acquisition = prepare_plan(
        campaign_id=campaign_id,
        output_dir=output_dir,
        train=train,
        validation=validation,
        reserved=reserved,
        seconds_per_session=seconds_per_session,
        pause_seconds=pause_seconds,
        research_timing=True,
    )
    budgets = _research_preflight(settings, acquisition)
    windows = _windows(acquisition, windows, settings["fold"]["embargo_ns"])
    schedule = {
        "schema_version": 2 if runnable else 1,
        "kind": RUNNABLE_KIND if runnable else KIND,
        "acquisition": acquisition,
        "research_settings_json": raw.decode("utf-8"),
        "research_settings_sha256": settings_sha256,
        "windows": windows,
        "campaign_deadline_ns": windows[-1]["latest_capture_end_ns"],
        "budgets": budgets,
        "failure_policy": dict(POLICY),
        "authority": dict(AUTHORITY),
        "runtime_available": runnable,
    }
    if runnable:
        schedule["runtime"] = dict(RUNTIME)
    validate_schedule(schedule)
    _check_binding(acquisition)
    return schedule


def load_schedule(path, sha256):
    """Read one pinned schedule; stale code/runtime refuses operational inspection."""
    schedule = strict_json(_read_metadata(path, sha256))
    validate_schedule(schedule)
    _check_binding(schedule["acquisition"])
    return schedule


def inspect_unstarted_schedule(schedule, *, at_ns):
    """Read-only time assessment, NOT a scheduler or proof of completion/permission."""
    validate_schedule(schedule)
    _check_binding(schedule["acquisition"])
    _timestamp(at_ns)
    first = schedule["windows"][0]
    if at_ns < schedule["acquisition"]["prepared_at_ns"]:
        raise ValueError("Assessment clock precedes plan preparation.")
    state = (
        "waiting_for_first_window"
        if at_ns < first["open_at_ns"]
        else "first_dispatch_window_open"
        if at_ns <= first["last_dispatch_at_ns"]
        else "expired_unstarted_campaign"
    )
    return {
        "kind": "unstarted_capture_window_assessment_v1",
        "schedule_payload_sha256": digest(schedule),
        "at_ns": at_ns,
        "state": state,
        "runtime_available": schedule["runtime_available"],
        "campaign_deadline_utc": format_utc(schedule["campaign_deadline_ns"]),
        "windows": [
            {
                **w,
                "open_utc": format_utc(w["open_at_ns"]),
                "last_dispatch_utc": format_utc(w["last_dispatch_at_ns"]),
                "latest_capture_end_utc": format_utc(w["latest_capture_end_ns"]),
            }
            for w in schedule["windows"]
        ],
        "distinct_utc_start_dates": len(
            {format_utc(w["open_at_ns"])[:10] for w in schedule["windows"]}
        ),
        "budgets": dict(schedule["budgets"]),
        "authority": dict(AUTHORITY),
        "limitation": (
            "Metadata only. No job scheduled, capture started, completion verified "
            "or independence established."
        ),
    }


def validate_completion_times(schedule, completed):
    """Pure time-contract checks for a future runner; caller claims are not custody evidence.

    An exact all-slot sequence is required: this cannot bless a successful subset.
    It performs no raw-source verification and produces no research registration.
    """
    validate_schedule(schedule)
    if type(completed) is not tuple or len(completed) != len(schedule["windows"]):
        raise ValueError("Every declared window must complete once, in order; no subsets.")
    acquisition = schedule["acquisition"]
    settings = _settings(schedule)
    gap = max(acquisition["pause_seconds"] * NS, settings["fold"]["embargo_ns"])
    last_end = None
    for window, item in zip(schedule["windows"], completed, strict=True):
        _shape(item, ("source_session", "dispatched_at_ns", "started_at_ns", "ended_at_ns"))
        for key in ("dispatched_at_ns", "started_at_ns", "ended_at_ns"):
            _timestamp(item[key])
        dispatch, start, end = (
            item[k] for k in ("dispatched_at_ns", "started_at_ns", "ended_at_ns")
        )
        if (
            item["source_session"] != window["source_session"]
            or not window["open_at_ns"] <= dispatch <= window["last_dispatch_at_ns"]
            or not dispatch < start <= dispatch + CONNECTION_ALLOWANCE_NS
            or not (acquisition["seconds_per_session"] - 1) * NS
            <= end - start
            <= (acquisition["seconds_per_session"] + 5) * NS
            or end > window["latest_capture_end_ns"]
            or (last_end is not None and start <= last_end + gap)
        ):
            raise ValueError("Completion violates source order, dispatch, duration or strict gap.")
        last_end = end


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Offline metadata only; does not schedule a job.")
    prepare.add_argument("--campaign-id", required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--settings", type=Path, required=True)
    prepare.add_argument("--settings-sha256", required=True)
    prepare.add_argument("--plan", type=Path, required=True)
    prepare.add_argument(
        "--window",
        nargs=2,
        action="append",
        metavar=("OPEN_UTC", "LAST_DISPATCH_UTC"),
        required=True,
    )
    for role in ROLES:
        prepare.add_argument(f"--{role}", type=int, default=1)
    prepare.add_argument("--seconds-per-session", type=int, default=120)
    prepare.add_argument("--pause-seconds", type=int, default=5)
    prepare.add_argument(
        "--runnable", action="store_true", help="Create V2; does not start capture."
    )
    inspect = commands.add_parser("inspect", help="Read-only assessment of an unstarted campaign.")
    inspect.add_argument("--plan", type=Path, required=True)
    inspect.add_argument("--plan-sha256", required=True)
    inspect.add_argument("--at-utc", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        schedule = prepare_schedule(
            campaign_id=args.campaign_id,
            output_dir=args.output_dir,
            settings_path=args.settings,
            settings_sha256=args.settings_sha256,
            windows=tuple(CaptureWindow(parse_utc(a), parse_utc(b)) for a, b in args.window),
            train=args.train,
            validation=args.validation,
            reserved=args.reserved,
            seconds_per_session=args.seconds_per_session,
            pause_seconds=args.pause_seconds,
            runnable=args.runnable,
        )
        print(
            canonical(
                {
                    "plan_sha256": write_new(args.plan, schedule),
                    "runtime_available": schedule["runtime_available"],
                }
            )
        )
    else:
        schedule = load_schedule(args.plan, args.plan_sha256)
        print(canonical(inspect_unstarted_schedule(schedule, at_ns=parse_utc(args.at_utc))))


if __name__ == "__main__":
    main()
