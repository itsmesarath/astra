"""Tests for combining independently labeled capture sessions."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from ai_trader.training.combine_datasets import combine_labeled_datasets

FIELDNAMES = (
    "schema_version",
    "symbol",
    "depth_event_time_ms",
    "update_id",
    "midpoint",
    "future_event_time_ms",
    "label_horizon_ms",
    "neutral_threshold_bps",
    "target_direction",
)


def make_rows(
    *,
    start_time_ms: int,
    start_update_id: int,
    directions: tuple[int, ...] = (-1, 0, 1),
    horizon_ms: int = 1000,
    threshold_bps: str = "0.5",
    symbol: str = "BTCUSDT",
) -> list[dict[str, str]]:
    """Create one small chronological labeled session."""
    rows = []

    for offset, direction in enumerate(directions):
        event_time_ms = start_time_ms + offset * 100
        rows.append(
            {
                "schema_version": "1",
                "symbol": symbol,
                "depth_event_time_ms": str(event_time_ms),
                "update_id": str(start_update_id + offset),
                "midpoint": str(100 + offset),
                "future_event_time_ms": str(event_time_ms + horizon_ms),
                "label_horizon_ms": str(horizon_ms),
                "neutral_threshold_bps": threshold_bps,
                "target_direction": str(direction),
            }
        )

    return rows


def write_dataset(
    path: Path,
    rows: list[dict[str, str]],
) -> None:
    """Write one labeled-session fixture."""
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=FIELDNAMES,
        )
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read every row from a combined CSV."""
    with path.open(encoding="utf-8", newline="") as input_file:
        return list(csv.DictReader(input_file))


def test_combines_sessions_in_chronological_order(
    tmp_path: Path,
) -> None:
    """Input order must not control combined chronological order."""
    early_path = tmp_path / "early.csv"
    late_path = tmp_path / "late.csv"
    output_path = tmp_path / "combined.csv"

    write_dataset(
        early_path,
        make_rows(
            start_time_ms=1000,
            start_update_id=10,
        ),
    )
    write_dataset(
        late_path,
        make_rows(
            start_time_ms=5000,
            start_update_id=20,
            directions=(1, 1),
        ),
    )

    report = combine_labeled_datasets(
        [late_path, early_path],
        output_path,
    )
    rows = read_rows(output_path)

    assert report.session_count == 2
    assert report.total_rows == 5
    assert report.down_labels == 1
    assert report.neutral_labels == 1
    assert report.up_labels == 3
    assert [row["depth_event_time_ms"] for row in rows] == [
        "1000",
        "1100",
        "1200",
        "5000",
        "5100",
    ]
    assert rows[0]["source_session"].startswith("session_0001_early")
    assert rows[-1]["source_session"].startswith("session_0002_late")


def test_writes_auditable_manifest(tmp_path: Path) -> None:
    """Manifest must record configuration, hashes, and class counts."""
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    output_path = tmp_path / "combined.csv"

    write_dataset(
        first_path,
        make_rows(
            start_time_ms=1000,
            start_update_id=10,
        ),
    )
    write_dataset(
        second_path,
        make_rows(
            start_time_ms=5000,
            start_update_id=20,
        ),
    )

    report = combine_labeled_datasets(
        [first_path, second_path],
        output_path,
    )

    with report.manifest_path.open(encoding="utf-8") as input_file:
        manifest = json.load(input_file)

    assert manifest["schema_version"] == 1
    assert manifest["session_count"] == 2
    assert manifest["total_rows"] == 6
    assert manifest["symbol"] == "BTCUSDT"
    assert manifest["label_horizon_ms"] == 1000
    assert manifest["neutral_threshold_bps"] == "0.5"
    assert manifest["class_counts"] == {
        "down": 2,
        "neutral": 2,
        "up": 2,
    }
    assert len(manifest["sessions"][0]["source_sha256"]) == 64
    assert manifest["sessions"][0]["rows"] == 3


def test_rejects_overlapping_label_periods(tmp_path: Path) -> None:
    """No session may begin before the prior session's labels finish."""
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"

    write_dataset(
        first_path,
        make_rows(
            start_time_ms=1000,
            start_update_id=10,
        ),
    )
    write_dataset(
        second_path,
        make_rows(
            start_time_ms=2000,
            start_update_id=20,
        ),
    )

    with pytest.raises(ValueError, match="sessions overlap"):
        combine_labeled_datasets(
            [first_path, second_path],
            tmp_path / "combined.csv",
        )


def test_rejects_mismatched_label_configuration(
    tmp_path: Path,
) -> None:
    """Combined sessions must use an identical prediction horizon."""
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"

    write_dataset(
        first_path,
        make_rows(
            start_time_ms=1000,
            start_update_id=10,
        ),
    )
    write_dataset(
        second_path,
        make_rows(
            start_time_ms=5000,
            start_update_id=20,
            horizon_ms=5000,
        ),
    )

    with pytest.raises(ValueError, match="different label horizon"):
        combine_labeled_datasets(
            [first_path, second_path],
            tmp_path / "combined.csv",
        )


def test_rejects_duplicate_source_path(tmp_path: Path) -> None:
    """The same capture cannot be counted twice."""
    session_path = tmp_path / "session.csv"
    write_dataset(
        session_path,
        make_rows(
            start_time_ms=1000,
            start_update_id=10,
        ),
    )

    with pytest.raises(ValueError, match="must be unique"):
        combine_labeled_datasets(
            [session_path, session_path],
            tmp_path / "combined.csv",
        )
