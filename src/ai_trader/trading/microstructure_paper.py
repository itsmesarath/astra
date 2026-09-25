"""Explicitly activated OFFLINE paper simulation of a registered research hypothesis.

Not forward paper deployment, strategy promotion, an L2 fill model or live trading.
Original research cases/registrations are never rewritten into execution authority.
"""

import argparse
import json
from collections import Counter
from dataclasses import replace
from decimal import localcontext
from itertools import chain, islice
from pathlib import Path

from ai_trader.research.microstructure_trial import _environment, load_registration
from ai_trader.trading.capture_replay import CaptureReplay, _implementation_hash
from ai_trader.trading.durable_paper_gateway import DurablePaperGateway
from ai_trader.trading.microstructure_policy import ResearchRiskSnapshot, assess_microstructure
from ai_trader.trading.paper_account import PaperAccountSeed
from ai_trader.trading.paper_runner import PaperRunner, PaperRunnerConfig
from ai_trader.trading.trade_case import CaseEvidence, PreTradeCase
from ai_trader.trading.trade_journal import JournalConflict, TradeJournal, _encode, _hash

ADAPTER_VERSION = "offline_microstructure_paper_v1"


def paper_run_id(registration, source_session):
    registration.research_source(source_session)
    return "micro-paper-" + _hash(
        ADAPTER_VERSION + ":" + registration.sha256 + ":" + source_session
    )


def _case_id(registration, tick):
    return "micro-paper-case-" + _hash(
        ADAPTER_VERSION + ":" + registration.sha256 + ":" + tick.tick_id
    )


def _evidence(registration, frame, context):
    return (
        CaseEvidence("paper_replay_frame", frame.tick.observed_at_ns, _hash(_encode(frame))),
        CaseEvidence("paper_decision_context", frame.tick.observed_at_ns, _hash(_encode(context))),
        # Availability is the simulated decision time; this is configuration provenance,
        # not a claim that the real-world operator registered before historical trading.
        CaseEvidence(
            "offline_paper_activation",
            frame.tick.observed_at_ns,
            _hash(ADAPTER_VERSION + ":" + registration.sha256),
        ),
    )


def _build_case(registration, frame, context):
    evidence = _evidence(registration, frame, context)
    case_id = _case_id(registration, frame.tick)
    if context.protection_active:
        # Do not ask entry policy to reassess after an exit or when an exit is blocked.
        # In particular, a malformed entry observation cannot veto position protection.
        return PreTradeCase(
            case_id,
            frame.tick.source_session,
            frame.tick.observed_at_ns,
            ADAPTER_VERSION + ":" + registration.sha256,
            "receipt_causal_microstructure_v1:" + _hash(_encode(registration.replay.features)),
            frame.tick.observation_sha256,
            "Protect existing paper inventory before considering entries.",
            "No same-tick re-entry after protection, including a blocked exit.",
            "Unhealthy quotes block execution; no guessed prices or forced footer liquidation.",
            evidence,
            "NO_ACTION",
            None,
            "NOT_EVALUATED",
            "protective_exit_tick",
            registration.gateway.risk_config_sha256,
            mode="paper",
        )
    account, checkpoint = context.account, context.checkpoint
    # Use journal state AFTER marks, day rollover and any protection, not trial cash
    # on every frame. No kill, loss, peak or pending-order state is reset here.
    with localcontext() as decimal_context:
        decimal_context.prec = 100
        risk = ResearchRiskSnapshot(
            frame.tick.observed_at_ns,
            account.cash_usdt,
            account.position_btc,
            account.realized_pnl_usdt - checkpoint.day_start_realized_usdt,
            checkpoint.peak_equity_usdt,
            checkpoint.kill_switch_active,
            bool(account.unresolved_order_ids),
        )
    assessment = assess_microstructure(
        frame,
        policy=registration.policy,
        features=registration.replay.features,
        gateway=registration.gateway,
        risk=risk,
        registration_sha256=registration.sha256,
    )
    # Fresh assessment from this paper ledger, not promotion/copying of shadow-journal cases.
    return replace(
        assessment,
        case_id=case_id,
        mode="paper",
        policy_version=ADAPTER_VERSION + ":" + assessment.policy_version,
        evidence=assessment.evidence + evidence,
    )


def _verify_replayed_case(case, registration, frame):
    expected = {
        "paper_replay_frame": _hash(_encode(frame)),
        "offline_paper_activation": _hash(ADAPTER_VERSION + ":" + registration.sha256),
    }
    if case is None or case.case_id != _case_id(registration, frame.tick) or case.mode != "paper":
        raise JournalConflict("Missing or mismatched durable paper case.")
    evidence = {item.evidence_id: item for item in case.evidence}
    for name, checksum in expected.items():
        if (
            name not in evidence
            or evidence[name].observation_sha256 != checksum
            or evidence[name].available_at_ns != frame.tick.observed_at_ns
        ):
            raise JournalConflict("Paper case frame/activation evidence differs on retry.")


def simulate_registered_capture(
    *,
    registration_path: Path,
    capture_path: Path,
    source_session: str,
    journal_path: Path,
    max_frames: int,
    enable_paper_simulation: bool = False,
    resume: bool = False,
) -> dict:
    """One bounded, atomic invocation. No network, hidden file discovery or live mode.

    Explicit activation is required on EVERY invocation, including resume. It
    consents only to local quote-fill simulation, not promotion of this hypothesis.
    One immutable registration/source belongs to one dedicated funded paper run.
    """
    if enable_paper_simulation is not True:
        raise ValueError(
            "Explicit enable_paper_simulation=True is required for offline paper fills."
        )
    if type(resume) is not bool or type(max_frames) is not int or not 1 <= max_frames <= 10_000:
        raise ValueError("Boolean resume and frame budget in [1, 10000] required.")
    registration = load_registration(registration_path)
    source = registration.research_source(
        source_session
    )  # Reject holdout before capture/journal IO.
    replay = CaptureReplay.from_path(
        capture_path,
        expected_sha256=source.source_sha256,
        source_session=source_session,
        config=registration.replay,
    )
    framing = replay._framing()
    if (framing[0]["started_at_ns"], framing[-1]["ended_at_ns"]) != (
        source.started_at_ns,
        source.ended_at_ns,
    ):
        raise ValueError("Capture times differ from registered source declaration.")
    return _simulate_replays(
        registration,
        (replay,),
        journal_path=journal_path,
        max_frames=max_frames,
        resume=resume,
        run_id=paper_run_id(registration, source_session),
    )


def _simulate_replays(registration, replays, *, journal_path, max_frames, resume, run_id):
    """Shared internal executor; public callers must validate activation and source scope."""
    seed = PaperAccountSeed(
        registration.initial_cash_usdt, next(replays[0].frames()).tick.observed_at_ns
    )
    runner_config = PaperRunnerConfig(
        registration.policy.maximum_trade_age_ns, registration.policy.maximum_spread_bps
    )
    factory = TradeJournal if resume else TradeJournal.create
    cases, reasons, health = Counter(), Counter(), Counter()
    count, faults = 0, 0
    entry_ids, exit_ids, blocked = [], [], []
    sessions = {
        r.source_session: {
            "source_session": r.source_session,
            "source_sha256": r.source_sha256,
            "frames_in_prefix": 0,
            "session_consumed": False,
            "market_fault_frames": 0,
        }
        for r in replays
    }
    last_lines = {r.source_session: r.record_count for r in replays}
    with factory(journal_path, run_id=run_id, mode="paper") as journal:
        with journal._write():
            prior_count = journal._db.execute("SELECT count(*) FROM paper_runner_ticks").fetchone()[
                0
            ]
            if len(replays) > 1 and prior_count > max_frames:
                raise JournalConflict("Campaign budget cannot omit previously committed ticks.")
            prior_ids = [
                row[0]
                for row in journal._db.execute(
                    "SELECT tick_id FROM paper_runner_ticks ORDER BY sequence LIMIT ?",
                    (max_frames,),
                )
            ]
            if resume:
                if journal.account_seed() != seed:
                    raise JournalConflict("Paper account seed mismatch; refusing to reset it.")
                gateway = DurablePaperGateway(journal, registration.gateway)
                runner = PaperRunner(gateway, runner_config)
            else:
                journal.initialize_account(seed)
                gateway = DurablePaperGateway.initialize(journal, registration.gateway)
                runner = PaperRunner.initialize(gateway, runner_config)
            for frame in islice(chain.from_iterable(r.frames() for r in replays), max_frames):
                if count < len(prior_ids) and prior_ids[count] != frame.tick.tick_id:
                    raise JournalConflict("Committed tick sequence is not the registered prefix.")
                case_id = _case_id(registration, frame.tick)

                def builder(context, current_frame=frame):
                    return _build_case(registration, current_frame, context)

                result = runner.process_with_case_builder(
                    frame.tick, case_id=case_id, build_case=builder
                )
                case = journal.get_case(case_id)
                _verify_replayed_case(case, registration, frame)
                count += 1
                faults += frame.status.startswith("resync_required:")
                session = sessions[frame.tick.source_session]
                session["frames_in_prefix"] += 1
                session["market_fault_frames"] += frame.status.startswith("resync_required:")
                session["session_consumed"] = (
                    frame.line_number == last_lines[frame.tick.source_session]
                )
                cases[f"{case.action}:{case.risk_verdict}"] += 1
                reasons[case.risk_reason] += 1
                health[result.quote_health] += 1
                if result.entry_order_id:
                    entry_ids.append(result.entry_order_id)
                exit_ids.extend(result.exit_order_ids)
                blocked = list(result.blocked_exit_entry_ids)
            if count < len(prior_ids):
                raise JournalConflict("Journal extends beyond the registered replay prefix.")
            if (
                registration.implementation_sha256 != _implementation_hash()
                or registration.environment_json != _environment()
            ):
                raise ValueError(
                    "Source/environment changed during simulation; invocation rolled back."
                )
            account, checkpoint = journal.account_state(), gateway.risk_checkpoint()
            # Report the current ledger, not a recomputed budget-prefix balance on retries.
            # For a smaller replayed prefix, these balances may include later committed ticks.
            report = {
                "mode": "offline_paper_simulation",
                "adapter_version": ADAPTER_VERSION,
                "registration_sha256": registration.sha256,
                "journal_run_id": run_id,
                "source_session": replays[0].source_session if len(replays) == 1 else None,
                "source_sessions": list(sessions.values()),
                "frames_processed": count,
                "session_consumed": all(s["session_consumed"] for s in sessions.values()),
                "market_fault_frames": faults,
                "case_counts": dict(cases),
                "case_reason_counts": dict(reasons),
                "quote_health_counts": dict(health),
                "entry_order_ids_in_prefix": entry_ids,
                "exit_order_ids_in_prefix": exit_ids,
                "blocked_exit_entry_ids_at_prefix_end": blocked,
                "ledger_order_count": len(journal.order_ids()),
                "cash_usdt": str(account.cash_usdt),
                "position_btc": str(account.position_btc),
                "cost_basis_usdt": str(account.cost_basis_usdt),
                "realized_pnl_usdt": str(account.realized_pnl_usdt),
                "fees_usdt": str(account.fees_usdt),
                "ledger_observed_at_ns": checkpoint.observed_at_ns,
                "kill_switch_active": checkpoint.kill_switch_active,
                "promotion_allowed": False,
                "live_trading_available": False,
                "limitation": (
                    "Quote-only fills; open inventory is not liquidated or valued "
                    "at the footer. No profitability claim."
                ),
            }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--source-session", required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, required=True)
    parser.add_argument(
        "--enable-paper-simulation",
        action="store_true",
        help="Explicit consent to local simulated fills, not strategy promotion.",
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    report = simulate_registered_capture(
        registration_path=args.registration,
        capture_path=args.capture,
        source_session=args.source_session,
        journal_path=args.journal,
        max_frames=args.max_frames,
        enable_paper_simulation=args.enable_paper_simulation,
        resume=args.resume,
    )
    print(json.dumps(report, sort_keys=True))
    if report["market_fault_frames"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
