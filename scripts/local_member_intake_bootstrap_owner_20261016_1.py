"""Finite pure retention support; no native capability or P3 validation."""

from types import FunctionType

_LOOKUP_NAMES = (
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
_CUT_PHASES = ("before_entry", "after_outcome", "before_commit", "after_commit")


class OwnerRefusal(ValueError):
    """An admission refusal with an ordinary mutable reason attribute."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _empty_slot():
    return {
        "call_state": "not_entered",
        "record_state": "absent",
        "attempts": 0,
        "raw_return": None,
        "raw_error": None,
        "conversion_error": None,
        "conversion_result": None,
        "pending_record": None,
        "committed_record": None,
        "cut_ref": None,
        "reason": None,
    }


class _Owner:
    __slots__ = (
        "carrier",
        "initialization",
        "binding_initialization",
        "constructor",
        "lookups",
        "next_lookup",
        "in_progress",
        "stopped",
    )

    def __init__(self, carrier):
        self.carrier = carrier
        self.initialization = carrier["initialization"]
        self.binding_initialization = carrier["binding_initialization"]
        self.constructor = _empty_slot()
        self.lookups = tuple(_empty_slot() for _ in range(33))
        self.next_lookup = 0
        self.in_progress = False
        self.stopped = False


def _carrier_shape(carrier):
    if type(carrier) is not dict or len(carrier) != 2:
        raise OwnerRefusal("carrier")
    for key in carrier:
        if type(key) is not str:
            raise OwnerRefusal("carrier")
    if set(carrier) != {"initialization", "binding_initialization"}:
        raise OwnerRefusal("carrier")
    initialization = carrier["initialization"]
    bindings = carrier["binding_initialization"]
    if type(initialization) is not list or type(bindings) is not list:
        raise OwnerRefusal("carrier")
    if initialization is bindings:
        raise OwnerRefusal("carrier")


def _require_owner(owner):
    if type(owner) is not _Owner:
        raise OwnerRefusal("owner")


def _retained_row(slot):
    if slot["record_state"] == "committed":
        return slot["committed_record"]
    return slot["pending_record"]


def _check_carrier(owner):
    _carrier_shape(owner.carrier)
    if owner.carrier["initialization"] is not owner.initialization:
        raise OwnerRefusal("carrier")
    if owner.carrier["binding_initialization"] is not owner.binding_initialization:
        raise OwnerRefusal("carrier")
    constructor_count = int(owner.constructor["record_state"] != "absent")
    if len(owner.initialization) != constructor_count:
        raise OwnerRefusal("carrier")
    if constructor_count and owner.initialization[0] is not _retained_row(owner.constructor):
        raise OwnerRefusal("carrier")
    binding_count = 0
    for slot in owner.lookups:
        if slot["record_state"] == "absent":
            break
        binding_count += 1
    if len(owner.binding_initialization) != binding_count:
        raise OwnerRefusal("carrier")
    for index in range(binding_count):
        if owner.binding_initialization[index] is not _retained_row(owner.lookups[index]):
            raise OwnerRefusal("carrier")


def _admit(owner, pending_record, invoke, convert, cut):
    _require_owner(owner)
    _check_carrier(owner)
    if type(pending_record) is not dict:
        raise OwnerRefusal("pending_record")
    if type(invoke) is not FunctionType or type(convert) is not FunctionType:
        raise OwnerRefusal("callback")
    if cut is not None:
        if type(cut) is not tuple or len(cut) != 2:
            raise OwnerRefusal("cut")
        if type(cut[0]) is not str or cut[0] not in _CUT_PHASES:
            raise OwnerRefusal("cut")
    if owner.in_progress:
        raise OwnerRefusal("reentrant")
    if owner.stopped:
        raise OwnerRefusal("stopped")


def _successful(slot):
    return (
        slot["call_state"] == "returned"
        and slot["record_state"] == "committed"
        and slot["reason"] is None
    )


def _cut_reached(owner, slot, cut, phase):
    if cut is None or cut[0] != phase:
        return False
    slot["cut_ref"] = cut[1]
    slot["reason"] = "cut_" + phase
    if phase != "after_commit":
        slot["record_state"] = "unqualified"
    owner.stopped = True
    owner.in_progress = False
    return True


def _unqualified(owner, slot, reason):
    slot["record_state"] = "unqualified"
    slot["reason"] = reason
    owner.stopped = True
    owner.in_progress = False
    return dict(slot)


def _conversion_status(slot):
    proposal = slot["conversion_result"]
    if type(proposal) is not tuple or len(proposal) != 2:
        return "conversion_protocol"
    status, record = proposal
    if type(status) is not str:
        return "conversion_protocol"
    if status in ("unsupported", "oversize"):
        return status if record is None else "conversion_protocol"
    if status == "complete_success":
        expected_state = "returned"
    elif status == "complete_error":
        expected_state = "raised"
    else:
        return "conversion_protocol"
    if slot["call_state"] != expected_state:
        return "conversion_protocol"
    if type(record) is not dict or record is slot["pending_record"]:
        return "conversion_protocol"
    return status


def _run(owner, slot, rows, index, pending_record, invoke, convert, cut):
    owner.in_progress = True
    slot["pending_record"] = pending_record
    slot["record_state"] = "reserved"
    rows.append(pending_record)
    if _cut_reached(owner, slot, cut, "before_entry"):
        return dict(slot)

    slot["attempts"] = 1
    slot["call_state"] = "entered"
    try:
        raw_object = invoke()
    except Exception as error:
        slot["raw_error"] = error
        slot["call_state"] = "raised"
        raw_object = error
    else:
        slot["raw_return"] = raw_object
        slot["call_state"] = "returned"

    if _cut_reached(owner, slot, cut, "after_outcome"):
        return dict(slot)
    try:
        proposal = convert(slot["call_state"], raw_object)
    except Exception as error:
        slot["conversion_error"] = error
        return _unqualified(owner, slot, "conversion_exception")
    slot["conversion_result"] = proposal
    status = _conversion_status(slot)
    if status in ("unsupported", "oversize", "conversion_protocol"):
        return _unqualified(owner, slot, status)
    if _cut_reached(owner, slot, cut, "before_commit"):
        return dict(slot)

    record = proposal[1]
    rows[index] = record
    slot["committed_record"] = record
    slot["record_state"] = "committed"
    if status == "complete_error":
        slot["reason"] = "complete_error"
        owner.stopped = True
    elif rows is owner.binding_initialization:
        owner.next_lookup += 1
    if _cut_reached(owner, slot, cut, "after_commit"):
        return dict(slot)
    owner.in_progress = False
    return dict(slot)


def new_owner(carrier):
    """Publish the fixed owner while retaining the caller's original arrays."""
    _carrier_shape(carrier)
    if carrier["initialization"] or carrier["binding_initialization"]:
        raise OwnerRefusal("carrier")
    return _Owner(carrier)


def run_constructor(owner, pending_record, invoke, convert, *, cut=None):
    """Invoke one trusted constructor fake after reserving its pending row."""
    _admit(owner, pending_record, invoke, convert, cut)
    if owner.constructor["record_state"] != "absent":
        raise OwnerRefusal("order")
    return _run(
        owner,
        owner.constructor,
        owner.initialization,
        0,
        pending_record,
        invoke,
        convert,
        cut,
    )


def run_lookup(owner, api_name, pending_record, invoke, convert, *, cut=None):
    """Invoke only the next registered lookup fake, never an automatic roster."""
    _admit(owner, pending_record, invoke, convert, cut)
    if type(api_name) is not str:
        raise OwnerRefusal("order")
    if not _successful(owner.constructor) or owner.next_lookup >= 33:
        raise OwnerRefusal("order")
    for index in range(owner.next_lookup):
        if not _successful(owner.lookups[index]):
            raise OwnerRefusal("order")
    if api_name != _LOOKUP_NAMES[owner.next_lookup]:
        raise OwnerRefusal("order")
    slot = owner.lookups[owner.next_lookup]
    if slot["record_state"] != "absent":
        raise OwnerRefusal("order")
    return _run(
        owner,
        slot,
        owner.binding_initialization,
        owner.next_lookup,
        pending_record,
        invoke,
        convert,
        cut,
    )


def inspect_owner(owner):
    """Copy fixed view metadata without walking any retained reference graph."""
    _require_owner(owner)
    return {
        "next_lookup": owner.next_lookup,
        "in_progress": owner.in_progress,
        "stopped": owner.stopped,
        "constructor": dict(owner.constructor),
        "lookups": tuple(dict(slot) for slot in owner.lookups),
    }


def select_paths(owner):
    """Select conservative pure routes, never a native cleanup or output path."""
    _require_owner(owner)
    complete = (
        owner.next_lookup == 33
        and not owner.in_progress
        and not owner.stopped
        and _successful(owner.constructor)
    )
    for slot in owner.lookups:
        if not _successful(slot):
            complete = False
    return {
        "bootstrap_recording_complete": complete,
        "native_cleanup_allowed": False,
        "native_emission_allowed": False,
        "cleanup_route": "no_explicit_native_owners",
        "emission_route": "existing_python_stdout_only",
    }
