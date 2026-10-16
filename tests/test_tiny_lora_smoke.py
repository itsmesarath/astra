"""Core protocol tests are offline/fake; the explicit native CLI supplies numerical evidence."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.training import _tiny_lora_worker as worker
from ai_trader.training import tiny_lora_smoke as smoke
from ai_trader.training.advisory_training_run import _lock_pin, _write, runtime_manifest
from ai_trader.training.lora_backend import adapter_manifest

LOCK = Path(__file__).resolve().parents[1] / "requirements/qwen-training-win-py312.txt"
PIN = hashlib.sha256(LOCK.read_bytes()).hexdigest()


@pytest.fixture
def smoke_request(tmp_path):
    return {
        "enable_native_smoke": True,
        "python_executable": str(Path(sys.executable).resolve()),
        "output_dir": str(tmp_path / "new-run"),
        "dependency_lock": str(LOCK),
        "dependency_lock_sha256": PIN,
        "source_sha256": smoke.source_sha256(),
    }


def make_result(smoke_request):
    directory = Path(smoke_request["output_dir"]) / "adapter"
    directory.mkdir()
    (directory / "adapter_config.json").write_text("{}", encoding="utf-8")
    # Fake bytes for parent protocol validation only, NOT a usable native adapter.
    (directory / "adapter_model.safetensors").write_bytes(b"fake-test-adapter")
    runtime = runtime_manifest()
    pins = _lock_pin(LOCK, PIN)
    runtime["packages"] = {name: pins[name] for name in runtime["packages"]}
    return {
        "kind": smoke.KIND,
        "request_sha256": digest(smoke_request),
        "steps": 3,
        "metrics": [{"loss": 4.0, "gradient_norm": 0.1}] * 3,
        "runtime": runtime,
        "base_parameters": 20000,
        "trainable_parameters": 896,
        "base_parameters_unchanged": True,
        "cuda_initialized": False,
        "reload": {
            "adapter_manifest": adapter_manifest(directory),
            "adapter_updated": True,
            "reload_state_equal": True,
            "probe_loss_before": 4.0,
            "probe_loss_after": 4.0,
            "probe_loss_absolute_tolerance": 1e-5,
            "base_checkpoint_unchanged": True,
        },
        **smoke.NO_AUTHORITY,
    }


def launch(smoke_request):
    return smoke.run(
        smoke_request["python_executable"],
        smoke_request["dependency_lock"],
        smoke_request["dependency_lock_sha256"],
        smoke_request["output_dir"],
        enable_native_smoke=smoke_request["enable_native_smoke"],
    )


def test_training_lock_is_self_contained():
    pins = _lock_pin(LOCK, PIN)
    assert len(pins) == 39
    assert pins["peft"] == "0.21.0"
    assert pins["accelerate"] == "1.15.0"
    assert pins["torch"] == "2.14.0+cu132"


def test_synthetic_sequence_has_only_completion_eos_loss():
    record = worker.synthetic_record()
    assert record["input_ids"] == list(range(3, 14)) + [2] * 5
    assert record["labels"] == [-100] * 8 + [11, 12, 13, 2] + [-100] * 4
    assert record["attention_mask"] == [1] * 12 + [0] * 4
    assert worker.TINY_CONFIG["vocab_size"] == 64
    assert worker.TINY_CONFIG["num_hidden_layers"] == 1


def test_no_optional_native_imports():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; import ai_trader.training._tiny_lora_worker; "
            "assert not {'torch', 'peft', 'transformers'} & sys.modules.keys()",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("value", [False, None, 1, "yes"])
def test_opt_in_is_strict_and_precedes_outputs(smoke_request, value):
    smoke_request["enable_native_smoke"] = value
    with pytest.raises(ValueError, match="opt-in"):
        launch(smoke_request)
    assert not Path(smoke_request["output_dir"]).exists()


@pytest.mark.parametrize(
    "key,value",
    [
        ("checkpoint", "forbidden"),
        ("steps", 100),
        ("source_sha256", "f" * 64),
        ("dependency_lock_sha256", "0" * 64),
        ("python_executable", "relative.exe"),
        ("output_dir", "relative-output"),
        ("enable_native_smoke", 1),
    ],
)
def test_worker_rejects_changed_request_before_native_import(
    smoke_request, key, value, monkeypatch
):
    smoke_request[key] = value
    monkeypatch.setattr(worker, "_TinyBackend", lambda: pytest.fail("Native import reached"))
    with pytest.raises(ValueError):
        worker.respond(canonical(smoke_request).encode())


@pytest.mark.parametrize(
    "raw",
    [b"x" * 8193, b'{"enable_native_smoke":true,"enable_native_smoke":true}', b"null", "not bytes"],
)
def test_worker_rejects_bad_protocol(raw):
    with pytest.raises(ValueError):
        worker.respond(raw)


def test_supervisor_dispatches_once_and_persists(smoke_request, monkeypatch):
    calls = []

    def exchange(command, sent, timeout_ms):
        calls.append(command)
        assert command == [smoke_request["python_executable"], "-I", "-m", smoke.WORKER]
        assert timeout_ms == 120_000
        assert json.loads((Path(sent["output_dir"]) / "request.json").read_text()) == sent
        return canonical(make_result(sent))

    monkeypatch.setattr(smoke, "_exchange", exchange)
    report = launch(smoke_request)
    assert report["status"] == "passed"
    assert report["execution_allowed"] is False
    assert report["result"]["steps"] == 3
    assert len(calls) == 1
    with pytest.raises(FileExistsError):
        launch(smoke_request)
    assert len(calls) == 1


@pytest.mark.parametrize("error", [TimeoutError, RuntimeError, KeyboardInterrupt])
def test_failed_child_is_quarantined_without_retry(smoke_request, monkeypatch, error):
    calls = []

    def exchange(*args):
        calls.append(1)
        raise error("synthetic failure")

    monkeypatch.setattr(smoke, "_exchange", exchange)
    with pytest.raises(error):
        launch(smoke_request)
    result = json.loads((Path(smoke_request["output_dir"]) / "run.json").read_text())
    assert result["status"] == "failed_or_interrupted"
    assert result["completed_steps"] is None
    assert result["automatic_retry"] is False
    assert calls == [1]


@pytest.mark.parametrize(
    "key,value",
    [
        ("steps", 2),
        ("steps", True),
        ("cuda_initialized", True),
        ("base_parameters_unchanged", False),
        ("execution_allowed", True),
        ("market_data_used", True),
        ("base_parameters", 100001),
        ("trainable_parameters", 4097),
        ("request_sha256", "0" * 64),
        ("metrics", []),
        ("metrics", [{"loss": -1.0, "gradient_norm": 0.1}] * 3),
    ],
)
def test_parent_rejects_invalid_result(smoke_request, monkeypatch, key, value):
    def exchange(command, sent, timeout):
        result = make_result(sent)
        result[key] = value
        return canonical(result)

    monkeypatch.setattr(smoke, "_exchange", exchange)
    with pytest.raises(ValueError):
        launch(smoke_request)
    assert (
        json.loads((Path(smoke_request["output_dir"]) / "run.json").read_text())["status"]
        != "passed"
    )


@pytest.mark.parametrize("mutation", ["reload", "manifest", "runtime", "nonfinite"])
def test_parent_rechecks_reload_files_and_runtime(smoke_request, mutation):
    directory = Path(smoke_request["output_dir"])
    directory.mkdir()
    result = copy.deepcopy(make_result(smoke_request))
    if mutation == "reload":
        result["reload"]["probe_loss_after"] = 9.0
    elif mutation == "manifest":
        (directory / "adapter" / "adapter_model.safetensors").write_bytes(b"changed")
    elif mutation == "runtime":
        result["runtime"]["packages"]["peft"] = "0.0.0"
    else:
        result["metrics"][0]["loss"] = float("nan")
    with pytest.raises(ValueError):
        smoke.validate_result(result, smoke_request, directory)


@pytest.mark.parametrize("failure", ["versions", "offline", "persisted", "existing"])
def test_worker_checks_runtime_and_ownership_before_native(smoke_request, monkeypatch, failure):
    pins = smoke.validate_request(smoke_request)
    monkeypatch.setattr(worker, "version", lambda name: pins[name])
    monkeypatch.setattr(worker, "_TinyBackend", lambda: pytest.fail("Native import reached"))
    for name in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        monkeypatch.setenv(name, "1")
    directory = Path(smoke_request["output_dir"])
    directory.mkdir()
    _write(directory / "request.json", smoke_request if failure != "persisted" else {})
    if failure == "versions":
        monkeypatch.setattr(worker, "version", lambda name: "0.0.0")
    elif failure == "offline":
        monkeypatch.delenv("HF_HUB_OFFLINE")
    elif failure == "existing":
        (directory / "steps.jsonl").touch()
    with pytest.raises(ValueError):
        worker.respond(canonical(smoke_request).encode())
    assert not (directory / "adapter").exists()


def test_worker_durable_steps_use_fixed_backend(smoke_request, monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")  # Restore the original process env at teardown.
    pins = smoke.validate_request(smoke_request)
    monkeypatch.setattr(worker, "version", lambda name: pins[name])
    for name in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        monkeypatch.setenv(name, "1")
    directory = Path(smoke_request["output_dir"])
    directory.mkdir()
    _write(directory / "request.json", smoke_request)
    calls = []

    def step(record):
        assert os.environ["CUDA_VISIBLE_DEVICES"] == "-1"
        events = [json.loads(line) for line in (directory / "steps.jsonl").read_text().splitlines()]
        assert events[-1] == {"event": "step_intent", "step": len(calls) + 1}
        assert record == worker.synthetic_record()
        calls.append(1)
        return {"loss": 4.0, "gradient_norm": 0.1}

    backend = SimpleNamespace(
        step=step,
        verify_base=lambda: None,
        base_parameters=20000,
        trainable_parameters=896,
        save_reload=lambda path, record: make_result(smoke_request)["reload"],
        torch=SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda: False)),
    )

    def initialize():
        assert os.environ["CUDA_VISIBLE_DEVICES"] == "-1"
        return backend

    monkeypatch.setattr(worker, "_TinyBackend", initialize)
    result = worker.respond(canonical(smoke_request).encode())
    assert result["steps"] == len(calls) == 3
    events = [json.loads(line) for line in (directory / "steps.jsonl").read_text().splitlines()]
    assert events[-1] == {"event": "save_reload_completed"}
    assert len(events) == 9
