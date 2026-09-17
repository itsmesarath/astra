"""Typed representation of a Binance aggregate-trade event."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True, slots=True)
class AggTrade:
    """A validated aggregate trade received from Binance."""

    event_time_ms: int
    symbol: str
    aggregate_trade_id: int
    price: Decimal
    quantity: Decimal
    first_trade_id: int
    last_trade_id: int
    trade_time_ms: int
    buyer_is_maker: bool

    @classmethod
    def from_event(cls, event: Mapping[str, object]) -> AggTrade:
        """Convert a raw Binance event into a validated aggregate trade."""
        if event.get("e") != "aggTrade":
            raise ValueError("Expected an aggTrade event.")

        buyer_is_maker = event["m"]
        if not isinstance(buyer_is_maker, bool):
            raise TypeError("Field 'm' must be a Boolean.")

        trade = cls(
            event_time_ms=int(str(event["E"])),
            symbol=str(event["s"]),
            aggregate_trade_id=int(str(event["a"])),
            price=Decimal(str(event["p"])),
            quantity=Decimal(str(event["q"])),
            first_trade_id=int(str(event["f"])),
            last_trade_id=int(str(event["l"])),
            trade_time_ms=int(str(event["T"])),
            buyer_is_maker=buyer_is_maker,
        )
        trade.validate()
        return trade

    def validate(self) -> None:
        """Reject impossible or unsupported values."""
        if not self.symbol:
            raise ValueError("Symbol cannot be empty.")
        if self.aggregate_trade_id < 0:
            raise ValueError("Aggregate trade ID cannot be negative.")
        if self.price <= 0:
            raise ValueError("Price must be positive.")
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive.")
        if self.first_trade_id > self.last_trade_id:
            raise ValueError("First trade ID cannot exceed last trade ID.")

    @property
    def aggressor_side(self) -> Literal["BUY", "SELL"]:
        """Return the side of the incoming taker order."""
        return "SELL" if self.buyer_is_maker else "BUY"

    @property
    def underlying_trade_count(self) -> int:
        """Return how many raw trades were aggregated into this event."""
        return self.last_trade_id - self.first_trade_id + 1
