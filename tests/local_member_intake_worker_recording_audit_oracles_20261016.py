"""Independent literal Worker/Marker/Payload occurrence-accounting oracles.

Only invented complete builtin trees are supplied here.  They are deliberately
not native observations: the minimal GO body is not a complete 48-byte read
sequence, the Worker payload is the JSON text {}, and marker/hash values are not
claimed correct.  Tests must retain the report's complete not_validated list.
No production serializer, schema, audit implementation, native helper or data is
imported.  Golden body/M bytes, raw paths and numeric totals are fixed literals.
"""

import json

FLAGS = [
    ["source_authenticated", False],
    ["collection_receipt_authenticated", False],
    ["native_runtime_authenticated", False],
    ["native_abi_authenticated", False],
    ["native_wire_authenticated", False],
    ["native_header_authenticated", False],
    ["native_eof_authenticated", False],
    ["feed_authenticated", False],
    ["calendar_authenticated", False],
    ["historical_read_authorized", False],
    ["historical_validation_authorized", False],
    ["book_acceptance_authorized", False],
    ["event_acceptance_authorized", False],
    ["feature_acceptance_authorized", False],
    ["account_authorized", False],
    ["funding_authorized", False],
    ["receipt_authorized", False],
    ["cash_authorized", False],
    ["margin_authorized", False],
    ["risk_authorized", False],
    ["storage_authorized", False],
    ["resume_authorized", False],
    ["execution_authorized", False],
    ["trading_authorized", False],
    ["training_authorized", False],
    ["scoring_authorized", False],
    ["independent_validation_authorized", False],
    ["promotion_authorized", False],
]

API_NAMES = [
    "GetProcAddress",
    "GetModuleHandleExW",
    "GetModuleFileNameW",
    "GetStdHandle",
    "GetFileType",
    "GetHandleInformation",
    "WriteFile",
    "PeekNamedPipe",
    "ReadFile",
    "GetCurrentProcessId",
    "CloseHandle",
    "VirtualAlloc",
    "VirtualFree",
    "CreatePipe",
    "SetHandleInformation",
]

BINDING_NAMES = [
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
]

SOURCE_SELECTORS = {
    "GetProcAddress": "R15/libloaderapi_nf-libloaderapi-getprocaddress.md:GetProcAddress",
    "GetModuleHandleExW": (
        "R15/libloaderapi_nf-libloaderapi-getmodulehandleexw.md:GetModuleHandleExW"
    ),
    "GetModuleFileNameW": (
        "R15/libloaderapi_nf-libloaderapi-getmodulefilenamew.md:GetModuleFileNameW"
    ),
    "GetStdHandle": "R15/fixed_getstdhandle.md:GetStdHandle",
    "GetFileType": "R14/api_09_nf-fileapi-getfiletype.md:GetFileType",
    "GetHandleInformation": (
        "R15/handleapi_nf-handleapi-gethandleinformation.md:GetHandleInformation"
    ),
    "WriteFile": "R15/extra_nf-fileapi-writefile.md:WriteFile",
    "PeekNamedPipe": "R15/namedpipeapi_nf-namedpipeapi-peeknamedpipe.md:PeekNamedPipe",
    "ReadFile": "R14/api_01_nf-fileapi-readfile.md:ReadFile",
    "GetCurrentProcessId": (
        "R15/extra_nf-processthreadsapi-getcurrentprocessid.md:GetCurrentProcessId"
    ),
    "CloseHandle": "R14/api_10_nf-handleapi-closehandle.md:CloseHandle",
    "VirtualAlloc": "R15/extra_nf-memoryapi-virtualalloc.md:VirtualAlloc",
    "VirtualFree": "R15/extra_nf-memoryapi-virtualfree.md:VirtualFree",
    "CreatePipe": "R15/namedpipeapi_nf-namedpipeapi-createpipe.md:CreatePipe",
    "SetHandleInformation": (
        "R15/handleapi_nf-handleapi-sethandleinformation.md:SetHandleInformation"
    ),
}

NOT_VALIDATED = [
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
]

BASIS = {
    "protocol_raw_sha256": "2252ebefe2d38b14f5c915b3a1b9fbb2c8bc960a02477372bb1dd0ea7114c31f",
    "worker_source_raw_sha256": "7adaf7f42fc97a0221bf792ff657c6f23b625355e348697301bdfcd9d5d00279",
}
AUDIT_VERSION = "local-member-intake-worker-recording-audit-v1"

# Parameter definitions below are independent test-side literals.  Tuple-like
# lists use [name, kind, value], with pointer values already complete Pointer4s.
_API_ARGUMENTS = {
    "GetProcAddress": [
        {"name": "hModule", "kind": "handle64", "value": 10},
        {
            "name": "lpProcName",
            "kind": "pointer",
            "value": {
                "address_u64": 1001,
                "storage_before_hex": "4100",
                "storage_bytes_u32": 2,
                "pointee_kind": "ascii_z",
            },
        },
    ],
    "GetModuleHandleExW": [
        {"name": "dwFlags", "kind": "u32", "value": 6},
        {
            "name": "lpModuleName",
            "kind": "pointer",
            "value": {
                "address_u64": 400,
                "storage_before_hex": None,
                "storage_bytes_u32": 0,
                "pointee_kind": "external_function_address",
            },
        },
        {
            "name": "phModule",
            "kind": "pointer",
            "value": {
                "address_u64": 1002,
                "storage_before_hex": "0000000000000000",
                "storage_bytes_u32": 8,
                "pointee_kind": "handle_out",
            },
        },
    ],
    "GetModuleFileNameW": [
        {"name": "hModule", "kind": "handle64", "value": 10},
        {
            "name": "lpFilename",
            "kind": "pointer",
            "value": {
                "address_u64": 1001,
                "storage_before_hex": (
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                    "0000000000000000000000000000000000000000000000000000000000000000"
                ),
                "storage_bytes_u32": 1024,
                "pointee_kind": "utf16_mutable_z",
            },
        },
        {"name": "nSize", "kind": "u32", "value": 512},
    ],
    "GetStdHandle": [{"name": "nStdHandle", "kind": "u32", "value": 4294967286}],
    "GetFileType": [{"name": "hFile", "kind": "handle64", "value": 10}],
    "GetHandleInformation": [
        {"name": "hObject", "kind": "handle64", "value": 10},
        {
            "name": "lpdwFlags",
            "kind": "pointer",
            "value": {
                "address_u64": 1001,
                "storage_before_hex": "00000000",
                "storage_bytes_u32": 4,
                "pointee_kind": "dword_out",
            },
        },
    ],
    "WriteFile": [
        {"name": "hFile", "kind": "handle64", "value": 10},
        {
            "name": "lpBuffer",
            "kind": "pointer",
            "value": {
                "address_u64": 1001,
                "storage_before_hex": "aa",
                "storage_bytes_u32": 1,
                "pointee_kind": "byte_buffer",
            },
        },
        {"name": "nNumberOfBytesToWrite", "kind": "u32", "value": 1},
        {
            "name": "lpNumberOfBytesWritten",
            "kind": "pointer",
            "value": {
                "address_u64": 1003,
                "storage_before_hex": "00000000",
                "storage_bytes_u32": 4,
                "pointee_kind": "dword_out",
            },
        },
        {
            "name": "lpOverlapped",
            "kind": "pointer",
            "value": {
                "address_u64": 0,
                "storage_before_hex": None,
                "storage_bytes_u32": 0,
                "pointee_kind": "none",
            },
        },
    ],
    "PeekNamedPipe": [
        {"name": "hNamedPipe", "kind": "handle64", "value": 10},
        {
            "name": "lpBuffer",
            "kind": "pointer",
            "value": {
                "address_u64": 0,
                "storage_before_hex": None,
                "storage_bytes_u32": 0,
                "pointee_kind": "none",
            },
        },
        {"name": "nBufferSize", "kind": "u32", "value": 0},
        {
            "name": "lpBytesRead",
            "kind": "pointer",
            "value": {
                "address_u64": 0,
                "storage_before_hex": None,
                "storage_bytes_u32": 0,
                "pointee_kind": "none",
            },
        },
        {
            "name": "lpTotalBytesAvail",
            "kind": "pointer",
            "value": {
                "address_u64": 1004,
                "storage_before_hex": "00000000",
                "storage_bytes_u32": 4,
                "pointee_kind": "dword_out",
            },
        },
        {
            "name": "lpBytesLeftThisMessage",
            "kind": "pointer",
            "value": {
                "address_u64": 1005,
                "storage_before_hex": "00000000",
                "storage_bytes_u32": 4,
                "pointee_kind": "dword_out",
            },
        },
    ],
    "ReadFile": [
        {"name": "hFile", "kind": "handle64", "value": 10},
        {
            "name": "lpBuffer",
            "kind": "pointer",
            "value": {
                "address_u64": 1001,
                "storage_before_hex": "aa",
                "storage_bytes_u32": 1,
                "pointee_kind": "byte_buffer",
            },
        },
        {"name": "nNumberOfBytesToRead", "kind": "u32", "value": 1},
        {
            "name": "lpNumberOfBytesRead",
            "kind": "pointer",
            "value": {
                "address_u64": 1003,
                "storage_before_hex": "00000000",
                "storage_bytes_u32": 4,
                "pointee_kind": "dword_out",
            },
        },
        {
            "name": "lpOverlapped",
            "kind": "pointer",
            "value": {
                "address_u64": 0,
                "storage_before_hex": None,
                "storage_bytes_u32": 0,
                "pointee_kind": "none",
            },
        },
    ],
    "GetCurrentProcessId": [],
    "CloseHandle": [{"name": "hObject", "kind": "handle64", "value": 10}],
    "VirtualAlloc": [
        {
            "name": "lpAddress",
            "kind": "pointer",
            "value": {
                "address_u64": 0,
                "storage_before_hex": None,
                "storage_bytes_u32": 0,
                "pointee_kind": "none",
            },
        },
        {"name": "dwSize", "kind": "u64", "value": 268435456},
        {"name": "flAllocationType", "kind": "u32", "value": 12288},
        {"name": "flProtect", "kind": "u32", "value": 4},
    ],
    "VirtualFree": [
        {
            "name": "lpAddress",
            "kind": "pointer",
            "value": {
                "address_u64": 400,
                "storage_before_hex": None,
                "storage_bytes_u32": 0,
                "pointee_kind": "allocation_base",
            },
        },
        {"name": "dwSize", "kind": "u64", "value": 0},
        {"name": "dwFreeType", "kind": "u32", "value": 32768},
    ],
    "CreatePipe": [
        {
            "name": "hReadPipe",
            "kind": "pointer",
            "value": {
                "address_u64": 1000,
                "storage_before_hex": "0000000000000000",
                "storage_bytes_u32": 8,
                "pointee_kind": "handle_out",
            },
        },
        {
            "name": "hWritePipe",
            "kind": "pointer",
            "value": {
                "address_u64": 1001,
                "storage_before_hex": "0000000000000000",
                "storage_bytes_u32": 8,
                "pointee_kind": "handle_out",
            },
        },
        {
            "name": "lpPipeAttributes",
            "kind": "pointer",
            "value": {
                "address_u64": 1002,
                "storage_before_hex": "000000000000000000000000000000000000000000000000",
                "storage_bytes_u32": 24,
                "pointee_kind": "security_attributes",
            },
        },
        {"name": "nSize", "kind": "u32", "value": 65536},
    ],
    "SetHandleInformation": [
        {"name": "hObject", "kind": "handle64", "value": 10},
        {"name": "dwMask", "kind": "u32", "value": 1},
        {"name": "dwFlags", "kind": "u32", "value": 0},
    ],
}

_RETURN_KINDS = {
    "GetProcAddress": "handle64",
    "GetModuleHandleExW": "bool32",
    "GetModuleFileNameW": "dword32",
    "GetStdHandle": "handle64",
    "GetFileType": "dword32",
    "GetHandleInformation": "bool32",
    "WriteFile": "bool32",
    "PeekNamedPipe": "bool32",
    "ReadFile": "bool32",
    "GetCurrentProcessId": "dword32",
    "CloseHandle": "bool32",
    "VirtualAlloc": "handle64",
    "VirtualFree": "bool32",
    "CreatePipe": "bool32",
    "SetHandleInformation": "bool32",
}


def _clone(value):
    """Test-data clone that deliberately copies each physical alias path."""
    if type(value) is dict:
        return {key: _clone(item) for key, item in value.items()}
    if type(value) is list:
        return [_clone(item) for item in value]
    return value


def _quote(value):
    pieces = ['"']
    short = {
        '"': '\\"',
        "\\": "\\\\",
        "\b": "\\b",
        "\t": "\\t",
        "\n": "\\n",
        "\f": "\\f",
        "\r": "\\r",
    }
    for character in value:
        code = ord(character)
        if character in short:
            pieces.append(short[character])
        elif 32 <= code <= 126:
            pieces.append(character)
        elif code <= 0xFFFF:
            pieces.append(f"\\u{code:04x}")
        else:
            scalar = code - 0x10000
            pieces.append(f"\\u{0xD800 + (scalar >> 10):04x}\\u{0xDC00 + (scalar & 0x3FF):04x}")
    pieces.append('"')
    return "".join(pieces)


def independent_canonical(value):
    """Independent test encoder, not json.dumps or production serialization."""
    if value is None:
        return b"null"
    if type(value) is bool:
        return b"true" if value else b"false"
    if type(value) is int:
        return str(value).encode("ascii")
    if type(value) is str:
        return _quote(value).encode("ascii")
    if type(value) is list:
        return b"[" + b",".join(independent_canonical(item) for item in value) + b"]"
    if type(value) is dict:
        return (
            b"{"
            + b",".join(
                _quote(key).encode("ascii") + b":" + independent_canonical(value[key])
                for key in sorted(value)
            )
            + b"}"
        )
    raise AssertionError("unsupported test oracle value")


def make_trace(api):
    """One independently defined selected API row, not a valid native history."""
    arguments = _clone(_API_ARGUMENTS[api])
    kind = _RETURN_KINDS[api]
    raw = 1 if kind == "bool32" else 200 if kind == "handle64" else 3
    outputs = []
    for argument in arguments:
        if argument["kind"] == "pointer":
            pointer = argument["value"]
            if pointer["storage_before_hex"] is not None:
                outputs.append(
                    {
                        "parameter": argument["name"],
                        "capacity_bytes": pointer["storage_bytes_u32"],
                        "returned_bytes": None,
                        "full_buffer_hex": pointer["storage_before_hex"],
                        "output_validity": "storage_only",
                        "valid_prefix_bytes": None,
                        "projection_kind": "none",
                    }
                )
    return {
        "ordinal": 0,
        "phase": "preflight" if api == "GetProcAddress" else "resumed",
        "api": api,
        "source_selector": SOURCE_SELECTORS[api],
        "arguments": arguments,
        "return": {
            "kind": kind,
            "raw_i64": raw if kind == "bool32" else None,
            "raw_u64": None if kind == "bool32" else raw,
            "win32_error_u32": None,
        },
        "saved_error_seed": {
            "helper": "ctypes.set_last_error",
            "input_i32": 0,
            "returned_previous_i32": -7,
        }
        if api == "GetFileType"
        else None,
        "output_buffers": outputs,
        "started_monotonic_ns": 1,
        "ended_monotonic_ns": 2,
    }


def make_constructor_error():
    """Complete ten-field broad diagnostic; every value is metadata."""
    return {
        "type_module": "builtins",
        "type_qualname": "OSError",
        "args": [
            {"kind": "none", "value": None},
            {"kind": "int", "value": -1},
            {"kind": "str", "value": "00ff"},
        ],
        "errno": {"kind": "int", "value": 1},
        "winerror": {"kind": "int", "value": 5},
        "strerror": {"kind": "str", "value": "failure"},
        "filename": {"kind": "absent", "value": None},
        "filename2": {"kind": "none", "value": None},
        "hresult": {"kind": "int", "value": -1},
        "display_text": "complete invented diagnostic",
    }


def make_binding_error():
    """Complete eight-field lookup diagnostic; no hidden opaque subrecord."""
    return {
        "type_module": "builtins",
        "type_qualname": "AttributeError",
        "args": [{"kind": "str", "value": "missing"}],
        "display_text": "complete invented lookup diagnostic",
        "name": {"kind": "str", "value": "ReadFile"},
        "obj_state": "expected_library",
        "obj_constructor_ordinal": 0,
        "native_error_observed": False,
    }


# The following six complete canonical byte strings are fixed golden literals.
# No factory, independent encoder, classifier or implementation derives them
# when golden_cases() is called. Numeric values below were independently fixed:
# Worker full2185=M2141+2H22; Payload2339=M2221+2B10+2H49;
# Marker6305=M5977+2B52+2H112. Every initialization is full480 bytes.
_GOLDEN_WORKER_BODY_ASCII = (
    b'{"authority_flags":[["source_authenticated",false],["collection_'
    b'receipt_authenticated",false],["native_runtime_authenticated",fa'
    b'lse],["native_abi_authenticated",false],["native_wire_authentica'
    b'ted",false],["native_header_authenticated",false],["native_eof_a'
    b'uthenticated",false],["feed_authenticated",false],["calendar_aut'
    b'henticated",false],["historical_read_authorized",false],["histor'
    b'ical_validation_authorized",false],["book_acceptance_authorized"'
    b',false],["event_acceptance_authorized",false],["feature_acceptan'
    b'ce_authorized",false],["account_authorized",false],["funding_aut'
    b'horized",false],["receipt_authorized",false],["cash_authorized",'
    b'false],["margin_authorized",false],["risk_authorized",false],["s'
    b'torage_authorized",false],["resume_authorized",false],["executio'
    b'n_authorized",false],["trading_authorized",false],["training_aut'
    b'horized",false],["scoring_authorized",false],["independent_valid'
    b'ation_authorized",false],["promotion_authorized",false]],"case_i'
    b'd":"audit_worker","ended_monotonic_ns":2,"nonce_hex":"1111111111'
    b'1111111111111111111111","observed_parent_pid":5,"packet_sha256":'
    b'"000000000000000000000000000000000000000000000000000000000000000'
    b'0","payload_hex":"7b7d","started_monotonic_ns":1,"status":"compl'
    b'eted","version":"local-member-intake-bootstrap-result-v3","worke'
    b'r_cleanup":[{"close_attempted":true,"close_bool_i32":1,"disposit'
    b'ion":"closed","handle_u64":11,"ordinal":0,"role":"control_stdin_'
    b'read","win32_error_u32":null}],"worker_pid":7,"worker_pre_emissi'
    b'on_api_trace":[{"api":"GetProcAddress","arguments":[{"kind":"han'
    b'dle64","name":"hModule","value":10},{"kind":"pointer","name":"lp'
    b'ProcName","value":{"address_u64":1001,"pointee_kind":"ascii_z","'
    b'storage_before_hex":"4100","storage_bytes_u32":2}}],"ended_monot'
    b'onic_ns":2,"ordinal":0,"output_buffers":[{"capacity_bytes":2,"fu'
    b'll_buffer_hex":"4100","output_validity":"storage_only","paramete'
    b'r":"lpProcName","projection_kind":"none","returned_bytes":null,"'
    b'valid_prefix_bytes":null}],"phase":"preflight","return":{"kind":'
    b'"handle64","raw_i64":null,"raw_u64":200,"win32_error_u32":null},'
    b'"saved_error_seed":null,"source_selector":"R15/libloaderapi_nf-l'
    b'ibloaderapi-getprocaddress.md:GetProcAddress","started_monotonic'
    b'_ns":1}]}'
)

_GOLDEN_WORKER_METADATA_ASCII = (
    b'{"authority_flags":[["source_authenticated",false],["collection_'
    b'receipt_authenticated",false],["native_runtime_authenticated",fa'
    b'lse],["native_abi_authenticated",false],["native_wire_authentica'
    b'ted",false],["native_header_authenticated",false],["native_eof_a'
    b'uthenticated",false],["feed_authenticated",false],["calendar_aut'
    b'henticated",false],["historical_read_authorized",false],["histor'
    b'ical_validation_authorized",false],["book_acceptance_authorized"'
    b',false],["event_acceptance_authorized",false],["feature_acceptan'
    b'ce_authorized",false],["account_authorized",false],["funding_aut'
    b'horized",false],["receipt_authorized",false],["cash_authorized",'
    b'false],["margin_authorized",false],["risk_authorized",false],["s'
    b'torage_authorized",false],["resume_authorized",false],["executio'
    b'n_authorized",false],["trading_authorized",false],["training_aut'
    b'horized",false],["scoring_authorized",false],["independent_valid'
    b'ation_authorized",false],["promotion_authorized",false]],"case_i'
    b'd":"audit_worker","ended_monotonic_ns":2,"nonce_hex":"","observe'
    b'd_parent_pid":5,"packet_sha256":"0000000000000000000000000000000'
    b'000000000000000000000000000000000","payload_hex":"","started_mon'
    b'otonic_ns":1,"status":"completed","version":"local-member-intake'
    b'-bootstrap-result-v3","worker_cleanup":[{"close_attempted":true,'
    b'"close_bool_i32":1,"disposition":"closed","handle_u64":11,"ordin'
    b'al":0,"role":"control_stdin_read","win32_error_u32":null}],"work'
    b'er_pid":7,"worker_pre_emission_api_trace":[{"api":"GetProcAddres'
    b's","arguments":[{"kind":"handle64","name":"hModule","value":10},'
    b'{"kind":"pointer","name":"lpProcName","value":{"address_u64":100'
    b'1,"pointee_kind":"ascii_z","storage_before_hex":"","storage_byte'
    b's_u32":2}}],"ended_monotonic_ns":2,"ordinal":0,"output_buffers":'
    b'[{"capacity_bytes":2,"full_buffer_hex":"","output_validity":"sto'
    b'rage_only","parameter":"lpProcName","projection_kind":"none","re'
    b'turned_bytes":null,"valid_prefix_bytes":null}],"phase":"prefligh'
    b't","return":{"kind":"handle64","raw_i64":null,"raw_u64":200,"win'
    b'32_error_u32":null},"saved_error_seed":null,"source_selector":"R'
    b"15/libloaderapi_nf-libloaderapi-getprocaddress.md:GetProcAddress"
    b'","started_monotonic_ns":1}]}'
)

_GOLDEN_WORKER_ROWS = [
    {"path": ["nonce_hex"], "category": "H", "raw_byte_length": 16},
    {"path": ["payload_hex"], "category": "H", "raw_byte_length": 2},
    {
        "path": ["worker_pre_emission_api_trace", 0, "arguments", 1, "value", "storage_before_hex"],
        "category": "H",
        "raw_byte_length": 2,
    },
    {
        "path": ["worker_pre_emission_api_trace", 0, "output_buffers", 0, "full_buffer_hex"],
        "category": "H",
        "raw_byte_length": 2,
    },
]

_GOLDEN_PAYLOAD_BODY_ASCII = (
    b'{"control_payload_hex":"00","go_observation":{"binding_initializ'
    b'ation":[{"api_name":"ReadFile","completed":true,"constructor_ord'
    b'inal":0,"ended_monotonic_ns":4,"exception":null,"exposed_address'
    b'_u64":200,"lookup_kind":"ctypes_library_item","native_call_obser'
    b'vation":"not_exposed","ordinal":0,"owner_role":"worker","source_'
    b'selector":"R15/cpython_31210_ctypes_init.py.txt:CDLL.__getitem__'
    b'/_FuncPtr","started_monotonic_ns":3}],"data_reads":[{"api_ordina'
    b'l":0,"buffer_observations":[{"capacity_bytes":1,"full_buffer_hex'
    b'":"aa","output_validity":"documented_valid","parameter":"lpBuffe'
    b'r","projection_kind":"byte_prefix","returned_bytes":1,"valid_pre'
    b'fix_bytes":1},{"capacity_bytes":4,"full_buffer_hex":"01000000","'
    b'output_validity":"documented_valid","parameter":"lpNumberOfBytes'
    b'Read","projection_kind":"u32","returned_bytes":4,"valid_prefix_b'
    b'ytes":4}],"offset_u32":0,"ordinal":0,"requested_count_u32":1,"re'
    b'turn":{"kind":"bool32","raw_i64":1,"raw_u64":null,"win32_error_u'
    b'32":null},"returned_count_u32":1}],"eof_probe":{"api_ordinal":1,'
    b'"buffer_observations":[{"capacity_bytes":1,"full_buffer_hex":"00'
    b'","output_validity":"storage_only","parameter":"lpBuffer","proje'
    b'ction_kind":"none","returned_bytes":null,"valid_prefix_bytes":nu'
    b'll},{"capacity_bytes":4,"full_buffer_hex":"00000000","output_val'
    b'idity":"storage_only","parameter":"lpNumberOfBytesRead","project'
    b'ion_kind":"none","returned_bytes":null,"valid_prefix_bytes":null'
    b'}],"offset_u32":48,"ordinal":1,"requested_count_u32":1,"return":'
    b'{"kind":"bool32","raw_i64":0,"raw_u64":null,"win32_error_u32":10'
    b'9},"returned_count_u32":null},"initialization":[{"arguments":{"h'
    b'andle":null,"mode":0,"name":"C:\\\\Windows\\\\System32\\\\kernel'
    b'32.dll","use_errno":false,"use_last_error":true,"winmode":2304},'
    b'"completed":true,"constructor":"ctypes.WinDLL","ended_monotonic_'
    b'ns":2,"exception":null,"exposed_handle_u64":100,"native_call_obs'
    b'ervation":"not_exposed","ordinal":0,"owner_role":"worker","refer'
    b'ence_disposition":"process_lifetime_bootstrap","source_selector"'
    b':"R15/cpython_31210_ctypes_init.py.txt:CDLL.__init__/WinDLL","st'
    b'arted_monotonic_ns":1}],"packet_hex":"00000000000000000000000000'
    b"0000000000000000000000000000000000000000000000000000000000000000"
    b'000000","stdin_close":{"close_attempted":true,"close_bool_i32":1'
    b',"disposition":"closed","handle_u64":11,"ordinal":0,"role":"cont'
    b'rol_stdin_read","win32_error_u32":null}}}'
)

_GOLDEN_PAYLOAD_METADATA_ASCII = (
    b'{"control_payload_hex":"","go_observation":{"binding_initializat'
    b'ion":[{"api_name":"ReadFile","completed":true,"constructor_ordin'
    b'al":0,"ended_monotonic_ns":4,"exception":null,"exposed_address_u'
    b'64":200,"lookup_kind":"ctypes_library_item","native_call_observa'
    b'tion":"not_exposed","ordinal":0,"owner_role":"worker","source_se'
    b'lector":"R15/cpython_31210_ctypes_init.py.txt:CDLL.__getitem__/_'
    b'FuncPtr","started_monotonic_ns":3}],"data_reads":[{"api_ordinal"'
    b':0,"buffer_observations":[{"capacity_bytes":1,"full_buffer_hex":'
    b'"","output_validity":"documented_valid","parameter":"lpBuffer","'
    b'projection_kind":"byte_prefix","returned_bytes":1,"valid_prefix_'
    b'bytes":1},{"capacity_bytes":4,"full_buffer_hex":"","output_valid'
    b'ity":"documented_valid","parameter":"lpNumberOfBytesRead","proje'
    b'ction_kind":"u32","returned_bytes":4,"valid_prefix_bytes":4}],"o'
    b'ffset_u32":0,"ordinal":0,"requested_count_u32":1,"return":{"kind'
    b'":"bool32","raw_i64":1,"raw_u64":null,"win32_error_u32":null},"r'
    b'eturned_count_u32":1}],"eof_probe":{"api_ordinal":1,"buffer_obse'
    b'rvations":[{"capacity_bytes":1,"full_buffer_hex":"","output_vali'
    b'dity":"storage_only","parameter":"lpBuffer","projection_kind":"n'
    b'one","returned_bytes":null,"valid_prefix_bytes":null},{"capacity'
    b'_bytes":4,"full_buffer_hex":"","output_validity":"storage_only",'
    b'"parameter":"lpNumberOfBytesRead","projection_kind":"none","retu'
    b'rned_bytes":null,"valid_prefix_bytes":null}],"offset_u32":48,"or'
    b'dinal":1,"requested_count_u32":1,"return":{"kind":"bool32","raw_'
    b'i64":0,"raw_u64":null,"win32_error_u32":109},"returned_count_u32'
    b'":null},"initialization":[{"arguments":{"handle":null,"mode":0,"'
    b'name":"C:\\\\Windows\\\\System32\\\\kernel32.dll","use_errno":fa'
    b'lse,"use_last_error":true,"winmode":2304},"completed":true,"cons'
    b'tructor":"ctypes.WinDLL","ended_monotonic_ns":2,"exception":null'
    b',"exposed_handle_u64":100,"native_call_observation":"not_exposed'
    b'","ordinal":0,"owner_role":"worker","reference_disposition":"pro'
    b'cess_lifetime_bootstrap","source_selector":"R15/cpython_31210_ct'
    b'ypes_init.py.txt:CDLL.__init__/WinDLL","started_monotonic_ns":1}'
    b'],"packet_hex":"","stdin_close":{"close_attempted":true,"close_b'
    b'ool_i32":1,"disposition":"closed","handle_u64":11,"ordinal":0,"r'
    b'ole":"control_stdin_read","win32_error_u32":null}}}'
)

_GOLDEN_PAYLOAD_ROWS = [
    {"path": ["control_payload_hex"], "category": "H", "raw_byte_length": 1},
    {
        "path": ["go_observation", "data_reads", 0, "buffer_observations", 0, "full_buffer_hex"],
        "category": "B",
        "raw_byte_length": 1,
    },
    {
        "path": ["go_observation", "data_reads", 0, "buffer_observations", 1, "full_buffer_hex"],
        "category": "B",
        "raw_byte_length": 4,
    },
    {
        "path": ["go_observation", "eof_probe", "buffer_observations", 0, "full_buffer_hex"],
        "category": "B",
        "raw_byte_length": 1,
    },
    {
        "path": ["go_observation", "eof_probe", "buffer_observations", 1, "full_buffer_hex"],
        "category": "B",
        "raw_byte_length": 4,
    },
    {"path": ["go_observation", "packet_hex"], "category": "H", "raw_byte_length": 48},
]

_GOLDEN_MARKER_BODY_ASCII = (
    b'{"authority_flags":[["source_authenticated",false],["collection_'
    b'receipt_authenticated",false],["native_runtime_authenticated",fa'
    b'lse],["native_abi_authenticated",false],["native_wire_authentica'
    b'ted",false],["native_header_authenticated",false],["native_eof_a'
    b'uthenticated",false],["feed_authenticated",false],["calendar_aut'
    b'henticated",false],["historical_read_authorized",false],["histor'
    b'ical_validation_authorized",false],["book_acceptance_authorized"'
    b',false],["event_acceptance_authorized",false],["feature_acceptan'
    b'ce_authorized",false],["account_authorized",false],["funding_aut'
    b'horized",false],["receipt_authorized",false],["cash_authorized",'
    b'false],["margin_authorized",false],["risk_authorized",false],["s'
    b'torage_authorized",false],["resume_authorized",false],["executio'
    b'n_authorized",false],["trading_authorized",false],["training_aut'
    b'horized",false],["scoring_authorized",false],["independent_valid'
    b'ation_authorized",false],["promotion_authorized",false]],"case_i'
    b'd":"blocked_owned_pipe_read","completed_api_trace":[{"api":"Crea'
    b'tePipe","arguments":[{"kind":"pointer","name":"hReadPipe","value'
    b'":{"address_u64":1000,"pointee_kind":"handle_out","storage_befor'
    b'e_hex":"0000000000000000","storage_bytes_u32":8}},{"kind":"point'
    b'er","name":"hWritePipe","value":{"address_u64":1001,"pointee_kin'
    b'd":"handle_out","storage_before_hex":"0000000000000000","storage'
    b'_bytes_u32":8}},{"kind":"pointer","name":"lpPipeAttributes","val'
    b'ue":{"address_u64":1002,"pointee_kind":"security_attributes","st'
    b'orage_before_hex":"000000000000000000000000000000000000000000000'
    b'000","storage_bytes_u32":24}},{"kind":"u32","name":"nSize","valu'
    b'e":65536}],"ended_monotonic_ns":2,"ordinal":0,"output_buffers":['
    b'{"capacity_bytes":8,"full_buffer_hex":"0000000000000000","output'
    b'_validity":"storage_only","parameter":"hReadPipe","projection_ki'
    b'nd":"none","returned_bytes":null,"valid_prefix_bytes":null},{"ca'
    b'pacity_bytes":8,"full_buffer_hex":"0000000000000000","output_val'
    b'idity":"storage_only","parameter":"hWritePipe","projection_kind"'
    b':"none","returned_bytes":null,"valid_prefix_bytes":null},{"capac'
    b'ity_bytes":24,"full_buffer_hex":"0000000000000000000000000000000'
    b'00000000000000000","output_validity":"storage_only","parameter":'
    b'"lpPipeAttributes","projection_kind":"none","returned_bytes":nul'
    b'l,"valid_prefix_bytes":null}],"phase":"resumed","return":{"kind"'
    b':"bool32","raw_i64":1,"raw_u64":null,"win32_error_u32":null},"sa'
    b'ved_error_seed":null,"source_selector":"R15/namedpipeapi_nf-name'
    b'dpipeapi-createpipe.md:CreatePipe","started_monotonic_ns":1}],"g'
    b'o_observation":{"binding_initialization":[{"api_name":"ReadFile"'
    b',"completed":true,"constructor_ordinal":0,"ended_monotonic_ns":4'
    b',"exception":null,"exposed_address_u64":200,"lookup_kind":"ctype'
    b's_library_item","native_call_observation":"not_exposed","ordinal'
    b'":0,"owner_role":"worker","source_selector":"R15/cpython_31210_c'
    b'types_init.py.txt:CDLL.__getitem__/_FuncPtr","started_monotonic_'
    b'ns":3}],"data_reads":[{"api_ordinal":0,"buffer_observations":[{"'
    b'capacity_bytes":1,"full_buffer_hex":"aa","output_validity":"docu'
    b'mented_valid","parameter":"lpBuffer","projection_kind":"byte_pre'
    b'fix","returned_bytes":1,"valid_prefix_bytes":1},{"capacity_bytes'
    b'":4,"full_buffer_hex":"01000000","output_validity":"documented_v'
    b'alid","parameter":"lpNumberOfBytesRead","projection_kind":"u32",'
    b'"returned_bytes":4,"valid_prefix_bytes":4}],"offset_u32":0,"ordi'
    b'nal":0,"requested_count_u32":1,"return":{"kind":"bool32","raw_i6'
    b'4":1,"raw_u64":null,"win32_error_u32":null},"returned_count_u32"'
    b':1}],"eof_probe":{"api_ordinal":1,"buffer_observations":[{"capac'
    b'ity_bytes":1,"full_buffer_hex":"00","output_validity":"storage_o'
    b'nly","parameter":"lpBuffer","projection_kind":"none","returned_b'
    b'ytes":null,"valid_prefix_bytes":null},{"capacity_bytes":4,"full_'
    b'buffer_hex":"00000000","output_validity":"storage_only","paramet'
    b'er":"lpNumberOfBytesRead","projection_kind":"none","returned_byt'
    b'es":null,"valid_prefix_bytes":null}],"offset_u32":48,"ordinal":1'
    b',"requested_count_u32":1,"return":{"kind":"bool32","raw_i64":0,"'
    b'raw_u64":null,"win32_error_u32":109},"returned_count_u32":null},'
    b'"initialization":[{"arguments":{"handle":null,"mode":0,"name":"C'
    b':\\\\Windows\\\\System32\\\\kernel32.dll","use_errno":false,"use'
    b'_last_error":true,"winmode":2304},"completed":true,"constructor"'
    b':"ctypes.WinDLL","ended_monotonic_ns":2,"exception":null,"expose'
    b'd_handle_u64":100,"native_call_observation":"not_exposed","ordin'
    b'al":0,"owner_role":"worker","reference_disposition":"process_lif'
    b'etime_bootstrap","source_selector":"R15/cpython_31210_ctypes_ini'
    b't.py.txt:CDLL.__init__/WinDLL","started_monotonic_ns":1}],"packe'
    b't_hex":"00000000000000000000000000000000000000000000000000000000'
    b'0000000000000000000000000000000000000000","stdin_close":{"close_'
    b'attempted":true,"close_bool_i32":1,"disposition":"closed","handl'
    b'e_u64":11,"ordinal":0,"role":"control_stdin_read","win32_error_u'
    b'32":null}},"marker_sha256":"ffffffffffffffffffffffffffffffffffff'
    b'ffffffffffffffffffffffffffff","nonce_hex":"111111111111111111111'
    b'11111111111","observed_parent_pid":5,"owned_handles":[{"handle_u'
    b'64":12,"role":"control_pipe_read"},{"handle_u64":13,"role":"cont'
    b'rol_pipe_write"}],"packet_sha256":"00000000000000000000000000000'
    b'00000000000000000000000000000000000","pending_call":{"api":"Read'
    b'File","arguments":[{"kind":"handle64","name":"hFile","value":12}'
    b',{"kind":"pointer","name":"lpBuffer","value":{"address_u64":1001'
    b',"pointee_kind":"byte_buffer","storage_before_hex":"00","storage'
    b'_bytes_u32":1}},{"kind":"u32","name":"nNumberOfBytesToRead","val'
    b'ue":1},{"kind":"pointer","name":"lpNumberOfBytesRead","value":{"'
    b'address_u64":1003,"pointee_kind":"dword_out","storage_before_hex'
    b'":"00000000","storage_bytes_u32":4}},{"kind":"pointer","name":"l'
    b'pOverlapped","value":{"address_u64":0,"pointee_kind":"none","sto'
    b'rage_before_hex":null,"storage_bytes_u32":0}}],"input_buffers":['
    b'{"capacity_bytes":1,"full_buffer_hex":"00","output_validity":"st'
    b'orage_only","parameter":"lpBuffer","projection_kind":"none","ret'
    b'urned_bytes":null,"valid_prefix_bytes":null},{"capacity_bytes":4'
    b',"full_buffer_hex":"00000000","output_validity":"storage_only","'
    b'parameter":"lpNumberOfBytesRead","projection_kind":"none","retur'
    b'ned_bytes":null,"valid_prefix_bytes":null}],"source_selector":"R'
    b'14/api_01_nf-fileapi-readfile.md:ReadFile","started_monotonic_ns'
    b'":6},"started_monotonic_ns":1,"version":"local-member-intake-boo'
    b'tstrap-pending-read-v2","worker_pid":7}'
)

_GOLDEN_MARKER_METADATA_ASCII = (
    b'{"authority_flags":[["source_authenticated",false],["collection_'
    b'receipt_authenticated",false],["native_runtime_authenticated",fa'
    b'lse],["native_abi_authenticated",false],["native_wire_authentica'
    b'ted",false],["native_header_authenticated",false],["native_eof_a'
    b'uthenticated",false],["feed_authenticated",false],["calendar_aut'
    b'henticated",false],["historical_read_authorized",false],["histor'
    b'ical_validation_authorized",false],["book_acceptance_authorized"'
    b',false],["event_acceptance_authorized",false],["feature_acceptan'
    b'ce_authorized",false],["account_authorized",false],["funding_aut'
    b'horized",false],["receipt_authorized",false],["cash_authorized",'
    b'false],["margin_authorized",false],["risk_authorized",false],["s'
    b'torage_authorized",false],["resume_authorized",false],["executio'
    b'n_authorized",false],["trading_authorized",false],["training_aut'
    b'horized",false],["scoring_authorized",false],["independent_valid'
    b'ation_authorized",false],["promotion_authorized",false]],"case_i'
    b'd":"blocked_owned_pipe_read","completed_api_trace":[{"api":"Crea'
    b'tePipe","arguments":[{"kind":"pointer","name":"hReadPipe","value'
    b'":{"address_u64":1000,"pointee_kind":"handle_out","storage_befor'
    b'e_hex":"","storage_bytes_u32":8}},{"kind":"pointer","name":"hWri'
    b'tePipe","value":{"address_u64":1001,"pointee_kind":"handle_out",'
    b'"storage_before_hex":"","storage_bytes_u32":8}},{"kind":"pointer'
    b'","name":"lpPipeAttributes","value":{"address_u64":1002,"pointee'
    b'_kind":"security_attributes","storage_before_hex":"","storage_by'
    b'tes_u32":24}},{"kind":"u32","name":"nSize","value":65536}],"ende'
    b'd_monotonic_ns":2,"ordinal":0,"output_buffers":[{"capacity_bytes'
    b'":8,"full_buffer_hex":"","output_validity":"storage_only","param'
    b'eter":"hReadPipe","projection_kind":"none","returned_bytes":null'
    b',"valid_prefix_bytes":null},{"capacity_bytes":8,"full_buffer_hex'
    b'":"","output_validity":"storage_only","parameter":"hWritePipe","'
    b'projection_kind":"none","returned_bytes":null,"valid_prefix_byte'
    b's":null},{"capacity_bytes":24,"full_buffer_hex":"","output_valid'
    b'ity":"storage_only","parameter":"lpPipeAttributes","projection_k'
    b'ind":"none","returned_bytes":null,"valid_prefix_bytes":null}],"p'
    b'hase":"resumed","return":{"kind":"bool32","raw_i64":1,"raw_u64":'
    b'null,"win32_error_u32":null},"saved_error_seed":null,"source_sel'
    b'ector":"R15/namedpipeapi_nf-namedpipeapi-createpipe.md:CreatePip'
    b'e","started_monotonic_ns":1}],"go_observation":{"binding_initial'
    b'ization":[{"api_name":"ReadFile","completed":true,"constructor_o'
    b'rdinal":0,"ended_monotonic_ns":4,"exception":null,"exposed_addre'
    b'ss_u64":200,"lookup_kind":"ctypes_library_item","native_call_obs'
    b'ervation":"not_exposed","ordinal":0,"owner_role":"worker","sourc'
    b'e_selector":"R15/cpython_31210_ctypes_init.py.txt:CDLL.__getitem'
    b'__/_FuncPtr","started_monotonic_ns":3}],"data_reads":[{"api_ordi'
    b'nal":0,"buffer_observations":[{"capacity_bytes":1,"full_buffer_h'
    b'ex":"","output_validity":"documented_valid","parameter":"lpBuffe'
    b'r","projection_kind":"byte_prefix","returned_bytes":1,"valid_pre'
    b'fix_bytes":1},{"capacity_bytes":4,"full_buffer_hex":"","output_v'
    b'alidity":"documented_valid","parameter":"lpNumberOfBytesRead","p'
    b'rojection_kind":"u32","returned_bytes":4,"valid_prefix_bytes":4}'
    b'],"offset_u32":0,"ordinal":0,"requested_count_u32":1,"return":{"'
    b'kind":"bool32","raw_i64":1,"raw_u64":null,"win32_error_u32":null'
    b'},"returned_count_u32":1}],"eof_probe":{"api_ordinal":1,"buffer_'
    b'observations":[{"capacity_bytes":1,"full_buffer_hex":"","output_'
    b'validity":"storage_only","parameter":"lpBuffer","projection_kind'
    b'":"none","returned_bytes":null,"valid_prefix_bytes":null},{"capa'
    b'city_bytes":4,"full_buffer_hex":"","output_validity":"storage_on'
    b'ly","parameter":"lpNumberOfBytesRead","projection_kind":"none","'
    b'returned_bytes":null,"valid_prefix_bytes":null}],"offset_u32":48'
    b',"ordinal":1,"requested_count_u32":1,"return":{"kind":"bool32","'
    b'raw_i64":0,"raw_u64":null,"win32_error_u32":109},"returned_count'
    b'_u32":null},"initialization":[{"arguments":{"handle":null,"mode"'
    b':0,"name":"C:\\\\Windows\\\\System32\\\\kernel32.dll","use_errno'
    b'":false,"use_last_error":true,"winmode":2304},"completed":true,"'
    b'constructor":"ctypes.WinDLL","ended_monotonic_ns":2,"exception":'
    b'null,"exposed_handle_u64":100,"native_call_observation":"not_exp'
    b'osed","ordinal":0,"owner_role":"worker","reference_disposition":'
    b'"process_lifetime_bootstrap","source_selector":"R15/cpython_3121'
    b'0_ctypes_init.py.txt:CDLL.__init__/WinDLL","started_monotonic_ns'
    b'":1}],"packet_hex":"","stdin_close":{"close_attempted":true,"clo'
    b'se_bool_i32":1,"disposition":"closed","handle_u64":11,"ordinal":'
    b'0,"role":"control_stdin_read","win32_error_u32":null}},"marker_s'
    b'ha256":"ffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
    b'ffffffff","nonce_hex":"","observed_parent_pid":5,"owned_handles"'
    b':[{"handle_u64":12,"role":"control_pipe_read"},{"handle_u64":13,'
    b'"role":"control_pipe_write"}],"packet_sha256":"00000000000000000'
    b'00000000000000000000000000000000000000000000000","pending_call":'
    b'{"api":"ReadFile","arguments":[{"kind":"handle64","name":"hFile"'
    b',"value":12},{"kind":"pointer","name":"lpBuffer","value":{"addre'
    b'ss_u64":1001,"pointee_kind":"byte_buffer","storage_before_hex":"'
    b'","storage_bytes_u32":1}},{"kind":"u32","name":"nNumberOfBytesTo'
    b'Read","value":1},{"kind":"pointer","name":"lpNumberOfBytesRead",'
    b'"value":{"address_u64":1003,"pointee_kind":"dword_out","storage_'
    b'before_hex":"","storage_bytes_u32":4}},{"kind":"pointer","name":'
    b'"lpOverlapped","value":{"address_u64":0,"pointee_kind":"none","s'
    b'torage_before_hex":null,"storage_bytes_u32":0}}],"input_buffers"'
    b':[{"capacity_bytes":1,"full_buffer_hex":"","output_validity":"st'
    b'orage_only","parameter":"lpBuffer","projection_kind":"none","ret'
    b'urned_bytes":null,"valid_prefix_bytes":null},{"capacity_bytes":4'
    b',"full_buffer_hex":"","output_validity":"storage_only","paramete'
    b'r":"lpNumberOfBytesRead","projection_kind":"none","returned_byte'
    b's":null,"valid_prefix_bytes":null}],"source_selector":"R14/api_0'
    b'1_nf-fileapi-readfile.md:ReadFile","started_monotonic_ns":6},"st'
    b'arted_monotonic_ns":1,"version":"local-member-intake-bootstrap-p'
    b'ending-read-v2","worker_pid":7}'
)

_GOLDEN_MARKER_ROWS = [
    {
        "path": ["completed_api_trace", 0, "arguments", 0, "value", "storage_before_hex"],
        "category": "B",
        "raw_byte_length": 8,
    },
    {
        "path": ["completed_api_trace", 0, "arguments", 1, "value", "storage_before_hex"],
        "category": "B",
        "raw_byte_length": 8,
    },
    {
        "path": ["completed_api_trace", 0, "arguments", 2, "value", "storage_before_hex"],
        "category": "H",
        "raw_byte_length": 24,
    },
    {
        "path": ["completed_api_trace", 0, "output_buffers", 0, "full_buffer_hex"],
        "category": "B",
        "raw_byte_length": 8,
    },
    {
        "path": ["completed_api_trace", 0, "output_buffers", 1, "full_buffer_hex"],
        "category": "B",
        "raw_byte_length": 8,
    },
    {
        "path": ["completed_api_trace", 0, "output_buffers", 2, "full_buffer_hex"],
        "category": "H",
        "raw_byte_length": 24,
    },
    {
        "path": ["go_observation", "data_reads", 0, "buffer_observations", 0, "full_buffer_hex"],
        "category": "B",
        "raw_byte_length": 1,
    },
    {
        "path": ["go_observation", "data_reads", 0, "buffer_observations", 1, "full_buffer_hex"],
        "category": "B",
        "raw_byte_length": 4,
    },
    {
        "path": ["go_observation", "eof_probe", "buffer_observations", 0, "full_buffer_hex"],
        "category": "B",
        "raw_byte_length": 1,
    },
    {
        "path": ["go_observation", "eof_probe", "buffer_observations", 1, "full_buffer_hex"],
        "category": "B",
        "raw_byte_length": 4,
    },
    {"path": ["go_observation", "packet_hex"], "category": "H", "raw_byte_length": 48},
    {"path": ["nonce_hex"], "category": "H", "raw_byte_length": 16},
    {
        "path": ["pending_call", "arguments", 1, "value", "storage_before_hex"],
        "category": "B",
        "raw_byte_length": 1,
    },
    {
        "path": ["pending_call", "arguments", 3, "value", "storage_before_hex"],
        "category": "B",
        "raw_byte_length": 4,
    },
    {
        "path": ["pending_call", "input_buffers", 0, "full_buffer_hex"],
        "category": "B",
        "raw_byte_length": 1,
    },
    {
        "path": ["pending_call", "input_buffers", 1, "full_buffer_hex"],
        "category": "B",
        "raw_byte_length": 4,
    },
]


def make_go():
    return json.loads(_GOLDEN_PAYLOAD_BODY_ASCII)["go_observation"]


def make_worker(trace=None, payload_hex="7b7d"):
    body = json.loads(_GOLDEN_WORKER_BODY_ASCII)
    body["worker_pre_emission_api_trace"] = (
        [make_trace("GetProcAddress")] if trace is None else _clone(trace)
    )
    body["payload_hex"] = payload_hex
    return body


def make_payload(go=None, control_payload_hex="00"):
    body = json.loads(_GOLDEN_PAYLOAD_BODY_ASCII)
    body["go_observation"] = make_go() if go is None else _clone(go)
    body["control_payload_hex"] = control_payload_hex
    return body


def make_marker(trace=None, go=None):
    body = json.loads(_GOLDEN_MARKER_BODY_ASCII)
    body["completed_api_trace"] = [make_trace("CreatePipe")] if trace is None else _clone(trace)
    body["go_observation"] = make_go() if go is None else _clone(go)
    return body


def _measurement(path, quantity, actual, limit):
    return {
        "path": list(path),
        "quantity": quantity,
        "actual": actual,
        "limit": limit,
        "within": actual <= limit,
    }


def _fixed_expected(container, body_ascii, metadata_ascii, rows, totals, measures):
    """Assemble only complete fixed literals, without deriving golden totals."""
    return {
        "version": AUDIT_VERSION,
        "container": container,
        "basis": _clone(BASIS),
        "body": json.loads(body_ascii),
        "body_ascii": body_ascii,
        "metadata": json.loads(metadata_ascii),
        "metadata_ascii": metadata_ascii,
        "occurrences": _clone(rows),
        "totals": _clone(totals),
        "measurements": _clone(measures),
        "over_limits": [],
        "not_validated": list(NOT_VALIDATED),
        "authority_flags": _clone(FLAGS),
    }


def golden_cases():
    """Three fresh complete literal expectations, independent of all code under test."""
    worker_measures = [
        {"path": [], "quantity": "B", "actual": 0, "limit": 12582912, "within": True},
        {"path": [], "quantity": "H", "actual": 22, "limit": 2097152, "within": True},
        {"path": [], "quantity": "M", "actual": 2141, "limit": 8388608, "within": True},
        {"path": [], "quantity": "full", "actual": 2185, "limit": 1048576, "within": True},
        {
            "path": ["payload_hex"],
            "quantity": "decoded_bytes",
            "actual": 2,
            "limit": 262144,
            "within": True,
        },
    ]
    payload_measures = [
        {"path": [], "quantity": "B", "actual": 10, "limit": 12582912, "within": True},
        {"path": [], "quantity": "H", "actual": 49, "limit": 2097152, "within": True},
        {"path": [], "quantity": "M", "actual": 2221, "limit": 8388608, "within": True},
        {"path": [], "quantity": "full", "actual": 2339, "limit": 262144, "within": True},
        {
            "path": ["go_observation", "initialization", 0],
            "quantity": "full",
            "actual": 480,
            "limit": 32768,
            "within": True,
        },
    ]
    marker_measures = [
        {"path": [], "quantity": "B", "actual": 52, "limit": 12582912, "within": True},
        {"path": [], "quantity": "H", "actual": 112, "limit": 2097152, "within": True},
        {"path": [], "quantity": "M", "actual": 5977, "limit": 8388608, "within": True},
        {"path": [], "quantity": "full", "actual": 6305, "limit": 262144, "within": True},
        {
            "path": ["go_observation", "initialization", 0],
            "quantity": "full",
            "actual": 480,
            "limit": 32768,
            "within": True,
        },
    ]
    rows = [
        (
            "worker",
            "BootstrapResult",
            _GOLDEN_WORKER_BODY_ASCII,
            _GOLDEN_WORKER_METADATA_ASCII,
            _GOLDEN_WORKER_ROWS,
            {"D": 0, "B": 0, "H": 22, "R": 0, "M": 2141, "full": 2185},
            worker_measures,
        ),
        (
            "payload",
            "ResultPayload",
            _GOLDEN_PAYLOAD_BODY_ASCII,
            _GOLDEN_PAYLOAD_METADATA_ASCII,
            _GOLDEN_PAYLOAD_ROWS,
            {"D": 0, "B": 10, "H": 49, "R": 0, "M": 2221, "full": 2339},
            payload_measures,
        ),
        (
            "marker",
            "PendingReadMarker",
            _GOLDEN_MARKER_BODY_ASCII,
            _GOLDEN_MARKER_METADATA_ASCII,
            _GOLDEN_MARKER_ROWS,
            {"D": 0, "B": 52, "H": 112, "R": 0, "M": 5977, "full": 6305},
            marker_measures,
        ),
    ]
    return [
        {
            "id": identity,
            "container": container,
            "body": json.loads(body_ascii),
            "expected": _fixed_expected(
                container, body_ascii, metadata_ascii, raw_rows, totals, measures
            ),
        }
        for identity, container, body_ascii, metadata_ascii, raw_rows, totals, measures in rows
    ]


def _path_order(path):
    return tuple((0, part) if type(part) is str else (1, part) for part in path)


def expected_from_paths(container, body, raw_rows):
    """Generated-case expectation from explicitly supplied independent paths.

    This does not discover raw paths or classify APIs. The test author must supply
    the complete physical path/category/extent roster independently. It is not an
    input validator and must not be used to infer that malformed input is valid.
    """
    snapshot = _clone(body)
    metadata = _clone(body)
    occurrences = sorted(_clone(raw_rows), key=lambda row: _path_order(row["path"]))
    buffer_bytes = 0
    hex_bytes = 0
    for row in occurrences:
        selected = metadata
        for part in row["path"][:-1]:
            selected = selected[part]
        selected[row["path"][-1]] = ""
        if row["category"] == "B":
            buffer_bytes += row["raw_byte_length"]
        elif row["category"] == "H":
            hex_bytes += row["raw_byte_length"]
        else:
            raise AssertionError("test oracle category")
    body_ascii = independent_canonical(snapshot)
    metadata_ascii = independent_canonical(metadata)
    full_limit = 1048576 if container == "BootstrapResult" else 262144
    measurements = [
        _measurement([], "B", buffer_bytes, 12582912),
        _measurement([], "H", hex_bytes, 2097152),
        _measurement([], "M", len(metadata_ascii), 8388608),
        _measurement([], "full", len(body_ascii), full_limit),
    ]
    if container == "BootstrapResult":
        measurements.append(
            _measurement(
                ["payload_hex"], "decoded_bytes", len(snapshot["payload_hex"]) // 2, 262144
            )
        )
    else:
        for index, initialization in enumerate(snapshot["go_observation"]["initialization"]):
            measurements.append(
                _measurement(
                    ["go_observation", "initialization", index],
                    "full",
                    len(independent_canonical(initialization)),
                    32768,
                )
            )
    return {
        "version": AUDIT_VERSION,
        "container": container,
        "basis": _clone(BASIS),
        "body": snapshot,
        "body_ascii": body_ascii,
        "metadata": metadata,
        "metadata_ascii": metadata_ascii,
        "occurrences": occurrences,
        "totals": {
            "D": 0,
            "B": buffer_bytes,
            "H": hex_bytes,
            "R": 0,
            "M": len(metadata_ascii),
            "full": len(body_ascii),
        },
        "measurements": measurements,
        "over_limits": [_clone(row) for row in measurements if not row["within"]],
        "not_validated": list(NOT_VALIDATED),
        "authority_flags": _clone(FLAGS),
    }


# Backwards-compatible private coordination alias; no classification is added.
expected_audit = expected_from_paths
