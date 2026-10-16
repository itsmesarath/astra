"""Mechanics of the rule-based 6E strategy tester on hand-built minute paths."""

from datetime import date

import numpy as np
import pytest

from ai_trader.research import six_e_intraday_strategies as s


def flat_day(d=date(2025, 7, 15), price=22000.0):
    n = 1440
    arr = {k: np.full(n, price) for k in ("open", "high", "low", "close")}
    arr["traded"] = np.ones(n, dtype=bool)
    arr["date"] = d
    return arr


def test_stop_is_assumed_before_target_in_the_same_minute():
    a = flat_day()
    a["high"][101], a["low"][101] = 22010, 21990
    assert s.run_trade(a, 100, 1, 22000, 21995, 22005, 200, cost=2) == -7


def test_target_and_time_exit():
    a = flat_day()
    a["high"][105] = 22010
    assert s.run_trade(a, 100, 1, 22000, 21990, 22008, 200, cost=2) == 6
    a = flat_day()
    a["close"][150] = 22003
    assert s.run_trade(a, 100, -1, 22000, 22010, None, 150, cost=2) == -5


def test_dst_aware_session_times():
    assert s.utc_minute(date(2025, 7, 15), 8, 30, s.NEW_YORK) == 12 * 60 + 30
    assert s.utc_minute(date(2025, 12, 15), 8, 30, s.NEW_YORK) == 13 * 60 + 30
    assert s.utc_minute(date(2025, 7, 15), 8, 0, s.LONDON) == 7 * 60


def test_orb_long_breakout_hits_target():
    a = flat_day()
    start = s.utc_minute(a["date"], 8, 0, s.LONDON)
    a["high"][start:start + 15] = 22005  # range 21995-22005, width 10
    a["low"][start:start + 15] = 21995
    a["high"][start + 20] = 22006  # breakout -> buy at 22006
    a["high"][start + 30] = 22016  # target 1 x range = 22016
    result = s.orb(a, s.LONDON, (8, 0), 15, 1.0, 120, cost=2.6)
    assert result == pytest.approx(10 - 2.6)


def test_release_fade_direction():
    a = flat_day()
    t = s.utc_minute(a["date"], 8, 29, s.NEW_YORK)
    a["close"][t + 2:] = 22010  # +10 ticks in two minutes, then flat
    a["high"][t + 2:] = 22010
    a["low"][t + 2:] = 22010
    a["low"][t + 10] = 21990  # fade target 22010-16=21994 reached
    assert s.release(a, 2, 4, -1, 8, 16, 30, cost=2.6) == pytest.approx(16 - 2.6)
    assert s.release(a, 2, 4, 1, 8, 16, 30, cost=2.6) == pytest.approx(-8 - 2.6)
