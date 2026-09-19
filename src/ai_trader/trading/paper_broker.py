"""Offline broker connecting intentions, risk, fills, and accounting."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ai_trader.risk.engine import (
    OrderIntent,
    PortfolioRiskState,
    RiskDecision,
    RiskLimits,
    evaluate_order,
)
from ai_trader.trading.decision_policy import PositionIntent
from ai_trader.trading.execution import (
    ExecutionCosts,
    MarketQuote,
    simulate_market_fill,
)
from ai_trader.trading.paper_portfolio import (
    PaperFill,
    PaperPortfolio,
    PortfolioSnapshot,
)


@dataclass(frozen=True, slots=True)
class BrokerResult:
    """Result of processing one position intention."""

    requested_intent: PositionIntent
    executed: bool
    reason: str
    fill: PaperFill | None
    risk_decision: RiskDecision | None
    snapshot: PortfolioSnapshot


@dataclass(slots=True)
class PaperBroker:
    """Single-symbol broker with no exchange connectivity."""

    portfolio: PaperPortfolio
    risk_limits: RiskLimits
    execution_costs: ExecutionCosts
    kill_switch_active: bool = False

    def set_kill_switch(self, active: bool) -> None:
        """Enable or disable the local hard kill switch."""
        if not isinstance(active, bool):
            raise TypeError("Kill-switch state must be a Boolean.")
        self.kill_switch_active = active

    def process_intent(
        self,
        *,
        intent: PositionIntent,
        entry_quantity_btc: Decimal,
        quote: MarketQuote,
    ) -> BrokerResult:
        """Process at most one safe paper order for an intention."""
        if intent not in {"LONG", "FLAT", "SHORT"}:
            raise ValueError("Position intent must be LONG, FLAT, or SHORT.")
        if entry_quantity_btc <= 0:
            raise ValueError("Entry quantity must be greater than zero.")

        before = self.portfolio.mark_to_market(quote.midpoint_usdt)
        position = self.portfolio.position_btc

        if intent == "FLAT":
            if position == 0:
                return BrokerResult(
                    requested_intent=intent,
                    executed=False,
                    reason="already_flat",
                    fill=None,
                    risk_decision=None,
                    snapshot=before,
                )

            side = "SELL" if position > 0 else "BUY"
            quantity = abs(position)
            reduce_only = True

        elif intent == "LONG":
            if position > 0:
                return BrokerResult(
                    requested_intent=intent,
                    executed=False,
                    reason="already_long",
                    fill=None,
                    risk_decision=None,
                    snapshot=before,
                )

            if position < 0:
                side = "BUY"
                quantity = abs(position)
                reduce_only = True
            else:
                side = "BUY"
                quantity = entry_quantity_btc
                reduce_only = False

        else:
            if position < 0:
                return BrokerResult(
                    requested_intent=intent,
                    executed=False,
                    reason="already_short",
                    fill=None,
                    risk_decision=None,
                    snapshot=before,
                )

            if position > 0:
                side = "SELL"
                quantity = abs(position)
                reduce_only = True
            else:
                side = "SELL"
                quantity = entry_quantity_btc
                reduce_only = False

        proposed_fill = simulate_market_fill(
            side=side,
            quantity_btc=quantity,
            quote=quote,
            costs=self.execution_costs,
        )
        order = OrderIntent(
            side=side,
            quantity_btc=quantity,
            price_usdt=proposed_fill.price_usdt,
            reduce_only=reduce_only,
        )
        risk_state = PortfolioRiskState(
            position_btc=self.portfolio.position_btc,
            realized_pnl_today_usdt=(self.portfolio.net_realized_pnl_usdt),
            equity_usdt=before.equity_usdt,
            peak_equity_usdt=before.peak_equity_usdt,
            kill_switch_active=self.kill_switch_active,
        )
        risk_decision = evaluate_order(
            order,
            risk_state,
            self.risk_limits,
        )

        if not risk_decision.approved:
            return BrokerResult(
                requested_intent=intent,
                executed=False,
                reason=f"risk_rejected:{risk_decision.reason}",
                fill=None,
                risk_decision=risk_decision,
                snapshot=before,
            )

        self.portfolio.apply_fill(proposed_fill)
        after = self.portfolio.mark_to_market(quote.midpoint_usdt)

        return BrokerResult(
            requested_intent=intent,
            executed=True,
            reason="paper_fill_applied",
            fill=proposed_fill,
            risk_decision=risk_decision,
            snapshot=after,
        )
