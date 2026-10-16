"""Root-owned, finite harmless-control bootstrap host.

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
_ROLE = "host"
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


def _schema(value, name, protocol):
    """Enforce complete P record/type domains; relational checks are explicit."""
    registry = protocol["schemas"]
    regular = sys.modules["re"]
    def expression(body, declaration, depth):
        _require(depth <= 64, "budget")
        operation = declaration["op"]
        if operation == "ref":
            definition(body, registry[declaration["name"]], depth + 1)
        elif operation == "literal":
            _require(_canonical(body) == _canonical(declaration["value"]))
        elif operation == "nullable":
            if body is not None:
                expression(body, declaration["item"], depth + 1)
        elif operation == "array":
            _require(type(body) is list and declaration["min"] <= len(body) <= declaration["max"])
            for item in body:
                expression(item, declaration["item"], depth + 1)
        elif operation == "union":
            for item in declaration["items"]:
                try:
                    expression(body, item, depth + 1)
                except BootstrapFailure:
                    continue
                return
            raise BootstrapFailure("query_value")
        else:
            raise BootstrapFailure("query_value")
    def domain(body, declaration, depth):
        operation = declaration["op"]
        if operation == "integer":
            _integer(body, declaration["min"], declaration["max"])
        elif operation == "boolean":
            _require(type(body) is bool)
        elif operation == "string":
            _require(type(body) is str and declaration["min"] <= len(body) <= declaration["max"])
            if declaration["encoding"] == "ASCII":
                _require(body.isascii())
            if declaration["pattern"] is not None:
                _require(regular.fullmatch(declaration["pattern"], body) is not None)
        elif operation == "enum":
            _require(any(_canonical(body) == _canonical(item) for item in declaration["values"]))
        elif operation == "literal":
            _require(_canonical(body) == _canonical(declaration["value"]))
        elif operation in ("array", "union"):
            expression(body, declaration, depth + 1)
        else:
            raise BootstrapFailure("query_value")
    def definition(body, declaration, depth):
        _require(depth <= 64, "budget")
        if declaration["kind"] == "record":
            _keys(body, declaration["keys"])
            for key in declaration["keys"]:
                expression(body[key], declaration["fields"][key], depth + 1)
        else:
            domain(body, declaration["domain"], depth + 1)
    definition(value, registry[name], 0)
    cap = protocol["schemas"]["RecordCaps"]["domain"]["value"].get(name)
    if type(cap) is int:
        _require(len(_canonical(value)) <= cap, "budget")


def _date_filetime(value):
    """Check retained round-trip/ticks/offset arithmetic without another query."""
    _require(value["managed_type"] == "System.DateTime" and value["conversion_state"] == "valid")
    _require(value["kind"] in ("Utc", "Local") and value["quantum_100ns"] in (1, 10))
    text = value["roundtrip_text"]
    _require(type(text) is str and len(text) in (28, 33))
    _require(text[4] == text[7] == "-" and text[10] == "T" and text[13] == text[16] == ":" and text[19] == ".")
    components = (text[:4], text[5:7], text[8:10], text[11:13], text[14:16], text[17:19], text[20:27])
    _require(all(part.isascii() and part.isdigit() for part in components))
    year, month, day, hour, minute, second, fraction = [int(part) for part in components]
    _require(1 <= year <= 9999 and 1 <= month <= 12 and 0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60)
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    month_days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    _require(1 <= day <= month_days[month - 1])
    previous = year - 1
    days = 365 * previous + previous // 4 - previous // 100 + previous // 400 + sum(month_days[:month - 1]) + day - 1
    ticks = ((days * 24 + hour) * 3600 + minute * 60 + second) * 10000000 + fraction
    _require(ticks == value["ticks_i64"])
    if value["kind"] == "Utc":
        _require(len(text) == 28 and text[-1] == "Z")
        utc = ticks
    else:
        _require(len(text) == 33 and text[27] in ("+", "-") and text[30] == ":")
        _require(text[28:30].isdigit() and text[31:33].isdigit())
        hours, minutes = int(text[28:30]), int(text[31:33])
        _require(hours <= 14 and minutes < 60 and (hours < 14 or minutes == 0))
        offset = (hours * 60 + minutes) * 600000000
        utc = ticks - offset if text[27] == "+" else ticks + offset
    _require(value["utc_ticks_i64"] == utc and value["filetime_u64"] == utc - 504911232000000000, "timestamp")
    _integer(value["filetime_u64"], 0, _U64)
    return value["filetime_u64"]


def _query_text(process_id):
    _integer(process_id, 1, 4294967295)
    return "Get-CimInstance -Namespace 'root/cimv2' -ClassName 'Win32_Process' -Filter ('ProcessId = {0}' -f " + str(process_id) + ") -Property 'ProcessId','ParentProcessId','CreationDate','ExecutablePath','CommandLine' -OperationTimeoutSec 1 -ErrorAction Stop"


class Host:
    def __init__(self, loaded, packet_hex, context_hex):
        self.raw, self.context, self.registration, self.protocol, self.sources, self.runtime, self.helpers, self.worker_context, self.worker_raw = loaded
        self.packet_hex = packet_hex
        self.context_hex = context_hex
        self.registration_sha = self.context["registration"]["canonical_sha256"]
        self.oracle_sha = self.context["declarations"]["raw_sha256"]
        self.protocol_sha = self.context["protocol"]["canonical_sha256"]
        self.packet = None
        self.native = None
        self.owned = {}
        self.parent_closes = []
        self.lifecycle = []
        self.job_observations = []
        self.module_observations = []
        self.stdout_data = bytearray()
        self.stderr_data = bytearray()
        self.stdout_eof = False
        self.stderr_eof = False
        self.stdout_ordinals = []
        self.stderr_ordinals = []
        self.stdout_excess = False
        self.stderr_excess = False
        self.parent_identity = None
        self.creation = json.loads(_canonical(self.protocol["schemas"]["PureRefusalPolicy"]["domain"]["value"]["creation"]))
        self.terminal = {"outcome": "incomplete", "failure_stage": None, "failure_code": None, "termination_requested": False, "termination_return": None, "wait_result_u32": None, "exit_code_u32": None, "exit_filetime_u64": None, "kernel_time_100ns_u64": None, "user_time_100ns_u64": None, "final_job_empty": None, "parent_closes": self.parent_closes, "cleanup_complete": None, "acceptance": "incomplete"}
        self.result = None
        self.birth = None
        self.work_end = None
        self.attributes = None
        self.attributes_initialized = False
        self.fault = None
        self._event("preflight")

    def _event(self, event, related=()):
        _require(len(self.lifecycle) < 4096, "budget")
        self.lifecycle.append({"ordinal": len(self.lifecycle), "event": event, "monotonic_ns": time.monotonic_ns(), "related_api_ordinals": list(related)})
        if self.native is not None:
            self.native.phase = event

    def _choose(self, outcome, code=None, acceptance="accepted_control"):
        self.terminal.update(outcome=outcome, failure_stage=self.lifecycle[-1]["event"] if code else None, failure_code=code, acceptance=acceptance)
        if code:
            self._event("failure_selected")

    def _remaining(self, end=None):
        _deadline()
        if end is None:
            end = self.work_end
        _require(end is not None)
        remaining = min(end - time.monotonic_ns(), _HARD_END_NS - time.time_ns())
        _require(remaining > 0, "work_deadline")
        return remaining

    def _close(self, role):
        _require(role in self.owned and self.owned[role] is not None)
        handle = self.owned[role]
        value, row = self.native.call("CloseHandle", handle)
        close = {"ordinal": len(self.parent_closes), "role": role, "handle_u64": handle, "close_attempted": True, "close_return": row["return"], "close_api_ordinal": row["ordinal"], "disposition": "closed" if value else "close_failed"}
        self.parent_closes.append(close)
        # A failed close is not retried or declared closed.
        self.owned[role] = None
        self._event("handle_closed", (row["ordinal"],))
        _require(value != 0, "query_failure")
        return close

    def _unattempted_closes(self):
        recorded = {row["role"] for row in self.parent_closes}
        for role, handle in self.owned.items():
            if handle is not None and role not in recorded:
                self.parent_closes.append({"ordinal": len(self.parent_closes), "role": role, "handle_u64": handle, "close_attempted": False, "close_return": None, "close_api_ordinal": None, "disposition": "not_attempted"})

    def _job_query(self, phase):
        values = {}
        rows = {}
        for info_class, size, pointee, projection in ((9, 144, "job_extended_limit", "job_extended_limits"), (1, 48, "job_accounting", "job_accounting"), (3, 16, "job_pid_list", "job_pid_list")):
            allocation = self.native.buffer(size)
            length = ctypes.c_uint32()
            def valid(returned, _error, size=size, info_class=info_class, allocation=allocation, length=length, projection=projection):
                expected = size
                if info_class == 3:
                    assigned, listed = struct.unpack("<II", self.native.raw(allocation)[:8])
                    expected = 8 + listed * 8
                    if assigned != listed or listed > 1:
                        return {}
                if returned and length.value == expected:
                    return {"lpJobObjectInformation": (expected, expected, projection), "lpReturnLength": (4, 4, "u32")}
                return {}
            returned, row = self.native.call("QueryInformationJobObject", self.owned["job"], info_class, self.native.pointer(allocation, pointee), size, self.native.pointer(length, "dword_out"), valid=valid)
            values[info_class] = (returned, self.native.raw(allocation), length.value)
            rows[info_class] = row
        observation = {"ordinal": len(self.job_observations), "phase": phase, "limits_state": "attempted_invalid", "accounting_state": "attempted_invalid", "process_list_state": "attempted_invalid", "limits_return": rows[9]["return"], "accounting_return": rows[1]["return"], "process_list_return": rows[3]["return"], "limits_api_ordinal": rows[9]["ordinal"], "accounting_api_ordinal": rows[1]["ordinal"], "process_list_api_ordinal": rows[3]["ordinal"], "extended_limit_bytes_hex": values[9][1].hex(), "accounting_bytes_hex": values[1][1].hex(), "pid_list_bytes_hex": values[3][1].hex(), "extended_limits": None, "accounting": None, "assigned_process_count": None, "listed_process_count": None, "process_ids": None}
        self.job_observations.append(observation)
        if values[9][0] and values[9][2] == 144:
            raw = values[9][1]
            basic = struct.unpack_from("<qqI", raw)
            working = struct.unpack_from("<QQ", raw, 24)
            active = struct.unpack_from("<I", raw, 40)[0]
            affinity, priority, scheduling = struct.unpack_from("<QII", raw, 48)
            io = struct.unpack_from("<QQQQQQ", raw, 64)
            memory = struct.unpack_from("<QQQQ", raw, 112)
            observation["extended_limits"] = {"per_process_user_time_i64": basic[0], "per_job_user_time_i64": basic[1], "limit_flags_u32": basic[2], "minimum_working_set_u64": working[0], "maximum_working_set_u64": working[1], "active_process_limit_u32": active, "affinity_u64": affinity, "priority_class_u32": priority, "scheduling_class_u32": scheduling, "io_counters": dict(zip(("read_operation_count", "write_operation_count", "other_operation_count", "read_transfer_count", "write_transfer_count", "other_transfer_count"), io)), "process_memory_limit_u64": memory[0], "job_memory_limit_u64": memory[1], "peak_process_memory_used_u64": memory[2], "peak_job_memory_used_u64": memory[3]}
            observation["limits_state"] = "observed_valid"
        if values[1][0] and values[1][2] == 48:
            accounting = struct.unpack("<qqqqIIII", values[1][1])
            observation["accounting"] = dict(zip(("total_user_time_i64", "total_kernel_time_i64", "period_user_time_i64", "period_kernel_time_i64", "total_page_fault_count_u32", "total_processes_u32", "active_processes_u32", "total_terminated_processes_u32"), accounting))
            observation["accounting_state"] = "observed_valid"
        if values[3][0]:
            assigned, listed, process_id = struct.unpack("<IIQ", values[3][1])
            if assigned == listed and listed <= 1 and values[3][2] == 8 + listed * 8:
                observation.update(assigned_process_count=assigned, listed_process_count=listed, process_ids=[] if listed == 0 else [process_id], process_list_state="observed_valid")
        _require(all(observation[key] == "observed_valid" for key in ("limits_state", "accounting_state", "process_list_state")), "query_failure")
        limits = observation["extended_limits"]
        _require(limits["per_process_user_time_i64"] == 50000000 and limits["limit_flags_u32"] == 8458 and limits["active_process_limit_u32"] == 1 and limits["process_memory_limit_u64"] == self.policy["process_memory_bytes"], "query_value")
        return observation

    def _prepare(self):
        self.native = Native(self.protocol, self.registration, self.runtime, "host")
        self.module_observations = self.native.snapshots
        self.creation["module_observations"] = self.module_observations
        self.creation["initialization"] = self.native.initialization
        self.creation["binding_initialization"] = self.native.bindings
        self.native.validate_bindings()
        interpreter = self.registration["process_contract"]["direct_interpreter"]
        host_path = _ROOT + "/scripts/local_member_intake_bootstrap_host_20261015_1.py"
        self.host_command = _prepared_command(interpreter, host_path, self.packet_hex, self.context_hex)
        self.self_handle, self.self_request = self.native.self_identity(self.host_command)
        method = self.registration["binding_contract"]["parent_observation_method"]
        self.parent_identity = {"observation_state": "incomplete", "pid": self.self_request["pid"], "creation_filetime_u64": self.self_request["creation_filetime_u64"], "image_utf16le_hex": self.self_request["image_utf16le_hex"], "command_utf16le_hex": self.self_request["command_utf16le_hex"], "creator_pid": None, "creator_creation_filetime_u64": None, "observation_method": method}
        for _ in range(2):
            self.native.snapshot("host", self.self_handle, self.self_request["pid"], self.self_request["creation_filetime_u64"], len(self.module_observations))
        _require(_snapshot_identity(self.module_observations[0]) == _snapshot_identity(self.module_observations[1]), "identity_mismatch")
        self.host_stdin = self.native.std_handle(4294967286)
        self.host_stdout = self.native.std_handle(4294967285)
        self.host_stderr = self.native.std_handle(4294967284)
        job, row = self.native.require_call("CreateJobObjectW", self.native.pointer(None, "none"), self.native.pointer(None, "none"))
        self.owned["job"] = job
        self._event("job_created", (row["ordinal"],))
        limits = self.native.types["JOBOBJECT_EXTENDED_LIMIT_INFORMATION"]()
        limits.BasicLimitInformation.PerProcessUserTimeLimit = 50000000
        limits.BasicLimitInformation.LimitFlags = 8458
        limits.BasicLimitInformation.ActiveProcessLimit = 1
        limits.ProcessMemoryLimit = self.policy["process_memory_bytes"]
        _, row = self.native.require_call("SetInformationJobObject", job, 9, self.native.pointer(limits, "job_extended_limit"), 144)
        self._event("limits_set", (row["ordinal"],))
        observation = self._job_query("before_create")
        self._event("limits_queried", (observation["limits_api_ordinal"], observation["accounting_api_ordinal"], observation["process_list_api_ordinal"]))
        _require(observation["process_ids"] == [] and observation["accounting"]["active_processes_u32"] == 0)
        self._event("job_empty")
        for read_role, write_role in (("child_stdin_read", "child_stdin_write"), ("stdout_read", "stdout_write"), ("stderr_read", "stderr_write")):
            read, write = self.native.pipe()
            self.owned[read_role] = read
            self.owned[write_role] = write
            self.native.inherit(write if read_role == "child_stdin_read" else read, 0)
        self._event("pipes_created")
        required = ctypes.c_uint64()
        returned, _ = self.native.call("InitializeProcThreadAttributeList", self.native.pointer(None, "none"), 2, 0, self.native.pointer(required, "size_t_inout"), valid=lambda _value, _error: {"lpSize": (8, 8, "u64")})
        _require(returned == 0 and 1 <= required.value <= 65536, "query_value")
        self.attributes = self.native.buffer(required.value)
        _require(ctypes.addressof(self.attributes) % 8 == 0)
        self.native.require_call("InitializeProcThreadAttributeList", self.native.pointer(self.attributes, "opaque_attribute_list"), 2, 0, self.native.pointer(required, "size_t_inout"), valid=lambda value, _error: {"lpAttributeList": (ctypes.sizeof(self.attributes), ctypes.sizeof(self.attributes), "opaque_attribute_list"), "lpSize": (8, 8, "u64")} if value else {})
        self.attributes_initialized = True
        self.handle_array = self.native.types["HANDLE_ARRAY_3"]()
        inherited = [self.owned["child_stdin_read"], self.owned["stdout_write"], self.owned["stderr_write"]]
        for index, handle in enumerate(inherited):
            self.handle_array.elements[index] = handle
        self.job_array = self.native.types["HANDLE_ARRAY_1"]()
        self.job_array.elements[0] = job
        returned, _ = self.native.call("UpdateProcThreadAttribute", self.native.pointer(self.attributes, "opaque_attribute_list"), 0, 131074, self.native.pointer(self.handle_array, "handle_array_3"), 24, self.native.pointer(None, "none"), self.native.pointer(None, "none"))
        self.creation["handle_attribute_u64"] = 131074
        _require(returned != 0, "query_failure")
        returned, _ = self.native.call("UpdateProcThreadAttribute", self.native.pointer(self.attributes, "opaque_attribute_list"), 0, 131085, self.native.pointer(self.job_array, "handle_array_1"), 8, self.native.pointer(None, "none"), self.native.pointer(None, "none"))
        self.creation["job_attribute_u64"] = 131085
        _require(returned != 0, "query_failure")
        self.creation["inherited_handles_u64"] = inherited
        self._event("attributes_ready")

    def _create(self):
        interpreter = self.registration["process_contract"]["direct_interpreter"]
        path = _ROOT + "/scripts/local_member_intake_bootstrap_worker_20261015_1.py"
        _require(self.worker_raw == _canonical(self.worker_context))
        self.worker_command = _prepared_command(interpreter, path, self.packet_hex, self.worker_raw.hex())
        pairs = self.registration["process_contract"]["environment"]
        _require(type(pairs) is list and len(pairs) == 9)
        names = set()
        environment = []
        for pair in pairs:
            _keys(pair, ("name", "value"))
            _require(type(pair["name"]) is str and pair["name"] and type(pair["value"]) is str)
            _require(not any(character in pair["name"] for character in "=\0") and "\0" not in pair["value"] and pair["name"].upper() not in names)
            names.add(pair["name"].upper())
            environment.append(pair["name"] + "=" + pair["value"])
        environment_raw = ("\0".join(environment) + "\0\0").encode("utf-16-le")
        _require(len(environment_raw) <= 16384, "budget")
        command_raw = (self.worker_command + "\0").encode("utf-16-le")
        application = self.native.buffer(len(interpreter.encode("utf-16-le")) + 2, interpreter.encode("utf-16-le") + b"\0\0")
        command = self.native.buffer(len(command_raw), command_raw)
        environment_buffer = self.native.buffer(len(environment_raw), environment_raw)
        directory = self.native.buffer(len(_ROOT.encode("utf-16-le")) + 2, _ROOT.encode("utf-16-le") + b"\0\0")
        startup = self.native.types["STARTUPINFOEXW"]()
        startup.StartupInfo.cb = 112
        startup.StartupInfo.dwFlags = 256
        startup.StartupInfo.hStdInput = self.owned["child_stdin_read"]
        startup.StartupInfo.hStdOutput = self.owned["stdout_write"]
        startup.StartupInfo.hStdError = self.owned["stderr_write"]
        startup.lpAttributeList = ctypes.addressof(self.attributes)
        process = self.native.types["PROCESS_INFORMATION"]()
        self.creation.update(attempted=True, creation_flags_u32=134743044, command_utf16le_hex=command_raw.hex(), environment_utf16le_hex=environment_raw.hex())
        returned, row = self.native.call("CreateProcessW", self.native.pointer(application, "utf16_z"), self.native.pointer(command, "utf16_mutable_z"), self.native.pointer(None, "none"), self.native.pointer(None, "none"), 1, 134743044, self.native.pointer(environment_buffer, "utf16_environment"), self.native.pointer(directory, "utf16_z"), self.native.pointer(startup, "startupinfoexw"), self.native.pointer(process, "process_information"), valid=lambda value, _error: {"lpProcessInformation": (24, 24, "process_information")} if value else {})
        self.creation.update(create_bool_i32=returned, win32_error_u32=row["return"]["win32_error_u32"])
        _require(returned != 0, "query_failure")
        self.birth = row["started_monotonic_ns"]
        self.work_end = self.birth + 12000000000
        _require(process.hProcess is not None and process.hProcess > 0 and process.hThread is not None and process.hThread > 0 and process.dwProcessId > 0 and process.dwThreadId > 0)
        self.owned["process"] = process.hProcess
        self.owned["thread"] = process.hThread
        self.creation.update(process_handle_u64=process.hProcess, thread_handle_u64=process.hThread, child_pid=process.dwProcessId, child_tid=process.dwThreadId)
        self._event("created_suspended", (row["ordinal"],))
        for role in ("child_stdin_read", "stdout_write", "stderr_write"):
            self._close(role)
        times = self.native.process_times(self.owned["process"])
        self.creation["child_creation_filetime_u64"] = times[0]
        self.creation["observed_image_utf16le_hex"] = self.native.process_image(self.owned["process"])
        if self.case == "suspended_identity_refusal":
            expected = self.protocol["raw_byte_recipes"]["fault_image_utf16"]["text"].encode("utf-16-le").hex()
            self._event("identity_checked")
            self._fault("identity_checked", {"kind": "expected_image_override", "expected_image_utf16le_hex": expected}, calls=1)
            _require(self.creation["observed_image_utf16le_hex"] != expected)
            self._choose("identity_refusal", "expected_image_mismatch")
            return False
        _require(self.creation["observed_image_utf16le_hex"] == self.runtime["interpreter"]["path"].encode("utf-16-le").hex(), "identity_mismatch")
        self._event("identity_checked")
        suspended = self._job_query("suspended")
        if self.case == "suspended_membership_refusal":
            self._event("membership_checked")
            self._fault("membership_checked", {"kind": "expected_membership_override", "expected_process_ids": []}, calls=1)
            _require(suspended["process_ids"] != [])
            self._choose("membership_refusal", "expected_membership_mismatch")
            return False
        _require(suspended["process_ids"] == [self.creation["child_pid"]] and suspended["accounting"]["active_processes_u32"] == 1, "identity_mismatch")
        self._event("membership_checked")
        return True

    def _fault(self, stage, supplied, actual_row=None, calls=0):
        self.fault = {"version": "local-member-intake-bootstrap-fault-v1", "case_id": self.case, "registration_sha256": self.registration_sha, "packet_sha256": _hash(self.raw), "site": self.packet["control"]["fault_site"], "trigger_stage": stage, "original_call_count": calls, "actual_api_ordinal": None if actual_row is None else actual_row["ordinal"], "actual_return": None if actual_row is None else actual_row["return"], "supplied_observation": supplied, "restoration_complete": True}
        _with_hash(self.fault, "fault_sha256")

    def _rendezvous(self):
        command_bytes = bytes.fromhex(self.creation["command_utf16le_hex"])
        _require(command_bytes[-2:] == b"\0\0" and command_bytes[-4:-2] != b"\0\0")
        request = {"version": "local-intake-identity-request-v1", "registration_sha256": self.registration_sha, "case_id": self.case, "nonce_hex": self.packet["nonce_hex"], "packet_sha256": _hash(self.raw), "host": self.self_request, "worker": {"pid": self.creation["child_pid"], "creation_filetime_u64": self.creation["child_creation_filetime_u64"], "image_utf16le_hex": self.creation["observed_image_utf16le_hex"], "command_utf16le_hex": command_bytes[:-2].hex()}, "job_process_ids": [self.creation["child_pid"]]}
        _with_hash(request, "request_sha256")
        raw = _canonical(request)
        _require(len(raw) <= 262144, "budget")
        self.creation["identity_transport"]["request"] = request
        self.native.write(self.host_stdout, b"LMR1" + struct.pack("<I", len(raw)) + raw)
        ack_end = min(self.work_end, time.monotonic_ns() + 3000000000)
        captured = bytearray()
        expected = None
        while True:
            self._remaining(ack_end)
            available, eof, _ = self.native.peek(self.host_stdin)
            if available:
                requested = min(available, 65536, 524297 - len(captured))
                _require(requested > 0, "transport")
                data, _row, count = self.native.read(self.host_stdin, requested)
                _require(data is not None and count is not None and count > 0, "transport")
                captured.extend(data)
                _require(len(captured) <= 524296, "transport")
                if len(captured) >= 8 and expected is None:
                    _require(captured[:4] == b"LMA1", "transport")
                    body_length = struct.unpack("<I", captured[4:8])[0]
                    _require(1 <= body_length <= 524288, "transport")
                    expected = body_length + 8
                if expected is not None:
                    _require(len(captured) <= expected, "transport")
            elif eof:
                _require(expected is not None and len(captured) == expected, "transport")
                break
            else:
                time.sleep(min(0.02, self._remaining(ack_end) / 1000000000))
        ack = _parse(bytes(captured[8:]), 524288, True)
        self.creation["identity_transport"]["ack"] = ack
        _schema(ack, "IdentityAck", self.protocol)
        _own_hash(ack, "ack_sha256")
        _require(ack["registration_sha256"] == self.registration_sha and ack["case_id"] == self.case and ack["nonce_hex"] == self.packet["nonce_hex"] and ack["request_sha256"] == request["request_sha256"], "identity_mismatch")
        _require(ack["decision"] == "allow" and ack["failure_code"] is None and len(ack["observations"]) == 3, "identity_mismatch")
        actors = []
        previous_end = 0
        for role, observation in zip(("observer", "host", "worker"), ack["observations"]):
            _require(observation["role"] == role and observation["state"] == "complete" and observation["error"] is None and observation["excess_observed"] is False and len(observation["selected_instances"]) == 1, "identity_mismatch")
            _require(observation["ended_monotonic_ns"] is not None and previous_end <= observation["started_monotonic_ns"] <= observation["ended_monotonic_ns"], "timestamp")
            previous_end = observation["ended_monotonic_ns"]
            actor = observation["selected_instances"][0]
            _require(observation["query_text"] == _query_text(actor["process_id"]) and observation["query_sha256"] == _hash(observation["query_text"].encode("utf-8")), "identity_mismatch")
            _require(actor["executable_path_utf16le_hex"] is not None and actor["command_line_utf16le_hex"] is not None and actor["creation"] is not None, "identity_mismatch")
            _require(len(actor["executable_path_utf16le_hex"]) <= 2048 and len(actor["command_line_utf16le_hex"]) <= (131072 if role == "observer" else 98304), "budget")
            filetime = _date_filetime(actor["creation"])
            _require(actor["creation"]["quantum_100ns"] == 10, "timestamp")
            if role != "observer":
                expected_actor = request[role]
                _require(actor["process_id"] == expected_actor["pid"] and actor["executable_path_utf16le_hex"] == expected_actor["image_utf16le_hex"] and actor["command_line_utf16le_hex"] == expected_actor["command_utf16le_hex"] and filetime // 10 == expected_actor["creation_filetime_u64"] // 10, "identity_mismatch")
            actors.append(actor)
        observer, host, worker = actors
        _require(host["parent_process_id"] == observer["process_id"] and worker["parent_process_id"] == host["process_id"], "identity_mismatch")
        _require(observer["creation"]["filetime_u64"] <= host["creation"]["filetime_u64"] <= worker["creation"]["filetime_u64"], "timestamp")
        self.parent_identity.update(observation_state="complete", creator_pid=observer["process_id"], creator_creation_filetime_u64=observer["creation"]["filetime_u64"])
        self.creation.update(observed_parent_pid=worker["parent_process_id"], parent_observation_method=self.registration["binding_contract"]["parent_observation_method"], cim_observations=ack["observations"])
        membership = self._job_query("suspended")
        _require(membership["process_ids"] == [self.creation["child_pid"]] and membership["accounting"]["active_processes_u32"] == 1, "identity_mismatch")
        return ack

    def _drain(self, role):
        data = self.stdout_data if role == "stdout" else self.stderr_data
        eof_name = "stdout_eof" if role == "stdout" else "stderr_eof"
        excess_name = "stdout_excess" if role == "stdout" else "stderr_excess"
        ordinals = self.stdout_ordinals if role == "stdout" else self.stderr_ordinals
        if getattr(self, eof_name) or getattr(self, excess_name):
            return
        cap = 4194312
        if role == "stdout" and self.case in ("result_exact_limit", "result_first_excess"):
            cap = 1048584
        available, eof, _ = self.native.peek(self.owned[role + "_read"])
        if eof:
            setattr(self, eof_name, True)
            return
        if not available:
            return
        aggregate_remaining = 4194313 - len(self.stdout_data) - len(self.stderr_data)
        requested = min(available, 65536, cap + 1 - len(data), aggregate_remaining)
        _require(requested > 0, "budget")
        returned, row, count = self.native.read(self.owned[role + "_read"], requested)
        ordinals.append(row["ordinal"])
        _require(returned is not None and count is not None and count > 0, "transport")
        data.extend(returned)
        self._event("output_read", (row["ordinal"],))
        if len(data) > cap:
            setattr(self, excess_name, True)

    def _ready_and_go(self, ack):
        while len(self.stdout_data) < 8:
            self._remaining()
            self._drain("stdout")
            self._drain("stderr")
            _require(not self.stdout_eof and not self.stderr_data, "transport")
            time.sleep(min(0.02, self._remaining() / 1000000000))
        _require(bytes(self.stdout_data) == _READY, "transport")
        transport = self.creation["identity_transport"]
        transport["ready_hex"] = _READY.hex()
        transport["ready_read_api_ordinals"] = list(self.stdout_ordinals)
        for _ in range(2):
            self.native.snapshot("worker", self.owned["process"], self.creation["child_pid"], self.creation["child_creation_filetime_u64"], len(self.module_observations))
        _require(_snapshot_identity(self.module_observations[-2]) == _snapshot_identity(self.module_observations[-1]), "identity_mismatch")
        raw = _GO_MAGIC + struct.pack("<II", self.self_request["pid"], self.creation["child_pid"]) + bytes.fromhex(ack["ack_sha256"])
        _require(len(raw) == 48)
        transport["go_hex"] = raw.hex()
        transport["go_write_api_ordinals"] = self.native.write(self.owned["child_stdin_write"], raw)
        close = self._close("child_stdin_write")
        transport["child_stdin_parent_closes"] = [row for row in self.parent_closes if row["role"] in ("child_stdin_read", "child_stdin_write")]
        _require(close["disposition"] == "closed")

    def _marker(self):
        if self.case != "blocked_owned_pipe_read" or not self.stdout_data.startswith(_READY) or len(self.stdout_data) == 8:
            return False
        try:
            marker = _parse(bytes(self.stdout_data[8:]), 262144, True)
        except BootstrapFailure:
            return False
        _schema(marker, "PendingReadMarker", self.protocol)
        _own_hash(marker, "marker_sha256")
        _require(marker["case_id"] == self.case and marker["packet_sha256"] == _hash(self.raw) and marker["nonce_hex"] == self.packet["nonce_hex"] and marker["worker_pid"] == self.creation["child_pid"] and marker["observed_parent_pid"] == self.self_request["pid"] and marker["authority_flags"] == self.packet["authority_flags"], "identity_mismatch")
        _require(marker["go_observation"]["packet_hex"] == self.creation["identity_transport"]["go_hex"], "identity_mismatch")
        self._worker_observation(marker["completed_api_trace"], marker["go_observation"])
        return True

    def _worker_observation(self, trace, go):
        """Join complete transported worker calls, rather than trusting labels."""
        _require(type(trace) is list and 99 <= len(trace) <= 4096)
        contracts = self.native.contracts
        for ordinal, row in enumerate(trace):
            _schema(row, "ApiTrace", self.protocol)
            _require(row["ordinal"] == ordinal and row["started_monotonic_ns"] <= row["ended_monotonic_ns"])
            contract = contracts.get(row["api"])
            _require(contract is not None and row["source_selector"] == contract["source_selector"])
            _require(row["return"]["kind"] == contract["return_kind"] and len(row["arguments"]) == len(contract["parameters"]))
            allocated = []
            for argument, parameter in zip(row["arguments"], contract["parameters"]):
                _require(argument["name"] == parameter[0] and argument["kind"] == parameter[2])
                if argument["kind"] == "pointer":
                    pointer = argument["value"]
                    if pointer["storage_before_hex"] is not None:
                        _require(pointer["address_u64"] > 0 and len(_hex(pointer["storage_before_hex"], 65536)) == pointer["storage_bytes_u32"])
                        allocated.append((argument["name"], pointer["storage_bytes_u32"]))
            _require([(value["parameter"], value["capacity_bytes"]) for value in row["output_buffers"]] == allocated)
            for buffer in row["output_buffers"]:
                _require(len(_hex(buffer["full_buffer_hex"], 65536)) == buffer["capacity_bytes"])
                if buffer["output_validity"] == "storage_only":
                    _require(buffer["returned_bytes"] is None and buffer["valid_prefix_bytes"] is None and buffer["projection_kind"] == "none")
                else:
                    _require(buffer["returned_bytes"] is not None and buffer["valid_prefix_bytes"] is not None and buffer["returned_bytes"] <= buffer["capacity_bytes"] and buffer["valid_prefix_bytes"] <= buffer["capacity_bytes"])
            if row["api"] == "GetFileType":
                _require(row["saved_error_seed"] is not None and row["saved_error_seed"]["input_i32"] == 0)
            else:
                _require(row["saved_error_seed"] is None)
        _require(len(go["initialization"]) == 1 and go["initialization"][0]["owner_role"] == "worker" and go["initialization"][0]["completed"] is True)
        _require([row["api_name"] for row in go["binding_initialization"]] == self.registration["runtime_contract"]["binding_order"])
        for ordinal, binding in enumerate(go["binding_initialization"]):
            _require(binding["ordinal"] == ordinal and binding["owner_role"] == "worker" and binding["constructor_ordinal"] == 0 and binding["completed"] is True and binding["exception"] is None)
            resolver, owner, path = trace[3 * ordinal:3 * ordinal + 3]
            _require([row["api"] for row in (resolver, owner, path)] == ["GetProcAddress", "GetModuleHandleExW", "GetModuleFileNameW"])
            _require(resolver["return"]["raw_u64"] == binding["exposed_address_u64"] and resolver["return"]["win32_error_u32"] is None)
            _require(owner["return"]["raw_i64"] != 0 and owner["arguments"][0]["value"] == 6 and owner["arguments"][1]["value"]["address_u64"] == binding["exposed_address_u64"])
            count = path["return"]["raw_u64"]
            _require(1 <= count <= 511)
            storage = _hex(path["output_buffers"][0]["full_buffer_hex"], 1024)
            _require(storage[2 * count:2 * count + 2] == b"\0\0")
            observed = storage[:2 * count].decode("utf-16-le", errors="strict")
            registration = next(value for value in self.runtime["exports"] if value["role"] == "worker" and value["export_name"] == binding["api_name"])
            _require(observed in registration["allowed_owner_paths"], "identity_mismatch")
        pieces = []
        offset = 0
        stdin = None
        for ordinal, read in enumerate(go["data_reads"]):
            row = trace[read["api_ordinal"]]
            _require(row["api"] == "ReadFile" and read["ordinal"] == ordinal and read["offset_u32"] == offset and read["requested_count_u32"] == 48 - offset)
            _require(read["return"] == row["return"] and read["buffer_observations"] == row["output_buffers"] and row["return"]["raw_i64"] != 0)
            count = read["returned_count_u32"]
            _require(type(count) is int and 1 <= count <= 48 - offset and row["arguments"][2]["value"] == 48 - offset)
            handle = row["arguments"][0]["value"]
            _require(stdin is None or stdin == handle)
            stdin = handle
            _require(int.from_bytes(_hex(row["output_buffers"][1]["full_buffer_hex"], 4), "little") == count)
            pieces.append(_hex(row["output_buffers"][0]["full_buffer_hex"], 48)[:count])
            offset += count
        _require(offset == 48 and b"".join(pieces).hex() == go["packet_hex"], "identity_mismatch")
        eof = go["eof_probe"]
        row = trace[eof["api_ordinal"]]
        _require(eof["ordinal"] == len(go["data_reads"]) and eof["offset_u32"] == 48 and eof["requested_count_u32"] == 1 and eof["returned_count_u32"] is None)
        _require(row["api"] == "ReadFile" and row["arguments"][0]["value"] == stdin and row["arguments"][2]["value"] == 1 and row["return"]["raw_i64"] == 0 and row["return"]["win32_error_u32"] == 109)
        _require(eof["return"] == row["return"] and eof["buffer_observations"] == row["output_buffers"] and all(value["output_validity"] == "storage_only" for value in row["output_buffers"]))
        close = go["stdin_close"]
        _require(close["ordinal"] == 0 and close["role"] == "control_stdin_read" and close["handle_u64"] == stdin and close["close_attempted"] is True and close["disposition"] == "closed")
        matches = [row for row in trace if row["api"] == "CloseHandle" and row["arguments"][0]["value"] == stdin]
        _require(len(matches) == 1 and matches[0]["return"]["raw_i64"] == close["close_bool_i32"] != 0 and matches[0]["return"]["win32_error_u32"] == close["win32_error_u32"])

    def _collect(self):
        marker_observed = False
        while True:
            self._drain("stdout")
            self._drain("stderr")
            if self.stdout_excess:
                if self.case == "result_first_excess":
                    self._choose("result_limit_refusal", "result_bytes")
                elif self.case == "diagnostic_first_excess":
                    self._choose("output_limit_refusal", "diagnostic_bytes")
                else:
                    self._choose("failed_control", "diagnostic_bytes", "failed_control")
                return
            _require(not self.stderr_excess, "diagnostic_bytes")
            if self.case == "blocked_owned_pipe_read" and not marker_observed:
                marker_observed = self._marker()
            remaining = min(self.work_end - time.monotonic_ns(), _HARD_END_NS - time.time_ns())
            if remaining <= 0:
                _require(self.case in ("initialization_stall", "wall_stall", "blocked_owned_pipe_read"), "work_deadline")
                _require(self.case != "blocked_owned_pipe_read" or marker_observed, "transport")
                self._choose("work_timeout", "work_deadline")
                return
            wait_ms = min(20, max(0, remaining // 1000000))
            wait, row = self.native.call("WaitForSingleObject", self.owned["process"], wait_ms)
            _require(wait in (0, 258), "query_failure")
            if wait == 0:
                self.terminal["wait_result_u32"] = 0
                self._event("process_signalled", (row["ordinal"],))
                if self.stdout_eof and self.stderr_eof:
                    break
        self._interpret()

    def _interpret(self):
        exit_code = ctypes.c_uint32()
        self.native.require_call("GetExitCodeProcess", self.owned["process"], self.native.pointer(exit_code, "dword_out"), valid=lambda returned, _error: {"lpExitCode": (4, 4, "u32")} if returned else {})
        self.terminal["exit_code_u32"] = exit_code.value
        times = self.native.process_times(self.owned["process"], True)
        self.terminal.update(exit_filetime_u64=times[1], kernel_time_100ns_u64=times[2], user_time_100ns_u64=times[3])
        _require(times[0] == self.creation["child_creation_filetime_u64"], "identity_mismatch")
        if self.case == "cpu_limit":
            _require(exit_code.value != 0 and times[3] >= 50000000 and bytes(self.stdout_data) == _READY and not self.stderr_data, "query_value")
            self._choose("cpu_control_observed")
            return
        if self.case == "crash":
            _require(exit_code.value == 37 and bytes(self.stdout_data) == _READY and not self.stderr_data, "query_value")
            self._choose("child_failure", "child_exit")
            return
        _require(exit_code.value == 0, "child_exit")
        _require(self.stdout_data.startswith(_READY), "transport")
        semantic = bytes(self.stdout_data[8:])
        if self.stderr_data:
            _require(self.case == "unexpected_stderr" and bytes(self.stderr_data) == b"x", "stderr")
            self._choose("transport_refusal", "stderr")
            return
        if self.case == "diagnostic_exact_limit":
            _require(semantic == b"d" * 4194304, "query_value")
            self._choose("transport_boundary_observed")
            return
        if self.case == "result_exact_limit":
            _require(len(semantic) == 1048576 and semantic == _parser_bytes(1048576), "query_value")
            _schema(_parse(semantic, 1048576, True), "ParserControlBody", self.protocol)
            self._choose("result_boundary_observed")
            return
        if self.case in ("invalid_utf8", "duplicate_key", "trailing_json"):
            _require(semantic == bytes.fromhex(self.packet["control"]["literal_hex"]), "query_value")
            reason = {"invalid_utf8": "utf8", "duplicate_key": "duplicate_key", "trailing_json": "trailing_json"}[self.case]
            try:
                _parse(semantic, 1048576, True)
            except BootstrapFailure as error:
                _require(error.reason == reason, "query_value")
            else:
                raise BootstrapFailure("query_value")
            self._choose("transport_refusal", reason)
            return
        result = _parse(semantic, 1048576, True)
        _schema(result, "BootstrapResult", self.protocol)
        _require(result["case_id"] == self.case and result["packet_sha256"] == _hash(self.raw) and result["nonce_hex"] == self.packet["nonce_hex"] and result["worker_pid"] == self.creation["child_pid"] and result["observed_parent_pid"] == self.self_request["pid"] and result["authority_flags"] == self.packet["authority_flags"], "identity_mismatch")
        bundle_raw = _hex(result["payload_hex"], 262144)
        bundle = _parse(bundle_raw, 262144, True)
        _schema(bundle, "ResultPayload", self.protocol)
        _require(bundle["go_observation"]["packet_hex"] == self.creation["identity_transport"]["go_hex"], "identity_mismatch")
        _require(result["worker_cleanup"] == [bundle["go_observation"]["stdin_close"]], "query_value")
        self._worker_observation(result["worker_pre_emission_api_trace"], bundle["go_observation"])
        if self.case in ("memory_limit", "memory_positive_control"):
            memory = _parse(_hex(bundle["control_payload_hex"], 262144), 262144, True)
            _schema(memory, "MemoryControlObservation", self.protocol)
            if self.case == "memory_limit":
                _require(memory["return_address_u64"] == 0 and memory["release"] is None and memory["win32_error_u32"] is not None and result["status"] == "controlled_failure")
                self._choose("memory_control_observed")
            else:
                _require(memory["return_address_u64"] > 0 and memory["release"] is not None and memory["release"]["return_bool_i32"] != 0 and memory["release"]["address_u64"] == memory["return_address_u64"] and result["status"] == "completed")
                self._choose("memory_positive_observed")
        else:
            _require(bundle["control_payload_hex"] == b"bootstrap-ok".hex() and result["status"] == "completed")
            self._choose("completed")
        self.result = result

    def _cleanup(self):
        if self.native is None:
            return
        end = time.monotonic_ns() + 3000000000
        if self.work_end is not None:
            end = min(end, self.work_end + 3000000000)
        if self.owned.get("process"):
            wait, row = self.native.call("WaitForSingleObject", self.owned["process"], 0)
            _require(wait in (0, 258), "query_failure")
            if wait == 258:
                self.terminal["termination_requested"] = True
                returned, row = self.native.call("TerminateJobObject", self.owned["job"], 3758096455)
                self.terminal["termination_return"] = row["return"]
                self._event("termination_requested", (row["ordinal"],))
                _require(returned != 0, "query_failure")
                while True:
                    remaining = self._remaining(end)
                    wait, row = self.native.call("WaitForSingleObject", self.owned["process"], min(20, max(0, remaining // 1000000)))
                    _require(wait in (0, 258), "query_failure")
                    if wait == 0:
                        break
            self.terminal["wait_result_u32"] = 0
            self._event("process_signalled", (row["ordinal"],))
            exit_code = ctypes.c_uint32()
            self.native.require_call("GetExitCodeProcess", self.owned["process"], self.native.pointer(exit_code, "dword_out"), valid=lambda returned, _error: {"lpExitCode": (4, 4, "u32")} if returned else {})
            times = self.native.process_times(self.owned["process"], True)
            self.terminal.update(exit_code_u32=exit_code.value, exit_filetime_u64=times[1], kernel_time_100ns_u64=times[2], user_time_100ns_u64=times[3])
            if self.creation["child_creation_filetime_u64"] is not None:
                _require(times[0] == self.creation["child_creation_filetime_u64"], "identity_mismatch")
            while not ((self.stdout_eof or self.stdout_excess) and (self.stderr_eof or self.stderr_excess)):
                self._remaining(end)
                self._drain("stdout")
                self._drain("stderr")
                if not ((self.stdout_eof or self.stdout_excess) and (self.stderr_eof or self.stderr_excess)):
                    time.sleep(min(0.02, self._remaining(end) / 1000000000))
            if self.terminal["termination_requested"]:
                _require(exit_code.value == 3758096455, "child_exit")
        if self.owned.get("job"):
            while True:
                observation = self._job_query("terminal")
                if observation["process_ids"] == [] and observation["accounting"]["active_processes_u32"] == 0:
                    self.terminal["final_job_empty"] = True
                    self._event("job_empty_final", (observation["limits_api_ordinal"], observation["accounting_api_ordinal"], observation["process_list_api_ordinal"]))
                    break
                self._remaining(end)
                time.sleep(min(0.02, self._remaining(end) / 1000000000))
        if self.attributes_initialized:
            self.native.call("DeleteProcThreadAttributeList", self.native.pointer(self.attributes, "opaque_attribute_list"))
            self.attributes_initialized = False
        for role in ("child_stdin_read", "child_stdin_write", "stdout_write", "stderr_write", "stdout_read", "stderr_read", "thread", "process", "job"):
            if self.owned.get(role):
                close = self._close(role)
                if role == "stdout_read" and self.case == "close_refusal":
                    actual = self.native.trace[close["close_api_ordinal"]]
                    self._fault("handle_closed", {"kind": "close_observation_override", "close_bool_i32": 0, "win32_error_u32": 1234}, actual, 1)
                    self._choose("injected_refusal", "injected_close_observation")
        self.terminal["cleanup_complete"] = self.terminal["final_job_empty"] is True and all(row["disposition"] == "closed" for row in self.parent_closes) and not any(value is not None for value in self.owned.values()) and not self.attributes_initialized
        _require(self.terminal["cleanup_complete"] is True, "query_failure")
        for _ in range(2):
            self.native.snapshot("host", self.self_handle, self.self_request["pid"], self.self_request["creation_filetime_u64"], len(self.module_observations))
        _require(_snapshot_identity(self.module_observations[-2]) == _snapshot_identity(self.module_observations[-1]), "identity_mismatch")

    def _stream(self, role):
        data = bytes(self.stdout_data if role == "stdout" else self.stderr_data)
        eof = self.stdout_eof if role == "stdout" else self.stderr_eof
        excess = self.stdout_excess if role == "stdout" else self.stderr_excess
        return {"retained_hex": data.hex(), "retained_byte_count": len(data), "retained_sha256": _hash(data), "observed_byte_count_lower_bound": len(data), "complete": eof is True and excess is False, "eof_observed": eof, "excess_sentinel_observed": excess, "read_api_ordinals": self.stdout_ordinals if role == "stdout" else self.stderr_ordinals}

    def _receipt(self):
        self._event("finished")
        result = {"version": "local-member-intake-bootstrap-attempt-v3", "case_id": self.case, "packet": self.packet, "packet_sha256": _hash(self.raw), "registration_sha256": self.registration_sha, "oracle_sha256": self.oracle_sha, "declared_policy": self.policy, "runtime_pins": _runtime_pins(self.context, self.sources, self.runtime), "parent_identity": self.parent_identity, "creation": self.creation, "job_observations": self.job_observations, "api_trace": [] if self.native is None else self.native.trace, "lifecycle": self.lifecycle, "stdout": self._stream("stdout") if self.creation["child_pid"] is not None else None, "stderr": self._stream("stderr") if self.creation["child_pid"] is not None else None, "result": self.result, "fault_observation": self.fault, "terminal": self.terminal, "authority_flags": self.protocol["authority_flags"]}
        _budget_receipt(result)
        _with_hash(result, "receipt_sha256")
        _schema(result, "BootstrapAttemptReceipt", self.protocol)
        raw = _canonical(result)
        _require(len(raw) <= 67108864, "budget")
        return raw

    def run(self):
        # The selected proof recipes are externally bound before this program.
        # This parse selects only the receipt label after actual packet admission.
        try:
            admitted = self.helpers["contract"].admit_packet(self.raw, expected_packet_sha256=self.context["expected_packet_sha256"], registration_sha256=self.registration_sha, protocol_sha256=self.protocol_sha, oracle_sha256=self.oracle_sha, now_unix_ns=time.time_ns())
        except self.helpers["contract"].BootstrapRefusal as error:
            # The first-excess bytes intentionally are not a JSON document.
            # Select only the externally bound context's registered case label;
            # never parse past the length refusal to manufacture that label.
            selected = [row for row in self.registration["control_schedule"] if row["contexts"]["worker"] == self.context["worker_context"]["path"]]
            _require(len(selected) == 1, "packet_context")
            self.case = selected[0]["case_id"]
            reasons = {"packet_first_excess": "packet_length", "packet_wrong_pin": "packet_pin", "unknown_control": "packet_control"}
            _require(self.case in reasons and error.reason == reasons[self.case], "packet_context")
            self.policy = _declared_policy(self.protocol, self.case)
            self._choose("preflight_refusal", error.reason)
            return self._receipt()
        self.packet = admitted
        self.case = self.packet["case_id"]
        self.policy = _declared_policy(self.protocol, self.case)
        _require(_canonical(self.packet["authority_flags"]) == _canonical(self.protocol["authority_flags"]), "authority_flags")
        try:
            self._prepare()
            if self.case == "creation_refusal":
                self._fault("attributes_ready", {"kind": "pre_call_refusal", "reason": "injected_creation_refusal"})
                self._choose("injected_refusal", "injected_creation_refusal")
            elif self._create():
                ack = self._rendezvous()
                if self.case == "resume_refusal":
                    self._fault("membership_checked", {"kind": "pre_call_refusal", "reason": "injected_resume_refusal"})
                    self._choose("injected_refusal", "injected_resume_refusal")
                else:
                    self._remaining()
                    count, row = self.native.call("ResumeThread", self.owned["thread"])
                    self.creation["resume_count_u32"] = count
                    _require(count == 1, "query_failure")
                    self._event("resumed", (row["ordinal"],))
                    # Before GO, even immediate crash/raw controls still wait.
                    # A post-GO singleton query would race their legitimate exit.
                    observation = self._job_query("resumed")
                    _require(observation["process_ids"] == [self.creation["child_pid"]] and observation["accounting"]["active_processes_u32"] == 1, "identity_mismatch")
                    if self.case != "initialization_stall":
                        self._ready_and_go(ack)
                    self._collect()
        except BootstrapFailure as error:
            self._choose("failed_control", error.reason, "failed_control")
        finally:
            try:
                self._cleanup()
            except BootstrapFailure as error:
                self._choose("incomplete", error.reason, "incomplete")
                self.terminal["cleanup_complete"] = False
                self._unattempted_closes()
        return self._receipt()


def _budget_receipt(receipt):
    """Conservative complete occurrence accounting, not a parent RAM claim."""
    counts = {"D": 0, "B": 0, "H": 0}
    def visit(value, key=None):
        if type(value) is dict:
            for name, body in value.items():
                visit(body, name)
        elif type(value) is list:
            for item in value:
                visit(item)
        elif type(value) is str and key is not None and key.endswith("_hex"):
            raw = _hex(value, 67108864)
            category = "D" if key == "retained_hex" else "B" if key in ("storage_before_hex", "full_buffer_hex") else "H"
            counts[category] += len(raw)
            if key == "payload_hex" and raw:
                visit(_parse(raw, 262144, True))
    visit(receipt)
    def metadata(value):
        if type(value) is dict:
            return {name: (None if name == "result" else "" if name.endswith("_hex") and type(body) is str else metadata(body)) for name, body in value.items()}
        if type(value) is list:
            return [metadata(body) for body in value]
        return value
    result_size = 0 if receipt["result"] is None else len(_canonical(receipt["result"]))
    metadata_size = len(_canonical(metadata(receipt)))
    _require(counts["D"] <= 4194313 and counts["B"] <= 12582912 and counts["H"] <= 2097152 and result_size <= 1048576 and metadata_size <= 8388608, "budget")
    _require(2 * counts["D"] + 2 * counts["B"] + 2 * counts["H"] + result_size + metadata_size <= 47185938, "budget")


def main():
    _require(len(sys.argv) == 3, "packet_context")
    loaded = _load_inputs(sys.argv[1], sys.argv[2])
    host = Host(loaded, sys.argv[1], sys.argv[2])
    body = host.run()
    frame = b"LMF1" + struct.pack("<I", len(body)) + body
    if host.native is None:
        # Pure packet refusals do not initialize WinDLL merely to emit evidence.
        for offset in range(0, len(frame), 65536):
            chunk = frame[offset:offset + 65536]
            written = sys.stdout.buffer.write(chunk)
            _require(type(written) is int and written == len(chunk), "transport")
        sys.stdout.buffer.flush()
    else:
        host.native.write(host.host_stdout, frame, sealed=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())



