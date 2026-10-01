# Historical 6E multi month research

The nine-session historical comparison stopped on a timestamp safeguard in its final October source file. No strategy report or partial dataset was published. The completed engineering work adds explicit dated contracts, a source-exposure ledger and protected calendar partitions; a separate timestamp-only investigation identifies the blocker below. Qwen training, broker connections, trading and the BTC collector remain unchanged.

## Exposure and reserved periods

The metadata audit reconciles the pinned March–April feature manifest and July microdepth report against the 471 daily members in the 18-month intake. It finds 29 sessions with examined outcomes and seven additional members replayed for reconstruction. The earlier five-day March–April pilot, subsequent scenario studies and failed July OFI pilot fall within those dates; they do not restore any holdout status.

The remaining 435 members have no replay documented by this evidence inventory. That is not a guarantee that nobody has inspected them. Archive checksum reads and header inspection during the original intake are distinct from order-book reconstruction and outcome analysis. Future evaluation must reconcile any additional access history before calling a period untouched.

| Calendar period | Assigned role | Daily members | Access in this protocol |
| --- | --- | ---: | --- |
| 26 March through December 2025 | Development | 241 | Only the twelve explicitly registered members |
| January through March 2026 | Reserved validation | 77 | Metadata only |
| April through June 2026 | Reserved test | 78 | Metadata only |
| July through 25 September 2026 | Reserved final evaluation | 75 | Metadata only |

These are UTC file counts, not complete exchange-session counts or guarantees of usable data. Seven vendor-degraded members remain flagged in the inventory. None belongs to the selected comparison. The new runner refuses reserved dates before opening market files, including a preceding reconstruction day that would cross a partition boundary. Different contracts cannot move the same source date into a different partition.

## Fixed comparison

| Development block | Contract | Decision dates in 2025 | Additional reconstruction member |
| --- | --- | --- | --- |
| April | 6EM5 | 7, 8 and 9 April | 6 April |
| July | 6EU5 | 7, 8 and 9 July | 6 July |
| October | 6EZ5 | 6, 7 and 8 October | 5 October |

All decisions use the existing 12:00–16:00 UTC window. April and July were previously exposed; October is explicitly development data, not an independent test. The dates are a small calendar sample, not all months or all market conditions. There is no selection by realized profit or a search for a favorable contract.

The nine directional rules and their signs are unchanged: queue imbalance, CVD, depth imbalance, prior midpoint change, generic reload, matched passive flow, held-price support, same-ID refresh support and other-ID reload support. Each retains the 100 ms entry latency, one-second quote wait, 15-second holding period, crossed spread plus one additional cost tick, one-position quote policy and ten-second cooldown. The engine retains rejected entries and unresolved exits. There is no fitted predictive model, threshold optimization, sign reversal or automatic winner selection.

Activity terciles come only from eligible 7 April feature values and are reused for every block. Price controls use the sign of the preceding five-second midpoint change. These descriptive controls do not establish causality. Directional AUC conditions on hindsight-positive outcomes and is not a deployable entry filter. The first day's full-feature terciles are descriptive strata, not an intraday online calibration claim.

Each block starts a separate engine with an explicit contract, rather than inheriting the old hardcoded 6EU5 selection. Every daily DBN header must resolve that contract to exactly one valid instrument. The engine preserves the existing book, event-completion, timestamp, execution-credit and target checks. Reported mappings use the actual selected contract. State does not carry between blocks or daily feature windows.

This is not a continuous futures series: there is no automatic roll, back adjustment, price splicing, volume-based contract selection or assertion that the contract was the most liquid at every instant. It also does not implement a full exchange holiday calendar. Missing, degraded, empty or insufficiently covered dates stop the entire comparison; the runner cannot replace them with better-looking sessions.

## Evidence protection

Preparation reads bounded pinned metadata and archive file sizes, not raw market members. The registration freezes the protocol, exposure inventory, selected source hashes and implementation hashes. Execution requires its raw-file SHA256 pin and new output paths. A persistent attempt record conservatively marks every planned member exposed before raw access, so interruption cannot make a partially inspected cohort appear untouched.

One attempt is allowed for a registration path. A failure retains its block and error, publishes no successful-subset dataset and triggers no retry. Do not copy or rename a registration to evade that policy. A future protocol must account for the retained attempt, including dates conservatively marked exposed. The frozen initial ledger is a snapshot; it does not silently rewrite itself after a run.

The comparison permits at most 130,000 rows and 300 MiB of serialized output. Source decoding retains the existing per-member decompression bounds and compressed-member hashes. July must reproduce every original feature, execution feature and 15-second outcome exactly before any final rows or results are published.

## Completed attempt and timestamp diagnosis

The single registered attempt passed the April and July block replay checks, then refused `6EZ5` on 8 October 2025 because a non-snapshot exchange timestamp exceeded its receive timestamp. The engine validates the entire selected UTC member, including records after the research window. The whole comparison remains failed. Its exact-July regression and final publication checks were not reached, so this attempt does not establish those results on real data.

A separate timestamp-only diagnostic read that one member to EOF and verified its compressed SHA256. It did not reconstruct a book, calculate features or labels, rerun a strategy, change the file or alter the quality gate. It examined 2,093,517 target-contract records, including 3,208 snapshots excluded from timestamp comparison.

| Timing finding among non-snapshot target records | Result |
| --- | ---: |
| Exchange timestamp later than receive timestamp | 1,451 records |
| Inside the 12:00–16:00 UTC decision window | 0 |
| Affected receive-time minutes | 23:00–23:04 UTC |
| Smallest exchange-minus-receive discrepancy | 1.016392 ms |
| Largest discrepancy | 247.040417 ms |
| Regressing receive timestamps | 0 |
| Receive timestamps outside the source UTC date | 0 |
| Non-snapshot bad-receive or maybe-bad-book flags | 0 |
| Exchange events later than publisher sending time | 0 |

All 1,451 affected records also have negative publisher-send-to-receive deltas. Counts are records, not distinct trades or independent events. The issue is embedded in the historical dataset and is unrelated to this computer's current clock.

Databento preserves publisher event timestamps without adjustment, warns that publisher and capture clocks need not share synchronization, and uses receive time as the index when available. Negative sending-to-receive deltas are explicitly possible. Thus our strict cross-clock inequality is a research policy, not a guaranteed vendor invariant. The documentation does not identify the cause of this particular incident or prove that its data is suitable for latency research. [Databento timestamp definitions](https://databento.com/docs/standards-and-conventions/common-fields-enums-types).

The next engineering step is a separately versioned receive-time causality and clock-quality policy. It must distinguish nonmonotonic arrival time, bad source flags and invalid book transitions from disagreement between independent clocks; retain original timestamps and anomaly counts; and predefine how anomalies inside versus outside decision windows affect eligibility. Do not select a tolerance from profitable outcomes, reorder by exchange time, delete offending records or revive this failed registration. Regression against the existing exposed cohorts is still required before another comparison. No conclusion about the nine rules' multi-month profitability is available from this attempt.

## Local evidence

Prepared registration: `logs/6e_multimonth_development_20261001_1_registration.json`.

Registration SHA256: `4e3e264edf09b5a4717e8034108c21dad5f4c8ed6070bb56e8740cee855bb25f`.

The retained attempt sidecar marks all twelve planned members conservatively exposed, including the four October members not in the original positive-access inventory. Future research must include that sidecar rather than relying only on the initial ledger.

- Attempt sidecar SHA256: `212221bc8390dd8f4afcb4335a57e1ad9eb31005ab6dac52dd96beb54d7de64b`.
- Failure sidecar SHA256: `12f2b6357b83480ed3438173c89585453fe45d036ff5d261abf420e30011f977`.
- Timestamp diagnostic: `data/processed/6e_multimonth_development_20261001_1_clock_diagnostic.json`.
- Timestamp diagnostic SHA256: `a80a58b1e1c4b198492329b43abf074f5d8d0cb67a821ccf1083454a644b7eef`.
- Verified 8 October source-member SHA256: `a1e5756169bfe6a579a82c250e0aa1fada72e062654dee4d731562eb56b00d77`.

The 35 new cohort tests cover calendar boundaries, reserved-source refusal, overlapping reconstruction files, explicit dated mappings, daily and contract-state isolation, metadata drift, original-July regression, whole-cohort publication and retained failures at each block. Six additional diagnostic tests cover timestamp signs, window boundaries, snapshots, receive regressions, bounded samples and evidence preservation. The repository Ruff check and changed-file format checks passed. The final complete suite passed **3,284 tests with one optional Nautilus skip** in 217.35 seconds, compared with 3,243 passing tests before this work. An independent read-only check also reconciled the diagnostic's action, flag and minute counters and sample timestamp arithmetic.

## Research boundary

Even positive futures quote results would not validate a cTrader EURUSD strategy. The data does not establish broker spreads, fills, commissions, slippage, rejection or the futures-to-spot basis. No trading policy can be promoted from this development comparison. A later sequence-confirmation hypothesis must be specified separately and evaluated with the reserved periods protected during design.

See the [preceding execution study](EURUSD_EXECUTION_LINKED_RESEARCH_20261001.md) for feature definitions, the prior negative policy results and feed interpretation limits.
