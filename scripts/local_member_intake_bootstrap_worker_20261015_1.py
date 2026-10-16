"""Root-owned, finite harmless-control bootstrap worker.

This program is not a member-file provider, an authentication mechanism, or a
parent-process sandbox.  Its final receipt is sealed before its own emission.
Only the separately registered root observer may launch the program.
"""

import sys
import os
import time
import json
import hashlib
import struct
import ctypes
import importlib.util


_ROOT = "C:/Users/pabta/Projects/ai-trader"
_HARD_END = "2026-10-15T14:59:08Z"
_HARD_END_NS = 1792076348000000000
_ROLE = "worker"
_CONTEXT_KEYS = (
    "version", "role", "registration", "protocol", "declarations",
    "source_manifest", "runtime_manifest", "expected_packet_sha256",
    "hard_end_utc", "hard_end_unix_ns", "working_directory", "worker_context",
)
_REF_KEYS = ("path", "raw_byte_length", "raw_sha256", "canonical_byte_length", "canonical_sha256")
_SOURCE_ROLES = (
    ("host", "scripts/local_member_intake_bootstrap_host_20261015_1.py"),
    ("worker", "scripts/local_member_intake_bootstrap_worker_20261015_1.py"),
    ("contract", "scripts/local_member_intake_bootstrap_contract_20261015_1.py"),
    ("validation", "scripts/local_member_intake_bootstrap_validation_20261015_1.py"),
    ("bootstrap_observer", "scripts/local_member_intake_bootstrap_observer_20261015_1.ps1"),
    ("bootstrap_primitives", "scripts/local_member_intake_bootstrap_primitives_20261015_1.psm1"),
)
_HELPERS = (
    ("contract", "local_member_intake_bootstrap_contract_20261015_1_fixed"),
    ("validation", "local_member_intake_bootstrap_validation_20261015_1_fixed"),
)
_READY = bytes.fromhex("4c4d494e4954310a")
_GO_MAGIC = bytes.fromhex("4c4d474f3030310a")
_U64 = (1 << 64) - 1


class BootstrapFailure(Exception):
    """A closed protocol or actual-observation refusal, never positive evidence."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _require(condition, reason="query_value"):
    if condition is not True:
        raise BootstrapFailure(reason)


def _keys(value, names):
    _require(type(value) is dict and set(value) == set(names))


def _integer(value, low, high):
    _require(type(value) is int and low <= value <= high)
    return value


def _hex(value, limit):
    _require(type(value) is str and len(value) % 2 == 0 and len(value) <= 2 * limit)
    _require(all(character in "0123456789abcdef" for character in value))
    return bytes.fromhex(value)


def _sha(value):
    _require(type(value) is str and len(value) == 64)
    _hex(value, 32)
    return value


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _pairs(pairs):
    result = {}
    for name, value in pairs:
        _require(name not in result, "duplicate_key")
        result[name] = value
    return result


def _invalid_number(_value):
    raise BootstrapFailure("query_value")


def _parse(raw, cap, canonical=False):
    _require(type(raw) is bytes and len(raw) <= cap, "budget")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise BootstrapFailure("utf8") from error
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_invalid_number)
    except json.JSONDecodeError as error:
        raise BootstrapFailure("trailing_json" if error.msg == "Extra data" else "query_value") from error
    if canonical:
        _require(_canonical(value) == raw, "query_value")
    return value


def _own_hash(value, key):
    _sha(value[key])
    _require(value[key] == _hash(_canonical({name: body for name, body in value.items() if name != key})), "transport")


def _with_hash(value, key):
    value[key] = _hash(_canonical(value))
    return value


def _deadline():
    _require(time.time_ns() < _HARD_END_NS, "deadline")


def _capture(path, length, digest, cap):
    """Capture only explicitly registered trusted metadata, once plus EOF."""
    _require(type(path) is str and path.startswith(_ROOT + "/"))
    _integer(length, 1, cap)
    _sha(digest)
    with open(path, "rb") as source:
        raw = source.read(cap + 1)
        _require(type(raw) is bytes and len(raw) == length and len(raw) <= cap, "budget")
        _require(source.read(1) == b"", "transport")
    _require(_hash(raw) == digest, "packet_pin")
    return raw


def _artifact(reference, expected_path, cap):
    _keys(reference, _REF_KEYS)
    _require(reference["path"] == expected_path)
    raw = _capture(reference["path"], reference["raw_byte_length"], reference["raw_sha256"], cap)
    value = _parse(raw, cap)
    canonical = _canonical(value)
    _integer(reference["canonical_byte_length"], 1, cap)
    _require(len(canonical) == reference["canonical_byte_length"])
    _require(_hash(canonical) == _sha(reference["canonical_sha256"]), "packet_pin")
    return value, raw


class FixedCapturedByteLoader:
    """Execute only previously captured, externally pinned helper source."""

    def __init__(self, raw, filename):
        self.raw = raw
        self.filename = filename

    def create_module(self, _spec):
        return None

    def exec_module(self, module):
        code = compile(self.raw, self.filename, "exec", dont_inherit=True, optimize=0)
        exec(code, module.__dict__)


def _load_helper(row, name):
    raw = _capture(row["path"], row["raw_byte_length"], row["raw_sha256"], 262144)
    loader = FixedCapturedByteLoader(raw, row["path"])
    specification = importlib.util.spec_from_file_location(name, row["path"], loader=loader)
    _require(specification is not None and specification.loader is loader)
    module = importlib.util.module_from_spec(specification)
    _require(module.__name__ == name and module.__file__ == row["path"] and module.__package__ == "")
    specification.loader.exec_module(module)
    return module


def _load_inputs(packet_hex, context_hex):
    packet_raw = _hex(packet_hex, 8193)
    context_raw = _hex(context_hex, 3072)
    context = _parse(context_raw, 3072, True)
    _keys(context, _CONTEXT_KEYS)
    _require(context["version"] == "local-member-intake-bootstrap-context-v1")
    _require(context["role"] == _ROLE and context["hard_end_utc"] == _HARD_END)
    _require(type(context["hard_end_unix_ns"]) is int and context["hard_end_unix_ns"] == _HARD_END_NS)
    _require(context["working_directory"] == _ROOT and os.getcwd() == "C:\\Users\\pabta\\Projects\\ai-trader")
    _deadline()
    registration_ref = context["registration"]
    _keys(registration_ref, _REF_KEYS)
    _require(registration_ref["path"] == _ROOT + "/logs/local_member_intake_proof_20261015_1/bootstrap_registration_2.json")
    registration, _ = _artifact(registration_ref, registration_ref["path"], 1048576)
    _require(registration["schema"] == "local-intake-bootstrap-registration-v2")
    _require(registration["window"]["hard_end_utc"] == _HARD_END)
    _require(registration["window"]["hard_end_unix_ns"] == _HARD_END_NS)
    resources = {row["role"]: row["artifact"] for row in registration["existing_inputs"]["json_resources"]}
    _require(context["protocol"] == resources["protocol"] and context["declarations"] == resources["declarations"])
    protocol, _ = _artifact(context["protocol"], resources["protocol"]["path"], 1048576)
    # Declarations are pinned complete metadata, never a production output oracle.
    _artifact(context["declarations"], resources["declarations"]["path"], 4194304)
    _require(protocol["hard_end_utc"] == _HARD_END and protocol["authority_flags"] == registration["authority_flags"])
    source_manifest, _ = _artifact(context["source_manifest"], registration["artifact_contract"]["source_manifest_path"], 1048576)
    runtime_manifest, _ = _artifact(context["runtime_manifest"], registration["artifact_contract"]["runtime_manifest_path"], 1048576)
    _keys(source_manifest, ("version", "registration_sha256", "sources"))
    _keys(runtime_manifest, ("version", "registration_sha256", "interpreter", "static_modules", "host_required_paths", "worker_required_paths", "exports"))
    _require(source_manifest["version"] == "local-member-intake-bootstrap-source-manifest-v1")
    _require(runtime_manifest["version"] == "local-member-intake-bootstrap-runtime-manifest-v1")
    _require(protocol["schemas"]["BootstrapResult"]["fields"]["version"]["value"] == "local-member-intake-bootstrap-result-v3")
    _require(protocol["schemas"]["BootstrapAttemptReceipt"]["fields"]["version"]["value"] == "local-member-intake-bootstrap-attempt-v3")
    registration_sha = registration_ref["canonical_sha256"]
    _require(source_manifest["registration_sha256"] == registration_sha == runtime_manifest["registration_sha256"])
    rows = source_manifest["sources"]
    _require(type(rows) is list and len(rows) == len(_SOURCE_ROLES))
    for row, (role, relative) in zip(rows, _SOURCE_ROLES):
        _keys(row, ("role", "path", "raw_byte_length", "raw_sha256"))
        _require(row["role"] == role and row["path"] == _ROOT + "/" + relative)
        _integer(row["raw_byte_length"], 1, 262144)
        _sha(row["raw_sha256"])
    _require([(row["role"], row["path"]) for row in registration["planned_sources"]["runtime"]] == [(role, _ROOT + "/" + path) for role, path in _SOURCE_ROLES])
    _require(runtime_manifest["interpreter"] == registration["runtime_contract"]["interpreter_static_candidate"])
    _require(runtime_manifest["exports"] == registration["runtime_contract"]["export_registrations"])
    allowlists = registration["runtime_contract"]["role_module_allowlists"]
    _require([row["role"] for row in allowlists] == ["host_runtime", "worker_runtime"])
    expected_modules = []
    _require(_canonical(allowlists[0]["files"]) == _canonical(allowlists[1]["files"]))
    _require(_canonical(allowlists[0]["required_paths"]) == _canonical(allowlists[1]["required_paths"]))
    for row in allowlists[0]["files"]:
        expected_modules.append({"role": "host_runtime", "absolute_path_utf16le_hex": row["absolute_path"].encode("utf-16-le").hex(), "byte_length": row["byte_length"], "sha256": row["sha256"]})
    _require(len(expected_modules) == 25)
    _require(runtime_manifest["static_modules"] == expected_modules)
    for role, allowlist in zip(("host", "worker"), allowlists):
        _require(runtime_manifest[role + "_required_paths"] == allowlist["required_paths"])
        _require(len(set(allowlist["required_paths"])) == len(allowlist["required_paths"]))
        _require(all(path in [row["absolute_path"] for row in allowlist["files"]] for path in allowlist["required_paths"]))
    for export in runtime_manifest["exports"]:
        _keys(export, ("role", "requested_module_path", "export_name", "allowed_owner_paths"))
        allowed = next(row for row in allowlists if row["role"] == export["role"] + "_runtime")
        paths = [row["absolute_path"] for row in allowed["files"]]
        _require(export["requested_module_path"] in paths and len(export["allowed_owner_paths"]) > 0)
        _require(len(set(export["allowed_owner_paths"])) == len(export["allowed_owner_paths"]))
        _require(all(path in paths for path in export["allowed_owner_paths"]))
    sources = {row["role"]: row for row in rows}
    helpers = {role: _load_helper(sources[role], name) for role, name in _HELPERS}
    expected_flags = helpers["contract"].packet_contract()["authority_flags"]
    for flags in (protocol["authority_flags"], registration["authority_flags"]):
        _require(type(flags) is list and len(flags) == 28 and _canonical(flags) == _canonical(expected_flags), "authority_flags")
        _require(all(type(row) is list and len(row) == 2 and row[1] is False for row in flags), "authority_flags")
    worker_context = None
    worker_context_raw = None
    if _ROLE == "host":
        worker_ref = context["worker_context"]
        _keys(worker_ref, _REF_KEYS)
        _require(sum(row["contexts"]["worker"] == worker_ref["path"] for row in registration["control_schedule"]) == 1)
        worker_context, worker_context_raw = _artifact(worker_ref, worker_ref["path"], 3072)
        _keys(worker_context, _CONTEXT_KEYS)
        _require(worker_context["version"] == context["version"] and worker_context["role"] == "worker" and worker_context["worker_context"] is None)
        for key in _CONTEXT_KEYS:
            if key not in ("role", "worker_context"):
                _require(worker_context[key] == context[key])
    else:
        _require(context["worker_context"] is None)
    return packet_raw, context, registration, protocol, source_manifest, runtime_manifest, helpers, worker_context, worker_context_raw


def _scalar_exception(value, absent=False):
    if absent:
        return {"kind": "absent", "value": None}
    if value is None:
        return {"kind": "none", "value": None}
    if type(value) is int:
        _integer(value, -(1 << 63), (1 << 63) - 1)
        return {"kind": "int", "value": value}
    _require(type(value) is str)
    return {"kind": "str", "value": value}


def _exception_attribute(error, name):
    if not hasattr(error, name):
        return _scalar_exception(None, True)
    return _scalar_exception(getattr(error, name))


class Native:
    """Owned FFI calls with complete initialized pre/post storage snapshots."""

    def __init__(self, protocol, registration, runtime_manifest, role):
        self.protocol = protocol
        self.registration = registration
        self.runtime_manifest = runtime_manifest
        self.role = role
        self.trace = []
        self.initialization = []
        self.bindings = []
        self.phase = "preflight"
        self.buffer_bytes = 0
        self.other_hex_bytes = 0
        self.functions = {}
        self.snapshots = []
        self.contracts = {row["api"]: row for row in protocol["schemas"]["ApiContracts"]["domain"]["value"]["rows"]}
        self.types = {}
        for name, entry in protocol["schemas"]["NativeScalars"]["domain"]["value"].items():
            self.types[name] = getattr(ctypes, entry["ffi"])
        self.types["JOBOBJECTINFOCLASS"] = ctypes.c_int32
        self.types["LPWSTR"] = ctypes.POINTER(ctypes.c_uint16)
        self.types["LPCWSTR"] = ctypes.POINTER(ctypes.c_uint16)
        self.types["LPBYTE"] = ctypes.POINTER(ctypes.c_uint8)
        self.types["LPCSTR"] = ctypes.POINTER(ctypes.c_uint8)
        for entry in protocol["schemas"]["NativeStructures"]["domain"]["value"]:
            fields = []
            for name, offset, width, native_type in entry["fields"]:
                resolved = self.resolve(native_type)
                if name == "elements":
                    resolved = resolved * (width // ctypes.sizeof(resolved))
                fields.append((name, resolved))
            structure = type(entry["name"], (ctypes.Structure,), {"_fields_": fields})
            _require(ctypes.sizeof(structure) == entry["bytes"] and ctypes.alignment(structure) == entry["alignment"])
            for name, offset, width, _ in entry["fields"]:
                _require(getattr(structure, name).offset == offset and getattr(structure, name).size == width)
            self.types[entry["name"]] = structure
        self._initialize()

    def resolve(self, native_type):
        if native_type.startswith("P(") and native_type.endswith(")"):
            return ctypes.POINTER(self.resolve(native_type[2:-1]))
        return self.types[native_type]

    def _initialize(self):
        arguments = next(row["arguments"] for row in self.registration["runtime_contract"]["constructor_arguments"] if row["owner_role"] == self.role)
        _require(_canonical(arguments) == _canonical({"name": "C:\\Windows\\System32\\kernel32.dll", "mode": 0, "handle": None, "use_errno": False, "use_last_error": True, "winmode": 2304}))
        _deadline()
        observation = {"ordinal": 0, "owner_role": self.role, "constructor": "ctypes.WinDLL", "arguments": dict(arguments), "source_selector": "R15/cpython_31210_ctypes_init.py.txt:CDLL.__init__/WinDLL", "started_monotonic_ns": time.monotonic_ns(), "ended_monotonic_ns": None, "completed": False, "exposed_handle_u64": None, "exception": None, "native_call_observation": "not_exposed", "reference_disposition": "unresolved"}
        self.initialization.append(observation)
        try:
            self.library = ctypes.WinDLL(**arguments)
        except OSError as error:
            details = {"type_module": type(error).__module__, "type_qualname": type(error).__qualname__, "args": [_scalar_exception(value) for value in error.args]}
            details.update({name: _exception_attribute(error, name) for name in ("errno", "winerror", "strerror", "filename", "filename2", "hresult")})
            details["display_text"] = str(error)
            observation.update(ended_monotonic_ns=time.monotonic_ns(), exception=details, reference_disposition="not_acquired")
            raise BootstrapFailure("query_failure") from error
        observation.update(ended_monotonic_ns=time.monotonic_ns(), completed=True, exposed_handle_u64=_integer(self.library._handle, 1, _U64), reference_disposition="process_lifetime_bootstrap")
        _require(len(_canonical(observation)) <= 32768, "budget")
        for name in self.registration["runtime_contract"]["binding_order"]:
            _deadline()
            row = {"ordinal": len(self.bindings), "owner_role": self.role, "constructor_ordinal": 0, "api_name": name, "lookup_kind": "ctypes_library_item", "source_selector": "R15/cpython_31210_ctypes_init.py.txt:CDLL.__getitem__/_FuncPtr", "started_monotonic_ns": time.monotonic_ns(), "ended_monotonic_ns": None, "completed": False, "exposed_address_u64": None, "exception": None, "native_call_observation": "not_exposed"}
            self.bindings.append(row)
            try:
                function = self.library[name]
            except AttributeError as error:
                if not hasattr(error, "obj"):
                    state = "absent"
                elif error.obj is None:
                    state = "none"
                else:
                    _require(error.obj is self.library)
                    state = "expected_library"
                row.update(ended_monotonic_ns=time.monotonic_ns(), exception={"type_module": type(error).__module__, "type_qualname": type(error).__qualname__, "args": [_scalar_exception(value) for value in error.args], "display_text": str(error), "name": _exception_attribute(error, "name"), "obj_state": state, "obj_constructor_ordinal": 0 if state == "expected_library" else None, "native_error_observed": False})
                raise BootstrapFailure("query_failure") from error
            contract = self.contracts[name]
            function.argtypes = [self.resolve(parameter[1]) for parameter in contract["parameters"]]
            function.restype = {"bool32": ctypes.c_int32, "dword32": ctypes.c_uint32, "handle64": ctypes.c_void_p, "void": None}[contract["return_kind"]]
            self.functions[name] = function
            address = ctypes.cast(function, ctypes.c_void_p).value
            row.update(ended_monotonic_ns=time.monotonic_ns(), completed=True, exposed_address_u64=_integer(address, 1, _U64))

    def buffer(self, size, initial=b""):
        _integer(size, 1, 65536)
        _require(type(initial) is bytes and len(initial) <= size)
        allocation = (ctypes.c_uint8 * size)()
        if initial:
            ctypes.memmove(allocation, initial, len(initial))
        return allocation

    def pointer(self, allocation, kind):
        if allocation is None:
            return (None, 0, "none", None)
        return (allocation, ctypes.sizeof(allocation), kind, None)

    def address(self, address, kind):
        _integer(address, 1, _U64)
        _require(kind in ("external_function_address", "allocation_base"))
        return (None, 0, kind, address)

    def raw(self, allocation):
        return ctypes.string_at(ctypes.addressof(allocation), ctypes.sizeof(allocation))

    def call(self, name, *values, valid=None):
        _deadline()
        contract = self.contracts[name]
        _require(len(values) == len(contract["parameters"]))
        _require(len(self.trace) < 4096, "budget")
        arguments = []
        native_arguments = []
        buffers = []
        reservation = 0
        for parameter, value in zip(contract["parameters"], values):
            parameter_name, native_type, kind, _, _ = parameter
            if kind == "pointer":
                allocation, size, pointee, address = value
                if allocation is not None:
                    address = ctypes.addressof(allocation)
                    before = self.raw(allocation)
                    reservation += 2 * size
                    buffers.append((parameter_name, allocation, size))
                else:
                    address = 0 if address is None else address
                    before = None
                pointer = {"address_u64": address, "storage_before_hex": None if before is None else before.hex(), "storage_bytes_u32": size, "pointee_kind": pointee}
                arguments.append({"name": parameter_name, "kind": "pointer", "value": pointer})
                native_arguments.append(ctypes.cast(ctypes.c_void_p(address), self.resolve(native_type)))
            else:
                _integer(value, -(1 << 31) if kind == "i64" else 0, (1 << 31) - 1 if kind == "i64" else ((1 << 32) - 1 if kind == "u32" else _U64))
                arguments.append({"name": parameter_name, "kind": kind, "value": value})
                native_arguments.append(value)
        # Host reserves one MiB for the complete later worker buffer occurrences.
        ceiling = 11534336 if self.role == "host" else 12582912
        _require(self.buffer_bytes + reservation <= ceiling, "budget")
        self.buffer_bytes += reservation
        started = time.monotonic_ns()
        seed = None
        if name == "GetFileType":
            previous = ctypes.set_last_error(0)
            _integer(previous, -(1 << 31), (1 << 31) - 1)
            seed = {"helper": "ctypes.set_last_error", "input_i32": 0, "returned_previous_i32": previous}
        returned = self.functions[name](*native_arguments)
        # No clock, log, serialization, or second foreign call precedes this read.
        kind = contract["return_kind"]
        actual = 0 if kind == "handle64" and returned is None else returned
        failed = kind == "bool32" and actual == 0
        if kind == "handle64":
            failed = actual == (1 << 64) - 1 if name == "GetStdHandle" else actual == 0 and name != "GetCurrentProcess"
        if kind == "dword32":
            failed = actual == 0 if name in ("GetFileType", "GetModuleFileNameW", "K32GetModuleFileNameExW") else actual == 4294967295 if name in ("ResumeThread", "WaitForSingleObject") else False
        if failed:
            signed_error = ctypes.get_last_error()
            _integer(signed_error, -(1 << 31), (1 << 31) - 1)
            error = signed_error if signed_error >= 0 else signed_error + (1 << 32)
        elif name == "GetModuleFileNameW" and actual == 512:
            signed_error = ctypes.get_last_error()
            _integer(signed_error, -(1 << 31), (1 << 31) - 1)
            error = signed_error if signed_error >= 0 else signed_error + (1 << 32)
        else:
            error = None
        ended = time.monotonic_ns()
        result = {"kind": kind, "raw_i64": actual if kind == "bool32" else None, "raw_u64": actual if kind in ("dword32", "handle64") else None, "win32_error_u32": error}
        outputs = []
        projections = {} if valid is None else valid(actual, error)
        for parameter_name, allocation, size in buffers:
            projection = projections.get(parameter_name)
            outputs.append({"parameter": parameter_name, "capacity_bytes": size, "returned_bytes": None if projection is None else projection[0], "full_buffer_hex": self.raw(allocation).hex(), "output_validity": "storage_only" if projection is None else "documented_valid", "valid_prefix_bytes": None if projection is None else projection[1], "projection_kind": "none" if projection is None else projection[2]})
        row = {"ordinal": len(self.trace), "phase": self.phase, "api": name, "source_selector": contract["source_selector"], "arguments": arguments, "return": result, "saved_error_seed": seed, "output_buffers": outputs, "started_monotonic_ns": started, "ended_monotonic_ns": ended}
        self.trace.append(row)
        return actual, row

    def require_call(self, name, *values, valid=None):
        value, row = self.call(name, *values, valid=valid)
        _require(value is not None and value != 0, "query_failure")
        return value, row

    def validate_bindings(self):
        kernel = self.library._handle
        for binding in self.bindings:
            name = binding["api_name"]
            encoded = name.encode("ascii") + b"\0"
            string = self.buffer(len(encoded), encoded)
            address, _ = self.require_call("GetProcAddress", kernel, self.pointer(string, "ascii_z"))
            _require(address == binding["exposed_address_u64"], "identity_mismatch")
            module = ctypes.c_uint64()
            self.require_call("GetModuleHandleExW", 6, self.address(address, "external_function_address"), self.pointer(module, "handle_out"), valid=lambda value, _error: {"phModule": (8, 8, "handle_u64")} if value else {})
            _require(module.value != 0, "query_value")
            path = self.module_path(module.value)
            registration = next(row for row in self.runtime_manifest["exports"] if row["role"] == self.role and row["export_name"] == name)
            _require(path in registration["allowed_owner_paths"], "identity_mismatch")

    def module_path(self, module, process=None):
        buffer = self.buffer(1024)
        name = "GetModuleFileNameW" if process is None else "K32GetModuleFileNameExW"
        values = (module, self.pointer(buffer, "utf16_mutable_z"), 512) if process is None else (process, module, self.pointer(buffer, "utf16_mutable_z"), 512)
        maximum = 511 if process is None else 510
        returned, row = self.call(name, *values, valid=lambda count, _error: {"lpFilename": (2 * count, 2 * (count + 1), "utf16_z")} if 1 <= count <= maximum and self.raw(buffer)[2 * count:2 * count + 2] == b"\0\0" else {})
        _require(1 <= returned <= maximum and self.raw(buffer)[2 * returned:2 * returned + 2] == b"\0\0", "identity_mismatch")
        return self.raw(buffer)[:2 * returned].decode("utf-16-le", errors="strict")

    def process_times(self, process, signalled=False):
        allocations = [self.types["FILETIME"]() for _ in range(4)]
        names = ("lpCreationTime", "lpExitTime", "lpKernelTime", "lpUserTime")
        def projections(returned, _error):
            if not returned:
                return {}
            return {name: (8, 8, "filetime_u64") for name in names if name != "lpExitTime" or signalled}
        self.require_call("GetProcessTimes", process, *(self.pointer(value, "filetime_out") for value in allocations), valid=projections)
        return [int.from_bytes(self.raw(value), "little") if name != "lpExitTime" or signalled else None for name, value in zip(names, allocations)]

    def process_image(self, process):
        path = self.buffer(1024)
        count = ctypes.c_uint32(512)
        def projections(returned, _error):
            if returned and 1 <= count.value <= 511 and self.raw(path)[2 * count.value:2 * count.value + 2] == b"\0\0":
                return {"lpExeName": (2 * count.value, 2 * (count.value + 1), "utf16_z"), "lpdwSize": (4, 4, "u32")}
            return {}
        self.require_call("QueryFullProcessImageNameW", process, 0, self.pointer(path, "utf16_mutable_z"), self.pointer(count, "dword_inout"), valid=projections)
        _require(1 <= count.value <= 511 and self.raw(path)[2 * count.value:2 * count.value + 2] == b"\0\0")
        return self.raw(path)[:2 * count.value].hex()

    def self_identity(self, prepared_command):
        process, _ = self.call("GetCurrentProcess")
        _require(process == _U64)
        process_id, _ = self.call("GetCurrentProcessId")
        _integer(process_id, 1, (1 << 32) - 1)
        times = self.process_times(process)
        return process, {"pid": process_id, "creation_filetime_u64": times[0], "image_utf16le_hex": self.process_image(process), "command_utf16le_hex": prepared_command.encode("utf-16-le").hex()}

    def snapshot(self, role, process, process_id, creation, ordinal):
        modules = self.buffer(1024)
        needed = ctypes.c_uint32()
        def projections(returned, _error):
            if returned and needed.value <= 1024 and needed.value % 8 == 0:
                return {"lphModule": (needed.value, needed.value, "module_array"), "lpcbNeeded": (4, 4, "u32")}
            return {}
        returned, row = self.call("K32EnumProcessModulesEx", process, self.pointer(modules, "module_array_128"), 1024, self.pointer(needed, "dword_out"), 3, valid=projections)
        self.other_hex_bytes += 1024
        _require(self.other_hex_bytes <= 2097152, "budget")
        snapshot = {"role": role, "ordinal": ordinal, "process_id": process_id, "process_creation_filetime_u64": creation, "enum_api_ordinal": row["ordinal"], "raw_module_buffer_hex": self.raw(modules).hex(), "needed_bytes": None, "entries": None, "state": "invalid"}
        _require(len(self.snapshots) < 6, "budget")
        self.snapshots.append(snapshot)
        _require(returned != 0 and 0 < needed.value <= 1024 and needed.value % 8 == 0, "identity_mismatch")
        snapshot["needed_bytes"] = needed.value
        entries = []
        snapshot["entries"] = entries
        allowlist = next(entry for entry in self.registration["runtime_contract"]["role_module_allowlists"] if entry["role"] == role + "_runtime")
        pins = {entry["absolute_path"]: entry for entry in allowlist["files"]}
        observed = []
        bases = set()
        for offset in range(0, needed.value, 8):
            base = int.from_bytes(self.raw(modules)[offset:offset + 8], "little")
            _require(base > 0 and base not in bases, "identity_mismatch")
            bases.add(base)
            path = self.module_path(base, None if role == self.role else process)
            entry = {"ordinal": len(entries), "module_base_u64": base, "path_api_ordinal": self.trace[-1]["ordinal"], "path_utf16le_hex": path.encode("utf-16-le").hex(), "registered_static_sha256": None}
            entries.append(entry)
            _require(path in pins, "identity_mismatch")
            entry["registered_static_sha256"] = pins[path]["sha256"]
            observed.append(path)
        _require(all(path in observed for path in allowlist["required_paths"]), "identity_mismatch")
        snapshot["state"] = "complete"
        return snapshot

    def handle_flags(self, handle, wanted=None):
        flags = ctypes.c_uint32()
        self.require_call("GetHandleInformation", handle, self.pointer(flags, "dword_out"), valid=lambda returned, _error: {"lpdwFlags": (4, 4, "u32")} if returned else {})
        _require(flags.value in (0, 1), "query_value")
        if wanted is not None:
            _require(flags.value == wanted, "query_value")
        return flags.value

    def std_handle(self, number):
        handle, _ = self.call("GetStdHandle", number)
        _require(0 < handle < _U64, "query_failure")
        kind, _ = self.call("GetFileType", handle)
        _require(kind == 3, "query_value")
        self.handle_flags(handle)
        return handle

    def pipe(self):
        read = ctypes.c_uint64()
        write = ctypes.c_uint64()
        security = self.types["SECURITY_ATTRIBUTES"]()
        security.nLength = 24
        security.bInheritHandle = 1
        self.require_call("CreatePipe", self.pointer(read, "handle_out"), self.pointer(write, "handle_out"), self.pointer(security, "security_attributes"), 65536, valid=lambda returned, _error: {"hReadPipe": (8, 8, "handle_u64"), "hWritePipe": (8, 8, "handle_u64")} if returned else {})
        _require(0 < read.value < _U64 and 0 < write.value < _U64 and read.value != write.value)
        self.handle_flags(read.value, 1)
        self.handle_flags(write.value, 1)
        return read.value, write.value

    def inherit(self, handle, inherit):
        self.require_call("SetHandleInformation", handle, 1, inherit)
        self.handle_flags(handle, inherit)

    def peek(self, handle):
        available = ctypes.c_uint32()
        message = ctypes.c_uint32()
        returned, row = self.call("PeekNamedPipe", handle, self.pointer(None, "none"), 0, self.pointer(None, "none"), self.pointer(available, "dword_out"), self.pointer(message, "dword_out"), valid=lambda value, _error: {"lpTotalBytesAvail": (4, 4, "u32"), "lpBytesLeftThisMessage": (4, 4, "u32")} if value else {})
        if returned:
            _require(message.value == 0)
            return available.value, False, row
        _require(row["return"]["win32_error_u32"] == 109, "transport")
        return 0, True, row

    def read(self, handle, requested):
        _integer(requested, 1, 65536)
        data = self.buffer(requested)
        count = ctypes.c_uint32()
        def projections(returned, _error):
            if returned and count.value <= requested:
                return {"lpBuffer": (count.value, count.value, "byte_prefix"), "lpNumberOfBytesRead": (4, 4, "u32")}
            return {}
        returned, row = self.call("ReadFile", handle, self.pointer(data, "byte_buffer"), requested, self.pointer(count, "dword_out"), self.pointer(None, "none"), valid=projections)
        if returned:
            _require(count.value <= requested)
            return self.raw(data)[:count.value], row, count.value
        return None, row, None

    def write(self, handle, raw, sealed=False):
        _require(type(raw) is bytes)
        ordinals = []
        for offset in range(0, len(raw), 65536):
            chunk = raw[offset:offset + 65536]
            data = self.buffer(len(chunk), chunk)
            count = ctypes.c_uint32()
            if sealed:
                # Intentionally outside the frozen receipt, never self-traced.
                returned = self.functions["WriteFile"](handle, ctypes.cast(data, ctypes.c_void_p), len(chunk), ctypes.byref(count), None)
                error = ctypes.get_last_error() if returned == 0 else None
                if returned == 0:
                    _integer(error, -(1 << 31), (1 << 31) - 1)
                _require(returned != 0 and count.value == len(chunk), "transport")
            else:
                returned, row = self.call("WriteFile", handle, self.pointer(data, "byte_buffer"), len(chunk), self.pointer(count, "dword_out"), self.pointer(None, "none"), valid=lambda value, _error: {"lpNumberOfBytesWritten": (4, 4, "u32")} if value else {})
                _require(returned != 0 and count.value == len(chunk), "transport")
                ordinals.append(row["ordinal"])
        return ordinals


def _prepared_command(interpreter, path, packet_hex, context_hex):
    values = ("-B", "-I", path, packet_hex, context_hex)
    _require(all(type(value) is str and value and not any(character in value for character in ' \t\r\n\0"') for value in values))
    _require(type(interpreter) is str and interpreter and not any(character in interpreter for character in '\r\n\0"'))
    command = '"' + interpreter + '" ' + " ".join(values)
    _require(len(command.encode("utf-16-le")) // 2 + 1 <= 24576, "budget")
    return command


def _declared_policy(protocol, case_id):
    policy = dict(protocol["budgets"])
    policy["process_memory_bytes"] = 536870912 if case_id == "memory_positive_control" else 268435456
    return policy


def _runtime_pins(context, source_manifest, runtime_manifest):
    pins = [dict(runtime_manifest["interpreter"])]
    for source in source_manifest["sources"][:2]:
        pins.append({"role": source["role"], "path": source["path"], "byte_length": source["raw_byte_length"], "sha256": source["raw_sha256"]})
    for role, key in (("protocol", "protocol"), ("oracle", "declarations")):
        artifact = context[key]
        pins.append({"role": role, "path": artifact["path"], "byte_length": artifact["raw_byte_length"], "sha256": artifact["raw_sha256"]})
    for source in source_manifest["sources"][2:]:
        pins.append({"role": "registered_dependency", "path": source["path"], "byte_length": source["raw_byte_length"], "sha256": source["raw_sha256"]})
    seen = {(row["role"], row["path"]) for row in pins}
    physical = {row["path"]: (row["byte_length"], row["sha256"]) for row in pins}
    host_modules = [row for row in runtime_manifest["static_modules"] if row["role"] == "host_runtime"]
    _require(len(host_modules) == 25 and len(runtime_manifest["static_modules"]) == 25)
    for source in host_modules:
        path = bytes.fromhex(source["absolute_path_utf16le_hex"]).decode("utf-16-le", errors="strict")
        if path == runtime_manifest["interpreter"]["path"]:
            _require((source["byte_length"], source["sha256"]) == (runtime_manifest["interpreter"]["byte_length"], runtime_manifest["interpreter"]["sha256"]))
            continue
        role = {"kernel32.dll": "kernel32", "KernelBase.dll": "kernelbase", "ntdll.dll": "ntdll"}.get(path.rsplit("\\", 1)[-1], "registered_dependency")
        key = (role, path)
        _require(path not in physical or physical[path] == (source["byte_length"], source["sha256"]))
        physical[path] = (source["byte_length"], source["sha256"])
        if key not in seen:
            pins.append({"role": role, "path": path, "byte_length": source["byte_length"], "sha256": source["sha256"]})
            seen.add(key)
    _require(len(pins) == 33, "budget")
    return pins


def _snapshot_identity(snapshot):
    return [(row["module_base_u64"], row["path_utf16le_hex"], row["registered_static_sha256"]) for row in snapshot["entries"]]


def _parser_bytes(length):
    prefix = b'{"padding":"'
    suffix = b'","version":"local-member-intake-bootstrap-parser-control-v1"}'
    _require(length in (1048576, 1048577))
    return prefix + b"a" * (length - len(prefix) - len(suffix)) + suffix


def _go_read(native, stdin, stdout, packet, packet_raw):
    native.phase = "resumed"
    native.write(stdout, _READY)
    pieces = []
    reads = []
    size = 0
    while size < 48:
        _deadline()
        available, eof, _ = native.peek(stdin)
        _require(not eof, "transport")
        remaining = 48 - size
        if available < remaining:
            time.sleep(0.02)
            continue
        data, row, count = native.read(stdin, remaining)
        _require(data is not None and type(count) is int and 1 <= count <= remaining, "transport")
        reads.append({"ordinal": len(reads), "offset_u32": size, "requested_count_u32": remaining, "api_ordinal": row["ordinal"], "return": row["return"], "returned_count_u32": count, "buffer_observations": row["output_buffers"]})
        # These complete post-storage copies occur again inside GoObservation.
        native.buffer_bytes += sum(value["capacity_bytes"] for value in row["output_buffers"])
        _require(native.buffer_bytes <= 12582912, "budget")
        pieces.append(data)
        size += count
    raw = b"".join(pieces)
    _require(len(raw) == 48 and raw[:8] == _GO_MAGIC, "transport")
    host_pid, worker_pid = struct.unpack("<II", raw[8:16])
    actual_worker_pid, _ = native.call("GetCurrentProcessId")
    _require(0 < host_pid <= 4294967295 and worker_pid == actual_worker_pid, "identity_mismatch")
    # This sole closure probe is permitted without a positive preceding peek.
    data, row, count = native.read(stdin, 1)
    _require(data is None and count is None and row["return"]["raw_i64"] == 0 and row["return"]["win32_error_u32"] == 109, "transport")
    eof_probe = {"ordinal": len(reads), "offset_u32": 48, "requested_count_u32": 1, "api_ordinal": row["ordinal"], "return": row["return"], "returned_count_u32": None, "buffer_observations": row["output_buffers"]}
    native.buffer_bytes += sum(value["capacity_bytes"] for value in row["output_buffers"])
    native.phase = "handle_closed"
    returned, close_row = native.call("CloseHandle", stdin)
    close = {"ordinal": 0, "role": "control_stdin_read", "handle_u64": stdin, "close_attempted": True, "close_bool_i32": returned, "win32_error_u32": close_row["return"]["win32_error_u32"], "disposition": "closed" if returned else "close_failed"}
    _require(returned != 0, "query_failure")
    observation = {"packet_hex": raw.hex(), "initialization": native.initialization, "binding_initialization": native.bindings, "data_reads": reads, "eof_probe": eof_probe, "stdin_close": close}
    _require(len(_canonical(observation)) <= 262144, "budget")
    return host_pid, worker_pid, observation, close


def _memory_control(native, positive):
    native.phase = "resumed"
    address, row = native.call("VirtualAlloc", native.pointer(None, "none"), 268435456, 12288, 4)
    result = {"allocation_type_u32": 12288, "requested_bytes_u64": 268435456, "protection_u32": 4, "return_address_u64": address, "win32_error_u32": row["return"]["win32_error_u32"], "release": None}
    if address:
        returned, free_row = native.call("VirtualFree", native.address(address, "allocation_base"), 0, 32768)
        result["release"] = {"attempted": True, "address_u64": address, "size_u64": 0, "free_type_u32": 32768, "return_bool_i32": returned, "win32_error_u32": free_row["return"]["win32_error_u32"]}
    # Preserve unexpected allocation/release observations in the complete body;
    # the host and independent reader refuse a mismatched control outcome.
    return _canonical(result), "completed" if address > 0 else "controlled_failure"


def _pending_marker(native, stdout, packet, packet_raw, host_pid, worker_pid, go, started):
    native.phase = "resumed"
    read, write = native.pipe()
    native.inherit(read, 0)
    native.inherit(write, 0)
    data = native.buffer(1)
    count = ctypes.c_uint32()
    arguments = [
        {"name": "hFile", "kind": "handle64", "value": read},
        {"name": "lpBuffer", "kind": "pointer", "value": {"address_u64": ctypes.addressof(data), "storage_before_hex": "00", "storage_bytes_u32": 1, "pointee_kind": "byte_buffer"}},
        {"name": "nNumberOfBytesToRead", "kind": "u32", "value": 1},
        {"name": "lpNumberOfBytesRead", "kind": "pointer", "value": {"address_u64": ctypes.addressof(count), "storage_before_hex": "00000000", "storage_bytes_u32": 4, "pointee_kind": "dword_out"}},
        {"name": "lpOverlapped", "kind": "pointer", "value": {"address_u64": 0, "storage_before_hex": None, "storage_bytes_u32": 0, "pointee_kind": "none"}},
    ]
    inputs = [
        {"parameter": "lpBuffer", "capacity_bytes": 1, "returned_bytes": None, "full_buffer_hex": "00", "output_validity": "storage_only", "valid_prefix_bytes": None, "projection_kind": "none"},
        {"parameter": "lpNumberOfBytesRead", "capacity_bytes": 4, "returned_bytes": None, "full_buffer_hex": "00000000", "output_validity": "storage_only", "valid_prefix_bytes": None, "projection_kind": "none"},
    ]
    marker = {"version": "local-member-intake-bootstrap-pending-read-v2", "case_id": packet["case_id"], "packet_sha256": _hash(packet_raw), "nonce_hex": packet["nonce_hex"], "worker_pid": worker_pid, "observed_parent_pid": host_pid, "started_monotonic_ns": started, "go_observation": go, "owned_handles": [{"role": "control_pipe_read", "handle_u64": read}, {"role": "control_pipe_write", "handle_u64": write}], "completed_api_trace": list(native.trace), "pending_call": {"api": "ReadFile", "source_selector": native.contracts["ReadFile"]["source_selector"], "arguments": arguments, "input_buffers": inputs, "started_monotonic_ns": time.monotonic_ns()}, "authority_flags": packet["authority_flags"]}
    _with_hash(marker, "marker_sha256")
    raw = _canonical(marker)
    _require(len(raw) <= 262144, "budget")
    # The pending timestamp is a pre-entry lower bound, not a future call return.
    # Full synchronous emission succeeds before the next blocking operation.
    native.write(stdout, raw, sealed=True)
    returned = native.functions["ReadFile"](read, ctypes.cast(data, ctypes.c_void_p), 1, ctypes.byref(count), None)
    error = ctypes.get_last_error() if returned == 0 else None
    if returned == 0:
        _integer(error, -(1 << 31), (1 << 31) - 1)
    # A returned private read is unexpected; no fabricated successful timeout.
    raise BootstrapFailure("query_failure")


def main():
    _require(len(sys.argv) == 3, "packet_context")
    packet_raw, context, registration, protocol, source_manifest, runtime_manifest, helpers, _worker_context, _worker_raw = _load_inputs(sys.argv[1], sys.argv[2])
    packet = helpers["contract"].admit_packet(packet_raw, expected_packet_sha256=context["expected_packet_sha256"], registration_sha256=context["registration"]["canonical_sha256"], protocol_sha256=context["protocol"]["canonical_sha256"], oracle_sha256=context["declarations"]["raw_sha256"], now_unix_ns=time.time_ns())
    _require(packet["authority_flags"] == protocol["authority_flags"])
    case = packet["case_id"]
    if case == "initialization_stall":
        time.sleep(13)
        raise BootstrapFailure("work_deadline")
    native = Native(protocol, registration, runtime_manifest, "worker")
    native.validate_bindings()
    stdin = native.std_handle(4294967286)
    stdout = native.std_handle(4294967285)
    stderr = native.std_handle(4294967284)
    started = time.monotonic_ns()
    host_pid, worker_pid, go, close = _go_read(native, stdin, stdout, packet, packet_raw)
    native.phase = "resumed"
    if case == "wall_stall":
        time.sleep(13)
        raise BootstrapFailure("work_deadline")
    if case == "cpu_limit":
        state = 1
        while True:
            for _ in range(1048576):
                state = (state * 1664525 + 1013904223) % 4294967296
    if case == "crash":
        os._exit(37)
    if case == "blocked_owned_pipe_read":
        _pending_marker(native, stdout, packet, packet_raw, host_pid, worker_pid, go, started)
    if case in ("result_exact_limit", "result_first_excess"):
        native.write(stdout, _parser_bytes(packet["control"]["amount"]))
        return 0
    if case in ("diagnostic_exact_limit", "diagnostic_first_excess"):
        native.write(stdout, b"d" * packet["control"]["amount"])
        return 0
    if case in ("invalid_utf8", "duplicate_key", "trailing_json"):
        native.write(stdout, bytes.fromhex(packet["control"]["literal_hex"]))
        return 0
    payload = b"bootstrap-ok"
    status = "completed"
    if case in ("memory_limit", "memory_positive_control"):
        payload, status = _memory_control(native, case == "memory_positive_control")
    if case == "unexpected_stderr":
        native.write(stderr, b"x")
    bundle = {"control_payload_hex": payload.hex(), "go_observation": go}
    payload_bytes = _canonical(bundle)
    _require(len(payload_bytes) <= 262144, "budget")
    result = {"version": "local-member-intake-bootstrap-result-v3", "case_id": case, "packet_sha256": _hash(packet_raw), "nonce_hex": packet["nonce_hex"], "status": status, "worker_pid": worker_pid, "observed_parent_pid": host_pid, "started_monotonic_ns": started, "ended_monotonic_ns": time.monotonic_ns(), "payload_hex": payload_bytes.hex(), "worker_pre_emission_api_trace": list(native.trace), "worker_cleanup": [close], "authority_flags": packet["authority_flags"]}
    raw = _canonical(result)
    _require(len(raw) <= 1048576, "budget")
    # The result is sealed now. Its own emission is externally observed only.
    native.write(stdout, raw, sealed=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())



