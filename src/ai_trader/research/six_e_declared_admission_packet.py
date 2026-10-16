"""Strict in-memory transport of a complete constructed admission declaration.

No files, persistence, resume, quotes, policy, model or orders are accessed.
Raw and canonical hashes bind caller-supplied expectations, not funding, receipt
provenance or installed source authentication. An invented whole declaration
with replaced expectations remains unauthenticated and grants no authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace

from ai_trader.research import six_e_declared_admission as admission

VERSION = "six_e_declared_admission_packet_v1"
STATUS = "constructed_declared_admission_packet_not_authenticated"
CORE_VERSION = "six_e_declared_admission_v1"
MAX_PACKET_BYTES, MAX_DEPTH, MAX_MARKERS = 4 * 1024**2, 8, 100_000
MAX_INTEGER_DIGITS, MAX_INTEGER_MAGNITUDE = 19, "9223372036854775807"
AUTHORITY_FLAGS = tuple(
    sorted(
        {
            **dict(admission.AUTHORITY_FLAGS),
            "packet_provenance_authenticated": False,
            "storage_written": False,
            "resume_authorized": False,
        }.items()
    )
)
TOP_FIELDS = frozenset(
    {
        "version",
        "scope",
        "core_version",
        "genesis",
        "expected_genesis_sha256",
        "expected_terminal",
        "records",
    }
)
PREFIX_FIELDS = frozenset({"sequence", "head_sha256", "complete_through_ns"})
RECORD_FIELDS = frozenset(
    {"event_id", "expected_prefix", "recorded_at_ns", "complete_through_ns", "payload", "kind"}
)
PAYLOAD_SCHEMAS = {
    "AdmissionRequested": (
        admission.AdmissionRequested,
        ("admission_id", "contract", "side", "quantity_contracts"),
    ),
    "EntryReceipt": (
        admission.EntryReceipt,
        (
            "admission_id",
            "receipt_id",
            "contract",
            "side",
            "quantity_contracts",
            "price_nano",
            "executed_at_ns",
        ),
    ),
    "EntryUnfilled": (admission.EntryUnfilled, ("admission_id", "reason")),
    "ExitRequested": (admission.ExitRequested, ("admission_id", "request_id")),
    "ExitReceipt": (
        admission.ExitReceipt,
        (
            "request_id",
            "receipt_id",
            "contract",
            "quantity_contracts",
            "price_nano",
            "executed_at_ns",
        ),
    ),
    "ExitUnknown": (admission.ExitUnknown, ("request_id",)),
    "ClockAdvanced": (admission.ClockAdvanced, ()),
}
KIND_BY_TYPE = {cls: kind for kind, (cls, _) in PAYLOAD_SCHEMAS.items()}


class PacketError(ValueError):
    """Refused malformed, noncanonical, oversized or conflicting packet."""


@dataclass(frozen=True, slots=True)
class DeclaredAdmissionPacket:
    genesis: admission.DeclaredAdmissionGenesis
    records: tuple[admission.DeclaredRecord, ...]
    expected_genesis_sha256: str
    expected_terminal: admission.DeclaredPrefix
    reconstructed_state: admission.DeclaredAdmissionState
    authority_flags: tuple[tuple[str, bool], ...]


def _require(condition, message):
    if not condition:
        raise PacketError(message)


def _pin(value):
    _require(
        type(value) is str
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value),
        "Exact lowercase external SHA256 required",
    )


def _shape(value, fields, label):
    _require(type(value) is dict and set(value) == set(fields), f"Exact {label} fields required")


def _scan(raw):
    """Bound depth and OUTSIDE-STRING markers, not every JSON node."""
    depth = markers = 0
    quoted = escaped = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (123, 91, 125, 93, 44, 58):
            markers += 1
            if byte in (123, 91):
                depth += 1
            elif byte in (125, 93):
                depth -= 1
            _require(0 <= depth <= MAX_DEPTH, "Packet nesting exceeds depth bound")
            _require(markers <= MAX_MARKERS, "Packet structural marker budget exceeded")
    _require(not quoted and depth == 0, "Unterminated packet string or container")


def _parse_integer(token):
    _require(type(token) is str and bool(token), "Exact integer token required")
    digits = token[1:] if token[0] == "-" else token
    _require(
        bool(digits)
        and len(digits) <= MAX_INTEGER_DIGITS
        and all("0" <= char <= "9" for char in digits),
        "Integer lexical digit bound exceeded",
    )
    _require(len(digits) == 1 or digits[0] != "0", "Noncanonical leading zero")
    _require(token != "-0", "Negative-zero spelling is not canonical")
    _require(
        len(digits) < len(MAX_INTEGER_MAGNITUDE) or digits <= MAX_INTEGER_MAGNITUDE,
        "Integer lexical signed63 magnitude exceeded",
    )
    return int(token)  # Conversion occurs only after lexical magnitude validation.


def _forbidden_number(_token):
    raise PacketError("Float, exponent and nonfinite numeric tokens are unsupported")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate JSON object key")
        result[key] = value
    return result


def _expectations(expected_genesis_sha256, expected_terminal):
    _pin(expected_genesis_sha256)
    _require(type(expected_terminal) is admission.DeclaredPrefix, "Exact external prefix required")
    replace(expected_terminal)  # Revalidate even poisoned frozen witness instances.
    _require(admission.VERSION == CORE_VERSION, "Held admission core version required")


def _prefix(value):
    _shape(value, PREFIX_FIELDS, "prefix")
    return admission.DeclaredPrefix(**value)


def _genesis(value):
    _shape(value, {"scenario_id", "seed", "economics", "limits"}, "genesis")
    seed, economics, limits = value["seed"], value["economics"], value["limits"]
    _shape(seed, {"initial_balance_usd_micros", "initialized_at_ns"}, "seed")
    _shape(
        economics,
        {
            "account_currency",
            "tick_value_usd_micros",
            "entry_fee_usd_micros_per_contract",
            "exit_fee_usd_micros_per_contract",
            "margin",
        },
        "economics",
    )
    margin = economics["margin"]
    if margin is not None:
        _shape(
            margin,
            {"initial_usd_micros_per_contract", "maintenance_usd_micros_per_contract"},
            "margin",
        )
        margin = admission.budget.economics.DeclaredMargin(**margin)
    _shape(
        limits,
        {
            "cash_buffer_usd_micros",
            "max_snapshot_age_ns",
            "max_cumulative_realization_loss_usd_micros",
        },
        "limits",
    )
    assumptions = admission.DeclaredEconomics(
        economics["account_currency"],
        economics["tick_value_usd_micros"],
        economics["entry_fee_usd_micros_per_contract"],
        economics["exit_fee_usd_micros_per_contract"],
        margin,
    )
    return admission.DeclaredAdmissionGenesis(
        value["scenario_id"],
        admission.EconomicSeed(**seed),
        assumptions,
        admission.DeclaredBudgetLimits(**limits),
    )


def _record(value):
    _shape(value, RECORD_FIELDS, "record")
    kind = value["kind"]
    _require(type(kind) is str and kind in PAYLOAD_SCHEMAS, "Closed payload kind required")
    cls, fields = PAYLOAD_SCHEMAS[kind]
    _shape(value["payload"], fields, "payload")
    return admission.DeclaredRecord(
        value["event_id"],
        _prefix(value["expected_prefix"]),
        value["recorded_at_ns"],
        value["complete_through_ns"],
        cls(**value["payload"]),
    )


def _wire(genesis, records, expected_genesis_sha256, expected_terminal):
    return {
        "version": VERSION,
        "scope": STATUS,
        "core_version": CORE_VERSION,
        "genesis": asdict(genesis),
        "expected_genesis_sha256": expected_genesis_sha256,
        "expected_terminal": asdict(expected_terminal),
        "records": [
            {**asdict(record), "kind": KIND_BY_TYPE[type(record.payload)]} for record in records
        ],
    }


def _canonical(value):
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")
    _require(0 < len(raw) <= MAX_PACKET_BYTES, "Packet byte bound exceeded")
    _scan(raw)
    return raw


def encode_packet(
    genesis: admission.DeclaredAdmissionGenesis,
    records: tuple[admission.DeclaredRecord, ...],
    *,
    expected_genesis_sha256: str,
    expected_terminal: admission.DeclaredPrefix,
) -> bytes:
    """Encode only a complete verified typed declaration; accept no packet/cache."""
    try:
        _expectations(expected_genesis_sha256, expected_terminal)
        admission.reconstruct(
            genesis,
            records,
            expected_genesis_sha256=expected_genesis_sha256,
            expected_terminal=expected_terminal,
        )
        return _canonical(_wire(genesis, records, expected_genesis_sha256, expected_terminal))
    except PacketError:
        raise
    except (
        ValueError,
        TypeError,
        AttributeError,
        RecursionError,
        OverflowError,
        MemoryError,
    ) as exc:
        raise PacketError("Invalid bounded typed packet declaration") from exc


def decode_packet(
    raw: bytes,
    *,
    expected_packet_sha256: str,
    expected_genesis_sha256: str,
    expected_terminal: admission.DeclaredPrefix,
) -> DeclaredAdmissionPacket:
    """Gate raw bytes before parsing, then reconstruct without serialized state.

    Independently retained expectations are mandatory. Replacing every witness
    can make an invented whole declaration consistent, never authenticated.
    """
    try:
        _require(type(raw) is bytes, "Exact immutable packet bytes required")
        _require(0 < len(raw) <= MAX_PACKET_BYTES, "Packet byte bound exceeded")
        _pin(expected_packet_sha256)
        _require(
            hashlib.sha256(raw).hexdigest() == expected_packet_sha256,
            "External raw packet SHA256 differs",
        )
        _expectations(expected_genesis_sha256, expected_terminal)
        _scan(raw)
        _require(not raw.startswith(b"\xef\xbb\xbf"), "UTF-8 BOM is unsupported")
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_int=_parse_integer,
            parse_float=_forbidden_number,
            parse_constant=_forbidden_number,
        )
        _shape(value, TOP_FIELDS, "top-level packet")
        for key, expected in (
            ("version", VERSION),
            ("scope", STATUS),
            ("core_version", CORE_VERSION),
        ):
            _require(
                type(value[key]) is str and value[key] == expected, "Fixed packet header required"
            )
        _pin(value["expected_genesis_sha256"])
        terminal = _prefix(value["expected_terminal"])
        _require(
            value["expected_genesis_sha256"] == expected_genesis_sha256
            and terminal == expected_terminal,
            "Embedded witnesses must match independent external expectations",
        )
        _require(
            type(value["records"]) is list and len(value["records"]) <= admission.MAX_RECORDS,
            "Complete bounded record array required",
        )
        genesis = _genesis(value["genesis"])
        records = tuple(_record(record) for record in value["records"])
        state = admission.reconstruct(
            genesis,
            records,
            expected_genesis_sha256=expected_genesis_sha256,
            expected_terminal=expected_terminal,
        )
        _require(
            _canonical(_wire(genesis, records, expected_genesis_sha256, terminal)) == raw,
            "Packet bytes must be exactly canonical",
        )
        return DeclaredAdmissionPacket(
            genesis, records, expected_genesis_sha256, terminal, state, AUTHORITY_FLAGS
        )
    except PacketError:
        raise
    except (
        ValueError,
        TypeError,
        AttributeError,
        RecursionError,
        OverflowError,
        MemoryError,
    ) as exc:
        raise PacketError("Invalid bounded canonical packet bytes") from exc
