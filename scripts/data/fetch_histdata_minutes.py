"""Fetch free 1-minute bars from histdata.com (ASCII M1 zips) and write the same per-day JSON
files as fetch_dukascopy_minutes.py (data/raw/dukascopy/<SYMBOL>/<date>.json), stdlib only.

histdata serves one zip per year (past years) or per month (current year) through a small
HTML form: the page carries hidden fields (tk, date, datemonth, platform, timeframe, fxpair)
that must be POSTed to /get.php with the page as Referer. Timestamps in the CSV are
"EST without daylight saving" (UTC-5 all year), so +5 h gives UTC. Rows:
``YYYYMMDD HHMMSS;open;high;low;close;volume``.

Existing non-empty day files are kept (placeholders and missing days are written).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SITE = "https://www.histdata.com"
PAGE = SITE + "/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{pair}/{year}{month}"
# histdata pair -> (our symbol, point)
PAIRS = {
    "eurusd": ("EURUSD", 0.00001), "gbpusd": ("GBPUSD", 0.00001), "usdjpy": ("USDJPY", 0.001),
    "audusd": ("AUDUSD", 0.00001), "xauusd": ("XAUUSD", 0.001), "nsxusd": ("US100", 0.001),
    "grxeur": ("DE40", 0.001), "spxusd": ("US500", 0.001),
}
EST = timezone(timedelta(hours=-5))
LOCKBOX_FROM = date(2026, 7, 1)
HEADERS = {"User-Agent": "Mozilla/5.0 (research downloader)"}


def get(url: str, data: bytes | None = None, referer: str | None = None) -> bytes:
    h = dict(HEADERS)
    if referer:
        h["Referer"] = referer
    req = urllib.request.Request(url, data=data, headers=h)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as exc:
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))
            err = exc
    raise RuntimeError(err)


def download_zip(pair: str, year: int, month: int | None) -> bytes | None:
    page_url = PAGE.format(pair=pair, year=year, month=f"/{month}" if month else "")
    html = get(page_url).decode("utf-8", "replace")
    form = re.search(r'<form[^>]*id="file_down"[^>]*action="([^"]+)"(.*?)</form>', html, re.S)
    if not form:
        return None
    action, body = form.group(1), form.group(2)
    fields = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', body))
    if "tk" not in fields:
        return None
    url = action if action.startswith("http") else SITE + ("" if action.startswith("/") else "/") + action
    raw = get(url, urllib.parse.urlencode(fields).encode(), referer=page_url)
    return raw if raw[:2] == b"PK" else None


def parse_rows(zip_bytes: bytes, point: float):
    """Yield (utc_day, [minute_ns, o, h, l, c, vol]) from the CSV inside the zip."""
    scale = round(1 / point)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        text = z.read(name).decode("ascii", "replace")
    for row in csv.reader(io.StringIO(text), delimiter=";"):
        if len(row) < 6:
            continue
        ts = datetime.strptime(row[0], "%Y%m%d %H%M%S").replace(tzinfo=EST).astimezone(timezone.utc)
        o, h, l, c = (int(round(float(v) * scale)) for v in row[1:5])
        yield ts.date(), [int(ts.timestamp()) * 10**9, o, h, l, c, float(row[5])]


def write_days(symbol: str, point: float, rows, out: Path, source: str) -> int:
    days: dict[date, list] = {}
    for d, bar in rows:
        days.setdefault(d, []).append(bar)
    written = 0
    for d, bars in days.items():
        if d >= LOCKBOX_FROM:
            continue  # Jul-Sep 2026 stays sealed, even the EST spill-over hours of a June file
        target = out / symbol / f"{d.isoformat()}.json"
        if target.exists() and target.stat().st_size > 0:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        doc = {"symbol": symbol, "source": source, "utc_date": d.isoformat(), "point": point,
               "columns": ["minute_ns", "open", "high", "low", "close", "volume"], "bars": sorted(bars)}
        tmp = target.with_suffix(".partial")
        tmp.write_text(json.dumps(doc, separators=(",", ":")))
        tmp.replace(target)
        written += 1
    return written


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--pairs", nargs="*", default=list(PAIRS))
    p.add_argument("--start-year", type=int, default=2021)
    p.add_argument("--end", type=date.fromisoformat, default=date(2026, 6, 30))
    p.add_argument("--output", type=Path, default=Path("data/raw/dukascopy"))
    a = p.parse_args(argv)
    if a.end >= date(2026, 7, 1):
        sys.exit("end must stay before the lockbox (2026-07-01)")
    for pair in a.pairs:
        symbol, point = PAIRS[pair]
        for year in range(a.start_year, a.end.year + 1):
            months = [None] if year < a.end.year else list(range(1, a.end.month + 1))
            for month in months:
                label = f"{pair} {year}" + (f"-{month:02d}" if month else "")
                try:
                    raw = download_zip(pair, year, month)
                except Exception as exc:
                    print(label, "error", exc, flush=True)
                    continue
                if raw is None:
                    print(label, "no file", flush=True)
                    continue
                n = write_days(symbol, point, parse_rows(raw, point), a.output, f"histdata:{label}")
                print(label, f"{len(raw) // 1024} KB, wrote {n} days", flush=True)
                time.sleep(1.5)


if __name__ == "__main__":
    main()
