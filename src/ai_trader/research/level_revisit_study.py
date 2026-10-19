"""Level-revisit study: mark levels where the market reversed sharply; when price comes back, does it
break through or reverse again, and can features at the approach tell which?

Level: a swing high/low of 1-minute bars (extreme over +-``swing`` minutes) from which price moved at
least ``sharp`` x ATR away within the next 60 minutes (ATR = 16 x 15-minute bars, as in the other
studies). Revisit: the first later minute (after 60 min, within ``expiry`` minutes) whose high/low
comes within ``tol`` x ATR of the level. Outcome within ``horizon`` minutes of the revisit, first of:
``break`` (close beyond the level by 0.5 ATR), ``hold`` (close back away from the level by 0.7 ATR
from the level, i.e. ~0.5 ATR from the touch), or ``neither``.

Features at the revisit (all known at the time): approach speed (30-minute move / ATR), 4-hour trend
sign relative to the level side, age of the level (minutes), number of earlier touches of the level,
minute of day, time-of-day window. Trades: at the revisit close, ``fade`` (sell at resistance / buy at
support) or ``break`` (the opposite), stop 1 x ATR, target ``rr`` x stop, 240-minute hold, cost per
symbol from pa_multi_market_study.COSTS. Development years fit the feature buckets; 2024-Jun 2026 is
the check. Nothing here touches lockbox data (the loader refuses it).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from ai_trader.research import pa_multi_market_study as mm
from ai_trader.research import six_e_session_pa_study as ps

DEV_LAST_YEAR = 2023


def swing_points(h, l, n):
    """Boolean arrays: bar is the max high / min low over the window [i-n, i+n]."""
    k = 2 * n + 1
    sh = np.zeros(h.size, dtype=bool)
    sl = np.zeros(l.size, dtype=bool)
    if h.size < k:
        return sh, sl
    wh = sliding_window_view(h, k).max(axis=1)
    wl = sliding_window_view(l, k).min(axis=1)
    sh[n:-n] = h[n:-n] >= wh
    sl[n:-n] = l[n:-n] <= wl
    return sh, sl


def find_levels(h, l, c, a, swing, sharp):
    """List of (i, side, price): side +1 = resistance (swing high), -1 = support (swing low)."""
    sh, sl = swing_points(h, l, swing)
    out = []
    n = h.size
    for i in np.flatnonzero(sh | sl):
        if not np.isfinite(a[i]) or a[i] <= 0 or i + 61 >= n:
            continue
        if sh[i] and np.nanmin(l[i + 1:i + 61]) <= h[i] - sharp * a[i]:
            out.append((int(i), 1, float(h[i])))
        if sl[i] and np.nanmax(h[i + 1:i + 61]) >= l[i] + sharp * a[i]:
            out.append((int(i), -1, float(l[i])))
    return out


def revisits(levels, h, l, c, a, mod, tol, expiry, horizon):
    """One event per (level, touch) with features and outcome."""
    n = c.size
    events = []
    for i, side, L in levels:
        start = i + 61
        end = min(n - horizon - 1, i + expiry)
        touches = 0
        j = start
        while j < end:
            tol_px = tol * a[j] if np.isfinite(a[j]) else np.nan
            if not np.isfinite(tol_px):
                j += 1
                continue
            seg_h, seg_l = h[j:end], l[j:end]
            if side > 0:
                hit = np.flatnonzero(seg_h >= L - tol_px)
            else:
                hit = np.flatnonzero(seg_l <= L + tol_px)
            if hit.size == 0:
                break
            j = j + int(hit[0])
            if not np.isfinite(a[j]) or a[j] <= 0 or not np.isfinite(c[j]) or j < 240:
                j += 1
                continue
            # already through the level on arrival: not a revisit, level is dead
            if side * (c[j] - L) > 0.5 * a[j]:
                break
            fc = c[j + 1:j + 1 + horizon]
            brk = np.flatnonzero(side * (fc - L) >= 0.5 * a[j])
            hold = np.flatnonzero(side * (fc - L) <= -0.7 * a[j])
            b = brk[0] if brk.size else None
            hd = hold[0] if hold.size else None
            if b is not None and (hd is None or b < hd):
                outcome = "break"
            elif hd is not None:
                outcome = "hold"
            else:
                outcome = "neither"
            touches += 1
            events.append({
                "i": int(j), "level_i": int(i), "side": side, "level": L, "touch_n": touches,
                "approach": float(side * (c[j] - c[j - 30]) / a[j]),          # >0: moving into the level
                "trend4": float(side * np.sign(c[j] - c[j - 240])),            # +1: 4h trend points through the level
                "age_min": int(j - i), "mod": int(mod[j]), "atr": float(a[j]),
                "dist": float(side * (L - c[j]) / a[j]),                       # distance left to the level (ATR)
                "outcome": outcome, "c": float(c[j]),
            })
            if outcome == "break":
                break
            j += 30  # next touch of the same level at least 30 minutes later
    return events


def trade(events, c, h, l, a, mod, dayk, rr, cost, hold=240):
    """Net result of fading and of trading the break at every event (ticks/points)."""
    n = c.size
    for e in events:
        j, side = e["i"], e["side"]
        stop_d = 1.0 * e["atr"]
        res = {}
        for name, d in (("fade", -side), ("break", side)):
            px = c[j]
            stop, target = px - d * stop_d, px + d * rr * stop_d
            end = min(j + hold, (int(dayk[j]) * 1440) + ps.DAY_END, n - 1)
            hs, ls = h[j + 1:end + 1], l[j + 1:end + 1]
            if d > 0:
                s_hit, t_hit = np.flatnonzero(ls <= stop), np.flatnonzero(hs >= target)
            else:
                s_hit, t_hit = np.flatnonzero(hs >= stop), np.flatnonzero(ls <= target)
            s_i = s_hit[0] if s_hit.size else None
            t_i = t_hit[0] if t_hit.size else None
            if s_i is not None and (t_i is None or s_i <= t_i):
                out = -stop_d
            elif t_i is not None:
                out = rr * stop_d
            else:
                out = d * (c[end] - px)
            res[name] = float(out - cost)
        e["net_fade"], e["net_break"] = res["fade"], res["break"]
    return events


def bucket(e):
    """Coarse feature buckets for the conditional analysis."""
    return {
        "approach": "fast" if e["approach"] >= 1.0 else ("slow" if e["approach"] <= 0.3 else "mid"),
        "trend4": "with" if e["trend4"] > 0 else "against",
        "touch": "first" if e["touch_n"] == 1 else "repeat",
        "age": "<4h" if e["age_min"] < 240 else ("<1d" if e["age_min"] < 1440 else ">1d"),
        "window": "london" if 7 * 60 <= e["mod"] < 9 * 60 else ("ny" if 13 * 60 <= e["mod"] < 16 * 60 else "other"),
    }


def summarise(events, cost, years):
    ev = [e for e in events if e["year"] in years]
    if not ev:
        return {}
    out = {"n": len(ev), "break": round(sum(e["outcome"] == "break" for e in ev) / len(ev), 3),
           "hold": round(sum(e["outcome"] == "hold" for e in ev) / len(ev), 3)}
    for k in ("net_fade", "net_break"):
        v = np.array([e[k] for e in ev])
        out[k] = round(float(v.mean() / cost), 2)   # in units of cost
    return out


def run_symbol(name, m, cfg):
    c, h, l = m["close"], m["high"], m["low"]
    a = ps.atr_minutes(h, l, c)
    mod, dayk = ps.minute_of_day(c.size), m["day"]
    years = np.array([d.year for d in m["dates"]])
    levels = find_levels(h, l, c, a, cfg["swing"], cfg["sharp"])
    ev = revisits(levels, h, l, c, a, mod, cfg["tol"], cfg["expiry"], cfg["horizon"])
    cost = mm.COSTS[name][0]
    ev = trade(ev, c, h, l, a, mod, dayk, cfg["rr"], cost)
    for e in ev:
        e["year"] = int(years[dayk[e["i"]]])
        e.update({"b_" + k: v for k, v in bucket(e).items()})
    dev = {y for y in set(years) if y <= DEV_LAST_YEAR}
    test = {y for y in set(years) if y > DEV_LAST_YEAR}
    rep = {"symbol": name, "cost": cost, "levels": len(levels), "events": len(ev), "traded_days": m["traded_days"],
           "events_per_day": round(len(ev) / max(m["traded_days"], 1), 2),
           "all": summarise(ev, cost, dev | test), "dev": summarise(ev, cost, dev), "test": summarise(ev, cost, test),
           "by_bucket": {}}
    for k in ("b_approach", "b_trend4", "b_touch", "b_age", "b_window"):
        rep["by_bucket"][k] = {}
        for v in sorted({e[k] for e in ev}):
            sub = [e for e in ev if e[k] == v]
            rep["by_bucket"][k][v] = {"dev": summarise(sub, cost, dev), "test": summarise(sub, cost, test)}
    # a simple two-feature rule chosen on dev years only: pick direction per (approach, trend) cell
    cells = defaultdict(list)
    for e in ev:
        cells[(e["b_approach"], e["b_trend4"])].append(e)
    policy, dev_pnl, test_pnl, test_n = {}, [], [], 0
    for key, sub in cells.items():
        d_ev = [e for e in sub if e["year"] in dev]
        t_ev = [e for e in sub if e["year"] in test]
        if len(d_ev) < 30:
            continue
        mf, mb = np.mean([e["net_fade"] for e in d_ev]), np.mean([e["net_break"] for e in d_ev])
        choice = "fade" if mf > mb else "break"
        if max(mf, mb) <= 0:
            choice = "skip"
        policy["|".join(key)] = {"choice": choice, "dev_fade": round(float(mf / cost), 2), "dev_break": round(float(mb / cost), 2), "n_dev": len(d_ev), "n_test": len(t_ev)}
        if choice != "skip":
            dev_pnl += [e["net_" + choice] for e in d_ev]
            test_pnl += [e["net_" + choice] for e in t_ev]
            test_n += len(t_ev)
    rep["policy"] = policy
    rep["policy_dev"] = {"n": len(dev_pnl), "mean_in_costs": round(float(np.mean(dev_pnl) / cost), 2) if dev_pnl else None}
    if test_pnl:
        tp = np.array(test_pnl)
        boot = np.random.default_rng(0).choice(tp, (1000, tp.size)).mean(axis=1)
        rep["policy_test"] = {"n": int(tp.size), "mean_in_costs": round(float(tp.mean() / cost), 2),
                              "ci95_in_costs": [round(float(np.percentile(boot, 2.5) / cost), 2), round(float(np.percentile(boot, 97.5) / cost), 2)],
                              "win": round(float((tp > 0).mean()), 3),
                              "per_day": round(tp.size / max(sum(1 for d in m["dates"] if d.year > DEV_LAST_YEAR) * 5 / 7, 1), 2)}
    else:
        rep["policy_test"] = {"n": 0}
    return rep, ev


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("symbol")
    p.add_argument("--data", type=Path, default=Path("data/raw/dukascopy"))
    p.add_argument("--swing", type=int, default=30)
    p.add_argument("--sharp", type=float, default=1.0)
    p.add_argument("--tol", type=float, default=0.2)
    p.add_argument("--expiry", type=int, default=3 * 1440)
    p.add_argument("--horizon", type=int, default=120)
    p.add_argument("--rr", type=float, default=2.0)
    p.add_argument("--out", type=Path, default=None)
    a = p.parse_args(argv)
    cfg = dict(swing=a.swing, sharp=a.sharp, tol=a.tol, expiry=a.expiry, horizon=a.horizon, rr=a.rr)
    m = mm.load_symbol(a.data / a.symbol)
    rep, ev = run_symbol(a.symbol, m, cfg)
    rep["config"] = cfg
    out = a.out or Path(f"data/processed/level_revisit_{a.symbol}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: rep[k] for k in ("symbol", "levels", "events", "events_per_day", "all", "dev", "test", "policy_dev", "policy_test")}, indent=1))
    print("policy:", json.dumps(rep["policy"], indent=1))


if __name__ == "__main__":
    main()
