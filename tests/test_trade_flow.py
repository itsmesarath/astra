"""Tests for aggregate-trade flow features."""

from decimal import Decimal

import pytest

from ai_trader.features.trade_flow import TradeFlowAccumulator
from ai_trader.ingestion.agg_trade import AggTrade


def make_trade(
    *,
    symbol: str = "BTCUSDT",
    aggregate_trade_id: int,
    price: str,
    quantity: str,
    first_trade_id: int,
    last_trade_id: int,
    buyer_is_maker: bool,
) -> AggTrade:
    """Create a validated aggregate trade for a test."""
    return AggTrade.from_event(
        {
            "e": "aggTrade",
            "E": 1000,
            "s": symbol,
            "a": aggregate_trade_id,
            "p": price,
            "q": quantity,
            "f": first_trade_id,
            "l": last_trade_id,
            "T": 999,
            "m": buyer_is_maker,
        }
    )


def test_accumulates_buy_and_sell_trade_flow() -> None:
    """BUY and SELL quantities should be accumulated separately."""
    accumulator = TradeFlowAccumulator(symbol="BTCUSDT")

    accumulator.add(
        make_trade(
            aggregate_trade_id=10,
            price="100",
            quantity="2",
            first_trade_id=50,
            last_trade_id=51,
            buyer_is_maker=False,
        )
    )
    accumulator.add(
        make_trade(
            aggregate_trade_id=11,
            price="101",
            quantity="1",
            first_trade_id=52,
            last_trade_id=52,
            buyer_is_maker=True,
        )
    )

    features = accumulator.snapshot()

    assert features.symbol == "BTCUSDT"
    assert features.aggregate_trade_count == 2
    assert features.underlying_trade_count == 3
    assert features.buy_base_volume == Decimal("2")
    assert features.sell_base_volume == Decimal("1")
    assert features.buy_quote_volume == Decimal("200")
    assert features.sell_quote_volume == Decimal("101")
    assert features.total_base_volume == Decimal("3")
    assert features.signed_base_volume == Decimal("1")
    assert features.total_quote_volume == Decimal("301")
    assert features.signed_quote_volume == Decimal("99")
    assert features.base_volume_imbalance == Decimal("1") / Decimal("3")


def test_empty_interval_has_zero_imbalance() -> None:
    """An interval without trades should produce finite zero features."""
    features = TradeFlowAccumulator(symbol="BTCUSDT").snapshot()

    assert features.aggregate_trade_count == 0
    assert features.underlying_trade_count == 0
    assert features.total_base_volume == Decimal("0")
    assert features.signed_base_volume == Decimal("0")
    assert features.base_volume_imbalance == Decimal("0")


def test_reset_starts_a_new_interval() -> None:
    """Reset should remove accumulated trades without changing the symbol."""
    accumulator = TradeFlowAccumulator(symbol="BTCUSDT")
    accumulator.add(
        make_trade(
            aggregate_trade_id=10,
            price="100",
            quantity="2",
            first_trade_id=50,
            last_trade_id=50,
            buyer_is_maker=False,
        )
    )

    accumulator.reset()
    features = accumulator.snapshot()

    assert features.symbol == "BTCUSDT"
    assert features.aggregate_trade_count == 0
    assert features.underlying_trade_count == 0
    assert features.total_base_volume == Decimal("0")
    assert features.total_quote_volume == Decimal("0")


def test_rejects_trade_for_wrong_symbol() -> None:
    """Trades from another market must not contaminate the accumulator."""
    accumulator = TradeFlowAccumulator(symbol="BTCUSDT")
    trade = make_trade(
        symbol="ETHUSDT",
        aggregate_trade_id=10,
        price="3000",
        quantity="1",
        first_trade_id=50,
        last_trade_id=50,
        buyer_is_maker=False,
    )

    with pytest.raises(ValueError, match="Expected symbol BTCUSDT"):
        accumulator.add(trade)
