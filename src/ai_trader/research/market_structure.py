"""Market-structure features for the desk's chart zones and the markets board, from our own bars.

Built from public definitions, not from anyone's product:
- Swing highs/lows: a bar whose high (low) is the highest (lowest) of ``n`` bars either side.
- Break of structure (BOS): a close beyond the most recent swing high (bullish) or swing low (bearish).
- Order block: the last bearish candle before a bullish displacement that breaks structure (and the
  mirror for bearish); the zone is that candle's low..high. A displacement is a move of at least
  ``disp_atr`` x ATR within ``disp_bars`` bars. The zone stays valid until price trades back into
  it (mitigated); zones are reported with their state and age.
- Liquidity levels: clusters of >= 2 swing highs (or lows) within ``eq_tol`` x ATR of each other
  (equal highs/lows), plus the previous session's high and low. A sweep is a wick beyond the level
  followed by a close back on the original side within ``sweep_bars`` bars.
- Support/resistance: swing levels touched >= ``touches`` times within tolerance.
- Strength score for the board: 4-hour move in ATR units, number of same-direction BOS in the window,
  and whether price sits inside an unmitigated order block.

Works on any OHLC array in price points (ticks or CFD points); 5-minute bars are the intended input.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np


@dataclass
class Zone:
    kind: str          # "order_block" | "liquidity" | "sr"
    side: str          # "bullish" | "bearish" | "resistance" | "support"
    low: float
    high: float
    bar: int           # bar index the zone was formed at
    state: str = "fresh"   # "fresh" | "mitigated" | "swept" | "held"
    touches: int = 0
    note: str = ""


def swings(h: np.ndarray, l: np.ndarray, n: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Boolean arrays: swing high / swing low at each bar (n bars either side)."""
    m = h.size
    sh = np.zeros(m, dtype=bool)
    sl = np.zeros(m, dtype=bool)
    for i in range(n, m - n):
        win_h = h[i - n:i + n + 1]
        win_l = l[i - n:i + n + 1]
        # highest of the window; on ties the first bar wins (strictly above everything to its right)
        if np.isfinite(win_h).all() and h[i] == win_h.max() and (h[i + 1:i + n + 1] < h[i]).all():
            sh[i] = True
        if np.isfinite(win_l).all() and l[i] == win_l.min() and (l[i + 1:i + n + 1] > l[i]).all():
            sl[i] = True
    return sh, sl


def atr(h, l, c, n: int = 14) -> np.ndarray:
    prev = np.concatenate([[np.nan], c[:-1]])
    tr = np.nanmax(np.column_stack([h - l, np.abs(h - prev), np.abs(l - prev)]), axis=1)
    out = np.full(h.size, np.nan)
    for i in range(n, h.size):
        out[i] = np.nanmean(tr[i - n + 1:i + 1])
    return out


def breaks_of_structure(c, sh, sl, h, l) -> list[tuple[int, str, float]]:
    """(bar, 'bullish'|'bearish', level) each time a close breaks the latest swing high/low."""
    out = []
    last_high = last_low = None
    broken_high = broken_low = False
    for i in range(c.size):
        if last_high is not None and not broken_high and c[i] > last_high:
            out.append((i, "bullish", last_high))
            broken_high = True
        if last_low is not None and not broken_low and c[i] < last_low:
            out.append((i, "bearish", last_low))
            broken_low = True
        if sh[i]:
            last_high, broken_high = h[i], False
        if sl[i]:
            last_low, broken_low = l[i], False
    return out


def order_blocks(o, h, l, c, a, bos, disp_atr: float = 1.5, disp_bars: int = 6) -> list[Zone]:
    zones = []
    for bar, side, _level in bos:
        start = max(0, bar - disp_bars)
        if side == "bullish":
            move = c[bar] - l[start:bar + 1].min()
            if not np.isfinite(a[bar]) or move < disp_atr * a[bar]:
                continue
            cands = [k for k in range(start, bar + 1) if c[k] < o[k]]  # last bearish candle before the push
            if not cands:
                continue
            k = cands[-1]
            zones.append(Zone("order_block", "bullish", float(l[k]), float(h[k]), k, note=f"BOS at bar {bar}"))
        else:
            move = h[start:bar + 1].max() - c[bar]
            if not np.isfinite(a[bar]) or move < disp_atr * a[bar]:
                continue
            cands = [k for k in range(start, bar + 1) if c[k] > o[k]]
            if not cands:
                continue
            k = cands[-1]
            zones.append(Zone("order_block", "bearish", float(l[k]), float(h[k]), k, note=f"BOS at bar {bar}"))
    # mitigation: price trades back into the zone after it formed (after the BOS bar)
    for z in zones:
        after = int(z.note.split()[-1]) + 1
        inside = np.flatnonzero((l[after:] <= z.high) & (h[after:] >= z.low))
        if inside.size:
            z.state = "mitigated"
            z.touches = int(inside.size)
    return zones


def liquidity_levels(h, l, sh, sl, a, c, eq_tol: float = 0.25, sweep_bars: int = 3) -> list[Zone]:
    zones = []
    for side, mask, px in (("highs", sh, h), ("lows", sl, l)):
        idx = np.flatnonzero(mask)
        used = set()
        for i in idx:
            if i in used or not np.isfinite(a[i]):
                continue
            tol = eq_tol * a[i]
            group = [j for j in idx if j >= i and abs(px[j] - px[i]) <= tol]
            if len(group) >= 2:
                used.update(group)
                level = float(np.mean(px[group]))
                z = Zone("liquidity", "resistance" if side == "highs" else "support", level - tol / 2, level + tol / 2,
                         int(group[-1]), touches=len(group), note=f"equal {side} x{len(group)}")
                # sweep: wick through the level then close back within sweep_bars
                after = int(group[-1]) + 1
                for k in range(after, min(c.size, after + 400)):
                    if side == "highs" and h[k] > level + tol:
                        back = c[k:k + sweep_bars]
                        z.state = "swept" if back.size and (back < level).any() else "held"
                        z.note += f"; swept at bar {k}" if z.state == "swept" else f"; broke at bar {k}"
                        break
                    if side == "lows" and l[k] < level - tol:
                        back = c[k:k + sweep_bars]
                        z.state = "swept" if back.size and (back > level).any() else "held"
                        z.note += f"; swept at bar {k}" if z.state == "swept" else f"; broke at bar {k}"
                        break
                zones.append(z)
    return zones


def support_resistance(h, l, sh, sl, a, touches: int = 3, tol_atr: float = 0.3) -> list[Zone]:
    zones = []
    for side, mask, px, label in (("highs", sh, h, "resistance"), ("lows", sl, l, "support")):
        idx = np.flatnonzero(mask)
        used = set()
        for i in idx:
            if i in used or not np.isfinite(a[i]):
                continue
            tol = tol_atr * a[i]
            group = [j for j in idx if abs(px[j] - px[i]) <= tol]
            if len(group) >= touches:
                used.update(group)
                level = float(np.mean(px[group]))
                zones.append(Zone("sr", label, level - tol / 2, level + tol / 2, int(max(group)), touches=len(group),
                                  note=f"{len(group)} touches"))
    return zones


def strength(c, a, bos, window: int = 48) -> dict:
    """Board score over the last `window` bars (48 x 5 min = 4 hours)."""
    i = c.size - 1
    j = max(0, i - window)
    move = (c[i] - c[j]) / a[i] if np.isfinite(a[i]) and a[i] > 0 else float("nan")
    recent = [s for b, s, _ in bos if b > j]
    bull = sum(1 for s in recent if s == "bullish")
    bear = sum(1 for s in recent if s == "bearish")
    label = "choppy"
    if np.isfinite(move) and abs(move) >= 1.5 and abs(bull - bear) >= 1:
        label = "bullish" if move > 0 else "bearish"
    return {"move_atr": round(float(move), 2) if np.isfinite(move) else None, "bos_bullish": bull, "bos_bearish": bear,
            "label": label}


def analyse(o, h, l, c, swing_n: int = 3) -> dict:
    o, h, l, c = (np.asarray(x, dtype=float) for x in (o, h, l, c))
    sh, sl = swings(h, l, swing_n)
    a = atr(h, l, c)
    bos = breaks_of_structure(c, sh, sl, h, l)
    obs = order_blocks(o, h, l, c, a, bos)
    liq = liquidity_levels(h, l, sh, sl, a, c)
    sr = support_resistance(h, l, sh, sl, a)
    last = float(c[-1])
    def dist(z):
        return 0.0 if z.low <= last <= z.high else min(abs(last - z.low), abs(last - z.high))
    nearest = sorted(obs + liq + sr, key=dist)[:6]
    return {"last": last, "atr": float(a[-1]) if np.isfinite(a[-1]) else None,
            "strength": strength(c, a, bos), "bos": [{"bar": b, "side": s, "level": float(v)} for b, s, v in bos[-5:]],
            "order_blocks": [asdict(z) for z in obs], "liquidity": [asdict(z) for z in liq], "sr": [asdict(z) for z in sr],
            "nearest": [asdict(z) for z in nearest]}


def five_minute_bars(minute_rows: list[list[float]]) -> tuple[np.ndarray, ...]:
    """Aggregate [minute_ns, o, h, l, c, ...] rows into 5-minute OHLC arrays (gaps allowed)."""
    buckets: dict[int, list] = {}
    for row in minute_rows:
        key = int(row[0] // (5 * 60_000_000_000))
        b = buckets.get(key)
        if b is None:
            buckets[key] = [row[1], row[2], row[3], row[4]]
        else:
            b[1] = max(b[1], row[2]); b[2] = min(b[2], row[3]); b[3] = row[4]
    keys = sorted(buckets)
    arr = np.array([buckets[k] for k in keys], dtype=float)
    return arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3]
