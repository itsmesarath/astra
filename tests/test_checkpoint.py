"""Tests for versioned linear checkpoints."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from ai_trader.models.checkpoint import (
    METADATA_FILENAME,
    MODEL_FILENAME,
    SCALER_FILENAME,
    load_linear_checkpoint,
    save_linear_checkpoint,
)
from ai_trader.models.linear_classifier import (
    LinearDirectionClassifier,
)
from ai_trader.training.standardize import fit_standardizer


def make_model() -> LinearDirectionClassifier:
    """Create a deterministic two-feature classifier."""
    model = LinearDirectionClassifier(input_features=2)

    with torch.no_grad():
        model.linear.weight.copy_(
            torch.tensor(
                [
                    [-1.0, 0.0],
                    [0.0, 0.0],
                    [1.0, 0.0],
                ]
            )
        )
        model.linear.bias.copy_(torch.tensor([0.0, 0.5, 0.0]))

    return model


def test_checkpoint_round_trip_preserves_predictions(
    tmp_path: Path,
) -> None:
    """Saved and loaded predictions must be identical."""
    model = make_model()
    standardizer = fit_standardizer(
        np.asarray(
            [
                [-1.0, 0.0],
                [1.0, 0.0],
            ]
        )
    )
    feature_names = ("first", "second")
    checkpoint_path = tmp_path / "linear_test"

    raw_features = np.asarray(
        [
            [-2.0, 0.0],
            [0.0, 0.0],
            [2.0, 0.0],
        ]
    )

    saved_path = save_linear_checkpoint(
        checkpoint_path,
        model,
        standardizer,
        feature_names=feature_names,
        training_metadata={
            "best_epoch": 7,
            "seed": 42,
        },
    )
    loaded = load_linear_checkpoint(saved_path)

    assert (saved_path / MODEL_FILENAME).is_file()
    assert (saved_path / SCALER_FILENAME).is_file()
    assert (saved_path / METADATA_FILENAME).is_file()
    assert loaded.feature_names == feature_names
    assert loaded.metadata["training"] == {
        "best_epoch": 7,
        "seed": 42,
    }

    np.testing.assert_array_equal(
        loaded.predict(raw_features),
        np.asarray([-1, 0, 1]),
    )

    probabilities = loaded.predict_probabilities(raw_features)
    assert probabilities.shape == (3, 3)
    np.testing.assert_allclose(
        probabilities.sum(axis=1),
        np.ones(3),
        atol=1e-7,
    )


def test_checkpoint_refuses_to_overwrite(
    tmp_path: Path,
) -> None:
    """Existing checkpoint directories must not be overwritten."""
    model = make_model()
    standardizer = fit_standardizer(
        np.asarray(
            [
                [-1.0, 0.0],
                [1.0, 0.0],
            ]
        )
    )
    checkpoint_path = tmp_path / "existing"
    checkpoint_path.mkdir()

    with pytest.raises(
        FileExistsError,
        match="already exists",
    ):
        save_linear_checkpoint(
            checkpoint_path,
            model,
            standardizer,
            feature_names=("first", "second"),
            training_metadata={},
        )


def test_checkpoint_rejects_inconsistent_schema(
    tmp_path: Path,
) -> None:
    """Model, scaler, and feature schema dimensions must agree."""
    model = make_model()
    standardizer = fit_standardizer(
        np.asarray(
            [
                [-1.0, 0.0],
                [1.0, 0.0],
            ]
        )
    )

    with pytest.raises(
        ValueError,
        match="Model input count does not match",
    ):
        save_linear_checkpoint(
            tmp_path / "bad_schema",
            model,
            standardizer,
            feature_names=("only_one",),
            training_metadata={},
        )
