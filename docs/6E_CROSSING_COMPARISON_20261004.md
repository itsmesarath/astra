# 6E crossing comparison 20261004

## Decision

The completed-event representation fix worked: real crossings now survive publication to the one-second decision grid, and both range playbooks can be exercised. It did not establish a profitable strategy. Keep these rules research-only; do not promote them or train Qwen to imitate their entry decisions as profitable targets.

Failed auction closed 16 quote outcomes at -45 total ticks, averaging -2.8125. Accepted breakout closed eight at -22 ticks, averaging -2.7500. Every active declared policy had negative pooled closed returns under the frozen base-cost assumptions. Snapshot-only and idle policies made no trades; their zero totals are abstention, not profitable performance.

This is a second exposed-development comparison, not independent validation, broker execution or account PnL. No training, model inference, download, network request, credential access, paper/live order, reserved outcome access or BTC collector change occurred.

## Representation change

The first pilot's feature-only diagnostic suggested a representation mismatch: native quote updates can roll the immediately preceding range forward before the sampled decision sees a full-tick attack. This version preserves the first crossed boundary rather than lowering the one-tick threshold. The unchanged snapshot controls still produce zero range signals, while the retained-event version has initiation and confirmation support.

- At the first strictly outside completed midpoint, freeze the pre-event 60-second range and its boundary. The previous completed midpoint must be inside or on that boundary; range width remains 2–12 ticks.
- Complete the attack when a subsequent completed midpoint reaches at least one tick outside that frozen level within five seconds. Two successive half-tick updates can meet this unchanged distance threshold.
- Preserve the completion timestamp, native ordinal, prices and causal aggressor-count/quantity frame. Publish all retained markers once, in native order, at the next decision. Never backdate the decision or entry to the attack.
- Clear partial attacks and unpublished evidence on inherited order-flow resets. Refuse overflow rather than truncate, and reject future, stale, duplicate, misordered or malformed evidence.

The policy takes the first qualifying native-order marker, not a hindsight winner. Initiation activity/CVD quantiles, confirmation gates, expiry and cooldown remain unchanged. Sequence confirmation requires a later decision; the episode deadline starts at the attack completion, not delayed publication. Trade volume remains `T`-only and available at completed `F_LAST` events. Unknown aggressors are not guessed.

The original pilot modules, results and thresholds remain byte-unchanged. Three new modules implement evidence retention, sequential rules and the two-stage runner: `six_e_crossing_events.py`, `six_e_crossing_playbooks.py` and `six_e_crossing_study.py`.

## Frozen scope and support gate

The new protocol was registered before native replay. It uses the same twelve calendar-selected 2025 sessions and 12:00–16:00 UTC decision windows as the first pilot:

| Dates | Dated contract | Existing role | Rows |
| --- | --- | --- | ---: |
| April 7, 8, 9 and July 7, 8, 9 | 6EM5 and 6EU5 | Train | 69,157 |
| October 6, 7, 8 | 6EZ5 | Validation development | 33,246 |
| December 8, 9, 10 | 6EH6 | Test development | 27,003 |
| Total | Four dated contracts | Exposed development | 129,406 |

Coverage remains 48 decision hours, or 6.056% of the 2,136,770 accepted decision rows. This is not a new-feature analysis of all 196 accepted sessions. Whole selected daily DBN members were consumed to EOF and their original hashes verified; this does not mean decisions outside the four-hour windows were evaluated. The 230 reserved inventory dates stayed metadata-only. Existing role names do not make already-exposed outcomes independent holdouts. The fixed research roll is not a guarantee of the most liquid contract, especially for December's 6EH6 observations.

Calibration is exactly the first pilot's feature-only quantiles from 26,187 early-train causal cases across 112 training sessions, including unknown-outcome cases. No threshold refit or search occurred. This is retrospective fold calibration, not an online-learning simulation of the early training dates.

Before cost scoring, the complete feature-only build had to provide at least 20 qualified markers across four sessions, including one validation-development session. Independent verification of all twelve sessions passed that frozen gate:

| Evidence stage | Count |
| --- | ---: |
| Completed native quote observations including warmup | 7,397,972 |
| Completed attack markers | 4,262 |
| Published markers | 4,258 |
| Unpublished markers discarded on reset | 4 |
| Qualified markers after initiation and current-decision quality gates | 262 |
| Sessions with qualified markers | 9 |
| Validation-development sessions with qualified markers | 3 |
| Failed-auction episodes armed and confirmed | 150 / 41 |
| Accepted-breakout episodes armed and confirmed | 151 / 11 |

There were no unpublished tail markers. Publication conservation was checked. Published markers, qualified markers, armed episodes, confirmed signals, selected attempts and closed outcomes are different populations; they must not be conflated. All original rows and all original 33-field auction snapshots matched the first pilot exactly. Twelve new feature-only sidecars total 307,940,291 bytes.

## Verified cost comparison

All eleven policies were fixed before replay. The price-only ablations remove only initiation activity/CVD gates; they retain marker-quality, confirmation and sequential gates. Queue controls use the same confirmation times, with neutral queue direction producing no signal. Crossing follow uses the first qualifying marker at publication time. Snapshot branches and burst follow were required to reproduce their original per-session results exactly.

The unchanged comparator uses eligible entries, a 100 ms minimum latency, a 15-second quote exit, one-position lock and ten-second cooldown. Base costs cross entry/exit quotes and deduct one additional tick. These are quote-based research outcomes, not simulated depth/queue fills, measured commissions, CFD returns or stop/target trades. Policies are evaluated separately, not as a combined portfolio.

| Policy | Signals | Selected attempts | Closed outcomes | Net ticks | Mean closed ticks |
| --- | ---: | ---: | ---: | ---: | ---: |
| Event failed auction | 41 | 22 | 16 | -45 | -2.8125 |
| Event accepted breakout | 11 | 8 | 8 | -22 | -2.7500 |
| Price-only failed auction | 217 | 129 | 102 | -223 | -2.1863 |
| Price-only accepted breakout | 12 | 8 | 6 | -9 | -1.5000 |
| Failed-auction queue control | 41 | 22 | 16 | -19 | -1.1875 |
| Accepted-breakout queue control | 9 | 7 | 7 | -8 | -1.1429 |
| Snapshot failed auction | 0 | 0 | 0 | 0 | Not estimable |
| Snapshot accepted breakout | 0 | 0 | 0 | 0 | Not estimable |
| Crossing follow | 212 | 88 | 63 | -132 | -2.0952 |
| Original burst follow | 1,964 | 876 | 658 | -1,600 | -2.4316 |
| Idle | 0 | 0 | 0 | 0 | Not applicable |

Failed auction had two positive closed outcomes and no positive session; six selected attempts were refused for widened entry spread. Accepted breakout had one positive closed outcome and no positive session. At two/four additional cost ticks, totals worsen to -61/-93 for failed auction and -30/-46 for accepted breakout. Every active declared policy remains negative at these recost levels.

Removing initiation flow gates increased failed-auction support but did not produce positive economics. Queue controls were less negative here, but their small samples and different directions do not establish a profitable queue edge or justify selecting them as a winner. Price-only and crossing-follow comparisons also have different entry times/populations; they do not establish causal attribution.

| Existing role | Failed auction signals / closed / net ticks | Accepted breakout signals / closed / net ticks |
| --- | --- | --- |
| Train | 38 / 13 / -39 | 8 / 5 / -16 |
| Validation development | 3 / 3 / -6 | 3 / 3 / -6 |
| Test development | 0 / 0 / 0 | 0 / 0 / 0 |

The December sessions had one qualified initiation marker in total, with no confirmed entry for either main rule. Zero test-development returns are not evidence of generalization. Failed auction generated approximately 0.85 signals/hour and accepted breakout 0.23 signals/hour across this sample. Neither meets the requested frequent-scalping objective; this is not a low-latency HFT engine.

All dataset status categories were retained: 70,111 resolved outcomes, 42,742 ineligible decisions, 11,101 widened-spread refusals and 5,452 entry-quote timeouts. Unknown/refused outcomes were not silently converted to zero-profit trades. The price-only failed-auction control included one inactivity-exposed entered outcome and four late quote exits; these diagnostics remain visible rather than being dropped.

## Next research decision

Keep the event buffer and its integrity tests. Do not enlarge or retune this negative experiment merely to find favorable sessions, and do not label its entries as positive Qwen targets. A next hypothesis needs a separately frozen, cost-aware definition of entry, no-trade and exit, with support checks before economics. Native execution latency, depth/liquidity and broker-specific spreads must be addressed before equating short futures quote movements with executable EURUSD CFD trades.

These results do not disprove all auction or order-flow concepts. They show that these exact causal sequences and execution assumptions did not establish an edge on this exposed sample. Broader predeclared development coverage and a genuinely untouched evaluation remain necessary before promotion. Model adapters stay quarantined. `independent_holdout`, `promotion_allowed`, `trading_enabled`, `reserved_outcomes_opened` and `model_training` are all false.

## Evidence and verification

Project root: `C:/Users/pabta/Projects/ai-trader`. Registration: `logs/6e_crossing_comparison_20261004_1_registration.json`. Feature evidence: `data/processed/6e_crossing_features_20261004_1`. Cost evidence: `data/processed/6e_crossing_cost_eval_20261004_1`.

| Pin | SHA256 |
| --- | --- |
| Original manifest | `ba773292535c97402826e6b40b34d367379a2db899f0010d474628220f965c2b` |
| Original pilot completion | `b9a0d347a251c58e8fa2c332cb63491dc5f8cd5e4dd461332350885e5b4337f0` |
| Unchanged thresholds | `e071972d50781e4e6f4a103fef7e45aebe77b55d48dc92dfbba9afaea2b810a1` |
| New registration | `1f1f858ded2f34ee8249b0500aec36f284454799a88b90089c675800e4304a8c` |
| Complete feature build | `a7d58549d87eb7331478380c0c427f2b4e97a8edff088e7e516737093fb3edf5` |
| Complete cost comparison | `09fc21c42a056b0e4c304cd22bdfb0035d0d3897c181dc901c4d036b0fa9895c` |

The terminal verifier independently checked complete sidecars, regenerated all signals and metrics, required baseline-control parity, recomputed pooled summaries and checked original calibration, code/source pins and false-authority flags. There was no successful-subset scoring or retry.

Read-only verification in PowerShell, without native replay, model call or trade:

```powershell
Set-Location C:\Users\pabta\Projects\ai-trader
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_crossing_study verify-evaluation --registration logs/6e_crossing_comparison_20261004_1_registration.json --registration-sha256 1f1f858ded2f34ee8249b0500aec36f284454799a88b90089c675800e4304a8c --build-output data/processed/6e_crossing_features_20261004_1 --build-sha256 a7d58549d87eb7331478380c0c427f2b4e97a8edff088e7e516737093fb3edf5 --output data/processed/6e_crossing_cost_eval_20261004_1 --completion-sha256 09fc21c42a056b0e4c304cd22bdfb0035d0d3897c181dc901c4d036b0fa9895c
```

Expected status: `verified_exposed_development_not_validation`, twelve sessions and 129,406 rows. Changed evidence, implementation, authority flags or failure markers must refuse verification, not trigger repair or an automatic rerun.

## Engineering checks

The 29 new tests cover mirrored native crossings, exact-once publication, reset conservation, expiry, malformed/future evidence, native-order selection, sequential confirmation, outcome independence, prefix causality, original-engine parity, two-stage support refusal and complete result verification. Combined with the 32 original auction tests, all 61 targeted tests passed. The final full suite passed 4,273 tests with one optional Nautilus dependency skip in 1,349.30 seconds. Repository-wide Ruff and formatting checks for the four new Python files passed. Existing unrelated working-tree changes were preserved.

This separate report uses the write-page skill to distinguish verified observations, design inference and deployment limitations; it does not replace the original pilot report.
