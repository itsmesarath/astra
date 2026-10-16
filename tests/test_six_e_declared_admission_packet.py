"""Strict in-memory transport tests using only independent constructed tapes."""

import builtins
import hashlib
import json
import socket
import sqlite3
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, replace
from pathlib import Path

import pytest

from ai_trader.research import six_e_declared_admission as admission
from ai_trader.research import six_e_declared_admission_packet as packet
from ai_trader.research import six_e_declared_economics as economics
from ai_trader.research import six_e_entry_budget as budget
from ai_trader.research import six_e_liquidity_status as reader

START = 1_000_000_000_000
DELAY = 100_000_000
SECOND = 1_000_000_000
DEADLINE = DELAY + SECOND
PRICE = 1_000_000_000
TICK = economics.ledger.target.TICK
MAX = 2**63 - 1


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def declaration(balance=135, *, zero=False, missing_margin=False):
    assumptions = economics.DeclaredEconomics(
        "USD",
        125,
        0 if zero else 10,
        0 if zero else 20,
        None
        if missing_margin
        else economics.DeclaredMargin(0, 0)
        if zero
        else economics.DeclaredMargin(100, 80),
    )
    return admission.DeclaredAdmissionGenesis(
        "synthetic-packet",
        economics.EconomicSeed(balance, START),
        assumptions,
        budget.DeclaredBudgetLimits(0 if zero else 5, SECOND, None),
    )


class Tape:
    def __init__(self, genesis=None):
        self.genesis = declaration() if genesis is None else genesis
        self.pin = admission.genesis_sha256(self.genesis)
        self.prefix = admission.DeclaredPrefix(0, self.pin, START)
        self.records = ()
        self.state = admission.reconstruct(
            self.genesis,
            self.records,
            expected_genesis_sha256=self.pin,
            expected_terminal=self.prefix,
        )

    def add(self, payload, at=None):
        at = self.prefix.complete_through_ns if at is None else at
        record = admission.DeclaredRecord(
            f"event-{len(self.records) + 1}", self.prefix, at, at, payload
        )
        result = admission.advance(
            self.genesis,
            self.records,
            record,
            expected_genesis_sha256=self.pin,
            expected_terminal=self.prefix,
        )
        self.records, self.state, self.prefix = result.records, result.state, result.state.prefix

    def encode(self, **changes):
        arguments = {"expected_genesis_sha256": self.pin, "expected_terminal": self.prefix}
        arguments.update(changes)
        return packet.encode_packet(self.genesis, self.records, **arguments)

    def decode(self, raw=None, **changes):
        raw = self.encode() if raw is None else raw
        arguments = {
            "expected_packet_sha256": digest(raw),
            "expected_genesis_sha256": self.pin,
            "expected_terminal": self.prefix,
        }
        arguments.update(changes)
        return packet.decode_packet(raw, **arguments)


def tape(kind="ENTRY_PENDING"):
    result = Tape(declaration(zero=kind == "ZERO_UNKNOWN", missing_margin=kind == "MISSING_MARGIN"))
    if kind == "EMPTY":
        return result
    if kind == "CLOCK_ONLY":
        result.add(admission.ClockAdvanced(), START + 1)
        return result
    at = START + SECOND + 1 if kind == "STALE_BUDGET" else START
    result.add(admission.AdmissionRequested("admission-1", "6EM5", "long", 1), at)
    if kind in ("ENTRY_PENDING", "MISSING_MARGIN", "STALE_BUDGET"):
        return result
    if kind == "UNFILLED":
        result.add(admission.EntryUnfilled("admission-1", "timeout"), START + DEADLINE)
        result.add(admission.ClockAdvanced(), START + DEADLINE + 1)
        return result
    at = START + DELAY
    result.add(admission.EntryReceipt("admission-1", "entry-1", "6EM5", "long", 1, PRICE, at), at)
    if kind == "OPEN":
        return result
    result.add(admission.ExitRequested("admission-1", "exit-1"), at)
    if kind == "EXIT_PENDING":
        return result
    if kind in ("EXIT_UNKNOWN", "ZERO_UNKNOWN"):
        result.add(admission.ExitUnknown("exit-1"), START + DELAY + DEADLINE)
        result.add(admission.ClockAdvanced(), START + 86_400 * SECOND)
        return result
    ticks = -3 if kind == "NEGATIVE_CLOSED" else 0
    at = START + 2 * DELAY
    result.add(admission.ExitReceipt("exit-1", "close-1", "6EM5", 1, PRICE + ticks * TICK, at), at)
    return result


def expected_wire(value):
    return {
        "version": "six_e_declared_admission_packet_v1",
        "scope": "constructed_declared_admission_packet_not_authenticated",
        "core_version": "six_e_declared_admission_v1",
        "genesis": asdict(value.genesis),
        "expected_genesis_sha256": value.pin,
        "expected_terminal": asdict(value.prefix),
        "records": [
            {**asdict(record), "kind": type(record.payload).__name__} for record in value.records
        ],
    }


def node(value, path):
    for key in path:
        value = value[key]
    return value


def assert_false_authority(value):
    packet_flags = dict(value.authority_flags)
    assert packet_flags["packet_provenance_authenticated"] is False
    assert packet_flags["storage_written"] is False
    assert packet_flags["resume_authorized"] is False
    for flags in (value.authority_flags, value.reconstructed_state.authority_flags):
        flags = dict(flags)
        assert flags
        assert all(flag is False for flag in flags.values())
        for key in (
            "genesis_authenticated",
            "complete_records_authenticated",
            "receipt_provenance_authenticated",
            "cash_balance_confirmed",
            "margin_requirement_confirmed",
            "risk_approved",
            "trading_enabled",
            "training_eligible",
            "strategy_scoring_allowed",
            "promotion_allowed",
            "independent_holdout",
            "broker_execution_confirmed",
            "execution_confirmed",
            "admission_authorized",
        ):
            assert flags[key] is False


@pytest.mark.parametrize(
    "kind",
    [
        "EMPTY",
        "CLOCK_ONLY",
        "ENTRY_PENDING",
        "OPEN",
        "EXIT_PENDING",
        "EXIT_UNKNOWN",
        "UNFILLED",
        "CLOSED",
        "ZERO_UNKNOWN",
        "NEGATIVE_CLOSED",
        "STALE_BUDGET",
        "MISSING_MARGIN",
    ],
)
def test_lossless_canonical_round_trip_preserves_all_phases_kinds_and_liabilities(kind):
    value = tape(kind)
    before = deepcopy((value.genesis, value.records, value.state))
    raw = value.encode()
    assert type(raw) is bytes
    assert raw == canonical(expected_wire(value))
    result = value.decode(raw)
    assert type(result) is packet.DeclaredAdmissionPacket
    assert result.genesis == value.genesis
    assert result.records == value.records
    assert type(result.records) is tuple
    assert result.expected_genesis_sha256 == value.pin
    assert result.expected_terminal == value.prefix
    assert result.reconstructed_state == value.state
    assert (
        packet.encode_packet(
            result.genesis,
            result.records,
            expected_genesis_sha256=result.expected_genesis_sha256,
            expected_terminal=result.expected_terminal,
        )
        == raw
    )
    assert_false_authority(result)
    assert (value.genesis, value.records, value.state) == before
    if kind == "NEGATIVE_CLOSED":
        assert result.reconstructed_state.declared_realization_balance_usd_micros == -270
    if kind == "ZERO_UNKNOWN":
        assert result.reconstructed_state.phase == "EXIT_UNKNOWN"
        assert result.reconstructed_state.total_commitments_usd_micros == 0
        assert result.reconstructed_state.complete_declared_equity_usd_micros is None


def test_wire_schema_is_explicit_and_contains_no_state_or_authority_cache():
    value = tape("OPEN")
    wire = json.loads(value.encode())
    assert set(wire) == {
        "version",
        "scope",
        "core_version",
        "genesis",
        "expected_genesis_sha256",
        "expected_terminal",
        "records",
    }
    assert all(
        set(record)
        == {
            "event_id",
            "expected_prefix",
            "recorded_at_ns",
            "complete_through_ns",
            "payload",
            "kind",
        }
        for record in wire["records"]
    )
    assert wire["genesis"]["limits"]["max_cumulative_realization_loss_usd_micros"] is None
    assert wire["records"][0]["kind"] == "AdmissionRequested"
    assert wire["records"][1]["kind"] == "EntryReceipt"
    missing = json.loads(tape("MISSING_MARGIN").encode())
    assert missing["genesis"]["economics"]["margin"] is None


@pytest.mark.parametrize(
    "key,changed", [("version", "v2"), ("scope", "authenticated"), ("core_version", "v2")]
)
def test_fixed_protocol_headers_do_not_accept_other_versions_or_authority(key, changed):
    value = tape()
    body = expected_wire(value)
    body[key] = changed
    with pytest.raises(packet.PacketError):
        value.decode(canonical(body))


SCHEMA_PATHS = [
    (),
    ("genesis",),
    ("genesis", "seed"),
    ("genesis", "economics"),
    ("genesis", "economics", "margin"),
    ("genesis", "limits"),
    ("expected_terminal",),
    ("records", 0),
    ("records", 0, "expected_prefix"),
    ("records", 0, "payload"),
]


@pytest.mark.parametrize("path", SCHEMA_PATHS)
@pytest.mark.parametrize("mutation", ["extra", "missing", "wrong_type"])
def test_each_object_requires_exact_keys_and_dictionary_shape(path, mutation):
    value = tape()
    body = expected_wire(value)
    target = node(body, path)
    if mutation == "extra":
        target["unrecognized"] = 0
    elif mutation == "missing":
        del target[next(iter(target))]
    elif path:
        node(body, path[:-1])[path[-1]] = []
    else:
        body = []
    with pytest.raises(packet.PacketError):
        value.decode(canonical(body))


@pytest.mark.parametrize(
    "key",
    [
        "state",
        "reconstructed_state",
        "cash",
        "phase",
        "authority_flags",
        "resume_path",
        "storage_path",
    ],
)
def test_cached_state_liabilities_authorities_and_storage_keys_are_not_accepted(key):
    value = tape("OPEN")
    body = expected_wire(value)
    body[key] = asdict(value.state) if key == "state" else None
    with pytest.raises(packet.PacketError):
        value.decode(canonical(body))


@pytest.mark.parametrize(
    "kind",
    [
        "EntryFill",
        "ExitFill",
        "Cancel",
        "Reconciled",
        "entryreceipt",
        "AdmissionRequested ",
        None,
        1,
    ],
)
def test_only_the_seven_case_sensitive_declared_kind_tags_are_allowed(kind):
    value = tape()
    body = expected_wire(value)
    body["records"][0]["kind"] = kind
    with pytest.raises(packet.PacketError):
        value.decode(canonical(body))


@pytest.mark.parametrize(
    "kind",
    ["ENTRY_PENDING", "OPEN", "EXIT_PENDING", "EXIT_UNKNOWN", "UNFILLED", "CLOSED", "CLOCK_ONLY"],
)
def test_each_payload_kind_refuses_extra_fields_instead_of_ignoring_them(kind):
    value = tape(kind)
    body = expected_wire(value)
    tag = {
        "ENTRY_PENDING": "AdmissionRequested",
        "OPEN": "EntryReceipt",
        "EXIT_PENDING": "ExitRequested",
        "EXIT_UNKNOWN": "ExitUnknown",
        "UNFILLED": "EntryUnfilled",
        "CLOSED": "ExitReceipt",
        "CLOCK_ONLY": "ClockAdvanced",
    }[kind]
    target = next(record for record in body["records"] if record["kind"] == tag)
    target["payload"]["extra"] = True
    with pytest.raises(packet.PacketError):
        value.decode(canonical(body))


@pytest.mark.parametrize(
    "key",
    [
        "version",
        "scenario_id",
        "initial_balance_usd_micros",
        "account_currency",
        "initial_usd_micros_per_contract",
        "cash_buffer_usd_micros",
        "head_sha256",
        "event_id",
        "admission_id",
    ],
)
@pytest.mark.parametrize("conflicting", [False, True])
def test_duplicate_json_keys_are_rejected_at_every_object_depth(key, conflicting):
    value = tape()
    raw = value.encode()
    token = canonical(key) + b":"
    start = raw.index(token) + len(token)
    decoder = json.JSONDecoder()
    decoded, length = decoder.raw_decode(raw[start:].decode("ascii"))
    original = raw[start : start + length]
    replacement = b"null" if conflicting else canonical(decoded)
    corrupted = raw[: start + length] + b"," + token + replacement + raw[start + length :]
    assert original
    with pytest.raises(packet.PacketError):
        value.decode(corrupted)


def test_escaped_alias_of_an_existing_json_key_is_also_a_duplicate():
    value = tape()
    raw = value.encode()
    duplicate = b'"\\u0076ersion":"six_e_declared_admission_packet_v1",'
    with pytest.raises(packet.PacketError):
        value.decode(raw[:1] + duplicate + raw[1:])


@pytest.mark.parametrize(
    "variant",
    [
        "leading_space",
        "trailing_newline",
        "indent",
        "reverse_keys",
        "escaped_key",
        "bom",
        "utf16",
        "second_document",
        "truncated",
        "invalid_utf8",
    ],
)
def test_only_byte_perfect_canonical_ascii_json_is_accepted(variant):
    value = tape()
    raw = value.encode()
    if variant == "leading_space":
        raw = b" " + raw
    elif variant == "trailing_newline":
        raw += b"\n"
    elif variant == "indent":
        raw = json.dumps(expected_wire(value), indent=2).encode()
    elif variant == "reverse_keys":
        raw = json.dumps(
            dict(reversed(list(expected_wire(value).items()))), separators=(",", ":")
        ).encode()
    elif variant == "escaped_key":
        raw = raw.replace(b'"version"', b'"\\u0076ersion"', 1)
    elif variant == "bom":
        raw = b"\xef\xbb\xbf" + raw
    elif variant == "utf16":
        raw = json.dumps(expected_wire(value)).encode("utf-16")
    elif variant == "second_document":
        raw += b"{}"
    elif variant == "truncated":
        raw = raw[:-1]
    else:
        raw = b"\xff" + raw
    with pytest.raises(packet.PacketError):
        value.decode(raw)


@pytest.mark.parametrize(
    "number",
    [
        b"5.0",
        b"5e0",
        b"5E+0",
        b"-0",
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"true",
        b"+5",
        b"05",
        b"9223372036854775808",
        b"-9223372036854775808",
        b"10000000000000000000",
    ],
)
def test_noncanonical_noninteger_or_overflow_tokens_are_not_coerced(number):
    value = tape()
    raw = value.encode().replace(
        b'"cash_buffer_usd_micros":5', b'"cash_buffer_usd_micros":' + number, 1
    )
    with pytest.raises(packet.PacketError):
        value.decode(raw)


@pytest.mark.parametrize(
    "target,value",
    [
        ("quantity_contracts", True),
        ("quantity_contracts", 2),
        ("admission_id", 1),
        ("contract", "EURUSD"),
        ("side", "LONG"),
    ],
)
def test_exact_payload_types_and_supported_domain_are_revalidated(target, value):
    original = tape()
    body = expected_wire(original)
    body["records"][0]["payload"][target] = value
    with pytest.raises(packet.PacketError):
        original.decode(canonical(body))


@pytest.mark.parametrize("raw", [None, "{}", bytearray(b"{}"), memoryview(b"{}"), 1])
def test_decode_requires_exact_bytes_not_a_coercible_input(raw):
    value = tape()
    with pytest.raises(packet.PacketError):
        packet.decode_packet(
            raw,
            expected_packet_sha256="a" * 64,
            expected_genesis_sha256=value.pin,
            expected_terminal=value.prefix,
        )


def test_subclassed_bytes_are_not_exact_wire_bytes():
    class UnsupportedBytes(bytes):
        pass

    value = tape()
    raw = UnsupportedBytes(value.encode())
    with pytest.raises(packet.PacketError):
        value.decode(raw)


@pytest.mark.parametrize("pin", [None, True, "A" * 64, "a" * 63, "b" * 64])
def test_raw_pin_is_required_canonical_and_checked_before_json_or_reconstruction(monkeypatch, pin):
    value = tape()
    raw = value.encode()

    def forbidden(*args, **kwargs):
        raise AssertionError("Unpinned wire bytes reached parser or admission core")

    with monkeypatch.context() as patch:
        patch.setattr(packet.json, "loads", forbidden)
        patch.setattr(admission, "reconstruct", forbidden)
        with pytest.raises(packet.PacketError):
            value.decode(raw, expected_packet_sha256=pin)


def test_wrong_raw_pin_precedes_utf8_failure_and_not_just_json_failure():
    value = tape()
    with pytest.raises(packet.PacketError, match="pin|SHA|hash|identity"):
        value.decode(b"\xff", expected_packet_sha256="a" * 64)


@pytest.mark.parametrize("witness", ["genesis", "sequence", "head", "frontier"])
def test_independently_retained_genesis_and_terminal_witnesses_cannot_be_defined_by_packet(witness):
    value = tape()
    arguments = {}
    if witness == "genesis":
        arguments["expected_genesis_sha256"] = "b" * 64
    else:
        field = {"sequence": "sequence", "head": "head_sha256", "frontier": "complete_through_ns"}[
            witness
        ]
        changed = "b" * 64 if field == "head_sha256" else getattr(value.prefix, field) + 1
        arguments["expected_terminal"] = replace(value.prefix, **{field: changed})
    with pytest.raises(packet.PacketError):
        value.decode(**arguments)
    with pytest.raises(packet.PacketError):
        value.encode(**arguments)


@pytest.mark.parametrize("witness", ["genesis", "sequence", "head", "frontier"])
def test_changed_embedded_witness_is_refused_despite_a_matching_new_raw_pin(witness):
    value = tape()
    body = expected_wire(value)
    if witness == "genesis":
        body["expected_genesis_sha256"] = "b" * 64
    else:
        field = {"sequence": "sequence", "head": "head_sha256", "frontier": "complete_through_ns"}[
            witness
        ]
        body["expected_terminal"][field] = (
            "b" * 64 if field == "head_sha256" else body["expected_terminal"][field] + 1
        )
    with pytest.raises(packet.PacketError):
        value.decode(canonical(body))


@pytest.mark.parametrize(
    "name", ["expected_packet_sha256", "expected_genesis_sha256", "expected_terminal"]
)
def test_all_three_external_decoder_witnesses_are_mandatory(name):
    value = tape()
    raw = value.encode()
    arguments = {
        "expected_packet_sha256": digest(raw),
        "expected_genesis_sha256": value.pin,
        "expected_terminal": value.prefix,
    }
    del arguments[name]
    with pytest.raises(TypeError):
        packet.decode_packet(raw, **arguments)


@pytest.mark.parametrize("name", ["expected_genesis_sha256", "expected_terminal"])
def test_both_external_encoder_witnesses_are_mandatory(name):
    value = tape()
    arguments = {"expected_genesis_sha256": value.pin, "expected_terminal": value.prefix}
    del arguments[name]
    with pytest.raises(TypeError):
        packet.encode_packet(value.genesis, value.records, **arguments)


@pytest.mark.parametrize(
    "mutation",
    [
        "omit_suffix",
        "omit_first",
        "reorder",
        "duplicate",
        "event_drift",
        "payload_drift",
        "prefix_drift",
    ],
)
def test_matching_raw_hash_never_repairs_or_subsets_a_changed_complete_prefix(mutation):
    value = tape("CLOSED")
    body = expected_wire(value)
    records = body["records"]
    if mutation == "omit_suffix":
        del records[-1]
    elif mutation == "omit_first":
        del records[0]
    elif mutation == "reorder":
        records[0], records[1] = records[1], records[0]
    elif mutation == "duplicate":
        records[1] = deepcopy(records[0])
    elif mutation == "event_drift":
        records[0]["event_id"] = "new-event"
    elif mutation == "payload_drift":
        records[0]["payload"]["side"] = "short"
    else:
        records[1]["expected_prefix"]["head_sha256"] = "b" * 64
    with pytest.raises(packet.PacketError):
        value.decode(canonical(body))


def test_intentionally_shorter_tape_needs_its_own_external_terminal_witness():
    value = tape("OPEN")
    shorter = Tape(value.genesis)
    shorter.add(admission.AdmissionRequested("admission-1", "6EM5", "long", 1))
    raw = shorter.encode()
    with pytest.raises(packet.PacketError):
        value.decode(raw)
    assert shorter.decode(raw).reconstructed_state == shorter.state


def test_complete_invented_declaration_with_replaced_witnesses_is_not_authenticated():
    original, invented = tape("OPEN"), Tape(declaration(1000))
    raw = invented.encode()
    with pytest.raises(packet.PacketError):
        original.decode(raw)
    decoded = invented.decode(raw)
    assert decoded.genesis.seed.initial_balance_usd_micros == 1000
    assert_false_authority(decoded)


def test_codec_always_uses_held_core_and_returns_freshly_reconstructed_state(monkeypatch):
    value = tape("EXIT_UNKNOWN")
    original = admission.reconstruct
    calls = []

    def observed(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append((args, kwargs, result))
        return result

    with monkeypatch.context() as patch:
        patch.setattr(admission, "reconstruct", observed)
        raw = value.encode()
        assert calls
        encoded_calls = len(calls)
        decoded = value.decode(raw)
        assert len(calls) > encoded_calls
        assert decoded.reconstructed_state is calls[-1][2]
        assert calls[-1][0][0] == value.genesis
        assert calls[-1][0][1] == value.records
        assert calls[-1][1] == {
            "expected_genesis_sha256": value.pin,
            "expected_terminal": value.prefix,
        }


def test_core_refusal_is_controlled_and_cannot_be_silently_bypassed(monkeypatch):
    value = tape()
    raw = value.encode()

    def refused(*args, **kwargs):
        raise admission.DeclaredAdmissionError("held core refuses declared prefix")

    with monkeypatch.context() as patch:
        patch.setattr(admission, "reconstruct", refused)
        with pytest.raises(packet.PacketError):
            value.encode()
        with pytest.raises(packet.PacketError):
            value.decode(raw)


def test_exact_maximum_money_remains_an_integer_in_lossless_genesis_round_trip():
    value = Tape(declaration(MAX))
    raw = value.encode()
    assert str(MAX).encode() in raw
    decoded = value.decode(raw)
    assert type(decoded.genesis.seed.initial_balance_usd_micros) is int
    assert decoded.genesis.seed.initial_balance_usd_micros == MAX


def test_result_and_all_typed_payloads_remain_immutable():
    value = tape()
    decoded = value.decode()
    with pytest.raises(FrozenInstanceError):
        decoded.records = ()
    with pytest.raises(FrozenInstanceError):
        decoded.genesis.seed.initial_balance_usd_micros = 1000
    with pytest.raises(FrozenInstanceError):
        decoded.records[0].payload.quantity_contracts = 2
    with pytest.raises(FrozenInstanceError):
        decoded.reconstructed_state.phase = "FLAT"


def test_packet_codec_is_pure_and_deterministic_without_storage_market_or_model_access(monkeypatch):
    value = tape("NEGATIVE_CLOSED")
    before = deepcopy((asdict(value.genesis), tuple(asdict(record) for record in value.records)))

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Packet codec attempted filesystem, source hashing, storage, policy or network access"
        )

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(Path, "open", forbidden)
        patch.setattr(Path, "read_bytes", forbidden)
        patch.setattr(Path, "read_text", forbidden)
        patch.setattr(Path, "write_bytes", forbidden)
        patch.setattr(Path, "write_text", forbidden)
        patch.setattr(sqlite3, "connect", forbidden)
        patch.setattr(socket, "create_connection", forbidden)
        patch.setattr(economics.replay, "fingerprints", forbidden)
        patch.setattr(economics.replay, "build_plan", forbidden)
        patch.setattr(economics.replay, "_freeze", forbidden)
        patch.setattr(economics, "project", forbidden)
        patch.setattr(economics.ledger, "ScenarioLedger", forbidden)
        patch.setattr(economics.replay.rules, "rules", forbidden)
        patch.setattr(economics.replay.rules.Model, "predict", forbidden)
        patch.setattr(economics.replay.study.common, "hash_file", forbidden)
        patch.setattr(reader, "snapshot", forbidden)
        first = value.encode()
        second = value.encode()
        assert first == second
        assert value.decode(first) == value.decode(second)
    assert (asdict(value.genesis), tuple(asdict(record) for record in value.records)) == before


def test_reviewed_resource_constants_and_held_core_limits_are_not_redefined():
    assert packet.MAX_PACKET_BYTES == 4 * 1024**2
    assert packet.MAX_DEPTH == 8
    assert packet.MAX_MARKERS == 100_000
    assert packet.MAX_INTEGER_DIGITS == 19
    assert packet.MAX_INTEGER_MAGNITUDE == "9223372036854775807"
    assert admission.MAX_RECORDS == 2000
    assert admission.MAX_RECORD_BYTES == 8192


def test_private_serializer_byte_boundary_is_not_an_arbitrary_public_packet_claim():
    # A JSON string exercises only the private serializer's exact byte limit.
    value = "x" * (4 * 1024**2 - 2)
    raw = packet._canonical(value)
    assert len(raw) == 4 * 1024**2
    assert raw == b'"' + value.encode("ascii") + b'"'
    with pytest.raises(packet.PacketError, match="byte bound"):
        packet._canonical(value + "x")


@pytest.mark.parametrize("raw", [b"", b"x" * (4 * 1024**2 + 1)], ids=["empty", "byte_overflow"])
def test_public_raw_size_refusal_precedes_hashing_and_parsing(monkeypatch, raw):
    value = tape()

    def forbidden(*args, **kwargs):
        raise AssertionError("Oversized or empty raw packet reached hash, parser or core")

    with monkeypatch.context() as patch:
        patch.setattr(packet.hashlib, "sha256", forbidden)
        patch.setattr(packet.json, "loads", forbidden)
        patch.setattr(admission, "reconstruct", forbidden)
        with pytest.raises(packet.PacketError, match="byte bound"):
            packet.decode_packet(
                raw,
                expected_packet_sha256="a" * 64,
                expected_genesis_sha256=value.pin,
                expected_terminal=value.prefix,
            )


def test_private_scanner_depth_equality_and_one_extra_do_not_claim_public_schema_acceptance():
    packet._scan(b"[" * 8 + b"0" + b"]" * 8)
    with pytest.raises(packet.PacketError, match="depth"):
        packet._scan(b"[" * 9 + b"0" + b"]" * 9)


def test_private_marker_budget_counts_only_outside_string_structural_markers():
    # Array(n zeros) has n+1 outside-string markers and is not a packet schema.
    exact = b"[" + b"0," * 99_998 + b"0]"
    one_extra = b"[" + b"0," * 99_999 + b"0]"
    assert len(exact) < 200_000
    packet._scan(exact)
    with pytest.raises(packet.PacketError, match="marker"):
        packet._scan(one_extra)
    # More than the entire budget inside a string must not count as structure.
    packet._scan(canonical("{}[],:" * 20_000))


@pytest.mark.parametrize(
    "text", ['"{}[],:', "\\{}[],:", '\\"{}[],:', "\\\\{}[],:", '\\\\\\"{}[],:']
)
def test_private_scanner_handles_escaped_quotes_and_backslash_parity_inside_strings(text):
    packet._scan(canonical([text, {"key": "{}[],:"}]))


@pytest.mark.parametrize(
    "raw",
    [b"[" * 9 + b"0" + b"]" * 9, b"[" + b"0," * 99_999 + b"0]"],
    ids=["depth_overflow", "marker_overflow"],
)
def test_public_resource_scanner_runs_after_pin_but_before_json_parser(monkeypatch, raw):
    value = tape()
    pin = digest(raw)

    def forbidden(*args, **kwargs):
        raise AssertionError("Resource-refused packet reached JSON or core")

    with monkeypatch.context() as patch:
        patch.setattr(packet.json, "loads", forbidden)
        patch.setattr(admission, "reconstruct", forbidden)
        with pytest.raises(packet.PacketError, match="depth|marker"):
            value.decode(raw, expected_packet_sha256=pin)


@pytest.mark.parametrize(
    "token,expected",
    [("0", 0), ("1", 1), ("-1", -1), ("9223372036854775807", MAX), ("-9223372036854775807", -MAX)],
)
def test_private_integer_parser_accepts_exact_signed63_lexical_bounds(token, expected):
    result = packet._parse_integer(token)
    assert type(result) is int
    assert result == expected


@pytest.mark.parametrize(
    "token",
    [
        None,
        True,
        b"1",
        "",
        "-",
        "-0",
        "00",
        "01",
        "-01",
        "+1",
        "1.0",
        "1e0",
        "1_0",
        "١",
        "9223372036854775808",
        "-9223372036854775808",
        "10000000000000000000",
    ],
)
def test_private_integer_parser_refuses_noncanonical_types_spellings_and_magnitudes(token):
    with pytest.raises(packet.PacketError):
        packet._parse_integer(token)


@pytest.mark.parametrize(
    "token", ["9223372036854775808", "-9223372036854775808", "10000000000000000000"]
)
def test_private_integer_overflow_refuses_before_python_int_conversion(monkeypatch, token):
    def forbidden(*args, **kwargs):
        raise AssertionError("Out-of-range lexical integer reached int conversion")

    with monkeypatch.context() as patch:
        patch.setattr(packet, "int", forbidden, raising=False)
        with pytest.raises(packet.PacketError):
            packet._parse_integer(token)


def test_overlong_wire_array_and_typed_tuple_refuse_without_quadratic_chain_building():
    value = tape()
    body = expected_wire(value)
    body["records"] = [deepcopy(body["records"][0])] * 2001
    with pytest.raises(packet.PacketError):
        value.decode(canonical(body))
    with pytest.raises(packet.PacketError):
        packet.encode_packet(
            value.genesis,
            value.records * 2001,
            expected_genesis_sha256=value.pin,
            expected_terminal=value.prefix,
        )


def test_exact_2000_record_constructed_clock_prefix_round_trips_in_linear_construction():
    # Build independent canonical prefix witnesses, not 2,000 quadratic advances.
    value = Tape()
    constructed = []
    prefix = value.prefix
    for sequence in range(1, 2001):
        at = START + sequence
        record = admission.DeclaredRecord(
            f"clock-{sequence}", prefix, at, at, admission.ClockAdvanced()
        )
        constructed.append(record)
        head = digest(
            canonical(
                {
                    "version": "six_e_declared_admission_v1",
                    "kind": "ClockAdvanced",
                    "record": asdict(record),
                }
            )
        )
        prefix = admission.DeclaredPrefix(sequence, head, at)
    value.records, value.prefix = tuple(constructed), prefix
    value.state = admission.reconstruct(
        value.genesis,
        value.records,
        expected_genesis_sha256=value.pin,
        expected_terminal=prefix,
    )
    raw = value.encode()
    decoded = value.decode(raw)
    assert len(decoded.records) == 2000
    assert decoded.expected_terminal.sequence == 2000
    assert decoded.records == value.records
    assert decoded.reconstructed_state == value.state
    assert decoded.reconstructed_state.phase == "FLAT"
    assert decoded.reconstructed_state.declared_realization_balance_usd_micros == 135
    assert_false_authority(decoded)


@pytest.mark.parametrize("replacement", [None, [], {}])
def test_records_are_exact_array_on_wire_and_complete_immutable_tuple_for_encoding(replacement):
    value = tape()
    body = expected_wire(value)
    body["records"] = replacement
    with pytest.raises(packet.PacketError):
        value.decode(canonical(body))
    with pytest.raises(packet.PacketError):
        packet.encode_packet(
            value.genesis,
            replacement,
            expected_genesis_sha256=value.pin,
            expected_terminal=value.prefix,
        )


def test_encoding_revalidates_deliberately_poisoned_nested_frozen_input():
    value = tape()
    object.__setattr__(value.genesis.economics.margin, "initial_usd_micros_per_contract", True)
    with pytest.raises(packet.PacketError):
        value.encode()


def test_decoding_does_not_release_unknown_or_manufacture_a_late_fill():
    value = tape("EXIT_UNKNOWN")
    body = expected_wire(value)
    last = body["records"][-1]
    last["kind"] = "ExitReceipt"
    last["payload"] = {
        "request_id": "exit-1",
        "receipt_id": "late-close",
        "contract": "6EM5",
        "quantity_contracts": 1,
        "price_nano": PRICE,
        "executed_at_ns": last["recorded_at_ns"],
    }
    with pytest.raises(packet.PacketError):
        value.decode(canonical(body))


@pytest.mark.parametrize(
    "field,changed", [("sequence", True), ("head_sha256", "A" * 64), ("complete_through_ns", -1)]
)
def test_external_frozen_prefix_poison_is_revalidated_before_parser_or_core(
    monkeypatch, field, changed
):
    value = tape()
    raw = value.encode()
    terminal = deepcopy(value.prefix)
    object.__setattr__(terminal, field, changed)

    def forbidden(*args, **kwargs):
        raise AssertionError("Poisoned external witness reached parser or admission core")

    with monkeypatch.context() as patch:
        patch.setattr(packet.json, "loads", forbidden)
        patch.setattr(admission, "reconstruct", forbidden)
        with pytest.raises(packet.PacketError):
            value.decode(raw, expected_terminal=terminal)
        with pytest.raises(packet.PacketError):
            value.encode(expected_terminal=terminal)


def test_actual_held_core_version_must_match_but_matching_version_is_not_source_authentication(
    monkeypatch,
):
    value = tape()
    raw = value.encode()
    with monkeypatch.context() as patch:
        patch.setattr(admission, "VERSION", "unexpected-core-v2")
        with pytest.raises(packet.PacketError):
            value.encode()
        with pytest.raises(packet.PacketError):
            value.decode(raw)
    assert_false_authority(value.decode(raw))


@pytest.mark.parametrize("kind", ["EntryReceipt", "ExitReceipt"])
def test_receipt_at_original_inclusive_deadline_round_trips_without_retiming(kind):
    value = Tape()
    value.add(admission.AdmissionRequested("admission-1", "6EM5", "long", 1))
    entry_at = START + DEADLINE if kind == "EntryReceipt" else START + DELAY
    value.add(
        admission.EntryReceipt("admission-1", "entry-1", "6EM5", "long", 1, PRICE, entry_at),
        entry_at,
    )
    if kind == "ExitReceipt":
        value.add(admission.ExitRequested("admission-1", "exit-1"), entry_at)
        exit_at = entry_at + DEADLINE
        value.add(admission.ExitReceipt("exit-1", "close-1", "6EM5", 1, PRICE, exit_at), exit_at)
    decoded = value.decode()
    assert decoded.records[-1].payload.executed_at_ns == value.prefix.complete_through_ns
    assert decoded.reconstructed_state == value.state


@pytest.mark.parametrize("raw", [b'{"x":"unterminated', b'"escaped\\', b"{", b"]", b"[]]", b"[[0]"])
def test_private_scanner_refuses_unterminated_or_negative_depth_inputs(raw):
    with pytest.raises(packet.PacketError):
        packet._scan(raw)


@pytest.mark.parametrize(
    "path,key,changed",
    [
        (("genesis", "seed"), "initial_balance_usd_micros", True),
        (("genesis", "seed"), "initialized_at_ns", True),
        (("genesis", "economics"), "tick_value_usd_micros", False),
        (("genesis", "economics", "margin"), "initial_usd_micros_per_contract", True),
        (("genesis", "limits"), "cash_buffer_usd_micros", False),
        (("expected_terminal",), "sequence", True),
        (("records", 0), "recorded_at_ns", True),
        (("records", 0, "expected_prefix"), "complete_through_ns", True),
    ],
)
def test_boolean_numbers_are_never_coerced_in_nested_genesis_prefix_or_envelope(path, key, changed):
    value = tape()
    body = expected_wire(value)
    node(body, path)[key] = changed
    with pytest.raises(packet.PacketError):
        value.decode(canonical(body))
