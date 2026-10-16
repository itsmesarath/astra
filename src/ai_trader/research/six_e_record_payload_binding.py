"""Bind complete invented MBO JSON bodies to constructed cursor assertions.

Exact JSON consistency is not native decoding, source authentication or book
acceptance. There is no reader, decoder, account, model or execution hook.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import wraps

from ai_trader.research import six_e_native_cursor_metadata as cursor


@dataclass(frozen=True, slots=True)
class PayloadContext:
    codec_id: str
    schema_version: int
    ts_out_mode: str


@dataclass(frozen=True, slots=True)
class MboPayload:
    publisher_id: int
    instrument_id: int
    ts_event: int
    order_id: int
    price: int
    size: int
    action: str
    side: str
    ts_recv: int
    flags: int
    channel_id: int
    ts_in_delta: int
    sequence: int
    ts_out: int | None
    rtype: int
    record_size: int


@dataclass(frozen=True, slots=True)
class PayloadBundle:
    context: PayloadContext
    cursor_fixture: cursor.CursorFixture
    payloads: tuple[MboPayload | None, ...]


@dataclass(frozen=True, slots=True)
class PayloadAudit:
    decoded_position: int
    disposition: str
    instrument_id: int | None
    target_candidate_ordinal: int | None
    payload_sha256: str | None
    cursor_item_sha256: str
    cursor_prefix_sha256: str
    bound_prefix_sha256: str


@dataclass(frozen=True, slots=True)
class BindingAssessment:
    status: str
    protocol_sha256: str
    context_sha256: str
    cursor_protocol_sha256: str
    cursor_fixture_sha256: str
    bundle_sha256: str
    bundle: PayloadBundle
    cursor_assessment: cursor.CursorAssessment
    audits: tuple[PayloadAudit, ...]
    authority_flags: tuple[tuple[str, bool], ...]
    assessment_sha256: str


def _guard(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, TypeError, AttributeError, OverflowError) as exc:
            raise ValueError("Malformed complete constructed payload binding") from exc

    return checked


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _read(value, expected_type, fields):
    _require(type(value) is expected_type, "Exact frozen type required")
    return {name: getattr(value, name) for name in fields}


def _pins(*values):
    valid = []
    for value in values:
        valid.append(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None)
    _require(all(valid), "Exact lowercase SHA256 pin required")


def _integer(value, minimum, maximum):
    _require(type(value) is int and minimum <= value <= maximum, "Exact bounded integer required")


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _bounded_canonical(value):
    """Bound each complete new bundle/result, independently of old cursor caps."""
    raw = _canonical(value)
    _require(len(raw) <= 262_144, "Complete constructed body exceeds its byte bound")
    return raw


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _flags():
    return (
        ("account_authenticated", False),
        ("book_application_verified", False),
        ("broker_economics_measured", False),
        ("byte_offsets_verified", False),
        ("calendar_authenticated", False),
        ("codec_context_authenticated", False),
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
        ("native_header_verified", False),
        ("native_payloads_verified", False),
        ("native_record_semantics_verified", False),
        ("native_target_ordinals_verified", False),
        ("original_bytes_verified", False),
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
    # Every enforcement choice is literal and each returned container is fresh.
    return {
        "version": "constructed_record_payload_binding_v1",
        "scope": "invented_complete_mbo_json_bodies_and_contextual_cursor_binding_only",
        "status": "constructed_record_payload_binding_not_native_verification",
        "codec_id": "constructed_mbo_json_v1",
        "schema_version": 1,
        "ts_out_modes": ["absent", "present"],
        "record_field_order": [
            "publisher_id",
            "instrument_id",
            "ts_event",
            "order_id",
            "price",
            "size",
            "action",
            "side",
            "ts_recv",
            "flags",
            "channel_id",
            "ts_in_delta",
            "sequence",
            "ts_out",
            "rtype",
            "record_size",
        ],
        "integer_bounds": {
            "publisher_id": [0, 18_446_744_073_709_551_615],
            "instrument_id": [0, 4_294_967_295],
            "ts_event": [-9_223_372_036_854_775_808, 9_223_372_036_854_775_807],
            "order_id": [0, 18_446_744_073_709_551_615],
            "price": [-9_223_372_036_854_775_808, 9_223_372_036_854_775_807],
            "size": [0, 18_446_744_073_709_551_615],
            "ts_recv": [-9_223_372_036_854_775_808, 9_223_372_036_854_775_807],
            "flags": [0, 18_446_744_073_709_551_615],
            "channel_id": [0, 18_446_744_073_709_551_615],
            "ts_in_delta": [-9_223_372_036_854_775_808, 9_223_372_036_854_775_807],
            "sequence": [0, 18_446_744_073_709_551_615],
            "ts_out": [-9_223_372_036_854_775_808, 9_223_372_036_854_775_807],
            "rtype": [0, 18_446_744_073_709_551_615],
            "record_size": [1, 65_536],
        },
        "action_side_length": 1,
        "action_side_codepoint_min": 0,
        "action_side_codepoint_max": 127,
        "min_items": 2,
        "max_items": 128,
        "max_payloads": 127,
        "max_body_bytes": 262_144,
        "max_cursor_body_bytes": 65_536,
        "metadata_payload": "literal_none",
        "context_pin_scheme": "sha256_canonical_context_body",
        "payload_pin_scheme": "sha256_canonical_complete_record_body",
        "contextual_prefix_scheme": "sha256_binding_protocol_context_cursor_prefix",
        "prefix_complete_member_pin": "excluded",
        "cursor_protocol_sha256": cursor.protocol_sha256(),
        "cursor_source_sha256": "c7bc0102073fa61f1d69411479331cf1e434616cb80faa6bbc266377745dcf91",
        "dataclass_fields": {
            "PayloadContext": ["codec_id", "schema_version", "ts_out_mode"],
            "MboPayload": [
                "publisher_id",
                "instrument_id",
                "ts_event",
                "order_id",
                "price",
                "size",
                "action",
                "side",
                "ts_recv",
                "flags",
                "channel_id",
                "ts_in_delta",
                "sequence",
                "ts_out",
                "rtype",
                "record_size",
            ],
            "PayloadBundle": ["context", "cursor_fixture", "payloads"],
            "PayloadAudit": [
                "decoded_position",
                "disposition",
                "instrument_id",
                "target_candidate_ordinal",
                "payload_sha256",
                "cursor_item_sha256",
                "cursor_prefix_sha256",
                "bound_prefix_sha256",
            ],
            "BindingAssessment": [
                "status",
                "protocol_sha256",
                "context_sha256",
                "cursor_protocol_sha256",
                "cursor_fixture_sha256",
                "bundle_sha256",
                "bundle",
                "cursor_assessment",
                "audits",
                "authority_flags",
                "assessment_sha256",
            ],
        },
        "authority_flags": dict(_flags()),
    }


def _expect_protocol(expected_protocol_sha256):
    _require(_digest(_protocol_body()) == expected_protocol_sha256, "Binding protocol pin differs")


def _context_body(context):
    body = _read(context, PayloadContext, ("codec_id", "schema_version", "ts_out_mode"))
    _require(
        type(body["codec_id"]) is str and body["codec_id"] == "constructed_mbo_json_v1",
        "Exact constructed codec required",
    )
    _integer(body["schema_version"], 1, 1)
    _require(
        type(body["ts_out_mode"]) is str and body["ts_out_mode"] in ("absent", "present"),
        "Explicit constructed ts_out mode required",
    )
    return body


def _payload_body(payload, context_body):
    body = _read(
        payload,
        MboPayload,
        (
            "publisher_id",
            "instrument_id",
            "ts_event",
            "order_id",
            "price",
            "size",
            "action",
            "side",
            "ts_recv",
            "flags",
            "channel_id",
            "ts_in_delta",
            "sequence",
            "ts_out",
            "rtype",
            "record_size",
        ),
    )
    _integer(body["instrument_id"], 0, 4_294_967_295)
    for name in ("publisher_id", "order_id", "size", "flags", "channel_id", "sequence", "rtype"):
        _integer(body[name], 0, 18_446_744_073_709_551_615)
    for name in ("price", "ts_event", "ts_recv", "ts_in_delta"):
        _integer(body[name], -9_223_372_036_854_775_808, 9_223_372_036_854_775_807)
    _integer(body["record_size"], 1, 65_536)
    for name in ("action", "side"):
        value = body[name]
        _require(
            type(value) is str and len(value) == 1 and ord(value) <= 127, "Exact ASCII required"
        )
    if context_body["ts_out_mode"] == "absent":
        _require(body["ts_out"] is None, "Absent mode retains literal None")
    else:
        _integer(body["ts_out"], -9_223_372_036_854_775_808, 9_223_372_036_854_775_807)
    return body


def _cursor_fixture_body(fixture):
    """Project only after the unchanged public cursor API validates metadata."""
    header = fixture.header
    return {
        "fixture_id": fixture.fixture_id,
        "source_session": fixture.source_session,
        "utc_date": fixture.utc_date,
        "contract": fixture.contract,
        "header": {
            "dataset": header.dataset,
            "schema": header.schema,
            "symbols": list(header.symbols),
            "not_found": list(header.not_found),
            "start_ns": header.start_ns,
            "end_ns": header.end_ns,
            "mappings": [
                {
                    "contract": group.contract,
                    "intervals": [
                        {
                            "start_date": interval.start_date,
                            "end_date": interval.end_date,
                            "instrument_symbol": interval.instrument_symbol,
                        }
                        for interval in group.intervals
                    ],
                }
                for group in header.mappings
            ],
        },
        "asserted_member_sha256": fixture.asserted_member_sha256,
        "declared_item_count": fixture.declared_item_count,
        "items": [
            {
                "decoded_position": item.decoded_position,
                "kind": item.kind,
                "instrument_id": item.instrument_id,
                "payload_sha256": item.payload_sha256,
            }
            for item in fixture.items
        ],
    }


def _cursor_assessment_body(assessment):
    """Keep the complete validated old result, including its own digest."""
    return {
        "status": assessment.status,
        "protocol_sha256": assessment.protocol_sha256,
        "fixture_sha256": assessment.fixture_sha256,
        "fixture": _cursor_fixture_body(assessment.fixture),
        "mapped_instrument_id": assessment.mapped_instrument_id,
        "decoded_item_count": assessment.decoded_item_count,
        "target_candidate_count": assessment.target_candidate_count,
        "foreign_count": assessment.foreign_count,
        "audits": [
            {
                "decoded_position": audit.decoded_position,
                "disposition": audit.disposition,
                "instrument_id": audit.instrument_id,
                "target_candidate_ordinal": audit.target_candidate_ordinal,
                "item_sha256": audit.item_sha256,
                "prefix_sha256": audit.prefix_sha256,
            }
            for audit in assessment.audits
        ],
        "authority_flags": dict(assessment.authority_flags),
        "assessment_sha256": assessment.assessment_sha256,
    }


def _expect_cursor_protocol(expected_cursor_protocol_sha256):
    _require(
        cursor.protocol_sha256() == expected_cursor_protocol_sha256,
        "Original cursor protocol pin differs",
    )


def _bundle_preflight(
    bundle,
    expected_context_sha256,
    expected_cursor_protocol_sha256,
    expected_cursor_fixture_sha256,
):
    """Finish complete metadata without accessing any MboPayload field."""
    values = _read(bundle, PayloadBundle, ("context", "cursor_fixture", "payloads"))
    context_body = _context_body(values["context"])
    _require(_digest(context_body) == expected_context_sha256, "Constructed context pin differs")
    fixture = values["cursor_fixture"]
    fixture_pin = cursor.fixture_sha256(
        fixture, expected_protocol_sha256=expected_cursor_protocol_sha256
    )
    _require(fixture_pin == expected_cursor_fixture_sha256, "Complete cursor fixture pin differs")
    old_assessment = cursor.assess(
        fixture,
        expected_fixture_sha256=expected_cursor_fixture_sha256,
        expected_protocol_sha256=expected_cursor_protocol_sha256,
    )
    payloads = values["payloads"]
    _require(
        type(payloads) is tuple and len(payloads) == fixture.declared_item_count,
        "Complete exact payload tuple must match all decoded positions",
    )
    _require(payloads[0] is None, "Header payload must be literal None")
    for payload in payloads[1:]:
        _require(type(payload) is MboPayload, "Every target and foreign body has exact type")
    return context_body, _cursor_fixture_body(fixture), old_assessment


def _bundle_body(bundle, context_body, fixture_body):
    payload_bodies = [None]
    for payload, item in zip(bundle.payloads[1:], fixture_body["items"][1:], strict=True):
        body = _payload_body(payload, context_body)
        _require(body["instrument_id"] == item["instrument_id"], "Payload instrument differs")
        _require(_digest(body) == item["payload_sha256"], "Recomputed complete payload pin differs")
        payload_bodies.append(body)
    return {
        "context": context_body,
        "cursor_fixture": fixture_body,
        "payloads": payload_bodies,
    }


def _bound_prefix(protocol_pin, context_pin, cursor_prefix):
    return _digest(
        {
            "binding_protocol_sha256": protocol_pin,
            "context_sha256": context_pin,
            "cursor_prefix_sha256": cursor_prefix,
        }
    )


def _construct_audits(old_assessment, protocol_pin, context_pin):
    return tuple(
        PayloadAudit(
            old_audit.decoded_position,
            old_audit.disposition,
            old_audit.instrument_id,
            old_audit.target_candidate_ordinal,
            item.payload_sha256,
            old_audit.item_sha256,
            old_audit.prefix_sha256,
            _bound_prefix(protocol_pin, context_pin, old_audit.prefix_sha256),
        )
        for old_audit, item in zip(old_assessment.audits, old_assessment.fixture.items, strict=True)
    )


def _audit_body(audit):
    return {
        "decoded_position": audit.decoded_position,
        "disposition": audit.disposition,
        "instrument_id": audit.instrument_id,
        "target_candidate_ordinal": audit.target_candidate_ordinal,
        "payload_sha256": audit.payload_sha256,
        "cursor_item_sha256": audit.cursor_item_sha256,
        "cursor_prefix_sha256": audit.cursor_prefix_sha256,
        "bound_prefix_sha256": audit.bound_prefix_sha256,
    }


def _assessment_body(assessment, bundle_body):
    return {
        "status": assessment.status,
        "protocol_sha256": assessment.protocol_sha256,
        "context_sha256": assessment.context_sha256,
        "cursor_protocol_sha256": assessment.cursor_protocol_sha256,
        "cursor_fixture_sha256": assessment.cursor_fixture_sha256,
        "bundle_sha256": assessment.bundle_sha256,
        "bundle": bundle_body,
        "cursor_assessment": _cursor_assessment_body(assessment.cursor_assessment),
        "audits": [_audit_body(audit) for audit in assessment.audits],
        "authority_flags": dict(assessment.authority_flags),
    }


def _construct_assessment(
    bundle,
    bundle_body,
    old_assessment,
    protocol_pin,
    context_pin,
    cursor_protocol_pin,
    cursor_fixture_pin,
    bundle_pin,
):
    audits = _construct_audits(old_assessment, protocol_pin, context_pin)
    result = BindingAssessment(
        "constructed_record_payload_binding_not_native_verification",
        protocol_pin,
        context_pin,
        cursor_protocol_pin,
        cursor_fixture_pin,
        bundle_pin,
        bundle,
        old_assessment,
        audits,
        _flags(),
        "0" * 64,
    )
    result_pin = hashlib.sha256(
        _bounded_canonical(_assessment_body(result, bundle_body))
    ).hexdigest()
    return BindingAssessment(
        result.status,
        result.protocol_sha256,
        result.context_sha256,
        result.cursor_protocol_sha256,
        result.cursor_fixture_sha256,
        result.bundle_sha256,
        result.bundle,
        result.cursor_assessment,
        result.audits,
        result.authority_flags,
        result_pin,
    )


def _flags_body(value):
    expected = _flags()
    _require(type(value) is tuple and len(value) == len(expected), "Complete false flags required")
    for supplied, original in zip(value, expected, strict=True):
        _require(type(supplied) is tuple and len(supplied) == 2, "Exact authority pair required")
        _require(
            type(supplied[0]) is str and supplied[0] == original[0] and supplied[1] is False,
            "Every named authority must stay literal False in exact order",
        )
    return dict(value)


def _audit_preflight(audit, expected, position):
    body = _read(
        audit,
        PayloadAudit,
        (
            "decoded_position",
            "disposition",
            "instrument_id",
            "target_candidate_ordinal",
            "payload_sha256",
            "cursor_item_sha256",
            "cursor_prefix_sha256",
            "bound_prefix_sha256",
        ),
    )
    _integer(body["decoded_position"], 1, 128)
    _require(body["decoded_position"] == position, "Complete audit positions must match order")
    _require(
        type(body["disposition"]) is str
        and body["disposition"] in ("header", "foreign", "target_candidate"),
        "Exact constructed disposition required",
    )
    if position == 1:
        _require(
            body["disposition"] == "header"
            and body["instrument_id"] is None
            and body["target_candidate_ordinal"] is None
            and body["payload_sha256"] is None,
            "Header audit must retain literal None declarations",
        )
    else:
        _require(body["disposition"] != "header", "Only position one is header")
        _integer(body["instrument_id"], 0, 4_294_967_295)
        _pins(body["payload_sha256"])
        if body["disposition"] == "foreign":
            _require(body["target_candidate_ordinal"] is None, "Foreign ordinal is literal None")
        else:
            _integer(body["target_candidate_ordinal"], 1, 127)
    _pins(body["cursor_item_sha256"], body["cursor_prefix_sha256"], body["bound_prefix_sha256"])
    _require(body == _audit_body(expected), "Submitted audit metadata differs from reconstruction")


def _submitted_preflight(
    assessment,
    original_bundle,
    old_assessment,
    protocol_pin,
    context_pin,
    cursor_protocol_pin,
    cursor_fixture_pin,
    bundle_pin,
    assessment_pin,
):
    """Validate ALL submitted metadata before either original/submitted body."""
    values = _read(
        assessment,
        BindingAssessment,
        (
            "status",
            "protocol_sha256",
            "context_sha256",
            "cursor_protocol_sha256",
            "cursor_fixture_sha256",
            "bundle_sha256",
            "bundle",
            "cursor_assessment",
            "audits",
            "authority_flags",
            "assessment_sha256",
        ),
    )
    _require(
        type(values["status"]) is str
        and values["status"] == "constructed_record_payload_binding_not_native_verification",
        "Exact constructed-only result status required",
    )
    _pins(
        values["protocol_sha256"],
        values["context_sha256"],
        values["cursor_protocol_sha256"],
        values["cursor_fixture_sha256"],
        values["bundle_sha256"],
        values["assessment_sha256"],
    )
    _require(
        values["protocol_sha256"] == protocol_pin
        and values["context_sha256"] == context_pin
        and values["cursor_protocol_sha256"] == cursor_protocol_pin
        and values["cursor_fixture_sha256"] == cursor_fixture_pin
        and values["bundle_sha256"] == bundle_pin
        and values["assessment_sha256"] == assessment_pin,
        "Retained caller expectations differ",
    )
    submitted_context, submitted_fixture, _ = _bundle_preflight(
        values["bundle"], context_pin, cursor_protocol_pin, cursor_fixture_pin
    )
    # Public old verification validates its entire body, audits, counts and 26
    # literal false flags, while neither new payload tuple has been traversed.
    cursor.verify(
        values["cursor_assessment"],
        original_bundle.cursor_fixture,
        expected_fixture_sha256=cursor_fixture_pin,
        expected_protocol_sha256=cursor_protocol_pin,
        expected_assessment_sha256=old_assessment.assessment_sha256,
    )
    expected_audits = _construct_audits(old_assessment, protocol_pin, context_pin)
    audits = values["audits"]
    _require(
        type(audits) is tuple and len(audits) == old_assessment.decoded_item_count,
        "Complete submitted audit tuple required",
    )
    for position, (audit, expected) in enumerate(zip(audits, expected_audits, strict=True), 1):
        _audit_preflight(audit, expected, position)
    _flags_body(values["authority_flags"])
    return values["bundle"], submitted_context, submitted_fixture


@_guard
def protocol() -> dict:
    """Return the complete fresh literal constructed binding protocol."""
    return _protocol_body()


@_guard
def protocol_sha256() -> str:
    """Pin the complete protocol without caller-object traversal."""
    return _digest(_protocol_body())


@_guard
def context_sha256(context: PayloadContext, *, expected_protocol_sha256: str) -> str:
    """Validate the entire explicit constructed context and pin its body."""
    _pins(expected_protocol_sha256)
    _expect_protocol(expected_protocol_sha256)
    return _digest(_context_body(context))


@_guard
def payload_sha256(
    payload: MboPayload,
    context: PayloadContext,
    *,
    expected_protocol_sha256: str,
    expected_context_sha256: str,
) -> str:
    """Pin all sixteen exact raw fields, without cursor or native claims."""
    _pins(expected_protocol_sha256, expected_context_sha256)
    _expect_protocol(expected_protocol_sha256)
    context_body = _context_body(context)
    _require(_digest(context_body) == expected_context_sha256, "Constructed context pin differs")
    return _digest(_payload_body(payload, context_body))


@_guard
def bundle_sha256(
    bundle: PayloadBundle,
    *,
    expected_protocol_sha256: str,
    expected_context_sha256: str,
    expected_cursor_protocol_sha256: str,
    expected_cursor_fixture_sha256: str,
) -> str:
    """Preflight all metadata, reconstruct both old caps, then bind every body."""
    _pins(
        expected_protocol_sha256,
        expected_context_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
    )
    _expect_protocol(expected_protocol_sha256)
    _expect_cursor_protocol(expected_cursor_protocol_sha256)
    context_body, fixture_body, _ = _bundle_preflight(
        bundle,
        expected_context_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
    )
    body = _bundle_body(bundle, context_body, fixture_body)
    return hashlib.sha256(_bounded_canonical(body)).hexdigest()


@_guard
def assess(
    bundle: PayloadBundle,
    *,
    expected_protocol_sha256: str,
    expected_context_sha256: str,
    expected_cursor_protocol_sha256: str,
    expected_cursor_fixture_sha256: str,
    expected_bundle_sha256: str,
) -> BindingAssessment:
    """Retain complete constructed-body consistency and contextual old prefixes."""
    _pins(
        expected_protocol_sha256,
        expected_context_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
        expected_bundle_sha256,
    )
    _expect_protocol(expected_protocol_sha256)
    _expect_cursor_protocol(expected_cursor_protocol_sha256)
    context_body, fixture_body, old_assessment = _bundle_preflight(
        bundle,
        expected_context_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
    )
    body = _bundle_body(bundle, context_body, fixture_body)
    bundle_pin = hashlib.sha256(_bounded_canonical(body)).hexdigest()
    _require(bundle_pin == expected_bundle_sha256, "Complete bundle pin differs")
    return _construct_assessment(
        bundle,
        body,
        old_assessment,
        expected_protocol_sha256,
        expected_context_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
        bundle_pin,
    )


@_guard
def verify(
    assessment: BindingAssessment,
    bundle: PayloadBundle,
    *,
    expected_protocol_sha256: str,
    expected_context_sha256: str,
    expected_cursor_protocol_sha256: str,
    expected_cursor_fixture_sha256: str,
    expected_bundle_sha256: str,
    expected_assessment_sha256: str,
) -> None:
    """Rebuild complete original and submitted bodies, never adopt summaries."""
    _pins(
        expected_protocol_sha256,
        expected_context_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
        expected_bundle_sha256,
        expected_assessment_sha256,
    )
    _expect_protocol(expected_protocol_sha256)
    _expect_cursor_protocol(expected_cursor_protocol_sha256)
    context_body, fixture_body, old_assessment = _bundle_preflight(
        bundle,
        expected_context_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
    )
    submitted_bundle, submitted_context, submitted_fixture = _submitted_preflight(
        assessment,
        bundle,
        old_assessment,
        expected_protocol_sha256,
        expected_context_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
        expected_bundle_sha256,
        expected_assessment_sha256,
    )
    # Both complete metadata traversals finish above. All sixteen raw fields in
    # every original and submitted target/foreign occurrence remain deferred.
    original_body = _bundle_body(bundle, context_body, fixture_body)
    submitted_body = _bundle_body(submitted_bundle, submitted_context, submitted_fixture)
    bundle_raw = _bounded_canonical(original_body)
    _require(
        hashlib.sha256(bundle_raw).hexdigest() == expected_bundle_sha256,
        "Original complete bundle pin differs",
    )
    _require(_bounded_canonical(submitted_body) == bundle_raw, "Submitted complete bundle differs")
    rebuilt = _construct_assessment(
        bundle,
        original_body,
        old_assessment,
        expected_protocol_sha256,
        expected_context_sha256,
        expected_cursor_protocol_sha256,
        expected_cursor_fixture_sha256,
        expected_bundle_sha256,
    )
    _require(
        rebuilt.assessment_sha256 == expected_assessment_sha256,
        "Rebuilt original complete result pin differs",
    )
    supplied_raw = _bounded_canonical(_assessment_body(assessment, submitted_body))
    rebuilt_raw = _bounded_canonical(_assessment_body(rebuilt, original_body))
    _require(
        supplied_raw == rebuilt_raw
        and hashlib.sha256(supplied_raw).hexdigest() == expected_assessment_sha256
        and assessment.assessment_sha256 == expected_assessment_sha256,
        "Submitted complete result differs from full original reconstruction",
    )
    return None
