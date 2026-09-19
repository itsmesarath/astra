"""Tests for linear training-checkpoint metadata."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from ai_trader.models.linear_classifier import (
    LinearDirectionClassifier,
)
from ai_trader.training.metrics import evaluate_classification
from ai_trader.training.standardize import fit_standardizer
from ai_trader.training.train_linear import (
    LinearFitResult,
    TrainingConfig,
)
from ai_trader.training.train_linear_checkpoint import (
    classification_report_to_dict,
    create_checkpoint_path,
    create_training_metadata,
)


def make_training_result() -> LinearFitResult:
    """Create a small result object for metadata testing."""
    model = LinearDirectionClassifier(input_features=2)
    standardizer = fit_standardizer(
        np.asarray(
            [
                [0.0, 1.0],
                [2.0, 3.0],
            ]
        )
    )
    report = evaluate_classification(
        actual=[-1, 0, 1],
        predicted=[-1, 0, 0],
    )

    return LinearFitResult(
        model=model,
        standardizer=standardizer,
        best_epoch=7,
        epochs_trained=57,
        class_weights=np.asarray(
            [2.0, 0.5, 2.5],
            dtype=np.float32,
        ),
        validation=report,
        device="cpu",
    )


def test_serializes_classification_report() -> None:
    """Every metric should be converted into JSON-safe values."""
    report = evaluate_classification(
        actual=[-1, 0, 1],
        predicted=[-1, 0, 0],
    )

    serialized = classification_report_to_dict(report)

    assert serialized["total"] == 3
    assert serialized["correct"] == 2
    assert serialized["confusion_matrix"] == [
        [1, 0, 0],
        [0, 1, 0],
        [0, 1, 0],
    ]
    assert serialized["missing_actual_classes"] == []
    assert len(serialized["classes"]) == 3

    json.dumps(serialized)


def test_creates_deterministic_utc_checkpoint_path() -> None:
    """Checkpoint names should contain a normalized UTC timestamp."""
    created_at = datetime(
        2026,
        9,
        19,
        13,
        39,
        16,
        tzinfo=UTC,
    )

    path = create_checkpoint_path(created_at=created_at)

    assert path == Path("checkpoints/linear_20260919T133916Z")

    with pytest.raises(
        ValueError,
        match="must include a timezone",
    ):
        create_checkpoint_path(
            created_at=datetime(2026, 9, 19),
        )


def test_creates_complete_json_safe_training_metadata(
    tmp_path: Path,
) -> None:
    """Metadata must record configuration, source, and results."""
    split_directory = tmp_path / "split"
    config = TrainingConfig(
        max_epochs=100,
        patience=20,
        learning_rate=0.02,
        weight_decay=0.001,
        seed=123,
        device="cpu",
    )
    result = make_training_result()
    created_at = datetime(
        2026,
        9,
        19,
        14,
        0,
        tzinfo=UTC,
    )

    metadata = create_training_metadata(
        split_directory=split_directory,
        config=config,
        result=result,
        created_at=created_at,
    )

    assert metadata["created_at_utc"] == ("2026-09-19T14:00:00+00:00")
    assert metadata["source_split_directory"] == str(split_directory.resolve())
    assert metadata["configuration"] == {
        "max_epochs": 100,
        "patience": 20,
        "learning_rate": 0.02,
        "weight_decay": 0.001,
        "class_weight_power": 1.0,
        "seed": 123,
        "device": "cpu",
    }
    assert metadata["device"] == "cpu"
    assert metadata["best_epoch"] == 7
    assert metadata["epochs_trained"] == 57
    assert metadata["class_weights"] == [2.0, 0.5, 2.5]
    assert metadata["validation"]["total"] == 3
    assert "test" not in metadata

    json.dumps(metadata)
