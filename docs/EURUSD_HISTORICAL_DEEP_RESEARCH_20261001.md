# Historical EURUSD futures research findings and next experiments

The historical evidence supports a change in research emphasis: first identify when sufficient movement is likely, then study direction and execution separately. The latest classifier learned more about opportunity frequency than direction. Sixteen simple directional rule variants remained negative after costs on all 15 examined days. This does not rule out microstructure trading, but it does rule out treating the current signals, or their reversed signs, as established profitable strategies.

This work is historical only. No live feed, collector, broker connection, training job or order was started. The saved classifier was evaluated without refitting. Existing BTC collection and trading controls were not changed. We can continue the historical program without connecting NinjaTrader or cTrader now.

## Scope and evidence limits

The pinned inventory contains 471 UTC daily MBO files across three ZIP archives totaling 17,928,869,179 bytes, covering March 26, 2025 through September 25, 2026. Seven daily files have vendor degraded flags and 277 headers contain partial symbol-resolution lists. Those flags need contract-specific investigation; they do not by themselves mean every active-contract record is missing. The inventory's missing calendar dates are Saturdays. File coverage is not the same as complete exchange-session coverage.

The original intake checked archive and supplied-manifest hashes, ZIP member checksums and DBN headers. It did not reconstruct every event in the full 18-month corpus. This pass rechecked that pinned inventory, not all archive bytes again. Its quantitative research uses the previously audited 6EU5 microdepth artifact: 159,101 decisions from 12:00 to 16:00 UTC on July 7–25, 2025, with 101,762 resolved outcomes. All 15 dates were already exposed. No unused raw archive dates were opened, and no fresh holdout was consumed.

The main earlier model and playbook experiments also examined 6EM5 in March–April, using minute sampling and a smaller seconds pilot. They provide context, not a pooled second-contract validation for the July calculations. We have not established results across all contracts, the London open, overnight periods, roll transitions, holidays or multiple market regimes.

The diagnostic program evaluated every listed comparison: 16 fixed directional variants, all 23 feature columns in up to five bins each, four assumed extra-cost levels, four UTC hours, all 15 sessions, a causal 60-second-thinned sample and a decomposition of the frozen classifier's probabilities. Early/later feature comparisons use seven early and eight later already-exposed sessions. Bin boundaries use only eligible early-session feature values, not outcomes. These are exploratory descriptions, not independent validation or a hidden search for a deployable winner.

## Movement is often too small to pay for crossing

The fixed target is a nominal 15-second hold, with entry at least 100 ms after the decision. Longs enter at the ask and exit at the bid; shorts do the opposite. The mean realized quote interval is 15.37 seconds because the exit uses an observed later quote. Commission, slippage and impact are not measured. An extra tick is an explicit assumption, not a broker fee quote.

Across resolved candidates, the median absolute midpoint move was one tick and the mean was 1.351 ticks. The average crossed-spread burden was 1.110 ticks. The remaining margin is small even for someone who knew the future direction; actual direction predictors performed much worse. Without selecting which situations to avoid, even choosing the better direction in hindsight on every resolved candidate would average about minus 0.759 ticks after the extra one-tick charge. A hindsight selector allowed to abstain is different and is not available to a causal strategy.

| Extra assumed round-trip cost beyond crossing | Resolved candidates with either direction positive in hindsight |
| --- | ---: |
| 0 ticks | 30.28% |
| 1 tick | 13.36% |
| 2 ticks | 6.01% |
| 4 ticks | 1.53% |

These are overlapping candidate outcomes, not achievable win rates or trade counts. Removing costs to create a profitable chart would not solve the problem. A limit-order strategy also cannot be evaluated by simply deleting the spread: fills, queue priority, latency and adverse selection must be modeled separately.

There were 120,674 causally eligible decisions. Of those, 18,912, or 15.67%, lacked an accepted entry outcome: 8,612 quote timeouts and 10,300 widened spreads. Another 38,427 decisions were ineligible before entry. The resolved set included 1,155 inactivity-exposed outcomes. None of those categories was silently converted into a win or removed from the availability accounting.

Selecting the first eligible decision at least 60 seconds after the previous selection, without consulting its outcome, left 3,508 candidates and 2,887 resolved outcomes. Their positive-opportunity fraction was 12.47%, versus 13.36% in the dense sample. This reduces overlap but does not make observations independent or eliminate missing-outcome selection. A large row count should not be confused with a large number of independent market episodes.

## Simple continuation and reversal rules both fail here

Each diagnostic follows or fades the sign of one current feature, abstains at zero, retains the inherited eligibility and entry rules, allows one position, and waits ten seconds after resolution. It can enter again while the feature retains its sign; it does not impose the earlier pilot's one-entry-per-signal-episode rule. No threshold was fitted. Entry failures remain counted, and late exits or inactivity exposures are retained. Results concern historical quote counterfactuals, not paper fills or account returns.

| Feature or control | Closed quote round trips per orientation | Follow mean net ticks | Fade mean net ticks |
| --- | ---: | ---: | ---: |
| Best-queue imbalance | 7,208 | −2.062 | −2.169 |
| Five-second OFI | 7,242 | −2.094 | −2.136 |
| Five-second CVD | 6,884 | −2.072 | −2.158 |
| Five-level depth imbalance | 7,245 | −2.043 | −2.186 |
| Five-second midpoint change | 6,573 | −2.115 | −2.116 |
| Bid reload minus ask reload | 7,189 | −2.061 | −2.170 |
| Sell absorption proxy minus buy absorption proxy | 6,884 | −2.158 | −2.072 |
| Always long and always short controls | 7,248 | −2.088 long | −2.143 short |

Every variant's daily net mean was negative on every examined day. Even the largest average favorable signed midpoint move, about 0.071 tick for following deeper-book imbalance, was much smaller than that rule's approximately 1.115-tick spread burden before the additional cost. The exact averages should not be used to rank and select a winner from a losing grid.

Reversing the direction does not reverse the costs. For a mirrored pair sharing the same schedule, the two net returns sum to minus twice the spread burden minus twice the extra cost. A losing directional rule can therefore remain losing after reversal. That identity was independently checked for all seven pairs.

The JSON report includes early/later results, daily means, retained entry failures, inactivity counts, return tails and descriptive whole-day bootstrap intervals. Its 2,000 resamples do not correct for the many comparisons or establish independence between days. No p-value or promotion claim is made.

## The classifier mostly recognizes activity rather than direction

The existing classifier predicts three mutually exclusive classes: positive-net short, neither direction positive, and positive-net long. Its probability distribution can be separated into the probability of any positive opportunity and the probability of long rather than short conditional on an opportunity.

On its original three exposed development days, July 16–18:

| Diagnostic | Frozen model | Training-prior control |
| --- | ---: | ---: |
| Any-opportunity binary log loss | 0.405656 | 0.446227 |
| Any-opportunity AUC | 0.655612 | 0.5 for a constant score |
| Directional log loss given a hindsight opportunity | 0.691742 | 0.694073 |
| Directional AUC given a hindsight opportunity | 0.537936 | 0.5 for a constant score |
| Conditional direction accuracy at a fixed 0.5 threshold | 53.00% | 49.39% |

About 99.10% of the total multiclass log-loss improvement comes from the first task. This follows directly from the loss identity: opportunity loss plus opportunity prevalence multiplied by conditional direction loss. It is a useful diagnosis, not proof that an activity filter will improve an executable strategy. The conditional-direction calculation uses hindsight to identify its subset; that subset is not a deployable filter.

The original classifier made 218 directional largest-probability classifications, 209 on July 16. An additional exploratory timing check found only four of those 209 in 12:30–12:45 UTC. BLS published PPI at 08:30 ET on July 16, equivalent to 12:30 UTC, but this narrow overlap does not support blaming that scheduled release for the classifier's whole-day concentration. Scheduled-news and unscheduled-event exposure should be separate future questions, not post-hoc explanations. [BLS archived release](https://www.bls.gov/news.release/archives/ppi_07162025.htm).

## Activity and liquidity states deserve attention

The later eight exposed sessions show consistent descriptive differences in whether either direction eventually clears the assumed costs. The bins below use early-session feature thresholds. They are not entry thresholds chosen for trading.

| Feature | Lowest populated bin opportunity rate | Highest populated bin opportunity rate |
| --- | ---: | ---: |
| Completed quote events in five seconds | 9.96% | 23.46% |
| Known trade count in five seconds | 11.06% | 22.33% |
| Recent midpoint travel | 10.98% | 23.38% |
| Normalized bid reload | 10.24% | 23.75% |
| Normalized ask reload | 9.98% | 24.18% |
| Best bid quantity | 18.46% | 13.58% |
| Best ask quantity | 19.14% | 13.04% |

The inference is that activity and thinner queues may help identify movement potential. These measures are correlated and may partly describe the same state; the comparisons do not establish independent contributions, causality or tradable direction. Reload also rises with activity, so its relationship with opportunity frequency is not evidence of iceberg detection.

Opportunity frequency varied from 5.68% to 23.85% across the 15 days. By decision hour it was 10.09%, 15.48%, 14.99% and 11.96% for 12, 13, 14 and 15 UTC. This is not a recommendation to trade a selected hour: directional edge and costs remain unresolved, and London morning and overnight observations were outside these experiments.

Two depth-span features were almost constant: the bid and ask five-level spans equaled their modal value on 99.96% of decision rows. They cannot contribute much discrimination in this cohort, though rare outliers and other contracts may differ. The unknown-trade fraction was zero on 95.91% of rows, but did reach one; it must not be discarded as universally constant.

## Our absorption and iceberg representations need stronger evidence

The current absorption proxy uses signed net CVD, depth and price displacement. Its sign is algebraically redundant: sell-proxy minus buy-proxy has exactly the opposite sign to CVD. This identity held across all 159,101 rows. Consequently the absorption sign variants above duplicate the CVD variants; 16 tested specifications are not 16 independent ideas.

The reload proxy matches visible queue decreases and later increases. It cannot distinguish cancellation from execution, and a replenishing price level need not represent one hidden order. A better historical test should retain passive order IDs, matched executed volume, surviving displayed quantity, subsequent refresh and event ordering. Keep same-order refresh candidates separate from new-order replenishment and unidentifiable cases.

CME explains that native iceberg refresh retains the OrderID, while synthetic refresh appears as a new exchange order. That provides a research distinction, not a guarantee that every repeated ID or refill is an iceberg. [CME MBO explanation](https://www.cmegroup.com/articles/faqs/market-by-order-mbo.html).

Databento requires completed `F_LAST` events for coherent book observations. Trade and passive Fill records describe different sides of the same execution; Fill records do not themselves mutate the displayed book. The GLBX normalization also distinguishes displayed MBO from implied liquidity and preserves per-instrument message ordering for FIFO inference. These details matter for execution-linked features and a future maker simulator; treating all volume records as separate trades would be wrong. [Databento GLBX normalization](https://databento.com/docs/knowledge-base/datasets).

## Research possibilities and what would test them

This is a map of distinct mechanisms, not a claim to have exhausted every parameter combination. Each new outcome study needs a recorded comparison budget, source-session split and rejection rule before unused evaluation outcomes are inspected.

| Possibility | Historical test needed | Current evidence or missing piece |
| --- | --- | --- |
| Movement potential plus separate direction | Estimate movement magnitude, conditional direction and payoff separately; compare with a single joint model | Current classifier mostly learns opportunity frequency; no validated two-stage policy |
| Multiple scalp horizons | Paired entry times with 1, 5, 15, 30 and 60-second outcomes; add event-count horizons as a separate clock | A subsequent three-day exposed pilot now compares these time horizons; event-count clocks and broader replication remain untested |
| Adaptive stop and target exits | Replay barrier crossings, latency-aware exits and explicit timeout exits; report favorable and adverse excursions | The subsequent pilot reconstructs observed extrema and barrier order, but does not simulate stop/target fills |
| Execution-linked absorption | Measure executed volume against persistent displayed liquidity, then a separately timed confirmation | Net-CVD and generic reload proxies are insufficient |
| Native refresh and synthetic replenishment | Separate same-OrderID refresh after fills from new-ID clusters; retain uncertain cases | Raw MBO permits richer investigation, but current saved rows omit order lifecycle detail |
| Queue depletion and continuation | Study event sequences and deeper-level flow before price changes; compare with imbalance-only controls | Simple sign continuation is negative at 15 seconds |
| Exhaustion, failed breaks and reclaim | Freeze a previously known level; test arrival, breach, refill, reversal and confirmation as separate stages | Earlier minute break/reclaim tests were negative; detailed event sequences are untested |
| Trend pullback | Establish trend and level from completed past data, then compare low-energy counterflow and renewed aggression | Cannot label trend using the eventual day high, low or close |
| Passive entry and hybrid exit | Explicit hypothetical queue placement, matching rules, latency, cancellations, partial fills and adverse-selection bounds | Removing spread from market-order targets is not a maker backtest |
| Activity, time of day and news | Predefine session clocks and published release times; test interaction effects and daily stability | Activity associations exist; causality, independent lift and news attribution are unproven |
| Contract rolls and multiple regimes | Prior-known contract choice, separate dated books and roll/session boundaries, multi-month replication | One dated July contract and a small March–April cohort are insufficient |
| Cross-contract or cross-market confirmation | Causal timestamp alignment and availability audit before lead-lag tests | Parent 6E MBO may contain several contracts; broker EURUSD and other markets are not interchangeable |
| Sequence encoder or small neural network | Compare a bounded event-sequence model against strong linear, tree and price-only controls | More capacity is not a substitute for verified labels; snapshot features may miss event order |
| Qwen as a slower research reviewer | Train factual structured explanations on verified outcomes and uncertainty, with an independent evaluation | Not a replacement for the fast quantitative signal and risk path |

The literature supports asking narrower questions. Cont, Kukanov and Stoikov study short-interval OFI and price changes; explaining contemporaneous movement does not establish a forecast. Gould and Bonart investigate next-midmove queue information in equities, not net 6E scalp profit. Work by Lucchese, Pakkanen and Veraart motivates testing order-book representation and multiple horizons; its findings do not establish profitability for this dataset. [OFI paper](https://arxiv.org/abs/1011.6402), [queue-imbalance paper](https://arxiv.org/abs/1512.03492), [order-book forecasting paper](https://arxiv.org/abs/2211.13777).

## Recommended historical sequence

The first step is now completed as a bounded [paired historical path study](EURUSD_HISTORICAL_PATH_STUDY_20261001.md) on 7–9 July. All original 15-second rows and features matched exactly. On identical entries, spread plus one extra cost tick left only 0.14% of one-second outcomes and 1.68% of five-second outcomes positive in either hindsight-selected direction. Longer horizons increased movement opportunities without establishing directional edge. Observed barrier order is now available, but execution-aware stop/target returns remain untested.

The second step now has a bounded [execution-linked pilot](EURUSD_EXECUTION_LINKED_RESEARCH_20261001.md) with fourteen passive-fill, displayed-decrease and refill features. It preserved all original outcomes and checked activity and prior-price controls. Matched passive-flow direction was largely redundant with CVD, and the tested held-price and replenishment sign rules did not establish a profitable edge. Richer sequence confirmation remains untested; a refill is not automatically absorption or an iceberg.

Third, expand to additional historical months with a versioned exposure ledger, dated-contract mapping and source-level quality gates. The [multi-month development protocol](EURUSD_MULTIMONTH_RESEARCH_20261001.md) now freezes development through December 2025 and reserves January–March 2026 for validation, April–June for testing and July–September for final evaluation. It reconciles documented prior replay but does not equate undocumented access with proven non-exposure. Its first comparison uses nine explicit development sessions; full exchange-session and holiday handling remain separate work. Do not shuffle overlapping rows across partitions or open reserved outcomes during design.

Only then compare a small set of model families and execution assumptions under a fixed comparison budget. Preserve every failed experiment. A final test must not become the next training feedback loop. Searching many alternatives until one looks good creates a substantial false-discovery problem; an ordinary held-out slice does not undo repeated selection on it. [Bailey and colleagues on backtest overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).

None of those three historical steps needs a live connection. Broker-specific execution validation remains a future requirement for claiming spot/CFD tradability, not a reason to interrupt the historical work now.

## Reproduction and verification

The new descriptive report is local at `data/processed/6e_historical_deep_diagnostics_20261001_1.json`, SHA256 `d00dc350f0c8f0f30dbeeb2293299ec2bc90f9e8ad90f209981405d8d1df4f97`. It records all input and implementation hashes, feature-bin tables, all rule variants and per-session statistics. No licensed rows or trained artifacts were added to Git.

Run the same diagnostic against the existing pinned local artifacts, using a new output name:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.historical_6e_diagnostics --output data/processed/6e_historical_diagnostics_reproduction.json
```

The command refuses changed input hashes and existing outputs. It does not fit a model or read unused archive members. A separate read-only arithmetic check verified mirrored-rule cost identities, the probability-loss decomposition, the absorption/CVD sign identity and feature concentration. That check also made the explicitly exploratory release-window count described above. The new focused suite passed 22 tests. The full suite passed 3,187 tests with one optional native Nautilus dependency skip in 213.94 seconds. Ruff and changed-file formatting checks passed. Unrelated worktree changes were preserved.
