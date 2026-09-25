"""Synthetic funded spot ledger: exits, accounting, persistence and failure boundaries."""

import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal, localcontext

import pytest
from test_paper_lifecycle import event, fill, open_journal, order, paper_case

from ai_trader.trading.paper_account import PaperAccountSeed
from ai_trader.trading.paper_lifecycle import PaperExitOrder
from ai_trader.trading.trade_journal import (
    JournalConflict,
    JournalError,
    TradeJournal,
    _create_lifecycle_tables,
)

D = Decimal


@pytest.fixture
def account(tmp_path):
    with TradeJournal.create(tmp_path / "journal.sqlite", run_id="run-1", mode="paper") as journal:
        journal.initialize_account(PaperAccountSeed(D("100"), 1000))
        journal.append_case(paper_case())
        journal.append_order(order())
        yield journal


def buy(journal):
    journal.append_order_event(event())
    journal.append_order_event(fill(quantity_btc=D("0.001"), fee_usdt=D("0.06")))


def exit_order(**changes):
    return replace(PaperExitOrder("exit-1", "order-1", D("0.001"), 2000, "stop_loss"), **changes)


def sell(journal, **changes):
    journal.append_order_event(
        event(order_id="exit-1", event_id="exit-submit", observed_at_ns=2100)
    )
    journal.append_order_event(
        fill(
            **(
                dict(
                    event_id="exit-fill",
                    order_id="exit-1",
                    fill_id="exit-fill",
                    observed_at_ns=2200,
                    executed_at_ns=2100,
                    quantity_btc=D("0.001"),
                    price_usdt=D("61000"),
                    fee_usdt=D("0.061"),
                )
                | changes
            )
        )
    )


def test_round_trip_cash_cost_pnl_and_restart(account, tmp_path):
    buy(account)
    state = account.account_state()
    assert state.cash_usdt == D("39.94")
    assert state.position_btc == D("0.001")
    assert state.cost_basis_usdt == D("60.06")
    assert state.realized_pnl_usdt == 0
    account.append_exit_order(exit_order())  # After entry case expiry; no new analyst verdict.
    assert account.account_state().positions[0].reserved_exit_btc == D("0.001")
    sell(account)
    state = account.account_state()
    assert state.cash_usdt == D("100.879")
    assert state.realized_pnl_usdt == D("0.879")
    assert state.fees_usdt == D("0.121")
    assert state.position_btc == state.cost_basis_usdt == 0
    assert state.unresolved_order_ids == ()
    with open_journal(tmp_path / "journal.sqlite", read_only=True) as reader:
        assert reader.account_state() == state
        assert reader.get_order("exit-1") == exit_order()
    assert not account.append_exit_order(exit_order())


def test_partial_sell_consumes_proportional_cost_once(account):
    buy(account)
    account.append_exit_order(exit_order())
    sell(account, quantity_btc=D("0.0004"), fee_usdt=D("0.0244"))
    state = account.account_state()
    assert state.position_btc == D("0.0006")
    assert state.cost_basis_usdt == D("36.036")
    assert state.realized_pnl_usdt == D("0.3516")
    assert state.cash_usdt == D("64.3156")
    assert state.positions[0].reserved_exit_btc == D("0.0006")
    account.append_order_event(
        fill(
            event_id="last",
            order_id="exit-1",
            fill_id="last",
            observed_at_ns=2300,
            executed_at_ns=2300,
            quantity_btc=D("0.0006"),
            price_usdt=D("59000"),
            fee_usdt=D("0.0354"),
        )
    )
    state = account.account_state()
    assert state.cost_basis_usdt == 0
    assert state.cash_usdt - state.initial_cash_usdt == state.realized_pnl_usdt


def test_duplicate_exit_fill_has_no_account_effect(account):
    buy(account)
    account.append_exit_order(exit_order())
    sell(account)
    before = account.account_state()
    assert not account.append_order_event(account.order_events("exit-1")[-1])
    assert account.account_state() == before


@pytest.mark.parametrize(
    "change",
    [
        {"entry_order_id": "missing"},
        {"quantity_btc": D("0.0011")},
        {"requested_at_ns": 1199},
    ],
)
def test_invalid_exit_does_not_change_inventory(account, change):
    buy(account)
    before = account.account_state()
    with pytest.raises(JournalError):
        account.append_exit_order(exit_order(**change))
    assert account.account_state() == before
    assert account.get_order("exit-1") is None


def test_unfilled_entry_cannot_fund_exit(account):
    with pytest.raises(JournalError, match="reservations"):
        account.append_exit_order(exit_order())


def test_exit_cannot_reference_another_exit(account):
    buy(account)
    account.append_exit_order(exit_order(quantity_btc=D("0.0005")))
    with pytest.raises(JournalError, match="entry"):
        account.append_exit_order(exit_order(order_id="exit-2", entry_order_id="exit-1"))


def test_concurrent_exits_cannot_reserve_same_inventory(account, tmp_path):
    buy(account)

    def submit(index):
        with open_journal(tmp_path / "journal.sqlite") as writer:
            try:
                writer.append_exit_order(exit_order(order_id=f"exit-{index}"))
                return "saved"
            except JournalError:
                return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit, (1, 2))) == ["rejected", "saved"]
    assert account.account_state().positions[0].reserved_exit_btc == D("0.001")


def test_cancellation_keeps_reservation_until_explicit_confirmation(account):
    buy(account)
    account.append_exit_order(exit_order())
    account.append_order_event(event(order_id="exit-1", event_id="s", observed_at_ns=2100))
    account.append_order_event(event("CANCELED", order_id="exit-1", observed_at_ns=2200))
    with pytest.raises(JournalError, match="reservations"):
        account.append_exit_order(exit_order(order_id="exit-2", requested_at_ns=2300))
    account.append_order_event(
        fill(
            order_id="exit-1",
            event_id="late",
            fill_id="late",
            observed_at_ns=2300,
            executed_at_ns=2100,
            quantity_btc=D("0.0004"),
        )
    )
    assert account.account_state().positions[0].reserved_exit_btc == D("0.0006")
    account.append_order_event(
        event(
            "CANCEL_CONFIRMED",
            order_id="exit-1",
            observed_at_ns=2400,
            reason="Paper simulator reconciled all fills; remainder canceled",
        )
    )
    assert account.account_state().positions[0].reserved_exit_btc == 0
    account.append_exit_order(
        exit_order(
            order_id="exit-2",
            quantity_btc=D("0.0006"),
            requested_at_ns=2500,
        )
    )
    with pytest.raises(JournalError, match="outstanding"):
        account.append_order_event(
            fill(
                order_id="exit-1",
                event_id="impossible-late",
                fill_id="impossible-late",
                observed_at_ns=2600,
                executed_at_ns=2100,
            )
        )


def test_unknown_entry_does_not_block_exit_of_known_fills(account):
    account.append_order_event(event("UNKNOWN"))
    account.append_order_event(fill())
    account.append_exit_order(exit_order(quantity_btc=D("0.0004")))
    sell(account, quantity_btc=D("0.0004"))
    assert account.account_state().position_btc == 0
    assert account.account_state().unresolved_order_ids == ("order-1",)


def test_overdraw_fill_rolls_back_event_and_account(account):
    account.append_order_event(event())
    before = account.account_state()
    with pytest.raises(JournalError, match="overdraw"):
        account.append_order_event(fill(quantity_btc=D("0.001"), price_usdt=D("100000")))
    assert account.account_state() == before
    assert len(account.order_events("order-1")) == 1
    assert account.append_order_event(fill())


def test_global_observation_time_cannot_regress(account):
    buy(account)
    account.append_exit_order(exit_order())
    account.append_order_event(event(order_id="exit-1", event_id="s", observed_at_ns=2100))
    # Another approved entry has valid local timestamps but stale account observation time.
    second_case = replace(
        paper_case(),
        case_id="case-2",
        decision_at_ns=2200,
        plan=replace(paper_case().plan, expires_at_ns=4000),
    )
    account.append_case(second_case)
    second = replace(
        order(),
        order_id="order-2",
        case_id="case-2",
        case_sha256=second_case.sha256,
        requested_at_ns=2200,
    )
    account.append_order(second)
    account.append_order_event(event(order_id="order-2", event_id="s2", observed_at_ns=2300))
    with pytest.raises(JournalError, match="regressed"):
        account.append_order_event(event("UNKNOWN", order_id="exit-1", observed_at_ns=2200))


def test_seed_idempotency_conflict_and_read_only(account, tmp_path):
    assert not account.initialize_account(PaperAccountSeed(D("100"), 1000))
    with pytest.raises(JournalConflict):
        account.initialize_account(PaperAccountSeed(D("200"), 1000))
    with open_journal(tmp_path / "journal.sqlite", read_only=True) as reader:
        with pytest.raises(JournalError, match="read-only"):
            reader.initialize_account(PaperAccountSeed(D("100"), 1000))
    with pytest.raises(sqlite3.IntegrityError):
        account._db.execute("DELETE FROM paper_account")


@pytest.mark.parametrize("cash, timestamp", [(D("0"), 1), (D("NaN"), 1), (1.0, 1), (D(1), True)])
def test_invalid_seed(cash, timestamp):
    with pytest.raises(ValueError):
        PaperAccountSeed(cash, timestamp)


def test_cannot_invent_funding_for_old_history(tmp_path):
    with TradeJournal.create(tmp_path / "j", run_id="run-1", mode="paper") as journal:
        journal.append_case(paper_case())
        journal.append_order(order())
        with pytest.raises(JournalError, match="before any orders"):
            journal.initialize_account(PaperAccountSeed(D("100"), 1000))
        with pytest.raises(JournalError, match="initialized"):
            journal.account_state()
        with pytest.raises(JournalError, match="initialized"):
            journal.append_exit_order(exit_order())


def test_fractional_cost_basis_full_close_leaves_no_dust(account):
    account.append_order_event(event())
    account.append_order_event(fill(quantity_btc=D("0.0003"), fee_usdt=D("0.01")))
    account.append_exit_order(exit_order(quantity_btc=D("0.0003")))
    with localcontext() as context:
        context.prec = 2
        sell(account, quantity_btc=D("0.0001"), fee_usdt=D("0.001"))
        account.append_order_event(
            fill(
                order_id="exit-1",
                event_id="final",
                fill_id="final",
                quantity_btc=D("0.0002"),
                fee_usdt=D("0.002"),
                observed_at_ns=2300,
                executed_at_ns=2300,
            )
        )
        state = account.account_state()
    assert state.position_btc == state.cost_basis_usdt == 0
    assert state.cash_usdt == D("100.087")
    assert abs(state.realized_pnl_usdt - D("0.087")) < D("1e-90")


def test_process_exit_preserves_funded_account(account, tmp_path):
    buy(account)
    account.append_exit_order(exit_order())
    sell(account)
    expected = account.account_state()
    script = """
import os, sqlite3, sys
db = sqlite3.connect(sys.argv[1], isolation_level=None)
db.execute('BEGIN IMMEDIATE')
db.execute("INSERT INTO paper_events "
           "(event_id, order_id, payload, sha256, recorded_at_ns) "
           "VALUES ('uncommitted', 'exit-1', '{}', 'bad', 1)")
os._exit(23)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "journal.sqlite")],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 23, result.stderr
    with open_journal(tmp_path / "journal.sqlite") as reopened:
        assert reopened.account_state() == expected


def test_seed_corruption_fails_closed(account):
    account._db.execute("DROP TRIGGER paper_account_no_update")
    account._db.execute("UPDATE paper_account SET payload='{}'")
    with pytest.raises(JournalError, match="checksum"):
        account.account_state()


def test_research_mode_cannot_initialize_account(tmp_path):
    with TradeJournal.create(tmp_path / "j", run_id="r", mode="research_only") as journal:
        with pytest.raises(JournalError, match="paper-only"):
            journal.initialize_account(PaperAccountSeed(D("100"), 1000))


def make_v2(path):
    with TradeJournal.create(path, run_id="run-1", mode="paper") as old:
        old._db.execute("DROP TABLE paper_replay_sources")
        old._db.execute("DROP TABLE paper_runner_ticks")
        old._db.execute("DROP TABLE paper_runner_config")
        for table in ("paper_gateway_requests", "paper_gateway_config", "paper_risk_checkpoints"):
            old._db.execute(f"DROP TABLE {table}")
        old._db.execute("DROP TABLE paper_events")
        old._db.execute("DROP TABLE paper_orders")
        old._db.execute("DROP TABLE paper_account")
        _create_lifecycle_tables(old._db)
        old._db.execute("PRAGMA user_version=2")
        old.append_case(paper_case())
        old.append_order(order())
        buy(old)


def test_v2_upgrade_preserves_exact_records_and_foreign_keys(tmp_path):
    path = tmp_path / "old.sqlite"
    make_v2(path)
    with open_journal(path) as old:
        state = old.order_state("order-1")
        rows = old._db.execute("SELECT * FROM paper_events").fetchall()
        with pytest.raises(JournalError, match="upgrade"):
            old.account_state()
        assert old.upgrade_schema()
        assert old.order_state("order-1") == state
        assert old._db.execute("SELECT * FROM paper_events").fetchall() == rows
        assert old._db.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(JournalError, match="before any orders"):
            old.initialize_account(PaperAccountSeed(D("100"), 1000))


def test_v2_failed_upgrade_rolls_back_all_tables(tmp_path):
    path = tmp_path / "old.sqlite"
    make_v2(path)
    with open_journal(path) as old:
        before = old.order_state("order-1")
        old._db.execute("CREATE TABLE paper_account (sentinel TEXT)")
        with pytest.raises(sqlite3.OperationalError):
            old.upgrade_schema()
        assert old._db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert old.order_state("order-1") == before
        assert old._db.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.IntegrityError):
            old._db.execute("DELETE FROM paper_orders")


def test_unknown_exit_keeps_inventory_reserved_after_restart(account, tmp_path):
    buy(account)
    account.append_exit_order(exit_order())
    account.append_order_event(event("UNKNOWN", order_id="exit-1", observed_at_ns=2100))
    with open_journal(tmp_path / "journal.sqlite") as reopened:
        assert reopened.account_state().positions[0].reserved_exit_btc == D("0.001")
        with pytest.raises(JournalError, match="reservations"):
            reopened.append_exit_order(exit_order(order_id="replacement", requested_at_ns=2200))


def test_rejected_exit_releases_reservation(account):
    buy(account)
    account.append_exit_order(exit_order())
    account.append_order_event(event("REJECTED", order_id="exit-1", observed_at_ns=2100))
    assert account.account_state().positions[0].reserved_exit_btc == 0
    account.append_exit_order(exit_order(order_id="replacement", requested_at_ns=2200))


def test_conflicting_exit_and_entry_exit_id_collision(account):
    buy(account)
    account.append_exit_order(exit_order())
    with pytest.raises(JournalConflict):
        account.append_exit_order(exit_order(reason="different reason"))
    with pytest.raises(JournalConflict):
        account.append_exit_order(exit_order(order_id="order-1", entry_order_id="other"))
    with pytest.raises(JournalConflict):
        account.append_order(replace(order(), order_id="exit-1"))


def test_two_entry_lots_cannot_lend_each_other_inventory(account):
    account.append_order_event(event())
    account.append_order_event(fill())  # .0004 in order-1
    second_case = replace(paper_case(), case_id="case-2")
    account.append_case(second_case)
    account.append_order(
        replace(
            order(),
            order_id="order-2",
            case_id="case-2",
            case_sha256=second_case.sha256,
            requested_at_ns=1250,
        )
    )
    account.append_order_event(event(order_id="order-2", event_id="s2", observed_at_ns=1300))
    account.append_order_event(
        fill(
            order_id="order-2",
            event_id="f2",
            fill_id="f2",
            observed_at_ns=1400,
            executed_at_ns=1300,
        )
    )
    assert account.account_state().position_btc == D("0.0008")
    with pytest.raises(JournalError, match="reservations"):
        account.append_exit_order(exit_order(quantity_btc=D("0.0005")))
    account.append_exit_order(exit_order(quantity_btc=D("0.0004")))
    sell(account, quantity_btc=D("0.0004"))
    positions = account.account_state().positions
    assert positions[0].quantity_btc == 0
    assert positions[1].quantity_btc == D("0.0004")


def test_account_read_has_consistent_snapshot_during_concurrent_fill(
    account, tmp_path, monkeypatch
):
    account._db.execute("PRAGMA journal_mode=WAL")
    account.append_order_event(event())
    expected = account.account_state()
    original = account.get_order

    def writer():
        with open_journal(tmp_path / "journal.sqlite") as other:
            other.append_order_event(fill())

    called = False

    def interleaved_read(order_id):
        nonlocal called
        if not called:
            called = True
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(writer).result(timeout=10)
        return original(order_id)

    monkeypatch.setattr(account, "get_order", interleaved_read)
    assert account.account_state() == expected
    assert account.account_state().position_btc == D("0.0004")


def test_entry_request_regression_rolls_back(account):
    buy(account)
    second = replace(paper_case(), case_id="case-2")
    account.append_case(second)
    with pytest.raises(JournalError, match="regressed"):
        account.append_order(
            replace(
                order(),
                order_id="order-2",
                case_id="case-2",
                case_sha256=second.sha256,
            )
        )
    assert account.get_order("order-2") is None


def test_no_network_or_gateway_required_for_recovery(account, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network forbidden")

    monkeypatch.setattr("socket.socket", forbidden)
    buy(account)
    account.append_exit_order(exit_order())
    sell(account)
    assert account.account_state().cash_usdt == D("100.879")


def test_exit_insert_failure_preserves_account_and_allows_retry(account):
    buy(account)
    expected = account.account_state()
    account._db.execute("""CREATE TRIGGER fail_exit BEFORE INSERT ON paper_orders
        BEGIN SELECT RAISE(ABORT, 'injected'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        account.append_exit_order(exit_order())
    assert account.account_state() == expected
    account._db.execute("DROP TRIGGER fail_exit")
    assert account.append_exit_order(exit_order())
