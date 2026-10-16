"""Independent S3 literals for three invented, native-free refusal controls.

The fixed bound declaration, not the implementation or its serializers, is the
authority for these expected records. No file, process, Windows API, production
module, protocol resource, or actual attempt output is read by this helper.

The ``a``/``b`` registration and oracle identities and the runtime paths/hashes
below are explicitly invented external test-registration literals. They are not
claims that a registration, executable, script, or native identity was observed.
The protocol canonical identity alone is the accepted complete P identity. The
three lifecycle numbers are registered injected clocks, not runtime readings.
"""

import hashlib
import json
from copy import deepcopy

NEGATIVE_CASE_IDS = (
    "packet_first_excess",
    "packet_wrong_pin",
    "unknown_control",
)

HARD_END_UTC = "2026-10-15T14:59:08Z"
PROTOCOL_CANONICAL_SHA256 = "21ca358bb60cd945719b48f97c507c8c246d28f803620a142b458259bd1408bf"
FIXTURE_REGISTRATION_SHA256 = "a" * 64
FIXTURE_ORACLE_SHA256 = "b" * 64


def canonical_bytes(value: object) -> bytes:
    """Encode complete independent JSON with the registered canonical choices."""
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def raw_sha256(raw: bytes) -> str:
    """Hash all supplied bytes, without a production hash/serializer helper."""
    return hashlib.sha256(raw).hexdigest()


def with_own_hash(record: dict[str, object], field: str) -> dict[str, object]:
    """Return a fresh complete record hashing every field except its own hash."""
    result = deepcopy(record)
    result.pop(field, None)
    result[field] = raw_sha256(canonical_bytes(result))
    return result


def authority_flags_literal() -> list[list[object]]:
    """The complete ordered 28 literal-False authority pairs from the declaration."""
    return [
        ["source_authenticated", False],
        ["collection_receipt_authenticated", False],
        ["native_runtime_authenticated", False],
        ["native_abi_authenticated", False],
        ["native_wire_authenticated", False],
        ["native_header_authenticated", False],
        ["native_eof_authenticated", False],
        ["feed_authenticated", False],
        ["calendar_authenticated", False],
        ["historical_read_authorized", False],
        ["historical_validation_authorized", False],
        ["book_acceptance_authorized", False],
        ["event_acceptance_authorized", False],
        ["feature_acceptance_authorized", False],
        ["account_authorized", False],
        ["funding_authorized", False],
        ["receipt_authorized", False],
        ["cash_authorized", False],
        ["margin_authorized", False],
        ["risk_authorized", False],
        ["storage_authorized", False],
        ["resume_authorized", False],
        ["execution_authorized", False],
        ["trading_authorized", False],
        ["training_authorized", False],
        ["scoring_authorized", False],
        ["independent_validation_authorized", False],
        ["promotion_authorized", False],
    ]


def runtime_pins_literal() -> list[dict[str, object]]:
    """Fresh, complete four-field metadata; none of these paths is opened."""
    return [
        {
            "role": "interpreter",
            "path": r"C:\__invented_intake_s3__\python.exe",
            "byte_length": 4096,
            "sha256": "c" * 64,
        },
        {
            "role": "host",
            "path": r"C:\__invented_intake_s3__\host.py",
            "byte_length": 8192,
            "sha256": "d" * 64,
        },
        {
            "role": "worker",
            "path": r"C:\__invented_intake_s3__\worker.py",
            "byte_length": 16384,
            "sha256": "e" * 64,
        },
    ]


def _case_spec(case_id: str) -> dict[str, object]:
    """Three independently written rows, not discovered from production/P."""
    return {
        "packet_first_excess": {
            "nonce_hex": "00000000000000000000000000000002",
            "control": {
                "kind": "emit_ok",
                "amount": 0,
                "literal_hex": "",
                "fault_site": "none",
            },
            "first_reason": "packet_length",
        },
        "packet_wrong_pin": {
            "nonce_hex": "00000000000000000000000000000003",
            "control": {
                "kind": "emit_ok",
                "amount": 0,
                "literal_hex": "",
                "fault_site": "none",
            },
            "first_reason": "packet_pin",
        },
        "unknown_control": {
            "nonce_hex": "00000000000000000000000000000004",
            "control": {
                "kind": "unknown",
                "amount": 0,
                "literal_hex": "",
                "fault_site": "none",
            },
            "first_reason": "packet_control",
        },
    }[case_id]


def packet_literal(case_id: str) -> dict[str, object]:
    """Complete original ten-field packet, before the registered raw mutation."""
    row = _case_spec(case_id)
    return {
        "version": "local-member-intake-bootstrap-packet-v1",
        "operation": "bootstrap",
        "case_id": case_id,
        "registration_sha256": FIXTURE_REGISTRATION_SHA256,
        "protocol_sha256": PROTOCOL_CANONICAL_SHA256,
        "oracle_sha256": FIXTURE_ORACLE_SHA256,
        "hard_end_utc": HARD_END_UTC,
        "nonce_hex": row["nonce_hex"],
        "control": row["control"],
        "authority_flags": authority_flags_literal(),
    }


def packet_inputs(case_id: str) -> dict[str, object]:
    """Fresh complete external kwargs common to both registered public APIs.

    Only first-excess has no original expected body. Wrong-pin retains the entire
    nonce-3 original and the entire same-length nonce-4 submission. Unknown-kind
    retains the complete same canonical, correctly pinned body on both sides.
    """
    original = canonical_bytes(packet_literal(case_id))
    if case_id == "packet_first_excess":
        padded_packet = packet_literal(case_id)
        padded_packet["padding"] = ""
        padding_length = 8193 - len(canonical_bytes(padded_packet))
        if padding_length < 0:
            raise AssertionError("Independent first-excess recipe has negative padding")
        padded_packet["padding"] = "a" * padding_length
        submitted = canonical_bytes(padded_packet)
        if len(submitted) != 8193:
            raise AssertionError("Independent first-excess recipe is not exactly8193")
        expected: bytes | None = None
        expected_pin = raw_sha256(submitted)
    elif case_id == "packet_wrong_pin":
        needle = b'"nonce_hex":"00000000000000000000000000000003"'
        replacement = b'"nonce_hex":"00000000000000000000000000000004"'
        if original.count(needle) != 1:
            raise AssertionError("Independent wrong-pin recipe has ambiguous nonce")
        submitted = original.replace(needle, replacement, 1)
        expected = original
        expected_pin = raw_sha256(original)
    else:
        # _case_spec already refuses every ID outside the three fixed rows.
        submitted = original
        expected = original
        expected_pin = raw_sha256(original)
    return {
        "submitted_packet_raw": submitted,
        "expected_packet_raw": expected,
        "expected_packet_sha256": expected_pin,
        "case_id": case_id,
        "registration_sha256": FIXTURE_REGISTRATION_SHA256,
        "oracle_sha256": FIXTURE_ORACLE_SHA256,
    }


def rejected_fixture(case_id: str) -> dict[str, object]:
    """Complete RejectedInputEvidence13; every submitted byte remains present."""
    inputs = packet_inputs(case_id)
    submitted = inputs["submitted_packet_raw"]
    expected = inputs["expected_packet_raw"]
    if not isinstance(submitted, bytes):
        raise AssertionError("Independent submitted literal must be bytes")
    if expected is not None and not isinstance(expected, bytes):
        raise AssertionError("Independent original literal must be bytes or None")
    body = {
        "version": "local-member-intake-bootstrap-rejected-input-v1",
        "case_id": case_id,
        "registration_sha256": FIXTURE_REGISTRATION_SHA256,
        "oracle_sha256": FIXTURE_ORACLE_SHA256,
        "expected_raw_hex": None if expected is None else expected.hex(),
        "expected_packet_sha256": inputs["expected_packet_sha256"],
        "submitted_raw_hex": submitted.hex(),
        "submitted_raw_byte_length": len(submitted),
        "submitted_raw_sha256": raw_sha256(submitted),
        "first_reason": _case_spec(case_id)["first_reason"],
        "admitted_packet": None,
        "native_setup_attempted": False,
    }
    return with_own_hash(body, "rejection_sha256")


def declared_policy_literal() -> dict[str, object]:
    """All23 fixed default-policy fields; no caller override or native fact."""
    return {
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
        "hard_end_utc": HARD_END_UTC,
    }


def identity_transport_literal() -> dict[str, object]:
    """All seven unentered transport fields are null, never an absent record."""
    return {
        "request": None,
        "ack": None,
        "ready_hex": None,
        "ready_read_api_ordinals": None,
        "go_hex": None,
        "go_write_api_ordinals": None,
        "child_stdin_parent_closes": None,
    }


def creation_literal() -> dict[str, object]:
    """Complete23-key preflight state: no attempted native initialization."""
    return {
        "attempted": False,
        "create_bool_i32": None,
        "win32_error_u32": None,
        "creation_flags_u32": None,
        "command_utf16le_hex": None,
        "environment_utf16le_hex": None,
        "inherited_handles_u64": None,
        "job_attribute_u64": None,
        "handle_attribute_u64": None,
        "process_handle_u64": None,
        "thread_handle_u64": None,
        "child_pid": None,
        "child_tid": None,
        "child_creation_filetime_u64": None,
        "observed_image_utf16le_hex": None,
        "observed_parent_pid": None,
        "parent_observation_method": None,
        "cim_observations": None,
        "resume_count_u32": None,
        "initialization": [],
        "binding_initialization": [],
        "module_observations": [],
        "identity_transport": identity_transport_literal(),
    }


def terminal_literal(case_id: str) -> dict[str, object]:
    """Complete14-key terminal for an admitted pure negative-control receipt."""
    return {
        "outcome": "preflight_refusal",
        "failure_stage": "preflight",
        "failure_code": _case_spec(case_id)["first_reason"],
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


def preflight_fixture(case_id: str) -> dict[str, object]:
    """Complete BootstrapAttemptReceipt19, with injected lifecycle0,1,2 only."""
    inputs = packet_inputs(case_id)
    submitted = inputs["submitted_packet_raw"]
    if not isinstance(submitted, bytes):
        raise AssertionError("Independent submitted literal must be bytes")
    body = {
        "version": "local-member-intake-bootstrap-attempt-v2",
        "case_id": case_id,
        "packet": None,
        "packet_sha256": raw_sha256(submitted),
        "registration_sha256": FIXTURE_REGISTRATION_SHA256,
        "oracle_sha256": FIXTURE_ORACLE_SHA256,
        "declared_policy": declared_policy_literal(),
        "runtime_pins": runtime_pins_literal(),
        "parent_identity": None,
        "creation": creation_literal(),
        "job_observations": [],
        "api_trace": [],
        "lifecycle": [
            {
                "ordinal": 0,
                "event": "preflight",
                "monotonic_ns": 0,
                "related_api_ordinals": [],
            },
            {
                "ordinal": 1,
                "event": "failure_selected",
                "monotonic_ns": 1,
                "related_api_ordinals": [],
            },
            {
                "ordinal": 2,
                "event": "finished",
                "monotonic_ns": 2,
                "related_api_ordinals": [],
            },
        ],
        "stdout": None,
        "stderr": None,
        "result": None,
        "terminal": terminal_literal(case_id),
        "authority_flags": authority_flags_literal(),
    }
    return with_own_hash(body, "receipt_sha256")
