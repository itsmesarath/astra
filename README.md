# Auto-Trader

An experimental cryptocurrency market-microstructure research system.

Current project stage and the separate 6E research roadmap: [status and flowchart](PROJECT_STATUS.md).
The 11 October payload-binding increment is accepted on constructed fixtures; the latest full
Python regression is **10,869 passed plus three expected skips**. Native/historical integration,
independent strategy validation and trading readiness remain separate gates. [Agent workflow](AGENTS.md)
records the skill-guided approval, testing, review and preservation rules. This is not a service-health
check or permission to start capture, training or orders.

Development roadmap: [the autonomous research-system plan](AUTONOMOUS_SYSTEM_PLAN.md) covers
order-book-first trading, pre/post-trade cases, decision-quality review, point-in-time memory,
controlled experiments, local Qwen roles and deterministic risk. It distinguishes implemented
components from future work; it is not a claim of a complete autonomous trading system.
The [ASTRA V2 proposal review](ASTRA_V2_REVIEW.md) records the September 24 roadmap additions,
corrections and deferred technology decisions; no proposed framework is implied to be installed.

An isolated [NautilusTrader evaluation](docs/adr/trading_engine.md) now has a synthetic replay
harness and tested reference calculations. Its historical native replay attempt was blocked by Windows Application Control;
Nautilus is not adopted by the trading runtime. See that record for commands and limitations.

[Capture-quality auditing and immutable trade cases](docs/QUALITY_AND_CASES.md) are implemented
as a read-only research slice, with a synthetic no-order example. They do not start a paper loop.

The [durable evidence and paper-account journal](docs/TRADE_JOURNAL.md) adds SQLite persistence,
conflict-safe retries, entry/exit fills and flat-start cash/position/PnL reconstruction. It is not
used by the default runner. An opt-in [durable paper gateway](docs/DURABLE_PAPER_GATEWAY.md) now
simulates atomic quote fills with pre-fill risk checks and persistent kill/daily-loss/drawdown state.
The opt-in [bounded paper controller](docs/PAPER_RUNNER.md) adds per-tick data-health checks, equity
marks and automatic stop/target/max-hold exits. An explicit-path [capture replay adapter](docs/CAPTURE_PAPER_REPLAY.md)
now rebuilds order-book/CVD evidence into controller ticks with snapshot timing and gap/recovery
checks. [Bounded public capture supervision and an offline paper smoke command](docs/CAPTURE_SUPERVISION_AND_SMOKE.md)
now add quotas, quarantined partials, finite fresh-session retries and explicit-source zero-order
checks. These were tested synthetically; unattended operation remains planned and no service starts
automatically.

A [fresh 60-second public-data check](docs/REAL_DATA_READINESS.md) now passes recorder integrity
and a complete offline paper replay with zero orders. It exposed and fixed snapshot-availability
lookahead in the standalone feature exporter. All 585 corrected observations match paper replay;
484 pass retrospective feature-quality checks, not training approval. Old standalone artifacts
must be rebuilt under the version-2 availability contract. No unattended service or strategy edge
is established by this one-minute operational sample.

[Prospective acquisition plans](docs/PROSPECTIVE_CAPTURE_PLAN.md) now freeze train, validation and
reserved whole-session assignments before collection. They use pinned code/runtime, finite quotas,
write-once audits and one attempt per slot; any failure stops the campaign without replacement.
Reserved captures stay outside research/training, and acquisition does not authorize model fitting.
The first planned campaign completed three separate one-minute sessions without retries. Their
transport checks passed; stricter event-label quality is assessed separately below.

The [first fixed event-label experiment](docs/PROSPECTIVE_EVENT_TRIAL.md) now reconstructs both
research sessions. Training-source quote gaps and session-end censoring leave only 31.9% of
eligible outcomes resolved, below the frozen 50% quality gate. The whole fold and NumPy fitting
were correctly blocked; reserved data remains unopened and no model was trained or promoted.

[Bounded capture-timing diagnostics](docs/CAPTURE_TIMING.md) now separate high-resolution receipt
gaps, event-loop lag, startup buffering, streaming queue wait and parsing/writing time. They use
an optional sidecar and leave the market-data schema and timestamps unchanged.
A one-minute diagnostic run passed integrity checks without reproducing the earlier >500-ms
gaps. This does not establish their cause or make the earlier blocked training fold eligible.

[Instrumented prospective campaigns](docs/INSTRUMENTED_CAMPAIGN.md) now freeze optional timing
for train/validation, bind sidecars to capture hashes and reject incomplete reports. Reserved
sessions stay uninstrumented and outside research. A two-minute-session recipe retains the
same label/freshness/cost gates, with a bounded 10,000-frame aggregate processing allowance.
The first instrumented campaign completed train but stopped near the validation deadline;
its partial remains quarantined and reserved was never started. A separately reproduced early
timer-wakeup defect is now fixed and tested synthetically; its role in that real interruption
is unproven. No training followed that incomplete campaign.

[Sanitized failure evidence](docs/CAPTURE_FAILURE_EVIDENCE.md) now distinguishes capture stages
and fixed failure reasons without recording exception messages or tracebacks. Completed capture
and timing schemas stay unchanged, and the earlier failed campaign remains quarantined.
A new three-session campaign completed without retries. Both research sessions passed the
unchanged label-quality gates (79.3% / 90.5% resolved), but all 856 training outcomes were net
losses under frozen costs. The numerical baseline correctly refused its one-class dataset;
zero epochs ran. Next broaden prospectively planned data coverage, not weaken cost or quality gates.

A [training-only historical corpus audit](docs/EVENT_CORPUS_AUDIT.md) now checks pinned label
accounting, coverage, overlap and frozen-cost arithmetic without reopening captures, validation
labels or reserved data. The 856 resolved training labels contain only nine disjoint outcome
intervals; their maximum inferred pre-cost ask-to-bid return was 1.10 bps versus a 24.03-bps
break-even requirement. This describes one two-minute sample, not a strategy-wide conclusion.
Historical code pins remain intact, and the audit cannot authorize fitting or deployment.

A [bounded UTC capture-window contract](docs/CAPTURE_WINDOWS.md) now freezes separated sessions,
exact research settings, dispatch deadlines and no-replacement failure policy offline. It checks
warmup/horizon feasibility and aggregate frame/compute quotas before collection. The candidate
two-train-session recipe keeps label/cost/quality settings unchanged while fitting within the
existing 10,000-frame budget. The [window-aware runner and strict intake](docs/WINDOWED_CAPTURE_RUNTIME.md)
now enforce these plans with durable single-use claims, connection/deadline checks, terminal failure
records and frozen-settings research preparation. The first real four-window campaign failed
during validation with receiver queue overflow; two training captures remain quarantined with
the failed campaign, and reserved never started. An [offline burst diagnosis](docs/CAPTURE_BURST_DIAGNOSIS.md)
reproduces a scheduling weakness without changing production code or opening raw captures.
A [bounded reader/writer repair](docs/CAPTURE_BURST_REPAIR.md) now passes synthetic bursts above
queue capacity, preserving receipt timestamps, FIFO order, quotas and overload refusal. Real-feed
reliability and the earlier receipt-gap cause remain unproven; no replacement capture was started.
A [separate predeclared two-minute diagnostic](docs/CAPTURE_BURST_DIAGNOSTIC.md) subsequently
passed integrity and all frozen operational checks: 6,358 events, queue high-water 49/256,
maximum depth-receipt gap 327 ms and zero orders. This one sample is diagnostic-only, not a
training fold or sustained-reliability result. Next prepare fresh prospectively assigned windows.
A [new post-repair windowed campaign](docs/WINDOWED_CAMPAIGN_20260925_3.md) started its first
train capture at 14:03 UTC on September 25, then failed with receiver queue overflow before
the initial snapshot became available: 257 received, 256 queued, zero processed. Both runner
processes exited; second train, validation and reserved never started. The monitor was deleted,
evidence retained, and no retry, labels, training or trading followed. This exposed a startup
buffering problem. The user requested this earlier start before campaign -2 acquired anything;
that canceled waiting run's claim/audit remain retained and cannot resume. Neither claim may
restart. The 3,000-frame/source research cap remains a declared risk for future busy sessions,
not a limit that can be enlarged after capture.
A [subsequent offline startup repair](docs/CAPTURE_STARTUP_REPAIR.md) now stages events while
the snapshot is pending and assembles the same receipt-causal format after acquisition. The
queue stays at 256; staging and final-copy bytes share the original 32-MiB ceiling, so byte
capacity is more conservative. Failed campaigns remain quarantined. Next consider a separately
predeclared operational diagnostic; no new capture, training or trading was started by this repair.
A subsequently authorized [single startup diagnostic](docs/CAPTURE_STARTUP_DIAGNOSTIC.md)
failed with snapshot timeout. It staged 271 messages with queue high-water 2/256 and no overflow,
but never reached snapshot availability or post-snapshot validation. Evidence is retained,
without retries or training. Next investigate the snapshot-fetch timeout offline.
The [offline snapshot investigation](docs/SNAPSHOT_TIMEOUT_DIAGNOSIS.md) now distinguishes
opening, body-read and elapsed/capture deadline failures, and rejects late EOF/validation results.
Timeouts and quality gates were not increased. The historical network cause remains unknown;
the subsequent [single snapshot/clock probe](docs/SNAPSHOT_CLOCK_PROBE.md) passed snapshot
validation in 1.50 seconds. Its exchange-time measurement was too uncertain to establish clock
offset. No new capture or training followed; next obtain a tighter read-only clock assessment
before a separately declared startup diagnostic. This does not resolve the historical timeout.
The [subsequent transfer diagnosis and fix](docs/SNAPSHOT_TRANSFER_FIX.md) measured slow body
delivery (8.02 seconds of a 9.33-second snapshot request). Gzip negotiation now reduces transfer
size, with independent compressed/decoded byte caps and unchanged depth/deadlines. A separate
late-acquisition race is fixed. Fresh NTP checks found about 156 ms of local clock lag; the
user's resync was accepted, but clock suitability must still be verified before a new campaign.
Neither the original timeout's network root cause nor continuous capture reliability is proven.
The final production check passed in 7.36 seconds with 9,950 compressed bytes; the clock still
measured about 140 ms behind its reference. Final regression: 2,780 Python passes, one optional
skip, 38 JavaScript passes and Ruff clean. No new research capture or trading followed.
Old runners reject the window contract. No training or trading follows capture automatically.

A [registered microstructure research policy](docs/MICROSTRUCTURE_POLICY.md) now converts causal
order-book/CVD/replenishment evidence into auditable proposals and abstentions with cost/risk checks.
It refuses reserved sources and records research-only cases; it does not execute trades, simulate
portfolio returns, or establish profitability.

A separate [explicit offline paper simulation](docs/MICROSTRUCTURE_PAPER.md) now connects that
frozen hypothesis to ledger-derived risk and exits-first paper execution. It requires opt-in on
every invocation, preserves kill/loss state on resume and never promotes stored research cases.
Verification uses synthetic inputs; quote-only fills do not establish an edge or a running paper service.

A [read-only paper evaluation report](docs/PAPER_EVALUATION.md) now reconstructs executed trades,
fee/slippage-aware PnL, sampled equity/drawdown and time in position, with a holding-cash control.
It flags incomplete runs and unknown open-inventory values; it cannot execute or promote a strategy.

[Mechanical post-trade reviews](docs/POST_TRADE_REVIEW.md) now separate outcome-blind structural
case checks from verified PnL, retain rejected/unfilled cases, and mark lessons as anecdotes.
They use a single read-only journal snapshot and do not train or update a policy.

[Registered multi-session paper campaigns](docs/MICROSTRUCTURE_CAMPAIGN.md) now preserve one account,
open positions and risk history across a fixed sequence of captures while rebuilding each session's
book/CVD/warmup state. Combined read-only evaluation retains disconnect exposure and unknown marks.
This is synthetic-tested offline continuity, not a supervised forward trading service.

[Receipt-causal event labels](docs/MICROSTRUCTURE_EVENT_LABELS.md) now pair order-book/CVD/liquidity
features with later, after-cost hypothetical Spot-long outcomes inside one registered research
session. Unknown outcomes stay explicit and reserved sources are refused. A
[source-verified loader and whole-session fold manifest](docs/EVENT_TRAINING_DATA.md) now reproduce
those artifacts, enforce chronological outcome cutoffs and block the whole fold when a declared
source fails quality checks. An [opt-in numerical event baseline](docs/EVENT_BASELINE.md) now adds
training-only preprocessing, fixed-budget NumPy fitting, validation controls/metrics and safe JSON
model reload. [Registered walk-forward evaluation](docs/EVENT_WALK_FORWARD.md) now refits fixed-recipe
models on expanding earlier-session prefixes and evaluates each later research session once. Failed
folds stay visible and suppress pooled metrics; reserved sources remain unopened. All fitting so far
uses synthetic test fixtures, not actual market data, and is not connected to paper execution.

A [non-executing model shadow adapter](docs/EVENT_SHADOW.md) now seals a single-baseline model with
its availability time and records predictions/abstentions on later research captures. It refuses
reused/reserved sources, stale inputs and expired predictions, and has no order-placement authority.

Research software, not a profitable trading product or financial advice. No profitable strategy
has been established. Execution is paper-only. A [bounded local Qwen reviewer adapter](docs/LOCAL_QWEN_REVIEWER.md)
now adds an opt-in process boundary, pinned local checkpoints and strict advisory reports, verified
with synthetic transport/runtime tests. Qwen3-4B-Base is now installed in an isolated environment
and completed one measured local CUDA inference test. Its JSON was valid, but its positive
economic interpretation was unsupported by the supplied evidence; this is not a trading-quality
pass. A [25-case synthetic advisory curriculum and offline scorer](docs/QWEN_ADVISORY_EVALUATION.md)
now checks abstention, costs, conflicting microstructure evidence and conditional positive controls.
The frozen labels were drafts; the existing smoke fails its matched regression. The curriculum
subset now has separately recorded delegated-agent review; development scores remain provisional.
A separately enabled frozen-plan runner now evaluates only the development split, with at most
seven local worker attempts, durable per-case records and no retries after worker failure. Its
scores are provisional, not a trading-quality approval. No training or model deployment follows
automatically. Its first approved batch matched only 2/7 draft verdicts. A
[versioned Spot-long contract](docs/QWEN_REVIEW_CONTRACTS.md) now preserves V1 replay and makes
the cost/stress question explicit. Its approved V2 comparison improved veto recall but passed
only 1/7 full model checks; neither version is promoted. Independent
[bounded evidence/arithmetic checks](docs/SPOT_LONG_EVIDENCE_CHECKS.md) now preserve those raw
results and prepare 14 curriculum fact packets. The user explicitly delegated target decisions:
a [versioned AI review](docs/QWEN_DELEGATED_REVIEW.md) now accepts all 14 proposed targets
(11 veto, 3 conditional support) and exports an independently reconstructed candidate. It records
no human approval and grants no training or execution authority.
[Protected-evaluation metadata and training preflight](docs/QWEN_TRAINING_PREFLIGHT.md)
now add overlap checks, completion-only loss masks and a CPU tokenizer check of all 14 proposals.
A [separate protected-dataset intake](docs/QWEN_PROTECTED_INTAKE.md) now derives reservation
metadata from pinned evaluation payloads and checks overlap, behavior coverage and numeric targets.
It is synthetic-tested; no real protected dataset or custodian approval has been created.
A [bounded LoRA worker](docs/QWEN_LORA_WORKER.md) now adds explicit opt-in, fixed-step/deadline
supervision and adapter save/reload checks. A separate [pinned training environment and native
tiny-model smoke](docs/QWEN_NATIVE_LORA_SMOKE.md) now pass real CPU LoRA updates and exact adapter
reload. Actual Qwen CUDA training feasibility and the holdout reservation remain pending;
no Qwen fitting or model promotion has occurred. The
[offline operator-review page](docs/QWEN_REVIEW_WORKBENCH.md) remains optional for a separate
human review; it is not needed for this delegated candidate and still needs a visual browser check.
The Python package remains named
`ai-trader` (import: `ai_trader`).

Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). Project code is available
under the [MIT license](LICENSE); third-party dependencies and downloaded data retain their
own licenses and terms. See [the TradingAgents review](TRADINGAGENTS_REVIEW.md) for architectural
inspiration and attribution.

## Initial scope

- Market: BTCUSDT on Binance
- Mode: research, backtesting, and paper trading only
- Language: Python
- Hardware: NVIDIA RTX 5080 Laptop GPU with 16 GB VRAM

## Safety boundary

Live trading is disabled during development. Model decisions will never directly control an exchange account. A separate deterministic risk and execution layer must validate every proposed action.

Agents and model inference run locally; public market data may use internet access. Execution
configuration now recognizes `paper`, `spot_testnet`, and `spot_live`, with paper as the default.
Only paper is implemented; testnet/live selections fail closed rather than place orders or pretend
to be paper. See [execution modes and the live-adapter roadmap](EXECUTION_MODES.md).

```powershell
.venv\Scripts\python.exe -m ai_trader.trading.runtime --mode paper --check
```

## Research principles

Our primary direction is **order-book and trade-flow research**: CVD, liquidity, replenishment,
absorption and other microstructure features. See [MICROSTRUCTURE_PLAN.md](MICROSTRUCTURE_PLAN.md)
for implemented evidence, uncertainty and the next research stages. Candle strategies below are
comparison baselines, not the main trading approach.

Build receipt-causal microstructure evidence from an explicitly selected combined capture:

```sh
python -m ai_trader.features.build_microstructure data/raw/YOUR_CAPTURE.jsonl data/processed/microstructure.jsonl --source-session YOUR_SESSION --levels 5
```

Use a new output path for each build. This offline command emits a separate JSONL research artifact,
not trading instructions or training-ready labels. Replenishment/absorption flags are heuristic
evidence, not confirmed iceberg orders. It does not modify existing datasets or contact an exchange.

The fixed trend-pullback research API is implemented in `ai_trader.research.trend_pullback`.
`ai_trader.research.pullback_replay.replay_pullback_scenarios` takes explicitly selected raw
five-minute candle sessions and reports every 24/36/48-bps cost scenario at next-open and delayed
entry, with 10% capital allocation and frozen ATR price distances. It does not load data, enforce
a research registration, select a winner, or authorize promotion. Tests are synthetic; no economic
edge has been demonstrated. See [RESEARCH_LOG.md](RESEARCH_LOG.md) for assumptions and remaining gates.

For an auditable research run, first use `ai_trader.research.registration` to write a new local
registration from a **five-minute BTCUSDT** archive manifest and explicit ordered research/reserved
session names. Registration reads metadata, not candle files. Then
`ai_trader.research.registered_pullback` verifies the source/environment/manifest record and loads
only the research selection. Do not use reserved or previously inspected confirmation data to
rescue a rejected hypothesis. These commands provide research evidence only, not promotion.

```sh
python -m ai_trader.research.registration --help
python -m ai_trader.research.registered_pullback --help
```

Store registrations and outputs under `data/processed/` (ignored by Git). Both commands refuse
existing output files. A post-validation failed trial retains a failure artifact; do not erase
failed trials. Source or dependency changes require a new registration. A local hash is not trusted
timestamping, and the record does not prove an archive was never previously inspected. Formal
controls and uncertainty estimation remain unfinished; no historical run of this rule is claimed.

- Use time-based train, validation, and test splits.
- Prevent future information from leaking into model inputs.
- Include fees, spread, slippage, and latency.
- Compare advanced models with simple baselines.
- Evaluate expected value and drawdown, not prediction accuracy alone.
- Require sustained paper-trading evidence before considering small live tests.

## Planned architecture

```text
Binance market data
    -> validated event storage
    -> order-book reconstruction
    -> microstructure features
    -> baseline models
    -> specialized neural models
    -> decision model
    -> hard risk engine
    -> paper-trading execution
    -> evaluation and retraining
```

## Public historical Spot data

The historical downloader uses Binance's unauthenticated public-data archive. It verifies each
published SHA-256 checksum, retains the original ZIP and checksum, and writes a normalized CSV with
millisecond timestamps plus a request manifest. It never reads API credentials or submits orders.

Download completed daily BTCUSDT 5-minute candles:

```cmd
python -m ai_trader.ingestion.download_binance_history --data-type klines --interval 5m --start-date 2024-01-01 --end-date 2024-01-31
```

Download completed daily aggregate trades:

```cmd
python -m ai_trader.ingestion.download_binance_history --data-type aggTrades --start-date 2024-01-01 --end-date 2024-01-02
```

Outputs go under `data/raw/binance_spot_history` by default. A request cannot include the current
UTC day because Binance daily archives are only reproducible after a day has completed. Historical
archives do not contain order-book depth, so kline/aggregate-trade models must use a separate
feature schema from the live depth-capture pipeline.

Build causal 1-, 5-, and 15-minute Spot datasets from a verified 1-minute kline manifest:

```cmd
python -m ai_trader.features.kline_dataset data\raw\binance_spot_history\manifest_BTCUSDT_klines_1m_2024-01-01_2024-01-31.json --output-directory data\processed\btcusdt_kline_research
```

Every UTC day is a distinct `source_session`. Sixty-bar rolling features reset at each session
boundary, labels enter at the next bar's open, and future barrier windows never cross into another
day. Labels subtract configured entry and exit fees plus slippage. If profit and stop barriers are
both touched within one candle, the label records the stop first to avoid optimistic intrabar bias.
The defaults model market-order execution and are research assumptions, not guaranteed fills.

The linear trainer and session-aware walk-forward evaluator detect this historical kline feature
schema explicitly and preserve its ordered feature names in checkpoints and reports. They reject
mixed or mismatched schemas even when the numeric dimensions happen to agree.

For kline datasets, walk-forward reports also simulate one non-overlapping long position at a time.
Use `--starting-balance` and `--position-fraction` to set research capital assumptions. Reports
include cost-adjusted PnL, closed-trade drawdown, turnover, exposure, profit factor, and signals
skipped while a prior trade was open. This remains offline evaluation and cannot place an order.
Optional CLI controls include `--minimum-reentry-delay-minutes`,
`--maximum-trades-per-session`, `--session-profit-target`, and `--session-loss-limit`; reports count
signals rejected by each control.

## Research validity and next milestone

Read the [strategy research reset](STRATEGY_RESEARCH_PLAN.md) before interpreting backtests.
Walk-forward report schema 7 separates fitting, past-session checkpoint tuning, and next-session
evaluation. `--minimum-training-sessions` counts fitting sessions only;
`--tuning-session-count` (default 1) adds a disjoint tuning block. For a 20-session initial prefix,
use `--minimum-training-sessions 15 --tuning-session-count 5`. Legacy `validation` metric fields
now mean evaluation-only; tuning metrics and session names are recorded separately. Schema 1
reports reused the scored session for checkpoint selection and remain exploratory.

The loader first inventories source-session names and feature timestamps, then reserves the final
sessions before converting features, labels or economic outcomes. It rejects unordered/overlapping
sessions and any research outcome reaching the next session's first feature timestamp. Optional
`--embargo-ms` adds a required gap: `outcome_time + embargo_ms < next_session_start` must hold for
every research row. Crossing rows cause an error, not silent trimming. Nonmonotonic exit times are
allowed; the check does not assume the last row is the longest trade. Both feature and outcome
timestamp columns are now mandatory, including for legacy depth datasets.

Schema 3 records the source SHA-256, session inventory, embargo and boundary policy. Reserved CSV
rows are still tokenized as text, and their names/feature timestamps are inspected; their features,
targets and returns are not converted or summarized. This is not physical lockbox isolation.
Schema 2 separated checkpoint tuning but still converted all held-out rows.

Kline labeling version 2 processes opening barrier hits before intrabar high/low touches, using
the opening price and timestamp for idealized market-triggered exits. Stops can lose more than
their configured threshold. Unknown intrabar ordering remains stop-first; costs remain fixed bps.
The common CSV row schema stays at 1, with an explicit `labeling_version` column; the kline manifest
is schema 2 and records the fill policy. Older labels are unchanged: regenerate into a new directory
before relying on these rules, and do not mix labeling versions in an experiment.

Schema 4 carries capital and re-entry cooldowns across evaluation sessions. Only session trade
counters and session-start PnL limits reset. Accepted outcomes enter an in-memory settlement ledger:
PnL is booked at exit before subsequent decisions, not when the trade is selected. Intervals remain
inclusive, so a new entry at the exact exit millisecond is rejected. Aggregate metrics use those
same settlements and reject independently reset session reports. Observation duration spans the
first entry through the maximum outcome exit, including gaps between sessions. Schema 3 and older
economic reports used per-session selection capital and must not be treated as equivalent.

This remains label-based accounting, not independent candle execution replay. Drawdown is still
closed-trade only and turnover is explicitly a twice-entry-notional proxy. Fully isolated
per-session storage and complete code/environment manifests remain future work. No new historical
profitability claim has been made. Execution remains paper-only; public data ingestion may be online.

## Independent candle replay

`ai_trader.backtesting.candle_replay` is a research API with opt-in walk-forward integration, not
connected to promotion gates. It accepts chronological `CandleSession` objects containing raw `Kline`
candles and ordered long-signal candle-close timestamps for one asset. It never consumes outcome
labels. Callers must produce signals causally; matching a timestamp alone does not prove causality.

```python
from dataclasses import replace
from pathlib import Path
from ai_trader.backtesting.candle_replay import ReplayConfig, replay_candles, write_replay_report

# sessions: tuple[CandleSession, ...], explicitly selected research sessions only
config = ReplayConfig(holding_bars=120)
next_open = replay_candles(sessions, config)
delayed = replay_candles(sessions, replace(config, entry_delay_bars=1))
write_replay_report(Path("data/processed/replay/next_open.json"), next_open)
write_replay_report(Path("data/processed/replay/delayed.json"), delayed)
```

Entry uses the next open plus the configured number of full delay bars. There is one pending order
or long position at a time; overlapping signals are discarded, not queued for later opportunities.
Sizing includes the entry fee in the cash budget and rounds quantity down to a configurable step.
Slippage worsens buy/sell prices, and fees apply to each simulated fill's actual notional. Reference
stop/target geometry matches labeling version 2, but actual fee/slippage arithmetic is not the
labels' additive-bps approximation. A configured stop is not a guaranteed loss cap.

Opening barrier hits precede high/low tests; ambiguous intrabar touches use the stop. Intrabar/time
exits are timestamped at candle close. Positions are liquidated at session end and unfillable
pending signals expire; no position crosses a session boundary. Cash and cooldown carry forward,
while session trade counts and realized-PnL gates reset. These gates prevent new entries after
settled gains/losses; they are not unrealized-equity liquidation rules.

Replay reports contain fills, trade PnL, decisions, session balances, every candle-close equity
mark, actual simulated buy-plus-sell turnover, costs, configuration and an input-content hash.
Marked equity values holdings at close without reserving hypothetical exit costs; both marked and
closed-trade drawdowns are reported. Observation time includes all supplied candles and gaps
between sessions. Reports refuse overwrites. This remains an idealized market-order model: no
volume/queue model, exchange tick/min-notional filters, intrabar equity path, or guaranteed fills.

### Frozen-prediction walk-forward replay

Schema-7 walk-forward reports save each evaluation fold's feature timestamps and class probabilities
in `[-1, 0, 1]` order, captured once before scoring. To opt into candle replay, provide both
`--replay-manifest` (the verified normalized Binance kline manifest) and `--replay-holding-bars`.
The latter is an explicit bar count, not minutes. Optional `--replay-take-profit-bps`,
`--replay-stop-loss-bps`, `--replay-taker-fee-bps` and `--replay-slippage-bps` control replay assumptions.
Capital and session-risk settings are shared with label economics. Short-enabled policies and
non-kline feature schemas are rejected for this integration.

The loader selects all non-held-out research session names before opening or hashing candle
archives, covering fitting, tuning and evaluation inputs. Only evaluation candles reach trading
replay. Held-out and unrelated archive files are not opened; manifest dates and names remain
visible. Selected file hashes are verified before and after parsing. The combined
labeled CSV still has the metadata/tokenization limitations described above.

`candle_replay` contains `next_open` and `delayed_one_bar` reports driven by identical frozen
predictions and the same fixed policy. Both scenarios retain their own continuous capital path.
All prediction timestamps, including flat decisions, must match unique candle closes. Reports
include the prediction/policy hash and each scenario's candle/signal input hash. Neither
scenario selects a model or promotes a winner. `aggregate_economics` remains the separate legacy
label-based measure, with different cost and observation definitions.

With replay enabled, schema 7 recomputes every fit/tuning/evaluation feature from the selected raw
candles before any model fitting. Each calculation receives only its 60 preceding in-session
bars plus its current completed bar. After the generator's existing 12-significant-digit formatting,
the resulting float64 values must match the model inputs exactly: no tolerance, repair or override.
Missing warmup, changed features, mismatched timestamps and inconsistent raw candles reject the run.
Older features generated under different rules may need regeneration into a new directory.

`replay_feature_provenance` records the verification policy, feature names, warmup, calculation-module
SHA-256 and per-session candle/feature content hashes and row counts. Its scope is all non-held-out
research features. `research_label_provenance` separately records exact label recomputation against
those same candles, the current calculation-module hash, label-record hashes and declared settings.
Replay-enabled runs require complete labeling-v2 columns; legacy/incomplete rows must be regenerated
into a new directory, not silently accepted.

Labels must use one consistent declared horizon, neutral threshold, profit/stop barriers, fee and
slippage configuration across research rows. The checker verifies targets, net/gross returns,
entry/exit prices and times, barrier outcomes, durations, symbol/session identity and cost metadata,
and confirms that the parsed model targets/economic outcomes match the evidence. Horizons must
fit wholly within their source session. Label settings are independent of replay stress settings;
both are recorded, allowing cost stresses without rewriting the training labels.

These checks establish consistency with the current generator, not historical authenticity or
independent correctness of the labeling algorithm. They neither validate held-out rows nor prove
the original generation process. Standalone frozen-prediction replay has no feature/label matrix
and does not perform these checks; walk-forward runs without replay record null provenance.

The `training.replay_evaluation.replay_frozen_predictions` API can replay saved predictions without
fitting a model again. Walk-forward reports now refuse overwrites; choose a new `--output` path for
each experiment. Enabling replay writes detailed marks/fills and predictions, so reports are larger.
No historical experiment or final held-out evaluation has been run to validate this integration.

## Offline research council

The [TradingAgents architecture review](TRADINGAGENTS_REVIEW.md) documents what we can reuse
locally without paid model keys. An opt-in research council now supports bounded analyst/critic
reviews, timestamped evidence, strict JSON citations, and deterministic risk vetoes. It cannot
place orders and is not connected to the paper champion. The supplied reviewer is deterministic;
a local LLM backend has not yet been installed or integrated.

Run a synthetic, entirely offline safety demonstration:

```powershell
.venv\Scripts\python.exe -m ai_trader.research.council --demo
```

## Local development setup

Use Python 3.12. Open Command Prompt in the project directory, then run:

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"
python -m pip install -r requirements\cpu.txt
```

On Linux/macOS, activate with `source .venv/bin/activate` and use
`requirements/cpu.txt`. A GPU is optional for the test suite. For the NVIDIA development
environment, install `requirements/gpu-cu132.txt` instead of the CPU requirements.

Verify the installation:

```cmd
python -m ai_trader.diagnostics
python -m ruff check .
python -m ruff format --check .
python -m pytest -v
```

The CUDA smoke test is skipped on machines without CUDA; CPU tests still run. GitHub Actions
runs lint, formatting checks, and the suite on Python 3.12 with CPU PyTorch.
