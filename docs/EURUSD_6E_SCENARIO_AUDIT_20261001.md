# EUR/USD 6E historical breakout and reclaim audit

Status, 2026-10-01: **the tested minute-level break and reclaim rules are not suitable for promotion.** A bounded, read-only replay of 6E futures order-book data produced 2,400 decision minutes across eight training and two development-validation trading days. Every tested rule had a negative average 60-second crossed-futures-quote change on validation, before fees and slippage. These are historical counterfactuals, not paper fills, broker EUR/USD results, or evidence that a different playbook will work.

## Data boundary and replay quality

The local Databento archive inventory has **471 UTC daily MBO files** across the roughly 18-month request, occupying 17.93 GB in three ZIP archives. The intake marks seven delivered daily files degraded and explicitly says `training_ready: false`: for the full archive it checked manifests and DBN headers, **not** all event streams or every dated 6E contract. Volume of files is not proof of a clean training set.

The [versioned scenario replay](../src/ai_trader/research/databento_6e_scenario_replay.py) used the original frozen 6EM5 configuration (SHA256 `927607008b24877f24c961da1aafc1bc151e0d4b8253a1627bd51699e48fb144`) but selected only its eight training sessions and the first two validation sessions, March 27 through April 9, 2025. It verified 13 pinned UTC MBO members and replayed 36,251,965 target-contract records. The April 10 UTC file was deliberately excluded: its evening records would enter the original April 11 test session. No original test source file was selected. The third original validation day was omitted from this bounded pass, not declared a new holdout.

Each included trading day supplied all 30 warmup minutes and 240 decision minutes. Book updates were checked at complete `F_LAST` events, and an unexpected book clear inside the observation window would abort the study. Of 2,400 decisions, 2,390 had a valid quote at least 60 seconds later inside the window; the final minute of each day was censored. The original supplied-archive manifest is not an independent vendor authentication, and the rest of the 18-month archive has not passed this event-level audit. [Databento documents why `F_LAST` is required for a valid reconstructed quote](https://databento.com/docs/venues-and-datasets).

The ignored local evidence files are `data/processed/databento_6e_dev_scenarios_v2_rows.jsonl` (raw SHA256 `43fd34f76a3134ee19900b915f2eb96938398ac1248a472fe77ee01d0292b92b`) and `data/processed/databento_6e_dev_scenarios_v2_summary.json` (raw SHA256 `73d971e2f9762cb715783b8c892afdab72bfe42dcf4a17a6441d47caf8ba7b5a`). The result is reproducible from the frozen config, local archives and [pinned decoder dependencies](../requirements/databento-6e-research.txt); it made no network request, model call, order, or paper trade.

## Candidate definitions and observed results

The exploratory rules used a high or low from the **30 completed prior one-minute midpoint observations**, never the current minute's future path. An initial break required at least one full tick beyond that range. A failed break was a return through the *frozen original boundary* within five later minutes. These are unconfirmed initial breaks and reclaims; the study did **not** test accepted-break persistence, absorption, stop-run intent, iceberg identity, stops or targets.

The table shows number of signals and mean 60-second **gross crossed-futures-quote ticks**. For a long, that is later bid minus entry ask; for a short, entry bid minus later ask. Negative values are adverse even before commission, slippage, latency and fills.

| Causal minute setup | Training signals | Training mean ticks | Validation signals | Validation mean ticks |
| --- | ---: | ---: | ---: | ---: |
| Initial break up | 73 | −1.01 | 22 | −3.18 |
| Initial break down | 61 | −2.48 | 19 | −3.16 |
| Failed up break, short | 31 | −0.06 | 16 | −3.50 |
| Failed down break, long | 36 | −1.58 | 12 | −3.17 |

Together the four rules emitted 69 validation candidate rows, with 19 showing a positive gross crossed-quote change and a weighted mean of about **−3.25 ticks**. The remaining 2,130 of 2,400 decision minutes emitted `no_trade`. Every failed-break row is a later stage of a recorded initial-break episode, so the 270 candidate rows are **not 270 independent, executable trades**. Outcomes from nearby minutes also overlap. There are only two included validation days, and they had already been used for development of the earlier baseline. The table cannot be treated as an independent profitability estimate.

## What reverse engineering showed

A training example on April 7 illustrates both the appeal and the trap of outcome-first selection. At 14:10 UTC, an initial down-break had five-minute known-side CVD of −257 and a one-minute gross crossed-quote change of **−38 ticks**. One minute later, a fast reclaim was observed with CVD +181; its corresponding long counterfactual gained **+21 gross ticks** over the next minute. This is a real historical sequence in the bounded registry, but choosing only that rebound would ignore the other failed-break signals. Across training, book-imbalance alignment and CVD alignment both still had negative mean gross crossed-quote changes; the validation averages for both reclaim directions were negative.

The practical change to our strategy is therefore **abstention** on these simple signals, not a narrower threshold fitted to this small sample. A superficially positive training subset of 26 CVD-aligned failed breaks averaged +1.08 ticks, but its median was −0.5, only 10 were positive, and removing its three largest winners turned the mean negative. Its 20 validation rows averaged −3.65 ticks. CVD sign is a diagnostic for the next study, **not a learned entry gate**. The saved first-model rows lacked price paths and quote exits, which is why a one-tick directional hit rate was misleading. The raw replay adds causal levels, trigger times, quote sides, frozen reclaim boundaries and later outcomes, but still samples only one decision per minute. It cannot establish subsecond absorption, real iceberg fills, cTrader execution or positive expected value.

## Next validation gate

The next single primary hypothesis should be registered **before opening additional outcomes**: an accepted break, with the original 30-minute level frozen at the first break, followed by two clean one-minute decisions at least one tick beyond that level and no intervening re-entry. Enter the counterfactual only at the second confirmation quote, at most once per break episode. Use a five-minute crossed-quote outcome as primary, one minute as secondary, censor the last five minutes, and compare with a same-time level-only control. Record rejected opportunities and `no_trade` reasons, and predeclare quote-quality, spread and volatility vetoes. Log CVD and top-book imbalance as diagnostics without tuning gates on this exposed cohort.

An absorption/replenishment playbook remains a separate, untested hypothesis; the minute-sampled replay cannot validate it. Replay a fresh, dated outright-contract cohort only after its symbol mapping, roll rule, exchange calendar and member quality are verified. The metadata-complete July and October 2025 windows are candidates, not validated samples; a later reserved window must remain untouched through rule selection. Report gross and cost-sensitive outcomes with session-block uncertainty, including the number of episodes and abstentions, not just a pooled hit rate.

The futures crossed-quote calculation is an optimistic gross proxy for hypothetical futures market orders, not a bound on cTrader results. Broker EUR/USD bid/ask alignment, commissions, spread behavior, slippage, latency and financing are needed before a CFD backtest or paper strategy claim. Keep Qwen training and model-controlled trading off until a simpler, cost-aware policy beats controls on fresh whole-session validation.
