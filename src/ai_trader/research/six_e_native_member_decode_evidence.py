"""Complete invented-member consistency; native codecs never run in this facade."""

import hashlib
import re

from . import _native_member_types as _types
from ._native_member_types import (
    Action,
    Artifact,
    DbnFramingReport,
    DecodedOccurrence,
    FrameSpan,
    Interpreter,
    MappingGroup,
    MappingInterval,
    MboObservation,
    MboWireBody,
    MemberDecodeContext,
    MemberDecodeEvidence,
    MetadataProjection,
    MetadataWireBody,
    Package,
    PythonDate,
    RtypeMbo,
    RuntimeManifest,
    SchemaMbo,
    Side,
    SType,
    TerminalEvidence,
    UnknownChar,
    WireMappingGroup,
    WireMappingInterval,
    WireSpan,
    ZstdFramingReport,
)

# Root replaces this only with the H of the complete stable execution manifest.
# An unregistered build cannot start a worker.
_EXECUTION_SHA256 = "2db856c8c85a1d9d268819b9c7e7246478342d86c419c6e64f889f18cee103b2"

__all__ = [
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
]


def protocol() -> dict:
    return _types.protocol_body()


def protocol_sha256() -> str:
    return _types.body_sha256(protocol())


def context_sha256(context, *, expected_protocol_sha256) -> str:
    _pin(expected_protocol_sha256)
    if expected_protocol_sha256 != protocol_sha256():
        raise ValueError("protocol expectation mismatch")
    body = _types.project("Context", context)
    if len(_types.canonical_bytes(body)) > 65536:
        raise ValueError("complete context exceeds limit")
    return _types.body_sha256(body)


def decode_member(
    member_bytes,
    context,
    *,
    expected_protocol_sha256,
    expected_profile_sha256,
    expected_runtime_manifest_sha256,
    expected_member_sha256,
    expected_metadata_sha256,
) -> MemberDecodeEvidence:
    pins = _pins(
        expected_protocol_sha256,
        expected_profile_sha256,
        expected_runtime_manifest_sha256,
        expected_member_sha256,
        expected_metadata_sha256,
    )
    context_body = _preflight(member_bytes, context, pins)
    body = _dispatch_decode(member_bytes, context_body, pins)
    _validate_result(body, context_body, pins)
    return _types.from_body("MemberDecodeEvidence", body)


def verify(
    evidence,
    member_bytes,
    context,
    *,
    expected_protocol_sha256,
    expected_profile_sha256,
    expected_runtime_manifest_sha256,
    expected_member_sha256,
    expected_metadata_sha256,
    expected_evidence_sha256,
) -> None:
    _pin(expected_evidence_sha256)
    pins = _pins(
        expected_protocol_sha256,
        expected_profile_sha256,
        expected_runtime_manifest_sha256,
        expected_member_sha256,
        expected_metadata_sha256,
    )
    context_body = _preflight(member_bytes, context, pins)
    submitted = _types.project("MemberDecodeEvidence", evidence)
    _validate_result(submitted, context_body, pins)
    if submitted["evidence_sha256"] != expected_evidence_sha256:
        raise ValueError("submitted evidence expectation mismatch")
    rebuilt = _dispatch_decode(member_bytes, context_body, pins)
    _validate_result(rebuilt, context_body, pins)
    if rebuilt != submitted:
        raise ValueError("complete reconstructed evidence differs")


def _pin(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("exact lowercase SHA256 expectation required")


def _pins(protocol_pin, profile_pin, runtime_pin, member_pin, metadata_pin):
    values = (protocol_pin, profile_pin, runtime_pin, member_pin, metadata_pin)
    for value in values:
        _pin(value)
    if (
        protocol_pin != _types._PROTOCOL_SHA
        or profile_pin != _types._PROFILE_SHA
        or runtime_pin != _types._RUNTIME_SHA
    ):
        raise ValueError("registered expectation mismatch")
    return dict(
        zip(
            (
                "expected_protocol_sha256",
                "expected_profile_sha256",
                "expected_runtime_manifest_sha256",
                "expected_member_sha256",
                "expected_metadata_sha256",
            ),
            values,
            strict=True,
        )
    )


def _preflight(member_bytes, context, pins):
    context_body = _types.project("Context", context)
    if len(_types.canonical_bytes(context_body)) > 65536:
        raise ValueError("complete context exceeds limit")
    _types.profile_body()
    if type(member_bytes) is not bytes or not 1 <= len(member_bytes) <= 262144:
        raise ValueError("complete immutable member byte limit/type")
    if hashlib.sha256(member_bytes).hexdigest() != pins["expected_member_sha256"]:
        raise ValueError("complete member expectation mismatch")
    return context_body


def _validate_result(body, context_body, pins):
    _types.validate_body("MemberDecodeEvidence", body)
    for field in ("protocol", "profile", "runtime_manifest", "member", "metadata"):
        if body[field + "_sha256"] != pins["expected_" + field + "_sha256"]:
            raise ValueError("result expectation mismatch")
    if body["context_sha256"] != _types.body_sha256(context_body):
        raise ValueError("complete context identity mismatch")
    if body["occurrences"][0]["projection"]["ts_out"] is not context_body["expected_ts_out"]:
        raise ValueError("observed ts_out context mismatch")


def _dispatch_decode(member_bytes, context_body, pins):
    if (
        type(_EXECUTION_SHA256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", _EXECUTION_SHA256) is None
    ):
        raise RuntimeError("provider execution build is not registered")
    from . import _native_member_host

    request = {
        "schema": "native_member_worker_request_v1",
        "operation": "decode",
        "context": context_body,
        "member_hex": member_bytes.hex(),
        **pins,
        "execution_manifest_sha256": _EXECUTION_SHA256,
        "attempt_token": "0" * 64,
    }
    response, _receipt = _native_member_host.run_decode(request, _EXECUTION_SHA256)
    return response["evidence"]
