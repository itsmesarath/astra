"""Pure packet admission for the registered 2026-10-15 intake proof slice.

This module performs no caller-file, process, ctypes or native proof operation.
Its literals implement the independently saved S1 registration and declarations;
they are not the later complete native bootstrap protocol resource.
"""

import hashlib
import json
import re

_HARD_END_UTC = "2026-10-15T14:59:08Z"
_HARD_END_UNIX_NS = 1792076348000000000
_PACKET_VERSION = "local-member-intake-bootstrap-packet-v1"
_CONTRACT_VERSION = "local-member-intake-pure-packet-contract-v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_U64_MAX = 18446744073709551615
_I32_MIN = -2147483648
_I32_MAX = 2147483647
_INFINITY = float("inf")

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

# ID, nonce, kind, amount, literal hex, fault site, policy variant.
_CONTROL_ROWS = (
    (
        "success",
        "00000000000000000000000000000001",
        "emit_ok",
        0,
        "",
        "none",
        "default_256_mib",
    ),
    (
        "packet_first_excess",
        "00000000000000000000000000000002",
        "emit_ok",
        0,
        "",
        "none",
        "default_256_mib",
    ),
    (
        "packet_wrong_pin",
        "00000000000000000000000000000003",
        "emit_ok",
        0,
        "",
        "none",
        "default_256_mib",
    ),
    (
        "unknown_control",
        "00000000000000000000000000000004",
        "unknown",
        0,
        "",
        "none",
        "default_256_mib",
    ),
    (
        "initialization_stall",
        "00000000000000000000000000000005",
        "stall_before_dispatch",
        13000,
        "",
        "before_worker_dispatch",
        "default_256_mib",
    ),
    (
        "wall_stall",
        "00000000000000000000000000000006",
        "stall_after_dispatch",
        13000,
        "",
        "none",
        "default_256_mib",
    ),
    (
        "cpu_limit",
        "00000000000000000000000000000007",
        "burn_user_cpu",
        0,
        "",
        "none",
        "default_256_mib",
    ),
    (
        "memory_limit",
        "00000000000000000000000000000008",
        "allocate_commit",
        268435456,
        "",
        "none",
        "default_256_mib",
    ),
    (
        "crash",
        "00000000000000000000000000000009",
        "exit_nonzero",
        37,
        "",
        "none",
        "default_256_mib",
    ),
    (
        "result_exact_limit",
        "0000000000000000000000000000000a",
        "emit_registered_bytes",
        1048576,
        "",
        "none",
        "default_256_mib",
    ),
    (
        "result_first_excess",
        "0000000000000000000000000000000b",
        "emit_registered_bytes",
        1048577,
        "",
        "none",
        "default_256_mib",
    ),
    (
        "diagnostic_exact_limit",
        "0000000000000000000000000000000c",
        "emit_raw_bytes",
        4194304,
        "",
        "none",
        "default_256_mib",
    ),
    (
        "diagnostic_first_excess",
        "0000000000000000000000000000000d",
        "emit_raw_bytes",
        4194305,
        "",
        "none",
        "default_256_mib",
    ),
    (
        "invalid_utf8",
        "0000000000000000000000000000000e",
        "emit_raw_bytes",
        1,
        "ff",
        "none",
        "default_256_mib",
    ),
    (
        "duplicate_key",
        "0000000000000000000000000000000f",
        "emit_raw_bytes",
        13,
        "7b2278223a312c2278223a327d",
        "none",
        "default_256_mib",
    ),
    (
        "trailing_json",
        "00000000000000000000000000000010",
        "emit_raw_bytes",
        5,
        "7b7d207b7d",
        "none",
        "default_256_mib",
    ),
    (
        "unexpected_stderr",
        "00000000000000000000000000000011",
        "emit_stderr",
        1,
        "78",
        "none",
        "default_256_mib",
    ),
    (
        "creation_refusal",
        "00000000000000000000000000000012",
        "host_fault",
        0,
        "",
        "before_create_process",
        "default_256_mib",
    ),
    (
        "suspended_identity_refusal",
        "00000000000000000000000000000013",
        "host_fault",
        0,
        "",
        "before_identity_comparison",
        "default_256_mib",
    ),
    (
        "suspended_membership_refusal",
        "00000000000000000000000000000014",
        "host_fault",
        0,
        "",
        "before_membership_comparison",
        "default_256_mib",
    ),
    (
        "resume_refusal",
        "00000000000000000000000000000015",
        "host_fault",
        0,
        "",
        "before_resume_thread",
        "default_256_mib",
    ),
    (
        "blocked_owned_pipe_read",
        "00000000000000000000000000000016",
        "block_on_owned_pipe",
        1,
        "",
        "none",
        "default_256_mib",
    ),
    (
        "close_refusal",
        "00000000000000000000000000000017",
        "host_fault",
        0,
        "",
        "after_stdout_read_close",
        "default_256_mib",
    ),
    (
        "memory_positive_control",
        "00000000000000000000000000000018",
        "allocate_commit",
        268435456,
        "",
        "none",
        "positive_512_mib",
    ),
)

_PACKET_KEYS = frozenset(
    (
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
)
_CONTROL_KEYS = frozenset(("kind", "amount", "literal_hex", "fault_site"))
_STRING_FIELDS = (
    "version",
    "operation",
    "case_id",
    "registration_sha256",
    "protocol_sha256",
    "oracle_sha256",
    "hard_end_utc",
    "nonce_hex",
)
_REFUSAL_REASONS = frozenset(
    (
        "packet_type",
        "packet_length",
        "packet_context",
        "packet_pin",
        "packet_encoding",
        "packet_json",
        "packet_canonical",
        "packet_schema",
        "authority_flags",
        "packet_control",
        "saved_error",
    )
)


class BootstrapRefusal(ValueError):
    """A declared validation refusal with a read-only public reason."""

    __slots__ = ("_reason",)

    def __init__(self, reason):
        if type(reason) is not str:
            raise TypeError("A bootstrap refusal reason must be an exact string")
        if reason not in _REFUSAL_REASONS:
            raise ValueError("Unknown bootstrap refusal reason")
        self._reason = reason
        super().__init__(reason)

    @property
    def reason(self):
        return self._reason


def packet_contract():
    """Return a fresh complete S1 contract, including rejected-input rows."""
    return {
        "version": _CONTRACT_VERSION,
        "hard_end_utc": _HARD_END_UTC,
        "hard_end_unix_ns": _HARD_END_UNIX_NS,
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
        "authority_flags": [[name, False] for name in _AUTHORITY_NAMES],
        "controls": [
            {
                "case_id": row[0],
                "nonce_hex": row[1],
                "control": {
                    "kind": row[2],
                    "amount": row[3],
                    "literal_hex": row[4],
                    "fault_site": row[5],
                },
                "policy_variant": row[6],
            }
            for row in _CONTROL_ROWS
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


def _is_sha256(value):
    return type(value) is str and _SHA256.fullmatch(value) is not None


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BootstrapRefusal("packet_json")
        result[key] = value
    return result


def _reject_nonfinite(_value):
    raise BootstrapRefusal("packet_json")


def _finite_float(value):
    result = float(value)
    if result != result or result == _INFINITY or result == -_INFINITY:
        raise BootstrapRefusal("packet_json")
    return result


def _check_authorities(flags):
    if len(flags) != len(_AUTHORITY_NAMES):
        raise BootstrapRefusal("authority_flags")
    for row, name in zip(flags, _AUTHORITY_NAMES, strict=True):
        if (
            type(row) is not list
            or len(row) != 2
            or type(row[0]) is not str
            or row[0] != name
            or row[1] is not False
        ):
            raise BootstrapRefusal("authority_flags")


def _check_control(packet):
    row = next((item for item in _CONTROL_ROWS if item[0] == packet["case_id"]), None)
    if row is None or row[2] == "unknown":
        raise BootstrapRefusal("packet_control")
    control = packet["control"]
    if (
        packet["nonce_hex"] != row[1]
        or set(control) != _CONTROL_KEYS
        or type(control["kind"]) is not str
        or type(control["amount"]) is not int
        or type(control["literal_hex"]) is not str
        or type(control["fault_site"]) is not str
        or control["kind"] != row[2]
        or control["amount"] != row[3]
        or control["literal_hex"] != row[4]
        or control["fault_site"] != row[5]
    ):
        raise BootstrapRefusal("packet_control")


def admit_packet(
    raw,
    *,
    expected_packet_sha256,
    registration_sha256,
    protocol_sha256,
    oracle_sha256,
    now_unix_ns,
):
    """Admit one complete canonical S1 packet in the registered phase order."""
    if type(raw) is not bytes:
        raise BootstrapRefusal("packet_type")
    if not 1 <= len(raw) <= 8192:
        raise BootstrapRefusal("packet_length")
    if (
        not all(
            _is_sha256(value)
            for value in (
                expected_packet_sha256,
                registration_sha256,
                protocol_sha256,
                oracle_sha256,
            )
        )
        or type(now_unix_ns) is not int
        or not 0 <= now_unix_ns <= _U64_MAX
        or now_unix_ns >= _HARD_END_UNIX_NS
    ):
        raise BootstrapRefusal("packet_context")
    if hashlib.sha256(raw).hexdigest() != expected_packet_sha256:
        raise BootstrapRefusal("packet_pin")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise BootstrapRefusal("packet_encoding") from None
    if text.startswith("\ufeff"):
        raise BootstrapRefusal("packet_encoding")
    try:
        packet = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonfinite,
            parse_float=_finite_float,
        )
    except (ValueError, RecursionError):
        raise BootstrapRefusal("packet_json") from None
    try:
        canonical = json.dumps(
            packet,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except RecursionError:
        raise BootstrapRefusal("packet_json") from None
    if canonical != raw:
        raise BootstrapRefusal("packet_canonical")
    if (
        type(packet) is not dict
        or set(packet) != _PACKET_KEYS
        or any(type(packet[name]) is not str for name in _STRING_FIELDS)
        or type(packet["control"]) is not dict
        or type(packet["authority_flags"]) is not list
    ):
        raise BootstrapRefusal("packet_schema")
    if (
        packet["version"] != _PACKET_VERSION
        or packet["operation"] != "bootstrap"
        or packet["hard_end_utc"] != _HARD_END_UTC
        or packet["registration_sha256"] != registration_sha256
        or packet["protocol_sha256"] != protocol_sha256
        or packet["oracle_sha256"] != oracle_sha256
    ):
        raise BootstrapRefusal("packet_context")
    _check_authorities(packet["authority_flags"])
    _check_control(packet)
    return packet


def saved_error_bits(value):
    """Preserve the complete DWORD bits of one exact signed32 saved error."""
    if type(value) is not int or not _I32_MIN <= value <= _I32_MAX:
        raise BootstrapRefusal("saved_error")
    return value if value >= 0 else value + 4294967296
