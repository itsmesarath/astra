"""Atomic quote-only paper execution and durable risk, using synthetic data only."""

import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal, localcontext

import pytest
from test_paper_lifecycle import event, order, paper_case

from ai_trader.risk.engine import RiskLimits
from ai_trader.trading.durable_paper_gateway import (
    DAY_NS,
    DurablePaperGateway,
    PaperGatewayConfig,
    PaperQuoteRequest,
)
from ai_trader.trading.execution import ExecutionCosts
from ai_trader.trading.gateway import ExecutionMode, ExecutionStatus
from ai_trader.trading.paper_account import PaperAccountSeed
from ai_trader.trading.paper_lifecycle import PaperExitOrder
from ai_trader.trading.trade_journal import JournalConflict, JournalError, TradeJournal

D = Decimal
DEFAULT_QUANTITY = D("0.001")


def config(**limits):
    values = dict(
        max_position_btc=D("0.01"),
        max_order_btc=D("0.01"),
        max_order_notional_usdt=D("1000"),
        max_position_notional_usdt=D("1000"),
        max_daily_loss_usdt=D("10"),
        max_drawdown_usdt=D("20"),
    )
    return PaperGatewayConfig(RiskLimits(**(values | limits)), ExecutionCosts(D("10"), D("0")), 100)


def request(order_id="order-1", **changes):
    return replace(PaperQuoteRequest(order_id, D("59990"), D("60000"), 1200, 1200), **changes)


def prepare(journal, cfg, *, order_id="order-1", time=1100, quantity=DEFAULT_QUANTITY):
    case = replace(
        paper_case(),
        case_id=order_id + "-case",
        decision_at_ns=time - 1,
        risk_config_sha256=cfg.risk_config_sha256,
        plan=replace(paper_case().plan, expires_at_ns=time + 1000),
    )
    journal.append_case(case)
    journal.append_order(
        replace(
            order(),
            order_id=order_id,
            case_id=case.case_id,
            case_sha256=case.sha256,
            requested_at_ns=time,
            quantity_btc=quantity,
        )
    )


def open_journal(path, **changes):
    return TradeJournal(path, run_id="run-1", mode="paper", **changes)


@pytest.fixture
def gateway(tmp_path):
    with TradeJournal.create(tmp_path / "j.sqlite", run_id="run-1", mode="paper") as journal:
        journal.initialize_account(PaperAccountSeed(D("100"), 1000))
        instance = DurablePaperGateway.initialize(journal, config())
        prepare(journal, instance.config)
        yield instance


def prepare_exit(gateway, *, order_id="exit-1", time=2200):
    gateway.journal.append_exit_order(PaperExitOrder(order_id, "order-1", D("0.001"), time, "stop"))
    return request(
        order_id, bid_usdt=D("61000"), ask_usdt=D("61010"), quote_at_ns=time, observed_at_ns=time
    )


def test_fill_retry_reopen_and_exit_accounting(gateway, tmp_path):
    receipt = gateway.execute(request())
    assert receipt.mode == ExecutionMode.PAPER
    assert receipt.status == ExecutionStatus.FILLED
    assert receipt.filled_quantity_btc == D("0.001")
    assert receipt.average_fill_price_usdt == D("60000")
    assert receipt.fee_usdt == D("0.06")
    assert gateway.execute(request()) == receipt
    before = gateway.journal.account_state()
    with open_journal(tmp_path / "j.sqlite") as journal:
        reopened = DurablePaperGateway(journal, config())
        assert reopened.execute(request()) == receipt
        assert journal.account_state() == before
        exit_receipt = reopened.execute(prepare_exit(reopened))
        assert exit_receipt.fill_side == "SELL"
        assert journal.account_state().cash_usdt == D("100.879")
        assert reopened.risk_checkpoint().cumulative_realized_usdt == D("0.879")
    assert len(gateway.journal.order_events("order-1")) == 2


def test_request_conflict_does_not_refill(gateway):
    gateway.execute(request())
    with pytest.raises(JournalConflict):
        gateway.execute(request(ask_usdt=D("60001")))
    assert gateway.journal.account_state().position_btc == D("0.001")


def test_insufficient_cash_rejected_before_fill(gateway):
    receipt = gateway.execute(request(bid_usdt=D("99999"), ask_usdt=D("100000")))
    assert receipt.status == ExecutionStatus.REJECTED
    assert receipt.reason == "insufficient_spot_cash"
    assert gateway.journal.account_state().cash_usdt == D("100")
    assert [e.kind for e in gateway.journal.order_events("order-1")] == ["REJECTED"]


@pytest.mark.parametrize(
    "limits, reason",
    [
        ({"max_order_btc": D("0.0005")}, "order_quantity_limit_exceeded"),
        ({"max_position_btc": D("0.0005")}, "position_quantity_limit_exceeded"),
        ({"max_order_notional_usdt": D("50")}, "order_notional_limit_exceeded"),
        ({"max_position_notional_usdt": D("50")}, "position_notional_limit_exceeded"),
        ({"max_drawdown_usdt": D("0.01")}, "projected_drawdown_limit"),
    ],
)
def test_pre_fill_risk_veto(tmp_path, limits, reason):
    with TradeJournal.create(tmp_path / "j", run_id="run-1", mode="paper") as journal:
        journal.initialize_account(PaperAccountSeed(D("100"), 1000))
        gw = DurablePaperGateway.initialize(journal, config(**limits))
        prepare(journal, gw.config)
        receipt = gw.execute(request())
        assert receipt.reason == "risk_rejected:" + reason
        assert journal.account_state().position_btc == 0


def test_kill_switch_persists_but_does_not_block_exit(gateway, tmp_path):
    gateway.execute(request())
    gateway.set_kill_switch(True, observed_at_ns=2000)
    with open_journal(tmp_path / "j.sqlite") as journal:
        reopened = DurablePaperGateway(journal, config())
        assert reopened.risk_checkpoint().kill_switch_active
        assert reopened.execute(prepare_exit(reopened)).status == ExecutionStatus.FILLED
        prepare(journal, config(), order_id="new", time=2300)
        receipt = reopened.execute(request("new", quote_at_ns=2400, observed_at_ns=2400))
        assert receipt.reason == "risk_rejected:kill_switch_active"
        reopened.set_kill_switch(False, observed_at_ns=2500)
    assert not gateway.risk_checkpoint().kill_switch_active


def test_daily_loss_survives_restart_and_resets_on_utc_day(gateway, tmp_path):
    gateway.execute(request())
    exit_request = prepare_exit(gateway)
    gateway.execute(replace(exit_request, bid_usdt=D("40000"), ask_usdt=D("40010")))
    before = gateway.risk_checkpoint()
    assert before.cumulative_realized_usdt == D("-20.1")
    with open_journal(tmp_path / "j.sqlite") as journal:
        gw = DurablePaperGateway(journal, config())
        prepare(journal, config(), order_id="loss-gated", time=3000)
        receipt = gw.execute(request("loss-gated", quote_at_ns=3100, observed_at_ns=3100))
        assert receipt.reason == "risk_rejected:daily_loss_limit_reached"
        # Day changes reset the realized baseline, NOT the all-time peak/drawdown.
        gw.set_kill_switch(False, observed_at_ns=DAY_NS + 1000)
        checkpoint = gw.risk_checkpoint()
        assert checkpoint.day_start_realized_usdt == D("-20.1")
        assert checkpoint.peak_equity_usdt == before.peak_equity_usdt
        prepare(journal, config(), order_id="dd-gated", time=DAY_NS + 1100)
        receipt = gw.execute(
            request("dd-gated", quote_at_ns=DAY_NS + 1200, observed_at_ns=DAY_NS + 1200)
        )
        assert receipt.reason == "risk_rejected:drawdown_limit_reached"


def test_drawdown_peak_cannot_reset_by_reopening(gateway, tmp_path):
    gateway.execute(request())
    gateway.execute(prepare_exit(gateway))
    peak = gateway.risk_checkpoint().peak_equity_usdt
    assert peak == D("100.94")  # Pre-exit bid mark, before sell fee.
    with open_journal(tmp_path / "j.sqlite") as journal:
        gw = DurablePaperGateway.initialize(journal, config())
        assert gw.risk_checkpoint().peak_equity_usdt == peak
        with pytest.raises(JournalConflict):
            DurablePaperGateway(journal, config(max_drawdown_usdt=D("200")))


@pytest.mark.parametrize(
    "changes, reason",
    [
        ({"quote_at_ns": 1099}, "stale_quote"),
        ({"quote_at_ns": 2100, "observed_at_ns": 2100}, "entry_case_expired"),
    ],
)
def test_stale_or_expired_request_is_durable_rejection(gateway, changes, reason):
    req = request(**changes)
    receipt = gateway.execute(req)
    assert receipt.reason == reason
    assert gateway.execute(req) == receipt
    assert gateway.journal.account_state().position_btc == 0


def test_case_risk_configuration_must_match_run(gateway):
    value = replace(paper_case(), case_id="wrong-config")
    gateway.journal.append_case(value)
    gateway.journal.append_order(
        replace(order(), order_id="wrong", case_id=value.case_id, case_sha256=value.sha256)
    )
    assert gateway.execute(request("wrong")).reason == "case_risk_config_mismatch"


def test_unknown_or_external_events_require_reconciliation(gateway):
    gateway.journal.append_order_event(event("UNKNOWN"))
    with pytest.raises(JournalError, match="reconciliation"):
        gateway.execute(request())
    with pytest.raises(JournalError, match="reconciliation"):
        gateway.get_receipt("order-1")


def test_failure_after_fill_rolls_back_request_events_and_checkpoint(gateway):
    before = gateway.journal.account_state()
    checkpoint = gateway.risk_checkpoint()
    gateway.journal._db.execute("""CREATE TRIGGER fail_checkpoint
        BEFORE INSERT ON paper_risk_checkpoints BEGIN SELECT RAISE(ABORT, 'injected'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        gateway.execute(request())
    assert gateway.journal.account_state() == before
    assert gateway.risk_checkpoint() == checkpoint
    assert gateway.get_receipt("order-1") is None
    gateway.journal._db.execute("DROP TRIGGER fail_checkpoint")
    assert gateway.execute(request()).status == ExecutionStatus.FILLED


def test_concurrent_identical_requests_book_once(gateway, tmp_path):
    def execute(_):
        with open_journal(tmp_path / "j.sqlite") as journal:
            return DurablePaperGateway(journal, config()).execute(request())

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(execute, range(2)))
    assert receipts[0] == receipts[1]
    assert gateway.journal.account_state().position_btc == D("0.001")


def test_concurrent_entries_cannot_spend_same_cash(gateway, tmp_path):
    prepare(gateway.journal, config(), order_id="order-2")

    def execute(order_id):
        with open_journal(tmp_path / "j.sqlite") as journal:
            return DurablePaperGateway(journal, config()).execute(request(order_id))

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(execute, ("order-1", "order-2")))
    assert {r.status for r in receipts} == {ExecutionStatus.FILLED, ExecutionStatus.REJECTED}
    assert gateway.journal.account_state().cash_usdt == D("39.94")


def test_read_only_recovery(gateway, tmp_path):
    receipt = gateway.execute(request())
    with open_journal(tmp_path / "j.sqlite", read_only=True) as journal:
        reader = DurablePaperGateway(journal, config())
        assert reader.get_receipt("order-1") == receipt
        with pytest.raises(JournalError, match="read-only"):
            reader.set_kill_switch(True, observed_at_ns=2000)


def test_corrupt_checkpoint_fails_closed(gateway):
    db = gateway.journal._db
    db.execute("DROP TRIGGER paper_risk_checkpoints_no_update")
    db.execute("UPDATE paper_risk_checkpoints SET payload='{}'")
    with pytest.raises(JournalError, match="checksum"):
        gateway.execute(request())
    assert gateway.journal.account_state().position_btc == 0


def test_unknown_receipt_and_no_network(gateway, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network forbidden")

    monkeypatch.setattr("socket.socket", forbidden)
    assert gateway.get_receipt("missing") is None
    assert gateway.execute(request()).status == ExecutionStatus.FILLED


@pytest.mark.parametrize(
    "changes",
    [
        {"bid_usdt": D("NaN")},
        {"ask_usdt": 60000.0},
        {"quote_at_ns": True},
        {"bid_usdt": D("60001")},
        {"quote_at_ns": 1201},
    ],
)
def test_invalid_quote_contract(changes):
    with pytest.raises(ValueError):
        request(**changes)


def test_decimal_precision_does_not_change_fill(gateway):
    with localcontext() as context:
        context.prec = 2
        receipt = gateway.execute(request())
    assert receipt.fee_usdt == D("0.06")
    assert gateway.journal.account_state().cash_usdt == D("39.94")


def test_backward_risk_time_rejected_without_mutation(gateway):
    gateway.set_kill_switch(True, observed_at_ns=1300)
    with pytest.raises(JournalError, match="regressed"):
        gateway.execute(request())
    assert gateway.get_receipt("order-1") is None
    with pytest.raises(ValueError):
        gateway.set_kill_switch(1, observed_at_ns=1400)


@pytest.mark.parametrize("boundary", ["before_checkpoint", "after_commit"])
def test_abrupt_process_exit_is_safe_on_both_sides_of_commit(gateway, tmp_path, boundary):
    # Simulate both an interrupted transaction and a lost acknowledgement after commit.
    script = """
import os, sys
from decimal import Decimal as D
from ai_trader.trading.trade_journal import TradeJournal
from ai_trader.trading.durable_paper_gateway import DurablePaperGateway, PaperQuoteRequest
from ai_trader.trading.durable_paper_gateway import _decode_config
from ai_trader.trading.trade_journal import _read
with TradeJournal(sys.argv[1], run_id='run-1', mode='paper') as j:
    row = j._db.execute('SELECT payload, sha256 FROM paper_gateway_config').fetchone()
    gw = DurablePaperGateway(j, _read(*row, _decode_config))
    if sys.argv[2] == 'before_checkpoint':
        gw._save_checkpoint = lambda *args: os._exit(23)
    gw.execute(PaperQuoteRequest('order-1', D('59990'), D('60000'), 1200, 1200))
    os._exit(23)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "j.sqlite"), boundary],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 23, result.stderr
    with open_journal(tmp_path / "j.sqlite") as journal:
        reopened = DurablePaperGateway(journal, config())
        if boundary == "before_checkpoint":
            assert reopened.get_receipt("order-1") is None
            assert journal.account_state().cash_usdt == D("100")
        else:
            assert reopened.get_receipt("order-1").status == ExecutionStatus.FILLED
            assert journal.account_state().cash_usdt == D("39.94")
        receipt = reopened.execute(request())
    with open_journal(tmp_path / "j.sqlite") as journal:
        assert DurablePaperGateway(journal, config()).execute(request()) == receipt


def test_configuration_reassignment_and_corruption_fail_closed(gateway):
    gateway.config = config(max_drawdown_usdt=D("200"))
    with pytest.raises(JournalConflict, match="configuration changed"):
        gateway.execute(request())
    gateway.config = config()
    gateway.journal._db.execute("DROP TRIGGER paper_gateway_config_no_update")
    gateway.journal._db.execute("UPDATE paper_gateway_config SET payload='{}'")
    with pytest.raises(JournalError, match="checksum"):
        gateway.execute(request())


def make_v3(path):
    with TradeJournal.create(path, run_id="run-1", mode="paper") as journal:
        journal._db.execute("DROP TABLE paper_replay_sources")
        journal.initialize_account(PaperAccountSeed(D("100"), 1000))
        journal._db.execute("DROP TABLE paper_runner_ticks")
        journal._db.execute("DROP TABLE paper_runner_config")
        for table in ("paper_gateway_requests", "paper_gateway_config", "paper_risk_checkpoints"):
            journal._db.execute(f"DROP TABLE {table}")
        journal._db.execute("PRAGMA user_version=3")


def test_v3_explicit_upgrade_preserves_account(tmp_path):
    path = tmp_path / "v3.sqlite"
    make_v3(path)
    with open_journal(path) as journal:
        before = journal.account_state()
        with pytest.raises(JournalError, match="upgrade"):
            DurablePaperGateway.initialize(journal, config())
        assert journal.upgrade_schema()
        assert journal.account_state() == before
        gw = DurablePaperGateway.initialize(journal, config())
        prepare(journal, config())
        assert gw.execute(request()).status == ExecutionStatus.FILLED


def test_v3_migration_failure_rolls_back(tmp_path):
    path = tmp_path / "v3.sqlite"
    make_v3(path)
    with open_journal(path) as journal:
        journal._db.execute("CREATE TABLE paper_risk_checkpoints (sentinel TEXT)")
        with pytest.raises(sqlite3.OperationalError):
            journal.upgrade_schema()
        assert journal._db.execute("PRAGMA user_version").fetchone()[0] == 3
        assert (
            journal._db.execute(
                "SELECT name FROM sqlite_master WHERE name='paper_gateway_config'"
            ).fetchone()
            is None
        )
        assert journal.account_state().cash_usdt == D("100")


def test_cannot_enable_gateway_on_an_existing_order_history(tmp_path):
    with TradeJournal.create(tmp_path / "j", run_id="run-1", mode="paper") as journal:
        journal.initialize_account(PaperAccountSeed(D("100"), 1000))
        prepare(journal, config())
        with pytest.raises(JournalError, match="before preparing"):
            DurablePaperGateway.initialize(journal, config())
        assert journal._db.execute("SELECT * FROM paper_gateway_config").fetchall() == []


def test_gateway_requires_initialized_paper_account(tmp_path):
    with TradeJournal.create(tmp_path / "j", run_id="r", mode="research_only") as journal:
        with pytest.raises(JournalError, match="paper-only"):
            DurablePaperGateway.initialize(journal, config())
    with TradeJournal.create(tmp_path / "p", run_id="r", mode="paper") as journal:
        with pytest.raises(JournalError, match="initialized"):
            DurablePaperGateway.initialize(journal, config())


def test_stale_quote_does_not_raise_equity_peak(gateway):
    gateway.execute(request())
    prepare(gateway.journal, config(), order_id="other", time=1300)
    peak = gateway.risk_checkpoint().peak_equity_usdt
    receipt = gateway.execute(
        request(
            "other",
            quote_at_ns=1200,
            observed_at_ns=1400,
            bid_usdt=D("999999"),
            ask_usdt=D("1000000"),
        )
    )
    assert receipt.reason == "stale_quote"
    assert gateway.risk_checkpoint().peak_equity_usdt == peak


def test_adverse_slippage_and_fees_are_booked_once(tmp_path):
    cfg = replace(config(), costs=ExecutionCosts(D("10"), D("5")))
    with TradeJournal.create(tmp_path / "j", run_id="run-1", mode="paper") as journal:
        journal.initialize_account(PaperAccountSeed(D("100"), 1000))
        gw = DurablePaperGateway.initialize(journal, cfg)
        prepare(journal, cfg)
        receipt = gw.execute(request())
        assert receipt.average_fill_price_usdt == D("60030")
        assert receipt.fee_usdt == D("0.06003")
        assert journal.account_state().cash_usdt == D("39.90997")


def test_risk_checkpoint_tables_are_append_only(gateway):
    gateway.execute(request())
    for table in ("paper_gateway_config", "paper_gateway_requests", "paper_risk_checkpoints"):
        with pytest.raises(sqlite3.IntegrityError):
            gateway.journal._db.execute(f"DELETE FROM {table}")
        with pytest.raises(sqlite3.IntegrityError):
            gateway.journal._db.execute(f"UPDATE {table} SET payload='bad'")
