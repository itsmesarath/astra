"""Trained opportunity model: predict 2:1 bracket winners, then trade only the top picks.

Built on the hindsight study (``six_e_hindsight_study``). For each side, a logistic model
predicts "this minute is a +20 before -10 tick winner within 60 minutes". The model is
refit every month on all earlier months (expanding walk-forward). The threshold is the
95th percentile of *training* scores, so only about the top 5% of minutes are traded.

Trades are simulated honestly:
- non-overlapping, one contract;
- bracket +20 / -10 ticks on minute highs and lows, stop first if both are touched in the
  same minute;
- time exit at 60 minutes;
- cost deducted per round trip.
Opposite signals in the same minute are skipped. Only data before the Jul-Sep 2026 lockbox
is used.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ai_trader.research import six_e_minute_model as mm
from ai_trader.research.six_e_hindsight_study import DOWN, UP, WINDOW, opportunities


def fit_logistic(z: np.ndarray, t: np.ndarray, steps: int = 300, l2: float = 1e-3):
    w = np.zeros(z.shape[1]); b = float(np.log(t.mean() / (1 - t.mean())))
    for _ in range(steps):
        p = 1 / (1 + np.exp(-(z @ w + b)))
        w -= 0.5 * (z.T @ (p - t) / len(t) + l2 * w)
        b -= 0.5 * float((p - t).mean())
    return w, b


def bracket(hi, lo, cl, i, direction, cost):
    entry = cl[i]
    for j in range(i + 1, min(i + 1 + WINDOW, len(cl))):
        if not np.isfinite(hi[j]):
            continue
        if direction > 0:
            if lo[j] <= entry - DOWN: return -DOWN - cost, j
            if hi[j] >= entry + UP: return UP - cost, j
        else:
            if hi[j] >= entry + DOWN: return -DOWN - cost, j
            if lo[j] <= entry - UP: return UP - cost, j
    last = min(i + WINDOW, len(cl) - 1)
    while last > i and not np.isfinite(cl[last]): last -= 1
    return direction * (cl[last] - entry) - cost, last


def main(argv=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cost", type=float, default=2.6)
    parser.add_argument("--top", type=float, default=0.05)
    args = parser.parse_args(argv)
    days = mm.load_days(Path("data/processed/6e_minute_bars_dev_1"))
    X, Y, MO, DAY, MIN = [], [], [], [], []
    paths = []
    for d, day in enumerate(days):
        rows, label = opportunities(day)
        u = rows["usable"]
        X.append(np.column_stack([rows[f][u] for f in mm.FEATURES])); Y.append(label[u])
        MO.append(np.full(u.sum(), int(day["utc_date"][:4]) * 100 + int(day["utc_date"][5:7])))
        DAY.append(np.full(u.sum(), d)); MIN.append(np.flatnonzero(u))
        start = int(np.datetime64(day["utc_date"], "s").astype(np.int64)) * 10**9
        hi = np.full(1440, np.nan); lo = np.full(1440, np.nan); cl = np.full(1440, np.nan)
        for minute, _o, h, l, c, *_ in day["bars"]:
            k = (minute - start) // mm.MINUTE_NS
            hi[k], lo[k], cl[k] = h / mm.TICK, l / mm.TICK, c / mm.TICK
        paths.append((hi, lo, cl))
    x, y, mo, dd, mi = map(np.concatenate, (X, Y, MO, DAY, MIN)) if False else (np.vstack(X), np.concatenate(Y), np.concatenate(MO), np.concatenate(DAY), np.concatenate(MIN))
    report = {"cost_ticks": args.cost, "top_share": args.top, "months": {}}
    all_pnl = []
    for m in sorted(v for v in np.unique(mo) if v >= 202507):
        train, test = mo < m, mo == m
        mean, std = x[train].mean(0), x[train].std(0); std[std == 0] = 1
        zt, ze = (x[train] - mean) / std, (x[test] - mean) / std
        sig = np.zeros(test.sum())
        for side in (1, -1):
            w, b = fit_logistic(zt, (y[train] == side).astype(float))
            thr = np.quantile(zt @ w + b, 1 - args.top)
            pick = (ze @ w + b) > thr
            sig = np.where(pick & (sig == 0), side, np.where(pick & (sig != 0), 0, sig))
        idx = np.flatnonzero(test)
        order = idx[np.lexsort((mi[idx], dd[idx]))]
        sig_by = dict(zip(idx, sig))
        pnl, busy = [], (-1, -1)
        for k in order:
            s = sig_by[k]
            if s == 0 or (dd[k], mi[k]) < busy: continue
            hi, lo, cl = paths[dd[k]]
            v, exit_min = bracket(hi, lo, cl, mi[k], s, args.cost)
            pnl.append((s, v)); busy = (dd[k], exit_min)
        vals = np.array([v for _, v in pnl])
        report["months"][str(m)] = {"trades": len(vals), "total_net_ticks": round(float(vals.sum()), 1) if len(vals) else 0,
                                    "mean_net_ticks": round(float(vals.mean()), 2) if len(vals) else None,
                                    "long": sum(1 for s, _ in pnl if s > 0), "short": sum(1 for s, _ in pnl if s < 0)}
        all_pnl += [v for _, v in pnl]
        print(m, report["months"][str(m)], flush=True)
    a = np.array(all_pnl)
    eq = np.cumsum(a)
    report["pooled"] = {"trades": len(a), "mean_net_ticks": round(float(a.mean()), 2), "total_net_ticks": round(float(a.sum()), 1),
                        "win_rate": round(float((a > 0).mean()), 3), "max_drawdown_ticks": round(float((np.maximum.accumulate(eq) - eq).max()), 1),
                        "positive_months": sum(1 for r in report["months"].values() if r["total_net_ticks"] > 0), "months": len(report["months"])}
    print("POOLED", report["pooled"])
    Path(f"data/processed/6e_opportunity_model_dev_cost{args.cost:g}_top{args.top:g}.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
