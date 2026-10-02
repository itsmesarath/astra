"""Opt-in disk-backed replay of one quote-limited development day and one control.

The frozen census, receive-clock policy, features and target/path functions stay
unchanged. This is a registered resource correction, not strategy validation.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import shutil
import time
import zipfile
from array import array
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ai_trader.research import historical_6e_refusal_diagnostic as diagnostic

census, review = diagnostic.census, diagnostic.review
common, paths = census.common, census.paths
CONTROL_DAY = "2025-04-03"
RESOURCE_DAY = "2025-04-04"
MAX_QUOTES = 12_000_000  # 288 MB of retained, little-endian int64 quote columns.
MAX_PATH_QUOTES = 1_000_000  # Refuse pathological paths, never thin their quotes.
CHUNK_QUOTES = 65536
MAX_SECONDS = 2 * census.MAX_DAY_SECONDS
COLUMNS = ("ts", "bid", "ask")


def fingerprints() -> dict:
    return {
        **diagnostic.fingerprints(),
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
    }


def protocol() -> dict:
    return {
        "version": "6e_disk_quote_resource_replay_v1",
        "dates": [CONTROL_DAY, RESOURCE_DAY],
        "scope": "Previously exposed development only; control then resource-refused day",
        "storage": "Three append-only little-endian int64 columns; contiguous timestamp mmap; "
        "retain every completed quote in original order, including equal timestamps",
        "unchanged": "Receive-clock V2, original book/events/features/decisions, 100ms entry, "
        "15s crossed quote targets, one extra tick, causal 60s case selection and all path rules",
        "control": "Require byte-identical rows and cases against original accepted day",
        "bounds": {
            "quotes_per_day": MAX_QUOTES,
            "quotes_per_path": MAX_PATH_QUOTES,
            "quotes_per_write_chunk": CHUNK_QUOTES,
            "quote_bytes_per_day": MAX_QUOTES * 24,
            "seconds_per_day": census.MAX_DAY_SECONDS,
            "seconds_total": MAX_SECONDS,
            "artifact_bytes": census.MAX_DAY_BYTES,
        },
        "failure": "Exclusive one attempt; retain evidence; no automatic retry or subset success",
        "training_enabled": False,
        "trading_enabled": False,
        "promotion_enabled": False,
    }


def scope(root: Path) -> dict:
    # Check both dates before any raw path can be constructed.
    for day in (CONTROL_DAY, RESOURCE_DAY):
        census.dated_contract(day)
    old = diagnostic.scope(root)
    frozen = census.registration(root, root / diagnostic.REGISTRATION, diagnostic.REGISTRATION_PIN)
    ledger = {m["utc_date"]: m for m in frozen["inventory"]["ledger"]}
    receipt = review.pinned(
        root / diagnostic.CENSUS_DIRECTORY / "completion.json", diagnostic.RECEIPT_PIN
    )
    entries = {r["utc_date"]: r for r in receipt["dates"]}
    if (
        entries[CONTROL_DAY]["status"] != "replayed"
        or entries[RESOURCE_DAY]["status"] != "quality_refused"
        or entries[RESOURCE_DAY]["error"] != "Daily completed quote bound exceeded"
    ):
        raise ValueError("Resource replay requires its accepted control and original quote refusal")
    control = review.pinned(
        root / diagnostic.CENSUS_DIRECTORY / "days" / f"{CONTROL_DAY}.json",
        entries[CONTROL_DAY]["report_sha256"],
    )
    for day in (CONTROL_DAY, RESOURCE_DAY):
        if (
            ledger[day]["condition"] != "available"
            or ledger[day]["planned_action"] != "decision_window_replay"
            or ledger[day]["contract"] != census.dated_contract(day)
        ):
            raise ValueError("Resource replay member scope differs")
    if (
        control["source_sha256"] != ledger[CONTROL_DAY]["sha256"]
        or control["full_member_hash_verified"] is not True
        or control["training_eligible"] is not False
    ):
        raise ValueError("Control identity or operational scope differs")
    return {
        "source_scope": old,
        "members": [ledger[CONTROL_DAY], ledger[RESOURCE_DAY]],
        "control_report_sha256": entries[CONTROL_DAY]["report_sha256"],
        "control_rows_sha256": control["rows_sha256"],
        "control_cases_sha256": control["cases_sha256"],
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
        raise ValueError("Resource registration, implementation or source changed")
    return frozen


class QuoteView:
    """Small adapter for the unchanged path analyzer, without an Nx3 resident array."""

    def __init__(self, directory: Path, count: int):
        if not 1 <= count <= MAX_QUOTES:
            raise ValueError("Invalid disk quote count")
        self.count, self.columns = count, []
        try:
            for name in COLUMNS:
                path = directory / f"{name}.i64"
                if path.is_symlink() or path.stat().st_size != count * 8:
                    raise ValueError("Disk quote column is linked or has wrong length")
                self.columns.append(np.memmap(path, dtype="<i8", mode="r", shape=(count,)))
        except Exception:
            self.close()
            raise

    def __len__(self):
        return self.count

    def __getitem__(self, key):
        if isinstance(key, tuple):
            selection, column = key
            return self.columns[column][selection]
        if isinstance(key, slice):
            start, stop, step = key.indices(self.count)
            if step != 1 or max(0, stop - start) > MAX_PATH_QUOTES:
                raise ValueError("Disk quote path slice exceeds resource bound")
            return np.column_stack([column[key] for column in self.columns])
        return np.asarray([column[key] for column in self.columns], dtype=np.int64)

    def close(self):
        for column in self.columns:
            column._mmap.close()
        self.columns = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class QuoteSpool:
    def __init__(self, directory: Path, window_end: int):
        directory.mkdir(parents=False, exist_ok=False)
        self.directory, self.window_end = directory, window_end
        self.count, self.buffer, self.last_recv = 0, array("q"), None
        self.handles, self.sealed = [], False
        try:
            for name in COLUMNS:
                self.handles.append((directory / f"{name}.i64").open("xb"))
        except Exception:
            self.close()
            raise

    def append(self, quote) -> None:
        if self.sealed or not self.handles:
            raise ValueError("Disk quote spool is closed")
        if self.count >= MAX_QUOTES:
            raise ValueError("Disk completed quote bound exceeded")
        if self.last_recv is not None and quote.ts_recv_ns < self.last_recv:
            raise ValueError("Disk completed quote receive timestamp regressed")
        self.buffer.extend((quote.ts_recv_ns, quote.bid, quote.ask))
        self.last_recv = quote.ts_recv_ns
        self.count += 1
        if len(self.buffer) // 3 >= CHUNK_QUOTES:
            self.flush()

    def flush(self) -> None:
        if not self.buffer:
            return
        quotes = np.frombuffer(self.buffer, dtype=np.int64).reshape(-1, 3)
        ts, bid, ask = quotes.T
        if (
            np.any(np.diff(ts) < 0)
            or np.any(ts < 0)
            or np.any(ts >= self.window_end)
            or np.any(bid <= 0)
            or np.any(ask <= bid)
            or np.any(bid % paths.clock.TICK)
            or np.any(ask % paths.clock.TICK)
        ):
            raise ValueError("Invalid disk completed quote sequence")
        for column, handle in zip(quotes.T, self.handles, strict=True):
            handle.write(np.asarray(column, dtype="<i8").tobytes())
        self.buffer = array("q")

    def seal(self) -> QuoteView:
        if self.sealed or not self.handles:
            raise ValueError("Disk quote spool already closed")
        self.flush()
        self.sealed = True
        self.close()
        return QuoteView(self.directory, self.count)

    def close(self) -> None:
        for handle in self.handles:
            handle.close()
        self.handles = []


class DiskDailyBuilder(census.DailyBuilder):
    def __init__(self, day: str, contract: str, quote_directory: Path):
        super().__init__(day, contract)
        self.quote_directory = quote_directory
        self.spool = None

    def start_day(self, day) -> None:
        if self.spool is not None:
            raise ValueError("Disk builder cannot carry state across source sessions")
        super().start_day(day)
        self.spool = QuoteSpool(self.quote_directory, self.window_end_ns)

    def _process_quote(self, quote) -> None:
        self.spool.append(quote)
        # Skip only the frozen DailyBuilder's whole-day array; retain every lower hook.
        super(census.DailyBuilder, self)._process_quote(quote)

    def finish(self) -> tuple[list[dict], list[dict], dict]:
        # Same feature/outcome finalization as DailyBuilder, different quote storage only.
        rows, quality = super(census.DailyBuilder, self).finish()
        if self.clock_audit.counts["target_records"] != quality["target_records"]:
            raise ValueError("Disk daily clock audit count differs")
        census.study.audit_conservation(quality["execution_flow"])
        quality["receive_clock_v2"] = self.clock_audit.report()
        census.baseline.validate_rows(
            rows, sessions=self.sessions, feature_names=census.study.data.FEATURES
        )
        with self.spool.seal() as quotes:
            selected = [
                {
                    **row,
                    "path_horizons": paths.analyze_entry(
                        quotes, row["outcome"], self.window_end_ns
                    ),
                }
                for row in census.study.diagnostics.thin_causally(rows)
            ]
        for row in (*rows, *selected):
            row.update(contract=self.contract, partition="development")
            if set(row["execution_features"]) != set(census.study.flow.FEATURES) or any(
                not math.isfinite(x) or x < 0 for x in row["execution_features"].values()
            ):
                raise ValueError("Invalid disk replay execution features")
        return rows, selected, quality


def replay_day(member: dict, quote_directory: Path) -> tuple[list, list, dict]:
    contract = census.dated_contract(member["utc_date"])
    if member["contract"] != contract or member["condition"] != "available":
        raise ValueError("Undeclared or degraded resource member")
    path = Path(member["archive"])
    stamp = (path.stat().st_size, path.stat().st_mtime_ns)
    if path.is_symlink() or stamp[0] != member["archive_bytes"]:
        raise ValueError("Resource source archive changed or linked")
    builder = DiskDailyBuilder(member["utc_date"], contract, quote_directory)
    builder.start_day(census.v1.iso_day(member["utc_date"]))
    started = time.monotonic()
    try:
        with zipfile.ZipFile(path) as archive:
            for index, record in enumerate(census.source._member_records(archive, member)):
                if index % 65536 == 0 and time.monotonic() - started > census.MAX_DAY_SECONDS:
                    raise TimeoutError("Disk replay per-day time bound exceeded")
                builder.consume(record)
            builder.finish_day()
        if (path.stat().st_size, path.stat().st_mtime_ns) != stamp:
            raise ValueError("Resource source archive changed during replay")
        rows, cases, quality = builder.finish()
        if time.monotonic() - started > census.MAX_DAY_SECONDS:
            raise TimeoutError("Disk replay/path analysis per-day time bound exceeded")
        storage = {
            name: {
                "bytes": (quote_directory / f"{name}.i64").stat().st_size,
                "sha256": common.hash_file(quote_directory / f"{name}.i64", MAX_QUOTES * 8),
            }
            for name in COLUMNS
        }
        if time.monotonic() - started > census.MAX_DAY_SECONDS:
            raise TimeoutError("Disk replay evidence hashing per-day time bound exceeded")
        return (
            rows,
            cases,
            {
                "quality": quality,
                "instrument_id": builder.instrument_id,
                "full_member_hash_verified": True,
                "completed_quotes": builder.spool.count,
                "quote_columns": storage,
            },
        )
    finally:
        builder.spool.close()  # Retain disk evidence on refusal, never an implicit retry.


def run(root: Path, path: Path, pin: str, output: Path) -> dict:
    if output.exists() or not output.resolve().is_relative_to((root / "data/processed").resolve()):
        raise ValueError("Resource directory must be new and inside processed data")
    frozen = registration(root, path, pin)
    if shutil.disk_usage(root).free < 2 * (MAX_QUOTES * 24 + 2 * census.MAX_DAY_BYTES) + 1024**3:
        raise ValueError("Insufficient disk space for bounded resource replay")
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
        for member in frozen["scope"]["members"]:
            if time.monotonic() - started > MAX_SECONDS:
                raise TimeoutError("Resource replay total time bound exceeded")
            registration(root, path, pin)
            day = member["utc_date"]
            common._write_new(
                output / f"{day}.attempt.json",
                {
                    "utc_date": day,
                    "contract": member["contract"],
                    "source_sha256": member["sha256"],
                    "registration_sha256": pin,
                    "exposure": "already_exposed_development_resource_correction",
                },
            )
            print(f"Disk-backed resource replay {day}", flush=True)
            rows, cases, quality = replay_day(member, output / f"{day}.quotes")
            raw, case_raw = census.encode_rows(rows), census.encode_rows(cases)
            row_pin, case_pin = (
                hashlib.sha256(raw).hexdigest(),
                hashlib.sha256(case_raw).hexdigest(),
            )
            if day == CONTROL_DAY and (
                row_pin != frozen["scope"]["control_rows_sha256"]
                or case_pin != frozen["scope"]["control_cases_sha256"]
            ):
                raise ValueError("Disk control rows or cases differ from original frozen census")
            registration(root, path, pin)
            for suffix, content in (("rows.jsonl", raw), ("cases.jsonl", case_raw)):
                with (output / f"{day}.{suffix}").open("xb") as handle:
                    handle.write(content)
            report = {
                "utc_date": day,
                "status": "replayed_resource_correction",
                "contract": member["contract"],
                "source_sha256": member["sha256"],
                "registration_sha256": pin,
                "rows": len(rows),
                "cases": len(cases),
                "rows_sha256": row_pin,
                "cases_sha256": case_pin,
                **quality,
                "control_byte_parity_verified": day == CONTROL_DAY,
                "training_eligible": False,
                "promotion_enabled": False,
            }
            common._write_new(output / f"{day}.json", report)
            reports.append(
                {
                    "utc_date": day,
                    "report_sha256": common.hash_file(
                        output / f"{day}.json", diagnostic.MAX_REPORT_BYTES
                    ),
                }
            )
        if time.monotonic() - started > MAX_SECONDS:
            raise TimeoutError("Resource replay total time bound exceeded")
        registration(root, path, pin)
        result = {
            "status": "resource_correction_completed_not_strategy_validated",
            "registration_sha256": pin,
            "reports": reports,
            "source_scope": frozen["scope"],
            "implementation_sha256": frozen["implementation_sha256"],
            "finished_utc": datetime.now(UTC).isoformat(),
            "original_census_modified": False,
            "quality_gate_changed": False,
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
                "status": "resource_correction_incomplete",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "completed_dates": len(reports),
                "registration_sha256": pin,
                "automatic_retry": False,
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
        prepare(args.project_root, args.registration)
        print("Resource replay registered; no raw data opened")
    else:
        if args.registration_sha256 is None or args.output is None:
            parser.error("Registration pin and exclusive output directory required")
        result = run(args.project_root, args.registration, args.registration_sha256, args.output)
        print(
            common.canonical(
                {"status": result["status"], "reports": len(result["reports"])}
            ).decode()
        )


if __name__ == "__main__":
    main()
