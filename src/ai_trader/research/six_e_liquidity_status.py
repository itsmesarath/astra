"""Bounded metadata-only status snapshots; never launch or revalidate a study."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import date, datetime
from pathlib import Path

MAX_JSON = 2 * 1024**2
MAX_REGISTRATION = 8 * 1024**2
MAX_JOURNAL = 1024**2
MAX_LINE = 4096
FALSE_FLAGS = (
    "independent_holdout",
    "promotion_allowed",
    "trading_enabled",
    "reserved_outcomes_opened",
    "qwen_training",
)
STATES = {
    "collection": (
        "completed_whole_liquidity_targets_not_validation",
        "verified_whole_liquidity_targets_not_validation",
    ),
    "cpu_evaluation": (
        "completed_quarantined_liquidity_cpu_not_validation",
        "verified_quarantined_liquidity_cpu_not_validation",
    ),
}


class SnapshotUnavailable(ValueError):
    """A concurrent metadata write may be incomplete; not proof of corruption."""


def _pin(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("An external lowercase SHA256 pin is required")
    return value


def _inside(root: Path, path: Path, scope: str) -> Path:
    root = root.resolve(strict=True)
    absolute = Path(os.path.abspath(path))
    boundary = root / scope
    if absolute == boundary or not absolute.is_relative_to(boundary):
        raise ValueError("Status path is outside its bounded project scope")
    for component in (absolute, *absolute.parents):
        if component == root:
            break
        if component.is_symlink() or os.path.isjunction(component):
            raise ValueError("Status paths cannot traverse symlinks or junctions")
    if not absolute.resolve().is_relative_to(boundary):
        raise ValueError("Status path resolves outside its project scope")
    return absolute


def _raw(root: Path, path: Path, bound: int, scope: str) -> bytes:
    path = _inside(root, path, scope)
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if before.st_size > bound:
            raise ValueError("Status metadata exceeds its read bound")
        raw = stream.read(bound + 1)
        after = os.fstat(stream.fileno())
    if len(raw) > bound:
        raise ValueError("Status metadata exceeds its read bound")
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise SnapshotUnavailable("Metadata changed during this read")
    return raw


def _pairs(pairs: list) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate status metadata field")
        value[key] = item
    return value


def _decode(raw: bytes) -> dict:
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotUnavailable("Metadata is not a complete JSON snapshot") from exc
    if not isinstance(value, dict):
        raise ValueError("Status metadata must be an object")
    return value


def _constant(value: str):
    raise ValueError("Nonfinite status metadata is not allowed")


def _json(root: Path, path: Path, bound=MAX_JSON, scope="data/processed") -> tuple[dict, str]:
    raw = _raw(root, path, bound, scope)
    return _decode(raw), hashlib.sha256(raw).hexdigest()


def _flags(value: dict, cpu: bool) -> None:
    expected = {**dict.fromkeys(FALSE_FLAGS, False), "cpu_training": cpu}
    if value != expected or any(type(v) is not bool for v in value.values()):
        raise ValueError("Status authority flags differ from quarantined research")


def _journal(root: Path, output: Path, dates: list[str], phase: str) -> dict:
    path = output / "progress.jsonl"
    if not path.exists():
        return {"completed_sessions": 0, "active_session": None, "partial_tail": False}
    raw = _raw(root, path, MAX_JOURNAL, "data/processed")
    partial = bool(raw and not raw.endswith(b"\n"))
    lines = raw.split(b"\n")[:-1]
    completed, active, last_utc = 0, None, None
    for line in lines:
        if not line or len(line) > MAX_LINE:
            raise ValueError("Status progress line is empty or oversized")
        value = _decode(line)
        day, event = value["utc_date"], value["event"]
        if completed >= len(dates) or day != dates[completed]:
            raise ValueError("Status progress is not the complete chronological cohort prefix")
        utc = datetime.fromisoformat(value["utc"])
        if utc.utcoffset() is None or (last_utc is not None and utc < last_utc):
            raise ValueError("Status progress timestamp is invalid or reversed")
        last_utc = utc
        if event == "native_session_started" and phase == "collection" and active is None:
            active = day
        elif event == ("session_completed" if phase == "collection" else "cpu_session_completed"):
            if phase == "collection" and active != day:
                raise ValueError("Status session completed without its original start")
            if type(value["rows"]) is not int or not 0 < value["rows"] <= 14400:
                raise ValueError("Invalid status progress row count")
            completed, active = completed + 1, None
        else:
            raise ValueError("Unexpected or duplicated status progress event")
    return {"completed_sessions": completed, "active_session": active, "partial_tail": partial}


def snapshot(root: Path, registration: Path, pin: str, output: Path, completion_pin=None) -> dict:
    """Read only named metadata, not targets, quotes, models, predictions or archives.

    Receipt agreement is not content verification or process-liveness evidence.
    This function cannot authorize fitting, resuming, promotion or trading.
    """
    _pin(pin)
    if completion_pin is not None:
        _pin(completion_pin)
    registration = _inside(root, registration, "logs")
    output = _inside(root, output, "data/processed")
    frozen, actual = _json(root, registration, MAX_REGISTRATION, "logs")
    if actual != pin:
        raise ValueError("Original status registration pin differs")
    protocol = frozen["protocol"]
    if protocol["version"] != "six_e_whole_liquidity_development_v1" or any(
        protocol[k] is not False for k in FALSE_FLAGS
    ):
        raise ValueError("Status registration is not quarantined liquidity research")
    dates = [s["entry"]["utc_date"] for s in frozen["sources"]]
    if not dates or len(dates) > 366 or dates != sorted(set(dates)):
        raise ValueError("Status cohort must be a bounded chronological set")
    for day in dates:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError("Invalid status source-session date")
    result = {
        "status": "awaiting_request_unverified",
        "total_sessions": len(dates),
        "registration_sha256": pin,
        "full_content_verified_by_this_check": False,
        "process_checked": False,
        "permission_to_start_or_resume": False,
        "trading_enabled": False,
    }
    try:
        if (output / "failure.json").exists():
            failure, failure_pin = _json(root, output / "failure.json")
            if (
                failure["registration_sha256"] != pin
                or failure["status"] != "failed_no_subset_or_retry"
                or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,99}", failure["exception"]) is None
            ):
                raise ValueError("Status failure identity differs")
            return {
                **result,
                "status": "failure_metadata_present_no_retry",
                "exception": failure["exception"],
                "failure_sha256": failure_pin,
            }
        if not (output / "request.json").exists():
            if (output / "completion.json").exists() or (output / "verification.json").exists():
                raise ValueError("Terminal status metadata lacks its original request")
            return result
        request, request_pin = _json(root, output / "request.json")
        phase = "cpu_evaluation" if "build" in request else "collection"
        expected = {"registration_sha256": pin, "protocol": protocol}
        if phase == "cpu_evaluation":
            build = _inside(root, Path(request["build"]), "data/processed")
            expected.update(build=str(build), build_sha256=_pin(request["build_sha256"]))
        if request != expected:
            raise ValueError("Original status request differs from the registration")
        result.update(phase=phase, status="progress_metadata_unverified")
        result.update(_journal(root, output, dates, phase))
        if not (output / "completion.json").exists():
            if (output / "verification.json").exists():
                raise ValueError("Verification receipt lacks a completion report")
            return result
        completed, actual_pin = _json(root, output / "completion.json")
        if completion_pin is not None and actual_pin != completion_pin:
            raise ValueError("External completion pin differs")
        _flags(completed["flags"], phase == "cpu_evaluation")
        if (
            completed["status"] != STATES[phase][0]
            or completed["registration_sha256"] != pin
            or completed["protocol"] != protocol
            or completed["request_sha256"] != request_pin
            or [d["utc_date"] for d in completed["days"]] != dates
            or completed["implementation_sha256"] != frozen["implementation_sha256"]
            or result["completed_sessions"] != len(dates)
            or result["partial_tail"]
        ):
            raise ValueError("Completion metadata identity or full coverage differs")
        if phase == "cpu_evaluation" and completed["build_sha256"] != request["build_sha256"]:
            raise ValueError("CPU completion source pin differs")
        rows = [d["rows"] for d in completed["days"]]
        if any(type(n) is not int or not 0 < n <= 14400 for n in rows):
            raise ValueError("Completion status rows are invalid")
        result.update(status="completion_metadata_not_revalidated", completion_sha256=actual_pin)
        if (output / "verification.json").exists():
            receipt, receipt_pin = _json(root, output / "verification.json")
            _flags(receipt["flags"], phase == "cpu_evaluation")
            if receipt != {
                "status": STATES[phase][1],
                "completion_sha256": actual_pin,
                "sessions": len(dates),
                "rows": sum(rows),
                "flags": completed["flags"],
            }:
                raise ValueError("Verification receipt does not match the complete metadata")
            result.update(
                status=(
                    "pinned_receipt_matches_metadata_not_revalidated"
                    if completion_pin is not None
                    else "unpinned_receipt_matches_metadata_not_revalidated"
                ),
                verification_sha256=receipt_pin,
                rows=sum(rows),
            )
        return result
    except SnapshotUnavailable as exc:
        return {**result, "status": "concurrent_snapshot_unverified", "reason": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", required=True, type=Path)
    parser.add_argument("--registration-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--completion-sha256")
    args = parser.parse_args()
    result = snapshot(
        Path(__file__).resolve().parents[3],
        args.registration,
        args.registration_sha256,
        args.output,
        args.completion_sha256,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
