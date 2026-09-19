"""Tests for validation-only model promotion gates."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ai_trader.backtesting.paper_simulation import SimulationReport
from ai_trader.backtesting.promotion_gate import (
    PromotionCriteria,
    evaluate_promotion,
)
from ai_trader.trading.evaluate_decision_policy import PolicyEvaluation


def make_policy_report(
    *,
    rows: int = 2000,
    short_signals: int = 40,
    long_signals: int = 40,
    correct_short_signals: int = 30,
    correct_long_signals: int = 30,
) -> PolicyEvaluation:
    """Create a policy report with configurable directional quality."""
    return PolicyEvaluation(
        rows=rows,
        short_signals=short_signals,
        flat_decisions=rows - short_signals - long_signals,
        long_signals=long_signals,
        correct_short_signals=correct_short_signals,
        correct_long_signals=correct_long_signals,
        short_outcomes=(correct_short_signals, 10, 0),
        long_outcomes=(0, 10, correct_long_signals),
        reason_counts={},
    )


def make_simulation_report(
    *,
    net_pnl_usdt: str = "5",
    maximum_drawdown_usdt: str = "2",
    final_position_btc: str = "0",
) -> SimulationReport:
    """Create a reconciled simulation summary for gate tests."""
    initial_equity = Decimal("10000")
    net_pnl = Decimal(net_pnl_usdt)

    return SimulationReport(
        rows=2000,
        short_intents=40,
        flat_intents=1920,
        long_intents=40,
        fills=20,
        risk_rejections=0,
        initial_equity_usdt=initial_equity,
        final_equity_usdt=initial_equity + net_pnl,
        net_pnl_usdt=net_pnl,
        return_fraction=net_pnl / initial_equity,
        maximum_drawdown_usdt=Decimal(maximum_drawdown_usdt),
        gross_realized_pnl_usdt=Decimal("7"),
        fees_paid_usdt=Decimal("2"),
        net_realized_pnl_usdt=net_pnl,
        final_position_btc=Decimal(final_position_btc),
    )


def test_approves_only_when_every_gate_passes() -> None:
    """A sound validation report should pass all fixed requirements."""
    decision = evaluate_promotion(
        validation_rows=2000,
        balanced_accuracy=0.60,
        macro_f1=0.55,
        policy_report=make_policy_report(),
        simulation_report=make_simulation_report(),
        criteria=PromotionCriteria(),
    )

    assert decision.approved
    assert decision.failed_checks == ()
    assert all(check.passed for check in decision.checks)


def test_blocks_unprofitable_low_precision_model() -> None:
    """Classification strength cannot override policy and cost failures."""
    decision = evaluate_promotion(
        validation_rows=2000,
        balanced_accuracy=0.70,
        macro_f1=0.60,
        policy_report=make_policy_report(
            correct_short_signals=10,
            correct_long_signals=10,
        ),
        simulation_report=make_simulation_report(
            net_pnl_usdt="-3",
        ),
        criteria=PromotionCriteria(),
    )
    failed_names = {check.name for check in decision.failed_checks}

    assert not decision.approved
    assert failed_names == {
        "directional_precision",
        "net_pnl_usdt",
    }


def test_blocks_insufficient_directional_evidence() -> None:
    """A nearly inactive strategy must not pass on a tiny lucky sample."""
    decision = evaluate_promotion(
        validation_rows=2000,
        balanced_accuracy=0.60,
        macro_f1=0.55,
        policy_report=make_policy_report(
            short_signals=2,
            long_signals=2,
            correct_short_signals=2,
            correct_long_signals=2,
        ),
        simulation_report=make_simulation_report(),
        criteria=PromotionCriteria(),
    )
    failed_names = {check.name for check in decision.failed_checks}

    assert not decision.approved
    assert failed_names == {
        "directional_signals",
        "directional_coverage",
    }


def test_blocks_open_final_position_and_excessive_drawdown() -> None:
    """Accounting safety requirements must independently block promotion."""
    decision = evaluate_promotion(
        validation_rows=2000,
        balanced_accuracy=0.60,
        macro_f1=0.55,
        policy_report=make_policy_report(),
        simulation_report=make_simulation_report(
            maximum_drawdown_usdt="12",
            final_position_btc="0.001",
        ),
        criteria=PromotionCriteria(),
    )
    failed_names = {check.name for check in decision.failed_checks}

    assert not decision.approved
    assert failed_names == {
        "maximum_drawdown_usdt",
        "flat_final_position",
    }


def test_rejects_invalid_criteria() -> None:
    """Promotion thresholds must remain internally valid."""
    with pytest.raises(
        ValueError,
        match="between zero and one",
    ):
        PromotionCriteria(
            minimum_directional_precision=1.1,
        )
