"""Mode isolation and safety contracts for current/future execution adapters."""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from ai_trader.risk.engine import RiskLimits
from ai_trader.trading.execution import ExecutionCosts, MarketQuote
from ai_trader.trading.gateway import (
    ExecutionGateway,
    ExecutionMode,
    ExecutionRequest,
    ExecutionStatus,
)
from ai_trader.trading.runtime import (
    ExecutionConfig,
    ExecutionModeUnavailable,
    create_execution_gateway,
    main,
)


def gateway(*, cash="10000", max_order="1"):
    return create_execution_gateway(
        ExecutionConfig(),
        initial_cash_usdt=Decimal(cash),
        risk_limits=RiskLimits(
            *(Decimal(v) for v in ("1", max_order, "10000", "10000", "100", "200"))
        ),
        execution_costs=ExecutionCosts(Decimal("10"), Decimal("5")),
    )


def request(request_id="entry-1", intent="LONG"):
    return ExecutionRequest(
        request_id,
        intent,
        Decimal("0.1"),
        MarketQuote(Decimal("100"), Decimal("101"), 1000),
    )


def test_paper_default_and_contract():
    broker = gateway()
    assert isinstance(broker, ExecutionGateway)
    assert broker.mode == ExecutionMode.PAPER
    receipt = broker.submit(request())
    assert receipt.status == ExecutionStatus.FILLED
    assert receipt.filled_quantity_btc == Decimal("0.1")
    assert receipt.average_fill_price_usdt == Decimal("101.0505")
    assert receipt.fill_side == "BUY"
    assert receipt.fee_usdt > 0
    assert broker.get_receipt("entry-1") == receipt
    assert broker.get_receipt("not-seen") is None


@pytest.mark.parametrize("mode", ["spot_testnet", "spot_live"])
def test_authenticated_modes_fail_before_paper_allocation_or_network(mode, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No account lookup, paper fallback or network is allowed")

    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr("ai_trader.trading.runtime.PaperPortfolio.create", forbidden)
    # Even plausible credentials must never silently enable execution.
    monkeypatch.setenv("BINANCE_API_KEY", "not-a-real-key")
    with pytest.raises(ExecutionModeUnavailable, match="reserved but disabled"):
        create_execution_gateway(
            ExecutionConfig(mode),
            initial_cash_usdt=Decimal("1000"),
            risk_limits=None,
            execution_costs=None,
        )


@pytest.mark.parametrize("mode", ["live", "PAPER", "", None, True])
def test_invalid_modes_are_not_coerced_to_paper(mode):
    with pytest.raises(ValueError):
        ExecutionConfig(mode)


def test_mode_is_immutable_and_namespaces_are_separate():
    assert len({ExecutionConfig(mode).state_namespace for mode in ExecutionMode}) == 3
    config = ExecutionConfig()
    with pytest.raises(FrozenInstanceError):
        config.mode = ExecutionMode.SPOT_LIVE


def test_retries_cannot_reopen_after_position_was_closed():
    broker = gateway()
    original = broker.submit(request())
    assert broker.submit(request("exit-1", "FLAT")).fill_side == "SELL"
    assert broker.submit(request()) == original
    assert broker.submit(request("still-flat", "FLAT")).status == ExecutionStatus.NOOP


def test_conflicting_retry_is_rejected():
    broker = gateway()
    broker.submit(request())
    with pytest.raises(ValueError, match="different intent"):
        broker.submit(replace(request(), entry_quantity_btc=Decimal("0.2")))


def test_concurrent_duplicates_have_one_receipt():
    broker = gateway()
    with ThreadPoolExecutor(max_workers=4) as executor:
        receipts = list(executor.map(broker.submit, [request()] * 8))
    assert all(receipt is receipts[0] for receipt in receipts)
    assert receipts[0].status == ExecutionStatus.FILLED


def test_kill_switch_blocks_entries_but_allows_flattening():
    broker = gateway()
    broker.submit(request())
    broker.set_kill_switch(True)
    assert broker.submit(request("exit", "FLAT")).status == ExecutionStatus.FILLED
    rejected = broker.submit(request("new-entry"))
    assert rejected.status == ExecutionStatus.REJECTED
    assert rejected.reason == "risk_rejected:kill_switch_active"
    broker.set_kill_switch(False)
    # A retry is the old result; a genuinely new attempt needs a new ID.
    assert broker.submit(request("new-entry")) == rejected
    assert broker.submit(request("new-attempt")).status == ExecutionStatus.FILLED


def test_risk_limits_still_apply_through_interface():
    receipt = gateway(max_order="0.01").submit(request())
    assert receipt.status == ExecutionStatus.REJECTED
    assert receipt.reason == "risk_rejected:order_quantity_limit_exceeded"


def test_spot_cash_includes_fees_and_slippage():
    receipt = gateway(cash="10.1").submit(request())
    assert receipt.status == ExecutionStatus.REJECTED
    assert receipt.reason == "insufficient_spot_cash"
    assert receipt.filled_quantity_btc == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"intent": "SHORT"},
        {"symbol": "ETHUSDT"},
        {"request_id": " "},
        {"request_id": "a" * 37},
        {"entry_quantity_btc": Decimal("Infinity")},
        {"entry_quantity_btc": Decimal("NaN")},
        {"entry_quantity_btc": Decimal("0")},
    ],
)
def test_invalid_requests_are_rejected(changes):
    with pytest.raises(ValueError):
        replace(request(), **changes)


def test_independent_paper_runs_do_not_share_balances_or_requests():
    first, second = gateway(), gateway()
    first.submit(request())
    assert second.get_receipt("entry-1") is None
    assert second.submit(request("exit", "FLAT")).status == ExecutionStatus.NOOP


@pytest.mark.parametrize("mode,exit_code", [("paper", 0), ("spot_testnet", 2), ("spot_live", 2)])
def test_mode_check_cli(mode, exit_code, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["runtime", "--mode", mode, "--check"])
    if exit_code:
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == exit_code
        assert "disabled" in capsys.readouterr().err
    else:
        main()
        payload = json.loads(capsys.readouterr().out)
        assert payload["mode"] == "paper"
        assert payload["orders_submitted"] == 0
