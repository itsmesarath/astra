"""Synthetic paired/check-only evaluation: no native models, reserved data or fitting."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
import test_six_e_balance_plan as balance_tests
import test_six_e_balanced_lora as training_tests
from test_qwen_gpu_smoke import gpu_resources
from test_six_e_balance_plan import original as original
from test_six_e_balance_plan import samples as samples
from test_six_e_forecast_eval import FakeBackend
from test_six_e_forecast_eval import candidate as candidate
from test_six_e_forecast_eval import trial_request as trial_request
from test_six_e_lora_trial import gpu_request as gpu_request
from test_six_e_lora_trial import pin, write

from ai_trader.models import _six_e_balanced_eval_worker as gpu_worker
from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.models.local_reviewer import LocalReviewError
from ai_trader.research import _six_e_balanced_controls_worker as cpu_worker
from ai_trader.research import six_e_balanced_eval as e

balance_frozen = balance_tests.frozen
balanced_frozen = training_tests.frozen


@pytest.fixture
def trained(balanced_frozen, monkeypatch):
    path, training_pin, _ = balanced_frozen
    directory = path.parent / "balanced-candidate"

    def dispatch(command, packet, timeout):
        training_tests.install(packet, monkeypatch, owned=True)
        return canonical(training_tests.w.respond(canonical(packet).encode()))

    monkeypatch.setattr(e.training, "_exchange", dispatch)
    e.training.run(path, training_pin, directory, enable_research_training=True)
    return (
        path,
        training_pin,
        directory,
        pin(directory / "request.json"),
        pin(directory / "run.json"),
    )


@pytest.fixture
def frozen(trained):
    path = trained[0].parent / "comparison-registration.json"
    value = e.freeze(*trained, path)
    return path, pin(path), value


@pytest.fixture
def packets(frozen):
    path, frozen_pin, registered = frozen
    _, value, _, rows = e.registration(path, frozen_pin)
    chosen = e.selected(value, rows)
    output = path.parent / "comparison"
    return (
        e.gpu_packet(registered, value, chosen, frozen_pin, output),
        e.cpu_packet(registered, value, chosen, frozen_pin, output / "controls"),
        chosen,
    )


def install_gpu(packet, monkeypatch, *, owned=False):
    directory = Path(packet["output_dir"])
    if not owned:
        directory.mkdir()
        write(directory / "request.json", packet)
    pins, runtime = e.validate_gpu_packet(packet)
    monkeypatch.setattr(gpu_worker, "runtime_manifest", lambda: runtime)
    monkeypatch.setattr(gpu_worker, "version", lambda name: pins[name])
    monkeypatch.setattr(gpu_worker, "load_tokenizer", lambda *args: lambda text: [10, 11])
    backend = FakeBackend()
    monkeypatch.setattr(gpu_worker, "create_backend", lambda packet: backend)
    monkeypatch.setattr(gpu_worker, "resources", lambda backend: gpu_resources())
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        monkeypatch.setenv(key, "1")
    return backend


def install_cpu(packet, monkeypatch, *, owned=False):
    directory = Path(packet["output_dir"])
    if not owned:
        directory.mkdir(parents=True, exist_ok=False)
        write(directory / "request.json", packet)
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        monkeypatch.setenv(key, "1")


def test_pure_imports_and_frozen_decoding():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; from ai_trader.research import six_e_balanced_eval; "
            "from ai_trader.models import _six_e_balanced_eval_worker; "
            "from ai_trader.research import _six_e_balanced_controls_worker; "
            "assert not ({'torch','peft','transformers','tokenizers','databento','databento_dbn'} "
            "& set(sys.modules))",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert e.protocol()["pre_training_comparison"] == e.training.protocol()["comparison"]
    assert e.protocol()["pre_training_comparison"]["decoding"]["max_new_tokens"] == 48
    assert e.CASES == 80 and e.TIMEOUT_MS == 600_000
    assert all(e.protocol()[k] is False for k in e.FLAGS)


def test_exact_original_comparison_and_verified_candidate(frozen, trained):
    path, frozen_pin, registered = frozen
    _, value, _, rows = e.registration(path, frozen_pin)
    assert registered["comparison"] == value["comparison"]
    chosen = e.selected(value, rows)
    assert len(chosen) == len({row["case_id"] for row in chosen}) == 80
    assert all(row["source_session"] in value["session_split"]["check"] for row in chosen)
    assert registered["training_registration"]["sha256"] == trained[1]
    assert registered["training_trial"]["report_sha256"] == trained[4]


def test_feature_selection_cannot_access_targets_or_metadata(packets):
    gpu, cpu, _ = packets

    class Poison(dict):
        def __getitem__(self, key):
            assert key in {"case_id", "input_sha256", "prompt"}
            return gpu["selection"][0][key]

    value = {"comparison": [{"prompt_tokens": 2}] * 80}
    assert len(e.feature_selection(value, [Poison()] * 80)) == 80
    for packet in (gpu, cpu):
        assert not (
            {
                "dataset",
                "comparison",
                "training_trial",
                "target_sha256",
                "completion",
                "source_session",
            }
            & set(packet)
        )
        assert all(
            set(item) == {"case_id", "input_sha256", "prompt", "prompt_tokens"}
            for item in packet["selection"]
        )
    assert "models" not in gpu and "checkpoint" not in cpu


@pytest.mark.parametrize(
    "change",
    [
        "source",
        "protocol",
        "authority",
        "selection",
        "extra_target",
        "prompt",
        "identity",
        "tokens",
        "duplicate",
        "asset",
        "overlap",
    ],
)
def test_gpu_packet_changes_refused(packets, change):
    packet = packets[0]
    if change == "source":
        packet["source_sha256"] = "0" * 64
    elif change == "protocol":
        packet["protocol"]["pre_training_comparison"]["decoding"]["max_new_tokens"] = 49
    elif change == "authority":
        packet["enable_development_evaluation"] = 1
    elif change == "selection":
        packet["selection"].pop()
    elif change == "extra_target":
        packet["selection"][-1]["completion"] = "poison target"
    elif change == "prompt":
        packet["selection"][-1]["prompt"] += " future price"
    elif change == "identity":
        packet["selection"][-1]["input_sha256"] = "0" * 64
    elif change == "tokens":
        packet["selection"][-1]["prompt_tokens"] = True
    elif change == "duplicate":
        packet["selection"][-1] = packet["selection"][0]
    elif change == "asset":
        packet["adapter_manifest_sha256"] = "0" * 64
    else:
        packet["output_dir"] = packet["checkpoint"]
    with pytest.raises(ValueError):
        e.validate_gpu_packet(packet)


@pytest.mark.parametrize("change", ["models", "hash", "power", "extra_label", "runtime", "optin"])
def test_cpu_packet_changes_refused(packets, change):
    packet = packets[1]
    if change == "models":
        packet["models"].pop(next(iter(packet["models"])))
    elif change == "hash":
        packet["models_sha256"] = "0" * 64
    elif change == "power":
        packet["models"][next(iter(packet["models"]))]["weight_power"] = True
        packet["models_sha256"] = digest(packet["models"])
    elif change == "extra_label":
        packet["selection"][0]["target_sha256"] = "0" * 64
    elif change == "runtime":
        packet["cpu_runtime"]["extra"] = "changed"
    else:
        packet["enable_development_evaluation"] = False
    with pytest.raises(ValueError):
        e.validate_cpu_packet(packet, parent_required=False)


def test_native_workers_selected_inputs_only_and_no_refit(packets, monkeypatch):
    gpu, cpu, _ = packets
    backend = install_gpu(gpu, monkeypatch)
    original_open = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name not in {
            "train.jsonl",
            "validation_development.jsonl",
            "test_development.jsonl",
            "unavailable.jsonl",
            "models.json",
            "balance-plan.json",
        }
        assert path.suffix not in {".dbn", ".zip"}
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    monkeypatch.setattr(
        e, "candidate", lambda *args: pytest.fail("Worker loaded upstream trial/dataset")
    )
    monkeypatch.setattr(e.balance, "fit", lambda *args: pytest.fail("Controls were refitted"))
    gpu_result = gpu_worker.respond(canonical(gpu).encode())
    install_cpu(cpu, monkeypatch)
    cpu_result = cpu_worker.respond(canonical(cpu).encode())
    assert len(backend.calls) == 160 and gpu_result["completed_calls"] == 160
    assert len(e.validate_gpu_result(gpu_result, gpu, Path(gpu["output_dir"]))) == 160
    assert len(e.validate_cpu_result(cpu_result, cpu, Path(cpu["output_dir"]))) == 160
    assert len(canonical(gpu_result).encode()) < 16 * 1024
    assert len(canonical(cpu_result).encode()) < 16 * 1024


@pytest.mark.parametrize("change", ["offline", "runtime", "tokens", "saved", "stale"])
def test_gpu_preflight_before_loading(packets, monkeypatch, change):
    packet = packets[0]
    install_gpu(packet, monkeypatch)
    if change == "offline":
        monkeypatch.delenv("HF_HUB_OFFLINE")
    elif change == "runtime":
        monkeypatch.setattr(gpu_worker, "version", lambda name: "wrong")
    elif change == "tokens":
        monkeypatch.setattr(gpu_worker, "load_tokenizer", lambda *args: lambda text: [99])
    elif change == "saved":
        write(Path(packet["output_dir"]) / "request.json", {})
    else:
        write(Path(packet["output_dir"]) / "failure.json", {})
    monkeypatch.setattr(
        gpu_worker, "create_backend", lambda *args: pytest.fail("Native model loaded")
    )
    with pytest.raises(ValueError):
        gpu_worker.respond(canonical(packet).encode())


@pytest.mark.parametrize("change", ["offline", "runtime", "saved"])
def test_cpu_preflight_before_prediction(packets, monkeypatch, change):
    packet = packets[1]
    install_cpu(packet, monkeypatch)
    if change == "offline":
        monkeypatch.delenv("HF_HUB_OFFLINE")
    elif change == "runtime":
        packet["cpu_runtime"]["numpy"] = "wrong"
        write(Path(packet["output_dir"]) / "request.json", packet)
    else:
        write(Path(packet["output_dir"]) / "request.json", {})
    with pytest.raises(ValueError):
        cpu_worker.respond(canonical(packet).encode())
    assert not (Path(packet["output_dir"]) / "predictions.jsonl").exists()


def test_native_failure_private_error_retains_stage_no_subset(packets, monkeypatch):
    packet = packets[0]
    backend = install_gpu(packet, monkeypatch)
    original_predict = backend.predict

    def fail_after_three(ids, mode):
        if len(backend.calls) == 3:
            raise RuntimeError("private error must not persist")
        return original_predict(ids, mode)

    monkeypatch.setattr(backend, "predict", fail_after_three)
    with pytest.raises(RuntimeError):
        gpu_worker.respond(canonical(packet).encode())
    raw = (Path(packet["output_dir"]) / "failure.json").read_text()
    assert "private error" not in raw and json.loads(raw)["completed_calls_unverified"] == 3


def test_cpu_failure_after_one_control_never_scores_subset(packets, monkeypatch):
    packet = packets[1]
    install_cpu(packet, monkeypatch)
    original_predict, calls = e.balance.predict, []

    def predict(model, features):
        if len(features) == 80:
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError("private control error")
        return original_predict(model, features)

    monkeypatch.setattr(e.balance, "predict", predict)
    with pytest.raises(RuntimeError):
        cpu_worker.respond(canonical(packet).encode())
    raw = (Path(packet["output_dir"]) / "failure.json").read_text()
    assert "private control" not in raw and json.loads(raw)["completed_predictions_unverified"] == 0
    assert not (Path(packet["output_dir"]) / "predictions.jsonl").exists()


@pytest.mark.parametrize(
    "change",
    ["calls", "summary_flag", "prediction", "event", "framing", "resources", "subset", "adapter"],
)
def test_bad_gpu_result_refused(packets, monkeypatch, change):
    packet = packets[0]
    install_gpu(packet, monkeypatch)
    result = gpu_worker.respond(canonical(packet).encode())
    directory = Path(packet["output_dir"])
    if change == "calls":
        result["completed_calls"] = 159
    elif change == "summary_flag":
        result["promotion_allowed"] = True
    elif change == "resources":
        result["resources"]["tf32_enabled"] = True
    elif change == "adapter":
        (Path(packet["adapter"]) / "adapter_model.safetensors").write_bytes(b"changed")
    else:
        name = "events.jsonl" if change == "event" else "predictions.jsonl"
        path = directory / name
        raw = path.read_bytes()
        if change == "framing":
            raw = raw[:-1]
        elif change == "subset":
            raw = b"\n".join(raw.splitlines()[:-1]) + b"\n"
        else:
            raw = raw.replace(packet["selection"][-1]["case_id"].encode(), b"bad-case")
        path.write_bytes(raw)
        result["files"][name] = e.file_info(path)
    with pytest.raises(ValueError):
        e.validate_gpu_result(result, packet, directory)


@pytest.mark.parametrize("change", ["count", "runtime", "models", "order", "forecast"])
def test_bad_cpu_result_refused(packets, monkeypatch, change):
    packet = packets[1]
    install_cpu(packet, monkeypatch)
    result = cpu_worker.respond(canonical(packet).encode())
    directory = Path(packet["output_dir"])
    if change == "count":
        result["completed_predictions"] = 159
    elif change == "runtime":
        result["cpu_runtime"] = {**result["cpu_runtime"], "numpy": "wrong"}
    elif change == "models":
        result["models_sha256"] = "0" * 64
    else:
        path = directory / "predictions.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if change == "order":
            rows[0], rows[1] = rows[1], rows[0]
        else:
            rows[0]["forecast"]["extra_4_ticks"] = "invalid"
        path.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")
        result["predictions"] = e.file_info(path)
    with pytest.raises(ValueError):
        e.validate_cpu_result(result, packet, directory)


@pytest.mark.parametrize("change", ["comparison", "source", "counts", "authority", "runtime"])
def test_operational_registration_tampering_refused(frozen, change):
    path, _, value = frozen
    value = copy.deepcopy(value)
    if change == "comparison":
        value["comparison"][0]["check_index"] += 1
    elif change == "source":
        value["source_sha256"] = "0" * 64
    elif change == "counts":
        value["inner_fit_joint_counts"]["NNN"] += 1
    elif change == "authority":
        value["promotion_allowed"] = True
    else:
        value["cpu_runtime"]["numpy"] = "wrong"
    with pytest.raises(ValueError):
        e.registration(path, write(path, value))


def test_optin_before_inputs(tmp_path):
    with pytest.raises(ValueError, match="opt-in"):
        e.run(tmp_path / "absent", "bad", tmp_path / "output")
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("failure", [None, "gpu", "cpu", "drift"])
def test_parent_bounded_exact_two_workers_no_retry_or_partial_scores(frozen, monkeypatch, failure):
    path, frozen_pin, _ = frozen
    output = path.parent / "parent-comparison"
    calls = []
    original_registration = e.registration

    def registered(*args):
        if calls and failure == "drift":
            raise ValueError("Inputs changed during comparison")
        return original_registration(*args)

    monkeypatch.setattr(e, "registration", registered)

    def dispatch(command, packet, timeout):
        calls.append((command[-1], timeout))
        if (packet["kind"] == e.KIND and failure == "gpu") or (
            packet["kind"] == e.CPU_KIND and failure == "cpu"
        ):
            raise LocalReviewError("worker_deadline")
        if packet["kind"] == e.KIND:
            install_gpu(packet, monkeypatch, owned=True)
            return canonical(gpu_worker.respond(canonical(packet).encode()))
        install_cpu(packet, monkeypatch, owned=True)
        return canonical(cpu_worker.respond(canonical(packet).encode()))

    monkeypatch.setattr(e, "_exchange", dispatch)
    if failure:
        with pytest.raises((LocalReviewError, ValueError)):
            e.run(path, frozen_pin, output, enable_development_evaluation=True)
        report = json.loads((output / "run.json").read_text())
        assert (
            report["status"] == "failed_or_interrupted_no_subset_score" and "scores" not in report
        )
    else:
        report = e.run(path, frozen_pin, output, enable_development_evaluation=True)
        assert report["examples"] == 80 and report["source_sessions"] == 2
        assert len(report["scores"]) == 6 and len(report["per_session_scores"]) == 2
        assert report["scores"]["base"]["coverage"] == 0
        assert report["scores"]["adapter"]["coverage"] == 1
        assert all(report[k] is False for k in e.FLAGS) and report["adapter_quarantined"]
        with pytest.raises(FileExistsError):
            e.run(path, frozen_pin, output, enable_development_evaluation=True)
    assert calls[0] == (e.GPU_WORKER, 600_000)
    assert len(calls) == (1 if failure == "gpu" else 2)
    if len(calls) == 2:
        assert calls[1] == (e.CPU_WORKER, 30_000)


def test_fixed_control_argmax_uses_fit_counts_and_invalids_are_not_noops(
    frozen, packets, monkeypatch
):
    gpu, cpu, chosen = packets
    install_gpu(gpu, monkeypatch)
    gpu_result = gpu_worker.respond(canonical(gpu).encode())
    install_cpu(cpu, monkeypatch)
    cpu_result = cpu_worker.respond(canonical(cpu).encode())
    result = e.score(
        frozen[2],
        chosen,
        e.validate_gpu_result(gpu_result, gpu, Path(gpu["output_dir"])),
        e.validate_cpu_result(cpu_result, cpu, Path(cpu["output_dir"])),
    )
    assert result["output_status_counts"]["base"] == {"invalid_json_or_contract": 80}
    assert result["scores"]["base"]["by_cost"]["extra_1_tick"]["correct"] == 0
    assert result["scores"]["no_opportunity"]["by_cost"]["extra_1_tick"]["directional_recall"] == 0
    # All fit joint states are equally common: the frozen state tie order chooses NNN.
    assert result["scores"]["inner_fit_joint_prior"] == result["scores"]["no_opportunity"]
