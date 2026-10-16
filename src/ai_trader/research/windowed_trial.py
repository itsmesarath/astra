"""Pinned all-window acquisition intake; frozen settings, no raw/research data reads."""

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

from ai_trader.ingestion.capture_schedule import (
    CONNECTION_ALLOWANCE_NS,
    RUNTIME,
    validate_completion_times,
    validate_schedule,
)
from ai_trader.ingestion.planned_capture import AUTHORITY, DEFAULT_LIMITS, _integer, _shape
from ai_trader.ingestion.windowed_capture import RECEIPT_KIND
from ai_trader.models.local_checkpoint import canonical, strict_json
from ai_trader.research.microstructure_trial import SourceDeclaration
from ai_trader.research.prospective_trial import (
    CompletedCampaign,
    _pinned_bytes,
    _prepare_verified_campaign,
    _verify_timing,
)


@dataclass(frozen=True, slots=True)
class CompletedWindowCampaign:
    campaign: CompletedCampaign
    research_settings_json: str
    research_settings_sha256: str


def load_completed_schedule(*, schedule_path, schedule_sha256, receipt_sha256, audit_sha256):
    """Validate historical metadata and research telemetry, never raw or reserved contents.

    Pins are consistency evidence, not proof of independent custody. Actual source
    reproduction is still mandatory before labels/fitting; no authority is granted.
    """
    schedule = strict_json(_pinned_bytes(schedule_path, schedule_sha256))
    validate_schedule(schedule)  # Historical acquisition code is not replaced with current code.
    if schedule["schema_version"] != 2:
        raise ValueError("Only completed runnable V2 window campaigns are supported.")
    acquisition = schedule["acquisition"]
    output = Path(acquisition["output_dir"])
    receipt = strict_json(_pinned_bytes(output / "receipt.json", receipt_sha256))
    fixed = {
        "schema_version": 1,
        "kind": RECEIPT_KIND,
        "schedule_sha256": schedule_sha256,
        "campaign_id": acquisition["campaign_id"],
        "status": "completed",
        "reserved_integrity_only": True,
        "independence_authenticated": False,
        "model_calls": 0,
        "optimization_steps": 0,
        "orders": 0,
        "authority": AUTHORITY,
    }
    _shape(receipt, (*fixed, "schedule_copy_sha256", "clock_origin_wall_ns", "sessions"))
    if canonical({k: receipt[k] for k in fixed}) != canonical(fixed):
        raise ValueError("Only complete unpromoted window receipts are accepted.")
    copied = strict_json(_pinned_bytes(output / "schedule.json", receipt["schedule_copy_sha256"]))
    if canonical(copied) != canonical(schedule):
        raise ValueError("Frozen schedule copy mismatch.")
    forbidden = [
        "failure.json",
        "failure.json.partial",
        "receipt.json.partial",
        "schedule.json.partial",
        "plan.json",  # Reject an ambiguous/downgraded back-to-back campaign directory.
        *[s["filename"] + ".partial" for s in acquisition["sessions"]],
    ]
    if any((output / name).exists() or (output / name).is_symlink() for name in forbidden):
        raise ValueError("Failed, incomplete or ambiguous acquisition remains quarantined.")
    audit = [
        strict_json(line)
        for line in _pinned_bytes(output / "audit.jsonl", audit_sha256).splitlines()
    ]
    count = len(acquisition["sessions"])
    if (
        type(receipt["sessions"]) is not list
        or len(receipt["sessions"]) != count
        or len(audit) != 2 + 3 * count
    ):
        raise ValueError("Every frozen window must complete exactly once with a connection guard.")
    origin = receipt["clock_origin_wall_ns"]
    _integer(origin, acquisition["prepared_at_ns"] + 1, 2**63 - 1)
    previous_wall, previous_elapsed = origin, 0
    for event in audit:
        if type(event) is not dict:
            raise ValueError("Invalid window audit event.")
        _integer(event.get("at_ns"), previous_wall, 2**63 - 1)
        _integer(event.get("elapsed_ns"), previous_elapsed, 2**63 - 1)
        previous_wall, previous_elapsed = event["at_ns"], event["elapsed_ns"]
    if previous_wall > time.time_ns():
        raise ValueError("Acquisition audit cannot be future dated.")

    def event_at(index, status, **values):
        return {
            "status": status,
            "at_ns": audit[index]["at_ns"],
            "elapsed_ns": audit[index]["elapsed_ns"],
            **values,
        }

    expected = [
        event_at(
            0,
            "started",
            schedule_sha256=schedule_sha256,
            schedule_copy_sha256=receipt["schedule_copy_sha256"],
            clock_origin_wall_ns=origin,
        )
    ]
    sources, research_paths, completion = [], [], []
    for index, (assignment, window, item) in enumerate(
        zip(
            acquisition["sessions"],
            schedule["windows"],
            receipt["sessions"],
            strict=True,
        )
    ):
        _shape(
            item,
            (
                *assignment,
                "status",
                "source",
                "snapshot_received_at_ns",
                "bytes",
                "trade_events",
                "depth_events",
                "timing",
                "window_evidence",
            ),
        )
        if (
            canonical({k: item[k] for k in assignment}) != canonical(assignment)
            or item["status"] != "completed"
        ):
            raise ValueError("Window source omitted, replaced, reordered or reassigned.")
        _shape(
            item["source"],
            ("source_session", "source_sha256", "started_at_ns", "ended_at_ns", "role"),
        )
        source = SourceDeclaration(**item["source"])
        if source.source_session != assignment["source_session"] or source.role != (
            "reserved" if assignment["split"] == "reserved" else "research"
        ):
            raise ValueError("Source identity/role differs from the window assignment.")
        evidence = item["window_evidence"]
        _shape(
            evidence,
            (
                "intent_at_ns",
                "dispatched_at_ns",
                "dispatch_elapsed_ns",
                "started_at_ns",
                "connected_at_ns",
                "connected_elapsed_ns",
            ),
        )
        for value in evidence.values():
            _integer(value, 0, 2**63 - 1)
        intent, connected, ended = audit[1 + 3 * index : 4 + 3 * index]
        deadline = window["latest_capture_end_ns"] + RUNTIME["completion_grace_ns"]
        if (
            not window["open_at_ns"]
            <= intent["at_ns"]
            == evidence["intent_at_ns"]
            <= evidence["dispatched_at_ns"]
            <= window["last_dispatch_at_ns"]
            or not window["open_at_ns"]
            <= origin + intent["elapsed_ns"]
            <= window["last_dispatch_at_ns"]
            or not window["open_at_ns"]
            <= origin + evidence["dispatch_elapsed_ns"]
            <= window["last_dispatch_at_ns"]
            or not intent["elapsed_ns"]
            <= evidence["dispatch_elapsed_ns"]
            <= evidence["connected_elapsed_ns"]
            == connected["elapsed_ns"]
            or evidence["connected_elapsed_ns"] - evidence["dispatch_elapsed_ns"]
            > CONNECTION_ALLOWANCE_NS
            or not source.started_at_ns
            == evidence["started_at_ns"]
            <= evidence["connected_at_ns"]
            == connected["at_ns"]
            <= evidence["dispatched_at_ns"] + CONNECTION_ALLOWANCE_NS
            or not source.ended_at_ns <= ended["at_ns"] <= deadline
            or origin + ended["elapsed_ns"] > deadline
        ):
            raise ValueError("Window clock/dispatch/connection evidence mismatch.")
        completion.append(
            {
                "source_session": source.source_session,
                "dispatched_at_ns": evidence["dispatched_at_ns"],
                "started_at_ns": source.started_at_ns,
                "ended_at_ns": source.ended_at_ns,
            }
        )
        _integer(item["snapshot_received_at_ns"], source.started_at_ns, source.ended_at_ns)
        _integer(item["bytes"], 1, DEFAULT_LIMITS.max_bytes)
        _integer(item["trade_events"], 0, DEFAULT_LIMITS.max_events)
        _integer(item["depth_events"], 1, DEFAULT_LIMITS.max_events)
        if item["trade_events"] + item["depth_events"] > DEFAULT_LIMITS.max_events:
            raise ValueError("Source event quota exceeded.")
        _verify_timing(output, schedule_sha256, assignment, item)
        expected.extend(
            [
                event_at(1 + 3 * index, "session_started", **assignment),
                event_at(
                    2 + 3 * index,
                    "session_connected",
                    source_session=source.source_session,
                    **{k: v for k, v in evidence.items() if k != "intent_at_ns"},
                ),
                event_at(3 + 3 * index, "session_completed", session=item),
            ]
        )
        sources.append(source)
        if source.role == "research":
            research_paths.append(output / assignment["filename"])
    validate_completion_times(schedule, tuple(completion))
    expected.append(event_at(-1, "receipt_prepared", receipt_sha256=receipt_sha256))
    if canonical(audit) != canonical(expected):
        raise ValueError("Audit does not match all declared window completions.")
    if len({s.source_sha256 for s in sources}) != len(sources):
        raise ValueError("Aliased capture bytes across windows.")
    return CompletedWindowCampaign(
        CompletedCampaign(
            tuple(sources),
            acquisition["counts"]["train"],
            tuple(research_paths),
            acquisition["implementation_sha256"],
            acquisition["environment_json"],
            audit[-1]["at_ns"],
        ),
        schedule["research_settings_json"],
        schedule["research_settings_sha256"],
    )


def prepare_windowed_trial(
    *, schedule_path, schedule_sha256, receipt_sha256, audit_sha256, output_dir
):
    """Use only the embedded pre-capture recipe; no settings override or automatic fitting."""
    completed = load_completed_schedule(
        schedule_path=schedule_path,
        schedule_sha256=schedule_sha256,
        receipt_sha256=receipt_sha256,
        audit_sha256=audit_sha256,
    )
    return _prepare_verified_campaign(
        campaign=completed.campaign,
        settings=strict_json(completed.research_settings_json),
        output_dir=output_dir,
        provenance={
            "schema_version": 1,
            "kind": "windowed_research_preparation_v1",
            "schedule_sha256": schedule_sha256,
            "receipt_sha256": receipt_sha256,
            "audit_sha256": audit_sha256,
            "settings_sha256": completed.research_settings_sha256,
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--schedule-sha256", required=True)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--audit-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(
        canonical(
            prepare_windowed_trial(
                schedule_path=args.schedule,
                schedule_sha256=args.schedule_sha256,
                receipt_sha256=args.receipt_sha256,
                audit_sha256=args.audit_sha256,
                output_dir=args.output_dir,
            )
        )
    )


if __name__ == "__main__":
    main()
