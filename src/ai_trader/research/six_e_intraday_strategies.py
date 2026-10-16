"""Rule-based intraday 6E strategy families on 2025 minute bars (research tier T1).

Families are fixed in advance and every configuration is reported, losers included:

- ``orb``: opening-range breakout around the London or New York open. Entry is a stop
  order 1 tick beyond the range, with the stop on the other side of the range, a target
  of k x range and a time exit.
- ``release``: the 08:30 New York time slot, when most US data is released. Measure the
  move over the first minutes after 08:30, then either follow or fade it, with a fixed
  stop/target and a time exit.
- ``trend_day``: at a fixed New York time, trade in (or against) the direction of the move
  since the London open, holding until a fixed exit time.

Fill model (deliberately conservative):
- Entries cost 1 tick of slippage and exits cost 1 tick, plus fees of 0.6 tick round trip.
  The total is passed as ``cost`` (default 2.6 ticks per round trip).
- A stop or target is checked against each later minute's high/low. If both are touched
  in the same minute, the stop is assumed to come first.
- Times are converted with daylight-saving rules (Europe/London, America/New_York).
- Only 2025 data is accepted.
"""

from __future__ import annotations

import argparse
import itertools
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

TICK = 50_000
MINUTE_NS = 60_000_000_000
RESERVED_FROM = date(2026, 1, 1)
LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")


def load_days(directory: Path) -> list[dict]:
    days = []
    for path in sorted(directory.glob("*.json")):
        day = json.loads(path.read_text())
        if date.fromisoformat(day["utc_date"]) >= RESERVED_FROM:
            raise ValueError("Reserved 2026 day found; refusing")
        days.append(day)
    return days


def day_arrays(day: dict) -> dict:
    """Minute arrays (in ticks) for one UTC day; untraded minutes carry the last close."""
    d = date.fromisoformat(day["utc_date"])
    start = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()) * 10**9
    n = 1440
    o, h, l, c = (np.full(n, np.nan) for _ in range(4))
    traded = np.zeros(n, dtype=bool)
    for minute, op, hi, lo, cl, *_ in day["bars"]:
        i = (minute - start) // MINUTE_NS
        o[i], h[i], l[i], c[i], traded[i] = op / TICK, hi / TICK, lo / TICK, cl / TICK, True
    for i in range(1, n):
        if not traded[i] and np.isfinite(c[i - 1]):
            o[i] = h[i] = l[i] = c[i] = c[i - 1]
    return {"date": d, "open": o, "high": h, "low": l, "close": c, "traded": traded}


def utc_minute(d: date, hour: int, minute: int, zone: ZoneInfo) -> int:
    """Minute-of-UTC-day index for a local wall-clock time on date d."""
    local = datetime(d.year, d.month, d.day, hour, minute, tzinfo=zone)
    utc = local.astimezone(timezone.utc)
    if utc.date() != d:
        raise ValueError("Local time falls on another UTC day")
    return utc.hour * 60 + utc.minute


def run_trade(a: dict, entry_i: int, direction: int, entry_price: float, stop: float,
              target: float | None, exit_i: int, cost: float) -> float | None:
    """Walk minutes after entry; return net ticks or None if data is missing."""
    hi, lo, cl = a["high"], a["low"], a["close"]
    exit_i = min(exit_i, 1439)
    for i in range(entry_i + 1, exit_i + 1):
        if not np.isfinite(cl[i]):
            return None
        stop_hit = lo[i] <= stop if direction > 0 else hi[i] >= stop
        target_hit = target is not None and (hi[i] >= target if direction > 0 else lo[i] <= target)
        if stop_hit:
            return direction * (stop - entry_price) - cost
        if target_hit:
            return direction * (target - entry_price) - cost
    return direction * (cl[exit_i] - entry_price) - cost


def orb(a: dict, zone: ZoneInfo, open_hm: tuple[int, int], range_min: int, target_k: float,
        hold_min: int, cost: float) -> float | None:
    s = utc_minute(a["date"], *open_hm, zone)
    e = s + range_min
    if e + 1 >= 1440 or not a["traded"][s:e].any():
        return None
    hi, lo = np.nanmax(a["high"][s:e]), np.nanmin(a["low"][s:e])
    width = hi - lo
    if not np.isfinite(width) or width < 2:
        return None
    last = min(e + hold_min, 1439)
    for i in range(e, last):
        if a["high"][i] >= hi + 1:  # buy stop at hi + 1 tick
            entry = hi + 1
            target = entry + target_k * width if target_k else None
            return run_trade(a, i, 1, entry, lo, target, last, cost) if i < last else None
        if a["low"][i] <= lo - 1:
            entry = lo - 1
            target = entry - target_k * width if target_k else None
            return run_trade(a, i, -1, entry, hi, target, last, cost) if i < last else None
    return None  # no breakout: no trade


def release(a: dict, measure_min: int, threshold: float, mode: int, stop_ticks: float,
            target_ticks: float, hold_min: int, cost: float) -> float | None:
    s = utc_minute(a["date"], 8, 29, NEW_YORK)  # close of 08:29 = price just before 08:30
    m = s + measure_min
    c = a["close"]
    if m + 1 >= 1440 or not (np.isfinite(c[s]) and np.isfinite(c[m])):
        return None
    move = c[m] - c[s]
    if abs(move) < threshold:
        return None
    direction = int(np.sign(move)) * mode
    entry = c[m]
    return run_trade(a, m, direction, entry, entry - direction * stop_ticks,
                     entry + direction * target_ticks, m + hold_min, cost)


def trend_day(a: dict, decide_hm: tuple[int, int], exit_hm: tuple[int, int], threshold: float,
              mode: int, stop_ticks: float, cost: float) -> float | None:
    start = utc_minute(a["date"], 8, 0, LONDON)
    t = utc_minute(a["date"], *decide_hm, NEW_YORK)
    x = utc_minute(a["date"], *exit_hm, NEW_YORK)
    c = a["close"]
    if not (np.isfinite(c[start]) and np.isfinite(c[t])):
        return None
    move = c[t] - c[start]
    if abs(move) < threshold:
        return None
    direction = int(np.sign(move)) * mode
    return run_trade(a, t, direction, c[t], c[t] - direction * stop_ticks, None, x, cost)


def configurations(cost: float):
    for (name, zone, hm), rng, k, hold in itertools.product(
        (("london", LONDON, (8, 0)), ("newyork", NEW_YORK, (8, 30))),
        (15, 30, 60), (1.0, 2.0, 0.0), (120, 240),
    ):
        yield (f"orb_{name}_r{rng}_t{k:g}_h{hold}",
               lambda a, z=zone, h=hm, r=rng, kk=k, hd=hold: orb(a, z, h, r, kk, hd, cost))
    for meas, thr, mode, (stop, tgt), hold in itertools.product(
        (2, 5), (4, 8), (1, -1), ((8, 16), (12, 24)), (30, 90),
    ):
        tag = "follow" if mode > 0 else "fade"
        yield (f"release_m{meas}_x{thr}_{tag}_s{stop}_t{tgt}_h{hold}",
               lambda a, me=meas, th=thr, mo=mode, st=stop, tg=tgt, hd=hold:
               release(a, me, th, mo, st, tg, hd, cost))
    for (dh, xh), thr, mode, stop in itertools.product(
        (((9, 30), (15, 30)), ((10, 0), (16, 0))), (10, 20), (1, -1), (15, 30),
    ):
        tag = "follow" if mode > 0 else "fade"
        yield (f"trend_{dh[0]:02d}{dh[1]:02d}_x{thr}_{tag}_s{stop}",
               lambda a, d=dh, x=xh, th=thr, mo=mode, st=stop:
               trend_day(a, d, x, th, mo, st, cost))


def summarize(pnl: list[tuple[int, float]]) -> dict:
    """pnl: list of (month, net ticks)."""
    if not pnl:
        return {"trades": 0}
    months = np.array([m for m, _ in pnl])
    values = np.array([v for _, v in pnl])
    equity = np.cumsum(values)
    first, second = values[months <= 8], values[months >= 9]
    gains, losses = values[values > 0].sum(), -values[values < 0].sum()
    return {
        "trades": int(values.size),
        "mean_net_ticks": round(float(values.mean()), 3),
        "total_net_ticks": round(float(values.sum()), 1),
        "win_rate": round(float((values > 0).mean()), 3),
        "profit_factor": round(float(gains / losses), 3) if losses else None,
        "max_drawdown_ticks": round(float((np.maximum.accumulate(equity) - equity).max()), 1),
        "apr_aug_mean": round(float(first.mean()), 3) if first.size else None,
        "apr_aug_trades": int(first.size),
        "sep_dec_mean": round(float(second.mean()), 3) if second.size else None,
        "sep_dec_trades": int(second.size),
        "positive_months": int(sum(values[months == m].sum() > 0 for m in np.unique(months))),
        "months": int(np.unique(months).size),
    }


def evaluate(days: list[dict], cost: float) -> dict:
    arrays = [day_arrays(d) for d in days]
    arrays = [a for a in arrays if a["date"].weekday() < 5]  # weekday sessions only
    results = {}
    for name, rule in configurations(cost):
        pnl = []
        for a in arrays:
            try:
                value = rule(a)
            except ValueError:
                value = None
            if value is not None:
                pnl.append((a["date"].month, float(value)))
        results[name] = summarize(pnl)
    return results


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bars", type=Path, default=Path("data/processed/6e_minute_bars_2025_1"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/6e_intraday_strategies_2025_1.json"))
    parser.add_argument("--cost", type=float, default=2.6)
    args = parser.parse_args(argv)
    days = load_days(args.bars)
    results = evaluate(days, args.cost)
    args.output.write_text(json.dumps({"cost_ticks": args.cost, "days": len(days),
                                       "configurations": len(results), "results": results}, indent=1))
    ranked = sorted(((v.get("mean_net_ticks", -99), k, v) for k, v in results.items() if v["trades"] >= 40),
                    reverse=True)
    print(f"{len(results)} configurations, cost {args.cost} ticks; top 15 by mean net ticks:")
    for mean, name, v in ranked[:15]:
        print(f"{name:45s} n={v['trades']:4d} mean={mean:+.2f} pf={v['profit_factor']} "
              f"AprAug={v['apr_aug_mean']} SepDec={v['sep_dec_mean']} +months={v['positive_months']}/{v['months']}")
    positive = sum(1 for m, _, _ in ranked if m > 0)
    print(f"{positive} of {len(ranked)} configurations with >=40 trades are net positive")


if __name__ == "__main__":
    main()
