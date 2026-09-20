"""Synthetic causal fixtures only; no historical outcomes or reserved data."""

from dataclasses import replace
from decimal import ROUND_UP, Decimal, localcontext

import pytest

from ai_trader.backtesting.candle_replay import CandleSession
from ai_trader.features.kline_dataset import Kline
from ai_trader.research.pullback_replay import replay_pullback_scenarios
from ai_trader.research.trend_pullback import generate_pullback_signals

D = Decimal


def bars(closes, width="1"):
    result = []
    for i, value in enumerate(closes):
        close = D(str(value))
        result.append(
            Kline(
                i * 300000,
                close,
                close + D(width),
                close - D(width),
                close,
                D(10),
                (i + 1) * 300000 - 1,
                D(1000),
                10,
                D(5),
            )
        )
    return tuple(result)


def crossing():
    return bars([100 + i for i in range(70)] + [155, 172, 173, 174])


def test_hand_calculated_seeds_and_updates():
    result = generate_pullback_signals("one", bars(range(100, 170)))
    assert result.points[18].ema20 is None
    assert result.points[19].ema20 == D("109.5")
    assert result.points[20].ema20 == D("110.5")
    assert result.points[58].ema60 is None
    assert result.points[59].ema60 == D("129.5")
    assert result.points[60].ema60 == D("130.5")
    assert result.points[13].atr14 is None
    assert result.points[14].atr14 == D(2)
    assert not result.signals


def test_wilder_range_uses_previous_close_and_gap():
    candles = bars([100] * 15 + [110])
    result = generate_pullback_signals("one", candles)
    assert result.points[15].atr14 == (D(2) * 13 + 11) / 14


def test_one_crossing_emits_one_frozen_atr_event():
    result = generate_pullback_signals("one", crossing())
    assert len(result.signals) == 1
    signal = result.signals[0]
    assert signal.time_ms == crossing()[71].close_time_ms
    assert signal.source_session == "one"
    assert signal.atr == result.points[71].atr14
    assert signal.stop_distance == signal.atr
    assert signal.target_distance == 2 * signal.atr
    assert signal.holding_bars == 24


def test_every_prefix_has_identical_indicators_and_events():
    candles = crossing()
    full = generate_pullback_signals("one", candles)
    for length in range(1, len(candles) + 1):
        prefix = generate_pullback_signals("one", candles[:length])
        assert prefix.points == full.points[:length]
        assert prefix.signals == tuple(
            s for s in full.signals if s.time_ms <= candles[length - 1].close_time_ms
        )


def test_future_changes_do_not_change_past_signal():
    candles = crossing()
    changed = candles[:72] + tuple(
        replace(c, open=D(500), close=D(500), high=D(501), low=D(499)) for c in candles[72:]
    )
    original = generate_pullback_signals("one", candles)
    other = generate_pullback_signals("one", changed)
    assert original.points[:72] == other.points[:72]
    assert original.signals[0] == other.signals[0]


def test_new_session_resets_warmup():
    assert generate_pullback_signals("two", crossing()[70:]).points[0].ema20 is None
    assert not generate_pullback_signals("two", crossing()[70:]).signals


def test_decimal_precision_does_not_change_results():
    candles = crossing()
    expected = generate_pullback_signals("one", candles)
    with localcontext() as ctx:
        ctx.prec = 9
        ctx.rounding = ROUND_UP
        assert generate_pullback_signals("one", candles) == expected


@pytest.mark.parametrize(
    "change",
    [
        {"open_time_ms": True},
        {"close_time_ms": 999},
        {"open_time_ms": -1},
        {"close": D("NaN")},
        {"high": D("Infinity")},
        {"low": D(0)},
        {"high": D(1)},
        {"low": D(1000)},
        {"close": 100.0},
    ],
)
def test_invalid_candles_fail_closed(change):
    with pytest.raises(ValueError):
        generate_pullback_signals("one", (replace(bars([100])[0], **change),))


def test_gaps_and_duplicates_are_rejected():
    candles = crossing()
    for invalid in (candles[:20] + candles[21:], candles[:20] + candles[19:]):
        with pytest.raises(ValueError, match="contiguous"):
            generate_pullback_signals("one", invalid)


def test_empty_inputs_rejected():
    with pytest.raises(ValueError):
        generate_pullback_signals("", crossing())
    with pytest.raises(ValueError):
        generate_pullback_signals("one", ())


def test_fixed_cost_screen_rejects_tiny_amplitude_crossing():
    closes = [D(100) + D(i) / 10000 for i in range(70)] + [D("100.0055"), D("100.0072")]
    assert not generate_pullback_signals("one", bars(closes, width="0.0001")).signals


def test_all_six_scenarios_share_frozen_signals_and_capital_limit():
    candles = bars([100 + i for i in range(70)] + [155, 172] + [173] * 26)
    study = replay_pullback_scenarios((CandleSession("one", candles),))
    with localcontext() as context:
        context.prec = 9
        context.rounding = ROUND_UP
        assert replay_pullback_scenarios((CandleSession("one", candles),)) == study
    assert len(study.signals[0].signals) == 1
    assert [(s.round_trip_cost_bps, s.entry_delay_bars) for s in study.scenarios] == [
        (24, 0),
        (24, 1),
        (36, 0),
        (36, 1),
        (48, 0),
        (48, 1),
    ]
    assert len({s.replay.input_sha256 for s in study.scenarios}) == 1
    for scenario in study.scenarios:
        report = scenario.replay
        assert len(report.trades) == 1
        assert report.trades[0].entry.notional_quote + report.trades[0].entry.fee_quote <= D(1000)
        assert report.config.require_full_horizon
        assert report.config.barriers.round_trip_cost_bps == scenario.round_trip_cost_bps
        assert report.config.barrier_mode == "signal_distances"


def test_scenario_runner_rejects_supplied_signals_and_bad_session_order():
    candles = crossing()
    with pytest.raises(ValueError, match="raw candles"):
        replay_pullback_scenarios((CandleSession("one", candles, (candles[0].close_time_ms,)),))
    with pytest.raises(ValueError, match="chronological"):
        replay_pullback_scenarios((CandleSession("one", candles), CandleSession("two", candles)))
