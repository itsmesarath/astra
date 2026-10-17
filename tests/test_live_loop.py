"""Live loop: fresh decisions become orders once, housekeeping closes them, unarmed runs only log."""

import json
from datetime import datetime, timezone
from pathlib import Path

from ai_trader.live import live_loop as ll


class FakeBridge:
    def __init__(self):
        self.placed, self.closed = [], []

    def place_bracket(self, **intent):
        self.placed.append(intent)
        return {"execution_type": "ORDER_FILLED", "position_id": 42}

    def close_position(self, position_id, volume):
        self.closed.append((position_id, volume))
        return {"execution_type": "ORDER_FILLED"}


def _decision(date="2026-10-19", minute="07:35", side="long"):
    return {"date": date, "minute_utc": minute, "side": side, "stop_ticks": 12.0, "target_ticks": 36.0}


def test_cycle_places_once_and_closes_after_hold(tmp_path, monkeypatch):
    monkeypatch.setattr(ll, "convert_today", lambda g, s: 5)
    monkeypatch.setattr(ll, "fresh_decisions", lambda store, wb, wk, now: [_decision()])
    state = ll.LoopState(tmp_path / "sent.jsonl")
    bridge = FakeBridge()
    now = datetime(2026, 10, 19, 7, 35, tzinfo=timezone.utc)
    acts = ll.cycle(now, state, tmp_path, "*.jsonl", None, None, bridge, armed=True, log=lambda s: None)
    assert [a["action"] for a in acts] == ["placed"] and len(bridge.placed) == 1
    assert bridge.placed[0]["side"] == "BUY" and bridge.placed[0]["lots"] == 0.01
    # same minute again: nothing new
    acts = ll.cycle(now, state, tmp_path, "*.jsonl", None, None, bridge, armed=True, log=lambda s: None)
    assert acts == [] and len(bridge.placed) == 1
    # four hours later: time exit
    later = datetime(2026, 10, 19, 11, 36, tzinfo=timezone.utc)
    monkeypatch.setattr(ll, "fresh_decisions", lambda *a: [])
    acts = ll.cycle(later, state, tmp_path, "*.jsonl", None, None, bridge, armed=True, log=lambda s: None)
    assert [a["action"] for a in acts] == ["closed"] and bridge.closed == [(42, 100000)]
    rows = [json.loads(l) for l in (tmp_path / "sent.jsonl").read_text().splitlines()]
    assert [r["action"] for r in rows] == ["placed", "closed"]
    # restart from disk: still nothing to close
    state2 = ll.LoopState(tmp_path / "sent.jsonl")
    assert state2.open_orders() == []


def test_unarmed_only_logs_and_refusals_are_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(ll, "convert_today", lambda g, s: 0)
    monkeypatch.setattr(ll, "fresh_decisions", lambda *a: [_decision(side="short")])
    state = ll.LoopState(tmp_path / "sent.jsonl")
    now = datetime(2026, 10, 19, 7, 35, tzinfo=timezone.utc)
    acts = ll.cycle(now, state, tmp_path, "*.jsonl", None, None, None, armed=False, log=lambda s: None)
    assert acts[0]["action"] == "would_place" and acts[0]["intent"]["side"] == "SELL"

    class Refusing(FakeBridge):
        def place_bracket(self, **intent):
            raise RuntimeError("kill switch present")

    state = ll.LoopState(tmp_path / "sent2.jsonl")
    acts = ll.cycle(now, state, tmp_path, "*.jsonl", None, None, Refusing(), armed=True, log=lambda s: None)
    assert acts[0]["action"] == "refused" and "kill switch" in acts[0]["error"]


def test_outside_window_no_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(ll, "fresh_decisions", lambda *a: [_decision(minute="12:00")])
    state = ll.LoopState(tmp_path / "sent.jsonl")
    now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    assert ll.cycle(now, state, tmp_path, "*.jsonl", None, None, FakeBridge(), armed=True, log=lambda s: None) == []
