"""Pure synthetic native-prefix consistency, never feed or execution authority.

Validates the complete supplied fixture, but publishes only consumed quotes and
separate timestamp-only boundary evidence. No files, clocks, policy, accounting,
models, historical loaders, persistence or orders are accessed. Retained pins
and prefixes are required; a replacement invented fixture is not authenticated.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields

VERSION = "six_e_native_prefix_v1"
TICK_NANO, SECOND_NS = 50_000, 1_000_000_000
MAX_QUOTES, MAX_PUBLICATIONS, MAX_INPUT_BYTES = 1024, 64, 256 * 1024
MAX_INT = 2**63 - 1
AUTHORITY_FLAGS = tuple(
    (name, False)
    for name in (
        "source_authenticated",
        "feed_authenticated",
        "runtime_authenticated",
        "genesis_authenticated",
        "prefix_authenticated",
        "publication_event_authenticated",
        "consumer_coverage_verified",
        "receipt_authenticated",
        "account_authenticated",
        "cash_confirmed",
        "margin_confirmed",
        "risk_confirmed",
        "execution_confirmed",
        "broker_execution_confirmed",
        "storage_authorized",
        "resume_authorized",
        "trading_enabled",
        "training_enabled",
        "strategy_scoring_allowed",
        "independent_validation",
        "promotion_allowed",
    )
)


class NativePrefixError(ValueError):
    """Malformed or conflicting constructed fixture or retained witness."""


def _require(condition, message):
    if not condition:
        raise NativePrefixError(message)


def _integer(value, low=0, high=MAX_INT):
    _require(type(value) is int and low <= value <= high, "Exact bounded integer required")


def _identifier(value):
    _require(
        type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value),
        "Exact bounded ASCII identifier required",
    )


def _pin(value):
    _require(
        type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value),
        "Exact lowercase SHA256 required",
    )


def _typed(value, cls):
    _require(type(value) is cls, f"Exact {cls.__name__} required")
    _require(all(hasattr(value, field.name) for field in fields(cls)), "Incomplete typed object")


def _metadata_fields(value):
    _identifier(value.source_session)
    _require(
        value.source_session.startswith("synthetic-") and len(value.source_session) > 10,
        "Explicit nonempty synthetic session label required",
    )
    _require(
        type(value.contract) is str and re.fullmatch(r"6E[HMUZ][0-9]", value.contract),
        "Declared dated 6E label required, not calendar authentication",
    )
    _pin(value.source_sha256)
    _integer(value.start_ns)
    _integer(value.end_ns)
    _require(value.start_ns < value.end_ns, "Nonempty bounded declared interval required")


def _canonical(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    _require(len(raw) <= MAX_INPUT_BYTES, "Complete canonical input exceeds byte bound")
    return raw


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class NativeQuote:
    received_at_ns: int
    bid_nano: int
    ask_nano: int

    def __post_init__(self):
        _quote_fields(self)


@dataclass(frozen=True, slots=True)
class NativePublication:
    publication_id: str
    published_cursor: int
    received_at_ns: int

    def __post_init__(self):
        _publication_fields(self)


@dataclass(frozen=True, slots=True)
class NativeFixture:
    source_session: str
    contract: str
    source_sha256: str
    start_ns: int
    end_ns: int
    quotes: tuple[NativeQuote, ...]
    publications: tuple[NativePublication, ...]

    def __post_init__(self):
        _fixture_raw(self)


@dataclass(frozen=True, slots=True)
class NativePrefix:
    fixture_sha256: str
    source_session: str
    contract: str
    source_sha256: str
    start_ns: int
    end_ns: int
    total_quotes: int
    total_publications: int
    consumed_count: int
    last_cursor: int | None
    last_received_at_ns: int | None
    current_timestamp_first_cursor: int | None
    consumed_content_sha256: str
    authority_flags: tuple[tuple[str, bool], ...] = AUTHORITY_FLAGS

    def __post_init__(self):
        _prefix_fields(self)


@dataclass(frozen=True, slots=True)
class ConsumedNativeQuote:
    native_cursor: int
    quote: NativeQuote
    prefix: NativePrefix


@dataclass(frozen=True, slots=True)
class PublicationWitness:
    publication_id: str
    published_cursor: int
    received_at_ns: int
    prefix: NativePrefix
    boundary_state: str = "OPEN"
    authority_flags: tuple[tuple[str, bool], ...] = AUTHORITY_FLAGS


@dataclass(frozen=True, slots=True)
class ClosedNativeBoundary:
    prefix: NativePrefix
    through_ns: int
    closure_kind: str
    next_cursor: int | None
    next_received_at_ns: int | None
    boundary_state: str = "CLOSED"
    authority_flags: tuple[tuple[str, bool], ...] = AUTHORITY_FLAGS


def _quote_fields(quote):
    _typed(quote, NativeQuote)
    _integer(quote.received_at_ns)
    for price in (quote.bid_nano, quote.ask_nano):
        _integer(price, TICK_NANO)
        _require(price % TICK_NANO == 0, "Positive on-grid quote price required")
    _require(quote.bid_nano < quote.ask_nano, "Strictly uncrossed bid/ask required")


def _publication_fields(publication):
    _typed(publication, NativePublication)
    _identifier(publication.publication_id)
    _integer(publication.published_cursor, 0, MAX_QUOTES - 1)
    _integer(publication.received_at_ns)


def _metadata(fixture):
    return {
        "version": VERSION,
        "source_session": fixture.source_session,
        "contract": fixture.contract,
        "source_sha256": fixture.source_sha256,
        "start_ns": fixture.start_ns,
        "end_ns": fixture.end_ns,
        "tick_nano": TICK_NANO,
    }


def _quote_value(quote):
    return [quote.received_at_ns, quote.bid_nano, quote.ask_nano]


def _fixture_raw(fixture):
    _typed(fixture, NativeFixture)
    _metadata_fields(fixture)  # Metadata and tuple caps precede price inspection.
    _require(
        type(fixture.quotes) is tuple and len(fixture.quotes) <= MAX_QUOTES,
        "Complete bounded immutable quote tuple required",
    )
    _require(
        type(fixture.publications) is tuple and len(fixture.publications) <= MAX_PUBLICATIONS,
        "Complete bounded immutable publication tuple required",
    )
    declarations, seen, previous = [], set(), None
    for publication in fixture.publications:
        _publication_fields(publication)
        _require(publication.publication_id not in seen, "Unique publication IDs required")
        seen.add(publication.publication_id)
        _require(
            publication.published_cursor < len(fixture.quotes)
            and fixture.start_ns <= publication.received_at_ns < fixture.end_ns,
            "Publication must identify supplied interval/cursor",
        )
        if previous is not None:
            _require(
                publication.published_cursor > previous.published_cursor
                and publication.received_at_ns - previous.received_at_ns >= SECOND_NS,
                "Chronological first-row publications at least one second apart required",
            )
        previous = publication
        declarations.append(
            {
                "publication_id": publication.publication_id,
                "published_cursor": publication.published_cursor,
                "received_at_ns": publication.received_at_ns,
            }
        )
    body = {
        "version": VERSION,
        "kind": "complete_constructed_native_fixture",
        "metadata": _metadata(fixture),
        "quote_count": len(fixture.quotes),
        "publication_count": len(fixture.publications),
        "quotes": [],
        "publications": declarations,
    }
    _canonical(body)  # Known minimum byte guard; final size also checked below.
    previous_time = None
    for quote in fixture.quotes:
        _quote_fields(quote)
        _require(
            fixture.start_ns <= quote.received_at_ns < fixture.end_ns
            and (previous_time is None or previous_time <= quote.received_at_ns),
            "Native receive timestamps must be ordered inside declared interval",
        )
        previous_time = quote.received_at_ns
        body["quotes"].append(_quote_value(quote))
    for publication in fixture.publications:
        cursor, now = publication.published_cursor, publication.received_at_ns
        _require(
            fixture.quotes[cursor].received_at_ns == now
            and (cursor == 0 or fixture.quotes[cursor - 1].received_at_ns < now),
            "Publication must follow its first native quote at the declared timestamp",
        )
    return _canonical(body)


def _prefix_fields(prefix):
    _typed(prefix, NativePrefix)
    _metadata_fields(prefix)
    _pin(prefix.fixture_sha256)
    _pin(prefix.consumed_content_sha256)
    _integer(prefix.total_quotes, 0, MAX_QUOTES)
    _integer(prefix.total_publications, 0, MAX_PUBLICATIONS)
    _integer(prefix.consumed_count, 0, prefix.total_quotes)
    if prefix.consumed_count == 0:
        _require(
            prefix.last_cursor is None
            and prefix.last_received_at_ns is None
            and prefix.current_timestamp_first_cursor is None,
            "Empty prefix requires null observation fields",
        )
    else:
        _integer(prefix.last_cursor, 0, prefix.consumed_count - 1)
        _require(prefix.last_cursor == prefix.consumed_count - 1, "Exact last cursor required")
        _integer(prefix.last_received_at_ns, prefix.start_ns, prefix.end_ns - 1)
        _integer(prefix.current_timestamp_first_cursor, 0, prefix.last_cursor)
    flags = prefix.authority_flags
    _require(
        type(flags) is tuple and len(flags) == len(AUTHORITY_FLAGS),
        "Exact bounded immutable false authority tuple required",
    )
    _require(
        all(
            type(item) is tuple and len(item) == 2 and type(item[0]) is str and item[1] is False
            for item in flags
        )
        and flags == AUTHORITY_FLAGS,
        "Every exact authority flag must remain false",
    )


def fixture_sha256(fixture: NativeFixture) -> str:
    """Generate a prospective local pin, not an independently retained expectation."""
    return hashlib.sha256(_fixture_raw(fixture)).hexdigest()


def prepare_fixture(fixture: NativeFixture, *, expected_fixture_sha256: str) -> NativeFixture:
    """Revalidate all bounded supplied input against its separately retained pin."""
    _pin(expected_fixture_sha256)
    _require(fixture_sha256(fixture) == expected_fixture_sha256, "Complete fixture pin differs")
    return fixture


def _prefix(fixture, fixture_pin, count):
    head = _digest(
        {"version": VERSION, "kind": "consumed_metadata_seed", "metadata": _metadata(fixture)}
    )
    last_time, run_first = None, None
    for cursor in range(count):
        quote = fixture.quotes[cursor]
        if last_time != quote.received_at_ns:
            run_first = cursor
        last_time = quote.received_at_ns
        head = _digest(
            {
                "version": VERSION,
                "kind": "consumed_quote",
                "previous_sha256": head,
                "native_cursor": cursor,
                "quote": _quote_value(quote),
            }
        )
    return NativePrefix(
        fixture_pin,
        fixture.source_session,
        fixture.contract,
        fixture.source_sha256,
        fixture.start_ns,
        fixture.end_ns,
        len(fixture.quotes),
        len(fixture.publications),
        count,
        count - 1 if count else None,
        last_time,
        run_first,
        head,
    )


def initial_prefix(fixture: NativeFixture, *, expected_fixture_sha256: str) -> NativePrefix:
    """Return the empty consumed witness; complete preparation is not observation."""
    prepare_fixture(fixture, expected_fixture_sha256=expected_fixture_sha256)
    return _prefix(fixture, expected_fixture_sha256, 0)


def verify_prefix(
    fixture: NativeFixture, *, expected_fixture_sha256: str, expected_prefix: NativePrefix
) -> NativePrefix:
    """Reconstruct and exactly compare the full externally retained witness."""
    prepare_fixture(fixture, expected_fixture_sha256=expected_fixture_sha256)
    _prefix_fields(expected_prefix)
    _require(expected_prefix.consumed_count <= len(fixture.quotes), "Prefix count exceeds input")
    prefix = _prefix(fixture, expected_fixture_sha256, expected_prefix.consumed_count)
    _require(prefix == expected_prefix, "Exact retained native prefix differs")
    return prefix


def consume_next(
    fixture: NativeFixture,
    *,
    expected_fixture_sha256: str,
    expected_prefix: NativePrefix,
    expected_cursor: int,
) -> ConsumedNativeQuote:
    """Consume only the next quote purely; repeated calls are not persisted events."""
    prefix = verify_prefix(
        fixture, expected_fixture_sha256=expected_fixture_sha256, expected_prefix=expected_prefix
    )
    _integer(expected_cursor, 0, MAX_QUOTES - 1)
    _require(
        expected_cursor == prefix.consumed_count and expected_cursor < len(fixture.quotes),
        "Exact next unconsumed native cursor required",
    )
    return ConsumedNativeQuote(
        expected_cursor,
        fixture.quotes[expected_cursor],
        _prefix(fixture, expected_fixture_sha256, expected_cursor + 1),
    )


def publication_witness(
    fixture: NativeFixture,
    *,
    expected_fixture_sha256: str,
    expected_prefix: NativePrefix,
    publication_id: str,
) -> PublicationWitness:
    """Publish after the original first row, never after its equal-time suffix."""
    prefix = verify_prefix(
        fixture, expected_fixture_sha256=expected_fixture_sha256, expected_prefix=expected_prefix
    )
    _identifier(publication_id)
    publication = next(
        (p for p in fixture.publications if p.publication_id == publication_id), None
    )
    _require(publication is not None, "Pinned original publication required")
    _require(
        prefix.consumed_count == publication.published_cursor + 1,
        "Publication requires its exact first-row consumed prefix",
    )
    return PublicationWitness(
        publication.publication_id, publication.published_cursor, publication.received_at_ns, prefix
    )


def close_through(
    fixture: NativeFixture,
    *,
    expected_fixture_sha256: str,
    expected_prefix: NativePrefix,
    through_ns: int,
) -> ClosedNativeBoundary:
    """Return timestamp-only supplied boundary evidence, not deadline authority."""
    prefix = verify_prefix(
        fixture, expected_fixture_sha256=expected_fixture_sha256, expected_prefix=expected_prefix
    )
    _integer(through_ns, fixture.start_ns, fixture.end_ns)
    _require(
        prefix.last_received_at_ns is None or prefix.last_received_at_ns <= through_ns,
        "A quote beyond the requested boundary was already consumed",
    )
    cursor = prefix.consumed_count
    if cursor == len(fixture.quotes):
        return ClosedNativeBoundary(prefix, through_ns, "complete_eof", None, None)
    next_time = fixture.quotes[cursor].received_at_ns
    _require(next_time > through_ns, "Every native row at or before the boundary must be consumed")
    return ClosedNativeBoundary(prefix, through_ns, "next_timestamp", cursor, next_time)
