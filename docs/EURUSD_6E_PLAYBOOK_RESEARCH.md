# EUR/USD futures signal playbooks and validation plan

Status, 2026-10-01: **research hypotheses only; no strategy has qualified for paper or live trading.** The project intends to trade EUR/USD spot or CFD through a future cTrader broker, using CME 6E order flow as a supplementary signal. The first fixed-contract 6E model did not beat simple validation controls. This note translates established traders' ideas into tests; their examples are not evidence of a profitable 6E or CFD strategy.

## Why the current model needs a different question

The [first registered experiment](../configs/databento_6e_first_training_20261001.json) predicts every one-minute, one-tick midprice move from eight book and recent-flow features. On 717 validation rows, model accuracy was 43.93% versus 48.95% for the training-majority control; log loss was 0.9671 versus 0.9522 for the training prior. It predicted none of the 71 neutral outcomes. The three test sessions were already evaluated, so they are **exposed** for future design. These results neither prove that order flow lacks signal nor justify training Qwen on the current labels. A selective setup with `no_trade` is a different, still untested objective.

## Playbook ideas from original sources

### Range context and competing breaks

[Jim Dalton](https://jimdaltontrading.com/top-ten-resolutions-traders/) distinguishes an open inside versus outside the previous pit-session range and warns against fading trend days. [SMB Capital's range-break guide](https://www.smbtraining.com/blog/wp-content/uploads/2024/03/Technical-Analysis-Range-Break-Trading-Cheat-Sheet.pdf) describes initial breaks, break-and-retest, and failed breaks back into an established range. Dalton's pit-session framework and SMB's stock examples do not directly define a Globex FX trading day or 6E stop distance.

**Our hypothesis:** Fix the exchange-time boundary of a completed CME trading-day interval in advance, then register two competing families at its known range edge: an **accepted break** that sustains trading outside the boundary, and a **failed break** that re-enters. Compare whether prior signed flow, book imbalance and replenishment distinguish them before entry. Never use the current day's eventual high, low or close to classify its earlier state. Refute the idea if a level-only or no-flow control performs as well on later sessions, or if confirmation arrives too late to cover costs.

### Absorption with price confirmation

[Axia Futures' Euro example](https://axiafutures.com/blog/volume-delta-reversal-trade-strategy/) shows aggressive selling absorbed without further price decline before an upward range break; Axia calls for price and order-flow confirmation beyond delta alone. [Jigsaw Trading's reversal lesson](https://www.jigsawtrading.com/blog/elements-of-a-reversal/) separates absorption, waning aggression and opposing aggressive flow, while emphasizing location and additional evidence. These are discretionary examples, not measured 6E edge.

**Our hypothesis:** At a known low, measure aggressive sells, displayed-bid replenishment and small downward displacement as separate causal features, then require a later upward trigger. Compare against CVD alone and comparable attacks without replenishment. Refute it if the combination adds no out-of-sample value, or the apparent advantage vanishes after confirmation latency and costs. Do not collapse these features into an opaque “iceberg” flag.

### Trend pullback as a separate candidate

[Jigsaw's pullback lesson](https://www.jigsawtrading.com/blog/how-to-learn-order-flow-the-right-way/) describes lower-energy countertrend pulls and renewed trend-side activity. **Our hypothesis:** Compare an already-observed impulse with the later counterleg's volume and displacement, then test a renewed-flow trigger, separately from range reversals. Refute it if defining the state requires future knowledge or adds no value beyond a simple trend control.

The trader sources motivate **where and when to ask** for a signal. They do not establish which rule works in this data. In particular, do not label every stalled move a stop run, every refill an iceberg, or every imbalance a trade.

## Data features to test before complex setups

The first feature ablation should compare lagged, depth-normalized order-flow imbalance, top-of-book queue imbalance, signed trade flow and selected deeper levels against the existing features. [Cont, Kukanov and Stoikov](https://arxiv.org/abs/1011.6402) report a strong **contemporaneous** OFI and price-change relation; that alone does not establish a 6E forecast. [Gould and Bonart](https://arxiv.org/abs/1512.03492) report next-midmove information in queue imbalance for Nasdaq stocks, with market-dependent strength. These papers support testing, not transferring their effect sizes to FX futures.

Build each feature only from exchange events complete **before** the decision. Per [Databento's GLBX normalization](https://databento.com/docs/venues-and-datasets), evaluate a book snapshot after `F_LAST`; count a Trade once rather than counting its associated Fill again, and exclude or separately report unknown aggressor side in signed volume. Displayed MBO depth is not all implied liquidity. Use the term **replenishment proxy** until native iceberg identification is independently validated; [CME's MBO explanation](https://www.cmegroup.com/articles/faqs/market-by-order-mbo.html) distinguishes native and synthetic iceberg behavior. Reset/clear, crossed-book, stale-book, missing-session and contract-roll states must produce `no_trade`, not fabricated features.

## Registered evaluation before another fit

1. Preserve the original 14-session run and its exposed March–April 2025 test. Version the builder instead of changing its frozen recipe. The next intake must verify the 18-month archive's individual files, reconstruct complete CME trading-day intervals, use a predeclared exchange calendar and select dated outright contracts without looking at same-day outcomes. Holidays, maintenance, time zones, daily snapshots and rolls need explicit treatment; the existing single-contract, 21-weekday builder does not cover them.
2. Before reading new outcomes, record which later whole sessions are for development, validation and untouched final test, along with source hashes, candidate families, price levels, feature windows, horizons, threshold grid, stopping rules and a limit on comparisons. No source session may cross a partition. Any revision after seeing validation is a new version; do not use the final test to choose rules.
3. Test simple causal features first. Then compare the two opposing range-break rules and, separately, the pullback candidate. Include price-level-only, CVD-only, existing model and `no_trade` controls. Log every eligible setup, rejected setup and trigger time so selective accuracy cannot hide low coverage or future leakage.
4. Evaluate at several pre-registered horizons with conditional precision, coverage, trade count, calibration, per-session results and session-block uncertainty. Count overlapping labels as dependent. A higher hit rate alone is not a promotion gate. Do not claim an executable edge until timestamp-aligned cTrader broker bid/ask quotes allow spread, commission, latency, slippage and financing to be modeled, followed by independent paper execution.
5. Keep live orders disabled. Train Qwen only after a numerical policy has passed fresh session-separated validation and there is a stable, non-leaking setup/decision target. A language model cannot turn an unvalidated label into a trading edge.

**Next implementation task:** build a versioned, read-only 6E multi-session replay and event registry that emits prior-known range levels, `F_LAST`-safe order-flow features, data-quality vetoes and a `no_trade` state. Freeze the new chronological split and test specification before fitting or inspecting its reserved outcomes. This document registers research direction, **not** numeric thresholds, an executable strategy or permission to trade.
