"""Explicit-path, bounded Binance capture -> causal features -> paper-runner bridge.

No network, file discovery or signal generation. Framing is validated up front;
market faults are handled in receipt order and invalidate the rest of a session.
Snapshot-buffered records never produce observations before snapshot availability.
"""

import json
from dataclasses import dataclass, field, replace
from decimal import Decimal
from hashlib import sha256
from itertools import islice
from pathlib import Path

from ai_trader.features.microstructure import (
    MicrostructureConfig,
    MicrostructureEngine,
    MicrostructureObservation,
)
from ai_trader.ingestion.agg_trade import AggTrade
from ai_trader.ingestion.validate_combined import DEPTH_STREAM, SYMBOL, TRADE_STREAM
from ai_trader.orderbook.depth_update import DepthUpdate
from ai_trader.orderbook.local_book import LocalOrderBook, SequenceGapError
from ai_trader.trading.paper_lifecycle import _timestamp
from ai_trader.trading.paper_runner import PaperMarketTick, PaperTickResult
from ai_trader.trading.trade_journal import (
    JournalConflict,
    JournalError,
    _constant,
    _encode,
    _hash,
    _identifier,
    _pairs,
    _read,
    _shape,
)

MAX_BYTES = 32 * 1024 * 1024
MAX_RECORDS = 100_000
MAX_RECORD_BYTES = 2_000_000


def _digest(value):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("Expected lowercase SHA256.")


def _integer(value):
    if type(value) is not int or value < 0:
        raise ValueError("Expected nonnegative integer.")


def _levels(values, *, snapshot=False):
    if not isinstance(values, list) or len(values) > 10_000:
        raise ValueError("Invalid depth levels.")
    seen = set()
    for level in values:
        if (
            not isinstance(level, list)
            or len(level) != 2
            or any(not isinstance(value, str) for value in level)
        ):
            raise ValueError("Depth prices/quantities must be string pairs.")
        price, quantity = map(Decimal, level)
        if (
            not price.is_finite()
            or not quantity.is_finite()
            or price <= 0
            or quantity < 0
            or (snapshot and quantity == 0)
            or price in seen
        ):
            raise ValueError("Invalid or duplicate depth price/quantity.")
        seen.add(price)


@dataclass(frozen=True, slots=True)
class CaptureReplayConfig:
    features: MicrostructureConfig = field(default_factory=MicrostructureConfig)
    max_event_lag_ns: int = 2_000_000_000
    max_future_skew_ns: int = 100_000_000

    def __post_init__(self):
        if type(self.features) is not MicrostructureConfig:
            raise ValueError("Expected typed feature config.")
        self.features.validate()
        _timestamp(self.max_event_lag_ns)
        _timestamp(self.max_future_skew_ns)
        if self.max_event_lag_ns == 0:
            raise ValueError("Maximum event lag must be positive.")


@dataclass(frozen=True, slots=True)
class ReplayFrame:
    line_number: int
    tick: PaperMarketTick
    status: str
    observation: MicrostructureObservation | None = None


@dataclass(frozen=True, slots=True)
class ReplayOutcome:
    line_number: int
    status: str
    result: PaperTickResult


@dataclass(frozen=True, slots=True)
class ReplayBinding:
    source_session: str
    source_sha256: str
    config_json: str
    implementation_sha256: str
    candidates_json: str

    def __post_init__(self):
        _identifier(self.source_session)
        _digest(self.source_sha256)
        _digest(self.implementation_sha256)
        for value in (self.config_json, self.candidates_json):
            if not isinstance(value, str):
                raise ValueError("Expected canonical configuration string.")
            parsed = json.loads(value, object_pairs_hook=_pairs, parse_constant=_constant)
            if json.dumps(parsed, sort_keys=True, allow_nan=False) != value:
                raise ValueError("Noncanonical replay binding.")


def _decode_binding(value):
    return ReplayBinding(**_shape(value, ReplayBinding))


def _implementation_hash():
    root = Path(__file__).resolve().parents[1]
    manifest = {
        p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*.py"))
    }
    return _hash(json.dumps(manifest, sort_keys=True))


class IncrementalCaptureFrames:
    """Receipt-ordered, in-memory frames for one capture; never a success receipt.

    The caller supplies the canonical capture order: start, snapshot, then each
    staged stream event. An event received before snapshot availability is
    stitched into the book, but cannot produce a paper tick or feature warmup.
    Replay the prefix from the start after a restart; no hidden mutable state is
    trusted across processes.
    """

    def __init__(self, start, snapshot, *, source_session: str, config: CaptureReplayConfig):
        _identifier(source_session)
        if type(config) is not CaptureReplayConfig:
            raise ValueError("Expected typed replay configuration.")
        for record in (start, snapshot):
            if (
                not isinstance(record, dict)
                or type(record.get("schema_version")) is not int
                or record["schema_version"] != 1
            ):
                raise ValueError("Unsupported capture envelope.")
        if (
            start.get("record_type") != "session_start"
            or start.get("symbol") != SYMBOL
            or start.get("streams") != [TRADE_STREAM, DEPTH_STREAM]
            or snapshot.get("record_type") != "depth_snapshot"
        ):
            raise ValueError("Invalid capture framing.")
        for value in (
            start.get("started_at_ns"),
            snapshot.get("requested_at_ns"),
            snapshot.get("received_at_ns"),
        ):
            _timestamp(value)
        if not (
            start["started_at_ns"] <= snapshot["requested_at_ns"] <= snapshot["received_at_ns"]
        ):
            raise ValueError("Invalid snapshot availability interval.")
        raw = snapshot.get("event")
        if not isinstance(raw, dict):
            raise ValueError("Missing snapshot payload.")
        _integer(raw.get("lastUpdateId"))
        _levels(raw.get("bids"), snapshot=True)
        _levels(raw.get("asks"), snapshot=True)
        self.book = LocalOrderBook.from_snapshot(SYMBOL, raw)
        self.source_session = source_session
        self.config = config
        self.snapshot = snapshot
        self.available = snapshot["received_at_ns"]
        self.previous_received = start["started_at_ns"]
        self.counts = {TRADE_STREAM: 0, DEPTH_STREAM: 0}
        self.line_number = 2
        self.subject = None
        self.last_trade_id = self.last_trade_time = self.last_trade_received = None
        self.last_depth_time = None
        self.invalid = None
        self.observation = None
        self.fallback = (self.book.best_bid.price, self.book.best_ask.price)
        self.closed = False
        self._opening_frame = ReplayFrame(
            2, self._tick(2, self.available), "awaiting_snapshot_bridge"
        )

    def _tick(self, line, now, *, synchronized=False, ready=False):
        tick_id = "capture-" + _hash(self.source_session + ":" + str(line))
        if self.observation is not None:
            value = PaperMarketTick.from_observation(
                self.observation,
                tick_id=tick_id,
                observed_at_ns=now,
                last_trade_received_at_ns=self.last_trade_received,
                book_synchronized=synchronized,
            )
            return value if ready else replace(value, features_ready=False)
        return PaperMarketTick(
            tick_id,
            self.source_session,
            now,
            self.available,
            self.last_trade_received,
            *self.fallback,
            False,
            False,
            _hash(json.dumps(self.snapshot, sort_keys=True)),
        )

    def opening_frame(self):
        return self._opening_frame

    def push(self, record) -> ReplayFrame | None:
        """Consume one staged event; return a paper frame only after availability."""
        if self.closed or self.line_number >= MAX_RECORDS - 1:
            raise ValueError("Capture stream is closed or exceeds the record budget.")
        if (
            not isinstance(record, dict)
            or type(record.get("schema_version")) is not int
            or record["schema_version"] != 1
            or record.get("record_type") != "stream_event"
            or record.get("stream") not in self.counts
            or not isinstance(record.get("event"), dict)
        ):
            raise ValueError("Invalid stream envelope.")
        received = record.get("received_at_ns")
        _timestamp(received)
        if received < self.previous_received:
            raise ValueError("Capture receipt time regressed.")
        self.previous_received = received
        self.line_number += 1
        self.counts[record["stream"]] += 1
        event = record["event"]
        depth_applied = False
        if self.invalid is None:
            try:
                if event.get("s") != SYMBOL:
                    raise ValueError("Symbol mismatch.")
                _integer(event.get("E"))
                delay = received - event["E"] * 1_000_000
                if not -self.config.max_future_skew_ns <= delay <= self.config.max_event_lag_ns:
                    raise ValueError("Event latency/clock-skew bound exceeded.")
                if self.subject is None and received > self.available:
                    self.subject = MicrostructureEngine(
                        self.source_session, self.book, self.config.features
                    )
                if record["stream"] == TRADE_STREAM:
                    for key in ("a", "f", "l", "T"):
                        _integer(event.get(key))
                    if any(not isinstance(event.get(key), str) for key in ("p", "q")):
                        raise ValueError("Trade amounts must be strings.")
                    trade = AggTrade.from_event(event)
                    if any(not v.is_finite() for v in (trade.price, trade.quantity)):
                        raise ValueError("Non-finite trade amount.")
                    if (
                        self.last_trade_id is not None
                        and trade.aggregate_trade_id != self.last_trade_id + 1
                    ):
                        raise ValueError("Aggregate trade sequence gap/duplicate.")
                    if (
                        self.last_trade_time is not None
                        and trade.trade_time_ms < self.last_trade_time
                    ):
                        raise ValueError("Trade time regressed.")
                    trade_age = received - trade.trade_time_ms * 1_000_000
                    if (
                        not -self.config.max_future_skew_ns
                        <= trade_age
                        <= self.config.max_event_lag_ns
                    ):
                        raise ValueError("Trade execution time outside freshness bounds.")
                    self.last_trade_id, self.last_trade_time = (
                        trade.aggregate_trade_id,
                        trade.trade_time_ms,
                    )
                    if received > self.available:
                        self.subject.add_trade(trade, received_at_ns=received)
                        self.last_trade_received = received
                else:
                    for key in ("U", "u"):
                        _integer(event.get(key))
                    _levels(event.get("b"))
                    _levels(event.get("a"))
                    update = DepthUpdate.from_event(event)
                    if (
                        self.last_depth_time is not None
                        and update.event_time_ms < self.last_depth_time
                    ):
                        raise ValueError("Depth event time regressed.")
                    self.last_depth_time = update.event_time_ms
                    if received <= self.available:
                        self.book.apply(update)
                    else:
                        row = self.subject.apply_depth(update, received_at_ns=received)
                        if row is not None:
                            self.observation, depth_applied = row, True
            except (ValueError, TypeError, KeyError, ArithmeticError, SequenceGapError) as error:
                self.invalid = f"resync_required:{type(error).__name__}:{error}"
                if self.subject is not None:
                    self.subject.valid = False
        if received <= self.available:
            return None
        status = self.invalid or ("observation" if depth_applied else "no_new_depth")
        return ReplayFrame(
            self.line_number,
            self._tick(
                self.line_number,
                received,
                synchronized=self.invalid is None and self.observation is not None,
                ready=depth_applied and self.invalid is None,
            ),
            status,
            self.observation if depth_applied and self.invalid is None else None,
        )

    def close(self, end) -> ReplayFrame:
        if (
            self.closed
            or not isinstance(end, dict)
            or type(end.get("schema_version")) is not int
            or end["schema_version"] != 1
        ):
            raise ValueError("Invalid capture footer.")
        if end.get("record_type") != "session_end":
            raise ValueError("Invalid capture footer.")
        _timestamp(end.get("ended_at_ns"))
        if end["ended_at_ns"] < max(self.previous_received, self.available):
            raise ValueError("Capture receipt time exceeded footer.")
        for key, stream in (("trade_events", TRADE_STREAM), ("depth_events", DEPTH_STREAM)):
            _integer(end.get(key))
            if end[key] != self.counts[stream]:
                raise ValueError("Capture footer count mismatch.")
        if not self.counts[DEPTH_STREAM]:
            raise ValueError("Capture has no depth events.")
        self.closed = True
        self.line_number += 1
        return ReplayFrame(
            self.line_number,
            self._tick(self.line_number, end["ended_at_ns"]),
            self.invalid or "session_closed",
        )


class CaptureReplay:
    """Immutable input bytes, fresh in-memory engine on each iteration/restart."""

    def __init__(
        self, data: bytes, *, expected_sha256: str, source_session: str, config: CaptureReplayConfig
    ):
        _digest(expected_sha256)
        _identifier(source_session)
        if type(config) is not CaptureReplayConfig:
            raise ValueError("Expected typed replay configuration.")
        if type(data) is not bytes or not data or len(data) > MAX_BYTES:
            raise ValueError("Capture must be nonempty bytes within the replay size budget.")
        if sha256(data).hexdigest() != expected_sha256:
            raise ValueError("Capture checksum mismatch.")
        self._data = data
        self.source_sha256, self.source_session, self.config = (
            expected_sha256,
            source_session,
            config,
        )
        self._framing()  # Reject incomplete/malformed metadata before any journal writes.

    @classmethod
    def from_path(cls, path: Path, **kwargs):
        with Path(path).open("rb") as source:
            data = source.read(MAX_BYTES + 1)
        return cls(data, **kwargs)

    @property
    def record_count(self):
        """Physical record count, including the footer even for an invalid market stream."""
        return len(self._data.splitlines())

    def _framing(self):
        lines = self._data.splitlines()
        if not 4 <= len(lines) <= MAX_RECORDS:
            raise ValueError("Capture record count is outside the replay budget.")
        records = []
        for line in lines:
            if not line or len(line) > MAX_RECORD_BYTES:
                raise ValueError("Empty/oversized capture record.")
            record = json.loads(line, object_pairs_hook=_pairs, parse_constant=_constant)
            if (
                not isinstance(record, dict)
                or type(record.get("schema_version")) is not int
                or record["schema_version"] != 1
            ):
                raise ValueError("Unsupported capture envelope.")
            records.append(record)
        start, snapshot, end = records[0], records[1], records[-1]
        if (
            start.get("record_type") != "session_start"
            or start.get("symbol") != SYMBOL
            or start.get("streams") != [TRADE_STREAM, DEPTH_STREAM]
            or snapshot.get("record_type") != "depth_snapshot"
            or end.get("record_type") != "session_end"
        ):
            raise ValueError("Invalid capture framing.")
        for value in (
            start.get("started_at_ns"),
            snapshot.get("requested_at_ns"),
            snapshot.get("received_at_ns"),
            end.get("ended_at_ns"),
        ):
            _timestamp(value)
        if not (
            start["started_at_ns"]
            <= snapshot["requested_at_ns"]
            <= snapshot["received_at_ns"]
            <= end["ended_at_ns"]
        ):
            raise ValueError("Invalid snapshot availability interval.")
        raw = snapshot.get("event")
        if not isinstance(raw, dict):
            raise ValueError("Missing snapshot payload.")
        _integer(raw.get("lastUpdateId"))
        _levels(raw.get("bids"), snapshot=True)
        _levels(raw.get("asks"), snapshot=True)
        LocalOrderBook.from_snapshot(SYMBOL, raw)
        counts = dict.fromkeys((TRADE_STREAM, DEPTH_STREAM), 0)
        previous = start["started_at_ns"]
        for record in records[2:-1]:
            if (
                record.get("record_type") != "stream_event"
                or record.get("stream") not in counts
                or not isinstance(record.get("event"), dict)
            ):
                raise ValueError("Invalid stream envelope.")
            received = record.get("received_at_ns")
            _timestamp(received)
            if not previous <= received <= end["ended_at_ns"]:
                raise ValueError("Capture receipt time regressed or exceeded footer.")
            previous = received
            counts[record["stream"]] += 1
        for key, stream in (("trade_events", TRADE_STREAM), ("depth_events", DEPTH_STREAM)):
            _integer(end.get(key))
            if counts[stream] != end[key]:
                raise ValueError("Capture footer count mismatch.")
        if not counts[DEPTH_STREAM]:
            raise ValueError("Capture has no depth events.")
        return records

    def frames(self):
        """No future footer/quality values authorize trades; footer merely ends availability."""
        records = self._framing()
        stream = IncrementalCaptureFrames(
            records[0], records[1], source_session=self.source_session, config=self.config
        )
        yield stream.opening_frame()
        for record in records[2:-1]:
            frame = stream.push(record)
            if frame is not None:
                yield frame
        yield stream.close(records[-1])

    def run(self, runner, *, max_frames: int, candidate_cases=None) -> tuple[ReplayOutcome, ...]:
        """Reconstruct from the start; persisted runner ticks make exact retries harmless.

        Budget counts frames from the beginning, including already committed ones.
        Increase the budget to continue a prefix, without skipping reconstruction.
        """
        if type(max_frames) is not int or not 1 <= max_frames <= MAX_RECORDS:
            raise ValueError("Invalid frame budget.")
        if runner.journal._db.execute("PRAGMA user_version").fetchone()[0] != 6:
            raise JournalError("Explicit schema upgrade required for capture replay.")
        candidates = dict(candidate_cases or {})
        case_bindings = {}
        valid_ids = {
            "capture-" + _hash(self.source_session + ":" + str(n))
            for n in range(3, len(self._framing()))
        }
        for tick_id, case_id in candidates.items():
            _identifier(tick_id)
            _identifier(case_id)
            if tick_id not in valid_ids:
                raise JournalError("Candidate tick is outside the stream record range.")
            case = runner.journal.get_case(case_id)
            if case is None:
                raise JournalError("Replay candidate case must already be recorded.")
            case_bindings[tick_id] = [case_id, case.sha256]
        binding = ReplayBinding(
            self.source_session,
            self.source_sha256,
            _encode(self.config),
            _implementation_hash(),
            json.dumps(case_bindings, sort_keys=True),
        )
        payload = _encode(binding)
        with runner.journal._write():
            row = runner.journal._db.execute(
                "SELECT payload, sha256 FROM paper_replay_sources WHERE source_session=?",
                (self.source_session,),
            ).fetchone()
            if row is None:
                runner.journal._db.execute(
                    "INSERT INTO paper_replay_sources VALUES (?, ?, ?)",
                    (self.source_session, payload, _hash(payload)),
                )
            elif _encode(_read(*row, _decode_binding)) != payload:
                raise JournalConflict("Replay source/config/code/candidate binding changed.")
        results = []
        for frame in islice(self.frames(), max_frames):
            tick = replace(frame.tick, candidate_case_id=candidates.get(frame.tick.tick_id))
            result = runner.process(tick)
            results.append(ReplayOutcome(frame.line_number, frame.status, result))
        return tuple(results)
