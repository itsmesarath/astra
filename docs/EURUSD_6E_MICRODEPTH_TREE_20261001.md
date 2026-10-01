# EURUSD research with 6E depth and queue reload features

The completed experiment added causal depth and temporal features and trained one small nonlinear model on 65,920 resolved examples. The model selected no trades on either validation or test: every predicted return remained negative after costs. This is a verified research result, not a strategy ready for paper deployment. Qwen, model promotion and order routing remain disabled; the BTC collector is unchanged.

## Registered experiment

The protocol was frozen before reading the new evaluation outcomes. The intake metadata confirmed that the required source members were available. The configuration is `configs/databento_6e_microdepth_tree_v1.json`, with raw SHA256 `4e1bdedbc7dbeee654d54d87862ccfc162bdde893f7c4a050a06554e736ddb37`. Its Git attribute preserves LF line endings.

| Role | UTC decision sessions in 2025 | Exposure at registration |
| --- | --- | --- |
| Train | July 7 to 11 and July 14 to 18 | All previously examined; training only |
| Validation | July 21 and 22 | Not previously inspected for outcomes |
| Test | July 23 to 25 | Not previously inspected for outcomes |

Each complete source session has exactly one role. The replay reads 18 daily members, including three Sunday preparation members, and makes decisions only on the 15 registered weekdays from 12:00 inclusive to 16:00 exclusive UTC. It uses the same pinned intake and strict dated 6EU5 mapping, event-completeness, timestamp, book and compressed-member hash checks as the prior experiment. Any failing session aborts the whole cohort; there is no successful-subset fit.

## Causal features and targets

The original eight inputs remain: bid and ask queue sizes, queue imbalance, normalized order-flow imbalance and CVD, trade count, unknown-side trade fraction, and prior quote gap. Fifteen additional inputs describe visible depth and recent completed events:

- Five occupied price levels per side, using fewer if fewer exist: log depth sums, depth imbalance, top-level shares and price spans.
- Trailing five-second midpoint change, range, total absolute travel and completed-quote count. Change is relative to the oldest retained quote, not an interpolated price exactly five seconds earlier.
- Bid and ask queue reload: an increase at an unchanged best price matches previously unmatched decreases in FIFO order. Decreases must be no older than five seconds; price changes discard unmatched credits. Matched increases from the last five seconds are summed and divided by current total best depth. Consequently, a counted reload may refer to a depletion up to ten seconds before the current decision.
- Buy and sell absorption proxies: the corresponding positive or negative net CVD magnitude divided by total best depth and by one plus same-direction positive midpoint change.

These are observable proxies. A queue decrease may be a cancellation, not an execution; a subsequent increase is not proof of an iceberg. Net CVD can also conceal heavy two-sided trading. The feature names and report do not claim hidden-liquidity identification.

Depth is read only at a completed-event decision. Temporal history resets when the inherited OFI history resets after startup, book reset or more than five seconds of inactivity. No partial event, future price, outcome status, session ID or hindsight label enters the model. Features stored for an earlier decision never change when later events arrive.

The target and policy clocks are unchanged: decisions no more frequently than once per second, one-tick entry spread, 100 ms entry latency, up to one second to obtain an entry quote, a 15-second hold, and spread crossing plus one extra assumed cost tick. The first completed quote after the exit target supplies the exit, including late and widened quotes. No-entry and unresolved outcomes stay unknown, not fabricated no-trade labels. Inactivity flags remain visible. Training uses all resolved targets, so missing-outcome selection remains a limitation.

## Bounded model and policy

The model is a deterministic, two-output regression tree implemented with the existing NumPy dependency. It predicts long and short net ticks. Root thresholds are the 15 linear quantiles at multiples of one sixteenth, computed only from resolved training rows and reused at every node. Greedy splits reduce summed squared error across both targets; exact ties retain the first feature and threshold. Maximum depth is four. Every leaf requires at least 500 rows and at least three training sessions contributing 50 or more rows each. A leaf predicts its training target means.

There is one fit, no hyperparameter search, validation refit or threshold adjustment. A canonical model hash is fixed before evaluation and checked afterward. Model parameters are plain JSON, not an executable pickle. The controls are no trade and the training mean return using the same decision threshold.

The sequential policy selects the better predicted direction only when its net prediction is strictly above 0.5 ticks; ties abstain. It allows one position and a ten-second cooldown after an exit, rejected entry or entry expiry. Selection precedes reading the future outcome status. Positive evidence requires at least 100 closed test trades, at least 20 per day, positive net mean both pooled and on every test day, and no unresolved or inactivity-exposed selected test positions. Even a passing result cannot automatically promote the model.

## Results and decision

All 18 source members passed the registered checks, covering 24,177,619 target MBO records and the dated 6EU5 instrument ID 3624. The replay retained 220 observed inactivity intervals and accepted three narrowly permitted closed-period timestamp-clear records under the inherited protocol. Passing this protocol does not imply a gap-free feed.

| Partition | Decision rows | Causally eligible | Resolved targets | Model trades selected |
| --- | ---: | ---: | ---: | ---: |
| Train | 105,909 | 78,711 | 65,920 | Not used for promotion |
| Validation | 20,980 | 16,598 | 14,127 | 0 |
| Test | 32,212 | 25,365 | 21,715 | 0 |

The 159,101 decision rows include every ineligible or unavailable candidate. There were 18,912 no-entry outcomes across all partitions; their labels remain unknown. All entered candidates resolved before the decision window ended. The training target means were −2.113683 long and −2.121283 short net ticks. The fitted tree has 23 nodes and 12 supported leaves.

On both validation and test, the largest long prediction was −1.295620 net ticks and the largest short prediction was −1.654912. Neither approached the unchanged +0.5-tick entry threshold. The no-trade and training-mean controls also selected zero trades. Mean trade return is undefined because there were no policy trades; zero total closed profit is not a successful trading result.

| Evaluation metric in squared net ticks | Tree long | Mean control long | Tree short | Mean control short |
| --- | ---: | ---: | ---: | ---: |
| Validation mean squared error | 3.189041 | 3.198692 | 3.176560 | 3.184866 |
| Test mean squared error | 4.597464 | 4.598083 | 4.591768 | 4.591445 |

The tree made only small regression improvements over the mean control, and its short-side test error was slightly worse. It did not demonstrate actionable selectivity. In hindsight, 3,500 test candidates had a positive net long or short target, while 18,215 favored no trade. These overlapping opportunities are not an achievable oracle portfolio; their existence does not show that this model could identify them beforehand.

The decision is `not_ready_for_promotion`, with `insufficient_test_trades` and `no_positive_cost_adjusted_evidence`. No threshold was lowered and no second model was fitted after seeing evaluation outcomes. July 21–25 are now exposed dates, not fresh holdouts for another tuned experiment.

## Evidence and verification

The local ignored artifacts are `data/processed/databento_6e_microdepth_tree_v1_rows.jsonl` and `data/processed/databento_6e_microdepth_tree_v1_report.json`. The report contains the complete JSON tree, training thresholds, feature order, source/code fingerprints, quality metadata, partition metrics and unchanged deployment blocks.

| Evidence | SHA256 |
| --- | --- |
| Target and feature rows | `d8064ae8d320cecbdc220ac590f7c8099e8b836c0a75b70ce3dae6505876344a` |
| Research report | `72ded08fa3a1eb1b2b316343cd9b99d97c6dbd3d905a3982e89adaf013cecf90` |
| Canonical serialized model | `580493d454ccc5a819ca73b403c8df24474d07aa7340a09641715591a2304c03` |

A separate read-only audit verified the artifact and implementation hashes, session membership, decision spacing, target arithmetic, unknown-label handling and feature invariants. It checked that all 105,909 overlapping rows matched the prior baseline exactly after removing the additional feature columns. It independently reconstructed the training quantile thresholds, each tree node's row and session support and target means, and the evaluation predictions and errors without refitting. The existing sequential policy reproduced the saved zero-entry results.

The focused suite passed 120 tests. The final complete suite passed 3,079 tests with one optional native Nautilus dependency skip in 228.79 seconds. Ruff lint and formatting checks for changed Python files passed. An earlier suite overlapped source edits and correctly failed a registration fingerprint check; the complete passing run held source files fixed. Runtime was Python 3.12.10, NumPy 2.5.3, databento-dbn 0.70.0 and zstandard 0.25.0. Unrelated worktree changes were preserved.

## Running independently

From the project directory, use the existing virtual environment and downloaded archives:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.training.train_6e_microdepth_tree --config configs/databento_6e_microdepth_tree_v1.json --rows-output data/processed/microdepth_reproduction_rows.jsonl --report-output data/processed/microdepth_reproduction_report.json
```

Both output paths must be new. This command reproduces one fixed offline experiment; it does not download data, continuously retrain, modify Qwen or trade. Repeating it does not supply independent evidence. Licensed records and generated model/data artifacts stay local and are not committed to Git.

## Interpretation limits

These short-horizon candidates overlap and are not independent samples or an achievable hindsight portfolio. Five evaluation sessions cannot establish robustness across market regimes. The experiment uses futures quotes, not measured cTrader bid/ask prices, fills, commissions, latency or market impact. The additional one-tick cost is a research assumption. Broker-specific synchronized data remains necessary before relying on futures signals for spot/CFD execution.

## Next step

Do not turn this model into an order source or force trades by relaxing the gate. Prioritize synchronized cTrader EUR/USD quote collection and measured broker costs so that the execution target matches the intended market. A further signal experiment should register its event definitions and reserve new whole sessions before looking at their outcomes. True execution-linked replenishment patterns would need stronger evidence than the current visible-queue proxies. More model capacity or Qwen fine-tuning alone is not evidence of an edge.
