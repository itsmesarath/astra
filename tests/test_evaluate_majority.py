"""Tests for the training-majority baseline."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from ai_trader.training.evaluate_majority import (
    choose_majority_label,
    evaluate_constant_prediction,
    evaluate_majority_baseline,
    read_target_labels,
)


def write_partition(
    path: Path,
    labels: list[int],
) -> None:
    """Write a minimal split partition."""
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=["target_direction"],
        )
        writer.writeheader()

        for label in labels:
            writer.writerow({"target_direction": label})


def test_selects_training_majority_class() -> None:
    """The most common training target should be selected."""
    assert choose_majority_label([-1, 0, 0, 0, 1, 1]) == 0
    assert choose_majority_label([-1, -1, 0, 1]) == -1
    assert choose_majority_label([-1, 0, 1, 1]) == 1


def test_uses_deterministic_tie_breaking() -> None:
    """A tied majority should prefer neutral, then down, then up."""
    assert choose_majority_label([-1, 0, 1]) == 0
    assert choose_majority_label([-1, 1]) == -1


def test_evaluates_constant_prediction() -> None:
    """A constant prediction should produce expected metrics."""
    report = evaluate_constant_prediction(
        actual=[-1, 0, 0, 1],
        predicted_label=0,
    )

    assert report.total == 4
    assert report.correct == 2
    assert report.accuracy == pytest.approx(0.5)
    assert report.balanced_accuracy == pytest.approx(1 / 3)
    assert report.classes[0].recall == pytest.approx(0.0)
    assert report.classes[1].recall == pytest.approx(1.0)
    assert report.classes[2].recall == pytest.approx(0.0)


def test_evaluates_split_using_training_labels_only(
    tmp_path: Path,
) -> None:
    """The predicted class must be fitted only from training data."""
    split_directory = tmp_path / "split"
    split_directory.mkdir()

    write_partition(
        split_directory / "train.csv",
        [-1, 0, 0, 0, 1],
    )
    write_partition(
        split_directory / "validation.csv",
        [-1, 0, 1],
    )
    write_partition(
        split_directory / "test.csv",
        [1, 1, 0],
    )

    report = evaluate_majority_baseline(split_directory)

    assert report.majority_label == 0
    assert report.train_rows == 5
    assert report.validation.accuracy == pytest.approx(1 / 3)
    assert report.test.accuracy == pytest.approx(1 / 3)


def test_rejects_invalid_or_empty_targets(tmp_path: Path) -> None:
    """Partition files must contain supported target labels."""
    invalid_path = tmp_path / "invalid.csv"
    empty_path = tmp_path / "empty.csv"

    write_partition(invalid_path, [2])
    write_partition(empty_path, [])

    with pytest.raises(
        ValueError,
        match="unsupported target direction",
    ):
        read_target_labels(invalid_path)

    with pytest.raises(
        ValueError,
        match="contains no data rows",
    ):
        read_target_labels(empty_path)

    with pytest.raises(
        ValueError,
        match="At least one training label",
    ):
        choose_majority_label([])
