"""Book-free reversal rule on broker minute bars (XAUUSD etc.), the exact rule of the multi-market study.

``pa_multi_market_study`` found the failed-breakout reversal with the 4-hour trend filter positive on
XAUUSD over 2021-Jun 2026 (sessions window, stop 1.5 x ATR, target 3 x stop, 240-minute hold). This
module evaluates that rule live on bars pulled from cTrader through the file bridge (``bars`` intent).

The bars are laid onto a midnight-aligned minute grid (gaps filled with the previous close, like the
study loader) so the 15-minute ATR blocks and the session windows line up exactly with the study.
``decide`` returns the decision for the last completed minute, or None.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from ai_trader.research import six_e_session_pa_study as ps

RULES = {
    # symbol -> rule parameters (from pa_multi_market_study, trend-filtered reversal)
    "XAUUSD": {"pattern": "reversal", "window": "sessions", "stop_k": 1.5, "rr": 3.0, "hold": 240, "min_days": 3},
}
WINDOW_MINUTES = {"sessions": [(7 * 60, 9 * 60), (13 * 60, 16 * 60)]}


def grid_from_bars(bars: list[list], now: datetime) -> dict:
    """[[open_ms, o, h, l, c, vol], ...] -> midnight-aligned arrays ending at the minute before ``now``."""
    if not bars:
        raise ValueError("no bars")
    first_day = datetime.fromtimestamp(bars[0][0] / 1000, timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(second=0, microsecond=0)
    n = int((end - first_day).total_seconds() // 60)
    o, h, l, c = (np.full(n, np.nan) for _ in range(4))
    traded = np.zeros(n, dtype=bool)
    for ms, bo, bh, bl, bc, _v in bars:
        i = int((ms / 1000 - first_day.timestamp()) // 60)
        if 0 <= i < n:
            o[i], h[i], l[i], c[i], traded[i] = bo, bh, bl, bc, True
    last = np.nan
    for i in range(n):
        if traded[i]:
            last = c[i]
        elif np.isfinite(last):
            h[i] = l[i] = c[i] = o[i] = last
    mod = (np.arange(n) + int((first_day - first_day).total_seconds() // 60)) % 1440
    return {"open": o, "high": h, "low": l, "close": c, "traded": traded, "mod": mod, "n": n,
            "first_day": first_day, "last_minute": end - timedelta(minutes=1)}


def in_window(minute_of_day: int, window: str) -> bool:
    return any(lo <= minute_of_day < hi for lo, hi in WINDOW_MINUTES[window])


def decide(symbol: str, bars: list[list], now: datetime) -> dict | None:
    """Decision for the minute that just completed, or None. Pure function of the bars."""
    rule = RULES[symbol]
    g = grid_from_bars(bars, now)
    c, h, l, mod = g["close"], g["high"], g["low"], g["mod"]
    i = g["n"] - 1
    if i < 1440 * rule["min_days"] or not g["traded"][i] or not np.isfinite(c[i]):
        return None
    if not in_window(int(mod[i]), rule["window"]) or int(mod[i]) >= ps.DAY_END:
        return None
    # ATR is defined per 15-minute block from the completed blocks before it; pad the partial last block
    # so the current minute gets its block's value exactly as in the study's full-day arrays
    pad = (-g["n"]) % 15
    hp, lp, cp = (np.concatenate([x, np.full(pad, np.nan)]) for x in (h, l, c))
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            a = ps.atr_minutes(hp, lp, cp)[: g["n"]]
    if not np.isfinite(a[i]) or a[i] <= 0:
        return None
    sig = ps.pattern_signals(c, h, l, a, rule["pattern"])
    trend4 = np.sign(c[i] - c[i - 240])
    if sig[i] == 0 or sig[i] != trend4:
        return None
    side = "long" if sig[i] > 0 else "short"
    stop = rule["stop_k"] * float(a[i])
    return {"symbol": symbol, "date": g["last_minute"].date().isoformat(),
            "minute_utc": g["last_minute"].strftime("%H:%M"), "side": side, "entry": float(c[i]),
            "stop_price_distance": round(stop, 5), "target_price_distance": round(stop * rule["rr"], 5),
            "atr": round(float(a[i]), 5), "hold": rule["hold"], "rule": "reversal_v1_bookfree"}


def intent_from_decision(d: dict, lots: float = 0.01) -> dict:
    return {"symbol": d["symbol"], "side": "BUY" if d["side"] == "long" else "SELL", "lots": lots,
            "stop_price_distance": d["stop_price_distance"], "target_price_distance": d["target_price_distance"],
            "label": f"{d['rule']} {d['date']} {d['minute_utc']} {d['side']}"}


def replay(symbol: str, bars: list[list], start: datetime, end: datetime, step_minutes: int = 1) -> list[dict]:
    """Walk ``decide`` minute by minute over a bar list (for checking the live rule against the study)."""
    out = []
    t = start.replace(second=0, microsecond=0)
    while t <= end:
        visible = [b for b in bars if b[0] / 1000 < t.timestamp()]
        if visible:
            d = decide(symbol, visible, t)
            if d:
                out.append(d)
        t += timedelta(minutes=step_minutes)
    return out
