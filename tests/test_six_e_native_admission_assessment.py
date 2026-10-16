"""Invented paired contexts; assessments are never causal-history or trade authority."""

import ast
import builtins
import hashlib
import inspect
import json
import socket
import sqlite3
import subprocess
import time
from dataclasses import FrozenInstanceError, asdict, fields
from pathlib import Path

import pytest

from ai_trader.research import six_e_declared_admission as admission
from ai_trader.research import six_e_entry_budget as budget
from ai_trader.research import six_e_native_admission_assessment as assessment
from ai_trader.research import six_e_native_prefix as native

SECOND = 1_000_000_000
START = 10 * SECOND
END = 100 * SECOND
TICK = 50_000
PRICE = 1_000_000_000
MAX_INT = 2**63 - 1
VERSION = "six_e_native_admission_assessment_v1"
BUDGET_STATUS = "constructed_native_budget_assessment_not_authenticated"
DEADLINE_STATUS = "constructed_native_deadline_assessment_not_authenticated"
EXTRA_FLAGS = (
    "native_accounting_history_verified",
    "original_strategy_selection_verified",
    "timer_elapsed_verified",
    "timeout_authorized",
    "accounting_transition_authorized",
    "cross_call_continuity_authenticated",
    "absence_of_eligible_fill_verified",
    "complete_decision_quote_audit_verified",
)


def changed(value, **changes):
    """Copy/poison frozen fields to reach consuming guards, not constructors."""
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(result, field.name, getattr(value, field.name))
    for name, replacement in changes.items():
        object.__setattr__(result, name, replacement)
    return result


def canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def declared(balance=135, *, entry=10, exit_fee=20, margin=True, buffer=5, age=SECOND, loss=None):
    economics = budget.DeclaredEconomics(
        "USD",
        125,
        entry,
        exit_fee,
        budget.economics.DeclaredMargin(100, 80) if margin is True else margin,
    )
    return admission.DeclaredAdmissionGenesis(
        "synthetic-account-case",
        budget.EconomicSeed(balance, START),
        economics,
        budget.DeclaredBudgetLimits(buffer, age, loss),
    )


class Tape:
    """Tiny complete constructed tape, never a cached state submitted to the bridge."""

    def __init__(self, genesis=None):
        self.genesis = declared() if genesis is None else genesis
        self.pin = admission.genesis_sha256(self.genesis)
        self.records = ()
        self.prefix = admission.DeclaredPrefix(0, self.pin, self.genesis.seed.initialized_at_ns)

    def state(self):
        return admission.reconstruct(
            self.genesis,
            self.records,
            expected_genesis_sha256=self.pin,
            expected_terminal=self.prefix,
        )

    def append(self, payload, at=None):
        at = self.prefix.complete_through_ns if at is None else at
        record = admission.DeclaredRecord(
            f"event-{len(self.records) + 1}", self.prefix, at, at, payload
        )
        transition = admission.advance(
            self.genesis,
            self.records,
            record,
            expected_genesis_sha256=self.pin,
            expected_terminal=self.prefix,
        )
        self.records = transition.records
        self.prefix = transition.state.prefix
        return self


def pending_entry(genesis=None, contract="6EU5"):
    return Tape(genesis).append(admission.AdmissionRequested("entry-1", contract, "long", 1))


def open_position(genesis=None, contract="6EU5"):
    return pending_entry(genesis, contract).append(
        admission.EntryReceipt(
            "entry-1", "entry-receipt", contract, "long", 1, PRICE, START + admission.DELAY_NS
        ),
        START + admission.DELAY_NS,
    )


def pending_exit(genesis=None, contract="6EU5"):
    return open_position(genesis, contract).append(admission.ExitRequested("entry-1", "exit-1"))


def unknown_exit(genesis=None, contract="6EU5"):
    tape = pending_exit(genesis, contract)
    return tape.append(admission.ExitUnknown("exit-1"), tape.state().pending_exit.deadline_ns)


def linear_clock_tape(count, genesis=None):
    """Independent record-head oracle, not quadratic advance/reconstruct setup."""
    tape = Tape(genesis)
    records = []
    prefix = tape.prefix
    for index in range(count):
        record = admission.DeclaredRecord(
            f"clock-{index}", prefix, START, START, admission.ClockAdvanced()
        )
        identity = sha(
            {
                "version": "six_e_declared_admission_v1",
                "kind": "ClockAdvanced",
                "record": asdict(record),
            }
        )
        prefix = admission.DeclaredPrefix(index + 1, identity, START)
        records.append(record)
    tape.records, tape.prefix = tuple(records), prefix
    return tape


def publication_fixture(at=START + SECOND, *, contract="6EU5"):
    return native.NativeFixture(
        "synthetic-native-case",
        contract,
        "a" * 64,
        START,
        END,
        (
            native.NativeQuote(at, PRICE, PRICE + TICK),
            native.NativeQuote(at, PRICE - 5 * TICK, PRICE - 4 * TICK),
            native.NativeQuote(at + SECOND, PRICE + TICK, PRICE + 2 * TICK),
        ),
        (native.NativePublication("pub-1", 0, at),),
    )


def fixture_body(fixture):
    metadata = {
        "version": "six_e_native_prefix_v1",
        "source_session": fixture.source_session,
        "contract": fixture.contract,
        "source_sha256": fixture.source_sha256,
        "start_ns": fixture.start_ns,
        "end_ns": fixture.end_ns,
        "tick_nano": TICK,
    }
    return {
        "version": "six_e_native_prefix_v1",
        "kind": "complete_constructed_native_fixture",
        "metadata": metadata,
        "quote_count": len(fixture.quotes),
        "publication_count": len(fixture.publications),
        "quotes": [[q.received_at_ns, q.bid_nano, q.ask_nano] for q in fixture.quotes],
        "publications": [asdict(publication) for publication in fixture.publications],
    }


def native_prefix(fixture, count):
    """Derive an independently asserted full-prefix digest in one linear pass."""
    body = fixture_body(fixture)
    full_pin = sha(body)
    head = sha(
        {
            "version": "six_e_native_prefix_v1",
            "kind": "consumed_metadata_seed",
            "metadata": body["metadata"],
        }
    )
    last_time = group = None
    for cursor, quote in enumerate(fixture.quotes[:count]):
        if quote.received_at_ns != last_time:
            group = cursor
        last_time = quote.received_at_ns
        head = sha(
            {
                "version": "six_e_native_prefix_v1",
                "kind": "consumed_quote",
                "previous_sha256": head,
                "native_cursor": cursor,
                "quote": [quote.received_at_ns, quote.bid_nano, quote.ask_nano],
            }
        )
    return native.NativePrefix(
        full_pin,
        fixture.source_session,
        fixture.contract,
        fixture.source_sha256,
        fixture.start_ns,
        fixture.end_ns,
        len(fixture.quotes),
        len(fixture.publications),
        count,
        count - 1 if count else None,
        last_time,
        group,
        head,
    )


def context(tape=None, fixture=None, count=1):
    tape = Tape() if tape is None else tape
    fixture = publication_fixture() if fixture is None else fixture
    prefix = native_prefix(fixture, count)
    return {
        "fixture": fixture,
        "genesis": tape.genesis,
        "records": tape.records,
        "expected_fixture_sha256": prefix.fixture_sha256,
        "expected_native_prefix": prefix,
        "expected_genesis_sha256": tape.pin,
        "expected_accounting_prefix": tape.prefix,
    }


def pending_context(kind="entry", *, tape=None, eof=False):
    tape = (pending_entry() if kind == "entry" else pending_exit()) if tape is None else tape
    state = tape.state()
    liability = state.pending_entry if kind == "entry" else state.pending_exit
    ready, deadline = liability.ready_at_ns, liability.deadline_ns
    quotes = (
        native.NativeQuote(ready, PRICE, PRICE + TICK),
        native.NativeQuote(deadline, PRICE + TICK, PRICE + 2 * TICK),
        native.NativeQuote(deadline, PRICE - TICK, PRICE),
    )
    if not eof:
        quotes += (native.NativeQuote(deadline + 1, PRICE, PRICE + 2 * TICK),)
    fixture = native.NativeFixture(
        "synthetic-deadline-case", "6EU5", "b" * 64, START, END, quotes, ()
    )
    result = context(tape, fixture, count=3)
    result["expected_deadline_ns"] = deadline
    return result


def run_budget(ctx):
    return assessment.assess_publication_budget(**ctx, publication_id="pub-1")


def run_deadline(ctx):
    return assessment.assess_pending_deadline_boundary(**ctx)


def oracle_flags():
    return tuple(
        sorted(
            (
                dict(native.AUTHORITY_FLAGS)
                | dict(admission.AUTHORITY_FLAGS)
                | dict.fromkeys(EXTRA_FLAGS, False)
            ).items()
        )
    )


def accounting_state(ctx):
    return admission.reconstruct(
        ctx["genesis"],
        ctx["records"],
        expected_genesis_sha256=ctx["expected_genesis_sha256"],
        expected_terminal=ctx["expected_accounting_prefix"],
    )


def oracle_budget_body(ctx):
    state = accounting_state(ctx)
    publication = native.publication_witness(
        ctx["fixture"],
        expected_fixture_sha256=ctx["expected_fixture_sha256"],
        expected_prefix=ctx["expected_native_prefix"],
        publication_id="pub-1",
    )
    snapshot = budget.DeclaredCapitalSnapshot(
        ctx["genesis"].seed,
        state.declared_realization_balance_usd_micros,
        state.prefix.sequence,
        state.prefix.head_sha256,
        state.last_event_at_ns,
        state.prefix.complete_through_ns,
        1 if state.position is not None else 0,
        1 if state.pending_exit is not None else 0,
        state.pending_exit.status if state.pending_exit is not None else None,
        state.pending_entry is not None,
    )
    proposal = budget.EntryProposal(
        publication.received_at_ns,
        state.prefix.sequence,
        state.prefix.head_sha256,
        ctx["fixture"].contract,
        1,
    )
    decision = budget.assess_entry_budget(
        snapshot, proposal, ctx["genesis"].economics, ctx["genesis"].limits
    )
    return {
        "version": VERSION,
        "status": BUDGET_STATUS,
        "fixture_sha256": ctx["expected_fixture_sha256"],
        "genesis_sha256": ctx["expected_genesis_sha256"],
        "native_prefix": asdict(ctx["expected_native_prefix"]),
        "accounting_state": asdict(state),
        "publication": asdict(publication),
        "budget_decision": asdict(decision),
        "authority_flags": oracle_flags(),
    }


def oracle_deadline_body(ctx):
    state = accounting_state(ctx)
    if state.pending_entry is not None:
        kind, liability, identity = "entry", state.pending_entry, state.pending_entry.admission_id
        contract = liability.contract
    else:
        kind, liability, identity = "exit", state.pending_exit, state.pending_exit.request_id
        contract = state.position.contract
    boundary = native.close_through(
        ctx["fixture"],
        expected_fixture_sha256=ctx["expected_fixture_sha256"],
        expected_prefix=ctx["expected_native_prefix"],
        through_ns=liability.deadline_ns,
    )
    return {
        "version": VERSION,
        "status": DEADLINE_STATUS,
        "fixture_sha256": ctx["expected_fixture_sha256"],
        "genesis_sha256": ctx["expected_genesis_sha256"],
        "native_prefix": asdict(ctx["expected_native_prefix"]),
        "accounting_state": asdict(state),
        "liability_kind": kind,
        "liability_id": identity,
        "contract": contract,
        "ready_at_ns": liability.ready_at_ns,
        "deadline_ns": liability.deadline_ns,
        "boundary": asdict(boundary),
        "authority_flags": oracle_flags(),
    }


def assert_link(result, expected_body):
    body = asdict(result)
    actual_pin = body.pop("link_sha256")
    assert set(body) == set(expected_body)
    assert canonical(body) == canonical(expected_body)
    assert actual_pin == sha(expected_body)
    assert result.authority_flags == oracle_flags()
    assert all(type(flag) is bool and flag is False for _, flag in result.authority_flags)


def forbid_deep_paths(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Preflight must refuse before native or receipt reconstruction")

    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "reconstruct", forbidden)


class IntSubclass(int):
    pass


class StringSubclass(str):
    pass


class TupleSubclass(tuple):
    def __len__(self):
        raise AssertionError("Tuple subclasses must refuse before length inspection")


def safe_id(value):
    return (
        repr(value) if type(value) in (str, int, float, bool, type(None)) else type(value).__name__
    )


def test_closed_protocol_and_budget_matches_independent_full_control():
    assert assessment.VERSION == VERSION
    assert assessment.BUDGET_STATUS == BUDGET_STATUS
    assert assessment.DEADLINE_STATUS == DEADLINE_STATUS
    assert assessment.MAX_ACCOUNTING_RECORDS == 128
    assert assessment.MAX_LINK_BYTES == 256 * 1024
    assert assessment.AUTHORITY_FLAGS == oracle_flags()
    ctx = context()
    result = run_budget(ctx)
    assert type(result) is assessment.NativeBudgetAssessment
    assert_link(result, oracle_budget_body(ctx))
    assert result.budget_decision.disposition == "declared_budget_available"
    assert result.budget_decision.declared_budget_condition_met is True
    assert result.budget_decision.snapshot.observed_through_ns == START
    assert result.budget_decision.snapshot_age_ns == SECOND
    assert result.publication.boundary_state == "OPEN"
    assert result.accounting_state.phase == "FLAT"


@pytest.mark.parametrize("kind", ["entry", "exit"])
@pytest.mark.parametrize("eof", [False, True])
def test_deadline_assessment_matches_original_liability_and_independent_full_link(kind, eof):
    ctx = pending_context(kind, eof=eof)
    result = run_deadline(ctx)
    assert type(result) is assessment.NativeDeadlineAssessment
    assert_link(result, oracle_deadline_body(ctx))
    assert result.liability_kind == kind
    assert result.liability_id == ("entry-1" if kind == "entry" else "exit-1")
    assert result.deadline_ns == ctx["expected_deadline_ns"]
    assert result.boundary.closure_kind == ("complete_eof" if eof else "next_timestamp")
    assert result.accounting_state.phase == ("ENTRY_PENDING" if kind == "entry" else "EXIT_PENDING")
    assert result.accounting_state.complete_declared_equity_usd_micros is None
    assert result.accounting_state.complete_declared_net_return_usd_micros is None
    assert result.authority_flags == oracle_flags()


@pytest.mark.parametrize("balance,available", [(134, False), (135, True), (136, True)])
def test_declared_cash_equality_is_preserved_not_debited(balance, available):
    tape = Tape(declared(balance))
    ctx = context(tape)
    result = run_budget(ctx)
    assert_link(result, oracle_budget_body(ctx))
    assert result.budget_decision.declared_budget_condition_met is available
    assert result.budget_decision.declared_requirement_usd_micros == 135
    assert result.accounting_state.declared_realization_balance_usd_micros == balance
    assert result.accounting_state.entry_fees_usd_micros == 0
    assert result.accounting_state.total_commitments_usd_micros == 0
    assert tape.records == ()


@pytest.mark.parametrize(
    "age,disposition",
    [
        (SECOND - 1, "budget_undetermined"),
        (SECOND, "declared_budget_available"),
        (SECOND + 1, "declared_budget_available"),
    ],
)
def test_snapshot_age_ceiling_keeps_equality_and_never_advances_accounting_frontier(
    age, disposition
):
    ctx = context(Tape(declared(age=age)))
    result = run_budget(ctx)
    assert_link(result, oracle_budget_body(ctx))
    assert result.budget_decision.disposition == disposition
    assert result.budget_decision.snapshot.observed_through_ns == START
    assert result.budget_decision.snapshot_age_ns == SECOND


@pytest.mark.parametrize("frontier", [START + SECOND, START + SECOND + 1])
def test_exact_publication_frontier_is_allowed_but_future_frontier_refuses(frontier):
    tape = Tape().append(admission.ClockAdvanced(), frontier)
    ctx = context(tape)
    if frontier == START + SECOND:
        result = run_budget(ctx)
        assert result.budget_decision.snapshot_age_ns == 0
        assert_link(result, oracle_budget_body(ctx))
    else:
        with pytest.raises(assessment.NativeAdmissionAssessmentError):
            run_budget(ctx)


@pytest.mark.parametrize("loss,available", [(9, False), (10, True), (11, True)])
def test_proposed_entry_fee_loss_ceiling_preserves_exact_equality(loss, available):
    ctx = context(Tape(declared(loss=loss)))
    result = run_budget(ctx)
    assert_link(result, oracle_budget_body(ctx))
    assert result.budget_decision.hypothetical_loss_after_entry_fee_usd_micros == 10
    assert result.budget_decision.declared_budget_condition_met is available
    assert result.accounting_state.entry_fees_usd_micros == 0


def test_missing_margin_is_undetermined_not_declared_zero():
    missing = context(Tape(declared(margin=None)))
    missing_result = run_budget(missing)
    assert_link(missing_result, oracle_budget_body(missing))
    assert missing_result.budget_decision.disposition == "budget_undetermined"
    assert missing_result.budget_decision.declared_requirement_usd_micros is None
    zero = context(
        Tape(
            declared(
                1,
                entry=0,
                exit_fee=0,
                margin=budget.economics.DeclaredMargin(0, 0),
                buffer=0,
                loss=0,
            )
        )
    )
    zero_result = run_budget(zero)
    assert_link(zero_result, oracle_budget_body(zero))
    assert zero_result.budget_decision.disposition == "declared_budget_available"
    assert zero_result.budget_decision.declared_requirement_usd_micros == 0


@pytest.mark.parametrize("phase", ["entry", "open", "exit", "unknown"])
@pytest.mark.parametrize("zero", [False, True])
def test_typed_liabilities_block_budget_and_preserve_null_equity_even_at_zero_commitments(
    phase, zero
):
    genesis = (
        declared(
            1, entry=0, exit_fee=0, margin=budget.economics.DeclaredMargin(0, 0), buffer=0, loss=0
        )
        if zero
        else declared()
    )
    constructors = {
        "entry": pending_entry,
        "open": open_position,
        "exit": pending_exit,
        "unknown": unknown_exit,
    }
    tape = constructors[phase](genesis)
    publication_at = max(START + SECOND, tape.prefix.complete_through_ns)
    ctx = context(tape, publication_fixture(publication_at))
    result = run_budget(ctx)
    assert_link(result, oracle_budget_body(ctx))
    assert result.budget_decision.disposition == "entry_blocked_by_liability"
    assert result.accounting_state.complete_declared_equity_usd_micros is None
    assert result.accounting_state.complete_declared_net_return_usd_micros is None
    assert result.accounting_state == tape.state()
    if zero:
        assert result.accounting_state.total_commitments_usd_micros == 0


def test_budget_keeps_old_supported_contract_liability_when_current_fixture_contract_changes():
    tape = unknown_exit()
    at = tape.prefix.complete_through_ns
    ctx = context(tape, publication_fixture(at, contract="6EZ5"))
    result = run_budget(ctx)
    assert_link(result, oracle_budget_body(ctx))
    assert result.budget_decision.proposal.contract == "6EZ5"
    assert result.accounting_state.position.contract == "6EU5"
    assert result.accounting_state.pending_exit.status == "UNKNOWN"
    assert result.budget_decision.disposition == "entry_blocked_by_liability"


def test_realized_loss_negative_cash_and_both_fees_are_retained_without_extra_tick():
    tape = pending_exit()
    at = tape.state().pending_exit.ready_at_ns
    tape.append(admission.ExitReceipt("exit-1", "exit-receipt", "6EU5", 1, PRICE - TICK, at), at)
    ctx = context(tape)
    result = run_budget(ctx)
    assert_link(result, oracle_budget_body(ctx))
    state = result.accounting_state
    assert (
        state.gross_realized_usd_micros,
        state.entry_fees_usd_micros,
        state.exit_fees_usd_micros,
    ) == (-125, 10, 20)
    assert state.declared_realization_balance_usd_micros == -20
    assert state.complete_declared_net_return_usd_micros == -155
    assert state.phase == "FLAT"
    assert result.budget_decision.realization_loss_from_original_seed_usd_micros == 155
    assert result.budget_decision.hypothetical_loss_after_entry_fee_usd_micros == 165
    assert result.budget_decision.disposition == "declared_budget_insufficient"


def test_repeated_pure_assessments_do_not_advance_records_fees_reserves_or_clocks():
    for ctx, call in (
        (context(open_position()), run_budget),
        (pending_context("exit"), run_deadline),
    ):
        original_records = ctx["records"]
        before = accounting_state(ctx)
        first = call(ctx)
        assert call(ctx) == first
        assert ctx["records"] is original_records
        assert accounting_state(ctx) == before
        assert first.accounting_state == before


PREFLIGHT_CASES = [
    "fixture_subclass",
    "genesis_subclass",
    "native_prefix_subclass",
    "accounting_prefix_subclass",
    "fixture_incomplete",
    "genesis_incomplete",
    "native_prefix_incomplete",
    "accounting_prefix_incomplete",
    "record_list",
    "record_tuple_subclass",
    "too_many_records",
    "fixture_quote_list",
    "fixture_quote_tuple_subclass",
    "too_many_quotes",
    "fixture_publication_list",
    "fixture_publication_tuple_subclass",
    "too_many_publications",
    "bare_session",
    "bare_scenario",
    "empty_session_suffix",
    "empty_scenario_suffix",
    "session_too_long",
    "scenario_too_long",
    "session_string_subclass",
    "scenario_string_subclass",
    "unsupported_fixture_contract",
    "native_total_quotes",
    "native_total_publications",
    "native_consumed_count",
    "native_pin",
    "native_source_session",
    "native_contract",
    "native_source_pin",
    "native_start",
    "native_end",
    "native_count_bool",
    "native_count_float",
    "native_count_subclass",
    "native_flag_zero",
    "accounting_sequence",
    "accounting_sequence_bool",
    "accounting_sequence_float",
    "accounting_sequence_subclass",
    "accounting_frontier_bool",
    "accounting_bad_head",
    "fixture_pin_type",
    "fixture_pin_syntax",
    "genesis_pin_type",
    "genesis_pin_syntax",
]


def poison_top_level(value):
    def forbidden(self, name):
        raise AssertionError("Exact top-level type must be checked before field access")

    subclass = type("PoisonSubclass", (type(value),), {"__getattribute__": forbidden})
    return object.__new__(subclass)


def corrupted_preflight(ctx, case):
    result = dict(ctx)
    names = {
        "fixture": "fixture",
        "genesis": "genesis",
        "native_prefix": "expected_native_prefix",
        "accounting_prefix": "expected_accounting_prefix",
    }
    for name, key in names.items():
        if case == name + "_subclass":
            result[key] = poison_top_level(ctx[key])
            return result
        if case == name + "_incomplete":
            result[key] = object.__new__(type(ctx[key]))
            return result
    fixture = ctx["fixture"]
    prefix = ctx["expected_native_prefix"]
    if case == "record_list":
        result["records"] = list(ctx["records"])
    elif case == "record_tuple_subclass":
        result["records"] = TupleSubclass(ctx["records"])
    elif case == "too_many_records":
        result["records"] = (object(),) * 129
    elif case.startswith("fixture_quote_"):
        value = list(fixture.quotes) if case.endswith("list") else TupleSubclass(fixture.quotes)
        result["fixture"] = changed(fixture, quotes=value)
    elif case == "too_many_quotes":
        result["fixture"] = changed(fixture, quotes=(object(),) * 1025)
    elif case.startswith("fixture_publication_"):
        value = (
            list(fixture.publications)
            if case.endswith("list")
            else TupleSubclass(fixture.publications)
        )
        result["fixture"] = changed(fixture, publications=value)
    elif case == "too_many_publications":
        result["fixture"] = changed(fixture, publications=(object(),) * 65)
    elif case in (
        "bare_session",
        "empty_session_suffix",
        "session_too_long",
        "session_string_subclass",
    ):
        value = {
            "bare_session": "2025-07-07",
            "empty_session_suffix": "synthetic-",
            "session_too_long": "synthetic-" + "a" * 55,
            "session_string_subclass": StringSubclass(fixture.source_session),
        }[case]
        result["fixture"] = changed(fixture, source_session=value)
        result["expected_native_prefix"] = changed(prefix, source_session=value)
    elif case in (
        "bare_scenario",
        "empty_scenario_suffix",
        "scenario_too_long",
        "scenario_string_subclass",
    ):
        value = {
            "bare_scenario": "ordinary-account",
            "empty_scenario_suffix": "synthetic-",
            "scenario_too_long": "synthetic-" + "a" * 55,
            "scenario_string_subclass": StringSubclass(ctx["genesis"].scenario_id),
        }[case]
        result["genesis"] = changed(ctx["genesis"], scenario_id=value)
    elif case == "unsupported_fixture_contract":
        result["fixture"] = changed(fixture, contract="6EU9")
        result["expected_native_prefix"] = changed(prefix, contract="6EU9")
    elif case.startswith("native_"):
        changes = {
            "native_total_quotes": {"total_quotes": prefix.total_quotes + 1},
            "native_total_publications": {"total_publications": prefix.total_publications + 1},
            "native_consumed_count": {"consumed_count": prefix.total_quotes + 1},
            "native_pin": {"fixture_sha256": "f" * 64},
            "native_source_session": {"source_session": "synthetic-other"},
            "native_contract": {"contract": "6EZ5"},
            "native_source_pin": {"source_sha256": "f" * 64},
            "native_start": {"start_ns": fixture.start_ns + 1},
            "native_end": {"end_ns": fixture.end_ns + 1},
            "native_count_bool": {"consumed_count": True},
            "native_count_float": {"consumed_count": float(prefix.consumed_count)},
            "native_count_subclass": {"consumed_count": IntSubclass(prefix.consumed_count)},
            "native_flag_zero": {
                "authority_flags": ((prefix.authority_flags[0][0], 0), *prefix.authority_flags[1:])
            },
        }[case]
        result["expected_native_prefix"] = changed(prefix, **changes)
    elif case.startswith("accounting_"):
        accounting = ctx["expected_accounting_prefix"]
        changes = {
            "accounting_sequence": {"sequence": accounting.sequence + 1},
            "accounting_sequence_bool": {"sequence": True},
            "accounting_sequence_float": {"sequence": float(accounting.sequence)},
            "accounting_sequence_subclass": {"sequence": IntSubclass(accounting.sequence)},
            "accounting_frontier_bool": {"complete_through_ns": True},
            "accounting_bad_head": {"head_sha256": "A" * 64},
        }[case]
        result["expected_accounting_prefix"] = changed(accounting, **changes)
    else:
        key = (
            "expected_fixture_sha256"
            if case.startswith("fixture_pin")
            else "expected_genesis_sha256"
        )
        result[key] = StringSubclass(ctx[key]) if case.endswith("type") else "A" * 64
    return result


@pytest.mark.parametrize("kind", ["budget", "deadline"])
@pytest.mark.parametrize("case", PREFLIGHT_CASES)
def test_preflight_specificity_before_both_quote_and_receipt_paths(kind, case, monkeypatch):
    ctx, call = (context(), run_budget) if kind == "budget" else (pending_context(), run_deadline)
    assert call(ctx).authority_flags == oracle_flags()
    bad = corrupted_preflight(ctx, case)
    forbid_deep_paths(monkeypatch)
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        call(bad)


@pytest.mark.parametrize("kind", ["budget", "deadline"])
@pytest.mark.parametrize("which", ["fixture", "genesis"])
def test_valid_but_wrong_external_pin_refuses_complete_reconstruction(kind, which):
    ctx, call = (context(), run_budget) if kind == "budget" else (pending_context(), run_deadline)
    assert call(ctx).authority_flags == oracle_flags()
    bad = dict(ctx)
    bad[f"expected_{which}_sha256"] = "f" * 64
    if which == "fixture":
        bad["expected_native_prefix"] = changed(
            ctx["expected_native_prefix"], fixture_sha256="f" * 64
        )
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        call(bad)


@pytest.mark.parametrize("kind", ["budget", "deadline"])
@pytest.mark.parametrize(
    "field", ["consumed_content_sha256", "last_received_at_ns", "current_timestamp_first_cursor"]
)
def test_scalar_valid_but_forged_retained_native_prefix_refuses_exact_reconstruction(kind, field):
    ctx, call = (context(), run_budget) if kind == "budget" else (pending_context(), run_deadline)
    assert call(ctx).authority_flags == oracle_flags()
    prefix = ctx["expected_native_prefix"]
    value = {
        "consumed_content_sha256": "f" * 64,
        "last_received_at_ns": prefix.last_received_at_ns + 1,
        "current_timestamp_first_cursor": prefix.last_cursor,
    }[field]
    if field == "current_timestamp_first_cursor" and value == prefix.current_timestamp_first_cursor:
        value = None
    bad = dict(ctx, expected_native_prefix=changed(prefix, **{field: value}))
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        call(bad)


@pytest.mark.parametrize("kind", ["budget", "deadline"])
@pytest.mark.parametrize("field", ["head_sha256", "complete_through_ns"])
def test_scalar_valid_but_forged_accounting_prefix_refuses_complete_state_reconstruction(
    kind, field
):
    ctx, call = (context(), run_budget) if kind == "budget" else (pending_context(), run_deadline)
    assert call(ctx).authority_flags == oracle_flags()
    prefix = ctx["expected_accounting_prefix"]
    value = "f" * 64 if field == "head_sha256" else prefix.complete_through_ns + 1
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        call(dict(ctx, expected_accounting_prefix=changed(prefix, **{field: value})))


@pytest.mark.parametrize("kind", ["budget", "deadline"])
@pytest.mark.parametrize(
    "drift", ["future_price", "equal_time_order", "omitted_quote", "omitted_record"]
)
def test_complete_context_drift_never_adopts_a_successful_subset(kind, drift):
    ctx, call = (
        (context(linear_clock_tape(2)), run_budget)
        if kind == "budget"
        else (pending_context(), run_deadline)
    )
    assert call(ctx).authority_flags == oracle_flags()
    bad = dict(ctx)
    fixture = ctx["fixture"]
    if drift == "future_price":
        quotes = (*fixture.quotes[:-1], changed(fixture.quotes[-1], ask_nano=PRICE + 7 * TICK))
        bad["fixture"] = changed(fixture, quotes=quotes)
    elif drift == "equal_time_order":
        cursor = 0 if kind == "budget" else 1
        quotes = list(fixture.quotes)
        quotes[cursor], quotes[cursor + 1] = quotes[cursor + 1], quotes[cursor]
        bad["fixture"] = changed(fixture, quotes=tuple(quotes))
    elif drift == "omitted_quote":
        bad["fixture"] = changed(fixture, quotes=fixture.quotes[:-1])
    else:
        bad["records"] = ctx["records"][:-1]
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        call(bad)


@pytest.mark.parametrize("kind", ["budget", "deadline"])
def test_reordered_complete_accounting_records_refuse_wrapped_preceding_prefix_conflict(kind):
    ctx, call = (
        (context(pending_exit()), run_budget)
        if kind == "budget"
        else (pending_context("exit"), run_deadline)
    )
    assert call(ctx).accounting_state.prefix.sequence == 3
    original = ctx["records"]
    reordered = (original[1], original[0], original[2])
    bad = dict(ctx, records=reordered)
    assert len(reordered) == ctx["expected_accounting_prefix"].sequence
    with pytest.raises(admission.DeclaredAdmissionError, match="preceding prefix"):
        accounting_state(bad)
    with pytest.raises(assessment.NativeAdmissionAssessmentError, match="preceding prefix"):
        call(bad)


def rebind_constructed_records(ctx, records):
    """Bind malformed scalar contents, so an unrelated terminal mismatch cannot mask them."""
    prefix = admission.DeclaredPrefix(
        0, ctx["expected_genesis_sha256"], ctx["genesis"].seed.initialized_at_ns
    )
    rebuilt = []
    for record in records:
        record = changed(record, expected_prefix=prefix)
        identity = sha(
            {
                "version": "six_e_declared_admission_v1",
                "kind": type(record.payload).__name__,
                "record": asdict(record),
            }
        )
        prefix = admission.DeclaredPrefix(prefix.sequence + 1, identity, record.complete_through_ns)
        rebuilt.append(record)
    return dict(ctx, records=tuple(rebuilt), expected_accounting_prefix=prefix)


@pytest.mark.parametrize("kind", ["budget", "deadline"])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("price_nano", PRICE + 1),
        ("price_nano", True),
        ("executed_at_ns", float(START + admission.DELAY_NS)),
    ],
)
def test_poisoned_receipt_with_matching_canonical_terminal_is_a_wrapped_held_refusal(
    kind, field, value
):
    ctx, call = (
        (context(pending_exit()), run_budget)
        if kind == "budget"
        else (pending_context("exit"), run_deadline)
    )
    assert call(ctx).accounting_state.prefix.sequence == 3
    records = list(ctx["records"])
    payload = changed(records[1].payload, **{field: value})
    records[1] = changed(records[1], payload=payload)
    bad = rebind_constructed_records(ctx, records)
    assert (
        bad["expected_accounting_prefix"].head_sha256
        != ctx["expected_accounting_prefix"].head_sha256
    )
    with pytest.raises(admission.DeclaredAdmissionError) as held:
        accounting_state(bad)
    with pytest.raises(assessment.NativeAdmissionAssessmentError) as wrapped:
        call(bad)
    assert str(wrapped.value) == str(held.value)
    assert accounting_state(ctx).entry_fees_usd_micros == 10


@pytest.mark.parametrize("kind", ["budget", "deadline"])
def test_poison_receipt_subclass_refuses_without_reading_its_price_fields(kind):
    class PoisonReceipt(admission.EntryReceipt):
        def __getattribute__(self, name):
            raise AssertionError("Unsupported receipt subtype must refuse before field access")

    ctx, call = (
        (context(pending_exit()), run_budget)
        if kind == "budget"
        else (pending_context("exit"), run_deadline)
    )
    assert call(ctx).accounting_state.prefix.sequence == 3
    records = list(ctx["records"])
    records[1] = changed(records[1], payload=object.__new__(PoisonReceipt))
    with pytest.raises(assessment.NativeAdmissionAssessmentError, match="typed payload"):
        call(dict(ctx, records=tuple(records)))


@pytest.mark.parametrize("count", [0, 2, 3])
def test_first_cursor_budget_refuses_before_publication_or_after_equal_time_suffix(count):
    ctx = context()
    assert run_budget(ctx).publication.boundary_state == "OPEN"
    bad = dict(ctx, expected_native_prefix=native_prefix(ctx["fixture"], count))
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        run_budget(bad)


@pytest.mark.parametrize(
    "publication_id", [None, True, "", "bad space", StringSubclass("pub-1")], ids=safe_id
)
def test_publication_identifier_schema_precedes_reconstruction(publication_id, monkeypatch):
    ctx = context()
    assert run_budget(ctx).publication.publication_id == "pub-1"
    forbid_deep_paths(monkeypatch)
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        assessment.assess_publication_budget(**ctx, publication_id=publication_id)


def test_unregistered_publication_is_not_manufactured_from_a_caller_identifier():
    ctx = context()
    assert run_budget(ctx).publication.publication_id == "pub-1"
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        assessment.assess_publication_budget(**ctx, publication_id="new-publication")


@pytest.mark.parametrize("kind", ["entry", "exit"])
@pytest.mark.parametrize("count", [0, 1, 2, 3, 4])
def test_deadline_coverage_requires_every_equality_row_and_no_consumed_later_price(kind, count):
    ctx = pending_context(kind)
    assert run_deadline(ctx).boundary.closure_kind == "next_timestamp"
    candidate = dict(ctx, expected_native_prefix=native_prefix(ctx["fixture"], count))
    if count == 3:
        result = run_deadline(candidate)
        assert_link(result, oracle_deadline_body(candidate))
    else:
        with pytest.raises(assessment.NativeAdmissionAssessmentError):
            run_deadline(candidate)


@pytest.mark.parametrize("kind", ["entry", "exit"])
@pytest.mark.parametrize("offset", [-1, 1])
def test_only_prospectively_retained_original_deadline_is_accepted(kind, offset):
    ctx = pending_context(kind)
    assert run_deadline(ctx).deadline_ns == ctx["expected_deadline_ns"]
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        run_deadline(dict(ctx, expected_deadline_ns=ctx["expected_deadline_ns"] + offset))


@pytest.mark.parametrize(
    "deadline", [None, True, 1.0, -1, MAX_INT + 1, IntSubclass(START)], ids=safe_id
)
def test_deadline_scalar_type_guard_precedes_deep_reconstruction(deadline, monkeypatch):
    ctx = pending_context()
    assert run_deadline(ctx).deadline_ns == ctx["expected_deadline_ns"]
    bad = dict(ctx, expected_deadline_ns=deadline)
    forbid_deep_paths(monkeypatch)
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        run_deadline(bad)


@pytest.mark.parametrize("kind", ["entry", "exit"])
def test_deadline_requires_original_liability_contract_not_another_supported_fixture_contract(kind):
    ctx = pending_context(kind)
    assert run_deadline(ctx).contract == "6EU5"
    fixture = changed(ctx["fixture"], contract="6EZ5")
    bad = dict(ctx, fixture=fixture, expected_native_prefix=native_prefix(fixture, 3))
    bad["expected_fixture_sha256"] = bad["expected_native_prefix"].fixture_sha256
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        run_deadline(bad)


@pytest.mark.parametrize("kind", ["entry", "exit"])
@pytest.mark.parametrize(
    "edge",
    ["ready_equal_start", "ready_before_start", "deadline_end_minus_one", "deadline_equal_end"],
)
def test_entire_inclusive_ready_deadline_interval_must_be_inside_half_open_native_window(
    kind, edge
):
    ctx = pending_context(kind, eof=True)
    ready = (
        accounting_state(ctx).pending_entry.ready_at_ns
        if kind == "entry"
        else accounting_state(ctx).pending_exit.ready_at_ns
    )
    deadline = ctx["expected_deadline_ns"]
    fixture = ctx["fixture"]
    if edge == "ready_equal_start":
        fixture = changed(fixture, start_ns=ready)
    elif edge == "ready_before_start":
        fixture = changed(fixture, start_ns=ready + 1, quotes=fixture.quotes[1:])
    elif edge == "deadline_end_minus_one":
        fixture = changed(fixture, end_ns=deadline + 1)
    else:
        fixture = changed(fixture, end_ns=deadline, quotes=fixture.quotes[:1])
    candidate = dict(
        ctx, fixture=fixture, expected_native_prefix=native_prefix(fixture, len(fixture.quotes))
    )
    candidate["expected_fixture_sha256"] = candidate["expected_native_prefix"].fixture_sha256
    native.prepare_fixture(fixture, expected_fixture_sha256=candidate["expected_fixture_sha256"])
    if edge in ("ready_equal_start", "deadline_end_minus_one"):
        result = run_deadline(candidate)
        assert_link(result, oracle_deadline_body(candidate))
    else:
        with pytest.raises(assessment.NativeAdmissionAssessmentError):
            run_deadline(candidate)


@pytest.mark.parametrize("phase", ["flat", "open", "unknown"])
@pytest.mark.parametrize("zero", [False, True])
def test_deadline_assessment_refuses_nonpending_and_terminal_unknown_without_transition(
    phase, zero
):
    genesis = (
        declared(
            1, entry=0, exit_fee=0, margin=budget.economics.DeclaredMargin(0, 0), buffer=0, loss=0
        )
        if zero
        else declared()
    )
    tape = {"flat": Tape, "open": open_position, "unknown": unknown_exit}[phase](genesis)
    before = tape.state()
    if phase == "unknown":
        ctx = pending_context("exit", tape=tape)
        assert ctx["expected_deadline_ns"] == before.pending_exit.deadline_ns
        closure = native.close_through(
            ctx["fixture"],
            expected_fixture_sha256=ctx["expected_fixture_sha256"],
            expected_prefix=ctx["expected_native_prefix"],
            through_ns=ctx["expected_deadline_ns"],
        )
        assert closure.closure_kind == "next_timestamp"
        assert closure.through_ns == before.pending_exit.deadline_ns
    else:
        ctx = context(tape)
        ctx["expected_deadline_ns"] = START + admission.DELAY_NS + admission.WAIT_NS
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        run_deadline(ctx)
    assert tape.state() == before
    if phase == "unknown":
        assert before.pending_exit.status == "UNKNOWN"
        assert before.complete_declared_equity_usd_micros is None
        if zero:
            assert before.total_commitments_usd_micros == 0


def test_deadline_coverage_does_not_prove_absence_of_eligible_fills_or_expire_a_timer():
    ctx = pending_context()
    result = run_deadline(ctx)
    assert result.boundary.prefix.consumed_count == 3
    assert ctx["fixture"].quotes[0].received_at_ns == result.ready_at_ns
    assert ctx["fixture"].quotes[1].received_at_ns == result.deadline_ns
    assert result.accounting_state.phase == "ENTRY_PENDING"
    assert result.accounting_state.pending_entry is not None
    assert result.accounting_state.entry_fees_usd_micros == 0
    assert result.accounting_state.total_commitments_usd_micros == 130
    flags = dict(result.authority_flags)
    for name in EXTRA_FLAGS:
        assert flags[name] is False


def test_empty_supplied_eof_is_local_coverage_not_market_completeness_or_timeout():
    ctx = pending_context()
    fixture = changed(ctx["fixture"], quotes=())
    candidate = dict(ctx, fixture=fixture, expected_native_prefix=native_prefix(fixture, 0))
    candidate["expected_fixture_sha256"] = candidate["expected_native_prefix"].fixture_sha256
    result = run_deadline(candidate)
    assert_link(result, oracle_deadline_body(candidate))
    assert result.boundary.closure_kind == "complete_eof"
    assert result.accounting_state.pending_entry is not None
    assert dict(result.authority_flags)["absence_of_eligible_fill_verified"] is False


@pytest.mark.parametrize("kind", ["budget", "deadline"])
def test_link_hash_closed_schema_binds_every_context_without_hashing_itself(kind):
    ctx, call, oracle = (
        (context(), run_budget, oracle_budget_body)
        if kind == "budget"
        else (pending_context("exit"), run_deadline, oracle_deadline_body)
    )
    result = call(ctx)
    body = oracle(ctx)
    assert_link(result, body)
    assert sha(asdict(result)) != result.link_sha256
    for key in (
        "version",
        "status",
        "fixture_sha256",
        "genesis_sha256",
        "native_prefix",
        "accounting_state",
        "authority_flags",
    ):
        altered = dict(body)
        altered[key] = None
        assert sha(altered) != result.link_sha256
    for field in fields(result):
        with pytest.raises(FrozenInstanceError):
            setattr(result, field.name, getattr(result, field.name))
    assert not hasattr(result, "__dict__")


@pytest.mark.parametrize("kind", ["budget", "deadline"])
def test_reduced_link_byte_bound_checks_equality_and_never_returns_partial_output(
    kind, monkeypatch
):
    """A reduced-cap enforcement probe; bounded production schema is much smaller."""
    ctx, call, oracle = (
        (context(), run_budget, oracle_budget_body)
        if kind == "budget"
        else (pending_context(), run_deadline, oracle_deadline_body)
    )
    body = oracle(ctx)
    size = len(canonical(body))
    assert size < 256 * 1024
    monkeypatch.setattr(assessment, "MAX_LINK_BYTES", size)
    assert_link(call(ctx), body)
    monkeypatch.setattr(assessment, "MAX_LINK_BYTES", size - 1)
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        call(ctx)


@pytest.mark.parametrize("kind", ["budget", "deadline"])
def test_reduced_native_input_cap_is_preserved_by_the_assessment(kind, monkeypatch):
    ctx, call = (context(), run_budget) if kind == "budget" else (pending_context(), run_deadline)
    assert call(ctx).authority_flags == oracle_flags()
    size = len(canonical(fixture_body(ctx["fixture"])))
    monkeypatch.setattr(native, "MAX_INPUT_BYTES", size - 1)
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        call(ctx)


def maximum_publication_context():
    tape = linear_clock_tape(128, declared(age=64 * SECOND))
    quotes = (native.NativeQuote(START, PRICE, PRICE + TICK),) * 960
    quotes += tuple(
        native.NativeQuote(START + (index + 1) * SECOND, PRICE + TICK, PRICE + 2 * TICK)
        for index in range(64)
    )
    publications = tuple(
        native.NativePublication(
            "pub-1" if index == 63 else f"other-publication-{index}",
            960 + index,
            START + (index + 1) * SECOND,
        )
        for index in range(64)
    )
    fixture = native.NativeFixture(
        "synthetic-maximum-case",
        "6EU5",
        "c" * 64,
        START,
        END,
        quotes,
        publications,
    )
    return context(tape, fixture, 1024)


def maximum_deadline_context():
    tape = linear_clock_tape(127).append(admission.AdmissionRequested("entry-1", "6EU5", "long", 1))
    deadline = tape.state().pending_entry.deadline_ns
    fixture = native.NativeFixture(
        "synthetic-maximum-deadline",
        "6EU5",
        "d" * 64,
        START,
        END,
        (native.NativeQuote(deadline, PRICE, PRICE + TICK),) * 1024,
        (),
    )
    ctx = context(tape, fixture, 1024)
    ctx["expected_deadline_ns"] = deadline
    return ctx


@pytest.mark.parametrize("kind", ["budget", "deadline"])
def test_complete_maximum_contexts_reconstruct_with_bounded_linear_work(kind, monkeypatch):
    ctx, call, oracle = (
        (maximum_publication_context(), run_budget, oracle_budget_body)
        if kind == "budget"
        else (maximum_deadline_context(), run_deadline, oracle_deadline_body)
    )
    assert len(ctx["records"]) == 128
    assert len(ctx["fixture"].quotes) == ctx["expected_native_prefix"].consumed_count == 1024
    if kind == "budget":
        assert (
            len(ctx["fixture"].publications)
            == ctx["expected_native_prefix"].total_publications
            == 64
        )
    body = oracle(ctx)
    original_step, original_quote = admission._step, native._quote_fields
    counts = {"records": 0, "quotes": 0}

    def step(*args, **kwargs):
        counts["records"] += 1
        return original_step(*args, **kwargs)

    def quote(*args, **kwargs):
        counts["quotes"] += 1
        return original_quote(*args, **kwargs)

    monkeypatch.setattr(admission, "_step", step)
    monkeypatch.setattr(native, "_quote_fields", quote)
    started = time.perf_counter()
    result = call(ctx)
    elapsed = time.perf_counter() - started
    assert_link(result, body)
    assert result.accounting_state.prefix.sequence == 128
    assert result.native_prefix.consumed_count == result.native_prefix.total_quotes == 1024
    assert 128 <= counts["records"] <= 4 * 128
    assert 1024 <= counts["quotes"] <= 4 * 1024
    assert elapsed < 10  # Generous constructed bound, not trading throughput or latency.


@pytest.mark.parametrize("kind", ["budget", "deadline"])
def test_complete_129_records_refuse_instead_of_adopting_the_first_128(kind, monkeypatch):
    if kind == "budget":
        tape = linear_clock_tape(129)
        ctx = context(tape)
        control = context(linear_clock_tape(128))
        call = run_budget
    else:
        tape = linear_clock_tape(128).append(
            admission.AdmissionRequested("entry-1", "6EU5", "long", 1)
        )
        ctx = pending_context(tape=tape)
        control = maximum_deadline_context()
        call = run_deadline
    assert len(ctx["records"]) == ctx["expected_accounting_prefix"].sequence == 129
    assert call(control).accounting_state.prefix.sequence == 128
    forbid_deep_paths(monkeypatch)
    with pytest.raises(assessment.NativeAdmissionAssessmentError):
        call(ctx)


def test_all_four_held_supported_contracts_preserve_their_exact_identity():
    for contract in ("6EM5", "6EU5", "6EZ5", "6EH6"):
        ctx = context(fixture=publication_fixture(contract=contract))
        result = run_budget(ctx)
        assert result.budget_decision.proposal.contract == contract
        assert_link(result, oracle_budget_body(ctx))


@pytest.mark.parametrize("kind", ["entry", "exit"])
def test_constructed_record_receipts_do_not_gain_native_history_authentication(kind):
    tape = pending_entry() if kind == "entry" else pending_exit()
    ctx = pending_context(kind, tape=tape)
    result = run_deadline(ctx)
    assert result.accounting_state == tape.state()
    assert dict(result.authority_flags)["native_accounting_history_verified"] is False
    assert dict(result.authority_flags)["receipt_provenance_authenticated"] is False
    if kind == "exit":
        assert len(result.accounting_state.receipt_content_sha256s) == 1
        assert result.accounting_state.entry_fees_usd_micros == 10
        assert result.accounting_state.exit_fees_usd_micros == 0


def test_next_quote_prices_are_neither_exposed_nor_consumed_by_deadline_assessment():
    first = pending_context()
    original = run_deadline(first)
    fixture = first["fixture"]
    different = changed(
        fixture,
        quotes=(
            *fixture.quotes[:3],
            native.NativeQuote(
                fixture.quotes[3].received_at_ns, PRICE + 50 * TICK, PRICE + 51 * TICK
            ),
        ),
    )
    second = dict(first, fixture=different, expected_native_prefix=native_prefix(different, 3))
    second["expected_fixture_sha256"] = second["expected_native_prefix"].fixture_sha256
    altered = run_deadline(second)
    assert altered.link_sha256 != original.link_sha256
    assert altered.accounting_state == original.accounting_state
    assert (
        altered.native_prefix.consumed_content_sha256
        == original.native_prefix.consumed_content_sha256
    )
    assert altered.boundary.next_cursor == original.boundary.next_cursor == 3
    assert altered.boundary.next_received_at_ns == original.boundary.next_received_at_ns
    assert altered.native_prefix.consumed_count == original.native_prefix.consumed_count == 3
    assert set(asdict(altered.boundary)) == {
        "prefix",
        "through_ns",
        "closure_kind",
        "next_cursor",
        "next_received_at_ns",
        "boundary_state",
        "authority_flags",
    }


def test_source_has_only_allowed_imports_and_no_cli_advance_or_outcome_generation():
    tree = ast.parse(inspect.getsource(assessment))
    roots, project_aliases = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or "").split(".")[0])
            if node.module == "ai_trader.research":
                project_aliases.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "advance",
                "append",
                "EntryReceipt",
                "ExitReceipt",
                "ExitUnknown",
                "ExitRequested",
                "AdmissionRequested",
            }
    assert roots <= {"__future__", "hashlib", "json", "dataclasses", "ai_trader"}
    assert project_aliases == {
        "six_e_declared_admission",
        "six_e_entry_budget",
        "six_e_native_prefix",
    }
    assert not hasattr(assessment, "main")
    assert not hasattr(assessment, "verify_budget_assessment")
    assert not hasattr(assessment, "verify_deadline_assessment")


def test_pure_both_assessments_with_io_network_process_and_advance_disabled(monkeypatch):
    budget_ctx, deadline_ctx = context(open_position()), pending_context("exit")
    budget_body, deadline_body = oracle_budget_body(budget_ctx), oracle_deadline_body(deadline_ctx)

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Assessments must not use I/O, network, processes or state advancement"
        )

    with monkeypatch.context() as active:
        active.setattr(builtins, "open", forbidden)
        active.setattr(Path, "open", forbidden)
        active.setattr(socket, "socket", forbidden)
        active.setattr(socket, "create_connection", forbidden)
        active.setattr(sqlite3, "connect", forbidden)
        active.setattr(subprocess, "Popen", forbidden)
        active.setattr(subprocess, "run", forbidden)
        active.setattr(admission, "advance", forbidden)
        assert_link(run_budget(budget_ctx), budget_body)
        assert_link(run_deadline(deadline_ctx), deadline_body)
