"""One bounded public BTCUSDT capture with durable, receipt-causal paper decisions.

No credentials, private exchange endpoint, live order route, model call, retry,
or automatic resume. A failed/incomplete session retains its capture and journal
for audit; it can never be promoted to a completed paper result.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass, replace
from decimal import Decimal, localcontext
from pathlib import Path

from ai_trader.ingestion.capture_failure import failure_details, safe_error_type
from ai_trader.ingestion.collect_combined import (
    CaptureLimits,
    DurableCaptureRecord,
    collect,
)
from ai_trader.research.microstructure_trial import (
    _decode_gateway,
    _decode_policy,
    _decode_replay,
    _environment,
)
from ai_trader.trading.capture_replay import (
    CaptureReplay,
    CaptureReplayConfig,
    IncrementalCaptureFrames,
    ReplayFrame,
    _implementation_hash,
)
from ai_trader.trading.durable_paper_gateway import DurablePaperGateway, PaperGatewayConfig
from ai_trader.trading.microstructure_policy import (
    MicrostructurePolicyConfig,
    ResearchRiskSnapshot,
    assess_microstructure,
)
from ai_trader.trading.paper_account import PaperAccountSeed
from ai_trader.trading.paper_lifecycle import _money, _timestamp
from ai_trader.trading.paper_runner import PaperRunner, PaperRunnerConfig
from ai_trader.trading.trade_case import CaseEvidence, PreTradeCase, _digest
from ai_trader.trading.trade_journal import (
    JournalConflict,
    TradeJournal,
    _constant,
    _decimal,
    _encode,
    _hash,
    _identifier,
    _pairs,
)

PLAN_VERSION = "prospective_realtime_paper_v1"
MAX_PLAN_BYTES = 100_000
MAX_PRE_SNAPSHOT_EVENTS = 5_000
MAX_PRE_SNAPSHOT_BYTES = 4 * 1024 * 1024
MAX_PAPER_EVENTS = 10_000
MAX_PAPER_BYTES = 8 * 1024 * 1024
MAX_MANIFEST_BYTES = 1_000_000
REALTIME_LIMITS = CaptureLimits(max_events=MAX_PAPER_EVENTS, max_bytes=MAX_PAPER_BYTES)


def _capture_sha256(path: Path) -> str:
    with Path(path).open("rb") as source:
        raw = source.read(MAX_PAPER_BYTES + 1)
    if not raw or len(raw) > MAX_PAPER_BYTES:
        raise ValueError("Paper capture is empty or exceeds its byte budget.")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class RealtimePaperPlan:
    plan_id: str
    source_session: str
    registered_at_ns: int
    policy: MicrostructurePolicyConfig
    replay: CaptureReplayConfig
    gateway: PaperGatewayConfig
    initial_cash_usdt: Decimal
    max_decision_delay_ns: int
    max_action_event_lag_ns: int
    implementation_sha256: str
    environment_json: str
    schema_version: int = 1
    version: str = PLAN_VERSION
    mode: str = "paper"
    promotion_allowed: bool = False

    def __post_init__(self):
        _identifier(self.plan_id)
        _identifier(self.source_session)
        _timestamp(self.registered_at_ns)
        _timestamp(self.max_decision_delay_ns)
        _timestamp(self.max_action_event_lag_ns)
        _digest(self.implementation_sha256)
        _money(self.initial_cash_usdt)
        if (
            type(self.policy) is not MicrostructurePolicyConfig
            or type(self.replay) is not CaptureReplayConfig
            or type(self.gateway) is not PaperGatewayConfig
            or not 1 <= self.max_decision_delay_ns <= 5_000_000_000
            or not 1
            <= self.max_action_event_lag_ns
            <= min(2_000_000_000, self.replay.max_event_lag_ns)
        ):
            raise ValueError("Typed policy/replay/gateway and bounded paper freshness required.")
        if (
            type(self.schema_version) is not int
            or self.schema_version != 1
            or self.version != PLAN_VERSION
            or self.mode != "paper"
            or self.promotion_allowed is not False
            or self.environment_json != _environment()
        ):
            raise ValueError("Unsupported or changed realtime paper plan.")

    @property
    def sha256(self):
        return _hash(_encode(self))


def register_realtime_plan(
    path: Path,
    *,
    plan_id: str,
    source_session: str,
    policy: MicrostructurePolicyConfig,
    replay: CaptureReplayConfig,
    gateway: PaperGatewayConfig,
    initial_cash_usdt: Decimal,
    max_decision_delay_ns: int = 2_000_000_000,
    max_action_event_lag_ns: int = 2_000_000_000,
) -> RealtimePaperPlan:
    plan = RealtimePaperPlan(
        plan_id,
        source_session,
        time.time_ns(),
        policy,
        replay,
        gateway,
        initial_cash_usdt,
        max_decision_delay_ns,
        max_action_event_lag_ns,
        _implementation_hash(),
        _environment(),
    )
    raw = (
        json.dumps({"plan_sha256": plan.sha256, "plan": json.loads(_encode(plan))}, sort_keys=True)
        + "\n"
    ).encode()
    if len(raw) > MAX_PLAN_BYTES:
        raise ValueError("Realtime paper plan exceeds its byte budget.")
    with Path(path).open("xb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    return plan


def load_realtime_plan(path: Path) -> RealtimePaperPlan:
    with Path(path).open("rb") as source:
        raw = source.read(MAX_PLAN_BYTES + 1)
    if len(raw) > MAX_PLAN_BYTES:
        raise ValueError("Realtime paper plan exceeds its byte budget.")
    envelope = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    if not isinstance(envelope, dict) or set(envelope) != {"plan", "plan_sha256"}:
        raise ValueError("Invalid realtime paper plan envelope.")
    value = envelope["plan"]
    if not isinstance(value, dict) or set(value) != set(RealtimePaperPlan.__dataclass_fields__):
        raise ValueError("Invalid realtime paper plan fields.")
    value["policy"] = _decode_policy(value["policy"])
    value["replay"] = _decode_replay(value["replay"])
    value["gateway"] = _decode_gateway(value["gateway"])
    value["initial_cash_usdt"] = _decimal(value["initial_cash_usdt"])
    plan = RealtimePaperPlan(**value)
    if plan.sha256 != envelope["plan_sha256"]:
        raise ValueError("Realtime paper plan checksum mismatch.")
    if plan.implementation_sha256 != _implementation_hash():
        raise ValueError("Source code changed after realtime paper plan registration.")
    return plan


def _case_id(plan: RealtimePaperPlan, tick) -> str:
    return "realtime-paper-case-" + _hash(PLAN_VERSION + ":" + plan.sha256 + ":" + tick.tick_id)


def _build_case(plan: RealtimePaperPlan, frame: ReplayFrame, context) -> PreTradeCase:
    evidence = (
        CaseEvidence("paper_live_frame", frame.tick.observed_at_ns, _hash(_encode(frame))),
        CaseEvidence("paper_decision_context", frame.tick.observed_at_ns, _hash(_encode(context))),
        CaseEvidence("predeclared_paper_plan", frame.tick.observed_at_ns, plan.sha256),
    )
    case_id = _case_id(plan, frame.tick)
    if context.protection_active:
        return PreTradeCase(
            case_id,
            frame.tick.source_session,
            frame.tick.observed_at_ns,
            PLAN_VERSION + ":" + plan.sha256,
            "receipt_causal_microstructure_v1:" + _hash(_encode(plan.replay.features)),
            frame.tick.observation_sha256,
            "Protect existing paper inventory before considering entries.",
            "No same-tick re-entry after protection, including a blocked exit.",
            "Unhealthy quotes block execution; no guessed prices or forced footer liquidation.",
            evidence,
            "NO_ACTION",
            None,
            "NOT_EVALUATED",
            "protective_exit_tick",
            plan.gateway.risk_config_sha256,
            mode="paper",
        )
    account, checkpoint = context.account, context.checkpoint
    with localcontext() as decimal_context:
        decimal_context.prec = 100
        risk = ResearchRiskSnapshot(
            frame.tick.observed_at_ns,
            account.cash_usdt,
            account.position_btc,
            account.realized_pnl_usdt - checkpoint.day_start_realized_usdt,
            checkpoint.peak_equity_usdt,
            checkpoint.kill_switch_active,
            bool(account.unresolved_order_ids),
        )
    assessment = assess_microstructure(
        frame,
        policy=plan.policy,
        features=plan.replay.features,
        gateway=plan.gateway,
        risk=risk,
        registration_sha256=plan.sha256,
    )
    return replace(
        assessment,
        case_id=case_id,
        mode="paper",
        policy_version=PLAN_VERSION + ":" + assessment.policy_version,
        evidence=assessment.evidence + evidence,
    )


class RealtimePaperSession:
    """Durable callback consumer for one new collector session; never resumes a partial."""

    def __init__(
        self,
        plan: RealtimePaperPlan,
        journal_path: Path,
        *,
        source_session: str | None = None,
        prior_captures: tuple[Path, ...] = (),
    ):
        if type(plan) is not RealtimePaperPlan:
            raise TypeError("Typed realtime paper plan required.")
        if plan.implementation_sha256 != _implementation_hash():
            raise ValueError("Source code differs from the registered paper plan.")
        if type(prior_captures) is not tuple or any(
            not isinstance(path, Path) for path in prior_captures
        ):
            raise ValueError("Explicit ordered prior capture paths are required.")
        self.plan = plan
        self.source_session = source_session or plan.source_session
        _identifier(self.source_session)
        if not prior_captures and self.source_session != plan.source_session:
            raise ValueError("First paper session differs from its registered source.")
        self.run_id = "realtime-paper-" + _hash(plan.sha256)
        continuing = bool(prior_captures)
        self.journal = (
            TradeJournal(journal_path, run_id=self.run_id, mode="paper")
            if continuing
            else TradeJournal.create(journal_path, run_id=self.run_id, mode="paper")
        )
        self.continuing = continuing
        self.state = "new"
        self.start = None
        self.stream = None
        self.runner = None
        self.buffer = []
        self.buffer_bytes = 0
        self.previous_offsets = {"metadata": 0, "stream": 0}
        self.sequence = 0
        self.frame_count = 0
        self.frozen = False
        if continuing:
            try:
                binding = self.journal._db.execute(
                    "SELECT plan_sha256, source_session FROM paper_live_binding WHERE singleton=1"
                ).fetchone()
                completed = self.journal._db.execute(
                    "SELECT source_session, capture_sha256 FROM paper_live_completion "
                    "ORDER BY source_session"
                ).fetchall()
                receipt_sources = [
                    row[0]
                    for row in self.journal._db.execute(
                        "SELECT DISTINCT source_session FROM paper_live_receipts "
                        "ORDER BY source_session"
                    )
                ]
                if (
                    binding != (plan.sha256, plan.source_session)
                    or not plan.source_session.endswith("-s0001")
                    or len(completed) != len(prior_captures)
                    or not 1 <= len(completed) < 32
                    or receipt_sources != [row[0] for row in completed]
                ):
                    raise JournalConflict("Paper journal is not a completed service prefix.")
                prefix = plan.source_session[:-4]
                expected = [f"{prefix}{i:04d}" for i in range(1, len(completed) + 1)]
                if (
                    [row[0] for row in completed] != expected
                    or self.source_session != f"{prefix}{len(completed) + 1:04d}"
                    or any(
                        _capture_sha256(path) != row[1]
                        for path, row in zip(prior_captures, completed, strict=True)
                    )
                    or self.journal._db.execute(
                        "SELECT 1 FROM paper_live_receipts WHERE source_session=? LIMIT 1",
                        (self.source_session,),
                    ).fetchone()
                    is not None
                ):
                    raise JournalConflict("Prior captures or next paper session do not match.")
            except BaseException:
                self.close()
                raise
        else:
            try:
                with self.journal._write():
                    self.journal._db.execute(
                        "CREATE TABLE paper_live_binding ("
                        "singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                        "plan_sha256 TEXT NOT NULL, source_session TEXT NOT NULL)"
                    )
                    self.journal._db.execute(
                        "INSERT INTO paper_live_binding VALUES (1, ?, ?)",
                        (plan.sha256, plan.source_session),
                    )
                    self.journal._db.execute(
                        "CREATE TABLE paper_live_receipts (source_session TEXT NOT NULL, "
                        "sequence INTEGER NOT NULL, "
                        "record_type TEXT NOT NULL, file_kind TEXT NOT NULL, "
                        "start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL, "
                        "line_sha256 TEXT NOT NULL, tick_id TEXT, "
                        "PRIMARY KEY (source_session, sequence))"
                    )
                    self.journal._db.execute(
                        "CREATE TABLE paper_live_completion (source_session TEXT PRIMARY KEY, "
                        "capture_sha256 TEXT NOT NULL, "
                        "record_count INTEGER NOT NULL, frame_count INTEGER NOT NULL)"
                    )
            except BaseException:
                self.close()
                raise
        self.prior_tick_count = self.journal._db.execute(
            "SELECT count(*) FROM paper_runner_ticks"
        ).fetchone()[0]

    def close(self):
        self.journal.close()

    def _process_frame(self, frame):
        now = time.time_ns()
        delay = now - frame.tick.observed_at_ns
        if not -self.plan.replay.max_future_skew_ns <= delay <= self.plan.max_decision_delay_ns:
            raise RuntimeError("Paper decision exceeded wall-clock lag/skew bound.")
        if self.runner is None:
            runner_config = PaperRunnerConfig(
                self.plan.policy.maximum_trade_age_ns,
                self.plan.policy.maximum_spread_bps,
            )
            if self.continuing:
                gateway = DurablePaperGateway(self.journal, self.plan.gateway)
                self.runner = PaperRunner(gateway, runner_config)
            else:
                seed = PaperAccountSeed(self.plan.initial_cash_usdt, frame.tick.observed_at_ns)
                self.journal.initialize_account(seed)
                gateway = DurablePaperGateway.initialize(self.journal, self.plan.gateway)
                self.runner = PaperRunner.initialize(gateway, runner_config)
        case_id = _case_id(self.plan, frame.tick)

        def builder(context):
            return _build_case(self.plan, frame, context)

        self.runner.process_with_case_builder(frame.tick, case_id=case_id, build_case=builder)
        self.frame_count += 1
        return frame.tick.tick_id

    def _observe_event_age(self, record):
        if record.get("record_type") != "stream_event":
            return
        event = record.get("event")
        received = record.get("received_at_ns")
        if (
            not isinstance(event, dict)
            or type(event.get("E")) is not int
            or type(received) is not int
        ):
            raise ValueError("Invalid paper event clock fields.")
        if received - event["E"] * 1_000_000 > self.plan.max_action_event_lag_ns:
            self.frozen = True

    def _paper_frame(self, frame):
        if frame is None or not self.frozen:
            return frame
        return replace(
            frame,
            tick=replace(frame.tick, book_synchronized=False, features_ready=False),
        )

    def _commit(self, record, receipt, frame=None):
        if type(receipt) is not DurableCaptureRecord:
            raise ValueError("Durable collector receipt required.")
        if (
            receipt.file_kind not in self.previous_offsets
            or receipt.start_offset != self.previous_offsets[receipt.file_kind]
            or receipt.end_offset <= receipt.start_offset
        ):
            # Footer follows the assembled stream in the metadata file.
            if not (
                record["record_type"] == "session_end"
                and receipt.file_kind == "metadata"
                and receipt.start_offset
                == self.previous_offsets["metadata"] + self.previous_offsets["stream"]
            ):
                raise ValueError("Durable capture offset is not an exact file prefix.")
        with self.journal._write():
            tick_id = self._process_frame(frame) if frame is not None else None
            self.sequence += 1
            self.journal._db.execute(
                "INSERT INTO paper_live_receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.source_session,
                    self.sequence,
                    record["record_type"],
                    receipt.file_kind,
                    receipt.start_offset,
                    receipt.end_offset,
                    receipt.line_sha256,
                    tick_id,
                ),
            )
        self.previous_offsets[receipt.file_kind] = receipt.end_offset
        if frame is not None and frame.status.startswith("resync_required:"):
            raise RuntimeError("Market stream lost synchronization; paper session stopped.")

    def accept(self, record: dict, receipt: DurableCaptureRecord):
        kind = record.get("record_type") if isinstance(record, dict) else None
        if self.state == "new":
            if (
                kind != "session_start"
                or record.get("started_at_ns", 0) <= self.plan.registered_at_ns
            ):
                raise ValueError("Realtime paper session must start after its plan.")
            self.start = record
            self._commit(record, receipt)
            self.state = "before_snapshot"
        elif self.state == "before_snapshot":
            if kind == "stream_event":
                self._observe_event_age(record)
                length = receipt.end_offset - receipt.start_offset
                if (
                    len(self.buffer) >= MAX_PRE_SNAPSHOT_EVENTS
                    or self.buffer_bytes + length > MAX_PRE_SNAPSHOT_BYTES
                ):
                    raise RuntimeError("Pre-snapshot paper buffer exceeded its bound.")
                self._commit(record, receipt)
                self.buffer.append(record)
                self.buffer_bytes += length
            elif kind == "depth_snapshot":
                self.stream = IncrementalCaptureFrames(
                    self.start,
                    record,
                    source_session=self.source_session,
                    config=self.plan.replay,
                )
                self._commit(record, receipt, self.stream.opening_frame())
                for buffered in self.buffer:
                    if self.stream.push(buffered) is not None:
                        raise RuntimeError("Buffered event crossed snapshot availability.")
                self.buffer.clear()
                self.state = "after_snapshot"
            else:
                raise ValueError("Expected stream event or depth snapshot before paper trading.")
        elif self.state == "after_snapshot":
            if kind == "stream_event":
                self._observe_event_age(record)
                self._commit(record, receipt, self._paper_frame(self.stream.push(record)))
            elif kind == "session_end":
                self._commit(record, receipt, self._paper_frame(self.stream.close(record)))
                self.state = "closed"
            else:
                raise ValueError("Unexpected record after depth snapshot.")
        else:
            raise ValueError("Realtime paper session is already closed.")

    def complete(self, capture_path: Path) -> dict:
        """Promote only a validated final capture with an exact paper tick prefix."""
        if self.state != "closed" or self.frame_count == 0:
            raise RuntimeError("Incomplete realtime paper session.")
        with Path(capture_path).open("rb") as source:
            raw = source.read(MAX_PAPER_BYTES + 1)
        if len(raw) > MAX_PAPER_BYTES:
            raise ValueError("Realtime paper capture exceeds its byte budget.")
        capture_sha256 = hashlib.sha256(raw).hexdigest()
        replay = CaptureReplay(
            raw,
            expected_sha256=capture_sha256,
            source_session=self.source_session,
            config=self.plan.replay,
        )
        records = replay._framing()
        frozen = False
        frames = []
        event_index = 2
        for frame in replay.frames():
            while event_index < min(frame.line_number, len(records) - 1):
                record = records[event_index]
                age = record["received_at_ns"] - record["event"]["E"] * 1_000_000
                frozen |= age > self.plan.max_action_event_lag_ns
                event_index += 1
            frames.append(
                replace(
                    frame,
                    tick=replace(frame.tick, book_synchronized=False, features_ready=False),
                )
                if frozen
                else frame
            )
        if frozen != self.frozen:
            raise JournalConflict("Paper freeze state differs from final capture.")
        if any(frame.status.startswith("resync_required:") for frame in frames) or not any(
            frame.observation is not None for frame in frames
        ):
            raise JournalConflict("Final capture has no healthy paper observation.")
        if len(frames) != self.frame_count:
            raise JournalConflict("Paper frame count differs from final capture.")
        stored = self.journal._db.execute(
            "SELECT payload FROM paper_runner_ticks ORDER BY sequence LIMIT -1 OFFSET ?",
            (self.prior_tick_count,),
        ).fetchall()
        if len(stored) != len(frames) or any(
            row[0]
            != _encode(replace(frame.tick, candidate_case_id=_case_id(self.plan, frame.tick)))
            for row, frame in zip(stored, frames, strict=True)
        ):
            raise JournalConflict("Paper journal is not the exact final capture prefix.")
        lines = raw.splitlines(keepends=True)
        receipts = self.journal._db.execute(
            "SELECT record_type, file_kind, start_offset, end_offset, line_sha256 "
            "FROM paper_live_receipts WHERE source_session=? ORDER BY sequence",
            (self.source_session,),
        ).fetchall()
        if len(receipts) != len(lines):
            raise JournalConflict("Durable receipt count differs from final capture.")
        canonical = [
            receipts[0],
            *[r for r in receipts if r[0] == "depth_snapshot"],
            *[r for r in receipts if r[0] == "stream_event"],
            receipts[-1],
        ]
        if len(canonical) != len(lines) or any(
            hashlib.sha256(line).hexdigest() != receipt[4]
            for line, receipt in zip(lines, canonical, strict=True)
        ):
            raise JournalConflict("Durable record hashes differ from final capture.")
        metadata_end = stream_end = 0
        for line, receipt in zip(lines, canonical, strict=True):
            _, file_kind, start, end, _ = receipt
            expected_start = (
                metadata_end + stream_end
                if receipt[0] == "session_end"
                else stream_end
                if file_kind == "stream"
                else metadata_end
            )
            if start != expected_start or end != start + len(line):
                raise JournalConflict("Durable record offsets differ from final capture.")
            if file_kind == "stream":
                stream_end = end
            else:
                metadata_end = end
        if self.plan.implementation_sha256 != _implementation_hash():
            raise ValueError("Source code changed during realtime paper capture.")
        with self.journal._write():
            self.journal._db.execute(
                "INSERT INTO paper_live_completion VALUES (?, ?, ?, ?)",
                (self.source_session, capture_sha256, len(lines), len(frames)),
            )
        account = self.journal.account_state()
        return {
            "mode": "realtime_paper",
            "source_session": self.source_session,
            "plan_sha256": self.plan.sha256,
            "capture_sha256": capture_sha256,
            "records": len(lines),
            "paper_frames": len(frames),
            "paper_orders": len(self.journal.order_ids()),
            "paper_frozen": self.frozen,
            "cash_usdt": str(account.cash_usdt),
            "position_btc": str(account.position_btc),
            "live_trading_available": False,
            "training_started": False,
        }


async def run_realtime_paper(
    *,
    plan_path: Path,
    capture_path: Path,
    journal_path: Path,
    seconds: int,
    enable_public_data: bool = False,
    enable_paper_simulation: bool = False,
    limits: CaptureLimits = REALTIME_LIMITS,
    collector=collect,
) -> dict:
    if enable_public_data is not True or enable_paper_simulation is not True:
        raise ValueError("Explicit public-data and paper-simulation activation required.")
    if type(seconds) is not int or not 1 <= seconds <= 3600 or type(limits) is not CaptureLimits:
        raise ValueError("Bounded duration and typed capture limits required.")
    if limits.max_events > MAX_PAPER_EVENTS or limits.max_bytes > MAX_PAPER_BYTES:
        raise ValueError("Realtime paper collector exceeds its event/byte budget.")
    plan = load_realtime_plan(plan_path)
    for path in (
        capture_path,
        capture_path.with_suffix(".jsonl.partial"),
        capture_path.with_suffix(".jsonl.stream.partial"),
        journal_path,
    ):
        if Path(path).exists():
            raise FileExistsError(path)
    session = RealtimePaperSession(plan, journal_path)
    try:
        result_path, _, _ = await collector(
            seconds,
            output_path=capture_path,
            limits=limits,
            on_durable_record=session.accept,
            validation_config=plan.replay,
        )
        if Path(result_path) != capture_path:
            raise ValueError("Collector published a different capture destination.")
        return session.complete(capture_path)
    finally:
        session.close()


def _append_manifest(path: Path, record: dict) -> None:
    encoded = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with path.open("ab") as output:
        output.write(encoded)
        output.flush()
        os.fsync(output.fileno())


async def run_realtime_paper_service(
    *,
    plan_path: Path,
    output_directory: Path,
    journal_path: Path,
    manifest_path: Path,
    sessions: int,
    seconds_per_session: int,
    enable_public_data: bool = False,
    enable_paper_simulation: bool = False,
    limits: CaptureLimits = REALTIME_LIMITS,
    collector=collect,
) -> dict:
    """Run a finite, stateful paper sequence; no retry or partial-session resume."""
    if enable_public_data is not True or enable_paper_simulation is not True:
        raise ValueError("Explicit public-data and paper-simulation activation required.")
    if (
        type(sessions) is not int
        or not 1 <= sessions <= 32
        or type(seconds_per_session) is not int
        or not 1 <= seconds_per_session <= 3600
        or type(limits) is not CaptureLimits
        or limits.max_events > MAX_PAPER_EVENTS
        or limits.max_bytes > MAX_PAPER_BYTES
    ):
        raise ValueError("Finite sessions, duration and paper capture limits required.")
    plan = load_realtime_plan(plan_path)
    if not plan.source_session.endswith("-s0001"):
        raise ValueError("Service source_session must end in -s0001.")
    prefix = plan.source_session[:-4]
    output_directory, journal_path, manifest_path = (
        Path(output_directory),
        Path(journal_path),
        Path(manifest_path),
    )
    names = tuple(f"{prefix}{index:04d}" for index in range(1, sessions + 1))
    paths = tuple(output_directory / f"{name}.jsonl" for name in names)
    targets = (journal_path, manifest_path, output_directory / ".realtime-paper.lock")
    targets += tuple(
        path
        for capture in paths
        for path in (
            capture,
            capture.with_suffix(".jsonl.partial"),
            capture.with_suffix(".jsonl.stream.partial"),
        )
    )
    if any(path.exists() for path in targets):
        raise FileExistsError("Realtime paper service output already exists.")
    output_directory.mkdir(parents=True, exist_ok=True)
    lock_path = output_directory / ".realtime-paper.lock"
    with lock_path.open("xb") as lock:
        lock.write(b"realtime paper service lock; inspect before removing\n")
        lock.flush()
        os.fsync(lock.fileno())
    completed = []
    last_report = None
    try:
        with manifest_path.open("xb") as manifest:
            manifest.flush()
            os.fsync(manifest.fileno())
        _append_manifest(
            manifest_path,
            {
                "record_type": "service_start",
                "plan_sha256": plan.sha256,
                "source_sessions": names,
                "seconds_per_session": seconds_per_session,
                "started_at_ns": time.time_ns(),
                "mode": "paper",
                "live_trading_available": False,
            },
        )
        for source_session, capture_path in zip(names, paths, strict=True):
            _append_manifest(
                manifest_path,
                {
                    "record_type": "session_start",
                    "source_session": source_session,
                    "started_at_ns": time.time_ns(),
                },
            )
            session = None
            try:
                session = RealtimePaperSession(
                    plan,
                    journal_path,
                    source_session=source_session,
                    prior_captures=tuple(completed),
                )
                published, _, _ = await collector(
                    seconds_per_session,
                    output_path=capture_path,
                    limits=limits,
                    on_durable_record=session.accept,
                    validation_config=plan.replay,
                )
                if Path(published) != capture_path:
                    raise ValueError("Collector published a different capture destination.")
                report = session.complete(capture_path)
                last_report = report
                completed.append(capture_path)
                _append_manifest(
                    manifest_path,
                    {
                        "record_type": "session_completed",
                        "source_session": source_session,
                        "capture_sha256": report["capture_sha256"],
                        "paper_frames": report["paper_frames"],
                        "paper_frozen": report["paper_frozen"],
                        "paper_orders_in_journal": report["paper_orders"],
                        "completed_at_ns": time.time_ns(),
                    },
                )
            except BaseException as error:
                _append_manifest(
                    manifest_path,
                    {
                        "record_type": "session_failed",
                        "source_session": source_session,
                        "error_type": type(error).__name__,
                        "failed_at_ns": time.time_ns(),
                    },
                )
                raise
            finally:
                if session is not None:
                    session.close()
        _append_manifest(
            manifest_path,
            {
                "record_type": "service_completed",
                "completed_sessions": len(completed),
                "completed_at_ns": time.time_ns(),
                "training_started": False,
                "live_orders_submitted": False,
                "open_paper_inventory_btc": last_report["position_btc"],
            },
        )
    finally:
        lock_path.unlink(missing_ok=True)
    return {
        "mode": "realtime_paper_service",
        "plan_sha256": plan.sha256,
        "completed_sessions": len(completed),
        "capture_paths": [str(path) for path in completed],
        "journal_path": str(journal_path),
        "manifest_path": str(manifest_path),
        "open_paper_inventory_btc": last_report["position_btc"],
        "paper_orders": last_report["paper_orders"],
        "live_trading_available": False,
        "training_started": False,
    }


def inspect_realtime_paper_service(
    *, journal_path: Path, output_directory: Path, manifest_path: Path
) -> dict:
    """Read-only evidence check; never resumes a failed or partial session."""
    journal_path = Path(journal_path)
    with sqlite3.connect(journal_path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        binding = db.execute(
            "SELECT plan_sha256, source_session FROM paper_live_binding WHERE singleton=1"
        ).fetchone()
    if binding is None:
        raise ValueError("Missing realtime paper journal binding.")
    plan_sha256, first_source = binding
    _digest(plan_sha256)
    _identifier(first_source)
    with TradeJournal(
        journal_path,
        run_id="realtime-paper-" + _hash(plan_sha256),
        mode="paper",
        read_only=True,
    ) as journal:
        completions = journal._db.execute(
            "SELECT source_session, capture_sha256, record_count, frame_count "
            "FROM paper_live_completion ORDER BY source_session"
        ).fetchall()
        receipt_sources = [
            row[0]
            for row in journal._db.execute(
                "SELECT DISTINCT source_session FROM paper_live_receipts ORDER BY source_session"
            )
        ]
        receipt_counts = dict(
            journal._db.execute(
                "SELECT source_session, count(*) FROM paper_live_receipts GROUP BY source_session"
            )
        )
        paper_ticks = journal._db.execute("SELECT count(*) FROM paper_runner_ticks").fetchone()[0]
        paper_orders = len(journal.order_ids())
    with Path(manifest_path).open("rb") as source:
        raw = source.read(MAX_MANIFEST_BYTES + 1)
    if not raw or len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("Service manifest is empty or exceeds its byte budget.")
    if not raw.endswith(b"\n"):
        raw = raw[: raw.rfind(b"\n") + 1]
    manifest = [
        json.loads(line, object_pairs_hook=_pairs, parse_constant=_constant)
        for line in raw.splitlines()
    ]
    if (
        not manifest
        or any(not isinstance(row, dict) for row in manifest)
        or manifest[0].get("record_type") != "service_start"
        or manifest[0].get("plan_sha256") != plan_sha256
    ):
        raise ValueError("Service manifest does not match the paper journal.")
    complete_rows = [row for row in manifest if row.get("record_type") == "session_completed"]

    def capture_matches(session, digest):
        try:
            return _capture_sha256(Path(output_directory) / f"{session}.jsonl") == digest
        except (OSError, ValueError):
            return False

    hashes_match = all(capture_matches(session, digest) for session, digest, _, _ in completions)
    manifest_matches = len(complete_rows) == len(completions) and all(
        row.get("source_session") == session
        and row.get("capture_sha256") == digest
        and row.get("paper_frames") == frames
        and receipt_counts.get(session) == records
        for row, (session, digest, records, frames) in zip(complete_rows, completions, strict=True)
    )
    declared = manifest[0].get("source_sessions")
    expected_names = (
        [f"{first_source[:-4]}{index:04d}" for index in range(1, len(declared) + 1)]
        if first_source.endswith("-s0001")
        and isinstance(declared, list)
        and 1 <= len(declared) <= 32
        else []
    )
    finished = (
        declared == expected_names
        and [row[0] for row in completions] == expected_names
        and sum(row[3] for row in completions) == paper_ticks
        and manifest[-1].get("record_type") == "service_completed"
        and manifest[-1].get("completed_sessions") == len(completions)
    )
    if not hashes_match or not manifest_matches:
        status = "integrity_failed"
    elif finished and receipt_sources == [row[0] for row in completions]:
        status = "recorded_complete"
    elif any(row.get("record_type") == "session_failed" for row in manifest):
        status = "failed_incomplete"
    else:
        status = "incomplete_or_running"
    return {
        "status": status,
        "plan_sha256": plan_sha256,
        "completed_sessions": len(completions),
        "receipt_sources": receipt_sources,
        "capture_hashes_match": hashes_match,
        "paper_ticks": paper_ticks,
        "paper_orders": paper_orders,
        "read_only": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    register = subparsers.add_parser("register")
    register.add_argument("--settings", type=Path, required=True)
    register.add_argument("--output", type=Path, required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--capture", type=Path, required=True)
    run.add_argument("--journal", type=Path, required=True)
    run.add_argument("--seconds", type=int, required=True)
    run.add_argument("--enable-public-data", action="store_true")
    run.add_argument("--enable-paper-simulation", action="store_true")
    service = subparsers.add_parser("service")
    service.add_argument("--plan", type=Path, required=True)
    service.add_argument("--output-directory", type=Path, required=True)
    service.add_argument("--journal", type=Path, required=True)
    service.add_argument("--manifest", type=Path, required=True)
    service.add_argument("--sessions", type=int, required=True)
    service.add_argument("--seconds-per-session", type=int, required=True)
    service.add_argument("--enable-public-data", action="store_true")
    service.add_argument("--enable-paper-simulation", action="store_true")
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--journal", type=Path, required=True)
    inspect.add_argument("--output-directory", type=Path, required=True)
    inspect.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "register":
        value = json.loads(args.settings.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
        if not isinstance(value, dict) or set(value) != {
            "plan_id",
            "source_session",
            "policy",
            "replay",
            "gateway",
            "initial_cash_usdt",
            "max_decision_delay_ns",
            "max_action_event_lag_ns",
        }:
            parser.error("Settings must contain the eight realtime paper fields.")
        plan = register_realtime_plan(
            args.output,
            plan_id=value["plan_id"],
            source_session=value["source_session"],
            policy=_decode_policy(value["policy"]),
            replay=_decode_replay(value["replay"]),
            gateway=_decode_gateway(value["gateway"]),
            initial_cash_usdt=_decimal(value["initial_cash_usdt"]),
            max_decision_delay_ns=value["max_decision_delay_ns"],
            max_action_event_lag_ns=value["max_action_event_lag_ns"],
        )
        print(json.dumps({"plan": str(args.output.resolve()), "sha256": plan.sha256}))
    elif args.command == "run":
        report = asyncio.run(
            run_realtime_paper(
                plan_path=args.plan,
                capture_path=args.capture,
                journal_path=args.journal,
                seconds=args.seconds,
                enable_public_data=args.enable_public_data,
                enable_paper_simulation=args.enable_paper_simulation,
            )
        )
        print(json.dumps(report, sort_keys=True))
    elif args.command == "service":
        report = asyncio.run(
            run_realtime_paper_service(
                plan_path=args.plan,
                output_directory=args.output_directory,
                journal_path=args.journal,
                manifest_path=args.manifest,
                sessions=args.sessions,
                seconds_per_session=args.seconds_per_session,
                enable_public_data=args.enable_public_data,
                enable_paper_simulation=args.enable_paper_simulation,
            )
        )
        print(json.dumps(report, sort_keys=True))
    else:
        print(
            json.dumps(
                inspect_realtime_paper_service(
                    journal_path=args.journal,
                    output_directory=args.output_directory,
                    manifest_path=args.manifest,
                ),
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": safe_error_type(error),
                    "failure": failure_details(error),
                    "message": "Retain capture, journal and manifest evidence; no automatic retry.",
                },
                sort_keys=True,
            )
        )
        raise SystemExit(1) from None
