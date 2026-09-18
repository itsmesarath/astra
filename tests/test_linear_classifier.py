"""Tests for the linear direction classifier."""

import numpy as np
import pytest
import torch

from ai_trader.models.linear_classifier import (
    LinearDirectionClassifier,
    calculate_class_weights,
    decode_directions,
    encode_directions,
)


def test_encodes_and_decodes_direction_classes() -> None:
    """Direction labels should round-trip through class indices."""
    directions = np.asarray([-1, 0, 1, 1, -1])

    encoded = encode_directions(directions)
    decoded = decode_directions(encoded)

    np.testing.assert_array_equal(
        encoded,
        np.asarray([0, 1, 2, 2, 0]),
    )
    np.testing.assert_array_equal(decoded, directions)


def test_calculates_inverse_frequency_class_weights() -> None:
    """Less frequent training classes should receive more weight."""
    targets = np.asarray([-1, -1, 0, 0, 0, 0, 1, 1])

    weights = calculate_class_weights(targets)

    np.testing.assert_allclose(
        weights,
        np.asarray(
            [
                8 / (3 * 2),
                8 / (3 * 4),
                8 / (3 * 2),
            ],
            dtype=np.float32,
        ),
    )


def test_linear_model_returns_three_scores_per_row() -> None:
    """The model should produce one score for each direction class."""
    model = LinearDirectionClassifier(input_features=9)
    features = torch.zeros((4, 9), dtype=torch.float32)

    logits = model(features)

    assert logits.shape == (4, 3)
    assert logits.requires_grad

    logits.sum().backward()
    assert model.linear.weight.grad is not None


def test_rejects_invalid_targets_and_model_shapes() -> None:
    """Invalid labels, absent classes, and shapes must fail clearly."""
    with pytest.raises(
        ValueError,
        match="must be -1, 0, or 1",
    ):
        encode_directions(np.asarray([-1, 2]))

    with pytest.raises(
        ValueError,
        match="must contain every direction class",
    ):
        calculate_class_weights(np.asarray([-1, 0, 0]))

    model = LinearDirectionClassifier(input_features=9)

    with pytest.raises(
        ValueError,
        match="two-dimensional",
    ):
        model(torch.zeros(9))

    with pytest.raises(
        ValueError,
        match="Expected 9 input features",
    ):
        model(torch.zeros((2, 8)))
