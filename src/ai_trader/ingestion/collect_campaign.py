"""Run an auditable campaign of bounded public market-data captures."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ai_trader.ingestion.collect_combined import collect
from ai_trader.ingestion.validate_combined import (
    ValidationReport,
    validate_capture,
)

DEFAULT_CAMPAIGN_DIRECTORY = Path("data/raw/campaigns")

Collector = Callable[[int], Awaitable[tuple[Path, int, int]]]
Validator = Callable[[Path], ValidationReport]
Sleeper = Callable[[float], Awaitable[None]]
Clock = Callable[[], int]


@dataclass(frozen=True, slots=True)
class CampaignReport:
    """Summary of a completed collection campaign."""

    manifest_path: Path
    requested_sessions: int
    completed_sessions: int
    total_trade_events: int
    total_depth_events: int


def create_manifest_path() -> Path:
    """Create a unique default campaign-manifest path."""
    DEFAULT_CAMPAIGN_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    return DEFAULT_CAMPAIGN_DIRECTORY / (f"btcusdt_campaign_{timestamp}.json")


def write_manifest(
    path: Path,
    manifest: dict[str, object],
) -> None:
    """Atomically write the current campaign state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")

    with temporary_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as output_file:
        json.dump(manifest, output_file, indent=2)
        output_file.write("\n")

    temporary_path.replace(path)


def validation_metadata(
    report: ValidationReport,
) -> dict[str, object]:
    """Convert one validation report to JSON-safe metadata."""
    return {
        "total_records": report.total_records,
        "snapshot_update_id": report.snapshot_update_id,
        "trade_events": report.trade_events,
        "depth_events": report.depth_events,
        "stale_depth_events": report.stale_depth_events,
        "applied_depth_events": report.applied_depth_events,
        "first_trade_id": report.first_trade_id,
        "last_trade_id": report.last_trade_id,
        "final_book_update_id": report.final_book_update_id,
        "best_bid": str(report.best_bid),
        "best_ask": str(report.best_ask),
        "spread": str(report.spread),
        "minimum_delay_ms": report.minimum_delay_ms,
        "average_delay_ms": report.average_delay_ms,
        "maximum_delay_ms": report.maximum_delay_ms,
    }


async def run_collection_campaign(
    *,
    sessions: int,
    seconds_per_session: int,
    pause_seconds: int,
    manifest_path: Path,
    collector: Collector = collect,
    validator: Validator = validate_capture,
    sleeper: Sleeper = asyncio.sleep,
    clock: Clock = time.time_ns,
) -> CampaignReport:
    """Collect and immediately validate multiple bounded sessions."""
    if sessions <= 0:
        raise ValueError("Session count must be greater than zero.")
    if seconds_per_session <= 0:
        raise ValueError("Seconds per session must be greater than zero.")
    if pause_seconds < 0:
        raise ValueError("Pause seconds cannot be negative.")

    manifest: dict[str, object] = {
        "schema_version": 1,
        "campaign_status": "running",
        "symbol": "BTCUSDT",
        "started_at_ns": clock(),
        "completed_at_ns": None,
        "configuration": {
            "requested_sessions": sessions,
            "seconds_per_session": seconds_per_session,
            "pause_seconds": pause_seconds,
        },
        "sessions": [],
    }
    write_manifest(manifest_path, manifest)

    session_records: list[dict[str, object]] = []
    total_trade_events = 0
    total_depth_events = 0

    for index in range(1, sessions + 1):
        if index > 1 and pause_seconds > 0:
            await sleeper(float(pause_seconds))

        session_started_at_ns = clock()

        try:
            capture_path, trade_count, depth_count = await collector(seconds_per_session)
            validation = await asyncio.to_thread(
                validator,
                capture_path,
            )

            if trade_count != validation.trade_events:
                raise ValueError("Collector and validator trade counts differ.")
            if depth_count != validation.depth_events:
                raise ValueError("Collector and validator depth counts differ.")

            session_record = {
                "session_index": index,
                "status": "valid",
                "started_at_ns": session_started_at_ns,
                "completed_at_ns": clock(),
                "capture_path": str(capture_path.resolve()),
                "validation": validation_metadata(validation),
            }
            session_records.append(session_record)
            total_trade_events += trade_count
            total_depth_events += depth_count

        except Exception as error:
            session_records.append(
                {
                    "session_index": index,
                    "status": "failed",
                    "started_at_ns": session_started_at_ns,
                    "completed_at_ns": clock(),
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                }
            )
            manifest["campaign_status"] = "failed"
            manifest["completed_at_ns"] = clock()
            manifest["sessions"] = session_records
            write_manifest(manifest_path, manifest)
            raise RuntimeError(f"Collection campaign failed at session {index}.") from error

        manifest["sessions"] = session_records
        write_manifest(manifest_path, manifest)

    manifest["campaign_status"] = "complete"
    manifest["completed_at_ns"] = clock()
    manifest["sessions"] = session_records
    manifest["totals"] = {
        "completed_sessions": len(session_records),
        "trade_events": total_trade_events,
        "depth_events": total_depth_events,
    }
    write_manifest(manifest_path, manifest)

    return CampaignReport(
        manifest_path=manifest_path,
        requested_sessions=sessions,
        completed_sessions=len(session_records),
        total_trade_events=total_trade_events,
        total_depth_events=total_depth_events,
    )


def parse_args() -> argparse.Namespace:
    """Read bounded campaign settings."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sessions",
        type=int,
        default=4,
        help="Number of independent captures (default: 4).",
    )
    parser.add_argument(
        "--seconds-per-session",
        type=int,
        default=900,
        help="Duration of each capture in seconds (default: 900).",
    )
    parser.add_argument(
        "--pause-seconds",
        type=int,
        default=2700,
        help="Pause between captures in seconds (default: 2700).",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Optional exact campaign-manifest path.",
    )
    args = parser.parse_args()

    if args.sessions <= 0:
        parser.error("--sessions must be greater than zero")
    if args.seconds_per_session <= 0:
        parser.error("--seconds-per-session must be greater than zero")
    if args.pause_seconds < 0:
        parser.error("--pause-seconds cannot be negative")

    return args


def main() -> None:
    """Run one public-data collection campaign."""
    args = parse_args()
    manifest_path = args.manifest or create_manifest_path()

    print("Mode: PUBLIC MARKET-DATA COLLECTION CAMPAIGN")
    print(
        f"Plan: sessions={args.sessions}, "
        f"seconds_per_session={args.seconds_per_session}, "
        f"pause_seconds={args.pause_seconds}"
    )
    print(f"Manifest: {manifest_path.resolve()}")

    report = asyncio.run(
        run_collection_campaign(
            sessions=args.sessions,
            seconds_per_session=args.seconds_per_session,
            pause_seconds=args.pause_seconds,
            manifest_path=manifest_path,
        )
    )

    print(f"Completed sessions: {report.completed_sessions}")
    print(f"Trade events: {report.total_trade_events}")
    print(f"Depth events: {report.total_depth_events}")
    print(f"Manifest: {report.manifest_path.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user. Check the campaign manifest.")
