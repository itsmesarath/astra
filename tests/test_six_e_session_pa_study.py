"""Checks for the intraday price-action session study on synthetic minute series."""

import numpy as np

from ai_trader.research import six_e_session_pa_study as ps


def test_rolling_max_excludes_current_minute():
    a = np.array([1.0, 5.0, 2.0, 3.0, 9.0])
    out = ps.rolling_max(a, 2)
    assert np.isnan(out[:2]).all() and list(out[2:]) == [5.0, 5.0, 3.0]
    assert list(ps.rolling_min(a, 2)[2:]) == [1.0, 2.0, 2.0]


def test_atr_uses_completed_bars_only():
    n = 15 * 40
    c = np.full(n, 100.0)
    h, l = c + 2, c - 2  # every 15-minute bar has a 4-tick range
    a = ps.atr_minutes(h, l, c)
    assert np.isnan(a[:15 * 16]).all()
    assert np.allclose(a[15 * 16:], 4.0)


def test_breakout_signal_and_target_exit():
    n = 1440 * 2
    c = np.full(n, 1000.0)
    c[1440 + 500:] = 1030.0  # jump of 30 ticks at 08:20 UTC on day 2, then flat
    c[1440 + 560:] = 1100.0  # second jump 60 minutes later carries price to the target
    h, l = c + 1, c - 1
    a = np.full(n, 10.0)
    sig = ps.pattern_signals(c, h, l, a, "breakout")
    assert sig[1440 + 500] == 1 and sig[1440 + 499] == 0
    ps._ADJ = np.zeros(n)
    ps._MONTHS = np.array([202507, 202507])
    mod, dayk = ps.minute_of_day(n), np.repeat([0, 1], 1440)
    trades = ps.simulate(c, h, l, a, mod, dayk, [None, None], sig, "market", 1.0, 3.0, 240, False, None)
    assert trades and trades[0]["why"] == "target"
    assert np.isclose(trades[0]["net"], 30.0 - ps.MARKET_COST)  # target = 3 x 10-tick stop


def test_stop_first_when_both_touched_and_day_end_flat():
    n = 1440
    c = np.full(n, 1000.0)
    c[600:] = 1020.0
    h, l = c + 1, c - 1
    h[601], l[601] = 1100.0, 900.0  # both touched in the first minute after entry
    a = np.full(n, 10.0)
    sig = np.zeros(n, dtype=np.int8)
    sig[600] = 1
    sig[ps.DAY_END + 5] = 1  # too late in the day: must be ignored
    ps._ADJ = np.zeros(n)
    ps._MONTHS = np.array([202507])
    trades = ps.simulate(c, h, l, a, ps.minute_of_day(n), np.zeros(n, dtype=int), [None], sig,
                         "market", 1.0, 2.0, 240, False, None)
    assert len(trades) == 1 and trades[0]["why"] == "stop"
    assert np.isclose(trades[0]["net"], -10.0 - ps.MARKET_COST)
