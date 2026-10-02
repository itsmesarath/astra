# EURUSD archive coverage and movement research

The archive is much larger than the completed strategy studies. This work expands the historical research from selected dates to a date-by-date census of the development archive, with short-horizon movement paths and an interpretable cost-aware model experiment. It does not claim that the whole archive has already been analyzed, that hindsight winners were predictable, or that a profitable bot has been established.

## Verified starting coverage

The pinned intake contains 471 UTC daily files in three local ZIP archives totaling 17,928,869,179 bytes. All 471 have prior archive-integrity and header checks; those checks are not full order-book or strategy analysis. The updated exposure inventory reconciles the earlier feature studies and the completed [receive-clock comparison](EURUSD_RECEIVE_CLOCK_RESEARCH_20261001.md).

| Evidence before this expansion | Daily dates | Interpretation |
| --- | ---: | --- |
| Outcomes previously examined | 32 | 6.8% of file dates, not 6.8% of every event or hour |
| Additional reconstruction replay | 8 | No outcome study established for these dates |
| No replay documented in this inventory | 431 | Not proof that nobody ever inspected them |
| Latest standardized short-trade comparison | 9 | Subset of the 32 dates; 102,403 decision snapshots across four-hour windows |

File dates are not complete CME exchange sessions. Many files are Sunday reconstruction members, and all earlier short-trade outcomes use 12:00–16:00 UTC. The archive-wide program must track both date coverage and intraday-window coverage; analyzing every calendar file is not the same as labeling every trading hour.

## How the whole archive will be used

The phases preserve the ability to test a model on later data it did not help us design against.

| Period | Files | Current phase |
| --- | ---: | --- |
| 26 March through December 2025 | 241 | Development census and movement discovery |
| January through March 2026 | 77 | Reserved validation after a candidate and evaluation rules are frozen |
| April through June 2026 | 78 | Reserved test after validation decisions |
| July through 25 September 2026 | 75 | Final reserved evaluation, not another tuning set |

All 471 files are included in the inventory. The first census plans 198 available weekday decision-window replays and 40 reconstruction-only replays. Three 2025 members already marked degraded by the vendor—17 September, 24 September and 28 November—remain explicit non-replay records. Later quality failures are retained too. No date is replaced with a more profitable one.

The current extension deliberately retains the audited 12:00–16:00 UTC decision window and decodes each selected UTC member to EOF. Extending decisions to the remaining hours is a separate required phase: it needs tested handling of exchange maintenance, weekend boundaries, scheduled closes and session-crossing outcomes. That all-hours extension is not implemented or claimed complete here. Reserved dates will eventually be evaluated under a frozen protocol rather than mixed into pattern discovery.

## What the movement census records

Each date gets a fresh order book, feature state and position state. A fixed research calendar selects 6EM5 before 9 June, 6EU5 before 8 September, 6EZ5 before 8 December, and 6EH6 thereafter. These are explicit UTC-date roll assumptions, not evidence of the most liquid contract at every instant. Contracts are not price-spliced or back-adjusted. Daily header mappings and book reconstruction must pass; no liquidity-based contract substitution occurs after seeing outcomes.

Every accepted weekday retains the 37 causal feature quantities and original two-sided 15-second quote targets. Features include CVD, queue and visible-depth imbalance, prior price changes, replenishment proxies, matched passive executions and held-price support. Unavailable outcomes remain null rather than becoming fabricated losing or no-trade labels.

For deeper paths, the census selects the first eligible decision at least 60 seconds after the previously selected eligible decision. This selection uses timestamps and eligibility only, before outcome availability. Both winners and nonwinners remain in the sample. For the same recorded entry it measures 1, 5, 15, 30 and 60-second quote outcomes, favorable and adverse liquidation quotes, first observed gross +2/-2 and +4/-4 tick crossings, late exits, gaps and censoring. First crossings are not stop/target fills, and maximum favorable excursions are not achievable returns from a known exit rule.

The daily report compares each pre-entry feature with the existence of a positive 15-second direction after the stated costs. It retains the original feature orientation and reports support, unavailable cases, means and descriptive AUCs. These comparisons are hypotheses for later controlled tests, not proof of causes. Order-book data cannot by itself identify a trader's intent, confirm hidden iceberg size or establish which news event caused a move. Activity, volatility, time of day and contract regime can confound apparent explanations.

## Explanatory model experiment

A separate registered experiment fits exactly two shallow CPU cost trees: a CVD-only control and a model with all 37 microstructure features. Both use the unchanged depth-four, 16-bin, minimum-500-row leaves with support from three training sessions. Quantile thresholds and leaf returns are learned only from resolved 7–9 April outcomes. July and October are later, already-exposed development diagnostics, not fresh holdouts.

The target is net long and short quote return, not price direction alone. A decision can abstain unless its estimated best direction exceeds the existing half-tick entry threshold. Evaluation includes all later eligible decisions, unavailable entries and position/cooldown accounting, with an explicit no-trade control. The report saves every leaf's pre-entry conditions and training support, and both candidates are reported without automatic winner selection. No threshold search, sign reversal or retraining on later diagnostic outcomes is allowed in this attempt.

This improves the research model's ability to express selective entries and no-trade decisions; improved realized performance must still be demonstrated. No active trading model or Qwen checkpoint is replaced. More recent candidate training will require the census coverage and quality review, a fixed chronological whole-session split and a separately recorded experiment.

## Evidence and operation

The census and selective-fit registrations pin source metadata, earlier results, implementation files and protocols before their attempts. The census additionally records installed runtime versions. Each attempted raw date gets a persistent exposure record before access. Every successful day has separately hashed rows, thinned path cases and a report; failed dates retain error records. A report is published only after source-member hash verification and daily quality checks. Partial writes or interrupted attempts are not completed evidence.

The census is a quality-and-movement inventory, not the old all-or-nothing nine-session strategy experiment. It continues to independent dates after recorded quality refusals, without retrying the refused date. Its completion marker accounts for all planned dates but explicitly forbids aggregate strategy promotion from the successful subset. Unexpected errors, changed evidence, insufficient disk space or resource limits stop the run with retained evidence. Existing output directories cannot be reused as implicit restarts.

The local limits are a 12-hour check between days, a ten-minute per-day processing check, a two-million completed-quote daily buffer, 48 MiB per row/case artifact and 12 GiB of published daily artifacts. No raw archives are extracted or modified. The process needs this PC awake but does not need a browser, ChatGPT, an API key, the internet, a broker or a GPU. Do not edit its source or dependencies while it runs; it checks for drift before each date and publication.

The initial baseline passed 3,323 tests with one optional Nautilus skip. Focused verification passed 185 tests, including 36 new census/model tests. These cover calendar boundaries, reserved-data refusal, completed exposure, single-day equivalence to the V2 engine, path selection, unavailable labels, preserved failures, no implicit retry, evidence hashes, training-only fitting and immunity of fitted parameters to later outcomes. The final full suite passed **3,359 tests with one optional Nautilus skip** in 217.76 seconds. Repository Ruff and formatting checks passed.

## Completed model and case comparison

The two registered CPU fits completed once, using 14,156 resolved April observations each. The CVD-only tree has 11 leaves; the 37-feature tree has eight. Even the least-negative direction in the best training leaf remained negative: -1.961 ticks for the CVD-only tree and -1.350 ticks for the richer tree. Both therefore abstained on all 50,334 eligible later observations across July and October. Another 13,668 later observations were ineligible.

This equals the no-trade control, not a profitable trading result or improved predictive accuracy. It shows that these supported tree partitions did not find a cost-positive mean entry. It does not establish that no alternative strategy exists. No candidate was adopted, no threshold was reduced to force trades, and no Qwen training occurred.

An independent read-only check reloaded both saved models, verified their hashes, reconstructed all 64,002 later predictions and policy summaries without refitting, checked every explanatory leaf and reconciled leaf support to the April training count. All checks passed.

The causally thinned case comparison produced the following descriptive evidence:

| Three-day block | Selected cases | Resolved | Positive direction in hindsight | Unavailable |
| --- | ---: | ---: | ---: | ---: |
| April | 695 | 509 | 184 | 186 |
| July | 699 | 573 | 41 | 126 |
| October | 707 | 617 | 38 | 90 |

Greater prior five-second quote activity had opportunity AUCs of 0.555, 0.607 and 0.578 across those blocks. Prior five-second price range had AUCs of 0.560, 0.563 and 0.570. These are associations with the existence of either profitable direction, not predictions of the correct direction or deployable entry rules. The positive later samples are small, many features were inspected, and the comparisons are not adjusted for activity/volatility confounding or multiple comparisons. The hypothesis to examine after the broader census is whether a causal activity/volatility filter plus sequence confirmation can improve cost-aware selectivity; no threshold is selected from these descriptive results.

The contrast between many hindsight winners and no profitable fitted leaf matters: a price path can contain opportunity while the recorded pre-entry features still fail to distinguish it reliably from losses. Training only on the hindsight winners would hide that problem.

## Run status

The census finished at **21:49 Lisbon time on 1 October 2026**. The [completed review on 2 October](EURUSD_CENSUS_REVIEW_20261002.md) reconciles all 471 dates and verifies all published hashes: 195 weekday decision dates, 26 Sunday reconstruction dates, 17 refusals, three vendor-degraded members and 230 reserved metadata-only dates. It analyzes 45,584 thinned movement cases and documents the changing opportunity rates, separate activity/direction associations and sparse same-ID replenishment features. This completion covers the registered four-hour development windows; all-hours research and strategy validation remain pending. The launch and first-shard notes below are retained as historical operation evidence.

The archive census was launched locally at **2026-10-01 19:14:32 UTC** (20:14 Lisbon), with launcher PID 36200 and Python child PID 35120. These IDs identify this launch only; future checks must also match command line and creation time. The run is independent of this chat and remains bounded by its registered limits.

The first published day, 26 March, contains 11,001 decision snapshots and 235 thinned cases. Its full-member replay counted 1,856,559 target records. An independent artifact audit verified the row/case hashes, source pin, target arithmetic, timing, feature allowlists, exact causal case selection, all published horizon summaries and execution conservation. This is evidence of a functioning first shard, not completion of the 241-file development phase. Completion requires the final receipt, all-date accounting, retained refusals and artifact verification—not merely a running process or a progress line.

Local evidence paths and raw SHA256 pins:

- Census registration: `logs/6e_archive_development_20261001_1_registration.json` — `ef4d929d1521a55e8f2273e13935d69e31570272be1a3c5fc1517b52b62fdc59`.
- Census output directory: `data/processed/6e_archive_development_20261001_1`. `progress.jsonl` records completed or refused dates; `attempts/` records conservative access; `days/` holds daily artifacts. A terminal `completion.json` or `failure.json` is written by the runner.
- First daily report: `days/2025-03-26.json` within that directory — `0d880c3571feeb5713cd85a05816a03a6121e2ac989e5e2c9feebeff1a8e0b0d`.
- Selective-fit registration: `logs/6e_selective_development_20261001_1_registration.json` — `79f2324fdd1e34b60b32f518f8ecb2ce727e773871579cf12ef3f0be6a05c333`.
- Selective-fit report: `data/processed/6e_selective_development_20261001_1_report.json` — `f24be05b11dd53127f197a36e5b949284ad67f15022abab89fc8ba8bcdc903dd`.
- Saved CVD-only model hash: `a47db4aff531982d75b2127c8c241c8fe69852599bb08f60a7009f20e64e316a`.
- Saved 37-feature model hash: `d9ffd62216522e347cb9848d414eae019833a03e0d270ac23c0bb920222e5103`.

For a read-only progress glance from the project directory in PowerShell:

```powershell
Get-Content -LiteralPath logs/6e_archive_development_20261001_1.stdout.log -Tail 8
Get-Content -LiteralPath logs/6e_archive_development_20261001_1.stderr.log -Tail 8
```

Do not relaunch this registration or overwrite its output if the process stops. Retain incomplete evidence for diagnosis. The broader archive analysis, all-hours extension, controlled explanation tests and independently validated model improvement remain unfinished. BTC collection, broker connections and trading were not changed.
