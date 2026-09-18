"""Tests for synchronized order-book features."""

from decimal import Decimal

import pytest

from ai_trader.features.orderbook import OrderBookFeatures
from ai_trader.orderbook.local_book import LocalOrderBook


def sample_book() -> LocalOrderBook:
    """Return a small deterministic local book."""
    return LocalOrderBook.from_snapshot(
        "BTCUSDT",
        {
            "lastUpdateId": 100,
            "bids": [
                ["100", "2"],
                ["99", "1"],
            ],
            "asks": [
                ["101", "3"],
                ["102", "1"],
            ],
        },
    )


def test_calculates_exact_top_two_features() -> None:
    """Feature values should use exact decimal arithmetic."""
    features = OrderBookFeatures.from_book(
        sample_book(),
        levels=2,
    )

    assert features.symbol == "BTCUSDT"
    assert features.update_id == 100
    assert features.spread == Decimal("1")
    assert features.midpoint == Decimal("100.5")
    assert features.microprice == Decimal("100.4")
    assert features.bid_depth == Decimal("3")
    assert features.ask_depth == Decimal("4")
    assert features.imbalance == Decimal("-1") / Decimal("7")


def test_feature_depth_changes_imbalance() -> None:
    """Top-one and top-two imbalance are distinct measurements."""
    book = sample_book()

    top_one = OrderBookFeatures.from_book(book, levels=1)
    top_two = OrderBookFeatures.from_book(book, levels=2)

    assert top_one.imbalance == Decimal("-1") / Decimal("5")
    assert top_two.imbalance == Decimal("-1") / Decimal("7")
    assert top_one.imbalance != top_two.imbalance


def test_rejects_nonpositive_feature_depth() -> None:
    """A feature window must contain at least one level."""
    with pytest.raises(ValueError, match="greater than zero"):
        OrderBookFeatures.from_book(sample_book(), levels=0)


def test_rejects_insufficient_book_depth() -> None:
    """Requested depth must be available on both book sides."""
    with pytest.raises(ValueError, match="at least 3 levels"):
        OrderBookFeatures.from_book(sample_book(), levels=3)
