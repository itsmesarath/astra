"""Independent S1 literals for the 2026-10-15 local-intake proof slice.

Only declared, invented packet metadata is represented here.  This module does
not import the implementation or generate expected values from its output.
"""

import hashlib
import json

HARD_END_UTC = "2026-10-15T14:59:08Z"
HARD_END_UNIX_NS = 1_792_076_348_000_000_000
REGISTRATION_SHA256 = "1" * 64
PROTOCOL_SHA256 = "2" * 64
ORACLE_SHA256 = "3" * 64

SAVED_ERROR_BOUNDARIES = (
    (-2_147_483_648, 2_147_483_648),
    (-1, 4_294_967_295),
    (0, 0),
    (1, 1),
    (2_147_483_647, 2_147_483_647),
)


def authority_flags_literal():
    """Return the full ordered independent literal, including every false."""
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


def packet_contract_literal():
    """Return a fresh complete seven-key contract from the declaration text."""
    return {
        "version": "local-member-intake-pure-packet-contract-v1",
        "hard_end_utc": HARD_END_UTC,
        "hard_end_unix_ns": HARD_END_UNIX_NS,
        "canonical_rules": {
            "encoding": "utf-8",
            "sorted_keys": True,
            "separators": [",", ":"],
            "ensure_ascii": True,
            "allow_nan": False,
            "duplicate_keys": "refuse",
            "integer_bool": "refuse",
            "canonical_input_equality": True,
        },
        "authority_flags": authority_flags_literal(),
        "controls": [
            {
                "case_id": "success",
                "nonce_hex": "00000000000000000000000000000001",
                "control": {
                    "kind": "emit_ok",
                    "amount": 0,
                    "literal_hex": "",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "packet_first_excess",
                "nonce_hex": "00000000000000000000000000000002",
                "control": {
                    "kind": "emit_ok",
                    "amount": 0,
                    "literal_hex": "",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "packet_wrong_pin",
                "nonce_hex": "00000000000000000000000000000003",
                "control": {
                    "kind": "emit_ok",
                    "amount": 0,
                    "literal_hex": "",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "unknown_control",
                "nonce_hex": "00000000000000000000000000000004",
                "control": {
                    "kind": "unknown",
                    "amount": 0,
                    "literal_hex": "",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "initialization_stall",
                "nonce_hex": "00000000000000000000000000000005",
                "control": {
                    "kind": "stall_before_dispatch",
                    "amount": 13_000,
                    "literal_hex": "",
                    "fault_site": "before_worker_dispatch",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "wall_stall",
                "nonce_hex": "00000000000000000000000000000006",
                "control": {
                    "kind": "stall_after_dispatch",
                    "amount": 13_000,
                    "literal_hex": "",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "cpu_limit",
                "nonce_hex": "00000000000000000000000000000007",
                "control": {
                    "kind": "burn_user_cpu",
                    "amount": 0,
                    "literal_hex": "",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "memory_limit",
                "nonce_hex": "00000000000000000000000000000008",
                "control": {
                    "kind": "allocate_commit",
                    "amount": 268_435_456,
                    "literal_hex": "",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "crash",
                "nonce_hex": "00000000000000000000000000000009",
                "control": {
                    "kind": "exit_nonzero",
                    "amount": 37,
                    "literal_hex": "",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "result_exact_limit",
                "nonce_hex": "0000000000000000000000000000000a",
                "control": {
                    "kind": "emit_registered_bytes",
                    "amount": 1_048_576,
                    "literal_hex": "",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "result_first_excess",
                "nonce_hex": "0000000000000000000000000000000b",
                "control": {
                    "kind": "emit_registered_bytes",
                    "amount": 1_048_577,
                    "literal_hex": "",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "diagnostic_exact_limit",
                "nonce_hex": "0000000000000000000000000000000c",
                "control": {
                    "kind": "emit_raw_bytes",
                    "amount": 4_194_304,
                    "literal_hex": "",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "diagnostic_first_excess",
                "nonce_hex": "0000000000000000000000000000000d",
                "control": {
                    "kind": "emit_raw_bytes",
                    "amount": 4_194_305,
                    "literal_hex": "",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "invalid_utf8",
                "nonce_hex": "0000000000000000000000000000000e",
                "control": {
                    "kind": "emit_raw_bytes",
                    "amount": 1,
                    "literal_hex": "ff",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "duplicate_key",
                "nonce_hex": "0000000000000000000000000000000f",
                "control": {
                    "kind": "emit_raw_bytes",
                    "amount": 13,
                    "literal_hex": "7b2278223a312c2278223a327d",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "trailing_json",
                "nonce_hex": "00000000000000000000000000000010",
                "control": {
                    "kind": "emit_raw_bytes",
                    "amount": 5,
                    "literal_hex": "7b7d207b7d",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "unexpected_stderr",
                "nonce_hex": "00000000000000000000000000000011",
                "control": {
                    "kind": "emit_stderr",
                    "amount": 1,
                    "literal_hex": "78",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "creation_refusal",
                "nonce_hex": "00000000000000000000000000000012",
                "control": {
                    "kind": "host_fault",
                    "amount": 0,
                    "literal_hex": "",
                    "fault_site": "before_create_process",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "suspended_identity_refusal",
                "nonce_hex": "00000000000000000000000000000013",
                "control": {
                    "kind": "host_fault",
                    "amount": 0,
                    "literal_hex": "",
                    "fault_site": "before_identity_comparison",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "suspended_membership_refusal",
                "nonce_hex": "00000000000000000000000000000014",
                "control": {
                    "kind": "host_fault",
                    "amount": 0,
                    "literal_hex": "",
                    "fault_site": "before_membership_comparison",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "resume_refusal",
                "nonce_hex": "00000000000000000000000000000015",
                "control": {
                    "kind": "host_fault",
                    "amount": 0,
                    "literal_hex": "",
                    "fault_site": "before_resume_thread",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "blocked_owned_pipe_read",
                "nonce_hex": "00000000000000000000000000000016",
                "control": {
                    "kind": "block_on_owned_pipe",
                    "amount": 1,
                    "literal_hex": "",
                    "fault_site": "none",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "close_refusal",
                "nonce_hex": "00000000000000000000000000000017",
                "control": {
                    "kind": "host_fault",
                    "amount": 0,
                    "literal_hex": "",
                    "fault_site": "after_stdout_read_close",
                },
                "policy_variant": "default_256_mib",
            },
            {
                "case_id": "memory_positive_control",
                "nonce_hex": "00000000000000000000000000000018",
                "control": {
                    "kind": "allocate_commit",
                    "amount": 268_435_456,
                    "literal_hex": "",
                    "fault_site": "none",
                },
                "policy_variant": "positive_512_mib",
            },
        ],
        "admission_order": [
            "raw_type",
            "packet_length",
            "external_context",
            "packet_pin",
            "packet_encoding",
            "packet_json",
            "packet_canonical",
            "packet_schema",
            "packet_context",
            "authority_flags",
            "packet_control",
        ],
    }


def packet_literal(
    case_id="success",
    *,
    registration_sha256=REGISTRATION_SHA256,
    protocol_sha256=PROTOCOL_SHA256,
    oracle_sha256=ORACLE_SHA256,
):
    """Build one complete invented base packet using only independent literals."""
    for row in packet_contract_literal()["controls"]:
        if row["case_id"] == case_id:
            return {
                "version": "local-member-intake-bootstrap-packet-v1",
                "operation": "bootstrap",
                "case_id": row["case_id"],
                "registration_sha256": registration_sha256,
                "protocol_sha256": protocol_sha256,
                "oracle_sha256": oracle_sha256,
                "hard_end_utc": HARD_END_UTC,
                "nonce_hex": row["nonce_hex"],
                "control": row["control"],
                "authority_flags": authority_flags_literal(),
            }
    raise KeyError(case_id)


def canonical_bytes(value):
    """Implement the declared byte rule independently of production helpers."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def raw_sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def admission_kwargs(
    raw,
    *,
    expected_packet_sha256=None,
    registration_sha256=REGISTRATION_SHA256,
    protocol_sha256=PROTOCOL_SHA256,
    oracle_sha256=ORACLE_SHA256,
    now_unix_ns=HARD_END_UNIX_NS - 1,
):
    """Supply independent external metadata, allowing an explicit held raw pin."""
    return {
        "expected_packet_sha256": (
            raw_sha256(raw) if expected_packet_sha256 is None else expected_packet_sha256
        ),
        "registration_sha256": registration_sha256,
        "protocol_sha256": protocol_sha256,
        "oracle_sha256": oracle_sha256,
        "now_unix_ns": now_unix_ns,
    }


def packet_first_excess_bytes():
    """Return the complete 8193-byte canonical rejected-input declaration."""
    value = packet_literal("packet_first_excess")
    value["padding"] = ""
    value["padding"] = "a" * (8193 - len(canonical_bytes(value)))
    return canonical_bytes(value)


def packet_wrong_pin_pair():
    """Return the entire expected base and the exactly one-byte changed input."""
    base = canonical_bytes(packet_literal("packet_wrong_pin"))
    return base, base.replace(
        b'"nonce_hex":"00000000000000000000000000000003"',
        b'"nonce_hex":"00000000000000000000000000000004"',
        1,
    )
