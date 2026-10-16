"""Smoke harness tests are synthetic and never invoke the provisioned model."""

import sys
from dataclasses import replace
from pathlib import Path

import pytest

from ai_trader.models import qwen_smoke as smoke
from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.models.local_reviewer import LocalReviewerConfig, LocalReviewError


def config(tmp_path):
    return LocalReviewerConfig(
        "synthetic-qwen-smoke",
        backend="transformers",
        model_id="Qwen/Qwen3-4B-Base",
        checkpoint_path=tmp_path,
        checkpoint_sha256="a" * 64,
        device="cuda",
        max_calls=1,
    )


def install_fake(monkeypatch, raw=None, wrong_binding=False):
    calls = []

    def exchange(command, request, timeout):
        calls.append((command, request, timeout))
        return canonical(
            {
                "request_sha256": "b" * 64 if wrong_binding else digest(request),
                "raw_response": raw
                if raw is not None
                else canonical(
                    {
                        "verdict": "veto",
                        "evidence_ids": ["cvd", "cost"],
                        "rationale": "Synthetic only.",
                    }
                ),
                "metrics": {"cuda_peak_allocated_bytes": 1024},
            }
        )

    monkeypatch.setattr(smoke, "_exchange", exchange)
    return calls


def test_one_synthetic_call_no_execution_or_promotion(tmp_path, monkeypatch):
    calls = install_fake(monkeypatch)
    result = smoke.run_smoke(config(tmp_path), enable_local_inference=True)
    assert len(calls) == 1
    assert calls[0][0] == [sys.executable, "-I", "-m", "ai_trader.models.qwen_smoke", "--worker"]
    assert calls[0][1]["input"]["role"] == "analyst"
    assert all(
        e["source_session"] == "synthetic-qwen-smoke" for e in calls[0][1]["input"]["evidence"]
    )
    assert result["generation_completed"] and result["report_valid"]
    assert result["orders"] == 0 and result["training_started"] is False
    assert result["promotion_allowed"] is False


@pytest.mark.parametrize("enabled", [False, None, "true", 1])
def test_opt_in_is_required(tmp_path, enabled):
    with pytest.raises(ValueError, match="opt-in"):
        smoke.run_smoke(config(tmp_path), enable_local_inference=enabled)


@pytest.mark.parametrize(
    "changes",
    [
        {"device": "cpu"},
        {"model_id": "Qwen/Qwen3-4B"},
        {"max_calls": 2},
        {"source_session": "actual-data"},
    ],
)
def test_configuration_cannot_expand_scope(tmp_path, changes):
    with pytest.raises(ValueError, match="single-call"):
        smoke.run_smoke(replace(config(tmp_path), **changes), enable_local_inference=True)


@pytest.mark.parametrize("raw", ["text instead of JSON", "{}", "```json\n{}\n```"])
def test_generation_is_distinct_from_valid_report(tmp_path, monkeypatch, raw):
    calls = install_fake(monkeypatch, raw)
    result = smoke.run_smoke(config(tmp_path), enable_local_inference=True)
    assert len(calls) == 1 and result["generation_completed"]
    assert not result["report_valid"] and result["raw_response"] == raw
    assert result["status"] == "invalid_measurement_or_report"


def test_wrong_binding_never_claims_completed_generation(tmp_path, monkeypatch):
    install_fake(monkeypatch, wrong_binding=True)
    result = smoke.run_smoke(config(tmp_path), enable_local_inference=True)
    assert not result["generation_completed"] and not result["report_valid"]


def test_deadline_failure_no_retry(tmp_path, monkeypatch):
    calls = []

    def timeout(*args):
        calls.append(args)
        raise LocalReviewError("worker_deadline")

    monkeypatch.setattr(smoke, "_exchange", timeout)
    result = smoke.run_smoke(config(tmp_path), enable_local_inference=True)
    assert len(calls) == 1 and result["status"] == "worker_deadline"
    assert not result["generation_completed"]


def test_cli_cannot_overwrite_artifact_or_repeat_inference(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    output.write_text("keep")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qwen_smoke",
            "--checkpoint",
            str(tmp_path),
            "--checkpoint-sha256",
            "a" * 64,
            "--python-executable",
            str(Path(sys.executable)),
            "--output",
            str(output),
            "--enable-local-inference",
        ],
    )
    calls = install_fake(monkeypatch)
    with pytest.raises(FileExistsError):
        smoke.main()
    assert not calls and output.read_text() == "keep"


def test_smoke_module_keeps_optional_imports_lazy():
    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; import ai_trader.models.qwen_smoke; "
            "assert not {'torch','transformers','psutil'} & sys.modules.keys()",
        ],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
