"""Python side of the NinjaTrader history connector (see integrations/ninjatrader/AiTraderHistoryConnector.cs).

- ``request``: write a request file the add-on fulfils (instrument, from, to, tick|minute).
- ``status``: list pending / done / error requests and the day files present.
- ``convert``: turn the add-on's tick JSONL day files into the research bar store
  (``six_e_horizon_census`` schema, prices in nano units, aggressor from the bid/ask stamped on
  each trade: at/above ask = buyer, at/below bid = seller), re-bucketed by UTC day.

Lockbox: days inside 2026-07-01 .. 2026-09-30 are refused by ``convert`` unless
``--allow-lockbox`` is given explicitly (final test only).
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from ai_trader.research.six_e_horizon_census import minute_bars

LOCKBOX = (date(2026, 7, 1), date(2026, 10, 1))


def user_dir() -> Path:
    env = os.environ.get("NINJATRADER_USER_DIR")
    if env:
        return Path(env)
    return Path.home() / "Documents" / "NinjaTrader 8"


def write_request(folder: Path, instrument: str, start: date, end: date, kind: str = "tick") -> Path:
    if kind not in ("tick", "minute"):
        raise ValueError("kind must be tick or minute")
    if end < start:
        raise ValueError("end before start")
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{instrument.replace(' ', '_')}_{kind}.json"
    path = folder / name
    path.write_text(json.dumps({"instrument": instrument, "from": start.isoformat(), "to": end.isoformat(),
                                "type": kind}, indent=1))
    return path


def status(base: Path) -> dict:
    req = base / "ai-trader-requests"
    hist = base / "ai-trader-history"
    out = {"pending": sorted(p.name for p in req.glob("*.json")) if req.exists() else [],
           "done": sorted(p.name for p in req.glob("*.done")) if req.exists() else [],
           "error": sorted(p.name for p in req.glob("*.error")) if req.exists() else [],
           "history": {}}
    if hist.exists():
        for folder in sorted(p for p in hist.iterdir() if p.is_dir()):
            files = sorted(folder.glob("*.jsonl"))
            out["history"][folder.name] = {"files": len(files),
                                           "first": files[0].name if files else None, "last": files[-1].name if files else None}
    return out


def read_ticks(path: Path):
    """Yield (ts_ns, price_nano, size, aggressor) from one tick day file; return header via StopIteration value."""
    header = None
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("record") == "header":
                header = row
                continue
            p, b, a = Decimal(str(row["p"])), Decimal(str(row.get("b", "0"))), Decimal(str(row.get("a", "0")))
            side = "B" if a > 0 and p >= a else ("A" if b > 0 and p <= b else "N")
            yield int(row["t"]), int(p * 10**9), int(row["v"]), side
    return header


def convert(history_dir: Path, instrument_folder: str, out: Path, allow_lockbox: bool = False) -> list[Path]:
    folder = history_dir / instrument_folder
    files = sorted(folder.glob("tick_*.jsonl"))
    if not files:
        raise SystemExit(f"no tick files in {folder}")
    tick_size = None
    by_day = defaultdict(list)
    for path in files:
        gen = read_ticks(path)
        header = None
        while True:
            try:
                ts, p, s, side = next(gen)
            except StopIteration as stop:
                header = stop.value
                break
            d = datetime.fromtimestamp(ts // 10**9, tz=timezone.utc).date()
            by_day[d].append((ts, p, s, side))
        if header and header.get("tick_size"):
            tick_size = header["tick_size"]
    tick_nano = int(Decimal(tick_size) * 10**9) if tick_size else 50_000
    out.mkdir(parents=True, exist_ok=True)
    written = []
    days = sorted(by_day)
    # The first and last UTC days are usually partial (local-day requests); drop the edges unless they are the only days.
    for d in days:
        if LOCKBOX[0] <= d < LOCKBOX[1] and not allow_lockbox:
            continue
        trades = sorted(by_day[d])
        doc = {"utc_date": d.isoformat(), "contract": instrument_folder.replace("_", " "), "source": "ninjatrader_history",
               "trade_count": len(trades), "tick_nano": tick_nano,
               "columns": ["minute_ns", "open", "high", "low", "close", "volume", "trades", "buy_volume", "sell_volume"],
               "bars": minute_bars(trades), "partial_edge_day": d in (days[0], days[-1])}
        target = out / f"{d.isoformat()}.json"
        tmp = target.with_suffix(".partial")
        tmp.write_text(json.dumps(doc, separators=(",", ":")))
        tmp.replace(target)
        written.append(target)
    return written


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("request")
    r.add_argument("instrument", help='e.g. "6E 12-26"')
    r.add_argument("start", type=date.fromisoformat)
    r.add_argument("end", type=date.fromisoformat)
    r.add_argument("--kind", default="tick", choices=["tick", "minute"])
    r.add_argument("--base", type=Path, default=None, help="NinjaTrader user directory")
    s = sub.add_parser("status")
    s.add_argument("--base", type=Path, default=None)
    c = sub.add_parser("convert")
    c.add_argument("instrument_folder", help='e.g. 6E_12-26')
    c.add_argument("--base", type=Path, default=None)
    c.add_argument("--output", type=Path, default=Path("data/live/6e_history_bars"))
    c.add_argument("--allow-lockbox", action="store_true")
    a = p.parse_args(argv)
    base = a.base or user_dir()
    if a.cmd == "request":
        path = write_request(base / "ai-trader-requests", a.instrument, a.start, a.end, a.kind)
        print(f"request written: {path}")
    elif a.cmd == "status":
        print(json.dumps(status(base), indent=1))
    else:
        for path in convert(base / "ai-trader-history", a.instrument_folder, a.output, a.allow_lockbox):
            print(path)


if __name__ == "__main__":
    main()
