"""CFD stream in the live loop: bars from a fake bridge -> decision -> placed / would_place, idempotent."""

from datetime import datetime, timezone
from pathlib import Path

from ai_trader.live import live_loop as ll
from ai_trader.live import cfd_signals as cs


class FakeBridge:
    def __init__(self, bars):
        self._bars, self.placed = bars, []

    def bars(self, symbol, count):
        return self._bars[-count:]

    def place_bracket(self, **intent):
        self.placed.append(intent)
        return {"execution_type": "ORDER_FILLED", "position_id": 7, "entry_price": 1.0, "error": None}

    def close_position(self, pid, volume=0):
        return {"execution_type": "ORDER_FILLED"}


def test_cfd_cycle_places_once(tmp_path, monkeypatch):
    now = datetime(2026, 10, 19, 13, 36, 10, tzinfo=timezone.utc)
    dec = {"symbol": "XAUUSD", "date": "2026-10-19", "minute_utc": "13:35", "side": "long", "entry": 4000.0,
           "stop_price_distance": 6.0, "target_price_distance": 18.0, "atr": 4.0, "hold": 240, "rule": "reversal_v1_bookfree"}
    monkeypatch.setattr(cs, "decide", lambda sym, bars, t: dec)
    state = ll.LoopState(tmp_path / "sent.jsonl")
    b = FakeBridge([[1, 1, 1, 1, 1, 1]] * 10)
    logs = []
    out = ll.cfd_cycle(now, state, ["XAUUSD"], b, armed=True, lots=0.01, log=logs.append)
    assert len(out) == 1 and out[0]["action"] == "placed" and b.placed[0]["symbol"] == "XAUUSD"
    assert ll.cfd_cycle(now, state, ["XAUUSD"], b, armed=True, lots=0.01, log=logs.append) == []  # same key: not resent
    dec["minute_utc"] = "13:36"   # next minute, same symbol still open: skipped, not refused
    assert ll.cfd_cycle(now.replace(minute=37), state, ["XAUUSD"], b, armed=True, lots=0.01, log=logs.append) == []
    assert len(b.placed) == 1
    dec["minute_utc"] = "13:35"
    # outside the window nothing is evaluated
    assert ll.cfd_cycle(now.replace(hour=11), state, ["XAUUSD"], b, armed=True, lots=0.01, log=logs.append) == []
    # unarmed: logged only
    s2 = ll.LoopState(tmp_path / "s2.jsonl")
    out = ll.cfd_cycle(now, s2, ["XAUUSD"], b, armed=False, lots=0.01, log=logs.append)
    assert out[0]["action"] == "would_place" and len(b.placed) == 1
    # time exit via the shared housekeeping
    later = now.replace(hour=17, minute=40)
    acts = ll.cycle(later, state, tmp_path / "store", str(tmp_path / "none-*.jsonl"), None, None, b, True, log=logs.append)
    assert any(a["action"] == "closed" for a in acts)
