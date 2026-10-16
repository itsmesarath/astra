# 6E Liquidity Research Operator Guide

This guide explains how to inspect the fixed historical liquidity experiment without ChatGPT. It does not enable trading, continuously retrain Qwen, collect new data or resume a failed experiment. Keep the computer awake while its existing Python process runs. Closing the terminal, sleeping or restarting the computer can interrupt it.

The study uses dated CME Euro FX futures contracts as research signals. It is not a cTrader EURUSD backtest: broker quotes, spreads, commissions, currency conversion and execution still need separate validation. BTC collectors are outside this workflow and remain unchanged.

## Check progress safely

Open PowerShell and run these commands from the project folder:

```powershell
Set-Location C:\Users\pabta\Projects\ai-trader
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_liquidity_status `
  --registration logs/6e_liquidity_whole_20261004_1_registration.json `
  --registration-sha256 3bb478f1ca3af529c280671597193438b032e18985a7041f4ba6a9777a95a275 `
  --output data/processed/6e_liquidity_whole_20261004_1
```

This reads bounded registration, request, progress, completion, verification and failure metadata only. It does not open prices, targets, predictions, raw archives or model weights. It does not launch another job or modify anything. It checks progress against the original chronological cohort; it does not check whether a matching process is alive.

The Python status command preserves the stored timestamp strings. In recent PowerShell versions, `ConvertFrom-Json` can convert ISO timestamps into local-time date objects when displaying them. Use `ConvertFrom-Json -DateKind String` where supported if you need the exact original strings, or inspect the JSON directly. A different displayed timezone offset is not itself clock drift; historical decision windows remain UTC and process deadlines use monotonic elapsed time.

| Status | Meaning | What to do |
| --- | --- | --- |
| `progress_metadata_unverified` | Complete progress lines show a cohort prefix. They do not prove success or process liveness. | Let the original job run. Do not start a duplicate. |
| `concurrent_snapshot_unverified` | A metadata file changed or was incomplete during the read. | Repeat the status command later. Do not assume corruption. |
| `completion_metadata_not_revalidated` | A complete report exists, but this check has not verified its contents. | Wait for the original terminal verifier. |
| `unpinned_receipt_matches_metadata_not_revalidated` | A verification receipt agrees with the report, without an externally supplied completion pin. | Compare with the original successful verifier output. |
| `pinned_receipt_matches_metadata_not_revalidated` | The externally supplied completion pin and saved receipt agree with metadata. | This is still a metadata check, not a fresh full verification. |
| `failure_metadata_present_no_retry` | Retained failure evidence exists. | Keep the files and diagnostics. Do not repair, resume or score a subset. |
| `awaiting_request_unverified` | No original request is visible in the specified directory. | Check the path and original terminal. It is not permission to launch. |

The returned fields `full_content_verified_by_this_check`, `process_checked`, `permission_to_start_or_resume` and `trading_enabled` remain false. A process existing, a final progress line or a completion file alone is insufficient evidence of success.

A failure can occur after a model or some forecast files have already been written. Failure metadata is not proof that no fitting happened. Retain every file in that claimed directory and keep any candidate quarantined; do not reuse its partial outputs, fit a successful subset or create a replacement run automatically.

## Verify a completed collection

The original collector performs terminal verification automatically. Success requires an exit code of zero and `verified_whole_liquidity_targets_not_validation`, covering all 196 accepted sessions and every original decision row. A failure file overrides a completion file.

For a later read-only recheck, use the original successful completion pin below. Do not accept a changed file merely by hashing it again.

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_liquidity_study verify-collection `
  --registration logs/6e_liquidity_whole_20261004_1_registration.json `
  --registration-sha256 3bb478f1ca3af529c280671597193438b032e18985a7041f4ba6a9777a95a275 `
  --output data/processed/6e_liquidity_whole_20261004_1 `
  --completion-sha256 c3c14ecf5344556c2aa3037e54979a2c3bbc417fe387775a44c266ec9d7ce58b
```

Unlike the status command, this verifier reads the accepted development rows and retained native quote columns, checks their pins, recomputes all targets and accounting, and rechecks the frozen implementation. It can take substantial time. It does not replay raw archives, fit a model or open reserved outcomes.

## Inspect the completed CPU candidate

The October 4 candidate finished and passed full verification across all 196 accepted sessions and 2,136,770 rows. It made no trading signals. All three active rule baselines had negative closed-trade averages under both exit plans. Keep the candidate quarantined; completion is not strategy approval. The complete result and limitations are in `docs/6E_LIQUIDITY_WHOLE_20261004.md`.

For a quick metadata-only check of this completed candidate:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_liquidity_status `
  --registration logs/6e_liquidity_whole_20261004_1_registration.json `
  --registration-sha256 3bb478f1ca3af529c280671597193438b032e18985a7041f4ba6a9777a95a275 `
  --output data/processed/6e_liquidity_cpu_20261004_1 `
  --completion-sha256 f8d85b19e23ae96588abfa52ebeb734ef20391db4fdadfa730336e7a0a7dbe43
```

Expected status is `pinned_receipt_matches_metadata_not_revalidated`; its authority flags remain false. For a separate full read-only content recheck, use:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_liquidity_study verify-evaluation `
  --registration logs/6e_liquidity_whole_20261004_1_registration.json `
  --registration-sha256 3bb478f1ca3af529c280671597193438b032e18985a7041f4ba6a9777a95a275 `
  --build-output data/processed/6e_liquidity_whole_20261004_1 `
  --build-sha256 c3c14ecf5344556c2aa3037e54979a2c3bbc417fe387775a44c266ec9d7ce58b `
  --output data/processed/6e_liquidity_cpu_20261004_1 `
  --completion-sha256 f8d85b19e23ae96588abfa52ebeb734ef20391db4fdadfa730336e7a0a7dbe43
```

This rechecks model arithmetic, forecasts, targets and all policy summaries without refitting or selecting another candidate. It can take tens of minutes and does not grant training or trading permission. Keep the original pins even if files are copied; missing files or pin drift are blockers, not instructions to rerun the experiment.

## Understand the training gate

Collection and training are separate phases. One fixed CPU candidate may fit only after every accepted session verifies. It uses train sessions alone, with causal selections at least 60 seconds apart. The required support is at least 1,000 jointly resolved training cases and 100 unknown cases. If this gate fails, no fitting occurs and no successful subset is substituted.

The CPU candidate has 37 causal features and three ridge-regression heads. One head estimates whether both directional exits will be resolved; the two other heads estimate conditional long and short net returns on jointly resolved cases. Losses remain in training. Unknown returns are not replaced with zero. The conditional heads cannot establish the economics of unresolved cases, and the clipped availability score is not a calibrated probability guarantee.

Unknown labels can arise because this simulator requires a fresh completed quote within its bounded wait. They are not automatically evidence of corrupted data, a bad session or a losing trade. In particular, a quiet but unchanged order book does not supply the new liquidation event required by this target definition. The availability head predicts observability under that definition, not actual broker execution availability.

The comparison retains six fixed policies: CVD follow, liquidity follow, absorption fade, CPU cost, CPU cost with the liquidity gate, and no trade. Decisions use features only. Each policy has its own one-position simulation, a ten-second cooldown and a session block after an entered trade whose exit remains unknown. An idle model is a valid result; it is not a reason to lower thresholds automatically.

The evaluation output is claimed exclusively. Do not run `evaluate` while another owner is evaluating it. Reusing a claimed directory, retrying a failed fit, choosing a better-looking subset, changing thresholds or opening reserved data requires a new explicitly registered research plan. This guide intentionally does not contain an automatic training launcher.

Each source session has an independent research schedule. An unknown entered exit blocks that session; the replay does not establish that the position closed overnight or carry an account ledger into the next session. Summing observed closed returns therefore does not create complete strategy PnL or account equity. The descriptive diagnostics retain unknown-exit counts and label their drawdown as a closed-session sequence, not account drawdown.

## Interpret the results

The time exit and bracket exit share the same entry quote. The bracket uses a three-tick target and stop after one assumed extra round-trip tick, a fifteen-second timeout, and a hundred-millisecond delay before entry and exit requests. It liquidates at the first allowed quote; it does not assume exact stop or target fills. Widened exits, overshoots, refusals and missing quotes remain visible. The two- and four-tick cost stresses recost the same closed selections without changing triggers.

All train, validation-development and test-development roles are already exposed research data, not independent holdouts. Counterfactual directional labels overlap and are not simultaneous executable trades. Visible queue, replenishment and absorption measurements are proxies, not proof that a particular participant used an iceberg.

Before considering paper deployment, require session and month coverage, retained unknown-entry and exit counts, positive economics under realistic costs, and independent prospective validation. Closed-trade accuracy or positive hindsight opportunities alone do not establish a usable strategy. The current research flags keep model promotion, Qwen training and trading disabled.

The optional reporting diagnostics use fixed five-session blocks and 2,000 deterministic resamples to describe variability in the mean return of closed trades. Every accepted session remains in the resampling cohort. Fewer than twenty sessions with closed trades, or any resample without a closed trade, makes the interval unavailable. These descriptive intervals do not correct for exposed data, unknown returns, nonstationarity or multiple policy comparisons, and cannot authorize promotion.

## Understand the prediction benchmark

The separate CPU timing tool requires a completed pinned candidate, a matching receipt, unchanged model bytes, and unchanged prediction and standardization code. It measures exactly 1,000 single-row predictions after ten warmup calls, with a thirty-second checked runtime bound. Inputs are synthetic zeros, not prices or real market features. It does not fit a model, read training rows, call Qwen or send orders.

Prediction time is only one part of decision latency. This measurement excludes raw decoding, feature construction, policy selection, risk checks, journaling, feed delays and broker execution. Shared-computer load can affect it. A fast prediction result cannot justify reducing the study's assumed hundred-millisecond entry or exit delay, and it is not an end-to-end latency guarantee.

## Run software checks

These checks are offline and do not launch real-data training or send orders. Unit tests may fit tiny synthetic CPU fixtures in temporary directories; they do not update the completed candidate or production weights:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\python.exe -m pytest -q
```

The full suite may take tens of minutes. Stop treating the implementation as verified if it fails; retain the failure and fix the software separately without changing the frozen experiment under a running job.
