"""Owner question (16 Oct 2026): what if we add a moving (trailing) stop loss?

The entries are the same as in the autopsy: the trained winning-trade finder's top 5% picks
and random entries, over Jul 2025 - Jun 2026 walk-forward test months. Only the exit
changes, to a trailing stop that follows price minute by minute.

Variants, all with 2.6 ticks round-trip cost:
- ``trail N``: the stop starts N ticks from entry and follows the best price by N ticks.
  There is no fixed target, and the trade exits after 60 or 120 minutes at the latest.
- ``trail N after +A``: a fixed -10 tick stop until the trade is A ticks up, then the stop
  trails by N ticks.

Fill model, conservative: each minute, the stop from the *previous* minute is checked
against this minute's low/high first, and only then is the stop moved using this minute's
best price. The stop fills 1 tick worse.
"""
from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np

from ai_trader.research import six_e_minute_model as mm
from ai_trader.research import six_e_trade_autopsy as ta
from ai_trader.research.six_e_hindsight_study import opportunities
from ai_trader.research.six_e_opportunity_model import fit_logistic


def trailing(hi, lo, cl, i, d, cost, trail, activate, hold):
    entry = cl[i]
    stop = entry - d * (10 if activate else trail)
    best = entry
    armed = not activate
    for j in range(i + 1, min(i + 1 + hold, 1440)):
        if not np.isfinite(hi[j]):
            continue
        if (d > 0 and lo[j] <= stop) or (d < 0 and hi[j] >= stop):
            return d * (stop - entry) - 1 - cost, j
        best = max(best, hi[j]) if d > 0 else min(best, lo[j])
        if not armed and d * (best - entry) >= activate:
            armed = True
        if armed:
            new = best - d * trail
            stop = max(stop, new) if d > 0 else min(stop, new)
    last = min(i + hold, 1439)
    while last > i and not np.isfinite(cl[last]):
        last -= 1
    return d * (cl[last] - entry) - cost, last


def main():
    days = mm.load_days(ta.BARS)
    X, Y, MO, DAY, MIN = [], [], [], [], []
    for d_i, day in enumerate(days):
        rows, label = opportunities(day)
        u = rows["usable"]
        X.append(np.column_stack([rows[f][u] for f in mm.FEATURES])); Y.append(label[u])
        MO.append(np.full(u.sum(), int(day["utc_date"][:4]) * 100 + int(day["utc_date"][5:7])))
        DAY.append(np.full(u.sum(), d_i)); MIN.append(np.flatnonzero(u))
    x, y, mo, dd, mi = np.vstack(X), np.concatenate(Y), np.concatenate(MO), np.concatenate(DAY), np.concatenate(MIN)
    paths = [ta.day_paths(day) for day in days]
    rng = np.random.default_rng(7)
    signals = []  # (month, idx array, model signal, random signal)
    for m in sorted(v for v in np.unique(mo) if v >= 202507):
        train, test = mo < m, mo == m
        mean, std = x[train].mean(0), x[train].std(0); std[std == 0] = 1
        zt, ze = (x[train] - mean) / std, (x[test] - mean) / std
        sig = np.zeros(test.sum())
        for side in (1, -1):
            w, b = fit_logistic(zt, (y[train] == side).astype(float))
            pick = (ze @ w + b) > np.quantile(zt @ w + b, 0.95)
            sig = np.where(pick & (sig == 0), side, np.where(pick & (sig != 0), 0, sig))
        idx = np.flatnonzero(test)
        rnd = np.where(rng.random(len(idx)) < 0.05, rng.choice([-1, 1], len(idx)), 0)
        signals.append((m, idx, sig, rnd))
    variants = [(t, 0, h) for t, h in itertools.product((5, 8, 10, 15, 20), (60, 120))] + \
               [(t, a, h) for t, a, h in itertools.product((5, 10), (10, 15), (60, 120))]
    print(f"{'exit rule':28s} {'finder n':>8s} {'finder/trade':>12s} {'finder 25/26':>14s} {'random/trade':>12s}")
    for trail, act, hold in variants:
        res = {}
        for name, which in (("finder", 2), ("random", 3)):
            pnl, yrs = [], []
            for sig_set in signals:
                m, idx, s = sig_set[0], sig_set[1], sig_set[which]
                order = np.lexsort((mi[idx], dd[idx]))
                busy = (-1, -1)
                for o in order:
                    k = idx[o]
                    if s[o] == 0 or (dd[k], mi[k]) < busy:
                        continue
                    hi, lo, cl = paths[dd[k]]
                    v, ex = trailing(hi, lo, cl, mi[k], int(s[o]), 2.6, trail, act, hold)
                    pnl.append(v); yrs.append(m // 100); busy = (dd[k], ex)
            p, yr = np.array(pnl), np.array(yrs)
            res[name] = (len(p), p.mean(), p[yr == 2025].mean(), p[yr == 2026].mean())
        label = f"trail {trail}" + (f" after +{act}" if act else "") + f", max {hold}m"
        f, r = res["finder"], res["random"]
        print(f"{label:28s} {f[0]:8d} {f[1]:+12.2f} {f[2]:+7.2f}/{f[3]:+6.2f} {r[1]:+12.2f}")
    print("Reference, fixed +20/-10 bracket: finder -2.62, random -3.01 ticks per trade")


if __name__ == "__main__":
    main()
