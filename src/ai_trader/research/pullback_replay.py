"""Run all six declared paper scenarios, without selecting a winning scenario."""

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from ai_trader.backtesting.candle_replay import (
    CandleSession,
    ReplayConfig,
    ReplayReport,
    SignalDistances,
    replay_candles,
)
from ai_trader.backtesting.economic_metrics import EconomicConfig
from ai_trader.features.kline_dataset import TripleBarrierConfig
from ai_trader.research.trend_pullback import (
    HOLDING_BARS,
    PullbackResult,
    generate_pullback_signals,
)


@dataclass(frozen=True, slots=True)
class PullbackScenario:
    round_trip_cost_bps: int
    entry_delay_bars: int
    replay: ReplayReport


@dataclass(frozen=True, slots=True)
class PullbackStudy:
    signals: tuple[PullbackResult, ...]
    scenarios: tuple[PullbackScenario, ...]


def replay_pullback_scenarios(sessions: tuple[CandleSession, ...]) -> PullbackStudy:
    """Research API, not a promotion gate or a historical-data loader.

    Caller must preselect research-only sessions. This API does not enforce a
    registered data manifest or lockbox exclusion. Indicator warmup resets per
    session; entries need all 24 holding bars within that session. Signal-close
    ATR stays frozen under both entry delays and all cost scenarios. Price levels
    anchor at the actual entry bar's open, before adverse execution slippage.
    """
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        return _replay_scenarios(sessions)


def _replay_scenarios(sessions: tuple[CandleSession, ...]) -> PullbackStudy:
    if not sessions:
        raise ValueError("Research sessions are required.")
    if any(s.long_signal_times_ms or s.signal_distances for s in sessions):
        raise ValueError("Supply raw candles, not caller-provided trading signals.")
    results = tuple(generate_pullback_signals(s.name, s.candles) for s in sessions)
    prepared = tuple(
        CandleSession(
            session.name,
            session.candles,
            tuple(signal.time_ms for signal in result.signals),
            tuple(
                SignalDistances(signal.time_ms, signal.stop_distance, signal.target_distance)
                for signal in result.signals
            ),
        )
        for session, result in zip(sessions, results, strict=True)
    )
    scenarios = []
    for cost in (24, 36, 48):
        for delay in (0, 1):
            config = ReplayConfig(
                capital=EconomicConfig(starting_balance=10_000, position_fraction=0.1),
                barriers=TripleBarrierConfig(
                    taker_fee_bps=Decimal(10), slippage_bps=Decimal(cost) / 2 - 10
                ),
                holding_bars=HOLDING_BARS,
                entry_delay_bars=delay,
                barrier_mode="signal_distances",
                require_full_horizon=True,
            )
            scenarios.append(PullbackScenario(cost, delay, replay_candles(prepared, config)))
    return PullbackStudy(results, tuple(scenarios))
