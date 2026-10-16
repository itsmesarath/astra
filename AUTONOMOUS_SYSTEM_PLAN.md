# Autonomous BTCUSDT research system: authoritative development plan

BTC roadmap updated 2026-09-25; current status pointer refreshed 2026-10-11.
Includes the maintainer's ASTRA V2 proposal review.
This is a design and delivery plan, not a claim that its future components are implemented.
It supersedes the ordering and promotion criteria in AUTONOMOUS_TRAINING_PLAN.md.
MICROSTRUCTURE_PLAN.md remains the detailed feature/data contract; EXECUTION_MODES.md remains
the implemented execution boundary. Historical research findings remain in RESEARCH_LOG.md.

The separate 6E research track and latest accepted Python evidence are indexed in
[PROJECT_STATUS.md](PROJECT_STATUS.md), including its current-stage flowchart and proposed
next gates. Constructed payload binding is complete; the native/historical bridge is not.
That status does not supersede the BTC roadmap below, validate collectors or release a new
implementation, experiment, model or trading action. [AGENTS.md](AGENTS.md) records the
skill-guided approval, independent testing/review and preservation workflow.

The [ASTRA V2 review](ASTRA_V2_REVIEW.md) records accepted additions, corrections, deferred
technologies and repository evidence. The supplied document is a proposal, not an instruction
that overrides the owner or authorizes implementation, agents, installation or trading.

## Objective and non-negotiable boundaries

Build a system that observes market state, proposes falsifiable hypotheses, plans bounded trades,
checks risk, executes in paper, manages positions, reviews the process, and tests improvements.
It is not just a direction classifier, and a sophisticated workflow does not establish an edge.

- Primary inputs: BTCUSDT Spot L2 order book and aggressive trades, CVD, liquidity and
  replenishment/absorption evidence. Candles are context and comparison baselines.
- Public market-data connections may use the internet. Agent inference, memory and training
  remain local. No paid model API is required by the intended design.
- Only paper execution currently works. Testnet/live selections fail closed. This plan does not
  authorize adding credentials, connecting an account, placing orders, or starting ongoing capture.
- Spot positions are long/flat, with no borrowed assets, shorting or leverage. Bearish evidence
  may mean abstain or propose a risk-approved reduction, not initiate a short.
- The user's approximately EUR 100 future live-capital idea is a tentative total cap, not a
  risk recommendation or activation instruction. Quote-currency conversion, venue availability,
  order filters and permissible sizing must be checked at that later milestone; never increase
  capital automatically to satisfy an exchange minimum.
- Deterministic code owns calculations, risk, position management and execution. Neither LLM
  output, research memory, a profitable trade, nor model promotion can enable live trading.
- Continuous learning means collecting evidence and running controlled batches, not changing
  model weights or rules after every trade. The active paper policy stays frozen during a run.

## Current state and actual gaps

| Area | Existing reusable implementation | Still missing for this objective |
| --- | --- | --- |
| Data | Combined capture/validation, reconstruction, quality reports, bounded capture supervision and offline smoke checks | Operational timing, recovery, quotas and supervised forward-feed verification |
| Features | Receipt-causal CVD/OFI/depth/evidence, source-reproduced loading and training-only baseline preprocessing | Causal regime/intensity/impact features and real-data quality validation |
| Research | Event-fold/recipe manifests, protected-source loading, fixed-recipe event walk-forward evaluation, predictive controls and read-only paper evaluation | Actual-data walk-forward evidence, point-in-time memory and experiment scheduler |
| Execution | Durable Spot paper ledger, cost/risk checks, bounded protection controller and offline multi-session campaigns | L2/partial/latency fill realism, supervised forward service and remote reconciliation |
| Agents | Strict analyst/critic council, bounded local reviewer, pinned Qwen3-4B-Base installation and one measured CUDA smoke test | Content-quality/abstention evaluation, broader latency tests, durable graph and memory |
| Learning | Costed event labels, verified folds, opt-in NumPy fitting/reload, sealed non-executing shadow predictions and mechanical case/outcome reviews, tested synthetically | Actual-data validation, independent quality reviews, point-in-time memory, LOB model, Qwen adapter training |

Latest complete Python regression: **10,869 passed, three expected skips**, accepted on
2026-10-11; current files and saved report were reconciled without rerunning tests. See
[the dated status evidence](logs/project_status_evidence_20261011.md) for exact identities,
pins and verification limits. This does not establish native/backend or external-service health.
Historical September 25 regression: **2,780 Python tests passed, one optional-Nautilus skip**,
plus **38 JavaScript tests passed**. JavaScript was not freshly rerun in this status review.
The earlier operator-approved single 30-second public capture connected but was quarantined:
85 events exceeded the 2-second receipt/event freshness bound (maximum 2.405 seconds). No retry,
feature generation, paper smoke or training followed that failure. A subsequent distinct
[60-second readiness sample](docs/REAL_DATA_READINESS.md) now passes the unchanged freshness
limits and zero-order paper replay. It exposed and fixed a standalone exporter snapshot-lookahead
bug; all 585 corrected feature rows match the already-causal paper replay. Multi-session/forward
reliability remains unproven. The earlier failed partial remains quarantined, not retried or repaired.
A [prospectively assigned acquisition campaign](docs/PROSPECTIVE_CAPTURE_PLAN.md) subsequently
completed three new one-minute sessions, assigned train/validation/reserved before collection.
All passed unchanged integrity checks without retries; the reserved raw contents remain outside
research/training. This is a small transport-data milestone, not event-label eligibility, model
fitting or independently authenticated Qwen evaluation custody.
The [first fixed event-label trial](docs/PROSPECTIVE_EVENT_TRIAL.md) has now reconstructed the
two research sources without opening reserved data. Train resolved 151/474 eligible labels
(31.9%) and validation 247/414 (59.7%). The frozen 50% source-quality gate blocked the entire
fold and the one bounded NumPy attempt, with zero fitting. Recorded 0.57–1.04-second quote gaps
and session-end censoring explain the training gate failure; network versus local scheduling
causes remain unproven. Next instrument capture timing and collect longer planned sessions,
without relaxing the fixed quality rules or silently relabeling inspected sources.
[Bounded QPC/queue/event-loop diagnostics](docs/CAPTURE_TIMING.md) now leave raw receipts unchanged
and distinguish startup snapshot buffering from streaming work. One 60-second diagnostic capture
completed: maximum depth-receipt gap 437 ms, probe lag 29 ms, streaming queue wait 1.89 ms and
parse/write time 0.35 ms. The earlier >500-ms stalls were not reproduced; their cause and sustained
reliability remain unproven. Next collect longer prospectively assigned sessions with these diagnostics.
The [version-2 acquisition contract](docs/INSTRUMENTED_CAMPAIGN.md) now freezes research-only
instrumentation before capture and verifies pinned reports during metadata intake. Reserved
sessions receive no timing sidecar. A new two-minute recipe keeps all label/cost/quality gates
unchanged and caps processing at 5,000 frames per research session, 10,000 total.
That first instrumented campaign stopped with a validation partial near its deadline after
training capture completed. Reserved was not started; no labels or fitting followed. A synthetic
regression separately reproduced an early timer-wakeup defect, now corrected using QPC deadlines
and retained pending operations. This does not prove the real failure's cause. Next add sanitized
failure reasons and verify a new bounded campaign; do not retry or repair the failed experiment.
[Allowlisted failure-stage/reason evidence](docs/CAPTURE_FAILURE_EVIDENCE.md) is now implemented
and tested, including sanitized campaign/timing audits and the legacy supervisor. Completed capture
schemas, timing contracts and training gates remain unchanged.
A new fixed three-session, two-minute-per-session campaign completed without retries. Both
research sources now pass the original quality gates: 856/1,079 (79.3%) train and 974/1,076 (90.5%)
validation outcomes resolved. Two measured >500-ms receipt gaps remain censored, not repaired.
The single NumPy attempt was blocked by training class counts [856, 0, 0] (loss/breakeven/profit),
with zero epochs and no validation scoring. Reserved research reads remain zero; Qwen was not
trained. A [bounded training-artifact corpus audit](docs/EVENT_CORPUS_AUDIT.md) now separates
historical evidence from current audit code, retains stale-trial training guards and never opens
raw captures, validation labels or reserved data. It found only nine disjoint outcome intervals
among 856 resolved training labels, with maximum inferred pre-cost ask-to-bid movement of 1.10 bps
against a 24.03-bps break-even requirement. This is not statistical sufficiency or a new replay.
A [bounded, predeclared UTC window contract](docs/CAPTURE_WINDOWS.md) is now implemented and
tested offline. It freezes exact settings and whole-session roles, checks temporal/processing
budgets, rejects late/reordered/incomplete completion claims and cannot be executed by the old
back-to-back runner. A two-train/one-validation candidate uses 3,000 frames/source (9,000 total),
with unchanged costs, labels and quality gates. No real schedule or capture was started.
The [window-aware runtime and metadata intake](docs/WINDOWED_CAPTURE_RUNTIME.md) now enforce
single-use claims, dual-clock deadlines, post-connection admission, terminal failure evidence
and exact all-slot receipts, with frozen-settings research preparation. Synthetic tests cover
crashes, concurrency, cancellation, disk stalls and altered evidence. The first real windowed
campaign was subsequently launched on 2026-09-25 at 10:26 UTC after the user confirmed host
availability. Four predeclared two-minute windows open at 10:30, 11:30, 12:30 and 13:30 UTC,
assigned train/train/validation/reserved. It subsequently failed during validation with receiver
queue overflow after two completed training captures; reserved never started. The runner exited
and follow-up was removed. No successful-subset research or fitting is allowed. An
[offline burst diagnosis](docs/CAPTURE_BURST_DIAGNOSIS.md) reproduces overflow before a ready
writer gets a scheduling turn, but does not establish the source of the real 2.87-second receipt
gap. A single synthetic yield per message was insufficient on larger bursts with the old
watched consumer. The subsequent [bounded scheduling repair](docs/CAPTURE_BURST_REPAIR.md) adds
a receiver handoff and ready-queue draining capped by count/time, including shutdown cancellation.
Synthetic bursts up to 4,096 frames pass; genuine overload still fails at the unchanged capacity.
Caps, receipt semantics, deadline checks, costs and quality rules remain unchanged. Next consider
one distinct predeclared diagnostic capture to check real-feed behavior; do not repeat the failed
campaign, process its successful subset or infer throughput/strategy quality from synthetic tests.
No new capture or training occurred in the repair slice. A subsequently predeclared
[single two-minute operational diagnostic](docs/CAPTURE_BURST_DIAGNOSTIC.md) passed integrity
and all frozen timing/accounting checks without retries: 6,358 messages, queue high-water 49/256,
maximum depth-receipt gap 327 ms, streaming queue wait 2.04 ms and loop lag 25.25 ms. It remains
diagnostic-only, not a training source or sustained-reliability/causal-attribution result. Next
prepare a distinct prospective multi-window fold under the repaired source; confirm windows and
host availability before acquisition. No further campaign, labels or fitting was started.
A [distinct post-repair campaign](docs/WINDOWED_CAMPAIGN_20260925_2.md) was subsequently
launched after the user confirmed availability. Its four 120-second train/train/validation/
reserved windows open at 14:15, 15:15, 16:15 and 17:15 UTC on September 25. A read-only follow-up
checks metadata and must verify every slot after process exit; launch does not establish success.
Source/dependency edits must wait until this campaign terminates. The unchanged 3,000-frame/source
research cap may reject busy captures (the preceding diagnostic had 6,311 frames); that risk was
disclosed before launch, and no post-outcome cap increase, replacement or subset is allowed.
Before its first capture, the user explicitly requested an earlier start. The verified waiting
campaign -2 was stopped without acquiring data; its original claim/audit remain unchanged.
A separately pinned [campaign -3](docs/WINDOWED_CAMPAIGN_20260925_3.md) was scheduled at
14:03/15:03/16:03/17:03 UTC instead, with the same roles, duration, limits, settings and source.
It began at 14:03 UTC but failed in the first train slot with receiver queue overflow before
snapshot availability: 257 received, 256 enqueued, zero processed, queue high-water 256/256.
Both processes exited; second train, validation and reserved never started. Pinned failure/audit/
timing metadata agree; raw contents remain unopened. The follow-up was deleted, with no retry,
labels, training or trading. Next diagnose startup buffering offline; snapshot latency and burst
origin remain unproven. Neither campaign may resume. This user-requested pre-acquisition change
does not authorize future automatic shifts, replacements, cap increases or continuous collection.
A subsequent [offline startup repair](docs/CAPTURE_STARTUP_REPAIR.md) starts the bounded writer
alongside the snapshot and stages receipts on disk, then assembles the existing snapshot-first
format. Memory queue capacity remains 256. Staging and assembly share the original byte ceiling,
with stricter effective final-file capacity; idle monitoring now covers startup too. Causal replay,
freshness/quality/cost gates and no-retry policy are unchanged. Synthetic pending-snapshot bursts
now pass, but real-feed startup reliability remains unverified. Next consider one separately
predeclared diagnostic under the new source, not a replay/resumption of the failed campaign.
The subsequently authorized [single startup diagnostic](docs/CAPTURE_STARTUP_DIAGNOSTIC.md)
failed with snapshot timeout before its intended 120-second completion. It parsed/staged 271
messages while awaiting the snapshot, with high-water 2/256 and no queue overflow; snapshot
availability and post-snapshot coverage were absent. This is useful pending-snapshot staging
evidence, not a passing operational test or training source. Metadata pins/bindings verified;
failed raw partials remain unopened. No retry, model call, fitting or order followed. Next
investigate the snapshot-fetch timeout offline before any separately declared network check.
The [offline snapshot follow-up](docs/SNAPSHOT_TIMEOUT_DIAGNOSIS.md) adds phase-specific,
sanitized timeout/transport/status evidence that survives the executor boundary. A reproduced
deadline gap is corrected: late EOF or validation cannot bypass the unchanged elapsed budget.
No timeout/byte/freshness gate is relaxed. The cause of the previous network timeout remains
unknown. A subsequent [single snapshot/clock probe](docs/SNAPSHOT_CLOCK_PROBE.md), without a
WebSocket or retry, passed snapshot validation in 1.50 seconds. The separate exchange-time
request's wide offset interval was inconclusive; Windows' phase value is not a fresh Binance
offset measurement. Next obtain a tighter read-only clock assessment before a separately
declared startup diagnostic. No clock adjustment, freshness relaxation, capture, research-fold
reuse or model call followed this probe; it is not full-capture or training-readiness evidence.
The [next diagnostic/fix](docs/SNAPSHOT_TRANSFER_FIX.md) isolated slow response-body delivery
in one nearly 10-second request. Gzip negotiation reduces wire payload without shrinking the
book, increasing deadlines or relaxing byte/freshness limits. Bounded decompression rejects
ambiguous framing and over-expansion. A reproduced late-acquisition success race is also fixed.
NTP checks show local-clock lag around 156 ms; the user's administrator resync was accepted,
but a successful sync command alone does not establish acceptable offset. Verify clock quality
before any separately declared full startup diagnostic. Historical failures remain quarantined.
The final production gzip probe passed in 7.36 seconds (9,950 wire bytes), showing transfer
size reduction but persistent latency variability. Final NTP readings remain about 140 ms
behind the configured reference. No further campaign starts or freshness relaxation follow.
Do not collect until profitable
or change inspected costs/labels to fit. Training still requires actual-data quality/class
diversity and Qwen's separate protected-case/custody gates.
Synthetic tests and bounded data-quality checks are not profitable-strategy or successful model-
training evidence. Do not treat old dataset/session counts as the current inventory; inspect
explicit manifests when needed. Earlier Windows Application Control failures and their subsequent
development context remain in RESEARCH_LOG.md. Passing this suite does not clear the separate
native Nautilus blocker or establish a working Qwen training environment. Never weaken security
controls to bypass native dependency failures.

## Architecture: fast execution path, slow improvement path

Separate three deployable responsibilities: the development assistant (called ASTRA in the
proposal), the trading runtime, and an isolated research/training laboratory. The assistant is
not a per-trade dependency. The lab can create challengers but has no execution credentials or
write access to the active runtime bundle. Promotion is an audited operator-controlled operation.

```text
Public feed -> immutable capture -> validated market state -> numerical features/models
                                      |                         |
                                      |                  candidate + pre-trade case
                                      |                         |
                                      |                  deterministic risk
                                      |                         |
                                      +--------------> paper execution + position supervisor
                                                                |
                                                         fills, marks, exits
                                                                |
case/outcome journal -> reviews -> hypothesis registry -> isolated experiments -> evidence gates
                                                                          |
                                                          versioned paper challenger
```

The diagram describes the target; not all nodes are implemented. Slow local LLM roles consume
bounded market summaries and journal records, not raw book dumps. They must not block feed
processing, emergency controls or exits. Any advisory response has an expiry and references the
exact state/proposal version; a late response cannot authorize a stale proposal. Recheck current
state, size and risk immediately before execution. A denied entry is not a forced exit.

| Logical role | Initial implementation | Authority |
| --- | --- | --- |
| Market State / Microstructure Analyst | Deterministic reconstruction and feature code | Emit observations and quality flags, no orders |
| Regime Analyst | Causal statistical baseline; ML later | Versioned context/uncertainty, no risk overrides |
| Trading Agent | Rule/numerical baseline first; local LLM advisory later | Propose LONG, HOLD/NO_ACTION or REDUCE/CLOSE through a validated plan |
| Risk Agent | Deterministic engine, not an LLM | Approve, reject or conservatively cap within declared rules; journal final size |
| Execution Agent | Deterministic gateway and position state machine | Act only on a fresh authorized request, reconcile receipts |
| Post-Trade Analyst | Numeric metrics + fixed rubric; optional LLM interpretation | Append a review, never rewrite the original thesis |
| Research Agent | Experiment registry/runner + optional local hypothesis drafting | Propose and test ideas, no execution or champion-write capability |

Reuse existing LONG/FLAT interfaces via an explicit adapter when the richer proposal schema is
introduced. HOLD, denied entry and requested flattening must never be conflated. Roles are not
eight models: start with the existing analyst/critic pair sharing one local model sequentially.

### Hierarchical intelligence without a compulsory LLM bottleneck

Distinguish perception (features/embeddings), strategic advice (optional local Qwen), tactical
policy (rules or a small numerical model), and a deterministic proposal selector. Schedule feed,
perception, tactical and strategic work separately. Start with an explicit selector table, not
another learned controller. Version its precedence, disagreement and expiry rules. Learned
arbitration must later beat this baseline in component ablations on identical protected splits.
Qwen is not a prerequisite for the first independent paper runtime. In a policy that requires
Qwen approval, its absence blocks new entries; in a separately approved rule-only policy it is
not required. Never silently switch policies after a model failure. Position protection continues.

A future target-exposure contract must distinguish `NO_ACTION` (leave position management in
control) from `SET_TARGET(0)` (request liquidation). Reject contradictory action/target fields.
Define target as BTC inventory valued at a declared causal mark divided by positive portfolio
equity in USDT, before converting to BTC quantity. Record mark, balance and pending-order
versions; account for outstanding buys/sells, reserved funds, fees, rounding and minimum notional.
Zero/invalid equity blocks increases. Risk rechecks the resulting order; a target is not an order.
Do not reinterpret today's LONG/FLAT request schema without an explicit migration and tests.

## Data and feature contracts

Retain raw events, snapshot IDs, capture/reconnect IDs, local wall time, local monotonic receipt
time, exchange event/trade time, sequence ranges, schemas, checksums and configuration. Monotonic
timestamps are relative to a process/boot epoch; never compare them across restarts without that
identity. Do not call wall-clock minus exchange time a measured one-way network latency without
clock-synchronization assumptions. Late, duplicated, missing, reordered and incomplete streams
must be visible in quality reports. Quarantine unusable sessions; do not silently repair outcomes.

Preserve known snapshot depth bounds. Report observed versus complete depth and inferred versus
measured values. Public L2 cannot directly establish individual cancellations, hidden iceberg
reserves or stop orders. Liquidity removals/pulls, replenishment and stop-run-like patterns must
have explicit proxy definitions and attribution quality. Never label them confirmed hidden intent.
Archived candles/aggTrades cannot reconstruct absent historical L2; collect or obtain actual depth
captures instead. Market impact requires an explicit model; observed post-trade movement alone
does not identify our own causal impact.

Add features incrementally: multi-horizon intensity and CVD, spread/depth changes, liquidity
persistence, short returns/volatility, price-response-to-flow and causal regime state. Each carries
units, availability time, warmup, missingness and quality. Fit scalers, encoders, thresholds and
regime definitions only on fitting/tuning partitions. Regimes must allow unknown/transition states;
never use future-smoothed regime labels as live inputs. Feature ablations count as experiments.

Extend the existing recorder, not replace it: bounded buffering, explicit overflow/gap incidents,
monotonic/processing/persistence timing, reconnect epochs and tested snapshot resynchronization.
Do not merge disconnected intervals into one apparently continuous session. Measure sustained
bytes/second, disk headroom and capture lag before unattended collection. Configure quotas and
retention; reaching a limit stops collection/new exposure safely, never silently deletes pinned
experiment data. Preserve source hashes, units and schema links across raw, normalized, book,
feature and episode layers. Parquet/analytical storage is a benchmarked derived layer, not a
reason to discard working raw JSONL or invalidate existing provenance.

## Structured trade case: create before the first new paper strategy

Every candidate, including abstentions and risk rejections, receives a `case_id`; a filled trade
also has a `trade_id`. One case may have multiple requests/fills. Preserve rejected and unfilled
cases so memory does not learn only from trades that happened to execute.

Pre-trade record, sealed before any order submission:

- Identity/provenance: case ID, session, symbol, mode, event sequence, decision/availability times,
  market-state reference/hash, strategy/model/adapter/prompt versions and research approval ID.
- Context: regime estimate/version/uncertainty, microstructure features, liquidity coverage,
  feed health, feature quality and cited evidence IDs.
- Thesis: hypothesis ID, expected observable behavior, horizon, supporting/contradictory evidence,
  invalidation conditions and explicit abstention/expiry conditions.
- Proposal: entry semantics, stop, target, holding period, proposed size, intended management
  rules, expected costs and liquidity assumptions. Record numerical estimates separately from
  uncalibrated model scores and prose confidence; missing calibrated probability stays null.
- Risk: current portfolio/limits version, proposed loss at stop including modeled costs,
  risk verdict/reason, approved size, expiry and final execution-intent fingerprint. Actual loss
  can exceed a stop estimate through gaps, fees, slippage or operational failures.

Append-only lifecycle events:

`PROPOSED -> REJECTED / EXPIRED / APPROVED -> SUBMITTED -> PARTIAL / FILLED / CANCELED / UNKNOWN`

Track position management and closure separately from order status. Bind amendments to new plan
versions and risk checks; never retrospectively edit the original entry thesis. Unknown execution
state requires reconciliation, not blind resubmission. Restart must not create a second fill or
silently discard an open position. Risk-reducing handling remains available when entries are blocked.

Post-trade record, after fills and outcome horizon are resolved:

- Actual weighted entry/exit, quantity changes, cash flows, fee assets and conversion assumptions,
  realized PnL, slippage versus declared benchmarks, holding time, and mark series references.
- MAE/MFE (each once): maximum adverse/favorable excursion, explicitly defining mark basis,
  costs, quantity changes and observation frequency. Prefer executable-side/depth-aware marks
  where supported; midpoint or candle marks must disclose their limitations. Never invent marks
  during outages. Store quote-currency and normalized measures with units.
- Expected-versus-observed path, invalidation events, thesis support/contradiction, unexpected
  events, and entry/exit/risk/execution/regime-assessment quality with evidence references.
- Primary and secondary reason categories, reviewer/version, uncertainty, and a proposed lesson
  classified as anecdote until a registered study supports it. Counterfactuals are labeled simulated.

### Separate outcome from decision quality

Freeze the review rubric before outcomes. Score evidence availability, rule adherence, risk
compliance, planned versus actual execution, and operational handling separately. Store mechanical
checks separately from subjective LLM assessments; unknown is allowed. Outcome is net PnL and
observed path, not a quality label. An outcome-blind pass evaluates the sealed case first; a second
pass compares expectations with actual events. Regime-estimation quality cannot use a hindsight
regime definition. Winning rule violations remain violations; one compliant loss is not evidence
to retrain. Evaluate consistency of reviews and include human audits of disputed/high-impact cases.

## Three memories, one provenance discipline

Start with local SQLite event tables and typed schemas, not an unrestricted vector database.
Use transactional event IDs, unique request/fill keys, schema migrations, crash recovery and
read-only consumers; retain raw market files outside the database. This is proposed storage,
not yet installed or implemented. Local append-only policy is not tamper-proof storage.

| Memory | Contents | Allowed effect |
| --- | --- | --- |
| Trade | Sealed cases, rejections, requests, fills, outcomes and reviews | Retrieve past evidence, never alter the ledger |
| Pattern | Candidate and validated definitions, sample scope, estimates, uncertainty, expiry | Only approved patterns may be eligible policy inputs |
| Research | Registrations, all trials including failures, data/code/model versions and conclusions | Reproduce, reject or propose a challenger; never trade |

Every record needs source event time, observed/available time, outcome-resolution time where
relevant, and lesson creation/approval time. Retrieval at cutoff T requires all necessary knowledge
to have been available by T. Partition by research run/fold, role, model/policy version and execution
mode; filter before similarity retrieval. Held-out outcomes must not enter training memory, prompts,
regime selection or research summaries. A lesson generated tomorrow is unavailable in yesterday's
replay even when it describes an older trade. Freeze/snapshot memory per evaluation run.

Memory updates are contextual retrieval, not weight training. Prevent self-reinforcing summaries:
lessons cite underlying cases, counts and counterexamples; unsupported conclusions remain candidates.
Approved patterns expire or become suspended on predefined drift/quality failures; suspension blocks
use but does not silently invent a replacement policy. Treat retrieved text as data, not instructions.

Extend these three evidence memories with separate operational records, not six new databases:
runtime state belongs to the durable order/position journal; model lineage belongs to a registry;
playbooks are versioned policy artifacts referencing pattern/research evidence. A playbook declares
market, mechanism, required/contradictory evidence, regimes, entry/management/invalidation rules,
cost assumptions, failure modes and evaluation IDs. Separate research status, deployment eligibility
and active deployment; a `LIVE` label never arms an account. Immutable versions bind into a runtime
bundle with model, features, prompts, selector, risk configuration and memory snapshot hashes.

Human-readable Markdown/Obsidian views are optional projections of these records. Notes cite
case/run/dataset/model IDs and report paths; editing a note cannot alter a registry or risk limit.
Exclude secrets, raw event dumps and binary checkpoints. No external vault is created by this plan.
MLflow/DVC export compatibility is a future tested adapter, not a claim made merely because our
manifests contain similar fields. Start with portable local manifests and explicit registry states.

## Research engine and evidence gates

Lifecycle: draft -> registered -> running -> completed/failed -> rejected/inconclusive/validated
-> paper challenger -> approved paper version or rollback. Preserve every attempt. Registration
must bind microstructure data, event definitions, hypothesis direction, horizons, regimes, cost/
latency/impact assumptions, controls, sample criteria, uncertainty method and trial budget.
Do not reuse the fixed candle-pullback registration as if it validated an L2 study.

Initial example to investigate, not an approved strategy: aggressive buying with persistent ask
replenishment and limited upward price response may predict weak continuation or reversal.
For Spot long/flat, test it first as a no-entry/context variable; an exit policy is a separate
experiment. Mirror bid absorption is a separate declared long-entry hypothesis, not assumed symmetry.

Deduplicate overlapping events and record unavailable/low-quality cases. Search/discover on fitting
data, select thresholds/horizons on past tuning data, then freeze before chronological evaluation.
Keep all rows/sequences from a source session exclusive within each fold; purge overlapping outcome
windows and apply an explicit embargo. Past evaluation sessions can enter later folds only once
outcomes are available. Record retired/previously exposed holdouts and reserve fresh confirmation.

Compare against cash, declared risk/exposure-matched baselines and seeded random events using the
same executable fill model. Report unmatched controls, every registered horizon/regime, rejection
counts, net expectancy, PnL, drawdown, turnover, exposure and cost stresses. Predefine block/session
resampling, effect size/sample planning and multiple-testing treatment. Row counts and many
correlated trades do not establish independent sample size; a favorable subgroup is not confirmation.

Before an economic trial, a registration must contain numerical minimum-session/event coverage,
drawdown/exposure limits, baseline-improvement and uncertainty thresholds, stress requirements,
failure tolerances and the maximum hypothesis budget. Choose these from risk objectives and sample
planning, not after results. Unset thresholds block promotion; insufficient evidence is inconclusive.
Classification accuracy/F1 are diagnostics, not substitutes for net economic and operational gates.
Human approval is required for initial paper-policy promotions. Live arming is always a separate gate.

Repeated historical episodes must bind data/split manifest, warmup, start/end, starting inventory,
cost/fill/latency version, seed and objective. Windows may be sampled from training sessions only;
time stays causal within each episode. Repetition creates optimization trials, not new independent
evidence. Log failed/pruned trials as well as successes, and keep protected evaluation unavailable
to prompt search, teachers, hyperparameter search and curriculum selection.

## L2 execution and operational safety

Reuse the risk/gateway interfaces, but add a depth/trade replay implementation rather than claim
candle fills are realistic for subsecond order-flow strategies. Simulate arrival after declared
decision/network latency, walk available displayed liquidity, track partial fills/remaining size,
fees, cancellation latency and expiry. Missing depth means unknown/unfillable under a declared
policy, not unlimited liquidity at the last quote. No guaranteed maker fills from price touches.
If modeling queue priority, test conservative queue assumptions and sensitivity; do not infer exact
queue position from public L2. Avoid double-counting spread/slippage already paid in simulated fills.

The supervisor owns stops/targets, invalidation, maximum hold, daily loss, drawdown, exposure,
cooldown, data staleness and emergency entry halt independently of the LLM. Test partial entry
protection, stop rejection, cancellation/fill races, missing marks, restart, disk exhaustion and
unknown order state. During a disconnect, halt new exposure and reconcile; do not promise immediate
flattening without connectivity. Future venue-side protection, if supported, needs separate testing.

Model risk configuration as finite, validated, versioned operator input: balance allocation,
per-trade loss budget, position/order caps, stop/target semantics, daily-loss/drawdown limits,
cooldowns and resume policy. Not all these controls exist yet. A profit target is a policy setting,
not an earnings promise. Separate research/replay workflow selection from the execution environment
(`paper`, reserved `spot_testnet`, reserved `spot_live`) and health state (`RUNNING`, `HALTED`,
`RECONCILING`); do not add contradictory mode enums. Future live-to-paper switching must first
quiesce new live exposure and explicitly reconcile/cancel/manage outstanding live orders and
positions under an approved policy. Changing a UI label does not end live obligations.

### Independent paper-runtime handoff gate

Milestone 5 is operationally complete only after a predeclared soak/fault test demonstrates:
causal healthy inputs, a frozen policy bundle, bounded lag/resource use, independent risk and
position management, durable cases/fills, restart reconciliation, alerts, and operator stop/resume.
Specify numeric duration, lag/recovery/error budgets before the run; unset budgets block handoff.
Exercise feed gaps, disk pressure, unknown orders and model/research process failure. The runtime
must continue its declared safe behavior with the development assistant absent. Operational
handoff does not establish profitability or eligibility for live deployment.

Monitor data quality, features, predictions, calibrated errors, actions and execution separately;
labels arrive only after their horizons resolve. Drift creates a versioned incident and invokes
a predefined entry-halt/reduction policy, not automatic retraining, relaxation of limits or promotion.
Use human-approved resumes. A model rollback changes future decisions but never rewinds fills,
balances or orders; reconcile existing positions and plan versions before switching bundles.

## Local models, LangGraph and controlled improvement

Numerical baselines come first: rule-only, logistic/linear or small MLP on the same event dataset,
then a small causal temporal/LOB encoder if it adds measured value. Calibration, scaling and
embeddings must obey the same fold boundaries. Keep a schema/version contract for numeric outputs
passed to the LLM. Arithmetic, risk sizing, costs and metrics never depend on generated prose.

Preserve `Qwen/Qwen3-4B-Base` as an adapter-training candidate, not a permanent dependency.
Evaluate `Qwen/Qwen3.5-4B-Base` as a separate candidate only in a bounded hardware benchmark;
post-trained `Qwen/Qwen3-4B` remains a distinct instruction-following baseline, not a silent
substitution. Base checkpoints are not assumed to follow instructions reliably without adaptation.
Compare actual tasks and inference/training costs, not model names or parameter counts alone.
Benchmark a single local instance with bounded summaries,
strict JSON/citations, time/token/memory limits, abstention and no cloud fallback. Start in shadow
review/post-trade interpretation. Raw responses, model/tokenizer/quantization/prompt hashes, sampling
settings and memory snapshots belong in the audit record. Multiple roles share correlated errors.

LoRA/QLoRA feasibility must be measured on this machine: driver/runtime compatibility, tokenizer,
sequence length, batch size, peak VRAM, throughput and a saved-adapter reload test. Do not guarantee
training fit from weight size alone. Pin a tested environment; training must not starve capture or
position supervision. No model download or large training job starts as part of plan editing.

Training examples use causal market summaries, approved structured plans, all outcome classes and
rejections. Validated outcome metrics and human/criterion-reviewed concise rationales are separate
targets; LLM-generated lessons are not ground truth. Train in versioned batches, evaluate schema
validity/calibration/latency and net economics, then compare rule-only, numerical-only, LLM-advisory
and memory-enabled variants. Test prospectively to reduce historical knowledge contamination.
Fine-tuning changes weights; prompt memory changes context; hypothesis approval changes policy
eligibility. Each needs an independent version and experiment record.

Treat the proposal's Windows 11 / RTX 5080 Laptop / 16 GB VRAM / 32 GB RAM / 1 TB SSD as
reported hardware, not freshly verified capacity. Check actual free resources, driver/runtime
compatibility and sustained thermal/throughput behavior before selecting a backend. Register job
limits for disk, RAM, VRAM, wall time and trial count. Default to sequential training/inference
on the laptop; unattended research needs explicit bounds, recoverable progress and protected data.

Read-only preflight on 2026-09-24 verified the RTX 5080 Laptop GPU with 16,303 MiB VRAM and working
PyTorch CUDA device discovery. At that initial stage no Qwen model or isolated Transformers
runtime had been installed. The core environment still excludes Transformers and adapter-training
dependencies; the separately provisioned runtime is described below.
The [bounded local reviewer](docs/LOCAL_QWEN_REVIEWER.md) implements the
non-executing backend interface, owned-worker deadlines, pinned safetensors, local-only loaders,
strict citations and synthetic transport tests. Its first implementation had no actual Qwen
inference evidence; the later approved smoke test below adds that evidence, not training.
It cold-loads each role; process isolation is not an OS sandbox or RAM/VRAM quota. Synthetic integration
does not need to wait for a profitable strategy or successful new capture; actual-data training and
paper deployment retain their separate data/evidence gates. Do not infer QLoRA readiness from CUDA
device discovery alone.

The subsequent operator-approved Qwen setup created `.venv-qwen` and installed hash-pinned
staging dependencies (Transformers/tokenizers/safetensors and their dependency closure). Its
dependency/import and synthetic worker checks pass, with no core-environment changes. Local
connections to Hugging Face and the CUDA PyTorch download host reset before metadata/index
retrieval, although PyPI works. CUDA Torch is not installed in the isolated environment, no
model revision/assets are pinned or downloaded, and no real-model inference was attempted.
Resume provisioning after normal access to the official hosts is restored; do not replace this
with CPU fallback, unofficial mirrors or security-control changes. No training is authorized.

That initial network blocker was subsequently resolved: ordinary IPv4 terminal requests worked
after the operator confirmed Chrome access, without security/network-setting changes. The exact
official Qwen3-4B-Base revision and hashes are now pinned, 8.06 GB of assets verified, and the
isolated CUDA environment installed. One bounded synthetic call completed in 40.281 seconds,
using approximately 7.68 GiB peak Torch-allocated VRAM and 8.32 GiB peak process working set.
It returned valid JSON but an unsupported positive economic interpretation without calibrated
after-cost expectancy. This is inference/format evidence, not a content-quality or trading pass.
No training, model/policy promotion or paper integration followed. A
[25-case draft advisory curriculum and offline scorer](docs/QWEN_ADVISORY_EVALUATION.md) now adds
abstention/cost/conflict/proxy/risk regressions, conditional positive controls and input-boundary
cases. Family/session grouping and exact normalized duplicate checks separate curriculum from
visible development evaluation; this is not a final holdout or approved training dataset. Offline
rescoring catches the original smoke's unsupported verdict. A subsequent explicitly approved,
frozen-plan batch completed seven local model calls and four input refusals in 276.406 seconds.
All model replies were valid JSON but returned support, matching only 2/7 draft verdicts; the
five expected vetoes were missed. The four deterministic input checks passed separately.
Rationale semantics remain ungraded. Inspection also exposed an underspecified v1 review task:
the prompt mentions an existing hypothesis without a dedicated hypothesis field or the suite's
precise stress rule. The [versioned Spot-long contract](docs/QWEN_REVIEW_CONTRACTS.md) now supplies
that question/rubric and preserves V1 replay exactly. One separately approved V2 batch completed
seven calls and four input refusals in 291.406 seconds. Only 4/7 model reports were valid; four
draft vetoes matched, but only 1/7 passed full schema/verdict/citation checks. Both positive controls
failed output validation, and an explanation inverted 35 minus 30 into a loss. V2 is not an overall
improvement or a promotion candidate. A separate [bounded numeric checker](docs/SPOT_LONG_EVIDENCE_CHECKS.md)
now audits supplied estimates with exact arithmetic, preserving both original scores and raw
replies. The [pinned curriculum approval workflow](docs/QWEN_CURRICULUM_APPROVAL.md) now supports
explicit review, candidate export and reconstruction. Following explicit user delegation,
[V2 AI review](docs/QWEN_DELEGATED_REVIEW.md) accepted all 14 proposed targets and exported a
verified candidate with 11 veto and 3 conditional-support examples. No human review is claimed;
manual target decisions are no longer a prerequisite for this candidate. A
[metadata-only holdout boundary and training preflight](docs/QWEN_TRAINING_PREFLIGHT.md) now reject
declared overlap with every exposed case and prepare completion-only loss masks. All 14 proposed
targets pass a local CPU tokenizer check; no real holdout was created and no optimization ran.
A [custodian-side protected dataset intake](docs/QWEN_PROTECTED_INTAKE.md) now derives and
reconstructs metadata from actual supplied payloads, refusing overlap, cross-session evidence
and inconsistent targets. It has synthetic tests only; no real protected dataset was supplied
and no independent-data attestation is inferred from passing structural checks.
A [bounded optimization/save-reload worker](docs/QWEN_LORA_WORKER.md) is now implemented with
synthetic/fake-backend tests, pinned launch inputs/source/runtime, adapter-only updates and a parent
deadline. A separate [pinned training environment/native tiny CPU smoke](docs/QWEN_NATIVE_LORA_SMOKE.md)
now passes three real LoRA updates and exact adapter reload. No Qwen fitting or CUDA training
feasibility result is claimed. Next: actual protected evaluation reservation and a bounded Qwen
resource trial. The [offline review workbench](docs/QWEN_REVIEW_WORKBENCH.md) remains an optional
V1 human-review interface, separate from the completed delegated review; visual browser
verification is incomplete. The new candidate grants no fitting or execution authority. Keep validator
decisions separate from raw model output. Do not relabel failures, relax validation or train on
these development cases. Additional iterations on them cannot constitute independent confirmation.

Training sequence: causal supervised outcome prediction -> behavior cloning from auditable
policy trajectories -> optional offline RL -> optional simulator RL. Qwen SFT is a separate
language/schema/review curriculum; preference training is later research, not a replacement for
the numerical tactical model. Keep no-trade, rejected, failed and losing cases; selecting only
winners or full-path hindsight actions creates selection bias. Teacher labels need deterministic
checks and sampled review. Retain regression cases for schemas, abstention, risk and old regimes.

RL is not required for paper autonomy or live readiness. It needs action/reward/next-state
trajectories, adequate behavior-policy coverage and an audited simulator. A price series alone
is not an offline policy dataset; replay does not reveal all counterfactual fills or our market
impact. Record truncation versus terminal states, warmup, carried inventory and terminal valuation
or costed liquidation. Test episode-boundary exploits. Report net change in marked equity after
external cash-flow adjustment; if fills/fees already embed costs, do not subtract them again.
Keep reward-shaping penalties separate from reported economic PnL and immutable hard limits.
Unsupported actions, unrealistic fills or reward hacks invalidate a claimed improvement.

Use LangGraph only for the slower research/review workflow once the journal contracts exist.
Reuse the analyst/critic `Reviewer` seam. Plan persistent local checkpoints, stable run/node IDs,
bounded iterations, retry budgets, deduplicated side effects and crash-replay tests. A checkpoint
is not an order/fill ledger and does not guarantee exactly-once execution. The research graph must
not possess execution/account capabilities. Local-only endpoints and process permissions must be
enforced, not merely requested in a prompt. No dependency is added in this planning change.

### Technology decisions before adoption

The initial [decision register](ASTRA_V2_REVIEW.md#technology-decision-register) separates existing
core tools from candidates. Before milestone 3's larger replay implementation, run one bounded,
isolated build/adapt/adopt evaluation of NautilusTrader against our existing interfaces and a
hand-calculated synthetic fixture. Test receipt-time visibility, snapshot bounds, partial fills,
precision, risk veto, order identity, restart/export and latency semantics. Record exact package
and matching documentation versions, Windows compatibility, license, measured costs and exit plan.
Do not rewrite the repository or install an engine as part of this document review.

Development update (2026-09-24): the subsequent authorized implementation added an isolated
[Nautilus evaluation harness](docs/adr/trading_engine.md) and portable reference tests. Version
1.231.0 installed in a separate environment, but native replay is BLOCKED by Windows Application
Control loading pandas. No adoption decision or successful native backtest is claimed. Resolve
that environment issue through an approved process before continuing the native comparison.

## Delivery sequence and proposed files

Paths marked NEW below are proposed, not currently runnable. Tests accompany each implementation.
Reuse existing modules instead of replacing working capture, risk, feature or gateway behavior.

| Milestone | New / changed repository files | Acceptance gate |
| --- | --- | --- |
| 1. Quality + case contracts | IMPLEMENTED minimal v1: `src/ai_trader/research/capture_quality.py`, `src/ai_trader/trading/trade_case.py`; `tests/test_capture_quality.py`, `tests/test_trade_case.py` | Synthetic rejection/reproduction/immutability tests; no order access; durable sealing and complete lifecycle fields remain future work |
| 2. Durable trade journal | PARTIAL: `trade_journal.py`, `paper_lifecycle.py`, `paper_account.py`, `durable_paper_gateway.py` and tests implement evidence, account reconstruction, opt-in atomic quote simulation and durable risk checkpoints | Verified retries, conflicts, cash/cost/PnL, reservations, concurrent cash claims, migrations and crashes before/after commit; default runtime/feed integration and remote reconciliation NOT implemented |
| 3. Engine decision + microstructure execution | FIRST proposed `docs/adr/trading_engine.md` with bounded build/adapt/adopt evidence; THEN `src/ai_trader/research/microstructure_protocol.py` and selected replay adapter (provisional `src/ai_trader/backtesting/l2_replay.py`), with tests | No broad rewrite; preserve causal/risk contracts; registered holdout isolation; hand-calculated partial fills/fees/latency; uncertainty specified before runs |
| 4. Event dataset + baselines | PARTIAL: `training/microstructure_data.py`, `training/event_training_data.py`, `training/train_event_baseline.py`, `training/event_walk_forward.py` and tests implement costed outcomes, verified folds, frozen preprocessing, NumPy fitting/reload and registered expanding-session evaluation | Synthetic timing/cost/isolation/embargo/fit/reload/walk-forward tests pass; actual-data quality/sample validation and walk-forward evidence, calibration adequacy and model-to-runtime integration remain |
| 5. Recoverable paper loop + review | PARTIAL: `trading/paper_runner.py`, `trading/capture_replay.py`, `ingestion/capture_supervisor.py`, `trading/paper_smoke.py` and `research/post_trade.py` implement health/protection, durable results, bounded capture retries, an explicit-source zero-order check and mechanical read-only case/outcome reviews | Verified synthetic timing, gap invalidation, reconnect warmup/CVD reset, protection, recorder recovery, smoke restart/rollback and outcome-blind structural reviews; operational feed recovery, independent thesis/quality assessment and unattended-runtime handoff remain |
| 6. Memory + research registry | NEW `src/ai_trader/research/memory.py`, `src/ai_trader/research/hypothesis_registry.py`; corresponding tests | As-of/fold filtering, negative results and counterexamples, version/approval/expiry gates; no broker capability |
| 7. Shadow local Qwen + graph | NEW `src/ai_trader/models/local_reviewer.py`, `src/ai_trader/research/workflow.py`; corresponding tests; CHANGE `research/council.py` and optional dependencies only after review | Deterministic stub first, then local schema/latency/VRAM tests; no network fallback, bounded graph, no orders |
| 8. Controlled model/policy expansion | Proposed `src/ai_trader/training/train_qwen_adapter.py`, `src/ai_trader/models/lob_encoder.py` only if warranted; tactical-model/RL paths selected separately after trajectory/simulator review | Versioned examples/adapters; component ablations; forgetting/reward-hack tests where applicable; evidence beyond frozen baselines; explicit paper promotion; RL optional |
| 9. Future bounded live pilot | Revisit `EXECUTION_MODES.md`; adapter/reconciliation/arming design and exact files reviewed separately | Operational testnet checks, prospective paper gates, operator approval and bounded capital; no automatic transition |

Milestone 1's initial [quality/case slice](docs/QUALITY_AND_CASES.md) is implemented, including a
synthetic capture -> observation -> no-order warmup rejection example. Milestone 2 now includes
entry/exit lifecycle records and opt-in funded paper-account reconstruction in the
[durable journal](docs/TRADE_JOURNAL.md). An opt-in [durable quote-only paper adapter](docs/DURABLE_PAPER_GATEWAY.md)
now integrates pre-fill buying-power/risk checks and persistent kill/daily-loss/peak checkpoints,
with atomic commit/crash tests. It uses ledger-derived balances rather than restoring the old broker.
The [bounded paper controller](docs/PAPER_RUNNER.md) now adds supplied-tick health gating,
per-tick risk marking and deterministic protective exits, with atomic recovery. The explicit-path
[capture replay bridge](docs/CAPTURE_PAPER_REPLAY.md) now verifies source bytes/configuration,
snapshot availability, gaps, event/receipt freshness and recorded reconnect warmup end to end.
The [capture supervisor and offline smoke workflow](docs/CAPTURE_SUPERVISION_AND_SMOKE.md) now add
bounded buffers/recordings, cancellation cleanup, fresh-session retry budgets and a zero-order,
explicit-source operator command. Verification is synthetic only; real feed recovery and a forward
paper service are not demonstrated. A [registered microstructure policy-to-case adapter](docs/MICROSTRUCTURE_POLICY.md)
now adds research-only bid-replenishment/CVD/OFI/liquidity proposals, explicit abstentions, after-cost
sizing and preliminary hard-risk checks. Its stateless shadow audit is not a backtester or automatic
paper promotion. A separate [bounded offline paper strategy adapter](docs/MICROSTRUCTURE_PAPER.md)
now uses ledger-derived risk, exits-first sequencing and explicit activation on every invocation,
with exact prefix resume and atomic failure recovery. It creates fresh paper cases, does not promote
research cases, and is verified on synthetic captures only. A separate read-only
[fixed-protocol paper evaluation report](docs/PAPER_EVALUATION.md) now adds cost-aware PnL, sampled
equity/drawdown, actual-fill statistics, cash control and explicit truncation/open-inventory handling.
It does not execute, promote or claim an edge. A separate registered
[multi-session paper campaign](docs/MICROSTRUCTURE_CAMPAIGN.md) now preserves funding, open lots and
risk history across a fixed offline source sequence, resets market features for each new capture,
and evaluates the continuous ledger without hiding disconnect valuation gaps. A separate
[receipt-causal event-label builder](docs/MICROSTRUCTURE_EVENT_LABELS.md) now emits versioned causal
features and costed hypothetical outcomes within each research source, without strategy-signal
selection or invented targets for censored windows. The [event-training data loader](docs/EVENT_TRAINING_DATA.md)
now verifies entire artifacts against source replay, freezes chronological whole-session assignments
from metadata and blocks both partitions on any source-quality failure. Reserved sources remain
unopened. The [bounded numerical baseline](docs/EVENT_BASELINE.md) now adds a metadata-frozen recipe,
training-only preprocessing, fixed-epoch NumPy fitting, controls/calibration diagnostics and pinned
JSON model reload. [Registered walk-forward evaluation](docs/EVENT_WALK_FORWARD.md) now refits that
recipe on expanding earlier-session prefixes, evaluates each later session once and withholds pooled
metrics if any planned fold is blocked. All verification and fitting so far are synthetic, not actual
market-data training. A [sealed model shadow adapter](docs/EVENT_SHADOW.md) now records non-executing
single-baseline probabilities on strictly later research sources, with availability/expiry and
source-reuse checks. It does not select or deploy a walk-forward fold. [Mechanical post-trade reviews](docs/POST_TRADE_REVIEW.md)
now separate structural process checks from verified outcomes and retain all cases as anecdotes.
Actual fitting and paper integration still require meaningful data/evidence gates. Next operational
gate: explicitly approved bounded public capture and zero-order smoke verification. Point-in-time
memory, independent reviews, final-fit policy and supervised forward operation remain development work.
Separately authorize a small capture/zero-order smoke check; supervised
forward-runtime verification remains necessary before deployment.
The default runtime remains unchanged;
no network service is running. Replay does not automatically choose a strategy or authorize training.
Quote fills are not validation of L2 execution quality.
This remains independent of the native Nautilus
blocker. Qwen's separately approved installation/smoke test is complete; do not expand it into
training or a service automatically. Do not yet install LangGraph, train on actual market data,
open reserved datasets, or implement live
connectivity. Operationally verify recorder timing/recovery/quotas before any unattended
capture campaign. Treat this as a data prerequisite alongside milestone 2, not permission to start
collecting. Keep the existing package layout; the proposal's 17 phases are a horizon, not a reset
of already completed work. UI, Obsidian, model/RL expansion and framework adoption are not blockers
for a minimal rule-based autonomous paper runtime.

## Delivery and verification contract

For each implemented slice provide changed paths, runnable code in the repository, exact Windows
commands, behavior/units, tests, actual results, known errors/fixes and what remains unproven.
Expected and observed output must be distinguished. Avoid dumping entire modules into chat.

Commands available now from the project directory:

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ai_trader.features.build_microstructure --help
.venv\Scripts\python.exe -m ai_trader.trading.runtime --mode paper --check
```

Expected behavior: clean lint/format, passing regression tests (CUDA smoke skip is valid without
CUDA), builder usage text, and a paper-mode availability check. No command above starts trading.
Future milestone-specific CLI commands will be documented only after they exist. Data sequence/
coverage errors require quarantine/resynchronization, not threshold loosening; invalid model JSON
means abstain; unknown execution state means reconcile; changed registration means a new recorded
trial, not overwriting the old one. Document each failure and the limit of its test evidence.

## Primary references and scope of reuse

- [TradingAgents](https://github.com/TauricResearch/TradingAgents): reusable architecture ideas,
  not evidence that its recommendation evaluation simulates crypto execution. The pinned local
  review in TRADINGAGENTS_REVIEW.md remains the source for previously inspected code. Preserve
  third-party notices if code is later imported; no upstream code is copied in this plan.
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence): separates
  per-run checkpoints from application memory stores. Our event/authority boundaries are additional
  requirements, not guarantees supplied by the library.
- [Qwen3-4B-Base](https://huggingface.co/Qwen/Qwen3-4B-Base) and
  [Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B): distinct local-model candidates. Model capability
  and trading usefulness must be evaluated; neither model card establishes a profitable policy.
- [Qwen3.5-4B-Base](https://huggingface.co/Qwen/Qwen3.5-4B-Base): additional benchmark candidate;
  the card describes pretrained-only artifacts with a vision encoder, not a drop-in guarantee
  of equivalent memory use or direct instruction-following. See review for metadata caveat.
- [NautilusTrader installation](https://nautilustrader.io/docs/latest/getting_started/installation/):
  candidate environment/version constraints; local integration and correctness remain untested.
