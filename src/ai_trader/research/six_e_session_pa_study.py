"""Intraday price-action study for 6E: patterns x higher-timeframe trend x session windows x
Level-2 execution x reward-to-risk, on the 15-month development set (lockbox never read).

Owner direction (16 Oct 2026): intraday only; find breakouts, reversals, trends and patterns
in price; use Level 2 to make entries better and losses smaller; and get a better P/L ratio
(average win vs average loss). This study combines the only two things that helped earlier
(trading with the 4-hour trend; passive Level-2 entries) with longer intraday holds and
asymmetric brackets, and measures each dimension separately.

Patterns (all on 1-minute bars, back-adjusted closes, evaluated at minute close):
- ``breakout``: close above the highest high of the previous N minutes (long) / below the
  lowest low (short), N = 120.
- ``pullback``: with a 4-hour move of at least 1 ATR in one direction, price retraced at
  least 0.5 ATR from the 4-hour extreme, and now closes back above the previous 15-minute
  high (long) / below the 15-minute low (short) while still inside the 4-hour range.
- ``reversal``: a failed breakout - price made a new 240-minute low within the last
  15 minutes and now closes back above the previous 15-minute high (long); mirrored short.
- ``random``: benchmark - random minutes with the same exits, to separate pattern value
  from exit value.

Filters: ``trend`` (direction must match the sign of the 4-hour change), ``window``
(London open 07-09 UTC and the London/New York overlap 13-16 UTC, else 06-17 UTC),
``depth`` (resting size within 5 ticks on both sides at least the trailing 60-minute
median - do not enter a thin book).

Execution: ``market`` entry at the close, 2.6 ticks round-trip cost; ``passive`` limit at
the best bid/ask with real queue position (see six_e_book_strategy.passive_fill), 1.6
ticks cost, 15-minute wait. Exits: stop = stop_k x ATR (ATR of 15-minute bars over 4
hours), target = rr x stop, time exit after ``hold`` minutes, flat by 20:59 UTC. Stop
checked first when both are touched in one minute. Optional ``book_exit``: while losing,
three consecutive minutes with level-1 imbalance of at least 0.6 against the position
closes it at the minute close.

Reported per configuration: trades, mean net ticks, win rate, breakeven win rate for the
bracket, P/L ratio (average win / average loss), profit factor, 2025 and 2026 means,
bootstrap 95% CI of the mean, positive months, max drawdown in ticks.
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np

from ai_trader.research import six_e_book_strategy as bs
from ai_trader.research import six_e_trend_model as tm

MARKET_COST, PASSIVE_COST = 2.6, 1.6
DAY_END = 20 * 60 + 59  # flat by 20:59 UTC
WINDOWS = {"sessions": [(7 * 60, 9 * 60), (13 * 60, 16 * 60)], "day": [(6 * 60, 17 * 60)]}


def rolling_max(a: np.ndarray, n: int) -> np.ndarray:
    """Max of the previous n values (excluding the current one)."""
    from numpy.lib.stride_tricks import sliding_window_view
    out = np.full(a.size, np.nan)
    if a.size > n:
        out[n:] = sliding_window_view(a, n)[:-1].max(axis=1)
    return out


def rolling_min(a: np.ndarray, n: int) -> np.ndarray:
    return -rolling_max(-a, n)


def atr_minutes(h: np.ndarray, l: np.ndarray, c: np.ndarray, bars: int = 16, width: int = 15) -> np.ndarray:
    """ATR of `width`-minute bars over `bars` bars, written to every minute (uses completed bars only)."""
    n = h.size // width * width
    hh = h[:n].reshape(-1, width).max(1)
    ll = l[:n].reshape(-1, width).min(1)
    cc = c[:n].reshape(-1, width)[:, -1]
    prev = np.concatenate([[np.nan], cc[:-1]])
    tr = np.nanmax(np.column_stack([hh - ll, np.abs(hh - prev), np.abs(ll - prev)]), axis=1)
    a = np.full(tr.size, np.nan)
    for k in range(bars, tr.size):
        a[k] = np.nanmean(tr[k - bars:k])  # completed bars before block k
    out = np.full(h.size, np.nan)
    out[:n] = np.repeat(a, width)
    return out


def minute_of_day(n: int) -> np.ndarray:
    return np.arange(n) % 1440


def in_windows(mod: np.ndarray, name: str) -> np.ndarray:
    ok = np.zeros(mod.size, dtype=bool)
    for lo, hi in WINDOWS[name]:
        ok |= (mod >= lo) & (mod < hi)
    return ok


def pattern_signals(c, h, l, a, kind: str, rng: np.random.Generator | None = None,
                    lookback: int = 240, bounce: int = 15) -> np.ndarray:
    """+1/-1/0 per minute for the raw pattern (no filters)."""
    sig = np.zeros(c.size, dtype=np.int8)
    hi15, lo15 = rolling_max(h, bounce), rolling_min(l, bounce)
    if kind == "breakout":
        sig[c > rolling_max(h, 120)] = 1
        sig[c < rolling_min(l, 120)] = -1
    elif kind == "pullback":
        mv = c - np.concatenate([np.full(240, np.nan), c[:-240]])
        hi240, lo240 = rolling_max(h, 240), rolling_min(l, 240)
        lo30, hi30 = rolling_min(l, 30), rolling_max(h, 30)
        up = (mv >= a) & (hi240 - lo30 >= 0.5 * a) & (c > hi15) & (c < hi240)
        dn = (mv <= -a) & (hi30 - lo240 >= 0.5 * a) & (c < lo15) & (c > lo240)
        sig[up] = 1
        sig[dn] = -1
    elif kind == "reversal":
        lo240_prev, hi240_prev = rolling_min(l, lookback), rolling_max(h, lookback)
        new_low = lo15 <= np.concatenate([np.full(bounce, np.nan), lo240_prev[:-bounce]])
        new_high = hi15 >= np.concatenate([np.full(bounce, np.nan), hi240_prev[:-bounce]])
        sig[new_low & (c > hi15)] = 1
        sig[new_high & (c < lo15)] = -1
    elif kind == "random":
        pick = rng.random(c.size) < 0.01
        sig[pick] = rng.choice([-1, 1], size=int(pick.sum()))
    else:
        raise ValueError(kind)
    sig[~np.isfinite(a)] = 0
    return sig


def simulate(c, h, l, a, mod, dayk, books, sig, entry: str, stop_k: float, rr: float, hold: int,
             book_exit: bool, depth_ok: np.ndarray | None) -> list[dict]:
    n = c.size
    trades = []
    busy_until = -1
    cost = MARKET_COST if entry == "market" else PASSIVE_COST
    for i in np.flatnonzero(sig):
        if i <= busy_until or mod[i] >= DAY_END:
            continue
        d = int(sig[i])
        k, m = int(dayk[i]), int(mod[i])
        b = books[k]
        if depth_ok is not None and not depth_ok[i]:
            continue
        if entry == "market":
            j, px = i, c[i]
        else:
            if b is None:
                continue
            f = bs.passive_fill(b, m, d)
            if f is None:
                continue
            j = k * 1440 + f[0]
            px = float(f[1]) + adj_at(c, j)  # book prices are raw contract ticks; add the back-adjustment
        stop_d = stop_k * a[i]
        stop, target = px - d * stop_d, px + d * rr * stop_d
        end = min(j + hold, k * 1440 + DAY_END)
        if end <= j:
            continue
        hs, ls = h[j + 1:end + 1], l[j + 1:end + 1]
        if d > 0:
            s_hit = np.flatnonzero(ls <= stop)
            t_hit = np.flatnonzero(hs >= target)
        else:
            s_hit = np.flatnonzero(hs >= stop)
            t_hit = np.flatnonzero(ls <= target)
        s_i = j + 1 + s_hit[0] if s_hit.size else None
        t_i = j + 1 + t_hit[0] if t_hit.size else None
        if s_i is not None and (t_i is None or s_i <= t_i):
            ex, px_out, why = s_i, stop, "stop"
        elif t_i is not None:
            ex, px_out, why = t_i, target, "target"
        else:
            ex, px_out, why = end, c[end], "time"
        if book_exit and b is not None:
            imb = b["imb"]
            lo_m, hi_m = m + (j - i) + 1, min(ex, k * 1440 + 1439) - k * 1440
            run = 0
            for mm_ in range(lo_m, hi_m + 1):
                v = imb[mm_]
                run = run + 1 if np.isfinite(v) and d * v <= -0.6 else 0
                ii = k * 1440 + mm_
                if run >= 3 and d * (c[ii] - px) < 0 and ii < ex:
                    ex, px_out, why = ii, c[ii], "book"
                    break
        net = d * (px_out - px) - cost
        trades.append({"i": int(j), "exit": int(ex), "d": d, "net": float(net), "why": why,
                       "month": int(months_of(k)), "stop": float(stop_d)})
        busy_until = ex
    return trades


_ADJ = None
_MONTHS = None


def adj_at(c, j):
    return _ADJ[j]


def months_of(k):
    return _MONTHS[k]


def stats(trades: list[dict], rr: float, stop_k: float, cost: float, rng) -> dict:
    if len(trades) < 20:
        return {"trades": len(trades)}
    p = np.array([t["net"] for t in trades])
    mo = np.array([t["month"] for t in trades])
    wins, losses = p[p > 0], p[p <= 0]
    boots = np.array([rng.choice(p, p.size).mean() for _ in range(400)])
    eq = np.cumsum(p)
    dd = float((np.maximum.accumulate(eq) - eq).max())
    stop_mean = float(np.mean([t["stop"] for t in trades]))
    be = (stop_mean + cost) / (stop_mean * (1 + rr))
    months = np.unique(mo)
    return {
        "trades": int(p.size), "mean_net": round(float(p.mean()), 2), "total": round(float(p.sum()), 1),
        "win_rate": round(float((p > 0).mean()), 3), "breakeven_win_rate": round(float(be), 3),
        "pl_ratio": round(float(wins.mean() / -losses.mean()), 2) if wins.size and losses.size else None,
        "profit_factor": round(float(wins.sum() / -losses.sum()), 2) if losses.size and losses.sum() else None,
        "mean_2025": round(float(p[mo < 202601].mean()), 2) if (mo < 202601).any() else None,
        "mean_2026": round(float(p[mo >= 202601].mean()), 2) if (mo >= 202601).any() else None,
        "ci95": [round(float(np.quantile(boots, 0.025)), 2), round(float(np.quantile(boots, 0.975)), 2)],
        "positive_months": f"{int(sum(p[mo == m].sum() > 0 for m in months))}/{months.size}",
        "max_drawdown": round(dd, 1), "stop_ticks": round(stop_mean, 1),
        "exits": {w: int(sum(t["why"] == w for t in trades)) for w in ("stop", "target", "time", "book")},
    }


def main(argv=None):
    global _ADJ, _MONTHS
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=Path, default=Path("data/processed/6e_minute_bars_dev_1"))
    parser.add_argument("--book", type=Path, default=Path("data/processed/6e_book_minutes_dev_1"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/6e_session_pa_study_dev_1.json"))
    parser.add_argument("--quick", action="store_true", help="smaller grid for smoke tests")
    parser.add_argument("--part", default=None, help="k/N: run every N-th configuration starting at k (0-based)")
    parser.add_argument("--merge", nargs="*", type=Path, help="merge these part files into --output and report")
    parser.add_argument("--sweep", action="store_true", help="robustness sweep around the reversal candidate")
    args = parser.parse_args(argv)
    if args.merge:
        results = [r for p in args.merge for r in json.loads(p.read_text())]
        args.output.write_text(json.dumps(results, indent=1))
        report(results)
        return

    m = tm.load_minutes(args.bars)
    c_raw, h_raw, l_raw, adj = m["close"], m["high"], m["low"], m["adj"]
    c, h, l = c_raw + adj, h_raw + adj, l_raw + adj
    n = c.size
    _ADJ = adj
    _MONTHS = np.array([d.year * 100 + d.month for d in m["dates"]])
    mod, dayk = minute_of_day(n), m["day"]
    a = atr_minutes(h, l, c)
    print(f"{len(m['dates'])} days, ATR median {np.nanmedian(a):.1f} ticks", flush=True)

    books, depth_tot = [], np.full(n, np.nan)
    for k, d in enumerate(m["dates"]):
        bp = args.book / f"{d.isoformat()}.json"
        if not bp.exists():
            books.append(None)
            continue
        b = bs.book_arrays(json.loads(bp.read_text()))
        tot = b["bid_sz"] + b["ask_sz"]
        b["imb"] = np.divide(b["bid_sz"] - b["ask_sz"], tot, out=np.full(1440, np.nan), where=tot > 0)
        books.append(b)
        depth_tot[k * 1440:(k + 1) * 1440] = b["bid_d5"] + b["ask_d5"]
    med60 = np.full(n, np.nan)
    from numpy.lib.stride_tricks import sliding_window_view
    med60[60:] = np.nanmedian(sliding_window_view(depth_tot, 60)[:-1], axis=1)
    depth_ok = depth_tot >= med60
    print(f"{sum(b is not None for b in books)} days with book data", flush=True)

    rng = np.random.default_rng(7)
    trend4 = np.sign(c - np.concatenate([np.full(240, np.nan), c[:-240]]))
    if args.sweep:
        # Robustness of the failed-breakout reversal candidate: vary everything near it.
        WINDOWS["london"] = [(7 * 60, 9 * 60)]
        WINDOWS["newyork"] = [(13 * 60, 16 * 60)]
        WINDOWS["sessions_wide"] = [(6 * 60, 10 * 60), (12 * 60, 17 * 60)]
        out = []
        combos = list(itertools.product(
            (180, 240, 300), (10, 15, 20), (0.8, 1.0, 1.2), ("sessions", "london", "newyork", "sessions_wide"), (1.0, 1.5)))
        if args.part:
            k_, n_ = (int(v) for v in args.part.split("/"))
            combos = combos[k_::n_]
        for lookback, bounce, mult, window, stop_k in combos:
            sig = pattern_signals(c, h, l, a, "reversal", lookback=lookback, bounce=bounce)
            sig[sig != trend4] = 0
            sig[~in_windows(mod, window)] = 0
            dok = depth_tot >= mult * med60
            trades = simulate(c, h, l, a, mod, dayk, books, sig, "passive", stop_k, 3.0, 240, False, dok)
            st = stats(trades, 3.0, stop_k, PASSIVE_COST, rng)
            cfg = dict(lookback=lookback, bounce=bounce, depth_mult=mult, window=window, stop_k=stop_k)
            out.append({**cfg, **st})
            print(cfg, {k: st.get(k) for k in ("trades", "mean_net", "win_rate", "mean_2025", "mean_2026", "positive_months")}, flush=True)
        args.output.write_text(json.dumps(out, indent=1))
        ok = [r for r in out if r.get("trades", 0) >= 20]
        print(f"\n{len(ok)} sweep configs; positive mean: {sum(r['mean_net'] > 0 for r in ok)}; "
              f"median mean_net {np.median([r['mean_net'] for r in ok]):+.2f}; "
              f"both years positive: {sum((r['mean_2025'] or 0) > 0 and (r['mean_2026'] or 0) > 0 for r in ok)}")
        for dim in ("lookback", "bounce", "depth_mult", "window", "stop_k"):
            parts = [f"{v}: {np.mean([r['mean_net'] for r in ok if str(r[dim]) == v]):+.2f}" for v in sorted({str(r[dim]) for r in ok})]
            print(f"  {dim:10s} " + " | ".join(parts))
        return
    raw = {k: pattern_signals(c, h, l, a, k, rng) for k in ("breakout", "pullback", "reversal", "random")}
    for k, s in raw.items():
        print(f"  raw {k}: {int((s != 0).sum())} signal minutes", flush=True)

    grid = dict(pattern=list(raw), trend=[True, False], window=["sessions", "day"], depth=[False, True],
                entry=["market", "passive"], stop_k=[1.0, 1.5], rr=[1.0, 2.0, 3.0, 4.0], hold=[240],
                book_exit=[False, True])
    if args.quick:
        grid.update(trend=[True], window=["sessions"], depth=[False], stop_k=[1.0], rr=[2.0], book_exit=[False])
    results = []
    keys = list(grid)
    combos = list(itertools.product(*grid.values()))
    if args.part:
        k_, n_ = (int(v) for v in args.part.split("/"))
        combos = combos[k_::n_]
    print(f"{len(combos)} configurations", flush=True)
    for idx, combo in enumerate(combos):
        cfg = dict(zip(keys, combo))
        sig = raw[cfg["pattern"]].copy()
        if cfg["trend"]:
            sig[sig != trend4] = 0
        sig[~in_windows(mod, cfg["window"])] = 0
        trades = simulate(c, h, l, a, mod, dayk, books, sig, cfg["entry"], cfg["stop_k"], cfg["rr"],
                          cfg["hold"], cfg["book_exit"], depth_ok if cfg["depth"] else None)
        cost = MARKET_COST if cfg["entry"] == "market" else PASSIVE_COST
        st = stats(trades, cfg["rr"], cfg["stop_k"], cost, rng)
        results.append({**cfg, **st})
        if idx % 32 == 0 or st.get("mean_net", -99) > 0:
            print(f"[{idx + 1}/{len(combos)}] {cfg} -> {st}", flush=True)
    args.output.write_text(json.dumps(results, indent=1))
    report(results)


def report(results: list[dict]) -> None:
    ok = [r for r in results if r.get("trades", 0) >= 20]
    ok.sort(key=lambda r: r["mean_net"], reverse=True)
    print("\nTop 15 by mean net ticks/trade:")
    for r in ok[:15]:
        print({k: r[k] for k in ("pattern", "trend", "window", "depth", "entry", "stop_k", "rr", "book_exit",
                                 "trades", "mean_net", "win_rate", "breakeven_win_rate", "pl_ratio",
                                 "profit_factor", "mean_2025", "mean_2026", "ci95", "positive_months")})
    print("\nEffect of each dimension (average mean net ticks/trade over all other settings):")
    for dim in ("pattern", "trend", "window", "depth", "entry", "stop_k", "rr", "book_exit"):
        parts = []
        for v in sorted({str(r[dim]) for r in ok}):
            vals = [r["mean_net"] for r in ok if str(r[dim]) == v]
            wr = [r["win_rate"] for r in ok if str(r[dim]) == v]
            parts.append(f"{v}: {np.mean(vals):+.2f} (win {np.mean(wr):.2f}, n={len(vals)})")
        print(f"  {dim:10s} " + " | ".join(parts))
    print("\nRandom-entry benchmark by rr (market, no filters):")
    for r in results:
        if r["pattern"] == "random" and not r["trend"] and r["window"] == "day" and not r["depth"] \
                and r["entry"] == "market" and r["stop_k"] == 1.0 and not r["book_exit"]:
            print({k: r.get(k) for k in ("rr", "trades", "mean_net", "win_rate", "breakeven_win_rate", "pl_ratio")})


if __name__ == "__main__":
    main()
