"""Finite, public-data-only BTCUSDT capture with verified cloud archiving.

Each attempt has a fresh source session. Interrupted/failed attempts are
archived as evidence, never promoted to complete sessions. Uploads are
create-only and checked against Cloud Storage object metadata before local
large files are removed. No account API, model, or order path is reachable.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import tarfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from ai_trader.ingestion.collect_combined import CaptureLimits, collect

_BUCKET_RE = re.compile(r"[a-z0-9][a-z0-9._-]{2,61}[a-z0-9]")
_SESSION_RE = re.compile(r"s_\d{8}T\d{6}Z_[0-9a-f]{12}")
_ARTIFACTS = (
    "started.json",
    "capture.jsonl",
    "capture.jsonl.partial",
    "capture.jsonl.stream.partial",
)
MAX_DURATION = timedelta(days=31)


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _md5_base64(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return base64.b64encode(digest.digest()).decode("ascii")


def _write_json(path: Path, value: dict[str, object]) -> None:
    temp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with temp.open("xb") as output:
        output.write(encoded)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temp, path)


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"Expected a JSON object in {path}.")
    return value


@dataclass(frozen=True, slots=True)
class CloudCaptureConfig:
    bucket: str
    spool: Path
    stop_at: datetime
    seconds_per_session: int = 300
    max_attempts: int = 9_000
    max_uploaded_bytes: int = 30 * 1024**3
    min_free_bytes: int = 2 * 1024**3
    failure_pause_seconds: int = 60
    max_consecutive_capture_failures: int = 12

    def __post_init__(self) -> None:
        if not _BUCKET_RE.fullmatch(self.bucket):
            raise ValueError("Invalid Cloud Storage bucket name.")
        if self.stop_at.tzinfo is None or self.stop_at.utcoffset() != timedelta(0):
            raise ValueError("stop_at must be timezone-aware UTC.")
        if not 1 <= self.seconds_per_session <= 3_600:
            raise ValueError("seconds_per_session must be in [1, 3600].")
        if not 1 <= self.max_attempts <= 10_000:
            raise ValueError("max_attempts must be in [1, 10000].")
        if not 1 <= self.max_uploaded_bytes <= 30 * 1024**3:
            raise ValueError("max_uploaded_bytes must be at most 30 GiB.")
        if not 0 <= self.min_free_bytes <= 10 * 1024**3:
            raise ValueError("Invalid minimum free-space threshold.")
        if not 0 <= self.failure_pause_seconds <= 3_600:
            raise ValueError("Invalid failure pause.")
        if not 1 <= self.max_consecutive_capture_failures <= 100:
            raise ValueError("Invalid capture failure threshold.")


class Uploader(Protocol):
    def upload_once(self, path: Path, object_name: str) -> str: ...


class GcsUploader:
    """Uses the VM's metadata identity; never reads a key file."""

    def __init__(self, bucket: str) -> None:
        from google.cloud import storage

        self._bucket = storage.Client().bucket(bucket)

    def upload_once(self, path: Path, object_name: str) -> str:
        from google.api_core.exceptions import PreconditionFailed

        blob = self._bucket.blob(object_name)
        try:
            blob.upload_from_filename(
                str(path), if_generation_match=0, checksum="crc32c", timeout=120
            )
        except PreconditionFailed:
            # An ambiguous earlier upload can succeed before the reply is lost.
            # Accept it only after verifying the immutable object's content.
            pass
        blob.reload(timeout=30)
        if blob.size != path.stat().st_size or blob.md5_hash != _md5_base64(path):
            raise ValueError(f"Cloud object does not match local evidence: {object_name}")
        return str(blob.generation)


def _session_dirs(spool: Path) -> list[Path]:
    result = []
    for path in sorted(spool.iterdir()):
        if path.is_dir() and not path.is_symlink() and _SESSION_RE.fullmatch(path.name):
            result.append(path)
    return result


def _finalize(path: Path, *, status: str, trades: int = 0, depths: int = 0,
              error_type: str | None = None) -> dict[str, object]:
    files = []
    for name in _ARTIFACTS:
        item = path / name
        if item.is_file() and not item.is_symlink():
            files.append({"name": name, "bytes": item.stat().st_size, "sha256": _sha256(item)})
    if status == "completed" and not (path / "capture.jsonl").is_file():
        raise ValueError("A completed capture must have a published JSONL file.")
    archive = path / "evidence.tar.gz"
    partial = path / "evidence.tar.gz.partial"
    with partial.open("xb") as output:
        with tarfile.open(fileobj=output, mode="w:gz") as bundle:
            for file in files:
                name = str(file["name"])
                bundle.add(path / name, arcname=name, recursive=False)
        output.flush()
        os.fsync(output.fileno())
    os.replace(partial, archive)
    receipt: dict[str, object] = {
        "schema_version": 1,
        "source_session": path.name,
        "status": status,
        "error_type": error_type,
        "completed_at": datetime.now(UTC).isoformat(),
        "trade_events": trades,
        "depth_events": depths,
        "files": files,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": _sha256(archive),
        "public_data_only": True,
        "orders_submitted": False,
        "training_started": False,
    }
    _write_json(path / "receipt.json", receipt)
    return receipt


def _cleanup_uploaded(path: Path) -> None:
    if not (path / "uploaded.json").is_file():
        raise ValueError("Refusing to prune unverified local evidence.")
    for name in (*_ARTIFACTS, "evidence.tar.gz"):
        (path / name).unlink(missing_ok=True)


def _upload_attempt(path: Path, uploader: Uploader) -> dict[str, object]:
    receipt = _read_json(path / "receipt.json")
    archive = path / "evidence.tar.gz"
    if _sha256(archive) != receipt["archive_sha256"]:
        raise ValueError("Local archive differs from its receipt.")
    prefix = f"btcusdt/sessions/{path.name[2:6]}/{path.name[6:8]}/{path.name[8:10]}"
    archive_generation = uploader.upload_once(archive, f"{prefix}/{path.name}.tar.gz")
    receipt_generation = uploader.upload_once(
        path / "receipt.json", f"{prefix}/{path.name}.receipt.json"
    )
    uploaded: dict[str, object] = {
        "archive_generation": archive_generation,
        "receipt_generation": receipt_generation,
        "verified_at": datetime.now(UTC).isoformat(),
    }
    _write_json(path / "uploaded.json", uploaded)
    _cleanup_uploaded(path)
    return receipt


def _recover(path: Path) -> None:
    if (path / "uploaded.json").is_file():
        _cleanup_uploaded(path)
    elif not (path / "receipt.json").is_file():
        (path / "evidence.tar.gz.partial").unlink(missing_ok=True)
        (path / "evidence.tar.gz").unlink(missing_ok=True)
        _finalize(path, status="interrupted", error_type="InterruptedBeforeReceipt")
    elif not (path / "evidence.tar.gz").is_file():
        raise ValueError("Receipt exists without local archive or upload marker.")


def _total_uploaded_bytes(paths: list[Path]) -> int:
    total = 0
    for path in paths:
        if (path / "uploaded.json").is_file():
            receipt = _read_json(path / "receipt.json")
            total += int(receipt["archive_bytes"])
    return total


def _capture_failure_streak(paths: list[Path]) -> int:
    streak = 0
    for path in reversed(paths):
        if not (path / "uploaded.json").is_file():
            break
        status = _read_json(path / "receipt.json")["status"]
        if status == "completed":
            break
        streak += 1
    return streak


Collector = Callable[..., Awaitable[tuple[Path, int, int]]]


async def run_cloud_capture_service(
    config: CloudCaptureConfig,
    *,
    uploader: Uploader,
    collector: Collector = collect,
    sleeper: Callable[[float], Awaitable[object]] = asyncio.sleep,
    max_new_sessions: int | None = None,
) -> dict[str, object]:
    """Run only until the predeclared deadline, attempt cap, or byte cap."""
    if type(config) is not CloudCaptureConfig:
        raise TypeError("CloudCaptureConfig is required.")
    if config.stop_at - datetime.now(UTC) > MAX_DURATION:
        raise ValueError("Cloud capture cannot be scheduled more than 31 days ahead.")
    config.spool.mkdir(parents=True, exist_ok=True)
    created = 0
    while True:
        paths = _session_dirs(config.spool)
        for path in paths:
            _recover(path)
            if not (path / "uploaded.json").is_file():
                receipt = _upload_attempt(path, uploader)
                print(
                    json.dumps(
                        {
                            "source_session": path.name,
                            "status": receipt["status"],
                            "archive_bytes": receipt["archive_bytes"],
                            "recovered_upload": True,
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
        paths = _session_dirs(config.spool)
        uploaded_bytes = _total_uploaded_bytes(paths)
        failure_streak = _capture_failure_streak(paths)
        if (
            datetime.now(UTC) >= config.stop_at
            or len(paths) >= config.max_attempts
            or uploaded_bytes >= config.max_uploaded_bytes
            or (max_new_sessions is not None and created >= max_new_sessions)
        ):
            return {
                "attempts": len(paths),
                "uploaded_bytes": uploaded_bytes,
                "stopped_at": datetime.now(UTC).isoformat(),
            }
        if shutil.disk_usage(config.spool).free < config.min_free_bytes:
            raise OSError("Insufficient free disk space for a bounded capture.")
        if failure_streak >= config.max_consecutive_capture_failures:
            raise RuntimeError("Repeated capture failures; inspect uploaded receipts.")
        session_id = f"s_{datetime.now(UTC):%Y%m%dT%H%M%SZ}_{uuid4().hex[:12]}"
        path = config.spool / session_id
        path.mkdir(mode=0o700)
        _write_json(
            path / "started.json",
            {"source_session": session_id, "started_at": datetime.now(UTC).isoformat()},
        )
        status, trades, depths, error_type = "completed", 0, 0, None
        try:
            captured, trades, depths = await collector(
                config.seconds_per_session,
                output_path=path / "capture.jsonl",
                limits=CaptureLimits(),
            )
            if Path(captured) != path / "capture.jsonl":
                raise ValueError("Collector returned an unexpected destination.")
        except Exception as error:
            status, error_type = "failed", type(error).__name__
        _finalize(path, status=status, trades=trades, depths=depths, error_type=error_type)
        receipt = _upload_attempt(path, uploader)
        print(
            json.dumps(
                {
                    "source_session": path.name,
                    "status": receipt["status"],
                    "archive_bytes": receipt["archive_bytes"],
                    "recovered_upload": False,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        created += 1
        if status == "failed":
            if failure_streak + 1 >= config.max_consecutive_capture_failures:
                raise RuntimeError("Repeated capture failures; inspect uploaded receipts.")
            await sleeper(config.failure_pause_seconds)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-public-data", action="store_true")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--spool", type=Path, required=True)
    parser.add_argument("--stop-at-utc", required=True)
    parser.add_argument("--seconds-per-session", type=int, default=300)
    parser.add_argument("--max-attempts", type=int, default=9_000)
    parser.add_argument("--max-uploaded-bytes", type=int, default=30 * 1024**3)
    args = parser.parse_args()
    if not args.enable_public_data:
        parser.error("Public network capture requires --enable-public-data.")
    try:
        stop_at = datetime.fromisoformat(args.stop_at_utc.replace("Z", "+00:00"))
        args.config = CloudCaptureConfig(
            bucket=args.bucket,
            spool=args.spool,
            stop_at=stop_at,
            seconds_per_session=args.seconds_per_session,
            max_attempts=args.max_attempts,
            max_uploaded_bytes=args.max_uploaded_bytes,
        )
    except ValueError as error:
        parser.error(str(error))
    return args


def main() -> None:
    args = _parse_args()
    result = asyncio.run(
        run_cloud_capture_service(args.config, uploader=GcsUploader(args.config.bucket))
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
