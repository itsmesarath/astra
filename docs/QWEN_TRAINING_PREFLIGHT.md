# Protected-evaluation metadata and Qwen training preflight

Status (2026-09-24): **preparation only, not a trained model**. Added a metadata-only evaluation
reservation boundary, completion-only token/loss-mask preparation and a dry-run recipe/report.
All 14 targets passed a local CPU tokenizer preflight. The user-delegated
[AI target review and candidate export](QWEN_DELEGATED_REVIEW.md) are now complete, including a
fresh 14-target CPU tokenizer check. An actual protected evaluation reservation remains incomplete. A separate
[supervised LoRA worker](QWEN_LORA_WORKER.md) is implemented, and a
[pinned training environment/tiny native CPU smoke](QWEN_NATIVE_LORA_SMOKE.md) now passes real
adapter optimization and reload. Qwen CUDA training feasibility remains unverified. This planner
does not approve candidates, load model weights, perform fitting/inference or place orders.

## Protected evaluation stays outside the planner

`training/advisory_holdout.py` reconstructs an exposure inventory from **all 25** known cases,
including curriculum, rejected examples and the already-visible development cases. It reuses
the evaluator's exact normalized evidence fingerprint: identifiers and absolute time offsets are
removed, decimal representation is normalized without rounding, and evidence order is ignored.
The helper extraction preserves historical duplicate detection and both recorded Qwen scores.

A future evaluation custodian supplies a pinned metadata registry with case IDs, families,
source sessions, V2 model-input hashes, normalized evidence hashes and an opaque dataset hash.
The planner never receives a dataset path, evidence payload, target label or rationale. Such
fields are rejected. It does not open, generate or evaluate held-out examples.

The audit refuses overlap with any known case ID, family, session, input hash or normalized
evidence hash. It also refuses duplicate protected IDs/input hashes/scenario hashes and a session
assigned to multiple families. Existing exposed data cannot be rebranded as final evaluation.
Each source session stays on one side of the exposed/protected boundary; this is a synthetic
advisory-case boundary, not a replacement for chronological actual-market dataset splitting.

A nonempty disjoint declaration, dataset hash and explicit operator/custodian attestation that
the data are unexposed can complete **metadata reservation**. This is not authentication: the
custodian must correctly derive metadata and preserve the private payload, verify target quality
and class coverage, and ensure the cases were not used for tuning. The audit cannot verify these
claims without reading the dataset. It explicitly leaves `heldout_contents_verified`,
`independence_authenticated` and `near_duplicates_checked` false. Hashes catch exact matches/drift,
not semantically similar examples, altered numbers or exposures omitted from the declared inventory.

The saved real registry is an **empty pending template**, not a genuine holdout. No private
evaluation cases or supposed independent labels were fabricated during development.

A separate [custodian-side dataset intake](QWEN_PROTECTED_INTAKE.md) can now derive that metadata
from an actual pinned protected payload and reproduce it independently. It checks normalized
overlap, case/session boundaries, numeric target consistency and three-way behavior coverage.
It outputs a pending registry, never a fabricated unexposed attestation. It must not run inside
the metadata-only training planner; no real protected dataset has been supplied yet.

## Completion-only training records

`training/advisory_training_plan.py` adds `completion_only_record`, a dependency-free builder.
The future causal-LM trainer must receive unshifted labels and perform its normal internal shift;
the builder does not pre-shift them. It prepares:

- `input_ids`: prompt tokens, reply tokens, one EOS, then right padding.
- `attention_mask`: one for prompt/reply/EOS and zero for padding.
- `labels`: `-100` for prompt and padding; reply token IDs and EOS remain supervised.

EOS remains supervised when the tokenizer uses the same ID for padding. The mask is derived from
positions/sequence lengths, never by replacing every occurrence of the pad ID. Embedded EOS/pad
tokens, booleans, non-integer/out-of-range IDs and empty/oversized sequences are refused.

The Base-model protocol is `qwen_base_separate_completion_eos_v1`. Prompt and reply are encoded
**separately**, with automatic special-token addition disabled, then concatenated. This preserves
the exact inference prompt prefix instead of letting BPE merge across the prompt/reply boundary.
The shared `base_review_prompt` helper preserves the historical V1/V2 text bytes. This is the Base
completion format, not an instruction-model chat template.

Limits are 2,048 prompt tokens, 255 reply tokens plus one EOS, and 2,304 total padded tokens.
Nothing is silently truncated. Structural token-ID bounds do not verify a future model's embedding
size; the actual training worker must also check vocabulary/config compatibility. Padding/masking
tests and a tokenizer dry run do not prove gradient correctness or GPU memory feasibility.

## Draft plan and optional tokenizer check

Preparation revalidates review/registry bindings. It checks proposed target schema, citations,
verdict and numeric consistency **even while operator decisions are pending**. Rejections remain
explicit excluded rows. Failed proposals/tokenization remain visible and block readiness.

The optional tokenizer reads only a bounded, SHA-pinned local `tokenizer.json`; it disables
truncation/padding and automatic special-token insertion. It uses the already-installed CPU
`tokenizers` package, not model weights, a model server or a network fallback. The dry report stores
only per-case hashes/counts/statuses, not training tensors or copied prompts/targets. Tokenizing a
draft does not approve it or export a training dataset. The optional native tokenizer is trusted
local code, not an OS-sandboxed hostile tokenizer execution service.

The fixed proposed smoke recipe is LoRA rank 8/alpha 16 on `q_proj` and `v_proj`, frozen Base
weights, BF16 without quantization, batch size 1, gradient accumulation 1, gradient checkpointing,
AdamW at 0.0002, seed 42, at most 20 optimizer steps and 600 seconds, with no retries. These are
**planned limits in this draft v1 contract**: `limits_enforced_by_training_worker` remains false.
The separate launch contract now adds supervised enforcement; this planner alone does not execute
it. There is no claim that this recipe fits available VRAM or yields useful learning.
It is not a full fine-tune or automatic continuous-learning job.

Every plan leaves `training_allowed`, `weights_loaded`, `promotion_allowed` and
`execution_allowed` false, with zero optimization steps/model calls/orders. Even synthetic test
approvals cannot remove the missing-worker/environment blockers. The nested curriculum audit
describes its own curriculum-only scope; the plan additionally audits reservation metadata.

## Commands

Create a new pending reservation without opening any held-out data:

```powershell
$suitePin = '5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659'
.venv\Scripts\python.exe -m ai_trader.training.advisory_training_plan reserve-template --suite configs/qwen_review_cases_v1.json --suite-sha256 $suitePin --output logs/YOUR_NEW_reservation_template.json
```

Reproduce the dry run against the existing pending registry and agent-reviewed proposals. Use a
new output path. Omit all four tokenizer options and use `.venv` for a static plan without imports
from the optional tokenizer environment:

```powershell
$reviewPin = 'ebbc3b756b651e70f9fb04b005b351c1c09f4b9054ffdc0fd69f74e7e7f0fb60'
$registryPin = '0026c7f909435a0d7a1cce5530c56dc91e4307e29ccdc3ce8fdd7d85c0318075'
$tokenizerPin = 'c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539'
.venv-qwen\Scripts\python.exe -m ai_trader.training.advisory_training_plan prepare --suite configs/qwen_review_cases_v1.json --suite-sha256 $suitePin --review logs/qwen_curriculum_agent_review_20260924.json --review-sha256 $reviewPin --registry logs/qwen_protected_eval_reservation_pending_20260924.json --registry-sha256 $registryPin --tokenizer-json checkpoints/qwen3-4b-base-906bfd4b4dc7/tokenizer.json --tokenizer-sha256 $tokenizerPin --eos-token-id 151643 --pad-token-id 151643 --output logs/YOUR_NEW_training_preflight.json
```

The observed EOS ID is from the installed Base config/tokenizer, not an assumed instruction-model
default. The planner's explicit token IDs and tokenizer pin do not certify the complete checkpoint
or dependency environment. Future fitting must verify them together with the model/recipe pins.
CLI input/report size limits and exclusive output creation remain enforced. Exit zero only means
the artifact was prepared; inspect its blockers. It never starts training after a successful check.

## Measured local result

All 14 proposed targets were accepted for **tokenization only**:

| Measurement | Result |
| --- | --- |
| Prompt token counts | 707–818 |
| Reply token counts, excluding EOS | 56–72 |
| Supervised token counts, including EOS | 57–73 |
| Token-budget/refusal failures | 0/14 |
| Training steps / generation calls / orders | 0 / 0 / 0 |

A separate local CPU check compared all 28 prompt/reply encodings with the installed inference
`AutoTokenizer`, using local files only and no remote code. They matched exactly; EOS was 151643.
This checks these inputs under the current local runtime, not all possible inputs or future
library versions. No packages were installed. Exact rescoring also reproduced both old V1/V2
score files; frozen prompts, original cases, prior model replies and proposed target reviews were
not changed.

Saved Git-ignored artifacts, raw-file SHA256:

- `logs/qwen_protected_eval_reservation_pending_20260924.json`:
  `0026c7f909435a0d7a1cce5530c56dc91e4307e29ccdc3ce8fdd7d85c0318075`.
- `logs/qwen_draft_training_tokenizer_preflight_20260924.json`:
  `5af042ea35ca1bcb7d134920f643e1a9831c1ea5e9c936c6bf9f20151e0c3b9f`.

The saved historical preflight lists four blockers: incomplete curriculum review, incomplete protected
evaluation reservation, optimization worker not implemented and training environment not verified.

The [bounded optimization/save-reload worker](QWEN_LORA_WORKER.md) and synthetic tests are now
implemented under a separate launch contract. Isolated dependency provisioning and native tiny CPU
adapter verification are now complete; see [the measured smoke](QWEN_NATIVE_LORA_SMOKE.md).
The reviewed V2 candidate now exists. Actual Qwen fitting still requires protected evaluation and a bounded CUDA
resource trial. The 14 synthetic examples test language/review behavior, not trading edge;
actual-market learning still requires eligible causal order-book/CVD data. The failed capture
remains quarantined, and all execution remains paper-only.
