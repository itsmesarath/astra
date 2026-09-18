"""Validated representation of a partial order-book snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from itertools import pairwise


@dataclass(frozen=True, slots=True)
class BookLevel:
    """One displayed price level and its available base-asset quantity."""

    price: Decimal
    quantity: Decimal

    def validate(self) -> None:
        """Reject impossible values in a partial snapshot."""
        if self.price <= 0:
            raise ValueError("Book-level price must be positive.")
        if self.quantity <= 0:
            raise ValueError("Book-level quantity must be positive.")


def parse_side(raw_side: object, side_name: str) -> tuple[BookLevel, ...]:
    """Convert one raw Binance book side into validated levels."""
    if not isinstance(raw_side, list):
        raise TypeError(f"{side_name} must be a list.")

    levels: list[BookLevel] = []

    for index, raw_level in enumerate(raw_side):
        if not isinstance(raw_level, list) or len(raw_level) != 2:
            raise ValueError(f"{side_name} level {index} must contain price and quantity.")

        try:
            level = BookLevel(
                price=Decimal(str(raw_level[0])),
                quantity=Decimal(str(raw_level[1])),
            )
        except (InvalidOperation, ValueError) as error:
            raise ValueError(f"{side_name} level {index} contains an invalid number.") from error

        level.validate()
        levels.append(level)

    return tuple(levels)


@dataclass(frozen=True, slots=True)
class PartialDepthSnapshot:
    """A complete top-N snapshot from Binance's partial-depth stream."""

    update_id: int
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]

    @classmethod
    def from_event(cls, event: Mapping[str, object]) -> PartialDepthSnapshot:
        """Convert a raw Binance partial-depth event into a snapshot."""
        snapshot = cls(
            update_id=int(str(event["lastUpdateId"])),
            bids=parse_side(event["bids"], "bids"),
            asks=parse_side(event["asks"], "asks"),
        )
        snapshot.validate()
        return snapshot

    def validate(self) -> None:
        """Check ordering and ensure that the book is not crossed."""
        if self.update_id < 0:
            raise ValueError("Update ID cannot be negative.")
        if not self.bids:
            raise ValueError("Snapshot must contain bids.")
        if not self.asks:
            raise ValueError("Snapshot must contain asks.")

        if any(left.price <= right.price for left, right in pairwise(self.bids)):
            raise ValueError("Bid prices must be strictly descending.")

        if any(left.price >= right.price for left, right in pairwise(self.asks)):
            raise ValueError("Ask prices must be strictly ascending.")

        if self.best_bid.price >= self.best_ask.price:
            raise ValueError("Snapshot is locked or crossed.")

    @property
    def best_bid(self) -> BookLevel:
        """Return the highest-priced bid."""
        return self.bids[0]

    @property
    def best_ask(self) -> BookLevel:
        """Return the lowest-priced ask."""
        return self.asks[0]

    @property
    def spread(self) -> Decimal:
        """Return the best ask minus the best bid."""
        return self.best_ask.price - self.best_bid.price

    @property
    def midpoint(self) -> Decimal:
        """Return the midpoint between the best bid and ask."""
        return (self.best_bid.price + self.best_ask.price) / 2

    @property
    def total_bid_quantity(self) -> Decimal:
        """Return displayed base quantity across all included bid levels."""
        return sum(
            (level.quantity for level in self.bids),
            Decimal("0"),
        )

    @property
    def total_ask_quantity(self) -> Decimal:
        """Return displayed base quantity across all included ask levels."""
        return sum(
            (level.quantity for level in self.asks),
            Decimal("0"),
        )

    @property
    def imbalance(self) -> Decimal:
        """Return quantity imbalance in the closed interval [-1, 1]."""
        total_quantity = self.total_bid_quantity + self.total_ask_quantity
        if total_quantity == 0:
            return Decimal("0")

        return (self.total_bid_quantity - self.total_ask_quantity) / total_quantity
