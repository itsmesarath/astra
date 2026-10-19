"""cfd_signals: the live rule must fire on exactly the minutes the study's vectorised rule fires on."""

from datetime import datetime, timedelta, timezone

import numpy as np

from ai_trader.live import cfd_signals as cs
from ai_trader.research import six_e_session_pa_study as ps


def _bars(days=6, seed=3):
    """Random-walk minute bars with a few planted failed breakouts, as [[open_ms,o,h,l,c,v],...]."""
    rng = np.random.default_rng(seed)
    n = days * 1440
    c = 4000 + np.cumsum(rng.normal(0, 0.8, n))
    # plant V-shaped dips (new 4h low then sharp recovery) inside the London window on each day
    for d in range(1, days):
        i = d * 1440 + 7 * 60 + 40
        c[i - 10:i] -= np.linspace(0, 12, 10)
        c[i:i + 5] += np.linspace(12, 20, 5)
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) + rng.uniform(0.1, 0.6, n)
    l = np.minimum(o, c) - rng.uniform(0.1, 0.6, n)
    t0 = datetime(2026, 10, 12, tzinfo=timezone.utc)
    return [[int((t0 + timedelta(minutes=i)).timestamp() * 1000), float(o[i]), float(h[i]), float(l[i]), float(c[i]), 10]
            for i in range(n)], t0


def test_live_rule_matches_study_rule():
    bars, t0 = _bars()
    # study side: signal per minute on the full grid, trend- and window-filtered
    o, h, l, c = (np.array([b[k] for b in bars]) for k in (1, 2, 3, 4))
    a = ps.atr_minutes(h, l, c)
    sig = ps.pattern_signals(c, h, l, a, "reversal")
    trend4 = np.sign(c - np.concatenate([np.full(240, np.nan), c[:-240]]))
    sig[sig != trend4] = 0
    mod = ps.minute_of_day(c.size)
    sig[~ps.in_windows(mod, "sessions")] = 0
    sig[:1440 * 3] = 0  # live rule needs min_days of history
    expected = {int(i) for i in np.flatnonzero(sig)}
    assert expected, "the synthetic series should contain reversal signals"
    # live side: decide() at the start of every minute of the last three days
    got = set()
    for i in range(1440 * 3, len(bars)):
        now = t0 + timedelta(minutes=i + 1)        # minute i has just completed
        d = cs.decide("XAUUSD", bars[: i + 1], now)
        if d:
            got.add(i)
            assert d["side"] == ("long" if sig[i] > 0 else "short")
            assert abs(d["stop_price_distance"] - 1.5 * a[i]) < 1e-4
            assert abs(d["target_price_distance"] - 3 * d["stop_price_distance"]) < 1e-4
    assert got == expected


def test_decide_outside_window_and_with_gap():
    bars, t0 = _bars()
    now = t0 + timedelta(days=4, hours=11)   # 11:00 UTC: between sessions
    assert cs.decide("XAUUSD", [b for b in bars if b[0] < now.timestamp() * 1000], now) is None
    # a weekend-style gap is filled with the previous close and does not raise
    gap = [b for b in bars if not (t0 + timedelta(days=2) <= datetime.fromtimestamp(b[0] / 1000, timezone.utc) < t0 + timedelta(days=3))]
    g = cs.grid_from_bars(gap, t0 + timedelta(days=5))
    assert g["n"] == 5 * 1440 and np.isfinite(g["close"][2 * 1440 + 100])


def test_intent_shape():
    d = {"symbol": "XAUUSD", "date": "2026-10-19", "minute_utc": "13:35", "side": "short", "entry": 4000.0,
         "stop_price_distance": 6.0, "target_price_distance": 18.0, "atr": 4.0, "hold": 240, "rule": "reversal_v1_bookfree"}
    it = cs.intent_from_decision(d)
    assert it["side"] == "SELL" and it["lots"] == 0.01 and it["symbol"] == "XAUUSD" and "13:35" in it["label"]
