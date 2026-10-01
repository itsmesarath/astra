# Training probabilities of short term 6E opportunities

One offline classifier has been trained to distinguish a positive-net short opportunity, neither direction clearing costs, and a positive-net long opportunity. Its probability scores improved over the training class prior on all three development days. Directional identification remains weak, and these dates were already exposed by earlier experiments. This is a development model, not a profitable strategy or an independent test result. No Qwen weights, platform connections, trading controls or BTC collection were changed.

The purpose is to learn whether the existing order-book and flow features distinguish favorable from unfavorable short-term outcomes. This differs from the previous model's task of estimating mean net return. A probability of a positive outcome does not include the size of wins or losses and must not be interpreted as expected profit or an order instruction. The previous cost-model rejection remains intact.

## Data and session separation

The input is the existing pinned microdepth dataset described in [the depth feature experiment](EURUSD_6E_MICRODEPTH_TREE_20261001.md), not a new download or NinjaTrader capture. It contains 159,101 rows from dated 6EU5 futures observations. The new run selected only 105,909 rows from July 7 to 18, 2025. The other 53,192 rows from July 21 to 25 were excluded from this run's fitting and evaluation. No unused archive dates were opened.

| Role | Whole UTC sessions in 2025 | All decision rows | Resolved labels |
| --- | --- | ---: | ---: |
| Training | July 7 to 11 and July 14 to 15 | 72,943 | 45,262 |
| Development | July 16 to 18 | 32,966 | 20,658 |

These are chronological, disjoint whole-session partitions. All ten dates had already been studied, including the three development dates. Calling them development dates is intentional: a different split does not make old data an independent holdout. No row from the development partition influences feature normalization, class priors or fitting in this run.

Targets retain the existing 100 ms entry latency, one-second entry-quote allowance, 15-second hold, spread crossing and one additional assumed cost tick. A direction's label is positive only when its net target is strictly greater than zero. If neither direction clears costs, the class is neither. These are hindsight research targets, not realized fills; the model receives only causal input features.

The training labels comprise 2,621 short-positive, 40,185 neither-positive and 2,456 long-positive examples. The development labels comprise 1,614, 17,390 and 1,654 respectively. Ineligible decisions and missing entry outcomes remain in the accounting but do not become artificial neither-positive labels. Training excluded 18,607 ineligible decisions and 9,074 missing-entry outcomes; development excluded 8,591 and 3,717. There were 617 resolved training examples and 149 resolved development examples exposed to recorded inactivity. These remain counted, so the experiment does not certify uninterrupted data or eliminate missing-outcome selection bias.

## Fixed learning procedure

The model is a deterministic NumPy multinomial logistic classifier with the 23 existing features: best queues, order-flow imbalance, CVD, trade activity, quote gap, visible depth, recent price behavior, queue reload and absorption proxies. The reload and absorption features remain proxies, not confirmed icebergs or hidden liquidity. No additional feature was selected after inspecting this run's scores.

Training uses only training-column means and standard deviations, clips standardized values to plus or minus ten, initializes weights to zero and biases to the log of the Laplace-smoothed training class prior, and runs 200 full-batch gradient steps. The learning rate is 0.05, and the weight L2 coefficient is 0.01; biases are not penalized. There is no oversampling, class reweighting, early stopping, parameter search, development refit or automatic promotion. Model parameters are plain JSON, not executable serialized objects.

The protocol and implementation hashes were saved before opening the input rows for fitting. The reader enforces bounded intake, exact source sessions, the pinned full-file digest and target arithmetic. The model hash is fixed before development scoring. Code, registration and input hashes are checked again before publishing the report, and existing output paths cannot be overwritten.

## Results and limitations

Lower log loss and Brier score indicate better probability estimates. Both compare all three classes, not a simulated trading portfolio.

| Development session | Classifier log loss | Prior log loss | Classifier Brier score | Prior Brier score |
| --- | ---: | ---: | ---: | ---: |
| July 16 | 0.664330 | 0.777775 | 0.360687 | 0.415563 |
| July 17 | 0.471246 | 0.482824 | 0.232436 | 0.237884 |
| July 18 | 0.414323 | 0.414988 | 0.196446 | 0.197194 |
| Pooled | 0.515086 | 0.556027 | 0.262149 | 0.282038 |

The registered criterion of lower scores on every development day was met. Most of the improvement came from July 16; improvement on July 18 was very small. This is a descriptive result on dependent, overlapping observations, not a significance claim or evidence across market regimes.

Raw classification accuracy was 84.28%, compared with 84.18% for always predicting the majority class. That headline is not evidence of a useful trading model: most examples belong to neither-positive. Balanced accuracy was only 34.88%.

The model's largest-probability class was short-positive on 96 examples and long-positive on 122 examples. Of those predictions, 31 and 51 matched their respective targets: precision was 32.29% for short and 41.80% for long, while recall was only 1.92% and 3.08%. These are overlapping classification examples, not orders or an achievable trade count. Of the 218 directional classifications, 209 occurred on July 16. There is no execution policy or profitable backtest attached to this classifier.

The report also retains ten fixed calibration bins for the probability that either direction clears costs. Those estimates are not uniformly calibrated; some middle bins underpredict opportunity frequency and the highest bins overpredict it. No calibration or decision threshold was fitted on these development outcomes afterward.

The decision remains `development_only_not_ready_for_promotion`. Required next evidence includes a separately registered independent cohort, stronger directional and payoff estimates, and synchronized cTrader broker observations with measured execution costs. Futures quotes alone cannot establish EURUSD spot or CFD profitability. The [NinjaTrader and cTrader capture foundation](NINJATRADER_CTRADER_CAPTURE.md) is available, but feed entitlement, platform smoke tests and cross-provider clock alignment still need verification.

## Reproduce locally without ChatGPT

Use the existing project virtual environment and local dataset. Choose new output names; these commands perform one fixed offline fit and do not download, continuously retrain, load Qwen or trade.

```powershell
.\.venv\Scripts\python.exe -m ai_trader.training.train_6e_opportunity prepare --output logs/6e_opportunity_local_registration.json
.\.venv\Scripts\python.exe -m ai_trader.training.train_6e_opportunity train --registration logs/6e_opportunity_local_registration.json --output data/processed/6e_opportunity_local_report.json
```

Preparation records the current fixed protocol and code without opening market data. Training refuses a changed registration or source dataset. The report contains the reusable classifier coefficients, feature order, class definitions, split, quality accounting, calibration tables and per-session metrics. Repeating the same fit is reproducibility, not additional learning evidence. A changed experiment requires a new protocol and appropriate evaluation design.

## Evidence and verification

The completed local artifacts are `logs/6e_opportunity_development_20261001_1_registration.json` and `data/processed/6e_opportunity_development_20261001_1_report.json`. Licensed input rows and generated model artifacts remain local and are not committed.

| Evidence | SHA256 |
| --- | --- |
| Input rows | `d8064ae8d320cecbdc220ac590f7c8099e8b836c0a75b70ce3dae6505876344a` |
| Input report | `72ded08fa3a1eb1b2b316343cd9b99d97c6dbd3d905a3982e89adaf013cecf90` |
| Protocol | `d7dd8a7ac79ce7f7d5103ec0aca7ff588e925ffb1b4509b0f4b5a00e05880dc1` |
| Registration file | `580faf9810f5578cca043f3be86e65552cb8169fbd8260a48b7b12d0f13cb0eb` |
| Completed report | `465be3e1146086016aa82d8ab9d4b91046aaf803b25b0769a2cd354fff3b53ac` |
| Canonical model | `a8435c4a4924fc6c8192adb41da67f963c067a162132197968056226ff85dbed` |

A separate read-only calculation verified source and model hashes, session counts, target arithmetic and timing, training-only means, scales and priors, and reproduced all pooled and daily predictions, confusion matrices, log losses and Brier scores without fitting again. The focused suite passed 94 tests, including 42 new tests for this trainer. The complete suite passed 3,165 tests with one optional native Nautilus dependency skip in 214.17 seconds. Ruff and changed-file formatting checks passed. Unrelated worktree changes were preserved.
