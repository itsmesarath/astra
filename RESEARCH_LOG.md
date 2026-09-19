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
