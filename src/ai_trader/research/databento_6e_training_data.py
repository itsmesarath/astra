"""Build one bounded, offline 6E MBO research cohort from pinned local ZIPs.

Run in the isolated Databento pilot runtime. No network, account, collector,
training, or execution imports. A failed source or book gate publishes no rows.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import re
import zipfile
from collections import Counter, deque
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import databento_dbn as dbn
import zstandard as zstd

DAY_NS = 86_400_000_000_000
SECOND_NS = 1_000_000_000
MINUTE_NS = 60 * SECOND_NS
TICK = 50_000  # Databento fixed-point 1e-9 price units; CME 6E tick = 0.00005.
MAX_DECOMPRESSED_PER_DAY = 3 * 1024**3
MAX_SESSION_COUNT = 21
FEATURE_NAMES = (
    "spread_ticks",
    "top_bid_qty",
    "top_ask_qty",
    "imbalance",
    "cvd_rolling",
    "trade_count_rolling",
    "cancel_imbalance_rolling",
    "replenishment_proxy",
)
CONTRACT = re.compile(r"6E[FGHJKMNQUVXZ]\d\Z")
EXPECTED_ARTIFACT = "databento_6e_mbo_features_v1"


class Book:
    """Order-level outright book; CME T/F/N records do not mutate standing orders."""

    def __init__(self):
        self.orders = {}
        self.levels = {"A": {}, "B": {}}
        self.heaps = {"A": [], "B": []}
        self.queued = {"A": set(), "B": set()}
        self.initialized = False
        self.errors = Counter()

    def _change(self, side, price, quantity):
        levels = self.levels[side]
        updated = levels.get(price, 0) + quantity
        if updated < 0:
            raise ValueError("Negative reconstructed level quantity")
        if updated:
            levels[price] = updated
            if price not in self.queued[side]:
                heapq.heappush(self.heaps[side], -price if side == "B" else price)
                self.queued[side].add(price)
        else:
            levels.pop(price, None)

    def best(self, side):
        heap = self.heaps[side]
        while heap:
            price = -heap[0] if side == "B" else heap[0]
            if price in self.levels[side]:
                return price
            heapq.heappop(heap)
            self.queued[side].remove(price)
        return None

    def apply(self, event):
        action, side = str(event.action), str(event.side)
        if action == "R":
            self.orders.clear()
            for label in ("A", "B"):
                self.levels[label].clear()
                self.heaps[label].clear()
                self.queued[label].clear()
            self.initialized = True
            return
        if action in {"T", "F", "N"}:
            return
        if not self.initialized:
            self.errors["update_before_clear"] += 1
        if action not in {"A", "C", "M"} or side not in {"A", "B"}:
            self.errors["invalid_action_or_side"] += 1
            return
        if event.flags & (dbn.F_TOB | dbn.F_MBP):
            self.errors["unsupported_non_order_granularity"] += 1
            return
        price, size, oid = event.price, event.size, event.order_id
        if price == dbn.UNDEF_PRICE or size <= 0:
            self.errors["invalid_order_price_or_size"] += 1
            return
        previous = self.orders.get(oid)
        if action == "A" and previous is not None:
            self.errors["duplicate_add"] += 1
            return
        if action == "C":
            if previous is None:
                self.errors["cancel_unknown_order"] += 1
                return
            old_side, old_price, old_size = previous
            if (old_side, old_price) != (side, price) or size > old_size:
                self.errors["cancel_mismatch"] += 1
                return
            self._change(side, price, -size)
            if size == old_size:
                del self.orders[oid]
            else:
                self.orders[oid] = (side, price, old_size - size)
            return
        if previous is not None:
            old_side, old_price, old_size = previous
            if old_side != side:
                self.errors["modify_changed_side"] += 1
                return
            self._change(old_side, old_price, -old_size)
        self.orders[oid] = (side, price, size)
        self._change(side, price, size)


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _utc_ns(day: date) -> int:
    return int(datetime.combine(day, time(), UTC).timestamp()) * SECOND_NS


def _first_sunday(year: int, month: int) -> int:
    first = date(year, month, 1)
    return 1 + (6 - first.weekday()) % 7


def _chicago_offset_hours(utc: datetime) -> int:
    """US Central DST since 2007, with explicit UTC transition instants."""
    year = utc.year
    spring_day = _first_sunday(year, 3) + 7
    fall_day = _first_sunday(year, 11)
    spring = datetime(year, 3, spring_day, 8, tzinfo=UTC)
    fall = datetime(year, 11, fall_day, 7, tzinfo=UTC)
    return -5 if spring <= utc < fall else -6


def cme_session(ts_recv_ns: int) -> str | None:
    """Trading-date label for CME 17:00-16:00 CT, with the daily break closed."""
    utc = datetime.fromtimestamp(ts_recv_ns // SECOND_NS, UTC)
    local = utc + timedelta(hours=_chicago_offset_hours(utc))
    if 16 <= local.hour < 17:
        return None
    trading_day = local.date() + timedelta(days=local.hour >= 17)
    return trading_day.isoformat() if trading_day.weekday() < 5 else None


def _utc_minute(ts_recv_ns: int) -> int | None:
    utc = datetime.fromtimestamp(ts_recv_ns // SECOND_NS, UTC)
    return utc.hour * 60 + utc.minute if 12 <= utc.hour < 16 else None


def _session_list(config: dict) -> list[str]:
    sessions = config.get("source_sessions")
    if (
        type(sessions) is not list
        or not 3 <= len(sessions) <= MAX_SESSION_COUNT
        or any(type(value) is not str for value in sessions)
    ):
        raise ValueError("Expected 3-21 explicit CME source sessions")
    dates = [date.fromisoformat(value) for value in sessions]
    if any(day.weekday() >= 5 for day in dates):
        raise ValueError("A declared source session falls on a weekend")
    expected = [
        (dates[0] + timedelta(days=offset)).isoformat()
        for offset in range((dates[-1] - dates[0]).days + 1)
        if (dates[0] + timedelta(days=offset)).weekday() < 5
    ]
    if sessions != expected:
        raise ValueError("Source sessions must be complete, unique, chronological weekdays")
    return sessions


def load_frozen_config(path: Path, expected_sha256: str) -> tuple[dict, str]:
    actual = _sha256(path)
    if actual != expected_sha256:
        raise ValueError("Frozen experiment configuration SHA256 mismatch")
    config = json.loads(path.read_bytes())
    sessions = _session_list(config)
    contract = config.get("contract")
    if (
        config.get("dataset") != "GLBX.MDP3"
        or config.get("schema") != "mbo"
        or type(contract) is not str
        or not CONTRACT.fullmatch(contract)
        or config.get("feature_names") != list(FEATURE_NAMES)
        or config.get("decision_window_utc") != "12:00:00 inclusive through 16:00:00 exclusive"
        or config.get("sampling") != "First clean target-contract F_LAST event in each UTC minute"
        or config.get("rolling_flow_window_seconds") != 300
        or config.get("label_horizon_seconds") != 60
        or config.get("tick_size") != "0.00005"
        or config.get("source_intake_report") is None
        or config.get("source_intake_sha256") is None
        or config.get("train_sessions", [])
        + config.get("validation_sessions", [])
        + config.get("test_sessions", [])
        != sessions
    ):
        raise ValueError("Frozen experiment differs from the implemented feature/label protocol")
    return config, actual


def _needed_dates(sessions: list[str]) -> list[date]:
    start = date.fromisoformat(sessions[0]) - timedelta(days=1)
    end = date.fromisoformat(sessions[-1])
    return [
        start + timedelta(days=offset)
        for offset in range((end - start).days + 1)
        if (start + timedelta(days=offset)).weekday() != 5
    ]


def selected_sources(config: dict, project_root: Path) -> tuple[dict, list[dict], str]:
    intake_path = project_root / config["source_intake_report"]
    intake_sha = _sha256(intake_path)
    if intake_sha != config["source_intake_sha256"]:
        raise ValueError("Pinned archive intake report changed")
    intake = json.loads(intake_path.read_bytes())
    if (
        intake.get("status") != "integrity_and_headers_verified_event_quality_review_required"
        or len(intake.get("batches", [])) != 3
    ):
        raise ValueError("Intake evidence has not passed archive integrity and header checks")
    by_day = {}
    for batch in intake["batches"]:
        archive = Path(batch["archive"])
        if (
            archive.is_symlink()
            or not archive.is_file()
            or archive.stat().st_size != batch["archive_bytes"]
        ):
            raise ValueError("Pinned source archive is missing or has changed size")
        for member in batch["files"]:
            if "date" not in member:
                continue
            day = date.fromisoformat(member["date"])
            if day in by_day:
                raise ValueError("Duplicate source day in intake")
            by_day[day] = {
                "day": day,
                "archive": archive,
                "archive_sha256": batch["archive_sha256"],
                "name": member["filename"],
                "bytes": member["bytes"],
                "sha256": member["sha256"],
                "condition": member["condition"],
            }
    selected = []
    for day in _needed_dates(_session_list(config)):
        source = by_day.get(day)
        if source is None:
            raise ValueError(f"Missing source UTC day {day}")
        if source["condition"] != "available":
            raise ValueError(f"Source UTC day {day} is {source['condition']}; cohort held")
        selected.append(source)
    return intake, selected, intake_sha


def _mapped_instrument(metadata: dbn.Metadata, symbol: str, day: date) -> int:
    if (
        metadata.dataset != "GLBX.MDP3"
        or str(metadata.schema) != "mbo"
        or metadata.symbols != ["6E.FUT"]
        or metadata.not_found
        or metadata.start != _utc_ns(day)
        or metadata.end != _utc_ns(day + timedelta(days=1))
    ):
        raise ValueError(f"Invalid daily 6E MBO metadata for {day}")
    mappings = metadata.mappings.get(symbol, [])
    active = [item for item in mappings if item["start_date"] <= day < item["end_date"]]
    if len(active) != 1 or not str(active[0]["symbol"]).isdigit():
        raise ValueError(f"Invalid dated outright mapping for {symbol} on {day}")
    return int(active[0]["symbol"])


def _member_records(archive: zipfile.ZipFile, source: dict):
    """Decode complete concatenated Zstd frames and pin the compressed member."""
    info = archive.getinfo(source["name"])
    if info.file_size != source["bytes"]:
        raise ValueError("Source member length changed")
    digest = hashlib.sha256()
    decoder = dbn.DBNDecoder()
    decompressor = None
    decoded_total = 0
    with archive.open(info) as compressed:
        while block := compressed.read(64 * 1024):
            digest.update(block)
            while block:
                if decompressor is None:
                    decompressor = zstd.ZstdDecompressor().decompressobj()
                decoded = decompressor.decompress(block)
                decoded_total += len(decoded)
                if decoded_total > MAX_DECOMPRESSED_PER_DAY:
                    raise ValueError("Daily DBN exceeds decompressed byte bound")
                for offset in range(0, len(decoded), 1024 * 1024):
                    yield from decoder.write_and_decode(decoded[offset : offset + 1024 * 1024])
                if decompressor.eof:
                    block = decompressor.unused_data
                    decompressor = None
                else:
                    block = b""
    if decompressor is not None:
        raise ValueError("Incomplete Zstandard frame")
    yield from decoder.decode()
    if decoder.buffer():
        raise ValueError("Incomplete DBN metadata or record")
    if digest.hexdigest() != source["sha256"]:
        raise ValueError("Selected source member SHA256 differs from pinned intake")


class FlowWindow:
    def __init__(self):
        self.events = deque()
        self.sums = [0] * 6  # CVD, trades, ask cancels, bid cancels, best adds, volume.

    def add(self, timestamp: int, event: dbn.MBOMsg, best_before: int | None):
        action, side = str(event.action), str(event.side)
        values = [0] * 6
        if action == "T":
            values[0] = event.size if side == "B" else -event.size if side == "A" else 0
            values[1] = 1
            values[5] = event.size
        elif action == "C" and side in {"A", "B"}:
            values[2 if side == "A" else 3] = event.size
        elif action == "A" and side in {"A", "B"} and event.price == best_before:
            values[4] = event.size
        if any(values):
            self.events.append((timestamp, values))
            for index, value in enumerate(values):
                self.sums[index] += value

    def snapshot(self, timestamp: int) -> dict:
        cutoff = timestamp - 300 * SECOND_NS
        while self.events and self.events[0][0] < cutoff:
            _, values = self.events.popleft()
            for index, value in enumerate(values):
                self.sums[index] -= value
        cvd, trades, ask_cancel, bid_cancel, best_add, traded = self.sums
        cancel_total = ask_cancel + bid_cancel
        return {
            "cvd_rolling": cvd,
            "trade_count_rolling": trades,
            "cancel_imbalance_rolling": (
                (ask_cancel - bid_cancel) / cancel_total if cancel_total else 0.0
            ),
            # Observable best-price additions relative to traded quantity; no iceberg claim.
            "replenishment_proxy": best_add / (best_add + traded) if best_add + traded else 0.0,
        }


class CohortBuilder:
    def __init__(self, sessions: list[str], contract: str):
        self.sessions = sessions
        self.session_set = set(sessions)
        self.contract = contract
        self.book = Book()
        self.flow = FlowWindow()
        self.rows = []
        self.pending = deque()
        self.counts = Counter()
        self.per_session = Counter()
        self.last_minute = {}
        self.last_recv = None
        self.day = None
        self.instrument_id = None
        self.metadata_seen = False
        self.day_target_records = 0
        self.accepted_closed_period_clears = []

    def start_day(self, day: date):
        self.day = day
        self.instrument_id = None
        self.metadata_seen = False
        self.day_target_records = 0
        self.book = Book()
        self.flow = FlowWindow()
        self.last_recv = None

    def consume(self, item):
        if isinstance(item, dbn.Metadata):
            if self.metadata_seen:
                raise ValueError("Multiple metadata headers in one daily file")
            self.instrument_id = _mapped_instrument(item, self.contract, self.day)
            self.metadata_seen = True
            return
        if not self.metadata_seen or not isinstance(item, dbn.MBOMsg):
            raise ValueError("Missing metadata or unexpected non-MBO record")
        if item.instrument_id != self.instrument_id:
            return
        recv = item.ts_recv
        if not _utc_ns(self.day) <= recv < _utc_ns(self.day) + DAY_NS:
            raise ValueError("Target receive timestamp outside its daily file")
        accepted_closed_period_clear = False
        if not item.flags & dbn.F_SNAPSHOT:
            if self.last_recv is not None and recv < self.last_recv:
                raise ValueError("Target receive timestamp regressed")
            accepted_closed_period_clear = (
                item.flags == dbn.F_BAD_TS_RECV
                and str(item.action) == "R"
                and str(item.side) == "N"
                and cme_session(recv) is None
                and _utc_minute(recv) is None
                and item.ts_event <= recv
            )
            flagged = item.flags & (
                dbn.F_BAD_TS_RECV | dbn.F_MAYBE_BAD_BOOK | dbn.F_TOB | dbn.F_MBP
            )
            if flagged and not accepted_closed_period_clear:
                raise ValueError("Target MBO quality flag outside a snapshot")
            if item.ts_event > recv:
                raise ValueError("Target exchange timestamp is later than receive timestamp")
            self.last_recv = recv
        before = self.book.best(str(item.side)) if str(item.side) in {"A", "B"} else None
        errors_before = sum(self.book.errors.values())
        self.book.apply(item)
        if sum(self.book.errors.values()) != errors_before:
            raise ValueError(f"Target order-book replay fault: {dict(self.book.errors)}")
        self.counts["target_records"] += 1
        self.day_target_records += 1
        if accepted_closed_period_clear:
            if self.pending or len(self.accepted_closed_period_clears) >= 32:
                raise ValueError("Closed-period clear conflicts with label or audit bound")
            self.flow = FlowWindow()
            self.accepted_closed_period_clears.append(
                {
                    "utc_date": self.day.isoformat(),
                    "ts_recv_ns": recv,
                    "ts_recv_utc": datetime.fromtimestamp(recv // SECOND_NS, UTC).isoformat(),
                    "flags": int(item.flags),
                    "action": "R",
                    "side": "N",
                }
            )
            return
        if item.flags & dbn.F_SNAPSHOT:
            return
        self.flow.add(recv, item, before)
        if not item.flags & dbn.F_LAST or not self.book.initialized:
            return
        session = cme_session(recv)
        minute = _utc_minute(recv)
        if session not in self.session_set or minute is None:
            return
        bid, ask = self.book.best("B"), self.book.best("A")
        if bid is None or ask is None or bid >= ask:
            raise ValueError(f"Locked, crossed, or one-sided target book in {session}")
        bid_qty, ask_qty = self.book.levels["B"][bid], self.book.levels["A"][ask]
        if bid_qty <= 0 or ask_qty <= 0 or (ask - bid) % TICK:
            raise ValueError("Invalid target best-price quantity or tick spread")
        mid_twice = bid + ask
        while self.pending and self.pending[0]["decision_ts_ns"] + 60 * SECOND_NS <= recv:
            row = self.pending.popleft()
            if row["source_session"] != session:
                raise ValueError("Forward label would cross a CME session boundary")
            difference_twice = mid_twice - row.pop("_mid_twice")
            row["label_end_ts_ns"] = recv
            row["label"] = (
                1 if difference_twice >= 2 * TICK else -1 if difference_twice <= -2 * TICK else 0
            )
            self.rows.append(row)
            self.counts["resolved_labels"] += 1
        if self.last_minute.get(session) == minute:
            return
        self.last_minute[session] = minute
        self.per_session[session] += 1
        if self.per_session[session] > 240:
            raise ValueError("Decision count exceeds four-hour minute budget")
        features = self.flow.snapshot(recv)
        denominator = bid_qty + ask_qty
        row = {
            "source_session": session,
            "decision_ts_ns": recv,
            "label_end_ts_ns": None,
            "contract": self.contract,
            "spread_ticks": (ask - bid) // TICK,
            "top_bid_qty": bid_qty,
            "top_ask_qty": ask_qty,
            "imbalance": (bid_qty - ask_qty) / denominator,
            **features,
            "label": None,
            "_mid_twice": mid_twice,
        }
        self.pending.append(row)
        self.counts["decisions"] += 1

    def finish_day(self):
        if not self.metadata_seen or self.day_target_records == 0:
            raise ValueError(f"Empty target contract in UTC day {self.day}")
        for row in self.pending:
            if _utc_minute(row["decision_ts_ns"]) != 15 * 60 + 59:
                raise ValueError("An earlier decision has no within-window forward outcome")
        self.counts["unresolved_final_minute"] += len(self.pending)
        self.pending.clear()

    def finish(self) -> tuple[list[dict], dict]:
        if self.pending:
            raise ValueError("Unfinished daily forward labels")
        observed = [session for session in self.sessions if self.per_session[session] > 0]
        labeled = {session: 0 for session in self.sessions}
        for row in self.rows:
            labeled[row["source_session"]] += 1
        if observed != self.sessions or any(count == 0 for count in labeled.values()):
            raise ValueError("Exact session inventory or per-session labels incomplete")
        if any(
            left["source_session"] > right["source_session"]
            or left["decision_ts_ns"] >= right["decision_ts_ns"]
            for left, right in zip(self.rows, self.rows[1:], strict=False)
        ):
            raise ValueError("Feature rows are not strictly chronological")
        return self.rows, {
            "counts": dict(self.counts),
            "rows_per_session": labeled,
            "accepted_closed_period_bad_ts_clears": self.accepted_closed_period_clears,
        }


def build_cohort(config: dict, config_sha: str, project_root: Path) -> tuple[list[dict], dict]:
    sessions = _session_list(config)
    _, sources, intake_sha = selected_sources(config, project_root)
    builder = CohortBuilder(sessions, config["contract"])
    open_archives = {}
    stamps = {}
    try:
        for source in sources:
            archive_path = source["archive"]
            if archive_path not in open_archives:
                open_archives[archive_path] = zipfile.ZipFile(archive_path)
                stat = archive_path.stat()
                stamps[archive_path] = (stat.st_size, stat.st_mtime_ns)
            print(f"Replaying {source['name']} ({source['condition']})", flush=True)
            builder.start_day(source["day"])
            for record in _member_records(open_archives[archive_path], source):
                builder.consume(record)
            builder.finish_day()
        rows, quality = builder.finish()
        for archive_path, original in stamps.items():
            stat = archive_path.stat()
            if (stat.st_size, stat.st_mtime_ns) != original:
                raise ValueError("Source archive changed during replay")
    finally:
        for archive in open_archives.values():
            archive.close()
    source = {
        "intake_report": config["source_intake_report"],
        "intake_sha256": intake_sha,
        "experiment_config_sha256": config_sha,
        "members": [
            {
                "utc_date": item["day"].isoformat(),
                "archive": item["archive"].name,
                "archive_sha256_from_intake": item["archive_sha256"],
                "member": item["name"],
                "member_sha256_verified_during_replay": item["sha256"],
            }
            for item in sources
        ],
    }
    return rows, {"source": source, "quality": quality}


def publish(rows: list[dict], evidence: dict, config: dict, rows_path: Path, manifest_path: Path):
    if rows_path == manifest_path or rows_path.exists() or manifest_path.exists():
        raise ValueError("Refusing to overwrite a research artifact")
    lines = [json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows]
    raw = "".join(lines).encode("utf-8")
    manifest = {
        "schema_version": 1,
        "artifact_type": EXPECTED_ARTIFACT,
        "experiment_id": config["experiment_id"],
        "config_sha256": evidence["source"]["experiment_config_sha256"],
        "feature_names": list(FEATURE_NAMES),
        "rows_sha256": hashlib.sha256(raw).hexdigest(),
        "rows": len(rows),
        "contract": config["contract"],
        "first_session": config["source_sessions"][0],
        "last_session": config["source_sessions"][-1],
        "sessions": config["source_sessions"],
        "quality_passed": True,
        "held_dates": [],
        "source": evidence["source"],
        "quality": evidence["quality"],
        "mode": "offline_research_only",
    }
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with rows_path.open("xb") as output:
        output.write(raw)
    with manifest_path.open("x", encoding="utf-8") as output:
        json.dump(manifest, output, indent=2)
        output.write("\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--rows-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    args = parser.parse_args()
    config, config_sha = load_frozen_config(args.config, args.config_sha256)
    rows, evidence = build_cohort(config, config_sha, args.project_root)
    manifest = publish(rows, evidence, config, args.rows_output, args.manifest_output)
    print(
        json.dumps(
            {
                "rows": manifest["rows"],
                "sessions": len(manifest["sessions"]),
                "rows_sha256": manifest["rows_sha256"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
