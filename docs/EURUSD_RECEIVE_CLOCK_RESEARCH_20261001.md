# Historical 6E receive clock revision

This revision separates recorded arrival time from publisher-clock disagreement without changing the strategy comparison. V1 remains failed and immutable. V2 uses a separately frozen protocol and the same nine exposed development sessions; it does not restore their holdout status. No Qwen training, broker connection, live or paper orders, or BTC collector changes are included.

## Why the clock policy changes

The [V1 diagnostic](EURUSD_MULTIMONTH_RESEARCH_20261001.md) found 1,451 records on 8 October 2025 with exchange timestamps later than their receive timestamps, all after the research window. The discrepancy is embedded in the historical file, not caused by this computer's clock. V1 refused the full cohort before publishing results, as its registered rule required.

Databento preserves publisher event timestamps, uses receive time as the data index when available, and documents that publisher and capture clocks may disagree. Its sending-to-receive delta can be negative. This supports distinguishing arrival ordering from cross-clock comparisons; it does not prove the cause or harmlessness of this particular incident. [Databento timestamp definitions](https://databento.com/docs/standards-and-conventions/common-fields-enums-types).

## Explicit policy

| Record condition | V2 behavior |
| --- | --- |
| Normal target record | Preserve receive time and source order, including ties; publish features only at completed instrument events |
| Exchange timestamp exceeds receive time, or sending-to-receive delta is negative, during 11:59:50–16:00 UTC on a selected decision day | Refuse the whole cohort before applying that record; the ten-second warmup is protected too |
| Either disagreement outside that interval or on a reconstruction-only day | Audit the original timestamps and continue ordinary book processing; do not delete the record |
| Undefined receive timestamp or undefined non-snapshot event timestamp | Refuse the whole cohort |
| Snapshot timestamps | Preserve the earlier snapshot rules; do not interpret synthetic snapshot timestamps as measured latency |
| Receive-order violation, disallowed source flags, invalid book transition or incomplete event | Preserve the existing refusal rules, including the existing bounded closed-period clear exception |

The protected interval includes its start and excludes 16:00. V2 does not invent an acceptable clock-offset threshold from the observed 247 ms maximum. Outside the protected interval, it records counts, minimum and maximum positive event offsets, negative sending deltas, and the first eight disagreeing records per source member. Original files and input record timestamps are unchanged. These audits describe clock disagreement, not verified exchange-to-observer latency.

The replay already scheduled its features, entry waits, exits and inactivity timers on receive time. V2 changes the cross-clock refusal policy, not that causal clock. It never sorts by exchange time, adjusts timestamps, fits clock offsets, skips anomalous records or adds outside-window trade labels. Windows, contracts, 37 feature quantities, nine signal signs, entry latency, holding time and assumed costs are unchanged. Any disagreement inside a protected interval still fails the entire run; there is no favorable-session subset.

## Compatibility and exposure

The implementation uses a separate versioned receive core. The earlier source files and their hashes remain unchanged, so their registrations can still be verified. An AST regression checks that the new core differs from the original `consume` method only at the cross-clock check. The inherited event-completion, order-book, feature and execution wrappers remain in the method chain.

Synthetic tests require exact equality of all original feature and target rows for clean three-day blocks in each dated contract. The real run must also reproduce the pinned July execution-study rows exactly before publishing any results. Testing synthetic equality is not a substitute for that historical regression.

The new metadata ledger explicitly incorporates V1's immutable attempt sidecar. Of 471 daily members, 29 have documented outcome exposure, seven additional members were replayed for reconstruction, and four additional October members are conservatively exposed by the failed attempt. The remaining 431 have no replay documented by this inventory; that is not proof of non-exposure. The 230 reserved 2026 members remain metadata-only.

## Registration and verification

Registration: `logs/6e_multimonth_development_v2_20261001_1_registration.json`.

Registration SHA256: `96bc5d2bf691b8c3534fc697dcc77e9e9984329416f9103aae3b5b9244d19a38`.

The single new attempt must use new rows and report paths. The original failed registration, attempt, failure and diagnostic are pinned dependencies, not overwritten evidence. Code or metadata drift refuses execution. A failed V2 run retains its own attempt and failure files, publishes no partial rows and does not retry automatically.

The baseline full suite passed 3,284 tests with one optional Nautilus skip. The focused verification passed 136 tests, including 39 new tests for clock boundaries, raw-record preservation, unchanged strict gates, method-body compatibility, state reset, previous exposure and whole-cohort publication. The final full suite passed **3,323 tests with the same optional skip** in 227.09 seconds. Ruff and changed-file formatting checks passed.

## Completed historical comparison

The single V2 attempt started at 18:41:55 UTC on 1 October 2026 and exited successfully. It published 102,403 decision snapshots across all nine registered sessions, not 102,403 executed trades. All 30,756 July rows reproduced the earlier pinned artifact exactly, including every original feature, execution feature and target. No failure sidecar was created, and there was no retry or successful-session subset.

| Development block | Dated contract | Decision snapshots | Eligible | Resolved quote outcomes |
| --- | --- | ---: | ---: | ---: |
| 7–9 April 2025 | 6EM5 | 38,401 | 18,631 | 14,156 |
| 7–9 July 2025 | 6EU5 | 30,756 | 22,984 | 19,011 |
| 6–8 October 2025 | 6EZ5 | 33,246 | 27,350 | 24,275 |
| Total | Separate contracts, no splice | 102,403 | 68,965 | 57,442 |

The other 11,523 eligible decisions had unavailable entry outcomes: 8,177 spread-widening refusals and 3,346 quote timeouts. Their targets remain null; they are not silently relabeled as losses or no-trade examples. Another 33,438 decisions were ineligible. Of the resolved outcomes, 8,659 (15.07%) had a positive direction in hindsight after the assumed costs. That hindsight fraction is not a causal signal or an achievable win rate.

The clock audit covered 24,765,052 target records from all 12 source members, including 24,169 snapshots excluded from cross-clock comparison. It counted exactly the previously diagnosed 1,451 disagreeing records on 8 October, outside the protected interval, and none in any protected interval. No other selected member had a disagreement. All execution-volume conservation checks passed. This validates V2's declared processing policy; it does not certify the clocks or establish the root cause of their disagreement.

An additional read-only audit of the published files checked their raw hashes, canonical bounded rows, unique chronological decisions, exact dates/contracts/partition, all 37 finite feature quantities, nonnegative execution quantities, independent two-sided target arithmetic, null unavailable labels, entry/exit timing and session boundaries, per-session counts, all 12 dated mappings, clock-accounting totals and execution conservation. It also repeated the exact July comparison and revalidated the frozen registration. All checks passed; it did not replay raw data or fit a model.

### Fixed-rule results

Values below are mean net ticks per resolved selected trade under the registered quote policy: 100 ms entry delay, up to one second waiting for entry, at least 15 seconds holding, one position at a time, ten-second cooldown, crossed quotes and one extra tick of cost. They are not broker-account returns. The nine rules are separate, overlapping comparisons, not a combined portfolio.

| Fixed signal direction | April | July | October | Pooled | Positive session means |
| --- | ---: | ---: | ---: | ---: | ---: |
| Queue imbalance | -2.245 | -2.077 | -2.027 | -2.111 | 0/9 |
| CVD | -2.427 | -2.035 | -2.059 | -2.169 | 0/9 |
| Depth imbalance | -1.993 | -2.126 | -2.072 | -2.065 | 0/9 |
| Momentum | -2.184 | -2.168 | -2.141 | -2.164 | 0/9 |
| Generic replenishment | -2.051 | -2.125 | -2.091 | -2.090 | 0/9 |
| Passive execution flow | -2.413 | -2.033 | -2.057 | -2.163 | 0/9 |
| Held passive support | -2.092 | -2.193 | -2.150 | -2.145 | 0/9 |
| Same-ID net refresh support | No actions | No actions | No actions | No actions | Not applicable |
| Other-ID replenishment support | -2.394 | -2.187 | -2.160 | -2.244 | 0/9 |

Every active rule had a negative mean on every individual session, not only when pooled. Passive execution flow agreed in sign with CVD on 99.83% of eligible observations where both were nonzero; its richer accounting does not establish a distinct trading edge. Same-ID net refresh remained zero in these sampled features, so this run provides no positive evidence for that candidate and does not demonstrate that real icebergs are absent.

Queue and depth had conditional directional AUCs of about 0.529 (about 0.534 within activity/price strata), but both quote policies lost money. These AUCs use only hindsight-profitable directions; they cannot identify the profitable subset in advance. They must not be presented as profitable predictive accuracy.

### Evidence pins

All generated data and full research artifacts remain local and uncommitted. The following are SHA256 hashes of the exact file bytes:

- Attempt: `logs/6e_multimonth_development_v2_20261001_1_registration.attempt.json` — `3f37efea82351c7cf40cd19af98a2a8bf65aba73f3fe7fa96f0e9bcd87d7824f`.
- Rows (191,211,151 bytes): `data/processed/6e_multimonth_development_v2_20261001_1_rows.jsonl` — `9a2bb5fe5c32ea067c4d236f8245815bb8380b518bfdf26960b8954282efef84`.
- Report: `data/processed/6e_multimonth_development_v2_20261001_1_report.json` — `4493fec0320a96499eb683ba8c0376e43baf5795555c71d7c2d4467b183b0680`.

The registration and its preflight ledger stay frozen. Following successful V2 publication, the four October members previously marked conservatively exposed now have completed evidence: three outcome-bearing days and one reconstruction-only day. Future exposure inventories must include this result; these days are not fresh validation data. The 2026 reserved members were not replayed.

## Decision and next step

Do not promote these sign-only policies or use their losing trades as positive Qwen action demonstrations. The result rejects these specific, frequent 15-second entries under the stated costs; it does not reject all microstructure strategies or all holding periods.

The next bounded research step is to preregister a selective, cost-aware entry experiment on development data: predict net opportunity as well as direction, allow abstention, compare against no-trade and CVD-only baselines, and measure whether execution features add value. Use chronological whole-session splits with training-only calibration, report missing outcomes and activity-stratified coverage, and keep the reserved 2026 data untouched. This is a proposed experiment, not an authorization to search many thresholds until a profitable backtest appears or a claim that a model will solve the cost problem. Qwen training remains deferred until there is a defensible learning target.

## Research limits

This comparison is development research, not an independent test or an execution simulation at a cTrader broker. Quote returns omit broker-specific costs and fills. Conditional directional AUC uses hindsight-positive outcomes and is not a live entry filter. Correct clock handling does not establish a profitable strategy or justify promoting any of the nine rules.
