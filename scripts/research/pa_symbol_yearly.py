"""Per-year breakdown of one price-action configuration on one CFD symbol, in points and in R (net / stop).

Usage: python scripts/research/pa_symbol_yearly.py XAUUSD --window sessions [--pattern reversal --stop-k 1.5 --rr 3]
Reads data/raw/dukascopy/<symbol> (lockbox days refused by the loader).
"""
import argparse, itertools, json
from pathlib import Path
import numpy as np
from ai_trader.research import pa_multi_market_study as mm
from ai_trader.research import six_e_session_pa_study as ps


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("symbol"); p.add_argument("--window", default="sessions"); p.add_argument("--pattern", default="reversal")
    p.add_argument("--stop-k", type=float, default=1.5); p.add_argument("--rr", type=float, default=3.0)
    p.add_argument("--no-trend", action="store_true"); p.add_argument("--data", type=Path, default=Path("data/raw/dukascopy"))
    p.add_argument("--out", type=Path, default=None)
    a = p.parse_args(argv)
    m = mm.load_symbol(a.data / a.symbol)
    grid = dict(pattern=[a.pattern], trend=[not a.no_trend], window=[a.window], stop_k=[a.stop_k], rr=[a.rr])
    rng = np.random.default_rng(0)
    # re-run run_symbol internals to keep the trade list
    c, h, l = m["close"], m["high"], m["low"]; n = c.size
    ps._ADJ = np.zeros(n); ps._MONTHS = np.array([d.year * 100 + d.month for d in m["dates"]])
    mod, dayk = ps.minute_of_day(n), m["day"]; at = ps.atr_minutes(h, l, c); cost = mm.COSTS[a.symbol][0]
    trend4 = np.sign(c - np.concatenate([np.full(240, np.nan), c[:-240]]))
    sig = ps.pattern_signals(c, h, l, at, a.pattern, rng)
    if not a.no_trend: sig[sig != trend4] = 0
    sig[~ps.in_windows(mod, a.window)] = 0; sig[~np.isfinite(c)] = 0
    trades = ps.simulate(c, h, l, at, mod, dayk, [None] * len(m["dates"]), sig, "market", a.stop_k, a.rr, 240, False, None, cost=cost)
    years = sorted({t["month"] // 100 for t in trades})
    rows = []
    print(f"{a.symbol} {a.pattern} trend={not a.no_trend} {a.window} k{a.stop_k} rr{a.rr}  cost {cost} pts")
    print(f"{'year':5} {'n':>5} {'/day':>5} {'win':>5} {'mean pts':>9} {'net/cost':>8} {'mean R':>7} {'sum R':>7} {'pf':>5}")
    for y in years + ["all"]:
        ts = [t for t in trades if y == "all" or t["month"] // 100 == y]
        net = np.array([t["net"] for t in ts]); R = net / np.array([t["stop"] for t in ts])
        wins, losses = net[net > 0].sum(), -net[net < 0].sum()
        days = sum(1 for d in m["dates"] if y == "all" or d.year == y)
        row = dict(year=y, n=len(ts), per_day=round(len(ts) / max(days, 1) * 7 / 5, 2), win=round(float((net > 0).mean()), 3),
                   mean_pts=round(float(net.mean()), 1), net_in_costs=round(float(net.mean() / cost), 2),
                   mean_R=round(float(R.mean()), 3), sum_R=round(float(R.sum()), 1), pf=round(float(wins / losses), 2) if losses else None)
        rows.append(row)
        print(f"{row['year']!s:5} {row['n']:5} {row['per_day']:5} {row['win']:5} {row['mean_pts']:9} {row['net_in_costs']:8} {row['mean_R']:7} {row['sum_R']:7} {row['pf']!s:5}")
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True); a.out.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
