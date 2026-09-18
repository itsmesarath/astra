"""Tests for partial order-book snapshots."""

from decimal import Decimal

import pytest

from ai_trader.orderbook.snapshot import PartialDepthSnapshot


def sample_snapshot() -> dict[str, object]:
    """Return a small, correctly ordered book snapshot."""
    return {
        "lastUpdateId": 123,
        "bids": [
            ["100.00", "2.00"],
            ["99.00", "1.00"],
        ],
        "asks": [
            ["101.00", "3.00"],
            ["102.00", "1.00"],
        ],
    }


def test_calculates_snapshot_metrics() -> None:
    """A valid snapshot should produce exact Decimal metrics."""
    snapshot = PartialDepthSnapshot.from_event(sample_snapshot())

    assert snapshot.update_id == 123
    assert snapshot.best_bid.price == Decimal("100.00")
    assert snapshot.best_ask.price == Decimal("101.00")
    assert snapshot.spread == Decimal("1.00")
    assert snapshot.midpoint == Decimal("100.50")
    assert snapshot.total_bid_quantity == Decimal("3.00")
    assert snapshot.total_ask_quantity == Decimal("4.00")
    assert snapshot.imbalance == Decimal("-1") / Decimal("7")


def test_rejects_incorrect_bid_order() -> None:
    """Bid prices must decrease as their depth increases."""
    event = sample_snapshot()
    event["bids"] = [
        ["99.00", "1.00"],
        ["100.00", "2.00"],
    ]

    with pytest.raises(ValueError, match="strictly descending"):
        PartialDepthSnapshot.from_event(event)


def test_rejects_locked_or_crossed_book() -> None:
    """The best bid must remain strictly below the best ask."""
    event = sample_snapshot()
    event["asks"] = [
        ["100.00", "3.00"],
        ["102.00", "1.00"],
    ]

    with pytest.raises(ValueError, match="locked or crossed"):
        PartialDepthSnapshot.from_event(event)


def test_rejects_zero_quantity_in_snapshot() -> None:
    """Partial snapshots must not contain empty displayed levels."""
    event = sample_snapshot()
    event["bids"] = [
        ["100.00", "0"],
        ["99.00", "1.00"],
    ]

    with pytest.raises(ValueError, match="quantity must be positive"):
        PartialDepthSnapshot.from_event(event)
