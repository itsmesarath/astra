"""Tests for bounded multi-session collection campaigns."""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from pathlib import Path

import pytest

from ai_trader.ingestion.collect_campaign import (
    run_collection_campaign,
)
from ai_trader.ingestion.validate_combined import ValidationReport


def make_validation_report(
    *,
    trade_events: int,
    depth_events: int,
) -> ValidationReport:
    """Create one successful capture-validation report."""
    return ValidationReport(
        total_records=trade_events + depth_events + 3,
        snapshot_update_id=100,
        trade_events=trade_events,
        depth_events=depth_events,
        stale_depth_events=1,
        applied_depth_events=depth_events - 1,
        first_trade_id=10,
        last_trade_id=10 + trade_events - 1,
        final_book_update_id=200,
        best_bid=Decimal("100"),
        best_ask=Decimal("101"),
        spread=Decimal("1"),
        minimum_delay_ms=10.0,
        average_delay_ms=12.0,
        maximum_delay_ms=20.0,
    )


def test_collects_validates_and_records_each_session(
    tmp_path: Path,
) -> None:
    """Every successful capture must appear in the manifest."""
    manifest_path = tmp_path / "campaign.json"
    capture_index = 0
    sleep_calls: list[float] = []

    async def fake_collector(
        seconds: int,
    ) -> tuple[Path, int, int]:
        nonlocal capture_index
        assert seconds == 30
        capture_index += 1
        return (
            tmp_path / f"capture_{capture_index}.jsonl",
            capture_index * 2,
            capture_index * 10,
        )

    def fake_validator(path: Path) -> ValidationReport:
        index = int(path.stem.split("_")[-1])
        return make_validation_report(
            trade_events=index * 2,
            depth_events=index * 10,
        )

    async def fake_sleeper(seconds: float) -> None:
        sleep_calls.append(seconds)

    report = asyncio.run(
        run_collection_campaign(
            sessions=2,
            seconds_per_session=30,
            pause_seconds=5,
            manifest_path=manifest_path,
            collector=fake_collector,
            validator=fake_validator,
            sleeper=fake_sleeper,
            clock=iter(range(100, 200)).__next__,
        )
    )

    with manifest_path.open(encoding="utf-8") as input_file:
        manifest = json.load(input_file)

    assert report.completed_sessions == 2
    assert report.total_trade_events == 6
    assert report.total_depth_events == 30
    assert sleep_calls == [5.0]
    assert manifest["campaign_status"] == "complete"
    assert manifest["totals"] == {
        "completed_sessions": 2,
        "trade_events": 6,
        "depth_events": 30,
    }
    assert [session["status"] for session in manifest["sessions"]] == ["valid", "valid"]


def test_stops_and_records_validation_failure(
    tmp_path: Path,
) -> None:
    """A failed validation must stop the campaign audibly."""
    manifest_path = tmp_path / "campaign.json"

    async def fake_collector(
        seconds: int,
    ) -> tuple[Path, int, int]:
        return tmp_path / "capture.jsonl", 2, 10

    def failing_validator(path: Path) -> ValidationReport:
        raise ValueError("sequence gap")

    with pytest.raises(
        RuntimeError,
        match="failed at session 1",
    ):
        asyncio.run(
            run_collection_campaign(
                sessions=2,
                seconds_per_session=30,
                pause_seconds=0,
                manifest_path=manifest_path,
                collector=fake_collector,
                validator=failing_validator,
            )
        )

    with manifest_path.open(encoding="utf-8") as input_file:
        manifest = json.load(input_file)

    assert manifest["campaign_status"] == "failed"
    assert len(manifest["sessions"]) == 1
    assert manifest["sessions"][0]["status"] == "failed"
    assert manifest["sessions"][0]["error_type"] == "ValueError"
    assert manifest["sessions"][0]["error_message"] == "sequence gap"


def test_rejects_collector_validator_count_mismatch(
    tmp_path: Path,
) -> None:
    """Stored session counts must reconcile before acceptance."""
    manifest_path = tmp_path / "campaign.json"

    async def fake_collector(
        seconds: int,
    ) -> tuple[Path, int, int]:
        return tmp_path / "capture.jsonl", 3, 10

    def fake_validator(path: Path) -> ValidationReport:
        return make_validation_report(
            trade_events=2,
            depth_events=10,
        )

    with pytest.raises(
        RuntimeError,
        match="failed at session 1",
    ):
        asyncio.run(
            run_collection_campaign(
                sessions=1,
                seconds_per_session=30,
                pause_seconds=0,
                manifest_path=manifest_path,
                collector=fake_collector,
                validator=fake_validator,
            )
        )

    with manifest_path.open(encoding="utf-8") as input_file:
        manifest = json.load(input_file)

    assert manifest["sessions"][0]["error_type"] == "ValueError"
    assert "trade counts differ" in (manifest["sessions"][0]["error_message"])


@pytest.mark.parametrize(
    ("sessions", "seconds_per_session", "pause_seconds", "message"),
    [
        (0, 30, 0, "Session count"),
        (1, 0, 0, "Seconds per session"),
        (1, 30, -1, "Pause seconds"),
    ],
)
def test_rejects_invalid_campaign_configuration(
    tmp_path: Path,
    sessions: int,
    seconds_per_session: int,
    pause_seconds: int,
    message: str,
) -> None:
    """Campaign bounds must be explicit and valid."""
    with pytest.raises(ValueError, match=message):
        asyncio.run(
            run_collection_campaign(
                sessions=sessions,
                seconds_per_session=seconds_per_session,
                pause_seconds=pause_seconds,
                manifest_path=tmp_path / "campaign.json",
            )
        )
