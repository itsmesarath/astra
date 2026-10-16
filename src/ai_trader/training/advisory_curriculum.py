"""Pinned curriculum review and candidate export; no model loading, training or promotion."""

import argparse
import re
from datetime import datetime
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.models.review_contracts import SPOT_LONG_V2, SPOT_LONG_V2_PROMPT
from ai_trader.research.advisory_evaluation import load_suite, read_pinned
from ai_trader.research.advisory_fact_audit import curriculum_review_packet
from ai_trader.research.council import parse_role_report
from ai_trader.research.spot_long_checks import CHECK_VERSION

REVIEW_KIND = "advisory_curriculum_review_v1"
CANDIDATE_KIND = "advisory_sft_candidate_v1"
DELEGATED_REVIEW_KIND = "advisory_delegated_curriculum_review_v2"
DELEGATED_CANDIDATE_KIND = "advisory_delegated_sft_candidate_v2"
SEMANTIC_CHECKS = (
    "rationale_supported",
    "citations_sufficient",
    "uncertainty_preserved",
    "no_execution_authority",
)
MAX_ARTIFACT_BYTES = 1024 * 1024


def _fields(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError("Unexpected review artifact fields.")


def _bounded_artifact(value):
    encoded = canonical(value)
    if len(encoded.encode("utf-8")) > MAX_ARTIFACT_BYTES:
        raise ValueError("Curriculum artifact byte budget exceeded.")
    return encoded


def prepare_review(suite):
    """Bind original targets/facts; pending is never implicitly converted to approval."""
    packet = curriculum_review_packet(suite)
    if not packet["cases"]:
        raise ValueError("A nonempty curriculum partition is required.")
    return {
        "schema_version": 1,
        "kind": REVIEW_KIND,
        "suite_sha256": suite.sha256,
        "packet_sha256": digest(packet),
        "review_contract": SPOT_LONG_V2,
        "prompt_sha256": digest(SPOT_LONG_V2_PROMPT),
        "check_version": CHECK_VERSION,
        "attestation": {
            "reviewer_type": "operator",
            "reviewer_id": None,
            "reviewed_at_utc": None,
            "confirmed": False,
        },
        "cases": [
            {
                "case_id": row["case_id"],
                "binding_sha256": digest(row),
                "decision": "pending",
                "target_response": row["draft_reference_response"],
                "checks": dict.fromkeys(SEMANTIC_CHECKS),
                "note": "",
            }
            for row in packet["cases"]
        ],
    }


def _attestation(value):
    _fields(value, ("reviewer_type", "reviewer_id", "reviewed_at_utc", "confirmed"))
    if value["reviewer_type"] not in ("operator", "agent") or type(value["confirmed"]) is not bool:
        raise ValueError("Invalid reviewer type or confirmation.")
    if not value["confirmed"]:
        if value["reviewer_id"] is not None or value["reviewed_at_utc"] is not None:
            raise ValueError("Unconfirmed review must not claim an identity/time attestation.")
        return False
    identity, stamp = value["reviewer_id"], value["reviewed_at_utc"]
    if type(identity) is not str or re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", identity) is None:
        raise ValueError("Explicit bounded reviewer identity required.")
    if (
        type(stamp) is not str
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp) is None
    ):
        raise ValueError("Review time must use UTC YYYY-MM-DDTHH:MM:SSZ.")
    datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    # A local identity/time claim is an attestation, not authenticated human provenance.
    return value["reviewer_type"] == "operator"


def validate_delegation(suite, delegation):
    """A scoped local record of user delegation, not authentication or trading authority."""
    _bounded_artifact(delegation)
    _fields(
        delegation,
        (
            "schema_version",
            "kind",
            "suite_sha256",
            "authorization_source",
            "user_instruction",
            "recorded_at_utc",
            "agent_reviewer_id",
            "review_scope",
            "manual_review_required",
            "training_allowed",
            "execution_allowed",
        ),
    )
    if (
        type(delegation["schema_version"]) is not int
        or delegation["schema_version"] != 1
        or delegation["kind"] != "user_delegated_curriculum_review_v1"
        or delegation["suite_sha256"] != suite.sha256
        or delegation["authorization_source"] != "user_message"
        or delegation["review_scope"] != "curriculum_targets_only"
        or any(
            delegation[k] is not False
            for k in (
                "manual_review_required",
                "training_allowed",
                "execution_allowed",
            )
        )
    ):
        raise ValueError("Invalid delegation scope or suite binding.")
    instruction = delegation["user_instruction"]
    if type(instruction) is not str or not instruction.strip() or len(instruction) > 1024:
        raise ValueError("Bounded explicit user-delegation instruction required.")
    # Reuse identity/time syntax validation without claiming an operator performed the review.
    _attestation(
        {
            "reviewer_type": "agent",
            "reviewer_id": delegation["agent_reviewer_id"],
            "reviewed_at_utc": delegation["recorded_at_utc"],
            "confirmed": True,
        }
    )


def prepare_delegated_review(suite, delegation):
    """Versioned opt-in to agent decisions; no decisions/checks are filled automatically."""
    validate_delegation(suite, delegation)
    review = prepare_review(suite)
    review.update(schema_version=2, kind=DELEGATED_REVIEW_KIND, delegation=dict(delegation))
    review["attestation"]["reviewer_type"] = "agent"
    return review


def audit_review(suite, review):
    """Rebuild bindings and distinguish legacy human review from explicitly delegated AI review."""
    _bounded_artifact(review)
    delegated = type(review) is dict and review.get("kind") == DELEGATED_REVIEW_KIND
    expected = (
        prepare_delegated_review(suite, review.get("delegation"))
        if delegated
        else prepare_review(suite)
    )
    _fields(review, expected)
    for name in expected.keys() - {"attestation", "cases"}:
        # Canonical comparison rejects bool-as-int schema versions as well as content drift.
        if canonical(review[name]) != canonical(expected[name]):
            raise ValueError("Review binding mismatch: " + name)
    operator = _attestation(review["attestation"])
    agent = review["attestation"]["reviewer_type"] == "agent" and review["attestation"]["confirmed"]
    if delegated:
        if review["attestation"]["reviewer_type"] != "agent":
            raise ValueError("Delegated review must remain explicitly agent-authored.")
        if agent and (
            review["attestation"]["reviewer_id"] != review["delegation"]["agent_reviewer_id"]
            or review["attestation"]["reviewed_at_utc"] < review["delegation"]["recorded_at_utc"]
        ):
            raise ValueError("Delegated reviewer mismatch or review predates delegation.")
    accepted_reviewer = operator or (delegated and agent)
    originals = {row["case_id"]: row for row in expected["cases"]}
    if type(review["cases"]) is not list or len(review["cases"]) != len(originals):
        raise ValueError("Review must cover exactly the declared curriculum cases.")
    by_id = {}
    for row in review["cases"]:
        _fields(row, ("case_id", "binding_sha256", "decision", "target_response", "checks", "note"))
        case_id = row["case_id"]
        if type(case_id) is not str or case_id not in originals or case_id in by_id:
            raise ValueError("Duplicate, unknown or non-curriculum review case.")
        if row["binding_sha256"] != originals[case_id]["binding_sha256"]:
            raise ValueError("Case evidence/target/facts binding mismatch.")
        if row["decision"] not in ("pending", "approve", "reject"):
            raise ValueError("Unknown review decision.")
        if row["target_response"] is not None and (
            type(row["target_response"]) is not str or len(row["target_response"]) > 2048
        ):
            raise ValueError("Target response must be null or a bounded string.")
        _fields(row["checks"], SEMANTIC_CHECKS)
        if any(v is not None and type(v) is not bool for v in row["checks"].values()):
            raise ValueError("Semantic checks must be explicit booleans or pending nulls.")
        if type(row["note"]) is not str or len(row["note"]) > 1024:
            raise ValueError("Review note must be a bounded string.")
        by_id[case_id] = row

    facts = {r["case_id"]: r for r in curriculum_review_packet(suite)["cases"]}
    rows, blockers, verdicts = [], [], set()
    for case in suite.cases:
        if case.split != "curriculum_draft":
            continue
        row, fact = by_id[case.case_id], facts[case.case_id]
        issues = []
        if row["decision"] == "pending":
            issues.append("pending_review")
        if row["decision"] in ("approve", "reject") and not row["note"].strip():
            issues.append("review_note_required")
        if row["decision"] == "approve":
            if not all(row["checks"][key] is True for key in SEMANTIC_CHECKS):
                issues.append("semantic_attestations_incomplete")
            if fact["numerical_assessment"]["status"] == "preflight_refused":
                issues.append("preflight_refused")
            elif fact["draft_verdict_agrees_with_numeric_check"] is not True:
                issues.append("draft_numeric_disagreement_requires_new_suite")
            try:
                target = parse_role_report(row["target_response"], "analyst", case.snapshot)
            except (ValueError, TypeError, RecursionError):
                issues.append("invalid_target_schema")
            else:
                if target.verdict != case.expected:
                    issues.append("target_verdict_changed")
                if not all(set(g) & set(target.evidence_ids) for g in case.citation_groups):
                    issues.append("missing_required_citations")
                if not issues:
                    verdicts.add(target.verdict)
        if issues:
            blockers.append("unresolved_case:" + case.case_id)
        rows.append(
            {
                "case_id": case.case_id,
                "decision": row["decision"],
                "issues": issues,
                "operator_approved": operator and row["decision"] == "approve" and not issues,
                "target_sha256": digest(row["target_response"]),
            }
        )
        if delegated:
            rows[-1]["agent_approved"] = agent and row["decision"] == "approve" and not issues
    if not accepted_reviewer:
        blockers.append(
            "delegated_agent_attestation_required" if delegated else "operator_attestation_required"
        )
    if verdicts != {"support", "veto"}:
        blockers.append("approved_support_and_veto_examples_required")
    report = {
        "schema_version": 1,
        "kind": "advisory_curriculum_review_audit_v1",
        "suite_sha256": suite.sha256,
        "review_sha256": digest(review),
        "cases": rows,
        "candidate_export_allowed": not blockers,
        "blockers": blockers,
        "operator_attestation_present": operator,
        "operator_identity_authenticated": False,
        "rationale_semantics_machine_verified": False,
        "training_allowed": False,
        "training_blockers": [
            "protected_final_evaluation_not_registered",
            "bounded_training_plan_and_environment_not_verified",
        ],
        "promotion_allowed": False,
        "execution_allowed": False,
        "model_calls": 0,
        "orders": 0,
    }
    if delegated:
        report.update(
            schema_version=2,
            kind="advisory_delegated_curriculum_review_audit_v2",
            review_basis="user_delegated_agent",
            delegation_sha256=digest(review["delegation"]),
            delegation_authenticated=False,
            agent_identity_authenticated=False,
            agent_attestation_present=agent,
            human_reviewed=False,
        )
    return report


def export_candidate(suite, review):
    """Only explicitly reviewed targets; this candidate is still NOT training authorization."""
    report = audit_review(suite, review)
    if not report["candidate_export_allowed"]:
        raise ValueError(
            "Curriculum review blocks candidate export: " + ", ".join(report["blockers"])
        )
    packet = curriculum_review_packet(suite)
    reviewed = {row["case_id"]: row for row in review["cases"]}
    result = {
        "schema_version": 1,
        "kind": CANDIDATE_KIND,
        "suite_sha256": suite.sha256,
        "review_sha256": digest(review),
        "packet_sha256": digest(packet),
        "review_contract": SPOT_LONG_V2,
        "system_prompt": SPOT_LONG_V2_PROMPT,
        "prompt_sha256": digest(SPOT_LONG_V2_PROMPT),
        "included_split": "curriculum_draft",
        "excluded_case_ids": [c.case_id for c in suite.cases if c.split != "curriculum_draft"],
        "rejected_case_ids": [r["case_id"] for r in report["cases"] if r["decision"] == "reject"],
        "examples": [
            {
                "case_id": row["case_id"],
                "family": row["family"],
                "source_session": row["source_session"],
                "input": row["input"],
                "input_sha256": digest(row["input"]),
                "target_response": reviewed[row["case_id"]]["target_response"],
                "target_sha256": digest(reviewed[row["case_id"]]["target_response"]),
            }
            for row in packet["cases"]
            if reviewed[row["case_id"]]["decision"] == "approve"
        ],
        "review_audit": report,
        "training_allowed": False,
        "promotion_allowed": False,
        "execution_allowed": False,
    }
    if review["kind"] == DELEGATED_REVIEW_KIND:
        result.update(
            schema_version=2,
            kind=DELEGATED_CANDIDATE_KIND,
            review_basis="user_delegated_agent",
            delegation_sha256=digest(review["delegation"]),
            human_reviewed=False,
        )
    _bounded_artifact(result)
    return result


def verify_candidate(suite, review, candidate):
    """Reproduce every field before trusting a saved candidate, not just self-reported hashes."""
    if _bounded_artifact(candidate) != canonical(export_candidate(suite, review)):
        raise ValueError("Candidate does not reproduce the pinned suite and review.")
    return candidate


def _write_new(path, value):
    encoded = _bounded_artifact(value)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("prepare", "prepare-delegated", "audit", "export", "verify")
    )
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument("--suite-sha256", required=True)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--review-sha256")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--candidate-sha256")
    parser.add_argument("--delegation", type=Path)
    parser.add_argument("--delegation-sha256")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    needs_review = args.action not in ("prepare", "prepare-delegated")
    if bool(args.review) != needs_review or bool(args.review_sha256) != needs_review:
        parser.error("Audit/export/verify require a review path and pin; prepare accepts neither.")
    needs_candidate = args.action == "verify"
    if bool(args.candidate) != needs_candidate or bool(args.candidate_sha256) != needs_candidate:
        parser.error("Only verify requires a candidate path and pin.")
    needs_delegation = args.action == "prepare-delegated"
    if (
        bool(args.delegation) != needs_delegation
        or bool(args.delegation_sha256) != needs_delegation
    ):
        parser.error("Only prepare-delegated requires a delegation path and raw SHA256 pin.")
    suite = load_suite(args.suite, args.suite_sha256)
    review = read_pinned(args.review, args.review_sha256) if needs_review else None
    if args.action == "prepare":
        report = prepare_review(suite)
    elif args.action == "prepare-delegated":
        report = prepare_delegated_review(
            suite, read_pinned(args.delegation, args.delegation_sha256)
        )
    elif args.action == "audit":
        report = audit_review(suite, review)
    elif args.action == "export":
        report = export_candidate(suite, review)
    else:
        verify_candidate(suite, review, read_pinned(args.candidate, args.candidate_sha256))
        report = {
            "kind": "advisory_candidate_verification_v1",
            "candidate_sha256": args.candidate_sha256,
            "review_sha256": args.review_sha256,
            "candidate_reproduced": True,
            "training_allowed": False,
            "promotion_allowed": False,
        }
    _write_new(args.output, report)
    print(
        canonical({"kind": report["kind"], "output": str(args.output), "training_allowed": False})
    )
    # Audit exit 2 means a valid but incomplete/rejected review, not a parse or model failure.
    return 2 if args.action == "audit" and not report["candidate_export_allowed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
