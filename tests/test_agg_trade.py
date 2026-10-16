"""Tests for Binance aggregate-trade parsing."""

from decimal import Decimal

import pytest

from ai_trader.ingestion.agg_trade import AggTrade


def sample_event() -> dict[str, object]:
    """Return a representative Binance aggregate-trade event."""
    return {
        "e": "aggTrade",
        "E": 1001,
        "s": "BTCUSDT",
        "a": 42,
        "p": "76500.32",
        "q": "0.27262",
        "f": 100,
        "l": 116,
        "T": 1000,
        "m": True,
        "M": True,
    }


def test_parses_valid_aggregate_trade() -> None:
    """A valid raw event should become a typed trade."""
    trade = AggTrade.from_event(sample_event())

    assert trade.symbol == "BTCUSDT"
    assert trade.price == Decimal("76500.32")
    assert trade.quantity == Decimal("0.27262")
    assert trade.aggressor_side == "SELL"
    assert trade.underlying_trade_count == 17


def test_rejects_wrong_event_type() -> None:
    """A regular trade event must not be accepted as an aggregate trade."""
    event = sample_event()
    event["e"] = "trade"

    with pytest.raises(ValueError, match="Expected an aggTrade event"):
        AggTrade.from_event(event)


def test_rejects_reversed_trade_id_range() -> None:
    """The first underlying trade ID cannot follow the last one."""
    event = sample_event()
    event["f"] = 117
    event["l"] = 116

    with pytest.raises(ValueError, match="First trade ID cannot exceed"):
        AggTrade.from_event(event)
