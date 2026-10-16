"""Pure synthetic paired assessments, not admission or deadline authority.

Reconstructs complete externally retained hypothetical accounting and native
visibility. Never appends records, changes cash/reserves, generates receipts,
selects policy, stamps outcomes or accesses files, clocks, models or orders.
Existing accounting history is constructed, not linked to native quote history.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields, replace

from ai_trader.research import six_e_declared_admission as admission
from ai_trader.research import six_e_entry_budget as budget
from ai_trader.research import six_e_native_prefix as native

VERSION = "six_e_native_admission_assessment_v1"
MAX_ACCOUNTING_RECORDS, MAX_LINK_BYTES = 128, 256 * 1024
BUDGET_STATUS = "constructed_native_budget_assessment_not_authenticated"
DEADLINE_STATUS = "constructed_native_deadline_assessment_not_authenticated"
SUPPORTED_CONTRACTS = ("6EM5", "6EU5", "6EZ5", "6EH6")
AUTHORITY_FLAGS = tuple(
    sorted(
        {
            **dict(native.AUTHORITY_FLAGS),
            **dict(admission.AUTHORITY_FLAGS),
            "native_accounting_history_verified": False,
            "original_strategy_selection_verified": False,
            "timer_elapsed_verified": False,
            "timeout_authorized": False,
            "accounting_transition_authorized": False,
            "cross_call_continuity_authenticated": False,
            "absence_of_eligible_fill_verified": False,
            "complete_decision_quote_audit_verified": False,
        }.items()
    )
)


class NativeAdmissionAssessmentError(ValueError):
    """Malformed, conflicting or unsupported synthetic paired expectations."""


def _require(condition, message):
    if not condition:
        raise NativeAdmissionAssessmentError(message)


def _typed(value, cls):
    _require(type(value) is cls, f"Exact {cls.__name__} required")
    _require(all(hasattr(value, field.name) for field in fields(cls)), "Incomplete typed object")


def _synthetic(value):
    native._identifier(value)
    _require(
        value.startswith("synthetic-") and len(value) > 10,
        "Explicit nonempty synthetic session and scenario labels required",
    )


@dataclass(frozen=True, slots=True)
class NativeBudgetAssessment:
    version: str
    status: str
    fixture_sha256: str
    genesis_sha256: str
    native_prefix: native.NativePrefix
    accounting_state: admission.DeclaredAdmissionState
    publication: native.PublicationWitness
    budget_decision: budget.DeclaredBudgetDecision
    link_sha256: str
    authority_flags: tuple[tuple[str, bool], ...]


@dataclass(frozen=True, slots=True)
class NativeDeadlineAssessment:
    version: str
    status: str
    fixture_sha256: str
    genesis_sha256: str
    native_prefix: native.NativePrefix
    accounting_state: admission.DeclaredAdmissionState
    liability_kind: str
    liability_id: str
    contract: str
    ready_at_ns: int
    deadline_ns: int
    boundary: native.ClosedNativeBoundary
    link_sha256: str
    authority_flags: tuple[tuple[str, bool], ...]


def _preflight(
    fixture, genesis, records, fixture_pin, native_prefix, genesis_pin, accounting_prefix
):
    # These checks must precede either reconstruction and its quote/receipt prices.
    _typed(fixture, native.NativeFixture)
    _typed(genesis, admission.DeclaredAdmissionGenesis)
    _typed(native_prefix, native.NativePrefix)
    _typed(accounting_prefix, admission.DeclaredPrefix)
    native._pin(fixture_pin)
    native._pin(genesis_pin)
    _require(
        type(records) is tuple and len(records) <= MAX_ACCOUNTING_RECORDS,
        "Complete immutable accounting tuple exceeds local bound",
    )
    _synthetic(fixture.source_session)
    _synthetic(genesis.scenario_id)
    native._metadata_fields(fixture)
    _require(fixture.contract in SUPPORTED_CONTRACTS, "Held supported contract required")
    _require(
        type(fixture.quotes) is tuple and len(fixture.quotes) <= native.MAX_QUOTES,
        "Complete bounded immutable native quote tuple required",
    )
    _require(
        type(fixture.publications) is tuple
        and len(fixture.publications) <= native.MAX_PUBLICATIONS,
        "Complete bounded immutable native publication tuple required",
    )
    native._prefix_fields(native_prefix)
    replace(accounting_prefix)  # Revalidate exact scalar schema, never record prices.
    _require(
        accounting_prefix.sequence == len(records),
        "Retained accounting sequence must cover the complete supplied tuple",
    )
    _require(
        native_prefix.total_quotes == len(fixture.quotes)
        and native_prefix.total_publications == len(fixture.publications)
        and native_prefix.consumed_count <= len(fixture.quotes),
        "Retained native counts must cover the complete supplied input",
    )
    _require(
        native_prefix.fixture_sha256 == fixture_pin
        and all(
            getattr(native_prefix, name) == getattr(fixture, name)
            for name in ("source_session", "contract", "source_sha256", "start_ns", "end_ns")
        ),
        "Retained native fixture identity and metadata differ",
    )


def _linked(result):
    body = asdict(result)
    del body["link_sha256"]
    raw = json.dumps(
        body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    _require(len(raw) <= MAX_LINK_BYTES, "Complete canonical assessment link exceeds byte bound")
    return replace(result, link_sha256=hashlib.sha256(raw).hexdigest())


def assess_publication_budget(
    fixture: native.NativeFixture,
    genesis: admission.DeclaredAdmissionGenesis,
    records: tuple[admission.DeclaredRecord, ...],
    *,
    expected_fixture_sha256: str,
    expected_native_prefix: native.NativePrefix,
    expected_genesis_sha256: str,
    expected_accounting_prefix: admission.DeclaredPrefix,
    publication_id: str,
) -> NativeBudgetAssessment:
    """Explain first-cursor affordability without advancing either accounting or time."""
    try:
        _preflight(
            fixture,
            genesis,
            records,
            expected_fixture_sha256,
            expected_native_prefix,
            expected_genesis_sha256,
            expected_accounting_prefix,
        )
        native._identifier(publication_id)
        state = admission.reconstruct(
            genesis,
            records,
            expected_genesis_sha256=expected_genesis_sha256,
            expected_terminal=expected_accounting_prefix,
        )
        publication = native.publication_witness(
            fixture,
            expected_fixture_sha256=expected_fixture_sha256,
            expected_prefix=expected_native_prefix,
            publication_id=publication_id,
        )
        snapshot = budget.DeclaredCapitalSnapshot(
            genesis.seed,
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
            fixture.contract,
            1,
        )
        decision = budget.assess_entry_budget(snapshot, proposal, genesis.economics, genesis.limits)
        return _linked(
            NativeBudgetAssessment(
                VERSION,
                BUDGET_STATUS,
                expected_fixture_sha256,
                expected_genesis_sha256,
                publication.prefix,
                state,
                publication,
                decision,
                "0" * 64,
                AUTHORITY_FLAGS,
            )
        )
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise NativeAdmissionAssessmentError(str(exc)) from exc


def assess_pending_deadline_boundary(
    fixture: native.NativeFixture,
    genesis: admission.DeclaredAdmissionGenesis,
    records: tuple[admission.DeclaredRecord, ...],
    *,
    expected_fixture_sha256: str,
    expected_native_prefix: native.NativePrefix,
    expected_genesis_sha256: str,
    expected_accounting_prefix: admission.DeclaredPrefix,
    expected_deadline_ns: int,
) -> NativeDeadlineAssessment:
    """Check supplied pending-deadline coverage, never absence of fills or elapsed time."""
    try:
        _preflight(
            fixture,
            genesis,
            records,
            expected_fixture_sha256,
            expected_native_prefix,
            expected_genesis_sha256,
            expected_accounting_prefix,
        )
        native._integer(expected_deadline_ns)
        state = admission.reconstruct(
            genesis,
            records,
            expected_genesis_sha256=expected_genesis_sha256,
            expected_terminal=expected_accounting_prefix,
        )
        if state.phase == "ENTRY_PENDING" and state.pending_entry is not None:
            pending = state.pending_entry
            kind, identity, contract = "entry", pending.admission_id, pending.contract
        elif (
            state.phase == "EXIT_PENDING"
            and state.pending_exit is not None
            and state.pending_exit.status == "PENDING"
            and state.position is not None
        ):
            pending = state.pending_exit
            kind, identity, contract = "exit", pending.request_id, state.position.contract
        else:
            raise NativeAdmissionAssessmentError("Original pending entry or PENDING exit required")
        ready, deadline = pending.ready_at_ns, pending.deadline_ns
        _require(expected_deadline_ns == deadline, "Retained original deadline differs")
        _require(fixture.contract == contract, "Fixture must match original liability contract")
        _require(
            fixture.start_ns <= ready <= deadline < fixture.end_ns,
            "Complete inclusive eligible interval must lie inside the supplied quote interval",
        )
        boundary = native.close_through(
            fixture,
            expected_fixture_sha256=expected_fixture_sha256,
            expected_prefix=expected_native_prefix,
            through_ns=deadline,
        )
        return _linked(
            NativeDeadlineAssessment(
                VERSION,
                DEADLINE_STATUS,
                expected_fixture_sha256,
                expected_genesis_sha256,
                boundary.prefix,
                state,
                kind,
                identity,
                contract,
                ready,
                deadline,
                boundary,
                "0" * 64,
                AUTHORITY_FLAGS,
            )
        )
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise NativeAdmissionAssessmentError(str(exc)) from exc
