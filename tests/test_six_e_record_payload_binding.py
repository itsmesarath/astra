"""Independent invented-body contract tests; no native or historical input."""

import copy
import hashlib
import importlib
import inspect
import json
from dataclasses import FrozenInstanceError, replace

import pytest

from ai_trader.research import six_e_native_cursor_metadata as cursor

U64 = 2**64 - 1
S64_MIN, S64_MAX = -(2**63), 2**63 - 1
U32 = 2**32 - 1
BODY_FIELDS = (
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
)
OLD_FLAGS = (
    "account_authenticated",
    "book_application_verified",
    "broker_economics_measured",
    "byte_offsets_verified",
    "calendar_authenticated",
    "decoded_source_authenticated",
    "event_closure_verified",
    "execution_allowed",
    "feature_derivation_verified",
    "funding_authenticated",
    "historical_access_allowed",
    "historical_validation_allowed",
    "mapping_authenticated",
    "model_call_allowed",
    "native_decoding_verified",
    "native_eof_verified",
    "native_target_ordinals_verified",
    "promotion_allowed",
    "publication_cursor_verified",
    "runtime_authenticated",
    "scoring_allowed",
    "source_authenticated",
    "storage_resume_allowed",
    "strategy_integration_allowed",
    "trading_enabled",
    "training_allowed",
)
NEW_FLAGS = (
    "account_authenticated",
    "book_application_verified",
    "broker_economics_measured",
    "byte_offsets_verified",
    "calendar_authenticated",
    "codec_context_authenticated",
    "decoded_source_authenticated",
    "event_closure_verified",
    "execution_allowed",
    "feature_derivation_verified",
    "funding_authenticated",
    "historical_access_allowed",
    "historical_validation_allowed",
    "mapping_authenticated",
    "model_call_allowed",
    "native_decoding_verified",
    "native_eof_verified",
    "native_header_verified",
    "native_payloads_verified",
    "native_record_semantics_verified",
    "native_target_ordinals_verified",
    "original_bytes_verified",
    "promotion_allowed",
    "publication_cursor_verified",
    "runtime_authenticated",
    "scoring_allowed",
    "source_authenticated",
    "storage_resume_allowed",
    "strategy_integration_allowed",
    "trading_enabled",
    "training_allowed",
)
SCHEMAS = {
    "PayloadContext": ("codec_id", "schema_version", "ts_out_mode"),
    "MboPayload": BODY_FIELDS,
    "PayloadBundle": ("context", "cursor_fixture", "payloads"),
    "PayloadAudit": (
        "decoded_position",
        "disposition",
        "instrument_id",
        "target_candidate_ordinal",
        "payload_sha256",
        "cursor_item_sha256",
        "cursor_prefix_sha256",
        "bound_prefix_sha256",
    ),
    "BindingAssessment": (
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
}
INTEGER_BOUNDS = {
    "publisher_id": (0, U64),
    "instrument_id": (0, U32),
    "ts_event": (S64_MIN, S64_MAX),
    "order_id": (0, U64),
    "price": (S64_MIN, S64_MAX),
    "size": (0, U64),
    "ts_recv": (S64_MIN, S64_MAX),
    "flags": (0, U64),
    "channel_id": (0, U64),
    "ts_in_delta": (S64_MIN, S64_MAX),
    "sequence": (0, U64),
    "ts_out": (S64_MIN, S64_MAX),
    "rtype": (0, U64),
    "record_size": (1, 65_536),
}


class IntAlias(int):
    pass


class StrAlias(str):
    pass


class TupleAlias(tuple):
    pass


def canonical(body):
    return json.dumps(
        body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(body):
    return hashlib.sha256(canonical(body)).hexdigest()


def old_protocol_body():
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
        "max_instrument_id": U32,
        "decoded_position_origin": 1,
        "target_candidate_ordinal_origin": 1,
        "header_included": True,
        "payload_pins": "opaque_caller_assertions",
        "prefix_complete_member_pin": "excluded",
        "authority_flags": dict.fromkeys(OLD_FLAGS, False),
    }


def protocol_body():
    return {
        "version": "constructed_record_payload_binding_v1",
        "scope": "invented_complete_mbo_json_bodies_and_contextual_cursor_binding_only",
        "status": "constructed_record_payload_binding_not_native_verification",
        "codec_id": "constructed_mbo_json_v1",
        "schema_version": 1,
        "ts_out_modes": ["absent", "present"],
        "record_field_order": list(BODY_FIELDS),
        "integer_bounds": {name: list(pair) for name, pair in INTEGER_BOUNDS.items()},
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
        "cursor_protocol_sha256": digest(old_protocol_body()),
        "cursor_source_sha256": "c7bc0102073fa61f1d69411479331cf1e434616cb80faa6bbc266377745dcf91",
        "dataclass_fields": {name: list(names) for name, names in SCHEMAS.items()},
        "authority_flags": dict.fromkeys(NEW_FLAGS, False),
    }


def context_body(mode="absent"):
    return {"codec_id": "constructed_mbo_json_v1", "schema_version": 1, "ts_out_mode": mode}


def record_body(instrument=7, mode="absent", **changes):
    body = {
        "publisher_id": 2**53 + 1,
        "instrument_id": instrument,
        "ts_event": -17,
        "order_id": U64,
        "price": -(2**53) - 1,
        "size": 0,
        "action": "\x00",
        "side": "\x7f",
        "ts_recv": -29,
        "flags": 65_535,
        "channel_id": 42,
        "ts_in_delta": S64_MIN,
        "sequence": 2**53 - 1,
        "ts_out": None if mode == "absent" else -9,
        "rtype": 18,
        "record_size": 1,
    }
    body.update(changes)
    return body


def fixture_body(bodies, *, member="1" * 64, mappings=None):
    if mappings is None:
        mappings = [
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
        ]
    return {
        "fixture_id": "synthetic-payload-binding",
        "source_session": "synthetic-complete-mbo",
        "utc_date": "2025-04-07",
        "contract": "6EM5",
        "header": {
            "dataset": "GLBX.MDP3",
            "schema": "mbo",
            "symbols": ["6E.FUT"],
            "not_found": [],
            "start_ns": 1_743_984_000_000_000_000,
            "end_ns": 1_744_070_400_000_000_000,
            "mappings": mappings,
        },
        "asserted_member_sha256": member,
        "declared_item_count": len(bodies) + 1,
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
                "decoded_position": pos,
                "kind": "mbo",
                "instrument_id": body["instrument_id"],
                "payload_sha256": digest(body),
            }
            for pos, body in enumerate(bodies, 2)
        ],
    }


def old_assessment_body(fixture):
    old_pin = digest(old_protocol_body())
    prefix = digest(
        {
            "protocol_sha256": old_pin,
            "fixture_id": fixture["fixture_id"],
            "source_session": fixture["source_session"],
            "utc_date": fixture["utc_date"],
            "contract": fixture["contract"],
            "header": fixture["header"],
        }
    )
    targets = foreign = 0
    audits = []
    for item in fixture["items"]:
        prefix = digest({"previous_prefix_sha256": prefix, "item": item})
        ordinal = None
        if item["kind"] == "metadata":
            disposition = "header"
        elif item["instrument_id"] == 7:
            disposition = "target_candidate"
            targets += 1
            ordinal = targets
        else:
            disposition = "foreign"
            foreign += 1
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
    body = {
        "status": "constructed_decoded_cursor_metadata_not_native_verification",
        "protocol_sha256": old_pin,
        "fixture_sha256": digest(fixture),
        "fixture": fixture,
        "mapped_instrument_id": 7,
        "decoded_item_count": len(fixture["items"]),
        "target_candidate_count": targets,
        "foreign_count": foreign,
        "audits": audits,
        "authority_flags": dict.fromkeys(OLD_FLAGS, False),
    }
    return body | {"assessment_sha256": digest(body)}


def assessment_body(bundle):
    protocol_pin, context_pin = digest(protocol_body()), digest(bundle["context"])
    old = old_assessment_body(bundle["cursor_fixture"])
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
    return {
        "status": "constructed_record_payload_binding_not_native_verification",
        "protocol_sha256": protocol_pin,
        "context_sha256": context_pin,
        "cursor_protocol_sha256": digest(old_protocol_body()),
        "cursor_fixture_sha256": digest(bundle["cursor_fixture"]),
        "bundle_sha256": digest(bundle),
        "bundle": bundle,
        "cursor_assessment": old,
        "audits": audits,
        "authority_flags": dict.fromkeys(NEW_FLAGS, False),
    }


def fixture_object(body):
    header = body["header"]
    groups = tuple(
        cursor.MappingGroup(
            group["contract"],
            tuple(
                cursor.MappingInterval(
                    interval["start_date"], interval["end_date"], interval["instrument_symbol"]
                )
                for interval in group["intervals"]
            ),
        )
        for group in header["mappings"]
    )
    header_object = cursor.DeclaredHeader(
        header["dataset"],
        header["schema"],
        tuple(header["symbols"]),
        tuple(header["not_found"]),
        header["start_ns"],
        header["end_ns"],
        groups,
    )
    items = tuple(
        cursor.DecodedItem(
            item["decoded_position"], item["kind"], item["instrument_id"], item["payload_sha256"]
        )
        for item in body["items"]
    )
    return cursor.CursorFixture(
        body["fixture_id"],
        body["source_session"],
        body["utc_date"],
        body["contract"],
        header_object,
        body["asserted_member_sha256"],
        body["declared_item_count"],
        items,
    )


def make_case(mode="absent", bodies=None, *, member="1" * 64, mappings=None):
    binding = binding_module()
    if bodies is None:
        bodies = [record_body(7, mode), record_body(99, mode), record_body(7, mode, sequence=4)]
    context = context_body(mode)
    fixture = fixture_body(bodies, member=member, mappings=mappings)
    body = {"context": context, "cursor_fixture": fixture, "payloads": [None, *bodies]}
    bundle = binding.PayloadBundle(
        binding.PayloadContext(**context),
        fixture_object(fixture),
        (None, *(binding.MboPayload(**payload) for payload in bodies)),
    )
    pins = {
        "expected_protocol_sha256": digest(protocol_body()),
        "expected_context_sha256": digest(context),
        "expected_cursor_protocol_sha256": digest(old_protocol_body()),
        "expected_cursor_fixture_sha256": digest(fixture),
        "expected_bundle_sha256": digest(body),
    }
    return binding, bundle, pins, body


def call_bundle(binding, api, bundle, pins):
    arguments = dict(pins)
    if api == "bundle_sha256":
        arguments.pop("expected_bundle_sha256")
    return getattr(binding, api)(bundle, **arguments)


def submitted(binding, bundle, pins):
    return binding.assess(bundle, **pins)


def verify(binding, result, bundle, pins, body):
    return binding.verify(
        result, bundle, **pins, expected_assessment_sha256=digest(assessment_body(body))
    )


def poison_fields(monkeypatch, binding, objects, field):
    original = binding.MboPayload.__getattribute__
    poisoned_ids = {id(value) for value in objects}

    def guarded(self, name):
        if id(self) in poisoned_ids and name == field:
            raise AssertionError("Deferred payload field was traversed: " + field)
        return original(self, name)

    monkeypatch.setattr(binding.MboPayload, "__getattribute__", guarded)


def expected_result(binding, bundle, body):
    result_body = assessment_body(body)
    old = result_body["cursor_assessment"]
    old_audits = tuple(cursor.CursorAudit(**audit) for audit in old["audits"])
    old_result = cursor.CursorAssessment(
        old["status"],
        old["protocol_sha256"],
        old["fixture_sha256"],
        bundle.cursor_fixture,
        old["mapped_instrument_id"],
        old["decoded_item_count"],
        old["target_candidate_count"],
        old["foreign_count"],
        old_audits,
        tuple((name, False) for name in OLD_FLAGS),
        old["assessment_sha256"],
    )
    return binding.BindingAssessment(
        result_body["status"],
        result_body["protocol_sha256"],
        result_body["context_sha256"],
        result_body["cursor_protocol_sha256"],
        result_body["cursor_fixture_sha256"],
        result_body["bundle_sha256"],
        bundle,
        old_result,
        tuple(binding.PayloadAudit(**audit) for audit in result_body["audits"]),
        tuple((name, False) for name in NEW_FLAGS),
        digest(result_body),
    )


def changed_body_value(body, field):
    value = body[field]
    if field in ("action", "side"):
        return "Z"
    if value is None:
        return 0
    return value - 1 if field == "order_id" else value + 1


def metadata_defect(bundle, name):
    fixture = bundle.cursor_fixture
    if name == "final_item_position":
        items = fixture.items[:-1] + (replace(fixture.items[-1], decoded_position=99),)
        return replace(bundle, cursor_fixture=replace(fixture, items=items))
    if name == "final_item_pin":
        items = fixture.items[:-1] + (replace(fixture.items[-1], payload_sha256="bad"),)
        return replace(bundle, cursor_fixture=replace(fixture, items=items))
    if name == "final_payload_type":
        return replace(bundle, payloads=bundle.payloads[:-1] + (None,))
    if name == "header_payload":
        return replace(bundle, payloads=(bundle.payloads[1],) + bundle.payloads[1:])
    if name == "payload_count":
        return replace(bundle, payloads=bundle.payloads[:-1])
    if name == "tuple_alias":
        return replace(bundle, payloads=TupleAlias(bundle.payloads))
    if name == "context":
        return replace(bundle, context=replace(bundle.context, schema_version=True))
    raise AssertionError("Unknown independent metadata defect")


def submitted_defect(result, name):
    if name == "status":
        return replace(result, status="accepted_native")
    if name == "context":
        retained = replace(result.bundle, context=replace(result.bundle.context, codec_id="native"))
        return replace(result, bundle=retained)
    if name == "retained_final_item":
        return replace(result, bundle=metadata_defect(result.bundle, "final_item_position"))
    if name == "retained_final_payload_type":
        return replace(result, bundle=metadata_defect(result.bundle, "final_payload_type"))
    if name == "final_audit":
        audits = result.audits[:-1] + (replace(result.audits[-1], decoded_position=99),)
        return replace(result, audits=audits)
    if name == "final_audit_prefix":
        audits = result.audits[:-1] + (replace(result.audits[-1], bound_prefix_sha256="bad"),)
        return replace(result, audits=audits)
    if name == "top_final_flag":
        return replace(
            result, authority_flags=result.authority_flags[:-1] + (("training_allowed", 0),)
        )
    if name == "nested_final_flag":
        old = result.cursor_assessment
        flags = old.authority_flags[:-1] + (("training_allowed", True),)
        return replace(result, cursor_assessment=replace(old, authority_flags=flags))
    if name == "nested_final_audit":
        old = result.cursor_assessment
        audits = old.audits[:-1] + (replace(old.audits[-1], prefix_sha256="0" * 64),)
        return replace(result, cursor_assessment=replace(old, audits=audits))
    if name == "nested_count":
        return replace(
            result, cursor_assessment=replace(result.cursor_assessment, foreign_count=True)
        )
    if name == "retained_context_pin":
        return replace(result, context_sha256="0" * 64)
    if name == "retained_assessment_pin":
        return replace(result, assessment_sha256="bad")
    raise AssertionError("Unknown independent submitted metadata defect")


def binding_module():
    try:
        return importlib.import_module("ai_trader.research.six_e_record_payload_binding")
    except ModuleNotFoundError as exc:
        if exc.name != "ai_trader.research.six_e_record_payload_binding":
            raise
        pytest.fail("Required constructed payload-binding protocol behavior is not implemented")


def test_slice1_required_literal_protocol_behavior():
    binding = binding_module()
    body = binding.protocol()
    assert body["version"] == "constructed_record_payload_binding_v1"
    assert body["codec_id"] == "constructed_mbo_json_v1"
    assert body["max_body_bytes"] == 262_144
    assert body["max_cursor_body_bytes"] == 65_536


def test_slice1_complete_literal_protocol_oracle():
    binding = binding_module()
    assert binding.protocol() == protocol_body()
    assert binding.protocol_sha256() == digest(protocol_body())
    assert cursor.protocol() == old_protocol_body()
    assert cursor.protocol_sha256() == digest(old_protocol_body())


@pytest.mark.parametrize("name, expected_fields", SCHEMAS.items())
def test_slice1_exact_frozen_required_schemas(name, expected_fields):
    binding = binding_module()
    cls = getattr(binding, name)
    signature = inspect.signature(cls)
    assert tuple(signature.parameters) == expected_fields
    assert all(
        parameter.default is inspect.Parameter.empty for parameter in signature.parameters.values()
    )
    with pytest.raises(TypeError):
        cls()
    if name == "PayloadContext":
        value = cls("constructed_mbo_json_v1", 1, "absent")
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            value.schema_version = 2


@pytest.mark.parametrize("mode", ["absent", "present"])
def test_slice1_complete_context_and_raw_body_oracles(mode):
    binding = binding_module()
    context = binding.PayloadContext(**context_body(mode))
    body = record_body(mode=mode)
    payload = binding.MboPayload(**body)
    protocol_pin = digest(protocol_body())
    context_pin = digest(context_body(mode))
    assert binding.context_sha256(context, expected_protocol_sha256=protocol_pin) == context_pin
    assert binding.payload_sha256(
        payload,
        context,
        expected_protocol_sha256=protocol_pin,
        expected_context_sha256=context_pin,
    ) == digest(body)
    for field in BODY_FIELDS:
        assert type(getattr(payload, field)) is type(body[field])
        assert getattr(payload, field) == body[field]


@pytest.mark.parametrize("field", INTEGER_BOUNDS)
@pytest.mark.parametrize("edge", ["minimum", "maximum", "below", "above", "bool", "float", "alias"])
def test_slice1_exact_integer_domains(field, edge):
    binding = binding_module()
    low, high = INTEGER_BOUNDS[field]
    value = {
        "minimum": low,
        "maximum": high,
        "below": low - 1,
        "above": high + 1,
        "bool": True,
        "float": float(low),
        "alias": IntAlias(low),
    }[edge]
    mode = "present" if field == "ts_out" else "absent"
    body = record_body(mode=mode, **{field: value})
    context = binding.PayloadContext(**context_body(mode))
    arguments = {
        "expected_protocol_sha256": digest(protocol_body()),
        "expected_context_sha256": digest(context_body(mode)),
    }
    if edge in ("minimum", "maximum"):
        assert binding.payload_sha256(binding.MboPayload(**body), context, **arguments) == digest(
            body
        )
    else:
        with pytest.raises(ValueError):
            binding.payload_sha256(binding.MboPayload(**body), context, **arguments)


@pytest.mark.parametrize("field", ["action", "side"])
@pytest.mark.parametrize(
    "value", ["\x00", "\x01", " ", "\n", "\x7f", "", "AB", "\x80", None, StrAlias("A")]
)
def test_slice1_ascii_exactness_without_enum_or_trimming(field, value):
    binding = binding_module()
    body = record_body(**{field: value})
    arguments = {
        "expected_protocol_sha256": digest(protocol_body()),
        "expected_context_sha256": digest(context_body()),
    }
    payload, context = binding.MboPayload(**body), binding.PayloadContext(**context_body())
    if type(value) is str and len(value) == 1 and ord(value) <= 127:
        assert binding.payload_sha256(payload, context, **arguments) == digest(body)
    else:
        with pytest.raises(ValueError):
            binding.payload_sha256(payload, context, **arguments)


@pytest.mark.parametrize(
    "mode, value",
    [
        ("absent", None),
        ("absent", 0),
        ("absent", False),
        ("absent", -1),
        ("present", None),
        ("present", 0),
        ("present", False),
        ("present", S64_MAX),
    ],
)
def test_slice1_ts_out_is_explicit_and_never_inferred(mode, value):
    binding = binding_module()
    body = record_body(mode=mode, ts_out=value)
    context = binding.PayloadContext(**context_body(mode))
    arguments = {
        "expected_protocol_sha256": digest(protocol_body()),
        "expected_context_sha256": digest(context_body(mode)),
    }
    valid = value is None if mode == "absent" else type(value) is int
    if valid:
        assert binding.payload_sha256(binding.MboPayload(**body), context, **arguments) == digest(
            body
        )
    else:
        with pytest.raises(ValueError):
            binding.payload_sha256(binding.MboPayload(**body), context, **arguments)


@pytest.mark.parametrize("field", BODY_FIELDS)
def test_slice1_every_raw_field_has_an_independent_binding(field):
    binding = binding_module()
    original = record_body(mode="present")
    changed = dict(original)
    value = original[field]
    changed[field] = "Z" if field in ("action", "side") else value + 1
    if field == "order_id":
        changed[field] = value - 1
    context = binding.PayloadContext(**context_body("present"))
    arguments = {
        "expected_protocol_sha256": digest(protocol_body()),
        "expected_context_sha256": digest(context_body("present")),
    }
    original_pin = binding.payload_sha256(binding.MboPayload(**original), context, **arguments)
    changed_pin = binding.payload_sha256(binding.MboPayload(**changed), context, **arguments)
    assert original_pin == digest(original)
    assert changed_pin == digest(changed)
    assert original_pin != changed_pin


@pytest.mark.parametrize(
    "field, bad",
    [
        ("codec_id", "native"),
        ("codec_id", StrAlias("constructed_mbo_json_v1")),
        ("schema_version", True),
        ("schema_version", 1.0),
        ("schema_version", 2),
        ("ts_out_mode", "absent "),
        ("ts_out_mode", None),
        ("ts_out_mode", StrAlias("absent")),
    ],
)
def test_slice1_context_values_are_exact(field, bad):
    binding = binding_module()
    body = context_body() | {field: bad}
    with pytest.raises(ValueError):
        binding.context_sha256(
            binding.PayloadContext(**body), expected_protocol_sha256=digest(protocol_body())
        )


@pytest.mark.parametrize("field", BODY_FIELDS)
@pytest.mark.parametrize("failure", ["bad_protocol", "bad_context", "bad_context_pin"])
def test_slice1_metadata_checks_precede_every_raw_field(monkeypatch, field, failure):
    binding = binding_module()
    payload = binding.MboPayload(**record_body())
    context = binding.PayloadContext(**context_body())
    arguments = {
        "expected_protocol_sha256": digest(protocol_body()),
        "expected_context_sha256": digest(context_body()),
    }
    if failure == "bad_protocol":
        arguments["expected_protocol_sha256"] = "0" * 64
    elif failure == "bad_context":
        context = replace(context, schema_version=True)
    else:
        arguments["expected_context_sha256"] = "F" * 64
    poison_fields(monkeypatch, binding, [payload], field)
    with pytest.raises(ValueError):
        binding.payload_sha256(payload, context, **arguments)


def test_slice1_returned_protocol_mutation_cannot_change_literals():
    binding = binding_module()
    before = digest(protocol_body())
    mutable = binding.protocol()
    mutable["max_body_bytes"] = 1
    mutable["integer_bounds"]["price"] = [0, 0]
    mutable["dataclass_fields"]["MboPayload"].clear()
    mutable["authority_flags"]["trading_enabled"] = True
    assert binding.protocol() == protocol_body()
    assert binding.protocol_sha256() == before


def test_slice2_complete_bundle_and_assessment_required_behavior():
    binding, bundle, pins, body = make_case()
    assert callable(getattr(binding, "bundle_sha256", None)), "Complete bundle API not implemented"
    assert callable(getattr(binding, "assess", None)), "Complete assessment API not implemented"
    assert call_bundle(binding, "bundle_sha256", bundle, pins) == digest(body)
    actual = binding.assess(bundle, **pins)
    assert actual.assessment_sha256 == digest(assessment_body(body))


@pytest.mark.parametrize("field", BODY_FIELDS)
def test_slice2_complete_final_metadata_precedes_every_raw_field(monkeypatch, field):
    binding, bundle, pins, _ = make_case()
    assert callable(getattr(binding, "assess", None)), (
        "Complete phase-order behavior not implemented"
    )
    fixture = bundle.cursor_fixture
    items = fixture.items[:-1] + (replace(fixture.items[-1], decoded_position=99),)
    bundle = replace(bundle, cursor_fixture=replace(fixture, items=items))
    poison_fields(monkeypatch, binding, bundle.payloads[1:], field)
    with pytest.raises(ValueError):
        binding.assess(bundle, **pins)


def test_slice2_complete_foreign_raw_body_mismatch_refuses():
    binding, bundle, pins, _ = make_case()
    assert callable(getattr(binding, "assess", None)), (
        "Foreign body binding behavior not implemented"
    )
    payloads = bundle.payloads[:2] + (replace(bundle.payloads[2], price=12),) + bundle.payloads[3:]
    with pytest.raises(ValueError):
        binding.assess(replace(bundle, payloads=payloads), **pins)


@pytest.mark.parametrize("mode", ["absent", "present"])
def test_slice2_complete_literal_bundle_cursor_audit_result_oracle(mode):
    binding, bundle, pins, body = make_case(mode)
    assert call_bundle(binding, "bundle_sha256", bundle, pins) == digest(body)
    actual = binding.assess(bundle, **pins)
    expected = expected_result(binding, bundle, body)
    assert actual == expected
    assert actual.assessment_sha256 == digest(assessment_body(body))
    assert actual.cursor_assessment == expected.cursor_assessment
    assert tuple(name for name, _ in actual.authority_flags) == NEW_FLAGS
    assert tuple(name for name, _ in actual.cursor_assessment.authority_flags) == OLD_FLAGS
    assert all(value is False for _, value in actual.authority_flags)
    assert all(value is False for _, value in actual.cursor_assessment.authority_flags)


@pytest.mark.parametrize("api", ["bundle_sha256", "assess"])
@pytest.mark.parametrize("field", BODY_FIELDS)
@pytest.mark.parametrize(
    "defect",
    [
        "final_item_pin",
        "final_payload_type",
        "header_payload",
        "payload_count",
        "tuple_alias",
        "context",
    ],
)
def test_slice2_all_original_metadata_precedes_all_body_fields(monkeypatch, api, field, defect):
    binding, bundle, pins, _ = make_case()
    poisoned = bundle.payloads[1:]
    bad = metadata_defect(bundle, defect)
    poison_fields(monkeypatch, binding, poisoned, field)
    with pytest.raises(ValueError):
        call_bundle(binding, api, bad, pins)


@pytest.mark.parametrize("position", [1, 2, 3], ids=["target_first", "foreign", "target_final"])
@pytest.mark.parametrize("field", BODY_FIELDS)
def test_slice2_every_target_and_foreign_field_refuses_retained_pin_mismatch(position, field):
    binding, bundle, pins, body = make_case()
    payload = bundle.payloads[position]
    body_value = body["payloads"][position]
    changed = replace(payload, **{field: changed_body_value(body_value, field)})
    payloads = bundle.payloads[:position] + (changed,) + bundle.payloads[position + 1 :]
    with pytest.raises(ValueError):
        binding.assess(replace(bundle, payloads=payloads), **pins)


@pytest.mark.parametrize("field", BODY_FIELDS)
def test_slice2_valid_body_access_assertions_are_not_caught(monkeypatch, field):
    binding, bundle, pins, _ = make_case()
    poison_fields(monkeypatch, binding, [bundle.payloads[1]], field)
    with pytest.raises(AssertionError, match="Deferred payload field"):
        binding.assess(bundle, **pins)


@pytest.mark.parametrize("kind", ["future_target", "future_foreign", "append", "member"])
def test_slice2_valid_suffix_and_complete_member_do_not_enter_earlier_prefixes(kind):
    binding, bundle, pins, body = make_case()
    original = binding.assess(bundle, **pins)
    bodies = copy.deepcopy(body["payloads"][1:])
    member = "1" * 64
    preceding = 3
    if kind == "future_target":
        bodies[-1]["price"] = 17
    elif kind == "future_foreign":
        bodies[-1] = record_body(88, price=25)
    elif kind == "append":
        bodies.append(record_body(7, sequence=10))
        preceding = 4
    else:
        member, preceding = "2" * 64, 4
    _, changed, changed_pins, changed_body = make_case(bodies=bodies, member=member)
    result = binding.assess(changed, **changed_pins)
    assert original.audits[:preceding] == result.audits[:preceding]
    assert (
        original.cursor_assessment.audits[:preceding] == result.cursor_assessment.audits[:preceding]
    )
    assert original.bundle_sha256 != result.bundle_sha256
    assert original.assessment_sha256 != result.assessment_sha256
    assert result == expected_result(binding, changed, changed_body)


def test_slice2_changed_preceding_foreign_body_changes_following_prefix():
    binding, bundle, pins, body = make_case()
    original = binding.assess(bundle, **pins)
    bodies = copy.deepcopy(body["payloads"][1:])
    bodies[1]["ts_event"] = S64_MAX
    _, changed, changed_pins, _ = make_case(bodies=bodies)
    result = binding.assess(changed, **changed_pins)
    assert original.audits[:2] == result.audits[:2]
    assert original.audits[-1].payload_sha256 == result.audits[-1].payload_sha256
    assert original.audits[-1].cursor_prefix_sha256 != result.audits[-1].cursor_prefix_sha256
    assert original.audits[-1].bound_prefix_sha256 != result.audits[-1].bound_prefix_sha256


def test_slice2_context_binds_header_without_changing_old_header_chain():
    binding, absent, absent_pins, _ = make_case("absent")
    _, present, present_pins, _ = make_case("present")
    absent_result = binding.assess(absent, **absent_pins)
    present_result = binding.assess(present, **present_pins)
    assert (
        absent_result.audits[0].cursor_prefix_sha256
        == present_result.audits[0].cursor_prefix_sha256
    )
    assert (
        absent_result.audits[0].bound_prefix_sha256 != present_result.audits[0].bound_prefix_sha256
    )
    assert absent_result.context_sha256 != present_result.context_sha256


def test_slice2_repeated_bodies_are_distinct_complete_occurrences():
    body = record_body()
    binding, bundle, pins, projected = make_case(bodies=[dict(body), dict(body), dict(body)])
    result = binding.assess(bundle, **pins)
    assert result == expected_result(binding, bundle, projected)
    assert [audit.target_candidate_ordinal for audit in result.audits] == [None, 1, 2, 3]
    assert len({audit.bound_prefix_sha256 for audit in result.audits}) == 4
    assert len({audit.payload_sha256 for audit in result.audits[1:]}) == 1


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_slice2_shared_complete_body_cap_equality_and_overflow(delta):
    binding = binding_module()
    # Arbitrary JSON guard body, not a legal public fixture or universal maximum.
    value = "x" * (262_144 - 2 + delta)
    assert len(canonical(value)) == 262_144 + delta
    if delta <= 0:
        assert binding._bounded_canonical(value) == canonical(value)
    else:
        with pytest.raises(ValueError):
            binding._bounded_canonical(value)


@pytest.mark.parametrize("mode", ["absent", "present"])
def test_slice2_independent_cap_compliant_128_position_envelope(mode):
    bodies = [
        record_body(
            7 if pos % 2 else U32, mode, publisher_id=U64, price=S64_MIN, record_size=65_536
        )
        for pos in range(127)
    ]
    binding, bundle, pins, body = make_case(mode, bodies)
    expected = assessment_body(body)
    assert len(canonical(body["cursor_fixture"])) <= 65_536
    old_body = dict(expected["cursor_assessment"])
    old_body.pop("assessment_sha256")
    assert len(canonical(old_body)) <= 65_536
    assert len(canonical(body)) <= 262_144
    assert len(canonical(expected)) <= 262_144
    result = binding.assess(bundle, **pins)
    assert result == expected_result(binding, bundle, body)
    assert len(result.audits) == 128


@pytest.mark.parametrize("api", ["bundle_sha256", "assess"])
@pytest.mark.parametrize("old_body_kind", ["fixture", "assessment"])
def test_slice2_each_old_complete_cap_is_still_required(monkeypatch, api, old_body_kind):
    binding, bundle, pins, _ = make_case()
    original = cursor._bounded_canonical

    def refuse_selected_complete_body(value):
        selected = "fixture_id" in value if old_body_kind == "fixture" else "status" in value
        if selected:
            raise ValueError("Independent simulated old complete-cap refusal")
        return original(value)

    monkeypatch.setattr(cursor, "_bounded_canonical", refuse_selected_complete_body)
    with pytest.raises(ValueError):
        call_bundle(binding, api, bundle, pins)


def test_slice2_bundle_and_result_share_new_complete_cap_guard(monkeypatch):
    binding, bundle, pins, body = make_case()
    original = binding._bounded_canonical
    seen = []

    def observed(value):
        if type(value) is dict:
            seen.append(copy.deepcopy(value))
        return original(value)

    monkeypatch.setattr(binding, "_bounded_canonical", observed)
    actual = binding.assess(bundle, **pins)
    assert body in seen
    assert assessment_body(body) in seen
    assert actual.assessment_sha256 == digest(assessment_body(body))


@pytest.mark.parametrize("body_kind", ["bundle", "result"])
def test_slice2_new_complete_cap_refusal_returns_no_partial_assessment(monkeypatch, body_kind):
    binding, bundle, pins, _ = make_case()
    original = binding._bounded_canonical

    def refused(value):
        selected = "payloads" in value if body_kind == "bundle" else "status" in value
        if selected:
            raise ValueError("Independent simulated new complete-cap refusal")
        return original(value)

    monkeypatch.setattr(binding, "_bounded_canonical", refused)
    with pytest.raises(ValueError):
        binding.assess(bundle, **pins)


def test_slice3_submitted_verification_required_complete_behavior():
    binding, bundle, pins, body = make_case()
    assert callable(getattr(binding, "verify", None)), (
        "Complete submitted verification not implemented"
    )
    result = expected_result(binding, bundle, body)
    assert verify(binding, result, bundle, pins, body) is None


@pytest.mark.parametrize("field", BODY_FIELDS)
@pytest.mark.parametrize("side", ["original", "submitted"])
@pytest.mark.parametrize(
    "defect",
    [
        "status",
        "context",
        "retained_final_item",
        "retained_final_payload_type",
        "final_audit",
        "final_audit_prefix",
        "top_final_flag",
        "nested_final_flag",
        "nested_final_audit",
        "nested_count",
        "retained_context_pin",
        "retained_assessment_pin",
    ],
)
def test_slice3_entire_submitted_metadata_precedes_both_payload_traversals(
    monkeypatch, field, side, defect
):
    binding, bundle, pins, body = make_case()
    assert callable(getattr(binding, "verify", None)), "Submitted metadata phase not implemented"
    # Independent retained objects ensure original and submitted are separately exercised.
    _, retained, _, _ = make_case()
    result = expected_result(binding, retained, body)
    bad = submitted_defect(result, defect)
    poison_bundle = bundle if side == "original" else retained
    poison_fields(monkeypatch, binding, poison_bundle.payloads[1:], field)
    with pytest.raises(ValueError):
        verify(binding, bad, bundle, pins, body)


@pytest.mark.parametrize("field", BODY_FIELDS)
@pytest.mark.parametrize("side", ["original", "submitted"])
def test_slice3_valid_verification_reaches_uncaught_actual_body_sentinel(monkeypatch, field, side):
    binding, bundle, pins, body = make_case()
    assert callable(getattr(binding, "verify", None)), (
        "Submitted traversal behavior not implemented"
    )
    _, retained, _, _ = make_case()
    result = expected_result(binding, retained, body)
    poison_bundle = bundle if side == "original" else retained
    poison_fields(monkeypatch, binding, poison_bundle.payloads[1:], field)
    with pytest.raises(AssertionError, match="Deferred payload field"):
        verify(binding, result, bundle, pins, body)


def test_slice3_nested_public_cursor_verification_precedes_new_body_access(monkeypatch):
    binding, bundle, pins, body = make_case()
    assert callable(getattr(binding, "verify", None)), "Nested cursor verification not implemented"
    result = expected_result(binding, bundle, body)
    original_verify = cursor.verify

    def required_nested_check(*args, **kwargs):
        if args[0] is result.cursor_assessment:
            raise AssertionError("Required nested public cursor.verify reached before payload")
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(cursor, "verify", required_nested_check)
    poison_fields(monkeypatch, binding, bundle.payloads[1:], "price")
    with pytest.raises(AssertionError, match="Required nested public cursor.verify"):
        verify(binding, result, bundle, pins, body)


@pytest.mark.parametrize("mode", ["absent", "present"])
def test_slice3_full_independent_submitted_reconstruction_is_deterministic(mode):
    binding, bundle, pins, body = make_case(mode)
    actual = binding.assess(bundle, **pins)
    expected = expected_result(binding, bundle, body)
    assert actual == expected
    assert verify(binding, expected, bundle, pins, body) is None
    assert verify(binding, actual, bundle, pins, body) is None


@pytest.mark.parametrize("field", BODY_FIELDS)
def test_slice3_valid_paired_raw_field_change_rebinds_complete_identities(field):
    binding, bundle, pins, body = make_case("present")
    original = binding.assess(bundle, **pins)
    bodies = copy.deepcopy(body["payloads"][1:])
    bodies[-1][field] = changed_body_value(bodies[-1], field)
    _, changed, changed_pins, changed_body = make_case("present", bodies)
    result = binding.assess(changed, **changed_pins)
    assert result == expected_result(binding, changed, changed_body)
    assert original.audits[:-1] == result.audits[:-1]
    assert original.audits[-1].payload_sha256 != result.audits[-1].payload_sha256
    assert original.audits[-1].bound_prefix_sha256 != result.audits[-1].bound_prefix_sha256
    assert original.bundle_sha256 != result.bundle_sha256
    assert original.assessment_sha256 != result.assessment_sha256
    assert verify(binding, result, changed, changed_pins, changed_body) is None


@pytest.mark.parametrize("field", BODY_FIELDS)
@pytest.mark.parametrize("position", [1, 2, 3], ids=["first_target", "foreign", "final_target"])
def test_slice3_submitted_every_raw_field_is_rebuilt_not_adopted(field, position):
    binding, bundle, pins, body = make_case("present")
    result = expected_result(binding, bundle, body)
    retained = result.bundle
    payload = retained.payloads[position]
    changed = replace(payload, **{field: changed_body_value(body["payloads"][position], field)})
    payloads = retained.payloads[:position] + (changed,) + retained.payloads[position + 1 :]
    bad = replace(result, bundle=replace(retained, payloads=payloads))
    with pytest.raises(ValueError):
        verify(binding, bad, bundle, pins, body)


@pytest.mark.parametrize("field", BODY_FIELDS)
@pytest.mark.parametrize("api", ["payload_sha256", "assess", "verify_original", "verify_submitted"])
def test_slice3_each_missing_raw_slot_is_normalized_only_in_body_phase(field, api):
    binding, bundle, pins, body = make_case()
    _, retained, _, _ = make_case()
    result = expected_result(binding, retained, body)
    chosen = retained if api == "verify_submitted" else bundle
    object.__delattr__(chosen.payloads[-1], field)
    with pytest.raises(ValueError):
        if api == "payload_sha256":
            binding.payload_sha256(
                chosen.payloads[-1],
                chosen.context,
                expected_protocol_sha256=pins["expected_protocol_sha256"],
                expected_context_sha256=pins["expected_context_sha256"],
            )
        elif api == "assess":
            binding.assess(bundle, **pins)
        else:
            verify(binding, result, bundle, pins, body)


@pytest.mark.parametrize("field", BODY_FIELDS)
@pytest.mark.parametrize("side", ["original", "submitted"])
def test_slice3_deleted_raw_slots_still_defer_to_bad_final_metadata(field, side):
    binding, bundle, pins, body = make_case()
    _, retained, _, _ = make_case()
    result = submitted_defect(expected_result(binding, retained, body), "status")
    chosen = bundle if side == "original" else retained
    object.__delattr__(chosen.payloads[1], field)
    # This tests normalization but the preceding AssertionError cases prove order.
    with pytest.raises(ValueError):
        verify(binding, result, bundle, pins, body)


@pytest.mark.parametrize("name", NEW_FLAGS)
@pytest.mark.parametrize("bad", [True, 0], ids=["enabled", "integer_zero"])
def test_slice3_each_top_authority_is_literal_false(name, bad):
    binding, bundle, pins, body = make_case()
    result = expected_result(binding, bundle, body)
    flags = tuple((flag, bad if flag == name else False) for flag in NEW_FLAGS)
    with pytest.raises(ValueError):
        verify(binding, replace(result, authority_flags=flags), bundle, pins, body)


@pytest.mark.parametrize("name", OLD_FLAGS)
@pytest.mark.parametrize("bad", [True, 0], ids=["enabled", "integer_zero"])
def test_slice3_each_nested_old_authority_is_literal_false(name, bad):
    binding, bundle, pins, body = make_case()
    result = expected_result(binding, bundle, body)
    flags = tuple((flag, bad if flag == name else False) for flag in OLD_FLAGS)
    old = replace(result.cursor_assessment, authority_flags=flags)
    with pytest.raises(ValueError):
        verify(binding, replace(result, cursor_assessment=old), bundle, pins, body)


@pytest.mark.parametrize("side", ["top", "nested"])
@pytest.mark.parametrize(
    "defect", ["missing", "extra", "reversed", "list", "tuple_alias", "pair_list"]
)
def test_slice3_authority_container_order_and_coverage_are_complete(side, defect):
    binding, bundle, pins, body = make_case()
    result = expected_result(binding, bundle, body)
    old = result.cursor_assessment
    flags = result.authority_flags if side == "top" else old.authority_flags
    if defect == "missing":
        changed = flags[:-1]
    elif defect == "extra":
        changed = flags + (("unknown_authority", False),)
    elif defect == "reversed":
        changed = tuple(reversed(flags))
    elif defect == "list":
        changed = list(flags)
    elif defect == "tuple_alias":
        changed = TupleAlias(flags)
    else:
        changed = flags[:-1] + ([flags[-1][0], False],)
    bad = (
        replace(result, authority_flags=changed)
        if side == "top"
        else replace(result, cursor_assessment=replace(old, authority_flags=changed))
    )
    with pytest.raises(ValueError):
        verify(binding, bad, bundle, pins, body)


@pytest.mark.parametrize(
    "field",
    [
        "protocol_sha256",
        "context_sha256",
        "cursor_protocol_sha256",
        "cursor_fixture_sha256",
        "bundle_sha256",
        "assessment_sha256",
    ],
)
@pytest.mark.parametrize("bad", ["0" * 64, "F" * 64, "bad", StrAlias("0" * 64)])
def test_slice3_every_retained_result_pin_is_checked(field, bad):
    binding, bundle, pins, body = make_case()
    result = expected_result(binding, bundle, body)
    with pytest.raises(ValueError):
        verify(binding, replace(result, **{field: bad}), bundle, pins, body)


@pytest.mark.parametrize(
    "field, bad",
    [
        ("status", "native_success"),
        ("status", StrAlias("constructed_record_payload_binding_not_native_verification")),
        ("bundle", None),
        ("cursor_assessment", None),
        ("audits", ()),
        ("audits", []),
        ("authority_flags", ()),
    ],
)
def test_slice3_complete_submitted_result_metadata_is_not_a_summary(field, bad):
    binding, bundle, pins, body = make_case()
    result = expected_result(binding, bundle, body)
    with pytest.raises(ValueError):
        verify(binding, replace(result, **{field: bad}), bundle, pins, body)


@pytest.mark.parametrize(
    "field, bad",
    [
        ("decoded_position", True),
        ("decoded_position", 99),
        ("disposition", "book_accepted"),
        ("instrument_id", True),
        ("instrument_id", 8),
        ("target_candidate_ordinal", True),
        ("target_candidate_ordinal", 99),
        ("payload_sha256", "0" * 64),
        ("cursor_item_sha256", "0" * 64),
        ("cursor_prefix_sha256", "0" * 64),
        ("bound_prefix_sha256", "0" * 64),
    ],
)
def test_slice3_complete_final_audit_metadata_and_valid_hex_pins_are_rebuilt(field, bad):
    binding, bundle, pins, body = make_case()
    result = expected_result(binding, bundle, body)
    audits = result.audits[:-1] + (replace(result.audits[-1], **{field: bad}),)
    with pytest.raises(ValueError):
        verify(binding, replace(result, audits=audits), bundle, pins, body)


@pytest.mark.parametrize(
    "position, field, bad",
    [
        (0, "payload_sha256", "0" * 64),
        (0, "instrument_id", 7),
        (0, "target_candidate_ordinal", 1),
        (0, "disposition", "foreign"),
        (2, "target_candidate_ordinal", 1),
        (2, "disposition", "target_candidate"),
        (2, "instrument_id", 7),
    ],
)
def test_slice3_header_and_foreign_audits_have_distinct_exact_none_semantics(position, field, bad):
    binding, bundle, pins, body = make_case()
    result = expected_result(binding, bundle, body)
    changed = replace(result.audits[position], **{field: bad})
    audits = result.audits[:position] + (changed,) + result.audits[position + 1 :]
    with pytest.raises(ValueError):
        verify(binding, replace(result, audits=audits), bundle, pins, body)


@pytest.mark.parametrize(
    "field, bad",
    [
        ("status", "native"),
        ("protocol_sha256", "0" * 64),
        ("fixture_sha256", "0" * 64),
        ("fixture", None),
        ("mapped_instrument_id", True),
        ("mapped_instrument_id", 8),
        ("decoded_item_count", 3),
        ("target_candidate_count", 1),
        ("foreign_count", 2),
        ("audits", ()),
        ("authority_flags", ()),
        ("assessment_sha256", "0" * 64),
    ],
)
def test_slice3_each_nested_cursor_result_field_is_verified_against_original(field, bad):
    binding, bundle, pins, body = make_case()
    result = expected_result(binding, bundle, body)
    old = replace(result.cursor_assessment, **{field: bad})
    with pytest.raises(ValueError):
        verify(binding, replace(result, cursor_assessment=old), bundle, pins, body)


@pytest.mark.parametrize("api", ["assess", "verify"])
@pytest.mark.parametrize(
    "pin_name",
    [
        "expected_protocol_sha256",
        "expected_context_sha256",
        "expected_cursor_protocol_sha256",
        "expected_cursor_fixture_sha256",
        "expected_bundle_sha256",
    ],
)
@pytest.mark.parametrize("bad", [None, 0, "", "A" * 64, "0" * 63, "0" * 65, StrAlias("0" * 64)])
def test_slice3_every_expected_pin_syntax_precedes_all_caller_object_access(
    monkeypatch, api, pin_name, bad
):
    binding, bundle, pins, body = make_case()
    result = expected_result(binding, bundle, body)
    bad_pins = pins | {pin_name: bad}

    def no_traversal(self, name):
        raise AssertionError("Caller object traversal before expected pin syntax")

    monkeypatch.setattr(binding.PayloadBundle, "__getattribute__", no_traversal)
    monkeypatch.setattr(binding.BindingAssessment, "__getattribute__", no_traversal)
    with pytest.raises(ValueError):
        if api == "assess":
            binding.assess(bundle, **bad_pins)
        else:
            verify(binding, result, bundle, bad_pins, body)


@pytest.mark.parametrize("bad", [None, 0, "", "A" * 64, "0" * 63, "0" * 65, StrAlias("0" * 64)])
def test_slice3_expected_assessment_pin_syntax_precedes_both_bodies(monkeypatch, bad):
    binding, bundle, pins, body = make_case()
    result = expected_result(binding, bundle, body)

    def no_traversal(self, name):
        raise AssertionError("Caller traversal before assessment pin syntax")

    monkeypatch.setattr(binding.PayloadBundle, "__getattribute__", no_traversal)
    monkeypatch.setattr(binding.BindingAssessment, "__getattribute__", no_traversal)
    with pytest.raises(ValueError):
        binding.verify(result, bundle, **pins, expected_assessment_sha256=bad)


def test_slice3_valid_expected_pin_control_reaches_actual_caller_access(monkeypatch):
    binding, bundle, pins, body = make_case()
    result = expected_result(binding, bundle, body)

    def no_traversal(self, name):
        raise AssertionError("Actual caller traversal with valid expected pins")

    monkeypatch.setattr(binding.PayloadBundle, "__getattribute__", no_traversal)
    monkeypatch.setattr(binding.BindingAssessment, "__getattribute__", no_traversal)
    with pytest.raises(AssertionError, match="Actual caller traversal"):
        verify(binding, result, bundle, pins, body)


@pytest.mark.parametrize("type_name", ["PayloadContext", "MboPayload", "PayloadBundle"])
@pytest.mark.parametrize("defect", ["subclass", "dictionary", "none"])
def test_slice3_original_boundary_types_are_exact(type_name, defect):
    binding, bundle, pins, _ = make_case()
    value = {
        "PayloadContext": bundle.context,
        "MboPayload": bundle.payloads[-1],
        "PayloadBundle": bundle,
    }[type_name]
    if defect == "subclass":
        alias_type = type("Alias", (getattr(binding, type_name),), {})
        altered = object.__new__(alias_type)
        for field in SCHEMAS[type_name]:
            object.__setattr__(altered, field, getattr(value, field))
    else:
        altered = {} if defect == "dictionary" else None
    if type_name == "PayloadContext":
        bad = replace(bundle, context=altered)
    elif type_name == "MboPayload":
        bad = replace(bundle, payloads=bundle.payloads[:-1] + (altered,))
    else:
        bad = altered
    with pytest.raises(ValueError):
        binding.assess(bad, **pins)


@pytest.mark.parametrize("type_name", SCHEMAS)
def test_slice3_submitted_exact_new_types_reject_subclasses(type_name):
    binding, bundle, pins, body = make_case()
    result = expected_result(binding, bundle, body)
    value = {
        "PayloadContext": result.bundle.context,
        "MboPayload": result.bundle.payloads[-1],
        "PayloadBundle": result.bundle,
        "PayloadAudit": result.audits[-1],
        "BindingAssessment": result,
    }[type_name]
    alias_type = type("Alias", (getattr(binding, type_name),), {})
    altered = object.__new__(alias_type)
    for field in SCHEMAS[type_name]:
        object.__setattr__(altered, field, getattr(value, field))
    if type_name == "PayloadContext":
        bad = replace(result, bundle=replace(result.bundle, context=altered))
    elif type_name == "MboPayload":
        payloads = result.bundle.payloads[:-1] + (altered,)
        bad = replace(result, bundle=replace(result.bundle, payloads=payloads))
    elif type_name == "PayloadBundle":
        bad = replace(result, bundle=altered)
    elif type_name == "PayloadAudit":
        bad = replace(result, audits=result.audits[:-1] + (altered,))
    else:
        bad = altered
    with pytest.raises(ValueError):
        verify(binding, bad, bundle, pins, body)


@pytest.mark.parametrize(
    "shape", ["list", "tuple_alias", "header_missing", "reordered", "duplicate"]
)
def test_slice3_complete_payload_occurrence_tuple_is_never_repaired(shape):
    binding, bundle, pins, _ = make_case()
    payloads = bundle.payloads
    if shape == "list":
        changed = list(payloads)
    elif shape == "tuple_alias":
        changed = TupleAlias(payloads)
    elif shape == "header_missing":
        changed = payloads[1:]
    elif shape == "reordered":
        changed = (None, payloads[2], payloads[1], payloads[3])
    else:
        changed = payloads + (payloads[-1],)
    with pytest.raises(ValueError):
        binding.assess(replace(bundle, payloads=changed), **pins)


@pytest.mark.parametrize("type_name", SCHEMAS)
def test_slice3_new_constructors_reject_unsupported_fields(type_name):
    binding, bundle, _, body = make_case()
    result = expected_result(binding, bundle, body)
    valid_arguments = {
        "PayloadContext": context_body(),
        "MboPayload": record_body(),
        "PayloadBundle": {
            "context": bundle.context,
            "cursor_fixture": bundle.cursor_fixture,
            "payloads": bundle.payloads,
        },
        "PayloadAudit": assessment_body(body)["audits"][-1],
        "BindingAssessment": {
            "status": result.status,
            "protocol_sha256": result.protocol_sha256,
            "context_sha256": result.context_sha256,
            "cursor_protocol_sha256": result.cursor_protocol_sha256,
            "cursor_fixture_sha256": result.cursor_fixture_sha256,
            "bundle_sha256": result.bundle_sha256,
            "bundle": result.bundle,
            "cursor_assessment": result.cursor_assessment,
            "audits": result.audits,
            "authority_flags": result.authority_flags,
            "assessment_sha256": result.assessment_sha256,
        },
    }
    with pytest.raises(TypeError):
        getattr(binding, type_name)(**valid_arguments[type_name], unsupported_field=0)


@pytest.mark.parametrize(
    "api", ["context_sha256", "payload_sha256", "bundle_sha256", "assess", "verify"]
)
def test_slice3_all_expected_pin_parameters_are_required_keyword_only(api):
    binding = binding_module()
    parameters = inspect.signature(getattr(binding, api)).parameters
    expected = [parameter for name, parameter in parameters.items() if name.startswith("expected_")]
    assert expected
    assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in expected)
    assert all(parameter.default is inspect.Parameter.empty for parameter in expected)


def test_slice3_exported_constants_and_returned_protocol_do_not_control_enforcement(monkeypatch):
    binding = binding_module()
    for name in tuple(vars(binding)):
        if name.isupper() and not name.startswith("_"):
            monkeypatch.setattr(binding, name, object())
    returned = binding.protocol()
    returned["schema_version"] = True
    returned["max_body_bytes"] = 1
    returned["integer_bounds"]["price"] = [0, 0]
    returned["authority_flags"]["training_allowed"] = True
    assert binding.protocol() == protocol_body()
    assert binding.protocol_sha256() == digest(protocol_body())
    context = binding.PayloadContext(**context_body())
    body = record_body(price=S64_MIN)
    assert binding.payload_sha256(
        binding.MboPayload(**body),
        context,
        expected_protocol_sha256=digest(protocol_body()),
        expected_context_sha256=digest(context_body()),
    ) == digest(body)
    with pytest.raises(ValueError):
        binding.payload_sha256(
            binding.MboPayload(**record_body(price=S64_MIN - 1)),
            context,
            expected_protocol_sha256=digest(protocol_body()),
            expected_context_sha256=digest(context_body()),
        )


@pytest.mark.parametrize("api", ["bundle_sha256", "assess"])
@pytest.mark.parametrize("position", [1, 2, 3], ids=["first_target", "foreign", "final_target"])
@pytest.mark.parametrize("field", BODY_FIELDS)
def test_slice3_refreshed_outer_digest_cannot_mask_stale_old_body_pin(api, position, field):
    binding, bundle, pins, body = make_case("present")
    changed_projection = copy.deepcopy(body)
    changed_projection["payloads"][position][field] = changed_body_value(
        body["payloads"][position], field
    )
    changed_payload = binding.MboPayload(**changed_projection["payloads"][position])
    payloads = bundle.payloads[:position] + (changed_payload,) + bundle.payloads[position + 1 :]
    changed_bundle = replace(bundle, payloads=payloads)
    # Preserve the old complete cursor/item assertions; only refresh the new outer pin.
    refreshed_pins = pins | {"expected_bundle_sha256": digest(changed_projection)}
    with pytest.raises(ValueError):
        call_bundle(binding, api, changed_bundle, refreshed_pins)
