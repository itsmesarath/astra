"""PEFT/Torch API-contract fakes, not a native dependency or GPU compatibility test."""

import contextlib
import json
import math
import sys
from types import SimpleNamespace

import pytest

from ai_trader.models.local_checkpoint import digest
from ai_trader.training import lora_backend as module
from ai_trader.training.advisory_training_plan import completion_only_record, proposed_recipe


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    calls = {
        "loss": 2.0,
        "gradient": 0.1,
        "steps": 0,
        "backwards": 0,
        "loads": [],
        "cuda": True,
        "bf16": True,
        "tamper_reload": False,
        "saved": None,
    }
    checkpoint_manifest = {"synthetic": "not actual model weights"}
    monkeypatch.setattr(module, "inspect_checkpoint", lambda *args: checkpoint_manifest)

    class Tensor:
        def __init__(self, value, requires_grad=False):
            self.value, self.requires_grad = value, requires_grad

        def detach(self):
            return self

        def float(self):
            return self

        def cpu(self):
            return self

        def clone(self):
            return Tensor(self.value, self.requires_grad)

        def numel(self):
            return 1

        def __float__(self):
            return float(self.value)

        def backward(self):
            calls["backwards"] += 1

    class Model:
        def __init__(self):
            self.a, self.b, self.base = Tensor(1.0), Tensor(0.0), Tensor(99.0)
            self.config = SimpleNamespace(vocab_size=151936, eos_token_id=151643, use_cache=True)

        def to(self, device):
            assert device == "cuda"
            return self

        def requires_grad_(self, value):
            for p in self.parameters():
                p.requires_grad = value

        def parameters(self):
            return [self.a, self.b, self.base]

        def named_parameters(self):
            return [
                ("base.model.attn.q_proj.lora_A.default.weight", self.a),
                ("base.model.attn.v_proj.lora_B.default.weight", self.b),
                ("base.weight", self.base),
            ]

        def gradient_checkpointing_enable(self, **kwargs):
            calls["checkpointing"] = kwargs

        def enable_input_require_grads(self):
            calls["input_grads"] = True

        def train(self):
            calls["training"] = True

        def eval(self):
            calls["training"] = False

        def __call__(self, **kwargs):
            calls["batch"] = kwargs
            return SimpleNamespace(loss=Tensor(calls["loss"]))

        def save_pretrained(self, directory, **kwargs):
            from pathlib import Path

            calls["save_kwargs"] = kwargs
            calls["saved"] = {"a": self.a.value, "b": self.b.value}
            (Path(directory) / "adapter_config.json").write_text("{}", encoding="utf-8")
            (Path(directory) / "adapter_model.safetensors").write_text(
                json.dumps(calls["saved"]), encoding="utf-8"
            )

    class Loader:
        @staticmethod
        def from_pretrained(path, **kwargs):
            calls["loads"].append((path, kwargs))
            model = Model()
            calls["last_base"] = model
            return model

    class PeftLoader:
        @staticmethod
        def from_pretrained(model, path, **kwargs):
            calls["reload_kwargs"] = kwargs
            model.a.value = calls["saved"]["a"]
            model.b.value = calls["saved"]["b"] + int(calls["tamper_reload"])
            calls["reloaded_base"] = model
            return model

    def get_peft_model(model, config, **kwargs):
        calls["lora_config"], calls["get_peft_kwargs"] = config, kwargs
        model.a.requires_grad = model.b.requires_grad = True
        return model

    def state_dict(model, **kwargs):
        assert kwargs == {"save_embedding_layers": False}
        return {"q_proj.lora_A.weight": model.a, "v_proj.lora_B.weight": model.b}

    class Optimizer:
        def __init__(self, params, **kwargs):
            self.params = params
            calls["optimizer_kwargs"] = kwargs

        def zero_grad(self, **kwargs):
            assert kwargs == {"set_to_none": True}

        def step(self):
            calls["steps"] += 1
            for p in self.params:
                p.value += 0.01

    def clip(params, norm, **kwargs):
        calls["clip"] = (norm, kwargs)
        return Tensor(calls["gradient"])

    torch = SimpleNamespace(
        bfloat16="bf16",
        long="int64",
        manual_seed=lambda seed: calls.update(seed=seed),
        use_deterministic_algorithms=lambda flag: calls.update(deterministic=flag),
        cuda=SimpleNamespace(
            is_available=lambda: calls["cuda"],
            is_bf16_supported=lambda: calls["bf16"],
            manual_seed_all=lambda seed: calls.update(cuda_seed=seed),
            empty_cache=lambda: calls.update(cache_emptied=True),
        ),
        backends=SimpleNamespace(
            cuda=SimpleNamespace(matmul=SimpleNamespace(allow_tf32=True)),
            cudnn=SimpleNamespace(benchmark=True),
        ),
        optim=SimpleNamespace(AdamW=Optimizer),
        nn=SimpleNamespace(utils=SimpleNamespace(clip_grad_norm_=clip)),
        tensor=lambda values, **kwargs: (values, kwargs),
        isfinite=lambda tensor: SimpleNamespace(all=lambda: math.isfinite(tensor.value)),
        equal=lambda a, b: a.value == b.value,
        inference_mode=contextlib.nullcontext,
    )
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(AutoModelForCausalLM=Loader))
    monkeypatch.setitem(
        sys.modules,
        "peft",
        SimpleNamespace(
            LoraConfig=lambda **kwargs: kwargs,
            PeftModel=PeftLoader,
            TaskType=SimpleNamespace(CAUSAL_LM="causal"),
            get_peft_model=get_peft_model,
            get_peft_model_state_dict=state_dict,
        ),
    )
    return calls, tmp_path, digest(checkpoint_manifest), torch


def record():
    return completion_only_record([1, 2], [3, 4], eos_token_id=151643, pad_token_id=151643)


def test_backend_trains_only_adapters_then_saves_and_reloads_fresh_base(runtime):
    calls, path, pin, torch = runtime
    trainer = module.PeftBackend(path, pin, proposed_recipe())
    initial = trainer.model
    assert calls["seed"] == calls["cuda_seed"] == 42 and calls["deterministic"]
    assert not torch.backends.cuda.matmul.allow_tf32 and not torch.backends.cudnn.benchmark
    assert calls["lora_config"]["target_modules"] == ["q_proj", "v_proj"]
    assert (
        calls["lora_config"]["bias"] == "none" and calls["lora_config"]["modules_to_save"] is None
    )
    assert calls["checkpointing"] == {"gradient_checkpointing_kwargs": {"use_reentrant": False}}
    assert calls["optimizer_kwargs"] == {"lr": 0.0002, "weight_decay": 0.0}
    assert trainer.step(record()) == {"loss": 2.0, "gradient_norm": 0.1}
    assert calls["steps"] == calls["backwards"] == 1
    assert calls["clip"] == (1.0, {"error_if_nonfinite": True})
    assert initial.base.value == 99 and not initial.base.requires_grad
    result = trainer.save_reload(path / "adapter", record())
    assert (
        result["adapter_updated"]
        and result["reload_state_equal"]
        and result["base_checkpoint_unchanged"]
    )
    assert calls["cache_emptied"] and trainer.model is not initial
    assert not any(p.requires_grad for p in trainer.model.parameters())
    assert calls["save_kwargs"] == {
        "safe_serialization": True,
        "save_embedding_layers": False,
        "selected_adapters": ["default"],
    }
    assert calls["reload_kwargs"] == {
        "is_trainable": False,
        "local_files_only": True,
        "autocast_adapter_dtype": True,
    }
    assert len(calls["loads"]) == 2
    for _, kwargs in calls["loads"]:
        assert kwargs == {
            "local_files_only": True,
            "trust_remote_code": False,
            "use_safetensors": True,
            "dtype": "bf16",
            "attn_implementation": "eager",
        }


@pytest.mark.parametrize("key", ["cuda", "bf16"])
def test_missing_cuda_or_bf16_never_falls_back(runtime, key):
    calls, path, pin, _ = runtime
    calls[key] = False
    with pytest.raises(ValueError, match="no fallback"):
        module.PeftBackend(path, pin, proposed_recipe())
    assert not calls["loads"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("loss", math.nan),
        ("loss", math.inf),
        ("loss", -1),
        ("gradient", math.nan),
        ("gradient", math.inf),
    ],
)
def test_invalid_loss_or_gradients_prevent_optimizer_update(runtime, field, value):
    calls, path, pin, _ = runtime
    trainer = module.PeftBackend(path, pin, proposed_recipe())
    calls[field] = value
    with pytest.raises(ValueError):
        trainer.step(record())
    assert calls["steps"] == 0
    if field == "loss":
        assert calls["backwards"] == 0


def test_nonadapter_unfreeze_and_vocab_overflow_refused(runtime):
    calls, path, pin, _ = runtime
    trainer = module.PeftBackend(path, pin, proposed_recipe())
    trainer.model.base.requires_grad = True
    with pytest.raises(ValueError, match="Non-adapter"):
        trainer.step(record())
    trainer.model.base.requires_grad = False
    bad = record()
    bad["input_ids"][0] = 151936
    with pytest.raises(ValueError, match="vocabulary"):
        trainer.step(bad)
    assert calls["steps"] == 0


def test_no_update_and_mismatched_reload_do_not_pass(runtime):
    calls, path, pin, _ = runtime
    trainer = module.PeftBackend(path, pin, proposed_recipe())
    with pytest.raises(ValueError, match="No adapter update"):
        trainer.save_reload(path / "unchanged", record())
    trainer.step(record())
    calls["tamper_reload"] = True
    with pytest.raises(ValueError, match="state differs"):
        trainer.save_reload(path / "changed", record())


def test_checkpoint_drift_refused_before_model_loading(runtime):
    calls, path, _, _ = runtime
    with pytest.raises(ValueError, match="checkpoint pin"):
        module.PeftBackend(path, "a" * 64, proposed_recipe())
    assert not calls["loads"]
