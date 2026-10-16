"""Read-only mechanical case/outcome reviews; no learning, LLM judgments or orders."""

import argparse
import json
import time
from collections import Counter
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

from ai_trader.research.paper_evaluation import _with_registered_paper_snapshot
from ai_trader.trading.microstructure_paper import ADAPTER_VERSION
from ai_trader.trading.microstructure_policy import POLICY_VERSION
from ai_trader.trading.paper_lifecycle import PaperEntryOrder, _timestamp
from ai_trader.trading.trade_case import PostTradeReview, PreTradeCase
from ai_trader.trading.trade_journal import _encode
from ai_trader.training.microstructure_data import _hash, _json, _publish

REVIEW_VERSION = "mechanical_case_outcome_review_v1"
MAX_REPORT_BYTES = 32 * 1024 * 1024
RUBRIC = MappingProxyType(
    {
        "version": REVIEW_VERSION,
        "scope": "all_cases_entire_verified_committed_prefix",
        "first_pass": "sealed_case_only_no_outcomes",
        "second_pass": "join_verified_fills_and_costed_outcomes",
        "decision_quality": "unknown_structural_checks_do_not_establish_strategy_quality",
        "unknown_outcomes": "unfilled_and_open_cases_have_no_closed_trade_pnl",
        "lesson_status": "anecdote_no_validation_or_promotion",
        "excursions": "unknown_not_derived_from_portfolio_equity",
    }
)


def review_case_process(case: PreTradeCase, registration) -> dict:
    """Outcome-blind structural rubric: deliberately accepts no fills, returns or future marks."""
    if type(case) is not PreTradeCase:
        raise ValueError("Typed sealed pre-trade case required.")
    policy_version = ADAPTER_VERSION
    if case.risk_reason != "protective_exit_tick":
        policy_version += ":" + POLICY_VERSION
    checks = {
        "paper_mode": case.mode == "paper",
        "policy_version_matches": case.policy_version == policy_version + ":" + registration.sha256,
        "feature_version_matches": case.feature_version
        == ("receipt_causal_microstructure_v1:" + _hash(_encode(registration.replay.features))),
        "risk_configuration_matches": case.risk_config_sha256
        == registration.gateway.risk_config_sha256,
        "evidence_available_at_decision": all(
            e.available_at_ns <= case.decision_at_ns for e in case.evidence
        ),
        "entry_plan_unexpired_at_decision": None
        if case.plan is None
        else case.plan.expires_at_ns > case.decision_at_ns,
        "approved_size_within_proposal": None
        if case.risk_verdict != "APPROVED"
        else case.approved_quantity_btc <= case.plan.quantity_btc,
    }
    return {
        "case_id": case.case_id,
        "case_sha256": case.sha256,
        "source_session": case.source_session,
        "decision_at_ns": case.decision_at_ns,
        "action": case.action,
        "risk_verdict": case.risk_verdict,
        "risk_reason": case.risk_reason,
        "checks": checks,
        "failed_checks": [k for k, passed in checks.items() if passed is False],
        "decision_quality": "UNKNOWN",
        "limitation": "Structural consistency is not independent policy/risk or thesis validation.",
    }


def _review_snapshot(journal, registration, evaluation):
    # The same read transaction covers evaluator, sealed cases, orders and review joins.
    cases = [
        journal.get_case(row[0])
        for row in journal._db.execute("SELECT case_id FROM cases ORDER BY rowid")
    ]
    if len(cases) != evaluation["frames_evaluated"]:
        raise ValueError("Review scope must retain every verified case.")
    process = [review_case_process(case, registration) for case in cases]
    # No outcome is supplied to the first pass above.
    trades = {trade["case_id"]: trade for trade in evaluation["trades"]}
    entries = {}
    for identifier in journal.order_ids():
        order = journal.get_order(identifier)
        if type(order) is PaperEntryOrder:
            if order.case_id in entries:
                raise ValueError("Multiple entry orders for a reviewed case.")
            entries[order.case_id] = (order, journal.order_events(identifier)[-1])
    reviewed_at = time.time_ns()
    _timestamp(reviewed_at)
    if reviewed_at < max(evaluation["ended_at_ns"], registration.registered_at_ns):
        raise ValueError("Review creation precedes its evidence or registration.")
    reviews = []
    for case, blind in zip(cases, process, strict=True):
        trade, entry = trades.get(case.case_id), entries.get(case.case_id)
        status = (
            trade["status"]
            if trade
            else "order_rejected"
            if entry
            else "risk_rejected"
            if case.risk_verdict == "REJECTED"
            else "not_submitted"
            if case.action == "ENTER_LONG"
            else "no_action"
        )
        resolved = None
        if trade is not None and trade["status"] == "closed":
            review = PostTradeReview(
                case=case,
                trade_id=trade["entry_order_id"],
                outcome_resolved_at_ns=trade["closed_at_ns"],
                reviewed_at_ns=reviewed_at,
                net_pnl_usdt=Decimal(trade["net_realized_pnl_usdt"]),
                decision_quality="UNKNOWN",
                summary=(
                    "Verified quote-paper outcome. Mechanical case checks are recorded separately; "
                    "one outcome does not establish decision quality or a reusable pattern."
                ),
                reviewer_version=REVIEW_VERSION,
                outcome_evidence_sha256=evaluation["ledger_snapshot_sha256"],
            )
            resolved = {**asdict(review), "outcome": review.outcome}
        reviews.append(
            {
                "review_id": "review-"
                + _hash(case.sha256 + evaluation["ledger_snapshot_sha256"] + REVIEW_VERSION),
                "available_at_ns": reviewed_at,
                "process": blind,
                "status": status,
                "entry_order_id": entry[0].order_id if entry else None,
                "entry_terminal_event": entry[1].kind if entry else None,
                "trade": trade,
                "resolved_review": resolved,
                "maximum_adverse_excursion_usdt": None,
                "maximum_favorable_excursion_usdt": None,
                "lesson_status": "ANECDOTE",
                "promotion_allowed": False,
            }
        )
    return {
        "schema_version": 1,
        "artifact_type": "mechanical_paper_review",
        "review_version": REVIEW_VERSION,
        "rubric": dict(RUBRIC),
        "rubric_sha256": _hash(_json(dict(RUBRIC))),
        "registration_sha256": registration.sha256,
        "ledger_snapshot_sha256": evaluation["ledger_snapshot_sha256"],
        "evaluation_sha256": _hash(_json(evaluation)),
        "reviewed_at_ns": reviewed_at,
        "source_session": evaluation["source_session"],
        "cases_reviewed": len(reviews),
        "status_counts": dict(Counter(r["status"] for r in reviews)),
        "process_failure_cases": sum(bool(r["failed_checks"]) for r in process),
        "session_consumed": evaluation["session_consumed"],
        "market_fault_frames": evaluation["market_fault_frames"],
        "open_trades": evaluation["open_trades"],
        "reviews": reviews,
        "mode": "research_only",
        "orders_created": 0,
        "training_started": False,
        "promotion_allowed": False,
        "live_trading_available": False,
        "limitation": (
            "Outcome-blind structural checks plus verified quote-paper outcomes; "
            "not an independent risk audit, causal thesis assessment, MAE/MFE analysis, "
            "validated lesson or model training. "
            "Unknown/open/unfilled cases are not zero-return trades. All cases are retained."
        ),
    }


def review_registered_paper(
    *,
    registration_path: Path,
    capture_path: Path,
    source_session: str,
    journal_path: Path,
    max_frames: int,
    output_path: Path,
) -> dict:
    """Create a new bounded review artifact; never append to or modify the source journal."""
    output_path = Path(output_path)
    if output_path.exists() or output_path.with_name(output_path.name + ".partial").exists():
        raise FileExistsError(output_path)
    report = _with_registered_paper_snapshot(
        registration_path=registration_path,
        capture_path=capture_path,
        source_session=source_session,
        journal_path=journal_path,
        max_frames=max_frames,
        transform=_review_snapshot,
    )
    report = json.loads(_json(report))
    _publish(report, output_path, payload_name="report", max_bytes=MAX_REPORT_BYTES)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("registration", "capture", "journal", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--source-session", required=True)
    parser.add_argument("--max-frames", type=int, required=True)
    args = parser.parse_args()
    result = review_registered_paper(
        registration_path=args.registration,
        capture_path=args.capture,
        source_session=args.source_session,
        journal_path=args.journal,
        max_frames=args.max_frames,
        output_path=args.output,
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "cases_reviewed",
                    "status_counts",
                    "process_failure_cases",
                    "orders_created",
                )
            }
        )
    )
    if (
        not result["session_consumed"]
        or result["market_fault_frames"]
        or result["process_failure_cases"]
        or result["open_trades"]
    ):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
