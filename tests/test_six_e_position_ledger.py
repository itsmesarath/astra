"""Synthetic receipts only: no feed, raw history, model, actual account or orders."""

import hashlib
import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace

import pytest

from ai_trader.research import six_e_position_ledger as l

DAY = "2025-04-07"
START = l.target.window(DAY)[0]
SECOND, TICK = l.target.SECOND, l.target.TICK


def config(**changes):
    return replace(
        l.ScenarioConfig(
            "scenario-1",
            "policy-1",
            "bracket_exit",
            "a" * 64,
            "synthetic-v1",
            max_position_contracts=2,
        ),
        **changes,
    )


def evidence(number):
    return hashlib.sha256(f"synthetic-receipt-{number}".encode()).hexdigest()


def entry(**changes):
    return replace(
        l.EntryFill(
            "entry-1",
            DAY,
            START,
            "position-1",
            "6EM5",
            "long",
            2,
            101 * TICK,
            START,
            "receipt-entry",
            evidence(1),
        ),
        **changes,
    )


def intent(**changes):
    return replace(
        l.ExitIntent("request-1", DAY, START + SECOND, "exit-1", "position-1", 2), **changes
    )


def unknown(**changes):
    return replace(
        l.UnresolvedExit(
            "unknown-1", DAY, START + 2 * SECOND, "exit-1", "No fresh exit observation"
        ),
        **changes,
    )


def fill(**changes):
    return replace(
        l.ExitFill(
            "fill-1",
            DAY,
            START + 3 * SECOND,
            "exit-1",
            "6EM5",
            2,
            105 * TICK,
            START + 2 * SECOND,
            "receipt-fill",
            evidence(2),
        ),
        **changes,
    )


def reference(**changes):
    return replace(
        l.QuoteReference(
            "reference-1",
            DAY,
            START + 3 * SECOND,
            "6EM5",
            START + 2 * SECOND,
            10,
            100 * TICK,
            101 * TICK,
        ),
        **changes,
    )


def append(ledger, event):
    return ledger.append(event, expected_tip_sha256=ledger.snapshot().tip_sha256)


@pytest.fixture
def ledger(tmp_path):
    with l.ScenarioLedger.create(tmp_path / "scenario.sqlite", config()) as ledger:
        yield ledger


def pending(ledger):
    append(ledger, entry())
    append(ledger, intent())
    append(ledger, unknown())


@pytest.mark.parametrize(
    "side,exit_price,expected_gross",
    [("long", 105, 8), ("short", 97, 8), ("long", 97, -8), ("short", 105, -8)],
)
def test_integer_contract_tick_accounting_and_costs(side, exit_price, expected_gross, ledger):
    append(ledger, entry(side=side))
    append(ledger, intent())
    append(ledger, fill(price_nano=exit_price * TICK))
    state = ledger.snapshot()
    assert state.position is state.reservation is None
    assert state.closed_contracts == 2 and state.closed_positions == 1
    assert state.closed_gross_contract_ticks == expected_gross
    assert state.closed_net_contract_ticks == expected_gross - 2
    assert state.complete_simulated_net_contract_ticks == expected_gross - 2
    assert not state.entry_recording_blocked
    assert l.protocol()["trading_enabled"] is False


def test_unknown_survives_session_change_restart_and_reference(ledger):
    pending(ledger)
    append(ledger, reference())
    before = ledger.snapshot()
    tomorrow = "2025-04-08"
    boundary_time = l.target.window(tomorrow)[0]
    append(ledger, l.SessionBoundary("next-day", tomorrow, boundary_time))
    state = ledger.snapshot()
    assert state.position == before.position
    assert state.reservation == before.reservation
    assert state.reservation.status == "UNKNOWN"
    assert state.last_reference == before.last_reference
    assert state.reference_age_ns == boundary_time - reference().quote_at_ns
    assert state.last_reference.source_session != state.current_session
    assert state.closed_net_contract_ticks == before.closed_net_contract_ticks == 0
    assert state.complete_simulated_net_contract_ticks is None
    assert state.entry_recording_blocked
    with l.ScenarioLedger(ledger.path, config()) as reader:
        assert reader.snapshot(expected_tip_sha256=state.tip_sha256) == state
    with pytest.raises(l.LedgerError, match="Open liability"):
        append(
            ledger,
            entry(
                event_id="entry-next",
                position_id="position-2",
                source_session=tomorrow,
                observed_at_ns=boundary_time,
                executed_at_ns=boundary_time,
                evidence_id="entry-other",
                paper_receipt_sha256=evidence(3),
            ),
        )


def test_reference_and_cancel_intent_never_close_or_release_reserved_inventory(ledger):
    pending(ledger)
    append(ledger, l.CancelIntent("cancel-intent", DAY, START + 3 * SECOND, "exit-1"))
    append(ledger, reference(event_id="quote-diagnostic", observed_at_ns=START + 4 * SECOND))
    state = ledger.snapshot()
    assert state.reservation.status == "CANCEL_REQUESTED"
    assert state.position.remaining_contracts == state.reservation.remaining_contracts == 2
    assert state.closed_contracts == 0 and state.complete_simulated_net_contract_ticks is None
    with pytest.raises(l.LedgerError, match="duplicate a pending"):
        append(
            ledger,
            intent(
                event_id="duplicate-exit", request_id="exit-2", observed_at_ns=START + 5 * SECOND
            ),
        )


def test_partial_unknown_fill_retains_remainder_and_charges_only_closed_quantity(ledger):
    pending(ledger)
    append(ledger, fill(quantity_contracts=1))
    state = ledger.snapshot()
    assert state.position.remaining_contracts == state.reservation.remaining_contracts == 1
    assert state.reservation.status == "UNKNOWN"
    assert state.closed_contracts == 1 and state.closed_net_contract_ticks == 3
    assert state.complete_simulated_net_contract_ticks is None
    append(
        ledger,
        fill(
            event_id="fill-last",
            observed_at_ns=START + 4 * SECOND,
            quantity_contracts=1,
            price_nano=99 * TICK,
            evidence_id="receipt-last",
            paper_receipt_sha256=evidence(3),
        ),
    )
    state = ledger.snapshot()
    assert state.position is state.reservation is None
    assert state.closed_net_contract_ticks == 0  # +3 and -3, exact once each.
    assert state.closed_positions == 1


def test_cancel_confirmation_releases_request_but_not_remaining_position(ledger):
    pending(ledger)
    append(ledger, fill(quantity_contracts=1))
    cancellation = l.CancelReceipt(
        "cancel-confirmed", DAY, START + 4 * SECOND, "exit-1", 1, "receipt-cancel", evidence(3)
    )
    append(ledger, cancellation)
    state = ledger.snapshot()
    assert state.position.remaining_contracts == 1 and state.reservation is None
    assert state.closed_net_contract_ticks == 3 and state.entry_recording_blocked
    append(
        ledger,
        intent(
            event_id="new-reducing-exit",
            request_id="exit-2",
            quantity_contracts=1,
            observed_at_ns=START + 5 * SECOND,
        ),
    )
    append(
        ledger,
        fill(
            event_id="new-exit-fill",
            request_id="exit-2",
            quantity_contracts=1,
            observed_at_ns=START + 7 * SECOND,
            executed_at_ns=START + 6 * SECOND,
            evidence_id="receipt-new",
            paper_receipt_sha256=evidence(4),
        ),
    )
    assert ledger.snapshot().closed_net_contract_ticks == 6


def test_late_receipt_after_session_boundary_keeps_original_contract_and_entry_source(ledger):
    pending(ledger)
    tomorrow = "2025-04-08"
    boundary_time = l.target.window(tomorrow)[0]
    append(ledger, l.SessionBoundary("next-day", tomorrow, boundary_time))
    append(ledger, fill(source_session=tomorrow, observed_at_ns=boundary_time + SECOND))
    state = ledger.snapshot()
    assert state.current_session == tomorrow and state.position is None
    assert state.closed_net_contract_ticks == 6


def test_delayed_entry_receipt_preserves_execution_source_not_later_observation_day(ledger):
    tomorrow = "2025-04-08"
    observed = l.target.window(tomorrow)[0]
    append(ledger, entry(source_session=tomorrow, observed_at_ns=observed))
    assert ledger.snapshot().position.entry_source_session == DAY
    assert ledger.snapshot().current_session == tomorrow


def test_late_new_entry_cannot_backdate_inventory_overlap_after_a_closed_position(ledger):
    append(ledger, entry())
    append(ledger, intent())
    append(ledger, fill())
    before = ledger.snapshot()
    assert before.execution_watermark_ns == fill().executed_at_ns
    with pytest.raises(l.LedgerError, match="overlap already reconciled"):
        append(
            ledger,
            entry(
                event_id="late-other-entry",
                position_id="position-2",
                observed_at_ns=START + 4 * SECOND,
                executed_at_ns=START + SECOND,
                evidence_id="receipt-other-entry",
                paper_receipt_sha256=evidence(3),
            ),
        )
    assert ledger.snapshot() == before


def test_out_of_order_partial_receipts_keep_maximum_inventory_execution_watermark(ledger):
    append(ledger, entry())
    append(ledger, intent())
    append(ledger, fill(quantity_contracts=1, executed_at_ns=START + 3 * SECOND))
    append(
        ledger,
        fill(
            event_id="late-earlier-fill",
            observed_at_ns=START + 4 * SECOND,
            executed_at_ns=START + 2 * SECOND,
            quantity_contracts=1,
            evidence_id="receipt-late-earlier-fill",
            paper_receipt_sha256=evidence(3),
        ),
    )
    before = ledger.snapshot()
    assert before.position is None and before.execution_watermark_ns == START + 3 * SECOND
    with l.ScenarioLedger(ledger.path, config()) as reader:
        assert reader.snapshot() == before
    append(
        ledger,
        entry(
            event_id="entry-after-all-executions",
            position_id="position-2",
            observed_at_ns=START + 5 * SECOND,
            executed_at_ns=START + 3 * SECOND,
            evidence_id="receipt-after-all-executions",
            paper_receipt_sha256=evidence(4),
        ),
    )
    assert ledger.snapshot().position.position_id == "position-2"


def test_contract_roll_does_not_liquidate_roll_or_mark_old_inventory(ledger):
    day = "2025-06-06"
    start = l.target.window(day)[0]
    append(ledger, entry(source_session=day, observed_at_ns=start, executed_at_ns=start))
    append(ledger, intent(source_session=day, observed_at_ns=start + SECOND))
    append(ledger, unknown(source_session=day, observed_at_ns=start + 2 * SECOND))
    roll_day = "2025-06-09"
    observed = l.target.window(roll_day)[0]
    append(ledger, l.SessionBoundary("roll-date", roll_day, observed))
    assert ledger.snapshot().position.contract == "6EM5"
    for event in (
        reference(
            contract="6EU5", source_session=roll_day, quote_at_ns=observed, observed_at_ns=observed
        ),
        fill(
            contract="6EU5",
            source_session=roll_day,
            executed_at_ns=observed,
            observed_at_ns=observed,
        ),
    ):
        with pytest.raises(l.LedgerError, match="contract"):
            append(ledger, event)
    append(ledger, fill(source_session=roll_day, executed_at_ns=observed, observed_at_ns=observed))
    assert ledger.snapshot().position is None


def test_new_session_requires_explicit_boundary_and_global_time_is_monotonic(ledger):
    pending(ledger)
    with pytest.raises(l.LedgerError, match="clock regressed"):
        append(ledger, reference(observed_at_ns=START, quote_at_ns=START))
    tomorrow = "2025-04-08"
    observed = l.target.window(tomorrow)[0]
    with pytest.raises(l.LedgerError, match="Explicit session boundary"):
        append(ledger, fill(source_session=tomorrow, observed_at_ns=observed))


@pytest.mark.parametrize(
    "changes", [{"native_cursor": 9}, {"quote_at_ns": START + SECOND}, {"bid_nano": 99 * TICK}]
)
def test_reference_cannot_regress_or_rewrite_published_native_cursor(ledger, changes):
    pending(ledger)
    append(ledger, reference())
    with pytest.raises(l.LedgerError):
        append(ledger, reference(event_id="next-ref", observed_at_ns=START + 4 * SECOND, **changes))


def test_new_session_resets_only_native_cursor_namespace_not_account(ledger):
    pending(ledger)
    append(ledger, reference())
    tomorrow = "2025-04-08"
    observed = l.target.window(tomorrow)[0]
    append(ledger, l.SessionBoundary("next-day", tomorrow, observed))
    append(
        ledger,
        reference(
            event_id="new-native-day",
            source_session=tomorrow,
            quote_at_ns=observed,
            observed_at_ns=observed,
            native_cursor=0,
        ),
    )
    assert ledger.snapshot().position.remaining_contracts == 2
    assert ledger.snapshot().reference_age_ns == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity_contracts": 3},
        {"request_id": "wrong"},
        {"contract": "6EU5"},
        {"executed_at_ns": START},
    ],
)
def test_invalid_exit_receipt_rolls_back_without_changing_state(ledger, changes):
    pending(ledger)
    before = ledger.snapshot()
    with pytest.raises(l.LedgerError):
        append(ledger, fill(**changes))
    assert ledger.snapshot() == before


def test_duplicate_identical_event_is_idempotent_even_with_old_tip(ledger):
    before = ledger.snapshot().tip_sha256
    event = entry()
    assert ledger.append(event, expected_tip_sha256=before)
    append(ledger, intent())
    state = ledger.snapshot()
    assert not ledger.append(event, expected_tip_sha256=before)
    assert ledger.snapshot() == state
    with pytest.raises(l.LedgerConflict, match="different content"):
        ledger.append(entry(price_nano=102 * TICK), expected_tip_sha256=before)


@pytest.mark.parametrize("reuse", ["evidence_id", "paper_receipt_sha256"])
def test_same_receipt_under_new_event_id_cannot_double_fill(ledger, reuse):
    pending(ledger)
    append(ledger, fill(quantity_contracts=1))
    before = ledger.snapshot()
    changes = {
        "event_id": "changed-event",
        "quantity_contracts": 1,
        "evidence_id": "new-evidence",
        "paper_receipt_sha256": evidence(3),
    }
    changes[reuse] = getattr(fill(), reuse)
    with pytest.raises(l.LedgerError, match="two incremental events"):
        append(ledger, fill(**changes))
    assert ledger.snapshot() == before


def test_closed_position_and_cancelled_request_ids_cannot_be_reused(ledger):
    append(ledger, entry())
    append(ledger, intent())
    append(ledger, fill())
    with pytest.raises(l.LedgerError, match="Position identifiers"):
        append(
            ledger,
            entry(
                event_id="new-entry",
                observed_at_ns=START + 4 * SECOND,
                executed_at_ns=START + 4 * SECOND,
                evidence_id="new-receipt",
                paper_receipt_sha256=evidence(3),
            ),
        )
    append(
        ledger,
        entry(
            event_id="entry-2",
            position_id="position-2",
            observed_at_ns=START + 4 * SECOND,
            executed_at_ns=START + 4 * SECOND,
            evidence_id="new-receipt",
            paper_receipt_sha256=evidence(3),
        ),
    )
    with pytest.raises(l.LedgerError, match="request identifiers"):
        append(
            ledger,
            intent(
                event_id="new-intent", position_id="position-2", observed_at_ns=START + 5 * SECOND
            ),
        )


def test_cancel_confirmation_requires_exact_remainder_and_does_not_admit_late_fill(ledger):
    pending(ledger)
    before = ledger.snapshot()
    with pytest.raises(l.LedgerError, match="exact remainder"):
        append(
            ledger,
            l.CancelReceipt(
                "cancel", DAY, START + 3 * SECOND, "exit-1", 1, "receipt-cancel", evidence(3)
            ),
        )
    assert ledger.snapshot() == before
    append(
        ledger,
        l.CancelReceipt(
            "cancel", DAY, START + 3 * SECOND, "exit-1", 2, "receipt-cancel", evidence(3)
        ),
    )
    with pytest.raises(l.LedgerError, match="outstanding exit"):
        append(ledger, fill(observed_at_ns=START + 4 * SECOND))


def test_pending_request_cannot_be_cancel_confirmed_without_intent_or_unknown(ledger):
    append(ledger, entry())
    append(ledger, intent())
    with pytest.raises(l.LedgerError, match="explicit reconciliation"):
        append(
            ledger,
            l.CancelReceipt(
                "cancel", DAY, START + 2 * SECOND, "exit-1", 2, "receipt-cancel", evidence(3)
            ),
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"scenario_id": "wrong"},
        {"policy_id": "different"},
        {"exit_plan": "time_exit"},
        {"source_manifest_sha256": "b" * 64},
        {"simulator_version": "other-v2"},
        {"extra_round_trip_ticks_per_contract": 2},
        {"max_position_contracts": 1},
    ],
)
def test_reopen_never_adopts_different_scenario_parameters(ledger, changes):
    pending(ledger)
    before = ledger.snapshot()
    with pytest.raises(l.LedgerError, match="Scenario identity"):
        l.ScenarioLedger(ledger.path, config(**changes))
    assert ledger.snapshot() == before


def test_read_only_default_and_create_never_overwrite_existing_evidence(ledger):
    append(ledger, entry())
    with l.ScenarioLedger(ledger.path, config()) as reader:
        with pytest.raises(l.LedgerError, match="Read-only"):
            append(reader, intent())
    with pytest.raises(FileExistsError):
        l.ScenarioLedger.create(ledger.path, config())
    assert ledger.snapshot().position.remaining_contracts == 2


def test_stale_snapshot_and_concurrent_connections_cannot_reserve_twice(ledger):
    append(ledger, entry())
    tip = ledger.snapshot().tip_sha256

    def compete(number):
        with l.ScenarioLedger(ledger.path, config(), read_only=False) as writer:
            try:
                writer.append(
                    intent(event_id=f"intent-{number}", request_id=f"exit-{number}"),
                    expected_tip_sha256=tip,
                )
                return "recorded"
            except l.LedgerConflict:
                return "stale"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(compete, (1, 2))) == ["recorded", "stale"]
    assert ledger.snapshot().reservation.remaining_contracts == 2


def test_injected_failure_after_insert_rolls_back_atomically(ledger, monkeypatch):
    append(ledger, entry())
    before = ledger.snapshot()
    original, calls = ledger._state, 0

    def fail():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Injected after insert, before commit")
        return original()

    monkeypatch.setattr(ledger, "_state", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        ledger.append(intent(), expected_tip_sha256=before.tip_sha256)
    monkeypatch.setattr(ledger, "_state", original)
    assert ledger.snapshot() == before


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity_contracts": True},
        {"quantity_contracts": 0},
        {"quantity_contracts": 1.5},
        {"observed_at_ns": True},
        {"executed_at_ns": START + 1},
        {"price_nano": 101 * TICK + 1},
        {"price_nano": float("nan")},
        {"contract": "EURUSD"},
        {"side": "BUY"},
        {"paper_receipt_sha256": "A" * 64},
        {"source_session": "2026-01-01"},
        {"source_session": "2025-04-08"},
        {"event_id": "../../bad"},
    ],
)
def test_invalid_typed_receipts_fail_before_any_write(changes, ledger):
    before = ledger.snapshot()
    with pytest.raises(ValueError):
        append(ledger, entry(**changes))
    assert ledger.snapshot() == before


def test_reserved_scope_rejects_before_quote_price_access():
    class Poison:
        def __lt__(self, other):
            pytest.fail("Reserved event inspected prices")

    with pytest.raises(ValueError):
        reference(source_session="2026-01-01", bid_nano=Poison())


@pytest.mark.parametrize("change", ["hash", "sequence", "payload", "schema", "application"])
def test_corrupt_database_is_unusable_not_repaired(ledger, change):
    pending(ledger)
    with sqlite3.connect(ledger.path) as db:
        db.execute("DROP TRIGGER events_no_update")
        if change == "hash":
            db.execute("UPDATE events SET sha256=? WHERE sequence=1", ("f" * 64,))
        elif change == "sequence":
            db.execute("UPDATE events SET sequence=10 WHERE sequence=3")
        elif change == "payload":
            db.execute("UPDATE events SET payload=? WHERE sequence=1", (b'{"bad":NaN}',))
        elif change == "schema":
            db.execute("PRAGMA user_version=99")
        else:
            db.execute("PRAGMA application_id=0")
    with pytest.raises(l.LedgerError):
        ledger.snapshot()
    with pytest.raises(l.LedgerError):
        l.ScenarioLedger(ledger.path, config())


def test_sql_append_only_triggers_reject_changes(ledger):
    append(ledger, entry())
    with sqlite3.connect(ledger.path) as db:
        for sql in (
            "DELETE FROM events",
            "UPDATE config SET sha256='changed'",
            "UPDATE events SET event_id='changed'",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="Append-only"):
                db.execute(sql)


def test_external_tip_pin_detects_valid_prefix_truncation(ledger):
    pending(ledger)
    trusted = ledger.snapshot().tip_sha256
    with sqlite3.connect(ledger.path) as db:
        db.execute("DROP TRIGGER events_no_delete")
        db.execute("DELETE FROM events WHERE sequence=3")
        # Restore schema to demonstrate the independent tip guard, not missing triggers.
        db.execute(next(row[3] for row in l._schema_rows() if row[1] == "events_no_delete"))
    with pytest.raises(l.LedgerConflict, match="trusted pin"):
        ledger.snapshot(expected_tip_sha256=trusted)


def test_source_drift_blocks_snapshot_and_append_before_commit(ledger, monkeypatch):
    append(ledger, entry())
    tip = ledger.snapshot().tip_sha256
    monkeypatch.setattr(l, "_fingerprints", lambda: {"changed": "f" * 64})
    with pytest.raises(l.LedgerError, match="frozen source"):
        ledger.append(intent(), expected_tip_sha256=tip)
    assert ledger._db.execute("SELECT count(*) FROM events").fetchone()[0] == 1


def test_event_bound_preserves_existing_inventory(tmp_path, monkeypatch):
    monkeypatch.setattr(l, "MAX_EVENTS", 2)
    with l.ScenarioLedger.create(tmp_path / "bounded.sqlite", config()) as ledger:
        append(ledger, entry())
        append(ledger, intent())
        before = ledger.snapshot()
        with pytest.raises(l.LedgerError, match="count bound"):
            append(ledger, unknown())
        assert ledger.snapshot() == before


def test_missing_empty_wrong_suffix_or_linked_path_does_not_initialize(tmp_path, monkeypatch):
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(l.LedgerError, match="explicit initialization"):
        l.ScenarioLedger(missing, config())
    assert not missing.exists()
    empty = tmp_path / "empty.sqlite"
    empty.touch()
    with pytest.raises(l.LedgerError):
        l.ScenarioLedger(empty, config())
    with pytest.raises(l.LedgerError, match="separate .sqlite"):
        l.ScenarioLedger.create(tmp_path / "different.json", config())
    original = l.os.path.isjunction
    monkeypatch.setattr(l.os.path, "isjunction", lambda path: path == tmp_path or original(path))
    with pytest.raises(l.LedgerError, match="junction"):
        l.ScenarioLedger.create(tmp_path / "linked.sqlite", config())
    assert not (tmp_path / "linked.sqlite").exists()


def test_abrupt_process_exit_recovery_on_each_side_of_commit(tmp_path):
    path = tmp_path / "crash.sqlite"
    cfg = config()
    with l.ScenarioLedger.create(path, cfg) as ledger:
        append(ledger, entry())
        expected = ledger.snapshot()
    setup = (
        "from ai_trader.research import six_e_position_ledger as l; "
        "import json,os,sys; from pathlib import Path; "
        "c=l.ScenarioConfig(**json.loads(sys.argv[2])); "
        "ledger=l.ScenarioLedger(Path(sys.argv[1]),c,read_only=False); "
        "tip=ledger.snapshot().tip_sha256; "
    )
    record = f"e=l.ExitIntent('request-1','{DAY}',{START + SECOND},'exit-1','position-1',2); "
    before = (
        setup + record + "ledger._db.execute('BEGIN IMMEDIATE'); raw=l._record(e); "
        "ledger._db.execute('INSERT INTO events VALUES(2,?,?,?,?)',"
        "(e.event_id,raw,tip,l._hash(tip.encode()+b'\\n'+raw))); os._exit(17)"
    )
    after = setup + record + "ledger.append(e,expected_tip_sha256=tip); os._exit(18)"
    assert (
        subprocess.run(
            [sys.executable, "-c", before, str(path), json.dumps(asdict(cfg))], timeout=30
        ).returncode
        == 17
    )
    with l.ScenarioLedger(path, cfg) as reader:
        assert reader.snapshot() == expected
    assert (
        subprocess.run(
            [sys.executable, "-c", after, str(path), json.dumps(asdict(cfg))], timeout=30
        ).returncode
        == 18
    )
    with l.ScenarioLedger(path, cfg) as reader:
        assert reader.snapshot().reservation.request_id == "exit-1"
        assert reader.snapshot().position.remaining_contracts == 2


def test_noncanonical_duplicate_and_nonfinite_stored_json_refused():
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{ "x":1}', b"[]"):
        with pytest.raises(l.LedgerError):
            l._decode(raw)


def test_protocol_never_grants_scoring_training_or_execution_authority():
    p = l.protocol()
    for key in (
        "training_eligible",
        "strategy_scoring_allowed",
        "trading_enabled",
        "promotion_allowed",
        "broker_execution_confirmed",
        "receipt_provenance_verified",
    ):
        assert p[key] is False


def test_schema_drift_without_payload_change_also_blocks_read_and_write(ledger):
    append(ledger, entry())
    with sqlite3.connect(ledger.path) as db:
        db.execute("DROP TRIGGER events_no_delete")
    with pytest.raises(l.LedgerError, match="append-only triggers"):
        ledger.snapshot()
    with pytest.raises(l.LedgerError, match="append-only triggers"):
        append(ledger, intent())


def test_schema_validation_does_not_hide_names_that_only_match_sql_like_wildcards(ledger):
    with sqlite3.connect(ledger.path) as db:
        db.execute("CREATE TABLE sqliteXextra (value INTEGER)")
    with pytest.raises(l.LedgerError, match="schema"):
        ledger.snapshot()


def test_quantity_limit_refuses_imported_entry_receipt_without_inventory(ledger):
    before = ledger.snapshot()
    with pytest.raises(l.LedgerError, match="quantity limit"):
        append(ledger, entry(quantity_contracts=3))
    assert ledger.snapshot() == before


@pytest.mark.parametrize(
    "changes",
    [
        {"extra_round_trip_ticks_per_contract": True},
        {"extra_round_trip_ticks_per_contract": -1},
        {"max_position_contracts": True},
        {"max_position_contracts": 1001},
        {"exit_plan": "best_future"},
        {"source_manifest_sha256": "missing"},
    ],
)
def test_invalid_config_does_not_claim_a_new_database(tmp_path, changes):
    path = tmp_path / "invalid.sqlite"
    with pytest.raises(l.LedgerError):
        l.ScenarioLedger.create(path, config(**changes))
    assert not path.exists()


def test_bad_receipt_type_and_read_only_flag_do_not_grant_write_access(ledger):
    before = ledger.snapshot()
    with pytest.raises(l.LedgerError, match="Typed"):
        append(ledger, {"kind": "EntryFill", "data": asdict(entry())})
    with pytest.raises(l.LedgerError, match="Boolean"):
        l.ScenarioLedger(ledger.path, config(), read_only=0)
    assert ledger.snapshot() == before


def test_mid_transaction_source_drift_rolls_back_insert(ledger, monkeypatch):
    append(ledger, entry())
    before = ledger.snapshot()
    original, calls = l._fingerprints, 0

    def drift():
        nonlocal calls
        calls += 1
        return original() if calls == 1 else {"mid_transaction_drift": "f" * 64}

    monkeypatch.setattr(l, "_fingerprints", drift)
    with pytest.raises(l.LedgerError, match="frozen source"):
        ledger.append(intent(), expected_tip_sha256=before.tip_sha256)
    monkeypatch.setattr(l, "_fingerprints", original)
    assert ledger.snapshot() == before


def test_oversized_event_payload_refused_without_a_durable_event(ledger, monkeypatch):
    before = ledger.snapshot()
    monkeypatch.setattr(l, "MAX_RECORD_BYTES", 10)
    with pytest.raises(l.LedgerError, match="byte bound"):
        ledger.append(entry(), expected_tip_sha256=before.tip_sha256)
    assert ledger._db.execute("SELECT count(*) FROM events").fetchone()[0] == 0


def test_oversized_database_refused_before_content_recovery(ledger, monkeypatch):
    monkeypatch.setattr(l, "MAX_DB_BYTES", 1)
    with pytest.raises(l.LedgerError, match="oversized"):
        l.ScenarioLedger(ledger.path, config())
