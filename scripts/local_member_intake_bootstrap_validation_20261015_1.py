"""Pure S3 validation of complete invented rejected-input/preflight metadata.

This module performs no file, process, native, or runtime-identity observation.
Caller-supplied external expectations are not authentication. Created attempts,
worker results, and root transport receipts are deliberately outside this slice.
"""

import hashlib
import json
import re

__all__ = ("ReceiptRefusal", "verify_rejected_input", "verify_preflight_receipt")

_PROTOCOL_SHA256 = "21ca358bb60cd945719b48f97c507c8c246d28f803620a142b458259bd1408bf"
_HARD_END = "2026-10-15T14:59:08Z"
_U64_MAX = 18446744073709551615
_SHA = re.compile(r"[0-9a-f]{64}", re.ASCII)
_HEX = re.compile(r"(?:[0-9a-f]{2})*", re.ASCII)
_CASES = {
    "packet_first_excess": ("00000000000000000000000000000002", "packet_length"),
    "packet_wrong_pin": ("00000000000000000000000000000003", "packet_pin"),
    "unknown_control": ("00000000000000000000000000000004", "packet_control"),
}
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
_RUNTIME_ROLES = (
    "interpreter",
    "worker",
    "host",
    "protocol",
    "oracle",
    "kernel32",
    "kernelbase",
    "ntdll",
    "registered_dependency",
)
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
_ATTEMPT_KEYS = (
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
_LIFECYCLE_KEYS = ("ordinal", "event", "monotonic_ns", "related_api_ordinals")
_POLICY = {
    "packet_bytes_max": 8192,
    "command_utf16_units_max": 24576,
    "environment_utf16_units_max": 8192,
    "active_processes": 1,
    "process_memory_bytes": 268435456,
    "user_cpu_100ns": 50000000,
    "work_ms": 12000,
    "teardown_ms": 3000,
    "poll_ms": 20,
    "result_bytes_max": 1048576,
    "diagnostic_bytes_max": 4194312,
    "semantic_diagnostic_bytes_max": 4194304,
    "ready_prefix_bytes": 8,
    "go_bytes": 48,
    "receipt_bytes_max": 67108864,
    "buffer_occurrences_raw_bytes_max": 12582912,
    "other_hex_occurrences_raw_bytes_max": 2097152,
    "other_canonical_bytes_max": 8388608,
    "api_rows_max": 4096,
    "lifecycle_rows_max": 4096,
    "parent_handle_rows_max": 16,
    "worker_handle_rows_max": 16,
    "hard_end_utc": _HARD_END,
}


class ReceiptRefusal(ValueError):
    """An expected metadata refusal, distinct from unexpected implementation faults."""

    __slots__ = ("_reason",)

    def __init__(self, reason):
        super().__init__(reason)
        self._reason = reason

    @property
    def reason(self):
        return self._reason


def _refuse(reason):
    raise ReceiptRefusal(reason)


def _require(condition, reason):
    if not condition:
        _refuse(reason)


def _same(value, expected):
    if type(value) is not type(expected):
        return False
    if type(expected) is dict:
        return value.keys() == expected.keys() and all(
            _same(value[key], item) for key, item in expected.items()
        )
    if type(expected) is list:
        return len(value) == len(expected) and all(
            _same(item, other) for item, other in zip(value, expected, strict=True)
        )
    return value == expected


def _record(value, keys, reason="query_value"):
    _require(type(value) is dict, reason)
    _require(len(value) == len(keys) and value.keys() == set(keys), reason)


def _sha(value):
    return type(value) is str and _SHA.fullmatch(value) is not None


def _integer(value, lower, upper, reason="query_value"):
    _require(type(value) is int and lower <= value <= upper, reason)


def _canonical(value):
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, RecursionError) as error:
        raise ReceiptRefusal("transport") from error


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value, "duplicate_key")
        value[key] = item
    return value


def _noninteger(token):
    _refuse("transport")


def _parse(raw):
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ReceiptRefusal("utf8") from error
    _require(not text.startswith("\ufeff"), "utf8")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_float=_noninteger,
            parse_constant=_noninteger,
        )
    except ReceiptRefusal:
        raise
    except json.JSONDecodeError as error:
        reason = "trailing_json" if error.msg == "Extra data" else "transport"
        raise ReceiptRefusal(reason) from error
    except (ValueError, RecursionError) as error:
        raise ReceiptRefusal("transport") from error
    _require(_canonical(value) == raw, "transport")
    return value


def _flags():
    return [[name, False] for name in _AUTHORITY_NAMES]


def _packet(case_id, registration_sha256, oracle_sha256):
    return {
        "version": "local-member-intake-bootstrap-packet-v1",
        "operation": "bootstrap",
        "case_id": case_id,
        "registration_sha256": registration_sha256,
        "protocol_sha256": _PROTOCOL_SHA256,
        "oracle_sha256": oracle_sha256,
        "hard_end_utc": _HARD_END,
        "nonce_hex": _CASES[case_id][0],
        "control": {
            "kind": "unknown" if case_id == "unknown_control" else "emit_ok",
            "amount": 0,
            "literal_hex": "",
            "fault_site": "none",
        },
        "authority_flags": _flags(),
    }


def _runtime_expectations(runtime_pins):
    _require(type(runtime_pins) is list and 1 <= len(runtime_pins) <= 128, "packet_context")
    associations = set()
    physical = {}
    copied = []
    for row in runtime_pins:
        _record(row, ("role", "path", "byte_length", "sha256"), "packet_context")
        _require(type(row["role"]) is str and row["role"] in _RUNTIME_ROLES, "packet_context")
        _require(type(row["path"]) is str and len(row["path"]) <= 8388608, "packet_context")
        _integer(row["byte_length"], 1, _U64_MAX, "packet_context")
        _require(_sha(row["sha256"]), "packet_context")
        association = (row["role"], row["path"])
        _require(association not in associations, "packet_context")
        associations.add(association)
        identity = (row["byte_length"], row["sha256"])
        if row["path"] in physical:
            _require(physical[row["path"]] == identity, "packet_context")
        physical[row["path"]] = identity
        copied.append(dict(row))
    return copied


def _bindings(
    submitted_packet_raw,
    expected_packet_raw,
    expected_packet_sha256,
    case_id,
    registration_sha256,
    oracle_sha256,
    runtime_pins=None,
):
    _require(type(submitted_packet_raw) is bytes, "packet_context")
    _require(type(case_id) is str and case_id in _CASES, "packet_context")
    _require(
        all(
            _sha(item)
            for item in (
                expected_packet_sha256,
                registration_sha256,
                oracle_sha256,
            )
        ),
        "packet_context",
    )
    packet = _packet(case_id, registration_sha256, oracle_sha256)
    base = _canonical(packet)
    if case_id == "packet_first_excess":
        _require(expected_packet_raw is None, "packet_context")
        packet["padding"] = ""
        padding_length = 8193 - len(_canonical(packet))
        _require(padding_length >= 0, "packet_context")
        packet["padding"] = "a" * padding_length
        submitted = _canonical(packet)
        expected_pin = _digest(submitted)
    elif case_id == "packet_wrong_pin":
        _require(
            type(expected_packet_raw) is bytes and expected_packet_raw == base, "packet_context"
        )
        old = b'"nonce_hex":"00000000000000000000000000000003"'
        new = b'"nonce_hex":"00000000000000000000000000000004"'
        _require(base.count(old) == 1, "packet_context")
        submitted = base.replace(old, new, 1)
        expected_pin = _digest(base)
    else:
        _require(
            type(expected_packet_raw) is bytes and expected_packet_raw == base, "packet_context"
        )
        submitted = base
        expected_pin = _digest(base)
    _require(submitted_packet_raw == submitted, "packet_context")
    _require(expected_packet_sha256 == expected_pin, "packet_context")
    value = {
        "case_id": case_id,
        "registration_sha256": registration_sha256,
        "oracle_sha256": oracle_sha256,
        "expected_packet_raw": expected_packet_raw,
        "expected_packet_sha256": expected_packet_sha256,
        "submitted_packet_raw": submitted_packet_raw,
        "submitted_raw_sha256": _digest(submitted_packet_raw),
        "first_reason": _CASES[case_id][1],
    }
    if runtime_pins is not None:
        value["runtime_pins"] = _runtime_expectations(runtime_pins)
    return value


def _outer(raw, maximum, bindings, keys, version):
    value = _parse(raw)
    _record(value, keys)
    _require(type(value["version"]) is str and value["version"] == version, "query_value")
    _require(type(value["case_id"]) is str, "query_value")
    _require(_sha(value["registration_sha256"]) and _sha(value["oracle_sha256"]), "query_value")
    for key in ("case_id", "registration_sha256", "oracle_sha256"):
        _require(value[key] == bindings[key], "packet_context")
    _require(len(raw) <= maximum, "budget")
    return value


def _verify_ownhash(value, key):
    _require(_sha(value[key]), "transport")
    body = {name: item for name, item in value.items() if name != key}
    _require(_digest(_canonical(body)) == value[key], "transport")


def _hex(value, maximum):
    _require(type(value) is str and _HEX.fullmatch(value) is not None, "query_value")
    _require(len(value) <= 2 * maximum, "budget")
    return bytes.fromhex(value)


def _array(value, count, maximum):
    _require(type(value) is list, "query_value")
    _require(len(value) <= maximum, "budget")
    _require(len(value) == count, "query_count")


def _validate_rejected_body(value, bindings):
    raw_expected = bindings["expected_packet_raw"]
    if raw_expected is None:
        _require(value["expected_raw_hex"] is None, "query_value")
    else:
        _require(_hex(value["expected_raw_hex"], 8192) == raw_expected, "packet_context")
    _integer(value["submitted_raw_byte_length"], 0, 4294967295)
    submitted = _hex(value["submitted_raw_hex"], 8193)
    _require(submitted == bindings["submitted_packet_raw"], "packet_context")
    _require(value["submitted_raw_byte_length"] == len(submitted), "packet_context")
    _require(
        type(value["first_reason"]) is str and value["first_reason"] == bindings["first_reason"],
        "query_value",
    )
    _require(value["admitted_packet"] is None, "query_value")
    _require(value["native_setup_attempted"] is False, "query_value")


def _validate_creation(value):
    _record(value, _CREATION_KEYS)
    _require(value["attempted"] is False, "query_value")
    for key in _CREATION_KEYS[1:19]:
        _require(value[key] is None, "query_value")
    for key, maximum in (
        ("initialization", 16),
        ("binding_initialization", 128),
        ("module_observations", 6),
    ):
        _array(value[key], 0, maximum)
    _record(value["identity_transport"], _TRANSPORT_KEYS)
    for item in value["identity_transport"].values():
        _require(item is None, "query_value")


def _validate_lifecycle(value):
    _array(value, 3, 4096)
    previous = 0
    for ordinal, event in enumerate(("preflight", "failure_selected", "finished")):
        row = value[ordinal]
        _record(row, _LIFECYCLE_KEYS)
        _integer(row["ordinal"], 0, 4294967295)
        _require(row["ordinal"] == ordinal, "query_value")
        _require(type(row["event"]) is str and row["event"] == event, "query_value")
        _integer(row["monotonic_ns"], 0, _U64_MAX, "timestamp")
        _require(row["monotonic_ns"] >= previous, "timestamp")
        previous = row["monotonic_ns"]
        _array(row["related_api_ordinals"], 0, 4096)


def _validate_terminal(value, reason):
    _record(value, _TERMINAL_KEYS)
    fixed = {
        "outcome": "preflight_refusal",
        "failure_stage": "preflight",
        "failure_code": reason,
        "termination_requested": False,
        "termination_return": None,
        "wait_result_u32": None,
        "exit_code_u32": None,
        "exit_filetime_u64": None,
        "kernel_time_100ns_u64": None,
        "user_time_100ns_u64": None,
        "final_job_empty": None,
        "parent_closes": [],
        "cleanup_complete": None,
        "acceptance": "accepted_control",
    }
    _array(value["parent_closes"], 0, 16)
    _require(_same(value, fixed), "query_value")


def _validate_preflight_body(value, bindings):
    # This pure branch has no stream/buffer/result hex categories: its entire
    # canonical body, excluding only its own digest, is metadata category M.
    body = {key: item for key, item in value.items() if key != "receipt_sha256"}
    _require(len(_canonical(body)) <= 8388608, "budget")
    _record(value["declared_policy"], tuple(_POLICY))
    _require(_same(value["declared_policy"], _POLICY), "query_value")
    _require(value["parent_identity"] is None, "query_value")
    _validate_creation(value["creation"])
    _array(value["job_observations"], 0, 4096)
    _array(value["api_trace"], 0, 4096)
    _validate_lifecycle(value["lifecycle"])
    for key in ("stdout", "stderr", "result"):
        _require(value[key] is None, "query_value")
    _validate_terminal(value["terminal"], bindings["first_reason"])


def verify_rejected_input(
    raw: bytes,
    *,
    submitted_packet_raw: bytes,
    expected_packet_raw: bytes | None,
    expected_packet_sha256: str,
    case_id: str,
    registration_sha256: str,
    oracle_sha256: str,
) -> dict:
    """Verify one entire three-control rejected-input record against external pins."""
    _require(type(raw) is bytes, "transport")
    _require(len(raw) <= 65536, "budget")
    bindings = _bindings(
        submitted_packet_raw,
        expected_packet_raw,
        expected_packet_sha256,
        case_id,
        registration_sha256,
        oracle_sha256,
    )
    value = _outer(
        raw, 65536, bindings, _REJECTED_KEYS, "local-member-intake-bootstrap-rejected-input-v1"
    )
    for key in ("expected_packet_sha256", "submitted_raw_sha256"):
        _require(_sha(value[key]), "query_value")
        _require(value[key] == bindings[key], "packet_context")
    _verify_ownhash(value, "rejection_sha256")
    _validate_rejected_body(value, bindings)
    return value


def verify_preflight_receipt(
    raw: bytes,
    *,
    submitted_packet_raw: bytes,
    expected_packet_raw: bytes | None,
    expected_packet_sha256: str,
    case_id: str,
    registration_sha256: str,
    oracle_sha256: str,
    runtime_pins: list[dict],
) -> dict:
    """Verify a pure preflight refusal, never a created/native attempt receipt."""
    _require(type(raw) is bytes, "transport")
    _require(len(raw) <= 67108864, "budget")
    _require(runtime_pins is not None, "packet_context")
    bindings = _bindings(
        submitted_packet_raw,
        expected_packet_raw,
        expected_packet_sha256,
        case_id,
        registration_sha256,
        oracle_sha256,
        runtime_pins,
    )
    value = _outer(
        raw, 67108864, bindings, _ATTEMPT_KEYS, "local-member-intake-bootstrap-attempt-v2"
    )
    _require(_sha(value["packet_sha256"]), "query_value")
    _require(value["packet_sha256"] == bindings["submitted_raw_sha256"], "packet_context")
    _require(value["packet"] is None, "packet_context")
    _require(_same(value["runtime_pins"], bindings["runtime_pins"]), "packet_context")
    _require(_same(value["authority_flags"], _flags()), "authority_flags")
    _verify_ownhash(value, "receipt_sha256")
    _validate_preflight_body(value, bindings)
    return value
