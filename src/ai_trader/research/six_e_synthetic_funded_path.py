"""One complete invented funded policy path, never authenticated execution.

Walks a bounded synthetic quote fixture from one immutable declared genesis.
Supplied features, eligibility, fees, margin and crossed full-contract receipts
remain assumptions. No history, files, clocks, models, accounts or orders are
accessed, and no completed future entry/roundtrip plan is used as prior state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields, replace

from ai_trader.research import six_e_declared_admission as admission
from ai_trader.research import six_e_entry_budget as budget
from ai_trader.research import six_e_native_admission_assessment as assessment
from ai_trader.research import six_e_native_prefix as native
from ai_trader.research import six_e_synthetic_liquidity_point as point

VERSION = "six_e_synthetic_funded_path_v1"
STATUS = "constructed_funded_path_not_authenticated_execution"
MAX_QUOTES, MIN_PUBLICATIONS, MAX_PUBLICATIONS = 128, 1, 4
MAX_ACCOUNTING_RECORDS, MAX_CANONICAL_BYTES = 20, 262144
TICK_NANO, QUANTITY_CONTRACTS = 50000, 1
ENTRY_DELAY_NS, EXIT_DELAY_NS = 100000000, 100000000
ENTRY_WAIT_NS, EXIT_WAIT_NS = 1000000000, 1000000000
HOLD_NS, COOLDOWN_NS, END_BUFFER_NS = 15000000000, 10000000000, 18000000000
MIN_PUBLICATION_CADENCE_NS = 1000000000
TARGET_TICKS, STOP_TICKS, COMPARATOR_COST_TICKS = 3, -3, 1
SUPPORTED_CONTRACTS = ("6EM5", "6EU5", "6EZ5", "6EH6")
SELECTOR_PROTOCOL_SHA256 = "d85e79987b12130f4dd54e106a247e621b96dba7ab0bdf1c9c267b4295076f6e"
AUTHORITY_FLAGS = tuple(
    sorted({**dict(assessment.AUTHORITY_FLAGS), **dict(point.AUTHORITY_FLAGS)}.items())
)
_HELPER_SOURCE_PINS = (
    (
        "src/ai_trader/research/six_e_native_prefix.py",
        "ae1a7e98aec517e1aa9bcd45f869040d812cfbb19190313b240a5313dca748b5",
    ),
    (
        "src/ai_trader/research/six_e_declared_admission.py",
        "69f1850ab6f7721005b47bf798e1960d1b3081021f0e9b3bc8240aafe4da5abb",
    ),
    (
        "src/ai_trader/research/six_e_entry_budget.py",
        "be3e0b924356b1090dff802cbb8be3059aec81002d550afebc8ef1ef475b72d6",
    ),
    (
        "src/ai_trader/research/six_e_declared_economics.py",
        "d45137f63c82afcce41d4214546d5ec1a1402487e8f91f02fd90d6617e627c85",
    ),
    (
        "src/ai_trader/research/six_e_native_admission_assessment.py",
        "5810d5213ce03bf326fee97e2252dbfe197cb93400cced4fac91a80723b0fcb6",
    ),
    (
        "src/ai_trader/research/six_e_synthetic_liquidity_point.py",
        "4cba581af818c9fb9b5ad9aef876216350b4bff5e1368e2afb4355754c46b35e",
    ),
)
_IDENTIFIER_TEMPLATES = (
    ("candidate_id", "synthetic-candidate-{ordinal:04d}"),
    ("clock_event_id", "synthetic-publication-clock-{ordinal:04d}"),
    ("request_event_id", "synthetic-admission-request-{ordinal:04d}"),
    ("admission_id", "synthetic-admission-{ordinal:04d}"),
    ("entry_outcome_event_id", "synthetic-entry-outcome-{ordinal:04d}"),
    ("entry_receipt_id", "synthetic-entry-receipt-{ordinal:04d}"),
    ("exit_request_event_id", "synthetic-exit-request-{ordinal:04d}"),
    ("exit_request_id", "synthetic-exit-{ordinal:04d}"),
    ("exit_outcome_event_id", "synthetic-exit-outcome-{ordinal:04d}"),
    ("exit_receipt_id", "synthetic-exit-receipt-{ordinal:04d}"),
)
_BUDGET_MAPPING = {
    "declared_budget_available": "entry_selected",
    "declared_budget_insufficient": "budget_denied",
    "budget_undetermined": "budget_undetermined",
}


class SyntheticFundedPathError(ValueError):
    """Malformed, conflicting or excessive complete invented context."""


def _require(condition, message):
    if not condition:
        raise SyntheticFundedPathError(message)


def _typed(value, cls):
    _require(type(value) is cls, f"Exact {cls.__name__} required")
    _require(all(hasattr(value, field.name) for field in fields(cls)), "Complete fields required")


def _synthetic(value):
    native._identifier(value)
    _require(
        value.startswith("synthetic-") and len(value) > 10,
        "Explicit nonempty synthetic identifier required",
    )


def _canonical(value):
    raw = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    _require(len(raw) <= MAX_CANONICAL_BYTES, "Complete canonical funded-path body exceeds bound")
    return raw


def _hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class PublishedLiquidityBinding:
    publication_id: str
    eligible: bool
    point: point.SyntheticLiquidityPoint
    point_sha256: str

    def __post_init__(self):
        try:
            _binding_metadata(self)
        except (ValueError, TypeError, AttributeError, OverflowError) as exc:
            raise SyntheticFundedPathError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class FundedPathDeclaration:
    declaration_id: str
    policy_id: str
    exit_plan: str

    def __post_init__(self):
        try:
            _declaration_fields(self)
        except (ValueError, TypeError, AttributeError, OverflowError) as exc:
            raise SyntheticFundedPathError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class CandidateIdentifiers:
    candidate_id: str
    clock_event_id: str
    request_event_id: str
    admission_id: str
    entry_outcome_event_id: str
    entry_receipt_id: str
    exit_request_event_id: str
    exit_request_id: str
    exit_outcome_event_id: str
    exit_receipt_id: str


@dataclass(frozen=True, slots=True)
class PublicationAudit:
    publication: native.PublicationWitness
    eligible: bool
    end_buffer_eligible: bool
    point_sha256: str
    point_selection: point.PointSelection
    selected_direction: int
    phase_before: str
    accounting_prefix_before: admission.DeclaredPrefix
    accounting_prefix_after: admission.DeclaredPrefix
    cooldown_before_ns: int
    first_disposition: str
    candidate_ordinal: int | None
    candidate_id: str | None
    budget_decision: budget.DeclaredBudgetDecision | None
    decision_record_start: int | None
    decision_record_stop: int | None


@dataclass(frozen=True, slots=True)
class CandidateTrace:
    publication_id: str
    ordinal: int
    identities: CandidateIdentifiers
    direction: int
    side: str
    first_disposition: str
    budget_decision: budget.DeclaredBudgetDecision
    record_start: int
    record_stop: int
    entry_execution_outcome: str
    entry_outcome_cursor: int | None
    entry_outcome_at_ns: int | None
    hold_at_ns: int | None
    exit_trigger_reason: str | None
    exit_trigger_cursor: int | None
    exit_requested_at_ns: int | None
    exit_execution_outcome: str
    exit_outcome_cursor: int | None
    exit_outcome_at_ns: int | None


@dataclass(frozen=True, slots=True)
class QuoteAudit:
    cursor: int
    received_at_ns: int
    consumed_count: int
    consumed_content_sha256: str


@dataclass(frozen=True, slots=True)
class AccountingLink:
    record_index: int
    candidate_ordinal: int
    publication_id: str
    event_id: str
    record_sha256: str
    native_prefix: native.NativePrefix
    kind: str
    publication: native.PublicationWitness | None
    boundary: native.ClosedNativeBoundary | None


@dataclass(frozen=True, slots=True)
class FundedPathPlan:
    version: str
    status: str
    protocol_sha256: str
    fixture_sha256: str
    genesis_sha256: str
    bindings_sha256: str
    declaration_sha256: str
    declaration: FundedPathDeclaration
    bindings: tuple[PublishedLiquidityBinding, ...]
    publication_audit: tuple[PublicationAudit, ...]
    candidates: tuple[CandidateTrace, ...]
    records: tuple[admission.DeclaredRecord, ...]
    record_links: tuple[AccountingLink, ...]
    quote_audit: tuple[QuoteAudit, ...]
    terminal_native_prefix: native.NativePrefix
    terminal_accounting_state: admission.DeclaredAdmissionState
    terminal_cooldown_until_ns: int
    plan_sha256: str
    authority_flags: tuple[tuple[str, bool], ...]


def _binding_metadata(binding):
    _typed(binding, PublishedLiquidityBinding)
    native._pin(binding.point_sha256)
    native._identifier(binding.publication_id)
    _require(type(binding.eligible) is bool, "Exact Boolean eligibility required")
    point._point_metadata(binding.point)


def _bindings_metadata(bindings):
    _require(
        type(bindings) is tuple and MIN_PUBLICATIONS <= len(bindings) <= MAX_PUBLICATIONS,
        "Complete bounded immutable bindings required",
    )
    for binding in bindings:
        _typed(binding, PublishedLiquidityBinding)
        native._pin(binding.point_sha256)
    publications, points = set(), set()
    for binding in bindings:
        _binding_metadata(binding)
        _require(binding.publication_id not in publications, "Unique publication bindings required")
        _require(binding.point.point_id not in points, "Unique synthetic point IDs required")
        publications.add(binding.publication_id)
        points.add(binding.point.point_id)


def _declaration_fields(declaration):
    _typed(declaration, FundedPathDeclaration)
    _synthetic(declaration.declaration_id)
    _require(
        type(declaration.policy_id) is str and declaration.policy_id in point.POLICIES,
        "One exact fixed numerical policy required",
    )
    _require(
        type(declaration.exit_plan) is str
        and declaration.exit_plan in ("time_exit", "bracket_exit"),
        "One exact fixed time/bracket exit plan required",
    )


def _selector_pin():
    native._pin(SELECTOR_PROTOCOL_SHA256)
    pin = point.protocol_sha256()
    _require(pin == SELECTOR_PROTOCOL_SHA256, "Held fixed selector protocol differs")
    return pin


def _protocol():
    # Reviewed declared provenance literals, not filesystem/runtime authentication.
    for _, pin in _HELPER_SOURCE_PINS:
        native._pin(pin)
    _require(
        len(AUTHORITY_FLAGS) == 57
        and all(type(name) is str and flag is False for name, flag in AUTHORITY_FLAGS),
        "Complete exact false authority union required",
    )
    return {
        "version": VERSION,
        "status": STATUS,
        "selector_protocol_sha256": _selector_pin(),
        "helper_source_pins": dict(_HELPER_SOURCE_PINS),
        "supported_contracts": ["6EM5", "6EU5", "6EZ5", "6EH6"],
        "policies": ["cvd_follow", "liquidity_follow", "absorption_fade", "no_trade"],
        "exit_plans": ["time_exit", "bracket_exit"],
        "tick_nano": 50000,
        "entry_delay_ns": 100000000,
        "entry_wait_ns": 1000000000,
        "exit_delay_ns": 100000000,
        "exit_wait_ns": 1000000000,
        "hold_ns": 15000000000,
        "cooldown_ns": 10000000000,
        "end_buffer_ns": 18000000000,
        "min_publication_cadence_ns": 1000000000,
        "target_ticks": 3,
        "stop_ticks": -3,
        "comparator_cost_ticks": 1,
        "quantity_contracts": 1,
        "max_quotes": 128,
        "min_publications": 1,
        "max_publications": 4,
        "max_accounting_records": 20,
        "max_canonical_bytes": 262144,
        "max_fixture_end_ns": 9223372026854775807,
        "selection_order": [
            "ineligible",
            "inventory_blocked",
            "pending_entry_blocked",
            "cooldown",
            "no_signal",
            "candidate",
        ],
        "quote_order": [
            "elapsed_deadlines_and_due_hold",
            "consume_quote",
            "entry_candidate",
            "bracket_trigger",
            "exit_candidate",
            "first_cursor_publication",
        ],
        "initial_cooldown_until_ns": 0,
        "candidate_budget_mapping": {
            "declared_budget_available": "entry_selected",
            "declared_budget_insufficient": "budget_denied",
            "budget_undetermined": "budget_undetermined",
        },
        "denied_candidate_effects": "consume_ordinal_clock_request_only",
        "deadline_rule": "inclusive_quote_deadline_close_when_next_timestamp_is_greater",
        "hold_rule": "actual_entry_plus_hold_wins_equality_closed_through_hold_minus_one",
        "eof_rule": "close_original_timers_no_new_account_clock",
        "unknown_rule": "terminal_inventory_no_later_accounting_mutation",
        "accounting_seed_rule": "one_fresh_immutable_genesis_no_reseed",
        "entry_execution_rule": "first_eligible_quote_one_tick_spread_or_permanent_refusal",
        "exit_execution_rule": "first_eligible_crossed_quote_widening_retained_no_budget_gate",
        "comparator_rule": "bracket_difference_ticks_minus_one_not_an_extra_money_debit",
        "identifier_templates": dict(_IDENTIFIER_TEMPLATES),
        "authority_flags": AUTHORITY_FLAGS,
    }


def protocol_sha256() -> str:
    """Generate fixed declared protocol identity, never runtime/source-file proof."""
    try:
        return _hash(_protocol())
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise SyntheticFundedPathError(str(exc)) from exc


def bindings_sha256(bindings: tuple[PublishedLiquidityBinding, ...]) -> str:
    """Hash all ordered original bindings, not directions or refreshed expectations."""
    try:
        _bindings_metadata(bindings)
        selector_pin = _selector_pin()
        for binding in bindings:
            _require(
                point.point_sha256(binding.point) == binding.point_sha256,
                "Retained complete point differs",
            )
        return _hash(
            {
                "version": VERSION,
                "status": STATUS,
                "selector_protocol_sha256": selector_pin,
                "bindings": [asdict(binding) for binding in bindings],
            }
        )
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise SyntheticFundedPathError(str(exc)) from exc


def declaration_sha256(
    declaration: FundedPathDeclaration,
    *,
    fixture_sha256: str,
    genesis_sha256: str,
    bindings_sha256: str,
) -> str:
    """Generate a context-bound declaration pin, not validate absent original inputs."""
    try:
        for pin in (fixture_sha256, genesis_sha256, bindings_sha256):
            native._pin(pin)
        _declaration_fields(declaration)
        return _hash(
            {
                "version": VERSION,
                "status": STATUS,
                "protocol_sha256": protocol_sha256(),
                "fixture_sha256": fixture_sha256,
                "genesis_sha256": genesis_sha256,
                "bindings_sha256": bindings_sha256,
                "declaration": asdict(declaration),
            }
        )
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise SyntheticFundedPathError(str(exc)) from exc


def _interval(fixture, now):
    ready, deadline = now + admission.DELAY_NS, now + admission.DELAY_NS + admission.WAIT_NS
    native._integer(ready)
    native._integer(deadline)
    _require(
        fixture.start_ns <= now <= ready <= deadline < fixture.end_ns,
        "Complete original execution interval inside fixture required",
    )
    return ready, deadline


def _prepare(
    fixture,
    genesis,
    bindings,
    declaration,
    protocol_pin,
    fixture_pin,
    genesis_pin,
    bindings_pin,
    declaration_pin,
):
    _typed(fixture, native.NativeFixture)
    _typed(genesis, admission.DeclaredAdmissionGenesis)
    _typed(declaration, FundedPathDeclaration)
    _require(
        type(fixture.quotes) is tuple and 1 <= len(fixture.quotes) <= MAX_QUOTES,
        "Complete bounded immutable native quotes required",
    )
    _require(
        type(fixture.publications) is tuple
        and MIN_PUBLICATIONS <= len(fixture.publications) <= MAX_PUBLICATIONS,
        "Complete bounded original publications required",
    )
    _require(
        type(bindings) is tuple and len(bindings) == len(fixture.publications),
        "Exactly one binding per original publication required",
    )
    for pin in (protocol_pin, fixture_pin, genesis_pin, bindings_pin, declaration_pin):
        native._pin(pin)
    for _, pin in _HELPER_SOURCE_PINS:
        native._pin(pin)
    _bindings_metadata(bindings)  # Every point pin precedes any numeric value.
    _declaration_fields(declaration)
    native._metadata_fields(fixture)
    _synthetic(genesis.scenario_id)
    _require(fixture.contract in SUPPORTED_CONTRACTS, "Held supported dated contract required")
    seen, previous = set(), None
    for publication, binding in zip(fixture.publications, bindings, strict=True):
        native._publication_fields(publication)
        _require(
            publication.publication_id == binding.publication_id
            and publication.publication_id not in seen
            and publication.published_cursor < len(fixture.quotes)
            and fixture.start_ns <= publication.received_at_ns < fixture.end_ns,
            "Complete ordered original publication binding required",
        )
        if previous is not None:
            _require(
                publication.published_cursor > previous.published_cursor
                and publication.received_at_ns - previous.received_at_ns
                >= MIN_PUBLICATION_CADENCE_NS,
                "Original first-cursor chronology and one-second cadence required",
            )
        seen.add(publication.publication_id)
        previous = publication
    previous_time = None
    for quote in fixture.quotes:
        _typed(quote, native.NativeQuote)
        native._integer(quote.received_at_ns, fixture.start_ns, fixture.end_ns - 1)
        _require(
            previous_time is None or previous_time <= quote.received_at_ns,
            "Complete ordered native timestamp metadata required",
        )
        previous_time = quote.received_at_ns
    for publication in fixture.publications:
        cursor, now = publication.published_cursor, publication.received_at_ns
        _require(
            fixture.quotes[cursor].received_at_ns == now
            and (cursor == 0 or fixture.quotes[cursor - 1].received_at_ns < now),
            "Exact original first native cursor before price inspection required",
        )
    _require(
        fixture.end_ns <= native.MAX_INT - COOLDOWN_NS,
        "Synthetic fixture end must leave bounded outcome cooldown",
    )
    _typed(genesis.seed, admission.EconomicSeed)
    native._integer(genesis.seed.initialized_at_ns)
    _require(
        genesis.seed.initialized_at_ns == fixture.start_ns,
        "One fresh original seed at fixture start required",
    )
    _require(protocol_sha256() == protocol_pin, "Retained complete fixed protocol differs")
    for publication in fixture.publications:
        now = publication.received_at_ns
        if now < fixture.end_ns - END_BUFFER_NS:
            _, deadline = _interval(fixture, now)
            latest_hold = deadline + HOLD_NS
            native._integer(latest_hold)
            _interval(fixture, latest_hold)
    # All metadata, expectation syntax and timer bounds precede numeric contents.
    _require(admission.genesis_sha256(genesis) == genesis_pin, "Retained original genesis differs")
    _require(bindings_sha256(bindings) == bindings_pin, "Retained complete bindings differ")
    native.prepare_fixture(fixture, expected_fixture_sha256=fixture_pin)
    _require(
        declaration_sha256(
            declaration,
            fixture_sha256=fixture_pin,
            genesis_sha256=genesis_pin,
            bindings_sha256=bindings_pin,
        )
        == declaration_pin,
        "Retained context-bound declaration differs",
    )


def _identities(ordinal):
    native._integer(ordinal, 1, MAX_PUBLICATIONS)
    return CandidateIdentifiers(
        **{name: template.format(ordinal=ordinal) for name, template in _IDENTIFIER_TEMPLATES}
    )


def _bracket_reason(position, quote):
    difference = (
        quote.bid_nano - position.entry_price_nano
        if position.side == "long"
        else position.entry_price_nano - quote.ask_nano
    )
    net = difference // TICK_NANO - COMPARATOR_COST_TICKS
    return "target" if net >= TARGET_TICKS else "stop" if net <= STOP_TICKS else None


class _Walker:
    def __init__(self, fixture, genesis, bindings, declaration, fixture_pin, genesis_pin):
        self.fixture, self.genesis, self.bindings, self.declaration = (
            fixture,
            genesis,
            bindings,
            declaration,
        )
        self.fixture_pin, self.genesis_pin = fixture_pin, genesis_pin
        self.prefix = native.initial_prefix(fixture, expected_fixture_sha256=fixture_pin)
        initial = admission.DeclaredPrefix(0, genesis_pin, genesis.seed.initialized_at_ns)
        self.state = admission.reconstruct(
            genesis, (), expected_genesis_sha256=genesis_pin, expected_terminal=initial
        )
        self.records, self.links, self.audit, self.publications, self.candidates = (
            (),
            [],
            [],
            [],
            [],
        )
        self.active, self.cooldown = None, 0

    def append(self, candidate, event_id, now, payload, kind, publication=None, boundary=None):
        _require(self.state.phase != "EXIT_UNKNOWN", "UNKNOWN prohibits all accounting mutation")
        _require(len(self.records) < MAX_ACCOUNTING_RECORDS, "Complete record bound exceeded")
        record = admission.DeclaredRecord(event_id, self.state.prefix, now, now, payload)
        transition = admission.advance(
            self.genesis,
            self.records,
            record,
            expected_genesis_sha256=self.genesis_pin,
            expected_terminal=self.state.prefix,
        )
        self.links.append(
            AccountingLink(
                len(self.records),
                candidate["ordinal"],
                candidate["publication_id"],
                event_id,
                transition.state.prefix.head_sha256,
                self.prefix,
                kind,
                publication,
                boundary,
            )
        )
        self.records, self.state = transition.records, transition.state
        candidate["record_stop"] = len(self.records)
        return transition

    def close(self, through):
        return native.close_through(
            self.fixture,
            expected_fixture_sha256=self.fixture_pin,
            expected_prefix=self.prefix,
            through_ns=through,
        )

    def cooldown_at(self, now):
        self.cooldown = now + COOLDOWN_NS
        native._integer(self.cooldown)

    def publish(self, index):
        binding = self.bindings[index]
        witness = native.publication_witness(
            self.fixture,
            expected_fixture_sha256=self.fixture_pin,
            expected_prefix=self.prefix,
            publication_id=binding.publication_id,
        )
        selection = point.select_point(binding.point, expected_point_sha256=binding.point_sha256)
        direction = dict(selection.directions)[self.declaration.policy_id]
        now, before, phase, cooldown = (
            witness.received_at_ns,
            self.state.prefix,
            self.state.phase,
            self.cooldown,
        )
        end_eligible = now < self.fixture.end_ns - END_BUFFER_NS
        candidate = None
        if not binding.eligible or not end_eligible:
            disposition = "ineligible"
        elif self.state.position is not None or self.state.pending_exit is not None:
            disposition = "inventory_blocked"
        elif self.state.pending_entry is not None:
            disposition = "pending_entry_blocked"
        elif now < cooldown:
            disposition = "cooldown"
        elif direction == 0:
            disposition = "no_signal"
        else:
            ordinal = len(self.candidates) + 1
            ids = _identities(ordinal)
            candidate = {
                "publication_id": binding.publication_id,
                "ordinal": ordinal,
                "identities": ids,
                "direction": direction,
                "side": "long" if direction == 1 else "short",
                "first_disposition": None,
                "budget_decision": None,
                "record_start": len(self.records),
                "record_stop": len(self.records),
                "entry_execution_outcome": "no_pending_entry",
                "entry_outcome_cursor": None,
                "entry_outcome_at_ns": None,
                "hold_at_ns": None,
                "exit_trigger_reason": None,
                "exit_trigger_cursor": None,
                "exit_requested_at_ns": None,
                "exit_execution_outcome": "no_exit",
                "exit_outcome_cursor": None,
                "exit_outcome_at_ns": None,
            }
            self.candidates.append(candidate)
            self.append(
                candidate,
                ids.clock_event_id,
                now,
                admission.ClockAdvanced(),
                "publication",
                publication=witness,
            )
            transition = self.append(
                candidate,
                ids.request_event_id,
                now,
                admission.AdmissionRequested(
                    ids.admission_id, self.fixture.contract, candidate["side"], 1
                ),
                "publication",
                publication=witness,
            )
            decision = transition.budget_decision
            _require(
                decision is not None and decision.disposition in _BUDGET_MAPPING,
                "Unblocked candidate must have complete consistent original budget",
            )
            disposition = _BUDGET_MAPPING[decision.disposition]
            candidate["first_disposition"], candidate["budget_decision"] = disposition, decision
            if disposition == "entry_selected":
                _require(self.state.pending_entry is not None, "Selected pending entry required")
                candidate["entry_execution_outcome"] = "pending_entry"
                self.active = candidate
            else:
                _require(self.state.pending_entry is None, "Denied request cannot create liability")
        self.publications.append(
            PublicationAudit(
                witness,
                binding.eligible,
                end_eligible,
                binding.point_sha256,
                selection,
                direction,
                phase,
                before,
                self.state.prefix,
                cooldown,
                disposition,
                candidate["ordinal"] if candidate is not None else None,
                candidate["identities"].candidate_id if candidate is not None else None,
                candidate["budget_decision"] if candidate is not None else None,
                candidate["record_start"] if candidate is not None else None,
                len(self.records) if candidate is not None else None,
            )
        )

    def entry_timeout(self):
        candidate, pending = self.active, self.state.pending_entry
        boundary = self.close(pending.deadline_ns)
        self.append(
            candidate,
            candidate["identities"].entry_outcome_event_id,
            pending.deadline_ns,
            admission.EntryUnfilled(pending.admission_id, "timeout"),
            "entry_deadline_boundary",
            boundary=boundary,
        )
        candidate["entry_execution_outcome"] = "constructed_entry_timeout"
        candidate["entry_outcome_at_ns"] = pending.deadline_ns
        self.cooldown_at(pending.deadline_ns)
        self.active = None

    def entry_candidate(self, cursor, quote):
        candidate, pending = self.active, self.state.pending_entry
        ids, now = candidate["identities"], quote.received_at_ns
        if quote.ask_nano - quote.bid_nano != TICK_NANO:
            payload = admission.EntryUnfilled(pending.admission_id, "simulator_refusal")
            outcome = "simulator_spread_refusal"
        else:
            price = quote.ask_nano if pending.side == "long" else quote.bid_nano
            payload = admission.EntryReceipt(
                pending.admission_id,
                ids.entry_receipt_id,
                pending.contract,
                pending.side,
                1,
                price,
                now,
            )
            outcome = "constructed_entry_receipt"
        self.append(candidate, ids.entry_outcome_event_id, now, payload, "entry_candidate_quote")
        candidate["entry_execution_outcome"] = outcome
        candidate["entry_outcome_cursor"], candidate["entry_outcome_at_ns"] = cursor, now
        if outcome == "constructed_entry_receipt":
            candidate["hold_at_ns"] = now + HOLD_NS
            native._integer(candidate["hold_at_ns"])
            _interval(self.fixture, candidate["hold_at_ns"])
        else:
            self.cooldown_at(now)
            self.active = None

    def request_exit(self, reason, cursor=None):
        candidate = self.active
        if reason == "hold_timer":
            now, kind = candidate["hold_at_ns"], "hold_boundary"
            boundary = self.close(now - 1)
        else:
            now, kind = self.prefix.last_received_at_ns, "bracket_trigger_quote"
            boundary = None
        _interval(self.fixture, now)
        ids = candidate["identities"]
        self.append(
            candidate,
            ids.exit_request_event_id,
            now,
            admission.ExitRequested(self.state.position.admission_id, ids.exit_request_id),
            kind,
            boundary=boundary,
        )
        candidate["exit_trigger_reason"], candidate["exit_trigger_cursor"] = reason, cursor
        candidate["exit_requested_at_ns"] = now

    def exit_unknown(self):
        candidate, pending = self.active, self.state.pending_exit
        boundary = self.close(pending.deadline_ns)
        self.append(
            candidate,
            candidate["identities"].exit_outcome_event_id,
            pending.deadline_ns,
            admission.ExitUnknown(pending.request_id),
            "exit_deadline_boundary",
            boundary=boundary,
        )
        candidate["exit_execution_outcome"] = "constructed_exit_unknown"
        candidate["exit_outcome_at_ns"] = pending.deadline_ns
        self.active = None  # No later accounting mutation, including zero-value liability.

    def exit_candidate(self, cursor, quote):
        candidate, position, pending = self.active, self.state.position, self.state.pending_exit
        now, ids = quote.received_at_ns, candidate["identities"]
        price = quote.bid_nano if position.side == "long" else quote.ask_nano
        self.append(
            candidate,
            ids.exit_outcome_event_id,
            now,
            admission.ExitReceipt(
                pending.request_id, ids.exit_receipt_id, position.contract, 1, price, now
            ),
            "exit_candidate_quote",
        )
        candidate["exit_execution_outcome"] = "constructed_exit_receipt"
        candidate["exit_outcome_cursor"], candidate["exit_outcome_at_ns"] = cursor, now
        self.cooldown_at(now)
        self.active = None

    def timers(self, next_time):
        # Reevaluate after every transition: gaps may span hold and exit deadline.
        while self.state.phase != "EXIT_UNKNOWN":
            pending = self.state.pending_entry
            if pending is not None and next_time > pending.deadline_ns:
                self.entry_timeout()
            elif self.state.phase == "OPEN" and next_time >= self.active["hold_at_ns"]:
                self.request_exit("hold_timer")
            elif (
                self.state.pending_exit is not None
                and self.state.pending_exit.status == "PENDING"
                and next_time > self.state.pending_exit.deadline_ns
            ):
                self.exit_unknown()
            else:
                break

    def run(self):
        publication_index = 0
        for cursor, quote in enumerate(self.fixture.quotes):
            self.timers(quote.received_at_ns)  # Only timestamp closes prior intervals.
            consumed = native.consume_next(
                self.fixture,
                expected_fixture_sha256=self.fixture_pin,
                expected_prefix=self.prefix,
                expected_cursor=cursor,
            )
            self.prefix = consumed.prefix
            self.audit.append(
                QuoteAudit(
                    cursor,
                    quote.received_at_ns,
                    self.prefix.consumed_count,
                    self.prefix.consumed_content_sha256,
                )
            )
            now, pending = quote.received_at_ns, self.state.pending_entry
            if pending is not None and pending.ready_at_ns <= now <= pending.deadline_ns:
                self.entry_candidate(cursor, quote)
            if (
                self.state.phase == "OPEN"
                and self.declaration.exit_plan == "bracket_exit"
                and now < self.active["hold_at_ns"]
            ):
                reason = _bracket_reason(self.state.position, quote)
                if reason is not None:
                    self.request_exit(reason, cursor)
            pending = self.state.pending_exit
            if (
                pending is not None
                and pending.status == "PENDING"
                and pending.ready_at_ns <= now <= pending.deadline_ns
            ):
                self.exit_candidate(cursor, quote)
            if (
                publication_index < len(self.fixture.publications)
                and cursor == self.fixture.publications[publication_index].published_cursor
            ):
                self.publish(publication_index)  # Quote effects precede first-cursor audit.
                publication_index += 1
        self.timers(self.fixture.end_ns)  # Complete EOF closes original times, not a new clock.
        _require(
            self.state.phase in ("FLAT", "EXIT_UNKNOWN") and self.active is None,
            "Complete flat or terminal UNKNOWN path required",
        )
        self.check()

    def check(self):
        _require(
            len(self.audit) == self.prefix.consumed_count == len(self.fixture.quotes)
            and len(self.publications) == len(self.bindings)
            and len(self.records) == len(self.links) <= MAX_ACCOUNTING_RECORDS,
            "Complete every-quote/publication/record coverage required",
        )
        terminal = self.close(self.fixture.end_ns)
        _require(terminal.closure_kind == "complete_eof", "Complete supplied EOF required")
        for index, row in enumerate(self.audit):
            prefix = native.verify_prefix(
                self.fixture,
                expected_fixture_sha256=self.fixture_pin,
                expected_prefix=replace(
                    self.prefix,
                    consumed_count=index + 1,
                    last_cursor=index,
                    last_received_at_ns=row.received_at_ns,
                    current_timestamp_first_cursor=(self._first_timestamp_cursor(index)),
                    consumed_content_sha256=row.consumed_content_sha256,
                ),
            )
            _require(
                row.cursor == index
                and row.consumed_count == index + 1
                and row.received_at_ns == self.fixture.quotes[index].received_at_ns
                and row.consumed_content_sha256 == prefix.consumed_content_sha256,
                "Exact contiguous consumed quote audit required",
            )
        end = 0
        for ordinal, candidate in enumerate(self.candidates, 1):
            _require(
                candidate["ordinal"] == ordinal
                and candidate["identities"] == _identities(ordinal)
                and candidate["record_start"] == end,
                "Complete contiguous candidate record partition and ordinal identities required",
            )
            length = candidate["record_stop"] - candidate["record_start"]
            expected = (
                2
                if candidate["first_disposition"] != "entry_selected"
                else 5
                if candidate["entry_execution_outcome"] == "constructed_entry_receipt"
                else 3
            )
            _require(length == expected, "Complete candidate accounting range required")
            self.check_candidate(candidate)
            end = candidate["record_stop"]
        _require(end == len(self.records), "Every record must belong to exactly one candidate")
        for index, (record, link) in enumerate(zip(self.records, self.links, strict=True)):
            _require(
                link.record_index == index and link.event_id == record.event_id,
                "Exact contiguous accounting link identity required",
            )
            candidate = self.candidates[link.candidate_ordinal - 1]
            _require(
                candidate["record_start"] <= index < candidate["record_stop"]
                and link.publication_id == candidate["publication_id"],
                "Accounting link must belong to its complete originating candidate",
            )
            before = admission.reconstruct(
                self.genesis,
                self.records[:index],
                expected_genesis_sha256=self.genesis_pin,
                expected_terminal=record.expected_prefix,
            )
            after = admission.DeclaredPrefix(index + 1, link.record_sha256, record.recorded_at_ns)
            admission.reconstruct(
                self.genesis,
                self.records[: index + 1],
                expected_genesis_sha256=self.genesis_pin,
                expected_terminal=after,
            )
            prefix = native.verify_prefix(
                self.fixture,
                expected_fixture_sha256=self.fixture_pin,
                expected_prefix=link.native_prefix,
            )
            _require(prefix.last_cursor is not None, "Accounting link requires consumed quote")
            row = self.audit[prefix.last_cursor]
            _require(
                row.received_at_ns == prefix.last_received_at_ns
                and row.consumed_count == prefix.consumed_count
                and row.consumed_content_sha256 == prefix.consumed_content_sha256,
                "Record link must match exact consumed quote audit",
            )
            self.check_link(record, link, before, candidate)
        _require(
            admission.reconstruct(
                self.genesis,
                self.records,
                expected_genesis_sha256=self.genesis_pin,
                expected_terminal=self.state.prefix,
            )
            == self.state,
            "Every complete terminal accounting field must reconstruct",
        )

    def _first_timestamp_cursor(self, cursor):
        now = self.fixture.quotes[cursor].received_at_ns
        while cursor > 0 and self.fixture.quotes[cursor - 1].received_at_ns == now:
            cursor -= 1
        return cursor

    def check_candidate(self, candidate):
        audit = next(
            row
            for row in self.publications
            if row.publication.publication_id == candidate["publication_id"]
        )
        start = candidate["record_start"]
        _require(
            audit.candidate_ordinal == candidate["ordinal"]
            and audit.candidate_id == candidate["identities"].candidate_id
            and audit.first_disposition == candidate["first_disposition"]
            and audit.budget_decision == candidate["budget_decision"]
            and audit.selected_direction == candidate["direction"]
            and audit.decision_record_start == start
            and audit.decision_record_stop == start + 2
            and audit.accounting_prefix_before == self.records[start].expected_prefix
            and candidate["direction"] in (-1, 1)
            and candidate["side"] == ("long" if candidate["direction"] == 1 else "short"),
            "Immutable initial candidate audit and separate direction/range required",
        )
        request = self.records[start + 1]
        transition = admission.advance(
            self.genesis,
            self.records[: start + 1],
            request,
            expected_genesis_sha256=self.genesis_pin,
            expected_terminal=request.expected_prefix,
        )
        _require(
            transition.budget_decision == candidate["budget_decision"]
            and transition.state.prefix == audit.accounting_prefix_after,
            "Original post-clock budget and post-request prefix required",
        )
        outcome = candidate["entry_execution_outcome"]
        if candidate["first_disposition"] != "entry_selected":
            _require(outcome == "no_pending_entry", "Denied candidate cannot have entry execution")
        else:
            _require(
                outcome
                in (
                    "constructed_entry_receipt",
                    "simulator_spread_refusal",
                    "constructed_entry_timeout",
                ),
                "Complete selected entry outcome required",
            )
        if outcome != "constructed_entry_receipt":
            _require(
                candidate["hold_at_ns"] is None
                and candidate["exit_execution_outcome"] == "no_exit"
                and all(
                    candidate[name] is None
                    for name in (
                        "exit_trigger_reason",
                        "exit_trigger_cursor",
                        "exit_requested_at_ns",
                        "exit_outcome_cursor",
                        "exit_outcome_at_ns",
                    )
                ),
                "Unreceived candidate has no hold or exit fields",
            )
        else:
            _require(
                candidate["exit_execution_outcome"]
                in ("constructed_exit_receipt", "constructed_exit_unknown"),
                "Received entry requires complete exit outcome",
            )

    def check_link(self, record, link, before, candidate):
        payload, now, prefix, ids = (
            record.payload,
            record.recorded_at_ns,
            link.native_prefix,
            candidate["identities"],
        )
        if link.kind == "publication":
            witness = native.publication_witness(
                self.fixture,
                expected_fixture_sha256=self.fixture_pin,
                expected_prefix=prefix,
                publication_id=candidate["publication_id"],
            )
            _require(
                link.publication == witness
                and link.boundary is None
                and witness.received_at_ns == now
                and (record.event_id, type(payload))
                in (
                    (ids.clock_event_id, admission.ClockAdvanced),
                    (ids.request_event_id, admission.AdmissionRequested),
                ),
                "Original first-cursor clock/request publication link required",
            )
            return
        _require(link.publication is None, "Only publication records carry OPEN witness")
        if link.kind in ("entry_candidate_quote", "bracket_trigger_quote", "exit_candidate_quote"):
            _require(
                link.boundary is None and prefix.last_received_at_ns == now,
                "Exact consumed quote link without CLOSED boundary required",
            )
            cursor, quote = prefix.last_cursor, self.fixture.quotes[prefix.last_cursor]
            if link.kind == "entry_candidate_quote":
                pending = before.pending_entry
                _require(
                    pending is not None
                    and record.event_id == ids.entry_outcome_event_id
                    and cursor == candidate["entry_outcome_cursor"]
                    and now == candidate["entry_outcome_at_ns"]
                    and cursor == self.first_candidate(pending.ready_at_ns, pending.deadline_ns),
                    "Exact first eligible entry candidate required",
                )
                if type(payload) is admission.EntryReceipt:
                    crossed = quote.ask_nano if pending.side == "long" else quote.bid_nano
                    _require(
                        payload.receipt_id == ids.entry_receipt_id
                        and payload.price_nano == crossed
                        and quote.ask_nano - quote.bid_nano == TICK_NANO
                        and candidate["entry_execution_outcome"] == "constructed_entry_receipt"
                        and candidate["hold_at_ns"] == now + HOLD_NS,
                        "Original narrow full-contract crossed entry and actual hold required",
                    )
                else:
                    _require(
                        type(payload) is admission.EntryUnfilled
                        and payload.reason == "simulator_refusal"
                        and quote.ask_nano - quote.bid_nano != TICK_NANO
                        and candidate["entry_execution_outcome"] == "simulator_spread_refusal",
                        "First widened entry refuses permanently",
                    )
            elif link.kind == "bracket_trigger_quote":
                _require(
                    type(payload) is admission.ExitRequested
                    and record.event_id == ids.exit_request_event_id
                    and payload.request_id == ids.exit_request_id
                    and self.declaration.exit_plan == "bracket_exit"
                    and before.position is not None
                    and now < candidate["hold_at_ns"]
                    and cursor == candidate["exit_trigger_cursor"]
                    and now == candidate["exit_requested_at_ns"]
                    and candidate["exit_trigger_reason"] == _bracket_reason(before.position, quote)
                    and candidate["exit_trigger_reason"] in ("target", "stop"),
                    "Original strictly-before-hold crossed bracket trigger required",
                )
            else:
                pending, position = before.pending_exit, before.position
                crossed = quote.bid_nano if position.side == "long" else quote.ask_nano
                _require(
                    type(payload) is admission.ExitReceipt
                    and record.event_id == ids.exit_outcome_event_id
                    and payload.request_id == ids.exit_request_id
                    and payload.receipt_id == ids.exit_receipt_id
                    and payload.price_nano == crossed
                    and cursor == candidate["exit_outcome_cursor"]
                    and now == candidate["exit_outcome_at_ns"]
                    and cursor == self.first_candidate(pending.ready_at_ns, pending.deadline_ns)
                    and candidate["exit_execution_outcome"] == "constructed_exit_receipt",
                    "Original first crossed exit without spread/funding filtering required",
                )
            return
        _require(
            link.kind in ("entry_deadline_boundary", "hold_boundary", "exit_deadline_boundary")
            and link.boundary is not None
            and link.boundary.prefix == prefix,
            "Phase-specific complete CLOSED boundary link required",
        )
        if link.kind == "hold_boundary":
            _require(
                type(payload) is admission.ExitRequested
                and record.event_id == ids.exit_request_event_id
                and payload.request_id == ids.exit_request_id
                and before.position is not None
                and now == before.position.executed_at_ns + HOLD_NS == candidate["hold_at_ns"]
                and now == candidate["exit_requested_at_ns"]
                and candidate["exit_trigger_reason"] == "hold_timer"
                and candidate["exit_trigger_cursor"] is None,
                "Actual-entry hold and strict-left timer precedence required",
            )
            through = now - 1
        elif link.kind == "entry_deadline_boundary":
            pending = before.pending_entry
            _require(
                type(payload) is admission.EntryUnfilled
                and payload.reason == "timeout"
                and record.event_id == ids.entry_outcome_event_id
                and pending is not None
                and now == pending.deadline_ns == candidate["entry_outcome_at_ns"]
                and candidate["entry_outcome_cursor"] is None
                and candidate["entry_execution_outcome"] == "constructed_entry_timeout"
                and self.first_candidate(pending.ready_at_ns, pending.deadline_ns) is None,
                "Original complete no-quote entry deadline required",
            )
            through = now
        else:
            pending = before.pending_exit
            _require(
                type(payload) is admission.ExitUnknown
                and record.event_id == ids.exit_outcome_event_id
                and payload.request_id == ids.exit_request_id
                and pending is not None
                and pending.status == "PENDING"
                and now == pending.deadline_ns == candidate["exit_outcome_at_ns"]
                and candidate["exit_outcome_cursor"] is None
                and candidate["exit_execution_outcome"] == "constructed_exit_unknown"
                and self.first_candidate(pending.ready_at_ns, pending.deadline_ns) is None,
                "Original complete no-quote exit deadline and terminal liability required",
            )
            through = now
        _require(
            link.boundary
            == native.close_through(
                self.fixture,
                expected_fixture_sha256=self.fixture_pin,
                expected_prefix=prefix,
                through_ns=through,
            ),
            "Exact regenerated CLOSED deadline/strict-left hold boundary required",
        )

    def first_candidate(self, ready, deadline):
        return next(
            (
                cursor
                for cursor, quote in enumerate(self.fixture.quotes)
                if ready <= quote.received_at_ns <= deadline
            ),
            None,
        )


def build_funded_path_plan(
    fixture: native.NativeFixture,
    genesis: admission.DeclaredAdmissionGenesis,
    bindings: tuple[PublishedLiquidityBinding, ...],
    declaration: FundedPathDeclaration,
    *,
    expected_protocol_sha256: str,
    expected_fixture_sha256: str,
    expected_genesis_sha256: str,
    expected_bindings_sha256: str,
    expected_declaration_sha256: str,
) -> FundedPathPlan:
    """Build one complete bounded invented path, never trade or a successful subset."""
    try:
        _prepare(
            fixture,
            genesis,
            bindings,
            declaration,
            expected_protocol_sha256,
            expected_fixture_sha256,
            expected_genesis_sha256,
            expected_bindings_sha256,
            expected_declaration_sha256,
        )
        walker = _Walker(
            fixture,
            genesis,
            bindings,
            declaration,
            expected_fixture_sha256,
            expected_genesis_sha256,
        )
        walker.run()
        plan = FundedPathPlan(
            VERSION,
            STATUS,
            expected_protocol_sha256,
            expected_fixture_sha256,
            expected_genesis_sha256,
            expected_bindings_sha256,
            expected_declaration_sha256,
            declaration,
            bindings,
            tuple(walker.publications),
            tuple(CandidateTrace(**candidate) for candidate in walker.candidates),
            walker.records,
            tuple(walker.links),
            tuple(walker.audit),
            walker.prefix,
            walker.state,
            walker.cooldown,
            "0" * 64,
            AUTHORITY_FLAGS,
        )
        body = asdict(plan)
        del body["plan_sha256"]
        return replace(plan, plan_sha256=_hash(body))
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise SyntheticFundedPathError(str(exc)) from exc


def verify_funded_path_plan(
    fixture: native.NativeFixture,
    genesis: admission.DeclaredAdmissionGenesis,
    bindings: tuple[PublishedLiquidityBinding, ...],
    declaration: FundedPathDeclaration,
    *,
    expected_protocol_sha256: str,
    expected_fixture_sha256: str,
    expected_genesis_sha256: str,
    expected_bindings_sha256: str,
    expected_declaration_sha256: str,
    expected_plan_sha256: str,
) -> FundedPathPlan:
    """Rebuild all original inputs against a retained complete pin, never adopt a plan."""
    try:
        for pin in (
            expected_protocol_sha256,
            expected_fixture_sha256,
            expected_genesis_sha256,
            expected_bindings_sha256,
            expected_declaration_sha256,
            expected_plan_sha256,
        ):
            native._pin(pin)
        plan = build_funded_path_plan(
            fixture,
            genesis,
            bindings,
            declaration,
            expected_protocol_sha256=expected_protocol_sha256,
            expected_fixture_sha256=expected_fixture_sha256,
            expected_genesis_sha256=expected_genesis_sha256,
            expected_bindings_sha256=expected_bindings_sha256,
            expected_declaration_sha256=expected_declaration_sha256,
        )
        _require(plan.plan_sha256 == expected_plan_sha256, "Retained complete funded plan differs")
        return plan
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise SyntheticFundedPathError(str(exc)) from exc
