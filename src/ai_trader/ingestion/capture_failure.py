"""Allowlisted failure evidence, never exception messages, reprs or tracebacks.

Codes identify the observed failing operation, not a network/OS root-cause claim.
Only explicit cause chains are inspected, with a fixed depth bound. A later cleanup
failure is reported in its own right; implicit exception context is not exported.
"""

import asyncio
from contextlib import contextmanager

CODES = frozenset(
    {
        "connection.transport_error",
        "snapshot.timeout",
        "snapshot.open_timeout",
        "snapshot.read_timeout",
        "snapshot.deadline",
        "snapshot.acquisition_timeout",
        "snapshot.open_transport_error",
        "snapshot.read_transport_error",
        "snapshot.http_error",
        "snapshot.close_error",
        "snapshot.transport_error",
        "snapshot.invalid_response",
        "snapshot.byte_limit",
        "snapshot.failed",
        "receiver.receipt_clock_regression",
        "receiver.message_limit",
        "receiver.queue_overflow",
        "receiver.transport_error",
        "receiver.disconnected",
        "observer.failed",
        "observer.stopped",
        "stream.idle_timeout",
        "stream.failed",
        "parse.invalid_message",
        "write.byte_limit",
        "write.event_limit",
        "write.failed",
        "write.durable_callback",
        "finalize.failed",
        "integrity.rejected",
        "publication.failed",
        "recording.failed",
        "campaign.binding_mismatch",
        "campaign.slot_metadata",
        "campaign.timing_mismatch",
        "campaign.failed",
        "schedule.failed",
        "schedule.missed_window",
        "schedule.clock_regression",
        "schedule.invalid_clock",
        "schedule.clock_stalled",
        "schedule.completion_timeout",
        "schedule.connected_late",
        "schedule.start_guard_missing",
        "schedule.completion_mismatch",
        "diagnostics.publication_failed",
        "unclassified.unexpected_error",
    }
)
CODES |= frozenset(code.split(".")[0] + ".cancelled" for code in CODES)
ERROR_TYPES = frozenset(
    {
        "CaptureInterrupted",
        "CaptureQuotaExceeded",
        "CancelledError",
        "KeyboardInterrupt",
        "TimeoutError",
        "SnapshotTimeout",
        "_CaptureWaitTimeout",
        "ValueError",
        "TypeError",
        "KeyError",
        "ArithmeticError",
        "OSError",
        "FileExistsError",
        "FileNotFoundError",
        "PermissionError",
        "RuntimeError",
        "AssertionError",
        "ConnectionClosed",
        "ConnectionClosedError",
        "ConnectionClosedOK",
        "PayloadTooBig",
    }
)


def safe_error_type(error):
    name = type(error).__name__
    return name if name in ERROR_TYPES else "OtherError"


def _code(error):
    for _ in range(8):
        if not isinstance(error, BaseException):
            break
        code = vars(error).get("_capture_failure_code")
        if type(code) is str and code in CODES:
            return code
        error = error.__cause__
    return None


def mark_failure(error, code):
    """Annotate and return the same exception, preserving its type and any inner code."""
    if type(code) is not str or code not in CODES:
        raise ValueError("Unsupported capture failure code.")
    if _code(error) is None:
        if isinstance(error, (asyncio.CancelledError, KeyboardInterrupt)):
            code = code.split(".")[0] + ".cancelled"
        error._capture_failure_code = code
    return error


@contextmanager
def failure_stage(code):
    if type(code) is not str or code not in CODES:
        raise ValueError("Unsupported capture failure code.")
    try:
        yield
    except BaseException as error:
        mark_failure(error, code)
        raise


def failure_details(error):
    code = _code(error)
    if code is None:
        code = (
            "unclassified.cancelled"
            if isinstance(error, (asyncio.CancelledError, KeyboardInterrupt))
            else "unclassified.unexpected_error"
        )
    stage, reason = code.split(".")
    return {"schema_version": 1, "stage": stage, "reason": reason}
