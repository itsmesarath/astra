"""The batch runner is tested with fake transports, never installed Qwen weights."""

import copy
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.models.local_reviewer import LocalReviewerConfig, LocalReviewError
from ai_trader.research import advisory_runner as runner
from ai_trader.research.advisory_evaluation import load_suite, model_input, reference_response

SUITE_PATH = Path(__file__).resolve().parents[1] / "configs" / "qwen_review_cases_v1.json"
SUITE_SHA = "5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659"


@pytest.fixture
def prepared(tmp_path):
    suite = load_suite(SUITE_PATH, SUITE_SHA)
    config = LocalReviewerConfig(
        runner.TEMPLATE_SESSION,
        backend="transformers",
        model_id="Qwen/Qwen3-4B-Base",
        checkpoint_path=tmp_path,
        checkpoint_sha256="a" * 64,
        device="cuda",
        timeout_ms=120000,
        reply_ttl_ms=120000,
        max_calls=1,
    )
    return suite, config, runner.prepare_plan(suite, config)


def fake_transport(monkeypatch, suite, *, fail_at=None, error=None, raw_first=None, output=None):
    calls = []
    cases = {digest(model_input(c)): c for c in suite.cases}

    def exchange(command, request, timeout):
        calls.append((command, request, timeout))
        case = cases[digest(request["input"])]
        if output is not None:
            assert (output / "plan.json").is_file()
            events = [
                json.loads(line) for line in (output / "events.jsonl").read_text().splitlines()
            ]
            assert events[-1]["event"] == "case_started"
            assert events[-1]["case_id"] == case.case_id
        if len(calls) == fail_at:
            raise error
        raw = raw_first if raw_first is not None and len(calls) == 1 else reference_response(case)
        return canonical({"request_sha256": digest(request), "raw_response": raw})

    monkeypatch.setattr(runner, "_exchange", exchange)
    return calls


def test_preparation_is_offline_no_model_or_checkpoint_loading(prepared, monkeypatch):
    suite, config, plan = prepared

    def forbidden(*args, **kwargs):
        raise AssertionError("No worker/network/checkpoint loading expected")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr("ai_trader.models.local_checkpoint.inspect_checkpoint", forbidden)
    assert runner.prepare_plan(suite, config) == plan
    assert len(plan["cases"]) == 11
    assert plan["maximum_model_calls"] == 7
    assert plan["maximum_worker_wait_ms"] == 840000
    assert sum(c["preflight_refusal"] is not None for c in plan["cases"]) == 4
    assert not plan["training_allowed"] and not plan["promotion_allowed"]
    assert plan["orders"] == 0


def test_full_fake_batch_has_seven_calls_four_refusals_and_no_target_leakage(
    prepared, tmp_path, monkeypatch
):
    suite, _, plan = prepared
    output = tmp_path / "run"
    calls = fake_transport(monkeypatch, suite, output=output)
    result = runner.run_plan(suite, plan, output, enable_local_inference=True)
    assert len(calls) == result["worker_attempts"] == 7
    assert result["status"] == "all_selected_cases_attempted"
    assert result["development_summary"]["machine_checks_passed"] == 11
    assert result["development_summary"]["preflight_correct_count"] == 4
    assert result["orders"] == 0 and not result["training_started"]
    assert not result["promotion_allowed"]
    for command, request, timeout in calls:
        assert command == [sys.executable, "-I", "-m", runner.WORKER]
        assert timeout == 120000
        assert request["configuration"]["max_calls"] == 1
        assert set(request["input"]) == {"role", "symbol", "as_of_ms", "evidence", "prior"}
        assert request["input"]["role"] == "analyst" and request["input"]["prior"] == []
        for case in suite.cases:
            assert case.case_id not in canonical(request)
            assert case.family not in canonical(request)
            if case.reference_rationale:
                assert case.reference_rationale not in canonical(request)
    score = json.loads((output / "score.json").read_text())
    assert score["summary"]["missing_count"] == 14  # Curriculum is intentionally NOT evaluated.
    assert score["by_split"]["development_eval"]["all_machine_checks_pass"]
    assert not score["summary"]["all_machine_checks_pass"]
    assert score["model_calls"] == 0  # Scorer only; run.json separately reports dispatch attempts.
    assert len(json.loads((output / "responses.json").read_text())["responses"]) == 11
    assert len((output / "events.jsonl").read_text().splitlines()) == 24


@pytest.mark.parametrize("enabled", [False, None, "true", 1])
def test_opt_in_is_strict(prepared, tmp_path, monkeypatch, enabled):
    suite, _, plan = prepared
    calls = fake_transport(monkeypatch, suite)
    output = tmp_path / "run"
    with pytest.raises(ValueError, match="opt-in"):
        runner.run_plan(suite, plan, output, enable_local_inference=enabled)
    assert not calls and not output.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"source_session": "actual-session"},
        {"device": "cpu"},
        {"model_id": "Qwen/Qwen3-4B"},
        {"max_calls": 2},
        {"max_new_tokens": 512},
        {"max_input_tokens": 1024},
        {"timeout_ms": 60000},
        {"reply_ttl_ms": 60000},
        {"maximum_evidence_age_ms": 1000},
    ],
)
def test_configuration_cannot_expand_or_silently_change_profile(prepared, changes):
    suite, config, _ = prepared
    with pytest.raises(ValueError, match="profile"):
        runner.prepare_plan(suite, replace(config, **changes))


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(maximum_model_calls=8),
        lambda p: p.update(maximum_worker_wait_ms=960000),
        lambda p: p.update(prompt_sha256="b" * 64),
        lambda p: p.update(suite_sha256="b" * 64),
        lambda p: p.update(split="curriculum_draft"),
        lambda p: p.update(worker_module="other.module"),
        lambda p: p.update(schema_version=True),
        lambda p: p["cases"].reverse(),
        lambda p: p["cases"][0].update(input_sha256="b" * 64),
        lambda p: p["cases"][0].update(request_sha256="b" * 64),
        lambda p: p["cases"][0].update(preflight_refusal="skip"),
    ],
)
def test_frozen_plan_drift_refused_before_artifacts_or_dispatch(
    prepared, tmp_path, monkeypatch, change
):
    suite, _, plan = prepared
    calls = fake_transport(monkeypatch, suite)
    change(plan)
    output = tmp_path / "run"
    with pytest.raises(ValueError, match="Frozen plan"):
        runner.run_plan(suite, plan, output, enable_local_inference=True)
    assert not calls and not output.exists()


def test_suite_case_and_call_caps(prepared):
    suite, config, _ = prepared
    with pytest.raises(ValueError, match="case budget"):
        runner.prepare_plan(
            replace(suite, cases=tuple(replace(c, split=runner.SPLIT) for c in suite.cases)),
            config,
        )
    with pytest.raises(ValueError, match="Model-call budget"):
        runner.prepare_plan(
            replace(
                suite,
                cases=tuple(
                    replace(c, split=runner.SPLIT) if c.family == "flow_without_edge" else c
                    for c in suite.cases
                ),
            ),
            config,
        )
    with pytest.raises(ValueError, match="empty selection"):
        runner.prepare_plan(
            replace(suite, cases=tuple(c for c in suite.cases if c.split != runner.SPLIT)), config
        )


@pytest.mark.parametrize("raw", ["not JSON", "", "[]", "{}", "```json\n{}\n```"])
def test_bad_report_is_preserved_and_does_not_retry_or_skip_other_cases(
    prepared, tmp_path, monkeypatch, raw
):
    suite, _, plan = prepared
    output = tmp_path / "run"
    calls = fake_transport(monkeypatch, suite, raw_first=raw)
    result = runner.run_plan(suite, plan, output, enable_local_inference=True)
    rows = json.loads((output / "responses.json").read_text())["responses"]
    assert len(calls) == 7 and rows[0]["raw_response"] == raw
    assert rows[0]["status"] == "completed"
    assert result["development_summary"]["schema_valid_count"] == 6
    assert not result["development_summary"]["all_machine_checks_pass"]


@pytest.mark.parametrize(
    "error,reason",
    [
        (LocalReviewError("worker_deadline"), "worker_deadline"),
        (LocalReviewError("worker_failed"), "worker_failed"),
        (LocalReviewError("worker_output_or_pipe_limit"), "worker_output_or_pipe_limit"),
        (LocalReviewError("sensitive provider details"), "worker_or_protocol_failure"),
        (RuntimeError("sensitive provider details"), "worker_or_protocol_failure"),
    ],
)
def test_infrastructure_failure_stops_batch_without_retry(
    prepared, tmp_path, monkeypatch, error, reason
):
    suite, _, plan = prepared
    output = tmp_path / "run"
    calls = fake_transport(monkeypatch, suite, fail_at=1, error=error)
    result = runner.run_plan(suite, plan, output, enable_local_inference=True)
    assert len(calls) == 1 and result["status"] == "stopped_after_worker_failure"
    assert result["development_summary"]["missing_count"] == 10
    events = (output / "events.jsonl").read_text()
    assert reason in events and "sensitive provider details" not in events
    assert json.loads((output / "responses.json").read_text())["responses"][0] == {
        "case_id": plan["cases"][0]["case_id"],
        "input_sha256": plan["cases"][0]["input_sha256"],
        "status": "failed",
        "raw_response": None,
    }


@pytest.mark.parametrize(
    "response",
    [
        "not JSON",
        "[]",
        '{"request_sha256":"wrong","raw_response":"{}"}',
        canonical({"request_sha256": "a" * 64, "raw_response": "x" * 2049}),
    ],
)
def test_bad_protocol_is_not_completed_generation(prepared, tmp_path, monkeypatch, response):
    suite, _, plan = prepared
    calls = []

    def exchange(*args):
        calls.append(args)
        return response

    monkeypatch.setattr(runner, "_exchange", exchange)
    result = runner.run_plan(suite, plan, tmp_path / "run", enable_local_inference=True)
    assert len(calls) == 1
    assert result["status"] == "stopped_after_worker_failure"
    assert result["development_summary"]["schema_valid_count"] == 0


def test_expired_reply_never_becomes_a_scored_response(prepared, monkeypatch):
    suite, config, _ = prepared
    fake_transport(monkeypatch, suite)
    request = runner._prepare(suite, config)[1][0]
    times = iter([0.0, 120.0, 120.0])
    monkeypatch.setattr(runner, "time", SimpleNamespace(monotonic=lambda: next(times)))
    result = runner._invoke(request)
    assert result["status"] == "failed" and result["raw_response"] is None
    assert result["audit"]["reason"] == "expired_review"
    assert result["audit"]["rejected_raw_response"] is not None


def test_interruption_keeps_completed_rows_and_never_resumes(prepared, tmp_path, monkeypatch):
    suite, _, plan = prepared
    output = tmp_path / "run"
    calls = fake_transport(monkeypatch, suite, fail_at=2, error=KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        runner.run_plan(suite, plan, output, enable_local_inference=True)
    assert len(calls) == 2
    result = json.loads((output / "run.json").read_text())
    assert result["status"] == "interrupted_no_retry" and result["worker_attempts"] == 2
    assert result["development_summary"]["missing_count"] == 10
    before = (output / "events.jsonl").read_bytes()
    with pytest.raises(FileExistsError):
        runner.run_plan(suite, plan, output, enable_local_inference=True)
    assert len(calls) == 2 and (output / "events.jsonl").read_bytes() == before


@pytest.mark.parametrize("event", ["case_started", "case_finished"])
def test_persistence_failure_stops_before_any_further_dispatch(
    prepared, tmp_path, monkeypatch, event
):
    suite, _, plan = prepared
    calls = fake_transport(monkeypatch, suite)
    original = runner._event

    def fail_write(stream, value):
        if value["event"] == event:
            raise OSError("simulated full disk")
        return original(stream, value)

    monkeypatch.setattr(runner, "_event", fail_write)
    with pytest.raises(OSError):
        runner.run_plan(suite, plan, tmp_path / "run", enable_local_inference=True)
    assert len(calls) == (0 if event == "case_started" else 1)


def test_plan_input_is_not_mutated(prepared, tmp_path, monkeypatch):
    suite, _, plan = prepared
    fake_transport(monkeypatch, suite)
    before = copy.deepcopy(plan)
    runner.run_plan(suite, plan, tmp_path / "run", enable_local_inference=True)
    assert plan == before


def test_cli_run_checks_raw_plan_pin_and_scores_selected_split(prepared, tmp_path, monkeypatch):
    suite, _, plan = prepared
    calls = fake_transport(monkeypatch, suite)
    path = tmp_path / "plan.json"
    runner._write(path, plan)
    args = [
        "advisory_runner",
        "run",
        "--suite",
        str(SUITE_PATH),
        "--plan",
        str(path),
        "--plan-sha256",
        "0" * 64,
        "--output-dir",
        str(tmp_path / "run"),
        "--enable-local-inference",
    ]
    monkeypatch.setattr(sys, "argv", args)
    with pytest.raises(ValueError, match="SHA256"):
        runner.main()
    assert not calls
    args[args.index("--plan-sha256") + 1] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert runner.main() == 0  # Only development coverage is intended, not curriculum.
    assert len(calls) == 7


def test_import_keeps_optional_model_and_training_modules_unloaded():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; import ai_trader.research.advisory_runner; "
            "assert not {'torch','transformers','psutil'} & sys.modules.keys(); "
            "assert not any(m.startswith('ai_trader.training.') for m in sys.modules)",
        ],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
