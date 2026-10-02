"""Private paired base/adapter inference worker: causal prompts only, no target reader."""

import contextlib
import os
import sys
from importlib.metadata import version
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, digest, strict_json
from ai_trader.research import six_e_forecast_eval as evaluation
from ai_trader.training._qwen_gpu_smoke_worker import resources
from ai_trader.training.advisory_training_plan import load_tokenizer
from ai_trader.training.advisory_training_run import _event, _write, runtime_manifest
from ai_trader.training.lora_backend import trainable_adapters


class InferenceBoundaryError(ValueError):
    """Allowlisted diagnostic code, never a native exception message or tensor/input dump."""

    def __init__(self, code):
        if code not in {"frozen_parameter_guard", "unexpected_adapter_flags", "generation_framing"}:
            raise ValueError("Unknown inference boundary error code")
        self.code = code
        super().__init__(code)


class InferenceBackend:
    """One frozen CUDA model; base mode disables adapters on the identical input."""

    def __init__(self, packet):
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
        import torch
        from peft import PeftModel
        from tokenizers import Tokenizer
        from transformers import AutoModelForCausalLM, GenerationConfig

        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            raise ValueError("CUDA BF16 required; no fallback")
        self.torch = torch
        torch.manual_seed(42)
        torch.cuda.manual_seed_all(42)
        torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        torch.cuda.reset_peak_memory_stats()
        base = AutoModelForCausalLM.from_pretrained(
            packet["checkpoint"],
            local_files_only=True,
            trust_remote_code=False,
            use_safetensors=True,
            dtype=torch.bfloat16,
            attn_implementation="eager",
        ).to("cuda")
        if base.config.vocab_size != 151936 or base.config.eos_token_id != 151643:
            raise ValueError("Pinned Base vocabulary/EOS differs")
        base.requires_grad_(False)
        self.model = PeftModel.from_pretrained(
            base,
            packet["adapter"],
            is_trainable=False,
            local_files_only=True,
            autocast_adapter_dtype=True,
        )
        self.model.requires_grad_(False)
        self.model.eval()
        self.tokenizer = Tokenizer.from_file(packet["tokenizer_json"])
        self.generation = GenerationConfig(
            max_new_tokens=evaluation.MAX_NEW_TOKENS,
            do_sample=False,
            num_beams=1,
            use_cache=True,
            eos_token_id=151643,
            pad_token_id=151643,
        )
        self.guard()

    def guard(self):
        if self.model.training or any(
            p.requires_grad or p.grad is not None or p.device.type != "cuda"
            for p in self.model.parameters()
        ):
            raise InferenceBoundaryError("frozen_parameter_guard")

    def restore_inference_flags(self):
        # PEFT enable_adapter_layers() calls set_adapter(), which re-enables active LoRA
        # requires_grad flags even for a loaded inference-only adapter. Accept only the
        # known q/v LoRA flag transition; never hide a gradient or trainable base weight.
        if any(p.grad is not None for p in self.model.parameters()):
            raise InferenceBoundaryError("frozen_parameter_guard")
        if any(p.requires_grad for p in self.model.parameters()):
            try:
                trainable_adapters(self.model)
            except ValueError as exc:
                raise InferenceBoundaryError("unexpected_adapter_flags") from exc
        self.model.requires_grad_(False)
        self.guard()

    def predict(self, ids, mode):
        if mode not in evaluation.MODES:
            raise ValueError("Only paired base/adapter modes supported")
        self.guard()
        batch = {
            "input_ids": self.torch.tensor([ids], dtype=self.torch.long, device="cuda"),
            "attention_mask": self.torch.ones((1, len(ids)), dtype=self.torch.long, device="cuda"),
        }
        adapter_context = (
            self.model.disable_adapter() if mode == "base" else contextlib.nullcontext()
        )
        try:
            with adapter_context, self.torch.inference_mode():
                self.guard()
                result = self.model.generate(**batch, generation_config=self.generation)
        finally:
            if mode == "base":
                self.restore_inference_flags()
        generated = result[0][len(ids) :].tolist()
        if (
            not 1 <= len(generated) <= evaluation.MAX_NEW_TOKENS
            or 151643 in generated[:-1]
            or (generated[-1] != 151643 and len(generated) != evaluation.MAX_NEW_TOKENS)
        ):
            raise InferenceBoundaryError("generation_framing")
        eos = generated[-1] == 151643
        # Strip only the terminal EOS; other special tokens remain visible and fail strict parsing.
        raw = self.tokenizer.decode(generated[:-1] if eos else generated, skip_special_tokens=False)
        self.guard()
        return {
            "raw_response": raw,
            "generated_tokens": len(generated),
            "stop_reason": "eos" if eos else "token_limit",
        }


def create_backend(packet):
    return InferenceBackend(packet)


def respond(raw: bytes) -> dict:
    if type(raw) is not bytes or len(raw) > evaluation.MAX_PACKET_BYTES:
        raise ValueError("Bounded feature-only inference packet required")
    packet = strict_json(raw)
    pins, runtime = evaluation.validate_packet(packet)
    if (
        packet["python_executable"] != str(Path(sys.executable).resolve())
        or runtime_manifest() != runtime
        or any(version(name) != expected for name, expected in pins.items())
    ):
        raise ValueError("Worker runtime/installed version drift")
    if any(
        os.environ.get(key) != "1"
        for key in (
            "HF_HUB_OFFLINE",
            "TRANSFORMERS_OFFLINE",
            "HF_HUB_DISABLE_TELEMETRY",
            "DO_NOT_TRACK",
        )
    ):
        raise ValueError("Offline inference worker required")
    directory = Path(packet["output_dir"])
    if (
        directory.is_symlink()
        or not directory.is_dir()
        or {p.name for p in directory.iterdir()} != {"request.json"}
    ):
        raise ValueError("Fresh supervisor-owned inference output required")
    saved = directory / "request.json"
    evaluation.file_info(saved, evaluation.MAX_PACKET_BYTES)
    if strict_json(saved.read_bytes()) != packet:
        raise ValueError("Persisted request differs")
    encode = load_tokenizer(Path(packet["tokenizer_json"]), packet["tokenizer_sha256"])
    records = [encode(item["prompt"]) for item in packet["selection"]]
    if any(
        type(ids) is not list
        or not 1 <= len(ids) <= 2048
        or any(type(t) is not int or not 0 <= t < 151936 or t == 151643 for t in ids)
        for ids in records
    ):
        raise ValueError("Bounded prompt tokens required without truncation/EOS")
    stage, completed = "native_initialization", 0
    try:
        with (
            (directory / "events.jsonl").open("x", encoding="utf-8", newline="\n") as events,
            (directory / "predictions.jsonl").open(
                "x", encoding="utf-8", newline="\n"
            ) as predictions,
        ):
            _event(events, {"event": "native_initialization_started"})
            backend = create_backend(packet)
            backend.guard()
            _event(events, {"event": "native_initialization_completed"})
            for item, ids in zip(packet["selection"], records, strict=True):
                for mode in evaluation.MODES:
                    current = evaluation.binding(completed + 1, mode, item)
                    stage = f"prediction_{completed + 1}"
                    _event(events, {"event": "prediction_intent", **current})
                    prediction = {**current, **backend.predict(ids, mode)}
                    evaluation.validate_prediction(prediction)
                    backend.guard()
                    _event(predictions, prediction)
                    _event(
                        events,
                        {
                            "event": "prediction_completed",
                            **current,
                            "prediction_sha256": digest(prediction),
                        },
                    )
                    completed += 1
            stage = "post_inference_pins"
            evaluation.validate_packet(packet)
            evidence = resources(backend)
            _event(events, {"event": "inference_completed"})
        return {
            "kind": evaluation.KIND,
            "request_sha256": digest(packet),
            "completed_calls": completed,
            "parameters_frozen": True,
            "runtime": runtime_manifest(),
            "resources": evidence,
            "files": {
                name: evaluation.file_info(directory / name)
                for name in ("predictions.jsonl", "events.jsonl")
            },
            **evaluation.FLAGS,
        }
    except BaseException as exc:
        _write(
            directory / "failure.json",
            {
                "stage": stage,
                "error_type": type(exc).__name__,
                "error_code": exc.code
                if isinstance(exc, InferenceBoundaryError)
                else "native_runtime_unclassified",
                "completed_calls_unverified": completed,
                "adapter_quarantined": True,
                **evaluation.FLAGS,
            },
        )
        raise


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(evaluation.MAX_PACKET_BYTES + 1)
        with contextlib.redirect_stdout(sys.stderr):
            result = respond(raw)
        print(canonical(result))
        return 0
    except Exception as exc:
        print(f"six_e_forecast_worker_failed:{type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
