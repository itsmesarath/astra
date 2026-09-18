"""Tests for leakage-resistant chronological splitting."""

import pytest

from ai_trader.training.time_split import create_purged_time_split


def test_creates_chronological_split_and_purges_overlap() -> None:
    """Labels crossing section boundaries must be removed."""
    event_times_ms = [index * 100 for index in range(20)]
    future_event_times_ms = [(index + 2) * 100 for index in range(20)]

    split = create_purged_time_split(
        event_times_ms,
        future_event_times_ms,
        train_fraction=0.60,
        validation_fraction=0.20,
    )

    assert (split.train.start, split.train.stop) == (0, 10)
    assert (
        split.purged_after_train.start,
        split.purged_after_train.stop,
    ) == (10, 12)
    assert (
        split.validation.start,
        split.validation.stop,
    ) == (12, 14)
    assert (
        split.purged_after_validation.start,
        split.purged_after_validation.stop,
    ) == (14, 16)
    assert (split.test.start, split.test.stop) == (16, 20)
    assert split.purged_rows == 4


def test_training_and_validation_labels_do_not_cross_boundaries() -> None:
    """Retained outcomes must finish before the following section."""
    event_times_ms = [index * 100 for index in range(20)]
    future_event_times_ms = [(index + 2) * 100 for index in range(20)]

    split = create_purged_time_split(
        event_times_ms,
        future_event_times_ms,
        train_fraction=0.60,
        validation_fraction=0.20,
    )

    validation_start_time = event_times_ms[split.validation.start]
    test_start_time = event_times_ms[split.test.start]

    assert all(
        future_event_times_ms[index] < validation_start_time
        for index in range(split.train.start, split.train.stop)
    )
    assert all(
        future_event_times_ms[index] < test_start_time
        for index in range(
            split.validation.start,
            split.validation.stop,
        )
    )


@pytest.mark.parametrize(
    ("train_fraction", "validation_fraction"),
    [
        (0.0, 0.20),
        (1.0, 0.20),
        (0.70, 0.0),
        (0.70, 1.0),
        (0.80, 0.20),
    ],
)
def test_rejects_invalid_split_fractions(
    train_fraction: float,
    validation_fraction: float,
) -> None:
    """Fractions must create three nonempty chronological sections."""
    with pytest.raises(ValueError):
        create_purged_time_split(
            [0, 100, 200],
            [100, 200, 300],
            train_fraction=train_fraction,
            validation_fraction=validation_fraction,
        )


def test_rejects_reversed_timestamps() -> None:
    """Both feature and future timestamps must be chronological."""
    with pytest.raises(
        ValueError,
        match="Event times must be nondecreasing",
    ):
        create_purged_time_split(
            [0, 200, 100],
            [100, 300, 400],
        )

    with pytest.raises(
        ValueError,
        match="Future event times must be nondecreasing",
    ):
        create_purged_time_split(
            [0, 100, 200],
            [200, 150, 300],
        )


def test_rejects_split_when_purge_removes_training_section() -> None:
    """An excessively long horizon must fail instead of leaking."""
    with pytest.raises(
        ValueError,
        match="Purging removed every training row",
    ):
        create_purged_time_split(
            [index * 100 for index in range(10)],
            [(index + 10) * 100 for index in range(10)],
            train_fraction=0.60,
            validation_fraction=0.20,
        )
