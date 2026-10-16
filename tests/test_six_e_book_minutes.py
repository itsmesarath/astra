"""Book reconstruction checks on a hand-built MBO stream."""

import zipfile
from datetime import date
from types import SimpleNamespace as NS

import pytest

from ai_trader.research import six_e_book_minutes as bm

DAY0 = 1_745_366_400 * 10**9  # 2025-04-23
T = bm.TICK_NANO
M = bm.MINUTE_NS


def test_book_best_depth_and_removal():
    b = bm.Book()
    b.add(1, "B", 100, 5); b.add(2, "B", 99, 7); b.add(3, "A", 101, 4); b.add(4, "A", 103, 9)
    assert b.best("B") == 100 and b.best("A") == 101
    assert b.depth("B", 100) == 12 and b.depth("A", 101) == 13
    b.remove(1)
    assert b.best("B") == 99
    b.reduce(3, 4)
    assert b.best("A") == 103


def test_decode_day_features_and_queue_volume(tmp_path):
    dbn = pytest.importorskip("databento_dbn")
    zstd = pytest.importorskip("zstandard")
    day = date(2025, 4, 23)
    metadata = dbn.Metadata(dataset="GLBX.MDP3", start=DAY0, end=DAY0 + 86_400 * 10**9,
                            stype_in=dbn.SType.PARENT, stype_out=dbn.SType.INSTRUMENT_ID,
                            schema=dbn.Schema.MBO, symbols=["6E.FUT"],
                            mappings=[NS(raw_symbol="6EM5", intervals=[NS(start_date=day, end_date=date(2025, 4, 24), symbol="42")])])
    A = {"A": dbn.Action.ADD, "C": dbn.Action.CANCEL, "T": dbn.Action.TRADE, "F": dbn.Action.FILL}
    S = {"B": dbn.Side.BID, "A": dbn.Side.ASK}

    def msg(ts, action, side, price_ticks, size, oid):
        return bytes(dbn.MBOMsg(publisher_id=1, instrument_id=42, ts_event=ts, order_id=oid,
                                price=price_ticks * T, size=size, action=A[action], side=S[side], ts_recv=ts, flags=0))

    raw = metadata.encode() + b"".join([
        msg(DAY0 + 1, "A", "B", 1000, 10, 1),   # bid 1000 x10
        msg(DAY0 + 2, "A", "B", 999, 20, 2),    # bid 999 x20
        msg(DAY0 + 3, "A", "A", 1001, 6, 3),    # ask 1001 x6
        msg(DAY0 + 4, "A", "A", 1002, 8, 4),
        msg(DAY0 + 5, "C", "A", 1001, 6, 3),    # cancel best ask -> ask becomes 1002
        msg(DAY0 + M + 1, "T", "A", 1000, 4, 0),  # seller hits the bid at 1000 for 4
        msg(DAY0 + M + 2, "F", "B", 1000, 4, 1),  # resting bid order 1 filled 4
    ])
    name = "glbx-mdp3-20250423.mbo.dbn.zst"
    path = tmp_path / "GLBX-TEST.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(name, zstd.ZstdCompressor().compress(raw))
    out = bm.decode_day(day, path, name)
    m0, m1 = out["minutes"]["0"], out["minutes"]["1"]
    assert (m0["bid"], m0["ask"], m0["bid_sz"], m0["ask_sz"]) == (1000, 1002, 10, 8)
    assert m0["bid_d5"] == 30 and m0["ask_d5"] == 8
    assert m0["min_ask"] == 1001 and m0["max_bid"] == 1000
    # First orders into an empty book have no best quote to compare with, so are not counted.
    assert m0["adds_b"] == 20 and m0["adds_a"] == 8 and m0["cxl_a"] == 6 and m0["ofi"] == 6
    assert m1["sell_vol"] == 4 and m1["trades"] == 1 and m1["tpx"] == {"1000": [0, 4]}
    assert m1["bid_sz"] == 6  # 10 - 4 filled


def test_lockbox_dates_refused(tmp_path):
    with pytest.raises(ValueError, match="lockbox"):
        bm.contract_for(date(2026, 7, 1))
