"""Versioned contract and replay checks without any real model invocation."""

import copy
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from ai_trader.models import _local_review_worker as worker
from ai_trader.models import local_reviewer as local
from ai_trader.models import qwen_smoke
from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.models.review_contracts import (
    LEGACY_V1,
    SPOT_LONG_V2,
    SPOT_LONG_V2_PROMPT,
    review_task,
)
from ai_trader.research import advisory_evaluation as evaluation
from ai_trader.research import advisory_runner as runner

SUITE_PATH = Path(__file__).resolve().parents[1] / "configs" / "qwen_review_cases_v1.json"
SUITE_SHA = "5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659"
V1_PROMPT_SHA = "463834a90c2bce8bc10d45321858d8bd4804fadf7c5712f64221a7a26cd89662"


@pytest.fixture
def suite():
    return evaluation.load_suite(SUITE_PATH, SUITE_SHA)


def batch_config(tmp_path, contract=SPOT_LONG_V2):
    return local.LocalReviewerConfig(
        runner.TEMPLATE_SESSION,
        backend="transformers",
        model_id="Qwen/Qwen3-4B-Base",
        checkpoint_path=tmp_path,
        checkpoint_sha256="a" * 64,
        device="cuda",
        max_calls=1,
        timeout_ms=120000,
        reply_ttl_ms=120000,
        review_contract=contract,
    )


def test_legacy_request_wire_contract_is_unchanged(suite):
    case = suite.cases[0]
    config = local.LocalReviewerConfig(case.source_session)
    assert config.review_contract == LEGACY_V1
    expected = {
        "protocol_version": "local_advisory_reviewer_v1",
        "configuration": {
            "source_session": case.source_session,
            "backend": "stub",
            "model_id": "synthetic-veto",
            "checkpoint_path": None,
            "checkpoint_sha256": None,
            "python_executable": sys.executable,
            "device": "cpu",
            "max_input_tokens": 2048,
            "max_new_tokens": 256,
            "timeout_ms": 60000,
            "reply_ttl_ms": 60000,
            "maximum_evidence_age_ms": 300000,
            "max_calls": 2,
        },
        "system_prompt": local.SYSTEM_PROMPT,
        "prompt_sha256": V1_PROMPT_SHA,
        "input": evaluation.model_input(case),
    }
    actual = local.build_request(config, "analyst", case.snapshot, ())
    assert canonical(actual) == canonical(expected)
    assert digest(local.SYSTEM_PROMPT) == V1_PROMPT_SHA
    assert digest(evaluation.model_input(suite.cases[10])) == (
        "393acf1c7f0877bd5b9be6a550c5f4351c942adaddedfe98044b2bd3e6c0875c"
    )
    assert "review_contract" not in actual["configuration"]
    assert "review_task" not in actual["input"]
    decoded, rebuilt = worker.decode_request(canonical(actual).encode())
    assert decoded.review_contract == LEGACY_V1 and rebuilt == actual


@pytest.mark.parametrize("value", [None, True, 1, "v2", "", [], {"contract": SPOT_LONG_V2}])
def test_unknown_contract_cannot_fall_back_to_legacy(value):
    with pytest.raises(ValueError, match="contract"):
        local.LocalReviewerConfig("synthetic", review_contract=value)
    with pytest.raises(ValueError, match="contract"):
        review_task(value)


def test_v2_inputs_use_fixed_question_without_case_labels(suite):
    for case in suite.cases:
        config = local.LocalReviewerConfig(case.source_session, review_contract=SPOT_LONG_V2)
        if case.expected == "preflight_refusal":
            with pytest.raises(local.LocalReviewError):
                local.build_request(config, "analyst", case.snapshot, ())
            continue
        request = local.build_request(config, "analyst", case.snapshot, ())
        assert request["input"] == evaluation.model_input(case, SPOT_LONG_V2)
        assert request["input"]["review_task"] == review_task(SPOT_LONG_V2)
        assert request["configuration"]["review_contract"] == SPOT_LONG_V2
        assert request["protocol_version"] == "local_advisory_reviewer_v2"
        assert request["system_prompt"] == SPOT_LONG_V2_PROMPT
        assert request["prompt_sha256"] == (
            "303e86702ea20f5f44de3920533a1f45466023211c44476f9ee353b79b15c7ea"
        )
        assert request["prompt_sha256"] != V1_PROMPT_SHA
        assert case.case_id not in canonical(request)
        assert case.family not in canonical(request)
        assert case.reference_rationale not in canonical(request)
        assert "citation_groups" not in canonical(request)
        decoded, rebuilt = worker.decode_request(canonical(request).encode())
        assert decoded.review_contract == SPOT_LONG_V2 and rebuilt == request


def test_static_task_is_not_mutable_shared_state():
    task = review_task(SPOT_LONG_V2)
    task["hypothesis"] = "BUY regardless of evidence"
    assert review_task(SPOT_LONG_V2)["hypothesis"] != task["hypothesis"]


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["input"]["review_task"].update(hypothesis="Support bearish trades"),
        lambda r: r["input"].pop("review_task"),
        lambda r: r["input"]["review_task"].update(expected="support"),
        lambda r: r["configuration"].pop("review_contract"),
        lambda r: r.update(protocol_version="local_advisory_reviewer_v1"),
        lambda r: r.update(system_prompt=local.SYSTEM_PROMPT),
        lambda r: r.update(prompt_sha256=V1_PROMPT_SHA),
    ],
)
def test_worker_refuses_mixed_or_tampered_contracts(suite, change):
    case = suite.cases[0]
    request = local.build_request(
        local.LocalReviewerConfig(case.source_session, review_contract=SPOT_LONG_V2),
        "analyst",
        case.snapshot,
        (),
    )
    change(request)
    with pytest.raises(ValueError, match="contract"):
        worker.decode_request(canonical(request).encode())


def test_v2_local_reviewer_audit_binds_actual_prompt(suite, monkeypatch):
    case = suite.cases[0]

    def exchange(command, request, timeout):
        assert request["system_prompt"] == SPOT_LONG_V2_PROMPT
        return canonical(
            {"request_sha256": digest(request), "raw_response": evaluation.reference_response(case)}
        )

    monkeypatch.setattr(local, "_exchange", exchange)
    reviewer = local.LocalReviewer(
        local.LocalReviewerConfig(case.source_session, review_contract=SPOT_LONG_V2),
        enable_local_inference=True,
    )
    reviewer.review("analyst", case.snapshot, ())
    assert reviewer.audit[0]["prompt_sha256"] == digest(SPOT_LONG_V2_PROMPT)
    assert reviewer.audit[0]["orders"] == 0


def test_legacy_smoke_cannot_silently_switch_to_v2(tmp_path):
    config = replace(batch_config(tmp_path), source_session="synthetic-qwen-smoke")
    with pytest.raises(ValueError, match="single-call"):
        qwen_smoke.run_smoke(config, enable_local_inference=True)


def test_v1_and_v2_reference_demos_preserve_targets_not_input_bindings(suite):
    old = evaluation.reference_responses(suite)
    new = evaluation.reference_responses(suite, SPOT_LONG_V2)
    assert old["schema_version"] == 1 and "review_contract" not in old
    assert new["schema_version"] == 2 and new["review_contract"] == SPOT_LONG_V2
    for before, after in zip(old["responses"], new["responses"], strict=True):
        assert before["input_sha256"] != after["input_sha256"]
        assert before["raw_response"] == after["raw_response"]
    score = evaluation.score_responses(suite, new)
    assert score["schema_version"] == 2 and score["review_contract"] == SPOT_LONG_V2
    assert score["summary"]["machine_checks_passed"] == 25
    assert not score["training_export_allowed"] and not score["promotion_allowed"]


@pytest.mark.parametrize("target_contract", [LEGACY_V1, SPOT_LONG_V2])
def test_cross_version_rows_cannot_pass_input_bindings(suite, target_contract):
    other = SPOT_LONG_V2 if target_contract == LEGACY_V1 else LEGACY_V1
    data = evaluation.reference_responses(suite, target_contract)
    data["responses"] = evaluation.reference_responses(suite, other)["responses"]
    score = evaluation.score_responses(suite, data)
    assert score["summary"]["machine_checks_passed"] == 0
    assert all(r["status"] == "input_binding_mismatch" for r in score["cases"])


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(schema_version=True),
        lambda d: d.pop("review_contract"),
        lambda d: d.update(review_contract=LEGACY_V1),
        lambda d: d.update(schema_version=1),
        lambda d: d["producer"].update(prompt_sha256=V1_PROMPT_SHA),
    ],
)
def test_v2_recording_requires_matching_contract_and_prompt(suite, change):
    data = evaluation.reference_responses(suite, SPOT_LONG_V2)
    data["producer"] = {
        "kind": "recorded",
        "model_id": "Qwen/Qwen3-4B-Base",
        "checkpoint_sha256": "a" * 64,
        "prompt_sha256": digest(SPOT_LONG_V2_PROMPT),
    }
    change(data)
    with pytest.raises(ValueError):
        evaluation.score_responses(suite, data)


def test_v2_batch_keeps_limits_targets_and_recording_contract(suite, tmp_path, monkeypatch):
    legacy = runner.prepare_plan(suite, batch_config(tmp_path, LEGACY_V1))
    plan = runner.prepare_plan(suite, batch_config(tmp_path))
    assert plan["maximum_model_calls"] == legacy["maximum_model_calls"] == 7
    assert plan["maximum_worker_wait_ms"] == legacy["maximum_worker_wait_ms"] == 840000
    assert plan["suite_sha256"] == legacy["suite_sha256"] == SUITE_SHA
    assert plan["prompt_sha256"] == digest(SPOT_LONG_V2_PROMPT)
    assert plan["configuration_template"]["review_contract"] == SPOT_LONG_V2
    assert "review_contract" not in legacy["configuration_template"]
    assert [e["case_id"] for e in plan["cases"]] == [e["case_id"] for e in legacy["cases"]]
    cases = {digest(evaluation.model_input(c, SPOT_LONG_V2)): c for c in suite.cases}
    calls = []

    def exchange(command, request, timeout):
        calls.append(request)
        case = cases[digest(request["input"])]
        assert request["system_prompt"] == SPOT_LONG_V2_PROMPT
        return canonical(
            {"request_sha256": digest(request), "raw_response": evaluation.reference_response(case)}
        )

    monkeypatch.setattr(runner, "_exchange", exchange)
    before = copy.deepcopy(plan)
    output = tmp_path / "run"
    result = runner.run_plan(suite, plan, output, enable_local_inference=True)
    assert before == plan and len(calls) == 7
    assert result["schema_version"] == 2 and result["review_contract"] == SPOT_LONG_V2
    assert result["development_summary"]["machine_checks_passed"] == 11
    recorded = json.loads((output / "responses.json").read_text())
    assert recorded["schema_version"] == 2 and recorded["review_contract"] == SPOT_LONG_V2
    assert (
        evaluation.score_responses(suite, recorded)["by_split"][runner.SPLIT]
        == (result["development_summary"])
    )


def test_v1_plan_cannot_be_upgraded_just_by_editing_configuration(suite, tmp_path, monkeypatch):
    plan = runner.prepare_plan(suite, batch_config(tmp_path, LEGACY_V1))
    plan["configuration_template"]["review_contract"] = SPOT_LONG_V2

    def forbidden(*args):
        raise AssertionError("Drift reached worker")

    monkeypatch.setattr(runner, "_exchange", forbidden)
    with pytest.raises(ValueError, match="Frozen plan"):
        runner.run_plan(suite, plan, tmp_path / "run", enable_local_inference=True)
    assert not (tmp_path / "run").exists()
