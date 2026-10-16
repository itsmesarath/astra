"""Fetch free 1-minute BID candles from the Dukascopy public archive for IC Markets-like
instruments, as one JSON file per UTC day (standard library only; runs natively on Windows).

Output: data/raw/dukascopy/<SYMBOL>/<YYYY-MM-DD>.json with
  {"symbol", "utc_date", "point": <price unit as float>, "columns": [...],
   "bars": [[minute_ns, open, high, low, close, volume], ...]}
Prices are integers in units of ``point`` (e.g. 0.00001 for EURUSD), so the research code can
treat them like the 6E tick integers. Minutes without trades are absent. Days with no data
(weekends, holidays, 404) are written as an empty bar list so they are not refetched.

Dukascopy candle record: 6 big-endian fields of 4 bytes each -
time offset in seconds from day start (uint32), open, close, low, high (int32, scaled by the
instrument's decimal factor), volume (float32). Files are LZMA (.bi5); an empty file means no data.
Months in the URL are zero-based.
"""

from __future__ import annotations

import argparse
import json
import lzma
import struct
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE = "https://datafeed.dukascopy.com/datafeed/{sym}/{y}/{m:02d}/{d:02d}/BID_candles_min_1.bi5"
# Dukascopy instrument name -> (friendly name, decimal factor, point)
SYMBOLS = {
    "EURUSD": ("EURUSD", 100000, 0.00001),
    "GBPUSD": ("GBPUSD", 100000, 0.00001),
    "USDJPY": ("USDJPY", 1000, 0.001),
    "AUDUSD": ("AUDUSD", 100000, 0.00001),
    "XAUUSD": ("XAUUSD", 1000, 0.001),
    "USATECHIDXUSD": ("US100", 1000, 0.001),
    "DEUIDXEUR": ("DE40", 1000, 0.001),
    "USA30IDXUSD": ("US30", 1000, 0.001),
}
MINUTE_NS = 60_000_000_000


PAUSE = 0.4  # seconds between requests; the archive returns 503 when hammered


def fetch(url: str, timeout: int = 20) -> bytes | None:
    """GET with polite pacing; 404 -> None; 503/timeouts -> exponential backoff, then raise."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research downloader)"})
    delay = 5
    for attempt in range(7):
        time.sleep(PAUSE)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err = e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            err = e
        time.sleep(delay)
        delay = min(delay * 2, 120)
    raise RuntimeError(f"gave up: {err}")


def decode(raw: bytes, day: date) -> list[list[int | float]]:
    if not raw:
        return []
    data = lzma.decompress(raw)
    start = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()) * 10**9
    bars = []
    for off in range(0, len(data) - len(data) % 24, 24):
        t, o, c, lo, hi, v = struct.unpack(">Iiiiif", data[off:off + 24])
        if o <= 0 or hi < lo:
            continue
        bars.append([start + t * 10**9, o, hi, lo, c, round(v, 2)])
    return bars


def one_day(sym: str, day: date, out: Path) -> str:
    name, factor, point = SYMBOLS[sym]
    target = out / name / f"{day.isoformat()}.json"
    if target.exists() and target.stat().st_size > 0:
        return "skip"  # an empty file is a placeholder from an aborted run: refetch it
    target.parent.mkdir(parents=True, exist_ok=True)
    url = BASE.format(sym=sym, y=day.year, m=day.month - 1, d=day.day)
    try:
        raw = fetch(url)
    except Exception as exc:
        return f"error {exc}"
    bars = decode(raw, day) if raw else []
    doc = {"symbol": name, "source": sym, "utc_date": day.isoformat(), "point": point,
           "columns": ["minute_ns", "open", "high", "low", "close", "volume"], "bars": bars}
    tmp = target.with_suffix(".partial")
    tmp.write_text(json.dumps(doc, separators=(",", ":")))
    tmp.replace(target)
    return f"ok {len(bars)}"


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="*", default=list(SYMBOLS))
    p.add_argument("--start", type=date.fromisoformat, default=date(2021, 1, 1))
    p.add_argument("--end", type=date.fromisoformat, default=date(2026, 6, 30),
                   help="inclusive; keep before the Jul-Sep 2026 lockbox")
    p.add_argument("--output", type=Path, default=Path("data/raw/dukascopy"))
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--probe", action="store_true", help="fetch one day per symbol and print the first bars")
    a = p.parse_args(argv)
    if a.end >= date(2026, 7, 1):
        sys.exit("end date must stay before the lockbox (2026-07-01)")
    if a.probe:
        for sym in a.symbols:
            d = date(2026, 3, 10)
            raw = fetch(BASE.format(sym=sym, y=d.year, m=d.month - 1, d=d.day))
            bars = decode(raw, d) if raw else []
            print(sym, len(bars), "bars; first:", bars[:2], "point", SYMBOLS[sym][2], flush=True)
        return
    days = [a.start + timedelta(i) for i in range((a.end - a.start).days + 1)]
    jobs = [(s, d) for s in a.symbols for d in days]
    print(f"{len(jobs)} symbol-days to {a.output}", flush=True)
    counts = {}
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for (s, d), status in zip(jobs, pool.map(lambda j: one_day(j[0], j[1], a.output), jobs)):
            key = status.split()[0]
            counts[key] = counts.get(key, 0) + 1
            if key == "error" or d.day in (1, 15):
                print(s, d, status, flush=True)
    print("done", counts, flush=True)


if __name__ == "__main__":
    main()
