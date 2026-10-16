# 6E Whole Cohort Liquidity Study

The historical target collection and one fixed CPU candidate completed and passed full verification on October 4, 2026. They cover all 196 accepted development sessions, 2,136,770 original decision rows and 129,039,967 native completed quotes. The three active rules have negative average closed-trade returns under both exit plans. The trained CPU candidate abstains on every row because its conditional net forecasts remain negative. No candidate is approved for trading.

This is a completed negative research result, not an unfinished fit or evidence that every possible order-book strategy fails. The study tests fixed causal liquidity, flow and replenishment measurements against declared quote-level friction; it does not establish executable EURUSD broker economics.

## Scope and session separation

The cohort contains all and only the accepted source sessions in the original pinned development manifest, from March 26 through December 31, 2025. Each session uses its declared dated Euro FX futures contract. Price analysis is confined to the original 12:00 to 16:00 UTC decision window and its declared reconstruction warmup. This is not analysis of every hour in the eighteen-month archive.

| Role | Accepted sessions | Decision rows | Causally eligible | Entered counterfactual candidates |
| --- | ---: | ---: | ---: | ---: |
| Train | 112 | 1,242,509 | 891,145 | 747,530 |
| Validation development | 43 | 473,337 | 365,158 | 316,200 |
| Test development | 41 | 420,924 | 328,663 | 281,676 |
| Total | 196 | 2,136,770 | 1,584,966 | 1,345,406 |

The original inventory contains 241 development dates and 230 reserved dates. The remaining 45 development dates retain their original dispositions: forty reconstruction-only, three vendor-degraded and two observed empty windows. They are not silently dropped from the coverage ledger or relabeled as negative examples. Reserved dates remain metadata-only. All later development roles were already exposed by earlier research, so none is an independent holdout.

The native replay verifies each accepted source member at EOF, reproduces every original row and sixty-second case, and matches reconstruction, receive-clock and execution-flow quality accounting. Quote columns retain every completed event in native order, including equal-time events. Disk-backed columns handle the high-activity day without discarding it. Bounded quote pages and one-hundred-decision target slices reduce memory use without reducing the native quote sequence.

## Fixed entry and exit targets

The entry is the first completed quote at or after decision plus 100 milliseconds, with a one-second wait limit. A widened first quote refuses entry; the engine does not search for a better later quote. Long and short counterfactuals share that entry. They cross the entry and liquidation bid/ask and subtract one assumed extra round-trip tick, not measured broker costs.

The time exit requests liquidation after a fifteen-second hold. The bracket watches for a net target of three ticks or stop of minus three ticks strictly before the timeout. Both exits wait 100 milliseconds after a request and use the first allowed completed quote, within a one-second wait. Stop overshoots and widened exits remain; fills are not assumed at exact barrier prices. A decision needs eighteen seconds before the window ends. Two- and four-tick stresses recost the same closed selections without changing triggers.

An unchanged one-tick spread starts the counterfactual at minus two net ticks: the spread plus the extra tick. Consequently, this bracket's three-tick net stop can trigger after only one further adverse tick. It is a deliberately fixed research setting, not an optimized or broker-validated risk setting.

| Hindsight state | Time exit | Bracket exit |
| --- | ---: | ---: |
| Long only positive | 97,196 | 63,652 |
| Short only positive | 97,867 | 63,802 |
| Both positive | 0 | 0 |
| Neither positive | 1,048,111 | 1,129,543 |
| Unknown | 893,596 | 879,773 |
| Jointly resolved | 1,243,174 | 1,256,997 |

Among jointly resolved bracket cases, 89.86 percent have neither direction positive; for time exits, the proportion is 84.31 percent. These are overlapping one-second counterfactuals, not independent trades, attainable classification accuracy or an executable oracle portfolio.

Unknown counts include 551,804 ineligible rows and 239,560 entry refusals or timeouts, plus 88,409 entered candidates lacking at least one bracket exit or 102,232 lacking at least one time exit. Unknown does not mean no trade, zero profit or a loss. The strict requirement for a new quote can make quiet, unchanged books unobservable under this target definition; that is not automatically corrupted data or actual broker unavailability.

## Causal policies and CPU training

The experiment fixes six policies before replay: CVD follow, liquidity follow, absorption fade, CPU cost, CPU cost with the liquidity gate, and no trade. Their inputs are exactly 23 original flow and visible-depth fields plus 14 prior-five-second execution proxies. Model inputs contain no dates, contract identifiers, absolute prices, future outcomes or labels.

The liquidity gate requires a prior quote gap of at most 250 milliseconds, known aggressors, unknown aggressor count fraction at most 0.1, at least five contracts on both top queues, at least twenty contracts in each five-level visible depth, five-level spans no larger than eight ticks, and at least twenty quote events in five seconds. The follow rule additionally requires twenty known trades, aligned CVD, OFI and midpoint movement, and sufficient preceding movement. The fade rule requires strong aggression without corresponding midpoint movement, held-top passive execution and other-ID reload on the attacked side, plus opposing visible queue imbalance. Those measurements are proxies, not proof of an iceberg or of a causal explanation for subsequent prices.

Feature-only signal support is 1,690,090 CVD-follow rows, 20,879 liquidity-follow rows and 5,440 absorption-fade rows. These include rows that later scheduling or causal eligibility can refuse. They are not counts of filled trades.

Training selections are causally eligible cases at least sixty seconds apart, independently within each train session. All 112 train sessions contribute 26,185 cases. The availability head uses all of them; the economic heads use the 20,090 jointly resolved cases, including losses and neither-positive cases. The remaining 6,095 cases have unknown returns and are not given zero-return targets. This exceeds the registered support requirements of one thousand jointly resolved and one hundred unknown train cases.

The original replay reproduces all 45,816 source cases. The new eighteen-second end margin leaves 45,812 sampled cases across the three roles. A separate pinned metadata and source-case reconciliation accounts for the difference: one original terminal case each on April 11, May 15, November 12 and December 23, all at approximately 15:59:42 UTC, lacks the declared eighteen-second margin. Two are train cases and two are test-development cases. All original decision rows remain in coverage; no future-return or successful-exit filter removes these four cases.

One ridge candidate has an unpenalized intercept and coefficient one under the mean-squared-error convention. Scaling uses all selected train cases, including unknowns; standardized inputs are clipped to ten in magnitude. The candidate has a clipped observability score and two conditional bracket-net-return heads, not a calibrated probability guarantee. It acts only if observability is at least 0.90 and the strictly larger conditional return exceeds 0.5 tick. Ties abstain. The same causal action sequence is compared under both exit plans; no separate time-exit model is trained. There is no class balancing, parameter search, later-role fitting or automatic winner selection.

Every policy and exit plan has a separate one-position schedule and ten-second cooldown. An entered position with an unknown exit blocks the remaining session. Daily research schedules do not carry an account ledger or prove overnight liquidation. Closed-return totals and descriptive drawdown therefore are not complete account PnL or account equity.

## Complete policy results

The CPU run exited successfully with `verified_quarantined_liquidity_cpu_not_validation`. Its verifier checked the train-only normal equations without refitting, regenerated every saved forecast and daily policy metric, compared all pooled summaries, reverified all target collection contents and checked the frozen implementation. All 196 daily report and forecast sidecars were required. No partial-cohort result was used to select parameters. A separate read-only run of the published operator verification command also exited successfully for the complete cohort and the same original completion pin; this is a reproducibility check, not independent market validation.

The following means are net ticks per **closed** trade at the base assumption of one extra round-trip tick in addition to crossing the bid and ask. Selected attempts include refused entries and entered trades with unknown exits. Unknowns are retained, not charged zero. The totals are incomplete research economics, not account PnL.

| Policy | Exit | Selected | Closed | Unknown entered exits | Positive closed | Mean net ticks |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| CVD follow | Time | 4,651 | 3,308 | 193 | 465 | -2.328 |
| CVD follow | Bracket | 11,796 | 8,981 | 192 | 675 | -2.245 |
| Liquidity follow | Time | 3,715 | 3,196 | 59 | 594 | -2.133 |
| Liquidity follow | Bracket | 4,933 | 4,305 | 15 | 395 | -2.204 |
| Absorption fade | Time | 2,368 | 2,092 | 32 | 326 | -2.083 |
| Absorption fade | Bracket | 2,684 | 2,401 | 15 | 222 | -2.091 |
| CPU cost | Time | 0 | 0 | 0 | 0 | Not available |
| CPU cost | Bracket | 0 | 0 | 0 | 0 | Not available |
| CPU cost with liquidity | Time | 0 | 0 | 0 | 0 | Not available |
| CPU cost with liquidity | Bracket | 0 | 0 | 0 | 0 | Not available |
| No trade | Time | 0 | 0 | 0 | 0 | Not available |
| No trade | Bracket | 0 | 0 | 0 | 0 | Not available |

The idle policies have zero entered trades and a zero closed-return sum, but no per-trade mean or win rate. Their abstention is not demonstrated predictive skill. For CVD follow, unknown exits block 192 bracket schedules and 193 time schedules out of 196 sessions. A large feature signal count therefore does not imply that a continuously funded account could execute that many trades.

Bracket stop overshoots remain in the closed samples: 711 for CVD follow, 301 for liquidity follow and 138 for absorption fade. Widened liquidation spreads occur in 3,832, 1,559 and 729 bracket closures respectively. These are not assumed fills at exact barrier prices.

### Role coverage

Every active rule has a negative closed-trade mean in every development role under both plans. Entries below are closed count, mean net ticks, and unknown entered exits. The two CPU policies and no-trade control have zero selected and closed trades in every role. The later roles remain exposed development checks, not independent validation.

| Role | Policy | Time closed | Time mean | Time unknown | Bracket closed | Bracket mean | Bracket unknown |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | CVD follow | 2,676 | -2.362 | 109 | 7,504 | -2.254 | 108 |
| Train | Liquidity follow | 2,319 | -2.127 | 43 | 3,258 | -2.183 | 8 |
| Train | Absorption fade | 1,368 | -2.161 | 20 | 1,599 | -2.098 | 7 |
| Validation development | CVD follow | 477 | -2.233 | 43 | 1,086 | -2.170 | 43 |
| Validation development | Liquidity follow | 586 | -2.212 | 8 | 702 | -2.255 | 3 |
| Validation development | Absorption fade | 433 | -1.894 | 8 | 481 | -2.139 | 5 |
| Test development | CVD follow | 155 | -2.019 | 41 | 391 | -2.279 | 41 |
| Test development | Liquidity follow | 291 | -2.017 | 8 | 345 | -2.299 | 4 |
| Test development | Absorption fade | 291 | -2.000 | 4 | 321 | -1.988 | 3 |

### Month coverage

All ten accepted month groups have negative closed-trade means for every active rule under both plans. Each cell shows time mean then bracket mean in net ticks. This is a complete month table, not selection of a favorable period; March contains only four accepted sessions. The CPU and idle policies abstain in every month.

| Month | Sessions | CVD time and bracket | Liquidity time and bracket | Absorption time and bracket |
| --- | ---: | --- | --- | --- |
| March 2025 | 4 | -1.886 / -2.163 | -1.806 / -2.099 | -1.857 / -1.795 |
| April 2025 | 21 | -2.460 / -2.258 | -2.055 / -2.257 | -2.680 / -2.285 |
| May 2025 | 22 | -2.089 / -2.276 | -2.220 / -2.093 | -1.982 / -2.095 |
| June 2025 | 21 | -2.192 / -2.227 | -2.036 / -2.143 | -2.090 / -1.996 |
| July 2025 | 23 | -2.169 / -2.334 | -1.889 / -2.174 | -1.913 / -1.991 |
| August 2025 | 21 | -2.150 / -2.194 | -2.499 / -2.230 | -2.142 / -2.147 |
| September 2025 | 20 | -2.181 / -2.155 | -2.395 / -2.327 | -2.084 / -2.080 |
| October 2025 | 23 | -2.268 / -2.176 | -2.072 / -2.209 | -1.744 / -2.181 |
| November 2025 | 19 | -2.120 / -2.240 | -2.062 / -2.378 | -1.927 / -1.909 |
| December 2025 | 22 | -1.787 / -2.328 | -1.972 / -2.206 | -2.094 / -2.082 |

### Cost and session diagnostics

The diagnostic plan was pinned at 16:45:38 UTC, before any model evaluation results were inspected. It uses 2,000 deterministic PCG64 resamples with seed 20261004 and five consecutive accepted-session blocks. Every accepted session remains in resampling, including no-trade and unknown-exit sessions. The intervals describe pooled closed-trade mean variability, not calibrated confidence, a p-value, multiple-testing protection or complete strategy economics.

| Policy | Exit | Mean at one extra tick | Mean at two | Mean at four | Descriptive interval at one |
| --- | --- | ---: | ---: | ---: | --- |
| CVD follow | Time | -2.328 | -3.328 | -5.328 | -2.414 to -2.137 |
| CVD follow | Bracket | -2.245 | -3.245 | -5.245 | -2.271 to -2.208 |
| Liquidity follow | Time | -2.133 | -3.133 | -5.133 | -2.272 to -2.025 |
| Liquidity follow | Bracket | -2.204 | -3.204 | -5.204 | -2.263 to -2.147 |
| Absorption fade | Time | -2.083 | -3.083 | -5.083 | -2.235 to -1.954 |
| Absorption fade | Bracket | -2.091 | -3.091 | -5.091 | -2.159 to -2.035 |

The stresses recost exactly the same closed selections and triggers. They are not a simulation of different broker commissions or a new optimized execution policy. The CPU and no-trade per-trade intervals are unavailable because they have no closed trades; no zero-return interval is invented.

Closed sums are negative in 187 of the 188 CVD bracket sessions with closures, 179 of 180 liquidity bracket sessions, and 174 of 176 absorption bracket sessions. The corresponding time counts are 170 of 171, 167 of 173 and 166 of 172. Unknown exits remain outside these closed sums, so neither daily totals nor descriptive path drawdown establish complete account risk.

## Missing exit observability audit

After inspecting the complete results, one explicitly post-result descriptive audit scanned all 2,136,770 owned target rows across all 196 accepted sessions. It counted both directional statuses, trigger categories and the existing path-inactivity marker. Its source and scope were pinned before this scan. It neither scored net returns nor called a predictor, fit a model, changed labels, opened raw archives or accessed reserved prices. This is not another prespecified strategy experiment.

| Exit plan | Entered cases with either direction unknown | Unknown directional outcomes | Unknown outcomes with a path gap over five seconds | Unknown outcomes without that marker |
| --- | ---: | ---: | ---: | ---: |
| Time | 102,232 | 204,464 | 7,634 | 196,830 |
| Bracket | 88,409 | 97,321 | 4,503 | 92,818 |

Time exits share the same request time, so both directions are unknown together in 102,232 cases. Brackets can request at different times: 8,912 cases have both directions unknown, 40,074 only long unknown and 39,423 only short unknown. The bracket's unknown directional outcomes follow 79,803 timeout requests, 17,503 stop requests and fifteen target requests.

Thus 96.27 percent of unknown time-exit directional outcomes and 95.37 percent of unknown bracket directional outcomes lack the path-gap-over-five-seconds marker. The marker describes an observed gap along a path; it does not identify the cause of a timeout. Its absence does not establish an intact transport connection, a firm broker quote or executable stale liquidity. This supports examining quote observability separately from long inactivity, not relabeling unknowns as losses, successes or corrupted sessions.

The complete declared-contract groups also retain different observability support. Percentages below use entered counterfactual cases, not selected policy trades or independent samples. Contracts span different dates and conditions, so this is not a causal comparison or a rule for dropping one contract.

| Declared contract | Sessions | Entered cases | Time joint unknown | Time percent | Bracket joint unknown | Bracket percent |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 6EM5 | 52 | 346,859 | 18,261 | 5.26 | 13,791 | 3.98 |
| 6EU5 | 65 | 432,493 | 36,669 | 8.48 | 30,666 | 7.09 |
| 6EZ5 | 62 | 461,726 | 34,937 | 7.57 | 31,836 | 6.89 |
| 6EH6 | 17 | 104,328 | 12,365 | 11.85 | 12,116 | 11.61 |

The existing roll is declared in advance, not proven contemporaneous maximum liquidity. This audit does not change it or select the better-looking dates. The separate next-study design in `docs/6E_OBSERVABILITY_NEXT_STUDY.md` is a proposal, not a launched experiment or training permission.

A separate pure-code completed-quote reference helper has passed 32 synthetic tests for cursor causality, quote validity, age bands and false authority. It has not been applied to historical rows, changed these targets or entered the paper engine. It is a foundation for testing observability, not a substitute fill model or an improvement in this candidate's measured returns.

## What the trained model learned

The jointly resolved train targets average -2.206 ticks for long and -2.191 for short. Both saved economic heads predict negative returns on every decision row: across the complete cohort, the highest long forecast is -1.789 ticks and the highest short forecast is -1.786. None passes the fixed requirement of more than 0.5 tick. The model does not abstain merely because its observability threshold is too high.

A post-result read-only arithmetic audit checked all 196 pinned daily reports and binary forecast sidecars. It counted 56,178 rows with observability at least 0.90, but zero rows with either conditional edge above 0.5 tick and zero fixed-gate actions. No features, target files, raw archives or reserved rows were opened by that supplementary audit, and it did not call a predictor or fit a model. This explanation is descriptive after the result, not a prespecified new strategy or permission to relax a threshold.

| Role | Sampled cases | Observability RMSE | Conditional long RMSE in ticks | Conditional short RMSE in ticks |
| --- | ---: | ---: | ---: | ---: |
| Train | 26,185 | 0.416 | 1.404 | 1.397 |
| Validation development | 10,080 | 0.401 | 1.230 | 1.213 |
| Test development | 9,547 | 0.435 | 1.092 | 1.082 |

Economic errors use only jointly resolved sampled cases. Unknown availability is not random; conditional-head errors cannot establish performance on missing exits. Error levels and abstention do not prove superiority to a constant predictor, calibrated probabilities or profitable timing. This fixed coarse linear candidate is not an exhaustive test of richer temporal order-book models.

## Synthetic prediction timing

The separate timing plan was pinned at 17:36:49 UTC, before model results were inspected. One completed benchmark measured exactly 1,000 single-row CPU calls after ten warmups. Median `Model.predict` time was 0.0177 milliseconds, p95 0.0183, p99 0.020301 and maximum 0.036, including numerical guards and standardization. Inputs were synthetic zeros, not market snapshots.

This excludes ingestion, raw decoding, feature construction, policy selection, risk, journaling, network transport, broker execution and Qwen. Shared-computer load can affect the measurement. It is not an end-to-end latency guarantee or evidence that a cheap spot broker can fill these opportunities. The fixed hundred-millisecond entry and exit delays remain unchanged.

## Evidence pins

| Evidence | SHA256 |
| --- | --- |
| Original development manifest | `ba773292535c97402826e6b40b34d367379a2db899f0010d474628220f965c2b` |
| Whole-cohort registration | `3bb478f1ca3af529c280671597193438b032e18985a7041f4ba6a9777a95a275` |
| Verified target collection completion | `c3c14ecf5344556c2aa3037e54979a2c3bbc417fe387775a44c266ec9d7ce58b` |
| Target collection verification receipt | `22cdcb35811abd1d44fc4b3118e3a083cd9cf2f56572c9bf1a9c4847e2638e7c` |
| Verified CPU comparison completion | `f8d85b19e23ae96588abfa52ebeb734ef20391db4fdadfa730336e7a0a7dbe43` |
| CPU comparison verification receipt | `7e0693b28de0bcb9056f041be9416242fdb2677f3f941abc0e3d637e74e2b587` |
| Quarantined CPU model JSON | `24d8e27cf52bf73689681db237ac96628670160ba77c00ec1969aae107548e8b` |
| CPU comparison request | `191d211394739d087fb604695e4c147891bf7d0ffd42e1b4c38d622070243a9c` |
| Prespecified descriptive diagnostics plan | `3d5e90a154b7cd8a0b72de4fcae1ec2ce59e8bba1527100a313af549dfe6bd89` |
| Completed descriptive diagnostics | `60d62ed0d5a275e8c7de70fca4287764909dd136e17e192382c36e141f12c4f6` |
| Prespecified synthetic timing plan | `8ac48858cba165e6216cc5b68bf32b49d7d2592c570dc79716a8f4eb8abc8c3e` |
| Completed synthetic timing | `9530aad946d0d0b63b703209c6e4f219cbf30b2bd24cbd2bebddc75854c660b7` |
| Post result missingness audit plan | `5597489c3ca5272a1315b297ca05f03f86c93d09bb08d7721e3bc295f295ff6c` |
| Post result missingness audit source | `0c6be56e333405983ea74be770894a57390bc7ebfd0555c62710e7007ad4721d` |
| Complete missingness description | `5eb8aca41c13284770c9e0c1696127d0dbd06507fde3531161ddfe832a82ef5e` |

The collection output is `data/processed/6e_liquidity_whole_20261004_1`; the completed CPU comparison is `data/processed/6e_liquidity_cpu_20261004_1`. The separate diagnostics and timing JSON files are beside these directories. Licensed archives, videos, raw captures, generated targets, forecasts and weights remain local and ignored by Git. The new root downloads ignore rule prevents accidental publication without removing any files. Existing unrelated changes remain preserved.

## Software verification and operating limits

The operator guide at `docs/6E_LIQUIDITY_OPERATOR.md` contains runnable PowerShell status and read-only verification commands. Its quick status checker reads bounded metadata only and never labels receipt agreement as a fresh full content verification. Failure evidence overrides completion metadata, and partial append reads remain unverified rather than being called corruption.

Runtime is Python 3.12.10, NumPy 2.5.3, databento-dbn 0.70.0 and zstandard 0.25.0. Repository-wide Ruff passed, and all eleven new production and test files pass formatting checks. The final full Python suite passed 4,440 tests with one optional Nautilus dependency skip in 1,319.71 seconds, including the reference helper's 32 synthetic tests. Earlier full checks passed at each implementation stage. All 38 JavaScript tests passed. The separate local missingness audit passed explicit Ruff and synthetic checks with poisoned profit and price fields, directional accounting and invalid-status/trigger/nonboolean-marker refusals. These software results do not validate profitability.

There were no downloads, network requests, credential access, live or paper orders, Qwen calls or training, reserved outcome reads, shutdowns or BTC collector changes. Model promotion, independent-holdout and trading flags remain false. The CPU candidate is a named research exception to the no-training phase, not permission to fit other models or update production weights.

Before any EURUSD paper deployment, synchronized broker quotes, realistic broker costs and latency, a continuous account ledger and independent prospective evidence are still required. CME futures BBO liquidation is not a demonstration of executable cTrader spot or CFD fills. More model training alone cannot supply the missing evidence.

## Next research boundary

Keep the completed candidate and the earlier Qwen adapter quarantined. Do not lower the action threshold, flip negative trades, select a favorable month, tune on reserved outcomes or repeat the fit to manufacture activity. Retain this complete negative result as a baseline.

| Readiness requirement | Current evidence | State |
| --- | --- | --- |
| Complete registered development coverage | All 196 accepted sessions and all original rows verified | Complete for this study |
| Causal features and session separated fitting | Thirty-seven allowlisted features and train-only normal-equation proof | Complete for this candidate |
| Positive net opportunity selection | All active rule means negative; CPU candidate selects no trades | Not established |
| Account treatment of unresolved positions | Unknown exits retained, but schedules reset daily without a continuous ledger | Incomplete |
| Independent strategy assessment | All used outcomes are exposed development data | Not performed |
| EURUSD broker execution evidence | Futures quote-level assumptions only | Not supplied |
| End to end decision latency | Synthetic CPU prediction component only | Not measured |

A subsequent explicitly registered offline study should first examine whether the fresh-quote exit rule creates avoidable observability censoring, without silently treating stale quotes as fills. It should define an account-level treatment for unresolved positions and costs before making economic claims. Any more expressive temporal liquidity model needs its own train-only development protocol and untouched prospective assessment; this study has not tested it. Broker quote alignment and execution evidence remain a separate requirement before EURUSD paper strategy activation.

The prior course review proposes location-aware attack, response and retest sequences. The current five-second aggregate features are not a complete implementation or refutation of those playbooks. A future causal sequence study should define a level using only the preceding prefix, distinguish held versus failed liquidity, and account for the delay needed to observe confirmation. Whether this improves opportunity selection remains an unanswered research question, not a reason to promote this candidate.
