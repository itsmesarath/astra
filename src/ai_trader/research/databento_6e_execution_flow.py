"""Completed-event passive executions and conservative replenishment candidates.

Observes, but never changes, the strict book. T and F volume are separate views.
Unlinked decreases are not asserted to be cancellations; refresh is not proof
of hidden liquidity. No model, network or execution gateway is involved.
"""

from __future__ import annotations

import math
from collections import Counter, deque
from dataclasses import dataclass

import databento_dbn as dbn

from ai_trader.research import databento_6e_microdepth as data

clock = data.clock
WINDOW = clock.FLOW_NS
MAX_EVENT_RECORDS = 100_000
MAX_ROLLING_EVENTS = 100_000
MAX_CREDITS = 100_000
METRICS = (
    "passive",
    "held_top_passive",
    "linked_decrease",
    "unlinked_decrease",
    "same_id_reload",
    "other_id_reload",
    "same_id_net_refresh",
)
FEATURES = tuple(f"{side}_{metric}_5s" for side in ("bid", "ask") for metric in METRICS)


@dataclass(frozen=True)
class Record:
    recv: int
    action: str
    side: str
    price: int
    size: int
    oid: int
    before: tuple[str, int, int] | None

    @classmethod
    def capture(cls, message, book):
        return cls(
            message.ts_recv,
            str(message.action),
            str(message.side),
            message.price,
            message.size,
            message.order_id,
            book.orders.get(message.order_id),
        )


def match_fills(records: list[Record], audit: Counter) -> dict[int, Record]:
    """Link only a consecutive T/F group with a known passive side and resting ID."""
    approved, trade, used = {}, None, 0
    for index, r in enumerate(records):
        if r.action == "T":
            trade, used = r, 0
            if r.size <= 0 or r.price <= 0 or r.price % clock.TICK:
                raise ValueError("Invalid target trade quantity or price")
            audit[f"trade_{r.side}_volume"] += r.size
        elif r.action == "F":
            if r.size <= 0:
                raise ValueError("Invalid fill quantity")
            reason = (
                "without_trade"
                if trade is None
                else "unknown_aggressor"
                if trade.side not in {"A", "B"}
                else "aggressor"
                if r.oid == trade.oid or r.side == trade.side
                else "unknown_side"
                if r.side not in {"A", "B"}
                else "price_mismatch"
                if r.price != trade.price
                else "unmatched_book"
                if r.before is None or r.before[:2] != (r.side, r.price)
                else "matched_passive"
            )
            audit[f"fill_{reason}_records"] += 1
            audit[f"fill_{reason}_volume"] += r.size
            if reason == "matched_passive":
                used += r.size
                if used > trade.size:
                    raise ValueError("Matched passive fills exceed their trade summary")
                approved[index] = r
                audit["fill_above_displayed_volume"] += max(0, r.size - r.before[2])
        else:
            trade, used = None, 0
    return approved


class ExecutionWindow:
    """Rolling features published only after a full target event has completed."""

    def __init__(self):
        self.audit = Counter()
        self.last_ts = None
        self.events = deque()
        self.totals = Counter()
        self.credits = {"A": deque(), "B": deque()}

    def expire(self, now: int) -> None:
        cutoff = now - WINDOW
        while self.events and self.events[0][0] < cutoff:
            _, values = self.events.popleft()
            self.totals.subtract(values)
        for credit in self.credits.values():
            while credit and (credit[0][0] < cutoff or credit[0][2] == 0):
                credit.popleft()

    def _reset_temporal(self) -> None:
        self.events.clear()
        self.totals.clear()
        for credit in self.credits.values():
            credit.clear()

    def complete(self, records: list[Record], previous, quote, book) -> None:
        now = quote.ts_recv_ns
        if self.last_ts is not None and now < self.last_ts:
            raise ValueError("Execution feature clock regressed")
        if len(records) > MAX_EVENT_RECORDS or not records:
            raise ValueError("Invalid bounded execution event")
        if records[-1].recv != now or any(r.recv > now for r in records):
            raise ValueError("Execution event lies after its completion")
        if self.last_ts is None or now - self.last_ts > WINDOW:
            self._reset_temporal()
            previous = None
            self.audit["temporal_resets"] += 1
        self.last_ts = now
        self.expire(now)
        if now - records[0].recv > WINDOW:
            self.audit["stale_spanning_events_excluded"] += 1
            return
        fills = match_fills(records, self.audit)
        delta, remaining, first_fill, fill_totals = Counter(), Counter(), {}, Counter()
        modified, discontinuous = set(), set()
        stable = {
            "B": previous is not None and previous.bid == quote.bid,
            "A": previous is not None and previous.ask == quote.ask,
        }
        best = {"B": quote.bid, "A": quote.ask}
        for side in ("A", "B"):
            if not stable[side]:
                self.credits[side].clear()

        for index, r in enumerate(records):
            key = (r.oid, r.side, r.price)
            if index in fills:
                delta[(r.side, "passive")] += r.size
                if stable[r.side] and r.price == best[r.side]:
                    delta[(r.side, "held_top_passive")] += r.size
                remaining[key] += r.size
                fill_totals[key] += r.size
                first_fill.setdefault(key, r)
                continue
            if r.action not in {"A", "C", "M"}:
                continue
            old = r.before
            if r.action == "C":
                decrease, increase = r.size, 0
                if old is not None and r.size == old[2]:
                    discontinuous.add(r.oid)
            elif r.action == "M":
                if old is None:
                    raise ValueError("Execution observer saw unknown modify")
                if old[:2] == (r.side, r.price):
                    decrease, increase = max(0, old[2] - r.size), max(0, r.size - old[2])
                    # Only modifications after a matched fill can support net refresh.
                    if key in first_fill:
                        modified.add(key)
                else:
                    discontinuous.add(r.oid)
                    delta[(old[0], "unlinked_decrease")] += old[2]
                    decrease, increase = 0, r.size
            else:
                decrease, increase = 0, r.size
            linked = min(decrease, remaining[key])
            remaining[key] -= linked
            delta[(r.side, "linked_decrease")] += linked
            delta[(r.side, "unlinked_decrease")] += decrease - linked
            if not stable[r.side] or r.price != best[r.side]:
                continue
            credit = self.credits[r.side]
            if linked:
                if sum(len(c) for c in self.credits.values()) >= MAX_CREDITS:
                    raise ValueError("Execution credit bound exceeded")
                credit.append([now, r.oid, linked])
            while increase and credit:
                amount = min(increase, credit[0][2])
                category = "same_id_reload" if credit[0][1] == r.oid else "other_id_reload"
                delta[(r.side, category)] += amount
                increase -= amount
                credit[0][2] -= amount
                if credit[0][2] == 0:
                    credit.popleft()

        # Separate, overlapping candidate measure, never added to reload as hidden volume.
        for key in modified:
            oid, side, price = key
            final = book.orders.get(oid)
            if (
                oid in discontinuous
                or final is None
                or final[:2] != (side, price)
                or not stable[side]
                or price != best[side]
            ):
                continue
            initial = first_fill[key].before[2]
            executed = fill_totals[key]
            refill = min(executed, max(0, final[2] - max(0, initial - executed)))
            delta[(side, "same_id_net_refresh")] += refill
        delta = +delta
        if delta:
            if len(self.events) >= MAX_ROLLING_EVENTS:
                raise ValueError("Execution rolling event bound exceeded")
            self.events.append((now, delta))
            self.totals.update(delta)
            self.audit.update(
                {f"{side}_{metric}_volume": value for (side, metric), value in delta.items()}
            )
        self.audit["completed_events"] += 1

    def features(self, quote) -> dict[str, float]:
        self.expire(quote.ts_recv_ns)
        depth = quote.bid_qty + quote.ask_qty
        if depth <= 0:
            raise ValueError("Invalid normalization depth")
        values = {
            f"{name}_{metric}_5s": self.totals[(side, metric)] / depth
            for name, side in (("bid", "B"), ("ask", "A"))
            for metric in METRICS
        }
        if any(v < 0 or not math.isfinite(v) for v in values.values()):
            raise ValueError("Invalid execution feature")
        return values


class ExecutionBuilder(data.MicrodepthBuilder):
    """Supplement original features/targets; never feed future outcomes into features."""

    def __init__(self, sessions: tuple[str, ...], minimum_resolved: int = 100):
        super().__init__(sessions, minimum_resolved)
        self.execution_rows = {}
        self.execution_quality = []

    def start_day(self, day) -> None:
        super().start_day(day)
        self.execution = ExecutionWindow()
        self.event_records = []

    def consume(self, item) -> None:
        capture = (
            isinstance(item, dbn.MBOMsg)
            and item.instrument_id == self.instrument_id
            and self.day.isoformat() in self.session_set
            and self.window_start_ns - self.quote_warmup_ns <= item.ts_recv < self.window_end_ns
            and not item.flags & dbn.F_SNAPSHOT
        )
        if capture:
            if len(self.event_records) >= MAX_EVENT_RECORDS:
                raise ValueError("Execution event record bound exceeded")
            self.event_records.append(Record.capture(item, self.book))
        # Validation and book updates belong exclusively to the unchanged parent.
        super().consume(item)
        if isinstance(item, dbn.MBOMsg) and item.instrument_id == self.instrument_id:
            if (str(item.action) == "R" or item.flags & dbn.F_SNAPSHOT) and not self.window_closed:
                self.execution = ExecutionWindow()
                self.event_records.clear()
            elif item.flags & dbn.F_LAST:
                self.event_records.clear()

    def _observe_completed_quote(self, quote) -> None:
        previous = self.last_quote
        super()._observe_completed_quote(quote)
        self.execution.complete(self.event_records, previous, quote, self.book)

    def _event_decision(self, quote) -> None:
        super()._event_decision(quote)
        key = (self.day.isoformat(), quote.ts_recv_ns)
        self.execution_rows[key] = self.execution.features(quote)

    def finish_day(self) -> None:
        super().finish_day()
        if self.day.isoformat() in self.session_set:
            if self.event_records:
                raise ValueError("Unfinished execution event")
            self.execution_quality.append(
                {
                    "source_session": self.day.isoformat(),
                    "audit_including_warmup": dict(self.execution.audit),
                }
            )

    def finish(self) -> tuple[list[dict], dict]:
        rows, quality = super().finish()
        for row in rows:
            row["execution_features"] = self.execution_rows[
                (row["source_session"], row["decision_ts_ns"])
            ]
        quality["execution_flow"] = self.execution_quality
        return rows, quality
