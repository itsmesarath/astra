"""Loader checks for the Dukascopy-based multi-market study."""

import json
from datetime import date

import numpy as np
import pytest

from ai_trader.research import pa_multi_market_study as mm


def _day(d: date, price: int, filler: bool = False):
    start = int(np.datetime64(d.isoformat(), "s").astype(np.int64)) * 10**9
    bars = []
    for k in range(3):
        if filler:
            bars.append([start + k * 60 * 10**9, price, price, price, price, 0.0])
        else:
            bars.append([start + k * 60 * 10**9, price, price + 2, price - 2, price + 1, 5.0])
    return {"symbol": "EURUSD", "utc_date": d.isoformat(), "point": 0.00001, "bars": bars}


def test_load_symbol_skips_placeholders_and_filler_bars(tmp_path):
    (tmp_path / "2025-01-06.json").write_text(json.dumps(_day(date(2025, 1, 6), 105000)))
    (tmp_path / "2025-01-07.json").write_text("")  # placeholder from an aborted download
    (tmp_path / "2025-01-08.json").write_text(json.dumps(_day(date(2025, 1, 8), 106000, filler=True)))
    m = mm.load_symbol(tmp_path)
    assert m["traded_days"] == 2 and len(m["dates"]) == 3  # two data files over a three-day calendar
    assert m["close"][0] == 105001 and m["traded"][0]
    assert m["close"][1440] == 105001 and not m["traded"][1440]  # placeholder day carried forward
    assert not m["traded"][2 * 1440]  # filler bars are not trades
    assert m["high"][2] == 105002 and m["low"][2] == 104998


def test_lockbox_refused(tmp_path):
    (tmp_path / "2026-07-01.json").write_text(json.dumps(_day(date(2026, 7, 1), 1)))
    with pytest.raises(ValueError):
        mm.load_symbol(tmp_path)
