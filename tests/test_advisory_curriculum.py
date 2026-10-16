"""Synthetic approvals exercise the workflow; they are not real operator attestations."""

import copy
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.models.review_contracts import SPOT_LONG_V2, SPOT_LONG_V2_PROMPT
from ai_trader.research.advisory_evaluation import load_suite, model_input
from ai_trader.research.advisory_fact_audit import curriculum_review_packet
from ai_trader.training import advisory_curriculum as curriculum

SUITE_PATH = Path(__file__).resolve().parents[1] / "configs" / "qwen_review_cases_v1.json"
SUITE_SHA = "5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659"


@pytest.fixture
def suite():
    return load_suite(SUITE_PATH, SUITE_SHA)


def approved(suite):
    review = curriculum.prepare_review(suite)
    review["attestation"].update(
        confirmed=True,
        reviewer_id="synthetic-test-operator",
        reviewed_at_utc="2026-09-24T12:00:00Z",
    )
    for row in review["cases"]:
        row.update(decision="approve", note="Synthetic test attestation only, not a real review.")
        row["checks"] = dict.fromkeys(curriculum.SEMANTIC_CHECKS, True)
    return review


def edit_response(review, index, **changes):
    target = json.loads(review["cases"][index]["target_response"])
    target.update(changes)
    review["cases"][index]["target_response"] = canonical(target)


def test_default_is_pending_bound_and_cannot_export(suite):
    review = curriculum.prepare_review(suite)
    before = copy.deepcopy(review)
    report = curriculum.audit_review(suite, review)
    assert review == before and len(review["cases"]) == 14
    assert review["packet_sha256"] == digest(curriculum_review_packet(suite))
    assert review["prompt_sha256"] == digest(SPOT_LONG_V2_PROMPT)
    assert not review["attestation"]["confirmed"]
    assert all(
        r["decision"] == "pending" and set(r["checks"].values()) == {None} for r in review["cases"]
    )
    assert not report["candidate_export_allowed"] and not report["training_allowed"]
    assert "operator_attestation_required" in report["blockers"]
    with pytest.raises(ValueError, match="blocks candidate"):
        curriculum.export_candidate(suite, review)


def test_synthetic_approval_exports_only_curriculum_inputs_and_targets(suite, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No worker/network allowed")

    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    review = approved(suite)
    before = copy.deepcopy(review)
    report = curriculum.audit_review(suite, review)
    assert report["candidate_export_allowed"]
    assert all(r["operator_approved"] for r in report["cases"])
    assert not report["operator_identity_authenticated"]
    assert not report["rationale_semantics_machine_verified"]
    assert not report["training_allowed"] and not report["promotion_allowed"]
    result = curriculum.export_candidate(suite, review)
    assert review == before
    assert curriculum.verify_candidate(suite, review, result) == result
    assert result["system_prompt"] == SPOT_LONG_V2_PROMPT
    assert len(result["examples"]) == 14 and len(result["excluded_case_ids"]) == 11
    dev = [c for c in suite.cases if c.split == "development_eval"]
    cases = {c.case_id: c for c in suite.cases}
    for row in result["examples"]:
        case = cases[row["case_id"]]
        assert case.split == "curriculum_draft"
        assert row["family"] not in {c.family for c in dev}
        assert row["source_session"] not in {c.source_session for c in dev}
        assert row["input"] == model_input(case, SPOT_LONG_V2)
        assert row["input_sha256"] == digest(row["input"])
        assert row["target_sha256"] == digest(row["target_response"])
        assert case.reference_rationale not in canonical(row["input"])
        assert "checks" not in row and "note" not in row and "expected" not in row["input"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("schema_version", 2),
        ("kind", "new-kind"),
        ("suite_sha256", "a" * 64),
        ("packet_sha256", "a" * 64),
        ("prompt_sha256", "a" * 64),
        ("review_contract", "legacy_v1"),
        ("check_version", "other"),
    ],
)
def test_envelope_drift_rejected(suite, field, value):
    review = approved(suite)
    review[field] = value
    with pytest.raises(ValueError, match="binding"):
        curriculum.audit_review(suite, review)


@pytest.mark.parametrize("change", ["extra", "missing", "duplicate", "development", "binding"])
def test_exact_case_coverage_and_binding(suite, change):
    review = approved(suite)
    if change == "extra":
        review["cases"].append(copy.deepcopy(review["cases"][0]))
    elif change == "missing":
        review["cases"].pop()
    elif change == "duplicate":
        review["cases"][1] = copy.deepcopy(review["cases"][0])
    elif change == "development":
        review["cases"][0]["case_id"] = "g005_a"
    else:
        review["cases"][0]["binding_sha256"] = "a" * 64
    with pytest.raises(ValueError):
        curriculum.audit_review(suite, review)


def test_reordering_cannot_change_export_selection(suite):
    review = approved(suite)
    original = curriculum.export_candidate(suite, review)
    review["cases"].reverse()
    assert curriculum.export_candidate(suite, review)["examples"] == original["examples"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("reviewer_type", "unknown"),
        ("confirmed", 1),
        ("reviewer_id", ""),
        ("reviewer_id", "x" * 129),
        ("reviewed_at_utc", "2026-09-24"),
        ("reviewed_at_utc", "2026-02-30T12:00:00Z"),
        ("reviewed_at_utc", None),
    ],
)
def test_malformed_attestation_rejected(suite, field, value):
    review = approved(suite)
    review["attestation"][field] = value
    with pytest.raises(ValueError):
        curriculum.audit_review(suite, review)


def test_unconfirmed_identity_cannot_look_attested(suite):
    review = approved(suite)
    review["attestation"]["confirmed"] = False
    with pytest.raises(ValueError, match="Unconfirmed"):
        curriculum.audit_review(suite, review)


def test_agent_attestation_does_not_substitute_for_operator(suite):
    review = approved(suite)
    review["attestation"]["reviewer_type"] = "agent"
    report = curriculum.audit_review(suite, review)
    assert not report["candidate_export_allowed"]
    assert all(not r["operator_approved"] for r in report["cases"])
    assert report["blockers"] == ["operator_attestation_required"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("decision", "approved"),
        ("target_response", {}),
        ("target_response", "x" * 2049),
        ("note", None),
        ("note", "x" * 1025),
    ],
)
def test_malformed_row_fields(suite, field, value):
    review = approved(suite)
    review["cases"][0][field] = value
    with pytest.raises(ValueError):
        curriculum.audit_review(suite, review)


@pytest.mark.parametrize("value", [False, None])
@pytest.mark.parametrize("check", curriculum.SEMANTIC_CHECKS)
def test_every_semantic_attestation_required(suite, check, value):
    review = approved(suite)
    review["cases"][0]["checks"][check] = value
    report = curriculum.audit_review(suite, review)
    assert not report["candidate_export_allowed"]
    assert "semantic_attestations_incomplete" in report["cases"][0]["issues"]


def test_bool_as_number_and_extra_fields_rejected(suite):
    review = approved(suite)
    review["cases"][0]["checks"][curriculum.SEMANTIC_CHECKS[0]] = 1
    with pytest.raises(ValueError, match="booleans"):
        curriculum.audit_review(suite, review)
    for path in ((), ("attestation",), ("cases", 0), ("cases", 0, "checks")):
        review = approved(suite)
        target = review
        for key in path:
            target = target[key]
        target["extra"] = True
        with pytest.raises(ValueError, match="fields"):
            curriculum.audit_review(suite, review)


@pytest.mark.parametrize("raw", [None, "{}", "not JSON", '{"verdict":"support"}'])
def test_schema_invalid_target_cannot_export(suite, raw):
    review = approved(suite)
    review["cases"][0]["target_response"] = raw
    assert "invalid_target_schema" in curriculum.audit_review(suite, review)["cases"][0]["issues"]
    with pytest.raises(ValueError, match="blocks candidate"):
        curriculum.export_candidate(suite, review)


def test_wrong_verdict_or_missing_required_citations_block(suite):
    review = approved(suite)
    edit_response(review, 0, verdict="support")
    assert "target_verdict_changed" in curriculum.audit_review(suite, review)["cases"][0]["issues"]
    edit_response(review, 0, verdict="veto", evidence_ids=["cvd"])
    assert (
        "missing_required_citations" in curriculum.audit_review(suite, review)["cases"][0]["issues"]
    )


def test_revised_rationale_preserves_frozen_original_and_changes_candidate_hash(suite):
    review = approved(suite)
    index = next(i for i, r in enumerate(review["cases"]) if r["case_id"] == "g002_c")
    original = curriculum.export_candidate(suite, review)
    revised = "The supplied baseline net is +5 bps, but stressed net is -1 bps. Veto."
    edit_response(review, index, rationale=revised)
    result = curriculum.export_candidate(suite, review)
    assert result["review_sha256"] != original["review_sha256"]
    assert revised in result["examples"][index]["target_response"]
    assert (
        "cost stress" in next(c for c in suite.cases if c.case_id == "g002_c").reference_rationale
    )


def test_semantic_attestation_is_not_a_prose_validator(suite):
    review = approved(suite)
    edit_response(review, 0, rationale="An intentionally false sentence for a limitations test.")
    report = curriculum.audit_review(suite, review)
    assert report["candidate_export_allowed"]  # Honest limitation: operator is a trust boundary.
    assert not report["rationale_semantics_machine_verified"]


def test_rejection_is_retained_and_pending_cannot_be_silently_dropped(suite):
    review = approved(suite)
    review["cases"][0].update(decision="reject", note="Synthetic rejection reason.")
    result = curriculum.export_candidate(suite, review)
    assert len(result["examples"]) == 13
    assert result["rejected_case_ids"] == ["g001_a"]
    review["cases"][0]["decision"] = "pending"
    with pytest.raises(ValueError, match="unresolved_case:g001_a"):
        curriculum.export_candidate(suite, review)
    review["cases"][0].update(decision="reject", note=" ")
    with pytest.raises(ValueError, match="unresolved_case:g001_a"):
        curriculum.export_candidate(suite, review)


def test_rejecting_a_class_or_every_case_cannot_export(suite):
    review = approved(suite)
    for row in review["cases"]:
        if json.loads(row["target_response"])["verdict"] == "support":
            row["decision"] = "reject"
    report = curriculum.audit_review(suite, review)
    assert "approved_support_and_veto_examples_required" in report["blockers"]
    for row in review["cases"]:
        row["decision"] = "reject"
    assert not curriculum.audit_review(suite, review)["candidate_export_allowed"]


def test_facts_disagreement_or_input_refusal_cannot_be_attested_away(suite):
    wrong = replace(suite, cases=(replace(suite.cases[0], expected="support"), *suite.cases[1:]))
    review = approved(wrong)
    report = curriculum.audit_review(wrong, review)
    assert "draft_numeric_disagreement_requires_new_suite" in report["cases"][0]["issues"]
    refused = next(c for c in suite.cases if c.expected == "preflight_refusal")
    isolated = replace(suite, cases=(replace(refused, split="curriculum_draft"),))
    report = curriculum.audit_review(isolated, approved(isolated))
    assert "preflight_refused" in report["cases"][0]["issues"]
    assert not report["candidate_export_allowed"]


def test_changed_evidence_invalidates_old_review(suite):
    review = approved(suite)
    first = suite.cases[0]
    changed = replace(first, snapshot=replace(first.snapshot, as_of_ms=first.snapshot.as_of_ms + 1))
    with pytest.raises(ValueError, match="binding"):
        curriculum.audit_review(replace(suite, cases=(changed, *suite.cases[1:])), review)


@pytest.mark.parametrize("change", ["training", "input", "target", "drop", "metadata", "prompt"])
def test_candidate_reconstruction_rejects_tampering(suite, change):
    review = approved(suite)
    candidate = curriculum.export_candidate(suite, review)
    if change == "training":
        candidate["training_allowed"] = True
    elif change == "input":
        candidate["examples"][0]["input"]["expected"] = "veto"
        candidate["examples"][0]["input_sha256"] = digest(candidate["examples"][0]["input"])
    elif change == "target":
        candidate["examples"][0]["target_response"] = "{}"
        candidate["examples"][0]["target_sha256"] = digest("{}")
    elif change == "drop":
        candidate["examples"].pop()
    elif change == "metadata":
        candidate["examples"][0]["family"] = "development"
    else:
        candidate["system_prompt"] = "Different instructions"
        candidate["prompt_sha256"] = digest(candidate["system_prompt"])
    with pytest.raises(ValueError, match="reproduce"):
        curriculum.verify_candidate(suite, review, candidate)


def test_artifact_budget_and_empty_curriculum(suite, monkeypatch):
    review = approved(suite)
    monkeypatch.setattr(curriculum, "MAX_ARTIFACT_BYTES", 1)
    with pytest.raises(ValueError, match="budget"):
        curriculum.audit_review(suite, review)
    dev_only = replace(suite, cases=tuple(c for c in suite.cases if c.split == "development_eval"))
    with pytest.raises(ValueError, match="nonempty"):
        curriculum.prepare_review(dev_only)


def cli_args(action, output):
    return [
        "curriculum",
        action,
        "--suite",
        str(SUITE_PATH),
        "--suite-sha256",
        SUITE_SHA,
        "--output",
        str(output),
    ]


def write_fixture(path, data):
    raw = canonical(data).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_cli_lifecycle_with_synthetic_test_approval(suite, tmp_path, monkeypatch):
    template = tmp_path / "pending.json"
    monkeypatch.setattr(sys, "argv", cli_args("prepare", template))
    assert curriculum.main() == 0
    template_pin = hashlib.sha256(template.read_bytes()).hexdigest()
    status = tmp_path / "status.json"
    args = cli_args("audit", status) + ["--review", str(template), "--review-sha256", template_pin]
    monkeypatch.setattr(sys, "argv", args)
    assert curriculum.main() == 2
    assert not json.loads(status.read_text())["candidate_export_allowed"]
    reviewed = tmp_path / "synthetic-approved.json"
    pin = write_fixture(reviewed, approved(suite))
    candidate = tmp_path / "candidate.json"
    monkeypatch.setattr(
        sys,
        "argv",
        cli_args("export", candidate)
        + [
            "--review",
            str(reviewed),
            "--review-sha256",
            pin,
        ],
    )
    assert curriculum.main() == 0
    candidate_pin = hashlib.sha256(candidate.read_bytes()).hexdigest()
    verified = tmp_path / "verified.json"
    monkeypatch.setattr(
        sys,
        "argv",
        cli_args("verify", verified)
        + [
            "--review",
            str(reviewed),
            "--review-sha256",
            pin,
            "--candidate",
            str(candidate),
            "--candidate-sha256",
            candidate_pin,
        ],
    )
    assert curriculum.main() == 0
    assert json.loads(verified.read_text())["candidate_reproduced"]
    with pytest.raises(FileExistsError):
        curriculum.main()


@pytest.mark.parametrize(
    "action,extra",
    [
        ("prepare", ["--review", "x"]),
        ("audit", []),
        ("export", ["--review", "x"]),
        ("verify", ["--review", "x", "--review-sha256", "a" * 64]),
        ("prepare", ["--candidate", "x"]),
    ],
)
def test_cli_requires_exact_mode_pins(tmp_path, monkeypatch, action, extra):
    output = tmp_path / "output.json"
    monkeypatch.setattr(sys, "argv", cli_args(action, output) + extra)
    with pytest.raises(SystemExit):
        curriculum.main()
    assert not output.exists()


def test_cli_drift_or_pending_export_leaves_no_file(suite, tmp_path, monkeypatch):
    review_path = tmp_path / "pending.json"
    pin = write_fixture(review_path, curriculum.prepare_review(suite))
    output = tmp_path / "candidate.json"
    args = cli_args("export", output) + ["--review", str(review_path), "--review-sha256", pin]
    monkeypatch.setattr(sys, "argv", args)
    with pytest.raises(ValueError, match="blocks candidate"):
        curriculum.main()
    assert not output.exists()
    args[-1] = "a" * 64
    with pytest.raises(ValueError, match="SHA256"):
        curriculum.main()
    assert not output.exists()
