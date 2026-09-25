"""Synthetic ledger tests: no exchange, credentials, network or account mutations."""

import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal, localcontext

import pytest
from test_trade_case import case

from ai_trader.trading.paper_lifecycle import PaperEntryOrder, PaperOrderEvent
from ai_trader.trading.trade_journal import JournalConflict, JournalError, TradeJournal

D = Decimal


def paper_case():
    return replace(case(), mode="paper")


def order():
    value = paper_case()
    return PaperEntryOrder("order-1", value.case_id, value.sha256, D("0.001"), 1100)


def event(kind="SUBMITTED", **changes):
    return PaperOrderEvent(
        **(
            dict(
                event_id=kind,
                order_id="order-1",
                kind=kind,
                observed_at_ns=1200,
                reason="Synthetic evidence",
            )
            | changes
        )
    )


def fill(**changes):
    return event(
        "FILL",
        **(
            dict(
                fill_id="fill-1",
                executed_at_ns=1200,
                quantity_btc=D("0.0004"),
                price_usdt=D("60000"),
                fee_usdt=D("0.024"),
            )
            | changes
        ),
    )


def open_journal(path, **changes):
    return TradeJournal(path, **(dict(run_id="run-1", mode="paper") | changes))


@pytest.fixture
def journal(tmp_path):
    with TradeJournal.create(tmp_path / "journal.sqlite", run_id="run-1", mode="paper") as value:
        value.append_case(paper_case())
        value.append_order(order())
        yield value


def test_reopen_partial_fill_exact_retry_and_full_fill(journal, tmp_path):
    journal.append_order_event(event())
    assert journal.append_order_event(fill())
    with open_journal(tmp_path / "journal.sqlite") as reopened:
        assert not reopened.append_order(order())
        assert not reopened.append_order_event(fill())
        assert reopened.order_ids() == ("order-1",)
        state = reopened.order_state("order-1")
        assert state.status == "PARTIALLY_FILLED"
        assert state.filled_quantity_btc == D("0.0004")
        assert state.fill_notional_usdt == D("24")
        assert state.fee_usdt == D("0.024")
        reopened.append_order_event(
            fill(
                event_id="fill-event-2",
                fill_id="fill-2",
                quantity_btc=D("0.0006"),
                price_usdt=D("60100"),
                fee_usdt=D("0.03606"),
            )
        )
        state = reopened.order_state("order-1")
        assert state.status == "FILLED"
        assert state.fill_notional_usdt == D("60.06")
        assert state.fee_usdt == D("0.06006")


@pytest.mark.parametrize(
    "change",
    [
        {"case_sha256": "a" * 64},
        {"case_id": "missing"},
        {"requested_at_ns": 999},
        {"requested_at_ns": 1500},
        {"quantity_btc": D("0.002")},
    ],
)
def test_order_case_binding(journal, change):
    with pytest.raises(JournalError):
        journal.append_order(replace(order(), order_id="new", **change))
    assert journal.order_ids() == ("order-1",)


def test_one_order_per_case_and_conflicting_retry(journal):
    with pytest.raises(JournalConflict):
        journal.append_order(replace(order(), order_id="new"))
    with pytest.raises(JournalConflict):
        journal.append_order(replace(order(), quantity_btc=D("0.0005")))


def test_rejected_case_cannot_fund_entry(tmp_path):
    rejected = replace(paper_case(), risk_verdict="REJECTED", approved_quantity_btc=None)
    with TradeJournal.create(tmp_path / "j", run_id="run-1", mode="paper") as journal:
        journal.append_case(rejected)
        with pytest.raises(JournalError):
            journal.append_order(replace(order(), case_sha256=rejected.sha256))


def test_research_mode_cannot_store_orders(tmp_path):
    with TradeJournal.create(tmp_path / "j", run_id="run-1", mode="research_only") as journal:
        with pytest.raises(JournalError, match="paper-only"):
            journal.append_order(order())


@pytest.mark.parametrize(
    "change",
    [
        {"quantity_btc": D("NaN")},
        {"price_usdt": D("Infinity")},
        {"fee_usdt": D("-1")},
        {"quantity_btc": D("0")},
        {"quantity_btc": 0.1},
        {"fee_usdt": None},
        {"fill_id": ""},
        {"observed_at_ns": True},
        {"executed_at_ns": 1300},
        {"price_usdt": D("1e-100")},
        {"observed_at_ns": 2**63},
    ],
)
def test_invalid_fill_contract(change):
    with pytest.raises(ValueError):
        fill(**change)


def test_nonfill_cannot_smuggle_cumulative_fill():
    with pytest.raises(ValueError):
        event(quantity_btc=D("0.001"))


def test_fill_id_and_event_conflicts_do_not_double_count(journal):
    journal.append_order_event(event())
    journal.append_order_event(fill())
    with pytest.raises(JournalConflict):
        journal.append_order_event(fill(event_id="another-event"))
    with pytest.raises(JournalConflict):
        journal.append_order_event(fill(price_usdt=D("1")))
    assert journal.order_state("order-1").fee_usdt == D("0.024")


@pytest.mark.parametrize(
    "bad",
    [
        event("CANCELED"),
        fill(),
        event(observed_at_ns=1099),
        event(order_id="missing"),
    ],
)
def test_invalid_initial_transition_leaves_no_event(journal, bad):
    with pytest.raises(JournalError):
        journal.append_order_event(bad)
    assert journal.order_events("order-1") == ()


def test_unknown_requires_reconciliation(journal, tmp_path):
    journal.append_order_event(event("UNKNOWN"))
    journal.append_order_event(fill())
    with open_journal(tmp_path / "journal.sqlite") as reopened:
        assert reopened.order_state("order-1").status == "UNKNOWN"
        # Explicit observation of the original order, not permission to submit again.
        reopened.append_order_event(event(reason="Original order reconciled as open"))
        assert reopened.order_state("order-1").status == "PARTIALLY_FILLED"


def test_cancel_then_late_fills_preserve_remainder_and_reach_full(journal):
    journal.append_order_event(event())
    journal.append_order_event(event("CANCELED", observed_at_ns=1300))
    journal.append_order_event(fill(observed_at_ns=1400))
    assert journal.order_state("order-1").status == "CANCELED"
    journal.append_order_event(
        fill(
            event_id="last",
            fill_id="last",
            observed_at_ns=1500,
            quantity_btc=D("0.0006"),
        )
    )
    assert journal.order_state("order-1").status == "FILLED"


@pytest.mark.parametrize(
    "bad",
    [
        event("REJECTED"),
        event(event_id="submit-again"),
        fill(event_id="overflow", fill_id="overflow", quantity_btc=D("0.001")),
        fill(event_id="old", fill_id="old", observed_at_ns=1199, executed_at_ns=1199),
        fill(event_id="pre-request", fill_id="pre-request", executed_at_ns=1099),
    ],
)
def test_invalid_partial_transitions_are_atomic(journal, bad):
    journal.append_order_event(event())
    journal.append_order_event(fill())
    with pytest.raises(JournalError):
        journal.append_order_event(bad)
    assert len(journal.order_events("order-1")) == 2


@pytest.mark.parametrize("terminal", ["REJECTED", "FILLED"])
def test_terminal_orders_do_not_reopen(journal, terminal):
    if terminal == "FILLED":
        journal.append_order_event(event())
        journal.append_order_event(fill(quantity_btc=D("0.001")))
    else:
        journal.append_order_event(event("REJECTED"))
    with pytest.raises(JournalError):
        journal.append_order_event(event("UNKNOWN"))


def test_decimal_context_does_not_change_accounting(journal):
    journal.append_order_event(event())
    with localcontext() as context:
        context.prec = 2
        journal.append_order_event(fill(price_usdt=D("60123.456789")))
        state = journal.order_state("order-1")
    assert state.fill_notional_usdt == D("24.0493827156")


def test_concurrent_duplicate_fill_one_commit(journal, tmp_path):
    journal.append_order_event(event())

    def append(_):
        with open_journal(tmp_path / "journal.sqlite") as writer:
            return writer.append_order_event(fill())

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(append, range(2))) == [False, True]
    assert journal.order_state("order-1").filled_quantity_btc == D("0.0004")


def test_injected_insert_failure_rollback_and_retry(journal):
    journal._db.execute("""CREATE TRIGGER fail_event BEFORE INSERT ON paper_events
        BEGIN SELECT RAISE(ABORT, 'injected'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        journal.append_order_event(event())
    assert journal.order_state("order-1").status == "PREPARED"
    journal._db.execute("DROP TRIGGER fail_event")
    assert journal.append_order_event(event())


def test_read_only_and_append_only(journal, tmp_path):
    journal.append_order_event(event())
    with open_journal(tmp_path / "journal.sqlite", read_only=True) as reader:
        assert reader.order_state("order-1").status == "SUBMITTED"
        with pytest.raises(JournalError, match="read-only"):
            reader.append_order_event(fill())
    for table in ("paper_orders", "paper_events"):
        with pytest.raises(sqlite3.IntegrityError):
            journal._db.execute(f"DELETE FROM {table}")
        with pytest.raises(sqlite3.IntegrityError):
            journal._db.execute(f"UPDATE {table} SET payload='corrupt'")


def test_corrupted_events_fail_closed(journal):
    journal.append_order_event(event())
    journal._db.execute("DROP TRIGGER paper_events_no_update")
    journal._db.execute("UPDATE paper_events SET payload='{}'")
    with pytest.raises(JournalError):
        journal.order_state("order-1")
    with pytest.raises(JournalError):
        journal.append_order_event(event())


def make_v1(path):
    # Reproduce the previous schema, retaining its real case table and content.
    with TradeJournal.create(path, run_id="run-1", mode="paper") as old:
        old.append_case(paper_case())
        old._db.execute("DROP TABLE paper_replay_sources")
        old._db.execute("DROP TABLE paper_runner_ticks")
        old._db.execute("DROP TABLE paper_runner_config")
        for table in ("paper_gateway_requests", "paper_gateway_config", "paper_risk_checkpoints"):
            old._db.execute(f"DROP TABLE {table}")
        old._db.execute("DROP TABLE paper_events")
        old._db.execute("DROP TABLE paper_orders")
        old._db.execute("DROP TABLE paper_account")
        old._db.execute("PRAGMA user_version=1")


def test_explicit_upgrade_preserves_v1_case(tmp_path):
    path = tmp_path / "old.sqlite"
    make_v1(path)
    with open_journal(path, read_only=True) as old:
        assert old.get_case("case-1") == paper_case()
        with pytest.raises(JournalError, match="upgrade"):
            old.order_ids()
        with pytest.raises(JournalError, match="read-only"):
            old.upgrade_schema()
    with open_journal(path) as old:
        assert old.upgrade_schema()
        assert not old.upgrade_schema()
        assert old.get_case("case-1") == paper_case()
        assert old.append_order(order())


def test_failed_migration_rolls_back_new_tables_and_version(tmp_path):
    path = tmp_path / "old.sqlite"
    make_v1(path)
    with open_journal(path) as old:
        old._db.execute("CREATE TABLE paper_events (sentinel TEXT)")
        with pytest.raises(sqlite3.OperationalError):
            old.upgrade_schema()
        assert old._db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert (
            old._db.execute("SELECT name FROM sqlite_master WHERE name='paper_orders'").fetchone()
            is None
        )
        assert old.get_case("case-1") == paper_case()


def test_fill_ids_are_unique_across_orders(journal):
    second_case = replace(paper_case(), case_id="case-2")
    journal.append_case(second_case)
    journal.append_order(
        replace(
            order(),
            order_id="order-2",
            case_id=second_case.case_id,
            case_sha256=second_case.sha256,
        )
    )
    journal.append_order_event(event())
    journal.append_order_event(event(event_id="submit-2", order_id="order-2"))
    journal.append_order_event(fill())
    with pytest.raises(JournalConflict):
        journal.append_order_event(fill(event_id="fill-event-2", order_id="order-2"))
    assert journal.order_state("order-2").filled_quantity_btc == 0


def test_concurrent_distinct_fills_cannot_overfill(journal, tmp_path):
    journal.append_order_event(event())

    def append(index):
        with open_journal(tmp_path / "journal.sqlite") as writer:
            try:
                writer.append_order_event(
                    fill(
                        event_id=f"event-{index}",
                        fill_id=f"fill-{index}",
                        quantity_btc=D("0.0006"),
                    )
                )
                return "committed"
            except JournalError:
                return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(append, range(2))) == ["committed", "rejected"]
    assert journal.order_state("order-1").filled_quantity_btc == D("0.0006")


def test_process_exit_preserves_committed_fill_not_uncommitted_event(journal, tmp_path):
    journal.append_order_event(event())
    journal.append_order_event(fill())
    script = """
import os, sqlite3, sys
db = sqlite3.connect(sys.argv[1], isolation_level=None)
db.execute('BEGIN IMMEDIATE')
db.execute("INSERT INTO paper_events "
           "(event_id, order_id, payload, sha256, recorded_at_ns) "
           "VALUES ('uncommitted', 'order-1', '{}', 'bad', 1)")
os._exit(23)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "journal.sqlite")],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 23, result.stderr
    with open_journal(tmp_path / "journal.sqlite") as reopened:
        assert len(reopened.order_events("order-1")) == 2
        assert reopened.order_state("order-1").filled_quantity_btc == D("0.0004")
        assert not reopened.append_order_event(fill())


def test_order_and_event_binding_tampering_is_rejected(journal):
    journal.append_order_event(event())
    journal._db.execute("DROP TRIGGER paper_events_no_update")
    journal._db.execute("UPDATE paper_events SET fill_id='smuggled-fill'")
    with pytest.raises(JournalError, match="binding"):
        journal.order_state("order-1")


def test_lifecycle_uses_no_network(journal, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network forbidden")

    monkeypatch.setattr("socket.socket", forbidden)
    journal.append_order_event(event())
    journal.append_order_event(fill())
    assert journal.order_state("order-1").status == "PARTIALLY_FILLED"
