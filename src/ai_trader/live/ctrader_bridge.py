"""cTrader Open API bridge (demo-first): places bracket orders for shadow decisions and audits
everything. Protocol: protobuf messages framed as 4-byte big-endian length + ProtoMessage over
TLS (demo host demo.ctraderapi.com:5035, live host live.ctraderapi.com:5035).

Safety built in, in this order, and none can be switched off from a decision file:
- demo only: the account returned for the access token must report ``isLive == False``; a
  live account is refused at connect time (``allow_live`` exists for a later, separate gate
  and is False here).
- kill switch: if ``config/ctrader_kill_switch`` exists, no order is sent.
- limits: ``max_lots`` (default 0.01), ``max_open_positions`` (default 1), symbol allowlist.
- every request and response is appended to the audit log (JSONL) before and after sending.

Credentials live in a local JSON file (gitignored): {"client_id", "client_secret",
"access_token", "account_id" (ctidTraderAccountId, optional: taken from the token's account
list if absent), "host" (optional)}. Message definitions come from the ``ctrader-open-api``
package (Spotware's published protobufs); only its message classes are used, not its client.

Decision translation: shadow decisions are in 6E ticks (0.00005). On EURUSD CFD the same
distance is stop_ticks x 0.00005 in price; cTrader's relative stop/target fields take
1/100000 of a price unit, so relative = stop_ticks x 5. Volume is in cents of units:
0.01 lot = 1,000 units = 100,000.
"""

from __future__ import annotations

import json
import socket
import ssl
import struct
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:  # message definitions only
    from ctrader_open_api.messages import OpenApiCommonMessages_pb2 as C
    from ctrader_open_api.messages import OpenApiMessages_pb2 as M
    from ctrader_open_api.messages import OpenApiModelMessages_pb2 as MM
except ImportError:  # pragma: no cover - reported at use
    C = M = MM = None

DEMO_HOST = ("demo.ctraderapi.com", 5035)
TICK_6E = 0.00005
RELATIVE_PER_PRICE_UNIT = 100_000
UNITS_PER_LOT = 100_000
VOLUME_CENTS = 100


class BridgeError(RuntimeError):
    pass


def _require_proto():
    if M is None:
        raise BridgeError("ctrader-open-api package not installed (pip install ctrader-open-api)")


# ----------------------------------------------------------------------------- transports
class TlsTransport:
    """Blocking framed transport; one request at a time, heartbeats answered in between."""

    def __init__(self, host=DEMO_HOST, timeout: float = 20.0):
        self.host, self.timeout = host, timeout
        self.sock = None

    def connect(self):
        raw = socket.create_connection(self.host, timeout=self.timeout)
        ctx = ssl.create_default_context()
        self.sock = ctx.wrap_socket(raw, server_hostname=self.host[0])

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def _send(self, msg) -> None:
        wrapper = C.ProtoMessage(payloadType=msg.payloadType, payload=msg.SerializeToString(),
                                 clientMsgId=getattr(msg, "_client_msg_id", None) or str(uuid.uuid4()))
        data = wrapper.SerializeToString()
        self.sock.sendall(struct.pack(">I", len(data)) + data)
        return wrapper.clientMsgId

    def _recv(self):
        head = self._exact(4)
        (n,) = struct.unpack(">I", head)
        wrapper = C.ProtoMessage()
        wrapper.ParseFromString(self._exact(n))
        return wrapper

    def _exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise BridgeError("connection closed")
            buf += chunk
        return buf

    def request(self, msg, expect: tuple[int, ...], timeout: float | None = None):
        """Send msg, return the first ProtoMessage whose payloadType is in `expect` (errors raise)."""
        msg_id = self._send(msg)
        deadline = time.time() + (timeout or self.timeout)
        while time.time() < deadline:
            w = self._recv()
            if w.payloadType == C.ProtoPayloadType.Value("HEARTBEAT_EVENT"):
                hb = C.ProtoHeartbeatEvent()
                self._send(hb)
                continue
            if w.payloadType == MM.ProtoOAPayloadType.Value("PROTO_OA_ERROR_RES"):
                err = M.ProtoOAErrorRes()
                err.ParseFromString(w.payload)
                raise BridgeError(f"{err.errorCode}: {err.description}")
            if w.payloadType in expect and (not w.clientMsgId or w.clientMsgId == msg_id):
                return w
        raise BridgeError("timeout waiting for response")


class MockTransport:
    """Scripted responses keyed by request payloadType, for tests and dry runs."""

    def __init__(self, handlers: dict):
        self.handlers = handlers
        self.sent = []

    def connect(self):
        pass

    def close(self):
        pass

    def request(self, msg, expect, timeout=None):
        self.sent.append(msg)
        resp = self.handlers[msg.payloadType](msg)
        return C.ProtoMessage(payloadType=resp.payloadType, payload=resp.SerializeToString(), clientMsgId="mock")


# ----------------------------------------------------------------------------- bridge
def _pt(name: str) -> int:
    return MM.ProtoOAPayloadType.Value(name)


def _parse(wrapper, cls):
    msg = cls()
    msg.ParseFromString(wrapper.payload)
    return msg


class CTraderBridge:
    def __init__(self, transport, config: dict, audit_path: Path, kill_switch: Path = Path("config/ctrader_kill_switch"),
                 max_lots: float = 0.01, max_open_positions: int = 1, symbols: tuple[str, ...] = ("EURUSD",),
                 allow_live: bool = False):
        _require_proto()
        self.t, self.cfg, self.audit_path = transport, config, audit_path
        self.kill_switch, self.max_lots, self.max_open = kill_switch, max_lots, max_open_positions
        self.symbols_allowed, self.allow_live = symbols, allow_live
        self.account_id = None
        self.symbol_ids: dict[str, int] = {}
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    # audit
    def _audit(self, kind: str, **fields):
        row = {"utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "kind": kind, **fields}
        with self.audit_path.open("a") as fh:
            fh.write(json.dumps(row, default=str) + "\n")

    def _req(self, msg, expect_names: tuple[str, ...], cls):
        self._audit("send", type=msg.DESCRIPTOR.name, body=_public(msg))
        try:
            w = self.t.request(msg, tuple(_pt(n) for n in expect_names))
        except BridgeError as exc:
            self._audit("error", type=msg.DESCRIPTOR.name, error=str(exc))
            raise
        resp = _parse(w, cls)
        self._audit("recv", type=resp.DESCRIPTOR.name, body=_public(resp))
        return resp

    # lifecycle
    def connect(self) -> dict:
        self.t.connect()
        self._req(M.ProtoOAApplicationAuthReq(clientId=self.cfg["client_id"], clientSecret=self.cfg["client_secret"]),
                  ("PROTO_OA_APPLICATION_AUTH_RES",), M.ProtoOAApplicationAuthRes)
        accounts = self._req(M.ProtoOAGetAccountListByAccessTokenReq(accessToken=self.cfg["access_token"]),
                             ("PROTO_OA_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES",), M.ProtoOAGetAccountListByAccessTokenRes)
        wanted = self.cfg.get("account_id")
        chosen = None
        for acc in accounts.ctidTraderAccount:
            if wanted is None or acc.ctidTraderAccountId == int(wanted):
                chosen = acc
                break
        if chosen is None:
            raise BridgeError("account not found for this access token")
        if chosen.isLive and not self.allow_live:
            self._audit("refused", reason="live account; bridge is demo-only")
            raise BridgeError("refusing to operate on a LIVE account")
        self.account_id = chosen.ctidTraderAccountId
        self._req(M.ProtoOAAccountAuthReq(ctidTraderAccountId=self.account_id, accessToken=self.cfg["access_token"]),
                  ("PROTO_OA_ACCOUNT_AUTH_RES",), M.ProtoOAAccountAuthRes)
        syms = self._req(M.ProtoOASymbolsListReq(ctidTraderAccountId=self.account_id),
                         ("PROTO_OA_SYMBOLS_LIST_RES",), M.ProtoOASymbolsListRes)
        self.symbol_ids = {s.symbolName: s.symbolId for s in syms.symbol}
        missing = [s for s in self.symbols_allowed if s not in self.symbol_ids]
        if missing:
            raise BridgeError(f"symbols not offered by this account: {missing}")
        return {"account_id": self.account_id, "is_live": bool(chosen.isLive), "symbols": len(self.symbol_ids)}

    def close(self):
        self.t.close()

    # state
    def open_positions(self) -> list[dict]:
        rec = self._req(M.ProtoOAReconcileReq(ctidTraderAccountId=self.account_id),
                        ("PROTO_OA_RECONCILE_RES",), M.ProtoOAReconcileRes)
        return [{"position_id": p.positionId, "symbol_id": p.tradeData.symbolId,
                 "side": MM.ProtoOATradeSide.Name(p.tradeData.tradeSide), "volume": p.tradeData.volume,
                 "label": p.tradeData.label} for p in rec.position]

    # orders
    def place_bracket(self, symbol: str, side: str, lots: float, stop_price_distance: float,
                      target_price_distance: float, label: str, comment: str = "") -> dict:
        if self.kill_switch.exists():
            self._audit("refused", reason="kill switch present", label=label)
            raise BridgeError("kill switch present; no orders")
        if symbol not in self.symbols_allowed:
            raise BridgeError(f"symbol {symbol} not allowed")
        if lots <= 0 or lots > self.max_lots + 1e-12:
            raise BridgeError(f"lots {lots} exceeds max {self.max_lots}")
        if stop_price_distance <= 0 or target_price_distance <= 0:
            raise BridgeError("stop and target distances must be positive")
        if len(self.open_positions()) >= self.max_open:
            self._audit("refused", reason="max open positions", label=label)
            raise BridgeError("max open positions reached")
        req = M.ProtoOANewOrderReq(
            ctidTraderAccountId=self.account_id, symbolId=self.symbol_ids[symbol],
            orderType=MM.ProtoOAOrderType.Value("MARKET"), tradeSide=MM.ProtoOATradeSide.Value(side.upper()),
            volume=int(round(lots * UNITS_PER_LOT * VOLUME_CENTS)),
            relativeStopLoss=int(round(stop_price_distance * RELATIVE_PER_PRICE_UNIT)),
            relativeTakeProfit=int(round(target_price_distance * RELATIVE_PER_PRICE_UNIT)),
            label=label[:100], comment=comment[:100])
        ev = self._req(req, ("PROTO_OA_EXECUTION_EVENT",), M.ProtoOAExecutionEvent)
        out = {"execution_type": MM.ProtoOAExecutionType.Name(ev.executionType),
               "order_id": ev.order.orderId if ev.HasField("order") else None,
               "position_id": ev.position.positionId if ev.HasField("position") else None,
               "error": ev.errorCode if ev.HasField("errorCode") else None}
        self._audit("execution", label=label, **out)
        return out

    def close_position(self, position_id: int, volume: int) -> dict:
        ev = self._req(M.ProtoOAClosePositionReq(ctidTraderAccountId=self.account_id, positionId=position_id, volume=volume),
                       ("PROTO_OA_EXECUTION_EVENT",), M.ProtoOAExecutionEvent)
        return {"execution_type": MM.ProtoOAExecutionType.Name(ev.executionType)}


def _public(msg) -> dict:
    """Message fields for the audit log with secrets masked."""
    out = {}
    for f, v in msg.ListFields():
        if f.name in ("clientSecret", "accessToken"):
            out[f.name] = "***"
        elif f.label == f.LABEL_REPEATED:
            out[f.name] = f"[{len(v)} items]"
        elif hasattr(v, "ListFields"):
            out[f.name] = _public(v)
        else:
            out[f.name] = v
    return out


# ----------------------------------------------------------------------------- decisions -> intents
def intent_from_decision(decision: dict, lots: float = 0.01, symbol: str = "EURUSD") -> dict:
    """Translate a shadow decision (6E ticks) into a bracket intent for the CFD."""
    stop = float(decision["stop_ticks"]) * TICK_6E
    target = float(decision["target_ticks"]) * TICK_6E
    side = "BUY" if decision["side"] == "long" else "SELL"
    label = f"shadow {decision['date']} {decision['minute_utc']} {decision['side']}"
    return {"symbol": symbol, "side": side, "lots": lots, "stop_price_distance": stop,
            "target_price_distance": target, "label": label}


def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text())
    for k in ("client_id", "client_secret", "access_token"):
        if not cfg.get(k):
            raise BridgeError(f"config missing {k}")
    return cfg


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="cTrader demo bridge: connect check or place one decision")
    p.add_argument("--config", type=Path, default=Path("config/ctrader_demo.json"))
    p.add_argument("--audit", type=Path, default=Path("logs/ctrader/audit.jsonl"))
    p.add_argument("--check", action="store_true", help="connect, verify demo account and symbols, list positions")
    p.add_argument("--decision", type=Path, help="JSON file with one shadow decision to place as a bracket")
    a = p.parse_args(argv)
    cfg = load_config(a.config)
    host = tuple(cfg["host"]) if cfg.get("host") else DEMO_HOST
    bridge = CTraderBridge(TlsTransport(host), cfg, a.audit)
    info = bridge.connect()
    print("connected:", info)
    try:
        if a.check:
            print("open positions:", bridge.open_positions())
        if a.decision:
            intent = intent_from_decision(json.loads(a.decision.read_text()))
            print("placing:", intent)
            print(bridge.place_bracket(**intent))
    finally:
        bridge.close()


if __name__ == "__main__":
    main()
