"""Local-only tests of the bounded cloud capture spool and upload contract."""

from __future__ import annotations

import asyncio
import json
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ai_trader.ingestion.cloud_capture_service import (
    CloudCaptureConfig,
    _capture_failure_streak,
    run_cloud_capture_service,
)


class FakeUploader:
    def __init__(self, *, fail_once: bool = False) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_once = fail_once

    def upload_once(self, path: Path, object_name: str) -> str:
        if self.fail_once:
            self.fail_once = False
            raise OSError("simulated upload outage")
        payload = path.read_bytes()
        if object_name in self.objects:
            assert self.objects[object_name] == payload
        self.objects[object_name] = payload
        return "1"


def _config(tmp_path: Path, **kwargs: object) -> CloudCaptureConfig:
    return CloudCaptureConfig(
        bucket="example-btcusdt-bucket",
        spool=tmp_path,
        stop_at=datetime.now(UTC) + timedelta(hours=1),
        min_free_bytes=0,
        **kwargs,
    )


async def _collector(seconds: int, *, output_path: Path, limits):
    assert seconds == 300
    assert limits.max_bytes == 32 * 1024 * 1024
    output_path.write_bytes(b"public capture\n")
    return output_path, 2, 3


def test_completed_capture_uploads_archive_and_receipt_then_prunes_raw(tmp_path: Path) -> None:
    uploader = FakeUploader()
    result = asyncio.run(
        run_cloud_capture_service(
            _config(tmp_path), uploader=uploader, collector=_collector, max_new_sessions=1
        )
    )
    assert result["attempts"] == 1
    assert len(uploader.objects) == 2
    session = next(tmp_path.glob("s_*"))
    receipt = json.loads((session / "receipt.json").read_text())
    assert receipt["status"] == "completed"
    assert receipt["public_data_only"] is True
    assert receipt["orders_submitted"] is False
    assert receipt["training_started"] is False
    assert not (session / "capture.jsonl").exists()
    assert (session / "uploaded.json").is_file()
    archive = next(value for key, value in uploader.objects.items() if key.endswith(".tar.gz"))
    archive_path = tmp_path / "saved.tar.gz"
    archive_path.write_bytes(archive)
    with tarfile.open(archive_path, "r:gz") as bundle:
        assert bundle.extractfile("capture.jsonl").read() == b"public capture\n"


def test_failed_capture_keeps_partial_evidence_and_does_not_claim_success(tmp_path: Path) -> None:
    async def failing(seconds: int, *, output_path: Path, limits):
        output_path.with_suffix(".jsonl.partial").write_bytes(b"partial\n")
        raise RuntimeError("private exception text is not persisted")

    uploader = FakeUploader()
    result = asyncio.run(
        run_cloud_capture_service(
            _config(tmp_path, failure_pause_seconds=0),
            uploader=uploader,
            collector=failing,
            max_new_sessions=1,
        )
    )
    assert result["attempts"] == 1
    session = next(tmp_path.glob("s_*"))
    receipt = json.loads((session / "receipt.json").read_text())
    assert receipt["status"] == "failed"
    assert receipt["error_type"] == "RuntimeError"
    assert "private exception text" not in (session / "receipt.json").read_text()
    archive = next(value for key, value in uploader.objects.items() if key.endswith(".tar.gz"))
    archive_path = tmp_path / "failed.tar.gz"
    archive_path.write_bytes(archive)
    with tarfile.open(archive_path, "r:gz") as bundle:
        assert bundle.extractfile("capture.jsonl.partial").read() == b"partial\n"
    assert _capture_failure_streak([session]) == 1


def test_interrupted_attempt_is_uploaded_before_deadline_exit(tmp_path: Path) -> None:
    session = tmp_path / "s_20260925T230000Z_aaaaaaaaaaaa"
    session.mkdir()
    (session / "started.json").write_text("{}\n")
    (session / "capture.jsonl.partial").write_text("incomplete\n")
    uploader = FakeUploader()
    config = CloudCaptureConfig(
        bucket="example-btcusdt-bucket",
        spool=tmp_path,
        stop_at=datetime.now(UTC) - timedelta(seconds=1),
        min_free_bytes=0,
    )
    result = asyncio.run(run_cloud_capture_service(config, uploader=uploader))
    assert result["attempts"] == 1
    assert json.loads((session / "receipt.json").read_text())["status"] == "interrupted"
    assert len(uploader.objects) == 2


def test_upload_outage_retains_spool_and_retry_uses_same_session(tmp_path: Path) -> None:
    uploader = FakeUploader(fail_once=True)
    config = _config(tmp_path)
    with pytest.raises(OSError, match="upload outage"):
        asyncio.run(
            run_cloud_capture_service(
                config, uploader=uploader, collector=_collector, max_new_sessions=1
            )
        )
    session = next(tmp_path.glob("s_*"))
    assert (session / "evidence.tar.gz").is_file()
    assert not (session / "uploaded.json").exists()
    result = asyncio.run(
        run_cloud_capture_service(config, uploader=uploader, max_new_sessions=0)
    )
    assert result["attempts"] == 1
    assert (session / "uploaded.json").is_file()
    assert len(uploader.objects) == 2


def test_config_rejects_unbounded_upload_and_non_utc_deadline(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="30 GiB"):
        _config(tmp_path, max_uploaded_bytes=31 * 1024**3)
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        CloudCaptureConfig("example-bucket", tmp_path, datetime(2026, 9, 25))
