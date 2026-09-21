"""Receipt-causal L2/trade evidence, not proof of hidden orders or trading signals.

CVD includes only aggregate trades observed in this capture. Cross-stream matching
is a heuristic: trade time must lie strictly after the previous applied depth event
and no later than the current one. Late trades never rewrite earlier observations.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from ai_trader.features.orderbook import OrderBookFeatures
from ai_trader.ingestion.agg_trade import AggTrade
from ai_trader.orderbook.depth_update import DepthUpdate
from ai_trader.orderbook.local_book import LocalOrderBook

ZERO = Decimal(0)
BPS = Decimal(10000)


@dataclass(frozen=True, slots=True)
class MicrostructureConfig:
    levels: int = 5
    rolling_window_ms: int = 10_000
    liquidity_band_bps: Decimal = Decimal(10)
    maximum_evidence_interval_ms: int = 1_000
    retained_depth_fraction: Decimal = Decimal("0.8")
    repeated_intervals: int = 3
    maximum_buffered_trades: int = 100_000

    def validate(self) -> None:
        for value in (
            self.levels,
            self.rolling_window_ms,
            self.maximum_evidence_interval_ms,
            self.repeated_intervals,
            self.maximum_buffered_trades,
        ):
            if type(value) is not int or value <= 0:
                raise ValueError("Microstructure counts and durations must be positive integers.")
        if (
            not isinstance(self.liquidity_band_bps, Decimal)
            or not self.liquidity_band_bps.is_finite()
            or not ZERO < self.liquidity_band_bps < BPS
        ):
            raise ValueError("Liquidity band must be a finite Decimal between 0 and 10000 bps.")
        if (
            not isinstance(self.retained_depth_fraction, Decimal)
            or not self.retained_depth_fraction.is_finite()
            or not ZERO < self.retained_depth_fraction <= 1
        ):
            raise ValueError("Retained depth fraction must be a finite Decimal in (0, 1].")


@dataclass(frozen=True, slots=True)
class PassiveSideEvidence:
    price: Decimal
    displayed_before: Decimal
    displayed_after: Decimal
    aggressive_volume_at_price: Decimal
    net_addition_proxy: Decimal
    absorption_candidate: bool
    consecutive_replenishment_intervals: int
    repeated_replenishment_candidate: bool


@dataclass(frozen=True, slots=True)
class MicrostructureObservation:
    source_session: str
    received_at_ns: int
    depth_event_time_ms: int
    book: OrderBookFeatures
    session_cvd_base: Decimal
    session_cvd_quote: Decimal
    rolling_buy_base: Decimal
    rolling_sell_base: Decimal
    rolling_cvd_base: Decimal
    rolling_trade_count: int
    rolling_window_complete: bool
    bid_band_depth: Decimal
    ask_band_depth: Decimal
    bid_band_covered: bool
    ask_band_covered: bool
    bid_top_n_covered: bool
    ask_top_n_covered: bool
    top_level_order_flow_imbalance: Decimal | None
    evidence_interval_ms: int | None
    evidence_interval_valid: bool
    unmatched_trade_count: int
    pending_trade_count: int
    bid: PassiveSideEvidence | None
    ask: PassiveSideEvidence | None


def _number(value: object, *, allow_zero: bool = False) -> None:
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or value < 0
        or (not allow_zero and value == 0)
    ):
        raise ValueError("Prices/quantities must be finite Decimals with valid signs.")


def _integer(value: object) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("Timestamps and identifiers must be nonnegative integers.")


class MicrostructureEngine:
    """One session, one synchronized book; any rejected event invalidates this engine.

    Create a new engine from a fresh snapshot after a gap or malformed event. Receipt
    times must be nondecreasing. The first applied depth establishes the evidence
    baseline; snapshot timing cannot support execution attribution.
    """

    def __init__(
        self,
        source_session: str,
        book: LocalOrderBook,
        config: MicrostructureConfig | None = None,
    ) -> None:
        config = config or MicrostructureConfig()
        config.validate()
        if not isinstance(source_session, str) or not source_session.strip():
            raise ValueError("Source session is required.")
        _integer(book.update_id)
        for side in (book.bids, book.asks):
            for price, quantity in side.items():
                _number(price)
                _number(quantity)
        book.validate()
        self._book = LocalOrderBook(book.symbol, book.update_id, dict(book.bids), dict(book.asks))
        self._initial_bid_boundary = min(book.bids)
        self._initial_ask_boundary = max(book.asks)
        self.source_session, self.config = source_session, config
        self.valid = True
        self._received = -1
        self._first_received: int | None = None
        self._last_trade: AggTrade | None = None
        self._depth_time: int | None = None
        self._pending: list[AggTrade] = []
        self._rolling: deque[tuple[int, AggTrade]] = deque()
        self._cvd_base = self._cvd_quote = ZERO
        self._bid_streak = self._ask_streak = 0

    def _receipt(self, received_at_ns: int) -> None:
        if not self.valid:
            raise ValueError("Engine invalidated; start a new synchronized session.")
        _integer(received_at_ns)
        if received_at_ns < self._received:
            raise ValueError("Receipt time moved backwards.")
        self._received = received_at_ns
        if self._first_received is None:
            self._first_received = received_at_ns
        cutoff = received_at_ns - self.config.rolling_window_ms * 1_000_000
        while self._rolling and self._rolling[0][0] <= cutoff:
            self._rolling.popleft()

    def add_trade(self, trade: AggTrade, *, received_at_ns: int) -> None:
        """Require contiguous aggregate IDs; duplicates/gaps invalidate CVD."""
        try:
            with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
                self._receipt(received_at_ns)
                for value in (
                    trade.event_time_ms,
                    trade.trade_time_ms,
                    trade.aggregate_trade_id,
                    trade.first_trade_id,
                    trade.last_trade_id,
                ):
                    _integer(value)
                _number(trade.price)
                _number(trade.quantity)
                if type(trade.buyer_is_maker) is not bool:
                    raise ValueError("Trade maker flag must be boolean.")
                trade.validate()
                if trade.symbol != self._book.symbol:
                    raise ValueError("Trade symbol mismatch.")
                if self._last_trade is not None:
                    if trade.aggregate_trade_id != self._last_trade.aggregate_trade_id + 1:
                        raise ValueError("Aggregate trade sequence is not contiguous.")
                    if trade.trade_time_ms < self._last_trade.trade_time_ms:
                        raise ValueError("Trade time moved backwards.")
                if (
                    max(len(self._pending), len(self._rolling))
                    >= self.config.maximum_buffered_trades
                ):
                    raise ValueError("Trade buffer limit reached; evidence is incomplete.")
                direction = -1 if trade.buyer_is_maker else 1
                self._cvd_base += direction * trade.quantity
                self._cvd_quote += direction * trade.quantity * trade.price
                self._pending.append(trade)
                self._rolling.append((received_at_ns, trade))
                self._last_trade = trade
        except Exception:
            self.valid = False
            raise

    def apply_depth(
        self, update: DepthUpdate, *, received_at_ns: int
    ) -> MicrostructureObservation | None:
        """Apply absolute quantities; stale depth does not emit or consume evidence."""
        try:
            with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
                return self._apply_depth(update, received_at_ns)
        except Exception:
            self.valid = False
            raise

    def _apply_depth(
        self, update: DepthUpdate, received_at_ns: int
    ) -> MicrostructureObservation | None:
        self._receipt(received_at_ns)
        for value in (update.event_time_ms, update.first_update_id, update.final_update_id):
            _integer(value)
        update.validate()
        for changes in (update.bid_changes, update.ask_changes):
            if len({c.price for c in changes}) != len(changes):
                raise ValueError("Duplicate price in depth side.")
            for change in changes:
                _number(change.price)
                _number(change.quantity, allow_zero=True)
        before = self._book
        after = LocalOrderBook(
            before.symbol, before.update_id, dict(before.bids), dict(before.asks)
        )
        if not after.apply(update):
            return None
        if (
            after.best_bid.price < self._initial_bid_boundary
            or after.best_ask.price > self._initial_ask_boundary
        ):
            raise ValueError("Best quote left known snapshot coverage; resynchronization required.")
        if self._depth_time is not None and update.event_time_ms < self._depth_time:
            raise ValueError("Applied depth time moved backwards.")
        book_features = OrderBookFeatures.from_book(after, levels=self.config.levels)
        interval = None if self._depth_time is None else update.event_time_ms - self._depth_time
        valid_interval = (
            interval is not None and 0 < interval <= self.config.maximum_evidence_interval_ms
        )
        matched: list[AggTrade] = []
        future: list[AggTrade] = []
        unmatched = 0
        for trade in self._pending:
            if trade.trade_time_ms > update.event_time_ms:
                future.append(trade)
            elif valid_interval and self._depth_time < trade.trade_time_ms:
                matched.append(trade)
            else:
                unmatched += 1
        bid = ask = None
        ofi = None
        if valid_interval:
            bid = self._side_evidence(before.bids, after.bids, matched, True, self._bid_streak)
            ask = self._side_evidence(before.asks, after.asks, matched, False, self._ask_streak)
            # Best-queue OFI: additions/improvements bid-positive, ask-negative.
            old_bid, new_bid = before.best_bid, after.best_bid
            old_ask, new_ask = before.best_ask, after.best_ask
            ofi = (
                (new_bid.quantity if new_bid.price >= old_bid.price else ZERO)
                - (old_bid.quantity if new_bid.price <= old_bid.price else ZERO)
                - (new_ask.quantity if new_ask.price <= old_ask.price else ZERO)
                + (old_ask.quantity if new_ask.price >= old_ask.price else ZERO)
            )
        self._bid_streak = bid.consecutive_replenishment_intervals if bid else 0
        self._ask_streak = ask.consecutive_replenishment_intervals if ask else 0
        self._pending = future
        self._book, self._depth_time = after, update.event_time_ms
        buy = sum((t.quantity for _, t in self._rolling if not t.buyer_is_maker), ZERO)
        sell = sum((t.quantity for _, t in self._rolling if t.buyer_is_maker), ZERO)
        bid_limit = after.best_bid.price * (1 - self.config.liquidity_band_bps / BPS)
        ask_limit = after.best_ask.price * (1 + self.config.liquidity_band_bps / BPS)
        return MicrostructureObservation(
            self.source_session,
            received_at_ns,
            update.event_time_ms,
            book_features,
            self._cvd_base,
            self._cvd_quote,
            buy,
            sell,
            buy - sell,
            len(self._rolling),
            received_at_ns - self._first_received >= self.config.rolling_window_ms * 1_000_000,
            sum((q for p, q in after.bids.items() if p >= bid_limit), ZERO),
            sum((q for p, q in after.asks.items() if p <= ask_limit), ZERO),
            self._initial_bid_boundary <= bid_limit,
            self._initial_ask_boundary >= ask_limit,
            sorted(after.bids, reverse=True)[self.config.levels - 1] >= self._initial_bid_boundary,
            sorted(after.asks)[self.config.levels - 1] <= self._initial_ask_boundary,
            ofi,
            interval,
            valid_interval,
            unmatched,
            len(future),
            bid,
            ask,
        )

    def _side_evidence(
        self,
        before: dict[Decimal, Decimal],
        after: dict[Decimal, Decimal],
        trades: list[AggTrade],
        is_bid: bool,
        streak: int,
    ) -> PassiveSideEvidence:
        old_price = max(before) if is_bid else min(before)
        new_price = max(after) if is_bid else min(after)
        old_quantity = before[old_price]
        new_quantity = after.get(old_price, ZERO)
        executed = sum(
            (
                trade.quantity
                for trade in trades
                if trade.price == old_price and trade.buyer_is_maker == is_bid
            ),
            ZERO,
        )
        addition = max(ZERO, new_quantity - old_quantity + executed)
        replenished = old_price == new_price and executed > 0 and addition > 0
        count = streak + 1 if replenished else 0
        return PassiveSideEvidence(
            old_price,
            old_quantity,
            new_quantity,
            executed,
            addition,
            old_price == new_price
            and executed >= old_quantity
            and new_quantity >= old_quantity * self.config.retained_depth_fraction,
            count,
            count >= self.config.repeated_intervals,
        )
