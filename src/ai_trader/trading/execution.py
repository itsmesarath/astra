"""Deterministic offline market-order fill simulation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ai_trader.trading.paper_portfolio import (
    FillSide,
    PaperFill,
)

BASIS_POINTS_PER_UNIT = Decimal("10000")


@dataclass(frozen=True, slots=True)
class ExecutionCosts:
    """Explicit fee and adverse-slippage assumptions."""

    taker_fee_bps: Decimal
    slippage_bps: Decimal

    def __post_init__(self) -> None:
        if self.taker_fee_bps < 0:
            raise ValueError("Taker fee cannot be negative.")
        if self.slippage_bps < 0:
            raise ValueError("Slippage cannot be negative.")
        if self.taker_fee_bps >= BASIS_POINTS_PER_UNIT:
            raise ValueError("Taker fee must be below 10000 basis points.")
        if self.slippage_bps >= BASIS_POINTS_PER_UNIT:
            raise ValueError("Slippage must be below 10000 basis points.")


@dataclass(frozen=True, slots=True)
class MarketQuote:
    """Best bid and ask available at one event time."""

    best_bid_usdt: Decimal
    best_ask_usdt: Decimal
    event_time_ms: int

    def __post_init__(self) -> None:
        if self.best_bid_usdt <= 0:
            raise ValueError("Best bid must be greater than zero.")
        if self.best_ask_usdt <= 0:
            raise ValueError("Best ask must be greater than zero.")
        if self.best_bid_usdt >= self.best_ask_usdt:
            raise ValueError("Market quote must have bid below ask.")
        if self.event_time_ms < 0:
            raise ValueError("Market quote event time cannot be negative.")

    @property
    def spread_usdt(self) -> Decimal:
        """Return ask minus bid."""
        return self.best_ask_usdt - self.best_bid_usdt

    @property
    def midpoint_usdt(self) -> Decimal:
        """Return the quoted midpoint."""
        return (self.best_bid_usdt + self.best_ask_usdt) / Decimal("2")


def simulate_market_fill(
    *,
    side: FillSide,
    quantity_btc: Decimal,
    quote: MarketQuote,
    costs: ExecutionCosts,
) -> PaperFill:
    """Simulate spread crossing, adverse slippage, and fees."""
    if quantity_btc <= 0:
        raise ValueError("Market-order quantity must be greater than zero.")

    slippage_fraction = costs.slippage_bps / BASIS_POINTS_PER_UNIT

    if side == "BUY":
        fill_price = quote.best_ask_usdt * (Decimal("1") + slippage_fraction)
    elif side == "SELL":
        fill_price = quote.best_bid_usdt * (Decimal("1") - slippage_fraction)
    else:
        raise ValueError("Market-order side must be BUY or SELL.")

    notional = quantity_btc * fill_price
    fee = notional * costs.taker_fee_bps / BASIS_POINTS_PER_UNIT

    return PaperFill(
        side=side,
        quantity_btc=quantity_btc,
        price_usdt=fill_price,
        fee_usdt=fee,
        event_time_ms=quote.event_time_ms,
    )
