"""Leakage-resistant chronological dataset splitting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndexRange:
    """A half-open range of chronological row indices."""

    start: int
    stop: int

    @property
    def size(self) -> int:
        """Return the number of rows in the range."""
        return self.stop - self.start


@dataclass(frozen=True, slots=True)
class PurgedTimeSplit:
    """Chronological train, validation, and test ranges."""

    train: IndexRange
    purged_after_train: IndexRange
    validation: IndexRange
    purged_after_validation: IndexRange
    test: IndexRange

    @property
    def purged_rows(self) -> int:
        """Return the total number of boundary rows removed."""
        return self.purged_after_train.size + self.purged_after_validation.size


def _is_nondecreasing(values: list[int]) -> bool:
    """Return whether values remain in chronological order."""
    return all(
        current <= following
        for current, following in zip(
            values,
            values[1:],
            strict=False,
        )
    )


def _validate_split_inputs(
    event_times_ms: list[int],
    future_event_times_ms: list[int],
    *,
    train_fraction: float,
    validation_fraction: float,
) -> None:
    """Validate inputs shared by row- and session-boundary splits."""
    if len(event_times_ms) != len(future_event_times_ms):
        raise ValueError("Event times and future event times must have equal lengths.")
    if len(event_times_ms) < 3:
        raise ValueError("At least three labeled rows are required.")
    if not 0 < train_fraction < 1:
        raise ValueError("Train fraction must be between zero and one.")
    if not 0 < validation_fraction < 1:
        raise ValueError("Validation fraction must be between zero and one.")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("Train and validation fractions must leave a test section.")
    if not _is_nondecreasing(event_times_ms):
        raise ValueError("Event times must be nondecreasing.")
    if not _is_nondecreasing(future_event_times_ms):
        raise ValueError("Future event times must be nondecreasing.")
    if any(
        future_time < event_time
        for event_time, future_time in zip(
            event_times_ms,
            future_event_times_ms,
            strict=True,
        )
    ):
        raise ValueError("A future event time cannot precede its feature time.")


def _create_split_at_boundaries(
    event_times_ms: list[int],
    future_event_times_ms: list[int],
    *,
    validation_start: int,
    test_start: int,
) -> PurgedTimeSplit:
    """Create and validate a purged split at two chosen row boundaries."""
    row_count = len(event_times_ms)

    if validation_start <= 0:
        raise ValueError("Training section would be empty.")
    if test_start <= validation_start:
        raise ValueError("Validation section would be empty.")
    if test_start >= row_count:
        raise ValueError("Test section would be empty.")

    validation_boundary_ms = event_times_ms[validation_start]
    test_boundary_ms = event_times_ms[test_start]

    train_stop = validation_start
    while train_stop > 0 and future_event_times_ms[train_stop - 1] >= validation_boundary_ms:
        train_stop -= 1

    validation_stop = test_start
    while (
        validation_stop > validation_start
        and future_event_times_ms[validation_stop - 1] >= test_boundary_ms
    ):
        validation_stop -= 1

    split = PurgedTimeSplit(
        train=IndexRange(0, train_stop),
        purged_after_train=IndexRange(
            train_stop,
            validation_start,
        ),
        validation=IndexRange(
            validation_start,
            validation_stop,
        ),
        purged_after_validation=IndexRange(
            validation_stop,
            test_start,
        ),
        test=IndexRange(test_start, row_count),
    )

    if split.train.size == 0:
        raise ValueError("Purging removed every training row.")
    if split.validation.size == 0:
        raise ValueError("Purging removed every validation row.")
    if split.test.size == 0:
        raise ValueError("Test section is empty.")

    return split


def _session_start_indices(source_sessions: list[str]) -> list[int]:
    """Return starts of validated, contiguous source-session groups."""
    if not source_sessions:
        raise ValueError("At least one source session is required.")
    if any(not session.strip() for session in source_sessions):
        raise ValueError("Source sessions must be nonempty.")

    starts = [0]
    completed_sessions: set[str] = set()
    current_session = source_sessions[0]

    for index, session in enumerate(source_sessions[1:], start=1):
        if session == current_session:
            continue

        completed_sessions.add(current_session)
        if session in completed_sessions:
            raise ValueError("Each source session must occupy one contiguous row range.")

        starts.append(index)
        current_session = session

    return starts


def create_purged_session_split(
    event_times_ms: list[int],
    future_event_times_ms: list[int],
    source_sessions: list[str],
    *,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
) -> PurgedTimeSplit:
    """Create a chronological split whose boundaries never divide a session.

    The pair of session boundaries closest to the requested cumulative row
    fractions is selected. Label outcomes crossing either selected boundary
    are still purged from the earlier partition.
    """
    _validate_split_inputs(
        event_times_ms,
        future_event_times_ms,
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
    )
    if len(source_sessions) != len(event_times_ms):
        raise ValueError("Source sessions and event times must have equal lengths.")

    session_starts = _session_start_indices(source_sessions)
    if len(session_starts) < 3:
        raise ValueError("At least three source sessions are required for a session split.")

    row_count = len(event_times_ms)
    target_validation_start = row_count * train_fraction
    target_test_start = row_count * (train_fraction + validation_fraction)
    boundary_pairs = (
        (validation_start, test_start)
        for validation_position, validation_start in enumerate(session_starts[1:-1], start=1)
        for test_start in session_starts[validation_position + 1 :]
    )
    validation_start, test_start = min(
        boundary_pairs,
        key=lambda pair: (
            abs(pair[0] - target_validation_start) + abs(pair[1] - target_test_start),
            abs(pair[0] - target_validation_start),
            pair,
        ),
    )

    return _create_split_at_boundaries(
        event_times_ms,
        future_event_times_ms,
        validation_start=validation_start,
        test_start=test_start,
    )


def create_purged_time_split(
    event_times_ms: list[int],
    future_event_times_ms: list[int],
    *,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
) -> PurgedTimeSplit:
    """Create chronological ranges and purge overlapping label outcomes.

    Rows are initially divided chronologically. Rows at the end of the
    training and validation sections are then removed when their future
    outcomes reach into the next section.
    """
    _validate_split_inputs(
        event_times_ms,
        future_event_times_ms,
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
    )

    row_count = len(event_times_ms)
    validation_start = int(row_count * train_fraction)
    test_start = int(row_count * (train_fraction + validation_fraction))

    return _create_split_at_boundaries(
        event_times_ms,
        future_event_times_ms,
        validation_start=validation_start,
        test_start=test_start,
    )
