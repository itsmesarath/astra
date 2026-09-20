# Strategy research reset

Audit date: 2026-09-19. Code reviewed: `3f22d8f`.

Status: research plan, not an implemented strategy or a promotion decision. The existing linear
model has been trained, but no tested configuration has demonstrated an economic edge. Qwen
fine-tuning is not the next bottleneck. Keep execution offline and paper-only; this work adds no
account access, credentials, or live-order capability.

Implementation update (2026-09-19): schema-2 walk-forward reports now use disjoint fitting,
past-only tuning, and next-session evaluation. Regression tests cover checkpoint/prediction
invariance under changed evaluation labels and changed later-session data. This closes the direct
checkpoint-selection leak in finding 1, not every task in step 1 below. Strict timestamp/label
boundary enforcement, pre-parse lockbox exclusion and reproducibility manifests remain pending.
No new historical strategy trial was run. The other audit findings still apply.

Implementation update (2026-09-20): schema-3 walk-forward reports now inventory sessions before
loading model data, exclude reserved features/outcomes from conversion, enforce chronological
feature timestamps and strict research outcome/embargo boundaries, and record source SHA-256
plus session metadata. Dataset changes between passes are rejected. Nonmonotonic outcome times
are supported. This narrows finding 7 for new runs but cannot undo prior holdout exposure.
Combined-CSV tokenization still reads reserved cells as strings; this is not physical file-level
isolation. Separate sealed files, complete code/environment manifests and simulator repairs remain
pending. No historical dataset or final-block evaluation was run in this update.

## Findings that change the next milestone

1. **Checkpoint selection and reported evaluation share the same session.** In
   `src/ai_trader/training/walk_forward.py`, `run_walk_forward` passes the evaluation session to
   `fit_linear_baseline`. In `training/train_linear.py`, that session's macro F1 selects the best
   epoch and controls early stopping. Policy and economic results then use that checkpoint on the
   same session. These are validation-selected exploratory results, not independent forward tests.
   Session-exclusive splitting alone does not prevent this selection leakage.
2. **Stop fills can be impossible.** In `features/kline_dataset.py`,
   `calculate_triple_barrier_outcome` fills a touched stop at its barrier without first checking
   the candle open. A synthetic entry at 100, followed by a quiet candle and then an open of 99,
   high of 99.10, and low of 98.90, produces an exit at 99.84. That price never traded in the exit
   candle. Reproduced during this audit without reading historical test data.
3. **The current payoff is demanding.** Defaults subtract 24 bps round-trip costs. A net target
   of +20 bps needs a +44 bps price move; a net stop of -40 bps is only a -16 bps price move.
   Barrier-only breakeven is 40 / (20 + 40) = 66.7% wins. Time exits and execution differences
   change that calculation, so label precision is not a substitute for measured expectancy.
4. **Softmax scores are not verified win probabilities.** Training uses class-weighted loss;
   neither a 0.55 nor a 0.65 score has been calibrated to that success frequency. Kline classes
   describe net long-trade outcomes, not simply price direction. A positive price move can still
   receive a negative net-return label. Names and reports must distinguish these concepts.
5. **Portfolio controls and aggregation use different capital paths.**
   `backtesting/economic_metrics.py` resets selection capital per session, while aggregate returns
   compound across sessions. Consequently dollar-denominated session gates need not match the
   aggregate portfolio. Future exit PnL is also booked during entry selection, before overlap is
   checked on subsequent signals. In the current one-position design this can change rejection
   reasons without changing accepted trades, but it is not a causal event ledger.
6. **Reported risk has limited resolution.** Drawdown uses closed trades, not marked positions;
   turnover estimates twice entry notional; observation duration uses the last row's exit rather
   than the maximum exit. Earlier entries can exit later than later entries. These limitations
   require tests and explicit metric definitions before promotion.
7. **Holdout provenance needs more precise language.** The final February 20-March 1 block was
   excluded from fitting, checkpoint selection, and reported performance, but the loader parses
   its labels and the dataset builder includes all sessions in aggregate label counts. It is
   not a sealed, never-inspected lockbox. The old January 13-14 holdout was incorporated into
   training in the expanded study and is retired as an independent test.

The prior losses remain a reason to reject those candidates, not evidence that correcting the
evaluation will make them profitable. Passing unit tests establishes tested behavior, not alpha.

## Implementation sequence and acceptance tests

### 1. Separate fitting, tuning, evaluation, and the final lockbox

Implement this before another historical strategy comparison.

- Within each expanding fold, use older complete sessions for fitting, a later disjoint block for
  early stopping/calibration/threshold selection, and the next session for evaluation only.
  For the existing 20-session prefix, a starting protocol is 15 fit sessions, 5 tuning sessions,
  then evaluate day 21. Advance one day, retaining the most recent 5 past sessions for tuning.
- Fit scaling and class weights only on the fitting block. Freeze the checkpoint, preprocessing,
  calibration and policy before reading evaluation outcomes. Past evaluation sessions may enter
  later folds only after their outcomes would have become available.
- Declare boundaries in a manifest before loading features or labels. Research commands must
  exclude lockbox files before parsing outcomes, not merely omit them from an aggregate report.
- Purge labels whose outcome intervals reach the next partition; make any embargo explicit.
  Features may use only information available at decision time. Preserve session-exclusive
  ownership within each fold and chronological ordering.
- Record code/data hashes, seed, feature schema, all partition names, chosen epoch and complete
  policy/cost configuration. Identify old report schemas as exploratory.
- Tests: evaluation-target permutations must not change the checkpoint or predictions for that
  fold; changing future sessions must not change earlier decisions; disjointness and crossing
  labels are checked; excluded lockbox labels must never reach a parser/trainer.

Keep February 20-March 1 unopened for now and record its historical exposure. After the protocol
and candidate are frozen, reserve a fresh, not-yet-inspected chronological block for confirmation.
Do not repeatedly inspect a final block after each rejected candidate.

### 2. Make execution and capital accounting causal

- Separate outcome labels from an independently replayed paper execution ledger. Use identical
  declared order semantics and compare both implementations on hand-calculated fixtures.
- Process known bar-open gaps before ambiguous high/low touches. A stop-market simulation must
  allow worse fills after an adverse gap. If ordering remains unknown, use conservative handling
  and record that ambiguity. Specify target order type; candle touch alone is not proof of fill.
- State signal availability and entry latency explicitly. Compare the idealized next open with
  a one-full-bar delayed entry as a stress scenario; neither is a guarantee of executable prices.
- Carry capital across sessions. Reset only session counters and the session-start equity
  reference. Settle exits before applying subsequent PnL-dependent limits. Do not spend future
  proceeds or classify open-position rejections using a future loss.
- Add candle-close marked equity alongside closed-trade drawdown, actual simulated buy/sell
  turnover, and correctly bounded observation/exposure intervals. Intrabar drawdown stays unknown.
- Tests: adverse gaps, both barriers touched, exits at boundaries, delayed fills, daily reset,
  continuous capital, limits reached at settlement, nonmonotonic exit times, and ledger totals.

### 3. Test an economic hypothesis before adding a larger model

First candidate: **long-only trend pullback**, evaluated on 5-minute completed candles with a
maximum 2-hour holding period. This is an unproven hypothesis, chosen to examine larger price
moves relative to transaction costs, not a claim that slower trading is profitable.

Freeze this initial specification before looking at its returns:

- Calculate EMA20, EMA60 and ATR14 using completed 5-minute bars. Seed EMAs with their first
  period's simple average and ATR with its first 14 true ranges, then use Wilder smoothing.
  Warm up for at least 60 bars; use a fixed gap policy and only past data.
- Trend filter: EMA20 > EMA60 and EMA60 > its value six bars earlier.
- Trigger: previous close <= previous EMA20, and current close > current EMA20. Emit one event
  per crossing, not one sample for every minute in a trend.
- Freeze ATR at the signal. At the declared next-bar entry, use a gross-price stop distance of
  1 ATR and target distance of 2 ATR, with a 24-bar maximum holding period. Unlike the old net
  barriers, these price levels do not move when a cost sensitivity scenario changes.
- Require the 2-ATR gross target distance to be at least three times the baseline round-trip
  cost estimate. This is a screening rule, not evidence of favorable expected return.
- Stay long/flat, hold at most one position, allocate at most 10% of available capital and use
  no leverage. Skip entries lacking a full within-session outcome window. Define session-end
  handling before replay; never silently carry labels across partitions.
- Use the existing 24 bps round-trip assumption as a reference, with 36 and 48 bps stresses.
  These are hypothetical scenarios, not verified account fees or measured slippage. No assumed
  maker discount or guaranteed maker fill.

Cross-session *past-only* indicator warmup may be useful for this slower hypothesis. If added,
document it separately from label ownership, prohibit future bars, and test prefix invariance.
Never backfill a missing value with future information.

Compare against cash, a declared buy-and-hold allocation, and seeded random entries matched on
session, trade count and approximate holding-time/exposure, all under the same cost assumptions.
Record unmatched random-control sessions rather than silently changing constraints. Run the
rule alone first; then test whether a small model improves the same event set out of sample.

Do not launch a parameter grid. A trend breakout or range mean-reversion rule is a separate,
later registered hypothesis, not a rescue variant selected after inspecting a bad result.

### 4. Evidence gate and model progression

- Maintain an append-only experiment ledger including failures, policy changes, and trial count.
  Report net expectancy, daily returns, drawdown, exposure, turnover and cost sensitivity.
- Quantify uncertainty with session/block resampling that retains trade dependence; report block
  choices and sensitivity. Sixty days and a handful of trades cannot establish durable behavior.
  A confidence interval from a selected experiment alone does not correct multiple testing.
- Before running confirmation, freeze numerical drawdown, minimum-event and minimum-session
  requirements in the run manifest. Treat insufficient evidence as inconclusive, not a pass.
- A paper-promotion candidate should beat cash after reference costs, have a positive lower
  confidence bound for net expectancy under the registered procedure, meet its risk budget,
  and remain economically credible under worse costs and across separate time blocks. Report
  all baseline comparisons; do not substitute raw buy-and-hold return for risk/exposure matching.
- First train a small event-level baseline to estimate net return or calibrated profitable-trade
  probability. Evaluate calibration on past-only tuning data and confirm it on evaluation data.
  A model must improve the rule-only baseline rather than merely fit retrospective winners.
- Only then consider Qwen3-4B-Base adaptation: serialize causal event features into a fixed input
  schema, label with all outcomes including losses/no-trade examples, and evaluate any adapter on
  the identical chronological protocol. Hardware feasibility and resource budgeting are a
  separate prerequisite; this audit does not establish them.
- Continuously collect data, but retrain in versioned batches. Keep the paper champion fixed
  until a challenger passes the gate; never let training automatically replace risk controls.

We can train experimental models now. We should postpone Qwen fine-tuning and autonomous promotion
until trustworthy evaluation and sufficient event-level evidence exist. More model capacity cannot
by itself establish tradable information in these inputs.

## Research reference

Implementation update: kline labeling version 2 now handles opening stop/target gaps before
intrabar touches. These are idealized market-triggered exits with fixed-bps costs, not guaranteed
exchange fills. Existing historical datasets remain unchanged. Schema-4 walk-forward economics
now settle label-based PnL at exit, carry capital/cooldowns across sessions, reset session counters
and PnL references, and summarize the same settlements instead of a second capital path. Observation
duration now uses the maximum exit and includes inter-session gaps. This addresses finding 5 and
the interval part of finding 6. A separate candle-replay API now independently executes reference
barriers with per-fill fees/adverse slippage, marked-close equity, simulated buy/sell turnover and
full-bar entry delays. Synthetic fixtures verify zero-cost label parity and hand-calculated costed
fills; labels' additive-bps PnL is not assumed equal to actual fill accounting. Session-end forced
liquidation and caller-supplied causal signals are explicit assumptions. Schema-5 walk-forward
reports now freeze probabilities/timestamps and optionally replay identical signals at next open
and one bar later. Raw archive loading is restricted to evaluation sessions, before file access;
no scenario winner is selected. Schema 6 additionally recomputes evaluation features before fitting
from causal in-session windows and requires exact agreement under current generator rounding.
Reports bind the verification to feature/candle content hashes and the calculation-module hash.
This establishes evaluation-input numeric consistency, not original-generation authenticity.
Fit/tuning features and outcome-label provenance, exchange/volume realism and remaining provenance
gates above are still pending. Integration tests are synthetic, not alpha evidence.

Bailey, Borwein, Lopez de Prado and Zhu, [The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf),
explain why repeated strategy selection on the same history creates false discoveries. This
motivates recording trials and using fresh confirmation; it does not validate our proposed rule
or imply that we have implemented their PBO estimator.
