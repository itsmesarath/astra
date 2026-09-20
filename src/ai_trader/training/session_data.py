"""Two-pass, point-in-time loading of research sessions without holdout conversion."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ai_trader.backtesting.economic_metrics import TradeOutcome
from ai_trader.training.metrics import CLASS_LABELS
from ai_trader.training.model_data import (
    ModelPartition,
    infer_model_feature_names,
    row_to_schema_features,
)

TIME_COLUMN = "depth_event_time_ms"
FUTURE_COLUMN = "future_event_time_ms"
SESSION_COLUMN = "source_session"


@dataclass(frozen=True, slots=True)
class SessionMetadata:
    """Feature-time boundaries only; never contains a label or realized return."""

    name: str
    first_event_time_ms: int
    last_event_time_ms: int
    rows: int


@dataclass(frozen=True, slots=True)
class SessionPartition:
    """One selected source session converted to model inputs."""

    name: str
    partition: ModelPartition
    outcomes: tuple[TradeOutcome, ...] | None


@dataclass(frozen=True, slots=True)
class SessionDataset:
    """Frozen session inventory plus only the permitted model partitions."""

    metadata: tuple[SessionMetadata, ...]
    sessions: tuple[SessionPartition, ...]
    held_out_sessions: tuple[str, ...]
    source_sha256: str


def source_sha256(path: Path) -> str:
    """Fingerprint file bytes without interpreting held-out outcomes."""
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _timestamp(raw: str) -> int:
    if not raw or not raw.isascii() or not raw.isdecimal():
        raise ValueError("Timestamps must be nonnegative integer milliseconds.")
    return int(raw)


def scan_session_metadata(path: Path) -> tuple[SessionMetadata, ...]:
    """Scan only session names and feature timestamps, not feature/label values.

    CSV tokenization necessarily reads other columns as strings. This is not
    physical file isolation. No held-out features, targets or outcomes are
    converted, validated, summarized, or exposed as model partitions.
    """
    metadata = []
    seen: set[str] = set()
    current = None
    first = last = count = 0
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.reader(source, strict=True)
        header = next(reader, None)
        if not header or len(header) != len(set(header)):
            raise ValueError("Dataset must have a nonempty, unique-column header.")
        required = {SESSION_COLUMN, TIME_COLUMN, FUTURE_COLUMN, "target_direction"}
        if not required <= set(header):
            raise ValueError(
                f"Dataset is missing columns: {', '.join(sorted(required - set(header)))}."
            )
        session_index, time_index = header.index(SESSION_COLUMN), header.index(TIME_COLUMN)
        for line_number, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise ValueError(f"Line {line_number}: CSV row width does not match header.")
            session = row[session_index]
            if not session.strip() or session != session.strip():
                raise ValueError(f"Line {line_number}: source_session is empty or padded.")
            event_time = _timestamp(row[time_index])
            if session != current:
                if session in seen:
                    raise ValueError(f"Source session {session!r} is not contiguous.")
                if current is not None:
                    if event_time <= last:
                        raise ValueError(
                            "Source sessions must be strictly chronological and disjoint."
                        )
                    metadata.append(SessionMetadata(current, first, last, count))
                seen.add(session)
                current, first, count = session, event_time, 0
            elif event_time < last:
                raise ValueError(f"Line {line_number}: feature timestamps are not chronological.")
            last = event_time
            count += 1
    if current is None:
        raise ValueError("Dataset contains no data rows.")
    metadata.append(SessionMetadata(current, first, last, count))
    return tuple(metadata)


def load_session_dataset(
    path: Path,
    *,
    held_out_session_count: int = 0,
    embargo_ms: int = 0,
) -> SessionDataset:
    """Reserve final sessions before converting any feature, target or outcome.

    Reject crossing labels, rather than silently trimming or reassigning rows.
    Each selected outcome plus embargo must end strictly before the next
    session's first feature timestamp, including the first reserved session.
    Exit times may be nonmonotonic: every row is checked, not just the last.
    """
    for value in (held_out_session_count, embargo_ms):
        if type(value) is not int or value < 0:
            raise ValueError("Holdout count and embargo must be nonnegative integers.")
    fingerprint = source_sha256(path)
    metadata = scan_session_metadata(path)
    if held_out_session_count >= len(metadata):
        raise ValueError("Holdout count must leave at least one research session.")
    selected = metadata[: len(metadata) - held_out_session_count]
    permitted = {item.name for item in selected}
    next_start = {
        previous.name: following.first_event_time_ms
        for previous, following in zip(metadata, metadata[1:], strict=False)
    }
    features: dict[str, list[np.ndarray]] = {item.name: [] for item in selected}
    targets: dict[str, list[int]] = {item.name: [] for item in selected}
    outcomes: dict[str, list[TradeOutcome]] = {item.name: [] for item in selected}

    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        feature_names = infer_model_feature_names(reader.fieldnames)
        # future_event_time_ms is also used by depth labels without economic columns.
        economic_columns = {"entry_time_ms", "net_return_bps"}
        present = economic_columns & set(reader.fieldnames)
        if present and present != economic_columns:
            raise ValueError("Dataset has incomplete economic columns.")
        has_outcomes = bool(present)
        for line_number, row in enumerate(reader, start=2):
            session = row[SESSION_COLUMN]
            if session not in permitted:
                continue  # Before reading/converting ANY held-out feature or outcome value.
            try:
                event_time = _timestamp(row[TIME_COLUMN])
                future_time = _timestamp(row[FUTURE_COLUMN])
                if future_time <= event_time:
                    raise ValueError("Label outcome must be after its feature timestamp.")
                if session in next_start and future_time + embargo_ms >= next_start[session]:
                    raise ValueError("Label outcome/embargo crosses the next session boundary.")
                target = int(row["target_direction"])
                if target not in CLASS_LABELS:
                    raise ValueError("target_direction must be -1, 0, or 1.")
                feature_row = row_to_schema_features(row, feature_names)
                if has_outcomes:
                    entry_time = _timestamp(row["entry_time_ms"])
                    if entry_time <= event_time:
                        raise ValueError("Entry must be after its feature timestamp.")
                    if outcomes[session] and entry_time <= outcomes[session][-1].entry_time_ms:
                        raise ValueError("Entry timestamps must be strictly increasing.")
                    outcome = TradeOutcome(entry_time, future_time, float(row["net_return_bps"]))
                    outcome.validate()
                    outcomes[session].append(outcome)
                features[session].append(feature_row)
                targets[session].append(target)
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"{path.name} line {line_number}: {error}") from error

    if source_sha256(path) != fingerprint:
        raise ValueError("Dataset changed during session loading; use an immutable capture.")
    if any(len(features[item.name]) != item.rows for item in selected):
        raise ValueError("Dataset rows do not match the frozen session inventory.")
    partitions = tuple(
        SessionPartition(
            item.name,
            ModelPartition(
                features=np.vstack(features[item.name]).astype(np.float64, copy=False),
                targets=np.asarray(targets[item.name], dtype=np.int64),
                feature_names=feature_names,
            ),
            tuple(outcomes[item.name]) if has_outcomes else None,
        )
        for item in selected
    )
    return SessionDataset(
        metadata,
        partitions,
        tuple(item.name for item in metadata[len(selected) :]),
        fingerprint,
    )
