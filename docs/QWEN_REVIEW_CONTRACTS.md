# Versioned Spot-long advisory contract

The first [Qwen development batch](QWEN_ADVISORY_EVALUATION.md) exposed an underspecified task:
the prompt referred to an existing hypothesis without supplying one. Qwen sometimes supported
its own bearish or loss hypothesis instead of assessing a Spot-long research proposal.

`models/review_contracts.py` adds an explicitly selected **`spot_long_v2`** task and prompt.
The default remains **`legacy_v1`**. This is a prompt/task clarification, not fine-tuning,
a numerical trading model, a new risk engine or permission to deploy Qwen.

## Fixed V2 question and rubric

The input's fixed `review_task` asks whether the supplied estimates conditionally support
research into a BTCUSDT Spot **LONG** entry after round-trip costs and stress. It defines support
and veto for that question alone; neither is an order, and veto is not an exit/short instruction.

The static system prompt requires:

- One unambiguous supplied gross-return, round-trip-cost, baseline-net and stressed-net estimate.
  Missing, duplicate or inconsistent estimates require veto.
- Nonnegative costs and baseline net equal to gross minus costs. Both baseline net and stressed
  net must be strictly positive; zero or negative is a veto under this research rubric.
- A nonzero supplied kill-switch or daily-loss-limit flag requires veto. Actual production risk
  checks stay in deterministic code and must not depend on the model noticing a flag.
- CVD, imbalance, classifier scores and liquidity proxies cannot substitute for net estimates,
  prove calibration, confirm iceberg orders or guarantee profit/downside protection.
- Conditional wording and decisive supplied citations; no invented evidence, sizing or tools.

These are **instructions to a fallible model**, not newly implemented deterministic arithmetic
or semantic enforcement. The existing independent risk/execution boundary is unchanged. Positive
supplied estimates are scenario assumptions, not proof of market edge. The fixed task and prompt
contain no case-specific answer, split, expected verdict, reference rationale or citation rubric.
Observed strings/prior explanations remain untrusted; prompting is not an OS/security sandbox.

## Compatibility and bindings

| Layer | Legacy V1 | Spot-long V2 |
| --- | --- | --- |
| Configuration selector | Default `legacy_v1`; omitted from serialized legacy configuration | Explicit `review_contract: spot_long_v2` |
| Worker protocol | `local_advisory_reviewer_v1` | `local_advisory_reviewer_v2` |
| Input | Existing five fields | Same evidence plus a fixed `review_task` |
| Response/score/run artifact schema | Version 1, no contract field | Version 2 with explicit `review_contract` |
| Frozen-plan schema | Version 1 | Version 1; selector is pinned inside the configuration |

Legacy prompt/request/configuration bytes and hashes are preserved, not merely mapped to an
equivalent default. Offline replay verified the original smoke's request binding, the exact V1
batch plan and the full original V1 score unchanged. Unknown contracts are refused, not mapped to
a default. The worker reconstructs the selected contract and rejects a tampered task, prompt,
protocol or configuration before generation. Both Base completion and chat-template paths use
the validated request's selected prompt. The historical smoke harness remains V1-only.

V2 response recordings require the V2 prompt digest and V2 model-input hashes. Cross-version rows
fail input binding even when their case IDs match. Recorded raw output is never rewritten to fit
the new rubric. Versioned reference demos remain authored-target harness checks, not Qwen evidence.
The 25-case suite and all target verdicts/citation groups remain unchanged; the development split
is exposed research data, not a sealed final holdout.

Prompt SHA256 values (canonical JSON string digests):

- V1: `463834a90c2bce8bc10d45321858d8bd4804fadf7c5712f64221a7a26cd89662`
- V2: `303e86702ea20f5f44de3920533a1f45466023211c44476f9ee353b79b15c7ea`

Do not change a version's text in place after recording a run. A later prompt experiment needs
a new version, new frozen plan and bounded approval. Local hashes are drift checks, not signed
provenance or a guarantee of identical outputs across changed runtimes/hardware.

## Prepare or score without inference

From the repository root in PowerShell, using the existing provisioned checkpoint/environment:

```powershell
$suitePin = '5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659'
$checkpointPin = '8a1a0f20ba8a2c6d4480309f0f442114c4fa310018d143ee610061b1ecf47d3c'
$checkpointPath = (Get-Item checkpoints/qwen3-4b-base-906bfd4b4dc7).FullName
$qwenPython = (Get-Item .venv-qwen/Scripts/python.exe).FullName
.venv\Scripts\python.exe -m ai_trader.research.advisory_runner prepare --suite configs/qwen_review_cases_v1.json --suite-sha256 $suitePin --checkpoint $checkpointPath --checkpoint-sha256 $checkpointPin --python-executable $qwenPython --review-contract spot_long_v2 --output logs/YOUR_NEW_v2_plan.json
Get-FileHash logs/YOUR_NEW_v2_plan.json -Algorithm SHA256
```

Preparation does not load weights or spawn a worker. Running requires the existing `run` command,
the recorded raw-file plan hash, a new output directory and `--enable-local-inference`, following
separate approval. The fixed budget remains seven workers at most, 120 seconds each, 2,048 input
and 256 output tokens, no retry/fallback/training/trading/download. Evidence preflight still
rejects four invalid-input cases without model calls. See the runner contract for failure records.

An entirely offline V2 reference demo is also available:

```powershell
.venv\Scripts\python.exe -m ai_trader.research.advisory_evaluation --suite configs/qwen_review_cases_v1.json --suite-sha256 $suitePin --demo --review-contract spot_long_v2 --output logs/YOUR_NEW_v2_reference_demo.json
```

Recorded-response scoring reads the contract from the artifact; do not pass `--review-contract`
to relabel a recording. The scorer still separates schema, verdict and citation checks and leaves
rationale semantics unassessed. Training export and promotion remain disallowed.

## Approved V2 comparison result (2026-09-24)

After the operator approved one bounded comparison and the full suite passed, V2 ran exactly
seven local model calls plus four input-refusal checks. The checkpoint, numeric evidence, case
selection, draft targets and generation budgets were unchanged. Only the versioned prompt/task
contract changed. There were no retries, downloads, training, promotion or orders.

The batch completed in **291.406 seconds**, with cold calls taking 39.922–46.656 seconds each.
All workers exited. This is one experiment on already-exposed synthetic development cases, not
an independent holdout, a statistical performance estimate or a trading benchmark.

| Development metric | V1 | V2 |
| --- | --- | --- |
| Strictly valid model reports | 7/7 | 4/7 |
| Draft verdict matches, invalid reports counted wrong | 2/7 | 4/7 |
| Full schema + verdict + required-citation checks | 2/7 | 1/7 |
| Expected vetoes correctly returned in valid reports | 0/5 | 4/5 |
| Positive controls correctly returned in valid reports | 2/2 | 0/2 |
| Balanced verdict accuracy | 0.5 | 0.4 |
| Deterministic input refusals, separate from model quality | 4/4 | 4/4 |

**V2 is not an overall improvement or a promotion candidate.** The positive controls failed
output validation, not because the model returned valid vetoes. Invalid outputs remain failures
in all verdict denominators. V2's zero `unsafe_support_count` concerns valid reports only;
it must not hide unsupported support inside rejected output. Four input refusals are not four
successful model judgments. The 14 curriculum cases were intentionally not invoked.

Failure inspection (agent observations, not operator-approved semantic grades):

- `g005_a`: support with a 1,213-character rationale, exceeding the 512-character limit. It
  called nonnegative costs a positive factor and wrongly claimed supplied flow evidence was absent.
- `g005_b`: the only full mechanical pass; still called 14-bps costs relatively high without an
  edge comparison. A mechanical pass therefore remains insufficient to approve its prose.
- `g006_a`: correct veto, missing the required net citation; falsely claimed 30 exceeded 35 and
  turned the supplied positive 5-bps net estimate into −5. Negative stress still warranted veto,
  but the explanation was numerically wrong.
- `g006_b`: correct veto with consistent arithmetic, missing the required gross-return citation.
- `g006_c`: correct veto for insufficient estimates, missing the required classifier-score citation.
- `g007_a`: emitted the schema placeholder followed by a second JSON object, so strict parsing
  rejected it. No second-object extraction/repair was performed.
- `g007_b`: appended `Critic JSON:` and another report to its analyst answer. This was text from
  one call, not a second critic invocation; the extra output was rejected unchanged.

Preserved local artifacts (Git-ignored):

- `logs/qwen_development_plan_v2_20260924_approval3.json`, raw-file SHA256
  `fb70c7cdc5cdff25462bae00dc5c41cea004182fef6a82719ddc472f40a537cd`.
- `logs/qwen_development_v2_20260924_approval3/`, with plan, events, responses, score and run summary.
  Canonical plan digest: `ebf7e9637aedf1ddca5edbfa11a5cee05eb2576875c5705146ebd3a480aa436f`.
- `responses.json` raw-file SHA256:
  `384e8d199891d396e60d3e1ebceb3637f8c3da8984ccec042facf14bcf9a4f6d`.
- `score.json` raw-file SHA256:
  `187fb394f1ea7c47fa7a4d45c494ca3e3a772105d5d8c2c4f6bc1ee0cbff6204`.

The [deterministic evidence/arithmetic checker](SPOT_LONG_EVIDENCE_CHECKS.md) is now implemented
as a separate offline sidecar, preserving both recorded scores exactly. It also prepares 14 pending
curriculum fact packets, excluding the development cases. The
[versioned approval workflow](QWEN_CURRICULUM_APPROVAL.md) now has 14 agent-reviewed proposals,
pending operator decisions. Next: resolve those reviews and register protected evaluation before
training. Validator decisions remain separate from
raw model replies and are not presented as better model reasoning. Do not
relax the JSON/length/citation rules to rescue this experiment, or keep adjusting this prompt
against the same seven cases until it appears to pass. Any LoRA/QLoRA trial remains a separate
environment/resource approval after training targets and protected evaluation are ready. These
two small batches do not prove that fine-tuning is impossible or that it will solve the failures.
