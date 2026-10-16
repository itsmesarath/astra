"""Pure constructed 6E admission accounting, not funded or authenticated execution.

Reconstructs the complete supplied declaration from its bound original genesis.
No files, quotes, policy, simulator, account or order lifecycle are accessed.
Canonical hashes establish local consistency only: an invented replacement whole
chain is not authenticated funding, receipt evidence, market freshness or risk
approval. Every explicit frontier is constructed-prefix completeness, not feed
health or proof that a native equal-time suffix or first quote was observed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace

from ai_trader.research import six_e_entry_budget as budget

EconomicSeed = budget.EconomicSeed
DeclaredEconomics = budget.DeclaredEconomics
DeclaredBudgetLimits = budget.DeclaredBudgetLimits
ledger = budget.ledger
VERSION = "six_e_declared_admission_v1"
STATUS = "constructed_declared_admission_not_authenticated"
MAX_RECORDS, MAX_RECORD_BYTES = 2000, 8192
DELAY_NS, WAIT_NS = 100_000_000, 1_000_000_000
AUTHORITY_FLAGS = tuple(
    sorted(
        {
            **dict(budget.AUTHORITY_FLAGS),
            "genesis_authenticated": False,
            "complete_records_authenticated": False,
            "receipt_provenance_authenticated": False,
            "execution_confirmed": False,
            "broker_execution_confirmed": False,
            "admission_authorized": False,
        }.items()
    )
)


class DeclaredAdmissionError(ValueError):
    """Malformed, conflicting or unsupported constructed declaration."""


def _require(condition, message):
    if not condition:
        raise DeclaredAdmissionError(message)


def _integer(value, low=0, high=ledger.MAX_INT):
    _require(type(value) is int and low <= value <= high, "Exact bounded integer required")


def _signed(value):
    _integer(value, -ledger.MAX_INT)


def _identifier(value):
    _require(type(value) is str, "Exact bounded identifier required")
    try:
        ledger._identifier(value)
    except ValueError as exc:
        raise DeclaredAdmissionError(str(exc)) from exc


def _pin(value):
    _require(type(value) is str, "Exact lowercase SHA256 required")
    try:
        ledger._pin(value)
    except ValueError as exc:
        raise DeclaredAdmissionError(str(exc)) from exc


def _validated(value, cls):
    _require(type(value) is cls, f"Exact {cls.__name__} required")
    try:
        replace(value)  # Revalidate even deliberately poisoned frozen instances.
    except (ValueError, TypeError, AttributeError) as exc:
        raise DeclaredAdmissionError(str(exc)) from exc


def _contract(value):
    _require(type(value) is str and value in ledger.CONTRACTS, "Supported dated 6E required")


def _side(value):
    _require(type(value) is str and value in ("long", "short"), "Exact long/short required")


def _price(value):
    _integer(value, ledger.target.TICK)
    _require(value % ledger.target.TICK == 0, "Declared tick-grid price required")


def _hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    _require(len(raw) <= MAX_RECORD_BYTES, "Canonical declaration exceeds byte bound")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class DeclaredAdmissionGenesis:
    scenario_id: str
    seed: EconomicSeed
    economics: DeclaredEconomics
    limits: DeclaredBudgetLimits

    def __post_init__(self):
        _identifier(self.scenario_id)
        for value, cls in (
            (self.seed, EconomicSeed),
            (self.economics, DeclaredEconomics),
            (self.limits, DeclaredBudgetLimits),
        ):
            _validated(value, cls)


@dataclass(frozen=True, slots=True)
class DeclaredPrefix:
    sequence: int
    head_sha256: str
    complete_through_ns: int

    def __post_init__(self):
        _integer(self.sequence, 0, MAX_RECORDS)
        _pin(self.head_sha256)
        _integer(self.complete_through_ns)


@dataclass(frozen=True, slots=True)
class AdmissionRequested:
    admission_id: str
    contract: str
    side: str
    quantity_contracts: int

    def __post_init__(self):
        _identifier(self.admission_id)
        _contract(self.contract)
        _side(self.side)
        _integer(self.quantity_contracts, 1, 1)


@dataclass(frozen=True, slots=True)
class EntryReceipt:
    admission_id: str
    receipt_id: str
    contract: str
    side: str
    quantity_contracts: int
    price_nano: int
    executed_at_ns: int

    def __post_init__(self):
        _identifier(self.admission_id)
        _identifier(self.receipt_id)
        _contract(self.contract)
        _side(self.side)
        _integer(self.quantity_contracts, 1, 1)
        _price(self.price_nano)
        _integer(self.executed_at_ns)


@dataclass(frozen=True, slots=True)
class EntryUnfilled:
    admission_id: str
    reason: str

    def __post_init__(self):
        _identifier(self.admission_id)
        _require(
            type(self.reason) is str and self.reason in ("timeout", "simulator_refusal"),
            "Closed timeout/simulator_refusal reason required",
        )


@dataclass(frozen=True, slots=True)
class ExitRequested:
    admission_id: str
    request_id: str

    def __post_init__(self):
        _identifier(self.admission_id)
        _identifier(self.request_id)


@dataclass(frozen=True, slots=True)
class ExitReceipt:
    request_id: str
    receipt_id: str
    contract: str
    quantity_contracts: int
    price_nano: int
    executed_at_ns: int

    def __post_init__(self):
        _identifier(self.request_id)
        _identifier(self.receipt_id)
        _contract(self.contract)
        _integer(self.quantity_contracts, 1, 1)
        _price(self.price_nano)
        _integer(self.executed_at_ns)


@dataclass(frozen=True, slots=True)
class ExitUnknown:
    request_id: str

    def __post_init__(self):
        _identifier(self.request_id)


@dataclass(frozen=True, slots=True)
class ClockAdvanced:
    pass


PAYLOAD_TYPES = (
    AdmissionRequested,
    EntryReceipt,
    EntryUnfilled,
    ExitRequested,
    ExitReceipt,
    ExitUnknown,
    ClockAdvanced,
)


@dataclass(frozen=True, slots=True)
class DeclaredRecord:
    event_id: str
    expected_prefix: DeclaredPrefix
    recorded_at_ns: int
    complete_through_ns: int
    payload: (
        AdmissionRequested
        | EntryReceipt
        | EntryUnfilled
        | ExitRequested
        | ExitReceipt
        | ExitUnknown
        | ClockAdvanced
    )

    def __post_init__(self):
        _identifier(self.event_id)
        _validated(self.expected_prefix, DeclaredPrefix)
        _integer(self.recorded_at_ns)
        _integer(self.complete_through_ns)
        _require(
            self.recorded_at_ns == self.complete_through_ns
            and self.recorded_at_ns >= self.expected_prefix.complete_through_ns,
            "Explicit equal frontier/event clocks must not precede bound prefix",
        )
        _require(type(self.payload) in PAYLOAD_TYPES, "Exact supported typed payload required")
        _validated(self.payload, type(self.payload))


@dataclass(frozen=True, slots=True)
class DeclaredPendingAdmission:
    admission_id: str
    contract: str
    side: str
    quantity_contracts: int
    requested_at_ns: int
    ready_at_ns: int
    deadline_ns: int


@dataclass(frozen=True, slots=True)
class DeclaredPosition:
    admission_id: str
    contract: str
    side: str
    quantity_contracts: int
    entry_price_nano: int
    executed_at_ns: int


@dataclass(frozen=True, slots=True)
class DeclaredExit:
    request_id: str
    requested_at_ns: int
    ready_at_ns: int
    deadline_ns: int
    status: str


@dataclass(frozen=True, slots=True)
class DeclaredAdmissionState:
    version: str
    status: str
    genesis_sha256: str
    prefix: DeclaredPrefix
    last_event_at_ns: int | None
    phase: str
    declared_realization_balance_usd_micros: int
    gross_realized_usd_micros: int
    entry_fees_usd_micros: int
    exit_fees_usd_micros: int
    realization_balance_shortfall_usd_micros: int
    entry_fee_reserve_usd_micros: int
    initial_margin_commitment_usd_micros: int
    exit_fee_reserve_usd_micros: int
    total_commitments_usd_micros: int
    available_balance_usd_micros: int
    complete_declared_equity_usd_micros: int | None
    complete_declared_net_return_usd_micros: int | None
    pending_entry: DeclaredPendingAdmission | None
    position: DeclaredPosition | None
    pending_exit: DeclaredExit | None
    receipt_content_sha256s: tuple[str, ...]
    authority_flags: tuple[tuple[str, bool], ...]


@dataclass(frozen=True, slots=True)
class DeclaredAdmissionTransition:
    records: tuple[DeclaredRecord, ...]
    state: DeclaredAdmissionState
    budget_decision: budget.DeclaredBudgetDecision | None


def genesis_sha256(genesis: DeclaredAdmissionGenesis) -> str:
    """Hash a validated declaration, never files or external source evidence."""
    _validated(genesis, DeclaredAdmissionGenesis)
    return _hash(
        {
            "version": VERSION,
            "scope": STATUS,
            "delay_ns": DELAY_NS,
            "wait_ns": WAIT_NS,
            "quantity_contracts": 1,
            "genesis": asdict(genesis),
        }
    )


def _state(genesis, identity, prefix, pending, position, exit_, gross, entry, exit_fees, receipts):
    _signed(gross)
    _integer(entry)
    _integer(exit_fees)
    before_fees = genesis.seed.initial_balance_usd_micros + gross
    _signed(before_fees)
    after_entry = before_fees - entry
    _signed(after_entry)
    balance = after_entry - exit_fees
    _signed(balance)
    net = balance - genesis.seed.initial_balance_usd_micros
    _signed(net)
    liability = pending is not None or position is not None or exit_ is not None
    assumptions = genesis.economics
    entry_reserve = assumptions.entry_fee_usd_micros_per_contract if pending else 0
    margin = assumptions.margin.initial_usd_micros_per_contract if liability else 0
    exit_reserve = assumptions.exit_fee_usd_micros_per_contract if liability else 0
    total = entry_reserve + margin + exit_reserve
    _integer(total)
    available = balance - total
    _signed(available)
    phase = (
        "ENTRY_PENDING"
        if pending
        else "EXIT_UNKNOWN"
        if exit_ and exit_.status == "UNKNOWN"
        else "EXIT_PENDING"
        if exit_
        else "OPEN"
        if position
        else "FLAT"
    )
    return DeclaredAdmissionState(
        VERSION,
        STATUS,
        identity,
        prefix,
        prefix.complete_through_ns if prefix.sequence else None,
        phase,
        balance,
        gross,
        entry,
        exit_fees,
        max(0, -balance),
        entry_reserve,
        margin,
        exit_reserve,
        total,
        available,
        None if liability else balance,
        None if liability else net,
        pending,
        position,
        exit_,
        receipts,
        AUTHORITY_FLAGS,
    )


def _times(now):
    ready, deadline = now + DELAY_NS, now + DELAY_NS + WAIT_NS
    _integer(ready)
    _integer(deadline)
    return ready, deadline


def _unique(seen, namespace, value):
    _require(value not in seen[namespace], f"Duplicate {namespace} identity")
    seen[namespace].add(value)


def _receipt(state, record, liability, seen):
    payload = record.payload
    _unique(seen, "receipt", payload.receipt_id)
    body = asdict(payload)
    del body["receipt_id"]
    identity = _hash(
        {
            "genesis_sha256": state.genesis_sha256,
            "phase": type(payload).__name__,
            "liability": asdict(liability),
            "position": asdict(state.position) if state.position is not None else None,
            "recorded_at_ns": record.recorded_at_ns,
            "receipt": body,
        }
    )
    _require(identity not in state.receipt_content_sha256s, "Duplicate declared receipt content")
    return state.receipt_content_sha256s + (identity,)


def _step(genesis, state, record, seen):
    _validated(record, DeclaredRecord)
    _require(record.expected_prefix == state.prefix, "Exact preceding prefix required")
    _unique(seen, "event", record.event_id)
    _require(state.prefix.sequence < MAX_RECORDS, "Constructed record count exceeds bound")
    now, payload = record.recorded_at_ns, record.payload
    pending, position, exit_ = state.pending_entry, state.position, state.pending_exit
    for deadline in (
        pending.deadline_ns if pending else None,
        exit_.deadline_ns if exit_ and exit_.status == "PENDING" else None,
    ):
        _require(deadline is None or now <= deadline, "Explicit deadline outcome required first")
    gross, entry, exit_fees = (
        state.gross_realized_usd_micros,
        state.entry_fees_usd_micros,
        state.exit_fees_usd_micros,
    )
    receipts, decision = state.receipt_content_sha256s, None
    if type(payload) is AdmissionRequested:
        _unique(seen, "admission", payload.admission_id)
        snapshot = budget.DeclaredCapitalSnapshot(
            genesis.seed,
            state.declared_realization_balance_usd_micros,
            state.prefix.sequence,
            state.prefix.head_sha256,
            state.last_event_at_ns,
            state.prefix.complete_through_ns,
            1 if position else 0,
            1 if exit_ else 0,
            exit_.status if exit_ else None,
            pending is not None,
        )
        proposal = budget.EntryProposal(
            now, state.prefix.sequence, state.prefix.head_sha256, payload.contract, 1
        )
        try:
            decision = budget.assess_entry_budget(
                snapshot, proposal, genesis.economics, genesis.limits
            )
        except ValueError as exc:
            raise DeclaredAdmissionError(str(exc)) from exc
        if decision.disposition == "declared_budget_available":
            ready, deadline = _times(now)
            pending = DeclaredPendingAdmission(
                payload.admission_id, payload.contract, payload.side, 1, now, ready, deadline
            )
    elif type(payload) is EntryReceipt:
        _require(
            pending is not None
            and payload.admission_id == pending.admission_id
            and payload.contract == pending.contract
            and payload.side == pending.side,
            "Matching unfilled admission required",
        )
        _require(
            payload.executed_at_ns == now and pending.ready_at_ns <= now <= pending.deadline_ns,
            "Immediate full entry receipt inside original inclusive interval required",
        )
        receipts = _receipt(state, record, pending, seen)
        entry += genesis.economics.entry_fee_usd_micros_per_contract
        position = DeclaredPosition(
            pending.admission_id, pending.contract, pending.side, 1, payload.price_nano, now
        )
        pending = None
    elif type(payload) is EntryUnfilled:
        _require(
            pending is not None and payload.admission_id == pending.admission_id,
            "Matching still-unfilled admission required",
        )
        _require(
            now == pending.deadline_ns
            if payload.reason == "timeout"
            else pending.ready_at_ns <= now <= pending.deadline_ns,
            "Declared refusal must retain original eligible interval/deadline",
        )
        pending = None
    elif type(payload) is ExitRequested:
        _unique(seen, "request", payload.request_id)
        _require(
            position is not None
            and exit_ is None
            and payload.admission_id == position.admission_id,
            "Matching open position without an exit reservation required",
        )
        ready, deadline = _times(now)
        exit_ = DeclaredExit(payload.request_id, now, ready, deadline, "PENDING")
    elif type(payload) is ExitReceipt:
        _require(
            position is not None
            and exit_ is not None
            and exit_.status == "PENDING"
            and payload.request_id == exit_.request_id
            and payload.contract == position.contract,
            "Matching PENDING original-contract exit required; UNKNOWN is terminal",
        )
        _require(
            payload.executed_at_ns == now and exit_.ready_at_ns <= now <= exit_.deadline_ns,
            "Immediate full exit receipt inside original inclusive interval required",
        )
        receipts = _receipt(state, record, exit_, seen)
        ticks = (payload.price_nano - position.entry_price_nano) // ledger.target.TICK
        delta = ticks * genesis.economics.tick_value_usd_micros
        delta *= 1 if position.side == "long" else -1
        _signed(delta)
        gross += delta
        exit_fees += genesis.economics.exit_fee_usd_micros_per_contract
        position = exit_ = None
    elif type(payload) is ExitUnknown:
        _require(
            exit_ is not None
            and exit_.status == "PENDING"
            and payload.request_id == exit_.request_id
            and now == exit_.deadline_ns,
            "Matching original PENDING deadline required for terminal UNKNOWN",
        )
        exit_ = replace(exit_, status="UNKNOWN")
    head = _hash({"version": VERSION, "kind": type(payload).__name__, "record": asdict(record)})
    prefix = DeclaredPrefix(state.prefix.sequence + 1, head, record.complete_through_ns)
    return (
        _state(
            genesis,
            state.genesis_sha256,
            prefix,
            pending,
            position,
            exit_,
            gross,
            entry,
            exit_fees,
            receipts,
        ),
        decision,
    )


def _reconstruct(genesis, records, expected_genesis_sha256, expected_terminal):
    identity = genesis_sha256(genesis)
    _pin(expected_genesis_sha256)
    _require(identity == expected_genesis_sha256, "Bound original genesis identity differs")
    _validated(expected_terminal, DeclaredPrefix)
    _require(
        type(records) is tuple and len(records) <= MAX_RECORDS,
        "Complete bounded immutable record tuple required",
    )
    prefix = DeclaredPrefix(0, identity, genesis.seed.initialized_at_ns)
    state = _state(genesis, identity, prefix, None, None, None, 0, 0, 0, ())
    seen = {name: set() for name in ("event", "admission", "request", "receipt")}
    for record in records:
        state, _ = _step(genesis, state, record, seen)
    _require(state.prefix == expected_terminal, "Complete terminal sequence/head/frontier differs")
    return state, seen


def reconstruct(
    genesis: DeclaredAdmissionGenesis,
    records: tuple[DeclaredRecord, ...],
    *,
    expected_genesis_sha256: str,
    expected_terminal: DeclaredPrefix,
) -> DeclaredAdmissionState:
    """Verify the complete declared prefix, not external funding or receipt provenance."""
    return _reconstruct(genesis, records, expected_genesis_sha256, expected_terminal)[0]


def advance(
    genesis: DeclaredAdmissionGenesis,
    records: tuple[DeclaredRecord, ...],
    record: DeclaredRecord,
    *,
    expected_genesis_sha256: str,
    expected_terminal: DeclaredPrefix,
) -> DeclaredAdmissionTransition:
    """Append one declaration purely; failure leaves every supplied object unchanged.

    Admission uses only the preceding frontier. Timeout/UNKNOWN stamped exactly
    deadline asserts the equal-time boundary; no native suffix is authenticated.
    Append that outcome before a later ClockAdvanced. UNKNOWN never reconciles.
    """
    state, seen = _reconstruct(genesis, records, expected_genesis_sha256, expected_terminal)
    state, decision = _step(genesis, state, record, seen)
    return DeclaredAdmissionTransition(records + (record,), state, decision)
