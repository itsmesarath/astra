"""Measure complete submitted Worker trees without executing their producers.

The fixed structural subset comes from the reviewed 2026-10-16 occurrence
contract and the held P3/Worker source texts.  This is not a P3 semantic reader,
native observation, ownership certificate, cleanup proof, or runtime governor.
"""

import json

_U32 = (1 << 32) - 1
_U64 = (1 << 64) - 1
_I32_MIN = -(1 << 31)
_I32_MAX = (1 << 31) - 1
_I64_MIN = -(1 << 63)
_I64_MAX = (1 << 63) - 1
_WORK_BYTES = 67108864
_WORK_NODES = 1048576
_WORK_ITEMS = 65536
_WORK_DEPTH = 64
_REASONS = ("input", "shape", "hex", "unsupported", "work")
_CONTAINERS = ("BootstrapResult", "PendingReadMarker", "ResultPayload")
_PROTOCOL_SHA = "2252ebefe2d38b14f5c915b3a1b9fbb2c8bc960a02477372bb1dd0ea7114c31f"
_WORKER_SHA = "7adaf7f42fc97a0221bf792ff657c6f23b625355e348697301bdfcd9d5d00279"
_INITIALIZATION_SELECTOR = "R15/cpython_31210_ctypes_init.py.txt:CDLL.__init__/WinDLL"
_BINDING_SELECTOR = "R15/cpython_31210_ctypes_init.py.txt:CDLL.__getitem__/_FuncPtr"

# P3 AuthorityFlags literal; every destination receives fresh mutable pairs.
_FLAG_NAMES = (
    "source_authenticated",
    "collection_receipt_authenticated",
    "native_runtime_authenticated",
    "native_abi_authenticated",
    "native_wire_authenticated",
    "native_header_authenticated",
    "native_eof_authenticated",
    "feed_authenticated",
    "calendar_authenticated",
    "historical_read_authorized",
    "historical_validation_authorized",
    "book_acceptance_authorized",
    "event_acceptance_authorized",
    "feature_acceptance_authorized",
    "account_authorized",
    "funding_authorized",
    "receipt_authorized",
    "cash_authorized",
    "margin_authorized",
    "risk_authorized",
    "storage_authorized",
    "resume_authorized",
    "execution_authorized",
    "trading_authorized",
    "training_authorized",
    "scoring_authorized",
    "independent_validation_authorized",
    "promotion_authorized",
)
_NOT_VALIDATED = (
    "P3_rules",
    "native_execution",
    "clock_ordinal_return_GO_associations",
    "cross_copy_associations",
    "payload_JSON",
    "ownhash_correctness",
    "source_reachability",
    "owner_cleanup_state",
    "protected_continuation",
    "source_runtime_authentication",
)

# R3 runtime_contract.binding_order, not an assertion that this sequence ran.
_BINDING_NAMES = (
    "CreateJobObjectW",
    "SetInformationJobObject",
    "QueryInformationJobObject",
    "InitializeProcThreadAttributeList",
    "UpdateProcThreadAttribute",
    "DeleteProcThreadAttributeList",
    "CreateProcessW",
    "ResumeThread",
    "WaitForSingleObject",
    "GetProcessTimes",
    "GetExitCodeProcess",
    "QueryFullProcessImageNameW",
    "GetCurrentProcess",
    "GetCurrentProcessId",
    "TerminateJobObject",
    "CreatePipe",
    "PeekNamedPipe",
    "ReadFile",
    "WriteFile",
    "GetStdHandle",
    "GetFileType",
    "GetHandleInformation",
    "SetHandleInformation",
    "CloseHandle",
    "LoadLibraryExW",
    "GetProcAddress",
    "GetModuleHandleExW",
    "GetModuleFileNameW",
    "K32EnumProcessModulesEx",
    "K32GetModuleFileNameExW",
    "FreeLibrary",
    "VirtualAlloc",
    "VirtualFree",
)
_PROJECTIONS = (
    "u32",
    "u64",
    "handle_u64",
    "filetime_u64",
    "process_information",
    "job_extended_limits",
    "job_accounting",
    "job_pid_list",
    "utf16_z",
    "module_array",
    "byte_prefix",
    "opaque_attribute_list",
    "none",
)

# (name, argument kind, pointee kind, extent, fixed scalar).  The string extent
# "request" refers only to the corresponding fixed-position scalar in this table.
# Source selectors and parameter order are transcribed from P3 ApiContracts.
_CALLS = {
    "GetProcAddress": (
        "handle64",
        "R15/libloaderapi_nf-libloaderapi-getprocaddress.md:GetProcAddress",
        (
            ("hModule", "handle64", None, None, None),
            ("lpProcName", "pointer", "ascii_z", (2, 129), None),
        ),
    ),
    "GetModuleHandleExW": (
        "bool32",
        "R15/libloaderapi_nf-libloaderapi-getmodulehandleexw.md:GetModuleHandleExW",
        (
            ("dwFlags", "u32", None, None, 6),
            ("lpModuleName", "pointer", "external_function_address", 0, None),
            ("phModule", "pointer", "handle_out", 8, None),
        ),
    ),
    "GetModuleFileNameW": (
        "dword32",
        "R15/libloaderapi_nf-libloaderapi-getmodulefilenamew.md:GetModuleFileNameW",
        (
            ("hModule", "handle64", None, None, None),
            ("lpFilename", "pointer", "utf16_mutable_z", 1024, None),
            ("nSize", "u32", None, None, 512),
        ),
    ),
    "GetStdHandle": (
        "handle64",
        "R15/fixed_getstdhandle.md:GetStdHandle",
        (("nStdHandle", "u32", None, None, (4294967286, 4294967285, 4294967284)),),
    ),
    "GetFileType": (
        "dword32",
        "R14/api_09_nf-fileapi-getfiletype.md:GetFileType",
        (("hFile", "handle64", None, None, None),),
    ),
    "GetHandleInformation": (
        "bool32",
        "R15/handleapi_nf-handleapi-gethandleinformation.md:GetHandleInformation",
        (("hObject", "handle64", None, None, None), ("lpdwFlags", "pointer", "dword_out", 4, None)),
    ),
    "WriteFile": (
        "bool32",
        "R15/extra_nf-fileapi-writefile.md:WriteFile",
        (
            ("hFile", "handle64", None, None, None),
            ("lpBuffer", "pointer", "byte_buffer", "request", None),
            ("nNumberOfBytesToWrite", "u32", None, None, None),
            ("lpNumberOfBytesWritten", "pointer", "dword_out", 4, None),
            ("lpOverlapped", "pointer", "none", 0, None),
        ),
    ),
    "PeekNamedPipe": (
        "bool32",
        "R15/namedpipeapi_nf-namedpipeapi-peeknamedpipe.md:PeekNamedPipe",
        (
            ("hNamedPipe", "handle64", None, None, None),
            ("lpBuffer", "pointer", "none", 0, None),
            ("nBufferSize", "u32", None, None, 0),
            ("lpBytesRead", "pointer", "none", 0, None),
            ("lpTotalBytesAvail", "pointer", "dword_out", 4, None),
            ("lpBytesLeftThisMessage", "pointer", "dword_out", 4, None),
        ),
    ),
    "ReadFile": (
        "bool32",
        "R14/api_01_nf-fileapi-readfile.md:ReadFile",
        (
            ("hFile", "handle64", None, None, None),
            ("lpBuffer", "pointer", "byte_buffer", "request", None),
            ("nNumberOfBytesToRead", "u32", None, None, None),
            ("lpNumberOfBytesRead", "pointer", "dword_out", 4, None),
            ("lpOverlapped", "pointer", "none", 0, None),
        ),
    ),
    "GetCurrentProcessId": (
        "dword32",
        "R15/extra_nf-processthreadsapi-getcurrentprocessid.md:GetCurrentProcessId",
        (),
    ),
    "CloseHandle": (
        "bool32",
        "R14/api_10_nf-handleapi-closehandle.md:CloseHandle",
        (("hObject", "handle64", None, None, None),),
    ),
    "VirtualAlloc": (
        "handle64",
        "R15/extra_nf-memoryapi-virtualalloc.md:VirtualAlloc",
        (
            ("lpAddress", "pointer", "none", 0, None),
            ("dwSize", "u64", None, None, 268435456),
            ("flAllocationType", "u32", None, None, 12288),
            ("flProtect", "u32", None, None, 4),
        ),
    ),
    "VirtualFree": (
        "bool32",
        "R15/extra_nf-memoryapi-virtualfree.md:VirtualFree",
        (
            ("lpAddress", "pointer", "allocation_base", 0, None),
            ("dwSize", "u64", None, None, 0),
            ("dwFreeType", "u32", None, None, 32768),
        ),
    ),
    "CreatePipe": (
        "bool32",
        "R15/namedpipeapi_nf-namedpipeapi-createpipe.md:CreatePipe",
        (
            ("hReadPipe", "pointer", "handle_out", 8, None),
            ("hWritePipe", "pointer", "handle_out", 8, None),
            ("lpPipeAttributes", "pointer", "security_attributes", 24, None),
            ("nSize", "u32", None, None, 65536),
        ),
    ),
    "SetHandleInformation": (
        "bool32",
        "R15/handleapi_nf-handleapi-sethandleinformation.md:SetHandleInformation",
        (
            ("hObject", "handle64", None, None, None),
            ("dwMask", "u32", None, None, 1),
            ("dwFlags", "u32", None, None, 0),
        ),
    ),
}
_H_INPUTS = (
    ("GetProcAddress", "lpProcName"),
    ("WriteFile", "lpBuffer"),
    ("CreatePipe", "lpPipeAttributes"),
)


class WorkerRecordingRefusal(ValueError):
    """Refusal carrying the public accounting-interface reason."""

    def __init__(self, reason):
        if type(reason) is not str or reason not in _REASONS:
            raise ValueError("unknown Worker recording refusal reason")
        self.reason = reason
        super().__init__(reason)


def _refuse(reason):
    raise WorkerRecordingRefusal(reason)


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def _snapshot(body):
    """Copy every mutable occurrence and charge width before any serialization."""
    nodes = 0
    width = 0
    ancestors = set()
    string_widths = {}

    def charge(amount):
        nonlocal width
        if amount > _WORK_BYTES - width:
            _refuse("work")
        width += amount

    def string_width(value):
        # Immutable strings may reuse a scan, but each physical path is charged.
        if len(value) + 2 > _WORK_BYTES - width:
            _refuse("work")
        cached = string_widths.get(id(value))
        if cached is not None:
            charge(cached[1])
            return
        measured = 2
        for character in value:
            code = ord(character)
            if 32 <= code <= 126:
                measured += 2 if code == 34 or code == 92 else 1
            elif code == 8 or code == 9 or code == 10 or code == 12 or code == 13:
                measured += 2
            elif code <= 65535:
                if 55296 <= code <= 57343:
                    _refuse("input")
                measured += 6
            else:
                measured += 12
            if measured > _WORK_BYTES - width:
                _refuse("work")
        string_widths[id(value)] = (value, measured)
        charge(measured)

    def visit(value, depth):
        nonlocal nodes
        if depth > _WORK_DEPTH or nodes == _WORK_NODES:
            _refuse("work")
        nodes += 1
        kind = type(value)
        if value is None:
            charge(4)
            return None
        if kind is bool:
            charge(4 if value else 5)
            return value
        if kind is int:
            if not _I64_MIN <= value <= _U64:
                _refuse("input")
            charge(len(str(value)))
            return value
        if kind is str:
            string_width(value)
            return value
        if kind is not dict and kind is not list:
            _refuse("input")
        size = len(value)
        if size > _WORK_ITEMS:
            _refuse("work")
        identity = id(value)
        if identity in ancestors:
            _refuse("input")
        ancestors.add(identity)
        try:
            charge(2 + max(size - 1, 0))
            if kind is list:
                copied = [visit(item, depth + 1) for item in value]
            else:
                copied = {}
                for key, item in value.items():
                    if type(key) is not str:
                        _refuse("input")
                    string_width(key)
                    charge(1)
                    copied[key] = visit(item, depth + 1)
            if len(copied) != size:
                _refuse("input")
            return copied
        finally:
            ancestors.remove(identity)

    try:
        copied = visit(body, 0)
    except RuntimeError as error:
        # A concurrently changed builtin collection is not a coherent capture.
        raise WorkerRecordingRefusal("input") from error
    return copied, width


def _record(value, keys):
    if type(value) is not dict or len(value) != len(keys):
        _refuse("shape")
    if any(key not in value for key in keys):
        _refuse("shape")


def _sequence(value, minimum, maximum):
    if type(value) is not list or not minimum <= len(value) <= maximum:
        _refuse("shape")


def _integer(value, minimum, maximum, nullable=False):
    if value is None and nullable:
        return
    if type(value) is not int or not minimum <= value <= maximum:
        _refuse("shape")


def _literal(value, expected):
    if type(value) is not type(expected) or value != expected:
        _refuse("shape")


def _token(value, choices):
    if type(value) is not str or value not in choices:
        _refuse("shape")


def _text(value):
    if type(value) is not str or len(value) > 8388608:
        _refuse("shape")


def _hex(value, extent=None):
    if type(value) is not str:
        _refuse("shape")
    if len(value) > 134217728 or len(value) % 2:
        _refuse("hex")
    if extent is not None and len(value) != 2 * extent:
        _refuse("hex")
    if any(character not in "0123456789abcdef" for character in value):
        _refuse("hex")


def _flags(value):
    _sequence(value, len(_FLAG_NAMES), len(_FLAG_NAMES))
    for index, name in enumerate(_FLAG_NAMES):
        _sequence(value[index], 2, 2)
        _literal(value[index][0], name)
        _literal(value[index][1], False)


def _worker_close(value):
    _record(
        value,
        (
            "ordinal",
            "role",
            "handle_u64",
            "close_attempted",
            "close_bool_i32",
            "win32_error_u32",
            "disposition",
        ),
    )
    _integer(value["ordinal"], 0, _U32)
    _token(
        value["role"],
        (
            "control_stdin_read",
            "control_pipe_read",
            "control_pipe_write",
        ),
    )
    _integer(value["handle_u64"], 1, _U64)
    if type(value["close_attempted"]) is not bool:
        _refuse("shape")
    _integer(value["close_bool_i32"], _I32_MIN, _I32_MAX, nullable=True)
    _integer(value["win32_error_u32"], 0, _U32, nullable=True)
    _token(value["disposition"], ("closed", "close_failed", "not_attempted"))


def _return(value, kind):
    _record(value, ("kind", "raw_i64", "raw_u64", "win32_error_u32"))
    _literal(value["kind"], kind)
    _integer(value["raw_i64"], _I32_MIN, _I32_MAX, nullable=True)
    _integer(value["raw_u64"], 0, _U64, nullable=True)
    _integer(value["win32_error_u32"], 0, _U32, nullable=True)


def _exception_scalar(value, optional=False):
    _record(value, ("kind", "value"))
    choices = ("none", "int", "str", "absent") if optional else ("none", "int", "str")
    _token(value["kind"], choices)
    if value["kind"] == "int":
        _integer(value["value"], _I64_MIN, _I64_MAX)
    elif value["kind"] == "str":
        _text(value["value"])
    else:
        _literal(value["value"], None)


def _error(value, binding=False):
    if binding:
        _record(
            value,
            (
                "type_module",
                "type_qualname",
                "args",
                "display_text",
                "name",
                "obj_state",
                "obj_constructor_ordinal",
                "native_error_observed",
            ),
        )
    else:
        _record(
            value,
            (
                "type_module",
                "type_qualname",
                "args",
                "errno",
                "winerror",
                "strerror",
                "filename",
                "filename2",
                "hresult",
                "display_text",
            ),
        )
    for key in ("type_module", "type_qualname", "display_text"):
        _text(value[key])
    _sequence(value["args"], 0, 8)
    for argument in value["args"]:
        _exception_scalar(argument)
    if binding:
        _exception_scalar(value["name"], optional=True)
        _token(value["obj_state"], ("absent", "none", "expected_library"))
        _integer(value["obj_constructor_ordinal"], 0, _U32, nullable=True)
        _literal(value["native_error_observed"], False)
    else:
        for key in ("errno", "winerror", "strerror", "filename", "filename2", "hresult"):
            _exception_scalar(value[key], optional=True)


def _initialization(value):
    _record(
        value,
        (
            "ordinal",
            "owner_role",
            "constructor",
            "arguments",
            "source_selector",
            "started_monotonic_ns",
            "ended_monotonic_ns",
            "completed",
            "exposed_handle_u64",
            "exception",
            "native_call_observation",
            "reference_disposition",
        ),
    )
    _integer(value["ordinal"], 0, _U32)
    _literal(value["owner_role"], "worker")
    _literal(value["constructor"], "ctypes.WinDLL")
    _literal(value["source_selector"], _INITIALIZATION_SELECTOR)
    _record(
        value["arguments"],
        (
            "name",
            "mode",
            "handle",
            "use_errno",
            "use_last_error",
            "winmode",
        ),
    )
    fixed_arguments = {
        "name": "C:\\Windows\\System32\\kernel32.dll",
        "mode": 0,
        "handle": None,
        "use_errno": False,
        "use_last_error": True,
        "winmode": 2304,
    }
    for key, fixed in fixed_arguments.items():
        _literal(value["arguments"][key], fixed)
    _integer(value["started_monotonic_ns"], 0, _U64)
    _integer(value["ended_monotonic_ns"], 0, _U64, nullable=True)
    if type(value["completed"]) is not bool:
        _refuse("shape")
    _integer(value["exposed_handle_u64"], 1, _U64, nullable=True)
    if value["exception"] is not None:
        _error(value["exception"])
    _literal(value["native_call_observation"], "not_exposed")
    _token(
        value["reference_disposition"],
        (
            "unresolved",
            "not_acquired",
            "process_lifetime_bootstrap",
        ),
    )


def _binding(value):
    _record(
        value,
        (
            "ordinal",
            "owner_role",
            "constructor_ordinal",
            "api_name",
            "lookup_kind",
            "source_selector",
            "started_monotonic_ns",
            "ended_monotonic_ns",
            "completed",
            "exposed_address_u64",
            "exception",
            "native_call_observation",
        ),
    )
    _integer(value["ordinal"], 0, _U32)
    _integer(value["constructor_ordinal"], 0, _U32)
    _literal(value["owner_role"], "worker")
    _token(value["api_name"], _BINDING_NAMES)
    _literal(value["lookup_kind"], "ctypes_library_item")
    _literal(value["source_selector"], _BINDING_SELECTOR)
    _integer(value["started_monotonic_ns"], 0, _U64)
    _integer(value["ended_monotonic_ns"], 0, _U64, nullable=True)
    if type(value["completed"]) is not bool:
        _refuse("shape")
    _integer(value["exposed_address_u64"], 1, _U64, nullable=True)
    if value["exception"] is not None:
        _error(value["exception"], binding=True)
    _literal(value["native_call_observation"], "not_exposed")


class _Shape:
    """A fixed shape walk records paths; it does not certify their truth."""

    def __init__(self):
        self.raw_paths = {}
        self.initializations = []

    def raw(self, value, path, category, extent=None):
        _hex(value, extent)
        if path in self.raw_paths:
            raise AssertionError("duplicate internal raw path")
        self.raw_paths[path] = (category, len(value) // 2)

    def pointer(self, value, path, pointee, extent, category):
        _record(
            value,
            (
                "address_u64",
                "storage_before_hex",
                "storage_bytes_u32",
                "pointee_kind",
            ),
        )
        _integer(value["address_u64"], 0 if pointee == "none" else 1, _U64)
        _integer(value["storage_bytes_u32"], 0, _U32)
        _literal(value["pointee_kind"], pointee)
        size = value["storage_bytes_u32"]
        if type(extent) is tuple:
            _integer(size, extent[0], extent[1])
        else:
            _literal(size, extent)
        if size == 0:
            _literal(value["storage_before_hex"], None)
            if pointee == "none":
                _literal(value["address_u64"], 0)
            return None
        self.raw(value["storage_before_hex"], path + ("storage_before_hex",), category, size)
        return size

    def arguments(self, api, values, path, pending=False):
        specifications = _CALLS[api][2]
        _sequence(values, len(specifications), len(specifications))
        for argument, specification in zip(values, specifications, strict=False):
            _record(argument, ("name", "kind", "value"))
            _literal(argument["name"], specification[0])
            _literal(argument["kind"], specification[1])
        requested = None
        if api == "ReadFile" or api == "WriteFile":
            ceiling = 48 if api == "ReadFile" else 65536
            requested = values[2]["value"]
            _integer(requested, 1, ceiling)
            if pending:
                _literal(requested, 1)
        allocated = []
        for index, (argument, specification) in enumerate(
            zip(values, specifications, strict=False)
        ):
            name, kind, pointee, extent, fixed = specification
            category = "H" if (api, name) in _H_INPUTS else "B"
            if kind == "pointer":
                capacity = self.pointer(
                    argument["value"],
                    path + (index, "value"),
                    pointee,
                    requested if extent == "request" else extent,
                    category,
                )
                if capacity is not None:
                    allocated.append((name, capacity, category))
            else:
                _integer(argument["value"], 0, _U32 if kind == "u32" else _U64)
                if fixed is not None:
                    if type(fixed) is tuple:
                        if argument["value"] not in fixed:
                            _refuse("shape")
                    else:
                        _literal(argument["value"], fixed)
        return allocated

    def buffer(self, value, path, name, capacity, category):
        _record(
            value,
            (
                "parameter",
                "capacity_bytes",
                "returned_bytes",
                "full_buffer_hex",
                "output_validity",
                "valid_prefix_bytes",
                "projection_kind",
            ),
        )
        _literal(value["parameter"], name)
        _literal(value["capacity_bytes"], capacity)
        self.raw(value["full_buffer_hex"], path + ("full_buffer_hex",), category, capacity)
        _token(value["output_validity"], ("storage_only", "documented_valid"))
        if value["output_validity"] == "storage_only":
            _literal(value["returned_bytes"], None)
            _literal(value["valid_prefix_bytes"], None)
            _literal(value["projection_kind"], "none")
        else:
            _integer(value["returned_bytes"], 0, capacity)
            _integer(value["valid_prefix_bytes"], 0, capacity)
            _token(value["projection_kind"], _PROJECTIONS)

    def buffers(self, values, path, allocated):
        _sequence(values, len(allocated), len(allocated))
        for index, (name, capacity, category) in enumerate(allocated):
            self.buffer(values[index], path + (index,), name, capacity, category)

    def trace(self, value, path):
        _record(
            value,
            (
                "ordinal",
                "phase",
                "api",
                "source_selector",
                "arguments",
                "return",
                "saved_error_seed",
                "output_buffers",
                "started_monotonic_ns",
                "ended_monotonic_ns",
            ),
        )
        if type(value["api"]) is not str:
            _refuse("shape")
        if value["api"] not in _CALLS:
            _refuse("unsupported")
        api = value["api"]
        kind, selector, _ = _CALLS[api]
        _literal(value["source_selector"], selector)
        _integer(value["ordinal"], 0, _U32)
        _token(value["phase"], ("preflight", "resumed", "handle_closed"))
        _integer(value["started_monotonic_ns"], 0, _U64)
        _integer(value["ended_monotonic_ns"], 0, _U64)
        allocated = self.arguments(api, value["arguments"], path + ("arguments",))
        _return(value["return"], kind)
        if api == "GetFileType":
            seed = value["saved_error_seed"]
            _record(seed, ("helper", "input_i32", "returned_previous_i32"))
            _literal(seed["helper"], "ctypes.set_last_error")
            _literal(seed["input_i32"], 0)
            _integer(seed["returned_previous_i32"], _I32_MIN, _I32_MAX)
        else:
            _literal(value["saved_error_seed"], None)
        self.buffers(value["output_buffers"], path + ("output_buffers",), allocated)

    def traces(self, values, path):
        _sequence(values, 1, 4096)
        for index, value in enumerate(values):
            self.trace(value, path + (index,))

    def go_read(self, value, path, eof=False):
        _record(
            value,
            (
                "ordinal",
                "offset_u32",
                "requested_count_u32",
                "api_ordinal",
                "return",
                "returned_count_u32",
                "buffer_observations",
            ),
        )
        for key in ("ordinal", "offset_u32", "api_ordinal"):
            _integer(value[key], 0, _U32)
        requested = value["requested_count_u32"]
        _integer(requested, 1, 48)
        if eof:
            _literal(requested, 1)
            _literal(value["offset_u32"], 48)
        _integer(value["returned_count_u32"], 0, _U32, nullable=True)
        _return(value["return"], "bool32")
        self.buffers(
            value["buffer_observations"],
            path + ("buffer_observations",),
            (("lpBuffer", requested, "B"), ("lpNumberOfBytesRead", 4, "B")),
        )

    def go(self, value, path):
        _record(
            value,
            (
                "packet_hex",
                "initialization",
                "binding_initialization",
                "data_reads",
                "eof_probe",
                "stdin_close",
            ),
        )
        self.raw(value["packet_hex"], path + ("packet_hex",), "H", 48)
        _sequence(value["initialization"], 1, 16)
        for index, initialization in enumerate(value["initialization"]):
            _initialization(initialization)
            self.initializations.append((path + ("initialization", index), initialization))
        _sequence(value["binding_initialization"], 1, 128)
        for binding in value["binding_initialization"]:
            _binding(binding)
        _sequence(value["data_reads"], 1, 48)
        for index, read in enumerate(value["data_reads"]):
            self.go_read(read, path + ("data_reads", index))
        self.go_read(value["eof_probe"], path + ("eof_probe",), eof=True)
        _worker_close(value["stdin_close"])

    def worker(self, value):
        _record(
            value,
            (
                "version",
                "case_id",
                "packet_sha256",
                "nonce_hex",
                "status",
                "worker_pid",
                "observed_parent_pid",
                "started_monotonic_ns",
                "ended_monotonic_ns",
                "payload_hex",
                "worker_pre_emission_api_trace",
                "worker_cleanup",
                "authority_flags",
            ),
        )
        _literal(value["version"], "local-member-intake-bootstrap-result-v3")
        case = value["case_id"]
        if type(case) is not str or not 1 <= len(case) <= 64:
            _refuse("shape")
        if any(not ("a" <= char <= "z" or "0" <= char <= "9" or char == "_") for char in case):
            _refuse("shape")
        _hex(value["packet_sha256"], 32)
        self.raw(value["nonce_hex"], ("nonce_hex",), "H", 16)
        self.raw(value["payload_hex"], ("payload_hex",), "H")
        _token(value["status"], ("completed", "controlled_failure"))
        _integer(value["worker_pid"], 1, _U32)
        _integer(value["observed_parent_pid"], 1, _U32)
        _integer(value["started_monotonic_ns"], 0, _U64)
        _integer(value["ended_monotonic_ns"], 0, _U64)
        self.traces(value["worker_pre_emission_api_trace"], ("worker_pre_emission_api_trace",))
        _sequence(value["worker_cleanup"], 0, 16)
        for close in value["worker_cleanup"]:
            _worker_close(close)
        _flags(value["authority_flags"])

    def payload(self, value):
        _record(value, ("control_payload_hex", "go_observation"))
        self.raw(value["control_payload_hex"], ("control_payload_hex",), "H")
        self.go(value["go_observation"], ("go_observation",))

    def marker(self, value):
        _record(
            value,
            (
                "version",
                "case_id",
                "packet_sha256",
                "nonce_hex",
                "worker_pid",
                "observed_parent_pid",
                "started_monotonic_ns",
                "go_observation",
                "owned_handles",
                "completed_api_trace",
                "pending_call",
                "authority_flags",
                "marker_sha256",
            ),
        )
        _literal(value["version"], "local-member-intake-bootstrap-pending-read-v2")
        _literal(value["case_id"], "blocked_owned_pipe_read")
        _hex(value["packet_sha256"], 32)
        _hex(value["marker_sha256"], 32)
        self.raw(value["nonce_hex"], ("nonce_hex",), "H", 16)
        _integer(value["worker_pid"], 1, _U32)
        _integer(value["observed_parent_pid"], 1, _U32)
        _integer(value["started_monotonic_ns"], 0, _U64)
        self.go(value["go_observation"], ("go_observation",))
        _sequence(value["owned_handles"], 2, 2)
        for index, role in enumerate(("control_pipe_read", "control_pipe_write")):
            owned = value["owned_handles"][index]
            _record(owned, ("role", "handle_u64"))
            _literal(owned["role"], role)
            _integer(owned["handle_u64"], 1, _U64)
        self.traces(value["completed_api_trace"], ("completed_api_trace",))
        pending = value["pending_call"]
        _record(
            pending,
            (
                "api",
                "source_selector",
                "arguments",
                "input_buffers",
                "started_monotonic_ns",
            ),
        )
        _literal(pending["api"], "ReadFile")
        _literal(pending["source_selector"], _CALLS["ReadFile"][1])
        _integer(pending["started_monotonic_ns"], 0, _U64)
        allocated = self.arguments(
            "ReadFile", pending["arguments"], ("pending_call", "arguments"), pending=True
        )
        # These are generic BufferObservation shapes.  Their semantic validity
        # as precall inputs is outside this audit, just like native post validity.
        self.buffers(pending["input_buffers"], ("pending_call", "input_buffers"), allocated)
        _flags(value["authority_flags"])


def _metadata_view(body, raw_paths):
    occurrences = []
    counted = {"B": 0, "H": 0}

    def visit(value, path):
        if path in raw_paths:
            category, extent = raw_paths[path]
            occurrences.append(
                {
                    "path": list(path),
                    "category": category,
                    "raw_byte_length": extent,
                }
            )
            counted[category] += extent
            return ""
        if type(value) is dict:
            return {key: visit(value[key], path + (key,)) for key in sorted(value)}
        if type(value) is list:
            return [visit(item, path + (index,)) for index, item in enumerate(value)]
        return value

    metadata = visit(body, ())
    if len(occurrences) != len(raw_paths):
        raise AssertionError("raw path was not visited")
    return metadata, occurrences, counted


def _measurement(path, quantity, actual, limit):
    return {
        "path": list(path),
        "quantity": quantity,
        "actual": actual,
        "limit": limit,
        "within": actual <= limit,
    }


def audit_worker_recording(container, body):
    """Return exact complete-tree accounting, never producer/native admission."""
    if type(container) is not str:
        _refuse("input")
    if container not in _CONTAINERS:
        _refuse("unsupported")
    if type(body) is not dict:
        _refuse("input")
    snapshot, declared_width = _snapshot(body)
    shape = _Shape()
    if container == "BootstrapResult":
        shape.worker(snapshot)
        full_limit, occurrence_limit = 1048576, 24578
    elif container == "PendingReadMarker":
        shape.marker(snapshot)
        full_limit, occurrence_limit = 262144, 24680
    else:
        shape.payload(snapshot)
        full_limit, occurrence_limit = 262144, 100
    body_ascii = _canonical(snapshot)
    if len(body_ascii) != declared_width:
        raise AssertionError("snapshot canonical width mismatch")
    metadata, occurrences, counted = _metadata_view(snapshot, shape.raw_paths)
    if len(occurrences) > occurrence_limit:
        raise AssertionError("structural occurrence bound mismatch")
    metadata_ascii = _canonical(metadata)
    totals = {
        "D": 0,
        "B": counted["B"],
        "H": counted["H"],
        "R": 0,
        "M": len(metadata_ascii),
        "full": len(body_ascii),
    }
    if totals["full"] != totals["M"] + 2 * totals["B"] + 2 * totals["H"]:
        raise AssertionError("complete occurrence accounting identity mismatch")
    measurements = [
        _measurement((), "B", totals["B"], 12582912),
        _measurement((), "H", totals["H"], 2097152),
        _measurement((), "M", totals["M"], 8388608),
        _measurement((), "full", totals["full"], full_limit),
    ]
    if container == "BootstrapResult":
        measurements.append(
            _measurement(
                ("payload_hex",), "decoded_bytes", len(snapshot["payload_hex"]) // 2, 262144
            )
        )
    else:
        for path, initialization in shape.initializations:
            measurements.append(_measurement(path, "full", len(_canonical(initialization)), 32768))
    over_limits = [
        _measurement(row["path"], row["quantity"], row["actual"], row["limit"])
        for row in measurements
        if not row["within"]
    ]
    return {
        "version": "local-member-intake-worker-recording-audit-v1",
        "container": container,
        "basis": {"protocol_raw_sha256": _PROTOCOL_SHA, "worker_source_raw_sha256": _WORKER_SHA},
        "body": snapshot,
        "body_ascii": body_ascii,
        "metadata": metadata,
        "metadata_ascii": metadata_ascii,
        "occurrences": occurrences,
        "totals": totals,
        "measurements": measurements,
        "over_limits": over_limits,
        "not_validated": list(_NOT_VALIDATED),
        "authority_flags": [[name, False] for name in _FLAG_NAMES],
    }
