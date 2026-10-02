"""Explicit, whole-session development training permission over immutable evidence.

No raw archives, reserved artifacts, model calls, source repair or trading.
Original research-only reports remain unchanged; this manifest has one purpose.
"""

from __future__ import annotations

import argparse
import hashlib
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from ai_trader.research import historical_6e_resource_replay as resource

diagnostic, review, census = resource.diagnostic, resource.review, resource.census
common = census.common
PURPOSE = "6e_activity_direction_baseline_v1"
TRAIN_END = "2025-09-01"
VALIDATION_END = "2025-11-01"
ROLES = ("train", "validation_development", "test_development")
DIAGNOSTIC_DIR = "data/processed/6e_refusal_diagnostic_20261002_1"
DIAGNOSTIC_PIN = "07ed88bfec5b3b8fcb3acaa22a270e78c5c4313ca8b673400a0271a7758a3f15"
RESOURCE_DIR = "data/processed/6e_resource_replay_20261002_1"
RESOURCE_PIN = "3fb0df6fcca5885226c2deb01ff063ff9a80479deb1a34c45fa104e178486545"
MAX_MANIFEST_BYTES = 2 * 1024**2
MAX_LINE = 64 * 1024


def role_for_day(day: str) -> str:
    if census.v1.partition(day) != "development":
        raise ValueError("Reserved dates cannot become development training sessions")
    return (
        "train"
        if day < TRAIN_END
        else ("validation_development" if day < VALIDATION_END else "test_development")
    )


def protocol() -> dict:
    return {
        "version": "6e_session_training_manifest_v1",
        "purpose": PURPOSE,
        "split": {
            "train_before": TRAIN_END,
            "validation_before": VALIDATION_END,
            "roles": list(ROLES),
            "unit": "Whole UTC source_session, never rows",
        },
        "window": "12:00-16:00 UTC; dated outright contracts, fresh daily state",
        "fit_inputs": "Causal sixty-second cases; resolved targets only; unknowns accounted",
        "evaluation_inputs": "Complete one-second decision rows, including unavailable outcomes",
        "exposure": "All 2025 evidence already exposed development; later roles are not holdouts",
        "exclusions": "Reconstruction-only Sundays, observed empty windows and vendor-degraded "
        "dates remain in coverage; no fabricated negative/no-trade labels",
        "training_permitted": True,
        "qwen_training": False,
        "trading_enabled": False,
        "promotion_enabled": False,
        "reserved_outcomes_opened": False,
    }


def fingerprints() -> dict:
    return {
        **resource.fingerprints(),
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
    }


def source_pins() -> dict:
    return {
        "census_registration": {
            "path": diagnostic.REGISTRATION,
            "sha256": diagnostic.REGISTRATION_PIN,
        },
        "census_completion": {
            "path": f"{diagnostic.CENSUS_DIRECTORY}/completion.json",
            "sha256": diagnostic.RECEIPT_PIN,
        },
        "diagnostic_completion": {
            "path": f"{DIAGNOSTIC_DIR}/completion.json",
            "sha256": DIAGNOSTIC_PIN,
        },
        "resource_completion": {"path": f"{RESOURCE_DIR}/completion.json", "sha256": RESOURCE_PIN},
    }


def artifact_path(root: Path, value: str) -> Path:
    path = root / value
    if path.is_symlink() or not path.resolve().is_relative_to((root / "data/processed").resolve()):
        raise ValueError("Training artifact must be unlinked and inside processed data")
    return path


def read_rows(root: Path, entry: dict, kind: str) -> list[dict]:
    # Refuse a reserved role/date before constructing any dataset path.
    day = entry["utc_date"]
    if (
        entry["role"] not in ROLES
        or entry["role"] != role_for_day(day)
        or entry["disposition"] != "decision_session"
        or kind not in {"rows", "cases"}
    ):
        raise ValueError("Unexpected training session, role or artifact kind")
    artifact = entry["artifacts"][kind]
    path = artifact_path(root, artifact["path"])
    limit = 14_400 if kind == "rows" else review.MAX_CASES_PER_DAY
    if type(artifact["count"]) is not int or not 1 <= artifact["count"] <= limit:
        raise ValueError("Invalid declared training row count")
    rows, size, digest = [], 0, hashlib.sha256()
    with path.open("rb") as handle:
        while raw := handle.readline(MAX_LINE + 1):
            size += len(raw)
            if (
                len(raw) > MAX_LINE
                or not raw.endswith(b"\n")
                or size > census.MAX_DAY_BYTES
                or len(rows) >= limit
            ):
                raise ValueError("Training JSONL exceeds its bounds or is incomplete")
            digest.update(raw)
            rows.append(common.loads(raw))
    if digest.hexdigest() != artifact["sha256"] or len(rows) != artifact["count"]:
        raise ValueError("Training artifact hash or count differs")
    census.baseline.validate_rows(rows, sessions=(day,), feature_names=census.study.data.FEATURES)
    for row in rows:
        execution = row["execution_features"]
        if (
            row["contract"] != entry["contract"]
            or row["partition"] != "development"
            or entry["contract"] != census.dated_contract(day)
            or set(execution) != set(census.study.flow.FEATURES)
            or any(
                type(v) not in (int, float) or not math.isfinite(v) or v < 0
                for v in execution.values()
            )
        ):
            raise ValueError("Training row identity or execution feature allowlist differs")
    if kind == "cases" and (
        any(r["eligible"] is not True for r in rows)
        or census.study.diagnostics.thin_causally(rows) != rows
    ):
        raise ValueError("Training cases violate causal sampling")
    return rows


def accounting(rows: list[dict]) -> dict:
    statuses = Counter(r["outcome"]["status"] for r in rows)
    return {
        "cases": len(rows),
        "statuses": dict(statuses),
        "resolved": statuses["resolved"],
        "unknown": len(rows) - statuses["resolved"],
    }


def decision_entry(root: Path, directory: Path, report: dict, report_pin: str) -> dict:
    day = report["utc_date"]
    if (
        report["contract"] != census.dated_contract(day)
        or report["full_member_hash_verified"] is not True
        or report["training_eligible"] is not False
        or report["promotion_enabled"] is not False
        or report["quality"]["receive_clock_v2"]["counts"].get("protected_disagreements", 0)
    ):
        raise ValueError("Decision report identity, source quality or operational flags differ")
    return {
        "utc_date": day,
        "partition": "development",
        "role": role_for_day(day),
        "disposition": "decision_session",
        "contract": report["contract"],
        "source_sha256": report["source_sha256"],
        "artifacts": {
            kind: {
                "path": (directory / f"{day}.{kind}.jsonl").relative_to(root).as_posix(),
                "sha256": report[f"{kind}_sha256"],
                "count": report[kind],
            }
            for kind in ("rows", "cases")
        },
        "report": {
            "path": (directory / f"{day}.json").relative_to(root).as_posix(),
            "sha256": report_pin,
        },
    }


def verified_additions(root: Path) -> tuple[dict, dict]:
    diag = review.pinned(root / DIAGNOSTIC_DIR / "completion.json", DIAGNOSTIC_PIN)
    res = review.pinned(root / RESOURCE_DIR / "completion.json", RESOURCE_PIN)
    if (
        (root / DIAGNOSTIC_DIR / "failure.json").exists()
        or (root / RESOURCE_DIR / "failure.json").exists()
        or diag["status"] != "all_refused_members_scanned_not_source_accepted"
        or res["status"] != "resource_correction_completed_not_strategy_validated"
        or diag["source_scope"] != diagnostic.scope(root)
        or res["source_scope"] != resource.scope(root)
        or diag["implementation_sha256"] != diagnostic.fingerprints()
        or res["implementation_sha256"] != resource.fingerprints()
    ):
        raise ValueError("Diagnostic/resource evidence is incomplete or changed")
    for record, keys in (
        (
            diag,
            (
                "quality_gate_changed",
                "source_modified",
                "new_labels_or_features",
                "reserved_raw_opened",
                "training_enabled",
                "trading_enabled",
                "promotion_enabled",
            ),
        ),
        (
            res,
            (
                "original_census_modified",
                "quality_gate_changed",
                "reserved_raw_opened",
                "training_enabled",
                "trading_enabled",
                "promotion_enabled",
            ),
        ),
    ):
        if any(record[k] is not False for k in keys):
            raise ValueError("Diagnostic/resource operational flags differ")
    refused = {r["member"]["utc_date"]: r for r in diag["source_scope"]["refused_dates"]}
    if [r["utc_date"] for r in diag["reports"]] != list(refused):
        raise ValueError("Diagnostic date accounting differs")
    diagnoses = {}
    for item in diag["reports"]:
        day = item["utc_date"]
        r = review.pinned(root / DIAGNOSTIC_DIR / f"{day}.json", item["report_sha256"])
        old = refused[day]
        if (
            r["member_sha256_verified_at_eof"] != old["member"]["sha256"]
            or r["original_failure_sha256"] != old["original_failure_sha256"]
            or r["original_error"] != old["original_error"]
            or r["source_accepted"] is not False
        ):
            raise ValueError("Diagnostic report identity differs")
        diagnoses[day] = r
    if [r["utc_date"] for r in res["reports"]] != [resource.CONTROL_DAY, resource.RESOURCE_DAY]:
        raise ValueError("Resource control or corrected date missing")
    members = {m["utc_date"]: m for m in res["source_scope"]["members"]}
    additions = {}
    for item in res["reports"]:
        day = item["utc_date"]
        r = review.pinned(root / RESOURCE_DIR / f"{day}.json", item["report_sha256"])
        if (
            r["status"] != "replayed_resource_correction"
            or r["registration_sha256"] != res["registration_sha256"]
            or r["source_sha256"] != members[day]["sha256"]
        ):
            raise ValueError("Unexpected resource status")
        entry = decision_entry(root, root / RESOURCE_DIR, r, item["report_sha256"])
        for kind in ("rows", "cases"):
            review.checked_hash(
                artifact_path(root, entry["artifacts"][kind]["path"]),
                entry["artifacts"][kind]["sha256"],
                census.MAX_DAY_BYTES,
            )
        for key, column in r["quote_columns"].items():
            if key not in resource.COLUMNS or column["bytes"] != r["completed_quotes"] * 8:
                raise ValueError("Resource quote-column identity differs")
            size = review.checked_hash(
                root / RESOURCE_DIR / f"{day}.quotes/{key}.i64",
                column["sha256"],
                resource.MAX_QUOTES * 8,
            )
            if size != column["bytes"]:
                raise ValueError("Resource quote-column byte count differs")
        if (
            set(r["quote_columns"]) != set(resource.COLUMNS)
            or not 1 <= r["completed_quotes"] <= resource.MAX_QUOTES
        ):
            raise ValueError("Resource quote count differs")
        if day == resource.CONTROL_DAY:
            if (
                r["control_byte_parity_verified"] is not True
                or r["rows_sha256"] != res["source_scope"]["control_rows_sha256"]
                or r["cases_sha256"] != res["source_scope"]["control_cases_sha256"]
            ):
                raise ValueError("Resource control parity differs")
        additions[day] = entry
    return diagnoses, additions


def build(root: Path) -> dict:
    root = root.resolve()
    implementation = fingerprints()
    frozen = census.registration(root, root / diagnostic.REGISTRATION, diagnostic.REGISTRATION_PIN)
    receipt, reports, cases = review.verify_census(
        root / diagnostic.CENSUS_DIRECTORY,
        root / diagnostic.REGISTRATION,
        diagnostic.REGISTRATION_PIN,
        diagnostic.RECEIPT_PIN,
    )
    diagnoses, additions = verified_additions(root)
    by_report = {r["utc_date"]: r for r in reports}
    by_case = defaultdict(list)
    for row in cases:
        by_case[row["source_session"]].append(row)
    original = {r["utc_date"]: r for r in receipt["dates"]}
    ledger = []
    for member in frozen["inventory"]["ledger"]:
        day = member["utc_date"]
        entry = {
            "utc_date": day,
            "partition": member["partition"],
            "original_status": original[day]["status"],
            "artifacts": None,
        }
        if member["partition"] != "development":
            entry.update(role=member["partition"], disposition="reserved_metadata_only")
        elif member["planned_action"] == "vendor_degraded_no_replay":
            entry.update(role="excluded", disposition="vendor_degraded")
        elif member["planned_action"] == "reconstruction_only":
            entry.update(role="excluded", disposition="reconstruction_only")
        elif original[day]["status"] == "replayed":
            entry.update(
                decision_entry(
                    root,
                    root / diagnostic.CENSUS_DIRECTORY / "days",
                    by_report[day],
                    original[day]["report_sha256"],
                )
            )
            entry["case_accounting"] = accounting(by_case[day])
        elif day == resource.RESOURCE_DAY:
            entry.update(additions[day])
            entry["case_accounting"] = accounting(read_rows(root, entry, "cases"))
            entry["resource_correction"] = True
        elif (
            diagnoses[day]["decision_window_empty_of_target_records"] is True
            and diagnoses[day]["original_error"]
            == "Missing or excessive event decisions in source session"
        ):
            entry.update(role="excluded", disposition="observed_empty_window")
        else:
            raise ValueError("Undisposed weekday refusal prevents a complete training manifest")
        ledger.append(entry)
    counts = Counter(e["role"] for e in ledger if e["artifacts"])
    if any(not counts[role] for role in ROLES):
        raise ValueError("All chronological development roles require complete source sessions")
    result = {
        "artifact_type": "6e_session_training_manifest_v1",
        "status": "verified_for_named_baseline_only",
        "protocol": protocol(),
        "sources": source_pins(),
        "implementation_sha256": implementation,
        "created_utc": datetime.now(UTC).isoformat(),
        "ledger": ledger,
        "coverage": {
            "inventory_dates": len(ledger),
            "decision_sessions": sum(counts.values()),
            "sessions_by_role": dict(counts),
            "dispositions": dict(Counter(e["disposition"] for e in ledger)),
            "rows": sum(e["artifacts"]["rows"]["count"] for e in ledger if e["artifacts"]),
            "cases": sum(e["case_accounting"]["cases"] for e in ledger if e["artifacts"]),
        },
    }
    if implementation != fingerprints():
        raise ValueError("Manifest implementation changed during verification")
    for item in source_pins().values():
        review.pinned(root / item["path"], item["sha256"])
    return result


def load(root: Path, path: Path, pin: str) -> dict:
    value = review.pinned(path, pin)
    if (
        value["artifact_type"] != "6e_session_training_manifest_v1"
        or value["status"] != "verified_for_named_baseline_only"
        or value["protocol"] != protocol()
        or value["implementation_sha256"] != fingerprints()
        or value["sources"] != source_pins()
    ):
        raise ValueError("Training manifest permission, protocol or implementation differs")
    for item in source_pins().values():
        review.pinned(root / item["path"], item["sha256"])
    if any(
        (root / directory / "failure.json").exists()
        for directory in (DIAGNOSTIC_DIR, RESOURCE_DIR, diagnostic.CENSUS_DIRECTORY)
    ):
        raise ValueError("Manifest source acquired failure evidence")
    frozen = census.registration(root, root / diagnostic.REGISTRATION, diagnostic.REGISTRATION_PIN)
    ledger = value["ledger"]
    if [e["utc_date"] for e in ledger] != [e["utc_date"] for e in frozen["inventory"]["ledger"]]:
        raise ValueError("Manifest must retain every unique original inventory date")
    receipt = review.pinned(
        root / diagnostic.CENSUS_DIRECTORY / "completion.json", diagnostic.RECEIPT_PIN
    )
    original = {r["utc_date"]: r for r in receipt["dates"]}
    members = {m["utc_date"]: m for m in frozen["inventory"]["ledger"]}
    correction = review.pinned(root / RESOURCE_DIR / "completion.json", RESOURCE_PIN)
    correction_pins = {r["utc_date"]: r["report_sha256"] for r in correction["reports"]}
    diagnoses = review.pinned(root / DIAGNOSTIC_DIR / "completion.json", DIAGNOSTIC_PIN)
    diagnosis_pins = {r["utc_date"]: r["report_sha256"] for r in diagnoses["reports"]}
    for entry in ledger:
        day, role = entry["utc_date"], entry["role"]
        partition = census.v1.partition(day)
        if partition != entry["partition"] or entry["original_status"] != original[day]["status"]:
            raise ValueError("Manifest partition differs from source calendar")
        if entry["artifacts"]:
            if (
                partition != "development"
                or role != role_for_day(day)
                or entry["disposition"] != "decision_session"
                or members[day]["planned_action"] != "decision_window_replay"
            ):
                raise ValueError("Manifest has cross-role or reserved training access")
            corrected = day == resource.RESOURCE_DAY
            if original[day]["status"] != ("quality_refused" if corrected else "replayed"):
                raise ValueError("Manifest cannot admit an originally refused weekday")
            directory = (
                root / RESOURCE_DIR if corrected else root / diagnostic.CENSUS_DIRECTORY / "days"
            )
            report_pin = correction_pins[day] if corrected else original[day]["report_sha256"]
            report = review.pinned(directory / f"{day}.json", report_pin)
            expected = decision_entry(root, directory, report, report_pin)
            if any(entry[k] != v for k, v in expected.items()):
                raise ValueError("Manifest artifact lineage differs from original pinned reports")
            if entry["source_sha256"] != members[day]["sha256"]:
                raise ValueError("Manifest source identity differs")
            a = entry["case_accounting"]
            if (
                a["cases"] != entry["artifacts"]["cases"]["count"]
                or a["resolved"] + a["unknown"] != a["cases"]
                or sum(a["statuses"].values()) != a["cases"]
                or a["statuses"].get("resolved", 0) != a["resolved"]
            ):
                raise ValueError("Manifest case/unknown accounting differs")
        elif role in ROLES or (
            partition != "development"
            and (role != partition or entry["disposition"] != "reserved_metadata_only")
        ):
            raise ValueError("Excluded/reserved session cannot claim a training role")
        elif partition == "development":
            member = members[day]
            if (
                role != "excluded"
                or (
                    member["planned_action"] == "reconstruction_only"
                    and entry["disposition"] != "reconstruction_only"
                )
                or (
                    member["planned_action"] == "vendor_degraded_no_replay"
                    and entry["disposition"] != "vendor_degraded"
                )
                or (
                    member["planned_action"] == "decision_window_replay"
                    and (
                        original[day]["status"] != "quality_refused"
                        or day == resource.RESOURCE_DAY
                        or entry["disposition"] != "observed_empty_window"
                    )
                )
            ):
                raise ValueError("Manifest cannot silently drop a decision source session")
            if entry["disposition"] == "observed_empty_window":
                diagnosis = review.pinned(
                    root / DIAGNOSTIC_DIR / f"{day}.json", diagnosis_pins[day]
                )
                if (
                    diagnosis["decision_window_empty_of_target_records"] is not True
                    or diagnosis["original_error"]
                    != "Missing or excessive event decisions in source session"
                ):
                    raise ValueError("Excluded weekday is not an observed empty window")
    if any(not any(e["role"] == role for e in ledger) for role in ROLES):
        raise ValueError("Manifest is missing a chronological role")
    included = [e for e in ledger if e["artifacts"]]
    expected_coverage = {
        "inventory_dates": len(ledger),
        "decision_sessions": len(included),
        "sessions_by_role": dict(Counter(e["role"] for e in included)),
        "dispositions": dict(Counter(e["disposition"] for e in ledger)),
        "rows": sum(e["artifacts"]["rows"]["count"] for e in included),
        "cases": sum(e["case_accounting"]["cases"] for e in included),
    }
    if value["coverage"] != expected_coverage:
        raise ValueError("Manifest coverage totals differ from its complete ledger")
    return value


def run(root: Path, output: Path) -> dict:
    attempt, failure = output.with_suffix(".attempt.json"), output.with_suffix(".failure.json")
    if any(p.exists() for p in (output, attempt, failure)) or not output.resolve().is_relative_to(
        (root / "data/processed").resolve()
    ):
        raise ValueError("Manifest output must be new and inside processed data")
    common._write_new(
        attempt, {"started_utc": datetime.now(UTC).isoformat(), "automatic_retry": False}
    )
    try:
        result = build(root)
        if len(common.canonical(result)) + 1 > MAX_MANIFEST_BYTES:
            raise ValueError("Manifest exceeds byte bound")
        common._write_new(output, result)
        return result
    except Exception as exc:
        common._write_new(failure, {"error": str(exc), "automatic_retry": False})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.project_root, args.output)
    print(common.canonical(result["coverage"]).decode())


if __name__ == "__main__":
    main()
