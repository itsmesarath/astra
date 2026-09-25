"""Offline sequence-only adapter for pinned legacy spot Parquet, not native captures.

Preserve source order and ambiguous source timestamps. Never synthesize receipt
times, sort away faults, read price/quantity columns, generate labels or train.
"""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ai_trader.ingestion import hf_lob_intake as intake

VERSION = "legacy_spot_sequence_audit_v1"
TIME_POLICY = "source_timestamp_ms_semantics_unresolved"
DAY_MS = 86_400_000
MAX_ID = 10**18
MAX_ANCHORS = 256
MAX_SEGMENTS = 256
MAX_REPORT_BYTES = 1_000_000
PROJECTED = {
    "snapshots": ("timestamp_ms", "last_update_id", "asset", "exchange", "side"),
    "trades": ("timestamp_ms", "trade_id", "asset", "exchange", "buyer_maker"),
    "depth": ("timestamp_ms", "first_update_id", "last_update_id", "asset", "exchange", "side"),
}


@dataclass(frozen=True)
class AuditConfig:
    batch_rows: int = 65_536
    max_total_rows: int = 80_000_000
    max_seconds: int = 300
    idle_gap_ms: int = 1000
    max_examples_per_fault: int = 20

    def __post_init__(self):
        bounds = {
            "batch_rows": (1, 65_536),
            "max_total_rows": (1, 100_000_000),
            "max_seconds": (1, 600),
            "idle_gap_ms": (1, 60_000),
            "max_examples_per_fault": (0, 100),
        }
        for name, (low, high) in bounds.items():
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"Invalid audit limit: {name}.")


DEFAULT_AUDIT_CONFIG = AuditConfig()


def _digest(value):
    return hashlib.sha256(intake._canonical(value)).hexdigest()


def _implementation():
    return {
        "modules": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__), Path(intake.__file__))
        },
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pyarrow": importlib.metadata.version("pyarrow"),
    }


def _protocol(plan, config):
    return {
        "schema_version": 1,
        "protocol": VERSION,
        "intake_plan": plan,
        "intake_plan_sha256": _digest(plan),
        "config": asdict(config),
        "implementation": _implementation(),
        "time_policy": TIME_POLICY,
        "trade_identifier_policy": "publisher_trade_id_not_native_aggregate_trade_id",
        "depth_group_key": ["timestamp_ms", "first_update_id", "last_update_id"],
        "ordering": "stored_row_order_no_sort_no_deduplication",
        "projected_columns": {k: list(v) for k, v in PROJECTED.items()},
        "research_scope": "entire_pinned_month_quality_only_no_holdout_claim",
        "training_allowed": False,
        "promotion_allowed": False,
        "live_trading_available": False,
    }


def register_audit(plan_path, output_path, config=DEFAULT_AUDIT_CONFIG):
    """Freeze schema/time policy and resource limits before reading source rows."""
    if type(config) is not AuditConfig:
        raise ValueError("Typed audit configuration required.")
    protocol = _protocol(intake.load_plan(plan_path), config)
    intake._publish(Path(output_path), protocol)
    return hashlib.sha256(intake._canonical(protocol)).hexdigest()


def _load_protocol(path, expected_sha256):
    with Path(path).open("rb") as source:
        raw = source.read(64 * 1024 + 1)
    if len(raw) > 64 * 1024 or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Audit registration differs from pinned raw-file checksum.")
    value = json.loads(raw, object_pairs_hook=intake._no_duplicates)
    config = AuditConfig(**value["config"])
    plan = intake.validate_plan(value["intake_plan"])
    if intake._canonical(value) != intake._canonical(_protocol(plan, config)):
        raise ValueError("Audit registration differs from current code/environment/contract.")
    return value, config


def _month_bounds(month):
    year, number = map(int, month.split("-"))
    start = datetime(year, number, 1, tzinfo=UTC)
    end = datetime(year + (number == 12), number % 12 + 1, 1, tzinfo=UTC)
    return int(start.timestamp()) * 1000, int(end.timestamp()) * 1000


@dataclass(frozen=True)
class HistoricalKeys:
    """Diagnostic-only columns; deliberately no event/received_at or execution fields."""

    source_time_ms: np.ndarray
    first_id: np.ndarray
    final_id: np.ndarray
    source_rows: np.ndarray


def adapt_keys(kind, timestamps, first_ids, final_ids, *, row_offset, previous_raw=None):
    """Collapse consecutive depth/snapshot *level rows* into diagnostic message keys.

    Trades are never collapsed. Identical range/time keys cannot distinguish a
    duplicated entire depth event from extra levels; this limitation is reported.
    """
    if kind not in PROJECTED or type(row_offset) is not int or row_offset < 0:
        raise ValueError("Invalid source kind/row offset.")
    arrays = (timestamps, first_ids, final_ids)
    if (
        any(type(a) is not np.ndarray or a.dtype != np.int64 or a.ndim != 1 for a in arrays)
        or not 1 <= len(timestamps) <= 65_536
        or any(len(a) != len(timestamps) for a in arrays)
    ):
        raise ValueError("Expected bounded, equally sized int64 sequence columns.")
    if any(np.any(a < 0) or np.any(a > MAX_ID) for a in arrays) or np.any(first_ids > final_ids):
        raise ValueError("Invalid timestamp/sequence identifier range.")
    keep = np.ones(len(timestamps), dtype=bool)
    if kind != "trades":
        keep[1:] = (
            (timestamps[1:] != timestamps[:-1])
            | (first_ids[1:] != first_ids[:-1])
            | (final_ids[1:] != final_ids[:-1])
        )
        if previous_raw is not None:
            keep[0] = tuple(int(a[0]) for a in arrays) != previous_raw
    positions = np.flatnonzero(keep)
    values = [a[positions].copy() for a in arrays] + [positions.astype(np.int64) + row_offset]
    for array in values:
        array.flags.writeable = False
    return HistoricalKeys(*values), tuple(int(a[-1]) for a in arrays)


class SequenceSummary:
    """Streaming cross-batch diagnostics; counts faults without repairing them."""

    def __init__(self, kind, config):
        self.kind, self.config = kind, config
        self.rows = self.units = 0
        self.previous = None
        self.first = self.last = None
        self.counts = dict.fromkeys(
            (
                "forward_id_gaps",
                "nonadvancing_ids",
                "overlap_advances",
                "source_time_regressions",
                "source_idle_gaps",
            ),
            0,
        )
        self.examples = {k: [] for k in self.counts}
        self.missing_id_positions = 0
        self.max_idle_ms = 0
        self.by_source_day = {}
        self.run = self.longest_run = None
        self.run_count = 0
        self.segments = []
        self.segments_truncated = False

    def raw_rows(self, timestamps):
        self.rows += len(timestamps)
        for day, count in zip(*np.unique(timestamps // DAY_MS, return_counts=True), strict=True):
            key = datetime.fromtimestamp(int(day) * 86400, UTC).date().isoformat()
            self.by_source_day[key] = self.by_source_day.get(key, 0) + int(count)

    def _finish_run(self):
        if self.run is not None:
            finished = dict(self.run)
            finished["duration_ms"] = (
                self.run["end_source_time_ms"] - self.run["start_source_time_ms"]
            )
            if self.longest_run is None or (finished["duration_ms"], finished["units"]) > (
                self.longest_run["duration_ms"],
                self.longest_run["units"],
            ):
                self.longest_run = finished
            if len(self.segments) < MAX_SEGMENTS:
                self.segments.append(finished)
            else:
                self.segments_truncated = True
            self.run = None

    def add(self, keys):
        t, f, u, rows = keys.source_time_ms, keys.first_id, keys.final_id, keys.source_rows
        if not len(t):
            return
        has_previous = np.ones(len(t), dtype=bool)
        previous_time, previous_id = self.previous or (int(t[0]), int(u[0]))
        has_previous[0] = self.previous is not None
        pt, pu = np.r_[previous_time, t[:-1]], np.r_[previous_id, u[:-1]]
        elapsed = t - pt
        gaps = (f > pu + 1) & has_previous
        overlaps = (f <= pu) & (u > pu) & has_previous
        if self.kind == "snapshots":
            gaps[:] = overlaps[:] = False  # Sparse snapshot IDs do not define missed updates.
        flags = {
            "forward_id_gaps": gaps,
            "nonadvancing_ids": (u <= pu) & has_previous,
            "overlap_advances": overlaps,
            "source_time_regressions": (elapsed < 0) & has_previous,
            "source_idle_gaps": (elapsed > self.config.idle_gap_ms) & has_previous,
        }
        self.missing_id_positions += sum(int(x) for x in (f - pu - 1)[gaps])
        if has_previous.any():
            self.max_idle_ms = max(self.max_idle_ms, int(elapsed[has_previous].max()))
        for name, mask in flags.items():
            self.counts[name] += int(np.count_nonzero(mask))
            remaining = self.config.max_examples_per_fault - len(self.examples[name])
            for i in np.flatnonzero(mask)[:remaining]:
                self.examples[name].append(
                    {
                        "source_row": int(rows[i]),
                        "source_time_ms": int(t[i]),
                        "first_id": int(f[i]),
                        "final_id": int(u[i]),
                        "previous_final_id": int(pu[i]),
                        "previous_source_time_ms": int(pt[i]),
                    }
                )
        breaks = gaps | flags["nonadvancing_ids"] | flags["source_time_regressions"]
        breaks |= flags["source_idle_gaps"]
        starts = np.unique(np.r_[0, np.flatnonzero(breaks)])
        ends = np.r_[starts[1:], len(t)]
        for start, end in zip(starts, ends, strict=True):
            if self.run is None or breaks[start]:
                self._finish_run()
                self.run_count += 1
                self.run = {
                    "start_source_time_ms": int(t[start]),
                    "first_source_row": int(rows[start]),
                    "units": 0,
                }
            self.run["units"] += int(end - start)
            self.run["end_source_time_ms"] = int(t[end - 1])
            self.run["last_source_row"] = int(rows[end - 1])
        self.units += len(t)
        if self.first is None:
            self.first = {"source_time_ms": int(t[0]), "first_id": int(f[0])}
        self.last = {"source_time_ms": int(t[-1]), "final_id": int(u[-1])}
        self.previous = int(t[-1]), int(u[-1])

    def result(self):
        self._finish_run()
        return {
            "rows_scanned": self.rows,
            "diagnostic_units": self.units,
            "unit_definition": "trade_rows"
            if self.kind == "trades"
            else "consecutive_range_time_groups",
            "first_stored_unit": self.first,
            "last_stored_unit": self.last,
            "counts": self.counts,
            "examples": self.examples,
            "missing_numeric_id_positions": self.missing_id_positions,
            "maximum_source_idle_ms": self.max_idle_ms,
            "rows_by_source_timestamp_day": self.by_source_day,
            "observed_run_count": self.run_count,
            "segments": self.segments,
            "segments_truncated": self.segments_truncated,
            "longest_observed_run": self.longest_run,
        }


def _arrays(batch, kind, month_bounds):
    import pyarrow.compute as pc

    if any(column.null_count for column in batch.columns):
        raise ValueError("Null sequence/provenance values cannot be silently skipped.")
    for column, value in (("asset", "BTCUSDT"), ("exchange", "binance")):
        if not pc.all(pc.equal(batch.column(column), value)).as_py():
            raise ValueError("Mixed symbol/venue in pinned spot source.")
    if (
        kind != "trades"
        and not pc.all(
            pc.or_(pc.equal(batch.column("side"), "bid"), pc.equal(batch.column("side"), "ask"))
        ).as_py()
    ):
        raise ValueError("Unrecognized side value.")
    t = batch.column("timestamp_ms").to_numpy(zero_copy_only=False)
    name = "trade_id" if kind == "trades" else "last_update_id"
    u = batch.column(name).to_numpy(zero_copy_only=False)
    f = batch.column("first_update_id").to_numpy(zero_copy_only=False) if kind == "depth" else u
    if np.any(t < month_bounds[0]) or np.any(t >= month_bounds[1]):
        raise ValueError("Source timestamp outside its declared month.")
    return t, f, u


def _schema(parquet, kind):
    schema = parquet.schema_arrow
    if len(schema.names) != len(set(schema.names)) or parquet.metadata.num_columns > 64:
        raise ValueError("Duplicate/oversized source schema.")
    for name in PROJECTED[kind]:
        expected = "string" if name in {"asset", "exchange", "side"} else "int64"
        if name == "buyer_maker":
            expected = "bool"
        if name not in schema.names or str(schema.field(name).type) != expected:
            raise ValueError(f"Unsupported projected column: {name}.")
    if parquet.metadata.num_row_groups > 10_000:
        raise ValueError("Row-group budget exceeded.")
    for group in range(parquet.metadata.num_row_groups):
        selected_bytes = sum(
            parquet.metadata.row_group(group)
            .column(schema.get_field_index(name))
            .total_uncompressed_size
            for name in PROJECTED[kind]
        )
        if selected_bytes > 128 * 1024 * 1024:
            raise ValueError("Projected row group exceeds decoded-byte budget.")


def _scan_file(source, spec, config, bounds, anchors, anchor_meta, deadline):
    import pyarrow.parquet as pq

    intake._verify_file(source, spec)
    parquet = pq.ParquetFile(
        source,
        pre_buffer=False,
        thrift_string_size_limit=1_000_000,
        thrift_container_size_limit=100_000,
    )
    kind = spec["kind"]
    _schema(parquet, kind)
    if not 1 <= parquet.metadata.num_rows <= config.max_total_rows:
        raise ValueError("Source row count exceeds remaining registered budget or is empty.")
    summary = SequenceSummary(kind, config)
    tail = None
    for batch in parquet.iter_batches(
        batch_size=config.batch_rows, columns=list(PROJECTED[kind]), use_threads=False
    ):
        if time.monotonic() >= deadline:
            raise TimeoutError("Audit exceeded registered elapsed budget.")
        if batch.nbytes > 16 * 1024 * 1024:
            raise ValueError("Projected batch exceeds decoded-byte budget.")
        t, f, u = _arrays(batch, kind, bounds)
        keys, tail = adapt_keys(kind, t, f, u, row_offset=summary.rows, previous_raw=tail)
        summary.raw_rows(t)
        summary.add(keys)
        if kind == "snapshots":
            anchor_meta["groups_scanned"] += len(keys.source_rows)
            for index in range(len(keys.source_rows)):
                # The complete snapshot stream is audited, while only a bounded,
                # deterministic prefix is retained for the later depth bridge.
                # Refusing the whole audit merely because the source has many
                # snapshot levels would turn a reporting budget into data loss.
                if len(anchors) >= MAX_ANCHORS:
                    anchor_meta["sampling_truncated"] = True
                    continue
                anchors.append(
                    {
                        "source_row": int(keys.source_rows[index]),
                        "source_time_ms": int(keys.source_time_ms[index]),
                        "last_update_id": int(keys.final_id[index]),
                        "first_depth_id_bridge": None,
                    }
                )
        elif kind == "depth":
            for anchor in anchors:
                if anchor["first_depth_id_bridge"] is None:
                    candidates = np.flatnonzero(
                        (keys.first_id <= anchor["last_update_id"] + 1)
                        & (keys.final_id > anchor["last_update_id"])
                    )
                    if len(candidates):
                        i = candidates[0]
                        anchor["first_depth_id_bridge"] = {
                            "source_row": int(keys.source_rows[i]),
                            "source_time_ms": int(keys.source_time_ms[i]),
                            "first_id": int(keys.first_id[i]),
                            "final_id": int(keys.final_id[i]),
                        }
    if summary.rows != parquet.metadata.num_rows:
        raise ValueError("Decoded row count differs from footer.")
    intake._verify_file(source, spec)
    if time.monotonic() >= deadline:
        raise TimeoutError("Audit exceeded registered elapsed budget.")
    return {"kind": kind, "sha256": spec["sha256"], **summary.result()}


def audit_registered(registration_path, expected_sha256, directory, output_path):
    protocol, config = _load_protocol(registration_path, expected_sha256)
    output_path, directory = Path(output_path), Path(directory)
    if output_path.exists() or output_path.with_name(output_path.name + ".partial").exists():
        raise FileExistsError(output_path)
    plan = protocol["intake_plan"]
    if intake._canonical(intake.load_plan(directory / "plan.json")) != intake._canonical(plan):
        raise ValueError("Directory plan differs from registered source identities.")
    deadline = time.monotonic() + config.max_seconds
    results, anchors = [], []
    anchor_meta = {"groups_scanned": 0, "sampling_truncated": False}
    rows_left = config.max_total_rows
    for spec in plan["files"]:
        limits = AuditConfig(**(asdict(config) | {"max_total_rows": rows_left}))
        with (directory / f"{spec['kind']}.parquet").open("rb") as source:
            result = _scan_file(
                source,
                spec,
                limits,
                _month_bounds(plan["month"]),
                anchors,
                anchor_meta,
                deadline,
            )
        rows_left -= result["rows_scanned"]
        results.append(result)
        print(json.dumps({"audited": spec["kind"], "rows": result["rows_scanned"]}), flush=True)
    if protocol["implementation"] != _implementation():
        raise ValueError("Implementation changed during audit.")
    report = {
        "schema_version": 1,
        "protocol": VERSION,
        "status": "sequence_audit_complete_training_blocked",
        "registration_raw_sha256": expected_sha256,
        "intake_plan_sha256": _digest(plan),
        "implementation": protocol["implementation"],
        "config": asdict(config),
        "time_policy": TIME_POLICY,
        "files": results,
        "snapshot_id_bridge_candidates": anchors,
        "snapshot_anchor_groups_scanned": anchor_meta["groups_scanned"],
        "snapshot_anchor_groups_retained": len(anchors),
        "snapshot_anchor_sampling_truncated": anchor_meta["sampling_truncated"],
        "all_declared_sources_fully_scanned": True,
        "training_started": False,
        "epochs_completed": 0,
        "labels_generated": 0,
        "price_quantity_columns_read": False,
        "receipt_clock_reconstructed": False,
        "book_reconstructed": False,
        "promotion_allowed": False,
        "live_trading_available": False,
        "limitations": [
            "Source clock meanings and cross-stream availability remain unresolved.",
            "ID bridge candidates do not prove snapshot completeness or causal availability.",
            "Depth group keys cannot detect duplicated identical whole events or missing levels.",
            "Numeric ID gaps are not a count of missed executions or depth messages.",
            "An idle timestamp gap is not by itself proof of lost events.",
            "Longest runs are unanchored diagnostics, not selected training sessions.",
            "Prices, sizes, book coverage, CVD, costs and outcomes were not evaluated.",
            "No source was sorted, repaired, filled, relabeled or promoted.",
        ],
    }
    if len(intake._canonical(report)) > MAX_REPORT_BYTES:
        raise ValueError("Audit report exceeds metadata budget.")
    intake._publish(output_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register")
    register.add_argument("--plan", type=Path, required=True)
    run = commands.add_parser("audit")
    run.add_argument("--registration", type=Path, required=True)
    run.add_argument("--registration-sha256", required=True)
    run.add_argument("--directory", type=Path, required=True)
    for command in (register, run):
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "register":
        print(json.dumps({"registration_raw_sha256": register_audit(args.plan, args.output)}))
    else:
        result = audit_registered(
            args.registration, args.registration_sha256, args.directory, args.output
        )
        print(json.dumps({"status": result["status"], "training_started": False}))


if __name__ == "__main__":
    main()
