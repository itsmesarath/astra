"""Bind complete invented native members to constructed publication evidence.

Replay and verification compose unchanged public providers. Complete consistency
does not grant source authentication, historical access or trading authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date
from functools import wraps
from pathlib import Path

from ai_trader.research import six_e_native_cursor_metadata as cursor
from ai_trader.research import six_e_native_member_decode_evidence as native
from ai_trader.research import six_e_record_payload_binding as binding
from ai_trader.research import six_e_typed_native_event_adapter as adapter

__all__ = [
    "BridgeContext",
    "NativePrefixLink",
    "PublicationLink",
    "BridgeEvidence",
    "protocol",
    "protocol_sha256",
    "context_sha256",
    "replay",
    "verify",
]

_PROTOCOL_SHA = "924c4c37e66e561ece476cb57d927ecb64e01588050df3edb9aa17d5ebd13862"
_PROTOCOL_RAW_SHA = "1c14ab24b624a7e2e5429a2a9379eeb6def9d0f484cdda04c9964b0e8f3ee6ed"
_STATUS = "complete_invented_member_publication_consistency_not_source_authentication"
_NATIVE_PIN = "baef653d21535c864a889e1299332b1b182421cbd154cd3247d81705f10133e1"
_CURSOR_PIN = "1923a5d70b9bfd90a08329f882da35850b3ce522d5e22ee9d8d1442043c0d5c1"
_BINDING_PIN = "8781ece9e9bc6c299dfa8127da77a1a9668aa9b61b4912d062c911ef5fe97564"
_ADAPTER_PIN = "d4236573e06080830247ebfcc843c42b39333a5f2b3a9cdbfb1f344483eb7cef"
_PROFILE_PIN = "5016b1dc56537fdefdac74e56154ceb410307f3677fb08d8455cba8f54c86b0d"
_RUNTIME_PIN = "4aab559ab26a25cf35579dc723cb00d06db933ea65c63d9793a34939191c2ec3"
_DAY_START = 1743984000000000000
_DAY_END = 1744070400000000000


@dataclass(frozen=True, slots=True)
class BridgeContext:
    fixture_id: str
    source_session: str
    native_context: native.MemberDecodeContext


@dataclass(frozen=True, slots=True)
class NativePrefixLink:
    decoded_position: int
    kind: str
    wire_span_ordinal: int
    decompressed_start: int
    decompressed_end: int
    wire_sha256: str
    wire_fields_sha256: str
    projection_sha256: str
    previous_prefix_sha256: str
    prefix_sha256: str


@dataclass(frozen=True, slots=True)
class PublicationLink:
    publication_ordinal: int
    quote_ordinal: int
    event_ordinal: int
    decoded_position: int
    ts_recv_ns: int
    adapter_prefix_sha256: str
    publication_sha256: str
    native_prefix_sha256: str
    link_sha256: str


@dataclass(frozen=True, slots=True)
class BridgeEvidence:
    status: str
    protocol_sha256: str
    context_sha256: str
    context: BridgeContext
    native_evidence: native.MemberDecodeEvidence
    adapter_assessment: adapter.AdapterAssessment
    native_prefixes: tuple[NativePrefixLink, ...]
    publication_links: tuple[PublicationLink, ...]
    authorities: tuple[tuple[str, bool], ...]
    evidence_sha256: str


def _guard(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, TypeError, AttributeError, OverflowError) as exc:
            raise ValueError("Malformed complete invented member-publication bridge") from exc

    return checked


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _pins(*values):
    for value in values:
        _require(
            type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
            "Exact lowercase SHA256 expectation required",
        )


def _canonical(body, maximum):
    raw = json.dumps(
        body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    _require(len(raw) <= maximum, "Complete canonical byte limit exceeded")
    return raw


def _digest(body, maximum=65536):
    return hashlib.sha256(_canonical(body, maximum)).hexdigest()


def _literal_equal(actual, expected):
    """Traverse only the fixed, bounded protocol schema, not caller-selected JSON."""
    _require(type(actual) is type(expected), "Exact dependency protocol type required")
    if type(expected) is dict:
        _require(len(actual) == len(expected), "Complete dependency protocol length differs")
        _require(
            all(type(key) is str for key in actual) and actual.keys() == expected.keys(),
            "Complete dependency protocol keys differ",
        )
        for key in expected:
            _literal_equal(actual[key], expected[key])
    elif type(expected) is list:
        _require(len(actual) == len(expected), "Complete dependency protocol length differs")
        for item, reference in zip(actual, expected, strict=True):
            _literal_equal(item, reference)
    else:
        _require(actual == expected, "Complete dependency protocol value differs")


def _protocol_body():
    resource = Path(__file__).with_name("_source_publication_bridge_protocol_v1.json")
    with resource.open("rb") as stream:
        raw = stream.read(262145)
    if len(raw) > 262144 or hashlib.sha256(raw).hexdigest() != _PROTOCOL_RAW_SHA:
        raise RuntimeError("Registered literal bridge protocol resource differs")
    body = json.loads(raw)
    if type(body) is not dict or _digest(body, 262144) != _PROTOCOL_SHA:
        raise RuntimeError("Complete literal bridge protocol identity differs")
    return body


def _expected_protocols(expected_protocol_sha256):
    _require(expected_protocol_sha256 == _PROTOCOL_SHA, "Bridge protocol expectation differs")
    body = _protocol_body()
    for name, module in (
        ("native", native),
        ("adapter", adapter),
        ("binding", binding),
        ("cursor", cursor),
    ):
        _literal_equal(module.protocol(), body["dependencies"][name])
    return body


def _context_body(context):
    _require(type(context) is BridgeContext, "Exact BridgeContext required")
    for label in (context.fixture_id, context.source_session):
        _require(
            type(label) is str
            and len(label) <= 64
            and re.fullmatch(r"synthetic-[A-Za-z0-9._:-]+", label) is not None,
            "Complete prospective synthetic label required",
        )
    value = context.native_context
    _require(type(value) is native.MemberDecodeContext, "Exact native context required")
    for actual, expected in (
        (value.profile_id, "dbn_v3_asis_zstd_cext_invented_20261012_v1"),
        (value.member_compression, "ZSTD_CONCAT"),
        (value.upgrade_policy, "AS_IS"),
    ):
        _require(type(actual) is str and actual == expected, "Fixed native context differs")
    _require(type(value.input_version) is int and value.input_version == 3, "Exact input3 required")
    _require(type(value.expected_ts_out) is bool, "Exact native ts_out mode required")
    return {
        "fixture_id": context.fixture_id,
        "source_session": context.source_session,
        "native_context": {
            "profile_id": value.profile_id,
            "member_compression": value.member_compression,
            "input_version": value.input_version,
            "upgrade_policy": value.upgrade_policy,
            "expected_ts_out": value.expected_ts_out,
        },
    }


def _preflight(member_bytes, context, protocol_pin, context_pin, member_pin):
    body = _expected_protocols(protocol_pin)
    context_body = _context_body(context)
    _require(_digest(context_body) == context_pin, "Complete bridge context expectation differs")
    _require(
        type(member_bytes) is bytes and 1 <= len(member_bytes) <= 262144,
        "Complete immutable member byte type/limit required",
    )
    _require(
        hashlib.sha256(member_bytes).hexdigest() == member_pin,
        "Complete member byte expectation differs",
    )
    return body, context_body


def _integer(value, minimum, maximum):
    _require(type(value) is int and minimum <= value <= maximum, "Exact bounded integer required")


def _links_preflight(prefixes, publications):
    _require(
        type(prefixes) is tuple and 2 <= len(prefixes) <= 128, "Complete native links required"
    )
    previous_end = 0
    for position, link in enumerate(prefixes, 1):
        _require(type(link) is NativePrefixLink, "Exact NativePrefixLink required")
        _integer(link.decoded_position, position, position)
        _integer(link.wire_span_ordinal, position, position)
        expected_kind = "Metadata" if position == 1 else "MBO"
        _require(type(link.kind) is str and link.kind == expected_kind, "Native link kind differs")
        _integer(link.decompressed_start, previous_end, previous_end)
        _integer(link.decompressed_end, previous_end + 1, 1048576)
        previous_end = link.decompressed_end
        _pins(
            link.wire_sha256,
            link.wire_fields_sha256,
            link.projection_sha256,
            link.previous_prefix_sha256,
            link.prefix_sha256,
        )
    _require(
        type(publications) is tuple and 1 <= len(publications) <= 32,
        "Complete publication links required",
    )
    for ordinal, link in enumerate(publications, 1):
        _require(type(link) is PublicationLink, "Exact PublicationLink required")
        _integer(link.publication_ordinal, ordinal, ordinal)
        _integer(link.quote_ordinal, 1, 127)
        _integer(link.event_ordinal, 1, 127)
        _integer(link.decoded_position, 2, len(prefixes))
        _integer(link.ts_recv_ns, 1744027200000000000, 1744041599999999999)
        _pins(
            link.adapter_prefix_sha256,
            link.publication_sha256,
            link.native_prefix_sha256,
            link.link_sha256,
        )


def _submitted_preflight(evidence, context_body, protocol_body, protocol_pin, context_pin, own_pin):
    _require(type(evidence) is BridgeEvidence, "Exact BridgeEvidence required")
    _require(type(evidence.status) is str and evidence.status == _STATUS, "Bridge status differs")
    _pins(evidence.protocol_sha256, evidence.context_sha256, evidence.evidence_sha256)
    _require(evidence.protocol_sha256 == protocol_pin, "Submitted protocol differs")
    _require(evidence.context_sha256 == context_pin, "Submitted context pin differs")
    _require(evidence.evidence_sha256 == own_pin, "Submitted complete evidence pin differs")
    _require(
        _canonical(_context_body(evidence.context), 65536) == _canonical(context_body, 65536),
        "Submitted complete context differs",
    )
    _require(type(evidence.native_evidence) is native.MemberDecodeEvidence, "Exact native envelope")
    _require(
        type(evidence.adapter_assessment) is adapter.AdapterAssessment, "Exact adapter envelope"
    )
    _pins(evidence.native_evidence.evidence_sha256, evidence.adapter_assessment.assessment_sha256)
    names = protocol_body["authority_names"]
    _require(
        type(evidence.authorities) is tuple and len(evidence.authorities) == len(names),
        "Complete bridge authority tuple required",
    )
    for pair, name in zip(evidence.authorities, names, strict=True):
        _require(
            type(pair) is tuple
            and len(pair) == 2
            and type(pair[0]) is str
            and pair[0] == name
            and pair[1] is False,
            "Literal ordered false bridge authority required",
        )
    _links_preflight(evidence.native_prefixes, evidence.publication_links)


# This is a closed literal projection grammar, not dataclass reflection or a
# caller-selected JSON schema. Every container is checked before descending;
# scalar slots never recurse into a tuple/list/record supplied in their place.
_OPT_INT = ("optional", int)
_OPT_STR = ("optional", str)
_POSITIONS = ("sequence", 0, 127, int)
_COUNTERS = ("pairs", 0, 160, int)
_ENUM_FIELDS = (("kind", str), ("class_name", str), ("name", str), ("code", int), ("text", str))
_RECORD_SCHEMAS = {
    native.SchemaMbo: _ENUM_FIELDS,
    native.RtypeMbo: _ENUM_FIELDS,
    native.SType: _ENUM_FIELDS,
    native.Action: _ENUM_FIELDS,
    native.Side: _ENUM_FIELDS,
    native.UnknownChar: (("kind", str), ("value", str)),
    native.PythonDate: (("kind", str), ("year", int), ("month", int), ("day", int)),
    native.WireMappingInterval: (("start_date", int), ("end_date", int), ("symbol", str)),
    native.MappingInterval: (
        ("start_date", native.PythonDate),
        ("end_date", native.PythonDate),
        ("symbol", str),
    ),
    native.MappingGroup: (
        ("raw_symbol", str),
        ("intervals", ("sequence", 0, 16, native.MappingInterval)),
    ),
    native.WireMappingGroup: (
        ("raw_symbol", str),
        ("interval_count", int),
        ("intervals", ("sequence", 0, 16, native.WireMappingInterval)),
    ),
    native.MetadataWireBody: (
        ("magic_hex", str),
        ("version", int),
        ("length_body", int),
        ("dataset", str),
        ("dataset_cstr_bytes", int),
        ("schema", int),
        ("start", int),
        ("end", int),
        ("limit", int),
        ("stype_in", int),
        ("stype_out", int),
        ("ts_out", int),
        ("symbol_cstr_len", int),
        ("reserved_bytes", ("sequence", 53, 53, int)),
        ("schema_definition_length", int),
        ("symbols_count", int),
        ("symbols", ("sequence", 1, 1, str)),
        ("partial_count", int),
        ("partial", ("sequence", 0, 0, str)),
        ("not_found_count", int),
        ("not_found", ("sequence", 0, 0, str)),
        ("mappings_count", int),
        ("mappings", ("sequence", 1, 8, native.WireMappingGroup)),
        ("alignment_padding_bytes", ("sequence", 0, 7, int)),
    ),
    native.MetadataProjection: (
        ("version", int),
        ("dataset", str),
        ("schema", native.SchemaMbo),
        ("start", int),
        ("end_observed", _OPT_INT),
        ("limit_observed", _OPT_INT),
        ("stype_in", ("optional", native.SType)),
        ("stype_out", native.SType),
        ("ts_out", bool),
        ("symbol_cstr_len", int),
        ("symbols", ("sequence", 1, 1, str)),
        ("partial", ("sequence", 0, 0, str)),
        ("not_found", ("sequence", 0, 0, str)),
        ("mappings", ("sequence", 1, 8, native.MappingGroup)),
    ),
    native.MboWireBody: (
        ("length_words", int),
        ("rtype", int),
        ("publisher_id", int),
        ("instrument_id", int),
        ("ts_event", int),
        ("order_id", int),
        ("price", int),
        ("size", int),
        ("flags", int),
        ("channel_id", int),
        ("action", int),
        ("side", int),
        ("ts_recv", int),
        ("ts_in_delta", int),
        ("sequence", int),
        ("ts_out", _OPT_INT),
    ),
    native.MboObservation: (
        ("rtype", native.RtypeMbo),
        ("publisher_id", int),
        ("instrument_id", int),
        ("ts_event", int),
        ("order_id", int),
        ("price", int),
        ("size", int),
        ("action", ("union", native.Action, native.UnknownChar)),
        ("side", ("union", native.Side, native.UnknownChar)),
        ("ts_recv", int),
        ("flags", int),
        ("channel_id", int),
        ("ts_in_delta", int),
        ("sequence", int),
        ("ts_out_observed", int),
        ("record_size_observed", int),
        ("ts_index_observed", int),
    ),
    native.MemberDecodeContext: (
        ("profile_id", str),
        ("member_compression", str),
        ("input_version", int),
        ("upgrade_policy", str),
        ("expected_ts_out", bool),
    ),
    native.DecodedOccurrence: (
        ("decoded_position", int),
        ("kind", str),
        ("wire_span_ordinal", int),
        ("projection", ("union", native.MetadataProjection, native.MboObservation)),
        ("projection_sha256", str),
    ),
    native.FrameSpan: (
        ("frame_ordinal", int),
        ("compressed_start", int),
        ("compressed_end", int),
        ("decompressed_start", int),
        ("decompressed_end", int),
        ("compressed_span_sha256", str),
        ("decompressed_span_sha256", str),
    ),
    native.ZstdFramingReport: (
        ("compressed_bytes", int),
        ("compressed_sha256", str),
        ("decompressed_bytes", int),
        ("decompressed_sha256", str),
        ("frames", ("sequence", 1, 16, native.FrameSpan)),
        ("report_sha256", str),
    ),
    native.WireSpan: (
        ("wire_span_ordinal", int),
        ("kind", str),
        ("decompressed_start", int),
        ("decompressed_end", int),
        ("wire_sha256", str),
        ("wire_fields", ("union", native.MetadataWireBody, native.MboWireBody)),
        ("wire_fields_sha256", str),
    ),
    native.DbnFramingReport: (
        ("decompressed_bytes", int),
        ("decompressed_sha256", str),
        ("spans", ("sequence", 2, 128, native.WireSpan)),
        ("report_sha256", str),
    ),
    native.TerminalEvidence: (
        ("compressed_bytes", int),
        ("compressed_sha256", str),
        ("decompressed_bytes", int),
        ("decompressed_sha256", str),
        ("frame_count", int),
        ("decoded_positions", int),
        ("metadata_count", int),
        ("mbo_count", int),
        ("dbn_remaining_buffer_bytes", int),
        ("zstd_framing_sha256", str),
        ("dbn_framing_sha256", str),
        ("framing_status", str),
        ("zstd_status", str),
    ),
    native.Interpreter: (
        ("implementation", str),
        ("version", ("sequence", 3, 3, int)),
        ("executable_sha256", str),
    ),
    native.Package: (("name", str), ("version", str), ("metadata_sha256", str)),
    native.Artifact: (("logical_id", str), ("kind", str), ("raw_bytes", int), ("raw_sha256", str)),
    native.RuntimeManifest: (
        ("schema", str),
        ("interpreter", native.Interpreter),
        ("packages", ("sequence", 2, 2, native.Package)),
        ("artifacts", ("sequence", 13, 13, native.Artifact)),
    ),
    native.MemberDecodeEvidence: (
        ("status", str),
        ("protocol_sha256", str),
        ("profile_sha256", str),
        ("runtime_manifest", native.RuntimeManifest),
        ("runtime_manifest_sha256", str),
        ("context_sha256", str),
        ("member_sha256", str),
        ("metadata_sha256", str),
        ("occurrences", ("sequence", 2, 128, native.DecodedOccurrence)),
        ("zstd_framing", native.ZstdFramingReport),
        ("dbn_framing", native.DbnFramingReport),
        ("terminal", native.TerminalEvidence),
        ("authorities", ("sequence", 28, 28, ("row", str, bool))),
        ("evidence_sha256", str),
    ),
    cursor.MappingInterval: (("start_date", str), ("end_date", str), ("instrument_symbol", str)),
    cursor.MappingGroup: (
        ("contract", str),
        ("intervals", ("sequence", 0, 16, cursor.MappingInterval)),
    ),
    cursor.DeclaredHeader: (
        ("dataset", str),
        ("schema", str),
        ("symbols", ("sequence", 1, 1, str)),
        ("not_found", ("sequence", 0, 0, str)),
        ("start_ns", int),
        ("end_ns", int),
        ("mappings", ("sequence", 1, 8, cursor.MappingGroup)),
    ),
    cursor.DecodedItem: (
        ("decoded_position", int),
        ("kind", str),
        ("instrument_id", _OPT_INT),
        ("payload_sha256", _OPT_STR),
    ),
    cursor.CursorFixture: (
        ("fixture_id", str),
        ("source_session", str),
        ("utc_date", str),
        ("contract", str),
        ("header", cursor.DeclaredHeader),
        ("asserted_member_sha256", str),
        ("declared_item_count", int),
        ("items", ("sequence", 2, 128, cursor.DecodedItem)),
    ),
    cursor.CursorAudit: (
        ("decoded_position", int),
        ("disposition", str),
        ("instrument_id", _OPT_INT),
        ("target_candidate_ordinal", _OPT_INT),
        ("item_sha256", str),
        ("prefix_sha256", str),
    ),
    cursor.CursorAssessment: (
        ("status", str),
        ("protocol_sha256", str),
        ("fixture_sha256", str),
        ("fixture", cursor.CursorFixture),
        ("mapped_instrument_id", int),
        ("decoded_item_count", int),
        ("target_candidate_count", int),
        ("foreign_count", int),
        ("audits", ("sequence", 2, 128, cursor.CursorAudit)),
        ("authority_flags", ("pairs", 26, 26, bool)),
        ("assessment_sha256", str),
    ),
    binding.PayloadContext: (("codec_id", str), ("schema_version", int), ("ts_out_mode", str)),
    binding.MboPayload: (
        ("publisher_id", int),
        ("instrument_id", int),
        ("ts_event", int),
        ("order_id", int),
        ("price", int),
        ("size", int),
        ("action", str),
        ("side", str),
        ("ts_recv", int),
        ("flags", int),
        ("channel_id", int),
        ("ts_in_delta", int),
        ("sequence", int),
        ("ts_out", _OPT_INT),
        ("rtype", int),
        ("record_size", int),
    ),
    binding.PayloadBundle: (
        ("context", binding.PayloadContext),
        ("cursor_fixture", cursor.CursorFixture),
        ("payloads", ("sequence", 2, 128, ("optional", binding.MboPayload))),
    ),
    binding.PayloadAudit: (
        ("decoded_position", int),
        ("disposition", str),
        ("instrument_id", _OPT_INT),
        ("target_candidate_ordinal", _OPT_INT),
        ("payload_sha256", _OPT_STR),
        ("cursor_item_sha256", str),
        ("cursor_prefix_sha256", str),
        ("bound_prefix_sha256", str),
    ),
    binding.BindingAssessment: (
        ("status", str),
        ("protocol_sha256", str),
        ("context_sha256", str),
        ("cursor_protocol_sha256", str),
        ("cursor_fixture_sha256", str),
        ("bundle_sha256", str),
        ("bundle", binding.PayloadBundle),
        ("cursor_assessment", cursor.CursorAssessment),
        ("audits", ("sequence", 2, 128, binding.PayloadAudit)),
        ("authority_flags", ("pairs", 31, 31, bool)),
        ("assessment_sha256", str),
    ),
    adapter.AdapterContext: (
        ("input_version", int),
        ("upgrade_policy", str),
        ("yielded_version", int),
        ("stype_in", str),
        ("stype_out", str),
        ("partial", ("sequence", 0, 0, str)),
        ("limit", _OPT_INT),
        ("ts_out", bool),
    ),
    adapter.AdapterFixture: (
        ("context", adapter.AdapterContext),
        ("payload_bundle", binding.PayloadBundle),
    ),
    adapter.OrderState: (("side", str), ("price", int), ("size", int)),
    adapter.OrderEntry: (("order_id", int), ("state", adapter.OrderState)),
    adapter.PriceLevel: (("price", int), ("size", int)),
    adapter.AdapterAudit: (
        ("decoded_position", int),
        ("disposition", str),
        ("instrument_id", _OPT_INT),
        ("target_candidate_ordinal", _OPT_INT),
        ("target_transition_ordinal", _OPT_INT),
        ("binding_prefix_sha256", str),
        ("adapter_prefix_sha256", str),
    ),
    adapter.TargetTransition: (
        ("decoded_position", int),
        ("target_transition_ordinal", int),
        ("disposition", str),
        ("snapshot", bool),
        ("exceptional_closed_clear", bool),
        ("order_id", int),
        ("before", ("optional", adapter.OrderState)),
        ("after", ("optional", adapter.OrderState)),
        ("initialized_before", bool),
        ("initialized_after", bool),
        ("last_recv_before", _OPT_INT),
        ("last_recv_after", _OPT_INT),
        ("event_ordinal", _OPT_INT),
        ("quote_ordinal", _OPT_INT),
        ("publication_ordinal", _OPT_INT),
        ("state_sha256", str),
    ),
    adapter.EventWitness: (
        ("event_ordinal", int),
        ("closing_decoded_position", int),
        ("closing_target_transition_ordinal", int),
        ("ts_recv_ns", int),
        ("target_positions", _POSITIONS),
        ("trade_positions", _POSITIONS),
        ("execution_capture_positions", _POSITIONS),
        ("quote_ordinal", _OPT_INT),
        ("adapter_prefix_sha256", str),
        ("event_sha256", str),
    ),
    adapter.QuoteWitness: (
        ("quote_ordinal", int),
        ("event_ordinal", int),
        ("decoded_position", int),
        ("ts_recv_ns", int),
        ("bid", int),
        ("ask", int),
        ("bid_qty", int),
        ("ask_qty", int),
        ("prior_quote_gap_ns", int),
        ("ofi_generation", int),
        ("bid_depth5", ("sequence", 0, 5, adapter.PriceLevel)),
        ("ask_depth5", ("sequence", 0, 5, adapter.PriceLevel)),
        ("adapter_prefix_sha256", str),
        ("quote_sha256", str),
    ),
    adapter.InactivityInterval: (
        ("start_ns", int),
        ("timer_fired_ns", int),
        ("end_ns", int),
        ("recovered", bool),
        ("trigger_decoded_position", _OPT_INT),
    ),
    adapter.FeaturePublication: (
        ("publication_ordinal", int),
        ("quote_ordinal", int),
        ("event_ordinal", int),
        ("decoded_position", int),
        ("ts_recv_ns", int),
        ("adapter_prefix_sha256", str),
        ("features", ("sequence", 37, 37, ("row", str, "number"))),
        ("publication_sha256", str),
    ),
    adapter.ClockSample: (
        ("decoded_position", int),
        ("ts_recv", int),
        ("ts_event", int),
        ("ts_in_delta", int),
        ("flags", int),
        ("sequence", int),
        ("action", str),
        ("protected", bool),
        ("event_ahead_ns", int),
        ("sending_ns", int),
    ),
    adapter.ClockQuality: (
        ("target_records", int),
        ("snapshot_records", int),
        ("non_snapshot_records", int),
        ("event_after_receive", int),
        ("negative_send_delta", int),
        ("event_after_sending", int),
        ("clamped_delta", int),
        ("clock_disagreement_records", int),
        ("protected_disagreement_records", int),
        ("outside_disagreement_records", int),
        ("min_event_ahead_ns", _OPT_INT),
        ("max_event_ahead_ns", _OPT_INT),
        ("min_negative_delta_ns", _OPT_INT),
        ("samples", ("sequence", 0, 8, adapter.ClockSample)),
    ),
    adapter.ReconstructedState: (
        ("initialized", bool),
        ("orders", ("sequence", 0, 127, adapter.OrderEntry)),
        ("bid_levels", ("sequence", 0, 127, adapter.PriceLevel)),
        ("ask_levels", ("sequence", 0, 127, adapter.PriceLevel)),
        ("last_recv_ns", _OPT_INT),
        ("pending_target_positions", _POSITIONS),
        ("pending_trade_positions", _POSITIONS),
        ("execution_capture_positions", _POSITIONS),
        ("last_quote_ordinal", _OPT_INT),
        ("flow_events", ("sequence", 0, 127, ("row", int, int, int, int))),
        ("cvd", int),
        ("known_trades", int),
        ("unknown_trades", int),
        ("ofi_generation", int),
        ("ofi_previous_quote_ordinal", _OPT_INT),
        ("ofi_first_ts_ns", _OPT_INT),
        ("ofi_events", ("sequence", 0, 127, ("row", int, int))),
        ("ofi_total", int),
        ("history_ofi_generation", _OPT_INT),
        ("history_quote_ordinals", _POSITIONS),
        ("bid_depletions", ("sequence", 0, 127, ("row", int, int))),
        ("ask_depletions", ("sequence", 0, 127, ("row", int, int))),
        ("history_reloads", ("sequence", 0, 127, ("row", int, int, int))),
        ("execution_last_ts_ns", _OPT_INT),
        ("execution_events", ("sequence", 0, 127, ("row", int, _COUNTERS))),
        ("execution_totals", _COUNTERS),
        ("bid_credits", ("sequence", 0, 127, ("row", int, int, int))),
        ("ask_credits", ("sequence", 0, 127, ("row", int, int, int))),
        ("execution_audit", _COUNTERS),
        ("next_publication_ns", int),
        ("watch_since_ns", int),
        ("inactivity_start_ns", _OPT_INT),
        ("window_closed", bool),
    ),
    adapter.AdapterAssessment: (
        ("status", str),
        ("protocol_sha256", str),
        ("context_sha256", str),
        ("binding_protocol_sha256", str),
        ("cursor_protocol_sha256", str),
        ("fixture_sha256", str),
        ("fixture", adapter.AdapterFixture),
        ("binding_assessment", binding.BindingAssessment),
        ("audits", ("sequence", 2, 128, adapter.AdapterAudit)),
        ("transitions", ("sequence", 1, 127, adapter.TargetTransition)),
        ("events", ("sequence", 1, 127, adapter.EventWitness)),
        ("quotes", ("sequence", 1, 127, adapter.QuoteWitness)),
        ("publications", ("sequence", 1, 32, adapter.FeaturePublication)),
        ("inactivity_intervals", ("sequence", 0, 128, adapter.InactivityInterval)),
        ("clock_quality", adapter.ClockQuality),
        ("exceptional_clear_count", int),
        ("terminal_state", adapter.ReconstructedState),
        ("authority_flags", ("pairs", 34, 34, bool)),
        ("assessment_sha256", str),
    ),
}


def _project_fixed(value, schema):
    """Explicit complete projection with fixed depth and bounded container walks."""
    if schema in (int, str, bool):
        _require(type(value) is schema, "Exact scalar type required")
        if schema is str:
            _require(len(value) <= 256, "Fixed-schema text bound exceeded")
        return value
    if schema == "number":
        _require(type(value) in (int, float), "Exact feature scalar required")
        if type(value) is float:
            _require(math.isfinite(value), "Finite feature scalar required")
        return value
    if type(schema) is type:
        _require(type(value) is schema, "Exact nested record required")
        return {
            name: _project_fixed(getattr(value, name), child)
            for name, child in _RECORD_SCHEMAS[schema]
        }
    operation = schema[0]
    if operation == "optional":
        return None if value is None else _project_fixed(value, schema[1])
    if operation == "union":
        _require(type(value) in schema[1:], "Exact registered record alternative required")
        return _project_fixed(value, type(value))
    if operation == "row":
        _require(type(value) is tuple and len(value) == len(schema) - 1, "Exact fixed row required")
        return [_project_fixed(item, child) for item, child in zip(value, schema[1:], strict=True)]
    _require(
        type(value) is tuple and schema[1] <= len(value) <= schema[2],
        "Exact complete bounded tuple required",
    )
    if operation == "sequence":
        return [_project_fixed(item, schema[3]) for item in value]
    _require(operation == "pairs", "Unknown fixed projection operation")
    result = {}
    previous = None
    for pair in value:
        _require(type(pair) is tuple and len(pair) == 2, "Exact dictionary-pair row required")
        name = _project_fixed(pair[0], str)
        _require(previous is None or previous < name, "Unique ordinally sorted dictionary pairs")
        result[name] = _project_fixed(pair[1], schema[3])
        previous = name
    return result


def _admit_shape(value, schema):
    """Non-serializing shape admission before the unchanged public verifier.

    Only exact scalar types are inspected here, never their values. Record slots
    are read, so this is deliberately not a promise that old deep metadata checks
    precede those getter reads. The public adapter verifier retains its own local
    metadata-before-values boundary. No submitted object is replaced or repaired.
    """
    if schema in (int, str, bool):
        _require(type(value) is schema, "Exact submitted scalar type required")
        return
    if schema == "number":
        _require(type(value) in (int, float), "Exact submitted numerical scalar required")
        return
    if type(schema) is type:
        _require(type(value) is schema, "Exact submitted record type required")
        for name, child in _RECORD_SCHEMAS[schema]:
            _admit_shape(getattr(value, name), child)
        return
    operation = schema[0]
    if operation == "optional":
        if value is not None:
            _admit_shape(value, schema[1])
        return
    if operation == "union":
        _require(type(value) in schema[1:], "Exact submitted record alternative required")
        _admit_shape(value, type(value))
        return
    if operation == "row":
        _require(
            type(value) is tuple and len(value) == len(schema) - 1,
            "Exact submitted row arity required",
        )
        for item, child in zip(value, schema[1:], strict=True):
            _admit_shape(item, child)
        return
    _require(
        type(value) is tuple and schema[1] <= len(value) <= schema[2],
        "Exact bounded submitted tuple required",
    )
    if operation == "sequence":
        for item in value:
            _admit_shape(item, schema[3])
        return
    _require(operation == "pairs", "Unknown fixed admission operation")
    for pair in value:
        _require(
            type(pair) is tuple and len(pair) == 2, "Exact submitted dictionary-pair arity required"
        )
        _admit_shape(pair[0], str)
        _admit_shape(pair[1], schema[3])


def _exact(value, expected):
    _require(type(value) is type(expected) and value == expected, "Exact fixed value differs")


def _tuple(value, minimum, maximum):
    _require(
        type(value) is tuple and minimum <= len(value) <= maximum, "Bounded exact tuple required"
    )
    return value


def _enum(value, record_type, class_name, name, code, text):
    _require(type(value) is record_type, "Exact native enum record required")
    _literal_equal(
        _project_fixed(value, record_type),
        {"kind": "native_enum", "class_name": class_name, "name": name, "code": code, "text": text},
    )


def _mapping_text(value):
    _require(
        type(value) is str
        and 1 <= len(value) <= 32
        and re.fullmatch(r"[A-Za-z0-9._:-]+", value) is not None,
        "Complete bounded ASCII mapping name required",
    )
    return value


def _wire_date(value):
    _integer(value, 20000101, 21001231)
    result = date(value // 10000, value // 100 % 100, value % 100)
    return result.isoformat(), native.PythonDate(
        "python_date", result.year, result.month, result.day
    )


def _metadata_header(evidence, context):
    """Admit every header declaration before touching any original MBO value."""
    _require(type(evidence) is native.MemberDecodeEvidence, "Exact native result required")
    occurrences = _tuple(evidence.occurrences, 2, 128)
    _require(type(evidence.dbn_framing) is native.DbnFramingReport, "Exact framing result required")
    spans = _tuple(evidence.dbn_framing.spans, 2, 128)
    _require(len(spans) == len(occurrences), "Every occurrence needs its original wire span")
    previous_end = 0
    for position, (occurrence, span) in enumerate(zip(occurrences, spans, strict=True), 1):
        _require(type(occurrence) is native.DecodedOccurrence, "Exact occurrence required")
        _require(type(span) is native.WireSpan, "Exact wire span required")
        _exact(occurrence.decoded_position, position)
        _exact(occurrence.wire_span_ordinal, position)
        _exact(span.wire_span_ordinal, position)
        kind = "Metadata" if position == 1 else "MBO"
        _exact(occurrence.kind, kind)
        _exact(span.kind, kind)
        _integer(span.decompressed_start, previous_end, previous_end)
        _integer(span.decompressed_end, previous_end + 1, 1048576)
        previous_end = span.decompressed_end
    _exact(previous_end, evidence.dbn_framing.decompressed_bytes)
    metadata = occurrences[0].projection
    wire = spans[0].wire_fields
    _require(type(metadata) is native.MetadataProjection, "Exact Metadata projection required")
    _require(type(wire) is native.MetadataWireBody, "Exact original Metadata wire body required")
    for actual, expected in (
        (wire.version, 3),
        (metadata.version, 3),
        (wire.dataset, "GLBX.MDP3"),
        (metadata.dataset, "GLBX.MDP3"),
        (wire.schema, 0),
        (wire.start, _DAY_START),
        (metadata.start, _DAY_START),
        (wire.end, _DAY_END),
        (metadata.end_observed, _DAY_END),
        (wire.limit, 0),
        (metadata.limit_observed, None),
        (wire.stype_in, 4),
        (wire.stype_out, 0),
        (wire.ts_out, int(context.native_context.expected_ts_out)),
        (metadata.ts_out, context.native_context.expected_ts_out),
    ):
        _exact(actual, expected)
    _enum(metadata.schema, native.SchemaMbo, "Schema", "MBO", 0, "mbo")
    _enum(metadata.stype_in, native.SType, "SType", "PARENT", 4, "parent")
    _enum(metadata.stype_out, native.SType, "SType", "INSTRUMENT_ID", 0, "instrument_id")
    for actual in (wire.symbols, metadata.symbols):
        _tuple(actual, 1, 1)
        _exact(actual[0], "6E.FUT")
    for actual in (wire.partial, metadata.partial, wire.not_found, metadata.not_found):
        _tuple(actual, 0, 0)
    _exact(wire.symbols_count, 1)
    _exact(wire.partial_count, 0)
    _exact(wire.not_found_count, 0)
    groups = _tuple(wire.mappings, 1, 8)
    _exact(wire.mappings_count, len(groups))
    _tuple(metadata.mappings, len(groups), len(groups))
    converted = []
    logical = []
    names = set()
    interval_count = 0
    active = []
    for group in groups:
        _require(type(group) is native.WireMappingGroup, "Exact wire mapping group required")
        name = _mapping_text(group.raw_symbol)
        _require(name not in names, "Unique complete mapping group names required")
        names.add(name)
        intervals = _tuple(group.intervals, 0, 16)
        _exact(group.interval_count, len(intervals))
        interval_count += len(intervals)
        _require(interval_count <= 32, "Complete mapping interval limit exceeded")
        old_intervals = []
        logical_intervals = []
        for interval in intervals:
            _require(type(interval) is native.WireMappingInterval, "Exact wire mapping interval")
            start, logical_start = _wire_date(interval.start_date)
            end, logical_end = _wire_date(interval.end_date)
            _require(start < end, "Mapping interval must increase strictly")
            symbol = _mapping_text(interval.symbol)
            old_intervals.append(cursor.MappingInterval(start, end, symbol))
            logical_intervals.append(native.MappingInterval(logical_start, logical_end, symbol))
            if name == "6EM5" and start <= "2025-04-07" < end:
                _require(
                    re.fullmatch(r"[0-9]+", symbol) is not None, "ASCII numeric target mapping"
                )
                mapped = int(symbol)
                _integer(mapped, 0, 4294967295)
                active.append(mapped)
        converted.append(cursor.MappingGroup(name, tuple(old_intervals)))
        logical.append(native.MappingGroup(name, tuple(logical_intervals)))
    _require(len(active) == 1, "Exactly one active end-exclusive target interval required")
    logical.sort(key=lambda group: group.raw_symbol)
    _literal_equal(
        _project_fixed(metadata.mappings, ("sequence", 1, 8, native.MappingGroup)),
        _project_fixed(tuple(logical), ("sequence", 1, 8, native.MappingGroup)),
    )
    # Project only these admitted header records here; MBO projection is later.
    _project_fixed(metadata, native.MetadataProjection)
    _project_fixed(wire, native.MetadataWireBody)
    return cursor.DeclaredHeader(
        wire.dataset, "mbo", wire.symbols, wire.not_found, wire.start, wire.end, tuple(converted)
    )


def _character(raw, observation, record_type, class_name, rows):
    _integer(raw, 0, 127)
    text = chr(raw)
    if type(observation) is native.UnknownChar:
        _exact(observation.kind, "str")
        _exact(observation.value, text)
        _require(raw not in {row[1] for row in rows}, "Known character needs its exact enum")
    else:
        _require(type(observation) is record_type, "Exact character observation required")
        matching = [row for row in rows if row[1] == raw]
        _require(len(matching) == 1, "Registered enum character required")
        name, code, expected_text = matching[0]
        _enum(observation, record_type, class_name, name, code, expected_text)
    return text


def _payload(occurrence, span, present):
    observed = occurrence.projection
    wire = span.wire_fields
    _require(type(observed) is native.MboObservation, "Exact MBO observation required")
    _require(type(wire) is native.MboWireBody, "Exact MBO wire body required")
    # Exact native widths are narrower than some accepted old JSON widths.
    for name, minimum, maximum in (
        ("publisher_id", 0, 65535),
        ("instrument_id", 0, 4294967295),
        ("ts_event", 0, 9223372036854775807),
        ("order_id", 0, 18446744073709551615),
        ("price", -9223372036854775808, 9223372036854775807),
        ("size", 0, 4294967295),
        ("ts_recv", 0, 9223372036854775807),
        ("flags", 0, 255),
        ("channel_id", 0, 255),
        ("ts_in_delta", -2147483648, 2147483647),
        ("sequence", 0, 4294967295),
    ):
        raw = getattr(wire, name)
        _integer(raw, minimum, maximum)
        _exact(getattr(observed, name), raw)
    action = _character(
        wire.action,
        observed.action,
        native.Action,
        "Action",
        (
            ("MODIFY", 77, "M"),
            ("TRADE", 84, "T"),
            ("FILL", 70, "F"),
            ("CANCEL", 67, "C"),
            ("ADD", 65, "A"),
            ("CLEAR", 82, "R"),
            ("NONE", 78, "N"),
        ),
    )
    side = _character(
        wire.side,
        observed.side,
        native.Side,
        "Side",
        (
            ("ASK", 65, "A"),
            ("BID", 66, "B"),
            ("NONE", 78, "N"),
        ),
    )
    _exact(wire.rtype, 160)
    _enum(observed.rtype, native.RtypeMbo, "RType", "MBO", 160, "mbo")
    size = 64 if present else 56
    _exact(wire.length_words, size // 4)
    _exact(observed.record_size_observed, size)
    _exact(span.decompressed_end - span.decompressed_start, size)
    _exact(observed.ts_index_observed, wire.ts_recv)
    if present:
        _integer(wire.ts_out, 0, 9223372036854775807)
        _exact(observed.ts_out_observed, wire.ts_out)
    else:
        _exact(wire.ts_out, None)
        _exact(observed.ts_out_observed, 18446744073709551615)
    return binding.MboPayload(
        wire.publisher_id,
        wire.instrument_id,
        wire.ts_event,
        wire.order_id,
        wire.price,
        wire.size,
        action,
        side,
        wire.ts_recv,
        wire.flags,
        wire.channel_id,
        wire.ts_in_delta,
        wire.sequence,
        wire.ts_out,
        wire.rtype,
        observed.record_size_observed,
    )


def _adapter_fixture(evidence, context, member_pin):
    header = _metadata_header(evidence, context)
    present = context.native_context.expected_ts_out
    payload_context = binding.PayloadContext(
        "constructed_mbo_json_v1", 1, "present" if present else "absent"
    )
    payload_context_pin = binding.context_sha256(
        payload_context, expected_protocol_sha256=_BINDING_PIN
    )
    items = [cursor.DecodedItem(1, "metadata", None, None)]
    payloads = [None]
    for occurrence, span in zip(
        evidence.occurrences[1:], evidence.dbn_framing.spans[1:], strict=True
    ):
        value = _payload(occurrence, span, present)
        payload_pin = binding.payload_sha256(
            value,
            payload_context,
            expected_protocol_sha256=_BINDING_PIN,
            expected_context_sha256=payload_context_pin,
        )
        payloads.append(value)
        items.append(
            cursor.DecodedItem(occurrence.decoded_position, "mbo", value.instrument_id, payload_pin)
        )
    fixture = cursor.CursorFixture(
        context.fixture_id,
        context.source_session,
        "2025-04-07",
        "6EM5",
        header,
        member_pin,
        len(items),
        tuple(items),
    )
    cursor_pin = cursor.fixture_sha256(fixture, expected_protocol_sha256=_CURSOR_PIN)
    cursor_result = cursor.assess(
        fixture,
        expected_fixture_sha256=cursor_pin,
        expected_protocol_sha256=_CURSOR_PIN,
    )
    cursor.verify(
        cursor_result,
        fixture,
        expected_fixture_sha256=cursor_pin,
        expected_protocol_sha256=_CURSOR_PIN,
        expected_assessment_sha256=cursor_result.assessment_sha256,
    )
    bundle = binding.PayloadBundle(payload_context, fixture, tuple(payloads))
    bundle_pin = binding.bundle_sha256(
        bundle,
        expected_protocol_sha256=_BINDING_PIN,
        expected_context_sha256=payload_context_pin,
        expected_cursor_protocol_sha256=_CURSOR_PIN,
        expected_cursor_fixture_sha256=cursor_pin,
    )
    adapter_context = adapter.AdapterContext(
        3, "AS_IS", 3, "parent", "instrument_id", (), None, present
    )
    adapter_context_pin = adapter.context_sha256(
        adapter_context, expected_protocol_sha256=_ADAPTER_PIN
    )
    result = adapter.AdapterFixture(adapter_context, bundle)
    arguments = {
        "expected_protocol_sha256": _ADAPTER_PIN,
        "expected_context_sha256": adapter_context_pin,
        "expected_binding_protocol_sha256": _BINDING_PIN,
        "expected_cursor_protocol_sha256": _CURSOR_PIN,
        "expected_cursor_fixture_sha256": cursor_pin,
        "expected_binding_bundle_sha256": bundle_pin,
    }
    arguments["expected_fixture_sha256"] = adapter.fixture_sha256(result, **arguments)
    return result, arguments


def _own_digest(body, own_name, maximum):
    _pins(body[own_name])
    without_own = {name: value for name, value in body.items() if name != own_name}
    _require(_digest(without_own, maximum) == body[own_name], "Complete named own digest differs")


def _native_body(evidence, member_bytes, context_pin, member_pin, metadata_pin, packet):
    body = _project_fixed(evidence, native.MemberDecodeEvidence)
    for name, expected in (
        ("status", packet["dependencies"]["native"]["status"]),
        ("protocol_sha256", _NATIVE_PIN),
        ("profile_sha256", _PROFILE_PIN),
        ("runtime_manifest_sha256", _RUNTIME_PIN),
        ("context_sha256", context_pin),
        ("member_sha256", member_pin),
        ("metadata_sha256", metadata_pin),
    ):
        _exact(body[name], expected)
    _literal_equal(body["authorities"], [[name, False] for name in packet["authority_names"]])
    _exact(_digest(body["runtime_manifest"], 1048576), _RUNTIME_PIN)
    _own_digest(body, "evidence_sha256", 1048576)
    zstd = body["zstd_framing"]
    dbn = body["dbn_framing"]
    terminal = body["terminal"]
    _own_digest(zstd, "report_sha256", 1048576)
    _own_digest(dbn, "report_sha256", 1048576)
    _exact(zstd["compressed_bytes"], len(member_bytes))
    _exact(zstd["compressed_sha256"], member_pin)
    _integer(zstd["decompressed_bytes"], 1, 1048576)
    _pins(zstd["decompressed_sha256"])
    _exact(dbn["decompressed_bytes"], zstd["decompressed_bytes"])
    _exact(dbn["decompressed_sha256"], zstd["decompressed_sha256"])
    compressed_end = decompressed_end = 0
    for ordinal, frame in enumerate(zstd["frames"], 1):
        _exact(frame["frame_ordinal"], ordinal)
        _exact(frame["compressed_start"], compressed_end)
        _integer(frame["compressed_end"], compressed_end + 1, len(member_bytes))
        _exact(frame["decompressed_start"], decompressed_end)
        _integer(frame["decompressed_end"], decompressed_end + 1, zstd["decompressed_bytes"])
        _pins(frame["compressed_span_sha256"], frame["decompressed_span_sha256"])
        _exact(
            hashlib.sha256(member_bytes[compressed_end : frame["compressed_end"]]).hexdigest(),
            frame["compressed_span_sha256"],
        )
        compressed_end, decompressed_end = frame["compressed_end"], frame["decompressed_end"]
    _exact(compressed_end, len(member_bytes))
    _exact(decompressed_end, zstd["decompressed_bytes"])
    occurrences = body["occurrences"]
    spans = dbn["spans"]
    _exact(len(occurrences), len(spans))
    previous_end = 0
    for position, (occurrence, span) in enumerate(zip(occurrences, spans, strict=True), 1):
        kind = "Metadata" if position == 1 else "MBO"
        _exact(occurrence["decoded_position"], position)
        _exact(occurrence["wire_span_ordinal"], position)
        _exact(occurrence["kind"], kind)
        _exact(span["wire_span_ordinal"], position)
        _exact(span["kind"], kind)
        _exact(span["decompressed_start"], previous_end)
        _integer(span["decompressed_end"], previous_end + 1, dbn["decompressed_bytes"])
        _pins(span["wire_sha256"], span["wire_fields_sha256"], occurrence["projection_sha256"])
        _exact(_digest(span["wire_fields"], 1048576), span["wire_fields_sha256"])
        _exact(_digest(occurrence["projection"], 1048576), occurrence["projection_sha256"])
        if position == 1:
            _integer(span["decompressed_end"], 128, 65536)
            _exact(span["wire_fields"]["length_body"] + 8, span["decompressed_end"])
            _exact(occurrence["projection_sha256"], metadata_pin)
        previous_end = span["decompressed_end"]
    _exact(previous_end, dbn["decompressed_bytes"])
    for name, expected in (
        ("compressed_bytes", len(member_bytes)),
        ("compressed_sha256", member_pin),
        ("decompressed_bytes", dbn["decompressed_bytes"]),
        ("decompressed_sha256", dbn["decompressed_sha256"]),
        ("frame_count", len(zstd["frames"])),
        ("decoded_positions", len(occurrences)),
        ("metadata_count", 1),
        ("mbo_count", len(occurrences) - 1),
        ("dbn_remaining_buffer_bytes", 0),
        ("zstd_framing_sha256", zstd["report_sha256"]),
        ("dbn_framing_sha256", dbn["report_sha256"]),
        ("framing_status", "complete_independent_v3_mbo_framing"),
        ("zstd_status", "complete_nonempty_frames_native_terminal_equality"),
    ):
        _exact(terminal[name], expected)
    return body


def _adapter_body(assessment, fixture, arguments, packet):
    """Complete late projection, after public replay/verification has finished."""
    body = _project_fixed(assessment, adapter.AdapterAssessment)
    fixture_body = _project_fixed(fixture, adapter.AdapterFixture)
    _literal_equal(body["fixture"], fixture_body)
    _exact(_digest(fixture_body, 1048576), arguments["expected_fixture_sha256"])
    _exact(body["fixture_sha256"], arguments["expected_fixture_sha256"])
    _exact(body["context_sha256"], arguments["expected_context_sha256"])
    _exact(body["protocol_sha256"], _ADAPTER_PIN)
    _exact(body["binding_protocol_sha256"], _BINDING_PIN)
    _exact(body["cursor_protocol_sha256"], _CURSOR_PIN)
    _own_digest(body, "assessment_sha256", 1048576)
    _canonical(body["terminal_state"], 1048576)
    _integer(body["exceptional_clear_count"], 0, 32)
    bound = body["binding_assessment"]
    cursor_result = bound["cursor_assessment"]
    for name, value in (("adapter", body), ("binding", bound), ("cursor", cursor_result)):
        _exact(value["status"], packet["dependencies"][name]["status"])
        _literal_equal(value["authority_flags"], packet["dependencies"][name]["authority_flags"])
    _exact(bound["protocol_sha256"], _BINDING_PIN)
    _exact(bound["cursor_protocol_sha256"], _CURSOR_PIN)
    _exact(cursor_result["protocol_sha256"], _CURSOR_PIN)
    _literal_equal(bound["bundle"], fixture_body["payload_bundle"])
    _literal_equal(cursor_result["fixture"], bound["bundle"]["cursor_fixture"])
    _exact(_digest(cursor_result["fixture"], 65536), arguments["expected_cursor_fixture_sha256"])
    _exact(cursor_result["fixture_sha256"], arguments["expected_cursor_fixture_sha256"])
    _exact(bound["cursor_fixture_sha256"], arguments["expected_cursor_fixture_sha256"])
    _own_digest(cursor_result, "assessment_sha256", 65536)
    _exact(_digest(bound["bundle"], 262144), arguments["expected_binding_bundle_sha256"])
    _exact(bound["bundle_sha256"], arguments["expected_binding_bundle_sha256"])
    _exact(_digest(bound["bundle"]["context"]), bound["context_sha256"])
    _own_digest(bound, "assessment_sha256", 262144)
    _exact(_digest(fixture_body["context"]), arguments["expected_context_sha256"])
    count = len(cursor_result["fixture"]["items"])
    _exact(cursor_result["decoded_item_count"], count)
    for audits in (body["audits"], bound["audits"], cursor_result["audits"]):
        _exact(len(audits), count)
        for position, audit in enumerate(audits, 1):
            _exact(audit["decoded_position"], position)
    for name, own in (
        ("events", "event_sha256"),
        ("quotes", "quote_sha256"),
        ("publications", "publication_sha256"),
    ):
        for value in body[name]:
            _own_digest(value, own, 1048576)
    for publication in body["publications"]:
        _literal_equal(
            [pair[0] for pair in publication["features"]],
            packet["dependencies"]["adapter"]["feature_names"],
        )
    return body


def _prefix_body(link, *, include_own=True):
    _require(type(link) is NativePrefixLink, "Exact native prefix link required")
    result = {
        "decoded_position": link.decoded_position,
        "kind": link.kind,
        "wire_span_ordinal": link.wire_span_ordinal,
        "decompressed_start": link.decompressed_start,
        "decompressed_end": link.decompressed_end,
        "wire_sha256": link.wire_sha256,
        "wire_fields_sha256": link.wire_fields_sha256,
        "projection_sha256": link.projection_sha256,
        "previous_prefix_sha256": link.previous_prefix_sha256,
    }
    if include_own:
        result["prefix_sha256"] = link.prefix_sha256
    return result


def _publication_body(link, *, include_own=True):
    _require(type(link) is PublicationLink, "Exact publication link required")
    result = {
        "publication_ordinal": link.publication_ordinal,
        "quote_ordinal": link.quote_ordinal,
        "event_ordinal": link.event_ordinal,
        "decoded_position": link.decoded_position,
        "ts_recv_ns": link.ts_recv_ns,
        "adapter_prefix_sha256": link.adapter_prefix_sha256,
        "publication_sha256": link.publication_sha256,
        "native_prefix_sha256": link.native_prefix_sha256,
    }
    if include_own:
        result["link_sha256"] = link.link_sha256
    return result


def _causal_links(native_body, adapter_body, bridge_context_pin, native_context_pin):
    previous = _digest(
        {
            "domain": "member_publication_native_prefix_seed_v1",
            "bridge_protocol_sha256": _PROTOCOL_SHA,
            "bridge_context_sha256": bridge_context_pin,
            "native_context_sha256": native_context_pin,
            "native_protocol_sha256": _NATIVE_PIN,
            "profile_sha256": _PROFILE_PIN,
            "runtime_manifest_sha256": _RUNTIME_PIN,
        }
    )
    prefixes = []
    for occurrence, span in zip(
        native_body["occurrences"], native_body["dbn_framing"]["spans"], strict=True
    ):
        values = (
            occurrence["decoded_position"],
            occurrence["kind"],
            span["wire_span_ordinal"],
            span["decompressed_start"],
            span["decompressed_end"],
            span["wire_sha256"],
            span["wire_fields_sha256"],
            occurrence["projection_sha256"],
            previous,
        )
        incomplete = NativePrefixLink(*values, "0" * 64)
        previous = _digest(
            {
                "domain": "member_publication_native_prefix_link_v1",
                "link": _prefix_body(incomplete, include_own=False),
            }
        )
        prefixes.append(NativePrefixLink(*values, previous))
    publications = []
    for ordinal, publication in enumerate(adapter_body["publications"], 1):
        _exact(publication["publication_ordinal"], ordinal)
        _integer(publication["decoded_position"], 2, len(prefixes))
        _integer(publication["quote_ordinal"], 1, len(adapter_body["quotes"]))
        _integer(publication["event_ordinal"], 1, len(adapter_body["events"]))
        quote = adapter_body["quotes"][publication["quote_ordinal"] - 1]
        event = adapter_body["events"][publication["event_ordinal"] - 1]
        for name in (
            "quote_ordinal",
            "event_ordinal",
            "decoded_position",
            "ts_recv_ns",
            "adapter_prefix_sha256",
        ):
            _exact(publication[name], quote[name])
        _exact(event["event_ordinal"], publication["event_ordinal"])
        _exact(event["quote_ordinal"], publication["quote_ordinal"])
        _exact(event["closing_decoded_position"], publication["decoded_position"])
        _exact(event["ts_recv_ns"], publication["ts_recv_ns"])
        _exact(event["adapter_prefix_sha256"], publication["adapter_prefix_sha256"])
        values = (
            ordinal,
            publication["quote_ordinal"],
            publication["event_ordinal"],
            publication["decoded_position"],
            publication["ts_recv_ns"],
            publication["adapter_prefix_sha256"],
            publication["publication_sha256"],
            prefixes[publication["decoded_position"] - 1].prefix_sha256,
        )
        incomplete = PublicationLink(*values, "0" * 64)
        pin = _digest(
            {
                "domain": "member_publication_link_v1",
                "bridge_protocol_sha256": _PROTOCOL_SHA,
                "bridge_context_sha256": bridge_context_pin,
                "link": _publication_body(incomplete, include_own=False),
            }
        )
        publications.append(PublicationLink(*values, pin))
    result = tuple(prefixes), tuple(publications)
    _links_preflight(*result)
    return result


def _bridge_body(
    context_body, context_pin, native_body, adapter_body, prefixes, publications, authorities
):
    return {
        "status": _STATUS,
        "protocol_sha256": _PROTOCOL_SHA,
        "context_sha256": context_pin,
        "context": context_body,
        "native_evidence": native_body,
        "adapter_assessment": adapter_body,
        "native_prefixes": [_prefix_body(link) for link in prefixes],
        "publication_links": [_publication_body(link) for link in publications],
        "authorities": [[name, value] for name, value in authorities],
    }


@_guard
def protocol() -> dict:
    """Return the fresh complete fixed protocol without caller or native execution."""
    return _protocol_body()


@_guard
def protocol_sha256() -> str:
    """Pin the complete fixed literal protocol."""
    return _digest(_protocol_body(), 262144)


@_guard
def context_sha256(context, *, expected_protocol_sha256) -> str:
    """Validate the complete exact context before returning its canonical identity."""
    _pins(expected_protocol_sha256)
    _expected_protocols(expected_protocol_sha256)
    return _digest(_context_body(context))


@_guard
def replay(
    member_bytes,
    context,
    *,
    expected_protocol_sha256,
    expected_context_sha256,
    expected_member_sha256,
    expected_metadata_sha256,
) -> BridgeEvidence:
    """Reconstruct one complete invented member/publication association atomically."""
    _pins(
        expected_protocol_sha256,
        expected_context_sha256,
        expected_member_sha256,
        expected_metadata_sha256,
    )
    packet, context_body = _preflight(
        member_bytes,
        context,
        expected_protocol_sha256,
        expected_context_sha256,
        expected_member_sha256,
    )
    native_context_pin = native.context_sha256(
        context.native_context, expected_protocol_sha256=_NATIVE_PIN
    )
    native_evidence = native.decode_member(
        member_bytes,
        context.native_context,
        expected_protocol_sha256=_NATIVE_PIN,
        expected_profile_sha256=_PROFILE_PIN,
        expected_runtime_manifest_sha256=_RUNTIME_PIN,
        expected_member_sha256=expected_member_sha256,
        expected_metadata_sha256=expected_metadata_sha256,
    )
    fixture, arguments = _adapter_fixture(native_evidence, context, expected_member_sha256)
    assessment = adapter.replay(fixture, **arguments)
    native_body = _native_body(
        native_evidence,
        member_bytes,
        native_context_pin,
        expected_member_sha256,
        expected_metadata_sha256,
        packet,
    )
    adapter_body = _adapter_body(assessment, fixture, arguments, packet)
    prefixes, publications = _causal_links(
        native_body, adapter_body, expected_context_sha256, native_context_pin
    )
    authorities = tuple((name, False) for name in packet["authority_names"])
    body = _bridge_body(
        context_body,
        expected_context_sha256,
        native_body,
        adapter_body,
        prefixes,
        publications,
        authorities,
    )
    own = _digest(body, 4194304)
    _canonical({**body, "evidence_sha256": own}, 4194304)
    return BridgeEvidence(
        _STATUS,
        _PROTOCOL_SHA,
        expected_context_sha256,
        context,
        native_evidence,
        assessment,
        prefixes,
        publications,
        authorities,
        own,
    )


@_guard
def verify(
    evidence,
    member_bytes,
    context,
    *,
    expected_protocol_sha256,
    expected_context_sha256,
    expected_member_sha256,
    expected_metadata_sha256,
    expected_evidence_sha256,
) -> None:
    """Verify complete original bytes and every submitted association field."""
    _pins(
        expected_protocol_sha256,
        expected_context_sha256,
        expected_member_sha256,
        expected_metadata_sha256,
        expected_evidence_sha256,
    )
    protocol_body, context_body = _preflight(
        member_bytes,
        context,
        expected_protocol_sha256,
        expected_context_sha256,
        expected_member_sha256,
    )
    _submitted_preflight(
        evidence,
        context_body,
        protocol_body,
        expected_protocol_sha256,
        expected_context_sha256,
        expected_evidence_sha256,
    )
    native_context_pin = native.context_sha256(
        context.native_context, expected_protocol_sha256=_NATIVE_PIN
    )
    native.verify(
        evidence.native_evidence,
        member_bytes,
        context.native_context,
        expected_protocol_sha256=_NATIVE_PIN,
        expected_profile_sha256=_PROFILE_PIN,
        expected_runtime_manifest_sha256=_RUNTIME_PIN,
        expected_member_sha256=expected_member_sha256,
        expected_metadata_sha256=expected_metadata_sha256,
        expected_evidence_sha256=evidence.native_evidence.evidence_sha256,
    )
    fixture, arguments = _adapter_fixture(evidence.native_evidence, context, expected_member_sha256)
    _admit_shape(evidence.adapter_assessment, adapter.AdapterAssessment)
    adapter.verify(
        evidence.adapter_assessment,
        fixture,
        **arguments,
        expected_assessment_sha256=evidence.adapter_assessment.assessment_sha256,
    )
    native_body = _native_body(
        evidence.native_evidence,
        member_bytes,
        native_context_pin,
        expected_member_sha256,
        expected_metadata_sha256,
        protocol_body,
    )
    adapter_body = _adapter_body(evidence.adapter_assessment, fixture, arguments, protocol_body)
    prefixes, publications = _causal_links(
        native_body, adapter_body, expected_context_sha256, native_context_pin
    )
    authorities = tuple((name, False) for name in protocol_body["authority_names"])
    rebuilt_body = _bridge_body(
        context_body,
        expected_context_sha256,
        native_body,
        adapter_body,
        prefixes,
        publications,
        authorities,
    )
    # The supplied envelope is projected from its actual fields, not silently
    # replaced by reconstructed links or fixed top-level values.
    submitted_body = {
        "status": evidence.status,
        "protocol_sha256": evidence.protocol_sha256,
        "context_sha256": evidence.context_sha256,
        "context": _context_body(evidence.context),
        "native_evidence": native_body,
        "adapter_assessment": adapter_body,
        "native_prefixes": [_prefix_body(link) for link in evidence.native_prefixes],
        "publication_links": [_publication_body(link) for link in evidence.publication_links],
        "authorities": [[name, value] for name, value in evidence.authorities],
    }
    rebuilt_raw = _canonical(rebuilt_body, 4194304)
    submitted_raw = _canonical(submitted_body, 4194304)
    _require(submitted_raw == rebuilt_raw, "Every complete bridge field must reconstruct exactly")
    _exact(hashlib.sha256(submitted_raw).hexdigest(), expected_evidence_sha256)
    _canonical({**submitted_body, "evidence_sha256": evidence.evidence_sha256}, 4194304)
    return None
