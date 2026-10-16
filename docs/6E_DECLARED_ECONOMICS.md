# Declared futures tape economics

The companion `src/ai_trader/research/six_e_declared_economics.py` projects explicit hypothetical cash charges over a supplied 6E event/receipt tape. It fills a gap between contract-tick accounting and a future funded simulator: entry fees are charged immediately, including when an exit never resolves. It does not create a funded account, route orders, run a strategy, select historical trades or train a model.

This is a pure Python API, not a command that runs the bot. Its separate registered wrapper is documented in `docs/6E_ECONOMICS_OPERATOR.md`; that companion's two verified toy projections are recorded in the development-window handoff. The original replay, targets, diagnostic reports and completed controls stay unchanged.

## Inputs and units

Call `project(plan, seed, assumptions)` with a typed `ReplayPlan`, `EconomicSeed` and `DeclaredEconomics`. Supply every amount explicitly; there are no broker fee, current margin or tick-value defaults. USD amounts are integer micro-dollars: one dollar is 1,000,000 units. Floats, Booleans, negative fees, zero funding/tick value and other account currencies are refused. Optional `DeclaredMargin` has fixed hypothetical initial and maintenance requirements, with initial not below maintenance.

The API supports the frozen one-contract simulator format and sequential positions. Partial or multiple-contract fills, imported delayed broker receipts and cancellation/reconciliation tapes are unsupported. The generic liability ledger supports some broader records, but this companion must not silently extend the original quote simulator.

All amounts describe caller-declared futures assumptions. They are not current CME specifications, measured broker charges, variation-margin settlement, available capital or cTrader EURUSD CFD economics. A dollar conversion of 6E ticks does not turn futures observations into broker EURUSD prices or fills.

## Cash conservation and open exposure

Every supplied event is retained in observation order, including session boundaries, references and unresolved exits. Entry debits the explicit entry fee. Exit credits its incremental gross contract-tick change multiplied by the declared tick value, then debits the explicit exit fee. The original extra round-trip tick remains a separate simulation comparator; it is neither split into entry/exit fees nor deducted again.

```text
declared realization balance
    = initial hypothetical balance
    + gross closed contract ticks × declared tick value
    - explicit entry fees - explicit exit fees
```

A negative realization balance is preserved with its shortfall and all subsequent events. The module does not stop at a convenient funded prefix or remove losing receipts. It cannot report a margin liquidation or determine whether the path could have been executed with the supplied seed.

An outstanding exit does not double the position's margin quantity. UNKNOWN, a new session and reference prices cannot release inventory or position margin. A fill after UNKNOWN cannot reconcile the frozen simulator. Complete declared equity and return stay null while inventory, reservations or pending simulator uncertainty remain. A standing or late reference price never marks an open position into a complete return.

If a margin assumption is supplied, the module shows its initial/maintenance amounts for remaining inventory and balance minus declared initial margin. This is arithmetic only, not measured free margin, liquidation equity or a maintenance-margin pass. With no margin assumption, those fields stay null rather than becoming zero.

## Declared consistency, not historical authentication

The projection checks complete ordered event/receipt binding, receipt content and hashes, typed transitions, session boundaries and the reconstructed terminal state/head. It derives the declared genesis from the supplied original source-key map without opening source files. It never reads quotes or decision features, evaluates policy, generates a fill or changes a ledger.

The result status is `declared_tape_economic_projection_not_authenticated`. It cannot authenticate the source map, the historical manifest, quote prices/cursors, causal policy choices or the checkpoint's full causal derivation. Use the existing original trial verifier for that separate responsibility. Even successful original reconstruction proves local simulation consistency, not broker execution.

Every execution, training, strategy-scoring, promotion, cash/margin confirmation, risk-approval and CFD-execution authority flag remains false. No projection becomes a label, a new result for the old trial or an independent validation score automatically.

## Verification and next integration

Synthetic tests cover fee timing, mirrored long/short conversion, profitable and losing closes, exact cash conservation, sequential positions, UNKNOWN carry, negative balances, unsupported scope, malformed amounts and receipts, terminal/head mismatches, and a pure no-filesystem/no-quote-access contract. All 134 cases passed in both the author's and root's final runs, including interoperability with the actual planner's synthetic closed position and UNKNOWN carry. Whole-package Ruff and formatting checks passed. Independent review found no remaining blockers. The production source is frozen at SHA256 `d45137f63c82afcce41d4214546d5ec1a1402487e8f91f02fd90d6617e627c85`. The full-suite result is recorded in `docs/6E_DEVELOPMENT_WINDOW_20261008.md`.

From PowerShell, run the synthetic tests without historical inputs:

```powershell
Set-Location C:\Users\pabta\Projects\ai-trader
.\.venv\Scripts\python.exe -m pytest -q tests/test_six_e_declared_economics.py
```

The separate economics wrapper now supplies explicit pinned assumptions, complete original verification, fresh output paths, canonical read-only verification and full coverage. A funded simulator still needs causal entry admission, actual risk limits, settlement/roll rules, measured costs and appropriate execution evidence. Neither integration may rewrite existing targets or manufacture closure for an unresolved position.
