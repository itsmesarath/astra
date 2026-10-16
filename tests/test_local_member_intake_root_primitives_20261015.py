"""Read the complete historical S2 evidence; never execute PowerShell from pytest.

The pre-fixed JSON vectors and nine literal clock cases are the semantic oracles.
Report hashes pin provenance only. No production parser, serializer, native helper,
subprocess, reflection, or source import participates in these assertions.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LOG = _ROOT / "logs" / "local_member_intake_proof_20261015_1"
_OBSERVER = _ROOT / "scripts" / "local_member_intake_observer_20261015_1.ps1"
_SOURCE_SNAPSHOT = _LOG / "root_observer_primitives_accepted.snapshot"
_VECTOR_PATH = _ROOT / "tests" / "local_member_intake_root_primitive_vectors_20261015_1.json"
_RECEIPT_PATH = _LOG / "root_primitives_1.json"
_SOURCE_SHA = "c7ead7d864cf7ca4df99b7b478a1516b2b9137fb31160dec2c225cbb24b6f823"
_VECTOR_SHA = "321fedfa5b9d88583a216ee4e636fb182959e72fc0c096ad0ef78a609157e22d"
_RECEIPT_SHA = "1763ba0306d2e1274ee82d32e4988cb5b54225654e735623d62382f5d8659c27"
_START_UTC_NS = 1792047548000000000
_HARD_END_UTC_NS = 1792076348000000000
_I64_MAX = 9223372036854775807
_U64_MAX = 18446744073709551615
_LOWER_HEX = re.compile(r"(?:[0-9a-f]{2})*", re.ASCII)
_ID = re.compile(r"[a-z][a-z0-9_]*", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}", re.ASCII)

_CANONICAL_IDS = (
    "c_empty_object",
    "c_empty_array",
    "c_empty_string",
    "c_null",
    "c_true",
    "c_false",
    "c_zero",
    "c_negative_zero",
    "c_i64_min",
    "c_i64_max",
    "c_i64_successor",
    "c_u64_max",
    "c_whitespace",
    "c_key_order_case",
    "c_nested",
    "c_singleton_array",
    "c_escaped_slash",
    "c_short_escapes",
    "c_controls_del",
    "c_raw_del",
    "c_quote_backslash",
    "c_nonascii_utf8",
    "c_astral_utf8",
    "c_combining_no_normalize",
    "c_date_string",
    "c_scalar_key_order",
    "c_unpaired_surrogates",
    "c_escaped_key",
    "c_depth_64",
)
_REJECTION_IDS = (
    "r_empty",
    "r_utf8_invalid",
    "r_utf8_overlong",
    "r_utf8_truncated",
    "r_utf8_surrogate",
    "r_utf8_bom",
    "r_duplicate",
    "r_escaped_duplicate",
    "r_nested_duplicate",
    "r_trailing_value",
    "r_comment",
    "r_incomplete",
    "r_trailing_comma",
    "r_control_in_string",
    "r_invalid_escape",
    "r_leading_zero",
    "r_plus_integer",
    "r_i64_first_below",
    "r_u64_first_excess",
    "r_fraction",
    "r_exponent",
    "r_overflow_exponent",
    "r_nan",
    "r_infinity",
    "r_negative_infinity",
    "r_depth_65",
)
_CLOCK_LITERALS = (
    ("zero", 0, 1, 0, None),
    ("one_third", 1, 3, 333333333, None),
    ("two_thirds", 2, 3, 666666666, None),
    ("one_second", 3, 3, 1000000000, None),
    ("max_i64_exact", 9223372036854775807, 1000000000, 9223372036854775807, None),
    ("negative_ticks", -1, 1, None, "clock"),
    ("zero_frequency", 1, 0, None, "clock"),
    ("negative_frequency", 1, -1, None, "clock"),
    ("u64_overflow", 9223372036854775807, 1, None, "clock"),
)
_AUTHORITY_NAMES = (
    "source_authenticated",
    "collection_receipt_authenticated",
    "native_runtime_authenticated",
    "native_abi_authenticated",
    "native_wire_authenticated",
    "native_header_authenticated",
    "native_eof_authenticated",
    "feed_authenticated",
    "calendar_authenticated",
    "historical_read_authorized",
    "historical_validation_authorized",
    "book_acceptance_authorized",
    "event_acceptance_authorized",
    "feature_acceptance_authorized",
    "account_authorized",
    "funding_authorized",
    "receipt_authorized",
    "cash_authorized",
    "margin_authorized",
    "risk_authorized",
    "storage_authorized",
    "resume_authorized",
    "execution_authorized",
    "trading_authorized",
    "training_authorized",
    "scoring_authorized",
    "independent_validation_authorized",
    "promotion_authorized",
)


def _read_complete(path, limit):
    assert path.is_file(), f"Missing immutable evidence: {path}"
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    assert 0 < len(raw) <= limit, f"Evidence size outside fixed bound: {path}"
    return raw


def _read_pinned(path, length, sha256, limit):
    raw = _read_complete(path, limit)
    assert len(raw) == length
    assert hashlib.sha256(raw).hexdigest() == sha256
    return raw


def _no_duplicate_pairs(pairs):
    value = {}
    for key, item in pairs:
        assert key not in value, f"Duplicate JSON key: {key!r}"
        value[key] = item
    return value


def _not_a_json_integer(token):
    raise AssertionError(f"Unexpected non-integer token in evidence: {token}")


def _parse_json(raw):
    assert type(raw) is bytes
    assert not raw.startswith(b"\xef\xbb\xbf")
    return json.loads(
        raw.decode("utf-8", errors="strict"),
        object_pairs_hook=_no_duplicate_pairs,
        parse_float=_not_a_json_integer,
        parse_constant=_not_a_json_integer,
    )


def _canonical(value):
    """Independent stdlib canonicalization of the receipt, not its byte oracles."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _keys(value, names):
    assert type(value) is dict
    assert set(value) == set(names)
    assert len(value) == len(names)


def _exact(value, expected):
    """Prevent bool/int equality or any nested shape/type coercion."""
    assert type(value) is type(expected)
    if type(expected) is dict:
        _keys(value, expected)
        for key, item in expected.items():
            _exact(value[key], item)
    elif type(expected) is list:
        assert len(value) == len(expected)
        for actual_item, expected_item in zip(value, expected, strict=True):
            _exact(actual_item, expected_item)
    else:
        assert value == expected


def _integer(value, lower, upper):
    assert type(value) is int
    assert lower <= value <= upper


def _hex_bytes(value, maximum=8192):
    assert type(value) is str
    assert _LOWER_HEX.fullmatch(value) is not None
    assert len(value) <= 2 * maximum
    return bytes.fromhex(value)


def _byte_literal(value):
    _keys(value, ("encoding", "data"))
    assert type(value["encoding"]) is str
    assert type(value["data"]) is str
    if value["encoding"] == "ascii":
        raw = value["data"].encode("ascii", errors="strict")
    else:
        assert value["encoding"] == "hex"
        raw = _hex_bytes(value["data"])
    assert len(raw) <= 8192
    return raw


@pytest.fixture(scope="module")
def vectors():
    raw = _read_pinned(_VECTOR_PATH, 6849, _VECTOR_SHA, 1048576)
    value = _parse_json(raw)
    _keys(value, ("version", "canonical_vectors", "rejection_vectors"))
    _exact(value["version"], "local-intake-root-primitive-vectors-v1")
    assert type(value["canonical_vectors"]) is list
    assert type(value["rejection_vectors"]) is list
    assert len(value["canonical_vectors"]) == 29
    assert len(value["rejection_vectors"]) == 26
    assert len(value["canonical_vectors"]) + len(value["rejection_vectors"]) <= 64
    for row in value["canonical_vectors"]:
        _keys(row, ("id", "raw", "canonical"))
        assert type(row["id"]) is str and _ID.fullmatch(row["id"]) is not None
        _byte_literal(row["raw"])
        _byte_literal(row["canonical"])
    for row in value["rejection_vectors"]:
        _keys(row, ("id", "raw", "reason"))
        assert type(row["id"]) is str and _ID.fullmatch(row["id"]) is not None
        _byte_literal(row["raw"])
        assert type(row["reason"]) is str
        assert row["reason"] in ("encoding", "duplicate", "json", "number")
    _exact([row["id"] for row in value["canonical_vectors"]], list(_CANONICAL_IDS))
    _exact([row["id"] for row in value["rejection_vectors"]], list(_REJECTION_IDS))
    assert len(set(_CANONICAL_IDS + _REJECTION_IDS)) == 55
    return value


@pytest.fixture(scope="module")
def receipt():
    raw = _read_pinned(_RECEIPT_PATH, 12382, _RECEIPT_SHA, 2097152)
    assert raw.isascii() and not raw.endswith((b"\r", b"\n"))
    value = _parse_json(raw)
    _keys(
        value,
        (
            "version",
            "vector_identity",
            "observer_identity",
            "clock",
            "canonical_rows",
            "rejection_rows",
            "clock_vectors",
            "authority_flags",
            "receipt_sha256",
        ),
    )
    _exact(value["version"], "local-intake-root-primitives-v1")
    assert _canonical(value) == raw
    assert type(value["receipt_sha256"]) is str
    assert _SHA.fullmatch(value["receipt_sha256"]) is not None
    body = {key: item for key, item in value.items() if key != "receipt_sha256"}
    assert hashlib.sha256(_canonical(body)).hexdigest() == value["receipt_sha256"]
    return value


def test_s2_missing_interface():
    """Same collected test that genuinely failed before source existed."""
    assert _OBSERVER.is_file(), "Registered pure root observer is not yet implemented"


def test_s2_historical_source_snapshot_is_complete(receipt):
    snapshot = _read_pinned(_SOURCE_SNAPSHOT, 23715, _SOURCE_SHA, 1048576)
    _exact(
        receipt["observer_identity"],
        {
            "raw_byte_length": len(snapshot),
            "raw_sha256": _SOURCE_SHA,
        },
    )


def test_s2_current_source_has_not_silently_replaced_historical_qualification():
    """A future source expansion needs separately reviewed C3-equivalence support."""
    current = _read_complete(_OBSERVER, 1048576)
    assert hashlib.sha256(current).hexdigest() == _SOURCE_SHA, (
        "Observer changed: register/review complete pure-function-equivalence "
        "evidence before amending this isolated current-source gate; do not "
        "rewrite the historical source snapshot or rerun S2 for status"
    )


def test_s2_vector_identity_is_the_complete_pre_fixed_resource(receipt, vectors):
    _exact(
        receipt["vector_identity"],
        {
            "raw_byte_length": 6849,
            "raw_sha256": _VECTOR_SHA,
        },
    )
    assert len(vectors["canonical_vectors"]) + len(vectors["rejection_vectors"]) == 55


def test_s2_complete_ordered_cohort_no_missing_extra_or_subset(receipt):
    for name in ("canonical_rows", "rejection_rows", "clock_vectors", "authority_flags"):
        assert type(receipt[name]) is list
    _exact([row["id"] for row in receipt["canonical_rows"]], list(_CANONICAL_IDS))
    _exact([row["id"] for row in receipt["rejection_rows"]], list(_REJECTION_IDS))
    _exact([row["id"] for row in receipt["clock_vectors"]], [row[0] for row in _CLOCK_LITERALS])
    assert len(receipt["canonical_rows"]) + len(receipt["rejection_rows"]) == 55
    assert (
        sum(
            len(receipt[name])
            for name in (
                "canonical_rows",
                "rejection_rows",
                "clock_vectors",
            )
        )
        == 64
    )
    assert len(receipt["authority_flags"]) == 28


@pytest.mark.parametrize("index,case_id", enumerate(_CANONICAL_IDS), ids=_CANONICAL_IDS)
def test_s2_each_complete_canonical_vector(receipt, vectors, index, case_id):
    literal = vectors["canonical_vectors"][index]
    raw = _byte_literal(literal["raw"])
    expected = _byte_literal(literal["canonical"])
    actual = receipt["canonical_rows"][index]
    _exact(
        actual,
        {
            "id": case_id,
            "raw_hex": raw.hex(),
            "expected_canonical_hex": expected.hex(),
            "actual_canonical_hex": expected.hex(),
            "matched": True,
        },
    )
    assert _hex_bytes(actual["raw_hex"]) == raw
    assert _hex_bytes(actual["expected_canonical_hex"]) == expected
    assert _hex_bytes(actual["actual_canonical_hex"]) == expected


@pytest.mark.parametrize("index,case_id", enumerate(_REJECTION_IDS), ids=_REJECTION_IDS)
def test_s2_each_complete_rejection_vector(receipt, vectors, index, case_id):
    literal = vectors["rejection_vectors"][index]
    raw = _byte_literal(literal["raw"])
    actual = receipt["rejection_rows"][index]
    _exact(
        actual,
        {
            "id": case_id,
            "raw_hex": raw.hex(),
            "expected_reason": literal["reason"],
            "actual_reason": literal["reason"],
            "matched": True,
        },
    )
    assert _hex_bytes(actual["raw_hex"]) == raw


@pytest.mark.parametrize(
    "index,literal", enumerate(_CLOCK_LITERALS), ids=[row[0] for row in _CLOCK_LITERALS]
)
def test_s2_each_actual_clock_boundary(receipt, index, literal):
    case_id, ticks, frequency, expected_ns, reason = literal
    actual = receipt["clock_vectors"][index]
    _exact(
        actual,
        {
            "id": case_id,
            "ticks_i64": ticks,
            "frequency_i64": frequency,
            "expected_ns_u64": expected_ns,
            "expected_reason": reason,
            "actual_ns_u64": expected_ns,
            "actual_reason": reason,
            "matched": True,
        },
    )
    _integer(actual["ticks_i64"], -9223372036854775808, _I64_MAX)
    _integer(actual["frequency_i64"], -9223372036854775808, _I64_MAX)
    if reason is None:
        _integer(actual["actual_ns_u64"], 0, _U64_MAX)
        assert (ticks * 1000000000) // frequency == expected_ns
    else:
        assert actual["actual_ns_u64"] is None
        assert ticks < 0 or frequency <= 0 or (ticks * 1000000000) // frequency > _U64_MAX


def test_s2_actual_observation_clock_is_integer_monotonic_and_before_deadline(receipt):
    clock = receipt["clock"]
    _keys(
        clock,
        (
            "frequency_i64",
            "start_ticks_i64",
            "end_ticks_i64",
            "start_monotonic_ns_u64",
            "end_monotonic_ns_u64",
            "started_utc_unix_ns_u64",
            "ended_utc_unix_ns_u64",
        ),
    )
    _integer(clock["frequency_i64"], 1, _I64_MAX)
    for key in ("start_ticks_i64", "end_ticks_i64"):
        _integer(clock[key], 0, _I64_MAX)
    for key in (
        "start_monotonic_ns_u64",
        "end_monotonic_ns_u64",
        "started_utc_unix_ns_u64",
        "ended_utc_unix_ns_u64",
    ):
        _integer(clock[key], 0, _U64_MAX)
    assert clock["start_ticks_i64"] <= clock["end_ticks_i64"]
    assert clock["start_monotonic_ns_u64"] <= clock["end_monotonic_ns_u64"]
    assert (
        _START_UTC_NS
        <= clock["started_utc_unix_ns_u64"]
        <= clock["ended_utc_unix_ns_u64"]
        < _HARD_END_UTC_NS
    )
    for prefix in ("start", "end"):
        assert (
            clock[f"{prefix}_monotonic_ns_u64"]
            == (clock[f"{prefix}_ticks_i64"] * 1000000000) // clock["frequency_i64"]
        )
    # This interval ends before sealing/write. Tool/owned-exit evidence below,
    # not an invented post-emission timestamp inside the receipt, covers return.


@pytest.mark.parametrize("index,name", enumerate(_AUTHORITY_NAMES), ids=_AUTHORITY_NAMES)
def test_s2_each_authority_is_literal_false_in_original_order(receipt, index, name):
    _exact(receipt["authority_flags"][index], [name, False])


def test_s2_actual_receipt_has_complete_root_tool_and_acceptance_provenance(receipt):
    """These frozen files prove origin, not expected parser/clock semantics."""
    owned_raw = _read_pinned(
        _LOG / "root_primitives_1_owned.json",
        8981,
        "510a650f575d1ad37e22a0ca6a2efbbc2af33f93fb71174f56905a4cd06a70cb",
        1048576,
    )
    tool_raw = _read_pinned(
        _LOG / "root_primitives_1_tool.json",
        9417,
        "1022d93312435d7a75d05f0cb8d63750e1ee9779e28012c5a4d81260d023a2a6",
        1048576,
    )
    acceptance_raw = _read_pinned(
        _LOG / "root_primitives_1_acceptance.json",
        1160,
        "668e3ba7a02bece1cc5d347234458eeae67545f49ab5b627a2564cbd9470777e",
        1048576,
    )
    command = _read_pinned(
        _LOG / "root_primitives_1_command.txt",
        7104,
        "f1b0ec6258c4300f95edde2a579629f586e8f46a21a14ff0196558461558f576",
        1048576,
    ).decode("utf-8", errors="strict")
    owned = _parse_json(owned_raw)
    # The tool envelope contains an observed duration, not restricted root JSON.
    tool = json.loads(tool_raw.decode("utf-8"), object_pairs_hook=_no_duplicate_pairs)
    acceptance = _parse_json(acceptance_raw)
    _exact(tool["exit_code"], 0)
    _exact(_parse_json(tool["output"].encode("utf-8")), owned)
    _exact(owned["schema"], "local_intake_root_primitive_owned_run_v1")
    _exact(owned["source_mode"], "primitives")
    _exact(owned["actual_error"], None)
    _exact(owned["source_invocation_completed"], True)
    _exact(owned["no_child_process_launched_by_this_wrapper"], True)
    _exact(owned["observer_source_sha256"], _SOURCE_SHA)
    _exact(owned["vector_sha256"], _VECTOR_SHA)
    _exact(owned["artifact"]["bytes"], 12382)
    _exact(owned["artifact"]["sha256"], _RECEIPT_SHA)
    identity = owned["identity"]
    _exact(identity["pid"], 2552)
    _exact(identity["parent_pid"], 23516)
    _exact(identity["creation_utc"], "2026-10-15T08:56:48.6303710Z")
    _exact(identity["creation_managed_kind"], "Local")
    _integer(identity["creation_managed_ticks"], 1, _I64_MAX)
    assert type(identity["executable"]) is str and identity["executable"]
    assert type(identity["command"]) is str and identity["command"]
    # The tool wraps the registered text and trims its terminal newlines only.
    assert command.rstrip("\r\n") in identity["command"]
    assert identity["command"].startswith(f'"{identity["executable"]}" -Command "')
    for name in (
        "exception_aware_old441_and_new4_raw_pins_matched",
        "named_fixed_resource_source_pins_matched",
        "root_static_exe_pin_matched",
        "raw_old_freeze_container_pin_matched",
    ):
        _exact(owned[name], True)
    _exact(owned["pre_post_exact_registered_python_set"], 445)
    _exact(acceptance["schema"], "local_intake_root_primitives_acceptance_v1")
    _exact(acceptance["actual_tool_exit"], 0)
    _exact(acceptance["actual_root_pid"], identity["pid"])
    _exact(acceptance["actual_root_parent_pid"], identity["parent_pid"])
    _exact(acceptance["canonical_cases"], 29)
    _exact(acceptance["rejection_cases"], 26)
    _exact(acceptance["actual_clock_cases"], 9)
    _exact(acceptance["complete_case_sensitive_cohort"], 64)
    for name in (
        "exact_owned_command_executable_creation_parent",
        "owned_identity_absent_after_actual_tool_exit",
        "all_original_expected_actual_bytes_and_reasons_matched",
        "complete_canonical_receipt_ownhash_clock_schema_and28literalFalse_flags",
        "exception_aware_old441_new4_python_pins_and445set",
        "all_named_resources_source_and_rawfreeze_pins",
    ):
        _exact(acceptance[name], True)
    _exact(
        acceptance["report"],
        {
            "path": "logs/local_member_intake_proof_20261015_1/root_primitives_1.json",
            "bytes": 12382,
            "sha256": _RECEIPT_SHA,
        },
    )
    _exact(acceptance["source_sha256"], _SOURCE_SHA)
    _exact(receipt["observer_identity"]["raw_sha256"], acceptance["source_sha256"])
