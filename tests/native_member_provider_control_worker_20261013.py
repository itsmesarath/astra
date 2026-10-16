"""Fixed harmless provider controls; root launches only under the registered host.

No production imports, native codecs, variable commands or persistent writes.
Independent Win32 declarations follow the exact dated harmless registration.
"""

import ctypes
import hashlib
import json
import sys
import time

MAPPING_BYTES = 1048576
FIXED_PYTHON = "C:/Users/pabta/AppData/Local/Programs/Python/Python312/python.exe"
CONTROL_IDS = (
    "mapping_roundtrip",
    "ordinary_refusal",
    "never_read",
    "respond_then_wait",
    "stdout_excess",
    "stderr_excess",
    "stderr_nonempty",
    "truncated_response",
    "trailing_response",
    "duplicate_response",
    "wrong_token",
    "wrong_request_hash",
    "wrong_manifest_hash",
    "valid_then_exit_73",
    "memory_error_71",
    "memory_pressure",
    "grandchild_denied",
)
REQUEST_KEYS = {
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


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _no_codecs():
    return not any(
        name == "databento_dbn"
        or name.startswith("databento_dbn.")
        or name == "zstandard"
        or name.startswith("zstandard.")
        for name in sys.modules
    )


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate request key")
        result[key] = value
    return result


def _strict_json(raw, maximum=1048564, maximum_nodes=128):
    """Independent lexical bounds before allocating any decoded JSON tree."""
    if type(raw) is not bytes or not 0 < len(raw) <= maximum:
        raise ValueError("JSON byte bounds")
    text = raw.decode("utf-8", "strict")
    if text.startswith("\ufeff"):
        raise ValueError("JSON BOM")
    index = depth = nodes = 0
    while index < len(text):
        char = text[index]
        if char in " \t\r\n,:":
            index += 1
            continue
        if char in "{[":
            depth += 1
            nodes += 1
            index += 1
            if depth > 64:
                raise ValueError("JSON depth bounds")
        elif char in "}]":
            depth -= 1
            index += 1
            if depth < 0:
                raise ValueError("JSON nesting")
        else:
            nodes += 1
            if depth + 1 > 64:
                raise ValueError("JSON scalar depth bounds")
            if char == '"':
                index += 1
                while True:
                    if index >= len(text):
                        raise ValueError("JSON unterminated string")
                    char = text[index]
                    index += 1
                    if char == '"':
                        break
                    if ord(char) < 32:
                        raise ValueError("JSON string control")
                    if char == "\\":
                        if index >= len(text):
                            raise ValueError("JSON missing escape")
                        escaped = text[index]
                        index += 1
                        if escaped == "u":
                            digits = text[index : index + 4]
                            if len(digits) != 4 or any(
                                item not in "0123456789abcdefABCDEF" for item in digits
                            ):
                                raise ValueError("JSON Unicode escape")
                            index += 4
                        elif escaped not in '"\\/bfnrt':
                            raise ValueError("JSON escape")
            elif char == "-" or char in "0123456789":
                if char == "-":
                    index += 1
                first = index
                while index < len(text) and text[index] in "0123456789":
                    index += 1
                count = index - first
                if not 1 <= count <= 20 or (count > 1 and text[first] == "0"):
                    raise ValueError("JSON integer representation")
            else:
                for literal in ("true", "false", "null"):
                    if text.startswith(literal, index):
                        index += len(literal)
                        break
                else:
                    raise ValueError("JSON unsupported token")
        if nodes > maximum_nodes:
            raise ValueError("JSON node bounds")
    if depth:
        raise ValueError("JSON incomplete nesting")
    body = json.loads(text, object_pairs_hook=_unique_pairs)
    if _canonical(body) != raw:
        raise ValueError("JSON is not canonical")
    return body


def _parse_request(raw):
    if len(raw) != MAPPING_BYTES or raw[:8] != b"NMREQ001":
        raise ValueError("invalid fixed mapping")
    size = int.from_bytes(raw[8:12], "little")
    if not 1 <= size <= MAPPING_BYTES - 12 or any(raw[12 + size :]):
        raise ValueError("invalid complete mapping length/padding")
    encoded = raw[12 : 12 + size]
    request = _strict_json(encoded)
    if type(request) is not dict or set(request) != REQUEST_KEYS or _canonical(request) != encoded:
        raise ValueError("invalid complete request body")
    if request["schema"] != "native_member_worker_request_v1" or request["operation"] != "decode":
        raise ValueError("invalid fixed request operation")
    return request, encoded


def _kernel():
    if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError("registered Windows AMD64 required")
    kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
    handle = ctypes.c_void_p
    dword = ctypes.c_uint32
    kernel.MapViewOfFile.argtypes = [handle, dword, dword, dword, ctypes.c_size_t]
    kernel.MapViewOfFile.restype = handle
    kernel.UnmapViewOfFile.argtypes = [handle]
    kernel.UnmapViewOfFile.restype = ctypes.c_int32
    kernel.GetHandleInformation.argtypes = [handle, ctypes.POINTER(dword)]
    kernel.GetHandleInformation.restype = ctypes.c_int32
    kernel.CloseHandle.argtypes = [handle]
    kernel.CloseHandle.restype = ctypes.c_int32
    return kernel


def _request_from_mapping(handle, exercise):
    kernel = _kernel()
    read_view = kernel.MapViewOfFile(handle, 4, 0, 0, MAPPING_BYTES)
    if not read_view:
        raise ctypes.WinError(ctypes.get_last_error())
    copy_view = None
    try:
        raw = ctypes.string_at(read_view, MAPPING_BYTES)
        request, encoded = _parse_request(raw)
        result = None
        if exercise:
            flags = ctypes.c_uint32()
            if not kernel.GetHandleInformation(handle, ctypes.byref(flags)):
                raise ctypes.WinError(ctypes.get_last_error())
            ctypes.set_last_error(0)
            shared_write = kernel.MapViewOfFile(handle, 2, 0, 0, MAPPING_BYTES)
            shared_error = ctypes.get_last_error()
            if shared_write:
                kernel.UnmapViewOfFile(shared_write)
                raise AssertionError("shared WRITE view unexpectedly permitted")
            if shared_error != 5:
                raise AssertionError("shared WRITE failed for an unregistered reason")
            copy_view = kernel.MapViewOfFile(handle, 1, 0, 0, MAPPING_BYTES)
            if not copy_view:
                raise ctypes.WinError(ctypes.get_last_error())
            private_byte = ctypes.c_ubyte.from_address(copy_view + MAPPING_BYTES - 1)
            before = private_byte.value
            private_byte.value = 165
            after = private_byte.value
            shared_after = ctypes.c_ubyte.from_address(read_view + MAPPING_BYTES - 1).value
            shared_after_sha = _sha(ctypes.string_at(read_view, MAPPING_BYTES))
            if not kernel.UnmapViewOfFile(copy_view):
                raise ctypes.WinError(ctypes.get_last_error())
            copy_view = None
            result = {
                "mapping_bytes": MAPPING_BYTES,
                "inherited_handle_flags": flags.value,
                "read_access": "FILE_MAP_READ",
                "shared_write_denied": True,
                "shared_write_winerror": shared_error,
                "copy_view_created": True,
                "copy_offset": MAPPING_BYTES - 1,
                "copy_before": before,
                "copy_after": after,
                "shared_after": shared_after,
                "shared_after_sha256": shared_after_sha,
                "copy_view_unmapped": True,
                "read_view_unmapped": True,
                "mapping_handle_closed": True,
                "native_codec_imported": not _no_codecs(),
            }
    finally:
        if copy_view and not kernel.UnmapViewOfFile(copy_view):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.UnmapViewOfFile(read_view):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())
    return request, encoded, _sha(raw), result


class _StartupInfo(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("reserved", ctypes.c_wchar_p),
        ("desktop", ctypes.c_wchar_p),
        ("title", ctypes.c_wchar_p),
        ("x", ctypes.c_uint32),
        ("y", ctypes.c_uint32),
        ("xsize", ctypes.c_uint32),
        ("ysize", ctypes.c_uint32),
        ("xchars", ctypes.c_uint32),
        ("ychars", ctypes.c_uint32),
        ("fill", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("show", ctypes.c_uint16),
        ("reserved_count", ctypes.c_uint16),
        ("reserved_bytes", ctypes.c_void_p),
        ("stdin", ctypes.c_void_p),
        ("stdout", ctypes.c_void_p),
        ("stderr", ctypes.c_void_p),
    ]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("process", ctypes.c_void_p),
        ("thread", ctypes.c_void_p),
        ("pid", ctypes.c_uint32),
        ("tid", ctypes.c_uint32),
    ]


def _grandchild_denied():
    if sys.executable.replace("\\", "/").casefold() != FIXED_PYTHON.casefold():
        raise RuntimeError("unregistered interpreter")
    if ctypes.sizeof(_StartupInfo) != 104 or ctypes.sizeof(_ProcessInfo) != 24:
        raise RuntimeError("unregistered process ABI")
    kernel = _kernel()
    kernel.CreateProcessW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.POINTER(_StartupInfo),
        ctypes.POINTER(_ProcessInfo),
    ]
    kernel.CreateProcessW.restype = ctypes.c_int32
    kernel.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.TerminateProcess.restype = ctypes.c_int32
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.WaitForSingleObject.restype = ctypes.c_uint32
    startup = _StartupInfo()
    startup.cb = ctypes.sizeof(startup)
    process = _ProcessInfo()
    command = ctypes.create_unicode_buffer(f'"{FIXED_PYTHON}" -I -S -B -c pass')
    ctypes.set_last_error(0)
    created = kernel.CreateProcessW(
        FIXED_PYTHON,
        command,
        None,
        None,
        False,
        0x08000004,
        None,
        None,
        ctypes.byref(startup),
        ctypes.byref(process),
    )
    error = ctypes.get_last_error()
    if created:
        try:
            if not kernel.TerminateProcess(process.process, 74):
                raise ctypes.WinError(ctypes.get_last_error())
            if kernel.WaitForSingleObject(process.process, 3000) != 0:
                raise RuntimeError("unexpected grandchild did not terminate")
        finally:
            if process.thread:
                kernel.CloseHandle(process.thread)
            if process.process:
                kernel.CloseHandle(process.process)
        raise AssertionError("grandchild unexpectedly created; never resumed")
    if error not in (5, 1816):
        raise AssertionError("grandchild denial not a qualifying job-policy observation")
    returned_process = bool(process.process)
    returned_thread = bool(process.thread)
    if returned_process or returned_thread:
        if returned_thread:
            kernel.CloseHandle(process.thread)
        if returned_process:
            kernel.CloseHandle(process.process)
        raise AssertionError("failed creation returned unexpected handles")
    return {
        "executable": FIXED_PYTHON,
        "argv": [FIXED_PYTHON, "-I", "-S", "-B", "-c", "pass"],
        "creation_attempted": True,
        "create_returned": False,
        "winerror": error,
        "returned_process_handle": returned_process,
        "returned_thread_handle": returned_thread,
        "resumed": False,
        "native_codec_imported": not _no_codecs(),
    }


def _memory_pressure():
    try:
        allocation = bytearray(536870912)
    except MemoryError:
        return {
            "attempted_bytes": 536870912,
            "attempted": True,
            "memory_error_caught": True,
            "allocation_returned": False,
            "allocation_length": None,
            "retained_allocation_object": False,
            "native_codec_imported": not _no_codecs(),
        }
    del allocation
    raise SystemExit(74)


def _write_bytes(stream, value):
    for start in range(0, len(value), 65536):
        stream.write(value[start : start + 65536])
        stream.flush()


def _flip(value):
    return ("1" if value[0] == "0" else "0") + value[1:]


def main():
    if len(sys.argv) != 7 or sys.argv[1] != "--mapping-handle" or sys.argv[3] != "--mapping-size":
        return 72
    if sys.argv[5] != "--control" or sys.argv[6] not in CONTROL_IDS:
        return 72
    if not sys.argv[2].isascii() or not sys.argv[2].isdigit() or sys.argv[4] != "1048576":
        return 72
    handle = int(sys.argv[2])
    if not 0 < handle < 1 << 64 or not _no_codecs():
        return 72
    control = sys.argv[6]
    if control == "never_read":
        time.sleep(60)
        return 73
    if control == "memory_error_71":
        return 71
    if control == "stdout_excess":
        _write_bytes(sys.stdout.buffer, b"X" * 4194305)
        return 0
    if control == "stderr_excess":
        _write_bytes(sys.stderr.buffer, b"X" * 65537)
        return 0
    request, encoded, mapping_sha, mapping_result = _request_from_mapping(
        handle, control == "mapping_roundtrip"
    )
    result = {"step": "response_ready", "native_codec_imported": not _no_codecs()}
    if control == "mapping_roundtrip":
        result = mapping_result
    elif control == "memory_pressure":
        result = _memory_pressure()
    elif control == "grandchild_denied":
        result = _grandchild_denied()
    response = {
        "schema": "native_member_harmless_response_v1",
        "attempt_token": request["attempt_token"],
        "request_sha256": _sha(encoded),
        "execution_manifest_sha256": request["execution_manifest_sha256"],
        "status": "complete",
        "evidence": {
            "schema": "native_member_harmless_observation_v1",
            "control_id": control,
            "request_body": request,
            "mapping_sha256": mapping_sha,
            "result": result,
        },
        "failure_kind": None,
    }
    if control == "ordinary_refusal":
        response.update(status="refused", evidence=None, failure_kind="invalid_member")
    elif control == "wrong_token":
        response["attempt_token"] = _flip(response["attempt_token"])
    elif control == "wrong_request_hash":
        response["request_sha256"] = _flip(response["request_sha256"])
    elif control == "wrong_manifest_hash":
        response["execution_manifest_sha256"] = _flip(response["execution_manifest_sha256"])
    body = _canonical(response)
    frame = b"NMRES001" + len(body).to_bytes(4, "little") + body
    if control == "truncated_response":
        frame = frame[:-1]
    elif control == "trailing_response":
        frame += b"X"
    elif control == "duplicate_response":
        frame *= 2
    _write_bytes(sys.stdout.buffer, frame)
    if control == "stderr_nonempty":
        _write_bytes(sys.stderr.buffer, b"E")
    if control == "respond_then_wait":
        time.sleep(60)
    if control == "valid_then_exit_73":
        return 73
    return 2 if control == "ordinary_refusal" else 0


if __name__ == "__main__":
    raise SystemExit(main())
