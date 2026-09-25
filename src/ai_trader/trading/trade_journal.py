"""Transactional evidence and paper-entry lifecycle journal; no execution.

One database belongs to one research/paper run. Inserts are append-only through
this API; exact retries return False, conflicting identifiers raise. Local hashes
and triggers detect some corruption but are not signatures or tamper-proofing.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, fields
from decimal import Decimal
from pathlib import Path

from ai_trader.trading.paper_account import PaperAccountSeed, recover_account
from ai_trader.trading.paper_lifecycle import (
    PaperEntryOrder,
    PaperExitOrder,
    PaperOrderEvent,
    reconstruct,
)
from ai_trader.trading.trade_case import CaseEvidence, EntryPlan, PostTradeReview, PreTradeCase

APPLICATION_ID = 0x41544A52
SCHEMA_VERSION = 6
MAX_PAYLOAD_BYTES = 1_000_000


class JournalError(ValueError):
    """Journal identity, schema, content or cross-record invariant failed."""


class JournalConflict(JournalError):
    """An existing identifier was retried with different content."""


def _identifier(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise JournalError("Identifier must contain 1-2048 characters.")


def _shape(value, cls):
    if not isinstance(value, dict) or set(value) != {field.name for field in fields(cls)}:
        raise JournalError(f"Invalid {cls.__name__} schema.")
    return dict(value)


def _decimal(value):
    if not isinstance(value, str):
        raise JournalError("Stored Decimal must be a string.")
    value = Decimal(value)
    if not value.is_finite():
        raise JournalError("Stored Decimal must be finite.")
    return value


def _decode_case(value):
    value = _shape(value, PreTradeCase)
    if not isinstance(value["evidence"], list):
        raise JournalError("Stored evidence must be a list.")
    value["evidence"] = tuple(
        CaseEvidence(**_shape(item, CaseEvidence)) for item in value["evidence"]
    )
    if value["plan"] is not None:
        plan = _shape(value["plan"], EntryPlan)
        for key in (
            "quantity_btc",
            "reference_price_usdt",
            "stop_price_usdt",
            "take_profit_price_usdt",
        ):
            plan[key] = _decimal(plan[key])
        value["plan"] = EntryPlan(**plan)
    if value["approved_quantity_btc"] is not None:
        value["approved_quantity_btc"] = _decimal(value["approved_quantity_btc"])
    return PreTradeCase(**value)


def _decode_review(value):
    value = _shape(value, PostTradeReview)
    value["case"] = _decode_case(value["case"])
    value["net_pnl_usdt"] = _decimal(value["net_pnl_usdt"])
    return PostTradeReview(**value)


def _decode_order(value):
    value = _shape(value, PaperEntryOrder)
    value["quantity_btc"] = _decimal(value["quantity_btc"])
    return PaperEntryOrder(**value)


def _decode_exit(value):
    value = _shape(value, PaperExitOrder)
    value["quantity_btc"] = _decimal(value["quantity_btc"])
    return PaperExitOrder(**value)


def _decode_seed(value):
    value = _shape(value, PaperAccountSeed)
    value["initial_cash_usdt"] = _decimal(value["initial_cash_usdt"])
    return PaperAccountSeed(**value)


def _decode_event(value):
    value = _shape(value, PaperOrderEvent)
    for key in ("quantity_btc", "price_usdt", "fee_usdt"):
        if value[key] is not None:
            value[key] = _decimal(value[key])
    return PaperOrderEvent(**value)


def _create_lifecycle_tables(db):
    db.execute("""CREATE TABLE paper_orders (
        order_id TEXT PRIMARY KEY, case_id TEXT NOT NULL UNIQUE REFERENCES cases(case_id),
        payload TEXT NOT NULL, sha256 TEXT NOT NULL,
        recorded_at_ns INTEGER NOT NULL CHECK(recorded_at_ns >= 0))""")
    db.execute("""CREATE TABLE paper_events (
        sequence INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
        order_id TEXT NOT NULL REFERENCES paper_orders(order_id), fill_id TEXT UNIQUE,
        payload TEXT NOT NULL, sha256 TEXT NOT NULL,
        recorded_at_ns INTEGER NOT NULL CHECK(recorded_at_ns >= 0))""")
    db.execute("CREATE INDEX paper_events_by_order ON paper_events(order_id, sequence)")
    for table in ("paper_orders", "paper_events"):
        for action in ("UPDATE", "DELETE"):
            db.execute(f"""CREATE TRIGGER {table}_no_{action.lower()}
                BEFORE {action} ON {table} BEGIN
                SELECT RAISE(ABORT, 'Append-only journal'); END""")


def _upgrade_account_tables(db):
    # Rebuild together without disabling foreign keys. Parent renaming updates the
    # child reference. Copies preserve all payloads, hashes and event sequences.
    db.execute("""CREATE TABLE paper_orders_v3 (
        order_id TEXT PRIMARY KEY, case_id TEXT UNIQUE REFERENCES cases(case_id),
        payload TEXT NOT NULL, sha256 TEXT NOT NULL,
        recorded_at_ns INTEGER NOT NULL CHECK(recorded_at_ns >= 0),
        entry_order_id TEXT REFERENCES paper_orders_v3(order_id),
        CHECK ((case_id IS NULL) != (entry_order_id IS NULL)))""")
    db.execute("""INSERT INTO paper_orders_v3
        (order_id, case_id, payload, sha256, recorded_at_ns)
        SELECT order_id, case_id, payload, sha256, recorded_at_ns FROM paper_orders""")
    db.execute("""CREATE TABLE paper_events_v3 (
        sequence INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
        order_id TEXT NOT NULL REFERENCES paper_orders_v3(order_id), fill_id TEXT UNIQUE,
        payload TEXT NOT NULL, sha256 TEXT NOT NULL,
        recorded_at_ns INTEGER NOT NULL CHECK(recorded_at_ns >= 0))""")
    db.execute("INSERT INTO paper_events_v3 SELECT * FROM paper_events")
    db.execute("DROP TABLE paper_events")
    db.execute("DROP TABLE paper_orders")
    db.execute("ALTER TABLE paper_orders_v3 RENAME TO paper_orders")
    db.execute("ALTER TABLE paper_events_v3 RENAME TO paper_events")
    db.execute("CREATE INDEX paper_events_by_order ON paper_events(order_id, sequence)")
    db.execute("""CREATE TABLE paper_account (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        payload TEXT NOT NULL, sha256 TEXT NOT NULL)""")
    for table in ("paper_orders", "paper_events", "paper_account"):
        for action in ("UPDATE", "DELETE"):
            db.execute(f"""CREATE TRIGGER {table}_no_{action.lower()}
                BEFORE {action} ON {table} BEGIN
                SELECT RAISE(ABORT, 'Append-only journal'); END""")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise JournalError("Migration found invalid foreign keys.")


def _create_gateway_tables(db):
    db.execute("""CREATE TABLE paper_gateway_config (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        payload TEXT NOT NULL, sha256 TEXT NOT NULL)""")
    db.execute("""CREATE TABLE paper_gateway_requests (
        order_id TEXT PRIMARY KEY REFERENCES paper_orders(order_id),
        payload TEXT NOT NULL, sha256 TEXT NOT NULL)""")
    db.execute("""CREATE TABLE paper_risk_checkpoints (
        sequence INTEGER PRIMARY KEY, payload TEXT NOT NULL, sha256 TEXT NOT NULL)""")
    for table in ("paper_gateway_config", "paper_gateway_requests", "paper_risk_checkpoints"):
        for action in ("UPDATE", "DELETE"):
            db.execute(f"""CREATE TRIGGER {table}_no_{action.lower()}
                BEFORE {action} ON {table} BEGIN
                SELECT RAISE(ABORT, 'Append-only journal'); END""")


def _create_runner_tables(db):
    db.execute("""CREATE TABLE paper_runner_config (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        payload TEXT NOT NULL, sha256 TEXT NOT NULL)""")
    db.execute("""CREATE TABLE paper_runner_ticks (
        sequence INTEGER PRIMARY KEY, tick_id TEXT NOT NULL UNIQUE,
        payload TEXT NOT NULL, sha256 TEXT NOT NULL,
        result TEXT NOT NULL, result_sha256 TEXT NOT NULL)""")
    for table in ("paper_runner_config", "paper_runner_ticks"):
        for action in ("UPDATE", "DELETE"):
            db.execute(f"""CREATE TRIGGER {table}_no_{action.lower()}
                BEFORE {action} ON {table} BEGIN
                SELECT RAISE(ABORT, 'Append-only journal'); END""")


def _create_replay_tables(db):
    db.execute("""CREATE TABLE paper_replay_sources (
        source_session TEXT PRIMARY KEY, payload TEXT NOT NULL, sha256 TEXT NOT NULL)""")
    for action in ("UPDATE", "DELETE"):
        db.execute(f"""CREATE TRIGGER paper_replay_sources_no_{action.lower()}
            BEFORE {action} ON paper_replay_sources BEGIN
            SELECT RAISE(ABORT, 'Append-only journal'); END""")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise JournalError("Duplicate stored JSON key.")
        result[key] = value
    return result


def _constant(value):
    raise JournalError(f"Invalid JSON numeric constant: {value}")


def _encode(value):
    payload = json.dumps(asdict(value), default=str, sort_keys=True, allow_nan=False)
    if len(payload.encode()) > MAX_PAYLOAD_BYTES:
        raise JournalError("Journal record is too large.")
    return payload


def _hash(payload):
    return hashlib.sha256(payload.encode()).hexdigest()


def _read(payload, checksum, decoder):
    try:
        if not isinstance(payload, str) or len(payload.encode()) > MAX_PAYLOAD_BYTES:
            raise JournalError("Invalid stored payload.")
        if _hash(payload) != checksum:
            raise JournalError("Stored checksum mismatch.")
        result = decoder(json.loads(payload, object_pairs_hook=_pairs, parse_constant=_constant))
        if _encode(result) != payload:
            raise JournalError("Noncanonical stored record.")
        return result
    except (ValueError, TypeError, ArithmeticError, KeyError) as error:
        raise JournalError(f"Cannot decode journal record: {error}") from error


class TradeJournal:
    """Open existing journals explicitly; create never overwrites an existing file.

    Connections belong to their creating thread. Use separate instances per thread.
    BEGIN IMMEDIATE serializes writers; busy/IO errors propagate and never become
    success. Close connections before moving/backing up database files.
    """

    def __init__(self, path: Path, *, run_id: str, mode: str, read_only: bool = False):
        _identifier(run_id)
        if mode not in ("research_only", "paper") or type(read_only) is not bool:
            raise JournalError("Only explicit research/paper journal modes are supported.")
        self.run_id, self.mode, self.read_only = run_id, mode, read_only
        uri = Path(path).resolve().as_uri() + ("?mode=ro" if read_only else "?mode=rw")
        self._db = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=5)
        try:
            if self._db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
                raise JournalError("Not an ai-trader case journal.")
            if self._db.execute("PRAGMA user_version").fetchone()[0] not in (
                1,
                2,
                3,
                4,
                5,
                SCHEMA_VERSION,
            ):
                raise JournalError("Unsupported journal schema; explicit migration required.")
            metadata = dict(self._db.execute("SELECT key, value FROM metadata"))
            if metadata != {"run_id": run_id, "mode": mode}:
                raise JournalError("Journal run/mode identity mismatch.")
            if self._db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise JournalError("SQLite integrity check failed.")
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.execute("PRAGMA synchronous=FULL")
            if read_only:
                self._db.execute("PRAGMA query_only=ON")
        except BaseException:
            self._db.close()
            raise

    @classmethod
    def create(cls, path: Path, *, run_id: str, mode: str):
        _identifier(run_id)
        if mode not in ("research_only", "paper"):
            raise JournalError("Only research/paper journals may be created.")
        path = Path(path)
        # Exclusive creation, without creating parents or reusing an unrelated database.
        with path.open("xb"):
            pass
        db = sqlite3.connect(path, isolation_level=None)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            db.execute(f"PRAGMA application_id={APPLICATION_ID}")
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            db.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.executemany(
                "INSERT INTO metadata VALUES (?, ?)", [("run_id", run_id), ("mode", mode)]
            )
            db.execute("""CREATE TABLE cases (
                case_id TEXT PRIMARY KEY, payload TEXT NOT NULL, sha256 TEXT NOT NULL,
                recorded_at_ns INTEGER NOT NULL CHECK(recorded_at_ns >= 0))""")
            db.execute("""CREATE TABLE reviews (
                sequence INTEGER PRIMARY KEY, review_id TEXT NOT NULL UNIQUE,
                case_id TEXT NOT NULL REFERENCES cases(case_id), trade_id TEXT NOT NULL,
                payload TEXT NOT NULL, sha256 TEXT NOT NULL,
                recorded_at_ns INTEGER NOT NULL CHECK(recorded_at_ns >= 0))""")
            db.execute("CREATE INDEX reviews_by_case ON reviews(case_id, sequence)")
            db.execute("CREATE INDEX reviews_by_trade ON reviews(trade_id)")
            _create_lifecycle_tables(db)
            _upgrade_account_tables(db)
            _create_gateway_tables(db)
            _create_runner_tables(db)
            _create_replay_tables(db)
            for table in ("metadata", "cases", "reviews"):
                for action in ("UPDATE", "DELETE"):
                    db.execute(f"""CREATE TRIGGER {table}_no_{action.lower()}
                        BEFORE {action} ON {table} BEGIN
                        SELECT RAISE(ABORT, 'Append-only journal'); END""")
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            # Leave the newly owned file for diagnosis; never delete an unrelated file.
            raise
        finally:
            db.close()
        return cls(path, run_id=run_id, mode=mode)

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def _write(self):
        if self.read_only:
            raise JournalError("Journal is read-only.")
        if self._db.in_transaction:
            # Nested journal operations participate in the enclosing atomic paper
            # simulation. A nested failure rolls back its savepoint, not its parent.
            self._db.execute("SAVEPOINT journal_write")
            try:
                yield
                self._db.execute("RELEASE journal_write")
            except BaseException:
                self._db.execute("ROLLBACK TO journal_write")
                self._db.execute("RELEASE journal_write")
                raise
            return
        self._db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self._db.execute("COMMIT")
        except BaseException:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
            raise

    def _case_row(self, case_id):
        return self._db.execute(
            "SELECT payload, sha256 FROM cases WHERE case_id=?", (case_id,)
        ).fetchone()

    def get_case(self, case_id: str) -> PreTradeCase | None:
        _identifier(case_id)
        row = self._case_row(case_id)
        if row is None:
            return None
        case = _read(*row, _decode_case)
        if case.case_id != case_id or case.mode != self.mode:
            raise JournalError("Stored case identity mismatch.")
        return case

    def append_case(self, case: PreTradeCase) -> bool:
        if type(case) is not PreTradeCase or case.mode != self.mode:
            raise JournalError("Case mode/type does not match journal.")
        payload = _encode(case)
        _read(payload, _hash(payload), _decode_case)
        with self._write():
            previous = self.get_case(case.case_id)
            if previous is not None:
                if _encode(previous) != payload:
                    raise JournalConflict("Case ID already has different content.")
                return False
            self._db.execute(
                "INSERT INTO cases VALUES (?, ?, ?, ?)",
                (case.case_id, payload, _hash(payload), time.time_ns()),
            )
        return True

    def append_review(self, review_id: str, review: PostTradeReview) -> bool:
        _identifier(review_id)
        if type(review) is not PostTradeReview:
            raise JournalError("Expected a typed post-trade review.")
        payload = _encode(review)
        _read(payload, _hash(payload), _decode_review)
        with self._write():
            previous = self.get_review(review_id)
            if previous is not None:
                if _encode(previous) != payload:
                    raise JournalConflict("Review ID already has different content.")
                return False
            stored_case = self.get_case(review.case.case_id)
            if stored_case is None or stored_case.sha256 != review.case.sha256:
                raise JournalConflict("Review does not reference the exact stored case.")
            binding = self._db.execute(
                "SELECT case_id FROM reviews WHERE trade_id=? LIMIT 1", (review.trade_id,)
            ).fetchone()
            if binding is not None and binding[0] != review.case.case_id:
                raise JournalConflict("Trade ID is already bound to another case.")
            self._db.execute(
                """INSERT INTO reviews
                (review_id, case_id, trade_id, payload, sha256, recorded_at_ns)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    review_id,
                    review.case.case_id,
                    review.trade_id,
                    payload,
                    _hash(payload),
                    time.time_ns(),
                ),
            )
        return True

    def get_review(self, review_id: str) -> PostTradeReview | None:
        _identifier(review_id)
        row = self._db.execute(
            "SELECT case_id, trade_id, payload, sha256 FROM reviews WHERE review_id=?", (review_id,)
        ).fetchone()
        if row is None:
            return None
        case_id, trade_id, payload, checksum = row
        review = _read(payload, checksum, _decode_review)
        case = self.get_case(case_id)
        if case is None or case.sha256 != review.case.sha256 or review.trade_id != trade_id:
            raise JournalError("Stored review binding mismatch.")
        return review

    def review_ids(self, case_id: str) -> tuple[str, ...]:
        _identifier(case_id)
        return tuple(
            row[0]
            for row in self._db.execute(
                "SELECT review_id FROM reviews WHERE case_id=? ORDER BY sequence", (case_id,)
            )
        )

    def upgrade_schema(self) -> bool:
        """Explicit, atomic v1-v5 -> v6 upgrade. Back up the closed file first."""
        with self._write():
            version = self._db.execute("PRAGMA user_version").fetchone()[0]
            if version == SCHEMA_VERSION:
                return False
            if version not in (1, 2, 3, 4, 5):
                raise JournalError("Unsupported migration source schema.")
            if version == 1:
                _create_lifecycle_tables(self._db)
            if version < 3:
                _upgrade_account_tables(self._db)
            if version < 4:
                _create_gateway_tables(self._db)
            if version < 5:
                _create_runner_tables(self._db)
            _create_replay_tables(self._db)
            self._db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        return True

    def _paper(self):
        if self.mode != "paper":
            raise JournalError("Order lifecycle is paper-only.")
        if self._db.execute("PRAGMA user_version").fetchone()[0] not in (
            2,
            3,
            4,
            5,
            SCHEMA_VERSION,
        ):
            raise JournalError("Explicit schema upgrade required for order lifecycle.")

    def _account_schema(self):
        self._paper()
        if self._db.execute("PRAGMA user_version").fetchone()[0] not in (3, 4, 5, SCHEMA_VERSION):
            raise JournalError("Explicit schema upgrade required for paper accounts/exits.")

    def _validate_order_case(self, order):
        case = self.get_case(order.case_id)
        if (
            case is None
            or case.sha256 != order.case_sha256
            or case.action != "ENTER_LONG"
            or case.risk_verdict != "APPROVED"
            or order.quantity_btc > case.approved_quantity_btc
            or not case.decision_at_ns <= order.requested_at_ns < case.plan.expires_at_ns
        ):
            raise JournalError("Paper entry must bind to an exact, unexpired approved case.")

    def get_order(self, order_id: str) -> PaperEntryOrder | PaperExitOrder | None:
        self._paper()
        _identifier(order_id)
        row = self._db.execute(
            "SELECT case_id, payload, sha256 FROM paper_orders WHERE order_id=?", (order_id,)
        ).fetchone()
        if row is None:
            return None
        case_id, payload, checksum = row
        if case_id is None:
            self._account_schema()
            order = _read(payload, checksum, _decode_exit)
            binding = self._db.execute(
                "SELECT entry_order_id FROM paper_orders WHERE order_id=?", (order_id,)
            ).fetchone()[0]
            # Read the parent directly, avoiding recursive traversal of corrupt exit cycles.
            parent = self._db.execute(
                "SELECT case_id FROM paper_orders WHERE order_id=?", (binding,)
            ).fetchone()
            if (
                order.order_id != order_id
                or order.entry_order_id != binding
                or parent is None
                or parent[0] is None
            ):
                raise JournalError("Stored exit binding mismatch.")
            self.get_order(binding)
            return order
        order = _read(payload, checksum, _decode_order)
        if order.order_id != order_id or order.case_id != case_id:
            raise JournalError("Stored order binding mismatch.")
        self._validate_order_case(order)
        return order

    def append_order(self, order: PaperEntryOrder) -> bool:
        self._paper()
        if type(order) is not PaperEntryOrder:
            raise JournalError("Expected typed paper-entry order.")
        payload = _encode(order)
        _read(payload, _hash(payload), _decode_order)
        with self._write():
            previous = self.get_order(order.order_id)
            if previous is not None:
                if _encode(previous) != payload:
                    raise JournalConflict("Order ID already has different content.")
                if self._has_account():
                    self.account_state()
                return False
            self._validate_order_case(order)
            if self._db.execute(
                "SELECT 1 FROM paper_orders WHERE case_id=?", (order.case_id,)
            ).fetchone():
                raise JournalConflict("Case already has an entry order; require a fresh risk case.")
            self._db.execute(
                "INSERT INTO paper_orders "
                "(order_id, case_id, payload, sha256, recorded_at_ns) VALUES (?, ?, ?, ?, ?)",
                (order.order_id, order.case_id, payload, _hash(payload), time.time_ns()),
            )
            if self._has_account():
                self._validate_request_time(order.requested_at_ns)
                self.account_state()
        return True

    def order_ids(self) -> tuple[str, ...]:
        self._paper()
        return tuple(
            row[0]
            for row in self._db.execute("SELECT order_id FROM paper_orders ORDER BY order_id")
        )

    def order_events(self, order_id: str) -> tuple[PaperOrderEvent, ...]:
        self._paper()
        _identifier(order_id)
        events = []
        for event_id, fill_id, payload, checksum in self._db.execute(
            "SELECT event_id, fill_id, payload, sha256 FROM paper_events "
            "WHERE order_id=? ORDER BY sequence",
            (order_id,),
        ):
            event = _read(payload, checksum, _decode_event)
            if (event.event_id, event.fill_id, event.order_id) != (event_id, fill_id, order_id):
                raise JournalError("Stored event binding mismatch.")
            events.append(event)
        return tuple(events)

    def order_state(self, order_id: str):
        order = self.get_order(order_id)
        if order is None:
            raise JournalError("Unknown paper order.")
        try:
            return reconstruct(order, self.order_events(order_id))
        except ValueError as error:
            raise JournalError(f"Invalid stored lifecycle: {error}") from error

    def append_order_event(self, event: PaperOrderEvent) -> bool:
        self._paper()
        if type(event) is not PaperOrderEvent:
            raise JournalError("Expected typed paper-order event.")
        if event.kind == "CANCEL_CONFIRMED":
            self._account_schema()
        payload = _encode(event)
        _read(payload, _hash(payload), _decode_event)
        with self._write():
            previous = self._db.execute(
                "SELECT order_id, payload, sha256 FROM paper_events WHERE event_id=?",
                (event.event_id,),
            ).fetchone()
            if previous is not None:
                self.order_state(previous[0])
                if previous[1] != payload:
                    raise JournalConflict("Event ID already has different content.")
                if self._has_account():
                    self.account_state()
                return False
            if (
                event.fill_id is not None
                and self._db.execute(
                    "SELECT 1 FROM paper_events WHERE fill_id=?", (event.fill_id,)
                ).fetchone()
            ):
                raise JournalConflict("Fill ID already recorded; retry the original event ID.")
            order = self.get_order(event.order_id)
            if order is None:
                raise JournalError("Event has no durable order.")
            try:
                reconstruct(order, self.order_events(event.order_id) + (event,))
            except ValueError as error:
                raise JournalError(f"Invalid lifecycle event: {error}") from error
            self._db.execute(
                "INSERT INTO paper_events "
                "(event_id, order_id, fill_id, payload, sha256, recorded_at_ns) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.order_id,
                    event.fill_id,
                    payload,
                    _hash(payload),
                    time.time_ns(),
                ),
            )
            if self._has_account():
                self.account_state()
        return True

    def _has_account(self):
        return (
            self._db.execute("PRAGMA user_version").fetchone()[0] in (3, 4, 5, SCHEMA_VERSION)
            and self._db.execute("SELECT 1 FROM paper_account").fetchone() is not None
        )

    def account_seed(self) -> PaperAccountSeed | None:
        self._account_schema()
        row = self._db.execute(
            "SELECT payload, sha256 FROM paper_account WHERE singleton=1"
        ).fetchone()
        return None if row is None else _read(*row, _decode_seed)

    def initialize_account(self, seed: PaperAccountSeed) -> bool:
        """Opt-in flat-start account; never invent funding for an existing order history."""
        self._account_schema()
        if type(seed) is not PaperAccountSeed:
            raise JournalError("Expected typed paper-account seed.")
        payload = _encode(seed)
        _read(payload, _hash(payload), _decode_seed)
        with self._write():
            previous = self.account_seed()
            if previous is not None:
                if _encode(previous) != payload:
                    raise JournalConflict("Paper account funding is immutable.")
                return False
            if self.order_ids():
                raise JournalError("Account must be initialized before any orders.")
            self._db.execute(
                "INSERT INTO paper_account VALUES (1, ?, ?)", (payload, _hash(payload))
            )
        return True

    def _validate_request_time(self, requested_at_ns):
        state = self.account_state()
        latest_request = max(
            (self.get_order(order_id).requested_at_ns for order_id in self.order_ids()),
            default=state.last_observed_at_ns,
        )
        if requested_at_ns < max(latest_request, state.last_observed_at_ns):
            raise JournalError("Account request time regressed.")

    def append_exit_order(self, order: PaperExitOrder) -> bool:
        self._account_schema()
        if type(order) is not PaperExitOrder:
            raise JournalError("Expected typed paper-exit order.")
        payload = _encode(order)
        _read(payload, _hash(payload), _decode_exit)
        with self._write():
            previous = self.get_order(order.order_id)
            if previous is not None:
                if _encode(previous) != payload:
                    raise JournalConflict("Order ID already has different content.")
                self.account_state()
                return False
            parent = self.get_order(order.entry_order_id)
            if type(parent) is not PaperEntryOrder:
                raise JournalError("Exit must reference a recorded entry.")
            self._validate_request_time(order.requested_at_ns)
            self._db.execute(
                "INSERT INTO paper_orders "
                "(order_id, entry_order_id, payload, sha256, recorded_at_ns) "
                "VALUES (?, ?, ?, ?, ?)",
                (order.order_id, order.entry_order_id, payload, _hash(payload), time.time_ns()),
            )
            self.account_state()
        return True

    def account_state(self):
        """Recover under one SQLite read snapshot (or the caller's write transaction)."""
        self._account_schema()
        owns_transaction = not self._db.in_transaction
        if owns_transaction:
            self._db.execute("BEGIN")
        try:
            seed = self.account_seed()
            if seed is None:
                raise JournalError("Paper account has not been initialized.")
            orders = tuple(self.get_order(order_id) for order_id in self.order_ids())
            events = []
            for event_id, order_id, fill_id, payload, checksum in self._db.execute(
                "SELECT event_id, order_id, fill_id, payload, sha256 "
                "FROM paper_events ORDER BY sequence"
            ):
                event = _read(payload, checksum, _decode_event)
                if (event.event_id, event.order_id, event.fill_id) != (event_id, order_id, fill_id):
                    raise JournalError("Stored account event binding mismatch.")
                events.append(event)
            return recover_account(seed, orders, tuple(events))
        except (ValueError, ArithmeticError) as error:
            raise JournalError(f"Invalid paper account: {error}") from error
        finally:
            if owns_transaction:
                self._db.execute("ROLLBACK")
