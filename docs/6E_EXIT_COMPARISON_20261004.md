# 6E exit comparison 20261004

## Decision

The cost-aware exit experiment completed and passed independent result verification on October 4, 2026. Fixed brackets did not establish a profitable strategy. Keep all eleven rules and these new hindsight targets research-only. Do not promote the rules or train Qwen to imitate their entries as profitable decisions.

On the matched latency-aware time-exit comparator, failed auction closed 16 outcomes for -47 ticks; its bracket closed the same 16 for -40 ticks. Accepted breakout closed eight for -23 ticks with the time exit and -19 with the bracket. These small pooled reductions in loss are not an edge: failed auction worsened from -6 to -9 ticks on validation development, while accepted breakout stayed at -6. Neither main rule generated a test-development entry.

Every active declared policy had negative pooled closed returns with both exit plans. Idle and the two snapshot policies made no trades; their zero returns are abstention, not profitable performance. Unknown entered exits remain unresolved and can block a policy for the rest of a session, so closed-return totals are not complete account PnL.

No training, model call, download, network request, credential access, paper/live order, reserved outcome access, shutdown or BTC collector change occurred. Existing pilot and crossing modules, thresholds and evidence remain unchanged.

## What changed

Two new research modules, `six_e_bracket_targets.py` and `six_e_bracket_study.py`, add quote-based exit counterfactuals and a frozen whole-cohort verifier. This is not a modification of the production execution engine.

- Entry is the original first completed quote at or after decision plus 100 ms, within a one-second wait. A first widened spread refuses entry; the engine does not search for a better later quote. Both directions and both plans share that quote.
- The time exit requests liquidation 15 seconds after entry. The bracket requests it at the first observed net liquidation value reaching +3 or -3 ticks strictly before that deadline; otherwise it uses the timer. Exact deadline ties favor timeout. Native equal-time event order is preserved.
- Both plans exit at the first completed quote at or after the request plus 100 ms, within a one-second wait. A trigger is not a fill. Exit spread widening, adverse overshoot and favorable recovery are retained; no exact stop/target-price fill is invented.
- Net values cross entry and exit bid/ask and subtract one assumed extra round-trip tick. The trigger levels include that cost, not merely distance from the midpoint. An unchanged one-tick-spread quote starts at -2 net ticks; only one further adverse price tick reaches the -3 stop. This deliberately fixed bracket is not an optimized risk setting.
- Eligibility retains all original causal gates and adds an 18-second buffer before 16:00 UTC for both delays and waits. Six previously eligible decisions become ineligible. No future outcome is used to select an entry.
- Each policy and plan has one pending entry/position and ten seconds of cooldown after a close or entry refusal. An entered position without an observed exit blocks further entries for the rest of its session, rather than being treated as flat.
- Base triggers and selections are also recosted with two/four extra ticks without changing the paths or thresholds. These are sensitivity checks, not separately optimized policies.

The previous 15-second reference did not add this exit latency or one-second exit cutoff. Its old -45/-22 main-rule totals remain unchanged and must not be substituted for the new -47/-23 comparator when attributing an exit difference. Strict unknown-position handling also changes selection populations for some controls.

## Frozen coverage

Registration was completed before this native replay. The experiment preserves exactly the previous twelve calendar-selected sessions, their rows, all 33 auction fields and crossing evidence packets. The first pilot's feature-only calibration from 26,187 early-train cases across 112 training sessions was reused without fitting or threshold search.

| Dates | Dated contract | Existing role | Decision rows |
| --- | --- | --- | ---: |
| April 7, 8, 9 and July 7, 8, 9, 2025 | 6EM5 and 6EU5 | Train | 69,157 |
| October 6, 7, 8, 2025 | 6EZ5 | Validation development | 33,246 |
| December 8, 9, 10, 2025 | 6EH6 | Test development | 27,003 |
| Total | Four dated contracts | Exposed development | 129,406 |

This is 48 decision hours at 12:00–16:00 UTC, 6.056% of the 2,136,770 accepted decision rows, not a new exit analysis of all 196 accepted sessions. Selected whole daily DBN members were consumed to hash-verified EOF. The stored active-window native sequence has 7,394,312 completed quotes; earlier warmup observations are not in those packed columns. The fixed research roll does not guarantee the most liquid contract, especially for December's 6EH6.

All 2025 outcomes here were already exposed development data. Existing validation/test role names do not make them independent holdouts. The 230 reserved inventory dates remain metadata-only. This remains a retrospective fold-calibrated study, not a simulation of online learning on early training dates.

There are 86,658 eligible decisions: 70,105 shared entries, 11,101 widened-entry refusals and 5,452 entry-quote timeouts. Another 42,748 decisions are ineligible. Entry/refusal prices match the original engine exactly wherever the new known window buffer allows entry.

## Two sided hindsight states

Each eligible shared entry receives long and short counterfactuals under both plans. A joint state requires both directional exits to resolve. Missing entry or either missing exit is unknown, never a zero-profit trade or a no-positive label. A both-positive state is supported because bracket exits can occur at different times; it is not forced into one hindsight winner.

| State across all decisions | Time exit | Bracket exit |
| --- | ---: | ---: |
| Long only positive | 4,577 | 2,852 |
| Short only positive | 4,550 | 2,748 |
| Both positive | 0 | 0 |
| Neither direction positive | 54,925 | 58,936 |
| Unknown | 65,354 | 64,870 |
| Total | 129,406 | 129,406 |

Among the bracket's 64,536 fully resolved joint cases, 91.32% have neither direction positive under this exact execution/cost/exit definition. This is descriptive, not an achievable model accuracy or proof that all trading opportunities are absent. These one-second cases overlap; they are not independent trades or a realizable hindsight portfolio. Unknown counts include ineligible/refused cases plus 5,569 entered bracket cases and 6,053 entered time-exit cases lacking at least one directional exit.

The files explicitly keep `training_allowed` false. Future supervised targets would need a separately registered training-only conversion, leakage-safe session splits, support and uncertainty analysis, and independent evaluation. They must not become inputs at decision time.

## Policy comparison

All eleven frozen feature-only entry policies were evaluated separately. Closed returns below deduct the base extra tick; unavailable exits are separately retained, not included as zeros. A shorter exit changes subsequent eligibility through position/cooldown state, so different closed populations must not be read as matched causal gains.

| Policy | Signals | Time selected / closed | Time net ticks | Bracket selected / closed | Bracket net ticks |
| --- | ---: | ---: | ---: | ---: | ---: |
| Event failed auction | 41 | 22 / 16 | -47 | 22 / 16 | -40 |
| Event accepted breakout | 11 | 8 / 8 | -23 | 8 / 8 | -19 |
| Price-only failed auction | 217 | 99 / 73 | -164 | 113 / 88 | -188 |
| Price-only accepted breakout | 12 | 8 / 6 | -9 | 8 / 6 | -14 |
| Failed-auction queue control | 41 | 22 / 16 | -21 | 22 / 16 | -32 |
| Accepted-breakout queue control | 9 | 7 / 7 | -9 | 7 / 7 | -11 |
| Crossing follow | 212 | 85 / 58 | -122 | 89 / 64 | -137 |
| Burst follow | 1,964 | 651 / 481 | -1,196 | 1,006 / 738 | -1,669 |
| Snapshot failed auction | 0 | 0 / 0 | 0 | 0 / 0 | 0 |
| Snapshot accepted breakout | 0 | 0 / 0 | 0 | 0 / 0 | 0 |
| Idle | 0 | 0 / 0 | 0 | 0 / 0 | 0 |

Failed auction's bracket mean is -2.5000 ticks versus -2.9375 for the time exit. It has one positive close, 15 stop requests, one timeout, four widened exit spreads and one close worse than the -3 stop. Six attempts are widened-entry refusals. Accepted breakout's bracket mean is -2.3750 versus -2.8750; it has zero positive closes, six stop requests, two timeouts and four widened exit spreads. Neither main rule reaches a target trigger in this experiment.

Their bracket holdings average 3.149 and 5.434 seconds respectively, rather than approximately 15.2 seconds. Shorter holdings have not produced positive expectancy. At two/four extra cost ticks, failed-auction bracket totals are -56/-88 and accepted-breakout totals -27/-43. Every active policy remains negative under those recosts.

| Existing role | Failed auction time / bracket ticks | Accepted breakout time / bracket ticks |
| --- | ---: | ---: |
| Train | -41 / -31 | -17 / -13 |
| Validation development | -6 / -9 | -6 / -6 |
| Test development | 0 / 0 | 0 / 0 |

There are three closed validation-development outcomes per main rule, insufficient to establish an edge. December provides no main-rule entry; zero results do not prove generalization. The entry rules still generate only 41 and 11 signals over 48 hours, not the requested frequent-scalping objective or a low-latency HFT strategy.

## Matched entry diagnostics

Both exits were additionally evaluated at every entry selected by the time-exit schedule. All statuses and unmatched outcomes are retained. A return difference is reported only where both exit quotes resolve; this diagnostic does not permit selecting favorable pairs or promoting a winner.

Failed auction has 22 common attempts, 16 both-resolved pairs and six entry refusals, with a +7-tick bracket-minus-time sum. Accepted breakout has eight common attempts, all eight resolved, with a +4-tick sum. The failed-auction difference is +10 on train but -3 on validation development; the accepted-breakout difference is +4 on train and zero on validation development.

For burst follow, 651 common attempts include 479 both-resolved pairs and 172 unavailable/refused pairs; its +93-tick matched difference is not the difference between the separately scheduled portfolio totals. Five entered time exits versus three entered bracket exits are unresolved in their respective burst schedules, and therefore block later selections in those sessions. Price-only failed auction has three/two such unresolved exits and crossing follow two/zero. These are not assumed closed at session end and their unobserved liabilities are not inferred.

## Evidence and verification

Project root: `C:/Users/pabta/Projects/ai-trader`. Registration: `logs/6e_bracket_exit_20261004_1_registration.json`. Output: `data/processed/6e_bracket_exit_20261004_1`. Twelve packed native quote files total 177,463,488 bytes; twelve target sidecars total 244,121,280 bytes. Per-day source/target/report hashes are in the completion receipt. No repair, retry or successful-subset scoring occurred.

| Pin | SHA256 |
| --- | --- |
| Original manifest | `ba773292535c97402826e6b40b34d367379a2db899f0010d474628220f965c2b` |
| Unchanged thresholds | `e071972d50781e4e6f4a103fef7e45aebe77b55d48dc92dfbba9afaea2b810a1` |
| Previous crossing registration | `1f1f858ded2f34ee8249b0500aec36f284454799a88b90089c675800e4304a8c` |
| Previous feature build | `a7d58549d87eb7331478380c0c427f2b4e97a8edff088e7e516737093fb3edf5` |
| Previous cost comparison | `09fc21c42a056b0e4c304cd22bdfb0035d0d3897c181dc901c4d036b0fa9895c` |
| New exit registration | `49e7de68bf84ca898f034ee37328583a94606769710edbff9dca3dacaaee49ff` |
| New completion | `a13c7b33e136c13ee7e44db060dbbf740372225fd8f5ff8ab5ff03c3ef0eb7b0` |
| New request | `7279ee09096eb71817be204ed25fc692f9cbabbcadf1b748cdd7aa4e91ccb609` |
| New verification receipt | `4999617c13a98acec1cea71b81c067ee59a95de3b1d69515b94c8cc2176e82af` |

The terminal verifier recomputed all directional targets from the exact pinned quote sequence, checked original decision and resolved reference-exit prices, required original shared-entry parity, regenerated all signals and all per-day/pooled metrics, and revalidated the complete previous experiment and calibration. Code, protocol, artifact bounds, whole-member evidence and false-authority flags were checked. The verified status is `verified_exposed_exit_comparison_not_validation`, twelve sessions and 129,406 rows.

Read-only verification in PowerShell, without native replay, model call or trade:

```powershell
Set-Location C:\Users\pabta\Projects\ai-trader
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_bracket_study verify --registration logs/6e_bracket_exit_20261004_1_registration.json --registration-sha256 49e7de68bf84ca898f034ee37328583a94606769710edbff9dca3dacaaee49ff --output data/processed/6e_bracket_exit_20261004_1 --completion-sha256 a13c7b33e136c13ee7e44db060dbbf740372225fd8f5ff8ab5ff03c3ef0eb7b0
```

Changed evidence, code, authority flags or a failure marker must refuse verification, not initiate a rerun. `independent_holdout`, `model_training`, `promotion_allowed`, `reserved_outcomes_opened` and `trading_enabled` remain false.

## Limitations and next decision

The engineering improvement is a more realistic cost-aware exit and abstention representation, not a demonstrated strategy improvement. Native receive timestamps and hypothetical BBO liquidation do not model depth/queue fills, broker EURUSD spreads/commissions, futures-to-CFD basis, order routing or measured execution latency. Stop levels do not cap realized losses when quotes widen or move before liquidation.

Do not retune brackets on this negative sample or expand it merely to find favorable sessions. The next hypothesis should explicitly address whether causal pre-entry liquidity, cost and short-horizon movement support can identify opportunities above round-trip friction, using a new fixed protocol and train-only construction. Broader declared development coverage and a genuinely untouched holdout remain required before promotion. Model training by itself cannot repair unsupported economics.

## Engineering checks

The 41 new tests cover mirrored exits, first-quote latency, widened spreads, overshoot, exact wait/deadline boundaries, native equal-time order, missing exits, both-positive states, window margin, gap bounds, future-outcome independence, mixed/reserved-session refusal, complete verification, repinned target/quote/metric/authority mutation and failure retention. With the previous auction/crossing tests, all 102 targeted tests pass. The final full Python suite passed 4,314 tests with one optional Nautilus evaluation-dependency skip in 1,275.77 seconds. Repository-wide Ruff, formatting checks for the three new Python files, and all 38 JavaScript tests pass.

This separate report uses the write-page skill to keep verified observations distinct from inference and deployment limitations. Prior reports and unrelated working-tree changes are preserved.
