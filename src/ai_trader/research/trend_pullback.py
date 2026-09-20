"""Fixed, causal trend-pullback hypothesis; no fitting, orders, or outcome access.

Indicators reset at each supplied session. Missing bars fail closed rather than
being interpolated. ATR seeds from 14 true ranges starting at the second bar,
whose previous close is known. Signals do not promise an executable trade.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from ai_trader.features.kline_dataset import Kline

INTERVAL_MS = 300_000
REFERENCE_ROUND_TRIP_BPS = Decimal("24")
HOLDING_BARS = 24


@dataclass(frozen=True, slots=True)
class PullbackPoint:
    time_ms: int
    close: Decimal
    ema20: Decimal | None
    ema60: Decimal | None
    atr14: Decimal | None


@dataclass(frozen=True, slots=True)
class PullbackSignal:
    source_session: str
    time_ms: int
    reference_close: Decimal
    atr: Decimal
    stop_distance: Decimal
    target_distance: Decimal
    holding_bars: int = HOLDING_BARS


@dataclass(frozen=True, slots=True)
class PullbackResult:
    source_session: str
    points: tuple[PullbackPoint, ...]
    signals: tuple[PullbackSignal, ...]


def _validate(candles: tuple[Kline, ...]) -> None:
    previous_end: int | None = None
    for candle in candles:
        if (
            type(candle.open_time_ms) is not int
            or type(candle.close_time_ms) is not int
            or candle.open_time_ms < 0
            or candle.close_time_ms - candle.open_time_ms + 1 != INTERVAL_MS
        ):
            raise ValueError("Expected nonnegative integer timestamps and five-minute candles.")
        if previous_end is not None and candle.open_time_ms != previous_end + 1:
            raise ValueError("Session candles must be contiguous and chronological.")
        prices = (candle.open, candle.high, candle.low, candle.close)
        if any(not isinstance(p, Decimal) or not p.is_finite() or p <= 0 for p in prices):
            raise ValueError("OHLC prices must be finite positive Decimals.")
        if candle.high < max(candle.open, candle.close) or candle.low > min(
            candle.open, candle.close
        ):
            raise ValueError("Inconsistent OHLC range.")
        previous_end = candle.close_time_ms


def generate_pullback_signals(source_session: str, candles: tuple[Kline, ...]) -> PullbackResult:
    """Emit close-time events with ATR frozen at the signal, never future entries.

    EMA seeds use the first period's simple mean; subsequent updates use 2/(n+1).
    ATR uses Wilder smoothing. The slow-EMA slope requires six prior completed
    bars, so the earliest eligible signal is bar index 65. The cost screen uses
    the signal close (the future entry price is unknown), and always the fixed
    24 bps reference, not the replay stress cost. Execution must separately check
    entry feasibility, positive stop prices, risk limits and within-session horizon.
    """
    if not isinstance(source_session, str) or not source_session.strip():
        raise ValueError("A nonempty source session is required.")
    if not candles:
        raise ValueError("At least one candle is required.")
    _validate(candles)
    points: list[PullbackPoint] = []
    signals: list[PullbackSignal] = []
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        closes: list[Decimal] = []
        ranges: list[Decimal] = []
        fast = slow = atr = None
        for index, candle in enumerate(candles):
            closes.append(candle.close)
            if index == 19:
                fast = sum(closes, Decimal(0)) / 20
            elif fast is not None:
                fast += (candle.close - fast) * Decimal(2) / 21
            if index == 59:
                slow = sum(closes, Decimal(0)) / 60
            elif slow is not None:
                slow += (candle.close - slow) * Decimal(2) / 61
            if index:
                true_range = max(
                    candle.high - candle.low,
                    abs(candle.high - closes[-2]),
                    abs(candle.low - closes[-2]),
                )
                if index <= 14:
                    ranges.append(true_range)
                if index == 14:
                    atr = sum(ranges, Decimal(0)) / 14
                elif atr is not None:
                    atr = (atr * 13 + true_range) / 14
            point = PullbackPoint(candle.close_time_ms, candle.close, fast, slow, atr)
            points.append(point)
            if index < 65:
                continue
            previous = points[-2]
            prior_slow = points[index - 6].ema60
            assert fast is not None and slow is not None and atr is not None
            assert previous.ema20 is not None and prior_slow is not None
            if (
                fast > slow > prior_slow
                and previous.close <= previous.ema20
                and candle.close > fast
                and atr > 0
                and 2 * atr * 10_000 >= 3 * REFERENCE_ROUND_TRIP_BPS * candle.close
            ):
                signals.append(
                    PullbackSignal(source_session, point.time_ms, candle.close, atr, atr, 2 * atr)
                )
    return PullbackResult(source_session, tuple(points), tuple(signals))
