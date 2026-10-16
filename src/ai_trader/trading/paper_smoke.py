"""Explicit-source OFFLINE paper plumbing check. Never proposes or permits orders."""

import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from ai_trader.features.microstructure import MicrostructureConfig
from ai_trader.risk.engine import RiskLimits
from ai_trader.trading.capture_replay import CaptureReplay, CaptureReplayConfig
from ai_trader.trading.durable_paper_gateway import DurablePaperGateway, PaperGatewayConfig
from ai_trader.trading.execution import ExecutionCosts
from ai_trader.trading.paper_account import PaperAccountSeed
from ai_trader.trading.paper_runner import PaperRunner, PaperRunnerConfig
from ai_trader.trading.trade_journal import JournalConflict, TradeJournal, _identifier

DEFAULT_REPLAY_CONFIG = CaptureReplayConfig()


def run_smoke(
    *,
    capture_path: Path,
    expected_sha256: str,
    source_session: str,
    journal_path: Path,
    run_id: str,
    initial_cash_usdt: Decimal,
    max_frames: int,
    replay_config: CaptureReplayConfig = DEFAULT_REPLAY_CONFIG,
    resume: bool = False,
) -> dict:
    """One atomic bounded invocation; exact restarts require --resume and a larger budget.

    No candidate cases, account history, model, discovery, migration or network.
    The kill switch is durably armed as a second defense. All ticks from this
    invocation roll back if anything attempts an order or processing fails.
    """
    _identifier(run_id)
    if type(resume) is not bool or type(max_frames) is not int or not 1 <= max_frames <= 10_000:
        raise ValueError("Boolean resume and max_frames in [1, 10000] required.")
    replay = CaptureReplay.from_path(
        capture_path,
        expected_sha256=expected_sha256,
        source_session=source_session,
        config=replay_config,
    )
    seed = PaperAccountSeed(initial_cash_usdt, next(replay.frames()).tick.observed_at_ns)
    # Fixed smoke-only settings, not a strategy configuration or recommended allocation.
    gateway_config = PaperGatewayConfig(
        RiskLimits(
            Decimal("0.01"),
            Decimal("0.001"),
            Decimal("100"),
            Decimal("1000"),
            Decimal("10"),
            Decimal("20"),
        ),
        ExecutionCosts(Decimal("10"), Decimal("5")),
        2_000_000_000,
    )
    runner_config = PaperRunnerConfig(2_000_000_000, Decimal("20"))
    factory = TradeJournal if resume else TradeJournal.create
    with factory(journal_path, run_id=run_id, mode="paper") as journal:
        # BEGIN IMMEDIATE prevents another writer from adding an order mid-check.
        with journal._write():
            if journal.order_ids():
                raise JournalConflict("Smoke checks require a dedicated journal with no orders.")
            if resume:
                if journal.account_seed() != seed:
                    raise JournalConflict("Smoke account seed differs; never reset on resume.")
                gateway = DurablePaperGateway(journal, gateway_config)
                runner = PaperRunner(gateway, runner_config)
                if not gateway.risk_checkpoint().kill_switch_active:
                    raise JournalConflict("Smoke journal kill switch must remain active.")
            else:
                journal.initialize_account(seed)
                gateway = DurablePaperGateway.initialize(journal, gateway_config)
                gateway.set_kill_switch(True, observed_at_ns=seed.initialized_at_ns)
                runner = PaperRunner.initialize(gateway, runner_config)
            outcomes = replay.run(runner, max_frames=max_frames)
            if journal.order_ids():
                raise JournalConflict("Unexpected smoke order; entire invocation rolled back.")
            account = journal.account_state()
            complete = outcomes[-1].line_number == replay.record_count
            faults = sum(o.status.startswith("resync_required:") for o in outcomes)
            health = dict(Counter(o.result.quote_health for o in outcomes))
            return {
                "mode": "offline_paper_smoke",
                "journal": str(Path(journal_path).resolve()),
                "capture_sha256": expected_sha256,
                "source_session": source_session,
                "run_id": run_id,
                "frames_processed": len(outcomes),
                "status": ("session_invalid" if faults else "session_complete")
                if complete
                else "frame_budget_reached",
                "session_consumed": complete,
                "market_fault_frames": faults,
                "check_result": "failed"
                if faults or (complete and not health.get("healthy"))
                else "passed"
                if complete
                else "incomplete",
                "quote_health_counts": health,
                "orders": 0,
                "kill_switch_active": True,
                "cash_usdt": str(account.cash_usdt),
                "position_btc": str(account.position_btc),
                "note": "Plumbing check only; no strategy, training or profitability evaluation.",
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--source-session", required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--initial-cash-usdt", type=Decimal, required=True)
    parser.add_argument("--max-frames", type=int, required=True)
    parser.add_argument("--levels", type=int, default=5)
    parser.add_argument(
        "--rolling-window-ms", type=int, default=DEFAULT_REPLAY_CONFIG.features.rolling_window_ms
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    report = run_smoke(
        capture_path=args.capture,
        expected_sha256=args.sha256,
        source_session=args.source_session,
        journal_path=args.journal,
        run_id=args.run_id,
        initial_cash_usdt=args.initial_cash_usdt,
        max_frames=args.max_frames,
        resume=args.resume,
        replay_config=CaptureReplayConfig(
            features=MicrostructureConfig(
                levels=args.levels,
                rolling_window_ms=args.rolling_window_ms,
            )
        ),
    )
    print(json.dumps(report, sort_keys=True))
    if report["check_result"] == "failed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
