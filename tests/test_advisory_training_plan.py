"""Synthetic metadata reservations and fake tokenization never certify actual final evaluation."""

import copy
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_trader.models.local_checkpoint import canonical
from ai_trader.models.review_contracts import SPOT_LONG_V2, SPOT_LONG_V2_PROMPT, base_review_prompt
from ai_trader.research.advisory_evaluation import load_suite, model_input, scenario_fingerprint
from ai_trader.training import advisory_curriculum as curriculum
from ai_trader.training import advisory_holdout as holdout
from ai_trader.training import advisory_training_plan as plan

SUITE_PATH = Path(__file__).resolve().parents[1] / "configs" / "qwen_review_cases_v1.json"
SUITE_SHA = "5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659"


@pytest.fixture
def suite():
    return load_suite(SUITE_PATH, SUITE_SHA)


def declared_reservation(suite):
    registry = holdout.reservation_template(suite)
    registry.update(dataset_sha256="b" * 64, unexposed_attested=True)
    registry["attestation"].update(
        confirmed=True, reviewer_id="synthetic-custodian", reviewed_at_utc="2026-09-24T12:00:00Z"
    )
    registry["cases"] = [
        {
            "case_id": "reserved-test",
            "family": "reserved-family",
            "source_session": "reserved-session",
            "input_sha256": "c" * 64,
            "scenario_sha256": "d" * 64,
        }
    ]
    return registry


def approved_review(suite):
    review = curriculum.prepare_review(suite)
    review["attestation"].update(
        confirmed=True, reviewer_id="synthetic-operator", reviewed_at_utc="2026-09-24T12:00:00Z"
    )
    for row in review["cases"]:
        row.update(decision="approve", note="Synthetic fixture only.")
        row["checks"] = dict.fromkeys(curriculum.SEMANTIC_CHECKS, True)
    return review


def fake_encode(text):
    return [1 + i % 50 for i in range(max(1, len(text) // 8))]


def prepared(suite, review=None, registry=None, encode=fake_encode):
    return plan.prepare_training_plan(
        suite,
        review or curriculum.prepare_review(suite),
        registry or holdout.reservation_template(suite),
        encode=encode,
        tokenizer_sha256="a" * 64 if encode else None,
        eos_token_id=90 if encode else None,
        pad_token_id=90 if encode else None,
    )


def test_pending_reservation_is_not_a_holdout(suite):
    registry = holdout.reservation_template(suite)
    result = holdout.audit_reservation(suite, registry)
    assert registry["cases"] == [] and registry["dataset_sha256"] is None
    assert result["exposed_case_count"] == 25
    assert not result["reservation_complete"] and len(result["blockers"]) == 3
    assert not result["heldout_contents_opened"] and not result["heldout_contents_verified"]


def test_metadata_reservation_never_opens_targets_or_authenticates_truth(suite, monkeypatch):
    registry = declared_reservation(suite)

    def forbidden(*args, **kwargs):
        raise AssertionError("The registry cannot read held-out files or contact a provider")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    report = holdout.audit_reservation(suite, registry)
    assert report["reservation_complete"] and report["declared_metadata_disjoint"]
    assert report["protected_case_count"] == 1
    assert all(
        report[key] is False
        for key in (
            "heldout_contents_opened",
            "heldout_contents_verified",
            "independence_authenticated",
            "near_duplicates_checked",
            "training_allowed",
            "promotion_allowed",
        )
    )


@pytest.mark.parametrize("key", holdout.INDEX_FIELDS)
@pytest.mark.parametrize("source_index", [0, 10, 24])
def test_overlap_with_any_exposed_partition_refused(suite, key, source_index):
    registry = declared_reservation(suite)
    registry["cases"][0][key] = holdout.exposure_inventory(suite)[source_index][key]
    with pytest.raises(ValueError, match="overlaps exposed"):
        holdout.audit_reservation(suite, registry)


def test_normalized_fingerprint_survives_identifier_and_time_changes(suite):
    snap = suite.cases[0].snapshot
    changed = replace(
        snap,
        as_of_ms=snap.as_of_ms + 10000,
        evidence=tuple(
            replace(
                e,
                evidence_id="new-" + e.evidence_id,
                source_session="new-session",
                value=Decimal(str(e.value) + "0")
                if "." in str(e.value)
                else Decimal(str(e.value) + ".0"),
                event_time_ms=e.event_time_ms + 10000,
                available_time_ms=e.available_time_ms + 10000,
            )
            for e in reversed(snap.evidence)
        ),
    )
    assert scenario_fingerprint(changed) == scenario_fingerprint(snap)
    registry = declared_reservation(suite)
    registry["cases"][0]["scenario_sha256"] = scenario_fingerprint(changed)
    with pytest.raises(ValueError, match="scenario_sha256"):
        holdout.audit_reservation(suite, registry)


@pytest.mark.parametrize("key", ["case_id", "input_sha256", "scenario_sha256"])
def test_duplicate_protected_metadata_refused(suite, key):
    registry = declared_reservation(suite)
    row = copy.deepcopy(registry["cases"][0])
    row.update(case_id="second", input_sha256="e" * 64, scenario_sha256="f" * 64)
    row[key] = registry["cases"][0][key]
    registry["cases"].append(row)
    with pytest.raises(ValueError, match="Duplicate protected"):
        holdout.audit_reservation(suite, registry)


def test_whole_protected_sessions_cannot_cross_families(suite):
    registry = declared_reservation(suite)
    row = {
        **registry["cases"][0],
        "case_id": "second",
        "family": "different",
        "input_sha256": "e" * 64,
        "scenario_sha256": "f" * 64,
    }
    registry["cases"].append(row)
    with pytest.raises(ValueError, match="crosses families"):
        holdout.audit_reservation(suite, registry)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("kind", "other"),
        ("review_contract", "legacy_v1"),
        ("exposed_suite_sha256", "a" * 64),
        ("exposure_inventory_sha256", "a" * 64),
        ("fingerprint_version", "other"),
        ("dataset_sha256", SUITE_SHA),
        ("dataset_sha256", "bad"),
        ("unexposed_attested", 1),
        ("cases", {}),
    ],
)
def test_registry_shape_and_drift(suite, field, value):
    registry = declared_reservation(suite)
    registry[field] = value
    with pytest.raises(ValueError):
        holdout.audit_reservation(suite, registry)


@pytest.mark.parametrize("key", ["path", "payload", "target_response", "expected"])
def test_registry_rejects_payloads_paths_and_labels(suite, key):
    registry = declared_reservation(suite)
    registry["cases"][0][key] = "must-not-be-opened"
    with pytest.raises(ValueError, match="fields"):
        holdout.audit_reservation(suite, registry)


def test_agent_or_missing_unexposed_attestation_is_not_complete(suite):
    registry = declared_reservation(suite)
    registry["attestation"]["reviewer_type"] = "agent"
    assert not holdout.audit_reservation(suite, registry)["reservation_complete"]
    registry["attestation"]["reviewer_type"] = "operator"
    registry["unexposed_attested"] = False
    assert not holdout.audit_reservation(suite, registry)["reservation_complete"]


@pytest.mark.parametrize("same_pad", [True, False])
def test_loss_mask_is_unshifted_and_preserves_eos(same_pad):
    padding_id = 90 if same_pad else 91
    prompt, answer = [1, 2], [3, 4]
    result = plan.completion_only_record(prompt, answer, eos_token_id=90, pad_token_id=padding_id)
    assert prompt == [1, 2] and answer == [3, 4]
    assert result["input_ids"][:6] == [1, 2, 3, 4, 90, padding_id]
    assert result["labels"][:6] == [-100, -100, 3, 4, 90, -100]
    assert result["attention_mask"][:6] == [1, 1, 1, 1, 1, 0]
    assert set(result["labels"][5:]) == {-100}
    assert set(result["attention_mask"][5:]) == {0}
    assert {len(v) for v in result.values()} == {2304}


def test_exact_maximum_and_one_more_token_refused():
    result = plan.completion_only_record([1] * 2048, [2] * 255, eos_token_id=90, pad_token_id=90)
    assert len(result["input_ids"]) == 2304 and result["labels"][-1] == 90
    assert set(result["attention_mask"]) == {1}
    for prompt, answer in (([1] * 2049, [2]), ([1], [2] * 256)):
        with pytest.raises(ValueError, match="no truncation"):
            plan.completion_only_record(prompt, answer, eos_token_id=90, pad_token_id=90)


@pytest.mark.parametrize(
    "prompt,answer",
    [
        ([], [1]),
        ([1], []),
        ("x", [1]),
        ([1], "x"),
        ([True], [1]),
        ([1], [1.0]),
        ([-1], [1]),
        ([1], [1_000_000]),
        ([90], [1]),
        ([1], [91]),
    ],
)
def test_invalid_ids_or_embedded_special_tokens_refused(prompt, answer):
    with pytest.raises(ValueError):
        plan.completion_only_record(prompt, answer, eos_token_id=90, pad_token_id=91)


@pytest.mark.parametrize("value", [True, -1, None, "90", 1_000_000])
def test_special_id_validation(value):
    with pytest.raises(ValueError):
        plan.completion_only_record([1], [2], eos_token_id=value, pad_token_id=90)


def test_prompt_helper_preserves_frozen_inference_bytes(suite):
    payload = model_input(suite.cases[0], SPOT_LONG_V2)
    assert base_review_prompt(SPOT_LONG_V2_PROMPT, payload) == (
        SPOT_LONG_V2_PROMPT + "\nEvidence JSON:\n" + canonical(payload) + "\nReview JSON:\n"
    )


def test_preflight_keeps_pending_drafts_and_training_blockers(suite):
    review = curriculum.prepare_review(suite)
    before = copy.deepcopy(review)
    report = prepared(suite, review)
    assert review == before and len(report["proposal_checks"]) == 14
    assert all(r["status"] == "tokenized_proposal" for r in report["proposal_checks"])
    assert "curriculum_review_incomplete" in report["blockers"]
    assert "protected_evaluation_reservation_incomplete" in report["blockers"]
    assert report["optimization_steps"] == report["model_calls"] == report["orders"] == 0
    assert not report["training_allowed"] and not report["weights_loaded"]
    assert not report["recipe"]["limits_enforced_by_training_worker"]
    for row in report["proposal_checks"]:
        assert set(row) == {
            "case_id",
            "decision",
            "input_sha256",
            "target_sha256",
            "status",
            "prompt_tokens",
            "completion_tokens",
            "supervised_tokens",
            "record_sha256",
        }
        assert row["supervised_tokens"] == row["completion_tokens"] + 1
    assert report == prepared(suite, review)


def test_even_synthetic_approvals_do_not_authorize_training(suite):
    report = prepared(suite, approved_review(suite), declared_reservation(suite))
    assert report["blockers"] == [
        "optimization_worker_not_implemented",
        "training_environment_not_verified",
    ]
    assert not report["training_allowed"] and not report["execution_allowed"]


def test_no_tokenizer_import_needed_for_static_plan(suite, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Static preflight cannot invoke a model or tokenizer")

    monkeypatch.setattr(plan, "load_tokenizer", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    report = prepared(suite, encode=None)
    assert "tokenizer_preflight_not_run" in report["blockers"]
    assert all(r["status"] == "tokenizer_not_run" for r in report["proposal_checks"])


def test_prompt_and_response_encoded_separately_without_labels_in_prompt(suite):
    calls = []

    def encode(text):
        calls.append(text)
        return [1, 2]

    review = curriculum.prepare_review(suite)
    prepared(suite, review, encode=encode)
    assert len(calls) == 28
    cases = {c.case_id: c for c in suite.cases}
    for i, row in enumerate(review["cases"]):
        case = cases[row["case_id"]]
        assert calls[2 * i] == base_review_prompt(
            SPOT_LONG_V2_PROMPT, model_input(case, SPOT_LONG_V2)
        )
        assert calls[2 * i + 1] == row["target_response"]
        assert case.reference_rationale not in calls[2 * i]


def test_bad_draft_targets_are_refused_before_tokenizer(suite):
    review = curriculum.prepare_review(suite)
    review["cases"][0]["target_response"] = "{}"
    result = prepared(suite, review)
    assert result["proposal_checks"][0]["status"] == "proposal_refused"
    assert (
        len(result["proposal_checks"]) == 14 and "proposal_preflight_failed" in result["blockers"]
    )
    target = json.loads(review["cases"][1]["target_response"])
    target["verdict"] = "support"
    review["cases"][1]["target_response"] = canonical(target)
    assert prepared(suite, review)["proposal_checks"][1]["status"] == "proposal_refused"


def test_rejected_cases_accounted_for_not_tokenized(suite):
    review = curriculum.prepare_review(suite)
    review["cases"][0].update(decision="reject", note="Test rejection.", target_response=None)
    assert prepared(suite, review)["proposal_checks"][0]["status"] == "excluded_rejection"


def test_oversized_encoding_refuses_without_truncation(suite):
    report = prepared(suite, encode=lambda text: [1] * 2049)
    assert all(r["status"] == "tokenization_refused" for r in report["proposal_checks"])
    assert "proposal_preflight_failed" in report["blockers"]


def test_tokenizer_metadata_is_required_and_cannot_fake_static_verification(suite):
    review, registry = curriculum.prepare_review(suite), holdout.reservation_template(suite)
    with pytest.raises(ValueError):
        plan.prepare_training_plan(suite, review, registry, encode=fake_encode)
    with pytest.raises(ValueError, match="without tokenization"):
        plan.prepare_training_plan(suite, review, registry, tokenizer_sha256="a" * 64)


def test_local_tokenizer_only_reads_pinned_bytes_and_disables_truncation(tmp_path, monkeypatch):
    path = tmp_path / "tokenizer.json"
    path.write_text("{}", encoding="utf-8")
    calls = []

    class FakeTokenizer:
        @staticmethod
        def from_str(raw):
            calls.append(raw)
            return FakeTokenizer()

        def no_truncation(self):
            calls.append("no_truncation")

        def no_padding(self):
            calls.append("no_padding")

        def encode(self, text, *, add_special_tokens):
            assert not add_special_tokens
            calls.append(text)
            return SimpleNamespace(ids=[1, 2])

    monkeypatch.setitem(sys.modules, "tokenizers", SimpleNamespace(Tokenizer=FakeTokenizer))
    pin = hashlib.sha256(path.read_bytes()).hexdigest()
    encode = plan.load_tokenizer(path, pin)
    assert encode("hello") == [1, 2]
    assert calls == ["{}", "no_truncation", "no_padding", "hello"]
    with pytest.raises(ValueError, match="SHA256"):
        plan.load_tokenizer(path, "a" * 64)
    with pytest.raises(ValueError, match="regular"):
        plan.load_tokenizer(tmp_path, pin)


def write_fixture(path, data):
    raw = canonical(data).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def cli_args(action, output):
    return [
        "training-plan",
        action,
        "--suite",
        str(SUITE_PATH),
        "--suite-sha256",
        SUITE_SHA,
        "--output",
        str(output),
    ]


def test_cli_templates_and_dry_plan_use_pinned_inputs_and_exclusive_outputs(
    suite, tmp_path, monkeypatch
):
    registry_path = tmp_path / "registry.json"
    monkeypatch.setattr(sys, "argv", cli_args("reserve-template", registry_path))
    assert plan.main() == 0
    registry_pin = hashlib.sha256(registry_path.read_bytes()).hexdigest()
    review_path = tmp_path / "review.json"
    review_pin = write_fixture(review_path, curriculum.prepare_review(suite))
    output = tmp_path / "plan.json"
    monkeypatch.setattr(
        sys,
        "argv",
        cli_args("prepare", output)
        + [
            "--review",
            str(review_path),
            "--review-sha256",
            review_pin,
            "--registry",
            str(registry_path),
            "--registry-sha256",
            registry_pin,
        ],
    )
    assert plan.main() == 0
    assert not json.loads(output.read_text())["training_allowed"]
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        plan.main()
    assert output.read_bytes() == before


@pytest.mark.parametrize(
    "action,extra",
    [
        ("prepare", []),
        ("reserve-template", ["--review", "x"]),
        ("reserve-template", ["--tokenizer-json", "x"]),
        ("prepare", ["--review", "x", "--review-sha256", "a" * 64]),
    ],
)
def test_cli_requires_mode_specific_pins(tmp_path, monkeypatch, action, extra):
    output = tmp_path / "plan.json"
    monkeypatch.setattr(sys, "argv", cli_args(action, output) + extra)
    with pytest.raises(SystemExit):
        plan.main()
    assert not output.exists()
