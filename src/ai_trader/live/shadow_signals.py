"""Shadow-mode evaluation of the candidate rule on the live minute store (no orders).

Rule (from docs/6E_SESSION_PRICE_ACTION_STUDY_20261016.md): failed-breakout reversal in the
direction of the 4-hour change, London window 07:00-09:00 UTC, taken only when resting depth
within 5 ticks of the best on both sides is at least the trailing 60-minute median; stop
1.5 x ATR (15-minute bars over 4 hours), target 3 x stop, 240-minute hold, flat by 20:59 UTC;
market-like entry with the IC Markets cost model (1.8 ticks round trip on a 6E-equivalent).

Inputs: ``<store>/bars/*.json`` and ``<store>/book/*.json`` written by ``capture_minutes``;
optionally the historical development stores first, for indicator warm-up (ATR needs 4 hours,
the trend 4 hours, the depth median 60 minutes). Days inside the sealed lockbox
(2026-07-01 .. 2026-09-30) are refused. Output: every decision (would-be entry with stop,
target, ATR, depth and its median) and the simulated outcome of closed trades, appended to
``logs/shadow/decisions.jsonl`` and a running tally printed.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

from ai_trader.research import six_e_book_strategy as bs
from ai_trader.research import six_e_session_pa_study as ps

LOCKBOX = (date(2026, 7, 1), date(2026, 10, 1))
RULE = dict(lookback=240, bounce=15, window=[(7 * 60, 9 * 60)], depth_mult=1.0,
            stop_k=1.5, rr=3.0, hold=240, cost=1.8)
TICK = 50_000


def load_store(bars_dir: Path, book_dir: Path | None, days_seen: dict) -> None:
    for path in sorted(bars_dir.glob("*.json")):
        d = date.fromisoformat(path.stem)
        if LOCKBOX[0] <= d < LOCKBOX[1]:
            raise ValueError(f"{d} is inside the sealed lockbox")
        doc = json.loads(path.read_text())
        book = None
        if book_dir is not None and (book_dir / path.name).exists():
            book = json.loads((book_dir / path.name).read_text())
        days_seen[d] = (doc, book)


def arrays(days: dict):
    dates = sorted(days)
    first = dates[0]
    n_days = (dates[-1] - first).days + 1
    n = n_days * 1440
    h, l, c = (np.full(n, np.nan) for _ in range(3))
    depth = np.full(n, np.nan)
    books = [None] * n_days
    for d in dates:
        doc, book = days[d]
        k = (d - first).days
        base = k * 1440
        start = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()) * 10**9
        tick = doc.get("tick_nano", TICK)
        for minute, _o, hi, lo, cl, *_ in doc["bars"]:
            i = base + (minute - start) // 60_000_000_000
            h[i], l[i], c[i] = hi / tick, lo / tick, cl / tick
        if book:
            b = bs.book_arrays(book)
            books[k] = b
            depth[base:base + 1440] = b["bid_d5"] + b["ask_d5"]
    for i in range(1, n):
        if not np.isfinite(c[i]) and np.isfinite(c[i - 1]):
            h[i] = l[i] = c[i] = c[i - 1]
    from datetime import timedelta
    return {"high": h, "low": l, "close": c, "depth": depth, "books": books,
            "dates": [first + timedelta(k) for k in range(n_days)]}


def decisions(m: dict, since: date | None = None) -> list[dict]:
    c, h, l = m["close"], m["high"], m["low"]
    n = c.size
    ps._ADJ = np.zeros(n)
    ps._MONTHS = np.array([d.year * 100 + d.month for d in m["dates"]])
    mod = ps.minute_of_day(n)
    dayk = np.repeat(np.arange(len(m["dates"])), 1440)
    a = ps.atr_minutes(h, l, c)
    trend4 = np.sign(c - np.concatenate([np.full(240, np.nan), c[:-240]]))
    sig = ps.pattern_signals(c, h, l, a, "reversal", lookback=RULE["lookback"], bounce=RULE["bounce"])
    sig[sig != trend4] = 0
    ok = np.zeros(n, dtype=bool)
    for lo, hi in RULE["window"]:
        ok |= (mod >= lo) & (mod < hi)
    sig[~ok] = 0
    sig[~np.isfinite(c)] = 0
    from numpy.lib.stride_tricks import sliding_window_view
    med = np.full(n, np.nan)
    med[60:] = np.nanmedian(sliding_window_view(m["depth"], 60)[:-1], axis=1)
    depth_ok = m["depth"] >= RULE["depth_mult"] * med
    trades = ps.simulate(c, h, l, a, mod, dayk, m["books"], sig, "market", RULE["stop_k"], RULE["rr"],
                         RULE["hold"], False, depth_ok, cost=RULE["cost"])
    out = []
    for t in trades:
        d = m["dates"][int(dayk[t["i"]])]
        if since and d < since:
            continue
        i = t["i"]
        out.append({"date": d.isoformat(), "minute_utc": f"{int(mod[i]) // 60:02d}:{int(mod[i]) % 60:02d}",
                    "side": "long" if t["d"] > 0 else "short", "entry_ticks": float(c[i]),
                    "stop_ticks": round(float(t["stop"]), 1), "target_ticks": round(float(t["stop"] * RULE["rr"]), 1),
                    "atr": round(float(a[i]), 1), "depth": float(m["depth"][i]), "depth_median": float(med[i]),
                    "exit": t["why"], "exit_minute": int(mod[t["exit"]]), "net_ticks": round(t["net"], 2),
                    "open": bool(t["exit"] >= n - 1 or not np.isfinite(c[min(t["exit"] + 1, n - 1)]))})
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--store", type=Path, default=Path("data/live/6e_minutes"))
    p.add_argument("--warmup-bars", type=Path, default=None, help="historical bars dir for indicator warm-up")
    p.add_argument("--warmup-book", type=Path, default=None)
    p.add_argument("--since", type=date.fromisoformat, default=None, help="report decisions from this date")
    p.add_argument("--log", type=Path, default=Path("logs/shadow/decisions.jsonl"))
    a = p.parse_args(argv)
    days: dict = {}
    if a.warmup_bars:
        load_store(a.warmup_bars, a.warmup_book, days)
    load_store(a.store / "bars", a.store / "book", days)
    if not days:
        print("no minute data in the store yet")
        return
    m = arrays(days)
    out = decisions(m, a.since)
    a.log.parent.mkdir(parents=True, exist_ok=True)
    with a.log.open("a") as fh:
        for row in out:
            fh.write(json.dumps({"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), **row}) + "\n")
    closed = [r for r in out if not r["open"]]
    print(f"{len(out)} decisions ({len(closed)} closed) from {min(days)} to {max(days)}")
    for r in out[-10:]:
        print(" ", r)
    if closed:
        net = np.array([r["net_ticks"] for r in closed])
        print(f"tally: {net.size} closed, mean {net.mean():+.2f} ticks, total {net.sum():+.1f}, win rate {(net > 0).mean():.2f}")


if __name__ == "__main__":
    main()
