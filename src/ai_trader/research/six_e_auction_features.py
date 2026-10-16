"""Completed-event tape and prior-price context; no labels, models or orders."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from datetime import UTC, datetime

from ai_trader.training import historical_6e_manifest as data

SECOND = 1_000_000_000
TICK = data.census.study.data.clock.TICK
WINDOWS = (5, 15, 30)
RANGE_SECONDS = 60
MAX_OBSERVATIONS = 500_000
TAPE_FIELDS = (
    "buy_qty",
    "sell_qty",
    "unknown_qty",
    "delta_qty",
    "known_trades",
    "unknown_fraction_qty",
)
FEATURES = (
    "bid_nano",
    "ask_nano",
    "prior_low_nano2",
    "prior_high_nano2",
    "prior_range_ticks",
    "range_ready",
    "prior_quote_count",
    "range_age_seconds",
    *(f"{key}_{window}s" for window in WINDOWS for key in TAPE_FIELDS),
    "diagonal_buy_max_5s",
    "diagonal_sell_max_5s",
    "diagonal_pairs_5s",
    "executed_span_5s_ticks",
    "segment_vwap_nano",
    "segment_vwap_qty",
    "segment_vwap_start_ns",
)


def protocol() -> dict:
    return {
        "version": "six_e_auction_features_v1",
        "features": list(FEATURES),
        "range": "Prior completed quote midpoints in inclusive trailing 60s; excludes current "
        "event, includes earlier equal-receive-time events in original order",
        "range_ready": "60s since fresh state and at least two retained prior quotes",
        "tape": "T records only, observed at enclosing F_LAST completion; F never adds volume",
        "windows_seconds": list(WINDOWS),
        "expiry": "Remove only observations strictly older than now-window",
        "unknown": "Unknown aggressor quantity retained separately; never assigned a side",
        "footprint": "Rolling 5s executions, not a closed candle; diagonal buy(p) versus "
        "sell(p-tick); both positive and combined >=2 contracts; bounded difference/sum",
        "vwap": "Trade-quantity weighted price since first trade at/after 12 UTC in current "
        "unbroken segment; NOT a full-session profile or economic fair value",
        "reset": "Fresh UTC session/dated contract; reset with inherited OFI; "
        "an incomplete event spanning >5s is refused, not silently assigned to a window",
        "max_observations_per_window": MAX_OBSERVATIONS,
        "future_fields_accessed": False,
        "confirmed_icebergs": False,
    }


@dataclass(frozen=True)
class Trade:
    ts: int
    price: int
    size: int
    side: str


class Tape:
    def __init__(self, seconds: int):
        self.seconds = seconds
        self.events: deque[Trade] = deque()
        self.qty = Counter()
        self.counts = Counter()
        self.buy = Counter()
        self.sell = Counter()

    def _change(self, trade: Trade, sign: int) -> None:
        self.qty[trade.side] += sign * trade.size
        self.counts[trade.side] += sign
        levels = self.buy if trade.side == "B" else self.sell if trade.side == "A" else None
        if levels is not None:
            levels[trade.price] += sign * trade.size
            if levels[trade.price] == 0:
                del levels[trade.price]

    def expire(self, now: int) -> None:
        while self.events and self.events[0].ts < now - self.seconds * SECOND:
            self._change(self.events.popleft(), -1)

    def add(self, trade: Trade) -> None:
        if len(self.events) >= MAX_OBSERVATIONS:
            raise ValueError("Auction tape observation bound exceeded")
        self.events.append(trade)
        self._change(trade, 1)

    def values(self) -> tuple:
        buy, sell, unknown = (self.qty[key] for key in ("B", "A", "N"))
        total = buy + sell + unknown
        return (
            buy,
            sell,
            unknown,
            buy - sell,
            self.counts["B"] + self.counts["A"],
            (unknown / total if total else 0.0),
        )


class AuctionFeatures:
    def __init__(self, session: str, contract: str):
        data.role_for_day(session)  # Guard reserved dates before data access.
        if contract != data.census.dated_contract(session):
            raise ValueError("Auction contract differs from dated session")
        self.session, self.contract = session, contract
        self.quotes: deque[tuple[int, int]] = deque()
        self.lows: deque[tuple[int, int]] = deque()
        self.highs: deque[tuple[int, int]] = deque()
        self.tapes = {window: Tape(window) for window in WINDOWS}
        self.first_ts = self.last_ts = None
        self.vwap_numerator = self.vwap_qty = self.vwap_start = 0
        self.snapshot: dict | None = None

    def observe(self, quote, records: list) -> None:
        now, bid, ask = quote.ts_recv_ns, quote.bid, quote.ask
        if type(now) is not int:
            raise ValueError("Auction timestamp requires integer nanoseconds")
        day_start = (now // (86400 * SECOND)) * 86400 * SECOND
        if (
            type(now) is not int
            or datetime.fromtimestamp(now // SECOND, UTC).date().isoformat() != self.session
            or not day_start + (12 * 3600 - 10) * SECOND <= now < day_start + 16 * 3600 * SECOND
            or type(bid) is not int
            or type(ask) is not int
            or bid <= 0
            or ask <= bid
            or bid % TICK
            or ask % TICK
            or (self.last_ts is not None and now < self.last_ts)
        ):
            raise ValueError("Invalid completed auction quote identity, price or order")
        for record in records:
            if type(record.recv) is not int or record.recv > now:
                raise ValueError("Auction event has a future record")
        if records and now - min(record.recv for record in records) > 5 * SECOND:
            raise ValueError("Auction event span exceeds five seconds")
        self.first_ts = now if self.first_ts is None else self.first_ts
        cutoff = now - RANGE_SECONDS * SECOND
        for queue in (self.quotes, self.lows, self.highs):
            while queue and queue[0][0] < cutoff:
                queue.popleft()
        for tape in self.tapes.values():
            tape.expire(now)
        for record in records:
            if record.action != "T":
                continue
            if (
                type(record.size) is not int
                or record.size <= 0
                or type(record.price) is not int
                or record.price <= 0
                or record.price % TICK
                or record.side not in {"A", "B", "N"}
            ):
                raise ValueError("Invalid auction trade size, price or aggressor side")
            trade = Trade(now, record.price, record.size, record.side)
            for tape in self.tapes.values():
                tape.add(trade)
            if now >= day_start + 12 * 3600 * SECOND:
                self.vwap_numerator += trade.price * trade.size
                self.vwap_qty += trade.size
                self.vwap_start = self.vwap_start or now
        mid2 = bid + ask
        low, high = (self.lows[0][1], self.highs[0][1]) if self.quotes else (mid2, mid2)
        values = {
            "bid_nano": bid,
            "ask_nano": ask,
            "prior_low_nano2": low,
            "prior_high_nano2": high,
            "prior_range_ticks": (high - low) / (2 * TICK),
            "range_ready": int(
                now - self.first_ts >= RANGE_SECONDS * SECOND and len(self.quotes) >= 2
            ),
            "prior_quote_count": len(self.quotes),
            "range_age_seconds": min(RANGE_SECONDS, (now - self.first_ts) / SECOND),
        }
        self.snapshot = values
        if len(self.quotes) >= MAX_OBSERVATIONS:
            raise ValueError("Auction prior-quote observation bound exceeded")
        self.quotes.append((now, mid2))
        while self.lows and self.lows[-1][1] >= mid2:
            self.lows.pop()
        while self.highs and self.highs[-1][1] <= mid2:
            self.highs.pop()
        self.lows.append((now, mid2))
        self.highs.append((now, mid2))
        self.last_ts = now

    def features(self, now: int) -> dict:
        if self.last_ts != now or self.snapshot is None:
            raise ValueError("Auction features require the current completed event")
        # Price-level reductions happen only at decision time, not at every quote.
        values = dict(self.snapshot)
        for window, tape in self.tapes.items():
            values.update(
                zip((f"{key}_{window}s" for key in TAPE_FIELDS), tape.values(), strict=True)
            )
        tape = self.tapes[5]
        ratios = [
            (buy - tape.sell[price - TICK]) / (buy + tape.sell[price - TICK])
            for price, buy in tape.buy.items()
            if tape.sell[price - TICK] > 0 and buy + tape.sell[price - TICK] >= 2
        ]
        levels = tape.buy.keys() | tape.sell.keys()
        values.update(
            diagonal_buy_max_5s=max((max(0.0, value) for value in ratios), default=0.0),
            diagonal_sell_max_5s=max((max(0.0, -value) for value in ratios), default=0.0),
            diagonal_pairs_5s=len(ratios),
            executed_span_5s_ticks=(max(levels) - min(levels)) / TICK if levels else 0.0,
            segment_vwap_nano=self.vwap_numerator / self.vwap_qty if self.vwap_qty else 0.0,
            segment_vwap_qty=self.vwap_qty,
            segment_vwap_start_ns=self.vwap_start,
        )
        return values
