"""Trade autopsy: why did simulated 6E trades win or lose? (Mar 2025 - Jun 2026, lockbox sealed)

Strategies examined (all simulated, one contract, ticks):
- ``opportunity``: the trained winning-trade finder; monthly walk-forward logistic, top 5%
  picks, +20/-10 bracket, 60-minute time exit, 2.6-tick cost.
- ``trend``: the best hourly trend rule (momentum 72 h, passive limit -2 ticks, 3 ATR
  trailing stop, 1-tick fee plus fill slippage as simulated).
- ``random``: the same bracket as ``opportunity``, entered at random decision minutes with
  a random direction. This is the "no skill" yardstick: what costs alone do.

For every trade the autopsy records:
- MFE (best open profit) and MAE (worst open loss), in ticks;
- gross versus net result;
- hour (UTC), weekday, and proximity to 08:30 New York (US data releases);
- volatility quintile at entry (rv60), and whether the trade went with or against the
  4-hour trend.

Statistics per condition:
- n, mean, median, win rate;
- a bootstrap 95% confidence interval of the mean net result;
- the 2025 and 2026 means separately (a pattern counts as *consistent* only if both years
  have the same sign and the CI excludes zero);
- the number of tests run, for a multiple-comparison warning.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from ai_trader.research import six_e_minute_model as mm
from ai_trader.research import six_e_trend_model as tm
from ai_trader.research.six_e_hindsight_study import DOWN, UP, WINDOW, opportunities
from ai_trader.research.six_e_opportunity_model import fit_logistic

BARS = Path("data/processed/6e_minute_bars_dev_1")
NY = ZoneInfo("America/New_York")
RNG = np.random.default_rng(20261016)


def day_paths(day):
    start = int(np.datetime64(day["utc_date"], "s").astype(np.int64)) * 10**9
    hi = np.full(1440, np.nan); lo = np.full(1440, np.nan); cl = np.full(1440, np.nan)
    for minute, _o, h, l, c, *_ in day["bars"]:
        k = (minute - start) // mm.MINUTE_NS
        hi[k], lo[k], cl[k] = h / mm.TICK, l / mm.TICK, c / mm.TICK
    return hi, lo, cl


def bracket_detail(hi, lo, cl, i, d, cost):
    entry, mfe, mae = cl[i], 0.0, 0.0
    for j in range(i + 1, min(i + 1 + WINDOW, 1440)):
        if not np.isfinite(hi[j]):
            continue
        fav = (hi[j] - entry) if d > 0 else (entry - lo[j])
        adv = (entry - lo[j]) if d > 0 else (hi[j] - entry)
        if adv >= DOWN:
            return dict(gross=-DOWN, net=-DOWN - cost, mfe=max(mfe, min(fav, UP)), mae=DOWN, exit="stop", hold=j - i)
        mfe, mae = max(mfe, fav), max(mae, adv)
        if fav >= UP:
            return dict(gross=UP, net=UP - cost, mfe=UP, mae=mae, exit="target", hold=j - i)
    last = min(i + WINDOW, 1439)
    while last > i and not np.isfinite(cl[last]):
        last -= 1
    g = d * (cl[last] - entry)
    return dict(gross=g, net=g - cost, mfe=mfe, mae=mae, exit="time", hold=last - i)


def context(day, rows, i, d):
    dt = datetime.fromisoformat(day["utc_date"]).replace(tzinfo=timezone.utc)
    ny_830 = dt.replace(hour=8, minute=30, tzinfo=NY) if False else None
    local = datetime(dt.year, dt.month, dt.day, 8, 30, tzinfo=NY).astimezone(timezone.utc)
    news_min = local.hour * 60 + local.minute
    r240 = rows["r240"][i]
    return dict(
        date=day["utc_date"], year=int(day["utc_date"][:4]), month=day["utc_date"][:7],
        hour=int(i // 60), weekday=dt.strftime("%a"),
        near_us_news=bool(abs(i - news_min) <= 30),
        rv60=float(rows["rv60"][i]),
        with_4h_trend=("with" if np.sign(r240) == d else "against" if r240 != 0 else "flat"),
    )


def opportunity_and_random(days, cost=2.6, top=0.05):
    X, Y, MO, DAY, MIN, ROWS = [], [], [], [], [], []
    for d_i, day in enumerate(days):
        rows, label = opportunities(day)
        u = rows["usable"]
        X.append(np.column_stack([rows[f][u] for f in mm.FEATURES])); Y.append(label[u])
        MO.append(np.full(u.sum(), int(day["utc_date"][:4]) * 100 + int(day["utc_date"][5:7])))
        DAY.append(np.full(u.sum(), d_i)); MIN.append(np.flatnonzero(u)); ROWS.append(rows)
    x, y, mo, dd, mi = np.vstack(X), np.concatenate(Y), np.concatenate(MO), np.concatenate(DAY), np.concatenate(MIN)
    paths = [day_paths(day) for day in days]
    trades = {"opportunity": [], "random": []}
    for m in sorted(v for v in np.unique(mo) if v >= 202507):
        train, test = mo < m, mo == m
        mean, std = x[train].mean(0), x[train].std(0); std[std == 0] = 1
        zt, ze = (x[train] - mean) / std, (x[test] - mean) / std
        sig = np.zeros(test.sum())
        for side in (1, -1):
            w, b = fit_logistic(zt, (y[train] == side).astype(float))
            thr = np.quantile(zt @ w + b, 1 - top)
            pick = (ze @ w + b) > thr
            sig = np.where(pick & (sig == 0), side, np.where(pick & (sig != 0), 0, sig))
        idx = np.flatnonzero(test)
        order = np.lexsort((mi[idx], dd[idx]))
        for name, signal in (("opportunity", sig),
                             ("random", np.where(RNG.random(len(idx)) < top, RNG.choice([-1, 1], len(idx)), 0))):
            busy = (-1, -1)
            for o in order:
                k = idx[o]; s = signal[o]
                if s == 0 or (dd[k], mi[k]) < busy:
                    continue
                hi, lo, cl = paths[dd[k]]
                t = bracket_detail(hi, lo, cl, mi[k], s, cost)
                t.update(context(days[dd[k]], ROWS[dd[k]], mi[k], s), direction=int(s), strategy=name)
                trades[name].append(t)
                busy = (dd[k], mi[k] + t["hold"])
    return trades


def trend_trades(days):
    m = tm.load_minutes(BARS)
    raw = tm.backtest(m, "tsmom", "limit", 2.0, 3.0, 1.0)
    rows_by_day = {}
    out = []
    for t in raw:
        e, x_, d = t["entry_minute"], t["exit_minute"], t["direction"]
        entry_px = None
        seg_hi, seg_lo = m["high"][e:x_ + 1], m["low"][e:x_ + 1]
        # entry price is the limit; reconstruct from net + exit not stored -> use close at entry as proxy
        entry_px = m["close"][e]
        mfe = float(np.nanmax((seg_hi - entry_px) if d > 0 else (entry_px - seg_lo)))
        mae = float(np.nanmax((entry_px - seg_lo) if d > 0 else (seg_hi - entry_px)))
        k = int(m["day"][e]); day = days[k]
        if k not in rows_by_day:
            rows_by_day[k] = mm.day_rows(day)
        c = context(day, rows_by_day[k], e % 1440, d)
        out.append(dict(gross=t["net_ticks"] + 1.0, net=t["net_ticks"], mfe=max(mfe, 0.0), mae=max(mae, 0.0),
                        exit=t["reason"], hold=int(x_ - e), direction=d, strategy="trend", **c))
    return out


def stats(values, years):
    v = np.asarray(values, float); yrs = np.asarray(years)
    if v.size == 0:
        return None
    boots = RNG.choice(v, (2000, v.size), replace=True).mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    m25 = v[yrs == 2025].mean() if (yrs == 2025).any() else None
    m26 = v[yrs == 2026].mean() if (yrs == 2026).any() else None
    consistent = (m25 is not None and m26 is not None and np.sign(m25) == np.sign(m26)
                  and (lo > 0 or hi < 0))
    return dict(n=int(v.size), mean=round(float(v.mean()), 2), median=round(float(np.median(v)), 2),
                win_rate=round(float((v > 0).mean()), 3), ci95=[round(float(lo), 2), round(float(hi), 2)],
                mean_2025=None if m25 is None else round(float(m25), 2),
                mean_2026=None if m26 is None else round(float(m26), 2), consistent=bool(consistent))


def breakdown(trades):
    rv = np.array([t["rv60"] for t in trades])
    edges = np.quantile(rv, [0.2, 0.4, 0.6, 0.8])
    for t in trades:
        t["vol_quintile"] = int(np.searchsorted(edges, t["rv60"]) + 1)
    out, tests = {}, 0
    for key in ("hour", "weekday", "near_us_news", "vol_quintile", "with_4h_trend", "direction", "exit", "month"):
        groups = defaultdict(list)
        for t in trades:
            groups[str(t[key])].append(t)
        out[key] = {g: stats([t["net"] for t in ts], [t["year"] for t in ts]) for g, ts in sorted(groups.items())}
        tests += len(groups)
    return out, tests


def excursions(trades, cost):
    los = [t for t in trades if t["net"] <= 0]; wins = [t for t in trades if t["net"] > 0]
    return {
        "losers": len(los), "winners": len(wins),
        "losers_that_were_up_5_ticks": round(float(np.mean([t["mfe"] >= 5 for t in los])), 3) if los else None,
        "losers_that_were_up_10_ticks": round(float(np.mean([t["mfe"] >= 10 for t in los])), 3) if los else None,
        "losers_median_mfe": round(float(np.median([t["mfe"] for t in los])), 1) if los else None,
        "winners_median_mae": round(float(np.median([t["mae"] for t in wins])), 1) if wins else None,
        "losers_only_because_of_cost": round(float(np.mean([t["gross"] > 0 for t in los])), 3) if los else None,
        "gross_mean": round(float(np.mean([t["gross"] for t in trades])), 2),
        "net_mean": round(float(np.mean([t["net"] for t in trades])), 2),
        "mfe_hist": np.histogram([t["mfe"] for t in trades], bins=[0, 2, 5, 10, 15, 20, 30, 50, 100, 1000])[0].tolist(),
        "mae_hist": np.histogram([t["mae"] for t in trades], bins=[0, 2, 5, 10, 15, 20, 30, 50, 100, 1000])[0].tolist(),
    }


def main():
    days = mm.load_days(BARS)
    trades = opportunity_and_random(days)
    trades["trend"] = trend_trades(days)
    report = {"generated": "2026-10-16", "period": "2025-07..2026-06 walk-forward test months (trend: full 2025-03..2026-06)",
              "strategies": {}}
    for name, ts in trades.items():
        cost = 1.0 if name == "trend" else 2.6
        by, tests = breakdown(ts)
        report["strategies"][name] = {"overall": stats([t["net"] for t in ts], [t["year"] for t in ts]),
                                      "excursions": excursions(ts, cost), "by": by, "tests_run": tests,
                                      "equity": np.round(np.cumsum([t["net"] for t in ts]), 1).tolist()}
        o, e = report["strategies"][name]["overall"], report["strategies"][name]["excursions"]
        print(f"== {name}: {o}")
        print("   excursions:", {k: v for k, v in e.items() if not k.endswith('hist')})
        cons = [(k, g, s["mean"], s["ci95"], s["mean_2025"], s["mean_2026"]) for k, gs in by.items() for g, s in gs.items()
                if s and s["consistent"] and s["n"] >= 30]
        print(f"   consistent subgroups (n>=30, both years same sign, CI excludes 0; {tests} tests run):", cons)
    Path("data/processed/6e_trade_autopsy_dev_1.json").write_text(json.dumps(report, indent=1))
    with open("data/processed/6e_trade_autopsy_dev_1_trades.csv", "w") as f:
        keys = ["strategy", "date", "hour", "weekday", "direction", "exit", "hold", "gross", "net", "mfe", "mae",
                "near_us_news", "with_4h_trend", "vol_quintile", "year", "month"]
        f.write(",".join(keys) + "\n")
        for ts in trades.values():
            for t in ts:
                f.write(",".join(str(round(t[k], 2) if isinstance(t[k], float) else t[k]) for k in keys) + "\n")


if __name__ == "__main__":
    main()
