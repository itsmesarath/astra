"""Optional model loading/generation contracts using fakes, not Qwen inference evidence."""

import contextlib
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import pytest

from ai_trader.models import _local_review_worker as worker
from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.models.local_reviewer import LocalReviewerConfig, build_request
from ai_trader.models.review_contracts import LEGACY_V1, SPOT_LONG_V2
from ai_trader.research.council import Evidence, ResearchSnapshot


@pytest.fixture(autouse=True)
def isolated_offline_environment(monkeypatch):
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        monkeypatch.setenv(key, "1")


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    calls = {"length": 10, "response": "synthetic raw output", "cuda": True, "bf16": True}
    manifest = {"synthetic": "manifest, never real model weights"}
    config = LocalReviewerConfig(
        "synthetic",
        backend="transformers",
        model_id="Qwen/Qwen3-4B-Base",
        checkpoint_path=tmp_path,
        checkpoint_sha256=digest(manifest),
    )
    snapshot = ResearchSnapshot(
        "BTCUSDT",
        1000,
        (Evidence("cvd", "BTCUSDT", "synthetic", "rolling_cvd_btc", Decimal("1"), 900, 950),),
    )

    class Tensor:
        @property
        def shape(self):
            return (1, calls["length"])

        def to(self, device):
            calls.setdefault("tensor_devices", []).append(device)
            return self

    class Tokenizer:
        eos_token_id = 151643
        pad_token_id = None

        def __call__(self, prompt, **kwargs):
            calls["prompt"], calls["tokenize"] = prompt, kwargs
            return {"input_ids": Tensor(), "attention_mask": Tensor()}

        def apply_chat_template(self, messages, **kwargs):
            calls["chat"] = (messages, kwargs)
            return "synthetic chat prompt"

        def decode(self, tokens, **kwargs):
            calls["decode"] = (tokens, kwargs)
            return calls["response"]

    class TokenizerLoader:
        @staticmethod
        def from_pretrained(path, **kwargs):
            calls["tokenizer_load"] = (path, kwargs)
            return Tokenizer()

    class Model:
        def to(self, device):
            calls["model_device"] = device
            return self

        def eval(self):
            calls["eval"] = True

        def generate(self, **kwargs):
            calls["generate"] = kwargs
            assert calls["inference_mode"] and calls["eval"]
            return [[0] * calls["length"] + [99]]

    class ModelLoader:
        @staticmethod
        def from_pretrained(path, **kwargs):
            calls["model_load"] = (path, kwargs)
            return Model()

    @contextlib.contextmanager
    def inference_mode():
        calls["inference_mode"] = True
        try:
            yield
        finally:
            calls["inference_mode"] = False

    monkeypatch.setattr(worker, "inspect_checkpoint", lambda *args: manifest)
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            float32="float32",
            bfloat16="bfloat16",
            inference_mode=inference_mode,
            cuda=SimpleNamespace(
                is_available=lambda: calls["cuda"], is_bf16_supported=lambda: calls["bf16"]
            ),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            AutoTokenizer=TokenizerLoader,
            AutoModelForCausalLM=ModelLoader,
            GenerationConfig=SimpleNamespace,
        ),
    )
    return config, snapshot, calls


@pytest.mark.parametrize("device,dtype", [("cpu", "float32"), ("cuda", "bfloat16")])
@pytest.mark.parametrize("model_id", ["Qwen/Qwen3-4B-Base", "Qwen/Qwen3-4B"])
@pytest.mark.parametrize("contract", [LEGACY_V1, SPOT_LONG_V2])
def test_explicit_local_load_and_bounded_generation(runtime, device, dtype, model_id, contract):
    config, snapshot, calls = runtime
    config = replace(
        config, device=device, model_id=model_id, max_new_tokens=123, review_contract=contract
    )
    request = build_request(config, "analyst", snapshot, ())
    result = worker.respond(canonical(request).encode())
    assert result["request_sha256"] == digest(request)
    assert result["raw_response"] == calls["response"]
    assert calls["tokenizer_load"] == (
        str(config.checkpoint_path),
        {
            "local_files_only": True,
            "trust_remote_code": False,
        },
    )
    assert calls["model_load"] == (
        str(config.checkpoint_path),
        {
            "local_files_only": True,
            "trust_remote_code": False,
            "use_safetensors": True,
            "dtype": dtype,
            "attn_implementation": "eager",
        },
    )
    assert calls["tokenize"] == {
        "return_tensors": "pt",
        "truncation": False,
        "add_special_tokens": False,
    }
    assert calls["model_device"] == device
    assert calls["tensor_devices"] == [device, device]
    assert calls["generate"]["generation_config"].__dict__ == {
        "max_new_tokens": 123,
        "do_sample": False,
        "num_beams": 1,
        "use_cache": True,
        "eos_token_id": 151643,
        "pad_token_id": 151643,
    }
    assert calls["decode"] == ([99], {"skip_special_tokens": True})
    if model_id.endswith("-Base"):
        assert "chat" not in calls and "Evidence JSON:" in calls["prompt"]
        assert calls["prompt"].startswith(request["system_prompt"] + "\n")
        assert canonical(request["input"]) in calls["prompt"]
    else:
        assert calls["chat"][0][0] == {"role": "system", "content": request["system_prompt"]}
        assert calls["chat"][1] == {
            "tokenize": False,
            "add_generation_prompt": True,
            "enable_thinking": False,
        }


def test_pin_mismatch_precedes_runtime_import(runtime, monkeypatch):
    config, snapshot, calls = runtime
    config = replace(config, checkpoint_sha256="0" * 64)
    monkeypatch.setitem(sys.modules, "torch", None)
    request = build_request(config, "analyst", snapshot, ())
    with pytest.raises(ValueError, match="pin mismatch"):
        worker.respond(canonical(request).encode())
    assert "model_load" not in calls


def test_checkpoint_drift_refuses_completed_inference(runtime, monkeypatch):
    config, snapshot, calls = runtime
    original = worker.inspect_checkpoint(config.checkpoint_path, config.model_id)
    manifests = iter([original, {"changed": True}])
    monkeypatch.setattr(worker, "inspect_checkpoint", lambda *args: next(manifests))
    request = build_request(config, "analyst", snapshot, ())
    with pytest.raises(ValueError, match="changed during review"):
        worker.respond(canonical(request).encode())
    assert "generate" in calls


@pytest.mark.parametrize("length", [0, 2049])
def test_token_budget_before_loading_weights(runtime, length):
    config, snapshot, calls = runtime
    calls["length"] = length
    request = build_request(config, "analyst", snapshot, ())
    with pytest.raises(ValueError, match="token budget"):
        worker.respond(canonical(request).encode())
    assert "model_load" not in calls


@pytest.mark.parametrize("capability", ["cuda", "bf16"])
def test_no_silent_cpu_or_precision_fallback(runtime, capability):
    config, snapshot, calls = runtime
    calls[capability] = False
    config = replace(config, device="cuda")
    request = build_request(config, "analyst", snapshot, ())
    with pytest.raises(ValueError, match="no fallback"):
        worker.respond(canonical(request).encode())
    assert "model_load" not in calls


def test_missing_dependency_is_not_replaced_by_stub(runtime, monkeypatch):
    config, snapshot, calls = runtime
    monkeypatch.setitem(sys.modules, "transformers", None)
    request = build_request(config, "analyst", snapshot, ())
    with pytest.raises(ModuleNotFoundError):
        worker.respond(canonical(request).encode())
    assert "model_load" not in calls


def test_output_bound_in_worker(runtime):
    config, snapshot, calls = runtime
    calls["response"] = "x" * 2049
    request = build_request(config, "analyst", snapshot, ())
    with pytest.raises(ValueError, match="Response budget"):
        worker.respond(canonical(request).encode())


@pytest.mark.parametrize("data", [b"SECRET malformed", b'{"configuration":{}}', b"[]"])
def test_private_worker_cli_sanitizes_errors(data):
    result = subprocess.run(
        [sys.executable, "-I", "-m", "ai_trader.models._local_review_worker"],
        input=data,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr.strip() == b"local_worker_failed"
