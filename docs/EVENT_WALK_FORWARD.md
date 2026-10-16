# Registered event walk-forward evaluation

Implemented in `training/event_walk_forward.py`, verified with synthetic fixtures only. This is
offline predictive research using the [numerical event baseline](EVENT_BASELINE.md), not an
execution policy, Qwen training, continuous learning or evidence of profitable paper trading.

## Freeze the whole schedule before fitting

`register_event_walk_forward` reads registration metadata only and exclusively publishes a plan.
The plan freezes the initial training prefix, all later evaluation sessions, source-quality gates,
embargo, budgets and one shared training recipe. For four chronological research sessions:

| Fold | Train from scratch | Evaluate once |
| --- | --- | --- |
| 0 | S1, S2 | S3 |
| 1 | S1, S2, S3 | S4 |

Every source is exclusive within each fold. A past evaluation session may enter a later training
prefix, but never an earlier one. This is a separate walk-forward protocol; existing fixed-split
manifests are not changed. Reserved sessions remain metadata-only and never enter a model or metric.
At every training/evaluation and evaluation/next-source boundary, require
`previous_source_end + embargo_ns < next_source_start`; equality fails. Every row's feature and
outcome availability must remain inside its source and before its fold cutoff, including unknown
outcomes. Labels may mature out of feature order; they are not sorted by future resolution time.

Each fold refits the baseline's medians, missing-value channels, standardizer and classifier from
its earlier training sessions only. Epochs, learning rate, L2, feature schema, controls and metric
definitions do not change between folds. There is no warm start, validation-guided checkpoint,
best-fold selection, hyperparameter search or final all-data refit. Changing the recipe is a new
experiment. Checksums/exclusive files identify artifacts, not proof of unseen data or authentication;
a complete cross-experiment registry remains future work.

## Verification and failure accounting

`evaluate_registered_event_walk_forward` requires `enable_training=True` on every call, before
input access. The CLI requires `--enable-training`. All research sources must be supplied once,
in declared order, before any capture or label input is read. Their entire artifacts are reproduced
from pinned capture bytes through the [verified event loader](EVENT_TRAINING_DATA.md). Each capture
and label artifact is read once across the whole run; reserved/unknown/duplicate/omitted/reordered
sources are refused. Corruption, code/environment drift and numerical errors abort publication.

Every scheduled fold remains in the report. A quality failure blocks folds that use that source;
it does not erase the source or earlier healthy folds. Fewer than two observed training classes
blocks that fold without fabricating labels. The report is `incomplete`, and pooled metrics are
withheld, if **any** planned fold is blocked. Completed folds remain available as diagnostics, not
a passing subset presented as the whole experiment.

For a complete run, concatenate the once-only out-of-sample probabilities and targets and recompute
metrics; do not average fold F1, calibration bins or log losses. Training-majority and Laplace-prior
controls are recomputed from each fold's training prefix; the uniform control stays fixed. Pooled
metrics are event-weighted, not equal-session averages. Duplicate prediction identities are rejected.
Overlapping labels are dependent; prediction counts are not independent trades. There is no PnL,
confidence interval, significance claim, fitted calibration, trading threshold or promotion.

## Limits and output

- Require 3–32 research sessions, at least one initial training session and two evaluation sessions.
- At most 10,000 declared source frames and 64 MiB combined capture/label reads across the run.
- Repeated training prefixes count toward the 2,000,000 declared frame-epoch budget:
  `sum(prefix_session_counts) * max_frames_per_session * epochs`.
- Plans are capped at 1,000,000 bytes; complete checksummed reports at 8 MiB. Existing output or
  quarantined partial paths are refused. Publication uses the existing exclusive staged publisher.

The report contains the plan, source diagnostics, every fold's status/model/fit/metrics/predictions,
and pooled metrics only when all folds complete. It records model-training outcome availability and
reserved-source reads (zero). This multi-model report is not a standalone baseline-model reload
artifact or deployment approval. No shadow/runtime adapter consumes it yet.

## Commands

Safe help and synthetic tests:

```powershell
.venv\Scripts\python.exe -m ai_trader.training.event_walk_forward register --help
.venv\Scripts\python.exe -m ai_trader.training.event_walk_forward evaluate --help
.venv\Scripts\python.exe -m pytest -q tests/test_event_walk_forward.py
```

Operator examples only, not run on actual captures during development. First freeze the plan for
an existing current-code registration with four research sources followed by reserved sources.
Paths and numeric settings are placeholders, not statistically approved sample criteria:

```powershell
.venv\Scripts\python.exe -m ai_trader.training.event_walk_forward register --registration data/processed/REGISTRATION.json --output data/processed/NEW_WALK_PLAN.json --initial-training-sessions 2 --max-frames-per-session 1000 --embargo-ns 0 --minimum-resolved-per-session 100 --minimum-resolved-fraction 0.5 --epochs 50 --learning-rate 0.05 --l2 0.001
```

Generate research-only event-label artifacts at the plan's exact frame budget. After approved inputs
meet meaningful predeclared quality/sample gates, this explicit command starts numerical fitting:

```powershell
.venv\Scripts\python.exe -m ai_trader.training.event_walk_forward evaluate --registration data/processed/REGISTRATION.json --plan data/processed/NEW_WALK_PLAN.json --source S1 data/raw/S1.jsonl data/processed/S1_LABELS.json --source S2 data/raw/S2.jsonl data/processed/S2_LABELS.json --source S3 data/raw/S3.jsonl data/processed/S3_LABELS.json --source S4 data/raw/S4.jsonl data/processed/S4_LABELS.json --output data/processed/NEW_WALK_RESULT.json --enable-training
```

CLI output is compact status/checksum metadata. Exit 0 means every scheduled fold completed;
exit 2 means an incomplete diagnostic report was published. Neither means profitable or ready to trade.

A [sealed single-baseline shadow adapter](EVENT_SHADOW.md) now records predictions on later sources
without execution. It does not select or deploy a walk-forward fold; final-fit policy remains future
work. Actual-data readiness and explicit policy/risk/paper evidence gates remain necessary.
No actual market dataset, public feed, account credential, model deployment or live connection was
accessed by this implementation. The default paper runtime is unchanged.
