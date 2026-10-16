"""Convert NinjaTrader capture files (ai_trader_market_capture_v1 JSONL, written by
``AiTraderSixEDataCapture``) into the per-day minute stores the research code already reads:

- ``<out>/bars/<date>.json``  — same schema as ``six_e_horizon_census`` bars
  (utc_date, contract, tick_nano, bars [minute_ns, open, high, low, close, volume, trades,
  buy_volume, sell_volume] with prices in nano units = ticks x tick_nano).
- ``<out>/book/<date>.json`` — same schema as ``six_e_book_minutes`` (bid, ask, sizes, depth
  within 5 ticks, min_ask/max_bid, aggressor volumes, trades, big_trades, tpx).

What the live feed cannot give and how it is handled:
- No aggressor flag: a trade at or above the current ask counts as buyer-initiated, at or
  below the bid as seller-initiated, otherwise volume only.
- Depth arrives as 10-level ladder operations (add/update/remove at a position), not as
  orders, so order-flow imbalance, adds and cancels are written as 0. The depth filter used by
  the candidate rule needs only ``bid_d5``/``ask_d5``, which the ladder gives directly.
- Prices are decimal strings; they are converted to integer ticks with the session's tick_size.

Several files may cover one UTC day (rotation); they are merged in observation order.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from ai_trader.research.six_e_horizon_census import minute_bars

MINUTE_NS = 60_000_000_000
DEPTH = 5
BIG = 25


class Ladder:
    """Ten-level price ladder per side maintained from NinjaTrader depth operations."""

    def __init__(self):
        self.levels = {"bid": [], "ask": []}  # list of [price_ticks, size], best first

    def apply(self, side: str, operation: str, position: int, price: int, size: int) -> None:
        lv = self.levels[side]
        if operation == "add":
            if 0 <= position <= len(lv):
                lv.insert(position, [price, size])
        elif operation == "update":
            if 0 <= position < len(lv):
                lv[position] = [price, size]
        elif operation == "remove":
            if 0 <= position < len(lv):
                lv.pop(position)
        else:
            raise ValueError(f"unknown depth operation {operation!r}")

    def best(self, side: str):
        lv = self.levels[side]
        return lv[0] if lv else None

    def within(self, side: str) -> int:
        """Total size within DEPTH ticks of the best on that side."""
        lv = self.levels[side]
        if not lv:
            return 0
        best = lv[0][0]
        if side == "bid":
            return sum(s for p, s in lv if best - DEPTH < p <= best)
        return sum(s for p, s in lv if best <= p < best + DEPTH)


def _ticks(text: str, tick: Decimal) -> int:
    return int((Decimal(text) / tick).to_integral_value())


def read_capture(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        with path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    rows.sort(key=lambda r: (r["observed_utc_ns"], r.get("sequence", 0)))
    return rows


def convert(rows: list[dict]) -> tuple[dict, dict]:
    """Return ({date: bars_doc}, {date: book_doc}) from ordered capture records."""
    tick = None
    tick_nano = None
    market = instrument = None
    ladder = Ladder()
    last_bid = last_ask = None  # (ticks, size)
    trades_by_day = defaultdict(list)
    minutes_by_day: dict[str, dict] = defaultdict(dict)
    cur_key = None
    acc = None

    def new_acc():
        return {"buy_vol": 0, "sell_vol": 0, "trades": 0, "big_trades": 0, "ofi": 0,
                "adds_b": 0, "adds_a": 0, "cxl_b": 0, "cxl_a": 0, "min_ask": None, "max_bid": None, "tpx": {}}

    def close_minute():
        if cur_key is None:
            return
        day, minute = cur_key
        bb, ba = ladder.best("bid") or last_bid, ladder.best("ask") or last_ask
        row = dict(acc)
        row["bid"], row["ask"] = (bb[0] if bb else None), (ba[0] if ba else None)
        row["bid_sz"], row["ask_sz"] = (bb[1] if bb else 0), (ba[1] if ba else 0)
        row["bid_d5"], row["ask_d5"] = ladder.within("bid"), ladder.within("ask")
        row["tpx"] = {str(p): v for p, v in row["tpx"].items()}
        minutes_by_day[day][str(minute)] = row

    def note_quotes():
        bb, ba = ladder.best("bid") or last_bid, ladder.best("ask") or last_ask
        if ba:
            acc["min_ask"] = ba[0] if acc["min_ask"] is None else min(acc["min_ask"], ba[0])
        if bb:
            acc["max_bid"] = bb[0] if acc["max_bid"] is None else max(acc["max_bid"], bb[0])

    for r in rows:
        kind = r["kind"]
        if kind == "session_start":
            tick = Decimal(r["tick_size"])
            tick_nano = int(tick * 10**9)
            market, instrument = r["market"], r["instrument"]
            continue
        if kind not in ("bid", "ask", "trade", "depth", "quote") or tick is None:
            continue
        ts = int(r["observed_utc_ns"])
        day = datetime.fromtimestamp(ts // 10**9, tz=timezone.utc).date().isoformat()
        day_start = int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()) * 10**9
        minute = (ts - day_start) // MINUTE_NS
        if (day, minute) != cur_key:
            close_minute()
            cur_key, acc = (day, minute), new_acc()
        if kind == "bid":
            last_bid = (_ticks(r["price"], tick), int(r["size"]))
        elif kind == "ask":
            last_ask = (_ticks(r["price"], tick), int(r["size"]))
        elif kind == "quote":
            last_bid = (_ticks(r["bid"], tick), last_bid[1] if last_bid else 0)
            last_ask = (_ticks(r["ask"], tick), last_ask[1] if last_ask else 0)
        elif kind == "depth":
            ladder.apply(r["side"], r["operation"], int(r["position"]), _ticks(r["price"], tick), int(r["size"]))
        elif kind == "trade":
            p, s = _ticks(r["price"], tick), int(r["size"])
            bb, ba = ladder.best("bid") or last_bid, ladder.best("ask") or last_ask
            side = "B" if ba and p >= ba[0] else ("A" if bb and p <= bb[0] else "N")
            trades_by_day[day].append((ts, p * tick_nano, s, side))
            acc["trades"] += 1
            if s >= BIG:
                acc["big_trades"] += 1
            slot = acc["tpx"].setdefault(p, [0, 0])
            if side == "B":
                acc["buy_vol"] += s; slot[0] += s
            elif side == "A":
                acc["sell_vol"] += s; slot[1] += s
        note_quotes()
    close_minute()
    if tick is None:
        raise ValueError("No session_start record; cannot convert")
    bars_docs, book_docs = {}, {}
    for day in sorted(set(trades_by_day) | set(minutes_by_day)):
        trades = sorted(trades_by_day.get(day, []))
        bars_docs[day] = {
            "utc_date": day, "contract": instrument, "market": market, "source": "ninjatrader_capture",
            "trade_count": len(trades), "tick_nano": tick_nano,
            "columns": ["minute_ns", "open", "high", "low", "close", "volume", "trades", "buy_volume", "sell_volume"],
            "bars": minute_bars(trades),
        }
        book_docs[day] = {"utc_date": day, "contract": instrument, "source": "ninjatrader_capture",
                          "minutes": dict(sorted(minutes_by_day.get(day, {}).items(), key=lambda kv: int(kv[0])))}
    return bars_docs, book_docs


def write_docs(bars_docs: dict, book_docs: dict, out: Path) -> list[str]:
    written = []
    for sub, docs in (("bars", bars_docs), ("book", book_docs)):
        (out / sub).mkdir(parents=True, exist_ok=True)
        for day, doc in docs.items():
            target = out / sub / f"{day}.json"
            tmp = target.with_suffix(".partial")
            tmp.write_text(json.dumps(doc, separators=(",", ":")))
            tmp.replace(target)
            written.append(str(target))
    return written


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("captures", nargs="+", help="capture .jsonl files or globs; all are merged so days split across rotated files stay whole")
    p.add_argument("--output", type=Path, default=Path("data/live/6e_minutes"))
    a = p.parse_args(argv)
    import glob
    paths = sorted({Path(q) for c in a.captures for q in (glob.glob(str(c)) or [str(c)])})
    missing = [q for q in paths if not q.exists()]
    if missing:
        raise SystemExit(f"capture files not found: {missing}")
    print(f"{len(paths)} capture files")
    rows = read_capture(paths)
    bars_docs, book_docs = convert(rows)
    for path in write_docs(bars_docs, book_docs, a.output):
        print(path)


if __name__ == "__main__":
    main()
