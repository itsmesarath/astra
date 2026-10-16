"""Registered harmless Windows child controls; not a native codec provider.

Root owns launches. Job limits constrain committed memory and user-mode CPU,
not all RAM, filesystem/network access, or exact real-time exit. No DBN/Zstd
library is imported. Parent-death cleanup has not been empirically exercised.

API/layout sources:
https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw
https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute
https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information
https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list
https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess
https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-peeknamedpipe
https://learn.microsoft.com/en-us/cpp/build/x64-software-conventions
"""

import ctypes as C
import hashlib
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

MEMORY_BYTES = 268435456
USER_TIME_100NS = 50000000
WORK_SECONDS = 12.0
TOTAL_SECONDS = 15.0
OUTPUT_BYTES = 4194304
READ_BYTES = 65536
LIMIT_FLAGS = 0x230E
CREATION_FLAGS = 0x08080004 | 0x00000400
REGISTERED_PYTHON = Path("C:/Users/pabta/AppData/Local/Programs/Python/Python312/python.exe")
REGISTERED_PYTHON_SHA256 = "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a"
ROOT = Path(__file__).resolve().parents[1]
REGISTERED_SCRIPT = ROOT / "scripts/native_profile_probe_20261012_1.py"
REGISTERED_CONTROLS = frozenset(
    {
        "stub_success",
        "stub_timeout",
        "stub_memory",
        "stub_crash",
        "stub_output",
        "native_identity",
        "native_dbn",
        "native_zstd",
        "native_enums",
        "native_boundaries",
        "native_capacity",
        "native_zstd_partitions",
        "native_zstd_capacity",
        "native_composed",
    }
)
DWORD = C.c_uint32
WORD = C.c_uint16
BOOL = C.c_int32
HANDLE = C.c_void_p
SIZE_T = C.c_size_t
ULONG64 = C.c_uint64
LONG64 = C.c_int64
VOID = C.c_void_p
INVALID_HANDLE = C.c_void_p(-1).value
WAIT_TIMEOUT = 258
TERMINATION_CODE = 0xE0000001


class SecurityAttributes(C.Structure):
    _fields_ = [("length", DWORD), ("descriptor", VOID), ("inherit", BOOL)]


class StartupInfo(C.Structure):
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


class StartupInfoEx(C.Structure):
    _fields_ = [("startup", StartupInfo), ("attributes", VOID)]


class ProcessInformation(C.Structure):
    _fields_ = [("process", HANDLE), ("thread", HANDLE), ("pid", DWORD), ("tid", DWORD)]


class BasicLimits(C.Structure):
    _fields_ = [
        ("process_time", LONG64),
        ("job_time", LONG64),
        ("flags", DWORD),
        ("minimum_working_set", SIZE_T),
        ("maximum_working_set", SIZE_T),
        ("active_processes", DWORD),
        ("affinity", SIZE_T),
        ("priority", DWORD),
        ("scheduling", DWORD),
    ]


class IoCounters(C.Structure):
    _fields_ = [
        ("read_operations", ULONG64),
        ("write_operations", ULONG64),
        ("other_operations", ULONG64),
        ("read_bytes", ULONG64),
        ("write_bytes", ULONG64),
        ("other_bytes", ULONG64),
    ]


class ExtendedLimits(C.Structure):
    _fields_ = [
        ("basic", BasicLimits),
        ("io", IoCounters),
        ("process_memory", SIZE_T),
        ("job_memory", SIZE_T),
        ("peak_process_memory", SIZE_T),
        ("peak_job_memory", SIZE_T),
    ]


class Accounting(C.Structure):
    _fields_ = [
        ("user_time", LONG64),
        ("kernel_time", LONG64),
        ("period_user_time", LONG64),
        ("period_kernel_time", LONG64),
        ("page_faults", DWORD),
        ("total_processes", DWORD),
        ("active_processes", DWORD),
        ("terminated_processes", DWORD),
    ]


class ProcessIdList(C.Structure):
    _fields_ = [("assigned", DWORD), ("listed", DWORD), ("pids", SIZE_T * 16)]


class FileTime(C.Structure):
    _fields_ = [("low", DWORD), ("high", DWORD)]


class ProcessEntry(C.Structure):
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


def _utc():
    return datetime.now(UTC)


def _stamp():
    return _utc().isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sha_file(path, maximum):
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        while block := stream.read(READ_BYTES):
            total += len(block)
            if total > maximum:
                raise ValueError("registered artifact exceeds its read bound")
            digest.update(block)
    return digest.hexdigest()


def _pin(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _abi():
    expected = (
        (SecurityAttributes, 24),
        (StartupInfo, 104),
        (StartupInfoEx, 112),
        (ProcessInformation, 24),
        (BasicLimits, 64),
        (IoCounters, 48),
        (ExtendedLimits, 144),
        (Accounting, 48),
        (ProcessIdList, 136),
        (FileTime, 8),
        (ProcessEntry, 568),
    )
    if os.name != "nt" or sys.maxsize != 9223372036854775807:
        raise ValueError("only the registered 64-bit Windows ABI is supported")
    if C.sizeof(HANDLE) != 8 or C.sizeof(C.c_wchar) != 2:
        raise ValueError("unexpected Windows pointer or WCHAR width")
    if any(C.sizeof(kind) != size for kind, size in expected):
        raise ValueError("Windows structure size mismatch")
    offsets = (
        (StartupInfo.stdin, 80),
        (StartupInfoEx.attributes, 104),
        (BasicLimits.affinity, 48),
        (ExtendedLimits.process_memory, 112),
        (ProcessIdList.pids, 8),
        (ProcessEntry.parent_pid, 32),
        (ProcessEntry.exe_name, 44),
    )
    if any(field.offset != offset for field, offset in offsets):
        raise ValueError("Windows structure offset mismatch")
    return {kind.__name__: size for kind, size in expected}


def _api():
    api = C.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
    ptr = C.POINTER
    signatures = {
        "CreateJobObjectW": ([VOID, C.c_wchar_p], HANDLE),
        "SetInformationJobObject": ([HANDLE, C.c_int, VOID, DWORD], BOOL),
        "QueryInformationJobObject": ([HANDLE, C.c_int, VOID, DWORD, ptr(DWORD)], BOOL),
        "CreatePipe": ([ptr(HANDLE), ptr(HANDLE), ptr(SecurityAttributes), DWORD], BOOL),
        "SetHandleInformation": ([HANDLE, DWORD, DWORD], BOOL),
        "CreateFileW": (
            [C.c_wchar_p, DWORD, DWORD, ptr(SecurityAttributes), DWORD, DWORD, HANDLE],
            HANDLE,
        ),
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
                ptr(StartupInfoEx),
                ptr(ProcessInformation),
            ],
            BOOL,
        ),
        "IsProcessInJob": ([HANDLE, HANDLE, ptr(BOOL)], BOOL),
        "ResumeThread": ([HANDLE], DWORD),
        "WaitForSingleObject": ([HANDLE, DWORD], DWORD),
        "GetExitCodeProcess": ([HANDLE, ptr(DWORD)], BOOL),
        "GetProcessTimes": (
            [HANDLE, ptr(FileTime), ptr(FileTime), ptr(FileTime), ptr(FileTime)],
            BOOL,
        ),
        "QueryFullProcessImageNameW": ([HANDLE, DWORD, C.c_wchar_p, ptr(DWORD)], BOOL),
        "GetCurrentProcess": ([], HANDLE),
        "GetCurrentProcessId": ([], DWORD),
        "CreateToolhelp32Snapshot": ([DWORD, DWORD], HANDLE),
        "Process32FirstW": ([HANDLE, ptr(ProcessEntry)], BOOL),
        "Process32NextW": ([HANDLE, ptr(ProcessEntry)], BOOL),
        "PeekNamedPipe": ([HANDLE, VOID, DWORD, ptr(DWORD), ptr(DWORD), ptr(DWORD)], BOOL),
        "ReadFile": ([HANDLE, VOID, DWORD, ptr(DWORD), VOID], BOOL),
        "TerminateJobObject": ([HANDLE, DWORD], BOOL),
        "TerminateProcess": ([HANDLE, DWORD], BOOL),
        "CloseHandle": ([HANDLE], BOOL),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(api, name, None)
        if function is None:
            raise ValueError("required Windows API is unavailable: " + name)
        function.argtypes = arguments
        function.restype = result
    return api


def _check(ok, operation):
    if not ok:
        raise C.WinError(C.get_last_error(), operation)


def _query(api, job, information_class, kind):
    value = kind()
    written = DWORD()
    _check(
        api.QueryInformationJobObject(
            job, information_class, C.byref(value), C.sizeof(value), C.byref(written)
        ),
        "QueryInformationJobObject",
    )
    if written.value != C.sizeof(value):
        raise ValueError("job query returned an unexpected structure length")
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


def _job_pids(api, job):
    """Complete bounded own-job membership, not a cumulative lifetime count."""
    value = ProcessIdList()
    written = DWORD()
    _check(
        api.QueryInformationJobObject(job, 3, C.byref(value), C.sizeof(value), C.byref(written)),
        "QueryInformationJobObject(process list)",
    )
    if (
        value.assigned != value.listed
        or value.listed > 16
        or not 8 + 8 * value.listed <= written.value <= C.sizeof(value)
    ):
        raise ValueError("own-job process list is incomplete or outside its byte bound")
    pids = [value.pids[index] for index in range(value.listed)]
    if any(pid == 0 for pid in pids) or len(set(pids)) != len(pids):
        raise ValueError("own-job process list contains invalid or duplicate identities")
    return pids


def _accounting_body(value):
    return {
        "total_user_time_100ns": value.user_time,
        "total_kernel_time_100ns": value.kernel_time,
        "total_processes": value.total_processes,
        "active_processes": value.active_processes,
        "terminated_processes": value.terminated_processes,
        "page_faults": value.page_faults,
    }


def _terminate_owned(api, job, process, *, in_job):
    """Request own-job termination; the caller must perform the bounded wait.

    Do not race a successful job termination with redundant process termination.
    The retained process fallback is only for a failed job request or membership
    that could not be proven. Every observed API failure remains in the receipt.
    """
    job_succeeded = bool(api.TerminateJobObject(job, TERMINATION_CODE))
    result = {
        "job_succeeded": job_succeeded,
        "job_error": None if job_succeeded else C.get_last_error(),
        "process_fallback_requested": False,
        "process_succeeded": None,
        "process_error": None,
    }
    if not job_succeeded or not in_job:
        state = api.WaitForSingleObject(process, 0)
        if state == WAIT_TIMEOUT:
            result["process_fallback_requested"] = True
            succeeded = bool(api.TerminateProcess(process, TERMINATION_CODE))
            result["process_succeeded"] = succeeded
            result["process_error"] = None if succeeded else C.get_last_error()
        elif state != 0:
            result["process_error"] = C.get_last_error()
    return result


def _times(api, process, exited=False):
    creation, exit_time, kernel, user = (FileTime() for _ in range(4))
    _check(
        api.GetProcessTimes(
            process, C.byref(creation), C.byref(exit_time), C.byref(kernel), C.byref(user)
        ),
        "GetProcessTimes",
    )
    return {
        "creation_filetime": (creation.high << 32) | creation.low,
        "exit_filetime": ((exit_time.high << 32) | exit_time.low) if exited else None,
        "user_time_100ns": (user.high << 32) | user.low,
        "kernel_time_100ns": (kernel.high << 32) | kernel.low,
    }


def _image(api, process):
    buffer = C.create_unicode_buffer(32768)
    length = DWORD(len(buffer))
    _check(
        api.QueryFullProcessImageNameW(process, 0, buffer, C.byref(length)),
        "QueryFullProcessImageNameW",
    )
    return buffer.value


def _parent_pid(api, child_pid):
    # Only the retained owned child's creator entry is selected or recorded.
    snapshot = api.CreateToolhelp32Snapshot(0x2, 0)
    if snapshot in (None, INVALID_HANDLE):
        raise C.WinError(C.get_last_error(), "CreateToolhelp32Snapshot")
    try:
        entry = ProcessEntry()
        entry.size = C.sizeof(entry)
        _check(api.Process32FirstW(snapshot, C.byref(entry)), "Process32FirstW")
        for _ in range(4096):
            if entry.pid == child_pid:
                return entry.parent_pid
            if not api.Process32NextW(snapshot, C.byref(entry)):
                error = C.get_last_error()
                if error != 18:
                    raise C.WinError(error, "Process32NextW")
                break
        raise ValueError("owned child creator entry not found within the bound")
    finally:
        _check(api.CloseHandle(snapshot), "CloseHandle(snapshot)")


def _create_process(api, application, command_line, environment, cwd, startup, process_info):
    """Single creation seam; bad-pin phase tests may replace it with a sentinel."""
    _check(
        api.CreateProcessW(
            application,
            command_line,
            None,
            None,
            True,
            CREATION_FLAGS,
            environment,
            cwd,
            C.byref(startup),
            C.byref(process_info),
        ),
        "CreateProcessW",
    )


def _resume_thread(api, thread):
    """Single resume seam after all pre-resume identity and budget checks."""
    return api.ResumeThread(thread)


def run_owned_case(
    *,
    python_exe,
    expected_python_sha256,
    script_path,
    expected_script_sha256,
    script_args,
    case_id,
    hard_end_utc,
):
    """Return one bounded harmless-control receipt and its retained output bytes."""
    started = time.perf_counter()
    output = bytearray()
    receipt = {
        "case_id": case_id,
        "disposition": "setup_refused",
        "created": False,
        "resumed": False,
        "exit_code": None,
        "in_job_before_resume": False,
        "resume_previous_count": None,
        "parent_pid": os.getpid(),
        "parent_creation_filetime": None,
        "child_pid": None,
        "child_tid": None,
        "child_image": None,
        "child_creation_filetime": None,
        "child_parent_pid": None,
        "argv": None,
        "cwd": str(ROOT),
        "hard_end_utc": hard_end_utc,
        "started_utc": _stamp(),
        "configured_limits": None,
        "queried_limits": None,
        "work_seconds": WORK_SECONDS,
        "total_seconds": TOTAL_SECONDS,
        "output_limit_bytes": OUTPUT_BYTES,
        "read_chunk_bytes": READ_BYTES,
        "kill_on_job_close_queried": False,
        "parent_death_empirically_tested": False,
        "termination_reason": None,
        "termination_requested": False,
        "termination_attempt": None,
        "process_exited": False,
        "output_complete": False,
        "output_bytes": 0,
        "output_sha256": None,
        "output_hash_scope": "retained_prefix",
        "job_accounting_initial": None,
        "job_accounting_before_resume": None,
        "job_accounting": None,
        "final_active_processes": None,
        "job_process_ids_initial": None,
        "job_process_ids_before_resume": None,
        "job_process_ids_final": None,
        "peak_process_memory_bytes": None,
        "peak_job_memory_bytes": None,
        "child_times": None,
        "abi_sizes": None,
        "error": None,
        "cleanup_errors": [],
        "closed_handles": [],
        "native_codec_imported": None
        if case_id
        in {
            "native_identity",
            "native_dbn",
            "native_zstd",
            "native_enums",
            "native_boundaries",
            "native_capacity",
            "native_zstd_partitions",
            "native_zstd_capacity",
            "native_composed",
        }
        else False,
        "native_profile_closed": False,
    }
    api = None
    handles = {}
    attributes = None
    attributes_initialized = False
    process_info = ProcessInformation()
    hard_end = None

    def close(name):
        handle = handles.pop(name, None)
        if handle is not None:
            if api.CloseHandle(handle):
                receipt["closed_handles"].append(name)
            else:
                receipt["cleanup_errors"].append(
                    {"operation": "CloseHandle(" + name + ")", "winerror": C.get_last_error()}
                )

    def terminate(reason):
        if receipt["termination_requested"]:
            return
        receipt["termination_requested"] = True
        receipt["termination_reason"] = reason
        attempt = _terminate_owned(
            api, handles["job"], handles["process"], in_job=receipt["in_job_before_resume"]
        )
        receipt["termination_attempt"] = attempt
        if attempt["job_error"] is not None:
            receipt["cleanup_errors"].append(
                {"operation": "TerminateJobObject", "winerror": attempt["job_error"]}
            )

    try:
        if not _pin(expected_python_sha256) or not _pin(expected_script_sha256):
            raise ValueError("expected artifact pins must be lowercase SHA256")
        if type(python_exe) is not str or type(script_path) is not str:
            raise ValueError("registered paths must be exact strings")
        executable = Path(python_exe).resolve(strict=True)
        script = Path(script_path).resolve(strict=True)
        if executable != REGISTERED_PYTHON.resolve(strict=True):
            raise ValueError("unregistered direct Python executable")
        if script != REGISTERED_SCRIPT.resolve(strict=True):
            raise ValueError("unregistered harmless control script")
        if expected_python_sha256 != REGISTERED_PYTHON_SHA256:
            raise ValueError("executable pin does not match the fixed registration")
        if _sha_file(executable, 67108864) != expected_python_sha256:
            raise ValueError("executable raw pin mismatch")
        if _sha_file(script, 1048576) != expected_script_sha256:
            raise ValueError("script raw pin mismatch")
        if type(case_id) is not str or case_id not in REGISTERED_CONTROLS:
            raise ValueError("unregistered harmless control")
        if type(script_args) is not tuple or script_args != (case_id,):
            raise ValueError("arguments must be exactly the registered control choice")
        if type(hard_end_utc) is not str or len(hard_end_utc) != 20:
            raise ValueError("hard end must be exact second-resolution UTC text")
        hard_end = datetime.strptime(hard_end_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        if hard_end.strftime("%Y-%m-%dT%H:%M:%SZ") != hard_end_utc:
            raise ValueError("hard end must be canonical UTC text")
        if (hard_end - _utc()).total_seconds() < TOTAL_SECONDS:
            raise ValueError("insufficient work and teardown reserve before hard end")
        receipt["abi_sizes"] = _abi()
        api = _api()
        receipt["parent_creation_filetime"] = _times(api, api.GetCurrentProcess())[
            "creation_filetime"
        ]
        if api.GetCurrentProcessId() != receipt["parent_pid"]:
            raise ValueError("parent identity mismatch")

        handles["job"] = api.CreateJobObjectW(None, None)
        if not handles["job"]:
            handles.pop("job")
            raise C.WinError(C.get_last_error(), "CreateJobObjectW")
        limits = ExtendedLimits()
        limits.basic.flags = LIMIT_FLAGS
        limits.basic.active_processes = 1
        limits.basic.process_time = USER_TIME_100NS
        limits.basic.job_time = USER_TIME_100NS
        limits.process_memory = MEMORY_BYTES
        limits.job_memory = MEMORY_BYTES
        _check(
            api.SetInformationJobObject(handles["job"], 9, C.byref(limits), C.sizeof(limits)),
            "SetInformationJobObject",
        )
        receipt["configured_limits"] = _limits(limits)
        receipt["queried_limits"] = _limits(_query(api, handles["job"], 9, ExtendedLimits))
        if receipt["queried_limits"] != receipt["configured_limits"]:
            raise ValueError("configured job limits did not survive query")
        end_action = _query(api, handles["job"], 6, DWORD)
        if end_action.value != 0:
            raise ValueError("job CPU limit does not have terminating end action")
        receipt["kill_on_job_close_queried"] = True
        initial = _query(api, handles["job"], 1, Accounting)
        receipt["job_accounting_initial"] = _accounting_body(initial)
        receipt["job_process_ids_initial"] = _job_pids(api, handles["job"])
        if initial.active_processes != 0 or receipt["job_process_ids_initial"]:
            raise ValueError("fresh own job is not empty before creation")

        security = SecurityAttributes(C.sizeof(SecurityAttributes), None, True)
        reader, writer = HANDLE(), HANDLE()
        _check(
            api.CreatePipe(C.byref(reader), C.byref(writer), C.byref(security), READ_BYTES),
            "CreatePipe",
        )
        handles["reader"], handles["writer"] = reader.value, writer.value
        _check(api.SetHandleInformation(handles["reader"], 1, 0), "SetHandleInformation")
        nul = api.CreateFileW("NUL", 0x80000000, 3, C.byref(security), 3, 0, None)
        if nul in (None, INVALID_HANDLE):
            raise C.WinError(C.get_last_error(), "CreateFileW(NUL)")
        handles["nul"] = nul

        attribute_size = SIZE_T()
        C.set_last_error(0)
        result = api.InitializeProcThreadAttributeList(None, 2, 0, C.byref(attribute_size))
        if result or C.get_last_error() != 122 or not 0 < attribute_size.value <= 65536:
            raise ValueError("unexpected process attribute sizing response")
        attributes = C.create_string_buffer(attribute_size.value)
        if C.addressof(attributes) % 8:
            raise ValueError("process attribute allocation is not pointer-aligned")
        _check(
            api.InitializeProcThreadAttributeList(attributes, 2, 0, C.byref(attribute_size)),
            "InitializeProcThreadAttributeList",
        )
        attributes_initialized = True
        job_list = (HANDLE * 1)(handles["job"])
        handle_list = (HANDLE * 2)(handles["writer"], handles["nul"])
        # WinSDK WinBase.h defines input attributes 13 (job) and 2 (handles).
        _check(
            api.UpdateProcThreadAttribute(
                attributes, 0, 0x0002000D, job_list, C.sizeof(job_list), None, None
            ),
            "UpdateProcThreadAttribute(JOB_LIST)",
        )
        _check(
            api.UpdateProcThreadAttribute(
                attributes, 0, 0x00020002, handle_list, C.sizeof(handle_list), None, None
            ),
            "UpdateProcThreadAttribute(HANDLE_LIST)",
        )
        startup = StartupInfoEx()
        startup.startup.cb = C.sizeof(startup)
        startup.startup.flags = 0x100
        startup.startup.stdin = handles["nul"]
        startup.startup.stdout = startup.startup.stderr = handles["writer"]
        startup.attributes = C.cast(attributes, VOID)
        argv = [str(executable), "-I", "-S", "-B", str(script), *script_args]
        receipt["argv"] = argv
        command_line = C.create_unicode_buffer(subprocess.list2cmdline(argv))
        system_root = os.environ.get("SystemRoot")
        if not system_root or "\0" in system_root or not os.path.isabs(system_root):
            raise ValueError("required SystemRoot environment entry is unavailable")
        environment = C.create_unicode_buffer("SystemRoot=" + system_root + "\0\0")
        elapsed_setup = time.perf_counter() - started
        remaining_reserve = max(0.0, WORK_SECONDS - elapsed_setup) + 3.0
        if elapsed_setup >= WORK_SECONDS or (hard_end - _utc()).total_seconds() < remaining_reserve:
            raise ValueError("setup exhausted the registered work budget")
        _create_process(
            api, str(executable), command_line, environment, str(ROOT), startup, process_info
        )
        handles["process"], handles["thread"] = process_info.process, process_info.thread
        receipt["created"] = True
        receipt["child_pid"], receipt["child_tid"] = process_info.pid, process_info.tid
        close("writer")
        close("nul")
        receipt["child_image"] = _image(api, handles["process"])
        receipt["child_creation_filetime"] = _times(api, handles["process"])["creation_filetime"]
        receipt["child_parent_pid"] = _parent_pid(api, process_info.pid)
        if (
            os.path.normcase(receipt["child_image"]) != os.path.normcase(str(executable))
            or receipt["child_parent_pid"] != receipt["parent_pid"]
        ):
            raise ValueError("retained child image or creator identity mismatch")
        in_job = BOOL()
        _check(
            api.IsProcessInJob(handles["process"], handles["job"], C.byref(in_job)),
            "IsProcessInJob",
        )
        receipt["in_job_before_resume"] = bool(in_job.value)
        if not receipt["in_job_before_resume"]:
            raise ValueError("retained child is not in the own job")
        checked = _limits(_query(api, handles["job"], 9, ExtendedLimits))
        if checked != receipt["configured_limits"] or receipt["cleanup_errors"]:
            raise ValueError("pre-resume job limits or handle cleanup mismatch")
        receipt["job_accounting_before_resume"] = _accounting_body(
            _query(api, handles["job"], 1, Accounting)
        )
        receipt["job_process_ids_before_resume"] = _job_pids(api, handles["job"])
        if (
            receipt["job_process_ids_before_resume"] != [process_info.pid]
            or receipt["job_accounting_before_resume"]["active_processes"] != 1
        ):
            raise ValueError("own job does not contain only the retained suspended child")
        elapsed = time.perf_counter() - started
        required_reserve = WORK_SECONDS - elapsed + (TOTAL_SECONDS - WORK_SECONDS)
        if elapsed >= WORK_SECONDS or (hard_end - _utc()).total_seconds() < required_reserve:
            raise ValueError("pre-resume work or hard-end teardown reserve exhausted")
        previous = _resume_thread(api, handles["thread"])
        receipt["resume_previous_count"] = previous
        if previous != 1:
            raise ValueError("primary thread was not in the single suspended state")
        receipt["resumed"] = True

        buffer = C.create_string_buffer(READ_BYTES)
        while True:
            if time.perf_counter() - started >= WORK_SECONDS or _utc() >= hard_end:
                receipt["disposition"] = "timeout"
                terminate("work_timeout")
                break
            available = DWORD()
            if not api.PeekNamedPipe(handles["reader"], None, 0, None, C.byref(available), None):
                error = C.get_last_error()
                if error != 109:
                    raise C.WinError(error, "PeekNamedPipe")
                receipt["output_complete"] = True
            if available.value > OUTPUT_BYTES - len(output):
                receipt["disposition"] = "output_limit"
                terminate("output_limit")
                break
            if available.value:
                count = DWORD()
                requested = min(available.value, READ_BYTES, OUTPUT_BYTES - len(output))
                _check(
                    api.ReadFile(handles["reader"], buffer, requested, C.byref(count), None),
                    "ReadFile",
                )
                if not 0 < count.value <= requested:
                    raise ValueError("output read returned an invalid bounded count")
                output.extend(buffer.raw[: count.value])
            state = api.WaitForSingleObject(handles["process"], 0)
            if state == 0:
                receipt["process_exited"] = True
                if receipt["output_complete"]:
                    code = DWORD()
                    _check(
                        api.GetExitCodeProcess(handles["process"], C.byref(code)),
                        "GetExitCodeProcess",
                    )
                    receipt["exit_code"] = code.value
                    receipt["disposition"] = "completed" if code.value == 0 else "nonzero_exit"
                    break
            elif state != WAIT_TIMEOUT:
                raise C.WinError(C.get_last_error(), "WaitForSingleObject")
            time.sleep(0.01)
    except (OSError, ValueError) as error:
        receipt["error"] = {"type": type(error).__name__, "message": str(error)}
        if receipt["created"]:
            terminate("setup_or_monitor_refusal")
    finally:
        if api is not None:
            if receipt["created"]:
                if not receipt["process_exited"] and not receipt["termination_requested"]:
                    terminate("unhandled_failure_cleanup")
                remaining = max(0, min(3.0, TOTAL_SECONDS - (time.perf_counter() - started)))
                state = api.WaitForSingleObject(handles["process"], int(remaining * 1000))
                receipt["process_exited"] = state == 0
                if state == 0:
                    code = DWORD()
                    if api.GetExitCodeProcess(handles["process"], C.byref(code)):
                        receipt["exit_code"] = code.value
                    else:
                        receipt["cleanup_errors"].append(
                            {"operation": "GetExitCodeProcess", "winerror": C.get_last_error()}
                        )
                    try:
                        receipt["child_times"] = _times(api, handles["process"], True)
                    except OSError as error:
                        receipt["cleanup_errors"].append(
                            {"operation": "GetProcessTimes(final)", "message": str(error)}
                        )
                else:
                    receipt["cleanup_errors"].append(
                        {"operation": "WaitForSingleObject(final)", "result": state}
                    )
                attempt = receipt["termination_attempt"]
                if attempt and attempt["process_error"] is not None:
                    # ERROR_ACCESS_DENIED is documented after process termination;
                    # retain it as an observation, benign only with verified exit.
                    if attempt["process_error"] != 5 or not receipt["process_exited"]:
                        receipt["cleanup_errors"].append(
                            {
                                "operation": "retained process fallback",
                                "winerror": attempt["process_error"],
                            }
                        )
            for name in ("thread", "process", "writer", "nul", "reader"):
                close(name)
            if attributes_initialized:
                api.DeleteProcThreadAttributeList(attributes)
            if "job" in handles:
                try:
                    accounting = _query(api, handles["job"], 1, Accounting)
                    receipt["job_accounting"] = _accounting_body(accounting)
                    receipt["final_active_processes"] = accounting.active_processes
                    receipt["job_process_ids_final"] = _job_pids(api, handles["job"])
                    final_limits = _query(api, handles["job"], 9, ExtendedLimits)
                    receipt["peak_process_memory_bytes"] = final_limits.peak_process_memory
                    receipt["peak_job_memory_bytes"] = final_limits.peak_job_memory
                    if receipt["created"] and (
                        accounting.active_processes != 0 or receipt["job_process_ids_final"]
                    ):
                        receipt["cleanup_errors"].append(
                            {
                                "operation": "final owned-job membership",
                                "active": accounting.active_processes,
                                "process_ids": receipt["job_process_ids_final"],
                            }
                        )
                except (OSError, ValueError) as error:
                    receipt["cleanup_errors"].append(
                        {"operation": "final job queries", "message": str(error)}
                    )
                close("job")
        if receipt["cleanup_errors"] or (receipt["created"] and not receipt["process_exited"]):
            receipt["disposition"] = "teardown_incomplete"
        receipt["output_bytes"] = len(output)
        receipt["output_sha256"] = hashlib.sha256(output).hexdigest()
        if receipt["output_complete"]:
            receipt["output_hash_scope"] = "complete_stream"
        receipt["elapsed_seconds"] = time.perf_counter() - started
        receipt["finished_utc"] = _stamp()
    return receipt, bytes(output)
