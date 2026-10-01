# Paired historical 6E horizons and observed price paths

This study compares short holding periods from identical entry attempts on three already-exposed development sessions. It extends the historical investigation, without training a model, connecting a platform or changing the BTC collector. Results are futures quote counterfactuals, not EURUSD broker fills or a promoted strategy.

## Fixed protocol

The cohort is 7–9 July 2025, contract 6EU5, from 12:00 inclusive to 16:00 exclusive UTC. The replay reads the preceding Sunday for reconstruction and the three complete daily source members. It verifies their compressed hashes, complete decoding, dated contract mapping, event completion and strict order-book transitions using the existing research engine. No additional months or untouched evaluation sessions are opened.

Original candidate timing and eligibility are unchanged: decisions are completed events at least one second apart, with a one-tick spread, five seconds of feature warmup, and decision time plus 17 seconds strictly before the window ends. Entry is the first completed quote at or after a 100 ms delay, with a one-second maximum wait and a one-tick entry spread. Every original row, all 23 features and every 15-second outcome must match the pinned earlier artifact exactly.

Each entered candidate gets outcomes at 1, 5, 15, 30 and 60 seconds after that same entry. The exit is the first completed quote at or after the scheduled horizon, before the window ends. Widened spreads and late exits are retained. Missing entries and unresolved exits remain unknown; they are not reclassified as losing trades or no-trade labels. Original eligibility is retained for regression, so longer horizons can be censored near 16:00.

Gross liquidation values use exit bid minus entry ask for longs and entry bid minus exit ask for shorts. The report subtracts 0, 1, 2 and 4 additional round-trip ticks as sensitivity assumptions. They are not measured broker fees. Two-sided positive-outcome frequency assumes the direction is known afterward and is therefore not a strategy win rate.

## Observed paths and barrier order

For each horizon, the study records maximum and minimum liquidation values from the entry quote through the scheduled deadline. A quote exactly at the deadline is included, but subsequent events with the same timestamp are not: the exit uses the first event. A late exit quote is priced separately and cannot create an earlier path extreme or target hit.

Symmetric gross thresholds of plus or minus 2 ticks and plus or minus 4 ticks record the first observed crossing for each direction, preserving event order. These are trigger diagnostics, not simulated stop/target fills. Overshoots are retained instead of assuming a fill exactly at the threshold. Maximum liquidation value may still be negative; it is not clamped to zero to hide the spread paid at entry.

Completed-quote gaps strictly greater than five seconds are flagged, including silence up to the scheduled path deadline. Exit inactivity also includes waiting for a late quote or waiting until the session window closes. Inactivity can conceal crossings; `none_observed` does not mean the continuous market path never crossed a barrier. Quiet activity cannot be distinguished from missing observations using that flag alone.

## Comparison and selection limits

The report discloses all attempts and censoring, a paired subset with all five horizons resolved, and a separate paired subset without late exits or inactivity. The latter two subsets depend on future observation availability, so neither can serve as a causal trading filter. It also thins eligible decisions to the first at least 60 seconds after the last selected decision, before inspecting outcome availability.

These entries overlap and are not a portfolio or independent statistical samples. Three previously examined sessions do not justify choosing an optimal horizon, stop or target. A larger historical cohort, a fixed causal direction rule, latency-aware barrier execution and untouched evaluation remain necessary before any profitability claim. Broker spread, basis, queue position, market impact, partial fills and rejected orders are outside this study.

## Completed replay and results

The full replay passed on all three sessions, processing 4,441,814 target-contract records across the four daily members and 1,204,186 completed quotes inside the three research windows. All 30,756 original decision rows, including features and 15-second outcomes, matched exactly. No source-quality gate was relaxed.

The retained quality evidence includes 64 completed-quote inactivity intervals and one timestamp-flagged closed-period clear accepted under the existing narrow exception. These are disclosed observations, not evidence that the local computer clock caused the historical gaps.

Of 22,984 eligible attempts, 19,011 entered, 2,069 encountered a widened entry spread and 1,904 lacked an entry quote within the permitted wait. Another 7,772 decisions were ineligible. The paired comparison below uses the same 18,969 entries at every horizon; the final column instead accounts for unresolved outcomes among all 19,011 entered candidates.

| Hold in seconds | Either direction positive after spread and one extra tick | Mean long net ticks | Mean short net ticks | Unresolved among all entered |
| --- | --- | --- | --- | --- |
| 1 | 0.14% | -2.074 | -2.076 | 0 |
| 5 | 1.68% | -2.118 | -2.107 | 0 |
| 15 | 8.92% | -2.107 | -2.132 | 0 |
| 30 | 19.46% | -2.100 | -2.140 | 17 |
| 60 | 31.99% | -2.096 | -2.150 | 42 |

The positive-outcome column grants hindsight knowledge of direction at the horizon; it does not imply that a model could select those entries or achieve those percentages as a win rate. Mean long and short values are unconditional candidate averages, not nonoverlapping strategy returns. Holding longer increased the frequency of sufficiently large moves on these dates, but did not create an unconditional directional edge.

The same pattern appeared on each individual day. One-second positive frequency ranged from 0.108% to 0.197%; five-second frequency from 0.93% to 2.46%; and 60-second frequency from 27.79% to 35.73%. This supports investigating the cost and movement constraint, not selecting a winning holding period from three exposed days. Even with zero additional cost beyond crossing the spread, the paired positive frequency was only 1.41% at one second and 8.26% at five seconds.

Late exits cannot be ignored: 1,849, 2,054, 2,119, 2,099 and 2,066 exits arrived more than one second after the scheduled 1, 5, 15, 30 and 60-second deadlines respectively. The paired no-gap/no-late subset contained 11,033 entries. Its corresponding positive frequencies were 0.18%, 2.30%, 11.21%, 23.34% and 35.51%. These cleaner observations still do not establish a deployable filter because availability is known afterward.

The causal 60-second thinning retained 699 eligible attempts, including entry failures. It yielded 573 resolved observations through 15 seconds and 572 at the longer horizons. Positive frequencies were 0.17%, 1.22%, 7.16%, 19.76% and 32.17%. This reduces overlapping decisions but does not turn the small cohort into independent evidence of profitability.

## What the paths add

For paired long candidates, the mean maximum observed gross liquidation value was -0.87 ticks at one second, -0.56 at five seconds, -0.05 at 15 seconds and +1.13 at 60 seconds. Mean minimum liquidation value changed from -1.21 ticks at one second to -3.27 at 60 seconds. Longer observation windows expose both more favorable and more adverse movement; the ability to choose a favorable exit afterward is not a causal exit rule.

With gross thresholds at plus or minus 2 ticks over 60 seconds, paired long paths first observed a target on 2,990 entries, a stop on 15,354, and neither on 625. Short paths were similar: 3,028 target first, 15,296 stop first and 645 neither. Every entry starts at a gross liquidation loss of one tick from the spread. Therefore these symmetric liquidation thresholds are not symmetric distances from the initial midpoint: reaching +2 requires three favorable ticks from initial liquidation, whereas reaching -2 needs one adverse tick. These counts do not include latency-aware exit fills and must not be presented as a stop strategy backtest.

With plus or minus 4 ticks over 60 seconds, long paths recorded 2,044 targets first, 6,913 stops first and 10,012 neither; short paths recorded 2,067, 6,881 and 10,021 respectively. Wider thresholds leave many paths unresolved at the barrier level. A later execution study must retain timeout exits, overshoots, latency and unavailable observations rather than calculating win rates only among convenient barrier hits.

## Development decision

Keep one-to-five-second market-crossing trades as an unproven, cost-constrained hypothesis, not the default training objective. This pilot does not rule out selective event-driven scalps, passive orders or different regimes. It does show why labeling many tiny moves as good trades would be misleading under the current cost assumptions.

The subsequent [execution-linked research pilot](EURUSD_EXECUTION_LINKED_RESEARCH_20261001.md) now separates passive fills, displayed decreases and replenishment while preserving all original outcomes. Its nine frozen sign comparisons did not establish a profitable edge. The next phase is a dated-contract, multi-month cohort and a preregistered sequence-confirmation study. A separate latency-aware barrier execution test can use the path infrastructure; no horizon or stop setting is promoted from this pilot.

## Reproduction

Freeze the code and protocol before opening the raw members. Both commands refuse existing evidence outputs; use distinct new names for a new experiment.

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.historical_6e_paths --prepare --registration logs/6e_paired_paths_20261001_1_registration.json
.\.venv\Scripts\python.exe -m ai_trader.research.historical_6e_paths --registration logs/6e_paired_paths_20261001_1_registration.json --rows-output data/processed/6e_paired_paths_20261001_1_rows.jsonl --summary-output data/processed/6e_paired_paths_20261001_1_report.json
```

The original microdepth configuration and row artifact are pinned. The registration also pins the implementation, horizons, barriers, costs, source dates and quote buffer bound. Final publication occurs only after the full cohort passes quality checks and the original 15-second regression. Licensed market rows and generated evidence remain local and outside Git.

Completed local evidence SHA256 values:

- Registration: `5f0886ce7dd727cc42ef8e084628c62eccec98d74807c33a2924625a0d2cd42c`.
- Rows: `cebf014ee4f93a7d0c70949f4ae0505efb265561b2f7ce47bf5b6a806f653c8f`.
- Report: `af3fafddf1b454e330e111c87c8a7d31969539410c74e6ba6a02f5dcd7eb6381`.

All 24 focused path tests passed, including same-timestamp event order, late-quote exclusion, cost arithmetic, censoring, entry failures, exact prior-feature regression, registration changes, overwrite refusal and bounded quote collection. A separate read-only check of all published rows verified the output hash, every liquidation identity, monotonic path extrema, persistent first crossings and the paired opportunity frequencies.

The complete suite passed 3,211 tests with one optional native Nautilus dependency skip in 209.98 seconds. Repository Ruff checks and changed-Python formatting checks passed. Unrelated worktree changes were preserved.
