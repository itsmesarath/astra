"""Independent native-free transport tests and later registered host controls.

Root alone launches checks; expected bodies are literal registration/oracle data.
No decoder, process creation or shared mapping is used by boundary tests.
"""

import copy
import hashlib
import importlib
import importlib.machinery
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path
from types import ModuleType

import pytest

SPEC = importlib.util.spec_from_file_location(
    "native_member_host_independent_oracles_20261013",
    Path(__file__).with_name("native_member_provider_oracles_20261013.py"),
)
assert SPEC is not None and SPEC.loader is not None
ORACLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ORACLE)
EXECUTION_SHA = "a" * 64
REGISTERED_EXECUTION_SHA = "2db856c8c85a1d9d268819b9c7e7246478342d86c419c6e64f889f18cee103b2"
TOKEN = "3" * 64


def canonical(body):
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def request_template():
    member, evidence = ORACLE.minimal_evidence_body()
    return {
        "schema": "native_member_worker_request_v1",
        "operation": "decode",
        "context": ORACLE.context_body(),
        "member_hex": member.hex(),
        "expected_protocol_sha256": ORACLE.digest(ORACLE.protocol_literal()),
        "expected_profile_sha256": ORACLE.PROFILE_SHA256,
        "expected_runtime_manifest_sha256": ORACLE.RUNTIME_SHA256,
        "expected_member_sha256": sha(member),
        "expected_metadata_sha256": evidence["metadata_sha256"],
        "execution_manifest_sha256": EXECUTION_SHA,
        "attempt_token": "0" * 64,
    }


def mapping(raw):
    return b"NMREQ001" + len(raw).to_bytes(4, "little") + raw + bytes(1048564 - len(raw))


def response_body(*, harmless=False, refused=False):
    request = request_template()
    request["attempt_token"] = TOKEN
    _, evidence = ORACLE.minimal_evidence_body()
    if harmless:
        evidence = {
            "schema": "native_member_harmless_observation_v1",
            "control_id": "mapping_roundtrip",
            "request_body": copy.deepcopy(request),
            "mapping_sha256": sha(mapping(canonical(request))),
            "result": {"step": "response_ready", "native_codec_imported": False},
        }
    return request, {
        "schema": "native_member_harmless_response_v1"
        if harmless
        else "native_member_worker_response_v1",
        "attempt_token": TOKEN,
        "request_sha256": sha(canonical(request)),
        "execution_manifest_sha256": EXECUTION_SHA,
        "status": "refused" if refused else "complete",
        "evidence": None if refused else evidence,
        "failure_kind": "invalid_member" if refused else None,
    }


def frame(body):
    raw = canonical(body)
    return b"NMRES001" + len(raw).to_bytes(4, "little") + raw


def host_module():
    return importlib.import_module("ai_trader.research._native_member_host")


def worker_module():
    return importlib.import_module("ai_trader.research._native_member_worker")


def test_host_boundary_request_exact_complete_mapping_and_fresh_token(monkeypatch):
    host = host_module()
    template = request_template()
    before = copy.deepcopy(template)
    visits = []

    def token_hex(count):
        visits.append(count)
        return TOKEN

    monkeypatch.setattr(host.secrets, "token_hex", token_hex)
    actual, raw, complete = host._request_bytes(template, EXECUTION_SHA)
    expected = copy.deepcopy(before)
    expected["attempt_token"] = TOKEN
    assert actual == expected
    assert raw == canonical(expected)
    assert complete == mapping(canonical(expected))
    assert len(complete) == 1048576
    assert template == before
    assert visits == [32]
    actual["context"]["expected_ts_out"] = True
    assert template == before


@pytest.mark.parametrize("field", tuple(request_template()))
@pytest.mark.parametrize("mutation", ("missing", "wrong_type"))
def test_host_boundary_request_exact_fields_before_token(monkeypatch, field, mutation):
    host = host_module()
    body = request_template()
    if mutation == "missing":
        del body[field]
    else:
        body[field] = []

    def sentinel(*args):
        raise AssertionError("request refusal must precede token allocation")

    monkeypatch.setattr(host.secrets, "token_hex", sentinel)
    with pytest.raises(ValueError):
        host._request_bytes(body, EXECUTION_SHA)


@pytest.mark.parametrize(
    "field",
    (
        "expected_protocol_sha256",
        "expected_profile_sha256",
        "expected_runtime_manifest_sha256",
        "expected_member_sha256",
        "execution_manifest_sha256",
        "attempt_token",
    ),
)
def test_host_boundary_request_rejects_semantic_pin_mismatch(monkeypatch, field):
    host = host_module()
    body = request_template()
    body[field] = "b" * 64

    def sentinel(*args):
        raise AssertionError("pin refusal must precede token allocation")

    monkeypatch.setattr(host.secrets, "token_hex", sentinel)
    with pytest.raises(ValueError):
        host._request_bytes(body, EXECUTION_SHA)


@pytest.mark.parametrize("harmless", (False, True))
@pytest.mark.parametrize("refused", (False, True))
def test_host_boundary_response_complete_literal_envelopes(harmless, refused):
    request, body = response_body(harmless=harmless, refused=refused)
    assert (
        host_module()._response_body(
            frame(body), request, sha(canonical(request)), harmless=harmless
        )
        == body
    )


@pytest.mark.parametrize(
    "field",
    (
        "attempt_token",
        "request_sha256",
        "execution_manifest_sha256",
    ),
)
@pytest.mark.parametrize("harmless", (False, True))
def test_host_boundary_response_rejects_rebound_complete_body(field, harmless):
    request, body = response_body(harmless=harmless)
    body[field] = "b" * 64
    with pytest.raises(ValueError):
        host_module()._response_body(
            frame(body), request, sha(canonical(request)), harmless=harmless
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "empty",
        "magic",
        "zero_length",
        "long_length",
        "short_length",
        "truncated",
        "trailing",
        "duplicate",
        "bytearray",
        "memoryview",
    ),
)
def test_host_boundary_response_strict_complete_transport(mutation):
    request, body = response_body()
    raw = frame(body)
    if mutation == "empty":
        raw = b""
    elif mutation == "magic":
        raw = b"X" + raw[1:]
    elif mutation == "zero_length":
        raw = raw[:8] + bytes(4) + raw[12:]
    elif mutation == "long_length":
        raw = raw[:8] + (2097153).to_bytes(4, "little") + raw[12:]
    elif mutation == "short_length":
        raw = raw[:8] + (len(raw) - 13).to_bytes(4, "little") + raw[12:]
    elif mutation == "truncated":
        raw = raw[:-1]
    elif mutation == "trailing":
        raw += b"X"
    elif mutation == "duplicate":
        raw *= 2
    elif mutation == "bytearray":
        raw = bytearray(raw)
    else:
        raw = memoryview(raw)
    with pytest.raises(ValueError):
        host_module()._response_body(raw, request, sha(canonical(request)))


@pytest.mark.parametrize(
    "mutation",
    (
        "extra",
        "missing",
        "schema",
        "status",
        "failure_kind",
        "refusal_evidence",
        "wrong_evidence_member",
        "wrong_evidence_context",
        "wrong_evidence_metadata",
    ),
)
def test_host_boundary_response_rejects_schema_or_evidence(mutation):
    request, body = response_body()
    if mutation == "extra":
        body["extra"] = None
    elif mutation == "missing":
        del body["failure_kind"]
    elif mutation == "schema":
        body["schema"] = "native_member_harmless_response_v1"
    elif mutation == "status":
        body["status"] = "pending"
    elif mutation == "failure_kind":
        body["failure_kind"] = "invalid_member"
    elif mutation == "refusal_evidence":
        body.update(status="refused", failure_kind="invalid_member")
    elif mutation == "wrong_evidence_metadata":
        request["expected_metadata_sha256"] = "b" * 64
        body["request_sha256"] = sha(canonical(request))
    else:
        key = {
            "wrong_evidence_member": "member_sha256",
            "wrong_evidence_context": "context_sha256",
            "wrong_evidence_metadata": "metadata_sha256",
        }[mutation]
        body["evidence"][key] = "b" * 64
        ORACLE.rehash_evidence(body["evidence"])
    with pytest.raises(ValueError):
        host_module()._response_body(frame(body), request, sha(canonical(request)))


def test_worker_boundary_mapping_matches_complete_request():
    request = request_template()
    request["attempt_token"] = TOKEN
    assert worker_module()._parse_request_mapping(mapping(canonical(request))) == request


@pytest.mark.parametrize(
    "mutation", ("empty", "short", "long", "magic", "zero", "excess", "padding", "bytearray")
)
def test_worker_boundary_refuses_mapping_corruption(mutation):
    raw = mapping(canonical(request_template()))
    if mutation == "empty":
        raw = b""
    elif mutation == "short":
        raw = raw[:-1]
    elif mutation == "long":
        raw += b"\0"
    elif mutation == "magic":
        raw = b"X" + raw[1:]
    elif mutation == "zero":
        raw = raw[:8] + bytes(4) + raw[12:]
    elif mutation == "excess":
        raw = raw[:8] + (1048565).to_bytes(4, "little") + raw[12:]
    elif mutation == "padding":
        raw = raw[:-1] + b"X"
    else:
        raw = bytearray(raw)
    with pytest.raises(ValueError):
        worker_module()._parse_request_mapping(raw)


@pytest.mark.parametrize(
    "raw",
    (
        b"",
        b"\xef\xbb\xbf{}",
        b"\xff",
        b'{"x":0,"x":1}',
        b'{"x":1.0}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":-Infinity}',
        b'{"x":1e2}',
        b'{"x":123456789012345678901}',
        b'{"x":-123456789012345678901}',
        b'{"x":01}',
        b'{"x":+1}',
        b'{"x":--1}',
        b'{"x":0} ',
        b'{ "x":0}',
        b'{"z":0,"a":1}',
        b'"\\u0061"',
        b'{"x":0}\0',
        b"{}{}",
    ),
)
def test_worker_boundary_strict_parser_refuses_invalid_json(raw):
    with pytest.raises((ValueError, UnicodeDecodeError)):
        worker_module()._strict(raw, 1048564, 128)


def test_worker_boundary_parser_exact_integer_node_depth_limits():
    worker = worker_module()
    raw = b'{"x":18446744073709551615}'
    assert worker._strict(raw, len(raw), 3) == {"x": 18446744073709551615}
    for maximum, nodes in ((len(raw) - 1, 3), (len(raw), 2)):
        with pytest.raises(ValueError):
            worker._strict(raw, maximum, nodes)
    accepted = b"[" * 63 + b"0" + b"]" * 63
    assert worker._strict(accepted, 1048564, 128) is not None
    with pytest.raises(ValueError):
        worker._strict(b"[" + accepted + b"]", 1048564, 128)


CONTROL_OUTCOMES = {
    "mapping_roundtrip": "complete",
    "ordinary_refusal": "input_refused",
    "never_read": "timeout",
    "respond_then_wait": "timeout",
    "stdout_excess": "transport_failed",
    "stderr_excess": "transport_failed",
    "stderr_nonempty": "transport_failed",
    "truncated_response": "transport_failed",
    "trailing_response": "transport_failed",
    "duplicate_response": "transport_failed",
    "wrong_token": "transport_failed",
    "wrong_request_hash": "transport_failed",
    "wrong_manifest_hash": "transport_failed",
    "valid_then_exit_73": "worker_failed",
    "memory_error_71": "resource_failed",
    "memory_pressure": "complete",
    "grandchild_denied": "complete",
}
RECEIPT_KEYS = {
    "schema",
    "operation",
    "execution_manifest_sha256",
    "attempt_token",
    "started_utc",
    "finished_utc",
    "elapsed_ns",
    "request",
    "parent",
    "child",
    "command",
    "mapping",
    "limits",
    "job",
    "channels",
    "implementation_checks",
    "response",
    "exit",
    "termination",
    "cleanup",
    "outcome",
}
LIMITS = {
    "limit_flags": 8974,
    "active_process_limit": 1,
    "process_memory_bytes": 268435456,
    "job_memory_bytes": 268435456,
    "process_user_time_100ns": 50000000,
    "job_user_time_100ns": 50000000,
}
ROOT = Path(__file__).resolve().parents[1]
PYTHON = "C:/Users/pabta/AppData/Local/Programs/Python/Python312/python.exe"


def exact_keys(body, keys):
    assert type(body) is dict and set(body) == set(keys)


def exact_uint(value, maximum=(1 << 64) - 1, minimum=0):
    assert type(value) is int and minimum <= value <= maximum


def harmless_registration(control):
    manifest_path = ROOT / "src/ai_trader/research/_native_member_execution_v1.json"
    assert manifest_path.is_file(), "registered execution manifest must precede host qualification"
    raw = manifest_path.read_bytes()
    assert 0 < len(raw) <= 65536
    manifest = json.loads(raw)
    assert canonical(manifest) == raw
    execution_sha = sha(raw)
    assert execution_sha == REGISTERED_EXECUTION_SHA
    request = request_template()
    request["execution_manifest_sha256"] = execution_sha
    worker_raw = (
        Path(__file__).with_name("native_member_provider_control_worker_20261013.py").read_bytes()
    )
    registration = {
        "schema": "native_member_harmless_execution_v1",
        "provider_execution_manifest_sha256": execution_sha,
        "control_id": control,
        "worker": {
            "logical_id": "harmless_worker",
            "relative_path": "tests/native_member_provider_control_worker_20261013.py",
            "raw_bytes": len(worker_raw),
            "raw_sha256": sha(worker_raw),
        },
        "argument_template": [
            "--mapping-handle",
            "HOST_GENERATED_UINT",
            "--mapping-size",
            "1048576",
            "--control",
            control,
        ],
        "request_template_sha256": sha(canonical(request)),
        "expected_outcome": CONTROL_OUTCOMES[control],
        "native_codec_imports": False,
    }
    return manifest, request, registration


def expected_control_result(control, mapping_sha, actual_result=None):
    if control == "mapping_roundtrip":
        return {
            "mapping_bytes": 1048576,
            "inherited_handle_flags": 1,
            "read_access": "FILE_MAP_READ",
            "shared_write_denied": True,
            "shared_write_winerror": 5,
            "copy_view_created": True,
            "copy_offset": 1048575,
            "copy_before": 0,
            "copy_after": 165,
            "shared_after": 0,
            "shared_after_sha256": mapping_sha,
            "copy_view_unmapped": True,
            "read_view_unmapped": True,
            "mapping_handle_closed": True,
            "native_codec_imported": False,
        }
    if control == "memory_pressure":
        return {
            "attempted_bytes": 536870912,
            "attempted": True,
            "memory_error_caught": True,
            "allocation_returned": False,
            "allocation_length": None,
            "retained_allocation_object": False,
            "native_codec_imported": False,
        }
    if control == "grandchild_denied":
        assert type(actual_result) is dict
        observed_error = actual_result["winerror"]
        exact_uint(observed_error, (1 << 32) - 1, 1)
        assert observed_error in (5, 1816), (
            "only the registered access/quota error categories qualify"
        )
        return {
            "executable": PYTHON,
            "argv": [PYTHON, "-I", "-S", "-B", "-c", "pass"],
            "creation_attempted": True,
            "create_returned": False,
            "winerror": observed_error,
            "returned_process_handle": False,
            "returned_thread_handle": False,
            "resumed": False,
            "native_codec_imported": False,
        }
    return {"step": "response_ready", "native_codec_imported": False}


def expected_control_response(control, actual_request, actual_response):
    result = None
    if control == "grandchild_denied":
        assert type(actual_response) is dict
        result = actual_response["evidence"]["result"]
    expected = {
        "schema": "native_member_harmless_response_v1",
        "attempt_token": actual_request["attempt_token"],
        "request_sha256": sha(canonical(actual_request)),
        "execution_manifest_sha256": actual_request["execution_manifest_sha256"],
        "status": "complete",
        "evidence": {
            "schema": "native_member_harmless_observation_v1",
            "control_id": control,
            "request_body": copy.deepcopy(actual_request),
            "mapping_sha256": sha(mapping(canonical(actual_request))),
            "result": expected_control_result(
                control, sha(mapping(canonical(actual_request))), result
            ),
        },
        "failure_kind": None,
    }
    if control == "ordinary_refusal":
        expected.update(status="refused", evidence=None, failure_kind="invalid_member")
    field = {
        "wrong_token": "attempt_token",
        "wrong_request_hash": "request_sha256",
        "wrong_manifest_hash": "execution_manifest_sha256",
    }.get(control)
    if field is not None:
        old = expected[field]
        expected[field] = ("1" if old[0] == "0" else "0") + old[1:]
    return expected


def assert_created_receipt(
    receipt,
    control,
    manifest,
    template,
    registration,
    *,
    production=False,
    production_outcome="complete",
):
    exact_keys(receipt, RECEIPT_KEYS)
    assert receipt["schema"] == "native_member_provider_owned_receipt_v1"
    assert receipt["operation"] == ("decode" if production else "control")
    assert (
        receipt["execution_manifest_sha256"] == registration["provider_execution_manifest_sha256"]
    )
    token = receipt["attempt_token"]
    assert type(token) is str and re.fullmatch("[0-9a-f]{64}", token)
    assert token != "0" * 64
    for key in ("started_utc", "finished_utc"):
        assert type(receipt[key]) is str and receipt[key].endswith("Z")
    assert datetime.fromisoformat(
        receipt["finished_utc"].replace("Z", "+00:00")
    ) >= datetime.fromisoformat(receipt["started_utc"].replace("Z", "+00:00"))
    exact_uint(receipt["elapsed_ns"])
    actual_request = copy.deepcopy(template)
    actual_request["attempt_token"] = token
    encoded_request = canonical(actual_request)
    assert receipt["request"] == {
        "canonical_bytes": len(encoded_request),
        "canonical_sha256": sha(encoded_request),
        "member_bytes": len(bytes.fromhex(template["member_hex"])),
        "member_sha256": template["expected_member_sha256"],
    }
    parent, child = receipt["parent"], receipt["child"]
    exact_keys(parent, ("pid", "creation_filetime", "image"))
    exact_keys(
        child,
        (
            "pid",
            "tid",
            "parent_pid",
            "creation_filetime",
            "image",
            "in_job_before_resume",
            "resume_previous_count",
        ),
    )
    exact_uint(parent["pid"], (1 << 32) - 1, 1)
    exact_uint(parent["creation_filetime"], minimum=1)
    for key in ("pid", "tid", "parent_pid"):
        exact_uint(child[key], (1 << 32) - 1, 1)
    exact_uint(child["creation_filetime"], minimum=1)
    assert child["parent_pid"] == parent["pid"]
    assert child["pid"] != parent["pid"]
    assert child["in_job_before_resume"] is True
    assert type(child["resume_previous_count"]) is int and child["resume_previous_count"] == 1
    assert child["image"].replace("\\", "/").casefold() == PYTHON.casefold()
    command = receipt["command"]
    exact_keys(command, ("executable", "argv", "cwd", "environment"))
    assert command["executable"].replace("\\", "/").casefold() == PYTHON.casefold()
    argv = command["argv"]
    assert type(argv) is list and len(argv) == (9 if production else 11)
    assert argv[0].replace("\\", "/").casefold() == PYTHON.casefold()
    assert argv[1:4] == ["-I", "-S", "-B"]
    expected_worker = (
        ROOT / "src/ai_trader/research/_native_member_worker.py"
        if production
        else Path(__file__).with_name("native_member_provider_control_worker_20261013.py")
    )
    assert Path(argv[4]) == expected_worker
    assert (
        argv[5] == "--mapping-handle"
        and type(argv[6]) is str
        and re.fullmatch("[1-9][0-9]{0,19}", argv[6])
    )
    assert argv[7:] == (
        ["--mapping-size", "1048576"]
        if production
        else ["--mapping-size", "1048576", "--control", control]
    )
    assert Path(command["cwd"]) == ROOT
    exact_keys(command["environment"], ("SystemRoot",))
    assert type(command["environment"]["SystemRoot"]) is str
    assert receipt["mapping"] == {
        "bytes": 1048576,
        "inherited_access": "FILE_MAP_READ",
        "writable_parent_view_unmapped": True,
        "write_capable_parent_handle_closed": True,
        "explicit_inherited_handle_count": 4,
    }
    exact_keys(receipt["limits"], ("configured", "queried_before_resume", "queried_final"))
    for observed in receipt["limits"].values():
        assert observed == LIMITS
        for value in observed.values():
            exact_uint(value)
    job = receipt["job"]
    exact_keys(
        job,
        (
            "pids_initial",
            "pids_before_resume",
            "pids_final",
            "accounting_initial",
            "accounting_before_resume",
            "accounting_final",
        ),
    )
    assert job["pids_initial"] == []
    assert job["pids_before_resume"] == [child["pid"]]
    assert job["pids_final"] == []
    for name in ("accounting_initial", "accounting_before_resume", "accounting_final"):
        exact_keys(
            job[name],
            (
                "total_user_time_100ns",
                "total_kernel_time_100ns",
                "total_processes",
                "active_processes",
                "terminated_processes",
                "page_faults",
            ),
        )
        for value in job[name].values():
            exact_uint(value)
    assert job["accounting_initial"]["total_processes"] == 0
    assert job["accounting_before_resume"]["active_processes"] == 1
    assert job["accounting_final"]["active_processes"] == 0
    assert job["accounting_final"]["total_processes"] >= 1
    exact_keys(receipt["channels"], ("stdout", "stderr"))
    for name, channel in receipt["channels"].items():
        exact_keys(channel, ("retained_bytes", "raw_sha256", "eof", "hash_scope"))
        exact_uint(channel["retained_bytes"], 65536 if name == "stderr" else 4194304)
        assert type(channel["eof"]) is bool
        assert channel["hash_scope"] == ("complete" if channel["eof"] else "retained_prefix")
        assert type(channel["raw_sha256"]) is str and re.fullmatch(
            "[0-9a-f]{64}", channel["raw_sha256"]
        )
    assert sum(item["retained_bytes"] for item in receipt["channels"].values()) <= 4194304
    checks = receipt["implementation_checks"]
    exact_keys(checks, ("before", "after"))
    expected_artifacts = [
        {
            "logical_id": row["logical_id"],
            "raw_bytes": row["raw_bytes"],
            "raw_sha256": row["raw_sha256"],
        }
        for row in manifest["artifacts"]
    ]
    for name in ("before", "after"):
        assert checks[name] == expected_artifacts
    exited = receipt["exit"]
    exact_keys(
        exited,
        (
            "created",
            "resumed",
            "observed",
            "code",
            "creation_filetime",
            "exit_filetime",
            "user_time_100ns",
            "kernel_time_100ns",
        ),
    )
    assert exited["created"] is True and exited["resumed"] is True and exited["observed"] is True
    assert exited["creation_filetime"] == child["creation_filetime"]
    exact_uint(exited["code"], (1 << 32) - 1)
    exact_uint(exited["exit_filetime"], minimum=child["creation_filetime"])
    exact_uint(exited["user_time_100ns"])
    exact_uint(exited["kernel_time_100ns"])
    termination = receipt["termination"]
    if termination is not None:
        exact_keys(
            termination,
            (
                "requested",
                "reason",
                "job_attempted",
                "job_winerror",
                "process_fallback_attempted",
                "process_winerror",
            ),
        )
        assert type(termination["requested"]) is bool
        for key in ("job_attempted", "process_fallback_attempted"):
            assert type(termination[key]) is bool
        for key in ("job_winerror", "process_winerror"):
            if termination[key] is not None:
                exact_uint(termination[key], (1 << 32) - 1)
    cleanup = receipt["cleanup"]
    exact_keys(cleanup, ("completed", "closed_handles", "unmapped_views", "errors"))
    assert cleanup["completed"] is True and cleanup["errors"] == []
    assert type(cleanup["closed_handles"]) is list and len(set(cleanup["closed_handles"])) == len(
        cleanup["closed_handles"]
    )
    assert {
        "job",
        "process",
        "thread",
        "request_write",
        "request_read",
        "stdout_read",
        "stdout_write",
        "stderr_read",
        "stderr_write",
        "nul",
    } <= set(cleanup["closed_handles"])
    assert type(cleanup["unmapped_views"]) is list and "parent_write" in cleanup["unmapped_views"]
    if production:
        assert "artifact_harmless_worker" not in cleanup["closed_handles"]
        assert production_outcome in {"complete", "input_refused"}
        assert receipt["outcome"] == production_outcome
    else:
        assert receipt["outcome"] == CONTROL_OUTCOMES[control]
    return actual_request


@pytest.mark.parametrize("control", tuple(CONTROL_OUTCOMES))
def test_registered_harmless_host_lifecycle_complete_receipt(control):
    manifest, template, registration = harmless_registration(control)
    before_template, before_registration = copy.deepcopy(template), copy.deepcopy(registration)
    try:
        response, receipt = host_module()._run_harmless(
            template,
            registration,
            expected_registration_sha256=sha(canonical(registration)),
            expected_execution_sha256=registration["provider_execution_manifest_sha256"],
        )
    except BaseException as error:
        # A real cancellation/resource fault must not discard its owned receipt.
        # Never manufacture one when failure preceded receipt construction.
        if getattr(error, "receipt", None) is not None:
            print("COMPLETE_HARMLESS_REGISTRATION=" + canonical(registration).decode())
            print("COMPLETE_HARMLESS_REQUEST_TEMPLATE=" + canonical(before_template).decode())
            print("COMPLETE_OWNED_RECEIPT=" + canonical(error.receipt).decode())
        raise
    print("COMPLETE_HARMLESS_REGISTRATION=" + canonical(registration).decode())
    print("COMPLETE_HARMLESS_REQUEST_TEMPLATE=" + canonical(before_template).decode())
    print("COMPLETE_OWNED_RECEIPT=" + canonical(receipt).decode())
    assert template == before_template and registration == before_registration
    actual_request = assert_created_receipt(receipt, control, manifest, template, registration)
    no_frame = control in {"never_read", "stdout_excess", "stderr_excess", "memory_error_71"}
    expected = None if no_frame else expected_control_response(control, actual_request, response)
    if expected is not None:
        print("COMPLETE_INDEPENDENT_EXPECTED_RESPONSE=" + canonical(expected).decode())
    intended_stdout = b"" if no_frame else frame(expected)
    intended_stderr = b""
    if control == "stdout_excess":
        intended_stdout = b"X" * 4194305
    elif control == "stderr_excess":
        intended_stderr = b"X" * 65537
    elif control == "stderr_nonempty":
        intended_stderr = b"E"
    elif control == "truncated_response":
        intended_stdout = intended_stdout[:-1]
    elif control == "trailing_response":
        intended_stdout += b"X"
    elif control == "duplicate_response":
        intended_stdout *= 2
    for name, intended in (("stdout", intended_stdout), ("stderr", intended_stderr)):
        observed = receipt["channels"][name]
        size = observed["retained_bytes"]
        assert observed["raw_sha256"] == sha(intended[:size])
        if control not in {"stdout_excess", "stderr_excess"}:
            assert size == len(intended) and observed["eof"] is True
        else:
            assert size <= len(intended)
    if receipt["response"] is not None:
        parsed = receipt["response"]
        exact_keys(
            parsed,
            (
                "parsed_body",
                "canonical_bytes",
                "canonical_sha256",
                "binding_validated",
                "evidence_validated",
            ),
        )
        if parsed["parsed_body"] is not None:
            assert parsed["parsed_body"] == expected
            assert parsed["canonical_bytes"] == len(canonical(expected))
            assert parsed["canonical_sha256"] == sha(canonical(expected))
    if control in {"mapping_roundtrip", "ordinary_refusal", "memory_pressure", "grandchild_denied"}:
        assert response == expected
        assert receipt["response"]["binding_validated"] is True
        assert receipt["response"]["evidence_validated"] is True
        assert receipt["termination"] is None
        assert receipt["exit"]["code"] == (2 if control == "ordinary_refusal" else 0)
    else:
        assert response is None
    if control in {"never_read", "respond_then_wait"}:
        assert receipt["termination"]["requested"] is True
        assert receipt["termination"]["reason"] == "deadline"
    if control in {"stdout_excess", "stderr_excess"}:
        assert receipt["termination"]["requested"] is True
        assert receipt["termination"]["reason"] == "output_limit"
    if control == "valid_then_exit_73":
        assert receipt["exit"]["code"] == 73
    if control == "memory_error_71":
        assert receipt["exit"]["code"] == 71


def harmless_worker_module():
    path = Path(__file__).with_name("native_member_provider_control_worker_20261013.py")
    module = ModuleType("independent_harmless_worker_parser_20261013")
    # Fixed registered source only, never a bytecode cache or member-derived code.
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


@pytest.mark.parametrize(
    "raw",
    (
        b"\xef\xbb\xbf{}",
        b'{"x":1.0}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1e2}',
        b'{"x":123456789012345678901}',
        b'{"x":-123456789012345678901}',
        b"[" * 64 + b"0" + b"]" * 64,
        b"[" + b",".join([b"0"] * 128) + b"]",
    ),
)
def test_harmless_boundary_lexical_limits_precede_json_allocation(monkeypatch, raw):
    worker = harmless_worker_module()

    def sentinel(*args, **kwargs):
        raise AssertionError("JSON tree allocation preceded independent lexical bounds")

    monkeypatch.setattr(worker.json, "loads", sentinel)
    with pytest.raises(ValueError):
        worker._strict_json(raw)


@pytest.mark.parametrize(
    "raw",
    (
        b"",
        b"\xff",
        b'{"x":0,"x":1}',
        b'{"x":01}',
        b'{"x":+1}',
        b'{"x":--1}',
        b'{"x":0} ',
        b'{ "x":0}',
        b'{"z":0,"a":1}',
        b'"\\u0061"',
        b'{"x":0}\0',
        b"{}{}",
        b'"\\q"',
        b'"\\u123"',
        b'"\x01"',
        b'"unterminated',
    ),
)
def test_harmless_boundary_strict_parser_invalid_inputs(raw):
    with pytest.raises((ValueError, UnicodeDecodeError)):
        harmless_worker_module()._strict_json(raw)


def test_harmless_boundary_complete_mapping_copy_and_parser_limits():
    worker = harmless_worker_module()
    request = request_template()
    request["attempt_token"] = TOKEN
    raw = canonical(request)
    assert worker._parse_request(mapping(raw)) == (request, raw)
    numeric = b'{"x":18446744073709551615}'
    assert worker._strict_json(numeric, len(numeric), 3) == {"x": 18446744073709551615}
    for maximum, nodes in ((len(numeric) - 1, 3), (len(numeric), 2)):
        with pytest.raises(ValueError):
            worker._strict_json(numeric, maximum, nodes)
    accepted = b"[" * 63 + b"0" + b"]" * 63
    assert worker._strict_json(accepted) is not None


def bootstrap_literal_corpus():
    manifest_path = ROOT / "src/ai_trader/research/_native_member_execution_v1.json"
    manifest = json.loads(manifest_path.read_bytes())
    names = {
        "engine": "_native_member_engine.py",
        "host": "_native_member_host.py",
        "profile": "_native_member_profile_20261012.json",
        "protocol": "_native_member_protocol_v1.json",
        "types": "_native_member_types.py",
        "worker": "_native_member_worker.py",
    }
    sources = {
        name: (
            b'{"literal":"resource"}'
            if key in {"profile", "protocol"}
            else b'fixed_registered_source_marker = "independent"\n'
        )
        for key, name in names.items()
    }
    manifest["artifacts"] = [
        {
            "logical_id": key,
            "relative_path": names[key],
            "kind": "canonical_json_resource"
            if key in {"profile", "protocol"}
            else "python_module_source",
            "raw_bytes": len(sources[names[key]]),
            "raw_sha256": sha(sources[names[key]]),
        }
        for key in sorted(names)
    ]
    sources["_native_member_execution_v1.json"] = canonical(manifest)
    return manifest, sources


def test_worker_loader_guard_bootstrap_retains_exact_verified_source_bytes(monkeypatch):
    worker = worker_module()
    manifest, sources = bootstrap_literal_corpus()
    monkeypatch.setattr(worker, "_bounded_file", lambda name, maximum: sources[name])
    observed_manifest, verified = worker._bootstrap(
        sha(sources["_native_member_execution_v1.json"])
    )
    assert observed_manifest == manifest
    assert verified == {name[:-3]: raw for name, raw in sources.items() if name.endswith(".py")}


@pytest.mark.parametrize("logical_id", ("engine", "host", "profile", "protocol", "types", "worker"))
def test_worker_loader_guard_bad_source_pin_is_runtime_failure_before_execution(
    monkeypatch, logical_id
):
    worker = worker_module()
    manifest, sources = bootstrap_literal_corpus()
    name = next(
        row["relative_path"] for row in manifest["artifacts"] if row["logical_id"] == logical_id
    )
    sources[name] += b"X"
    monkeypatch.setattr(worker, "_bounded_file", lambda name, maximum: sources[name])
    with pytest.raises(RuntimeError, match="implementation identity mismatch"):
        worker._bootstrap(sha(sources["_native_member_execution_v1.json"]))


def test_worker_loader_guard_bad_manifest_pin_precedes_parser(monkeypatch):
    worker = worker_module()
    _, sources = bootstrap_literal_corpus()
    monkeypatch.setattr(worker, "_bounded_file", lambda name, maximum: sources[name])

    def sentinel(*args):
        raise AssertionError("manifest parser reached before exact source identity")

    monkeypatch.setattr(worker, "_strict", sentinel)
    with pytest.raises(RuntimeError, match="execution identity mismatch"):
        worker._bootstrap("b" * 64)


def test_worker_loader_guard_executes_verified_bytes_not_source_loader_cache(monkeypatch):
    worker = worker_module()
    name = "_native_member_engine"
    assert name not in worker.sys.modules

    def sentinel(*args, **kwargs):
        raise AssertionError("bytecode-capable source loader used")

    monkeypatch.setattr(importlib.machinery.SourceFileLoader, "exec_module", sentinel)
    monkeypatch.setattr(importlib.machinery.SourceFileLoader, "get_code", sentinel)
    literal_source = b'fixed_registered_source_marker = "independent"\n'
    try:
        loaded = worker._load(name, {name: literal_source})
        assert loaded.fixed_registered_source_marker == "independent"
        assert worker.sys.modules[name] is loaded
    finally:
        worker.sys.modules.pop(name, None)


@pytest.mark.parametrize(
    "raw",
    (
        b'{"x":1.0}',
        b'{"x":NaN}',
        b'{"x":123456789012345678901}',
        b"[" * 64 + b"0" + b"]" * 64,
        b"[" + b",".join([b"0"] * 128) + b"]",
    ),
)
def test_harmless_boundary_mapping_lexical_limits_precede_json_allocation(monkeypatch, raw):
    worker = harmless_worker_module()

    def sentinel(*args, **kwargs):
        raise AssertionError("mapped JSON allocation preceded lexical resource checks")

    monkeypatch.setattr(worker.json, "loads", sentinel)
    with pytest.raises(ValueError):
        worker._parse_request(mapping(raw))


RECEIPT_FIELDS = (
    "schema",
    "operation",
    "execution_manifest_sha256",
    "attempt_token",
    "started_utc",
    "finished_utc",
    "elapsed_ns",
    "request",
    "parent",
    "child",
    "command",
    "mapping",
    "limits",
    "job",
    "channels",
    "implementation_checks",
    "response",
    "exit",
    "termination",
    "cleanup",
    "outcome",
)


def failure_only_api(closes, close_error=None):
    class FakeApi:
        def CloseHandle(self, handle):
            closes.append(handle)
            if close_error is not None:
                raise close_error
            return 1

        def __getattr__(self, name):
            raise AssertionError("unexpected WinAPI access in native-free failure test: " + name)

    return FakeApi()


@pytest.mark.parametrize("stage", ("prepare", "create", "monitor"))
@pytest.mark.parametrize("kind", (KeyboardInterrupt, SystemExit, MemoryError, AssertionError))
def test_host_failure_injection_preserves_original_critical_error_after_cleanup(
    monkeypatch, stage, kind
):
    host = host_module()
    original, closes, attempts = kind("independent injected failure"), [], []

    def prepare(attempt, *args):
        attempts.append(attempt)
        attempt.api = failure_only_api(closes)
        attempt.handles["artifact_host"] = 101
        if stage == "prepare":
            raise original
        return request_template(), b""

    def create(*args):
        if stage == "create":
            raise original

    def monitor(attempt):
        assert stage == "monitor"
        raise original

    monkeypatch.setattr(host, "_prepare", prepare)
    monkeypatch.setattr(host, "_create", create)
    monkeypatch.setattr(host._Attempt, "monitor", monitor)
    with pytest.raises(kind) as caught:
        host._execute(request_template(), EXECUTION_SHA)
    assert caught.value is original
    receipt = caught.value.receipt
    exact_keys(receipt, RECEIPT_FIELDS)
    assert closes == [101] and attempts[0].handles == {}
    assert receipt["cleanup"] == {
        "completed": True,
        "closed_handles": ["artifact_host"],
        "unmapped_views": [],
        "errors": [],
    }
    assert receipt["channels"] is None and receipt["termination"] is None
    assert receipt["exit"] is None and receipt["child"] is None and receipt["response"] is None
    expected = (
        "resource_failed"
        if kind is MemoryError
        else "worker_failed"
        if kind is AssertionError
        else "cancelled"
    )
    assert receipt["outcome"] == expected
    assert type(receipt["elapsed_ns"]) is int and receipt["elapsed_ns"] >= 0
    assert type(receipt["finished_utc"]) is str


@pytest.mark.parametrize("kind", (ValueError, OSError, RuntimeError))
@pytest.mark.parametrize("harmless", (False, True))
def test_host_failure_injection_setup_refusal_is_not_success_or_input_refusal(
    monkeypatch, kind, harmless
):
    host, closes = host_module(), []

    def prepare(attempt, *args):
        attempt.api = failure_only_api(closes)
        attempt.handles["artifact_host"] = 102
        raise kind("setup is not member refusal")

    monkeypatch.setattr(host, "_prepare", prepare)
    if harmless:
        response, receipt = host._execute(request_template(), EXECUTION_SHA, {})
        assert response is None
    else:
        with pytest.raises(RuntimeError) as caught:
            host._execute(request_template(), EXECUTION_SHA)
        assert type(caught.value) is RuntimeError
        receipt = caught.value.receipt
    assert closes == [102]
    assert receipt["outcome"] == "setup_failed"
    assert receipt["cleanup"]["completed"] is True
    assert all(receipt[name] is None for name in ("channels", "job", "child", "exit", "response"))


@pytest.mark.parametrize(
    "original_kind", (KeyboardInterrupt, SystemExit, MemoryError, AssertionError)
)
@pytest.mark.parametrize("cleanup_kind", (RuntimeError, AssertionError))
def test_host_failure_injection_cleanup_uncertainty_keeps_original_error_and_owned_handle(
    monkeypatch, original_kind, cleanup_kind
):
    host, attempts, closes = host_module(), [], []
    original, secondary = original_kind("primary"), cleanup_kind("secondary")

    def prepare(attempt, *args):
        attempts.append(attempt)
        attempt.api = failure_only_api(closes, secondary)
        attempt.handles["artifact_host"] = 103
        raise original

    monkeypatch.setattr(host, "_prepare", prepare)
    with pytest.raises(original_kind) as caught:
        host._execute(request_template(), EXECUTION_SHA)
    assert caught.value is original
    assert closes == [103] and attempts[0].handles == {"artifact_host": 103}
    assert caught.value.receipt["outcome"] == "cleanup_failed"
    assert caught.value.receipt["cleanup"] == {
        "completed": False,
        "closed_handles": [],
        "unmapped_views": [],
        "errors": [{"operation": "CloseHandle", "kind": cleanup_kind.__name__, "winerror": None}],
    }


@pytest.mark.parametrize("kind", (KeyboardInterrupt, SystemExit, MemoryError, AssertionError))
def test_host_failure_injection_cleanup_critical_error_cannot_become_positive(monkeypatch, kind):
    host, closes = host_module(), []
    original = kind("cleanup sentinel")

    def prepare(attempt, *args):
        attempt.api = failure_only_api(closes, original)
        attempt.handles["artifact_host"] = 104
        return request_template(), b""

    monkeypatch.setattr(host, "_prepare", prepare)
    monkeypatch.setattr(host, "_create", lambda *args: None)
    monkeypatch.setattr(host._Attempt, "monitor", lambda attempt: None)
    with pytest.raises(kind) as caught:
        host._execute(request_template(), EXECUTION_SHA)
    assert caught.value is original and closes == [104]
    assert caught.value.receipt["cleanup"]["completed"] is False
    assert caught.value.receipt["outcome"] == "cleanup_failed"


@pytest.mark.parametrize("stage", ("none", "stdout"))
def test_host_failure_injection_uncreated_channels_stay_null(monkeypatch, stage):
    host = host_module()
    attempt = host._Attempt(EXECUTION_SHA, False)
    attempt.api = failure_only_api([])
    if stage == "stdout":
        attempt.receipt["channels"] = {
            "stdout": {
                "retained_bytes": 0,
                "raw_sha256": sha(b""),
                "eof": False,
                "hash_scope": "retained_prefix",
            },
            "stderr": None,
        }
    attempt.cleanup()
    if stage == "none":
        assert attempt.receipt["channels"] is None
    else:
        assert attempt.receipt["channels"]["stderr"] is None
        assert attempt.receipt["channels"]["stdout"] == {
            "retained_bytes": 0,
            "raw_sha256": sha(b""),
            "eof": False,
            "hash_scope": "retained_prefix",
        }
    assert attempt.receipt["cleanup"]["completed"] is True


@pytest.mark.parametrize("mode", ("failed", "exception"))
@pytest.mark.parametrize("value", (0, 201))
def test_host_failure_injection_duplicate_mapping_captures_partial_outputs(
    monkeypatch, mode, value
):
    host, closes = host_module(), []
    original = AssertionError("DuplicateHandle partial-return sentinel")

    class FakeApi:
        def GetCurrentProcess(self):
            return -1

        def DuplicateHandle(self, owner, handle, target, output, access, inherit, options):
            assert (owner, handle, target, access, inherit, options) == (-1, 200, -1, 4, True, 0)
            output._obj.value = value
            if mode == "exception":
                raise original
            return 0

        def CloseHandle(self, handle):
            closes.append(handle)
            return 1

    attempt = host._Attempt(EXECUTION_SHA, False)
    attempt.api = FakeApi()
    with pytest.raises(AssertionError if mode == "exception" else OSError) as caught:
        host._duplicate_read_mapping(attempt, 200)
    if mode == "exception":
        assert caught.value is original
    assert attempt.handles == ({"request_read": value} if value else {})
    attempt.cleanup()
    assert closes == ([value] if value else []) and not attempt.handles


@pytest.mark.parametrize("mode", ("failed", "exception"))
@pytest.mark.parametrize("values", ((0, 0), (301, 0), (0, 302), (301, 302)))
def test_host_failure_injection_pipe_captures_every_partial_endpoint(monkeypatch, mode, values):
    host, closes = host_module(), []
    original = AssertionError("CreatePipe partial-return sentinel")

    class FakeApi:
        def CreatePipe(self, reader, writer, security, capacity):
            assert capacity == 65536
            reader._obj.value, writer._obj.value = values
            if mode == "exception":
                raise original
            return 0

        def CloseHandle(self, handle):
            closes.append(handle)
            return 1

    attempt = host._Attempt(EXECUTION_SHA, False)
    attempt.api = FakeApi()
    attempt.receipt["channels"] = {"stdout": None, "stderr": None}
    security = host._SecurityAttributes()
    with pytest.raises(AssertionError if mode == "exception" else OSError) as caught:
        host._create_pipe(attempt, "stdout", security)
    if mode == "exception":
        assert caught.value is original
    expected = {
        name: value
        for name, value in zip(("stdout_read", "stdout_write"), values, strict=True)
        if value
    }
    assert attempt.handles == expected
    assert attempt.receipt["channels"]["stderr"] is None
    assert attempt.receipt["channels"]["stdout"] == (
        {
            "retained_bytes": None,
            "raw_sha256": None,
            "eof": None,
            "hash_scope": None,
        }
        if expected
        else None
    )
    attempt.cleanup()
    assert closes == list(expected.values()) and not attempt.handles
    assert attempt.receipt["channels"]["stderr"] is None


@pytest.mark.parametrize("ts_out", (False, True), ids=("absent", "present"))
def test_registered_native_member_minimal_public_decode_verify_repeat(monkeypatch, ts_out):
    """Actual contained codecs: root registers and launches this cohort only."""
    provider = importlib.import_module("ai_trader.research.six_e_native_member_decode_evidence")
    host = host_module()
    member, expected_body = ORACLE.minimal_evidence_body(ts_out)
    expected_record = ORACLE.typed_evidence(provider, expected_body)
    context = provider.MemberDecodeContext(ORACLE.PROFILE_ID, "ZSTD_CONCAT", 3, "AS_IS", ts_out)
    pins = {
        "expected_" + name + "_sha256": expected_body[name + "_sha256"]
        for name in ("protocol", "profile", "runtime_manifest", "member", "metadata")
    }
    manifest_raw = (ROOT / "src/ai_trader/research/_native_member_execution_v1.json").read_bytes()
    manifest = json.loads(manifest_raw)
    assert canonical(manifest) == manifest_raw and sha(manifest_raw) == REGISTERED_EXECUTION_SHA
    expected_template = {
        "schema": "native_member_worker_request_v1",
        "operation": "decode",
        "context": ORACLE.context_body(ts_out),
        "member_hex": member.hex(),
        **pins,
        "execution_manifest_sha256": REGISTERED_EXECUTION_SHA,
        "attempt_token": "0" * 64,
    }
    original_run, receipts = host.run_decode, []
    print("COMPLETE_INDEPENDENT_NATIVE_MEMBER_HEX=" + member.hex())
    print("COMPLETE_INDEPENDENT_NATIVE_EXPECTED_BODY=" + canonical(expected_body).decode())

    def recorded_run(template, execution_sha):
        assert template == expected_template and execution_sha == REGISTERED_EXECUTION_SHA
        before = copy.deepcopy(template)
        try:
            response, receipt = original_run(template, execution_sha)
        except BaseException as error:
            if getattr(error, "receipt", None) is not None:
                print("COMPLETE_NATIVE_REQUEST_TEMPLATE=" + canonical(before).decode())
                print("COMPLETE_NATIVE_OWNED_RECEIPT=" + canonical(error.receipt).decode())
            raise
        print("COMPLETE_NATIVE_REQUEST_TEMPLATE=" + canonical(before).decode())
        print("COMPLETE_NATIVE_OWNED_RECEIPT=" + canonical(receipt).decode())
        print("COMPLETE_NATIVE_ACTUAL_RESPONSE=" + canonical(response).decode())
        assert template == before
        actual_request = assert_created_receipt(
            receipt,
            None,
            manifest,
            before,
            {"provider_execution_manifest_sha256": REGISTERED_EXECUTION_SHA},
            production=True,
        )
        expected_response = {
            "schema": "native_member_worker_response_v1",
            "attempt_token": receipt["attempt_token"],
            "request_sha256": sha(canonical(actual_request)),
            "execution_manifest_sha256": REGISTERED_EXECUTION_SHA,
            "status": "complete",
            "evidence": expected_body,
            "failure_kind": None,
        }
        assert response == expected_response
        stdout = frame(expected_response)
        assert receipt["channels"] == {
            "stdout": {
                "retained_bytes": len(stdout),
                "raw_sha256": sha(stdout),
                "eof": True,
                "hash_scope": "complete",
            },
            "stderr": {
                "retained_bytes": 0,
                "raw_sha256": sha(b""),
                "eof": True,
                "hash_scope": "complete",
            },
        }
        assert receipt["response"] == {
            "parsed_body": expected_response,
            "canonical_bytes": len(canonical(expected_response)),
            "canonical_sha256": sha(canonical(expected_response)),
            "binding_validated": True,
            "evidence_validated": True,
        }
        assert receipt["exit"]["code"] == 0 and receipt["termination"] is None
        receipts.append(copy.deepcopy(receipt))
        return response, receipt

    monkeypatch.setattr(host, "run_decode", recorded_run)
    actual = provider.decode_member(member, context, **pins)
    assert actual == expected_record and type(actual) is provider.MemberDecodeEvidence
    assert (
        provider.verify(
            actual,
            member,
            context,
            **pins,
            expected_evidence_sha256=expected_body["evidence_sha256"],
        )
        is None
    )
    repeated = provider.decode_member(member, context, **pins)
    assert repeated == expected_record and repeated is not actual
    assert len(receipts) == 3
    assert len({receipt["attempt_token"] for receipt in receipts}) == 3
    assert (
        len(
            {
                (receipt["child"]["pid"], receipt["child"]["creation_filetime"])
                for receipt in receipts
            }
        )
        == 3
    )


def assert_native_response_receipt(response, receipt, manifest, template, expected_body):
    refused = expected_body is None
    actual_request = assert_created_receipt(
        receipt,
        None,
        manifest,
        template,
        {"provider_execution_manifest_sha256": REGISTERED_EXECUTION_SHA},
        production=True,
        production_outcome="input_refused" if refused else "complete",
    )
    expected_response = {
        "schema": "native_member_worker_response_v1",
        "attempt_token": receipt["attempt_token"],
        "request_sha256": sha(canonical(actual_request)),
        "execution_manifest_sha256": REGISTERED_EXECUTION_SHA,
        "status": "refused" if refused else "complete",
        "evidence": expected_body,
        "failure_kind": "invalid_member" if refused else None,
    }
    assert response == expected_response
    stdout = frame(expected_response)
    assert receipt["channels"] == {
        "stdout": {
            "retained_bytes": len(stdout),
            "raw_sha256": sha(stdout),
            "eof": True,
            "hash_scope": "complete",
        },
        "stderr": {
            "retained_bytes": 0,
            "raw_sha256": sha(b""),
            "eof": True,
            "hash_scope": "complete",
        },
    }
    assert receipt["response"] == {
        "parsed_body": expected_response,
        "canonical_bytes": len(canonical(expected_response)),
        "canonical_sha256": sha(canonical(expected_response)),
        "binding_validated": True,
        "evidence_validated": True,
    }
    assert receipt["exit"]["code"] == (2 if refused else 0)
    assert receipt["termination"] is None


@pytest.mark.parametrize("case", ORACLE.native_member_cases(), ids=lambda case: case["id"])
def test_registered_native_member_rich_independent_cohort(monkeypatch, case):
    """Every literal oracle case is prospectively registered before root runs."""
    exact_keys(
        case, ("id", "member", "context", "expected_body", "expected_metadata_sha256", "refusal")
    )
    assert type(case["id"]) is str and case["id"]
    assert type(case["member"]) is bytes
    assert case["refusal"] in {None, "preflight", "worker"}
    assert type(case["expected_metadata_sha256"]) is str
    assert re.fullmatch("[0-9a-f]{64}", case["expected_metadata_sha256"])
    expected_body, member = case["expected_body"], case["member"]
    assert (expected_body is None) is (case["refusal"] is not None)
    provider = importlib.import_module("ai_trader.research.six_e_native_member_decode_evidence")
    host = host_module()
    declared_context = case["context"]
    exact_keys(
        declared_context,
        ("profile_id", "member_compression", "input_version", "upgrade_policy", "expected_ts_out"),
    )
    context = provider.MemberDecodeContext(
        declared_context["profile_id"],
        declared_context["member_compression"],
        declared_context["input_version"],
        declared_context["upgrade_policy"],
        declared_context["expected_ts_out"],
    )
    pins = {
        "expected_protocol_sha256": ORACLE.digest(ORACLE.protocol_literal()),
        "expected_profile_sha256": ORACLE.PROFILE_SHA256,
        "expected_runtime_manifest_sha256": ORACLE.RUNTIME_SHA256,
        "expected_member_sha256": sha(member),
        "expected_metadata_sha256": case["expected_metadata_sha256"],
    }
    manifest_raw = (ROOT / "src/ai_trader/research/_native_member_execution_v1.json").read_bytes()
    manifest = json.loads(manifest_raw)
    assert canonical(manifest) == manifest_raw and sha(manifest_raw) == REGISTERED_EXECUTION_SHA
    template = {
        "schema": "native_member_worker_request_v1",
        "operation": "decode",
        "context": copy.deepcopy(declared_context),
        "member_hex": member.hex(),
        **pins,
        "execution_manifest_sha256": REGISTERED_EXECUTION_SHA,
        "attempt_token": "0" * 64,
    }
    print("COMPLETE_NATIVE_CASE_ID=" + case["id"])
    print("COMPLETE_INDEPENDENT_NATIVE_MEMBER_HEX=" + member.hex())
    print("COMPLETE_INDEPENDENT_NATIVE_CONTEXT=" + canonical(declared_context).decode())
    print("COMPLETE_INDEPENDENT_NATIVE_EXPECTED_BODY=" + canonical(expected_body).decode())
    print(
        "COMPLETE_INDEPENDENT_NATIVE_EXPECTED_METADATA_SHA256=" + case["expected_metadata_sha256"]
    )
    print("COMPLETE_NATIVE_EXPECTED_REFUSAL_STAGE=" + str(case["refusal"]))
    captured, original_run = [], host.run_decode

    def recording_run(actual_template, execution_sha):
        assert actual_template == template and execution_sha == REGISTERED_EXECUTION_SHA
        before = copy.deepcopy(actual_template)
        if case["refusal"] == "preflight":
            raise AssertionError("preflight case attempted a worker invocation")
        try:
            response, receipt = original_run(actual_template, execution_sha)
        except BaseException as error:
            receipt = getattr(error, "receipt", None)
            if receipt is not None:
                print("COMPLETE_NATIVE_REQUEST_TEMPLATE=" + canonical(before).decode())
                print("COMPLETE_NATIVE_OWNED_RECEIPT=" + canonical(receipt).decode())
                parsed = receipt["response"]
                response = None if parsed is None else parsed["parsed_body"]
                print("COMPLETE_NATIVE_ACTUAL_RESPONSE=" + canonical(response).decode())
                captured.append((copy.deepcopy(response), copy.deepcopy(receipt)))
            raise
        print("COMPLETE_NATIVE_REQUEST_TEMPLATE=" + canonical(before).decode())
        print("COMPLETE_NATIVE_OWNED_RECEIPT=" + canonical(receipt).decode())
        print("COMPLETE_NATIVE_ACTUAL_RESPONSE=" + canonical(response).decode())
        assert actual_template == before
        captured.append((copy.deepcopy(response), copy.deepcopy(receipt)))
        return response, receipt

    monkeypatch.setattr(host, "run_decode", recording_run)
    if case["refusal"] is not None:
        with pytest.raises(ValueError) as caught:
            provider.decode_member(member, context, **pins)
        assert type(caught.value) is ValueError
        if case["refusal"] == "preflight":
            assert captured == [] and getattr(caught.value, "receipt", None) is None
        else:
            assert len(captured) == 1 and caught.value.receipt == captured[0][1]
            assert_native_response_receipt(*captured[0], manifest, template, None)
        return
    assert expected_body["metadata_sha256"] == case["expected_metadata_sha256"]
    assert expected_body["member_sha256"] == sha(member)
    assert expected_body["context_sha256"] == sha(canonical(declared_context))
    expected_record = ORACLE.typed_evidence(provider, expected_body)
    actual = provider.decode_member(member, context, **pins)
    assert type(actual) is provider.MemberDecodeEvidence and actual == expected_record
    assert len(captured) == 1
    assert_native_response_receipt(*captured[0], manifest, template, expected_body)
    assert (
        provider.verify(
            actual,
            member,
            context,
            **pins,
            expected_evidence_sha256=expected_body["evidence_sha256"],
        )
        is None
    )
    assert len(captured) == 2
    assert_native_response_receipt(*captured[1], manifest, template, expected_body)
    assert captured[0][1]["attempt_token"] != captured[1][1]["attempt_token"]
    assert (captured[0][1]["child"]["pid"], captured[0][1]["child"]["creation_filetime"]) != (
        captured[1][1]["child"]["pid"],
        captured[1][1]["child"]["creation_filetime"],
    )
