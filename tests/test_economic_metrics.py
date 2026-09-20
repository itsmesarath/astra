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
        previous_evaluation=first,
    )

    aggregate = aggregate_economic_evaluations((first, second), config)

    assert aggregate.accepted_trades == 2
    assert aggregate.ending_balance == pytest.approx(999.9)
    assert aggregate.net_pnl == pytest.approx(-0.1)
    assert aggregate.maximum_closed_trade_drawdown_pct == pytest.approx(1.0)
    assert second.starting_balance == first.ending_balance
    assert aggregate.ending_balance == second.ending_balance
    assert aggregate.observation_ms == 3000
    assert sum(trade.net_pnl for trade in aggregate.trade_ledger) == pytest.approx(
        aggregate.net_pnl
    )


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
    with pytest.raises(ValueError, match="re-entry delay"):
        EconomicConfig(minimum_reentry_delay_ms=-1).validate()
    with pytest.raises(ValueError, match="Maximum trades"):
        EconomicConfig(maximum_trades_per_session=0).validate()
    with pytest.raises(ValueError, match="Session profit target"):
        EconomicConfig(session_profit_target=0).validate()
    with pytest.raises(ValueError, match="Session loss limit"):
        EconomicConfig(session_loss_limit=float("inf")).validate()
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
    assert "trade_ledger" not in payload
    assert payload["accounting_policy"] == "label_settlement_continuous_capital_v2"
    assert payload["turnover_definition"] == "twice_entry_notional_proxy"
    assert payload["drawdown_definition"] == "closed_trade_only_no_position_marks"
    assert payload["observation_ms"] == 1000


def test_applies_cooldown_and_trade_count_limits() -> None:
    """Cooldown and session trade caps must reject otherwise valid long signals audibly."""
    outcomes = (
        TradeOutcome(0, 999, 10),
        TradeOutcome(1500, 2499, 10),
        TradeOutcome(3000, 3999, 10),
        TradeOutcome(5000, 5999, 10),
    )
    report = evaluate_spot_economics(
        (LONG, LONG, LONG, LONG),
        outcomes,
        spot_policy(),
        EconomicConfig(
            minimum_reentry_delay_ms=1000,
            maximum_trades_per_session=2,
        ),
    )

    assert report.accepted_trades == 2
    assert report.skipped_cooldown_signals == 1
    assert report.skipped_trade_limit_signals == 1
    assert report.skipped_session_limit_signals == 0


@pytest.mark.parametrize(
    "config",
    [
        EconomicConfig(session_profit_target=50),
        EconomicConfig(session_loss_limit=50),
    ],
)
def test_stops_new_entries_after_session_pnl_limit(config: EconomicConfig) -> None:
    """Realized session targets must stop new exposure while preserving the triggering trade."""
    first_return = 100 if config.session_profit_target is not None else -100
    report = evaluate_spot_economics(
        (LONG, LONG),
        (
            TradeOutcome(0, 999, first_return),
            TradeOutcome(2000, 2999, 100),
        ),
        spot_policy(),
        config,
    )

    assert report.accepted_trades == 1
    assert report.skipped_session_limit_signals == 1


@pytest.mark.parametrize("first_return", [-100, 100])
def test_future_pnl_cannot_change_open_position_rejections(first_return: float) -> None:
    report = evaluate_spot_economics(
        (LONG, LONG, LONG),
        (
            TradeOutcome(0, 999, first_return),
            TradeOutcome(500, 1499, 500),
            TradeOutcome(1000, 1999, 500),
        ),
        spot_policy(),
        EconomicConfig(session_profit_target=50, session_loss_limit=50),
    )
    assert report.accepted_trades == 1
    assert report.skipped_overlapping_signals == 1
    assert report.skipped_session_limit_signals == 1
    assert report.trade_ledger[0].balance_before == 10_000
    assert report.trade_ledger[0].balance_after == 10_000 + first_return


def test_settles_before_flat_rows_and_drains_final_trade() -> None:
    report = evaluate_spot_economics(
        (LONG, FLAT, LONG),
        (TradeOutcome(0, 999, 100), TradeOutcome(1000, 1999, 0), TradeOutcome(2000, 2999, -50)),
        spot_policy(),
        EconomicConfig(starting_balance=1000, position_fraction=0.5),
    )
    first, last = report.trade_ledger
    assert first.net_pnl == 5
    assert last.balance_before == first.balance_after == 1005
    assert last.entry_notional == 502.5
    assert last.net_pnl == -2.5125
    assert report.ending_balance == last.balance_after == 1002.4875
    assert report.last_exit_time_ms == 2999


def test_exit_timestamp_is_inclusive_and_next_millisecond_allows_reentry() -> None:
    report = evaluate_spot_economics(
        (LONG, LONG, LONG),
        (TradeOutcome(0, 999, 100), TradeOutcome(999, 1500, 100), TradeOutcome(1000, 2000, 100)),
        spot_policy(),
        EconomicConfig(),
    )
    assert report.accepted_trades == 2
    assert report.skipped_overlapping_signals == 1
    assert report.trade_ledger[1].balance_before == 10_100


@pytest.mark.parametrize(
    "first_return,config,accepted",
    [
        (1000, EconomicConfig(starting_balance=1000, session_profit_target=10.5), 1),
        (-1000, EconomicConfig(starting_balance=1000, session_loss_limit=9.5), 2),
    ],
)
def test_session_limits_use_carried_capital_and_reset_pnl_reference(
    first_return: float, config: EconomicConfig, accepted: int
) -> None:
    first = evaluate_spot_economics(
        (LONG,), (TradeOutcome(0, 999, first_return),), spot_policy(), config
    )
    next_return = 100 if first_return > 0 else -100
    second = evaluate_spot_economics(
        (LONG, LONG),
        (TradeOutcome(2000, 2999, next_return), TradeOutcome(4000, 4999, next_return)),
        spot_policy(),
        config,
        previous_evaluation=first,
    )
    assert second.starting_balance == first.ending_balance
    assert second.accepted_trades == accepted
    assert second.skipped_session_limit_signals == 2 - accepted
    aggregate = aggregate_economic_evaluations((first, second), config)
    assert aggregate.ending_balance == second.ending_balance
    assert aggregate.net_pnl == pytest.approx(first.net_pnl + second.net_pnl)


def test_cooldown_survives_flat_sessions_while_trade_counter_resets() -> None:
    config = EconomicConfig(minimum_reentry_delay_ms=8000, maximum_trades_per_session=1)
    first = evaluate_spot_economics((LONG,), (TradeOutcome(0, 999, 100),), spot_policy(), config)
    flat = evaluate_spot_economics(
        (FLAT,), (TradeOutcome(2000, 2999, 0),), spot_policy(), config, previous_evaluation=first
    )
    third = evaluate_spot_economics(
        (LONG, LONG),
        (TradeOutcome(8999, 9500, 100), TradeOutcome(9000, 9999, 100)),
        spot_policy(),
        config,
        previous_evaluation=flat,
    )
    assert flat.starting_balance == flat.ending_balance == first.ending_balance
    assert flat.last_exit_time_ms == 999
    assert third.accepted_trades == 1
    assert third.skipped_cooldown_signals == 1
    assert third.skipped_trade_limit_signals == 0
    aggregate = aggregate_economic_evaluations((first, flat, third), config)
    assert aggregate.ending_balance == third.ending_balance


def test_observation_uses_maximum_exit_even_for_nonmonotonic_unselected_rows() -> None:
    report = evaluate_spot_economics(
        (LONG, FLAT, LONG),
        (TradeOutcome(0, 3000, 100), TradeOutcome(1000, 5000, 0), TradeOutcome(2000, 2500, 100)),
        spot_policy(),
        EconomicConfig(),
    )
    assert report.observation_ms == 5001
    assert report.exposure_ms == 3001
    assert report.exposure_ratio == pytest.approx(3001 / 5001)
    assert report.last_exit_time_ms == 3000


@pytest.mark.parametrize("first_return", [100, 0])
def test_aggregation_rejects_independently_reset_sessions(first_return: float) -> None:
    config = EconomicConfig()
    first = evaluate_spot_economics(
        (LONG,), (TradeOutcome(0, 999, first_return),), spot_policy(), config
    )
    second = evaluate_spot_economics(
        (LONG,), (TradeOutcome(2000, 2999, 100),), spot_policy(), config
    )
    with pytest.raises(ValueError, match="across sessions"):
        aggregate_economic_evaluations((first, second), config)


def test_rejects_overlapping_or_reversed_session_chain() -> None:
    config = EconomicConfig()
    first = evaluate_spot_economics((LONG,), (TradeOutcome(0, 999, 100),), spot_policy(), config)
    with pytest.raises(ValueError, match="chronological and non-overlapping"):
        evaluate_spot_economics(
            (LONG,),
            (TradeOutcome(999, 1999, 100),),
            spot_policy(),
            config,
            previous_evaluation=first,
        )
    second = evaluate_spot_economics(
        (LONG,),
        (TradeOutcome(2000, 2999, 100),),
        spot_policy(),
        config,
        previous_evaluation=first,
    )
    with pytest.raises(ValueError, match="continuous capital"):
        aggregate_economic_evaluations((second, first), config)
