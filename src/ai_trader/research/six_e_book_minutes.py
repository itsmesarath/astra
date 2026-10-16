"""Rebuild the 6E limit order book from Databento MBO and write minute-level book features.

Why: every earlier model used trade prices and volumes only. The MBO archive also holds
every resting order, so this pass adds what the book looked like at each minute close and
what flowed through it during the minute. It also records what a passive limit order
would have faced, so limit-order entries can be simulated with real queue positions.

Per minute (UTC day, 1440 slots, only minutes with any book event are written):
- ``bid``/``ask``: best prices in ticks at minute close; ``bid_sz``/``ask_sz`` their sizes.
- ``bid_d5``/``ask_d5``: total resting size within 5 ticks of the best on each side.
- ``min_ask``/``max_bid``: extremes of the best quotes during the minute (used to detect
  a limit order being traded through).
- ``buy_vol``/``sell_vol``: aggressor volume (side B = buyer lifted the ask).
- ``trades``, ``big_trades`` (size >= 25).
- ``ofi``: order-flow imbalance at the best quotes over the minute (Cont et al. style:
  bid-side additions minus ask-side additions, in contracts, from best-level changes).
- ``adds_b``/``adds_a``/``cxl_b``/``cxl_a``: contracts added to / cancelled from within
  5 ticks of the best on each side during the minute.
- ``tpx``: traded volume by price during the minute as {price_ticks: [buy_vol, sell_vol]},
  for queue-position fill simulation.

Book handling: R clears; A adds; C removes the order; M replaces price/size; F reduces the
resting order by the filled size; T is a trade print (volume only). Snapshot records
(F_SNAPSHOT) are applied like adds. Dates on or after 2026-07-01 (the lockbox) are refused.
"""

from __future__ import annotations

import argparse
import heapq
import json
import os
import zipfile
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from ai_trader.research.six_e_horizon_census import (TICK_NANO, contract_for,
                                                     development_members)

MINUTE_NS = 60_000_000_000
DEPTH = 5
BIG = 25


class Book:
    def __init__(self):
        self.orders = {}  # order_id -> [side, price_ticks, size]
        self.levels = {"B": {}, "A": {}}  # side -> {price: size}
        self.heap = {"B": [], "A": []}  # lazy heaps for best lookup (max for B, min for A)

    def clear(self):
        self.__init__()

    def _touch(self, side, price):
        heapq.heappush(self.heap[side], -price if side == "B" else price)

    def best(self, side):
        lv, h = self.levels[side], self.heap[side]
        while h:
            p = -h[0] if side == "B" else h[0]
            if lv.get(p, 0) > 0:
                return p
            heapq.heappop(h)
        return None

    def add(self, oid, side, price, size):
        self.orders[oid] = [side, price, size]
        lv = self.levels[side]
        if lv.get(price, 0) <= 0:
            self._touch(side, price)
        lv[price] = lv.get(price, 0) + size

    def remove(self, oid):
        o = self.orders.pop(oid, None)
        if o is None:
            return None
        side, price, size = o
        self.levels[side][price] -= size
        return o

    def reduce(self, oid, qty):
        o = self.orders.get(oid)
        if o is None:
            return None
        take = min(qty, o[2])
        o[2] -= take
        self.levels[o[0]][o[1]] -= take
        if o[2] <= 0:
            del self.orders[oid]
        return (o[0], o[1], take)

    def depth(self, side, best):
        lv = self.levels[side]
        rng = range(best - DEPTH + 1, best + 1) if side == "B" else range(best, best + DEPTH)
        return sum(max(lv.get(p, 0), 0) for p in rng)


def decode_day(day, path, name) -> dict:
    import databento_dbn as dbn
    import zstandard as zstd

    contract = contract_for(day)
    start = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()) * 10**9
    end = start + 86_400 * 10**9
    book = Book()
    iid = None
    minutes = {}
    cur = None  # current minute index
    acc = None  # accumulator for the current minute

    def new_acc():
        return {"buy_vol": 0, "sell_vol": 0, "trades": 0, "big_trades": 0, "ofi": 0,
                "adds_b": 0, "adds_a": 0, "cxl_b": 0, "cxl_a": 0,
                "min_ask": None, "max_bid": None, "tpx": {}}

    def close_minute():
        nonlocal acc
        if cur is None:
            return
        bb, ba = book.best("B"), book.best("A")
        row = dict(acc)
        row["bid"], row["ask"] = bb, ba
        row["bid_sz"] = book.levels["B"].get(bb, 0) if bb is not None else 0
        row["ask_sz"] = book.levels["A"].get(ba, 0) if ba is not None else 0
        row["bid_d5"] = book.depth("B", bb) if bb is not None else 0
        row["ask_d5"] = book.depth("A", ba) if ba is not None else 0
        row["tpx"] = {str(p): v for p, v in row["tpx"].items()}
        minutes[cur] = row

    def note_quotes():
        bb, ba = book.best("B"), book.best("A")
        if ba is not None:
            acc["min_ask"] = ba if acc["min_ask"] is None else min(acc["min_ask"], ba)
        if bb is not None:
            acc["max_bid"] = bb if acc["max_bid"] is None else max(acc["max_bid"], bb)

    decoder = dbn.DBNDecoder()

    def consume(item):
        nonlocal iid, cur, acc
        if isinstance(item, dbn.Metadata):
            active = [m for m in item.mappings.get(contract, []) if m["start_date"] <= day < m["end_date"]]
            if len(active) != 1:
                raise ValueError(f"No unique mapping for {contract} on {day}")
            iid = int(active[0]["symbol"])
            return
        if not isinstance(item, dbn.MBOMsg) or item.instrument_id != iid:
            return
        ts = item.ts_recv
        if not start <= ts < end:
            return
        m = (ts - start) // MINUTE_NS
        if m != cur:
            close_minute()
            cur, acc = m, new_acc()
        a, s = str(item.action), str(item.side)
        price = item.price // TICK_NANO if item.price > 0 else None
        bb, ba = book.best("B"), book.best("A")
        if a == "R":
            book.clear()
        elif a == "A":
            if s in ("B", "A") and price is not None:
                book.add(item.order_id, s, price, item.size)
                if s == "B" and bb is not None and price >= bb - DEPTH + 1:
                    acc["adds_b"] += item.size
                    if price >= bb:
                        acc["ofi"] += item.size
                elif s == "A" and ba is not None and price <= ba + DEPTH - 1:
                    acc["adds_a"] += item.size
                    if price <= ba:
                        acc["ofi"] -= item.size
        elif a == "C":
            o = book.remove(item.order_id)
            if o is not None:
                side, p, size = o
                if side == "B" and bb is not None and p >= bb - DEPTH + 1:
                    acc["cxl_b"] += size
                    if p >= bb:
                        acc["ofi"] -= size
                elif side == "A" and ba is not None and p <= ba + DEPTH - 1:
                    acc["cxl_a"] += size
                    if p <= ba:
                        acc["ofi"] += size
        elif a == "M":
            o = book.remove(item.order_id)
            if s in ("B", "A") and price is not None:
                book.add(item.order_id, s, price, item.size)
        elif a == "F":
            book.reduce(item.order_id, item.size)
        elif a == "T":
            if price is not None and item.size > 0:
                acc["trades"] += 1
                if item.size >= BIG:
                    acc["big_trades"] += 1
                slot = acc["tpx"].setdefault(price, [0, 0])
                if s == "B":
                    acc["buy_vol"] += item.size
                    slot[0] += item.size
                elif s == "A":
                    acc["sell_vol"] += item.size
                    slot[1] += item.size
        note_quotes()

    with zipfile.ZipFile(path) as archive, archive.open(name) as compressed:
        decompressor = zstd.ZstdDecompressor().decompressobj()
        while block := compressed.read(1 << 20):
            while block:
                decoded = decompressor.decompress(block)
                for item in decoder.write_and_decode(decoded):
                    consume(item)
                if decompressor.eof:
                    block = decompressor.unused_data
                    decompressor = zstd.ZstdDecompressor().decompressobj()
                else:
                    block = b""
        for item in decoder.decode():
            consume(item)
    close_minute()
    if iid is None:
        raise ValueError(f"No metadata in {name}")
    return {"utc_date": day.isoformat(), "contract": contract, "instrument_id": iid,
            "minutes": {str(k): v for k, v in sorted(minutes.items())}}


def _job(args):
    day, path, name, output = args
    target = output / f"{day.isoformat()}.json"
    if target.exists():
        return day.isoformat(), "skipped"
    try:
        result = decode_day(day, Path(path), name)
    except Exception as exc:
        (output / f"{day.isoformat()}.error.txt").write_text(f"{type(exc).__name__}: {exc}\n")
        return day.isoformat(), "error"
    partial = target.with_suffix(".partial")
    partial.write_text(json.dumps(result, separators=(",", ":")))
    partial.replace(target)
    return day.isoformat(), f"ok {len(result['minutes'])} minutes"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--downloads", type=Path, default=Path("downloads"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/6e_book_minutes_dev_1"))
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    jobs = [(d, str(p), n, args.output) for d, p, n in development_members(args.downloads)]
    print(f"{len(jobs)} days; writing to {args.output}", flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for day, status in pool.map(_job, jobs):
            print(day, status, flush=True)


if __name__ == "__main__":
    main()
