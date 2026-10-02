"""Fake native backends only; an explicit bounded CLI run supplies GPU evidence."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_advisory_training_run import launch as launch
from test_local_checkpoint import ARCHITECTURE

from ai_trader.models.local_checkpoint import canonical, digest, inspect_checkpoint
from ai_trader.models.local_reviewer import LocalReviewError
from ai_trader.training import _qwen_gpu_smoke_worker as w
from ai_trader.training import advisory_training_run as market
from ai_trader.training import qwen_gpu_smoke as s
from ai_trader.training.lora_backend import adapter_manifest

LOCK = Path(__file__).resolve().parents[1] / "requirements/qwen-training-win-py312.txt"
LOCK_PIN = hashlib.sha256(LOCK.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(canonical(value) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def gpu_request(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    write(base / "config.json", ARCHITECTURE)
    write(base / "tokenizer.json", {})
    write(base / "tokenizer_config.json", {})
    (base / "model.safetensors").write_bytes(b"fake-unloadable-test-weights")
    runtime = market.runtime_manifest()
    pins = market._lock_pin(LOCK, LOCK_PIN)
    runtime["packages"] = {name: pins[name] for name in runtime["packages"]}
    runtime_path = tmp_path / "runtime.json"
    runtime_pin = write(runtime_path, runtime)
    return {
        "enable_gpu_smoke": True,
        "python_executable": str(Path(sys.executable).resolve()),
        "output_dir": str(tmp_path / "new-smoke"),
        "checkpoint": str(base),
        "checkpoint_sha256": digest(inspect_checkpoint(base, "Qwen/Qwen3-4B-Base")),
        "dependency_lock": str(LOCK),
        "dependency_lock_sha256": LOCK_PIN,
        "runtime_manifest": str(runtime_path),
        "runtime_sha256": runtime_pin,
        "source_sha256": s.source_sha256(),
        "profile": s.profile(),
    }


def invoke_gpu(gpu_request):
    return s.run(
        gpu_request["python_executable"],
        gpu_request["checkpoint"],
        gpu_request["checkpoint_sha256"],
        gpu_request["dependency_lock"],
        gpu_request["dependency_lock_sha256"],
        gpu_request["runtime_manifest"],
        gpu_request["runtime_sha256"],
        gpu_request["output_dir"],
        enable_gpu_smoke=gpu_request["enable_gpu_smoke"],
    )


def gpu_resources():
    return {
        "device": "FAKE GPU",
        "total_bytes": 16 * 1024**3,
        "peak_allocated_bytes": 9 * 1024**3,
        "peak_reserved_bytes": 10 * 1024**3,
        "cuda_bf16": True,
        "deterministic_algorithms": True,
        "tf32_enabled": False,
    }


def reload_result(directory):
    adapter = directory / "adapter"
    adapter.mkdir()
    (adapter / "adapter_model.safetensors").write_bytes(b"fake-native-adapter")
    write(adapter / "adapter_config.json", {})
    return {
        "adapter_manifest": adapter_manifest(adapter),
        "adapter_updated": True,
        "reload_state_equal": True,
        "probe_loss_before": 1.0,
        "probe_loss_after": 1.0,
        "probe_loss_absolute_tolerance": 1e-5,
        "base_checkpoint_unchanged": True,
    }


def fake_result(gpu_request):
    directory = Path(gpu_request["output_dir"])
    metrics = [{"loss": 1.0, "gradient_norm": 0.5}] * s.STEPS
    events = [
        {"event": "native_initialization_started"},
        {"event": "native_initialization_completed"},
    ]
    for step, metric in enumerate(metrics, 1):
        events.extend(
            [
                {"event": "step_intent", "step": step},
                {"event": "step_completed", "step": step, **metric},
            ]
        )
    events.extend([{"event": "save_reload_started"}, {"event": "save_reload_completed"}])
    (directory / "steps.jsonl").write_text(
        "".join(canonical(event) + "\n" for event in events), encoding="utf-8"
    )
    return {
        "kind": s.KIND,
        "request_sha256": digest(gpu_request),
        "steps": s.STEPS,
        "metrics": metrics,
        "runtime": json.loads(Path(gpu_request["runtime_manifest"]).read_text()),
        "resources": gpu_resources(),
        "trainable_parameters": 200,
        "frozen_parameter_guards_passed": True,
        "reload": reload_result(directory),
        **s.NO_AUTHORITY,
    }


def test_full_length_synthetic_sequence_is_completion_only_and_not_a_market_task():
    record = s.synthetic_record()
    assert len(record["input_ids"]) == 2304
    assert record["attention_mask"] == [1] * 2304
    assert record["labels"][:2048] == [-100] * 2048
    assert record["labels"][2048:] == record["input_ids"][2048:]
    assert record["input_ids"][-1] == 151643
    assert s.profile()["synthetic_record_sha256"] == digest(record)
    assert s.profile()["max_optimizer_steps"] == 3
    assert s.profile()["market_training_authorized"] is False


def test_optional_libraries_not_imported_and_gates_are_separate():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; import ai_trader.training._qwen_gpu_smoke_worker; "
            "assert not {'torch','transformers','peft'} & sys.modules.keys()",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("value", [False, None, 1, "yes"])
def test_strict_opt_in_before_outputs_or_dispatch(gpu_request, value, monkeypatch):
    gpu_request["enable_gpu_smoke"] = value
    monkeypatch.setattr(s, "_exchange", lambda *a: pytest.fail("unexpected GPU dispatch"))
    with pytest.raises(ValueError, match="opt-in"):
        invoke_gpu(gpu_request)
    assert not Path(gpu_request["output_dir"]).exists()


@pytest.mark.parametrize(
    "change",
    ["checkpoint_pin", "lock_pin", "runtime_pin", "source", "profile", "extra_dataset", "overlap"],
)
def test_changed_request_refused_before_optional_import(gpu_request, change, monkeypatch):
    if change in ("checkpoint_pin", "lock_pin", "runtime_pin", "source"):
        key = {
            "checkpoint_pin": "checkpoint_sha256",
            "lock_pin": "dependency_lock_sha256",
            "runtime_pin": "runtime_sha256",
            "source": "source_sha256",
        }[change]
        gpu_request[key] = "f" * 64
    elif change == "profile":
        gpu_request["profile"]["max_optimizer_steps"] = 100
    elif change == "extra_dataset":
        gpu_request["dataset"] = "forbidden"
    else:
        gpu_request["output_dir"] = str(Path(gpu_request["checkpoint"]) / "adapter")
    monkeypatch.setattr(w, "create_backend", lambda *a: pytest.fail("unexpected native import"))
    with pytest.raises(ValueError):
        w.respond(canonical(gpu_request).encode())


@pytest.mark.parametrize(
    "raw",
    [
        b"x" * (s.MAX_REQUEST_BYTES + 1),
        b"null",
        b'{"enable_gpu_smoke":true,"enable_gpu_smoke":true}',
        "not bytes",
    ],
)
def test_invalid_worker_request(raw):
    with pytest.raises(ValueError):
        w.respond(raw)


def test_supervisor_dispatches_once_rechecks_files_and_cannot_resume(gpu_request, monkeypatch):
    calls = []

    def exchange(command, sent, timeout):
        calls.append(command)
        assert command == [sent["python_executable"], "-I", "-m", s.WORKER]
        assert timeout == 600_000
        assert json.loads((Path(sent["output_dir"]) / "request.json").read_text()) == sent
        return canonical(fake_result(sent))

    monkeypatch.setattr(s, "_exchange", exchange)
    report = invoke_gpu(gpu_request)
    assert report["status"] == "passed_synthetic_gpu_capability_only"
    assert report["adapter_approved_for_inference"] is False
    assert len(calls) == 1
    with pytest.raises(FileExistsError):
        invoke_gpu(gpu_request)
    assert len(calls) == 1


@pytest.mark.parametrize("error", [TimeoutError, LocalReviewError, KeyboardInterrupt])
def test_failure_is_quarantined_no_retry_or_known_step_claim(gpu_request, monkeypatch, error):
    calls = []

    def exchange(*args):
        calls.append(1)
        raise error("safe-test-error")

    monkeypatch.setattr(s, "_exchange", exchange)
    with pytest.raises(error):
        invoke_gpu(gpu_request)
    report = json.loads((Path(gpu_request["output_dir"]) / "run.json").read_text())
    assert report["completed_steps"] is None and report["adapter_quarantined"]
    assert report["automatic_retry"] is False and calls == [1]


@pytest.mark.parametrize(
    "change",
    [
        "steps",
        "authority",
        "metrics",
        "reload",
        "adapter_bytes",
        "resources",
        "runtime",
        "journal",
        "checkpoint_bytes",
        "negative_gradient",
    ],
)
def test_parent_refuses_invalid_native_evidence(gpu_request, monkeypatch, change):
    def exchange(command, sent, timeout):
        result = fake_result(sent)
        if change == "steps":
            result["steps"] = True
        elif change == "authority":
            result["market_data_used"] = True
        elif change == "metrics":
            result["metrics"] = []
        elif change == "reload":
            result["reload"]["probe_loss_after"] = 2.0
        elif change == "adapter_bytes":
            (Path(sent["output_dir"]) / "adapter/adapter_model.safetensors").write_bytes(b"changed")
        elif change == "resources":
            result["resources"]["cuda_bf16"] = False
        elif change == "runtime":
            result["runtime"]["packages"]["peft"] = "0.0"
        elif change == "journal":
            (Path(sent["output_dir"]) / "steps.jsonl").write_text("{}\n")
        elif change == "checkpoint_bytes":
            (Path(sent["checkpoint"]) / "model.safetensors").write_bytes(b"changed")
        else:
            result["metrics"][0]["gradient_norm"] = -1
        return canonical(result)

    monkeypatch.setattr(s, "_exchange", exchange)
    with pytest.raises(ValueError):
        invoke_gpu(gpu_request)
    report = json.loads((Path(gpu_request["output_dir"]) / "run.json").read_text())
    assert report["status"] == "failed_or_interrupted"


def install_worker(gpu_request, monkeypatch):
    pins, runtime = s.validate_request(gpu_request)
    monkeypatch.setattr(w, "runtime_manifest", lambda: copy.deepcopy(runtime))
    monkeypatch.setattr(w, "version", lambda name: pins[name])
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        monkeypatch.setenv(key, "1")
    directory = Path(gpu_request["output_dir"])
    directory.mkdir()
    write(directory / "request.json", gpu_request)
    return directory


@pytest.mark.parametrize("failure", ["version", "offline", "persisted", "existing"])
def test_worker_intake_failure_before_native(gpu_request, monkeypatch, failure):
    directory = install_worker(gpu_request, monkeypatch)
    monkeypatch.setattr(w, "create_backend", lambda *a: pytest.fail("unexpected native import"))
    if failure == "version":
        monkeypatch.setattr(w, "version", lambda name: "0.0")
    elif failure == "offline":
        monkeypatch.delenv("HF_HUB_OFFLINE")
    elif failure == "persisted":
        write(directory / "request.json", {})
    else:
        (directory / "steps.jsonl").touch()
    with pytest.raises(ValueError):
        w.respond(canonical(gpu_request).encode())
    assert not (directory / "adapter").exists()


def fake_backend(directory, fail=False):
    adapter = SimpleNamespace(
        requires_grad=True, grad=None, device=SimpleNamespace(type="cuda"), numel=lambda: 200
    )
    base = SimpleNamespace(
        requires_grad=False, grad=None, device=SimpleNamespace(type="cuda"), numel=lambda: 1000
    )
    model = SimpleNamespace(
        parameters=lambda: [adapter, base],
        named_parameters=lambda: [
            ("model.q_proj.lora_A.default.weight", adapter),
            ("base.weight", base),
        ],
    )

    def step(record):
        events = [json.loads(line) for line in (directory / "steps.jsonl").read_text().splitlines()]
        assert events[-1]["event"] == "step_intent"
        assert record == s.synthetic_record()
        if fail:
            raise RuntimeError("synthetic failure")
        return {"loss": 1.0, "gradient_norm": 0.5}

    def reload(path, record):
        adapter.requires_grad = False
        return reload_result(path.parent)

    return SimpleNamespace(model=model, step=step, save_reload=reload)


def test_worker_native_loop_has_fixed_sequence_and_durable_evidence(gpu_request, monkeypatch):
    directory = install_worker(gpu_request, monkeypatch)
    monkeypatch.setattr(w, "create_backend", lambda req: fake_backend(directory))
    monkeypatch.setattr(w, "resources", lambda backend: gpu_resources())
    result = w.respond(canonical(gpu_request).encode())
    s.validate_result(result, gpu_request, directory)
    assert result["steps"] == 3 and result["trainable_parameters"] == 200
    assert all(result[key] is False for key in s.NO_AUTHORITY)


def test_worker_error_retains_stage_without_exception_message_or_retry(gpu_request, monkeypatch):
    directory = install_worker(gpu_request, monkeypatch)
    monkeypatch.setattr(w, "create_backend", lambda req: fake_backend(directory, fail=True))
    with pytest.raises(RuntimeError):
        w.respond(canonical(gpu_request).encode())
    failure = json.loads((directory / "failure.json").read_text())
    assert failure["stage"] == "optimizer_step_1"
    assert failure["completed_steps_unverified"] == 0
    assert failure["error_type"] == "RuntimeError"
    assert failure["adapter_quarantined"] and not failure["automatic_retry"]
    assert not (directory / "adapter").exists()


def test_frozen_base_gradient_or_cpu_placement_refuses(tmp_path):
    backend = fake_backend(tmp_path)
    base = backend.model.parameters()[1]
    base.grad = "forbidden"
    with pytest.raises(ValueError, match="frozen"):
        w.verify_frozen_parameters(backend)
    base.grad = None
    base.device.type = "cpu"
    with pytest.raises(ValueError, match="CUDA"):
        w.verify_frozen_parameters(backend)


def test_existing_market_training_gate_still_requires_nonempty_protected_reservation(launch):
    plan = launch
    inputs = copy.deepcopy(plan["inputs"])
    registry = Path(inputs["registry"]["path"])
    record = json.loads(registry.read_text())
    record["cases"] = []
    inputs["registry"]["sha256"] = write(registry, record)
    with pytest.raises(ValueError, match="protected-evaluation"):
        market.prepare_run(
            inputs,
            plan["checkpoint"],
            plan["checkpoint_sha256"],
            plan["tokenizer_sha256"],
            plan["output_dir"],
        )
