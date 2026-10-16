"""Synthetic checks for the hourly trend model with passive entries."""

import json
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from ai_trader.research import six_e_trend_model as tm

T = tm.TICK


def write_days(tmp_path, first: date, n_days: int, path_fn, contract="6EU5"):
    for k in range(n_days):
        d = first + timedelta(days=k)
        start = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()) * 10**9
        bars = []
        for i in range(1440):
            p = path_fn(k * 1440 + i)
            bars.append([start + i * tm.MINUTE_NS, p * T, (p + 1) * T, (p - 1) * T, p * T, 5, 1, 2, 3])
        (tmp_path / f"{d.isoformat()}.json").write_text(
            json.dumps({"utc_date": d.isoformat(), "contract": contract, "bars": bars})
        )


def test_hold_and_donchian():
    assert list(tm._hold(np.array([0, 1, 0, 0, -1, 0]))) == [0, 1, 1, 1, -1, -1]
    bars = {"close": np.array([1, 2, 3, 10.0]), "high": np.array([1, 2, 3, 10.0]),
            "low": np.array([1, 2, 3, 10.0])}
    assert list(tm.donchian(bars, 2)) == [0, 0, 1, 1]


def test_reserved_days_refused(tmp_path):
    (tmp_path / "2026-01-05.json").write_text(json.dumps({"utc_date": "2026-01-05", "contract": "6EH6", "bars": []}))
    with pytest.raises(ValueError, match="Reserved"):
        tm.load_minutes(tmp_path)


def test_steady_uptrend_is_traded_long_and_profitably(tmp_path):
    # Mon 2025-07-07 .. Thu 2025-07-10: rises 1 tick every 10 minutes with small wiggles.
    write_days(tmp_path, date(2025, 7, 7), 4, lambda i: 22000 + i // 10 + (i % 7 == 0) * -2)
    m = tm.load_minutes(tmp_path)
    trades = tm.backtest(m, "donchian", "market", 0.0, 3.0, fee=1.0)
    assert trades and all(t["direction"] == 1 for t in trades)
    assert sum(t["net_ticks"] for t in trades) > 0


def test_limit_entry_requires_trade_through(tmp_path):
    # Flat, then a jump of 100 ticks at minute 3000 (after 48 warm-up hours) that stays exactly flat afterwards.
    write_days(tmp_path, date(2025, 7, 7), 3, lambda i: 22000 if i < 3000 else 22100)
    m = tm.load_minutes(tmp_path)
    for key in ("high", "low"):
        m[key][:] = m["close"]  # no intra-minute range at all
    market = tm.backtest(m, "donchian", "market", 0.0, 3.0, fee=1.0)
    limit = tm.backtest(m, "donchian", "limit", 0.0, 3.0, fee=1.0)
    assert any(t["direction"] == 1 for t in market)  # market order enters after the breakout
    assert limit == []  # the passive limit at the close is never traded through


def test_back_adjustment_at_contract_change(tmp_path):
    write_days(tmp_path, date(2025, 9, 4), 1, lambda i: 22000, contract="6EU5")
    write_days(tmp_path, date(2025, 9, 5), 1, lambda i: 22040, contract="6EZ5")
    m = tm.load_minutes(tmp_path)
    assert m["adj"][0] == 40 and m["adj"][1440] == 0
    assert m["close"][0] + m["adj"][0] == m["close"][1440]
