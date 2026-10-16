# Protected evaluation dataset intake

Status (2026-09-24): custodian-side payload validation and metadata derivation are implemented
and tested with synthetic fixtures. **No real protected dataset has been supplied, generated or
reserved by this step.** The existing 14-target AI-reviewed candidate remains unchanged. Qwen
fitting has not started; the saved protected registry is still the original empty template.

Validation: 51 new synthetic intake tests; full suite **2,090 passed, one optional Nautilus skip**
(89.82 seconds). Ruff lint and formatting checks pass. The earlier 14-target candidate was
independently reverified against its unchanged raw source pins.

## What this adds

Previously, reservation validation could check declared hashes and identities but had no intake
tool to derive them from actual evaluation payloads. `research/protected_intake.py` now reads one
explicit, bounded, raw-SHA256-pinned dataset on the evaluation-custodian side. It produces only:

- `registry.json`: the existing metadata-only reservation format, with dataset/input/scenario
  hashes and case/family/session IDs derived from the supplied examples. Custodian attestation
  remains unset and `unexposed_attested` remains false.
- `receipt.json`: aggregate coverage, source bindings and mechanical-check results. It contains
  no evidence values, rationale text, per-case target labels or private dataset path.

Preparation requires a new output directory under an existing parent. All data checks run before
it claims the directory. Files are exclusively created and fsynced, with the receipt written last.
I/O failures retain any partial output, return a failure and do not retry. A receipt must pass
separate pinned reconstruction before it is trusted. Existing files/directories are not overwritten.

`verify` rereads the exact pinned private dataset and independently derives both artifacts. It
rejects content, provenance and authority changes, including a rationale-only edit to the dataset
under its old raw hash. It writes nothing. Neither command prints private inputs or labels;
validation errors use a generic message instead of echoing parser/payload details.

## Data and target checks

The source must be a separate `advisory_protected_dataset_v1` JSON document. Its exact fields are
`schema_version: 1`, `kind`, `dataset_id`, `review_contract: spot_long_v2`, and `cases`.
Use the actual contract string documented below; unknown fields or alternative contracts refuse.
Each case uses the established advisory-case encoding, with **`split: protected_eval`**:

- Case metadata: `case_id`, `family`, `split`, `source_session`, `as_of_ms`.
- `evidence`: 1–32 items, each containing `evidence_id`, `symbol`, `source_session`, `metric`,
  a bounded decimal-string `value`, `event_time_ms` and `available_time_ms`.
- `expected`: `support`, `veto` or `preflight_refusal`; `citation_groups`; `reference_rationale`.

The exact `review_contract` is the repository's `SPOT_LONG_V2` constant, not an arbitrary version
label. The development-suite loader still rejects this protected envelope and split, as do
default scoring and exposure-inventory interfaces. Shared strict case parsing does not make
protected examples eligible for training or turn them into exposed development cases.

The intake requires 1–64 cases and at least one support, veto and input-refusal example. It checks:

1. Evidence types, IDs, timestamps, bounded values, citation references and response schema.
2. Non-refused labels against the existing exact Spot-long arithmetic/risk rubric. The label
   does not drive the calculation. Positive estimates cannot override an active reported risk
   flag, missing estimates or a nonpositive stress result.
3. Refusal labels against the real local reviewer input preflight, with no response rationale
   or citation target permitted for those cases. No model is invoked.
4. Disjoint case IDs, families, source sessions, V2 model-input hashes and normalized scenario
   fingerprints against **all 25 exposed cases**, including curriculum and development.
5. No repeated normalized scenario content or case IDs within the submitted set, and no session
   shared by different families. Renaming IDs, shifting absolute time, reordering evidence or
   changing equivalent decimal formatting cannot conceal an exact normalized duplicate.

Every evidence item's session must match its case's declared session, including refusal cases.
This version therefore supports stale/future-input refusal cases, but not cross-session negative
fixtures that would disguise additional session provenance. Dataset bytes are capped at 1 MiB.

## Boundaries and limitations

This is a **custodian-side reader**, not an OS-isolated service, encrypted vault or authentication
system. Running it in a process necessarily exposes the private payload to that process. Do not
run it inside model-training input preparation or print its decoded data into a tuning transcript.
Only the derived registry belongs in the training launch's metadata interface; the training
launcher continues not to open protected payloads or labels. Aggregate coverage in the receipt
is not secret; it is not a per-case target export.

Mechanical checks do not review rationale semantics, establish calibration, authenticate a
custodian or prove unseen data/independent market evidence. They also do not detect semantic
near-duplicates, altered-number variants or exposures absent from the declared 25-case inventory.
Further previously exposed datasets must be accounted for before any independence claim. A
self-consistent forged payload/registry is not a genuine holdout. Both targets and provenance
still need substantiation; no sign-off switch is provided by this intake tool.

Accordingly, `target_semantics_reviewed`, `independence_authenticated`, `near_duplicates_checked`,
`reservation_complete`, `training_allowed`, `promotion_allowed` and `execution_allowed` remain
false. A successful intake produces a **pending** reservation, not permission to fit or trade.
This does not reintroduce human review of the 14 curriculum targets: their explicit
[delegated AI review](QWEN_DELEGATED_REVIEW.md) is complete. Evaluation custody is a separate
provenance question, not an opportunity to invent human attestations.

## Commands

Use a dataset derived and kept separately from curriculum development. The placeholders below
are intentionally not a downloadable dataset or a generated final holdout.

```powershell
.venv\Scripts\python.exe -m ai_trader.research.protected_intake prepare --suite configs/qwen_review_cases_v1.json --suite-sha256 5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659 --dataset C:/private/evaluation.json --dataset-sha256 RECORDED_PRIVATE_DATASET_RAW_SHA256 --output-dir logs/YOUR_NEW_protected_intake
.venv\Scripts\python.exe -m ai_trader.research.protected_intake verify --suite configs/qwen_review_cases_v1.json --suite-sha256 5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659 --dataset C:/private/evaluation.json --dataset-sha256 RECORDED_PRIVATE_DATASET_RAW_SHA256 --registry logs/YOUR_NEW_protected_intake/registry.json --registry-sha256 RECORDED_REGISTRY_RAW_SHA256 --receipt logs/YOUR_NEW_protected_intake/receipt.json --receipt-sha256 RECORDED_RECEIPT_RAW_SHA256
```

All CLI pins refer to raw file bytes; `registry_sha256` inside the receipt is a canonical-JSON
digest. Verification requires all four input pins. Preparation has no attestation/approval flag.
No new data downloads, Qwen inference, fitting, paper orders or live connectivity are performed.

Next: obtain/freeze separately sourced evaluation cases, validate targets and custody, and run
this intake before completing a real reservation. Then prepare a fresh source-pinned bounded
Qwen CUDA LoRA trial. Actual-market training also requires eligible causal order-book/CVD data;
this tool does not make the quarantined capture usable or prove a profitable strategy.
