"""Evaluate a training-majority no-skill classification baseline."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ai_trader.training.metrics import (
    CLASS_LABELS,
    ClassificationReport,
    evaluate_classification,
)

DEFAULT_DATA_DIRECTORY = Path("data/processed")
TIE_BREAK_ORDER = (0, -1, 1)

LABEL_NAMES = {
    -1: "DOWN",
    0: "NEUTRAL",
    1: "UP",
}


@dataclass(frozen=True, slots=True)
class MajorityBaselineReport:
    """Validation and test results for a majority baseline."""

    majority_label: int
    train_rows: int
    validation: ClassificationReport
    test: ClassificationReport


def find_latest_split_directory() -> Path:
    """Return the newest complete dataset split directory."""
    candidates = [
        path
        for path in DEFAULT_DATA_DIRECTORY.glob("*_split")
        if path.is_dir()
        and (path / "manifest.json").is_file()
        and (path / "train.csv").is_file()
        and (path / "validation.csv").is_file()
        and (path / "test.csv").is_file()
    ]

    if not candidates:
        raise FileNotFoundError("No complete split dataset directories were found.")

    return max(
        candidates,
        key=lambda path: (path / "manifest.json").stat().st_mtime,
    )


def read_target_labels(path: Path) -> list[int]:
    """Read and validate target directions from one partition."""
    with path.open(encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)

        if reader.fieldnames is None:
            raise ValueError(f"{path.name} does not contain a header.")
        if "target_direction" not in reader.fieldnames:
            raise ValueError(f"{path.name} does not contain target_direction.")

        try:
            labels = [int(row["target_direction"]) for row in reader]
        except ValueError as error:
            raise ValueError(f"{path.name} contains an invalid target direction.") from error

    if not labels:
        raise ValueError(f"{path.name} contains no data rows.")
    if any(label not in CLASS_LABELS for label in labels):
        raise ValueError(f"{path.name} contains an unsupported target direction.")

    return labels


def choose_majority_label(labels: list[int]) -> int:
    """Choose the most frequent training class deterministically."""
    if not labels:
        raise ValueError("At least one training label is required.")
    if any(label not in CLASS_LABELS for label in labels):
        raise ValueError("Training labels must be -1, 0, or 1.")

    counts = Counter(labels)
    largest_count = max(counts.values())

    for label in TIE_BREAK_ORDER:
        if counts[label] == largest_count:
            return label

    raise RuntimeError("Unable to select a majority class.")


def evaluate_constant_prediction(
    actual: list[int],
    *,
    predicted_label: int,
) -> ClassificationReport:
    """Evaluate one constant prediction against actual labels."""
    predictions = [predicted_label] * len(actual)
    return evaluate_classification(actual, predictions)


def evaluate_majority_baseline(
    split_directory: Path,
) -> MajorityBaselineReport:
    """Fit the majority class on train and evaluate later partitions."""
    train_labels = read_target_labels(split_directory / "train.csv")
    validation_labels = read_target_labels(split_directory / "validation.csv")
    test_labels = read_target_labels(split_directory / "test.csv")

    majority_label = choose_majority_label(train_labels)

    return MajorityBaselineReport(
        majority_label=majority_label,
        train_rows=len(train_labels),
        validation=evaluate_constant_prediction(
            validation_labels,
            predicted_label=majority_label,
        ),
        test=evaluate_constant_prediction(
            test_labels,
            predicted_label=majority_label,
        ),
    )


def print_class_metrics(report: ClassificationReport) -> None:
    """Print per-class precision, recall, and F1."""
    for metrics in report.classes:
        print(
            f"  {LABEL_NAMES[metrics.label]:7s} | "
            f"support={metrics.support:5d} | "
            f"precision={metrics.precision:.4f} | "
            f"recall={metrics.recall:.4f} | "
            f"f1={metrics.f1:.4f}"
        )


def print_evaluation(
    name: str,
    report: ClassificationReport,
) -> None:
    """Print one partition's baseline metrics."""
    print(f"\n{name}:")
    print(f"  Rows: {report.total}")
    print(f"  Accuracy: {report.accuracy:.4f}")
    print(f"  Balanced accuracy: {report.balanced_accuracy:.4f}")
    print(f"  Macro F1: {report.macro_f1:.4f}")
    print("  Per-class metrics:")
    print_class_metrics(report)
    print("  Confusion matrix (actual rows DOWN/NEUTRAL/UP, predicted columns DOWN/NEUTRAL/UP):")
    for row in report.confusion_matrix:
        print(f"    {row}")


def parse_args() -> argparse.Namespace:
    """Read an optional split-directory path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "split_directory",
        nargs="?",
        type=Path,
        help="Split directory; defaults to the newest complete split.",
    )
    return parser.parse_args()


def main() -> None:
    """Evaluate the majority baseline."""
    args = parse_args()
    split_directory = args.split_directory or find_latest_split_directory()
    report = evaluate_majority_baseline(split_directory)

    majority_name = LABEL_NAMES[report.majority_label]

    print(f"Split directory: {split_directory.resolve()}")
    print(f"Training rows: {report.train_rows}")
    print(f"Training-majority prediction: {majority_name} ({report.majority_label})")

    print_evaluation("Validation", report.validation)
    print_evaluation("Test", report.test)


if __name__ == "__main__":
    main()
