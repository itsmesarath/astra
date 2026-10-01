"""Read-only, research-only 6E quote and scenario registry for the original development days.

The v1 feature builder and model are intentionally untouched. This replay reads only
its eight original train and first two validation sessions, emits one row per UTC decision minute,
and never treats midpoint or crossed-quote changes as executable broker PnL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter, deque
from datetime import UTC, date, datetime
from pathlib import Path

import databento_dbn as dbn

from ai_trader.research.databento_6e_training_data import (
    MINUTE_NS,
    SECOND_NS,
    TICK,
    Book,
    _mapped_instrument,
    _member_records,
    _utc_minute,
    cme_session,
    load_frozen_config,
    selected_sources,
)

CONFIG_SHA256 = "927607008b24877f24c961da1aafc1bc151e0d4b8253a1627bd51699e48fb144"
EXPERIMENT_ID = "databento_6e_dev_scenarios_v2_20261001"
ARTIFACT_TYPE = "databento_6e_scenario_registry_v2"
PRIOR_MINUTES = 30
FLOW_SECONDS = 300
OUTCOME_SECONDS = 60
BREAKOUT_TICKS = 1
MAX_FAILURE_AGE_MINUTES = 5
DECISIONS_PER_SESSION = 240
MAX_ROWS = 10 * DECISIONS_PER_SESSION
CANDIDATES = (
    "initial_break_up",
    "initial_break_down",
    "failed_up_breakout",
    "failed_down_breakout",
)


class StrictBook(Book):
    """Reject an order modify that cannot be reconciled to an existing order."""

    def apply(self, event):
        if str(event.action) == "M" and event.order_id not in self.orders:
            raise ValueError("Unknown target order modify")
        super().apply(event)
        if self.errors:
            raise ValueError(f"Target order-book replay fault: {dict(self.errors)}")


class SignedFlow:
    """Bounded five-minute trade flow; unknown aggressors never get a sign."""

    def __init__(self):
        self.events = deque()
        self.cvd = 0
        self.known_trades = 0
        self.unknown_trades = 0

    def add(self, timestamp: int, event) -> None:
        self.expire(timestamp)
        if str(event.action) != "T":
            return
        side = str(event.side)
        signed = event.size if side == "B" else -event.size if side == "A" else 0
        known = int(side in {"A", "B"})
        unknown = 1 - known
        self.events.append((timestamp, signed, known, unknown))
        self.cvd += signed
        self.known_trades += known
        self.unknown_trades += unknown

    def expire(self, timestamp: int) -> None:
        cutoff = timestamp - FLOW_SECONDS * SECOND_NS
        while self.events and self.events[0][0] < cutoff:
            _, signed, known, unknown = self.events.popleft()
            self.cvd -= signed
            self.known_trades -= known
            self.unknown_trades -= unknown


class ScenarioBuilder:
    """One-pass causal minute registry with later, separate quote outcomes."""

    def __init__(self, sessions: tuple[str, ...], contract: str):
        self.sessions = sessions
        self.session_set = set(sessions)
        self.contract = contract
        self.rows: list[dict] = []
        self.pending = deque()
        self.counts = Counter()
        self.per_session = Counter()
        self.warmup_per_session = Counter()
        self.last_minute: dict[str, int] = {}
        self.day = None
        self.day_start_ns = None
        self.instrument_id = None
        self.metadata_seen = False
        self.day_target_records = 0
        self.last_recv = None
        self.book = StrictBook()
        self.flow = SignedFlow()
        self.history = deque()
        self.breakout: dict | None = None

    def start_day(self, day) -> None:
        if self.pending:
            raise ValueError("Unfinished prior-day outcomes")
        self.day = day
        self.day_start_ns = (
            int(datetime.combine(day, datetime.min.time(), UTC).timestamp()) * SECOND_NS
        )
        self.instrument_id = None
        self.metadata_seen = False
        self.day_target_records = 0
        self.last_recv = None
        self.book = StrictBook()
        self.flow = SignedFlow()
        self.history.clear()
        self.breakout = None

    def _censor_pending(self, reason: str) -> None:
        while self.pending:
            row = self.pending.popleft()
            row["outcome_status"] = reason
            self.counts[reason] += 1

    def _clear_state(self) -> None:
        self._censor_pending("censored_book_clear")
        self.flow = SignedFlow()
        self.history.clear()
        self.breakout = None
        self.counts["book_clears"] += 1

    @staticmethod
    def _in_observation_window(recv: int) -> bool:
        utc = datetime.fromtimestamp(recv // SECOND_NS, UTC)
        return (utc.hour == 11 and utc.minute >= 30) or 12 <= utc.hour < 16

    def _quote_at_last(self) -> tuple[int, int, int, int]:
        bid, ask = self.book.best("B"), self.book.best("A")
        if bid is None or ask is None or bid >= ask:
            raise ValueError("Incomplete, locked, or crossed target book at F_LAST")
        bid_qty, ask_qty = self.book.levels["B"][bid], self.book.levels["A"][ask]
        if bid_qty <= 0 or ask_qty <= 0 or (ask - bid) % TICK:
            raise ValueError("Invalid target best quantity or tick spread at F_LAST")
        return bid, ask, bid_qty, ask_qty

    def _classify(
        self, minute: int, mid_twice: int
    ) -> tuple[str, int, str | None, int | None, int | None, int, int | None, int | None]:
        while self.history and self.history[0][0] < minute - PRIOR_MINUTES:
            self.history.popleft()
        prior = [mid for _, mid in self.history]
        count = len(prior)
        high = max(prior) if prior else None
        low = min(prior) if prior else None
        previous = self.breakout
        if previous is not None and minute - previous["minute"] > MAX_FAILURE_AGE_MINUTES:
            self.breakout = previous = None
        boundary = previous["boundary"] if previous is not None else None
        age = minute - previous["minute"] if previous is not None else None
        if count < PRIOR_MINUTES:
            return "no_trade", 0, "insufficient_prior_minutes", high, low, count, boundary, age
        if previous is not None:
            if previous["direction"] == 1 and mid_twice <= previous["boundary"]:
                self.breakout = None
                return "failed_up_breakout", -1, None, high, low, count, boundary, age
            if previous["direction"] == -1 and mid_twice >= previous["boundary"]:
                self.breakout = None
                return "failed_down_breakout", 1, None, high, low, count, boundary, age
            return "no_trade", 0, "awaiting_reentry", high, low, count, boundary, age

        if mid_twice >= high + 2 * TICK * BREAKOUT_TICKS:
            self.breakout = {"direction": 1, "boundary": high, "minute": minute}
            return "initial_break_up", 1, None, high, low, count, high, 0
        if mid_twice <= low - 2 * TICK * BREAKOUT_TICKS:
            self.breakout = {"direction": -1, "boundary": low, "minute": minute}
            return "initial_break_down", -1, None, high, low, count, low, 0
        return "no_trade", 0, "inside_prior_range", high, low, count, None, None

    def _resolve(self, recv: int, session: str, bid: int, ask: int) -> None:
        mid_twice = bid + ask
        while (
            self.pending and self.pending[0]["decision_ts_ns"] + OUTCOME_SECONDS * SECOND_NS <= recv
        ):
            row = self.pending.popleft()
            if row["source_session"] != session:
                raise ValueError("Outcome would cross a CME session boundary")
            row["outcome_status"] = "resolved"
            row["outcome_ts_ns"] = recv
            row["future_bid_nano"] = bid
            row["future_ask_nano"] = ask
            row["future_mid_twice_nano"] = mid_twice
            direction = row["candidate_direction"]
            if direction:
                row["signed_mid_move_ticks"] = (
                    direction * (mid_twice - row["decision_mid_twice_nano"]) / (2 * TICK)
                )
                quote_move = (
                    bid - row["decision_ask_nano"]
                    if direction == 1
                    else row["decision_bid_nano"] - ask
                )
                row["gross_crossed_quote_ticks"] = quote_move / TICK
            self.counts["resolved_outcomes"] += 1

    def consume(self, item) -> None:
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
        if not self.day_start_ns <= recv < self.day_start_ns + 86_400 * SECOND_NS:
            raise ValueError("Target receive timestamp outside its daily file")
        action, side = str(item.action), str(item.side)
        accepted_closed_clear = (
            item.flags == dbn.F_BAD_TS_RECV
            and action == "R"
            and side == "N"
            and cme_session(recv) is None
            and _utc_minute(recv) is None
            and item.ts_event <= recv
        )
        bad = item.flags & (dbn.F_BAD_TS_RECV | dbn.F_MAYBE_BAD_BOOK | dbn.F_TOB | dbn.F_MBP)
        if item.flags & dbn.F_SNAPSHOT:
            # DBN's daily synthetic snapshot can carry a bad receive-time bit.
            # It cannot create a decision or supply signed flow.
            bad &= ~dbn.F_BAD_TS_RECV
        if bad and not accepted_closed_clear:
            raise ValueError("Target MBO has a bad timestamp or quality flag")
        if item.ts_event > recv and not item.flags & dbn.F_SNAPSHOT:
            raise ValueError("Target exchange timestamp is later than receive timestamp")
        if not item.flags & dbn.F_SNAPSHOT:
            if self.last_recv is not None and recv < self.last_recv:
                raise ValueError("Target receive timestamp regressed")
            self.last_recv = recv

        if (
            action == "R"
            and not item.flags & dbn.F_SNAPSHOT
            and cme_session(recv) in self.session_set
            and self._in_observation_window(recv)
        ):
            raise ValueError("Unexpected live book clear in the observation window")
        self.book.apply(item)
        self.counts["target_records"] += 1
        self.day_target_records += 1
        if action == "R":
            if accepted_closed_clear:
                if self.pending or self.counts["accepted_closed_period_bad_ts_clears"] >= 32:
                    raise ValueError("Closed-period bad-timestamp clear conflicts with audit bound")
                self.counts["accepted_closed_period_bad_ts_clears"] += 1
            self._clear_state()
            return
        if item.flags & dbn.F_SNAPSHOT:
            self.counts["snapshot_records"] += 1
            if (
                item.flags & dbn.F_LAST
                and cme_session(recv) in self.session_set
                and self._in_observation_window(recv)
            ):
                self._quote_at_last()
            return
        self.flow.add(recv, item)
        if not item.flags & dbn.F_LAST:
            return
        session = cme_session(recv)
        if session not in self.session_set:
            return
        minute_of_day = _utc_minute(recv)
        # Build thirty causal prior minute observations before the 12:00 decision window.
        if not self._in_observation_window(recv):
            return
        bid, ask, bid_qty, ask_qty = self._quote_at_last()

        minute = recv // MINUTE_NS
        if minute_of_day is not None:
            self._resolve(recv, session, bid, ask)
        if self.last_minute.get(session) == minute:
            return
        self.last_minute[session] = minute
        mid_twice = bid + ask
        if minute_of_day is not None:
            candidate, direction, reason, high, low, count, boundary, age = self._classify(
                minute, mid_twice
            )
            row = {
                "source_session": session,
                "decision_ts_ns": recv,
                "decision_minute_utc": minute_of_day,
                "contract": self.contract,
                "decision_bid_nano": bid,
                "decision_ask_nano": ask,
                "decision_mid_twice_nano": mid_twice,
                "decision_spread_ticks": (ask - bid) // TICK,
                "top_bid_qty": bid_qty,
                "top_ask_qty": ask_qty,
                "top_imbalance": (bid_qty - ask_qty) / (bid_qty + ask_qty),
                "cvd_5m_known_side": self.flow.cvd,
                "known_side_trades_5m": self.flow.known_trades,
                "unknown_side_trades_5m": self.flow.unknown_trades,
                "prior_30m_observations": count,
                "prior_30m_high_mid_twice_nano": high,
                "prior_30m_low_mid_twice_nano": low,
                "frozen_breakout_boundary_mid_twice_nano": boundary,
                "breakout_age_minutes": age,
                "candidate": candidate,
                "candidate_direction": direction,
                "no_trade_reason": reason,
                "outcome_status": "pending",
                "outcome_ts_ns": None,
                "future_bid_nano": None,
                "future_ask_nano": None,
                "future_mid_twice_nano": None,
                "signed_mid_move_ticks": None,
                "gross_crossed_quote_ticks": None,
            }
            self.rows.append(row)
            self.pending.append(row)
            self.per_session[session] += 1
            self.counts["decisions"] += 1
            self.counts[f"candidate_{candidate}"] += 1
            if self.per_session[session] > DECISIONS_PER_SESSION or len(self.rows) > MAX_ROWS:
                raise ValueError("Decision count exceeds the bounded minute budget")
        else:
            self.warmup_per_session[session] += 1
        self.history.append((minute, mid_twice))
        while self.history and self.history[0][0] < minute - PRIOR_MINUTES + 1:
            self.history.popleft()

    def finish_day(self) -> None:
        if not self.metadata_seen or self.day_target_records == 0:
            raise ValueError(f"Empty target contract in UTC day {self.day}")
        self._censor_pending("censored_no_quote_before_window_end")

    def finish(self) -> tuple[list[dict], dict]:
        if self.pending:
            raise ValueError("Unfinished forward outcomes")
        if any(self.per_session[session] != DECISIONS_PER_SESSION for session in self.sessions):
            raise ValueError("Every included session must contain exactly 240 decision minutes")
        if any(self.warmup_per_session[session] != PRIOR_MINUTES for session in self.sessions):
            raise ValueError("Every included session must contain all 30 warmup minutes")
        if tuple(dict.fromkeys(row["source_session"] for row in self.rows)) != self.sessions:
            raise ValueError("Development session inventory is incomplete or reordered")
        return self.rows, {
            **dict(self.counts),
            "rows_per_session": {session: self.per_session[session] for session in self.sessions},
            "warmup_minutes_per_session": {
                session: self.warmup_per_session[session] for session in self.sessions
            },
        }


def _metrics(rows: list[dict]) -> dict:
    result = {"decisions": len(rows), "candidates": {}}
    for name in CANDIDATES:
        selected = [row for row in rows if row["candidate"] == name]
        resolved = [row for row in selected if row["outcome_status"] == "resolved"]
        crossed = [row["gross_crossed_quote_ticks"] for row in resolved]
        signed_mid = [row["signed_mid_move_ticks"] for row in resolved]
        result["candidates"][name] = {
            "signals": len(selected),
            "coverage": len(selected) / len(rows) if rows else None,
            "resolved": len(resolved),
            "favorable_mid": sum(value > 0 for value in signed_mid),
            "adverse_mid": sum(value < 0 for value in signed_mid),
            "flat_mid": sum(value == 0 for value in signed_mid),
            "mean_signed_mid_ticks": sum(signed_mid) / len(signed_mid) if signed_mid else None,
            "mean_gross_crossed_quote_ticks": sum(crossed) / len(crossed) if crossed else None,
            "positive_gross_crossed_quote": sum(value > 0 for value in crossed),
        }
    return result


def _publish(rows_output: Path, summary_output: Path, rows_raw: bytes, report: dict) -> None:
    """Publish both files exclusively; clean only files created by this invocation on error."""
    rows_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        with rows_output.open("xb") as destination:
            created.append(rows_output)
            destination.write(rows_raw)
        with summary_output.open("x", encoding="utf-8", newline="\n") as destination:
            created.append(summary_output)
            json.dump(report, destination, indent=2)
            destination.write("\n")
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise


def replay_scenarios(
    *, project_root: Path, config_path: Path, rows_output: Path, summary_output: Path
) -> dict:
    """Replay only the pinned v1 training and validation source sessions."""
    project_root, config_path, rows_output, summary_output = map(
        Path, (project_root, config_path, rows_output, summary_output)
    )
    if (
        rows_output.resolve() == summary_output.resolve()
        or rows_output.exists()
        or summary_output.exists()
    ):
        raise ValueError("Refusing to overwrite a scenario artifact")
    config, config_sha = load_frozen_config(config_path, CONFIG_SHA256)
    included_validation = config["validation_sessions"][:2]
    sessions = tuple(config["train_sessions"] + included_validation)
    if (
        sessions != tuple(config["source_sessions"][:10])
        or len(config["train_sessions"]) != 8
        or len(config["validation_sessions"]) != 3
        or len(included_validation) != 2
        or set(sessions) & set(config["test_sessions"])
    ):
        raise ValueError("Only eight train and the first two validation sessions are allowed")
    restricted = dict(config)
    restricted["source_sessions"] = list(sessions)
    _, sources, intake_sha = selected_sources(restricted, project_root)
    last_allowed_utc_day = date.fromisoformat(included_validation[-1])
    if any(source["day"] > last_allowed_utc_day for source in sources):
        raise ValueError("Selected source day reaches beyond the bounded validation cohort")
    source_days = [
        {
            "utc_date": item["day"].isoformat(),
            "archive": item["archive"].name,
            "archive_sha256_from_intake": item["archive_sha256"],
            "member": item["name"],
            "member_sha256": item["sha256"],
        }
        for item in sources
    ]
    source_days_sha256 = hashlib.sha256(
        json.dumps(source_days, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    builder = ScenarioBuilder(sessions, config["contract"])
    open_archives = {}
    stamps = {}
    try:
        for source in sources:
            archive_path = source["archive"]
            if archive_path not in open_archives:
                open_archives[archive_path] = zipfile.ZipFile(archive_path)
                stat = archive_path.stat()
                stamps[archive_path] = (stat.st_size, stat.st_mtime_ns)
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

    rows_raw = b"".join(
        (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode() for row in rows
    )
    train = set(config["train_sessions"])
    validation = set(included_validation)
    report = {
        "schema_version": 2,
        "artifact_type": ARTIFACT_TYPE,
        "experiment_id": EXPERIMENT_ID,
        "mode": "offline_research_only",
        "config_sha256": config_sha,
        "source_intake_report": config["source_intake_report"],
        "source_intake_sha256": intake_sha,
        "source_days": source_days,
        "source_days_sha256": source_days_sha256,
        "session_split": {
            "train": list(config["train_sessions"]),
            "validation": list(included_validation),
            "omitted_original_validation": config["validation_sessions"][2:],
            "reserved_sources_read": 0,
        },
        "rules": {
            "decision_window_utc": "12:00 inclusive through 16:00 exclusive",
            "sampling": "first non-snapshot target-contract F_LAST in each UTC minute",
            "prior_range": (
                "midpoint high/low of all 30 prior UTC minute buckets in same CME session"
            ),
            "prior_minutes": PRIOR_MINUTES,
            "minimum_prior_observations": PRIOR_MINUTES,
            "required_decision_minutes_per_session": DECISIONS_PER_SESSION,
            "required_warmup_minutes_per_session": PRIOR_MINUTES,
            "breakout_minimum_ticks_beyond_range": BREAKOUT_TICKS,
            "initial_break": "first full-tick move beyond the known prior range, unconfirmed",
            "accepted_break_tested": False,
            "failed_breakout": "reentry to frozen pre-breakout boundary within five later minutes",
            "maximum_failure_age_minutes": MAX_FAILURE_AGE_MINUTES,
            "flow_window_seconds": FLOW_SECONDS,
            "flow_aggressor": "B adds trade size, A subtracts, unknown adds zero",
            "outcome": (
                "first clean F_LAST two-sided quote at or after decision plus 60s, before 16:00"
            ),
            "outcome_seconds": OUTCOME_SECONDS,
            "gross_crossed_quote_ticks": (
                "long: future bid minus decision ask; short: decision bid minus future ask"
            ),
        },
        "quality": quality,
        "rows": len(rows),
        "rows_sha256": hashlib.sha256(rows_raw).hexdigest(),
        "train": _metrics([row for row in rows if row["source_session"] in train]),
        "validation": _metrics([row for row in rows if row["source_session"] in validation]),
        "by_session": [
            {
                "source_session": session,
                "split": "train" if session in train else "validation",
                **_metrics([row for row in rows if row["source_session"] == session]),
            }
            for session in sessions
        ],
        "limitations": [
            "The two included validation sessions are development evidence, not an untouched test.",
            "Gross crossed-quote ticks exclude commissions, slippage, latency and fills.",
            "CME futures quotes are not cTrader spot/CFD broker quotes or executable PnL.",
            "Overlapping one-minute outcomes are dependent observations.",
            "No model is fitted and no paper or live trading is connected.",
        ],
    }
    _publish(rows_output, summary_output, rows_raw, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--rows-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    args = parser.parse_args()
    report = replay_scenarios(
        project_root=args.project_root,
        config_path=args.config,
        rows_output=args.rows_output,
        summary_output=args.summary_output,
    )
    print(
        json.dumps(
            {
                "experiment_id": report["experiment_id"],
                "rows": report["rows"],
                "rows_sha256": report["rows_sha256"],
                "reserved_sources_read": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
