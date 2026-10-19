"""Sequential replay of the level-fade rule chosen by level_revisit_study: one position at a time.

Rule ("level_fade_v1"): price revisits a sharp-reversal level (swing +-30 min, moved >= 1 ATR away
within 60 min, first revisit within 3 days, tolerance 0.2 ATR); the 30-minute approach is slow
(<= 0.3 ATR) and the 4-hour trend points into the level; not already through the level. Trade: fade
(sell at resistance / buy at support) at the revisit close, stop 1 x ATR, target rr x stop, 240-minute
hold, flat at DAY_END. Only one open position per symbol; a new event while in a position is skipped.
Costs from pa_multi_market_study.COSTS. Results per year in cost units and in R (net / stop).

Usage: python -m ai_trader.research.level_fade_replay GBPUSD [--rr 2] [--window sessions|all]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ai_trader.research import level_revisit_study as lr
from ai_trader.research import pa_multi_market_study as mm
from ai_trader.research import six_e_session_pa_study as ps

SESSIONS = [(7 * 60, 9 * 60), (13 * 60, 16 * 60)]


def select(events, window: str):
    out = []
    for e in events:
        if e["approach"] > 0.3 or e["trend4"] <= 0:
            continue
        if window == "sessions" and not any(lo <= e["mod"] < hi for lo, hi in SESSIONS):
            continue
        out.append(e)
    return out


def replay(events, c, h, l, dayk, rr, cost, hold=240):
    n = c.size
    trades = []
    busy = -1
    for e in sorted(events, key=lambda e: e["i"]):
        j, side = e["i"], e["side"]
        if j <= busy:
            continue
        d = -side
        px, stop_d = c[j], e["atr"]
        stop, target = px - d * stop_d, px + d * rr * stop_d
        end = min(j + hold, int(dayk[j]) * 1440 + ps.DAY_END, n - 1)
        if end <= j:
            continue
        hs, ls = h[j + 1:end + 1], l[j + 1:end + 1]
        s_hit, t_hit = (np.flatnonzero(ls <= stop), np.flatnonzero(hs >= target)) if d > 0 else (np.flatnonzero(hs >= stop), np.flatnonzero(ls <= target))
        s_i = j + 1 + s_hit[0] if s_hit.size else None
        t_i = j + 1 + t_hit[0] if t_hit.size else None
        if s_i is not None and (t_i is None or s_i <= t_i):
            ex, out, why = s_i, -stop_d, "stop"
        elif t_i is not None:
            ex, out, why = t_i, rr * stop_d, "target"
        else:
            ex, out, why = end, d * (c[end] - px), "time"
        trades.append({"i": int(j), "exit": int(ex), "d": d, "net": float(out - cost), "R": float((out - cost) / stop_d),
                       "why": why, "year": e["year"], "mod": e["mod"]})
        busy = ex
    return trades


def table(trades, cost, dates):
    years = sorted({t["year"] for t in trades})
    rows = []
    for y in years + ["all"]:
        ts = [t for t in trades if y == "all" or t["year"] == y]
        if not ts:
            continue
        net = np.array([t["net"] for t in ts]); R = np.array([t["R"] for t in ts])
        days = sum(1 for d in dates if (y == "all" or d.year == y)) * 5 / 7
        wins, losses = net[net > 0].sum(), -net[net < 0].sum()
        rows.append({"year": y, "n": len(ts), "per_day": round(len(ts) / max(days, 1), 2), "win": round(float((net > 0).mean()), 3),
                     "net_in_costs": round(float(net.mean() / cost), 2), "mean_R": round(float(R.mean()), 3), "sum_R": round(float(R.sum()), 1),
                     "pf": round(float(wins / losses), 2) if losses else None,
                     "exits": {w: int(sum(t["why"] == w for t in ts)) for w in ("stop", "target", "time")}})
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("symbol")
    p.add_argument("--data", type=Path, default=Path("data/raw/dukascopy"))
    p.add_argument("--rr", type=float, default=2.0)
    p.add_argument("--window", choices=["all", "sessions"], default="all")
    p.add_argument("--swing", type=int, default=30)
    p.add_argument("--sharp", type=float, default=1.0)
    p.add_argument("--out", type=Path, default=None)
    a = p.parse_args(argv)
    m = mm.load_symbol(a.data / a.symbol)
    c, h, l = m["close"], m["high"], m["low"]
    at = ps.atr_minutes(h, l, c)
    mod, dayk = ps.minute_of_day(c.size), m["day"]
    years = np.array([d.year for d in m["dates"]])
    levels = lr.find_levels(h, l, c, at, a.swing, a.sharp)
    ev = lr.revisits(levels, h, l, c, at, mod, 0.2, 3 * 1440, 120)
    for e in ev:
        e["year"] = int(years[dayk[e["i"]]])
    cost = mm.COSTS[a.symbol][0]
    sel = select(ev, a.window)
    trades = replay(sel, c, h, l, dayk, a.rr, cost)
    rows = table(trades, cost, m["dates"])
    print(f"{a.symbol} level_fade_v1 rr {a.rr} window {a.window}: {len(ev)} revisits, {len(sel)} selected, {len(trades)} sequential trades, cost {cost}")
    print(f"{'year':5} {'n':>5} {'/day':>5} {'win':>5} {'net/cost':>8} {'mean R':>7} {'sum R':>7} {'pf':>5}  exits")
    for r in rows:
        print(f"{r['year']!s:5} {r['n']:5} {r['per_day']:5} {r['win']:5} {r['net_in_costs']:8} {r['mean_R']:7} {r['sum_R']:7} {r['pf']!s:5}  {r['exits']}")
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps({"symbol": a.symbol, "rr": a.rr, "window": a.window, "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
