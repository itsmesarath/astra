"""Burst-momentum study on 6E tick history: do volume bursts have follow-through worth trading?

A *burst* is a rolling window of ``W`` seconds in which traded volume is at least ``k`` times the
trailing-hour average for a window of that length (and at least ``vmin`` contracts), price has moved
at least ``m`` ticks from the window start, and the aggressor side (trade at ask = buy, at bid = sell)
agrees with the direction by at least ``imb`` share. The trade enters at the next tick on the far
side of the spread, in the burst direction, and exits on the first of: trailing stop ``trail`` ticks
from the best price seen, hard stop ``hard`` ticks, time limit ``T`` seconds, or (if ``flip``) the
10-second aggressor imbalance turning against the trade after at least 10 s in position. One trade at
a time, 60 s cooldown after an exit. Costs: ``cost`` ticks round trip (default 1.8, IC Markets EURUSD
model) plus the spread crossed on entry and exit (taken from the recorded bid/ask).

Data: ``Documents\\NinjaTrader 8\\ai-trader-history\\6E_*\\tick_<date>.jsonl`` from the history
connector; per date the contract with the most ticks is the front month. Lockbox days (Jul-Sep 2026)
are refused unless ``--allow-lockbox`` (final test only).

Run per month in separate processes (``--month 2026-01``) and ``--merge`` the part files.
"""

from __future__ import annotations

import argparse
import itertools
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

TICK = 0.00005
LOCKBOX = (date(2026, 7, 1), date(2026, 10, 1))
DEFAULT_GRID = dict(W=[5, 10], k=[10, 20], m=[3, 5], trail=[3, 5, 8], T=[60, 180, 600], flip=[False, True])
FIXED = dict(vmin=150, imb=0.6, hard=10, cooldown=60, cost=1.8)


# ----------------------------------------------------------------------------- data
def day_files(history: Path) -> dict[date, Path]:
    """date -> tick file of the contract with the most ticks that day (front month)."""
    best: dict[date, tuple[int, Path]] = {}
    for p in history.glob("6E_*/tick_*.jsonl"):
        d = date.fromisoformat(p.stem[5:])
        size = p.stat().st_size
        if d not in best or size > best[d][0]:
            best[d] = (size, p)
    return {d: p for d, (s, p) in sorted(best.items()) if s > 1000}


def load_day(path: Path):
    t, p, v, s = [], [], [], []
    with path.open() as fh:
        for line in fh:
            if not line.startswith('{"t"'):
                continue
            r = json.loads(line)
            t.append(r["t"]); p.append(r["p"]); v.append(r["v"])
            s.append(1 if r["p"] >= r["a"] else (-1 if r["p"] <= r["b"] else 0))
    t = np.asarray(t, dtype=np.int64) / 1e9
    px = np.rint(np.asarray(p) / TICK).astype(np.int64)
    return t, px, np.asarray(v, dtype=np.int64), np.asarray(s, dtype=np.int8)


# ----------------------------------------------------------------------------- detection
def bursts(t, px, v, s, W, k, m, vmin, imb):
    """Indices i where the window (t[i]-W, t[i]] is a burst; returns (indices, directions)."""
    n = t.size
    if n < 100:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int8)
    cv = np.concatenate([[0], np.cumsum(v)])
    cb = np.concatenate([[0], np.cumsum(v * (s > 0))])
    cs = np.concatenate([[0], np.cumsum(v * (s < 0))])
    start = np.searchsorted(t, t - W, side="right")      # first tick inside the window
    vol = cv[np.arange(n) + 1] - cv[start]
    hour = np.searchsorted(t, t - 3600, side="right")
    base = (cv[np.arange(n) + 1] - cv[hour]) * (W / 3600.0)   # average volume per W seconds, trailing hour
    move = px - px[np.maximum(start - 1, 0)]
    buy = cb[np.arange(n) + 1] - cb[start]
    sell = cs[np.arange(n) + 1] - cs[start]
    with np.errstate(divide="ignore", invalid="ignore"):
        share_b = np.where(vol > 0, buy / vol, 0.0)
        share_s = np.where(vol > 0, sell / vol, 0.0)
    ok_vol = (vol >= np.maximum(k * base, vmin)) & (t - t[0] > 3600)
    up = ok_vol & (move >= m) & (share_b >= imb)
    dn = ok_vol & (move <= -m) & (share_s >= imb)
    idx = np.flatnonzero(up | dn)
    return idx, np.where(up[idx], 1, -1).astype(np.int8)


# ----------------------------------------------------------------------------- simulation
def simulate(t, px, v, s, idx, dirs, trail, hard, T, flip, cooldown, cost):
    trades = []
    n = t.size
    busy_until = -1.0
    cb = np.concatenate([[0], np.cumsum(v * (s > 0))])
    cs = np.concatenate([[0], np.cumsum(v * (s < 0))])
    for i, d in zip(idx, dirs):
        if t[i] < busy_until or i + 1 >= n:
            continue
        j = i + 1
        entry = px[j] + d            # cross the spread: pay one tick
        best = px[j]
        t_in = t[j]
        exit_px, why, e = None, None, None
        for e in range(j + 1, n):
            p = px[e]
            if d * (p - best) > 0:
                best = p
            pnl = d * (p - entry)
            if d * (best - p) >= trail:
                exit_px, why = p, "trail"; break
            if pnl <= -hard:
                exit_px, why = p, "hard"; break
            if t[e] - t_in >= T:
                exit_px, why = p, "time"; break
            if flip and t[e] - t_in >= 10:
                w0 = np.searchsorted(t, t[e] - 10, side="right")
                b, sl = cb[e + 1] - cb[w0], cs[e + 1] - cs[w0]
                tot = b + sl
                if tot > 0 and (sl if d > 0 else b) / tot >= 0.6:
                    exit_px, why = p, "flip"; break
        if exit_px is None:
            exit_px, why, e = px[-1], "eod", n - 1
        net = d * (exit_px - entry) - 1 - cost     # exit crosses the spread too
        trades.append({"t": float(t[j]), "d": int(d), "entry": int(entry), "exit": int(exit_px),
                       "hold_s": float(t[e] - t_in), "net": float(net), "why": why})
        busy_until = t[e] + cooldown
    return trades


def stats(trades, days):
    if not trades:
        return {"trades": 0}
    net = np.array([tr["net"] for tr in trades])
    months = defaultdict(list)
    for tr in trades:
        months[date.fromtimestamp(tr["t"]).strftime("%Y-%m")].append(tr["net"])
    boot = np.random.default_rng(0).choice(net, (2000, net.size)).mean(axis=1)
    return {"trades": int(net.size), "per_day": round(net.size / max(days, 1), 2), "mean_net": round(float(net.mean()), 2),
            "median_net": round(float(np.median(net)), 2), "win": round(float((net > 0).mean()), 3),
            "ci95": [round(float(np.percentile(boot, 2.5)), 2), round(float(np.percentile(boot, 97.5)), 2)],
            "total": round(float(net.sum()), 1), "mean_hold_s": round(float(np.mean([tr["hold_s"] for tr in trades])), 0),
            "exits": {w: int(sum(tr["why"] == w for tr in trades)) for w in ("trail", "hard", "time", "flip", "eod")},
            "months": {k: [len(v), round(float(np.mean(v)), 2)] for k, v in sorted(months.items())}}


# ----------------------------------------------------------------------------- driver
def run(history: Path, month: str | None, grid: dict, allow_lockbox: bool, log=print):
    files = day_files(history)
    sel = {d: p for d, p in files.items() if (month is None or d.strftime("%Y-%m") == month)}
    for d in sel:
        if LOCKBOX[0] <= d < LOCKBOX[1] and not allow_lockbox:
            raise ValueError(f"lockbox day {d} refused")
    combos = [dict(zip(grid, c)) for c in itertools.product(*grid.values())]
    per_cfg = defaultdict(list)
    for d, p in sel.items():
        t, px, v, s = load_day(p)
        det_cache = {}
        for cfg in combos:
            dk = (cfg["W"], cfg["k"], cfg["m"])
            if dk not in det_cache:
                det_cache[dk] = bursts(t, px, v, s, cfg["W"], cfg["k"], cfg["m"], FIXED["vmin"], FIXED["imb"])
            idx, dirs = det_cache[dk]
            per_cfg[json.dumps(cfg, sort_keys=True)] += simulate(t, px, v, s, idx, dirs, cfg["trail"], FIXED["hard"], cfg["T"],
                                                                 cfg["flip"], FIXED["cooldown"], FIXED["cost"])
        log(f"{d}: {t.size} ticks")
    return {"days": len(sel), "trades": {k: v for k, v in per_cfg.items()}}


def merge(parts: list[Path]) -> list[dict]:
    days = 0
    allt = defaultdict(list)
    for p in parts:
        doc = json.loads(p.read_text())
        days += doc["days"]
        for k, v in doc["trades"].items():
            allt[k] += v
    rows = []
    for k, v in allt.items():
        rows.append({**json.loads(k), **stats(v, days)})
    rows.sort(key=lambda r: -(r.get("mean_net", -99) * r.get("trades", 0)))
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--history", type=Path, default=Path.home() / "Documents" / "NinjaTrader 8" / "ai-trader-history")
    p.add_argument("--month", default=None, help="YYYY-MM to process (one part)")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--merge", nargs="*", type=Path)
    p.add_argument("--allow-lockbox", action="store_true")
    p.add_argument("--quick", action="store_true")
    a = p.parse_args(argv)
    if a.merge:
        rows = merge(a.merge)
        if a.out:
            a.out.write_text(json.dumps(rows, indent=1))
        for r in rows[:12]:
            print({k: r[k] for k in ("W", "k", "m", "trail", "T", "flip", "trades", "per_day", "mean_net", "win", "ci95", "exits")})
        return
    grid = dict(DEFAULT_GRID)
    if a.quick:
        grid = dict(W=[10], k=[20], m=[3], trail=[5], T=[180], flip=[True])
    doc = run(a.history, a.month, grid, a.allow_lockbox)
    out = a.out or Path(f"data/processed/burst_{a.month or 'all'}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc))
    print("wrote", out, "days", doc["days"])


if __name__ == "__main__":
    main()
