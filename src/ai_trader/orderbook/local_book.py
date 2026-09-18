"""Mutable local order book synchronized with Binance update IDs."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ai_trader.orderbook.depth_update import DepthChange, DepthUpdate
from ai_trader.orderbook.snapshot import BookLevel, PartialDepthSnapshot


class SequenceGapError(RuntimeError):
    """Raised when an expected depth-update sequence is incomplete."""


@dataclass(slots=True)
class LocalOrderBook:
    """An in-memory price-level book initialized from a REST snapshot."""

    symbol: str
    update_id: int
    bids: dict[Decimal, Decimal]
    asks: dict[Decimal, Decimal]

    @classmethod
    def from_snapshot(
        cls,
        symbol: str,
        event: dict[str, object],
    ) -> LocalOrderBook:
        """Initialize state from a Binance order-book snapshot."""
        snapshot = PartialDepthSnapshot.from_event(event)

        book = cls(
            symbol=symbol,
            update_id=snapshot.update_id,
            bids={level.price: level.quantity for level in snapshot.bids},
            asks={level.price: level.quantity for level in snapshot.asks},
        )
        book.validate()
        return book

    def apply(self, update: DepthUpdate) -> bool:
        """Apply one continuous update.

        Return False when the event is already covered by the current
        snapshot or state. Raise SequenceGapError when updates are missing.
        """
        if update.symbol != self.symbol:
            raise ValueError(f"Expected symbol {self.symbol}, received {update.symbol}.")

        if update.final_update_id <= self.update_id:
            return False

        if update.first_update_id > self.update_id + 1:
            raise SequenceGapError(
                f"Expected update ID {self.update_id + 1}, "
                f"received range "
                f"{update.first_update_id}-{update.final_update_id}."
            )

        self._apply_side(self.bids, update.bid_changes)
        self._apply_side(self.asks, update.ask_changes)
        self.update_id = update.final_update_id
        self.validate()
        return True

    @staticmethod
    def _apply_side(
        side: dict[Decimal, Decimal],
        changes: tuple[DepthChange, ...],
    ) -> None:
        """Set absolute quantities, deleting levels whose quantity is zero."""
        for change in changes:
            if change.removes_level:
                side.pop(change.price, None)
            else:
                side[change.price] = change.quantity

    def validate(self) -> None:
        """Reject empty, nonpositive, locked, or crossed state."""
        if not self.symbol:
            raise ValueError("Symbol cannot be empty.")
        if self.update_id < 0:
            raise ValueError("Update ID cannot be negative.")
        if not self.bids:
            raise ValueError("Local book must contain bids.")
        if not self.asks:
            raise ValueError("Local book must contain asks.")
        if any(price <= 0 or quantity <= 0 for price, quantity in self.bids.items()):
            raise ValueError("All bid prices and quantities must be positive.")
        if any(price <= 0 or quantity <= 0 for price, quantity in self.asks.items()):
            raise ValueError("All ask prices and quantities must be positive.")
        if self.best_bid.price >= self.best_ask.price:
            raise ValueError("Local book is locked or crossed.")

    @property
    def best_bid(self) -> BookLevel:
        """Return the current highest bid."""
        price = max(self.bids)
        return BookLevel(price=price, quantity=self.bids[price])

    @property
    def best_ask(self) -> BookLevel:
        """Return the current lowest ask."""
        price = min(self.asks)
        return BookLevel(price=price, quantity=self.asks[price])

    @property
    def spread(self) -> Decimal:
        """Return the current best ask minus best bid."""
        return self.best_ask.price - self.best_bid.price
