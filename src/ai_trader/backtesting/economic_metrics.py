"""Cost-adjusted long-only economics for non-overlapping historical signals."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from ai_trader.trading.decision_policy import DecisionPolicy, decide_position

BASIS_POINTS_PER_UNIT = 10_000.0


@dataclass(frozen=True, slots=True)
class EconomicConfig:
    """Capital assumptions for validation-only Spot simulations."""

    starting_balance: float = 10_000.0
    position_fraction: float = 1.0

    def validate(self) -> None:
        """Reject invalid or leveraged capital assumptions."""
        if not math.isfinite(self.starting_balance) or self.starting_balance <= 0:
            raise ValueError("Starting balance must be finite and positive.")
        if not math.isfinite(self.position_fraction) or not 0 < self.position_fraction <= 1:
            raise ValueError("Position fraction must be in the interval (0, 1].")


@dataclass(frozen=True, slots=True)
class TradeOutcome:
    """A precomputed next-open long outcome whose return already includes costs."""

    entry_time_ms: int
    exit_time_ms: int
    net_return_bps: float

    def validate(self) -> None:
        """Reject impossible holding intervals or returns."""
        if self.entry_time_ms < 0 or self.exit_time_ms < self.entry_time_ms:
            raise ValueError("Trade outcome has an invalid time interval.")
        if not math.isfinite(self.net_return_bps):
            raise ValueError("Trade net return must be finite.")
        if self.net_return_bps <= -BASIS_POINTS_PER_UNIT:
            raise ValueError("Trade net return cannot lose 100% or more.")


@dataclass(frozen=True, slots=True)
class EconomicEvaluation:
    """Closed-trade economics for one or more chronological validation sessions."""

    rows: int
    long_signals: int
    accepted_trades: int
    skipped_overlapping_signals: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    starting_balance: float
    ending_balance: float
    net_pnl: float
    return_pct: float
    maximum_closed_trade_drawdown_pct: float
    turnover_quote: float
    turnover_multiple: float
    exposure_ms: int
    observation_ms: int
    exposure_ratio: float
    total_net_return_bps: float
    profit_factor: float | None
    trade_net_returns_bps: tuple[float, ...]


def _summarize_returns(
    trade_returns_bps: Sequence[float],
    *,
    rows: int,
    long_signals: int,
    skipped_overlapping_signals: int,
    exposure_ms: int,
    observation_ms: int,
    config: EconomicConfig,
) -> EconomicEvaluation:
    """Compound chronological trade outcomes and calculate portfolio statistics."""
    config.validate()
    balance = config.starting_balance
    peak_balance = balance
    maximum_drawdown = 0.0
    turnover_quote = 0.0
    gains = 0.0
    losses = 0.0
    normalized_returns = tuple(float(value) for value in trade_returns_bps)
    for return_bps in normalized_returns:
        if not math.isfinite(return_bps) or return_bps <= -BASIS_POINTS_PER_UNIT:
            raise ValueError("Trade returns must be finite and greater than -10000 bps.")
        position_notional = balance * config.position_fraction
        turnover_quote += 2 * position_notional
        pnl = position_notional * return_bps / BASIS_POINTS_PER_UNIT
        balance += pnl
        if return_bps > 0:
            gains += pnl
        elif return_bps < 0:
            losses += -pnl
        peak_balance = max(peak_balance, balance)
        drawdown = (peak_balance - balance) / peak_balance
        maximum_drawdown = max(maximum_drawdown, drawdown)

    accepted_trades = len(normalized_returns)
    winning_trades = sum(value > 0 for value in normalized_returns)
    losing_trades = sum(value < 0 for value in normalized_returns)
    ending_balance = balance
    net_pnl = ending_balance - config.starting_balance
    return EconomicEvaluation(
        rows=rows,
        long_signals=long_signals,
        accepted_trades=accepted_trades,
        skipped_overlapping_signals=skipped_overlapping_signals,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        breakeven_trades=accepted_trades - winning_trades - losing_trades,
        starting_balance=config.starting_balance,
        ending_balance=ending_balance,
        net_pnl=net_pnl,
        return_pct=net_pnl / config.starting_balance * 100,
        maximum_closed_trade_drawdown_pct=maximum_drawdown * 100,
        turnover_quote=turnover_quote,
        turnover_multiple=turnover_quote / config.starting_balance,
        exposure_ms=exposure_ms,
        observation_ms=observation_ms,
        exposure_ratio=exposure_ms / observation_ms if observation_ms > 0 else 0.0,
        total_net_return_bps=sum(normalized_returns),
        profit_factor=gains / losses if losses > 0 else None,
        trade_net_returns_bps=normalized_returns,
    )


def evaluate_spot_economics(
    probabilities: Sequence[Sequence[float]],
    outcomes: Sequence[TradeOutcome],
    policy: DecisionPolicy,
    config: EconomicConfig,
) -> EconomicEvaluation:
    """Simulate one long position at a time using cost-adjusted realized outcomes."""
    config.validate()
    if policy.allow_short:
        raise ValueError("Spot economic evaluation requires short signals to be disabled.")
    if len(probabilities) != len(outcomes):
        raise ValueError("Probabilities and trade outcomes must have equal lengths.")
    if not outcomes:
        raise ValueError("At least one trade outcome row is required.")

    previous_entry = -1
    for outcome in outcomes:
        outcome.validate()
        if outcome.entry_time_ms <= previous_entry:
            raise ValueError("Trade outcome entry times must be strictly increasing.")
        previous_entry = outcome.entry_time_ms

    long_signals = 0
    skipped_overlapping_signals = 0
    available_after_ms = -1
    accepted_returns = []
    exposure_ms = 0
    for probability_row, outcome in zip(probabilities, outcomes, strict=True):
        decision = decide_position(probability_row, policy)
        if decision.intent != "LONG":
            continue
        long_signals += 1
        if outcome.entry_time_ms <= available_after_ms:
            skipped_overlapping_signals += 1
            continue
        accepted_returns.append(outcome.net_return_bps)
        exposure_ms += outcome.exit_time_ms - outcome.entry_time_ms + 1
        available_after_ms = outcome.exit_time_ms

    observation_ms = outcomes[-1].exit_time_ms - outcomes[0].entry_time_ms + 1
    return _summarize_returns(
        accepted_returns,
        rows=len(outcomes),
        long_signals=long_signals,
        skipped_overlapping_signals=skipped_overlapping_signals,
        exposure_ms=exposure_ms,
        observation_ms=observation_ms,
        config=config,
    )


def aggregate_economic_evaluations(
    evaluations: Sequence[EconomicEvaluation],
    config: EconomicConfig,
) -> EconomicEvaluation:
    """Compound fold trade returns in chronological validation order."""
    if not evaluations:
        raise ValueError("At least one economic evaluation is required.")
    return _summarize_returns(
        [
            trade_return
            for evaluation in evaluations
            for trade_return in evaluation.trade_net_returns_bps
        ],
        rows=sum(evaluation.rows for evaluation in evaluations),
        long_signals=sum(evaluation.long_signals for evaluation in evaluations),
        skipped_overlapping_signals=sum(
            evaluation.skipped_overlapping_signals for evaluation in evaluations
        ),
        exposure_ms=sum(evaluation.exposure_ms for evaluation in evaluations),
        observation_ms=sum(evaluation.observation_ms for evaluation in evaluations),
        config=config,
    )


def economic_evaluation_payload(report: EconomicEvaluation) -> dict[str, object]:
    """Serialize summary metrics without embedding every individual trade return."""
    return {
        "rows": report.rows,
        "long_signals": report.long_signals,
        "accepted_trades": report.accepted_trades,
        "skipped_overlapping_signals": report.skipped_overlapping_signals,
        "winning_trades": report.winning_trades,
        "losing_trades": report.losing_trades,
        "breakeven_trades": report.breakeven_trades,
        "starting_balance": report.starting_balance,
        "ending_balance": report.ending_balance,
        "net_pnl": report.net_pnl,
        "return_pct": report.return_pct,
        "maximum_closed_trade_drawdown_pct": report.maximum_closed_trade_drawdown_pct,
        "turnover_quote": report.turnover_quote,
        "turnover_multiple": report.turnover_multiple,
        "exposure_ratio": report.exposure_ratio,
        "total_net_return_bps": report.total_net_return_bps,
        "profit_factor": report.profit_factor,
    }
