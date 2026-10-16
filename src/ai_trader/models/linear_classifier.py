"""Three-class linear direction classifier."""

from __future__ import annotations

import numpy as np
import torch
from torch import nn

DIRECTION_CLASSES = (-1, 0, 1)
DIRECTION_TO_INDEX = {direction: index for index, direction in enumerate(DIRECTION_CLASSES)}


class LinearDirectionClassifier(nn.Module):
    """A multinomial linear classifier for market direction."""

    def __init__(
        self,
        input_features: int,
    ) -> None:
        super().__init__()

        if input_features <= 0:
            raise ValueError("Input feature count must be greater than zero.")

        self.input_features = input_features
        self.output_classes = len(DIRECTION_CLASSES)
        self.linear = nn.Linear(
            input_features,
            self.output_classes,
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """Return unnormalized class scores."""
        if features.ndim != 2:
            raise ValueError("Model input must be a two-dimensional tensor.")
        if features.shape[1] != self.input_features:
            raise ValueError(
                f"Expected {self.input_features} input features, received {features.shape[1]}."
            )

        return self.linear(features)


def encode_directions(targets: np.ndarray) -> np.ndarray:
    """Map direction labels -1, 0, and 1 to class indices."""
    values = np.asarray(targets)

    if values.ndim != 1:
        raise ValueError("Direction targets must be one-dimensional.")
    if values.size == 0:
        raise ValueError("At least one direction target is required.")
    if not np.isin(values, DIRECTION_CLASSES).all():
        raise ValueError("Direction targets must be -1, 0, or 1.")

    return np.asarray(
        [DIRECTION_TO_INDEX[int(value)] for value in values],
        dtype=np.int64,
    )


def decode_directions(class_indices: np.ndarray) -> np.ndarray:
    """Map class indices back to direction labels."""
    indices = np.asarray(class_indices)

    if indices.ndim != 1:
        raise ValueError("Class indices must be one-dimensional.")
    if indices.size == 0:
        raise ValueError("At least one class index is required.")
    if not np.isin(
        indices,
        range(len(DIRECTION_CLASSES)),
    ).all():
        raise ValueError("Class index must be 0, 1, or 2.")

    return np.asarray(
        [DIRECTION_CLASSES[int(index)] for index in indices],
        dtype=np.int64,
    )


def calculate_class_weights(targets: np.ndarray) -> np.ndarray:
    """Calculate inverse-frequency weights from training targets."""
    encoded = encode_directions(targets)
    counts = np.bincount(
        encoded,
        minlength=len(DIRECTION_CLASSES),
    )

    if np.any(counts == 0):
        raise ValueError("Training data must contain every direction class.")

    weights = encoded.size / (len(DIRECTION_CLASSES) * counts)
    return weights.astype(np.float32)
