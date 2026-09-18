"""Tests for directional classification metrics."""

import pytest

from ai_trader.training.metrics import evaluate_classification


def test_calculates_multiclass_metrics() -> None:
    """Metrics should agree with a known confusion matrix."""
    report = evaluate_classification(
        actual=[-1, -1, 0, 0, 1, 1],
        predicted=[-1, 0, 0, 0, 1, -1],
    )

    assert report.total == 6
    assert report.correct == 4
    assert report.accuracy == pytest.approx(2 / 3)
    assert report.balanced_accuracy == pytest.approx(2 / 3)
    assert report.macro_f1 == pytest.approx((0.5 + 0.8 + (2 / 3)) / 3)
    assert report.confusion_matrix == (
        (1, 1, 0),
        (0, 2, 0),
        (1, 0, 1),
    )

    down, neutral, up = report.classes

    assert down.label == -1
    assert down.support == 2
    assert down.predicted == 2
    assert down.precision == pytest.approx(0.5)
    assert down.recall == pytest.approx(0.5)
    assert down.f1 == pytest.approx(0.5)

    assert neutral.label == 0
    assert neutral.support == 2
    assert neutral.predicted == 3
    assert neutral.precision == pytest.approx(2 / 3)
    assert neutral.recall == pytest.approx(1.0)
    assert neutral.f1 == pytest.approx(0.8)

    assert up.label == 1
    assert up.support == 2
    assert up.predicted == 1
    assert up.precision == pytest.approx(1.0)
    assert up.recall == pytest.approx(0.5)
    assert up.f1 == pytest.approx(2 / 3)


def test_reports_class_missing_from_actual_targets() -> None:
    """Absent classes must be visible rather than silently ignored."""
    report = evaluate_classification(
        actual=[0, 0, 1],
        predicted=[0, 0, 0],
    )

    assert report.missing_actual_classes == (-1,)
    assert report.classes[0].support == 0
    assert report.classes[0].recall == 0.0
    assert report.balanced_accuracy == pytest.approx(0.5)


def test_rejects_invalid_labels() -> None:
    """Only the three configured direction labels are supported."""
    with pytest.raises(
        ValueError,
        match="Actual labels",
    ):
        evaluate_classification(
            actual=[2],
            predicted=[0],
        )

    with pytest.raises(
        ValueError,
        match="Predicted labels",
    ):
        evaluate_classification(
            actual=[0],
            predicted=[2],
        )


def test_rejects_empty_or_misaligned_inputs() -> None:
    """Metric inputs must be nonempty and aligned."""
    with pytest.raises(
        ValueError,
        match="equal lengths",
    ):
        evaluate_classification(
            actual=[0, 1],
            predicted=[0],
        )

    with pytest.raises(
        ValueError,
        match="At least one prediction",
    ):
        evaluate_classification(
            actual=[],
            predicted=[],
        )
