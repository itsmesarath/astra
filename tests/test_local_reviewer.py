"""Process, protocol, scope and council checks without a real model/runtime/network."""

import json
import subprocess
import sys
import time
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from ai_trader.models import _local_review_worker as worker
from ai_trader.models import local_reviewer as local
from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.research.council import (
    Evidence,
    ResearchSnapshot,
    RoleReport,
    parse_role_report,
    review_spot_entry,
)
from ai_trader.risk.engine import OrderIntent, PortfolioRiskState, RiskLimits
from ai_trader.trading.decision_policy import DecisionPolicy, decide_position


@pytest.fixture(autouse=True)
def isolated_offline_environment(monkeypatch):
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        monkeypatch.setenv(key, "1")


def snapshot():
    return ResearchSnapshot(
        "BTCUSDT",
        1000,
        (Evidence("cvd", "BTCUSDT", "synthetic", "rolling_cvd_btc", Decimal("1"), 900, 950),),
    )


def reviewer(**kwargs):
    return local.LocalReviewer(
        local.LocalReviewerConfig("synthetic", **kwargs), enable_local_inference=True
    )


def support():
    return canonical({"verdict": "support", "evidence_ids": ["cvd"], "rationale": "Test only."})


def bind_reply(monkeypatch, raw=None):
    def exchange(command, request, timeout_ms):
        return canonical(
            {"request_sha256": digest(request), "raw_response": support() if raw is None else raw}
        )

    monkeypatch.setattr(local, "_exchange", exchange)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"timeout_ms": True},
        {"timeout_ms": 0},
        {"timeout_ms": 120001},
        {"max_calls": 3},
        {"max_input_tokens": 2049},
        {"max_new_tokens": 513},
        {"reply_ttl_ms": 0},
        {"maximum_evidence_age_ms": -1},
        {"backend": "cloud"},
        {"model_id": "Qwen/Qwen3-4B"},
        {"device": "auto"},
        {"python_executable": Path("python.exe")},
        {"checkpoint_sha256": "a" * 64},
    ],
)
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        local.LocalReviewerConfig("synthetic", **kwargs)


@pytest.mark.parametrize("enabled", [False, 1, "true", None])
def test_explicit_opt_in_required(enabled):
    with pytest.raises(ValueError, match="Explicit"):
        local.LocalReviewer(local.LocalReviewerConfig("synthetic"), enable_local_inference=enabled)


def test_real_subprocess_stub_has_no_model_or_order_authority():
    instance = reviewer()
    raw = instance.review("analyst", snapshot(), ())
    report = parse_role_report(raw, "analyst", snapshot())
    assert report.verdict == "veto"
    assert report.evidence_ids == ("cvd",)
    assert "Synthetic" in report.rationale
    audit = instance.audit[0]
    assert audit["status"] == "validated_advisory"
    assert audit["model_id"] == "synthetic-veto"
    assert audit["orders"] == 0 and audit["promotion_allowed"] is False
    audit["orders"] = 1
    assert instance.audit[0]["orders"] == 0


def test_stub_imports_no_native_model_packages_in_worker(monkeypatch):
    import builtins

    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        assert name.split(".")[0] not in {"torch", "transformers", "safetensors"}
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    request = local.build_request(local.LocalReviewerConfig("synthetic"), "analyst", snapshot(), ())
    response = worker.respond(canonical(request).encode())
    assert response["request_sha256"] == digest(request)
    assert json.loads(response["raw_response"])["verdict"] == "veto"


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_session", "another"),
        ("symbol", "ETHUSDT"),
        ("available_time_ms", 1001),
        ("event_time_ms", 0),
        ("value", Decimal("1" * 1025)),
    ],
)
def test_scope_and_freshness_refused_before_spawn(monkeypatch, field, value):
    def forbidden(*args, **kwargs):
        raise AssertionError("Out-of-scope input reached worker")

    monkeypatch.setattr(local, "_exchange", forbidden)
    current = snapshot()
    current = replace(current, evidence=(replace(current.evidence[0], **{field: value}),))
    instance = reviewer(maximum_evidence_age_ms=200)
    with pytest.raises(local.LocalReviewError, match="out_of_scope"):
        instance.review("analyst", current, ())


def test_two_roles_exact_prior_snapshot_no_retry_and_bounded_audit(monkeypatch):
    bind_reply(monkeypatch)
    instance = reviewer()
    first = instance.review("analyst", snapshot(), ())
    prior = (parse_role_report(first, "analyst", snapshot()),)
    assert instance.review("critic", snapshot(), prior) == support()
    for _ in range(10):
        with pytest.raises(local.LocalReviewError, match="review_call_budget"):
            instance.review("analyst", snapshot(), ())
    assert len(instance.audit) == 3


@pytest.mark.parametrize("alteration", ["repeat", "prior", "snapshot", "veto"])
def test_sequence_cannot_switch_snapshot_or_forge_prior(monkeypatch, alteration):
    bind_reply(
        monkeypatch, support().replace('"support"', '"veto"') if alteration == "veto" else None
    )
    instance = reviewer()
    first = instance.review("analyst", snapshot(), ())
    prior = (parse_role_report(first, "analyst", snapshot()),)
    current, role = snapshot(), "critic"
    if alteration == "repeat":
        role, prior = "analyst", ()
    elif alteration == "prior":
        prior = (replace(prior[0], rationale="Forged"),)
    elif alteration == "snapshot":
        current = replace(current, as_of_ms=1001)
    with pytest.raises(local.LocalReviewError, match="invalid_role_sequence"):
        instance.review(role, current, prior)


def test_critic_cannot_start_a_sequence():
    with pytest.raises(local.LocalReviewError, match="invalid_role_sequence"):
        reviewer().review("critic", snapshot(), (RoleReport("analyst", "support", ("cvd",), "x"),))


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        "x" * 2049,
        "<think>analysis</think>" + support(),
        "```json\n" + support() + "\n```",
        support() + " extra",
        support().replace('"cvd"', '"invented"'),
        support()[:-1] + ',"quantity":1}',
        '{"verdict":"support","verdict":"veto","evidence_ids":["cvd"],"rationale":"x"}',
    ],
)
def test_bad_responses_fail_closed(monkeypatch, raw):
    bind_reply(monkeypatch, raw)
    instance = reviewer()
    with pytest.raises(local.LocalReviewError):
        instance.review("analyst", snapshot(), ())
    assert instance.audit[0]["status"] != "validated_advisory"


def test_wrong_request_binding_and_worker_errors_sanitized(monkeypatch):
    monkeypatch.setattr(
        local,
        "_exchange",
        lambda *a: canonical({"request_sha256": "a" * 64, "raw_response": support()}),
    )
    with pytest.raises(local.LocalReviewError, match="invalid_worker_binding"):
        reviewer().review("analyst", snapshot(), ())

    def private_error(*args):
        raise RuntimeError("SECRET-provider-detail")

    monkeypatch.setattr(local, "_exchange", private_error)
    instance = reviewer()
    with pytest.raises(local.LocalReviewError, match="invalid_or_failed_local_review"):
        instance.review("analyst", snapshot(), ())
    assert "SECRET" not in repr(instance.audit)


def test_expired_reply_is_never_validated(monkeypatch):
    bind_reply(monkeypatch)
    timestamps = iter([0, 1, 2])
    monkeypatch.setattr(local.time, "monotonic", lambda: next(timestamps))
    with pytest.raises(local.LocalReviewError, match="expired_review"):
        reviewer(reply_ttl_ms=10).review("analyst", snapshot(), ())


def test_concurrent_call_refused():
    instance = reviewer()
    with instance._lock, pytest.raises(local.LocalReviewError, match="concurrent_review_refused"):
        instance.review("analyst", snapshot(), ())


@pytest.mark.parametrize("field", ["system_prompt", "protocol_version", "prompt_sha256"])
def test_worker_rebuilds_contract(field):
    request = local.build_request(local.LocalReviewerConfig("synthetic"), "analyst", snapshot(), ())
    request[field] = "tampered"
    with pytest.raises(ValueError, match="contract"):
        worker.decode_request(canonical(request).encode())


def test_request_byte_cap_on_both_sides(monkeypatch):
    monkeypatch.setattr(local, "MAX_REQUEST_BYTES", 10)
    with pytest.raises(local.LocalReviewError, match="request_byte_limit"):
        local.build_request(local.LocalReviewerConfig("synthetic"), "analyst", snapshot(), ())
    with pytest.raises(ValueError, match="request bytes"):
        worker.decode_request(b"x" * (worker.MAX_REQUEST_BYTES + 1))


def test_worker_environment_drops_credentials_and_proxies(monkeypatch):
    for key in ("HF_TOKEN", "BINANCE_API_KEY", "OPENAI_API_KEY", "HTTPS_PROXY", "PYTHONPATH"):
        monkeypatch.setenv(key, "SECRET")
    env = local._worker_environment()
    assert "SECRET" not in repr(env)
    assert env["HF_HUB_OFFLINE"] == env["TRANSFORMERS_OFFLINE"] == "1"


def child(code):
    return [sys.executable, "-I", "-c", code]


def test_real_pipe_environment():
    raw = local._exchange(
        child("import sys,os,json; sys.stdin.read(); print(json.dumps(dict(os.environ)))"), {}, 5000
    )
    env = json.loads(raw)
    assert env["HF_HUB_OFFLINE"] == "1"
    assert env["HF_HUB_DISABLE_PROGRESS_BARS"] == "1"
    assert "PYTHONPATH" not in env


@pytest.mark.parametrize("pipe", ["stdout", "stderr"])
def test_real_pipe_overflow_is_bounded(pipe):
    with pytest.raises(local.LocalReviewError, match="pipe_limit"):
        local._exchange(
            child(
                f"import sys; sys.stdin.read(); sys.{pipe}.write('x'*1000000); sys.{pipe}.flush()"
            ),
            {},
            5000,
        )


def test_deadline_kills_owned_worker(monkeypatch):
    created = []
    original = subprocess.Popen

    def track(*args, **kwargs):
        result = original(*args, **kwargs)
        created.append(result)
        return result

    monkeypatch.setattr(local.subprocess, "Popen", track)
    start = time.monotonic()
    with pytest.raises(local.LocalReviewError, match="deadline"):
        local._exchange(child("import time; time.sleep(60)"), {}, 100)
    assert time.monotonic() - start < 5
    assert created[0].poll() is not None


def test_worker_failure_does_not_include_stderr():
    with pytest.raises(local.LocalReviewError, match="^worker_failed$"):
        local._exchange(
            child("import sys; sys.stdin.read(); sys.stderr.write('SECRET'); sys.exit(2)"), {}, 5000
        )


def test_council_preserves_paper_only_and_risk_veto():
    args = {
        "signal": decide_position([0.1, 0.1, 0.8], DecisionPolicy(allow_short=False)),
        "order": OrderIntent("BUY", Decimal("0.01"), Decimal("80000")),
        "state": PortfolioRiskState(Decimal("0"), Decimal("0"), Decimal("10000"), Decimal("10000")),
        "limits": RiskLimits(*(Decimal(v) for v in ("0.1", "0.02", "2000", "5000", "100", "150"))),
        "snapshot": snapshot(),
        "reviewer": reviewer(),
    }
    result = review_spot_entry(**args)
    assert not result.entry_allowed and result.reason == "analyst_veto"
    assert result.mode == "offline_research_only"
    args.update(state=replace(args["state"], kill_switch_active=True), reviewer=reviewer())
    assert review_spot_entry(**args).reason == "risk_veto:kill_switch_active"
    assert args["reviewer"].audit == ()


@pytest.mark.parametrize("option", ["--demo", "--runtime-check"])
def test_cli_without_model(option):
    result = subprocess.run(
        [sys.executable, "-I", "-m", "ai_trader.models.local_reviewer", option],
        capture_output=True,
        text=True,
        timeout=10,
        env=local._worker_environment(),
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    if option == "--demo":
        assert output["synthetic_demo"] is True and output["report"]["verdict"] == "veto"
    else:
        assert output["model_loaded"] is False and output["training_started"] is False


def test_module_does_not_eagerly_import_model_runtime():
    result = subprocess.run(
        child(
            "import sys; import ai_trader.models.local_reviewer; "
            "assert not {'torch','transformers','safetensors'} & sys.modules.keys()"
        ),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
