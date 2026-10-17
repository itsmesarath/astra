"""NinjaTrader history connector, Python side: request files, status, tick -> bar-store conversion."""

import json
from datetime import date, datetime, timezone

import pytest

from ai_trader.live import nt_history as nh


def test_request_file_and_status(tmp_path):
    base = tmp_path
    path = nh.write_request(base / "ai-trader-requests", "6E 12-26", date(2026, 10, 1), date(2026, 10, 16))
    doc = json.loads(path.read_text())
    assert doc == {"instrument": "6E 12-26", "from": "2026-10-01", "to": "2026-10-16", "type": "tick"}
    with pytest.raises(ValueError):
        nh.write_request(base / "ai-trader-requests", "6E 12-26", date(2026, 10, 2), date(2026, 10, 1))
    st = nh.status(base)
    assert st["pending"] == [path.name] and st["done"] == [] and st["history"] == {}


def _tick_file(folder, day: str, rows):
    folder.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"record": "header", "schema": "ai_trader_nt_history_v1", "instrument": "6E 12-26",
                         "type": "tick", "day_local": day, "tick_size": "0.00005", "count": len(rows)})]
    lines += [json.dumps(r) for r in rows]
    (folder / f"tick_{day}.jsonl").write_text("\n".join(lines) + "\n")


def _ns(y, m, d, hh, mm, ss=0):
    return int(datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc).timestamp()) * 10**9


def test_convert_classifies_aggressor_and_buckets_by_utc_day(tmp_path):
    hist = tmp_path / "ai-trader-history"
    _tick_file(hist / "6E_12-26", "2026-10-05", [
        {"t": _ns(2026, 10, 5, 7, 0, 1), "p": "1.10010", "v": 3, "b": "1.10005", "a": "1.10010"},  # at ask: buyer
        {"t": _ns(2026, 10, 5, 7, 0, 30), "p": "1.10005", "v": 2, "b": "1.10005", "a": "1.10010"},  # at bid: seller
        {"t": _ns(2026, 10, 5, 23, 30, 0), "p": "1.10100", "v": 1, "b": "1.10095", "a": "1.10100"},
        {"t": _ns(2026, 10, 6, 0, 5, 0), "p": "1.10120", "v": 4, "b": "1.10115", "a": "1.10120"},   # next UTC day
    ])
    out = tmp_path / "bars"
    written = nh.convert(hist, "6E_12-26", out)
    assert [p.name for p in written] == ["2026-10-05.json", "2026-10-06.json"]
    doc = json.loads((out / "2026-10-05.json").read_text())
    assert doc["tick_nano"] == 50_000 and doc["trade_count"] == 3 and doc["contract"] == "6E 12-26"
    first = doc["bars"][0]
    assert first[1] == 1_100_100_000 and first[5] == 5 and first[7] == 3 and first[8] == 2  # open, vol, buy, sell
    assert doc["partial_edge_day"] is True


def test_convert_refuses_lockbox_days_by_default(tmp_path):
    hist = tmp_path / "ai-trader-history"
    _tick_file(hist / "6E_09-26", "2026-08-03", [
        {"t": _ns(2026, 8, 3, 7, 0, 1), "p": "1.10010", "v": 3, "b": "1.10005", "a": "1.10010"}])
    assert nh.convert(hist, "6E_09-26", tmp_path / "bars") == []
    assert len(nh.convert(hist, "6E_09-26", tmp_path / "bars2", allow_lockbox=True)) == 1
