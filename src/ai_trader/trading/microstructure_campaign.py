"""Explicit offline multi-capture paper continuity; no network or live execution.

All registered research captures, in declared order, share one funded account.
Every call reconstructs a bounded global prefix; it never skips to a new session.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from ai_trader.research.microstructure_trial import load_registration
from ai_trader.trading.capture_replay import CaptureReplay
from ai_trader.trading.microstructure_paper import _simulate_replays
from ai_trader.trading.trade_journal import _hash, _identifier

CAMPAIGN_VERSION = "offline_microstructure_campaign_v1"
MAX_CAMPAIGN_SOURCES = 32
MAX_CAMPAIGN_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class CampaignInput:
    source_session: str
    capture_path: Path

    def __post_init__(self):
        _identifier(self.source_session)
        if not isinstance(self.capture_path, Path):
            raise ValueError("Campaign capture path must be an explicit Path.")


def campaign_run_id(registration):
    return "micro-paper-campaign-" + _hash(CAMPAIGN_VERSION + ":" + registration.sha256)


def _load_replays(registration, sources):
    """Validate the entire declared scope BEFORE any capture path/stat/read is touched."""
    research = tuple(s for s in registration.sources if s.role == "research")
    if (
        type(sources) is not tuple
        or not 2 <= len(sources) <= MAX_CAMPAIGN_SOURCES
        or any(type(s) is not CampaignInput for s in sources)
        or tuple(s.source_session for s in sources) != tuple(s.source_session for s in research)
    ):
        raise ValueError(
            "Supply every registered research source, in declared order, exactly once (2-32)."
        )
    # The fixed registration already excludes overlapping times and aliased capture hashes.
    total_bytes, replays = 0, []
    for selected, declared in zip(sources, research, strict=True):
        if total_bytes + selected.capture_path.stat().st_size > MAX_CAMPAIGN_BYTES:
            raise ValueError("Campaign exceeds its aggregate capture byte budget.")
        replay = CaptureReplay.from_path(
            selected.capture_path,
            expected_sha256=declared.source_sha256,
            source_session=declared.source_session,
            config=registration.replay,
        )
        total_bytes += len(replay._data)
        if total_bytes > MAX_CAMPAIGN_BYTES:
            raise ValueError("Campaign exceeds its aggregate capture byte budget.")
        framing = replay._framing()
        if (framing[0]["started_at_ns"], framing[-1]["ended_at_ns"]) != (
            declared.started_at_ns,
            declared.ended_at_ns,
        ):
            raise ValueError("Capture times differ from registered source declaration.")
        replays.append(replay)
    return tuple(replays)


def simulate_registered_campaign(
    *,
    registration_path: Path,
    sources: tuple[CampaignInput, ...],
    journal_path: Path,
    max_frames: int,
    enable_paper_simulation: bool = False,
    resume: bool = False,
) -> dict:
    """One atomic prefix across declared sessions, not a forward feed service.

    Start with a NEW journal; single-session journals cannot be converted implicitly.
    The first account seed is retained across all fresh book/feature reconstructions.
    """
    if enable_paper_simulation is not True:
        raise ValueError(
            "Explicit enable_paper_simulation=True is required for offline paper fills."
        )
    if type(resume) is not bool or type(max_frames) is not int or not 1 <= max_frames <= 10_000:
        raise ValueError("Boolean resume and global frame budget in [1, 10000] required.")
    registration = load_registration(registration_path)
    replays = _load_replays(registration, sources)
    report = _simulate_replays(
        registration,
        replays,
        journal_path=journal_path,
        max_frames=max_frames,
        resume=resume,
        run_id=campaign_run_id(registration),
    )
    report.update(
        mode="offline_paper_campaign",
        campaign_version=CAMPAIGN_VERSION,
        campaign_consumed=report["session_consumed"],
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument(
        "--source", nargs=2, action="append", required=True, metavar=("SESSION", "PATH")
    )
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, required=True)
    parser.add_argument("--enable-paper-simulation", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    report = simulate_registered_campaign(
        registration_path=args.registration,
        sources=tuple(CampaignInput(name, Path(path)) for name, path in args.source),
        journal_path=args.journal,
        max_frames=args.max_frames,
        enable_paper_simulation=args.enable_paper_simulation,
        resume=args.resume,
    )
    print(json.dumps(report, sort_keys=True))
    if report["market_fault_frames"] or not report["campaign_consumed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
