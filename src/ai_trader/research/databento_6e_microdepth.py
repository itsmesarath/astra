"""Causal visible-depth and queue-reload proxies for a separately frozen cohort."""

from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from pathlib import Path

from ai_trader.research import databento_6e_cost_targets as base

clock = base.clock
CONFIG_SHA256 = "4e1bdedbc7dbeee654d54d87862ccfc162bdde893f7c4a050a06554e736ddb37"
TRAIN = base.SESSIONS
VALIDATION = ("2025-07-21", "2025-07-22")
TEST = ("2025-07-23", "2025-07-24", "2025-07-25")
SESSIONS = (*TRAIN, *VALIDATION, *TEST)
SOURCE_DAYS = (*base.SOURCE_DAYS, "2025-07-20", *VALIDATION, *TEST)
FEATURES = (
    *base.FEATURES,
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
)


def load_config(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    pin = hashlib.sha256(raw).hexdigest()
    if pin != CONFIG_SHA256:
        raise ValueError("Frozen microdepth configuration changed")
    return json.loads(raw), pin


class QuoteHistory:
    """Observe completed quotes only; never interpret cancellations as proven trades."""

    def __init__(self):
        self.quotes = deque()
        self.depletions = (deque(), deque())
        self.reloads = deque()

    def observe(self, quote: clock.Quote) -> None:
        now = quote.ts_recv_ns
        cutoff = now - clock.FLOW_NS
        previous = self.quotes[-1] if self.quotes else None
        if previous and now < previous.ts_recv_ns:
            raise ValueError("Quote history timestamp regressed")
        matched = [0, 0]
        for index, (price, qty) in enumerate(
            ((quote.bid, quote.bid_qty), (quote.ask, quote.ask_qty))
        ):
            credit = self.depletions[index]
            while credit and credit[0][0] < cutoff:
                credit.popleft()
            if previous is None:
                continue
            old_price, old_qty = (
                (previous.bid, previous.bid_qty) if index == 0 else (previous.ask, previous.ask_qty)
            )
            if price != old_price:
                credit.clear()
                continue
            change = qty - old_qty
            if change < 0:
                credit.append([now, -change])
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

    def features(self, book, cvd: int) -> dict[str, float]:
        quote = self.quotes[-1]
        bid_prices = sorted(book.levels["B"], reverse=True)[:5]
        ask_prices = sorted(book.levels["A"])[:5]
        if (
            not bid_prices
            or not ask_prices
            or (bid_prices[0], ask_prices[0]) != (quote.bid, quote.ask)
        ):
            raise ValueError("Depth book does not match completed quote")
        bid_depth = sum(book.levels["B"][p] for p in bid_prices)
        ask_depth = sum(book.levels["A"][p] for p in ask_prices)
        mids = [(q.bid + q.ask) / (2 * clock.TICK) for q in self.quotes]
        change = mids[-1] - mids[0]
        depth = quote.bid_qty + quote.ask_qty
        values = (
            math.log1p(bid_depth),
            math.log1p(ask_depth),
            (bid_depth - ask_depth) / (bid_depth + ask_depth),
            quote.bid_qty / bid_depth,
            quote.ask_qty / ask_depth,
            (quote.bid - bid_prices[-1]) / clock.TICK,
            (ask_prices[-1] - quote.ask) / clock.TICK,
            change,
            max(mids) - min(mids),
            sum(abs(b - a) for a, b in zip(mids, mids[1:], strict=False)),
            math.log1p(len(mids)),
            sum(r[1] for r in self.reloads) / depth,
            sum(r[2] for r in self.reloads) / depth,
            max(cvd, 0) / (depth * (1 + max(change, 0))),
            max(-cvd, 0) / (depth * (1 + max(-change, 0))),
        )
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Nonfinite microdepth feature")
        return dict(zip(FEATURES[len(base.FEATURES) :], values, strict=True))


class MicrodepthBuilder(base.CostTargetBuilder):
    def __init__(self, sessions: tuple[str, ...] = SESSIONS, minimum_resolved: int = 100):
        super().__init__(sessions, minimum_resolved)

    def start_day(self, day) -> None:
        super().start_day(day)
        self.history = QuoteHistory()
        self.history_ofi = None

    def _observe_completed_quote(self, quote: clock.Quote) -> None:
        super()._observe_completed_quote(quote)
        # The inherited OFI object changes on startup, reset or >5-second inactivity.
        if self.history_ofi is not self.ofi:
            self.history = QuoteHistory()
            self.history_ofi = self.ofi
        self.history.observe(quote)

    def _event_decision(self, quote: clock.Quote) -> None:
        super()._event_decision(quote)
        self.rows[-1]["features"].update(self.history.features(self.book, self.flow.cvd))


def build_targets(config: dict, project_root: Path) -> tuple[list[dict], dict]:
    return base.build_targets(
        config, project_root, builder=MicrodepthBuilder(), source_days=SOURCE_DAYS
    )
