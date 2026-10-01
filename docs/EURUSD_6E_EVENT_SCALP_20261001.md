# EURUSD event triggered scalp evaluation

Result on 2026-10-01: **reject this OFI and queue entry rule for strategy promotion.** The event-triggered replay completed all five frozen sessions, but the primary rule lost an average 1.01 ticks per evaluation round trip after crossing the spread, before any additional fees or slippage. It generated hundreds of short trades, not a demonstrated profitable edge. No model was trained, no paper or live orders were placed, and the BTC collector was untouched.

This is a separate experiment from the [stopped fixed-grid OFI study](EURUSD_6E_OFI_SCALP_20261001.md). That study's 70% availability gate and failed result remain unchanged. Event sampling asks a different question and must not be described as repairing the old study into a passing result.

## Protocol frozen before outcomes

The [registered configuration](../configs/databento_6e_event_scalp_v1.json) uses dated CME 6EU5 MBO records for July 7–11, 2025. July 7–8 are development sessions; July 9–11 are the evaluation partition. Only July 7 quote availability had previously been inspected. No thresholds, features or execution rules were fitted or changed between these partitions, and there was one outcome replay. All five dates are now exposed research data, not reusable untouched holdouts.

The [replay](../src/ai_trader/research/databento_6e_event_scalp.py) reconstructs the full target-contract order book and observes it at completed `F_LAST` events. During 12:00–16:00 UTC, the first completed event at least one second after the previous decision triggers the next decision. It never invents observations between events, and an unfinished event cannot trigger a decision. The just-completed event is available to the signal; the first simulated entry opportunity is at least 100 ms later. Equal-timestamp later events cannot change an already-recorded decision.

Features are the same five-second best-book order-flow imbalance (OFI) and queue-weighted midpoint proxy as the prior hypothesis. The primary rule requires a one-tick spread, normalized OFI magnitude at least one, midpoint offset at least 0.15 tick, and matching signs. The independent control omits only the OFI requirement. Queue-weighted midpoint is algebraically tied to queue imbalance; it is not a second independent signal or a trained microprice model.

Both strategies keep one primary position at a time, select at most once per contiguous direction episode observed at decision times, hold for 15 seconds, and wait ten seconds after resolution. Entries expire strictly after the latency target plus one second, even without a new quote. The 500 ms and 1,000 ms variants reprice the primary selection schedule and are not independent portfolios. Selection stops in the final 17 seconds to leave room for the slowest entry, its quote wait and the hold.

Longs enter at the observed ask and exit at the later bid; shorts reverse those sides. A late or widened exit is retained at its observed price, not discarded. Any unresolved exposure stays explicit at the window end. Extra round-trip costs of 0, 1, 2 and 4 ticks are assumptions; the primary extra-cost setting is one tick, not a measured cTrader commission. Prices alone do not establish fills, executable size or market impact.

## Inactivity and data integrity

Strictly more than five seconds without a completed target quote resets the OFI history and requires another five seconds of observation before a signal can pass. Entries already waiting expire on their own deadline. Entered positions stay open in the accounting, receive an inactivity-exposure flag, and close at the first qualifying later quote. Boundary silence is recorded too. The timer identifies target-contract inactivity, not its cause: quiet trading and upstream data loss cannot be distinguished from these observations alone.

The six compressed UTC members, July 6–11, passed their pinned reads and full decode. Dated symbol mappings, timestamps, quality flags and book reconstruction were checked; unfinished non-trade events now also fail at a reset or member end. Archive size/mtime and implementation hashes remained unchanged through replay. A hard source or reconstruction failure would reject the whole run without publishing a subset.

The replay processed 7,268,018 target-contract records. Each strategy observed 51,642 rate-limited decision events, producing 103,284 rows across both strategies. Inactivity intervals numbered 28, 9, 27, 9 and 12 on the five respective days. These are observability warnings retained in the result, not a claim of verified feed outages or a reason to delete inconvenient returns.

## Primary quote results

Every number below concerns 100 ms entry delay and a four-hour window, not a full trading day or a broker account. Gross ticks already include crossing the bid/ask spread; the last column additionally subtracts one assumed tick per closed round trip.

| Session | Role | Selected episodes | Closed round trips | Mean gross ticks | Mean after extra cost |
| --- | --- | ---: | ---: | ---: | ---: |
| July 7 | Development | 409 | 338 | −0.879 | −1.879 |
| July 8 | Development | 429 | 357 | −1.109 | −2.109 |
| July 9 | Evaluation | 429 | 332 | −0.976 | −1.976 |
| July 10 | Evaluation | 420 | 344 | −1.113 | −2.113 |
| July 11 | Evaluation | 420 | 351 | −0.940 | −1.940 |
| Evaluation total | Evaluation | 1,269 | 1,027 | −1.010 | −2.010 |

The evaluation mean holding time was 15.42 seconds, with about 342 closed round trips per four-hour window. Of the 1,027 closed outcomes, 156 were positive gross (15.2%) and 69 remained positive after one extra tick (6.7%). The remaining 242 selections never entered: 74 expired and 168 encountered a widened entry spread. All entered positions resolved, including 120 late exits and 18 primary positions exposed to inactivity. Those 18 were retained, not filtered out.

The independent queue-only control closed 1,321 evaluation round trips, with mean gross −1.069 ticks and mean after one extra tick −2.069 ticks. The portfolios selected different episodes, so this is not a paired estimate of OFI's incremental value. Both failed the cost-aware gate. The frozen primary gate also required at least 100 evaluation closures and at least 20 per evaluation day, positive mean after the extra tick both pooled and on every evaluation day, and no unresolved or inactivity-exposed evaluation positions across either strategy or latency. Even meeting those conditions would only require further replication and broker validation, never automatic promotion.

An independent decomposition found a mean signed midpoint move of +0.111 tick against an average round-trip spread burden of 1.120 ticks. A small favorable midpoint movement was insufficient to pay for crossing the market. Long and short evaluation means were both negative. On the 723 primary selections that resolved at all three tested entry delays, gross means were −1.040, −1.058 and −1.066 ticks at 100, 500 and 1,000 ms respectively. The unpaired sensitivity reports have different entry-veto sets; do not rank delays by their unpaired means.

## Reproducible evidence

The ignored local outputs are `data/processed/databento_6e_event_scalp_v1_rows.jsonl` and `data/processed/databento_6e_event_scalp_v1_summary.json`. The summary retains every source-member pin, dated mapping and implementation fingerprint, separate development/evaluation statistics, all daily results and inactivity intervals. Licensed raw records were not added to Git.

| Raw byte evidence | SHA256 |
| --- | --- |
| Frozen configuration | `f4c17bb5f2c494d10be7df748e4b022e7ac13ab3805485292f54afc3e189a08f` |
| Existing archive intake report | `de12f9833b951781f27b5ea46d2c6dc2302c422e1080bfc48914b2dc8a82b27a` |
| Event replay implementation | `48bd0402c2e8a7c0d8d286b8956a2f55059c71df81dc1115ee15d8adce560b3e` |
| Output rows | `214de7fa32aa1b1aac99f873987e8bfca447df44f51b9d231a4771509fc0ad1a` |
| Output summary | `b2a84de5b3deba3303fca5d396c57ac3857ab4b24c95a00961389fbbe88b1121` |

A separate read-only audit recomputed all split/latency counts and means from the published rows. It checked the one-second decision limit, one selection per episode, primary nonoverlap and cooldown, feature identities, latency and hold boundaries, crossed-quote returns, cost arithmetic, inactivity flags against timer intervals, and source-code/output hashes. All checks passed. This is independent output arithmetic, not an independent reimplementation of the raw-data decoder.

Verification: all 88 related research tests passed. The final complete workspace suite reported 3,027 passed and one skipped in 202.09 seconds; the skip is the optional native Nautilus evaluation dependency. Ruff lint and formatting for the changed Python files passed. Existing unrelated worktree changes were preserved.

Reproduction uses the project virtual environment and the existing pinned local archives:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.databento_6e_event_scalp --config configs/databento_6e_event_scalp_v1.json --rows-output data/processed/event_scalp_reproduction_rows.jsonl --summary-output data/processed/event_scalp_reproduction_summary.json
```

Both output paths must be new; the runner refuses overwrites. It does not download data, call a model or import an order gateway. Repeating the same days is a reproducibility check, not new validation.

## Next strategy development step

Retain the event clock and explicit position accounting, but keep this entry policy disabled. The evidence does not support adding more trades by loosening its thresholds or learning only from hindsight-selected winners.

Follow-up: the [cost-aware target pipeline and selective baseline](EURUSD_6E_COST_BASELINE_20261001.md) have now been implemented and trained. They use all causally eligible event decisions, including losses and no-trade targets, with whole-session train/validation/test separation. The baseline abstained on validation and test and remains unqualified for trading. Richer flow, replenishment and absorption features should be tested as separately recorded hypotheses rather than repeatedly optimizing these exposed days.

Before EUR/USD spot/CFD paper execution, collect synchronized cTrader broker quotes and validate broker-specific spread, latency and charges. CME futures evidence is an additional signal source, not a substitute for that execution evidence. Qwen can later review research and outcomes outside the fast entry loop; these failed entries must not be presented to it as a proven profitable playbook.
