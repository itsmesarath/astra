"""Classify complete invented decoded-item assertions, without native replay.

Payload and member pins are opaque caller assertions. Candidate ordinals identify
mapped occurrences, not successful book transitions or original native cursors.
There is no reader, decoder, numerical record body, historical or account hook.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from functools import wraps


@dataclass(frozen=True, slots=True)
class MappingInterval:
    start_date: str
    end_date: str
    instrument_symbol: str


@dataclass(frozen=True, slots=True)
class MappingGroup:
    contract: str
    intervals: tuple[MappingInterval, ...]


@dataclass(frozen=True, slots=True)
class DeclaredHeader:
    dataset: str
    schema: str
    symbols: tuple[str, ...]
    not_found: tuple[str, ...]
    start_ns: int
    end_ns: int
    mappings: tuple[MappingGroup, ...]


@dataclass(frozen=True, slots=True)
class DecodedItem:
    decoded_position: int
    kind: str
    instrument_id: int | None
    payload_sha256: str | None


@dataclass(frozen=True, slots=True)
class CursorFixture:
    fixture_id: str
    source_session: str
    utc_date: str
    contract: str
    header: DeclaredHeader
    asserted_member_sha256: str
    declared_item_count: int
    items: tuple[DecodedItem, ...]


@dataclass(frozen=True, slots=True)
class CursorAudit:
    decoded_position: int
    disposition: str
    instrument_id: int | None
    target_candidate_ordinal: int | None
    item_sha256: str
    prefix_sha256: str


@dataclass(frozen=True, slots=True)
class CursorAssessment:
    status: str
    protocol_sha256: str
    fixture_sha256: str
    fixture: CursorFixture
    mapped_instrument_id: int
    decoded_item_count: int
    target_candidate_count: int
    foreign_count: int
    audits: tuple[CursorAudit, ...]
    authority_flags: tuple[tuple[str, bool], ...]
    assessment_sha256: str


def _guard(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, TypeError, AttributeError, OverflowError) as exc:
            raise ValueError("Malformed complete constructed cursor metadata") from exc

    return checked


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _read(value, expected_type, fields):
    _require(type(value) is expected_type, "Exact frozen metadata type required")
    return {name: getattr(value, name) for name in fields}


def _integer(value, minimum, maximum):
    _require(
        type(value) is int and minimum <= value <= maximum,
        "Exact bounded integer required",
    )


def _name(value, *, maximum=64, synthetic=False):
    _require(
        type(value) is str
        and 1 <= len(value) <= maximum
        and re.fullmatch(r"[A-Za-z0-9._:-]+", value) is not None,
        "Exact bounded ASCII name required",
    )
    if synthetic:
        _require(
            re.fullmatch(r"synthetic-[A-Za-z0-9._:-]+", value) is not None,
            "Invented identifier with nonempty synthetic suffix required",
        )


def _pins(*values):
    # Inspect every expectation's syntax before equality or fixture traversal.
    valid = []
    for value in values:
        valid.append(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None)
    _require(all(valid), "Exact lowercase SHA256 pin required")


def _day(value):
    _require(
        type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is not None,
        "Canonical ASCII ISO date required",
    )
    parsed = date.fromisoformat(value)
    _require(
        date(2000, 1, 1) <= parsed <= date(2100, 12, 31) and parsed.isoformat() == value,
        "Canonical bounded date required",
    )
    return parsed


def _canonical(value):
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("Invalid complete canonical body") from exc


def _bounded_canonical(value):
    """Bound a complete canonical body; arbitrary guard tests are not fixtures."""
    raw = _canonical(value)
    _require(len(raw) <= 65_536, "Complete canonical body exceeds its byte bound")
    return raw


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _flags():
    # Fresh literal values: returned containers or exported constants cannot
    # silently change enforcement or complete protocol identity.
    return (
        ("account_authenticated", False),
        ("book_application_verified", False),
        ("broker_economics_measured", False),
        ("byte_offsets_verified", False),
        ("calendar_authenticated", False),
        ("decoded_source_authenticated", False),
        ("event_closure_verified", False),
        ("execution_allowed", False),
        ("feature_derivation_verified", False),
        ("funding_authenticated", False),
        ("historical_access_allowed", False),
        ("historical_validation_allowed", False),
        ("mapping_authenticated", False),
        ("model_call_allowed", False),
        ("native_decoding_verified", False),
        ("native_eof_verified", False),
        ("native_target_ordinals_verified", False),
        ("promotion_allowed", False),
        ("publication_cursor_verified", False),
        ("runtime_authenticated", False),
        ("scoring_allowed", False),
        ("source_authenticated", False),
        ("storage_resume_allowed", False),
        ("strategy_integration_allowed", False),
        ("trading_enabled", False),
        ("training_allowed", False),
    )


def _protocol_body():
    return {
        "version": "constructed_decoded_cursor_metadata_v1",
        "scope": "invented_header_mapping_and_decoded_item_assertions_only",
        "status": "constructed_decoded_cursor_metadata_not_native_verification",
        "utc_date": "2025-04-07",
        "contract": "6EM5",
        "dataset": "GLBX.MDP3",
        "schema": "mbo",
        "symbols": ["6E.FUT"],
        "not_found": [],
        "day_start_ns": 1_743_984_000_000_000_000,
        "day_end_ns": 1_744_070_400_000_000_000,
        "max_items": 128,
        "max_mapping_groups": 8,
        "max_intervals_per_group": 16,
        "max_total_intervals": 32,
        "max_body_bytes": 65_536,
        "max_instrument_id": 4_294_967_295,
        "decoded_position_origin": 1,
        "target_candidate_ordinal_origin": 1,
        "header_included": True,
        "payload_pins": "opaque_caller_assertions",
        "prefix_complete_member_pin": "excluded",
        "authority_flags": dict(_flags()),
    }


def _interval_body(value):
    body = _read(
        value,
        MappingInterval,
        ("start_date", "end_date", "instrument_symbol"),
    )
    start, end = _day(body["start_date"]), _day(body["end_date"])
    _require(start < end, "Mapping date interval must be strictly increasing")
    _name(body["instrument_symbol"], maximum=32)
    return body


def _header_body(value):
    body = _read(
        value,
        DeclaredHeader,
        ("dataset", "schema", "symbols", "not_found", "start_ns", "end_ns", "mappings"),
    )
    _require(
        type(body["dataset"]) is str and body["dataset"] == "GLBX.MDP3",
        "Exact declared dataset required",
    )
    _require(
        type(body["schema"]) is str and body["schema"] == "mbo",
        "Exact declared schema required",
    )
    symbols, not_found = body["symbols"], body["not_found"]
    _require(
        type(symbols) is tuple
        and len(symbols) == 1
        and type(symbols[0]) is str
        and symbols[0] == "6E.FUT",
        "Exact requested parent symbol tuple required",
    )
    _require(type(not_found) is tuple and not not_found, "Empty not-found tuple required")
    _integer(body["start_ns"], 1_743_984_000_000_000_000, 1_743_984_000_000_000_000)
    _integer(body["end_ns"], 1_744_070_400_000_000_000, 1_744_070_400_000_000_000)
    mappings = body["mappings"]
    _require(type(mappings) is tuple and 1 <= len(mappings) <= 8, "Complete mapping tuple required")
    groups, keys, total, active = [], [], 0, []
    for value in mappings:
        group = _read(value, MappingGroup, ("contract", "intervals"))
        _name(group["contract"], maximum=32)
        _require(group["contract"] not in keys, "Mapping keys must be unique")
        keys.append(group["contract"])
        intervals = group["intervals"]
        _require(
            type(intervals) is tuple and len(intervals) <= 16,
            "Complete bounded interval tuple required",
        )
        total += len(intervals)
        _require(total <= 32, "Complete mapping interval bound exceeded")
        projected = []
        for interval in intervals:
            entry = _interval_body(interval)
            projected.append(entry)
            if (
                group["contract"] == "6EM5"
                and entry["start_date"] <= "2025-04-07" < entry["end_date"]
            ):
                active.append(entry["instrument_symbol"])
        groups.append({"contract": group["contract"], "intervals": projected})
    _require("6EM5" in keys and len(active) == 1, "Exactly one requested active mapping required")
    _require(
        re.fullmatch(r"[0-9]+", active[0]) is not None,
        "Active target mapping must be ASCII decimal",
    )
    mapped_id = int(active[0])
    _integer(mapped_id, 0, 4_294_967_295)
    return {
        "dataset": body["dataset"],
        "schema": body["schema"],
        "symbols": list(symbols),
        "not_found": list(not_found),
        "start_ns": body["start_ns"],
        "end_ns": body["end_ns"],
        "mappings": groups,
    }, mapped_id


def _item_body(value, position):
    body = _read(
        value,
        DecodedItem,
        ("decoded_position", "kind", "instrument_id", "payload_sha256"),
    )
    _integer(body["decoded_position"], 1, 128)
    _require(body["decoded_position"] == position, "Complete decoded positions must be contiguous")
    _require(type(body["kind"]) is str, "Exact decoded kind required")
    if position == 1:
        _require(
            body["kind"] == "metadata"
            and body["instrument_id"] is None
            and body["payload_sha256"] is None,
            "Only the first metadata item has exact None fields",
        )
    else:
        _require(body["kind"] == "mbo", "Unexpected decoded item kind")
        _integer(body["instrument_id"], 0, 4_294_967_295)
        _pins(body["payload_sha256"])
    return body


def _fixture_body(value):
    body = _read(
        value,
        CursorFixture,
        (
            "fixture_id",
            "source_session",
            "utc_date",
            "contract",
            "header",
            "asserted_member_sha256",
            "declared_item_count",
            "items",
        ),
    )
    _name(body["fixture_id"], synthetic=True)
    _name(body["source_session"], synthetic=True)
    _require(
        type(body["utc_date"]) is str and body["utc_date"] == "2025-04-07",
        "Fixed invented UTC date required",
    )
    _require(
        type(body["contract"]) is str and body["contract"] == "6EM5",
        "Fixed invented contract required",
    )
    _pins(body["asserted_member_sha256"])
    _integer(body["declared_item_count"], 2, 128)
    items = body["items"]
    _require(
        type(items) is tuple and len(items) == body["declared_item_count"],
        "Complete item tuple must match its declared count",
    )
    header, mapped_id = _header_body(body["header"])
    projected = [_item_body(item, position) for position, item in enumerate(items, 1)]
    _require(
        any(item["instrument_id"] == mapped_id for item in projected[1:]),
        "At least one mapped target candidate required",
    )
    return {
        "fixture_id": body["fixture_id"],
        "source_session": body["source_session"],
        "utc_date": body["utc_date"],
        "contract": body["contract"],
        "header": header,
        "asserted_member_sha256": body["asserted_member_sha256"],
        "declared_item_count": body["declared_item_count"],
        "items": projected,
    }, mapped_id


def _audit_body(value):
    body = _read(
        value,
        CursorAudit,
        (
            "decoded_position",
            "disposition",
            "instrument_id",
            "target_candidate_ordinal",
            "item_sha256",
            "prefix_sha256",
        ),
    )
    _integer(body["decoded_position"], 1, 128)
    disposition = body["disposition"]
    _require(
        type(disposition) is str and disposition in ("header", "foreign", "target_candidate"),
        "Closed audit disposition required",
    )
    if disposition == "header":
        _require(
            body["decoded_position"] == 1
            and body["instrument_id"] is None
            and body["target_candidate_ordinal"] is None,
            "Header audit must retain exact None fields",
        )
    else:
        _integer(body["instrument_id"], 0, 4_294_967_295)
        if disposition == "foreign":
            _require(body["target_candidate_ordinal"] is None, "Foreign candidate ordinal is None")
        else:
            _integer(body["target_candidate_ordinal"], 1, 127)
    _pins(body["item_sha256"], body["prefix_sha256"])
    return body


def _flags_body(value):
    expected = _flags()
    _require(
        type(value) is tuple and len(value) == len(expected), "Complete authority tuple required"
    )
    for supplied, original in zip(value, expected, strict=True):
        _require(type(supplied) is tuple and len(supplied) == 2, "Exact authority pair required")
        _require(
            type(supplied[0]) is str and supplied[0] == original[0] and supplied[1] is False,
            "Every exact authority must stay False in original order",
        )
    return dict(value)


def _assessment_body(value):
    body = _read(
        value,
        CursorAssessment,
        (
            "status",
            "protocol_sha256",
            "fixture_sha256",
            "fixture",
            "mapped_instrument_id",
            "decoded_item_count",
            "target_candidate_count",
            "foreign_count",
            "audits",
            "authority_flags",
            "assessment_sha256",
        ),
    )
    _require(
        type(body["status"]) is str
        and body["status"] == "constructed_decoded_cursor_metadata_not_native_verification",
        "Exact constructed-only status required",
    )
    _pins(body["protocol_sha256"], body["fixture_sha256"], body["assessment_sha256"])
    fixture_body, _ = _fixture_body(body["fixture"])
    _integer(body["mapped_instrument_id"], 0, 4_294_967_295)
    _integer(body["decoded_item_count"], 2, 128)
    _integer(body["target_candidate_count"], 1, 127)
    _integer(body["foreign_count"], 0, 126)
    _require(
        body["decoded_item_count"] == 1 + body["target_candidate_count"] + body["foreign_count"],
        "Complete assessment counts must reconcile",
    )
    audits = body["audits"]
    _require(
        type(audits) is tuple and len(audits) == body["decoded_item_count"],
        "Complete audit tuple required",
    )
    projected = [_audit_body(audit) for audit in audits]
    flags = _flags_body(body["authority_flags"])
    return {
        "status": body["status"],
        "protocol_sha256": body["protocol_sha256"],
        "fixture_sha256": body["fixture_sha256"],
        "fixture": fixture_body,
        "mapped_instrument_id": body["mapped_instrument_id"],
        "decoded_item_count": body["decoded_item_count"],
        "target_candidate_count": body["target_candidate_count"],
        "foreign_count": body["foreign_count"],
        "audits": projected,
        "authority_flags": flags,
    }


def _checked_fixture(fixture, expected_protocol_sha256):
    protocol_pin = _digest(_protocol_body())
    _require(protocol_pin == expected_protocol_sha256, "Original complete protocol pin differs")
    body, mapped_id = _fixture_body(fixture)
    fixture_pin = hashlib.sha256(_bounded_canonical(body)).hexdigest()
    return protocol_pin, fixture_pin, body, mapped_id


def _construct(fixture, expected_fixture_sha256, expected_protocol_sha256):
    protocol_pin, fixture_pin, body, mapped_id = _checked_fixture(fixture, expected_protocol_sha256)
    _require(fixture_pin == expected_fixture_sha256, "Original complete fixture pin differs")
    prefix = _digest(
        {
            "protocol_sha256": protocol_pin,
            "fixture_id": body["fixture_id"],
            "source_session": body["source_session"],
            "utc_date": body["utc_date"],
            "contract": body["contract"],
            "header": body["header"],
        }
    )
    audits, targets, foreign = [], 0, 0
    for item in body["items"]:
        item_pin = _digest(item)
        prefix = _digest({"previous_prefix_sha256": prefix, "item": item})
        ordinal = None
        if item["kind"] == "metadata":
            disposition = "header"
        elif item["instrument_id"] == mapped_id:
            disposition = "target_candidate"
            targets += 1
            ordinal = targets
        else:
            disposition = "foreign"
            foreign += 1
        audits.append(
            CursorAudit(
                item["decoded_position"],
                disposition,
                item["instrument_id"],
                ordinal,
                item_pin,
                prefix,
            )
        )
    result = CursorAssessment(
        "constructed_decoded_cursor_metadata_not_native_verification",
        protocol_pin,
        fixture_pin,
        fixture,
        mapped_id,
        len(body["items"]),
        targets,
        foreign,
        tuple(audits),
        _flags(),
        "0" * 64,
    )
    assessment_pin = hashlib.sha256(_bounded_canonical(_assessment_body(result))).hexdigest()
    return CursorAssessment(
        result.status,
        result.protocol_sha256,
        result.fixture_sha256,
        result.fixture,
        result.mapped_instrument_id,
        result.decoded_item_count,
        result.target_candidate_count,
        result.foreign_count,
        result.audits,
        result.authority_flags,
        assessment_pin,
    )


@_guard
def protocol() -> dict:
    """Return the fresh complete literal constructed protocol."""
    return _protocol_body()


@_guard
def protocol_sha256() -> str:
    """Pin the complete literal protocol without inspecting a fixture."""
    return _digest(_protocol_body())


@_guard
def fixture_sha256(fixture: CursorFixture, *, expected_protocol_sha256: str) -> str:
    """Validate every declaration and pin the complete original fixture."""
    _pins(expected_protocol_sha256)
    _, fixture_pin, _, _ = _checked_fixture(fixture, expected_protocol_sha256)
    return fixture_pin


@_guard
def assess(
    fixture: CursorFixture,
    *,
    expected_fixture_sha256: str,
    expected_protocol_sha256: str,
) -> CursorAssessment:
    """Retain all asserted decoded dispositions; authenticate no referent."""
    _pins(expected_protocol_sha256, expected_fixture_sha256)
    return _construct(fixture, expected_fixture_sha256, expected_protocol_sha256)


@_guard
def verify(
    assessment: CursorAssessment,
    fixture: CursorFixture,
    *,
    expected_fixture_sha256: str,
    expected_protocol_sha256: str,
    expected_assessment_sha256: str,
) -> None:
    """Rebuild all original fields and exact types, never adopt an audit head."""
    _pins(expected_protocol_sha256, expected_fixture_sha256, expected_assessment_sha256)
    rebuilt = _construct(fixture, expected_fixture_sha256, expected_protocol_sha256)
    _require(
        rebuilt.assessment_sha256 == expected_assessment_sha256,
        "Original complete assessment pin differs",
    )
    supplied_body = _assessment_body(assessment)
    supplied_raw = _bounded_canonical(supplied_body)
    rebuilt_raw = _bounded_canonical(_assessment_body(rebuilt))
    _require(
        supplied_raw == rebuilt_raw
        and assessment.assessment_sha256 == expected_assessment_sha256
        and hashlib.sha256(supplied_raw).hexdigest() == expected_assessment_sha256,
        "Submitted complete assessment differs from original reconstruction",
    )
    return None
