"""Convert model probabilities into non-executable position intentions."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

Direction = Literal[-1, 0, 1]
PositionIntent = Literal["SHORT", "FLAT", "LONG"]

DIRECTION_CLASSES: tuple[Direction, ...] = (-1, 0, 1)


@dataclass(frozen=True, slots=True)
class DecisionPolicy:
    """Conservative thresholds for accepting directional predictions."""

    minimum_direction_probability: float = 0.55
    minimum_probability_margin: float = 0.10

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_direction_probability <= 1:
            raise ValueError("Minimum direction probability must be between zero and one.")
        if not 0 <= self.minimum_probability_margin <= 1:
            raise ValueError("Minimum probability margin must be between zero and one.")


@dataclass(frozen=True, slots=True)
class Decision:
    """One model-derived position intention."""

    predicted_direction: Direction
    intent: PositionIntent
    confidence: float
    probability_margin: float
    reason: str


def validate_probabilities(
    probabilities: Sequence[float],
) -> tuple[float, float, float]:
    """Validate DOWN, NEUTRAL, and UP probabilities."""
    if len(probabilities) != 3:
        raise ValueError("Exactly three class probabilities are required.")

    values = tuple(float(value) for value in probabilities)

    if any(not math.isfinite(value) for value in values):
        raise ValueError("Probabilities must be finite.")
    if any(value < 0 or value > 1 for value in values):
        raise ValueError("Probabilities must be between zero and one.")
    if not math.isclose(
        sum(values),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-5,
    ):
        raise ValueError("Probabilities must sum to one.")

    return values


def decide_position(
    probabilities: Sequence[float],
    policy: DecisionPolicy,
) -> Decision:
    """Convert probabilities into LONG, FLAT, or SHORT."""
    values = validate_probabilities(probabilities)
    confidence = max(values)
    winning_indices = [
        index
        for index, value in enumerate(values)
        if math.isclose(
            value,
            confidence,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    ]
    ordered_probabilities = sorted(values, reverse=True)
    probability_margin = ordered_probabilities[0] - ordered_probabilities[1]

    if len(winning_indices) != 1:
        return Decision(
            predicted_direction=0,
            intent="FLAT",
            confidence=confidence,
            probability_margin=probability_margin,
            reason="tied_highest_probability",
        )

    predicted_direction = DIRECTION_CLASSES[winning_indices[0]]

    if predicted_direction == 0:
        return Decision(
            predicted_direction=0,
            intent="FLAT",
            confidence=confidence,
            probability_margin=probability_margin,
            reason="neutral_is_most_likely",
        )

    if confidence < policy.minimum_direction_probability:
        return Decision(
            predicted_direction=predicted_direction,
            intent="FLAT",
            confidence=confidence,
            probability_margin=probability_margin,
            reason="direction_probability_below_threshold",
        )

    if probability_margin < policy.minimum_probability_margin:
        return Decision(
            predicted_direction=predicted_direction,
            intent="FLAT",
            confidence=confidence,
            probability_margin=probability_margin,
            reason="probability_margin_below_threshold",
        )

    intent: PositionIntent = "LONG" if predicted_direction == 1 else "SHORT"
    return Decision(
        predicted_direction=predicted_direction,
        intent=intent,
        confidence=confidence,
        probability_margin=probability_margin,
        reason="directional_signal_accepted",
    )
