# EURUSD development census review — 2 October 2026

The completed census has now been reviewed across all published development dates. Prior quote activity is associated with the presence of a cost-positive 15-second direction; queue imbalance has a weaker association with the better direction. The two observations support testing an activity gate followed by a separate directional model. They do not establish profitable entries or justify deploying or fine-tuning Qwen on hindsight winners alone.

## Verified coverage

The review reconciles the pinned registration, completion receipt and append journal for all 471 inventory dates. It verifies 221 daily reports, 442 row/case artifact hashes, 238 attempted-date records and all 17 retained refusal records. It loads and validates the 45,584 published cases, reproduces daily case associations and horizon summaries, checks the source-session window and original target arithmetic, and retains unavailable targets. The 2,123,320 full decision rows are hash-verified; the deeper association analysis uses the causally thinned cases rather than parsing or fitting every decision row.

| Census result | Dates | Interpretation |
| --- | ---: | --- |
| Weekday decision replay accepted | 195 | Decisions from 12:00–16:00 UTC; complete source member decoded by the census |
| Sunday reconstruction accepted | 26 | No decision-window rows or movement cases |
| Refused during replay | 17 | Evidence retained; no automatic retry |
| Vendor-degraded development member | 3 | No replay |
| Reserved 2026 member | 230 | Metadata accounting only; no outcome artifacts opened |

The accepted files published 4,234,083,875 bytes of reports and row/case artifacts. File-date coverage includes every inventory member, but all-hours research remains unfinished. Refused dates are not counted as analyzed decision windows. The accepted subset cannot establish aggregate strategy performance or authorize model promotion.

## What caused the refusals

Fourteen refusals have the message `Target MBO has a bad timestamp or quality flag`; all are Sunday reconstruction dates. The strict source checks cover `F_BAD_TS_RECV`, `F_MAYBE_BAD_BOOK`, `F_TOB` and `F_MBP`, with the pre-existing narrow snapshot and closed-period-clear exceptions. The retained message does not identify the triggering record or flag. It is evidence of a source-quality refusal, not enough to diagnose an exchange or vendor error. November and December have particularly many of these refusals. Future diagnostics should record the exact flag, action, snapshot state and time before considering any change to the acceptance policy.

The 4 April refusal is a resource limit: the completed quote buffer exceeded two million quotes. It is not proof of bad market data. This busy date must remain visible because excluding it could affect an activity-based hypothesis. A separate implementation should retain bounded recent quotes and compute pending paths as events arrive, with exact parity tests on already accepted dates before a separately registered 4 April attempt. The original census and its resource bounds remain historical evidence.

The 18 April and 25 December refusals report missing or excessive decision counts. The engine raises this message for an empty decision window or more than 14,400 decisions; the retained failure does not distinguish those cases. The dates suggest holiday closures, but that classification requires an instrument-specific historical calendar and a diagnostic count. CME identifies 18 April 2025 as Good Friday in its [official advisory](https://www.cmegroup.com/tools-information/holiday-calendar/files/2025/2025-good-friday-clearing-advisory.pdf). That advisory does not itself prove the 6E window was closed. A future calendar-aware census should represent confirmed scheduled closures explicitly rather than fabricating training rows.

No source quality checks were relaxed and no refused date was replayed by this review.

## Short-horizon movement room

The following figures count whether **either** direction would have a positive crossed-quote outcome after one additional cost tick at the scheduled horizon. They use the same causally selected entries and preserve each horizon's missing outcomes. Spread is already included in the crossed quotes. These are hindsight opportunity frequencies, not predicted directions, trade win rates, stop/target fills or a trading portfolio.

| Horizon | Resolved cases | Either direction positive after one extra tick | Fraction of resolved cases |
| --- | ---: | ---: | ---: |
| 1 second | 37,724 | 194 | 0.514% |
| 5 seconds | 37,724 | 1,566 | 4.151% |
| 15 seconds | 37,724 | 5,381 | 14.264% |
| 30 seconds | 37,685 | 9,955 | 26.416% |
| 60 seconds | 37,608 | 15,381 | 40.898% |

There are 7,860 unavailable outcomes at 15 seconds. Of the resolved cases, 3,310 have late exits; gaps are counted separately. The future-clean subset contains 34,145 resolved 15-second cases and 5,270 positive-direction cases. That subset is an availability diagnostic, not a causal entry filter.

At 15 seconds, increasing the additional cost from one to two ticks reduces the hindsight opportunity count from 5,381 to 2,612; four extra ticks leaves 725. These assumptions do not estimate cTrader costs. Broker EUR/USD quotes, basis differences, commissions and execution must be measured separately.

The one-second sample leaves very little room after the stated costs. More trades alone is not a useful objective. Fifteen seconds is retained as the existing research target; the larger 30/60-second hindsight counts are descriptive and were not used to select a new holding period.

## Regime variation

| Month | Resolved 15-second cases | Positive hindsight direction | Fraction |
| --- | ---: | ---: | ---: |
| March, partial | 832 | 131 | 15.75% |
| April | 3,697 | 1,109 | 30.00% |
| May | 4,275 | 800 | 18.71% |
| June | 3,976 | 642 | 16.15% |
| July | 4,429 | 630 | 14.22% |
| August | 4,089 | 622 | 15.21% |
| September | 3,745 | 485 | 12.95% |
| October | 4,750 | 475 | 10.00% |
| November | 3,804 | 246 | 6.47% |
| December | 4,127 | 241 | 5.84% |

The opportunity rate changes substantially over the development period. That does not identify the cause: activity, volatility, calendar effects and the declared quarterly contract changes can confound the comparison. It does show why April-only examples cannot represent the later months.

## Separate activity from direction

Daily AUCs preserve the original feature sign and use equal date weights. A daily comparison enters the descriptive summary only if both classes contain at least five cases. No feature sign is reversed to improve its score, and no entry threshold is fitted. The 37 feature comparisons are exploratory and not corrected for multiple testing.

| Pre-entry feature and question | Supported dates | Median daily AUC | 10th–90th percentile | Dates above 0.5 |
| --- | ---: | ---: | --- | ---: |
| Quote activity: any positive 15-second direction? | 188 | 0.5902 | 0.5140–0.7013 | 177 |
| Queue imbalance: long better than short? | 195 | 0.5465 | 0.4783–0.6136 | 155 |
| Signed CVD: long better than short? | 195 | 0.5001 | 0.4377–0.5564 | 98 |

Quote activity's monthly median opportunity AUC ranges from approximately 0.559 to 0.638, but its median directional AUC is 0.5007. An activity filter cannot supply the missing directional decision. Queue imbalance's monthly median directional AUC remains above 0.5 in this sample, although some individual dates reverse and the overall association is modest. The directional target includes entries where both directions lose; a better direction is not necessarily a profitable direction. Exact direction ties are excluded and reported.

Signed five-second CVD alone has little directional association here. This does not test CVD changes over longer windows, its magnitude, divergence, or interactions with replenishment and held-price executions. Those remain hypotheses requiring separately recorded feature definitions and comparisons.

The feature support review also matters for the planned iceberg logic. Across the 45,584 sampled decisions, bid same-ID reload is nonzero zero times, ask same-ID reload only three times, and both same-ID net-refresh quantities are always zero. By contrast, other-ID reload is nonzero in 13,854 bid and 14,040 ask cases. The existing conservative same-ID quantities offer almost no training variation in this sample. These counts do not establish how many actual icebergs existed or prove a broken detector; the raw event semantics and matching assumptions need a dedicated audit before changing the detector or naming a training label “iceberg.”

## Next experiment selected

The next development model should separate an activity/volatility gate from direction and net-return estimation. Keep the 15-second target and the existing cost-aware abstention threshold; compare with no-trade, CVD-only and queue-imbalance controls. Add a causal sequence comparison only after its feature construction and session boundaries have been tested. Fit scalers, thresholds and parameters only in a declared early development period, and report each later development month separately. All 2025 outcomes are already exposed; none of these comparisons is independent validation.

Before that model fit, the quote-bound date and suspected holiday windows need a recorded disposition. Publish a new training manifest with whole source-session roles, the full date coverage ledger, unavailable-label accounting and conservative refusal handling. The original census's `training_eligible=False` reports must not be silently treated as approved training artifacts. The reserved 2026 periods stay available for a later candidate evaluated under frozen rules.

Qwen should receive structured causal observations and carefully defined research labels after this evidence review. There is not yet a verified profitable teacher policy, and this review does not supply one. No Qwen call, weight update, paper order or broker connection was made.

## Evidence and reproducibility

The new `ai_trader.research.historical_6e_census_review` command runs in the existing project environment. It needs no downloads, model API or GPU. It refuses changed input pins, incomplete receipts, missing/altered shards, inconsistent refusal evidence, reserved replay records and an existing output path. It records the review implementation and helper hashes and refuses publication if they change during the review.

- Original registration: `logs/6e_archive_development_20261001_1_registration.json`; SHA256 `ef4d929d1521a55e8f2273e13935d69e31570272be1a3c5fc1517b52b62fdc59`.
- Completion receipt: `data/processed/6e_archive_development_20261001_1/completion.json`; SHA256 `26f0767f99142aea07d82584889b0f5a1108dbd0b147f4db1733b5d298c38873`.
- Append journal: `data/processed/6e_archive_development_20261001_1/progress.jsonl`; SHA256 `a7d8dc3f005c0ae4d3e035b39014fbd5e8cc10060e92660135d4888526ff7158`.
- Final review: `data/processed/6e_archive_review_20261002_2_report.json`; SHA256 `34c436898d49c93d7f27353f61f88ea5bc73f708f75302a0a47b2b95da144616`.

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.historical_6e_census_review `
  --census-directory data/processed/6e_archive_development_20261001_1 `
  --registration logs/6e_archive_development_20261001_1_registration.json `
  --registration-sha256 ef4d929d1521a55e8f2273e13935d69e31570272be1a3c5fc1517b52b62fdc59 `
  --receipt-sha256 26f0767f99142aea07d82584889b0f5a1108dbd0b147f4db1733b5d298c38873 `
  --output data/processed/6e_archive_review_local_new_report.json
```

Use a fresh output path for another review. The generated reports remain local under the repository's data ignore rules. The original census artifacts were retained.

## Validation

The starting suite passed 3,359 tests with one optional Nautilus dependency skip. The completed change adds 25 tests for evidence integrity, refusal retention, reserved-date isolation, output boundaries, implementation drift, cost sensitivity and separate opportunity/direction accounting. The final complete suite passed **3,384 tests with one optional Nautilus skip** in 231.83 seconds. Repository Ruff checks and formatting checks passed for all 380 Python files.

An independent report check reconciled monthly and hourly horizon denominators, monthly opportunity totals, declining opportunity counts as costs increase, all 195 association dates and the recorded implementation hashes. A test run during source editing correctly triggered the existing paper-simulation source-drift refusal; its isolated check and the final stable-source suite both passed. No safeguard was removed. Existing formatting failures were corrected with formatting-only changes.
