"""Capture -> minute store conversion and the shadow-rule runner on synthetic data."""

import json
from datetime import date, datetime, timezone

import numpy as np

from ai_trader.live import capture_minutes as cm
from ai_trader.live import shadow_signals as ss

START = int(datetime(2026, 10, 19, 7, 0, tzinfo=timezone.utc).timestamp()) * 10**9


def _rec(kind, ms, seq, **f):
    return {"kind": kind, "source_session": "ninjatrader-" + "a" * 32, "sequence": seq,
            "observed_utc_ns": START + ms * 1_000_000, "elapsed_ns": ms * 1_000_000, **f}


def _session():
    return {"kind": "session_start", "source_session": "ninjatrader-" + "a" * 32, "sequence": 0,
            "observed_utc_ns": START, "elapsed_ns": 0, "schema": "ai_trader_market_capture_v1",
            "provider": "ninjatrader", "market": "6E", "instrument": "6E 12-26", "feed_environment": "unverified",
            "feed_label": "SYNTHETIC_TEST_ONLY", "tick_size": "0.00005", "max_seconds": 60, "max_events": 100,
            "clock_basis": "serialized_callback_observation_utc", "clock_sync_verified": False,
            "trading_enabled": False}


def test_ladder_operations():
    lad = cm.Ladder()
    lad.apply("bid", "add", 0, 1000, 10)
    lad.apply("bid", "add", 1, 999, 20)
    lad.apply("bid", "add", 2, 990, 50)  # outside the 5-tick window
    lad.apply("ask", "add", 0, 1001, 7)
    assert lad.best("bid") == [1000, 10] and lad.within("bid") == 30 and lad.within("ask") == 7
    lad.apply("bid", "update", 0, 1000, 4)
    lad.apply("bid", "remove", 1, 999, 0)
    assert lad.within("bid") == 4 and lad.best("bid") == [1000, 4]
    lad.apply("ask", "remove", 7, 0, 0)  # out of range: ignored
    assert lad.best("ask") == [1001, 7]


def test_convert_builds_bars_and_book_minutes(tmp_path):
    rows = [_session(),
            _rec("depth", 10, 1, side="bid", operation="add", position=0, price="1.10000", size=10, provider_time_text="x"),
            _rec("depth", 11, 2, side="ask", operation="add", position=0, price="1.10010", size=8, provider_time_text="x"),
            _rec("depth", 12, 3, side="bid", operation="add", position=1, price="1.09995", size=15, provider_time_text="x"),
            _rec("trade", 500, 4, price="1.10010", size=3, provider_time_text="x"),   # at the ask: buyer
            _rec("trade", 60_500, 5, price="1.10000", size=30, provider_time_text="x"),  # next minute, at the bid: seller, big
            _rec("session_end", 61_000, 6, reason="manual_stop", clean_shutdown=True, event_records=5)]
    bars, book = cm.convert(rows)
    day = "2026-10-19"
    b = bars[day]
    assert b["tick_nano"] == 50_000 and b["trade_count"] == 2
    assert b["bars"][0] == [START, 22002 * 50_000, 22002 * 50_000, 22002 * 50_000, 22002 * 50_000, 3, 1, 3, 0]
    assert b["bars"][1][5:] == [30, 1, 0, 30]
    m420, m421 = book[day]["minutes"]["420"], book[day]["minutes"]["421"]
    assert (m420["bid"], m420["ask"], m420["bid_sz"], m420["ask_sz"]) == (22000, 22002, 10, 8)
    assert m420["bid_d5"] == 25 and m420["ask_d5"] == 8 and m420["buy_vol"] == 3
    assert m421["sell_vol"] == 30 and m421["big_trades"] == 1 and m421["tpx"] == {"22000": [0, 30]}
    written = cm.write_docs(bars, book, tmp_path)
    assert len(written) == 2 and json.loads((tmp_path / "book" / f"{day}.json").read_text())["utc_date"] == day


def _store_day(tmp_path, d: date, closes, depth):
    start = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()) * 10**9
    bars, minutes = [], {}
    for k, cl in enumerate(closes):
        p = int(cl) * 50_000
        bars.append([start + k * 60_000_000_000, p, p + 50_000, p - 50_000, p, 5, 1, 3, 2])
        minutes[str(k)] = {"bid": int(cl) - 1, "ask": int(cl) + 1, "bid_sz": 10, "ask_sz": 10, "bid_d5": depth[k],
                           "ask_d5": depth[k], "min_ask": int(cl) + 1, "max_bid": int(cl) - 1, "buy_vol": 3,
                           "sell_vol": 2, "trades": 1, "big_trades": 0, "ofi": 0, "adds_b": 0, "adds_a": 0,
                           "cxl_b": 0, "cxl_a": 0, "tpx": {}}
    (tmp_path / "bars").mkdir(parents=True, exist_ok=True); (tmp_path / "book").mkdir(parents=True, exist_ok=True)
    (tmp_path / "bars" / f"{d}.json").write_text(json.dumps({"utc_date": d.isoformat(), "contract": "6E 12-26",
                                                               "tick_nano": 50_000, "bars": bars}))
    (tmp_path / "book" / f"{d}.json").write_text(json.dumps({"utc_date": d.isoformat(), "contract": "6E 12-26",
                                                               "minutes": minutes}))


def test_shadow_rule_fires_only_with_thick_book(tmp_path):
    # Gentle drift down (so no new highs appear), a sharp dip to a new 4-hour low at 07:20-07:35 UTC, then a
    # snap back above the previous 15-minute high that also puts the 4-hour change positive.
    closes = np.full(1440, 22000.0) - np.arange(1440) * 0.01
    closes[440:455] -= 60
    closes[455:] += 10
    thick = [100] * 1440
    thin = [100] * 440 + [20] * 1000  # book thins out exactly when the setup appears
    _store_day(tmp_path / "thick", date(2026, 10, 19), closes, thick)
    _store_day(tmp_path / "thin", date(2026, 10, 19), closes, thin)
    for name, expect in (("thick", True), ("thin", False)):
        days = {}
        ss.load_store(tmp_path / name / "bars", tmp_path / name / "book", days)
        out = ss.decisions(ss.arrays(days))
        assert (len(out) > 0) is expect, name
        if out:
            assert out[0]["side"] == "long" and out[0]["minute_utc"].startswith("07:")


def test_lockbox_days_refused(tmp_path):
    _store_day(tmp_path, date(2026, 8, 3), np.full(1440, 22000.0), [1] * 1440)
    days = {}
    try:
        ss.load_store(tmp_path / "bars", tmp_path / "book", days)
    except ValueError as e:
        assert "lockbox" in str(e)
    else:
        raise AssertionError("lockbox day was accepted")
