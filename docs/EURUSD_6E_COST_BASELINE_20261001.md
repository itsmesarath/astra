# EURUSD cost aware baseline training

Result on 2026-10-01: **the local CPU baseline trained successfully, but did not qualify for trading.** It fitted 31,959 two-sided cost-target examples and chose no trade on every eligible validation and test decision. This is a saved research model and working batch training pipeline, not a profitable strategy or a Qwen fine-tune. No paper/live orders were placed, no broker connection or credentials were added, and BTC collection was not changed.

## Data and session separation

The [frozen configuration](../configs/databento_6e_cost_baseline_v1.json) assigns whole dated 6EU5 sessions to exactly one partition. Previously exposed July 7–11, 2025 sessions are training only. July 14–15 are validation; July 16–18 are the single test. Model form, features, costs, thresholds and partitions were fixed before reading outcomes from the later dates. Validation did not select parameters, and the same frozen model evaluated test once. These dates are now exposed; rerunning them is not fresh validation.

The [target builder](../src/ai_trader/research/databento_6e_cost_targets.py) checked twelve local compressed UTC members spanning July 6–18, excluding Saturday, and decoded 16,023,970 target-contract records. It reused the strict order-book/event clock, verified dated mappings and member hashes at EOF, and retained reconstruction, timestamp and incomplete-event checks. Sources, code and configuration remained unchanged through the run. No new data was downloaded.

| Partition | Sessions | Event decisions | Causally eligible | Resolved two-sided targets |
| --- | --- | ---: | ---: | ---: |
| Train | July 7–11 | 51,642 | 38,560 | 31,959 |
| Validation | July 14–15 | 21,301 | 15,776 | 13,303 |
| Test | July 16–18 | 32,966 | 24,375 | 20,658 |
| Total | Ten sessions | 105,909 | 78,711 | 65,920 |

Decisions occur at most once per second, on a newly completed book event during 12:00–16:00 UTC. Eligibility uses only information known then: one-tick spread, five seconds of feature warmup following startup or an inactivity reset, and sufficient time before the window closes. It does **not** require the previous OFI rule to select an entry. Flat queues, zero OFI and disagreeing signals remain candidates. This avoids training only on that failed strategy's selected trades.

## Targets and causal features

Every eligible decision receives independent hypothetical long and short outcomes from the same future entry and exit quotes. Entry is the first qualifying completed quote after a 100 ms delay, with a one-second wait limit. Long enters at ask and exits at bid; short enters at bid and exits at ask. Exit is the first completed quote at or after a 15-second hold, retaining widened or late exits. Both targets subtract one additional tick as an assumed round-trip cost, not a measured cTrader charge.

The hindsight action is long or short only when that direction's observed net target is positive. It is no trade only when both observed targets are nonpositive. Missing or rejected entries and unresolved exits have **unknown targets**, never invented no-trade labels. The dataset retained 12,791 unavailable entry outcomes and 27,198 causally ineligible decisions. All entered target positions resolved in this run. Resolved late and inactivity-exposed outcomes were kept in the fit, not filtered to improve results; missing-outcome selection still limits what the regression estimates.

The eight input features are log bid depth, log ask depth, queue imbalance, five-second OFI divided by mean best-side depth, known-side CVD normalized the same way, log known-side trade count, unknown-side trade fraction and log time since the previous completed quote. Signed Trade flow becomes available only when its event completes; Fill messages do not duplicate that flow. A gap over five seconds resets feature warmup. An explicit feature allowlist excludes all future prices, labels, outcomes and session identifiers from model inputs.

The stored `outcome` object includes future entry/exit quotes for auditing. Its inherited gross-return and extra-cost diagnostic fields reference the long direction; the explicit `net_targets_long_short_ticks` pair is the regression target in the report's declared long/short order. Neither object is an inference input.

## Model and policy evaluation

The [trainer](../src/ai_trader/training/train_6e_cost_baseline.py) performs one float64, two-output ridge-regression solve. Feature means and population scales come exclusively from resolved training rows; standardized values are clipped to ±10. The regularization coefficient is one under the mean-squared-error convention, and the intercept is unpenalized. No optimizer search, epoch selection or validation-driven adjustment occurred. The model's serialized hash remained unchanged during both evaluations.

The policy chooses the larger predicted net return only when it exceeds 0.5 tick; ties and lower values mean no trade. Evaluation selects without consulting the future target status, then accounts for the observed result, including entry failures. It permits one position at a time and a ten-second cooldown after exit, entry expiry or rejection. Overlapping labeling candidates are therefore not summed as a simultaneous trading portfolio.

| Evaluation measurement | Validation | Test |
| --- | ---: | ---: |
| Eligible decisions | 15,776 | 24,375 |
| Model-selected entries | 0 | 0 |
| Best predicted long net return | −1.950 ticks | −1.957 ticks |
| Best predicted short net return | −1.936 ticks | −1.962 ticks |
| Long target mean squared error | 3.9142 | 7.9008 |
| Constant training-mean long error | 3.9247 | 7.9063 |
| Short target mean squared error | 3.9073 | 7.8928 |
| Constant training-mean short error | 3.9181 | 7.8997 |

The learned predictions were slightly more accurate than constant training means by this error metric, but remained negative everywhere. The always-no-trade and training-mean controls also selected nothing. Zero realized quote P&L from zero trades is not demonstrated profitability, and a mean trade return is undefined, not zero. The model failed the frozen minimum-trade and positive-cost-adjusted-evidence requirements, so promotion remains disabled.

This result does not mean profitable moves were absent. In hindsight, 3,268 of the 20,658 resolved test candidates had a positive long or short net target; the other 17,390 favored no trade. Those candidates overlap and are not an achievable oracle portfolio. This feature set and linear model did not identify them prospectively. The roughly −2.12 tick mean training targets show why ignoring spread and cost would give a misleading training objective.

## Saved model and verification

Local ignored artifacts are `data/processed/databento_6e_cost_baseline_v1_rows.jsonl` and `data/processed/databento_6e_cost_baseline_v1_report.json`. The report contains the plain JSON model weights, bias, training-only preprocessing, runtime versions, partition metrics, policy selections and source/code pins. No pickle or executable checkpoint is required. Licensed raw records and the local research artifacts were not committed to Git.

| Evidence | SHA256 |
| --- | --- |
| Frozen configuration | `331b7faa85ed5d976453c12371cb0850e8c361e85b13d5eba6b69be14a2c1ede` |
| Target rows | `1f615c1da8226535794d84f13e84482562c39cc4d617651e7b2d91fd433d055e` |
| Research report | `2613e87bd6cb5cfd15e0d949b8c6063bbba617b4491d7237aff70bc79a97c34f` |
| Canonical serialized model | `8dbb619393a56062d9c7f5ab4d085483f34d8a609878cad26c6a3c9bcabe19f2` |

An independent read-only audit verified row and model hashes, disjoint session membership, all target-price arithmetic, unknown-label handling, latency/window boundaries and decision-rate limits. It recomputed train-only scaling and checked the ridge normal equations using the saved parameters without fitting a second model. It independently reproduced prediction errors and the zero-entry evaluation decisions. Runtime was Python 3.12.10, NumPy 2.5.3, databento-dbn 0.70.0 and zstandard 0.25.0.

All 127 related tests passed. Final full-suite verification was 3,060 passed and one skipped in 187.31 seconds; the skip is the optional native Nautilus evaluation dependency. Ruff lint and formatting for changed Python files passed. Unrelated worktree changes were preserved.

## Running the batch without ChatGPT

From the project directory, the existing virtual environment and pinned local archives are sufficient:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.training.train_6e_cost_baseline --config configs/databento_6e_cost_baseline_v1.json --rows-output data/processed/cost_baseline_reproduction_rows.jsonl --report-output data/processed/cost_baseline_reproduction_report.json
```

Both output paths must be new. This reproduces a single fixed experiment and refuses overwrites; it does not continuously retrain, download live data or execute trades. Repeating it does not create independent evidence. Qwen weights were neither loaded nor updated.

## Next research gate

Keep this baseline as a cost-aware reference, not a trading strategy. The next proposed experiment should add a small, explicitly causal set of temporal depth, replenishment and absorption features and compare a suitably bounded nonlinear model against these controls on newly reserved whole sessions. Freeze that protocol before inspecting its new outcomes. Do not lower the threshold merely to force this model to trade or repeatedly optimize the now-exposed test dates.

Before eventual cTrader EUR/USD paper execution, synchronized broker quotes and broker-specific cost/latency evidence are still required. CME 6E prices do not demonstrate executable spot/CFD fills. More training or a larger language model alone cannot establish a trading edge.

The proposed feature expansion and bounded nonlinear experiment is now complete. See [the depth and queue reload tree audit](EURUSD_6E_MICRODEPTH_TREE_20261001.md) for the fresh session split, training results and unchanged deployment block.
