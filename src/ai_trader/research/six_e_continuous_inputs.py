"""Read-only causal inputs for a bounded first-prefix 6E account replay.

Only original decision rows and native quote columns are read. Future outcome
fields in the original row envelope are discarded without interpretation.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from ai_trader.research import six_e_quote_observability as obs

if TYPE_CHECKING:
    from ai_trader.research.six_e_continuous_replay import ReplaySession

study, status, resource = obs.study, obs.status, obs.resource
CAUSAL_FIELDS = (
    "source_session",
    "contract",
    "partition",
    "decision_ts_ns",
    "eligible",
    "eligibility_reason",
    "features",
    "execution_features",
)
MAX_LINE = 65536
MAX_DAY_DECISIONS = 14400


def fingerprints() -> dict:
    """Source pins for a future separately registered input-loading contract."""
    return {
        **obs.fingerprints(),
        Path(__file__).name: study.common.hash_file(Path(__file__), 1024**2),
    }


def metadata(root: Path, path: Path, pin: str) -> tuple[dict, dict, dict]:
    """Verify pinned original metadata/source only, without target/model readers."""
    path = status._inside(root, path, "logs")
    return obs.registration(root, path, pin)


def _calendar(days: tuple[str, ...], maximum: int) -> None:
    if type(days) is not tuple or not 1 <= len(days) <= maximum:
        raise ValueError("Continuous inputs require a bounded explicit session tuple")
    for day in days:
        if type(day) is not str or date.fromisoformat(day).isoformat() != day:
            raise ValueError("Continuous input dates must be canonical")
        if study.data.role_for_day(day) != "train":
            raise ValueError("Continuous first-prefix inputs must retain the train role")
        study.census.dated_contract(day)
    if list(days) != sorted(set(days)):
        raise ValueError("Continuous input dates must be unique and chronological")


def _scope(frozen: dict, report: dict, days: tuple[str, ...], maximum_quotes: int) -> list:
    sources = frozen["sources"]
    if type(sources) is not list or len(sources) < len(days):
        raise ValueError("Continuous input cohort lacks the requested first prefix")
    if days != tuple(source["entry"]["utc_date"] for source in sources[: len(days)]):
        raise ValueError("Continuous inputs must be the exact first accepted cohort prefix")
    if [item["utc_date"] for item in report["days"]] != [
        source["entry"]["utc_date"] for source in sources
    ]:
        raise ValueError("Continuous original collection coverage differs")
    selected = []
    for day, source, evidence in zip(days, sources, report["days"], strict=False):
        entry, member = source["entry"], source["member"]
        contract = study.census.dated_contract(day)
        if (
            entry["utc_date"] != day
            or evidence["utc_date"] != day
            or entry["role"] != "train"
            or entry["partition"] != "development"
            or entry["disposition"] != "decision_session"
            or entry["contract"] != contract
            or member["utc_date"] != day
            or member["contract"] != contract
            or member["partition"] != "development"
            or member["condition"] != "available"
            or member["planned_action"] != "decision_window_replay"
            or member["sha256"] != entry["source_sha256"]
        ):
            raise ValueError("Continuous session identity or original source disposition differs")
        status._pin(entry["source_sha256"])
        artifact = entry["artifacts"]["rows"]
        count = artifact["count"]
        if (
            type(count) is not int
            or not 0 < count <= MAX_DAY_DECISIONS
            or type(evidence["rows"]) is not int
            or evidence["rows"] != count
        ):
            raise ValueError("Continuous original decision count differs or exceeds bound")
        status._pin(artifact["sha256"])
        quote_meta = evidence["quotes"]
        if (
            type(quote_meta) is not dict
            or set(quote_meta) != {"count", "columns"}
            or type(quote_meta["count"]) is not int
            or not 0 < quote_meta["count"] <= maximum_quotes
            or type(quote_meta["columns"]) is not dict
            or set(quote_meta["columns"]) != set(resource.COLUMNS)
        ):
            raise ValueError("Continuous native quote count or columns exceed the fixed bound")
        for column in quote_meta["columns"].values():
            if (
                type(column) is not dict
                or set(column) != {"bytes", "sha256"}
                or type(column["bytes"]) is not int
                or column["bytes"] != quote_meta["count"] * 8
            ):
                raise ValueError("Continuous native quote column byte count differs")
            status._pin(column["sha256"])
        selected.append((entry, evidence))
    return selected


def _decisions(root: Path, entry: dict, quotes: np.ndarray, project) -> tuple[dict, ...]:
    artifact = entry["artifacts"]["rows"]
    path = status._inside(root, root / artifact["path"], "data/processed")
    study.data.review.checked_hash(path, artifact["sha256"], study.census.MAX_DAY_BYTES)
    day, contract = entry["utc_date"], entry["contract"]
    start, end = obs.target.window(day)
    times = quotes[:, 0]
    result, size, digest, last = [], 0, hashlib.sha256(), None
    with path.open("rb") as stream:
        while raw := stream.readline(MAX_LINE + 1):
            size += len(raw)
            if (
                len(raw) > MAX_LINE
                or not raw.endswith(b"\n")
                or size > study.census.MAX_DAY_BYTES
                or len(result) >= artifact["count"]
            ):
                raise ValueError("Continuous original rows are incomplete or exceed their bounds")
            digest.update(raw)
            original = study.common.loads(raw)
            row = {name: original[name] for name in CAUSAL_FIELDS}
            now = row["decision_ts_ns"]
            if (
                row["source_session"] != day
                or row["contract"] != contract
                or row["partition"] != "development"
                or type(row["eligible"]) is not bool
                or (
                    row["eligibility_reason"] is not None
                    and (
                        type(row["eligibility_reason"]) is not str
                        or not row["eligibility_reason"].strip()
                        or len(row["eligibility_reason"]) > 512
                    )
                )
                or (row["eligible"] != (row["eligibility_reason"] is None))
                or type(now) is not int
                or not start <= now < end
                or (last is not None and now - last < obs.target.SECOND)
            ):
                raise ValueError("Continuous causal decision identity or order differs")
            study.rules.inputs(row)  # Scope and feature allowlists before native cursor access.
            cursor = int(np.searchsorted(times, now, side="left"))
            if cursor >= len(times) or int(times[cursor]) != now:
                raise ValueError("Continuous decision lacks its original native completed quote")
            result.append(project(row, cursor))
            last = now
    if digest.hexdigest() != artifact["sha256"] or len(result) != artifact["count"]:
        raise ValueError("Continuous original row hash or complete decision count differs")
    study.data.review.checked_hash(path, artifact["sha256"], study.census.MAX_DAY_BYTES)
    return tuple(result)


def load_sessions(
    root: Path,
    original_observability_registration_path: Path,
    original_pin: str,
    days: tuple[str, ...],
) -> tuple[ReplaySession, ...]:
    """Load the exact first one-to-three accepted train sessions, never a result subset."""
    # Lazy import keeps the replay's output/registration entry points free of a module cycle.
    from ai_trader.research import six_e_continuous_replay as c

    _calendar(days, c.MAX_SESSIONS)
    implementation = fingerprints()
    value, frozen, report = metadata(root, original_observability_registration_path, original_pin)
    selected = _scope(frozen, report, days, c.MAX_QUOTES)
    if sum(entry["artifacts"]["rows"]["count"] for entry, _ in selected) > c.MAX_DECISIONS:
        raise ValueError("Continuous total decision bound exceeded")
    build = status._inside(root, Path(value["inputs"]["build"]), "data/processed")
    sessions = []
    for entry, evidence in selected:
        day = entry["utc_date"]
        # Validate every source path, including ancestor links, before a pinned reader opens it.
        status._inside(root, root / entry["report"]["path"], "data/processed")
        report_path = status._inside(root, build / f"{day}.json", "data/processed")
        saved = obs._read(root, report_path, evidence["report_sha256"])
        if (
            saved["utc_date"] != day
            or saved["role"] != entry["role"]
            or saved["parity_verified"] is not True
            or saved["source_sha256"] != entry["source_sha256"]
            or saved["quotes"] != evidence["quotes"]
        ):
            raise ValueError("Continuous original daily replay metadata differs")
        study._replay_check(root, entry, saved["replay"], evidence["quotes"])
        quote_path = status._inside(root, build / f"{day}.quotes", "data/processed")
        for name in resource.COLUMNS:
            status._inside(root, quote_path / f"{name}.i64", "data/processed")
        with study._view(quote_path, evidence["quotes"]) as view:
            obs.ReferenceIndex(tuple(view.columns), day, entry["contract"])
            quotes = np.column_stack(view.columns)
        quotes.setflags(write=False)
        decisions = _decisions(root, entry, quotes, c.decision_input)
        for name in resource.COLUMNS:
            study.data.review.checked_hash(
                quote_path / f"{name}.i64",
                evidence["quotes"]["columns"][name]["sha256"],
                c.MAX_QUOTES * 8,
            )
        obs._read(root, report_path, evidence["report_sha256"])
        sessions.append(
            c.ReplaySession(day, entry["contract"], entry["source_sha256"], decisions, quotes)
        )
    metadata(root, original_observability_registration_path, original_pin)
    if fingerprints() != implementation:
        raise ValueError("Continuous input loader source changed during the read")
    return tuple(sessions)
