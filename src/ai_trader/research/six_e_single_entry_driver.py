"""One invented source-linked entry, never policy, paper or broker execution.

Contiguously consumes a complete small synthetic fixture from one original seed.
Constructed receipts assume a full contract at supplied top-of-book prices; no
size, queue or broker evidence exists. There is no clock, I/O, model, account
store, resume, exit, hold, cooldown, mark-to-market or subsequent policy action.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields, replace

from ai_trader.research import six_e_declared_admission as admission
from ai_trader.research import six_e_entry_budget as budget
from ai_trader.research import six_e_native_admission_assessment as assessment
from ai_trader.research import six_e_native_prefix as native

VERSION = "six_e_single_entry_driver_v1"
STATUS = "constructed_single_entry_plan_not_trading"
END_BUFFER_NS = 18_000_000_000
MAX_DRIVER_QUOTES, MAX_DRIVER_PUBLICATIONS = 128, 1
MAX_ACCOUNTING_RECORDS, MAX_RESULT_BYTES = 3, 64 * 1024
CLOCK_EVENT_ID = "publication-clock"
REQUEST_EVENT_ID = "admission-request"
OUTCOME_EVENT_ID = "entry-outcome"
ENTRY_RECEIPT_ID = "constructed-entry-receipt"
AUTHORITY_FLAGS = assessment.AUTHORITY_FLAGS


class SingleEntryDriverError(ValueError):
    """Malformed, conflicting or excessive complete invented context."""


def _require(condition, message):
    if not condition:
        raise SingleEntryDriverError(message)


def _typed(value, cls):
    _require(type(value) is cls, f"Exact {cls.__name__} required")
    _require(all(hasattr(value, field.name) for field in fields(cls)), "Incomplete typed object")


def _synthetic(value):
    native._identifier(value)
    _require(
        value.startswith("synthetic-") and len(value) > 10,
        "Explicit nonempty synthetic declaration/session/scenario required",
    )


def _canonical(value):
    raw = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    _require(len(raw) <= MAX_RESULT_BYTES, "Complete canonical driver body exceeds byte bound")
    return raw


@dataclass(frozen=True, slots=True)
class SingleEntryDeclaration:
    declaration_id: str
    publication_id: str
    admission_id: str
    side: str

    def __post_init__(self):
        _declaration_fields(self)


@dataclass(frozen=True, slots=True)
class QuoteAudit:
    cursor: int
    received_at_ns: int
    consumed_count: int
    consumed_content_sha256: str


@dataclass(frozen=True, slots=True)
class AccountingLink:
    record_index: int
    event_id: str
    record_sha256: str
    native_prefix: native.NativePrefix
    kind: str
    publication: native.PublicationWitness | None
    boundary: native.ClosedNativeBoundary | None


@dataclass(frozen=True, slots=True)
class SingleEntryPlan:
    version: str
    status: str
    fixture_sha256: str
    genesis_sha256: str
    declaration_sha256: str
    declaration: SingleEntryDeclaration
    publication: native.PublicationWitness
    budget_decision: budget.DeclaredBudgetDecision
    first_disposition: str
    execution_outcome: str
    outcome_cursor: int | None
    outcome_at_ns: int | None
    records: tuple[admission.DeclaredRecord, ...]
    record_links: tuple[AccountingLink, ...]
    quote_audit: tuple[QuoteAudit, ...]
    terminal_native_prefix: native.NativePrefix
    terminal_accounting_state: admission.DeclaredAdmissionState
    plan_sha256: str
    authority_flags: tuple[tuple[str, bool], ...]


def _declaration_fields(declaration):
    _typed(declaration, SingleEntryDeclaration)
    _synthetic(declaration.declaration_id)
    native._identifier(declaration.publication_id)
    native._identifier(declaration.admission_id)
    _require(
        type(declaration.side) is str and declaration.side in ("long", "short"),
        "Exact long/short declared side required",
    )


def declaration_sha256(
    declaration: SingleEntryDeclaration, *, fixture_sha256: str, genesis_sha256: str
) -> str:
    """Generate prospective local identity; never replace retained input expectations."""
    try:
        _declaration_fields(declaration)
        native._pin(fixture_sha256)
        native._pin(genesis_sha256)
        body = {
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
            "fixture_sha256": fixture_sha256,
            "genesis_sha256": genesis_sha256,
            "declaration": asdict(declaration),
        }
        return hashlib.sha256(_canonical(body)).hexdigest()
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise SingleEntryDriverError(str(exc)) from exc


def _prepare(fixture, genesis, declaration, fixture_pin, genesis_pin, declaration_pin):
    # Exact scalar identity and complete resource guards precede quote prices.
    _typed(fixture, native.NativeFixture)
    _typed(genesis, admission.DeclaredAdmissionGenesis)
    _declaration_fields(declaration)
    for pin in (fixture_pin, genesis_pin, declaration_pin):
        native._pin(pin)
    _synthetic(fixture.source_session)
    _synthetic(genesis.scenario_id)
    native._metadata_fields(fixture)
    _require(fixture.contract in assessment.SUPPORTED_CONTRACTS, "Held supported contract required")
    _require(
        type(fixture.quotes) is tuple and 1 <= len(fixture.quotes) <= MAX_DRIVER_QUOTES,
        "Complete nonempty bounded immutable quote tuple required",
    )
    _require(
        type(fixture.publications) is tuple
        and len(fixture.publications) == 1
        and len(fixture.publications) <= MAX_DRIVER_PUBLICATIONS,
        "Exactly one complete declared publication required",
    )
    publication = fixture.publications[0]
    native._publication_fields(publication)
    _require(
        publication.publication_id == declaration.publication_id
        and publication.published_cursor < len(fixture.quotes)
        and fixture.start_ns <= publication.received_at_ns < fixture.end_ns,
        "Original sole publication identity/cursor/time required",
    )
    ready = publication.received_at_ns + admission.DELAY_NS
    deadline = ready + admission.WAIT_NS
    native._integer(ready)
    native._integer(deadline)
    _require(
        publication.received_at_ns + END_BUFFER_NS < fixture.end_ns
        and fixture.start_ns <= ready <= deadline < fixture.end_ns,
        "Strict original end buffer and complete inclusive entry interval required",
    )
    _typed(genesis.seed, admission.EconomicSeed)
    replace(genesis.seed)
    _require(
        genesis.seed.initialized_at_ns == fixture.start_ns, "Fresh seed at fixture start required"
    )
    _require(admission.genesis_sha256(genesis) == genesis_pin, "Retained original genesis differs")
    _require(
        declaration_sha256(declaration, fixture_sha256=fixture_pin, genesis_sha256=genesis_pin)
        == declaration_pin,
        "Retained prospective declaration differs",
    )
    native.prepare_fixture(fixture, expected_fixture_sha256=fixture_pin)


class _Driver:
    def __init__(self, fixture, genesis, declaration, fixture_pin, genesis_pin):
        self.fixture, self.genesis, self.declaration = fixture, genesis, declaration
        self.fixture_pin, self.genesis_pin = fixture_pin, genesis_pin
        self.prefix = native.initial_prefix(fixture, expected_fixture_sha256=fixture_pin)
        initial = admission.DeclaredPrefix(0, genesis_pin, genesis.seed.initialized_at_ns)
        self.state = admission.reconstruct(
            genesis, (), expected_genesis_sha256=genesis_pin, expected_terminal=initial
        )
        self.records, self.links, self.audit = (), (), ()
        self.publication, self.decision = None, None
        self.outcome, self.outcome_cursor, self.outcome_at = None, None, None

    def append(self, event_id, now, payload, kind, publication=None, boundary=None):
        _require(len(self.records) < MAX_ACCOUNTING_RECORDS, "Complete accounting bound exceeded")
        record = admission.DeclaredRecord(event_id, self.state.prefix, now, now, payload)
        transition = admission.advance(
            self.genesis,
            self.records,
            record,
            expected_genesis_sha256=self.genesis_pin,
            expected_terminal=self.state.prefix,
        )
        link = AccountingLink(
            len(self.records),
            event_id,
            transition.state.prefix.head_sha256,
            self.prefix,
            kind,
            publication,
            boundary,
        )
        self.records, self.state = transition.records, transition.state
        self.links += (link,)
        return transition

    def publish(self):
        declaration = self.declaration
        self.publication = native.publication_witness(
            self.fixture,
            expected_fixture_sha256=self.fixture_pin,
            expected_prefix=self.prefix,
            publication_id=declaration.publication_id,
        )
        now = self.publication.received_at_ns
        self.append(CLOCK_EVENT_ID, now, admission.ClockAdvanced(), "publication", self.publication)
        transition = self.append(
            REQUEST_EVENT_ID,
            now,
            admission.AdmissionRequested(
                declaration.admission_id, self.fixture.contract, declaration.side, 1
            ),
            "publication",
            self.publication,
        )
        self.decision = transition.budget_decision  # Sequence-one, never the pending snapshot.
        _require(self.decision is not None, "Original admission budget decision required")
        if self.state.pending_entry is None:
            self.outcome = "no_pending_entry"

    def timeout(self):
        pending = self.state.pending_entry
        boundary = native.close_through(
            self.fixture,
            expected_fixture_sha256=self.fixture_pin,
            expected_prefix=self.prefix,
            through_ns=pending.deadline_ns,
        )
        self.append(
            OUTCOME_EVENT_ID,
            pending.deadline_ns,
            admission.EntryUnfilled(pending.admission_id, "timeout"),
            "deadline_boundary",
            boundary=boundary,
        )
        self.outcome, self.outcome_cursor, self.outcome_at = (
            "constructed_timeout",
            None,
            pending.deadline_ns,
        )

    def candidate(self, cursor, quote):
        now, pending = quote.received_at_ns, self.state.pending_entry
        if quote.ask_nano - quote.bid_nano != native.TICK_NANO:
            payload = admission.EntryUnfilled(pending.admission_id, "simulator_refusal")
            outcome = "simulator_spread_refusal"
        else:
            price = quote.ask_nano if pending.side == "long" else quote.bid_nano
            payload = admission.EntryReceipt(
                pending.admission_id,
                ENTRY_RECEIPT_ID,
                pending.contract,
                pending.side,
                1,
                price,
                now,
            )
            outcome = "constructed_entry_receipt"
        self.append(OUTCOME_EVENT_ID, now, payload, "candidate_quote")
        self.outcome, self.outcome_cursor, self.outcome_at = outcome, cursor, now

    def run(self):
        publication_cursor = self.fixture.publications[0].published_cursor
        for cursor, quote in enumerate(self.fixture.quotes):
            pending = self.state.pending_entry
            if pending is not None and quote.received_at_ns > pending.deadline_ns:
                self.timeout()  # Only next timestamp is used, before later prices are consumed.
            consumed = native.consume_next(
                self.fixture,
                expected_fixture_sha256=self.fixture_pin,
                expected_prefix=self.prefix,
                expected_cursor=cursor,
            )
            self.prefix = consumed.prefix
            self.audit += (
                QuoteAudit(
                    cursor,
                    consumed.quote.received_at_ns,
                    self.prefix.consumed_count,
                    self.prefix.consumed_content_sha256,
                ),
            )
            if cursor == publication_cursor:
                self.publish()  # Immediately after first row, before equal-time suffix.
            pending = self.state.pending_entry
            if (
                pending is not None
                and pending.ready_at_ns <= consumed.quote.received_at_ns <= pending.deadline_ns
            ):
                self.candidate(cursor, consumed.quote)
        if self.state.pending_entry is not None:
            self.timeout()  # Complete pinned EOF, not a real elapsed-time assertion.
        _require(
            self.publication is not None and self.decision is not None and self.outcome is not None,
            "Complete publication and separated outcome required",
        )
        self.check_links()

    def check_links(self):
        _require(
            len(self.audit) == len(self.fixture.quotes) == self.prefix.consumed_count,
            "Every complete native quote required",
        )
        _require(
            len(self.records) == len(self.links) <= MAX_ACCOUNTING_RECORDS,
            "Complete one-for-one accounting links required",
        )
        for index, (record, link) in enumerate(zip(self.records, self.links, strict=True)):
            _require(
                link.record_index == index and link.event_id == record.event_id,
                "Exact contiguous record identity required",
            )
            terminal = admission.DeclaredPrefix(
                index + 1, link.record_sha256, record.complete_through_ns
            )
            admission.reconstruct(
                self.genesis,
                self.records[: index + 1],
                expected_genesis_sha256=self.genesis_pin,
                expected_terminal=terminal,
            )
            prefix = native.verify_prefix(
                self.fixture,
                expected_fixture_sha256=self.fixture_pin,
                expected_prefix=link.native_prefix,
            )
            _require(prefix.consumed_count > 0, "Accounting link requires a consumed source row")
            row = self.audit[prefix.last_cursor]
            _require(
                row.cursor == prefix.last_cursor
                and row.received_at_ns == prefix.last_received_at_ns
                and row.consumed_count == prefix.consumed_count
                and row.consumed_content_sha256 == prefix.consumed_content_sha256,
                "Accounting link must exactly match its quote-audit row",
            )
            if link.kind == "publication":
                _require(
                    link.publication == self.publication
                    and link.boundary is None
                    and prefix == self.publication.prefix
                    and record.recorded_at_ns == self.publication.received_at_ns,
                    "Original first-cursor publication link required",
                )
            elif link.kind == "candidate_quote":
                _require(
                    link.publication is None
                    and link.boundary is None
                    and prefix.last_cursor == self.outcome_cursor
                    and prefix.last_received_at_ns == record.recorded_at_ns == self.outcome_at,
                    "Exact consumed candidate outcome link required",
                )
                quote = self.fixture.quotes[prefix.last_cursor]
                if type(record.payload) is admission.EntryReceipt:
                    crossed = quote.ask_nano if self.declaration.side == "long" else quote.bid_nano
                    _require(
                        record.payload.price_nano == crossed
                        and quote.ask_nano - quote.bid_nano == native.TICK_NANO,
                        "Original narrow crossed candidate required",
                    )
                else:
                    _require(
                        type(record.payload) is admission.EntryUnfilled
                        and record.payload.reason == "simulator_refusal"
                        and quote.ask_nano - quote.bid_nano != native.TICK_NANO,
                        "First widened candidate must refuse permanently",
                    )
            else:
                _require(
                    link.kind == "deadline_boundary"
                    and link.publication is None
                    and link.boundary is not None
                    and link.boundary.prefix == prefix
                    and record.recorded_at_ns == self.outcome_at == link.boundary.through_ns
                    and self.outcome_cursor is None,
                    "Original deadline boundary link required",
                )
                _require(
                    link.boundary
                    == native.close_through(
                        self.fixture,
                        expected_fixture_sha256=self.fixture_pin,
                        expected_prefix=prefix,
                        through_ns=record.recorded_at_ns,
                    ),
                    "Exact regenerated deadline boundary required",
                )
        _require(
            admission.reconstruct(
                self.genesis,
                self.records,
                expected_genesis_sha256=self.genesis_pin,
                expected_terminal=self.state.prefix,
            )
            == self.state,
            "Complete final constructed accounting reconstruction differs",
        )


def build_single_entry_plan(
    fixture: native.NativeFixture,
    genesis: admission.DeclaredAdmissionGenesis,
    declaration: SingleEntryDeclaration,
    *,
    expected_fixture_sha256: str,
    expected_genesis_sha256: str,
    expected_declaration_sha256: str,
) -> SingleEntryPlan:
    """Build one complete invented entry from retained inputs; no successful subsets."""
    try:
        _prepare(
            fixture,
            genesis,
            declaration,
            expected_fixture_sha256,
            expected_genesis_sha256,
            expected_declaration_sha256,
        )
        driver = _Driver(
            fixture, genesis, declaration, expected_fixture_sha256, expected_genesis_sha256
        )
        driver.run()
        plan = SingleEntryPlan(
            VERSION,
            STATUS,
            expected_fixture_sha256,
            expected_genesis_sha256,
            expected_declaration_sha256,
            declaration,
            driver.publication,
            driver.decision,
            driver.decision.disposition,
            driver.outcome,
            driver.outcome_cursor,
            driver.outcome_at,
            driver.records,
            driver.links,
            driver.audit,
            driver.prefix,
            driver.state,
            "0" * 64,
            AUTHORITY_FLAGS,
        )
        body = asdict(plan)
        del body["plan_sha256"]
        return replace(plan, plan_sha256=hashlib.sha256(_canonical(body)).hexdigest())
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise SingleEntryDriverError(str(exc)) from exc


def verify_single_entry_plan(
    fixture: native.NativeFixture,
    genesis: admission.DeclaredAdmissionGenesis,
    declaration: SingleEntryDeclaration,
    *,
    expected_fixture_sha256: str,
    expected_genesis_sha256: str,
    expected_declaration_sha256: str,
    expected_plan_sha256: str,
) -> SingleEntryPlan:
    """Rebuild the complete plan against original expectations, not a submitted result."""
    try:
        native._pin(expected_plan_sha256)  # Before any deep quote or outcome access.
        plan = build_single_entry_plan(
            fixture,
            genesis,
            declaration,
            expected_fixture_sha256=expected_fixture_sha256,
            expected_genesis_sha256=expected_genesis_sha256,
            expected_declaration_sha256=expected_declaration_sha256,
        )
        _require(plan.plan_sha256 == expected_plan_sha256, "Retained complete plan pin differs")
        return plan
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise SingleEntryDriverError(str(exc)) from exc
