"""Separately registered clock-policy revision of the exposed development comparison."""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ai_trader.research import databento_6e_receive_clock as receive
from ai_trader.research import historical_6e_clock_diagnostic as diagnostic
from ai_trader.research import historical_6e_cohort as v1

common, source, study = v1.common, v1.source, v1.study
ATTEMPT_PIN = "212221bc8390dd8f4afcb4335a57e1ad9eb31005ab6dac52dd96beb54d7de64b"
DIAGNOSTIC_PATH = "data/processed/6e_multimonth_development_20261001_1_clock_diagnostic.json"
DIAGNOSTIC_PIN = "a80a58b1e1c4b198492329b43abf074f5d8d0cb67a821ccf1083454a644b7eef"


def protocol() -> dict:
    return {
        **v1.protocol(),
        "artifact_type": "6e_multimonth_development_v2",
        "receive_clock_policy": receive.policy(),
        "revision_reason": "V1 refused cross-clock disagreement after the decision window; "
        "replace only the blanket cross-clock inequality, not flags, books or receive order",
        "prior_registration_sha256": diagnostic.REGISTRATION_PIN,
        "prior_attempt_sha256": ATTEMPT_PIN,
        "prior_failure_sha256": diagnostic.FAILURE_PIN,
        "diagnostic_sha256": DIAGNOSTIC_PIN,
        "exposure": "All twelve members conservatively exposed by V1; no independent test claim",
        "unchanged_comparison": "Same days, contracts, nine signs, 37 features, entry/exit, costs, "
        "April feature strata and no-fit/no-promotion rules; no outcome-based revision",
    }


def fingerprints() -> dict:
    return {
        **v1.fingerprints(),
        **{
            p.name: common.hash_file(p, 1024**2)
            for p in (Path(receive.__file__), Path(diagnostic.__file__), Path(__file__))
        },
    }


def preflight(root: Path) -> dict:
    previous = root / diagnostic.REGISTRATION
    old = v1.registration(root, previous, diagnostic.REGISTRATION_PIN)
    attempt = v1.read_pinned(previous.with_suffix(".attempt.json"), ATTEMPT_PIN)
    failure = v1.read_pinned(previous.with_suffix(".failure.json"), diagnostic.FAILURE_PIN)
    audit = v1.read_pinned(root / DIAGNOSTIC_PATH, DIAGNOSTIC_PIN)
    days = [d for b in v1.BLOCKS for d in b.source_days]
    if (
        attempt["registration_sha256"] != diagnostic.REGISTRATION_PIN
        or attempt["conservatively_exposed_source_days"] != days
        or failure["registration_sha256"] != diagnostic.REGISTRATION_PIN
        or failure["status"] != "failed_whole_cohort"
        or audit["registration_sha256"] != diagnostic.REGISTRATION_PIN
    ):
        raise ValueError("Prior failure and exposure evidence do not match")
    result = old["preflight"]
    for item in result["ledger"]:
        if item["utc_date"] in days:
            if item["partition"] != "development":
                raise ValueError("Prior attempted source overlaps a reserved partition")
            if item["prior_access"] == "no_replay_documented":
                item["prior_access"] = "prior_attempt_conservatively_exposed"
    result["prior_access_counts"] = dict(Counter(r["prior_access"] for r in result["ledger"]))
    result["prior_attempt_conservative_exposure_days"] = days
    return result


def prepare(root: Path, path: Path) -> dict:
    result = {
        "protocol": protocol(),
        "implementation_sha256": fingerprints(),
        "preflight": preflight(root),
        "prepared_utc": datetime.now(UTC).isoformat(),
    }
    common._write_new(path, result)
    return result


def registration(root: Path, path: Path, pin: str) -> dict:
    result = v1.read_pinned(path, pin)
    if (
        result.get("protocol") != protocol()
        or result.get("implementation_sha256") != fingerprints()
        or result.get("preflight") != preflight(root)
    ):
        raise ValueError("V2 registration, implementation or prior evidence changed")
    return result


def replay_block(root: Path, block: v1.Block) -> tuple[list[dict], dict]:
    block.validate()
    _, members, _ = source.selected_sources(
        {
            "source_intake_report": v1.INTAKE,
            "source_intake_sha256": v1.INTAKE_SHA256,
            "source_sessions": list(block.sessions),
        },
        root,
    )
    builder = receive.ReceiveTimeBuilder(block)
    mappings = []
    for member in members:
        path = member["archive"]
        stamp = (path.stat().st_size, path.stat().st_mtime_ns)
        print(f"V2 replay {block.name} {block.contract} {member['day']}", flush=True)
        with zipfile.ZipFile(path) as archive:
            builder.start_day(member["day"])
            for record in source._member_records(archive, member):
                builder.consume(record)
                if len(builder.rows) > 43_200:
                    raise ValueError("Per-block row bound exceeded")
            builder.finish_day()
        if (path.stat().st_size, path.stat().st_mtime_ns) != stamp:
            raise ValueError("Source archive changed during V2 replay")
        mappings.append(
            {
                "utc_date": member["day"].isoformat(),
                "contract": block.contract,
                "instrument_id": builder.instrument_id,
            }
        )
    rows, quality = builder.finish()
    study.audit_conservation(quality["execution_flow"])
    for row in rows:
        row.update(contract=block.contract, block=block.name, partition="development")
    return rows, {"block": block.name, "quality": quality, "dated_contract_mappings": mappings}


def run(
    root: Path, registration_path: Path, pin: str, rows_output: Path, report_output: Path
) -> dict:
    attempt_path = registration_path.with_suffix(".attempt.json")
    failure_path = registration_path.with_suffix(".failure.json")
    paths = (registration_path, attempt_path, failure_path, rows_output, report_output)
    if len({p.resolve() for p in paths}) != 5 or any(p.exists() for p in paths[1:]):
        raise ValueError("Refusing to reuse or overwrite V2 research evidence")
    frozen = registration(root, registration_path, pin)
    common._write_new(
        attempt_path,
        {
            "registration_sha256": pin,
            "started_utc": datetime.now(UTC).isoformat(),
            "status": "claimed_not_proof_of_completion",
            "conservatively_exposed_source_days": [d for b in v1.BLOCKS for d in b.source_days],
        },
    )
    active = None
    try:
        rows, evidence = [], []
        for block in v1.BLOCKS:
            active = block.name
            batch, quality = replay_block(root, block)
            rows.extend(batch)
            evidence.append(quality)
            if len(rows) > v1.MAX_ROWS:
                raise ValueError("Cohort row bound exceeded")
        v1.verify_july(root, rows)
        reference = [
            r["features"]["log_quote_events_5s"]
            for r in rows
            if r["eligible"] and r["source_session"] == v1.BLOCKS[0].sessions[0]
        ]
        cuts = np.unique(np.quantile(reference, [1 / 3, 2 / 3]))
        raw = bytearray()
        for row in rows:
            raw.extend(common.canonical(row) + b"\n")
            if len(raw) > v1.MAX_OUTPUT_BYTES:
                raise ValueError("Cohort output byte bound exceeded")
        result = {
            "artifact_type": "6e_multimonth_development_report_v2",
            "status": "completed",
            "registration_sha256": pin,
            "implementation_sha256": frozen["implementation_sha256"],
            "protocol": frozen["protocol"],
            "rows": len(rows),
            "rows_sha256": hashlib.sha256(raw).hexdigest(),
            "july_regression": "all_original_features_execution_features_and_targets_exact",
            "activity_cuts_from_april7": cuts.tolist(),
            "evidence": evidence,
            "summary": study.summarize(rows, cuts),
            "by_block": {
                b.name: study.summarize([r for r in rows if r["block"] == b.name], cuts)
                for b in v1.BLOCKS
            },
            "by_session": {
                s: study.summarize([r for r in rows if r["source_session"] == s], cuts)
                for b in v1.BLOCKS
                for s in b.sessions
            },
            "decision": "development_comparison_only_no_promotion",
            "training_enabled": False,
            "trading_enabled": False,
            "promotion_enabled": False,
        }
        registration(root, registration_path, pin)
        study.data.clock._publish(rows_output, report_output, raw, result)
        return result
    except Exception as exc:
        common._write_new(
            failure_path,
            {
                "status": "failed_whole_cohort",
                "registration_sha256": pin,
                "block": active,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "successful_subset_permitted": False,
                "automatic_retry_permitted": False,
            },
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--registration-sha256")
    parser.add_argument("--rows-output", type=Path)
    parser.add_argument("--report-output", type=Path)
    args = parser.parse_args()
    if args.prepare:
        record = prepare(args.project_root, args.registration)
        print(common.canonical(record["preflight"]["prior_access_counts"]).decode())
    else:
        if None in (args.registration_sha256, args.rows_output, args.report_output):
            parser.error("Registration pin and new rows/report paths required")
        result = run(
            args.project_root,
            args.registration,
            args.registration_sha256,
            args.rows_output,
            args.report_output,
        )
        print(common.canonical({k: result[k] for k in ("status", "rows", "rows_sha256")}).decode())


if __name__ == "__main__":
    main()
