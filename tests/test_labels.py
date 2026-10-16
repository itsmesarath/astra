"""Tests for future-return label generation."""

from decimal import Decimal

import pytest

from ai_trader.features.labels import (
    calculate_future_return_labels,
    classify_return,
)


def test_uses_first_observation_at_or_beyond_time_horizon() -> None:
    """Labels must use elapsed time rather than a fixed row offset."""
    event_times_ms = [0, 400, 1000, 1500, 2100]
    midpoints = [
        Decimal("100"),
        Decimal("101"),
        Decimal("102"),
        Decimal("101"),
        Decimal("100"),
    ]

    labels = calculate_future_return_labels(
        event_times_ms,
        midpoints,
        horizon_ms=1000,
        neutral_threshold_bps=Decimal("50"),
    )

    first = labels[0]
    assert first is not None
    assert first.future_index == 2
    assert first.future_event_time_ms == 1000
    assert first.actual_horizon_ms == 1000
    assert first.future_midpoint == Decimal("102")
    assert first.return_bps == Decimal("200")
    assert first.direction == 1

    second = labels[1]
    assert second is not None
    assert second.future_index == 3
    assert second.actual_horizon_ms == 1100
    assert second.future_midpoint == Decimal("101")
    assert second.return_bps == Decimal("0")
    assert second.direction == 0

    third = labels[2]
    assert third is not None
    assert third.future_index == 4
    assert third.actual_horizon_ms == 1100
    assert third.return_bps == (Decimal("100") / Decimal("102") - Decimal("1")) * Decimal("10000")
    assert third.direction == -1

    assert labels[3] is None
    assert labels[4] is None


def test_return_equal_to_threshold_is_neutral() -> None:
    """The neutral band includes its positive and negative boundaries."""
    assert (
        classify_return(
            Decimal("10"),
            neutral_threshold_bps=Decimal("10"),
        )
        == 0
    )
    assert (
        classify_return(
            Decimal("-10"),
            neutral_threshold_bps=Decimal("10"),
        )
        == 0
    )


def test_accepts_repeated_event_timestamps() -> None:
    """Multiple updates may legitimately share one millisecond timestamp."""
    labels = calculate_future_return_labels(
        [1000, 1000, 1100],
        [
            Decimal("100"),
            Decimal("100.5"),
            Decimal("101"),
        ],
        horizon_ms=100,
        neutral_threshold_bps=Decimal("0"),
    )

    first = labels[0]
    second = labels[1]

    assert first is not None
    assert second is not None
    assert first.future_index == 2
    assert second.future_index == 2
    assert labels[2] is None


def test_rejects_decreasing_event_times() -> None:
    """Chronologically reversed observations must be rejected."""
    with pytest.raises(
        ValueError,
        match="Event times must be nondecreasing",
    ):
        calculate_future_return_labels(
            [1000, 999],
            [Decimal("100"), Decimal("101")],
            horizon_ms=100,
            neutral_threshold_bps=Decimal("0"),
        )


def test_rejects_invalid_configuration() -> None:
    """Invalid horizons and thresholds must fail clearly."""
    with pytest.raises(
        ValueError,
        match="Label horizon must be greater than zero",
    ):
        calculate_future_return_labels(
            [1000],
            [Decimal("100")],
            horizon_ms=0,
            neutral_threshold_bps=Decimal("0"),
        )

    with pytest.raises(
        ValueError,
        match="Neutral threshold cannot be negative",
    ):
        calculate_future_return_labels(
            [1000],
            [Decimal("100")],
            horizon_ms=100,
            neutral_threshold_bps=Decimal("-1"),
        )


def test_rejects_invalid_input_columns() -> None:
    """Time and midpoint columns must be aligned and valid."""
    with pytest.raises(
        ValueError,
        match="equal lengths",
    ):
        calculate_future_return_labels(
            [1000, 1100],
            [Decimal("100")],
            horizon_ms=100,
            neutral_threshold_bps=Decimal("0"),
        )

    with pytest.raises(
        ValueError,
        match="midpoint values must be positive",
    ):
        calculate_future_return_labels(
            [1000],
            [Decimal("0")],
            horizon_ms=100,
            neutral_threshold_bps=Decimal("0"),
        )
