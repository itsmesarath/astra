"""Offline 6E scenario liability ledger, not an execution engine or funded account.

Records supplied incremental paper-simulator receipts; does not generate orders,
verify receipt provenance, mark a futures book as a CFD fill, or alter old labels.
Session boundaries and quote references cannot release unresolved inventory.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields, replace
from datetime import UTC, date, datetime
from pathlib import Path

from ai_trader.research import six_e_liquidity_study as study

target = study.exits.target
APPLICATION_ID, SCHEMA = 0x3645504C, 1
MAX_EVENTS, MAX_RECORD_BYTES, MAX_DB_BYTES = 10_000, 8192, 128 * 1024**2
MAX_INT = 2**63 - 1
DAY_NS = 86_400 * target.SECOND
CONTRACTS = ("6EM5", "6EU5", "6EZ5", "6EH6")


class LedgerError(ValueError):
    """Invalid state, identity, source, schema or receipt record."""


class LedgerConflict(LedgerError):
    """Changed identity or stale caller snapshot; no new record committed."""


def _identifier(value) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", value) is None:
        raise LedgerError("Expected a bounded identifier, not a path or arbitrary text")


def _pin(value) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise LedgerError("Expected lowercase SHA256")


def _integer(value, low=0, high=MAX_INT) -> None:
    if type(value) is not int or not low <= value <= high:
        raise LedgerError("Expected bounded integer, not Boolean or floating point")


def _price(value) -> None:
    _integer(value, target.TICK)
    if value % target.TICK:
        raise LedgerError("6E nano-price must be on the declared tick grid")


def _session(value) -> int:
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise LedgerError("Expected canonical source-session date")
    target.window(value)  # Existing development/reserved guard, no price access.
    return int(datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp()) * target.SECOND


def _canonical(value) -> bytes:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if len(raw) > MAX_RECORD_BYTES:
        raise LedgerError("Ledger record exceeds its byte bound")
    return raw


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise LedgerError("Duplicate stored JSON key")
        result[key] = value
    return result


def _constant(value):
    raise LedgerError("Nonfinite stored JSON")


def _decode(raw) -> dict:
    if not isinstance(raw, bytes) or len(raw) > MAX_RECORD_BYTES:
        raise LedgerError("Invalid stored record bytes")
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise LedgerError("Invalid stored ledger JSON") from exc
    if not isinstance(value, dict) or _canonical(value) != raw:
        raise LedgerError("Stored ledger record must be a canonical object")
    return value


@dataclass(frozen=True, slots=True)
class ScenarioConfig:
    scenario_id: str
    policy_id: str
    exit_plan: str
    source_manifest_sha256: str
    simulator_version: str
    extra_round_trip_ticks_per_contract: int = 1
    max_position_contracts: int = 1

    def __post_init__(self):
        for value in (self.scenario_id, self.policy_id, self.simulator_version):
            _identifier(value)
        _pin(self.source_manifest_sha256)
        if self.exit_plan not in target.PLANS:
            raise LedgerError("One fixed exit plan per scenario")
        _integer(self.extra_round_trip_ticks_per_contract, 0, 100)
        _integer(self.max_position_contracts, 1, 1000)


@dataclass(frozen=True, slots=True)
class Observation:
    event_id: str
    source_session: str
    observed_at_ns: int

    def __post_init__(self):
        _validate(self)


@dataclass(frozen=True, slots=True)
class SessionBoundary(Observation):
    """Clock/context advancement only, never an implicit liquidation or reset."""


@dataclass(frozen=True, slots=True)
class EntryFill(Observation):
    position_id: str
    contract: str
    side: str
    quantity_contracts: int
    price_nano: int
    executed_at_ns: int
    evidence_id: str
    paper_receipt_sha256: str


@dataclass(frozen=True, slots=True)
class ExitIntent(Observation):
    request_id: str
    position_id: str
    quantity_contracts: int


@dataclass(frozen=True, slots=True)
class UnresolvedExit(Observation):
    request_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class CancelIntent(Observation):
    request_id: str


@dataclass(frozen=True, slots=True)
class CancelReceipt(Observation):
    request_id: str
    cancelled_remaining_contracts: int
    evidence_id: str
    paper_receipt_sha256: str


@dataclass(frozen=True, slots=True)
class ExitFill(Observation):
    request_id: str
    contract: str
    quantity_contracts: int
    price_nano: int
    executed_at_ns: int
    evidence_id: str
    paper_receipt_sha256: str


@dataclass(frozen=True, slots=True)
class QuoteReference(Observation):
    contract: str
    quote_at_ns: int
    native_cursor: int
    bid_nano: int
    ask_nano: int


RECORD_TYPES = {
    cls.__name__: cls
    for cls in (
        SessionBoundary,
        EntryFill,
        ExitIntent,
        UnresolvedExit,
        CancelIntent,
        CancelReceipt,
        ExitFill,
        QuoteReference,
    )
}


def _validate(event) -> None:
    if type(event).__name__ not in RECORD_TYPES or RECORD_TYPES[type(event).__name__] is not type(
        event
    ):
        raise LedgerError("Typed scenario ledger record required")
    _identifier(event.event_id)
    start = _session(event.source_session)
    _integer(event.observed_at_ns)
    if not start <= event.observed_at_ns < start + DAY_NS:
        raise LedgerError("Observation time must belong to its source session")
    for name in ("position_id", "request_id", "evidence_id"):
        if hasattr(event, name):
            _identifier(getattr(event, name))
    if hasattr(event, "contract") and event.contract not in CONTRACTS:
        raise LedgerError("Only declared dated 6E research contracts supported")
    for name in ("quantity_contracts", "cancelled_remaining_contracts"):
        if hasattr(event, name):
            _integer(getattr(event, name), 1, 1000)
    if hasattr(event, "paper_receipt_sha256"):
        _pin(event.paper_receipt_sha256)
    if isinstance(event, (EntryFill, ExitFill)):
        _price(event.price_nano)
        _integer(event.executed_at_ns)
        if event.executed_at_ns > event.observed_at_ns:
            raise LedgerError("Receipt cannot precede execution")
        executed_day = (
            datetime.fromtimestamp(event.executed_at_ns // target.SECOND, UTC).date().isoformat()
        )
        _session(executed_day)
        if isinstance(event, EntryFill):
            if event.side not in target.SIDES or event.contract != study.census.dated_contract(
                executed_day
            ):
                raise LedgerError("Entry side or original dated contract differs")
    if isinstance(event, UnresolvedExit):
        if not isinstance(event.reason, str) or not event.reason.strip() or len(event.reason) > 512:
            raise LedgerError("Unresolved exit needs a bounded explicit reason")
    if isinstance(event, QuoteReference):
        _integer(event.quote_at_ns)
        _integer(event.native_cursor, 0, study.resource.MAX_QUOTES - 1)
        _price(event.bid_nano)
        _price(event.ask_nano)
        if (
            not start <= event.quote_at_ns <= event.observed_at_ns
            or event.bid_nano >= event.ask_nano
        ):
            raise LedgerError("Reference is crossed, future or outside its declared source session")


def _record(event) -> bytes:
    _validate(event)
    return _canonical({"kind": type(event).__name__, "data": asdict(event)})


def _read_record(raw):
    value = _decode(raw)
    if set(value) != {"kind", "data"} or value["kind"] not in RECORD_TYPES:
        raise LedgerError("Unknown stored event schema")
    cls = RECORD_TYPES[value["kind"]]
    if not isinstance(value["data"], dict) or set(value["data"]) != {
        field.name for field in fields(cls)
    }:
        raise LedgerError("Stored event fields differ from typed contract")
    return cls(**value["data"])


@dataclass(frozen=True, slots=True)
class Position:
    position_id: str
    entry_source_session: str
    contract: str
    side: str
    initial_contracts: int
    remaining_contracts: int
    entry_price_nano: int
    executed_at_ns: int


@dataclass(frozen=True, slots=True)
class Reservation:
    request_id: str
    quantity_contracts: int
    remaining_contracts: int
    requested_at_ns: int
    status: str


@dataclass(frozen=True, slots=True)
class LedgerState:
    sequence: int
    tip_sha256: str
    current_session: str | None
    last_observed_at_ns: int
    position: Position | None
    reservation: Reservation | None
    last_reference: QuoteReference | None
    closed_contracts: int
    closed_gross_contract_ticks: int
    closed_net_contract_ticks: int
    closed_positions: int
    execution_watermark_ns: int = 0

    @property
    def complete_simulated_net_contract_ticks(self) -> int | None:
        return self.closed_net_contract_ticks if self.position is None else None

    @property
    def entry_recording_blocked(self) -> bool:
        return self.position is not None or self.reservation is not None

    @property
    def reference_age_ns(self) -> int | None:
        return (
            None
            if self.last_reference is None
            else self.last_observed_at_ns - self.last_reference.quote_at_ns
        )


def _apply(state: LedgerState, event: Observation, config: ScenarioConfig) -> LedgerState:
    _validate(event)
    if event.observed_at_ns < state.last_observed_at_ns:
        raise LedgerError("Account observation clock regressed")
    if (
        state.current_session is not None
        and event.source_session != state.current_session
        and not isinstance(event, SessionBoundary)
    ):
        raise LedgerError("Explicit session boundary required; cannot start a fresh daily account")
    updated = replace(
        state, current_session=event.source_session, last_observed_at_ns=event.observed_at_ns
    )
    if isinstance(event, SessionBoundary):
        return updated
    if isinstance(event, EntryFill):
        if (
            state.entry_recording_blocked
            or event.quantity_contracts > config.max_position_contracts
        ):
            raise LedgerError("Open liability or scenario quantity limit blocks a new entry record")
        if event.executed_at_ns < state.execution_watermark_ns:
            raise LedgerError("New entry execution cannot overlap already reconciled inventory")
        return replace(
            updated,
            position=Position(
                event.position_id,
                datetime.fromtimestamp(event.executed_at_ns // target.SECOND, UTC)
                .date()
                .isoformat(),
                event.contract,
                event.side,
                event.quantity_contracts,
                event.quantity_contracts,
                event.price_nano,
                event.executed_at_ns,
            ),
            last_reference=None,
            execution_watermark_ns=event.executed_at_ns,
        )
    position, request = state.position, state.reservation
    if position is None:
        raise LedgerError("Exit or reference requires existing scenario inventory")
    if isinstance(event, QuoteReference):
        if event.contract != position.contract or event.quote_at_ns < position.executed_at_ns:
            raise LedgerError("Reference cannot substitute another contract or pre-entry book")
        if state.last_reference is not None:
            old = state.last_reference
            if event.quote_at_ns < old.quote_at_ns or (
                event.source_session == old.source_session
                and event.native_cursor < old.native_cursor
            ):
                raise LedgerError("Reference receive clock or native cursor regressed")
            if (
                event.source_session == old.source_session
                and event.native_cursor == old.native_cursor
                and (event.quote_at_ns, event.bid_nano, event.ask_nano)
                != (old.quote_at_ns, old.bid_nano, old.ask_nano)
            ):
                raise LedgerError(
                    "Published reference cursor was retried with different quote content"
                )
        return replace(updated, last_reference=event)
    if isinstance(event, ExitIntent):
        if (
            request is not None
            or event.position_id != position.position_id
            or event.quantity_contracts > position.remaining_contracts
            or event.observed_at_ns < position.executed_at_ns
        ):
            raise LedgerError("Exit cannot duplicate a pending request or exceed owned inventory")
        return replace(
            updated,
            reservation=Reservation(
                event.request_id,
                event.quantity_contracts,
                event.quantity_contracts,
                event.observed_at_ns,
                "PENDING",
            ),
        )
    if request is None or event.request_id != request.request_id:
        raise LedgerError("Receipt or reconciliation must identify the outstanding exit")
    if isinstance(event, UnresolvedExit):
        return replace(updated, reservation=replace(request, status="UNKNOWN"))
    if isinstance(event, CancelIntent):
        return replace(updated, reservation=replace(request, status="CANCEL_REQUESTED"))
    if isinstance(event, CancelReceipt):
        if (
            request.status not in ("UNKNOWN", "CANCEL_REQUESTED")
            or event.cancelled_remaining_contracts != request.remaining_contracts
        ):
            raise LedgerError(
                "Cancellation requires explicit reconciliation of the exact remainder"
            )
        return replace(updated, reservation=None)  # Inventory is NOT liquidated.
    if isinstance(event, ExitFill):
        if (
            event.contract != position.contract
            or event.executed_at_ns < request.requested_at_ns
            or event.quantity_contracts > request.remaining_contracts
            or event.quantity_contracts > position.remaining_contracts
        ):
            raise LedgerError(
                "Exit receipt contract, execution time or incremental quantity differs"
            )
        sign = 1 if position.side == "long" else -1
        gross = (
            sign
            * ((event.price_nano - position.entry_price_nano) // target.TICK)
            * event.quantity_contracts
        )
        remainder = position.remaining_contracts - event.quantity_contracts
        pending = request.remaining_contracts - event.quantity_contracts
        return replace(
            updated,
            position=replace(position, remaining_contracts=remainder) if remainder else None,
            reservation=replace(request, remaining_contracts=pending) if pending else None,
            last_reference=state.last_reference if remainder else None,
            closed_contracts=state.closed_contracts + event.quantity_contracts,
            closed_gross_contract_ticks=state.closed_gross_contract_ticks + gross,
            closed_net_contract_ticks=state.closed_net_contract_ticks
            + gross
            - config.extra_round_trip_ticks_per_contract * event.quantity_contracts,
            closed_positions=state.closed_positions + int(remainder == 0),
            execution_watermark_ns=max(state.execution_watermark_ns, event.executed_at_ns),
        )
    raise LedgerError("Unsupported scenario transition")


def protocol() -> dict:
    return {
        "version": "six_e_scenario_liability_ledger_v1",
        "scope": "One supplied single-position development scenario and exit plan; not "
        "a strategy run, counterfactual portfolio, funded futures account or CFD account",
        "units": "Integer dated 6E contracts and nano-prices on the existing tick grid; "
        "closed simulation totals in contract-ticks, never USD cash or margin",
        "receipts": "Caller-supplied incremental paper-simulator receipts only; local "
        "hashes/typed records do not authenticate external provenance or broker fills",
        "carry": "Session boundaries, clock advancement, UNKNOWN and cancellation intent "
        "never reset inventory, reservations, cumulative costs or realized simulation totals",
        "reference": "A same-contract published quote reference cannot close or reconcile an exit",
        "limits": {
            "events": MAX_EVENTS,
            "record_bytes": MAX_RECORD_BYTES,
            "database_bytes": MAX_DB_BYTES,
        },
        "training_eligible": False,
        "strategy_scoring_allowed": False,
        "trading_enabled": False,
        "promotion_allowed": False,
        "broker_execution_confirmed": False,
        "receipt_provenance_verified": False,
    }


def _fingerprints() -> dict:
    return {
        **study.fingerprints(),
        Path(__file__).name: study.common.hash_file(Path(__file__), 1024**2),
    }


def _metadata(config: ScenarioConfig) -> bytes:
    if type(config) is not ScenarioConfig:
        raise LedgerError("Typed scenario configuration required")
    ScenarioConfig(**asdict(config))
    return _canonical(
        {"config": asdict(config), "protocol": protocol(), "source_sha256": _fingerprints()}
    )


def _safe_path(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink() or os.path.isjunction(part):
            raise LedgerError("Ledger path cannot traverse a symlink or junction")
    if path.suffix != ".sqlite":
        raise LedgerError("A separate .sqlite scenario ledger is required")
    return path


def _schema_rows() -> list[tuple]:
    rows = [
        (
            "table",
            "config",
            "config",
            "CREATE TABLE config "
            "(singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
            "payload BLOB NOT NULL, sha256 TEXT NOT NULL)",
        ),
        (
            "table",
            "events",
            "events",
            "CREATE TABLE events "
            "(sequence INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, "
            "payload BLOB NOT NULL, previous_sha256 TEXT NOT NULL, sha256 TEXT NOT NULL)",
        ),
    ]
    for table in ("config", "events"):
        for action in ("UPDATE", "DELETE"):
            name = f"{table}_no_{action.lower()}"
            sql = f"CREATE TRIGGER {name} BEFORE {action} ON {table} BEGIN "
            sql += "SELECT RAISE(ABORT, 'Append-only scenario ledger'); END"
            rows.append(("trigger", name, table, sql))
    return sorted(rows, key=lambda row: row[1])


class ScenarioLedger:
    """One SQLite connection per thread; explicit create never adopts or resets a file."""

    def __init__(self, path: Path, config: ScenarioConfig, *, read_only: bool = True):
        if type(read_only) is not bool:
            raise LedgerError("Read-only choice must be Boolean")
        self.path, self.config, self.read_only = _safe_path(path), config, read_only
        if not self.path.is_file() or not 0 < self.path.stat().st_size <= MAX_DB_BYTES:
            raise LedgerError(
                "Missing, empty or oversized ledger; explicit initialization required"
            )
        self._db = sqlite3.connect(
            self.path.as_uri() + ("?mode=ro" if read_only else "?mode=rw"),
            uri=True,
            isolation_level=None,
            timeout=5,
        )
        try:
            self._db.execute("PRAGMA synchronous=FULL") if not read_only else None
            self.snapshot()
        except BaseException:
            self._db.close()
            raise

    @classmethod
    def create(cls, path: Path, config: ScenarioConfig):
        raw = _metadata(config)  # Validate before any filesystem mutation.
        path = _safe_path(path)
        with path.open("xb"):
            pass  # Exclusive ownership. Failed initialization remains evidence, never a retry.
        db = sqlite3.connect(path, isolation_level=None)
        try:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            db.execute(f"PRAGMA application_id={APPLICATION_ID}")
            db.execute(f"PRAGMA user_version={SCHEMA}")
            for _, _, _, sql in _schema_rows():
                db.execute(sql)
            db.execute("INSERT INTO config VALUES (1, ?, ?)", (raw, _hash(raw)))
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
        return cls(path, config, read_only=False)

    @contextmanager
    def _transaction(self, *, write=False):
        if write and self.read_only:
            raise LedgerError("Read-only scenario ledger cannot append")
        self._db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield
            self._db.commit()
        except BaseException:
            self._db.rollback()
            raise

    def _state(self) -> tuple[LedgerState, list]:
        _safe_path(self.path)
        if (
            self.path.stat().st_size > MAX_DB_BYTES
            or self._db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
            or self._db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA
        ):
            raise LedgerError("Ledger size, application or schema differs")
        schema = self._db.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT GLOB 'sqlite_*' ORDER BY name"
        ).fetchmany(7)
        if schema != _schema_rows():
            raise LedgerError("Ledger schema or append-only triggers differ")
        rows = self._db.execute("SELECT singleton, payload, sha256 FROM config LIMIT 2").fetchall()
        if (
            len(rows) != 1
            or rows[0][0] != 1
            or rows[0][1] != _metadata(self.config)
            or _hash(rows[0][1]) != rows[0][2]
        ):
            raise LedgerError("Scenario identity, parameters, protocol or frozen source differs")
        genesis = rows[0][2]
        state = LedgerState(0, genesis, None, 0, None, None, None, 0, 0, 0, 0)
        history, identities, positions, requests, receipts, receipt_pins = (
            [],
            set(),
            set(),
            set(),
            set(),
            set(),
        )
        for sequence, event_id, raw, previous, pin in self._db.execute(
            "SELECT sequence, event_id, payload, previous_sha256, sha256 "
            "FROM events ORDER BY sequence LIMIT ?",
            (MAX_EVENTS + 1,),
        ):
            _pin(previous)
            _pin(pin)
            if not isinstance(raw, bytes) or len(raw) > MAX_RECORD_BYTES:
                raise LedgerError("Invalid stored record bytes")
            if (
                type(sequence) is not int
                or sequence != state.sequence + 1
                or sequence > MAX_EVENTS
                or previous != state.tip_sha256
                or _hash(previous.encode() + b"\n" + raw) != pin
            ):
                raise LedgerError("Ledger event chain, count or sequence differs")
            event = _read_record(raw)
            if event.event_id != event_id or event_id in identities:
                raise LedgerError("Duplicate or changed event identity")
            identities.add(event_id)
            if isinstance(event, EntryFill):
                if event.position_id in positions:
                    raise LedgerError("Position identifiers cannot be reused")
                positions.add(event.position_id)
            if isinstance(event, ExitIntent):
                if event.request_id in requests:
                    raise LedgerError("Exit request identifiers cannot be reused")
                requests.add(event.request_id)
            if hasattr(event, "evidence_id"):
                if event.evidence_id in receipts or event.paper_receipt_sha256 in receipt_pins:
                    raise LedgerError("A paper receipt cannot supply two incremental events")
                receipts.add(event.evidence_id)
                receipt_pins.add(event.paper_receipt_sha256)
            state = replace(_apply(state, event, self.config), sequence=sequence, tip_sha256=pin)
            history.append((event_id, raw))
        return state, history

    def snapshot(self, *, expected_tip_sha256: str | None = None) -> LedgerState:
        with self._transaction():
            state, _ = self._state()
            if expected_tip_sha256 is not None:
                _pin(expected_tip_sha256)
                if state.tip_sha256 != expected_tip_sha256:
                    raise LedgerConflict("Ledger tip differs from the caller's trusted pin")
            return state

    def append(self, event: Observation, *, expected_tip_sha256: str) -> bool:
        raw = _record(event)
        _pin(expected_tip_sha256)
        with self._transaction(write=True):
            state, history = self._state()
            previous = dict(history).get(event.event_id)
            if previous is not None:
                if previous != raw:
                    raise LedgerConflict("Existing event was retried with different content")
                return False  # An exact retry is harmless even with its original stale tip.
            if expected_tip_sha256 != state.tip_sha256:
                raise LedgerConflict("Ledger changed since the caller's snapshot")
            if state.sequence >= MAX_EVENTS:
                raise LedgerError("Scenario event count bound exceeded")
            # Reuse the complete replay to check both transitions and global identities
            # before commit. No cached position/risk checkpoint can silently reset state.
            pin = _hash(state.tip_sha256.encode() + b"\n" + raw)
            self._db.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?)",
                (state.sequence + 1, event.event_id, raw, state.tip_sha256, pin),
            )
            self._state()
            if (
                self._db.execute("PRAGMA page_count").fetchone()[0]
                * self._db.execute("PRAGMA page_size").fetchone()[0]
                > MAX_DB_BYTES
            ):
                raise LedgerError("Scenario database byte bound exceeded")
            return True

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
