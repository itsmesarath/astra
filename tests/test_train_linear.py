"""Tests for linear baseline training."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from ai_trader.models.linear_classifier import (
    LinearDirectionClassifier,
)
from ai_trader.training.model_data import ModelPartition
from ai_trader.training.train_linear import (
    TrainingConfig,
    set_reproducible_seed,
    soften_class_weights,
    train_linear_baseline,
    validate_config,
)


def make_separable_partition() -> ModelPartition:
    """Create a small balanced, linearly separable dataset."""
    features = np.asarray(
        [
            [-3.0, 0.0],
            [-2.5, 0.1],
            [-2.0, -0.1],
        ]
        * 4
        + [
            [0.0, -1.0],
            [0.0, 0.0],
            [0.0, 1.0],
        ]
        * 4
        + [
            [2.0, -0.1],
            [2.5, 0.1],
            [3.0, 0.0],
        ]
        * 4,
        dtype=np.float64,
    )
    targets = np.asarray(
        [-1] * 12 + [0] * 12 + [1] * 12,
        dtype=np.int64,
    )

    return ModelPartition(
        features=features,
        targets=targets,
    )


def test_trains_and_early_stops_on_separable_data() -> None:
    """The trainer should learn a simple balanced classification task."""
    train = make_separable_partition()
    validation = make_separable_partition()
    test = make_separable_partition()

    result = train_linear_baseline(
        train,
        validation,
        test,
        TrainingConfig(
            max_epochs=120,
            patience=15,
            learning_rate=0.1,
            weight_decay=0.0,
            seed=42,
            device="cpu",
        ),
    )

    assert result.device == "cpu"
    assert 1 <= result.best_epoch <= result.epochs_trained
    assert result.epochs_trained < 120
    np.testing.assert_allclose(
        result.class_weights,
        np.asarray([1.0, 1.0, 1.0]),
    )
    assert result.validation.accuracy == pytest.approx(1.0)
    assert result.validation.balanced_accuracy == pytest.approx(1.0)
    assert result.validation.macro_f1 == pytest.approx(1.0)
    assert result.test.accuracy == pytest.approx(1.0)


def test_seed_reproduces_model_initialization() -> None:
    """The same seed should produce identical initial parameters."""
    set_reproducible_seed(123)
    first_model = LinearDirectionClassifier(input_features=2)
    first_state = {name: value.detach().clone() for name, value in first_model.state_dict().items()}

    set_reproducible_seed(123)
    second_model = LinearDirectionClassifier(input_features=2)

    for name, value in second_model.state_dict().items():
        torch.testing.assert_close(
            value,
            first_state[name],
        )


def test_rejects_invalid_training_configuration() -> None:
    """Invalid hyperparameters must fail before training starts."""
    with pytest.raises(
        ValueError,
        match="Maximum epochs",
    ):
        validate_config(TrainingConfig(max_epochs=0))

    with pytest.raises(
        ValueError,
        match="Patience",
    ):
        validate_config(TrainingConfig(patience=0))

    with pytest.raises(
        ValueError,
        match="Learning rate",
    ):
        validate_config(TrainingConfig(learning_rate=0.0))

    with pytest.raises(
        ValueError,
        match="Weight decay",
    ):
        validate_config(TrainingConfig(weight_decay=-0.1))

    with pytest.raises(
        ValueError,
        match="Class-weight power",
    ):
        validate_config(TrainingConfig(class_weight_power=1.1))

    with pytest.raises(
        ValueError,
        match="Device must be",
    ):
        validate_config(TrainingConfig(device="invalid"))


def test_softens_inverse_frequency_class_weights() -> None:
    """Weight power should interpolate between none and full balancing."""
    full_weights = np.asarray(
        [4.0, 1.0, 9.0],
        dtype=np.float32,
    )

    np.testing.assert_allclose(
        soften_class_weights(full_weights, 0.0),
        np.asarray([1.0, 1.0, 1.0]),
    )
    np.testing.assert_allclose(
        soften_class_weights(full_weights, 0.5),
        np.asarray([2.0, 1.0, 3.0]),
    )
    np.testing.assert_allclose(
        soften_class_weights(full_weights, 1.0),
        full_weights,
    )


def test_rejects_partition_feature_count_mismatch() -> None:
    """All partitions must contain the same model feature count."""
    train = make_separable_partition()
    validation = ModelPartition(
        features=np.zeros((3, 3), dtype=np.float64),
        targets=np.asarray([-1, 0, 1], dtype=np.int64),
    )
    test = make_separable_partition()

    with pytest.raises(
        ValueError,
        match="feature counts must match",
    ):
        train_linear_baseline(
            train,
            validation,
            test,
            TrainingConfig(device="cpu"),
        )


def test_rejects_equal_width_but_different_feature_schemas() -> None:
    """Column count alone cannot establish train/validation schema compatibility."""
    train = make_separable_partition()
    validation = make_separable_partition()
    test = make_separable_partition()
    train = ModelPartition(train.features, train.targets, ("first", "second"))
    validation = ModelPartition(validation.features, validation.targets, ("other", "second"))
    test = ModelPartition(test.features, test.targets, ("first", "second"))

    with pytest.raises(ValueError, match="feature schemas must match"):
        train_linear_baseline(
            train,
            validation,
            test,
            TrainingConfig(device="cpu"),
        )
