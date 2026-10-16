# Continuous 6E replay pilot and operator handoff

The first separately registered continuous-account pilot verified all 22,311 decisions and 1,229,040 native quotes from the first two accepted train sessions. The fixed liquidity-follow rule produced 19 closed simulated positions with a combined net of -33 contract-ticks and one position with an unresolved exit. The complete simulated return remains unknown. This is an accounting and execution-assumption check, not a profitable-strategy result, independent validation or a training dataset.

The workflow now runs locally without ChatGPT through `prepare`, `run` and read-only `verify` commands. It neither runs Qwen nor accesses a broker. The original targets, model, studies and BTC collector remain unchanged.

## Pilot coverage and result

The pilot was registered before simulating its selected actions. It used the exact first two accepted sessions, 26 and 27 March 2025, with their complete 12:00-16:00 UTC windows. Both are already-exposed train-development sessions using dated contract `6EM5`. They were not selected for profitable outcomes. The original metadata still retains all 196 accepted sessions and all 471 inventory dispositions, including the 230 reserved metadata-only dates.

| Session | Decisions | Native quotes | Entry attempts | Entry fills | Closed positions | Unresolved positions at end |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 26 March 2025 | 11,001 | 583,955 | 25 | 19 | 19 | 0 |
| 27 March 2025 | 11,310 | 645,085 | 1 | 1 | 0 | 1 |
| Total | 22,311 | 1,229,040 | 26 | 20 | 19 | 1 |

Six entry attempts were refused at their first widened quote; the simulator did not search for a later favorable quote. Among the 19 exits on the first day, 14 were stop-triggered, three target-triggered and two timer-triggered. Their closed gross total was -14 contract-ticks; the assumed one extra tick per closed contract reduced that known closed portion to -33. This is not USD cash or cTrader CFD PnL.

The second day's exit lacked a fresh completed quote within the original deadline. The ledger retained the long position and its `UNKNOWN` reservation. The remaining eligible decisions could not start another position: 8,992 decisions on that day received the inventory-blocked disposition. The last quote of the session remained a reference, not a delayed fill or realized profit. There was no missing-exit reset at the end of the session.

Across both days, every decision has exactly one disposition: 4,363 ineligible, 9,043 inventory-blocked, 150 cooldown, 8,729 no-signal and 26 entry-selected. The durable output contains 65 ledger events and 39 incremental simulator receipt documents. Complete input consumption and reconstructed event identity verified independently. Cross-day unresolved carry, restart recovery and contract-change refusal are also covered by synthetic tests; this historical pilot ended flat on its first day and open on its second.

## Causal inputs and simulator assumptions

`six_e_continuous_inputs.py` verifies the original pinned registration, complete collection receipt and daily source/quote metadata. It reads only the requested first one-to-three accepted train-session prefix. Its bounded parser hashes the entire original row envelope while projecting only causal identity, time, eligibility and the 23 flow/depth plus 14 execution-proxy features. The policy receives no future-outcome, hindsight-action or return-target fields. All native quote columns are checked before and after use; the loader never opens raw archives, reserved price rows or model files.

`six_e_continuous_replay.py` attaches each decision to the first native completed quote at its receive timestamp. The decision is processed immediately after that cursor, before any later equal-time quote. It uses one fixed feature-only policy, not a fitted model or the old daily outcome scheduler. All decisions and quotes remain represented, including losses, refused entries and inventory-blocked decisions.

The pilot retains the original 100 ms entry/exit delays, inclusive one-second candidate waits, one-contract size, 15-second hold, bracket thresholds of +3/-3 ticks after one assumed extra round-trip tick, and 10-second cooldown. The hold timer wins equality with a quote at its deadline; a first candidate quote exactly on an entry/exit wait deadline remains eligible. The first widened entry quote refuses; widened exit prices and stop overshoot remain in receipts.

These are quote-simulator assumptions. Filling a whole contract at a supplied top-of-book price is not authenticated broker execution, available-size proof or a queue model. A missing entry is a simulator refusal, not proof that a real broker cancelled an order. A missing exit becomes `UNKNOWN`; later quotes cannot fill it automatically, retry it, cancel it or reset its inventory. The simulator does not infer overnight prices or substitute a new contract for a carried old one.

Every training, scoring, trading, promotion, broker-execution and independent-holdout authority flag is false. The absence of a complete return must not be replaced with a score calculated only from closed positions.

## Durable registration and verification

`six_e_continuous_trial.py` freezes the original source registration, exact input content manifest, fixed policy/exit plan, 45 implementation-source pins, complete original coverage and exclusive output path. Bounds are three sessions, 43,200 decisions, two million quotes per session, 2,000 ledger events, 16 MiB per sidecar and a five-minute registered-run rejection budget. Timing checks are cooperative checks around bounded operations, not an external hard process kill.

All inputs and the complete causal event plan are checked before the output directory is claimed. Existing output is never overwritten, adopted or resumed. Failed partial attempts retain evidence and cannot be verified as successful subsets. A completed simulation can still have an unreconciled position, as this one does.

Verification independently reloads the original pinned causal inputs and reconstructs every action, receipt, decision disposition, hash-chain head, terminal ledger state and pending-entry/timer/cooldown checkpoint. It also compares complete sidecars and false-authority flags. A valid truncated journal, an extra valid event or a rewritten journal with identical closed totals is not the registered result. Opening the ledger is read-only. Local hashes demonstrate reproducibility against trusted pins, not protection against a privileged actor rewriting all evidence and pins.

The output is `data/processed/6e_continuous_liquidity_20261008_1`. Its registration is `logs/6e_continuous_liquidity_20261008_1_registration.json`.

| Evidence | SHA256 |
| --- | --- |
| Trial registration | `05e238e2ff0ef62417ad3ba19e946a5ad6bab446a794af4d5a360f366f320eea` |
| Input content manifest | `b0b6139bfc2a49d807610fc7db4a186c943e5aa851d9d2d6aeb214635f4cb695` |
| Request | `b99fd21383766d7a43f6009d759d8371a33dd437addddddcfdfe6607e0ff37b3` |
| Completion | `b4a94815f4dae2c62f11d72920cb721a5bc0376ca3f4f3a10121dbfadaf4e3d9` |
| Verification receipt | `a8e74b8b6cf01e9c065193a795d9ca6ebde31ec5b8481271be1f02d3d6587c9d` |
| Complete event sidecar | `17df10c79abda7566ce2718767e7e51fc99334232274ce311857ec19409d2f8b` |
| Complete simulator receipt sidecar | `b27bfd27556002dee5515e277411c653ded03273dcf2304ed22aff9323c4d5b5` |
| Complete decision audit | `20f8f4615367a0fd90362f611a63e78511766405791288538ef92fce321c42ce` |
| Terminal ledger head | `1ad9a72bcb0a5d6e68ca1e132ddbe1b3b9f72b8a1d93d2f6a3b356312e420fb5` |

From PowerShell, verify this existing result without launching another simulation or changing files:

```powershell
Set-Location C:\Users\pabta\Projects\ai-trader
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_continuous_trial verify --registration logs/6e_continuous_liquidity_20261008_1_registration.json --registration-sha256 05e238e2ff0ef62417ad3ba19e946a5ad6bab446a794af4d5a360f366f320eea --completion-sha256 b4a94815f4dae2c62f11d72920cb721a5bc0376ca3f4f3a10121dbfadaf4e3d9
```

Expected status is `verified_continuous_quote_simulation_not_validation`, with two sessions, 22,311 decisions, 65 events, 39 receipts, one remaining contract, an `UNKNOWN` exit and a `null` complete simulated return. All authority flags must be false. Do not run the existing registration again: its claimed output intentionally refuses reuse. New studies need new paths and an explicit registration; editing pinned code or changing settings invalidates an existing registration rather than silently resuming it.

To inspect the available independent workflow and its required parameters:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_continuous_trial prepare --help
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_continuous_trial run --help
```

These help commands start no job. The workflow is a bounded offline research tool, not an unattended live-data paper trader or self-training system.

## Tests and next decision

The final regression passed 600 Python tests, including all 191 new tests: 87 replay, 48 input-loader and 56 command-wrapper cases. All 38 JavaScript tests passed; Ruff and formatting checks passed. Independent code review found no remaining blockers for this bounded pilot. A separate read-only CLI verification reproduced the completed result.

The complete project baseline ran before these new test files were added and finished with 4,456 passed, one optional Nautilus skip and ten collection errors. The errors remain Windows Application Control blocking PyTorch's `c10.dll`; security policy and dependencies were not changed. The baseline and focused totals overlap and are not a single green full-suite result. No Qwen training or inference started.

The next decision is how to diagnose and explicitly reconcile missing exits under defensible execution assumptions, then test those assumptions in a new registration with the original targets retained as controls. Do not increase apparent opportunity counts by silently marking old quotes as fills. Funded capital/margin, measured broker costs, pending real orders, expiry settlement and cTrader CFD execution still need separate contracts. Model retraining should wait for those execution targets and an untouched validation cohort; a closed negative portion plus an open liability is not training or promotion evidence.
