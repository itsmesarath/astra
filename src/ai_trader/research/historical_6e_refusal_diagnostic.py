"""Bounded metadata-only scans of every refused development census member.

No book reconstruction, features, labels, source repair, training or trading.
Original failures remain immutable. A completed scan is not source acceptance.
"""

from __future__ import annotations

import argparse
import time
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import databento_dbn as dbn

from ai_trader.research import historical_6e_archive as census
from ai_trader.research import historical_6e_census_review as review

common, source = census.common, census.source
REGISTRATION = "logs/6e_archive_development_20261001_1_registration.json"
REGISTRATION_PIN = "ef4d929d1521a55e8f2273e13935d69e31570272be1a3c5fc1517b52b62fdc59"
CENSUS_DIRECTORY = "data/processed/6e_archive_development_20261001_1"
RECEIPT_PIN = "26f0767f99142aea07d82584889b0f5a1108dbd0b147f4db1733b5d298c38873"
MAX_DATES = 32
MAX_DAY_SECONDS = 600
MAX_SECONDS = 1800
MAX_REPORT_BYTES = 2 * 1024**2


def fingerprints() -> dict:
    return {
        **census.fingerprints(),
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
        Path(review.__file__).name: common.hash_file(Path(review.__file__), 1024**2),
    }


def scope(root: Path) -> dict:
    """Verify only bounded census metadata; never read successful/reserved labels."""
    frozen = census.registration(root, root / REGISTRATION, REGISTRATION_PIN)
    directory = root / CENSUS_DIRECTORY
    if directory.is_symlink() or (directory / "failure.json").exists():
        raise ValueError("Missing or incomplete source census")
    receipt = review.pinned(directory / "completion.json", RECEIPT_PIN)
    if (
        receipt["status"] != review.STATUS
        or receipt["registration_sha256"] != REGISTRATION_PIN
        or any(
            receipt[key] is not False
            for key in (
                "training_enabled",
                "promotion_enabled",
                "reserved_outcomes_opened",
                "strategy_aggregate_permitted",
            )
        )
    ):
        raise ValueError("Source census is not completed research-only evidence")
    progress = directory / "progress.jsonl"
    review.checked_hash(progress, receipt["progress_sha256"], MAX_REPORT_BYTES)
    journal = [common.loads(raw) for raw in progress.read_bytes().splitlines()]
    ledger = frozen["inventory"]["ledger"]
    days = [m["utc_date"] for m in ledger]
    if (
        not days
        or days != sorted(set(days))
        or days != [r["utc_date"] for r in journal]
        or journal != receipt["dates"]
        or dict(Counter(r["status"] for r in journal)) != receipt["counts"]
    ):
        raise ValueError("Source census date accounting differs")
    selected = []
    for member, item in zip(ledger, journal, strict=True):
        day = member["utc_date"]
        role = census.v1.partition(day)
        if role != member["partition"]:
            raise ValueError("Source date partition differs")
        if role != "development":
            if item != {"utc_date": day, "status": "reserved_metadata_only", "raw_opened": False}:
                raise ValueError("Reserved source has unexpected access")
            continue  # No reserved artifact paths or archive opens.
        if item["status"] != "quality_refused":
            continue
        if (
            member["condition"] != "available"
            or member["contract"] != census.dated_contract(day)
            or member["planned_action"] not in {"decision_window_replay", "reconstruction_only"}
            or item["source_sha256"] != member["sha256"]
            or item["raw_access_attempted"] is not True
            or item["automatic_retry"] is not False
        ):
            raise ValueError("Refused source identity differs")
        failure_path = directory / "days" / f"{day}.failure.json"
        failure_pin = common.hash_file(failure_path, MAX_REPORT_BYTES)
        if review.pinned(failure_path, failure_pin) != item:
            raise ValueError("Retained failure differs from pinned journal")
        attempt_path = directory / "attempts" / f"{day}.json"
        attempt = review.pinned(attempt_path, common.hash_file(attempt_path, MAX_REPORT_BYTES))
        if any(
            attempt[k] != v
            for k, v in {
                "utc_date": day,
                "contract": member["contract"],
                "registration_sha256": REGISTRATION_PIN,
                "source_sha256": member["sha256"],
                "exposure": "conservatively_exposed_before_raw_access",
            }.items()
        ):
            raise ValueError("Source attempt identity differs")
        selected.append(
            {
                "member": member,
                "original_error": item["error"],
                "original_failure_sha256": failure_pin,
            }
        )
    if not 1 <= len(selected) <= MAX_DATES:
        raise ValueError("Invalid bounded refused-date scope")
    return {
        "source_registration_sha256": REGISTRATION_PIN,
        "source_receipt_sha256": RECEIPT_PIN,
        "source_progress_sha256": receipt["progress_sha256"],
        "all_inventory_dates": len(ledger),
        "refused_dates": selected,
    }


def protocol() -> dict:
    return {
        "version": "6e_refusal_metadata_diagnostic_v1",
        "scope": "Every refused development member only; whole UTC member decoded to EOF",
        "observations": "Target record counts, original flags/actions/timestamps, F_LAST counts; "
        "no price, size, order IDs, reconstructed book, quote claims or labels",
        "flags": "Mirror receive-clock V2 bad-flag and closed-clear predicates for diagnosis "
        "only; do not apply, filter or accept any record",
        "bounds": {
            "dates": MAX_DATES,
            "seconds_per_day": MAX_DAY_SECONDS,
            "seconds_total": MAX_SECONDS,
            "report_bytes": MAX_REPORT_BYTES,
            "samples_per_day": 8,
        },
        "training_enabled": False,
        "trading_enabled": False,
        "promotion_enabled": False,
    }


def prepare(root: Path, path: Path) -> dict:
    result = {
        "protocol": protocol(),
        "scope": scope(root),
        "implementation_sha256": fingerprints(),
        "prepared_utc": datetime.now(UTC).isoformat(),
    }
    common._write_new(path, result)
    return result


def registration(root: Path, path: Path, pin: str) -> dict:
    frozen = review.pinned(path, pin)
    if (
        frozen["protocol"] != protocol()
        or frozen["scope"] != scope(root)
        or frozen["implementation_sha256"] != fingerprints()
    ):
        raise ValueError("Diagnostic registration, source or implementation changed")
    return frozen


def flag_predicates(record, window: tuple[int, int]) -> tuple[int, bool]:
    """Only classify; this does not weaken the frozen replay's quality gate."""
    recv = record.ts_recv
    accepted_closed_clear = (
        record.flags == dbn.F_BAD_TS_RECV
        and str(record.action) == "R"
        and str(record.side) == "N"
        and recv != dbn.UNDEF_TIMESTAMP
        and source.cme_session(recv) is None
        and not window[0] <= recv < window[1]
        and record.ts_event <= recv
    )
    bad = record.flags & (dbn.F_BAD_TS_RECV | dbn.F_MAYBE_BAD_BOOK | dbn.F_TOB | dbn.F_MBP)
    if record.flags & dbn.F_SNAPSHOT:
        bad &= ~dbn.F_BAD_TS_RECV
    return int(bad), accepted_closed_clear


def summarize(records, day, contract: str, *, started: float | None = None) -> dict:
    if census.dated_contract(day.isoformat()) != contract:
        raise ValueError("Diagnostic contract differs from development calendar")
    started = time.monotonic() if started is None else started
    begin = source._utc_ns(day)
    window = (begin + 12 * 3600 * 10**9, begin + 16 * 3600 * 10**9)
    instrument, last_recv = None, None
    counts, flags, actions, hours = Counter(), Counter(), Counter(), Counter()
    refused_flags, samples = Counter(), []
    first_recv = last_valid_recv = None
    for index, record in enumerate(records):
        if index % 65536 == 0 and time.monotonic() - started > MAX_DAY_SECONDS:
            raise TimeoutError("Metadata scan per-day time bound exceeded")
        if isinstance(record, dbn.Metadata):
            if instrument is not None:
                raise ValueError("Multiple metadata headers")
            instrument = source._mapped_instrument(record, contract, day)
            continue
        if instrument is None or not isinstance(record, dbn.MBOMsg):
            raise ValueError("Missing metadata or unexpected record")
        if record.instrument_id != instrument:
            continue
        counts["target_records"] += 1
        recv, snapshot = record.ts_recv, bool(record.flags & dbn.F_SNAPSHOT)
        flags[str(record.flags)] += 1
        actions[str(record.action)] += 1
        counts["snapshot_records"] += snapshot
        counts["undefined_receive_timestamp"] += recv == dbn.UNDEF_TIMESTAMP
        valid_recv = begin <= recv < begin + source.DAY_NS
        counts["receive_outside_member_day"] += not valid_recv
        inside = valid_recv and window[0] <= recv < window[1]
        counts["records_in_decision_window"] += inside
        counts["snapshot_records_in_decision_window"] += inside and snapshot
        counts["non_snapshot_f_last_in_decision_window"] += (
            inside and not snapshot and bool(record.flags & dbn.F_LAST)
        )
        if valid_recv:
            hours[str((recv - begin) // (3600 * 10**9))] += 1
            first_recv = recv if first_recv is None else min(first_recv, recv)
            last_valid_recv = recv if last_valid_recv is None else max(last_valid_recv, recv)
        bad, accepted = flag_predicates(record, window)
        counts["legacy_closed_clear_exception"] += accepted
        if not snapshot and not accepted and valid_recv:
            counts["receive_regressions"] += last_recv is not None and recv < last_recv
            last_recv = recv
        if bad and not accepted:
            counts["flag_gate_refusal_records"] += 1
            counts["flag_gate_refusals_in_decision_window"] += inside
            refused_flags[str(record.flags)] += 1
            if len(samples) < 8:
                samples.append(
                    {
                        "ts_recv_ns": recv,
                        "ts_event_ns": record.ts_event,
                        "ts_in_delta_ns": record.ts_in_delta,
                        "sequence": record.sequence,
                        "flags": record.flags,
                        "effective_bad_bits": bad,
                        "action": str(record.action),
                        "side": str(record.side),
                        "snapshot": snapshot,
                        "inside_decision_window": inside,
                        "legacy_weekly_session": source.cme_session(recv) if valid_recv else None,
                    }
                )
    if instrument is None or not counts["target_records"]:
        raise ValueError("Missing target contract records")
    if time.monotonic() - started > MAX_DAY_SECONDS:
        raise TimeoutError("Metadata scan per-day time bound exceeded")
    return {
        "instrument_id": instrument,
        "counts": dict(counts),
        "flags": dict(flags),
        "actions": dict(actions),
        "records_by_utc_hour": dict(hours),
        "refused_flags": dict(refused_flags),
        "first_eight_flag_gate_refusals": samples,
        "first_valid_receive_ns": first_recv,
        "last_valid_receive_ns": last_valid_recv,
        "decision_window_empty_of_target_records": counts["records_in_decision_window"] == 0,
        "f_last_is_not_a_reconstructed_quote_count": True,
        "holiday_calendar_verified": False,
        "source_accepted": False,
    }


def scan(member: dict) -> dict:
    day = census.v1.iso_day(member["utc_date"])
    contract = census.dated_contract(day.isoformat())  # Before constructing raw path.
    if member["condition"] != "available" or member["contract"] != contract:
        raise ValueError("Undeclared or degraded diagnostic member")
    path = Path(member["archive"])
    stamp = (path.stat().st_size, path.stat().st_mtime_ns)
    if path.is_symlink() or stamp[0] != member["archive_bytes"]:
        raise ValueError("Diagnostic source archive changed or linked")
    started = time.monotonic()
    with zipfile.ZipFile(path) as archive:
        result = summarize(source._member_records(archive, member), day, contract, started=started)
    if (path.stat().st_size, path.stat().st_mtime_ns) != stamp:
        raise ValueError("Diagnostic source archive changed during scan")
    return {
        **result,
        "utc_date": day.isoformat(),
        "contract": contract,
        "member_sha256_verified_at_eof": member["sha256"],
    }


def run(root: Path, path: Path, pin: str, output: Path) -> dict:
    if output.exists() or not output.resolve().is_relative_to((root / "data/processed").resolve()):
        raise ValueError("Diagnostic directory must be new and inside processed data")
    frozen = registration(root, path, pin)
    output.mkdir(parents=False, exist_ok=False)
    common._write_new(
        output / "attempt.json",
        {
            "registration_sha256": pin,
            "started_utc": datetime.now(UTC).isoformat(),
            "automatic_retry": False,
            "status": "claimed_not_complete",
        },
    )
    started, reports = time.monotonic(), []
    try:
        for selected in frozen["scope"]["refused_dates"]:
            if time.monotonic() - started > MAX_SECONDS:
                raise TimeoutError("Diagnostic total time bound exceeded")
            registration(root, path, pin)
            member = selected["member"]
            day = member["utc_date"]
            common._write_new(
                output / f"{day}.attempt.json",
                {
                    "utc_date": day,
                    "source_sha256": member["sha256"],
                    "registration_sha256": pin,
                    "raw_access_attempted": True,
                    "new_labels_or_features": False,
                },
            )
            print(f"Scanning refused development metadata {day}", flush=True)
            report = {
                **scan(member),
                "original_error": selected["original_error"],
                "original_failure_sha256": selected["original_failure_sha256"],
            }
            if len(common.canonical(report)) + 1 > MAX_REPORT_BYTES:
                raise ValueError("Diagnostic report exceeds byte bound")
            registration(root, path, pin)
            common._write_new(output / f"{day}.json", report)
            reports.append(
                {
                    "utc_date": day,
                    "report_sha256": common.hash_file(output / f"{day}.json", MAX_REPORT_BYTES),
                }
            )
        if time.monotonic() - started > MAX_SECONDS:
            raise TimeoutError("Diagnostic total time bound exceeded")
        registration(root, path, pin)
        result = {
            "status": "all_refused_members_scanned_not_source_accepted",
            "registration_sha256": pin,
            "source_scope": frozen["scope"],
            "implementation_sha256": frozen["implementation_sha256"],
            "reports": reports,
            "finished_utc": datetime.now(UTC).isoformat(),
            "source_modified": False,
            "quality_gate_changed": False,
            "new_labels_or_features": False,
            "reserved_raw_opened": False,
            "training_enabled": False,
            "trading_enabled": False,
            "promotion_enabled": False,
        }
        common._write_new(output / "completion.json", result)
        return result
    except Exception as exc:
        common._write_new(
            output / "failure.json",
            {
                "status": "metadata_diagnostic_incomplete",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "completed_dates": len(reports),
                "automatic_retry": False,
                "registration_sha256": pin,
            },
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--registration-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.prepare:
        result = prepare(args.project_root, args.registration)
        print(common.canonical({"refused_dates": len(result["scope"]["refused_dates"])}).decode())
    else:
        if args.registration_sha256 is None or args.output is None:
            parser.error("Registration pin and new output directory required")
        result = run(args.project_root, args.registration, args.registration_sha256, args.output)
        print(
            common.canonical(
                {"status": result["status"], "reports": len(result["reports"])}
            ).decode()
        )


if __name__ == "__main__":
    main()
