# Declared entry admission and accounting lifecycle

The separate synthetic-only accounting component is implemented and independently reviewed. Root's focused verification passed 173 new constructed cases plus 195 unchanged adjacent economics/budget cases; Ruff and formatting checks passed. Complete source-frozen suite 6 passed 5,474 tests with three expected skips. Root reconciled every JUnit case, confirmed process exit and verified unchanged package, full source/test manifest and held file pins. This is not a funded historical backtest, a broker account, permission to trade or permission to train a model.

The existing entry-budget assessor explains a caller-supplied snapshot but cannot detect reseeding. The new component instead reconstructs declared capital and liabilities from one bound genesis and every preceding constructed record. No historical tape, price archive, model, order gateway or strategy is accessed.

The final expanded project suite 8 also passed 5,804 tests with three expected skips after the packet codec and read-only checker were added. Its complete case, process-exit and unchanged-source verification is recorded in `docs/6E_ADMISSION_DEVELOPMENT_WINDOW_20261008.md`. The admission source/tests remained unchanged throughout those additions.

## Bound declaration and complete prefix

The immutable genesis binds the original hypothetical seed, explicit USD economics, explicit budget limits, component version and synthetic scope. Consuming APIs require the expected genesis identity and the exact terminal sequence, head and asserted completeness frontier. Each event binds its preceding prefix; events remain in supplied order, including equal-time events. The reducer derives cash and liabilities rather than accepting a replacement balance or cached terminal state.

A fixed expected terminal witness distinguishes an omitted suffix from an intentionally shorter prefix. Canonical hashes only check local consistency. A caller can invent a complete new declaration or coherent fork; neither the original funding nor the source, account or feed becomes authenticated.

Every record explicitly declares its recording time and resulting completeness frontier; this narrow constructed contract requires them to be equal and nondecreasing. A clock-advance record can advance that assertion without changing accounting. An admission decision occurs at its recording time but is assessed against the preceding frontier before its own time becomes the new frontier, so the proposal cannot silently make its preceding snapshot fresh. Completeness is an assertion about the constructed prefix, not market-data freshness, feed health or native equal-time publication order.

Readiness is request time plus 100 ms; the deadline is that readiness time plus one second. The execution interval includes both endpoints. A prefix exactly at the deadline may still retain a pending entry or exit. A timeout refusal or UNKNOWN declaration is stamped exactly at that deadline, asserting completion of the equal-time boundary; append it before advancing the clock past the deadline. A clock or unrelated event cannot silently expire pending exposure. A full receipt must lie inside the original interval and have execution time equal to recording time, not a convenient later receipt time. A deadline receipt is allowed before the terminal declaration, never after it. These checks do not establish quote eligibility, depth, spread or broker fills.

## Pure API

Call `genesis_sha256`, `reconstruct` and `advance` in the separate `six_e_declared_admission.py` module. Genesis binds a scenario ID, `EconomicSeed`, `DeclaredEconomics` and `DeclaredBudgetLimits` plus the protocol scope and timing. Each `DeclaredRecord` has an event ID, exact preceding `DeclaredPrefix`, recording time, explicit completeness frontier and one typed payload. `reconstruct` verifies the full tuple against the expected genesis and terminal prefix. `advance` verifies the same complete preceding tuple before returning a new immutable tuple and derived state; it accepts no cached balance.

The seven payloads are admission request, entry receipt, explicit unfilled entry, exit request, exit receipt, UNKNOWN exit and clock advance. The five phases are FLAT, ENTRY_PENDING, OPEN, EXIT_PENDING and EXIT_UNKNOWN. Valid blocked or undetermined budget proposals remain recorded decisions without creating an admission. Malformed identities, duplicate events or receipts, unsupported payloads, wrong timing, omitted suffixes and overflow are errors, not silently repaired outcomes.

Event, admission, exit-request and receipt identities remain unique across the complete prefix within their typed namespaces. An ID-independent canonical receipt-content fingerprint is also tracked: it excludes the user-chosen receipt ID but binds the local declared genesis, phase, matching liability, contract, quantity, time and price. Renaming a receipt cannot bypass that content check or the phase that accepts its matching fill exactly once. These hashes do not authenticate external evidence. Derived views retain cumulative gross realization and both fees, signed balance, shortfall, all commitments and every typed liability.

## One-contract lifecycle

The component supports sequential constructed positions with one supported dated 6E contract and full quantity one. It accepts declared receipts, not raw quotes, and never generates a fill or proves that a receipt was the first eligible quote. The original 100 ms delay and inclusive one-second execution wait are not extended. Partial fills, extra quantity, settlement, roll conversion, deposits and funding resets are unsupported.

Let C be declared realization balance, E the entry fee, M the initial margin and X the exit fee. The explicit cash buffer B is a floor used once at admission; it is not paid or separately held.

| Constructed transition | Declared balance | Remaining commitments |
| --- | --- | --- |
| Admission creates pending entry | C | E + M + X |
| Permitted matching entry receipt | C - E | M + X |
| Explicit unfilled simulator refusal | C | 0 |
| Exit intent | unchanged | M + X |
| Exit becomes UNKNOWN | unchanged | M + X |
| Permitted full receipt while exit is PENDING | C + gross ticks times declared tick value - X | 0 |

Admission requires C to cover E + M + X + B and applies the frozen net-realization-loss comparisons: current loss is max(0, original seed minus C), and hypothetical loss after the proposed entry fee is max(0, original seed minus (C - E)). Exact cash and loss-ceiling equality passes the declared comparison. Consuming the entry-fee reserve while charging that fee keeps balance less commitments unchanged. Margin is counted once despite an exit reservation. Reserves, margin and buffer are never charged as fees; the old extra round-trip tick is never deducted again.

Zero numeric commitments do not mean no liability: a pending entry, open contract or UNKNOWN identity still blocks a new admission. Missing margin remains undetermined rather than becoming a declared zero. Valid exits are not blocked by an entry cash or loss limit. Negative realization balances are retained.

An explicit unfilled refusal releases only its own pending admission and charges no fee. This is not a broker cancellation claim. UNKNOWN is terminal under the frozen simulator: later fills, cancellation or reconciliation cannot close it or release its margin or exit-fee commitment. Date, contract and reference changes do not reset the seed or resolve exposure. Complete equity and return remain null while any pending or open liability exists.

## Run a constructed example

Paste this block into PowerShell. It declares one flat-price round trip with invented prices, times and costs. The $100 seed, $10 initial margin, $5 maintenance margin, ten-cent fees, $1 buffer and $1 tick value are toy assumptions, not broker or CME measurements. No data, quote selection, strategy, order, persistent account, model or output file is created. Input money remains exact integer micro-dollars; division below is display only.

```powershell
Set-Location -LiteralPath 'C:\Users\pabta\Projects\ai-trader' -ErrorAction Stop
@'
from ai_trader.research import six_e_declared_admission as a
from ai_trader.research.six_e_declared_economics import (
    EconomicSeed, DeclaredEconomics, DeclaredMargin,
)
from ai_trader.research.six_e_bracket_targets import TICK

start = 1_000_000_000
g = a.DeclaredAdmissionGenesis(
    "constructed-guide-example",
    EconomicSeed(100_000_000, start),
    DeclaredEconomics(
        "USD", 1_000_000, 100_000, 100_000,
        DeclaredMargin(10_000_000, 5_000_000),
    ),
    a.DeclaredBudgetLimits(1_000_000, 1_000_000_000, 5_000_000),
)
pin = a.genesis_sha256(g)
records = ()
state = a.reconstruct(
    g, records, expected_genesis_sha256=pin,
    expected_terminal=a.DeclaredPrefix(0, pin, start),
)

def append(event_id, at, payload):
    global records, state
    result = a.advance(
        g, records, a.DeclaredRecord(event_id, state.prefix, at, at, payload),
        expected_genesis_sha256=pin, expected_terminal=state.prefix,
    )
    records, state = result.records, result.state
    assert all(value is False for _, value in state.authority_flags)
    return result

append("event-1", start, a.AdmissionRequested("admission-1", "6EM5", "long", 1))
assert state.total_commitments_usd_micros == 10_200_000
assert state.available_balance_usd_micros == 89_800_000
price = 20_000 * TICK  # Constructed value, not a market quote.
entry_at = start + 100_000_000
append("event-2", entry_at, a.EntryReceipt(
    "admission-1", "entry-1", "6EM5", "long", 1, price, entry_at,
))
assert state.declared_realization_balance_usd_micros == 99_900_000
assert state.available_balance_usd_micros == 89_800_000
append("event-3", entry_at, a.ExitRequested("admission-1", "exit-1"))
exit_at = entry_at + 100_000_000
append("event-4", exit_at, a.ExitReceipt(
    "exit-1", "receipt-exit-1", "6EM5", 1, price, exit_at,
))
assert state.phase == "FLAT"
assert state.declared_realization_balance_usd_micros == 99_800_000
assert state.complete_declared_net_return_usd_micros == -200_000
assert a.reconstruct(
    g, records, expected_genesis_sha256=pin, expected_terminal=state.prefix,
) == state
print(state.phase)
print(f"Declared balance (USD): {state.declared_realization_balance_usd_micros / 1_000_000:.2f}")
print(f"Declared net return (USD): {state.complete_declared_net_return_usd_micros / 1_000_000:.2f}")
print("All authority flags false:", all(value is False for _, value in state.authority_flags))
'@ | .\.venv\Scripts\python.exe -
if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Constructed example failed or did not launch; do not continue.' }
```

Expected output is `FLAT`, declared balance `99.80`, declared net return `-0.20`, and all authority flags false `True`. The flat-price example loses only the two declared fees; it is not a historical or broker result. The buffer is not charged or reserved, and the unchanged available amount at entry confirms consumption of its already-held fee reserve.

## Verification boundary

Before calling this increment verified, require independent source review, constructed adversarial tests, Ruff, formatting checks and a complete source-frozen project suite. Cases must cover prefix drift and omissions, fee conservation, equality and overflow, timing, explicit refusals, duplicate receipts, zero-valued commitments, negative closes, UNKNOWN carry, unsupported transitions, poisoned immutable inputs and forbidden integration hooks.

All authentication, execution, broker/cash/margin confirmation, risk approval, trading, training, scoring, independent-validation and promotion authorities remain false. A later causal funded-assumption replay needs its own tested integration and registration before outcomes. Removing unaffordable fills from an old tape cannot manufacture a funded result.
