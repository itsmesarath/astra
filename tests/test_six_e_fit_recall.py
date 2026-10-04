"""Synthetic fit diagnostics only: no real GPU, optimizer, archives or trades."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
import test_six_e_context_eval as previous_tests
from test_qwen_gpu_smoke import gpu_resources
from test_six_e_context_eval import cpu_completed as cpu_completed
from test_six_e_context_eval import cpu_frozen as cpu_frozen
from test_six_e_context_eval import install as install_previous
from test_six_e_context_eval import trained as trained
from test_six_e_context_eval import training_frozen as training_frozen
from test_six_e_context_lora import balance_frozen as balance_frozen
from test_six_e_context_lora import candidate as candidate
from test_six_e_context_lora import evidence as evidence
from test_six_e_context_lora import gpu_request as gpu_request
from test_six_e_context_lora import original as original
from test_six_e_context_lora import prepared as prepared
from test_six_e_context_lora import samples as samples
from test_six_e_context_lora import trial_request as trial_request
from test_six_e_forecast_eval import FakeBackend
from test_six_e_lora_trial import pin, write

from ai_trader.models import _six_e_context_eval_worker as previous_worker
from ai_trader.models import _six_e_fit_recall_worker as w
from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.models.local_reviewer import LocalReviewError
from ai_trader.research import six_e_context_eval as e
from ai_trader.research import six_e_fit_recall as r

context_frozen = previous_tests.frozen


@pytest.fixture
def packet(training_frozen, trained):
    path, _, value = training_frozen
    directory, request_pin, report_pin = trained
    original_packet = e.tokens.metadata(directory / "request.json", request_pin)
    original_report = e.tokens.metadata(directory / "run.json", report_pin)
    chosen = r.selected_fit(original_packet, value)
    selection = e.feature_selection(chosen, lambda text: [10, 11])
    registered = {
        "kind": r.KIND,
        "protocol": r.protocol(),
        "source_sha256": r.source_sha256(),
        "completed_comparison": {
            "registration": str(path),
            "registration_sha256": "a" * 64,
            "directory": str(directory),
            "report_sha256": report_pin,
        },
        "adapter_manifest": original_report["result"]["reload"]["adapter_manifest"],
        "ordered_examples_sha256": digest([digest(row) for row in chosen]),
        "feature_file": e.feature_info(selection),
        "fit_joint_counts": value["fit_joint_counts"],
        "training_trace": r.trace_audit(
            chosen,
            r.training.validate_result(original_report["result"], original_packet, directory),
            original_report["result"]["reload"],
        ),
        **r.FLAGS,
    }
    old = {
        "training_trial": {"directory": str(directory)},
        "controls_trial": {"directory": str(path.parent / "controls")},
        "controls_registration": {"path": str(path.parent / "controls-plan.json")},
    }
    request = r.worker_packet(registered, value, "a" * 64, path.parent / "fit-recall", old)
    return request, selection, value, chosen, registered, old, original_packet


def install(packet, monkeypatch, *, owned=False):
    request, selection, *_ = packet
    directory = Path(request["output_dir"])
    if not owned:
        directory.mkdir()
        write(directory / "request.json", request)
        with (directory / "features.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for item in selection:
                r.controls._event(stream, item)
    for name in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        monkeypatch.setenv(name, "1")
    pins, runtime = r.validate_packet(request)
    monkeypatch.setattr(w, "runtime_manifest", lambda: runtime)
    monkeypatch.setattr(w, "version", lambda name: pins[name])
    monkeypatch.setattr(w, "load_tokenizer", lambda *args: lambda text: [10, 11])
    backend = FakeBackend()
    monkeypatch.setattr(w, "create_backend", lambda *args: backend)
    monkeypatch.setattr(w, "resources", lambda *args: gpu_resources())
    return backend


def test_import_and_fixed_scope():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; from ai_trader.research import six_e_fit_recall; "
            "from ai_trader.models import _six_e_fit_recall_worker; "
            "assert not ({'torch','peft','transformers','tokenizers','databento_dbn'} "
            "& set(sys.modules))",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert r.protocol()["bounds"]["calls"] == 384
    assert r.protocol()["bounds"]["worker_seconds"] == 1800
    assert r.protocol()["inference"] == e.training.protocol()["comparison"]["decoding"]
    assert "Seen train/inner-fit recall ONLY" in r.protocol()["scope"]
    assert all(r.protocol()[k] is False for k in r.FLAGS)


def test_original_order_trace_and_feature_only_transport(packet):
    request, selection, value, chosen, registered, _, original_packet = packet
    assert [row["case_id"] for row in chosen] == [i["case_id"] for i in value["selection"]]
    assert len(chosen) == 192 and all(row["inner_partition"] == "fit" for row in chosen)
    assert registered["training_trace"]["reload_probe"]["joint_state"] == r.controls.state_of(
        chosen[0]
    )
    assert (
        sum(v["examples"] for v in registered["training_trace"]["by_joint_state"].values()) == 192
    )
    assert all(
        set(item) == {"case_id", "input_sha256", "prompt", "prompt_tokens", "prompt_ids_sha256"}
        for item in selection
    )
    assert "target_sha256" not in request and "selection" not in request
    altered = copy.deepcopy(original_packet)
    altered["selection"].reverse()
    with pytest.raises(ValueError, match="ordered"):
        r.selected_fit(altered, value)


@pytest.mark.parametrize(
    "field,value",
    [("role", "reserved"), ("inner_partition", "check"), ("source_session", "reserved-session")],
)
def test_all_membership_gates_before_data_access(packet, field, value):
    _, _, registered, _, _, _, original_packet = packet

    class Poison(dict):
        def __getitem__(self, key):
            assert key not in {"prompt", "completion", "target_sha256", "input_sha256"}
            return super().__getitem__(key)

    altered = copy.deepcopy(original_packet)
    row = Poison(altered["selection"][-1]["example"])
    row[field] = value
    altered["selection"][-1]["example"] = row
    with pytest.raises(ValueError, match="membership"):
        r.selected_fit(altered, registered)
    chosen = [i["example"] for i in altered["selection"]]
    if field != "source_session":
        with pytest.raises(ValueError, match="scoring gate"):
            r.fit_gate(chosen)


@pytest.mark.parametrize(
    "field,value",
    [
        ("cases", 191),
        ("cases", True),
        ("enable_fit_diagnostic", False),
        ("kind", e.KIND),
        ("source_sha256", "0" * 64),
        ("protocol", {}),
        ("feature_file", {"bytes": 2**22, "sha256": "a" * 64}),
    ],
)
def test_packet_changes_refused(packet, field, value):
    request = copy.deepcopy(packet[0])
    request[field] = value
    with pytest.raises(ValueError):
        r.validate_packet(request)


def test_complete_native_diagnostic_and_invalid_not_idle(packet, monkeypatch):
    request, _, value, chosen, *_ = packet
    backend = install(packet, monkeypatch)
    original_open = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name not in {"fit.jsonl", "check.jsonl", "unavailable.jsonl", "model.json"}
        assert path.suffix != ".dbn"
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    result = w.respond(canonical(request).encode())
    predictions = r.validate_result(result, request, Path(request["output_dir"]))
    assert len(predictions) == len(backend.calls) == 384
    assert json.loads((Path(request["output_dir"]) / "gpu_result.json").read_text()) == result
    assert (
        len(
            r.controls.lines(
                Path(request["output_dir"]) / "events.jsonl", result["files"]["events.jsonl"]
            )
        )
        == 771
    )
    report = r.score(chosen, predictions, value["fit_joint_counts"])
    assert report["diagnostic_conclusion"] == "collapse_on_seen_fit"
    assert report["output_status_counts"]["adapter"] == {"valid": 192}
    assert report["scores"]["base"]["invalid_outputs"] == 192
    assert report["scores"]["adapter"] == report["scores"]["no_opportunity"]
    with pytest.raises(ValueError):
        r.score(chosen, predictions[:-1], value["fit_joint_counts"])
    predictions[0], predictions[1] = predictions[1], predictions[0]
    with pytest.raises(ValueError, match="binding"):
        r.score(chosen, predictions, value["fit_joint_counts"])


@pytest.mark.parametrize(
    "change",
    ["sidecar", "tokenization", "offline", "runtime", "saved", "deadline", "native", "gradients"],
)
def test_worker_failures_never_partial_success(packet, monkeypatch, change):
    request = packet[0]
    backend = install(packet, monkeypatch)
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
        stamps = iter([0, r.TIMEOUT_MS / 1000 + 1])
        monkeypatch.setattr(w.time, "monotonic", lambda: next(stamps))
    else:

        def fail(*args):
            raise RuntimeError("synthetic native failure")

        monkeypatch.setattr(backend, "guard" if change == "gradients" else "predict", fail)
    with pytest.raises((ValueError, TimeoutError, RuntimeError)):
        w.respond(canonical(request).encode())
    assert not backend.calls
    if change in {"deadline", "native", "gradients"}:
        assert json.loads((directory / "failure.json").read_text())["adapter_quarantined"] is True


@pytest.mark.parametrize(
    "change", ["count", "parameters", "authority", "resources", "prediction", "journal"]
)
def test_terminal_verification_refuses_partial_or_changed_outputs(packet, monkeypatch, change):
    request = packet[0]
    install(packet, monkeypatch)
    directory = Path(request["output_dir"])
    result = w.respond(canonical(request).encode())
    if change == "count":
        result["completed_calls"] -= 1
    elif change == "parameters":
        result["parameters_frozen"] = False
    elif change == "authority":
        result["promotion_allowed"] = True
    elif change == "resources":
        result["resources"]["tf32_enabled"] = True
    else:
        name = "predictions.jsonl" if change == "prediction" else "events.jsonl"
        lines = (directory / name).read_bytes().splitlines(keepends=True)
        (directory / name).write_bytes(b"".join(lines[:-1]))
        result["files"][name] = r.controls.file_info(directory / name)
    with pytest.raises(ValueError):
        r.validate_result(result, request, directory)


def test_diagnostic_conclusions_separate_seen_recall_from_invalid_output(packet):
    _, _, value, chosen, *_ = packet
    predictions = []
    for i, row in enumerate(chosen):
        for offset, mode in enumerate(r.legacy.MODES):
            predictions.append(
                {
                    **r.legacy.binding(2 * i + offset + 1, mode, row),
                    "raw_response": row["completion"],
                    "generated_tokens": 40,
                    "stop_reason": "eos",
                }
            )
    assert (
        r.score(chosen, predictions, value["fit_joint_counts"])["diagnostic_conclusion"]
        == "some_seen_fit_recall_requires_separate_development_transfer"
    )
    predictions[1]["stop_reason"] = "token_limit"
    predictions[1]["generated_tokens"] = r.legacy.MAX_NEW_TOKENS
    assert (
        r.score(chosen, predictions, value["fit_joint_counts"])["diagnostic_conclusion"]
        == "invalid_outputs_prevent_recall_conclusion"
    )


def test_explicit_optin_before_inputs(tmp_path):
    with pytest.raises(ValueError, match="opt-in"):
        r.run(tmp_path / "absent.json", "a" * 64, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_complete_registration_pipeline_and_reverification(context_frozen, monkeypatch):
    path, old_pin, _ = context_frozen
    directory = path.parent / "completed-comparison"

    def previous_dispatch(command, request, timeout):
        selection = e.read_selection(request)
        install_previous(request, selection, monkeypatch, owned=True)
        return canonical(previous_worker.respond(canonical(request).encode()))

    monkeypatch.setattr(e, "_exchange", previous_dispatch)
    e.run(path, old_pin, directory, enable_development_evaluation=True)
    target = path.parent / "recall-plan.json"
    r.freeze(path, old_pin, directory, pin(directory / "run.json"), target)
    registered, value, chosen, selection, old = r.registration(target, pin(target))
    calls = []

    def dispatch(command, request, timeout):
        calls.append((command, timeout))
        install((request, selection), monkeypatch, owned=True)
        return canonical(w.respond(canonical(request).encode()))

    monkeypatch.setattr(r, "_exchange", dispatch)
    output = path.parent / "recall-diagnostic"
    report = r.run(target, pin(target), output, enable_fit_diagnostic=True)
    assert report["status"] == r.STATUS and report["examples"] == 192
    assert len(calls) == 1 and calls[0][1] == r.TIMEOUT_MS
    packet = r.worker_packet(registered, value, pin(target), output, old)
    predictions = r.validate_result(report["gpu_result"], packet, output)
    for key, metric in r.score(chosen, predictions, registered["fit_joint_counts"]).items():
        assert canonical(report[key]) == canonical(metric)
    assert all(report[k] is False for k in r.FLAGS)
    monkeypatch.setattr(
        r, "_exchange", lambda *args: pytest.fail("Verification cannot call a model")
    )
    verified = r.verify_run(target, pin(target), output, pin(output / "run.json"))
    assert verified["completed_calls"] == 384 and verified["journal_events"] == 771
    assert verified["diagnostic_conclusion"] == report["diagnostic_conclusion"]
    altered = copy.deepcopy(report)
    altered["scores"]["adapter"]["valid_outputs"] -= 1
    (output / "run.json").write_text(canonical(altered) + "\n")
    with pytest.raises(ValueError, match="metrics differ"):
        r.verify_run(target, pin(target), output, pin(output / "run.json"))
    (output / "run.json").write_text(canonical(report) + "\n")
    with pytest.raises(ValueError):
        r.run(target, pin(target), output, enable_fit_diagnostic=True)
    completed = json.loads((directory / "run.json").read_text())
    completed["scores"]["adapter"]["valid_outputs"] -= 1
    (directory / "run.json").write_text(canonical(completed) + "\n")
    with pytest.raises(ValueError):
        r.registration(target, pin(target))


@pytest.mark.parametrize("failure", ["timeout", "post_input_drift"])
def test_dispatch_failure_no_retry_or_subset_scoring(packet, tmp_path, monkeypatch, failure):
    _, selection, value, chosen, registered, old, _ = packet
    path = tmp_path / "recall-plan.json"
    write(path, registered)
    expected = (registered, value, chosen, selection, old)
    monkeypatch.setattr(r, "registration", lambda *args: expected)
    calls = []

    def dispatch(command, request, timeout):
        calls.append(command)
        if failure == "timeout":
            raise LocalReviewError("synthetic_timeout")
        install((request, selection), monkeypatch, owned=True)
        result = w.respond(canonical(request).encode())
        monkeypatch.setattr(
            r, "registration", lambda *args: (*expected[:-1], {**old, "changed": True})
        )
        return canonical(result)

    monkeypatch.setattr(r, "_exchange", dispatch)
    monkeypatch.setattr(r, "score", lambda *args: pytest.fail("No partial/drifted scores"))
    output = tmp_path / "failed-diagnostic"
    with pytest.raises((ValueError, LocalReviewError)):
        r.run(path, pin(path), output, enable_fit_diagnostic=True)
    assert len(calls) == 1
    report = json.loads((output / "run.json").read_text())
    assert report["status"] == "failed_or_interrupted_no_subset_score" and "scores" not in report


def test_worker_byte_budget_applies_before_writing(tmp_path):
    path = tmp_path / "bounded.jsonl"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        with pytest.raises(ValueError, match="before write"):
            w.bounded_event(stream, {"value": "é" * 10}, limit=15)
        assert path.stat().st_size == 0


def test_actual_84_session_report_exceeds_legacy_writer_but_fits_declared_bound(tmp_path):
    from ai_trader.training.advisory_training_run import _write as legacy_write

    truth = [r.controls.balance.forecast(state) for state in r.training.STATES for _ in range(27)]
    idle = [r.controls.balance.forecast("NNN")] * len(truth)
    unit = r.controls.detailed_metrics(truth, idle)
    invalid = r.controls.detailed_metrics(truth, [None] * len(truth))
    models = {
        "base": invalid,
        "adapter": unit,
        "no_opportunity": unit,
        "inner_fit_joint_prior": unit,
    }
    report = {
        "scores": models,
        "per_session_scores": {f"train:session_{i:03}": models for i in range(84)},
    }
    encoded_size = len((canonical(report) + "\n").encode())
    assert 1024**2 < encoded_size < r.MAX_BYTES
    with pytest.raises(ValueError, match="budget"):
        legacy_write(tmp_path / "legacy.json", report)
    assert not (tmp_path / "legacy.json").exists()
    path = tmp_path / "full-report.json"
    r.write_artifact(path, report)
    assert r.previous.tokens.metadata(path, pin(path)) == report
    with pytest.raises(FileExistsError):
        r.write_artifact(path, report)


def test_metadata_budget_uses_utf8_and_refuses_before_file_creation(tmp_path):
    path = tmp_path / "too-large.json"
    with pytest.raises(ValueError, match="before write"):
        r.write_artifact(path, {"value": "é" * (r.MAX_BYTES // 2)})
    assert not path.exists()


def test_native_result_saved_before_transport_and_required_for_verification(packet, monkeypatch):
    request = packet[0]
    install(packet, monkeypatch)
    directory = Path(request["output_dir"])
    result = w.respond(canonical(request).encode())
    path = directory / "gpu_result.json"
    assert path.exists()
    path.unlink()
    with pytest.raises(ValueError):
        r.validate_result(result, request, directory)
