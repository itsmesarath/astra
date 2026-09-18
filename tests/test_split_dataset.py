"""Tests for labeled dataset partitioning."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from ai_trader.training.split_dataset import split_labeled_dataset

FIELDNAMES = (
    "schema_version",
    "symbol",
    "depth_event_time_ms",
    "future_event_time_ms",
    "label_horizon_ms",
    "neutral_threshold_bps",
    "target_direction",
    "midpoint",
)


def make_labeled_rows() -> list[dict[str, str]]:
    """Create twenty chronological labeled observations."""
    directions = (-1, 0, 1)
    rows = []

    for index in range(20):
        rows.append(
            {
                "schema_version": "1",
                "symbol": "BTCUSDT",
                "depth_event_time_ms": str(index * 100),
                "future_event_time_ms": str((index + 2) * 100),
                "label_horizon_ms": "200",
                "neutral_threshold_bps": "0.5",
                "target_direction": str(directions[index % len(directions)]),
                "midpoint": str(100 + index),
            }
        )

    return rows


def write_labeled_dataset(
    path: Path,
    rows: list[dict[str, str]],
) -> None:
    """Write a labeled CSV fixture."""
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=FIELDNAMES,
        )
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read all rows from a CSV file."""
    with path.open(encoding="utf-8", newline="") as input_file:
        return list(csv.DictReader(input_file))


def test_writes_purged_chronological_partitions(
    tmp_path: Path,
) -> None:
    """Split files must contain only their retained row ranges."""
    dataset_path = tmp_path / "labeled.csv"
    output_directory = tmp_path / "split"
    write_labeled_dataset(dataset_path, make_labeled_rows())

    report = split_labeled_dataset(
        dataset_path,
        output_directory,
        train_fraction=0.60,
        validation_fraction=0.20,
    )

    train_rows = read_rows(output_directory / "train.csv")
    validation_rows = read_rows(output_directory / "validation.csv")
    test_rows = read_rows(output_directory / "test.csv")

    assert report.input_rows == 20
    assert report.purged_rows == 4

    assert report.train.rows == 10
    assert report.train.down_labels == 4
    assert report.train.neutral_labels == 3
    assert report.train.up_labels == 3

    assert report.validation.rows == 2
    assert report.validation.down_labels == 1
    assert report.validation.neutral_labels == 1
    assert report.validation.up_labels == 0

    assert report.test.rows == 4
    assert report.test.down_labels == 1
    assert report.test.neutral_labels == 2
    assert report.test.up_labels == 1

    assert [row["depth_event_time_ms"] for row in train_rows] == [
        str(index * 100) for index in range(10)
    ]
    assert [row["depth_event_time_ms"] for row in validation_rows] == ["1200", "1300"]
    assert [row["depth_event_time_ms"] for row in test_rows] == [
        "1600",
        "1700",
        "1800",
        "1900",
    ]


def test_writes_auditable_split_manifest(tmp_path: Path) -> None:
    """The manifest must record ranges, counts, and output files."""
    dataset_path = tmp_path / "labeled.csv"
    output_directory = tmp_path / "split"
    write_labeled_dataset(dataset_path, make_labeled_rows())

    report = split_labeled_dataset(
        dataset_path,
        output_directory,
        train_fraction=0.60,
        validation_fraction=0.20,
    )

    with report.manifest_path.open(encoding="utf-8") as input_file:
        manifest = json.load(input_file)

    assert manifest["schema_version"] == 1
    assert manifest["input_rows"] == 20
    assert manifest["train_fraction"] == 0.60
    assert manifest["validation_fraction"] == 0.20
    assert manifest["test_fraction"] == pytest.approx(0.20)
    assert manifest["purged_rows"] == 4

    assert manifest["purged_ranges"]["after_train"] == {
        "start_index": 10,
        "stop_index": 12,
        "rows": 2,
    }
    assert manifest["purged_ranges"]["after_validation"] == {
        "start_index": 14,
        "stop_index": 16,
        "rows": 2,
    }

    assert manifest["partitions"]["train"]["file"] == "train.csv"
    assert manifest["partitions"]["train"]["rows"] == 10
    assert manifest["partitions"]["validation"]["rows"] == 2
    assert manifest["partitions"]["test"]["rows"] == 4


def test_rejects_multiple_label_configurations(
    tmp_path: Path,
) -> None:
    """One dataset must not mix different prediction horizons."""
    dataset_path = tmp_path / "mixed_labels.csv"
    output_directory = tmp_path / "split"
    rows = make_labeled_rows()
    rows[-1]["label_horizon_ms"] = "1000"
    write_labeled_dataset(dataset_path, rows)

    with pytest.raises(
        ValueError,
        match="multiple label horizons",
    ):
        split_labeled_dataset(
            dataset_path,
            output_directory,
            train_fraction=0.60,
            validation_fraction=0.20,
        )
