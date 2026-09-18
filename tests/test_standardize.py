"""Tests for train-only feature standardization."""

import numpy as np
import pytest

from ai_trader.training.standardize import fit_standardizer


def test_standardizes_training_columns() -> None:
    """Transformed training columns should have zero mean and unit scale."""
    training_features = np.asarray(
        [
            [1.0, 10.0],
            [2.0, 20.0],
            [3.0, 30.0],
        ]
    )

    standardizer = fit_standardizer(training_features)
    transformed = standardizer.transform(training_features)

    np.testing.assert_allclose(
        transformed.mean(axis=0),
        np.asarray([0.0, 0.0]),
        atol=1e-12,
    )
    np.testing.assert_allclose(
        transformed.std(axis=0),
        np.asarray([1.0, 1.0]),
        atol=1e-12,
    )


def test_validation_data_does_not_affect_fitted_statistics() -> None:
    """Future partition values must not influence training statistics."""
    training_features = np.asarray(
        [
            [0.0],
            [2.0],
        ]
    )
    validation_features = np.asarray([[100.0]])

    standardizer = fit_standardizer(training_features)
    transformed_validation = standardizer.transform(validation_features)

    np.testing.assert_allclose(
        standardizer.means,
        np.asarray([1.0]),
    )
    np.testing.assert_allclose(
        standardizer.scales,
        np.asarray([1.0]),
    )
    np.testing.assert_allclose(
        transformed_validation,
        np.asarray([[99.0]]),
    )


def test_constant_training_column_remains_finite() -> None:
    """A zero-variance column should use a safe scale of one."""
    training_features = np.asarray(
        [
            [5.0, 1.0],
            [5.0, 2.0],
            [5.0, 3.0],
        ]
    )

    standardizer = fit_standardizer(training_features)
    transformed = standardizer.transform(training_features)

    assert standardizer.scales[0] == pytest.approx(1.0)
    np.testing.assert_allclose(
        transformed[:, 0],
        np.asarray([0.0, 0.0, 0.0]),
    )
    assert np.isfinite(transformed).all()


def test_rejects_invalid_feature_matrices() -> None:
    """Matrices must be nonempty, two-dimensional, and finite."""
    with pytest.raises(
        ValueError,
        match="two-dimensional",
    ):
        fit_standardizer(np.asarray([1.0, 2.0]))

    with pytest.raises(
        ValueError,
        match="at least one row",
    ):
        fit_standardizer(np.empty((0, 2)))

    with pytest.raises(
        ValueError,
        match="finite values",
    ):
        fit_standardizer(
            np.asarray(
                [
                    [1.0, np.nan],
                    [2.0, 3.0],
                ]
            )
        )


def test_rejects_wrong_transform_column_count() -> None:
    """Transform input must match the fitted feature count."""
    standardizer = fit_standardizer(
        np.asarray(
            [
                [1.0, 2.0],
                [3.0, 4.0],
            ]
        )
    )

    with pytest.raises(
        ValueError,
        match="Expected 2 feature columns",
    ):
        standardizer.transform(
            np.asarray(
                [
                    [1.0, 2.0, 3.0],
                ]
            )
        )
