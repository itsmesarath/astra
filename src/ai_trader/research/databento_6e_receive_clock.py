"""Opt-in receive-clock V2; preserve the frozen V1 engine and original records."""

from __future__ import annotations

from collections import Counter

import databento_dbn as dbn

from ai_trader.research import databento_6e_seconds_pilot as clock
from ai_trader.research import historical_6e_cohort as cohort
from ai_trader.research.databento_6e_seconds_pilot import (
    MAX_PENDING_TRADE_RECORDS,
    FiveSecondFlow,
)
from ai_trader.research.databento_6e_training_data import _mapped_instrument, cme_session


def policy() -> dict:
    return {
        "version": "receive_clock_v2",
        "causal_clock": "Original ts_recv and original equal-timestamp record order; F_LAST only",
        "protected_interval": "On selected days: [11:59:50,16:00) UTC, including full warmup",
        "disagreement": "Non-snapshot ts_event > ts_recv OR ts_in_delta < 0",
        "inside": "Any disagreement refuses the whole cohort before applying that record",
        "outside": "Audit disagreements, retain original records and apply normal book transitions",
        "undefined": "Undefined receive or non-snapshot event timestamp refuses the whole cohort",
        "snapshots": "Preserve original snapshot rules; synthetic clock fields not compared",
        "unchanged": "Receive ordering, daily bounds, bad flags, bounded closed-clear exception, "
        "book integrity, event completion, inactivity, entry/exit rules and costs",
        "forbidden": "No timestamp correction, sorting, filtering, fitted offsets or tolerances; "
        "outside-window labels or exchange-clock latency claims",
        "samples": "First eight disagreeing records per UTC member; no price or size fields",
    }


class ClockAudit:
    def __init__(self, day: str, protected: tuple[int, int] | None):
        self.day, self.protected = day, protected
        self.counts = Counter()
        self.samples = []
        self.min_event_ahead_ns = None
        self.max_event_ahead_ns = None
        self.min_send_delta_ns = None

    def observe(self, item, snapshot: bool) -> None:
        self.counts["target_records"] += 1
        if item.ts_recv == dbn.UNDEF_TIMESTAMP:
            raise ValueError("Undefined receive timestamp")
        if snapshot:
            self.counts["snapshots_not_clock_compared"] += 1
            return
        if item.ts_event == dbn.UNDEF_TIMESTAMP:
            raise ValueError("Undefined non-snapshot event timestamp")
        self.counts["non_snapshot_records"] += 1
        event_ahead = item.ts_event - item.ts_recv
        negative_send = item.ts_in_delta < 0
        self.counts["event_after_receive"] += event_ahead > 0
        self.counts["negative_send_delta"] += negative_send
        self.counts["event_after_sending"] += item.ts_event > item.ts_recv - item.ts_in_delta
        self.counts["clamped_send_delta"] += item.ts_in_delta in (-(2**31), 2**31 - 1)
        if event_ahead <= 0 and not negative_send:
            return
        self.counts["disagreement_records"] += 1
        protected = (
            self.protected is not None and self.protected[0] <= item.ts_recv < self.protected[1]
        )
        self.counts["protected_disagreements" if protected else "outside_disagreements"] += 1
        if event_ahead > 0:
            self.min_event_ahead_ns = (
                event_ahead
                if self.min_event_ahead_ns is None
                else min(self.min_event_ahead_ns, event_ahead)
            )
            self.max_event_ahead_ns = (
                event_ahead
                if self.max_event_ahead_ns is None
                else max(self.max_event_ahead_ns, event_ahead)
            )
        if negative_send:
            self.min_send_delta_ns = (
                item.ts_in_delta
                if self.min_send_delta_ns is None
                else min(self.min_send_delta_ns, item.ts_in_delta)
            )
        if len(self.samples) < 8:
            self.samples.append(
                {
                    "ts_event_ns": item.ts_event,
                    "ts_recv_ns": item.ts_recv,
                    "ts_in_delta_ns": item.ts_in_delta,
                    "flags": item.flags,
                    "sequence": item.sequence,
                    "action": str(item.action),
                    "protected": protected,
                }
            )
        if protected:
            raise ValueError("Cross-clock disagreement in protected research interval")

    def report(self) -> dict:
        return {
            "source_utc_date": self.day,
            "protected_interval_ns": list(self.protected) if self.protected is not None else None,
            "counts": dict(self.counts),
            "min_event_ahead_ns": self.min_event_ahead_ns,
            "max_event_ahead_ns": self.max_event_ahead_ns,
            "min_negative_send_delta_ns": self.min_send_delta_ns,
            "first_eight_disagreements": self.samples,
        }


class ReceiveClockCore(clock.SecondsPilot):
    """Frozen V1 consume body with only its cross-clock check replaced.

    The explicit C3 extension inserts this core immediately before SecondsPilot,
    preserving every existing event, feature and execution wrapper. An AST regression
    test verifies that no other consume behavior diverges from V1. Do not edit V1.
    """

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
        self.clock_audit.observe(item, snapshot)
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
        # Signed flow is observable only when the enclosing event completes at F_LAST.
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


class ReceiveTimeBuilder(cohort.DatedExecutionBuilder, ReceiveClockCore):
    """V2 quality policy only; no added features or changed target calculation."""

    def __init__(self, block: cohort.Block, minimum_resolved: int = 100):
        super().__init__(block, minimum_resolved)
        self.clock_quality = []

    def start_day(self, day) -> None:
        super().start_day(day)
        protected = (
            (self.window_start_ns - self.quote_warmup_ns, self.window_end_ns)
            if day.isoformat() in self.session_set
            else None
        )
        self.clock_audit = ClockAudit(day.isoformat(), protected)

    def finish_day(self) -> None:
        super().finish_day()
        if self.clock_audit.counts["target_records"] != self.day_target_records:
            raise ValueError("Clock audit did not cover every target record")
        self.clock_quality.append(self.clock_audit.report())

    def finish(self) -> tuple[list[dict], dict]:
        rows, quality = super().finish()
        quality["receive_clock_v2"] = self.clock_quality
        return rows, quality
