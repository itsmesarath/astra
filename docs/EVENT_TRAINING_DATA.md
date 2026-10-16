# Verified event datasets and whole-session research folds

Implemented in `training/event_training_data.py`, with synthetic-only tests. This extends the
[event-label builder](MICROSTRUCTURE_EVENT_LABELS.md); it does not fit a model, open a journal,
connect to a feed, install anything or execute trades.

## Freeze the split before inspecting outcomes

`register_event_split` reads only a current-code [microstructure registration](MICROSTRUCTURE_POLICY.md)
and writes a new checksum-protected manifest. It does not need or open capture/label files. Assignments
are based on the registered chronological session inventory, never returns, class balance, row counts
or random sampling:

- Require 2–32 research sessions. The first explicitly specified number belong to training;
  every remaining research session belongs to validation. Neither group may be empty.
- All reserved sessions remain reserved. Only their existing declaration metadata is used;
  this API does not expose or evaluate a test partition.
- Every session has one role, including its excluded, censored and not-entered observations.
  No session, unsuccessful run or inconvenient row is moved to improve class balance/results.

The manifest binds the registration, implementation/environment, label protocol and feature schema,
the ordered 30-column feature allowlist/units, per-session frame budget, embargo, minimum resolved
count/fraction and missingness policy. All configuration arguments are explicit; there is no
automatic search for a split that passes. The global frame budget is at most 10,000, computed as
`number_of_research_sessions * max_frames_per_session`, before source access.

For both train-to-validation and validation-to-reserved boundaries, require:

```text
earlier_group_last_session_end_ns + embargo_ns < later_group_first_session_start_ns
```

This deliberately conservative whole-source check rejects the manifest when a boundary is too close,
instead of silently deleting boundary observations or moving sessions. Equality fails. Nanoseconds
remain integers, with no millisecond truncation. During verification every row must also satisfy
`source_start <= feature_available_at <= known_at <= source_end` and
`known_at + embargo_ns < partition_cutoff`.

These are the existing split utility's chronological/exclusive/strict-cutoff invariants, applied to
fixed metadata boundaries rather than its automatic row-fraction algorithm. The older three-way
splitter expects monotonic outcome times; event barriers can mature out of feature order. This loader
checks each outcome independently and preserves feature order. It never sorts by future maturity or
reads reserved examples to construct a test range.

Create the manifest before inspecting label outcomes. Exclusive files and checksums detect accidental
mutation and identify configurations; they are not tamper-proof signatures or proof that an operator
has never seen the data. Changing settings requires a separately recorded experiment, not an edited
old manifest. A complete cross-experiment research registry is still future work.

## Verification against original source bytes

`load_verified_event_dataset` verifies one explicit research artifact, without selecting training
rows. `load_event_split` first validates the manifest and requires **every** registered research
source exactly once, in declared order, before any capture or label input is accessed. Unknown,
reserved, omitted, duplicated, reordered and mutable source lists fail closed.

For each source the loader:

1. Reads a bounded checksum envelope, rejecting duplicate JSON keys, non-finite JSON constants,
   malformed envelopes and quarantined `.partial` paths.
2. Checks source/registration identity and the exact declared processing budget.
3. Reads capture bytes once, verifies the registered hash/framing, and rebuilds causal features and
   labels through the shared deterministic builder using those pinned bytes.
4. Compares the **entire** rebuilt dataset to the artifact's canonical JSON. Recalculating a checksum
   after changing a feature, target, count, schema, row order or numeric type does not pass this check.
5. Checks source/partition availability bounds and verifies the current code/environment again
   before returning a fold or publishing a report.

This proves consistency with the current source/implementation, not independent correctness of the
labeling algorithm or statistical validity. Registrations/artifacts tied to earlier code fail closed;
do not patch their fingerprints to bypass provenance. No legacy CSV loader is changed.

## Quality failures are visible, not selected away

Each declared research source must be fully consumed, have no replay market-fault frames, and meet
both predeclared resolved-example count and fraction requirements. The fraction is:

```text
resolved / (resolved + censored + not_entered)
```

Excluded frames are reported separately, not used to inflate this denominator. Zero eligible
examples fail with an unknown fraction, even when the configured fraction threshold is zero.
Freshness/disconnect censoring remains visible in reason counts; a fault-free capture does not imply
all its outcomes are known. Counts do not imply independent samples or adequate market coverage.

A structurally valid incomplete/faulted artifact can still be verified for diagnostics. If **any**
source fails quality, the report retains every source's hashes, counts, fraction and failure reasons,
but both `train` and `validation` are `None`. There is no usable subset fallback. A corrupt artifact
aborts verification without publishing a success or quality report; it is not relabeled a bad sample.

If every source passes, immutable `EventPartition` objects contain only resolved observations:

- `X`: ordered feature-only tuples, with decimal strings converted to `Decimal`. Booleans/counts
  retain their types and `null` stays `None`. Unknown is not zero, false or a neutral target.
- `direction` and `net_return_fraction`: separate targets. All signs are retained, including losses.
- `source_sessions`, `example_ids`, `available_at_ns`, `known_at_ns`: separate provenance, not X.

There is no scaler, imputation, encoding fit, class balancing, training call or model output. Future
preprocessing must learn its statistics from training only and record its missingness contract.
`fold_available=true` means these declared engineering checks passed, not scientific sample
sufficiency, good predictive performance, permission to trade or model-promotion eligibility.

## Bounds, publication and commands

Combined capture-plus-label reads are capped at 64 MiB over the whole fold; each capture and each
label envelope also retain their 32 MiB caps. Actual bytes read are counted, not just file stat sizes.
Manifests and verification reports have a 1,000,000-byte cap. Outputs reuse exclusive fsynced partial
staging and atomic no-replacement publication. Existing outputs/partials are never overwritten.
Parent directories must exist; hard-link support is required. No resume overwrites an old report.

Safe help and synthetic tests from the project root:

```powershell
.venv\Scripts\python.exe -m ai_trader.training.event_training_data register --help
.venv\Scripts\python.exe -m ai_trader.training.event_training_data verify --help
.venv\Scripts\python.exe -m pytest -q tests/test_event_training_data.py tests/test_microstructure_data.py
```

Operator example only, not run on actual data during development. First create the manifest for an
existing current-code registration containing two research sources followed by reserved sources.
The numeric values illustrate the interface, not statistically approved sample criteria:

```powershell
.venv\Scripts\python.exe -m ai_trader.training.event_training_data register --registration data/processed/REGISTRATION.json --output data/processed/NEW_SPLIT.json --training-session-count 1 --max-frames-per-session 1000 --embargo-ns 0 --minimum-resolved-per-session 100 --minimum-resolved-fraction 0.5
```

Generate one label artifact per declared research source using the event-label builder with exactly
that `--max-frames` value; do not generate or supply reserved artifacts. Then verify all research
sources in registration order:

```powershell
.venv\Scripts\python.exe -m ai_trader.training.event_training_data verify --registration data/processed/REGISTRATION.json --manifest data/processed/NEW_SPLIT.json --source RESEARCH_ONE data/raw/ONE.jsonl data/processed/ONE_LABELS.json --source RESEARCH_TWO data/raw/TWO.jsonl data/processed/TWO_LABELS.json --report data/processed/NEW_FOLD_REPORT.json
```

`register` prints the manifest checksum. `verify` prints/publishes a compact report without model
matrices: exit 0 means a fold is available; exit 2 means verified source-quality gates blocked it.
Other errors fail the invocation. Every report retains `training_started=false`,
`promotion_allowed=false`, `live_trading_available=false` and `reserved_sources_opened=0`.

## Next step

The [bounded numerical baseline](EVENT_BASELINE.md) now implements a frozen preprocessing/evaluation
recipe, training-only scaling/missingness handling, trivial controls, checksummed data-only model
artifacts and validation metrics. This separate opt-in step does not change the loader's raw values.
Do not start fitting actual data until approved captures pass meaningful quality/sample gates; tiny
synthetic passing folds are not evidence of data readiness. Overlapping hypothetical outcomes are
not independent portfolio trades. Keep profit claims separate from prediction scores.

[Registered walk-forward event evaluation](EVENT_WALK_FORWARD.md) now uses a separate expanding-prefix
schedule without changing these fixed-split manifests. A [sealed model shadow adapter](EVENT_SHADOW.md)
now supports non-executing predictions on strictly later research sources.
Local Qwen integration/fine-tuning and supervised forward paper-runtime checks remain later gates.
No actual dataset, reserved capture, feed or trading account was opened during this implementation.
