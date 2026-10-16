"""6E trend model v2: hourly trend signals with passive limit-order entries (roadmap §8).

The overhaul targets moves of tens of ticks over hours to days, with no high-frequency
trading. It has four parts:

1. **Signal** on hourly bars, decided at each bar close:
   - ``donchian``: price closes beyond the previous N-hour high or low.
   - ``tsmom``: sign of the N-hour return, only when it exceeds k x ATR.
   - ``ensemble``: average vote of three Donchian and three momentum lookbacks.
     It needs a clear majority to enter, and exits when the vote turns neutral or opposite.
2. **Entry**:
   - ``market``: next minute's open plus 1 tick of slippage.
   - ``limit``: a passive limit at the decision close minus an offset, valid for 60 minutes.
     It counts as filled only if price trades *through* the limit by at least 1 tick. That is
     a conservative stand-in for queue position, used until the MBO queue study is done.
     Unfilled entries are missed, never forced.
3. **Risk**: an ATR stop that trails at each hourly close. It is checked on every minute's
   high and low and fills 1 tick worse than the stop, or at the open if price gapped
   through. Signal exits are market orders with 1 tick of slippage. The position is flat
   before each contract roll day and on Fridays from 20:00 UTC (weekend gap risk).
4. **Accounting**: one contract, ticks net of fees (1.0 tick per round trip by default).
   Results are split into April–August and September–December 2025.

Only 2025 bar files are accepted, so the 2026 validation/test/lockbox data stays untouched.
"""

from __future__ import annotations

import argparse
import itertools
import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

TICK = 50_000
MINUTE_NS = 60_000_000_000
RESERVED_FROM = date(2026, 7, 1)  # Jul-Sep 2026 lockbox stays sealed
ROLL_DAYS = (date(2025, 6, 9), date(2025, 9, 8), date(2025, 12, 8), date(2026, 3, 9), date(2026, 6, 8))  # declared research roll
LIMIT_WINDOW_MIN = 60
ATR_BARS = 24


# ---------------------------------------------------------------- data -------------------
def load_minutes(directory: Path):
    """Concatenate 2025 minute bars into continuous arrays (ticks), back-adjusted at rolls.

    Returns dict of arrays over all minutes of all loaded days:
    ts (minute start ns), open/high/low/close (raw contract ticks, untraded minutes carry the
    last close), adj (back-adjustment to add for indicator continuity), date index, flags.
    """
    files = sorted(directory.glob("*.json"))
    days = []
    for path in files:
        day = json.loads(path.read_text())
        d = date.fromisoformat(day["utc_date"])
        if d >= RESERVED_FROM:
            raise ValueError("Reserved lockbox day found; refusing")
        days.append((d, day))
    n = 1440 * len(days)
    ts = np.zeros(n, dtype=np.int64)
    o, h, l, c = (np.full(n, np.nan) for _ in range(4))
    traded = np.zeros(n, dtype=bool)
    day_index = np.zeros(n, dtype=np.int32)
    contract = []
    for k, (d, day) in enumerate(days):
        start = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()) * 10**9
        base = k * 1440
        ts[base : base + 1440] = start + np.arange(1440) * MINUTE_NS
        day_index[base : base + 1440] = k
        contract.append(day["contract"])
        for minute, op, hi, lo, cl, *_ in day["bars"]:
            i = base + (minute - start) // MINUTE_NS
            o[i], h[i], l[i], c[i], traded[i] = op / TICK, hi / TICK, lo / TICK, cl / TICK, True
    for i in range(1, n):
        if not traded[i] and np.isfinite(c[i - 1]):
            o[i] = h[i] = l[i] = c[i] = c[i - 1]
    # Back-adjust earlier contracts by the price gap at each contract change (indicators only).
    adj = np.zeros(n)
    offset = 0.0
    for k in range(len(days) - 1, 0, -1):
        if contract[k] != contract[k - 1]:
            first = np.flatnonzero(traded[k * 1440 : (k + 1) * 1440])
            last = np.flatnonzero(traded[(k - 1) * 1440 : k * 1440])
            if first.size and last.size:
                offset += c[k * 1440 + first[0]] - c[(k - 1) * 1440 + last[-1]]
        adj[(k - 1) * 1440 : k * 1440] = offset
    return {
        "ts": ts, "open": o, "high": h, "low": l, "close": c, "traded": traded,
        "adj": adj, "day": day_index, "dates": [d for d, _ in days], "contract": contract,
    }


def hourly_bars(m: dict) -> dict:
    """Hourly OHLC on back-adjusted prices; only hours with at least one trade."""
    n = len(m["close"])
    hours = n // 60
    rows = []
    for k in range(hours):
        s, e = k * 60, (k + 1) * 60
        t = m["traded"][s:e]
        if not t.any():
            continue
        adj = m["adj"][s]
        rows.append((e - 1,
                     np.nanmax(m["high"][s:e][t]) + adj,
                     np.nanmin(m["low"][s:e][t]) + adj,
                     m["close"][e - 1] + adj))
    a = np.array(rows)
    return {"end_minute": a[:, 0].astype(np.int64), "high": a[:, 1], "low": a[:, 2], "close": a[:, 3]}


def atr(bars: dict, n: int = ATR_BARS) -> np.ndarray:
    h, l, c = bars["high"], bars["low"], bars["close"]
    prev = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))
    out = np.full(len(c), np.nan)
    for i in range(n, len(c)):
        out[i] = tr[i - n + 1 : i + 1].mean()
    return out


# ------------------------------------------------------------- signals -------------------
def donchian(bars: dict, n: int) -> np.ndarray:
    c, h, l = bars["close"], bars["high"], bars["low"]
    sig = np.zeros(len(c))
    for i in range(n, len(c)):
        if c[i] > h[i - n : i].max():
            sig[i] = 1
        elif c[i] < l[i - n : i].min():
            sig[i] = -1
    return sig


def tsmom(bars: dict, n: int, a: np.ndarray, k: float = 1.0) -> np.ndarray:
    c = bars["close"]
    sig = np.zeros(len(c))
    for i in range(n, len(c)):
        move = c[i] - c[i - n]
        if np.isfinite(a[i]) and abs(move) > k * a[i]:
            sig[i] = np.sign(move)
    return sig


def signal_series(bars: dict, kind: str, a: np.ndarray) -> np.ndarray:
    """Target direction per bar in {-1, 0, 1}. Donchian/TSMOM hold until the opposite signal."""
    if kind == "ensemble":
        votes = np.mean(
            [_hold(donchian(bars, n)) for n in (24, 48, 96)]
            + [tsmom(bars, n, a) for n in (24, 72, 120)],
            axis=0,
        )
        return np.where(votes >= 0.5, 1, np.where(votes <= -0.5, -1, 0))
    if kind == "donchian":
        return _hold(donchian(bars, 48))
    if kind == "tsmom":
        return tsmom(bars, 72, a)
    raise ValueError(kind)


def _hold(events: np.ndarray) -> np.ndarray:
    """Turn breakout events into a held state until an opposite breakout."""
    out = np.zeros(len(events))
    state = 0
    for i, e in enumerate(events):
        if e != 0:
            state = e
        out[i] = state
    return out


# ------------------------------------------------------------ backtest -------------------
def backtest(m: dict, kind: str, entry: str, offset: float, stop_k: float, fee: float) -> list[dict]:
    bars = hourly_bars(m)
    a = atr(bars)
    target = signal_series(bars, kind, a)
    o, h, l, c = m["open"], m["high"], m["low"], m["close"]
    n_min = len(c)
    dates = m["dates"]
    roll_eve = {k for k, d in enumerate(dates) if k + 1 < len(dates) and dates[k + 1] in ROLL_DAYS}
    trades = []
    position = None  # dict(direction, entry_price, stop, entry_minute)

    def must_be_flat(i: int) -> bool:
        d = dates[m["day"][i]]
        minute_of_day = i % 1440
        return (m["day"][i] in roll_eve and minute_of_day >= 20 * 60) or (
            d.weekday() == 4 and minute_of_day >= 20 * 60
        ) or d.weekday() == 5

    def close_trade(i: int, price: float, reason: str):
        nonlocal position
        p = position
        net = p["direction"] * (price - p["entry_price"]) - fee
        trades.append({"entry_minute": int(p["entry_minute"]), "exit_minute": int(i),
                       "month": dates[m["day"][i]].year * 100 + dates[m["day"][i]].month, "direction": p["direction"],
                       "net_ticks": float(net), "reason": reason, "entry": p["how"]})
        position = None

    def manage(i_from: int, i_to: int):
        """Walk minutes (i_from, i_to]: stop checks and forced flats."""
        nonlocal position
        for i in range(i_from + 1, min(i_to, n_min - 1) + 1):
            if position is None:
                return
            if not np.isfinite(c[i]):
                continue
            if must_be_flat(i):
                close_trade(i, o[i] - position["direction"], "forced_flat")
                return
            d, stop = position["direction"], position["stop"]
            if (d > 0 and l[i] <= stop) or (d < 0 and h[i] >= stop):
                gap = (d > 0 and o[i] < stop) or (d < 0 and o[i] > stop)
                fill = (o[i] if gap else stop) - d  # 1 tick worse than the stop
                close_trade(i, fill, "stop")
                return

    last_minute = -1
    for b in range(len(bars["close"])):
        i = int(bars["end_minute"][b])  # decision at the close of this hour's last minute
        manage(last_minute, i)
        last_minute = i
        if not np.isfinite(a[b]) or a[b] < 1 or i + 1 >= n_min:
            continue
        want = int(target[b])
        if position is not None:
            d = position["direction"]
            # Trail the stop on the hourly close.
            trail = c[i] - d * stop_k * a[b]
            position["stop"] = max(position["stop"], trail) if d > 0 else min(position["stop"], trail)
            if want != d:  # signal exit at next minute's open with slippage
                close_trade(i + 1, o[i + 1] - d, "signal")
                last_minute = i + 1
        if position is None and want != 0 and not must_be_flat(i + 1):
            if entry == "market":
                price, at = o[i + 1] + want, i + 1
            else:
                limit = c[i] - want * offset
                at = None
                for j in range(i + 1, min(i + 1 + LIMIT_WINDOW_MIN, n_min)):
                    if must_be_flat(j):
                        break
                    if (want > 0 and l[j] <= limit - 1) or (want < 0 and h[j] >= limit + 1):
                        at = j
                        break
                if at is None:
                    continue  # missed passive entry
                price = limit
            position = {"direction": want, "entry_price": price, "how": entry,
                        "stop": price - want * stop_k * a[b], "entry_minute": at}
            manage(at, at)  # nothing more inside the fill minute (conservative ordering)
            last_minute = max(last_minute, at)
    if position is not None:
        close_trade(n_min - 1, c[n_min - 1], "end")
    return trades


def summarize(trades: list[dict]) -> dict:
    if not trades:
        return {"trades": 0}
    v = np.array([t["net_ticks"] for t in trades])
    mo = np.array([t["month"] for t in trades])
    eq = np.cumsum(v)
    gains, losses = v[v > 0].sum(), -v[v < 0].sum()
    first, second = v[mo <= 202512], v[mo >= 202601]
    return {
        "trades": int(v.size),
        "mean_net_ticks": round(float(v.mean()), 2),
        "total_net_ticks": round(float(v.sum()), 1),
        "win_rate": round(float((v > 0).mean()), 3),
        "profit_factor": round(float(gains / losses), 2) if losses else None,
        "max_drawdown_ticks": round(float((np.maximum.accumulate(eq) - eq).max()), 1),
        "y2025_total": round(float(first.sum()), 1),
        "h1_2026_total": round(float(second.sum()), 1),
        "monthly_total": {int(k): round(float(v[mo == k].sum()), 1) for k in np.unique(mo)},
    }


def run_grid(m: dict, fee: float) -> dict:
    results = {}
    for kind, (entry, offset), stop_k in itertools.product(
        ("ensemble", "donchian", "tsmom"),
        (("market", 0.0), ("limit", 0.0), ("limit", 2.0)),
        (2.0, 3.0),
    ):
        name = f"{kind}_{entry}{'' if entry == 'market' else f'-off{offset:g}'}_stop{stop_k:g}atr"
        results[name] = summarize(backtest(m, kind, entry, offset, stop_k, fee))
    return results


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bars", type=Path, default=Path("data/processed/6e_minute_bars_dev_1"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/6e_trend_model_dev_1.json"))
    parser.add_argument("--fee", type=float, default=1.0)
    args = parser.parse_args(argv)
    m = load_minutes(args.bars)
    results = run_grid(m, args.fee)
    args.output.write_text(json.dumps({"fee_ticks_round_trip": args.fee, "results": results}, indent=1))
    for name, r in results.items():
        print(f"{name:34s} n={r['trades']:4d} mean={r.get('mean_net_ticks', 0):+7.2f} "
              f"total={r.get('total_net_ticks', 0):+8.1f} pf={r.get('profit_factor')} "
              f"2025={r.get('y2025_total')} H1-2026={r.get('h1_2026_total')} maxDD={r.get('max_drawdown_ticks')}")


if __name__ == "__main__":
    main()
