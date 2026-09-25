"""Run a bounded, restart-safe public-data capture service.

This service is deliberately narrower than a trading daemon.  It records finite
Binance public WebSocket sessions and can build the existing causal
microstructure artifact after each session.  It never submits orders, reads
credentials, retries a failed session, or starts training.  A caller can run it
from a normal shell after this chat ends; the explicit session and byte limits
make the run auditable instead of an unbounded hidden process.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_trader.features.build_microstructure import build_microstructure_dataset
from ai_trader.ingestion.collect_combined import CaptureLimits, collect
from ai_trader.trading.prospective_paper import (
    MAX_FRAMES,
    PaperSource,
    load_paper_plan,
    simulate_paper_prefix,
)

MAX_SESSIONS = 1_000
MAX_PAUSE_SECONDS = 24 * 60 * 60


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _positive_integer(value: object, name: str, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [1, {maximum}].")
    return value


@dataclass(frozen=True, slots=True)
class PaperDataServiceConfig:
    """Immutable limits for one local capture run."""

    sessions: int
    seconds_per_session: int
    output_directory: Path
    manifest_path: Path | None = None
    pause_seconds: int = 0
    enable_public_data: bool = False
    build_features: bool = True
    capture_limits: CaptureLimits = CaptureLimits()
    service_id: str | None = None
    paper_plan_path: Path | None = None
    paper_journal_path: Path | None = None
    max_paper_frames: int = MAX_FRAMES
    enable_paper_simulation: bool = False

    def __post_init__(self) -> None:
        _positive_integer(self.sessions, "sessions", MAX_SESSIONS)
        _positive_integer(self.seconds_per_session, "seconds_per_session", 3_600)
        if type(self.pause_seconds) is not int or not 0 <= self.pause_seconds <= MAX_PAUSE_SECONDS:
            raise ValueError(f"pause_seconds must be an integer in [0, {MAX_PAUSE_SECONDS}].")
        if type(self.enable_public_data) is not bool or not self.enable_public_data:
            raise ValueError("Public network capture requires enable_public_data=True.")
        if type(self.build_features) is not bool:
            raise ValueError("build_features must be boolean.")
        if type(self.capture_limits) is not CaptureLimits:
            raise ValueError("capture_limits must be CaptureLimits.")
        if self.service_id is not None:
            if type(self.service_id) is not str or not self.service_id.strip():
                raise ValueError("service_id must be a non-empty string when supplied.")
            if any(
                character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
                for character in self.service_id
            ):
                raise ValueError("service_id may contain only letters, digits, '-' and '_'.")
        if (self.paper_plan_path is None) != (self.paper_journal_path is None):
            raise ValueError("Paper plan and journal paths must be supplied together.")
        if self.paper_plan_path is not None and (
            not self.enable_paper_simulation or self.service_id is None
        ):
            raise ValueError("Paper replay requires explicit activation and a fixed service_id.")
        if self.enable_paper_simulation and self.paper_plan_path is None:
            raise ValueError("Paper replay requires a predeclared paper plan.")
        if self.paper_plan_path is not None and self.sessions > 32:
            raise ValueError("A paper service supports at most 32 sessions per plan.")
        _positive_integer(self.max_paper_frames, "max_paper_frames", MAX_FRAMES)


@dataclass(frozen=True, slots=True)
class PaperDataServiceResult:
    """Committed summary for a completed finite service run."""

    service_id: str
    manifest_path: Path
    completed_sessions: int
    failed_sessions: int
    capture_paths: tuple[Path, ...]
    feature_paths: tuple[Path, ...]


Collector = Callable[..., Awaitable[tuple[Path, int, int]]]
FeatureBuilder = Callable[..., int]
Sleeper = Callable[[float], Awaitable[Any]]


def _default_service_id() -> str:
    return datetime.now(UTC).strftime("paper-data-%Y%m%dT%H%M%S_%fZ")


def _append_record(path: Path, record: dict[str, Any]) -> None:
    """Append one canonical audit line and force it to durable storage."""
    encoded = (
        json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()
    with path.open("ab") as output:
        output.write(encoded)
        output.flush()
        os.fsync(output.fileno())


def _owned_lock(path: Path) -> None:
    try:
        with path.open("xb") as output:
            output.write(b"paper-data-service lock; inspect before removing\n")
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError as error:
        raise RuntimeError(f"Another paper data service owns {path}.") from error


async def run_paper_data_service(
    config: PaperDataServiceConfig,
    *,
    collector: Collector = collect,
    feature_builder: FeatureBuilder = build_microstructure_dataset,
    sleeper: Sleeper = asyncio.sleep,
    paper_simulator: Callable[..., dict[str, Any]] = simulate_paper_prefix,
) -> PaperDataServiceResult:
    """Capture and optionally feature-build exactly ``config.sessions`` sessions.

    A failed session is recorded and stops the run.  There is intentionally no
    automatic retry or ``forever`` mode: the operator can inspect the retained
    partial files and start a new explicit run later.
    """
    if type(config) is not PaperDataServiceConfig:
        raise TypeError("PaperDataServiceConfig is required.")
    output_directory = config.output_directory
    paper_plan = load_paper_plan(config.paper_plan_path) if config.paper_plan_path else None
    if paper_plan is not None and paper_plan.service_id != config.service_id:
        raise ValueError("Paper plan service_id differs from the capture service_id.")
    output_directory.mkdir(parents=True, exist_ok=True)
    service_id = config.service_id or _default_service_id()
    manifest_path = config.manifest_path or output_directory / f"{service_id}.jsonl"
    manifest_path = Path(manifest_path)
    if manifest_path.exists():
        raise FileExistsError(f"Refusing to append to existing manifest: {manifest_path}")
    lock_path = output_directory / ".paper-data-service.lock"
    _owned_lock(lock_path)
    capture_paths: list[Path] = []
    feature_paths: list[Path] = []
    completed = 0
    failed = 0
    started_at_ns = time.time_ns()
    try:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("xb") as output:
            output.flush()
            os.fsync(output.fileno())
        _append_record(
            manifest_path,
            {
                "record_type": "service_start",
                "schema_version": 1,
                "service_id": service_id,
                "started_at_ns": started_at_ns,
                "config": {
                    "sessions": config.sessions,
                    "seconds_per_session": config.seconds_per_session,
                    "pause_seconds": config.pause_seconds,
                    "build_features": config.build_features,
                    "public_data_only": True,
                },
            },
        )
        for index in range(config.sessions):
            source_session = f"{service_id}-s{index + 1:04d}"
            capture_path = output_directory / f"{source_session}.jsonl"
            feature_path = output_directory / f"{source_session}.microstructure.jsonl"
            _append_record(
                manifest_path,
                {
                    "record_type": "session_start",
                    "source_session": source_session,
                    "sequence": index + 1,
                    "capture_path": str(capture_path),
                    "started_at_ns": time.time_ns(),
                },
            )
            try:
                captured_path, trades, depths = await collector(
                    config.seconds_per_session,
                    output_path=capture_path,
                    limits=config.capture_limits,
                )
                if Path(captured_path) != capture_path:
                    raise ValueError(
                        "Collector published a path different from its requested destination."
                    )
                built_observations = None
                if config.build_features:
                    feature_options: dict[str, Any] = {"source_session": source_session}
                    if paper_plan is not None:
                        feature_options["config"] = paper_plan.replay.features
                    built_observations = feature_builder(
                        capture_path,
                        feature_path,
                        **feature_options,
                    )
                    feature_paths.append(feature_path)
                paper_report = None
                if paper_plan is not None:
                    paper_sources = tuple(
                        PaperSource(f"{service_id}-s{number:04d}", path)
                        for number, path in enumerate((*capture_paths, capture_path), start=1)
                    )
                    paper_report = paper_simulator(
                        plan_path=config.paper_plan_path,
                        sources=paper_sources,
                        journal_path=config.paper_journal_path,
                        max_frames=config.max_paper_frames,
                        enable_paper_simulation=True,
                        resume=index > 0,
                    )
                    if not paper_report["session_consumed"] or paper_report["market_fault_frames"]:
                        raise ValueError(
                            "Paper replay stopped on incomplete or unhealthy market data."
                        )
                capture_paths.append(capture_path)
                completed += 1
                _append_record(
                    manifest_path,
                    {
                        "record_type": "session_completed",
                        "source_session": source_session,
                        "sequence": index + 1,
                        "capture_path": str(capture_path),
                        "capture_sha256": _sha256(capture_path),
                        "trade_events": trades,
                        "depth_events": depths,
                        "feature_path": str(feature_path)
                        if built_observations is not None
                        else None,
                        "feature_observations": built_observations,
                        "paper_journal_path": (
                            str(config.paper_journal_path) if paper_report is not None else None
                        ),
                        "paper_plan_sha256": paper_plan.sha256
                        if paper_report is not None
                        else None,
                        "paper_ledger_order_count": (
                            paper_report["ledger_order_count"] if paper_report is not None else None
                        ),
                        "completed_at_ns": time.time_ns(),
                    },
                )
            except BaseException as error:
                failed += 1
                _append_record(
                    manifest_path,
                    {
                        "record_type": "session_failed",
                        "source_session": source_session,
                        "sequence": index + 1,
                        "capture_path": str(capture_path),
                        "error_type": type(error).__name__,
                        "completed_at_ns": time.time_ns(),
                    },
                )
                raise
            if index + 1 < config.sessions and config.pause_seconds:
                await sleeper(config.pause_seconds)
        _append_record(
            manifest_path,
            {
                "record_type": "service_completed",
                "service_id": service_id,
                "completed_sessions": completed,
                "failed_sessions": failed,
                "completed_at_ns": time.time_ns(),
                "training_started": False,
                "orders_submitted": False,
            },
        )
    finally:
        lock_path.unlink(missing_ok=True)
    return PaperDataServiceResult(
        service_id,
        manifest_path,
        completed,
        failed,
        tuple(capture_paths),
        tuple(feature_paths),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-public-data", action="store_true")
    parser.add_argument("--sessions", type=int, required=True)
    parser.add_argument("--seconds-per-session", type=int, default=120)
    parser.add_argument("--pause-seconds", type=int, default=0)
    parser.add_argument("--output-directory", type=Path, default=Path("data/raw/paper_service"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--skip-features", action="store_true")
    parser.add_argument("--service-id")
    parser.add_argument("--paper-plan", type=Path)
    parser.add_argument("--paper-journal", type=Path)
    parser.add_argument("--max-paper-frames", type=int, default=MAX_FRAMES)
    parser.add_argument("--enable-paper-simulation", action="store_true")
    args = parser.parse_args()
    try:
        PaperDataServiceConfig(
            sessions=args.sessions,
            seconds_per_session=args.seconds_per_session,
            output_directory=args.output_directory,
            manifest_path=args.manifest,
            pause_seconds=args.pause_seconds,
            enable_public_data=args.enable_public_data,
            build_features=not args.skip_features,
            service_id=args.service_id,
            paper_plan_path=args.paper_plan,
            paper_journal_path=args.paper_journal,
            max_paper_frames=args.max_paper_frames,
            enable_paper_simulation=args.enable_paper_simulation,
        )
    except ValueError as error:
        parser.error(str(error))
    return args


def main() -> None:
    args = _parse_args()
    config = PaperDataServiceConfig(
        sessions=args.sessions,
        seconds_per_session=args.seconds_per_session,
        output_directory=args.output_directory,
        manifest_path=args.manifest,
        pause_seconds=args.pause_seconds,
        enable_public_data=True,
        build_features=not args.skip_features,
        service_id=args.service_id,
        paper_plan_path=args.paper_plan,
        paper_journal_path=args.paper_journal,
        max_paper_frames=args.max_paper_frames,
        enable_paper_simulation=args.enable_paper_simulation,
    )
    result = asyncio.run(run_paper_data_service(config))
    print(
        json.dumps(
            {"manifest": str(result.manifest_path.resolve()), "sessions": result.completed_sessions}
        )
    )


if __name__ == "__main__":
    main()
