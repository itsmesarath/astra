"""Contract-first interface tests; root alone launches registered checks."""

import copy
import dataclasses
import importlib
import importlib.util
import inspect
import time
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
import source_publication_bridge_oracles_20261014 as oracle
import source_publication_bridge_rich_oracles_20261014 as rich_oracle
from source_publication_bridge_oracles_20261014 import (
    FIXTURE_ID,
    PROFILE_ID,
    PROTOCOL_SHA,
    SOURCE_SESSION,
    canonical,
    digest,
    expected_context,
    expected_protocol,
)

MODULE = "ai_trader.research.six_e_source_publication_bridge"
NATIVE_MODULE = "ai_trader.research.six_e_native_member_decode_evidence"


def bridge_module():
    specification = importlib.util.find_spec(MODULE)
    assert specification is not None, "missing public member-publication bridge behavior"
    return importlib.import_module(MODULE)


def native_context(**changes):
    native = importlib.import_module(NATIVE_MODULE)
    values = {
        "profile_id": PROFILE_ID,
        "member_compression": "ZSTD_CONCAT",
        "input_version": 3,
        "upgrade_policy": "AS_IS",
        "expected_ts_out": False,
    }
    values.update(changes)
    return native.MemberDecodeContext(**values)


def context(bridge, *, fixture_id=FIXTURE_ID, source_session=SOURCE_SESSION, **native_changes):
    return bridge.BridgeContext(fixture_id, source_session, native_context(**native_changes))


def forbid_native_dispatch(monkeypatch):
    native = importlib.import_module(NATIVE_MODULE)

    def forbidden(*args, **kwargs):
        raise AssertionError("T3 must not dispatch a native provider")

    monkeypatch.setattr(native, "decode_member", forbidden)
    monkeypatch.setattr(native, "verify", forbidden)


def test_protocol_is_complete_literal():
    # Deliberately discover inside the test: absence is an executed behavior RED,
    # never a collection/import failure hidden behind an expected exception.
    bridge = bridge_module()
    actual = bridge.protocol()
    assert type(actual) is dict
    assert canonical(actual) == canonical(expected_protocol())
    assert bridge.protocol_sha256() == PROTOCOL_SHA


def test_protocol_returns_fresh_deep_complete_body(monkeypatch):
    bridge = bridge_module()
    forbid_native_dispatch(monkeypatch)
    changed = bridge.protocol()
    changed["dependencies"]["native"]["schemas"]["U64"]["maximum_decimal"] = "0"
    changed["authority_names"].reverse()
    changed["dataclass_fields"]["BridgeContext"].append("unregistered")
    assert canonical(bridge.protocol()) == canonical(expected_protocol())
    assert bridge.protocol_sha256() == PROTOCOL_SHA


@pytest.mark.parametrize("function", expected_protocol()["projection_rules"][0]["functions"])
def test_exact_public_function_signatures(function):
    bridge = bridge_module()
    actual = inspect.signature(getattr(bridge, function["name"]))
    expected_names = function["positional"] + function["keyword_only"]
    assert list(actual.parameters) == expected_names
    for name, parameter in actual.parameters.items():
        expected_kind = (
            inspect.Parameter.POSITIONAL_OR_KEYWORD
            if name in function["positional"]
            else inspect.Parameter.KEYWORD_ONLY
        )
        assert parameter.kind is expected_kind
        assert parameter.default is inspect.Parameter.empty


@pytest.mark.parametrize("record", expected_protocol()["dataclass_fields"])
def test_four_complete_frozen_slotted_records(record):
    bridge = bridge_module()
    record_type = getattr(bridge, record)
    names = expected_protocol()["dataclass_fields"][record]
    # Reflection inspects the implementation only; expected declarations are the
    # independently reviewed complete literal packet, not reflected production.
    assert dataclasses.is_dataclass(record_type)
    assert record_type.__dataclass_params__.frozen is True
    assert tuple(record_type.__slots__) == tuple(names)
    assert [field.name for field in dataclasses.fields(record_type)] == names
    signature = inspect.signature(record_type)
    assert list(signature.parameters) == names
    for parameter in signature.parameters.values():
        assert parameter.default is inspect.Parameter.empty


@pytest.mark.parametrize("ts_out", [False, True], ids=["absent", "present"])
def test_context_hash_is_complete_independent_literal(ts_out, monkeypatch):
    bridge = bridge_module()
    forbid_native_dispatch(monkeypatch)
    original = context(bridge, expected_ts_out=ts_out)
    assert bridge.context_sha256(original, expected_protocol_sha256=PROTOCOL_SHA) == digest(
        expected_context(ts_out)
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        original.fixture_id = "synthetic-changed"
    assert not hasattr(original, "__dict__")


@pytest.mark.parametrize("field", ["fixture_id", "source_session"])
@pytest.mark.parametrize(
    "bad",
    [
        None,
        False,
        1,
        b"synthetic-a",
        "",
        "synthetic-",
        "a",
        "synthetic-a b",
        "synthetic-\u00e9",
        "synthetic-a\n",
        "synthetic-" + "a" * 55,
    ],
    ids=[
        "none",
        "bool",
        "int",
        "bytes",
        "empty",
        "empty-suffix",
        "wrong-prefix",
        "space",
        "nonascii",
        "newline",
        "too-long",
    ],
)
def test_context_rejects_invalid_labels(field, bad, monkeypatch):
    bridge = bridge_module()
    forbid_native_dispatch(monkeypatch)
    values = {"fixture_id": FIXTURE_ID, "source_session": SOURCE_SESSION}
    values[field] = bad
    original = context(bridge, **values)
    with pytest.raises(ValueError):
        bridge.context_sha256(original, expected_protocol_sha256=PROTOCOL_SHA)


@pytest.mark.parametrize("field", ["fixture_id", "source_session"])
def test_context_admits_exact_label_length_boundary(field, monkeypatch):
    bridge = bridge_module()
    forbid_native_dispatch(monkeypatch)
    values = {"fixture_id": FIXTURE_ID, "source_session": SOURCE_SESSION}
    values[field] = "synthetic-" + "a" * 54
    assert len(values[field]) == 64
    original = context(bridge, **values)
    assert bridge.context_sha256(original, expected_protocol_sha256=PROTOCOL_SHA) == digest(
        expected_context(**values)
    )


@pytest.mark.parametrize(
    "field,bad",
    [
        ("profile_id", "other"),
        ("member_compression", "NONE"),
        ("input_version", 2),
        ("input_version", True),
        ("input_version", 3.0),
        ("upgrade_policy", "UPGRADE"),
        ("expected_ts_out", 0),
        ("expected_ts_out", 1),
        ("expected_ts_out", None),
    ],
    ids=[
        "profile",
        "compression",
        "version",
        "bool-version",
        "float-version",
        "upgrade",
        "int-zero-mode",
        "int-one-mode",
        "none-mode",
    ],
)
def test_context_rejects_native_context_domain_changes(field, bad, monkeypatch):
    bridge = bridge_module()
    forbid_native_dispatch(monkeypatch)
    original = context(bridge, **{field: bad})
    with pytest.raises(ValueError):
        bridge.context_sha256(original, expected_protocol_sha256=PROTOCOL_SHA)


@pytest.mark.parametrize("kind", ["none", "dict", "object", "subclass"])
def test_context_requires_exact_record_type(kind, monkeypatch):
    bridge = bridge_module()
    forbid_native_dispatch(monkeypatch)
    values = {"none": None, "dict": expected_context(), "object": object()}
    if kind == "subclass":
        child = type("UnregisteredBridgeContext", (bridge.BridgeContext,), {})
        original = child(FIXTURE_ID, SOURCE_SESSION, native_context())
    else:
        original = values[kind]
    with pytest.raises(ValueError):
        bridge.context_sha256(original, expected_protocol_sha256=PROTOCOL_SHA)


PIN_CASES = [
    ("context_sha256", "expected_protocol_sha256"),
    *[
        ("replay", name)
        for name in (
            "expected_protocol_sha256",
            "expected_context_sha256",
            "expected_member_sha256",
            "expected_metadata_sha256",
        )
    ],
    *[
        ("verify", name)
        for name in (
            "expected_protocol_sha256",
            "expected_context_sha256",
            "expected_member_sha256",
            "expected_metadata_sha256",
            "expected_evidence_sha256",
        )
    ],
]


@pytest.mark.parametrize("api,pin_name", PIN_CASES, ids=[f"{a}-{p}" for a, p in PIN_CASES])
@pytest.mark.parametrize(
    "bad",
    [None, False, 0, b"a" * 64, "", "a" * 63, "a" * 65, "A" * 64, "g" * 64],
    ids=["none", "bool", "int", "bytes", "empty", "short", "long", "uppercase", "nonhex"],
)
def test_expected_pin_syntax_precedes_context_getter(api, pin_name, bad, monkeypatch):
    bridge = bridge_module()
    forbid_native_dispatch(monkeypatch)
    original = context(bridge)

    def forbidden_getter(_self):
        raise AssertionError("caller context traversed before every expected pin syntax")

    monkeypatch.setattr(bridge.BridgeContext, "fixture_id", property(forbidden_getter))
    keywords = {"expected_protocol_sha256": PROTOCOL_SHA}
    if api != "context_sha256":
        keywords.update(
            {
                "expected_context_sha256": digest(expected_context()),
                "expected_member_sha256": "a" * 64,
                "expected_metadata_sha256": "b" * 64,
            }
        )
    if api == "verify":
        keywords["expected_evidence_sha256"] = "c" * 64
    keywords[pin_name] = bad
    arguments = (original,) if api == "context_sha256" else (b"invented", original)
    if api == "verify":
        arguments = (object(), *arguments)
    with pytest.raises(ValueError):
        getattr(bridge, api)(*arguments, **keywords)


def test_wrong_protocol_pin_precedes_context_getter(monkeypatch):
    bridge = bridge_module()
    forbid_native_dispatch(monkeypatch)
    original = context(bridge)

    def forbidden_getter(_self):
        raise AssertionError("caller context traversed before protocol equality")

    monkeypatch.setattr(bridge.BridgeContext, "fixture_id", property(forbidden_getter))
    with pytest.raises(ValueError):
        bridge.context_sha256(original, expected_protocol_sha256="0" * 64)


def bridge_types():
    return (
        bridge_module(),
        importlib.import_module(NATIVE_MODULE),
        importlib.import_module("ai_trader.research.six_e_typed_native_event_adapter"),
        importlib.import_module("ai_trader.research.six_e_record_payload_binding"),
        importlib.import_module("ai_trader.research.six_e_native_cursor_metadata"),
    )


@contextmanager
def observe_original_native_seam(label):
    """Narrow registered observer; the ordinary public API owns every invocation."""
    host = importlib.import_module("ai_trader.research._native_member_host")
    original = host.run_decode
    captured = []
    started = datetime.now(UTC)
    wall_start, cpu_start = time.monotonic_ns(), time.process_time_ns()

    def recording_run(template, execution_sha):
        entry = {
            "template_before": copy.deepcopy(template),
            "template_after": None,
            "execution_sha256": execution_sha,
            "response": None,
            "receipt": None,
            "raised_type": None,
            "observation_error_type": None,
        }
        # Count invocation attempts, including original errors without receipts.
        captured.append(entry)
        try:
            result = original(template, execution_sha)
        except BaseException as error:
            entry["raised_type"] = type(error).__name__
            try:
                entry["template_after"] = copy.deepcopy(template)
                receipt = getattr(error, "receipt", None)
                entry["receipt"] = copy.deepcopy(receipt)
                if receipt is not None and receipt.get("response") is not None:
                    entry["response"] = copy.deepcopy(receipt["response"]["parsed_body"])
            except BaseException as observation_error:
                # Observation must not replace the original exception object.
                entry["observation_error_type"] = type(observation_error).__name__
            raise
        try:
            response, receipt = result
            entry["template_after"] = copy.deepcopy(template)
            entry["response"] = copy.deepcopy(response)
            entry["receipt"] = copy.deepcopy(receipt)
        except BaseException as observation_error:
            entry["observation_error_type"] = type(observation_error).__name__
        return result

    host.run_decode = recording_run
    try:
        yield captured
    finally:
        host.run_decode = original
        restored = host.run_decode is original
        finished = datetime.now(UTC)
        observation = {
            "schema": "bridge_public_call_observation_v1",
            "label": label,
            "started_utc": started.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "finished_utc": finished.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "elapsed_ns": time.monotonic_ns() - wall_start,
            "parent_process_cpu_ns": time.process_time_ns() - cpu_start,
            "attempted_native_calls": len(captured),
            "captured_native_receipts": sum(entry["receipt"] is not None for entry in captured),
            "original_callable_restored": restored,
            "parent_containment_claimed": False,
        }
        print("COMPLETE_BRIDGE_PUBLIC_CALL_OBSERVATION=" + canonical(observation).decode())
        for entry in captured:
            print("COMPLETE_BRIDGE_NATIVE_OBSERVATION=" + canonical(entry).decode())
        assert restored


def assert_one_original_native_call(captured, case):
    assert len(captured) == 1
    assert sum(entry["receipt"] is not None for entry in captured) == 1
    entry = captured[0]
    assert entry["raised_type"] is None
    assert entry["observation_error_type"] is None
    assert canonical(entry["template_before"]) == canonical(case["request_template"])
    assert canonical(entry["template_after"]) == canonical(case["request_template"])
    assert entry["execution_sha256"] == oracle.EXECUTION_SHA
    oracle.assert_native_receipt(
        entry["response"], entry["receipt"], case["request_template"], case["native"]
    )


@contextmanager
def observe_original_public_adapter_calls(label):
    """Observe only unchanged public APIs; no private reconstruction hook."""
    adapter = importlib.import_module("ai_trader.research.six_e_typed_native_event_adapter")
    names = ("fixture_sha256", "replay", "verify")
    originals = {name: getattr(adapter, name) for name in names}
    calls = {name: [] for name in names}

    def wrapper(name):
        def forwarding(*args, **kwargs):
            entry = {"args": args, "kwargs": dict(kwargs), "result": None, "raised_type": None}
            calls[name].append(entry)
            try:
                result = originals[name](*args, **kwargs)
            except BaseException as error:
                entry["raised_type"] = type(error).__name__
                raise
            entry["result"] = result
            return result

        return forwarding

    for name in names:
        setattr(adapter, name, wrapper(name))
    try:
        yield calls
    finally:
        for name, original in originals.items():
            setattr(adapter, name, original)
        restored = all(getattr(adapter, name) is original for name, original in originals.items())
        marker = {
            "schema": "bridge_public_adapter_calls_v1",
            "label": label,
            "original_callables_restored": restored,
            "calls": {
                name: [
                    {
                        "positional_object_ids": [id(value) for value in entry["args"]],
                        "keyword_arguments": entry["kwargs"],
                        "raised_type": entry["raised_type"],
                        "result_object_id": id(entry["result"]),
                        "scalar_result": entry["result"]
                        if type(entry["result"]) in (str, type(None))
                        else None,
                    }
                    for entry in entries
                ]
                for name, entries in calls.items()
            },
        }
        print("COMPLETE_BRIDGE_PUBLIC_ADAPTER_CALLS=" + canonical(marker).decode())
        assert restored


def assert_public_adapter_calls(calls, case, modules, *, submitted=None):
    operation = "replay" if submitted is None else "verify"
    assert {name: len(entries) for name, entries in calls.items()} == {
        "fixture_sha256": 1,
        "replay": int(operation == "replay"),
        "verify": int(operation == "verify"),
    }
    hashing, operation_call = calls["fixture_sha256"][0], calls[operation][0]
    assert hashing["raised_type"] is None and operation_call["raised_type"] is None
    assert len(hashing["args"]) == 1
    original = hashing["args"][0]
    assert canonical(oracle.observed_body(original, oracle.record_fields(*modules))) == canonical(
        case["adapter"]["fixture"]
    )
    assert hashing["result"] == case["adapter"]["fixture_sha256"]
    expected_keywords = {
        "expected_protocol_sha256": case["adapter"]["protocol_sha256"],
        "expected_context_sha256": case["adapter"]["context_sha256"],
        "expected_binding_protocol_sha256": case["adapter"]["binding_protocol_sha256"],
        "expected_cursor_protocol_sha256": case["adapter"]["cursor_protocol_sha256"],
        "expected_cursor_fixture_sha256": case["adapter"]["binding_assessment"][
            "cursor_fixture_sha256"
        ],
        "expected_binding_bundle_sha256": case["adapter"]["binding_assessment"]["bundle_sha256"],
    }
    oracle.exact_json(hashing["kwargs"], expected_keywords)
    expected_keywords["expected_fixture_sha256"] = case["adapter"]["fixture_sha256"]
    if submitted is None:
        assert len(operation_call["args"]) == 1 and operation_call["args"][0] is original
    else:
        assert len(operation_call["args"]) == 2
        assert operation_call["args"][0] is submitted
        assert operation_call["args"][1] is original
        assert operation_call["result"] is None
        expected_keywords["expected_assessment_sha256"] = case["adapter"]["assessment_sha256"]
    oracle.exact_json(operation_call["kwargs"], expected_keywords)


def print_complete_declaration(case, operation, ts_out):
    # Full bodies and original bytes are retained, not a short expected digest.
    print(
        "COMPLETE_INDEPENDENT_BRIDGE_DECLARATION="
        + canonical(
            {
                "schema": "bridge_minimal_independent_declaration_v1",
                "operation": operation,
                "ts_out": ts_out,
                "original_member_hex": case["member"].hex(),
                "original_decompressed_hex": case["raw"].hex(),
                "native_body": case["native"],
                "adapter_body": case["adapter"],
                "bridge_body": case["bridge"],
                "request_template": case["request_template"],
                "expected_native_invocations": 1,
            }
        ).decode()
    )


def print_submitted_object_ids(submitted):
    print(
        "COMPLETE_BRIDGE_SUBMITTED_OBJECT_IDS="
        + canonical(
            {
                "bridge": id(submitted),
                "native_evidence": id(submitted.native_evidence),
                "adapter_assessment": id(submitted.adapter_assessment),
            }
        ).decode()
    )


@pytest.mark.parametrize(
    "ts_out,iteration",
    [(False, "first"), (True, "first"), (False, "repeat"), (True, "repeat")],
    ids=["absent-first", "present-first", "absent-repeat", "present-repeat"],
)
def test_minimal_replay_complete_independent_body(ts_out, iteration):
    modules = bridge_types()
    bridge = modules[0]
    case = oracle.minimal_case(ts_out)
    expected = oracle.bridge_object(*modules, case["bridge"])
    fields = oracle.record_fields(*modules)
    assert canonical(oracle.observed_body(expected, fields)) == canonical(case["bridge"])
    print_complete_declaration(case, "replay-" + iteration, ts_out)
    with (
        observe_original_native_seam(f"replay-{iteration}-ts_out-{ts_out}") as captured,
        observe_original_public_adapter_calls(
            f"replay-{iteration}-ts_out-{ts_out}"
        ) as adapter_calls,
    ):
        actual = bridge.replay(
            case["member"],
            expected.context,
            expected_protocol_sha256=PROTOCOL_SHA,
            expected_context_sha256=case["bridge"]["context_sha256"],
            expected_member_sha256=case["native"]["member_sha256"],
            expected_metadata_sha256=case["native"]["metadata_sha256"],
        )
    actual_body = oracle.observed_body(actual, fields)
    print("COMPLETE_BRIDGE_ACTUAL_BODY=" + canonical(actual_body).decode())
    oracle.assert_exact_tree(actual, expected, fields)
    assert canonical(actual_body) == canonical(case["bridge"])
    assert_one_original_native_call(captured, case)
    assert_public_adapter_calls(adapter_calls, case, modules)


@pytest.mark.parametrize("ts_out", [False, True], ids=["absent", "present"])
def test_minimal_verify_complete_independent_submission(ts_out):
    modules = bridge_types()
    bridge = modules[0]
    case = oracle.minimal_case(ts_out)
    submitted = oracle.bridge_object(*modules, case["bridge"])
    fields = oracle.record_fields(*modules)
    assert canonical(oracle.observed_body(submitted, fields)) == canonical(case["bridge"])
    before = oracle.observed_body(submitted, fields)
    print_complete_declaration(case, "verify", ts_out)
    print_submitted_object_ids(submitted)
    with (
        observe_original_native_seam(f"verify-ts_out-{ts_out}") as captured,
        observe_original_public_adapter_calls(f"verify-ts_out-{ts_out}") as adapter_calls,
    ):
        # Submitted evidence is independently built, never obtained by replay.
        result = bridge.verify(
            submitted,
            case["member"],
            submitted.context,
            expected_protocol_sha256=PROTOCOL_SHA,
            expected_context_sha256=case["bridge"]["context_sha256"],
            expected_member_sha256=case["native"]["member_sha256"],
            expected_metadata_sha256=case["native"]["metadata_sha256"],
            expected_evidence_sha256=case["bridge"]["evidence_sha256"],
        )
    assert result is None
    assert canonical(oracle.observed_body(submitted, fields)) == canonical(before)
    print("COMPLETE_BRIDGE_VERIFIED_BODY=" + canonical(before).decode())
    assert_one_original_native_call(captured, case)
    assert_public_adapter_calls(
        adapter_calls, case, modules, submitted=submitted.adapter_assessment
    )


def replay_keywords(case):
    return {
        "expected_protocol_sha256": PROTOCOL_SHA,
        "expected_context_sha256": digest(
            expected_context(case["request_template"]["context"]["expected_ts_out"])
        ),
        "expected_member_sha256": case["native"]["member_sha256"],
        "expected_metadata_sha256": case["native"]["metadata_sha256"],
    }


@pytest.mark.parametrize("ts_out", [False, True], ids=["absent", "present"])
@pytest.mark.parametrize("variant", oracle.VARIANT_NAMES)
def test_actual_native_causal_variant_complete_body(variant, ts_out):
    """Actual provider cohort: one contained invocation, full independent output."""
    modules = bridge_types()
    bridge = modules[0]
    case = oracle.variant_case(variant, ts_out)
    expected = oracle.bridge_object(*modules, case["bridge"])
    fields = oracle.record_fields(*modules)
    assert canonical(oracle.observed_body(expected, fields)) == canonical(case["bridge"])
    print_complete_declaration(case, variant, ts_out)
    with (
        observe_original_native_seam(f"{variant}-ts_out-{ts_out}") as captured,
        observe_original_public_adapter_calls(f"{variant}-ts_out-{ts_out}") as adapter_calls,
    ):
        actual = bridge.replay(case["member"], expected.context, **replay_keywords(case))
    body = oracle.observed_body(actual, fields)
    print("COMPLETE_BRIDGE_ACTUAL_BODY=" + canonical(body).decode())
    oracle.assert_exact_tree(actual, expected, fields)
    assert canonical(body) == canonical(case["bridge"])
    assert_one_original_native_call(captured, case)
    assert_public_adapter_calls(adapter_calls, case, modules)
    base = oracle.minimal_case(ts_out)
    assert canonical(body["adapter_assessment"]["publications"][0]["features"]) == canonical(
        base["adapter"]["publications"][0]["features"]
    )
    assert body["evidence_sha256"] != base["bridge"]["evidence_sha256"]
    if variant.startswith("suffix-"):
        assert canonical(body["native_prefixes"][:5]) == canonical(
            base["bridge"]["native_prefixes"]
        )
        assert canonical(body["publication_links"]) == canonical(
            base["bridge"]["publication_links"]
        )
        assert canonical(body["adapter_assessment"]["publications"]) == canonical(
            base["adapter"]["publications"]
        )
    elif variant == "two-physical-frames":
        assert case["raw"] == base["raw"] and case["member"] != base["member"]
        assert canonical(body["native_prefixes"]) == canonical(base["bridge"]["native_prefixes"])
        assert canonical(body["publication_links"]) == canonical(
            base["bridge"]["publication_links"]
        )
        assert body["native_evidence"]["terminal"]["frame_count"] == 2
    elif variant.startswith("consumed-"):
        assert body["publication_links"][0]["decoded_position"] == 6
        other_name = "consumed-foreign-b" if variant.endswith("a") else "consumed-foreign-a"
        other = oracle.variant_case(other_name, ts_out)
        assert (
            body["publication_links"][0]["link_sha256"]
            != other["bridge"]["publication_links"][0]["link_sha256"]
        )
    else:
        other_name = (
            "header-inactive-first" if variant == "header-active-first" else "header-active-first"
        )
        other = oracle.variant_case(other_name, ts_out)
        assert body["native_evidence"]["metadata_sha256"] == other["native"]["metadata_sha256"]
        assert (
            body["native_prefixes"][0]["prefix_sha256"]
            != other["bridge"]["native_prefixes"][0]["prefix_sha256"]
        )
        assert (
            body["publication_links"][0]["link_sha256"]
            != other["bridge"]["publication_links"][0]["link_sha256"]
        )


@pytest.mark.parametrize("ts_out", [False, True], ids=["absent", "present"])
def test_actual_native_invalid_suffix_refuses_whole_bridge(ts_out):
    """Native U64 is valid; the complete old signed-int64 intersection is not."""
    modules = bridge_types()
    bridge, native = modules[:2]
    records = oracle.minimal_payloads(ts_out)
    invalid_suffix = copy.deepcopy(records[-1])
    invalid_suffix.update(
        instrument_id=99, ts_event=(1 << 64) - 1, ts_recv=oracle.NOON + oracle.SECOND
    )
    records.append(invalid_suffix)
    case = oracle.native_case_from_records(records, ts_out)
    original_context = bridge.BridgeContext(
        FIXTURE_ID,
        SOURCE_SESSION,
        oracle.native_object(native, expected_context(ts_out)["native_context"], "Context"),
    )
    print(
        "COMPLETE_INDEPENDENT_BRIDGE_REFUSAL_DECLARATION="
        + canonical(
            {
                "schema": "bridge_native_refusal_declaration_v1",
                "operation": "invalid-suffix",
                "ts_out": ts_out,
                "original_member_hex": case["member"].hex(),
                "original_decompressed_hex": case["raw"].hex(),
                "native_body": case["native"],
                "request_template": case["request_template"],
                "expected_native_invocations": 1,
                "expected_bridge_exception": "ValueError",
                "partial_output_allowed": False,
            }
        ).decode()
    )
    with observe_original_native_seam(f"invalid-suffix-ts_out-{ts_out}") as captured:
        with pytest.raises(ValueError):
            bridge.replay(case["member"], original_context, **replay_keywords(case))
    assert_one_original_native_call(captured, case)


METADATA_INTERSECTION_REFUSALS = (
    ("version", 2),
    ("dataset", "OTHER.MDP3"),
    ("start", oracle.DAY + 1),
    ("end_observed", None),
    ("end_observed", oracle.DAY + 1),
    ("limit_observed", 1),
    ("stype_in", None),
    ("symbols", []),
    ("symbols", ["6E.FUT", "OTHER.FUT"]),
    ("partial", ["6E.FUT"]),
    ("not_found", ["6E.FUT"]),
    ("ts_out", True),
)


@pytest.mark.parametrize(
    "field,bad",
    METADATA_INTERSECTION_REFUSALS,
    ids=[f"{field}-{index}" for index, (field, _) in enumerate(METADATA_INTERSECTION_REFUSALS)],
)
def test_mocked_metadata_intersection_precedes_mbo_getters(field, bad, monkeypatch):
    """Native-free boundary control, not a successful native-member assertion."""
    modules = bridge_types()
    bridge, native = modules[:2]
    case = oracle.minimal_case()
    native_body = copy.deepcopy(case["native"])
    native_body["occurrences"][0]["projection"][field] = bad
    returned = oracle.native_object(native, native_body)
    mbo_type = type(returned.occurrences[1].projection)
    calls = []

    def public_provider(*args, **kwargs):
        calls.append((args, kwargs))
        return returned

    def forbidden_getter(_self):
        raise AssertionError("MBO getter reached before complete Metadata intersection")

    monkeypatch.setattr(native, "decode_member", public_provider)
    monkeypatch.setattr(mbo_type, "publisher_id", property(forbidden_getter))
    with pytest.raises(ValueError):
        bridge.replay(case["member"], context(bridge), **replay_keywords(case))
    assert len(calls) == 1


@pytest.mark.parametrize("authority", expected_protocol()["authority_names"])
def test_verify_outer_authorities_precede_native_body(authority, monkeypatch):
    modules = bridge_types()
    bridge = modules[0]
    case = oracle.minimal_case()
    body = copy.deepcopy(case["bridge"])
    body["authorities"] = [[name, name == authority] for name, _ in body["authorities"]]
    submitted = oracle.bridge_object(*modules, body)
    native_type = type(submitted.native_evidence)

    def forbidden_body(_self):
        raise AssertionError("native body accessed before every top authority was false")

    monkeypatch.setattr(native_type, "occurrences", property(forbidden_body))
    forbid_native_dispatch(monkeypatch)
    with pytest.raises(ValueError):
        bridge.verify(
            submitted,
            case["member"],
            submitted.context,
            **replay_keywords(case),
            expected_evidence_sha256=body["evidence_sha256"],
        )


RAW_FIELD_MAXIMA = {
    "publisher_id": (1 << 16) - 1,
    "instrument_id": (1 << 32) - 1,
    "ts_event": (1 << 63) - 1,
    "order_id": (1 << 64) - 1,
    "price": (1 << 63) - 1,
    "size": (1 << 32) - 1,
    "action": 127,
    "side": 127,
    "ts_recv": (1 << 63) - 1,
    "flags": 255,
    "channel_id": 255,
    "ts_in_delta": (1 << 31) - 1,
    "sequence": (1 << 32) - 1,
    "ts_out": (1 << 63) - 1,
    "rtype": 160,
    "record_size": 64,
}


@pytest.mark.parametrize("field", RAW_FIELD_MAXIMA)
@pytest.mark.parametrize("kind", ["bool", "float", "above-domain", "below-domain"])
def test_mocked_every_raw_slot_exact_type_and_domain(field, kind, monkeypatch):
    """Mocked malformed dependency return, no native receipt or proof claimed."""
    assert_mocked_raw_slot_refusal(field, kind, monkeypatch, occurrence_index=1)


@pytest.mark.parametrize("field", RAW_FIELD_MAXIMA)
@pytest.mark.parametrize("kind", ["bool", "float", "above-domain", "below-domain"])
def test_mocked_every_foreign_raw_slot_exact_type_and_domain(field, kind, monkeypatch):
    """Foreign occurrences retain the same complete raw-domain obligations."""
    assert_mocked_raw_slot_refusal(field, kind, monkeypatch, occurrence_index=4)


def assert_mocked_raw_slot_refusal(field, kind, monkeypatch, *, occurrence_index):
    modules = bridge_types()
    bridge, native = modules[:2]
    case = (
        oracle.minimal_case(True)
        if occurrence_index == 1
        else oracle.variant_case("consumed-foreign-a", True)
    )
    body = copy.deepcopy(case["native"])
    wire = body["dbn_framing"]["spans"][occurrence_index]["wire_fields"]
    projection = body["occurrences"][occurrence_index]["projection"]
    minimum = {"price": -(1 << 63), "ts_in_delta": -(1 << 31), "rtype": 160, "record_size": 64}.get(
        field, 0
    )
    bad = (
        True
        if kind == "bool"
        else 1.0
        if kind == "float"
        else minimum - 1
        if kind == "below-domain"
        else RAW_FIELD_MAXIMA[field] + 1
    )
    if field in ("action", "side"):
        wire[field] = bad
        projection[field] = {
            "kind": "str",
            "value": chr(bad) if type(bad) is int and bad >= 0 else bad,
        }
    elif field == "rtype":
        wire[field] = bad
        projection[field]["code"] = bad
    elif field == "record_size":
        wire["length_words"] = bad
        projection["record_size_observed"] = bad
    elif field == "ts_out":
        wire[field] = bad
        projection["ts_out_observed"] = bad
    else:
        wire[field] = bad
        projection[field] = bad
        if field == "ts_recv":
            projection["ts_index_observed"] = bad
    oracle.rehash_mock_native_declarations(body)
    returned = oracle.native_object(native, body)
    calls = []

    def public_provider(*args, **kwargs):
        calls.append((args, kwargs))
        return returned

    original_payload = modules[3].payload_sha256
    payload_calls = []

    def forbidden_payload_boundary(*args, **kwargs):
        payload_calls.append((args, kwargs))
        if len(payload_calls) == occurrence_index:
            raise AssertionError(f"raw {field}/{kind} crossed the bridge's exact-domain boundary")
        return original_payload(*args, **kwargs)

    monkeypatch.setattr(native, "decode_member", public_provider)
    monkeypatch.setattr(modules[3], "payload_sha256", forbidden_payload_boundary)
    with pytest.raises(ValueError):
        bridge.replay(
            case["member"], context(bridge, expected_ts_out=True), **replay_keywords(case)
        )
    assert len(calls) == 1


LINK_REFUSALS = (
    ("native_prefixes", "decoded_position", 0),
    ("native_prefixes", "kind", "mbo"),
    ("native_prefixes", "wire_span_ordinal", True),
    ("native_prefixes", "decompressed_start", -1),
    ("native_prefixes", "decompressed_end", 0),
    *[
        ("native_prefixes", field, "g" * 64)
        for field in (
            "wire_sha256",
            "wire_fields_sha256",
            "projection_sha256",
            "previous_prefix_sha256",
            "prefix_sha256",
        )
    ],
    *[
        ("publication_links", field, True)
        for field in (
            "publication_ordinal",
            "quote_ordinal",
            "event_ordinal",
            "decoded_position",
            "ts_recv_ns",
        )
    ],
    *[
        ("publication_links", field, "g" * 64)
        for field in (
            "adapter_prefix_sha256",
            "publication_sha256",
            "native_prefix_sha256",
            "link_sha256",
        )
    ],
)


@pytest.mark.parametrize(
    "family,field,bad",
    LINK_REFUSALS,
    ids=[f"{family}-{field}" for family, field, _ in LINK_REFUSALS],
)
def test_verify_new_link_shape_precedes_native_body(family, field, bad, monkeypatch):
    modules = bridge_types()
    bridge = modules[0]
    case = oracle.minimal_case()
    body = copy.deepcopy(case["bridge"])
    body[family][0][field] = bad
    submitted = oracle.bridge_object(*modules, body)

    def forbidden_body(_self):
        raise AssertionError("native body accessed before complete new-link preflight")

    monkeypatch.setattr(type(submitted.native_evidence), "occurrences", property(forbidden_body))
    forbid_native_dispatch(monkeypatch)
    with pytest.raises(ValueError):
        bridge.verify(
            submitted,
            case["member"],
            submitted.context,
            **replay_keywords(case),
            expected_evidence_sha256=body["evidence_sha256"],
        )


MAPPING_REFUSALS = (
    "missing-target",
    "no-active-target",
    "duplicate-group",
    "multiple-active",
    "inactive-nonascii-name",
    "inactive-nonascii-symbol",
    "inactive-date-before-2000",
    "inactive-reversed-date",
    "inactive-name-too-long",
    "inactive-symbol-too-long",
    "nine-groups",
    "seventeen-intervals",
    "thirty-three-total-intervals",
    "active-nondecimal",
    "active-u32-overflow",
)


def mapping_refusal_groups(kind):
    active = ("6EM5", [(20250407, 20250408, "0007")])
    inactive = ("6EZ5", [(20251201, 20251202, "0042")])
    if kind == "missing-target":
        return [inactive]
    if kind == "no-active-target":
        return [("6EM5", [(20250408, 20250409, "0007")])]
    if kind == "duplicate-group":
        return [active, active]
    if kind == "multiple-active":
        return [("6EM5", [(20250407, 20250408, "0007"), (20250406, 20250408, "0008")])]
    if kind == "inactive-nonascii-name":
        return [active, ("6E\u00c95", inactive[1])]
    if kind == "inactive-nonascii-symbol":
        return [active, ("6EZ5", [(20251201, 20251202, "\u00e9")])]
    if kind == "inactive-date-before-2000":
        return [active, ("6EZ5", [(19990101, 19990102, "0042")])]
    if kind == "inactive-reversed-date":
        return [active, ("6EZ5", [(20251202, 20251201, "0042")])]
    if kind == "inactive-name-too-long":
        return [active, ("X" * 33, inactive[1])]
    if kind == "inactive-symbol-too-long":
        return [active, ("6EZ5", [(20251201, 20251202, "X" * 33)])]
    if kind == "nine-groups":
        return [active] + [(f"6EZ{index}", inactive[1]) for index in range(8)]
    if kind == "seventeen-intervals":
        return [active, ("6EZ5", [(20251201 + i, 20251202 + i, "0042") for i in range(17)])]
    if kind == "thirty-three-total-intervals":
        intervals = [(20251201 + i, 20251202 + i, "0042") for i in range(16)]
        return [active, ("6EZ5", intervals), ("6EZ6", intervals)]
    if kind == "active-nondecimal":
        return [("6EM5", [(20250407, 20250408, "7x")])]
    assert kind == "active-u32-overflow"
    return [("6EM5", [(20250407, 20250408, "4294967296")])]


@pytest.mark.parametrize("kind", MAPPING_REFUSALS)
def test_mocked_all_mapping_groups_checked_before_mbo_getters(kind, monkeypatch):
    modules = bridge_types()
    bridge, native = modules[:2]
    case = oracle.native_case_from_records(
        oracle.minimal_payloads(False),
        header=oracle.metadata_with_groups(False, mapping_refusal_groups(kind)),
    )
    returned = oracle.native_object(native, case["native"])
    calls = []

    def public_provider(*args, **kwargs):
        calls.append((args, kwargs))
        return returned

    def forbidden_getter(_self):
        raise AssertionError(
            "MBO body accessed before complete inactive and target mapping admission"
        )

    monkeypatch.setattr(native, "decode_member", public_provider)
    monkeypatch.setattr(
        type(returned.occurrences[1].projection), "publisher_id", property(forbidden_getter)
    )
    with pytest.raises(ValueError):
        bridge.replay(case["member"], context(bridge), **replay_keywords(case))
    assert len(calls) == 1


def object_at_path(value, path):
    for component in path:
        value = value[component] if type(component) is int else getattr(value, component)
    return value


def replaced_path(value, path, replacement):
    """Explicit selected test path; never mutate or reflect the other branches."""
    if not path:
        return replacement
    head, *tail = path
    if type(head) is int:
        assert type(value) is tuple
        return value[:head] + (replaced_path(value[head], tail, replacement),) + value[head + 1 :]
    return dataclasses.replace(
        value, **{head: replaced_path(getattr(value, head), tail, replacement)}
    )


def prepared_mock_verification(monkeypatch, *, variant="consumed-foreign-a"):
    """Explicit native-free submitted-shape controls, not native verification."""
    modules = bridge_types()
    case = oracle.variant_case(variant, False)
    submitted = oracle.bridge_object(*modules, case["bridge"])
    native_calls = []

    def original_native_verify(*args, **kwargs):
        native_calls.append((args, kwargs))
        return None

    def forbidden_decode(*args, **kwargs):
        raise AssertionError("verify must not adopt replay/decode or retry")

    monkeypatch.setattr(modules[1], "verify", original_native_verify)
    monkeypatch.setattr(modules[1], "decode_member", forbidden_decode)
    return modules, case, submitted, native_calls


def call_mock_verification(modules, case, submitted):
    return modules[0].verify(
        submitted,
        case["member"],
        context(modules[0]),
        **replay_keywords(case),
        expected_evidence_sha256=submitted.evidence_sha256,
    )


def forbid_late_adapter_verify(monkeypatch, modules):
    def forbidden(*args, **kwargs):
        raise AssertionError("malformed submitted shape crossed into public adapter.verify")

    monkeypatch.setattr(modules[2], "verify", forbidden)


class NestedTupleBomb(tuple):
    def __iter__(self):
        raise AssertionError("nested scalar poison was traversed")


RAW_BRANCHES = (
    ("fixture", "payload_bundle"),
    ("binding_assessment", "bundle"),
)


@pytest.mark.parametrize("field", RAW_FIELD_MAXIMA)
@pytest.mark.parametrize("payload_index", [1, 4], ids=["target", "foreign"])
@pytest.mark.parametrize("branch", RAW_BRANCHES, ids=["independent-fixture", "independent-binding"])
def test_mocked_verify_every_raw_scalar_rejects_nested_container(
    field,
    payload_index,
    branch,
    monkeypatch,
):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    path = ("adapter_assessment", *branch, "payloads", payload_index, field)
    poison = (NestedTupleBomb((0,)),)
    submitted = replaced_path(submitted, path, poison)
    forbid_late_adapter_verify(monkeypatch, modules)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


@pytest.mark.parametrize("field", RAW_FIELD_MAXIMA)
@pytest.mark.parametrize("payload_index", [1, 4], ids=["target", "foreign"])
@pytest.mark.parametrize("branch", RAW_BRANCHES, ids=["independent-fixture", "independent-binding"])
def test_mocked_verify_every_raw_getter_preserves_uncaught_sentinel(
    field,
    payload_index,
    branch,
    monkeypatch,
):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    path = ("adapter_assessment", *branch, "payloads", payload_index)
    selected = object_at_path(submitted, path)
    record_type = type(selected)
    descriptor = getattr(record_type, field)

    def selected_getter(value):
        if value is selected:
            raise AssertionError("selected submitted raw getter reached")
        return descriptor.__get__(value, record_type)

    def original_setter(value, assigned):
        descriptor.__set__(value, assigned)

    monkeypatch.setattr(record_type, field, property(selected_getter, original_setter))
    with pytest.raises(AssertionError, match="selected submitted raw getter reached"):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


@pytest.mark.parametrize(
    "index", range(37), ids=expected_protocol()["dependencies"]["adapter"]["feature_names"]
)
@pytest.mark.parametrize("bad_kind", ["nested", "bool", "nan", "infinity"])
def test_mocked_verify_feature_shape_or_nonfinite_value_refuses_at_scoped_boundary(
    index, bad_kind, monkeypatch
):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    bad = {
        "nested": (NestedTupleBomb((0,)),),
        "bool": True,
        "nan": float("nan"),
        "infinity": float("inf"),
    }[bad_kind]
    submitted = replaced_path(
        submitted,
        ("adapter_assessment", "publications", 0, "features", index, 1),
        bad,
    )
    if bad_kind in ("nested", "bool"):
        forbid_late_adapter_verify(monkeypatch, modules)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


NUMERIC_SHAPE_PATHS = (
    *[
        ("transitions", 3, name)
        for name in (
            "decoded_position",
            "target_transition_ordinal",
            "snapshot",
            "exceptional_closed_clear",
            "order_id",
            "initialized_before",
            "initialized_after",
            "last_recv_before",
            "last_recv_after",
            "event_ordinal",
            "quote_ordinal",
            "publication_ordinal",
        )
    ],
    *[("transitions", 1, "after", name) for name in ("price", "size")],
    *[
        ("events", 0, name)
        for name in (
            "event_ordinal",
            "closing_decoded_position",
            "closing_target_transition_ordinal",
            "ts_recv_ns",
            "quote_ordinal",
        )
    ],
    *[
        ("quotes", 0, name)
        for name in (
            "quote_ordinal",
            "event_ordinal",
            "decoded_position",
            "ts_recv_ns",
            "bid",
            "ask",
            "bid_qty",
            "ask_qty",
            "prior_quote_gap_ns",
            "ofi_generation",
        )
    ],
    *[
        ("quotes", 0, side, 0, name)
        for side in ("bid_depth5", "ask_depth5")
        for name in ("price", "size")
    ],
    *[
        ("inactivity_intervals", 0, name)
        for name in (
            "start_ns",
            "timer_fired_ns",
            "end_ns",
            "recovered",
            "trigger_decoded_position",
        )
    ],
    *[
        ("clock_quality", name)
        for name in (
            "target_records",
            "snapshot_records",
            "non_snapshot_records",
            "event_after_receive",
            "negative_send_delta",
            "event_after_sending",
            "clamped_delta",
            "clock_disagreement_records",
            "protected_disagreement_records",
            "outside_disagreement_records",
            "min_event_ahead_ns",
            "max_event_ahead_ns",
            "min_negative_delta_ns",
        )
    ],
    *[
        ("terminal_state", name)
        for name in (
            "initialized",
            "last_recv_ns",
            "last_quote_ordinal",
            "cvd",
            "known_trades",
            "unknown_trades",
            "ofi_generation",
            "ofi_previous_quote_ordinal",
            "ofi_first_ts_ns",
            "ofi_total",
            "history_ofi_generation",
            "execution_last_ts_ns",
            "next_publication_ns",
            "watch_since_ns",
            "inactivity_start_ns",
            "window_closed",
        )
    ],
    ("terminal_state", "orders", 0, "order_id"),
    *[("terminal_state", "orders", 0, "state", name) for name in ("price", "size")],
    *[
        ("terminal_state", side, 0, name)
        for side in ("bid_levels", "ask_levels")
        for name in ("price", "size")
    ],
    ("exceptional_clear_count",),
)


@pytest.mark.parametrize("path", NUMERIC_SHAPE_PATHS, ids=lambda path: ".".join(map(str, path)))
def test_mocked_verify_every_numeric_record_family_refuses_nested_scalar(path, monkeypatch):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    submitted = replaced_path(submitted, ("adapter_assessment", *path), (NestedTupleBomb((0,)),))
    forbid_late_adapter_verify(monkeypatch, modules)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


TERMINAL_QUEUE_ROWS = {
    "pending_target_positions": 2,
    "pending_trade_positions": 2,
    "execution_capture_positions": 2,
    "history_quote_ordinals": 1,
    "flow_events": (oracle.NOON, 1, 2, 3),
    "ofi_events": (oracle.NOON, 1),
    "bid_depletions": (oracle.NOON, 1),
    "ask_depletions": (oracle.NOON, 1),
    "history_reloads": (oracle.NOON, 1, 2),
    "bid_credits": (oracle.NOON, 1, 2),
    "ask_credits": (oracle.NOON, 1, 2),
    "execution_events": (oracle.NOON, (("completed_events", 1),)),
    "execution_totals": ("completed_events", 1),
    "execution_audit": ("completed_events", 1),
}


QUEUE_SCALAR_PATHS = (
    *[
        (name, ())
        for name in (
            "pending_target_positions",
            "pending_trade_positions",
            "execution_capture_positions",
            "history_quote_ordinals",
        )
    ],
    *[
        (name, (index,))
        for name, width in (
            ("flow_events", 4),
            ("ofi_events", 2),
            ("bid_depletions", 2),
            ("ask_depletions", 2),
            ("history_reloads", 3),
            ("bid_credits", 3),
            ("ask_credits", 3),
        )
        for index in range(width)
    ],
    ("execution_events", (0,)),
    ("execution_events", (1, 0, 1)),
    ("execution_totals", (1,)),
    ("execution_audit", (1,)),
)


@pytest.mark.parametrize(
    "name,leaf",
    QUEUE_SCALAR_PATHS,
    ids=[name + "-" + "-".join(map(str, leaf)) for name, leaf in QUEUE_SCALAR_PATHS],
)
def test_mocked_verify_terminal_queue_and_metric_leaves_refuse_nested_scalar(
    name, leaf, monkeypatch
):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    row = replaced_path(TERMINAL_QUEUE_ROWS[name], leaf, (NestedTupleBomb((0,)),))
    submitted = replaced_path(submitted, ("adapter_assessment", "terminal_state", name), (row,))
    forbid_late_adapter_verify(monkeypatch, modules)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


CLOCK_SAMPLE_FIELDS = (
    "decoded_position",
    "ts_recv",
    "ts_event",
    "ts_in_delta",
    "flags",
    "sequence",
    "action",
    "protected",
    "event_ahead_ns",
    "sending_ns",
)


@pytest.mark.parametrize("field", CLOCK_SAMPLE_FIELDS)
def test_mocked_verify_clock_sample_leaf_refuses_nested_scalar(field, monkeypatch):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    sample = modules[2].ClockSample(
        2, oracle.NOON, oracle.NOON + 1, 0, 0, 1, "N", False, 1, oracle.NOON
    )
    sample = dataclasses.replace(sample, **{field: (NestedTupleBomb((0,)),)})
    submitted = replaced_path(
        submitted, ("adapter_assessment", "clock_quality", "samples"), (sample,)
    )
    forbid_late_adapter_verify(monkeypatch, modules)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


BOUNDED_ADAPTER_TUPLES = (
    (("audits",), 128),
    (("transitions",), 127),
    (("events",), 127),
    (("quotes",), 127),
    (("publications",), 32),
    (("inactivity_intervals",), 128),
    (("clock_quality", "samples"), 8),
    (("publications", 0, "features"), 37),
    (("quotes", 0, "bid_depth5"), 5),
    (("quotes", 0, "ask_depth5"), 5),
    *[
        (("events", 0, name), 127)
        for name in ("target_positions", "trade_positions", "execution_capture_positions")
    ],
    *[
        (("terminal_state", name), 160 if name in ("execution_totals", "execution_audit") else 127)
        for name in ("orders", "bid_levels", "ask_levels", *TERMINAL_QUEUE_ROWS)
    ],
    (("fixture", "payload_bundle", "payloads"), 128),
    (("binding_assessment", "bundle", "payloads"), 128),
    (("binding_assessment", "audits"), 128),
    (("binding_assessment", "cursor_assessment", "audits"), 128),
)


@pytest.mark.parametrize(
    "path,maximum",
    BOUNDED_ADAPTER_TUPLES,
    ids=[".".join(map(str, path)) for path, _ in BOUNDED_ADAPTER_TUPLES],
)
def test_mocked_verify_count_plus_one_refuses_complete_container(path, maximum, monkeypatch):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    original = object_at_path(submitted, ("adapter_assessment", *path))
    if original:
        selected = original[1] if path[-1] == "payloads" else original[0]
    elif path == ("clock_quality", "samples"):
        selected = modules[2].ClockSample(
            2,
            oracle.NOON,
            oracle.NOON + 1,
            0,
            0,
            1,
            "N",
            False,
            1,
            oracle.NOON,
        )
    elif path[0] == "terminal_state":
        selected = TERMINAL_QUEUE_ROWS[path[-1]]
    elif path[0] == "events":
        selected = 2
    else:
        raise AssertionError("missing independent exact-shape cardinality seed")
    # Every element has a valid declared shape. The forbidden later boundary
    # therefore distinguishes an omitted count guard from a bad first element.
    submitted = replaced_path(submitted, ("adapter_assessment", *path), (selected,) * (maximum + 1))
    forbid_late_adapter_verify(monkeypatch, modules)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


def test_mocked_verify_nested_execution_metric_first_excess_precedes_adapter(monkeypatch):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    row = (oracle.NOON, (("completed_events", 1),) * 161)
    submitted = replaced_path(
        submitted, ("adapter_assessment", "terminal_state", "execution_events"), (row,)
    )
    forbid_late_adapter_verify(monkeypatch, modules)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


RECORD_CONTAINER_FIELDS = (
    (("audits",), "decoded_position"),
    (("transitions",), "decoded_position"),
    (("events",), "event_ordinal"),
    (("quotes",), "quote_ordinal"),
    (("publications",), "publication_ordinal"),
    (("inactivity_intervals",), "start_ns"),
    (("quotes", 0, "bid_depth5"), "price"),
    (("quotes", 0, "ask_depth5"), "price"),
    (("terminal_state", "orders"), "order_id"),
    (("terminal_state", "bid_levels"), "price"),
    (("terminal_state", "ask_levels"), "price"),
    (("fixture", "payload_bundle", "payloads"), "publisher_id"),
    (("binding_assessment", "bundle", "payloads"), "publisher_id"),
    (("binding_assessment", "audits"), "decoded_position"),
    (("binding_assessment", "cursor_assessment", "audits"), "decoded_position"),
)


@pytest.mark.parametrize(
    "path,field",
    RECORD_CONTAINER_FIELDS,
    ids=[".".join(map(str, path)) for path, _ in RECORD_CONTAINER_FIELDS],
)
def test_mocked_verify_record_count_plus_one_precedes_real_getter(path, field, monkeypatch):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    values = object_at_path(submitted, ("adapter_assessment", *path))
    selected = values[1] if path[-1] == "payloads" else values[0]
    maximum = dict(BOUNDED_ADAPTER_TUPLES)[path]
    submitted = replaced_path(submitted, ("adapter_assessment", *path), (selected,) * (maximum + 1))
    record_type = type(selected)
    descriptor = getattr(record_type, field)

    def selected_getter(value):
        if value is selected:
            raise AssertionError("count-plus-one traversed its first exact record")
        return descriptor.__get__(value, record_type)

    def original_setter(value, assigned):
        descriptor.__set__(value, assigned)

    monkeypatch.setattr(record_type, field, property(selected_getter, original_setter))
    forbid_late_adapter_verify(monkeypatch, modules)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


DEPENDENCY_LAYERS = {
    "adapter": ("adapter_assessment",),
    "binding": ("adapter_assessment", "binding_assessment"),
    "cursor": ("adapter_assessment", "binding_assessment", "cursor_assessment"),
}
DEPENDENCY_AUTHORITIES = tuple(
    (layer, index, name)
    for layer in DEPENDENCY_LAYERS
    for index, name in enumerate(expected_protocol()["dependencies"][layer]["authority_flags"])
)


@pytest.mark.parametrize(
    "layer,index,name",
    DEPENDENCY_AUTHORITIES,
    ids=[layer + "-" + name for layer, _, name in DEPENDENCY_AUTHORITIES],
)
@pytest.mark.parametrize("bad", [True, 0], ids=["true", "int-zero-alias"])
def test_mocked_verify_every_nested_authority_is_literal_false(
    layer, index, name, bad, monkeypatch
):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    path = (*DEPENDENCY_LAYERS[layer], "authority_flags", index, 1)
    submitted = replaced_path(submitted, path, bad)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


DEPENDENCY_HASH_PATHS = (
    *[
        ("adapter_assessment", name)
        for name in (
            "protocol_sha256",
            "context_sha256",
            "binding_protocol_sha256",
            "cursor_protocol_sha256",
            "fixture_sha256",
            "assessment_sha256",
        )
    ],
    *[
        ("adapter_assessment", "binding_assessment", name)
        for name in (
            "protocol_sha256",
            "cursor_protocol_sha256",
            "context_sha256",
            "bundle_sha256",
            "cursor_fixture_sha256",
            "assessment_sha256",
        )
    ],
    *[
        ("adapter_assessment", "binding_assessment", "cursor_assessment", name)
        for name in ("protocol_sha256", "fixture_sha256", "assessment_sha256")
    ],
    *[
        ("adapter_assessment", "audits", 1, name)
        for name in ("binding_prefix_sha256", "adapter_prefix_sha256")
    ],
    *[
        ("adapter_assessment", "events", 0, name)
        for name in ("adapter_prefix_sha256", "event_sha256")
    ],
    *[
        ("adapter_assessment", "quotes", 0, name)
        for name in ("adapter_prefix_sha256", "quote_sha256")
    ],
    *[
        ("adapter_assessment", "publications", 0, name)
        for name in ("adapter_prefix_sha256", "publication_sha256")
    ],
)


@pytest.mark.parametrize("path", DEPENDENCY_HASH_PATHS, ids=lambda path: ".".join(map(str, path)))
def test_mocked_verify_complete_nested_hash_tampering_refuses(path, monkeypatch):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    original = object_at_path(submitted, path)
    assert type(original) is str and len(original) == 64
    submitted = replaced_path(submitted, path, "0" * 64 if original != "0" * 64 else "1" * 64)
    # This is whole-object tamper rejection, not a claim that a particular stale
    # inner digest is the first rejection. No production serializer is an oracle.
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


@pytest.mark.parametrize("layer", DEPENDENCY_LAYERS)
@pytest.mark.parametrize("field,bad", [("status", "accepted"), ("status", True)])
def test_mocked_verify_nested_status_refuses(layer, field, bad, monkeypatch):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    submitted = replaced_path(submitted, (*DEPENDENCY_LAYERS[layer], field), bad)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


TAMPERED_TUPLE_PATHS = (
    ("adapter_assessment", "audits"),
    ("adapter_assessment", "transitions"),
    ("adapter_assessment", "events"),
    ("adapter_assessment", "quotes"),
    ("adapter_assessment", "publications"),
    ("adapter_assessment", "inactivity_intervals"),
    ("adapter_assessment", "publications", 0, "features"),
    ("adapter_assessment", "terminal_state", "orders"),
    ("adapter_assessment", "binding_assessment", "audits"),
    ("adapter_assessment", "binding_assessment", "cursor_assessment", "audits"),
    ("adapter_assessment", "fixture", "payload_bundle", "payloads"),
    ("adapter_assessment", "binding_assessment", "bundle", "payloads"),
)


@pytest.mark.parametrize("path", TAMPERED_TUPLE_PATHS, ids=lambda path: ".".join(map(str, path)))
@pytest.mark.parametrize("kind", ["missing", "extra", "reordered"])
def test_mocked_verify_complete_nested_sequence_tampering_refuses(path, kind, monkeypatch):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    original = object_at_path(submitted, path)
    assert type(original) is tuple and original
    if kind == "missing":
        changed = original[:-1]
    elif kind == "extra":
        changed = original + (original[-1],)
    elif len(original) > 1:
        changed = original[1:] + original[:1]
    else:
        # A singleton cannot be reordered; duplicating it is explicitly a
        # structural tamper, not evidence for a nonexistent permutation.
        changed = original + original
    submitted = replaced_path(submitted, path, changed)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


CAUSAL_HASH_PATHS = (
    *[
        ("native_prefixes", index, name)
        for index in (0, 4, 5)
        for name in (
            "wire_sha256",
            "wire_fields_sha256",
            "projection_sha256",
            "previous_prefix_sha256",
            "prefix_sha256",
        )
    ],
    *[
        ("publication_links", 0, name)
        for name in (
            "adapter_prefix_sha256",
            "publication_sha256",
            "native_prefix_sha256",
            "link_sha256",
        )
    ],
)


@pytest.mark.parametrize("path", CAUSAL_HASH_PATHS, ids=lambda path: ".".join(map(str, path)))
def test_mocked_verify_causal_body_mismatch_refuses_even_matching_outer_digest(path, monkeypatch):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    original = object_at_path(submitted, path)
    submitted = replaced_path(submitted, path, "0" * 64 if original != "0" * 64 else "1" * 64)
    submitted_body = oracle.observed_body(submitted, oracle.record_fields(*modules))
    submitted_body.pop("evidence_sha256")
    submitted = dataclasses.replace(submitted, evidence_sha256=digest(submitted_body))
    # Correct outer self-consistency cannot replace independently recomputed
    # header/foreign/target links or the actual publication's consumed cursor.
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


@pytest.mark.parametrize("operation", ["replay", "verify"])
@pytest.mark.parametrize("boundary", ["native", "adapter"])
@pytest.mark.parametrize(
    "exception_type",
    [RuntimeError, AssertionError, MemoryError, OSError, KeyboardInterrupt, SystemExit],
)
def test_mocked_operational_failures_preserve_identity_without_retry(
    operation,
    boundary,
    exception_type,
    monkeypatch,
):
    modules = bridge_types()
    bridge, native, adapter = modules[:3]
    case = oracle.minimal_case()
    submitted = oracle.bridge_object(*modules, case["bridge"])
    expected_exception = exception_type("registered operational sentinel")
    calls = []
    native_calls = []

    def native_success(*args, **kwargs):
        native_calls.append((args, kwargs))
        return submitted.native_evidence if operation == "replay" else None

    def failure(*args, **kwargs):
        calls.append((args, kwargs))
        raise expected_exception

    native_function = "decode_member" if operation == "replay" else "verify"
    monkeypatch.setattr(
        native, native_function, failure if boundary == "native" else native_success
    )
    complementary_native_function = "verify" if operation == "replay" else "decode_member"

    def forbidden_complementary_native(*args, **kwargs):
        raise AssertionError("mock-only operational control attempted complementary native API")

    monkeypatch.setattr(native, complementary_native_function, forbidden_complementary_native)
    if boundary == "adapter":
        monkeypatch.setattr(adapter, operation, failure)
    with pytest.raises(exception_type) as raised:
        if operation == "replay":
            bridge.replay(case["member"], submitted.context, **replay_keywords(case))
        else:
            call_mock_verification(modules, case, submitted)
    assert raised.value is expected_exception
    assert len(calls) == 1
    assert len(native_calls) == (1 if boundary == "adapter" else 0)
    if boundary == "native":
        if operation == "replay":
            assert calls[0][0][0] is case["member"]
            assert calls[0][0][1] is submitted.context.native_context
        else:
            assert calls[0][0][0] is submitted.native_evidence
            assert calls[0][0][1] is case["member"]
    elif operation == "verify":
        assert calls[0][0][0] is submitted.adapter_assessment


@pytest.mark.parametrize("ts_out", [False, True], ids=["absent", "present"])
@pytest.mark.parametrize("variant", rich_oracle.RICH_VARIANTS)
@pytest.mark.parametrize("operation", ["replay", "verify"])
def test_actual_native_rich_complete_independent_body(variant, ts_out, operation):
    """Separately registered finite rich cohort; no production-derived expected state."""
    modules = bridge_types()
    bridge = modules[0]
    case = rich_oracle.rich_case(oracle, ts_out, variant)
    expected = oracle.bridge_object(*modules, case["bridge"])
    fields = oracle.record_fields(*modules)
    assert canonical(oracle.observed_body(expected, fields)) == canonical(case["bridge"])
    label = f"rich-{variant}-{operation}-ts_out-{ts_out}"
    print_complete_declaration(case, "rich-" + variant + "-" + operation, ts_out)
    if operation == "verify":
        print_submitted_object_ids(expected)
    with (
        observe_original_native_seam(label) as captured,
        observe_original_public_adapter_calls(label) as adapter_calls,
    ):
        if operation == "replay":
            actual = bridge.replay(case["member"], expected.context, **replay_keywords(case))
        else:
            actual = bridge.verify(
                expected,
                case["member"],
                expected.context,
                **replay_keywords(case),
                expected_evidence_sha256=case["bridge"]["evidence_sha256"],
            )
    if operation == "replay":
        actual_body = oracle.observed_body(actual, fields)
        print("COMPLETE_BRIDGE_ACTUAL_BODY=" + canonical(actual_body).decode())
        oracle.assert_exact_tree(actual, expected, fields)
        assert canonical(actual_body) == canonical(case["bridge"])
        assert_public_adapter_calls(adapter_calls, case, modules)
    else:
        assert actual is None
        actual_body = oracle.observed_body(expected, fields)
        assert canonical(actual_body) == canonical(case["bridge"])
        print("COMPLETE_BRIDGE_VERIFIED_BODY=" + canonical(actual_body).decode())
        assert_public_adapter_calls(
            adapter_calls, case, modules, submitted=expected.adapter_assessment
        )
    assert_one_original_native_call(captured, case)


ADAPTER_REFUSAL_VARIANTS = oracle.ADAPTER_REFUSAL_VARIANTS
adapter_refusal_case = oracle.adapter_refusal_case


@pytest.mark.parametrize("variant", ADAPTER_REFUSAL_VARIANTS)
@pytest.mark.parametrize("ts_out", [False, True], ids=["absent", "present"])
def test_actual_native_complete_adapter_refusal_is_atomic(variant, ts_out):
    modules = bridge_types()
    bridge, native = modules[:2]
    case = adapter_refusal_case(variant, ts_out)
    original_context = bridge.BridgeContext(
        FIXTURE_ID,
        SOURCE_SESSION,
        oracle.native_object(native, expected_context(ts_out)["native_context"], "Context"),
    )
    label = f"adapter-refusal-{variant}-ts_out-{ts_out}"
    print(
        "COMPLETE_INDEPENDENT_BRIDGE_REFUSAL_DECLARATION="
        + canonical(
            {
                "schema": "bridge_native_refusal_declaration_v1",
                "operation": "adapter-refusal-" + variant,
                "ts_out": ts_out,
                "original_member_hex": case["member"].hex(),
                "original_decompressed_hex": case["raw"].hex(),
                "native_body": case["native"],
                "request_template": case["request_template"],
                "expected_native_invocations": 1,
                "expected_bridge_exception": "ValueError",
                "partial_output_allowed": False,
            }
        ).decode()
    )
    with (
        observe_original_native_seam(label) as captured,
        observe_original_public_adapter_calls(label) as adapter_calls,
    ):
        with pytest.raises(ValueError):
            bridge.replay(case["member"], original_context, **replay_keywords(case))
    assert_one_original_native_call(captured, case)
    assert len(adapter_calls["fixture_sha256"]) == 1
    assert adapter_calls["replay"] == [] and adapter_calls["verify"] == []
    assert adapter_calls["fixture_sha256"][0]["raised_type"] == "ValueError"
    assert adapter_calls["fixture_sha256"][0]["result"] is None


@pytest.mark.parametrize("maximum", [65536, 262144, 1048576, 4194304])
def test_new_canonical_guard_exact_equality_and_first_excess_only(maximum):
    """Arbitrary new helper guard, explicitly not reachable legal member capacity."""
    bridge = bridge_module()
    exact_body = "a" * (maximum - 2)
    assert len(canonical(exact_body)) == maximum
    assert bridge._canonical(exact_body, maximum) == canonical(exact_body)
    with pytest.raises(ValueError):
        bridge._canonical(exact_body + "a", maximum)


@pytest.mark.parametrize("length", [1, 262144])
def test_arbitrary_member_byte_equality_boundary_reaches_provider_once(length, monkeypatch):
    """Admission-only byte guard; these bytes are not claimed native DBN fixtures."""
    bridge = bridge_module()
    native = importlib.import_module(NATIVE_MODULE)
    forbid_native_dispatch(monkeypatch)
    member = b"x" * length
    sentinel = AssertionError("admitted bytes reached provider once")
    calls = []

    def provider(*args, **kwargs):
        calls.append((args, kwargs))
        raise sentinel

    monkeypatch.setattr(native, "decode_member", provider)
    with pytest.raises(AssertionError) as raised:
        bridge.replay(
            member,
            context(bridge),
            expected_protocol_sha256=PROTOCOL_SHA,
            expected_context_sha256=digest(expected_context()),
            expected_member_sha256=oracle.raw_digest(member),
            expected_metadata_sha256="0" * 64,
        )
    assert raised.value is sentinel and len(calls) == 1 and calls[0][0][0] is member


@pytest.mark.parametrize("length", [0, 262145])
def test_member_byte_empty_or_first_excess_refuses_before_native(length, monkeypatch):
    bridge = bridge_module()
    member = b"x" * length
    forbid_native_dispatch(monkeypatch)
    with pytest.raises(ValueError):
        bridge.replay(
            member,
            context(bridge),
            expected_protocol_sha256=PROTOCOL_SHA,
            expected_context_sha256=digest(expected_context()),
            expected_member_sha256=oracle.raw_digest(member),
            expected_metadata_sha256="0" * 64,
        )


@pytest.mark.parametrize("variant", oracle.PROVIDER_REFUSAL_VARIANTS)
@pytest.mark.parametrize("ts_out", [False, True], ids=["absent", "present"])
def test_actual_native_provider_failure_retains_complete_refusal(variant, ts_out):
    bridge = bridge_module()
    case = oracle.provider_refusal_case(variant, ts_out)
    request = case["request_template"]
    label = f"provider-refusal-{variant}-ts_out-{ts_out}"
    print(
        "COMPLETE_INDEPENDENT_BRIDGE_PROVIDER_REFUSAL_DECLARATION="
        + canonical(
            {
                "schema": "bridge_provider_refusal_declaration_v1",
                "operation": variant,
                "ts_out": ts_out,
                "original_member_hex": case["member"].hex(),
                "request_template": request,
                "response_template": case["response_template"],
                "expected_native_invocations": 1,
                "expected_exit_code": 2,
                "expected_outcome": "input_refused",
                "expected_bridge_exception": "ValueError",
                "partial_output_allowed": False,
            }
        ).decode()
    )
    with (
        observe_original_native_seam(label) as captured,
        observe_original_public_adapter_calls(label) as adapter_calls,
    ):
        with pytest.raises(ValueError):
            bridge.replay(
                case["member"],
                context(bridge, expected_ts_out=ts_out),
                expected_protocol_sha256=PROTOCOL_SHA,
                expected_context_sha256=digest(expected_context(ts_out)),
                expected_member_sha256=request["expected_member_sha256"],
                expected_metadata_sha256=request["expected_metadata_sha256"],
            )
    assert len(captured) == 1 and captured[0]["raised_type"] == "ValueError"
    entry = captured[0]
    assert entry["observation_error_type"] is None
    oracle.exact_json(entry["template_before"], request)
    oracle.exact_json(entry["template_after"], request)
    assert entry["execution_sha256"] == oracle.EXECUTION_SHA
    oracle.assert_native_receipt(entry["response"], entry["receipt"], request, None)
    assert all(calls == [] for calls in adapter_calls.values())


OUTER_PREFLIGHT_CHANGES = (
    ("status", "accepted"),
    ("status", True),
    ("protocol_sha256", "0" * 64),
    ("context_sha256", "0" * 64),
    ("evidence_sha256", "0" * 64),
    ("native_evidence", None),
    ("adapter_assessment", None),
)


@pytest.mark.parametrize(
    "field,bad",
    OUTER_PREFLIGHT_CHANGES,
    ids=[field + "-" + str(index) for index, (field, _) in enumerate(OUTER_PREFLIGHT_CHANGES)],
)
def test_outer_metadata_refuses_before_provider_or_deferred_body(field, bad, monkeypatch):
    modules = bridge_types()
    case = oracle.minimal_case()
    submitted = oracle.bridge_object(*modules, case["bridge"])
    submitted = dataclasses.replace(submitted, **{field: bad})
    forbid_native_dispatch(monkeypatch)

    def body_getter(_value):
        raise AssertionError("outer metadata reached a deferred native body")

    monkeypatch.setattr(modules[1].MemberDecodeEvidence, "occurrences", property(body_getter))
    with pytest.raises(ValueError):
        modules[0].verify(
            submitted,
            case["member"],
            context(modules[0]),
            **replay_keywords(case),
            expected_evidence_sha256=case["bridge"]["evidence_sha256"],
        )


@pytest.mark.parametrize("family,maximum", [("native_prefixes", 128), ("publication_links", 32)])
@pytest.mark.parametrize("kind", ["list-alias", "empty", "first-excess", "missing", "reordered"])
def test_outer_link_envelope_refuses_before_provider(family, maximum, kind, monkeypatch):
    modules = bridge_types()
    case = oracle.minimal_case()
    submitted = oracle.bridge_object(*modules, case["bridge"])
    values = getattr(submitted, family)
    if kind == "list-alias":
        changed = list(values)
    elif kind == "empty":
        changed = ()
    elif kind == "first-excess":
        changed = (values[0],) * (maximum + 1)
    elif kind == "missing":
        changed = values[:-1]
    else:
        changed = (
            tuple(reversed(values))
            if len(values) > 1
            else (dataclasses.replace(values[0], publication_ordinal=2),)
        )
    submitted = dataclasses.replace(submitted, **{family: changed})
    # A missing final native link can still have a syntactically valid prefix;
    # its publication cursor then exceeds the retained complete prefix count.
    forbid_native_dispatch(monkeypatch)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)


@pytest.mark.parametrize("operation", ["replay", "verify"])
@pytest.mark.parametrize(
    "pin", ["expected_protocol_sha256", "expected_context_sha256", "expected_member_sha256"]
)
def test_valid_syntax_wrong_early_pin_refuses_before_provider(operation, pin, monkeypatch):
    modules = bridge_types()
    case = oracle.minimal_case()
    submitted = oracle.bridge_object(*modules, case["bridge"])
    keywords = replay_keywords(case) | {pin: "0" * 64}
    forbid_native_dispatch(monkeypatch)
    with pytest.raises(ValueError):
        if operation == "replay":
            modules[0].replay(case["member"], submitted.context, **keywords)
        else:
            modules[0].verify(
                submitted,
                case["member"],
                submitted.context,
                **keywords,
                expected_evidence_sha256=submitted.evidence_sha256,
            )


@pytest.mark.parametrize("kind", ["bytearray", "memoryview", "bytes-subclass", "none"])
def test_complete_original_member_requires_exact_immutable_bytes(kind, monkeypatch):
    modules = bridge_types()
    case = oracle.minimal_case()
    submitted = oracle.bridge_object(*modules, case["bridge"])

    class BytesAlias(bytes):
        pass

    bad = {
        "bytearray": bytearray(case["member"]),
        "memoryview": memoryview(case["member"]),
        "bytes-subclass": BytesAlias(case["member"]),
        "none": None,
    }[kind]
    forbid_native_dispatch(monkeypatch)
    with pytest.raises(ValueError):
        modules[0].verify(
            submitted,
            bad,
            submitted.context,
            **replay_keywords(case),
            expected_evidence_sha256=submitted.evidence_sha256,
        )


def forbid_native_host_and_decode(monkeypatch, modules):
    """Submitted native-envelope validation remains the unchanged public verifier."""
    host = importlib.import_module("ai_trader.research._native_member_host")

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid submitted native evidence reached an execution seam")

    monkeypatch.setattr(host, "run_decode", forbidden)
    monkeypatch.setattr(modules[1], "decode_member", forbidden)


@pytest.mark.parametrize("authority", expected_protocol()["authority_names"])
@pytest.mark.parametrize("bad", [True, 0], ids=["enabled", "int-false-alias"])
def test_unchanged_public_native_verify_rejects_every_nested_authority(authority, bad, monkeypatch):
    modules = bridge_types()
    case = oracle.minimal_case()
    submitted = oracle.bridge_object(*modules, case["bridge"])
    changed = tuple(
        (name, bad if name == authority else value)
        for name, value in submitted.native_evidence.authorities
    )
    submitted = replaced_path(submitted, ("native_evidence", "authorities"), changed)
    forbid_native_host_and_decode(monkeypatch, modules)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)


NATIVE_COMPLETE_TAMPERS = (
    (("status",), "accepted"),
    *[
        ((name + "_sha256",), "0" * 64)
        for name in (
            "protocol",
            "profile",
            "runtime_manifest",
            "context",
            "member",
            "metadata",
            "evidence",
        )
    ],
    (("terminal", "dbn_remaining_buffer_bytes"), 1),
    (("terminal", "decoded_positions"), 4),
    (("terminal", "metadata_count"), 2),
    (("terminal", "frame_count"), 0),
    (("terminal", "zstd_status"), "empty_buffer_only"),
    (("zstd_framing", "frames", 0, "compressed_start"), 1),
    (("zstd_framing", "frames", 0, "decompressed_end"), 1),
    (("zstd_framing", "frames", 0, "compressed_span_sha256"), "0" * 64),
    (("dbn_framing", "spans", 1, "wire_sha256"), "0" * 64),
    (("dbn_framing", "spans", 1, "wire_fields_sha256"), "0" * 64),
    (("dbn_framing", "spans", 1, "decompressed_start"), 0),
    (("dbn_framing", "spans", 1, "kind"), "Metadata"),
    (("dbn_framing", "spans", 1, "wire_fields", "sequence"), 99),
    (("occurrences", 1, "decoded_position"), 99),
    (("occurrences", 1, "wire_span_ordinal"), 3),
    (("occurrences", 1, "projection_sha256"), "0" * 64),
    (("occurrences", 1, "projection", "rtype", "code"), 161),
    (("occurrences", 1, "projection", "action", "class_name"), "OtherAction"),
    (("occurrences", 1, "projection", "record_size_observed"), 64),
    (("occurrences", 1, "projection", "ts_out_observed"), None),
    (("occurrences", 0, "projection", "dataset"), "OTHER.MDP3"),
    (("occurrences", 0, "projection", "schema", "text"), "mbp-1"),
)


@pytest.mark.parametrize(
    "path,bad",
    NATIVE_COMPLETE_TAMPERS,
    ids=[".".join(map(str, path)) for path, _ in NATIVE_COMPLETE_TAMPERS],
)
def test_unchanged_public_native_verify_rejects_complete_body_tamper(path, bad, monkeypatch):
    """Complete-integrity control; no claim that stale hashes isolate a domain guard."""
    modules = bridge_types()
    case = oracle.minimal_case()
    submitted = oracle.bridge_object(*modules, case["bridge"])
    submitted = replaced_path(submitted, ("native_evidence", *path), bad)
    forbid_native_host_and_decode(monkeypatch, modules)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)


@pytest.mark.parametrize(
    "path",
    [
        ("occurrences",),
        ("dbn_framing", "spans"),
        ("zstd_framing", "frames"),
        ("runtime_manifest", "packages"),
        ("runtime_manifest", "artifacts"),
    ],
    ids=lambda path: ".".join(path),
)
@pytest.mark.parametrize("kind", ["missing", "extra", "reordered"])
def test_unchanged_public_native_verify_rejects_full_sequence_tamper(path, kind, monkeypatch):
    modules = bridge_types()
    case = oracle.minimal_case()
    submitted = oracle.bridge_object(*modules, case["bridge"])
    original = object_at_path(submitted.native_evidence, path)
    if kind == "missing":
        changed = original[:-1]
    elif kind == "extra" or len(original) == 1:
        changed = original + original[-1:]
    else:
        changed = original[1:] + original[:1]
    submitted = replaced_path(submitted, ("native_evidence", *path), changed)
    forbid_native_host_and_decode(monkeypatch, modules)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)


MBO_REPRESENTATION_MISMATCHES = (
    *[
        (field, "scalar")
        for field in (
            "publisher_id",
            "instrument_id",
            "ts_event",
            "order_id",
            "price",
            "size",
            "flags",
            "channel_id",
            "ts_recv",
            "ts_in_delta",
            "sequence",
            "record_size_observed",
            "ts_index_observed",
            "ts_out_observed",
        )
    ],
    *[
        (field, part)
        for field in ("rtype", "action", "side")
        for part in ("kind", "class_name", "name", "code", "text")
    ],
    ("action", "known-as-unknown"),
    ("side", "known-as-unknown"),
    ("ts_out_observed", "none"),
)


@pytest.mark.parametrize("occurrence_index", [1, 4], ids=["target", "foreign"])
@pytest.mark.parametrize(
    "field,part",
    MBO_REPRESENTATION_MISMATCHES,
    ids=[field + "-" + part for field, part in MBO_REPRESENTATION_MISMATCHES],
)
def test_mocked_wire_projection_correspondence_precedes_selected_payload(
    occurrence_index,
    field,
    part,
    monkeypatch,
):
    modules = bridge_types()
    case = oracle.variant_case("consumed-foreign-a", True)
    body = copy.deepcopy(case["native"])
    observed = body["occurrences"][occurrence_index]["projection"]
    if part == "scalar":
        observed[field] += 1
    elif part == "none":
        observed[field] = None
    elif part == "known-as-unknown":
        observed[field] = {"kind": "str", "value": observed[field]["text"]}
    elif part == "code":
        observed[field][part] += 1
    else:
        observed[field][part] += "-wrong"
    oracle.rehash_mock_native_declarations(body)
    returned = oracle.native_object(modules[1], body)
    forbid_native_dispatch(monkeypatch)
    native_calls, payload_calls = [], []
    original_payload = modules[3].payload_sha256

    def mocked_provider(*args, **kwargs):
        native_calls.append((args, kwargs))
        return returned

    def selected_boundary(*args, **kwargs):
        payload_calls.append((args, kwargs))
        if len(payload_calls) == occurrence_index:
            raise AssertionError("representation mismatch reached selected public payload hashing")
        return original_payload(*args, **kwargs)

    monkeypatch.setattr(modules[1], "decode_member", mocked_provider)
    monkeypatch.setattr(modules[3], "payload_sha256", selected_boundary)
    with pytest.raises(ValueError):
        modules[0].replay(
            case["member"], context(modules[0], expected_ts_out=True), **replay_keywords(case)
        )
    assert len(native_calls) == 1


@pytest.mark.parametrize(
    "bad", [None, 0, (1 << 63) - 1, False], ids=["none", "zero", "signed-max", "bool"]
)
def test_mocked_absent_ts_out_requires_native_u64_sentinel(bad, monkeypatch):
    modules = bridge_types()
    case = oracle.minimal_case(False)
    body = copy.deepcopy(case["native"])
    body["occurrences"][1]["projection"]["ts_out_observed"] = bad
    oracle.rehash_mock_native_declarations(body)
    returned = oracle.native_object(modules[1], body)
    forbid_native_dispatch(monkeypatch)
    monkeypatch.setattr(modules[1], "decode_member", lambda *args, **kwargs: returned)

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid absent ts_out reached payload hashing")

    monkeypatch.setattr(modules[3], "payload_sha256", forbidden)
    with pytest.raises(ValueError):
        modules[0].replay(case["member"], context(modules[0]), **replay_keywords(case))


INTEGER_FLOAT_ALIAS_INDICES = (
    3,
    4,
    5,
    6,
    7,
    11,
    12,
    13,
    14,
    15,
    16,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    30,
    31,
    32,
    33,
    34,
    35,
    36,
)


@pytest.mark.parametrize("feature_index", INTEGER_FLOAT_ALIAS_INDICES)
def test_mocked_complete_feature_float_tokens_do_not_accept_integer_alias(
    feature_index, monkeypatch
):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    path = ("adapter_assessment", "publications", 0, "features", feature_index, 1)
    original = object_at_path(submitted, path)
    assert type(original) is float and original.is_integer()
    submitted = replaced_path(submitted, path, int(original))
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


def test_mocked_exact_int_zero_travel_cannot_be_rewritten_to_float_zero(monkeypatch):
    modules, case, submitted, native_calls = prepared_mock_verification(monkeypatch)
    path = ("adapter_assessment", "publications", 0, "features", 17, 1)
    assert type(object_at_path(submitted, path)) is int
    submitted = replaced_path(submitted, path, 0.0)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
    assert len(native_calls) == 1


@pytest.mark.parametrize(
    "kind",
    [
        "return",
        "bare-error",
        "receipt-error",
        "observation-error",
        "error-observation-error",
        "swallowed-retry",
    ],
)
def test_mock_only_observer_preserves_attempts_identity_errors_and_restoration(
    kind, monkeypatch, capsys
):
    """Observer self-control only: no provider, process, or native execution."""
    host = importlib.import_module("ai_trader.research._native_member_host")
    template, execution = {"fixed": [1, False, None]}, "b" * 64
    seen = []
    original_error = RuntimeError("original host error, not observation error")

    class CopyBomb:
        def __deepcopy__(self, _memo):
            raise AssertionError("observation-only copy poison")

    response = {"complete": True}
    receipt = {"response": {"parsed_body": response}}
    if kind in ("observation-error", "error-observation-error"):
        receipt["observation_only"] = CopyBomb()
    if kind in ("receipt-error", "error-observation-error"):
        original_error.receipt = receipt
    result = (response, receipt)

    def original(received, pin):
        seen.append((received, pin))
        if kind in ("bare-error", "receipt-error", "error-observation-error"):
            raise original_error
        if kind == "swallowed-retry" and len(seen) == 1:
            raise original_error
        return result

    monkeypatch.setattr(host, "run_decode", original)
    with observe_original_native_seam("mock-only-observer-" + kind) as captured:
        if kind in ("bare-error", "receipt-error", "error-observation-error", "swallowed-retry"):
            with pytest.raises(RuntimeError) as caught:
                host.run_decode(template, execution)
            assert caught.value is original_error
            if kind == "swallowed-retry":
                assert host.run_decode(template, execution) is result
        else:
            assert host.run_decode(template, execution) is result
    assert host.run_decode is original
    assert all(args[0] is template and args[1] is execution for args in seen)
    assert len(captured) == len(seen) == (2 if kind == "swallowed-retry" else 1)
    if kind == "swallowed-retry":
        assert captured[0]["receipt"] is None and captured[1]["receipt"] is not None
        assert sum(entry["receipt"] is not None for entry in captured) == 1
    if kind in ("observation-error", "error-observation-error"):
        assert captured[0]["observation_error_type"] == "AssertionError"
    # Do not emit mock observer packets into the actual-native terminal cohort.
    output = capsys.readouterr().out
    assert "COMPLETE_BRIDGE_PUBLIC_CALL_OBSERVATION=" in output
    assert "COMPLETE_BRIDGE_NATIVE_OBSERVATION=" in output


@pytest.mark.parametrize(
    "boundary", ["cursor-fixture", "cursor-assess", "cursor-verify", "binding-bundle"]
)
@pytest.mark.parametrize("operation", ["replay", "verify"])
def test_mocked_inherited_public_cap_or_validation_refusal_is_atomic(
    boundary, operation, monkeypatch
):
    """Propagation test, not a claim that an arbitrary oversized fixture is valid."""
    modules = bridge_types()
    case = oracle.minimal_case()
    submitted = oracle.bridge_object(*modules, case["bridge"])
    native_calls, boundary_calls = [], []
    expected_error = ValueError("unchanged public dependency refused complete input")
    forbid_native_dispatch(monkeypatch)

    def native_call(*args, **kwargs):
        native_calls.append((args, kwargs))
        return submitted.native_evidence if operation == "replay" else None

    def refusing(*args, **kwargs):
        boundary_calls.append((args, kwargs))
        raise expected_error

    monkeypatch.setattr(
        modules[1], "decode_member" if operation == "replay" else "verify", native_call
    )
    owner, name = {
        "cursor-fixture": (modules[4], "fixture_sha256"),
        "cursor-assess": (modules[4], "assess"),
        "cursor-verify": (modules[4], "verify"),
        "binding-bundle": (modules[3], "bundle_sha256"),
    }[boundary]
    monkeypatch.setattr(owner, name, refusing)
    forbid_late_adapter_verify(monkeypatch, modules)
    with pytest.raises(ValueError) as caught:
        if operation == "replay":
            modules[0].replay(case["member"], submitted.context, **replay_keywords(case))
        else:
            call_mock_verification(modules, case, submitted)
    # ValueError is the documented malformed-input family; the public guard
    # normalizes it while retaining the exact dependency failure as its cause.
    assert caught.value.__cause__ is expected_error
    assert len(native_calls) == len(boundary_calls) == 1


@pytest.mark.parametrize("operation", ["replay", "verify"])
@pytest.mark.parametrize("refused_stage", ["body", "complete-artifact"])
def test_mocked_both_complete_outer_caps_run_before_positive_return(
    operation, refused_stage, monkeypatch
):
    """Exact new call-path guard; not a universal maximum-size fixture oracle."""
    modules = bridge_types()
    case = oracle.minimal_case()
    submitted = oracle.bridge_object(*modules, case["bridge"])
    original_canonical = modules[0]._canonical
    native_calls, guards = [], []
    sentinel = AssertionError("outer complete size boundary was reached before return")
    forbid_native_dispatch(monkeypatch)

    def native_call(*args, **kwargs):
        native_calls.append((args, kwargs))
        return submitted.native_evidence if operation == "replay" else None

    def complete_guard(body, maximum):
        complete_keys = set(case["bridge"])
        body_keys = complete_keys - {"evidence_sha256"}
        if type(body) is dict and set(body) in (body_keys, complete_keys):
            stage = "complete-artifact" if "evidence_sha256" in body else "body"
            assert maximum == 4194304
            expected = (
                case["bridge"]
                if stage == "complete-artifact"
                else {
                    key: value for key, value in case["bridge"].items() if key != "evidence_sha256"
                }
            )
            oracle.exact_json(body, expected)
            guards.append(stage)
            if stage == refused_stage:
                raise sentinel
        return original_canonical(body, maximum)

    monkeypatch.setattr(
        modules[1], "decode_member" if operation == "replay" else "verify", native_call
    )
    monkeypatch.setattr(modules[0], "_canonical", complete_guard)
    with pytest.raises(AssertionError) as caught:
        if operation == "replay":
            modules[0].replay(case["member"], submitted.context, **replay_keywords(case))
        else:
            call_mock_verification(modules, case, submitted)
    assert caught.value is sentinel and len(native_calls) == 1
    if refused_stage == "complete-artifact":
        assert guards[-1] == "complete-artifact" and "body" in guards[:-1]
    else:
        assert guards == ["body"]


@pytest.mark.parametrize("field", ["schema", "stype_in", "stype_out"])
@pytest.mark.parametrize("part", ["kind", "class_name", "name", "code", "text"])
def test_mocked_complete_metadata_enum_precedes_every_mbo_getter(field, part, monkeypatch):
    modules = bridge_types()
    case = oracle.minimal_case()
    body = copy.deepcopy(case["native"])
    enum = body["occurrences"][0]["projection"][field]
    enum[part] = enum[part] + 1 if part == "code" else enum[part] + "-wrong"
    oracle.rehash_mock_native_declarations(body)
    returned = oracle.native_object(modules[1], body)
    forbid_native_dispatch(monkeypatch)
    calls = []

    def provider(*args, **kwargs):
        calls.append((args, kwargs))
        return returned

    def forbidden_getter(_self):
        raise AssertionError("incomplete header enum reached original MBO getter")

    monkeypatch.setattr(modules[1], "decode_member", provider)
    monkeypatch.setattr(modules[1].MboObservation, "publisher_id", property(forbidden_getter))
    with pytest.raises(ValueError):
        modules[0].replay(case["member"], context(modules[0]), **replay_keywords(case))
    assert len(calls) == 1


@pytest.mark.parametrize(
    "field,bad",
    [
        ("dataset", "OTHER.MDP3"),
        ("version", True),
        ("schema", 1),
        ("start", oracle.DAY + 1),
        ("end", oracle.DAY + 1),
        ("limit", 1),
        ("stype_in", 0),
        ("stype_out", 4),
        ("ts_out", True),
        ("symbols_count", 2),
        ("partial_count", 1),
        ("not_found_count", 1),
        ("mappings_count", 2),
    ],
    ids=lambda value: str(value),
)
def test_mocked_original_header_wire_scalars_checked_before_mbo(field, bad, monkeypatch):
    modules = bridge_types()
    case = oracle.minimal_case()
    body = copy.deepcopy(case["native"])
    body["dbn_framing"]["spans"][0]["wire_fields"][field] = bad
    oracle.rehash_mock_native_declarations(body)
    returned = oracle.native_object(modules[1], body)
    forbid_native_dispatch(monkeypatch)

    def forbidden_getter(_self):
        raise AssertionError("header wire mismatch reached original MBO getter")

    monkeypatch.setattr(modules[1], "decode_member", lambda *args, **kwargs: returned)
    monkeypatch.setattr(modules[1].MboObservation, "publisher_id", property(forbidden_getter))
    with pytest.raises(ValueError):
        modules[0].replay(case["member"], context(modules[0]), **replay_keywords(case))


@pytest.mark.parametrize("bad_date", [20250230, 21010101, 19991231])
def test_mocked_mapping_calendar_and_both_year_limits_precede_mbo(bad_date, monkeypatch):
    modules = bridge_types()
    case = oracle.minimal_case()
    body = copy.deepcopy(case["native"])
    group = body["dbn_framing"]["spans"][0]["wire_fields"]["mappings"][0]
    group["intervals"][0]["start_date"] = bad_date
    oracle.rehash_mock_native_declarations(body)
    returned = oracle.native_object(modules[1], body)
    forbid_native_dispatch(monkeypatch)

    def forbidden_getter(_self):
        raise AssertionError("unrepresentable mapping calendar reached MBO getter")

    monkeypatch.setattr(modules[1], "decode_member", lambda *args, **kwargs: returned)
    monkeypatch.setattr(modules[1].MboObservation, "publisher_id", property(forbidden_getter))
    with pytest.raises(ValueError):
        modules[0].replay(case["member"], context(modules[0]), **replay_keywords(case))


@pytest.mark.parametrize("authority", expected_protocol()["authority_names"])
def test_outer_every_false_authority_refuses_integer_zero_alias(authority, monkeypatch):
    modules = bridge_types()
    case = oracle.minimal_case()
    submitted = oracle.bridge_object(*modules, case["bridge"])
    authorities = tuple(
        (name, 0 if name == authority else value) for name, value in submitted.authorities
    )
    submitted = dataclasses.replace(submitted, authorities=authorities)
    forbid_native_dispatch(monkeypatch)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)


@pytest.mark.parametrize("kind", ["list-alias", "missing", "extra", "reordered", "renamed"])
def test_outer_authority_complete_order_and_identity_are_not_partial(kind, monkeypatch):
    modules = bridge_types()
    case = oracle.minimal_case()
    submitted = oracle.bridge_object(*modules, case["bridge"])
    original = submitted.authorities
    if kind == "list-alias":
        changed = list(original)
    elif kind == "missing":
        changed = original[:-1]
    elif kind == "extra":
        changed = original + (original[-1],)
    elif kind == "reordered":
        changed = original[1:] + original[:1]
    else:
        changed = ((original[0][0] + "-renamed", False), *original[1:])
    submitted = dataclasses.replace(submitted, authorities=changed)
    forbid_native_dispatch(monkeypatch)
    with pytest.raises(ValueError):
        call_mock_verification(modules, case, submitted)
