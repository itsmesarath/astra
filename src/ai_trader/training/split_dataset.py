"""Split a labeled dataset into purged chronological partitions."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

from ai_trader.training.time_split import (
    IndexRange,
    create_purged_session_split,
    create_purged_time_split,
)

DEFAULT_DATA_DIRECTORY = Path("data/processed")
DEFAULT_TRAIN_FRACTION = 0.70
DEFAULT_VALIDATION_FRACTION = 0.15
SOURCE_SESSION_COLUMN = "source_session"

REQUIRED_COLUMNS = {
    "schema_version",
    "symbol",
    "depth_event_time_ms",
    "future_event_time_ms",
    "label_horizon_ms",
    "neutral_threshold_bps",
    "target_direction",
}


@dataclass(frozen=True, slots=True)
class PartitionSummary:
    """Summary of one chronological dataset partition."""

    name: str
    path: Path
    start: int
    stop: int
    rows: int
    down_labels: int
    neutral_labels: int
    up_labels: int
    source_sessions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DatasetSplitReport:
    """Summary of a completed purged dataset split."""

    input_path: Path
    output_directory: Path
    input_rows: int
    purged_rows: int
    train: PartitionSummary
    validation: PartitionSummary
    test: PartitionSummary
    manifest_path: Path


def find_latest_labeled_dataset() -> Path:
    """Return the newest labeled CSV dataset."""
    candidates = list(DEFAULT_DATA_DIRECTORY.glob("*_labeled_*.csv"))
    if not candidates:
        raise FileNotFoundError("No labeled datasets were found.")

    return max(candidates, key=lambda path: path.stat().st_mtime)


def create_output_directory(dataset_path: Path) -> Path:
    """Return the default directory for split artifacts."""
    return dataset_path.with_name(f"{dataset_path.stem}_split")


def read_labeled_rows(
    path: Path,
) -> tuple[list[str], list[dict[str, str]]]:
    """Read and validate the labeled dataset structure."""
    with path.open(encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)

        if reader.fieldnames is None:
            raise ValueError("Labeled dataset does not contain a header.")

        fieldnames = list(reader.fieldnames)
        missing_columns = REQUIRED_COLUMNS - set(fieldnames)

        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))
            raise ValueError(f"Labeled dataset is missing columns: {missing_text}.")

        rows = list(reader)

    if not rows:
        raise ValueError("Labeled dataset contains no rows.")

    if any(row["schema_version"] != "1" for row in rows):
        raise ValueError("Labeled dataset has an unsupported schema version.")

    symbols = {row["symbol"] for row in rows}
    if len(symbols) != 1 or "" in symbols:
        raise ValueError("Labeled dataset must contain exactly one nonempty symbol.")

    horizons = {row["label_horizon_ms"] for row in rows}
    if len(horizons) != 1:
        raise ValueError("Labeled dataset contains multiple label horizons.")

    thresholds = {row["neutral_threshold_bps"] for row in rows}
    if len(thresholds) != 1:
        raise ValueError("Labeled dataset contains multiple neutral thresholds.")

    try:
        directions = {int(row["target_direction"]) for row in rows}
    except ValueError as error:
        raise ValueError("Labeled dataset contains an invalid target direction.") from error

    if not directions <= {-1, 0, 1}:
        raise ValueError("Target directions must be -1, 0, or 1.")

    return fieldnames, rows


def write_partition(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
    index_range: IndexRange,
) -> None:
    """Write one chronological row range to CSV."""
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows[index_range.start : index_range.stop])


def summarize_partition(
    name: str,
    path: Path,
    rows: list[dict[str, str]],
    index_range: IndexRange,
    *,
    source_sessions: tuple[str, ...] = (),
) -> PartitionSummary:
    """Calculate size and class counts for one partition."""
    partition_rows = rows[index_range.start : index_range.stop]
    directions = [int(row["target_direction"]) for row in partition_rows]

    return PartitionSummary(
        name=name,
        path=path,
        start=index_range.start,
        stop=index_range.stop,
        rows=index_range.size,
        down_labels=directions.count(-1),
        neutral_labels=directions.count(0),
        up_labels=directions.count(1),
        source_sessions=source_sessions,
    )


def partition_manifest(
    summary: PartitionSummary,
) -> dict[str, object]:
    """Convert a partition summary into serializable metadata."""
    return {
        "file": summary.path.name,
        "start_index": summary.start,
        "stop_index": summary.stop,
        "rows": summary.rows,
        "class_counts": {
            "down": summary.down_labels,
            "neutral": summary.neutral_labels,
            "up": summary.up_labels,
        },
        "source_session_count": len(summary.source_sessions),
        "source_sessions": list(summary.source_sessions),
    }


def unique_sessions(rows: list[dict[str, str]], index_range: IndexRange) -> tuple[str, ...]:
    """Return source sessions in first-observed order for a row range."""
    return tuple(
        dict.fromkeys(
            row[SOURCE_SESSION_COLUMN] for row in rows[index_range.start : index_range.stop]
        )
    )


def split_labeled_dataset(
    dataset_path: Path,
    output_directory: Path,
    *,
    train_fraction: float,
    validation_fraction: float,
) -> DatasetSplitReport:
    """Create purged train, validation, and test CSV files."""
    fieldnames, rows = read_labeled_rows(dataset_path)

    try:
        event_times_ms = [int(row["depth_event_time_ms"]) for row in rows]
        future_event_times_ms = [int(row["future_event_time_ms"]) for row in rows]
    except ValueError as error:
        raise ValueError("Dataset contains an invalid event timestamp.") from error

    uses_session_boundaries = SOURCE_SESSION_COLUMN in fieldnames
    if uses_session_boundaries:
        source_sessions = [row[SOURCE_SESSION_COLUMN] for row in rows]
        split = create_purged_session_split(
            event_times_ms,
            future_event_times_ms,
            source_sessions,
            train_fraction=train_fraction,
            validation_fraction=validation_fraction,
        )
        train_sessions = unique_sessions(
            rows,
            IndexRange(0, split.purged_after_train.stop),
        )
        validation_sessions = unique_sessions(
            rows,
            IndexRange(split.validation.start, split.purged_after_validation.stop),
        )
        test_sessions = unique_sessions(rows, split.test)
    else:
        split = create_purged_time_split(
            event_times_ms,
            future_event_times_ms,
            train_fraction=train_fraction,
            validation_fraction=validation_fraction,
        )
        train_sessions = ()
        validation_sessions = ()
        test_sessions = ()

    output_directory.mkdir(parents=True, exist_ok=True)

    train_path = output_directory / "train.csv"
    validation_path = output_directory / "validation.csv"
    test_path = output_directory / "test.csv"

    write_partition(
        train_path,
        fieldnames,
        rows,
        split.train,
    )
    write_partition(
        validation_path,
        fieldnames,
        rows,
        split.validation,
    )
    write_partition(
        test_path,
        fieldnames,
        rows,
        split.test,
    )

    train_summary = summarize_partition(
        "train",
        train_path,
        rows,
        split.train,
        source_sessions=train_sessions,
    )
    validation_summary = summarize_partition(
        "validation",
        validation_path,
        rows,
        split.validation,
        source_sessions=validation_sessions,
    )
    test_summary = summarize_partition(
        "test",
        test_path,
        rows,
        split.test,
        source_sessions=test_sessions,
    )

    manifest_path = output_directory / "manifest.json"
    manifest = {
        "schema_version": 1,
        "source_dataset": str(dataset_path.resolve()),
        "input_rows": len(rows),
        "train_fraction": train_fraction,
        "validation_fraction": validation_fraction,
        "test_fraction": (1.0 - train_fraction - validation_fraction),
        "split_strategy": (
            "source_session_boundaries" if uses_session_boundaries else "row_boundaries"
        ),
        "source_session_column": (SOURCE_SESSION_COLUMN if uses_session_boundaries else None),
        "purged_rows": split.purged_rows,
        "purged_ranges": {
            "after_train": {
                "start_index": split.purged_after_train.start,
                "stop_index": split.purged_after_train.stop,
                "rows": split.purged_after_train.size,
            },
            "after_validation": {
                "start_index": (split.purged_after_validation.start),
                "stop_index": split.purged_after_validation.stop,
                "rows": split.purged_after_validation.size,
            },
        },
        "partitions": {
            "train": partition_manifest(train_summary),
            "validation": partition_manifest(validation_summary),
            "test": partition_manifest(test_summary),
        },
    }

    with manifest_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as output_file:
        json.dump(manifest, output_file, indent=2)
        output_file.write("\n")

    return DatasetSplitReport(
        input_path=dataset_path,
        output_directory=output_directory,
        input_rows=len(rows),
        purged_rows=split.purged_rows,
        train=train_summary,
        validation=validation_summary,
        test=test_summary,
        manifest_path=manifest_path,
    )


def parse_args() -> argparse.Namespace:
    """Read command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="Labeled CSV; defaults to the newest labeled dataset.",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        help="Optional directory for split files.",
    )
    parser.add_argument(
        "--train-fraction",
        type=float,
        default=DEFAULT_TRAIN_FRACTION,
        help=(f"Initial chronological training fraction (default: {DEFAULT_TRAIN_FRACTION})."),
    )
    parser.add_argument(
        "--validation-fraction",
        type=float,
        default=DEFAULT_VALIDATION_FRACTION,
        help=(
            f"Initial chronological validation fraction (default: {DEFAULT_VALIDATION_FRACTION})."
        ),
    )
    return parser.parse_args()


def print_partition(summary: PartitionSummary) -> None:
    """Print one partition summary."""
    print(
        f"{summary.name.title()}: "
        f"rows={summary.rows}, "
        f"down={summary.down_labels}, "
        f"neutral={summary.neutral_labels}, "
        f"up={summary.up_labels}"
    )


def main() -> None:
    """Split the selected or newest labeled dataset."""
    args = parse_args()
    dataset_path = args.path or find_latest_labeled_dataset()
    output_directory = args.output_directory or create_output_directory(dataset_path)

    report = split_labeled_dataset(
        dataset_path,
        output_directory,
        train_fraction=args.train_fraction,
        validation_fraction=args.validation_fraction,
    )

    print(f"Input: {report.input_path.resolve()}")
    print(f"Input rows: {report.input_rows}")
    print(f"Purged boundary rows: {report.purged_rows}")
    print_partition(report.train)
    print_partition(report.validation)
    print_partition(report.test)
    print(f"Output directory: {report.output_directory.resolve()}")
    print(f"Manifest: {report.manifest_path.resolve()}")


if __name__ == "__main__":
    main()
