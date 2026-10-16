"""Independent, invented one-entry protocol controls; no historical prices or orders."""

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
from ai_trader.research import six_e_single_entry_driver as driver

START = 10_000_000_000
PUB = START + 1_000_000_000
READY = PUB + 100_000_000
DEADLINE = READY + 1_000_000_000
END = START + 90_000_000_000
TICK = 50_000
PRICE = 1_000_000_000
SOURCE = "a" * 64
VERSION = "six_e_single_entry_driver_v1"
STATUS = "constructed_single_entry_plan_not_trading"


def canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def changed(value, **changes):
    """Poison a valid frozen object only in the test to reach consumer revalidation."""
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(result, field.name, getattr(value, field.name))
    for name, replacement in changes.items():
        object.__setattr__(result, name, replacement)
    return result


def safe_id(value):
    return (
        repr(value) if type(value) in (str, int, float, bool, type(None)) else type(value).__name__
    )


class IntSubclass(int):
    pass


class StrSubclass(str):
    pass


class TupleSubclass(tuple):
    pass


def forbidden(*args, **kwargs):
    raise AssertionError("Forbidden deep traversal or external hook was reached")


def quote(at, bid=PRICE, spread=TICK):
    return native.NativeQuote(at, bid, bid + spread)


def fixture(rows=None, *, publication_at=PUB, end=END, contract="6EM5", start=START):
    if rows is None:
        rows = (quote(PUB), quote(PUB, PRICE + 8 * TICK), quote(READY), quote(DEADLINE + 1))
    cursor = next(i for i, row in enumerate(rows) if row.received_at_ns == publication_at)
    return native.NativeFixture(
        "synthetic-driver-tape",
        contract,
        SOURCE,
        start,
        end,
        tuple(rows),
        (native.NativePublication("pub-1", cursor, publication_at),),
    )


def genesis(*, balance=135, entry=10, exit_fee=20, margin=100, buffer=5, age=0, loss=None):
    margin_value = None if margin is None else budget.economics.DeclaredMargin(margin, margin)
    return admission.DeclaredAdmissionGenesis(
        "synthetic-driver-account",
        budget.EconomicSeed(balance, START),
        budget.DeclaredEconomics("USD", 625, entry, exit_fee, margin_value),
        budget.DeclaredBudgetLimits(buffer, age, loss),
    )


def declaration(side="long"):
    return driver.SingleEntryDeclaration("synthetic-one-entry", "pub-1", "entry-1", side)


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
            "end_buffer_ns": 18000000000,
            "quantity_contracts": 1,
            "max_quotes": 128,
            "max_publications": 1,
            "max_accounting_records": 3,
            "max_result_bytes": 65536,
            "clock_event_id": "publication-clock",
            "request_event_id": "admission-request",
            "outcome_event_id": "entry-outcome",
            "entry_receipt_id": "constructed-entry-receipt",
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
    return driver.build_single_entry_plan(
        tape, account, proposal, **arguments(tape, account, proposal)
    )


def prefix_oracle(tape, count):
    content = digest(
        {
            "version": "six_e_native_prefix_v1",
            "kind": "consumed_metadata_seed",
            "metadata": metadata(tape),
        }
    )
    run_first = last_at = None
    for cursor, row in enumerate(tape.quotes[:count]):
        if row.received_at_ns != last_at:
            run_first = cursor
        last_at = row.received_at_ns
        content = digest(
            {
                "version": "six_e_native_prefix_v1",
                "kind": "consumed_quote",
                "previous_sha256": content,
                "native_cursor": cursor,
                "quote": [row.received_at_ns, row.bid_nano, row.ask_nano],
            }
        )
    return native.NativePrefix(
        fixture_pin(tape),
        tape.source_session,
        tape.contract,
        tape.source_sha256,
        tape.start_ns,
        tape.end_ns,
        len(tape.quotes),
        len(tape.publications),
        count,
        count - 1 if count else None,
        last_at,
        run_first,
        content,
        native.AUTHORITY_FLAGS,
    )


def oracle(tape, account, proposal):
    """Construct cadence, heads, budget, source links and full plan independently."""
    pins = arguments(tape, account, proposal)
    gp = pins["expected_genesis_sha256"]
    pub = tape.publications[0]
    pub_prefix = prefix_oracle(tape, pub.published_cursor + 1)
    witness = native.PublicationWitness(
        pub.publication_id, pub.published_cursor, pub.received_at_ns, pub_prefix
    )
    records, links = [], []
    accounting_prefix = admission.DeclaredPrefix(0, gp, account.seed.initialized_at_ns)

    def append(event_id, at, payload, native_prefix, kind, publication=None, boundary=None):
        nonlocal accounting_prefix
        record = admission.DeclaredRecord(event_id, accounting_prefix, at, at, payload)
        head = digest(
            {
                "version": "six_e_declared_admission_v1",
                "kind": type(payload).__name__,
                "record": asdict(record),
            }
        )
        accounting_prefix = admission.DeclaredPrefix(len(records) + 1, head, at)
        links.append(
            {
                "record_index": len(records),
                "event_id": event_id,
                "record_sha256": head,
                "native_prefix": asdict(native_prefix),
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
        accounting_prefix.head_sha256,
        pub.received_at_ns,
        pub.received_at_ns,
        0,
        0,
        None,
        False,
    )
    entry_proposal = budget.EntryProposal(
        pub.received_at_ns, 1, accounting_prefix.head_sha256, tape.contract, 1
    )
    decision = budget.assess_entry_budget(
        snapshot, entry_proposal, account.economics, account.limits
    )
    append(
        "admission-request",
        pub.received_at_ns,
        admission.AdmissionRequested(proposal.admission_id, tape.contract, proposal.side, 1),
        pub_prefix,
        "publication",
        witness,
    )
    outcome, cursor, at = "no_pending_entry", None, None
    ready = pub.received_at_ns + 100_000_000
    deadline = ready + 1_000_000_000
    if decision.disposition == "declared_budget_available":
        candidate = next(
            (i for i, row in enumerate(tape.quotes) if ready <= row.received_at_ns <= deadline),
            None,
        )
        if candidate is not None:
            cursor, row = candidate, tape.quotes[candidate]
            at = row.received_at_ns
            if row.ask_nano - row.bid_nano != TICK:
                outcome = "simulator_spread_refusal"
                payload = admission.EntryUnfilled(proposal.admission_id, "simulator_refusal")
            else:
                outcome = "constructed_entry_receipt"
                price = row.ask_nano if proposal.side == "long" else row.bid_nano
                payload = admission.EntryReceipt(
                    proposal.admission_id,
                    "constructed-entry-receipt",
                    tape.contract,
                    proposal.side,
                    1,
                    price,
                    at,
                )
            append("entry-outcome", at, payload, prefix_oracle(tape, cursor + 1), "candidate_quote")
        else:
            outcome, at = "constructed_timeout", deadline
            count = next(
                (i for i, row in enumerate(tape.quotes) if row.received_at_ns > deadline),
                len(tape.quotes),
            )
            prefix = prefix_oracle(tape, count)
            boundary = native.ClosedNativeBoundary(
                prefix,
                deadline,
                "next_timestamp" if count < len(tape.quotes) else "complete_eof",
                count if count < len(tape.quotes) else None,
                tape.quotes[count].received_at_ns if count < len(tape.quotes) else None,
            )
            append(
                "entry-outcome",
                deadline,
                admission.EntryUnfilled(proposal.admission_id, "timeout"),
                prefix,
                "deadline_boundary",
                boundary=boundary,
            )
    # The held reducer is an independent final accounting control, not the new driver.
    terminal = admission.reconstruct(
        account, tuple(records), expected_genesis_sha256=gp, expected_terminal=accounting_prefix
    )
    audit = [
        {
            "cursor": i,
            "received_at_ns": row.received_at_ns,
            "consumed_count": i + 1,
            "consumed_content_sha256": prefix_oracle(tape, i + 1).consumed_content_sha256,
        }
        for i, row in enumerate(tape.quotes)
    ]
    body = {
        "version": VERSION,
        "status": STATUS,
        "fixture_sha256": fixture_pin(tape),
        "genesis_sha256": gp,
        "declaration_sha256": pins["expected_declaration_sha256"],
        "declaration": asdict(proposal),
        "publication": asdict(witness),
        "budget_decision": asdict(decision),
        "first_disposition": decision.disposition,
        "execution_outcome": outcome,
        "outcome_cursor": cursor,
        "outcome_at_ns": at,
        "records": tuple(asdict(r) for r in records),
        "record_links": tuple(links),
        "quote_audit": tuple(audit),
        "terminal_native_prefix": asdict(prefix_oracle(tape, len(tape.quotes))),
        "terminal_accounting_state": asdict(terminal),
        "authority_flags": assessment.AUTHORITY_FLAGS,
    }
    return body | {"plan_sha256": digest(body)}


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize(
    "rows",
    [
        (quote(PUB), quote(PUB, PRICE + 8 * TICK), quote(READY), quote(DEADLINE + 1)),
        (quote(START), quote(PUB), quote(READY - 1), quote(READY + 1)),
        (quote(PUB), quote(READY, spread=2 * TICK), quote(READY), quote(DEADLINE)),
        (quote(PUB), quote(READY - 1), quote(DEADLINE + 1)),
        (quote(PUB), quote(READY - 1)),
        (quote(PUB), quote(DEADLINE)),
    ],
)
def test_entire_plan_matches_independent_context_oracle(side, rows):
    tape, account, proposal = fixture(rows), genesis(), declaration(side)
    expected = oracle(tape, account, proposal)
    result = build(tape, account, proposal)
    assert asdict(result) == expected
    assert (
        driver.verify_single_entry_plan(
            tape,
            account,
            proposal,
            **arguments(tape, account, proposal),
            expected_plan_sha256=expected["plan_sha256"],
        )
        == result
    )


def test_exact_closed_schema_and_fixed_protocol_declaration_pin():
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert driver.VERSION == VERSION and driver.STATUS == STATUS
    assert (
        driver.declaration_sha256(
            proposal, fixture_sha256=fixture_pin(tape), genesis_sha256=genesis_pin(account)
        )
        == args["expected_declaration_sha256"]
    )
    assert [f.name for f in fields(driver.SingleEntryPlan)] == [
        "version",
        "status",
        "fixture_sha256",
        "genesis_sha256",
        "declaration_sha256",
        "declaration",
        "publication",
        "budget_decision",
        "first_disposition",
        "execution_outcome",
        "outcome_cursor",
        "outcome_at_ns",
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
    assert driver.AUTHORITY_FLAGS == assessment.AUTHORITY_FLAGS
    assert type(driver.AUTHORITY_FLAGS) is tuple
    assert all(type(k) is str and type(v) is bool and v is False for k, v in driver.AUTHORITY_FLAGS)


@pytest.mark.parametrize("delta", [-1, 0, 1])
@pytest.mark.parametrize("endpoint", [READY, DEADLINE])
def test_first_eligible_quote_uses_inclusive_original_boundaries(endpoint, delta):
    at = endpoint + delta
    tape = fixture((quote(PUB), quote(at), quote(DEADLINE + 10, PRICE + 20 * TICK)))
    result = build(tape)
    expected = "constructed_entry_receipt" if READY <= at <= DEADLINE else "constructed_timeout"
    assert result.execution_outcome == expected
    assert result.outcome_at_ns == (at if expected == "constructed_entry_receipt" else DEADLINE)
    assert result.outcome_cursor == (1 if expected == "constructed_entry_receipt" else None)


@pytest.mark.parametrize("side", ["long", "short"])
def test_opposing_publication_suffix_and_post_outcome_quotes_never_change_candidate(side):
    rows = (
        quote(PUB),
        quote(PUB, PRICE + 100 * TICK),
        quote(READY, PRICE + 3 * TICK),
        quote(READY, PRICE - 100 * TICK),
        quote(DEADLINE + 1, PRICE + 300 * TICK),
    )
    result = build(fixture(rows), proposal=declaration(side))
    assert result.publication.prefix.consumed_count == 1
    assert all(link.native_prefix.consumed_count == 1 for link in result.record_links[:2])
    assert result.outcome_cursor == 2 and len(result.records) == 3
    assert (
        result.records[-1].payload.price_nano == rows[2].ask_nano
        if side == "long"
        else (result.records[-1].payload.price_nano == rows[2].bid_nano)
    )
    assert result.terminal_native_prefix.consumed_count == 5
    assert result.terminal_accounting_state.prefix.complete_through_ns == READY


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize("spread", [2 * TICK, 3 * TICK])
def test_wide_first_candidate_is_permanent_even_before_equal_time_narrow_quote(side, spread):
    result = build(
        fixture((quote(PUB), quote(READY, spread=spread), quote(READY), quote(DEADLINE))),
        proposal=declaration(side),
    )
    assert result.first_disposition == "declared_budget_available"
    assert result.execution_outcome == "simulator_spread_refusal"
    assert result.outcome_cursor == 1 and result.records[-1].payload.reason == "simulator_refusal"
    state = result.terminal_accounting_state
    assert state.phase == "FLAT" and state.entry_fees_usd_micros == 0
    assert (
        state.total_commitments_usd_micros == 0
        and state.complete_declared_net_return_usd_micros == 0
    )


@pytest.mark.parametrize("eof", [False, True])
def test_timeout_links_original_boundary_without_consuming_later_price(eof):
    rows = (quote(PUB), quote(READY - 1))
    if not eof:
        rows += (quote(DEADLINE + 1, PRICE + 100 * TICK), quote(DEADLINE + 1, PRICE - 100 * TICK))
    result = build(fixture(rows))
    link = result.record_links[-1]
    assert result.execution_outcome == "constructed_timeout" and result.outcome_cursor is None
    assert result.outcome_at_ns == DEADLINE and result.records[-1].recorded_at_ns == DEADLINE
    assert link.kind == "deadline_boundary" and link.publication is None
    assert (
        link.native_prefix.consumed_count == 2
        and link.native_prefix.last_received_at_ns == READY - 1
    )
    assert link.boundary.through_ns == DEADLINE and link.boundary.boundary_state == "CLOSED"
    assert link.boundary.closure_kind == ("complete_eof" if eof else "next_timestamp")
    assert link.boundary.next_cursor == (None if eof else 2)
    assert len(result.quote_audit) == len(rows)
    assert result.terminal_accounting_state.phase == "FLAT"


def test_timeout_closure_and_account_outcome_precede_first_later_cursor(monkeypatch):
    tape = fixture((quote(PUB), quote(READY - 1), quote(DEADLINE + 1), quote(DEADLINE + 2)))
    assert build(tape).execution_outcome == "constructed_timeout"
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
    closure = events.index(("close", 2, DEADLINE))
    outcome = events.index(("account", "EntryUnfilled", DEADLINE))
    later = events.index(("consume", 2))
    assert closure < outcome < later
    assert events.count(("close", 2, DEADLINE)) >= 2  # Includes later link revalidation.
    assert result.terminal_native_prefix.consumed_count == 4


def test_later_price_changes_complete_pin_but_not_timeout_visible_boundary():
    one = fixture((quote(PUB), quote(READY - 1), quote(DEADLINE + 1)))
    two = fixture((quote(PUB), quote(READY - 1), quote(DEADLINE + 1, PRICE + 1000 * TICK)))
    a, b = build(one), build(two)
    assert a.plan_sha256 != b.plan_sha256 and a.fixture_sha256 != b.fixture_sha256
    assert a.execution_outcome == b.execution_outcome == "constructed_timeout"
    assert a.records == b.records
    x, y = a.record_links[-1], b.record_links[-1]
    assert x.native_prefix.consumed_content_sha256 == y.native_prefix.consumed_content_sha256
    assert x.boundary.next_received_at_ns == y.boundary.next_received_at_ns


@pytest.mark.parametrize(
    "options, disposition, reason",
    [
        ({"balance": 134}, "declared_budget_insufficient", "insufficient_declared_cash"),
        ({"loss": 9}, "declared_budget_insufficient", "proposed_entry_fee_exceeds_loss_ceiling"),
        ({"margin": None}, "budget_undetermined", "margin_not_declared"),
        (
            {"balance": 1, "entry": 0, "exit_fee": 0, "margin": 0, "buffer": 0, "loss": 0},
            "declared_budget_available",
            None,
        ),
        ({"balance": 135, "loss": 10}, "declared_budget_available", None),
    ],
)
def test_budget_cash_loss_missing_and_zero_margin_have_full_post_clock_oracles(
    options, disposition, reason
):
    tape, account, proposal = fixture(), genesis(**options), declaration()
    result = build(tape, account, proposal)
    assert asdict(result) == oracle(tape, account, proposal)
    assert result.first_disposition == disposition
    decision = result.budget_decision
    assert decision.snapshot.sequence == decision.proposal.expected_sequence == 1
    assert decision.snapshot.tip_sha256 == result.record_links[0].record_sha256
    assert (
        decision.snapshot.last_event_at_ns == PUB and decision.snapshot.observed_through_ns == PUB
    )
    assert decision.snapshot.pending_entry is False and decision.snapshot_age_ns == 0
    if reason is not None:
        assert reason in decision.reasons
        assert len(result.records) == 2 and result.execution_outcome == "no_pending_entry"
        assert result.outcome_cursor is None and result.outcome_at_ns is None
        assert result.terminal_accounting_state.total_commitments_usd_micros == 0
    else:
        assert result.terminal_accounting_state.phase == "OPEN"
        assert result.terminal_accounting_state.complete_declared_equity_usd_micros is None


def test_once_only_entry_fee_and_open_commitments_never_fake_complete_return():
    result = build()
    state = result.terminal_accounting_state
    assert state.entry_fees_usd_micros == 10 and state.exit_fees_usd_micros == 0
    assert (
        state.gross_realized_usd_micros == 0
        and state.declared_realization_balance_usd_micros == 125
    )
    assert (
        state.entry_fee_reserve_usd_micros == 0
        and state.initial_margin_commitment_usd_micros == 100
    )
    assert state.exit_fee_reserve_usd_micros == 20 and state.total_commitments_usd_micros == 120
    assert state.available_balance_usd_micros == 5
    assert state.complete_declared_equity_usd_micros is None
    assert state.complete_declared_net_return_usd_micros is None
    assert state.pending_entry is None and state.position.quantity_contracts == 1
    assert len(state.receipt_content_sha256s) == 1
    assert all(
        type(r.payload)
        not in (admission.ExitRequested, admission.ExitReceipt, admission.ExitUnknown)
        for r in result.records
    )


@pytest.mark.parametrize("contract", ["6EM5", "6EU5", "6EZ5", "6EH6"])
def test_supported_contracts_preserve_one_original_identity(contract):
    tape = fixture(contract=contract)
    result = build(tape)
    assert result.publication.prefix.contract == contract
    assert result.terminal_accounting_state.position.contract == contract
    assert all(
        r.payload.contract == contract for r in result.records if hasattr(r.payload, "contract")
    )


@pytest.mark.parametrize(
    "target", ["expected_fixture_sha256", "expected_genesis_sha256", "expected_declaration_sha256"]
)
@pytest.mark.parametrize(
    "value", [None, True, 7, "", "a" * 63, "A" * 64, "g" * 64, StrSubclass("a" * 64)], ids=safe_id
)
def test_malformed_expectations_refuse_before_price_or_accounting_traversal(
    monkeypatch, target, value
):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert build(tape, account, proposal).execution_outcome == "constructed_entry_receipt"
    args[target] = value
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleEntryDriverError):
        driver.build_single_entry_plan(tape, account, proposal, **args)


@pytest.mark.parametrize(
    "value", [None, False, 1, "", "b" * 63, "B" * 64, "z" * 64, StrSubclass("b" * 64)], ids=safe_id
)
def test_verifier_malformed_result_pin_has_early_guard(monkeypatch, value):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    positive = build(tape, account, proposal)
    assert (
        driver.verify_single_entry_plan(
            tape, account, proposal, **args, expected_plan_sha256=positive.plan_sha256
        )
        == positive
    )
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleEntryDriverError):
        driver.verify_single_entry_plan(tape, account, proposal, **args, expected_plan_sha256=value)


@pytest.mark.parametrize(
    "target",
    [
        "expected_fixture_sha256",
        "expected_genesis_sha256",
        "expected_declaration_sha256",
        "expected_plan_sha256",
    ],
)
def test_valid_but_wrong_original_pins_cannot_be_adopted(target):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    result = build(tape, account, proposal)
    args["expected_plan_sha256"] = result.plan_sha256
    args[target] = "0" * 64
    with pytest.raises(driver.SingleEntryDriverError):
        driver.verify_single_entry_plan(tape, account, proposal, **args)


@pytest.mark.parametrize(
    "field,value",
    [
        ("declaration_id", "ordinary"),
        ("declaration_id", "synthetic-"),
        ("declaration_id", "synthetic-" + "x" * 55),
        ("declaration_id", "synthetic-é"),
        ("declaration_id", StrSubclass("synthetic-one-entry")),
        ("publication_id", "other"),
        ("publication_id", "bad/id"),
        ("admission_id", ""),
        ("admission_id", "bad id"),
        ("admission_id", StrSubclass("entry-1")),
        ("side", "LONG"),
        ("side", True),
        ("side", StrSubclass("long")),
    ],
    ids=lambda value: safe_id(value),
)
def test_declaration_metadata_refuses_before_quote_traversal(monkeypatch, field, value):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert build(tape, account, proposal).first_disposition == "declared_budget_available"
    proposal = changed(proposal, **{field: value})
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleEntryDriverError):
        driver.build_single_entry_plan(tape, account, proposal, **args)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_session", "real-20261009"),
        ("source_session", "synthetic-"),
        ("source_session", StrSubclass("synthetic-driver-tape")),
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
    ids=lambda value: safe_id(value),
)
def test_fixture_metadata_refuses_before_quote_traversal(monkeypatch, field, value):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert build(tape, account, proposal).execution_outcome == "constructed_entry_receipt"
    tape = changed(tape, **{field: value})
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleEntryDriverError):
        driver.build_single_entry_plan(tape, account, proposal, **args)


@pytest.mark.parametrize(
    "kind", ["129_quotes", "no_publication", "second_publication", "tuple_subclass"]
)
def test_complete_count_caps_refuse_before_quote_access_without_subsets(monkeypatch, kind):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert len(build(tape, account, proposal).quote_audit) == 4
    if kind == "129_quotes":
        tape = changed(tape, quotes=(quote(PUB),) * 129)
    elif kind == "no_publication":
        tape = changed(tape, publications=())
    elif kind == "second_publication":
        tape = changed(tape, publications=tape.publications * 2)
    else:
        tape = changed(tape, quotes=TupleSubclass(tape.quotes))
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleEntryDriverError):
        driver.build_single_entry_plan(tape, account, proposal, **args)


@pytest.mark.parametrize("kind", ["scenario", "initialization", "bool_seed", "economics", "limits"])
def test_genesis_metadata_and_exact_nested_types_precede_prices(monkeypatch, kind):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert build(tape, account, proposal).budget_decision.snapshot_age_ns == 0
    if kind == "scenario":
        account = changed(account, scenario_id="real-account")
    elif kind == "initialization":
        account = changed(account, seed=replace(account.seed, initialized_at_ns=START + 1))
    elif kind == "bool_seed":
        account = changed(account, seed=changed(account.seed, initial_balance_usd_micros=True))
    elif kind == "economics":
        account = changed(
            account, economics=changed(account.economics, entry_fee_usd_micros_per_contract=True)
        )
    else:
        account = changed(account, limits=changed(account.limits, max_snapshot_age_ns=True))
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleEntryDriverError):
        driver.build_single_entry_plan(tape, account, proposal, **args)


@pytest.mark.parametrize(
    "field,value",
    [
        ("publication_id", True),
        ("publication_id", StrSubclass("pub-1")),
        ("publication_id", "bad/id"),
        ("published_cursor", True),
        ("published_cursor", IntSubclass(0)),
        ("published_cursor", -1),
        ("published_cursor", 4),
        ("received_at_ns", True),
        ("received_at_ns", IntSubclass(PUB)),
        ("received_at_ns", START - 1),
        ("received_at_ns", END),
    ],
    ids=lambda value: safe_id(value),
)
def test_publication_scalars_refuse_before_prices_with_matching_full_pin(monkeypatch, field, value):
    tape, account, proposal = fixture(), genesis(), declaration()
    assert build(tape, account, proposal).publication.published_cursor == 0
    tape = changed(tape, publications=(changed(tape.publications[0], **{field: value}),))
    args = arguments(tape, account, proposal)
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleEntryDriverError):
        driver.build_single_entry_plan(tape, account, proposal, **args)


def test_publication_exact_type_precedes_quote_prices(monkeypatch):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert build(tape, account, proposal).publication.publication_id == "pub-1"
    subclass = type("PublicationSubclass", (native.NativePublication,), {})
    publication = object.__new__(subclass)
    for field in fields(native.NativePublication):
        object.__setattr__(publication, field.name, getattr(tape.publications[0], field.name))
    tape = changed(tape, publications=(publication,))
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleEntryDriverError):
        driver.build_single_entry_plan(tape, account, proposal, **args)


@pytest.mark.parametrize("where", ["fixture", "genesis", "declaration"])
@pytest.mark.parametrize("kind", ["subclass", "missing", "mapping"])
def test_exact_top_types_and_required_fields_are_consumer_guards(monkeypatch, where, kind):
    tape, account, proposal = fixture(), genesis(), declaration()
    values = {"fixture": tape, "genesis": account, "declaration": proposal}
    args = arguments(tape, account, proposal)
    assert build(tape, account, proposal).plan_sha256
    value = values[where]
    if kind == "mapping":
        bad = asdict(value)
    elif kind == "subclass":
        subclass = type("SyntheticSubclass", (type(value),), {})
        bad = object.__new__(subclass)
        for field in fields(value):
            object.__setattr__(bad, field.name, getattr(value, field.name))
    else:
        bad = changed(value)
        object.__delattr__(bad, fields(value)[0].name)
    values[where] = bad
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)
    with pytest.raises(driver.SingleEntryDriverError):
        driver.build_single_entry_plan(
            values["fixture"], values["genesis"], values["declaration"], **args
        )


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_strict_eighteen_second_end_buffer_with_valid_matching_context(delta):
    tape = fixture((quote(PUB), quote(READY)), end=PUB + 18_000_000_000 + delta)
    account, proposal = genesis(), declaration()
    args = arguments(tape, account, proposal)
    if delta == 1:
        assert build(tape, account, proposal).execution_outcome == "constructed_entry_receipt"
    else:
        with pytest.raises(driver.SingleEntryDriverError):
            driver.build_single_entry_plan(tape, account, proposal, **args)


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
    ids=lambda value: safe_id(value),
)
def test_malformed_quotes_refuse_with_independently_matching_full_fixture_pin(field, value):
    tape, account, proposal = fixture(), genesis(), declaration()
    assert build(tape, account, proposal).execution_outcome == "constructed_entry_receipt"
    rows = list(tape.quotes)
    rows[2] = changed(rows[2], **{field: value})
    tape = changed(tape, quotes=tuple(rows))
    with pytest.raises(driver.SingleEntryDriverError):
        driver.build_single_entry_plan(
            tape, account, proposal, **arguments(tape, account, proposal)
        )


@pytest.mark.parametrize(
    "kind", ["omit", "reorder", "changed_price", "changed_time", "changed_pub"]
)
def test_retained_original_complete_input_pin_prevents_omission_reordering_or_changes(kind):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    original = build(tape, account, proposal)
    if kind == "omit":
        tape = changed(tape, quotes=tape.quotes[:-1])
    elif kind == "reorder":
        tape = changed(tape, quotes=(tape.quotes[1], tape.quotes[0], *tape.quotes[2:]))
    elif kind == "changed_price":
        tape = changed(tape, quotes=(*tape.quotes[:2], quote(READY, PRICE + TICK), tape.quotes[3]))
    elif kind == "changed_time":
        tape = changed(tape, quotes=(*tape.quotes[:3], quote(DEADLINE + 2)))
    else:
        tape = changed(tape, publications=(changed(tape.publications[0], published_cursor=1),))
    with pytest.raises(driver.SingleEntryDriverError):
        driver.verify_single_entry_plan(
            tape, account, proposal, **args, expected_plan_sha256=original.plan_sha256
        )


def test_first_cursor_publication_guard_has_matching_pin_not_wrong_pin():
    tape, account, proposal = fixture(), genesis(), declaration()
    assert build(tape, account, proposal).publication.published_cursor == 0
    tape = changed(tape, publications=(changed(tape.publications[0], published_cursor=1),))
    with pytest.raises(driver.SingleEntryDriverError):
        driver.build_single_entry_plan(
            tape, account, proposal, **arguments(tape, account, proposal)
        )


def test_maximum_complete_128_quote_audit_and_rebuild_are_instrumented(monkeypatch):
    tape = fixture((quote(PUB),) * 128)
    account, proposal = genesis(), declaration()
    args = arguments(tape, account, proposal)
    calls = []
    original = native.consume_next
    inspected = 0
    quote_fields = native._quote_fields

    def observed(*args, **kwargs):
        value = original(*args, **kwargs)
        calls.append(value.native_cursor)
        return value

    def inspected_quote(*args, **kwargs):
        nonlocal inspected
        inspected += 1
        return quote_fields(*args, **kwargs)

    monkeypatch.setattr(native, "consume_next", observed)
    monkeypatch.setattr(native, "_quote_fields", inspected_quote)
    began = time.perf_counter()
    result = driver.build_single_entry_plan(tape, account, proposal, **args)
    assert calls == list(range(128))
    assert 128 <= inspected <= 8 * 128**2
    assert result.terminal_native_prefix == prefix_oracle(tape, 128)
    assert len(result.quote_audit) == 128 and result.execution_outcome == "constructed_timeout"
    calls.clear()
    inspected = 0
    rebuilt = driver.verify_single_entry_plan(
        tape, account, proposal, **args, expected_plan_sha256=result.plan_sha256
    )
    assert calls == list(range(128)) and rebuilt == result
    assert 128 <= inspected <= 8 * 128**2
    content = digest(
        {
            "version": "six_e_native_prefix_v1",
            "kind": "consumed_metadata_seed",
            "metadata": metadata(tape),
        }
    )
    for cursor, (quote_row, audit) in enumerate(zip(tape.quotes, result.quote_audit, strict=True)):
        content = digest(
            {
                "version": "six_e_native_prefix_v1",
                "kind": "consumed_quote",
                "previous_sha256": content,
                "native_cursor": cursor,
                "quote": [quote_row.received_at_ns, quote_row.bid_nano, quote_row.ask_nano],
            }
        )
        assert asdict(audit) == {
            "cursor": cursor,
            "received_at_ns": quote_row.received_at_ns,
            "consumed_count": cursor + 1,
            "consumed_content_sha256": content,
        }
    assert time.perf_counter() - began < 30  # Generous fixture bound, not trading latency.


def test_defensive_result_cap_is_pre_hash_and_does_not_change_fixed_protocol(monkeypatch):
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
    assert driver.build_single_entry_plan(tape, account, proposal, **args) == result
    monkeypatch.setattr(driver, "MAX_RESULT_BYTES", length - 1)
    with pytest.raises(driver.SingleEntryDriverError):
        driver.build_single_entry_plan(tape, account, proposal, **args)


@pytest.mark.parametrize("cap, value", [("MAX_DRIVER_QUOTES", 3), ("MAX_DRIVER_PUBLICATIONS", 0)])
def test_defensive_runtime_caps_precede_price_and_keep_versioned_identity(monkeypatch, cap, value):
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
    with pytest.raises(driver.SingleEntryDriverError):
        driver.build_single_entry_plan(tape, account, proposal, **args)


@pytest.mark.parametrize("cap", [1, 2])
def test_defensive_accounting_cap_returns_no_successful_partial_plan(monkeypatch, cap):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    assert len(build(tape, account, proposal).records) == 3
    before = canonical([asdict(tape), asdict(account), asdict(proposal)])
    monkeypatch.setattr(driver, "MAX_ACCOUNTING_RECORDS", cap)
    assert (
        driver.declaration_sha256(
            proposal, fixture_sha256=fixture_pin(tape), genesis_sha256=genesis_pin(account)
        )
        == args["expected_declaration_sha256"]
    )
    with pytest.raises(driver.SingleEntryDriverError):
        driver.build_single_entry_plan(tape, account, proposal, **args)
    assert canonical([asdict(tape), asdict(account), asdict(proposal)]) == before
    if cap == 2:
        denied = build(tape, genesis(balance=134), proposal)
        assert len(denied.records) == 2 and denied.execution_outcome == "no_pending_entry"


def test_repeat_calls_are_pure_frozen_not_persistent_exactly_once_or_trading():
    tape, account, proposal = fixture(), genesis(), declaration()
    before = canonical([asdict(tape), asdict(account), asdict(proposal)])
    first, second = build(tape, account, proposal), build(tape, account, proposal)
    assert first == second and first is not second
    assert canonical([asdict(tape), asdict(account), asdict(proposal)]) == before
    values = [
        proposal,
        first,
        first.quote_audit[0],
        first.record_links[0],
        first.publication,
        first.terminal_native_prefix,
        first.terminal_accounting_state,
    ]
    for value in values:
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)
    assert first.authority_flags == assessment.AUTHORITY_FLAGS
    assert all(flag is False for _, flag in first.authority_flags)
    assert first.terminal_accounting_state.complete_declared_net_return_usd_micros is None


def test_pure_driver_has_no_external_io_clock_process_or_exit_hooks(monkeypatch):
    tape, account, proposal = fixture(), genesis(), declaration()
    args = arguments(tape, account, proposal)
    expected = build(tape, account, proposal)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)
    monkeypatch.setattr(time, "perf_counter", forbidden)
    assert driver.build_single_entry_plan(tape, account, proposal, **args) == expected
    assert (
        driver.verify_single_entry_plan(
            tape, account, proposal, **args, expected_plan_sha256=expected.plan_sha256
        )
        == expected
    )


def test_source_imports_are_only_standard_library_and_four_held_pure_modules():
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
