# Bounded local Qwen LoRA worker

Status (2026-09-24): **implemented; native tiny CPU adapter update/save/reload verified** in a
[separate pinned training environment](QWEN_NATIVE_LORA_SMOKE.md). The launch/approval protocol also
has synthetic/fake-library regression tests. No CUDA/Qwen3-4B fitting, memory feasibility, Qwen
adapter artifact or held-out evaluation is claimed. The curriculum now has a completed
[user-delegated AI review and verified V2 candidate](QWEN_DELEGATED_REVIEW.md); no human review is
claimed. The real holdout registry is still an empty reservation template. The existing inference
environment still lacks PEFT/Accelerate and is preserved; use `.venv-qwen-train` for training work.

The worker is a local adapter smoke-test facility, not continuous learning, a profitable policy,
an autonomous paper service or a live-trading integration. It is not called by trading code.

## Implemented components

- `training/advisory_training_run.py`: runtime metadata capture, launch preparation, independent
  input reconstruction, supervision and durable run records.
- `training/_local_training_worker.py`: a private one-request process; rejects absent/non-boolean
  opt-in and oversized requests, and keeps library logs separate from its bounded result channel.
- `training/lora_backend.py`: lazy local Torch/Transformers/PEFT loading, adapter-only updates,
  safe adapter save and fresh-base reload checks. No package installation or hub fallback.

The backend uses PEFT's documented adapter configuration and save/reload interfaces with explicit
settings: [LoRA configuration](https://huggingface.co/docs/peft/package_reference/lora) and
[adapter state/save/load APIs](https://huggingface.co/docs/peft/package_reference/peft_model).
It saves only the selected adapter as safetensors, with embedding-layer saving disabled; it does
not merge into or save the Base model. These API choices were checked against official docs, but
the native combination now passes a tiny CPU smoke, not actual CUDA/Qwen training validation.

## Launch gates and provenance

Preparation consumes six explicit local path/raw-SHA256 bindings: frozen suite, eligible review
(V1 operator or explicitly delegated V2 agent),
reviewed candidate, protected-evaluation metadata registry, runtime-version manifest and dependency
lock. It rebuilds the candidate from the original suite/review and requires a completed declared
evaluation reservation before creating a launch plan. It does not open held-out payloads or labels.
Candidate consistency and metadata disjointness are not authentication of human review, true
independence, target quality or actual-market calibration; the earlier trust boundaries still apply.

The runtime manifest records interpreter path/version, platform/machine and installed versions of
Torch, Transformers, PEFT, Accelerate, safetensors, tokenizers and NumPy. All must be present. The
dependency lock must be self-contained, bounded, hash-qualified `name==version` entries, including
those packages. Includes, URLs, index options, unpinned entries and duplicates are rejected. The
worker checks installed versions for every declared lock entry again before native imports.

The lock's raw bytes are pinned, but this is **not a verification of installed package-file bytes,
complete dependency closure or wheel provenance**. It does not replace reviewed provisioning and
native compatibility testing. Interpreter path/version matching is not an executable-binary hash.
Do not relabel the existing inference lock as a complete training lock; it has includes and no PEFT.

A launch also binds the checkpoint manifest, tokenizer bytes, fixed recipe, new output directory,
worker/interpreter and SHA256 of the selected local worker/preflight source files. Source edits or
even line-ending changes invalidate an already-prepared launch. These are drift checks, not an OS
sandbox or code signature. No runtime configuration is guessed from an unrelated saved model.

## Execution limits and update checks

Execution requires both the pinned launch and `--enable-local-training`. Preparation/runtime
capture never starts training. The supervisor claims a new output directory; it cannot overlap
the Base checkpoint. Existing output directories are never overwritten or automatically resumed.

The fixed smoke profile is:

- Qwen3-4B-Base, CUDA BF16, local safetensors only; no CPU, quantization or network fallback.
- LoRA rank 8, alpha 16, dropout 0, `q_proj`/`v_proj`, no trainable biases or extra saved modules.
- Frozen Base parameters; only default adapter A/B weights may be trainable, at most 4 million
  parameters. The trainable set is rechecked every step, and only those parameters reach AdamW.
- Batch size 1, accumulation 1, AdamW learning rate 0.0002, weight decay 0, gradient norm cap 1,
  seed 42, non-reentrant gradient checkpointing and no KV cache. The framework is asked for
  deterministic algorithms with TF32 disabled; unsupported operations fail rather than relax this.
- Exactly 20 steps for a completed smoke run, deterministic reshuffling of curriculum records,
  no development/held-out early stopping and no retry. No learning-quality conclusion follows
  from taking 20 steps or reducing training loss.
- Completion/EOS-only labels from the existing token protocol: 2,048 prompt tokens, at most 255
  reply tokens plus EOS, 2,304 padded tokens. Embedded EOS/pad IDs and vocabulary overflow refuse.

Loss and gradient norms must be finite/nonnegative before an optimizer update can complete.
An adapter update must actually be detected before save. Every step writes and fsyncs intent
before the backend call and completion afterward. Persistence failure prevents further dispatch.

The supervisor reuses the bounded-pipe process transport: one owned child, no shell, isolated
Python invocation, scrubbed credential/proxy variables and offline Hugging Face settings. It gives
the worker **600 seconds total**, including imports, verification, loading, steps, save and reload.
Deadline/pipe overflow kills the child; process cleanup may take additional bounded seconds.
The inner loop also checks time between operations, but only the supervisor can interrupt a
stalled native operation. Do not invoke the private backend/worker directly and claim this guarantee.

This is not a hard RAM/VRAM or OS disk quota. Adapter files are checked against a 64-MiB aggregate
limit and a short filename allowlist after save; this does not stop a malfunctioning trusted library
from writing too much before that check. No 16-GB-VRAM compatibility result has been established.

## Save, reload and failure interpretation

After optimization, the worker retains a bounded CPU copy of adapter state and a loss probe on
one **training** example. It saves into a new `adapter/` directory, verifies only expected regular
files exist, rejects symlinks/pickle checkpoints and hashes their bytes. It releases the first
model/optimizer's CUDA references before loading a fresh pinned Base and the saved adapter locally.

Reload must be inference-only, with exact adapter-state equality and probe-loss agreement within
absolute tolerance 0.00001. Base checkpoint files are rehashed to confirm no disk changes, and
adapter bytes must remain unchanged during reload. The supervisor independently checks result
bindings, 20 completed steps, finite probe values, authority flags and the adapter manifest.
This is serialization consistency on a training input, **not held-out model evaluation**.

Artifacts in a claimed run directory:

- `launch.json`: exact input/source/recipe bindings, persisted before worker dispatch.
- `steps.jsonl`: finite step/save intent and completion events, if the worker reaches that stage.
- `adapter/`: partial or complete adapter-only files, if save begins.
- `worker_result.json`: produced only after the worker's verification finishes.
- `run.json`: supervisor outcome; always denies promotion/execution and records no held-out evaluation.

On failure/interruption, artifacts are retained and the supervisor records `failed_or_interrupted`,
unknown completed-step count and no automatic retry. A crash can happen between an update and its
completion record: do not interpret missing completion as proof no update happened. Disk failure
can prevent even a failure summary; no summary means incomplete, not success. Partial adapters are
quarantined by outcome and must never be automatically loaded into inference or paper trading.

## CLI

Capture version metadata in the chosen environment, without importing native model libraries:

```powershell
.venv-qwen-train\Scripts\python.exe -m ai_trader.training.advisory_training_run runtime --output logs/YOUR_NEW_runtime_versions.json
```

Before using `prepare`, create and review a descriptor JSON with exactly these fields:
`inputs`, `checkpoint`, `checkpoint_sha256`, `tokenizer_sha256`, `output_dir`. Each of the six
`inputs` entries named above contains `path` (absolute) and `sha256` (raw-file hash). Checkpoint
and output paths must also be absolute. The output parent must exist, and the run directory must
be new. Record the descriptor's exact hash after review; it is not an approval template to fill
with invented sign-offs or a command to bypass the still-incomplete evaluation reservation.

```powershell
.venv\Scripts\python.exe -m ai_trader.training.advisory_training_run prepare --source C:\path\to\reviewed_descriptor.json --source-sha256 RECORDED_DESCRIPTOR_SHA256 --output logs/YOUR_NEW_lora_launch.json
.venv\Scripts\python.exe -m ai_trader.training.advisory_training_run run --source logs/YOUR_NEW_lora_launch.json --source-sha256 RECORDED_LAUNCH_SHA256 --enable-local-training
```

The second command can perform real fitting once prerequisites pass; it is **not** a dry run.
Do not run it with today's incomplete protected-evaluation reservation. The pinned environment
has only a tiny CPU compatibility result, not a Qwen CUDA memory result. The interpreter in the runtime
manifest is the worker interpreter, independently checked in that child. Unknown flags/fields or
changed source data/recipe stop the launch; outputs are always exclusive.

## Current evidence and next step

65 new tests cover launch/input/recipe/code pins, unavailable runtime, dependency-lock format,
opt-in, overlap refusal, durable intents, fixed ordering/step caps, deadlines, non-finite metrics,
no retry/overwrite, malformed child results and adapter-only save/reload API contracts. Native
Torch/PEFT behavior is mocked; these tests do not establish gradients, memory feasibility or
real adapter save/reload compatibility. Full suite: **1,943 passed, one optional Nautilus skip**.

Read-only runtime capture is saved at `logs/qwen_lora_runtime_versions_20260924.json`, raw SHA256
`0c022b6a42f6d9470543f9c54aa51bd0377c0bdaef44088668d2d44f3dd8a638`. It records Python 3.12.10,
Torch 2.14.0+cu132 and Transformers 5.17.0, but **PEFT and Accelerate are absent**. This manifest
was verified to fail the launch dependency gate without loading weights or dispatching training.
No actual launch, real training output or operator approval was fabricated.

Subsequent native milestone: the [separate training lock/environment and tiny CPU adapter smoke](QWEN_NATIVE_LORA_SMOKE.md)
are now verified, including three real optimizer updates and exact save/reload with frozen base
parameters. This does not establish CUDA BF16/Qwen training feasibility. Target review is now
complete under explicit user delegation. Next: actual protected reservation before a bounded
Qwen trial. The V2 curriculum source change invalidates old implementation-hash bindings;
prepare a fresh launch and do not treat the historical tiny smoke as a new native run. The old draft
preflight v1 is preserved as a non-executing preparation contract; its saved historical
`optimization_worker_not_implemented` blocker is not a current native-compatibility assessment.
