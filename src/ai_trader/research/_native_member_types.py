"""Exact public records for bounded native-member consistency evidence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SchemaMbo:
    kind: str
    class_name: str
    name: str
    code: int
    text: str


@dataclass(frozen=True, slots=True)
class RtypeMbo:
    kind: str
    class_name: str
    name: str
    code: int
    text: str


@dataclass(frozen=True, slots=True)
class SType:
    kind: str
    class_name: str
    name: str
    code: int
    text: str


@dataclass(frozen=True, slots=True)
class Action:
    kind: str
    class_name: str
    name: str
    code: int
    text: str


@dataclass(frozen=True, slots=True)
class Side:
    kind: str
    class_name: str
    name: str
    code: int
    text: str


@dataclass(frozen=True, slots=True)
class UnknownChar:
    kind: str
    value: str


@dataclass(frozen=True, slots=True)
class PythonDate:
    kind: str
    year: int
    month: int
    day: int


@dataclass(frozen=True, slots=True)
class WireMappingInterval:
    start_date: int
    end_date: int
    symbol: str


@dataclass(frozen=True, slots=True)
class MappingInterval:
    start_date: PythonDate
    end_date: PythonDate
    symbol: str


@dataclass(frozen=True, slots=True)
class MappingGroup:
    raw_symbol: str
    intervals: tuple[MappingInterval, ...]


@dataclass(frozen=True, slots=True)
class WireMappingGroup:
    raw_symbol: str
    interval_count: int
    intervals: tuple[WireMappingInterval, ...]


@dataclass(frozen=True, slots=True)
class MetadataWireBody:
    magic_hex: str
    version: int
    length_body: int
    dataset: str
    dataset_cstr_bytes: int
    schema: int
    start: int
    end: int
    limit: int
    stype_in: int
    stype_out: int
    ts_out: int
    symbol_cstr_len: int
    reserved_bytes: tuple[int, ...]
    schema_definition_length: int
    symbols_count: int
    symbols: tuple[str, ...]
    partial_count: int
    partial: tuple[str, ...]
    not_found_count: int
    not_found: tuple[str, ...]
    mappings_count: int
    mappings: tuple[WireMappingGroup, ...]
    alignment_padding_bytes: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MetadataProjection:
    version: int
    dataset: str
    schema: SchemaMbo
    start: int
    end_observed: None | int
    limit_observed: None | int
    stype_in: None | SType
    stype_out: SType
    ts_out: bool
    symbol_cstr_len: int
    symbols: tuple[str, ...]
    partial: tuple[str, ...]
    not_found: tuple[str, ...]
    mappings: tuple[MappingGroup, ...]


@dataclass(frozen=True, slots=True)
class MboWireBody:
    length_words: int
    rtype: int
    publisher_id: int
    instrument_id: int
    ts_event: int
    order_id: int
    price: int
    size: int
    flags: int
    channel_id: int
    action: int
    side: int
    ts_recv: int
    ts_in_delta: int
    sequence: int
    ts_out: None | int


@dataclass(frozen=True, slots=True)
class MboObservation:
    rtype: RtypeMbo
    publisher_id: int
    instrument_id: int
    ts_event: int
    order_id: int
    price: int
    size: int
    action: Action | UnknownChar
    side: Side | UnknownChar
    ts_recv: int
    flags: int
    channel_id: int
    ts_in_delta: int
    sequence: int
    ts_out_observed: int
    record_size_observed: int
    ts_index_observed: int


@dataclass(frozen=True, slots=True)
class MemberDecodeContext:
    profile_id: str
    member_compression: str
    input_version: int
    upgrade_policy: str
    expected_ts_out: bool


@dataclass(frozen=True, slots=True)
class DecodedOccurrence:
    decoded_position: int
    kind: str
    wire_span_ordinal: int
    projection: MetadataProjection | MboObservation
    projection_sha256: str


@dataclass(frozen=True, slots=True)
class FrameSpan:
    frame_ordinal: int
    compressed_start: int
    compressed_end: int
    decompressed_start: int
    decompressed_end: int
    compressed_span_sha256: str
    decompressed_span_sha256: str


@dataclass(frozen=True, slots=True)
class ZstdFramingReport:
    compressed_bytes: int
    compressed_sha256: str
    decompressed_bytes: int
    decompressed_sha256: str
    frames: tuple[FrameSpan, ...]
    report_sha256: str


@dataclass(frozen=True, slots=True)
class WireSpan:
    wire_span_ordinal: int
    kind: str
    decompressed_start: int
    decompressed_end: int
    wire_sha256: str
    wire_fields: MetadataWireBody | MboWireBody
    wire_fields_sha256: str


@dataclass(frozen=True, slots=True)
class DbnFramingReport:
    decompressed_bytes: int
    decompressed_sha256: str
    spans: tuple[WireSpan, ...]
    report_sha256: str


@dataclass(frozen=True, slots=True)
class TerminalEvidence:
    compressed_bytes: int
    compressed_sha256: str
    decompressed_bytes: int
    decompressed_sha256: str
    frame_count: int
    decoded_positions: int
    metadata_count: int
    mbo_count: int
    dbn_remaining_buffer_bytes: int
    zstd_framing_sha256: str
    dbn_framing_sha256: str
    framing_status: str
    zstd_status: str


@dataclass(frozen=True, slots=True)
class Interpreter:
    implementation: str
    version: tuple[int, int, int]
    executable_sha256: str


@dataclass(frozen=True, slots=True)
class Package:
    name: str
    version: str
    metadata_sha256: str


@dataclass(frozen=True, slots=True)
class Artifact:
    logical_id: str
    kind: str
    raw_bytes: int
    raw_sha256: str


@dataclass(frozen=True, slots=True)
class RuntimeManifest:
    schema: str
    interpreter: Interpreter
    packages: tuple[Package, ...]
    artifacts: tuple[Artifact, ...]


@dataclass(frozen=True, slots=True)
class MemberDecodeEvidence:
    status: str
    protocol_sha256: str
    profile_sha256: str
    runtime_manifest: RuntimeManifest
    runtime_manifest_sha256: str
    context_sha256: str
    member_sha256: str
    metadata_sha256: str
    occurrences: tuple[DecodedOccurrence, ...]
    zstd_framing: ZstdFramingReport
    dbn_framing: DbnFramingReport
    terminal: TerminalEvidence
    authorities: tuple[tuple[str, bool], ...]
    evidence_sha256: str


_RECORDS = {
    "SchemaMbo": SchemaMbo,
    "RtypeMbo": RtypeMbo,
    "SType": SType,
    "Action": Action,
    "Side": Side,
    "UnknownChar": UnknownChar,
    "PythonDate": PythonDate,
    "WireMappingInterval": WireMappingInterval,
    "MappingInterval": MappingInterval,
    "MappingGroup": MappingGroup,
    "WireMappingGroup": WireMappingGroup,
    "MetadataWireBody": MetadataWireBody,
    "MetadataProjection": MetadataProjection,
    "MboWireBody": MboWireBody,
    "MboObservation": MboObservation,
    "Context": MemberDecodeContext,
    "DecodedOccurrence": DecodedOccurrence,
    "FrameSpan": FrameSpan,
    "ZstdFramingReport": ZstdFramingReport,
    "WireSpan": WireSpan,
    "DbnFramingReport": DbnFramingReport,
    "TerminalEvidence": TerminalEvidence,
    "Interpreter": Interpreter,
    "Package": Package,
    "Artifact": Artifact,
    "RuntimeManifest": RuntimeManifest,
    "MemberDecodeEvidence": MemberDecodeEvidence,
}

_PROJECTORS = {
    "SchemaMbo": lambda v: {
        "kind": v.kind,
        "class_name": v.class_name,
        "name": v.name,
        "code": v.code,
        "text": v.text,
    },
    "RtypeMbo": lambda v: {
        "kind": v.kind,
        "class_name": v.class_name,
        "name": v.name,
        "code": v.code,
        "text": v.text,
    },
    "SType": lambda v: {
        "kind": v.kind,
        "class_name": v.class_name,
        "name": v.name,
        "code": v.code,
        "text": v.text,
    },
    "Action": lambda v: {
        "kind": v.kind,
        "class_name": v.class_name,
        "name": v.name,
        "code": v.code,
        "text": v.text,
    },
    "Side": lambda v: {
        "kind": v.kind,
        "class_name": v.class_name,
        "name": v.name,
        "code": v.code,
        "text": v.text,
    },
    "UnknownChar": lambda v: {"kind": v.kind, "value": v.value},
    "PythonDate": lambda v: {"kind": v.kind, "year": v.year, "month": v.month, "day": v.day},
    "WireMappingInterval": lambda v: {
        "start_date": v.start_date,
        "end_date": v.end_date,
        "symbol": v.symbol,
    },
    "MappingInterval": lambda v: {
        "start_date": v.start_date,
        "end_date": v.end_date,
        "symbol": v.symbol,
    },
    "MappingGroup": lambda v: {"raw_symbol": v.raw_symbol, "intervals": v.intervals},
    "WireMappingGroup": lambda v: {
        "raw_symbol": v.raw_symbol,
        "interval_count": v.interval_count,
        "intervals": v.intervals,
    },
    "MetadataWireBody": lambda v: {
        "magic_hex": v.magic_hex,
        "version": v.version,
        "length_body": v.length_body,
        "dataset": v.dataset,
        "dataset_cstr_bytes": v.dataset_cstr_bytes,
        "schema": v.schema,
        "start": v.start,
        "end": v.end,
        "limit": v.limit,
        "stype_in": v.stype_in,
        "stype_out": v.stype_out,
        "ts_out": v.ts_out,
        "symbol_cstr_len": v.symbol_cstr_len,
        "reserved_bytes": v.reserved_bytes,
        "schema_definition_length": v.schema_definition_length,
        "symbols_count": v.symbols_count,
        "symbols": v.symbols,
        "partial_count": v.partial_count,
        "partial": v.partial,
        "not_found_count": v.not_found_count,
        "not_found": v.not_found,
        "mappings_count": v.mappings_count,
        "mappings": v.mappings,
        "alignment_padding_bytes": v.alignment_padding_bytes,
    },
    "MetadataProjection": lambda v: {
        "version": v.version,
        "dataset": v.dataset,
        "schema": v.schema,
        "start": v.start,
        "end_observed": v.end_observed,
        "limit_observed": v.limit_observed,
        "stype_in": v.stype_in,
        "stype_out": v.stype_out,
        "ts_out": v.ts_out,
        "symbol_cstr_len": v.symbol_cstr_len,
        "symbols": v.symbols,
        "partial": v.partial,
        "not_found": v.not_found,
        "mappings": v.mappings,
    },
    "MboWireBody": lambda v: {
        "length_words": v.length_words,
        "rtype": v.rtype,
        "publisher_id": v.publisher_id,
        "instrument_id": v.instrument_id,
        "ts_event": v.ts_event,
        "order_id": v.order_id,
        "price": v.price,
        "size": v.size,
        "flags": v.flags,
        "channel_id": v.channel_id,
        "action": v.action,
        "side": v.side,
        "ts_recv": v.ts_recv,
        "ts_in_delta": v.ts_in_delta,
        "sequence": v.sequence,
        "ts_out": v.ts_out,
    },
    "MboObservation": lambda v: {
        "rtype": v.rtype,
        "publisher_id": v.publisher_id,
        "instrument_id": v.instrument_id,
        "ts_event": v.ts_event,
        "order_id": v.order_id,
        "price": v.price,
        "size": v.size,
        "action": v.action,
        "side": v.side,
        "ts_recv": v.ts_recv,
        "flags": v.flags,
        "channel_id": v.channel_id,
        "ts_in_delta": v.ts_in_delta,
        "sequence": v.sequence,
        "ts_out_observed": v.ts_out_observed,
        "record_size_observed": v.record_size_observed,
        "ts_index_observed": v.ts_index_observed,
    },
    "Context": lambda v: {
        "profile_id": v.profile_id,
        "member_compression": v.member_compression,
        "input_version": v.input_version,
        "upgrade_policy": v.upgrade_policy,
        "expected_ts_out": v.expected_ts_out,
    },
    "DecodedOccurrence": lambda v: {
        "decoded_position": v.decoded_position,
        "kind": v.kind,
        "wire_span_ordinal": v.wire_span_ordinal,
        "projection": v.projection,
        "projection_sha256": v.projection_sha256,
    },
    "FrameSpan": lambda v: {
        "frame_ordinal": v.frame_ordinal,
        "compressed_start": v.compressed_start,
        "compressed_end": v.compressed_end,
        "decompressed_start": v.decompressed_start,
        "decompressed_end": v.decompressed_end,
        "compressed_span_sha256": v.compressed_span_sha256,
        "decompressed_span_sha256": v.decompressed_span_sha256,
    },
    "ZstdFramingReport": lambda v: {
        "compressed_bytes": v.compressed_bytes,
        "compressed_sha256": v.compressed_sha256,
        "decompressed_bytes": v.decompressed_bytes,
        "decompressed_sha256": v.decompressed_sha256,
        "frames": v.frames,
        "report_sha256": v.report_sha256,
    },
    "WireSpan": lambda v: {
        "wire_span_ordinal": v.wire_span_ordinal,
        "kind": v.kind,
        "decompressed_start": v.decompressed_start,
        "decompressed_end": v.decompressed_end,
        "wire_sha256": v.wire_sha256,
        "wire_fields": v.wire_fields,
        "wire_fields_sha256": v.wire_fields_sha256,
    },
    "DbnFramingReport": lambda v: {
        "decompressed_bytes": v.decompressed_bytes,
        "decompressed_sha256": v.decompressed_sha256,
        "spans": v.spans,
        "report_sha256": v.report_sha256,
    },
    "TerminalEvidence": lambda v: {
        "compressed_bytes": v.compressed_bytes,
        "compressed_sha256": v.compressed_sha256,
        "decompressed_bytes": v.decompressed_bytes,
        "decompressed_sha256": v.decompressed_sha256,
        "frame_count": v.frame_count,
        "decoded_positions": v.decoded_positions,
        "metadata_count": v.metadata_count,
        "mbo_count": v.mbo_count,
        "dbn_remaining_buffer_bytes": v.dbn_remaining_buffer_bytes,
        "zstd_framing_sha256": v.zstd_framing_sha256,
        "dbn_framing_sha256": v.dbn_framing_sha256,
        "framing_status": v.framing_status,
        "zstd_status": v.zstd_status,
    },
    "Interpreter": lambda v: {
        "implementation": v.implementation,
        "version": v.version,
        "executable_sha256": v.executable_sha256,
    },
    "Package": lambda v: {
        "name": v.name,
        "version": v.version,
        "metadata_sha256": v.metadata_sha256,
    },
    "Artifact": lambda v: {
        "logical_id": v.logical_id,
        "kind": v.kind,
        "raw_bytes": v.raw_bytes,
        "raw_sha256": v.raw_sha256,
    },
    "RuntimeManifest": lambda v: {
        "schema": v.schema,
        "interpreter": v.interpreter,
        "packages": v.packages,
        "artifacts": v.artifacts,
    },
    "MemberDecodeEvidence": lambda v: {
        "status": v.status,
        "protocol_sha256": v.protocol_sha256,
        "profile_sha256": v.profile_sha256,
        "runtime_manifest": v.runtime_manifest,
        "runtime_manifest_sha256": v.runtime_manifest_sha256,
        "context_sha256": v.context_sha256,
        "member_sha256": v.member_sha256,
        "metadata_sha256": v.metadata_sha256,
        "occurrences": v.occurrences,
        "zstd_framing": v.zstd_framing,
        "dbn_framing": v.dbn_framing,
        "terminal": v.terminal,
        "authorities": v.authorities,
        "evidence_sha256": v.evidence_sha256,
    },
}

_BUILDERS = {
    "SchemaMbo": lambda v: SchemaMbo(v["kind"], v["class_name"], v["name"], v["code"], v["text"]),
    "RtypeMbo": lambda v: RtypeMbo(v["kind"], v["class_name"], v["name"], v["code"], v["text"]),
    "SType": lambda v: SType(v["kind"], v["class_name"], v["name"], v["code"], v["text"]),
    "Action": lambda v: Action(v["kind"], v["class_name"], v["name"], v["code"], v["text"]),
    "Side": lambda v: Side(v["kind"], v["class_name"], v["name"], v["code"], v["text"]),
    "UnknownChar": lambda v: UnknownChar(v["kind"], v["value"]),
    "PythonDate": lambda v: PythonDate(v["kind"], v["year"], v["month"], v["day"]),
    "WireMappingInterval": lambda v: WireMappingInterval(
        v["start_date"], v["end_date"], v["symbol"]
    ),
    "MappingInterval": lambda v: MappingInterval(v["start_date"], v["end_date"], v["symbol"]),
    "MappingGroup": lambda v: MappingGroup(v["raw_symbol"], v["intervals"]),
    "WireMappingGroup": lambda v: WireMappingGroup(
        v["raw_symbol"], v["interval_count"], v["intervals"]
    ),
    "MetadataWireBody": lambda v: MetadataWireBody(
        v["magic_hex"],
        v["version"],
        v["length_body"],
        v["dataset"],
        v["dataset_cstr_bytes"],
        v["schema"],
        v["start"],
        v["end"],
        v["limit"],
        v["stype_in"],
        v["stype_out"],
        v["ts_out"],
        v["symbol_cstr_len"],
        v["reserved_bytes"],
        v["schema_definition_length"],
        v["symbols_count"],
        v["symbols"],
        v["partial_count"],
        v["partial"],
        v["not_found_count"],
        v["not_found"],
        v["mappings_count"],
        v["mappings"],
        v["alignment_padding_bytes"],
    ),
    "MetadataProjection": lambda v: MetadataProjection(
        v["version"],
        v["dataset"],
        v["schema"],
        v["start"],
        v["end_observed"],
        v["limit_observed"],
        v["stype_in"],
        v["stype_out"],
        v["ts_out"],
        v["symbol_cstr_len"],
        v["symbols"],
        v["partial"],
        v["not_found"],
        v["mappings"],
    ),
    "MboWireBody": lambda v: MboWireBody(
        v["length_words"],
        v["rtype"],
        v["publisher_id"],
        v["instrument_id"],
        v["ts_event"],
        v["order_id"],
        v["price"],
        v["size"],
        v["flags"],
        v["channel_id"],
        v["action"],
        v["side"],
        v["ts_recv"],
        v["ts_in_delta"],
        v["sequence"],
        v["ts_out"],
    ),
    "MboObservation": lambda v: MboObservation(
        v["rtype"],
        v["publisher_id"],
        v["instrument_id"],
        v["ts_event"],
        v["order_id"],
        v["price"],
        v["size"],
        v["action"],
        v["side"],
        v["ts_recv"],
        v["flags"],
        v["channel_id"],
        v["ts_in_delta"],
        v["sequence"],
        v["ts_out_observed"],
        v["record_size_observed"],
        v["ts_index_observed"],
    ),
    "Context": lambda v: MemberDecodeContext(
        v["profile_id"],
        v["member_compression"],
        v["input_version"],
        v["upgrade_policy"],
        v["expected_ts_out"],
    ),
    "DecodedOccurrence": lambda v: DecodedOccurrence(
        v["decoded_position"],
        v["kind"],
        v["wire_span_ordinal"],
        v["projection"],
        v["projection_sha256"],
    ),
    "FrameSpan": lambda v: FrameSpan(
        v["frame_ordinal"],
        v["compressed_start"],
        v["compressed_end"],
        v["decompressed_start"],
        v["decompressed_end"],
        v["compressed_span_sha256"],
        v["decompressed_span_sha256"],
    ),
    "ZstdFramingReport": lambda v: ZstdFramingReport(
        v["compressed_bytes"],
        v["compressed_sha256"],
        v["decompressed_bytes"],
        v["decompressed_sha256"],
        v["frames"],
        v["report_sha256"],
    ),
    "WireSpan": lambda v: WireSpan(
        v["wire_span_ordinal"],
        v["kind"],
        v["decompressed_start"],
        v["decompressed_end"],
        v["wire_sha256"],
        v["wire_fields"],
        v["wire_fields_sha256"],
    ),
    "DbnFramingReport": lambda v: DbnFramingReport(
        v["decompressed_bytes"], v["decompressed_sha256"], v["spans"], v["report_sha256"]
    ),
    "TerminalEvidence": lambda v: TerminalEvidence(
        v["compressed_bytes"],
        v["compressed_sha256"],
        v["decompressed_bytes"],
        v["decompressed_sha256"],
        v["frame_count"],
        v["decoded_positions"],
        v["metadata_count"],
        v["mbo_count"],
        v["dbn_remaining_buffer_bytes"],
        v["zstd_framing_sha256"],
        v["dbn_framing_sha256"],
        v["framing_status"],
        v["zstd_status"],
    ),
    "Interpreter": lambda v: Interpreter(v["implementation"], v["version"], v["executable_sha256"]),
    "Package": lambda v: Package(v["name"], v["version"], v["metadata_sha256"]),
    "Artifact": lambda v: Artifact(v["logical_id"], v["kind"], v["raw_bytes"], v["raw_sha256"]),
    "RuntimeManifest": lambda v: RuntimeManifest(
        v["schema"], v["interpreter"], v["packages"], v["artifacts"]
    ),
    "MemberDecodeEvidence": lambda v: MemberDecodeEvidence(
        v["status"],
        v["protocol_sha256"],
        v["profile_sha256"],
        v["runtime_manifest"],
        v["runtime_manifest_sha256"],
        v["context_sha256"],
        v["member_sha256"],
        v["metadata_sha256"],
        v["occurrences"],
        v["zstd_framing"],
        v["dbn_framing"],
        v["terminal"],
        v["authorities"],
        v["evidence_sha256"],
    ),
}


_PROTOCOL_SHA = "baef653d21535c864a889e1299332b1b182421cbd154cd3247d81705f10133e1"
_PROFILE_SHA = "5016b1dc56537fdefdac74e56154ceb410307f3677fb08d8455cba8f54c86b0d"
_PROFILE_RAW_SHA = "531b9a22fdba2e948c3e0e7a7ec37760c1c0ebc8e1c37b91ce1d929d9c8a6fb1"
_RUNTIME_SHA = "4aab559ab26a25cf35579dc723cb00d06db933ea65c63d9793a34939191c2ec3"
_TOKEN = re.compile(
    r'\s+|"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"'
    r"|-?(?:0|[1-9][0-9]*)|true|false|null|[{}\[\],:]"
)


def _require(condition, message="invalid native-member evidence"):
    if not condition:
        raise ValueError(message)


def _canonical_tree(value, depth=1):
    _require(depth <= 64, "canonical depth exceeds limit")
    kind = type(value)
    if kind is dict:
        _require(all(type(k) is str for k in value), "non-string canonical key")
        for item in value.values():
            _canonical_tree(item, depth + 1)
    elif kind in (list, tuple):
        for item in value:
            _canonical_tree(item, depth + 1)
    else:
        _require(kind in (str, int, bool, type(None)), "noncanonical value")


def canonical_bytes(body):
    _canonical_tree(body)
    try:
        return json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")
    except (UnicodeError, TypeError, OverflowError) as exc:
        raise ValueError("noncanonical body") from exc


def body_sha256(body):
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def _pairs(pairs):
    answer = {}
    for key, value in pairs:
        _require(key not in answer, "duplicate JSON key")
        answer[key] = value
    return answer


def strict_json_loads(raw, maximum=4194304, nodes=1048576):
    """Bound lexical structure before allocating a JSON object tree."""
    _require(type(raw) is bytes and 0 < len(raw) <= maximum, "JSON byte limit")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ValueError("invalid JSON UTF-8") from exc
    _require(not text.startswith("\ufeff"), "JSON BOM refused")
    offset, depth, count = 0, 0, 0
    while offset < len(text):
        match = _TOKEN.match(text, offset)
        _require(match is not None, "invalid JSON token")
        token = match.group()
        offset = match.end()
        if token.isspace() or token in (",", ":"):
            continue
        if token in ("{", "["):
            depth += 1
            count += 1
            _require(depth <= 64, "JSON depth limit")
        elif token in ("}", "]"):
            depth -= 1
            _require(depth >= 0, "invalid JSON nesting")
        else:
            count += 1
            _require(depth + 1 <= 64, "JSON depth limit")
            if token[0] == "-" or token[0].isdigit():
                _require(len(token.lstrip("-")) <= 20, "JSON integer token limit")
        _require(count <= nodes, "JSON node limit")
    _require(depth == 0, "unclosed JSON structure")
    try:
        body = json.loads(text, object_pairs_hook=_pairs)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid complete JSON") from exc
    _require(canonical_bytes(body) == raw, "noncanonical JSON encoding")
    return body


def _resource(name, expected, maximum=4194304):
    _require(name in ("_native_member_protocol_v1.json", "_native_member_profile_20261012.json"))
    path = Path(__file__).with_name(name)
    _require(not path.is_symlink(), "linked installation resource")
    with path.open("rb") as source:
        raw = source.read(maximum + 1)
    _require(
        len(raw) <= maximum and hashlib.sha256(raw).hexdigest() == expected,
        "fixed resource identity mismatch",
    )
    return strict_json_loads(raw, maximum)


def protocol_body():
    return _resource("_native_member_protocol_v1.json", _PROTOCOL_SHA)


def profile_body():
    envelope = _resource("_native_member_profile_20261012.json", _PROFILE_RAW_SHA)
    _require(type(envelope) is dict and set(envelope) == {"profile_body", "profile_sha256"})
    body = envelope["profile_body"]
    _require(envelope["profile_sha256"] == _PROFILE_SHA and body_sha256(body) == _PROFILE_SHA)
    _require(body["public_schemas"] == protocol_body(), "profile protocol differs")
    _require(body_sha256(body["runtime_manifest"]) == _RUNTIME_SHA)
    return body


def _date(value):
    try:
        date(value["year"], value["month"], value["day"])
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid Gregorian date") from exc


def _wire_date(value):
    result = {
        "kind": "python_date",
        "year": value // 10000,
        "month": value // 100 % 100,
        "day": value % 100,
    }
    _date(result)
    return result


def _enum_body(schemas, name, code):
    for row in schemas[name]["allowed_rows"]:
        if row[1] == code:
            return {
                "kind": "native_enum",
                "class_name": schemas[name]["fixed_values"]["class_name"],
                "name": row[0],
                "code": row[1],
                "text": row[2],
            }
    if name in ("Action", "Side"):
        return {"kind": "str", "value": chr(code)}
    raise ValueError("unknown registered enum code")


def wire_projection(kind, body):
    """Exact source-defined wire-to-logical translation, not native observation."""
    schemas = protocol_body()["schemas"]
    if kind == "Metadata":
        mappings = [
            {
                "raw_symbol": group["raw_symbol"],
                "intervals": [
                    {
                        "start_date": _wire_date(item["start_date"]),
                        "end_date": _wire_date(item["end_date"]),
                        "symbol": item["symbol"],
                    }
                    for item in group["intervals"]
                ],
            }
            for group in body["mappings"]
        ]
        return {
            "version": body["version"],
            "dataset": body["dataset"],
            "schema": _enum_body(schemas, "SchemaMbo", body["schema"]),
            "start": body["start"],
            "end_observed": None if body["end"] in (0, 18446744073709551615) else body["end"],
            "limit_observed": None if body["limit"] == 0 else body["limit"],
            "stype_in": None
            if body["stype_in"] == 255
            else _enum_body(schemas, "SType", body["stype_in"]),
            "stype_out": _enum_body(schemas, "SType", body["stype_out"]),
            "ts_out": body["ts_out"] == 1,
            "symbol_cstr_len": body["symbol_cstr_len"],
            "symbols": body["symbols"],
            "partial": body["partial"],
            "not_found": body["not_found"],
            "mappings": sorted(mappings, key=lambda group: group["raw_symbol"]),
        }
    _require(kind == "MBO")
    return {
        "rtype": _enum_body(schemas, "RtypeMbo", body["rtype"]),
        "publisher_id": body["publisher_id"],
        "instrument_id": body["instrument_id"],
        "ts_event": body["ts_event"],
        "order_id": body["order_id"],
        "price": body["price"],
        "size": body["size"],
        "action": _enum_body(schemas, "Action", body["action"]),
        "side": _enum_body(schemas, "Side", body["side"]),
        "ts_recv": body["ts_recv"],
        "flags": body["flags"],
        "channel_id": body["channel_id"],
        "ts_in_delta": body["ts_in_delta"],
        "sequence": body["sequence"],
        "ts_out_observed": 18446744073709551615 if body["ts_out"] is None else body["ts_out"],
        "record_size_observed": 4 * body["length_words"],
        "ts_index_observed": body["ts_recv"],
    }


def _validate(name, value, schemas, depth=1):
    _require(depth <= 64 and name in schemas, "unknown/deep schema")
    schema = schemas[name]
    kind = schema["kind"]
    if kind == "int":
        _require(
            type(value) is int
            and int(schema["minimum_decimal"]) <= value <= int(schema["maximum_decimal"]),
            "integer type/domain",
        )
    elif kind == "bool":
        _require(type(value) is bool, "boolean type")
    elif kind == "literal":
        literal = schema["value"]
        _require(type(value) is type(literal) and value == literal, "literal type/value")
    elif kind == "enum":
        expected_type = {"str": str, "int": int}[schema["exact_type"]]
        _require(type(value) is expected_type and value in schema["values"], "enum type/value")
    elif kind == "str":
        _require(type(value) is str, "text type")
        try:
            encoded = value.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ValueError("invalid text encoding") from exc
        _require(not schema.get("ascii") or value.isascii(), "ASCII text required")
        _require("pattern" not in schema or re.fullmatch(schema["pattern"], value) is not None)
        _require(len(encoded) <= schema.get("maximum_encoded_bytes", 4194304))
        _require(schema.get("nul") != "forbidden" or "\x00" not in value)
        _require(
            schema.get("minimum_characters", 0)
            <= len(value)
            <= schema.get("maximum_characters", 4194304)
        )
        if "maximum_codepoint" in schema:
            _require(
                all(
                    schema["minimum_codepoint"] <= ord(c) <= schema["maximum_codepoint"]
                    for c in value
                )
            )
    elif kind == "record":
        _require(type(value) is dict and all(type(k) is str for k in value), "record body type")
        _require(set(value) == {field for field, _ in schema["fields"]}, "record fields")
        for field, reference in schema["fields"]:
            _validate(reference, value[field], schemas, depth + 1)
        for field, fixed in schema.get("fixed_values", {}).items():
            _require(
                type(value[field]) is type(fixed) and value[field] == fixed, "fixed record value"
            )
        if "allowed_rows" in schema:
            _require(
                [value[f] for f in schema["row_fields"]] in schema["allowed_rows"],
                "mixed or unknown registered row",
            )
    elif kind == "tuple":
        _require(
            type(value) is list
            and schema["minimum_items"] <= len(value) <= schema["maximum_items"],
            "complete collection type/count",
        )
        for item in value:
            _validate(schema["item"], item, schemas, depth + 1)
    elif kind == "fixed_tuple":
        _require(type(value) is list, "fixed collection type")
        if "literal_items" in schema:
            _require(len(value) == len(schema["literal_items"]))
            _require(
                all(
                    type(v) is type(f) and v == f
                    for v, f in zip(value, schema["literal_items"], strict=True)
                )
            )
        else:
            _require(len(value) == len(schema["items"]))
            for item, reference in zip(value, schema["items"], strict=True):
                _validate(reference, item, schemas, depth + 1)
    elif kind == "union":
        for reference in schema["alternatives"]:
            try:
                _validate(reference, value, schemas, depth + 1)
            except ValueError:
                continue
            break
        else:
            raise ValueError("unknown union alternative")
    else:
        raise ValueError("unknown schema kind")
    _cross(name, value, schemas)


def _cross(name, v, schemas):
    if name == "PythonDate":
        _date(v)
    elif name == "WireDate":
        _wire_date(v)
    elif name in ("ActionObservation", "SideObservation") and v["kind"] == "str":
        target = "Action" if name == "ActionObservation" else "Side"
        _require(ord(v["value"]) not in {r[1] for r in schemas[target]["allowed_rows"]})
    elif name == "WireMappingGroup":
        _require(v["interval_count"] == len(v["intervals"]))
    elif name in ("MappingGroups", "WireMappingGroups"):
        names = [g["raw_symbol"] for g in v]
        _require(len(set(names)) == len(names) and sum(len(g["intervals"]) for g in v) <= 32)
        if name == "MappingGroups":
            _require(names == sorted(names), "logical mapping order")
    elif name == "MetadataWireBody":
        for field in ("symbols", "partial", "not_found", "mappings"):
            _require(v[field + "_count"] == len(v[field]))
        dynamic = 71 * sum(len(v[f]) for f in ("symbols", "partial", "not_found"))
        dynamic += sum(75 + 79 * len(g["intervals"]) for g in v["mappings"])
        padding = (-(128 + dynamic)) % 8
        _require(
            len(v["alignment_padding_bytes"]) == padding
            and v["length_body"] == 120 + dynamic + padding
        )
    elif name == "MboWireBody":
        _require(v["length_words"] == (14 if v["ts_out"] is None else 16))
    elif name == "MboObservation":
        _require(v["ts_index_observed"] == v["ts_recv"])
    elif name == "DecodedOccurrence":
        projection_name = "MetadataProjection" if v["kind"] == "Metadata" else "MboObservation"
        _validate(projection_name, v["projection"], schemas)
        _require(body_sha256(v["projection"]) == v["projection_sha256"])
    elif name in ("Occurrences", "WireSpans"):
        ordinal = "decoded_position" if name == "Occurrences" else "wire_span_ordinal"
        for index, item in enumerate(v, 1):
            _require(
                item[ordinal] == index and item["kind"] == ("Metadata" if index == 1 else "MBO")
            )
            if name == "Occurrences":
                _require(item["wire_span_ordinal"] == index)
            else:
                _require(
                    item["decompressed_start"]
                    == (0 if index == 1 else v[index - 2]["decompressed_end"])
                )
    elif name == "FrameSpan":
        _require(
            v["compressed_start"] < v["compressed_end"]
            and v["decompressed_start"] < v["decompressed_end"]
        )
    elif name == "Frames":
        for index, item in enumerate(v, 1):
            _require(item["frame_ordinal"] == index)
            for space in ("compressed", "decompressed"):
                _require(
                    item[space + "_start"] == (0 if index == 1 else v[index - 2][space + "_end"])
                )
    elif name in ("ZstdFramingReport", "DbnFramingReport"):
        _require(
            body_sha256({k: x for k, x in v.items() if k != "report_sha256"}) == v["report_sha256"]
        )
        if name == "ZstdFramingReport":
            _require(v["frames"][-1]["compressed_end"] == v["compressed_bytes"])
            _require(v["frames"][-1]["decompressed_end"] == v["decompressed_bytes"])
        else:
            _require(v["spans"][-1]["decompressed_end"] == v["decompressed_bytes"])
    elif name == "WireSpan":
        wire_name = "MetadataWireBody" if v["kind"] == "Metadata" else "MboWireBody"
        _validate(wire_name, v["wire_fields"], schemas)
        _require(v["wire_fields_sha256"] == body_sha256(v["wire_fields"]))
        length = (
            v["wire_fields"]["length_body"] + 8
            if v["kind"] == "Metadata"
            else v["wire_fields"]["length_words"] * 4
        )
        _require(v["decompressed_end"] - v["decompressed_start"] == length)
    elif name == "Authorities":
        _require([item[0] for item in v] == schemas["AuthorityName"]["values"])
    elif name == "Packages":
        _require([item["name"] for item in v] == ["databento-dbn", "zstandard"])
    elif name == "Artifacts":
        _require(
            [item["logical_id"] for item in v]
            == [row[0] for row in schemas["Artifact"]["allowed_rows"]]
        )
    elif name == "TerminalEvidence":
        _require(v["mbo_count"] == v["decoded_positions"] - 1)
    elif name == "MemberDecodeEvidence":
        _evidence_cross(v)


def _evidence_cross(v):
    _require(v["protocol_sha256"] == _PROTOCOL_SHA and v["profile_sha256"] == _PROFILE_SHA)
    _require(v["runtime_manifest_sha256"] == _RUNTIME_SHA == body_sha256(v["runtime_manifest"]))
    zstd, dbn, terminal = v["zstd_framing"], v["dbn_framing"], v["terminal"]
    _require(v["member_sha256"] == zstd["compressed_sha256"] == terminal["compressed_sha256"])
    _require(zstd["compressed_bytes"] == terminal["compressed_bytes"])
    _require(
        zstd["decompressed_bytes"] == dbn["decompressed_bytes"] == terminal["decompressed_bytes"]
    )
    _require(
        zstd["decompressed_sha256"] == dbn["decompressed_sha256"] == terminal["decompressed_sha256"]
    )
    _require(zstd["report_sha256"] == terminal["zstd_framing_sha256"])
    _require(dbn["report_sha256"] == terminal["dbn_framing_sha256"])
    _require(terminal["frame_count"] == len(zstd["frames"]))
    _require(terminal["decoded_positions"] == len(v["occurrences"]) == len(dbn["spans"]))
    _require(v["metadata_sha256"] == v["occurrences"][0]["projection_sha256"])
    mode = v["occurrences"][0]["projection"]["ts_out"]
    for occurrence, span in zip(v["occurrences"], dbn["spans"], strict=True):
        _require(occurrence["projection"] == wire_projection(span["kind"], span["wire_fields"]))
        if span["kind"] == "MBO":
            _require((span["wire_fields"]["ts_out"] is not None) is mode)
    body = {k: x for k, x in v.items() if k != "evidence_sha256"}
    _require(len(canonical_bytes(body)) <= 1048576, "complete evidence body limit")
    _require(body_sha256(body) == v["evidence_sha256"])


def validate_body(schema_name, body):
    _validate(schema_name, body, protocol_body()["schemas"])


def _project(name, value, schemas):
    schema = schemas[name]
    if schema["kind"] == "record":
        _require(type(value) is _RECORDS[name], "exact registered record required")
        raw = _PROJECTORS[name](value)
        return {field: _project(ref, raw[field], schemas) for field, ref in schema["fields"]}
    if schema["kind"] == "tuple":
        _require(type(value) is tuple, "exact tuple required")
        _require(schema["minimum_items"] <= len(value) <= schema["maximum_items"])
        return [_project(schema["item"], item, schemas) for item in value]
    if schema["kind"] == "fixed_tuple":
        _require(type(value) is tuple, "exact fixed tuple required")
        if "literal_items" in schema:
            return list(value)
        _require(len(value) == len(schema["items"]))
        return [
            _project(ref, item, schemas) for ref, item in zip(schema["items"], value, strict=True)
        ]
    if schema["kind"] == "union":
        for ref in schema["alternatives"]:
            try:
                answer = _project(ref, value, schemas)
                _validate(ref, answer, schemas)
            except ValueError:
                continue
            return answer
        raise ValueError("unknown exact union alternative")
    _validate(name, value, schemas)
    return value


def project(schema_name, typed):
    schemas = protocol_body()["schemas"]
    _require(schema_name in schemas)
    body = _project(schema_name, typed, schemas)
    _validate(schema_name, body, schemas)
    return body


def _from_body(name, value, schemas):
    schema = schemas[name]
    if schema["kind"] == "record":
        converted = {
            field: _from_body(ref, value[field], schemas) for field, ref in schema["fields"]
        }
        return _BUILDERS[name](converted)
    if schema["kind"] == "tuple":
        return tuple(_from_body(schema["item"], item, schemas) for item in value)
    if schema["kind"] == "fixed_tuple":
        if "literal_items" in schema:
            return tuple(value)
        return tuple(
            _from_body(ref, item, schemas) for ref, item in zip(schema["items"], value, strict=True)
        )
    if schema["kind"] == "union":
        for ref in schema["alternatives"]:
            try:
                _validate(ref, value, schemas)
            except ValueError:
                continue
            return _from_body(ref, value, schemas)
        raise ValueError("unknown body union")
    return value


def from_body(schema_name, body):
    schemas = protocol_body()["schemas"]
    _validate(schema_name, body, schemas)
    return _from_body(schema_name, body, schemas)
