"""Private one-request inference worker. No downloads, tools, orders or training."""

import contextlib
import os
import sys
from decimal import Decimal
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, digest, inspect_checkpoint, strict_json
from ai_trader.models.local_reviewer import (
    MAX_REQUEST_BYTES,
    LocalReviewerConfig,
    build_request,
)
from ai_trader.models.review_contracts import base_review_prompt
from ai_trader.research.council import Evidence, ResearchSnapshot, RoleReport


def decode_request(raw):
    """Rebuild typed inputs and require the exact public request contract."""
    if type(raw) is not bytes or len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("Invalid request bytes.")
    request = strict_json(raw)
    configuration = dict(request["configuration"])
    for name in ("checkpoint_path", "python_executable"):
        if configuration[name] is not None:
            configuration[name] = Path(configuration[name])
    config = LocalReviewerConfig(**configuration)
    payload = request["input"]
    evidence = []
    for item in payload["evidence"]:
        if type(item["value"]) is not str or len(item["value"]) > 1024:
            raise ValueError("Bounded decimal strings required.")
        evidence.append(Evidence(**{**item, "value": Decimal(item["value"])}))
    snapshot = ResearchSnapshot(payload["symbol"], payload["as_of_ms"], tuple(evidence))
    prior = tuple(
        RoleReport(**{**p, "evidence_ids": tuple(p["evidence_ids"])}) for p in payload["prior"]
    )
    rebuilt = build_request(config, payload["role"], snapshot, prior)
    if canonical(request) != canonical(rebuilt):
        raise ValueError("Request contract mismatch.")
    return config, request


def _transformers_response(config, request):
    """Trusted optional packages; caller must provision an immutable local checkpoint."""
    manifest = inspect_checkpoint(config.checkpoint_path, config.model_id)
    if digest(manifest) != config.checkpoint_sha256:
        raise ValueError("Checkpoint pin mismatch.")

    # Imported only in the explicitly requested local backend, inside its owned process.
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig

    if config.device == "cuda" and (
        not torch.cuda.is_available() or not torch.cuda.is_bf16_supported()
    ):
        raise ValueError("Requested CUDA BF16 runtime unavailable; no fallback.")
    local_path = str(config.checkpoint_path)
    tokenizer = AutoTokenizer.from_pretrained(
        local_path,
        local_files_only=True,
        trust_remote_code=False,
    )
    user_input = canonical(request["input"])
    if config.model_id == "Qwen/Qwen3-4B-Base":
        # A base completion checkpoint is NOT silently replaced by a chat model.
        prompt = base_review_prompt(request["system_prompt"], request["input"])
    else:
        prompt = tokenizer.apply_chat_template(
            [
                {"role": "system", "content": request["system_prompt"]},
                {"role": "user", "content": user_input},
            ],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    inputs = tokenizer(prompt, return_tensors="pt", truncation=False, add_special_tokens=False)
    input_length = inputs["input_ids"].shape[-1]
    if not 1 <= input_length <= config.max_input_tokens:
        raise ValueError("Input token budget exceeded; no silent truncation.")
    model = AutoModelForCausalLM.from_pretrained(
        local_path,
        local_files_only=True,
        trust_remote_code=False,
        use_safetensors=True,
        dtype=torch.bfloat16 if config.device == "cuda" else torch.float32,
        attn_implementation="eager",
    ).to(config.device)
    model.eval()
    # Do not inherit arbitrary sampling, tool or custom-generation settings from the checkpoint.
    generation = GenerationConfig(
        max_new_tokens=config.max_new_tokens,
        do_sample=False,
        num_beams=1,
        use_cache=True,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.pad_token_id
        if tokenizer.pad_token_id is not None
        else tokenizer.eos_token_id,
    )
    with torch.inference_mode():
        result = model.generate(
            **{k: v.to(config.device) for k, v in inputs.items()},
            generation_config=generation,
        )
    raw = tokenizer.decode(result[0][input_length:], skip_special_tokens=True)
    if type(raw) is not str or len(raw) > 2048:
        raise ValueError("Response budget exceeded.")
    if (
        digest(inspect_checkpoint(config.checkpoint_path, config.model_id))
        != config.checkpoint_sha256
    ):
        raise ValueError("Checkpoint changed during review.")
    return raw


def respond(raw):
    config, request = decode_request(raw)
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        os.environ[key] = "1"
    if config.backend == "stub":
        response = canonical(
            {
                "verdict": "veto",
                "evidence_ids": [request["input"]["evidence"][0]["evidence_id"]],
                "rationale": (
                    "Synthetic transport test only; no model loaded or trading edge established."
                ),
            }
        )
    else:
        response = _transformers_response(config, request)
    return {"request_sha256": digest(request), "raw_response": response}


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        # Libraries may write logs; the parent independently bounds stderr as well as stdout.
        with contextlib.redirect_stdout(sys.stderr):
            response = respond(raw)
        print(canonical(response))
        return 0
    except Exception:
        # Never leak native runtime/provider error details into a trading/research artifact.
        print("local_worker_failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
