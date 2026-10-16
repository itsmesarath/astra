"""Combine compatible labeled capture sessions chronologically."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ai_trader.training.split_dataset import read_labeled_rows

SOURCE_SESSION_COLUMN = "source_session"


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """Validated metadata for one labeled capture session."""

    path: Path
    source_session: str
    rows: int
    first_event_time_ms: int
    last_event_time_ms: int
    last_future_event_time_ms: int
    first_update_id: int
    last_update_id: int
    down_labels: int
    neutral_labels: int
    up_labels: int
    sha256: str


@dataclass(frozen=True, slots=True)
class CombinedDatasetReport:
    """Summary of a completed multi-session combination."""

    output_path: Path
    manifest_path: Path
    session_count: int
    total_rows: int
    symbol: str
    label_horizon_ms: int
    neutral_threshold_bps: Decimal
    down_labels: int
    neutral_labels: int
    up_labels: int
    sessions: tuple[SessionSummary, ...]


@dataclass(frozen=True, slots=True)
class LoadedSession:
    """One validated session waiting to be combined."""

    fieldnames: tuple[str, ...]
    rows: tuple[dict[str, str], ...]
    summary: SessionSummary
    symbol: str
    label_horizon_ms: int
    neutral_threshold_bps: Decimal


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of one source file."""
    digest = hashlib.sha256()

    with path.open("rb") as input_file:
        for block in iter(
            lambda: input_file.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def is_nondecreasing(values: list[int]) -> bool:
    """Return whether integer values remain chronological."""
    return all(
        current <= following
        for current, following in zip(
            values,
            values[1:],
            strict=False,
        )
    )


def is_strictly_increasing(values: list[int]) -> bool:
    """Return whether every integer is greater than its predecessor."""
    return all(
        current < following
        for current, following in zip(
            values,
            values[1:],
            strict=False,
        )
    )


def load_session(
    path: Path,
    *,
    source_session: str,
) -> LoadedSession:
    """Read and fully validate one labeled capture session."""
    fieldnames, rows = read_labeled_rows(path)

    if SOURCE_SESSION_COLUMN in fieldnames:
        raise ValueError(
            f"{path.name} already contains {SOURCE_SESSION_COLUMN!r}; "
            "nested dataset combination is not supported."
        )

    try:
        event_times_ms = [int(row["depth_event_time_ms"]) for row in rows]
        future_event_times_ms = [int(row["future_event_time_ms"]) for row in rows]
        update_ids = [int(row["update_id"]) for row in rows]
        directions = [int(row["target_direction"]) for row in rows]
        horizon_ms = int(rows[0]["label_horizon_ms"])
        threshold_bps = Decimal(rows[0]["neutral_threshold_bps"])
    except (InvalidOperation, KeyError, ValueError) as error:
        raise ValueError(f"{path.name} contains invalid session metadata.") from error

    if horizon_ms <= 0:
        raise ValueError(f"{path.name} has a nonpositive label horizon.")
    if not threshold_bps.is_finite() or threshold_bps < 0:
        raise ValueError(f"{path.name} has an invalid neutral threshold.")
    if not is_nondecreasing(event_times_ms):
        raise ValueError(f"{path.name} event times are not chronological.")
    if not is_nondecreasing(future_event_times_ms):
        raise ValueError(f"{path.name} future event times are not chronological.")
    if not is_strictly_increasing(update_ids):
        raise ValueError(f"{path.name} update IDs are not strictly increasing.")
    if any(
        future_time < event_time
        for event_time, future_time in zip(
            event_times_ms,
            future_event_times_ms,
            strict=True,
        )
    ):
        raise ValueError(f"{path.name} contains a future time before its feature time.")

    symbol = rows[0]["symbol"]
    summary = SessionSummary(
        path=path,
        source_session=source_session,
        rows=len(rows),
        first_event_time_ms=event_times_ms[0],
        last_event_time_ms=event_times_ms[-1],
        last_future_event_time_ms=future_event_times_ms[-1],
        first_update_id=update_ids[0],
        last_update_id=update_ids[-1],
        down_labels=directions.count(-1),
        neutral_labels=directions.count(0),
        up_labels=directions.count(1),
        sha256=file_sha256(path),
    )

    return LoadedSession(
        fieldnames=tuple(fieldnames),
        rows=tuple(rows),
        summary=summary,
        symbol=symbol,
        label_horizon_ms=horizon_ms,
        neutral_threshold_bps=threshold_bps,
    )


def validate_unique_inputs(paths: list[Path]) -> None:
    """Reject duplicate source paths."""
    resolved_paths = [path.resolve() for path in paths]

    if len(resolved_paths) != len(set(resolved_paths)):
        raise ValueError("Each labeled session path must be unique.")


def validate_compatible_sessions(
    sessions: list[LoadedSession],
) -> None:
    """Require one consistent schema and label configuration."""
    reference = sessions[0]

    for session in sessions[1:]:
        if session.fieldnames != reference.fieldnames:
            raise ValueError(f"{session.summary.path.name} has a different CSV schema.")
        if session.symbol != reference.symbol:
            raise ValueError(f"{session.summary.path.name} has a different symbol.")
        if session.label_horizon_ms != reference.label_horizon_ms:
            raise ValueError(f"{session.summary.path.name} has a different label horizon.")
        if session.neutral_threshold_bps != reference.neutral_threshold_bps:
            raise ValueError(f"{session.summary.path.name} has a different neutral threshold.")


def validate_nonoverlapping_sessions(
    sessions: list[LoadedSession],
) -> None:
    """Reject sessions whose feature or label periods overlap."""
    for previous, current in zip(
        sessions,
        sessions[1:],
        strict=False,
    ):
        if current.summary.first_event_time_ms <= previous.summary.last_future_event_time_ms:
            raise ValueError(
                "Labeled sessions overlap: "
                f"{previous.summary.path.name} and "
                f"{current.summary.path.name}."
            )


def session_manifest(
    summary: SessionSummary,
) -> dict[str, object]:
    """Convert one session summary to JSON metadata."""
    return {
        "source_session": summary.source_session,
        "source_path": str(summary.path.resolve()),
        "source_sha256": summary.sha256,
        "rows": summary.rows,
        "first_event_time_ms": summary.first_event_time_ms,
        "last_event_time_ms": summary.last_event_time_ms,
        "last_future_event_time_ms": (summary.last_future_event_time_ms),
        "first_update_id": summary.first_update_id,
        "last_update_id": summary.last_update_id,
        "class_counts": {
            "down": summary.down_labels,
            "neutral": summary.neutral_labels,
            "up": summary.up_labels,
        },
    }


def combine_labeled_datasets(
    paths: list[Path],
    output_path: Path,
) -> CombinedDatasetReport:
    """Combine compatible labeled sessions without relabeling them."""
    if len(paths) < 2:
        raise ValueError("At least two labeled session files are required.")

    validate_unique_inputs(paths)

    output_resolved = output_path.resolve()
    if any(path.resolve() == output_resolved for path in paths):
        raise ValueError("Output path cannot replace an input dataset.")

    loaded_sessions = [
        load_session(
            path,
            source_session=f"session_{index:04d}_{path.stem}",
        )
        for index, path in enumerate(paths, start=1)
    ]

    validate_compatible_sessions(loaded_sessions)

    loaded_sessions.sort(
        key=lambda session: (
            session.summary.first_event_time_ms,
            session.summary.first_update_id,
        )
    )

    loaded_sessions = [
        LoadedSession(
            fieldnames=session.fieldnames,
            rows=session.rows,
            summary=SessionSummary(
                path=session.summary.path,
                source_session=(f"session_{index:04d}_{session.summary.path.stem}"),
                rows=session.summary.rows,
                first_event_time_ms=(session.summary.first_event_time_ms),
                last_event_time_ms=(session.summary.last_event_time_ms),
                last_future_event_time_ms=(session.summary.last_future_event_time_ms),
                first_update_id=(session.summary.first_update_id),
                last_update_id=(session.summary.last_update_id),
                down_labels=session.summary.down_labels,
                neutral_labels=(session.summary.neutral_labels),
                up_labels=session.summary.up_labels,
                sha256=session.summary.sha256,
            ),
            symbol=session.symbol,
            label_horizon_ms=session.label_horizon_ms,
            neutral_threshold_bps=(session.neutral_threshold_bps),
        )
        for index, session in enumerate(
            loaded_sessions,
            start=1,
        )
    ]

    validate_nonoverlapping_sessions(loaded_sessions)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_fieldnames = [
        *loaded_sessions[0].fieldnames,
        SOURCE_SESSION_COLUMN,
    ]

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=output_fieldnames,
        )
        writer.writeheader()

        for session in loaded_sessions:
            for row in session.rows:
                writer.writerow(
                    {
                        **row,
                        SOURCE_SESSION_COLUMN: (session.summary.source_session),
                    }
                )

    session_summaries = tuple(session.summary for session in loaded_sessions)
    total_rows = sum(summary.rows for summary in session_summaries)
    down_labels = sum(summary.down_labels for summary in session_summaries)
    neutral_labels = sum(summary.neutral_labels for summary in session_summaries)
    up_labels = sum(summary.up_labels for summary in session_summaries)

    manifest_path = output_path.with_suffix(".manifest.json")
    manifest = {
        "schema_version": 1,
        "output_dataset": str(output_path.resolve()),
        "session_count": len(session_summaries),
        "total_rows": total_rows,
        "symbol": loaded_sessions[0].symbol,
        "label_horizon_ms": (loaded_sessions[0].label_horizon_ms),
        "neutral_threshold_bps": str(loaded_sessions[0].neutral_threshold_bps),
        "class_counts": {
            "down": down_labels,
            "neutral": neutral_labels,
            "up": up_labels,
        },
        "source_session_column": SOURCE_SESSION_COLUMN,
        "sessions": [session_manifest(summary) for summary in session_summaries],
    }

    with manifest_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as output_file:
        json.dump(
            manifest,
            output_file,
            indent=2,
        )
        output_file.write("\n")

    return CombinedDatasetReport(
        output_path=output_path,
        manifest_path=manifest_path,
        session_count=len(session_summaries),
        total_rows=total_rows,
        symbol=loaded_sessions[0].symbol,
        label_horizon_ms=(loaded_sessions[0].label_horizon_ms),
        neutral_threshold_bps=(loaded_sessions[0].neutral_threshold_bps),
        down_labels=down_labels,
        neutral_labels=neutral_labels,
        up_labels=up_labels,
        sessions=session_summaries,
    )


def parse_args() -> argparse.Namespace:
    """Read source session paths and output path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help=("Two or more independently labeled session CSV files."),
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Combined labeled CSV output path.",
    )
    args = parser.parse_args()

    if len(args.paths) < 2:
        parser.error("at least two labeled session paths are required")

    return args


def main() -> None:
    """Combine selected labeled session datasets."""
    args = parse_args()
    report = combine_labeled_datasets(
        args.paths,
        args.output,
    )

    print(f"Sessions combined: {report.session_count}")
    print(f"Symbol: {report.symbol}")
    print(
        f"Label configuration: "
        f"horizon={report.label_horizon_ms} ms, "
        f"neutral threshold="
        f"{report.neutral_threshold_bps} bps"
    )
    print(f"Rows written: {report.total_rows}")
    print(
        "Class counts: "
        f"down={report.down_labels}, "
        f"neutral={report.neutral_labels}, "
        f"up={report.up_labels}"
    )

    for session in report.sessions:
        print(
            f"  {session.source_session}: "
            f"rows={session.rows}, "
            f"time={session.first_event_time_ms}-"
            f"{session.last_event_time_ms}"
        )

    print(f"Output: {report.output_path.resolve()}")
    print(f"Manifest: {report.manifest_path.resolve()}")


if __name__ == "__main__":
    main()
