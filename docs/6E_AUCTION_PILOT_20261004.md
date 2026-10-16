# 6E auction strategy pilot 20261004

## Decision

The research infrastructure improved, but this pilot did not establish a profitable strategy. Do not promote these rules, connect them to execution, or use their decisions as profitable Qwen training targets.

Two active defended-level hypotheses lost after the frozen quote-crossing and extra-cost assumptions. The failed-auction and accepted-breakout hypotheses never armed, so their economic performance remains untested. Their zero returns are abstention, not successful trading.

This was an offline development pilot on 12 fixed sessions, not validation of the complete historical archive or an independent holdout. No model training, network request, paper/live order, credential access, or BTC collector change occurred.

## What changed

Three separate modules were added without editing the frozen historical engines or existing trading policy:

- `six_e_auction_features.py` reconstructs 33 causal fields from completed MBO events: current bid/ask, prior 60-second price range, separate 5/15/30-second aggressor quantities and CVD, unknown-aggressor quantity, rolling executed price-level diagonal imbalance, and partial-segment trade VWAP.
- `six_e_auction_playbooks.py` implements mirrored, sequential hypotheses with frozen attack levels, distinct confirmation decisions, expiry, cooldown and quality resets. The four branches are failed auction, accepted breakout, defended hold and defended failure.
- `six_e_auction_study.py` freezes the protocol and source pins, replays the declared days, requires exact parity with every original decision row, writes feature-only sidecars, evaluates all declared policies, and independently recomputes the complete result.

Trade volume uses `T` records once; `F` records never add volume. Trades become available only at enclosing `F_LAST` completion. Earlier equal-time events remain in original native order. The prior range excludes the current completed quote. Unknown aggressors are not guessed. An event spanning over five seconds is refused.

The footprint is a rolling execution summary, not a closed footprint candle. VWAP starts with the first trade at or after 12 UTC in the current unbroken segment; it is not full-session fair value. Replenishment and held-passive credits remain proxies, not proof of hidden icebergs or institutional intent. Footprint and VWAP fields are now available for research but were not additional entry gates in this pilot.

## Coverage and frozen design

The protocol was registered before this pilot's replay and scoring. Days were selected by calendar, not their returns. Each decision window was 12:00–16:00 UTC; whole daily DBN members were consumed and their original hashes verified.

| Days in 2025 | Contract | Existing role | Sessions | Decision rows |
| --- | --- | --- | ---: | ---: |
| April 7, 8, 9 | 6EM5 | train | 3 | 38,401 |
| July 7, 8, 9 | 6EU5 | train | 3 | 30,756 |
| October 6, 7, 8 | 6EZ5 | validation development | 3 | 33,246 |
| December 8, 9, 10 | 6EH6 | test development | 3 | 27,003 |
| Total | Dated contracts | Exposed development | 12 | 129,406 |

Coverage is 48 decision hours and 6.056% of the original 2,136,770 accepted decision rows. This is not an analysis of all 196 accepted sessions with the new features. The 230 reserved inventory dates remained metadata-only.

All selected outcomes were already exposed in earlier research. The role names indicate exclusive chronological session groups; they do not confer independent validation. The fixed research roll changes to 6EH6 on December 8 and is not a guarantee of the most liquid contract at that time.

Calibration used all 26,187 original early-train causal cases across the 112 training sessions, including cases with unknown outcomes. Only feature projections entered the quantiles; targets did not:

- Initiation activity q90: 2.833213344056216, in original log known-trade count units.
- Absolute normalized 5-second CVD q90: 2.3125.
- Positive held-passive credit q90: 1.0436758893280675.
- Confirmation activity q70: 2.0794415416798357.

The exact values are authoritative in `thresholds.json`; the display values above must agree with that file. This is retrospective fold calibration, not an online-learning simulation for the early training dates.

Four candidate rules, eight same-event CVD/queue controls, the original burst-follow rule and idle were fixed in advance: 14 policies, without a parameter search or best-rule selection. Each family is evaluated separately, not combined into an optimized portfolio.

The execution comparator retains the original eligible entry, 100 ms minimum latency, 15-second quote exit, one-position lock and 10-second cooldown. Base costs cross entry/exit quotes and deduct one additional tick. The same closed selections are also recosted at two and four extra ticks. These are not measured commissions, broker fills, CFD returns, stop/target exits or account PnL.

## Verified results

Every one of the 129,406 reconstructed original rows matched its pinned predecessor exactly. The terminal verifier re-read all original selected rows and sidecars, regenerated every signal and metric, checked calibration and source/code pins, and confirmed all false-authority flags. There was no successful-subset completion.

| Policy | Detected events | Selected attempts | Closed quote outcomes | Closed net ticks | Mean ticks per closed outcome |
| --- | ---: | ---: | ---: | ---: | ---: |
| Failed auction | 0 | 0 | 0 | 0 | Not estimable |
| Accepted breakout | 0 | 0 | 0 | 0 | Not estimable |
| Defended hold | 20 | 16 | 14 | −21 | −1.5000 |
| Defended failure | 12 | 9 | 9 | −25 | −2.7778 |
| Original burst follow | 1,964 | 876 | 658 | −1,600 | −2.4316 |
| Idle | 0 | 0 | 0 | 0 | Not applicable |

Defended hold had two positive closed outcomes, six negative sessions, one positive session and five zero/no-closed sessions. Its two remaining selected attempts were rejected because the entry spread widened. Defended failure had one positive closed outcome and no positive session. Neither is supported by a large sample.

The hold rule produced only 20 signals in 48 hours, approximately 0.42 signals/hour. It does not meet the requested frequent-scalping objective. This one-second decision grid and 15-second holding test is not a low-latency HFT or market-making engine.

The CVD controls coincide with candidate directions by construction: confirmation requires the current CVD direction. Their identical results do not prove that price context adds an independent edge. The hold queue control closed 13 outcomes at −27 total ticks, averaging −2.0769; the failure queue control coincided with its candidate. The original burst comparison uses different event times and cannot identify a causal improvement.

At two/four additional cost ticks, closed totals were −35/−63 for defended hold, −34/−52 for defended failure, and −2,258/−3,574 for burst follow. No active declared policy had positive pooled closed returns at the base cost.

Chronological support remained weak:

| Existing role | Hold closed and mean ticks | Failure closed and mean ticks | Burst closed and mean ticks |
| --- | --- | --- | --- |
| Train | 8 / −1.3750 | 8 / −2.6250 | 564 / −2.4433 |
| Validation development | 6 / −1.6667 | 1 / −4.0000 | 87 / −2.3678 |
| Test development | 0 / not estimable | 0 / not estimable | 7 / −2.2857 |

The complete row inventory contains 70,111 resolved outcomes, 42,742 ineligible decisions, 11,101 widened-spread refusals and 5,452 entry-quote timeouts. These categories were retained; unknown or refused outcomes were not silently converted into zero-profit trades. Selected-policy attempt counts above are distinct from these whole-dataset counts.

## Why the range branches were not exercised

A post-completion feature-only support diagnostic found:

- 120,258 decisions had a ready prior range.
- 109,250 passed range readiness and the unknown count/quantity quality conditions.
- 1,982 met quality, the fixed 2–12 tick range-width gate and aligned burst conditions.
- Only 31 decisions were at least a full tick beyond either immediately preceding rolling range boundary, before other gates.
- Zero simultaneously met the direction-aligned one-tick crossing, range-width, burst and quality conditions needed to arm either range branch.

Observed conclusion: neither range family had initiation support under this exact definition. It is incorrect to claim the market contained no breakouts or that those trading concepts were disproved.

Design inference: quote-level rolling extrema can absorb a newly crossed price before the one-second sampled decision sees it. Dense event updates plus a current-price crossing gate create a representation mismatch. This is a reason to preserve crossing evidence when the completed native event occurs, not a reason to tune thresholds against the returned profits. The frozen pilot was not retuned or rerun.

## Next research gate

The next candidate should first fix event representation: detect a crossing at the completed quote, retain its pre-attack level and timestamp, and publish that causal evidence to the decision grid. An alternative fixed reference is an already-completed price range, rather than extrema continually updated up to the immediately preceding event. Feature-only support tests should demonstrate that real initiation events survive publication before a new protocol is frozen.

Then compare the corrected sequential rules with timing-matched ablations and realistic transaction costs. Do not enlarge this negative pilot merely to hunt for favorable sessions, label hindsight winners as executable trades, or train Qwen to reproduce these losing rules. Broader development coverage and an independently authorized untouched evaluation remain necessary before any promotion. EURUSD CFD execution economics require broker-specific evidence; 6E futures quotes alone cannot validate cTrader PnL.

Existing model adapters remain quarantined. `independent_holdout`, `promotion_allowed`, `trading_enabled`, `reserved_outcomes_opened`, and `model_training` are all false.

## Evidence and verification

Project root: `C:/Users/pabta/Projects/ai-trader`.

The registration is `logs/6e_auction_pilot_20261004_1_registration.json`. Completed evidence is in `data/processed/6e_auction_pilot_20261004_1`: twelve feature-only JSONL sidecars, twelve daily reports, frozen thresholds, request, progress journal, completion and verification. Feature sidecars total 286,166,868 bytes. No source captures were changed.

| Pin | SHA256 |
| --- | --- |
| Original manifest | `ba773292535c97402826e6b40b34d367379a2db899f0010d474628220f965c2b` |
| Pilot registration | `bcc1668b34db05b405cdc88e92be04be2f216e67806bcda8dd6a8e08640bf02d` |
| Implementation content digest | `ea167e26cfa4b8d7e9393c1b1eb00c68e7f11c4c658dacd4d04b913d04da2ec7` |
| Frozen thresholds | `e071972d50781e4e6f4a103fef7e45aebe77b55d48dc92dfbba9afaea2b810a1` |
| Complete result | `b9a0d347a251c58e8fa2c332cb63491dc5f8cd5e4dd461332350885e5b4337f0` |

Read-only verification from PowerShell, with no native replay, model call or trade:

```powershell
Set-Location C:\Users\pabta\Projects\ai-trader
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_auction_study verify --registration logs/6e_auction_pilot_20261004_1_registration.json --registration-sha256 bcc1668b34db05b405cdc88e92be04be2f216e67806bcda8dd6a8e08640bf02d --output data/processed/6e_auction_pilot_20261004_1
```

Expected status is `verified_development_pilot_not_validation`, with 12 sessions and 129,406 rows. A changed pin, sidecar, metric, source, implementation or failure marker is a refusal, not permission to repair/retry automatically.

Engineering checks: the pre-change full suite passed 4,212 tests with one optional Nautilus dependency skip; all 32 added tests passed. The final complete suite passed 4,244 tests with the same one optional dependency skip in 1,206.58 seconds. Repository-wide Ruff passed. Existing unrelated working-tree changes were preserved.
