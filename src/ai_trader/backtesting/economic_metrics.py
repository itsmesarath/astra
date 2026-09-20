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
    minimum_reentry_delay_ms: int = 0
    maximum_trades_per_session: int | None = None
    session_profit_target: float | None = None
    session_loss_limit: float | None = None

    def validate(self) -> None:
        """Reject invalid or leveraged capital assumptions."""
        if not math.isfinite(self.starting_balance) or self.starting_balance <= 0:
            raise ValueError("Starting balance must be finite and positive.")
        if not math.isfinite(self.position_fraction) or not 0 < self.position_fraction <= 1:
            raise ValueError("Position fraction must be in the interval (0, 1].")
        if (
            not isinstance(self.minimum_reentry_delay_ms, int)
            or isinstance(self.minimum_reentry_delay_ms, bool)
            or self.minimum_reentry_delay_ms < 0
        ):
            raise ValueError("Minimum re-entry delay must be a nonnegative integer.")
        if self.maximum_trades_per_session is not None:
            if (
                not isinstance(self.maximum_trades_per_session, int)
                or isinstance(self.maximum_trades_per_session, bool)
                or self.maximum_trades_per_session <= 0
            ):
                raise ValueError("Maximum trades per session must be a positive integer.")
        for value, name in (
            (self.session_profit_target, "Session profit target"),
            (self.session_loss_limit, "Session loss limit"),
        ):
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive when configured.")


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
class SettledTrade:
    """One label-based settlement; not an exchange fill or marked position."""

    entry_time_ms: int
    exit_time_ms: int
    entry_notional: float
    net_return_bps: float
    net_pnl: float
    balance_before: float
    balance_after: float


@dataclass(frozen=True, slots=True)
class EconomicEvaluation:
    """Closed-trade economics for one or more chronological validation sessions."""

    rows: int
    long_signals: int
    accepted_trades: int
    skipped_overlapping_signals: int
    skipped_cooldown_signals: int
    skipped_trade_limit_signals: int
    skipped_session_limit_signals: int
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
    trade_ledger: tuple[SettledTrade, ...]
    observation_start_ms: int
    observation_end_ms: int
    last_exit_time_ms: int
    previous_exit_time_ms: int


def _summarize_trades(
    trades: Sequence[SettledTrade],
    *,
    rows: int,
    long_signals: int,
    skipped_overlapping_signals: int,
    skipped_cooldown_signals: int,
    skipped_trade_limit_signals: int,
    skipped_session_limit_signals: int,
    exposure_ms: int,
    observation_start_ms: int,
    observation_end_ms: int,
    starting_balance: float,
    last_exit_time_ms: int,
    previous_exit_time_ms: int,
) -> EconomicEvaluation:
    """Summarize actual settlements without recomputing a different capital path."""
    balance = starting_balance
    peak_balance = balance
    maximum_drawdown = 0.0
    turnover_quote = 0.0
    gains = 0.0
    losses = 0.0
    normalized_returns = tuple(trade.net_return_bps for trade in trades)
    for trade in trades:
        if trade.balance_before != balance:
            raise ValueError("Trade ledger balances must form a continuous capital path.")
        # Outcome labels cannot supply actual sell notional: retain the explicit proxy.
        turnover_quote += 2 * trade.entry_notional
        balance = trade.balance_after
        if trade.net_pnl > 0:
            gains += trade.net_pnl
        elif trade.net_pnl < 0:
            losses += -trade.net_pnl
        peak_balance = max(peak_balance, balance)
        drawdown = (peak_balance - balance) / peak_balance
        maximum_drawdown = max(maximum_drawdown, drawdown)

    accepted_trades = len(normalized_returns)
    winning_trades = sum(value > 0 for value in normalized_returns)
    losing_trades = sum(value < 0 for value in normalized_returns)
    ending_balance = balance
    net_pnl = ending_balance - starting_balance
    observation_ms = observation_end_ms - observation_start_ms + 1
    return EconomicEvaluation(
        rows=rows,
        long_signals=long_signals,
        accepted_trades=accepted_trades,
        skipped_overlapping_signals=skipped_overlapping_signals,
        skipped_cooldown_signals=skipped_cooldown_signals,
        skipped_trade_limit_signals=skipped_trade_limit_signals,
        skipped_session_limit_signals=skipped_session_limit_signals,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        breakeven_trades=accepted_trades - winning_trades - losing_trades,
        starting_balance=starting_balance,
        ending_balance=ending_balance,
        net_pnl=net_pnl,
        return_pct=net_pnl / starting_balance * 100,
        maximum_closed_trade_drawdown_pct=maximum_drawdown * 100,
        turnover_quote=turnover_quote,
        turnover_multiple=turnover_quote / starting_balance,
        exposure_ms=exposure_ms,
        observation_ms=observation_ms,
        exposure_ratio=exposure_ms / observation_ms if observation_ms > 0 else 0.0,
        total_net_return_bps=sum(normalized_returns),
        profit_factor=gains / losses if losses > 0 else None,
        trade_net_returns_bps=normalized_returns,
        trade_ledger=tuple(trades),
        observation_start_ms=observation_start_ms,
        observation_end_ms=observation_end_ms,
        last_exit_time_ms=last_exit_time_ms,
        previous_exit_time_ms=previous_exit_time_ms,
    )


def evaluate_spot_economics(
    probabilities: Sequence[Sequence[float]],
    outcomes: Sequence[TradeOutcome],
    policy: DecisionPolicy,
    config: EconomicConfig,
    *,
    previous_evaluation: EconomicEvaluation | None = None,
) -> EconomicEvaluation:
    """Settle label-based trades causally, carrying capital/cooldown between sessions.

    Only session counters and PnL limits reset. Intervals are inclusive: another
    entry at the exact exit millisecond is rejected. No intra-trade marks exist.
    """
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

    if (
        previous_evaluation is not None
        and outcomes[0].entry_time_ms <= previous_evaluation.observation_end_ms
    ):
        raise ValueError("Economic sessions must be strictly chronological and non-overlapping.")

    long_signals = 0
    skipped_overlapping_signals = 0
    skipped_cooldown_signals = 0
    skipped_trade_limit_signals = 0
    skipped_session_limit_signals = 0
    available_after_ms = (
        previous_evaluation.last_exit_time_ms if previous_evaluation is not None else -1
    )
    trades: list[SettledTrade] = []
    pending: TradeOutcome | None = None
    pending_notional = 0.0
    accepted_count = 0
    exposure_ms = 0
    starting_balance = (
        previous_evaluation.ending_balance
        if previous_evaluation is not None
        else config.starting_balance
    )
    balance = starting_balance
    session_limit_reached = False

    def settle() -> None:
        nonlocal pending, balance, available_after_ms, session_limit_reached
        if pending is None:
            return
        pnl = pending_notional * pending.net_return_bps / BASIS_POINTS_PER_UNIT
        next_balance = balance + pnl
        if not math.isfinite(next_balance) or next_balance <= 0:
            raise ValueError("Settlement balance must remain finite and positive.")
        trades.append(
            SettledTrade(
                entry_time_ms=pending.entry_time_ms,
                exit_time_ms=pending.exit_time_ms,
                entry_notional=pending_notional,
                net_return_bps=pending.net_return_bps,
                net_pnl=pnl,
                balance_before=balance,
                balance_after=next_balance,
            )
        )
        balance = next_balance
        available_after_ms = pending.exit_time_ms
        pending = None
        session_pnl = balance - starting_balance
        session_limit_reached = (
            config.session_profit_target is not None and session_pnl >= config.session_profit_target
        ) or (config.session_loss_limit is not None and session_pnl <= -config.session_loss_limit)

    for probability_row, outcome in zip(probabilities, outcomes, strict=True):
        if pending is not None and pending.exit_time_ms <= outcome.entry_time_ms:
            settle()
        decision = decide_position(probability_row, policy)
        if decision.intent != "LONG":
            continue
        long_signals += 1
        if pending is not None or outcome.entry_time_ms <= available_after_ms:
            skipped_overlapping_signals += 1
            continue
        if session_limit_reached:
            skipped_session_limit_signals += 1
            continue
        if (
            config.maximum_trades_per_session is not None
            and accepted_count >= config.maximum_trades_per_session
        ):
            skipped_trade_limit_signals += 1
            continue
        if (
            available_after_ms >= 0
            and outcome.entry_time_ms <= available_after_ms + config.minimum_reentry_delay_ms
        ):
            skipped_cooldown_signals += 1
            continue
        pending = outcome
        pending_notional = balance * config.position_fraction
        accepted_count += 1
        exposure_ms += outcome.exit_time_ms - outcome.entry_time_ms + 1

    # Drain the final accepted trade at its exit, even if no later signal exists.
    settle()
    return _summarize_trades(
        trades,
        rows=len(outcomes),
        long_signals=long_signals,
        skipped_overlapping_signals=skipped_overlapping_signals,
        skipped_cooldown_signals=skipped_cooldown_signals,
        skipped_trade_limit_signals=skipped_trade_limit_signals,
        skipped_session_limit_signals=skipped_session_limit_signals,
        exposure_ms=exposure_ms,
        observation_start_ms=outcomes[0].entry_time_ms,
        observation_end_ms=max(outcome.exit_time_ms for outcome in outcomes),
        starting_balance=starting_balance,
        last_exit_time_ms=available_after_ms,
        previous_exit_time_ms=(
            previous_evaluation.last_exit_time_ms if previous_evaluation is not None else -1
        ),
    )


def aggregate_economic_evaluations(
    evaluations: Sequence[EconomicEvaluation],
    config: EconomicConfig,
) -> EconomicEvaluation:
    """Combine a continuous fold ledger; independently reset folds are invalid."""
    config.validate()
    if not evaluations:
        raise ValueError("At least one economic evaluation is required.")
    expected_balance = config.starting_balance
    previous_end_ms = -1
    previous_exit_ms = -1
    for evaluation in evaluations:
        if evaluation.starting_balance != expected_balance:
            raise ValueError("Economic evaluations must use continuous capital across sessions.")
        if evaluation.observation_start_ms <= previous_end_ms:
            raise ValueError(
                "Economic sessions must be strictly chronological and non-overlapping."
            )
        if evaluation.previous_exit_time_ms != previous_exit_ms:
            raise ValueError("Economic evaluations must carry cooldown state across sessions.")
        expected_balance = evaluation.ending_balance
        previous_end_ms = evaluation.observation_end_ms
        previous_exit_ms = evaluation.last_exit_time_ms
    return _summarize_trades(
        [trade for evaluation in evaluations for trade in evaluation.trade_ledger],
        rows=sum(evaluation.rows for evaluation in evaluations),
        long_signals=sum(evaluation.long_signals for evaluation in evaluations),
        skipped_overlapping_signals=sum(
            evaluation.skipped_overlapping_signals for evaluation in evaluations
        ),
        skipped_cooldown_signals=sum(
            evaluation.skipped_cooldown_signals for evaluation in evaluations
        ),
        skipped_trade_limit_signals=sum(
            evaluation.skipped_trade_limit_signals for evaluation in evaluations
        ),
        skipped_session_limit_signals=sum(
            evaluation.skipped_session_limit_signals for evaluation in evaluations
        ),
        exposure_ms=sum(evaluation.exposure_ms for evaluation in evaluations),
        observation_start_ms=evaluations[0].observation_start_ms,
        observation_end_ms=evaluations[-1].observation_end_ms,
        starting_balance=config.starting_balance,
        last_exit_time_ms=evaluations[-1].last_exit_time_ms,
        previous_exit_time_ms=-1,
    )


def economic_evaluation_payload(report: EconomicEvaluation) -> dict[str, object]:
    """Serialize summary metrics without embedding every individual trade return."""
    return {
        "accounting_policy": "label_settlement_continuous_capital_v2",
        "turnover_definition": "twice_entry_notional_proxy",
        "drawdown_definition": "closed_trade_only_no_position_marks",
        "observation_definition": "inclusive_first_entry_to_maximum_outcome_exit",
        "rows": report.rows,
        "long_signals": report.long_signals,
        "accepted_trades": report.accepted_trades,
        "skipped_overlapping_signals": report.skipped_overlapping_signals,
        "skipped_cooldown_signals": report.skipped_cooldown_signals,
        "skipped_trade_limit_signals": report.skipped_trade_limit_signals,
        "skipped_session_limit_signals": report.skipped_session_limit_signals,
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
        "exposure_ms": report.exposure_ms,
        "observation_ms": report.observation_ms,
        "observation_start_ms": report.observation_start_ms,
        "observation_end_ms": report.observation_end_ms,
        "last_exit_time_ms": report.last_exit_time_ms,
        "total_net_return_bps": report.total_net_return_bps,
        "profit_factor": report.profit_factor,
    }
