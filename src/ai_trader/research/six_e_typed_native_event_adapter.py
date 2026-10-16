"""Reconstruct invented typed events without native or source authority.

No reader, decoder, account, model or I/O hook exists at this boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, deque
from dataclasses import dataclass
from functools import wraps

from ai_trader.research import six_e_native_cursor_metadata as cursor
from ai_trader.research import six_e_record_payload_binding as binding


@dataclass(frozen=True, slots=True)
class AdapterContext:
    input_version: int
    upgrade_policy: str
    yielded_version: int
    stype_in: str
    stype_out: str
    partial: tuple
    limit: None
    ts_out: bool


@dataclass(frozen=True, slots=True)
class AdapterFixture:
    context: AdapterContext
    payload_bundle: binding.PayloadBundle


@dataclass(frozen=True, slots=True)
class OrderState:
    side: str
    price: int
    size: int


@dataclass(frozen=True, slots=True)
class OrderEntry:
    order_id: int
    state: OrderState


@dataclass(frozen=True, slots=True)
class PriceLevel:
    price: int
    size: int


@dataclass(frozen=True, slots=True)
class AdapterAudit:
    decoded_position: int
    disposition: str
    instrument_id: int | None
    target_candidate_ordinal: int | None
    target_transition_ordinal: int | None
    binding_prefix_sha256: str
    adapter_prefix_sha256: str


@dataclass(frozen=True, slots=True)
class TargetTransition:
    decoded_position: int
    target_transition_ordinal: int
    disposition: str
    snapshot: bool
    exceptional_closed_clear: bool
    order_id: int
    before: OrderState | None
    after: OrderState | None
    initialized_before: bool
    initialized_after: bool
    last_recv_before: int | None
    last_recv_after: int | None
    event_ordinal: int | None
    quote_ordinal: int | None
    publication_ordinal: int | None
    state_sha256: str


@dataclass(frozen=True, slots=True)
class EventWitness:
    event_ordinal: int
    closing_decoded_position: int
    closing_target_transition_ordinal: int
    ts_recv_ns: int
    target_positions: tuple[int, ...]
    trade_positions: tuple[int, ...]
    execution_capture_positions: tuple[int, ...]
    quote_ordinal: int | None
    adapter_prefix_sha256: str
    event_sha256: str


@dataclass(frozen=True, slots=True)
class QuoteWitness:
    quote_ordinal: int
    event_ordinal: int
    decoded_position: int
    ts_recv_ns: int
    bid: int
    ask: int
    bid_qty: int
    ask_qty: int
    prior_quote_gap_ns: int
    ofi_generation: int
    bid_depth5: tuple[PriceLevel, ...]
    ask_depth5: tuple[PriceLevel, ...]
    adapter_prefix_sha256: str
    quote_sha256: str


@dataclass(frozen=True, slots=True)
class InactivityInterval:
    start_ns: int
    timer_fired_ns: int
    end_ns: int
    recovered: bool
    trigger_decoded_position: int | None


@dataclass(frozen=True, slots=True)
class FeaturePublication:
    publication_ordinal: int
    quote_ordinal: int
    event_ordinal: int
    decoded_position: int
    ts_recv_ns: int
    adapter_prefix_sha256: str
    features: tuple[tuple[str, float | int], ...]
    publication_sha256: str


@dataclass(frozen=True, slots=True)
class ClockSample:
    decoded_position: int
    ts_recv: int
    ts_event: int
    ts_in_delta: int
    flags: int
    sequence: int
    action: str
    protected: bool
    event_ahead_ns: int
    sending_ns: int


@dataclass(frozen=True, slots=True)
class ClockQuality:
    target_records: int
    snapshot_records: int
    non_snapshot_records: int
    event_after_receive: int
    negative_send_delta: int
    event_after_sending: int
    clamped_delta: int
    clock_disagreement_records: int
    protected_disagreement_records: int
    outside_disagreement_records: int
    min_event_ahead_ns: int | None
    max_event_ahead_ns: int | None
    min_negative_delta_ns: int | None
    samples: tuple[ClockSample, ...]


@dataclass(frozen=True, slots=True)
class ReconstructedState:
    initialized: bool
    orders: tuple[OrderEntry, ...]
    bid_levels: tuple[PriceLevel, ...]
    ask_levels: tuple[PriceLevel, ...]
    last_recv_ns: int | None
    pending_target_positions: tuple[int, ...]
    pending_trade_positions: tuple[int, ...]
    execution_capture_positions: tuple[int, ...]
    last_quote_ordinal: int | None
    flow_events: tuple
    cvd: int
    known_trades: int
    unknown_trades: int
    ofi_generation: int
    ofi_previous_quote_ordinal: int | None
    ofi_first_ts_ns: int | None
    ofi_events: tuple
    ofi_total: int
    history_ofi_generation: int | None
    history_quote_ordinals: tuple[int, ...]
    bid_depletions: tuple
    ask_depletions: tuple
    history_reloads: tuple
    execution_last_ts_ns: int | None
    execution_events: tuple
    execution_totals: tuple
    bid_credits: tuple
    ask_credits: tuple
    execution_audit: tuple
    next_publication_ns: int
    watch_since_ns: int
    inactivity_start_ns: int | None
    window_closed: bool


@dataclass(frozen=True, slots=True)
class AdapterAssessment:
    status: str
    protocol_sha256: str
    context_sha256: str
    binding_protocol_sha256: str
    cursor_protocol_sha256: str
    fixture_sha256: str
    fixture: AdapterFixture
    binding_assessment: binding.BindingAssessment
    audits: tuple[AdapterAudit, ...]
    transitions: tuple[TargetTransition, ...]
    events: tuple[EventWitness, ...]
    quotes: tuple[QuoteWitness, ...]
    publications: tuple[FeaturePublication, ...]
    inactivity_intervals: tuple[InactivityInterval, ...]
    clock_quality: ClockQuality
    exceptional_clear_count: int
    terminal_state: ReconstructedState
    authority_flags: tuple[tuple[str, bool], ...]
    assessment_sha256: str


def _guard(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, TypeError, AttributeError, OverflowError) as exc:
            raise ValueError("Malformed complete constructed typed adapter") from exc

    return checked


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _pins(*values):
    valid = [
        type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None for value in values
    ]
    _require(all(valid), "Exact lowercase SHA256 pins required")


def _context_body(context):
    _require(type(context) is AdapterContext, "Exact AdapterContext required")
    _require(
        type(context.input_version) is int and context.input_version == 3,
        "Exact input version required",
    )
    _require(
        type(context.upgrade_policy) is str and context.upgrade_policy == "AS_IS",
        "Exact upgrade policy required",
    )
    _require(
        type(context.yielded_version) is int and context.yielded_version == 3,
        "Exact yielded version required",
    )
    _require(
        type(context.stype_in) is str and context.stype_in == "parent",
        "Exact input symbology required",
    )
    _require(
        type(context.stype_out) is str and context.stype_out == "instrument_id",
        "Exact output symbology required",
    )
    _require(
        type(context.partial) is tuple and context.partial == (),
        "Empty exact partial tuple required",
    )
    _require(
        context.limit is None and type(context.ts_out) is bool,
        "Explicit None limit and exact ts_out bool required",
    )
    return {
        "input_version": context.input_version,
        "upgrade_policy": context.upgrade_policy,
        "yielded_version": context.yielded_version,
        "stype_in": context.stype_in,
        "stype_out": context.stype_out,
        "partial": [],
        "limit": None,
        "ts_out": context.ts_out,
    }


def _expected_protocols(protocol_pin, binding_pin, cursor_pin):
    _require(protocol_pin == protocol_sha256(), "Adapter protocol differs")
    _require(binding_pin == binding.protocol_sha256(), "Binding protocol differs")
    _require(cursor_pin == cursor.protocol_sha256(), "Cursor protocol differs")


class _Book:
    """Local strict standing-order reconstruction; T/F/N do not mutate it."""

    def __init__(self):
        self.initialized = False
        self.orders = {}
        self.levels = {"A": {}, "B": {}}

    def _change(self, side, price, quantity):
        updated = self.levels[side].get(price, 0) + quantity
        _require(updated >= 0, "Negative aggregate level quantity")
        if updated:
            self.levels[side][price] = updated
        else:
            self.levels[side].pop(price, None)

    def best(self, side):
        _require(side in ("A", "B"), "Standing side required")
        levels = self.levels[side]
        if not levels:
            return None
        return max(levels) if side == "B" else min(levels)

    def apply(self, payload):
        action, side = payload.action, payload.side
        if action == "R":
            self.orders.clear()
            self.levels["A"].clear()
            self.levels["B"].clear()
            self.initialized = True
            return
        if action in ("T", "F", "N"):
            return
        _require(self.initialized, "Order update before clear")
        _require(
            action in ("A", "C", "M") and side in ("A", "B"), "Unsupported standing action or side"
        )
        _require(not payload.flags & (64 | 16), "Unsupported non-order granularity")
        price, size, oid = payload.price, payload.size, payload.order_id
        _require(price != 9_223_372_036_854_775_807 and size > 0, "Invalid standing price or size")
        previous = self.orders.get(oid)
        if action == "A":
            _require(previous is None, "Duplicate order add")
        elif action == "C":
            _require(previous is not None, "Cancel of unknown order")
            _require(
                (previous.side, previous.price) == (side, price) and size <= previous.size,
                "Cancel mismatch or excessive size",
            )
            self._change(side, price, -size)
            if size == previous.size:
                del self.orders[oid]
            else:
                self.orders[oid] = OrderState(side, price, previous.size - size)
            return
        else:
            _require(previous is not None, "Modify of unknown order")
            _require(previous.side == side, "Modify changes standing side")
            self._change(previous.side, previous.price, -previous.size)
        self.orders[oid] = OrderState(side, price, size)
        self._change(side, price, size)
        _require(len(self.orders) <= 127, "Constructed standing order bound exceeded")


class _ClockAudit:
    """Preserve the inspected receive-clock arithmetic, not native authority."""

    def __init__(self):
        self.counts = Counter()
        self.samples = []
        self.min_event_ahead_ns = None
        self.max_event_ahead_ns = None
        self.min_negative_delta_ns = None

    def observe(self, payload, snapshot, decoded_position):
        self.counts["target_records"] += 1
        _require(payload.ts_recv != 18_446_744_073_709_551_615, "Undefined receive timestamp")
        if snapshot:
            self.counts["snapshot_records"] += 1
            return
        _require(
            payload.ts_event != 18_446_744_073_709_551_615, "Undefined non-snapshot event timestamp"
        )
        self.counts["non_snapshot_records"] += 1
        event_ahead = payload.ts_event - payload.ts_recv
        negative_delta = payload.ts_in_delta < 0
        self.counts["event_after_receive"] += event_ahead > 0
        self.counts["negative_send_delta"] += negative_delta
        self.counts["event_after_sending"] += (
            payload.ts_event > payload.ts_recv - payload.ts_in_delta
        )
        self.counts["clamped_delta"] += payload.ts_in_delta in (-(2**31), 2**31 - 1)
        if event_ahead <= 0 and not negative_delta:
            return
        self.counts["clock_disagreement_records"] += 1
        protected = 1_744_027_190_000_000_000 <= payload.ts_recv < 1_744_041_600_000_000_000
        self.counts[
            "protected_disagreement_records" if protected else "outside_disagreement_records"
        ] += 1
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
        if negative_delta:
            self.min_negative_delta_ns = (
                payload.ts_in_delta
                if self.min_negative_delta_ns is None
                else min(self.min_negative_delta_ns, payload.ts_in_delta)
            )
        if len(self.samples) < 8:
            self.samples.append(
                ClockSample(
                    decoded_position,
                    payload.ts_recv,
                    payload.ts_event,
                    payload.ts_in_delta,
                    payload.flags,
                    payload.sequence,
                    payload.action,
                    protected,
                    event_ahead,
                    payload.ts_recv - payload.ts_in_delta,
                )
            )
        _require(not protected, "Cross-clock disagreement in protected observation interval")

    def quality(self):
        return ClockQuality(
            self.counts["target_records"],
            self.counts["snapshot_records"],
            self.counts["non_snapshot_records"],
            self.counts["event_after_receive"],
            self.counts["negative_send_delta"],
            self.counts["event_after_sending"],
            self.counts["clamped_delta"],
            self.counts["clock_disagreement_records"],
            self.counts["protected_disagreement_records"],
            self.counts["outside_disagreement_records"],
            self.min_event_ahead_ns,
            self.max_event_ahead_ns,
            self.min_negative_delta_ns,
            tuple(self.samples),
        )


class _Flow:
    """Known-side trade summaries acquire the enclosing completion clock."""

    def __init__(self):
        self.events = deque()
        self.cvd = self.known = self.unknown = 0

    def expire(self, timestamp):
        while self.events and self.events[0][0] < timestamp - 5_000_000_000:
            _, signed, known, unknown = self.events.popleft()
            self.cvd -= signed
            self.known -= known
            self.unknown -= unknown

    def add(self, timestamp, payload):
        self.expire(timestamp)
        if payload.action != "T":
            return
        signed = (
            payload.size if payload.side == "B" else -payload.size if payload.side == "A" else 0
        )
        known = int(payload.side in ("A", "B"))
        unknown = 1 - known
        self.events.append((timestamp, signed, known, unknown))
        self.cvd += signed
        self.known += known
        self.unknown += unknown
        _require(len(self.events) <= 127, "Constructed flow queue bound exceeded")


class _Ofi:
    """Exact best-level increments between completed quote observations."""

    def __init__(self):
        self.previous = None
        self.first_ts = None
        self.events = deque()
        self.total = 0

    def expire(self, timestamp):
        while self.events and self.events[0][0] < timestamp - 5_000_000_000:
            _, value = self.events.popleft()
            self.total -= value

    def observe(self, quote):
        self.expire(quote.ts_recv_ns)
        if self.first_ts is None:
            self.first_ts = quote.ts_recv_ns
        if self.previous is not None:
            previous = self.previous
            bid = (quote.bid_qty if quote.bid >= previous.bid else 0) - (
                previous.bid_qty if quote.bid <= previous.bid else 0
            )
            ask = -(quote.ask_qty if quote.ask <= previous.ask else 0) + (
                previous.ask_qty if quote.ask >= previous.ask else 0
            )
            change = bid + ask
            self.events.append((quote.ts_recv_ns, change))
            self.total += change
            _require(len(self.events) <= 127, "Constructed OFI queue bound exceeded")
        self.previous = quote


class _History:
    """Visible quote/depletion proxies, not authenticated executions."""

    def __init__(self):
        self.quotes = deque()
        self.depletions = (deque(), deque())
        self.reloads = deque()

    def observe(self, quote):
        now = quote.ts_recv_ns
        cutoff = now - 5_000_000_000
        previous = self.quotes[-1] if self.quotes else None
        _require(previous is None or now >= previous.ts_recv_ns, "Quote history regressed")
        matched = [0, 0]
        for index, (price, quantity) in enumerate(
            ((quote.bid, quote.bid_qty), (quote.ask, quote.ask_qty))
        ):
            credit = self.depletions[index]
            while credit and credit[0][0] < cutoff:
                credit.popleft()
            if previous is None:
                continue
            old_price, old_quantity = (
                (previous.bid, previous.bid_qty) if index == 0 else (previous.ask, previous.ask_qty)
            )
            if price != old_price:
                credit.clear()
                continue
            change = quantity - old_quantity
            if change < 0:
                credit.append([now, -change])
                _require(len(credit) <= 127, "Constructed depletion queue bound exceeded")
            while change > 0 and credit:
                amount = min(change, credit[0][1])
                change -= amount
                credit[0][1] -= amount
                matched[index] += amount
                if credit[0][1] == 0:
                    credit.popleft()
        self.quotes.append(quote)
        self.reloads.append((now, *matched))
        while self.quotes and self.quotes[0].ts_recv_ns < cutoff:
            self.quotes.popleft()
        while self.reloads and self.reloads[0][0] < cutoff:
            self.reloads.popleft()
        _require(
            len(self.quotes) <= 127 and len(self.reloads) <= 127,
            "Constructed quote history queue bound exceeded",
        )

    @_guard
    def features(self, book, cvd):
        _require(bool(self.quotes), "Missing completed quote history")
        quote = self.quotes[-1]
        bid_prices = sorted(book.levels["B"], reverse=True)[:5]
        ask_prices = sorted(book.levels["A"])[:5]
        _require(
            bool(bid_prices)
            and bool(ask_prices)
            and (bid_prices[0], ask_prices[0]) == (quote.bid, quote.ask),
            "Depth book differs from completed quote",
        )
        bid_depth = sum(book.levels["B"][price] for price in bid_prices)
        ask_depth = sum(book.levels["A"][price] for price in ask_prices)
        mids = [(q.bid + q.ask) / (2 * 50_000) for q in self.quotes]
        change = mids[-1] - mids[0]
        depth = quote.bid_qty + quote.ask_qty
        values = (
            math.log1p(bid_depth),
            math.log1p(ask_depth),
            (bid_depth - ask_depth) / (bid_depth + ask_depth),
            quote.bid_qty / bid_depth,
            quote.ask_qty / ask_depth,
            (quote.bid - bid_prices[-1]) / 50_000,
            (ask_prices[-1] - quote.ask) / 50_000,
            change,
            max(mids) - min(mids),
            sum(abs(b - a) for a, b in zip(mids, mids[1:], strict=False)),
            math.log1p(len(mids)),
            sum(r[1] for r in self.reloads) / depth,
            sum(r[2] for r in self.reloads) / depth,
            max(cvd, 0) / (depth * (1 + max(change, 0))),
            max(-cvd, 0) / (depth * (1 + max(-change, 0))),
        )
        _require(all(math.isfinite(value) for value in values), "Nonfinite history feature")
        return dict(zip(_feature_names()[8:23], values, strict=True))


@dataclass(frozen=True, slots=True)
class _Captured:
    recv: int
    action: str
    side: str
    price: int
    size: int
    oid: int
    before: OrderState | None

    @classmethod
    def capture(cls, payload, book):
        return cls(
            payload.ts_recv,
            payload.action,
            payload.side,
            payload.price,
            payload.size,
            payload.order_id,
            book.orders.get(payload.order_id),
        )


def _match_fills(records, audit):
    approved, trade, used = {}, None, 0
    for index, record in enumerate(records):
        if record.action == "T":
            trade, used = record, 0
            _require(
                record.size > 0 and record.price > 0 and record.price % 50_000 == 0,
                "Invalid execution trade quantity or price",
            )
            audit[f"trade_{record.side}_volume"] += record.size
        elif record.action == "F":
            _require(record.size > 0, "Invalid fill quantity")
            reason = (
                "without_trade"
                if trade is None
                else "unknown_aggressor"
                if trade.side not in ("A", "B")
                else "aggressor"
                if record.oid == trade.oid or record.side == trade.side
                else "unknown_side"
                if record.side not in ("A", "B")
                else "price_mismatch"
                if record.price != trade.price
                else "unmatched_book"
                if record.before is None
                or (record.before.side, record.before.price) != (record.side, record.price)
                else "matched_passive"
            )
            audit[f"fill_{reason}_records"] += 1
            audit[f"fill_{reason}_volume"] += record.size
            if reason == "matched_passive":
                used += record.size
                _require(used <= trade.size, "Matched passive volume exceeds trade summary")
                approved[index] = record
                audit["fill_above_displayed_volume"] += max(0, record.size - record.before.size)
        else:
            trade, used = None, 0
    return approved


class _Execution:
    """Preserve conservative captured-event fill and refresh arithmetic."""

    def __init__(self):
        self.audit = Counter()
        self.last_ts = None
        self.events = deque()
        self.totals = Counter()
        self.credits = {"A": deque(), "B": deque()}

    def expire(self, now):
        cutoff = now - 5_000_000_000
        while self.events and self.events[0][0] < cutoff:
            _, values = self.events.popleft()
            self.totals.subtract(values)
        for credit in self.credits.values():
            while credit and (credit[0][0] < cutoff or credit[0][2] == 0):
                credit.popleft()

    def _reset_temporal(self):
        self.events.clear()
        self.totals.clear()
        for credit in self.credits.values():
            credit.clear()

    def complete(self, records, previous, quote, book):
        now = quote.ts_recv_ns
        _require(self.last_ts is None or now >= self.last_ts, "Execution feature clock regressed")
        _require(0 < len(records) <= 127, "Invalid bounded captured event")
        _require(
            records[-1].recv == now and all(record.recv <= now for record in records),
            "Captured event lies after completion",
        )
        if self.last_ts is None or now - self.last_ts > 5_000_000_000:
            self._reset_temporal()
            previous = None
            self.audit["temporal_resets"] += 1
        self.last_ts = now
        self.expire(now)
        if now - records[0].recv > 5_000_000_000:
            self.audit["stale_spanning_events_excluded"] += 1
            return
        fills = _match_fills(records, self.audit)
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
        for index, record in enumerate(records):
            key = (record.oid, record.side, record.price)
            if index in fills:
                delta[(record.side, "passive")] += record.size
                if stable[record.side] and record.price == best[record.side]:
                    delta[(record.side, "held_top_passive")] += record.size
                remaining[key] += record.size
                fill_totals[key] += record.size
                first_fill.setdefault(key, record)
                continue
            if record.action not in ("A", "C", "M"):
                continue
            old = record.before
            if record.action == "C":
                decrease, increase = record.size, 0
                if old is not None and record.size == old.size:
                    discontinuous.add(record.oid)
            elif record.action == "M":
                _require(old is not None, "Execution observer saw unknown modify")
                if (old.side, old.price) == (record.side, record.price):
                    decrease = max(0, old.size - record.size)
                    increase = max(0, record.size - old.size)
                    if key in first_fill:
                        modified.add(key)
                else:
                    discontinuous.add(record.oid)
                    delta[(old.side, "unlinked_decrease")] += old.size
                    decrease, increase = 0, record.size
            else:
                decrease, increase = 0, record.size
            linked = min(decrease, remaining[key])
            remaining[key] -= linked
            delta[(record.side, "linked_decrease")] += linked
            delta[(record.side, "unlinked_decrease")] += decrease - linked
            if not stable[record.side] or record.price != best[record.side]:
                continue
            credit = self.credits[record.side]
            if linked:
                _require(
                    sum(len(c) for c in self.credits.values()) < 127,
                    "Constructed execution credit bound exceeded",
                )
                credit.append([now, record.oid, linked])
            while increase and credit:
                amount = min(increase, credit[0][2])
                category = "same_id_reload" if credit[0][1] == record.oid else "other_id_reload"
                delta[(record.side, category)] += amount
                increase -= amount
                credit[0][2] -= amount
                if credit[0][2] == 0:
                    credit.popleft()
        for key in modified:
            oid, side, price = key
            final = book.orders.get(oid)
            if (
                oid in discontinuous
                or final is None
                or (final.side, final.price) != (side, price)
                or not stable[side]
                or price != best[side]
            ):
                continue
            initial = first_fill[key].before.size
            executed = fill_totals[key]
            refill = min(executed, max(0, final.size - max(0, initial - executed)))
            delta[(side, "same_id_net_refresh")] += refill
        delta = +delta
        if delta:
            _require(len(self.events) < 127, "Constructed execution event bound exceeded")
            self.events.append((now, delta))
            self.totals.update(delta)
            self.audit.update(
                {f"{side}_{metric}_volume": value for (side, metric), value in delta.items()}
            )
        self.audit["completed_events"] += 1

    @_guard
    def features(self, quote):
        self.expire(quote.ts_recv_ns)
        depth = quote.bid_qty + quote.ask_qty
        _require(depth > 0, "Invalid execution normalization depth")
        values = {
            f"{name}_{metric}_5s": self.totals[(side, metric)] / depth
            for name, side in (("bid", "B"), ("ask", "A"))
            for metric in (
                "passive",
                "held_top_passive",
                "linked_decrease",
                "unlinked_decrease",
                "same_id_reload",
                "other_id_reload",
                "same_id_net_refresh",
            )
        }
        _require(
            all(value >= 0 and math.isfinite(value) for value in values.values()),
            "Invalid execution feature",
        )
        return values


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _flags():
    return (
        ("account_authenticated", False),
        ("book_application_verified", False),
        ("broker_economics_measured", False),
        ("byte_offsets_verified", False),
        ("calendar_authenticated", False),
        ("codec_context_authenticated", False),
        ("complete_history_capacity_verified", False),
        ("decoded_source_authenticated", False),
        ("event_closure_verified", False),
        ("execution_allowed", False),
        ("feature_derivation_verified", False),
        ("funding_authenticated", False),
        ("historical_access_allowed", False),
        ("historical_validation_allowed", False),
        ("mapping_authenticated", False),
        ("model_call_allowed", False),
        ("multi_session_continuity_verified", False),
        ("native_decoding_verified", False),
        ("native_eof_verified", False),
        ("native_header_verified", False),
        ("native_payloads_verified", False),
        ("native_record_semantics_verified", False),
        ("native_target_ordinals_verified", False),
        ("original_bytes_verified", False),
        ("original_feature_row_parity_verified", False),
        ("promotion_allowed", False),
        ("publication_cursor_verified", False),
        ("runtime_authenticated", False),
        ("scoring_allowed", False),
        ("source_authenticated", False),
        ("storage_resume_allowed", False),
        ("strategy_integration_allowed", False),
        ("trading_enabled", False),
        ("training_allowed", False),
    )


def _feature_names():
    return (
        "log_bid_qty",
        "log_ask_qty",
        "queue_imbalance",
        "normalized_ofi_5s",
        "normalized_cvd_5s",
        "log_known_trades_5s",
        "unknown_trade_fraction_5s",
        "log_prior_quote_gap_ms",
        "log_bid_depth5",
        "log_ask_depth5",
        "depth5_imbalance",
        "bid_top_share5",
        "ask_top_share5",
        "bid_span5_ticks",
        "ask_span5_ticks",
        "mid_change_5s_ticks",
        "mid_range_5s_ticks",
        "mid_travel_5s_ticks",
        "log_quote_events_5s",
        "normalized_bid_reload_5s",
        "normalized_ask_reload_5s",
        "buy_absorption_proxy_5s",
        "sell_absorption_proxy_5s",
        "bid_passive_5s",
        "bid_held_top_passive_5s",
        "bid_linked_decrease_5s",
        "bid_unlinked_decrease_5s",
        "bid_same_id_reload_5s",
        "bid_other_id_reload_5s",
        "bid_same_id_net_refresh_5s",
        "ask_passive_5s",
        "ask_held_top_passive_5s",
        "ask_linked_decrease_5s",
        "ask_unlinked_decrease_5s",
        "ask_same_id_reload_5s",
        "ask_other_id_reload_5s",
        "ask_same_id_net_refresh_5s",
    )


def _schema_fields():
    return {
        "AdapterContext": [
            "input_version",
            "upgrade_policy",
            "yielded_version",
            "stype_in",
            "stype_out",
            "partial",
            "limit",
            "ts_out",
        ],
        "AdapterFixture": ["context", "payload_bundle"],
        "OrderState": ["side", "price", "size"],
        "OrderEntry": ["order_id", "state"],
        "PriceLevel": ["price", "size"],
        "AdapterAudit": [
            "decoded_position",
            "disposition",
            "instrument_id",
            "target_candidate_ordinal",
            "target_transition_ordinal",
            "binding_prefix_sha256",
            "adapter_prefix_sha256",
        ],
        "TargetTransition": [
            "decoded_position",
            "target_transition_ordinal",
            "disposition",
            "snapshot",
            "exceptional_closed_clear",
            "order_id",
            "before",
            "after",
            "initialized_before",
            "initialized_after",
            "last_recv_before",
            "last_recv_after",
            "event_ordinal",
            "quote_ordinal",
            "publication_ordinal",
            "state_sha256",
        ],
        "EventWitness": [
            "event_ordinal",
            "closing_decoded_position",
            "closing_target_transition_ordinal",
            "ts_recv_ns",
            "target_positions",
            "trade_positions",
            "execution_capture_positions",
            "quote_ordinal",
            "adapter_prefix_sha256",
            "event_sha256",
        ],
        "QuoteWitness": [
            "quote_ordinal",
            "event_ordinal",
            "decoded_position",
            "ts_recv_ns",
            "bid",
            "ask",
            "bid_qty",
            "ask_qty",
            "prior_quote_gap_ns",
            "ofi_generation",
            "bid_depth5",
            "ask_depth5",
            "adapter_prefix_sha256",
            "quote_sha256",
        ],
        "InactivityInterval": [
            "start_ns",
            "timer_fired_ns",
            "end_ns",
            "recovered",
            "trigger_decoded_position",
        ],
        "FeaturePublication": [
            "publication_ordinal",
            "quote_ordinal",
            "event_ordinal",
            "decoded_position",
            "ts_recv_ns",
            "adapter_prefix_sha256",
            "features",
            "publication_sha256",
        ],
        "ClockSample": [
            "decoded_position",
            "ts_recv",
            "ts_event",
            "ts_in_delta",
            "flags",
            "sequence",
            "action",
            "protected",
            "event_ahead_ns",
            "sending_ns",
        ],
        "ClockQuality": [
            "target_records",
            "snapshot_records",
            "non_snapshot_records",
            "event_after_receive",
            "negative_send_delta",
            "event_after_sending",
            "clamped_delta",
            "clock_disagreement_records",
            "protected_disagreement_records",
            "outside_disagreement_records",
            "min_event_ahead_ns",
            "max_event_ahead_ns",
            "min_negative_delta_ns",
            "samples",
        ],
        "ReconstructedState": [
            "initialized",
            "orders",
            "bid_levels",
            "ask_levels",
            "last_recv_ns",
            "pending_target_positions",
            "pending_trade_positions",
            "execution_capture_positions",
            "last_quote_ordinal",
            "flow_events",
            "cvd",
            "known_trades",
            "unknown_trades",
            "ofi_generation",
            "ofi_previous_quote_ordinal",
            "ofi_first_ts_ns",
            "ofi_events",
            "ofi_total",
            "history_ofi_generation",
            "history_quote_ordinals",
            "bid_depletions",
            "ask_depletions",
            "history_reloads",
            "execution_last_ts_ns",
            "execution_events",
            "execution_totals",
            "bid_credits",
            "ask_credits",
            "execution_audit",
            "next_publication_ns",
            "watch_since_ns",
            "inactivity_start_ns",
            "window_closed",
        ],
        "AdapterAssessment": [
            "status",
            "protocol_sha256",
            "context_sha256",
            "binding_protocol_sha256",
            "cursor_protocol_sha256",
            "fixture_sha256",
            "fixture",
            "binding_assessment",
            "audits",
            "transitions",
            "events",
            "quotes",
            "publications",
            "inactivity_intervals",
            "clock_quality",
            "exceptional_clear_count",
            "terminal_state",
            "authority_flags",
            "assessment_sha256",
        ],
    }


def _protocol_body():
    return {
        "version": "constructed_typed_native_event_adapter_v1",
        "scope": "invented_native_shaped_target_event_and_feature_publication_reconstruction_only",
        "status": "constructed_typed_native_event_adapter_not_native_verification",
        "context_values": {
            "input_version": 3,
            "upgrade_policy": "AS_IS",
            "yielded_version": 3,
            "stype_in": "parent",
            "stype_out": "instrument_id",
            "partial": [],
            "limit": None,
            "ts_out_modes": [False, True],
        },
        "utc_date": "2025-04-07",
        "contract": "6EM5",
        "day_start_ns": 1_743_984_000_000_000_000,
        "day_end_ns": 1_744_070_400_000_000_000,
        "warmup_start_ns": 1_744_027_190_000_000_000,
        "window_start_ns": 1_744_027_200_000_000_000,
        "window_end_ns": 1_744_041_600_000_000_000,
        "constants": {
            "second_ns": 1_000_000_000,
            "tick": 50_000,
            "decision_interval_ns": 1_000_000_000,
            "flow_ns": 5_000_000_000,
            "inactivity_ns": 5_000_000_000,
            "execution_window_ns": 5_000_000_000,
            "F_LAST": 128,
            "F_TOB": 64,
            "F_SNAPSHOT": 32,
            "F_MBP": 16,
            "F_BAD_TS_RECV": 8,
            "F_MAYBE_BAD_BOOK": 4,
            "UNDEF_PRICE": 9_223_372_036_854_775_807,
        },
        "limits": {
            "min_items": 2,
            "max_items": 128,
            "max_mapping_groups": 8,
            "max_intervals_per_group": 16,
            "max_total_intervals": 32,
            "max_cursor_body_bytes": 65_536,
            "max_binding_body_bytes": 262_144,
            "max_adapter_body_bytes": 1_048_576,
            "max_state_body_bytes": 1_048_576,
            "max_transitions": 127,
            "max_events": 127,
            "max_quotes": 127,
            "min_publications": 1,
            "max_publications": 32,
            "max_inactivity_intervals": 128,
            "max_orders": 127,
            "max_queue_entries": 127,
            "max_clock_samples": 8,
            "max_exceptional_clears": 32,
        },
        "dataclass_fields": _schema_fields(),
        "feature_names": list(_feature_names()),
        "feature_scalar_rule": "original_float_values_except_single_quote_int_zero_travel",
        "prefix_scheme": "adapter_protocol_context_checked_binding_prefix",
        "prefix_complete_member_pin": "excluded",
        "binding_protocol_sha256": binding.protocol_sha256(),
        "cursor_protocol_sha256": cursor.protocol_sha256(),
        "binding_source_sha256": "4c5ac736a268c350389c63f0c23577fdcdd4473ea19d16aa13313cb49187be94",
        "cursor_source_sha256": "c7bc0102073fa61f1d69411479331cf1e434616cb80faa6bbc266377745dcf91",
        "numerical_rule_sources": {
            "src/ai_trader/research/databento_6e_training_data.py": (
                "9d1c9190da304031113880dbfb4d002121908d35b6bc52671a65939a6e7049a3"
            ),
            "src/ai_trader/research/databento_6e_scenario_replay.py": (
                "d5bf8e3e0ec4b1957f1a2a7ed515f1cf9530b922e5c2c3929389ed0bfeab91ff"
            ),
            "src/ai_trader/research/databento_6e_seconds_pilot.py": (
                "7c295b7cc3875a6955d3582368a7d28804dd318e061e0d0b3906e4a21e411b2b"
            ),
            "src/ai_trader/research/databento_6e_ofi_scalp.py": (
                "05cade0f206c06cbea93198c9fb92e591c0275ef5ac70f8ce50bcb000ad0ff24"
            ),
            "src/ai_trader/research/databento_6e_event_scalp.py": (
                "48bd0402c2e8a7c0d8d286b8956a2f55059c71df81dc1115ee15d8adce560b3e"
            ),
            "src/ai_trader/research/databento_6e_cost_targets.py": (
                "ebc4c1dc0a44e71362cd96bed0a699dac6ebc04a66fc7f568d2bf4898d427b2b"
            ),
            "src/ai_trader/research/databento_6e_microdepth.py": (
                "8964b20a5de8104a0f7831cf827c1c736f3c11b6a2d61dbe0206521ee3b451c4"
            ),
            "src/ai_trader/research/databento_6e_execution_flow.py": (
                "7f777a19518378dd3b2a0371b7f3ddcf3077f51555faffa5e589de6255239b75"
            ),
            "src/ai_trader/research/databento_6e_receive_clock.py": (
                "351b4b54fc3ac4ac905ebdbb9725f270288ac235178cb50180e2040d8fef4636"
            ),
        },
        "authority_flags": dict(_flags()),
    }


def protocol() -> dict:
    """Return a fresh complete literal protocol, not runtime authentication."""
    return _protocol_body()


def protocol_sha256() -> str:
    """Pin the complete literal protocol without traversing caller values."""
    return _digest(_protocol_body())


@_guard
def context_sha256(context: AdapterContext, *, expected_protocol_sha256: str) -> str:
    """Validate and pin the complete explicit interpretation context."""
    _pins(expected_protocol_sha256)
    _require(expected_protocol_sha256 == protocol_sha256(), "Adapter protocol differs")
    return _digest(_context_body(context))


def _exact(value, expected_type):
    _require(type(value) is expected_type, "Exact declared type required")


def _tuple(value, minimum=0, maximum=127):
    _require(
        type(value) is tuple and minimum <= len(value) <= maximum,
        "Exact bounded complete tuple required",
    )


def _ordinal(value, maximum=127):
    _require(type(value) is int and 1 <= value <= maximum, "Exact bounded ordinal required")


def _optional_reference(value, allowed):
    _require(
        value is None or (type(value) is int and value in allowed),
        "Reference must name an existing metadata artifact",
    )


def _positions(values, allowed, minimum=0):
    _tuple(values, minimum)
    previous = 0
    for position in values:
        _require(
            type(position) is int and position in allowed and position > previous,
            "Exact ordered position membership required",
        )
        previous = position


def _flags_metadata(values, expected):
    _tuple(values, len(expected), len(expected))
    for supplied, original in zip(values, expected, strict=True):
        _require(type(supplied) is tuple and len(supplied) == 2, "Exact authority pair required")
        _require(
            type(supplied[0]) is str and supplied[0] == original[0] and supplied[1] is False,
            "Every authority stays literal False",
        )


def _bundle_metadata(bundle, adapter_context, cursor_pin, cursor_fixture_pin):
    """Read only original dependency metadata, never any MboPayload slot."""
    _exact(bundle, binding.PayloadBundle)
    _exact(bundle.context, binding.PayloadContext)
    context = bundle.context
    _require(
        type(context.codec_id) is str and context.codec_id == "constructed_mbo_json_v1",
        "Exact constructed payload codec required",
    )
    _require(
        type(context.schema_version) is int and context.schema_version == 1,
        "Exact constructed payload version required",
    )
    _require(
        type(context.ts_out_mode) is str
        and context.ts_out_mode == ("present" if adapter_context.ts_out else "absent"),
        "Explicit native-shaped/payload ts_out modes differ",
    )
    payload_context_pin = _digest(
        {
            "codec_id": context.codec_id,
            "schema_version": context.schema_version,
            "ts_out_mode": context.ts_out_mode,
        }
    )
    old_fixture = bundle.cursor_fixture
    computed = cursor.fixture_sha256(old_fixture, expected_protocol_sha256=cursor_pin)
    _require(computed == cursor_fixture_pin, "Complete cursor fixture differs")
    old = cursor.assess(
        old_fixture, expected_fixture_sha256=cursor_fixture_pin, expected_protocol_sha256=cursor_pin
    )
    _tuple(bundle.payloads, 2, 128)
    _require(
        len(bundle.payloads) == old.decoded_item_count and bundle.payloads[0] is None,
        "Complete payload positions and header None required",
    )
    for payload in bundle.payloads[1:]:
        _exact(payload, binding.MboPayload)
    # The public metadata verifier retains both old complete caps. It cannot
    # inspect the separately supplied raw payloads, even on replay's own gate.
    cursor.verify(
        old,
        old_fixture,
        expected_fixture_sha256=cursor_fixture_pin,
        expected_protocol_sha256=cursor_pin,
        expected_assessment_sha256=old.assessment_sha256,
    )
    return old, payload_context_pin


def _fixture_metadata(fixture, context_pin, cursor_pin, cursor_fixture_pin):
    _exact(fixture, AdapterFixture)
    _require(_digest(_context_body(fixture.context)) == context_pin, "Complete context differs")
    return _bundle_metadata(fixture.payload_bundle, fixture.context, cursor_pin, cursor_fixture_pin)


def _binding_prefix(binding_pin, payload_context_pin, cursor_prefix):
    return _digest(
        {
            "binding_protocol_sha256": binding_pin,
            "context_sha256": payload_context_pin,
            "cursor_prefix_sha256": cursor_prefix,
        }
    )


def _adapter_prefix(protocol_pin, context_pin, binding_prefix):
    return _digest(
        {
            "adapter_protocol_sha256": protocol_pin,
            "context_sha256": context_pin,
            "binding_prefix_sha256": binding_prefix,
        }
    )


def _binding_metadata(
    value,
    original,
    adapter_context,
    old,
    payload_context_pin,
    binding_pin,
    cursor_pin,
    cursor_fixture_pin,
    bundle_pin,
):
    _exact(value, binding.BindingAssessment)
    _require(
        type(value.status) is str
        and value.status == "constructed_record_payload_binding_not_native_verification",
        "Exact binding status required",
    )
    _pins(
        value.protocol_sha256,
        value.context_sha256,
        value.cursor_protocol_sha256,
        value.cursor_fixture_sha256,
        value.bundle_sha256,
        value.assessment_sha256,
    )
    _require(
        (
            value.protocol_sha256,
            value.context_sha256,
            value.cursor_protocol_sha256,
            value.cursor_fixture_sha256,
            value.bundle_sha256,
        )
        == (binding_pin, payload_context_pin, cursor_pin, cursor_fixture_pin, bundle_pin),
        "Submitted binding metadata differs",
    )
    submitted_old, submitted_context_pin = _bundle_metadata(
        value.bundle, adapter_context, cursor_pin, cursor_fixture_pin
    )
    _require(submitted_context_pin == payload_context_pin, "Submitted payload context differs")
    cursor.verify(
        value.cursor_assessment,
        original.cursor_fixture,
        expected_fixture_sha256=cursor_fixture_pin,
        expected_protocol_sha256=cursor_pin,
        expected_assessment_sha256=old.assessment_sha256,
    )
    _tuple(value.audits, old.decoded_item_count, old.decoded_item_count)
    for audit, original_audit, item in zip(
        value.audits, submitted_old.audits, original.cursor_fixture.items, strict=True
    ):
        _exact(audit, binding.PayloadAudit)
        expected_prefix = _binding_prefix(
            binding_pin, payload_context_pin, original_audit.prefix_sha256
        )
        _require(
            (
                audit.decoded_position,
                audit.disposition,
                audit.instrument_id,
                audit.target_candidate_ordinal,
                audit.payload_sha256,
                audit.cursor_item_sha256,
                audit.cursor_prefix_sha256,
                audit.bound_prefix_sha256,
            )
            == (
                original_audit.decoded_position,
                original_audit.disposition,
                original_audit.instrument_id,
                original_audit.target_candidate_ordinal,
                item.payload_sha256,
                original_audit.item_sha256,
                original_audit.prefix_sha256,
                expected_prefix,
            ),
            "Complete submitted binding audit differs",
        )
        _require(
            type(audit.decoded_position) is int and type(audit.disposition) is str,
            "Exact binding audit scalars required",
        )
        if audit.instrument_id is not None:
            _require(type(audit.instrument_id) is int, "Exact metadata instrument required")
        if audit.target_candidate_ordinal is not None:
            _ordinal(audit.target_candidate_ordinal)
        _pins(audit.cursor_item_sha256, audit.cursor_prefix_sha256, audit.bound_prefix_sha256)
        if audit.payload_sha256 is not None:
            _pins(audit.payload_sha256)
    _flags_metadata(
        value.authority_flags, tuple(sorted(binding.protocol()["authority_flags"].items()))
    )


def _levels_metadata(values, maximum=127):
    _tuple(values, 0, maximum)
    for value in values:
        _exact(value, PriceLevel)


def _metric_name(name):
    return type(name) is str and name in tuple(
        f"{side}_{metric}"
        for side in ("A", "B")
        for metric in (
            "passive",
            "held_top_passive",
            "linked_decrease",
            "unlinked_decrease",
            "same_id_reload",
            "other_id_reload",
            "same_id_net_refresh",
        )
    )


def _audit_name(name):
    if type(name) is not str:
        return False
    if name in (
        "temporal_resets",
        "stale_spanning_events_excluded",
        "fill_above_displayed_volume",
        "completed_events",
    ):
        return True
    if name in tuple(
        f"fill_{reason}_{kind}"
        for reason in (
            "without_trade",
            "unknown_aggressor",
            "aggressor",
            "unknown_side",
            "price_mismatch",
            "unmatched_book",
            "matched_passive",
        )
        for kind in ("records", "volume")
    ):
        return True
    if name.endswith("_volume") and _metric_name(name[:-7]):
        return True
    return re.fullmatch(r"trade_[\x00-\x7f]_volume", name) is not None


def _pairs_metadata(values, audit=False):
    _tuple(values, 0, 160)
    names = []
    for pair in values:
        _require(type(pair) is tuple and len(pair) == 2, "Exact named metric pair required")
        _require(
            _audit_name(pair[0]) if audit else _metric_name(pair[0]),
            "Exact normative metric name required",
        )
        names.append(pair[0])
    _require(names == sorted(set(names)), "Metric names must be sorted and unique")


def _queue_metadata(values, arity):
    _tuple(values)
    for value in values:
        _require(type(value) is tuple and len(value) == arity, "Exact state queue arity required")


def _state_metadata(value, target_positions, quote_ordinals):
    _exact(value, ReconstructedState)
    _tuple(value.orders)
    for entry in value.orders:
        _exact(entry, OrderEntry)
        _exact(entry.state, OrderState)
    _levels_metadata(value.bid_levels)
    _levels_metadata(value.ask_levels)
    for positions in (
        value.pending_target_positions,
        value.pending_trade_positions,
        value.execution_capture_positions,
    ):
        _positions(positions, target_positions)
    _optional_reference(value.last_quote_ordinal, quote_ordinals)
    _optional_reference(value.ofi_previous_quote_ordinal, quote_ordinals)
    _positions(value.history_quote_ordinals, quote_ordinals)
    for values, arity in (
        (value.flow_events, 4),
        (value.ofi_events, 2),
        (value.bid_depletions, 2),
        (value.ask_depletions, 2),
        (value.history_reloads, 3),
        (value.bid_credits, 3),
        (value.ask_credits, 3),
    ):
        _queue_metadata(values, arity)
    _queue_metadata(value.execution_events, 2)
    for entry in value.execution_events:
        _pairs_metadata(entry[1])
    _pairs_metadata(value.execution_totals)
    _pairs_metadata(value.execution_audit, audit=True)


def _submitted_metadata(
    value,
    fixture,
    old,
    payload_context_pin,
    protocol_pin,
    context_pin,
    binding_pin,
    cursor_pin,
    cursor_fixture_pin,
    bundle_pin,
    fixture_pin,
    assessment_pin,
):
    """Inspect named metadata slots only; all observed/numeric slots stay late."""
    _exact(value, AdapterAssessment)
    _require(
        type(value.status) is str
        and value.status == "constructed_typed_native_event_adapter_not_native_verification",
        "Exact constructed adapter status required",
    )
    _pins(
        value.protocol_sha256,
        value.context_sha256,
        value.binding_protocol_sha256,
        value.cursor_protocol_sha256,
        value.fixture_sha256,
        value.assessment_sha256,
    )
    _require(
        (
            value.protocol_sha256,
            value.context_sha256,
            value.binding_protocol_sha256,
            value.cursor_protocol_sha256,
            value.fixture_sha256,
            value.assessment_sha256,
        )
        == (protocol_pin, context_pin, binding_pin, cursor_pin, fixture_pin, assessment_pin),
        "Retained submitted expectations differ",
    )
    _fixture_metadata(value.fixture, context_pin, cursor_pin, cursor_fixture_pin)
    _binding_metadata(
        value.binding_assessment,
        fixture.payload_bundle,
        fixture.context,
        old,
        payload_context_pin,
        binding_pin,
        cursor_pin,
        cursor_fixture_pin,
        bundle_pin,
    )
    target_positions = {
        audit.decoded_position for audit in old.audits if audit.target_candidate_ordinal is not None
    }
    _tuple(value.transitions, len(target_positions), len(target_positions))
    transitions = {}
    for ordinal, transition in enumerate(value.transitions, 1):
        _exact(transition, TargetTransition)
        _ordinal(transition.decoded_position, 128)
        _ordinal(transition.target_transition_ordinal)
        _require(
            transition.decoded_position in target_positions
            and transition.target_transition_ordinal == ordinal,
            "Complete transition ordinals/positions required",
        )
        _require(
            type(transition.disposition) is str
            and transition.disposition in ("target_reset", "target_snapshot", "target_record"),
            "Exact transition disposition",
        )
        for state in (transition.before, transition.after):
            if state is not None:
                _exact(state, OrderState)
        _pins(transition.state_sha256)
        transitions[transition.decoded_position] = transition
    _require(
        tuple(transitions) == tuple(sorted(target_positions)),
        "Transitions must cover every ordered target",
    )
    _tuple(value.audits, old.decoded_item_count, old.decoded_item_count)
    prefixes = {}
    for audit, old_audit in zip(value.audits, old.audits, strict=True):
        _exact(audit, AdapterAudit)
        transition = transitions.get(old_audit.decoded_position)
        disposition = transition.disposition if transition is not None else old_audit.disposition
        bound = _binding_prefix(binding_pin, payload_context_pin, old_audit.prefix_sha256)
        prefix = _adapter_prefix(protocol_pin, context_pin, bound)
        _require(
            (
                audit.decoded_position,
                audit.disposition,
                audit.instrument_id,
                audit.target_candidate_ordinal,
                audit.target_transition_ordinal,
                audit.binding_prefix_sha256,
                audit.adapter_prefix_sha256,
            )
            == (
                old_audit.decoded_position,
                disposition,
                old_audit.instrument_id,
                old_audit.target_candidate_ordinal,
                old_audit.target_candidate_ordinal,
                bound,
                prefix,
            ),
            "Complete adapter audit metadata differs",
        )
        _require(
            type(audit.decoded_position) is int and type(audit.disposition) is str,
            "Exact adapter audit scalars required",
        )
        if audit.instrument_id is not None:
            _require(type(audit.instrument_id) is int, "Exact metadata instrument required")
        for ordinal in (audit.target_candidate_ordinal, audit.target_transition_ordinal):
            if ordinal is not None:
                _ordinal(ordinal)
        _pins(audit.binding_prefix_sha256, audit.adapter_prefix_sha256)
        prefixes[audit.decoded_position] = prefix
    _tuple(value.events)
    events = {}
    covered = []
    previous_closing = 0
    for ordinal, event in enumerate(value.events, 1):
        _exact(event, EventWitness)
        _ordinal(event.event_ordinal)
        _require(event.event_ordinal == ordinal, "Contiguous event ordinals required")
        _positions(event.target_positions, target_positions, 1)
        _positions(event.trade_positions, set(event.target_positions))
        _positions(event.execution_capture_positions, set(event.target_positions))
        _require(
            type(event.closing_decoded_position) is int
            and event.closing_decoded_position == event.target_positions[-1]
            and event.closing_decoded_position > previous_closing,
            "Ordered event closing positions required",
        )
        transition = transitions[event.closing_decoded_position]
        _require(
            type(event.closing_target_transition_ordinal) is int
            and event.closing_target_transition_ordinal == transition.target_transition_ordinal
            and transition.event_ordinal == ordinal,
            "Event closing transition differs",
        )
        _pins(event.adapter_prefix_sha256, event.event_sha256)
        _require(
            event.adapter_prefix_sha256 == prefixes[event.closing_decoded_position],
            "Event consumed prefix differs",
        )
        covered.extend(event.target_positions)
        previous_closing = event.closing_decoded_position
        events[ordinal] = event
    ordinary = [
        position
        for position, transition in transitions.items()
        if transition.disposition == "target_record"
    ]
    _require(covered == ordinary, "Complete disjoint ordinary event membership required")
    _tuple(value.quotes)
    quotes = {}
    previous_closing = 0
    for ordinal, quote in enumerate(value.quotes, 1):
        _exact(quote, QuoteWitness)
        _ordinal(quote.quote_ordinal)
        _ordinal(quote.event_ordinal)
        _require(
            quote.quote_ordinal == ordinal and quote.event_ordinal in events,
            "Contiguous quote ordinals/valid event required",
        )
        event = events[quote.event_ordinal]
        _require(
            type(quote.decoded_position) is int
            and quote.decoded_position == event.closing_decoded_position
            and quote.decoded_position > previous_closing
            and event.quote_ordinal == ordinal
            and transitions[quote.decoded_position].quote_ordinal == ordinal,
            "Complete quote back-links differ",
        )
        _levels_metadata(quote.bid_depth5, 5)
        _levels_metadata(quote.ask_depth5, 5)
        _pins(quote.adapter_prefix_sha256, quote.quote_sha256)
        _require(
            quote.adapter_prefix_sha256 == prefixes[quote.decoded_position],
            "Quote consumed prefix differs",
        )
        quotes[ordinal] = quote
        previous_closing = quote.decoded_position
    _tuple(value.publications, 1, 32)
    publications = {}
    previous_closing = 0
    used_quotes = set()
    for ordinal, publication in enumerate(value.publications, 1):
        _exact(publication, FeaturePublication)
        _ordinal(publication.publication_ordinal, 32)
        _ordinal(publication.quote_ordinal)
        _ordinal(publication.event_ordinal)
        _require(
            publication.publication_ordinal == ordinal
            and publication.quote_ordinal in quotes
            and publication.quote_ordinal not in used_quotes,
            "Contiguous publication ordinals/unique quote required",
        )
        quote = quotes[publication.quote_ordinal]
        _require(
            type(publication.decoded_position) is int
            and publication.decoded_position == quote.decoded_position
            and publication.decoded_position > previous_closing
            and publication.event_ordinal == quote.event_ordinal
            and transitions[publication.decoded_position].publication_ordinal == ordinal,
            "Complete publication back-links differ",
        )
        _tuple(publication.features, 37, 37)
        for pair, name in zip(publication.features, _feature_names(), strict=True):
            _require(
                type(pair) is tuple and len(pair) == 2 and type(pair[0]) is str and pair[0] == name,
                "Exact feature name/arity/order required",
            )
        _pins(publication.adapter_prefix_sha256, publication.publication_sha256)
        _require(
            publication.adapter_prefix_sha256 == prefixes[publication.decoded_position],
            "Publication consumed prefix differs",
        )
        publications[ordinal] = publication
        used_quotes.add(publication.quote_ordinal)
        previous_closing = publication.decoded_position
    for transition in value.transitions:
        _optional_reference(transition.event_ordinal, events)
        _optional_reference(transition.quote_ordinal, quotes)
        _optional_reference(transition.publication_ordinal, publications)
        if transition.quote_ordinal is not None:
            quote = quotes[transition.quote_ordinal]
            _require(
                quote.decoded_position == transition.decoded_position
                and quote.event_ordinal == transition.event_ordinal,
                "A transition may reference only its own closing quote",
            )
        if transition.publication_ordinal is not None:
            publication = publications[transition.publication_ordinal]
            _require(
                publication.decoded_position == transition.decoded_position
                and publication.event_ordinal == transition.event_ordinal
                and publication.quote_ordinal == transition.quote_ordinal,
                "A transition may reference only its own closing publication",
            )
        if transition.disposition != "target_record":
            _require(
                transition.event_ordinal is None
                and transition.quote_ordinal is None
                and transition.publication_ordinal is None,
                "Nonordinary links are None",
            )
        elif transition.event_ordinal is not None:
            _require(
                events[transition.event_ordinal].closing_decoded_position
                == transition.decoded_position,
                "Only closing transition owns event link",
            )
        else:
            _require(
                transition.quote_ordinal is None and transition.publication_ordinal is None,
                "No quote/publication without closing event",
            )
    for event in value.events:
        _optional_reference(event.quote_ordinal, quotes)
        if event.quote_ordinal is not None:
            quote = quotes[event.quote_ordinal]
            _require(
                quote.event_ordinal == event.event_ordinal
                and quote.decoded_position == event.closing_decoded_position,
                "An event may reference only its own closing quote",
            )
    _tuple(value.inactivity_intervals, 0, 128)
    for interval in value.inactivity_intervals:
        _exact(interval, InactivityInterval)
        _optional_reference(interval.trigger_decoded_position, target_positions)
    _exact(value.clock_quality, ClockQuality)
    _tuple(value.clock_quality.samples, 0, 8)
    sample_positions = []
    for sample in value.clock_quality.samples:
        _exact(sample, ClockSample)
        sample_positions.append(sample.decoded_position)
    _positions(tuple(sample_positions), target_positions)
    _state_metadata(value.terminal_state, target_positions, set(quotes))
    _flags_metadata(value.authority_flags, _flags())


def _late_binding(
    fixture,
    payload_context_pin,
    binding_pin,
    cursor_pin,
    cursor_fixture_pin,
    bundle_pin,
    submitted=None,
):
    arguments = {
        "expected_protocol_sha256": binding_pin,
        "expected_context_sha256": payload_context_pin,
        "expected_cursor_protocol_sha256": cursor_pin,
        "expected_cursor_fixture_sha256": cursor_fixture_pin,
    }
    computed = binding.bundle_sha256(fixture.payload_bundle, **arguments)
    _require(computed == bundle_pin, "Actual complete binding bundle differs")
    rebuilt = binding.assess(fixture.payload_bundle, **arguments, expected_bundle_sha256=bundle_pin)
    if submitted is not None:
        binding.verify(
            submitted.binding_assessment,
            fixture.payload_bundle,
            **arguments,
            expected_bundle_sha256=bundle_pin,
            expected_assessment_sha256=rebuilt.assessment_sha256,
        )
    return rebuilt


def _bounded_canonical(value):
    raw = _canonical(value)
    _require(len(raw) <= 1_048_576, "Complete adapter or state body exceeds its byte bound")
    return raw


def _counter_body(values):
    result = {}
    for name, value in values:
        _require(type(name) is str and type(value) is int, "Exact counter names/values required")
        result[name] = value
    return result


def _cursor_fixture_body(value):
    header = value.header
    return {
        "fixture_id": value.fixture_id,
        "source_session": value.source_session,
        "utc_date": value.utc_date,
        "contract": value.contract,
        "header": {
            "dataset": header.dataset,
            "schema": header.schema,
            "symbols": list(header.symbols),
            "not_found": list(header.not_found),
            "start_ns": header.start_ns,
            "end_ns": header.end_ns,
            "mappings": [
                {
                    "contract": group.contract,
                    "intervals": [
                        {
                            "start_date": interval.start_date,
                            "end_date": interval.end_date,
                            "instrument_symbol": interval.instrument_symbol,
                        }
                        for interval in group.intervals
                    ],
                }
                for group in header.mappings
            ],
        },
        "asserted_member_sha256": value.asserted_member_sha256,
        "declared_item_count": value.declared_item_count,
        "items": [
            {
                "decoded_position": item.decoded_position,
                "kind": item.kind,
                "instrument_id": item.instrument_id,
                "payload_sha256": item.payload_sha256,
            }
            for item in value.items
        ],
    }


def _bundle_body(value):
    context = value.context
    payloads = [None]
    for payload in value.payloads[1:]:
        payloads.append(
            {
                "publisher_id": payload.publisher_id,
                "instrument_id": payload.instrument_id,
                "ts_event": payload.ts_event,
                "order_id": payload.order_id,
                "price": payload.price,
                "size": payload.size,
                "action": payload.action,
                "side": payload.side,
                "ts_recv": payload.ts_recv,
                "flags": payload.flags,
                "channel_id": payload.channel_id,
                "ts_in_delta": payload.ts_in_delta,
                "sequence": payload.sequence,
                "ts_out": payload.ts_out,
                "rtype": payload.rtype,
                "record_size": payload.record_size,
            }
        )
    return {
        "context": {
            "codec_id": context.codec_id,
            "schema_version": context.schema_version,
            "ts_out_mode": context.ts_out_mode,
        },
        "cursor_fixture": _cursor_fixture_body(value.cursor_fixture),
        "payloads": payloads,
    }


def _cursor_assessment_body(value):
    return {
        "status": value.status,
        "protocol_sha256": value.protocol_sha256,
        "fixture_sha256": value.fixture_sha256,
        "fixture": _cursor_fixture_body(value.fixture),
        "mapped_instrument_id": value.mapped_instrument_id,
        "decoded_item_count": value.decoded_item_count,
        "target_candidate_count": value.target_candidate_count,
        "foreign_count": value.foreign_count,
        "audits": [
            {
                "decoded_position": audit.decoded_position,
                "disposition": audit.disposition,
                "instrument_id": audit.instrument_id,
                "target_candidate_ordinal": audit.target_candidate_ordinal,
                "item_sha256": audit.item_sha256,
                "prefix_sha256": audit.prefix_sha256,
            }
            for audit in value.audits
        ],
        "authority_flags": dict(value.authority_flags),
        "assessment_sha256": value.assessment_sha256,
    }


def _binding_assessment_body(value):
    return {
        "status": value.status,
        "protocol_sha256": value.protocol_sha256,
        "context_sha256": value.context_sha256,
        "cursor_protocol_sha256": value.cursor_protocol_sha256,
        "cursor_fixture_sha256": value.cursor_fixture_sha256,
        "bundle_sha256": value.bundle_sha256,
        "bundle": _bundle_body(value.bundle),
        "cursor_assessment": _cursor_assessment_body(value.cursor_assessment),
        "audits": [
            {
                "decoded_position": audit.decoded_position,
                "disposition": audit.disposition,
                "instrument_id": audit.instrument_id,
                "target_candidate_ordinal": audit.target_candidate_ordinal,
                "payload_sha256": audit.payload_sha256,
                "cursor_item_sha256": audit.cursor_item_sha256,
                "cursor_prefix_sha256": audit.cursor_prefix_sha256,
                "bound_prefix_sha256": audit.bound_prefix_sha256,
            }
            for audit in value.audits
        ],
        "authority_flags": dict(value.authority_flags),
        "assessment_sha256": value.assessment_sha256,
    }


def _project(value):
    """Late exact-value projection using only the fixed literal field schemas."""
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        _require(math.isfinite(value), "Finite exact float required")
        return value
    if type(value) is tuple:
        return [_project(item) for item in value]
    types = {
        OrderState: "OrderState",
        OrderEntry: "OrderEntry",
        PriceLevel: "PriceLevel",
        AdapterAudit: "AdapterAudit",
        TargetTransition: "TargetTransition",
        EventWitness: "EventWitness",
        QuoteWitness: "QuoteWitness",
        InactivityInterval: "InactivityInterval",
        FeaturePublication: "FeaturePublication",
        ClockSample: "ClockSample",
        ClockQuality: "ClockQuality",
        ReconstructedState: "ReconstructedState",
    }
    name = types.get(type(value))
    _require(name is not None, "Exact scalar/record types required in complete late body")
    body = {
        field: _project(getattr(value, field))
        for field in _schema_fields()[name]
        if not (
            name == "ReconstructedState"
            and field in ("execution_totals", "execution_audit", "execution_events")
        )
    }
    if name == "ReconstructedState":
        body["execution_totals"] = _counter_body(value.execution_totals)
        body["execution_audit"] = _counter_body(value.execution_audit)
        body["execution_events"] = [
            [_project(timestamp), _counter_body(metrics)]
            for timestamp, metrics in value.execution_events
        ]
    return body


def _fixture_body(value):
    return {
        "context": _context_body(value.context),
        "payload_bundle": _bundle_body(value.payload_bundle),
    }


def _assessment_body(value):
    return {
        "status": value.status,
        "protocol_sha256": value.protocol_sha256,
        "context_sha256": value.context_sha256,
        "binding_protocol_sha256": value.binding_protocol_sha256,
        "cursor_protocol_sha256": value.cursor_protocol_sha256,
        "fixture_sha256": value.fixture_sha256,
        "fixture": _fixture_body(value.fixture),
        "binding_assessment": _binding_assessment_body(value.binding_assessment),
        "audits": [_project(item) for item in value.audits],
        "transitions": [_project(item) for item in value.transitions],
        "events": [_project(item) for item in value.events],
        "quotes": [_project(item) for item in value.quotes],
        "publications": [_project(item) for item in value.publications],
        "inactivity_intervals": [_project(item) for item in value.inactivity_intervals],
        "clock_quality": _project(value.clock_quality),
        "exceptional_clear_count": _project(value.exceptional_clear_count),
        "terminal_state": _project(value.terminal_state),
        "authority_flags": dict(value.authority_flags),
    }


def _artifact_pin(value, own_pin):
    body = _project(value)
    del body[own_pin]
    return hashlib.sha256(_bounded_canonical(body)).hexdigest()


class _Engine:
    """One fresh reconstructed invented day; no supplied numeric state adopted."""

    def __init__(self, fixture, bound, protocol_pin, context_pin):
        self.fixture, self.bound = fixture, bound
        self.protocol_pin, self.context_pin = protocol_pin, context_pin
        self.book, self.clock = _Book(), _ClockAudit()
        self.flow, self.ofi, self.history, self.execution = (
            _Flow(),
            _Ofi(),
            _History(),
            _Execution(),
        )
        self.ofi_generation = 0
        self.history_ofi_generation = None
        self.last_recv = self.last_quote = None
        self.pending = []
        self.trades = []
        self.capture = []
        self.audits, self.transitions, self.events, self.quotes, self.publications = (
            [],
            [],
            [],
            [],
            [],
        )
        self.intervals = []
        self.exceptional_clears = 0
        self.next_publication = 1_744_027_200_000_000_000
        self.watch_since = 1_744_027_190_000_000_000
        self.inactivity_start = None
        self.window_closed = False

    def _replace_ofi(self):
        self.ofi = _Ofi()
        self.ofi_generation += 1

    def _advance_timers(self, timestamp):
        if self.inactivity_start is None and timestamp > self.watch_since + 5_000_000_000:
            self.inactivity_start = self.watch_since
            self._replace_ofi()

    def _close_inactivity(self, end, recovered, position):
        if self.inactivity_start is not None:
            self.intervals.append(
                InactivityInterval(
                    self.inactivity_start,
                    self.inactivity_start + 5_000_000_000 + 1,
                    end,
                    recovered,
                    position,
                )
            )
            self.inactivity_start = None
            _require(len(self.intervals) <= 128, "Constructed inactivity bound exceeded")

    def _end_window(self, position=None):
        if not self.window_closed:
            self._advance_timers(1_744_041_600_000_000_000 - 1)
            self._close_inactivity(1_744_041_600_000_000_000, False, position)
            self.window_closed = True

    def _levels(self, side, limit=None):
        prices = sorted(self.book.levels[side], reverse=side == "B")
        if limit is not None:
            prices = prices[:limit]
        return tuple(PriceLevel(price, self.book.levels[side][price]) for price in prices)

    def _state(self):
        def metric_pairs(counter):
            return tuple(
                sorted(
                    (f"{side}_{metric}", quantity) for (side, metric), quantity in counter.items()
                )
            )

        state = ReconstructedState(
            self.book.initialized,
            tuple(OrderEntry(oid, state) for oid, state in sorted(self.book.orders.items())),
            self._levels("B"),
            self._levels("A"),
            self.last_recv,
            tuple(self.pending),
            tuple(self.trades),
            tuple(position for position, _ in self.capture),
            self.last_quote.quote_ordinal if self.last_quote is not None else None,
            tuple(self.flow.events),
            self.flow.cvd,
            self.flow.known,
            self.flow.unknown,
            self.ofi_generation,
            self.ofi.previous.quote_ordinal if self.ofi.previous is not None else None,
            self.ofi.first_ts,
            tuple(self.ofi.events),
            self.ofi.total,
            self.history_ofi_generation,
            tuple(quote.quote_ordinal for quote in self.history.quotes),
            tuple(tuple(item) for item in self.history.depletions[0]),
            tuple(tuple(item) for item in self.history.depletions[1]),
            tuple(self.history.reloads),
            self.execution.last_ts,
            tuple((timestamp, metric_pairs(values)) for timestamp, values in self.execution.events),
            metric_pairs(self.execution.totals),
            tuple(tuple(item) for item in self.execution.credits["B"]),
            tuple(tuple(item) for item in self.execution.credits["A"]),
            tuple(sorted(self.execution.audit.items())),
            self.next_publication,
            self.watch_since,
            self.inactivity_start,
            self.window_closed,
        )
        _state_metadata(
            state,
            set(range(2, len(self.fixture.payload_bundle.payloads) + 1)),
            set(range(1, len(self.quotes) + 1)),
        )
        _bounded_canonical(_project(state))
        return state

    def _features(self, quote):
        self.ofi.expire(quote.ts_recv_ns)
        self.flow.expire(quote.ts_recv_ns)
        depth = quote.bid_qty + quote.ask_qty
        trade_count = self.flow.known + self.flow.unknown
        values = (
            math.log1p(quote.bid_qty),
            math.log1p(quote.ask_qty),
            (quote.bid_qty - quote.ask_qty) / depth,
            2 * self.ofi.total / depth,
            2 * self.flow.cvd / depth,
            math.log1p(self.flow.known),
            self.flow.unknown / trade_count if trade_count else 0.0,
            math.log1p(quote.prior_quote_gap_ns / 1_000_000),
        )
        history = self.history.features(self.book, self.flow.cvd)
        execution = self.execution.features(quote)
        values += tuple(history[name] for name in _feature_names()[8:23])
        values += tuple(execution[name] for name in _feature_names()[23:])
        _require(all(math.isfinite(value) for value in values), "Nonfinite complete feature row")
        return tuple(zip(_feature_names(), values, strict=True))

    def _observe(self, payload, position, event_ordinal, prefix):
        now = payload.ts_recv
        bid, ask = self.book.best("B"), self.book.best("A")
        _require(
            bid is not None and ask is not None and bid < ask,
            "Incomplete, locked or crossed completed book",
        )
        bid_qty, ask_qty = self.book.levels["B"][bid], self.book.levels["A"][ask]
        _require(
            bid_qty > 0 and ask_qty > 0 and (ask - bid) % 50_000 == 0,
            "Invalid top quantity or spread grid",
        )
        prior_gap = now - self.last_quote.ts_recv_ns if self.last_quote is not None else 0
        self._advance_timers(now)
        self._close_inactivity(now, True, position)
        if self.last_quote is None:
            self._replace_ofi()
        quote = QuoteWitness(
            len(self.quotes) + 1,
            event_ordinal,
            position,
            now,
            bid,
            ask,
            bid_qty,
            ask_qty,
            prior_gap,
            self.ofi_generation,
            self._levels("B", 5),
            self._levels("A", 5),
            prefix,
            "0" * 64,
        )
        quote = QuoteWitness(
            quote.quote_ordinal,
            quote.event_ordinal,
            quote.decoded_position,
            quote.ts_recv_ns,
            quote.bid,
            quote.ask,
            quote.bid_qty,
            quote.ask_qty,
            quote.prior_quote_gap_ns,
            quote.ofi_generation,
            quote.bid_depth5,
            quote.ask_depth5,
            quote.adapter_prefix_sha256,
            _artifact_pin(quote, "quote_sha256"),
        )
        self.ofi.observe(quote)
        if self.history_ofi_generation != self.ofi_generation:
            self.history = _History()
            self.history_ofi_generation = self.ofi_generation
        self.history.observe(quote)
        self.execution.complete(
            [record for _, record in self.capture], self.last_quote, quote, self.book
        )
        self.last_quote = quote
        self.watch_since = now
        self.quotes.append(quote)
        _require(len(self.quotes) <= 127, "Constructed quote bound exceeded")
        publication_ordinal = None
        if (
            not self.window_closed
            and 1_744_027_200_000_000_000 <= now < 1_744_041_600_000_000_000
            and now >= self.next_publication
        ):
            publication = FeaturePublication(
                len(self.publications) + 1,
                quote.quote_ordinal,
                event_ordinal,
                position,
                now,
                prefix,
                self._features(quote),
                "0" * 64,
            )
            publication = FeaturePublication(
                publication.publication_ordinal,
                publication.quote_ordinal,
                publication.event_ordinal,
                publication.decoded_position,
                publication.ts_recv_ns,
                publication.adapter_prefix_sha256,
                publication.features,
                _artifact_pin(publication, "publication_sha256"),
            )
            self.publications.append(publication)
            _require(len(self.publications) <= 32, "Constructed publication bound exceeded")
            publication_ordinal = publication.publication_ordinal
            self.next_publication = now + 1_000_000_000
        return quote.quote_ordinal, publication_ordinal

    def _consume(self, payload, audit, prefix):
        position, now = audit.decoded_position, payload.ts_recv
        snapshot = bool(payload.flags & 32)
        protected = 1_744_027_190_000_000_000 <= now < 1_744_041_600_000_000_000
        before = self.book.orders.get(payload.order_id)
        if protected and not snapshot:
            _require(len(self.capture) < 127, "Constructed captured event bound exceeded")
            self.capture.append((position, _Captured.capture(payload, self.book)))
        _require(
            1_743_984_000_000_000_000 <= now < 1_744_070_400_000_000_000,
            "Target receive outside declared day",
        )
        _require(
            not (snapshot and 1_744_027_200_000_000_000 <= now < 1_744_041_600_000_000_000),
            "Snapshot in selected observation window",
        )
        exceptional = (
            payload.flags == 8
            and payload.action == "R"
            and payload.side == "N"
            and 1_744_059_600_000_000_000 <= now < 1_744_063_200_000_000_000
            and payload.ts_event <= now
        )
        bad = payload.flags & (8 | 4 | 64 | 16)
        if snapshot:
            bad &= ~8
        _require(not bad or exceptional, "Target has bad quality flags")
        if exceptional:
            self.exceptional_clears += 1
            _require(self.exceptional_clears <= 32, "Exceptional closed clear bound exceeded")
        _require(
            not ((self.pending or self.trades) and (payload.action == "R" or snapshot)),
            "Incomplete ordinary event before reset or snapshot",
        )
        self.clock.observe(payload, snapshot, position)
        initialized_before, last_recv_before = self.book.initialized, self.last_recv
        if not snapshot and not exceptional:
            _require(self.last_recv is None or now >= self.last_recv, "Target receive regressed")
            if not self.window_closed:
                self._advance_timers(min(now, 1_744_041_600_000_000_000 - 1))
                if now >= 1_744_041_600_000_000_000:
                    self._end_window(position)
            self.last_recv = now
        _require(
            not (
                payload.action == "R"
                and not snapshot
                and 1_744_027_200_000_000_000 <= now < 1_744_041_600_000_000_000
            ),
            "Live reset in selected observation window",
        )
        self.book.apply(payload)
        ordinal = len(self.transitions) + 1
        event_ordinal = quote_ordinal = publication_ordinal = None
        if payload.action == "R":
            disposition = "target_reset"
            self.flow = _Flow()
            self.last_quote = None
            if not self.window_closed:
                self.execution = _Execution()
                self.capture.clear()
        elif snapshot:
            disposition = "target_snapshot"
            if not self.window_closed:
                self.execution = _Execution()
                self.capture.clear()
        else:
            disposition = "target_record"
            self.pending.append(position)
            if payload.action == "T":
                self.trades.append(position)
            if payload.flags & 128:
                event_ordinal = len(self.events) + 1
                target_positions, trade_positions = tuple(self.pending), tuple(self.trades)
                capture_positions = tuple(pos for pos, _ in self.capture)
                for trade_position in self.trades:
                    self.flow.add(now, self.fixture.payload_bundle.payloads[trade_position - 1])
                self.trades.clear()
                if (
                    self.book.initialized
                    and 1_744_027_190_000_000_000 <= now < 1_744_041_600_000_000_000
                ):
                    quote_ordinal, publication_ordinal = self._observe(
                        payload, position, event_ordinal, prefix
                    )
                event = EventWitness(
                    event_ordinal,
                    position,
                    ordinal,
                    now,
                    target_positions,
                    trade_positions,
                    capture_positions,
                    quote_ordinal,
                    prefix,
                    "0" * 64,
                )
                event = EventWitness(
                    event.event_ordinal,
                    event.closing_decoded_position,
                    event.closing_target_transition_ordinal,
                    event.ts_recv_ns,
                    event.target_positions,
                    event.trade_positions,
                    event.execution_capture_positions,
                    event.quote_ordinal,
                    event.adapter_prefix_sha256,
                    _artifact_pin(event, "event_sha256"),
                )
                self.events.append(event)
                _require(len(self.events) <= 127, "Constructed event bound exceeded")
                self.pending.clear()
                self.capture.clear()
        state_pin = hashlib.sha256(_bounded_canonical(_project(self._state()))).hexdigest()
        transition = TargetTransition(
            position,
            ordinal,
            disposition,
            snapshot,
            exceptional,
            payload.order_id,
            before,
            self.book.orders.get(payload.order_id),
            initialized_before,
            self.book.initialized,
            last_recv_before,
            self.last_recv,
            event_ordinal,
            quote_ordinal,
            publication_ordinal,
            state_pin,
        )
        self.transitions.append(transition)
        _require(len(self.transitions) <= 127, "Constructed transition bound exceeded")
        return disposition, ordinal

    def run(self):
        for audit, payload in zip(
            self.bound.audits, self.fixture.payload_bundle.payloads, strict=True
        ):
            prefix = _adapter_prefix(self.protocol_pin, self.context_pin, audit.bound_prefix_sha256)
            if audit.disposition == "target_candidate":
                disposition, ordinal = self._consume(payload, audit, prefix)
            else:
                disposition, ordinal = audit.disposition, None
            self.audits.append(
                AdapterAudit(
                    audit.decoded_position,
                    disposition,
                    audit.instrument_id,
                    audit.target_candidate_ordinal,
                    ordinal,
                    audit.bound_prefix_sha256,
                    prefix,
                )
            )
        _require(
            self.transitions and not self.pending and not self.trades and not self.capture,
            "Incomplete target, ordinary event, trade or captured terminal state",
        )
        self._end_window()
        _require(
            1 <= len(self.publications) <= 32
            and self.clock.counts["target_records"] == len(self.transitions),
            "Complete publication/clock/target coverage required",
        )
        _require(
            all(
                b.ts_recv_ns - a.ts_recv_ns >= 1_000_000_000
                for a, b in zip(self.publications, self.publications[1:], strict=False)
            ),
            "Publication cadence exceeded",
        )
        return self._state()


def _construct(
    fixture, bound, protocol_pin, context_pin, binding_pin, cursor_pin, fixture_pin=None
):
    computed_fixture_pin = hashlib.sha256(_bounded_canonical(_fixture_body(fixture))).hexdigest()
    if fixture_pin is not None:
        _require(computed_fixture_pin == fixture_pin, "Complete adapter fixture differs")
    engine = _Engine(fixture, bound, protocol_pin, context_pin)
    terminal = engine.run()
    values = (
        "constructed_typed_native_event_adapter_not_native_verification",
        protocol_pin,
        context_pin,
        binding_pin,
        cursor_pin,
        computed_fixture_pin,
        fixture,
        bound,
        tuple(engine.audits),
        tuple(engine.transitions),
        tuple(engine.events),
        tuple(engine.quotes),
        tuple(engine.publications),
        tuple(engine.intervals),
        engine.clock.quality(),
        engine.exceptional_clears,
        terminal,
        _flags(),
    )
    result = AdapterAssessment(*values, "0" * 64)
    result_pin = hashlib.sha256(_bounded_canonical(_assessment_body(result))).hexdigest()
    return AdapterAssessment(*values, result_pin)


@_guard
def fixture_sha256(
    fixture: AdapterFixture,
    *,
    expected_protocol_sha256: str,
    expected_context_sha256: str,
    expected_binding_protocol_sha256: str,
    expected_cursor_protocol_sha256: str,
    expected_cursor_fixture_sha256: str,
    expected_binding_bundle_sha256: str,
) -> str:
    """Pin a fixture only after complete binding, reconstruction and finish."""
    _pins(
        expected_protocol_sha256,
        expected_context_sha256,
        expected_binding_protocol_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
        expected_binding_bundle_sha256,
    )
    _expected_protocols(
        expected_protocol_sha256, expected_binding_protocol_sha256, expected_cursor_protocol_sha256
    )
    _, payload_context_pin = _fixture_metadata(
        fixture,
        expected_context_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
    )
    bound = _late_binding(
        fixture,
        payload_context_pin,
        expected_binding_protocol_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
        expected_binding_bundle_sha256,
    )
    result = _construct(
        fixture,
        bound,
        expected_protocol_sha256,
        expected_context_sha256,
        expected_binding_protocol_sha256,
        expected_cursor_protocol_sha256,
    )
    return result.fixture_sha256


@_guard
def replay(
    fixture: AdapterFixture,
    *,
    expected_protocol_sha256: str,
    expected_context_sha256: str,
    expected_binding_protocol_sha256: str,
    expected_cursor_protocol_sha256: str,
    expected_cursor_fixture_sha256: str,
    expected_binding_bundle_sha256: str,
    expected_fixture_sha256: str,
) -> AdapterAssessment:
    """Reconstruct the complete invented witness with no partial return."""
    _pins(
        expected_protocol_sha256,
        expected_context_sha256,
        expected_binding_protocol_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
        expected_binding_bundle_sha256,
        expected_fixture_sha256,
    )
    _expected_protocols(
        expected_protocol_sha256, expected_binding_protocol_sha256, expected_cursor_protocol_sha256
    )
    _, payload_context_pin = _fixture_metadata(
        fixture,
        expected_context_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
    )
    bound = _late_binding(
        fixture,
        payload_context_pin,
        expected_binding_protocol_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
        expected_binding_bundle_sha256,
    )
    return _construct(
        fixture,
        bound,
        expected_protocol_sha256,
        expected_context_sha256,
        expected_binding_protocol_sha256,
        expected_cursor_protocol_sha256,
        expected_fixture_sha256,
    )


@_guard
def verify(
    assessment: AdapterAssessment,
    fixture: AdapterFixture,
    *,
    expected_protocol_sha256: str,
    expected_context_sha256: str,
    expected_binding_protocol_sha256: str,
    expected_cursor_protocol_sha256: str,
    expected_cursor_fixture_sha256: str,
    expected_binding_bundle_sha256: str,
    expected_fixture_sha256: str,
    expected_assessment_sha256: str,
) -> None:
    """Rebuild original/submitted complete bodies without adopting summaries."""
    _pins(
        expected_protocol_sha256,
        expected_context_sha256,
        expected_binding_protocol_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
        expected_binding_bundle_sha256,
        expected_fixture_sha256,
        expected_assessment_sha256,
    )
    _expected_protocols(
        expected_protocol_sha256, expected_binding_protocol_sha256, expected_cursor_protocol_sha256
    )
    old, payload_context_pin = _fixture_metadata(
        fixture,
        expected_context_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
    )
    _submitted_metadata(
        assessment,
        fixture,
        old,
        payload_context_pin,
        expected_protocol_sha256,
        expected_context_sha256,
        expected_binding_protocol_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
        expected_binding_bundle_sha256,
        expected_fixture_sha256,
        expected_assessment_sha256,
    )
    bound = _late_binding(
        fixture,
        payload_context_pin,
        expected_binding_protocol_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
        expected_binding_bundle_sha256,
        submitted=assessment,
    )
    # Submitted fixture bodies are separately recomputed, not adopted from the
    # nested binding result or the original caller's retained object identities.
    submitted_bundle_pin = binding.bundle_sha256(
        assessment.fixture.payload_bundle,
        expected_protocol_sha256=expected_binding_protocol_sha256,
        expected_context_sha256=payload_context_pin,
        expected_cursor_protocol_sha256=expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256=expected_cursor_fixture_sha256,
    )
    _require(
        submitted_bundle_pin == expected_binding_bundle_sha256, "Submitted fixture bundle differs"
    )
    _require(
        hashlib.sha256(_bounded_canonical(_fixture_body(assessment.fixture))).hexdigest()
        == expected_fixture_sha256,
        "Submitted complete fixture differs",
    )
    rebuilt = _construct(
        fixture,
        bound,
        expected_protocol_sha256,
        expected_context_sha256,
        expected_binding_protocol_sha256,
        expected_cursor_protocol_sha256,
        expected_fixture_sha256,
    )
    supplied_body = _bounded_canonical(_assessment_body(assessment))
    rebuilt_body = _bounded_canonical(_assessment_body(rebuilt))
    _require(
        supplied_body == rebuilt_body
        and rebuilt.assessment_sha256 == expected_assessment_sha256
        and hashlib.sha256(supplied_body).hexdigest() == expected_assessment_sha256,
        "Complete reconstructed adapter assessment differs",
    )
