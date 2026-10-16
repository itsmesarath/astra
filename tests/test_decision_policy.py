"""Tests for model probability decision policy."""

import pytest

from ai_trader.trading.decision_policy import (
    DecisionPolicy,
    decide_position,
    validate_probabilities,
)


def test_accepts_confident_directional_predictions() -> None:
    """Strong directional probabilities should create intentions."""
    policy = DecisionPolicy(
        minimum_direction_probability=0.55,
        minimum_probability_margin=0.10,
    )

    long_decision = decide_position(
        [0.10, 0.20, 0.70],
        policy,
    )
    short_decision = decide_position(
        [0.65, 0.25, 0.10],
        policy,
    )

    assert long_decision.predicted_direction == 1
    assert long_decision.intent == "LONG"
    assert long_decision.reason == "directional_signal_accepted"
    assert long_decision.confidence == pytest.approx(0.70)
    assert long_decision.probability_margin == pytest.approx(0.50)

    assert short_decision.predicted_direction == -1
    assert short_decision.intent == "SHORT"
    assert short_decision.reason == "directional_signal_accepted"


def test_neutral_prediction_remains_flat() -> None:
    """A dominant neutral probability should not create exposure."""
    decision = decide_position(
        [0.10, 0.80, 0.10],
        DecisionPolicy(),
    )

    assert decision.predicted_direction == 0
    assert decision.intent == "FLAT"
    assert decision.reason == "neutral_is_most_likely"


def test_rejects_weak_directional_predictions() -> None:
    """Confidence and margin thresholds should independently apply."""
    policy = DecisionPolicy(
        minimum_direction_probability=0.60,
        minimum_probability_margin=0.15,
    )

    low_confidence = decide_position(
        [0.30, 0.20, 0.50],
        policy,
    )
    low_margin = decide_position(
        [0.10, 0.34, 0.56],
        policy,
    )

    assert low_confidence.intent == "FLAT"
    assert low_confidence.reason == ("direction_probability_below_threshold")

    assert low_margin.intent == "FLAT"
    assert low_margin.reason == ("direction_probability_below_threshold")

    margin_only_policy = DecisionPolicy(
        minimum_direction_probability=0.50,
        minimum_probability_margin=0.25,
    )
    margin_rejection = decide_position(
        [0.10, 0.34, 0.56],
        margin_only_policy,
    )

    assert margin_rejection.intent == "FLAT"
    assert margin_rejection.reason == ("probability_margin_below_threshold")


def test_tied_prediction_remains_flat() -> None:
    """A class tie must never be resolved into market exposure."""
    decision = decide_position(
        [0.45, 0.10, 0.45],
        DecisionPolicy(
            minimum_direction_probability=0.40,
            minimum_probability_margin=0.0,
        ),
    )

    assert decision.predicted_direction == 0
    assert decision.intent == "FLAT"
    assert decision.reason == "tied_highest_probability"


def test_rejects_invalid_probabilities_and_policy() -> None:
    """Probability vectors and thresholds must be valid."""
    with pytest.raises(
        ValueError,
        match="Exactly three",
    ):
        validate_probabilities([0.5, 0.5])

    with pytest.raises(
        ValueError,
        match="between zero and one",
    ):
        validate_probabilities([-0.1, 0.5, 0.6])

    with pytest.raises(
        ValueError,
        match="sum to one",
    ):
        validate_probabilities([0.2, 0.2, 0.2])

    with pytest.raises(
        ValueError,
        match="Minimum direction probability",
    ):
        DecisionPolicy(minimum_direction_probability=1.1)

    with pytest.raises(
        ValueError,
        match="Minimum probability margin",
    ):
        DecisionPolicy(minimum_probability_margin=-0.1)

    with pytest.raises(TypeError, match="allow_short"):
        DecisionPolicy(allow_short=1)  # type: ignore[arg-type]


def test_spot_policy_converts_short_signal_to_flat() -> None:
    """Spot mode must never turn a bearish prediction into short exposure."""
    decision = decide_position(
        [0.80, 0.10, 0.10],
        DecisionPolicy(allow_short=False),
    )

    assert decision.predicted_direction == -1
    assert decision.intent == "FLAT"
    assert decision.reason == "short_not_allowed"
