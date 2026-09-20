"""Point-in-time session inventory, boundary and holdout-conversion regressions."""

import csv
from pathlib import Path

import pytest

from ai_trader.features.kline_dataset import KLINE_FEATURE_COLUMNS
from ai_trader.training import session_data
from ai_trader.training.session_data import load_session_dataset


def rows(economic=True):
    result = []
    for day in range(4):
        for index in range(3):
            event = day * 1000 + index * 10
            row = dict.fromkeys(KLINE_FEATURE_COLUMNS, "0.5")
            row.update(
                source_session=f"session-{day}",
                depth_event_time_ms=str(event),
                future_event_time_ms=str(event + 8),
                target_direction=str(index - 1),
            )
            if economic:
                row.update(entry_time_ms=str(event + 1), net_return_bps="12")
            result.append(row)
    return result


def write(path: Path, values):
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def test_reserved_outcomes_and_features_are_not_converted(tmp_path, monkeypatch):
    source = tmp_path / "sessions.csv"
    values = rows()
    for row in values[6:]:
        for name in (
            *KLINE_FEATURE_COLUMNS,
            "target_direction",
            "future_event_time_ms",
            "entry_time_ms",
            "net_return_bps",
        ):
            row[name] = "MUST-NOT-BE-CONVERTED"
    write(source, values)
    original = session_data.row_to_schema_features
    loaded = []

    def guarded_conversion(row, feature_names):
        assert row["source_session"] not in ("session-2", "session-3")
        loaded.append(row["source_session"])
        return original(row, feature_names)

    monkeypatch.setattr(session_data, "row_to_schema_features", guarded_conversion)
    dataset = load_session_dataset(source, held_out_session_count=2)
    assert len(loaded) == 6
    assert dataset.held_out_sessions == ("session-2", "session-3")
    assert tuple(session.name for session in dataset.sessions) == ("session-0", "session-1")
    assert dataset.metadata[-1].rows == 3
    assert "MUST-NOT-BE-CONVERTED" not in repr(dataset)


@pytest.mark.parametrize("boundary_row", [0, 5, 8])
def test_any_crossing_outcome_is_rejected_even_before_holdout(tmp_path, boundary_row):
    source = tmp_path / "sessions.csv"
    values = rows()
    next_start = (boundary_row // 3 + 1) * 1000
    values[boundary_row]["future_event_time_ms"] = str(next_start)
    write(source, values)
    with pytest.raises(ValueError, match="crosses the next session boundary"):
        load_session_dataset(source, held_out_session_count=1)


def test_nonmonotonic_exit_times_are_valid(tmp_path):
    source = tmp_path / "sessions.csv"
    values = rows()
    values[0]["future_event_time_ms"] = "500"  # first entry lasts longer than later entries
    write(source, values)
    dataset = load_session_dataset(source, held_out_session_count=1)
    assert [outcome.exit_time_ms for outcome in dataset.sessions[0].outcomes] == [500, 18, 28]


def test_embargo_uses_longest_outcome_not_last_row(tmp_path):
    source = tmp_path / "sessions.csv"
    values = rows()
    values[0]["future_event_time_ms"] = "900"
    write(source, values)
    assert load_session_dataset(source, held_out_session_count=1, embargo_ms=99)
    with pytest.raises(ValueError, match="embargo crosses"):
        load_session_dataset(source, held_out_session_count=1, embargo_ms=100)


@pytest.mark.parametrize(
    "column,value,message",
    [
        ("depth_event_time_ms", "9", "not chronological"),
        ("depth_event_time_ms", "-1", "nonnegative integer"),
        ("future_event_time_ms", "20", "after its feature"),
        ("future_event_time_ms", "19", "after its feature"),
        ("entry_time_ms", "20", "Entry must be after"),
        ("entry_time_ms", "29", "invalid time interval"),
        ("future_event_time_ms", "NaN", "nonnegative integer"),
    ],
)
def test_invalid_times_rejected(tmp_path, column, value, message):
    source = tmp_path / "sessions.csv"
    values = rows()
    values[2][column] = value
    write(source, values)
    with pytest.raises(ValueError, match=message):
        load_session_dataset(source, held_out_session_count=1)


def test_entry_ordering_validated_even_in_fitting_sessions(tmp_path):
    source = tmp_path / "sessions.csv"
    values = rows()
    values[0].update(entry_time_ms="15", future_event_time_ms="30")
    write(source, values)
    with pytest.raises(ValueError, match="Entry timestamps must be strictly increasing"):
        load_session_dataset(source, held_out_session_count=1)


def test_sessions_not_sorted_silently(tmp_path):
    source = tmp_path / "sessions.csv"
    values = rows()
    write(source, values[3:6] + values[:3] + values[6:])
    with pytest.raises(ValueError, match="strictly chronological"):
        load_session_dataset(source, held_out_session_count=1)


def test_shared_feature_timestamp_between_sessions_is_rejected(tmp_path):
    source = tmp_path / "sessions.csv"
    values = rows()
    values[3]["depth_event_time_ms"] = "20"
    write(source, values)
    with pytest.raises(ValueError, match="strictly chronological"):
        load_session_dataset(source, held_out_session_count=1)


def test_equal_feature_times_within_session_are_allowed(tmp_path):
    source = tmp_path / "sessions.csv"
    values = rows(economic=False)
    values[1]["depth_event_time_ms"] = "0"
    write(source, values)
    assert load_session_dataset(source).sessions[0].partition.rows == 3


def test_depth_labels_do_not_require_economic_return_columns(tmp_path):
    source = tmp_path / "sessions.csv"
    write(source, rows(economic=False))
    assert all(item.outcomes is None for item in load_session_dataset(source).sessions)


def test_partial_economic_schema_rejected(tmp_path):
    source = tmp_path / "sessions.csv"
    values = rows()
    for row in values:
        del row["net_return_bps"]
    write(source, values)
    with pytest.raises(ValueError, match="incomplete economic"):
        load_session_dataset(source)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"held_out_session_count": -1},
        {"embargo_ms": -1},
        {"held_out_session_count": True},
        {"embargo_ms": 1.5},
    ],
)
def test_invalid_configuration_rejected_before_loading(tmp_path, kwargs):
    with pytest.raises(ValueError, match="nonnegative integers"):
        load_session_dataset(tmp_path / "not-opened.csv", **kwargs)


def test_source_changes_between_passes_are_detected(tmp_path, monkeypatch):
    source = tmp_path / "sessions.csv"
    values = rows()
    write(source, values)
    original_scan = session_data.scan_session_metadata

    def changing_scan(path):
        metadata = original_scan(path)
        values[0]["target_direction"] = "1"
        write(path, values)
        return metadata

    monkeypatch.setattr(session_data, "scan_session_metadata", changing_scan)
    with pytest.raises(ValueError, match="changed during session loading"):
        load_session_dataset(source, held_out_session_count=1)


def test_missing_timestamps_rejected(tmp_path):
    source = tmp_path / "sessions.csv"
    values = rows()
    for row in values:
        del row["depth_event_time_ms"]
    write(source, values)
    with pytest.raises(ValueError, match="missing columns: depth_event_time_ms"):
        load_session_dataset(source)


def test_cannot_reserve_every_session(tmp_path):
    source = tmp_path / "sessions.csv"
    write(source, rows())
    with pytest.raises(ValueError, match="at least one research session"):
        load_session_dataset(source, held_out_session_count=4)


def test_holdout_feature_timestamps_are_still_validated(tmp_path):
    source = tmp_path / "sessions.csv"
    values = rows()
    values[-1]["depth_event_time_ms"] = "0"
    write(source, values)
    with pytest.raises(ValueError, match="not chronological"):
        load_session_dataset(source, held_out_session_count=1)
