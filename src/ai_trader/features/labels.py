"""Future-return labels for supervised market prediction."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

DirectionLabel = Literal[-1, 0, 1]
BASIS_POINTS_PER_UNIT = Decimal("10000")


@dataclass(frozen=True, slots=True)
class FutureReturnLabel:
    """A future midpoint outcome associated with one feature row."""

    future_index: int
    future_event_time_ms: int
    actual_horizon_ms: int
    future_midpoint: Decimal
    return_bps: Decimal
    direction: DirectionLabel


def classify_return(
    return_bps: Decimal,
    *,
    neutral_threshold_bps: Decimal,
) -> DirectionLabel:
    """Convert a future return into down, neutral, or up."""
    if neutral_threshold_bps < 0:
        raise ValueError("Neutral threshold cannot be negative.")

    if return_bps > neutral_threshold_bps:
        return 1
    if return_bps < -neutral_threshold_bps:
        return -1
    return 0


def calculate_future_return_labels(
    event_times_ms: list[int],
    midpoints: list[Decimal],
    *,
    horizon_ms: int,
    neutral_threshold_bps: Decimal,
) -> tuple[FutureReturnLabel | None, ...]:
    """Calculate time-based labels using the first row at or beyond a horizon.

    A None result means the dataset ended before that observation had enough
    future data to calculate its label.
    """
    if horizon_ms <= 0:
        raise ValueError("Label horizon must be greater than zero.")
    if neutral_threshold_bps < 0:
        raise ValueError("Neutral threshold cannot be negative.")
    if len(event_times_ms) != len(midpoints):
        raise ValueError("Event times and midpoints must have equal lengths.")
    if any(midpoint <= 0 for midpoint in midpoints):
        raise ValueError("All midpoint values must be positive.")
    if any(
        current_time > next_time
        for current_time, next_time in zip(
            event_times_ms,
            event_times_ms[1:],
            strict=False,
        )
    ):
        raise ValueError("Event times must be nondecreasing.")

    labels: list[FutureReturnLabel | None] = []
    future_index = 0

    for current_index, current_time_ms in enumerate(event_times_ms):
        target_time_ms = current_time_ms + horizon_ms
        future_index = max(future_index, current_index + 1)

        while future_index < len(event_times_ms) and event_times_ms[future_index] < target_time_ms:
            future_index += 1

        if future_index >= len(event_times_ms):
            labels.extend([None] * (len(event_times_ms) - current_index))
            break

        current_midpoint = midpoints[current_index]
        future_midpoint = midpoints[future_index]
        return_bps = (future_midpoint / current_midpoint - Decimal("1")) * BASIS_POINTS_PER_UNIT

        labels.append(
            FutureReturnLabel(
                future_index=future_index,
                future_event_time_ms=event_times_ms[future_index],
                actual_horizon_ms=(event_times_ms[future_index] - current_time_ms),
                future_midpoint=future_midpoint,
                return_bps=return_bps,
                direction=classify_return(
                    return_bps,
                    neutral_threshold_bps=neutral_threshold_bps,
                ),
            )
        )

    return tuple(labels)
