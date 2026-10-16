"""Independent contract tests for the bounded native-member provider.

The first test deliberately discovers the interface inside the collected test,
so a missing implementation is an assertion failure, not a collection accident.
"""

import importlib
import importlib.util
import inspect
import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import date
from enum import IntEnum
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest

ORACLE_SPEC = importlib.util.spec_from_file_location(
    "native_member_provider_independent_oracles_20261013",
    Path(__file__).with_name("native_member_provider_oracles_20261013.py"),
)
ORACLES = importlib.util.module_from_spec(ORACLE_SPEC)
ORACLE_SPEC.loader.exec_module(ORACLES)
RECORD_FIELDS = ORACLES.RECORD_FIELDS
context_body = ORACLES.context_body
digest = ORACLES.digest
expected_pins = ORACLES.expected_pins
protocol_literal = ORACLES.protocol_literal
minimal_evidence_body = ORACLES.minimal_evidence_body
typed_evidence = ORACLES.typed_evidence


def native_phase_request(ts_out=False):
    member, expected = minimal_evidence_body(ts_out)
    path = (
        Path(__file__).resolve().parents[1]
        / "src/ai_trader/research/_native_member_execution_v1.json"
    )
    manifest_raw = path.read_bytes()
    manifest = json.loads(manifest_raw)
    assert ORACLES.canonical(manifest) == manifest_raw
    request = {
        "schema": "native_member_worker_request_v1",
        "operation": "decode",
        "context": context_body(ts_out),
        "member_hex": member.hex(),
        "expected_protocol_sha256": expected["protocol_sha256"],
        "expected_profile_sha256": expected["profile_sha256"],
        "expected_runtime_manifest_sha256": expected["runtime_manifest_sha256"],
        "expected_member_sha256": expected["member_sha256"],
        "expected_metadata_sha256": expected["metadata_sha256"],
        "execution_manifest_sha256": ORACLES.raw_digest(manifest_raw),
        "attempt_token": "3" * 64,
    }
    return request, manifest, member, expected


def fake_native_objects(ts_out=False, bomb=None):
    """Independent annotation-shaped doubles; never instantiate a native class."""

    class Schema(IntEnum):
        MBO = 0

        def __str__(self):
            return "mbo"

    class RType(IntEnum):
        MBO = 160

        def __str__(self):
            return "mbo"

    class SType(IntEnum):
        INSTRUMENT_ID = 0
        RAW_SYMBOL = 1

        def __str__(self):
            return "instrument_id" if self is SType.INSTRUMENT_ID else "raw_symbol"

    class Action(IntEnum):
        ADD = 65
        TRADE = 84

        def __str__(self):
            return chr(int(self))

    class Side(IntEnum):
        BID = 66
        ASK = 65

        def __str__(self):
            return chr(int(self))

    class Metadata:
        pass

    class MBOMsg:
        def __getattribute__(self, key):
            if key == bomb:
                raise AssertionError("deferred native MBO field: " + key)
            return object.__getattribute__(self, key)

        def record_size(self):
            return 64 if ts_out else 56

    class DBNError(Exception):
        pass

    class ZstdError(Exception):
        pass

    metadata = Metadata()
    metadata.version, metadata.dataset, metadata.schema = 3, "GLBX.MDP3", Schema.MBO
    metadata.start, metadata.end, metadata.limit = 100, None, None
    metadata.stype_in, metadata.stype_out = SType.RAW_SYMBOL, SType.INSTRUMENT_ID
    metadata.ts_out, metadata.symbol_cstr_len = ts_out, 71
    metadata.symbols, metadata.partial, metadata.not_found, metadata.mappings = [], [], [], {}
    records = []
    for instrument, order, price, event, received, action, side in (
        (1, 101, -125, 300, 290, Action.ADD, Side.BID),
        (999, 102, 250, 200, 400, Action.TRADE, Side.ASK),
    ):
        record = MBOMsg()
        record.rtype, record.publisher_id, record.instrument_id = RType.MBO, 7, instrument
        record.ts_event, record.order_id, record.price, record.size = event, order, price, 3
        record.action, record.side, record.ts_recv = action, side, received
        record.flags, record.channel_id, record.ts_in_delta, record.sequence = 128, 2, -9, 17
        record.ts_out = (1 << 64) - 2 if ts_out else (1 << 64) - 1
        record.ts_index = received
        records.append(record)
    dbn = SimpleNamespace(
        Schema=Schema,
        RType=RType,
        SType=SType,
        Action=Action,
        Side=Side,
        Metadata=Metadata,
        MBOMsg=MBOMsg,
        DBNError=DBNError,
        VersionUpgradePolicy=SimpleNamespace(AS_IS=object()),
        Compression=SimpleNamespace(NONE=object()),
    )
    return dbn, SimpleNamespace(ZstdError=ZstdError), metadata, records


def install_phase_fakes(monkeypatch, *, ts_out=False, bomb=None, metadata_mutation=None):
    engine = engine_module()
    request, manifest, member, expected = native_phase_request(ts_out)
    dbn, zstd, metadata, records = fake_native_objects(ts_out, bomb)
    trace = []
    raw = ORACLES.invented_raw_member(ts_out)

    class Decoder:
        def __init__(self, **kwargs):
            trace.append("dbn_constructor")
            assert kwargs == {
                "has_metadata": True,
                "ts_out": False,
                "input_version": None,
                "upgrade_policy": dbn.VersionUpgradePolicy.AS_IS,
                "compression": dbn.Compression.NONE,
            }
            self.written, self.delivered = b"", False

        def write(self, value):
            assert type(value) is bytes
            self.written += value

        def decode(self):
            if self.delivered:
                return []
            assert self.written == raw
            self.delivered = True
            return [metadata, *records]

        def write_and_decode(self, value):
            self.write(value)
            return self.decode()

        def buffer(self):
            return b""

    dbn.DBNDecoder = Decoder

    def load():
        trace.append("load")
        return dbn, zstd, deepcopy(expected["runtime_manifest"])

    def identity(actual_dbn, actual_zstd, runtime):
        assert actual_dbn is dbn and actual_zstd is zstd
        assert runtime == expected["runtime_manifest"]
        trace.append("identity")

    def decompress(actual, physical, actual_zstd):
        assert actual == member and actual_zstd is zstd
        assert physical == (ORACLES.raw_frame_expected(raw),)
        trace.append("zstd_constructor_boundary")
        return raw, deepcopy(expected["zstd_framing"]["frames"])

    def metadata_projection(value, actual_dbn):
        assert value is metadata and actual_dbn is dbn
        trace.append("metadata")
        body = deepcopy(expected["occurrences"][0]["projection"])
        if metadata_mutation is not None:
            field, replacement = metadata_mutation
            body[field] = replacement
        return body

    def mbo_projection(value, actual_dbn):
        assert actual_dbn is dbn
        # Explicit17 native observations, so every parametrized sentinel is real.
        observed = (
            value.rtype,
            value.publisher_id,
            value.instrument_id,
            value.ts_event,
            value.order_id,
            value.price,
            value.size,
            value.action,
            value.side,
            value.ts_recv,
            value.flags,
            value.channel_id,
            value.ts_in_delta,
            value.sequence,
            value.ts_out,
            value.record_size(),
            value.ts_index,
        )
        assert len(observed) == 17
        trace.append("mbo")
        index = 1 if value is records[0] else 2
        return deepcopy(expected["occurrences"][index]["projection"])

    monkeypatch.setattr(engine, "_load_native_runtime", load)
    monkeypatch.setattr(engine, "_check_native_identity", identity)
    monkeypatch.setattr(engine, "_decompress_frames", decompress)
    monkeypatch.setattr(engine, "_project_metadata", metadata_projection)
    monkeypatch.setattr(engine, "_project_mbo", mbo_projection)
    return engine, request, manifest, expected, trace, dbn, zstd


@pytest.mark.parametrize(
    "field",
    (
        "schema",
        "operation",
        "context",
        "member_hex",
        "expected_protocol_sha256",
        "expected_profile_sha256",
        "expected_runtime_manifest_sha256",
        "expected_member_sha256",
        "expected_metadata_sha256",
        "execution_manifest_sha256",
        "attempt_token",
    ),
)
def test_native_phase_request_shape_refused_before_loader(monkeypatch, field):
    engine = engine_module()
    request, manifest, _, _ = native_phase_request()
    request[field] = []

    def sentinel():
        raise AssertionError("native loader reached before complete request preflight")

    monkeypatch.setattr(engine, "_load_native_runtime", sentinel)
    with pytest.raises(ValueError):
        engine.decode_request(request, manifest)


@pytest.mark.parametrize(
    "field",
    (
        "expected_protocol_sha256",
        "expected_profile_sha256",
        "expected_runtime_manifest_sha256",
        "expected_member_sha256",
        "execution_manifest_sha256",
    ),
)
def test_native_phase_wrong_known_pin_refused_before_loader(monkeypatch, field):
    engine = engine_module()
    request, manifest, _, _ = native_phase_request()
    request[field] = "b" * 64

    def sentinel():
        raise AssertionError("native loader reached before complete known-pin check")

    monkeypatch.setattr(engine, "_load_native_runtime", sentinel)
    with pytest.raises((ValueError, RuntimeError)) as caught:
        engine.decode_request(request, manifest)
    assert type(caught.value) in (ValueError, RuntimeError)


@pytest.mark.parametrize("ts_out", (False, True))
def test_native_phase_complete_independent_evidence_and_identity_order(monkeypatch, ts_out):
    engine, request, manifest, expected, trace, _, _ = install_phase_fakes(
        monkeypatch, ts_out=ts_out
    )
    assert engine.decode_request(request, manifest) == expected
    assert trace[0] == "load" and trace[-1] == "identity"
    zstd_index, dbn_index = trace.index("zstd_constructor_boundary"), trace.index("dbn_constructor")
    assert "identity" in trace[1:zstd_index]
    assert "identity" in trace[zstd_index + 1 : dbn_index]
    assert trace.count("metadata") == 1 and trace.count("mbo") == 2
    assert trace.index("metadata") < trace.index("mbo")


MBO_DEFERRED_GETTERS = (
    "rtype",
    "publisher_id",
    "instrument_id",
    "ts_event",
    "order_id",
    "price",
    "size",
    "action",
    "side",
    "ts_recv",
    "flags",
    "channel_id",
    "ts_in_delta",
    "sequence",
    "ts_out",
    "record_size",
    "ts_index",
)


@pytest.mark.parametrize("getter", MBO_DEFERRED_GETTERS)
@pytest.mark.parametrize("refusal", ("metadata_pin", "metadata_version", "metadata_mode"))
def test_native_phase_metadata_refusal_precedes_every_mbo_getter(monkeypatch, getter, refusal):
    mutation = {
        "metadata_pin": None,
        "metadata_version": ("version", 2),
        "metadata_mode": ("ts_out", True),
    }[refusal]
    engine, request, manifest, _, trace, _, _ = install_phase_fakes(
        monkeypatch,
        bomb=getter,
        metadata_mutation=mutation,
    )
    if refusal == "metadata_pin":
        request["expected_metadata_sha256"] = "b" * 64
    with pytest.raises(ValueError):
        engine.decode_request(request, manifest)
    assert "metadata" in trace and "mbo" not in trace


@pytest.mark.parametrize("fault_type", (AssertionError, MemoryError, RuntimeError))
def test_native_phase_unknown_loader_fault_is_not_invalid_member(monkeypatch, fault_type):
    engine = engine_module()
    request, manifest, _, _ = native_phase_request()
    error = fault_type("independent sentinel")

    def loader():
        raise error

    monkeypatch.setattr(engine, "_load_native_runtime", loader)
    with pytest.raises(fault_type) as caught:
        engine.decode_request(request, manifest)
    assert caught.value is error


def test_native_phase_loaded_identity_failure_precedes_codec_constructor(monkeypatch):
    engine, request, manifest, _, trace, _, _ = install_phase_fakes(monkeypatch)

    def identity(*args):
        raise RuntimeError("independent loaded-identity mismatch")

    def codec(*args):
        raise AssertionError("codec reached before loaded identity")

    monkeypatch.setattr(engine, "_check_native_identity", identity)
    monkeypatch.setattr(engine, "_decompress_frames", codec)
    with pytest.raises(RuntimeError, match="independent loaded-identity mismatch"):
        engine.decode_request(request, manifest)
    assert "dbn_constructor" not in trace


@pytest.mark.parametrize("ts_out", (False, True))
def test_native_phase_exact_metadata_and_mbo_projection_literals(ts_out):
    dbn, _, metadata, records = fake_native_objects(ts_out)
    _, expected = minimal_evidence_body(ts_out)
    engine = engine_module()
    assert engine._project_metadata(metadata, dbn) == expected["occurrences"][0]["projection"]
    for index, record in enumerate(records, 1):
        assert engine._project_mbo(record, dbn) == expected["occurrences"][index]["projection"]


def test_native_phase_mapping_dates_sorted_groups_and_unknown_char_literals():
    dbn, _, metadata, records = fake_native_objects()
    metadata.symbols, metadata.partial, metadata.not_found = ["Z", "A"], ["P"], ["N"]
    interval = {"start_date": date(2024, 2, 29), "end_date": date(2024, 3, 1), "symbol": "42"}
    metadata.mappings = {"Z": [deepcopy(interval), deepcopy(interval)], "A": [deepcopy(interval)]}
    _, expected = minimal_evidence_body()
    body = deepcopy(expected["occurrences"][0]["projection"])
    projected_interval = {
        "start_date": {"kind": "python_date", "year": 2024, "month": 2, "day": 29},
        "end_date": {"kind": "python_date", "year": 2024, "month": 3, "day": 1},
        "symbol": "42",
    }
    body.update(
        symbols=["Z", "A"],
        partial=["P"],
        not_found=["N"],
        mappings=[
            {"raw_symbol": "A", "intervals": [deepcopy(projected_interval)]},
            {
                "raw_symbol": "Z",
                "intervals": [deepcopy(projected_interval), deepcopy(projected_interval)],
            },
        ],
    )
    assert engine_module()._project_metadata(metadata, dbn) == body
    record = records[0]
    record.action, record.side = "?", "!"
    mbo = deepcopy(expected["occurrences"][1]["projection"])
    mbo.update(action={"kind": "str", "value": "?"}, side={"kind": "str", "value": "!"})
    assert engine_module()._project_mbo(record, dbn) == mbo


class IntAlias(int):
    pass


class StrAlias(str):
    pass


class BytesAlias(bytes):
    pass


class RefuseCoercion:
    def __str__(self):
        raise AssertionError("caller string hook was read")

    def __int__(self):
        raise AssertionError("caller integer hook was read")

    def __bool__(self):
        raise AssertionError("caller truthiness hook was read")


def provider_module():
    module_name = "ai_trader.research.six_e_native_member_decode_evidence"
    assert importlib.util.find_spec(module_name) is not None, "provider is not implemented"
    return importlib.import_module(module_name)


def context(provider, ts_out=False):
    return provider.MemberDecodeContext(**context_body(ts_out))


def dispatch_sentinel(*args, **kwargs):
    raise AssertionError("contained dispatch was reached")


def test_provider_exposes_complete_registered_public_interface():
    module_name = "ai_trader.research.six_e_native_member_decode_evidence"
    spec = importlib.util.find_spec(module_name)
    assert spec is not None, "the registered native-member provider is not implemented"
    provider = importlib.import_module(module_name)
    expected_names = (
        "protocol",
        "protocol_sha256",
        "context_sha256",
        "decode_member",
        "verify",
        "SchemaMbo",
        "RtypeMbo",
        "SType",
        "Action",
        "Side",
        "UnknownChar",
        "PythonDate",
        "WireMappingInterval",
        "MappingInterval",
        "MappingGroup",
        "WireMappingGroup",
        "MetadataWireBody",
        "MetadataProjection",
        "MboWireBody",
        "MboObservation",
        "MemberDecodeContext",
        "DecodedOccurrence",
        "FrameSpan",
        "ZstdFramingReport",
        "WireSpan",
        "DbnFramingReport",
        "TerminalEvidence",
        "Interpreter",
        "Package",
        "Artifact",
        "RuntimeManifest",
        "MemberDecodeEvidence",
    )
    assert all(callable(getattr(provider, name, None)) for name in expected_names)


def test_protocol_is_complete_normative_literal_and_full_hash():
    provider = provider_module()
    expected = protocol_literal()
    assert provider.protocol() == expected
    assert provider.protocol_sha256() == digest(expected)


def test_protocol_returns_fresh_deeply_independent_trees():
    provider = provider_module()
    first = provider.protocol()
    second = provider.protocol()
    first["schemas"]["U64"]["maximum_decimal"] = "1"
    first["authority_names"].append("invented_authority")
    first["decoder_options"]["dbn"]["has_metadata"] = False
    assert second == protocol_literal()
    assert provider.protocol() == protocol_literal()
    assert provider.protocol_sha256() == digest(protocol_literal())


@pytest.mark.parametrize("record_name,fields", list(RECORD_FIELDS.items()), ids=RECORD_FIELDS)
def test_registered_records_have_exact_constructor_fields_frozen_slots(record_name, fields):
    record = getattr(provider_module(), record_name)
    assert tuple(inspect.signature(record).parameters) == fields
    assert tuple(record.__slots__) == fields
    assert record.__dataclass_params__.frozen is True


@pytest.mark.parametrize(
    "api,positional,keyword_only",
    [
        ("protocol", (), ()),
        ("protocol_sha256", (), ()),
        ("context_sha256", ("context",), ("expected_protocol_sha256",)),
        (
            "decode_member",
            ("member_bytes", "context"),
            (
                "expected_protocol_sha256",
                "expected_profile_sha256",
                "expected_runtime_manifest_sha256",
                "expected_member_sha256",
                "expected_metadata_sha256",
            ),
        ),
        (
            "verify",
            ("evidence", "member_bytes", "context"),
            (
                "expected_protocol_sha256",
                "expected_profile_sha256",
                "expected_runtime_manifest_sha256",
                "expected_member_sha256",
                "expected_metadata_sha256",
                "expected_evidence_sha256",
            ),
        ),
    ],
)
def test_public_signatures_are_exact_and_pins_mandatory(api, positional, keyword_only):
    parameters = inspect.signature(getattr(provider_module(), api)).parameters
    assert tuple(parameters) == positional + keyword_only
    for name in positional:
        assert parameters[name].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert parameters[name].default is inspect.Parameter.empty
    for name in keyword_only:
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert parameters[name].default is inspect.Parameter.empty


@pytest.mark.parametrize("ts_out", [False, True], ids=["absent", "present"])
def test_context_complete_canonical_identity(ts_out):
    provider = provider_module()
    value = context(provider, ts_out)
    assert provider.context_sha256(
        value, expected_protocol_sha256=digest(protocol_literal())
    ) == digest(context_body(ts_out))
    assert not hasattr(value, "__dict__")
    with pytest.raises(FrozenInstanceError):
        value.expected_ts_out = not ts_out


CONTEXT_BAD_VALUES = (
    ("profile_id", "other"),
    ("profile_id", StrAlias(context_body()["profile_id"])),
    ("profile_id", RefuseCoercion()),
    ("member_compression", "GZIP"),
    ("member_compression", "gzip"),
    ("member_compression", StrAlias("ZSTD_CONCAT")),
    ("input_version", 2),
    ("input_version", 4),
    ("input_version", True),
    ("input_version", 3.0),
    ("input_version", IntAlias(3)),
    ("input_version", RefuseCoercion()),
    ("upgrade_policy", "UPGRADE_TO_V3"),
    ("upgrade_policy", StrAlias("AS_IS")),
    ("expected_ts_out", 0),
    ("expected_ts_out", 1),
    ("expected_ts_out", None),
    ("expected_ts_out", "false"),
    ("expected_ts_out", RefuseCoercion()),
)


@pytest.mark.parametrize(
    "field,bad",
    CONTEXT_BAD_VALUES,
    ids=[f"{field}-{index}" for index, (field, _) in enumerate(CONTEXT_BAD_VALUES)],
)
def test_context_rejects_wrong_domains_and_equal_value_aliases(field, bad):
    provider = provider_module()
    bad_context = replace(context(provider), **{field: bad})
    with pytest.raises(ValueError):
        provider.context_sha256(bad_context, expected_protocol_sha256=digest(protocol_literal()))


@pytest.mark.parametrize("kind", ["dict", "subclass", "object", "none"])
def test_context_requires_exact_registered_class(kind):
    provider = provider_module()
    if kind == "dict":
        bad = context_body()
    elif kind == "subclass":
        alias = type("ContextAlias", (provider.MemberDecodeContext,), {})
        bad = alias(**context_body())
    elif kind == "object":
        bad = RefuseCoercion()
    else:
        bad = None
    with pytest.raises(ValueError):
        provider.context_sha256(bad, expected_protocol_sha256=digest(protocol_literal()))


PIN_BAD_VALUES = (
    None,
    True,
    1,
    b"0" * 64,
    "",
    "0" * 63,
    "0" * 65,
    "A" * 64,
    "g" * 64,
    "０" * 64,
    StrAlias("0" * 64),
    RefuseCoercion(),
)
DECODE_PIN_NAMES = (
    "expected_protocol_sha256",
    "expected_profile_sha256",
    "expected_runtime_manifest_sha256",
    "expected_member_sha256",
    "expected_metadata_sha256",
)


@pytest.mark.parametrize("pin_name", DECODE_PIN_NAMES)
@pytest.mark.parametrize("bad", PIN_BAD_VALUES, ids=[f"bad{n}" for n in range(len(PIN_BAD_VALUES))])
def test_decode_pin_syntax_refuses_before_dispatch(monkeypatch, pin_name, bad):
    provider = provider_module()
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    pins = expected_pins()
    pins[pin_name] = bad
    with pytest.raises(ValueError):
        provider.decode_member(b"invented-preflight-input", context(provider), **pins)


@pytest.mark.parametrize(
    "pin_name",
    [
        "expected_protocol_sha256",
        "expected_profile_sha256",
        "expected_runtime_manifest_sha256",
        "expected_member_sha256",
    ],
)
def test_decode_known_pin_mismatch_refuses_before_dispatch(monkeypatch, pin_name):
    provider = provider_module()
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    pins = expected_pins()
    pins[pin_name] = "0" * 64
    with pytest.raises(ValueError):
        provider.decode_member(b"invented-preflight-input", context(provider), **pins)


@pytest.mark.parametrize("ts_out", [False, True])
def test_valid_preflight_reaches_dispatch_without_early_metadata_equality(monkeypatch, ts_out):
    provider = provider_module()
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(AssertionError, match="contained dispatch was reached"):
        provider.decode_member(
            b"invented-preflight-input", context(provider, ts_out), **expected_pins()
        )


@pytest.mark.parametrize(
    "field,bad",
    CONTEXT_BAD_VALUES,
    ids=[f"{field}-{index}" for index, (field, _) in enumerate(CONTEXT_BAD_VALUES)],
)
def test_decode_complete_context_refuses_before_dispatch(monkeypatch, field, bad):
    provider = provider_module()
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    bad_context = replace(context(provider), **{field: bad})
    with pytest.raises(ValueError):
        provider.decode_member(b"invented-preflight-input", bad_context, **expected_pins())


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "not-a-path",
        bytearray(b"x"),
        memoryview(b"x"),
        BytesAlias(b"x"),
        [],
        iter((b"x",)),
        RefuseCoercion(),
    ],
    ids=["none", "path", "bytearray", "view", "bytes-alias", "list", "iterator", "hooks"],
)
def test_member_requires_exact_immutable_bytes_before_dispatch(monkeypatch, bad):
    provider = provider_module()
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(ValueError):
        provider.decode_member(bad, context(provider), **expected_pins())


@pytest.mark.parametrize("member", [b"", b"x" * 262145], ids=["empty", "first-excess"])
def test_member_complete_byte_cap_refuses_before_dispatch(monkeypatch, member):
    provider = provider_module()
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(ValueError):
        provider.decode_member(member, context(provider), **expected_pins(member))


@pytest.mark.parametrize("size", [1, 262144], ids=["minimum", "maximum"])
def test_member_accepted_byte_bounds_reach_dispatch(monkeypatch, size):
    provider = provider_module()
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    member = b"x" * size
    with pytest.raises(AssertionError, match="contained dispatch was reached"):
        provider.decode_member(member, context(provider), **expected_pins(member))


@pytest.mark.parametrize(
    "bad", [None, {}, (), RefuseCoercion()], ids=["none", "dict", "tuple", "hook"]
)
def test_verify_outer_record_refuses_before_dispatch(monkeypatch, bad):
    provider = provider_module()
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(ValueError):
        provider.verify(
            bad,
            b"invented-preflight-input",
            context(provider),
            **expected_pins(),
            expected_evidence_sha256="e" * 64,
        )


def evidence_case(provider, ts_out=False):
    member, body = minimal_evidence_body(ts_out)
    pins = {
        "expected_protocol_sha256": body["protocol_sha256"],
        "expected_profile_sha256": body["profile_sha256"],
        "expected_runtime_manifest_sha256": body["runtime_manifest_sha256"],
        "expected_member_sha256": body["member_sha256"],
        "expected_metadata_sha256": body["metadata_sha256"],
        "expected_evidence_sha256": body["evidence_sha256"],
    }
    return member, body, typed_evidence(provider, body), pins


def changed_record_at(record, path, value):
    result = deepcopy(record)
    target = result
    for part in path[:-1]:
        target = target[part] if type(part) is int else getattr(target, part)
    object.__setattr__(target, path[-1], value)
    return result


def value_at(record, path):
    for part in path:
        record = record[part] if type(part) is int else getattr(record, part)
    return record


@pytest.mark.parametrize("ts_out", [False, True], ids=["absent", "present"])
def test_verify_valid_complete_literal_body_reaches_fresh_dispatch(monkeypatch, ts_out):
    provider = provider_module()
    member, _, evidence, pins = evidence_case(provider, ts_out)
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(AssertionError, match="contained dispatch was reached"):
        provider.verify(evidence, member, context(provider, ts_out), **pins)


@pytest.mark.parametrize("pin_name", (*DECODE_PIN_NAMES, "expected_evidence_sha256"))
@pytest.mark.parametrize("bad", PIN_BAD_VALUES, ids=[f"bad{n}" for n in range(len(PIN_BAD_VALUES))])
def test_verify_all_pin_syntax_refuses_before_dispatch(monkeypatch, pin_name, bad):
    provider = provider_module()
    member, _, evidence, pins = evidence_case(provider)
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    pins[pin_name] = bad
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider), **pins)


@pytest.mark.parametrize("pin_name", (*DECODE_PIN_NAMES, "expected_evidence_sha256"))
def test_verify_all_held_expected_pin_mismatches_refuse_before_dispatch(monkeypatch, pin_name):
    provider = provider_module()
    member, _, evidence, pins = evidence_case(provider)
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    pins[pin_name] = "0" * 64
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider), **pins)


@pytest.mark.parametrize("authority_index", range(28))
@pytest.mark.parametrize("bad_flag", [True, 0, None], ids=["true", "integer-zero", "none"])
def test_every_submitted_authority_is_literal_false_before_dispatch(
    monkeypatch, authority_index, bad_flag
):
    provider = provider_module()
    member, _, evidence, pins = evidence_case(provider)
    entries = list(evidence.authorities)
    entries[authority_index] = (entries[authority_index][0], bad_flag)
    evidence = replace(evidence, authorities=tuple(entries))
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider), **pins)


SUBMITTED_TUPLE_PATHS = (
    ("occurrences",),
    ("authorities",),
    ("runtime_manifest", "packages"),
    ("runtime_manifest", "artifacts"),
    ("runtime_manifest", "interpreter", "version"),
    ("zstd_framing", "frames"),
    ("dbn_framing", "spans"),
    ("occurrences", 0, "projection", "symbols"),
    ("occurrences", 0, "projection", "partial"),
    ("occurrences", 0, "projection", "not_found"),
    ("occurrences", 0, "projection", "mappings"),
    ("dbn_framing", "spans", 0, "wire_fields", "reserved_bytes"),
    ("dbn_framing", "spans", 0, "wire_fields", "symbols"),
    ("dbn_framing", "spans", 0, "wire_fields", "partial"),
    ("dbn_framing", "spans", 0, "wire_fields", "not_found"),
    ("dbn_framing", "spans", 0, "wire_fields", "mappings"),
    ("dbn_framing", "spans", 0, "wire_fields", "alignment_padding_bytes"),
)


@pytest.mark.parametrize("path", SUBMITTED_TUPLE_PATHS, ids=lambda path: ".".join(map(str, path)))
def test_submitted_equal_canonical_list_aliases_refuse_before_dispatch(monkeypatch, path):
    provider = provider_module()
    member, _, evidence, pins = evidence_case(provider)
    evidence = changed_record_at(evidence, path, list(value_at(evidence, path)))
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider), **pins)


SUBMITTED_SCALAR_PATHS = (
    *(
        (field,)
        for field in (
            "status",
            "protocol_sha256",
            "profile_sha256",
            "runtime_manifest_sha256",
            "context_sha256",
            "member_sha256",
            "metadata_sha256",
            "evidence_sha256",
        )
    ),
    ("runtime_manifest", "schema"),
    ("runtime_manifest", "interpreter", "implementation"),
    ("runtime_manifest", "interpreter", "executable_sha256"),
    *(
        ("runtime_manifest", "packages", 0, field)
        for field in ("name", "version", "metadata_sha256")
    ),
    *(
        ("runtime_manifest", "artifacts", 0, field)
        for field in (
            "logical_id",
            "kind",
            "raw_bytes",
            "raw_sha256",
        )
    ),
    *(
        ("occurrences", 0, field)
        for field in (
            "decoded_position",
            "kind",
            "wire_span_ordinal",
            "projection_sha256",
        )
    ),
    *(
        ("occurrences", 0, "projection", field)
        for field in (
            "version",
            "dataset",
            "start",
            "symbol_cstr_len",
        )
    ),
    *(
        ("occurrences", 0, "projection", "schema", field)
        for field in (
            "kind",
            "class_name",
            "name",
            "code",
            "text",
        )
    ),
    *(
        ("occurrences", 0, "projection", "stype_in", field)
        for field in (
            "kind",
            "class_name",
            "name",
            "code",
            "text",
        )
    ),
    *(
        ("occurrences", 1, "projection", field)
        for field in (
            "publisher_id",
            "instrument_id",
            "ts_event",
            "order_id",
            "price",
            "size",
            "ts_recv",
            "flags",
            "channel_id",
            "ts_in_delta",
            "sequence",
            "ts_out_observed",
            "record_size_observed",
            "ts_index_observed",
        )
    ),
    *(
        ("occurrences", 1, "projection", enum, field)
        for enum in ("rtype", "action", "side")
        for field in ("kind", "class_name", "name", "code", "text")
    ),
    *(
        ("zstd_framing", field)
        for field in (
            "compressed_bytes",
            "compressed_sha256",
            "decompressed_bytes",
            "decompressed_sha256",
            "report_sha256",
        )
    ),
    *(("zstd_framing", "frames", 0, field) for field in RECORD_FIELDS["FrameSpan"]),
    *(
        ("dbn_framing", field)
        for field in (
            "decompressed_bytes",
            "decompressed_sha256",
            "report_sha256",
        )
    ),
    *(
        ("dbn_framing", "spans", 0, field)
        for field in (
            "wire_span_ordinal",
            "kind",
            "decompressed_start",
            "decompressed_end",
            "wire_sha256",
            "wire_fields_sha256",
        )
    ),
    *(
        ("dbn_framing", "spans", 0, "wire_fields", field)
        for field in (
            "magic_hex",
            "version",
            "length_body",
            "dataset",
            "dataset_cstr_bytes",
            "schema",
            "start",
            "end",
            "limit",
            "stype_in",
            "stype_out",
            "ts_out",
            "symbol_cstr_len",
            "schema_definition_length",
            "symbols_count",
            "partial_count",
            "not_found_count",
            "mappings_count",
        )
    ),
    *(
        ("dbn_framing", "spans", 1, "wire_fields", field)
        for field in RECORD_FIELDS["MboWireBody"]
        if field != "ts_out"
    ),
    *(("terminal", field) for field in RECORD_FIELDS["TerminalEvidence"]),
)


@pytest.mark.parametrize("path", SUBMITTED_SCALAR_PATHS, ids=lambda path: ".".join(map(str, path)))
def test_submitted_equal_canonical_scalar_aliases_refuse_before_dispatch(monkeypatch, path):
    provider = provider_module()
    member, _, evidence, pins = evidence_case(provider)
    original = value_at(evidence, path)
    assert type(original) in (str, int)
    alias = StrAlias(original) if type(original) is str else IntAlias(original)
    evidence = changed_record_at(evidence, path, alias)
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider), **pins)


@pytest.mark.parametrize("field", ["status", "protocol_sha256", "profile_sha256", "context_sha256"])
def test_submitted_rehashed_wrong_outer_identity_refuses_before_dispatch(monkeypatch, field):
    provider = provider_module()
    member, body, _, pins = evidence_case(provider)
    body[field] = "wrong_status" if field == "status" else "0" * 64
    body["evidence_sha256"] = digest(
        {key: value for key, value in body.items() if key != "evidence_sha256"}
    )
    evidence = typed_evidence(provider, body)
    pins["expected_evidence_sha256"] = body["evidence_sha256"]
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider), **pins)


@pytest.mark.parametrize("shape", ["missing", "duplicate", "reverse", "inner-list"])
def test_submitted_complete_authority_tuple_shape_refuses_before_dispatch(monkeypatch, shape):
    provider = provider_module()
    member, _, evidence, pins = evidence_case(provider)
    entries = evidence.authorities
    if shape == "missing":
        entries = entries[:-1]
    elif shape == "duplicate":
        entries = (entries[0],) + entries[:-1]
    elif shape == "reverse":
        entries = entries[::-1]
    else:
        entries = (list(entries[0]),) + entries[1:]
    evidence = replace(evidence, authorities=entries)
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider), **pins)


@pytest.mark.parametrize("field", RECORD_FIELDS["TerminalEvidence"])
def test_submitted_terminal_wrong_family_refuses_before_dispatch(monkeypatch, field):
    provider = provider_module()
    member, _, evidence, pins = evidence_case(provider)
    evidence = replace(evidence, terminal=replace(evidence.terminal, **{field: RefuseCoercion()}))
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider), **pins)


def test_private_engine_exposes_independent_complete_framers():
    module_name = "ai_trader.research._native_member_engine"
    assert importlib.util.find_spec(module_name) is not None, "private framers are not implemented"
    engine = importlib.import_module(module_name)
    assert callable(getattr(engine, "inspect_dbn_wire", None))
    assert callable(getattr(engine, "inspect_zstd_frames", None))


def test_private_host_exposes_fixed_contained_decode():
    module_name = "ai_trader.research._native_member_host"
    assert importlib.util.find_spec(module_name) is not None, (
        "contained provider host is not implemented"
    )
    host = importlib.import_module(module_name)
    assert callable(getattr(host, "run_decode", None))


@pytest.mark.parametrize("ts_out", [False, True], ids=["absent", "present"])
def test_decode_private_response_reconstructs_every_explicit_public_field(monkeypatch, ts_out):
    provider = provider_module()
    member, body, expected, pins = evidence_case(provider, ts_out)
    decode_pins = {key: value for key, value in pins.items() if key != "expected_evidence_sha256"}
    calls = []

    def independent_response(raw, supplied_context, supplied_pins):
        calls.append((raw, supplied_context, supplied_pins))
        return deepcopy(body)

    monkeypatch.setattr(provider, "_dispatch_decode", independent_response)
    actual = provider.decode_member(member, context(provider, ts_out), **decode_pins)
    assert actual == expected
    assert type(actual) is provider.MemberDecodeEvidence
    assert calls == [(member, context_body(ts_out), decode_pins)]


def test_verify_reconstructs_fresh_on_each_call_and_returns_none(monkeypatch):
    provider = provider_module()
    member, body, evidence, pins = evidence_case(provider)
    calls = []

    def independent_response(raw, supplied_context, supplied_pins):
        calls.append((raw, supplied_context, supplied_pins))
        return deepcopy(body)

    monkeypatch.setattr(provider, "_dispatch_decode", independent_response)
    assert provider.verify(evidence, member, context(provider), **pins) is None
    assert provider.verify(evidence, member, context(provider), **pins) is None
    decode_pins = {key: value for key, value in pins.items() if key != "expected_evidence_sha256"}
    assert calls == [(member, context_body(), decode_pins), (member, context_body(), decode_pins)]


@pytest.mark.parametrize("occurrence", [1, 2], ids=["target", "foreign"])
def test_verify_rebuilds_and_rejects_coherently_rehashed_false_raw_price(monkeypatch, occurrence):
    provider = provider_module()
    member, body, _, pins = evidence_case(provider)
    false_body = deepcopy(body)
    false_body["occurrences"][occurrence]["projection"]["price"] += 1
    false_body["dbn_framing"]["spans"][occurrence]["wire_fields"]["price"] += 1
    ORACLES.rehash_evidence(false_body)
    evidence = typed_evidence(provider, false_body)
    pins["expected_evidence_sha256"] = false_body["evidence_sha256"]
    calls = []

    def independent_response(*args):
        calls.append(args)
        return deepcopy(body)

    monkeypatch.setattr(provider, "_dispatch_decode", independent_response)
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider), **pins)
    assert len(calls) == 1, "fresh complete reconstruction is mandatory for coherent false bodies"


def test_decode_rejects_complete_response_bound_to_another_member(monkeypatch):
    provider = provider_module()
    member, body, _, pins = evidence_case(provider)
    body["member_sha256"] = "0" * 64
    ORACLES.rehash_evidence(body)
    monkeypatch.setattr(provider, "_dispatch_decode", lambda *args: deepcopy(body))
    decode_pins = {key: value for key, value in pins.items() if key != "expected_evidence_sha256"}
    with pytest.raises(ValueError):
        provider.decode_member(member, context(provider), **decode_pins)


def engine_module():
    name = "ai_trader.research._native_member_engine"
    assert importlib.util.find_spec(name) is not None, "private engine is not implemented"
    return importlib.import_module(name)


@pytest.mark.parametrize("ts_out", [False, True], ids=["absent", "present"])
def test_dbn_framer_retains_complete_independent_wire_bodies_and_field_ledgers(ts_out):
    raw = ORACLES.invented_raw_member(ts_out)
    expected = ORACLES.minimal_dbn_framing_expected(ts_out)
    assert engine_module().inspect_dbn_wire(raw) == expected


@pytest.mark.parametrize(
    "length",
    [
        0,
        1,
        3,
        4,
        7,
        8,
        24,
        55,
        107,
        108,
        111,
        112,
        115,
        119,
        123,
        127,
        128,
        129,
        151,
        183,
        185,
        200,
        239,
    ],
)
def test_dbn_framer_rejects_incomplete_header_record_and_tail(length):
    with pytest.raises(ValueError):
        engine_module().inspect_dbn_wire(ORACLES.invented_raw_member()[:length])


@pytest.mark.parametrize(
    "start,patch",
    [
        (0, b"ZIP"),
        (3, b"\x02"),
        (3, b"\x04"),
        (4, (112).to_bytes(4, "little")),
        (4, (121).to_bytes(4, "little")),
        (4, (65536).to_bytes(4, "little")),
        (24, b"\x01\x00"),
        (50, b"\x10"),
        (51, b"\xff"),
        (52, b"\x02"),
        (53, b"\x46\x00"),
        (55, b"\x01"),
        (107, b"\x01"),
        (108, b"\x01"),
        (112, (17).to_bytes(4, "little")),
        (116, (17).to_bytes(4, "little")),
        (120, (17).to_bytes(4, "little")),
        (124, (17).to_bytes(4, "little")),
        (128, b"\x10"),
        (129, b"\x01"),
        (184, b"\x10"),
        (185, b"\x01"),
        (8, b"x" * 16),
        (9, b"\x00x"),
        (8, b"\xff"),
    ],
    ids=[f"wire-mutation-{n}" for n in range(25)],
)
def test_dbn_framer_rejects_complete_unsupported_fields(start, patch):
    raw = ORACLES.invented_raw_member()
    changed = raw[:start] + patch + raw[start + len(patch) :]
    with pytest.raises(ValueError):
        engine_module().inspect_dbn_wire(changed)


@pytest.mark.parametrize("ts_out", [False, True])
def test_dbn_framer_exact_complete_position_cap_and_first_excess(ts_out):
    raw = ORACLES.invented_raw_member(ts_out)
    size = 64 if ts_out else 56
    record = raw[128 : 128 + size]
    maximum = raw[:128] + record * 127
    result = engine_module().inspect_dbn_wire(maximum)
    assert result["complete_bytes"] == 128 + 127 * size
    assert (
        len(result["wire_spans"]) == len(result["wire_bodies"]) == len(result["field_spans"]) == 128
    )
    with pytest.raises(ValueError):
        engine_module().inspect_dbn_wire(maximum + record)


@pytest.mark.parametrize("ts_out", [False, True], ids=["absent", "present"])
def test_zstd_framer_complete_literal_raw_frame(ts_out):
    raw = ORACLES.invented_raw_member(ts_out)
    compressed = ORACLES.raw_zstd_frame(raw)
    assert engine_module().inspect_zstd_frames(compressed) == (ORACLES.raw_frame_expected(raw),)


def test_zstd_framer_retains_two_cross_structure_frames_with_absolute_offsets():
    raw = ORACLES.invented_raw_member()
    first, second = raw[:131], raw[131:]
    encoded_first = ORACLES.raw_zstd_frame(first)
    encoded_second = ORACLES.raw_zstd_frame(second)
    expected = (
        ORACLES.raw_frame_expected(first),
        ORACLES.raw_frame_expected(second, ordinal=2, start=len(encoded_first)),
    )
    assert engine_module().inspect_zstd_frames(encoded_first + encoded_second) == expected


def test_zstd_framer_retains_unknown_size_header_and_exact_raw_block():
    raw = ORACLES.invented_raw_member()
    encoded = b"\x28\xb5\x2f\xfd\x00\x00" + ((len(raw) << 3) | 1).to_bytes(3, "little") + raw
    expected = (
        (
            1,
            0,
            249,
            0,
            6,
            0,
            0,
            0,
            False,
            0,
            False,
            None,
            1024,
            None,
            None,
            ((1, 6, 9, True, 0, 240, 9, 249),),
        ),
    )
    assert engine_module().inspect_zstd_frames(encoded) == expected


def test_zstd_physical_framer_does_not_claim_checksum_semantics():
    raw = b"abc"
    encoded = b"\x28\xb5\x2f\xfd\x24\x03\x19\x00\x00abc\x78\x56\x34\x12"
    expected = (
        (
            1,
            0,
            16,
            0,
            6,
            36,
            None,
            0,
            True,
            0,
            True,
            3,
            3,
            None,
            0x12345678,
            ((1, 6, 9, True, 0, 3, 9, 12),),
        ),
    )
    assert len(raw) == 3
    assert engine_module().inspect_zstd_frames(encoded) == expected


@pytest.mark.parametrize("descriptor", [1, 2, 3, 8, 16, 24, 33, 34, 35, 40, 48])
def test_zstd_framer_refuses_dictionary_reserved_and_unused_header_modes(descriptor):
    encoded = bytearray(ORACLES.raw_zstd_frame(b"abc"))
    encoded[4] = descriptor
    with pytest.raises(ValueError):
        engine_module().inspect_zstd_frames(bytes(encoded))


@pytest.mark.parametrize("length", range(12))
def test_zstd_framer_refuses_incomplete_last_frame(length):
    encoded = ORACLES.raw_zstd_frame(b"abc")
    with pytest.raises(ValueError):
        engine_module().inspect_zstd_frames(encoded[:length])


@pytest.mark.parametrize("tail", [b"x", b"\x28\xb5", b"\x50\x2a\x4d\x18\x00\x00\x00\x00"])
def test_zstd_framer_refuses_any_extra_nonstandard_tail(tail):
    encoded = ORACLES.raw_zstd_frame(b"abc")
    with pytest.raises(ValueError):
        engine_module().inspect_zstd_frames(encoded + tail)


def test_zstd_framer_exact_frame_cap_and_first_excess():
    encoded = ORACLES.raw_zstd_frame(b"x")
    expected = tuple(
        ORACLES.raw_frame_expected(b"x", ordinal=n + 1, start=n * len(encoded)) for n in range(16)
    )
    assert engine_module().inspect_zstd_frames(encoded * 16) == expected
    with pytest.raises(ValueError):
        engine_module().inspect_zstd_frames(encoded * 17)


@pytest.mark.parametrize(
    "encoded",
    [
        b"\x28\xb5\x2f\xfd\x20\x00\x01\x00\x00",
        b"\x28\xb5\x2f\xfd\x00\x58\x01\x00\x00",
        b"\x28\xb5\x2f\xfd\xa0\x01\x00\x10\x00\x01\x00\x00",
        b"\x28\xb5\x2f\xfd\x20\x01\x07\x00\x00",
        b"\x28\xb5\x2f\xfd\x20\x01\x11\x00\x00xx",
    ],
    ids=["known-empty", "window-over", "known-output-over", "reserved-block", "block-over-window"],
)
def test_zstd_framer_refuses_structural_and_declared_resource_excess(encoded):
    with pytest.raises(ValueError):
        engine_module().inspect_zstd_frames(encoded)


@pytest.mark.parametrize("entry", ["inspect_dbn_wire", "inspect_zstd_frames"])
@pytest.mark.parametrize("bad", [None, bytearray(b"x"), memoryview(b"x"), BytesAlias(b"x"), "x"])
def test_independent_framers_require_exact_complete_immutable_bytes(entry, bad):
    with pytest.raises(ValueError):
        getattr(engine_module(), entry)(bad)


def fake_decompression_case(outputs, *, declared=None, mode="valid", failure=None):
    """In-memory codec double: tests wrapper policy, never codec correctness.

    Large outputs deliberately use tiny marker frames and unknown FCS because
    this seam tests bounded reading, not a native decompression assertion.
    """
    encoded, physical, offset = [], [], 0
    for index, output in enumerate(outputs, 1):
        marker = output if 0 < len(output) < 65536 else b"invented-frame-marker"
        compressed = ORACLES.raw_zstd_frame(marker)
        row = list(ORACLES.raw_frame_expected(marker, index, offset))
        row[11] = None if declared is None else declared[index - 1]
        physical.append(tuple(row))
        encoded.append(compressed)
        offset += len(compressed)
    visits, instances = [], []

    class ZstdError(Exception):
        pass

    class Decoder:
        def __init__(self, *, max_window_size):
            assert max_window_size == 1048576
            self.index, self.closed = len(instances), False
            instances.append(self)
            visits.append(("constructor", self.index, max_window_size))
            if mode == "constructor_fault":
                raise failure

        def stream_reader(self, source, *, read_across_frames, read_size):
            assert read_across_frames is False and read_size == 65536
            assert source.getvalue() == encoded[self.index]
            if mode != "source_not_consumed":
                assert source.read() == encoded[self.index]
            owner, output, position = self, outputs[self.index], 0

            class Reader:
                def __enter__(self):
                    visits.append(("reader_enter", owner.index))
                    return self

                def __exit__(self, kind, value, traceback):
                    owner.closed = True
                    visits.append(("reader_exit", owner.index))

                def read(self, count):
                    nonlocal position
                    assert type(count) is int and 1 <= count <= 65536
                    visits.append(("read", owner.index, count))
                    if mode == "read_fault":
                        raise failure
                    if mode == "codec_read_fault":
                        raise ZstdError("declared codec refusal")
                    if mode == "oversized_chunk":
                        return b"x" * (count + 1)
                    if mode == "nonbytes_chunk":
                        return bytearray(b"x")
                    part = output[position : position + count]
                    position += len(part)
                    return part

            return Reader()

        def decompress(self, raw, *, max_output_size, read_across_frames, allow_extra_data):
            assert self.closed, "terminal decode must follow complete stream closure"
            assert raw == encoded[self.index]
            assert max_output_size == len(outputs[self.index]) and max_output_size > 0
            assert read_across_frames is False and allow_extra_data is False
            visits.append(("terminal", self.index, max_output_size))
            if mode == "terminal_fault":
                raise failure
            if mode == "codec_terminal_fault":
                raise ZstdError("declared terminal refusal")
            if mode == "terminal_mismatch":
                return outputs[self.index] + b"x"
            if mode == "nonbytes_terminal":
                return bytearray(outputs[self.index])
            return outputs[self.index]

    zstd = SimpleNamespace(ZstdDecompressor=Decoder, ZstdError=ZstdError)
    return b"".join(encoded), tuple(physical), zstd, visits, instances


@pytest.mark.parametrize("outputs", ((b"abc",), (b"first", b"second"), (b"x" * 1048576,)))
def test_native_decompression_complete_frames_use_same_decoder_and_exact_terminal_allocation(
    outputs,
):
    member, physical, fake, visits, instances = fake_decompression_case(outputs)
    actual, spans = engine_module()._decompress_frames(member, physical, fake)
    assert actual == b"".join(outputs)
    expected, begin = [], 0
    for index, (row, output) in enumerate(zip(physical, outputs, strict=True), 1):
        expected.append(
            {
                "frame_ordinal": index,
                "compressed_start": row[1],
                "compressed_end": row[2],
                "decompressed_start": begin,
                "decompressed_end": begin + len(output),
                "compressed_span_sha256": ORACLES.raw_digest(member[row[1] : row[2]]),
                "decompressed_span_sha256": ORACLES.raw_digest(output),
            }
        )
        begin += len(output)
        assert visits.count(("terminal", index - 1, len(output))) == 1
    assert spans == expected and len(instances) == len(outputs)
    if len(actual) == 1048576:
        assert ("read", 0, 1) in visits


@pytest.mark.parametrize(
    "mode",
    (
        "source_not_consumed",
        "oversized_chunk",
        "nonbytes_chunk",
        "terminal_mismatch",
        "nonbytes_terminal",
        "codec_read_fault",
        "codec_terminal_fault",
    ),
)
def test_native_decompression_rejects_incomplete_nonbytes_or_terminal_disagreement(mode):
    member, physical, fake, visits, _ = fake_decompression_case((b"abc",), mode=mode)
    with pytest.raises(ValueError) as caught:
        engine_module()._decompress_frames(member, physical, fake)
    assert type(caught.value) is ValueError
    if mode in {"source_not_consumed", "oversized_chunk", "nonbytes_chunk", "codec_read_fault"}:
        assert not any(item[0] == "terminal" for item in visits)


@pytest.mark.parametrize(
    "outputs", ((b"",), (b"abc", b""), (b"x" * 1048577,), (b"x" * 1048576, b"y"))
)
def test_native_decompression_empty_or_cumulative_excess_has_no_successful_prefix(outputs):
    member, physical, fake, visits, _ = fake_decompression_case(outputs)
    with pytest.raises(ValueError):
        engine_module()._decompress_frames(member, physical, fake)
    assert not any(item[0] == "terminal" and item[1] == len(outputs) - 1 for item in visits)


@pytest.mark.parametrize("declared", ((2,), (4,), (0,)))
def test_native_decompression_known_fcs_must_match_whole_output_before_terminal(declared):
    member, physical, fake, visits, _ = fake_decompression_case((b"abc",), declared=declared)
    with pytest.raises(ValueError):
        engine_module()._decompress_frames(member, physical, fake)
    assert not any(item[0] == "terminal" for item in visits)


@pytest.mark.parametrize("stage", ("constructor_fault", "read_fault", "terminal_fault"))
@pytest.mark.parametrize(
    "kind", (AssertionError, MemoryError, RuntimeError, KeyboardInterrupt, SystemExit)
)
def test_native_decompression_unknown_or_critical_fault_is_never_ordinary_refusal(stage, kind):
    original = kind("independent critical codec sentinel")
    member, physical, fake, _, _ = fake_decompression_case((b"abc",), mode=stage, failure=original)
    with pytest.raises(kind) as caught:
        engine_module()._decompress_frames(member, physical, fake)
    assert caught.value is original


def scripted_dbn_case(scenario="valid_split", *, fault_stage=None, fault=None):
    request, _, _, expected = native_phase_request()
    raw = ORACLES.invented_raw_member()
    dbn, _, metadata, records = fake_native_objects()
    batches = {
        "valid_split": ([metadata, records[0]], [records[1]]),
        "missing_metadata": ([*records], []),
        "duplicate_metadata": ([metadata, metadata, records[0]], []),
        "late_metadata": ([metadata, records[0]], [metadata]),
        "unsupported_final": ([metadata, records[0]], [object()]),
        "missing_mbo": ([metadata, records[0]], []),
        "extra_mbo": ([metadata, *records], [records[0]]),
        "nonempty_buffer": ([metadata, *records], []),
        "buffer_alias": ([metadata, *records], []),
        "batch_tuple": ((metadata, *records), []),
    }[scenario]
    visits = []

    class Decoder:
        def __init__(self, **kwargs):
            assert kwargs == {
                "has_metadata": True,
                "ts_out": False,
                "input_version": None,
                "upgrade_policy": dbn.VersionUpgradePolicy.AS_IS,
                "compression": dbn.Compression.NONE,
            }
            self.index = 0
            visits.append("constructor")
            if fault_stage == "constructor":
                raise fault

        def write(self, supplied):
            assert supplied == raw
            visits.append("write")
            if fault_stage == "write":
                raise fault

        def decode(self):
            stage = "first_decode" if self.index == 0 else "final_decode"
            visits.append(stage)
            if fault_stage == stage:
                raise fault
            result = batches[self.index]
            self.index += 1
            return result

        def buffer(self):
            visits.append("buffer")
            if fault_stage == "buffer":
                raise fault
            if scenario == "nonempty_buffer":
                return b"unconsumed"
            if scenario == "buffer_alias":
                return bytearray()
            return b""

    dbn.DBNDecoder = Decoder
    return raw, expected, request, dbn, visits


def test_native_final_state_scripted_split_batches_match_complete_independent_occurrences():
    raw, expected, request, dbn, visits = scripted_dbn_case()
    observed = engine_module()._decode_occurrences(raw, expected["dbn_framing"], request, dbn)
    assert observed == expected["occurrences"]
    assert visits == ["constructor", "write", "first_decode", "final_decode", "buffer"]


@pytest.mark.parametrize(
    "scenario",
    (
        "missing_metadata",
        "duplicate_metadata",
        "late_metadata",
        "unsupported_final",
        "missing_mbo",
        "extra_mbo",
        "nonempty_buffer",
        "buffer_alias",
        "batch_tuple",
    ),
)
def test_native_final_state_rejects_complete_count_type_metadata_and_buffer_failures(scenario):
    raw, expected, request, dbn, visits = scripted_dbn_case(scenario)
    with pytest.raises(ValueError) as caught:
        engine_module()._decode_occurrences(raw, expected["dbn_framing"], request, dbn)
    assert type(caught.value) is ValueError
    assert visits[:3] == ["constructor", "write", "first_decode"]
    if scenario in {"late_metadata", "unsupported_final", "extra_mbo"}:
        assert visits[-1] == "final_decode"
    if scenario in {"missing_mbo", "nonempty_buffer", "buffer_alias"}:
        assert visits[-1] == "buffer"


@pytest.mark.parametrize(
    "stage", ("constructor", "write", "first_decode", "final_decode", "buffer")
)
@pytest.mark.parametrize(
    "kind", (AssertionError, MemoryError, RuntimeError, KeyboardInterrupt, SystemExit)
)
def test_native_final_state_preserves_actual_codec_seam_critical_or_unknown_fault(stage, kind):
    original = kind("independent DBN fault sentinel")
    raw, expected, request, dbn, visits = scripted_dbn_case(fault_stage=stage, fault=original)
    with pytest.raises(kind) as caught:
        engine_module()._decode_occurrences(raw, expected["dbn_framing"], request, dbn)
    assert caught.value is original and visits[-1] == stage


@pytest.mark.parametrize(
    "stage", ("constructor", "write", "first_decode", "final_decode", "buffer")
)
def test_native_final_state_maps_only_declared_dbn_error_to_ordinary_refusal(stage):
    raw, expected, request, dbn, _visits = scripted_dbn_case()
    original = dbn.DBNError("declared codec refusal")
    decoder = dbn.DBNDecoder

    def failed(*args, **kwargs):
        raise original

    if stage == "constructor":
        dbn.DBNDecoder = failed
    elif stage in {"write", "buffer"}:
        setattr(decoder, stage, failed)
    else:
        original_decode = decoder.decode

        def decode(self):
            if self.index == (0 if stage == "first_decode" else 1):
                raise original
            return original_decode(self)

        decoder.decode = decode
    with pytest.raises(ValueError) as caught:
        engine_module()._decode_occurrences(raw, expected["dbn_framing"], request, dbn)
    assert type(caught.value) is ValueError and caught.value.__cause__ is original


@lru_cache(maxsize=1)
def rich_declared_cases():
    names = {
        "rich_metadata_raw_extrema_ts_out_0",
        "rich_metadata_raw_extrema_ts_out_1",
        "stype_in_0_out_15",
    }
    return {row["id"]: deepcopy(row) for row in ORACLES.native_member_cases() if row["id"] in names}


def rich_submitted_case(provider, ts_out=True):
    case_id = "rich_metadata_raw_extrema_ts_out_" + str(int(ts_out))
    case = rich_declared_cases()[case_id]
    body = deepcopy(case["expected_body"])
    pins = {
        "expected_" + name + "_sha256": body[name + "_sha256"]
        for name in ("protocol", "profile", "runtime_manifest", "member", "metadata", "evidence")
    }
    assert body["occurrences"][0]["projection"]["mappings"][0]["raw_symbol"] == "alpha.é"
    assert body["dbn_framing"]["spans"][0]["wire_fields"]["mappings"][1]["raw_symbol"] == "alpha.é"
    return case["member"], body, typed_evidence(provider, body), pins


def replaced_record_at(record, path, value):
    if not path:
        return value
    first, *remaining = path
    if type(first) is int:
        items = list(record)
        items[first] = replaced_record_at(items[first], remaining, value)
        return tuple(items)
    return replace(record, **{first: replaced_record_at(getattr(record, first), remaining, value)})


RICH_GROUP = ("occurrences", 0, "projection", "mappings", 0)
RICH_INTERVAL = (*RICH_GROUP, "intervals", 0)
RICH_WIRE_GROUP = ("dbn_framing", "spans", 0, "wire_fields", "mappings", 1)
RICH_WIRE_INTERVAL = (*RICH_WIRE_GROUP, "intervals", 0)
RICH_RECORD_PATHS = (
    ("MappingGroup", RICH_GROUP),
    ("MappingInterval", RICH_INTERVAL),
    ("PythonDate", (*RICH_INTERVAL, "start_date")),
    ("PythonDate", (*RICH_INTERVAL, "end_date")),
    ("WireMappingGroup", RICH_WIRE_GROUP),
    ("WireMappingInterval", RICH_WIRE_INTERVAL),
    ("UnknownChar", ("occurrences", 1, "projection", "action")),
    ("UnknownChar", ("occurrences", 1, "projection", "side")),
)
RICH_SCALAR_PATHS = (
    (*RICH_GROUP, "raw_symbol"),
    (*RICH_INTERVAL, "symbol"),
    *(
        (*RICH_INTERVAL, which, field)
        for which in ("start_date", "end_date")
        for field in ("kind", "year", "month", "day")
    ),
    (*RICH_WIRE_GROUP, "raw_symbol"),
    (*RICH_WIRE_GROUP, "interval_count"),
    *((*RICH_WIRE_INTERVAL, field) for field in ("start_date", "end_date", "symbol")),
    *(
        ("occurrences", 1, "projection", which, field)
        for which in ("action", "side")
        for field in ("kind", "value")
    ),
    ("occurrences", 0, "projection", "limit_observed"),
    ("occurrences", 1, "projection", "ts_out_observed"),
    ("dbn_framing", "spans", 1, "wire_fields", "ts_out"),
)


@pytest.mark.parametrize("ts_out", (False, True))
def test_submitted_rich_complete_baseline_reaches_real_dispatch_sentinel(monkeypatch, ts_out):
    provider = provider_module()
    member, _, evidence, pins = rich_submitted_case(provider, ts_out)
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(AssertionError, match="contained dispatch was reached"):
        provider.verify(evidence, member, context(provider, ts_out), **pins)


@pytest.mark.parametrize("path", RICH_SCALAR_PATHS, ids=lambda path: ".".join(map(str, path)))
@pytest.mark.parametrize("mutation", ("alias", "wrong_type"))
def test_submitted_rich_nested_scalars_refuse_before_dispatch(monkeypatch, path, mutation):
    provider = provider_module()
    member, _, evidence, pins = rich_submitted_case(provider)
    original = value_at(evidence, path)
    assert type(original) in (str, int)
    value = (
        (StrAlias(original) if type(original) is str else IntAlias(original))
        if mutation == "alias"
        else (0 if type(original) is str else True)
    )
    evidence = replaced_record_at(evidence, path, value)
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider, True), **pins)


@pytest.mark.parametrize(
    "family,path",
    RICH_RECORD_PATHS,
    ids=[name + "." + ".".join(map(str, path)) for name, path in RICH_RECORD_PATHS],
)
@pytest.mark.parametrize("mutation", ("record_alias", "dict"))
def test_submitted_rich_exact_record_families_refuse_before_dispatch(
    monkeypatch, family, path, mutation
):
    provider = provider_module()
    member, _, evidence, pins = rich_submitted_case(provider)
    original = value_at(evidence, path)
    # Explicit literal constructor arguments; no dataclass/reflection-based oracle.
    if family == "MappingGroup":
        args = (original.raw_symbol, original.intervals)
    elif family == "MappingInterval":
        args = (original.start_date, original.end_date, original.symbol)
    elif family == "PythonDate":
        args = (original.kind, original.year, original.month, original.day)
    elif family == "WireMappingGroup":
        args = (original.raw_symbol, original.interval_count, original.intervals)
    elif family == "WireMappingInterval":
        args = (original.start_date, original.end_date, original.symbol)
    elif family == "UnknownChar":
        args = (original.kind, original.value)
    else:
        raise AssertionError("unregistered independent record family")
    alias = type("IndependentRichRecordAlias", (getattr(provider, family),), {"__slots__": ()})
    value = alias(*args) if mutation == "record_alias" else {"not": "a registered record"}
    evidence = replaced_record_at(evidence, path, value)
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider, True), **pins)


@pytest.mark.parametrize(
    "path",
    (
        (*RICH_GROUP, "intervals"),
        (*RICH_WIRE_GROUP, "intervals"),
    ),
)
def test_submitted_rich_interval_collections_are_exact_tuples(monkeypatch, path):
    provider = provider_module()
    member, _, evidence, pins = rich_submitted_case(provider)
    evidence = replaced_record_at(evidence, path, list(value_at(evidence, path)))
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider, True), **pins)


@pytest.mark.parametrize(
    "path,value",
    (
        ((*RICH_INTERVAL, "start_date", "kind"), "wrong_date_kind"),
        ((*RICH_INTERVAL, "start_date", "year"), 0),
        ((*RICH_INTERVAL, "start_date", "month"), 13),
        ((*RICH_INTERVAL, "start_date", "day"), 30),
        ((*RICH_INTERVAL, "end_date", "day"), 32),
        ((*RICH_WIRE_INTERVAL, "start_date"), 20000230),
        ((*RICH_WIRE_GROUP, "interval_count"), 3),
        (("occurrences", 1, "projection", "action", "kind"), "native_enum"),
        (("occurrences", 1, "projection", "action", "value"), ""),
        (("occurrences", 1, "projection", "action", "value"), "??"),
        (("occurrences", 1, "projection", "side", "value"), "Ā"),
    ),
)
def test_submitted_rich_nested_malformed_domains_refuse_before_dispatch(monkeypatch, path, value):
    provider = provider_module()
    member, _, evidence, pins = rich_submitted_case(provider)
    evidence = replaced_record_at(evidence, path, value)
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider, True), **pins)


@pytest.mark.parametrize("mutation", ("baseline", "alias", "bool"))
def test_submitted_rich_nullable_end_nonnull_branch_is_validated(monkeypatch, mutation):
    provider = provider_module()
    case = rich_declared_cases()["stype_in_0_out_15"]
    body = deepcopy(case["expected_body"])
    evidence = typed_evidence(provider, body)
    path = ("occurrences", 0, "projection", "end_observed")
    original = value_at(evidence, path)
    assert type(original) is int and original == (1 << 64) - 2
    if mutation != "baseline":
        evidence = replaced_record_at(
            evidence, path, IntAlias(original) if mutation == "alias" else True
        )
    pins = {
        "expected_" + name + "_sha256": body[name + "_sha256"]
        for name in ("protocol", "profile", "runtime_manifest", "member", "metadata", "evidence")
    }
    monkeypatch.setattr(provider, "_dispatch_decode", dispatch_sentinel)
    if mutation == "baseline":
        with pytest.raises(AssertionError, match="contained dispatch was reached"):
            provider.verify(evidence, case["member"], context(provider), **pins)
    else:
        with pytest.raises(ValueError):
            provider.verify(evidence, case["member"], context(provider), **pins)


RICH_BODY_FIELD_PATHS = (
    *((*RICH_GROUP, key) for key in ("raw_symbol", "intervals")),
    *((*RICH_INTERVAL, key) for key in ("start_date", "end_date", "symbol")),
    *(
        (*RICH_INTERVAL, date_name, key)
        for date_name in ("start_date", "end_date")
        for key in ("kind", "year", "month", "day")
    ),
    *((*RICH_WIRE_GROUP, key) for key in ("raw_symbol", "interval_count", "intervals")),
    *((*RICH_WIRE_INTERVAL, key) for key in ("start_date", "end_date", "symbol")),
    *(
        ("occurrences", 1, "projection", name, key)
        for name in ("action", "side")
        for key in ("kind", "value")
    ),
)


@pytest.mark.parametrize("path", RICH_BODY_FIELD_PATHS, ids=lambda path: ".".join(map(str, path)))
@pytest.mark.parametrize("mutation", ("missing", "extra"))
def test_submitted_rich_fresh_response_nested_exact_keys_are_validated(monkeypatch, path, mutation):
    provider = provider_module()
    member, body, evidence, pins = rich_submitted_case(provider)
    wrong = deepcopy(body)
    target = wrong
    for field in path[:-1]:
        target = target[field]
    if mutation == "missing":
        del target[path[-1]]
    else:
        target["unregistered_extra"] = None
    calls = []

    def response(*args):
        calls.append(args)
        return deepcopy(wrong)

    monkeypatch.setattr(provider, "_dispatch_decode", response)
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider, True), **pins)
    assert len(calls) == 1, "rich valid submission must reach fresh complete response validation"


@pytest.mark.parametrize(
    "mutation", ("mapping_symbol", "interval_symbol", "date", "unknown_action", "unknown_side")
)
def test_submitted_rich_coherently_rehashed_false_body_requires_fresh_reconstruction(
    monkeypatch, mutation
):
    provider = provider_module()
    member, body, _, pins = rich_submitted_case(provider)
    wrong = deepcopy(body)
    logical_group = wrong["occurrences"][0]["projection"]["mappings"][0]
    wire_group = wrong["dbn_framing"]["spans"][0]["wire_fields"]["mappings"][1]
    if mutation == "mapping_symbol":
        logical_group["raw_symbol"] = wire_group["raw_symbol"] = "alpha.ê"
    elif mutation == "interval_symbol":
        logical_group["intervals"][0]["symbol"] = wire_group["intervals"][0]["symbol"] = "2"
    elif mutation == "date":
        logical_group["intervals"][0]["start_date"]["day"] = 28
        wire_group["intervals"][0]["start_date"] = 20000228
    else:
        field = "action" if mutation == "unknown_action" else "side"
        wrong["occurrences"][1]["projection"][field]["value"] = "?"
        wrong["dbn_framing"]["spans"][1]["wire_fields"][field] = 63
    ORACLES.rehash_evidence(wrong)
    evidence = typed_evidence(provider, wrong)
    pins["expected_metadata_sha256"] = wrong["metadata_sha256"]
    pins["expected_evidence_sha256"] = wrong["evidence_sha256"]
    visits = []

    def independent_response(raw, supplied_context, supplied_pins):
        visits.append((raw, supplied_context, supplied_pins))
        return deepcopy(body)

    monkeypatch.setattr(provider, "_dispatch_decode", independent_response)
    with pytest.raises(ValueError):
        provider.verify(evidence, member, context(provider, True), **pins)
    assert len(visits) == 1
    assert visits[0][0] == member and visits[0][1] == context_body(True)
