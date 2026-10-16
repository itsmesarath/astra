"""Private synthetic CPU harness; production launch never selects this tiny-model backend."""

import contextlib
import os
import sys
from importlib.metadata import version
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, digest, strict_json
from ai_trader.training.advisory_training_plan import completion_only_record, proposed_recipe
from ai_trader.training.advisory_training_run import _event, runtime_manifest
from ai_trader.training.lora_backend import PeftBackend, trainable_adapters
from ai_trader.training.tiny_lora_smoke import (
    KIND,
    MAX_REQUEST_BYTES,
    NO_AUTHORITY,
    STEPS,
    validate_request,
)

# This is not Qwen3-4B or a downloadable model ID. No tokenizer/dataset/checkpoint arguments.
TINY_CONFIG = {
    "vocab_size": 64,
    "hidden_size": 32,
    "intermediate_size": 64,
    "num_hidden_layers": 1,
    "num_attention_heads": 4,
    "num_key_value_heads": 2,
    "head_dim": 8,
    "max_position_embeddings": 32,
    "bos_token_id": 1,
    "eos_token_id": 2,
    "pad_token_id": 2,
    "use_cache": False,
    "attention_dropout": 0.0,
    "tie_word_embeddings": False,
}


def synthetic_record():
    record = completion_only_record(
        list(range(3, 11)), [11, 12, 13], eos_token_id=2, pad_token_id=2
    )
    # Only remove padding from this fixed synthetic example. Keep completion/EOS and four pads.
    return {key: value[:16] for key, value in record.items()}


class _TinyBackend(PeftBackend):
    """Exercise the real step/state/probe/save/reload methods with a tiny random CPU base.

    Only construction, input device and base verification differ. This subclass is not exposed
    through the production worker, so its Qwen size, checkpoint and CUDA gates remain unchanged.
    """

    def __init__(self):
        import torch
        from peft import LoraConfig, PeftModel, TaskType, get_peft_model, get_peft_model_state_dict
        from transformers import Qwen3Config, Qwen3ForCausalLM

        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.manual_seed(42)
        torch.use_deterministic_algorithms(True)
        self.torch, self.peft_loader = torch, PeftModel
        self.state_dict = get_peft_model_state_dict
        self.config_type, self.model_type = Qwen3Config, Qwen3ForCausalLM
        self.recipe = proposed_recipe()
        self.base_state, self.base_refs = None, None
        base = self._base()
        self.base_parameters = sum(p.numel() for p in base.parameters())
        config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=8,
            lora_alpha=16,
            lora_dropout=0.0,
            target_modules=["q_proj", "v_proj"],
            bias="none",
            modules_to_save=None,
            init_lora_weights=True,
            inference_mode=False,
        )
        self.model = get_peft_model(base, config, autocast_adapter_dtype=True)
        self.model.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )
        self.model.enable_input_require_grads()
        self.params = trainable_adapters(self.model)
        self.trainable_parameters = sum(p.numel() for p in self.params)
        if self.trainable_parameters > 4096:
            raise ValueError("Tiny adapter budget exceeded.")
        self.initial_state = self._state()
        self.optimizer = torch.optim.AdamW(self.params, lr=0.0002, weight_decay=0.0)
        self.model.train()
        self.verify_base()

    def _base(self):
        config = self.config_type(**TINY_CONFIG)
        config._attn_implementation = "eager"
        # No from_pretrained for the base; no file/hub/model identifier is accepted.
        with self.torch.device("cpu"):
            base = self.model_type(config).to(dtype=self.torch.float32)
        base.requires_grad_(False)
        if sum(p.numel() for p in base.parameters()) > 100_000:
            raise ValueError("Tiny base budget exceeded.")
        if self.base_state is None:
            self.base_state = {k: v.detach().clone() for k, v in base.state_dict().items()}
        else:
            base.load_state_dict(self.base_state, strict=True)
        # References retain original names across PEFT's module wrapping; no disk checkpoint.
        self.base_refs = dict(base.named_parameters())
        return base

    def _batch(self, record):
        if canonical(record) != canonical(synthetic_record()):
            raise ValueError("Only the fixed synthetic token sequence is accepted.")
        return {
            k: self.torch.tensor([v], dtype=self.torch.long, device="cpu")
            for k, v in record.items()
        }

    def verify_base(self):
        if self.torch.cuda.is_initialized():
            raise ValueError("Tiny native smoke must not initialize CUDA.")
        if self.base_refs is None or any(
            p.requires_grad
            or p.grad is not None
            or p.device.type != "cpu"
            or not self.torch.equal(p.detach(), self.base_state[name])
            for name, p in self.base_refs.items()
        ):
            raise ValueError("Tiny base parameter changed, has a gradient, or left CPU.")


def respond(raw):
    if type(raw) is not bytes or len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("Native smoke request budget exceeded.")
    request = strict_json(raw)
    pins = validate_request(request)
    if request["python_executable"] != str(Path(sys.executable).resolve()):
        raise ValueError("Native worker interpreter mismatch.")
    if any(version(name) != expected for name, expected in pins.items()):
        raise ValueError("Installed version differs from the training lock.")
    if any(
        os.environ.get(name) != "1"
        for name in (
            "HF_HUB_OFFLINE",
            "TRANSFORMERS_OFFLINE",
            "HF_HUB_DISABLE_TELEMETRY",
            "DO_NOT_TRACK",
        )
    ):
        raise ValueError("Offline native worker environment required.")
    directory = Path(request["output_dir"])
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Supervisor-owned output directory required.")
    if {p.name for p in directory.iterdir()} != {"request.json"}:
        raise ValueError("New supervisor-owned output required.")
    if (directory / "request.json").is_symlink():
        raise ValueError("Regular persisted request required.")
    with (directory / "request.json").open("rb") as stream:
        saved = stream.read(MAX_REQUEST_BYTES + 1)
    if len(saved) > MAX_REQUEST_BYTES or canonical(strict_json(saved)) != canonical(request):
        raise ValueError("Persisted native request mismatch.")
    # CUDA-enabled Torch's AdamW health check can initialize a GPU even for CPU tensors.
    # Hide devices before any native import; production CUDA training is a separate worker.
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    metrics = []
    with (directory / "steps.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        _event(stream, {"event": "native_import_and_initialization_started"})
        backend = _TinyBackend()  # Native imports happen only after opt-in and all checks.
        record = synthetic_record()
        for step in range(1, STEPS + 1):
            _event(stream, {"event": "step_intent", "step": step})
            metric = backend.step(record)
            backend.verify_base()
            metrics.append(metric)
            _event(stream, {"event": "step_completed", "step": step, **metric})
        _event(stream, {"event": "save_reload_started"})
        reload = backend.save_reload(directory / "adapter", record)
        backend.verify_base()
        _event(stream, {"event": "save_reload_completed"})
    return {
        "kind": KIND,
        "request_sha256": digest(request),
        "steps": STEPS,
        "metrics": metrics,
        "runtime": runtime_manifest(),
        "base_parameters": backend.base_parameters,
        "trainable_parameters": backend.trainable_parameters,
        "base_parameters_unchanged": True,
        "cuda_initialized": backend.torch.cuda.is_initialized(),
        "reload": reload,
        **NO_AUTHORITY,
    }


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        with contextlib.redirect_stdout(sys.stderr):
            result = respond(raw)
        print(canonical(result))
        return 0
    except Exception as exc:
        # No request, environment values or data echoed to the pipe.
        print(f"tiny_lora_worker_failed:{type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
