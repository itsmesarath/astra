"""Bounded multi-contract development replay with a metadata-only exposure ledger.

This version cannot replay reserved calendar periods. It does not implement a
continuous futures roll, a broker backtest, a model fit or a trading connection.
"""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np

from ai_trader.research import databento_6e_training_data as source
from ai_trader.research import historical_6e_execution_study as study

common, flow = study.common, study.flow
INTAKE = "data/processed/databento_6e_18_month_intake_20261001_2.json"
INTAKE_SHA256 = "de12f9833b951781f27b5ea46d2c6dc2302c422e1080bfc48914b2dc8a82b27a"
EXPOSURE_EVIDENCE = {
    "data/processed/databento_6e_6em5_initial_20261001_manifest.json": (
        "d68eaea3c84a081191c96239d0a803ea894471193c717b2cc2967dca5256dfc0"
    ),
    "data/processed/databento_6e_microdepth_tree_v1_report.json": (
        "72ded08fa3a1eb1b2b316343cd9b99d97c6dbd3d905a3982e89adaf013cecf90"
    ),
}
JULY_ROWS = "data/processed/6e_execution_linked_20261001_1_rows.jsonl"
JULY_SHA256 = "206807287182ee7f9c3f9944a5e166795a41d8afdd4688c0ade26c4e7f7bc97d"
MAX_ROWS = 130_000  # Nine four-hour windows, at most one decision per second.
MAX_OUTPUT_BYTES = 300 * 1024**2
PARTITIONS = (
    ("development", "2025-03-26", "2026-01-01"),
    ("validation_reserved", "2026-01-01", "2026-04-01"),
    ("test_reserved", "2026-04-01", "2026-07-01"),
    ("lockbox_reserved", "2026-07-01", "2026-09-26"),
)


def iso_day(value: str) -> date:
    day = date.fromisoformat(value)
    if day.isoformat() != value:
        raise ValueError("Expected canonical ISO date")
    return day


def partition(day: str) -> str:
    iso_day(day)
    matches = [name for name, start, end in PARTITIONS if start <= day < end]
    if len(matches) != 1:
        raise ValueError("Date outside unique calendar partition")
    return matches[0]


@dataclass(frozen=True)
class Block:
    name: str
    contract: str
    sessions: tuple[str, ...]

    def validate(self) -> None:
        if not self.name or not source.CONTRACT.fullmatch(self.contract):
            raise ValueError("Explicit dated outright contract required")
        for day in self.sessions:
            iso_day(day)
        source._session_list({"source_sessions": list(self.sessions)})
        if len(self.sessions) != 3:
            raise ValueError("This protocol requires exactly three sessions per block")
        # Check reconstruction members too: a warmup may not reach across a split.
        if any(partition(day) != "development" for day in self.source_days):
            raise ValueError("Reserved periods cannot be replayed by this development protocol")

    @property
    def source_days(self) -> tuple[str, ...]:
        return tuple(d.isoformat() for d in source._needed_dates(list(self.sessions)))


BLOCKS = (
    Block("april_2025", "6EM5", ("2025-04-07", "2025-04-08", "2025-04-09")),
    Block("july_2025", "6EU5", ("2025-07-07", "2025-07-08", "2025-07-09")),
    Block("october_2025", "6EZ5", ("2025-10-06", "2025-10-07", "2025-10-08")),
)


def validate_blocks(blocks: tuple[Block, ...]) -> None:
    if len(blocks) != 3 or len({b.name for b in blocks}) != len(blocks):
        raise ValueError("Three uniquely named blocks required")
    previous = None
    seen = set()
    for block in blocks:
        block.validate()
        if previous is not None and block.sessions[0] <= previous:
            raise ValueError("Blocks must be chronological")
        if seen.intersection(block.source_days):
            raise ValueError("Source members cannot overlap blocks, including reconstruction")
        seen.update(block.source_days)
        previous = block.sessions[-1]


def read_pinned(path: Path, pin: str, limit: int = 1024**2) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("Missing, linked or oversized metadata")
    raw = path.read_bytes()
    if len(raw) > limit or hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError("Pinned metadata changed")
    result = common.loads(raw)
    if type(result) is not dict:
        raise ValueError("Expected metadata object")
    return result


def exposure_ledger(intake: dict, evidence: list[dict]) -> list[dict]:
    """Existing reports document positive exposure, not proof of non-exposure."""
    outcomes, replayed = set(), {}
    for item in evidence:
        if "sessions" in item:
            outcomes.update(item["sessions"])
            members = item["source"]["members"]
        else:
            outcomes.update(s for group in item["session_split"].values() for s in group)
            members = item["source_days"]
        for member in members:
            day = member["utc_date"]
            pin = member.get("member_sha256", member.get("member_sha256_verified_during_replay"))
            if day in replayed and replayed[day] != pin:
                raise ValueError("Conflicting prior replay source pins")
            replayed[day] = pin
    ledger, seen = [], set()
    for batch in intake["batches"]:
        for member in batch["files"]:
            if "date" not in member:
                continue
            day = member["date"]
            if day in seen:
                raise ValueError("Duplicate inventory date")
            seen.add(day)
            role = partition(day)
            if day in replayed and replayed[day] != member["sha256"]:
                raise ValueError("Prior exposure evidence differs from intake")
            if day in replayed and role != "development":
                raise ValueError("Documented prior replay overlaps a reserved period")
            ledger.append(
                {
                    "utc_date": day,
                    "partition": role,
                    "condition": member["condition"],
                    "prior_access": "outcomes_exposed"
                    if day in outcomes
                    else "raw_replayed"
                    if day in replayed
                    else "no_replay_documented",
                    "member_sha256": member["sha256"],
                }
            )
    if not outcomes <= replayed.keys() or not replayed.keys() <= seen:
        raise ValueError("Prior exposure dates missing from source inventory")
    return sorted(ledger, key=lambda r: r["utc_date"])


def protocol() -> dict:
    validate_blocks(BLOCKS)
    return {
        "artifact_type": "6e_multimonth_development_v1",
        "blocks": [{**asdict(b), "sessions": list(b.sessions)} for b in BLOCKS],
        "partitions": [list(p) for p in PARTITIONS],
        "source_intake_sha256": INTAKE_SHA256,
        "exposure_evidence_sha256": EXPOSURE_EVIDENCE,
        "exposure_limit": "Positive access inventory only; undocumented is not certified unseen",
        "selection": "Three explicit development blocks in April, July and October; no ranking "
        "by realized return or volume. Calendar sample, not representative of every month.",
        "contract_handling": "Explicit outright per independent block; validate daily DBN mapping; "
        "reset book, features and positions. No continuous roll, splice or front-month claim.",
        "calendar": "12-16 UTC windows only, not full exchange sessions; no holiday substitution; "
        "missing, degraded or low-coverage source fails the entire run",
        "features": list(study.data.FEATURES),
        "execution_features": list(flow.FEATURES),
        "signals": list(study.SIGNALS),
        "entry_hold_cost": "Inherited 100ms entry, 1s wait, 15s hold, crossed spread plus one tick",
        "comparison": "Nine unchanged sign rules; no reversal, threshold search or fit. "
        "Per-session, per-block and pooled descriptive summaries; no best-rule selection.",
        "activity_control": "Terciles from eligible April 7 features only; shared by all blocks",
        "price_control": "Sign of prior five-second midpoint change; not causal identification",
        "july_regression_sha256": JULY_SHA256,
        "max_rows": MAX_ROWS,
        "max_output_bytes": MAX_OUTPUT_BYTES,
        "attempt_policy": "Single exclusive attempt claim before raw access; failures retain "
        "conservative exposure for every planned member. No restart or successful-subset output.",
        "training_enabled": False,
        "trading_enabled": False,
        "promotion_enabled": False,
    }


def fingerprints() -> dict:
    return {**study.fingerprints(), Path(__file__).name: common.hash_file(Path(__file__), 1024**2)}


def preflight(root: Path) -> dict:
    """Read small pinned metadata and archive stats only; never open a ZIP member."""
    validate_blocks(BLOCKS)
    intake = read_pinned(root / INTAKE, INTAKE_SHA256)
    evidence = [read_pinned(root / path, pin) for path, pin in EXPOSURE_EVIDENCE.items()]
    ledger = exposure_ledger(intake, evidence)
    selected = []
    for block in BLOCKS:
        _, members, _ = source.selected_sources(
            {
                "source_intake_report": INTAKE,
                "source_intake_sha256": INTAKE_SHA256,
                "source_sessions": list(block.sessions),
            },
            root,
        )
        if tuple(m["day"].isoformat() for m in members) != block.source_days:
            raise ValueError("Unexpected reconstruction source set")
        selected.append(
            {
                "block": block.name,
                "members": [
                    {
                        "utc_date": m["day"].isoformat(),
                        "archive": str(m["archive"]),
                        "archive_sha256_from_intake": m["archive_sha256"],
                        "member": m["name"],
                        "bytes": m["bytes"],
                        "member_sha256": m["sha256"],
                    }
                    for m in members
                ],
            }
        )
    return {
        "ledger": ledger,
        "selected_sources": selected,
        "prior_access_counts": dict(Counter(r["prior_access"] for r in ledger)),
        "partition_member_counts": dict(Counter(r["partition"] for r in ledger)),
        "condition_counts": dict(Counter(r["condition"] for r in ledger)),
        "raw_members_opened": False,
        "contract_mappings_verified": False,
    }


def prepare(root: Path, path: Path) -> dict:
    record = {
        "protocol": protocol(),
        "implementation_sha256": fingerprints(),
        "preflight": preflight(root),
        "prepared_utc": datetime.now(UTC).isoformat(),
    }
    common._write_new(path, record)
    return record


def registration(root: Path, path: Path, pin: str) -> dict:
    record = read_pinned(path, pin)
    if (
        record.get("protocol") != protocol()
        or record.get("implementation_sha256") != fingerprints()
        or record.get("preflight") != preflight(root)
    ):
        raise ValueError("Frozen registration, implementation or source metadata changed")
    return record


class DatedExecutionBuilder(flow.ExecutionBuilder):
    """One fixed dated contract; inherited event/quality/target rules are unchanged."""

    def __init__(self, block: Block, minimum_resolved: int = 100):
        block.validate()
        super().__init__(block.sessions, minimum_resolved)
        self.contract = block.contract


def replay_block(root: Path, block: Block) -> tuple[list[dict], dict]:
    block.validate()  # Must precede any raw source access.
    _, members, _ = source.selected_sources(
        {
            "source_intake_report": INTAKE,
            "source_intake_sha256": INTAKE_SHA256,
            "source_sessions": list(block.sessions),
        },
        root,
    )
    builder = DatedExecutionBuilder(block)
    mappings = []
    for member in members:
        path = member["archive"]
        stamp = (path.stat().st_size, path.stat().st_mtime_ns)
        print(f"Replaying {block.name} {block.contract} {member['day']}", flush=True)
        with zipfile.ZipFile(path) as archive:
            builder.start_day(member["day"])
            for record in source._member_records(archive, member):
                builder.consume(record)
                if len(builder.rows) > 43_200:
                    raise ValueError("Per-block row bound exceeded")
            builder.finish_day()
        if (path.stat().st_size, path.stat().st_mtime_ns) != stamp:
            raise ValueError("Archive changed during replay")
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


def verify_july(root: Path, rows: list[dict]) -> None:
    path = root / JULY_ROWS
    if common.hash_file(path, 100 * 1024**2) != JULY_SHA256:
        raise ValueError("Original July execution rows changed")
    selected = iter(r for r in rows if r["block"] == "july_2025")
    with path.open("rb") as handle:
        while line := handle.readline(common.MAX_LINE + 1):
            if len(line) > common.MAX_LINE:
                raise ValueError("Oversized original July row")
            new = next(selected, None)
            if new is None or {
                k: v for k, v in new.items() if k not in {"contract", "block", "partition"}
            } != common.loads(line):
                raise ValueError("July features or outcomes changed")
    if next(selected, None) is not None:
        raise ValueError("Extra July rows")
    if common.hash_file(path, 100 * 1024**2) != JULY_SHA256:
        raise ValueError("Original July rows changed while reading")


def run(
    root: Path, registration_path: Path, pin: str, rows_output: Path, report_output: Path
) -> dict:
    attempt_path = registration_path.with_suffix(".attempt.json")
    failure_path = registration_path.with_suffix(".failure.json")
    paths = (rows_output, report_output, registration_path, attempt_path, failure_path)
    if len({p.resolve() for p in paths}) != 5 or any(p.exists() for p in paths[:2]):
        raise ValueError("Refusing to overwrite research evidence")
    frozen = registration(root, registration_path, pin)
    # Conservative persistent exposure survives failure, interruption and process loss.
    common._write_new(
        attempt_path,
        {
            "registration_sha256": pin,
            "started_utc": datetime.now(UTC).isoformat(),
            "status": "claimed_not_proof_of_completion",
            "conservatively_exposed_source_days": [d for b in BLOCKS for d in b.source_days],
            "rule": "Never treat these dates as untouched, even if no completed report exists",
        },
    )
    active = None
    try:
        rows, evidence = [], []
        for block in BLOCKS:
            active = block.name
            batch, quality = replay_block(root, block)
            rows.extend(batch)
            evidence.append(quality)
            if len(rows) > MAX_ROWS:
                raise ValueError("Cohort row bound exceeded")
        verify_july(root, rows)
        reference = [
            r["features"]["log_quote_events_5s"]
            for r in rows
            if r["eligible"] and r["source_session"] == BLOCKS[0].sessions[0]
        ]
        cuts = np.unique(np.quantile(reference, [1 / 3, 2 / 3]))
        raw = bytearray()
        for row in rows:
            raw.extend(common.canonical(row) + b"\n")
            if len(raw) > MAX_OUTPUT_BYTES:
                raise ValueError("Cohort output byte bound exceeded")
        result = {
            "artifact_type": "6e_multimonth_development_report_v1",
            "status": "completed",
            "registration_sha256": pin,
            "implementation_sha256": frozen["implementation_sha256"],
            "rows": len(rows),
            "rows_sha256": hashlib.sha256(raw).hexdigest(),
            "july_regression": "all_original_features_execution_features_and_targets_exact",
            "activity_cuts_from_april7": cuts.tolist(),
            "evidence": evidence,
            "summary": study.summarize(rows, cuts),
            "by_block": {
                b.name: study.summarize([r for r in rows if r["block"] == b.name], cuts)
                for b in BLOCKS
            },
            "by_session": {
                s: study.summarize([r for r in rows if r["source_session"] == s], cuts)
                for b in BLOCKS
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
        result = prepare(args.project_root, args.registration)
        print(
            common.canonical(
                {
                    k: result["preflight"][k]
                    for k in ("prior_access_counts", "partition_member_counts")
                }
            ).decode()
        )
    else:
        if None in (args.registration_sha256, args.rows_output, args.report_output):
            parser.error("Registration pin and new rows/report output paths required")
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
