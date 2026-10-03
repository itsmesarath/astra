"""Synthetic full-context controls and inference tests; never real model calls or trading."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import test_six_e_context_lora as training_tests
from test_qwen_gpu_smoke import gpu_resources
from test_six_e_context_lora import balance_frozen as balance_frozen
from test_six_e_context_lora import candidate as candidate
from test_six_e_context_lora import evidence as evidence
from test_six_e_context_lora import gpu_request as gpu_request
from test_six_e_context_lora import install as install_training
from test_six_e_context_lora import original as original
from test_six_e_context_lora import prepared as prepared
from test_six_e_context_lora import samples as samples
from test_six_e_context_lora import trial_request as trial_request
from test_six_e_forecast_eval import FakeBackend
from test_six_e_lora_trial import pin, write

from ai_trader.models import _six_e_context_eval_worker as w
from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.models.local_reviewer import LocalReviewError
from ai_trader.research import six_e_context_eval as e
from ai_trader.training import six_e_context_controls as c

training_frozen = training_tests.frozen


@pytest.fixture
def cpu_frozen(training_frozen):
    path, training_pin, _ = training_frozen
    output = path.parent / "full-controls-plan.json"
    value = c.freeze(path, training_pin, output)
    return output, pin(output), value


@pytest.fixture
def cpu_completed(cpu_frozen):
    path, cpu_pin, _ = cpu_frozen
    output = path.parent / "full-controls"
    report = c.run(path, cpu_pin, output, enable_cpu_controls=True)
    return path, cpu_pin, output, pin(output / "run.json"), report


@pytest.fixture
def trained(training_frozen, monkeypatch):
    path, training_pin, _ = training_frozen
    output = path.parent / "context-candidate"

    def dispatch(command, packet, timeout):
        from ai_trader.training import _six_e_context_worker as worker

        install_training(packet, monkeypatch, owned=True)
        return canonical(worker.respond(canonical(packet).encode()))

    monkeypatch.setattr(c.training, "_exchange", dispatch)
    c.training.run(path, training_pin, output, enable_research_training=True)
    return output, pin(output / "request.json"), pin(output / "run.json")


@pytest.fixture
def frozen(cpu_completed, trained):
    path, cpu_pin, output, report_pin, _ = cpu_completed
    target = path.parent / "full-evaluation-plan.json"
    value = e.freeze(path, cpu_pin, output, report_pin, *trained, target)
    return target, pin(target), value


@pytest.fixture
def packet(frozen):
    path, plan_pin, _ = frozen
    value, parent, _, selection, _ = e.registration(path, plan_pin)
    result = e.worker_packet(value, parent, plan_pin, path.parent / "full-evaluation")
    return result, selection


def install(packet, selection, monkeypatch, *, owned=False):
    directory = Path(packet["output_dir"])
    if not owned:
        directory.mkdir()
        write(directory / "request.json", packet)
        with (directory / "features.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for item in selection:
                c._event(stream, item)
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        monkeypatch.setenv(key, "1")
    pins, runtime = e.validate_packet(packet)
    monkeypatch.setattr(w, "runtime_manifest", lambda: runtime)
    monkeypatch.setattr(w, "version", lambda name: pins[name])
    monkeypatch.setattr(w, "load_tokenizer", lambda *args: lambda text: [10, 11])
    backend = FakeBackend()
    monkeypatch.setattr(w, "create_backend", lambda *args: backend)
    monkeypatch.setattr(w, "resources", lambda *args: gpu_resources())
    return backend


def test_pure_import_and_immutable_specification():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; from ai_trader.training import six_e_context_controls; "
            "from ai_trader.research import six_e_context_eval; "
            "from ai_trader.models import _six_e_context_eval_worker; "
            "assert not ({'torch','peft','transformers','tokenizers','databento_dbn'} "
            "& set(sys.modules))",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert c.specification() == c.training.protocol()["comparison"]["linear"]
    assert c.specification()["columns"] == 79 and c.specification()["epochs"] == 200
    assert e.protocol()["pre_training_comparison"] == c.training.protocol()["comparison"]
    assert e.protocol()["pre_training_comparison"]["decoding"]["max_new_tokens"] == 48
    assert all(e.protocol()[k] is False for k in e.FLAGS)


def test_complete_fixed_controls_and_independent_recomputation(cpu_completed):
    path, cpu_pin, output, report_pin, report = cpu_completed
    _, value, chosen, verified = c.verified_run(path, cpu_pin, output, report_pin)
    assert (
        verified == report
        and report["check_examples"] == len(chosen) == value["comparison"]["cases"]
    )
    assert report["completed_predictions"] == 3 * len(chosen)
    assert set(report["scores"]) == set(c.NAMES)
    assert set(report["per_session_scores"]) == set(value["session_split"]["check"])
    assert report["cpu_fit_performed"] is True and report["qwen_training_performed"] is False
    assert len(c.lines(output / "epochs.jsonl", report["files"]["epochs.jsonl"])) == 400


def test_scaler_and_coefficients_use_all_fit_only(cpu_frozen):
    path, cpu_pin, _ = cpu_frozen
    _, value, fit, check = c.registration(path, cpu_pin)
    x = np.asarray([c.feature_values(row) for row in fit])
    events = []
    model = c.fit(fit, value["session_split"], epoch_sink=events.append)
    assert len(events) == 400
    assert np.allclose(model["means"], x.mean(axis=0), rtol=0, atol=1e-12)
    assert np.array_equal(
        np.asarray(model["scales"])[x.std(axis=0) == 0], np.ones(sum(x.std(axis=0) == 0))
    )
    changed = copy.deepcopy(check)
    for row in changed:
        row["completion"] = "poison check target"
    assert model == c.fit(fit, value["session_split"])
    with pytest.raises(ValueError, match="gate"):
        c.fit([*fit, changed[0]], value["session_split"])


def test_numeric_vector_prediction_and_selection_read_only_prompts(cpu_frozen):
    _, _, fit, _ = c.registration(cpu_frozen[0], cpu_frozen[1])
    row = fit[-1]

    class Poison(dict):
        def __getitem__(self, key):
            assert key == "prompt"
            return row[key]

    features = c.feature_values(Poison())
    payload = c.task.payload_from_prompt(row["prompt"])
    assert len(features) == 79 and features[:43] == payload["current"]
    assert features[43] == payload["past"][0][0] / 5
    assert features[55] == payload["past"][1][0] / 15
    assert features[67] == payload["past"][2][0] / 30
    assert features == c.feature_values(row)

    class Selected(dict):
        def __getitem__(self, key):
            assert key in {"case_id", "input_sha256", "prompt"}
            return row[key]

    selection = e.feature_selection([Selected()], lambda text: [10, 11])
    assert set(selection[0]) == {
        "case_id",
        "input_sha256",
        "prompt",
        "prompt_tokens",
        "prompt_ids_sha256",
    }


def test_metrics_count_wrong_side_noop_invalid_and_missed_separately():
    state = c.balance.forecast
    truth = [state("LLL"), state("SSS"), state("NNN"), state("LLL")]
    prediction = [state("SSS"), state("NNN"), state("LLL"), None]
    score = c.detailed_metrics(truth, prediction)
    assert score["coverage"] == 0.75
    for cost in score["by_cost"].values():
        assert cost["wrong_side_predictions"] == 1
        assert cost["no_opportunity_overcalls"] == 1
        assert cost["missed_opportunities"] == 3
        assert cost["missed_as_invalid"] == cost["missed_as_no_opportunity"] == 1
        assert cost["directional_precision"] == 0.0 and cost["overall_accuracy"] == 0.0


@pytest.mark.parametrize(
    "change", ["epoch", "request", "prediction", "score", "flag", "model", "runtime"]
)
def test_cpu_artifact_or_receipt_changes_refused(cpu_completed, change):
    path, cpu_pin, output, _, report = cpu_completed
    if change in {"epoch", "request", "prediction", "model"}:
        name = {
            "epoch": "epochs.jsonl",
            "request": "request.json",
            "prediction": "predictions.jsonl",
            "model": "model.json",
        }[change]
        with (output / name).open("ab") as stream:
            stream.write(b" \n")
    else:
        if change == "score":
            report["scores"][c.NAMES[0]]["coverage"] = 0.2
        elif change == "flag":
            report["promotion_allowed"] = True
        else:
            report["cpu_runtime"]["numpy"] = "untrusted"
        (output / "run.json").unlink()
        write(output / "run.json", report)
    with pytest.raises(ValueError):
        c.verified_run(path, cpu_pin, output, pin(output / "run.json"))


def test_no_fit_without_optin_no_output_reuse_and_deadline(cpu_frozen, monkeypatch):
    path, cpu_pin, _ = cpu_frozen
    output = path.parent / "deadline-controls"
    with pytest.raises(ValueError, match="opt-in"):
        c.run(path, cpu_pin, output)
    assert not output.exists()
    monkeypatch.setattr(c, "MAX_SECONDS", 0)
    # The protocol changes, so the original registration refuses even before fitting.
    with pytest.raises(ValueError):
        c.run(path, cpu_pin, output, enable_cpu_controls=True)
    assert not output.exists()
    with pytest.raises(TimeoutError):
        c.guard(-1)


def test_exact_full_comparison_and_candidate(packet, frozen):
    request, selection = packet
    assert request["cases"] == frozen[2]["comparison"]["cases"] == len(selection)
    assert e.feature_info(selection) == request["feature_file"]
    assert not ({"completion", "target_sha256", "dataset", "selection", "models"} & set(request))
    assert request["adapter_manifest_sha256"] == digest(frozen[2]["adapter_manifest"])


@pytest.mark.parametrize(
    "change", ["source", "protocol", "flag", "count", "sidecar", "overlap", "adapter", "extra"]
)
def test_native_packet_changes_refused(packet, change):
    request, _ = packet
    if change == "source":
        request["source_sha256"] = "0" * 64
    elif change == "protocol":
        request["protocol"]["pre_training_comparison"]["decoding"]["max_new_tokens"] = 49
    elif change == "flag":
        request["enable_development_evaluation"] = 1
    elif change == "count":
        request["cases"] = True
    elif change == "sidecar":
        request["feature_file"]["bytes"] = c.MAX_BYTES + 1
    elif change == "overlap":
        request["output_dir"] = request["checkpoint"]
    elif change == "adapter":
        request["adapter_manifest_sha256"] = "0" * 64
    else:
        request["completion"] = "future target"
    with pytest.raises(ValueError):
        e.validate_packet(request)


@pytest.mark.parametrize("change", ["duplicate", "tokens", "payload", "extra", "subset"])
def test_full_feature_selection_changes_refused(packet, change):
    request, selection = packet
    if change == "duplicate":
        selection[-1] = selection[0]
    elif change == "tokens":
        selection[-1]["prompt_tokens"] = True
    elif change == "payload":
        selection[-1]["input_sha256"] = "0" * 64
    elif change == "extra":
        selection[-1]["completion"] = "label"
    else:
        selection.pop()
    with pytest.raises(ValueError):
        e.validate_selection(selection, request["cases"])


def test_native_full_worker_and_complete_journal(packet, monkeypatch):
    request, selection = packet
    backend = install(request, selection, monkeypatch)
    original_open = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name not in {"fit.jsonl", "check.jsonl", "unavailable.jsonl", "model.json"}
        assert path.suffix != ".dbn"
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    result = w.respond(canonical(request).encode())
    predictions = e.validate_result(result, request, Path(request["output_dir"]))
    assert len(predictions) == len(backend.calls) == 2 * len(selection)
    assert (
        len(c.lines(Path(request["output_dir"]) / "events.jsonl", result["files"]["events.jsonl"]))
        == 4 * len(selection) + 3
    )
    assert all(result[k] is False for k in e.FLAGS)


@pytest.mark.parametrize(
    "change", ["sidecar", "tokenization", "offline", "runtime", "saved", "deadline", "native"]
)
def test_worker_refusals_and_failures_never_partial_success(packet, monkeypatch, change):
    request, selection = packet
    backend = install(request, selection, monkeypatch)
    directory = Path(request["output_dir"])
    if change == "sidecar":
        with (directory / "features.jsonl").open("ab") as stream:
            stream.write(b" \n")
    elif change == "tokenization":
        monkeypatch.setattr(w, "load_tokenizer", lambda *args: lambda text: [12, 13])
    elif change == "offline":
        monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    elif change == "runtime":
        monkeypatch.setattr(w, "version", lambda name: "wrong")
    elif change == "saved":
        (directory / "request.json").unlink()
        write(directory / "request.json", {"changed": True})
    elif change == "deadline":
        stamps = iter([0, e.TIMEOUT_MS / 1000 + 1])
        monkeypatch.setattr(w.time, "monotonic", lambda: next(stamps))
    else:

        def fail(*args):
            raise RuntimeError("synthetic native failure")

        monkeypatch.setattr(backend, "predict", fail)
    with pytest.raises((ValueError, TimeoutError, RuntimeError)):
        w.respond(canonical(request).encode())
    assert len(backend.calls) == 0
    if change in {"deadline", "native"}:
        assert json.loads((directory / "failure.json").read_text())["adapter_quarantined"] is True


def test_complete_pipeline_once_and_invalid_not_noop(frozen, monkeypatch):
    path, eval_pin, _ = frozen
    calls = []

    def dispatch(command, request, timeout):
        calls.append((command, timeout))
        selection = e.read_selection(request)
        install(request, selection, monkeypatch, owned=True)
        return canonical(w.respond(canonical(request).encode()))

    monkeypatch.setattr(e, "_exchange", dispatch)
    output = path.parent / "full-pipeline"
    report = e.run(path, eval_pin, output, enable_development_evaluation=True)
    assert len(calls) == 1 and calls[0][1] == e.TIMEOUT_MS
    assert set(report["scores"]) == {"base", "adapter", *c.NAMES}
    assert report["scores"]["base"]["invalid_outputs"] == report["examples"]
    assert report["scores"]["base"]["by_cost"]["extra_1_tick"]["overall_accuracy"] == 0.0
    assert report["adapter_quarantined"] is True
    with pytest.raises(ValueError):
        e.run(path, eval_pin, output, enable_development_evaluation=True)


def test_dispatch_timeout_no_retries_or_score(frozen, monkeypatch):
    path, eval_pin, _ = frozen
    calls = []

    def fail(*args):
        calls.append(args)
        raise LocalReviewError("worker_deadline")

    monkeypatch.setattr(e, "_exchange", fail)
    output = path.parent / "interrupted-evaluation"
    with pytest.raises(LocalReviewError):
        e.run(path, eval_pin, output, enable_development_evaluation=True)
    report = json.loads((output / "run.json").read_text())
    assert len(calls) == 1 and "scores" not in report and report["promotion_allowed"] is False


def test_gpu_optin_before_any_input_access(tmp_path):
    with pytest.raises(ValueError, match="opt-in"):
        e.run(tmp_path / "missing", "0" * 64, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_large_full_set_uses_pinned_sidecar_not_transport(packet):
    request, selection = packet
    template = selection[0]
    full = [{**template, "case_id": digest(index)} for index in range(5008)]
    e.validate_selection(full, 5008)
    info = e.feature_info(full)
    assert info["bytes"] > 1024**2 and info["bytes"] < c.MAX_BYTES
    request.update(cases=5008, feature_file=info)
    e.validate_packet(request)
    assert len(canonical(request).encode()) < e.MAX_PACKET_BYTES


@pytest.mark.parametrize("change", ["count", "journal", "predictions", "resource", "authority"])
def test_partial_or_altered_native_evidence_refused(packet, monkeypatch, change):
    request, selection = packet
    install(request, selection, monkeypatch)
    directory = Path(request["output_dir"])
    result = w.respond(canonical(request).encode())
    if change == "count":
        result["completed_calls"] -= 1
    elif change in {"journal", "predictions"}:
        name = "events.jsonl" if change == "journal" else "predictions.jsonl"
        rows = c.lines(directory / name, result["files"][name])[:-1]
        (directory / name).unlink()
        with (directory / name).open("x", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                c._event(stream, row)
        result["files"][name] = c.file_info(directory / name)
    elif change == "resource":
        result["resources"]["tf32_enabled"] = True
    else:
        result["promotion_allowed"] = True
    with pytest.raises(ValueError):
        e.validate_result(result, request, directory)


def test_final_input_drift_after_complete_worker_prevents_scoring(frozen, monkeypatch):
    path, eval_pin, _ = frozen
    real_registration = e.registration
    registrations = []

    def registration(*args):
        value = real_registration(*args)
        registrations.append(args)
        if len(registrations) == 2:
            value[0]["comparison"]["ordered_examples_sha256"] = "0" * 64
        return value

    def dispatch(command, request, timeout):
        selection = e.read_selection(request)
        install(request, selection, monkeypatch, owned=True)
        return canonical(w.respond(canonical(request).encode()))

    monkeypatch.setattr(e, "registration", registration)
    monkeypatch.setattr(e, "_exchange", dispatch)
    output = path.parent / "post-run-drift"
    with pytest.raises(ValueError, match="drifted"):
        e.run(path, eval_pin, output, enable_development_evaluation=True)
    report = json.loads((output / "run.json").read_text())
    assert "scores" not in report and report["status"] == "failed_or_interrupted_no_subset_score"


@pytest.mark.parametrize("text", ["é" * 40, "\x00" * 40])
def test_output_budget_checks_encoded_bytes_before_each_write(tmp_path, text):
    value = {"event": text}
    raw = (canonical(value) + "\n").encode()
    path = tmp_path / "bounded.jsonl"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        w.bounded_event(stream, value, limit=len(raw))
        with pytest.raises(ValueError, match="before write"):
            w.bounded_event(stream, value, limit=len(raw))
    assert path.read_bytes() == raw


def test_output_line_budget_refuses_before_first_write(tmp_path):
    path = tmp_path / "empty.jsonl"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        with pytest.raises(ValueError, match="before write"):
            w.bounded_event(stream, {"too_long": "x" * c.MAX_LINE})
    assert path.read_bytes() == b""
