"""Tests for checkpoint-based CSV inference."""

from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch

from ai_trader.models.checkpoint import (
    load_linear_checkpoint,
    save_linear_checkpoint,
)
from ai_trader.models.linear_classifier import (
    LinearDirectionClassifier,
)
from ai_trader.models.predict_csv import run_inference
from ai_trader.training.model_data import (
    MODEL_FEATURE_NAMES,
    row_to_model_features,
)
from ai_trader.training.standardize import fit_standardizer


def make_feature_row(
    *,
    target: str | None = None,
) -> dict[str, str]:
    """Create one causal feature row with an optional audit target."""
    row = {
        "depth_event_time_ms": "1000",
        "update_id": "10",
        "spread": "0.01",
        "midpoint": "100.005",
        "microprice": "100.006",
        "bid_depth": "2",
        "ask_depth": "3",
        "book_imbalance": "-0.2",
        "total_base_volume": "0.5",
        "trade_imbalance": "1",
        "aggregate_trade_count": "1",
        "underlying_trade_count": "2",
    }

    if target is not None:
        row["target_direction"] = target

    return row


def write_rows(
    path: Path,
    rows: list[dict[str, str]],
) -> None:
    """Write inference input rows."""
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=list(rows[0]),
        )
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read output prediction rows."""
    with path.open(encoding="utf-8", newline="") as input_file:
        return list(csv.DictReader(input_file))


def create_neutral_checkpoint(tmp_path: Path):
    """Create a checkpoint that always predicts neutral."""
    feature_row = row_to_model_features(make_feature_row())
    standardizer = fit_standardizer(np.vstack([feature_row, feature_row]))
    model = LinearDirectionClassifier(input_features=len(MODEL_FEATURE_NAMES))

    with torch.no_grad():
        model.linear.weight.zero_()
        model.linear.bias.copy_(torch.tensor([0.0, 1.0, 0.0]))

    checkpoint_path = tmp_path / "checkpoint"
    save_linear_checkpoint(
        checkpoint_path,
        model,
        standardizer,
        feature_names=MODEL_FEATURE_NAMES,
        training_metadata={
            "source_split_directory": str(tmp_path),
        },
    )
    return load_linear_checkpoint(checkpoint_path)


def test_runs_inference_without_historical_targets(
    tmp_path: Path,
) -> None:
    """Live-style causal rows should not require target columns."""
    checkpoint = create_neutral_checkpoint(tmp_path)
    input_path = tmp_path / "features.csv"
    output_path = tmp_path / "predictions.csv"
    write_rows(input_path, [make_feature_row()])

    report = run_inference(
        checkpoint,
        input_path,
        output_path,
    )
    output_rows = read_rows(output_path)

    assert report.input_rows == 1
    assert report.predicted_down == 0
    assert report.predicted_neutral == 1
    assert report.predicted_up == 0
    assert report.evaluation is None

    assert len(output_rows) == 1
    assert output_rows[0]["predicted_direction"] == "0"
    assert "actual_direction" not in output_rows[0]
    assert float(output_rows[0]["confidence"]) > 0.5

    probability_sum = sum(
        float(output_rows[0][column])
        for column in (
            "probability_down",
            "probability_neutral",
            "probability_up",
        )
    )
    assert probability_sum == pytest.approx(
        1.0,
        abs=1e-6,
    )


def test_evaluates_optional_historical_targets(
    tmp_path: Path,
) -> None:
    """Historical targets may be audited after prediction."""
    checkpoint = create_neutral_checkpoint(tmp_path)
    input_path = tmp_path / "labeled.csv"
    output_path = tmp_path / "predictions.csv"
    write_rows(
        input_path,
        [
            make_feature_row(target="0"),
            make_feature_row(target="1"),
        ],
    )

    report = run_inference(
        checkpoint,
        input_path,
        output_path,
    )
    output_rows = read_rows(output_path)

    assert report.evaluation is not None
    assert report.evaluation.total == 2
    assert report.evaluation.accuracy == pytest.approx(0.5)
    assert [row["actual_direction"] for row in output_rows] == ["0", "1"]


def test_rejects_checkpoint_feature_schema_mismatch(
    tmp_path: Path,
) -> None:
    """Inference must reject a differently ordered feature schema."""
    checkpoint = create_neutral_checkpoint(tmp_path)
    incompatible_checkpoint = replace(
        checkpoint,
        feature_names=tuple(reversed(checkpoint.feature_names)),
    )

    with pytest.raises(
        ValueError,
        match="feature schema does not match",
    ):
        run_inference(
            incompatible_checkpoint,
            tmp_path / "unused.csv",
            tmp_path / "unused_output.csv",
        )
