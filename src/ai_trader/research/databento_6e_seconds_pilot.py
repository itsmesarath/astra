"""Bounded, read-only 6EM5 seconds pilot on the already exposed March-April cohort.

The output is a futures quote counterfactual, not an order, fill, broker result,
or fresh out-of-sample test. It never imports a trading gateway or trainer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import zipfile
from collections import Counter, deque
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import databento_dbn as dbn

from ai_trader.research.databento_6e_scenario_replay import StrictBook
from ai_trader.research.databento_6e_training_data import (
    DAY_NS,
    SECOND_NS,
    TICK,
    _mapped_instrument,
    _member_records,
    _utc_ns,
    cme_session,
    selected_sources,
)

CONFIG_SHA256 = "f6b2bac411cbd5f794de5db64d98b2bb5ee7d030467b1afa2024391f53b8e79a"
CONFIG_V2_SHA256 = "9bae6c20c5c0740c758bfbb00485db3656f64481d390742a9cac22629292ea13"
ARTIFACT_TYPE = "databento_6e_seconds_quote_pilot_v1"
ARTIFACT_TYPE_V2 = "databento_6e_seconds_quote_pilot_v2"
SESSIONS = ("2025-03-31", "2025-04-01", "2025-04-02")
LATENCY_MS = (100, 500, 1000)
EXTRA_COST_TICKS = (0, 1, 2, 4)
GRID_NS = 5 * SECOND_NS
FLOW_NS = 5 * SECOND_NS
QUOTE_AGE_NS = 500_000_000
QUOTE_WAIT_NS = SECOND_NS
HOLD_NS = 15 * SECOND_NS
COOLDOWN_NS = 10 * SECOND_NS
GRIDS_PER_DAY = 4 * 60 * 60 // 5
MIN_FRESH_GRIDS_PER_DAY = 95 * GRIDS_PER_DAY // 100
MIN_FRESH_GRIDS_PER_DAY_V2 = 70 * GRIDS_PER_DAY // 100
MAX_PENDING_TRADE_RECORDS = 100_000
PROFILES = {
    CONFIG_SHA256: {
        "config_type": "databento_6e_seconds_pilot_config_v1",
        "experiment_id": "databento_6e_6em5_seconds_pilot_v1_20261001",
        "artifact_type": ARTIFACT_TYPE,
        "minimum_fraction": 0.95,
        "minimum_grids": MIN_FRESH_GRIDS_PER_DAY,
    },
    CONFIG_V2_SHA256: {
        "config_type": "databento_6e_seconds_pilot_config_v2",
        "experiment_id": "databento_6e_6em5_seconds_pilot_v2_20261001",
        "artifact_type": ARTIFACT_TYPE_V2,
        "minimum_fraction": 0.70,
        "minimum_grids": MIN_FRESH_GRIDS_PER_DAY_V2,
    },
}


@dataclass(frozen=True)
class Quote:
    ts_recv_ns: int
    bid: int
    ask: int
    bid_qty: int
    ask_qty: int

    @property
    def spread_ticks(self) -> int:
        return (self.ask - self.bid) // TICK


class FiveSecondFlow:
    """Known-side T records only; F records and unknown sides add no signed flow."""

    def __init__(self) -> None:
        self.events = deque()
        self.cvd = 0
        self.known = 0
        self.unknown = 0

    def expire(self, timestamp: int) -> None:
        cutoff = timestamp - FLOW_NS
        while self.events and self.events[0][0] < cutoff:
            _, signed, known, unknown = self.events.popleft()
            self.cvd -= signed
            self.known -= known
            self.unknown -= unknown

    def add(self, timestamp: int, event: dbn.MBOMsg) -> None:
        self.expire(timestamp)
        if str(event.action) != "T":
            return
        side = str(event.side)
        signed = event.size if side == "B" else -event.size if side == "A" else 0
        known = int(side in {"A", "B"})
        unknown = 1 - known
        self.events.append((timestamp, signed, known, unknown))
        self.cvd += signed
        self.known += known
        self.unknown += unknown


def load_config(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    profile = PROFILES.get(digest)
    if profile is None:
        raise ValueError("Seconds-pilot configuration SHA256 mismatch")
    config = json.loads(raw)
    if (
        config.get("artifact_type") != profile["config_type"]
        or config.get("experiment_id") != profile["experiment_id"]
        or config.get("mode") != "offline_research_only"
        or config.get("dataset") != "GLBX.MDP3"
        or config.get("schema") != "mbo"
        or config.get("contract") != "6EM5"
        or config.get("source_sessions") != list(SESSIONS)
        or config.get("exploratory_train_sessions") != list(SESSIONS[:2])
        or config.get("exposed_diagnostic_session") != SESSIONS[2]
        or config.get("decision_window_utc") != "12:00:00 inclusive through 16:00:00 exclusive"
        or config.get("grid_seconds") != 5
        or config.get("feature_window_seconds") != 5
        or config.get("maximum_decision_quote_age_ms") != 500
        or config.get("minimum_fresh_quote_grid_fraction_per_session")
        != profile["minimum_fraction"]
        or config.get("required_decision_spread_ticks") != 1
        or config.get("entry_latency_ms") != 100
        or config.get("latency_sensitivity_ms") != list(LATENCY_MS)
        or config.get("maximum_entry_or_exit_quote_wait_ms") != 1000
        or config.get("primary_holding_seconds") != 15
        or config.get("cooldown_seconds") != 10
        or config.get("extra_round_trip_cost_ticks") != list(EXTRA_COST_TICKS)
        or config.get("trading_enabled") is not False
        or config.get("training_enabled") is not False
        or config.get("broker_data_used") is not False
    ):
        raise ValueError("Seconds-pilot configuration differs from the implemented protocol")
    return config, digest


class SecondsPilot:
    """Stream a fixed grid; each grid uses only complete events strictly before it."""

    def __init__(
        self,
        sessions: tuple[str, ...] = SESSIONS,
        contract: str = "6EM5",
        minimum_fresh_grids_per_day: int = MIN_FRESH_GRIDS_PER_DAY,
        quote_warmup_ns: int = FLOW_NS,
    ):
        if not 1 <= minimum_fresh_grids_per_day <= GRIDS_PER_DAY:
            raise ValueError("Invalid per-day fresh quote coverage threshold")
        self.sessions = sessions
        self.session_set = set(sessions)
        self.contract = contract
        self.minimum_fresh_grids_per_day = minimum_fresh_grids_per_day
        self.quote_warmup_ns = quote_warmup_ns
        self.rows: list[dict] = []
        self.counts = Counter()
        self.trade_counts = Counter()
        self.day: date | None = None
        self.day_start_ns = 0
        self.day_end_ns = 0
        self.window_start_ns = 0
        self.window_end_ns = 0
        self.next_grid_ns = 0
        self.metadata_seen = False
        self.instrument_id: int | None = None
        self.last_recv_ns: int | None = None
        self.day_target_records = 0
        self.book = StrictBook()
        self.flow = FiveSecondFlow()
        self.pending_trade_records: list[dbn.MBOMsg] = []
        self.last_quote: Quote | None = None
        self.pending_rows: list[dict] = []
        self.active_row: dict | None = None
        self.cooldown_until_ns = 0
        self.episode_direction = 0
        self.episode_id = 0
        self.accepted_episode_id = 0
        self.window_closed = False

    def start_day(self, day: date) -> None:
        if (
            self.day is not None
            and not self.window_closed
            and self.day.isoformat() in self.session_set
        ):
            raise ValueError("Previous decision window was not closed")
        self.day = day
        self.day_start_ns = _utc_ns(day)
        self.day_end_ns = self.day_start_ns + DAY_NS
        self.window_start_ns = self.day_start_ns + 12 * 60 * 60 * SECOND_NS
        self.window_end_ns = self.day_start_ns + 16 * 60 * 60 * SECOND_NS
        self.next_grid_ns = self.window_start_ns
        self.metadata_seen = False
        self.instrument_id = None
        self.last_recv_ns = None
        self.day_target_records = 0
        self.book = StrictBook()
        self.flow = FiveSecondFlow()
        self.pending_trade_records = []
        self.last_quote = None
        self.pending_rows = []
        self.active_row = None
        self.cooldown_until_ns = 0
        self.episode_direction = 0
        self.episode_id = 0
        self.accepted_episode_id = 0
        self.window_closed = False

    def _quote_at_last(self, timestamp: int) -> Quote:
        bid, ask = self.book.best("B"), self.book.best("A")
        if bid is None or ask is None or bid >= ask:
            raise ValueError("Incomplete, locked, or crossed target book at F_LAST")
        bid_qty, ask_qty = self.book.levels["B"][bid], self.book.levels["A"][ask]
        if bid_qty <= 0 or ask_qty <= 0 or (ask - bid) % TICK:
            raise ValueError("Invalid target quantity or tick spread at F_LAST")
        return Quote(timestamp, bid, ask, bid_qty, ask_qty)

    def _advance_grids_before(self, timestamp: int) -> None:
        if self.day.isoformat() not in self.session_set or self.window_closed:
            return
        # A grid at t excludes records with receive time exactly t as well.
        while self.next_grid_ns <= timestamp and self.next_grid_ns < self.window_end_ns:
            self._decision(self.next_grid_ns)
            self.next_grid_ns += GRID_NS
        if timestamp >= self.window_end_ns:
            self._end_window()

    def _decision(self, grid_ns: int) -> None:
        self.flow.expire(grid_ns)
        session = self.day.isoformat()
        quote = self.last_quote
        age_ns = grid_ns - quote.ts_recv_ns if quote is not None else None
        cvd, known, unknown = self.flow.cvd, self.flow.known, self.flow.unknown
        reason = None
        direction = 0
        imbalance = None
        signal_fields = {}
        if quote is None or age_ns is None or not 0 < age_ns <= QUOTE_AGE_NS:
            reason = "stale_or_missing_completed_quote"
        else:
            self.counts["fresh_quote_grids"] += 1
            imbalance = (quote.bid_qty - quote.ask_qty) / (quote.bid_qty + quote.ask_qty)
            direction, reason, signal_fields = self._signal_at_grid(grid_ns, quote, imbalance)
        if known:
            self.counts["grids_with_known_side_trades"] += 1
        if unknown:
            self.counts["grids_with_unknown_side_trades"] += 1
        if direction == 0:
            self.episode_direction = 0
        elif direction != self.episode_direction:
            self.episode_direction = direction
            self.episode_id += 1
        row = {
            "source_session": session,
            "grid_ts_ns": grid_ns,
            "decision_quote_ts_ns": quote.ts_recv_ns if quote else None,
            "decision_quote_age_ns": age_ns,
            "decision_bid_nano": quote.bid if quote else None,
            "decision_ask_nano": quote.ask if quote else None,
            "decision_spread_ticks": quote.spread_ticks if quote else None,
            "top_bid_qty": quote.bid_qty if quote else None,
            "top_ask_qty": quote.ask_qty if quote else None,
            "queue_imbalance": imbalance,
            "cvd_known_side_5s": cvd,
            "known_side_trades_5s": known,
            "unknown_side_trades_5s": unknown,
            "signal_direction": direction,
            "episode_id": self.episode_id if direction else None,
            "policy_reason": reason,
            "selected_counterfactual": False,
            "latency_variants": {},
            **signal_fields,
        }
        self.rows.append(row)
        self.counts["decision_grids"] += 1
        if not direction:
            return
        self.counts["raw_signals"] += 1
        if self.active_row is not None:
            row["policy_reason"] = "entry_or_position_pending"
        elif grid_ns < self.cooldown_until_ns:
            row["policy_reason"] = "cooldown"
        elif self.accepted_episode_id == self.episode_id:
            row["policy_reason"] = "same_episode"
        elif grid_ns + LATENCY_MS[0] * 1_000_000 + HOLD_NS >= self.window_end_ns:
            row["policy_reason"] = "insufficient_window_for_hold"
        else:
            row["policy_reason"] = "selected"
            row["selected_counterfactual"] = True
            self.accepted_episode_id = self.episode_id
            self.active_row = row
            self.pending_rows.append(row)
            self.counts["selected_counterfactuals"] += 1
            for latency in LATENCY_MS:
                row["latency_variants"][str(latency)] = {
                    "status": "entry_pending",
                    "entry_target_ts_ns": grid_ns + latency * 1_000_000,
                    "entry_ts_ns": None,
                    "entry_bid_nano": None,
                    "entry_ask_nano": None,
                    "exit_target_ts_ns": None,
                    "exit_ts_ns": None,
                    "exit_bid_nano": None,
                    "exit_ask_nano": None,
                    "gross_crossed_quote_ticks": None,
                    "net_after_extra_cost_ticks": None,
                }

    def _signal_at_grid(self, grid_ns: int, quote: Quote, imbalance: float) -> tuple:
        """Extension point; the original pilot retains its frozen CVD rule."""
        if quote.spread_ticks != 1:
            return 0, "spread_not_one_tick", {}
        if self.flow.known == 0:
            return 0, "no_known_side_trades_5s", {}
        if self.flow.cvd == 0:
            return 0, "zero_known_side_cvd_5s", {}
        if imbalance == 0 or (self.flow.cvd > 0) != (imbalance > 0):
            return 0, "cvd_queue_sign_disagree_or_flat", {}
        return (1 if self.flow.cvd > 0 else -1), None, {}

    def _observe_completed_quote(self, quote: Quote) -> None:
        """Hook for causal features built only from completed exchange events."""

    def _process_quote(self, quote: Quote) -> None:
        still_pending = []
        for row in self.pending_rows:
            for variant in row["latency_variants"].values():
                if variant["status"] == "entry_pending":
                    target = variant["entry_target_ts_ns"]
                    if quote.ts_recv_ns < target:
                        continue
                    if quote.ts_recv_ns > target + QUOTE_WAIT_NS:
                        variant["status"] = "censored_entry_quote_timeout"
                    elif quote.spread_ticks != 1:
                        variant["status"] = "censored_entry_spread_widened"
                    else:
                        variant["entry_ts_ns"] = quote.ts_recv_ns
                        variant["entry_bid_nano"] = quote.bid
                        variant["entry_ask_nano"] = quote.ask
                        variant["exit_target_ts_ns"] = quote.ts_recv_ns + HOLD_NS
                        variant["status"] = "exit_pending"
                elif variant["status"] == "exit_pending":
                    target = variant["exit_target_ts_ns"]
                    if quote.ts_recv_ns < target:
                        continue
                    if quote.ts_recv_ns > target + QUOTE_WAIT_NS:
                        variant["status"] = "censored_exit_quote_timeout"
                    else:
                        variant["exit_ts_ns"] = quote.ts_recv_ns
                        variant["exit_bid_nano"] = quote.bid
                        variant["exit_ask_nano"] = quote.ask
                        gross = (
                            quote.bid - variant["entry_ask_nano"]
                            if row["signal_direction"] == 1
                            else variant["entry_bid_nano"] - quote.ask
                        ) / TICK
                        variant["gross_crossed_quote_ticks"] = gross
                        variant["net_after_extra_cost_ticks"] = {
                            str(cost): gross - cost for cost in EXTRA_COST_TICKS
                        }
                        variant["status"] = "resolved"
            primary = row["latency_variants"][str(LATENCY_MS[0])]
            if row is self.active_row and primary["status"] not in {
                "entry_pending",
                "exit_pending",
            }:
                self.active_row = None
                self.cooldown_until_ns = quote.ts_recv_ns + COOLDOWN_NS
            if any(
                variant["status"] in {"entry_pending", "exit_pending"}
                for variant in row["latency_variants"].values()
            ):
                still_pending.append(row)
        self.pending_rows = still_pending

    def _end_window(self) -> None:
        if self.window_closed:
            return
        while self.next_grid_ns < self.window_end_ns:
            self._decision(self.next_grid_ns)
            self.next_grid_ns += GRID_NS
        for row in self.pending_rows:
            for variant in row["latency_variants"].values():
                if variant["status"] in {"entry_pending", "exit_pending"}:
                    variant["status"] = "censored_window_end"
        self.pending_rows.clear()
        self.active_row = None
        self.window_closed = True

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
        if not self.day_start_ns <= recv < self.day_end_ns:
            raise ValueError("Target receive timestamp outside its daily file")
        action, side = str(item.action), str(item.side)
        snapshot = bool(item.flags & dbn.F_SNAPSHOT)
        if (
            snapshot
            and self.day.isoformat() in self.session_set
            and self.window_start_ns <= recv < self.window_end_ns
        ):
            raise ValueError("Unexpected target snapshot in decision window")
        accepted_closed_clear = (
            item.flags == dbn.F_BAD_TS_RECV
            and action == "R"
            and side == "N"
            and cme_session(recv) is None
            and not self.window_start_ns <= recv < self.window_end_ns
            and item.ts_event <= recv
        )
        bad = item.flags & (dbn.F_BAD_TS_RECV | dbn.F_MAYBE_BAD_BOOK | dbn.F_TOB | dbn.F_MBP)
        if snapshot:
            bad &= ~dbn.F_BAD_TS_RECV
        if bad and not accepted_closed_clear:
            raise ValueError("Target MBO has a bad timestamp or quality flag")
        if accepted_closed_clear:
            self.counts["accepted_closed_period_bad_ts_clears"] += 1
            if self.counts["accepted_closed_period_bad_ts_clears"] > 32:
                raise ValueError("Too many exceptional closed-period bad-timestamp clears")
        if self.pending_trade_records and (action == "R" or snapshot):
            raise ValueError("Incomplete target event before book reset or snapshot")
        if not snapshot and item.ts_event > recv:
            raise ValueError("Target exchange timestamp is later than receive timestamp")
        if not snapshot and not accepted_closed_clear:
            if self.last_recv_ns is not None and recv < self.last_recv_ns:
                raise ValueError("Target receive timestamp regressed")
            self._advance_grids_before(recv)
            self.last_recv_ns = recv
        if (
            action == "R"
            and not snapshot
            and self.day.isoformat() in self.session_set
            and self.window_start_ns <= recv < self.window_end_ns
        ):
            raise ValueError("Unexpected live book clear in decision window")
        self.book.apply(item)
        self.day_target_records += 1
        self.counts["target_records"] += 1
        if action == "R":
            self.flow = FiveSecondFlow()
            self.last_quote = None
            self.episode_direction = 0
            return
        if snapshot:
            self.counts["snapshot_records"] += 1
            if (
                item.flags & dbn.F_LAST
                and self.day.isoformat() in self.session_set
                and self.window_start_ns <= recv < self.window_end_ns
            ):
                self._quote_at_last(recv)
            return
        if action == "T":
            self.pending_trade_records.append(item)
            if len(self.pending_trade_records) > MAX_PENDING_TRADE_RECORDS:
                raise ValueError("Incomplete target event exceeds pending trade bound")
        if not item.flags & dbn.F_LAST:
            return
        # The match may span several MBO records and a decision grid. Signed flow
        # becomes observable only when the enclosing event completes at F_LAST.
        for trade in self.pending_trade_records:
            self.flow.add(recv, trade)
            if self.window_start_ns <= recv < self.window_end_ns:
                trade_side = str(trade.side)
                label = "known" if trade_side in {"A", "B"} else "unknown"
                self.trade_counts[(self.day.isoformat(), label)] += 1
        self.pending_trade_records.clear()
        if not self.book.initialized:
            return
        if self.day.isoformat() not in self.session_set:
            return
        if not self.window_start_ns - self.quote_warmup_ns <= recv < self.window_end_ns:
            return
        quote = self._quote_at_last(recv)
        self._observe_completed_quote(quote)
        self.last_quote = quote
        if recv >= self.window_start_ns:
            self._process_quote(quote)

    def finish_day(self) -> None:
        if not self.metadata_seen or self.day_target_records == 0:
            raise ValueError(f"Empty target contract in UTC day {self.day}")
        if self.pending_trade_records:
            raise ValueError("Incomplete target trade event at UTC member end")
        if self.day.isoformat() in self.session_set:
            self._end_window()
            day_rows = [row for row in self.rows if row["source_session"] == self.day.isoformat()]
            if len(day_rows) != GRIDS_PER_DAY:
                raise ValueError("Incomplete five-second decision grid")
            fresh = sum(
                row["decision_quote_age_ns"] is not None
                and 0 < row["decision_quote_age_ns"] <= QUOTE_AGE_NS
                for row in day_rows
            )
            if fresh < self.minimum_fresh_grids_per_day:
                raise ValueError(
                    "Decision quote coverage below frozen per-session minimum: "
                    f"session={self.day.isoformat()} fresh={fresh}/{GRIDS_PER_DAY} "
                    f"required={self.minimum_fresh_grids_per_day}"
                )
        else:
            self.window_closed = True

    def finish(self) -> tuple[list[dict], dict]:
        if self.pending_rows or self.active_row is not None:
            raise ValueError("Unfinished quote counterfactual")
        if len(self.rows) != len(self.sessions) * GRIDS_PER_DAY:
            raise ValueError("Missing source decision session")
        if tuple(dict.fromkeys(row["source_session"] for row in self.rows)) != self.sessions:
            raise ValueError("Unexpected decision session order")
        return self.rows, {
            **dict(self.counts),
            "trade_records_total": {
                "known_side_T": sum(
                    self.trade_counts[(session, "known")] for session in self.sessions
                ),
                "unknown_side_T": sum(
                    self.trade_counts[(session, "unknown")] for session in self.sessions
                ),
            },
            "trade_records_by_session": {
                session: {
                    "known_side_T": self.trade_counts[(session, "known")],
                    "unknown_side_T": self.trade_counts[(session, "unknown")],
                }
                for session in self.sessions
            },
        }


def _summary(rows: list[dict]) -> dict:
    reasons = Counter(row["policy_reason"] for row in rows)
    selected = [row for row in rows if row["selected_counterfactual"]]
    fresh = sum(
        row["decision_quote_age_ns"] is not None
        and 0 < row["decision_quote_age_ns"] <= QUOTE_AGE_NS
        for row in rows
    )
    primary_completed = sum(
        row["latency_variants"][str(LATENCY_MS[0])]["status"] == "resolved" for row in selected
    )
    variants = {}
    for latency in LATENCY_MS:
        key = str(latency)
        statuses = Counter(row["latency_variants"][key]["status"] for row in selected)
        complete = [
            row["latency_variants"][key]["gross_crossed_quote_ticks"]
            for row in selected
            if row["latency_variants"][key]["status"] == "resolved"
        ]
        variants[key] = {
            "statuses": dict(statuses),
            "resolved": len(complete),
            "positive_gross": sum(value > 0 for value in complete),
            "positive_gross_share": sum(value > 0 for value in complete) / len(complete)
            if complete
            else None,
            "mean_gross_crossed_quote_ticks": sum(complete) / len(complete) if complete else None,
            "median_gross_crossed_quote_ticks": statistics.median(complete) if complete else None,
            "mean_after_extra_cost_ticks": {
                str(cost): sum(value - cost for value in complete) / len(complete)
                if complete
                else None
                for cost in EXTRA_COST_TICKS
            },
        }
    return {
        "decision_grids": len(rows),
        "fresh_quote_grids": fresh,
        "fresh_quote_grid_fraction": fresh / len(rows) if rows else None,
        "grids_with_known_side_trades_5s": sum(row["known_side_trades_5s"] > 0 for row in rows),
        "grids_with_unknown_side_trades_5s": sum(row["unknown_side_trades_5s"] > 0 for row in rows),
        "raw_signal_grids": sum(row["signal_direction"] != 0 for row in rows),
        "raw_long_signal_grids": sum(row["signal_direction"] == 1 for row in rows),
        "raw_short_signal_grids": sum(row["signal_direction"] == -1 for row in rows),
        "distinct_signal_episodes": len(
            {
                (row["source_session"], row["episode_id"])
                for row in rows
                if row["episode_id"] is not None
            }
        ),
        "selected_counterfactuals": len(selected),
        "completed_primary_counterfactuals": primary_completed,
        "censored_primary_counterfactuals": len(selected) - primary_completed,
        "selected_long": sum(row["signal_direction"] == 1 for row in selected),
        "selected_short": sum(row["signal_direction"] == -1 for row in selected),
        "completed_primary_long": sum(
            row["signal_direction"] == 1
            and row["latency_variants"][str(LATENCY_MS[0])]["status"] == "resolved"
            for row in selected
        ),
        "completed_primary_short": sum(
            row["signal_direction"] == -1
            and row["latency_variants"][str(LATENCY_MS[0])]["status"] == "resolved"
            for row in selected
        ),
        "same_episode_skips": reasons["same_episode"],
        "cooldown_skips": reasons["cooldown"],
        "open_position_skips": reasons["entry_or_position_pending"],
        "policy_reasons": dict(reasons),
        "latency_ms": variants,
    }


def _publish(rows_output: Path, summary_output: Path, rows_raw: bytes, report: dict) -> None:
    if rows_output.resolve() == summary_output.resolve():
        raise ValueError("Rows and summary paths must differ")
    if rows_output.exists() or summary_output.exists():
        raise ValueError("Refusing to overwrite a seconds-pilot artifact")
    rows_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        with rows_output.open("xb") as output:
            created.append(rows_output)
            output.write(rows_raw)
        with summary_output.open("x", encoding="utf-8", newline="\n") as output:
            created.append(summary_output)
            json.dump(report, output, indent=2)
            output.write("\n")
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise


def run_pilot(
    *, project_root: Path, config_path: Path, rows_output: Path, summary_output: Path
) -> dict:
    """Replay only four pinned UTC members; write after all quality checks succeed."""
    project_root, config_path, rows_output, summary_output = map(
        Path, (project_root, config_path, rows_output, summary_output)
    )
    if (
        rows_output.resolve() == summary_output.resolve()
        or rows_output.exists()
        or summary_output.exists()
    ):
        raise ValueError("Refusing to overwrite a seconds-pilot artifact")
    config, config_sha = load_config(config_path)
    profile = PROFILES[config_sha]
    if config_sha == CONFIG_V2_SHA256 and (
        "v2" not in rows_output.name.lower() or "v2" not in summary_output.name.lower()
    ):
        raise ValueError("V2 seconds-pilot outputs require separate v2-named paths")
    _, sources, intake_sha = selected_sources(config, project_root)
    if tuple(source["day"].isoformat() for source in sources) != (
        "2025-03-30",
        *SESSIONS,
    ):
        raise ValueError("Unexpected UTC source days for seconds pilot")
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
    builder = SecondsPilot(minimum_fresh_grids_per_day=profile["minimum_grids"])
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
                raise ValueError("Source archive changed during seconds replay")
    finally:
        for archive in open_archives.values():
            archive.close()
    rows_raw = b"".join(
        (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode() for row in rows
    )
    report = {
        "schema_version": 1,
        "artifact_type": profile["artifact_type"],
        "experiment_id": config["experiment_id"],
        "mode": "offline_research_only",
        "evidence_status": "exploratory_inconclusive",
        "revision_basis": config.get("revision_basis"),
        "config_sha256": config_sha,
        "source_intake_report": config["source_intake_report"],
        "source_intake_sha256": intake_sha,
        "source_days": source_days,
        "rows_sha256": hashlib.sha256(rows_raw).hexdigest(),
        "source_sessions": list(SESSIONS),
        "split": {
            "exploratory_train": list(SESSIONS[:2]),
            "exposed_diagnostic": [SESSIONS[2]],
            "fresh_holdout": [],
        },
        "protocol": {
            "grid_seconds": 5,
            "grid_uses_records": "strictly before grid receive time and completed F_LAST only",
            "maximum_decision_quote_age_ms": 500,
            "minimum_fresh_quote_grid_fraction_per_session": profile["minimum_fraction"],
            "minimum_fresh_quote_grids_per_session": profile["minimum_grids"],
            "feature_window_seconds": 5,
            "trade_flow_availability": "T records enter 5s CVD at enclosing F_LAST completion time",
            "signal": "one-tick spread and matching nonzero known-side T CVD and top-queue signs",
            "episode": "one selected counterfactual per contiguous same-direction signal run",
            "primary_entry_latency_ms": 100,
            "latency_sensitivity_ms": list(LATENCY_MS),
            "latency_sensitivity_scope": (
                "Reprice the primary 100ms-selected decision schedule only; slower variants "
                "are not independent nonoverlapping portfolios."
            ),
            "entry_exit_quote_wait_ms": 1000,
            "hold_seconds_from_entry_quote": 15,
            "cooldown_seconds_after_primary_resolution": 10,
            "extra_round_trip_cost_ticks": list(EXTRA_COST_TICKS),
            "gross_crossed_quote": (
                "long later bid minus entry ask; short entry bid minus later ask"
            ),
        },
        "quality": quality,
        "all_sessions": {"trade_records": quality["trade_records_total"], **_summary(rows)},
        "by_session": [
            {
                "source_session": session,
                "trade_records": quality["trade_records_by_session"][session],
                **_summary([r for r in rows if r["source_session"] == session]),
            }
            for session in SESSIONS
        ],
        "limitations": [
            "All three original training days are exposed exploratory evidence; "
            "this is not fresh validation.",
            "Quote counterfactuals omit market-order depth, partial fills, and queue effects.",
            "Extra tick costs are assumptions, not verified exchange/broker commissions.",
            "Slower latency outcomes reuse the primary schedule and may overlap later "
            "primary selections.",
            "6E is CME futures; no cTrader EUR/USD broker quotes or fills were used.",
            "No training, order routing, paper trading, or live trading is connected.",
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
    report = run_pilot(
        project_root=args.project_root,
        config_path=args.config,
        rows_output=args.rows_output,
        summary_output=args.summary_output,
    )
    print(json.dumps({"artifact_type": report["artifact_type"], **report["all_sessions"]}))


if __name__ == "__main__":
    main()
