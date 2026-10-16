"""Synthetic delegated-review policy tests; never real user/operator attestations."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.research.advisory_evaluation import load_suite
from ai_trader.training import advisory_curriculum as curriculum
from ai_trader.training import advisory_holdout as holdout
from ai_trader.training import advisory_training_run as run

SUITE = Path(__file__).resolve().parents[1] / "configs/qwen_review_cases_v1.json"
SUITE_SHA = "5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659"


@pytest.fixture
def suite():
    return load_suite(SUITE, SUITE_SHA)


@pytest.fixture
def delegation(suite):
    return {
        "schema_version": 1,
        "kind": "user_delegated_curriculum_review_v1",
        "suite_sha256": suite.sha256,
        "authorization_source": "user_message",
        "user_instruction": "Synthetic delegation fixture, not a real user instruction.",
        "recorded_at_utc": "2026-09-24T10:00:00Z",
        "agent_reviewer_id": "synthetic-agent",
        "review_scope": "curriculum_targets_only",
        "manual_review_required": False,
        "training_allowed": False,
        "execution_allowed": False,
    }


def resolved(suite, delegation):
    review = curriculum.prepare_delegated_review(suite, delegation)
    review["attestation"].update(
        confirmed=True,
        reviewer_id="synthetic-agent",
        reviewed_at_utc="2026-09-24T12:00:00Z",
    )
    for row in review["cases"]:
        row.update(decision="approve", note="Synthetic AI review fixture only.")
        row["checks"] = dict.fromkeys(curriculum.SEMANTIC_CHECKS, True)
    return review


def test_delegation_does_not_fill_decisions(suite, delegation):
    original = copy.deepcopy(delegation)
    review = curriculum.prepare_delegated_review(suite, delegation)
    assert delegation == original
    assert review["schema_version"] == 2
    assert review["attestation"]["reviewer_type"] == "agent"
    assert review["attestation"]["confirmed"] is False
    assert all(row["decision"] == "pending" and row["note"] == "" for row in review["cases"])
    assert all(set(row["checks"].values()) == {None} for row in review["cases"])
    audit = curriculum.audit_review(suite, review)
    assert not audit["candidate_export_allowed"]
    assert "delegated_agent_attestation_required" in audit["blockers"]
    assert "operator_attestation_required" not in audit["blockers"]


def test_resolved_agent_candidate_never_claims_human_approval(suite, delegation, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network, worker, or training allowed")

    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    review = resolved(suite, delegation)
    before = copy.deepcopy(review)
    audit = curriculum.audit_review(suite, review)
    assert audit["candidate_export_allowed"] is True
    assert audit["review_basis"] == "user_delegated_agent"
    assert audit["agent_attestation_present"] is True
    for key in (
        "human_reviewed",
        "operator_attestation_present",
        "delegation_authenticated",
        "agent_identity_authenticated",
        "rationale_semantics_machine_verified",
    ):
        assert audit[key] is False
    assert all(row["agent_approved"] and not row["operator_approved"] for row in audit["cases"])
    candidate = curriculum.export_candidate(suite, review)
    assert candidate["kind"] == curriculum.DELEGATED_CANDIDATE_KIND
    assert candidate["schema_version"] == 2 and candidate["human_reviewed"] is False
    assert candidate["delegation_sha256"] == digest(delegation)
    assert len(candidate["examples"]) == 14 and len(candidate["excluded_case_ids"]) == 11
    assert curriculum.verify_candidate(suite, review, candidate) == candidate
    assert review == before
    for key in ("training_allowed", "promotion_allowed", "execution_allowed"):
        assert candidate[key] is False and audit[key] is False


def test_legacy_agent_record_is_not_implicitly_promoted(suite, delegation):
    review = resolved(suite, delegation)
    review.pop("delegation")
    review.update(kind=curriculum.REVIEW_KIND, schema_version=1)
    audit = curriculum.audit_review(suite, review)
    assert audit["kind"] == "advisory_curriculum_review_audit_v1"
    assert "operator_attestation_required" in audit["blockers"]
    assert not audit["candidate_export_allowed"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("kind", "other"),
        ("suite_sha256", "0" * 64),
        ("authorization_source", "webpage"),
        ("user_instruction", " "),
        ("user_instruction", "x" * 1025),
        ("user_instruction", 1),
        ("review_scope", "live_trading"),
        ("manual_review_required", 0),
        ("training_allowed", True),
        ("execution_allowed", True),
        ("agent_reviewer_id", "bad id"),
        ("recorded_at_utc", "2026-02-30T10:00:00Z"),
        ("recorded_at_utc", "2026-09-24"),
    ],
)
def test_delegation_scope_and_types_are_strict(suite, delegation, field, value):
    delegation[field] = value
    with pytest.raises(ValueError):
        curriculum.prepare_delegated_review(suite, delegation)


@pytest.mark.parametrize("change", ["missing", "extra", "operator", "wrong-agent", "predates"])
def test_review_must_have_scoped_agent_provenance(suite, delegation, change):
    review = resolved(suite, delegation)
    if change == "missing":
        review.pop("delegation")
    elif change == "extra":
        review["delegation"]["approval_override"] = True
    elif change == "operator":
        review["attestation"]["reviewer_type"] = "operator"
    elif change == "wrong-agent":
        review["attestation"]["reviewer_id"] = "another-agent"
    else:
        review["attestation"]["reviewed_at_utc"] = "2026-09-24T09:00:00Z"
    with pytest.raises(ValueError):
        curriculum.audit_review(suite, review)


@pytest.mark.parametrize("change", ["pending", "note", "check", "verdict", "citations", "schema"])
def test_delegation_does_not_bypass_case_checks(suite, delegation, change):
    review = resolved(suite, delegation)
    row = review["cases"][0]
    if change == "pending":
        row["decision"] = "pending"
    elif change == "note":
        row["note"] = ""
    elif change == "check":
        row["checks"]["rationale_supported"] = None
    else:
        target = json.loads(row["target_response"])
        if change == "verdict":
            target["verdict"] = "support"
        elif change == "citations":
            target["evidence_ids"] = ["cvd"]
        else:
            target["extra"] = True
        row["target_response"] = canonical(target)
    with pytest.raises(ValueError, match="blocks candidate"):
        curriculum.export_candidate(suite, review)


def test_rejections_and_class_coverage_remain_accounted_for(suite, delegation):
    review = resolved(suite, delegation)
    review["cases"][0]["decision"] = "reject"
    candidate = curriculum.export_candidate(suite, review)
    assert candidate["rejected_case_ids"] == ["g001_a"]
    for row in review["cases"]:
        row["decision"] = "reject"
    audit = curriculum.audit_review(suite, review)
    assert "approved_support_and_veto_examples_required" in audit["blockers"]
    assert audit["agent_attestation_present"] and not audit["candidate_export_allowed"]


@pytest.mark.parametrize(
    "key,value",
    [
        ("human_reviewed", True),
        ("review_basis", "operator"),
        ("delegation_sha256", "0" * 64),
        ("execution_allowed", True),
    ],
)
def test_candidate_provenance_cannot_be_relabelled(suite, delegation, key, value):
    review = resolved(suite, delegation)
    candidate = curriculum.export_candidate(suite, review)
    candidate[key] = value
    with pytest.raises(ValueError, match="reproduce"):
        curriculum.verify_candidate(suite, review, candidate)


def write_fixture(path, value):
    raw = value.encode() if type(value) is str else canonical(value).encode()
    path.write_bytes(raw)
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest()}


def test_prepare_cli_requires_pinned_delegation(tmp_path, suite, delegation, monkeypatch):
    item = write_fixture(tmp_path / "delegation.json", delegation)
    output = tmp_path / "pending.json"
    base = [
        "curriculum",
        "prepare-delegated",
        "--suite",
        str(SUITE),
        "--suite-sha256",
        SUITE_SHA,
        "--output",
        str(output),
    ]
    monkeypatch.setattr(sys, "argv", base)
    with pytest.raises(SystemExit):
        curriculum.main()
    assert not output.exists()
    monkeypatch.setattr(
        sys, "argv", base + ["--delegation", item["path"], "--delegation-sha256", "0" * 64]
    )
    with pytest.raises(ValueError):
        curriculum.main()
    assert not output.exists()
    monkeypatch.setattr(
        sys, "argv", base + ["--delegation", item["path"], "--delegation-sha256", item["sha256"]]
    )
    assert curriculum.main() == 0
    assert json.loads(output.read_text())["attestation"]["confirmed"] is False
    with pytest.raises(FileExistsError):
        curriculum.main()


def test_delegated_candidate_still_needs_reservation_and_explicit_training_enable(
    suite,
    delegation,
    tmp_path,
    monkeypatch,
):
    review = resolved(suite, delegation)
    candidate = curriculum.export_candidate(suite, review)
    registry = holdout.reservation_template(suite)
    runtime = {**run.runtime_manifest(), "packages": dict.fromkeys(run.PACKAGES, "1.0")}
    inputs = {
        "suite": {"path": str(SUITE), "sha256": SUITE_SHA},
        "review": write_fixture(tmp_path / "review.json", review),
        "candidate": write_fixture(tmp_path / "candidate.json", candidate),
        "registry": write_fixture(tmp_path / "registry.json", registry),
        "runtime": write_fixture(tmp_path / "runtime.json", runtime),
        "dependency_lock": write_fixture(
            tmp_path / "lock.txt",
            "\n".join(name + "==1.0 --hash=sha256:" + "a" * 64 for name in run.PACKAGES),
        ),
    }
    base = tmp_path / "base"
    base.mkdir()
    args = (inputs, str(base), "e" * 64, "f" * 64, str(tmp_path / "output"))
    with pytest.raises(ValueError, match="reservation"):
        run.prepare_run(*args)
    # Explicitly synthetic custodian metadata, never an actual protected dataset.
    registry.update(dataset_sha256="b" * 64, unexposed_attested=True)
    registry["attestation"].update(
        confirmed=True,
        reviewer_id="synthetic-custodian",
        reviewed_at_utc="2026-09-24T12:00:00Z",
    )
    registry["cases"] = [
        {
            "case_id": "unseen",
            "family": "unseen",
            "source_session": "unseen",
            "input_sha256": "c" * 64,
            "scenario_sha256": "d" * 64,
        }
    ]
    inputs["registry"] = write_fixture(tmp_path / "registry.json", registry)
    plan = run.prepare_run(*args)
    assert plan["candidate_sha256"] == digest(candidate)
    assert plan["recipe"]["max_optimizer_steps"] == 20
    assert not plan["execution_allowed"] and not plan["promotion_allowed"]
    monkeypatch.setattr(run, "_exchange", lambda *args: pytest.fail("No real worker allowed"))
    with pytest.raises(ValueError, match="Explicit"):
        run.run(plan)
    assert not Path(plan["output_dir"]).exists()
