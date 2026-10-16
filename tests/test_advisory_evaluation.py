"""Synthetic curriculum and recorded-output scoring, with no model, network or training."""

import copy
import hashlib
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.models.local_reviewer import LocalReviewerConfig, build_request
from ai_trader.research import advisory_evaluation as evaluation

SUITE_PATH = Path(__file__).resolve().parents[1] / "configs" / "qwen_review_cases_v1.json"
SUITE_SHA = "5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659"


@pytest.fixture
def suite():
    return evaluation.load_suite(SUITE_PATH, SUITE_SHA)


def load_modified(tmp_path, change):
    data = json.loads(SUITE_PATH.read_text())
    change(data)
    raw = canonical(data).encode()
    path = tmp_path / "modified.json"
    path.write_bytes(raw)
    return evaluation.load_suite(path, hashlib.sha256(raw).hexdigest())


def fake_smoke(suite, tmp_path, raw=None):
    case = suite.cases[0]
    config = LocalReviewerConfig(
        case.source_session,
        backend="transformers",
        model_id="Qwen/Qwen3-4B-Base",
        checkpoint_path=tmp_path,
        checkpoint_sha256="a" * 64,
        device="cuda",
        max_calls=1,
    )
    request = build_request(config, "analyst", case.snapshot, ())
    return {
        "schema_version": 1,
        "kind": "synthetic_qwen_smoke",
        "generation_completed": True,
        "orders": 0,
        "training_started": False,
        "promotion_allowed": False,
        "configuration": request["configuration"],
        "request_sha256": digest(request),
        "prompt_sha256": request["prompt_sha256"],
        "raw_response": raw
        if raw is not None
        else canonical(
            {
                "verdict": "support",
                "evidence_ids": ["cvd", "imbalance", "cost"],
                "rationale": "Unsupported optimism in this synthetic regression.",
            }
        ),
    }


def test_reference_demo_cannot_claim_model_quality_or_training_approval(suite, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network/subprocess expected")

    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    report = evaluation.score_responses(suite, evaluation.reference_responses(suite))
    assert report["summary"]["case_count"] == 25
    assert report["summary"]["machine_checks_passed"] == 25
    assert report["summary"]["preflight_correct_count"] == 4
    assert report["summary"]["review_case_count"] == 21
    assert report["by_split"]["curriculum_draft"]["case_count"] == 14
    assert report["by_split"]["development_eval"]["case_count"] == 11
    assert report["producer"]["kind"] == "synthetic_reference"
    assert report["model_calls"] == report["orders"] == 0
    assert not report["training_export_allowed"] and not report["promotion_allowed"]
    assert all(r["rationale_quality"].startswith("not_assessed") for r in report["cases"])


def test_model_visible_inputs_exclude_targets_and_split_metadata(suite):
    for case in suite.cases:
        payload = evaluation.model_input(case)
        assert set(payload) == {"role", "symbol", "as_of_ms", "evidence", "prior"}
        assert payload["role"] == "analyst" and payload["prior"] == []
        if case.expected != "preflight_refusal":
            request = build_request(
                LocalReviewerConfig(case.source_session), "analyst", case.snapshot, ()
            )
            assert payload == request["input"]
            assert case.reference_rationale not in canonical(payload)
        assert case.family not in canonical(payload)
        assert case.case_id not in canonical(payload)


@pytest.mark.parametrize(
    "verdict,unsafe,recalls",
    [
        ("veto", 0, (0.0, 1.0)),
        ("support", 16, (1.0, 0.0)),
    ],
)
def test_constant_verdict_cannot_pass(suite, verdict, unsafe, recalls):
    data = evaluation.reference_responses(suite)
    for row in data["responses"]:
        if row["status"] == "completed":
            raw = json.loads(row["raw_response"])
            raw["verdict"] = verdict
            row["raw_response"] = canonical(raw)
    report = evaluation.score_responses(suite, data)
    summary = report["summary"]
    assert not summary["all_machine_checks_pass"]
    assert summary["balanced_verdict_accuracy"] == 0.5
    assert (summary["support_recall"], summary["veto_recall"]) == recalls
    assert summary["unsafe_support_count"] == unsafe


def test_missing_and_failed_cases_stay_in_denominators(suite):
    data = evaluation.reference_responses(suite)
    data["responses"] = [data["responses"][0]]
    data["responses"][0].update(status="failed", raw_response=None)
    report = evaluation.score_responses(suite, data)
    assert len(report["cases"]) == 25
    assert report["summary"]["missing_count"] == 24
    assert not report["summary"]["coverage_complete"]
    assert report["summary"]["balanced_verdict_accuracy"] == 0


@pytest.mark.parametrize(
    "raw",
    [
        "not JSON",
        "[]",
        "x" * 2049,
        "[" * 1500 + "]" * 1500,
        '{"verdict":"veto","evidence_ids":["invented"],"rationale":"x"}',
        '{"verdict":"veto","evidence_ids":["cvd"],"rationale":"x","order":"BUY"}',
        '{"verdict":"support","verdict":"veto","evidence_ids":["cvd"],"rationale":"x"}',
    ],
)
def test_invalid_schema_never_counts_as_correct_veto(suite, raw):
    data = evaluation.reference_responses(suite)
    data["responses"][0]["raw_response"] = raw
    row = evaluation.score_responses(suite, data)["cases"][0]
    assert row["status"] == "invalid_schema"
    assert not row["machine_checks_pass"] and not row["verdict_match"]


def test_correct_verdict_with_nondecisive_citation_fails(suite):
    data = evaluation.reference_responses(suite)
    data["responses"][0]["raw_response"] = canonical(
        {
            "verdict": "veto",
            "evidence_ids": ["cvd"],
            "rationale": "Does not cite costs.",
        }
    )
    row = evaluation.score_responses(suite, data)["cases"][0]
    assert row["schema_valid"] and row["verdict_match"]
    assert not row["citation_requirements_met"] and not row["machine_checks_pass"]


def test_incorrect_rationale_is_not_claimed_semantically_verified(suite):
    data = evaluation.reference_responses(suite)
    raw = json.loads(data["responses"][0]["raw_response"])
    raw["rationale"] = "This is deliberately nonsense."
    data["responses"][0]["raw_response"] = canonical(raw)
    row = evaluation.score_responses(suite, data)["cases"][0]
    assert row["machine_checks_pass"]  # Deliberately limited metric, not semantic grading.
    assert row["rationale_quality"] == "not_assessed_requires_operator_review"


def test_no_model_response_is_expected_for_bad_inputs(suite):
    data = evaluation.reference_responses(suite)
    index = next(i for i, c in enumerate(suite.cases) if c.expected == "preflight_refusal")
    data["responses"][index].update(status="completed", raw_response="{}")
    row = evaluation.score_responses(suite, data)["cases"][index]
    assert row["status"] == "preflight_failure" and row["schema_valid"] is None
    assert not row["machine_checks_pass"]


def test_input_binding_mismatch_is_retained_not_skipped(suite):
    data = evaluation.reference_responses(suite)
    data["responses"][0]["input_sha256"] = "0" * 64
    report = evaluation.score_responses(suite, data)
    assert report["cases"][0]["status"] == "input_binding_mismatch"
    assert report["summary"]["machine_checks_passed"] == 24


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(suite_sha256="0" * 64),
        lambda d: d.update(schema_version=True),
        lambda d: d["responses"].append(d["responses"][0]),
        lambda d: d["responses"].__setitem__(1, d["responses"][0]),
        lambda d: d["responses"][0].update(case_id="unknown"),
        lambda d: d["responses"][0].update(raw_response="x" * 8193),
        lambda d: d["responses"][0].update(status="failed"),
        lambda d: d["producer"].update(kind="live"),
        lambda d: d["producer"].update(model_id="Qwen/Qwen3-4B-Base"),
    ],
)
def test_invalid_response_envelope_is_refused(suite, change):
    data = evaluation.reference_responses(suite)
    change(data)
    with pytest.raises(ValueError):
        evaluation.score_responses(suite, data)


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(review_status="approved"),
        lambda d: d.update(schema_version=True),
        lambda d: d.update(cases=[]),
        lambda d: d["cases"][1].update(case_id=d["cases"][0]["case_id"]),
        lambda d: d["cases"][1].update(split="development_eval"),
        lambda d: d["cases"][3].update(source_session=d["cases"][0]["source_session"]),
        lambda d: d["cases"][0].update(expected="preflight_refusal"),
        lambda d: d["cases"][0].update(citation_groups=[["unknown"]]),
        lambda d: d["cases"][0].update(citation_groups=[]),
        lambda d: d["cases"][0]["evidence"][0].update(value="NaN"),
        lambda d: d["cases"][0]["evidence"][0].update(value=1),
        lambda d: d["cases"][0]["evidence"][0].update(available_time_ms=1001),
    ],
)
def test_invalid_curriculum_is_refused(tmp_path, change):
    with pytest.raises(ValueError):
        load_modified(tmp_path, change)


def test_exact_relabelled_content_cannot_cross_splits(tmp_path):
    def change(data):
        duplicate = copy.deepcopy(data["cases"][0])
        duplicate.update(
            case_id="renamed",
            family="different",
            split="development_eval",
            source_session="new-session",
        )
        for e in duplicate["evidence"]:
            e["source_session"] = "new-session"
            e["value"] += "0" if "." in e["value"] else ".0"
        data["cases"].append(duplicate)

    with pytest.raises(ValueError, match="Duplicate scenario content"):
        load_modified(tmp_path, change)


def test_decimal_identity_does_not_round_long_values():
    assert evaluation._decimal_key(Decimal("1.00")) == evaluation._decimal_key(Decimal("1"))
    assert evaluation._decimal_key(Decimal("-0")) == evaluation._decimal_key(Decimal("0"))
    assert evaluation._decimal_key(
        Decimal("1.00000000000000000000000000001")
    ) != evaluation._decimal_key(Decimal("1.00000000000000000000000000002"))


def test_byte_bound_pin_and_duplicate_json_keys(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="SHA256"):
        evaluation.load_suite(SUITE_PATH, "0" * 64)
    monkeypatch.setattr(evaluation, "MAX_FILE_BYTES", 10)
    with pytest.raises(ValueError, match="size"):
        evaluation.load_suite(SUITE_PATH, SUITE_SHA)
    monkeypatch.setattr(evaluation, "MAX_FILE_BYTES", 1024)
    path = tmp_path / "duplicate.json"
    raw = b'{"a":1,"a":2}'
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="Duplicate"):
        evaluation.read_pinned(path, hashlib.sha256(raw).hexdigest())


def test_saved_overconfident_smoke_can_fail_content_without_new_inference(suite, tmp_path):
    smoke = fake_smoke(suite, tmp_path)
    data = evaluation.recorded_smoke_responses(suite, smoke, "g001_a")
    report = evaluation.score_responses(suite, data)
    assert report["cases"][0]["schema_valid"]
    assert report["cases"][0]["unsafe_support"]
    assert not report["cases"][0]["machine_checks_pass"]
    assert report["summary"]["missing_count"] == 24
    assert report["model_calls"] == 0


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s.update(generation_completed=False),
        lambda s: s.update(orders=True),
        lambda s: s.update(training_started=True),
        lambda s: s.update(request_sha256="0" * 64),
        lambda s: s.update(prompt_sha256="0" * 64),
        lambda s: s["configuration"].update(source_session="wrong-session"),
        lambda s: s["configuration"].update(max_calls=2),
    ],
)
def test_smoke_import_preserves_original_bindings(suite, tmp_path, change):
    smoke = fake_smoke(suite, tmp_path)
    change(smoke)
    with pytest.raises(ValueError):
        evaluation.recorded_smoke_responses(suite, smoke, "g001_a")


def test_smoke_cannot_be_assigned_to_another_scenario(suite, tmp_path):
    with pytest.raises(ValueError, match="binding"):
        evaluation.recorded_smoke_responses(suite, fake_smoke(suite, tmp_path), "g001_b")


def test_api_keeps_caller_responses_unchanged(suite):
    data = evaluation.reference_responses(suite)
    before = copy.deepcopy(data)
    report = evaluation.score_responses(suite, data)
    report["producer"]["kind"] = "changed"
    assert data == before


def test_cli_demo_is_offline_and_exclusive(tmp_path):
    output = tmp_path / "report.json"
    command = [
        sys.executable,
        "-I",
        "-m",
        "ai_trader.research.advisory_evaluation",
        "--suite",
        str(SUITE_PATH),
        "--suite-sha256",
        SUITE_SHA,
        "--demo",
        "--output",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    data = json.loads(output.read_text())
    assert data["model_calls"] == 0 and data["producer"]["kind"] == "synthetic_reference"
    before = output.read_bytes()
    again = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert again.returncode != 0 and output.read_bytes() == before


def test_cli_partial_recording_retains_failure_report_and_returns_two(suite, tmp_path):
    data = evaluation.reference_responses(suite)
    data["producer"] = {
        "kind": "recorded",
        "model_id": "test-fixture",
        "checkpoint_sha256": "a" * 64,
        "prompt_sha256": "b" * 64,
    }
    data["responses"] = data["responses"][:1]
    raw = canonical(data).encode()
    responses = tmp_path / "responses.json"
    responses.write_bytes(raw)
    output = tmp_path / "partial.json"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "ai_trader.research.advisory_evaluation",
            "--suite",
            str(SUITE_PATH),
            "--suite-sha256",
            SUITE_SHA,
            "--responses",
            str(responses),
            "--artifact-sha256",
            hashlib.sha256(raw).hexdigest(),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2, result.stderr
    report = json.loads(output.read_text())
    assert report["summary"]["missing_count"] == 24
    assert not report["summary"]["all_machine_checks_pass"]
    assert report["source_artifact_sha256"] == hashlib.sha256(raw).hexdigest()
    assert report["model_calls"] == 0


def test_import_does_not_load_ml_or_training_modules():
    code = (
        "import sys; import ai_trader.research.advisory_evaluation; "
        "assert not {'torch','transformers','psutil'} & sys.modules.keys(); "
        "assert not any(m.startswith('ai_trader.training.') for m in sys.modules)"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
