"""Intraday price-action study across IC Markets-style instruments on free Dukascopy history.

Same engine as ``six_e_session_pa_study`` (patterns, 4-hour trend filter, session windows,
ATR stop with 1-4x targets, 240-minute hold, flat before the day end), applied to the
1-minute candles fetched by ``scripts/data/fetch_dukascopy_minutes.py``. There is no order
book in this history, so entries are market orders and the depth filter is unavailable; the
book-based filters are tested separately on the 6E archive.

Cost model (round trip, in the instrument's price points, IC Markets Raw Spread, approximate;
verify against the live account before paper trading): spread + commission + a little
slippage. ``COSTS`` below documents each assumption.

Reported per instrument and configuration: trades, mean net (points), mean net in cost
multiples, win rate vs breakeven, P/L ratio, profit factor, by-year means, positive months,
bootstrap CI. Cross-market consistency is the key output: a configuration that is positive
on most instruments and most years is worth paper trading; one that is positive on one
instrument only is probably noise.
"""

from __future__ import annotations

import argparse
import itertools
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from ai_trader.research import six_e_session_pa_study as ps

RESERVED_FROM = date(2026, 7, 1)
# symbol -> (round-trip cost in points, note)
COSTS = {
    "EURUSD": (9, "0.1-0.2 pip spread + $7/lot commission (0.7 pip) + slippage"),
    "GBPUSD": (12, "0.2-0.3 pip spread + 0.7 pip commission + slippage"),
    "USDJPY": (12, "0.1-0.2 pip spread + ~1.1 pip commission (JPY pip value) + slippage"),
    "AUDUSD": (12, "0.2 pip spread + ~1.0 pip commission (AUD pip value) + slippage"),
    "XAUUSD": (250, "0.10-0.20 USD spread + $7/100oz commission (0.07) + slippage, point 0.001"),
    "US100": (1300, "~1.0 index point spread, no commission, slippage; point 0.001"),
    "DE40": (1300, "~1.0 index point spread, no commission, slippage; point 0.001"),
    "US30": (2500, "~2.0 index point spread, no commission, slippage; point 0.001"),
    "US500": (500, "~0.4 index point spread, no commission, slippage; point 0.001"),
}
ps.WINDOWS["us_cash"] = [(13 * 60 + 30, 20 * 60)]


def load_symbol(directory: Path) -> dict | None:
    files = sorted(p for p in directory.glob("*.json") if p.stat().st_size > 0)
    days = []
    for p in files:
        d = date.fromisoformat(p.stem)
        if d >= RESERVED_FROM:
            raise ValueError("Reserved lockbox day found")
        doc = json.loads(p.read_text())
        days.append((d, doc))
    if not days:
        return None
    # continuous calendar from first to last day so day_index*1440 + minute is consistent
    first, last = days[0][0], days[-1][0]
    n_days = (last - first).days + 1
    n = n_days * 1440
    h, l, c = (np.full(n, np.nan) for _ in range(3))
    traded = np.zeros(n, dtype=bool)
    for d, doc in days:
        base = (d - first).days * 1440
        start = int(np.datetime64(d.isoformat(), "s").astype(np.int64)) * 10**9
        for minute, o, hi, lo, cl, vol in doc["bars"]:
            if vol <= 0 and o == hi == lo == cl:
                continue  # Dukascopy filler bar: no trade
            i = base + int((minute - start) // 60_000_000_000)
            h[i], l[i], c[i], traded[i] = hi, lo, cl, True
    for i in range(1, n):
        if not traded[i] and np.isfinite(c[i - 1]):
            h[i] = l[i] = c[i] = c[i - 1]
    dates = [first + timedelta(k) for k in range(n_days)]
    return {"high": h, "low": l, "close": c, "traded": traded, "dates": dates,
            "day": np.repeat(np.arange(n_days), 1440), "traded_days": len(days)}


def run_symbol(name: str, m: dict, rng, grid: dict, part: str | None = None) -> list[dict]:
    c, h, l = m["close"], m["high"], m["low"]
    n = c.size
    ps._ADJ = np.zeros(n)
    ps._MONTHS = np.array([d.year * 100 + d.month for d in m["dates"]])
    mod, dayk = ps.minute_of_day(n), m["day"]
    a = ps.atr_minutes(h, l, c)
    cost = COSTS[name][0]
    trend4 = np.sign(c - np.concatenate([np.full(240, np.nan), c[:-240]]))
    raw = {k: ps.pattern_signals(c, h, l, a, k, rng) for k in grid["pattern"]}
    # never trade across a data gap (weekend / missing day): require the last 240 minutes traded or filled
    gap = ~np.isfinite(c)
    out = []
    combos = list(itertools.product(*grid.values()))
    if part:
        k_, n_ = (int(v) for v in part.split("/"))
        combos = combos[k_::n_]
    for combo in combos:
        cfg = dict(zip(grid, combo))
        sig = raw[cfg["pattern"]].copy()
        if cfg["trend"]:
            sig[sig != trend4] = 0
        sig[~ps.in_windows(mod, cfg["window"])] = 0
        sig[gap] = 0
        trades = ps.simulate(c, h, l, a, mod, dayk, [None] * len(m["dates"]), sig, "market",
                             cfg["stop_k"], cfg["rr"], 240, False, None, cost=cost)
        st = ps.stats(trades, cfg["rr"], cfg["stop_k"], cost, rng)
        if "mean_net" in st:
            st["mean_net_in_costs"] = round(st["mean_net"] / cost, 2)
            st["trades_per_day"] = round(st["trades"] / m["traded_days"], 2)
        out.append({"symbol": name, "cost_points": cost, "atr_median": float(np.nanmedian(a)), **cfg, **st})
    return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, default=Path("data/raw/dukascopy"))
    p.add_argument("--symbols", nargs="*", default=list(COSTS))
    p.add_argument("--output", type=Path, default=Path("data/processed/pa_multi_market_study_1.json"))
    p.add_argument("--quick", action="store_true")
    p.add_argument("--part", default=None, help="k/N slice of the configuration grid")
    p.add_argument("--merge", nargs="*", type=Path, help="merge part files into --output and report")
    a = p.parse_args(argv)
    if a.merge:
        results = [r for f in a.merge for r in json.loads(f.read_text())]
        a.output.write_text(json.dumps(results, indent=1))
        report(results)
        return
    grid = dict(pattern=["breakout", "pullback", "reversal", "random"], trend=[True, False],
                window=["sessions", "day", "us_cash"], stop_k=[1.0, 1.5], rr=[1.0, 2.0, 3.0, 4.0])
    if a.quick:
        grid.update(trend=[True], window=["sessions"], stop_k=[1.0], rr=[3.0])
    rng = np.random.default_rng(11)
    results = []
    for name in a.symbols:
        m = load_symbol(a.data / name)
        if m is None:
            print(f"{name}: no data yet", flush=True)
            continue
        print(f"{name}: {m['traded_days']} days {m['dates'][0]}..{m['dates'][-1]}", flush=True)
        res = run_symbol(name, m, rng, grid, a.part)
        results.extend(res)
        best = max((r for r in res if r.get("trades", 0) >= 30), key=lambda r: r["mean_net_in_costs"], default=None)
        if best:
            print("  best:", {k: best[k] for k in ("pattern", "trend", "window", "stop_k", "rr", "trades", "mean_net_in_costs",
                                                   "win_rate", "breakeven_win_rate", "positive_months")}, flush=True)
    a.output.write_text(json.dumps(results, indent=1))
    report(results)


def report(results: list[dict]) -> None:
    ok = [r for r in results if r.get("trades", 0) >= 30]
    syms = sorted({r["symbol"] for r in ok})
    keys = ("pattern", "trend", "window", "stop_k", "rr")
    print(f"\n{len(ok)} rows with >=30 trades across {syms}")
    print("\nCross-market consistency (configs ranked by number of instruments with positive mean net):")
    by_cfg = {}
    for r in ok:
        by_cfg.setdefault(tuple(r[k] for k in keys), []).append(r)
    rows = []
    for cfg, rs in by_cfg.items():
        pos = sum(r["mean_net"] > 0 for r in rs)
        rows.append((pos, np.mean([r["mean_net_in_costs"] for r in rs]), cfg, rs))
    rows.sort(key=lambda t: (-t[0], -t[1]))
    for pos, avg, cfg, rs in rows[:15]:
        print(f"  {dict(zip(keys, cfg))}: positive on {pos}/{len(rs)}; mean {avg:+.2f} costs; "
              + ", ".join(f"{r['symbol']} {r['mean_net_in_costs']:+.2f}" for r in rs))
    print("\nMarginals (mean net in cost multiples):")
    for dim in keys + ("symbol",):
        parts = [f"{v}: {np.mean([r['mean_net_in_costs'] for r in ok if str(r[dim]) == v]):+.2f}"
                 for v in sorted({str(r[dim]) for r in ok})]
        print(f"  {dim:8s} " + " | ".join(parts))


if __name__ == "__main__":
    main()
