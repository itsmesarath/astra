"""Independent constructed admission tapes; no history, policy, account or orders."""

import builtins
import hashlib
import json
import socket
import sqlite3
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, replace
from pathlib import Path

import pytest

from ai_trader.research import six_e_declared_admission as admission
from ai_trader.research import six_e_declared_economics as economics
from ai_trader.research import six_e_entry_budget as budget

START = 1_000_000_000_000
SECOND = 1_000_000_000
DELAY = SECOND // 10
WAIT = SECOND
DEADLINE = DELAY + WAIT
TICK = economics.ledger.target.TICK
PRICE = 1_000_000_000
MAX = economics.MAX_MONEY


def declared(**changes):
    return replace(
        economics.DeclaredEconomics("USD", 125, 10, 20, economics.DeclaredMargin(100, 80)),
        **changes,
    )


def limits(**changes):
    return replace(budget.DeclaredBudgetLimits(5, SECOND, None), **changes)


def genesis(balance=135, *, assumptions=None, bounds=None, **changes):
    return replace(
        admission.DeclaredAdmissionGenesis(
            "constructed-scenario",
            economics.EconomicSeed(balance, START),
            declared() if assumptions is None else assumptions,
            limits() if bounds is None else bounds,
        ),
        **changes,
    )


def poison(value, field, changed):
    object.__setattr__(value, field, changed)
    return value


class Chain:
    """Small caller-retained complete tape and witnesses, never a submitted cache."""

    def __init__(self, declaration=None):
        self.genesis = genesis() if declaration is None else declaration
        self.pin = admission.genesis_sha256(self.genesis)
        self.records = ()
        self.prefix = admission.DeclaredPrefix(0, self.pin, START)
        self.state = self.reconstruct()

    def reconstruct(self, records=None, **changes):
        arguments = {
            "expected_genesis_sha256": self.pin,
            "expected_terminal": self.prefix,
        }
        arguments.update(changes)
        return admission.reconstruct(
            self.genesis, self.records if records is None else records, **arguments
        )

    def record(self, payload, at=None, event_id=None, **changes):
        at = self.prefix.complete_through_ns if at is None else at
        record = admission.DeclaredRecord(
            f"event-{len(self.records) + 1}",
            self.prefix,
            self.prefix.complete_through_ns,
            self.prefix.complete_through_ns,
            admission.ClockAdvanced(),
        )
        # Deliberate corruption reaches the consuming API, not an eager constructor.
        for field, value in {
            "event_id": record.event_id if event_id is None else event_id,
            "recorded_at_ns": at,
            "complete_through_ns": at,
            "payload": payload,
            **changes,
        }.items():
            poison(record, field, value)
        return record

    def add(self, payload, at=None, event_id=None, **changes):
        record = self.record(payload, at, event_id, **changes)
        result = admission.advance(
            self.genesis,
            self.records,
            record,
            expected_genesis_sha256=self.pin,
            expected_terminal=self.prefix,
        )
        self.records, self.state = result.records, result.state
        self.prefix = result.state.prefix
        return result

    def refuse(self, record):
        before = deepcopy((self.records, self.state, self.prefix))
        with pytest.raises(ValueError):
            admission.advance(
                self.genesis,
                self.records,
                record,
                expected_genesis_sha256=self.pin,
                expected_terminal=self.prefix,
            )
        assert (self.records, self.state, self.prefix) == before
        assert self.reconstruct() == self.state


def request(admission_id="admission-1", contract="6EM5", side="long"):
    return admission.AdmissionRequested(admission_id, contract, side, 1)


def pending(declaration=None, side="long"):
    chain = Chain(declaration)
    result = chain.add(request(side=side))
    assert result.budget_decision.disposition == "declared_budget_available"
    return chain


def opened(declaration=None, side="long"):
    chain = pending(declaration, side)
    at = START + DELAY
    chain.add(admission.EntryReceipt("admission-1", "entry-1", "6EM5", side, 1, PRICE, at), at)
    return chain


def exiting(declaration=None, side="long"):
    chain = opened(declaration, side)
    chain.add(admission.ExitRequested("admission-1", "exit-1"))
    return chain


def close(chain, ticks=0, receipt_id="close-1"):
    at = START + 2 * DELAY
    return chain.add(
        admission.ExitReceipt("exit-1", receipt_id, "6EM5", 1, PRICE + ticks * TICK, at), at
    )


def assert_no_authority(state):
    assert state.version == "six_e_declared_admission_v1"
    assert state.status == "constructed_declared_admission_not_authenticated"
    flags = dict(state.authority_flags)
    assert flags
    assert all(value is False for value in flags.values())
    for key in (
        "trading_enabled",
        "training_eligible",
        "strategy_scoring_allowed",
        "promotion_allowed",
        "independent_holdout",
        "broker_execution_confirmed",
        "cash_balance_confirmed",
        "margin_requirement_confirmed",
        "risk_approved",
        "genesis_authenticated",
        "complete_records_authenticated",
        "receipt_provenance_authenticated",
        "execution_confirmed",
        "admission_authorized",
    ):
        assert flags[key] is False


def test_genesis_and_complete_tape_reconstruct_without_cached_state():
    chain = Chain()
    assert chain.prefix == admission.DeclaredPrefix(0, chain.pin, START)
    assert chain.state.phase == "FLAT"
    assert chain.reconstruct() == chain.state
    chain.add(admission.ClockAdvanced(), START + 1)
    first_head = chain.prefix.head_sha256
    chain.add(admission.ClockAdvanced(), START + 1)
    assert chain.prefix.sequence == 2
    assert chain.records[1].expected_prefix.sequence == 1
    assert chain.records[1].expected_prefix.head_sha256 == first_head
    assert first_head != chain.pin
    assert chain.prefix.head_sha256 != first_head
    assert chain.reconstruct() == chain.state


@pytest.mark.parametrize(
    "change",
    [
        "scenario",
        "seed_balance",
        "seed_time",
        "tick_value",
        "entry_fee",
        "exit_fee",
        "margin",
        "buffer",
        "age",
        "loss_cap",
    ],
)
def test_genesis_hash_binds_every_declared_input_and_retained_identity(change):
    original = genesis()
    changed = deepcopy(original)
    if change == "scenario":
        changed = replace(changed, scenario_id="another-scenario")
    elif change == "seed_balance":
        changed = replace(changed, seed=economics.EconomicSeed(136, START))
    elif change == "seed_time":
        changed = replace(changed, seed=economics.EconomicSeed(135, START + 1))
    elif change == "margin":
        changed = replace(changed, economics=declared(margin=economics.DeclaredMargin(101, 80)))
    elif change in ("tick_value", "entry_fee", "exit_fee"):
        field = {
            "tick_value": "tick_value_usd_micros",
            "entry_fee": "entry_fee_usd_micros_per_contract",
            "exit_fee": "exit_fee_usd_micros_per_contract",
        }[change]
        changed = replace(
            changed,
            economics=replace(changed.economics, **{field: getattr(changed.economics, field) + 1}),
        )
    else:
        field = {
            "buffer": "cash_buffer_usd_micros",
            "age": "max_snapshot_age_ns",
            "loss_cap": "max_cumulative_realization_loss_usd_micros",
        }[change]
        changed = replace(
            changed,
            limits=replace(
                changed.limits,
                **{field: 1 if change == "loss_cap" else getattr(changed.limits, field) + 1},
            ),
        )
    pin = admission.genesis_sha256(original)
    assert pin == admission.genesis_sha256(deepcopy(original))
    assert pin != admission.genesis_sha256(changed)
    with pytest.raises(ValueError):
        admission.reconstruct(
            changed,
            (),
            expected_genesis_sha256=pin,
            expected_terminal=admission.DeclaredPrefix(0, pin, START),
        )


@pytest.mark.parametrize("field", ["sequence", "head_sha256", "complete_through_ns"])
def test_exact_terminal_and_each_preceding_prefix_are_required(field):
    chain = Chain()
    chain.add(admission.ClockAdvanced(), START + 1)
    bad = replace(
        chain.prefix,
        **{field: "a" * 64 if field == "head_sha256" else getattr(chain.prefix, field) + 1},
    )
    with pytest.raises(ValueError):
        chain.reconstruct(expected_terminal=bad)
    chain.refuse(chain.record(admission.ClockAdvanced(), expected_prefix=bad))


@pytest.mark.parametrize("change", ["suffix", "first", "reverse", "duplicate", "replace", "list"])
def test_retained_terminal_detects_omissions_reordering_duplicates_and_drift(change):
    chain = Chain()
    chain.add(admission.ClockAdvanced(), START + 1)
    chain.add(admission.ClockAdvanced(), START + 2)
    records = chain.records
    if change == "suffix":
        records = records[:-1]
    elif change == "first":
        records = records[1:]
    elif change == "reverse":
        records = records[::-1]
    elif change == "duplicate":
        records = (records[0], records[0])
    elif change == "replace":
        records = (replace(records[0], event_id="renamed-event"), records[1])
    else:
        records = list(records)
    with pytest.raises(ValueError):
        chain.reconstruct(records)


def test_intentional_prefix_requires_its_own_retained_terminal_witness():
    chain = Chain()
    chain.add(admission.ClockAdvanced(), START + 1)
    old_records, old_prefix, old_state = chain.records, chain.prefix, chain.state
    chain.add(admission.ClockAdvanced(), START + 2)
    with pytest.raises(ValueError):
        chain.reconstruct(old_records)
    assert chain.reconstruct(old_records, expected_terminal=old_prefix) == old_state


def test_coherent_invented_genesis_and_fork_are_only_local_declared_consistency():
    first, second = Chain(), Chain(genesis(1000))
    first.add(admission.ClockAdvanced(), START + 1)
    second.add(admission.ClockAdvanced(), START + 1)
    assert first.pin != second.pin
    assert first.prefix.head_sha256 != second.prefix.head_sha256
    assert first.reconstruct() == first.state
    assert second.reconstruct() == second.state
    assert_no_authority(first.state)
    assert_no_authority(second.state)


@pytest.mark.parametrize(
    "balance,disposition",
    [(135, "declared_budget_available"), (134, "declared_budget_insufficient")],
)
def test_cash_equality_and_one_short_admission_are_atomic(balance, disposition):
    chain = Chain(genesis(balance))
    result = chain.add(request())
    assert result.budget_decision.disposition == disposition
    assert result.budget_decision.declared_requirement_usd_micros == 135
    assert chain.state.phase == ("ENTRY_PENDING" if balance == 135 else "FLAT")
    assert chain.prefix.sequence == 1
    assert chain.reconstruct() == chain.state


@pytest.mark.parametrize("margin", [None, economics.DeclaredMargin(0, 0)])
def test_missing_margin_is_not_declared_zero(margin):
    chain = Chain(
        genesis(
            1,
            assumptions=declared(
                entry_fee_usd_micros_per_contract=0,
                exit_fee_usd_micros_per_contract=0,
                margin=margin,
            ),
            bounds=limits(cash_buffer_usd_micros=0),
        )
    )
    result = chain.add(request())
    assert result.budget_decision.disposition == (
        "budget_undetermined" if margin is None else "declared_budget_available"
    )
    assert result.budget_decision.declared_requirement_usd_micros == (None if margin is None else 0)
    assert chain.state.phase == ("FLAT" if margin is None else "ENTRY_PENDING")


@pytest.mark.parametrize(
    "cap,disposition", [(10, "declared_budget_available"), (9, "declared_budget_insufficient")]
)
def test_proposed_entry_fee_alone_enters_initial_loss_ceiling(cap, disposition):
    chain = Chain(genesis(bounds=limits(max_cumulative_realization_loss_usd_micros=cap)))
    result = chain.add(request())
    assert result.budget_decision.disposition == disposition
    assert result.budget_decision.realization_loss_from_original_seed_usd_micros == 0
    assert result.budget_decision.hypothetical_loss_after_entry_fee_usd_micros == 10


@pytest.mark.parametrize(
    "age,disposition", [(SECOND, "declared_budget_available"), (SECOND + 1, "budget_undetermined")]
)
def test_admission_uses_preceding_frontier_including_exact_age_boundary(age, disposition):
    chain = Chain()
    result = chain.add(request(), START + age)
    assert result.budget_decision.snapshot.observed_through_ns == START
    assert result.budget_decision.snapshot_age_ns == age
    assert result.budget_decision.disposition == disposition
    assert chain.prefix.complete_through_ns == START + age


def test_stale_refusal_cannot_refresh_itself_but_next_distinct_same_time_proposal_can():
    chain = Chain()
    at = START + SECOND + 1
    first = chain.add(request(), at)
    assert first.budget_decision.disposition == "budget_undetermined"
    assert chain.state.phase == "FLAT"
    second = chain.add(request("admission-2"), at)
    assert second.budget_decision.snapshot_age_ns == 0
    assert second.budget_decision.disposition == "declared_budget_available"
    assert chain.state.phase == "ENTRY_PENDING"


@pytest.mark.parametrize("phase", ["ENTRY_PENDING", "OPEN", "EXIT_PENDING", "EXIT_UNKNOWN"])
def test_zero_commitments_do_not_erase_typed_liability_or_allow_new_contract(phase):
    declaration = genesis(
        1,
        assumptions=declared(
            entry_fee_usd_micros_per_contract=0,
            exit_fee_usd_micros_per_contract=0,
            margin=economics.DeclaredMargin(0, 0),
        ),
        bounds=limits(cash_buffer_usd_micros=0),
    )
    chain = pending(declaration) if phase == "ENTRY_PENDING" else opened(declaration)
    if phase in ("EXIT_PENDING", "EXIT_UNKNOWN"):
        chain.add(admission.ExitRequested("admission-1", "exit-1"))
    if phase == "EXIT_UNKNOWN":
        chain.add(admission.ExitUnknown("exit-1"), START + DELAY + DEADLINE)
    result = chain.add(request("admission-2", "6EU5"))
    assert result.budget_decision.disposition == "entry_blocked_by_liability"
    assert chain.state.phase == phase
    assert chain.state.complete_declared_equity_usd_micros is None
    assert chain.state.complete_declared_net_return_usd_micros is None


@pytest.mark.parametrize(
    "offset,valid", [(DELAY - 1, False), (DELAY, True), (DEADLINE, True), (DEADLINE + 1, False)]
)
def test_entry_receipt_interval_is_inclusive_and_immediate(offset, valid):
    chain = pending()
    at = START + offset
    payload = admission.EntryReceipt("admission-1", "entry-1", "6EM5", "long", 1, PRICE, at)
    if valid:
        chain.add(payload, at)
        assert chain.state.phase == "OPEN"
    else:
        chain.refuse(chain.record(payload, at))


@pytest.mark.parametrize(
    "offset,valid", [(DELAY - 1, False), (DELAY, True), (DEADLINE, True), (DEADLINE + 1, False)]
)
def test_exit_receipt_interval_is_inclusive_and_immediate(offset, valid):
    chain = exiting()
    at = START + DELAY + offset
    payload = admission.ExitReceipt("exit-1", "close-1", "6EM5", 1, PRICE, at)
    if valid:
        chain.add(payload, at)
        assert chain.state.phase == "FLAT"
    else:
        chain.refuse(chain.record(payload, at))


@pytest.mark.parametrize("phase", ["entry", "exit"])
def test_delayed_receipt_observation_is_not_retimed_into_execution(phase):
    chain = pending() if phase == "entry" else exiting()
    executed = START + (DELAY if phase == "entry" else 2 * DELAY)
    payload = (
        admission.EntryReceipt("admission-1", "entry-1", "6EM5", "long", 1, PRICE, executed)
        if phase == "entry"
        else admission.ExitReceipt("exit-1", "close-1", "6EM5", 1, PRICE, executed)
    )
    chain.refuse(chain.record(payload, executed + 1))


@pytest.mark.parametrize("phase", ["entry", "exit"])
def test_clock_deadline_equality_retains_pending_and_crossing_requires_explicit_outcome(phase):
    chain = pending() if phase == "entry" else exiting()
    deadline = START + DEADLINE + (0 if phase == "entry" else DELAY)
    chain.add(admission.ClockAdvanced(), deadline)
    assert chain.state.phase == ("ENTRY_PENDING" if phase == "entry" else "EXIT_PENDING")
    chain.refuse(chain.record(admission.ClockAdvanced(), deadline + 1))
    payload = (
        admission.EntryUnfilled("admission-1", "timeout")
        if phase == "entry"
        else admission.ExitUnknown("exit-1")
    )
    chain.add(payload, deadline)
    chain.add(admission.ClockAdvanced(), deadline + 1)
    assert chain.state.phase == ("FLAT" if phase == "entry" else "EXIT_UNKNOWN")


@pytest.mark.parametrize("phase", ["entry", "exit"])
@pytest.mark.parametrize("offset", [-1, 1])
def test_terminal_timeout_declaration_must_be_stamped_exact_deadline(phase, offset):
    chain = pending() if phase == "entry" else exiting()
    deadline = START + DEADLINE + (0 if phase == "entry" else DELAY)
    payload = (
        admission.EntryUnfilled("admission-1", "timeout")
        if phase == "entry"
        else admission.ExitUnknown("exit-1")
    )
    chain.refuse(chain.record(payload, deadline + offset))


@pytest.mark.parametrize("reason", ["timeout", "simulator_refusal"])
def test_explicit_unfilled_releases_only_pending_admission_without_fee(reason):
    chain = pending()
    chain.add(admission.EntryUnfilled("admission-1", reason), START + DEADLINE)
    assert chain.state.phase == "FLAT"
    assert chain.state.entry_fees_usd_micros == 0
    assert chain.state.exit_fees_usd_micros == 0
    assert chain.state.declared_realization_balance_usd_micros == 135
    chain.refuse(
        chain.record(
            admission.EntryReceipt(
                "admission-1", "late-entry", "6EM5", "long", 1, PRICE, START + DEADLINE
            ),
            START + DEADLINE,
        )
    )


def test_deadline_receipt_before_terminal_declaration_is_valid_but_terminal_after_fill_is_not():
    chain = pending()
    at = START + DEADLINE
    chain.add(admission.EntryReceipt("admission-1", "entry-1", "6EM5", "long", 1, PRICE, at), at)
    chain.refuse(chain.record(admission.EntryUnfilled("admission-1", "timeout"), at))
    chain.add(admission.ExitRequested("admission-1", "exit-1"), at)
    at += DEADLINE
    chain.add(admission.ExitReceipt("exit-1", "close-1", "6EM5", 1, PRICE, at), at)
    chain.refuse(chain.record(admission.ExitUnknown("exit-1"), at))


def test_unknown_carries_seed_contract_and_commitments_without_late_reconciliation():
    chain = exiting()
    at = START + DELAY + DEADLINE
    chain.add(admission.ExitUnknown("exit-1"), at)
    before = chain.state
    chain.refuse(
        chain.record(admission.ExitReceipt("exit-1", "late-close", "6EM5", 1, PRICE, at), at)
    )
    chain.refuse(chain.record(admission.ExitRequested("admission-1", "retry-exit"), at))
    chain.refuse(chain.record(admission.EntryUnfilled("admission-1", "simulator_refusal"), at))
    later = at + 86_400 * SECOND
    chain.add(admission.ClockAdvanced(), later)
    result = chain.add(request("admission-2", "6EU5"), later)
    assert result.budget_decision.disposition == "entry_blocked_by_liability"
    assert chain.state.phase == "EXIT_UNKNOWN"
    assert (
        chain.state.declared_realization_balance_usd_micros
        == before.declared_realization_balance_usd_micros
    )
    assert chain.state.entry_fees_usd_micros == 10
    assert chain.state.exit_fees_usd_micros == 0
    assert chain.genesis.seed.initial_balance_usd_micros == 135


@pytest.mark.parametrize("phase", ["FLAT", "ENTRY_PENDING", "OPEN", "EXIT_PENDING", "EXIT_UNKNOWN"])
def test_each_phase_retains_only_false_authority(phase):
    chain = Chain() if phase == "FLAT" else pending() if phase == "ENTRY_PENDING" else opened()
    if phase in ("EXIT_PENDING", "EXIT_UNKNOWN"):
        chain.add(admission.ExitRequested("admission-1", "exit-1"))
    if phase == "EXIT_UNKNOWN":
        chain.add(admission.ExitUnknown("exit-1"), START + DELAY + DEADLINE)
    assert_no_authority(chain.state)


@pytest.mark.parametrize("phase", ["entry", "exit"])
@pytest.mark.parametrize("change", ["owner", "contract", "quantity", "price", "execution_time"])
def test_matching_full_receipt_cannot_be_rebound_to_other_exposure(phase, change):
    chain = pending() if phase == "entry" else exiting()
    at = START + (DELAY if phase == "entry" else 2 * DELAY)
    payload = (
        admission.EntryReceipt("admission-1", "entry-1", "6EM5", "long", 1, PRICE, at)
        if phase == "entry"
        else admission.ExitReceipt("exit-1", "close-1", "6EM5", 1, PRICE, at)
    )
    field, value = {
        "owner": ("admission_id" if phase == "entry" else "request_id", "other-owner"),
        "contract": ("contract", "6EU5"),
        "quantity": ("quantity_contracts", 2),
        "price": ("price_nano", PRICE + 1),
        "execution_time": ("executed_at_ns", at + 1),
    }[change]
    chain.refuse(chain.record(poison(payload, field, value), at))


def test_entry_side_and_exit_intent_owner_must_match_existing_liability():
    chain = pending()
    at = START + DELAY
    chain.refuse(
        chain.record(
            admission.EntryReceipt("admission-1", "entry-1", "6EM5", "short", 1, PRICE, at), at
        )
    )
    chain = opened()
    chain.refuse(chain.record(admission.ExitRequested("other-owner", "exit-1")))
    chain = pending()
    chain.refuse(chain.record(admission.EntryUnfilled("other-owner", "timeout"), START + DEADLINE))
    chain = exiting()
    chain.refuse(chain.record(admission.ExitUnknown("other-request"), START + DELAY + DEADLINE))


@pytest.mark.parametrize("phase", ["FLAT", "ENTRY_PENDING", "OPEN", "EXIT_UNKNOWN"])
def test_exit_receipt_only_closes_matching_pending_exit(phase):
    chain = Chain() if phase == "FLAT" else pending() if phase == "ENTRY_PENDING" else opened()
    at = START + 2 * DELAY
    if phase == "EXIT_UNKNOWN":
        chain.add(admission.ExitRequested("admission-1", "exit-1"))
        at = START + DELAY + DEADLINE
        chain.add(admission.ExitUnknown("exit-1"), at)
    chain.refuse(chain.record(admission.ExitReceipt("exit-1", "close-1", "6EM5", 1, PRICE, at), at))


@pytest.mark.parametrize("renamed", [False, True])
def test_entry_receipt_replay_or_renaming_never_debits_another_fee(renamed):
    chain = opened()
    receipt = chain.records[-1].payload
    if renamed:
        receipt = replace(receipt, receipt_id="alias-entry")
    chain.refuse(chain.record(receipt, START + DELAY))
    assert chain.state.entry_fees_usd_micros == 10
    assert chain.state.declared_realization_balance_usd_micros == 125


@pytest.mark.parametrize("renamed", [False, True])
def test_exit_receipt_replay_or_renaming_never_realizes_or_debits_twice(renamed):
    chain = exiting()
    close(chain, 3)
    receipt = chain.records[-1].payload
    if renamed:
        receipt = replace(receipt, receipt_id="alias-close")
    chain.refuse(chain.record(receipt, START + 2 * DELAY))
    assert chain.state.exit_fees_usd_micros == 20
    assert chain.state.declared_realization_balance_usd_micros == 480


def test_event_ids_never_reset_even_after_clock_or_new_session():
    chain = Chain()
    chain.add(admission.ClockAdvanced(), START + 1, event_id="permanent-event")
    chain.refuse(
        chain.record(admission.ClockAdvanced(), START + 86_400 * SECOND, event_id="permanent-event")
    )


@pytest.mark.parametrize("outcome", ["refused_budget", "unfilled", "closed"])
def test_admission_ids_never_reset_after_refusal_close_day_or_contract_change(outcome):
    chain = Chain(genesis(134)) if outcome == "refused_budget" else pending()
    if outcome == "refused_budget":
        chain.add(request())
    elif outcome == "unfilled":
        chain.add(admission.EntryUnfilled("admission-1", "timeout"), START + DEADLINE)
    else:
        at = START + DELAY
        chain.add(
            admission.EntryReceipt("admission-1", "entry-1", "6EM5", "long", 1, PRICE, at), at
        )
        chain.add(admission.ExitRequested("admission-1", "exit-1"))
        close(chain, 3)
    later = START + 86_400 * SECOND
    chain.add(admission.ClockAdvanced(), later)
    chain.refuse(chain.record(request("admission-1", "6EU5"), later))


@pytest.mark.parametrize("namespace", ["receipt", "exit_request"])
def test_receipt_and_exit_request_ids_persist_across_sequential_positions(namespace):
    chain = exiting()
    close(chain, 3)
    at = START + SECOND
    chain.add(admission.ClockAdvanced(), at)
    chain.add(request("admission-2"), at)
    at += DELAY
    receipt_id = "close-1" if namespace == "receipt" else "entry-2"
    payload = admission.EntryReceipt("admission-2", receipt_id, "6EM5", "long", 1, PRICE, at)
    if namespace == "receipt":
        chain.refuse(chain.record(payload, at))
    else:
        chain.add(payload, at)
        chain.refuse(chain.record(admission.ExitRequested("admission-2", "exit-1"), at))


def test_equal_text_in_distinct_identity_namespaces_is_not_ambiguity():
    chain = Chain()
    chain.add(request("same-id"), event_id="same-id")
    at = START + DELAY
    chain.add(admission.EntryReceipt("same-id", "same-id", "6EM5", "long", 1, PRICE, at), at)
    chain.add(admission.ExitRequested("same-id", "same-id"), at)
    at += DELAY
    chain.add(admission.ExitReceipt("same-id", "different-receipt", "6EM5", 1, PRICE, at), at)
    assert chain.state.phase == "FLAT"
    assert chain.state.declared_realization_balance_usd_micros == 105


@pytest.mark.parametrize(
    "change", ["backward", "future_frontier", "lagging_frontier", "before_seed"]
)
def test_record_time_and_explicit_resulting_frontier_must_match_and_not_go_backward(change):
    chain = Chain()
    chain.add(admission.ClockAdvanced(), START + 10)
    record = chain.record(admission.ClockAdvanced(), START + 11)
    if change == "backward":
        poison(record, "recorded_at_ns", START + 9)
        poison(record, "complete_through_ns", START + 9)
    elif change == "future_frontier":
        poison(record, "complete_through_ns", START + 12)
    elif change == "lagging_frontier":
        poison(record, "complete_through_ns", START + 10)
    else:
        poison(record, "recorded_at_ns", START - 1)
        poison(record, "complete_through_ns", START - 1)
    chain.refuse(record)


@pytest.mark.parametrize("payload", [None, {}, (), "cancel", 1])
def test_only_seven_exact_typed_payloads_are_supported(payload):
    chain = Chain()
    record = poison(chain.record(admission.ClockAdvanced()), "payload", payload)
    chain.refuse(record)


@pytest.mark.parametrize(
    "target,field,value",
    [
        ("genesis", "scenario_id", "../scenario"),
        ("seed", "initial_balance_usd_micros", True),
        ("seed", "initial_balance_usd_micros", 135.0),
        ("seed", "initial_balance_usd_micros", 0),
        ("seed", "initialized_at_ns", -1),
        ("economics", "account_currency", "EUR"),
        ("economics", "tick_value_usd_micros", 0),
        ("economics", "entry_fee_usd_micros_per_contract", True),
        ("economics", "exit_fee_usd_micros_per_contract", -1),
        ("margin", "initial_usd_micros_per_contract", 79),
        ("margin", "maintenance_usd_micros_per_contract", True),
        ("limits", "cash_buffer_usd_micros", True),
        ("limits", "max_snapshot_age_ns", 1.0),
        ("limits", "max_cumulative_realization_loss_usd_micros", -1),
    ],
)
def test_poisoned_frozen_genesis_and_nested_inputs_are_revalidated(target, field, value):
    chain = Chain()
    values = {
        "genesis": chain.genesis,
        "seed": chain.genesis.seed,
        "economics": chain.genesis.economics,
        "margin": chain.genesis.economics.margin,
        "limits": chain.genesis.limits,
    }
    poison(values[target], field, value)
    with pytest.raises(ValueError):
        admission.genesis_sha256(chain.genesis)
    with pytest.raises(ValueError):
        chain.reconstruct()


@pytest.mark.parametrize(
    "target,field,value",
    [
        ("record", "event_id", "bad/event"),
        ("record", "event_id", ""),
        ("record", "recorded_at_ns", True),
        ("record", "complete_through_ns", float(START)),
        ("prefix", "sequence", True),
        ("prefix", "sequence", -1),
        ("prefix", "head_sha256", "A" * 64),
        ("prefix", "head_sha256", "a" * 63),
        ("prefix", "complete_through_ns", True),
        ("payload", "admission_id", "x" * 129),
        ("payload", "contract", "EURUSD"),
        ("payload", "side", "LONG"),
        ("payload", "quantity_contracts", True),
        ("payload", "quantity_contracts", 0),
        ("payload", "quantity_contracts", 2),
    ],
)
def test_poisoned_exact_record_prefix_and_payload_fields_refuse_before_arithmetic(
    target, field, value
):
    chain = Chain()
    record = chain.record(request())
    values = {"record": record, "prefix": record.expected_prefix, "payload": record.payload}
    poison(values[target], field, value)
    with pytest.raises(ValueError):
        admission.advance(
            chain.genesis,
            chain.records,
            record,
            expected_genesis_sha256=chain.pin,
            expected_terminal=chain.prefix,
        )


@pytest.mark.parametrize("pin", [None, "A" * 64, "a" * 63, True])
def test_expected_genesis_witness_requires_exact_canonical_sha256(pin):
    chain = Chain()
    with pytest.raises(ValueError):
        chain.reconstruct(expected_genesis_sha256=pin)


@pytest.mark.parametrize("witness", [None, {}, (0, "a" * 64, START)])
def test_terminal_witness_must_be_exact_typed_prefix(witness):
    chain = Chain()
    with pytest.raises(ValueError):
        chain.reconstruct(expected_terminal=witness)


def test_overlong_complete_tape_refuses_without_building_two_thousand_transitions():
    chain = Chain()
    record = chain.record(admission.ClockAdvanced())
    with pytest.raises(ValueError):
        chain.reconstruct((record,) * 2001)


def test_poisoned_oversized_record_is_bounded_without_accepting_arbitrary_text():
    chain = pending()
    record = chain.record(admission.EntryUnfilled("admission-1", "timeout"), START + DEADLINE)
    poison(record.payload, "reason", "x" * 8193)
    chain.refuse(record)


def test_internal_canonical_byte_guard_accepts_exact_bound_and_rejects_one_extra():
    # Internal serializer boundary only, not an arbitrary public protocol payload.
    value = "x" * (admission.MAX_RECORD_BYTES - 2)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    assert len(encoded) == admission.MAX_RECORD_BYTES
    assert admission._hash(value) == hashlib.sha256(encoded).hexdigest()
    with pytest.raises(admission.DeclaredAdmissionError, match="byte bound"):
        admission._hash(value + "x")


def test_result_and_retained_inputs_are_immutable_and_no_cash_cache_parameter_exists():
    chain = pending()
    with pytest.raises(FrozenInstanceError):
        chain.state.phase = "FLAT"
    with pytest.raises(FrozenInstanceError):
        chain.genesis.seed = economics.EconomicSeed(1000, START)
    with pytest.raises(FrozenInstanceError):
        chain.records[0].event_id = "replacement"
    with pytest.raises(TypeError):
        admission.reconstruct(
            chain.genesis,
            chain.records,
            expected_genesis_sha256=chain.pin,
            expected_terminal=chain.prefix,
            state=chain.state,
        )


def test_local_construction_and_reconstruction_are_pure_deterministic_and_unchanged(monkeypatch):
    declaration = genesis()
    original = deepcopy(asdict(declaration))

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Pure declared admission attempted filesystem, network, tape or policy access"
        )

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(Path, "open", forbidden)
        patch.setattr(sqlite3, "connect", forbidden)
        patch.setattr(socket, "create_connection", forbidden)
        patch.setattr(economics.replay, "fingerprints", forbidden)
        patch.setattr(economics.replay, "build_plan", forbidden)
        patch.setattr(economics.replay, "_freeze", forbidden)
        patch.setattr(economics, "project", forbidden)
        patch.setattr(economics.ledger, "ScenarioLedger", forbidden)
        patch.setattr(economics.replay.rules, "rules", forbidden)
        patch.setattr(economics.replay.rules.Model, "predict", forbidden)
        patch.setattr(economics.replay.study.common, "hash_file", forbidden)
        first, second = exiting(declaration), exiting(deepcopy(declaration))
        close(first, 3)
        close(second, 3)
        assert first.state == second.state
        assert first.records == second.records
        assert first.reconstruct() == first.state
    assert asdict(declaration) == original


def assert_accounting(
    chain, *, balance, gross, entry, exit_fee, entry_reserve, margin, exit_reserve
):
    """Independent arithmetic: no production accounting helper is consulted."""
    state = chain.state
    seed = chain.genesis.seed.initial_balance_usd_micros
    assert balance == seed + gross - entry - exit_fee
    assert state.declared_realization_balance_usd_micros == balance
    assert state.gross_realized_usd_micros == gross
    assert state.entry_fees_usd_micros == entry
    assert state.exit_fees_usd_micros == exit_fee
    assert state.entry_fee_reserve_usd_micros == entry_reserve
    assert state.initial_margin_commitment_usd_micros == margin
    assert state.exit_fee_reserve_usd_micros == exit_reserve
    assert state.total_commitments_usd_micros == entry_reserve + margin + exit_reserve
    assert state.available_balance_usd_micros == balance - entry_reserve - margin - exit_reserve
    assert state.realization_balance_shortfall_usd_micros == max(0, -balance)
    assert state.genesis_sha256 == chain.pin
    if state.phase == "FLAT":
        assert state.complete_declared_equity_usd_micros == balance
        assert state.complete_declared_net_return_usd_micros == balance - seed
    else:
        assert state.complete_declared_equity_usd_micros is None
        assert state.complete_declared_net_return_usd_micros is None
    assert chain.reconstruct() == state


def test_independent_lifecycle_oracle_charges_fees_once_and_consumes_matching_reserve():
    chain = Chain()
    assert_accounting(
        chain, balance=135, gross=0, entry=0, exit_fee=0, entry_reserve=0, margin=0, exit_reserve=0
    )
    chain.add(request())
    assert_accounting(
        chain,
        balance=135,
        gross=0,
        entry=0,
        exit_fee=0,
        entry_reserve=10,
        margin=100,
        exit_reserve=20,
    )
    assert chain.state.available_balance_usd_micros == 5
    assert chain.state.pending_entry.admission_id == "admission-1"
    assert chain.state.pending_entry.ready_at_ns == START + DELAY
    assert chain.state.pending_entry.deadline_ns == START + DEADLINE
    at = START + DELAY
    result = chain.add(
        admission.EntryReceipt("admission-1", "entry-1", "6EM5", "long", 1, PRICE, at), at
    )
    assert result.budget_decision is None
    assert_accounting(
        chain,
        balance=125,
        gross=0,
        entry=10,
        exit_fee=0,
        entry_reserve=0,
        margin=100,
        exit_reserve=20,
    )
    assert chain.state.available_balance_usd_micros == 5
    assert chain.state.pending_entry is None
    assert chain.state.position.admission_id == "admission-1"
    assert len(chain.state.receipt_content_sha256s) == 1
    chain.add(admission.ExitRequested("admission-1", "exit-1"), at)
    assert_accounting(
        chain,
        balance=125,
        gross=0,
        entry=10,
        exit_fee=0,
        entry_reserve=0,
        margin=100,
        exit_reserve=20,
    )
    assert chain.state.pending_exit.status == "PENDING"
    close(chain)
    assert_accounting(
        chain,
        balance=105,
        gross=0,
        entry=10,
        exit_fee=20,
        entry_reserve=0,
        margin=0,
        exit_reserve=0,
    )
    assert chain.state.pending_entry is chain.state.position is chain.state.pending_exit is None
    assert len(chain.state.receipt_content_sha256s) == 2


@pytest.mark.parametrize(
    "side,ticks,gross,balance",
    [
        ("long", 3, 375, 480),
        ("short", -3, 375, 480),
        ("long", -3, -375, -270),
        ("short", 3, -375, -270),
    ],
)
def test_signed_gross_realization_and_negative_cash_exits_ignore_entry_gates(
    side, ticks, gross, balance
):
    declaration = genesis(bounds=limits(max_cumulative_realization_loss_usd_micros=10))
    chain = opened(declaration, side)
    refused = chain.add(request("blocked-admission", "6EU5"))
    assert refused.budget_decision.disposition == "entry_blocked_by_liability"
    assert refused.budget_decision.declared_balance_less_requirement_usd_micros == -10
    chain.add(admission.ExitRequested("admission-1", "exit-1"))
    close(chain, ticks)
    assert_accounting(
        chain,
        balance=balance,
        gross=gross,
        entry=10,
        exit_fee=20,
        entry_reserve=0,
        margin=0,
        exit_reserve=0,
    )
    assert_no_authority(chain.state)
    if balance < 0:
        result = chain.add(request("after-loss", "6EU5"))
        assert result.budget_decision.disposition == "declared_budget_insufficient"
        assert result.budget_decision.realization_loss_from_original_seed_usd_micros == 405
        assert result.budget_decision.hypothetical_loss_after_entry_fee_usd_micros == 415
        assert chain.state.phase == "FLAT"
        assert chain.state.declared_realization_balance_usd_micros == -270


@pytest.mark.parametrize(
    "ceiling,disposition",
    [(39, "declared_budget_insufficient"), (40, "declared_budget_available")],
)
def test_next_day_and_contract_do_not_reset_original_seed_cumulative_fees_or_loss(
    ceiling, disposition
):
    declaration = genesis(1000, bounds=limits(max_cumulative_realization_loss_usd_micros=ceiling))
    chain = exiting(declaration)
    close(chain)
    assert_accounting(
        chain,
        balance=970,
        gross=0,
        entry=10,
        exit_fee=20,
        entry_reserve=0,
        margin=0,
        exit_reserve=0,
    )
    later = START + 86_400 * SECOND
    chain.add(admission.ClockAdvanced(), later)
    result = chain.add(request("admission-2", "6EU5"), later)
    assert result.budget_decision.realization_loss_from_original_seed_usd_micros == 30
    assert result.budget_decision.hypothetical_loss_after_entry_fee_usd_micros == 40
    assert result.budget_decision.disposition == disposition
    assert chain.state.declared_realization_balance_usd_micros == 970
    assert chain.genesis.seed.initial_balance_usd_micros == 1000


def test_unknown_keeps_single_margin_and_exit_fee_reserve_without_double_counting():
    chain = exiting()
    assert_accounting(
        chain,
        balance=125,
        gross=0,
        entry=10,
        exit_fee=0,
        entry_reserve=0,
        margin=100,
        exit_reserve=20,
    )
    chain.add(admission.ExitUnknown("exit-1"), START + DELAY + DEADLINE)
    assert_accounting(
        chain,
        balance=125,
        gross=0,
        entry=10,
        exit_fee=0,
        entry_reserve=0,
        margin=100,
        exit_reserve=20,
    )
    chain.add(admission.ClockAdvanced(), START + 86_400 * SECOND)
    assert chain.state.position.contract == "6EM5"
    assert chain.state.pending_exit.request_id == "exit-1"
    assert chain.state.pending_exit.status == "UNKNOWN"
    assert_accounting(
        chain,
        balance=125,
        gross=0,
        entry=10,
        exit_fee=0,
        entry_reserve=0,
        margin=100,
        exit_reserve=20,
    )


def test_explicit_simulator_refusal_inside_eligible_interval_is_not_a_timeout_or_broker_cancel():
    chain = pending()
    chain.add(admission.EntryUnfilled("admission-1", "simulator_refusal"), START + DELAY)
    assert_accounting(
        chain, balance=135, gross=0, entry=0, exit_fee=0, entry_reserve=0, margin=0, exit_reserve=0
    )
    assert_no_authority(chain.state)
    chain.add(request("admission-2"), START + DELAY)
    assert chain.state.phase == "ENTRY_PENDING"


@pytest.mark.parametrize(
    "case",
    [
        "single_amount",
        "commitment_sum",
        "clock_deadline",
        "gross_conversion",
        "realization_balance",
    ],
)
def test_individual_aggregate_clock_and_realization_overflow_fail_closed(case):
    if case == "single_amount":
        chain = Chain()
        poison(chain.genesis.economics, "entry_fee_usd_micros_per_contract", MAX + 1)
        with pytest.raises(ValueError):
            chain.reconstruct()
    elif case == "commitment_sum":
        chain = Chain(
            genesis(
                MAX,
                assumptions=declared(
                    entry_fee_usd_micros_per_contract=MAX,
                    exit_fee_usd_micros_per_contract=1,
                    margin=economics.DeclaredMargin(0, 0),
                ),
                bounds=limits(cash_buffer_usd_micros=0),
            )
        )
        chain.refuse(chain.record(request()))
    elif case == "clock_deadline":
        chain = Chain(genesis(bounds=limits(max_snapshot_age_ns=MAX)))
        chain.refuse(chain.record(request(), MAX))
    else:
        assumptions = declared(tick_value_usd_micros=MAX)
        chain = exiting(genesis(assumptions=assumptions))
        ticks = 2 if case == "gross_conversion" else 1
        at = START + 2 * DELAY
        chain.refuse(
            chain.record(
                admission.ExitReceipt("exit-1", "close-1", "6EM5", 1, PRICE + ticks * TICK, at), at
            )
        )


@pytest.mark.parametrize("side", ["long", "short"])
def test_negative_gross_overflow_is_rejected_without_releasing_exit(side):
    chain = exiting(genesis(assumptions=declared(tick_value_usd_micros=MAX)), side)
    ticks = -2 if side == "long" else 2
    at = START + 2 * DELAY
    chain.refuse(
        chain.record(
            admission.ExitReceipt("exit-1", "close-1", "6EM5", 1, PRICE + ticks * TICK, at), at
        )
    )
    assert chain.state.phase == "EXIT_PENDING"
    assert chain.state.exit_fees_usd_micros == 0


def test_poisoned_previous_record_is_revalidated_not_hidden_by_a_cached_terminal():
    chain = opened()
    poison(chain.records[0].payload, "quantity_contracts", 2)
    with pytest.raises(ValueError):
        chain.reconstruct()
    with pytest.raises(ValueError):
        admission.advance(
            chain.genesis,
            chain.records,
            chain.record(admission.ClockAdvanced()),
            expected_genesis_sha256=chain.pin,
            expected_terminal=chain.prefix,
        )


def test_genesis_protocol_identity_binds_version_scope_and_original_timing(monkeypatch):
    declaration = genesis()
    original = admission.genesis_sha256(declaration)
    for field, changed in (
        ("VERSION", "different-version"),
        ("STATUS", "different-scope"),
        ("DELAY_NS", DELAY + 1),
        ("WAIT_NS", WAIT + 1),
    ):
        with monkeypatch.context() as patch:
            patch.setattr(admission, field, changed)
            assert admission.genesis_sha256(declaration) != original


@pytest.mark.parametrize("changed", ["admission_id", "side", "entry_price"])
def test_exit_content_identity_binds_full_position_even_on_coherent_declared_forks(changed):
    states = []
    for alternate in (False, True):
        chain = Chain()
        admission_id = (
            "different-admission" if alternate and changed == "admission_id" else "admission-1"
        )
        side = "short" if alternate and changed == "side" else "long"
        entry_price = PRICE + TICK if alternate and changed == "entry_price" else PRICE
        chain.add(request(admission_id, side=side))
        at = START + DELAY
        chain.add(
            admission.EntryReceipt(admission_id, "entry-1", "6EM5", side, 1, entry_price, at), at
        )
        chain.add(admission.ExitRequested(admission_id, "exit-1"), at)
        close(chain)
        states.append(chain.state)
    assert states[0].genesis_sha256 == states[1].genesis_sha256
    assert states[0].receipt_content_sha256s[-1] != states[1].receipt_content_sha256s[-1]
    assert_no_authority(states[0])
    assert_no_authority(states[1])


def test_receipt_content_identity_excludes_user_receipt_id_but_chain_identity_does_not():
    first, second = exiting(), exiting()
    close(first, receipt_id="first-label")
    close(second, receipt_id="renamed-label")
    assert first.state.receipt_content_sha256s == second.state.receipt_content_sha256s
    assert first.prefix.head_sha256 != second.prefix.head_sha256
    assert (
        first.state.declared_realization_balance_usd_micros
        == second.state.declared_realization_balance_usd_micros
        == 105
    )


@pytest.mark.parametrize("target", ["genesis", "prefix", "record", "payload"])
def test_dataclass_subclasses_are_not_accepted_as_exact_protocol_types(target):
    chain = Chain()
    record = chain.record(request())
    value = {
        "genesis": chain.genesis,
        "prefix": chain.prefix,
        "record": record,
        "payload": record.payload,
    }[target]
    subtype = type("UnsupportedSubtype", (type(value),), {})
    substitute = subtype(**asdict(value)) if target == "payload" else None
    if target == "genesis":
        substitute = subtype(value.scenario_id, value.seed, value.economics, value.limits)
        with pytest.raises(ValueError):
            admission.genesis_sha256(substitute)
    elif target == "prefix":
        substitute = subtype(value.sequence, value.head_sha256, value.complete_through_ns)
        with pytest.raises(ValueError):
            chain.reconstruct(expected_terminal=substitute)
    elif target == "record":
        substitute = subtype(
            value.event_id,
            value.expected_prefix,
            value.recorded_at_ns,
            value.complete_through_ns,
            value.payload,
        )
        chain.refuse(substitute)
    else:
        chain.refuse(chain.record(substitute))


@pytest.mark.parametrize("phase", ["entry", "exit"])
@pytest.mark.parametrize("quantity", [0, 2, True, 1.0])
def test_partial_multiple_and_noninteger_receipts_do_not_charge_or_release(phase, quantity):
    chain = pending() if phase == "entry" else exiting()
    at = START + (DELAY if phase == "entry" else 2 * DELAY)
    payload = (
        admission.EntryReceipt("admission-1", "entry-1", "6EM5", "long", 1, PRICE, at)
        if phase == "entry"
        else admission.ExitReceipt("exit-1", "close-1", "6EM5", 1, PRICE, at)
    )
    poison(payload, "quantity_contracts", quantity)
    chain.refuse(chain.record(payload, at))
    assert chain.state.exit_fees_usd_micros == 0
    assert chain.state.entry_fees_usd_micros == (0 if phase == "entry" else 10)


@pytest.mark.parametrize("change", ["genesis_identity", "preceding_prefix", "backward_clock"])
def test_invalid_identity_and_clock_are_refused_before_calling_budget_assessor(monkeypatch, change):
    chain = Chain()
    record = chain.record(request())
    expected = chain.pin
    if change == "genesis_identity":
        expected = "a" * 64
    elif change == "preceding_prefix":
        poison(record, "expected_prefix", replace(chain.prefix, sequence=1))
    else:
        poison(record, "recorded_at_ns", START - 1)
        poison(record, "complete_through_ns", START - 1)

    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid prefix reached budget arithmetic")

    with monkeypatch.context() as patch:
        patch.setattr(budget, "assess_entry_budget", forbidden)
        with pytest.raises(ValueError):
            admission.advance(
                chain.genesis,
                chain.records,
                record,
                expected_genesis_sha256=expected,
                expected_terminal=chain.prefix,
            )
