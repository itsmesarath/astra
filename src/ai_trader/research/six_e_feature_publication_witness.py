"""Reconstruct all causal features from a complete invented target-MBO prefix.

Only the fixed helper source files are read. No source archive, retained data,
target builder, account, policy, model, order, CLI or storage hook is used.
Computed invented witnesses are not authenticated historical provenance.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from dataclasses import asdict, dataclass, fields, is_dataclass, replace
from functools import wraps
from pathlib import Path

from ai_trader.research import databento_6e_execution_flow as execution
from ai_trader.research import databento_6e_microdepth as microdepth
from ai_trader.research import databento_6e_ofi_scalp as ofi
from ai_trader.research import databento_6e_seconds_pilot as clock
from ai_trader.research.databento_6e_scenario_replay import StrictBook

VERSION = "six_e_feature_publication_witness_v1"
STATUS = "constructed_feature_reconstruction_not_historical_provenance"
UTC_DATE, CONTRACT, INSTRUMENT_ID = "2025-04-07", "6EM5", 1
DAY_START_NS = 1743984000000000000
WINDOW_START_NS, WINDOW_END_NS = 1744027200000000000, 1744041600000000000
WARMUP_START_NS, GENESIS_NS = 1744027190000000000, 1744027189999999999
SECOND_NS, FLOW_NS, WARMUP_NS = 1000000000, 5000000000, 10000000000
MIN_PUBLICATION_CADENCE_NS, READINESS_END_BUFFER_NS = 1000000000, 17000000000
TICK_NANO, F_LAST = 50000, 128
MAX_RECORDS, MAX_COMPLETED_EVENTS, MAX_PUBLICATIONS = 256, 128, 32
MAX_CANONICAL_BYTES, MAX_HELPER_SOURCE_BYTES = 1048576, 1048576
MAX_INT, MAX_SEQUENCE, MAX_SEND_DELTA = 9223372036854775807, 4294967295, 2147483647

_PROTOCOL_CONSTANTS = (
    ("VERSION", "six_e_feature_publication_witness_v1"),
    ("STATUS", "constructed_feature_reconstruction_not_historical_provenance"),
    ("UTC_DATE", "2025-04-07"),
    ("CONTRACT", "6EM5"),
    ("INSTRUMENT_ID", 1),
    ("DAY_START_NS", 1743984000000000000),
    ("WINDOW_START_NS", 1744027200000000000),
    ("WINDOW_END_NS", 1744041600000000000),
    ("WARMUP_START_NS", 1744027190000000000),
    ("GENESIS_NS", 1744027189999999999),
    ("SECOND_NS", 1000000000),
    ("FLOW_NS", 5000000000),
    ("WARMUP_NS", 10000000000),
    ("MIN_PUBLICATION_CADENCE_NS", 1000000000),
    ("READINESS_END_BUFFER_NS", 17000000000),
    ("TICK_NANO", 50000),
    ("F_LAST", 128),
    ("MAX_RECORDS", 256),
    ("MAX_COMPLETED_EVENTS", 128),
    ("MAX_PUBLICATIONS", 32),
    ("MAX_CANONICAL_BYTES", 1048576),
    ("MAX_HELPER_SOURCE_BYTES", 1048576),
    ("MAX_INT", 9223372036854775807),
    ("MAX_SEQUENCE", 4294967295),
    ("MAX_SEND_DELTA", 2147483647),
)
FEATURE_NAMES = (
    "log_bid_qty",
    "log_ask_qty",
    "queue_imbalance",
    "normalized_ofi_5s",
    "normalized_cvd_5s",
    "log_known_trades_5s",
    "unknown_trade_fraction_5s",
    "log_prior_quote_gap_ms",
    "log_bid_depth5",
    "log_ask_depth5",
    "depth5_imbalance",
    "bid_top_share5",
    "ask_top_share5",
    "bid_span5_ticks",
    "ask_span5_ticks",
    "mid_change_5s_ticks",
    "mid_range_5s_ticks",
    "mid_travel_5s_ticks",
    "log_quote_events_5s",
    "normalized_bid_reload_5s",
    "normalized_ask_reload_5s",
    "buy_absorption_proxy_5s",
    "sell_absorption_proxy_5s",
    "bid_passive_5s",
    "bid_held_top_passive_5s",
    "bid_linked_decrease_5s",
    "bid_unlinked_decrease_5s",
    "bid_same_id_reload_5s",
    "bid_other_id_reload_5s",
    "bid_same_id_net_refresh_5s",
    "ask_passive_5s",
    "ask_held_top_passive_5s",
    "ask_linked_decrease_5s",
    "ask_unlinked_decrease_5s",
    "ask_same_id_reload_5s",
    "ask_other_id_reload_5s",
    "ask_same_id_net_refresh_5s",
)
AUTHORITY_FLAGS = tuple(
    (name, False)
    for name in (
        "accounting_admission_authorized",
        "calendar_verified",
        "cohort_externally_complete",
        "collection_receipt_authenticated",
        "event_prefix_verified",
        "execution_authorized",
        "feature_derivation_verified",
        "feature_publication_verified",
        "feed_authenticated",
        "first_cursor_verified",
        "historical_access_authorized",
        "independent_validation",
        "input_authenticated",
        "metadata_assertions_authenticated",
        "promotion_allowed",
        "source_integrity_verified",
        "source_runtime_verified",
        "storage_resume_authorized",
        "trading_enabled",
        "training_enabled",
    )
)
_SOURCE_PINS = (
    (
        "src/ai_trader/research/databento_6e_cost_targets.py",
        "ebc4c1dc0a44e71362cd96bed0a699dac6ebc04a66fc7f568d2bf4898d427b2b",
    ),
    (
        "src/ai_trader/research/databento_6e_event_scalp.py",
        "48bd0402c2e8a7c0d8d286b8956a2f55059c71df81dc1115ee15d8adce560b3e",
    ),
    (
        "src/ai_trader/research/databento_6e_execution_flow.py",
        "7f777a19518378dd3b2a0371b7f3ddcf3077f51555faffa5e589de6255239b75",
    ),
    (
        "src/ai_trader/research/databento_6e_microdepth.py",
        "8964b20a5de8104a0f7831cf827c1c736f3c11b6a2d61dbe0206521ee3b451c4",
    ),
    (
        "src/ai_trader/research/databento_6e_ofi_scalp.py",
        "05cade0f206c06cbea93198c9fb92e591c0275ef5ac70f8ce50bcb000ad0ff24",
    ),
    (
        "src/ai_trader/research/databento_6e_receive_clock.py",
        "351b4b54fc3ac4ac905ebdbb9725f270288ac235178cb50180e2040d8fef4636",
    ),
    (
        "src/ai_trader/research/databento_6e_scenario_replay.py",
        "d5bf8e3e0ec4b1957f1a2a7ed515f1cf9530b922e5c2c3929389ed0bfeab91ff",
    ),
    (
        "src/ai_trader/research/databento_6e_seconds_pilot.py",
        "7c295b7cc3875a6955d3582368a7d28804dd318e061e0d0b3906e4a21e411b2b",
    ),
    (
        "src/ai_trader/research/databento_6e_training_data.py",
        "9d1c9190da304031113880dbfb4d002121908d35b6bc52671a65939a6e7049a3",
    ),
)
_RECORD_FIELDS = (
    "record_ordinal",
    "instrument_id",
    "ts_recv",
    "ts_event",
    "ts_in_delta",
    "sequence",
    "action",
    "side",
    "flags",
    "price",
    "size",
    "order_id",
)
_FIXTURE_FIELDS = (
    "fixture_id",
    "source_session",
    "utc_date",
    "contract",
    "instrument_id",
    "records",
)
_RECORD_AUDIT_FIELDS = (
    "record_ordinal",
    "before",
    "record_sha256",
    "preceding_prefix_sha256",
    "prefix_sha256",
)
_EVENT_FIELDS = (
    "event_id",
    "event_ordinal",
    "first_record_ordinal",
    "last_record_ordinal",
    "started_at_ns",
    "completed_at_ns",
    "quote_ordinal",
    "quote",
    "prior_quote_gap_ns",
    "ofi_first_ts_ns",
    "inactivity_reset",
    "execution_temporal_reset",
    "execution_stale_spanning",
    "prefix_sha256",
    "event_sha256",
)
_PUBLICATION_FIELDS = (
    "publication_id",
    "publication_ordinal",
    "event_ordinal",
    "quote_ordinal",
    "received_at_ns",
    "quote",
    "prefix_sha256",
    "event_sha256",
    "ofi_first_ts_ns",
    "prior_quote_gap_ns",
    "cvd",
    "known_trade_count",
    "unknown_trade_count",
    "ofi_total",
    "feature_values",
    "eligible",
    "eligibility_reason",
    "publication_sha256",
)
_WITNESS_FIELDS = (
    "version",
    "status",
    "protocol_sha256",
    "fixture_sha256",
    "fixture",
    "prefix_context_sha256",
    "record_audits",
    "completed_events",
    "publications",
    "execution_audit",
    "terminal_prefix_sha256",
    "terminal_received_at_ns",
    "record_count",
    "completed_event_count",
    "quote_count",
    "publication_count",
    "authority_flags",
    "witness_sha256",
)
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z", re.ASCII)
_PIN = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_UNSUPPLIED = object()


class FeaturePublicationWitnessError(ValueError):
    """Malformed or conflicting complete constructed context or helper evidence."""


def _require(condition, message):
    if not condition:
        raise FeaturePublicationWitnessError(message)


def _public(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except FeaturePublicationWitnessError:
            raise
        except (ValueError, TypeError, AttributeError, OverflowError, OSError) as exc:
            raise FeaturePublicationWitnessError(str(exc)) from exc

    return wrapped


def _typed(value, cls, deferred=()):
    _require(type(value) is cls, f"Exact {cls.__name__} required")
    _require(
        all(hasattr(value, field.name) for field in fields(cls) if field.name not in deferred),
        "Complete metadata fields required",
    )


def _integer(value, lower, upper, name):
    _require(type(value) is int and lower <= value <= upper, f"Invalid {name}")


def _identifier(value):
    _require(type(value) is str and _IDENTIFIER.fullmatch(value) is not None, "Invalid identifier")
    _require(value.startswith("synthetic-") and len(value) > 10, "Synthetic identifier required")


def _pin(value):
    _require(type(value) is str and _PIN.fullmatch(value) is not None, "Invalid SHA256 pin")


def _canonical(value):
    raw = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    _require(len(raw) <= MAX_CANONICAL_BYTES, "Complete canonical witness body exceeds bound")
    return raw


def _hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class ConstructedMboRecord:
    record_ordinal: int
    instrument_id: int
    ts_recv: int
    ts_event: int
    ts_in_delta: int
    sequence: int
    action: str
    side: str
    flags: int
    price: int
    size: int
    order_id: int

    @_public
    def __post_init__(self):
        _record_metadata(self)


@dataclass(frozen=True, slots=True)
class FeatureWitnessFixture:
    fixture_id: str
    source_session: str
    utc_date: str
    contract: str
    instrument_id: int
    records: tuple[ConstructedMboRecord, ...]

    @_public
    def __post_init__(self):
        _fixture_metadata(self)


@dataclass(frozen=True, slots=True)
class RecordAudit:
    record_ordinal: int
    before: tuple[str, int, int] | None
    record_sha256: str
    preceding_prefix_sha256: str
    prefix_sha256: str


@dataclass(frozen=True, slots=True)
class CompletedEventWitness:
    event_id: str
    event_ordinal: int
    first_record_ordinal: int
    last_record_ordinal: int
    started_at_ns: int
    completed_at_ns: int
    quote_ordinal: int
    quote: clock.Quote
    prior_quote_gap_ns: int
    ofi_first_ts_ns: int
    inactivity_reset: bool
    execution_temporal_reset: bool
    execution_stale_spanning: bool
    prefix_sha256: str
    event_sha256: str


@dataclass(frozen=True, slots=True)
class FeaturePublication:
    publication_id: str
    publication_ordinal: int
    event_ordinal: int
    quote_ordinal: int
    received_at_ns: int
    quote: clock.Quote
    prefix_sha256: str
    event_sha256: str
    ofi_first_ts_ns: int
    prior_quote_gap_ns: int
    cvd: int
    known_trade_count: int
    unknown_trade_count: int
    ofi_total: int
    feature_values: tuple[tuple[str, float], ...]
    eligible: bool
    eligibility_reason: str | None
    publication_sha256: str


@dataclass(frozen=True, slots=True)
class FeaturePublicationWitness:
    version: str
    status: str
    protocol_sha256: str
    fixture_sha256: str
    fixture: FeatureWitnessFixture
    prefix_context_sha256: str
    record_audits: tuple[RecordAudit, ...]
    completed_events: tuple[CompletedEventWitness, ...]
    publications: tuple[FeaturePublication, ...]
    execution_audit: tuple[tuple[str, int], ...]
    terminal_prefix_sha256: str
    terminal_received_at_ns: int
    record_count: int
    completed_event_count: int
    quote_count: int
    publication_count: int
    authority_flags: tuple[tuple[str, bool], ...]
    witness_sha256: str


@_public
def protocol() -> dict:
    """Return the complete literal protocol, without reading helpers or payloads."""
    result = {
        "version": VERSION,
        "status": STATUS,
        "scope": "constructed_target_mbo_prefix_only",
        "constants": dict(_PROTOCOL_CONSTANTS),
        "schemas": {
            "ConstructedMboRecord": list(_RECORD_FIELDS),
            "FeatureWitnessFixture": list(_FIXTURE_FIELDS),
            "RecordAudit": list(_RECORD_AUDIT_FIELDS),
            "CompletedEventWitness": list(_EVENT_FIELDS),
            "FeaturePublication": list(_PUBLICATION_FIELDS),
            "FeaturePublicationWitness": list(_WITNESS_FIELDS),
        },
        "feature_names": list(FEATURE_NAMES),
        "source_pins": [list(pair) for pair in _SOURCE_PINS],
        "identifier_templates": {
            "event_id": "synthetic-completed-event-{ordinal:04d}",
            "publication_id": "synthetic-feature-publication-{ordinal:04d}",
        },
        "readiness_reasons": [
            "spread_not_one_tick",
            "insufficient_feature_warmup",
            "insufficient_window_for_hold",
        ],
        "authority_flags": [list(pair) for pair in AUTHORITY_FLAGS],
    }
    _canonical(result)
    return result


@_public
def protocol_sha256() -> str:
    """Hash the entire literal protocol only, without runtime-source checks."""
    return _hash(protocol())


def _view_stamp(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _compatible_stamp(value):
    # Windows ctime can differ between a path stat and an opened handle.
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def _source_raw(path):
    _require(not path.is_symlink(), "Linked helper source refused")
    before = path.stat()
    _require(stat.S_ISREG(before.st_mode), "Regular helper source required")
    _require(0 < before.st_size <= MAX_HELPER_SOURCE_BYTES, "Helper source byte bound exceeded")
    with path.open("rb") as handle:
        opened = os.fstat(handle.fileno())
        _require(stat.S_ISREG(opened.st_mode), "Regular opened helper source required")
        _require(
            _compatible_stamp(before) == _compatible_stamp(opened), "Helper source view differs"
        )
        raw = handle.read(MAX_HELPER_SOURCE_BYTES + 1)
        finished = os.fstat(handle.fileno())
    after = path.stat()
    _require(not path.is_symlink(), "Linked final helper source refused")
    _require(_view_stamp(before) == _view_stamp(after), "Helper source path changed")
    _require(_view_stamp(opened) == _view_stamp(finished), "Helper source handle changed")
    _require(
        _compatible_stamp(after) == _compatible_stamp(finished), "Final helper source view differs"
    )
    _require(
        len(raw) == before.st_size and len(raw) <= MAX_HELPER_SOURCE_BYTES,
        "Helper source read length differs",
    )
    return raw


def _verify_sources():
    # Validate every literal pin before reading any of the fixed sources.
    for _, pin in _SOURCE_PINS:
        _pin(pin)
    research = Path(__file__).parent.resolve(strict=True)
    for relative, pin in _SOURCE_PINS:
        name = relative.rsplit("/", 1)[1]
        raw = _source_raw(research / name)
        _require(hashlib.sha256(raw).hexdigest() == pin, "Held helper source pin differs")
    _require(
        type(clock.TICK) is int
        and clock.TICK == TICK_NANO
        and type(clock.FLOW_NS) is int
        and clock.FLOW_NS == FLOW_NS
        and type(clock.SECOND_NS) is int
        and clock.SECOND_NS == SECOND_NS
        and type(clock.dbn.F_LAST) is int
        and clock.dbn.F_LAST == F_LAST,
        "Held causal constants differ",
    )
    _require(
        type(microdepth.FEATURES) is tuple
        and microdepth.FEATURES == FEATURE_NAMES[:23]
        and type(execution.FEATURES) is tuple
        and execution.FEATURES == FEATURE_NAMES[23:]
        and type(microdepth.base.FEATURES) is tuple
        and microdepth.base.FEATURES == FEATURE_NAMES[:8],
        "Held feature schemas differ",
    )


def _fixture_metadata(fixture):
    _typed(fixture, FeatureWitnessFixture)
    _identifier(fixture.fixture_id)
    _identifier(fixture.source_session)
    _require(
        type(fixture.utc_date) is str and fixture.utc_date == UTC_DATE, "Fixed UTC date required"
    )
    _require(
        type(fixture.contract) is str and fixture.contract == CONTRACT, "Fixed contract required"
    )
    _integer(fixture.instrument_id, INSTRUMENT_ID, INSTRUMENT_ID, "fixture instrument")
    _require(
        type(fixture.records) is tuple and 3 <= len(fixture.records) <= MAX_RECORDS,
        "Complete bounded record tuple required",
    )


def _record_metadata(record):
    # Price, size and order_id are deliberately not read during this phase.
    # Even their slot-presence checks must wait until all record metadata passes.
    _typed(record, ConstructedMboRecord, deferred=("price", "size", "order_id"))
    _integer(record.record_ordinal, 1, MAX_RECORDS, "record ordinal")
    _integer(record.instrument_id, INSTRUMENT_ID, INSTRUMENT_ID, "record instrument")
    _integer(record.ts_recv, GENESIS_NS, WINDOW_END_NS - 1, "receive timestamp")
    _integer(record.ts_event, 0, record.ts_recv, "event timestamp")
    _integer(record.ts_in_delta, 0, MAX_SEND_DELTA, "send delta")
    _integer(record.sequence, 0, MAX_SEQUENCE, "sequence")
    _require(
        type(record.action) is str and record.action in {"R", "A", "C", "M", "T", "F", "N"},
        "Invalid record action",
    )
    _require(type(record.side) is str and record.side in {"A", "B", "N"}, "Invalid record side")
    _integer(record.flags, 0, F_LAST, "flags")
    _require(record.flags in {0, F_LAST}, "Only original completion flag supported")
    if record.record_ordinal == 1:
        _require(
            record.action == "R"
            and record.side == "N"
            and record.flags == F_LAST
            and record.ts_recv == GENESIS_NS
            and record.ts_event == GENESIS_NS
            and record.ts_in_delta == 0
            and record.sequence == 0,
            "Exact empty-book genesis metadata required",
        )
    else:
        _require(
            record.ts_recv >= WARMUP_START_NS and record.action != "R",
            "Post-genesis protected records required",
        )
        if record.action in {"A", "C", "M"}:
            _require(record.side in {"A", "B"}, "Book action requires a resting side")
        elif record.action == "N":
            _require(record.side == "N", "Neutral marker side required")


def _all_metadata(fixture):
    _fixture_metadata(fixture)
    last_recv, completed = None, 0
    for ordinal, record in enumerate(fixture.records, 1):
        _record_metadata(record)
        _require(record.record_ordinal == ordinal, "Contiguous complete source ordinal required")
        _require(
            last_recv is None or record.ts_recv >= last_recv, "Original receive order regressed"
        )
        last_recv = record.ts_recv
        if ordinal > 1 and record.flags == F_LAST:
            completed += 1
    _require(fixture.records[-1].flags == F_LAST, "Incomplete final event refused")
    _require(1 <= completed <= MAX_COMPLETED_EVENTS, "Complete event count exceeds bound")


def _numbers(record):
    if record.record_ordinal == 1 or record.action == "N":
        _integer(record.price, 0, 0, "neutral price")
        _integer(record.size, 0, 0, "neutral size")
        _integer(record.order_id, 0, 0, "neutral order ID")
    else:
        _integer(record.price, 1, MAX_INT, "price")
        _require(record.price % TICK_NANO == 0, "Original on-grid price required")
        _integer(record.size, 1, MAX_INT, "size")
        _integer(record.order_id, 0 if record.action == "T" else 1, MAX_INT, "order ID")


def _prepare(
    fixture,
    expected_protocol_sha256,
    expected_fixture_sha256=_UNSUPPLIED,
    expected_witness_sha256=_UNSUPPLIED,
):
    # Independent pin syntax takes precedence over every caller payload field.
    _pin(expected_protocol_sha256)
    if expected_fixture_sha256 is not _UNSUPPLIED:
        _pin(expected_fixture_sha256)
    if expected_witness_sha256 is not _UNSUPPLIED:
        _pin(expected_witness_sha256)
    protocol_pin = protocol_sha256()
    _require(expected_protocol_sha256 == protocol_pin, "Complete protocol expectation differs")
    _verify_sources()
    _all_metadata(fixture)
    for record in fixture.records:
        _numbers(record)
    fixture_pin = _hash(
        {"version": VERSION, "protocol_sha256": protocol_pin, "fixture": asdict(fixture)}
    )
    if expected_fixture_sha256 is not _UNSUPPLIED:
        _require(expected_fixture_sha256 == fixture_pin, "Complete fixture expectation differs")
    return fixture_pin, protocol_pin


@_public
def fixture_sha256(fixture: FeatureWitnessFixture, *, expected_protocol_sha256: str) -> str:
    """Validate and hash the complete input only; this is not a replay claim."""
    return _prepare(fixture, expected_protocol_sha256)[0]


def _seal(value, field_name):
    body = asdict(value)
    body.pop(field_name)
    return replace(value, **{field_name: _hash(body)})


def _prefix_context(fixture, protocol_pin):
    # No complete fixture pin, future payload, terminal state or actual count.
    return _hash(
        {
            "version": VERSION,
            "protocol_sha256": protocol_pin,
            "fixture_id": fixture.fixture_id,
            "source_session": fixture.source_session,
            "utc_date": fixture.utc_date,
            "contract": fixture.contract,
            "instrument_id": fixture.instrument_id,
            "record_schema": list(_RECORD_FIELDS),
            "source_pins": [list(pair) for pair in _SOURCE_PINS],
        }
    )


def _capture(record, book, preceding):
    observed = execution.Record.capture(record, book)
    record_pin = _hash(asdict(record))
    prefix = _hash(
        {
            "preceding_prefix_sha256": preceding,
            "record_ordinal": record.record_ordinal,
            "record_sha256": record_pin,
        }
    )
    return observed, RecordAudit(
        record.record_ordinal, observed.before, record_pin, preceding, prefix
    )


def _quote(book, timestamp):
    _require(book.initialized is True, "Initialized empty-book genesis required")
    bid, ask = book.best("B"), book.best("A")
    _require(
        bid is not None and ask is not None and ask > bid,
        "Two-sided uncrossed completed state required",
    )
    bid_qty, ask_qty = book.levels["B"][bid], book.levels["A"][ask]
    _require(
        bid_qty > 0 and ask_qty > 0 and bid % TICK_NANO == 0 and ask % TICK_NANO == 0,
        "Positive on-grid completed quote required",
    )
    return clock.Quote(timestamp, bid, ask, bid_qty, ask_qty)


def _features(quote, flow, ofi_window, history, execution_window, book, prior_gap):
    now = quote.ts_recv_ns
    ofi_window.expire(now)
    flow.expire(now)
    depth = quote.bid_qty + quote.ask_qty
    trades = flow.known + flow.unknown
    base = (
        math.log1p(quote.bid_qty),
        math.log1p(quote.ask_qty),
        (quote.bid_qty - quote.ask_qty) / depth,
        2 * ofi_window.total / depth,
        2 * flow.cvd / depth,
        math.log1p(flow.known),
        flow.unknown / trades if trades else 0.0,
        math.log1p(prior_gap / 1000000),
    )
    depth_values = history.features(book, flow.cvd)
    execution_values = execution_window.features(quote)
    _require(
        tuple(depth_values) == FEATURE_NAMES[8:23]
        and tuple(execution_values) == FEATURE_NAMES[23:],
        "Complete derived feature schemas required",
    )
    travel = depth_values["mid_travel_5s_ticks"]
    if type(travel) is int and travel == 0:
        depth_values["mid_travel_5s_ticks"] = 0.0
    values = (
        *base,
        *(depth_values[name] for name in FEATURE_NAMES[8:23]),
        *(execution_values[name] for name in FEATURE_NAMES[23:]),
    )
    _require(
        len(values) == 37
        and all(type(value) is float and math.isfinite(value) for value in values),
        "All 37 exact finite feature values required",
    )
    return tuple(zip(FEATURE_NAMES, values, strict=True))


def _readiness(quote, first_ofi):
    now = quote.ts_recv_ns
    return (
        "spread_not_one_tick"
        if quote.spread_ticks != 1
        else "insufficient_feature_warmup"
        if first_ofi > now - FLOW_NS
        else "insufficient_window_for_hold"
        if now + READINESS_END_BUFFER_NS >= WINDOW_END_NS
        else None
    )


def _rebuild(fixture, fixture_pin, protocol_pin):
    book, flow = StrictBook(), clock.FiveSecondFlow()
    ofi_window, history, execution_window = (
        ofi.OfiWindow(),
        microdepth.QuoteHistory(),
        execution.ExecutionWindow(),
    )
    history_ofi, last_quote = None, None
    watch_since, inactive, next_publication = WARMUP_START_NS, False, WINDOW_START_NS
    context = _prefix_context(fixture, protocol_pin)
    genesis = fixture.records[0]
    _, genesis_audit = _capture(genesis, book, context)
    book.apply(genesis)
    audits, events, publications = [genesis_audit], [], []
    prefix = genesis_audit.prefix_sha256
    event_records, pending_trades, event_inactivity_reset = [], [], False

    for record in fixture.records[1:]:
        now = record.ts_recv
        # Timers are causal on every incoming record, not only a completion.
        if not inactive and now > watch_since + FLOW_NS:
            ofi_window = ofi.OfiWindow()
            inactive, event_inactivity_reset = True, True
        captured, audit = _capture(record, book, prefix)
        event_records.append(captured)
        book.apply(record)
        audits.append(audit)
        prefix = audit.prefix_sha256
        if record.action == "T":
            pending_trades.append(record)
        if record.flags != F_LAST:
            continue

        for trade in pending_trades:
            flow.add(now, trade)
        pending_trades.clear()
        quote = _quote(book, now)
        previous = last_quote
        prior_gap = now - previous.ts_recv_ns if previous is not None else 0
        ofi_window.observe(quote)
        if history_ofi is not ofi_window:
            history = microdepth.QuoteHistory()
            history_ofi = ofi_window
        history.observe(quote)
        inactive, watch_since = False, now
        temporal_reset = (
            execution_window.last_ts is None or now - execution_window.last_ts > FLOW_NS
        )
        stale_spanning = now - event_records[0].recv > FLOW_NS
        execution_window.complete(event_records, previous, quote, book)
        last_quote = quote
        _require(type(ofi_window.first_ts) is int, "Observed OFI start required")
        event_ordinal = len(events) + 1
        _require(event_ordinal <= MAX_COMPLETED_EVENTS, "Complete event bound exceeded")
        event = _seal(
            CompletedEventWitness(
                f"synthetic-completed-event-{event_ordinal:04d}",
                event_ordinal,
                record.record_ordinal - len(event_records) + 1,
                record.record_ordinal,
                event_records[0].recv,
                now,
                event_ordinal - 1,
                quote,
                prior_gap,
                ofi_window.first_ts,
                event_inactivity_reset,
                temporal_reset,
                stale_spanning,
                prefix,
                "",
            ),
            "event_sha256",
        )
        events.append(event)

        if now >= next_publication:
            values = _features(quote, flow, ofi_window, history, execution_window, book, prior_gap)
            reason = _readiness(quote, ofi_window.first_ts)
            ordinal = len(publications) + 1
            _require(ordinal <= MAX_PUBLICATIONS, "Complete publication bound exceeded")
            publication = _seal(
                FeaturePublication(
                    f"synthetic-feature-publication-{ordinal:04d}",
                    ordinal,
                    event_ordinal,
                    event.quote_ordinal,
                    now,
                    quote,
                    prefix,
                    event.event_sha256,
                    ofi_window.first_ts,
                    prior_gap,
                    flow.cvd,
                    flow.known,
                    flow.unknown,
                    ofi_window.total,
                    values,
                    reason is None,
                    reason,
                    "",
                ),
                "publication_sha256",
            )
            publications.append(publication)
            next_publication = now + MIN_PUBLICATION_CADENCE_NS
        event_records.clear()
        event_inactivity_reset = False

    _require(not event_records and not pending_trades, "Incomplete terminal source event refused")
    _require(events and publications, "A completed event and decision-window publication required")
    _require(
        events[0].first_record_ordinal == 2
        and events[-1].last_record_ordinal == len(fixture.records)
        and all(
            left.last_record_ordinal + 1 == right.first_record_ordinal
            for left, right in zip(events, events[1:], strict=False)
        ),
        "Complete adjacent event coverage required",
    )
    _require(len(audits) == len(fixture.records), "Every source record audit required")
    final_audit = tuple(sorted(execution_window.audit.items()))
    _require(
        all(type(name) is str and type(value) is int and value >= 0 for name, value in final_audit),
        "Complete helper execution audit required",
    )
    return _seal(
        FeaturePublicationWitness(
            VERSION,
            STATUS,
            protocol_pin,
            fixture_pin,
            fixture,
            context,
            tuple(audits),
            tuple(events),
            tuple(publications),
            final_audit,
            prefix,
            fixture.records[-1].ts_recv,
            len(fixture.records),
            len(events),
            len(events),
            len(publications),
            AUTHORITY_FLAGS,
            "",
        ),
        "witness_sha256",
    )


@_public
def replay(
    fixture: FeatureWitnessFixture, *, expected_fixture_sha256: str, expected_protocol_sha256: str
) -> FeaturePublicationWitness:
    """Rebuild the entire invented prefix after complete source/input preflight."""
    fixture_pin, protocol_pin = _prepare(fixture, expected_protocol_sha256, expected_fixture_sha256)
    return _rebuild(fixture, fixture_pin, protocol_pin)


def _same_types(value, reference):
    # Canonical JSON alone would erase tuple/list and int/float type distinctions.
    _require(type(value) is type(reference), "Exact complete witness nested type required")
    if is_dataclass(reference):
        _require(
            all(hasattr(value, field.name) for field in fields(reference)),
            "Complete witness nested fields required",
        )
        if hasattr(value, "__dict__"):
            _require(
                set(vars(value)) == {field.name for field in fields(reference)},
                "Unexpected witness nested attributes refused",
            )
        for field in fields(reference):
            _same_types(getattr(value, field.name), getattr(reference, field.name))
    elif type(reference) is tuple:
        _require(len(value) == len(reference), "Complete witness tuple length required")
        for item, expected in zip(value, reference, strict=True):
            _same_types(item, expected)


@_public
def verify(
    witness: FeaturePublicationWitness,
    fixture: FeatureWitnessFixture,
    *,
    expected_fixture_sha256: str,
    expected_protocol_sha256: str,
    expected_witness_sha256: str,
) -> None:
    """Reconstruct from independent original inputs, never submitted audit state."""
    fixture_pin, protocol_pin = _prepare(
        fixture, expected_protocol_sha256, expected_fixture_sha256, expected_witness_sha256
    )
    rebuilt = _rebuild(fixture, fixture_pin, protocol_pin)
    _require(
        rebuilt.witness_sha256 == expected_witness_sha256,
        "Complete rebuilt witness expectation differs",
    )
    _same_types(witness, rebuilt)
    _pin(witness.witness_sha256)
    body = asdict(witness)
    claimed = body.pop("witness_sha256")
    _require(
        _hash(body) == claimed == expected_witness_sha256,
        "Complete submitted witness digest differs",
    )
    rebuilt_body = asdict(rebuilt)
    rebuilt_body.pop("witness_sha256")
    _require(
        _canonical(body) == _canonical(rebuilt_body),
        "Complete original-input witness reconstruction differs",
    )
