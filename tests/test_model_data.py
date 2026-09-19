"""Tests for leakage-resistant model inputs."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pytest

from ai_trader.training.model_data import (
    KLINE_MODEL_FEATURE_NAMES,
    MODEL_FEATURE_NAMES,
    load_model_partition,
    row_to_kline_model_features,
    row_to_model_features,
)


def make_row() -> dict[str, str]:
    """Create one complete labeled feature row."""
    return {
        "spread": "1",
        "midpoint": "100",
        "microprice": "100.25",
        "bid_depth": "3",
        "ask_depth": "4",
        "book_imbalance": "0.2",
        "total_base_volume": "2",
        "trade_imbalance": "-0.5",
        "aggregate_trade_count": "3",
        "underlying_trade_count": "5",
        "target_direction": "1",
        "future_update_id": "999",
        "future_event_time_ms": "5000",
        "future_midpoint": "500",
        "future_return_bps": "40000",
    }


def write_rows(
    path: Path,
    rows: list[dict[str, str]],
) -> None:
    """Write model-data CSV rows."""
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=list(rows[0]),
        )
        writer.writeheader()
        writer.writerows(rows)


def test_transforms_only_stationary_causal_features() -> None:
    """The feature vector should match the explicit schema."""
    features = row_to_model_features(make_row())

    assert features.shape == (len(MODEL_FEATURE_NAMES),)
    assert features.dtype == np.float64
    np.testing.assert_allclose(
        features,
        np.asarray(
            [
                100.0,
                25.0,
                0.2,
                math.log1p(3),
                math.log1p(4),
                math.log1p(2),
                -0.5,
                math.log1p(3),
                math.log1p(5),
            ]
        ),
    )


def test_future_columns_cannot_change_model_features() -> None:
    """Future outcome metadata must never enter the feature vector."""
    original = make_row()
    modified = make_row()
    modified["future_update_id"] = "123456789"
    modified["future_event_time_ms"] = "999999999"
    modified["future_midpoint"] = "999999"
    modified["future_return_bps"] = "-999999"
    modified["target_direction"] = "-1"

    original_features = row_to_model_features(original)
    modified_features = row_to_model_features(modified)

    np.testing.assert_array_equal(
        original_features,
        modified_features,
    )


def test_loads_feature_matrix_and_separate_targets(
    tmp_path: Path,
) -> None:
    """Targets should be returned separately from model features."""
    path = tmp_path / "partition.csv"
    first = make_row()
    second = make_row()
    second["target_direction"] = "-1"
    second["book_imbalance"] = "-0.4"
    write_rows(path, [first, second])

    partition = load_model_partition(path)

    assert partition.rows == 2
    assert partition.columns == len(MODEL_FEATURE_NAMES)
    assert partition.features.shape == (2, 9)
    assert partition.features.dtype == np.float64
    assert partition.targets.dtype == np.int64
    np.testing.assert_array_equal(
        partition.targets,
        np.asarray([1, -1]),
    )
    assert partition.features[1, 2] == pytest.approx(-0.4)


def test_rejects_invalid_feature_values() -> None:
    """Impossible values must fail before reaching a model."""
    invalid_book = make_row()
    invalid_book["book_imbalance"] = "1.1"

    with pytest.raises(
        ValueError,
        match="Book imbalance must be between",
    ):
        row_to_model_features(invalid_book)

    negative_volume = make_row()
    negative_volume["total_base_volume"] = "-1"

    with pytest.raises(
        ValueError,
        match="Total base volume cannot be negative",
    ):
        row_to_model_features(negative_volume)


def make_kline_row() -> dict[str, str]:
    """Create one complete stationary historical-kline feature row."""
    row = {name: "0.25" for name in KLINE_MODEL_FEATURE_NAMES}
    row["taker_buy_ratio"] = "0.4"
    row["close_location"] = "0.6"
    row["target_direction"] = "1"
    return row


def test_loads_explicit_historical_kline_feature_schema(tmp_path: Path) -> None:
    """Historical partitions must retain their feature identity and column order."""
    path = tmp_path / "kline.csv"
    write_rows(path, [make_kline_row()])

    partition = load_model_partition(path)

    assert partition.feature_names == KLINE_MODEL_FEATURE_NAMES
    assert partition.columns == len(KLINE_MODEL_FEATURE_NAMES)
    np.testing.assert_array_equal(
        partition.features[0],
        row_to_kline_model_features(make_kline_row()),
    )


def test_rejects_invalid_kline_bounded_features() -> None:
    """Candle ratios with impossible values must fail before training."""
    row = make_kline_row()
    row["close_location"] = "1.1"

    with pytest.raises(ValueError, match="Close location must be between"):
        row_to_kline_model_features(row)
