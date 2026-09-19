"""Tests for the fully offline paper broker."""

from decimal import Decimal

from ai_trader.risk.engine import RiskLimits
from ai_trader.trading.execution import (
    ExecutionCosts,
    MarketQuote,
)
from ai_trader.trading.paper_broker import PaperBroker
from ai_trader.trading.paper_portfolio import PaperPortfolio


def make_limits(
    *,
    max_order_btc: str = "1",
) -> RiskLimits:
    """Create test broker limits."""
    return RiskLimits(
        max_position_btc=Decimal("1"),
        max_order_btc=Decimal(max_order_btc),
        max_order_notional_usdt=Decimal("10000"),
        max_position_notional_usdt=Decimal("10000"),
        max_daily_loss_usdt=Decimal("100"),
        max_drawdown_usdt=Decimal("200"),
    )


def make_broker(
    *,
    limits: RiskLimits | None = None,
) -> PaperBroker:
    """Create an empty offline broker."""
    return PaperBroker(
        portfolio=PaperPortfolio.create(Decimal("10000")),
        risk_limits=limits or make_limits(),
        execution_costs=ExecutionCosts(
            taker_fee_bps=Decimal("10"),
            slippage_bps=Decimal("5"),
        ),
    )


def make_quote(
    *,
    event_time_ms: int = 1000,
) -> MarketQuote:
    """Create a fixed market quote."""
    return MarketQuote(
        best_bid_usdt=Decimal("100"),
        best_ask_usdt=Decimal("101"),
        event_time_ms=event_time_ms,
    )


def test_opens_long_after_risk_approval() -> None:
    """Approved LONG intention should create one paper fill."""
    broker = make_broker()

    result = broker.process_intent(
        intent="LONG",
        entry_quantity_btc=Decimal("0.1"),
        quote=make_quote(),
    )

    assert result.executed
    assert result.reason == "paper_fill_applied"
    assert result.fill is not None
    assert result.fill.side == "BUY"
    assert result.fill.price_usdt == Decimal("101.0505")
    assert result.risk_decision is not None
    assert result.risk_decision.approved
    assert result.snapshot.position_btc == Decimal("0.1")
    assert broker.portfolio.fill_count == 1


def test_repeated_same_direction_is_no_op() -> None:
    """The broker should not repeatedly add same-side exposure."""
    broker = make_broker()
    broker.process_intent(
        intent="LONG",
        entry_quantity_btc=Decimal("0.1"),
        quote=make_quote(),
    )

    repeated = broker.process_intent(
        intent="LONG",
        entry_quantity_btc=Decimal("0.1"),
        quote=make_quote(event_time_ms=1100),
    )

    assert not repeated.executed
    assert repeated.reason == "already_long"
    assert repeated.fill is None
    assert broker.portfolio.fill_count == 1


def test_reversal_requires_close_then_new_entry() -> None:
    """Opposing intention should flatten before reversing."""
    broker = make_broker()
    broker.process_intent(
        intent="LONG",
        entry_quantity_btc=Decimal("0.1"),
        quote=make_quote(),
    )

    close_result = broker.process_intent(
        intent="SHORT",
        entry_quantity_btc=Decimal("0.1"),
        quote=make_quote(event_time_ms=1100),
    )

    assert close_result.executed
    assert close_result.fill is not None
    assert close_result.fill.side == "SELL"
    assert close_result.risk_decision is not None
    assert close_result.risk_decision.risk_reducing
    assert close_result.snapshot.position_btc == Decimal("0")

    short_result = broker.process_intent(
        intent="SHORT",
        entry_quantity_btc=Decimal("0.1"),
        quote=make_quote(event_time_ms=1200),
    )

    assert short_result.executed
    assert short_result.fill is not None
    assert short_result.fill.side == "SELL"
    assert short_result.snapshot.position_btc == Decimal("-0.1")
    assert broker.portfolio.fill_count == 3


def test_risk_rejection_does_not_modify_portfolio() -> None:
    """Rejected proposals must not create fills or change balances."""
    broker = make_broker(limits=make_limits(max_order_btc="0.05"))
    cash_before = broker.portfolio.cash_usdt

    result = broker.process_intent(
        intent="LONG",
        entry_quantity_btc=Decimal("0.1"),
        quote=make_quote(),
    )

    assert not result.executed
    assert result.reason == ("risk_rejected:order_quantity_limit_exceeded")
    assert result.fill is None
    assert broker.portfolio.position_btc == Decimal("0")
    assert broker.portfolio.cash_usdt == cash_before
    assert broker.portfolio.fill_count == 0


def test_kill_switch_blocks_entry_but_allows_flattening() -> None:
    """The kill switch must preserve risk-reducing exits."""
    broker = make_broker()
    broker.set_kill_switch(True)

    blocked = broker.process_intent(
        intent="LONG",
        entry_quantity_btc=Decimal("0.1"),
        quote=make_quote(),
    )

    assert not blocked.executed
    assert blocked.reason == "risk_rejected:kill_switch_active"
    assert broker.portfolio.position_btc == Decimal("0")

    broker.set_kill_switch(False)
    broker.process_intent(
        intent="LONG",
        entry_quantity_btc=Decimal("0.1"),
        quote=make_quote(event_time_ms=1100),
    )
    broker.set_kill_switch(True)

    flattened = broker.process_intent(
        intent="FLAT",
        entry_quantity_btc=Decimal("0.1"),
        quote=make_quote(event_time_ms=1200),
    )

    assert flattened.executed
    assert flattened.risk_decision is not None
    assert flattened.risk_decision.risk_reducing
    assert flattened.snapshot.position_btc == Decimal("0")
