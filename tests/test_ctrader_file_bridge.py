"""File bridge against a fake cBot (a thread that answers intent files the way AiTraderFileBridge does)."""

import json
import threading
import time
from pathlib import Path

import pytest

from ai_trader.live import ctrader_file_bridge as fb


class FakeCBot(threading.Thread):
    def __init__(self, base: Path, is_live=False):
        super().__init__(daemon=True)
        self.base, self.is_live, self.stop = base, is_live, False
        self.positions = []
        (base / "orders").mkdir(parents=True)
        (base / "status.json").write_text(json.dumps({"running": True, "is_live": is_live}))

    def run(self):
        while not self.stop:
            for p in sorted((self.base / "orders").glob("*.json")):
                if p.name.endswith(".done.json") or (p.parent / (p.stem + ".done.json")).exists():
                    continue
                intent = json.loads(p.read_text())
                if (self.base / "KILL").exists():
                    res = {"ok": False, "error": "kill switch present"}
                elif self.is_live:
                    res = {"ok": False, "error": "live account refused"}
                elif intent["action"] == "reconcile":
                    res = {"ok": True, "is_live": self.is_live, "broker": "Demo", "balance": 10000.0, "positions": list(self.positions)}
                elif intent["action"] == "place":
                    pos = {"position_id": 900 + len(self.positions), "symbol": intent["symbol"], "side": intent["side"],
                           "volume": int(intent["lots"] * 100000), "entry": 1.1, "label": "aitrader " + intent["label"]}
                    self.positions.append(pos)
                    res = {"ok": True, "position_id": pos["position_id"], "entry_price": 1.1, "error": None}
                else:
                    self.positions = [q for q in self.positions if q["position_id"] != intent["position_id"]]
                    res = {"ok": True, "position_id": intent["position_id"], "error": None}
                (p.parent / (p.stem + ".done.json")).write_text(json.dumps(res))
            time.sleep(0.05)


def test_place_close_and_limits(tmp_path):
    bot = FakeCBot(tmp_path / "bot"); bot.start()
    b = fb.FileBridge(tmp_path / "bot", audit_path=tmp_path / "audit.jsonl", timeout=5)
    info = b.connect()
    assert info["is_live"] is False and info["positions"] == 0
    out = b.place_bracket("EURUSD", "BUY", 0.01, 0.0006, 0.0018, "shadow test")
    assert out["position_id"] == 900 and out["execution_type"] == "ORDER_FILLED"
    assert len(b.open_positions()) == 1
    with pytest.raises(fb.BridgeError, match="max open"):
        b.place_bracket("EURUSD", "SELL", 0.01, 0.0006, 0.0018, "second")
    with pytest.raises(fb.BridgeError, match="exceeds max"):
        b.place_bracket("EURUSD", "SELL", 0.05, 0.0006, 0.0018, "big")
    assert b.close_position(900)["execution_type"] == "ORDER_FILLED"
    assert b.open_positions() == []
    (tmp_path / "bot" / "KILL").write_text("")
    with pytest.raises(fb.BridgeError, match="kill switch"):
        b.place_bracket("EURUSD", "BUY", 0.01, 0.0006, 0.0018, "killed")
    bot.stop = True
    audit = (tmp_path / "audit.jsonl").read_text()
    assert '"kind": "send"' in audit and '"kind": "recv"' in audit


def test_live_account_refused_and_missing_cbot(tmp_path):
    bot = FakeCBot(tmp_path / "live", is_live=True); bot.start()
    b = fb.FileBridge(tmp_path / "live", audit_path=tmp_path / "a.jsonl", timeout=5)
    with pytest.raises(fb.BridgeError):
        b.connect()
    bot.stop = True
    with pytest.raises(fb.BridgeError, match="not found"):
        fb.FileBridge(tmp_path / "nothing", audit_path=tmp_path / "b.jsonl", timeout=1).connect()
