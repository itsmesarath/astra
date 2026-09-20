"""Offline, long-only OHLC replay, independent of precomputed outcome labels.

Signals are supplied at completed candle closes. Their producer must itself be
causal; timestamp validation cannot prove how those signals were generated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import Literal

from ai_trader.backtesting.economic_metrics import EconomicConfig
from ai_trader.features.kline_dataset import Kline, TripleBarrierConfig

BPS = Decimal("10000")
ZERO = Decimal("0")
ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class ReplayConfig:
    """Fee-inclusive cash sizing; reference barriers retain labeling-v2 geometry."""

    capital: EconomicConfig = field(default_factory=EconomicConfig)
    barriers: TripleBarrierConfig = field(default_factory=TripleBarrierConfig)
    holding_bars: int = 120
    entry_delay_bars: int = 0
    quantity_step: Decimal = Decimal("0.00000001")
    barrier_mode: Literal["label_reference", "signal_distances"] = "label_reference"
    require_full_horizon: bool = False

    def validate(self) -> None:
        self.capital.validate()
        if self.barrier_mode not in ("label_reference", "signal_distances"):
            raise ValueError("Unknown replay barrier mode.")
        if type(self.require_full_horizon) is not bool:
            raise ValueError("Full-horizon requirement must be boolean.")
        if self.barrier_mode == "label_reference":
            self.barriers.validate()
        else:
            for cost in (self.barriers.taker_fee_bps, self.barriers.slippage_bps):
                if not isinstance(cost, Decimal) or not cost.is_finite() or cost < 0:
                    raise ValueError("Per-side costs must be finite nonnegative Decimals.")
        for value, minimum, name in (
            (self.holding_bars, 1, "Holding bars"),
            (self.entry_delay_bars, 0, "Entry delay"),
        ):
            if type(value) is not int or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}.")
        if not self.quantity_step.is_finite() or self.quantity_step <= 0:
            raise ValueError("Quantity step must be finite and positive.")
        if max(self.barriers.taker_fee_bps, self.barriers.slippage_bps) >= BPS:
            raise ValueError("Each per-side cost must be less than 10000 bps.")
        if self.barrier_mode == "label_reference" and (
            self.barriers.stop_loss_bps - self.barriers.round_trip_cost_bps >= BPS
        ):
            raise ValueError("Stop reference price must remain positive.")


@dataclass(frozen=True, slots=True)
class SignalDistances:
    """Absolute gross-price offsets frozen by the signal producer at close."""

    signal_time_ms: int
    stop_distance: Decimal
    target_distance: Decimal


@dataclass(frozen=True, slots=True)
class CandleSession:
    name: str
    candles: tuple[Kline, ...]
    long_signal_times_ms: tuple[int, ...] = ()
    signal_distances: tuple[SignalDistances, ...] = ()


@dataclass(frozen=True, slots=True)
class ReplayFill:
    source_session: str
    event_time_ms: int
    side: Literal["BUY", "SELL"]
    reference_price: Decimal
    price: Decimal
    quantity: Decimal
    fee_quote: Decimal
    reason: str

    @property
    def notional_quote(self) -> Decimal:
        return self.quantity * self.price


@dataclass(frozen=True, slots=True)
class ReplayTrade:
    signal_time_ms: int
    entry: ReplayFill
    exit: ReplayFill
    net_pnl: Decimal


@dataclass(frozen=True, slots=True)
class CandleMark:
    source_session: str
    event_time_ms: int
    cash: Decimal
    quantity: Decimal
    close: Decimal
    equity: Decimal


@dataclass(frozen=True, slots=True)
class SignalDecision:
    source_session: str
    signal_time_ms: int
    reason: str
    entry_time_ms: int | None = None


@dataclass(frozen=True, slots=True)
class SessionResult:
    source_session: str
    starting_balance: Decimal
    ending_balance: Decimal
    trades: int


@dataclass(frozen=True, slots=True)
class ReplayReport:
    config: ReplayConfig
    input_sha256: str
    sessions: tuple[SessionResult, ...]
    fills: tuple[ReplayFill, ...]
    trades: tuple[ReplayTrade, ...]
    marks: tuple[CandleMark, ...]
    decisions: tuple[SignalDecision, ...]
    starting_balance: Decimal
    ending_balance: Decimal
    net_pnl: Decimal
    fees_quote: Decimal
    turnover_quote: Decimal
    maximum_marked_drawdown_pct: Decimal
    maximum_closed_trade_drawdown_pct: Decimal
    exposure_ms: int
    observation_ms: int


@dataclass(frozen=True, slots=True)
class _Position:
    signal_time_ms: int
    entry: ReplayFill
    target: Decimal
    stop: Decimal
    final_index: int


def _validate_sessions(sessions: tuple[CandleSession, ...]) -> None:
    if not sessions:
        raise ValueError("At least one candle session is required.")
    previous_end = -1
    names: set[str] = set()
    interval: int | None = None
    for session in sessions:
        if not session.name or session.name in names or not session.candles:
            raise ValueError("Sessions require unique nonempty names and candles.")
        names.add(session.name)
        previous_bar_end = None
        for candle in session.candles:
            if (
                type(candle.open_time_ms) is not int
                or type(candle.close_time_ms) is not int
                or candle.open_time_ms < 0
                or candle.close_time_ms < candle.open_time_ms
            ):
                raise ValueError("Candle timestamps must be nonnegative ordered integers.")
            if interval is None:
                interval = candle.close_time_ms - candle.open_time_ms + 1
            if candle.close_time_ms - candle.open_time_ms + 1 != interval:
                raise ValueError("Replay candles must have a fixed interval.")
            if previous_bar_end is not None and candle.open_time_ms != previous_bar_end + 1:
                raise ValueError("Within-session candles must be contiguous and ordered.")
            prices = (candle.open, candle.high, candle.low, candle.close)
            if any(not price.is_finite() or price <= 0 for price in prices):
                raise ValueError("OHLC prices must be finite and positive.")
            if candle.high < max(candle.open, candle.close) or candle.low > min(
                candle.open, candle.close
            ):
                raise ValueError("OHLC range is inconsistent.")
            previous_bar_end = candle.close_time_ms
        if session.candles[0].open_time_ms <= previous_end:
            raise ValueError("Sessions must be chronological and non-overlapping.")
        previous_end = session.candles[-1].close_time_ms
        close_times = {candle.close_time_ms for candle in session.candles}
        previous_signal = -1
        for signal in session.long_signal_times_ms:
            if type(signal) is not int or signal not in close_times or signal <= previous_signal:
                raise ValueError("Signals must be unique ordered candle-close timestamps.")
            previous_signal = signal


def _json_decimal(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported report value: {type(value).__name__}")


def _entry_rejection(
    capital: EconomicConfig,
    cash: Decimal,
    session_start: Decimal,
    session_trades: int,
    last_exit: int,
    event_time: int,
) -> str | None:
    pnl = cash - session_start
    if (
        capital.session_profit_target is not None
        and pnl >= Decimal(str(capital.session_profit_target))
    ) or (
        capital.session_loss_limit is not None and pnl <= -Decimal(str(capital.session_loss_limit))
    ):
        return "session_limit"
    if (
        capital.maximum_trades_per_session is not None
        and session_trades >= capital.maximum_trades_per_session
    ):
        return "trade_limit"
    if last_exit >= 0 and event_time <= last_exit + capital.minimum_reentry_delay_ms:
        return "cooldown"
    return None


def replay_candles(sessions: tuple[CandleSession, ...], config: ReplayConfig) -> ReplayReport:
    """Replay cash/fills without reading labels or invoking the label outcome calculator.

    Market-triggered exits use open-first, then conservative intrabar stop-first
    ordering. Intrabar exit times are assigned to close. Pending orders expire at
    session end, and any open position is liquidated at the final close. Session
    loss/profit gates use settled net PnL, not unrealized marks, and block entries
    rather than guaranteeing a maximum loss. Volume/queue constraints are absent.
    """
    config.validate()
    _validate_sessions(sessions)
    for session in sessions:
        if config.barrier_mode == "label_reference":
            if session.signal_distances:
                raise ValueError("Signal distances require explicit signal_distances mode.")
            continue
        if tuple(item.signal_time_ms for item in session.signal_distances) != (
            session.long_signal_times_ms
        ):
            raise ValueError("Signal distances must match every signal in order exactly once.")
        for item in session.signal_distances:
            if type(item.signal_time_ms) is not int:
                raise ValueError("Distance timestamps must be integers.")
            for distance in (item.stop_distance, item.target_distance):
                if not isinstance(distance, Decimal) or not distance.is_finite() or distance <= 0:
                    raise ValueError("Signal distances must be finite positive Decimals.")
    capital, barriers = config.capital, config.barriers
    cash = starting_balance = Decimal(str(capital.starting_balance))
    fee_rate = barriers.taker_fee_bps / BPS
    slip_rate = barriers.slippage_bps / BPS
    fraction = Decimal(str(capital.position_fraction))
    marked_peak = closed_peak = cash
    marked_drawdown = closed_drawdown = ZERO
    last_exit = -1
    position: _Position | None = None
    fills: list[ReplayFill] = []
    trades: list[ReplayTrade] = []
    marks: list[CandleMark] = []
    decisions: list[SignalDecision] = []
    results: list[SessionResult] = []

    for session in sessions:
        session_start = cash
        session_trades = 0
        signals = set(session.long_signal_times_ms)
        distances = {item.signal_time_ms: item for item in session.signal_distances}
        pending: tuple[int, int] | None = None  # due bar, signal timestamp

        for index, candle in enumerate(session.candles):
            if pending is not None and pending[0] == index:
                _, signal_time = pending
                reason = _entry_rejection(
                    capital, cash, session_start, session_trades, last_exit, candle.open_time_ms
                )
                if config.barrier_mode == "signal_distances":
                    geometry = distances[signal_time]
                    target = candle.open + geometry.target_distance
                    stop = candle.open - geometry.stop_distance
                    if stop <= 0 and reason is None:
                        reason = "invalid_stop_price"
                else:
                    target = candle.open * (
                        ONE + (barriers.take_profit_bps + barriers.round_trip_cost_bps) / BPS
                    )
                    stop = candle.open * (
                        ONE + (barriers.round_trip_cost_bps - barriers.stop_loss_bps) / BPS
                    )
                price = candle.open * (ONE + slip_rate)
                budget = cash * fraction
                quantity = (
                    budget / (price * (ONE + fee_rate)) / config.quantity_step
                ).to_integral_value(rounding=ROUND_DOWN) * config.quantity_step
                if reason is None and quantity <= 0:
                    reason = "insufficient_cash"
                if reason is None:
                    fee = quantity * price * fee_rate
                    entry = ReplayFill(
                        session.name,
                        candle.open_time_ms,
                        "BUY",
                        candle.open,
                        price,
                        quantity,
                        fee,
                        "entry",
                    )
                    cash -= entry.notional_quote + fee
                    if cash < 0:
                        raise ArithmeticError("Replay entry exceeded its cash budget.")
                    fills.append(entry)
                    position = _Position(
                        signal_time,
                        entry,
                        target,
                        stop,
                        index + config.holding_bars - 1,
                    )
                    session_trades += 1
                decisions.append(
                    SignalDecision(
                        session.name,
                        signal_time,
                        reason or "filled",
                        candle.open_time_ms if reason is None else None,
                    )
                )
                pending = None

            if position is not None:
                reference = None
                exit_time = candle.close_time_ms
                if candle.open <= position.stop:
                    reference, reason, exit_time = candle.open, "gap_stop", candle.open_time_ms
                elif candle.open >= position.target:
                    reference, reason, exit_time = candle.open, "gap_target", candle.open_time_ms
                elif candle.low <= position.stop:
                    reference = position.stop
                    reason = "ambiguous_stop" if candle.high >= position.target else "stop"
                elif candle.high >= position.target:
                    reference, reason = position.target, "target"
                elif index >= position.final_index:
                    reference, reason = candle.close, "time"
                elif index == len(session.candles) - 1:
                    reference, reason = candle.close, "session_end"
                if reference is not None:
                    price = reference * (ONE - slip_rate)
                    quantity = position.entry.quantity
                    fee = quantity * price * fee_rate
                    exit_fill = ReplayFill(
                        session.name, exit_time, "SELL", reference, price, quantity, fee, reason
                    )
                    cash += exit_fill.notional_quote - fee
                    pnl = (
                        exit_fill.notional_quote
                        - fee
                        - position.entry.notional_quote
                        - position.entry.fee_quote
                    )
                    fills.append(exit_fill)
                    trades.append(
                        ReplayTrade(position.signal_time_ms, position.entry, exit_fill, pnl)
                    )
                    last_exit = exit_time
                    position = None
                    closed_peak = max(closed_peak, cash)
                    closed_drawdown = max(closed_drawdown, (closed_peak - cash) / closed_peak)

            quantity = position.entry.quantity if position is not None else ZERO
            equity = cash + quantity * candle.close
            marks.append(
                CandleMark(session.name, candle.close_time_ms, cash, quantity, candle.close, equity)
            )
            marked_peak = max(marked_peak, equity)
            marked_drawdown = max(marked_drawdown, (marked_peak - equity) / marked_peak)

            if candle.close_time_ms in signals:
                due_index = index + 1 + config.entry_delay_bars
                # Cash-dependent risk and cooldown are checked at execution, not
                # at signal close: a cooldown may expire before the due open.
                reason = (
                    "position_open"
                    if position is not None
                    else "pending_entry"
                    if pending is not None
                    else "session_end"
                    if due_index >= len(session.candles)
                    else "insufficient_horizon"
                    if config.require_full_horizon
                    and due_index + config.holding_bars > len(session.candles)
                    else None
                )
                if reason is not None:
                    decisions.append(SignalDecision(session.name, candle.close_time_ms, reason))
                else:
                    pending = (due_index, candle.close_time_ms)
        results.append(SessionResult(session.name, session_start, cash, session_trades))

    encoded = json.dumps(
        [asdict(session) for session in sessions], default=_json_decimal, sort_keys=True
    )
    return ReplayReport(
        config=config,
        input_sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        sessions=tuple(results),
        fills=tuple(fills),
        trades=tuple(trades),
        marks=tuple(marks),
        decisions=tuple(sorted(decisions, key=lambda decision: decision.signal_time_ms)),
        starting_balance=starting_balance,
        ending_balance=cash,
        net_pnl=cash - starting_balance,
        fees_quote=sum((fill.fee_quote for fill in fills), ZERO),
        turnover_quote=sum((fill.notional_quote for fill in fills), ZERO),
        maximum_marked_drawdown_pct=marked_drawdown * 100,
        maximum_closed_trade_drawdown_pct=closed_drawdown * 100,
        exposure_ms=sum(
            trade.exit.event_time_ms - trade.entry.event_time_ms + 1 for trade in trades
        ),
        observation_ms=sessions[-1].candles[-1].close_time_ms
        - sessions[0].candles[0].open_time_ms
        + 1,
    )


def replay_report_payload(report: ReplayReport) -> dict[str, object]:
    """Return JSON-safe audit data with exact Decimal values encoded as strings."""
    payload = {
        "schema_version": 2,
        "execution_mode": "paper",
        "fill_policy": "market_open_first_intrabar_stop_first_adverse_slippage",
        "barriers": (
            "signal_absolute_distances_from_entry_open_cost_independent"
            if report.config.barrier_mode == "signal_distances"
            else "label_v2_reference_geometry_actual_fill_costs"
        ),
        "horizon_policy": (
            "require_complete_session_window"
            if report.config.require_full_horizon
            else "allow_session_end_liquidation"
        ),
        "mark_policy": "candle_close_gross_position_value_no_exit_fee_reserve",
        "turnover_policy": "sum_buy_and_sell_fill_notionals_excluding_fees",
        "session_policy": "force_flat_at_final_close_carry_cash_and_cooldown",
        "signal_policy": "caller_supplied_completed_close_next_open_plus_delay",
        "limitations": ["no_queue_or_volume_model", "no_intrabar_marks", "no_exchange_filters"],
        **asdict(report),
    }
    return json.loads(json.dumps(payload, default=_json_decimal, allow_nan=False))


def write_replay_report(path: Path, report: ReplayReport) -> None:
    """Write a new audit artifact; refuse to overwrite an existing report."""
    payload = replay_report_payload(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output_file:
        json.dump(payload, output_file, default=_json_decimal, indent=2, allow_nan=False)
