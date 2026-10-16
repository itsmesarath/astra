"""One invented, source-linked entry and causal exit, never actual execution.

The complete bounded synthetic fixture is walked freshly from one declared seed.
Receipts assume one contract at supplied top-of-book prices. No depth, queue,
broker, elapsed-time, historical-policy or persisted progression evidence exists.
There is no I/O, clock, model, account store, resume or order connection.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields, replace

from ai_trader.research import six_e_declared_admission as admission
from ai_trader.research import six_e_entry_budget as budget
from ai_trader.research import six_e_native_admission_assessment as assessment
from ai_trader.research import six_e_native_prefix as native

VERSION = "six_e_single_roundtrip_driver_v1"
STATUS = "constructed_single_roundtrip_plan_not_trading"
END_BUFFER_NS, HOLD_NS = 18_000_000_000, 15_000_000_000
TARGET_TICKS, STOP_TICKS, COMPARATOR_COST_TICKS = 3, -3, 1
MAX_DRIVER_QUOTES, MAX_DRIVER_PUBLICATIONS = 128, 1
MAX_ACCOUNTING_RECORDS, MAX_RESULT_BYTES = 5, 65536
CLOCK_EVENT_ID = "publication-clock"
REQUEST_EVENT_ID = "admission-request"
ENTRY_OUTCOME_EVENT_ID = "entry-outcome"
ENTRY_RECEIPT_ID = "constructed-entry-receipt"
EXIT_REQUEST_EVENT_ID = "exit-request"
EXIT_REQUEST_ID = "constructed-exit-request"
EXIT_OUTCOME_EVENT_ID = "exit-outcome"
EXIT_RECEIPT_ID = "constructed-exit-receipt"
AUTHORITY_FLAGS = assessment.AUTHORITY_FLAGS


class SingleRoundtripDriverError(ValueError):
    """Malformed, conflicting or excessive complete invented context."""


def _require(condition, message):
    if not condition:
        raise SingleRoundtripDriverError(message)


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
class SingleRoundtripDeclaration:
    declaration_id: str
    publication_id: str
    admission_id: str
    side: str
    exit_plan: str

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
class SingleRoundtripPlan:
    version: str
    status: str
    fixture_sha256: str
    genesis_sha256: str
    declaration_sha256: str
    declaration: SingleRoundtripDeclaration
    publication: native.PublicationWitness
    budget_decision: budget.DeclaredBudgetDecision
    first_disposition: str
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
    records: tuple[admission.DeclaredRecord, ...]
    record_links: tuple[AccountingLink, ...]
    quote_audit: tuple[QuoteAudit, ...]
    terminal_native_prefix: native.NativePrefix
    terminal_accounting_state: admission.DeclaredAdmissionState
    plan_sha256: str
    authority_flags: tuple[tuple[str, bool], ...]


def _declaration_fields(declaration):
    _typed(declaration, SingleRoundtripDeclaration)
    _synthetic(declaration.declaration_id)
    native._identifier(declaration.publication_id)
    native._identifier(declaration.admission_id)
    _require(
        type(declaration.side) is str and declaration.side in ("long", "short"),
        "Exact long/short declared side required",
    )
    _require(
        type(declaration.exit_plan) is str
        and declaration.exit_plan in ("time_exit", "bracket_exit"),
        "Exact time_exit/bracket_exit declaration required",
    )


def declaration_sha256(
    declaration: SingleRoundtripDeclaration, *, fixture_sha256: str, genesis_sha256: str
) -> str:
    """Generate prospective local identity, never refresh retained expectations."""
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
            "fixture_sha256": fixture_sha256,
            "genesis_sha256": genesis_sha256,
            "declaration": asdict(declaration),
        }
        return hashlib.sha256(_canonical(body)).hexdigest()
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise SingleRoundtripDriverError(str(exc)) from exc


def _interval(fixture, now):
    ready, deadline = now + admission.DELAY_NS, now + admission.DELAY_NS + admission.WAIT_NS
    native._integer(ready)
    native._integer(deadline)
    _require(
        fixture.start_ns <= now <= ready <= deadline < fixture.end_ns,
        "Complete original inclusive execution interval required",
    )
    return ready, deadline


def _prepare(fixture, genesis, declaration, fixture_pin, genesis_pin, declaration_pin):
    # Complete scalar identity/resource guards precede all quote-price inspection.
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
    end_buffer = publication.received_at_ns + END_BUFFER_NS
    native._integer(end_buffer)
    _require(end_buffer < fixture.end_ns, "Strict original end buffer required")
    _, entry_deadline = _interval(fixture, publication.received_at_ns)
    latest_hold = entry_deadline + HOLD_NS
    native._integer(latest_hold)
    _interval(fixture, latest_hold)  # Bound the latest possible original hold/exit before prices.
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


def _bracket_reason(position, quote):
    difference = (
        quote.bid_nano - position.entry_price_nano
        if position.side == "long"
        else position.entry_price_nano - quote.ask_nano
    )
    net = difference // native.TICK_NANO - COMPARATOR_COST_TICKS
    return "target" if net >= TARGET_TICKS else "stop" if net <= STOP_TICKS else None


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
        self.entry_outcome, self.entry_cursor, self.entry_at = None, None, None
        self.hold_at, self.trigger_reason, self.trigger_cursor, self.request_at = (
            None,
            None,
            None,
            None,
        )
        self.exit_outcome, self.exit_cursor, self.exit_at = "no_exit", None, None

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

    def close(self, through):
        return native.close_through(
            self.fixture,
            expected_fixture_sha256=self.fixture_pin,
            expected_prefix=self.prefix,
            through_ns=through,
        )

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
            self.entry_outcome = "no_pending_entry"

    def entry_timeout(self):
        pending = self.state.pending_entry
        boundary = self.close(pending.deadline_ns)
        self.append(
            ENTRY_OUTCOME_EVENT_ID,
            pending.deadline_ns,
            admission.EntryUnfilled(pending.admission_id, "timeout"),
            "entry_deadline_boundary",
            boundary=boundary,
        )
        self.entry_outcome, self.entry_cursor, self.entry_at = (
            "constructed_entry_timeout",
            None,
            pending.deadline_ns,
        )

    def entry_candidate(self, cursor, quote):
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
        self.append(ENTRY_OUTCOME_EVENT_ID, now, payload, "entry_candidate_quote")
        self.entry_outcome, self.entry_cursor, self.entry_at = outcome, cursor, now
        if outcome == "constructed_entry_receipt":
            self.hold_at = now + HOLD_NS
            native._integer(self.hold_at)
            _interval(self.fixture, self.hold_at)

    def request_exit(self, reason, cursor=None):
        if reason == "hold_timer":
            now, kind, boundary = self.hold_at, "hold_boundary", self.close(self.hold_at - 1)
        else:
            now, kind, boundary = self.prefix.last_received_at_ns, "bracket_trigger_quote", None
        _interval(self.fixture, now)
        self.append(
            EXIT_REQUEST_EVENT_ID,
            now,
            admission.ExitRequested(self.state.position.admission_id, EXIT_REQUEST_ID),
            kind,
            boundary=boundary,
        )
        self.trigger_reason, self.trigger_cursor, self.request_at = reason, cursor, now

    def exit_unknown(self):
        pending = self.state.pending_exit
        boundary = self.close(pending.deadline_ns)
        self.append(
            EXIT_OUTCOME_EVENT_ID,
            pending.deadline_ns,
            admission.ExitUnknown(pending.request_id),
            "exit_deadline_boundary",
            boundary=boundary,
        )
        self.exit_outcome, self.exit_cursor, self.exit_at = (
            "constructed_exit_unknown",
            None,
            pending.deadline_ns,
        )

    def exit_candidate(self, cursor, quote):
        now, position, pending = quote.received_at_ns, self.state.position, self.state.pending_exit
        price = quote.bid_nano if position.side == "long" else quote.ask_nano
        self.append(
            EXIT_OUTCOME_EVENT_ID,
            now,
            admission.ExitReceipt(
                pending.request_id, EXIT_RECEIPT_ID, position.contract, 1, price, now
            ),
            "exit_candidate_quote",
        )
        self.exit_outcome, self.exit_cursor, self.exit_at = "constructed_exit_receipt", cursor, now

    def run(self):
        publication_cursor = self.fixture.publications[0].published_cursor
        for cursor, quote in enumerate(self.fixture.quotes):
            # Only the next timestamp closes elapsed supplied intervals, never its prices.
            pending = self.state.pending_entry
            if pending is not None and quote.received_at_ns > pending.deadline_ns:
                self.entry_timeout()
            if self.state.phase == "OPEN" and quote.received_at_ns >= self.hold_at:
                self.request_exit("hold_timer")  # Strict-left H-1 coverage; timer wins H equality.
            pending = self.state.pending_exit
            if (
                pending is not None
                and pending.status == "PENDING"
                and quote.received_at_ns > pending.deadline_ns
            ):
                self.exit_unknown()
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
                self.publish()  # First row before an equal-time suffix.
            now, pending = consumed.quote.received_at_ns, self.state.pending_entry
            if pending is not None and pending.ready_at_ns <= now <= pending.deadline_ns:
                self.entry_candidate(cursor, consumed.quote)
            if (
                self.state.phase == "OPEN"
                and self.declaration.exit_plan == "bracket_exit"
                and now < self.hold_at
            ):
                reason = _bracket_reason(self.state.position, consumed.quote)
                if reason is not None:
                    self.request_exit(reason, cursor)
            pending = self.state.pending_exit
            if (
                pending is not None
                and pending.status == "PENDING"
                and pending.ready_at_ns <= now <= pending.deadline_ns
            ):
                self.exit_candidate(cursor, consumed.quote)  # Widened exits are not refused.
        if self.state.pending_entry is not None:
            self.entry_timeout()
        if self.state.phase == "OPEN":
            self.request_exit("hold_timer")
        if self.state.pending_exit is not None and self.state.pending_exit.status == "PENDING":
            self.exit_unknown()
        _require(
            self.publication is not None
            and self.decision is not None
            and self.entry_outcome is not None
            and self.state.phase in ("FLAT", "EXIT_UNKNOWN"),
            "Complete publication, separated outcomes and terminal liability/flat state required",
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
            before = admission.reconstruct(
                self.genesis,
                self.records[:index],
                expected_genesis_sha256=self.genesis_pin,
                expected_terminal=record.expected_prefix,
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
            self.check_link(record, link, prefix, before)
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

    def check_link(self, record, link, prefix, before):
        payload, now, kind = record.payload, record.recorded_at_ns, link.kind
        if kind == "publication":
            witness = native.publication_witness(
                self.fixture,
                expected_fixture_sha256=self.fixture_pin,
                expected_prefix=prefix,
                publication_id=self.declaration.publication_id,
            )
            _require(
                link.publication == witness == self.publication
                and link.boundary is None
                and now == witness.received_at_ns
                and (record.event_id, type(payload))
                in (
                    (CLOCK_EVENT_ID, admission.ClockAdvanced),
                    (REQUEST_EVENT_ID, admission.AdmissionRequested),
                ),
                "Original first-cursor publication link required",
            )
            return
        _require(link.publication is None, "Only publication links may carry OPEN witnesses")
        if kind in ("entry_candidate_quote", "bracket_trigger_quote", "exit_candidate_quote"):
            _require(
                link.boundary is None and prefix.last_received_at_ns == now,
                "Exact consumed quote link without a boundary required",
            )
            quote = self.fixture.quotes[prefix.last_cursor]
            if kind == "entry_candidate_quote":
                _require(
                    record.event_id == ENTRY_OUTCOME_EVENT_ID
                    and prefix.last_cursor == self.entry_cursor
                    and now == self.entry_at,
                    "Exact original entry candidate identity required",
                )
                if type(payload) is admission.EntryReceipt:
                    crossed = quote.ask_nano if self.declaration.side == "long" else quote.bid_nano
                    _require(
                        payload.receipt_id == ENTRY_RECEIPT_ID
                        and payload.price_nano == crossed
                        and quote.ask_nano - quote.bid_nano == native.TICK_NANO
                        and self.entry_outcome == "constructed_entry_receipt"
                        and self.hold_at == now + HOLD_NS,
                        "Original narrow crossed entry and actual receipt hold required",
                    )
                else:
                    _require(
                        type(payload) is admission.EntryUnfilled
                        and payload.reason == "simulator_refusal"
                        and quote.ask_nano - quote.bid_nano != native.TICK_NANO
                        and self.entry_outcome == "simulator_spread_refusal",
                        "First widened entry candidate must refuse permanently",
                    )
            elif kind == "bracket_trigger_quote":
                _require(
                    type(payload) is admission.ExitRequested
                    and record.event_id == EXIT_REQUEST_EVENT_ID
                    and payload.request_id == EXIT_REQUEST_ID
                    and self.declaration.exit_plan == "bracket_exit"
                    and before.position is not None
                    and self.hold_at == before.position.executed_at_ns + HOLD_NS
                    and now < self.hold_at
                    and prefix.last_cursor == self.trigger_cursor
                    and now == self.request_at
                    and self.trigger_reason == _bracket_reason(before.position, quote)
                    and self.trigger_reason in ("target", "stop"),
                    "Original strictly-before-hold crossed bracket trigger required",
                )
            else:
                crossed = quote.bid_nano if before.position.side == "long" else quote.ask_nano
                _require(
                    type(payload) is admission.ExitReceipt
                    and record.event_id == EXIT_OUTCOME_EVENT_ID
                    and payload.request_id == EXIT_REQUEST_ID
                    and payload.receipt_id == EXIT_RECEIPT_ID
                    and payload.price_nano == crossed
                    and prefix.last_cursor == self.exit_cursor
                    and now == self.exit_at
                    and self.exit_outcome == "constructed_exit_receipt",
                    "Original eligible crossed exit without spread filtering required",
                )
            return
        _require(
            kind in ("entry_deadline_boundary", "hold_boundary", "exit_deadline_boundary")
            and link.boundary is not None
            and link.boundary.prefix == prefix,
            "Closed phase-specific boundary link required",
        )
        if kind == "hold_boundary":
            _require(
                type(payload) is admission.ExitRequested
                and record.event_id == EXIT_REQUEST_EVENT_ID
                and payload.request_id == EXIT_REQUEST_ID
                and before.position is not None
                and now
                == before.position.executed_at_ns + HOLD_NS
                == self.hold_at
                == self.request_at
                and self.trigger_reason == "hold_timer"
                and self.trigger_cursor is None,
                "Original actual-entry hold time and immutable timer reason required",
            )
            through = now - 1
        elif kind == "entry_deadline_boundary":
            _require(
                type(payload) is admission.EntryUnfilled
                and payload.reason == "timeout"
                and record.event_id == ENTRY_OUTCOME_EVENT_ID
                and before.pending_entry is not None
                and now == before.pending_entry.deadline_ns == self.entry_at
                and self.entry_cursor is None
                and self.entry_outcome == "constructed_entry_timeout",
                "Original entry liability deadline required",
            )
            through = now
        else:
            _require(
                type(payload) is admission.ExitUnknown
                and payload.request_id == EXIT_REQUEST_ID
                and record.event_id == EXIT_OUTCOME_EVENT_ID
                and before.pending_exit is not None
                and before.pending_exit.status == "PENDING"
                and now == before.pending_exit.deadline_ns == self.exit_at
                and self.exit_cursor is None
                and self.exit_outcome == "constructed_exit_unknown",
                "Original pending exit deadline and unresolved liability required",
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
            "Exact regenerated original deadline/strict-left hold boundary required",
        )


def build_single_roundtrip_plan(
    fixture: native.NativeFixture,
    genesis: admission.DeclaredAdmissionGenesis,
    declaration: SingleRoundtripDeclaration,
    *,
    expected_fixture_sha256: str,
    expected_genesis_sha256: str,
    expected_declaration_sha256: str,
) -> SingleRoundtripPlan:
    """Build one complete invented roundtrip, never a successful subset or actual order."""
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
        plan = SingleRoundtripPlan(
            VERSION,
            STATUS,
            expected_fixture_sha256,
            expected_genesis_sha256,
            expected_declaration_sha256,
            declaration,
            driver.publication,
            driver.decision,
            driver.decision.disposition,
            driver.entry_outcome,
            driver.entry_cursor,
            driver.entry_at,
            driver.hold_at,
            driver.trigger_reason,
            driver.trigger_cursor,
            driver.request_at,
            driver.exit_outcome,
            driver.exit_cursor,
            driver.exit_at,
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
        raise SingleRoundtripDriverError(str(exc)) from exc


def verify_single_roundtrip_plan(
    fixture: native.NativeFixture,
    genesis: admission.DeclaredAdmissionGenesis,
    declaration: SingleRoundtripDeclaration,
    *,
    expected_fixture_sha256: str,
    expected_genesis_sha256: str,
    expected_declaration_sha256: str,
    expected_plan_sha256: str,
) -> SingleRoundtripPlan:
    """Rebuild all original context against a retained complete pin, not a submitted plan."""
    try:
        native._pin(expected_plan_sha256)  # Syntax before any deep quote/outcome access.
        plan = build_single_roundtrip_plan(
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
        raise SingleRoundtripDriverError(str(exc)) from exc
