"""File bridge to the AiTraderFileBridge cBot running inside cTrader (demo), no Open API needed.

Same interface as ``ctrader_bridge.CTraderBridge`` (connect / place_bracket / open_positions /
close_position) so ``live_loop`` can use either. Intents are JSON files in the cBot's data folder
``Documents\\cAlgo\\Data\\cBots\\AiTraderFileBridge\\orders``; the cBot answers with ``<id>.done.json``.
The cBot enforces demo-only, max lots, max positions, symbol allowlist and a KILL file; this side
repeats the lot/position checks and keeps the audit JSONL.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


class BridgeError(RuntimeError):
    pass


def default_base() -> Path:
    env = os.environ.get("CTRADER_BRIDGE_DIR")
    if env:
        return Path(env)
    return Path.home() / "Documents" / "cAlgo" / "Data" / "cBots" / "AiTraderFileBridge"


class FileBridge:
    def __init__(self, base: Path | None = None, audit_path: Path = Path("logs/ctrader/file_bridge_audit.jsonl"),
                 max_lots: float = 0.01, max_open_positions: int = 1, symbols: tuple[str, ...] = ("EURUSD",),
                 timeout: float = 15.0):
        self.base = base or default_base()
        self.orders = self.base / "orders"
        self.audit_path = audit_path
        self.max_lots, self.max_open, self.symbols_allowed, self.timeout = max_lots, max_open_positions, symbols, timeout
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def _audit(self, kind: str, **fields):
        with self.audit_path.open("a") as fh:
            fh.write(json.dumps({"utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "kind": kind, **fields}) + "\n")

    def _send(self, intent: dict) -> dict:
        if not self.orders.exists():
            raise BridgeError(f"cBot folder not found: {self.orders} (is AiTraderFileBridge running in cTrader?)")
        status_path = self.base / "status.json"
        if status_path.exists():
            status = json.loads(status_path.read_text() or "{}")
            if not status.get("running", False):
                raise BridgeError("cBot is not running")
        intent = {"id": uuid.uuid4().hex, **intent}
        path = self.orders / f"{intent['id']}.json"
        tmp = path.with_suffix(".partial")
        self._audit("send", **intent)
        tmp.write_text(json.dumps(intent))
        tmp.replace(path)
        done = self.orders / f"{intent['id']}.done.json"
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            if done.exists():
                text = done.read_text()
                if text.strip():
                    result = json.loads(text)
                    self._audit("recv", id=intent["id"], **result)
                    return result
            time.sleep(0.25)
        self._audit("timeout", id=intent["id"])
        raise BridgeError("no response from cBot within timeout")

    # interface shared with CTraderBridge
    def connect(self) -> dict:
        r = self._send({"action": "reconcile"})
        if not r.get("ok"):
            raise BridgeError(r.get("error") or "reconcile failed")
        if r.get("is_live"):
            self._audit("refused", reason="live account")
            raise BridgeError("refusing to operate on a LIVE account")
        return {"is_live": bool(r.get("is_live")), "broker": r.get("broker"), "balance": r.get("balance"),
                "positions": len(r.get("positions", []))}

    def open_positions(self) -> list[dict]:
        r = self._send({"action": "reconcile"})
        if not r.get("ok"):
            raise BridgeError(r.get("error") or "reconcile failed")
        return r.get("positions", [])

    def place_bracket(self, symbol: str, side: str, lots: float, stop_price_distance: float,
                      target_price_distance: float, label: str, comment: str = "") -> dict:
        if symbol not in self.symbols_allowed:
            raise BridgeError(f"symbol {symbol} not allowed")
        if lots <= 0 or lots > self.max_lots + 1e-12:
            raise BridgeError(f"lots {lots} exceeds max {self.max_lots}")
        if stop_price_distance <= 0 or target_price_distance <= 0:
            raise BridgeError("stop and target distances must be positive")
        if len(self.open_positions()) >= self.max_open:
            raise BridgeError("max open positions reached")
        r = self._send({"action": "place", "symbol": symbol, "side": side.upper(), "lots": lots,
                        "stop_price_distance": stop_price_distance, "target_price_distance": target_price_distance,
                        "label": label[:80]})
        if not r.get("ok"):
            raise BridgeError(r.get("error") or "order refused")
        return {"execution_type": "ORDER_FILLED", "order_id": None, "position_id": r.get("position_id"),
                "entry_price": r.get("entry_price"), "error": None}

    def close_position(self, position_id: int, volume: int = 0) -> dict:
        r = self._send({"action": "close", "position_id": int(position_id)})
        if not r.get("ok"):
            raise BridgeError(r.get("error") or "close refused")
        return {"execution_type": "ORDER_FILLED"}

    def close(self):
        pass


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="cTrader file bridge check: reconcile the demo account through the cBot")
    p.add_argument("--base", type=Path, default=None)
    a = p.parse_args(argv)
    b = FileBridge(a.base)
    print("connected:", b.connect())
    print("open positions:", b.open_positions())


if __name__ == "__main__":
    main()
