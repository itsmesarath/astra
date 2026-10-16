"""Invented causal roundtrip controls, independent of the new implementation."""

from __future__ import annotations

import ast
import builtins
import hashlib
import inspect
import json
import socket
import subprocess
import time
from dataclasses import FrozenInstanceError, asdict, fields, replace

import pytest

from ai_trader.research import six_e_declared_admission as admission
from ai_trader.research import six_e_entry_budget as budget
from ai_trader.research import six_e_native_admission_assessment as assessment
from ai_trader.research import six_e_native_prefix as native
from ai_trader.research import six_e_single_roundtrip_driver as driver

START = 10_000_000_000
PUB = 11_000_000_000
READY = PUB + 100_000_000
ENTRY_DEADLINE = READY + 1_000_000_000
HOLD = READY + 15_000_000_000
EXIT_READY = HOLD + 100_000_000
EXIT_DEADLINE = EXIT_READY + 1_000_000_000
END = 100_000_000_000
TICK = 50_000
PRICE = 1_000_000_000
SOURCE = "a" * 64
VERSION = "six_e_single_roundtrip_driver_v1"
STATUS = "constructed_single_roundtrip_plan_not_trading"


def canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def changed(value, **changes):
    """Test-only poisoning reaches the consumer, not eager constructor validation."""
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(result, field.name, getattr(value, field.name))
    for name, replacement in changes.items():
        object.__setattr__(result, name, replacement)
    return result


def subclass_copy(value):
    cls = type("ConstructedSubclass", (type(value),), {})
    result = object.__new__(cls)
    for field in fields(value):
        object.__setattr__(result, field.name, getattr(value, field.name))
    return result


class IntSubclass(int):
    pass


class StrSubclass(str):
    pass


class TupleSubclass(tuple):
    pass


def safe_id(value):
    return (
        repr(value) if type(value) in (str, int, float, bool, type(None)) else type(value).__name__
    )


def forbidden(*args, **kwargs):
    raise AssertionError("Forbidden traversal or external operation was reached")


def quote(at, bid=PRICE, spread=TICK):
    return native.NativeQuote(at, bid, bid + spread)


def crossed_quote(at, side, entry_price, favorable_ticks, spread=TICK):
    crossed = entry_price + favorable_ticks * TICK * (1 if side == "long" else -1)
    return quote(at, crossed if side == "long" else crossed - spread, spread)


def fixture(rows=None, *, end=END, contract="6EM5"):
    if rows is None:
        rows = (
            quote(PUB),
            quote(PUB, PRICE + 20 * TICK),
            quote(READY),
            quote(HOLD - 1),
            quote(HOLD, PRICE + 30 * TICK),
            quote(EXIT_READY, PRICE + 4 * TICK, 3 * TICK),
            quote(EXIT_DEADLINE + 1),
        )
    cursor = next(i for i, row in enumerate(rows) if row.received_at_ns == PUB)
    return native.NativeFixture(
        "synthetic-roundtrip-tape",
        contract,
        SOURCE,
        START,
        end,
        tuple(rows),
        (native.NativePublication("pub-1", cursor, PUB),),
    )


def genesis(*, balance=135, entry=10, exit_fee=20, margin=100, buffer=5, age=0, loss=None):
    margin_value = None if margin is None else budget.economics.DeclaredMargin(margin, margin)
    return admission.DeclaredAdmissionGenesis(
        "synthetic-roundtrip-account",
        budget.EconomicSeed(balance, START),
        budget.DeclaredEconomics("USD", 625, entry, exit_fee, margin_value),
        budget.DeclaredBudgetLimits(buffer, age, loss),
    )


def declaration(side="long", plan="bracket_exit"):
    return driver.SingleRoundtripDeclaration("synthetic-roundtrip", "pub-1", "entry-1", side, plan)


def metadata(tape):
    return {
        "version": "six_e_native_prefix_v1",
        "source_session": tape.source_session,
        "contract": tape.contract,
        "source_sha256": tape.source_sha256,
        "start_ns": tape.start_ns,
        "end_ns": tape.end_ns,
        "tick_nano": TICK,
    }


def fixture_pin(tape):
    return digest(
        {
            "version": "six_e_native_prefix_v1",
            "kind": "complete_constructed_native_fixture",
            "metadata": metadata(tape),
            "quote_count": len(tape.quotes),
            "publication_count": len(tape.publications),
            "quotes": [[q.received_at_ns, q.bid_nano, q.ask_nano] for q in tape.quotes],
            "publications": [asdict(p) for p in tape.publications],
        }
    )


def genesis_pin(account):
    return digest(
        {
            "version": "six_e_declared_admission_v1",
            "scope": "constructed_declared_admission_not_authenticated",
            "delay_ns": 100_000_000,
            "wait_ns": 1_000_000_000,
            "quantity_contracts": 1,
            "genesis": asdict(account),
        }
    )


def declaration_body(proposal, fp, gp):
    return {
        "version": VERSION,
        "scope": STATUS,
        "protocol": {
            "tick_nano": 50000,
            "entry_delay_ns": 100000000,
            "entry_wait_ns": 1000000000,
            "exit_delay_ns": 100000000,
            "exit_wait_ns": 1000000000,
            "hold_ns": 15000000000,
            "target_ticks": 3,
            "stop_ticks": -3,
            "comparator_cost_ticks": 1,
            "end_buffer_ns": 18000000000,
            "quantity_contracts": 1,
            "max_quotes": 128,
            "max_publications": 1,
            "max_accounting_records": 5,
            "max_result_bytes": 65536,
            "clock_event_id": "publication-clock",
            "request_event_id": "admission-request",
            "entry_outcome_event_id": "entry-outcome",
            "entry_receipt_id": "constructed-entry-receipt",
            "exit_request_event_id": "exit-request",
            "exit_request_id": "constructed-exit-request",
            "exit_outcome_event_id": "exit-outcome",
            "exit_receipt_id": "constructed-exit-receipt",
        },
        "fixture_sha256": fp,
        "genesis_sha256": gp,
        "declaration": asdict(proposal),
    }


def arguments(tape, account, proposal):
    fp, gp = fixture_pin(tape), genesis_pin(account)
    return {
        "expected_fixture_sha256": fp,
        "expected_genesis_sha256": gp,
        "expected_declaration_sha256": digest(declaration_body(proposal, fp, gp)),
    }


def build(tape=None, account=None, proposal=None):
    tape = fixture() if tape is None else tape
    account = genesis() if account is None else account
    proposal = declaration() if proposal is None else proposal
    return driver.build_single_roundtrip_plan(
        tape, account, proposal, **arguments(tape, account, proposal)
    )


def prefixes_and_audit(tape):
    """Independent linear consumed chain; no new builder or held prefix generator."""
    content = digest(
        {
            "version": "six_e_native_prefix_v1",
            "kind": "consumed_metadata_seed",
            "metadata": metadata(tape),
        }
    )
    fp = fixture_pin(tape)
    prefixes = [
        native.NativePrefix(
            fp,
            tape.source_session,
            tape.contract,
            tape.source_sha256,
            tape.start_ns,
            tape.end_ns,
            len(tape.quotes),
            len(tape.publications),
            0,
            None,
            None,
            None,
            content,
        )
    ]
    audit, last_time, group_first = [], None, None
    for cursor, row in enumerate(tape.quotes):
        if row.received_at_ns != last_time:
            group_first = cursor
        last_time = row.received_at_ns
        content = digest(
            {
                "version": "six_e_native_prefix_v1",
                "kind": "consumed_quote",
                "previous_sha256": content,
                "native_cursor": cursor,
                "quote": [row.received_at_ns, row.bid_nano, row.ask_nano],
            }
        )
        prefixes.append(
            native.NativePrefix(
                fp,
                tape.source_session,
                tape.contract,
                tape.source_sha256,
                tape.start_ns,
                tape.end_ns,
                len(tape.quotes),
                len(tape.publications),
                cursor + 1,
                cursor,
                last_time,
                group_first,
                content,
            )
        )
        audit.append(
            {
                "cursor": cursor,
                "received_at_ns": last_time,
                "consumed_count": cursor + 1,
                "consumed_content_sha256": content,
            }
        )
    return prefixes, tuple(audit)


def boundary_oracle(tape, prefixes, through):
    count = next(
        (i for i, row in enumerate(tape.quotes) if row.received_at_ns > through), len(tape.quotes)
    )
    return native.ClosedNativeBoundary(
        prefixes[count],
        through,
        "next_timestamp" if count < len(tape.quotes) else "complete_eof",
        count if count < len(tape.quotes) else None,
        tape.quotes[count].received_at_ns if count < len(tape.quotes) else None,
    )


def receipt_content_pin(gp, payload, liability, position, at):
    body = asdict(payload)
    del body["receipt_id"]
    return digest(
        {
            "genesis_sha256": gp,
            "phase": type(payload).__name__,
            "liability": asdict(liability),
            "position": asdict(position) if position else None,
            "recorded_at_ns": at,
            "receipt": body,
        }
    )


def oracle(tape, account, proposal):
    """Select all original intervals algebraically and construct every event/hash/state."""
    args = arguments(tape, account, proposal)
    fp, gp = args["expected_fixture_sha256"], args["expected_genesis_sha256"]
    prefixes, audit = prefixes_and_audit(tape)
    pub = tape.publications[0]
    pub_prefix = prefixes[pub.published_cursor + 1]
    witness = native.PublicationWitness(
        pub.publication_id, pub.published_cursor, pub.received_at_ns, pub_prefix
    )
    prefix = admission.DeclaredPrefix(0, gp, account.seed.initialized_at_ns)
    records, links = [], []

    def append(event, at, payload, observed, kind, publication=None, boundary=None):
        nonlocal prefix
        record = admission.DeclaredRecord(event, prefix, at, at, payload)
        head = digest(
            {
                "version": "six_e_declared_admission_v1",
                "kind": type(payload).__name__,
                "record": asdict(record),
            }
        )
        prefix = admission.DeclaredPrefix(len(records) + 1, head, at)
        links.append(
            {
                "record_index": len(records),
                "event_id": event,
                "record_sha256": head,
                "native_prefix": asdict(observed),
                "kind": kind,
                "publication": asdict(publication) if publication is not None else None,
                "boundary": asdict(boundary) if boundary is not None else None,
            }
        )
        records.append(record)

    append(
        "publication-clock",
        pub.received_at_ns,
        admission.ClockAdvanced(),
        pub_prefix,
        "publication",
        witness,
    )
    snapshot = budget.DeclaredCapitalSnapshot(
        account.seed,
        account.seed.initial_balance_usd_micros,
        1,
        prefix.head_sha256,
        pub.received_at_ns,
        pub.received_at_ns,
        0,
        0,
        None,
        False,
    )
    offered = budget.EntryProposal(pub.received_at_ns, 1, prefix.head_sha256, tape.contract, 1)
    decision = budget.assess_entry_budget(snapshot, offered, account.economics, account.limits)
    append(
        "admission-request",
        pub.received_at_ns,
        admission.AdmissionRequested(proposal.admission_id, tape.contract, proposal.side, 1),
        pub_prefix,
        "publication",
        witness,
    )
    entry_outcome, entry_cursor, entry_at = "no_pending_entry", None, None
    hold_at = reason = trigger_cursor = requested_at = None
    exit_outcome, exit_cursor, exit_at = "no_exit", None, None
    position = pending_exit = None
    gross = entry_fees = exit_fees = 0
    receipt_pins = ()
    ready = pub.received_at_ns + 100_000_000
    deadline = ready + 1_000_000_000
    if decision.disposition == "declared_budget_available":
        entry_cursor = next(
            (i for i, q in enumerate(tape.quotes) if ready <= q.received_at_ns <= deadline), None
        )
        if entry_cursor is None:
            entry_outcome, entry_at = "constructed_entry_timeout", deadline
            boundary = boundary_oracle(tape, prefixes, deadline)
            append(
                "entry-outcome",
                deadline,
                admission.EntryUnfilled(proposal.admission_id, "timeout"),
                boundary.prefix,
                "entry_deadline_boundary",
                boundary=boundary,
            )
        else:
            row = tape.quotes[entry_cursor]
            entry_at = row.received_at_ns
            if row.ask_nano - row.bid_nano != TICK:
                entry_outcome = "simulator_spread_refusal"
                append(
                    "entry-outcome",
                    entry_at,
                    admission.EntryUnfilled(proposal.admission_id, "simulator_refusal"),
                    prefixes[entry_cursor + 1],
                    "entry_candidate_quote",
                )
            else:
                entry_outcome = "constructed_entry_receipt"
                entry_price = row.ask_nano if proposal.side == "long" else row.bid_nano
                pending = admission.DeclaredPendingAdmission(
                    proposal.admission_id,
                    tape.contract,
                    proposal.side,
                    1,
                    pub.received_at_ns,
                    ready,
                    deadline,
                )
                payload = admission.EntryReceipt(
                    proposal.admission_id,
                    "constructed-entry-receipt",
                    tape.contract,
                    proposal.side,
                    1,
                    entry_price,
                    entry_at,
                )
                receipt_pins = (receipt_content_pin(gp, payload, pending, None, entry_at),)
                append(
                    "entry-outcome",
                    entry_at,
                    payload,
                    prefixes[entry_cursor + 1],
                    "entry_candidate_quote",
                )
                position = admission.DeclaredPosition(
                    proposal.admission_id, tape.contract, proposal.side, 1, entry_price, entry_at
                )
                entry_fees = account.economics.entry_fee_usd_micros_per_contract
                hold_at = entry_at + 15_000_000_000
                if proposal.exit_plan == "bracket_exit":
                    for i in range(entry_cursor, len(tape.quotes)):
                        q = tape.quotes[i]
                        if q.received_at_ns >= hold_at:
                            break
                        comparison = (
                            (q.bid_nano - entry_price) // TICK
                            if proposal.side == "long"
                            else (entry_price - q.ask_nano) // TICK
                        ) - 1
                        if comparison >= 3 or comparison <= -3:
                            reason = "target" if comparison >= 3 else "stop"
                            trigger_cursor, requested_at = i, q.received_at_ns
                            break
                if requested_at is None:
                    reason, requested_at = "hold_timer", hold_at
                    boundary = boundary_oracle(tape, prefixes, hold_at - 1)
                    append(
                        "exit-request",
                        requested_at,
                        admission.ExitRequested(proposal.admission_id, "constructed-exit-request"),
                        boundary.prefix,
                        "hold_boundary",
                        boundary=boundary,
                    )
                else:
                    append(
                        "exit-request",
                        requested_at,
                        admission.ExitRequested(proposal.admission_id, "constructed-exit-request"),
                        prefixes[trigger_cursor + 1],
                        "bracket_trigger_quote",
                    )
                exit_ready, exit_deadline = requested_at + 100_000_000, requested_at + 1_100_000_000
                pending_exit = admission.DeclaredExit(
                    "constructed-exit-request", requested_at, exit_ready, exit_deadline, "PENDING"
                )
                exit_cursor = next(
                    (
                        i
                        for i, q in enumerate(tape.quotes)
                        if exit_ready <= q.received_at_ns <= exit_deadline
                    ),
                    None,
                )
                if exit_cursor is None:
                    exit_outcome, exit_at = "constructed_exit_unknown", exit_deadline
                    boundary = boundary_oracle(tape, prefixes, exit_deadline)
                    append(
                        "exit-outcome",
                        exit_at,
                        admission.ExitUnknown("constructed-exit-request"),
                        boundary.prefix,
                        "exit_deadline_boundary",
                        boundary=boundary,
                    )
                    pending_exit = replace(pending_exit, status="UNKNOWN")
                else:
                    exit_outcome = "constructed_exit_receipt"
                    q = tape.quotes[exit_cursor]
                    exit_at = q.received_at_ns
                    exit_price = q.bid_nano if proposal.side == "long" else q.ask_nano
                    payload = admission.ExitReceipt(
                        "constructed-exit-request",
                        "constructed-exit-receipt",
                        tape.contract,
                        1,
                        exit_price,
                        exit_at,
                    )
                    receipt_pins += (
                        receipt_content_pin(gp, payload, pending_exit, position, exit_at),
                    )
                    append(
                        "exit-outcome",
                        exit_at,
                        payload,
                        prefixes[exit_cursor + 1],
                        "exit_candidate_quote",
                    )
                    gross = (
                        (exit_price - entry_price) // TICK * account.economics.tick_value_usd_micros
                    )
                    gross *= 1 if proposal.side == "long" else -1
                    exit_fees = account.economics.exit_fee_usd_micros_per_contract
                    position = pending_exit = None
    balance = account.seed.initial_balance_usd_micros + gross - entry_fees - exit_fees
    liability = position is not None
    margin = account.economics.margin.initial_usd_micros_per_contract if liability else 0
    reserve = account.economics.exit_fee_usd_micros_per_contract if liability else 0
    terminal = admission.DeclaredAdmissionState(
        "six_e_declared_admission_v1",
        "constructed_declared_admission_not_authenticated",
        gp,
        prefix,
        prefix.complete_through_ns,
        "EXIT_UNKNOWN" if liability else "FLAT",
        balance,
        gross,
        entry_fees,
        exit_fees,
        max(0, -balance),
        0,
        margin,
        reserve,
        margin + reserve,
        balance - margin - reserve,
        None if liability else balance,
        None if liability else balance - account.seed.initial_balance_usd_micros,
        None,
        position,
        pending_exit,
        receipt_pins,
        admission.AUTHORITY_FLAGS,
    )
    # Complete held reconstruction must independently agree with manually derived state and heads.
    assert (
        admission.reconstruct(
            account, tuple(records), expected_genesis_sha256=gp, expected_terminal=prefix
        )
        == terminal
    )
    body = {
        "version": VERSION,
        "status": STATUS,
        "fixture_sha256": fp,
        "genesis_sha256": gp,
        "declaration_sha256": args["expected_declaration_sha256"],
        "declaration": asdict(proposal),
        "publication": asdict(witness),
        "budget_decision": asdict(decision),
        "first_disposition": decision.disposition,
        "entry_execution_outcome": entry_outcome,
        "entry_outcome_cursor": entry_cursor,
        "entry_outcome_at_ns": entry_at,
        "hold_at_ns": hold_at,
        "exit_trigger_reason": reason,
        "exit_trigger_cursor": trigger_cursor,
        "exit_requested_at_ns": requested_at,
        "exit_execution_outcome": exit_outcome,
        "exit_outcome_cursor": exit_cursor,
        "exit_outcome_at_ns": exit_at,
        "records": tuple(asdict(r) for r in records),
        "record_links": tuple(links),
        "quote_audit": audit,
        "terminal_native_prefix": asdict(prefixes[-1]),
        "terminal_accounting_state": asdict(terminal),
        "authority_flags": assessment.AUTHORITY_FLAGS,
    }
    return body | {"plan_sha256": digest(body)}


def case_rows(case, side):
    entry = PRICE + TICK if side == "long" else PRICE
    base = (quote(PUB), quote(PUB, PRICE + 20 * TICK), quote(READY))
    if case == "hold_fill":
        return base + (
            quote(HOLD),
            crossed_quote(EXIT_READY, side, entry, 6, 3 * TICK),
            quote(EXIT_DEADLINE + 1),
        )
    if case in ("target_fill", "stop_fill"):
        trigger = READY + 1_000_000_000
        ticks = 4 if case == "target_fill" else -2
        return base + (
            crossed_quote(trigger, side, entry, ticks),
            crossed_quote(trigger + 100_000_000, side, entry, -7, 4 * TICK),
            quote(HOLD + 1),
        )
    if case == "gap_unknown":
        return base + (quote(EXIT_DEADLINE + 1), quote(EXIT_DEADLINE + 1, PRICE + 40 * TICK))
    if case == "eof_unknown":
        return base
    if case == "entry_refusal":
        return (quote(PUB), quote(READY, spread=2 * TICK), quote(READY), quote(HOLD))
    if case == "entry_timeout":
        return (quote(PUB), quote(READY - 1), quote(ENTRY_DEADLINE + 1), quote(HOLD))
    raise AssertionError(case)


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize("plan", ["time_exit", "bracket_exit"])
@pytest.mark.parametrize(
    "case",
    [
        "hold_fill",
        "target_fill",
        "stop_fill",
        "gap_unknown",
        "eof_unknown",
        "entry_refusal",
        "entry_timeout",
    ],
)
def test_full_plan_matches_independent_native_event_receipt_financial_and_link_oracle(
    side, plan, case
):
    tape, account, proposal = fixture(case_rows(case, side)), genesis(), declaration(side, plan)
    expected = oracle(tape, account, proposal)
    result = build(tape, account, proposal)
    assert asdict(result) == expected
    assert (
        driver.verify_single_roundtrip_plan(
            tape,
            account,
            proposal,
            **arguments(tape, account, proposal),
            expected_plan_sha256=expected["plan_sha256"],
        )
        == result
    )


def test_closed_schema_constants_all_false_authorities_and_declaration_oracle():
    tape, account, proposal = fixture(), genesis(), declaration()
    assert driver.VERSION == VERSION and driver.STATUS == STATUS
    constants = {
        "MAX_DRIVER_QUOTES": 128,
        "MAX_DRIVER_PUBLICATIONS": 1,
        "MAX_ACCOUNTING_RECORDS": 5,
        "MAX_RESULT_BYTES": 65536,
        "END_BUFFER_NS": 18000000000,
        "HOLD_NS": 15000000000,
        "TARGET_TICKS": 3,
        "STOP_TICKS": -3,
        "COMPARATOR_COST_TICKS": 1,
    }
    for name, value in constants.items():
        assert getattr(driver, name) == value and type(getattr(driver, name)) is int
    assert [f.name for f in fields(driver.SingleRoundtripDeclaration)] == [
        "declaration_id",
        "publication_id",
        "admission_id",
        "side",
        "exit_plan",
    ]
    assert [f.name for f in fields(driver.SingleRoundtripPlan)] == [
        "version",
        "status",
        "fixture_sha256",
        "genesis_sha256",
        "declaration_sha256",
        "declaration",
        "publication",
        "budget_decision",
        "first_disposition",
        "entry_execution_outcome",
        "entry_outcome_cursor",
        "entry_outcome_at_ns",
        "hold_at_ns",
        "exit_trigger_reason",
        "exit_trigger_cursor",
        "exit_requested_at_ns",
        "exit_execution_outcome",
        "exit_outcome_cursor",
        "exit_outcome_at_ns",
        "records",
        "record_links",
        "quote_audit",
        "terminal_native_prefix",
        "terminal_accounting_state",
        "plan_sha256",
        "authority_flags",
    ]
    assert [f.name for f in fields(driver.AccountingLink)] == [
        "record_index",
        "event_id",
        "record_sha256",
        "native_prefix",
        "kind",
        "publication",
        "boundary",
    ]
    assert [f.name for f in fields(driver.QuoteAudit)] == [
        "cursor",
        "received_at_ns",
        "consumed_count",
        "consumed_content_sha256",
    ]
    assert (
        driver.declaration_sha256(
            proposal, fixture_sha256=fixture_pin(tape), genesis_sha256=genesis_pin(account)
        )
        == arguments(tape, account, proposal)["expected_declaration_sha256"]
    )
    assert driver.AUTHORITY_FLAGS == assessment.AUTHORITY_FLAGS
    assert all(
        type(pair) is tuple and type(pair[0]) is str and pair[1] is False
        for pair in driver.AUTHORITY_FLAGS
    )


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize(
    "barrier,ticks",
    [("target", 3), ("target", 4), ("target", 5), ("stop", -1), ("stop", -2), ("stop", -3)],
)
def test_bracket_threshold_equality_uses_original_comparator_not_declared_cash(
    side, barrier, ticks
):
    entry = PRICE + TICK if side == "long" else PRICE
    at = READY + 1_000_000_000
    rows = (
        quote(PUB),
        quote(READY),
        crossed_quote(at, side, entry, ticks),
        crossed_quote(at + 100_000_000, side, entry, ticks),
        quote(HOLD),
        quote(EXIT_READY),
    )
    result = build(fixture(rows), proposal=declaration(side))
    expected = barrier if (ticks - 1 >= 3 or ticks - 1 <= -3) else "hold_timer"
    assert result.exit_trigger_reason == expected
    assert result.exit_requested_at_ns == (at if expected != "hold_timer" else HOLD)
    assert result.exit_trigger_cursor == (2 if expected != "hold_timer" else None)


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize("barrier_ticks", [4, -2])
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_hold_equality_wins_over_quote_bracket_and_uses_strict_before_boundary(
    side, barrier_ticks, delta
):
    entry = PRICE + TICK if side == "long" else PRICE
    rows = (
        quote(PUB),
        quote(READY),
        crossed_quote(HOLD + delta, side, entry, barrier_ticks),
        crossed_quote(EXIT_READY + 1, side, entry, 2),
    )
    result = build(fixture(rows), proposal=declaration(side))
    if delta == -1:
        assert result.exit_trigger_reason == ("target" if barrier_ticks == 4 else "stop")
        assert result.exit_requested_at_ns == HOLD - 1
        assert result.record_links[3].kind == "bracket_trigger_quote"
    else:
        assert result.exit_trigger_reason == "hold_timer" and result.exit_requested_at_ns == HOLD
        assert result.exit_trigger_cursor is None
        link = result.record_links[3]
        assert link.kind == "hold_boundary" and link.native_prefix.consumed_count == 2
        assert link.boundary.through_ns == HOLD - 1 and link.boundary.next_cursor == 2
        assert link.boundary.next_received_at_ns == HOLD + delta


@pytest.mark.parametrize("side", ["long", "short"])
def test_time_plan_ignores_early_barrier_and_hold_uses_actual_receipt_time(side):
    filled_at = READY + 123
    hold_at = filled_at + 15_000_000_000
    entry = PRICE + TICK if side == "long" else PRICE
    rows = (
        quote(PUB),
        quote(READY - 1),
        quote(filled_at),
        crossed_quote(filled_at + 1, side, entry, 20),
        quote(hold_at),
        crossed_quote(hold_at + 100_000_000, side, entry, -10, 5 * TICK),
    )
    result = build(fixture(rows), proposal=declaration(side, "time_exit"))
    assert result.entry_outcome_at_ns == filled_at
    assert result.hold_at_ns == result.exit_requested_at_ns == hold_at
    assert result.exit_trigger_reason == "hold_timer"
    assert result.exit_outcome_cursor == 5


@pytest.mark.parametrize("endpoint", [READY, ENTRY_DEADLINE])
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_entry_original_inclusive_readiness_deadline_or_timeout(endpoint, delta):
    at = endpoint + delta
    tape = fixture((quote(PUB), quote(at), quote(EXIT_DEADLINE + 2)))
    result = build(tape, proposal=declaration(plan="time_exit"))
    valid = READY <= at <= ENTRY_DEADLINE
    assert result.entry_execution_outcome == (
        "constructed_entry_receipt" if valid else "constructed_entry_timeout"
    )
    assert result.entry_outcome_at_ns == (at if valid else ENTRY_DEADLINE)
    assert result.entry_outcome_cursor == (1 if valid else None)
    if not valid:
        assert result.exit_execution_outcome == "no_exit" and result.hold_at_ns is None


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize("endpoint", [EXIT_READY, EXIT_DEADLINE])
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_exit_original_inclusive_readiness_deadline_or_unknown(side, endpoint, delta):
    entry = PRICE + TICK if side == "long" else PRICE
    at = endpoint + delta
    rows = (
        quote(PUB),
        quote(READY),
        quote(HOLD),
        crossed_quote(at, side, entry, -6, 3 * TICK),
        quote(EXIT_DEADLINE + 20),
    )
    result = build(fixture(rows), proposal=declaration(side, "time_exit"))
    valid = EXIT_READY <= at <= EXIT_DEADLINE
    assert result.exit_execution_outcome == (
        "constructed_exit_receipt" if valid else "constructed_exit_unknown"
    )
    assert result.exit_outcome_at_ns == (at if valid else EXIT_DEADLINE)
    assert result.exit_outcome_cursor == (3 if valid else None)
    if valid:
        assert result.records[-1].payload.price_nano == (
            rows[3].bid_nano if side == "long" else rows[3].ask_nano
        )
    else:
        assert result.terminal_accounting_state.phase == "EXIT_UNKNOWN"


@pytest.mark.parametrize("side", ["long", "short"])
def test_equal_time_entry_suffix_can_trigger_exit_but_not_rewrite_publication_or_entry(side):
    entry = PRICE + TICK if side == "long" else PRICE
    rows = (
        quote(PUB),
        quote(PUB, PRICE + 100 * TICK),
        quote(READY),
        crossed_quote(READY, side, entry, 4),
        crossed_quote(READY, side, entry, -20),
        crossed_quote(READY + 100_000_000, side, entry, 2),
    )
    result = build(fixture(rows), proposal=declaration(side))
    assert result.publication.prefix.consumed_count == 1
    assert result.entry_outcome_cursor == 2 and result.entry_outcome_at_ns == READY
    assert result.exit_trigger_cursor == 3 and result.exit_trigger_reason == "target"
    assert result.exit_requested_at_ns == READY and result.exit_outcome_cursor == 5
    assert result.record_links[3].native_prefix.consumed_count == 4


@pytest.mark.parametrize("side", ["long", "short"])
def test_first_widened_entry_permanently_refuses_without_any_exit_or_fees(side):
    rows = (quote(PUB), quote(READY, spread=2 * TICK), quote(READY), quote(HOLD), quote(EXIT_READY))
    result = build(fixture(rows), proposal=declaration(side))
    assert result.first_disposition == "declared_budget_available"
    assert (
        result.entry_execution_outcome == "simulator_spread_refusal"
        and result.entry_outcome_cursor == 1
    )
    assert result.exit_execution_outcome == "no_exit" and result.exit_trigger_reason is None
    assert len(result.records) == 3 and len(result.quote_audit) == 5
    state = result.terminal_accounting_state
    assert state.phase == "FLAT" and state.entry_fees_usd_micros == state.exit_fees_usd_micros == 0


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize("trigger_ticks", [4, -2])
def test_widened_first_exit_keeps_overshoot_and_does_not_search_favorable_suffix(
    side, trigger_ticks
):
    entry = PRICE + TICK if side == "long" else PRICE
    requested = READY + 1_000_000_000
    at = requested + 100_000_000
    rows = (
        quote(PUB),
        quote(READY),
        crossed_quote(requested, side, entry, trigger_ticks),
        crossed_quote(at, side, entry, -100, 10 * TICK),
        crossed_quote(at, side, entry, 200),
    )
    result = build(fixture(rows), genesis(loss=10), declaration(side))
    state = result.terminal_accounting_state
    assert result.exit_outcome_cursor == 3 and result.exit_outcome_at_ns == at
    assert result.first_disposition == "declared_budget_available"
    assert result.budget_decision.limits.max_cumulative_realization_loss_usd_micros == 10
    assert result.budget_decision.hypothetical_loss_after_entry_fee_usd_micros == 10
    assert state.gross_realized_usd_micros == -100 * 625
    assert state.declared_realization_balance_usd_micros == 135 - 100 * 625 - 10 - 20
    assert state.declared_realization_balance_usd_micros < 0 and state.phase == "FLAT"
    assert (
        state.realization_balance_shortfall_usd_micros
        == -state.declared_realization_balance_usd_micros
    )
    assert state.entry_fees_usd_micros == 10 and state.exit_fees_usd_micros == 20
    assert state.total_commitments_usd_micros == 0
    assert state.complete_declared_net_return_usd_micros == -100 * 625 - 30


@pytest.mark.parametrize("side", ["long", "short"])
def test_first_widened_exit_at_inclusive_deadline_keeps_price_before_favorable_equal_suffix(side):
    entry = PRICE + TICK if side == "long" else PRICE
    rows = (
        quote(PUB),
        quote(READY),
        quote(HOLD),
        crossed_quote(EXIT_DEADLINE, side, entry, -50, 10 * TICK),
        crossed_quote(EXIT_DEADLINE, side, entry, 100),
        quote(EXIT_DEADLINE + 1),
    )
    tape, account, proposal = fixture(rows), genesis(), declaration(side, "time_exit")
    result = build(tape, account, proposal)
    assert asdict(result) == oracle(tape, account, proposal)
    assert result.exit_execution_outcome == "constructed_exit_receipt"
    assert result.exit_outcome_cursor == 3 and result.exit_outcome_at_ns == EXIT_DEADLINE
    assert result.records[-1].payload.price_nano == (
        rows[3].bid_nano if side == "long" else rows[3].ask_nano
    )
    assert result.terminal_accounting_state.gross_realized_usd_micros == -50 * 625
    assert result.terminal_accounting_state.phase == "FLAT"
    assert len(result.records) == 5 and len(result.quote_audit) == len(rows) == 6
    assert result.record_links[-1].native_prefix.consumed_count == 4
    assert result.terminal_native_prefix.consumed_count == 6


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize("eof", [False, True])
def test_unknown_preserves_original_inventory_and_zero_commitment_liability(side, eof):
    rows = (quote(PUB), quote(READY))
    if not eof:
        rows += (quote(EXIT_DEADLINE + 1), quote(EXIT_DEADLINE + 2, PRICE + 200 * TICK))
    account = genesis(balance=1, entry=0, exit_fee=0, margin=0, buffer=0, loss=0)
    result = build(fixture(rows), account, declaration(side, "time_exit"))
    assert asdict(result) == oracle(fixture(rows), account, declaration(side, "time_exit"))
    state = result.terminal_accounting_state
    assert state.phase == "EXIT_UNKNOWN" and state.position.quantity_contracts == 1
    assert state.pending_exit.status == "UNKNOWN" and state.total_commitments_usd_micros == 0
    assert state.declared_realization_balance_usd_micros == 1
    assert state.complete_declared_equity_usd_micros is None
    assert state.complete_declared_net_return_usd_micros is None
    assert len(result.records) == 5 and result.records[-1].recorded_at_ns == EXIT_DEADLINE
    assert result.terminal_native_prefix.consumed_count == len(rows)
    assert len(state.receipt_content_sha256s) == 1


def test_gap_closes_hold_then_unknown_before_consuming_any_late_cursor(monkeypatch):
    tape = fixture((quote(PUB), quote(READY), quote(EXIT_DEADLINE + 1), quote(EXIT_DEADLINE + 2)))
    assert build(tape).exit_execution_outcome == "constructed_exit_unknown"
    events = []
    consume, close, advance = native.consume_next, native.close_through, admission.advance

    def consumed(*args, **kwargs):
        events.append(("consume", kwargs["expected_cursor"]))
        return consume(*args, **kwargs)

    def closed(*args, **kwargs):
        events.append(("close", kwargs["expected_prefix"].consumed_count, kwargs["through_ns"]))
        return close(*args, **kwargs)

    def advanced(*args, **kwargs):
        record = args[2]
        events.append(("account", type(record.payload).__name__, record.recorded_at_ns))
        return advance(*args, **kwargs)

    monkeypatch.setattr(native, "consume_next", consumed)
    monkeypatch.setattr(native, "close_through", closed)
    monkeypatch.setattr(admission, "advance", advanced)
    result = build(tape)
    assert events.index(("close", 2, HOLD - 1)) < events.index(("account", "ExitRequested", HOLD))
    assert events.index(("account", "ExitRequested", HOLD)) < events.index(
        ("close", 2, EXIT_DEADLINE)
    )
    assert events.index(("close", 2, EXIT_DEADLINE)) < events.index(
        ("account", "ExitUnknown", EXIT_DEADLINE)
    )
    assert events.index(("account", "ExitUnknown", EXIT_DEADLINE)) < events.index(("consume", 2))
    assert (
        events.count(("close", 2, HOLD - 1)) >= 2 and events.count(("close", 2, EXIT_DEADLINE)) >= 2
    )
    assert result.terminal_accounting_state.prefix.complete_through_ns == EXIT_DEADLINE


def test_at_hold_row_is_consumed_after_timer_request_but_not_filled_without_delay(monkeypatch):
    tape = fixture((quote(PUB), quote(READY), quote(HOLD, PRICE + 100 * TICK), quote(EXIT_READY)))
    assert build(tape).exit_outcome_cursor == 3
    events = []
    consume, close, advance = native.consume_next, native.close_through, admission.advance

    def consumed(*args, **kwargs):
        events.append(("consume", kwargs["expected_cursor"]))
        return consume(*args, **kwargs)

    def closed(*args, **kwargs):
        events.append(("close", kwargs["through_ns"]))
        return close(*args, **kwargs)

    def advanced(*args, **kwargs):
        events.append(("account", type(args[2].payload).__name__))
        return advance(*args, **kwargs)

    monkeypatch.setattr(native, "consume_next", consumed)
    monkeypatch.setattr(native, "close_through", closed)
    monkeypatch.setattr(admission, "advance", advanced)
    result = build(tape)
    assert (
        events.index(("close", HOLD - 1))
        < events.index(("account", "ExitRequested"))
        < events.index(("consume", 2))
    )
    assert events.index(("consume", 3)) < events.index(("account", "ExitReceipt"))
    assert result.exit_trigger_reason == "hold_timer" and result.exit_outcome_cursor == 3


def test_late_price_changes_complete_identity_not_prior_unknown_or_hold_visibility():
    one = fixture((quote(PUB), quote(READY), quote(EXIT_DEADLINE + 1)))
    two = fixture((quote(PUB), quote(READY), quote(EXIT_DEADLINE + 1, PRICE + 1000 * TICK)))
    a, b = build(one), build(two)
    assert a.plan_sha256 != b.plan_sha256 and a.fixture_sha256 != b.fixture_sha256
    assert a.records == b.records and a.exit_requested_at_ns == b.exit_requested_at_ns == HOLD
    assert a.exit_execution_outcome == b.exit_execution_outcome == "constructed_exit_unknown"
    for x, y in zip(a.record_links, b.record_links, strict=True):
        assert x.native_prefix.consumed_content_sha256 == y.native_prefix.consumed_content_sha256
        if x.boundary is not None:
            assert x.boundary.through_ns == y.boundary.through_ns
            assert x.boundary.next_received_at_ns == y.boundary.next_received_at_ns


@pytest.mark.parametrize("plan", ["time_exit", "bracket_exit"])
@pytest.mark.parametrize(
    "options,disposition",
    [
        ({"balance": 134}, "declared_budget_insufficient"),
        ({"loss": 9}, "declared_budget_insufficient"),
        ({"margin": None}, "budget_undetermined"),
        ({"loss": 10}, "declared_budget_available"),
        (
            {"balance": 1, "entry": 0, "exit_fee": 0, "margin": 0, "buffer": 0, "loss": 0},
            "declared_budget_available",
        ),
    ],
)
def test_budget_uses_only_original_post_clock_snapshot_and_keeps_denial_without_exit(
    plan, options, disposition
):
    tape, account, proposal = fixture(), genesis(**options), declaration(plan=plan)
    result = build(tape, account, proposal)
    assert asdict(result) == oracle(tape, account, proposal)
    assert result.first_disposition == disposition
    decision = result.budget_decision
    assert decision.snapshot.sequence == decision.proposal.expected_sequence == 1
    assert decision.snapshot.tip_sha256 == result.record_links[0].record_sha256
    assert decision.snapshot.observed_through_ns == decision.snapshot.last_event_at_ns == PUB
    assert decision.snapshot.pending_entry is False and decision.snapshot_age_ns == 0
    if disposition != "declared_budget_available":
        assert result.entry_execution_outcome == "no_pending_entry"
        assert result.exit_execution_outcome == "no_exit" and len(result.records) == 2
        assert (
            result.hold_at_ns is result.exit_requested_at_ns is result.exit_trigger_reason is None
        )
        assert result.entry_outcome_cursor is result.exit_outcome_cursor is None
        assert result.terminal_accounting_state.total_commitments_usd_micros == 0


@pytest.mark.parametrize("side", ["long", "short"])
def test_actual_crossed_gross_and_fees_release_reserves_without_extra_comparator_charge(side):
    entry = PRICE + TICK if side == "long" else PRICE
    rows = (
        quote(PUB),
        quote(READY),
        quote(HOLD),
        crossed_quote(EXIT_READY, side, entry, 6, 3 * TICK),
        crossed_quote(EXIT_READY, side, entry, 100),
    )
    result = build(fixture(rows), proposal=declaration(side, "time_exit"))
    state = result.terminal_accounting_state
    assert state.gross_realized_usd_micros == 6 * 625
    assert state.entry_fees_usd_micros == 10 and state.exit_fees_usd_micros == 20
    assert state.declared_realization_balance_usd_micros == 135 + 6 * 625 - 30
    assert state.complete_declared_net_return_usd_micros == 6 * 625 - 30
    assert state.entry_fee_reserve_usd_micros == state.initial_margin_commitment_usd_micros == 0
    assert state.exit_fee_reserve_usd_micros == state.total_commitments_usd_micros == 0
    assert (
        state.available_balance_usd_micros
        == state.complete_declared_equity_usd_micros
        == state.declared_realization_balance_usd_micros
    )
    assert len(state.receipt_content_sha256s) == 2 and len(set(state.receipt_content_sha256s)) == 2
    assert len(result.records) == 5 and result.exit_outcome_cursor == 3


@pytest.mark.parametrize("contract", ["6EM5", "6EU5", "6EZ5", "6EH6"])
def test_original_supported_contract_is_preserved_through_both_receipts(contract):
    result = build(fixture(contract=contract))
    assert all(
        r.payload.contract == contract for r in result.records if hasattr(r.payload, "contract")
    )
    assert result.terminal_native_prefix.contract == contract


@pytest.mark.parametrize(
    "target", ["expected_fixture_sha256", "expected_genesis_sha256", "expected_declaration_sha256"]
)
@pytest.mark.parametrize(
    "value", [None, True, 7, "", "a" * 63, "A" * 64, "g" * 64, StrSubclass("a" * 64)], ids=safe_id
)
def test_malformed_input_pin_preflight_before_quotes_or_accounting(monkeypatch, target, value):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert build(tape, account, proposal).exit_execution_outcome == "constructed_exit_receipt"
    args[target] = value
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.build_single_roundtrip_plan(tape, account, proposal, **args)


@pytest.mark.parametrize(
    "value", [None, False, 1, "", "b" * 63, "B" * 64, "z" * 64, StrSubclass("b" * 64)], ids=safe_id
)
def test_verifier_malformed_output_pin_refuses_before_any_deep_path(monkeypatch, value):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    positive = build(tape, account, proposal)
    assert (
        driver.verify_single_roundtrip_plan(
            tape, account, proposal, **args, expected_plan_sha256=positive.plan_sha256
        )
        == positive
    )
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.verify_single_roundtrip_plan(
            tape, account, proposal, **args, expected_plan_sha256=value
        )


@pytest.mark.parametrize(
    "target",
    [
        "expected_fixture_sha256",
        "expected_genesis_sha256",
        "expected_declaration_sha256",
        "expected_plan_sha256",
    ],
)
def test_otherwise_valid_wrong_original_pin_is_never_adopted(target):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    args["expected_plan_sha256"] = build(tape, account, proposal).plan_sha256
    args[target] = "0" * 64
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.verify_single_roundtrip_plan(tape, account, proposal, **args)


@pytest.mark.parametrize(
    "field,value",
    [
        ("declaration_id", "ordinary"),
        ("declaration_id", "synthetic-"),
        ("declaration_id", "synthetic-" + "x" * 55),
        ("declaration_id", "synthetic-é"),
        ("declaration_id", StrSubclass("synthetic-roundtrip")),
        ("publication_id", "other"),
        ("publication_id", "bad/id"),
        ("admission_id", ""),
        ("admission_id", StrSubclass("entry-1")),
        ("side", "LONG"),
        ("side", True),
        ("side", StrSubclass("long")),
        ("exit_plan", "hold_exit"),
        ("exit_plan", True),
        ("exit_plan", StrSubclass("time_exit")),
    ],
    ids=safe_id,
)
def test_declaration_closed_fields_refuse_before_prices(monkeypatch, field, value):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert build(tape, account, proposal).plan_sha256
    proposal = changed(proposal, **{field: value})
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.build_single_roundtrip_plan(tape, account, proposal, **args)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_session", "real-20261009"),
        ("source_session", "synthetic-"),
        ("source_session", StrSubclass("synthetic-roundtrip-tape")),
        ("contract", "6EM6"),
        ("contract", "EURUSD"),
        ("contract", StrSubclass("6EM5")),
        ("source_sha256", "A" * 64),
        ("start_ns", True),
        ("end_ns", IntSubclass(END)),
        ("start_ns", -1),
        ("end_ns", 2**63),
        ("quotes", []),
        ("publications", []),
    ],
    ids=safe_id,
)
def test_fixture_scalar_metadata_and_tuple_types_precede_price_access(monkeypatch, field, value):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert build(tape, account, proposal).plan_sha256
    tape = changed(tape, **{field: value})
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.build_single_roundtrip_plan(tape, account, proposal, **args)


@pytest.mark.parametrize(
    "field,value",
    [
        ("publication_id", True),
        ("publication_id", StrSubclass("pub-1")),
        ("publication_id", "bad/id"),
        ("published_cursor", True),
        ("published_cursor", IntSubclass(0)),
        ("published_cursor", -1),
        ("published_cursor", 7),
        ("received_at_ns", True),
        ("received_at_ns", IntSubclass(PUB)),
        ("received_at_ns", START - 1),
        ("received_at_ns", END),
    ],
    ids=safe_id,
)
def test_publication_scalar_preflight_with_independently_matching_malformed_pin(
    monkeypatch, field, value
):
    tape, account, proposal = fixture(), genesis(), declaration()
    assert build(tape, account, proposal).publication.published_cursor == 0
    tape = changed(tape, publications=(changed(tape.publications[0], **{field: value}),))
    args = arguments(tape, account, proposal)
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.build_single_roundtrip_plan(tape, account, proposal, **args)


def test_publication_exact_type_precedes_price_access(monkeypatch):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert build(tape, account, proposal).plan_sha256
    tape = changed(tape, publications=(subclass_copy(tape.publications[0]),))
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.build_single_roundtrip_plan(tape, account, proposal, **args)


@pytest.mark.parametrize("kind", ["scenario", "initialization", "seed", "economics", "limits"])
def test_genesis_preflight_does_not_access_prices_or_create_account_events(monkeypatch, kind):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert build(tape, account, proposal).budget_decision.snapshot_age_ns == 0
    if kind == "scenario":
        account = changed(account, scenario_id="real-account")
    elif kind == "initialization":
        account = changed(account, seed=replace(account.seed, initialized_at_ns=START + 1))
    elif kind == "seed":
        account = changed(account, seed=changed(account.seed, initial_balance_usd_micros=True))
    elif kind == "economics":
        account = changed(
            account, economics=changed(account.economics, entry_fee_usd_micros_per_contract=True)
        )
    else:
        account = changed(account, limits=changed(account.limits, max_snapshot_age_ns=True))
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.build_single_roundtrip_plan(tape, account, proposal, **args)


@pytest.mark.parametrize("where", ["fixture", "genesis", "declaration"])
@pytest.mark.parametrize("kind", ["subclass", "missing", "mapping"])
def test_exact_top_types_and_field_completeness_are_consuming_guards(monkeypatch, where, kind):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert build(tape, account, proposal).plan_sha256
    values = {"fixture": tape, "genesis": account, "declaration": proposal}
    value = values[where]
    if kind == "subclass":
        bad = subclass_copy(value)
    elif kind == "mapping":
        bad = asdict(value)
    else:
        bad = changed(value)
        object.__delattr__(bad, fields(value)[0].name)
    values[where] = bad
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.build_single_roundtrip_plan(
            values["fixture"], values["genesis"], values["declaration"], **args
        )


@pytest.mark.parametrize(
    "kind",
    ["129_quotes", "zero_quotes", "zero_publications", "second_publication", "tuple_subclass"],
)
def test_complete_caps_are_early_and_no_subset_is_returned(monkeypatch, kind):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert len(build(tape, account, proposal).quote_audit) == 7
    if kind == "129_quotes":
        tape = changed(tape, quotes=(quote(PUB),) * 129)
    elif kind == "zero_quotes":
        tape = changed(tape, quotes=())
    elif kind == "zero_publications":
        tape = changed(tape, publications=())
    elif kind == "second_publication":
        tape = changed(tape, publications=tape.publications * 2)
    else:
        tape = changed(tape, quotes=TupleSubclass(tape.quotes))
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.build_single_roundtrip_plan(tape, account, proposal, **args)


@pytest.mark.parametrize(
    "field,value",
    [
        ("received_at_ns", True),
        ("received_at_ns", READY + 0.5),
        ("received_at_ns", IntSubclass(READY)),
        ("received_at_ns", START - 1),
        ("received_at_ns", END),
        ("bid_nano", 0),
        ("bid_nano", True),
        ("bid_nano", PRICE + 1),
        ("ask_nano", PRICE),
        ("ask_nano", PRICE - TICK),
        ("ask_nano", PRICE + TICK + 1),
        ("ask_nano", IntSubclass(PRICE + TICK)),
    ],
    ids=safe_id,
)
def test_quote_schema_refuses_with_matching_independent_complete_input_pin(field, value):
    tape, account, proposal = fixture(), genesis(), declaration()
    assert build(tape, account, proposal).plan_sha256
    rows = list(tape.quotes)
    rows[2] = changed(rows[2], **{field: value})
    tape = changed(tape, quotes=tuple(rows))
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.build_single_roundtrip_plan(
            tape, account, proposal, **arguments(tape, account, proposal)
        )


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_strict_original_end_buffer_has_valid_quote_and_matching_pin_control(delta):
    tape = fixture((quote(PUB), quote(READY)), end=PUB + 18_000_000_000 + delta)
    account, proposal = genesis(), declaration(plan="time_exit")
    if delta == 1:
        result = build(tape, account, proposal)
        assert (
            result.exit_outcome_at_ns == EXIT_DEADLINE
            and result.exit_execution_outcome == "constructed_exit_unknown"
        )
    else:
        with pytest.raises(driver.SingleRoundtripDriverError):
            driver.build_single_roundtrip_plan(
                tape, account, proposal, **arguments(tape, account, proposal)
            )


@pytest.mark.parametrize("overflow", ["readiness", "deadline"])
def test_matching_near_integer_limit_metadata_refuses_derived_overflow_before_prices(
    monkeypatch, overflow
):
    maximum = 2**63 - 1
    start = maximum - 20_000_000_000
    account = replace(genesis(), seed=replace(genesis().seed, initialized_at_ns=start))
    proposal = declaration(plan="time_exit")
    good_pub = maximum - 19_000_000_000
    positive = native.NativeFixture(
        "synthetic-near-limit",
        "6EM5",
        SOURCE,
        start,
        maximum,
        (quote(good_pub), quote(good_pub + 100_000_000)),
        (native.NativePublication("pub-1", 0, good_pub),),
    )
    valid = build(positive, account, proposal)
    assert asdict(valid) == oracle(positive, account, proposal)
    assert valid.exit_execution_outcome == "constructed_exit_unknown"
    offset = 100_000_000 if overflow == "readiness" else 1_100_000_000
    bad_pub = maximum - offset + 1
    tape = native.NativeFixture(
        "synthetic-near-limit",
        "6EM5",
        SOURCE,
        start,
        maximum,
        (quote(bad_pub),),
        (native.NativePublication("pub-1", 0, bad_pub),),
    )
    args = arguments(tape, account, proposal)
    assert native.fixture_sha256(tape) == args["expected_fixture_sha256"]
    assert admission.genesis_sha256(account) == args["expected_genesis_sha256"]
    assert bad_pub + offset == maximum + 1
    # Overflow cannot coexist with the valid18-second end guard: this proves
    # composite early refusal of valid native metadata, not one isolated guard.
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.build_single_roundtrip_plan(tape, account, proposal, **args)


@pytest.mark.parametrize("kind", ["omit", "reorder", "future_price", "future_time", "publication"])
def test_original_full_pins_prevent_omitted_reordered_changed_inputs(kind):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    original = build(tape, account, proposal)
    if kind == "omit":
        tape = changed(tape, quotes=tape.quotes[:-1])
    elif kind == "reorder":
        tape = changed(tape, quotes=(tape.quotes[1], tape.quotes[0], *tape.quotes[2:]))
    elif kind == "future_price":
        tape = changed(
            tape, quotes=(*tape.quotes[:-1], quote(EXIT_DEADLINE + 1, PRICE + 500 * TICK))
        )
    elif kind == "future_time":
        tape = changed(tape, quotes=(*tape.quotes[:-1], quote(EXIT_DEADLINE + 2)))
    else:
        tape = changed(tape, publications=(changed(tape.publications[0], published_cursor=1),))
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.verify_single_roundtrip_plan(
            tape, account, proposal, **args, expected_plan_sha256=original.plan_sha256
        )


def test_first_publication_cursor_refuses_with_matching_full_pin_and_equal_time_positive_control():
    tape, account, proposal = fixture(), genesis(), declaration()
    assert build(tape, account, proposal).publication.prefix.consumed_count == 1
    tape = changed(tape, publications=(changed(tape.publications[0], published_cursor=1),))
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.build_single_roundtrip_plan(
            tape, account, proposal, **arguments(tape, account, proposal)
        )


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize("plan", ["time_exit", "bracket_exit"])
def test_nonzero_original_publication_cursor_follows_complete_prefix_before_equal_suffix(
    side, plan
):
    entry = PRICE + TICK if side == "long" else PRICE
    rows = (
        quote(START),
        quote(PUB - 1),
        quote(PUB),
        quote(PUB, PRICE + 30 * TICK),
        quote(READY),
        quote(HOLD),
        crossed_quote(EXIT_READY, side, entry, 6, 3 * TICK),
        quote(EXIT_DEADLINE + 1),
    )
    tape, account, proposal = fixture(rows), genesis(), declaration(side, plan)
    result = build(tape, account, proposal)
    expected = oracle(tape, account, proposal)
    assert asdict(result) == expected
    assert result.publication.published_cursor == 2
    assert result.publication.prefix.consumed_count == 3
    assert result.publication.prefix.last_cursor == 2
    assert all(link.native_prefix.consumed_count == 3 for link in result.record_links[:2])
    assert result.entry_outcome_cursor == 4 and result.exit_outcome_cursor == 6
    assert len(result.quote_audit) == len(rows) == 8
    assert (
        driver.verify_single_roundtrip_plan(
            tape,
            account,
            proposal,
            **arguments(tape, account, proposal),
            expected_plan_sha256=expected["plan_sha256"],
        )
        == result
    )


@pytest.mark.parametrize("plan", ["time_exit", "bracket_exit"])
def test_full_128_quote_five_record_unknown_build_and_rebuild_fit_default_byte_and_work_bounds(
    monkeypatch, plan
):
    rows = (quote(PUB),) + (quote(READY),) * 126 + (quote(EXIT_DEADLINE + 1),)
    tape, account, proposal = fixture(rows), genesis(), declaration(plan=plan)
    args = arguments(tape, account, proposal)
    expected = oracle(tape, account, proposal)
    calls = []
    traversals = 0
    consume, quote_fields = native.consume_next, native._quote_fields

    def consumed(*args, **kwargs):
        value = consume(*args, **kwargs)
        calls.append(value.native_cursor)
        return value

    def inspected(*args, **kwargs):
        nonlocal traversals
        traversals += 1
        return quote_fields(*args, **kwargs)

    monkeypatch.setattr(native, "consume_next", consumed)
    monkeypatch.setattr(native, "_quote_fields", inspected)
    began = time.perf_counter()
    result = driver.build_single_roundtrip_plan(tape, account, proposal, **args)
    assert calls == list(range(128)) and 128 <= traversals <= 10 * 128**2
    assert asdict(result) == expected and len(result.records) == 5
    body = asdict(result)
    del body["plan_sha256"]
    body_size = len(canonical(body))
    assert body_size <= 65536
    print(f"constructed128 {plan}: complete canonical body {body_size} bytes <=65536")
    assert result.exit_execution_outcome == "constructed_exit_unknown"
    assert result.record_links[3].native_prefix.consumed_count == 127
    assert result.record_links[4].native_prefix.consumed_count == 127
    calls.clear()
    traversals = 0
    assert (
        driver.verify_single_roundtrip_plan(
            tape, account, proposal, **args, expected_plan_sha256=expected["plan_sha256"]
        )
        == result
    )
    assert calls == list(range(128)) and 128 <= traversals <= 10 * 128**2
    assert time.perf_counter() - began < 30  # Generous constructed bound, not trading latency.


def test_defensive_byte_cap_exact_size_and_size_minus_one_keep_fixed_declaration(monkeypatch):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    result = build(tape, account, proposal)
    body = asdict(result)
    del body["plan_sha256"]
    length = len(canonical(body))
    assert (
        len(canonical(declaration_body(proposal, fixture_pin(tape), genesis_pin(account))))
        < length - 1
    )
    monkeypatch.setattr(driver, "MAX_RESULT_BYTES", length)
    assert (
        driver.declaration_sha256(
            proposal, fixture_sha256=fixture_pin(tape), genesis_sha256=genesis_pin(account)
        )
        == args["expected_declaration_sha256"]
    )
    assert driver.build_single_roundtrip_plan(tape, account, proposal, **args) == result
    monkeypatch.setattr(driver, "MAX_RESULT_BYTES", length - 1)
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.build_single_roundtrip_plan(tape, account, proposal, **args)


@pytest.mark.parametrize("cap,value", [("MAX_DRIVER_QUOTES", 6), ("MAX_DRIVER_PUBLICATIONS", 0)])
def test_lowered_defensive_input_cap_precedes_price_and_keeps_protocol_identity(
    monkeypatch, cap, value
):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert build(tape, account, proposal).plan_sha256
    monkeypatch.setattr(driver, cap, value)
    assert (
        driver.declaration_sha256(
            proposal, fixture_sha256=fixture_pin(tape), genesis_sha256=genesis_pin(account)
        )
        == args["expected_declaration_sha256"]
    )
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.build_single_roundtrip_plan(tape, account, proposal, **args)


@pytest.mark.parametrize("cap", [2, 3, 4])
def test_lowered_accounting_cap_never_returns_partial_plan_or_alters_seed(monkeypatch, cap):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert len(build(tape, account, proposal).records) == 5
    before = canonical([asdict(tape), asdict(account), asdict(proposal)])
    monkeypatch.setattr(driver, "MAX_ACCOUNTING_RECORDS", cap)
    assert (
        driver.declaration_sha256(
            proposal, fixture_sha256=fixture_pin(tape), genesis_sha256=genesis_pin(account)
        )
        == args["expected_declaration_sha256"]
    )
    with pytest.raises(driver.SingleRoundtripDriverError):
        driver.build_single_roundtrip_plan(tape, account, proposal, **args)
    assert canonical([asdict(tape), asdict(account), asdict(proposal)]) == before
    denied = build(tape, genesis(balance=134), proposal)
    assert len(denied.records) == 2 and denied.exit_execution_outcome == "no_exit"


def test_repeat_calls_are_immutable_pure_not_persisted_exactly_once():
    tape, account, proposal = fixture(), genesis(), declaration()
    before = canonical([asdict(tape), asdict(account), asdict(proposal)])
    first, second = build(tape, account, proposal), build(tape, account, proposal)
    assert first == second and first is not second
    assert canonical([asdict(tape), asdict(account), asdict(proposal)]) == before
    for value in (
        proposal,
        first,
        first.quote_audit[0],
        first.record_links[0],
        first.publication,
        first.terminal_native_prefix,
        first.terminal_accounting_state,
    ):
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)
    assert first.authority_flags == assessment.AUTHORITY_FLAGS
    assert all(flag is False for _, flag in first.authority_flags)
    assert [type(r.payload).__name__ for r in first.records] == [
        "ClockAdvanced",
        "AdmissionRequested",
        "EntryReceipt",
        "ExitRequested",
        "ExitReceipt",
    ]


def test_builder_and_full_rebuild_have_no_io_process_network_or_clock_calls(monkeypatch):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    expected = build(tape, account, proposal)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)
    monkeypatch.setattr(time, "perf_counter", forbidden)
    assert driver.build_single_roundtrip_plan(tape, account, proposal, **args) == expected
    assert (
        driver.verify_single_roundtrip_plan(
            tape, account, proposal, **args, expected_plan_sha256=expected.plan_sha256
        )
        == expected
    )


def test_source_uses_only_standard_library_and_allowed_held_primitives():
    tree = ast.parse(inspect.getsource(driver))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "ai_trader.research":
                assert all(
                    alias.name
                    in {
                        "six_e_native_prefix",
                        "six_e_declared_admission",
                        "six_e_entry_budget",
                        "six_e_native_admission_assessment",
                        "six_e_single_entry_driver",
                    }
                    for alias in node.names
                )
            else:
                imports.append(node.module)
    assert set(imports) <= {"__future__", "dataclasses", "hashlib", "json"}
    assert not any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id in {"open", "eval", "exec", "compile", "__import__"}
        for n in ast.walk(tree)
    )
