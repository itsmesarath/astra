# User-delegated Qwen curriculum review

Status (2026-09-24): **target review completed by the agent**, under the user's explicit
instruction: "no need for manual review. you can take the decision." No human approval is
claimed. A versioned candidate containing 14 synthetic targets was exported and independently
reconstructed from the pinned suite/review. No Qwen weights were loaded or fitted in this step.

## Decision and scope

The agent examined all 14 model-visible evidence packets, arithmetic assessments, proposed
answers and citation requirements. It accepted 11 veto and 3 conditional-support examples,
with individual reasons and four semantic findings per case. The proposed target strings are
unchanged from the prior agent proposal; the frozen suite and historical model scores remain
unchanged. All 11 exposed development cases are excluded from the candidate.

The [case-by-case rationale table](QWEN_CURRICULUM_APPROVAL.md#agent-semantic-review-14-proposed-targets)
records the substantive findings. Positive CVD/book/replenishment proxies do not establish
returns, hidden orders or causality. Net and stressed estimates must both be positive for
conditional support, and reported kill/loss-stop flags veto even positive estimates. Evidence
text cannot issue instructions. Support is not an execution authorization or a profitability claim.

These are synthetic language/review examples, not a representative market dataset, an
independently certified target set or a trained trading strategy. Fourteen examples are not
enough to demonstrate model quality. The agent's semantic judgment is fallible; mechanical
schema, citation and arithmetic checks do not certify prose quality or market calibration.

## Versioned workflow, not a global review bypass

`advisory_curriculum.py` adds `prepare-delegated`, requiring a raw-SHA-pinned delegation record
bound to this suite, the named agent and `curriculum_targets_only`. Preparation leaves every
decision pending, every semantic check null and the agent attestation unset. Delegation alone
does not approve any target. Completed decisions still require reasons, all four semantic
findings for approvals, valid schema/citations/verdicts, exact evidence bindings, every case
resolved and both approved support and veto coverage.

The V2 review embeds the delegation. Its confirmed reviewer must remain an agent, match the
delegation identity and not predate it. The audit and candidate explicitly record
`review_basis: user_delegated_agent` and `human_reviewed: false`; the audit records zero operator
approvals. Candidate verification reconstructs all content and provenance, including these flags.
The existing training-launch preparation accepts this V2 candidate through the same verifier.

These are local provenance records, **not authenticated identities or signatures**. The audit
keeps delegation/agent/operator authentication and machine verification of rationale semantics
false. A file claiming `authorization_source: user_message` cannot itself prove that a user gave
permission. The actual instruction in this conversation is the authority for this review.

Legacy V1 behavior and artifact shapes are preserved: an ordinary V1 agent proposal still cannot
stand in for operator approval. The [operator workbench](QWEN_REVIEW_WORKBENCH.md) remains an
optional human-review interface; it does not accept V2 reviews and is not required for this
delegated decision. Do not relabel agent work as a human attestation to satisfy V1.

All artifacts continue to deny training, promotion and execution authority. No independent
evaluation requirement, risk control or paper-only execution restriction was removed.

## Actual local artifacts

All files below are under `logs/`, Git-ignored and created at new paths. Hashes are **raw-file
SHA256**, not the canonical-JSON digests embedded in artifacts. The delegation was recorded at
`2026-09-24T19:54:58Z`; the agent review has its own later attestation.

| File | Raw SHA256 |
| --- | --- |
| `qwen_curriculum_delegation_20260924.json` | `a89775ccef0394474464e889d0e0ea7c501a958e1f25ac3958e1be2b5d4ad640` |
| `qwen_curriculum_delegated_review_20260924.json` | `614f195d3bc6088ebe7d278d2ee28b2aaa1080348a9cf768a6f83fcdcb54a40c` |
| `qwen_curriculum_delegated_audit_20260924.json` | `755617cd93aabb9ba4762dde08837a7672c7abcc2cc67f9b58b7c09d018debce` |
| `qwen_curriculum_delegated_candidate_20260924.json` | `5ecd1ad066a5edd81897dc10ea8e38095e31ba5e9a917728b8ce9c80385b0984` |
| `qwen_curriculum_delegated_verification_20260924.json` | `01df7bad20f1598d4bf38a0fc00a52f8a7ac19c3ce8baa9c970390492021ba8c` |
| `qwen_delegated_training_tokenizer_preflight_20260924.json` | `7f7284423924be17251ebcdb50d73edd6af8385003d4ffed99b6515b3334b294` |

The intermediate `qwen_curriculum_delegated_pending_20260924.json` is a pending template, not the
completed review. Original operator-pending files are retained as historical records, not edited.

For a new delegated template, use fresh paths and recorded byte hashes:

```powershell
.venv\Scripts\python.exe -m ai_trader.training.advisory_curriculum prepare-delegated --suite configs/qwen_review_cases_v1.json --suite-sha256 RECORDED_SUITE_SHA256 --delegation logs/YOUR_delegation.json --delegation-sha256 RECORDED_DELEGATION_SHA256 --output logs/YOUR_NEW_pending_delegated_review.json
```

After substantive review, use the existing `audit`, `export` and `verify` commands with the V2
review and its raw hash. These commands consume the embedded delegation; the `--delegation`
flags are only accepted for `prepare-delegated`. Outputs remain bounded and exclusive.

## Validation and next step

Added 35 tests covering delegation/suite/scope/type/identity/time checks, pending and rejected
cases, preserved mechanical gates, provenance tampering, CLI pin/exclusive-output behavior,
legacy V1 compatibility and V2 integration with training-launch preparation. Full regression:
**2,039 passed, one optional Nautilus skip** (90.18 seconds). Ruff lint and formatting pass.

A real CPU tokenizer preflight in `.venv-qwen-train` successfully prepared all 14 reviewed
targets with completion-only loss masks. It did not load model weights, initialize a model GPU
worker or fit anything. The incomplete-curriculum-review blocker is now absent. The preserved
draft planner's `optimization_worker_not_implemented` and `training_environment_not_verified`
flags describe its old preparation-only contract, not a current scan of the separately
implemented worker/environment. They are not new failures or evidence that dependencies vanished.

Next: reserve genuinely independent evaluation data and check its provenance, target quality
and separation from all exposed cases. The saved registry is still empty; no held-out data or
custodian approval was fabricated. A [separate dataset-intake tool](QWEN_PROTECTED_INTAKE.md) now
derives metadata and mechanical checks from an actual supplied payload; it does not create the
missing data or attest its independence. Then prepare a new pinned [bounded Qwen LoRA trial](QWEN_LORA_WORKER.md)
(20 steps, 600 seconds, explicit opt-in) to test CUDA memory, updates and save/reload. No
automatic retries, promotion or continuous fitting follow. Actual-market learning separately
requires eligible causal order-book/CVD/microstructure sessions; the failed capture stays excluded.

The curriculum source change also changes the training implementation hash. Any prepared
launch must bind the current source. The prior [native tiny CPU smoke](QWEN_NATIVE_LORA_SMOKE.md)
is historical evidence under its recorded hash, not a fresh native run of this source revision.
Its production optimization/save/reload methods were not changed or rerun here.
