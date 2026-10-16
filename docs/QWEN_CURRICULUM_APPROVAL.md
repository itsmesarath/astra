# Qwen curriculum review and candidate-export workflow

Status (2026-09-24): implemented, offline and tested. The user explicitly delegated target
decisions to the agent. All 14 are now accepted in a [V2 AI-reviewed candidate](QWEN_DELEGATED_REVIEW.md),
with no claim of human approval. Manual target review is no longer required for this candidate.
Independent evaluation remains incomplete; no Qwen fitting or model promotion has occurred.

The optional [offline target-review page](QWEN_REVIEW_WORKBENCH.md) presents all 14 proposed answers,
evidence and arithmetic for a separate V1 human review. It resets all human confirmations and
exports only a review JSON for independent audit; no human approvals were entered by the agent.
Browser visual verification remains pending because the browser tool blocked local-file URLs.

`training/advisory_curriculum.py` provides `prepare`, `prepare-delegated`, `audit`, `export` and `verify`. It
uses the existing frozen suite, Spot-long V2 prompt and independent arithmetic checker. It
never loads a model, downloads packages, trains weights, starts capture or places orders.

## Review contract

Preparation reconstructs the curriculum fact packet and creates a versioned review template.
It binds the suite, fixed prompt, checker version, entire packet and every case's original
input/target/facts. It includes exactly `curriculum_draft`, never `development_eval`. A changed
input, original target, split, prompt or numerical assessment invalidates the old review.
This does not create a new final holdout: the existing development set is already exposed.

Each review row has:

- `decision`: `pending`, `approve` or `reject`.
- `target_response`: the proposed strict JSON reply, initially the frozen draft reference.
  Revised wording/citations are allowed without altering the frozen original. The verdict must
  match the original and the independent rubric; disagreement needs a new reviewed suite version.
- Four nullable boolean attestations: `rationale_supported`, `citations_sufficient`,
  `uncertainty_preserved`, and `no_execution_authority`.
- A bounded review note, required for either approval or rejection.

There must be exactly one row for every curriculum case. Unknown/development cases, duplicates,
missing rows, changed bindings, unknown fields, malformed confirmations and oversized values fail
closed. `audit` reports pending or unresolved cases without quietly dropping them. Approved
targets additionally pass the existing strict response schema, required citation groups, frozen
verdict and independent numeric checks. A preflight-refused case cannot be approved.

Candidate export requires every case resolved, every approved row passing its mechanical checks,
all four semantic attestations true, a reason for each decision, at least one approved support
and one approved veto, and an eligible reviewer attestation with ID and UTC timestamp. Legacy
V1 requires an operator; V2 accepts an explicitly delegated agent under the scoped, pinned
[delegation contract](QWEN_DELEGATED_REVIEW.md). Rejected cases remain accounted for outside the
exported examples. An all-veto curriculum or an undelegated V1 agent attestation cannot satisfy
these gates. Delegation is never a claim that the operator personally checked each rationale.

**Trust boundary:** these are local attestations, not authenticated identities or digital
signatures. Software cannot prove that a person read a sentence or understood it. A knowingly
false rationale can still pass if someone falsely attests to it; tests preserve that limitation.
`operator_identity_authenticated` and `rationale_semantics_machine_verified` remain false.
The checker verifies supplied arithmetic, not market calibration, causality or profitability.

## Candidate is not permission to train

Export creates one bounded JSON candidate, separating exact model-visible inputs and reviewed
responses from split/family/session metadata and review bookkeeping. Do not pass the whole
artifact to a model. Input building must continue to use only the established model payload;
targets are supervised completions, never prompt-side answers. No tokenization, loss masking,
trainer, optimizer or checkpoint save is implemented by this workflow.

`verify` independently rebuilds the candidate from the pinned suite and review and compares every
field, including the prompt, inputs, targets, exclusions and authority flags. Recomputed hashes
inside a tampered candidate do not substitute for reproducing the external source artifacts.
Raw-file CLI pins and internal canonical-JSON digests are distinct and deliberately labeled by
context: `--review-sha256` pins bytes; the audit/candidate's `review_sha256` binds canonical content.

Even a valid candidate has `training_allowed: false`, `promotion_allowed: false` and
`execution_allowed: false`. The remaining training gates are protected evaluation registration
and a tested, bounded training plan/environment. These blockers are this workflow's explicit
scope, not an automatic scan/certification of every environment on the machine.

## Legacy operator-review commands (optional)

All input files use the existing bounded SHA-pinned strict-JSON reader. Outputs are at most 1 MiB,
created exclusively and never overwritten. Use a new output path each time. A write failure can
leave an incomplete file; it is not a completed artifact and must not be silently reused.

```powershell
$suitePin = '5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659'
.venv\Scripts\python.exe -m ai_trader.training.advisory_curriculum prepare --suite configs/qwen_review_cases_v1.json --suite-sha256 $suitePin --output logs/YOUR_NEW_pending_review.json
```

Review the inputs/facts in [the numeric packet](SPOT_LONG_EVIDENCE_CHECKS.md), original references
and proposed replies. Save reviewed changes under a new filename; do not edit the frozen suite
or recorded model responses. Only the actual operator should replace the proposal's agent
attestation with their own operator identity/time, confirm it, and explicitly approve or reject
each case. Record the edited file's hash once the review is frozen. This is a deliberate record
of a completed review, not a script that marks every case approved.

```powershell
$reviewPin = 'REPLACE_WITH_RECORDED_OPERATOR_REVIEW_RAW_SHA256'
.venv\Scripts\python.exe -m ai_trader.training.advisory_curriculum audit --suite configs/qwen_review_cases_v1.json --suite-sha256 $suitePin --review logs/YOUR_OPERATOR_review.json --review-sha256 $reviewPin --output logs/YOUR_NEW_review_audit.json
.venv\Scripts\python.exe -m ai_trader.training.advisory_curriculum export --suite configs/qwen_review_cases_v1.json --suite-sha256 $suitePin --review logs/YOUR_OPERATOR_review.json --review-sha256 $reviewPin --output logs/YOUR_NEW_candidate.json
$candidatePin = 'REPLACE_WITH_RECORDED_CANDIDATE_RAW_SHA256'
.venv\Scripts\python.exe -m ai_trader.training.advisory_curriculum verify --suite configs/qwen_review_cases_v1.json --suite-sha256 $suitePin --review logs/YOUR_OPERATOR_review.json --review-sha256 $reviewPin --candidate logs/YOUR_NEW_candidate.json --candidate-sha256 $candidatePin --output logs/YOUR_NEW_candidate_verification.json
```

`audit` returns exit **2** for a valid but incomplete/blocked review, retaining the diagnostic
report. Export refuses it before opening an output file. Successful export/verification means
only candidate consistency, not training readiness or model quality. Missing/bad hashes are
errors; pins cannot be omitted for convenience.

## Agent semantic review: 14 proposed targets

The agent read every curriculum input, original rationale and citation requirement. The table
records the review findings; exact proposed JSON responses, expanded citations and case-specific
notes are in `logs/qwen_curriculum_agent_review_20260924.json`. All verdicts are unchanged.
The preserved V1 proposal is explicitly attested as `reviewer_type: agent`, with every operator decision still
`pending`. Its true checklist values are **agent findings only**, not human approvals or automatic
semantic grades. All 14 proposed targets separately pass schema/verdict/required-citation checks.

| Cases | Finding and proposed correction |
| --- | --- |
| `g001_a` | Positive CVD/book imbalance and 12-bps costs do not supply gross/net/stress estimates. Name the missing estimates and cite flow, book and costs. |
| `g001_b` | Larger positive proxies still do not quantify returns. No arbitrary strength threshold or invented calibration; same missing-estimate veto. |
| `g001_c` | Negative flow/book observations do not provide a quantified LONG expectancy, or authorize shorting. Costs are 6 bps; return estimates are missing. |
| `g002_a` | Explicitly state 10 − 12 = −2 bps net and −5 bps stress; cite all four estimates. Both estimates are negative, not guaranteed realized losses. |
| `g002_b` | Explicitly state 12 − 12 = 0 bps and −4 bps stress. Break-even fails the strictly-positive rule. |
| `g002_c` | Replace unsupported **“cost stress”** with the supplied stressed-net estimate. Net is 17 − 12 = +5 bps, stress is −1; the stress mechanism is unknown. |
| `g003_a` | State 20 − 12 = +8 bps, stress +3, with all four citations. Support remains conditional, not proof of calibration/profit or authority to trade. |
| `g003_b` | State 14 − 12 = +2 bps, stress +0.25, without rounding the positive stress away or claiming robustness. |
| `g004_a` | Replace vague “needs interpretation” prose with positive CVD and a −2-bps observed price change. Do not infer a causal absorption mechanism or confirmed iceberg. Return estimates are missing. |
| `g004_b` | A stop-run proxy and observed +8-bps price move are not evidence of actual stops or forward gross return; do not treat that move as an edge against 12-bps costs. |
| `g009_a` | Instruction-like metric text is data without authority. CVD and 10-bps costs do not supply the missing return estimates. |
| `g009_b` | Ignore the injected veto instruction. State 23 − 10 = +13 bps, stress +4, with conditionality and no order authority. |
| `g010_a` | State 22 − 12 = +10 bps, stress +2, but the **reported** active kill flag vetoes. This does not verify actual account state. |
| `g010_b` | State 24 − 12 = +12 bps, stress +5, but the **reported** daily-loss stop vetoes. No account loss is measured or reset by this review. |

Original frozen references, prompt versions, model replies and scores were not changed. Revisions
are proposals in a separately pinned artifact. Fourteen synthetic examples are a language/schema
seed curriculum, not enough to establish trading quality or a representative market training set.

Local Git-ignored artifacts, raw-file SHA256:

| Artifact under `logs/` | SHA256 |
| --- | --- |
| `qwen_curriculum_pending_review_20260924.json` | `7a66452efa537a0c79dabdcf0c1fcfcfeccd8e492d3b73f7bd0210dee81a1ac5` |
| `qwen_curriculum_agent_review_20260924.json` | `ebbc3b756b651e70f9fb04b005b351c1c09f4b9054ffdc0fd69f74e7e7f0fb60` |
| `qwen_curriculum_agent_review_audit_20260924.json` | `4281f5380240f6fb4e3be4c48799e8d464a002638ae9871c6deb73d661576b65` |

That historical V1 audit denies candidate export. It created no candidate or operator approval.
The subsequent [delegated V2 review](QWEN_DELEGATED_REVIEW.md) accepts these same proposed targets,
exports a real candidate and records agent decisions only. The old files remain unchanged.

## Remaining work before a Qwen training trial

The [metadata-only holdout boundary and training preflight](QWEN_TRAINING_PREFLIGHT.md) are now
implemented. All 14 proposed replies fit the local tokenizer budgets, with completion-only loss
masks. The new V2 candidate is AI-reviewed, not human-approved or a completed evaluation reservation.

1. Completed: explicit user-delegated agent review, candidate export and independent reconstruction.
2. Register protected final evaluation separately from exposed development examples, with
   family/session and duplicate boundaries. Do not relabel these visible development cases as sealed.
3. Completed in a separate `.venv-qwen-train`: a [self-contained training lock and native tiny
   CPU LoRA smoke](QWEN_NATIVE_LORA_SMOKE.md) now verify real gradients, frozen base parameters and
   exact adapter reload through the production backend methods. Actual Qwen CUDA BF16 memory
   feasibility remains untested. `.venv-qwen` is still inference-only and unchanged; quantization
   is a choice to evaluate, not presumed mandatory.
4. Run a small explicitly bounded training/save/reload/evaluation trial before expanding the data
   or fitting budget. Do not promote from training loss or this small synthetic curriculum alone.

No further permission is needed for ordinary in-scope development work, but permission does not
replace evidence that targets are correct or training is ready. Actual-market tactical learning
also needs eligible causal order-book/CVD data; the failed public capture remains quarantined.
