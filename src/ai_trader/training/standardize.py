"""Train-only feature standardization."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class Standardizer:
    """Column means and scales fitted only on training data."""

    means: np.ndarray
    scales: np.ndarray

    @property
    def columns(self) -> int:
        """Return the number of standardized features."""
        return self.means.shape[0]

    def transform(self, features: np.ndarray) -> np.ndarray:
        """Apply stored training statistics to a feature matrix."""
        matrix = validate_feature_matrix(features)

        if matrix.shape[1] != self.columns:
            raise ValueError(
                f"Expected {self.columns} feature columns, received {matrix.shape[1]}."
            )

        transformed = (matrix - self.means) / self.scales

        if not np.isfinite(transformed).all():
            raise ValueError("Standardization produced non-finite values.")

        return transformed


def validate_feature_matrix(features: np.ndarray) -> np.ndarray:
    """Return a finite two-dimensional float64 feature matrix."""
    matrix = np.asarray(features, dtype=np.float64)

    if matrix.ndim != 2:
        raise ValueError("Features must be a two-dimensional matrix.")
    if matrix.shape[0] == 0:
        raise ValueError("Feature matrix must contain at least one row.")
    if matrix.shape[1] == 0:
        raise ValueError("Feature matrix must contain at least one column.")
    if not np.isfinite(matrix).all():
        raise ValueError("Feature matrix must contain finite values.")

    return matrix


def fit_standardizer(features: np.ndarray) -> Standardizer:
    """Fit column statistics using training features only."""
    matrix = validate_feature_matrix(features)

    means = matrix.mean(axis=0)
    standard_deviations = matrix.std(axis=0)
    scales = np.where(
        standard_deviations == 0,
        1.0,
        standard_deviations,
    )

    return Standardizer(
        means=means.astype(np.float64, copy=False),
        scales=scales.astype(np.float64, copy=False),
    )
