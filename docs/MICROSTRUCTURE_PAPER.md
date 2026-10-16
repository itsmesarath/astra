# Explicit offline microstructure paper simulation

Implemented 2026-09-24 in `trading/microstructure_paper.py`. This connects the registered
order-book/CVD/replenishment hypothesis to the durable paper controller using actual simulated
account state. It is an **offline, bounded experiment**, not a forward paper service, promoted
strategy, L2 execution backtester or live-account adapter. No model or network client is involved.

## Authority and inputs

Every invocation, including resume, requires `--enable-paper-simulation` (Python API:
`enable_paper_simulation=True`). This permits local simulated fills only. Registration still has
`research_only` / `promotion_allowed: false`; the research evaluator and its stored cases remain
unchanged and cannot be submitted to the paper journal. This adapter creates fresh paper cases
from current ledger-derived assessments; it never imports an old research approval.

Supply one explicit registration, research source session, capture path and dedicated journal.
The adapter verifies registered code/environment, source hash, header/footer times and configuration.
Unknown/reserved sources are refused before capture or journal access. No directories are scanned,
holdouts opened, capture campaign started, strategy selected or parameters fitted. Registration
is local consistency metadata, not a signed authorization or proof of independent preregistration.

A new journal uses registered starting cash and the first causally available snapshot time.
The immutable run ID binds adapter version, registration and source session. Resume requires the
same seed/configuration and never resets cash, inventory, day-loss baseline, peak equity or kill
switch. The existing zero-order smoke command is separate; this adapter does not disarm it or
reuse its journal. New experimental paper accounts start with the gateway's normal inactive kill
switch, only after explicit activation; existing kill state is preserved on resume.

## Tick ordering and risk

For each receipt-causal replay frame:

1. Mark the current ledger with a healthy quote, or advance its risk clock without an unsafe mark.
2. Process protective exits before consulting entry policy.
3. On a protection/blocked-exit tick, record NO_ACTION and prohibit same-tick re-entry. Otherwise
   assess the frozen hypothesis against current cash, inventory, realized daily PnL, peak equity,
   kill switch and unresolved-order state from the journal.
4. Bind a fresh paper case to the source, observation, tick time, risk configuration, full replay
   frame, activation identity and immutable decision-context fingerprint.
5. Let the existing controller and gateway independently check entry health, cash and hard risk;
   atomically store case, marks, orders, simulated outcomes and tick result.

The signal still requires bid absorption/repeated replenishment, positive rolling CVD, OFI, book
imbalance and bid-side liquidity, with opposing ask absorption as a veto. These are uncalibrated
heuristics, not verified hidden-order identities or evidence of profitability. Existing inventory
or unresolved orders prevents another entry. Failed signals, abstentions and rejections are retained.

Protection follows the controller's daily-loss, drawdown, stop, take-profit and maximum-hold
priority. It remains independent of entry kill switches, feature warmup and trade freshness.
Kill means block entries, not automatically liquidate. Stops are triggers: a gap fills at the
available simulated bid minus slippage, not an invented stop price. Unsynchronized/stale quotes
block execution and leave inventory visible. The capture footer does not force liquidation.

Entry policy is not called during protection. The underlying case-builder seam is trusted
synchronous Python, not a security sandbox; it must not perform IO or mutate state. Detected
SQLite mutations, mismatched cases or coroutine returns fail and roll back. Exceptions roll back
local simulated outcomes only; this contract must never be assumed to undo external live orders.

## Bounds, retries and reporting

`max_frames` is an absolute prefix budget of 1–10,000 frames, **including previously committed
frames**. Resume with a larger budget to extend a prefix. Exact retries reuse stored cases/results,
not a new historical assessment using later balances. Changed frame/activation evidence conflicts.
One invocation commits atomically, including any new protective fills. A failure preserves earlier
committed invocations. A first-invocation failure can leave a metadata-only journal without an
account; retain it for diagnosis and explicitly select a new destination. There is no automatic
deletion, repair or reset. Source/environment drift also fails closed.

JSON reports distinguish two scopes:

- `frames_processed`, `session_consumed`, market faults, case/health counts and order IDs with
  `_in_prefix` describe the requested prefix. `blocked_exit_entry_ids_at_prefix_end` is historical
  if a smaller prefix is requested on retry.
- `ledger_order_count`, cash, position, cost basis, fees, realized PnL, kill state and
  `ledger_observed_at_ns` describe the **latest committed ledger**. They can include later ticks
  than a smaller requested prefix. A retry does not rewind the account.

A detected sequence/feed fault is retained, not retroactively removed from earlier decisions.
The CLI prints its report and exits 2 for market faults; 0 can still mean incomplete coverage or
no trades. Other failures raise without a success report. No independent failed-attempt journal
exists yet; retain error output. Neither exit code means profitable, promoted or training-ready.

## Commands and verification

These checks use help text or synthetic temporary fixtures only:

```powershell
.venv\Scripts\python.exe -m ai_trader.trading.microstructure_paper --help
.venv\Scripts\python.exe -m pytest -q tests/test_microstructure_paper.py tests/test_paper_case_builder.py
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q
```

The following is a template, **not a command executed during development**. Replace placeholders
only with explicitly selected, approved research inputs and an unused output path. The registration
workflow is in [the research-policy guide](MICROSTRUCTURE_POLICY.md).

```powershell
.venv\Scripts\python.exe -m ai_trader.trading.microstructure_paper --registration data/processed/NEW_REGISTRATION.json --capture data/raw/SELECTED_RESEARCH.jsonl --source-session DECLARED_RESEARCH_SESSION --journal data/processed/NEW_PAPER.sqlite --max-frames 1000 --enable-paper-simulation
# Extend the same prefix: repeat with --resume and a larger --max-frames, keeping activation explicit.
```

Synthetic tests cover hand-computed fees/slippage/PnL, targets, exact/gapped stops, maximum hold,
blocked exits, open footer inventory, repeated signals, actual realized-loss rejection, kill
preservation, independent gateway veto, no-trade control, exact/conflicting retries, explicit
activation on resume, reserved-source rejection, async/mutating builders and transactional failures.
See [the research log](../RESEARCH_LOG.md) for verified suite results.

## Remaining limits and next step

Quote-only immediate full fills do not model order-book depth consumption, queue position,
latency, partial fills or market impact. Its execution report remains a ledger/prefix summary;
the separate [read-only evaluation command](PAPER_EVALUATION.md) now adds sampled bid equity/returns,
drawdown, closed-trade statistics and a cash control, with explicit unknown terminal valuation.
Neither command forces liquidation. Realized PnL and cash alone are not total profitability when
inventory remains open. Strict numerical precision limits fail closed; unsupported amounts are not
rounded into passing risk checks.

This single-source API covers one registered capture. A separate
[multi-session campaign API](MICROSTRUCTURE_CAMPAIGN.md) now preserves funding/positions/risk across
a fixed declared source sequence, using its own dedicated journal and global prefix budget. Neither
API advances beyond the current 10,000-frame cap. Account reconstruction is correctness-first, not
high-throughput; no real-time throughput, supervision or overnight recovery is demonstrated.

The fixed-protocol, cost-aware [lifecycle evaluator](PAPER_EVALUATION.md) is now implemented and
tested synthetically. Next: separately authorize and verify a small public capture/zero-order smoke
run, then verify a supervised forward runtime and build event-label datasets. Model training and
Qwen integration remain separate gated stages; no data download, model training, reserved-source
evaluation or live connectivity was performed for this slice.
