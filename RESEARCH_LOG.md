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
