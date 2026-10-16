"""Optional local PEFT backend. Imported by the supervised worker, never by paper trading."""

import gc
import hashlib
import math
import re
from pathlib import Path

from ai_trader.models.local_checkpoint import digest, inspect_checkpoint

MAX_ADAPTER_BYTES = 64 * 1024 * 1024
MAX_TRAINABLE_PARAMETERS = 4_000_000


def adapter_manifest(directory):
    """Bound/hash the adapter-only files, rejecting symlinks and pickle checkpoints."""
    if not isinstance(directory, Path) or directory.is_symlink() or not directory.is_dir():
        raise ValueError("Regular adapter directory required.")
    entries = []
    for path in directory.iterdir():
        entries.append(path)
        if len(entries) > 3:
            raise ValueError("Unexpected adapter file count.")
    names = {p.name for p in entries}
    required = {"adapter_config.json", "adapter_model.safetensors"}
    if not required <= names or not names <= required | {"README.md"}:
        raise ValueError("Unexpected adapter files.")
    total, files = 0, []
    for path in sorted(entries):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Regular adapter files required.")
        checksum, size = hashlib.sha256(), 0
        with path.open("rb") as stream:
            while block := stream.read(min(1024 * 1024, MAX_ADAPTER_BYTES - total + 1)):
                size += len(block)
                total += len(block)
                if total > MAX_ADAPTER_BYTES:
                    raise ValueError("Adapter byte budget exceeded.")
                checksum.update(block)
        if not size:
            raise ValueError("Empty adapter file.")
        files.append({"name": path.name, "bytes": size, "sha256": checksum.hexdigest()})
    return {"files": files, "total_bytes": total}


def trainable_adapters(model):
    params = []
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        if not re.search(r"\.(q_proj|v_proj)\.lora_[AB]\.default\.weight$", name):
            raise ValueError("Non-adapter parameter became trainable.")
        params.append(parameter)
    count = sum(p.numel() for p in params)
    if not 1 <= count <= MAX_TRAINABLE_PARAMETERS:
        raise ValueError("Trainable adapter parameter budget exceeded or empty.")
    return params


class PeftBackend:
    """One BF16 CUDA Base model, then a fresh reload; no hub access or merged/base saves."""

    def __init__(self, checkpoint, checkpoint_sha256, recipe):
        self.checkpoint, self.checkpoint_sha256, self.recipe = checkpoint, checkpoint_sha256, recipe
        self.verify_base()
        import torch
        from peft import LoraConfig, PeftModel, TaskType, get_peft_model, get_peft_model_state_dict
        from transformers import AutoModelForCausalLM

        self.torch, self.loader, self.peft_loader = torch, AutoModelForCausalLM, PeftModel
        self.state_dict = get_peft_model_state_dict
        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            raise ValueError("CUDA BF16 is required; no fallback.")
        torch.manual_seed(recipe["seed"])
        torch.cuda.manual_seed_all(recipe["seed"])
        torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=recipe["lora_rank"],
            lora_alpha=recipe["lora_alpha"],
            lora_dropout=float(recipe["lora_dropout"]),
            target_modules=recipe["target_modules"],
            bias="none",
            modules_to_save=None,
            init_lora_weights=True,
            inference_mode=False,
        )
        self.model = get_peft_model(self._base(), config, autocast_adapter_dtype=True)
        self.model.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )
        self.model.enable_input_require_grads()
        self.params = trainable_adapters(self.model)
        self.initial_state = self._state()
        self.optimizer = torch.optim.AdamW(
            self.params,
            lr=float(recipe["learning_rate"]),
            weight_decay=0.0,
        )
        self.model.train()

    def _base(self):
        model = self.loader.from_pretrained(
            str(self.checkpoint),
            local_files_only=True,
            trust_remote_code=False,
            use_safetensors=True,
            dtype=self.torch.bfloat16,
            attn_implementation="eager",
        ).to("cuda")
        model.config.use_cache = False
        model.requires_grad_(False)
        if model.config.vocab_size != 151936 or model.config.eos_token_id != 151643:
            raise ValueError("Model vocabulary/EOS differs from the fixed Base training profile.")
        return model

    def _batch(self, record):
        if any(t >= 151936 for t in record["input_ids"]):
            raise ValueError("Token exceeds the verified model vocabulary.")
        return {
            k: self.torch.tensor([v], dtype=self.torch.long, device="cuda")
            for k, v in record.items()
        }

    def _state(self):
        result = {
            k: v.detach().cpu().clone()
            for k, v in self.state_dict(self.model, save_embedding_layers=False).items()
        }
        if not result or sum(v.numel() for v in result.values()) > MAX_TRAINABLE_PARAMETERS:
            raise ValueError("Adapter state budget exceeded or empty.")
        if any(not bool(self.torch.isfinite(v).all()) for v in result.values()):
            raise ValueError("Non-finite adapter state.")
        return result

    def step(self, record):
        # Recheck the trainable set each step so a changed model cannot update the base silently.
        if [id(p) for p in trainable_adapters(self.model)] != [id(p) for p in self.params]:
            raise ValueError("Trainable parameter set changed.")
        self.optimizer.zero_grad(set_to_none=True)
        loss = self.model(**self._batch(record)).loss
        loss_value = float(loss.detach().float().cpu())
        if not math.isfinite(loss_value) or loss_value < 0:
            raise ValueError("Invalid training loss.")
        loss.backward()
        grad = self.torch.nn.utils.clip_grad_norm_(
            self.params,
            float(self.recipe["max_grad_norm"]),
            error_if_nonfinite=True,
        )
        grad_value = float(grad.detach().float().cpu())
        if not math.isfinite(grad_value) or grad_value < 0:
            raise ValueError("Invalid gradient norm.")
        self.optimizer.step()
        return {"loss": loss_value, "gradient_norm": grad_value}

    def _probe(self, record):
        self.model.eval()
        with self.torch.inference_mode():
            loss = float(self.model(**self._batch(record)).loss.float().cpu())
        if not math.isfinite(loss) or loss < 0:
            raise ValueError("Invalid reload probe loss.")
        return loss

    def save_reload(self, directory, probe):
        directory.mkdir()  # Exclusive adapter directory; no overwrite or resume.
        before = self._state()
        changed = any(not self.torch.equal(before[k], self.initial_state[k]) for k in before)
        if not changed:
            raise ValueError("No adapter update detected.")
        before_loss = self._probe(probe)
        self.model.save_pretrained(
            str(directory),
            safe_serialization=True,
            save_embedding_layers=False,
            selected_adapters=["default"],
        )
        manifest = adapter_manifest(directory)
        # Release all CUDA references before loading a fresh base to avoid two resident models.
        self.optimizer, self.params, self.model, self.initial_state = None, None, None, None
        gc.collect()
        self.torch.cuda.empty_cache()
        self.verify_base()
        self.model = self.peft_loader.from_pretrained(
            self._base(),
            str(directory),
            is_trainable=False,
            local_files_only=True,
            autocast_adapter_dtype=True,
        )
        after = self._state()
        if set(before) != set(after) or any(
            not self.torch.equal(before[k], after[k]) for k in before
        ):
            raise ValueError("Reloaded adapter state differs.")
        if any(p.requires_grad for p in self.model.parameters()):
            raise ValueError("Reload verification must be inference-only.")
        after_loss = self._probe(probe)
        if not math.isclose(before_loss, after_loss, rel_tol=0, abs_tol=1e-5):
            raise ValueError("Reload probe loss differs.")
        if adapter_manifest(directory) != manifest:
            raise ValueError("Adapter files changed during reload.")
        self.verify_base()
        return {
            "adapter_manifest": manifest,
            "adapter_updated": True,
            "reload_state_equal": True,
            "probe_loss_before": before_loss,
            "probe_loss_after": after_loss,
            "probe_loss_absolute_tolerance": 1e-5,
            "base_checkpoint_unchanged": True,
        }

    def verify_base(self):
        if (
            digest(inspect_checkpoint(self.checkpoint, "Qwen/Qwen3-4B-Base"))
            != self.checkpoint_sha256
        ):
            raise ValueError("Base checkpoint pin mismatch.")
