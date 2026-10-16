# Offline Qwen advisory evaluation and draft curriculum

Status (2026-09-24): **25 synthetic draft cases, an offline scorer and completed V1/V2 bounded
development batches**. Neither passed all declared checks; this is not a trading-quality pass
or a trained model. The scoring module performs no inference; the separately enabled batch
runner does. Neither performs downloads, market-data capture, training, policy promotion or
orders. The default runner and [local reviewer's](LOCAL_QWEN_REVIEWER.md) prompt are unchanged.

The default V1 prompt remains unchanged; a separately selected
[V2 Spot-long task and rubric](QWEN_REVIEW_CONTRACTS.md) is now implemented with backwards-compatible
replay. V2 recordings use schema version 2 plus `review_contract: spot_long_v2` and must bind the
V2 prompt and model-visible inputs. The approved V2 comparison passed only 1/7 full model checks;
see that record for the formatting, arithmetic and citation failures. The original examples/results
below describe V1 unless noted.

The operator-approved Qwen smoke test returned structurally valid JSON but unsupported optimism
from CVD/imbalance and costs alone. This regression suite distinguishes formatting from a small,
explicit set of expected advisory behaviors. Its targets and rationales are **agent-authored
drafts requiring operator review**, not approved training labels or market ground truth.

## Cases and split boundaries

[`configs/qwen_review_cases_v1.json`](../configs/qwen_review_cases_v1.json) contains 10 scenario
families, with 14 cases in `curriculum_draft` and 11 in `development_eval`. There are 21 model-review
cases (16 expected vetoes, 5 conditional supports) and 4 deterministic preflight-refusal cases.

- Positive CVD/order-book imbalance without calibrated after-cost expectancy: abstain (`veto`).
- Costs consuming gross edge, break-even estimates or negative stressed expectancy: veto.
- Conflicting CVD/order-flow imbalance and uncalibrated probability scores: no invented edge.
- Replenishment, absorption and stop-run proxies: no claim of confirmed hidden orders or profit.
- Positive supplied baseline/stressed net estimates: conditional support controls, not guaranteed
  returns or execution approval. Their calibration is a scenario assumption, not proven by a name.
- Untrusted instruction-like metric strings: do not treat data as instructions.
- Kill-switch/daily-loss flags: veto as an advisory regression. Actual risk checks remain
  deterministic and must block unsafe execution independently, before asking a model.
- Future, stale, mixed-symbol and foreign-session inputs: reject before any model invocation.

Each declared `source_session` belongs to one family, and each family belongs to one split.
The loader also rejects exact normalized duplicate evidence after removing identifiers and
normalizing numeric values/time offsets. This is **not semantic or near-duplicate detection**.
The deliberate malformed-scope cases test refusal; they are not model-training examples.

V1 model inputs contain only the production analyst payload: symbol, as-of timestamp, numeric
evidence and an empty prior. V2 additionally supplies the same fixed review question to every
case, never a case-specific target. Case IDs, family names, split assignments, expected verdicts,
citation rules and reference rationales are kept outside that payload. Generation code must use
`model_input(case, review_contract)`/the existing request builder, not hand the whole suite file
to a model. Omitting the contract retains V1.

This visible development split is **not a sealed final holdout**, and it must not later be
rebranded as one. Do not fine-tune on `development_eval`. Before actual training, review and freeze
targets, register a training manifest and independently reserve final evaluation cases. For
actual-market data, whole-session chronological splits, causal inputs, source-quality checks
and protected evaluation remain mandatory. This fixture does not make the quarantined capture
eligible for training and does not replace the numerical event-prediction dataset.

Exact suite SHA256 (raw UTF-8 bytes):

```text
5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659
```

Git attributes preserve LF for this pinned fixture on Windows. Any content change requires a
new recorded fingerprint and intentional regression review; hashes detect drift, not authenticity.

## Scoring contract and limitations

`research/advisory_evaluation.py` reads bounded, SHA256-pinned local JSON artifacts. It does not
load weights or import Torch/Transformers. Report files use exclusive creation, never overwrite.

Recorded-response envelopes bind the suite, model/checkpoint/prompt identity, case ID and exact
model-visible input hash. Missing cases stay in the report and verdict denominators. Failed calls,
input-binding mismatches, invalid JSON and unsupported citations cannot count as correct vetoes.
Schema errors, verdict agreement and required citation coverage are separate fields. Deterministic
preflight checks are reported separately from model-review quality. Reporting a preflight refusal
is not evidence of model reasoning.

Each citation group requires at least one of its supplied evidence IDs. Correct citations are
necessary but do not establish that the model interpreted them correctly. **Rationale semantics
are not automatically graded**: every case says `not_assessed_requires_operator_review`, even
when all mechanical checks pass. Human review must assess costs, conditionality, uncertainty,
proxy versus observation, unsupported claims and whether prose contradicts the verdict.

Support/veto recall and balanced verdict accuracy expose constant-verdict shortcuts: always-veto
and always-support each score 0.5 balanced accuracy on the full review set, not a full pass.
`unsafe_support_count` counts structurally valid support where the draft target expects veto;
it is a regression label, not a measured live-trading loss rate. Missing/failed replies count as
incorrect in verdict metrics. Partial-run aggregate scores describe coverage and must not be
presented as a completed benchmark. `coverage_complete` means all rows were supplied, not that
all calls succeeded.

All reports set `model_calls=0`, `orders=0`, `training_export_allowed=false` and
`promotion_allowed=false`. `model_calls` refers to this scoring operation; imported recordings
may have been produced by earlier model calls. These fields are informational boundaries, not
an OS sandbox or signed provenance. This scorer provides no training-data exporter or promotion
mechanism. A separate [reviewed-candidate workflow](QWEN_CURRICULUM_APPROVAL.md) now requires
explicit operator sign-off and source reconstruction; it still does not authorize actual training.

## Commands (PowerShell, repository root)

Demonstrate the harness by scoring authored references against their own draft targets:

```powershell
$suitePin = '5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659'
.venv\Scripts\python.exe -m ai_trader.research.advisory_evaluation --suite configs/qwen_review_cases_v1.json --suite-sha256 $suitePin --demo --output logs/YOUR_NEW_reference_demo.json
```

The expected 25/25 result tests the harness only. It is marked `synthetic_reference`, not Qwen
performance or independent validation. Use a new output path on each invocation.

Rescore the existing, already-approved one-call smoke without rerunning Qwen:

```powershell
$smokePath = 'logs/qwen_base_smoke_20260924_approval1.json'
$smokePin = (Get-FileHash -LiteralPath $smokePath -Algorithm SHA256).Hash.ToLowerInvariant()
.venv\Scripts\python.exe -m ai_trader.research.advisory_evaluation --suite configs/qwen_review_cases_v1.json --suite-sha256 $suitePin --smoke $smokePath --artifact-sha256 $smokePin --smoke-case g001_a --output logs/YOUR_NEW_smoke_review.json
```

Compare the artifact hash with the previously recorded value before use. Computing a hash of the
current file does not authenticate it. The original smoke artifact's recorded SHA256 is
`caa9f21c6c67c5e7e0a9d013e5dbd1aeeba2fbdba99c6d35e5acfcbbcd6d72dc`.
The smoke importer reconstructs and checks the original
request/prompt hashes. It does not trust `report_valid` as proof of sound judgment. This bridge
uses the original local reviewer configuration, including an existing interpreter path; it is
not automatically portable to a machine with different paths or a changed request-builder version.

For separately collected responses, replace `--smoke ... --smoke-case ...` with
`--responses PATH --artifact-sha256 SHA`. The exact envelope is:

```json
{
  "schema_version": 1,
  "suite_sha256": "<pinned suite SHA256>",
  "producer": {
    "kind": "recorded",
    "model_id": "Qwen/Qwen3-4B-Base",
    "checkpoint_sha256": "<pinned manifest SHA256>",
    "prompt_sha256": "<pinned prompt SHA256>"
  },
  "responses": [{
    "case_id": "g001_a",
    "input_sha256": "<digest(model_input(case))>",
    "status": "completed",
    "raw_response": "<unaltered model JSON string>"
  }]
}
```

Use `failed` or `preflight_refused` with `raw_response: null` where applicable. Preserve every
declared case, including failures; never repair invalid model JSON. Inputs/artifacts are limited
to 1 MiB each and the generated report to 2 MiB. CLI exit 0 means all mechanical checks passed;
exit 2 means a scored failure or incomplete coverage, with the report still retained.

## Recorded results and next gates

On September 24, offline scoring of `logs/qwen_base_smoke_20260924_approval1.json` bound its
unchanged input to `g001_a`: schema valid, observed `support`, draft target `veto`, one unsupported
support and **24 missing cases**. This is one retrospective regression, not an independent
25-case Qwen evaluation. The suite was authored after inspecting that smoke. The separate
authored-reference demo passed 25/25; it provides no model-performance evidence.

Reports are retained locally (Git-ignored):

- `logs/qwen_advisory_smoke_review_20260924.json`
- `logs/qwen_advisory_reference_demo_20260924.json`

The subsequently approved development batch is recorded below. Targets still require operator
review, and prose must be reviewed separately. Compare against simple controls before expanding
the curriculum or planning an isolated LoRA/QLoRA resource trial, adapter save/reload and protected
evaluation. The current 25-case draft is not adequate training data or evidence of trading skill.
No automatic continuous fine-tuning, service launch, paper-policy integration or live execution
follows from these checks.

## Frozen-plan development runner

`research/advisory_runner.py` adds a separately enabled local evaluation path. `prepare` performs
metadata/preflight checks only; it does not inspect weights or start a worker. The resulting plan
freezes the suite, full ordered development selection, input/request hashes, model/checkpoint,
interpreter, prompt and budgets. `run` requires its independently recorded raw-file SHA256 and
rebuilds the plan before dispatch. Labels and reference rationales never enter worker requests.

The current fixed profile is Qwen3-4B-Base, CUDA BF16, 2,048 input tokens, 256 generated tokens,
120-second worker deadline/reply lifetime and one analyst call per eligible case. It cold-loads
the model in a fresh process each time using the existing local-only worker and checkpoint pins.
Only `development_eval` is selected: this suite has **7 model cases and 4 preflight refusals**.
There is a hard ceiling of 7 worker attempts and 16 selected cases. The 840-second sum of worker
wait budgets is not a hard wall-clock or RAM/VRAM quota: process cleanup, filesystem work and
reporting add overhead. There are no retries, warm services, critics, model fallbacks or downloads.

Invalid report JSON is retained unchanged for scoring; it is not repaired or retried. A worker
failure, timeout, expired reply or invalid transport binding stops the batch, leaving remaining
cases missing. Deterministic input refusals do not launch a worker. Draft scores stay provisional;
running the suite does not approve its labels for training or promote the model.

Example preparation, after confirming the existing paths and previously recorded pins:

```powershell
$suitePin = '5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659'
$checkpointPin = '8a1a0f20ba8a2c6d4480309f0f442114c4fa310018d143ee610061b1ecf47d3c'
$checkpointPath = (Get-Item checkpoints/qwen3-4b-base-906bfd4b4dc7).FullName
$qwenPython = (Get-Item .venv-qwen/Scripts/python.exe).FullName
.venv\Scripts\python.exe -m ai_trader.research.advisory_runner prepare --suite configs/qwen_review_cases_v1.json --suite-sha256 $suitePin --checkpoint $checkpointPath --checkpoint-sha256 $checkpointPin --python-executable $qwenPython --output logs/YOUR_NEW_development_plan.json
Get-FileHash logs/YOUR_NEW_development_plan.json -Algorithm SHA256
```

Only after reviewing that plan and obtaining a bounded-run approval:

```powershell
$approvedPlanPin = 'REPLACE_WITH_THE_RECORDED_LOWERCASE_PLAN_SHA256'
.venv\Scripts\python.exe -m ai_trader.research.advisory_runner run --suite configs/qwen_review_cases_v1.json --plan logs/YOUR_NEW_development_plan.json --plan-sha256 $approvedPlanPin --output-dir logs/YOUR_NEW_development_run --enable-local-inference
```

The runner exclusively claims a new directory before dispatch. It writes `plan.json`, then an
`events.jsonl` log with flushed/fsynced intent before each case and completion afterwards. Final
`responses.json`, `score.json` and `run.json` retain raw replies, missing cases, draft scoring,
attempt counts and timings. Keyboard interruption retains completed rows and partial scoring,
then propagates the interruption. Persistence errors stop further calls; hard termination or
disk failure may leave only the plan and a partial event log. Inspect these without automatically
rerunning. There is no resume command or global cross-directory exactly-once guarantee, and this
local log is not signed, tamper-proof storage or an OS sandbox.

`run.json` reports worker attempts; `score.json` still reports zero model calls because scoring
itself is offline. The full 25-case score intentionally has 14 missing curriculum cases. Judge
this batch using its separate **development** summary, not full-suite coverage. The runner exits
0 only when all selected development checks pass and 2 on a scored failure/incomplete batch.
Neither exit code certifies semantic correctness, actual-market performance or training readiness.

Plan-file pins cover raw bytes, including the trailing newline. The `plan_sha256` inside run/event
artifacts is the canonical JSON digest without that newline; these two fingerprints intentionally
differ. The plan freezes request/configuration identities, not the entire installed environment.
Worker/package source and the provisioned interpreter remain trusted; this is not a hermetic
build or dependency attestation. Preserve the runtime lock/source revision alongside results.

Before a later prompt or training experiment, make the research question explicit. The current
v1 prompt mentions an "existing hypothesis" but the payload has no dedicated hypothesis field.
It also does not state the suite's precise stressed-expectancy decision rule. Therefore a failed
draft verdict can reflect an underspecified task as well as poor model reasoning. Do not silently
change v1 during a batch or relabel its failures afterwards. A follow-up should introduce a
versioned Spot-long review contract and an explicit abstention/cost-stress rubric while preserving
v1 replay. Deterministic arithmetic/risk checks remain authoritative; an LLM is not needed to
compute whether net expectancy is positive. Evaluate any revised contract under a new plan before
attributing an improvement to fine-tuning or committing to a larger training run.

### Approved batch result (2026-09-24)

The operator explicitly approved one development batch after the runner's tests passed: at most
seven local GPU calls, 120 seconds per call, plus four input-refusal checks, without training,
trading, downloads or retries. The frozen plan and unchanged v1 prompt were used exactly once.
All 11 selected cases finished in **276.406 seconds**. Seven cold worker calls took
37.453–40.781 seconds each; four invalid-input cases were refused before dispatch. Workers exited
and no model service remains running. No new memory-peak instrumentation was used in this batch.

- Strict report schema: **7/7 valid**. Required citation groups: **6/7 covered**.
- Expected draft verdict: **2/7 matched**, both positive controls. All seven actual verdicts were
  `support`; all five expected vetoes were missed. Veto recall 0, support recall 1, balanced verdict
  accuracy **0.5**, identical to an always-support control on these cases.
- Deterministic preflight checks: **4/4 correct**, separate from model quality.
- Development machine checks: 6/11 including those four preflight checks; **not an overall pass**.
  The 14 curriculum cases were intentionally not invoked. No final holdout was opened or claimed.

The following qualitative observations are agent inspection, **not operator-approved semantic
grades**; the scorer continues to mark rationale quality as unassessed.

| Case | Draft expectation | Actual verdict | Finding from the recorded explanation |
| --- | --- | --- | --- |
| g005_a: conflicting CVD/OFI | Veto | Support | Invents a bearish-sentiment hypothesis; no calibrated net edge supplied |
| g005_b: conflict + replenishment | Veto | Support | Calls 14-bps costs relatively low and infers a viable buy from proxies |
| g006_a: positive baseline, negative stress | Veto | Support | Describes −4-bps stressed expectancy as resilience |
| g006_b: costs exceed gross return | Veto | Support | Correctly describes a net loss, but supports that invented loss hypothesis |
| g006_c: uncalibrated score | Veto | Support | Treats 0.95 as strong confidence and omits the required cost citation |
| g007_a: positive baseline/stress | Conditional support | Support | Matches the draft verdict; does not establish calibration or real profitability |
| g007_b: positive baseline/stress | Conditional support | Support | Matches the draft verdict but claims downside protection without evidence |

Do not conclude that fine-tuning is impossible, necessary or already justified from this tiny,
draft evaluation. It exposes both underspecified v1 task semantics and unsupported reasoning.
First preserve this baseline, version an explicit Spot-long research question and rubric, and
evaluate that change under a new bounded approval. Do not change the current targets to rescue
the result, train on the development cases, or reuse them as a final holdout.

Local artifacts (Git-ignored):

- Plan: `logs/qwen_development_plan_20260924_approval2.json`; raw-file SHA256
  `54a52e45a1a235a37749e0bc20814258b251b6664a7cb1f09bd70ac1d5c65ec4`.
- Run directory: `logs/qwen_development_20260924_approval2/`, containing the copied plan,
  events, unaltered responses, score and run summary. Canonical plan digest in the event log:
  `c17d9dee4f10ebcb4d57b584b43dea3b982e0a80dab10e9a1c67167f9962e32e`.
- `responses.json` raw-file SHA256:
  `98ad8f2cb7cdb67295b96599a9f078b166b5e8f40faebcfd87bf8d690b396ad3`.
- `score.json` raw-file SHA256:
  `a0f63cf0cd6be96a90eaf0ec84916aafed6ed56f400710825485afe91fc780a7`.

No further model run, tuning, download, market-data capture, paper/live order or promotion was
performed. The existing inference and core environments passed dependency checks unchanged.
