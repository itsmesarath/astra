# 6E activity and direction: first complete development training experiment

## Result

The manifest and all four CPU fits completed. The models were evaluated on all
894,261 original one-second decision rows from the 84 later development
sessions. **Every fitted model selected zero trades at the frozen cost-aware
threshold**, matching the no-trade control. This comparison supplies no trading
edge, win rate or profitable teacher policy. Nothing was promoted; Qwen remains
unchanged. The abstention is a valid experiment result, not a runtime failure.

Training read 26,187 causal cases from 112 sessions: 21,446 resolved targets
and 4,741 unavailable outcomes (1,399 entry timeouts and 3,342 widened-spread
refusals). All cases contributed causal activity features to the cutoff;
unavailable targets did not become zeros, losses or no-trade targets.
The cutoff was `5.652489180268651`. It admitted 7,862 training cases; the main
model fitted the 6,466 resolved gated cases from 111 sessions. Each other
model fitted all 21,446 resolved training cases.

| Later development period | Sessions | All decision rows | Resolved targets | Selected by each model |
| --- | ---: | ---: | ---: | ---: |
| September 2025 | 20 | 214,263 | 130,477 | 0 |
| October 2025 | 23 | 259,074 | 185,742 | 0 |
| November 2025 | 19 | 200,061 | 142,260 | 0 |
| December 2025 | 22 | 220,863 | 139,444 | 0 |

There were 693,875 causally eligible decisions, so the result is not simply an
empty eligible dataset. All policies skipped those decisions through the fixed
prediction/abstention rule; 200,386 other decisions were ineligible. Among the
eligible decisions, 95,952 had unavailable targets. The report's aggregate
`unknown` count is 296,338: unavailable eligible targets **plus** ineligible
decisions. Neither category is a losing-trade label. With no selected attempts,
closed net ticks are zero and mean return/win rate are undefined. Recosting the
same empty selections at two/four extra ticks cannot prove cost robustness.

Independent post-run verification checked every daily report and model hash,
reproduced the training cutoff, gated support and fitted feature means without
another fit, reconciled each role/month summary, and rehashed all consumed
shards (1,833,062,704 bytes). No raw archive or reserved outcome was opened.

## Scope and permission

This step creates a purpose-specific training manifest over the immutable
[historical census and resource correction](EURUSD_CENSUS_GAP_DIAGNOSIS_20261002.md).
It does not change their `training_eligible=False` reports. The new permission
is limited to four fixed local CPU ridge fits and their development comparison.
It does not authorize Qwen fine-tuning, model promotion, paper/live trading,
broker connectivity, a download, or access to reserved outcomes.

All 471 inventory dates remain accounted for: 196 decision sessions, two
observed empty decision windows, 40 Sunday reconstruction-only dates, three
vendor-degraded dates and 230 reserved dates. The accepted decision corpus
contains 2,136,770 one-second rows and 45,816 causally spaced cases. The April 4
resource correction is included once; its April 3 control is not double-counted.
The decision scope is still 12:00–16:00 UTC, not all trading hours.

| Whole source-session role | UTC date rule | Complete decision sessions |
| --- | --- | ---: |
| Training | Before 2025-09-01 | 112 |
| Development validation | 2025-09-01 through 2025-10-31 | 43 |
| Development test | 2025-11-01 through 2025-12-31 | 41 |

Every source session belongs to exactly one role. Cases and full decision rows
inherit that role; there is no random row split. All 2025 sessions have already
been inspected, including in the census review. These later roles test temporal
generalization within exposed development data, **not untouched holdout
performance**. The 2026 reserved roles remain metadata-only.

## Frozen experiment

The existing cost model, causal feature definitions, entry rules and target
arithmetic are reused without changes. The activity cutoff is the linear 70th
percentile of `log_quote_events_5s` over all causal training cases, including
cases whose outcome is unavailable. No validation/test features fit the cutoff.

| Model/control | Inputs | Fitting cases |
| --- | --- | --- |
| Activity-gated microstructure | 23 base and 14 execution-proxy features | Resolved training cases passing the activity gate |
| Ungated microstructure | Same 37 features | All resolved training cases |
| CVD-only | Signed normalized five-second CVD | All resolved training cases |
| Queue-only | Best-level queue imbalance | All resolved training cases |
| No-trade | None | No fit; fixed abstention |

Each fitted model predicts long and short crossed-quote net ticks, with its own
train-only scaler, clipping at ten standardized units and ridge penalty one.
The fixed policy abstains unless the better predicted net return exceeds 0.5
ticks; direction ties abstain. The main model also abstains below the activity
cutoff. There is no parameter search, winner selection, later-session refit or
automatic retry.

Fitting uses the existing 60-second-spaced causal cases. Evaluation uses every
one-second decision row on all 84 later sessions, including ineligible and
unavailable outcomes. It retains the original 100 ms entry delay, 15-second
holding target, quote-timeout/spread checks, one-position rule and cooldown.
Outcome fields update simulated position state only after selection; they are
never model inputs or entry-availability filters. Unknown outcomes are not
turned into losses or no-trade labels.

Reported closed-quote totals include crossed spread and one extra tick. The
same selected closed attempts are also recosted at two and four extra ticks.
These are sensitivity checks, not new policies. Futures quote outcomes are not
cTrader EUR/USD fills or measured broker costs. Closed totals alone do not give
portfolio P&L or a complete return for attempts with unknown outcomes.

## Reproducibility and failure behavior

The manifest verifies the original census, refusal diagnostic and resource
correction pins. It checks source-session lineage, complete coverage and causal
case accounting. Dataset reads are bounded JSONL reads with count/hash checks,
exact feature allowlists, dated contract identity and target validation.
Reserved dates are refused before constructing a dataset path.

Training is bounded to 50,000 causal cases and twenty minutes, with at least
1,000 resolved cases, 512 resolved gated cases and twenty gated sessions.
All consumed training-case and later decision-row hashes are checked again
before completion, as are the unchanged model bundle, every daily report,
registration and implementation. A partial run retains failure evidence but
cannot publish a successful-subset completion or approved model. Existing
outputs are never overwritten.

The three commands are:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.training.historical_6e_manifest `
  --output data/processed/NEW_manifest.json

.\.venv\Scripts\python.exe -m ai_trader.training.train_6e_activity_direction `
  --prepare --manifest data/processed/NEW_manifest.json `
  --manifest-sha256 MANIFEST_RAW_SHA256 --registration logs/NEW_registration.json

.\.venv\Scripts\python.exe -m ai_trader.training.train_6e_activity_direction `
  --registration logs/NEW_registration.json `
  --registration-sha256 REGISTRATION_RAW_SHA256 `
  --output data/processed/NEW_experiment
```

These illustrate the CLI, not permission to rerun the fixed experiment or change
thresholds after reading the results. Unique output paths retain each attempt.
The research artifacts stay local under ignored `data/` and `logs/`; only source,
tests and this report are committed. BTC collection is untouched.

## Completed local artifact pins

- Manifest: `data/processed/6e_training_manifest_20261002_1.json`; raw SHA256 `ba773292535c97402826e6b40b34d367379a2db899f0010d474628220f965c2b`.
- Registration: `logs/6e_activity_direction_20261002_1_registration.json`; raw SHA256 `1d4f65fa92a57200aa70cc7f9a094a320b00a19bb78cb196cab7352cd1b643b4`.
- Completion: `data/processed/6e_activity_direction_20261002_1/completion.json`; raw SHA256 `8046988ac301aa0eb3e3d157e7c51405b12b892c0582bf2611b6806d23d1a261`.
- Model bundle: `data/processed/6e_activity_direction_20261002_1/models.json`; raw SHA256 `1673da848483d275f451a0d6ccb7e0c99c2299dd07436f15dfd643e8bcbd0213`, canonical content SHA256 `dd296305e3eee05d01a7142256573768820430b978ed8c53a9a713c298a201a4`.

The completion retains all 84 daily report hashes and explicit implementation
hashes, along with the frozen protocol. It is not a deployable-model approval.

## Next decision

No model is automatically promoted. A weak or abstaining baseline is a research
result, not a reason to lower costs or force more trades. The next separately
specified experiment should examine causal sequence/context features and the
very sparse same-ID replenishment proxies, while keeping these session roles,
unknown outcomes and cost-aware abstention. A candidate and its evaluation
protocol must be frozen before any reserved outcome is opened. Qwen teacher
labels and autonomous paper deployment require evidence beyond this exposed
development comparison.

## Validation

The starting complete suite passed 3,444 tests with one optional Nautilus skip.
This step adds 45 tests for session roles and lineage, corrected-date accounting,
reserved-data isolation, bounded/hash-checked reads, later failure evidence,
train-only thresholds/scalers, exact feature allowlists, four frozen fits,
future-outcome independence, unknown-only evaluation, cost sensitivity,
changed inputs/parameters, complete-date evaluation and partial-job refusal.

The final full suite passed **3,489 tests, one optional Nautilus skip**, in
271.42 seconds. Repository Ruff checks and formatting checks passed. Package
source was unchanged throughout the full regression run and the actual
registered experiment. The observed abstention did not trigger a threshold
change, new fit or automatic retry.
