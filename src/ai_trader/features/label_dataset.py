"""Add future-return labels to a causal feature dataset."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ai_trader.features.labels import calculate_future_return_labels

DEFAULT_DATA_DIRECTORY = Path("data/processed")
DEFAULT_HORIZON_MS = 1000
DEFAULT_NEUTRAL_THRESHOLD_BPS = Decimal("0.5")

REQUIRED_FEATURE_COLUMNS = {
    "schema_version",
    "symbol",
    "depth_event_time_ms",
    "update_id",
    "midpoint",
}

LABEL_COLUMNS = (
    "label_horizon_ms",
    "neutral_threshold_bps",
    "future_update_id",
    "future_event_time_ms",
    "actual_horizon_ms",
    "future_midpoint",
    "future_return_bps",
    "target_direction",
)


@dataclass(frozen=True, slots=True)
class LabelingReport:
    """Summary of one completed labeling operation."""

    input_rows: int
    labeled_rows: int
    dropped_tail_rows: int
    down_labels: int
    neutral_labels: int
    up_labels: int


def find_latest_feature_dataset() -> Path:
    """Return the newest unlabeled feature CSV."""
    candidates = [
        path
        for path in DEFAULT_DATA_DIRECTORY.glob("*_features_l*.csv")
        if "_labeled_" not in path.stem
    ]

    if not candidates:
        raise FileNotFoundError("No feature datasets were found.")

    return max(candidates, key=lambda path: path.stat().st_mtime)


def threshold_filename_text(value: Decimal) -> str:
    """Convert a decimal threshold into a filename-safe value."""
    return format(value.normalize(), "f").replace(".", "p")


def create_output_path(
    feature_path: Path,
    *,
    horizon_ms: int,
    neutral_threshold_bps: Decimal,
) -> Path:
    """Create the default path for a labeled feature dataset."""
    threshold_text = threshold_filename_text(neutral_threshold_bps)
    filename = f"{feature_path.stem}_labeled_h{horizon_ms}ms_t{threshold_text}bps.csv"
    return feature_path.with_name(filename)


def read_feature_rows(
    path: Path,
) -> tuple[list[str], list[dict[str, str]]]:
    """Read and validate the structural feature columns."""
    with path.open(encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)

        if reader.fieldnames is None:
            raise ValueError("Feature dataset does not contain a header.")

        fieldnames = list(reader.fieldnames)
        missing_columns = REQUIRED_FEATURE_COLUMNS - set(fieldnames)

        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))
            raise ValueError(f"Feature dataset is missing columns: {missing_text}.")

        duplicate_label_columns = set(LABEL_COLUMNS) & set(fieldnames)
        if duplicate_label_columns:
            duplicate_text = ", ".join(sorted(duplicate_label_columns))
            raise ValueError(f"Feature dataset already contains label columns: {duplicate_text}.")

        rows = list(reader)

    if not rows:
        raise ValueError("Feature dataset contains no rows.")

    if any(row["schema_version"] != "1" for row in rows):
        raise ValueError("Feature dataset has an unsupported schema version.")

    symbols = {row["symbol"] for row in rows}
    if len(symbols) != 1 or "" in symbols:
        raise ValueError("Feature dataset must contain exactly one nonempty symbol.")

    try:
        update_ids = [int(row["update_id"]) for row in rows]
    except ValueError as error:
        raise ValueError("Feature dataset has an invalid update ID.") from error

    if any(
        current_id >= next_id
        for current_id, next_id in zip(
            update_ids,
            update_ids[1:],
            strict=False,
        )
    ):
        raise ValueError("Feature update IDs must be strictly increasing.")

    return fieldnames, rows


def label_feature_dataset(
    feature_path: Path,
    output_path: Path,
    *,
    horizon_ms: int,
    neutral_threshold_bps: Decimal,
) -> LabelingReport:
    """Add future labels while preserving the original causal features."""
    if horizon_ms <= 0:
        raise ValueError("Label horizon must be greater than zero.")
    if neutral_threshold_bps < 0:
        raise ValueError("Neutral threshold cannot be negative.")

    feature_columns, rows = read_feature_rows(feature_path)

    try:
        event_times_ms = [int(row["depth_event_time_ms"]) for row in rows]
        midpoints = [Decimal(row["midpoint"]) for row in rows]
    except ValueError as error:
        raise ValueError("Feature dataset contains an invalid time or midpoint.") from error

    labels = calculate_future_return_labels(
        event_times_ms,
        midpoints,
        horizon_ms=horizon_ms,
        neutral_threshold_bps=neutral_threshold_bps,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    labeled_rows = 0
    down_labels = 0
    neutral_labels = 0
    up_labels = 0

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=[*feature_columns, *LABEL_COLUMNS],
        )
        writer.writeheader()

        for row, label in zip(rows, labels, strict=True):
            if label is None:
                continue

            future_row = rows[label.future_index]
            labeled_row = {
                **row,
                "label_horizon_ms": horizon_ms,
                "neutral_threshold_bps": str(neutral_threshold_bps),
                "future_update_id": future_row["update_id"],
                "future_event_time_ms": label.future_event_time_ms,
                "actual_horizon_ms": label.actual_horizon_ms,
                "future_midpoint": str(label.future_midpoint),
                "future_return_bps": str(label.return_bps),
                "target_direction": label.direction,
            }
            writer.writerow(labeled_row)
            labeled_rows += 1

            if label.direction == -1:
                down_labels += 1
            elif label.direction == 0:
                neutral_labels += 1
            else:
                up_labels += 1

    return LabelingReport(
        input_rows=len(rows),
        labeled_rows=labeled_rows,
        dropped_tail_rows=len(rows) - labeled_rows,
        down_labels=down_labels,
        neutral_labels=neutral_labels,
        up_labels=up_labels,
    )


def parse_args() -> argparse.Namespace:
    """Read command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="Feature CSV; defaults to the newest unlabeled feature file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output CSV path.",
    )
    parser.add_argument(
        "--horizon-ms",
        type=int,
        default=DEFAULT_HORIZON_MS,
        help=(f"Future return horizon in milliseconds (default: {DEFAULT_HORIZON_MS})."),
    )
    parser.add_argument(
        "--neutral-threshold-bps",
        type=Decimal,
        default=DEFAULT_NEUTRAL_THRESHOLD_BPS,
        help=(
            "Absolute neutral-band threshold in basis points "
            f"(default: {DEFAULT_NEUTRAL_THRESHOLD_BPS})."
        ),
    )
    args = parser.parse_args()

    if args.horizon_ms <= 0:
        parser.error("--horizon-ms must be greater than zero")
    if args.neutral_threshold_bps < 0:
        parser.error("--neutral-threshold-bps cannot be negative")

    return args


def main() -> None:
    """Label the selected or latest feature dataset."""
    args = parse_args()
    feature_path = args.path or find_latest_feature_dataset()
    output_path = args.output or create_output_path(
        feature_path,
        horizon_ms=args.horizon_ms,
        neutral_threshold_bps=args.neutral_threshold_bps,
    )

    report = label_feature_dataset(
        feature_path,
        output_path,
        horizon_ms=args.horizon_ms,
        neutral_threshold_bps=args.neutral_threshold_bps,
    )

    print(f"Input: {feature_path.resolve()}")
    print(f"Input rows: {report.input_rows}")
    print(f"Labeled rows: {report.labeled_rows}")
    print(f"Dropped tail rows: {report.dropped_tail_rows}")
    print(
        "Class counts: "
        f"down={report.down_labels}, "
        f"neutral={report.neutral_labels}, "
        f"up={report.up_labels}"
    )
    print(f"Output: {output_path.resolve()}")


if __name__ == "__main__":
    main()
