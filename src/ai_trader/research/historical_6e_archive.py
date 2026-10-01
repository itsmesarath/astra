"""Offline development census with per-date evidence, never a deployable backtest.

All archived dates are accounted for. Reserved periods are metadata-only, failed
dates stay visible, and successful shards are not promoted as a complete corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import time
import zipfile
from array import array
from collections import Counter
from datetime import UTC, date, datetime
from importlib.metadata import version
from pathlib import Path

import numpy as np

from ai_trader.research import databento_6e_receive_clock as receive
from ai_trader.research import historical_6e_cohort_v2 as prior

v1, common, study, source = prior.v1, prior.common, prior.study, prior.source
paths, baseline = study.paths, study.diagnostics.baseline
PRIOR_REG = "logs/6e_multimonth_development_v2_20261001_1_registration.json"
PRIOR_PIN = "96bc5d2bf691b8c3534fc697dcc77e9e9984329416f9103aae3b5b9244d19a38"
PRIOR_REPORT = "data/processed/6e_multimonth_development_v2_20261001_1_report.json"
PRIOR_REPORT_PIN = "4493fec0320a96499eb683ba8c0376e43baf5795555c71d7c2d4467b183b0680"
MAX_DAY_BYTES = 48 * 1024**2
MAX_TOTAL_BYTES = 12 * 1024**3
MAX_SECONDS = 12 * 3600
MAX_DAY_SECONDS = 600


def dated_contract(day: str) -> str:
    """Declared research roll, not a claim of contemporaneous maximum liquidity."""
    if v1.partition(day) != "development":
        raise ValueError("Reserved dates cannot enter the development census")
    for end, symbol in (
        ("2025-06-09", "6EM5"),
        ("2025-09-08", "6EU5"),
        ("2025-12-08", "6EZ5"),
        ("2026-01-01", "6EH6"),
    ):
        if day < end:
            return symbol
    raise ValueError("No declared dated contract")


def inventory(root: Path) -> dict:
    frozen = prior.registration(root, root / PRIOR_REG, PRIOR_PIN)
    completed = v1.read_pinned(root / PRIOR_REPORT, PRIOR_REPORT_PIN, 8 * 1024**2)
    if completed["status"] != "completed" or completed["registration_sha256"] != PRIOR_PIN:
        raise ValueError("Previous comparison is not verified complete")
    intake = v1.read_pinned(root / v1.INTAKE, v1.INTAKE_SHA256)
    members = {}
    for batch in intake["batches"]:
        archive = Path(batch["archive"])
        if archive.is_symlink() or archive.stat().st_size != batch["archive_bytes"]:
            raise ValueError("Archive is linked or differs from pinned size")
        for item in batch["files"]:
            if "date" not in item:
                continue
            day = item["date"]
            if day in members:
                raise ValueError("Duplicate archive date")
            members[day] = {
                "utc_date": day,
                "archive": str(archive),
                "archive_bytes": batch["archive_bytes"],
                "name": item["filename"],
                "bytes": item["bytes"],
                "sha256": item["sha256"],
                "condition": item["condition"],
            }
    ledger = []
    replayed = {m["utc_date"] for e in completed["evidence"] for m in e["dated_contract_mappings"]}
    for old in frozen["preflight"]["ledger"]:
        day = old["utc_date"]
        member = members[day]
        if member["sha256"] != old["member_sha256"]:
            raise ValueError("Exposure inventory differs from source pin")
        row = {**old, **member}
        if day in completed["by_session"]:
            row["prior_access"] = "outcomes_exposed"
        elif day in replayed and row["prior_access"] != "outcomes_exposed":
            row["prior_access"] = "raw_replayed"
        dev = row["partition"] == "development"
        row["contract"] = dated_contract(day) if dev else None
        row["planned_action"] = (
            "reserved_metadata_only"
            if not dev
            else "vendor_degraded_no_replay"
            if row["condition"] != "available"
            else "reconstruction_only"
            if date.fromisoformat(day).weekday() >= 5
            else "decision_window_replay"
        )
        ledger.append(row)
    if len(ledger) != len(members):
        raise ValueError("Inventory and exposure ledger differ")
    return {
        "ledger": ledger,
        "prior_access_counts": dict(Counter(r["prior_access"] for r in ledger)),
        "partition_counts": dict(Counter(r["partition"] for r in ledger)),
        "planned_actions": dict(Counter(r["planned_action"] for r in ledger)),
        "raw_opened": False,
    }


def protocol() -> dict:
    return {
        "version": "6e_development_archive_census_v1",
        "runtime": {
            "python": sys.version,
            "numpy": version("numpy"),
            "databento_dbn": version("databento-dbn"),
            "zstandard": version("zstandard"),
        },
        "intake_sha256": v1.INTAKE_SHA256,
        "prior_report_sha256": PRIOR_REPORT_PIN,
        "scope": "Every 2025 inventory member; 2026 reserved dates metadata only",
        "window": "12-16 UTC decisions, ten-second warmup; decode complete UTC members",
        "calendar_roll": "6EM5 until June9, 6EU5 until Sep8, 6EZ5 until Dec8, then 6EH6; "
        "UTC-date boundaries; research assumption, no front-month or holiday-calendar claim",
        "isolation": "Fresh daily book/features/positions; daily snapshot; no price splice",
        "quality": receive.policy(),
        "features": [*study.data.FEATURES, *study.flow.FEATURES],
        "outcomes": "All original one-second event decisions, 100ms entry, 1s wait, "
        "15s quote target, crossed spread plus one tick; unavailable labels stay null",
        "paths": "First eligible decision at least 60s after prior chosen decision, "
        "chosen before outcome availability; 1/5/15/30/60s quotes, gross +/-2/4 tick "
        "first crossings, extrema and gaps; no fills or optimal-exit profit claim",
        "association": "Each causal feature versus any positive 15s direction on thinned "
        "resolved observations, fixed orientation, winners and nonwinners; not causal reasons",
        "failure_policy": "Per-day audit census, not a whole-cohort strategy experiment. "
        "Keep all refusals and attempted dates; continue independent dates, no replacements "
        "or retries. No aggregate strategy/model promotion from successful subsets.",
        "bounds": {
            "per_day_bytes": MAX_DAY_BYTES,
            "total_bytes": MAX_TOTAL_BYTES,
            "seconds": MAX_SECONDS,
            "per_day_seconds": MAX_DAY_SECONDS,
            "quotes_per_day": paths.MAX_QUOTES,
        },
        "training_enabled": False,
        "trading_enabled": False,
        "promotion_enabled": False,
    }


def fingerprints() -> dict:
    return {**prior.fingerprints(), Path(__file__).name: common.hash_file(Path(__file__), 1024**2)}


def prepare(root: Path, path: Path) -> dict:
    result = {
        "protocol": protocol(),
        "implementation_sha256": fingerprints(),
        "inventory": inventory(root),
        "prepared_utc": datetime.now(UTC).isoformat(),
    }
    common._write_new(path, result)
    return result


def registration(root: Path, path: Path, pin: str) -> dict:
    result = v1.read_pinned(path, pin, 2 * 1024**2)
    if (
        result["protocol"] != protocol()
        or result["implementation_sha256"] != fingerprints()
        or result["inventory"] != inventory(root)
    ):
        raise ValueError("Census registration or evidence changed")
    return result


def case_associations(rows: list[dict]) -> dict:
    chosen = study.diagnostics.thin_causally(rows)
    resolved = [r for r in chosen if r["outcome"]["status"] == "resolved"]
    positive = np.array([r["hindsight_action"] in {-1, 1} for r in resolved], dtype=bool)
    output = {}
    for key in (*study.data.FEATURES, *study.flow.FEATURES):
        values = np.array(
            [({**r["features"], **r["execution_features"]})[key] for r in resolved], dtype=float
        )
        if not np.isfinite(values).all():
            raise ValueError("Nonfinite case feature")
        output[key] = {
            "positive_opportunity_auc": study.diagnostics.auc(positive.astype(int), values),
            "mean_before_positive": float(values[positive].mean()) if positive.any() else None,
            "mean_before_nonpositive": float(values[~positive].mean())
            if (~positive).any()
            else None,
        }
    return {
        "causally_thinned": len(chosen),
        "resolved": len(resolved),
        "positive": int(positive.sum()),
        "nonpositive": int((~positive).sum()),
        "unavailable": len(chosen) - len(resolved),
        "feature_associations": output,
        "interpretation": "Descriptive associations, no causal or profitable-entry claim",
    }


class DailyBuilder(study.flow.ExecutionBuilder, receive.ReceiveClockCore):
    def __init__(self, day: str, contract: str):
        if contract != dated_contract(day):
            raise ValueError("Contract differs from declared calendar")
        sessions = (day,) if date.fromisoformat(day).weekday() < 5 else ()
        super().__init__(sessions, minimum_resolved=100)
        self.contract = contract

    def start_day(self, day) -> None:
        super().start_day(day)
        protected = (
            (self.window_start_ns - self.quote_warmup_ns, self.window_end_ns)
            if self.sessions
            else None
        )
        self.clock_audit = receive.ClockAudit(day.isoformat(), protected)
        self.quote_buffer = array("q")

    def _process_quote(self, quote) -> None:
        if len(self.quote_buffer) // 3 >= paths.MAX_QUOTES:
            raise ValueError("Daily completed quote bound exceeded")
        self.quote_buffer.extend((quote.ts_recv_ns, quote.bid, quote.ask))
        super()._process_quote(quote)

    def finish(self) -> tuple[list[dict], list[dict], dict]:
        rows, quality = super().finish()
        if self.clock_audit.counts["target_records"] != quality["target_records"]:
            raise ValueError("Daily clock audit count differs")
        study.audit_conservation(quality["execution_flow"])
        quality["receive_clock_v2"] = self.clock_audit.report()
        selected = []
        if self.sessions:
            baseline.validate_rows(rows, sessions=self.sessions, feature_names=study.data.FEATURES)
            quotes = np.frombuffer(self.quote_buffer, dtype=np.int64).reshape(-1, 3)
            paths.validate_quotes(quotes, self.window_end_ns)
            for row in study.diagnostics.thin_causally(rows):
                selected.append(
                    {
                        **row,
                        "path_horizons": paths.analyze_entry(
                            quotes, row["outcome"], self.window_end_ns
                        ),
                    }
                )
        for row in (*rows, *selected):
            row.update(contract=self.contract, partition="development")
            if set(row["execution_features"]) != set(study.flow.FEATURES) or any(
                not math.isfinite(x) or x < 0 for x in row["execution_features"].values()
            ):
                raise ValueError("Invalid execution features")
        return rows, selected, quality


def replay_day(member: dict) -> tuple[list[dict], list[dict], dict]:
    day = member["utc_date"]
    contract = dated_contract(day)  # Refuse reserved dates before any archive access.
    if member["contract"] != contract or member["condition"] != "available":
        raise ValueError("Undeclared contract or degraded member")
    builder = DailyBuilder(day, contract)
    builder.start_day(date.fromisoformat(day))
    path = Path(member["archive"])
    stamp = (path.stat().st_size, path.stat().st_mtime_ns)
    if path.is_symlink() or stamp[0] != member["archive_bytes"]:
        raise ValueError("Archive differs from registration")
    started = time.monotonic()
    with zipfile.ZipFile(path) as archive:
        for index, record in enumerate(source._member_records(archive, member)):
            if index % 65536 == 0 and time.monotonic() - started > MAX_DAY_SECONDS:
                raise TimeoutError("Daily replay time bound exceeded")
            builder.consume(record)
        builder.finish_day()
    if (path.stat().st_size, path.stat().st_mtime_ns) != stamp:
        raise ValueError("Archive changed during replay")
    rows, cases, quality = builder.finish()
    if time.monotonic() - started > MAX_DAY_SECONDS:
        raise TimeoutError("Daily replay and path analysis time bound exceeded")
    return (
        rows,
        cases,
        {
            "quality": quality,
            "instrument_id": builder.instrument_id,
            "full_member_hash_verified": True,
        },
    )


def encode_rows(rows: list[dict]) -> bytes:
    result = bytearray()
    for row in rows:
        result.extend(common.canonical(row) + b"\n")
        if len(result) > MAX_DAY_BYTES:
            raise ValueError("Daily artifact byte bound exceeded")
    return bytes(result)


def run(root: Path, path: Path, pin: str, output: Path) -> dict:
    frozen = registration(root, path, pin)
    if not output.resolve().is_relative_to((root / "data" / "processed").resolve()):
        raise ValueError("Census outputs must stay under project processed data")
    if shutil.disk_usage(root).free < MAX_TOTAL_BYTES + 1024**3:
        raise ValueError("Insufficient free space for bounded census")
    output.mkdir(parents=False, exist_ok=False)  # Exclusive run; no implicit restart.
    (output / "days").mkdir()
    (output / "attempts").mkdir()
    common._write_new(
        output / "attempt.json",
        {
            "registration_sha256": pin,
            "started_utc": datetime.now(UTC).isoformat(),
            "status": "claimed_not_complete",
            "automatic_retry": False,
        },
    )
    started, written, records = time.monotonic(), 0, []
    journal = output / "progress.jsonl"

    def record(item):
        with journal.open("ab") as handle:
            handle.write(common.canonical(item) + b"\n")
            handle.flush()
        records.append(item)
        print(json.dumps(item, separators=(",", ":")), flush=True)

    try:
        for member in frozen["inventory"]["ledger"]:
            day, action = member["utc_date"], member["planned_action"]
            if action in {"reserved_metadata_only", "vendor_degraded_no_replay"}:
                record({"utc_date": day, "status": action, "raw_opened": False})
                continue
            if time.monotonic() - started > MAX_SECONDS:
                raise TimeoutError("Census wall-time bound exceeded")
            if written + 2 * MAX_DAY_BYTES > MAX_TOTAL_BYTES:
                raise ValueError("Census total output bound reached")
            registration(root, path, pin)
            common._write_new(
                output / "attempts" / f"{day}.json",
                {
                    "utc_date": day,
                    "contract": member["contract"],
                    "registration_sha256": pin,
                    "source_sha256": member["sha256"],
                    "started_utc": datetime.now(UTC).isoformat(),
                    "exposure": "conservatively_exposed_before_raw_access",
                },
            )
            print(f"Replaying census {day} {member['contract']}", flush=True)
            try:
                rows, cases, quality = replay_day(member)
            except (ValueError, TimeoutError, zipfile.BadZipFile) as exc:
                refusal = {
                    "utc_date": day,
                    "status": "quality_refused",
                    "raw_access_attempted": True,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "source_sha256": member["sha256"],
                    "automatic_retry": False,
                }
                common._write_new(output / "days" / f"{day}.failure.json", refusal)
                record(refusal)
                continue
            raw, cases_raw = encode_rows(rows), encode_rows(cases)
            report = {
                "utc_date": day,
                "status": "replayed",
                "contract": member["contract"],
                "registration_sha256": pin,
                "source_sha256": member["sha256"],
                "rows": len(rows),
                "cases": len(cases),
                "rows_sha256": hashlib.sha256(raw).hexdigest(),
                "cases_sha256": hashlib.sha256(cases_raw).hexdigest(),
                **quality,
                "summary": study.diagnostics.summarize(rows),
                "case_associations": case_associations(rows),
                "thinned_paths": paths.horizon_summary(cases),
                "training_eligible": False,
                "promotion_enabled": False,
            }
            report_bytes = len(common.canonical(report)) + 1
            if report_bytes > 2 * 1024**2:
                raise ValueError("Daily report byte bound exceeded")
            if written + len(raw) + len(cases_raw) + report_bytes > MAX_TOTAL_BYTES:
                raise ValueError("Census total published byte bound exceeded")
            registration(root, path, pin)
            for suffix, content in (("rows.jsonl", raw), ("cases.jsonl", cases_raw)):
                with (output / "days" / f"{day}.{suffix}").open("xb") as handle:
                    handle.write(content)
            common._write_new(output / "days" / f"{day}.json", report)
            written += len(raw) + len(cases_raw) + (output / "days" / f"{day}.json").stat().st_size
            record(
                {
                    "utc_date": day,
                    "status": "replayed",
                    "rows": len(rows),
                    "cases": len(cases),
                    "report_sha256": common.hash_file(output / "days" / f"{day}.json", 2 * 1024**2),
                }
            )
        result = {
            "status": "census_completed_not_strategy_validated",
            "registration_sha256": pin,
            "counts": dict(Counter(r["status"] for r in records)),
            "dates": records,
            "total_published_bytes": written,
            "finished_utc": datetime.now(UTC).isoformat(),
            "reserved_outcomes_opened": False,
            "training_enabled": False,
            "promotion_enabled": False,
            "strategy_aggregate_permitted": False,
            "progress_sha256": common.hash_file(journal, 2 * 1024**2),
        }
        registration(root, path, pin)
        common._write_new(output / "completion.json", result)
        return result
    except Exception as exc:
        common._write_new(
            output / "failure.json",
            {
                "status": "census_incomplete",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "recorded_dates": len(records),
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
        print(json.dumps(result["inventory"]["planned_actions"]))
    else:
        if args.registration_sha256 is None or args.output is None:
            parser.error("Registration SHA256 and exclusive output directory required")
        result = run(args.project_root, args.registration, args.registration_sha256, args.output)
        print(json.dumps({k: result[k] for k in ("status", "counts")}))


if __name__ == "__main__":
    main()
