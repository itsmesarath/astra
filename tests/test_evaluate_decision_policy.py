"""Tests for offline decision-policy evaluation."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from ai_trader.trading.decision_policy import DecisionPolicy
from ai_trader.trading.evaluate_decision_policy import (
    evaluate_prediction_file,
)


def write_predictions(
    path: Path,
    rows: list[dict[str, str]],
) -> None:
    """Write historical probability and target rows."""
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=list(rows[0]),
        )
        writer.writeheader()
        writer.writerows(rows)


def test_evaluates_policy_coverage_and_precision(
    tmp_path: Path,
) -> None:
    """Accepted signals and rejection reasons should be counted."""
    path = tmp_path / "predictions.csv"
    write_predictions(
        path,
        [
            {
                "probability_down": "0.70",
                "probability_neutral": "0.20",
                "probability_up": "0.10",
                "actual_direction": "-1",
            },
            {
                "probability_down": "0.10",
                "probability_neutral": "0.20",
                "probability_up": "0.70",
                "actual_direction": "1",
            },
            {
                "probability_down": "0.10",
                "probability_neutral": "0.80",
                "probability_up": "0.10",
                "actual_direction": "0",
            },
            {
                "probability_down": "0.30",
                "probability_neutral": "0.20",
                "probability_up": "0.50",
                "actual_direction": "1",
            },
            {
                "probability_down": "0.10",
                "probability_neutral": "0.34",
                "probability_up": "0.56",
                "actual_direction": "0",
            },
        ],
    )

    report = evaluate_prediction_file(
        path,
        DecisionPolicy(
            minimum_direction_probability=0.55,
            minimum_probability_margin=0.25,
        ),
    )

    assert report.rows == 5
    assert report.short_signals == 1
    assert report.long_signals == 1
    assert report.flat_decisions == 3
    assert report.directional_signals == 2
    assert report.coverage == pytest.approx(0.4)
    assert report.directional_precision == pytest.approx(1.0)
    assert report.short_precision == pytest.approx(1.0)
    assert report.long_precision == pytest.approx(1.0)
    assert report.short_outcomes == (1, 0, 0)
    assert report.long_outcomes == (0, 0, 1)
    assert report.reason_counts == {
        "directional_signal_accepted": 2,
        "neutral_is_most_likely": 1,
        "direction_probability_below_threshold": 1,
        "probability_margin_below_threshold": 1,
    }


def test_rejects_missing_required_columns(tmp_path: Path) -> None:
    """Historical evaluation requires actual target directions."""
    path = tmp_path / "missing.csv"
    write_predictions(
        path,
        [
            {
                "probability_down": "0.2",
                "probability_neutral": "0.6",
                "probability_up": "0.2",
            }
        ],
    )

    with pytest.raises(
        ValueError,
        match="missing columns",
    ):
        evaluate_prediction_file(
            path,
            DecisionPolicy(),
        )


def test_rejects_invalid_actual_direction(tmp_path: Path) -> None:
    """Only DOWN, NEUTRAL, and UP targets are valid."""
    path = tmp_path / "invalid.csv"
    write_predictions(
        path,
        [
            {
                "probability_down": "0.2",
                "probability_neutral": "0.6",
                "probability_up": "0.2",
                "actual_direction": "2",
            }
        ],
    )

    with pytest.raises(
        ValueError,
        match="invalid actual direction",
    ):
        evaluate_prediction_file(
            path,
            DecisionPolicy(),
        )
