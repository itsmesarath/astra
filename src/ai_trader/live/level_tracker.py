"""Live level tracker for 6E: mark sharp-reversal levels, log the order book at every revisit, resolve
hold/break outcomes. The record this produces is what decides whether the book can tell a hold from a
break (see docs/LEVEL_REVISIT_STUDY_20261019.md); nothing here places orders.

Definitions match level_revisit_study: level = swing high/low over +-30 min from which price moved
>= 1 ATR (16 x 15-min bars) away within 60 min; active from 61 min after the swing for 3 days;
revisit = minute whose high/low comes within 0.2 ATR of the level while the close is not yet 0.5 ATR
through it; outcome within 120 min = break (close 0.5 ATR beyond) / hold (close 0.7 ATR back) /
neither. Touches of one level are at least 30 minutes apart; a break retires the level.

Inputs: the live minute store (``data/live/6e_minutes/bars/<date>.json``, prices in nano units) for
history, and today's raw capture files for the book. At each touch minute the tracker records the
ladder (resting size on the far side of the level within 5 ticks, on the near side, 10-level totals),
the aggressor volumes of the last 2 minutes, and the depth add/remove activity within 5 ticks of the
level in the last 2 minutes. Events go to ``logs/live/levels/events.jsonl`` (touch rows, then an
outcome row with the same id). Re-running is idempotent: ids already logged are skipped.
"""

from __future__ import annotations

import argparse
import glob
import json
from collections import deque
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np

from ai_trader.live import capture_minutes as cm
from ai_trader.research import level_revisit_study as lr
from ai_trader.research import six_e_session_pa_study as ps

MINUTE_NS = 60_000_000_000
SWING, SHARP, TOL, EXPIRY, HORIZON = 30, 1.0, 0.2, 3 * 1440, 120
NEAR = 5  # ticks around the level for book features


# ----------------------------------------------------------------------------- history
def load_history(stores: list[Path], first_day: date, last_day: date) -> dict:
    """Minute arrays (ticks) on a midnight-aligned grid from first_day to last_day inclusive.

    ``stores`` are folders holding ``<date>.json`` bar docs (e.g. ``data/live/6e_history_bars`` from
    the NinjaTrader history connector and ``data/live/6e_minutes/bars`` from the live capture); later
    folders win for a day present in several.
    """
    n_days = (last_day - first_day).days + 1
    n = n_days * 1440
    h, l, c = (np.full(n, np.nan) for _ in range(3))
    vol = np.zeros(n)
    tick_nano = None
    for k in range(n_days):
        d = first_day + timedelta(k)
        p = None
        for store in stores:
            q = store / f"{d.isoformat()}.json"
            if q.exists():
                p = q
        if p is None:
            continue
        doc = json.loads(p.read_text())
        tick_nano = doc["tick_nano"]
        day_ns = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()) * 10**9
        for row in doc["bars"]:
            m = int((row[0] - day_ns) // MINUTE_NS)
            if 0 <= m < 1440:
                i = k * 1440 + m
                h[i], l[i], c[i], vol[i] = row[2] / tick_nano, row[3] / tick_nano, row[4] / tick_nano, row[5]
    return {"high": h, "low": l, "close": c, "vol": vol, "first_day": first_day, "n": n, "tick_nano": tick_nano}


def fill_gaps(h, l, c):
    last = np.nan
    for i in range(c.size):
        if np.isfinite(c[i]):
            last = c[i]
        elif np.isfinite(last):
            h[i] = l[i] = c[i] = last


# ----------------------------------------------------------------------------- streaming today's capture
class TodayBook:
    """Ladder + short flow memory, driven by raw capture rows of the current day."""

    def __init__(self):
        self.ladder = cm.Ladder()
        self.tick = None
        self.last_bid = self.last_ask = None
        self.depth_ops = deque()         # (ts, side, op, price, size)
        self.trades = deque()            # (ts, price, size, side)
        self.minutes: dict[int, list] = {}   # minute of day -> [o, h, l, c, vol, buy, sell]
        self.last_ts = 0

    def feed(self, rows):
        for r in rows:
            kind = r.get("kind")
            if kind == "session_start":
                self.tick = Decimal(r["tick_size"])
                continue
            if self.tick is None or kind not in ("bid", "ask", "trade", "depth"):
                continue
            ts = int(r["observed_utc_ns"])
            self.last_ts = max(self.last_ts, ts)
            if kind == "bid":
                self.last_bid = (cm._ticks(r["price"], self.tick), int(r["size"]))
            elif kind == "ask":
                self.last_ask = (cm._ticks(r["price"], self.tick), int(r["size"]))
            elif kind == "depth":
                p = cm._ticks(r["price"], self.tick)
                self.ladder.apply(r["side"], r["operation"], int(r["position"]), p, int(r["size"]))
                self.depth_ops.append((ts, r["side"], r["operation"], p, int(r["size"])))
            elif kind == "trade":
                p, s = cm._ticks(r["price"], self.tick), int(r["size"])
                bb, ba = self.ladder.best("bid") or self.last_bid, self.ladder.best("ask") or self.last_ask
                side = "B" if ba and p >= ba[0] else ("A" if bb and p <= bb[0] else "N")
                self.trades.append((ts, p, s, side))
                m = int((ts % (86400 * 10**9)) // MINUTE_NS)
                b = self.minutes.get(m)
                if b is None:
                    self.minutes[m] = b = [p, p, p, p, 0, 0, 0]
                b[1], b[2], b[3], b[4] = max(b[1], p), min(b[2], p), p, b[4] + s
                if side == "B":
                    b[5] += s
                elif side == "A":
                    b[6] += s
            cutoff = ts - 3 * MINUTE_NS
            while self.depth_ops and self.depth_ops[0][0] < cutoff:
                self.depth_ops.popleft()
            while self.trades and self.trades[0][0] < cutoff:
                self.trades.popleft()

    def features(self, level: int, side: int, now_ns: int) -> dict:
        """Book and flow around a level at this moment. side +1 = resistance (far side = asks)."""
        far, near = ("ask", "bid") if side > 0 else ("bid", "ask")
        lv = self.ladder.levels
        if side > 0:
            far_sz = sum(s for p, s in lv["ask"] if level <= p < level + NEAR)
            near_sz = sum(s for p, s in lv["bid"] if level - NEAR < p <= level)
        else:
            far_sz = sum(s for p, s in lv["bid"] if level - NEAR < p <= level)
            near_sz = sum(s for p, s in lv["ask"] if level <= p < level + NEAR)
        bid_tot, ask_tot = sum(s for _, s in lv["bid"]), sum(s for _, s in lv["ask"])
        t0 = now_ns - 2 * MINUTE_NS
        buy = sum(s for ts, _, s, sd in self.trades if ts >= t0 and sd == "B")
        sell = sum(s for ts, _, s, sd in self.trades if ts >= t0 and sd == "A")
        adds = rems = add_sz = rem_sz = 0
        for ts, sd, op, p, s in self.depth_ops:
            if ts < t0 or sd != far or abs(p - level) >= NEAR:
                continue
            if op == "add":
                adds += 1; add_sz += s
            elif op == "remove":
                rems += 1; rem_sz += s
        bb, ba = self.ladder.best("bid"), self.ladder.best("ask")
        return {"far_size_5": far_sz, "near_size_5": near_sz, "bid_total": bid_tot, "ask_total": ask_tot,
                "book_imbalance": round((bid_tot - ask_tot) / (bid_tot + ask_tot), 3) if bid_tot + ask_tot else None,
                "buy_2m": buy, "sell_2m": sell, "flow_into_level_2m": (buy - sell) * side,
                "far_adds_2m": adds, "far_removes_2m": rems, "far_added_size_2m": add_sz, "far_removed_size_2m": rem_sz,
                "best_bid": bb[0] if bb else None, "best_ask": ba[0] if ba else None,
                "ladder_levels": {"bid": len(lv["bid"]), "ask": len(lv["ask"])}}


# ----------------------------------------------------------------------------- tracker
class LevelTracker:
    def __init__(self, stores: list[Path], capture_glob: str, out: Path, history_days: int = 7):
        self.stores, self.capture_glob, self.out, self.history_days = list(stores), capture_glob, out, history_days
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.logged: dict[str, dict] = {}
        if out.exists():
            for line in out.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    self.logged.setdefault(r["id"], {}).update(r)

    def _append(self, row: dict):
        with self.out.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        self.logged.setdefault(row["id"], {}).update(row)

    def run_once(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        today = now.date()
        first_day = today - timedelta(days=self.history_days)
        hist = load_history(self.stores, first_day, today)
        h, l, c, vol = hist["high"], hist["low"], hist["close"], hist["vol"]
        # today's capture on top (the store may lag; the raw rows are the truth for today)
        book = TodayBook()
        paths = sorted(Path(p) for p in glob.glob(self.capture_glob))
        day_ns = int(datetime(today.year, today.month, today.day, tzinfo=timezone.utc).timestamp()) * 10**9
        if paths:
            rows = [r for r in cm.read_capture(paths) if r.get("kind") == "session_start" or int(r.get("observed_utc_ns", 0)) >= day_ns]
            book.feed(rows)
            base = (today - first_day).days * 1440
            cur_minute = int(((book.last_ts - day_ns) // MINUTE_NS)) if book.last_ts else -1
            for m, b in book.minutes.items():
                if m < cur_minute:   # completed minutes only
                    i = base + m
                    h[i], l[i], c[i], vol[i] = b[1], b[2], b[3], b[4]
        fill_gaps(h, l, c)
        n = hist["n"]
        last_i = max(np.flatnonzero(np.isfinite(c))) if np.isfinite(c).any() else -1
        if last_i < 1440:
            return {"levels": 0, "events": 0, "note": "not enough history"}
        a = ps.atr_minutes(h, l, c)
        mod = ps.minute_of_day(n)
        levels = []
        for lv in lr.find_levels(h, l, c, a, SWING, SHARP):
            if lv[0] + EXPIRY <= last_i - 1440:
                continue
            # equal highs/lows over a few bars are one level, not several
            if levels and levels[-1][1] == lv[1] and levels[-1][2] == lv[2] and lv[0] - levels[-1][0] <= SWING:
                continue
            levels.append(lv)
        new_events = 0
        for i, side, L in levels:
            start = i + 61
            end = min(last_i + 1, i + EXPIRY)
            touches = 0
            j = start
            while j < end:
                if not np.isfinite(a[j]) or a[j] <= 0:
                    j += 1; continue
                tol = TOL * a[j]
                seg = h[j:end] if side > 0 else l[j:end]
                hit = np.flatnonzero(seg >= L - tol) if side > 0 else np.flatnonzero(seg <= L + tol)
                if hit.size == 0:
                    break
                j = j + int(hit[0])
                if side * (c[j] - L) > 0.5 * a[j]:
                    break
                touches += 1
                # ids are keyed by absolute minute, not by grid index
                abs_min_level = (datetime.combine(first_day, datetime.min.time(), timezone.utc) + timedelta(minutes=int(i)))
                abs_min_touch = (datetime.combine(first_day, datetime.min.time(), timezone.utc) + timedelta(minutes=int(j)))
                eid = f"{abs_min_level:%Y%m%d%H%M}{'R' if side > 0 else 'S'}:{abs_min_touch:%Y%m%d%H%M}"
                rec = self.logged.get(eid)
                if rec is None:
                    row = {"id": eid, "kind": "touch", "utc": abs_min_touch.isoformat(), "level_utc": abs_min_level.isoformat(),
                           "side": "resistance" if side > 0 else "support", "level_ticks": int(L), "close_ticks": float(c[j]),
                           "atr_ticks": round(float(a[j]), 2), "touch_n": touches, "age_min": int(j - i),
                           "approach": round(float(side * (c[j] - c[j - 30]) / a[j]), 3) if j >= 30 else None,
                           "trend4": float(side * np.sign(c[j] - c[j - 240])) if j >= 240 else None,
                           "minute_utc": f"{int(mod[j]) // 60:02d}:{int(mod[j]) % 60:02d}"}
                    # the book is only right for the minute that just closed (the deques hold the last
                    # 3 minutes); older touches caught up later are logged without it
                    if j == last_i and abs_min_touch.date() == today and book.tick is not None:
                        row["book"] = book.features(int(L), side, book.last_ts)
                    else:
                        row["book"] = None
                    self._append(row)
                    new_events += 1
                    rec = self.logged[eid]
                if "outcome" not in rec:
                    fc = c[j + 1:j + 1 + HORIZON]
                    brk = np.flatnonzero(side * (fc - L) >= 0.5 * a[j])
                    hold = np.flatnonzero(side * (fc - L) <= -0.7 * a[j])
                    b = brk[0] if brk.size else None
                    hd = hold[0] if hold.size else None
                    outcome = None
                    if b is not None and (hd is None or b < hd):
                        outcome, when = "break", int(b) + 1
                    elif hd is not None:
                        outcome, when = "hold", int(hd) + 1
                    elif j + HORIZON <= last_i:
                        outcome, when = "neither", HORIZON
                    if outcome:
                        self._append({"id": eid, "kind": "outcome", "outcome": outcome, "minutes_to_outcome": when,
                                      "utc": now.isoformat(timespec="seconds")})
                    if outcome == "break":
                        break
                elif rec.get("outcome") == "break":
                    break
                j += 30
        active = [{"level_ticks": int(L), "side": "resistance" if s > 0 else "support", "age_min": int(last_i - i)}
                  for i, s, L in levels if i + EXPIRY > last_i and i + 61 <= last_i]
        return {"levels": len(levels), "active": active[-20:], "events": new_events, "last_minute_index": int(last_i),
                "logged": len(self.logged)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--stores", type=Path, nargs="*", default=[Path("data/live/6e_history_bars"), Path("data/live/6e_minutes/bars")],
                   help="folders of <date>.json bar docs, later ones win")
    p.add_argument("--capture-glob", default=str(Path.home() / "Documents" / "NinjaTrader 8" / "ai-trader-captures" / "ninjatrader-*.jsonl"))
    p.add_argument("--out", type=Path, default=Path("logs/live/levels/events.jsonl"))
    p.add_argument("--history-days", type=int, default=7)
    a = p.parse_args(argv)
    t = LevelTracker(a.stores, a.capture_glob, a.out, a.history_days)
    print(json.dumps(t.run_once(), indent=1))


if __name__ == "__main__":
    main()
