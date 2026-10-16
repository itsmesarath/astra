"""Independent complete declarations from the held provider specification.

The protocol is the entire normative annex literal, guarded by its raw pin.
Nothing in this module imports production code or a native package. Byte
fixtures use the annex's explicit wire offsets and literal raw Zstd blocks.
"""

import hashlib
import json
from pathlib import Path

ANNEX_SHA256 = "7a97af1f024fadf1e87fbafaf6acb5838d059ce2976bc9be07bc735dfc398d79"
PROFILE_SHA256 = "5016b1dc56537fdefdac74e56154ceb410307f3677fb08d8455cba8f54c86b0d"
RUNTIME_SHA256 = "4aab559ab26a25cf35579dc723cb00d06db933ea65c63d9793a34939191c2ec3"
PROFILE_ID = "dbn_v3_asis_zstd_cext_invented_20261012_v1"
ROOT = Path(__file__).resolve().parents[1]

RECORD_FIELDS = {
    "SchemaMbo": ("kind", "class_name", "name", "code", "text"),
    "RtypeMbo": ("kind", "class_name", "name", "code", "text"),
    "SType": ("kind", "class_name", "name", "code", "text"),
    "Action": ("kind", "class_name", "name", "code", "text"),
    "Side": ("kind", "class_name", "name", "code", "text"),
    "UnknownChar": ("kind", "value"),
    "PythonDate": ("kind", "year", "month", "day"),
    "WireMappingInterval": ("start_date", "end_date", "symbol"),
    "MappingInterval": ("start_date", "end_date", "symbol"),
    "MappingGroup": ("raw_symbol", "intervals"),
    "WireMappingGroup": ("raw_symbol", "interval_count", "intervals"),
    "MetadataWireBody": (
        "magic_hex",
        "version",
        "length_body",
        "dataset",
        "dataset_cstr_bytes",
        "schema",
        "start",
        "end",
        "limit",
        "stype_in",
        "stype_out",
        "ts_out",
        "symbol_cstr_len",
        "reserved_bytes",
        "schema_definition_length",
        "symbols_count",
        "symbols",
        "partial_count",
        "partial",
        "not_found_count",
        "not_found",
        "mappings_count",
        "mappings",
        "alignment_padding_bytes",
    ),
    "MetadataProjection": (
        "version",
        "dataset",
        "schema",
        "start",
        "end_observed",
        "limit_observed",
        "stype_in",
        "stype_out",
        "ts_out",
        "symbol_cstr_len",
        "symbols",
        "partial",
        "not_found",
        "mappings",
    ),
    "MboWireBody": (
        "length_words",
        "rtype",
        "publisher_id",
        "instrument_id",
        "ts_event",
        "order_id",
        "price",
        "size",
        "flags",
        "channel_id",
        "action",
        "side",
        "ts_recv",
        "ts_in_delta",
        "sequence",
        "ts_out",
    ),
    "MboObservation": (
        "rtype",
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
        "ts_out_observed",
        "record_size_observed",
        "ts_index_observed",
    ),
    "MemberDecodeContext": (
        "profile_id",
        "member_compression",
        "input_version",
        "upgrade_policy",
        "expected_ts_out",
    ),
    "DecodedOccurrence": (
        "decoded_position",
        "kind",
        "wire_span_ordinal",
        "projection",
        "projection_sha256",
    ),
    "FrameSpan": (
        "frame_ordinal",
        "compressed_start",
        "compressed_end",
        "decompressed_start",
        "decompressed_end",
        "compressed_span_sha256",
        "decompressed_span_sha256",
    ),
    "ZstdFramingReport": (
        "compressed_bytes",
        "compressed_sha256",
        "decompressed_bytes",
        "decompressed_sha256",
        "frames",
        "report_sha256",
    ),
    "WireSpan": (
        "wire_span_ordinal",
        "kind",
        "decompressed_start",
        "decompressed_end",
        "wire_sha256",
        "wire_fields",
        "wire_fields_sha256",
    ),
    "DbnFramingReport": ("decompressed_bytes", "decompressed_sha256", "spans", "report_sha256"),
    "TerminalEvidence": (
        "compressed_bytes",
        "compressed_sha256",
        "decompressed_bytes",
        "decompressed_sha256",
        "frame_count",
        "decoded_positions",
        "metadata_count",
        "mbo_count",
        "dbn_remaining_buffer_bytes",
        "zstd_framing_sha256",
        "dbn_framing_sha256",
        "framing_status",
        "zstd_status",
    ),
    "Interpreter": ("implementation", "version", "executable_sha256"),
    "Package": ("name", "version", "metadata_sha256"),
    "Artifact": ("logical_id", "kind", "raw_bytes", "raw_sha256"),
    "RuntimeManifest": ("schema", "interpreter", "packages", "artifacts"),
    "MemberDecodeEvidence": (
        "status",
        "protocol_sha256",
        "profile_sha256",
        "runtime_manifest",
        "runtime_manifest_sha256",
        "context_sha256",
        "member_sha256",
        "metadata_sha256",
        "occurrences",
        "zstd_framing",
        "dbn_framing",
        "terminal",
        "authorities",
        "evidence_sha256",
    ),
}


def canonical(body):
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def digest(body):
    return hashlib.sha256(canonical(body)).hexdigest()


def raw_digest(body):
    return hashlib.sha256(body).hexdigest()


def protocol_literal():
    data = (ROOT / "docs/6E_NATIVE_PROFILE_SCHEMA_ANNEX_20261012.md").read_bytes()
    assert hashlib.sha256(data).hexdigest() == ANNEX_SHA256
    text = data.decode("utf-8")
    section = text.split("## Full public protocol body — PUBLIC_PROTOCOL_JSON", 1)[1]
    complete_literal = section.split("```json", 1)[1].split("```", 1)[0]
    result = json.loads(complete_literal)
    assert len(result["schemas"]) == 117
    return result


def context_body(ts_out=False):
    return {
        "profile_id": PROFILE_ID,
        "member_compression": "ZSTD_CONCAT",
        "input_version": 3,
        "upgrade_policy": "AS_IS",
        "expected_ts_out": ts_out,
    }


def expected_pins(member=b"invented-preflight-input"):
    return {
        "expected_protocol_sha256": digest(protocol_literal()),
        "expected_profile_sha256": PROFILE_SHA256,
        "expected_runtime_manifest_sha256": RUNTIME_SHA256,
        "expected_member_sha256": raw_digest(member),
        "expected_metadata_sha256": "e" * 64,
    }


def invented_raw_member(ts_out=False):
    """Independently laid out minimal header and two differently keyed MBOs."""
    header = bytearray(128)
    header[0:3] = b"DBN"
    header[3] = 3
    header[4:8] = (120).to_bytes(4, "little")
    header[8:18] = b"GLBX.MDP3\x00"
    header[26:34] = (100).to_bytes(8, "little")
    header[34:42] = ((1 << 64) - 1).to_bytes(8, "little")
    header[50:53] = bytes((1, 0, int(ts_out)))
    header[53:55] = (71).to_bytes(2, "little")
    records = []
    for instrument, order, price, event, received, action, side in (
        (1, 101, -125, 300, 290, 65, 66),
        (999, 102, 250, 200, 400, 84, 65),
    ):
        record = bytearray(64 if ts_out else 56)
        record[0:2] = bytes((16 if ts_out else 14, 160))
        record[2:4] = (7).to_bytes(2, "little")
        record[4:8] = instrument.to_bytes(4, "little")
        record[8:16] = event.to_bytes(8, "little")
        record[16:24] = order.to_bytes(8, "little")
        record[24:32] = price.to_bytes(8, "little", signed=True)
        record[32:36] = (3).to_bytes(4, "little")
        record[36:40] = bytes((128, 2, action, side))
        record[40:48] = received.to_bytes(8, "little")
        record[48:52] = (-9).to_bytes(4, "little", signed=True)
        record[52:56] = (17).to_bytes(4, "little")
        if ts_out:
            record[56:64] = ((1 << 64) - 2).to_bytes(8, "little")
        records.append(bytes(record))
    return bytes(header) + b"".join(records)


def raw_zstd_frame(raw):
    """Literal single-segment raw-block framing, not a native encoder."""
    length = len(raw)
    if length < 256:
        content_header = b"\x20" + bytes((length,))
    else:
        content_header = b"\x60" + (length - 256).to_bytes(2, "little")
    return b"\x28\xb5\x2f\xfd" + content_header + ((length << 3) | 1).to_bytes(3, "little") + raw


def minimal_evidence_body(ts_out=False):
    """Full expected public body, separately declared from input byte assembly."""
    protocol = protocol_literal()
    raw = invented_raw_member(ts_out)
    member = raw_zstd_frame(raw)
    metadata = {
        "version": 3,
        "dataset": "GLBX.MDP3",
        "schema": {
            "kind": "native_enum",
            "class_name": "Schema",
            "name": "MBO",
            "code": 0,
            "text": "mbo",
        },
        "start": 100,
        "end_observed": None,
        "limit_observed": None,
        "stype_in": {
            "kind": "native_enum",
            "class_name": "SType",
            "name": "RAW_SYMBOL",
            "code": 1,
            "text": "raw_symbol",
        },
        "stype_out": {
            "kind": "native_enum",
            "class_name": "SType",
            "name": "INSTRUMENT_ID",
            "code": 0,
            "text": "instrument_id",
        },
        "ts_out": ts_out,
        "symbol_cstr_len": 71,
        "symbols": [],
        "partial": [],
        "not_found": [],
        "mappings": [],
    }
    wire_metadata = {
        "magic_hex": "44424e",
        "version": 3,
        "length_body": 120,
        "dataset": "GLBX.MDP3",
        "dataset_cstr_bytes": 16,
        "schema": 0,
        "start": 100,
        "end": (1 << 64) - 1,
        "limit": 0,
        "stype_in": 1,
        "stype_out": 0,
        "ts_out": int(ts_out),
        "symbol_cstr_len": 71,
        "reserved_bytes": [0] * 53,
        "schema_definition_length": 0,
        "symbols_count": 0,
        "symbols": [],
        "partial_count": 0,
        "partial": [],
        "not_found_count": 0,
        "not_found": [],
        "mappings_count": 0,
        "mappings": [],
        "alignment_padding_bytes": [],
    }
    wire_mbos = [
        {
            "length_words": 16 if ts_out else 14,
            "rtype": 160,
            "publisher_id": 7,
            "instrument_id": 1,
            "ts_event": 300,
            "order_id": 101,
            "price": -125,
            "size": 3,
            "flags": 128,
            "channel_id": 2,
            "action": 65,
            "side": 66,
            "ts_recv": 290,
            "ts_in_delta": -9,
            "sequence": 17,
            "ts_out": (1 << 64) - 2 if ts_out else None,
        },
        {
            "length_words": 16 if ts_out else 14,
            "rtype": 160,
            "publisher_id": 7,
            "instrument_id": 999,
            "ts_event": 200,
            "order_id": 102,
            "price": 250,
            "size": 3,
            "flags": 128,
            "channel_id": 2,
            "action": 84,
            "side": 65,
            "ts_recv": 400,
            "ts_in_delta": -9,
            "sequence": 17,
            "ts_out": (1 << 64) - 2 if ts_out else None,
        },
    ]
    observed_mbos = [
        {
            "rtype": {
                "kind": "native_enum",
                "class_name": "RType",
                "name": "MBO",
                "code": 160,
                "text": "mbo",
            },
            "publisher_id": 7,
            "instrument_id": 1,
            "ts_event": 300,
            "order_id": 101,
            "price": -125,
            "size": 3,
            "action": {
                "kind": "native_enum",
                "class_name": "Action",
                "name": "ADD",
                "code": 65,
                "text": "A",
            },
            "side": {
                "kind": "native_enum",
                "class_name": "Side",
                "name": "BID",
                "code": 66,
                "text": "B",
            },
            "ts_recv": 290,
            "flags": 128,
            "channel_id": 2,
            "ts_in_delta": -9,
            "sequence": 17,
            "ts_out_observed": (1 << 64) - 2 if ts_out else (1 << 64) - 1,
            "record_size_observed": 64 if ts_out else 56,
            "ts_index_observed": 290,
        },
        {
            "rtype": {
                "kind": "native_enum",
                "class_name": "RType",
                "name": "MBO",
                "code": 160,
                "text": "mbo",
            },
            "publisher_id": 7,
            "instrument_id": 999,
            "ts_event": 200,
            "order_id": 102,
            "price": 250,
            "size": 3,
            "action": {
                "kind": "native_enum",
                "class_name": "Action",
                "name": "TRADE",
                "code": 84,
                "text": "T",
            },
            "side": {
                "kind": "native_enum",
                "class_name": "Side",
                "name": "ASK",
                "code": 65,
                "text": "A",
            },
            "ts_recv": 400,
            "flags": 128,
            "channel_id": 2,
            "ts_in_delta": -9,
            "sequence": 17,
            "ts_out_observed": (1 << 64) - 2 if ts_out else (1 << 64) - 1,
            "record_size_observed": 64 if ts_out else 56,
            "ts_index_observed": 400,
        },
    ]
    occurrences = [
        {
            "decoded_position": number,
            "kind": "Metadata" if number == 1 else "MBO",
            "wire_span_ordinal": number,
            "projection": projection,
            "projection_sha256": digest(projection),
        }
        for number, projection in enumerate([metadata, *observed_mbos], 1)
    ]
    record_size = 64 if ts_out else 56
    bounds = [(0, 128), (128, 128 + record_size), (128 + record_size, 128 + 2 * record_size)]
    spans = [
        {
            "wire_span_ordinal": number,
            "kind": "Metadata" if number == 1 else "MBO",
            "decompressed_start": begin,
            "decompressed_end": end,
            "wire_sha256": raw_digest(raw[begin:end]),
            "wire_fields": fields,
            "wire_fields_sha256": digest(fields),
        }
        for number, ((begin, end), fields) in enumerate(
            zip(bounds, [wire_metadata, *wire_mbos], strict=True), 1
        )
    ]
    zstd = {
        "compressed_bytes": len(member),
        "compressed_sha256": raw_digest(member),
        "decompressed_bytes": len(raw),
        "decompressed_sha256": raw_digest(raw),
        "frames": [
            {
                "frame_ordinal": 1,
                "compressed_start": 0,
                "compressed_end": len(member),
                "decompressed_start": 0,
                "decompressed_end": len(raw),
                "compressed_span_sha256": raw_digest(member),
                "decompressed_span_sha256": raw_digest(raw),
            }
        ],
    }
    zstd["report_sha256"] = digest(zstd)
    dbn = {"decompressed_bytes": len(raw), "decompressed_sha256": raw_digest(raw), "spans": spans}
    dbn["report_sha256"] = digest(dbn)
    interpreter = {
        "implementation": "cpython",
        "version": [3, 12, 10],
        "executable_sha256": "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a",
    }
    runtime = {
        "schema": "native_profile_runtime_manifest_v1",
        "interpreter": interpreter,
        "packages": [
            {"name": name, "version": version, "metadata_sha256": pin}
            for name, version, pin in protocol["schemas"]["Package"]["allowed_rows"]
        ],
        "artifacts": [
            {"logical_id": name, "kind": kind, "raw_bytes": size, "raw_sha256": pin}
            for name, kind, size, pin in protocol["schemas"]["Artifact"]["allowed_rows"]
        ],
    }
    assert digest(runtime) == RUNTIME_SHA256
    terminal = {
        "compressed_bytes": len(member),
        "compressed_sha256": raw_digest(member),
        "decompressed_bytes": len(raw),
        "decompressed_sha256": raw_digest(raw),
        "frame_count": 1,
        "decoded_positions": 3,
        "metadata_count": 1,
        "mbo_count": 2,
        "dbn_remaining_buffer_bytes": 0,
        "zstd_framing_sha256": zstd["report_sha256"],
        "dbn_framing_sha256": dbn["report_sha256"],
        "framing_status": "complete_independent_v3_mbo_framing",
        "zstd_status": "complete_nonempty_frames_native_terminal_equality",
    }
    body = {
        "status": "complete_member_consistency_not_source_authentication",
        "protocol_sha256": digest(protocol),
        "profile_sha256": PROFILE_SHA256,
        "runtime_manifest": runtime,
        "runtime_manifest_sha256": RUNTIME_SHA256,
        "context_sha256": digest(context_body(ts_out)),
        "member_sha256": raw_digest(member),
        "metadata_sha256": digest(metadata),
        "occurrences": occurrences,
        "zstd_framing": zstd,
        "dbn_framing": dbn,
        "terminal": terminal,
        "authorities": [[name, False] for name in protocol["authority_names"]],
    }
    body["evidence_sha256"] = digest(body)
    return member, body


def typed_evidence(provider, body):
    """Explicit test construction, never production serializers or reflection."""
    p = provider

    def schema(value):
        return p.SchemaMbo(
            value["kind"], value["class_name"], value["name"], value["code"], value["text"]
        )

    def stype(value):
        if value is None:
            return None
        return p.SType(
            value["kind"], value["class_name"], value["name"], value["code"], value["text"]
        )

    def date(value):
        return p.PythonDate(value["kind"], value["year"], value["month"], value["day"])

    def metadata(value):
        groups = tuple(
            p.MappingGroup(
                group["raw_symbol"],
                tuple(
                    p.MappingInterval(
                        date(item["start_date"]), date(item["end_date"]), item["symbol"]
                    )
                    for item in group["intervals"]
                ),
            )
            for group in value["mappings"]
        )
        return p.MetadataProjection(
            value["version"],
            value["dataset"],
            schema(value["schema"]),
            value["start"],
            value["end_observed"],
            value["limit_observed"],
            stype(value["stype_in"]),
            stype(value["stype_out"]),
            value["ts_out"],
            value["symbol_cstr_len"],
            tuple(value["symbols"]),
            tuple(value["partial"]),
            tuple(value["not_found"]),
            groups,
        )

    def action(value):
        if value["kind"] == "str":
            return p.UnknownChar(value["kind"], value["value"])
        return p.Action(
            value["kind"], value["class_name"], value["name"], value["code"], value["text"]
        )

    def side(value):
        if value["kind"] == "str":
            return p.UnknownChar(value["kind"], value["value"])
        return p.Side(
            value["kind"], value["class_name"], value["name"], value["code"], value["text"]
        )

    def mbo(value):
        rtype = value["rtype"]
        return p.MboObservation(
            p.RtypeMbo(
                rtype["kind"], rtype["class_name"], rtype["name"], rtype["code"], rtype["text"]
            ),
            value["publisher_id"],
            value["instrument_id"],
            value["ts_event"],
            value["order_id"],
            value["price"],
            value["size"],
            action(value["action"]),
            side(value["side"]),
            value["ts_recv"],
            value["flags"],
            value["channel_id"],
            value["ts_in_delta"],
            value["sequence"],
            value["ts_out_observed"],
            value["record_size_observed"],
            value["ts_index_observed"],
        )

    def wire_metadata(value):
        mappings = tuple(
            p.WireMappingGroup(
                group["raw_symbol"],
                group["interval_count"],
                tuple(
                    p.WireMappingInterval(item["start_date"], item["end_date"], item["symbol"])
                    for item in group["intervals"]
                ),
            )
            for group in value["mappings"]
        )
        return p.MetadataWireBody(
            value["magic_hex"],
            value["version"],
            value["length_body"],
            value["dataset"],
            value["dataset_cstr_bytes"],
            value["schema"],
            value["start"],
            value["end"],
            value["limit"],
            value["stype_in"],
            value["stype_out"],
            value["ts_out"],
            value["symbol_cstr_len"],
            tuple(value["reserved_bytes"]),
            value["schema_definition_length"],
            value["symbols_count"],
            tuple(value["symbols"]),
            value["partial_count"],
            tuple(value["partial"]),
            value["not_found_count"],
            tuple(value["not_found"]),
            value["mappings_count"],
            mappings,
            tuple(value["alignment_padding_bytes"]),
        )

    def wire_mbo(value):
        return p.MboWireBody(
            value["length_words"],
            value["rtype"],
            value["publisher_id"],
            value["instrument_id"],
            value["ts_event"],
            value["order_id"],
            value["price"],
            value["size"],
            value["flags"],
            value["channel_id"],
            value["action"],
            value["side"],
            value["ts_recv"],
            value["ts_in_delta"],
            value["sequence"],
            value["ts_out"],
        )

    runtime = body["runtime_manifest"]
    interpreter = runtime["interpreter"]
    manifest = p.RuntimeManifest(
        runtime["schema"],
        p.Interpreter(
            interpreter["implementation"],
            tuple(interpreter["version"]),
            interpreter["executable_sha256"],
        ),
        tuple(
            p.Package(row["name"], row["version"], row["metadata_sha256"])
            for row in runtime["packages"]
        ),
        tuple(
            p.Artifact(row["logical_id"], row["kind"], row["raw_bytes"], row["raw_sha256"])
            for row in runtime["artifacts"]
        ),
    )
    occurrences = tuple(
        p.DecodedOccurrence(
            row["decoded_position"],
            row["kind"],
            row["wire_span_ordinal"],
            metadata(row["projection"]) if row["kind"] == "Metadata" else mbo(row["projection"]),
            row["projection_sha256"],
        )
        for row in body["occurrences"]
    )
    zstd = body["zstd_framing"]
    zstd_report = p.ZstdFramingReport(
        zstd["compressed_bytes"],
        zstd["compressed_sha256"],
        zstd["decompressed_bytes"],
        zstd["decompressed_sha256"],
        tuple(
            p.FrameSpan(
                row["frame_ordinal"],
                row["compressed_start"],
                row["compressed_end"],
                row["decompressed_start"],
                row["decompressed_end"],
                row["compressed_span_sha256"],
                row["decompressed_span_sha256"],
            )
            for row in zstd["frames"]
        ),
        zstd["report_sha256"],
    )
    dbn = body["dbn_framing"]
    dbn_report = p.DbnFramingReport(
        dbn["decompressed_bytes"],
        dbn["decompressed_sha256"],
        tuple(
            p.WireSpan(
                row["wire_span_ordinal"],
                row["kind"],
                row["decompressed_start"],
                row["decompressed_end"],
                row["wire_sha256"],
                wire_metadata(row["wire_fields"])
                if row["kind"] == "Metadata"
                else wire_mbo(row["wire_fields"]),
                row["wire_fields_sha256"],
            )
            for row in dbn["spans"]
        ),
        dbn["report_sha256"],
    )
    terminal = body["terminal"]
    terminal_record = p.TerminalEvidence(
        terminal["compressed_bytes"],
        terminal["compressed_sha256"],
        terminal["decompressed_bytes"],
        terminal["decompressed_sha256"],
        terminal["frame_count"],
        terminal["decoded_positions"],
        terminal["metadata_count"],
        terminal["mbo_count"],
        terminal["dbn_remaining_buffer_bytes"],
        terminal["zstd_framing_sha256"],
        terminal["dbn_framing_sha256"],
        terminal["framing_status"],
        terminal["zstd_status"],
    )
    return p.MemberDecodeEvidence(
        body["status"],
        body["protocol_sha256"],
        body["profile_sha256"],
        manifest,
        body["runtime_manifest_sha256"],
        body["context_sha256"],
        body["member_sha256"],
        body["metadata_sha256"],
        occurrences,
        zstd_report,
        dbn_report,
        terminal_record,
        tuple((name, flag) for name, flag in body["authorities"]),
        body["evidence_sha256"],
    )


def minimal_dbn_framing_expected(ts_out=False):
    """Complete independent field ledgers, including original count/padding bytes."""
    _, evidence = minimal_evidence_body(ts_out)
    metadata = dict(evidence["dbn_framing"]["spans"][0]["wire_fields"])
    for field in (
        "reserved_bytes",
        "symbols",
        "partial",
        "not_found",
        "mappings",
        "alignment_padding_bytes",
    ):
        metadata[field] = tuple(metadata[field])
    metadata_fields = (
        ("magic", 0, 3),
        ("version", 3, 4),
        ("length_body", 4, 8),
        ("dataset", 8, 24),
        ("schema", 24, 26),
        ("start", 26, 34),
        ("end", 34, 42),
        ("limit", 42, 50),
        ("stype_in", 50, 51),
        ("stype_out", 51, 52),
        ("ts_out", 52, 53),
        ("symbol_cstr_len", 53, 55),
        ("reserved", 55, 108),
        ("schema_definition_length", 108, 112),
        ("symbols_count", 112, 116),
        ("partial_count", 116, 120),
        ("not_found_count", 120, 124),
        ("mappings_count", 124, 128),
    )
    relative_mbo_fields = (
        ("length_words", 0, 1),
        ("rtype", 1, 2),
        ("publisher_id", 2, 4),
        ("instrument_id", 4, 8),
        ("ts_event", 8, 16),
        ("order_id", 16, 24),
        ("price", 24, 32),
        ("size", 32, 36),
        ("flags", 36, 37),
        ("channel_id", 37, 38),
        ("action", 38, 39),
        ("side", 39, 40),
        ("ts_recv", 40, 48),
        ("ts_in_delta", 48, 52),
        ("sequence", 52, 56),
    )
    if ts_out:
        relative_mbo_fields += (("ts_out", 56, 64),)
    size = 64 if ts_out else 56
    return {
        "complete_bytes": 128 + 2 * size,
        "wire_spans": (
            ("Metadata", 0, 128),
            ("MBO", 128, 128 + size),
            ("MBO", 128 + size, 128 + 2 * size),
        ),
        "wire_bodies": (
            metadata,
            evidence["dbn_framing"]["spans"][1]["wire_fields"],
            evidence["dbn_framing"]["spans"][2]["wire_fields"],
        ),
        "field_spans": (
            metadata_fields,
            tuple((name, begin + 128, end + 128) for name, begin, end in relative_mbo_fields),
            tuple(
                (name, begin + 128 + size, end + 128 + size)
                for name, begin, end in relative_mbo_fields
            ),
        ),
    }


def raw_frame_expected(raw, ordinal=1, start=0):
    length = len(raw)
    descriptor = 32 if length < 256 else 96
    header_end = start + (6 if length < 256 else 7)
    end = header_end + 3 + length
    return (
        ordinal,
        start,
        end,
        start,
        header_end,
        descriptor,
        None,
        0 if length < 256 else 1,
        True,
        0,
        False,
        length,
        length,
        None,
        None,
        ((1, header_end, header_end + 3, True, 0, length, header_end + 3, end),),
    )


def rehash_evidence(body):
    """Independent whole-body hashing for deliberately coherent false submissions."""
    for occurrence in body["occurrences"]:
        occurrence["projection_sha256"] = digest(occurrence["projection"])
    for span in body["dbn_framing"]["spans"]:
        span["wire_fields_sha256"] = digest(span["wire_fields"])
    for report_name in ("zstd_framing", "dbn_framing"):
        report = body[report_name]
        report["report_sha256"] = digest(
            {key: value for key, value in report.items() if key != "report_sha256"}
        )
    body["terminal"]["zstd_framing_sha256"] = body["zstd_framing"]["report_sha256"]
    body["terminal"]["dbn_framing_sha256"] = body["dbn_framing"]["report_sha256"]
    body["metadata_sha256"] = body["occurrences"][0]["projection_sha256"]
    body["evidence_sha256"] = digest(
        {key: value for key, value in body.items() if key != "evidence_sha256"}
    )
    return body


# New provider-native cases. The builders below use only the held public schema
# and these pinned official format descriptions, never a production serializer,
# native encoder, reflected SDK definition, or previous native output:
# https://github.com/databento/dbn/blob/aa012adc6502e01b01d7b5c7836742dde21e93d8/rust/dbn/src/encode/dbn/sync.rs
# https://github.com/databento/dbn/blob/aa012adc6502e01b01d7b5c7836742dde21e93d8/rust/dbn/src/python/record.rs
# https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/doc/zstd_compression_format.md
# https://github.com/Cyan4973/xxHash/blob/e626a72bc2321cd320e953a0ccf1584cad60f363/doc/xxhash_spec.md


def _native_enum(class_name, name, code, text):
    return {
        "kind": "native_enum",
        "class_name": class_name,
        "name": name,
        "code": code,
        "text": text,
    }


_NATIVE_STYPES = (
    ("INSTRUMENT_ID", "instrument_id"),
    ("RAW_SYMBOL", "raw_symbol"),
    ("SMART", "smart"),
    ("CONTINUOUS", "continuous"),
    ("PARENT", "parent"),
    ("NASDAQ_SYMBOL", "nasdaq_symbol"),
    ("CMS_SYMBOL", "cms_symbol"),
    ("ISIN", "isin"),
    ("US_CODE", "us_code"),
    ("BBG_COMP_ID", "bbg_comp_id"),
    ("BBG_COMP_TICKER", "bbg_comp_ticker"),
    ("FIGI", "figi"),
    ("FIGI_TICKER", "figi_ticker"),
    ("LISTING_ID", "listing_id"),
    ("ISSUER_ID", "issuer_id"),
    ("SECURITY_ID", "security_id"),
)
_NATIVE_ACTIONS = {
    77: ("MODIFY", "M"),
    84: ("TRADE", "T"),
    70: ("FILL", "F"),
    67: ("CANCEL", "C"),
    65: ("ADD", "A"),
    82: ("CLEAR", "R"),
    78: ("NONE", "N"),
}
_NATIVE_SIDES = {65: ("ASK", "A"), 66: ("BID", "B"), 78: ("NONE", "N")}


def _native_stype(code):
    if code == 255:
        return None
    name, text = _NATIVE_STYPES[code]
    return _native_enum("SType", name, code, text)


def _native_char(class_name, code):
    rows = _NATIVE_ACTIONS if class_name == "Action" else _NATIVE_SIDES
    if code not in rows:
        return {"kind": "str", "value": chr(code)}
    name, text = rows[code]
    return _native_enum(class_name, name, code, text)


def _native_cstr(value, width):
    data = value.encode("utf-8")
    assert len(data) < width
    return data + bytes(width - len(data))


def _native_date(value):
    return {
        "kind": "python_date",
        "year": value // 10000,
        "month": (value // 100) % 100,
        "day": value % 100,
    }


def _native_metadata(
    ts_out=False,
    *,
    dataset="GLBX.MDP3",
    start=100,
    end=(1 << 64) - 1,
    limit=0,
    stype_in=1,
    stype_out=0,
    symbols=(),
    partial=(),
    not_found=(),
    mappings=(),
):
    """Declare every original field and logical translation, then lay out bytes.

    Each mapping input is (raw_symbol, ((YYYYMMDD, YYYYMMDD, symbol), ...)).
    The wire group order and repeated intervals deliberately survive unchanged.
    Only the logical dictionary key order is sorted, as the annex requires.
    """
    wire_groups = [
        {
            "raw_symbol": key,
            "interval_count": len(intervals),
            "intervals": [
                {"start_date": first, "end_date": last, "symbol": symbol}
                for first, last, symbol in intervals
            ],
        }
        for key, intervals in mappings
    ]
    projected_groups = [
        {
            "raw_symbol": key,
            "intervals": [
                {
                    "start_date": _native_date(first),
                    "end_date": _native_date(last),
                    "symbol": symbol,
                }
                for first, last, symbol in intervals
            ],
        }
        for key, intervals in sorted(mappings, key=lambda group: group[0])
    ]
    projection = {
        "version": 3,
        "dataset": dataset,
        "schema": _native_enum("Schema", "MBO", 0, "mbo"),
        "start": start,
        "end_observed": None if end in (0, (1 << 64) - 1) else end,
        "limit_observed": None if limit == 0 else limit,
        "stype_in": _native_stype(stype_in),
        "stype_out": _native_stype(stype_out),
        "ts_out": ts_out,
        "symbol_cstr_len": 71,
        "symbols": list(symbols),
        "partial": list(partial),
        "not_found": list(not_found),
        "mappings": projected_groups,
    }
    variable = bytearray()
    for values in (symbols, partial, not_found):
        variable.extend(len(values).to_bytes(4, "little"))
        for value in values:
            variable.extend(_native_cstr(value, 71))
    variable.extend(len(mappings).to_bytes(4, "little"))
    for key, intervals in mappings:
        variable.extend(_native_cstr(key, 71))
        variable.extend(len(intervals).to_bytes(4, "little"))
        for first, last, symbol in intervals:
            variable.extend(first.to_bytes(4, "little"))
            variable.extend(last.to_bytes(4, "little"))
            variable.extend(_native_cstr(symbol, 71))
    padding = bytes(-(112 + len(variable)) % 8)
    header_size = 112 + len(variable) + len(padding)
    wire = {
        "magic_hex": "44424e",
        "version": 3,
        "length_body": header_size - 8,
        "dataset": dataset,
        "dataset_cstr_bytes": 16,
        "schema": 0,
        "start": start,
        "end": end,
        "limit": limit,
        "stype_in": stype_in,
        "stype_out": stype_out,
        "ts_out": int(ts_out),
        "symbol_cstr_len": 71,
        "reserved_bytes": [0] * 53,
        "schema_definition_length": 0,
        "symbols_count": len(symbols),
        "symbols": list(symbols),
        "partial_count": len(partial),
        "partial": list(partial),
        "not_found_count": len(not_found),
        "not_found": list(not_found),
        "mappings_count": len(mappings),
        "mappings": wire_groups,
        "alignment_padding_bytes": list(padding),
    }
    fixed = (
        b"DBN\x03"
        + (header_size - 8).to_bytes(4, "little")
        + _native_cstr(dataset, 16)
        + b"\x00\x00"
        + start.to_bytes(8, "little")
        + end.to_bytes(8, "little")
        + limit.to_bytes(8, "little")
        + bytes((stype_in, stype_out, int(ts_out)))
        + b"\x47\x00"
        + bytes(53)
        + bytes(4)
    )
    return fixed + bytes(variable) + padding, wire, projection


def _native_mbo(
    ts_out=False,
    *,
    publisher=7,
    instrument=1,
    event=300,
    order=101,
    price=-125,
    size=3,
    flags=128,
    channel=2,
    action=65,
    side=66,
    received=290,
    delta=-9,
    sequence=17,
    output=(1 << 64) - 2,
):
    """Explicit width/signedness and all seventeen native observations."""
    wire = {
        "length_words": 16 if ts_out else 14,
        "rtype": 160,
        "publisher_id": publisher,
        "instrument_id": instrument,
        "ts_event": event,
        "order_id": order,
        "price": price,
        "size": size,
        "flags": flags,
        "channel_id": channel,
        "action": action,
        "side": side,
        "ts_recv": received,
        "ts_in_delta": delta,
        "sequence": sequence,
        "ts_out": output if ts_out else None,
    }
    projection = {
        "rtype": _native_enum("RType", "MBO", 160, "mbo"),
        "publisher_id": publisher,
        "instrument_id": instrument,
        "ts_event": event,
        "order_id": order,
        "price": price,
        "size": size,
        "action": _native_char("Action", action),
        "side": _native_char("Side", side),
        "ts_recv": received,
        "flags": flags,
        "channel_id": channel,
        "ts_in_delta": delta,
        "sequence": sequence,
        "ts_out_observed": output if ts_out else (1 << 64) - 1,
        "record_size_observed": 64 if ts_out else 56,
        "ts_index_observed": received,
    }
    data = (
        bytes((16 if ts_out else 14, 160))
        + publisher.to_bytes(2, "little")
        + instrument.to_bytes(4, "little")
        + event.to_bytes(8, "little")
        + order.to_bytes(8, "little")
        + price.to_bytes(8, "little", signed=True)
        + size.to_bytes(4, "little")
        + bytes((flags, channel, action, side))
        + received.to_bytes(8, "little")
        + delta.to_bytes(4, "little", signed=True)
        + sequence.to_bytes(4, "little")
        + (output.to_bytes(8, "little") if ts_out else b"")
    )
    return data, wire, projection


def _native_xxh64(data):
    """Independent seed-zero XXH64 from the pinned complete arithmetic spec."""
    mask = (1 << 64) - 1
    prime1 = 0x9E3779B185EBCA87
    prime2 = 0xC2B2AE3D27D4EB4F
    prime3 = 0x165667B19E3779F9
    prime4 = 0x85EBCA77C2B2AE63
    prime5 = 0x27D4EB2F165667C5

    def rotate(value, count):
        value &= mask
        return ((value << count) | (value >> (64 - count))) & mask

    def round_lane(accumulator, lane):
        return (rotate(accumulator + lane * prime2, 31) * prime1) & mask

    offset = 0
    if len(data) >= 32:
        accumulators = [(prime1 + prime2) & mask, prime2, 0, (-prime1) & mask]
        while offset + 32 <= len(data):
            for lane_index in range(4):
                begin = offset + 8 * lane_index
                lane = int.from_bytes(data[begin : begin + 8], "little")
                accumulators[lane_index] = round_lane(accumulators[lane_index], lane)
            offset += 32
        accumulator = (
            sum(
                rotate(value, amount)
                for value, amount in zip(accumulators, (1, 7, 12, 18), strict=True)
            )
            & mask
        )
        for value in accumulators:
            accumulator = ((accumulator ^ round_lane(0, value)) * prime1 + prime4) & mask
    else:
        accumulator = prime5
    accumulator = (accumulator + len(data)) & mask
    while offset + 8 <= len(data):
        accumulator ^= round_lane(0, int.from_bytes(data[offset : offset + 8], "little"))
        accumulator = (rotate(accumulator, 27) * prime1 + prime4) & mask
        offset += 8
    if offset + 4 <= len(data):
        accumulator ^= int.from_bytes(data[offset : offset + 4], "little") * prime1
        accumulator = (rotate(accumulator, 23) * prime2 + prime3) & mask
        offset += 4
    for value in data[offset:]:
        accumulator ^= value * prime5
        accumulator = (rotate(accumulator, 11) * prime1) & mask
    accumulator ^= accumulator >> 33
    accumulator = (accumulator * prime2) & mask
    accumulator ^= accumulator >> 29
    accumulator = (accumulator * prime3) & mask
    return accumulator ^ (accumulator >> 32)


def _native_frame(raw, *, known=True, checksum=False, blocks=None, empty_blocks=0):
    """Declarative Zstd frame; blocks are (kind, payload, regenerated_size).

    kind 0 is RAW, 1 is block RLE, and 2 is independently literal compressed
    payload. This function performs no compression or native codec operation.
    Unknown-FCS descriptor50 declares exactly a one-MiB window.
    """
    checkbit = 4 if checksum else 0
    if not known:
        header = bytes((checkbit, 0x50))
    elif len(raw) < 256:
        header = bytes((0x20 | checkbit, len(raw)))
    elif len(raw) <= 65791:
        header = bytes((0x60 | checkbit,)) + (len(raw) - 256).to_bytes(2, "little")
    else:
        header = bytes((0xA0 | checkbit,)) + len(raw).to_bytes(4, "little")
    if blocks is None:
        blocks = [
            (0, raw[start : start + 131072], len(raw[start : start + 131072]))
            for start in range(0, len(raw), 131072)
        ] or [(0, b"", 0)]
    encoded = bytearray(b"\x28\xb5\x2f\xfd" + header)
    encoded.extend(bytes(3) * empty_blocks)
    for index, (kind, payload, regenerated_size) in enumerate(blocks):
        size = regenerated_size if kind == 1 else len(payload)
        block_header = (size << 3) | (kind << 1) | int(index == len(blocks) - 1)
        encoded.extend(block_header.to_bytes(3, "little"))
        encoded.extend(payload)
    if checksum:
        encoded.extend((_native_xxh64(raw) & 0xFFFFFFFF).to_bytes(4, "little"))
    return bytes(encoded)


def _native_whole_body(parts, frames, ts_out):
    """Complete original/projection/framing/terminal bodies for declared parts.

    Each part carries bytes, independently declared complete wire fields and
    independently declared complete logical fields. Each frame carries its
    entire compressed and intended decompressed bytes, in original order.
    """
    raw = b"".join(part[0] for part in parts)
    member = b"".join(frame[0] for frame in frames)
    assert raw == b"".join(frame[1] for frame in frames)
    _, base = minimal_evidence_body(ts_out)
    spans = []
    occurrences = []
    offset = 0
    for number, (data, wire, projection) in enumerate(parts, 1):
        kind = "Metadata" if number == 1 else "MBO"
        spans.append(
            {
                "wire_span_ordinal": number,
                "kind": kind,
                "decompressed_start": offset,
                "decompressed_end": offset + len(data),
                "wire_sha256": raw_digest(data),
                "wire_fields": wire,
                "wire_fields_sha256": digest(wire),
            }
        )
        occurrences.append(
            {
                "decoded_position": number,
                "kind": kind,
                "wire_span_ordinal": number,
                "projection": projection,
                "projection_sha256": digest(projection),
            }
        )
        offset += len(data)
    compressed_offset = 0
    decompressed_offset = 0
    frame_spans = []
    for number, (compressed, decompressed) in enumerate(frames, 1):
        frame_spans.append(
            {
                "frame_ordinal": number,
                "compressed_start": compressed_offset,
                "compressed_end": compressed_offset + len(compressed),
                "decompressed_start": decompressed_offset,
                "decompressed_end": decompressed_offset + len(decompressed),
                "compressed_span_sha256": raw_digest(compressed),
                "decompressed_span_sha256": raw_digest(decompressed),
            }
        )
        compressed_offset += len(compressed)
        decompressed_offset += len(decompressed)
    zstd = {
        "compressed_bytes": len(member),
        "compressed_sha256": raw_digest(member),
        "decompressed_bytes": len(raw),
        "decompressed_sha256": raw_digest(raw),
        "frames": frame_spans,
    }
    zstd["report_sha256"] = digest(zstd)
    dbn = {"decompressed_bytes": len(raw), "decompressed_sha256": raw_digest(raw), "spans": spans}
    dbn["report_sha256"] = digest(dbn)
    terminal = {
        "compressed_bytes": len(member),
        "compressed_sha256": raw_digest(member),
        "decompressed_bytes": len(raw),
        "decompressed_sha256": raw_digest(raw),
        "frame_count": len(frames),
        "decoded_positions": len(parts),
        "metadata_count": 1,
        "mbo_count": len(parts) - 1,
        "dbn_remaining_buffer_bytes": 0,
        "zstd_framing_sha256": zstd["report_sha256"],
        "dbn_framing_sha256": dbn["report_sha256"],
        "framing_status": "complete_independent_v3_mbo_framing",
        "zstd_status": "complete_nonempty_frames_native_terminal_equality",
    }
    body = {
        "status": "complete_member_consistency_not_source_authentication",
        "protocol_sha256": base["protocol_sha256"],
        "profile_sha256": PROFILE_SHA256,
        "runtime_manifest": base["runtime_manifest"],
        "runtime_manifest_sha256": RUNTIME_SHA256,
        "context_sha256": digest(context_body(ts_out)),
        "member_sha256": raw_digest(member),
        "metadata_sha256": digest(parts[0][2]),
        "occurrences": occurrences,
        "zstd_framing": zstd,
        "dbn_framing": dbn,
        "terminal": terminal,
        "authorities": base["authorities"],
    }
    body["evidence_sha256"] = digest(body)
    return body


def native_member_cases():
    """Fresh complete intended cases; runtime acceptance belongs to root receipts.

    Equality capacities are genuine whole members. The one-MiB RLE controls
    deliberately are not DBN and therefore promise worker refusal, not public
    acceptance. No data from yesterday's native output packets is consulted.
    """
    cases = []

    def positive(case_id, parts, ts_out=False, *, frames=None):
        raw = b"".join(part[0] for part in parts)
        if frames is None:
            frames = [(_native_frame(raw), raw)]
        body = _native_whole_body(parts, frames, ts_out)
        cases.append(
            {
                "id": case_id,
                "member": b"".join(frame[0] for frame in frames),
                "context": context_body(ts_out),
                "expected_body": body,
                "expected_metadata_sha256": digest(parts[0][2]),
                "refusal": None,
            }
        )

    def negative(case_id, member, metadata, ts_out=False, refusal="worker"):
        cases.append(
            {
                "id": case_id,
                "member": member,
                "context": context_body(ts_out),
                "expected_body": None,
                "expected_metadata_sha256": digest(metadata),
                "refusal": refusal,
            }
        )

    rich_mappings = (
        ("zeta.\u03a9", ((20240229, 20240301, "999"), (20240229, 20240301, "999"))),
        ("alpha.\u00e9", ((20000229, 20000301, "1"), (20261231, 20260101, "reversed"))),
    )
    for ts_out in (False, True):
        metadata = _native_metadata(
            ts_out,
            dataset="GLBX.\u03a9",
            start=(1 << 64) - 1,
            end=0 if not ts_out else (1 << 64) - 1,
            limit=(1 << 64) - 1,
            symbols=("6E.FUT", "\u00e9\u03a9", "6E.FUT"),
            partial=("partial.\u00e9",),
            not_found=("missing.\u03a9", ""),
            mappings=rich_mappings,
        )
        records = [
            _native_mbo(
                ts_out,
                publisher=0,
                instrument=0,
                event=0,
                order=0,
                price=-(1 << 63),
                size=0,
                flags=0,
                channel=0,
                action=0,
                side=255,
                received=(1 << 64) - 1,
                delta=-(1 << 31),
                sequence=0,
                output=0,
            ),
            _native_mbo(
                ts_out,
                publisher=65535,
                instrument=(1 << 32) - 1,
                event=(1 << 64) - 1,
                order=(1 << 64) - 1,
                price=(1 << 63) - 1,
                size=(1 << 32) - 1,
                flags=255,
                channel=255,
                action=255,
                side=0,
                received=0,
                delta=(1 << 31) - 1,
                sequence=(1 << 32) - 1,
                output=(1 << 64) - 1,
            ),
        ]
        records.extend(
            _native_mbo(
                ts_out,
                instrument=index + 2,
                order=200 + index,
                action=action,
                side=(65, 66, 78)[index % 3],
                event=900 - index,
                received=100 + index,
            )
            for index, action in enumerate((77, 84, 70, 67, 65, 82, 78))
        )
        positive(f"rich_metadata_raw_extrema_ts_out_{int(ts_out)}", [metadata, *records], ts_out)

    for code in range(16):
        positive(
            f"stype_in_{code}_out_{15 - code}",
            [
                _native_metadata(stype_in=code, stype_out=15 - code, end=(1 << 64) - 2, limit=1),
                _native_mbo(),
            ],
        )
    positive("nullable_stype_in_255", [_native_metadata(stype_in=255), _native_mbo()])

    capacity_lists = tuple(f"symbol{index:02d}" for index in range(16))
    capacity_groups = tuple(
        (f"group{index:02d}", ((20240229, 20240301, f"{index}"), (20240229, 20240301, f"{index}")))
        for index in reversed(range(16))
    )
    capacity_metadata = _native_metadata(
        True,
        symbols=capacity_lists,
        partial=capacity_lists,
        not_found=capacity_lists,
        mappings=capacity_groups,
    )
    capacity_records = [
        _native_mbo(
            True,
            instrument=index,
            order=index,
            event=127 - index,
            received=index,
            price=-index,
            sequence=index,
            output=index,
        )
        for index in range(127)
    ]
    positive(
        "all_position_list_group_interval_caps_equal", [capacity_metadata, *capacity_records], True
    )
    for field in ("symbols", "partial", "not_found"):
        excessive = _native_metadata(**{field: capacity_lists + ("first_excess",)})
        negative(
            f"{field}_first_excess_17", _native_frame(excessive[0] + _native_mbo()[0]), excessive[2]
        )
    groups17 = capacity_groups + (("group16", ()),)
    excessive = _native_metadata(mappings=groups17)
    negative(
        "mapping_groups_first_excess_17",
        _native_frame(excessive[0] + _native_mbo()[0]),
        excessive[2],
    )
    intervals33 = (("one", tuple((20240229, 20240301, "1") for _ in range(33))),)
    excessive = _native_metadata(mappings=intervals33)
    negative(
        "mapping_intervals_first_excess_33",
        _native_frame(excessive[0] + _native_mbo()[0]),
        excessive[2],
    )
    excessive_raw = capacity_metadata[0] + b"".join(record[0] for record in capacity_records)
    excessive_raw += _native_mbo(True, instrument=127)[0]
    negative(
        "decoded_positions_first_excess_129",
        _native_frame(excessive_raw),
        capacity_metadata[2],
        True,
    )

    text70 = "\u00e9" * 35
    positive(
        "symbol_cstr_maximum_70_utf8_bytes", [_native_metadata(symbols=(text70,)), _native_mbo()]
    )
    intended_text = _native_metadata(symbols=("x" * 70,))
    no_terminator = bytearray(intended_text[0] + _native_mbo()[0])
    no_terminator[116:187] = b"x" * 71
    negative(
        "symbol_cstr_first_excess_no_nul_71_bytes",
        _native_frame(bytes(no_terminator)),
        intended_text[2],
    )

    parts = [_native_metadata(), _native_mbo(), _native_mbo(instrument=999, order=102)]
    raw = b"".join(part[0] for part in parts)
    positive("raw_known_fcs_complete", parts)
    positive("raw_unknown_fcs_complete", parts, frames=[(_native_frame(raw, known=False), raw)])
    checked = _native_frame(raw, checksum=True)
    positive("raw_xxh64_checksum_complete", parts, frames=[(checked, raw)])

    # AAAA has three independently specified compressed-block representations.
    literal_parts = [_native_metadata(symbols=("AAAA",)), _native_mbo()]
    literal_raw = b"".join(part[0] for part in literal_parts)
    for label, payload in (
        ("raw_literals", bytes.fromhex("204141414100")),
        ("rle_literals", bytes.fromhex("214100")),
        # LL=1, OF=0, ML=0, all RLE modes54. One literal A, then repeat
        # offset1 and length3; all table/extra-bit widths0; end marker01.
        ("match_repeat_offset_one", bytes.fromhex("0841015401000001")),
    ):
        blocks = [
            (0, literal_raw[:116], 116),
            (2, payload, 4),
            (0, literal_raw[120:], len(literal_raw) - 120),
        ]
        frame = _native_frame(literal_raw, blocks=blocks)
        positive(
            f"compressed_{label}_same_complete_dbn", literal_parts, frames=[(frame, literal_raw)]
        )

    # Single-stream Huffman tree: symbols00 and01 have weight1 each, with
    # final weight inferred. 80 10 is the direct tree; 11 is marker1 then
    # forward bits0001. Header42c000 declares regenerated4/compressed3.
    huffman_parts = [_native_metadata(), _native_mbo(instrument=0x01000000)]
    huffman_raw = b"".join(part[0] for part in huffman_parts)
    huffman_payload = bytes.fromhex("42c00080101100")
    blocks = [
        (0, huffman_raw[:132], 132),
        (2, huffman_payload, 4),
        (0, huffman_raw[136:], len(huffman_raw) - 136),
    ]
    frame = _native_frame(huffman_raw, blocks=blocks)
    positive(
        "compressed_huffman_00000001_complete_dbn", huffman_parts, frames=[(frame, huffman_raw)]
    )

    ts_parts = [_native_metadata(True), _native_mbo(True), _native_mbo(True, instrument=999)]
    ts_raw = b"".join(part[0] for part in ts_parts)
    for split in (5, 140, 188):
        pieces = (ts_raw[:split], ts_raw[split:])
        frames = [(_native_frame(piece), piece) for piece in pieces]
        positive(f"two_frames_crossing_offset_{split}", ts_parts, True, frames=frames)
    boundaries = (0, 3, 5, 26, 33, 53, 107, 112, 127, 129, 140, 167, 185, 188, 191, 201, 256)
    frames16 = [
        (_native_frame(ts_raw[begin:end]), ts_raw[begin:end])
        for begin, end in zip(boundaries, boundaries[1:], strict=False)
    ]
    positive("sixteen_nonempty_frames_crossing_all_structures", ts_parts, True, frames=frames16)

    # 240 decompressed bytes +9 framing +4 checksum =253. Adding87297
    # legal empty nonfinal RAW blocks contributes261891 bytes: exactly262144.
    # This is an intended format-derived positive, not prior native acceptance.
    padded = _native_frame(raw, checksum=True, empty_blocks=87297)
    assert len(padded) == 262144
    positive("compressed_bytes_exact_262144_empty_raw_blocks", parts, frames=[(padded, raw)])
    negative(
        "compressed_bytes_first_excess_262145", padded + b"\x00", parts[0][2], refusal="preflight"
    )

    negative("checksum_corrupted_final_byte", checked[:-1] + bytes((checked[-1] ^ 1,)), parts[0][2])
    incorrect_fcs = bytearray(_native_frame(raw))
    incorrect_fcs[5] -= 1
    negative("declared_fcs_one_less_than_actual", bytes(incorrect_fcs), parts[0][2])
    negative("empty_known_fcs_frame", _native_frame(b""), parts[0][2])
    negative("empty_unknown_fcs_frame", _native_frame(b"", known=False), parts[0][2])
    negative("valid_prefix_then_empty_frame", _native_frame(raw) + _native_frame(b""), parts[0][2])
    negative("truncated_last_raw_payload", _native_frame(raw)[:-1], parts[0][2])
    negative("truncated_checksum", checked[:-1], parts[0][2])
    negative("complete_frame_trailing_junk", _native_frame(raw) + b"tail", parts[0][2])
    negative(
        "skippable_frame_after_valid",
        _native_frame(raw) + bytes.fromhex("502a4d1800000000"),
        parts[0][2],
    )
    dictionary = bytes.fromhex("28b52ffd21") + b"\x00" + bytes((len(raw),))
    dictionary += ((len(raw) << 3) | 1).to_bytes(3, "little") + raw
    negative("dictionary_id_field_zero_forbidden", dictionary, parts[0][2])
    pieces17 = [ts_raw[index : index + 1] for index in range(16)] + [ts_raw[16:]]
    negative(
        "frame_count_first_excess_17",
        b"".join(_native_frame(piece) for piece in pieces17),
        ts_parts[0][2],
        True,
    )

    # The exact/first-excess expansion controls encode only repeated A bytes.
    # They are valid codec streams but invalid DBN, so neither is a positive
    # public capacity claim. Known/unknown-FCS branches remain separately named.
    for length in (1048576, 1048577):
        expanded = b"A" * length
        blocks = [(1, b"A", min(131072, length - start)) for start in range(0, length, 131072)]
        for known in (False, True):
            frame = _native_frame(expanded, known=known, blocks=blocks)
            negative(
                f"codec_rle_expansion_{length}_known_fcs_{int(known)}_invalid_dbn",
                frame,
                parts[0][2],
            )
    return tuple(cases)
