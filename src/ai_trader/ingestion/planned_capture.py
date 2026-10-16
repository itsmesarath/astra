"""Prospective whole-session splits and finite public-data acquisition; no execution.

Preparation reads no captures. Running needs a byte-pinned plan and explicit opt-in.
Reserved bytes are checked for transport integrity here, never reported as research
features, targets or performance. Local pins do not authenticate independent custody.
"""

import argparse
import asyncio
import hashlib
import os
import re
import time
from dataclasses import asdict
from pathlib import Path

from ai_trader.features.microstructure import MicrostructureConfig
from ai_trader.ingestion.capture_failure import failure_details, failure_stage, safe_error_type
from ai_trader.ingestion.capture_timing import (
    MAX_REPORT_BYTES,
    PERIOD_NS,
    SAMPLE_LIMIT,
    CaptureTiming,
)
from ai_trader.ingestion.collect_combined import DEFAULT_LIMITS, CaptureInterrupted, collect
from ai_trader.models.local_checkpoint import canonical, check_digest, strict_json
from ai_trader.research.advisory_evaluation import read_pinned
from ai_trader.research.microstructure_trial import SourceDeclaration, _environment
from ai_trader.trading.capture_replay import (
    CaptureReplay,
    CaptureReplayConfig,
    _implementation_hash,
)
from ai_trader.training.microstructure_data import _publish

PLAN_KIND = "prospective_capture_plan_v1"
RECEIPT_KIND = "prospective_capture_receipt_v1"
TIMED_PLAN_KIND = "prospective_capture_plan_v2"
TIMED_RECEIPT_KIND = "prospective_capture_receipt_v2"
TIMING_CONTRACT = {
    "kind": "research_capture_timing_v1",
    "scope": "train_validation_only",
    "timer_period_ns": PERIOD_NS,
    "sample_limit_per_metric": SAMPLE_LIMIT,
    "max_report_bytes": MAX_REPORT_BYTES,
}
ROLES = ("train", "validation", "reserved")
NS = 1_000_000_000
AUTHORITY = {"training_allowed": False, "promotion_allowed": False, "execution_allowed": False}


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Integer outside the acquisition budget.")


def _shape(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError("Unexpected acquisition metadata fields.")


def _assignments(campaign_id, counts):
    sessions = []
    for role, count in zip(ROLES, counts, strict=True):
        for _ in range(count):
            name = f"{campaign_id}-{len(sessions) + 1:02d}-{role}"
            sessions.append({"source_session": name, "split": role, "filename": f"{name}.jsonl"})
    return sessions


def validate_plan(plan):
    """Metadata-only validation. No capture opens, filesystem mutations or network."""
    if type(plan) is not dict or type(plan.get("schema_version")) is not int:
        raise ValueError("Unsupported acquisition schema.")
    version = plan["schema_version"]
    if version not in (1, 2):
        raise ValueError("Unsupported acquisition schema.")
    _shape(
        plan,
        (
            "schema_version",
            "kind",
            "campaign_id",
            "prepared_at_ns",
            "output_dir",
            "counts",
            "seconds_per_session",
            "pause_seconds",
            "limits",
            "sessions",
            "implementation_sha256",
            "environment_json",
            "authority",
            *(("timing",) if version == 2 else ()),
        ),
    )
    if plan["kind"] != (TIMED_PLAN_KIND if version == 2 else PLAN_KIND):
        raise ValueError("Unsupported acquisition kind.")
    if version == 2 and canonical(plan["timing"]) != canonical(TIMING_CONTRACT):
        raise ValueError("Only the fixed research-only timing contract is supported.")
    name = plan["campaign_id"]
    if type(name) is not str or re.fullmatch(r"[a-z][a-z0-9-]{0,63}", name) is None:
        raise ValueError("Use a short lowercase campaign identifier.")
    _integer(plan["prepared_at_ns"], 1, 2**63 - 1)
    _shape(plan["counts"], ROLES)
    counts = [plan["counts"][role] for role in ROLES]
    for count in counts:
        _integer(count, 1, 6)
    if sum(counts) > 8:
        raise ValueError("At most eight whole sessions per plan.")
    _integer(plan["seconds_per_session"], 30, 300)
    _integer(plan["pause_seconds"], 0, 60)
    if sum(counts) * plan["seconds_per_session"] > 1200:
        raise ValueError("Aggregate capture duration exceeds 1200 seconds.")
    # Canonical comparison rejects bools disguised as ints and all extra fields.
    if canonical(plan["limits"]) != canonical(asdict(DEFAULT_LIMITS)):
        raise ValueError("Only the fixed, validated recorder limits are supported.")
    if canonical(plan["authority"]) != canonical(AUTHORITY):
        raise ValueError("Acquisition cannot grant training, promotion or execution authority.")
    if canonical(plan["sessions"]) != canonical(_assignments(name, counts)):
        raise ValueError("Assignments must be unique, chronological whole-session splits.")
    check_digest(plan["implementation_sha256"])
    if type(plan["environment_json"]) is not str or not plan["environment_json"]:
        raise ValueError("Explicit runtime binding required.")
    output = plan["output_dir"]
    if (
        type(output) is not str
        or not Path(output).is_absolute()
        or str(Path(output).resolve()) != output
    ):
        raise ValueError("Use a canonical absolute new output directory.")


def prepare_plan(
    *,
    campaign_id,
    output_dir,
    train=1,
    validation=1,
    reserved=1,
    seconds_per_session=60,
    pause_seconds=5,
    research_timing=False,
):
    """Freeze roles before seeing outcomes; writing the returned plan is a separate step."""
    counts = (train, validation, reserved)
    if type(research_timing) is not bool:
        raise ValueError("Research timing must be an explicit boolean.")
    # Validate before expanding potentially untrusted counts.
    for count in counts:
        _integer(count, 1, 6)
    plan = {
        "schema_version": 2 if research_timing else 1,
        "kind": TIMED_PLAN_KIND if research_timing else PLAN_KIND,
        "campaign_id": campaign_id,
        "prepared_at_ns": time.time_ns(),
        "output_dir": str(Path(output_dir).resolve()),
        "counts": dict(zip(ROLES, counts, strict=True)),
        "seconds_per_session": seconds_per_session,
        "pause_seconds": pause_seconds,
        "limits": asdict(DEFAULT_LIMITS),
        "sessions": _assignments(campaign_id, counts),
        "implementation_sha256": _implementation_hash(),
        "environment_json": _environment(),
        "authority": dict(AUTHORITY),
    }
    if research_timing:
        plan["timing"] = dict(TIMING_CONTRACT)
    validate_plan(plan)
    if Path(plan["output_dir"]).exists():
        raise FileExistsError("Acquisition requires a new output directory.")
    return plan


def write_new(path, value):
    """Publish durable metadata without overwrite; failures retain owned partials."""
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise FileExistsError(path)
    raw = (canonical(value) + "\n").encode()
    if len(raw) > 64 * 1024:
        raise ValueError("Acquisition metadata exceeds its byte budget.")
    partial = path.with_name(path.name + ".partial")
    with partial.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(partial, path)
    partial.unlink()
    return hashlib.sha256(raw).hexdigest()


def _check_binding(plan):
    if (
        plan["implementation_sha256"] != _implementation_hash()
        or plan["environment_json"] != _environment()
    ):
        raise ValueError("Acquisition implementation or runtime changed; do not resume this plan.")


def _capture_metadata(path, assignment, *, earliest_ns, seconds):
    """Acquisition-side integrity check on every role; export only source metadata."""
    if (
        path.is_symlink()
        or not path.is_file()
        or path.with_suffix(".jsonl.partial").exists()
        or path.with_suffix(".jsonl.stream.partial").exists()
        or path.with_suffix(".jsonl.stream.partial").is_symlink()
    ):
        raise ValueError("Expected one completely published regular capture.")
    with path.open("rb") as stream:
        raw = stream.read(DEFAULT_LIMITS.max_bytes + 1)
    sha = hashlib.sha256(raw).hexdigest()
    replay = CaptureReplay(
        raw,
        expected_sha256=sha,
        source_session=assignment["source_session"],
        config=CaptureReplayConfig(features=MicrostructureConfig(levels=1)),
    )
    observed = False
    for frame in replay.frames():
        if frame.status.startswith("resync_required:"):
            raise CaptureInterrupted("Prospective capture failed the fixed integrity checks.")
        observed |= frame.observation is not None
    if not observed:
        raise CaptureInterrupted("No post-snapshot observation in prospective capture.")
    lines = raw.splitlines()
    start, snapshot, end = (strict_json(lines[i]) for i in (0, 1, -1))
    declaration = SourceDeclaration(
        assignment["source_session"],
        sha,
        start["started_at_ns"],
        end["ended_at_ns"],
        "reserved" if assignment["split"] == "reserved" else "research",
    )
    if declaration.started_at_ns <= earliest_ns:
        raise ValueError("Capture predates its intent or violates the frozen session gap.")
    duration = declaration.ended_at_ns - declaration.started_at_ns
    # Scheduling tolerance is fixed in code, not an outcome-dependent shortening option.
    if not (seconds - 1) * NS <= duration <= (seconds + 5) * NS:
        raise ValueError("Capture duration differs from its frozen budget.")
    return {
        **assignment,
        "status": "completed",
        "source": asdict(declaration),
        "snapshot_received_at_ns": snapshot["received_at_ns"],
        "bytes": len(raw),
        "trade_events": end["trade_events"],
        "depth_events": end["depth_events"],
    }


def timing_filename(assignment):
    return assignment["filename"] + ".timing.json"


def validate_timing_counts(diagnostics, item):
    """Completed telemetry must account for every event without replacing raw receipts."""
    total = item["trade_events"] + item["depth_events"]
    expected = {
        "received_events": total,
        "enqueued_events": total,
        "processed_events": total,
        "snapshot_available_wall_ns": item["snapshot_received_at_ns"],
        "timer_period_ns": PERIOD_NS,
        "sample_limit_per_metric": SAMPLE_LIMIT,
        "wall_regressions": 0,
    }
    if type(diagnostics) is not dict or canonical(
        {k: diagnostics.get(k) for k in expected}
    ) != canonical(expected):
        raise ValueError("Timing counters disagree with the completed capture.")
    _integer(diagnostics.get("queue_high_water"), 1, DEFAULT_LIMITS.queue_capacity)
    _integer(diagnostics.get("snapshot_available_perf_ns"), 1, 2**63 - 1)
    metrics = diagnostics.get("metrics")
    if type(metrics) is not dict:
        raise ValueError("Missing capture timing metrics.")
    for name, count in (
        ("parse_write", total),
        ("receipt_gap_perf", total - 1),
        ("receipt_gap_wall", total - 1),
        ("depth_receipt_gap_perf", item["depth_events"] - 1),
        ("depth_receipt_gap_wall", item["depth_events"] - 1),
    ):
        if type(metrics.get(name)) is not dict:
            raise ValueError("Missing capture timing metric.")
        _integer(metrics[name].get("count"), count, count)
    for name in ("queue_wait", "queue_wait_snapshot_buffer", "event_loop_lag"):
        if type(metrics.get(name)) is not dict:
            raise ValueError("Missing capture timing metric.")
        _integer(metrics[name].get("count"), 0, DEFAULT_LIMITS.max_events)
    if (
        metrics["queue_wait"]["count"] + metrics["queue_wait_snapshot_buffer"]["count"] != total
        or metrics["event_loop_lag"]["count"] == 0
    ):
        raise ValueError("Incomplete queue or event-loop timing coverage.")


async def _collect_slot(plan, plan_sha256, assignment, *, collector, earliest_ns, clock):
    path = Path(plan["output_dir"]) / assignment["filename"]
    timed = plan["schema_version"] == 2 and assignment["split"] != "reserved"
    timing = CaptureTiming() if timed else None
    item, error_type, failure = None, None, None
    try:
        result = await collector(
            plan["seconds_per_session"],
            output_path=path,
            limits=DEFAULT_LIMITS,
            **({"timing": timing} if timed else {}),
        )
        if (
            type(result) is not tuple
            or len(result) != 3
            or result[0] != path
            or any(type(count) is not int or count < 0 for count in result[1:])
        ):
            raise ValueError("Unexpected collector result.")
        with failure_stage("campaign.binding_mismatch"):
            _check_binding(plan)
        with failure_stage("campaign.slot_metadata"):
            metadata = _capture_metadata(
                path, assignment, seconds=plan["seconds_per_session"], earliest_ns=earliest_ns
            )
        if result[1:] != (metadata["trade_events"], metadata["depth_events"]):
            raise ValueError("Collector counts disagree with the captured footer.")
        if metadata["source"]["ended_at_ns"] > clock():
            raise ValueError("Capture footer exceeds the acquisition clock.")
        if timed:
            with failure_stage("campaign.timing_mismatch"):
                validate_timing_counts(timing.summary(), metadata)
        item = metadata
    except BaseException as error:
        error_type, failure = safe_error_type(error), failure_details(error)
        raise
    finally:
        if timed:
            report = {
                "schema_version": 1,
                "kind": TIMING_CONTRACT["kind"],
                "plan_sha256": plan_sha256,
                **assignment,
                "status": "completed" if item is not None else "failed",
                "source_sha256": None if item is None else item["source"]["source_sha256"],
                "error_type": error_type,
                "diagnostics": timing.summary(),
                "authority": dict(AUTHORITY),
            }
            if failure is not None:
                report["failure"] = failure
            report_path = path.with_name(timing_filename(assignment))
            with failure_stage("diagnostics.publication_failed"):
                _publish(report, report_path, payload_name="report", max_bytes=MAX_REPORT_BYTES)
                if report_path.with_name(report_path.name + ".partial").exists():
                    raise ValueError("Incomplete timing publication remains quarantined.")
    if plan["schema_version"] == 2:
        item["timing"] = None
        if timed:
            with report_path.open("rb") as stream:
                raw = stream.read(MAX_REPORT_BYTES + 1)
            if len(raw) > MAX_REPORT_BYTES:
                raise ValueError("Timing report exceeds its byte budget.")
            item["timing"] = {
                "filename": report_path.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
    return item


async def run_plan(
    plan_path, plan_sha256, *, enable_public_capture=False, collector=None, sleeper=None, clock=None
):
    """One attempt per frozen slot. Any failure/cancellation stops the entire campaign.

    No replacement, successful-subset selection, role reassignment or automatic resume.
    The new directory is the single-use claim; retain it after failure or process death.
    Dependencies are injectable for synthetic tests; CLI always uses the real recorder.
    """
    if enable_public_capture is not True:
        raise ValueError("Explicit public-capture opt-in required.")
    plan = read_pinned(Path(plan_path), plan_sha256)
    validate_plan(plan)
    _check_binding(plan)
    collector, sleeper, clock = (
        collector or collect,
        sleeper or asyncio.sleep,
        clock or time.time_ns,
    )
    if clock() <= plan["prepared_at_ns"]:
        raise ValueError("Acquisition clock must be later than plan preparation.")
    output = Path(plan["output_dir"])
    output.mkdir()  # No parents/overwrite: existing, concurrent and abandoned runs refuse.
    receipt = {
        "schema_version": plan["schema_version"],
        "kind": TIMED_RECEIPT_KIND if plan["schema_version"] == 2 else RECEIPT_KIND,
        "plan_sha256": plan_sha256,
        "campaign_id": plan["campaign_id"],
        "status": "running",
        "sessions": [{**item, "status": "not_started"} for item in plan["sessions"]],
        "reserved_integrity_only": True,
        "independence_authenticated": False,
        "model_calls": 0,
        "optimization_steps": 0,
        "orders": 0,
        "authority": dict(AUTHORITY),
    }
    # Startup failures still leave a claimed directory; never retry it automatically.
    with (output / "audit.jsonl").open("x", encoding="utf-8", newline="\n") as audit:

        def record(status, **values):
            at = clock()
            _integer(at, 1, 2**63 - 1)
            audit.write(canonical({"status": status, "at_ns": at, **values}) + "\n")
            audit.flush()
            os.fsync(audit.fileno())
            return at

        active = None
        try:
            copy_sha = write_new(output / "plan.json", plan)
            receipt["plan_copy_sha256"] = copy_sha
            record("started", plan_sha256=plan_sha256, plan_copy_sha256=copy_sha)
            previous_end = plan["prepared_at_ns"]
            for index, assignment in enumerate(plan["sessions"]):
                if index:
                    await sleeper(plan["pause_seconds"])
                _check_binding(plan)
                active = index
                intent = record("session_started", **assignment)
                boundary = previous_end + (plan["pause_seconds"] * NS if index else 0)
                if intent <= boundary:
                    raise ValueError(
                        "Acquisition clock regressed or the frozen gap has not elapsed."
                    )
                receipt["sessions"][index]["status"] = "started"
                item = await _collect_slot(
                    plan,
                    plan_sha256,
                    assignment,
                    collector=collector,
                    earliest_ns=max(intent, boundary),
                    clock=clock,
                )
                previous_end = item["source"]["ended_at_ns"]
                record("session_completed", session=item)
                receipt["sessions"][index] = item
                active = None
            receipt["status"] = "completed"
            receipt_sha = hashlib.sha256((canonical(receipt) + "\n").encode()).hexdigest()
            record("receipt_prepared", receipt_sha256=receipt_sha)
            write_new(output / "receipt.json", receipt)
        except BaseException as error:
            if active is not None:
                receipt["sessions"][active]["status"] = "failed"
            receipt["status"] = "failed"
            # Export fixed codes, never packet-bearing exception messages or traceback text.
            receipt["error_type"] = safe_error_type(error)
            receipt["failure"] = failure_details(error)
            record(
                "failed",
                error_type=safe_error_type(error),
                active_session=active,
                failure=receipt["failure"],
            )
            write_new(output / "failure.json", receipt)
            raise
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Offline; freezes roles without collecting data.")
    prepare.add_argument("--plan", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--campaign-id", required=True)
    for role in ROLES:
        prepare.add_argument(f"--{role}", type=int, default=1)
    prepare.add_argument("--seconds-per-session", type=int, default=60)
    prepare.add_argument("--pause-seconds", type=int, default=5)
    prepare.add_argument("--research-timing", action="store_true")
    run = commands.add_parser("run")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--plan-sha256", required=True)
    run.add_argument("--enable-public-capture", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        plan = prepare_plan(**{k: v for k, v in vars(args).items() if k not in ("command", "plan")})
        print(canonical({"plan_sha256": write_new(args.plan, plan), "sessions": plan["sessions"]}))
    else:
        receipt = asyncio.run(
            run_plan(args.plan, args.plan_sha256, enable_public_capture=args.enable_public_capture)
        )
        print(canonical(receipt))


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        # Do not print tracebacks containing protected raw records from a dependency.
        print(
            canonical(
                {
                    "status": "failed",
                    "error_type": safe_error_type(error),
                    "failure": failure_details(error),
                    "message": "Acquisition stopped. Keep the plan, audit and any partials.",
                }
            )
        )
        raise SystemExit(1) from None
