"""Explicit execution-mode selection; authenticated modes are reserved and disabled."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from decimal import Decimal

from ai_trader.risk.engine import RiskLimits
from ai_trader.trading.execution import ExecutionCosts
from ai_trader.trading.gateway import ExecutionGateway, ExecutionMode, PaperExecutionGateway
from ai_trader.trading.paper_broker import PaperBroker
from ai_trader.trading.paper_portfolio import PaperPortfolio


class ExecutionModeUnavailable(RuntimeError):
    """Raised before any account lookup, connection, or simulated substitution."""


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Mode is an operator setting, not a model output or profit-triggered switch."""

    mode: ExecutionMode = ExecutionMode.PAPER

    def __post_init__(self) -> None:
        if not isinstance(self.mode, (str, ExecutionMode)):
            raise ValueError("Execution mode must be paper, spot_testnet or spot_live.")
        object.__setattr__(self, "mode", ExecutionMode(self.mode))

    @property
    def state_namespace(self) -> str:
        """Use distinct ledgers/checkpoints for each environment."""
        return f"execution/{self.mode.value}"

    def require_available(self) -> None:
        if self.mode != ExecutionMode.PAPER:
            raise ExecutionModeUnavailable(
                f"{self.mode.value} is reserved but disabled: "
                "no authenticated adapter is installed. "
                "Account reconciliation, tested order lifecycle, independent risk approval and "
                "explicit operator arming are required. Paper profitability does not enable it."
            )


def create_execution_gateway(
    config: ExecutionConfig,
    *,
    initial_cash_usdt: Decimal,
    risk_limits: RiskLimits,
    execution_costs: ExecutionCosts,
) -> ExecutionGateway:
    """Fail closed on unsupported modes; never silently fall back to paper."""
    config.require_available()
    if not isinstance(initial_cash_usdt, Decimal) or not initial_cash_usdt.is_finite():
        raise ValueError("Initial cash must be a finite Decimal.")
    numeric_values = (
        risk_limits.max_position_btc,
        risk_limits.max_order_btc,
        risk_limits.max_order_notional_usdt,
        risk_limits.max_position_notional_usdt,
        risk_limits.max_daily_loss_usdt,
        risk_limits.max_drawdown_usdt,
        execution_costs.taker_fee_bps,
        execution_costs.slippage_bps,
    )
    if any(not isinstance(v, Decimal) or not v.is_finite() for v in numeric_values):
        raise ValueError("Risk limits and execution costs must be finite Decimals.")
    return PaperExecutionGateway(
        PaperBroker(
            portfolio=PaperPortfolio.create(initial_cash_usdt),
            risk_limits=risk_limits,
            execution_costs=execution_costs,
        )
    )


def main() -> None:
    """Check a selected mode without starting a feed or submitting any order."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=[mode.value for mode in ExecutionMode], default="paper")
    parser.add_argument("--check", action="store_true", required=True)
    args = parser.parse_args()
    config = ExecutionConfig(args.mode)
    try:
        config.require_available()
    except ExecutionModeUnavailable as error:
        parser.exit(2, f"{error}\n")
    print(
        json.dumps(
            {
                "mode": config.mode.value,
                "state_namespace": config.state_namespace,
                "execution_available": True,
                "orders_submitted": 0,
                "market_data_network_allowed": True,
                "model_inference_policy": "local",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
