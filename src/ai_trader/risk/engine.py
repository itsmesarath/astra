"""Deterministic hard limits for proposed trading orders."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

OrderSide = Literal["BUY", "SELL"]


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Absolute portfolio and order limits."""

    max_position_btc: Decimal
    max_order_btc: Decimal
    max_order_notional_usdt: Decimal
    max_position_notional_usdt: Decimal
    max_daily_loss_usdt: Decimal
    max_drawdown_usdt: Decimal

    def __post_init__(self) -> None:
        values = (
            self.max_position_btc,
            self.max_order_btc,
            self.max_order_notional_usdt,
            self.max_position_notional_usdt,
            self.max_daily_loss_usdt,
            self.max_drawdown_usdt,
        )
        if any(value <= 0 for value in values):
            raise ValueError("Every risk limit must be greater than zero.")


@dataclass(frozen=True, slots=True)
class PortfolioRiskState:
    """Portfolio values needed for pre-trade risk checks."""

    position_btc: Decimal
    realized_pnl_today_usdt: Decimal
    equity_usdt: Decimal
    peak_equity_usdt: Decimal
    kill_switch_active: bool = False

    def __post_init__(self) -> None:
        if self.equity_usdt <= 0:
            raise ValueError("Equity must be greater than zero.")
        if self.peak_equity_usdt <= 0:
            raise ValueError("Peak equity must be greater than zero.")
        if self.peak_equity_usdt < self.equity_usdt:
            raise ValueError("Peak equity cannot be below current equity.")

    @property
    def drawdown_usdt(self) -> Decimal:
        """Return peak equity minus current equity."""
        return self.peak_equity_usdt - self.equity_usdt


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """A proposed order that has not been sent anywhere."""

    side: OrderSide
    quantity_btc: Decimal
    price_usdt: Decimal
    reduce_only: bool = False

    def __post_init__(self) -> None:
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("Order side must be BUY or SELL.")
        if self.quantity_btc <= 0:
            raise ValueError("Order quantity must be greater than zero.")
        if self.price_usdt <= 0:
            raise ValueError("Order price must be greater than zero.")

    @property
    def signed_quantity_btc(self) -> Decimal:
        """Return positive BUY or negative SELL quantity."""
        return self.quantity_btc if self.side == "BUY" else -self.quantity_btc

    @property
    def notional_usdt(self) -> Decimal:
        """Return proposed order notional."""
        return self.quantity_btc * self.price_usdt


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Result of deterministic pre-trade checks."""

    approved: bool
    reason: str
    risk_reducing: bool
    resulting_position_btc: Decimal
    order_notional_usdt: Decimal
    resulting_position_notional_usdt: Decimal


def make_decision(
    *,
    approved: bool,
    reason: str,
    risk_reducing: bool,
    resulting_position_btc: Decimal,
    order: OrderIntent,
) -> RiskDecision:
    """Construct a complete risk decision."""
    return RiskDecision(
        approved=approved,
        reason=reason,
        risk_reducing=risk_reducing,
        resulting_position_btc=resulting_position_btc,
        order_notional_usdt=order.notional_usdt,
        resulting_position_notional_usdt=(abs(resulting_position_btc) * order.price_usdt),
    )


def evaluate_order(
    order: OrderIntent,
    state: PortfolioRiskState,
    limits: RiskLimits,
) -> RiskDecision:
    """Approve only orders satisfying every hard-risk rule."""
    resulting_position = state.position_btc + order.signed_quantity_btc
    flips_position = (
        state.position_btc != 0
        and resulting_position != 0
        and (state.position_btc > 0) != (resulting_position > 0)
    )
    risk_reducing = not flips_position and abs(resulting_position) < abs(state.position_btc)

    if order.reduce_only and not risk_reducing:
        return make_decision(
            approved=False,
            reason="reduce_only_would_not_reduce_risk",
            risk_reducing=False,
            resulting_position_btc=resulting_position,
            order=order,
        )

    if flips_position:
        return make_decision(
            approved=False,
            reason="position_flip_not_allowed",
            risk_reducing=False,
            resulting_position_btc=resulting_position,
            order=order,
        )

    if risk_reducing:
        return make_decision(
            approved=True,
            reason="risk_reducing_order",
            risk_reducing=True,
            resulting_position_btc=resulting_position,
            order=order,
        )

    if state.kill_switch_active:
        return make_decision(
            approved=False,
            reason="kill_switch_active",
            risk_reducing=False,
            resulting_position_btc=resulting_position,
            order=order,
        )

    if state.realized_pnl_today_usdt <= -limits.max_daily_loss_usdt:
        return make_decision(
            approved=False,
            reason="daily_loss_limit_reached",
            risk_reducing=False,
            resulting_position_btc=resulting_position,
            order=order,
        )

    if state.drawdown_usdt >= limits.max_drawdown_usdt:
        return make_decision(
            approved=False,
            reason="drawdown_limit_reached",
            risk_reducing=False,
            resulting_position_btc=resulting_position,
            order=order,
        )

    if order.quantity_btc > limits.max_order_btc:
        return make_decision(
            approved=False,
            reason="order_quantity_limit_exceeded",
            risk_reducing=False,
            resulting_position_btc=resulting_position,
            order=order,
        )

    if order.notional_usdt > limits.max_order_notional_usdt:
        return make_decision(
            approved=False,
            reason="order_notional_limit_exceeded",
            risk_reducing=False,
            resulting_position_btc=resulting_position,
            order=order,
        )

    if abs(resulting_position) > limits.max_position_btc:
        return make_decision(
            approved=False,
            reason="position_quantity_limit_exceeded",
            risk_reducing=False,
            resulting_position_btc=resulting_position,
            order=order,
        )

    resulting_notional = abs(resulting_position) * order.price_usdt
    if resulting_notional > limits.max_position_notional_usdt:
        return make_decision(
            approved=False,
            reason="position_notional_limit_exceeded",
            risk_reducing=False,
            resulting_position_btc=resulting_position,
            order=order,
        )

    return make_decision(
        approved=True,
        reason="risk_limits_passed",
        risk_reducing=False,
        resulting_position_btc=resulting_position,
        order=order,
    )
