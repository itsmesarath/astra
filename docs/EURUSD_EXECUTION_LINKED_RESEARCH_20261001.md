# Historical 6E execution and replenishment research

This pilot adds execution-linked features to the existing historical EURUSD signal research. It separates passive fills, displayed decreases and subsequent replenishment, while preserving every original feature and 15-second outcome. It uses only the already-exposed 7–9 July 2025 sessions, contract 6EU5, from 12:00 to 16:00 UTC, with the existing ten-second feature warmup. There is no training, platform connection, model promotion or change to the BTC collector.

## Feed semantics and limits

Databento normalizes trade summaries into `T` records and order-level execution details into `F` records. A fill can also describe an aggressor that was already resting on the book. The engine therefore links only consecutive trade/fill groups with known opposite sides, matching prices and a known resting order ID; aggressor IDs are excluded. Trade and fill volumes are separate views of executions, never added together as market volume. Features become visible only when the instrument event completes at `F_LAST`. [Databento CME normalization](https://databento.com/docs/knowledge-base/datasets).

Fill-side `A` denotes a resting sell order and `B` a resting buy order; those meanings differ from the aggressor-side interpretation of a trade record. [Databento field definitions](https://databento.com/docs/standards-and-conventions/common-fields-enums-types).

Neither trades nor fills directly mutate the reconstructed book. Add, modify and cancel messages do that. [Databento order-state tutorial](https://databento.com/docs/examples/order-book/order-tracking).

In this pilot, a displayed decrease is linked to an execution only when an earlier matched fill in the same event supports its order ID, side, price and quantity. Remaining decreases are called *unlinked*, not proven cancellations: missing or unclassifiable execution detail must remain uncertain.

CME says native iceberg refreshes retain an order ID, whereas externally managed synthetic refreshes arrive as new orders. This permits useful distinctions but does not prove that every refill is hidden liquidity or that every new order shares an owner with an earlier order. [CME MBO explanation](https://www.cmegroup.com/articles/faqs/market-by-order-mbo.html).

## Fixed feature definitions

All fourteen added quantities are trailing five-second sums, with inclusive expiry, divided by current best bid plus best ask quantity. Bid-side and ask-side quantities remain separate.

| Quantity on each side | Definition |
| --- | --- |
| Passive execution | Matched passive fill volume; summed fills cannot exceed their trade summary |
| Held top-price execution | Passive volume at a best price that is unchanged between the preceding and current completed events |
| Linked displayed decrease | Cancel or same-price modify reduction attributable once to preceding matched fills in the same event |
| Unlinked displayed decrease | Remaining reduction, including price-changing modifications; not assumed to be cancelled or executed |
| Same-ID reload | A later addition/increase consuming earlier executed-decrease credit from that same ID |
| Other-ID reload | A later addition/increase consuming such credit from a different ID at the same best price |
| Same-ID net refresh candidate | After a matched fill and subsequent same-price modification, final display exceeds display-before-fill minus executed volume; capped at executed volume |

Reload matching uses oldest remaining credit first. Credit is consumed once, expires after five seconds, and is discarded when the completed best price changes. It cannot travel between sides, prices or sessions. New-ID reload does not identify synthetic icebergs. Same-ID net refresh is restricted to uninterrupted identity and price during the event, and can overlap explicit reload; the two quantities must not be added as hidden volume. Manual order-size increases can generate refresh candidates.

The five-second reload feature sums recent replenishment events; each can reference a decrease up to five seconds earlier. Its causal dependence can therefore reach back ten seconds. Rolling reload and rolling decrease sums need not conserve quantity within the same moving window; conservation is enforced across their full event history.

Temporal history resets on book resets, daily boundaries or completed-quote gaps greater than five seconds. Events spanning more than five seconds are excluded from these new measurements. Unknown aggressors, missing IDs and unmatched fill prices stay separately counted. The existing decoder, strict book, timestamp and quality gates are unchanged. Explicit bounds limit records per event, rolling event storage and outstanding credits.

## Frozen comparison budget

The pilot compares nine fixed directional scores: queue imbalance, CVD, depth imbalance, prior midpoint change, generic visible reload, passive execution flow, held-price passive support, same-ID refresh support and other-ID reload support. There is no sign reversal search, threshold optimization, training or outcome-based feature selection.

Controls use activity terciles calculated from eligible 7 July quote-count features, and the sign of the preceding five-second midpoint move. Directional AUC is reported within those activity/price groups as well as overall, with support counts. Group-weighted AUC requires at least twenty positive-outcome observations and both directions. These are coarse descriptive controls, not proof of independent predictive value. All three dates have already been examined and none is a fresh holdout.

Each score also gets a separate sign-only historical quote policy, retaining the original entry conditions, a single position, 15-second holding period and ten-second cooldown. Policies can select different entry schedules; their averages are not paired effects. Positive-outcome AUC conditions on hindsight knowledge and cannot be used as an entry filter. Neither quote returns nor order-book features account for cTrader EURUSD broker fills, spread, market impact or rejection.

## Completed pilot results

All 30,756 original decision rows, all original features and every 15-second outcome matched the earlier pinned artifact exactly. There were 22,984 eligible attempts and 19,011 resolved outcomes; 2,069 entries encountered a widened spread and 1,904 timed out. Those failures stayed visible, not relabeled as losses or no-trade examples. The replay read the same four UTC members, including Sunday reconstruction, without exposing additional dates.

Across the three research windows and their ten-second warmups, the observer processed 1,204,852 completed events. It linked 58,870 passive-fill records representing 116,546 contracts, or 99.11% of known-side trade-summary quantity. All of that matched passive volume was reconciled to displayed decreases. This percentage is matching coverage under the stated rules, not proof that every trade was classified.

The audit separately excluded 1,032 aggressor-fill records representing 2,362 contracts, and 680 unknown-aggressor fill records representing 1,332 contracts. It retained 2,326,470 contracts of unlinked displayed decreases. Treating all decreases as executions would therefore seriously misrepresent this sample. These quantities are overlapping views of order activity, not additive measures of total traded volume.

Of the matched passive volume, 48,998 contracts executed at an unchanged completed best price. Later other-ID replenishment consumed 15,342 contracts of executed-decrease credit. No same-ID explicit reload or same-ID net-refresh candidate was observed under this narrow protocol, including on ineligible decision rows. This does not establish the absence of native icebergs: other time periods, deeper levels, longer sequences or different refresh encodings are outside this detector's definition.

## Direction and costs

The AUC comparison uses the same 1,692 resolved outcomes with a hindsight-positive long or short direction. AUC near 0.5 indicates little ranking discrimination in this sample. The adjusted column compares within activity and prior-price-sign groups; it is not a causal effect estimate. Quote-policy means subtract crossed spread and one additional cost tick.

| Fixed signal | Directional AUC | Within-group AUC | Closed quote candidates | Mean net ticks |
| --- | --- | --- | --- | --- |
| Queue imbalance | 0.553 | 0.562 | 1,411 | -2.077 |
| CVD | 0.523 | 0.511 | 1,332 | -2.035 |
| Depth imbalance | 0.510 | 0.506 | 1,418 | -2.126 |
| Prior midpoint change | 0.510 | 0.496 | 1,253 | -2.168 |
| Generic visible reload | 0.506 | 0.499 | 1,402 | -2.125 |
| Matched passive flow | 0.522 | 0.510 | 1,332 | -2.033 |
| Held-price passive support | 0.498 | 0.497 | 1,271 | -2.193 |
| Same-ID refresh support | 0.500 from all ties | 0.500 from all ties | 0 | Not available |
| Other-ID reload support | 0.468 | 0.462 | 1,126 | -2.187 |

Every nonempty policy had negative mean net quote returns on each of the three individual days. A below-0.5 AUC was not used to reverse a signal after inspecting results. The untested inverted rule would need its own protocol; these observations do not validate it.

Matched passive-flow direction agreed with CVD on 99.74% of eligible decisions where both were nonzero. The passive-flow representation improves execution accounting, but its directional score is mostly another view of existing CVD here, not an independent source of predictive information. Held-price support and other-ID reload are different signals, but neither demonstrated profitable standalone performance. Same-ID features had no observed support, so their tie AUC is not model evidence.

## Development decision

Keep the execution-aware parser and audited feature definitions as research infrastructure. Do not promote these sign rules or train a model to treat replenishment as an automatic trade signal. Better mechanical labels have not yet produced a demonstrated directional edge.

The next historical phase should establish a dated-contract, multi-month cohort and an exposure ledger, then preregister a small sequence-confirmation comparison. That can distinguish replenishment followed by renewed pressure from replenishment followed by rejection, with separate longer-horizon and latency-aware exit tests. Preserve unused evaluation periods and do not use three exposed days to choose thresholds or model architecture. Training and platform connections remain deferred.

## Reproduction

Freeze the implementation and protocol before raw replay, then use new output paths:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.historical_6e_execution_study --prepare --registration logs/6e_execution_linked_20261001_1_registration.json
.\.venv\Scripts\python.exe -m ai_trader.research.historical_6e_execution_study --registration logs/6e_execution_linked_20261001_1_registration.json --rows-output data/processed/6e_execution_linked_20261001_1_rows.jsonl --report-output data/processed/6e_execution_linked_20261001_1_report.json
```

The replay verifies the pinned source members and original row artifact, exact original-feature and target equality, and quantity conservation before publishing. It refuses changed registrations and existing output paths. Licensed rows and generated evidence remain local, outside Git.

Completed local evidence SHA256 values:

- Registration: `3c2951b99f7bfe881cb895963fba5401dae27a64a3307118fc5a9b431bcc38be`.
- Rows: `206807287182ee7f9c3f9944a5e166795a41d8afdd4688c0ade26c4e7f7bc97d`.
- Report: `4024ae7e2e1109f77eed3100391940e7e98e5dfe6dbeafe5c3b014baa1c4bb0d`.

The 32 new focused tests cover passive versus aggressive fill roles, unknown linkage, quantity caps, one-use credit, same-ID uncertainty, event completion, price changes, stale history, storage bounds, post-window resets, original-target regression and evidence protection. A separate read-only check verified the published row hash, every two-sided cost target, feature finiteness, execution-volume bounds and full-history credit conservation.

Before development, the full suite passed 3,211 tests with one optional Nautilus skip. After development it passed 3,243 tests with the same skip in 213.11 seconds. Repository Ruff and changed-file formatting checks passed. Unrelated worktree changes were preserved.
