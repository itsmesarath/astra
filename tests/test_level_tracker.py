"""Level tracker on a synthetic store + capture: a level forms, is revisited today, the book is logged, the outcome resolves."""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from ai_trader.live import level_tracker as lt

TICK_NANO = 50_000  # 0.00005 in nano units


def _store(tmp: Path, days: list[date], closes_by_day: dict):
    (tmp / "bars").mkdir(parents=True)
    for d in days:
        c = closes_by_day[d]
        day_ns = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()) * 10**9
        bars = []
        for m, px in enumerate(c):
            if np.isnan(px):
                continue
            bars.append([day_ns + m * 60_000_000_000, int(px * TICK_NANO), int((px + 1) * TICK_NANO), int((px - 1) * TICK_NANO), int(px * TICK_NANO), 5, 3, 2, 3])
        (tmp / "bars" / f"{d.isoformat()}.json").write_text(json.dumps({"tick_nano": TICK_NANO, "bars": bars}))


def _capture(path: Path, d: date, closes, start_minute: int):
    """Raw capture rows for today from start_minute: a trade per minute plus a static ladder."""
    day_ns = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()) * 10**9
    rows = [{"kind": "session_start", "tick_size": "0.00005", "observed_utc_ns": day_ns, "sequence": 0}]
    seq = 1
    for m in range(start_minute, len(closes)):
        px = closes[m]
        if np.isnan(px):
            continue
        ts = day_ns + m * 60_000_000_000 + 1_000_000
        for k in range(3):
            rows.append({"kind": "depth", "side": "ask", "operation": "update" if k else "add", "position": k, "price": f"{(px + 1 + k) * 0.00005:.5f}", "size": 100 + 50 * k, "observed_utc_ns": ts, "sequence": seq}); seq += 1
            rows.append({"kind": "depth", "side": "bid", "operation": "update" if k else "add", "position": k, "price": f"{(px - 1 - k) * 0.00005:.5f}", "size": 80, "observed_utc_ns": ts, "sequence": seq}); seq += 1
        rows.append({"kind": "trade", "price": f"{px * 0.00005:.5f}", "size": 7, "observed_utc_ns": ts + 10, "sequence": seq}); seq += 1
        rows.append({"kind": "trade", "price": f"{(px + 1) * 0.00005:.5f}", "size": 3, "observed_utc_ns": ts + 20, "sequence": seq}); seq += 1
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_tracker_logs_touch_with_book_and_outcome(tmp_path):
    rng = np.random.default_rng(0)
    today = date(2026, 10, 19)
    days = [today - timedelta(days=k) for k in range(3, -1, -1)]
    closes = {}
    base = 22000.0
    for d in days:
        c = base + np.cumsum(rng.normal(0, 0.6, 1440))
        closes[d] = c
        base = c[-1]
    # yesterday 10:00: a sharp top at 'L' then a 12-tick drop within the hour -> resistance level
    y = days[-2]
    c = closes[y]
    L = c[600] + 10
    c[598:603] = [c[600] + 6, c[600] + 9, L, c[600] + 8, c[600] + 5]
    c[603:660] = L - 14 - rng.normal(0, 0.3, 57)
    c[660:] = L - 14 + np.cumsum(rng.normal(0, 0.3, 780))
    # today: drift slowly back up to the level by 10:30, touch at 10:30, then fall away (hold)
    t = closes[today]
    t[:600] = np.linspace(L - 14, L - 1, 600)
    t[600:631] = np.linspace(L - 1, L, 31)
    t[631:] = L - 2 - np.linspace(0, 10, 1440 - 631)
    t[700:] = np.nan                       # the day is only partly through
    _store(tmp_path / "store", days[:-1], closes)
    _capture(tmp_path / "cap.jsonl", today, t, 0)
    out = tmp_path / "events.jsonl"
    tr = lt.LevelTracker([tmp_path / "store" / "bars"], str(tmp_path / "cap.jsonl"), out, history_days=3)
    rep = tr.run_once(now=datetime(today.year, today.month, today.day, 11, 40, tzinfo=timezone.utc))
    rows = [json.loads(x) for x in out.read_text().splitlines()]
    touches = [r for r in rows if r["kind"] == "touch" and r["side"] == "resistance" and abs(r["level_ticks"] - round(L)) <= 1
               and r["level_utc"].startswith(y.isoformat()) and r["utc"].startswith(today.isoformat())]
    assert touches, f"expected a touch of the planted level; events={rep}"
    t0 = touches[0]
    assert t0["utc"].startswith("2026-10-19T10:")
    assert t0["approach"] is not None and t0["trend4"] == 1.0
    outs = [r for r in rows if r["kind"] == "outcome" and r["id"] == t0["id"]]
    assert outs and outs[0]["outcome"] == "hold"
    # re-run: nothing is logged twice
    n = len(rows)
    tr2 = lt.LevelTracker([tmp_path / "store" / "bars"], str(tmp_path / "cap.jsonl"), out, history_days=3)
    tr2.run_once(now=datetime(today.year, today.month, today.day, 11, 41, tzinfo=timezone.utc))
    assert len(out.read_text().splitlines()) == n


def test_book_features_shape():
    b = lt.TodayBook()
    day_ns = int(datetime(2026, 10, 19, tzinfo=timezone.utc).timestamp()) * 10**9
    rows = [{"kind": "session_start", "tick_size": "0.00005", "observed_utc_ns": day_ns}]
    ts = day_ns + 10 * 60_000_000_000
    rows += [{"kind": "depth", "side": "ask", "operation": "add", "position": 0, "price": "1.12345", "size": 120, "observed_utc_ns": ts},
             {"kind": "depth", "side": "bid", "operation": "add", "position": 0, "price": "1.12340", "size": 60, "observed_utc_ns": ts},
             {"kind": "trade", "price": "1.12345", "size": 9, "observed_utc_ns": ts + 5}]
    b.feed(rows)
    f = b.features(level=22469, side=1, now_ns=ts + 10)
    assert f["far_size_5"] == 120 and f["near_size_5"] == 60 and f["buy_2m"] == 9 and f["far_adds_2m"] == 1
