"""Bounded causal 6E quote simulator with continuous liabilities, never broker fills.

Does not read target labels, fit/predict, route orders, or reset an account by day.
Every durable result needs a separate complete-input reconstruction before use.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

from ai_trader.research import six_e_position_ledger as ledger

study, target, rules = ledger.study, ledger.target, ledger.study.rules
MAX_SESSIONS, MAX_DECISIONS, MAX_QUOTES = 3, 43_200, 2_000_000
MAX_EVENTS, MAX_SECONDS, MAX_OUTPUT_BYTES = 2000, 300, 16 * 1024**2
COOLDOWN = study.exits.COOLDOWN
POLICIES = (*rules.POLICIES[:3], "no_trade")
DECISION_FIELDS = {
    "source_session",
    "contract",
    "partition",
    "decision_ts_ns",
    "eligible",
    "features",
    "execution_features",
    "published_cursor",
}


def _flags() -> dict:
    return {
        name: False
        for name in (
            "training_eligible",
            "strategy_scoring_allowed",
            "trading_enabled",
            "promotion_allowed",
            "broker_execution_confirmed",
            "receipt_provenance_verified",
            "independent_holdout",
            "qwen_training",
            "cpu_training",
            "reserved_outcomes_opened",
            "execution_assumptions_validated",
        )
    }


FLAGS = _flags()


def protocol() -> dict:
    return {
        "version": "six_e_continuous_quote_simulator_v1",
        "scope": "Complete bounded declared development fixtures; one fixed causal policy "
        "and one contract at a time, not a funded account or CFD execution",
        "decisions": "Allowlisted causal features and eligibility only; immediately after "
        "the explicit first native cursor at that receive timestamp, before equal-time suffix",
        "execution": "Original 100ms entry/exit delay plus inclusive 1s wait; first widened "
        "entry refuses, crossed widened exits retained; one full contract assumed filled",
        "holding": "15s hold timer wins equality; bracket trigger quotes strictly before "
        "timer, original +3/-3 net ticks after one extra tick; original 10s cooldown retained",
        "entry_timeout": "Simulator no-entry refusal only; not a broker cancellation proof",
        "unknown": "Exit deadline leaves inventory/reservation UNKNOWN forever; later quotes "
        "are references only, no retry, cancellation, standing-quote fill or daily reset",
        "coverage": "12-16 UTC windows only; no overnight or excluded-date price inference; "
        "new dated contract cannot close or mark old contract inventory",
        "costs": "Crossed supplied quotes plus one assumed extra round-trip tick per contract; "
        "closed portions are contract-ticks, not PnL, margin, capital or profitability",
        "resume": "No automatic resume; pending entry/timers/cooldown reconstructed from "
        "complete inputs and pinned event plan, partial attempts retained as failures",
        "limits": {
            "sessions": MAX_SESSIONS,
            "decisions": MAX_DECISIONS,
            "quotes_per_session": MAX_QUOTES,
            "events": MAX_EVENTS,
            "seconds": MAX_SECONDS,
            "sidecar_bytes": MAX_OUTPUT_BYTES,
        },
        "flags": _flags(),
    }


def fingerprints() -> dict:
    return {
        **ledger._fingerprints(),
        Path(__file__).name: study.common.hash_file(Path(__file__), 1024**2),
    }


def _json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value) -> str:
    return hashlib.sha256(value).hexdigest()


def decision_input(row: dict, published_cursor: int) -> dict:
    """Project original label-bearing rows without consulting their future fields."""
    ledger._session(row["source_session"])  # Calendar guard BEFORE features/prices.
    projected = {k: row[k] for k in DECISION_FIELDS - {"published_cursor"}}
    projected["features"] = dict(projected["features"])
    projected["execution_features"] = dict(projected["execution_features"])
    projected["published_cursor"] = published_cursor
    return projected


@dataclass(frozen=True, slots=True)
class ReplaySession:
    source_session: str
    contract: str
    source_sha256: str
    decisions: tuple[dict, ...]
    quotes: np.ndarray


def _freeze(sessions: tuple[ReplaySession, ...]) -> tuple[ReplaySession, ...]:
    if type(sessions) is not tuple or not 1 <= len(sessions) <= MAX_SESSIONS:
        raise ValueError("A complete bounded tuple of sessions is required")
    last_day, total, result = None, 0, []
    for session in sessions:
        if type(session) is not ReplaySession:
            raise ValueError("Typed replay session required")
        day = session.source_session
        ledger._session(day)  # Refuse reserved BEFORE any quote access.
        if last_day is not None and day <= last_day:
            raise ValueError("Unique chronological sessions required")
        last_day = day
        if session.contract != study.census.dated_contract(day):
            raise ValueError("Declared development dated contract differs")
        ledger._pin(session.source_sha256)
        if type(session.decisions) is not tuple or len(session.decisions) > 14_400:
            raise ValueError("Complete bounded decision tuple required")
        total += len(session.decisions)
        if total > MAX_DECISIONS:
            raise ValueError("Replay decision bound exceeded")
        q = session.quotes
        if (
            not isinstance(q, np.ndarray)
            or q.dtype != np.dtype(np.int64)
            or q.ndim != 2
            or q.shape[1] != 3
            or len(q) > MAX_QUOTES
        ):
            raise ValueError("Bounded native int64 time/bid/ask quotes required")
        q = np.array(q, dtype="<i8", copy=True)
        if len(q):
            target.validate_quotes(q, day)
        elif session.decisions:
            raise ValueError("Decisions require their published completed quotes")
        q.setflags(write=False)
        rows, last_ts = [], None
        for row in session.decisions:
            if type(row) is not dict or set(row) != DECISION_FIELDS:
                raise ValueError("Only feature/clock decision fields allowed; no future labels")
            if row["source_session"] != day or row["contract"] != session.contract:
                raise ValueError("Decision/session contract identity differs")
            copied = decision_input(row, row["published_cursor"])
            rules.inputs(copied)
            now, cursor = copied["decision_ts_ns"], copied["published_cursor"]
            if type(copied["eligible"]) is not bool:
                raise ValueError("Causal eligibility must be Boolean")
            ledger._integer(cursor, 0, len(q) - 1)
            if (
                int(q[cursor, 0]) != now
                or cursor != int(np.searchsorted(q[:, 0], now, side="left"))
                or (last_ts is not None and now - last_ts < target.SECOND)
            ):
                raise ValueError("Decision must follow its first native quote, in causal order")
            last_ts = now
            rows.append(copied)
        result.append(ReplaySession(day, session.contract, session.source_sha256, tuple(rows), q))
    return tuple(result)


def _manifest(sessions: tuple[ReplaySession, ...]) -> dict:
    return {
        "version": "six_e_feature_quote_fixture_v1",
        "sessions": [
            {
                "source_session": s.source_session,
                "contract": s.contract,
                "role": study.data.role_for_day(s.source_session),
                "source_sha256": s.source_sha256,
                "decisions": len(s.decisions),
                "decisions_sha256": _digest(_json(s.decisions)),
                "quotes": len(s.quotes),
                "quotes_sha256": _digest(s.quotes.tobytes(order="C")),
            }
            for s in sessions
        ],
    }


def input_manifest(sessions: tuple[ReplaySession, ...]) -> dict:
    return _manifest(_freeze(sessions))


def manifest_pin(sessions: tuple[ReplaySession, ...]) -> str:
    return _digest(_json(input_manifest(sessions)))


@dataclass(frozen=True, slots=True)
class ReplayPlan:
    config: ledger.ScenarioConfig
    inputs: tuple[ReplaySession, ...]
    manifest: dict
    source_pins: dict
    events: tuple[ledger.Observation, ...]
    receipts: tuple[dict, ...]
    decisions: tuple[dict, ...]
    sessions: tuple[dict, ...]
    terminal_state: ledger.LedgerState
    checkpoint: dict


class _Engine:
    def __init__(self, config):
        self.config = config
        genesis = ledger._hash(ledger._metadata(config))
        self.state = ledger.LedgerState(0, genesis, None, 0, None, None, None, 0, 0, 0, 0)
        self.events, self.receipts, self.decisions, self.sessions = [], [], [], []
        self.pending, self.hold, self.exit_deadline = None, None, None
        self.cooldown, self.attempts = 0, 0
        self.started = time.monotonic()

    def budget(self):
        if time.monotonic() - self.started > MAX_SECONDS:
            raise TimeoutError("Complete replay deadline exceeded; no successful-prefix result")

    def emit(self, cls, now, **values):
        if len(self.events) >= min(MAX_EVENTS, ledger.MAX_EVENTS):
            raise ValueError("Complete replay event bound exceeded")
        event = cls(f"event-{len(self.events) + 1:06d}", self.day, now, **values)
        raw = ledger._record(event)
        pin = ledger._hash(self.state.tip_sha256.encode() + b"\n" + raw)
        self.state = replace(
            ledger._apply(self.state, event, self.config),
            sequence=self.state.sequence + 1,
            tip_sha256=pin,
        )
        self.events.append(event)

    def receipt(self, phase, cursor, now, price, position_id):
        value = {
            "version": protocol()["version"],
            "phase": phase,
            "source_manifest_sha256": self.config.source_manifest_sha256,
            "scenario_id": self.config.scenario_id,
            "policy_id": self.config.policy_id,
            "exit_plan": self.config.exit_plan,
            "source_session": self.day,
            "contract": self.contract,
            "native_cursor": cursor,
            "executed_at_ns": now,
            "price_nano": price,
            "quantity_contracts": 1,
            "position_id": position_id,
            "execution_confirmed": False,
            "broker_execution_confirmed": False,
        }
        pin = _digest(_json(value))
        evidence = f"receipt-{len(self.receipts) + 1:06d}"
        self.receipts.append({"evidence_id": evidence, "sha256": pin, "receipt": value})
        return {"evidence_id": evidence, "paper_receipt_sha256": pin}

    def request_exit(self, now, reason):
        p = self.state.position
        self.emit(
            ledger.ExitIntent,
            now,
            request_id=f"exit-{p.position_id}",
            position_id=p.position_id,
            quantity_contracts=p.remaining_contracts,
        )
        self.hold = None
        self.exit_deadline = now + target.EXIT_DELAY + target.WAIT
        self.triggers[reason] += 1

    def advance(self, now, inclusive=False):
        while True:
            due = []
            if self.pending and (
                self.pending["deadline_ns"] < now
                or inclusive
                and self.pending["deadline_ns"] == now
            ):
                due.append((self.pending["deadline_ns"], "entry"))
            if self.hold is not None and self.hold <= now:
                due.append((self.hold, "hold"))
            if self.exit_deadline is not None and (
                self.exit_deadline < now or inclusive and self.exit_deadline == now
            ):
                due.append((self.exit_deadline, "exit"))
            if not due:
                return
            stamp, kind = min(due)
            if kind == "entry":
                self.pending = None
                self.cooldown = stamp + COOLDOWN
                self.counts["entry_timeout_refusals"] += 1
            elif kind == "hold":
                self.request_exit(stamp, "timeout")
            else:
                self.emit(
                    ledger.UnresolvedExit,
                    stamp,
                    request_id=self.state.reservation.request_id,
                    reason="No fresh completed quote by declared simulator deadline",
                )
                self.exit_deadline = None
                self.counts["unresolved_exits"] += 1

    def quote(self, cursor, q):
        now, bid, ask = map(int, q)
        self.advance(now)  # Hold equality first; candidate deadline equality stays eligible.
        if self.pending and now >= self.pending["target_ns"]:
            pending, self.pending = self.pending, None
            if ask - bid != target.TICK:
                self.cooldown = now + COOLDOWN
                self.counts["entry_spread_refusals"] += 1
            else:
                price = ask if pending["side"] == "long" else bid
                self.emit(
                    ledger.EntryFill,
                    now,
                    position_id=pending["position_id"],
                    contract=self.contract,
                    side=pending["side"],
                    quantity_contracts=1,
                    price_nano=price,
                    executed_at_ns=now,
                    **self.receipt("entry", cursor, now, price, pending["position_id"]),
                )
                self.hold = now + target.HOLD
                self.counts["entry_fills"] += 1
        p, r = self.state.position, self.state.reservation
        if p is None or p.contract != self.contract:
            return
        if r is not None:
            if r.status == "PENDING" and now >= r.requested_at_ns + target.EXIT_DELAY:
                price = bid if p.side == "long" else ask
                self.emit(
                    ledger.ExitFill,
                    now,
                    request_id=r.request_id,
                    contract=p.contract,
                    quantity_contracts=1,
                    price_nano=price,
                    executed_at_ns=now,
                    **self.receipt("exit", cursor, now, price, p.position_id),
                )
                self.exit_deadline = None
                self.cooldown = now + COOLDOWN
                self.counts["exit_fills"] += 1
            return  # UNKNOWN is never filled by a later quote.
        if self.config.exit_plan == "bracket_exit":
            net = (
                (bid - p.entry_price_nano) // target.TICK
                if p.side == "long"
                else (p.entry_price_nano - ask) // target.TICK
            ) - target.COST
            if net >= target.TARGET or net <= target.STOP:
                self.request_exit(now, "target" if net >= target.TARGET else "stop")

    def decision(self, row, direction):
        now = row["decision_ts_ns"]
        eligible = row["eligible"] and now + target.MARGIN < self.end
        if not eligible:
            disposition = "ineligible"
        elif self.state.entry_recording_blocked:
            disposition = "inventory_blocked"
        elif self.pending:
            disposition = "entry_pending_blocked"
        elif now < self.cooldown:
            disposition = "cooldown"
        elif not direction:
            disposition = "no_signal"
        else:
            disposition = "entry_selected"
            self.attempts += 1
            self.pending = {
                "position_id": f"position-{self.attempts}",
                "side": "long" if direction > 0 else "short",
                "decision_ts_ns": now,
                "target_ns": now + target.ENTRY_DELAY,
                "deadline_ns": now + target.ENTRY_DELAY + target.WAIT,
            }
        self.dispositions[disposition] += 1
        self.counts["signals"] += int(direction != 0)
        self.decisions.append(
            {
                "source_session": self.day,
                "decision_ts_ns": now,
                "published_cursor": row["published_cursor"],
                "direction": int(direction),
                "disposition": disposition,
            }
        )

    def session(self, session):
        self.day, self.contract = session.source_session, session.contract
        start, self.end = target.window(self.day)
        self.counts, self.triggers, self.dispositions = Counter(), Counter(), Counter()
        self.emit(ledger.SessionBoundary, start)
        directions = (
            rules.rules(list(session.decisions))[self.config.policy_id]
            if session.decisions and self.config.policy_id != "no_trade"
            else np.zeros(len(session.decisions), dtype=np.int8)
        )
        rows, index = session.decisions, 0
        for cursor, q in enumerate(session.quotes):
            if cursor % 4096 == 0:
                self.budget()
            self.quote(cursor, q)
            if index < len(rows) and rows[index]["published_cursor"] == cursor:
                self.decision(rows[index], int(directions[index]))
                index += 1
        if index != len(rows):
            raise ValueError("Incomplete decision publication coverage")
        self.advance(self.end, inclusive=True)  # Timers fire even with no subsequent quote.
        p = self.state.position
        if p is not None and p.contract == self.contract and len(session.quotes):
            now, bid, ask = map(int, session.quotes[-1])
            if now >= p.executed_at_ns:
                self.emit(
                    ledger.QuoteReference,
                    self.end,
                    contract=p.contract,
                    quote_at_ns=now,
                    native_cursor=len(session.quotes) - 1,
                    bid_nano=bid,
                    ask_nano=ask,
                )
        self.emit(ledger.SessionBoundary, self.end)
        if sum(self.dispositions.values()) != len(rows):
            raise ValueError("Every original decision disposition required")
        self.sessions.append(
            {
                "source_session": self.day,
                "contract": self.contract,
                "role": study.data.role_for_day(self.day),
                "decisions": len(rows),
                "quotes": len(session.quotes),
                "counts": dict(self.counts),
                "triggers": dict(self.triggers),
                "dispositions": dict(self.dispositions),
                "carried_contracts": 0 if p is None else p.remaining_contracts,
                "ledger_sequence": self.state.sequence,
                "ledger_tip_sha256": self.state.tip_sha256,
            }
        )
        self.budget()


def build_plan(sessions: tuple[ReplaySession, ...], config: ledger.ScenarioConfig) -> ReplayPlan:
    if (
        type(config) is not ledger.ScenarioConfig
        or config.policy_id not in POLICIES
        or config.max_position_contracts != 1
        or config.extra_round_trip_ticks_per_contract != target.COST
    ):
        raise ValueError("One fixed causal/idle policy, contract and original cost required")
    frozen = _freeze(sessions)
    manifest = _manifest(frozen)
    if config.source_manifest_sha256 != _digest(_json(manifest)):
        raise ValueError("Configuration must pin the complete feature/quote fixture")
    pins = fingerprints()
    engine = _Engine(config)
    for session in frozen:
        engine.session(session)
    if fingerprints() != pins:
        raise ValueError("Replay source changed during planning")
    return ReplayPlan(
        config,
        frozen,
        manifest,
        pins,
        tuple(engine.events),
        tuple(engine.receipts),
        tuple(engine.decisions),
        tuple(engine.sessions),
        engine.state,
        {
            "pending_entry": engine.pending,
            "hold_at_ns": engine.hold,
            "exit_deadline_ns": engine.exit_deadline,
            "cooldown_until_ns": engine.cooldown,
        },
    )


def _plan_payload(plan: ReplayPlan) -> dict:
    return {
        "protocol": protocol(),
        "config": asdict(plan.config),
        "manifest": plan.manifest,
        "source_pins": plan.source_pins,
        "events": [json.loads(ledger._record(e)) for e in plan.events],
        "receipts": plan.receipts,
        "decisions": plan.decisions,
        "sessions": plan.sessions,
        "terminal_state": asdict(plan.terminal_state),
        "checkpoint": plan.checkpoint,
    }


def _check_plan(plan: ReplayPlan) -> None:
    if type(plan) is not ReplayPlan or plan.source_pins != fingerprints():
        raise ValueError("Typed unchanged-source replay plan required")
    recomputed = build_plan(plan.inputs, plan.config)
    if _json(_plan_payload(plan)) != _json(_plan_payload(recomputed)):
        raise ValueError("Replay plan differs from complete causal reconstruction")


def _sidecars(plan: ReplayPlan) -> dict[str, bytes]:
    raw = {
        "events.jsonl": b"".join(ledger._record(e) + b"\n" for e in plan.events),
        "receipts.jsonl": b"".join(_json(r) + b"\n" for r in plan.receipts),
        "decisions.jsonl": b"".join(_json(d) + b"\n" for d in plan.decisions),
    }
    if any(len(value) > MAX_OUTPUT_BYTES for value in raw.values()):
        raise ValueError("Complete replay sidecar byte bound exceeded")
    return raw


def _request(plan: ReplayPlan) -> dict:
    return {
        "protocol": protocol(),
        "config": asdict(plan.config),
        "manifest": plan.manifest,
        "source_pins": plan.source_pins,
        "plan_sha256": _digest(_json(_plan_payload(plan))),
        "sidecars": {
            name: {"bytes": len(raw), "sha256": _digest(raw)}
            for name, raw in _sidecars(plan).items()
        },
        "flags": _flags(),
    }


def _write(path: Path, raw: bytes):
    if len(raw) > MAX_OUTPUT_BYTES:
        raise ValueError("Replay artifact byte bound exceeded")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _output(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    ledger._safe_path(path / "scenario.sqlite")
    return path


def _report(plan: ReplayPlan, request_pin: str) -> dict:
    return {
        "status": "completed_continuous_quote_simulation_not_validation",
        "request_sha256": request_pin,
        "protocol": protocol(),
        "source_pins": plan.source_pins,
        "sessions": plan.sessions,
        "terminal_state": asdict(plan.terminal_state),
        "checkpoint": plan.checkpoint,
        "flags": _flags(),
        "complete_simulated_net_contract_ticks": (
            plan.terminal_state.complete_simulated_net_contract_ticks
        ),
    }


def write_plan(plan: ReplayPlan, output: Path) -> dict:
    """Exclusive bounded offline write; failure evidence remains, never an automatic retry."""
    started = time.monotonic()
    _check_plan(plan)  # All input/state/event bounds verified BEFORE claiming output.
    output, sidecars, request = _output(output), _sidecars(plan), _request(plan)
    output.mkdir(exist_ok=False)
    try:
        raw = _json(request)
        _write(output / "request.json", raw)
        request_pin = _digest(raw)
        for name, raw in sidecars.items():
            _write(output / name, raw)
        with ledger.ScenarioLedger.create(output / "scenario.sqlite", plan.config) as account:
            tip = account.snapshot().tip_sha256
            for event in plan.events:
                if time.monotonic() - started > MAX_SECONDS:
                    raise TimeoutError("Complete durable replay deadline exceeded")
                if account.append(event, expected_tip_sha256=tip) is not True:
                    raise ValueError("Fresh journal cannot contain pre-existing event identities")
                tip = _digest(tip.encode() + b"\n" + ledger._record(event))
            if account.snapshot(expected_tip_sha256=tip) != plan.terminal_state:
                raise ValueError("Durable terminal account differs from complete replay")
        _check_plan(plan)
        if time.monotonic() - started > MAX_SECONDS:
            raise TimeoutError("Complete durable replay verification deadline exceeded")
        report = _report(plan, request_pin)
        _write(output / "completion.json", _json(report))
        return report
    except BaseException as exc:
        failure = {
            "status": "failed_continuous_quote_simulation",
            "exception_type": type(exc).__name__,
            "reason": str(exc)[:512],
            "flags": _flags(),
        }
        if not (output / "failure.json").exists():
            _write(output / "failure.json", _json(failure))
        raise


def _read(path: Path, pin: str) -> bytes:
    ledger._pin(pin)
    ledger._safe_path(path.parent / "scenario.sqlite")
    if path.is_symlink() or os.path.isjunction(path):
        raise ValueError("Replay evidence cannot be linked")
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        if before.st_size > MAX_OUTPUT_BYTES:
            raise ValueError("Replay evidence exceeds byte bound")
        raw = handle.read(MAX_OUTPUT_BYTES + 1)
        after = os.fstat(handle.fileno())
    if (
        len(raw) > MAX_OUTPUT_BYTES
        or _digest(raw) != pin
        or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
    ):
        raise ValueError("Replay content pin or stable-read guard differs")
    return raw


def verify_plan(
    inputs: tuple[ReplaySession, ...],
    config: ledger.ScenarioConfig,
    output: Path,
    request_sha256: str,
    completion_sha256: str,
) -> dict:
    """Independent full reconstruction, no writes, source repair or model calls."""
    started = time.monotonic()
    plan, output = build_plan(inputs, config), _output(output)
    if (output / "failure.json").exists():
        raise ValueError("Failure evidence forbids successful-subset verification")
    request, report = _request(plan), _report(plan, request_sha256)
    if _read(output / "request.json", request_sha256) != _json(request) or _read(
        output / "completion.json", completion_sha256
    ) != _json(report):
        raise ValueError("Replay request or complete report differs from reconstruction")
    for name, raw in _sidecars(plan).items():
        if _read(output / name, _digest(raw)) != raw:
            raise ValueError("Every complete native-derived receipt/audit event required")
    with ledger.ScenarioLedger(output / "scenario.sqlite", config) as account:
        if (
            account.snapshot(expected_tip_sha256=plan.terminal_state.tip_sha256)
            != plan.terminal_state
        ):
            raise ValueError("Complete journal sequence, head or state differs")
    _check_plan(plan)
    if time.monotonic() - started > MAX_SECONDS:
        raise TimeoutError("Complete replay verifier deadline exceeded")
    return {
        "status": "verified_continuous_quote_simulation_not_validation",
        "request_sha256": request_sha256,
        "completion_sha256": completion_sha256,
        "sessions": len(plan.sessions),
        "decisions": len(plan.decisions),
        "events": len(plan.events),
        "receipts": len(plan.receipts),
        "terminal_state": asdict(plan.terminal_state),
        "checkpoint": plan.checkpoint,
        "complete_simulated_net_contract_ticks": (
            plan.terminal_state.complete_simulated_net_contract_ticks
        ),
        "flags": _flags(),
    }
