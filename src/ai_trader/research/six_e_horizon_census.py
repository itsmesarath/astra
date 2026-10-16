"""6E horizon feasibility census on 2025 development data (roadmap §8, step 1).

Question answered: at which holding horizons and UTC hours does the 6E price move by
enough ticks to pay round-trip trading costs? Earlier studies only looked at a ±3-tick,
15-second scalp inside 12:00-16:00 UTC, where cost and typical move were the same size.

Two stages:
1. ``bars``: decode the Databento GLBX.MDP3 MBO daily files from 2025-03-26 to 2026-06-30
   (owner decision 16 Oct 2026: train on 15 months), keep trades of the declared front
   contract, and write one compact 1-minute bar file per day. Dates on or after 2026-07-01
   (the sealed Jul-Sep 2026 lockbox) are refused *before* any member is opened.
2. ``census``: from the bars, measure absolute price moves for several horizons and
   UTC hours, in ticks, and report how often they exceed cost thresholds.

This is descriptive research (rigor tier T1). It trains nothing and trades nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

TICK_NANO = 50_000  # 6E tick 0.00005 in Databento fixed-point (1e-9) price units.
MINUTE_NS = 60_000_000_000
RESERVED_FROM = date(2026, 7, 1)  # lockbox Jul-Sep 2026 stays sealed (owner decision 16 Oct)
DEVELOPMENT_FROM = date(2025, 3, 26)
HORIZONS_MIN = (1, 5, 15, 30, 60, 240)
THRESHOLDS_TICKS = (2, 3, 4, 6, 8, 12, 20)
MEMBER = re.compile(r"glbx-mdp3-(\d{8})\.mbo\.dbn\.zst")

# Declared research roll used by the earlier 6E studies (historical_6e_archive.py).
ROLL = (
    (date(2025, 6, 9), "6EM5"),
    (date(2025, 9, 8), "6EU5"),
    (date(2025, 12, 8), "6EZ5"),
    (date(2026, 3, 9), "6EH6"),
    (date(2026, 6, 8), "6EM6"),
    (date(2026, 7, 1), "6EU6"),
)


def contract_for(day: date) -> str:
    if day >= RESERVED_FROM:
        raise ValueError(f"{day} is in the reserved lockbox and must not be opened")
    if day < DEVELOPMENT_FROM:
        raise ValueError(f"{day} is before the development archive")
    for end, symbol in ROLL:
        if day < end:
            return symbol
    raise ValueError(f"No declared contract for {day}")


def development_members(downloads: Path) -> list[tuple[date, Path, str]]:
    """List (day, zip path, member name) for 2025 'available' days only."""
    found = []
    for path in sorted(downloads.glob("GLBX-*.zip")):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            conditions = {}
            if "condition.json" in names:
                for row in json.loads(archive.read("condition.json")):
                    conditions[row["date"]] = row["condition"]
            for name in names:
                match = MEMBER.fullmatch(name)
                if not match:
                    continue
                day = datetime.strptime(match.group(1), "%Y%m%d").date()
                if day >= RESERVED_FROM or day < DEVELOPMENT_FROM:
                    continue  # Filter by filename only; lockbox members are never opened.
                if conditions.get(day.isoformat()) != "available":
                    continue
                found.append((day, path, name))
    return sorted(found)


def minute_bars(trades) -> list[list[int]]:
    """Aggregate (ts_ns, price_nano, size, aggressor) trades into 1-minute bars.

    Returns rows [minute_start_ns, open, high, low, close, volume, trades, buy_vol, sell_vol]
    sorted by minute. Aggressor is 'B' (buyer lifted the ask), 'A' (seller hit the bid)
    or anything else (unknown, counted in volume only). Minutes with no trades are absent.
    """
    bars: dict[int, list[int]] = {}
    for ts, price, size, aggressor in trades:
        if size <= 0 or price <= 0:
            raise ValueError("Trade with non-positive size or price")
        minute = ts - ts % MINUTE_NS
        bar = bars.get(minute)
        if bar is None:
            bar = bars[minute] = [minute, price, price, price, price, 0, 0, 0, 0]
        else:
            bar[2] = max(bar[2], price)
            bar[3] = min(bar[3], price)
            bar[4] = price
        bar[5] += size
        bar[6] += 1
        if aggressor == "B":
            bar[7] += size
        elif aggressor == "A":
            bar[8] += size
    return [bars[key] for key in sorted(bars)]


def decode_day(day: date, path: Path, name: str) -> dict:
    """Decode one daily MBO member and return its 1-minute bars (needs databento_dbn)."""
    import databento_dbn as dbn
    import zstandard as zstd

    contract = contract_for(day)  # Refuses reserved dates before opening the member.
    start = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp()) * 10**9
    end = start + 86_400 * 10**9
    instrument_id = None
    trades = []
    last_ts = None
    out_of_order = 0
    decoder = dbn.DBNDecoder()

    def consume(item):
        nonlocal instrument_id, last_ts, out_of_order
        if isinstance(item, dbn.Metadata):
            active = [
                m
                for m in item.mappings.get(contract, [])
                if m["start_date"] <= day < m["end_date"]
            ]
            if len(active) != 1:
                raise ValueError(f"No unique mapping for {contract} on {day}")
            instrument_id = int(active[0]["symbol"])
            return
        if not isinstance(item, dbn.MBOMsg) or item.instrument_id != instrument_id:
            return
        if str(item.action) != "T" or item.flags & dbn.F_SNAPSHOT:
            return
        ts = item.ts_recv
        if not start <= ts < end:
            return
        if last_ts is not None and ts < last_ts:
            out_of_order += 1
        last_ts = ts if last_ts is None else max(last_ts, ts)
        trades.append((ts, item.price, item.size, str(item.side)))

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
    if instrument_id is None:
        raise ValueError(f"No metadata in {name}")
    trades.sort(key=lambda t: t[0])
    return {
        "utc_date": day.isoformat(),
        "contract": contract,
        "instrument_id": instrument_id,
        "source": f"{path.name}:{name}",
        "trade_count": len(trades),
        "out_of_order_trades": out_of_order,
        "tick_nano": TICK_NANO,
        "columns": ["minute_ns", "open", "high", "low", "close", "volume", "trades",
                    "buy_volume", "sell_volume"],
        "bars": minute_bars(trades),
    }


def _bars_job(args):
    day, path, name, output = args
    target = output / f"{day.isoformat()}.json"
    if target.exists():
        return day.isoformat(), "skipped"
    try:
        result = decode_day(day, Path(path), name)
    except Exception as exc:  # Record failures; never fabricate a day.
        (output / f"{day.isoformat()}.error.txt").write_text(f"{type(exc).__name__}: {exc}\n")
        return day.isoformat(), "error"
    partial = target.with_suffix(".partial")
    partial.write_text(json.dumps(result, separators=(",", ":")))
    partial.replace(target)
    return day.isoformat(), f"ok {result['trade_count']} trades"


def build_bars(downloads: Path, output: Path, workers: int) -> None:
    output.mkdir(parents=True, exist_ok=True)
    jobs = [(d, str(p), n, output) for d, p, n in development_members(downloads)]
    print(f"{len(jobs)} development days (before the lockbox); writing to {output}", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for day, status in pool.map(_bars_job, jobs):
            print(day, status, flush=True)


def census(bar_days: list[dict]) -> dict:
    """Absolute close-to-close moves by horizon and UTC hour, in ticks.

    A move at horizon h starts at every minute with a trade and ends at the close of
    the minute exactly h minutes later; pairs without a trade at the end minute, or
    crossing a contract change, are skipped (counted as missing, never filled).
    """
    moves: dict[tuple[int, int], list[int]] = defaultdict(list)
    missing: dict[int, int] = defaultdict(int)
    for day in bar_days:
        closes = {row[0]: row[4] for row in day["bars"]}
        for minute, price in closes.items():
            hour = (minute // 3_600_000_000_000) % 24
            for h in HORIZONS_MIN:
                later = closes.get(minute + h * MINUTE_NS)
                if later is None:
                    missing[h] += 1
                    continue
                moves[(h, hour)].append(abs(later - price) // TICK_NANO)
    result: dict = {"horizons": {}, "thresholds_ticks": list(THRESHOLDS_TICKS)}
    for h in HORIZONS_MIN:
        all_moves = sorted(m for (hh, _), ms in moves.items() if hh == h for m in ms)
        entry = {"samples": len(all_moves), "missing_end_minute": missing[h]}
        if all_moves:
            entry.update(_summary(all_moves))
        entry["by_utc_hour"] = {
            str(hour): _summary(sorted(moves[(h, hour)]))
            for hour in range(24)
            if moves.get((h, hour))
        }
        result["horizons"][str(h)] = entry
    return result


def _summary(sorted_moves: list[int]) -> dict:
    n = len(sorted_moves)

    def quantile(q):
        return sorted_moves[min(n - 1, int(q * n))]

    return {
        "n": n,
        "median_ticks": quantile(0.5),
        "p75_ticks": quantile(0.75),
        "p90_ticks": quantile(0.9),
        "share_at_least": {
            str(k): round(sum(1 for m in sorted_moves if m >= k) / n, 4) for k in THRESHOLDS_TICKS
        },
    }


def load_bar_days(directory: Path) -> list[dict]:
    days = []
    for path in sorted(directory.glob("*.json")):
        day = json.loads(path.read_text())
        if date.fromisoformat(day["utc_date"]) >= RESERVED_FROM:
            raise ValueError("Reserved lockbox day found in bar directory")
        days.append(day)
    return days


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    bars = sub.add_parser("bars", help="Decode 2025 MBO days into 1-minute bars")
    bars.add_argument("--downloads", type=Path, default=Path("downloads"))
    bars.add_argument("--output", type=Path, default=Path("data/processed/6e_minute_bars_dev_1"))
    bars.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    report = sub.add_parser("census", help="Summarise horizon moves from the bars")
    report.add_argument("--bars", type=Path, default=Path("data/processed/6e_minute_bars_dev_1"))
    report.add_argument("--output", type=Path, default=Path("data/processed/6e_horizon_census_dev_1.json"))
    args = parser.parse_args(argv)
    if args.command == "bars":
        build_bars(args.downloads, args.output, args.workers)
    else:
        days = load_bar_days(args.bars)
        result = census(days)
        result["days"] = len(days)
        result["first_day"] = days[0]["utc_date"] if days else None
        result["last_day"] = days[-1]["utc_date"] if days else None
        args.output.write_text(json.dumps(result, indent=1))
        print(f"Census of {len(days)} days written to {args.output}")


if __name__ == "__main__":
    main()
