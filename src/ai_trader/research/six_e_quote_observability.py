"""Offline quote observability descriptors; never fills, labels, fitting or orders."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ai_trader.research import six_e_liquidity_status as status
from ai_trader.research import six_e_liquidity_study as study
from ai_trader.research import six_e_quote_reference as reference

target, common, resource = study.exits.target, study.common, study.resource
ROLES = tuple(study.data.ROLES)
BANDS = (
    "at_most_100ms",
    "over_100_through_250ms",
    "over_250_through_1000ms",
    "over_1000ms",
    "no_reference",
)
MAX_ROWS, MAX_QUERIES = 14400, 57600
MAX_SECONDS, MAX_DAY_SECONDS = 1800, 60
MAX_OUTPUT_BYTES = 16 * 1024**2
FLAGS = {
    **study.AUTH,
    "cpu_training": False,
    "execution_confirmed": False,
    "training_eligible": False,
    "local_or_broker_receipt_verified": False,
    "account_reconciled": False,
}


def protocol() -> dict:
    return {
        "version": "six_e_quote_observability_v1",
        "scope": "Every accepted exposed development session and original decision; "
        "all entered counterfactual exit requests, no profitable or resolved subset",
        "clock": "Historical vendor receive boundary only, NOT verified live publication "
        "or local/broker receipt; latest native completed event <= delayed exit request",
        "cursor": "Explicit native prefix cursor; historical census uses last completed "
        "event at the receive boundary. Equal-time order retained, not timestamp deduplication",
        "fresh": "Original first event >= request, including equal timestamps, through "
        "unchanged 1s deadline; check saved exit identity without relabeling",
        "later": "First event strictly AFTER request within unchanged deadline, not a fill "
        "at request or a search for a better price",
        "age_bands": list(BANDS),
        "unknown": "Unresolved counterfactual exit liability remains unreconciled across "
        "sessions, never a zero return or an automatic daily account reset",
        "artifacts": "Per-session counts and ordered descriptor SHA256; native cursor/age "
        "descriptors reproducible from retained pinned inputs. No mark prices or returns exported",
        "interpretation": "Post-result descriptive observability, not preregistered "
        "strategy validation, profitability, broker availability or a training dataset",
        "limits": {
            "seconds": MAX_SECONDS,
            "day_seconds": MAX_DAY_SECONDS,
            "rows_per_session": MAX_ROWS,
            "queries_per_batch": MAX_QUERIES,
            "output_bytes": MAX_OUTPUT_BYTES,
            "quotes_per_session": resource.MAX_QUOTES,
        },
        "flags": dict(FLAGS),
    }


class ReferenceIndex:
    """Validate read-only native columns once, then query explicit published prefixes.

    File-backed callers must pin columns before AND after use. Read-only NumPy
    views alone do not establish file immutability or live publication timing.
    """

    def __init__(self, columns: tuple, source_session: str, contract: str):
        self.start, self.end = target.window(source_session)  # Before column access.
        if contract != study.census.dated_contract(source_session):
            raise ValueError("Observability contract differs from declared session")
        if not isinstance(columns, tuple) or len(columns) != 3:
            raise ValueError("Three read-only native quote columns required")
        for column in columns:
            if (
                not isinstance(column, np.ndarray)
                or column.dtype != np.dtype("int64")
                or column.ndim != 1
                or column.flags.writeable
            ):
                raise ValueError("Observability columns must be read-only int64 vectors")
        self.count = len(columns[0])
        if not 0 <= self.count <= resource.MAX_QUOTES or any(
            len(column) != self.count for column in columns
        ):
            raise ValueError("Observability native column count differs or exceeds bound")
        self.columns = columns
        last = None
        for first in range(0, self.count, resource.CHUNK_QUOTES):
            page = np.column_stack([c[first : first + resource.CHUNK_QUOTES] for c in columns])
            target.validate_quotes(page, source_session)
            if last is not None and int(page[0, 0]) < last:
                raise ValueError("Observability native order regressed across pages")
            last = int(page[-1, 0])

    def lookup(self, requests: np.ndarray, published_cursors: np.ndarray) -> dict:
        for value in (requests, published_cursors):
            if (
                not isinstance(value, np.ndarray)
                or value.dtype != np.dtype("int64")
                or value.ndim != 1
                or len(value) > MAX_QUERIES
            ):
                raise ValueError("Bounded int64 request and publication cursor vectors required")
        if (
            len(requests) != len(published_cursors)
            or np.any(requests < self.start)
            or np.any(requests >= self.end)
            or np.any(published_cursors < -1)
            or np.any(published_cursors >= self.count)
        ):
            raise ValueError("Observability request window or publication cursor differs")
        indices = np.minimum(
            np.searchsorted(self.columns[0], requests, side="right") - 1, published_cursors
        )
        times = np.full(len(requests), -1, dtype=np.int64)
        present = indices >= 0
        times[present] = self.columns[0][indices[present]]
        ages = np.where(present, requests - times, -1)
        return {"cursor": indices, "ts_ns": times, "age_ns": ages}


def _count(values, names) -> dict:
    counts = Counter(values)
    if set(counts) - set(names):
        raise ValueError("Unexpected observability descriptor category")
    return {name: counts[name] for name in names}


def describe(labels: list[dict], index: ReferenceIndex, day: str, contract: str) -> dict:
    start, end = target.window(day)  # Refuse reserved before labels/quotes.
    if contract != study.census.dated_contract(day) or (start, end) != (index.start, index.end):
        raise ValueError("Observability descriptor session identity differs")
    if not 0 < len(labels) <= MAX_ROWS:
        raise ValueError("Observability needs a complete bounded decision session")
    last = None
    for label in labels:
        now = label["decision_ts_ns"]
        if (
            label["source_session"] != day
            or label["contract"] != contract
            or label["partition"] != "development"
            or type(now) is not int
            or not start <= now < end
            or (last is not None and now - last < target.SECOND)
            or type(label["eligible"]) is not bool
            or (not label["eligible"] and label["entry"]["status"] != "not_eligible")
        ):
            raise ValueError("Observability original decision identity or order differs")
        last = now
    entry_counts = _count(
        (label["entry"]["status"] for label in labels),
        ("entered", "not_eligible", "no_entry_quote_timeout", "no_entry_spread_widened"),
    )
    entered = [label for label in labels if label["entry"]["status"] == "entered"]
    times, bids, asks = index.columns
    summaries, digest = {}, hashlib.sha256()
    for plan in target.PLANS:
        summaries[plan] = {}
        for side in target.SIDES:
            outcomes = [label["outcomes"][plan][side] for label in entered]
            for label, outcome in zip(entered, outcomes, strict=True):
                trigger = outcome["trigger_ts_ns"]
                request, deadline = outcome["exit_target_ts_ns"], outcome["exit_deadline_ts_ns"]
                if (
                    any(type(x) is not int for x in (trigger, request, deadline))
                    or request != trigger + target.EXIT_DELAY
                    or deadline != request + target.WAIT
                    or not label["entry"]["ts_ns"] <= trigger < end
                    or not start <= request < deadline < end
                    or outcome["trigger"] not in ("stop", "target", "timeout")
                    or type(outcome["inactivity_exposed"]) is not bool
                    or (
                        plan == "time_exit"
                        and (
                            outcome["trigger"] != "timeout"
                            or trigger != label["entry"]["ts_ns"] + target.HOLD
                        )
                    )
                ):
                    raise ValueError("Observability original exit request differs")
            requests = np.asarray([o["exit_target_ts_ns"] for o in outcomes], dtype=np.int64)
            deadlines = np.asarray([o["exit_deadline_ts_ns"] for o in outcomes], dtype=np.int64)
            # This is a DECLARED historical boundary, never inferred live/broker publication.
            boundary = np.searchsorted(times, requests, side="right") - 1
            refs = index.lookup(requests, boundary)
            first = np.searchsorted(times, requests, side="left")
            later = np.searchsorted(times, requests, side="right")
            fresh, next_after = [], []
            for i, outcome in enumerate(outcomes):
                j = int(first[i])
                resolved = j < index.count and times[j] <= deadlines[i]
                expected = "resolved" if resolved else "unresolved_exit_quote_timeout"
                if outcome["status"] != expected:
                    raise ValueError("Observability cannot relabel original exit availability")
                fields = ("exit_ts_ns", "exit_bid_nano", "exit_ask_nano")
                actual = tuple(outcome[k] for k in fields)
                if actual != (
                    (int(times[j]), int(bids[j]), int(asks[j])) if resolved else (None,) * 3
                ):
                    raise ValueError("Observability first native exit quote parity differs")
                fresh.append(j if resolved else -1)
                k = int(later[i])
                next_after.append(k if k < index.count and times[k] <= deadlines[i] else -1)
            bands = [
                reference.age_band(int(age)) if age >= 0 else "no_reference"
                for age in refs["age_ns"]
            ]
            groups = {}
            for original_status in ("resolved", "unresolved_exit_quote_timeout"):
                positions = [i for i, o in enumerate(outcomes) if o["status"] == original_status]
                groups[original_status] = {
                    "requests": len(positions),
                    "reference_age_bands": _count((bands[i] for i in positions), BANDS),
                    "path_inactivity_over_5s": sum(
                        outcomes[i]["inactivity_exposed"] for i in positions
                    ),
                    "trigger_counts": _count(
                        (outcomes[i]["trigger"] for i in positions), ("stop", "target", "timeout")
                    ),
                    "first_strictly_later_within_deadline": sum(
                        next_after[i] >= 0 for i in positions
                    ),
                }
            summaries[plan][side] = {
                "requests": len(outcomes),
                "by_original_status": groups,
                "equal_time_native_cursor_difference": int(np.count_nonzero(first < boundary)),
                "unreconciled_counterfactual_exit_liabilities": groups[
                    "unresolved_exit_quote_timeout"
                ]["requests"],
            }
            # Ordered indices bind every request without emitting prices, returns or new labels.
            digest.update(
                common.canonical(
                    {"session": day, "plan": plan, "side": side, "count": len(outcomes)}
                )
            )
            columns = [
                requests,
                deadlines,
                boundary,
                refs["cursor"],
                refs["ts_ns"],
                refs["age_ns"],
                fresh,
                next_after,
            ]
            digest.update(np.asarray(np.column_stack(columns), dtype="<i8").tobytes())
    return {
        "source_session": day,
        "contract": contract,
        "role": study.data.role_for_day(day),
        "rows": len(labels),
        "entry_statuses": entry_counts,
        "completed_quotes": index.count,
        "exit_requests": 4 * len(entered),
        "exits": summaries,
        "ordered_descriptors_sha256": digest.hexdigest(),
    }


def fingerprints() -> dict:
    return {
        **study.fingerprints(),
        **{
            Path(m.__file__).name: common.hash_file(Path(m.__file__), 1024**2)
            for m in (reference, status)
        },
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
    }


def _read(root: Path, path: Path, pin: str, scope="data/processed", bound=status.MAX_JSON) -> dict:
    status._pin(pin)
    raw = status._raw(root, path, bound, scope)
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError("Observability pinned metadata differs")
    return status._decode(raw)


def inputs(root: Path, spec: dict) -> tuple[dict, dict]:
    path = status._inside(root, Path(spec["registration"]), "logs")
    frozen = study.registration(root, path, spec["registration_sha256"])
    build = status._inside(root, Path(spec["build"]), "data/processed")
    report = _read(root, build / "completion.json", spec["completion_sha256"])
    receipt = _read(root, build / "verification.json", spec["verification_sha256"])
    expected = {
        "status": "verified_whole_liquidity_targets_not_validation",
        "completion_sha256": spec["completion_sha256"],
        "sessions": len(frozen["sources"]),
        "rows": sum(d["rows"] for d in report["days"]),
        "flags": {**study.AUTH, "cpu_training": False},
    }
    if (
        (build / "failure.json").exists()
        or common.canonical(receipt) != common.canonical(expected)
        or report["status"] != "completed_whole_liquidity_targets_not_validation"
        or report["registration_sha256"] != spec["registration_sha256"]
        or report["protocol"] != study.protocol()
        or report["implementation_sha256"] != study.fingerprints()
        or common.canonical(report["flags"]) != common.canonical(expected["flags"])
        or [d["utc_date"] for d in report["days"]]
        != [s["entry"]["utc_date"] for s in frozen["sources"]]
    ):
        raise ValueError("Observability requires complete pinned quarantined collection")
    request = _read(root, build / "request.json", report["request_sha256"])
    if request != {
        "registration_sha256": spec["registration_sha256"],
        "protocol": study.protocol(),
    }:
        raise ValueError("Observability original request differs")
    return frozen, report


def prepare(root: Path, spec: dict, path: Path) -> dict:
    path = status._inside(root, path, "logs")
    output = status._inside(root, Path(spec["output"]), "data/processed")
    if output.suffix != ".json" or output.is_relative_to(Path(spec["build"]).resolve()):
        raise ValueError("Observability registration requires separate JSON output")
    if str(output) != spec["output"]:
        raise ValueError("Observability registered output must be absolute")
    frozen, _ = inputs(root, spec)
    value = {
        "protocol": protocol(),
        "inputs": spec,
        "source_pins": fingerprints(),
        "coverage": frozen["coverage"],
    }
    common._write_new(path, value)
    return value


def registration(root: Path, path: Path, pin: str) -> tuple[dict, dict, dict]:
    value = _read(root, path, pin, "logs", status.MAX_REGISTRATION)
    if (
        common.canonical(value["protocol"]) != common.canonical(protocol())
        or value["source_pins"] != fingerprints()
    ):
        raise ValueError("Observability registered source or protocol drift")
    frozen, report = inputs(root, value["inputs"])
    if value["coverage"] != frozen["coverage"]:
        raise ValueError("Observability original dispositions or coverage drift")
    return value, frozen, report


def _day(root: Path, build: Path, source: dict, evidence: dict) -> dict:
    entry, day = source["entry"], source["entry"]["utc_date"]
    target.window(day)  # Scope check before constructing any price path.
    if (
        evidence["utc_date"] != day
        or type(evidence["rows"]) is not int
        or not 0 < evidence["rows"] <= MAX_ROWS
    ):
        raise ValueError("Observability original day row coverage differs")
    report_path = status._inside(root, build / f"{day}.json", "data/processed")
    saved = _read(root, report_path, evidence["report_sha256"])
    study._replay_check(root, entry, saved["replay"], evidence["quotes"])
    if (
        saved["parity_verified"] is not True
        or saved["source_sha256"] != entry["source_sha256"]
        or saved["quotes"] != evidence["quotes"]
    ):
        raise ValueError("Observability original replay identity differs")
    labels_path = status._inside(root, build / f"{day}.targets.jsonl", "data/processed")
    quote_path = status._inside(root, build / f"{day}.quotes", "data/processed")
    for name in resource.COLUMNS:
        status._inside(root, quote_path / f"{name}.i64", "data/processed")
    labels = study._labels(labels_path, evidence["targets_sha256"], evidence["rows"])
    with study._view(quote_path, evidence["quotes"]) as view:
        result = describe(
            labels,
            ReferenceIndex(tuple(view.columns), day, entry["contract"]),
            day,
            entry["contract"],
        )
    # Pin contents again: read-only mmap does not prevent another process replacing files.
    for name in resource.COLUMNS:
        study.data.review.checked_hash(
            quote_path / f"{name}.i64",
            evidence["quotes"]["columns"][name]["sha256"],
            resource.MAX_QUOTES * 8,
        )
    study.data.review.checked_hash(
        labels_path, evidence["targets_sha256"], study.census.MAX_DAY_BYTES
    )
    original_entries = saved["accounting"]["entry_statuses"]
    if (
        result["role"] != entry["role"]
        or set(original_entries) - set(result["entry_statuses"])
        or result["entry_statuses"]
        != {k: original_entries.get(k, 0) for k in result["entry_statuses"]}
    ):
        raise ValueError("Observability original entry accounting differs")
    result["original_source_quality_sha256"] = hashlib.sha256(
        common.canonical(saved["replay"]["quality"])
    ).hexdigest()
    return result


def pooled(days: list[dict]) -> dict:
    if not days:
        raise ValueError("Observability cannot pool an empty cohort")

    def zero(value):
        return {key: zero(item) for key, item in value.items()} if isinstance(value, dict) else 0

    def add(group):
        if not group:
            return zero(add(days[:1]))
        return {
            "sessions": len(group),
            **{k: sum(d[k] for d in group) for k in ("rows", "completed_quotes", "exit_requests")},
            "entry_statuses": study.exits._sum([d["entry_statuses"] for d in group]),
            "exits": study.exits._sum([d["exits"] for d in group]),
        }

    return {
        "overall": add(days),
        "by_role": {role: add([d for d in days if d["role"] == role]) for role in ROLES},
        "by_contract": {
            contract: add([d for d in days if d["contract"] == contract])
            for contract in sorted({d["contract"] for d in days})
        },
    }


def _write(path: Path, value: dict) -> None:
    raw = common.canonical(value) + b"\n"
    if len(raw) > MAX_OUTPUT_BYTES:
        raise ValueError("Observability output exceeds registered byte bound")
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def run(root: Path, path: Path, pin: str, output: Path) -> dict:
    value, frozen, report = registration(root, path, pin)
    output = status._inside(root, output, "data/processed")
    if (
        str(output) != value["inputs"]["output"]
        or output.exists()
        or output.suffix != ".json"
        or output.is_relative_to(Path(value["inputs"]["build"]).resolve())
    ):
        raise ValueError("Observability needs a new separate JSON result, never original artifacts")
    if shutil.disk_usage(root).free < MAX_OUTPUT_BYTES:
        raise ValueError("Insufficient free space for bounded observability evidence")
    claim = output.with_suffix(".attempt.json")
    if any(output.with_suffix(suffix).exists() for suffix in (".progress.jsonl", ".failure.json")):
        raise ValueError("Observability output has retained evidence; never append another run")
    _write(
        claim,
        {
            "registration_sha256": pin,
            "started_utc": datetime.now(UTC).isoformat(),
            "automatic_retry": False,
        },
    )
    started, days = time.monotonic(), []
    try:
        build = Path(value["inputs"]["build"])
        for source, evidence in zip(frozen["sources"], report["days"], strict=True):
            before = time.monotonic()
            if before - started > MAX_SECONDS:
                raise TimeoutError("Observability total deadline exceeded; no subset completion")
            days.append(_day(root, build, source, evidence))
            if time.monotonic() - before > MAX_DAY_SECONDS:
                raise TimeoutError("Observability per-session deadline exceeded")
            event = {
                "event": "observability_session_completed",
                "utc_date": evidence["utc_date"],
                "rows": evidence["rows"],
                "utc": datetime.now(UTC).isoformat(),
            }
            with output.with_suffix(".progress.jsonl").open("ab") as stream:
                stream.write(common.canonical(event) + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            print(
                json.dumps({"observability_sessions": len(days), "total": len(frozen["sources"])}),
                flush=True,
            )
        registration(root, path, pin)
        if time.monotonic() - started > MAX_SECONDS:
            raise TimeoutError("Observability final guard deadline exceeded")
        result = {
            "status": "complete_quote_observability_not_execution_validation",
            "registration_sha256": pin,
            "protocol": protocol(),
            "source_pins": fingerprints(),
            "coverage": frozen["coverage"],
            "days": days,
            "summaries": pooled(days),
            "flags": dict(FLAGS),
            "attempt_sha256": common.hash_file(claim, status.MAX_JSON),
            "progress_sha256": common.hash_file(
                output.with_suffix(".progress.jsonl"), status.MAX_JOURNAL
            ),
            "elapsed_seconds": time.monotonic() - started,
        }
        _write(output, result)
        return result
    except Exception as exc:
        _write(
            output.with_suffix(".failure.json"),
            {
                "registration_sha256": pin,
                "completed_sessions": len(days),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "automatic_retry": False,
            },
        )
        raise


def verify(root: Path, path: Path, pin: str, output: Path, result_pin: str) -> dict:
    value, frozen, report = registration(root, path, pin)
    output = status._inside(root, output, "data/processed")
    if str(output) != value["inputs"]["output"]:
        raise ValueError("Observability verifier output differs from registration")
    result = _read(root, output, result_pin, bound=MAX_OUTPUT_BYTES)
    if (
        output.with_suffix(".failure.json").exists()
        or result["status"] != "complete_quote_observability_not_execution_validation"
        or result["registration_sha256"] != pin
        or common.canonical(result["flags"]) != common.canonical(FLAGS)
        or common.canonical(result["protocol"]) != common.canonical(protocol())
        or result["source_pins"] != fingerprints()
        or result["coverage"] != frozen["coverage"]
        or type(result["elapsed_seconds"]) not in (int, float)
        or not 0 <= result["elapsed_seconds"] <= MAX_SECONDS
    ):
        raise ValueError("Observability terminal identity, authority or failure differs")
    expected = [s["entry"]["utc_date"] for s in frozen["sources"]]
    if [d["source_session"] for d in result["days"]] != expected:
        raise ValueError("Observability must verify every original session, not a subset")
    attempt = _read(root, output.with_suffix(".attempt.json"), result["attempt_sha256"])
    if attempt["registration_sha256"] != pin or attempt["automatic_retry"] is not False:
        raise ValueError("Observability original exclusive attempt differs")
    progress = status._raw(
        root, output.with_suffix(".progress.jsonl"), status.MAX_JOURNAL, "data/processed"
    )
    if hashlib.sha256(progress).hexdigest() != result["progress_sha256"] or not progress.endswith(
        b"\n"
    ):
        raise ValueError("Observability complete durable progress differs")
    events = [status._decode(line) for line in progress.splitlines()]
    if [e["utc_date"] for e in events] != expected or any(
        e["event"] != "observability_session_completed"
        or type(e["rows"]) is not int
        or e["rows"] != d["rows"]
        for e, d in zip(events, result["days"], strict=True)
    ):
        raise ValueError("Observability durable progress cohort differs")
    started = time.monotonic()
    days = []
    for source, evidence in zip(frozen["sources"], report["days"], strict=True):
        before = time.monotonic()
        days.append(_day(root, Path(value["inputs"]["build"]), source, evidence))
        if time.monotonic() - before > MAX_DAY_SECONDS or time.monotonic() - started > MAX_SECONDS:
            raise TimeoutError("Observability terminal recomputation deadline exceeded")
    if common.canonical(days) != common.canonical(result["days"]) or common.canonical(
        pooled(days)
    ) != common.canonical(result["summaries"]):
        raise ValueError("Observability recomputed descriptors or complete counts differ")
    registration(root, path, pin)
    if time.monotonic() - started > MAX_SECONDS:
        raise TimeoutError("Observability final verification guard deadline exceeded")
    return {
        "status": "verified_quote_observability_not_execution_validation",
        "result_sha256": result_pin,
        "sessions": len(days),
        "rows": sum(d["rows"] for d in days),
        "flags": dict(FLAGS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "verify"))
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--registration-sha256")
    parser.add_argument("--collection-registration", type=Path)
    parser.add_argument("--collection-registration-sha256")
    parser.add_argument("--build", type=Path)
    parser.add_argument("--build-sha256")
    parser.add_argument("--verification-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--result-sha256")
    args, root = parser.parse_args(), Path.cwd()
    if args.action == "prepare":
        if args.collection_registration is None or args.build is None or args.output is None:
            parser.error("prepare requires original collection registration, build and output")
        prepare(
            root,
            {
                "registration": str(args.collection_registration.resolve()),
                "registration_sha256": args.collection_registration_sha256,
                "build": str(args.build.resolve()),
                "completion_sha256": args.build_sha256,
                "verification_sha256": args.verification_sha256,
                "output": str(args.output.resolve()),
            },
            args.registration,
        )
        result = {
            "registration_sha256": common.hash_file(args.registration, status.MAX_REGISTRATION)
        }
    elif args.output is None or args.registration_sha256 is None:
        parser.error("run/verify require output and original registration pin")
    elif args.action == "run":
        result = run(root, args.registration, args.registration_sha256, args.output)
        result = {
            "status": result["status"],
            "result_sha256": common.hash_file(args.output, MAX_OUTPUT_BYTES),
            "summaries": result["summaries"],
        }
    else:
        result = verify(
            root, args.registration, args.registration_sha256, args.output, args.result_sha256
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
