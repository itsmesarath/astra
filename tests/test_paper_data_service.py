"""Tests for the bounded independent public-data service."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from ai_trader.ingestion.paper_data_service import (
    PaperDataServiceConfig,
    run_paper_data_service,
)


async def _collector(seconds: int, *, output_path: Path, limits) -> tuple[Path, int, int]:
    assert seconds == 2
    assert limits.max_events > 0
    output_path.write_text("capture\n", encoding="utf-8")
    return output_path, 3, 4


def test_public_capture_requires_explicit_opt_in(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="enable_public_data"):
        PaperDataServiceConfig(1, 2, tmp_path)


def test_service_commits_finite_sessions_and_never_training_or_orders(tmp_path: Path) -> None:
    config = PaperDataServiceConfig(
        sessions=2,
        seconds_per_session=2,
        output_directory=tmp_path,
        enable_public_data=True,
        build_features=False,
        service_id="test-run",
    )
    result = asyncio.run(run_paper_data_service(config, collector=_collector))

    assert result.completed_sessions == 2
    assert result.failed_sessions == 0
    assert not (tmp_path / ".paper-data-service.lock").exists()
    records = [json.loads(line) for line in result.manifest_path.read_text().splitlines()]
    assert [record["record_type"] for record in records] == [
        "service_start",
        "session_start",
        "session_completed",
        "session_start",
        "session_completed",
        "service_completed",
    ]
    assert records[-1]["training_started"] is False
    assert records[-1]["orders_submitted"] is False


def test_existing_manifest_is_not_appended(tmp_path: Path) -> None:
    manifest = tmp_path / "run.jsonl"
    manifest.write_text("existing\n", encoding="utf-8")
    config = PaperDataServiceConfig(
        sessions=1,
        seconds_per_session=1,
        output_directory=tmp_path,
        manifest_path=manifest,
        enable_public_data=True,
        build_features=False,
    )
    with pytest.raises(FileExistsError, match="existing manifest"):
        asyncio.run(run_paper_data_service(config, collector=_collector))


def test_failed_session_stops_without_retry_and_retains_audit(tmp_path: Path) -> None:
    calls = 0

    async def failing_collector(seconds: int, *, output_path: Path, limits):
        nonlocal calls
        calls += 1
        raise RuntimeError("network unavailable")

    config = PaperDataServiceConfig(
        sessions=3,
        seconds_per_session=1,
        output_directory=tmp_path,
        enable_public_data=True,
        build_features=False,
        service_id="failed-run",
    )
    with pytest.raises(RuntimeError, match="network unavailable"):
        asyncio.run(run_paper_data_service(config, collector=failing_collector))
    assert calls == 1
    records = [
        json.loads(line) for line in (tmp_path / "failed-run.jsonl").read_text().splitlines()
    ]
    assert records[-1]["record_type"] == "session_failed"
    assert not (tmp_path / ".paper-data-service.lock").exists()
