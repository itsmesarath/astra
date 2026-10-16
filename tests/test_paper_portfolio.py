"""Tests for offline paper portfolio accounting."""

from decimal import Decimal

import pytest

from ai_trader.trading.paper_portfolio import (
    PaperFill,
    PaperPortfolio,
)


def make_fill(
    side: str,
    quantity: str,
    price: str,
    fee: str,
    *,
    event_time_ms: int = 1000,
) -> PaperFill:
    """Create a paper fill using decimal strings."""
    return PaperFill(
        side=side,
        quantity_btc=Decimal(quantity),
        price_usdt=Decimal(price),
        fee_usdt=Decimal(fee),
        event_time_ms=event_time_ms,
    )


def test_opens_and_marks_long_position() -> None:
    """Long equity should reconcile cash, value, PnL, and fees."""
    portfolio = PaperPortfolio.create(Decimal("10000"))
    portfolio.apply_fill(make_fill("BUY", "0.1", "100", "1"))

    snapshot = portfolio.mark_to_market(Decimal("110"))

    assert portfolio.fill_count == 1
    assert snapshot.cash_usdt == Decimal("9989")
    assert snapshot.position_btc == Decimal("0.1")
    assert snapshot.average_entry_price_usdt == Decimal("100")
    assert snapshot.gross_realized_pnl_usdt == Decimal("0")
    assert snapshot.unrealized_pnl_usdt == Decimal("1")
    assert snapshot.fees_paid_usdt == Decimal("1")
    assert snapshot.net_realized_pnl_usdt == Decimal("-1")
    assert snapshot.equity_usdt == Decimal("10000")
    assert snapshot.peak_equity_usdt == Decimal("10000")
    assert snapshot.drawdown_usdt == Decimal("0")


def test_partially_closes_long_and_realizes_pnl() -> None:
    """Partial close should realize only the closed quantity."""
    portfolio = PaperPortfolio.create(Decimal("10000"))
    portfolio.apply_fill(make_fill("BUY", "0.1", "100", "1"))
    portfolio.apply_fill(make_fill("SELL", "0.04", "120", "0.5"))

    snapshot = portfolio.mark_to_market(Decimal("120"))

    assert snapshot.cash_usdt == Decimal("9993.3")
    assert snapshot.position_btc == Decimal("0.06")
    assert snapshot.average_entry_price_usdt == Decimal("100")
    assert snapshot.gross_realized_pnl_usdt == Decimal("0.8")
    assert snapshot.unrealized_pnl_usdt == Decimal("1.2")
    assert snapshot.fees_paid_usdt == Decimal("1.5")
    assert snapshot.net_realized_pnl_usdt == Decimal("-0.7")
    assert snapshot.equity_usdt == Decimal("10000.5")


def test_opens_and_closes_short_position() -> None:
    """Short PnL should increase when the mark price falls."""
    portfolio = PaperPortfolio.create(Decimal("10000"))
    portfolio.apply_fill(make_fill("SELL", "0.1", "100", "1"))

    open_snapshot = portfolio.mark_to_market(Decimal("90"))

    assert open_snapshot.cash_usdt == Decimal("10009")
    assert open_snapshot.position_btc == Decimal("-0.1")
    assert open_snapshot.average_entry_price_usdt == Decimal("100")
    assert open_snapshot.unrealized_pnl_usdt == Decimal("1")
    assert open_snapshot.equity_usdt == Decimal("10000")

    portfolio.apply_fill(make_fill("BUY", "0.1", "80", "1"))
    closed_snapshot = portfolio.mark_to_market(Decimal("80"))

    assert closed_snapshot.cash_usdt == Decimal("10000")
    assert closed_snapshot.position_btc == Decimal("0")
    assert closed_snapshot.average_entry_price_usdt == Decimal("0")
    assert closed_snapshot.gross_realized_pnl_usdt == Decimal("2")
    assert closed_snapshot.fees_paid_usdt == Decimal("2")
    assert closed_snapshot.net_realized_pnl_usdt == Decimal("0")
    assert closed_snapshot.equity_usdt == Decimal("10000")


def test_calculates_weighted_entry_and_rejects_flip() -> None:
    """Added exposure changes average cost; one fill cannot reverse."""
    portfolio = PaperPortfolio.create(Decimal("10000"))
    portfolio.apply_fill(make_fill("BUY", "0.1", "100", "0"))
    portfolio.apply_fill(make_fill("BUY", "0.2", "130", "0"))

    snapshot = portfolio.mark_to_market(Decimal("120"))

    assert snapshot.position_btc == Decimal("0.3")
    assert snapshot.average_entry_price_usdt == Decimal("120")

    cash_before = portfolio.cash_usdt
    position_before = portfolio.position_btc
    fills_before = portfolio.fill_count

    with pytest.raises(
        ValueError,
        match="cannot reverse",
    ):
        portfolio.apply_fill(make_fill("SELL", "0.4", "120", "0"))

    assert portfolio.cash_usdt == cash_before
    assert portfolio.position_btc == position_before
    assert portfolio.fill_count == fills_before


def test_updates_peak_equity_and_drawdown() -> None:
    """Peak equity should persist across later losses."""
    portfolio = PaperPortfolio.create(Decimal("10000"))
    portfolio.apply_fill(make_fill("BUY", "1", "100", "0"))

    peak_snapshot = portfolio.mark_to_market(Decimal("110"))
    drawdown_snapshot = portfolio.mark_to_market(Decimal("105"))

    assert peak_snapshot.equity_usdt == Decimal("10010")
    assert peak_snapshot.peak_equity_usdt == Decimal("10010")
    assert drawdown_snapshot.equity_usdt == Decimal("10005")
    assert drawdown_snapshot.peak_equity_usdt == Decimal("10010")
    assert drawdown_snapshot.drawdown_usdt == Decimal("5")


def test_rejects_invalid_fill_and_mark_values() -> None:
    """Paper accounting inputs must be valid."""
    with pytest.raises(
        ValueError,
        match="Initial cash",
    ):
        PaperPortfolio.create(Decimal("0"))

    with pytest.raises(
        ValueError,
        match="Fill fee cannot be negative",
    ):
        make_fill("BUY", "1", "100", "-1")

    portfolio = PaperPortfolio.create(Decimal("10000"))

    with pytest.raises(
        ValueError,
        match="Mark price",
    ):
        portfolio.mark_to_market(Decimal("0"))
