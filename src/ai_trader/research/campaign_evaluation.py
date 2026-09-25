"""Read-only, continuous-account evaluation of a registered offline paper campaign."""

import argparse
import json
from decimal import localcontext
from pathlib import Path

from ai_trader.research.microstructure_trial import _environment, load_registration
from ai_trader.research.paper_evaluation import DECIMAL_CONTEXT, _evaluate_snapshot
from ai_trader.trading.capture_replay import _implementation_hash
from ai_trader.trading.microstructure_campaign import (
    CAMPAIGN_VERSION,
    CampaignInput,
    _load_replays,
    campaign_run_id,
)
from ai_trader.trading.trade_journal import TradeJournal


def evaluate_registered_campaign(
    *,
    registration_path: Path,
    sources: tuple[CampaignInput, ...],
    journal_path: Path,
    max_frames: int,
) -> dict:
    """Use the existing fixed valuation protocol without resetting at session boundaries."""
    if type(max_frames) is not int or not 1 <= max_frames <= 10_000:
        raise ValueError("Global frame budget must be an integer in [1, 10000].")
    registration = load_registration(registration_path)
    replays = _load_replays(registration, sources)
    with (
        TradeJournal(
            journal_path, run_id=campaign_run_id(registration), mode="paper", read_only=True
        ) as journal,
        localcontext(DECIMAL_CONTEXT),
    ):
        journal._db.execute("BEGIN")
        try:
            report = _evaluate_snapshot(journal, registration, replays, max_frames)
            if (
                registration.implementation_sha256 != _implementation_hash()
                or registration.environment_json != _environment()
            ):
                raise ValueError("Source/environment changed during campaign evaluation.")
            report.update(
                campaign_version=CAMPAIGN_VERSION,
                campaign_consumed=report["session_consumed"],
                full_campaign_flat_comparison_available=report[
                    "full_session_flat_comparison_available"
                ],
            )
            return report
        finally:
            journal._db.execute("ROLLBACK")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument(
        "--source", nargs=2, action="append", required=True, metavar=("SESSION", "PATH")
    )
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, required=True)
    args = parser.parse_args()
    report = evaluate_registered_campaign(
        registration_path=args.registration,
        sources=tuple(CampaignInput(name, Path(path)) for name, path in args.source),
        journal_path=args.journal,
        max_frames=args.max_frames,
    )
    print(json.dumps(report, sort_keys=True))
    if not report["full_session_flat_comparison_available"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
