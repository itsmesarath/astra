"""Synthetic checks for the 6E horizon census (no archive access)."""

import json
import zipfile
from datetime import date

import pytest

from ai_trader.research import six_e_horizon_census as census

M = census.MINUTE_NS
T = census.TICK_NANO
DAY0 = 1_745_366_400 * 10**9  # 2025-04-23 00:00 UTC


def test_reserved_2026_dates_are_refused_before_opening():
    with pytest.raises(ValueError, match="reserved"):
        census.contract_for(date(2026, 1, 2))
    with pytest.raises(ValueError):
        census.contract_for(date(2025, 3, 1))
    assert census.contract_for(date(2025, 6, 8)) == "6EM5"
    assert census.contract_for(date(2025, 6, 9)) == "6EU5"
    assert census.contract_for(date(2025, 12, 31)) == "6EH6"


def test_member_listing_skips_reserved_and_unavailable(tmp_path):
    path = tmp_path / "GLBX-TEST.zip"
    conditions = [
        {"date": "2025-12-31", "condition": "available"},
        {"date": "2025-11-28", "condition": "degraded"},
        {"date": "2026-01-02", "condition": "available"},
    ]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("condition.json", json.dumps(conditions))
        for day in ("20251231", "20251128", "20260102"):
            archive.writestr(f"glbx-mdp3-{day}.mbo.dbn.zst", b"x")
    found = census.development_members(tmp_path)
    assert [(d.isoformat(), n) for d, _, n in found] == [
        ("2025-12-31", "glbx-mdp3-20251231.mbo.dbn.zst")
    ]


def test_minute_bars_ohlc_volume_and_aggressor_split():
    p = 1_100_000_000
    trades = [
        (DAY0 + 1, p, 2, "B"),
        (DAY0 + 2, p + 3 * T, 1, "A"),
        (DAY0 + 3, p - T, 4, "N"),
        (DAY0 + M + 5, p + T, 1, "B"),
    ]
    bars = census.minute_bars(trades)
    assert bars == [
        [DAY0, p, p + 3 * T, p - T, p - T, 7, 3, 2, 1],
        [DAY0 + M, p + T, p + T, p + T, p + T, 1, 1, 1, 0],
    ]
    with pytest.raises(ValueError):
        census.minute_bars([(DAY0, p, 0, "B")])


def test_census_counts_moves_in_ticks_and_never_fills_missing_minutes():
    p = 1_100_000_000
    # Trades at minutes 0, 1 and 5 (minutes 2-4 have no trade).
    bars = [
        [DAY0, p, p, p, p, 1, 1, 0, 0],
        [DAY0 + M, p, p, p, p + 2 * T, 1, 1, 0, 0],
        [DAY0 + 5 * M, p, p, p, p - 4 * T, 1, 1, 0, 0],
    ]
    result = census.census([{"utc_date": "2025-04-23", "bars": bars}])
    one = result["horizons"]["1"]
    assert one["samples"] == 1 and one["median_ticks"] == 2
    assert one["missing_end_minute"] == 2
    five = result["horizons"]["5"]
    assert five["samples"] == 1 and five["median_ticks"] == 4
    assert five["share_at_least"]["4"] == 1.0 and five["share_at_least"]["6"] == 0.0
    assert five["by_utc_hour"]["0"]["n"] == 1


def test_bar_loader_refuses_reserved_days(tmp_path):
    (tmp_path / "2026-01-02.json").write_text(json.dumps({"utc_date": "2026-01-02", "bars": []}))
    with pytest.raises(ValueError, match="Reserved"):
        census.load_bar_days(tmp_path)


def test_decode_day_end_to_end_on_a_synthetic_dbn_member(tmp_path):
    dbn = pytest.importorskip("databento_dbn")
    zstd = pytest.importorskip("zstandard")
    from types import SimpleNamespace as NS

    day = date(2025, 4, 23)
    interval = NS(start_date=day, end_date=date(2025, 4, 24), symbol="42")
    metadata = dbn.Metadata(
        dataset="GLBX.MDP3",
        start=DAY0,
        end=DAY0 + 86_400 * 10**9,
        stype_in=dbn.SType.PARENT,
        stype_out=dbn.SType.INSTRUMENT_ID,
        schema=dbn.Schema.MBO,
        symbols=["6E.FUT"],
        mappings=[NS(raw_symbol="6EM5", intervals=[interval])],
    )
    actions = {"T": dbn.Action.TRADE, "A": dbn.Action.ADD}
    sides = {"B": dbn.Side.BID, "A": dbn.Side.ASK}

    def msg(ts, action, side, price, size, instrument=42):
        return bytes(
            dbn.MBOMsg(
                publisher_id=1, instrument_id=instrument, ts_event=ts, order_id=1,
                price=price, size=size, action=actions[action], side=sides[side],
                ts_recv=ts, flags=0,
            )
        )

    p = 1_100_000_000
    raw = metadata.encode() + b"".join(
        [
            msg(DAY0 + 10, "T", "B", p, 2),
            msg(DAY0 + 20, "A", "A", p + T, 5),  # book add: ignored
            msg(DAY0 + 30, "T", "B", 9, 1, instrument=7),  # other instrument: ignored
            msg(DAY0 + M + 1, "T", "A", p + T, 3),
        ]
    )
    name = "glbx-mdp3-20250423.mbo.dbn.zst"
    path = tmp_path / "GLBX-TEST.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(name, zstd.ZstdCompressor().compress(raw))
    result = census.decode_day(day, path, name)
    assert result["contract"] == "6EM5" and result["instrument_id"] == 42
    assert result["trade_count"] == 2
    assert result["bars"] == [
        [DAY0, p, p, p, p, 2, 1, 2, 0],
        [DAY0 + M, p + T, p + T, p + T, p + T, 3, 1, 0, 3],
    ]
