# Bounded local Qwen research reviewer

Status: **Qwen3-4B-Base is installed locally and completed a CUDA smoke test plus two separately
approved seven-call development batches**. V1 missed all five draft veto cases; V2 improved veto
recall but regressed formatting and passed only 1/7 full model checks. Neither is promoted; see
the [V1 record](QWEN_ADVISORY_EVALUATION.md) and [V2 comparison](QWEN_REVIEW_CONTRACTS.md).
The approved setup recovered from the earlier download failures without changing security
settings. The response passed JSON/citation validation, not a trading-quality evaluation.
No model was trained. This module is
not wired into the default paper runner or its emergency/exit path. There is no live execution,
account connection, cloud LLM fallback, background inference service or automatic promotion.

## Implemented boundary

`models/local_reviewer.py` implements the existing `research/council.py` Reviewer interface.
One explicitly enabled instance supports one analyst-then-critic sequence, at most two calls.
The critic must receive the same snapshot and the exact validated, supporting analyst report.
Vetoes and failures cannot be retried within the sequence. The deterministic council checks its
existing signal and risk first; a model cannot manufacture an order, change sizing, bypass risk,
force an exit or grant execution authority. Instantiate a new reviewer for each separately
authorized research sequence; this is not an unattended loop or policy-selection mechanism.

Inputs contain BTCUSDT numeric evidence, availability/event timestamps, an explicit single
`source_session`, and (for the critic) the prior report. Future, stale, mixed-session and
mixed-symbol evidence is rejected before launching a worker. No outcomes, training labels,
portfolio credentials or tools are automatically supplied. Input strings/prior rationales are
untrusted data, not instructions. Prompt injection is not solved by wording: safety comes from
the advisory-only interface, strict validation and independent risk/execution boundary.

An opt-in [versioned Spot-long contract](QWEN_REVIEW_CONTRACTS.md) now adds a fixed `review_task`
and an explicit after-cost/stress rubric with `review_contract="spot_long_v2"`. The default
`legacy_v1` prompt and serialized request/configuration bytes stay unchanged for replay. The
worker validates the selected prompt/task before use; this is not semantic enforcement or a
new deterministic risk gate. V2 and V1 results have distinct input/prompt bindings.

Each call launches the chosen local Python executable using `-I -m` and no shell. The selected
environment must already have this package installed; there is no implicit environment creation
or package installation. Environment inheritance uses a small OS/path/temp allowlist, excludes
API/HF/exchange token and proxy variables, and explicitly enables Hugging Face offline mode.
The worker never intentionally requests network access. This is **not an OS network/filesystem
sandbox**: installed Python/native packages and the operator-provisioned checkpoint are trusted.

The worker is killed on deadline or pipe overflow. Only the owned worker process is managed;
untrusted executables or child-process trees are outside this boundary. Limits do not constitute
a hard OS RAM/VRAM quota. This initial implementation cold-loads the model for each role and
hashes assets before/after inference; real latency/peak resource usage must be measured before
considering a separately bounded warm worker. Do not run it in the feed or protection loop.

| Budget | Default / hard ceiling |
| --- | --- |
| Calls per sequence | 2 / 2, no retries or debate loops |
| Input JSON | 32 KiB; 1–32 evidence items |
| Input tokens | 2,048; oversized inputs refused, not truncated |
| Generated tokens | 256 / 512 |
| Deadline and reply lifetime | 60 s each / 120 s each; shorter limit governs worker |
| stdout and stderr | 16 KiB each |
| Raw report | 2,048 characters; rationale 1–512, citations 1–16 |
| Checkpoint | 20 GiB total, 16 MiB per metadata asset, 32 assets, 64 directory entries |

Reports must be exactly JSON with `verdict`, `evidence_ids` and `rationale`. Unknown/duplicate
citations, duplicate keys, order fields, malformed JSON, markdown, reasoning wrappers, oversized
outputs and expired replies fail closed. Parsing does not repair an invalid model response.
The reply binds the exact request hash. In-memory audit records retain request/configuration/
prompt/checkpoint hashes, bounded raw response, status, wall-clock availability and elapsed time.
They always report zero orders and no promotion. Callers must separately persist these records;
this is not durable decision memory, a signed audit log or a journal integration.

## Checkpoint and runtime contract

`models/local_checkpoint.py` performs bounded hashing without tensor/model imports. Supply an
absolute local directory with regular materialized files, not a symlinked Hub cache snapshot.
Only reviewed Qwen3-4B configuration/tokenizer assets and single/indexed safetensors weights are
accepted. Known optional chat templates are pinned too. Executable/pickle weights, custom code,
quantization configurations, tokenizer file overrides, unknown loadable assets and shard paths
outside the exact local weight set are refused. Documentation/cache bookkeeping is excluded.

The manifest's SHA256 must be supplied independently by the caller, not silently accepted anew
on every inference. It detects ordinary asset drift, not publisher authenticity or hostile
concurrent file replacement. Preserve the official source revision and verified download hashes
separately; keep the provisioned directory immutable throughout use. Declaring a model ID does
not prove its weights came from that publisher or distinguish fine-tuned weights automatically.

The optional worker lazily imports Torch/Transformers only after checkpoint inspection passes.
Both loaders use `local_files_only=True` and `trust_remote_code=False`; model weights require
`use_safetensors=True`. CPU uses explicit FP32, CUDA explicit BF16, and no quantization/automatic
device fallback is implemented. Eager attention, inference mode and a fresh greedy generation
configuration bound the request. CUDA discovery alone does not establish compatible inference.

- `Qwen/Qwen3-4B-Base`: preserved as the requested base-model candidate; plain completion prompt.
  Reliable instruction/JSON following is **unproven**. A malformed response is a veto, not a cue
  to substitute a different checkpoint.
- `Qwen/Qwen3-4B`: a separately selected post-trained comparison candidate; its local chat template
  is used with thinking disabled. It is never downloaded or selected implicitly.

Official references: [Qwen3-4B-Base](https://huggingface.co/Qwen/Qwen3-4B-Base),
[Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B),
[Transformers offline loading](https://huggingface.co/docs/transformers/main/en/installation),
[model loading options](https://huggingface.co/docs/transformers/main/en/main_classes/model), and
[generation configuration](https://huggingface.co/docs/transformers/main/en/main_classes/text_generation).
These are API references; the separately recorded smoke test below is the real-weight evidence.

## Safe commands available now (PowerShell, repository root)

```powershell
.venv\Scripts\python.exe -m ai_trader.models.local_reviewer --runtime-check
.venv\Scripts\python.exe -m ai_trader.models.local_reviewer --demo
.venv\Scripts\python.exe -m pytest tests/test_local_checkpoint.py tests/test_local_reviewer.py tests/test_local_review_worker.py -q
```

Runtime check reads installed-package metadata only: it does not import Torch, probe a GPU,
download weights or start training. The demo is explicitly a **synthetic veto stub**, not Qwen.
Observed core-project metadata on September 24: Python 3.12.10, Torch 2.14.0+cu132; Transformers,
safetensors, accelerate, PEFT and bitsandbytes were absent. This core environment was preserved.

### Completed provisioning and one real-model test (September 24, 2026)

After the operator confirmed that the official sites opened in Chrome, ordinary terminal IPv4
requests succeeded too. There was no proxy setting to reuse. No browser automation, credentials,
TLS bypass, DNS override, firewall change or unofficial mirror was needed. The earlier resets'
root cause remains unknown; success with IPv4 does not prove an IPv6 fault.

- Environment: `.venv-qwen` (Python 3.12.10); full hash-pinned Windows wheel dependencies in
  [`qwen-inference-win-py312.txt`](../requirements/qwen-inference-win-py312.txt). Torch
  2.14.0+cu132, Transformers 5.17.0, tokenizers 0.23.2, safetensors 0.8.0, psutil 7.2.2.
  Dependency checks, Qwen-class import, CUDA discovery and a tiny BF16 matrix probe pass.
- Model: official `Qwen/Qwen3-4B-Base`, revision
  `906bfd4b4dc7f14ee4320094d8b41684abff8539`, stored at
  `checkpoints/qwen3-4b-base-906bfd4b4dc7`. Downloaded 12 files totaling 8,056,519,973 bytes,
  including the original Apache-2.0 license and model card. Checked each size plus its published
  safetensors SHA256 or Git-blob metadata hash before publishing each file from `.partial`.
- Source record: [`qwen3_4b_base_source.json`](../configs/qwen3_4b_base_source.json).
  The local loadable-asset manifest SHA256 is
  `8a1a0f20ba8a2c6d4480309f0f442114c4fa310018d143ee610061b1ecf47d3c`.
  This fingerprint excludes documentation, so its byte total differs from the full download.
- One actual call: `models/qwen_smoke.py`, explicit opt-in, CUDA BF16, analyst only,
  synthetic evidence, 2,048 input-token ceiling, 256 new-token ceiling, 120-second deadline.
  Local-only loaders and offline worker settings were used; no model fallback, retry or training.

| Observed measurement | Result |
| --- | --- |
| End-to-end cold-call time, including worker startup/teardown and hashing | 40.281 s |
| Worker inference/loading/hashing time, after CUDA initialization | 38.141 s |
| Peak Torch-allocated GPU memory | 8,245,496,320 bytes (about 7.68 GiB) |
| Peak Torch-reserved GPU memory | 8,308,916,224 bytes (about 7.74 GiB) |
| Peak process working set, Windows/psutil | 8,930,152,448 bytes (about 8.32 GiB) |
| Generation and strict report validation | Completed; JSON/citations valid |
| Orders, training, promotion | None |

Allocator counters exclude some CUDA/context memory and other applications; process working set
is not a training-memory estimate. One cold call is not a latency distribution, throughput test,
fine-tuning feasibility proof or trading benchmark. The worker terminated normally; no persistent
model server remains running. Raw output/configuration/metrics are retained in the ignored artifact
`logs/qwen_base_smoke_20260924_approval1.json`. No model weights are committed to Git.

**Important quality finding:** the model returned `support` from synthetic positive CVD/imbalance
and a 12-bps cost estimate, describing the costs as low and the environment as favorable. No
calibrated return/after-cost expectancy was supplied. This is an unsupported positive economic
interpretation, despite valid structure and citations. Do not approve this opinion as a trading
signal or a training target. The [draft advisory evaluation](QWEN_ADVISORY_EVALUATION.md) now includes
this regression, insufficient-edge/cost-stress cases and conditional positive controls. Offline
rescoring confirms the original reply fails its expected verdict. A subsequent approved batch
evaluated the separate development split: seven model responses and four preflight refusals.
All seven replies returned support, matching only the two positive controls. The targets still
require operator review, and rationale semantics remain ungraded by the scorer. The smoke harness has no
execution authority, even when `report_valid` is true.

The harness reuses the bounded process transport, preserves raw invalid replies and distinguishes
generation completion from report validity. Its output uses exclusive creation before dispatch,
so reusing an existing output path refuses the run. Optional measurement imports stay in the
isolated child. Progress bars are disabled to keep library logging out of the bounded pipe budget;
validation/deadline limits were not relaxed. Regression tests use fakes, never the installed model.

Historical failed attempt, retained for context:

### Initial staging attempt: download failure (later recovered)

The operator approved isolated Qwen3-4B-Base installation and one bounded synthetic inference
test, without training or trading. Created `.venv-qwen` with no system-site-package inheritance
and installed the project there in editable mode. Installed 30 official-PyPI wheel dependencies
using exact versions and SHA256 hashes from
[`requirements/qwen-staging-win-py312.txt`](../requirements/qwen-staging-win-py312.txt).
This is explicitly a **staging lock**, not a complete CUDA inference environment. Key versions:
Transformers 5.17.0, tokenizers 0.23.2, safetensors 0.8.0 and huggingface-hub 1.33.0.

Dependency checking, native tokenizer/safetensors imports and the subprocess **stub** demo pass.
The isolated environment has no Torch, accelerator, PEFT or bitsandbytes installation. The core
environment's working CUDA Torch was neither modified nor imported through a shared site path.
The PyPI CPU Torch candidate encountered during resolution was not installed as a substitute.

DNS resolves both official download hosts, but local TLS connections to `huggingface.co` and
`download.pytorch.org` reset with Windows error 10054. The Hugging Face metadata request failed
in PowerShell, curl and Python; the CUDA package-index query also failed. A resulting pip
"no matching distribution" message does not establish that the CUDA package is unavailable:
the index could not be reached. PyPI downloads succeeded. These observations do not identify
whether the cause is the local network/security software, an upstream service or another layer.
No certificates, firewall, proxy, DNS, Windows security settings or credentials were changed;
no unofficial mirror was used.

At that point the model revision and asset hashes had **not** been obtained/pinned, no Qwen weights
had downloaded, and the real-model smoke test could not start. The initial synthetic demo was not
Qwen inference. The completed provisioning section above supersedes this historical blocker.

Local resolution/install reports are retained under `logs/qwen_*_20260924.json` (git-ignored).
Read-only status commands for the prepared environment:

```powershell
.venv-qwen\Scripts\python.exe -m pip check
.venv-qwen\Scripts\python.exe -I -m ai_trader.models.local_reviewer --runtime-check
.venv-qwen\Scripts\python.exe -I -m ai_trader.models.local_reviewer --demo
```

Inspect the provisioned checkpoint without loading weights into a model:

```powershell
.venv\Scripts\python.exe -m ai_trader.models.local_reviewer --checkpoint-fingerprint C:\Users\pabta\Projects\ai-trader\checkpoints\qwen3-4b-base-906bfd4b4dc7 --model-id Qwen/Qwen3-4B-Base
```

For a separately authorized research inference, construct
`LocalReviewerConfig` with `backend="transformers"`, the exact supported model ID, absolute local
checkpoint and isolated-Python paths, an independently recorded `checkpoint_sha256`, source-session
scope, device and budgets. Explicitly construct `LocalReviewer(..., enable_local_inference=True)`
and supply it to the research council with typed inputs. Missing dependencies/weights are errors,
never a stub or cloud fallback. There is deliberately no automatic download/train/trade command.

## Next gates: setup, then training

1. Completed: isolated dependency/model provisioning and one measured real-weight synthetic call.
   Preserve the core environment and pins; setup did not promote a model or policy.
2. Implemented: draft curriculum, offline scoring, frozen-plan runner and explicit V2 Spot-long
   task/rubric with exact V1 replay compatibility. Two approved comparisons are complete; V2
   passed only 1/7 full model checks. Independent [evidence/arithmetic reports](SPOT_LONG_EVIDENCE_CHECKS.md)
   now preserve raw model scores and prepare 14 curriculum fact packets. A
   [versioned review/candidate workflow](QWEN_CURRICULUM_APPROVAL.md) now binds those facts and
   now supports [explicitly delegated AI review](QWEN_DELEGATED_REVIEW.md): all 14 proposed
   targets were accepted and a V2 candidate independently reconstructed, without human-approval
   claims. Next: protected evaluation, not further tuning on these exposed development cases.
   [Training preflight](QWEN_TRAINING_PREFLIGHT.md) now adds a metadata-only overlap boundary,
   completion-only loss masks and a successful CPU token-budget check of all 14 proposals; it
   neither creates a real holdout nor trains a model. A separate
   [bounded LoRA worker](QWEN_LORA_WORKER.md) is now implemented. A separate
   [pinned training environment/tiny native CPU smoke](QWEN_NATIVE_LORA_SMOKE.md) passes real
   adapter updates and exact reload; actual Qwen CUDA fitting and memory feasibility remain gated.
   Neither schema/verdict/citation checks nor numeric facts grade prose quality; no model is promoted.
3. Benchmark reviewed, causal research examples against the deterministic reviewer and the
   numerical baseline. No paper deployment or trading edge follows from a successful smoke test.
4. Prepare a versioned Qwen curriculum and separately approved LoRA/QLoRA environment/resource
   trial. Whole-session chronological splits and protected evaluation remain mandatory. Train
   concise structured reviews from checked targets, not after-the-fact winners or unreviewed LLM
   lessons. Demonstrate adapter save/reload and held-out schema/task evaluation before promotion.

Model setup need not wait for a profitable strategy. Actual-market training still requires valid,
adequate data and reviewed targets. The latest approved public capture failed freshness checks
and remains quarantined; this reviewer does not make it eligible for training. Ongoing learning,
LangGraph/checkpointed orchestration and actual paper-policy integration are separate milestones.
