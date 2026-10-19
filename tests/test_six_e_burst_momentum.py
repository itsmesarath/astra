"""Burst detector and simulator on a synthetic tick stream: one planted burst, follow-through, then a fade."""

import numpy as np

from ai_trader.research import six_e_burst_momentum as bm


def _stream():
    rng = np.random.default_rng(1)
    # 2 hours of quiet trading: one 1-lot trade per second, price random-walking slowly
    t = np.arange(0, 7200, 1.0)
    v = np.ones(t.size, dtype=np.int64)
    px = 22000 + np.cumsum(rng.integers(-1, 2, t.size))
    s = rng.choice([-1, 1], t.size).astype(np.int8)
    # planted burst at t=5000: 40 buyer-initiated trades of 10 lots within 5 s, price +6 ticks
    bt = 5000 + np.linspace(0, 5, 40)
    bp = px[5000] + np.linspace(0, 6, 40).astype(np.int64)
    # follow-through: +4 ticks over the next 30 s, then a fade back over 60 s with seller initiative
    ft = 5006 + np.arange(30); fp = bp[-1] + (np.arange(30) // 8)
    fa = 5036 + np.arange(60); fap = fp[-1] - (np.arange(60) // 6)
    T = np.concatenate([t[:5000], bt, ft, fa, t[5100:] + 0.5])
    P = np.concatenate([px[:5000], bp, fp, fap, px[5100:]])
    V = np.concatenate([v[:5000], np.full(40, 10), np.full(30, 2), np.full(60, 3), v[5100:]])
    S = np.concatenate([s[:5000], np.ones(40, np.int8), np.ones(30, np.int8), -np.ones(60, np.int8), s[5100:]])
    order = np.argsort(T, kind="stable")
    return T[order], P[order], V[order], S[order]


def test_burst_detected_and_traded_with_flip_exit():
    t, px, v, s = _stream()
    idx, dirs = bm.bursts(t, px, v, s, W=5, k=10, m=3, vmin=100, imb=0.6)
    assert idx.size > 0 and set(dirs.tolist()) == {1}
    assert 5000 <= t[idx[0]] <= 5006
    trades = bm.simulate(t, px, v, s, idx, dirs, trail=5, hard=10, T=600, flip=True, cooldown=60, cost=1.8)
    assert len(trades) == 1
    tr = trades[0]
    assert tr["d"] == 1 and tr["why"] in ("flip", "trail") and tr["hold_s"] < 120
    # entered during the burst, exited before the fade took everything back
    assert tr["exit"] > tr["entry"] - 2


def test_no_burst_in_quiet_stream():
    t, px, v, s = _stream()
    quiet = t < 4900
    idx, _ = bm.bursts(t[quiet], px[quiet], v[quiet], s[quiet], W=5, k=10, m=3, vmin=100, imb=0.6)
    assert idx.size == 0


def test_stats_shape():
    st = bm.stats([{"t": 1.7e9, "d": 1, "entry": 1, "exit": 4, "hold_s": 30, "net": 1.2, "why": "trail"}] * 3, days=2)
    assert st["trades"] == 3 and st["per_day"] == 1.5 and "months" in st
