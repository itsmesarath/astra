"""Independent literal expectations for the invented member-publication bridge.

The reviewed documentation packet and literal independent byte/body builders are
the oracles, not any production serializer. No native execution or project/old-test
imports occur here; root alone may run the registered construction and tests.
"""

import copy
import hashlib
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "docs/6E_SOURCE_PUBLICATION_BRIDGE_PROTOCOL_20261014.json"
PROTOCOL_RAW_BYTES = 71923
PROTOCOL_RAW_SHA = "1c14ab24b624a7e2e5429a2a9379eeb6def9d0f484cdda04c9964b0e8f3ee6ed"
PROTOCOL_CANONICAL_BYTES = 68672
PROTOCOL_SHA = "924c4c37e66e561ece476cb57d927ecb64e01588050df3edb9aa17d5ebd13862"
PROFILE_ID = "dbn_v3_asis_zstd_cext_invented_20261012_v1"
FIXTURE_ID = "synthetic-member-publication-minimal"
SOURCE_SESSION = "synthetic-bridge-session"
DAY = 1_743_984_000_000_000_000
SECOND = 1_000_000_000
NOON = DAY + 43_200 * SECOND
WARMUP = NOON - 10 * SECOND
END = DAY + 57_600 * SECOND
EXECUTION_SHA = "2db856c8c85a1d9d268819b9c7e7246478342d86c419c6e64f889f18cee103b2"


def canonical(body):
    return json.dumps(
        body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(body):
    return hashlib.sha256(canonical(body)).hexdigest()


def expected_protocol():
    raw = PROTOCOL_PATH.read_bytes()
    assert len(raw) == PROTOCOL_RAW_BYTES
    assert hashlib.sha256(raw).hexdigest() == PROTOCOL_RAW_SHA
    body = json.loads(raw)
    encoded = canonical(body)
    assert len(encoded) == PROTOCOL_CANONICAL_BYTES
    assert hashlib.sha256(encoded).hexdigest() == PROTOCOL_SHA
    return body


def expected_context(ts_out=False, *, fixture_id=FIXTURE_ID, source_session=SOURCE_SESSION):
    return {
        "fixture_id": fixture_id,
        "source_session": source_session,
        "native_context": {
            "profile_id": PROFILE_ID,
            "member_compression": "ZSTD_CONCAT",
            "input_version": 3,
            "upgrade_policy": "AS_IS",
            "expected_ts_out": ts_out,
        },
    }


def raw_digest(value):
    return hashlib.sha256(value).hexdigest()


def _enum(class_name, name, code, text):
    return {
        "kind": "native_enum",
        "class_name": class_name,
        "name": name,
        "code": code,
        "text": text,
    }


def _character(class_name, character):
    rows = expected_protocol()["dependencies"]["native"]["schemas"][class_name]["allowed_rows"]
    for name, code, text in rows:
        if code == ord(character):
            return _enum(class_name, name, code, text)
    return {"kind": "str", "value": character}


def _cstr(value, width):
    encoded = value.encode("utf-8")
    assert len(encoded) < width and b"\0" not in encoded
    return encoded + bytes(width - len(encoded))


def minimal_payloads(ts_out):
    """Literal old idle-event oracle, with actual native 56/64-byte widths."""
    records = []
    for action, side, received, order, price, size, flags, sequence in (
        ("R", "N", WARMUP - SECOND, 0, 0, 0, 0, 1),
        ("A", "B", WARMUP - SECOND + 1, 11, 1_000_001, 10, 32, 2),
        ("A", "A", WARMUP - SECOND + 2, 12, 1_100_001, 20, 32, 3),
        ("N", "N", NOON, 0, 0, 0, 128, 4),
    ):
        records.append(
            {
                "publisher_id": 111,
                "instrument_id": 7,
                "ts_event": received - 1,
                "order_id": order,
                "price": price,
                "size": size,
                "action": action,
                "side": side,
                "ts_recv": received,
                "flags": flags,
                "channel_id": 2,
                "ts_in_delta": 0,
                "sequence": sequence,
                "ts_out": received + 20 if ts_out else None,
                "rtype": 160,
                "record_size": 64 if ts_out else 56,
            }
        )
    return records


def metadata_part(ts_out):
    """Original DBN layout and complete logical/wire declarations, independently."""
    start_date = {"kind": "python_date", "year": 2025, "month": 4, "day": 7}
    end_date = {"kind": "python_date", "year": 2025, "month": 4, "day": 8}
    projection = {
        "version": 3,
        "dataset": "GLBX.MDP3",
        "schema": _enum("Schema", "MBO", 0, "mbo"),
        "start": DAY,
        "end_observed": DAY + 86_400 * SECOND,
        "limit_observed": None,
        "stype_in": _enum("SType", "PARENT", 4, "parent"),
        "stype_out": _enum("SType", "INSTRUMENT_ID", 0, "instrument_id"),
        "ts_out": ts_out,
        "symbol_cstr_len": 71,
        "symbols": ["6E.FUT"],
        "partial": [],
        "not_found": [],
        "mappings": [
            {
                "raw_symbol": "6EM5",
                "intervals": [
                    {
                        "start_date": start_date,
                        "end_date": end_date,
                        "symbol": "0007",
                    }
                ],
            }
        ],
    }
    variable = (
        (1).to_bytes(4, "little")
        + _cstr("6E.FUT", 71)
        + bytes(4)
        + bytes(4)
        + (1).to_bytes(4, "little")
        + _cstr("6EM5", 71)
        + (1).to_bytes(4, "little")
        + (20250407).to_bytes(4, "little")
        + (20250408).to_bytes(4, "little")
        + _cstr("0007", 71)
    )
    padding = bytes(-(112 + len(variable)) % 8)
    header_size = 112 + len(variable) + len(padding)
    assert header_size == 360 and len(padding) == 7
    wire = {
        "magic_hex": "44424e",
        "version": 3,
        "length_body": header_size - 8,
        "dataset": "GLBX.MDP3",
        "dataset_cstr_bytes": 16,
        "schema": 0,
        "start": DAY,
        "end": DAY + 86_400 * SECOND,
        "limit": 0,
        "stype_in": 4,
        "stype_out": 0,
        "ts_out": int(ts_out),
        "symbol_cstr_len": 71,
        "reserved_bytes": [0] * 53,
        "schema_definition_length": 0,
        "symbols_count": 1,
        "symbols": ["6E.FUT"],
        "partial_count": 0,
        "partial": [],
        "not_found_count": 0,
        "not_found": [],
        "mappings_count": 1,
        "mappings": [
            {
                "raw_symbol": "6EM5",
                "interval_count": 1,
                "intervals": [
                    {
                        "start_date": 20250407,
                        "end_date": 20250408,
                        "symbol": "0007",
                    }
                ],
            }
        ],
        "alignment_padding_bytes": list(padding),
    }
    fixed = (
        b"DBN\x03"
        + (header_size - 8).to_bytes(4, "little")
        + _cstr("GLBX.MDP3", 16)
        + bytes(2)
        + DAY.to_bytes(8, "little")
        + (DAY + 86_400 * SECOND).to_bytes(8, "little")
        + bytes(8)
        + bytes((4, 0, int(ts_out)))
        + b"\x47\0"
        + bytes(53)
        + bytes(4)
    )
    return fixed + variable + padding, wire, projection


def mbo_part(raw, ts_out):
    wire = {
        "length_words": 16 if ts_out else 14,
        "rtype": 160,
        "publisher_id": raw["publisher_id"],
        "instrument_id": raw["instrument_id"],
        "ts_event": raw["ts_event"],
        "order_id": raw["order_id"],
        "price": raw["price"],
        "size": raw["size"],
        "flags": raw["flags"],
        "channel_id": raw["channel_id"],
        "action": ord(raw["action"]),
        "side": ord(raw["side"]),
        "ts_recv": raw["ts_recv"],
        "ts_in_delta": raw["ts_in_delta"],
        "sequence": raw["sequence"],
        "ts_out": raw["ts_out"],
    }
    projection = {
        "rtype": _enum("RType", "MBO", 160, "mbo"),
        "publisher_id": raw["publisher_id"],
        "instrument_id": raw["instrument_id"],
        "ts_event": raw["ts_event"],
        "order_id": raw["order_id"],
        "price": raw["price"],
        "size": raw["size"],
        "action": _character("Action", raw["action"]),
        "side": _character("Side", raw["side"]),
        "ts_recv": raw["ts_recv"],
        "flags": raw["flags"],
        "channel_id": raw["channel_id"],
        "ts_in_delta": raw["ts_in_delta"],
        "sequence": raw["sequence"],
        "ts_out_observed": raw["ts_out"] if ts_out else (1 << 64) - 1,
        "record_size_observed": 64 if ts_out else 56,
        "ts_index_observed": raw["ts_recv"],
    }
    data = (
        bytes((16 if ts_out else 14, 160))
        + raw["publisher_id"].to_bytes(2, "little")
        + raw["instrument_id"].to_bytes(4, "little")
        + raw["ts_event"].to_bytes(8, "little")
        + raw["order_id"].to_bytes(8, "little")
        + raw["price"].to_bytes(8, "little", signed=True)
        + raw["size"].to_bytes(4, "little")
        + bytes((raw["flags"], raw["channel_id"], ord(raw["action"]), ord(raw["side"])))
        + raw["ts_recv"].to_bytes(8, "little")
        + raw["ts_in_delta"].to_bytes(4, "little", signed=True)
        + raw["sequence"].to_bytes(4, "little")
        + (raw["ts_out"].to_bytes(8, "little") if ts_out else b"")
    )
    assert len(data) == raw["record_size"]
    return data, wire, projection


def raw_frame(raw):
    """One independent RAW block, never a native encoder or compression call."""
    assert 256 <= len(raw) <= 65791
    return (
        b"\x28\xb5\x2f\xfd\x60"
        + (len(raw) - 256).to_bytes(2, "little")
        + ((len(raw) << 3) | 1).to_bytes(3, "little")
        + raw
    )


def expected_runtime():
    schemas = expected_protocol()["dependencies"]["native"]["schemas"]
    interpreter = copy.deepcopy(schemas["Interpreter"]["fixed_values"])
    packages = [
        dict(zip(schemas["Package"]["row_fields"], row, strict=True))
        for row in schemas["Package"]["allowed_rows"]
    ]
    artifacts = [
        dict(zip(schemas["Artifact"]["row_fields"], row, strict=True))
        for row in schemas["Artifact"]["allowed_rows"]
    ]
    result = {
        "schema": "native_profile_runtime_manifest_v1",
        "interpreter": interpreter,
        "packages": sorted(packages, key=lambda item: item["name"]),
        "artifacts": sorted(artifacts, key=lambda item: item["logical_id"]),
    }
    assert digest(result) == expected_protocol()["dependencies"]["runtime_manifest_sha256"]
    return result


def native_evidence_body(parts, member, raw, ts_out):
    packet = expected_protocol()
    spans, occurrences, offset = [], [], 0
    for position, (data, wire, projection) in enumerate(parts, 1):
        kind = "Metadata" if position == 1 else "MBO"
        spans.append(
            {
                "wire_span_ordinal": position,
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
                "decoded_position": position,
                "kind": kind,
                "wire_span_ordinal": position,
                "projection": projection,
                "projection_sha256": digest(projection),
            }
        )
        offset += len(data)
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
    terminal = {
        "compressed_bytes": len(member),
        "compressed_sha256": raw_digest(member),
        "decompressed_bytes": len(raw),
        "decompressed_sha256": raw_digest(raw),
        "frame_count": 1,
        "decoded_positions": len(parts),
        "metadata_count": 1,
        "mbo_count": len(parts) - 1,
        "dbn_remaining_buffer_bytes": 0,
        "zstd_framing_sha256": zstd["report_sha256"],
        "dbn_framing_sha256": dbn["report_sha256"],
        "framing_status": "complete_independent_v3_mbo_framing",
        "zstd_status": "complete_nonempty_frames_native_terminal_equality",
    }
    result = {
        "status": "complete_member_consistency_not_source_authentication",
        "protocol_sha256": packet["hash_schemes"]["dependency_protocols"]["native"],
        "profile_sha256": packet["dependencies"]["profile_sha256"],
        "runtime_manifest": expected_runtime(),
        "runtime_manifest_sha256": packet["dependencies"]["runtime_manifest_sha256"],
        "context_sha256": digest(expected_context(ts_out)["native_context"]),
        "member_sha256": raw_digest(member),
        "metadata_sha256": digest(parts[0][2]),
        "occurrences": occurrences,
        "zstd_framing": zstd,
        "dbn_framing": dbn,
        "terminal": terminal,
        "authorities": [[name, False] for name in packet["authority_names"]],
    }
    return result | {"evidence_sha256": digest(result)}


def cursor_fixture_body(records, member):
    return {
        "fixture_id": FIXTURE_ID,
        "source_session": SOURCE_SESSION,
        "utc_date": "2025-04-07",
        "contract": "6EM5",
        "header": {
            "dataset": "GLBX.MDP3",
            "schema": "mbo",
            "symbols": ["6E.FUT"],
            "not_found": [],
            "start_ns": DAY,
            "end_ns": DAY + 86_400 * SECOND,
            "mappings": [
                {
                    "contract": "6EM5",
                    "intervals": [
                        {
                            "start_date": "2025-04-07",
                            "end_date": "2025-04-08",
                            "instrument_symbol": "0007",
                        }
                    ],
                }
            ],
        },
        "asserted_member_sha256": raw_digest(member),
        "declared_item_count": len(records) + 1,
        "items": [
            {
                "decoded_position": 1,
                "kind": "metadata",
                "instrument_id": None,
                "payload_sha256": None,
            }
        ]
        + [
            {
                "decoded_position": position,
                "kind": "mbo",
                "instrument_id": raw["instrument_id"],
                "payload_sha256": digest(raw),
            }
            for position, raw in enumerate(records, 2)
        ],
    }


def cursor_assessment_body(fixture):
    protocol = expected_protocol()["dependencies"]["cursor"]
    protocol_pin = digest(protocol)
    prefix = digest(
        {
            "protocol_sha256": protocol_pin,
            "fixture_id": fixture["fixture_id"],
            "source_session": fixture["source_session"],
            "utc_date": fixture["utc_date"],
            "contract": fixture["contract"],
            "header": fixture["header"],
        }
    )
    audits, targets, foreign = [], 0, 0
    for item in fixture["items"]:
        prefix = digest({"previous_prefix_sha256": prefix, "item": item})
        ordinal = None
        if item["kind"] == "metadata":
            disposition = "header"
        elif item["instrument_id"] == 7:
            disposition, targets = "target_candidate", targets + 1
            ordinal = targets
        else:
            disposition, foreign = "foreign", foreign + 1
        audits.append(
            {
                "decoded_position": item["decoded_position"],
                "disposition": disposition,
                "instrument_id": item["instrument_id"],
                "target_candidate_ordinal": ordinal,
                "item_sha256": digest(item),
                "prefix_sha256": prefix,
            }
        )
    result = {
        "status": protocol["status"],
        "protocol_sha256": protocol_pin,
        "fixture_sha256": digest(fixture),
        "fixture": fixture,
        "mapped_instrument_id": 7,
        "decoded_item_count": len(fixture["items"]),
        "target_candidate_count": targets,
        "foreign_count": foreign,
        "audits": audits,
        "authority_flags": copy.deepcopy(protocol["authority_flags"]),
    }
    return result | {"assessment_sha256": digest(result)}


def binding_assessment_body(bundle):
    protocol = expected_protocol()["dependencies"]["binding"]
    old = cursor_assessment_body(bundle["cursor_fixture"])
    context_pin, protocol_pin = digest(bundle["context"]), digest(protocol)
    audits = []
    for old_audit, item in zip(old["audits"], bundle["cursor_fixture"]["items"], strict=True):
        audits.append(
            {
                "decoded_position": old_audit["decoded_position"],
                "disposition": old_audit["disposition"],
                "instrument_id": old_audit["instrument_id"],
                "target_candidate_ordinal": old_audit["target_candidate_ordinal"],
                "payload_sha256": item["payload_sha256"],
                "cursor_item_sha256": old_audit["item_sha256"],
                "cursor_prefix_sha256": old_audit["prefix_sha256"],
                "bound_prefix_sha256": digest(
                    {
                        "binding_protocol_sha256": protocol_pin,
                        "context_sha256": context_pin,
                        "cursor_prefix_sha256": old_audit["prefix_sha256"],
                    }
                ),
            }
        )
    result = {
        "status": protocol["status"],
        "protocol_sha256": protocol_pin,
        "context_sha256": context_pin,
        "cursor_protocol_sha256": old["protocol_sha256"],
        "cursor_fixture_sha256": digest(bundle["cursor_fixture"]),
        "bundle_sha256": digest(bundle),
        "bundle": bundle,
        "cursor_assessment": old,
        "audits": audits,
        "authority_flags": copy.deepcopy(protocol["authority_flags"]),
    }
    return result | {"assessment_sha256": digest(result)}


def empty_state():
    return {
        "initialized": False,
        "orders": [],
        "bid_levels": [],
        "ask_levels": [],
        "last_recv_ns": None,
        "pending_target_positions": [],
        "pending_trade_positions": [],
        "execution_capture_positions": [],
        "last_quote_ordinal": None,
        "flow_events": [],
        "cvd": 0,
        "known_trades": 0,
        "unknown_trades": 0,
        "ofi_generation": 0,
        "ofi_previous_quote_ordinal": None,
        "ofi_first_ts_ns": None,
        "ofi_events": [],
        "ofi_total": 0,
        "history_ofi_generation": None,
        "history_quote_ordinals": [],
        "bid_depletions": [],
        "ask_depletions": [],
        "history_reloads": [],
        "execution_last_ts_ns": None,
        "execution_events": [],
        "execution_totals": {},
        "bid_credits": [],
        "ask_credits": [],
        "execution_audit": {},
        "next_publication_ns": NOON,
        "watch_since_ns": WARMUP,
        "inactivity_start_ns": None,
        "window_closed": False,
    }


def idle_features():
    values = (
        math.log1p(10),
        math.log1p(20),
        -10 / 30,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        math.log1p(10),
        math.log1p(20),
        -10 / 30,
        1.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
        math.log1p(1),
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    )
    names = expected_protocol()["dependencies"]["adapter"]["feature_names"]
    assert len(values) == len(names) == 37
    return [[name, value] for name, value in zip(names, values, strict=True)]


def adapter_assessment_body(fixture):
    """Complete four-transition literal idle path, not a second production engine."""
    packet = expected_protocol()
    protocol = packet["dependencies"]["adapter"]
    protocol_pin, context_pin = digest(protocol), digest(fixture["context"])
    bound = binding_assessment_body(fixture["payload_bundle"])
    positions = [
        audit["decoded_position"]
        for audit in bound["audits"]
        if audit["disposition"] == "target_candidate"
    ]
    assert len(positions) == 4
    quote_position = positions[-1]
    prefixes = {
        audit["decoded_position"]: digest(
            {
                "adapter_protocol_sha256": protocol_pin,
                "context_sha256": context_pin,
                "binding_prefix_sha256": audit["bound_prefix_sha256"],
            }
        )
        for audit in bound["audits"]
    }
    bid = {"side": "B", "price": 1_000_001, "size": 10}
    ask = {"side": "A", "price": 1_100_001, "size": 20}
    state, states = empty_state(), []
    state.update(initialized=True, last_recv_ns=WARMUP - SECOND)
    states.append(copy.deepcopy(state))
    state.update(
        orders=[{"order_id": 11, "state": bid}], bid_levels=[{"price": 1_000_001, "size": 10}]
    )
    states.append(copy.deepcopy(state))
    state.update(
        orders=[{"order_id": 11, "state": bid}, {"order_id": 12, "state": ask}],
        ask_levels=[{"price": 1_100_001, "size": 20}],
    )
    states.append(copy.deepcopy(state))
    state.update(
        last_recv_ns=NOON,
        last_quote_ordinal=1,
        ofi_generation=2,
        ofi_previous_quote_ordinal=1,
        ofi_first_ts_ns=NOON,
        history_ofi_generation=2,
        history_quote_ordinals=[1],
        history_reloads=[[NOON, 0, 0]],
        execution_last_ts_ns=NOON,
        execution_audit={"completed_events": 1, "temporal_resets": 1},
        next_publication_ns=NOON + SECOND,
        watch_since_ns=NOON,
    )
    states.append(copy.deepcopy(state))
    transitions = []
    for index, position in enumerate(positions):
        transitions.append(
            {
                "decoded_position": position,
                "target_transition_ordinal": index + 1,
                "disposition": (
                    "target_reset",
                    "target_snapshot",
                    "target_snapshot",
                    "target_record",
                )[index],
                "snapshot": index in (1, 2),
                "exceptional_closed_clear": False,
                "order_id": (0, 11, 12, 0)[index],
                "before": None,
                "after": (None, bid, ask, None)[index],
                "initialized_before": index != 0,
                "initialized_after": True,
                "last_recv_before": None if index == 0 else WARMUP - SECOND,
                "last_recv_after": NOON if index == 3 else WARMUP - SECOND,
                "event_ordinal": 1 if index == 3 else None,
                "quote_ordinal": 1 if index == 3 else None,
                "publication_ordinal": 1 if index == 3 else None,
                "state_sha256": digest(states[index]),
            }
        )
    audits = []
    for audit in bound["audits"]:
        ordinal = audit["target_candidate_ordinal"]
        audits.append(
            {
                "decoded_position": audit["decoded_position"],
                "disposition": audit["disposition"]
                if ordinal is None
                else transitions[ordinal - 1]["disposition"],
                "instrument_id": audit["instrument_id"],
                "target_candidate_ordinal": ordinal,
                "target_transition_ordinal": ordinal,
                "binding_prefix_sha256": audit["bound_prefix_sha256"],
                "adapter_prefix_sha256": prefixes[audit["decoded_position"]],
            }
        )
    event = {
        "event_ordinal": 1,
        "closing_decoded_position": quote_position,
        "closing_target_transition_ordinal": 4,
        "ts_recv_ns": NOON,
        "target_positions": [quote_position],
        "trade_positions": [],
        "execution_capture_positions": [quote_position],
        "quote_ordinal": 1,
        "adapter_prefix_sha256": prefixes[quote_position],
    }
    event["event_sha256"] = digest(event)
    quote = {
        "quote_ordinal": 1,
        "event_ordinal": 1,
        "decoded_position": quote_position,
        "ts_recv_ns": NOON,
        "bid": 1_000_001,
        "ask": 1_100_001,
        "bid_qty": 10,
        "ask_qty": 20,
        "prior_quote_gap_ns": 0,
        "ofi_generation": 2,
        "bid_depth5": [{"price": 1_000_001, "size": 10}],
        "ask_depth5": [{"price": 1_100_001, "size": 20}],
        "adapter_prefix_sha256": prefixes[quote_position],
    }
    quote["quote_sha256"] = digest(quote)
    publication = {
        "publication_ordinal": 1,
        "quote_ordinal": 1,
        "event_ordinal": 1,
        "decoded_position": quote_position,
        "ts_recv_ns": NOON,
        "adapter_prefix_sha256": prefixes[quote_position],
        "features": idle_features(),
    }
    publication["publication_sha256"] = digest(publication)
    state.update(
        ofi_generation=3, ofi_previous_quote_ordinal=None, ofi_first_ts_ns=None, window_closed=True
    )
    intervals = [
        {
            "start_ns": WARMUP,
            "timer_fired_ns": WARMUP + 5 * SECOND + 1,
            "end_ns": NOON,
            "recovered": True,
            "trigger_decoded_position": quote_position,
        },
        {
            "start_ns": NOON,
            "timer_fired_ns": NOON + 5 * SECOND + 1,
            "end_ns": END,
            "recovered": False,
            "trigger_decoded_position": None,
        },
    ]
    quality = {
        "target_records": 4,
        "snapshot_records": 2,
        "non_snapshot_records": 2,
        "event_after_receive": 0,
        "negative_send_delta": 0,
        "event_after_sending": 0,
        "clamped_delta": 0,
        "clock_disagreement_records": 0,
        "protected_disagreement_records": 0,
        "outside_disagreement_records": 0,
        "min_event_ahead_ns": None,
        "max_event_ahead_ns": None,
        "min_negative_delta_ns": None,
        "samples": [],
    }
    result = {
        "status": protocol["status"],
        "protocol_sha256": protocol_pin,
        "context_sha256": context_pin,
        "binding_protocol_sha256": bound["protocol_sha256"],
        "cursor_protocol_sha256": bound["cursor_protocol_sha256"],
        "fixture_sha256": digest(fixture),
        "fixture": fixture,
        "binding_assessment": bound,
        "audits": audits,
        "transitions": transitions,
        "events": [event],
        "quotes": [quote],
        "publications": [publication],
        "inactivity_intervals": intervals,
        "clock_quality": quality,
        "exceptional_clear_count": 0,
        "terminal_state": state,
        "authority_flags": copy.deepcopy(protocol["authority_flags"]),
    }
    return result | {"assessment_sha256": digest(result)}


def bridge_evidence_body(native, adapter, ts_out):
    packet = expected_protocol()
    context_body = expected_context(ts_out)
    context_pin = digest(context_body)
    previous = digest(
        {
            "domain": "member_publication_native_prefix_seed_v1",
            "bridge_protocol_sha256": PROTOCOL_SHA,
            "bridge_context_sha256": context_pin,
            "native_context_sha256": native["context_sha256"],
            "native_protocol_sha256": native["protocol_sha256"],
            "profile_sha256": native["profile_sha256"],
            "runtime_manifest_sha256": native["runtime_manifest_sha256"],
        }
    )
    prefixes = []
    for occurrence, span in zip(native["occurrences"], native["dbn_framing"]["spans"], strict=True):
        link = {
            "decoded_position": occurrence["decoded_position"],
            "kind": occurrence["kind"],
            "wire_span_ordinal": span["wire_span_ordinal"],
            "decompressed_start": span["decompressed_start"],
            "decompressed_end": span["decompressed_end"],
            "wire_sha256": span["wire_sha256"],
            "wire_fields_sha256": span["wire_fields_sha256"],
            "projection_sha256": occurrence["projection_sha256"],
            "previous_prefix_sha256": previous,
        }
        previous = digest({"domain": "member_publication_native_prefix_link_v1", "link": link})
        prefixes.append(link | {"prefix_sha256": previous})
    publications = []
    for publication in adapter["publications"]:
        link = {
            name: publication[name]
            for name in (
                "publication_ordinal",
                "quote_ordinal",
                "event_ordinal",
                "decoded_position",
                "ts_recv_ns",
                "adapter_prefix_sha256",
                "publication_sha256",
            )
        }
        link["native_prefix_sha256"] = prefixes[publication["decoded_position"] - 1][
            "prefix_sha256"
        ]
        link_hash = digest(
            {
                "domain": "member_publication_link_v1",
                "bridge_protocol_sha256": PROTOCOL_SHA,
                "bridge_context_sha256": context_pin,
                "link": link,
            }
        )
        publications.append(link | {"link_sha256": link_hash})
    result = {
        "status": packet["status"],
        "protocol_sha256": PROTOCOL_SHA,
        "context_sha256": context_pin,
        "context": context_body,
        "native_evidence": native,
        "adapter_assessment": adapter,
        "native_prefixes": prefixes,
        "publication_links": publications,
        "authorities": [[name, False] for name in packet["authority_names"]],
    }
    return result | {"evidence_sha256": digest(result)}


def minimal_case(ts_out=False):
    records = minimal_payloads(ts_out)
    parts = [metadata_part(ts_out)] + [mbo_part(raw, ts_out) for raw in records]
    raw = b"".join(part[0] for part in parts)
    member = raw_frame(raw)
    assert len(raw) == (616 if ts_out else 584)
    assert len(member) == (626 if ts_out else 594)
    native = native_evidence_body(parts, member, raw, ts_out)
    fixture = {
        "context": {
            "input_version": 3,
            "upgrade_policy": "AS_IS",
            "yielded_version": 3,
            "stype_in": "parent",
            "stype_out": "instrument_id",
            "partial": [],
            "limit": None,
            "ts_out": ts_out,
        },
        "payload_bundle": {
            "context": {
                "codec_id": "constructed_mbo_json_v1",
                "schema_version": 1,
                "ts_out_mode": "present" if ts_out else "absent",
            },
            "cursor_fixture": cursor_fixture_body(records, member),
            "payloads": [None, *records],
        },
    }
    adapter = adapter_assessment_body(fixture)
    bridge = bridge_evidence_body(native, adapter, ts_out)
    request = {
        "schema": "native_member_worker_request_v1",
        "operation": "decode",
        "context": expected_context(ts_out)["native_context"],
        "member_hex": member.hex(),
        **{
            "expected_" + name + "_sha256": native[name + "_sha256"]
            for name in ("protocol", "profile", "runtime_manifest", "member", "metadata")
        },
        "execution_manifest_sha256": EXECUTION_SHA,
        "attempt_token": "0" * 64,
    }
    return {
        "member": member,
        "raw": raw,
        "native": native,
        "adapter": adapter,
        "bridge": bridge,
        "request_template": request,
    }


def metadata_with_groups(ts_out, groups):
    """Literal header layout with wire-order groups and separately sorted getters."""
    original, wire, projection = metadata_part(ts_out)
    wire, projection = copy.deepcopy(wire), copy.deepcopy(projection)
    variable = (
        (1).to_bytes(4, "little")
        + _cstr("6E.FUT", 71)
        + bytes(8)
        + len(groups).to_bytes(4, "little")
    )
    logical_groups, wire_groups = [], []
    for symbol, intervals in groups:
        variable += _cstr(symbol, 71) + len(intervals).to_bytes(4, "little")
        logical_intervals, wire_intervals = [], []
        for start, end, instrument in intervals:
            variable += start.to_bytes(4, "little") + end.to_bytes(4, "little")
            variable += _cstr(instrument, 71)
            wire_intervals.append({"start_date": start, "end_date": end, "symbol": instrument})
            logical_intervals.append(
                {
                    "start_date": {
                        "kind": "python_date",
                        "year": start // 10000,
                        "month": start // 100 % 100,
                        "day": start % 100,
                    },
                    "end_date": {
                        "kind": "python_date",
                        "year": end // 10000,
                        "month": end // 100 % 100,
                        "day": end % 100,
                    },
                    "symbol": instrument,
                }
            )
        wire_groups.append(
            {"raw_symbol": symbol, "interval_count": len(intervals), "intervals": wire_intervals}
        )
        logical_groups.append({"raw_symbol": symbol, "intervals": logical_intervals})
    padding = bytes(-(112 + len(variable)) % 8)
    header_size = 112 + len(variable) + len(padding)
    wire.update(
        length_body=header_size - 8,
        mappings_count=len(groups),
        mappings=wire_groups,
        alignment_padding_bytes=list(padding),
    )
    projection["mappings"] = sorted(logical_groups, key=lambda group: group["raw_symbol"])
    fixed = original[:4] + (header_size - 8).to_bytes(4, "little") + original[8:112]
    return fixed + variable + padding, wire, projection


def native_case_from_records(records, ts_out=False, *, header=None, two_frames=False):
    """Complete independent native body, also usable for bridge-only refusals."""
    parts = [metadata_part(ts_out) if header is None else header]
    parts.extend(mbo_part(raw, ts_out) for raw in records)
    raw = b"".join(part[0] for part in parts)
    cuts = [len(raw) // 2, len(raw)] if two_frames else [len(raw)]
    chunks, frames, start, compressed_start = [], [], 0, 0
    for ordinal, end in enumerate(cuts, 1):
        chunk = raw[start:end]
        compressed = raw_frame(chunk)
        chunks.append(compressed)
        frames.append(
            {
                "frame_ordinal": ordinal,
                "compressed_start": compressed_start,
                "compressed_end": compressed_start + len(compressed),
                "decompressed_start": start,
                "decompressed_end": end,
                "compressed_span_sha256": raw_digest(compressed),
                "decompressed_span_sha256": raw_digest(chunk),
            }
        )
        start, compressed_start = end, compressed_start + len(compressed)
    member = b"".join(chunks)
    native = native_evidence_body(parts, member, raw, ts_out)
    native["zstd_framing"]["frames"] = frames
    frame_body = {
        key: value for key, value in native["zstd_framing"].items() if key != "report_sha256"
    }
    native["zstd_framing"]["report_sha256"] = digest(frame_body)
    native["terminal"]["frame_count"] = len(frames)
    native["terminal"]["zstd_framing_sha256"] = native["zstd_framing"]["report_sha256"]
    native["evidence_sha256"] = digest(
        {key: value for key, value in native.items() if key != "evidence_sha256"}
    )
    request = {
        "schema": "native_member_worker_request_v1",
        "operation": "decode",
        "context": expected_context(ts_out)["native_context"],
        "member_hex": member.hex(),
        **{
            "expected_" + name + "_sha256": native[name + "_sha256"]
            for name in ("protocol", "profile", "runtime_manifest", "member", "metadata")
        },
        "execution_manifest_sha256": EXECUTION_SHA,
        "attempt_token": "0" * 64,
    }
    return {"member": member, "raw": raw, "native": native, "request_template": request}


def rehash_mock_native_declarations(body):
    """Repair declaration digests only; this never proves original wire bytes."""
    for occurrence in body["occurrences"]:
        occurrence["projection_sha256"] = digest(occurrence["projection"])
    for span in body["dbn_framing"]["spans"]:
        span["wire_fields_sha256"] = digest(span["wire_fields"])
    body["metadata_sha256"] = body["occurrences"][0]["projection_sha256"]
    for family in ("dbn_framing", "zstd_framing"):
        report = body[family]
        report["report_sha256"] = digest(
            {key: value for key, value in report.items() if key != "report_sha256"}
        )
        body["terminal"][family + "_sha256"] = report["report_sha256"]
    body["evidence_sha256"] = digest(
        {key: value for key, value in body.items() if key != "evidence_sha256"}
    )


VARIANT_NAMES = (
    "consumed-foreign-a",
    "consumed-foreign-b",
    "suffix-foreign-a",
    "suffix-foreign-b",
    "two-physical-frames",
    "header-active-first",
    "header-inactive-first",
    "consumed-unknown-action",
    "consumed-unknown-side",
    "consumed-ascii-nul-action",
    "consumed-ascii-del-side",
    "consumed-foreign-extrema",
)


def variant_case(name, ts_out=False):
    """Only the literal four-target idle path; no generalized numerical engine."""
    assert name in VARIANT_NAMES
    records = minimal_payloads(ts_out)
    header = metadata_part(ts_out)
    if name.startswith(("consumed-", "suffix-foreign-")):
        foreign = copy.deepcopy(records[-1])
        foreign.update(
            instrument_id=99,
            order_id=71 if name.endswith("a") else 72,
            price=1_200_001,
            size=3,
            sequence=9,
        )
        received = NOON - 1 if name.startswith("consumed") else NOON + SECOND
        foreign.update(
            ts_event=received - 1, ts_recv=received, ts_out=received + 20 if ts_out else None
        )
        if name == "consumed-unknown-action":
            foreign["action"] = "?"
        if name == "consumed-unknown-side":
            foreign["side"] = "?"
        if name == "consumed-ascii-nul-action":
            foreign["action"] = "\x00"
        if name == "consumed-ascii-del-side":
            foreign["side"] = "\x7f"
        if name == "consumed-foreign-extrema":
            foreign.update(
                publisher_id=(1 << 16) - 1,
                instrument_id=(1 << 32) - 1,
                ts_event=(1 << 63) - 1,
                order_id=(1 << 64) - 1,
                price=-(1 << 63),
                size=(1 << 32) - 1,
                flags=255,
                channel_id=255,
                ts_recv=(1 << 63) - 1,
                ts_in_delta=-(1 << 31),
                sequence=(1 << 32) - 1,
                ts_out=(1 << 63) - 1 if ts_out else None,
                action="?",
                side="?",
            )
        records.insert(3 if name.startswith("consumed") else 4, foreign)
    if name.startswith("header-"):
        groups = [
            ("6EM5", [(20250407, 20250408, "0007")]),
            ("6EZ5", [(20251201, 20251202, "0042")]),
        ]
        if name == "header-inactive-first":
            groups.reverse()
        header = metadata_with_groups(ts_out, groups)
    case = native_case_from_records(
        records,
        ts_out,
        header=header,
        two_frames=name == "two-physical-frames",
    )
    cursor_fixture = cursor_fixture_body(records, case["member"])
    cursor_fixture["header"]["mappings"] = [
        {
            "contract": group["raw_symbol"],
            "intervals": [
                {
                    "start_date": f"{interval['start_date'] // 10000:04d}-"
                    f"{interval['start_date'] // 100 % 100:02d}-"
                    f"{interval['start_date'] % 100:02d}",
                    "end_date": f"{interval['end_date'] // 10000:04d}-"
                    f"{interval['end_date'] // 100 % 100:02d}-"
                    f"{interval['end_date'] % 100:02d}",
                    "instrument_symbol": interval["symbol"],
                }
                for interval in group["intervals"]
            ],
        }
        for group in header[1]["mappings"]
    ]
    fixture = {
        "context": {
            "input_version": 3,
            "upgrade_policy": "AS_IS",
            "yielded_version": 3,
            "stype_in": "parent",
            "stype_out": "instrument_id",
            "partial": [],
            "limit": None,
            "ts_out": ts_out,
        },
        "payload_bundle": {
            "context": {
                "codec_id": "constructed_mbo_json_v1",
                "schema_version": 1,
                "ts_out_mode": "present" if ts_out else "absent",
            },
            "cursor_fixture": cursor_fixture,
            "payloads": [None, *records],
        },
    }
    case["adapter"] = adapter_assessment_body(fixture)
    case["bridge"] = bridge_evidence_body(case["native"], case["adapter"], ts_out)
    return case


def native_object(provider, body, schema_name="MemberDecodeEvidence"):
    """Instantiate the independently declared literal schema, never reflect code."""
    schemas = expected_protocol()["dependencies"]["native"]["schemas"]

    def build(value, name):
        schema = schemas[name]
        if schema["kind"] == "record":
            assert type(value) is dict
            assert set(value) == {field for field, _ in schema["fields"]}
            record_name = "MemberDecodeContext" if name == "Context" else name
            record_type = getattr(provider, record_name)
            return record_type(*(build(value[field], child) for field, child in schema["fields"]))
        if schema["kind"] == "tuple":
            return tuple(build(item, schema["item"]) for item in value)
        if schema["kind"] == "fixed_tuple":
            if "literal_items" in schema:
                assert value == schema["literal_items"]
                return tuple(value)
            return tuple(
                build(item, child) for item, child in zip(value, schema["items"], strict=True)
            )
        if schema["kind"] == "union":
            if value is None:
                assert "Null" in schema["alternatives"]
                return None
            if type(value) is dict:
                matches = [
                    child
                    for child in schema["alternatives"]
                    if schemas[child]["kind"] == "record"
                    and {field for field, _ in schemas[child]["fields"]} == set(value)
                ]
                assert len(matches) == 1
                return build(value, matches[0])
            return value
        return value

    return build(body, schema_name)


def cursor_object(cursor, body):
    header = body["header"]
    groups = tuple(
        cursor.MappingGroup(
            group["contract"],
            tuple(cursor.MappingInterval(**interval) for interval in group["intervals"]),
        )
        for group in header["mappings"]
    )
    declared = cursor.DeclaredHeader(
        header["dataset"],
        header["schema"],
        tuple(header["symbols"]),
        tuple(header["not_found"]),
        header["start_ns"],
        header["end_ns"],
        groups,
    )
    return cursor.CursorFixture(
        body["fixture_id"],
        body["source_session"],
        body["utc_date"],
        body["contract"],
        declared,
        body["asserted_member_sha256"],
        body["declared_item_count"],
        tuple(cursor.DecodedItem(**item) for item in body["items"]),
    )


def payload_bundle_object(binding, cursor, bundle_body):
    fixture = cursor_object(cursor, bundle_body["cursor_fixture"])
    return binding.PayloadBundle(
        binding.PayloadContext(**bundle_body["context"]),
        fixture,
        tuple(
            None if item is None else binding.MboPayload(**item) for item in bundle_body["payloads"]
        ),
    )


def binding_object(binding, cursor, body):
    bundle = payload_bundle_object(binding, cursor, body["bundle"])
    old = body["cursor_assessment"]
    old_fixture = cursor_object(cursor, old["fixture"])
    old_result = cursor.CursorAssessment(
        old["status"],
        old["protocol_sha256"],
        old["fixture_sha256"],
        old_fixture,
        old["mapped_instrument_id"],
        old["decoded_item_count"],
        old["target_candidate_count"],
        old["foreign_count"],
        tuple(cursor.CursorAudit(**audit) for audit in old["audits"]),
        tuple(old["authority_flags"].items()),
        old["assessment_sha256"],
    )
    values = dict(body)
    values.update(
        bundle=bundle,
        cursor_assessment=old_result,
        audits=tuple(binding.PayloadAudit(**audit) for audit in body["audits"]),
        authority_flags=tuple(body["authority_flags"].items()),
    )
    return binding.BindingAssessment(**values)


def state_object(adapter, body):
    values = dict(body)
    values["orders"] = tuple(
        adapter.OrderEntry(entry["order_id"], adapter.OrderState(**entry["state"]))
        for entry in body["orders"]
    )
    for name in ("bid_levels", "ask_levels"):
        values[name] = tuple(adapter.PriceLevel(**level) for level in body[name])
    for name in (
        "pending_target_positions",
        "pending_trade_positions",
        "execution_capture_positions",
        "history_quote_ordinals",
    ):
        values[name] = tuple(body[name])
    for name in (
        "flow_events",
        "ofi_events",
        "bid_depletions",
        "ask_depletions",
        "history_reloads",
        "bid_credits",
        "ask_credits",
    ):
        values[name] = tuple(tuple(entry) for entry in body[name])
    values["execution_events"] = tuple(
        (time, tuple(sorted(metrics.items()))) for time, metrics in body["execution_events"]
    )
    for name in ("execution_totals", "execution_audit"):
        values[name] = tuple(sorted(body[name].items()))
    return adapter.ReconstructedState(**values)


def adapter_object(adapter, binding, cursor, body):
    values = dict(body)
    bound = binding_object(binding, cursor, body["binding_assessment"])
    original_context = dict(body["fixture"]["context"])
    original_context["partial"] = tuple(original_context["partial"])
    original_bundle = payload_bundle_object(binding, cursor, body["fixture"]["payload_bundle"])
    values["fixture"] = adapter.AdapterFixture(
        adapter.AdapterContext(**original_context), original_bundle
    )
    values["binding_assessment"] = bound
    values["audits"] = tuple(adapter.AdapterAudit(**item) for item in body["audits"])
    transitions = []
    for item in body["transitions"]:
        converted = dict(item)
        for field in ("before", "after"):
            converted[field] = None if item[field] is None else adapter.OrderState(**item[field])
        transitions.append(adapter.TargetTransition(**converted))
    values["transitions"] = tuple(transitions)
    values["events"] = tuple(
        adapter.EventWitness(
            **(
                item
                | {
                    field: tuple(item[field])
                    for field in (
                        "target_positions",
                        "trade_positions",
                        "execution_capture_positions",
                    )
                }
            )
        )
        for item in body["events"]
    )
    values["quotes"] = tuple(
        adapter.QuoteWitness(
            **(
                item
                | {
                    field: tuple(adapter.PriceLevel(**level) for level in item[field])
                    for field in ("bid_depth5", "ask_depth5")
                }
            )
        )
        for item in body["quotes"]
    )
    values["publications"] = tuple(
        adapter.FeaturePublication(
            **(item | {"features": tuple(tuple(pair) for pair in item["features"])})
        )
        for item in body["publications"]
    )
    values["inactivity_intervals"] = tuple(
        adapter.InactivityInterval(**item) for item in body["inactivity_intervals"]
    )
    values["clock_quality"] = adapter.ClockQuality(
        **(
            body["clock_quality"]
            | {
                "samples": tuple(
                    adapter.ClockSample(**item) for item in body["clock_quality"]["samples"]
                )
            }
        )
    )
    values["terminal_state"] = state_object(adapter, body["terminal_state"])
    values["authority_flags"] = tuple(body["authority_flags"].items())
    return adapter.AdapterAssessment(**values)


def bridge_object(bridge, native, adapter, binding, cursor, body):
    values = dict(body)
    values["context"] = bridge.BridgeContext(
        body["context"]["fixture_id"],
        body["context"]["source_session"],
        native_object(native, body["context"]["native_context"], "Context"),
    )
    values["native_evidence"] = native_object(native, body["native_evidence"])
    values["adapter_assessment"] = adapter_object(
        adapter, binding, cursor, body["adapter_assessment"]
    )
    values["native_prefixes"] = tuple(
        bridge.NativePrefixLink(**item) for item in body["native_prefixes"]
    )
    values["publication_links"] = tuple(
        bridge.PublicationLink(**item) for item in body["publication_links"]
    )
    values["authorities"] = tuple(tuple(item) for item in body["authorities"])
    return bridge.BridgeEvidence(**values)


def record_fields(bridge, native, adapter, binding, cursor):
    """Literal schema field registry for comparing actual objects, not an oracle."""
    packet = expected_protocol()
    result = {
        getattr(bridge, name): tuple(fields) for name, fields in packet["dataclass_fields"].items()
    }
    for module, dependency in ((adapter, "adapter"), (binding, "binding")):
        result.update(
            {
                getattr(module, name): tuple(fields)
                for name, fields in packet["dependencies"][dependency]["dataclass_fields"].items()
            }
        )
    for name, schema in packet["dependencies"]["native"]["schemas"].items():
        if schema["kind"] == "record":
            name = "MemberDecodeContext" if name == "Context" else name
            result[getattr(native, name)] = tuple(field for field, _ in schema["fields"])
    cursor_fields = {
        "MappingInterval": ("start_date", "end_date", "instrument_symbol"),
        "MappingGroup": ("contract", "intervals"),
        "DeclaredHeader": (
            "dataset",
            "schema",
            "symbols",
            "not_found",
            "start_ns",
            "end_ns",
            "mappings",
        ),
        "DecodedItem": ("decoded_position", "kind", "instrument_id", "payload_sha256"),
        "CursorFixture": (
            "fixture_id",
            "source_session",
            "utc_date",
            "contract",
            "header",
            "asserted_member_sha256",
            "declared_item_count",
            "items",
        ),
        "CursorAudit": (
            "decoded_position",
            "disposition",
            "instrument_id",
            "target_candidate_ordinal",
            "item_sha256",
            "prefix_sha256",
        ),
        "CursorAssessment": (
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
    }
    result.update({getattr(cursor, name): fields for name, fields in cursor_fields.items()})
    return result


def assert_exact_tree(actual, expected, fields, path="root"):
    assert type(actual) is type(expected), (path, type(actual), type(expected))
    if type(expected) in fields:
        for name in fields[type(expected)]:
            assert_exact_tree(
                getattr(actual, name), getattr(expected, name), fields, path + "." + name
            )
    elif type(expected) is tuple:
        assert len(actual) == len(expected), path
        for index, (left, right) in enumerate(zip(actual, expected, strict=True)):
            assert_exact_tree(left, right, fields, f"{path}[{index}]")
    else:
        assert type(expected) in (str, int, float, bool, type(None)), path
        assert canonical(actual) == canonical(expected), (path, actual, expected)


def observed_body(value, fields, field_name=None):
    """Explicit registered fields only; retain every actual scalar representation."""
    if type(value) in fields:
        return {
            name: observed_body(getattr(value, name), fields, name) for name in fields[type(value)]
        }
    if type(value) is tuple:
        if field_name in ("authority_flags", "execution_totals", "execution_audit"):
            assert len({pair[0] for pair in value}) == len(value)
            return {key: observed_body(item, fields) for key, item in value}
        if field_name == "execution_events":
            return [
                [time, {key: observed_body(item, fields) for key, item in metrics}]
                for time, metrics in value
            ]
        return [observed_body(item, fields) for item in value]
    assert type(value) in (str, int, float, bool, type(None))
    return value


RECEIPT_KEYS = {
    "schema",
    "operation",
    "execution_manifest_sha256",
    "attempt_token",
    "started_utc",
    "finished_utc",
    "elapsed_ns",
    "request",
    "parent",
    "child",
    "command",
    "mapping",
    "limits",
    "job",
    "channels",
    "implementation_checks",
    "response",
    "exit",
    "termination",
    "cleanup",
    "outcome",
}
LIMITS = {
    "limit_flags": 8974,
    "active_process_limit": 1,
    "process_memory_bytes": 268435456,
    "job_memory_bytes": 268435456,
    "process_user_time_100ns": 50000000,
    "job_user_time_100ns": 50000000,
}
PYTHON = "C:/Users/pabta/AppData/Local/Programs/Python/Python312/python.exe"
WINDOW_START = datetime(2026, 10, 15, 6, 59, 8, tzinfo=UTC)
HARD_END = datetime(2026, 10, 15, 14, 59, 8, tzinfo=UTC)


def exact_keys(value, names):
    assert type(value) is dict and set(value) == set(names)


ADAPTER_REFUSAL_VARIANTS = (
    "pending-N-then-reset",
    "pending-T-then-reset",
    "pending-N-then-snapshot",
    "pending-T-then-snapshot",
    "incomplete-N-suffix",
    "incomplete-T-suffix",
    "missing-initial-reset",
    "ordinary-quality-8",
    "ordinary-quality-4",
    "ordinary-quality-64",
    "ordinary-quality-16",
    "snapshot-quality-4",
    "snapshot-quality-64",
    "snapshot-quality-16",
    "window-snapshot",
    "window-reset",
    "window-event-ahead",
    "window-negative-delta",
    "receive-regression",
    "target-before-day",
    "target-at-day-end",
)


def adapter_refusal_case(variant, ts_out):
    """Independent native-valid bytes; held adapter text 3206–3335 says refuse.

    No old test helper is imported. There is intentionally no expected
    successful adapter/bridge body for these complete refusal declarations.
    """
    records = minimal_payloads(ts_out)

    def row(action="N", side="N", recv=NOON + SECOND, **changes):
        result = dict(records[-1])
        result.update(
            action=action,
            side=side,
            ts_recv=recv,
            ts_event=recv - 1,
            ts_out=recv + 20 if ts_out else None,
            sequence=9,
        )
        result.update(changes)
        return result

    if variant.startswith("pending-"):
        action = variant.split("-")[1]
        records = records[:3] + [
            row(
                action,
                "B" if action == "T" else "N",
                NOON - 2 * SECOND,
                price=1_100_000,
                size=1,
                flags=0,
            )
        ]
        incoming = (
            row("R", recv=NOON - SECOND, flags=0)
            if variant.endswith("reset")
            else row("A", "B", NOON - SECOND, order_id=88, price=900_001, size=1, flags=32)
        )
        records.append(incoming)
    elif variant.startswith("incomplete-"):
        action = variant.split("-")[1]
        records.append(row(action, "B" if action == "T" else "N", price=1_100_000, size=1, flags=0))
    elif variant == "missing-initial-reset":
        records = records[1:]
    elif variant.startswith("ordinary-quality-"):
        records[-1]["flags"] = 128 | int(variant.rsplit("-", 1)[1])
    elif variant.startswith("snapshot-quality-"):
        records[1]["flags"] = 32 | int(variant.rsplit("-", 1)[1])
    elif variant == "window-snapshot":
        records.append(row("A", "B", order_id=88, price=900_001, size=1, flags=32))
    elif variant == "window-reset":
        records.append(row("R", flags=0))
    elif variant == "window-event-ahead":
        records.append(row(ts_event=NOON + SECOND + 1))
    elif variant == "window-negative-delta":
        records.append(row(ts_in_delta=-1))
    elif variant == "receive-regression":
        records.append(row(recv=NOON - 1))
    elif variant in ("target-before-day", "target-at-day-end"):
        recv = DAY - 1 if variant == "target-before-day" else DAY + 86400 * SECOND
        records[0].update(ts_recv=recv, ts_event=recv - 1, ts_out=recv + 20 if ts_out else None)
    else:
        raise AssertionError("unregistered adapter refusal variant")
    return native_case_from_records(records, ts_out)


PROVIDER_REFUSAL_VARIANTS = ("corrupt-compression-magic", "wrong-metadata-pin")


def provider_refusal_case(variant, ts_out):
    """Full independent malformed request; no successful decoded-body assertion."""
    assert variant in PROVIDER_REFUSAL_VARIANTS
    original = minimal_case(ts_out)
    member = original["member"]
    request = copy.deepcopy(original["request_template"])
    if variant == "corrupt-compression-magic":
        member = bytes((member[0] ^ 1,)) + member[1:]
        request.update(member_hex=member.hex(), expected_member_sha256=raw_digest(member))
    else:
        assert request["expected_metadata_sha256"] != "0" * 64
        request["expected_metadata_sha256"] = "0" * 64
    response = {
        "schema": "native_member_worker_response_v1",
        "attempt_token": "0" * 64,
        "request_sha256": digest(request),
        "execution_manifest_sha256": EXECUTION_SHA,
        "status": "refused",
        "evidence": None,
        "failure_kind": "invalid_member",
    }
    return {
        "member": member,
        "request_template": request,
        "response_template": response,
        "expected_exit_code": 2,
        "expected_outcome": "input_refused",
    }


def exact_uint(value, maximum=(1 << 64) - 1, minimum=0):
    assert type(value) is int and minimum <= value <= maximum


def exact_json(actual, expected):
    """Compare fixed receipt subtrees without bool/int or container aliases."""
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert all(type(key) is str for key in actual)
        assert set(actual) == set(expected)
        for key, value in expected.items():
            exact_json(actual[key], value)
    elif type(expected) is list:
        assert len(actual) == len(expected)
        for actual_value, expected_value in zip(actual, expected, strict=True):
            exact_json(actual_value, expected_value)
    else:
        assert canonical(actual) == canonical(expected)


def response_frame(body):
    raw = canonical(body)
    return b"NMRES001" + len(raw).to_bytes(4, "little") + raw


def expected_execution_manifest():
    raw = (ROOT / "src/ai_trader/research/_native_member_execution_v1.json").read_bytes()
    assert len(raw) <= 65536 and raw_digest(raw) == EXECUTION_SHA
    result = json.loads(raw)
    assert canonical(result) == raw
    return result


def assert_native_receipt(response, receipt, template, expected_native):
    """Full independent success/refusal receipt; None means exact input refusal."""
    refused = expected_native is None
    manifest = expected_execution_manifest()
    exact_keys(receipt, RECEIPT_KEYS)
    exact_json(receipt["schema"], "native_member_provider_owned_receipt_v1")
    exact_json(receipt["operation"], "decode")
    exact_json(receipt["execution_manifest_sha256"], EXECUTION_SHA)
    token = receipt["attempt_token"]
    assert type(token) is str and re.fullmatch("[0-9a-f]{64}", token)
    assert token != "0" * 64
    times = []
    for name in ("started_utc", "finished_utc"):
        text = receipt[name]
        assert type(text) is str
        stamp = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
        assert stamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ") == text
        times.append(stamp)
    assert WINDOW_START <= times[0] <= times[1] <= HARD_END
    exact_uint(receipt["elapsed_ns"])
    request = copy.deepcopy(template)
    request["attempt_token"] = token
    request_raw = canonical(request)
    exact_json(
        receipt["request"],
        {
            "canonical_bytes": len(request_raw),
            "canonical_sha256": raw_digest(request_raw),
            "member_bytes": len(bytes.fromhex(template["member_hex"])),
            "member_sha256": template["expected_member_sha256"],
        },
    )
    parent, child = receipt["parent"], receipt["child"]
    exact_keys(parent, ("pid", "creation_filetime", "image"))
    exact_keys(
        child,
        (
            "pid",
            "tid",
            "parent_pid",
            "creation_filetime",
            "image",
            "in_job_before_resume",
            "resume_previous_count",
        ),
    )
    exact_uint(parent["pid"], (1 << 32) - 1, 1)
    exact_uint(parent["creation_filetime"], minimum=1)
    for name in ("pid", "tid", "parent_pid"):
        exact_uint(child[name], (1 << 32) - 1, 1)
    exact_uint(child["creation_filetime"], minimum=parent["creation_filetime"])
    assert child["pid"] != parent["pid"] and child["parent_pid"] == parent["pid"]
    for identity in (parent, child):
        assert type(identity["image"]) is str
        assert identity["image"].replace("\\", "/").casefold() == PYTHON.casefold()
    assert child["in_job_before_resume"] is True
    assert type(child["resume_previous_count"]) is int and child["resume_previous_count"] == 1
    command = receipt["command"]
    exact_keys(command, ("executable", "argv", "cwd", "environment"))
    assert type(command["executable"]) is str and type(command["cwd"]) is str
    assert command["executable"].replace("\\", "/").casefold() == PYTHON.casefold()
    argv = command["argv"]
    assert type(argv) is list and len(argv) == 9
    assert all(type(value) is str for value in argv)
    assert argv[0].replace("\\", "/").casefold() == PYTHON.casefold()
    exact_json(argv[1:4], ["-I", "-S", "-B"])
    assert Path(argv[4]) == ROOT / "src/ai_trader/research/_native_member_worker.py"
    assert argv[5] == "--mapping-handle"
    assert type(argv[6]) is str and re.fullmatch("[1-9][0-9]{0,19}", argv[6])
    exact_uint(int(argv[6]), minimum=1)
    exact_json(argv[7:], ["--mapping-size", "1048576"])
    assert Path(command["cwd"]) == ROOT
    exact_keys(command["environment"], ("SystemRoot",))
    assert type(command["environment"]["SystemRoot"]) is str
    exact_json(
        receipt["mapping"],
        {
            "bytes": 1048576,
            "inherited_access": "FILE_MAP_READ",
            "writable_parent_view_unmapped": True,
            "write_capable_parent_handle_closed": True,
            "explicit_inherited_handle_count": 4,
        },
    )
    exact_keys(receipt["limits"], ("configured", "queried_before_resume", "queried_final"))
    for item in receipt["limits"].values():
        exact_json(item, LIMITS)
        for value in item.values():
            exact_uint(value)
    job = receipt["job"]
    exact_keys(
        job,
        (
            "pids_initial",
            "pids_before_resume",
            "pids_final",
            "accounting_initial",
            "accounting_before_resume",
            "accounting_final",
        ),
    )
    exact_json(job["pids_initial"], [])
    exact_json(job["pids_before_resume"], [child["pid"]])
    exact_json(job["pids_final"], [])
    for name in ("accounting_initial", "accounting_before_resume", "accounting_final"):
        exact_keys(
            job[name],
            (
                "total_user_time_100ns",
                "total_kernel_time_100ns",
                "total_processes",
                "active_processes",
                "terminated_processes",
                "page_faults",
            ),
        )
        for value in job[name].values():
            exact_uint(value)
        assert job[name]["terminated_processes"] <= job[name]["total_processes"]
    assert job["accounting_initial"]["total_processes"] == 0
    assert job["accounting_before_resume"]["active_processes"] == 1
    assert job["accounting_final"]["active_processes"] == 0
    # The queried cumulative counter is not the concurrent active-process count.
    # Preserve its complete observation; owned identity and final emptiness above
    # establish this call's child lifecycle, not an exact-one cumulative claim.
    assert job["accounting_final"]["total_processes"] >= 1
    expected_artifacts = [
        {name: row[name] for name in ("logical_id", "raw_bytes", "raw_sha256")}
        for row in manifest["artifacts"]
    ]
    exact_json(
        receipt["implementation_checks"],
        {
            "before": expected_artifacts,
            "after": expected_artifacts,
        },
    )
    expected_response = {
        "schema": "native_member_worker_response_v1",
        "attempt_token": token,
        "request_sha256": raw_digest(request_raw),
        "execution_manifest_sha256": EXECUTION_SHA,
        "status": "refused" if refused else "complete",
        "evidence": expected_native,
        "failure_kind": "invalid_member" if refused else None,
    }
    exact_json(response, expected_response)
    stdout = response_frame(expected_response)
    exact_json(
        receipt["channels"],
        {
            "stdout": {
                "retained_bytes": len(stdout),
                "raw_sha256": raw_digest(stdout),
                "eof": True,
                "hash_scope": "complete",
            },
            "stderr": {
                "retained_bytes": 0,
                "raw_sha256": raw_digest(b""),
                "eof": True,
                "hash_scope": "complete",
            },
        },
    )
    assert len(stdout) <= 4194304
    exact_json(
        receipt["response"],
        {
            "parsed_body": expected_response,
            "canonical_bytes": len(canonical(expected_response)),
            "canonical_sha256": digest(expected_response),
            "binding_validated": True,
            "evidence_validated": True,
        },
    )
    exited = receipt["exit"]
    exact_keys(
        exited,
        (
            "created",
            "resumed",
            "observed",
            "code",
            "creation_filetime",
            "exit_filetime",
            "user_time_100ns",
            "kernel_time_100ns",
        ),
    )
    assert exited["created"] is True and exited["resumed"] is True and exited["observed"] is True
    assert type(exited["code"]) is int and exited["code"] == (2 if refused else 0)
    exact_uint(exited["creation_filetime"], minimum=1)
    assert exited["creation_filetime"] == child["creation_filetime"]
    exact_uint(exited["exit_filetime"], minimum=child["creation_filetime"])
    exact_uint(exited["user_time_100ns"])
    exact_uint(exited["kernel_time_100ns"])
    assert receipt["termination"] is None
    exact_json(receipt["outcome"], "input_refused" if refused else "complete")
    cleanup = receipt["cleanup"]
    exact_keys(cleanup, ("completed", "closed_handles", "unmapped_views", "errors"))
    assert cleanup["completed"] is True
    exact_json(cleanup["errors"], [])
    assert type(cleanup["closed_handles"]) is list
    assert all(type(value) is str for value in cleanup["closed_handles"])
    assert len(set(cleanup["closed_handles"])) == len(cleanup["closed_handles"])
    assert {
        "job",
        "process",
        "thread",
        "request_write",
        "request_read",
        "stdout_read",
        "stdout_write",
        "stderr_read",
        "stderr_write",
        "nul",
    } <= set(cleanup["closed_handles"])
    assert "artifact_harmless_worker" not in cleanup["closed_handles"]
    assert type(cleanup["unmapped_views"]) is list and "parent_write" in cleanup["unmapped_views"]
    assert all(type(value) is str for value in cleanup["unmapped_views"])
