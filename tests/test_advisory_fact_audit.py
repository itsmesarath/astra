"""Numerical results never rewrite model scores or authorize draft training material."""

import copy
import hashlib
import json
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from ai_trader.models.local_checkpoint import canonical
from ai_trader.models.review_contracts import LEGACY_V1, SPOT_LONG_V2
from ai_trader.research import advisory_evaluation as evaluation
from ai_trader.research import advisory_fact_audit as audit

SUITE_PATH = Path(__file__).resolve().parents[1] / "configs" / "qwen_review_cases_v1.json"
SUITE_SHA = "5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659"


@pytest.fixture
def suite():
    return evaluation.load_suite(SUITE_PATH, SUITE_SHA)


@pytest.mark.parametrize("contract", [LEGACY_V1, SPOT_LONG_V2])
def test_no_score_or_raw_output_mutation(suite, contract, monkeypatch):
    data = evaluation.reference_responses(suite, contract)
    before = copy.deepcopy(data)

    def forbidden(*args, **kwargs):
        raise AssertionError("Offline reports cannot launch workers or connect")

    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    report = audit.audit_recorded_responses(suite, data)
    assert data == before
    assert report["model_score"] == evaluation.score_responses(suite, data)
    assert Counter(r["numerical_assessment"]["status"] for r in report["numerical_checks"]) == {
        "conditional_support": 5,
        "veto": 16,
        "preflight_refused": 4,
    }
    assert report["combined_pass_or_promotion_metric"] is None
    assert report["rationale_semantics_verified"] is False
    assert report["model_calls"] == report["orders"] == 0
    assert not report["execution_allowed"] and not report["training_export_allowed"]
    assert not report["promotion_allowed"]


def test_constant_support_conflicts_stay_model_failures(suite):
    data = evaluation.reference_responses(suite)
    for row in data["responses"]:
        if row["status"] == "completed":
            raw = json.loads(row["raw_response"])
            raw["verdict"] = "support"
            row["raw_response"] = canonical(raw)
    report = audit.audit_recorded_responses(suite, data)
    assert report["model_support_conflict_count"] == 16
    assert report["model_score"]["summary"]["unsafe_support_count"] == 16


@pytest.mark.parametrize("state", ["missing", "failed", "invalid", "misbound"])
def test_invalid_or_unavailable_outputs_not_compared(suite, state):
    data = evaluation.reference_responses(suite)
    if state == "missing":
        data["responses"].pop(0)
    elif state == "failed":
        data["responses"][0].update(status="failed", raw_response=None)
    elif state == "invalid":
        data["responses"][0]["raw_response"] = "not JSON"
    else:
        data["responses"][0]["input_sha256"] = "a" * 64
    report = audit.audit_recorded_responses(suite, data)
    assert report["numerical_checks"][0]["comparison"] == "not_comparable"
    assert not report["model_score"]["cases"][0]["machine_checks_pass"]


def test_false_arithmetic_in_prose_remains_ungraded_and_unchanged(suite):
    data = evaluation.reference_responses(suite)
    index = next(i for i, c in enumerate(suite.cases) if c.case_id == "g006_a")
    raw = json.loads(data["responses"][index]["raw_response"])
    raw["rationale"] = "30 exceeds 35 and net is -5."
    data["responses"][index]["raw_response"] = canonical(raw)
    report = audit.audit_recorded_responses(suite, data)
    facts = report["numerical_checks"][index]["numerical_assessment"]
    assert facts["computed_net_bps"] == "5" and facts["costs_exceed_gross"] is False
    assert facts["reasons"] == ["nonpositive_stress"]
    scored = report["model_score"]["cases"][index]
    assert scored["raw_response"] == canonical(raw)
    assert scored["machine_checks_pass"] and scored["rationale_quality"].startswith("not_assessed")
    assert not report["rationale_semantics_verified"]


def test_valid_model_veto_not_overridden_by_numeric_support(suite):
    data = evaluation.reference_responses(suite)
    index = next(i for i, c in enumerate(suite.cases) if c.expected == "support")
    raw = json.loads(data["responses"][index]["raw_response"])
    raw["verdict"] = "veto"
    data["responses"][index]["raw_response"] = canonical(raw)
    report = audit.audit_recorded_responses(suite, data)
    assert (
        report["numerical_checks"][index]["comparison"] == "model_veto_despite_positive_estimates"
    )
    assert report["model_score"]["cases"][index]["observed_verdict"] == "veto"
    assert not report["model_score"]["cases"][index]["verdict_match"]


def test_labels_do_not_drive_numeric_assessment(suite):
    changed = replace(suite, cases=(replace(suite.cases[0], expected="support"), *suite.cases[1:]))
    data = evaluation.reference_responses(suite)
    original = audit.audit_recorded_responses(suite, data)
    modified = audit.audit_recorded_responses(changed, data)
    assert original["numerical_checks"] == modified["numerical_checks"]
    assert original["model_score"] != modified["model_score"]
    packet = audit.curriculum_review_packet(changed)
    assert packet["cases"][0]["draft_verdict_agrees_with_numeric_check"] is False
    assert json.loads(packet["cases"][0]["draft_reference_response"])["verdict"] == "support"
    assert packet["cases"][0]["operator_review"] == "pending"


def test_curriculum_is_separated_and_pending_not_exportable(suite):
    report = audit.curriculum_review_packet(suite)
    expected = [c for c in suite.cases if c.split == "curriculum_draft"]
    dev = [c for c in suite.cases if c.split == "development_eval"]
    assert report["case_count"] == 14 and report["excluded_case_count"] == 11
    for row, case in zip(report["cases"], expected, strict=True):
        assert row["case_id"] == case.case_id
        assert row["family"] not in {c.family for c in dev}
        assert row["source_session"] not in {c.source_session for c in dev}
        assert row["input"] == evaluation.model_input(case, SPOT_LONG_V2)
        assert row["draft_reference_response"] == evaluation.reference_response(case)
        assert row["draft_citation_groups"] == case.citation_groups
        assert row["operator_review"] == "pending" and row["training_eligible"] is False
        assert row["draft_verdict_agrees_with_numeric_check"] is True
    assert not report["training_export_allowed"] and not report["promotion_allowed"]


def test_future_curriculum_refusal_remains_visible_without_target(suite):
    bad = next(c for c in suite.cases if c.expected == "preflight_refusal")
    isolated = replace(suite, cases=(replace(bad, split="curriculum_draft"),))
    row = audit.curriculum_review_packet(isolated)["cases"][0]
    assert row["numerical_assessment"]["status"] == "preflight_refused"
    assert row["draft_reference_response"] is None
    assert row["draft_verdict_agrees_with_numeric_check"] is None
    assert row["training_eligible"] is False


def cli_args(tmp_path):
    return [
        "fact-audit",
        "--suite",
        str(SUITE_PATH),
        "--suite-sha256",
        SUITE_SHA,
        "--output",
        str(tmp_path / "report.json"),
    ]


@pytest.mark.parametrize("mode", ["curriculum", "responses"])
def test_cli_pinned_local_artifacts_and_no_overwrite(suite, tmp_path, monkeypatch, mode):
    args = cli_args(tmp_path)
    if mode == "curriculum":
        args += ["--curriculum-review"]
    else:
        raw = canonical(evaluation.reference_responses(suite)).encode()
        path = tmp_path / "responses.json"
        path.write_bytes(raw)
        args += ["--responses", str(path), "--artifact-sha256", hashlib.sha256(raw).hexdigest()]
    monkeypatch.setattr(sys, "argv", args)
    assert audit.main() == 0
    output = tmp_path / "report.json"
    before = output.read_bytes()
    report = json.loads(before)
    assert report["model_calls"] == 0 and not report["training_export_allowed"]
    if mode == "responses":
        assert report["source_artifact_sha256"] == hashlib.sha256(raw).hexdigest()
    with pytest.raises(FileExistsError):
        audit.main()
    assert output.read_bytes() == before


@pytest.mark.parametrize(
    "extra",
    [
        ["--responses", "missing.json"],
        ["--curriculum-review", "--artifact-sha256", "a" * 64],
        ["--curriculum-review", "--responses", "missing.json"],
    ],
)
def test_cli_rejects_missing_or_conflicting_recording_pins(tmp_path, monkeypatch, extra):
    monkeypatch.setattr(sys, "argv", cli_args(tmp_path) + extra)
    with pytest.raises(SystemExit):
        audit.main()
    assert not (tmp_path / "report.json").exists()


def test_cli_hash_mismatch_cannot_create_output(tmp_path, monkeypatch):
    args = cli_args(tmp_path) + ["--curriculum-review"]
    args[args.index("--suite-sha256") + 1] = "a" * 64
    monkeypatch.setattr(sys, "argv", args)
    with pytest.raises(ValueError, match="SHA256"):
        audit.main()
    assert not (tmp_path / "report.json").exists()
