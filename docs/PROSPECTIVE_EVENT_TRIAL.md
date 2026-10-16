# First prospective event-label experiment

This research step connects the completed acquisition plan to the existing causal event-label
and NumPy baseline interfaces. No network, credentials, model downloads, Qwen fitting or orders
are part of it. The reserved raw capture is not an input to the research workflow.

## Verified metadata handoff

`research.prospective_trial` reads only the caller-pinned original plan and the fixed locations
of its copied plan, receipt and audit. Each file is bounded to 64 KiB. It verifies the entire
expected audit transcript, original assignments, receipt pin, timestamps, duration, gap, counts,
distinct source hashes and absence of known partial/failure markers. Missing, duplicate,
reordered, relabeled or replaced slots fail. Self-consistent hash changes do not bypass these
structural checks. There is no raw capture hashing, book reconstruction or outcome inspection
during this preparation.

The original capture implementation fingerprint is historical evidence. It remains unchanged;
the new research registration independently binds the current research implementation/runtime.
This is not resuming an old trial under different code or rewriting its fingerprint. Subsequent
label building and fold verification still enforce the existing current-code guard and reproduce
research artifacts from the pinned original research bytes. Local hashes do not authenticate
independent custody or prove that no local user previously read the data.

All policy, feature, cost, fold and baseline settings are validated before output. Preparation
claims a new directory and writes intent, registration, split and recipe, followed by a prepared
receipt with raw artifact pins. Failures retain partial preparation and never create a success
marker or silently resume. The source inventory and training-session count come from acquisition,
not from caller-specified alternatives. The exported raw paths contain research sources only.
Existing low-level label CLIs still require those exact declared research paths; this is not an
OS access-control boundary or a new generic artifact execution service.

## Frozen first recipe

Configuration: `configs/prospective_event_trial_v1.json`, raw SHA256
`2e7e72ade98388aa4f928f2166bb8dc9328baa7c5b3b88febaae659dae12fdc7`.
These settings were chosen before research outcomes were opened; no parameter search is authorized
by preparation. The fee and slippage numbers are **explicit research assumptions**, not a verified
Binance account fee tier, liquidity estimate or recommendation.

| Component | Fixed setting |
| --- | --- |
| Source assignment | Original first session train; second validation; third stays reserved |
| Features | Top 5 levels, 10-second rolling CVD/flow window, 10-bps liquidity band |
| Evidence | 1-second maximum evidence interval, 80% retained-depth proxy, 3 repeated intervals |
| Freshness | 2-second event lag, 100-ms future skew, 500-ms quote age/gap, 2-second trade age |
| Counterfactual labels | Spot unit-long; next healthy depth quote after the feature, 1-second entry TTL |
| Exit | 20-bps stop, 40-bps target, 10-second hold from entry, whichever resolves first |
| Costs | 10-bps taker fee and 2-bps slippage per side, plus observed bid/ask spread |
| Processing | 2,500 frames per research session, 5,000 aggregate cap |
| Fold gates | At least 50 resolved examples and 50% resolved fraction per session; full fault-free replay |
| Split embargo | Strict five-second whole-source gap and outcome cutoff |
| NumPy recipe | 100 fixed full-batch epochs, learning rate 0.05, L2 0.01, zero initialization |
| Baseline gate | Both source gates and at least two training classes before any fitting |

The strategy policy is the abstain control; its unrelated proposal/risk fields do not select label
examples. The label builder samples **all eligible depth observations**, retaining excluded,
not-entered and censored rows. It is not a portfolio backtest. Outcomes overlap, and hundreds of
rows from one minute are not hundreds of independent trades or enough regime coverage.

Preparation grants no training authority. A later explicit bounded NumPy invocation may attempt
the frozen recipe once, after source reproduction and gates. It must report failed quality or
one-class data without changing costs, horizons, labels or split. It never fine-tunes Qwen or
promotes a trading policy. Qwen's separate protected-case/custody requirement remains unchanged.

## Current run

The original three-session campaign is pinned by the metadata in
[the acquisition report](PROSPECTIVE_CAPTURE_PLAN.md). Preparation completed on 2026-09-24 at
`1790284791337740400` ns, before either research source was labeled. The original acquisition
plan, receipt, audit and settings hashes remained unchanged through the run.

Verification: **2,244 Python tests passed, one optional Nautilus skip** (99.07 seconds), all
**38 JavaScript tests passed**, and Ruff lint/format passed. This includes 52 new synthetic tests
covering metadata-only preparation, original-role preservation, self-consistent but invalid
receipts, audit mutations, source aliasing, incomplete publications, recipe budgets, drift and
no raw/reserved opens or fitting during preparation.

Labeled both research sources and reproduced both artifacts through the existing fold verifier.
Both sessions were fully consumed with zero replay market-fault frames. The result is an honest
**failed fold-quality gate**, not a successful training run:

| Measure | Train | Validation |
| --- | --- | --- |
| Replay frames | 1,599 | 924 |
| Eligible counterfactual examples | 474 | 414 |
| Resolved outcomes | 151 | 247 |
| Censored outcomes | 323 | 167 |
| Excluded frames | 1,125 | 510 |
| Resolved / eligible | 31.8565% | 59.6618% |
| Minimum-count gate (50) | Pass | Pass |
| Resolved-fraction gate (50%) | **Fail** | Pass |

One explicit attempt at the frozen 100-epoch NumPy recipe returned `blocked_source_quality`.
It performed **zero fitting**: model, fit and validation results are null, `training_started`
is false, and neither training nor validation partition was released. The result file is an
expected gate-refusal report, not a test failure or an adapter. The reserved source was never
opened; there were no Qwen calls, optimizations, orders, downloads or new public-feed calls.
No settings, costs, source roles or thresholds were adjusted after seeing these outcomes.

## What caused the censoring?

Read-only diagnosis reconstructed only the two declared research sources under the frozen
registration. These are observed application-receipt facts, not a root-cause attribution:

- Training: three stale-quote instants censored 21, 100 and 101 pending examples (222 total).
  At those instants, a trade-only frame preceded the next received depth observation and the
  previous quote was 682.0311, 571.7663 and 1,039.2908 ms old, exceeding the fixed 500-ms limit.
  Another 101 examples were censored at session end.
- There were four training observation gaps above 500 ms: 580.3005, 682.0311, 571.7663 and
  1,039.2908 ms. The first was during warmup and had no pending eligible label to censor.
- Validation: one 533.6426-ms observation gap censored 87 pending examples. The incoming
  depth refreshed its quote age to zero, but the existing interquote-gap guard correctly retained
  uncertainty across the gap. Another 80 examples were censored at session end.
- Across every listed observation gap, adjacent depth exchange-event timestamps were only
  **100 ms apart**. Receipt batching/stalls are therefore visible, but these files cannot separate
  network, WebSocket buffering, application scheduling, clock behavior or other local causes.
  These are not measured one-way network latencies. Many records have equal receipt timestamps;
  no synthetic timestamp interpolation or retrospective reordering was performed.

The recorder's two-second event-freshness check and the labeler's 500-ms quote-continuity rule
serve different purposes. Passing transport integrity never promised label eligibility. Overlapping
10-second counterfactuals amplify one brief interruption into many censored labels; these counts
must not be represented as hundreds of independent failures or trades. No profitability or model
class-diversity conclusion was needed or made after the fold failed.

## Local artifacts

Directory: `data/processed/btcusdt_prospective_events_20260924_1/` (Git-ignored).
Historical acquisition implementation remains
`8ef2fa4acb3ea7666c00582de86fec9259e6e9e0d7498baef0abb60eea924afb`.
New research implementation, unchanged after labeling and the refusal report:
`1911d4139f455a5b64ae0e6c57e91c26393ca486be3ca937f5f09f3701e14b92`.

| Artifact | Raw SHA256 |
| --- | --- |
| `prepared.json` | `8e94d57e22633995cf35b3f5f8f1b864bc4d4c80894d00d8ba4b2e64ee802978` |
| `registration.json` | `24335c9842bfa66622e2104e915e5e6686343f615fbf240fa5730f5d8ee23c7a` |
| `split.json` | `3f3a762291859abaa08f39e8a5e5395aba1f214c9ae1d3b4d96c506dba2a45ce` |
| `recipe.json` | `4ce43a74299df47e2ab43d6571c010e3822c0d8a79843c84516618195324fa41` |
| `train_events.json` | `b3da2d889839a6ed1e6164b798b1eaccedab0eb0b35b09af0b010ce681be74a6` |
| `validation_events.json` | `921a08be9ac210bf7739264a88a0539d35a783f3fe99af125c5cf9fa58305f74` |
| `fold_report.json` | `b370ef9b4cc824766f0688539fe66b9985decf223e163f52857dc738102336ab` |
| `baseline_result.json` | `5ca1a50c2f2a71238cb96930b9b931256aa40d305cd038cb990711f55c1b53cb` |

Raw file hashes above differ from canonical payload digests inside checksum envelopes. The
baseline's canonical result digest is
`00a0ef43f17d20013b09fa7f34dc03cc7517455c6ad7b91d7933477719cdb0aa`.
Do not resume or edit these manifests after future source changes; prepare a separately recorded
experiment and preserve this failed-quality result. The research sessions are now inspected and
must never be relabeled protected evaluation.

## Next

Implemented [bounded capture timing diagnostics](CAPTURE_TIMING.md): QPC receipt timing,
event-loop lag, queue/batch and parse/write counters, with startup waiting separated. One new
60-second diagnostic run did not reproduce the >500-ms gaps; the earlier cause is not established
and this failed-quality fold remains unchanged. Next plan longer instrumented,
separate acquisition sessions with unchanged label/quality assumptions and adequate frame limits.
Do not simply loosen 500-ms freshness, lower the 50% fraction, shorten the horizon or search until
a run passes. Longer sessions can reduce end-of-session censoring but do not repair receipt stalls.
Keep the original reserved raw session out of this investigation. Numerical fitting and Qwen
fine-tuning remain pending separate data/evaluation gates; paper-only execution remains unchanged.

The [instrumented follow-up](INSTRUMENTED_CAMPAIGN.md) now supports this next acquisition step,
with prospectively pinned research telemetry and unchanged quality rules. Its results are a
separate experiment; this first fold's failed result and original artifacts remain untouched.
