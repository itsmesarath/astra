"""Fixed stdlib-first worker.  No native codec is loaded before registration.

This file is an internal process entry point, not a public command or reader.
Its own source is checked by the parent before the suspended process resumes.
"""

import ctypes as C
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

_FILES = {
    "engine": "_native_member_engine.py",
    "host": "_native_member_host.py",
    "profile": "_native_member_profile_20261012.json",
    "protocol": "_native_member_protocol_v1.json",
    "types": "_native_member_types.py",
    "worker": "_native_member_worker.py",
}
_TOKEN = re.compile(
    r'\s+|[{}\[\],:]|"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"|-?(?:0|[1-9][0-9]*)|true|false|null'
)


def _require(condition):
    if not condition:
        raise ValueError("invalid private worker protocol")


def _canonical(body):
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _strict(raw, maximum, nodes):
    """Bootstrap cannot import an unverified implementation to parse its pin."""
    _require(type(raw) is bytes and 0 < len(raw) <= maximum)
    text = raw.decode("utf-8", "strict")
    _require(not text.startswith("\ufeff"))
    offset = depth = count = 0
    while offset < len(text):
        match = _TOKEN.match(text, offset)
        _require(match is not None)
        token, offset = match.group(), match.end()
        if token.isspace() or token in (",", ":"):
            continue
        if token in ("{", "["):
            depth += 1
            count += 1
            _require(depth <= 64)
        elif token in ("}", "]"):
            depth -= 1
            _require(depth >= 0)
        else:
            count += 1
            _require(depth + 1 <= 64)
            if token[0] == "-" or token[0].isdigit():
                _require(len(token.lstrip("-")) <= 20)
        _require(count <= nodes)
    _require(depth == 0)
    body = json.loads(text, object_pairs_hook=_pairs)
    _require(_canonical(body) == raw)
    return body


def _parse_request_mapping(raw):
    _require(type(raw) is bytes and len(raw) == 1048576 and raw[:8] == b"NMREQ001")
    length = int.from_bytes(raw[8:12], "little")
    _require(0 < length <= 1048564)
    _require(not any(raw[12 + length :]))
    return _strict(raw[12 : 12 + length], 1048564, 128)


def _read_request_mapping(argv):
    _require(os.name == "nt" and C.sizeof(C.c_void_p) == 8)
    _require(
        type(argv) is list
        and len(argv) == 4
        and argv[0] == "--mapping-handle"
        and argv[2:] == ["--mapping-size", "1048576"]
    )
    _require(re.fullmatch(r"[1-9][0-9]{0,19}", argv[1]) is not None)
    handle = int(argv[1])
    _require(0 < handle < (1 << 64) - 1)
    api = C.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
    api.MapViewOfFile.argtypes = [C.c_void_p, C.c_uint32, C.c_uint32, C.c_uint32, C.c_size_t]
    api.MapViewOfFile.restype = C.c_void_p
    api.UnmapViewOfFile.argtypes, api.UnmapViewOfFile.restype = [C.c_void_p], C.c_int32
    api.CloseHandle.argtypes, api.CloseHandle.restype = [C.c_void_p], C.c_int32
    view = api.MapViewOfFile(handle, 4, 0, 0, 1048576)
    try:
        _require(bool(view))
        return C.string_at(view, 1048576)
    finally:
        unmapped = not view or bool(api.UnmapViewOfFile(view))
        closed = bool(api.CloseHandle(handle))
        if not unmapped or not closed:
            raise RuntimeError("worker mapping cleanup failed")


def _bounded_file(name, maximum):
    _require(name in {*_FILES.values(), "_native_member_execution_v1.json"})
    path = Path(__file__).with_name(name)
    _require(not path.is_symlink())
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    _require(0 < len(raw) <= maximum)
    return raw


def _bootstrap(expected_manifest_sha256):
    _require(
        type(expected_manifest_sha256) is str
        and re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256) is not None
    )
    raw = _bounded_file("_native_member_execution_v1.json", 65536)
    if hashlib.sha256(raw).hexdigest() != expected_manifest_sha256:
        raise RuntimeError("execution identity mismatch")
    manifest = _strict(raw, 65536, 1048576)
    _require(
        type(manifest) is dict
        and type(manifest.get("artifacts")) is list
        and len(manifest["artifacts"]) == 6
    )
    verified_sources = {}
    for row, logical_id in zip(manifest["artifacts"], sorted(_FILES), strict=True):
        _require(
            type(row) is dict
            and set(row) == {"logical_id", "relative_path", "kind", "raw_bytes", "raw_sha256"}
            and row["logical_id"] == logical_id
            and row["relative_path"] == _FILES[logical_id]
        )
        actual = _bounded_file(_FILES[logical_id], 4194304)
        if (
            type(row["raw_bytes"]) is not int
            or len(actual) != row["raw_bytes"]
            or hashlib.sha256(actual).hexdigest() != row["raw_sha256"]
        ):
            raise RuntimeError("implementation identity mismatch")
        if _FILES[logical_id].endswith(".py"):
            verified_sources[_FILES[logical_id][:-3]] = actual
    return manifest, verified_sources


def _load(name, verified_sources):
    _require(
        name in {"_native_member_types", "_native_member_host", "_native_member_engine"}
        and name not in sys.modules
    )
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    if spec is None or spec.loader is None:
        raise RuntimeError("fixed module loader unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    # -B forbids cache writes, not cache reads. Execute the exact source bytes
    # already checked against the registration, never an ambient bytecode cache.
    source = verified_sources[name]
    exec(compile(source, str(Path(__file__).with_name(name + ".py")), "exec"), module.__dict__)
    return module


def _response(request, evidence, status):
    body = {
        "schema": "native_member_worker_response_v1",
        "attempt_token": request["attempt_token"],
        "request_sha256": hashlib.sha256(_canonical(request)).hexdigest(),
        "execution_manifest_sha256": request["execution_manifest_sha256"],
        "status": status,
        "evidence": evidence,
        "failure_kind": "invalid_member" if status == "refused" else None,
    }
    raw = _canonical(body)
    _require(0 < len(raw) <= 2097152)
    return b"NMRES001" + len(raw).to_bytes(4, "little") + raw


def main():
    try:
        request = _parse_request_mapping(_read_request_mapping(sys.argv[1:]))
        _require(type(request) is dict and "execution_manifest_sha256" in request)
        try:
            manifest, verified_sources = _bootstrap(request["execution_manifest_sha256"])
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise RuntimeError("fixed bootstrap identity unavailable") from error
        _load("_native_member_types", verified_sources)
        host = _load("_native_member_host", verified_sources)
        try:
            _require(host._execution_manifest(request["execution_manifest_sha256"]) == manifest)
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise RuntimeError("fixed execution identity unavailable") from error
        host._validate_request(request, request["execution_manifest_sha256"], template=False)
    except MemoryError:
        return 71
    except RuntimeError:
        return 70
    except (ValueError, KeyError, TypeError, OSError):
        return 72
    try:
        engine = _load("_native_member_engine", verified_sources)
        evidence = engine.decode_request(request, manifest)
        status, code = "complete", 0
    except MemoryError:
        return 71
    except ValueError:
        evidence, status, code = None, "refused", 2
    except RuntimeError:
        return 70
    try:
        host._implementation_observations(manifest)
    except MemoryError:
        return 71
    except (OSError, ValueError, RuntimeError):
        return 70
    sys.stdout.buffer.write(_response(request, evidence, status))
    sys.stdout.buffer.flush()
    return code


if __name__ == "__main__":
    try:
        result = main()
    except BaseException:
        # No exception text/traceback/member values enter diagnostic channels.
        result = 1
    raise SystemExit(result)
