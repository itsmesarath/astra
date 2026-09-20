# Research Log

## 2025-01-01 through 2025-01-14 BTCUSDT Spot study

This is a validation-only linear-baseline experiment over 14 UTC source sessions containing 20,160
verified one-minute candles. January 13 and January 14 were reserved and were not used by model
fitting, model selection, or reported metrics.

Label assumptions:

- next-candle-open long entry;
- 10 bps taker fee and 2 bps slippage per side (24 bps estimated round trip);
- 20 bps net take profit, 40 bps net stop loss, and 5 bps time-exit neutral band;
- ambiguous same-candle profit/stop touches resolved as stop first.

Validation configuration:

- five initial training sessions and seven expanding validation folds;
- two final held-out sessions;
- linear classifier, maximum 150 epochs, patience 20, class-weight power 0.5;
- Spot-compatible policy: long/flat only, minimum direction probability 0.55, margin 0.10.

| Horizon | Validation rows | Balanced accuracy | Macro F1 | Long signals | Coverage | Long precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 minute | 9,653 | 0.5420 | 0.4068 | 12 | 0.12% | 8.33% |
| 5 minutes | 9,625 | 0.4923 | 0.4088 | 275 | 2.86% | 20.73% |
| 15 minutes | 9,555 | 0.4633 | 0.4079 | 692 | 7.24% | 26.30% |

Decision: reject all three candidates. The 15-minute target is the best of this comparison for Spot
long-signal coverage and precision, but its fold results are unstable and its precision is too low
for autonomous paper promotion. The unevaluated held-out sessions remain available for a frozen
candidate, but two days are not sufficient as a durable final test.

Next evidence should cover substantially more regimes, reserve a larger final block, and evaluate
net PnL, drawdown, and turnover in addition to label precision. These results must not be presented
as evidence of a profitable strategy.

## 2025-01-01 through 2025-03-01 BTCUSDT Spot study

This follow-up expanded the same 15-minute candidate to 60 UTC source sessions and 86,400 verified
one-minute candles. The first 20 sessions seeded training, the next 30 sessions were evaluated by
expanding walk-forward folds, and the final 10 sessions (February 20 through March 1) were excluded
from fitting, selection, and reported metrics.

The labeling, linear-model, and Spot decision thresholds remained consistent with the earlier
study. Economic simulation allocated 10% of current balance per trade, allowed one long position at
a time, and used the already cost-adjusted label return. Signals arriving during an open trade were
skipped. Drawdown is measured at closed-trade equity points because candle data cannot reconstruct
the exact intrabar equity path.

| Metric | Result |
| --- | ---: |
| Validation rows | 40,950 |
| Balanced accuracy | 0.4052 |
| Macro F1 | 0.3988 |
| Long signals | 764 |
| Non-overlapping trades | 370 |
| Winning / losing trades | 97 / 273 |
| Starting / ending balance | $10,000.00 / $9,168.75 |
| Net PnL | -$831.25 (-8.31%) |
| Maximum closed-trade drawdown | 8.33% |
| Turnover | 70.93x starting capital |
| Exposure | 3.17% |
| Profit factor | 0.179 |

Decision: reject the 15-minute candidate. Expanding the evidence made the economic failure clearer,
so the final 10 sessions must not be spent evaluating this rejected configuration. The next research
iteration should change the setup economics or feature hypothesis using training/validation evidence
and retain the final block for a genuinely frozen successor.

### Lower-turnover policy comparison

Three fixed policy variants were compared on the same 30 validation sessions. This is exploratory
model-selection evidence, not a new independent test. All variants used 10% position allocation;
the final 10 sessions remained excluded.

| Policy | Trades | Net PnL | Drawdown | Turnover |
| --- | ---: | ---: | ---: | ---: |
| Original probability 0.55 / margin 0.10 | 370 | -$831.25 (-8.31%) | 8.33% | 70.93x |
| Probability 0.65 / margin 0.15 | 209 | -$475.97 (-4.76%) | 4.78% | 40.80x |
| Stricter policy plus 30-minute re-entry delay | 32 | -$80.38 (-0.80%) | 0.82% | 6.38x |
| Delayed, maximum 3 trades/day, $10 session targets | 24 | -$48.58 (-0.49%) | 0.51% | 4.79x |

Decision: reject every filter variant. The controls successfully bound activity and loss, but they
do not convert the underlying negative expectancy into a profitable strategy. Further threshold
tuning on these same sessions would increase selection bias. The next candidate must change the
label/feature hypothesis, beginning with causal volatility-scaled barriers.

## 2026-09-19 independent methodology audit

The [strategy research reset](STRATEGY_RESEARCH_PLAN.md) supersedes the previous immediate next
step. No new historical strategy trial or final-block evaluation was run during this audit.

Corrections to interpreting the studies above:

- Each reported walk-forward session also selected its model's best epoch. These are exploratory,
  validation-selected results, not independent forward estimates. Rejected candidates remain
  rejected; no corrected profitability claim is available yet.
- Stop fills ignore adverse opening gaps. A synthetic fixture returned a 99.84 exit on a candle
  with a 99.10 high. Economic reports inherit this labeling limitation.
- Per-session dollar controls reset capital, whereas aggregate PnL compounds capital. Future
  trade PnL is recognized at selection time; the rejection-reason ledger is not causal.
- The February 20-March 1 block was excluded from fitting, selection and reported performance,
  but its labels were parsed and contributed to aggregate dataset counts. Earlier wording must
  not be read as a claim of zero access. January 13-14 was subsequently reused as training data
  and is no longer an independent holdout.

Implementation priority: nested chronological fit/tune/evaluate partitions, gap-aware execution
and continuous capital accounting, then a preregistered trend-pullback experiment. Qwen adaptation
remains conditional on trustworthy evaluation and a demonstrated improvement over simpler models.
This commit records the audit and plan only; the identified implementation issues remain open.

### Follow-up: separate fitting, checkpoint tuning and evaluation

The walk-forward evaluator now reserves a configurable past-only tuning block. Fitting expands
over older sessions; early stopping and best-epoch selection use only tuning sessions; the next
session supplies evaluation metrics. Schema 2 reports distinguish tuning from evaluation while
retaining legacy `validation` field names for evaluation metrics. The CLI minimum-training count
excludes tuning sessions, so 15 fit + 5 tune preserves a 20-session initial prefix.

Synthetic regressions check that changing evaluation labels cannot alter that fold's model or
predictions, and that later-session changes cannot alter earlier results. No historical dataset,
final-block performance or new strategy was evaluated. Offline/paper-only behavior is unchanged.

Next session: enforce chronological timestamps and label boundaries, exclude lockbox outcomes
before parsing, and finish provenance manifests. Then fix gap fills and continuous portfolio
accounting before any strategy comparison. Existing economic results remain unsuitable for
promotion; this checkpoint addresses selection leakage only.

## 2026-09-20 TradingAgents architecture review

Reviewed upstream commit `2d17df8da1536c121e4d7395ac5a5dcec9e96d6f`; see
[findings and adoption plan](TRADINGAGENTS_REVIEW.md). Local keyless model inference is supported
upstream, but its default data vendors are online. Its reflection is prompt memory, not model
training, and its recommendation backtest is not our cash-and-fills economic simulation.

Implemented a small independent offline research council with typed timestamped evidence,
bounded structured analyst/critic reports, provenance citations, input fingerprints and existing
hard-risk vetoes. The included cost-stress reviewer is deterministic, not an LLM. No broker
integration, live connection, credentials, cloud calls, model download or dependency additions.

Synthetic tests and a demonstration exercise the safety contract. No historical strategy trial,
held-out dataset evaluation, Qwen inference or performance improvement is claimed. Existing
timestamp/split and simulator repairs remain prerequisites for economic comparisons.

### Execution-mode foundation

Added explicit `paper`, `spot_testnet` and `spot_live` startup configuration and a common Spot
request/receipt interface. The working paper adapter wraps existing risk/fill/accounting code,
rejects short intentions and insufficient cash, serializes duplicate submissions, and preserves
kill-switch flattening. Receipt states accommodate future asynchronous exchange outcomes.

Testnet and live modes fail before any connection, credentials lookup or paper fallback. No live
adapter or real-money arming is implemented. Deduplication remains process-local and mode
namespaces are preparation for persistence, not durable ledgers. See [details](EXECUTION_MODES.md).
Local agents can consume online public Binance data; offline is not a bot-wide networking ban.
Paper outcomes can feed versioned training, but no profitability gate automatically enables live.

### Walk-forward timestamp boundaries and reserved-data loading

Schema 3 adds a metadata-first loader. Session names, row counts and first/last feature timestamps
are inventoried before choosing the research/held-out boundary. Only research rows reach feature,
target and economic-outcome conversion. A poisoned-holdout regression verifies that malformed
reserved features/labels do not reach the trainer, including through `run_walk_forward`.

Research outcomes must follow their features and end strictly before the next session's first
feature timestamp, including the first held-out session. `--embargo-ms` adds a configurable gap.
Crossing rows are rejected, not purged silently. Every outcome is checked, so an early entry with
a late exit cannot evade the boundary check; valid nonmonotonic exits are accepted. Entry timestamps
for economic rows must follow features and increase strictly. Feature times may tie within one
session but sessions must be strictly ordered and nonoverlapping.

Reports retain the input SHA-256, metadata inventory, configuration and boundary policy. Changes
between loading passes abort before fitting. Depth-label datasets containing future timestamps but
no entry/return columns are accepted again; those timestamps no longer imply incomplete economics.

Limitations: the combined CSV is still read/tokenized, held-out session metadata is inspected and
the raw file is hashed. This is value-conversion exclusion, not zero-byte access or a physically
sealed lockbox. Input timestamps are trusted provenance, not proof that upstream features were
causal. Historical holdout exposure remains recorded. No real historical dataset was loaded or
evaluated during this change; only synthetic fixtures were used. Next: gap fills and capital ledger.

## Gap-aware kline labels

Kline labeling version 2 checks each candle's opening price before its high/low. Opening at or
beyond a stop/target exits at that open and records the open timestamp, with distinct `gap_stop`
and `gap_target` counts. Unknown intrabar ordering remains conservative stop-first, timestamped
at bar close. A prior exit cannot be replaced by a later gap. This models idealized market-triggered
barriers and fixed-bps costs, not limit-order execution or guaranteed slippage. An adverse gap can
lose more than the configured stop amount.

The common CSV row schema remains 1 for splitter compatibility; `labeling_version=2` identifies
the changed semantics. The kline manifest is schema 2 and records fill/timing policies. Legacy
datasets are unchanged and must be regenerated into a new directory before using the new rules;
do not mix old and new labels in an experiment.

Verification: baseline 278 tests passed; completed suite 288 passed, with Ruff lint and format
checks passing. Regression coverage includes adverse/favorable gaps, exact barrier opens, opening
precedence when both levels later touch, unchanged intrabar fills, prior-exit precedence, and
generated-dataset session splitting. Only synthetic fixtures were used; no historical datasets,
held-out sessions, training runs, or live-order connectivity were touched. Next: a causal execution
ledger with continuous capital accounting.

## Continuous settlement accounting

Walk-forward report schema 4 carries balance and last-exit cooldown state across evaluation
sessions. Session trade counts and PnL limits reset against the carried starting balance. An
accepted outcome remains pending until its exit; subsequent signals cannot use its future PnL.
Settlement runs before later decisions, including flat rows, and the final pending trade settles
at its exit. Inclusive holding intervals still prohibit entry at the exact exit millisecond.

An in-memory `SettledTrade` ledger records entry/exit times, entry notional, net return, PnL and
before/after balances. Summaries use these settlements instead of recompounding an independent
capital path. Aggregation rejects reset capital/cooldown state and overlapping session intervals.
The observation interval uses the maximum outcome exit, including unselected rows, and aggregate
duration includes elapsed gaps between sessions. JSON summaries identify these accounting rules;
they do not embed individual ledger records.

Verification: 299 tests pass, Ruff lint/format and diff checks pass. Fixtures cover future-PnL
rejection invariance, final settlement, same-timestamp exits, carried capital under profit/loss
limits, reset counters, cooldown through flat sessions, nonmonotonic exits, invalid session chains,
ledger reconciliation and two-fold walk-forward continuity. No real historical dataset, reserved
block or research training run was used; model fitting occurred only in synthetic unit tests.

This closes the capital-path inconsistency, not the full execution milestone. Inputs are still
precomputed outcome labels; turnover remains twice entry notional and drawdown is closed-trade
only. Next: independent candle replay, candle-close marked equity, simulated buy/sell turnover and
entry-latency stress scenarios. Execution remains paper-only and live adapters remain disabled.

## Independent candle execution replay

Added a separate `backtesting.candle_replay` API accepting raw candle sessions and ordered
completed-close long-signal timestamps. It does not read precomputed outcomes or call their
calculator. Signals enter at the next open plus an optional full-bar delay. Entry sizing reserves
fees inside the cash budget and rounds base quantity down; cash and cooldown carry across sessions.
Each session resets only its entry count and realized-PnL gate reference. Open positions liquidate
at the final close, and signals whose scheduled entry falls outside the session expire.

Stop/target reference geometry matches labeling v2: opening hits first, then conservative
intrabar stop-first ordering. Replay independently charges per-fill quote fees and adverse price
slippage, so costed returns are not forced to equal additive-bps labels. Stop losses remain subject
to gap/slippage risk. Marks value open positions at each candle close without a hypothetical exit
fee reserve. Reports include both marked-close and closed-trade drawdown, actual simulated buy/sell
notional turnover, exposure, fills, trade PnL, signal decisions, session balances and configuration.
Input-content hashes cover candles and supplied signals; new JSON reports refuse overwrites.

Verification: clean baseline of 299 tests; completed suite 338 tests, Ruff lint/format and diff
checks passing. Synthetic fixtures verify independent calculation, zero-cost label-reference
parity, hand-calculated fees/slippage/turnover, cash conservation, adverse gaps, ambiguous touches,
unrealized drawdown, entry delays, session liquidation, risk resets, carried cooldowns, future-suffix
invariance, invalid inputs and report persistence. No historical data, held-out block, live
connectivity or research training was used.

Scope: research API only, not yet used by walk-forward reports or promotion gates. Supplied
signals must be generated causally; timestamp checks cannot prove that. Intrabar equity, queues,
volume-dependent execution and exchange-specific filters remain unmodeled. Next connect frozen
walk-forward predictions to explicit research candle sessions and compare next-open/delayed replay,
without opening reserved sessions or claiming profitability from these engineering tests.

## Frozen-prediction walk-forward replay integration

Schema-5 walk-forward reports now save immutable per-fold probability tuples and their feature
timestamps, captured once before scoring. An opt-in raw candle manifest and explicit holding-bar
configuration enable independent next-open and one-full-bar-delayed replay. Both scenarios use
identical frozen probabilities and the same long/flat decision policy, with no scenario winner
selection, refitting or promotion. Legacy label economics remain separate. Replay capital/risk
settings must match the walk-forward economic configuration.

The verified archive loader filters by exact evaluation session names before opening or hashing
archive files, rejects missing selections before archive loading, and checks selected files and
manifest hashes across reads. Other archive dates/names remain visible in the manifest. This does
not change the combined labeled CSV's metadata-only holdout conversion policy or its physical
tokenization limitations. All replay prediction times, even flat decisions, must align to unique
candle closes; extra/reordered sessions and holdout overlap fail closed.

Reports embed both replay ledgers/marks/configurations, prediction-policy hashes and candle/signal
input hashes. Frozen predictions can be replayed through a standalone API without fitting again.
Schema-5 report writing refuses overwrites, and the CLI checks an existing output before fitting.
Policy serialization rejects a policy different from the one actually used.

Verification: clean baseline 338 tests; completed suite 359 tests, Ruff lint/format and diff checks
passing. Synthetic tests cover single prediction calls per fold, two-scenario shared inputs,
saved-prediction replay equivalence, continuous balances, invalid alignment/scope, poisoned held-out
CSV values and unopened non-evaluation archives, changed source files and overwrite protection.
No real historical experiment, reserved-block evaluation, live connectivity or model promotion ran.

Next: bind feature-generation provenance to the exact raw candle inputs, then freeze the research
protocol/cost stresses before a registered research-only trial. Timestamps and separate data hashes
do not alone establish feature derivation lineage. Execution realism limitations remain unchanged.
