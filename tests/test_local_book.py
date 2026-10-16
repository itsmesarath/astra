"""Tests for local order-book state transitions."""

from decimal import Decimal

import pytest

from ai_trader.orderbook.depth_update import DepthUpdate
from ai_trader.orderbook.local_book import LocalOrderBook, SequenceGapError


def snapshot_event() -> dict[str, object]:
    """Return a small synchronized snapshot."""
    return {
        "lastUpdateId": 100,
        "bids": [
            ["100", "2"],
            ["99", "1"],
        ],
        "asks": [
            ["101", "3"],
            ["102", "1"],
        ],
    }


def depth_event(
    first_id: int,
    final_id: int,
    *,
    symbol: str = "BTCUSDT",
    bids: list[list[str]] | None = None,
    asks: list[list[str]] | None = None,
) -> dict[str, object]:
    """Return a configurable differential-depth event."""
    return {
        "e": "depthUpdate",
        "E": 1000,
        "s": symbol,
        "U": first_id,
        "u": final_id,
        "b": bids or [],
        "a": asks or [],
    }


def test_initializes_from_snapshot() -> None:
    """Snapshot data should initialize exact book state."""
    book = LocalOrderBook.from_snapshot("BTCUSDT", snapshot_event())

    assert book.update_id == 100
    assert book.best_bid.price == Decimal("100")
    assert book.best_ask.price == Decimal("101")
    assert book.spread == Decimal("1")


def test_applies_absolute_changes_and_removals() -> None:
    """Updates should replace quantities and delete zero-quantity levels."""
    book = LocalOrderBook.from_snapshot("BTCUSDT", snapshot_event())
    update = DepthUpdate.from_event(
        depth_event(
            101,
            102,
            bids=[
                ["100", "0"],
                ["99.5", "4"],
            ],
            asks=[
                ["101", "2"],
            ],
        )
    )

    assert book.apply(update)
    assert book.update_id == 102
    assert Decimal("100") not in book.bids
    assert book.bids[Decimal("99.5")] == Decimal("4")
    assert book.asks[Decimal("101")] == Decimal("2")
    assert book.best_bid.price == Decimal("99.5")


def test_ignores_update_already_covered_by_snapshot() -> None:
    """Events ending at the snapshot ID or earlier should be ignored."""
    book = LocalOrderBook.from_snapshot("BTCUSDT", snapshot_event())
    update = DepthUpdate.from_event(
        depth_event(
            99,
            100,
            bids=[["100", "0"]],
        )
    )

    assert not book.apply(update)
    assert book.update_id == 100
    assert book.best_bid.price == Decimal("100")


def test_accepts_update_bridging_snapshot_id() -> None:
    """The first useful buffered event may overlap the snapshot ID."""
    book = LocalOrderBook.from_snapshot("BTCUSDT", snapshot_event())
    update = DepthUpdate.from_event(
        depth_event(
            99,
            101,
            bids=[["100", "5"]],
        )
    )

    assert book.apply(update)
    assert book.update_id == 101
    assert book.bids[Decimal("100")] == Decimal("5")


def test_rejects_sequence_gap_without_modifying_book() -> None:
    """A missing update ID must force reconstruction to restart."""
    book = LocalOrderBook.from_snapshot("BTCUSDT", snapshot_event())
    original_bids = book.bids.copy()

    update = DepthUpdate.from_event(
        depth_event(
            102,
            103,
            bids=[["100", "0"]],
        )
    )

    with pytest.raises(SequenceGapError, match="Expected update ID 101"):
        book.apply(update)

    assert book.update_id == 100
    assert book.bids == original_bids


def test_rejects_wrong_symbol() -> None:
    """Updates from another market must never enter this book."""
    book = LocalOrderBook.from_snapshot("BTCUSDT", snapshot_event())
    update = DepthUpdate.from_event(
        depth_event(
            101,
            101,
            symbol="ETHUSDT",
        )
    )

    with pytest.raises(ValueError, match="Expected symbol BTCUSDT"):
        book.apply(update)
