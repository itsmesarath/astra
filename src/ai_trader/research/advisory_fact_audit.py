"""Offline numerical sidecars and pending curriculum review packets, not training exports."""

import argparse
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical
from ai_trader.models.review_contracts import SPOT_LONG_V2
from ai_trader.research.advisory_evaluation import (
    REVIEW_STATUS,
    _validate_suite,
    load_suite,
    model_input,
    read_pinned,
    reference_response,
    score_responses,
)
from ai_trader.research.spot_long_checks import CHECK_VERSION, assess_spot_long


def _base(suite, kind):
    return {
        "schema_version": 1,
        "kind": kind,
        "suite_sha256": suite.sha256,
        "check_version": CHECK_VERSION,
        "review_status": REVIEW_STATUS,
        "model_calls": 0,
        "orders": 0,
        "execution_allowed": False,
        "training_export_allowed": False,
        "promotion_allowed": False,
    }


def audit_recorded_responses(suite, recording):
    """Preserve the original score/raw replies; never use their labels to calculate facts."""
    score = score_responses(suite, recording)
    rows = []
    for case, model_check in zip(suite.cases, score["cases"], strict=True):
        assessment = assess_spot_long(case.snapshot, case.source_session)
        observed = model_check["observed_verdict"]
        comparison = "not_comparable"
        if model_check["schema_valid"] is True and assessment["status"] != "preflight_refused":
            if observed == "support":
                comparison = (
                    "conditional_agreement"
                    if assessment["status"] == "conditional_support"
                    else "model_support_conflicts_with_numeric_veto"
                )
            else:
                comparison = (
                    "veto_agreement"
                    if assessment["status"] == "veto"
                    else "model_veto_despite_positive_estimates"
                )
        rows.append(
            {"case_id": case.case_id, "numerical_assessment": assessment, "comparison": comparison}
        )
    return {
        **_base(suite, "recorded_advisory_numeric_sidecar"),
        "model_score": score,
        "numerical_checks": rows,
        "model_support_conflict_count": sum(
            r["comparison"] == "model_support_conflicts_with_numeric_veto" for r in rows
        ),
        "rationale_semantics_verified": False,
        "combined_pass_or_promotion_metric": None,
    }


def curriculum_review_packet(suite):
    """Draft-only human review material; never silently include development cases or fit data."""
    _validate_suite(suite)
    rows = []
    for case in suite.cases:
        if case.split != "curriculum_draft":
            continue
        assessment = assess_spot_long(case.snapshot, case.source_session)
        # This comparison happens AFTER calculation. Authored targets do not drive the checker.
        verdict = {"conditional_support": "support", "veto": "veto"}.get(assessment["status"])
        rows.append(
            {
                "case_id": case.case_id,
                "family": case.family,
                "source_session": case.source_session,
                "input": model_input(case, SPOT_LONG_V2),
                "numerical_assessment": assessment,
                "draft_reference_response": reference_response(case),
                "draft_citation_groups": case.citation_groups,
                "draft_verdict_agrees_with_numeric_check": (
                    verdict == case.expected if verdict is not None else None
                ),
                "operator_review": "pending",
                "training_eligible": False,
            }
        )
    return {
        **_base(suite, "pending_advisory_curriculum_fact_review"),
        "review_contract": SPOT_LONG_V2,
        "included_split": "curriculum_draft",
        "excluded_case_count": len(suite.cases) - len(rows),
        "case_count": len(rows),
        "cases": rows,
        "rationale_semantics_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--suite-sha256", required=True)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--responses", type=Path)
    choice.add_argument("--curriculum-review", action="store_true")
    parser.add_argument("--artifact-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.responses) != bool(args.artifact_sha256):
        parser.error("--responses requires --artifact-sha256; curriculum review uses no recording.")
    suite = load_suite(args.suite, args.suite_sha256)
    if args.responses:
        report = audit_recorded_responses(suite, read_pinned(args.responses, args.artifact_sha256))
        report["source_artifact_sha256"] = args.artifact_sha256
    else:
        report = curriculum_review_packet(suite)
    encoded = canonical(report)
    if len(encoded.encode("utf-8")) > 2 * 1024 * 1024:
        raise ValueError("Report byte budget exceeded.")
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded + "\n")
    print(
        canonical(
            {
                "kind": report["kind"],
                "output": str(args.output),
                "model_calls": 0,
                "training_export_allowed": False,
                "promotion_allowed": False,
            }
        )
    )
    # Success means report written, never that a model, curriculum or strategy is approved.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
