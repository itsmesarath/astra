"""Trade-flow features calculated from aggregate trades."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ai_trader.ingestion.agg_trade import AggTrade


@dataclass(frozen=True, slots=True)
class TradeFlowFeatures:
    """Immutable summary of aggregate trades in one observation interval."""

    symbol: str
    aggregate_trade_count: int
    underlying_trade_count: int
    buy_base_volume: Decimal
    sell_base_volume: Decimal
    buy_quote_volume: Decimal
    sell_quote_volume: Decimal

    @property
    def total_base_volume(self) -> Decimal:
        """Return total traded quantity in the base asset."""
        return self.buy_base_volume + self.sell_base_volume

    @property
    def signed_base_volume(self) -> Decimal:
        """Return buyer-initiated minus seller-initiated base volume."""
        return self.buy_base_volume - self.sell_base_volume

    @property
    def total_quote_volume(self) -> Decimal:
        """Return total traded notional value in the quote asset."""
        return self.buy_quote_volume + self.sell_quote_volume

    @property
    def signed_quote_volume(self) -> Decimal:
        """Return buyer-initiated minus seller-initiated quote volume."""
        return self.buy_quote_volume - self.sell_quote_volume

    @property
    def base_volume_imbalance(self) -> Decimal:
        """Return signed base volume divided by total base volume."""
        total_volume = self.total_base_volume
        if total_volume == 0:
            return Decimal("0")

        return self.signed_base_volume / total_volume


@dataclass(slots=True)
class TradeFlowAccumulator:
    """Accumulate trade-flow statistics for one symbol."""

    symbol: str
    aggregate_trade_count: int = 0
    underlying_trade_count: int = 0
    buy_base_volume: Decimal = Decimal("0")
    sell_base_volume: Decimal = Decimal("0")
    buy_quote_volume: Decimal = Decimal("0")
    sell_quote_volume: Decimal = Decimal("0")

    def add(self, trade: AggTrade) -> None:
        """Add one validated aggregate trade."""
        if trade.symbol != self.symbol:
            raise ValueError(f"Expected symbol {self.symbol}, received {trade.symbol}.")

        quote_volume = trade.price * trade.quantity

        self.aggregate_trade_count += 1
        self.underlying_trade_count += trade.underlying_trade_count

        if trade.aggressor_side == "BUY":
            self.buy_base_volume += trade.quantity
            self.buy_quote_volume += quote_volume
        else:
            self.sell_base_volume += trade.quantity
            self.sell_quote_volume += quote_volume

    def snapshot(self) -> TradeFlowFeatures:
        """Return an immutable copy of the accumulated features."""
        return TradeFlowFeatures(
            symbol=self.symbol,
            aggregate_trade_count=self.aggregate_trade_count,
            underlying_trade_count=self.underlying_trade_count,
            buy_base_volume=self.buy_base_volume,
            sell_base_volume=self.sell_base_volume,
            buy_quote_volume=self.buy_quote_volume,
            sell_quote_volume=self.sell_quote_volume,
        )

    def reset(self) -> None:
        """Clear the interval while retaining its configured symbol."""
        self.aggregate_trade_count = 0
        self.underlying_trade_count = 0
        self.buy_base_volume = Decimal("0")
        self.sell_base_volume = Decimal("0")
        self.buy_quote_volume = Decimal("0")
        self.sell_quote_volume = Decimal("0")
