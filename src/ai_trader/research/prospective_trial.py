"""Verify completed acquisition metadata and freeze a new research experiment offline.

No raw capture opens, network, labels, fitting or orders. Historical acquisition
fingerprints are retained, not rewritten to match the new research implementation.
"""

import argparse
import hashlib
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from ai_trader.ingestion.planned_capture import (
    AUTHORITY,
    DEFAULT_LIMITS,
    NS,
    RECEIPT_KIND,
    TIMED_RECEIPT_KIND,
    TIMING_CONTRACT,
    _integer,
    _shape,
    timing_filename,
    validate_plan,
    validate_timing_counts,
    write_new,
)
from ai_trader.models.local_checkpoint import canonical, check_digest, strict_json
from ai_trader.research.microstructure_trial import (
    MicrostructureRegistration,
    SourceDeclaration,
    _decode_gateway,
    _decode_policy,
    _decode_replay,
    _environment,
    _implementation_hash,
    register_trial,
)
from ai_trader.trading.trade_journal import _decimal
from ai_trader.training.event_training_data import _manifest, register_event_split
from ai_trader.training.microstructure_data import _json
from ai_trader.training.train_event_baseline import (
    _decode_config,
    _recipe,
    register_event_baseline,
)


def _pinned_bytes(path, expected, *, max_bytes=64 * 1024):
    check_digest(expected)
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Explicit regular metadata file required.")
    with path.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    if not raw or len(raw) > max_bytes or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Metadata byte budget or SHA256 mismatch.")
    return raw


def _verify_timing(output, plan_sha256, assignment, item):
    """Read only pinned research telemetry; reserved reports are forbidden, never opened."""
    filename = timing_filename(assignment)
    path = output / filename
    partial = path.with_name(filename + ".partial")
    if partial.exists() or partial.is_symlink():
        raise ValueError("Incomplete timing publication remains quarantined.")
    if assignment["split"] == "reserved":
        if item["timing"] is not None or path.exists() or path.is_symlink():
            raise ValueError("Reserved timing must remain unavailable to research.")
        return
    reference = item["timing"]
    _shape(reference, ("filename", "sha256", "bytes"))
    if reference["filename"] != filename:
        raise ValueError("Timing filename differs from its frozen source.")
    _integer(reference["bytes"], 1, TIMING_CONTRACT["max_report_bytes"])
    raw = _pinned_bytes(path, reference["sha256"], max_bytes=TIMING_CONTRACT["max_report_bytes"])
    if len(raw) != reference["bytes"]:
        raise ValueError("Timing report byte count mismatch.")
    envelope = strict_json(raw)
    _shape(envelope, ("report", "report_sha256"))
    report = envelope["report"]
    if hashlib.sha256(_json(report).encode()).hexdigest() != envelope["report_sha256"]:
        raise ValueError("Timing report payload digest mismatch.")
    fixed = {
        "schema_version": 1,
        "kind": TIMING_CONTRACT["kind"],
        "plan_sha256": plan_sha256,
        **assignment,
        "status": "completed",
        "source_sha256": item["source"]["source_sha256"],
        "error_type": None,
        "authority": AUTHORITY,
    }
    _shape(report, (*fixed, "diagnostics"))
    if canonical({k: report[k] for k in fixed}) != canonical(fixed):
        raise ValueError("Timing report disagrees with the completed acquisition slot.")
    validate_timing_counts(report["diagnostics"], item)


@dataclass(frozen=True, slots=True)
class CompletedCampaign:
    sources: tuple[SourceDeclaration, ...]
    training_session_count: int
    research_paths: tuple[Path, ...]
    acquisition_implementation_sha256: str
    acquisition_environment_json: str
    completed_at_ns: int


def load_completed_campaign(*, plan_path, plan_sha256, receipt_sha256, audit_sha256):
    """Read pinned metadata and optional research telemetry only; never raw source contents.

    A strict audit transcript must agree with all frozen slots and the final receipt.
    Later source reproduction is mandatory; this does not certify independent custody.
    """
    plan = strict_json(_pinned_bytes(plan_path, plan_sha256))
    validate_plan(plan)  # Historical contract, deliberately NOT current-code equality.
    output = Path(plan["output_dir"])
    receipt = strict_json(_pinned_bytes(output / "receipt.json", receipt_sha256))
    _shape(
        receipt,
        (
            "schema_version",
            "kind",
            "plan_sha256",
            "plan_copy_sha256",
            "campaign_id",
            "status",
            "sessions",
            "reserved_integrity_only",
            "independence_authenticated",
            "model_calls",
            "optimization_steps",
            "orders",
            "authority",
        ),
    )
    fixed = {
        "schema_version": plan["schema_version"],
        "kind": TIMED_RECEIPT_KIND if plan["schema_version"] == 2 else RECEIPT_KIND,
        "plan_sha256": plan_sha256,
        "campaign_id": plan["campaign_id"],
        "status": "completed",
        "reserved_integrity_only": True,
        "independence_authenticated": False,
        "model_calls": 0,
        "optimization_steps": 0,
        "orders": 0,
        "authority": AUTHORITY,
    }
    if canonical({k: receipt[k] for k in fixed}) != canonical(fixed):
        raise ValueError("Only complete unpromoted acquisition receipts are accepted.")
    copied = strict_json(_pinned_bytes(output / "plan.json", receipt["plan_copy_sha256"]))
    if canonical(copied) != canonical(plan):
        raise ValueError("Acquisition plan copy disagrees with original frozen plan.")
    # Only existence checks, never contents or directory discovery of raw data.
    forbidden = [
        "failure.json",
        "failure.json.partial",
        "receipt.json.partial",
        "plan.json.partial",
    ]
    forbidden += [s["filename"] + ".partial" for s in plan["sessions"]]
    if any((output / name).exists() or (output / name).is_symlink() for name in forbidden):
        raise ValueError("Failed or incomplete acquisition publication remains quarantined.")
    audit = [
        strict_json(line)
        for line in _pinned_bytes(output / "audit.jsonl", audit_sha256).splitlines()
    ]
    count = len(plan["sessions"])
    if (
        type(receipt["sessions"]) is not list
        or len(receipt["sessions"]) != count
        or len(audit) != 2 + 2 * count
    ):
        raise ValueError("Every frozen acquisition slot must complete exactly once.")
    prior = plan["prepared_at_ns"]
    for event in audit:
        if type(event) is not dict:
            raise ValueError("Invalid audit event.")
        _integer(event.get("at_ns"), prior, 2**63 - 1)
        prior = event["at_ns"]
    if audit[0]["at_ns"] <= plan["prepared_at_ns"] or prior > time.time_ns():
        raise ValueError("Acquisition audit must follow preparation and cannot be future dated.")
    expected_audit = [
        {
            "status": "started",
            "at_ns": audit[0]["at_ns"],
            "plan_sha256": plan_sha256,
            "plan_copy_sha256": receipt["plan_copy_sha256"],
        }
    ]
    sources, research_paths = [], []
    previous_end = plan["prepared_at_ns"]
    for index, (assignment, item) in enumerate(
        zip(plan["sessions"], receipt["sessions"], strict=True)
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
                *(("timing",) if plan["schema_version"] == 2 else ()),
            ),
        )
        if (
            canonical({k: item[k] for k in assignment}) != canonical(assignment)
            or item["status"] != "completed"
        ):
            raise ValueError("A frozen session was omitted, replaced, reordered or reassigned.")
        _shape(
            item["source"],
            ("source_session", "source_sha256", "started_at_ns", "ended_at_ns", "role"),
        )
        source = SourceDeclaration(**item["source"])
        expected_role = "reserved" if assignment["split"] == "reserved" else "research"
        if source.source_session != assignment["source_session"] or source.role != expected_role:
            raise ValueError("Source identity or role differs from the prospective assignment.")
        intent, completion = audit[1 + 2 * index], audit[2 + 2 * index]
        boundary = previous_end + (plan["pause_seconds"] * NS if index else 0)
        if (
            not boundary
            < intent["at_ns"]
            < source.started_at_ns
            < source.ended_at_ns
            <= completion["at_ns"]
        ):
            raise ValueError(
                "Source chronology, intent or prospective gap disagrees with the audit."
            )
        duration = source.ended_at_ns - source.started_at_ns
        if (
            not (plan["seconds_per_session"] - 1) * NS
            <= duration
            <= (plan["seconds_per_session"] + 5) * NS
        ):
            raise ValueError("Recorded duration differs from its frozen acquisition budget.")
        _integer(item["snapshot_received_at_ns"], source.started_at_ns, source.ended_at_ns)
        _integer(item["bytes"], 1, DEFAULT_LIMITS.max_bytes)
        _integer(item["trade_events"], 0, DEFAULT_LIMITS.max_events)
        _integer(item["depth_events"], 1, DEFAULT_LIMITS.max_events)
        if item["trade_events"] + item["depth_events"] > DEFAULT_LIMITS.max_events:
            raise ValueError("Recorded event count exceeds the acquisition budget.")
        if plan["schema_version"] == 2:
            _verify_timing(output, plan_sha256, assignment, item)
        expected_audit.extend(
            [
                {"status": "session_started", "at_ns": intent["at_ns"], **assignment},
                {"status": "session_completed", "at_ns": completion["at_ns"], "session": item},
            ]
        )
        sources.append(source)
        if source.role == "research":
            research_paths.append(output / assignment["filename"])
        previous_end = source.ended_at_ns
    expected_audit.append(
        {
            "status": "receipt_prepared",
            "at_ns": audit[-1]["at_ns"],
            "receipt_sha256": receipt_sha256,
        }
    )
    if canonical(audit) != canonical(expected_audit):
        raise ValueError("Audit transcript does not match complete acquisition receipt.")
    if len({s.source_sha256 for s in sources}) != len(sources):
        raise ValueError("Aliased source bytes across acquisition sessions.")
    return CompletedCampaign(
        tuple(sources),
        plan["counts"]["train"],
        tuple(research_paths),
        plan["implementation_sha256"],
        plan["environment_json"],
        audit[-1]["at_ns"],
    )


def prepare_campaign_trial(
    *,
    plan_path,
    plan_sha256,
    receipt_sha256,
    audit_sha256,
    settings_path,
    settings_sha256,
    output_dir,
):
    """Freeze registration/fold/recipe before outcomes; never grant training permission."""
    campaign = load_completed_campaign(
        plan_path=plan_path,
        plan_sha256=plan_sha256,
        receipt_sha256=receipt_sha256,
        audit_sha256=audit_sha256,
    )
    settings = strict_json(_pinned_bytes(settings_path, settings_sha256))
    return _prepare_verified_campaign(
        campaign=campaign,
        settings=settings,
        output_dir=output_dir,
        provenance={
            "schema_version": 1,
            "kind": "prospective_research_preparation_v1",
            "plan_sha256": plan_sha256,
            "receipt_sha256": receipt_sha256,
            "audit_sha256": audit_sha256,
            "settings_sha256": settings_sha256,
        },
    )


def _prepare_verified_campaign(*, campaign, settings, output_dir, provenance):
    """Shared metadata-only writer, after the public intake has verified its full campaign."""
    if type(campaign) is not CompletedCampaign:
        raise ValueError("A verified campaign metadata record is required.")
    _shape(
        settings,
        ("trial_id", "policy", "replay", "gateway", "initial_cash_usdt", "fold", "baseline"),
    )
    _shape(
        settings["fold"],
        (
            "max_frames_per_session",
            "embargo_ns",
            "minimum_resolved_per_session",
            "minimum_resolved_fraction",
        ),
    )
    fold_settings = {
        **settings["fold"],
        "minimum_resolved_fraction": _decimal(settings["fold"]["minimum_resolved_fraction"]),
    }
    baseline = _decode_config(settings["baseline"])
    trial_settings = {
        "trial_id": settings["trial_id"],
        "sources": campaign.sources,
        "policy": _decode_policy(settings["policy"]),
        "replay": _decode_replay(settings["replay"]),
        "gateway": _decode_gateway(settings["gateway"]),
        "initial_cash_usdt": _decimal(settings["initial_cash_usdt"]),
    }
    # Validate every knob and aggregate budget before creating any output.
    preview = MicrostructureRegistration(
        **trial_settings,
        registered_at_ns=time.time_ns(),
        implementation_sha256=_implementation_hash(),
        environment_json=_environment(),
    )
    manifest = _manifest(
        preview, training_session_count=campaign.training_session_count, **fold_settings
    )
    _recipe(preview, manifest, baseline)
    output = Path(output_dir).resolve()
    output.mkdir()  # A partial preparation is never silently resumed or overwritten.
    provenance = {
        **provenance,
        "acquisition_completed_at_ns": campaign.completed_at_ns,
        "acquisition_implementation_sha256": campaign.acquisition_implementation_sha256,
        "acquisition_environment_json": campaign.acquisition_environment_json,
        "source_declarations": [asdict(s) for s in campaign.sources],
        "training_session_count": campaign.training_session_count,
        "research_paths": [str(path) for path in campaign.research_paths],
        "raw_captures_opened": 0,
        "independence_authenticated": False,
        "authority": dict(AUTHORITY),
    }
    write_new(output / "preparation_intent.json", provenance)
    record = register_trial(output / "registration.json", **trial_settings)
    register_event_split(
        registration_path=output / "registration.json",
        output_path=output / "split.json",
        training_session_count=campaign.training_session_count,
        **fold_settings,
    )
    register_event_baseline(
        registration_path=output / "registration.json",
        manifest_path=output / "split.json",
        output_path=output / "recipe.json",
        config=baseline,
    )
    if (
        record.implementation_sha256 != preview.implementation_sha256
        or record.environment_json != preview.environment_json
        or record.implementation_sha256 != _implementation_hash()
        or record.environment_json != _environment()
        or record.registered_at_ns < campaign.completed_at_ns
    ):
        raise ValueError(
            "Research implementation, environment or clock changed during preparation."
        )
    provenance.update(
        status="prepared",
        research_implementation_sha256=record.implementation_sha256,
        research_environment_json=record.environment_json,
        registered_at_ns=record.registered_at_ns,
        artifacts={
            name: hashlib.sha256((output / name).read_bytes()).hexdigest()
            for name in ("registration.json", "split.json", "recipe.json")
        },
    )
    write_new(output / "prepared.json", provenance)
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--audit-sha256", required=True)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--settings-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = prepare_campaign_trial(
        plan_path=args.plan,
        plan_sha256=args.plan_sha256,
        receipt_sha256=args.receipt_sha256,
        audit_sha256=args.audit_sha256,
        settings_path=args.settings,
        settings_sha256=args.settings_sha256,
        output_dir=args.output_dir,
    )
    print(canonical(result))


if __name__ == "__main__":
    main()
