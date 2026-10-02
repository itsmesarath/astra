"""Fake paired inference only; no native model, raw archive, protected data or trades."""

import copy
import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_qwen_gpu_smoke import gpu_request as gpu_request
from test_qwen_gpu_smoke import gpu_resources
from test_six_e_forecast import observation
from test_six_e_lora_trial import dispatched_result, pin, write
from test_six_e_lora_trial import trial_request as trial_request

from ai_trader.models import _six_e_forecast_worker as w
from ai_trader.models.local_checkpoint import canonical
from ai_trader.models.local_reviewer import LocalReviewError
from ai_trader.research import six_e_forecast_eval as e
from ai_trader.training import prepare_6e_qwen_data as builder


@pytest.fixture
def candidate(trial_request):
    request = copy.deepcopy(trial_request)
    dataset = Path(request["dataset"])
    samples = [
        builder.example(
            observation(day=day, offset=i * 60, move=5 if i % 2 else -5), "validation_development"
        )[0]
        for day in ("2025-09-01", "2025-09-02")
        for i in range(40)
    ]
    path = dataset / "validation_development.jsonl"
    path.write_text("".join(canonical(row) + "\n" for row in samples), encoding="utf-8")
    receipt = json.loads((dataset / "completion.json").read_text())
    receipt["files"][path.name] = {
        "count": len(samples),
        "bytes": path.stat().st_size,
        "sha256": pin(path),
    }
    receipt["by_role"]["validation_development"] = {"supervised": len(samples)}
    request["dataset_sha256"] = write(dataset / "completion.json", receipt)
    token = json.loads(Path(request["token_preflight"]).read_text())
    token["dataset_completion_sha256"] = request["dataset_sha256"]
    request["token_preflight_sha256"] = write(Path(request["token_preflight"]), token)
    reservation = json.loads(Path(request["reservation"]).read_text())
    reservation["dataset_completion_sha256"] = request["dataset_sha256"]
    request["reservation_sha256"] = write(Path(request["reservation"]), reservation)
    directory = Path(request["output_dir"])
    result = dispatched_result(request)
    report = {
        "status": "completed_20_update_market_trial_not_validated",
        "adapter_quarantined": True,
        "full_training_epoch": False,
        "result": result,
        **e.trial.NO_AUTHORITY,
    }
    request_pin = write(directory / "request.json", request)
    report_pin = write(directory / "run.json", report)
    return directory, request_pin, report_pin


@pytest.fixture
def frozen(candidate):
    directory, request_pin, report_pin = candidate
    path = directory.parent / "eval-registration.json"
    value = e.freeze(directory, request_pin, report_pin, path)
    return path, pin(path), value


@pytest.fixture
def packet(frozen):
    path, frozen_pin, _ = frozen
    value, request, receipt = e.registration(path, frozen_pin)
    chosen = e.selected_rows(value, request, receipt)
    return e.worker_packet(
        request, Path(value["trial_directory"]), frozen_pin, chosen, path.parent / "new-eval"
    )


def noop():
    return dict.fromkeys(e.COST_KEYS, "neither_positive")


class FakeBackend:
    def __init__(self):
        self.calls = []

    def guard(self):
        return None

    def predict(self, ids, mode):
        self.calls.append((list(ids), mode))
        return {
            "raw_response": canonical(noop()) if mode == "adapter" else "not JSON",
            "generated_tokens": 20,
            "stop_reason": "eos",
        }


def install_worker(packet, monkeypatch):
    runtime = json.loads(Path(packet["runtime_manifest"]).read_text())
    pins = e._lock_pin(Path(packet["dependency_lock"]), packet["dependency_lock_sha256"])
    monkeypatch.setattr(w, "runtime_manifest", lambda: runtime)
    monkeypatch.setattr(w, "version", lambda name: pins[name])
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        monkeypatch.setenv(key, "1")
    monkeypatch.setattr(w, "load_tokenizer", lambda *args: lambda text: [10, 11])
    backend = FakeBackend()
    monkeypatch.setattr(w, "create_backend", lambda *args: backend)
    monkeypatch.setattr(w, "resources", lambda *args: gpu_resources())
    return backend


def invoke_worker(packet):
    directory = Path(packet["output_dir"])
    directory.mkdir()
    write(directory / "request.json", packet)
    return w.respond(canonical(packet).encode())


def test_pure_imports_no_native_dbn_dependencies():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; from ai_trader.research import six_e_forecast_eval; "
            "from ai_trader.models import _six_e_forecast_worker; "
            "assert not ({'torch', 'peft', 'transformers', 'tokenizers', "
            "'databento', 'databento_dbn'} & set(sys.modules))",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_fixed_sample_and_controls_protocol():
    assert e.indices(40) == list(range(40))
    actual = e.indices(7810)
    assert actual == [i * 7809 // 39 for i in range(40)] and len(set(actual)) == 40
    assert e.protocol()["inference"]["constrained_decoding"] is False
    assert e.protocol()["inference"]["do_sample"] is False
    assert e.protocol()["role"] == "validation_development"
    assert all(e.protocol()[key] is False for key in e.FLAGS)


@pytest.mark.parametrize("count", [39, True, 50001, None])
def test_invalid_support_refused(count):
    with pytest.raises(ValueError):
        e.indices(count)


def test_freeze_does_not_open_development_labels_or_reserved_members(candidate, monkeypatch):
    directory, request_pin, report_pin = candidate
    old = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name not in {
            "validation_development.jsonl",
            "test_development.jsonl",
            "unavailable.jsonl",
        }
        assert path.suffix not in {".dbn", ".zip"}
        return old(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    output = directory.parent / "frozen-before-labels.json"
    value = e.freeze(directory, request_pin, report_pin, output)
    assert value["training_prior"]["examples"] == 36
    assert len(value["example_indices"]) == 40
    # Ties come from train alone; use a coherent joint target instead of per-cost modes.
    assert value["training_prior"]["joint_mode"]["extra_1_tick"] == "long_positive"
    with pytest.raises(FileExistsError):
        e.freeze(directory, request_pin, report_pin, output)


def test_feature_payload_cannot_access_poison_target_or_metadata(packet):
    e.validate_packet(packet)
    assert set(packet) == set(e.PACKET_FIELDS)
    assert "dataset" not in packet and "trial_directory" not in packet
    fake = {
        **packet["selection"][0],
        "completion": object(),
        "target_sha256": object(),
        "source_session": object(),
        "contract": object(),
        "role": object(),
    }
    assert e.feature_selection([fake]) == [packet["selection"][0]]
    assert set(packet["selection"][0]) == {"case_id", "input_sha256", "prompt"}


@pytest.mark.parametrize(
    "change",
    [
        "target",
        "source",
        "sample",
        "prompt",
        "features",
        "duplicate",
        "adapter",
        "base",
        "authority",
    ],
)
def test_packet_tampering_refused(packet, change):
    bad = copy.deepcopy(packet)
    if change == "target":
        bad["selection"][0]["completion"] = canonical(noop())
    elif change == "source":
        bad["source_sha256"] = "0" * 64
    elif change == "sample":
        bad["selection"].pop()
    elif change == "prompt":
        bad["selection"][0]["prompt"] += "future price"
    elif change == "features":
        bad["selection"][0]["input_sha256"] = "0" * 64
    elif change == "duplicate":
        bad["selection"][1] = copy.deepcopy(bad["selection"][0])
    elif change == "adapter":
        (Path(bad["adapter"]) / "adapter_model.safetensors").write_bytes(b"changed")
    elif change == "base":
        (Path(bad["checkpoint"]) / "model.safetensors").write_bytes(b"changed")
    else:
        bad["protocol"]["trading_enabled"] = True
    with pytest.raises(ValueError):
        e.validate_packet(bad)


@pytest.mark.parametrize("change", ["role", "sample", "prior", "authority"])
def test_registration_rehash_cannot_expand_or_reselect_scope(frozen, change):
    path, _, value = frozen
    bad = copy.deepcopy(value)
    if change == "role":
        bad["protocol"]["role"] = "test_reserved"
    elif change == "sample":
        bad["example_indices"][1] += 1
    elif change == "prior":
        bad["training_prior"]["joint_mode"] = noop()
    else:
        bad["promotion_allowed"] = True
    with pytest.raises(ValueError):
        e.registration(path, write(path, bad))


def test_test_or_reserved_reader_refused_before_file_access(monkeypatch):
    monkeypatch.setattr(Path, "open", lambda *args, **kwargs: pytest.fail("file opened"))
    for role in ("test_development", "test_reserved", "lockbox_reserved", "unavailable"):
        with pytest.raises(ValueError, match="Only train"):
            list(e.rows(Path("not-opened"), role, {}))


def test_wrong_role_gate_before_prompt_target(candidate):
    request = json.loads((candidate[0] / "request.json").read_text())
    directory = Path(request["dataset"])
    path = directory / "validation_development.jsonl"
    path.write_text(canonical({"role": "reserved"}) + "\n", encoding="utf-8")
    receipt = {
        "files": {path.name: {"count": 1, "bytes": path.stat().st_size, "sha256": pin(path)}}
    }
    with pytest.raises(ValueError, match="Role gate"):
        list(e.rows(directory, "validation_development", receipt))


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not JSON",
        "```json\n{}\n```",
        '{"extra_1_tick":"long_positive","extra_1_tick":"short_positive"}',
        '{"extra_1_tick":"neither_positive","extra_2_ticks":"long_positive","extra_4_ticks":"neither_positive"}',
        '{"extra_1_tick":"buy","extra_2_ticks":"buy","extra_4_ticks":"buy"}',
    ],
)
def test_invalid_predictions_not_repaired_or_relabeled(text):
    assert e.forecast({"raw_response": text, "stop_reason": "eos"}) == (
        None,
        "invalid_json_or_contract",
    )


def test_token_limit_refused_even_if_decoded_json_closed():
    assert e.forecast({"raw_response": canonical(noop()), "stop_reason": "token_limit"}) == (
        None,
        "token_limit",
    )


def test_metrics_include_invalid_as_incorrect_and_directional_miss():
    long = dict.fromkeys(e.COST_KEYS, "long_positive")
    short = dict.fromkeys(e.COST_KEYS, "short_positive")
    truth = [long, short, noop(), noop()]
    result = e.metrics(truth, [long, None, noop(), short])
    assert result["coverage"] == 0.75
    score = result["by_cost"]["extra_1_tick"]
    assert score["overall_accuracy"] == 0.5 and score["accuracy_on_valid"] == 2 / 3
    assert score["confusion"]["short_positive"]["invalid"] == 1
    assert score["directional_precision"] == 0.5 and score["directional_recall"] == 0.5
    assert score["per_class"]["short_positive"]["recall"] == 0
    assert score["balanced_accuracy_over_supported_classes"] == 0.5


def test_all_invalid_and_absent_class_metrics_not_false_certainty():
    result = e.metrics([noop(), noop()], [None, None])
    assert result["coverage"] == 0
    score = result["by_cost"]["extra_1_tick"]
    assert score["overall_accuracy"] == 0 and score["accuracy_on_valid"] is None
    assert score["directional_precision"] is None and score["directional_recall"] is None
    assert score["supported_classes"] == ["neither_positive"]
    assert score["macro_f1_over_supported_classes"] == 0


@pytest.mark.parametrize("opt_in", [False, None, 1, "yes"])
def test_optin_before_any_input_read(monkeypatch, opt_in):
    monkeypatch.setattr(e, "registration", lambda *args: pytest.fail("input read"))
    with pytest.raises(ValueError):
        e.run(Path("not-read"), "a" * 64, Path("not-created"), enable_development_evaluation=opt_in)


def test_paired_worker_then_scoring_one_dispatch_no_retry(frozen, packet, monkeypatch):
    path, frozen_pin, _ = frozen
    backend = install_worker(packet, monkeypatch)
    calls = []

    def dispatch(command, request, timeout):
        calls.append((command, timeout))
        assert command[-1] == e.WORKER and timeout == 600_000
        assert "dataset" not in request and all(
            "completion" not in item for item in request["selection"]
        )
        return canonical(w.respond(canonical(request).encode()))

    monkeypatch.setattr(e, "_exchange", dispatch)
    report = e.run(path, frozen_pin, Path(packet["output_dir"]), enable_development_evaluation=True)
    assert report["status"] == "completed_exposed_development_diagnostic_not_validation"
    assert report["examples"] == 40 and len(calls) == 1
    assert report["scores"]["base"]["coverage"] == 0
    assert report["scores"]["adapter"]["coverage"] == 1
    assert report["scores"]["adapter"]["by_cost"]["extra_1_tick"]["overall_accuracy"] == 0
    assert report["adapter_quarantined"] and all(report[k] is False for k in e.FLAGS)
    assert (
        len(backend.calls) == 80 and [mode for _, mode in backend.calls] == ["base", "adapter"] * 40
    )
    assert all(backend.calls[i][0] == backend.calls[i + 1][0] for i in range(0, 80, 2))
    with pytest.raises(FileExistsError):
        e.run(path, frozen_pin, Path(packet["output_dir"]), enable_development_evaluation=True)
    assert len(calls) == 1


def test_timeout_retained_no_subset_scoring(frozen, packet, monkeypatch):
    path, frozen_pin, _ = frozen
    calls = []

    def timeout(*args):
        calls.append(1)
        raise LocalReviewError("worker_deadline")

    monkeypatch.setattr(e, "_exchange", timeout)
    with pytest.raises(LocalReviewError):
        e.run(path, frozen_pin, Path(packet["output_dir"]), enable_development_evaluation=True)
    report = json.loads((Path(packet["output_dir"]) / "run.json").read_text())
    assert (
        report["status"] == "failed_or_interrupted_no_subset_score"
        and report["completed_calls"] is None
    )
    assert "scores" not in report and len(calls) == 1 and report["adapter_quarantined"]


@pytest.mark.parametrize(
    "change",
    [
        "partial",
        "frozen",
        "authority",
        "runtime",
        "resources",
        "events",
        "predictions",
        "framing",
        "failure",
    ],
)
def test_partial_or_drifted_evidence_refused(packet, monkeypatch, change):
    install_worker(packet, monkeypatch)
    result = invoke_worker(packet)
    directory = Path(packet["output_dir"])
    if change == "partial":
        result["completed_calls"] = 79
    elif change == "frozen":
        result["parameters_frozen"] = False
    elif change == "authority":
        result["promotion_allowed"] = True
    elif change == "runtime":
        result["runtime"]["packages"]["torch"] = "wrong"
    elif change == "resources":
        result["resources"]["peak_reserved_bytes"] = result["resources"]["total_bytes"] + 1
    elif change == "failure":
        write(directory / "failure.json", {})
    else:
        path = directory / ("events.jsonl" if change == "events" else "predictions.jsonl")
        if change == "framing":
            path.write_bytes(path.read_bytes()[:-1])
        else:
            path.write_text(
                path.read_text().replace(packet["selection"][0]["case_id"], "d" * 64),
                encoding="utf-8",
            )
        result["files"][path.name] = e.file_info(path)
    with pytest.raises(ValueError):
        e.validate_result(result, packet, directory)


@pytest.mark.parametrize("change", ["offline", "version", "saved", "eos", "oversize", "bool_token"])
def test_worker_preflight_before_native_initialization(packet, monkeypatch, change):
    install_worker(packet, monkeypatch)
    directory = Path(packet["output_dir"])
    directory.mkdir()
    write(directory / "request.json", packet)
    if change == "offline":
        monkeypatch.delenv("HF_HUB_OFFLINE")
    elif change == "version":
        monkeypatch.setattr(w, "version", lambda name: "wrong")
    elif change == "saved":
        write(directory / "request.json", {})
    else:
        ids = {"eos": [151643], "oversize": [10] * 2049, "bool_token": [True]}[change]
        monkeypatch.setattr(w, "load_tokenizer", lambda *args: lambda text: ids)
    monkeypatch.setattr(w, "create_backend", lambda *args: pytest.fail("native model loaded"))
    with pytest.raises(ValueError):
        w.respond(canonical(packet).encode())


def test_worker_failure_records_unknown_success_not_private_contents(packet, monkeypatch):
    backend = install_worker(packet, monkeypatch)

    def fail(ids, mode):
        raise RuntimeError("private error contents")

    monkeypatch.setattr(backend, "predict", fail)
    with pytest.raises(RuntimeError):
        invoke_worker(packet)
    path = Path(packet["output_dir"]) / "failure.json"
    failure = json.loads(path.read_text())
    assert failure["stage"] == "prediction_1" and failure["completed_calls_unverified"] == 0
    assert "private error" not in path.read_text() and failure["adapter_quarantined"]


def native_shell(generated):
    """Exercise real prediction control flow with fake tensors/model, no native imports."""
    backend = object.__new__(w.InferenceBackend)
    states, calls = {"adapter": True, "inference": False}, []

    @contextmanager
    def disable():
        states["adapter"] = False
        try:
            yield
        finally:
            states["adapter"] = True
            # Model the observed PEFT runtime behavior, not just adapter enable/disable.
            parameter.requires_grad = True

    @contextmanager
    def inference():
        states["inference"] = True
        try:
            yield
        finally:
            states["inference"] = False

    class FakeTokens(list):
        def __getitem__(self, key):
            return FakeTokens(super().__getitem__(key))

        def tolist(self):
            return list(self)

    def generate(**kwargs):
        calls.append((states.copy(), kwargs["input_ids"]))
        return [FakeTokens([10, 11, *generated])]

    def decode(ids, *, skip_special_tokens):
        assert skip_special_tokens is False
        assert ids == (generated[:-1] if generated[-1] == 151643 else generated)
        return canonical(noop())

    parameter = SimpleNamespace(
        requires_grad=False, grad=None, device=SimpleNamespace(type="cuda"), numel=lambda: 1
    )

    def freeze(flag):
        parameter.requires_grad = flag

    backend.model = SimpleNamespace(
        training=False,
        parameters=lambda: [parameter],
        disable_adapter=disable,
        generate=generate,
        named_parameters=lambda: [("base.layers.0.q_proj.lora_A.default.weight", parameter)],
        requires_grad_=freeze,
    )
    backend.torch = SimpleNamespace(
        tensor=lambda ids, **kwargs: ids,
        ones=lambda *args, **kwargs: "ones",
        long="long",
        inference_mode=inference,
    )
    backend.generation = object()
    backend.tokenizer = SimpleNamespace(decode=decode)
    return backend, calls, parameter


def test_actual_prediction_path_disables_only_base_and_strips_only_terminal_eos():
    backend, calls, _ = native_shell([20, 151643])
    assert backend.predict([10, 11], "base")["stop_reason"] == "eos"
    assert backend.predict([10, 11], "adapter")["generated_tokens"] == 2
    assert calls == [
        ({"adapter": False, "inference": True}, [[10, 11]]),
        ({"adapter": True, "inference": True}, [[10, 11]]),
    ]
    with pytest.raises(ValueError):
        backend.predict([10, 11], "unsupported")


@pytest.mark.parametrize("tokens", [[], [20], [20, 151643, 30], [20] * 49])
def test_actual_generation_framing_refusal(tokens):
    backend, _, _ = native_shell(tokens)
    with pytest.raises(ValueError):
        backend.predict([10, 11], "adapter")


def test_actual_prediction_limit_and_frozen_parameter_guards():
    backend, _, parameter = native_shell([20] * 48)
    value = backend.predict([10, 11], "adapter")
    assert value["stop_reason"] == "token_limit" and e.forecast(value)[0] is None
    parameter.grad = object()
    with pytest.raises(ValueError, match="frozen_parameter_guard"):
        backend.guard()


def test_peft_context_flag_restoration_does_not_hide_base_trainability_or_gradients():
    backend, _, parameter = native_shell([20, 151643])
    backend.predict([10, 11], "base")
    assert parameter.requires_grad is False and parameter.grad is None
    parameter.requires_grad = True
    backend.model.named_parameters = lambda: [("base.layers.0.q_proj.weight", parameter)]
    with pytest.raises(w.InferenceBoundaryError, match="unexpected_adapter_flags"):
        backend.restore_inference_flags()
    assert parameter.requires_grad is True  # Refusal, not silent concealment of a base flag.
    parameter.grad = object()
    with pytest.raises(w.InferenceBoundaryError, match="frozen_parameter_guard"):
        backend.restore_inference_flags()


def test_safe_boundary_error_codes_in_failure_artifact(packet, monkeypatch):
    backend = install_worker(packet, monkeypatch)

    def fail(ids, mode):
        raise w.InferenceBoundaryError("frozen_parameter_guard")

    monkeypatch.setattr(backend, "predict", fail)
    with pytest.raises(w.InferenceBoundaryError):
        invoke_worker(packet)
    failure = json.loads((Path(packet["output_dir"]) / "failure.json").read_text())
    assert failure["error_code"] == "frozen_parameter_guard"
