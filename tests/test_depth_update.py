"""Tests for Binance differential-depth updates."""

from decimal import Decimal

import pytest

from ai_trader.orderbook.depth_update import DepthUpdate


def sample_update() -> dict[str, object]:
    """Return a representative differential-depth event."""
    return {
        "e": "depthUpdate",
        "E": 1000,
        "s": "BTCUSDT",
        "U": 10,
        "u": 12,
        "b": [
            ["100.00", "2.00"],
            ["99.00", "0"],
        ],
        "a": [
            ["101.00", "3.00"],
        ],
    }


def test_parses_depth_update() -> None:
    """A valid update should preserve exact quantities and identifiers."""
    update = DepthUpdate.from_event(sample_update())

    assert update.symbol == "BTCUSDT"
    assert update.first_update_id == 10
    assert update.final_update_id == 12
    assert update.bid_changes[0].price == Decimal("100.00")
    assert update.total_changes == 3
    assert update.bid_removals == 1
    assert update.ask_removals == 0


def test_classifies_sequence_relationships() -> None:
    """Continuity, overlap, and gaps should be distinguished."""
    update = DepthUpdate.from_event(sample_update())

    assert update.sequence_relation(9) == "OK"
    assert update.sequence_relation(10) == "OVERLAP"
    assert update.sequence_relation(8) == "GAP"


def test_rejects_negative_quantity() -> None:
    """Negative absolute quantities are impossible."""
    event = sample_update()
    event["b"] = [["100.00", "-1"]]

    with pytest.raises(ValueError, match="quantity cannot be negative"):
        DepthUpdate.from_event(event)


def test_rejects_reversed_update_range() -> None:
    """The final update ID cannot precede the first."""
    event = sample_update()
    event["U"] = 13
    event["u"] = 12

    with pytest.raises(ValueError, match="cannot precede"):
        DepthUpdate.from_event(event)
