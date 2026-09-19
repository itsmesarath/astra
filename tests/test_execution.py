"""Tests for offline market-order fill simulation."""

from decimal import Decimal

import pytest

from ai_trader.trading.execution import (
    ExecutionCosts,
    MarketQuote,
    simulate_market_fill,
)


def make_quote() -> MarketQuote:
    """Create a simple bid-ask quote."""
    return MarketQuote(
        best_bid_usdt=Decimal("100"),
        best_ask_usdt=Decimal("101"),
        event_time_ms=1234,
    )


def test_buy_crosses_ask_with_adverse_slippage_and_fee() -> None:
    """A market BUY should execute above the best ask."""
    fill = simulate_market_fill(
        side="BUY",
        quantity_btc=Decimal("2"),
        quote=make_quote(),
        costs=ExecutionCosts(
            taker_fee_bps=Decimal("10"),
            slippage_bps=Decimal("5"),
        ),
    )

    assert fill.side == "BUY"
    assert fill.price_usdt == Decimal("101.0505")
    assert fill.notional_usdt == Decimal("202.1010")
    assert fill.fee_usdt == Decimal("0.2021010")
    assert fill.event_time_ms == 1234


def test_sell_crosses_bid_with_adverse_slippage_and_fee() -> None:
    """A market SELL should execute below the best bid."""
    fill = simulate_market_fill(
        side="SELL",
        quantity_btc=Decimal("2"),
        quote=make_quote(),
        costs=ExecutionCosts(
            taker_fee_bps=Decimal("10"),
            slippage_bps=Decimal("5"),
        ),
    )

    assert fill.side == "SELL"
    assert fill.price_usdt == Decimal("99.9500")
    assert fill.notional_usdt == Decimal("199.9000")
    assert fill.fee_usdt == Decimal("0.1999000")
    assert fill.event_time_ms == 1234


def test_zero_costs_still_cross_the_spread() -> None:
    """Zero extra costs must still use ask for BUY and bid for SELL."""
    costs = ExecutionCosts(
        taker_fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    buy_fill = simulate_market_fill(
        side="BUY",
        quantity_btc=Decimal("1"),
        quote=make_quote(),
        costs=costs,
    )
    sell_fill = simulate_market_fill(
        side="SELL",
        quantity_btc=Decimal("1"),
        quote=make_quote(),
        costs=costs,
    )

    assert buy_fill.price_usdt == Decimal("101")
    assert sell_fill.price_usdt == Decimal("100")
    assert buy_fill.fee_usdt == Decimal("0")
    assert sell_fill.fee_usdt == Decimal("0")


def test_rejects_invalid_quote_costs_and_order() -> None:
    """Impossible quotes, costs, sides, and quantities must fail."""
    with pytest.raises(
        ValueError,
        match="bid below ask",
    ):
        MarketQuote(
            best_bid_usdt=Decimal("101"),
            best_ask_usdt=Decimal("101"),
            event_time_ms=0,
        )

    with pytest.raises(
        ValueError,
        match="Taker fee cannot be negative",
    ):
        ExecutionCosts(
            taker_fee_bps=Decimal("-1"),
            slippage_bps=Decimal("0"),
        )

    with pytest.raises(
        ValueError,
        match="Slippage must be below",
    ):
        ExecutionCosts(
            taker_fee_bps=Decimal("0"),
            slippage_bps=Decimal("10000"),
        )

    with pytest.raises(
        ValueError,
        match="quantity must be greater",
    ):
        simulate_market_fill(
            side="BUY",
            quantity_btc=Decimal("0"),
            quote=make_quote(),
            costs=ExecutionCosts(
                taker_fee_bps=Decimal("10"),
                slippage_bps=Decimal("5"),
            ),
        )

    with pytest.raises(
        ValueError,
        match="side must be BUY or SELL",
    ):
        simulate_market_fill(
            side="HOLD",
            quantity_btc=Decimal("1"),
            quote=make_quote(),
            costs=ExecutionCosts(
                taker_fee_bps=Decimal("10"),
                slippage_bps=Decimal("5"),
            ),
        )
