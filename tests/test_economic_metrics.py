"""Tests for cost-adjusted, non-overlapping Spot economics."""

from __future__ import annotations

import pytest

from ai_trader.backtesting.economic_metrics import (
    EconomicConfig,
    TradeOutcome,
    aggregate_economic_evaluations,
    economic_evaluation_payload,
    evaluate_spot_economics,
)
from ai_trader.trading.decision_policy import DecisionPolicy

LONG = (0.05, 0.05, 0.90)
FLAT = (0.05, 0.90, 0.05)


def spot_policy() -> DecisionPolicy:
    """Return a permissive long/flat-only policy."""
    return DecisionPolicy(
        minimum_direction_probability=0.5,
        minimum_probability_margin=0.1,
        allow_short=False,
    )


def test_compounds_nonoverlapping_cost_adjusted_outcomes() -> None:
    """Only executable sequential signals should affect equity and turnover."""
    outcomes = (
        TradeOutcome(1000, 1999, 100),
        TradeOutcome(1500, 2499, 500),
        TradeOutcome(3000, 3999, -50),
        TradeOutcome(5000, 5999, 0),
    )
    report = evaluate_spot_economics(
        (LONG, LONG, LONG, FLAT),
        outcomes,
        spot_policy(),
        EconomicConfig(starting_balance=10_000, position_fraction=0.5),
    )

    assert report.long_signals == 3
    assert report.accepted_trades == 2
    assert report.skipped_overlapping_signals == 1
    assert report.winning_trades == 1
    assert report.losing_trades == 1
    assert report.ending_balance == pytest.approx(10_024.875)
    assert report.net_pnl == pytest.approx(24.875)
    assert report.return_pct == pytest.approx(0.24875)
    assert report.maximum_closed_trade_drawdown_pct == pytest.approx(0.25)
    assert report.turnover_quote == pytest.approx(20_050)
    assert report.turnover_multiple == pytest.approx(2.005)
    assert report.exposure_ms == 2000
    assert report.observation_ms == 5000
    assert report.exposure_ratio == pytest.approx(0.4)
    assert report.total_net_return_bps == 50
    assert report.profit_factor == pytest.approx(50 / 25.125)


def test_aggregates_folds_in_chronological_trade_order() -> None:
    """Aggregate equity must compound every fold trade instead of averaging fold returns."""
    config = EconomicConfig(starting_balance=1000, position_fraction=1)
    first = evaluate_spot_economics(
        (LONG,),
        (TradeOutcome(0, 999, 100),),
        spot_policy(),
        config,
    )
    second = evaluate_spot_economics(
        (LONG,),
        (TradeOutcome(2000, 2999, -100),),
        spot_policy(),
        config,
    )

    aggregate = aggregate_economic_evaluations((first, second), config)

    assert aggregate.accepted_trades == 2
    assert aggregate.ending_balance == pytest.approx(999.9)
    assert aggregate.net_pnl == pytest.approx(-0.1)
    assert aggregate.maximum_closed_trade_drawdown_pct == pytest.approx(1.0)
    assert aggregate.observation_ms == 2000


def test_requires_spot_policy_and_aligned_rows() -> None:
    """Economic evaluation must reject short-capable or structurally misaligned inputs."""
    outcome = TradeOutcome(0, 999, 10)
    with pytest.raises(ValueError, match="short signals to be disabled"):
        evaluate_spot_economics(
            (LONG,),
            (outcome,),
            DecisionPolicy(allow_short=True),
            EconomicConfig(),
        )
    with pytest.raises(ValueError, match="equal lengths"):
        evaluate_spot_economics(
            (LONG, LONG),
            (outcome,),
            spot_policy(),
            EconomicConfig(),
        )


def test_validates_capital_and_outcome_inputs() -> None:
    """Invalid capital, chronology, and catastrophic returns must fail closed."""
    with pytest.raises(ValueError, match="Starting balance"):
        EconomicConfig(starting_balance=0).validate()
    with pytest.raises(ValueError, match="Position fraction"):
        EconomicConfig(position_fraction=1.1).validate()
    with pytest.raises(ValueError, match="invalid time interval"):
        TradeOutcome(1000, 999, 1).validate()
    with pytest.raises(ValueError, match="100% or more"):
        TradeOutcome(1000, 1999, -10_000).validate()


def test_payload_omits_individual_trade_returns() -> None:
    """Reports should expose aggregate economics without unnecessarily large return arrays."""
    report = evaluate_spot_economics(
        (LONG,),
        (TradeOutcome(0, 999, 10),),
        spot_policy(),
        EconomicConfig(),
    )

    payload = economic_evaluation_payload(report)

    assert payload["accepted_trades"] == 1
    assert "trade_net_returns_bps" not in payload
