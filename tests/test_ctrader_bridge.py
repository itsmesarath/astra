"""cTrader bridge against a scripted mock transport: demo guard, limits, order field encoding."""

from pathlib import Path

import pytest

pytest.importorskip("ctrader_open_api")
from ctrader_open_api.messages import OpenApiMessages_pb2 as M  # noqa: E402
from ctrader_open_api.messages import OpenApiModelMessages_pb2 as MM  # noqa: E402

from ai_trader.live import ctrader_bridge as cb  # noqa: E402

CFG = {"client_id": "id", "client_secret": "secret", "access_token": "token"}


def handlers(is_live=False, positions=0):
    def accounts(_):
        res = M.ProtoOAGetAccountListByAccessTokenRes(accessToken="token")
        acc = res.ctidTraderAccount.add()
        acc.ctidTraderAccountId, acc.isLive = 12345, is_live
        return res

    def symbols(_):
        res = M.ProtoOASymbolsListRes(ctidTraderAccountId=12345)
        s = res.symbol.add()
        s.symbolId, s.symbolName = 1, "EURUSD"
        return res

    def reconcile(_):
        res = M.ProtoOAReconcileRes(ctidTraderAccountId=12345)
        for k in range(positions):
            p = res.position.add()
            p.positionId = 100 + k
            p.positionStatus = MM.ProtoOAPositionStatus.Value("POSITION_STATUS_OPEN")
            p.swap = 0
            p.tradeData.symbolId, p.tradeData.volume = 1, 100000
            p.tradeData.tradeSide = MM.ProtoOATradeSide.Value("BUY")
            p.tradeData.openTimestamp = 0
        return res

    def new_order(req):
        ev = M.ProtoOAExecutionEvent(ctidTraderAccountId=12345, executionType=MM.ProtoOAExecutionType.Value("ORDER_FILLED"))
        ev.order.orderId = 777
        ev.order.tradeData.symbolId = req.symbolId
        ev.order.tradeData.tradeSide = req.tradeSide
        ev.order.tradeData.volume = req.volume
        ev.order.orderType = req.orderType
        ev.order.orderStatus = MM.ProtoOAOrderStatus.Value("ORDER_STATUS_FILLED")
        ev.order.tradeData.openTimestamp = 0
        ev.position.positionId = 999
        ev.position.positionStatus = MM.ProtoOAPositionStatus.Value("POSITION_STATUS_OPEN")
        ev.position.swap = 0
        ev.position.tradeData.symbolId = req.symbolId
        ev.position.tradeData.tradeSide = req.tradeSide
        ev.position.tradeData.volume = req.volume
        ev.position.tradeData.openTimestamp = 0
        return ev

    pt = MM.ProtoOAPayloadType.Value
    return {
        pt("PROTO_OA_APPLICATION_AUTH_REQ"): lambda _: M.ProtoOAApplicationAuthRes(),
        pt("PROTO_OA_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ"): accounts,
        pt("PROTO_OA_ACCOUNT_AUTH_REQ"): lambda _: M.ProtoOAAccountAuthRes(ctidTraderAccountId=12345),
        pt("PROTO_OA_SYMBOLS_LIST_REQ"): symbols,
        pt("PROTO_OA_RECONCILE_REQ"): reconcile,
        pt("PROTO_OA_NEW_ORDER_REQ"): new_order,
    }


def test_connect_refuses_live_account(tmp_path):
    bridge = cb.CTraderBridge(cb.MockTransport(handlers(is_live=True)), CFG, tmp_path / "audit.jsonl",
                              kill_switch=tmp_path / "kill")
    with pytest.raises(cb.BridgeError, match="LIVE"):
        bridge.connect()
    assert "refused" in (tmp_path / "audit.jsonl").read_text()


def test_bracket_order_encoding_and_limits(tmp_path):
    t = cb.MockTransport(handlers())
    bridge = cb.CTraderBridge(t, CFG, tmp_path / "audit.jsonl", kill_switch=tmp_path / "kill")
    info = bridge.connect()
    assert info == {"account_id": 12345, "is_live": False, "symbols": 1}
    decision = {"date": "2026-10-19", "minute_utc": "07:35", "side": "long", "stop_ticks": 12.0, "target_ticks": 36.0}
    intent = cb.intent_from_decision(decision)
    assert intent["side"] == "BUY" and abs(intent["stop_price_distance"] - 0.0006) < 1e-12
    out = bridge.place_bracket(**intent)
    assert out["execution_type"] == "ORDER_FILLED" and out["position_id"] == 999
    req = [m for m in t.sent if m.DESCRIPTOR.name == "ProtoOANewOrderReq"][0]
    assert req.volume == 100000  # 0.01 lot = 1,000 units in cents
    assert req.relativeStopLoss == 60 and req.relativeTakeProfit == 180  # 12 ticks x 5, 36 ticks x 5
    assert req.orderType == MM.ProtoOAOrderType.Value("MARKET") and req.label.startswith("shadow 2026-10-19")
    with pytest.raises(cb.BridgeError, match="exceeds max"):
        bridge.place_bracket("EURUSD", "BUY", 0.02, 0.0006, 0.0018, "too big")
    with pytest.raises(cb.BridgeError, match="not allowed"):
        bridge.place_bracket("GBPUSD", "BUY", 0.01, 0.0006, 0.0018, "wrong symbol")
    audit = (tmp_path / "audit.jsonl").read_text()
    assert "secret" not in audit and '"clientSecret": "***"' in audit


def test_kill_switch_and_max_positions(tmp_path):
    bridge = cb.CTraderBridge(cb.MockTransport(handlers(positions=1)), CFG, tmp_path / "audit.jsonl",
                              kill_switch=tmp_path / "kill")
    bridge.connect()
    with pytest.raises(cb.BridgeError, match="max open"):
        bridge.place_bracket("EURUSD", "SELL", 0.01, 0.0006, 0.0018, "second")
    (tmp_path / "kill").write_text("stop")
    with pytest.raises(cb.BridgeError, match="kill switch"):
        bridge.place_bracket("EURUSD", "SELL", 0.01, 0.0006, 0.0018, "killed")
