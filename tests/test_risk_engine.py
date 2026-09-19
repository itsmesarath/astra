"""Tests for deterministic hard-risk checks."""

from decimal import Decimal

import pytest

from ai_trader.risk.engine import (
    OrderIntent,
    PortfolioRiskState,
    RiskLimits,
    evaluate_order,
)


def make_limits() -> RiskLimits:
    """Create conservative test limits."""
    return RiskLimits(
        max_position_btc=Decimal("0.10"),
        max_order_btc=Decimal("0.02"),
        max_order_notional_usdt=Decimal("2000"),
        max_position_notional_usdt=Decimal("5000"),
        max_daily_loss_usdt=Decimal("100"),
        max_drawdown_usdt=Decimal("150"),
    )


def make_state(
    *,
    position_btc: str = "0",
    realized_pnl_today_usdt: str = "0",
    equity_usdt: str = "10000",
    peak_equity_usdt: str = "10100",
    kill_switch_active: bool = False,
) -> PortfolioRiskState:
    """Create portfolio risk state."""
    return PortfolioRiskState(
        position_btc=Decimal(position_btc),
        realized_pnl_today_usdt=Decimal(realized_pnl_today_usdt),
        equity_usdt=Decimal(equity_usdt),
        peak_equity_usdt=Decimal(peak_equity_usdt),
        kill_switch_active=kill_switch_active,
    )


def test_approves_order_within_all_limits() -> None:
    """A small exposure-increasing order should pass."""
    order = OrderIntent(
        side="BUY",
        quantity_btc=Decimal("0.01"),
        price_usdt=Decimal("80000"),
    )

    decision = evaluate_order(
        order,
        make_state(),
        make_limits(),
    )

    assert decision.approved
    assert decision.reason == "risk_limits_passed"
    assert not decision.risk_reducing
    assert decision.resulting_position_btc == Decimal("0.01")
    assert decision.order_notional_usdt == Decimal("800")
    assert decision.resulting_position_notional_usdt == Decimal("800")


def test_rejects_order_and_position_limit_violations() -> None:
    """Quantity and notional limits must be enforced."""
    limits = make_limits()

    quantity_decision = evaluate_order(
        OrderIntent(
            side="BUY",
            quantity_btc=Decimal("0.03"),
            price_usdt=Decimal("50000"),
        ),
        make_state(),
        limits,
    )
    assert not quantity_decision.approved
    assert quantity_decision.reason == ("order_quantity_limit_exceeded")

    order_notional_decision = evaluate_order(
        OrderIntent(
            side="BUY",
            quantity_btc=Decimal("0.02"),
            price_usdt=Decimal("110000"),
        ),
        make_state(),
        limits,
    )
    assert not order_notional_decision.approved
    assert order_notional_decision.reason == ("order_notional_limit_exceeded")

    position_quantity_decision = evaluate_order(
        OrderIntent(
            side="BUY",
            quantity_btc=Decimal("0.02"),
            price_usdt=Decimal("40000"),
        ),
        make_state(position_btc="0.09"),
        limits,
    )
    assert not position_quantity_decision.approved
    assert position_quantity_decision.reason == ("position_quantity_limit_exceeded")

    position_notional_decision = evaluate_order(
        OrderIntent(
            side="BUY",
            quantity_btc=Decimal("0.01"),
            price_usdt=Decimal("110000"),
        ),
        make_state(position_btc="0.04"),
        limits,
    )
    assert not position_notional_decision.approved
    assert position_notional_decision.reason == ("position_notional_limit_exceeded")


def test_loss_locks_block_new_risk_but_allow_exit() -> None:
    """Kill, daily-loss, and drawdown locks must preserve exits."""
    limits = make_limits()
    opening_order = OrderIntent(
        side="BUY",
        quantity_btc=Decimal("0.01"),
        price_usdt=Decimal("80000"),
    )

    kill_decision = evaluate_order(
        opening_order,
        make_state(kill_switch_active=True),
        limits,
    )
    assert not kill_decision.approved
    assert kill_decision.reason == "kill_switch_active"

    loss_decision = evaluate_order(
        opening_order,
        make_state(realized_pnl_today_usdt="-100"),
        limits,
    )
    assert not loss_decision.approved
    assert loss_decision.reason == ("daily_loss_limit_reached")

    drawdown_decision = evaluate_order(
        opening_order,
        make_state(
            equity_usdt="10000",
            peak_equity_usdt="10150",
        ),
        limits,
    )
    assert not drawdown_decision.approved
    assert drawdown_decision.reason == ("drawdown_limit_reached")

    exit_order = OrderIntent(
        side="SELL",
        quantity_btc=Decimal("0.05"),
        price_usdt=Decimal("80000"),
        reduce_only=True,
    )
    exit_decision = evaluate_order(
        exit_order,
        make_state(
            position_btc="0.05",
            realized_pnl_today_usdt="-100",
            kill_switch_active=True,
        ),
        limits,
    )

    assert exit_decision.approved
    assert exit_decision.reason == "risk_reducing_order"
    assert exit_decision.risk_reducing
    assert exit_decision.resulting_position_btc == Decimal("0")


def test_rejects_invalid_reduce_only_and_position_flip() -> None:
    """Reduce-only orders cannot increase or reverse exposure."""
    limits = make_limits()

    wrong_side = evaluate_order(
        OrderIntent(
            side="BUY",
            quantity_btc=Decimal("0.01"),
            price_usdt=Decimal("80000"),
            reduce_only=True,
        ),
        make_state(position_btc="0.05"),
        limits,
    )
    assert not wrong_side.approved
    assert wrong_side.reason == ("reduce_only_would_not_reduce_risk")

    flip = evaluate_order(
        OrderIntent(
            side="SELL",
            quantity_btc=Decimal("0.06"),
            price_usdt=Decimal("80000"),
        ),
        make_state(position_btc="0.05"),
        limits,
    )
    assert not flip.approved
    assert flip.reason == "position_flip_not_allowed"


def test_rejects_invalid_configuration_and_state() -> None:
    """Limits and portfolio values must be internally valid."""
    with pytest.raises(
        ValueError,
        match="Every risk limit",
    ):
        RiskLimits(
            max_position_btc=Decimal("0"),
            max_order_btc=Decimal("0.01"),
            max_order_notional_usdt=Decimal("100"),
            max_position_notional_usdt=Decimal("100"),
            max_daily_loss_usdt=Decimal("10"),
            max_drawdown_usdt=Decimal("10"),
        )

    with pytest.raises(
        ValueError,
        match="Peak equity cannot be below",
    ):
        make_state(
            equity_usdt="10000",
            peak_equity_usdt="9999",
        )

    with pytest.raises(
        ValueError,
        match="quantity must be greater",
    ):
        OrderIntent(
            side="BUY",
            quantity_btc=Decimal("0"),
            price_usdt=Decimal("80000"),
        )
