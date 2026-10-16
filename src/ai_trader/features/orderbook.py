"""Feature calculations for a synchronized local order book."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ai_trader.orderbook.local_book import LocalOrderBook


@dataclass(frozen=True, slots=True)
class OrderBookFeatures:
    """A deterministic feature snapshot calculated from local-book state."""

    symbol: str
    update_id: int
    levels: int
    best_bid_price: Decimal
    best_ask_price: Decimal
    spread: Decimal
    midpoint: Decimal
    microprice: Decimal
    bid_depth: Decimal
    ask_depth: Decimal
    imbalance: Decimal

    @classmethod
    def from_book(
        cls,
        book: LocalOrderBook,
        *,
        levels: int,
    ) -> OrderBookFeatures:
        """Calculate top-N depth, imbalance, midpoint, and microprice."""
        if levels <= 0:
            raise ValueError("Feature depth must be greater than zero.")
        if len(book.bids) < levels or len(book.asks) < levels:
            raise ValueError(f"Book must contain at least {levels} levels per side.")

        top_bids = sorted(
            book.bids.items(),
            reverse=True,
        )[:levels]
        top_asks = sorted(book.asks.items())[:levels]

        bid_depth = sum(
            (quantity for _, quantity in top_bids),
            Decimal("0"),
        )
        ask_depth = sum(
            (quantity for _, quantity in top_asks),
            Decimal("0"),
        )
        total_depth = bid_depth + ask_depth

        imbalance = (bid_depth - ask_depth) / total_depth if total_depth else Decimal("0")

        best_bid = book.best_bid
        best_ask = book.best_ask
        best_total_quantity = best_bid.quantity + best_ask.quantity

        microprice = (
            best_ask.price * best_bid.quantity + best_bid.price * best_ask.quantity
        ) / best_total_quantity

        return cls(
            symbol=book.symbol,
            update_id=book.update_id,
            levels=levels,
            best_bid_price=best_bid.price,
            best_ask_price=best_ask.price,
            spread=book.spread,
            midpoint=(best_bid.price + best_ask.price) / 2,
            microprice=microprice,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            imbalance=imbalance,
        )
