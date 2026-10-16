# Registered multi-session paper continuity

Implemented 2026-09-24 in `trading/microstructure_campaign.py` and
`research/campaign_evaluation.py`. This extends the [offline paper adapter](MICROSTRUCTURE_PAPER.md)
to a fixed sequence of captures with one funded account and one risk history. It simulates recorded
session transitions; it is **not a supervised forward WebSocket service or permission to trade live**.

## Explicit scope and limits

A campaign requires a [research registration](MICROSTRUCTURE_POLICY.md) containing 2–32 research
sessions followed by its reserved declarations. Supply **every research source exactly once, in
declared chronological order**, as `CampaignInput(source_session, Path(...))`. Missing, reordered,
duplicate, unknown and reserved selections fail before capture stat/read access. Registered times
cannot overlap and capture hashes cannot be aliased across names/roles. The reserved declarations
remain metadata only; their data are not opened.

All selected research captures undergo hash/framing/time checks before the journal is created or
extended. There is no directory discovery, automatic skip of a failed source or selection based on
its profitability. Capture bytes are pinned in memory for that invocation. The aggregate input-byte
budget is 64 MiB, checked against file sizes and again against actual bytes read; existing per-file
32 MiB, record and line-size limits still apply. This bounds inputs, not total interpreter/parsed-data
memory or hard real-time latency. All selected files must remain available on resume/evaluation.

The registration freezes source inventory, policy, feature/risk/cost settings, initial cash and
code/environment fingerprints. Its immutable identity plus campaign version binds the new journal.
A different registration needs a new run; neither adding sources to an existing campaign nor
converting an existing single-session journal is supported. Local hashes are consistency checks,
not authentication, a trusted preregistration service or a physical holdout lockbox.
Case IDs remain scoped to their journal run; do not merge cases from single-session and campaign
runs by case ID alone, since their ledger-derived context can differ.

## Account continuity versus market-state reset

The shared executor funds the account **once**, at the first capture's snapshot-availability time.
Every subsequent capture creates a fresh book and feature engine: depth/trade sequence baselines,
CVD, attribution intervals and entry warmup reset. Cash, entry lots, cost basis, realized PnL,
sampled equity peak, original stop/target/holding plans and kill state do not reset.

A footer disconnects the book. Existing inventory remains open and protection is blocked until a
fresh snapshot is bridged by a usable depth update. Snapshot-only prices cannot execute. At the
first synchronized, fresh quote, existing stop/target/drawdown/holding-time protection takes priority
even while the new session's entry features are still warming. Entry policy is skipped on protection
ticks and same-tick replacement entries remain prohibited. Gaps fill at the new simulated bid minus
slippage, not an invented price from the previous session or the original stop level.

Holding time includes downtime, not just time spent inside capture files. Daily realized-loss state
resets only under the existing UTC-day rule, not when a new capture starts; the baseline becomes the
previous cumulative realized PnL. Equity peak and kill state survive UTC rollover. Entry fees remain
in cost basis and daily realized PnL follows the gateway's documented accounting convention.
Kill blocks new entries but does not block risk-reducing exits. None of this guarantees protection
while quotes are unavailable; no hidden price interpolation or timer-driven exit runs between files.

## Activation, restart and transactions

Every simulation call, including resume, requires `enable_paper_simulation=True` /
`--enable-paper-simulation`. This authorizes local quote fills only. Research registrations/cases
are not promoted and no live adapter or credentials are used. The fresh account uses the existing
gateway's inactive initial kill state; resume preserves the current stored kill state.

`max_frames` is an absolute **global prefix** budget of 1–10,000 frames across all sources, including
already committed frames, snapshots and footers. Reconstruct from the first capture each time;
increase the budget to extend the prefix. The campaign API refuses a budget smaller than its already
committed tick count. Recorded tick IDs must match the exact chronological prefix. Exact retries
reuse original cases/results without recomputing historical policy against later balances.

One invocation is atomic across session boundaries. A failure in the next capture rolls back that
invocation's new marks/cases/simulated fills, preserving previously committed prefixes and inventory.
A first-invocation failure may leave a metadata-only journal for diagnosis; there is no automatic
repair/deletion/reset. These are SQLite paper outcomes only: database rollback cannot undo a live
order. No schema migration or user-journal modification was performed during development.

Simulation reports retain existing account fields and add `campaign_version`, `campaign_consumed`
and a `source_sessions` list with each source's hash, frames, faults and completion. Unvisited sources
are explicitly incomplete. `session_consumed` is a compatibility alias for whole-campaign completion;
finishing an early source is not completing the campaign. `source_session` is null because the result
is multi-source. Market faults remain in the report even if a later fresh capture restores health.

## Continuous evaluation, including blind intervals

The new read-only evaluator reuses the [fixed cost-aware protocol](PAPER_EVALUATION.md) against the
same source list, one account and the entire committed prefix. It never executes the strategy or
mutates the journal. Initial funding, cash benchmark, PnL, exposure and sampled drawdown are not
restarted at a session boundary. Exposure includes disconnect intervals while inventory is held.

Open inventory at a footer/new unbridged snapshot has unknown equity. The first usable later quote
does not retroactively fill those gaps. A run can end flat with known final PnL but still have an
incomplete drawdown path. In that case the strict comparison gate remains false. Completed/open lots,
failures and missing values must all be retained in broader research, not cherry-picked away.

`full_campaign_flat_comparison_available` aliases the shared evaluator's
`full_session_flat_comparison_available` field for clarity. It requires every source consumed, no
market faults, a fully valued sampled path and a flat terminal account. This is not a promotion,
profitability or statistical-significance gate. All outputs still prohibit automatic promotion/live use.

## Commands and synthetic verification

Safe checks that use help text or temporary synthetic fixtures:

```powershell
.venv\Scripts\python.exe -m ai_trader.trading.microstructure_campaign --help
.venv\Scripts\python.exe -m ai_trader.research.campaign_evaluation --help
.venv\Scripts\python.exe -m pytest -q tests/test_microstructure_campaign.py
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q
```

Templates only—**not executed against actual market data during development**. Supply all registered
research sources in order, repeat `--source SESSION PATH` for additional files, and quote paths
containing spaces. Parents must already exist; first simulation must use a new journal path.

```powershell
.venv\Scripts\python.exe -m ai_trader.trading.microstructure_campaign --registration data/processed/CAMPAIGN.json --source RESEARCH_ONE data/raw/ONE.jsonl --source RESEARCH_TWO data/raw/TWO.jsonl --journal data/processed/NEW_CAMPAIGN.sqlite --max-frames 1000 --enable-paper-simulation
# Resume: same command and inputs, plus --resume and a larger global --max-frames.
.venv\Scripts\python.exe -m ai_trader.research.campaign_evaluation --registration data/processed/CAMPAIGN.json --source RESEARCH_ONE data/raw/ONE.jsonl --source RESEARCH_TWO data/raw/TWO.jsonl --journal data/processed/NEW_CAMPAIGN.sqlite --max-frames 1000
```

Simulation prints JSON then exits 2 for an incomplete campaign or market faults; 0 only means the
declared replay completed without those faults, not that it ended flat/profitable. Evaluation prints
JSON then exits 2 when its strict comparison is unavailable; 0 can describe losses or no trades.
Other exceptions fail without a success report. No report/output files are silently overwritten.

Tests cover two/three-source prefixes, funding/peak/kill continuity, fresh CVD/warmup, first-quote
protection, stop/hold downtime, same-day loss and drawdown vetoes, UTC rollover, recorded gap recovery,
exact retries, changed registration/tick order, atomic cross-session failure, input/byte budgets,
protected-source rejection, read-only global accounting and CLI status. See the
[research log](../RESEARCH_LOG.md) for exact regression results.

## Next work

This remains a finite offline experiment with a 10,000-frame global cap, correctness-first
reconstruction and quote-only full fills. It does not establish operational reconnect reliability,
L2 fill realism, strategy edge, an unattended paper service or a training-ready dataset.

The separate [event-label builder](MICROSTRUCTURE_EVENT_LABELS.md) now adds receipt-causal,
source-local hypothetical outcomes with explicit censoring. A [verified loader and whole-session fold
manifest](EVENT_TRAINING_DATA.md) now guard their use. The separate [numerical baseline](EVENT_BASELINE.md)
implements opt-in research fitting/evaluation, verified on synthetic data only and not wired to execution.
Next: separately authorize a small public capture/zero-order
smoke check and verify the supervised forward runtime.
Training or local Qwen integration requires usable data and evaluation gates; no model was trained,
real capture opened or live-account connectivity added in this slice.
