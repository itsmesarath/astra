"""Tests for feature-dataset labeling."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest

from ai_trader.features.label_dataset import (
    LABEL_COLUMNS,
    create_output_path,
    label_feature_dataset,
)

FEATURE_COLUMNS = (
    "schema_version",
    "symbol",
    "depth_event_time_ms",
    "update_id",
    "midpoint",
    "book_imbalance",
)


def make_feature_rows() -> list[dict[str, str]]:
    """Create an irregularly timed causal feature dataset."""
    return [
        {
            "schema_version": "1",
            "symbol": "BTCUSDT",
            "depth_event_time_ms": "0",
            "update_id": "10",
            "midpoint": "100",
            "book_imbalance": "0.10",
        },
        {
            "schema_version": "1",
            "symbol": "BTCUSDT",
            "depth_event_time_ms": "400",
            "update_id": "11",
            "midpoint": "101",
            "book_imbalance": "0.20",
        },
        {
            "schema_version": "1",
            "symbol": "BTCUSDT",
            "depth_event_time_ms": "1000",
            "update_id": "12",
            "midpoint": "102",
            "book_imbalance": "-0.10",
        },
        {
            "schema_version": "1",
            "symbol": "BTCUSDT",
            "depth_event_time_ms": "1500",
            "update_id": "13",
            "midpoint": "101",
            "book_imbalance": "-0.20",
        },
        {
            "schema_version": "1",
            "symbol": "BTCUSDT",
            "depth_event_time_ms": "2100",
            "update_id": "14",
            "midpoint": "100",
            "book_imbalance": "0.00",
        },
    ]


def write_feature_dataset(
    path: Path,
    rows: list[dict[str, str]],
    *,
    fieldnames: tuple[str, ...] = FEATURE_COLUMNS,
) -> None:
    """Write a small feature CSV."""
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read every row from a CSV."""
    with path.open(encoding="utf-8", newline="") as input_file:
        return list(csv.DictReader(input_file))


def test_writes_labeled_rows_and_drops_incomplete_tail(
    tmp_path: Path,
) -> None:
    """Only observations with sufficient future data should be written."""
    feature_path = tmp_path / "features.csv"
    output_path = tmp_path / "labeled.csv"
    write_feature_dataset(feature_path, make_feature_rows())

    report = label_feature_dataset(
        feature_path,
        output_path,
        horizon_ms=1000,
        neutral_threshold_bps=Decimal("50"),
    )
    rows = read_rows(output_path)

    assert report.input_rows == 5
    assert report.labeled_rows == 3
    assert report.dropped_tail_rows == 2
    assert report.down_labels == 1
    assert report.neutral_labels == 1
    assert report.up_labels == 1

    assert len(rows) == 3
    assert list(rows[0]) == [*FEATURE_COLUMNS, *LABEL_COLUMNS]

    first = rows[0]
    assert first["update_id"] == "10"
    assert first["future_update_id"] == "12"
    assert first["label_horizon_ms"] == "1000"
    assert first["neutral_threshold_bps"] == "50"
    assert first["actual_horizon_ms"] == "1000"
    assert Decimal(first["future_midpoint"]) == Decimal("102")
    assert Decimal(first["future_return_bps"]) == Decimal("200")
    assert first["target_direction"] == "1"

    second = rows[1]
    assert second["update_id"] == "11"
    assert second["future_update_id"] == "13"
    assert second["actual_horizon_ms"] == "1100"
    assert Decimal(second["future_return_bps"]) == Decimal("0")
    assert second["target_direction"] == "0"

    third = rows[2]
    assert third["update_id"] == "12"
    assert third["future_update_id"] == "14"
    assert third["actual_horizon_ms"] == "1100"
    assert third["target_direction"] == "-1"


def test_rejects_missing_feature_columns(tmp_path: Path) -> None:
    """A dataset missing required causal columns must be rejected."""
    feature_path = tmp_path / "missing_columns.csv"
    output_path = tmp_path / "labeled.csv"
    rows = [
        {
            "schema_version": "1",
            "symbol": "BTCUSDT",
        }
    ]
    write_feature_dataset(
        feature_path,
        rows,
        fieldnames=("schema_version", "symbol"),
    )

    with pytest.raises(
        ValueError,
        match="Feature dataset is missing columns",
    ):
        label_feature_dataset(
            feature_path,
            output_path,
            horizon_ms=1000,
            neutral_threshold_bps=Decimal("0.5"),
        )


def test_rejects_nonincreasing_update_ids(tmp_path: Path) -> None:
    """Feature observations must remain in strict update-ID order."""
    feature_path = tmp_path / "bad_ids.csv"
    output_path = tmp_path / "labeled.csv"
    rows = make_feature_rows()
    rows[2]["update_id"] = rows[1]["update_id"]
    write_feature_dataset(feature_path, rows)

    with pytest.raises(
        ValueError,
        match="update IDs must be strictly increasing",
    ):
        label_feature_dataset(
            feature_path,
            output_path,
            horizon_ms=1000,
            neutral_threshold_bps=Decimal("0.5"),
        )


def test_default_output_path_records_label_configuration() -> None:
    """The generated filename should identify its labeling parameters."""
    output_path = create_output_path(
        Path("data/processed/sample_features_l5.csv"),
        horizon_ms=1000,
        neutral_threshold_bps=Decimal("0.5"),
    )

    assert output_path.name == ("sample_features_l5_labeled_h1000ms_t0p5bps.csv")
