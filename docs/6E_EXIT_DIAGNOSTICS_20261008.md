# Continuous replay exit diagnosis and carry controls

All 20 exits in the original continuous replay were verified against their native quote intervals and simulator receipts. Nineteen used the first allowed quote; one has an empty execution window. A new three-session control kept that unresolved position into the next day and blocked further entries instead of resetting the account. The complete strategy result remains unknown.

The controls are offline accounting checks on already-exposed development sessions, not independent validation, broker fills, cTrader EURUSD PnL or a training dataset. No model was fitted or called. The original source, targets and completed outputs remain unchanged.

## Why the exit stayed unresolved

The original long entry occurred at 12:04:28.743178638 UTC on 27 March 2025. None of the 66 observed quotes during its holding path reached a bracket threshold. The 15-second timer therefore requested an exit. The simulator then required a newly completed quote after its 100 ms execution delay and within an inclusive one-second wait.

| Observation | Native cursor | UTC time on 27 March 2025 |
| --- | ---: | --- |
| Entry | 7867 | 12:04:28.743178638 |
| Last quote before exit intent | 7932 | 12:04:41.845689921 |
| Timer exit intent | — | 12:04:43.743178638 |
| Execution becomes eligible | — | 12:04:43.843178638 |
| Inclusive wait deadline | — | 12:04:44.843178638 |
| First excluded later quote | 7933 | 12:04:46.381589056 |

No quote occurs in the execution interval. The update gap is 4.535899135 seconds, and the next update arrives 1.538410418 seconds after the deadline. The prices around the gap are identical: bid 1.08360 and ask 1.08365. This proves absence of a fresh recorded update under the frozen rule, not absence of standing liquidity or a failed broker order. It supplies neither available size nor transport-health evidence.

The late quote is a retrospective reference only. It does not reconcile `UNKNOWN`, release inventory, provide realized return or justify choosing a longer wait after seeing this case.

## Complete exit diagnostic

`src/ai_trader/research/six_e_exit_diagnostics.py` supplies a standalone `inspect` command and a read-only `verify` command. Before describing exits, it verifies the complete original trial, inputs, journal, receipts and terminal state. It then joins every exit intent to its entry and original outcome, and compares every resolved receipt to the exact first native candidate.

Seventeen intents were bracket-triggered and three were timer-triggered. All 20 are retained, including the unresolved exit and losing trades. Each descriptor contains the published reference at intent, a separately named retrospective reference strictly before readiness, the complete inclusive candidate count, its first candidate, and the first strictly post-deadline quote if the declared input window contains one.

A timer fires before any quote at its exact timestamp. A bracket intent includes its triggering native cursor but excludes a later equal-time suffix. Quote ordering is never sorted or collapsed to a timestamp-only state. The diagnostic does not infer overnight quotes or substitute another dated contract.

Optional output must be a new JSON file under `logs`; unsafe, linked or existing targets are refused before historical input access. Writing uses exclusive creation. Verification re-creates the entire report and compares its canonical bytes, including all source pins, exit descriptors, terminal state and false-authority flags. Updating the hash of a truncated, edited or noncanonical report does not make it the original result.

The saved report is `logs/6e_exit_quote_diagnostics_20261008_1.json`. Its SHA256 is `b981417dde93f745ce0e950f09cf64f5ec42328e31ca9557a017835e21466609`. It pins all 45 original trial implementation sources plus the new diagnostic module. The diagnostic source SHA256 is `7cb5b5eb3a8de0a129da6588f0e5cc092a8ade93b9597d11f4b5cc5c514f8f27`.

Run the existing report's verifier from PowerShell without writing or starting a new simulation:

```powershell
Set-Location C:\Users\pabta\Projects\ai-trader
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_exit_diagnostics verify --registration logs/6e_continuous_liquidity_20261008_1_registration.json --registration-sha256 05e238e2ff0ef62417ad3ba19e946a5ad6bab446a794af4d5a360f366f320eea --completion-sha256 b4a94815f4dae2c62f11d72920cb721a5bc0376ca3f4f3a10121dbfadaf4e3d9 --report logs/6e_exit_quote_diagnostics_20261008_1.json --report-sha256 b981417dde93f745ce0e950f09cf64f5ec42328e31ca9557a017835e21466609
```

Expected status is `verified_all_exit_diagnostic_artifact_not_reconciliation`: two sessions, 22,311 decisions, 1,229,040 quotes, 20 exit intents, the original terminal journal head, and all authority flags false.

## Three session carry and no trade controls

Both controls were registered before either new simulation. They use the exact first three accepted train sessions, 26–28 March 2025, all dated `6EM5`, with complete 12:00–16:00 UTC windows. Their source pins and input manifest match exactly: 33,966 decisions and 1,985,498 quotes. No dates were selected for profitable outcomes, and no parameter or execution deadline changed.

| Control | Closed positions | Known closed net contract ticks | Inventory at end | Complete simulated return |
| --- | ---: | ---: | --- | --- |
| Fixed liquidity follow | 19 | -33 | One long contract with `UNKNOWN` exit | Unavailable |
| No trade | 0 | 0 | Flat | 0 contract-ticks |

On 28 March the liquidity control consumed all 11,655 decisions and 756,458 quotes. It recorded 2,090 ineligible decisions and 9,565 inventory-blocked decisions. It made no new entry and preserved the original entry identity and unresolved reservation. The later reference did not close the position. Its complete journal contains 68 events and 39 receipts; the no-trade control contains six boundary events and no receipts.

The two known closed totals are not a profitability comparison. One strategy has unresolved exposure and an unavailable complete return; the no-trade control simply demonstrates a flat-account accounting baseline. The controls do not establish measured costs, capital, margin, queue position, transport health or CFD execution.

| Evidence | SHA256 |
| --- | --- |
| Shared input content manifest | `671dc27bd96a00e1391be7e58f14cdea5df8cf977993f96fcc4a251273648e10` |
| Carry registration | `b47904547b9b2a31fdca997f0e236794a99f4ff3084e83172d9ec9faaccfbe8c` |
| Carry completion | `f95d3b50a5fba7c54f5aba40ef0dbc945068362f23a0165716f111aee8ac2ea8` |
| Carry verification receipt | `423d6e42f6854c72a978e4074c83e37e4c8abe88c41654a59b413042c8ff9e17` |
| No trade registration | `0fd32bcaf6cafd458ece139091c03c6f00a216a9100098044d873ef09ab5b00b` |
| No trade completion | `b4c5a08b57ddb8f1ee900590453900a30d0e7f7b0ab7ef18d6572db79980c54e` |
| No trade verification receipt | `71b9fdeb241372b1ea0127a24a7d5fedb9862797d411c5d2ab943bc676a6da39` |

Their output directories are `data/processed/6e_continuous_carry_20261008_1` and `data/processed/6e_continuous_no_trade_20261008_1`. Both passed separate read-only CLI reconstruction after their run-time verification. Do not rerun or overwrite these registrations. Their existing evidence can be rechecked with:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_continuous_trial verify --registration logs/6e_continuous_carry_20261008_1_registration.json --registration-sha256 b47904547b9b2a31fdca997f0e236794a99f4ff3084e83172d9ec9faaccfbe8c --completion-sha256 f95d3b50a5fba7c54f5aba40ef0dbc945068362f23a0165716f111aee8ac2ea8
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_continuous_trial verify --registration logs/6e_continuous_no_trade_20261008_1_registration.json --registration-sha256 0fd32bcaf6cafd458ece139091c03c6f00a216a9100098044d873ef09ab5b00b --completion-sha256 b4c5a08b57ddb8f1ee900590453900a30d0e7f7b0ab7ef18d6572db79980c54e
```

## Execution evidence coverage

The companion `src/ai_trader/research/six_e_execution_evidence.py` now checks which execution claims the diagnostic can support. Its pure `assess` function checks declared consistency only; it never authenticates a caller's supplied verification status. The operator `inspect` first reconstructs the complete pinned original diagnostic. A separate `verify` command then compares the entire saved canonical report with a fresh reconstruction.

All 60 new synthetic cases passed, including cursor/content binding, timer and bracket references, complete candidate counts, closed-contract cost math, execution watermark, open-position/reservation linkage, unsafe paths, source drift and repinned report tampering. Ruff and formatting checks passed. Independent review found no remaining blockers. The assessor source is frozen at SHA256 `7c5685551dd0f4a21e8a4595c05145bae7d61f5c42e8a3468abb83465a257578`.

The actual coverage report, `logs/6e_execution_evidence_20261008_1.json`, passed a separate read-only CLI verification. Its SHA256 is `2b570cbe9426aeba1b263beebdf5d0d1089f9f8d13534c3b1029eaca5603baaf`. It retains all 20 exits, 22,311 decisions, 1,229,040 quotes, the original journal head and the unresolved long position. Complete simulated return remains null. It adds no fills or reconciliation.

Six missing evidence categories apply to prospective external execution claims: local transport/publication, source-sequence continuity, size at the execution cursor, measured order latency, independent receipts/reconciliation, and futures-to-CFD execution mapping. No broker orders or receipts are expected in this offline trial. These are requirements before making future execution claims, not accusations that an offline quote simulator lost real orders. Vendor timestamps, quiet quote updates, log-depth features sampled at a decision, fixed delays and local receipt hashes do not satisfy those requirements.

Recheck the saved report without changing it:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_execution_evidence verify --registration logs/6e_continuous_liquidity_20261008_1_registration.json --registration-sha256 05e238e2ff0ef62417ad3ba19e946a5ad6bab446a794af4d5a360f366f320eea --completion-sha256 b4a94815f4dae2c62f11d72920cb721a5bc0376ca3f4f3a10121dbfadaf4e3d9 --diagnostic logs/6e_exit_quote_diagnostics_20261008_1.json --diagnostic-sha256 b981417dde93f745ce0e950f09cf64f5ec42328e31ca9557a017835e21466609 --report logs/6e_execution_evidence_20261008_1.json --report-sha256 2b570cbe9426aeba1b263beebdf5d0d1089f9f8d13534c3b1029eaca5603baaf
```

Expected status is `verified_execution_evidence_coverage_artifact_external_execution_blocked`; all authority flags remain false.

## Verification and next work

The new diagnostic passed 55 synthetic tests with one skip for unavailable Windows symlink-creation privileges. Tests cover deadline equality, native equal-time ordering, timer priority, widened exits, unknown carry, input and source drift, path guards, all-exit coverage, read-only inspection and repinned report forgeries. A separate regression passed 600 existing replay, ledger, quote-research and paper-account tests. All 38 JavaScript tests passed; Ruff and formatting checks passed. These focused runs do not replace the full project suite.

The first full suite encountered Windows Application Control's `WinError 4551` in the main `.venv`. A later fresh main import succeeded at 10:31 UTC; all three existing NumPy/CPU/CUDA smoke tests and DBN/Zstandard/PyArrow imports then passed. The dedicated `.venv-qwen-train` also imports PyTorch `2.14.0+cu132`, but lacks the full test dependencies. No security or dependency settings changed by this work, and the cause of the changed enforcement behavior is not established. No Qwen inference, historical-data training or promotion started. The subsequent complete suite passed 5,015 tests with two expected skips and no failures or collection errors; its complete JUnit pin and process-exit evidence are in the development-window handoff.

The completed execution-evidence assessor distinguishes a book reference from feed-health, executable-size and fill evidence; it reports missing evidence instead of synthesizing it. The separately registered declared-economics operator is also complete, with hypothetical costs and no trading authority; see `docs/6E_ECONOMICS_OPERATOR.md` and the development-window handoff for its verified toy projections. The separate pure declared-entry-budget assessor passed 61 focused tests and independent review. The final expanded complete project suite passed 5,301 tests with three expected skips and no failures or errors; full JUnit, process-exit and unchanged-source checks passed. Entry budgeting is arithmetic, not a funded replay or trading permission. A different execution simulator or pending-order reconciliation contract still needs new tests and a separate registration. Broader historical analysis must preserve the complete declared cohort and unavailable outcomes; retraining still needs defensible targets and independent validation. The four-hour continuation expires at 13:41:31 UTC on 8 October 2026.
