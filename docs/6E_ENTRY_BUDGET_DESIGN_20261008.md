# Declared entry budget assessment

The pure `six_e_entry_budget.py` API explains whether a supplied one-contract entry meets explicit hypothetical cash and realization-loss conditions. It does not approve trading, authenticate an account or mutate a reservation. The completed economics operator explains charges on a saved tape; this separate component consumes an asserted observed prefix before a proposal instead. Neither may modify the completed controls or remove losing or unaffordable fills.

Independent source review found no blockers. The final 61 constructed synthetic cases passed, including a caller-reseeding limitation check; whole-package Ruff and new-file formatting checks passed. Source SHA256 is `be3e0b924356b1090dff802cbb8be3059aec81002d550afebc8ef1ef475b72d6`; test SHA256 is `9f11db0fad45a27fd4e6d3d7fb173fa809ffbab039268a5adb70fde8df573376`. The subsequent complete suite passed 5,301 tests with three expected skips and no failures or errors. Complete JUnit, process-exit and unchanged-source verification is recorded in `docs/6E_DEVELOPMENT_WINDOW_20261008.md`. Every Python file stayed frozen through that verification. No historical assessment or replay integration was run.

## Python API

Import `DeclaredCapitalSnapshot`, `EntryProposal`, `DeclaredBudgetLimits` and `assess_entry_budget` from `ai_trader.research.six_e_entry_budget`. The seed, economics and margin types come from `ai_trader.research.six_e_declared_economics`.

```python
assessment = assess_entry_budget(snapshot, proposal, declared_economics, limits)
```

The immutable snapshot requires the typed original seed, declared realization balance, sequence/head, latest event time, observation frontier, inventory quantity, exit quantity/status and pending-entry Boolean. A genesis sequence has no last event, charge or liability. The proposal requires its decision time, exact expected prefix sequence/head, one supported dated 6E contract and quantity one. Limits explicitly supply cash buffer, maximum snapshot age and either a nonnegative net realization-loss ceiling or `None`. There are no broker defaults and no command that runs the bot.

Every result has status `declared_entry_budget_assessment_not_authenticated`. Its separate disposition is `declared_budget_available`, `declared_budget_insufficient`, `entry_blocked_by_liability` or `budget_undetermined`, with reason codes and retained inputs/arithmetic. `declared_budget_condition_met` describes the comparison only: true for a met declared budget, false for insufficient or liability-blocked cases, and null for undetermined cases. It is not an order or risk permission; every authority flag stays false.

Invalid types, inconsistent state, future frontiers, prefix mismatches and arithmetic overflow raise `ValueError`. A validated liability takes precedence over staleness and missing margin. Otherwise, a valid stale snapshot is undetermined; a fresh liability-free snapshot with missing margin is also undetermined. Missing margin leaves requirement and balance-less-requirement null. Explicit zero margin is different from missing margin and remains a declared zero, not a broker fact.

## Run a constructed example

Paste this block into PowerShell. It runs the pure function using an invented genesis snapshot, synthetic clock and placeholder head. The $100 seed, $10 initial margin, $5 maintenance margin, ten-cent fees and $1 buffer are toy amounts, not market data, broker requirements or suggested account settings. It creates no research artifact, order, reservation or model.

```powershell
Set-Location -LiteralPath 'C:\Users\pabta\Projects\ai-trader'
@'
from ai_trader.research.six_e_declared_economics import (
    EconomicSeed, DeclaredEconomics, DeclaredMargin,
)
from ai_trader.research.six_e_entry_budget import (
    DeclaredCapitalSnapshot, EntryProposal, DeclaredBudgetLimits,
    assess_entry_budget,
)

seed = EconomicSeed(
    initial_balance_usd_micros=100_000_000,
    initialized_at_ns=1_000_000_000,
)
head = "0" * 64  # Placeholder, not an authenticated journal head.
snapshot = DeclaredCapitalSnapshot(
    seed=seed, declared_realization_balance_usd_micros=100_000_000,
    sequence=0, tip_sha256=head, last_event_at_ns=None,
    observed_through_ns=1_000_000_000, remaining_position_contracts=0,
    reserved_exit_contracts=0, reservation_status=None, pending_entry=False,
)
economics = DeclaredEconomics(
    account_currency="USD", tick_value_usd_micros=1_000_000,
    entry_fee_usd_micros_per_contract=100_000,
    exit_fee_usd_micros_per_contract=100_000,
    margin=DeclaredMargin(
        initial_usd_micros_per_contract=10_000_000,
        maintenance_usd_micros_per_contract=5_000_000,
    ),
)
proposal = EntryProposal(
    decision_at_ns=1_000_000_000, expected_sequence=0,
    expected_tip_sha256=head, contract="6EM5", quantity_contracts=1,
)
limits = DeclaredBudgetLimits(
    cash_buffer_usd_micros=1_000_000, max_snapshot_age_ns=1_000_000_000,
    max_cumulative_realization_loss_usd_micros=5_000_000,
)
result = assess_entry_budget(snapshot, proposal, economics, limits)
print(result.status)
print(result.disposition)
print(result.declared_requirement_usd_micros)
print(result.declared_balance_less_requirement_usd_micros)
print(all(value is False for _, value in result.authority_flags))
assert snapshot.declared_realization_balance_usd_micros == 100_000_000
assert not snapshot.pending_entry
'@ | .\.venv\Scripts\python.exe -
```

Expected output:

```text
declared_entry_budget_assessment_not_authenticated
declared_budget_available
11200000
88800000
True
```

The requirement is $11.20: $0.10 entry fee, $10 margin, $0.10 exit-fee reserve and $1 buffer. The $88.80 remainder is hypothetical balance less requirement, not a debited balance or verified free cash. The final `True` means every authority flag is false; it does not mean permission to trade. The assertions confirm that the example left the original $100 snapshot and pending-entry state unchanged.

## Pure assessment boundary

The API consumes a typed capital snapshot, one entry proposal, explicit `DeclaredEconomics` and explicit budget limits. It returns a deterministic declared-budget explanation. No filesystem, historical prices, policy evaluation, model, broker connectivity, order generation, fills or account mutation belong in the core. Supplied timestamps, balances and journal hashes describe assertions; this pure function cannot authenticate them.

The snapshot needs the original seed balance and initialization time, the current declared realization balance, an observation frontier, ledger sequence/head and existing inventory, exit reservation and pending simulator entry. These must describe the prefix observed before the proposed decision, not the final post-hoc projection. The frontier describes asserted observation completeness, not merely the latest ledger-event time; it proves neither feed health nor native equal-time publication order. A proposal supplies its decision time, expected preceding sequence/head, declared futures contract and fixed quantity one. The expected prefix identity must match the snapshot. A separately declared maximum snapshot age bounds ordinary staleness; a future or incoherent snapshot is refused, and age exactly at the bound passes.

The stateless function cannot detect a caller who substitutes a new seed, balance or jointly matching prefix. It uses those declared values without authenticating their origin. Future integration must bind the original seed and complete observed prefix before admission. The explicit reseeding test demonstrates this limitation instead of claiming it is prevented by a pure arithmetic function.

Keep USD integer micro-dollars, exact types and bounded arithmetic. Reject Booleans masquerading as integers, floats, unsupported currencies and quantities, negative fees or buffers, malformed hashes and inconsistent liability fields. Initial margin must not be below maintenance margin. Do not add broker-cost defaults, automatic sizing or CFD conversion.

## Budget and liability rules

Existing inventory, any exit reservation, UNKNOWN or a pending entry blocks another entry. Changing the date or session cannot reset funding or release these liabilities. Entry refusal does not authorize refusing an exit or cancelling a reservation.

With no explicit margin declaration, report that the budget is undetermined. Do not substitute zero. When margin is declared, the pre-entry requirement is:

```text
hypothetical entry fee
    + hypothetical initial margin for one contract
    + hypothetical exit-fee reserve
    + explicit cash buffer
```

Compare the entire requirement against the pre-entry realization balance, retaining negative balances; balance equal to the requirement passes this arithmetic comparison. Reserved amounts are not paid fees. Assessment alone must not mutate that balance or claim that a reservation was made.

The future integration must bind one hypothetical admission and its pending liability to one proposal and expected prefix atomically before creating the pending entry. Consume its entry-fee reserve and debit the fee exactly once at the observed entry fill. Keep the exit-fee reserve and position-margin commitment through PENDING, UNKNOWN, session changes and reference updates; consume the exit-fee reserve and debit that fee only at an observed permitted exit fill. After that permitted full exit fill and fee debit, release the closed position's margin commitment and any admission-only buffer hold if the future integration models it as reserved. UNKNOWN and references never release those commitments. Release an unfilled admission only on an explicit simulator no-entry refusal, with no fee and no claim of broker cancellation. A pure assessor implements none of this lifecycle.

An optional explicitly declared cumulative realization-loss ceiling uses `max(0, original_seed_balance - current_realization_balance)`: net realization loss, including already charged fees, not the sum of losing trades. It also checks the hypothetical loss after the proposed entry fee alone, `max(0, original_seed_balance - (current_realization_balance - entry_fee))`. Equality with the explicit ceiling passes; exceeding it yields a named insufficient-budget reason. Reserves are not realized losses. Keep the original seed across sessions: no peak-equity drawdown claim or daily-loss reset. This arithmetic does not bound future stop losses, authenticate liquidation equity or prove maintenance-margin adequacy or gap-bounded risk.

Results distinguish declared requirement met, insufficient budget, liability blocked and budget undetermined. Every execution, broker/cash/margin confirmation, trading, training, independent-validation, scoring, risk-approval and promotion authority stays false, even when the arithmetic requirement is met.

## Synthetic verification

The passing cases cover exact funding equality and one-unit shortfall; loss-ceiling equality and entry-fee crossing; reserves versus fee charges; explicit zero and missing margin; negative balance and arithmetic overflow; fixed size; exact types; malformed snapshots and prefix mismatch; stale/future observations and age equality; pending-entry refusal; PENDING and UNKNOWN carry across days/contracts; unchanged supplied seed and net losses; caller-reseeding limits; input immutability; and forbidden filesystem/journal/source-hashing/model/quote/policy/planner hooks.

Independent source review checked typed nested validation, prefix/frontier consistency, bounded arithmetic, liability priority, loss comparisons, false authority and the absence of integration. The assessor takes entry proposals only and has no exit/refusal lifecycle to change. The complete-suite result remains separate from these focused tests. Future integration must ensure that a rejected entry cannot disable exits.

## Later prospective integration

A funded-assumption replay is a different experiment. Its source, assumptions, complete session cohort, pending-entry lifecycle, termination rules and fresh output paths must be registered before outcomes. Refusing one entry changes later inventory, cooldowns and opportunities; deleting unaffordable fills from an existing tape and summing the remainder is not a causal funded result.

The original one-second wait, unresolved contract, reference prices, source pins and completed results stay unchanged. Any different execution policy needs its own tested contract and new registration, not a retroactive repair selected to fill the already-known late quote. New results retain all decisions, losses, refusals and unknown outcomes; no closed-only subset becomes a complete return.

Actual available capital, broker margin and settlement, measured fees/slippage, feed/size evidence, cancellation certainty and EURUSD CFD execution remain external evidence requirements. The current exposed futures controls establish neither those facts nor model-training or promotion readiness.
