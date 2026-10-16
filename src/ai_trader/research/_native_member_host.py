"""Fixed native-codec-free provider host; no public launch or policy hooks.

The private lifecycle is qualified separately from the old proof harness.  Its
job is a committed-memory/CPU/process limit, not a filesystem/network sandbox.
"""

import ctypes as C
import hashlib
import os
import re
import secrets
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

if __package__:
    from . import _native_member_types as _types
else:
    import _native_member_types as _types


MAPPING_BYTES = 1048576
REQUEST_MAGIC = b"NMREQ001"
RESPONSE_MAGIC = b"NMRES001"
REQUEST_KEYS = frozenset(
    {
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
    }
)
RESPONSE_KEYS = frozenset(
    {
        "schema",
        "attempt_token",
        "request_sha256",
        "execution_manifest_sha256",
        "status",
        "evidence",
        "failure_kind",
    }
)
ARTIFACT_FILES = {
    "engine": "_native_member_engine.py",
    "host": "_native_member_host.py",
    "profile": "_native_member_profile_20261012.json",
    "protocol": "_native_member_protocol_v1.json",
    "types": "_native_member_types.py",
    "worker": "_native_member_worker.py",
}
LAUNCH_POLICY = {
    "python_logical_id": "python.exe",
    "switches": ["-I", "-S", "-B"],
    "worker_arguments": ["--mapping-handle", "HOST_GENERATED_UINT", "--mapping-size", "1048576"],
    "inherit_handles": ["mapping_read", "stdout_write", "stderr_write", "nul_read"],
    "environment_keys": ["SystemRoot"],
    "cwd_policy": "fixed_installation_root",
}
TRANSPORT_POLICY = {
    "request_schema": "native_member_worker_request_v1",
    "response_schema": "native_member_worker_response_v1",
    "request_magic": "NMREQ001",
    "response_magic": "NMRES001",
    "length_encoding": "uint32_le",
    "mapping_bytes": 1048576,
    "request_json_max_bytes": 1048564,
    "response_json_max_bytes": 2097152,
    "stderr_max_bytes": 65536,
    "combined_output_max_bytes": 4194304,
    "read_quantum_bytes": 65536,
    "request_padding": "all_zero",
    "response_count": 1,
    "attempt_token_bytes": 32,
}
PARSER_POLICY = {
    "encoding": "strict_utf8_no_bom",
    "canonical_json_required": True,
    "duplicate_keys": "refuse",
    "floats_and_nonfinite": "refuse",
    "max_depth": 64,
    "max_integer_digits": 20,
    "integer_sign": "optional_single_leading_minus",
    "resource_max_bytes": 4194304,
    "execution_manifest_max_bytes": 65536,
    "resource_max_nodes": 1048576,
    "request_max_nodes": 128,
    "response_max_nodes": 1048576,
    "node_definition": "each_object_array_key_and_scalar_once",
    "bounds_checked": "lexically_before_json_object_allocation",
}
RESOURCE_POLICY = {
    "limit_flags": 8974,
    "active_process_limit": 1,
    "process_memory_bytes": 268435456,
    "job_memory_bytes": 268435456,
    "process_user_time_100ns": 50000000,
    "job_user_time_100ns": 50000000,
    "work_ns": 12000000000,
    "teardown_ns": 3000000000,
    "birth_job_assignment": True,
    "start_suspended": True,
    "native_in_parent": False,
    "uncontained_fallback": False,
    "parent_memory_sandbox": False,
    "filesystem_sandbox": False,
    "network_sandbox": False,
}
EXIT_POLICY = [
    [0, "complete", "complete"],
    [2, "refused", "ValueError"],
    [70, None, "RuntimeError_identity"],
    [71, None, "MemoryError"],
    [72, None, "RuntimeError_private_protocol"],
]
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


def _require(condition, message="invalid private provider boundary"):
    if not condition:
        raise ValueError(message)


def _pin(value):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None)


def _same(left, right):
    return _types.canonical_bytes(left) == _types.canonical_bytes(right)


def _fixed_raw(name, maximum):
    _require(
        name
        in {
            *ARTIFACT_FILES.values(),
            "_native_member_execution_v1.json",
            "six_e_native_member_decode_evidence.py",
        }
    )
    path = Path(__file__).with_name(name)
    _require(not path.is_symlink(), "linked implementation artifact")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    _require(0 < len(raw) <= maximum, "implementation artifact byte limit")
    return raw


def _execution_manifest(expected_sha256):
    """Read only the fixed registration and validate every policy exactly."""
    _pin(expected_sha256)
    raw = _fixed_raw("_native_member_execution_v1.json", 65536)
    _require(hashlib.sha256(raw).hexdigest() == expected_sha256, "execution identity mismatch")
    body = _types.strict_json_loads(raw, 65536)
    _require(
        type(body) is dict
        and set(body)
        == {
            "schema",
            "protocol_sha256",
            "profile_sha256",
            "runtime_manifest_sha256",
            "platform",
            "entry_point",
            "launch_policy",
            "artifacts",
            "bootstrap_exclusions",
            "transport_policy",
            "parser_policy",
            "resource_policy",
            "exit_policy",
        }
    )
    fixed = {
        "schema": "native_member_provider_execution_v1",
        "protocol_sha256": _types._PROTOCOL_SHA,
        "profile_sha256": _types._PROFILE_SHA,
        "runtime_manifest_sha256": _types._RUNTIME_SHA,
        "platform": "windows_amd64_cpython312",
        "entry_point": "_native_member_worker.py",
        "launch_policy": LAUNCH_POLICY,
        "transport_policy": TRANSPORT_POLICY,
        "parser_policy": PARSER_POLICY,
        "resource_policy": RESOURCE_POLICY,
        "exit_policy": EXIT_POLICY,
        "bootstrap_exclusions": [
            "six_e_native_member_decode_evidence.py",
            "_native_member_execution_v1.json",
        ],
    }
    for key, value in fixed.items():
        _require(_same(body[key], value), "execution policy mismatch")
    rows = body["artifacts"]
    _require(type(rows) is list and len(rows) == 6)
    for row, logical_id in zip(rows, sorted(ARTIFACT_FILES), strict=True):
        _require(
            type(row) is dict
            and set(row) == {"logical_id", "relative_path", "kind", "raw_bytes", "raw_sha256"}
        )
        expected_kind = (
            "canonical_json_resource"
            if logical_id in {"profile", "protocol"}
            else "python_module_source"
        )
        _require(
            row["logical_id"] == logical_id
            and row["relative_path"] == ARTIFACT_FILES[logical_id]
            and row["kind"] == expected_kind
        )
        _require(type(row["raw_bytes"]) is int and 0 < row["raw_bytes"] <= 4194304)
        _pin(row["raw_sha256"])
    return body


def _implementation_observations(manifest):
    observations = []
    for row in manifest["artifacts"]:
        raw = _fixed_raw(ARTIFACT_FILES[row["logical_id"]], 4194304)
        observed = {
            "logical_id": row["logical_id"],
            "raw_bytes": len(raw),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
        _require(
            observed["raw_bytes"] == row["raw_bytes"]
            and observed["raw_sha256"] == row["raw_sha256"],
            "implementation artifact identity mismatch",
        )
        observations.append(observed)
    return observations


def _validate_request(body, expected_execution_sha256, *, template):
    _pin(expected_execution_sha256)
    _require(type(body) is dict and set(body) == REQUEST_KEYS)
    _require(body["schema"] == "native_member_worker_request_v1" and body["operation"] == "decode")
    for key in REQUEST_KEYS - {"schema", "operation", "context", "member_hex"}:
        _pin(body[key])
    _require(body["execution_manifest_sha256"] == expected_execution_sha256)
    if template:
        _require(body["attempt_token"] == "0" * 64, "request must be a zero-token template")
    _require(
        body["expected_protocol_sha256"] == _types._PROTOCOL_SHA
        and body["expected_profile_sha256"] == _types._PROFILE_SHA
        and body["expected_runtime_manifest_sha256"] == _types._RUNTIME_SHA
    )
    _types.validate_body("Context", body["context"])
    encoded = body["member_hex"]
    _require(
        type(encoded) is str
        and 2 <= len(encoded) <= 524288
        and len(encoded) % 2 == 0
        and re.fullmatch(r"[0-9a-f]+", encoded) is not None
    )
    _require(hashlib.sha256(bytes.fromhex(encoded)).hexdigest() == body["expected_member_sha256"])
    return body


def _mapping_bytes(canonical_request):
    _require(type(canonical_request) is bytes and 0 < len(canonical_request) <= MAPPING_BYTES - 12)
    return (
        REQUEST_MAGIC
        + len(canonical_request).to_bytes(4, "little")
        + canonical_request
        + bytes(MAPPING_BYTES - 12 - len(canonical_request))
    )


def _request_bytes(request_template, expected_execution_sha256):
    _validate_request(request_template, expected_execution_sha256, template=True)
    request = _types.strict_json_loads(_types.canonical_bytes(request_template), 1048564, 128)
    request["attempt_token"] = secrets.token_hex(32)
    raw = _types.canonical_bytes(request)
    return request, raw, _mapping_bytes(raw)


def _response_body(raw_stdout, request_body, request_sha256, *, harmless=False):
    _pin(request_sha256)
    _require(type(raw_stdout) is bytes and 12 < len(raw_stdout) <= 2097164, "response byte limit")
    _require(raw_stdout[:8] == RESPONSE_MAGIC, "response magic mismatch")
    length = int.from_bytes(raw_stdout[8:12], "little")
    _require(0 < length <= 2097152 and length + 12 == len(raw_stdout), "response framing mismatch")
    body = _types.strict_json_loads(raw_stdout[12:], 2097152)
    _require(type(body) is dict and set(body) == RESPONSE_KEYS)
    schema = (
        "native_member_harmless_response_v1" if harmless else "native_member_worker_response_v1"
    )
    _require(body["schema"] == schema)
    for key, expected in (
        ("attempt_token", request_body["attempt_token"]),
        ("request_sha256", request_sha256),
        ("execution_manifest_sha256", request_body["execution_manifest_sha256"]),
    ):
        _pin(body[key])
        _require(body[key] == expected, "response binding mismatch")
    if body["status"] == "refused":
        _require(body["evidence"] is None and body["failure_kind"] == "invalid_member")
    else:
        _require(body["status"] == "complete" and body["failure_kind"] is None)
        if not harmless:
            evidence = body["evidence"]
            _types.validate_body("MemberDecodeEvidence", evidence)
            for field in ("protocol", "profile", "runtime_manifest", "member", "metadata"):
                _require(
                    evidence[field + "_sha256"] == request_body["expected_" + field + "_sha256"]
                )
            _require(evidence["context_sha256"] == _types.body_sha256(request_body["context"]))
            _require(
                evidence["occurrences"][0]["projection"]["ts_out"]
                is request_body["context"]["expected_ts_out"]
            )
        else:
            evidence = body["evidence"]
            _require(
                type(evidence) is dict
                and set(evidence)
                == {"schema", "control_id", "request_body", "mapping_sha256", "result"}
            )
            _require(
                evidence["schema"] == "native_member_harmless_observation_v1"
                and evidence["control_id"] in CONTROL_OUTCOMES
            )
            _require(_same(evidence["request_body"], request_body))
            _require(
                evidence["mapping_sha256"]
                == hashlib.sha256(_mapping_bytes(_types.canonical_bytes(request_body))).hexdigest()
            )
            _require(type(evidence["result"]) is dict)
    return body


def _control_registration(
    request_template, registration, expected_registration_sha256, expected_execution_sha256
):
    _pin(expected_registration_sha256)
    _require(
        type(registration) is dict
        and set(registration)
        == {
            "schema",
            "provider_execution_manifest_sha256",
            "control_id",
            "worker",
            "argument_template",
            "request_template_sha256",
            "expected_outcome",
            "native_codec_imports",
        }
    )
    _require(_types.body_sha256(registration) == expected_registration_sha256)
    _require(
        registration["schema"] == "native_member_harmless_execution_v1"
        and registration["provider_execution_manifest_sha256"] == expected_execution_sha256
        and registration["native_codec_imports"] is False
    )
    control = registration["control_id"]
    _require(type(control) is str and control in CONTROL_OUTCOMES)
    _require(registration["expected_outcome"] == CONTROL_OUTCOMES[control])
    _require(
        _same(
            registration["argument_template"],
            [
                "--mapping-handle",
                "HOST_GENERATED_UINT",
                "--mapping-size",
                "1048576",
                "--control",
                control,
            ],
        )
    )
    _pin(registration["request_template_sha256"])
    _require(registration["request_template_sha256"] == _types.body_sha256(request_template))
    worker = registration["worker"]
    _require(
        type(worker) is dict
        and set(worker) == {"logical_id", "relative_path", "raw_bytes", "raw_sha256"}
    )
    _require(
        worker["logical_id"] == "harmless_worker"
        and worker["relative_path"] == "tests/native_member_provider_control_worker_20261013.py"
    )
    _require(type(worker["raw_bytes"]) is int and 0 < worker["raw_bytes"] <= 1048576)
    _pin(worker["raw_sha256"])
    return registration


DWORD, WORD, BOOL = C.c_uint32, C.c_uint16, C.c_int32
HANDLE, VOID, SIZE_T = C.c_void_p, C.c_void_p, C.c_size_t
INVALID_HANDLE = C.c_void_p(-1).value
WAIT_TIMEOUT, TERMINATION_CODE = 258, 0xE0000001
CREATION_FLAGS = 0x08080004 | 0x00000400
_PYTHON = Path("C:/Users/pabta/AppData/Local/Programs/Python/Python312/python.exe")
_PYTHON_SHA = "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a"
_ROOT = Path(__file__).resolve().parents[3]


class _SecurityAttributes(C.Structure):
    _fields_ = [("length", DWORD), ("descriptor", VOID), ("inherit", BOOL)]


class _StartupInfo(C.Structure):
    _fields_ = [
        ("cb", DWORD),
        ("reserved", C.c_wchar_p),
        ("desktop", C.c_wchar_p),
        ("title", C.c_wchar_p),
        ("x", DWORD),
        ("y", DWORD),
        ("x_size", DWORD),
        ("y_size", DWORD),
        ("x_chars", DWORD),
        ("y_chars", DWORD),
        ("fill", DWORD),
        ("flags", DWORD),
        ("show", WORD),
        ("reserved_size", WORD),
        ("reserved_bytes", VOID),
        ("stdin", HANDLE),
        ("stdout", HANDLE),
        ("stderr", HANDLE),
    ]


class _StartupInfoEx(C.Structure):
    _fields_ = [("startup", _StartupInfo), ("attributes", VOID)]


class _ProcessInformation(C.Structure):
    _fields_ = [("process", HANDLE), ("thread", HANDLE), ("pid", DWORD), ("tid", DWORD)]


class _BasicLimits(C.Structure):
    _fields_ = [
        ("process_time", C.c_int64),
        ("job_time", C.c_int64),
        ("flags", DWORD),
        ("minimum_working_set", SIZE_T),
        ("maximum_working_set", SIZE_T),
        ("active_processes", DWORD),
        ("affinity", SIZE_T),
        ("priority", DWORD),
        ("scheduling", DWORD),
    ]


class _IoCounters(C.Structure):
    _fields_ = [
        (name, C.c_uint64)
        for name in (
            "read_operations",
            "write_operations",
            "other_operations",
            "read_bytes",
            "write_bytes",
            "other_bytes",
        )
    ]


class _ExtendedLimits(C.Structure):
    _fields_ = [
        ("basic", _BasicLimits),
        ("io", _IoCounters),
        ("process_memory", SIZE_T),
        ("job_memory", SIZE_T),
        ("peak_process_memory", SIZE_T),
        ("peak_job_memory", SIZE_T),
    ]


class _Accounting(C.Structure):
    _fields_ = [
        ("user_time", C.c_int64),
        ("kernel_time", C.c_int64),
        ("period_user_time", C.c_int64),
        ("period_kernel_time", C.c_int64),
        ("page_faults", DWORD),
        ("total_processes", DWORD),
        ("active_processes", DWORD),
        ("terminated_processes", DWORD),
    ]


class _ProcessIdList(C.Structure):
    _fields_ = [("assigned", DWORD), ("listed", DWORD), ("pids", SIZE_T * 16)]


class _FileTime(C.Structure):
    _fields_ = [("low", DWORD), ("high", DWORD)]


class _ProcessEntry(C.Structure):
    _fields_ = [
        ("size", DWORD),
        ("usage", DWORD),
        ("pid", DWORD),
        ("heap", SIZE_T),
        ("module", DWORD),
        ("threads", DWORD),
        ("parent_pid", DWORD),
        ("priority", C.c_int32),
        ("flags", DWORD),
        ("exe_name", C.c_wchar * 260),
    ]


def _abi():
    expected = (
        (_SecurityAttributes, 24),
        (_StartupInfo, 104),
        (_StartupInfoEx, 112),
        (_ProcessInformation, 24),
        (_BasicLimits, 64),
        (_IoCounters, 48),
        (_ExtendedLimits, 144),
        (_Accounting, 48),
        (_ProcessIdList, 136),
        (_FileTime, 8),
        (_ProcessEntry, 568),
    )
    offsets = (
        (_SecurityAttributes.length, 0),
        (_SecurityAttributes.descriptor, 8),
        (_SecurityAttributes.inherit, 16),
        (_StartupInfo.stdin, 80),
        (_StartupInfoEx.attributes, 104),
        (_BasicLimits.affinity, 48),
        (_ExtendedLimits.process_memory, 112),
        (_ProcessIdList.pids, 8),
        (_ProcessEntry.parent_pid, 32),
        (_ProcessEntry.exe_name, 44),
    )
    if (
        os.name != "nt"
        or sys.maxsize != 9223372036854775807
        or C.sizeof(HANDLE) != 8
        or C.sizeof(C.c_wchar) != 2
        or any(C.sizeof(kind) != size for kind, size in expected)
        or any(field.offset != offset for field, offset in offsets)
    ):
        raise RuntimeError("unsupported fixed Windows ABI")


def _api():
    api = C.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
    ptr = C.POINTER
    signatures = {
        "CreateJobObjectW": ([VOID, C.c_wchar_p], HANDLE),
        "SetInformationJobObject": ([HANDLE, C.c_int, VOID, DWORD], BOOL),
        "QueryInformationJobObject": ([HANDLE, C.c_int, VOID, DWORD, ptr(DWORD)], BOOL),
        "CreatePipe": ([ptr(HANDLE), ptr(HANDLE), ptr(_SecurityAttributes), DWORD], BOOL),
        "SetHandleInformation": ([HANDLE, DWORD, DWORD], BOOL),
        "GetHandleInformation": ([HANDLE, ptr(DWORD)], BOOL),
        "CreateFileW": (
            [C.c_wchar_p, DWORD, DWORD, ptr(_SecurityAttributes), DWORD, DWORD, HANDLE],
            HANDLE,
        ),
        "CreateFileMappingW": (
            [HANDLE, ptr(_SecurityAttributes), DWORD, DWORD, DWORD, C.c_wchar_p],
            HANDLE,
        ),
        "MapViewOfFile": ([HANDLE, DWORD, DWORD, DWORD, SIZE_T], VOID),
        "UnmapViewOfFile": ([VOID], BOOL),
        "DuplicateHandle": ([HANDLE, HANDLE, HANDLE, ptr(HANDLE), DWORD, BOOL, DWORD], BOOL),
        "InitializeProcThreadAttributeList": ([VOID, DWORD, DWORD, ptr(SIZE_T)], BOOL),
        "UpdateProcThreadAttribute": ([VOID, DWORD, SIZE_T, VOID, SIZE_T, VOID, VOID], BOOL),
        "DeleteProcThreadAttributeList": ([VOID], None),
        "CreateProcessW": (
            [
                C.c_wchar_p,
                C.c_wchar_p,
                VOID,
                VOID,
                BOOL,
                DWORD,
                VOID,
                C.c_wchar_p,
                ptr(_StartupInfoEx),
                ptr(_ProcessInformation),
            ],
            BOOL,
        ),
        "IsProcessInJob": ([HANDLE, HANDLE, ptr(BOOL)], BOOL),
        "ResumeThread": ([HANDLE], DWORD),
        "WaitForSingleObject": ([HANDLE, DWORD], DWORD),
        "GetExitCodeProcess": ([HANDLE, ptr(DWORD)], BOOL),
        "GetProcessTimes": (
            [HANDLE, ptr(_FileTime), ptr(_FileTime), ptr(_FileTime), ptr(_FileTime)],
            BOOL,
        ),
        "QueryFullProcessImageNameW": ([HANDLE, DWORD, C.c_wchar_p, ptr(DWORD)], BOOL),
        "GetCurrentProcess": ([], HANDLE),
        "GetCurrentProcessId": ([], DWORD),
        "CreateToolhelp32Snapshot": ([DWORD, DWORD], HANDLE),
        "Process32FirstW": ([HANDLE, ptr(_ProcessEntry)], BOOL),
        "Process32NextW": ([HANDLE, ptr(_ProcessEntry)], BOOL),
        "PeekNamedPipe": ([HANDLE, VOID, DWORD, ptr(DWORD), ptr(DWORD), ptr(DWORD)], BOOL),
        "ReadFile": ([HANDLE, VOID, DWORD, ptr(DWORD), VOID], BOOL),
        "TerminateJobObject": ([HANDLE, DWORD], BOOL),
        "TerminateProcess": ([HANDLE, DWORD], BOOL),
        "CloseHandle": ([HANDLE], BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(api, name, None)
        if function is None:
            raise RuntimeError("required fixed Windows API unavailable")
        function.argtypes, function.restype = args, result
    return api


def _check(ok, operation):
    if not ok:
        raise C.WinError(C.get_last_error(), operation)


def _query(api, job, information_class, kind):
    value, written = kind(), DWORD()
    _check(
        api.QueryInformationJobObject(
            job, information_class, C.byref(value), C.sizeof(value), C.byref(written)
        ),
        "QueryInformationJobObject",
    )
    if written.value != C.sizeof(value):
        raise RuntimeError("incomplete job structure")
    return value


def _limits(value):
    return {
        "limit_flags": value.basic.flags,
        "active_process_limit": value.basic.active_processes,
        "process_memory_bytes": value.process_memory,
        "job_memory_bytes": value.job_memory,
        "process_user_time_100ns": value.basic.process_time,
        "job_user_time_100ns": value.basic.job_time,
    }


def _accounting(value):
    result = {
        "total_user_time_100ns": value.user_time,
        "total_kernel_time_100ns": value.kernel_time,
        "total_processes": value.total_processes,
        "active_processes": value.active_processes,
        "terminated_processes": value.terminated_processes,
        "page_faults": value.page_faults,
    }
    if any(type(number) is not int or number < 0 for number in result.values()):
        raise RuntimeError("invalid job accounting")
    return result


def _job_pids(api, job):
    value, written = _ProcessIdList(), DWORD()
    _check(
        api.QueryInformationJobObject(job, 3, C.byref(value), C.sizeof(value), C.byref(written)),
        "QueryInformationJobObject",
    )
    if (
        value.assigned != value.listed
        or value.listed > 16
        or not 8 + 8 * value.listed <= written.value <= C.sizeof(value)
    ):
        raise RuntimeError("incomplete own-job process list")
    result = [value.pids[index] for index in range(value.listed)]
    if any(not 0 < pid <= 0xFFFFFFFF for pid in result) or len(set(result)) != len(result):
        raise RuntimeError("invalid own-job process list")
    return result


def _times(api, process):
    creation, ended, kernel, user = (_FileTime() for _ in range(4))
    _check(
        api.GetProcessTimes(
            process, C.byref(creation), C.byref(ended), C.byref(kernel), C.byref(user)
        ),
        "GetProcessTimes",
    )
    return {
        "creation_filetime": (creation.high << 32) | creation.low,
        "exit_filetime": (ended.high << 32) | ended.low,
        "user_time_100ns": (user.high << 32) | user.low,
        "kernel_time_100ns": (kernel.high << 32) | kernel.low,
    }


def _image(api, process):
    buffer, length = C.create_unicode_buffer(32768), DWORD(32768)
    _check(
        api.QueryFullProcessImageNameW(process, 0, buffer, C.byref(length)),
        "QueryFullProcessImageNameW",
    )
    result = buffer.value
    if not result or len(result.encode("utf-8")) > 32768:
        raise RuntimeError("invalid process image identity")
    return result


def _parent_pid(attempt, child_pid):
    api = attempt.api
    snapshot = api.CreateToolhelp32Snapshot(2, 0)
    if snapshot in (None, INVALID_HANDLE):
        raise C.WinError(C.get_last_error(), "CreateToolhelp32Snapshot")
    attempt.handles["identity_snapshot"] = snapshot
    try:
        entry = _ProcessEntry()
        entry.size = C.sizeof(entry)
        _check(api.Process32FirstW(snapshot, C.byref(entry)), "Process32FirstW")
        for _ in range(4096):
            if entry.pid == child_pid:
                return entry.parent_pid
            if not api.Process32NextW(snapshot, C.byref(entry)):
                if C.get_last_error() != 18:
                    raise C.WinError(C.get_last_error(), "Process32NextW")
                break
        raise RuntimeError("owned creator identity unavailable")
    finally:
        attempt.close("identity_snapshot")
        if "identity_snapshot" in attempt.handles:
            raise RuntimeError("owned identity snapshot cleanup failed")


def _stamp():
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _file_observation(path, maximum):
    if path.is_symlink():
        raise RuntimeError("linked fixed artifact")
    digest, total = hashlib.sha256(), 0
    with path.open("rb") as stream:
        while block := stream.read(65536):
            total += len(block)
            if total > maximum:
                raise RuntimeError("fixed artifact exceeds bound")
            digest.update(block)
    if total == 0:
        raise RuntimeError("empty fixed artifact")
    return total, digest.hexdigest()


def _create_process(api, executable, command, environment, startup, information):
    _check(
        api.CreateProcessW(
            executable,
            command,
            None,
            None,
            True,
            CREATION_FLAGS,
            environment,
            str(_ROOT),
            C.byref(startup),
            C.byref(information),
        ),
        "CreateProcessW",
    )


def _resume_thread(api, thread):
    return api.ResumeThread(thread)


def _duplicate_read_mapping(attempt, mapping_handle):
    reader = HANDLE()
    try:
        _check(
            attempt.api.DuplicateHandle(
                attempt.api.GetCurrentProcess(),
                mapping_handle,
                attempt.api.GetCurrentProcess(),
                C.byref(reader),
                4,
                True,
                0,
            ),
            "DuplicateHandle",
        )
    finally:
        if reader.value not in (None, INVALID_HANDLE):
            attempt.handles["request_read"] = reader.value
    if reader.value in (None, INVALID_HANDLE):
        raise RuntimeError("read mapping handle was not returned")


def _create_pipe(attempt, name, security):
    if name not in {"stdout", "stderr"}:
        raise RuntimeError("unknown fixed channel")
    reader, writer = HANDLE(), HANDLE()
    try:
        _check(
            attempt.api.CreatePipe(C.byref(reader), C.byref(writer), C.byref(security), 65536),
            "CreatePipe",
        )
    finally:
        returned = False
        for role, value in (("read", reader.value), ("write", writer.value)):
            if value not in (None, INVALID_HANDLE):
                attempt.handles[name + "_" + role] = value
                returned = True
        if returned:
            attempt.receipt["channels"][name] = {
                key: None for key in ("retained_bytes", "raw_sha256", "eof", "hash_scope")
            }
    if reader.value in (None, INVALID_HANDLE) or writer.value in (None, INVALID_HANDLE):
        raise RuntimeError("complete fixed channel was not returned")
    attempt.created_channels.add(name)


class _Attempt:
    """One owned attempt. No operation targets a PID without its retained handle."""

    def __init__(self, expected, harmless):
        self.started = time.monotonic_ns()
        self.work_end = self.started + RESOURCE_POLICY["work_ns"]
        self.end = self.work_end + RESOURCE_POLICY["teardown_ns"]
        self.api = None
        self.handles, self.views, self.guards = {}, {}, {}
        self.attributes, self.attributes_initialized = None, False
        self.streams = {"stdout": bytearray(), "stderr": bytearray()}
        self.eof = {"stdout": False, "stderr": False}
        self.created_channels = set()
        self.capped = False
        self.manifest = None
        self.cleanup_propagated = None
        self.receipt = {
            key: None
            for key in (
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
        }
        self.receipt.update(
            schema="native_member_provider_owned_receipt_v1",
            operation="control" if harmless else "decode",
            execution_manifest_sha256=expected,
            started_utc=_stamp(),
            outcome="setup_failed",
        )
        self.receipt["cleanup"] = {
            "completed": None,
            "closed_handles": [],
            "unmapped_views": [],
            "errors": [],
        }

    def error(self, operation, error):
        if self.cleanup_propagated is None and isinstance(
            error, (KeyboardInterrupt, SystemExit, MemoryError, AssertionError)
        ):
            self.cleanup_propagated = error
        kind = type(error).__name__
        if kind not in {
            "OSError",
            "RuntimeError",
            "TimeoutError",
            "MemoryError",
            "AssertionError",
            "KeyboardInterrupt",
            "SystemExit",
            "ValueError",
        }:
            kind = "OSError" if isinstance(error, OSError) else "RuntimeError"
        winerror = getattr(error, "winerror", None)
        if type(winerror) is not int or not 0 <= winerror <= 0xFFFFFFFF:
            winerror = None
        self.receipt["cleanup"]["errors"].append(
            {"operation": operation, "kind": kind, "winerror": winerror}
        )

    def close(self, name):
        if name not in self.handles:
            return
        try:
            _check(self.api.CloseHandle(self.handles[name]), "CloseHandle")
        except BaseException as error:
            self.error("CloseHandle", error)
        else:
            del self.handles[name]
            self.receipt["cleanup"]["closed_handles"].append(name)

    def unmap(self, name):
        if name not in self.views:
            return
        try:
            _check(self.api.UnmapViewOfFile(self.views[name]), "UnmapViewOfFile")
        except BaseException as error:
            self.error("UnmapViewOfFile", error)
        else:
            del self.views[name]
            self.receipt["cleanup"]["unmapped_views"].append(name)

    def guard(self, logical_id, path, maximum, expected=None):
        if path.is_symlink():
            raise RuntimeError("linked fixed artifact")
        handle = self.api.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
        if handle in (None, INVALID_HANDLE):
            raise C.WinError(C.get_last_error(), "CreateFileW")
        self.handles["artifact_" + logical_id] = handle
        actual = _file_observation(path, maximum)
        if expected is not None and actual != expected:
            raise RuntimeError("fixed artifact identity mismatch")
        self.guards[logical_id] = (path, maximum, actual)

    def identities_after(self):
        if self.manifest is not None:
            try:
                observed = _implementation_observations(self.manifest)
                self.receipt["implementation_checks"]["after"] = observed
                for path, maximum, expected in self.guards.values():
                    if _file_observation(path, maximum) != expected:
                        raise RuntimeError("guarded artifact changed")
            except (OSError, ValueError, RuntimeError) as error:
                self.receipt["outcome"] = "identity_failed"
                raise RuntimeError("implementation identity uncertainty") from error

    def budget(self):
        if time.monotonic_ns() >= self.work_end:
            raise TimeoutError("registered work budget exhausted")

    def terminate(self, reason):
        if self.receipt["termination"] is not None or "process" not in self.handles:
            return
        record = {
            "requested": True,
            "reason": reason,
            "job_attempted": False,
            "job_winerror": None,
            "process_fallback_attempted": False,
            "process_winerror": None,
        }
        self.receipt["termination"] = record
        succeeded = False
        if "job" in self.handles:
            record["job_attempted"] = True
            succeeded = bool(self.api.TerminateJobObject(self.handles["job"], TERMINATION_CODE))
            if not succeeded:
                record["job_winerror"] = C.get_last_error()
        in_job = (
            self.receipt["child"] is not None
            and self.receipt["child"]["in_job_before_resume"] is True
        )
        if not succeeded or not in_job:
            state = self.api.WaitForSingleObject(self.handles["process"], 0)
            if state == WAIT_TIMEOUT:
                record["process_fallback_attempted"] = True
                if not self.api.TerminateProcess(self.handles["process"], TERMINATION_CODE):
                    record["process_winerror"] = C.get_last_error()
            elif state != 0:
                self.error("WaitForSingleObject", C.WinError(C.get_last_error()))

    def drain(self):
        """One fair, nonblocking quantum from each separately owned pipe."""
        for name in ("stdout", "stderr"):
            if self.eof[name] or name + "_read" not in self.handles:
                continue
            available = DWORD()
            if not self.api.PeekNamedPipe(
                self.handles[name + "_read"], None, 0, None, C.byref(available), None
            ):
                error = C.get_last_error()
                if error == 109:
                    self.eof[name] = True
                    continue
                raise C.WinError(error, "PeekNamedPipe")
            total = sum(len(value) for value in self.streams.values())
            remaining = 4194304 - total
            if name == "stderr":
                remaining = min(remaining, 65536 - len(self.streams[name]))
            if available.value > remaining:
                self.capped = True
                self.receipt["outcome"] = "transport_failed"
                self.terminate("output_limit")
                continue
            if available.value:
                requested = min(available.value, 65536, remaining)
                buffer, count = C.create_string_buffer(requested), DWORD()
                _check(
                    self.api.ReadFile(
                        self.handles[name + "_read"], buffer, requested, C.byref(count), None
                    ),
                    "ReadFile",
                )
                if not 0 < count.value <= requested:
                    raise RuntimeError("invalid pipe read count")
                self.streams[name].extend(buffer.raw[: count.value])

    def observe_exit(self):
        if "process" not in self.handles:
            return False
        state = self.api.WaitForSingleObject(self.handles["process"], 0)
        if state == WAIT_TIMEOUT:
            return False
        if state != 0:
            raise C.WinError(C.get_last_error(), "WaitForSingleObject")
        code = DWORD()
        _check(
            self.api.GetExitCodeProcess(self.handles["process"], C.byref(code)),
            "GetExitCodeProcess",
        )
        times = _times(self.api, self.handles["process"])
        previous_creation = self.receipt["child"]["creation_filetime"]
        if (
            (previous_creation is not None and times["creation_filetime"] != previous_creation)
            or times["creation_filetime"] <= 0
            or times["exit_filetime"] < times["creation_filetime"]
        ):
            raise RuntimeError("retained exit identity mismatch")
        if previous_creation is None:
            self.receipt["child"]["creation_filetime"] = times["creation_filetime"]
        self.receipt["exit"].update(observed=True, code=code.value, **times)
        return True

    def monitor(self):
        while True:
            if time.monotonic_ns() >= self.work_end:
                self.receipt["outcome"] = "timeout"
                self.terminate("deadline")
                return
            self.drain()
            if self.observe_exit() and (all(self.eof.values()) or self.capped):
                return
            if self.capped:
                return
            time.sleep(0.005)

    def cleanup(self):
        """Always attempt every exact-owned teardown; retain every uncertainty."""
        if self.api is not None:
            if "process" in self.handles:
                try:
                    if not self.observe_exit():
                        self.terminate("host_exception")
                    while time.monotonic_ns() < self.end:
                        self.drain()
                        if self.observe_exit() and (all(self.eof.values()) or self.capped):
                            break
                        time.sleep(0.005)
                    if self.receipt["exit"]["observed"] is not True:
                        raise RuntimeError("owned exit not established")
                except BaseException as error:
                    self.error("WaitForSingleObject", error)
                    # Even a failed identity/query observation must not prevent
                    # an exact-owned termination attempt or a bounded exit wait.
                    try:
                        self.terminate("cleanup_failure")
                        remaining = max(0, min(3000, (self.end - time.monotonic_ns()) // 1000000))
                        if self.api.WaitForSingleObject(self.handles["process"], remaining) != 0:
                            raise RuntimeError("owned teardown exit remains uncertain")
                        self.observe_exit()
                    except BaseException as cleanup_error:
                        self.error("WaitForSingleObject", cleanup_error)
            if "job" in self.handles:
                try:
                    while True:
                        pids = _job_pids(self.api, self.handles["job"])
                        accounting = _accounting(
                            _query(self.api, self.handles["job"], 1, _Accounting)
                        )
                        self.receipt["job"]["pids_final"] = pids
                        self.receipt["job"]["accounting_final"] = accounting
                        if not pids and accounting["active_processes"] == 0:
                            break
                        if time.monotonic_ns() >= self.end:
                            raise RuntimeError("own job final membership is not empty")
                        time.sleep(0.005)
                    final = _limits(_query(self.api, self.handles["job"], 9, _ExtendedLimits))
                    self.receipt["limits"]["queried_final"] = final
                    if (
                        self.receipt["limits"]["configured"] is not None
                        and final != self.receipt["limits"]["configured"]
                    ):
                        raise RuntimeError("final own-job limits changed")
                except BaseException as error:
                    self.error("QueryInformationJobObject", error)
            for name in list(self.views):
                self.unmap(name)
            if self.attributes_initialized:
                try:
                    self.api.DeleteProcThreadAttributeList(self.attributes)
                except BaseException as error:
                    self.error("DeleteProcThreadAttributeList", error)
                else:
                    self.attributes_initialized = False
            # Exact identity rechecks happen while all guard handles are held.
            try:
                self.identities_after()
            except BaseException as error:
                self.error("identity_check", error)
            for name in list(self.handles):
                if name != "job":
                    self.close(name)
            self.close("job")
        if self.receipt["channels"] is not None:
            for name in self.created_channels:
                raw = self.streams[name]
                self.receipt["channels"][name] = {
                    "retained_bytes": len(raw),
                    "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    "eof": self.eof[name],
                    "hash_scope": "complete" if self.eof[name] else "retained_prefix",
                }
        complete = not (
            self.handles
            or self.views
            or self.attributes_initialized
            or self.receipt["cleanup"]["errors"]
        )
        self.receipt["cleanup"]["completed"] = complete
        if not complete:
            self.receipt["outcome"] = "cleanup_failed"


def _prepare(attempt, request_template, expected, registration):
    receipt = attempt.receipt
    try:
        manifest = _execution_manifest(expected)
    except (OSError, ValueError, RuntimeError) as error:
        receipt["outcome"] = "identity_failed"
        raise RuntimeError("execution registration unavailable or changed") from error
    _abi()
    attempt.api = api = _api()
    receipt["implementation_checks"] = {"before": None, "after": None}
    attempt.manifest = manifest
    try:
        for row in manifest["artifacts"]:
            attempt.guard(
                row["logical_id"],
                Path(__file__).with_name(row["relative_path"]),
                4194304,
                (row["raw_bytes"], row["raw_sha256"]),
            )
        attempt.guard(
            "execution", Path(__file__).with_name("_native_member_execution_v1.json"), 65536
        )
        if attempt.guards["execution"][2][1] != expected:
            raise RuntimeError("guarded execution registration changed")
        attempt.guard(
            "bootstrap", Path(__file__).with_name("six_e_native_member_decode_evidence.py"), 4194304
        )
        # The interpreter is a separate native-manifest guard, not a seventh
        # production implementation observation or complete import-graph proof.
        attempt.guard("python.exe", _PYTHON, 67108864)
        if attempt.guards["python.exe"][2][1] != _PYTHON_SHA:
            raise RuntimeError("fixed interpreter identity mismatch")
        if registration is not None:
            row = registration["worker"]
            attempt.guard(
                "harmless_worker",
                _ROOT / row["relative_path"],
                1048576,
                (row["raw_bytes"], row["raw_sha256"]),
            )
        receipt["implementation_checks"]["before"] = _implementation_observations(manifest)
    except (OSError, ValueError, RuntimeError) as error:
        receipt["outcome"] = "identity_failed"
        raise RuntimeError("fixed implementation identity uncertainty") from error
    request, request_raw, mapping = _request_bytes(request_template, expected)
    receipt["attempt_token"] = request["attempt_token"]
    receipt["request"] = {
        "canonical_bytes": len(request_raw),
        "canonical_sha256": hashlib.sha256(request_raw).hexdigest(),
        "member_bytes": len(bytes.fromhex(request["member_hex"])),
        "member_sha256": request["expected_member_sha256"],
    }
    receipt["parent"] = {"pid": os.getpid(), "creation_filetime": None, "image": None}
    receipt["parent"]["creation_filetime"] = _times(api, api.GetCurrentProcess())[
        "creation_filetime"
    ]
    receipt["parent"]["image"] = _image(api, api.GetCurrentProcess())
    if api.GetCurrentProcessId() != receipt["parent"]["pid"]:
        raise RuntimeError("parent identity mismatch")
    attempt.budget()
    return request, mapping


def _create(attempt, request, mapping, registration):
    api, receipt, handles = attempt.api, attempt.receipt, attempt.handles
    receipt["limits"] = {"configured": None, "queried_before_resume": None, "queried_final": None}
    receipt["job"] = {
        key: None
        for key in (
            "pids_initial",
            "pids_before_resume",
            "pids_final",
            "accounting_initial",
            "accounting_before_resume",
            "accounting_final",
        )
    }
    job = api.CreateJobObjectW(None, None)
    if not job:
        raise C.WinError(C.get_last_error(), "CreateJobObjectW")
    handles["job"] = job
    limits = _ExtendedLimits()
    limits.basic.flags, limits.basic.active_processes = 8974, 1
    limits.basic.process_time = limits.basic.job_time = 50000000
    limits.process_memory = limits.job_memory = 268435456
    _check(
        api.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)),
        "SetInformationJobObject",
    )
    receipt["limits"]["configured"] = _limits(limits)
    if _limits(_query(api, job, 9, _ExtendedLimits)) != receipt["limits"]["configured"]:
        raise RuntimeError("fresh job limit mismatch")
    if _query(api, job, 6, DWORD).value != 0:
        raise RuntimeError("job CPU policy does not terminate")
    receipt["job"]["pids_initial"] = _job_pids(api, job)
    receipt["job"]["accounting_initial"] = _accounting(_query(api, job, 1, _Accounting))
    if (
        receipt["job"]["pids_initial"]
        or receipt["job"]["accounting_initial"]["total_processes"] != 0
    ):
        raise RuntimeError("fresh job is not empty")
    receipt["mapping"] = {
        key: None
        for key in (
            "bytes",
            "inherited_access",
            "writable_parent_view_unmapped",
            "write_capable_parent_handle_closed",
            "explicit_inherited_handle_count",
        )
    }
    mapping_handle = api.CreateFileMappingW(INVALID_HANDLE, None, 4, 0, MAPPING_BYTES, None)
    if not mapping_handle:
        raise C.WinError(C.get_last_error(), "CreateFileMappingW")
    handles["request_write"] = mapping_handle
    view = api.MapViewOfFile(mapping_handle, 2, 0, 0, MAPPING_BYTES)
    if not view:
        raise C.WinError(C.get_last_error(), "MapViewOfFile")
    attempt.views["parent_write"] = view
    C.memmove(view, mapping, MAPPING_BYTES)
    _duplicate_read_mapping(attempt, mapping_handle)
    receipt["mapping"].update(bytes=MAPPING_BYTES, inherited_access="FILE_MAP_READ")
    attempt.unmap("parent_write")
    receipt["mapping"]["writable_parent_view_unmapped"] = "parent_write" not in attempt.views
    attempt.close("request_write")
    receipt["mapping"]["write_capable_parent_handle_closed"] = "request_write" not in handles
    if attempt.views or receipt["cleanup"]["errors"]:
        raise RuntimeError("writable mapping cleanup failed before creation")
    security = _SecurityAttributes(C.sizeof(_SecurityAttributes), None, True)
    receipt["channels"] = {"stdout": None, "stderr": None}
    for name in ("stdout", "stderr"):
        _create_pipe(attempt, name, security)
        _check(api.SetHandleInformation(handles[name + "_read"], 1, 0), "SetHandleInformation")
    nul = api.CreateFileW("NUL", 0x80000000, 3, C.byref(security), 3, 0, None)
    if nul in (None, INVALID_HANDLE):
        raise C.WinError(C.get_last_error(), "CreateFileW")
    handles["nul"] = nul
    for name in (
        "request_read",
        "stdout_write",
        "stderr_write",
        "nul",
        "stdout_read",
        "stderr_read",
    ):
        flags = DWORD()
        _check(api.GetHandleInformation(handles[name], C.byref(flags)), "GetHandleInformation")
        expected_flags = 0 if name in {"stdout_read", "stderr_read"} else 1
        if flags.value != expected_flags:
            raise RuntimeError("explicit handle inheritance mismatch")
    attribute_size = SIZE_T()
    C.set_last_error(0)
    ok = api.InitializeProcThreadAttributeList(None, 2, 0, C.byref(attribute_size))
    if ok or C.get_last_error() != 122 or not 0 < attribute_size.value <= 65536:
        raise RuntimeError("invalid process attribute sizing")
    attempt.attributes = C.create_string_buffer(attribute_size.value)
    if C.addressof(attempt.attributes) % 8:
        raise RuntimeError("unaligned process attributes")
    _check(
        api.InitializeProcThreadAttributeList(attempt.attributes, 2, 0, C.byref(attribute_size)),
        "InitializeProcThreadAttributeList",
    )
    attempt.attributes_initialized = True
    jobs = (HANDLE * 1)(job)
    inherited = (HANDLE * 4)(
        handles["request_read"], handles["stdout_write"], handles["stderr_write"], nul
    )
    _check(
        api.UpdateProcThreadAttribute(
            attempt.attributes, 0, 0x2000D, jobs, C.sizeof(jobs), None, None
        ),
        "UpdateProcThreadAttribute",
    )
    _check(
        api.UpdateProcThreadAttribute(
            attempt.attributes, 0, 0x20002, inherited, C.sizeof(inherited), None, None
        ),
        "UpdateProcThreadAttribute",
    )
    receipt["mapping"]["explicit_inherited_handle_count"] = 4
    startup, information = _StartupInfoEx(), _ProcessInformation()
    startup.startup.cb, startup.startup.flags = C.sizeof(startup), 0x100
    startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = (
        nul,
        handles["stdout_write"],
        handles["stderr_write"],
    )
    startup.attributes = C.cast(attempt.attributes, VOID)
    worker = (
        Path(__file__).with_name("_native_member_worker.py")
        if registration is None
        else _ROOT / registration["worker"]["relative_path"]
    )
    argv = [
        str(_PYTHON),
        "-I",
        "-S",
        "-B",
        str(worker),
        "--mapping-handle",
        str(handles["request_read"]),
        "--mapping-size",
        "1048576",
    ]
    if registration is not None:
        argv += ["--control", registration["control_id"]]
    system_root = os.environ.get("SystemRoot")
    if (
        type(system_root) is not str
        or not system_root
        or "\0" in system_root
        or not os.path.isabs(system_root)
        or len(system_root.encode("utf-8")) > 32768
    ):
        raise RuntimeError("fixed SystemRoot environment unavailable")
    receipt["command"] = {
        "executable": str(_PYTHON),
        "argv": argv,
        "cwd": str(_ROOT),
        "environment": {"SystemRoot": system_root},
    }
    command = C.create_unicode_buffer(subprocess.list2cmdline(argv))
    environment = C.create_unicode_buffer("SystemRoot=" + system_root + "\0\0")
    receipt["exit"] = {
        "created": None,
        "resumed": None,
        "observed": None,
        "code": None,
        "creation_filetime": None,
        "exit_filetime": None,
        "user_time_100ns": None,
        "kernel_time_100ns": None,
    }
    attempt.budget()
    try:
        _create_process(api, str(_PYTHON), command, environment, startup, information)
    except BaseException:
        # A Python cancellation can arrive immediately after the native call.
        # Capture any actually returned handles before propagating to teardown.
        if information.thread:
            handles["thread"] = information.thread
        if information.process:
            handles["process"] = information.process
            receipt["exit"]["created"] = True
            receipt["child"] = {
                "pid": information.pid,
                "tid": information.tid,
                "parent_pid": None,
                "creation_filetime": None,
                "image": None,
                "in_job_before_resume": None,
                "resume_previous_count": None,
            }
        else:
            receipt["exit"]["created"] = False
        raise
    handles["process"], handles["thread"] = information.process, information.thread
    receipt["exit"]["created"] = True
    receipt["child"] = {
        "pid": information.pid,
        "tid": information.tid,
        "parent_pid": None,
        "creation_filetime": None,
        "image": None,
        "in_job_before_resume": None,
        "resume_previous_count": None,
    }
    for name in ("request_read", "stdout_write", "stderr_write", "nul"):
        attempt.close(name)
    child = receipt["child"]
    child["creation_filetime"] = _times(api, handles["process"])["creation_filetime"]
    child["image"] = _image(api, handles["process"])
    child["parent_pid"] = _parent_pid(attempt, information.pid)
    if (
        os.path.normcase(child["image"]) != os.path.normcase(str(_PYTHON))
        or child["parent_pid"] != receipt["parent"]["pid"]
        or child["creation_filetime"] <= 0
    ):
        receipt["outcome"] = "identity_failed"
        raise RuntimeError("owned child identity mismatch")
    in_job = BOOL()
    _check(api.IsProcessInJob(handles["process"], job, C.byref(in_job)), "IsProcessInJob")
    child["in_job_before_resume"] = bool(in_job.value)
    receipt["limits"]["queried_before_resume"] = _limits(_query(api, job, 9, _ExtendedLimits))
    receipt["job"]["pids_before_resume"] = _job_pids(api, job)
    receipt["job"]["accounting_before_resume"] = _accounting(_query(api, job, 1, _Accounting))
    if (
        not child["in_job_before_resume"]
        or receipt["job"]["pids_before_resume"] != [information.pid]
        or receipt["job"]["accounting_before_resume"]["active_processes"] != 1
        or receipt["limits"]["queried_before_resume"] != receipt["limits"]["configured"]
        or receipt["cleanup"]["errors"]
    ):
        raise RuntimeError("owned pre-resume containment mismatch")
    attempt.budget()
    previous = _resume_thread(api, handles["thread"])
    child["resume_previous_count"] = previous
    receipt["exit"]["resumed"] = previous == 1
    if previous != 1:
        raise RuntimeError("unexpected primary thread suspension count")


def _interpret(attempt, request, registration):
    receipt = attempt.receipt
    if receipt["outcome"] in {
        "setup_failed",
        "timeout",
        "transport_failed",
        "cleanup_failed",
        "identity_failed",
    }:
        return None
    if not all(attempt.eof.values()) or attempt.streams["stderr"]:
        receipt["outcome"] = "transport_failed"
        return None
    code = receipt["exit"]["code"]
    if code in {70, 71, 72}:
        receipt["outcome"] = {70: "identity_failed", 71: "resource_failed", 72: "transport_failed"}[
            code
        ]
        return None
    receipt["response"] = {
        "parsed_body": None,
        "canonical_bytes": None,
        "canonical_sha256": None,
        "binding_validated": None,
        "evidence_validated": None,
    }
    try:
        body = _response_body(
            bytes(attempt.streams["stdout"]),
            request,
            receipt["request"]["canonical_sha256"],
            harmless=registration is not None,
        )
        if registration is not None and body["status"] == "complete":
            _require(body["evidence"]["control_id"] == registration["control_id"])
        raw = _types.canonical_bytes(body)
        receipt["response"].update(
            parsed_body=body,
            canonical_bytes=len(raw),
            canonical_sha256=hashlib.sha256(raw).hexdigest(),
            binding_validated=True,
            evidence_validated=True,
        )
    except ValueError:
        receipt["outcome"] = "worker_failed" if code not in {0, 2} else "transport_failed"
        return None
    if code not in {0, 2}:
        receipt["outcome"] = "worker_failed"
        return None
    if (code == 0 and body["status"] != "complete") or (code == 2 and body["status"] != "refused"):
        receipt["outcome"] = "transport_failed"
        return None
    receipt["outcome"] = "complete" if code == 0 else "input_refused"
    return body


def _execute(request_body, expected_execution_sha256, registration=None):
    attempt = _Attempt(expected_execution_sha256, registration is not None)
    request, response, propagated = None, None, None
    try:
        request, mapping = _prepare(attempt, request_body, expected_execution_sha256, registration)
        _create(attempt, request, mapping, registration)
        # Pending interpretation is explicitly distinct from failed setup.
        attempt.receipt["outcome"] = "worker_failed"
        attempt.monitor()
    except (KeyboardInterrupt, SystemExit, MemoryError, AssertionError) as error:
        propagated = error
        attempt.receipt["outcome"] = (
            "resource_failed"
            if isinstance(error, MemoryError)
            else "cancelled"
            if isinstance(error, (KeyboardInterrupt, SystemExit))
            else "worker_failed"
        )
        try:
            attempt.terminate(
                "memory_error"
                if isinstance(error, MemoryError)
                else "cancellation"
                if isinstance(error, (KeyboardInterrupt, SystemExit))
                else "host_exception"
            )
        except BaseException as cleanup_error:
            attempt.error("TerminateJobObject", cleanup_error)
    except TimeoutError:
        attempt.receipt["outcome"] = "timeout"
        try:
            attempt.terminate("deadline")
        except BaseException as error:
            attempt.error("TerminateJobObject", error)
    except (OSError, RuntimeError, ValueError):
        if attempt.receipt["outcome"] not in {"identity_failed", "transport_failed"}:
            exited = attempt.receipt["exit"]
            attempt.receipt["outcome"] = (
                "transport_failed"
                if exited is not None and exited["resumed"] is True
                else "setup_failed"
            )
        try:
            attempt.terminate(
                "identity_error"
                if attempt.receipt["outcome"] == "identity_failed"
                else "host_exception"
            )
        except BaseException as error:
            attempt.error("TerminateJobObject", error)
    except BaseException as error:
        # An unexpected host bug is not an ordinary input refusal. Preserve it
        # after the same exact-owned cleanup, including uncaught sentinels.
        propagated = error
        attempt.receipt["outcome"] = "worker_failed"
        try:
            attempt.terminate("host_exception")
        except BaseException as cleanup_error:
            attempt.error("TerminateJobObject", cleanup_error)
    finally:
        try:
            attempt.cleanup()
        except BaseException as error:
            attempt.error("host", error)
            attempt.receipt["cleanup"]["completed"] = False
            attempt.receipt["outcome"] = "cleanup_failed"
            if propagated is None:
                propagated = error
    if propagated is None:
        propagated = attempt.cleanup_propagated
    # Successful cleanup is a prerequisite, never something claimed by a child.
    try:
        if (
            propagated is None
            and request is not None
            and attempt.receipt["exit"] is not None
            and attempt.receipt["exit"]["observed"] is True
        ):
            response = _interpret(attempt, request, registration)
    except BaseException as error:
        propagated = error
        attempt.receipt["outcome"] = (
            "resource_failed"
            if isinstance(error, MemoryError)
            else "cancelled"
            if isinstance(error, (KeyboardInterrupt, SystemExit))
            else "transport_failed"
        )
    attempt.receipt["finished_utc"] = _stamp()
    attempt.receipt["elapsed_ns"] = time.monotonic_ns() - attempt.started
    if propagated is not None:
        propagated.receipt = attempt.receipt
        raise propagated
    if registration is not None:
        return response if attempt.receipt["outcome"] in {
            "complete",
            "input_refused",
        } else None, attempt.receipt
    if attempt.receipt["outcome"] == "complete":
        return response, attempt.receipt
    kind = {
        "input_refused": ValueError,
        "resource_failed": MemoryError,
        "timeout": TimeoutError,
    }.get(attempt.receipt["outcome"], RuntimeError)
    error = kind("native-member owned execution did not complete")
    error.receipt = attempt.receipt
    raise error


def run_decode(request_body, expected_execution_sha256):
    """Run only the fixed registered production worker; failure carries receipt."""
    _validate_request(request_body, expected_execution_sha256, template=True)
    return _execute(request_body, expected_execution_sha256)


def _run_harmless(
    request_template, registration, *, expected_registration_sha256, expected_execution_sha256
):
    """Internal qualification only; never selected by the five public APIs."""
    _validate_request(request_template, expected_execution_sha256, template=True)
    _control_registration(
        request_template, registration, expected_registration_sha256, expected_execution_sha256
    )
    return _execute(request_template, expected_execution_sha256, registration)
