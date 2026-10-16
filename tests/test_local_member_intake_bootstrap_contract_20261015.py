"""Independent tests for the registered native-free local-intake S1 slice."""

import importlib.util
import json
from pathlib import Path

import local_member_intake_bootstrap_oracles_20261015 as oracle
import pytest

_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "local_member_intake_bootstrap_contract_20261015_1.py"
)


def test_s1_missing_interface():
    """The first RED is an intended assertion, never a missing import error."""
    assert _SOURCE.is_file(), "S1 pure contract module is not yet implemented"
    spec = importlib.util.spec_from_file_location("local_intake_s1_contract", _SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    refusal = getattr(module, "BootstrapRefusal", None)
    assert isinstance(refusal, type) and issubclass(refusal, ValueError)
    for name in ("packet_contract", "admit_packet", "saved_error_bits"):
        assert callable(getattr(module, name, None)), f"Missing S1 interface: {name}"


@pytest.fixture(scope="module")
def contract_module():
    """Load only the new pure module; never an accepted native-transitive helper."""
    assert _SOURCE.is_file(), "S1 pure contract module is not yet implemented"
    spec = importlib.util.spec_from_file_location("local_intake_s1_contract", _SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_exact(actual, expected):
    """Compare every independent literal, including bool-versus-int distinctions."""
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert actual.keys() == expected.keys()
        for key, value in expected.items():
            _assert_exact(actual[key], value)
    elif type(expected) is list:
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected, strict=True):
            _assert_exact(left, right)
    else:
        assert actual == expected


def _context(raw=b"{}", **changes):
    values = {
        "expected_packet_sha256": oracle.raw_sha256(raw),
        "registration_sha256": "1" * 64,
        "protocol_sha256": "2" * 64,
        "oracle_sha256": "3" * 64,
        "now_unix_ns": 1792076347999999999,
    }
    values.update(changes)
    return values


def _refuses(module, reason, raw, **context_changes):
    hashed = raw if type(raw) is bytes else b"{}"
    with pytest.raises(module.BootstrapRefusal) as caught:
        module.admit_packet(raw, **_context(hashed, **context_changes))
    assert type(caught.value.reason) is str
    assert caught.value.reason == reason


def _raw_packet(**changes):
    packet = oracle.packet_literal("success")
    packet.update(changes)
    return oracle.canonical_bytes(packet)


_CONTROL_ROWS = oracle.packet_contract_literal()["controls"]
_SUPPORTED_IDS = [row["case_id"] for row in _CONTROL_ROWS if row["case_id"] != "unknown_control"]
_FLAG_NAMES = [pair[0] for pair in oracle.authority_flags_literal()]
_PACKET_KEYS = (
    "version",
    "operation",
    "case_id",
    "registration_sha256",
    "protocol_sha256",
    "oracle_sha256",
    "hard_end_utc",
    "nonce_hex",
    "control",
    "authority_flags",
)


def test_packet_contract_matches_complete_independent_literal(contract_module):
    _assert_exact(contract_module.packet_contract(), oracle.packet_contract_literal())


def test_packet_contract_returns_fresh_complete_nested_values(contract_module):
    first = contract_module.packet_contract()
    first["controls"][0]["control"]["amount"] = 999
    first["controls"][1]["nonce_hex"] = "f" * 32
    first["authority_flags"][0][1] = True
    first["canonical_rules"]["separators"][0] = ";"
    first["admission_order"].clear()
    _assert_exact(contract_module.packet_contract(), oracle.packet_contract_literal())


@pytest.mark.parametrize("case_id", _SUPPORTED_IDS)
def test_each_supported_base_control_admits_complete_original_packet(contract_module, case_id):
    expected = oracle.packet_literal(case_id)
    raw = oracle.canonical_bytes(expected)
    actual = contract_module.admit_packet(raw, **_context(raw))
    _assert_exact(actual, expected)


def test_declared_unknown_control_is_not_an_admitted_operation(contract_module):
    raw = oracle.canonical_bytes(oracle.packet_literal("unknown_control"))
    _refuses(contract_module, "packet_control", raw)


def test_admitted_packet_returns_fresh_nested_original_values(contract_module):
    expected = oracle.packet_literal("success")
    raw = oracle.canonical_bytes(expected)
    first = contract_module.admit_packet(raw, **_context(raw))
    first["control"]["amount"] = 999
    first["authority_flags"][0][1] = True
    _assert_exact(contract_module.admit_packet(raw, **_context(raw)), expected)


def test_admission_binds_supplied_external_context_not_hardcoded_test_pins(contract_module):
    expected = oracle.packet_literal(
        "success",
        registration_sha256="4" * 64,
        protocol_sha256="5" * 64,
        oracle_sha256="6" * 64,
    )
    raw = oracle.canonical_bytes(expected)
    actual = contract_module.admit_packet(
        raw,
        **_context(
            raw,
            registration_sha256="4" * 64,
            protocol_sha256="5" * 64,
            oracle_sha256="6" * 64,
        ),
    )
    _assert_exact(actual, expected)


def test_declared_first_excess_recipe_refuses_before_parsing(contract_module):
    raw = oracle.packet_first_excess_bytes()
    assert len(raw) == 8193
    _refuses(contract_module, "packet_length", raw)


def test_declared_wrong_pin_recipe_refuses_complete_original_bytes(contract_module):
    expected_raw, submitted_raw = oracle.packet_wrong_pin_pair()
    assert expected_raw != submitted_raw
    _refuses(
        contract_module,
        "packet_pin",
        submitted_raw,
        expected_packet_sha256=oracle.raw_sha256(expected_raw),
    )


class _BytesTrap(bytes):
    def __len__(self):
        raise AssertionError("bytes subclass length must remain untouched")

    def decode(self, *args, **kwargs):
        raise AssertionError("bytes subclass decoder must remain untouched")


class _StringTrap(str):
    def __len__(self):
        raise AssertionError("string subclass must remain untouched")

    def lower(self):
        raise AssertionError("string subclass must not be normalized")


class _IntegerTrap(int):
    def __int__(self):
        raise AssertionError("integer subclass must not be coerced")

    def __lt__(self, other):
        raise AssertionError("integer subclass must remain untouched")

    def __ge__(self, other):
        raise AssertionError("integer subclass must remain untouched")


@pytest.mark.parametrize(
    "raw",
    [None, True, 0, "{}", {}, [], bytearray(b"{}"), memoryview(b"{}"), _BytesTrap(b"{}")],
    ids=["none", "bool", "int", "text", "dict", "list", "bytearray", "memoryview", "subclass"],
)
def test_raw_requires_exact_builtin_bytes_before_other_access(contract_module, raw):
    _refuses(contract_module, "packet_type", raw, now_unix_ns=-1)


@pytest.mark.parametrize("raw", [b"", b"0" * 8193], ids=["empty", "first_excess"])
def test_raw_length_precedes_invalid_external_context(contract_module, raw):
    _refuses(contract_module, "packet_length", raw, now_unix_ns=-1)


@pytest.mark.parametrize("length", [1, 8191, 8192])
def test_inclusive_length_bounds_reach_later_json_schema_or_canonical_gate(contract_module, length):
    raw = b"0" + b" " * (length - 1)
    _refuses(contract_module, "packet_schema" if length == 1 else "packet_canonical", raw)


@pytest.mark.parametrize(
    "field", ["expected_packet_sha256", "registration_sha256", "protocol_sha256", "oracle_sha256"]
)
@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        0,
        "",
        "1" * 63,
        "1" * 65,
        "A" * 64,
        "g" * 64,
        " " + "1" * 63,
        _StringTrap("1" * 64),
    ],
    ids=[
        "none",
        "bool",
        "int",
        "empty",
        "short",
        "long",
        "uppercase",
        "nonhex",
        "space",
        "subclass",
    ],
)
def test_external_digest_context_is_exact_before_raw_pin_and_decode(contract_module, field, value):
    _refuses(contract_module, "packet_context", b"\xff", **{field: value})


@pytest.mark.parametrize(
    "value",
    [
        None,
        False,
        True,
        0.0,
        "0",
        -1,
        18446744073709551616,
        _IntegerTrap(0),
        1792076348000000000,
        1792076348000000001,
        18446744073709551615,
    ],
    ids=[
        "none",
        "false",
        "true",
        "float",
        "text",
        "negative",
        "u64_excess",
        "subclass",
        "deadline_equal",
        "deadline_excess",
        "u64_max_expired",
    ],
)
def test_invalid_or_expired_now_refuses_before_raw_decoding(contract_module, value):
    _refuses(contract_module, "packet_context", b"\xff", now_unix_ns=value)


@pytest.mark.parametrize("value", [0, 1, 1792076347999999999])
def test_valid_u64_now_is_strictly_before_fixed_deadline(contract_module, value):
    raw = _raw_packet()
    _assert_exact(
        contract_module.admit_packet(raw, **_context(raw, now_unix_ns=value)),
        oracle.packet_literal("success"),
    )


def test_external_raw_pin_precedes_invalid_utf8(contract_module):
    _refuses(contract_module, "packet_pin", b"\xff", expected_packet_sha256="0" * 64)


@pytest.mark.parametrize(
    "raw",
    [b"\xff", b"\xc0\xaf", b"\xe2\x82", b"\xef\xbb\xbf{}", b"\xff\xfe{\x00}"],
    ids=["ff", "overlong", "incomplete", "bom", "utf16"],
)
def test_packet_encoding_is_strict_utf8_without_bom(contract_module, raw):
    _refuses(contract_module, "packet_encoding", raw)


@pytest.mark.parametrize(
    "raw",
    [
        b"{",
        b"{} {}",
        b"{}null",
        b'{"x":1,"x":2}',
        b'{"x":{"a":0,"a":1}}',
        b'{"x":1,"\\u0078":2}',
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b'{"x":NaN}',
        b"1e9999",
        b"-1e9999",
        b'{"x":1e9999}',
        b"[1,]",
        b'{"x":01}',
    ],
    ids=[
        "incomplete",
        "two_values",
        "suffix",
        "duplicate_top",
        "duplicate_nested",
        "duplicate_escaped_name",
        "nan",
        "infinity",
        "negative_infinity",
        "nested_nan",
        "overflow_float",
        "negative_overflow_float",
        "nested_overflow_float",
        "trailing_comma",
        "leading_zero",
    ],
)
def test_json_rejects_complete_malformed_or_ambiguous_input(contract_module, raw):
    _refuses(contract_module, "packet_json", raw)


@pytest.mark.parametrize("prefix,suffix", [(b" ", b""), (b"", b" "), (b"\n", b"\r\n")])
def test_one_value_whitespace_is_noncanonical_not_prefix_adopted(contract_module, prefix, suffix):
    _refuses(contract_module, "packet_canonical", prefix + _raw_packet() + suffix)


def test_noncanonical_object_key_order_is_refused(contract_module):
    raw = json.dumps(oracle.packet_literal("success"), separators=(",", ":")).encode("utf-8")
    assert raw != _raw_packet()
    _refuses(contract_module, "packet_canonical", raw)


@pytest.mark.parametrize(
    "replacement",
    [b'"amount":-0', b'"amount": 0', b'"amount" :0'],
    ids=["negative_zero", "space_after_colon", "space_before_colon"],
)
def test_noncanonical_numeric_and_spacing_spellings_refuse(contract_module, replacement):
    raw = _raw_packet().replace(b'"amount":0', replacement, 1)
    _refuses(contract_module, "packet_canonical", raw)


def test_equivalent_unicode_escape_is_not_canonical_literal_spelling(contract_module):
    raw = _raw_packet().replace(b'"operation":"bootstrap"', b'"operation":"\\u0062ootstrap"')
    _refuses(contract_module, "packet_canonical", raw)


def test_canonical_ascii_escaping_precedes_invalid_control_value(contract_module):
    packet = oracle.packet_literal("success")
    packet["control"]["literal_hex"] = "\u00e9"
    canonical = oracle.canonical_bytes(packet)
    raw_utf8 = json.dumps(
        packet,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    _refuses(contract_module, "packet_canonical", raw_utf8)
    _refuses(contract_module, "packet_control", canonical)


@pytest.mark.parametrize(
    "value",
    [None, False, 0, 1.0, "text", [], [1], [[[0]]]],
    ids=["null", "bool", "int", "float", "text", "empty_list", "list", "nested_list"],
)
def test_canonical_non_object_json_is_packet_schema_refusal(contract_module, value):
    _refuses(contract_module, "packet_schema", oracle.canonical_bytes(value))


def test_actual_bounded_nested_json_reaches_schema_without_native_work(contract_module):
    raw = b"[" * 64 + b"0" + b"]" * 64
    _refuses(contract_module, "packet_schema", raw)


@pytest.mark.parametrize("field", _PACKET_KEYS)
def test_each_missing_top_level_field_refuses_exact_schema(contract_module, field):
    packet = oracle.packet_literal("success")
    del packet[field]
    _refuses(contract_module, "packet_schema", oracle.canonical_bytes(packet))


@pytest.mark.parametrize("field", ["extra", "Version", "__class__"])
def test_any_extra_top_level_field_refuses_exact_schema(contract_module, field):
    packet = oracle.packet_literal("success")
    packet[field] = None
    _refuses(contract_module, "packet_schema", oracle.canonical_bytes(packet))


@pytest.mark.parametrize("field", _PACKET_KEYS[:8])
@pytest.mark.parametrize("value", [None, False, 0, 0.0, [], {}])
def test_each_string_metadata_field_requires_exact_json_string(contract_module, field, value):
    _refuses(contract_module, "packet_schema", _raw_packet(**{field: value}))


@pytest.mark.parametrize("value", [None, False, 0, "", []])
def test_control_top_level_type_checked_before_context(contract_module, value):
    _refuses(contract_module, "packet_schema", _raw_packet(control=value, version="wrong"))


@pytest.mark.parametrize("value", [None, False, 0, "", {}])
def test_authority_top_level_type_checked_before_context(contract_module, value):
    _refuses(contract_module, "packet_schema", _raw_packet(authority_flags=value, version="wrong"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", "wrong"),
        ("version", "LOCAL-MEMBER-INTAKE-BOOTSTRAP-PACKET-V1"),
        ("operation", "Bootstrap"),
        ("operation", "other"),
        ("hard_end_utc", "2026-10-15T14:59:08.000000Z"),
        ("hard_end_utc", "2026-10-15T14:59:09Z"),
        ("registration_sha256", "4" * 64),
        ("protocol_sha256", "4" * 64),
        ("oracle_sha256", "4" * 64),
    ],
)
def test_complete_packet_context_values_match_external_literals(contract_module, field, value):
    _refuses(contract_module, "packet_context", _raw_packet(**{field: value}))


def test_packet_context_precedes_authority_and_control_traversal(contract_module):
    _refuses(
        contract_module,
        "packet_context",
        _raw_packet(version="wrong", authority_flags=[["source_authenticated", True]], control={}),
    )


@pytest.mark.parametrize("index", range(28), ids=_FLAG_NAMES)
@pytest.mark.parametrize("value", [True, 0, 1, None, "false", []])
def test_every_authority_requires_literal_false_without_coercion(contract_module, index, value):
    packet = oracle.packet_literal("success")
    packet["authority_flags"][index][1] = value
    packet["control"] = {}
    _refuses(contract_module, "authority_flags", oracle.canonical_bytes(packet))


@pytest.mark.parametrize("index", range(28), ids=_FLAG_NAMES)
def test_every_authority_name_is_exact_and_complete(contract_module, index):
    packet = oracle.packet_literal("success")
    packet["authority_flags"][index][0] += "_changed"
    _refuses(contract_module, "authority_flags", oracle.canonical_bytes(packet))


@pytest.mark.parametrize(
    "variant",
    ["missing", "extra", "reordered", "short_pair", "long_pair", "object"],
)
def test_authority_full_order_and_pair_shape_are_fixed(contract_module, variant):
    packet = oracle.packet_literal("success")
    flags = packet["authority_flags"]
    if variant == "missing":
        flags.pop()
    elif variant == "extra":
        flags.append(["extra", False])
    elif variant == "reordered":
        flags[0], flags[1] = flags[1], flags[0]
    elif variant == "short_pair":
        flags[0] = [flags[0][0]]
    elif variant == "long_pair":
        flags[0].append(False)
    else:
        flags[0] = {"name": flags[0][0], "value": False}
    _refuses(contract_module, "authority_flags", oracle.canonical_bytes(packet))


@pytest.mark.parametrize("case_id", _SUPPORTED_IDS)
def test_each_supported_control_nonce_is_original_complete_literal(contract_module, case_id):
    packet = oracle.packet_literal(case_id)
    packet["nonce_hex"] = "f" * 32
    _refuses(contract_module, "packet_control", oracle.canonical_bytes(packet))


@pytest.mark.parametrize("nonce", ["", "0" * 31, "0" * 33, "F" * 32, "0" * 31 + "g"])
def test_nonce_has_no_length_case_or_nonhex_normalization(contract_module, nonce):
    _refuses(contract_module, "packet_control", _raw_packet(nonce_hex=nonce))


@pytest.mark.parametrize("case_id", ["", "SUCCESS", "success ", "unregistered", "unknown_control"])
def test_control_dispatch_never_accepts_alias_default_or_unknown_kind(contract_module, case_id):
    _refuses(contract_module, "packet_control", _raw_packet(case_id=case_id))


@pytest.mark.parametrize("field", ["kind", "amount", "literal_hex", "fault_site"])
def test_each_control_field_is_mandatory(contract_module, field):
    packet = oracle.packet_literal("success")
    del packet["control"][field]
    _refuses(contract_module, "packet_control", oracle.canonical_bytes(packet))


@pytest.mark.parametrize(
    "field,value",
    [
        ("extra", None),
        ("kind", "EMIT_OK"),
        ("kind", None),
        ("kind", 0),
        ("amount", True),
        ("amount", False),
        ("amount", 0.0),
        ("amount", "0"),
        ("amount", -1),
        ("amount", 1),
        ("amount", 4294967296),
        ("literal_hex", None),
        ("literal_hex", 0),
        ("literal_hex", "00"),
        ("literal_hex", "F"),
        ("literal_hex", "0" * 514),
        ("fault_site", None),
        ("fault_site", False),
        ("fault_site", "NONE"),
    ],
)
def test_control_fields_require_exact_types_values_and_closed_keys(contract_module, field, value):
    packet = oracle.packet_literal("success")
    packet["control"][field] = value
    _refuses(contract_module, "packet_control", oracle.canonical_bytes(packet))


@pytest.mark.parametrize("case_id", _SUPPORTED_IDS)
def test_control_cannot_borrow_another_declared_rows_amount(contract_module, case_id):
    packet = oracle.packet_literal(case_id)
    packet["control"]["amount"] += 1
    _refuses(contract_module, "packet_control", oracle.canonical_bytes(packet))


@pytest.mark.parametrize("value", [b'"amount":0.0', b'"amount":-0.0'])
def test_canonical_float_amount_is_not_coerced_to_integer(contract_module, value):
    raw = _raw_packet().replace(b'"amount":0', value, 1)
    _refuses(contract_module, "packet_control", raw)


@pytest.mark.parametrize(
    "error_type",
    [ValueError, RecursionError],
    ids=["int_digit_value", "recursion"],
)
def test_expected_decoder_errors_are_explicit_json_refusals(
    contract_module,
    monkeypatch,
    error_type,
):
    raw = _raw_packet()
    context = _context(raw)

    def failed_decoder(*args, **kwargs):
        raise error_type("independent decoder-boundary failure")

    with monkeypatch.context() as patch:
        patch.setattr(json, "loads", failed_decoder)
        with pytest.raises(contract_module.BootstrapRefusal) as caught:
            contract_module.admit_packet(raw, **context)
        assert caught.value.reason == "packet_json"


def test_unexpected_decoder_assertion_propagates_uncaught(contract_module, monkeypatch):
    raw = _raw_packet()
    context = _context(raw)
    marker = AssertionError("independent unexpected decoder sentinel")

    def failed_decoder(*args, **kwargs):
        raise marker

    with monkeypatch.context() as patch:
        patch.setattr(json, "loads", failed_decoder)
        with pytest.raises(AssertionError) as caught:
            contract_module.admit_packet(raw, **context)
        assert caught.value is marker


def test_scoped_canonical_encoder_recursion_is_explicit_json_refusal(contract_module, monkeypatch):
    raw = _raw_packet()
    context = _context(raw)

    def failed_encoder(*args, **kwargs):
        raise RecursionError("independent canonical encoder depth failure")

    with monkeypatch.context() as patch:
        patch.setattr(json, "dumps", failed_encoder)
        with pytest.raises(contract_module.BootstrapRefusal) as caught:
            contract_module.admit_packet(raw, **context)
        assert caught.value.reason == "packet_json"


def test_unexpected_canonical_encoder_assertion_propagates_uncaught(contract_module, monkeypatch):
    raw = _raw_packet()
    context = _context(raw)
    marker = AssertionError("independent unexpected canonical encoder sentinel")

    def failed_encoder(*args, **kwargs):
        raise marker

    with monkeypatch.context() as patch:
        patch.setattr(json, "dumps", failed_encoder)
        with pytest.raises(AssertionError) as caught:
            contract_module.admit_packet(raw, **context)
        assert caught.value is marker


def test_invalid_external_context_never_calls_json_decoder(contract_module, monkeypatch):
    raw = _raw_packet()

    def forbidden_decoder(*args, **kwargs):
        raise AssertionError("JSON decoder must remain deferred")

    with monkeypatch.context() as patch:
        patch.setattr(json, "loads", forbidden_decoder)
        _refuses(contract_module, "packet_context", raw, now_unix_ns=-1)


@pytest.mark.parametrize(
    "signed,expected",
    [
        (-2147483648, 2147483648),
        (-1, 4294967295),
        (0, 0),
        (1, 1),
        (2147483647, 2147483647),
        (-2147483647, 2147483649),
        (-2, 4294967294),
        (2147483646, 2147483646),
    ],
)
def test_saved_error_signed_int32_preserves_exact_unsigned_bits(contract_module, signed, expected):
    actual = contract_module.saved_error_bits(signed)
    assert type(actual) is int
    assert actual == expected
    assert (actual if actual < 2147483648 else actual - 4294967296) == signed


@pytest.mark.parametrize(
    "value",
    [
        False,
        True,
        None,
        0.0,
        "0",
        b"0",
        [],
        {},
        -2147483649,
        2147483648,
        4294967295,
        -(1 << 64),
        1 << 64,
        _IntegerTrap(0),
    ],
    ids=[
        "false",
        "true",
        "none",
        "float",
        "text",
        "bytes",
        "list",
        "dict",
        "i32_below",
        "i32_above",
        "u32_max",
        "huge_negative",
        "huge_positive",
        "subclass",
    ],
)
def test_saved_error_rejects_non_int32_without_coercion_or_mask(contract_module, value):
    with pytest.raises(contract_module.BootstrapRefusal) as caught:
        contract_module.saved_error_bits(value)
    assert caught.value.reason == "saved_error"


def test_declared_refusal_reason_is_exact_and_read_only(contract_module):
    with pytest.raises(contract_module.BootstrapRefusal) as caught:
        contract_module.admit_packet(None, **_context())
    assert caught.value.reason == "packet_type"
    with pytest.raises((AttributeError, TypeError)):
        caught.value.reason = "packet_control"
    assert caught.value.reason == "packet_type"
