"""One-file timestamp-only investigation of the failed October development replay.

No book reconstruction, features, labels, model, source repair or strategy retry.
"""

from __future__ import annotations

import argparse
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import databento_dbn as dbn

from ai_trader.research import historical_6e_cohort as cohort

REGISTRATION = "logs/6e_multimonth_development_20261001_1_registration.json"
REGISTRATION_PIN = "4e3e264edf09b5a4717e8034108c21dad5f4c8ed6070bb56e8740cee855bb25f"
FAILURE_PIN = "12f2b6357b83480ed3438173c89585453fe45d036ff5d261abf420e30011f977"
DAY = "2025-10-08"
CONTRACT = "6EZ5"


def summarize(records, day, contract) -> dict:
    instrument = None
    last_recv = None
    counts, actions, flags, minutes = Counter(), Counter(), Counter(), Counter()
    samples = []
    min_inversion = max_inversion = None
    start = cohort.source._utc_ns(day)
    for record in records:
        if isinstance(record, dbn.Metadata):
            if instrument is not None:
                raise ValueError("Multiple metadata records")
            instrument = cohort.source._mapped_instrument(record, contract, day)
            continue
        if instrument is None or not isinstance(record, dbn.MBOMsg):
            raise ValueError("Missing metadata or unexpected record")
        if record.instrument_id != instrument:
            continue
        counts["target_records"] += 1
        if record.flags & dbn.F_SNAPSHOT:
            counts["snapshot_records_excluded_from_clock_comparison"] += 1
            continue
        counts["non_snapshot_records"] += 1
        recv, event = record.ts_recv, record.ts_event
        if dbn.UNDEF_TIMESTAMP in (recv, event):
            counts["undefined_timestamps"] += 1
            continue
        counts["receive_outside_member_day"] += int(
            not start <= recv < start + cohort.source.DAY_NS
        )
        counts["receive_regressions"] += int(last_recv is not None and recv < last_recv)
        last_recv = recv
        counts["bad_receive_flag"] += bool(record.flags & dbn.F_BAD_TS_RECV)
        counts["maybe_bad_book_flag"] += bool(record.flags & dbn.F_MAYBE_BAD_BOOK)
        counts["negative_send_to_receive_delta"] += int(record.ts_in_delta < 0)
        counts["event_later_than_sending_timestamp"] += int(event > recv - record.ts_in_delta)
        inversion = event - recv
        if inversion <= 0:
            continue
        counts["exchange_after_receive_records"] += 1
        in_window = start + 12 * 3600 * 10**9 <= recv < start + 16 * 3600 * 10**9
        counts["exchange_after_receive_inside_decision_window"] += int(in_window)
        counts["exchange_after_receive_outside_decision_window"] += int(not in_window)
        actions[str(record.action)] += 1
        flags[str(record.flags)] += 1
        minute = datetime.fromtimestamp(recv // 10**9, UTC).strftime("%H:%M")
        minutes[minute] += 1
        min_inversion = inversion if min_inversion is None else min(min_inversion, inversion)
        max_inversion = inversion if max_inversion is None else max(max_inversion, inversion)
        if len(samples) < 8:
            samples.append(
                {
                    "ts_recv_ns": recv,
                    "ts_event_ns": event,
                    "event_minus_receive_ns": inversion,
                    "ts_in_delta_ns": record.ts_in_delta,
                    "sequence": record.sequence,
                    "flags": record.flags,
                    "action": str(record.action),
                    "inside_decision_window": in_window,
                }
            )
    if instrument is None or not counts["target_records"]:
        raise ValueError("Missing target contract records")
    return {
        "instrument_id": instrument,
        "counts": dict(counts),
        "inverted_record_actions": dict(actions),
        "inverted_record_flags": dict(flags),
        "inverted_records_by_utc_minute": dict(minutes),
        "min_event_minus_receive_ns": min_inversion,
        "max_event_minus_receive_ns": max_inversion,
        "first_eight_inverted_records": samples,
    }


def run(root: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Refusing to overwrite timestamp diagnostic")
    registration = root / REGISTRATION
    frozen = cohort.registration(root, registration, REGISTRATION_PIN)
    failure = cohort.read_pinned(registration.with_suffix(".failure.json"), FAILURE_PIN)
    if (
        failure["registration_sha256"] != REGISTRATION_PIN
        or failure["block"] != "october_2025"
        or failure["error"] != "Target exchange timestamp is later than receive timestamp"
    ):
        raise ValueError("Unexpected failure scope")
    block = next(b for b in cohort.BLOCKS if b.name == failure["block"])
    _, members, _ = cohort.source.selected_sources(
        {
            "source_intake_report": cohort.INTAKE,
            "source_intake_sha256": cohort.INTAKE_SHA256,
            "source_sessions": list(block.sessions),
        },
        root,
    )
    member = next(m for m in members if m["day"].isoformat() == DAY)
    path = member["archive"]
    stamp = (path.stat().st_size, path.stat().st_mtime_ns)
    with zipfile.ZipFile(path) as archive:
        result = summarize(cohort.source._member_records(archive, member), member["day"], CONTRACT)
    if (path.stat().st_size, path.stat().st_mtime_ns) != stamp:
        raise ValueError("Source archive changed during timestamp diagnostic")
    result.update(
        {
            "artifact_type": "6e_timestamp_diagnostic_v1",
            "scope": "one_file_timestamps_only",
            "source_utc_date": DAY,
            "contract": CONTRACT,
            "member_sha256_verified": member["sha256"],
            "registration_sha256": REGISTRATION_PIN,
            "failure_sha256": FAILURE_PIN,
            "diagnostic_source_sha256": cohort.common.hash_file(Path(__file__), 1024**2),
            "implementation_sha256": frozen["implementation_sha256"],
            "strategy_replayed": False,
            "quality_gate_changed": False,
            "source_modified": False,
            "new_features_or_labels": False,
            "training_enabled": False,
            "trading_enabled": False,
        }
    )
    cohort.registration(root, registration, REGISTRATION_PIN)
    cohort.common._write_new(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.project_root, args.output)
    print(cohort.common.canonical(result).decode())


if __name__ == "__main__":
    main()
