"""Validated representation of a Binance differential-depth event."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal


@dataclass(frozen=True, slots=True)
class DepthChange:
    """The new absolute quantity for one order-book price level."""

    price: Decimal
    quantity: Decimal

    def validate(self) -> None:
        """Reject impossible price or quantity values."""
        if self.price <= 0:
            raise ValueError("Depth-change price must be positive.")
        if self.quantity < 0:
            raise ValueError("Depth-change quantity cannot be negative.")

    @property
    def removes_level(self) -> bool:
        """Return whether this change deletes the price level."""
        return self.quantity == 0


def parse_changes(
    raw_changes: object,
    side_name: str,
) -> tuple[DepthChange, ...]:
    """Convert one raw side into validated absolute-quantity changes."""
    if not isinstance(raw_changes, list):
        raise TypeError(f"{side_name} changes must be a list.")

    changes: list[DepthChange] = []

    for index, raw_change in enumerate(raw_changes):
        if not isinstance(raw_change, list) or len(raw_change) != 2:
            raise ValueError(f"{side_name} change {index} must contain price and quantity.")

        try:
            change = DepthChange(
                price=Decimal(str(raw_change[0])),
                quantity=Decimal(str(raw_change[1])),
            )
        except (InvalidOperation, ValueError) as error:
            raise ValueError(f"{side_name} change {index} contains an invalid number.") from error

        change.validate()
        changes.append(change)

    return tuple(changes)


@dataclass(frozen=True, slots=True)
class DepthUpdate:
    """One validated Binance differential-depth event."""

    event_time_ms: int
    symbol: str
    first_update_id: int
    final_update_id: int
    bid_changes: tuple[DepthChange, ...]
    ask_changes: tuple[DepthChange, ...]

    @classmethod
    def from_event(cls, event: Mapping[str, object]) -> DepthUpdate:
        """Convert a raw Binance event into a validated depth update."""
        if event.get("e") != "depthUpdate":
            raise ValueError("Expected a depthUpdate event.")

        update = cls(
            event_time_ms=int(str(event["E"])),
            symbol=str(event["s"]),
            first_update_id=int(str(event["U"])),
            final_update_id=int(str(event["u"])),
            bid_changes=parse_changes(event["b"], "bid"),
            ask_changes=parse_changes(event["a"], "ask"),
        )
        update.validate()
        return update

    def validate(self) -> None:
        """Reject invalid identifiers and metadata."""
        if self.event_time_ms < 0:
            raise ValueError("Event time cannot be negative.")
        if not self.symbol:
            raise ValueError("Symbol cannot be empty.")
        if self.first_update_id < 0:
            raise ValueError("First update ID cannot be negative.")
        if self.final_update_id < self.first_update_id:
            raise ValueError("Final update ID cannot precede first update ID.")

    @property
    def total_changes(self) -> int:
        """Return the number of bid and ask price levels changed."""
        return len(self.bid_changes) + len(self.ask_changes)

    @property
    def bid_removals(self) -> int:
        """Return the number of bid price levels deleted."""
        return sum(change.removes_level for change in self.bid_changes)

    @property
    def ask_removals(self) -> int:
        """Return the number of ask price levels deleted."""
        return sum(change.removes_level for change in self.ask_changes)

    def sequence_relation(
        self,
        previous_final_update_id: int,
    ) -> Literal["OK", "OVERLAP", "GAP"]:
        """Classify this event relative to a prior final update ID."""
        if self.first_update_id == previous_final_update_id + 1:
            return "OK"
        if self.first_update_id <= previous_final_update_id:
            return "OVERLAP"
        return "GAP"
