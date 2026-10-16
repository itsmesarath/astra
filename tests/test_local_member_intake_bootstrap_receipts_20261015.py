"""Independent S3 fixtures and refusals; no native, file-intake, or subprocess work."""

import copy
import importlib.util
import json
from pathlib import Path

import local_member_intake_bootstrap_receipt_oracles_20261015 as oracle
import pytest

_VALIDATION = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "local_member_intake_bootstrap_validation_20261015_1.py"
)

_KINDS = ("rejected", "preflight")
_CASES = ("packet_first_excess", "packet_wrong_pin", "unknown_control")
_OWN_KEY = {"rejected": "rejection_sha256", "preflight": "receipt_sha256"}
_RAW_CAP = {"rejected": 65536, "preflight": 67108864}
_REJECTED_KEYS = (
    "version",
    "case_id",
    "registration_sha256",
    "oracle_sha256",
    "expected_raw_hex",
    "expected_packet_sha256",
    "submitted_raw_hex",
    "submitted_raw_byte_length",
    "submitted_raw_sha256",
    "first_reason",
    "admitted_packet",
    "native_setup_attempted",
    "rejection_sha256",
)
_PREFLIGHT_KEYS = (
    "version",
    "case_id",
    "packet",
    "packet_sha256",
    "registration_sha256",
    "oracle_sha256",
    "declared_policy",
    "runtime_pins",
    "parent_identity",
    "creation",
    "job_observations",
    "api_trace",
    "lifecycle",
    "stdout",
    "stderr",
    "result",
    "terminal",
    "authority_flags",
    "receipt_sha256",
)
_CREATION_KEYS = (
    "attempted",
    "create_bool_i32",
    "win32_error_u32",
    "creation_flags_u32",
    "command_utf16le_hex",
    "environment_utf16le_hex",
    "inherited_handles_u64",
    "job_attribute_u64",
    "handle_attribute_u64",
    "process_handle_u64",
    "thread_handle_u64",
    "child_pid",
    "child_tid",
    "child_creation_filetime_u64",
    "observed_image_utf16le_hex",
    "observed_parent_pid",
    "parent_observation_method",
    "cim_observations",
    "resume_count_u32",
    "initialization",
    "binding_initialization",
    "module_observations",
    "identity_transport",
)
_TRANSPORT_KEYS = (
    "request",
    "ack",
    "ready_hex",
    "ready_read_api_ordinals",
    "go_hex",
    "go_write_api_ordinals",
    "child_stdin_parent_closes",
)
_TERMINAL_KEYS = (
    "outcome",
    "failure_stage",
    "failure_code",
    "termination_requested",
    "termination_return",
    "wait_result_u32",
    "exit_code_u32",
    "exit_filetime_u64",
    "kernel_time_100ns_u64",
    "user_time_100ns_u64",
    "final_job_empty",
    "parent_closes",
    "cleanup_complete",
    "acceptance",
)
_POLICY_KEYS = (
    "packet_bytes_max",
    "command_utf16_units_max",
    "environment_utf16_units_max",
    "active_processes",
    "process_memory_bytes",
    "user_cpu_100ns",
    "work_ms",
    "teardown_ms",
    "poll_ms",
    "result_bytes_max",
    "diagnostic_bytes_max",
    "semantic_diagnostic_bytes_max",
    "ready_prefix_bytes",
    "go_bytes",
    "receipt_bytes_max",
    "buffer_occurrences_raw_bytes_max",
    "other_hex_occurrences_raw_bytes_max",
    "other_canonical_bytes_max",
    "api_rows_max",
    "lifecycle_rows_max",
    "parent_handle_rows_max",
    "worker_handle_rows_max",
    "hard_end_utc",
)
_RUNTIME_KEYS = ("role", "path", "byte_length", "sha256")
_LIFECYCLE_KEYS = ("ordinal", "event", "monotonic_ns", "related_api_ordinals")
_CALLER_REASONS = frozenset(
    (
        "transport",
        "budget",
        "packet_context",
        "utf8",
        "duplicate_key",
        "trailing_json",
        "query_value",
        "authority_flags",
        "query_count",
        "timestamp",
        "identity_mismatch",
        "saved_error",
    )
)


def _exact(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert actual.keys() == expected.keys()
        for key, value in expected.items():
            _exact(actual[key], value)
    elif type(expected) is list:
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected, strict=True):
            _exact(left, right)
    else:
        assert actual == expected


def _fixture(kind, case_id="packet_wrong_pin"):
    if kind == "rejected":
        return oracle.rejected_fixture(case_id)
    return oracle.preflight_fixture(case_id)


def _bindings(kind, case_id="packet_wrong_pin"):
    values = oracle.packet_inputs(case_id)
    if kind == "preflight":
        values["runtime_pins"] = oracle.runtime_pins_literal()
    return values


def _call(module, kind, raw, bindings):
    if kind == "rejected":
        return module.verify_rejected_input(raw, **bindings)
    return module.verify_preflight_receipt(raw, **bindings)


def _encoded(kind, value, reseal=True):
    if reseal:
        value = oracle.with_own_hash(value, _OWN_KEY[kind])
    return oracle.canonical_bytes(value)


def _set(value, path, replacement):
    target = value
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = copy.deepcopy(replacement)


def _refuses(module, kind, raw, bindings, reason=None):
    with pytest.raises(module.ReceiptRefusal) as caught:
        _call(module, kind, raw, bindings)
    assert type(caught.value.reason) is str
    assert caught.value.reason in _CALLER_REASONS
    if reason is not None:
        assert caught.value.reason == reason


@pytest.fixture(scope="module")
def validation():
    assert _VALIDATION.is_file(), "Registered pure receipt validation module is not yet implemented"
    spec = importlib.util.spec_from_file_location("local_intake_s3_validation", _VALIDATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_s3_missing_interface():
    """ReceiptRefusal and both exact verifier interfaces require this new module."""
    assert _VALIDATION.is_file(), "Registered pure receipt validation module is not yet implemented"


def test_s3_exact_public_refusal_and_two_interfaces(validation):
    assert issubclass(validation.ReceiptRefusal, ValueError)
    assert callable(validation.verify_rejected_input)
    assert callable(validation.verify_preflight_receipt)
    refusal = validation.ReceiptRefusal("transport")
    assert refusal.reason == "transport"
    with pytest.raises(AttributeError):
        refusal.reason = "budget"


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("case_id", _CASES)
def test_s3_complete_independent_positive_fixture(validation, kind, case_id):
    expected = _fixture(kind, case_id)
    bindings = _bindings(kind, case_id)
    before = copy.deepcopy(bindings)
    actual = _call(validation, kind, _encoded(kind, expected), bindings)
    _exact(actual, expected)
    _exact(bindings, before)


@pytest.mark.parametrize("kind", _KINDS)
def test_s3_each_return_is_fresh_and_complete(validation, kind):
    raw = _encoded(kind, _fixture(kind))
    first = _call(validation, kind, raw, _bindings(kind))
    first["version"] = "caller_mutation"
    _exact(_call(validation, kind, raw, _bindings(kind)), _fixture(kind))


def test_s3_fixture_scope_and_three_exact_complete_recipe_identities():
    assert tuple(oracle.NEGATIVE_CASE_IDS) == _CASES
    for case_id in _CASES:
        rejected = oracle.rejected_fixture(case_id)
        preflight = oracle.preflight_fixture(case_id)
        bindings = oracle.packet_inputs(case_id)
        assert tuple(rejected) == _REJECTED_KEYS
        assert tuple(preflight) == _PREFLIGHT_KEYS
        assert tuple(preflight["creation"]) == _CREATION_KEYS
        assert tuple(preflight["creation"]["identity_transport"]) == _TRANSPORT_KEYS
        assert tuple(preflight["terminal"]) == _TERMINAL_KEYS
        assert tuple(preflight["declared_policy"]) == _POLICY_KEYS
        assert rejected["submitted_raw_hex"] == bindings["submitted_packet_raw"].hex()
        assert rejected["submitted_raw_sha256"] == oracle.raw_sha256(
            bindings["submitted_packet_raw"]
        )
        assert preflight["packet_sha256"] == rejected["submitted_raw_sha256"]
        if case_id == "packet_first_excess":
            assert bindings["expected_packet_raw"] is None
            assert rejected["expected_raw_hex"] is None
            assert len(bindings["submitted_packet_raw"]) == 8193
        else:
            assert type(bindings["expected_packet_raw"]) is bytes
            assert rejected["expected_raw_hex"] == bindings["expected_packet_raw"].hex()
        if case_id == "unknown_control":
            assert bindings["expected_packet_raw"] == bindings["submitted_packet_raw"]


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("bad", (None, False, 0, "{}", bytearray(b"{}"), memoryview(b"{}"), [], {}))
def test_s3_raw_exact_bytes_type_first(validation, kind, bad):
    bindings = _bindings(kind)
    bindings["registration_sha256"] = "bad"
    _refuses(validation, kind, bad, bindings, "transport")


@pytest.mark.parametrize("kind", _KINDS)
def test_s3_raw_bytes_subclass_is_not_exact_bytes(validation, kind):
    class NotExactBytes(bytes):
        pass

    _refuses(validation, kind, NotExactBytes(b"{}"), _bindings(kind), "transport")


@pytest.mark.parametrize("kind", _KINDS)
def test_s3_complete_first_excess_precedes_external_context(validation, kind):
    bindings = _bindings(kind)
    bindings["registration_sha256"] = "bad"
    _refuses(validation, kind, b"x" * (_RAW_CAP[kind] + 1), bindings, "budget")


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize(
    "name,bad",
    (
        ("submitted_packet_raw", None),
        ("submitted_packet_raw", bytearray(b"{}")),
        ("expected_packet_raw", "{}"),
        ("expected_packet_raw", None),
        ("expected_packet_sha256", "A" * 64),
        ("expected_packet_sha256", "a" * 63),
        ("expected_packet_sha256", False),
        ("case_id", "success"),
        ("case_id", 0),
        ("registration_sha256", "g" * 64),
        ("registration_sha256", None),
        ("oracle_sha256", "B" * 64),
        ("oracle_sha256", True),
    ),
)
def test_s3_external_binding_validation_precedes_decoding(validation, kind, name, bad):
    bindings = _bindings(kind)
    bindings[name] = bad
    _refuses(validation, kind, b"\xff", bindings, "packet_context")


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize(
    "raw,reason",
    (
        (b"\xff", "utf8"),
        (b"\xef\xbb\xbf{}", "utf8"),
        (b'{"x":1,"x":2}', "duplicate_key"),
        (b'{"x":1,"\\u0078":2}', "duplicate_key"),
        (b"{} {}", "trailing_json"),
        (b"[]true", "trailing_json"),
        (b"", "transport"),
        (b"{", "transport"),
        (b"{/*x*/}", "transport"),
        (b"0.0", "transport"),
        (b"1e9999", "transport"),
        (b"NaN", "transport"),
        (b"Infinity", "transport"),
    ),
)
def test_s3_strict_complete_decoder_reasons(validation, kind, raw, reason):
    _refuses(validation, kind, raw, _bindings(kind), reason)


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("form", ("prefix_space", "suffix_space", "newline", "unsorted"))
def test_s3_complete_canonical_byte_equality(validation, kind, form):
    record = _fixture(kind)
    raw = _encoded(kind, record)
    if form == "prefix_space":
        raw = b" " + raw
    elif form == "suffix_space":
        raw += b" "
    elif form == "newline":
        raw += b"\n"
    else:
        raw = json.dumps(record, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode(
            "ascii"
        )
        assert raw != _encoded(kind, record)
    _refuses(validation, kind, raw, _bindings(kind), "transport")


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("raw", (b"null", b"false", b"0", b'"x"', b"[]"))
def test_s3_outer_root_must_be_exact_record(validation, kind, raw):
    _refuses(validation, kind, raw, _bindings(kind), "query_value")


@pytest.mark.parametrize("key", _REJECTED_KEYS)
def test_s3_every_rejected_outer_key_is_required(validation, key):
    record = oracle.rejected_fixture("packet_wrong_pin")
    del record[key]
    _refuses(
        validation, "rejected", oracle.canonical_bytes(record), _bindings("rejected"), "query_value"
    )


@pytest.mark.parametrize("key", _PREFLIGHT_KEYS)
def test_s3_every_preflight_outer_key_is_required(validation, key):
    record = oracle.preflight_fixture("packet_wrong_pin")
    del record[key]
    _refuses(
        validation,
        "preflight",
        oracle.canonical_bytes(record),
        _bindings("preflight"),
        "query_value",
    )


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("change", ("extra", "version_value", "version_type"))
def test_s3_outer_schema_precedes_bad_context_and_flags(validation, kind, change):
    record = _fixture(kind)
    if change == "extra":
        record["extra"] = None
    else:
        record["version"] = 1 if change == "version_type" else "wrong_version"
    record["registration_sha256"] = "0" * 64
    if kind == "preflight":
        record["authority_flags"][0][1] = True
    _refuses(validation, kind, _encoded(kind, record), _bindings(kind), "query_value")


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("key", ("case_id", "registration_sha256", "oracle_sha256"))
def test_s3_external_metadata_mismatch_precedes_hash_and_body(validation, kind, key):
    record = _fixture(kind)
    record[key] = "unknown_control" if key == "case_id" else "0" * 64
    record[_OWN_KEY[kind]] = "0" * 64
    _refuses(validation, kind, _encoded(kind, record, False), _bindings(kind), "packet_context")


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("bad", (None, False, 0, [], {}, "", "A" * 64))
def test_s3_outer_metadata_types_and_domains_are_strict(validation, kind, bad):
    record = _fixture(kind)
    record["registration_sha256"] = bad
    _refuses(validation, kind, _encoded(kind, record), _bindings(kind), "query_value")


@pytest.mark.parametrize("index", tuple(range(28)))
@pytest.mark.parametrize("bad", (True, 0, 1, None, "false", []))
def test_s3_every_authority_value_is_literal_false_before_hash(validation, index, bad):
    record = oracle.preflight_fixture("packet_wrong_pin")
    record["authority_flags"][index][1] = bad
    _refuses(
        validation,
        "preflight",
        _encoded("preflight", record, False),
        _bindings("preflight"),
        "authority_flags",
    )


@pytest.mark.parametrize(
    "change", ("missing", "extra", "reverse", "name", "pair_short", "pair_extra", "null", "dict")
)
def test_s3_authority_complete_names_shape_and_order(validation, change):
    record = oracle.preflight_fixture("packet_wrong_pin")
    flags = record["authority_flags"]
    if change == "missing":
        flags.pop()
    elif change == "extra":
        flags.append(["extra", False])
    elif change == "reverse":
        flags.reverse()
    elif change == "name":
        flags[0][0] = "wrong"
    elif change == "pair_short":
        flags[0].pop()
    elif change == "pair_extra":
        flags[0].append(False)
    else:
        record["authority_flags"] = None if change == "null" else {}
    _refuses(
        validation,
        "preflight",
        _encoded("preflight", record, False),
        _bindings("preflight"),
        "authority_flags",
    )


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("change", ("digest", "stale_body"))
def test_s3_complete_own_hash_before_deferred_body(validation, kind, change):
    record = _fixture(kind)
    if change == "digest":
        record[_OWN_KEY[kind]] = "0" * 64
    elif kind == "rejected":
        record["native_setup_attempted"] = True
    else:
        record["creation"]["attempted"] = True
    _refuses(validation, kind, _encoded(kind, record, False), _bindings(kind), "transport")


@pytest.mark.parametrize("kind", _KINDS)
def test_s3_valid_path_reaches_uncaught_deferred_body_sentinel(validation, monkeypatch, kind):
    calls = []

    def sentinel(value, bindings):
        calls.append((value, bindings))
        raise AssertionError("S3 actual deferred body sentinel")

    name = "_validate_rejected_body" if kind == "rejected" else "_validate_preflight_body"
    monkeypatch.setattr(validation, name, sentinel)
    with pytest.raises(AssertionError, match="^S3 actual deferred body sentinel$"):
        _call(validation, kind, _encoded(kind, _fixture(kind)), _bindings(kind))
    assert len(calls) == 1


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("change", ("metadata", "ownhash"))
def test_s3_invalid_early_phase_never_reaches_deferred_sentinel(
    validation, monkeypatch, kind, change
):
    calls = []

    def sentinel(value, bindings):
        calls.append((value, bindings))
        raise AssertionError("S3 must not reach deferred body")

    name = "_validate_rejected_body" if kind == "rejected" else "_validate_preflight_body"
    monkeypatch.setattr(validation, name, sentinel)
    record = _fixture(kind)
    if change == "metadata":
        record["registration_sha256"] = "0" * 64
        reason = "packet_context"
    else:
        record[_OWN_KEY[kind]] = "0" * 64
        reason = "transport"
    _refuses(validation, kind, _encoded(kind, record, False), _bindings(kind), reason)
    assert calls == []


def test_s3_flags_precede_real_hash_and_body_sentinels(validation, monkeypatch):
    calls = []

    def hash_sentinel(value, key):
        calls.append("hash")
        raise AssertionError("S3 must not hash bad flags")

    def body_sentinel(value, bindings):
        calls.append("body")
        raise AssertionError("S3 must not traverse bad flags")

    monkeypatch.setattr(validation, "_verify_ownhash", hash_sentinel)
    monkeypatch.setattr(validation, "_validate_preflight_body", body_sentinel)
    record = oracle.preflight_fixture("packet_wrong_pin")
    record["authority_flags"][0][1] = True
    _refuses(
        validation,
        "preflight",
        oracle.canonical_bytes(record),
        _bindings("preflight"),
        "authority_flags",
    )
    assert calls == []


@pytest.mark.parametrize("kind", _KINDS)
def test_s3_valid_path_reaches_uncaught_ownhash_sentinel(validation, monkeypatch, kind):
    calls = []

    def sentinel(value, key):
        calls.append(key)
        raise AssertionError("S3 actual ownhash sentinel")

    monkeypatch.setattr(validation, "_verify_ownhash", sentinel)
    with pytest.raises(AssertionError, match="^S3 actual ownhash sentinel$"):
        _call(validation, kind, _encoded(kind, _fixture(kind)), _bindings(kind))
    assert calls == [_OWN_KEY[kind]]


@pytest.mark.parametrize("key", _CREATION_KEYS)
@pytest.mark.parametrize("change", ("missing", "wrong_type"))
def test_s3_every_creation_field_preserves_pure_absence(validation, key, change):
    record = oracle.preflight_fixture("packet_wrong_pin")
    if change == "missing":
        del record["creation"][key]
    else:
        original = record["creation"][key]
        record["creation"][key] = None if type(original) is list or type(original) is dict else []
    _refuses(validation, "preflight", _encoded("preflight", record), _bindings("preflight"))


@pytest.mark.parametrize("key", _TRANSPORT_KEYS)
@pytest.mark.parametrize("bad", ([], {}, False, 0, ""))
def test_s3_unentered_identity_transport_is_null_not_empty(validation, key, bad):
    record = oracle.preflight_fixture("packet_wrong_pin")
    record["creation"]["identity_transport"][key] = bad
    _refuses(validation, "preflight", _encoded("preflight", record), _bindings("preflight"))


@pytest.mark.parametrize("key", _TERMINAL_KEYS)
@pytest.mark.parametrize("change", ("missing", "wrong_type"))
def test_s3_every_terminal_field_is_exact(validation, key, change):
    record = oracle.preflight_fixture("packet_wrong_pin")
    if change == "missing":
        del record["terminal"][key]
    else:
        record["terminal"][key] = [] if type(record["terminal"][key]) is not list else None
    _refuses(validation, "preflight", _encoded("preflight", record), _bindings("preflight"))


@pytest.mark.parametrize("key", _POLICY_KEYS)
@pytest.mark.parametrize("change", ("missing", "value", "bool"))
def test_s3_every_declared_policy_field_is_fixed_and_type_exact(validation, key, change):
    record = oracle.preflight_fixture("packet_wrong_pin")
    if change == "missing":
        del record["declared_policy"][key]
    else:
        original = record["declared_policy"][key]
        record["declared_policy"][key] = (
            True
            if change == "bool"
            else (original + 1 if type(original) is int else "2099-01-01T00:00:00Z")
        )
    _refuses(validation, "preflight", _encoded("preflight", record), _bindings("preflight"))


@pytest.mark.parametrize(
    "path",
    (
        ("creation",),
        ("creation", "identity_transport"),
        ("terminal",),
        ("declared_policy",),
        ("lifecycle", 0),
        ("runtime_pins", 0),
    ),
)
def test_s3_every_nested_record_rejects_extra_fields(validation, path):
    record = oracle.preflight_fixture("packet_wrong_pin")
    target = record
    for key in path:
        target = target[key]
    target["extra"] = None
    _refuses(validation, "preflight", _encoded("preflight", record), _bindings("preflight"))


@pytest.mark.parametrize("key", _RUNTIME_KEYS)
@pytest.mark.parametrize("change", ("missing", "type", "value"))
def test_s3_runtime_rows_are_complete_external_associations(validation, key, change):
    record = oracle.preflight_fixture("packet_wrong_pin")
    if change == "missing":
        del record["runtime_pins"][0][key]
    elif change == "type":
        record["runtime_pins"][0][key] = False
    else:
        record["runtime_pins"][0][key] = 1 if key == "byte_length" else "changed"
    _refuses(validation, "preflight", _encoded("preflight", record), _bindings("preflight"))


@pytest.mark.parametrize("bad", (None, {}, [], [None], [False]))
def test_s3_external_runtime_list_strict_shape_before_decoder(validation, bad):
    bindings = _bindings("preflight")
    bindings["runtime_pins"] = bad
    _refuses(validation, "preflight", b"\xff", bindings, "packet_context")


@pytest.mark.parametrize("key", _RUNTIME_KEYS)
@pytest.mark.parametrize("bad", (None, False, [], {}))
def test_s3_external_runtime_row_fields_are_exact_types(validation, key, bad):
    bindings = _bindings("preflight")
    bindings["runtime_pins"][0][key] = bad
    _refuses(validation, "preflight", b"\xff", bindings, "packet_context")


def test_s3_external_runtime_duplicate_role_path_tuple_refuses(validation):
    bindings = _bindings("preflight")
    bindings["runtime_pins"].append(copy.deepcopy(bindings["runtime_pins"][0]))
    _refuses(validation, "preflight", b"\xff", bindings, "packet_context")


def test_s3_same_physical_path_different_consistent_role_is_not_path_only_duplicate(validation):
    bindings = _bindings("preflight")
    duplicate = copy.deepcopy(bindings["runtime_pins"][0])
    duplicate["role"] = "registered_dependency"
    bindings["runtime_pins"].append(duplicate)
    record = oracle.preflight_fixture("packet_wrong_pin")
    record["runtime_pins"] = copy.deepcopy(bindings["runtime_pins"])
    _exact(
        _call(validation, "preflight", _encoded("preflight", record), bindings),
        oracle.with_own_hash(record, "receipt_sha256"),
    )


@pytest.mark.parametrize("change", ("reverse", "missing", "extra", "null", "dict"))
def test_s3_entire_runtime_order_set_and_cardinality_match_external(validation, change):
    record = oracle.preflight_fixture("packet_wrong_pin")
    if change == "reverse":
        record["runtime_pins"].reverse()
    elif change == "missing":
        record["runtime_pins"].pop()
    elif change == "extra":
        record["runtime_pins"].append(copy.deepcopy(record["runtime_pins"][0]))
    else:
        record["runtime_pins"] = None if change == "null" else {}
    _refuses(validation, "preflight", _encoded("preflight", record), _bindings("preflight"))


@pytest.mark.parametrize("index", (0, 1, 2))
@pytest.mark.parametrize("key", _LIFECYCLE_KEYS)
@pytest.mark.parametrize("change", ("missing", "type"))
def test_s3_every_lifecycle_record_field_is_explicit(validation, index, key, change):
    record = oracle.preflight_fixture("packet_wrong_pin")
    if change == "missing":
        del record["lifecycle"][index][key]
    else:
        record["lifecycle"][index][key] = None
    _refuses(validation, "preflight", _encoded("preflight", record), _bindings("preflight"))


@pytest.mark.parametrize(
    "index,bad", ((0, True), (0, -1), (1, 18446744073709551616), (1, False), (2, 0))
)
def test_s3_lifecycle_times_are_exact_u64_and_nondecreasing(validation, index, bad):
    record = oracle.preflight_fixture("packet_wrong_pin")
    record["lifecycle"][index]["monotonic_ns"] = bad
    _refuses(
        validation, "preflight", _encoded("preflight", record), _bindings("preflight"), "timestamp"
    )


@pytest.mark.parametrize("change", ("reverse", "short", "extra", "event", "ordinal", "related_api"))
def test_s3_lifecycle_exact_order_no_invented_api_or_extra_event(validation, change):
    record = oracle.preflight_fixture("packet_wrong_pin")
    if change == "reverse":
        record["lifecycle"].reverse()
    elif change == "short":
        record["lifecycle"].pop()
    elif change == "extra":
        record["lifecycle"].append(copy.deepcopy(record["lifecycle"][-1]))
    elif change == "event":
        record["lifecycle"][1]["event"] = "job_created"
    elif change == "ordinal":
        record["lifecycle"][1]["ordinal"] = True
    else:
        record["lifecycle"][0]["related_api_ordinals"] = [0]
    _refuses(validation, "preflight", _encoded("preflight", record), _bindings("preflight"))


@pytest.mark.parametrize(
    "path,bad",
    (
        (("packet",), {}),
        (("parent_identity",), {}),
        (("stdout",), {}),
        (("stderr",), []),
        (("result",), {}),
        (("job_observations",), [None]),
        (("api_trace",), [{}]),
        (("creation", "attempted"), 0),
        (("creation", "initialization"), [{}]),
        (("creation", "binding_initialization"), [{}]),
        (("creation", "module_observations"), [{}]),
        (("terminal", "termination_requested"), 0),
        (("terminal", "cleanup_complete"), True),
        (("terminal", "final_job_empty"), True),
        (("terminal", "exit_code_u32"), 0),
        (("terminal", "acceptance"), "failed_control"),
        (("terminal", "failure_code"), "work_deadline"),
        (("terminal", "parent_closes"), [{}]),
    ),
)
def test_s3_pure_receipt_never_manufactures_entered_native_state(validation, path, bad):
    record = oracle.preflight_fixture("packet_wrong_pin")
    _set(record, path, bad)
    _refuses(validation, "preflight", _encoded("preflight", record), _bindings("preflight"))


@pytest.mark.parametrize(
    "field",
    (
        "expected_raw_hex",
        "submitted_raw_hex",
        "submitted_raw_byte_length",
        "submitted_raw_sha256",
        "expected_packet_sha256",
        "first_reason",
    ),
)
@pytest.mark.parametrize("bad", (None, False, 0, [], {}, "changed"))
def test_s3_rejected_body_preserves_full_raw_fields_and_absence(validation, field, bad):
    record = oracle.rejected_fixture("packet_wrong_pin")
    record[field] = bad
    _refuses(validation, "rejected", _encoded("rejected", record), _bindings("rejected"))


@pytest.mark.parametrize(
    "field,bad",
    (
        ("admitted_packet", False),
        ("admitted_packet", 0),
        ("admitted_packet", []),
        ("admitted_packet", {}),
        ("admitted_packet", "changed"),
        ("admitted_packet", True),
        ("native_setup_attempted", None),
        ("native_setup_attempted", True),
        ("native_setup_attempted", 0),
        ("native_setup_attempted", 1),
        ("native_setup_attempted", []),
        ("native_setup_attempted", {}),
    ),
)
def test_s3_rejected_absence_never_coerces_false_or_null(validation, field, bad):
    record = oracle.rejected_fixture("packet_wrong_pin")
    record[field] = bad
    _refuses(validation, "rejected", _encoded("rejected", record), _bindings("rejected"))


@pytest.mark.parametrize("case_id", _CASES)
def test_s3_wrong_selected_control_reason_is_not_relabelled(validation, case_id):
    for kind in _KINDS:
        record = _fixture(kind, case_id)
        if kind == "rejected":
            record["first_reason"] = "packet_json"
        else:
            record["terminal"]["failure_code"] = "packet_json"
        _refuses(validation, kind, _encoded(kind, record), _bindings(kind, case_id))


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("case_id", _CASES)
def test_s3_coherent_replaced_raw_packet_is_not_the_independent_recipe(validation, kind, case_id):
    bindings = _bindings(kind, case_id)
    record = _fixture(kind, case_id)
    if case_id == "packet_first_excess":
        substituted = b"x" * 8193
    else:
        packet = json.loads(bindings["submitted_packet_raw"].decode("ascii"))
        if case_id == "packet_wrong_pin":
            packet["nonce_hex"] = "00000000000000000000000000000005"
        else:
            packet["control"]["amount"] = 1
        substituted = oracle.canonical_bytes(packet)
    bindings["submitted_packet_raw"] = substituted
    submitted_sha = oracle.raw_sha256(substituted)
    if case_id != "packet_wrong_pin":
        bindings["expected_packet_sha256"] = submitted_sha
    if case_id == "unknown_control":
        bindings["expected_packet_raw"] = substituted
    if kind == "rejected":
        record["submitted_raw_hex"] = substituted.hex()
        record["submitted_raw_byte_length"] = len(substituted)
        record["submitted_raw_sha256"] = submitted_sha
        record["expected_packet_sha256"] = bindings["expected_packet_sha256"]
        if case_id == "unknown_control":
            record["expected_raw_hex"] = substituted.hex()
    else:
        record["packet_sha256"] = submitted_sha
    _refuses(validation, kind, _encoded(kind, record), bindings, "packet_context")


@pytest.mark.parametrize("kind", _KINDS)
def test_s3_wrong_pin_requires_every_other_original_byte_unchanged(validation, kind):
    bindings = _bindings(kind)
    original = bindings["expected_packet_raw"]
    assert type(original) is bytes
    changed = original.replace(b'"amount":0', b'"amount":1', 1)
    assert changed != original and len(changed) == len(original)
    bindings["expected_packet_raw"] = changed
    bindings["expected_packet_sha256"] = oracle.raw_sha256(changed)
    record = _fixture(kind)
    if kind == "rejected":
        record["expected_raw_hex"] = changed.hex()
        record["expected_packet_sha256"] = bindings["expected_packet_sha256"]
    _refuses(validation, kind, _encoded(kind, record), bindings, "packet_context")


@pytest.mark.parametrize("kind", _KINDS)
def test_s3_supported_case_recipe_cannot_be_replaced_by_another_supported_case(validation, kind):
    record = _fixture(kind, "packet_wrong_pin")
    bindings = _bindings(kind, "unknown_control")
    _refuses(validation, kind, _encoded(kind, record), bindings, "packet_context")


@pytest.mark.parametrize("kind", _KINDS)
def test_s3_receipt_not_accepted_when_wrong_verifier_is_selected(validation, kind):
    wrong_kind = "preflight" if kind == "rejected" else "rejected"
    raw = _encoded(wrong_kind, _fixture(wrong_kind))
    _refuses(validation, kind, raw, _bindings(kind), "query_value")


@pytest.mark.parametrize("bad", (True, False, 0, -1, 18446744073709551616, "1"))
def test_s3_external_runtime_length_is_positive_exact_u64(validation, bad):
    bindings = _bindings("preflight")
    bindings["runtime_pins"][0]["byte_length"] = bad
    _refuses(validation, "preflight", b"\xff", bindings, "packet_context")


@pytest.mark.parametrize(
    "key,bad",
    (
        ("role", "unknown"),
        ("sha256", "a" * 63),
        ("sha256", "A" * 64),
        ("sha256", "g" * 64),
    ),
)
def test_s3_external_runtime_domains_are_not_adopted_from_the_receipt(validation, key, bad):
    bindings = _bindings("preflight")
    bindings["runtime_pins"][0][key] = bad
    _refuses(validation, "preflight", b"\xff", bindings, "packet_context")


@pytest.mark.parametrize("path", ("", "relative.py"), ids=("empty_text", "relative_text"))
def test_s3_external_runtime_text_does_not_invent_a_new_path_policy(validation, path):
    """P Text permits these declared metadata strings; no file is opened."""
    bindings = _bindings("preflight")
    bindings["runtime_pins"][0]["path"] = path
    _refuses(validation, "preflight", b"\xff", bindings, "utf8")
    record = oracle.preflight_fixture("packet_wrong_pin")
    record["runtime_pins"] = copy.deepcopy(bindings["runtime_pins"])
    expected = oracle.with_own_hash(record, "receipt_sha256")
    _exact(_call(validation, "preflight", oracle.canonical_bytes(expected), bindings), expected)


def test_s3_same_physical_runtime_path_cannot_have_conflicting_raw_identity(validation):
    bindings = _bindings("preflight")
    duplicate = copy.deepcopy(bindings["runtime_pins"][0])
    duplicate["role"] = "registered_dependency"
    duplicate["sha256"] = "0" * 64
    bindings["runtime_pins"].append(duplicate)
    _refuses(validation, "preflight", b"\xff", bindings, "packet_context")


@pytest.mark.parametrize(
    "clocks", ((0, 0, 0), (0, 1, 18446744073709551615), (18446744073709551615,) * 3)
)
def test_s3_lifecycle_u64_equalities_and_maxima_remain_metadata_only(validation, clocks):
    record = oracle.preflight_fixture("packet_wrong_pin")
    for row, clock in zip(record["lifecycle"], clocks, strict=True):
        row["monotonic_ns"] = clock
    expected = oracle.with_own_hash(record, "receipt_sha256")
    _exact(
        _call(validation, "preflight", oracle.canonical_bytes(expected), _bindings("preflight")),
        expected,
    )


@pytest.mark.parametrize(
    "key",
    (
        "create_bool_i32",
        "win32_error_u32",
        "child_pid",
        "child_tid",
        "process_handle_u64",
        "resume_count_u32",
    ),
)
@pytest.mark.parametrize("bad", (0, 1, True, 4294967296, 18446744073709551616))
def test_s3_unentered_native_numeric_fields_never_gain_zero_or_true_values(validation, key, bad):
    record = oracle.preflight_fixture("packet_wrong_pin")
    record["creation"][key] = bad
    _refuses(validation, "preflight", _encoded("preflight", record), _bindings("preflight"))


def _metadata_budget_fixture(body_bytes):
    """Entire independently sized M body; no native/file path is opened."""
    bindings = _bindings("preflight")
    record = oracle.preflight_fixture("packet_wrong_pin")
    prefix = "C:\\__invented_intake_s3__\\"
    suffix = "\\python.exe"
    initial_path = prefix + suffix
    bindings["runtime_pins"][0]["path"] = initial_path
    record["runtime_pins"][0]["path"] = initial_path
    body = {key: value for key, value in record.items() if key != "receipt_sha256"}
    padding = body_bytes - len(oracle.canonical_bytes(body))
    assert padding >= 0
    entire_path = prefix + "a" * padding + suffix
    bindings["runtime_pins"][0]["path"] = entire_path
    record["runtime_pins"][0]["path"] = entire_path
    body = {key: value for key, value in record.items() if key != "receipt_sha256"}
    assert len(oracle.canonical_bytes(body)) == body_bytes
    sealed = oracle.with_own_hash(record, "receipt_sha256")
    raw = oracle.canonical_bytes(sealed)
    assert len(raw) < 67108864
    return raw, sealed, bindings


def test_s3_metadata_budget_exact_limit(validation):
    raw, expected, bindings = _metadata_budget_fixture(8388608)
    _exact(validation.verify_preflight_receipt(raw, **bindings), expected)


def test_s3_metadata_budget_first_excess(validation):
    raw, _expected, bindings = _metadata_budget_fixture(8388609)
    _refuses(validation, "preflight", raw, bindings, "budget")


@pytest.mark.parametrize(
    "kind,key",
    (
        ("rejected", "case_id"),
        ("rejected", "oracle_sha256"),
        ("rejected", "expected_packet_sha256"),
        ("rejected", "submitted_raw_sha256"),
        ("rejected", "rejection_sha256"),
        ("preflight", "case_id"),
        ("preflight", "oracle_sha256"),
        ("preflight", "packet_sha256"),
        ("preflight", "receipt_sha256"),
    ),
)
@pytest.mark.parametrize("bad", (None, False, 0, [], {}))
def test_s3_all_outer_metadata_scalars_reject_type_coercion(validation, kind, key, bad):
    record = _fixture(kind)
    record[key] = bad
    raw = oracle.canonical_bytes(record) if key == _OWN_KEY[kind] else _encoded(kind, record)
    reason = "transport" if key == _OWN_KEY[kind] else "query_value"
    _refuses(validation, kind, raw, _bindings(kind), reason)


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize(
    "case_id,bad",
    (
        ("packet_first_excess", b"{}"),
        ("unknown_control", None),
    ),
)
def test_s3_expected_original_absence_is_selected_recipe_specific(validation, kind, case_id, bad):
    bindings = _bindings(kind, case_id)
    bindings["expected_packet_raw"] = bad
    _refuses(validation, kind, b"\xff", bindings, "packet_context")


@pytest.mark.parametrize("case_id", _CASES)
@pytest.mark.parametrize("change", ("count", "retained_last_byte", "entire_hash", "expected_hash"))
def test_s3_every_rejected_raw_body_is_complete_not_prefix_or_summary(validation, case_id, change):
    record = oracle.rejected_fixture(case_id)
    if change == "count":
        record["submitted_raw_byte_length"] -= 1
    elif change == "retained_last_byte":
        record["submitted_raw_hex"] = record["submitted_raw_hex"][:-2]
    elif change == "entire_hash":
        record["submitted_raw_sha256"] = "0" * 64
    else:
        record["expected_packet_sha256"] = "0" * 64
    _refuses(validation, "rejected", _encoded("rejected", record), _bindings("rejected", case_id))


@pytest.mark.parametrize("index", (0, 1, 2))
@pytest.mark.parametrize("bad", (True, False, -1, 4294967296, "0"))
def test_s3_lifecycle_ordinals_are_exact_nonboolean_u32(validation, index, bad):
    record = oracle.preflight_fixture("packet_wrong_pin")
    record["lifecycle"][index]["ordinal"] = bad
    _refuses(validation, "preflight", _encoded("preflight", record), _bindings("preflight"))


@pytest.mark.parametrize(
    "path", (("lifecycle",), ("job_observations",), ("api_trace",), ("runtime_pins",))
)
@pytest.mark.parametrize("bad", (None, False, 0, "", {}))
def test_s3_all_outer_array_types_are_exact(validation, path, bad):
    record = oracle.preflight_fixture("packet_wrong_pin")
    _set(record, path, bad)
    _refuses(validation, "preflight", _encoded("preflight", record), _bindings("preflight"))


def test_s3_external_runtime_first_excess_count_is_refused_before_decoding(validation):
    bindings = _bindings("preflight")
    base = copy.deepcopy(bindings["runtime_pins"][0])
    bindings["runtime_pins"] = [
        {**base, "path": f"C:\\__invented_intake_s3__\\runtime_{index}.bin"} for index in range(129)
    ]
    _refuses(validation, "preflight", b"\xff", bindings, "packet_context")


def test_s3_external_runtime_exact_count_boundary_retains_all_rows(validation):
    bindings = _bindings("preflight")
    base = copy.deepcopy(bindings["runtime_pins"][0])
    bindings["runtime_pins"] = [
        {**base, "path": f"C:\\__invented_intake_s3__\\runtime_{index}.bin"} for index in range(128)
    ]
    record = oracle.preflight_fixture("packet_wrong_pin")
    record["runtime_pins"] = copy.deepcopy(bindings["runtime_pins"])
    expected = oracle.with_own_hash(record, "receipt_sha256")
    actual = _call(validation, "preflight", oracle.canonical_bytes(expected), bindings)
    _exact(actual, expected)
    assert len(actual["runtime_pins"]) == 128
