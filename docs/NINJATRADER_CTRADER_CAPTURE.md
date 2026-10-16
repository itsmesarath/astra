# Capture 6E and EURUSD data without orders

The project now includes a capture-only NinjaTrader indicator for dated CME 6E contracts and a demo-only cTrader cBot for EURUSD quotes. Both are disabled by default and bounded when enabled. They record observations for offline inspection; they do not place orders, train a model, open an account connection or promote the existing research model. No real platform capture has been started or verified yet. The BTC collector is unchanged.

NinjaTrader supplies the intended futures signal stream. cTrader supplies the intended spot/CFD broker quote stream. The existing Databento archives remain historical research data. A new live capture cannot be aligned with old 2025 observations simply because both instruments track the euro: a paired study needs overlapping collection times and verified clock uncertainty.

## Choose the correct NinjaTrader feed

NinjaTrader currently advertises a 14-day live-streaming market-data trial. Its simulation account and its artificial Simulated Data Feed are different things: virtual trading can use real, delayed, replayed or generated prices. The trial is not a promise of indefinitely free real-time data. Do not use generated prices as market-learning data. Confirm the active connection, expiry and CME depth entitlement in the platform before the first research capture. No subscription was purchased or changed. [Official simulator and data-source explanation](https://ninjatrader.com/trading-platform/trading-simulator/).

The indicator uses `OnMarketData` for bid, ask and last-trade observations, and `OnMarketDepth` for aggregated depth updates. NinjaTrader documents separate ordering guarantees for each stream, but not a guaranteed combined ordering between them. These callbacks are not Databento MBO, confirmed aggressor-side volume or native iceberg flags. [Level 1 reference](https://ninjatrader.com/support/helpguides/nt8/onmarketdata.htm), [Level 2 reference](https://ninjatrader.com/support/helpguides/nt8/onmarketdepth.htm).

## Included components

| Component | Purpose | Limits |
| --- | --- | --- |
| `integrations/ninjatrader/AiTraderSixEDataCapture.cs` | NinjaTrader data-only indicator for a dated 6E chart | No account or order access; feed status stays unverified |
| `integrations/ctrader/AiTraderEurUsdCapture.cs` | Paired EURUSD bid/ask observations from a cTrader demo chart | Refuses live accounts, backtests and other currency pairs |
| `integrations/market_data/BoundedCaptureWriter.cs` | Shared append-only JSONL transport with serialized callbacks and heartbeat | Fresh session ID, exclusive file creation, bounded run, no restart |
| `ai_trader.research.platform_capture` | Offline structural audit and causal quote lookup | Never declares training or trading readiness |
| `integrations/package_sources.py` | Combines each adapter and shared writer into one source file | Generates files only; does not install or start a platform |

The cTrader cBot uses `AccessRights.None` and local files in its designated algorithm directory. That flag is not a trading lock; the explicit demo guards and absence of order methods are what keep this implementation data-only. Its project targets .NET 6 and pins `cTrader.Automate` 1.0.21. The project disables automatic publishing to the user's cTrader directory. [cTrader file access](https://help.ctrader.com/ctrader-algo/guides/file-operations/), [account mode reference](https://help.ctrader.com/ctrader-algo/references/Account/IAccount/), [compiler publishing options](https://help.ctrader.com/ctrader-algo/compiling/).

## Generate standalone source files

From the project root:

```powershell
.\.venv\Scripts\python.exe integrations/package_sources.py --output-dir build/platform_capture_local
```

The output directory must not already exist. It contains `AiTraderSixEDataCapture.cs`, `AiTraderEurUsdCapture.cs` and a SHA256 manifest. Each C# file includes the shared writer and can be pasted into its platform editor without a separate helper DLL. A package was already generated locally at `build/platform_capture_20261001`. Generated binaries and packages are ignored by Git.

## First NinjaTrader capture

1. Open NinjaTrader and connect the intended live-data demo feed yourself. Keep credentials in the platform. Check that bid/ask and depth are actually updating; a connected icon or Sim101 account alone is insufficient.
2. In NinjaScript Editor, create a new indicator named `AiTraderSixEDataCapture`. Replace the new source with the complete generated standalone file, then compile. Do not paste the unbundled adapter by itself.
3. Add the indicator to a chart for the dated 6E contract supplied by the feed. Continuous `##-##` contracts are refused. No gold or BTC symbol is enabled by this adapter.
4. Initially leave `Enable capture` false. To perform the first bounded smoke capture, set it true, use one minute, and supply a harmless connection label without login details. The label is diagnostic, not proof of feed identity.
5. The output window prints the path under NinjaTrader's user-data directory in `ai-trader-captures`. This computer's NinjaTrader data directory is `C:/Users/pabta/Documents/NinjaTrader 8`. The file has a fresh `ninjatrader-<id>.jsonl` name.
6. Let the capture reach its bound, then remove or disable the indicator. Inspect the resulting file with the offline audit command below. An observed reset flag or later platform state change ends the file with failure evidence rather than starting a replacement session. Disconnect detection is not guaranteed by these callbacks; a heartbeat proves only that the writer is alive, not that the feed remains connected.

The default duration is ten minutes and the maximum is sixty. The default record limit is 250,000, including heartbeats; the hard upper limit is 1,000,000. Files stop before exceeding 64 MiB. The first limit reached wins. Enabling file capture does not control NinjaTrader's underlying chart subscriptions. The capture will not run while the computer or platform is off; this does not create a cloud service.

## First cTrader capture

Create a C# cBot named `AiTraderEurUsdCapture` in cTrader Algo and paste the generated standalone source. Build it with the platform's .NET 6 compiler, attach it to a EURUSD demo chart, and initially keep `Enable capture` false. Broker symbol suffixes are allowed because the adapter checks the EUR base asset and USD quote asset. Set the same one-minute smoke duration when ready to collect alongside NinjaTrader.

The cBot writes beneath its restricted data folder, normally `Documents/cAlgo/Data/cBots/AiTraderEurUsdCapture/captures`. The printed path identifies the session file. It reads the broker name but not account numbers, balances, passwords or tokens. No OpenAI key or cTrader Open API application is needed for this local platform route. The broker/demo account has not yet been confirmed in this task.

## Audit a completed file

Use a new report path for each completed capture:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.platform_capture --capture "C:/path/to/completed-session.jsonl" --output data/processed/platform_capture_audit.json
```

An optional `--expected-sha256` pins a previously recorded raw-file digest. The auditor never modifies the capture or overwrites an existing report. It rejects missing/failed footers, extra data after a footer, duplicate JSON keys, sequence gaps, changed session identities, invalid decimal prices, wrong tick grids, clock regression, excessive wall-versus-monotonic drift and exceeded bounds. A still-running or partially appended file is incomplete evidence, not automatically corrupt data.

A successful structural audit reports separate counts of bid, ask, trade and depth observations, spread statistics where both sides are fresh, quote inactivity and heartbeat gaps. It distinguishes a clean manual stop from a duration/event bound. Heartbeats cannot make old quotes fresh. `Capture.asof` uses only observations at or before a decision, checks bid and ask age separately, and refuses stale/crossed states rather than falling back to an older valid quote.

Depth updates and trades are retained in the raw file, but this first auditor does not reconstruct a certified L2 book or assign aggressor direction/CVD. A later reconstruction stage must establish an initialized ladder, reset handling and feed-specific semantics. Missing Level 2 observations are reported rather than replaced with invented depth.

## Clock and execution restrictions

Every record carries local UTC observation time and monotonic elapsed time. The observation occurs inside the writer's serialized callback, not at the exchange or network socket. Provider time strings are diagnostic only: they are never used to sort or backfill observations. Synchronous serialization can delay platform callbacks; this is a bounded research collector, not a low-latency execution engine.

A 250 ms wall-versus-monotonic drift threshold catches large clock changes but does not prove absolute UTC accuracy. No resynchronization, clock-offset correction or cross-provider alignment is performed automatically. The audit always retains `utc_synchronization_unverified`, `broker_costs_and_fills_unmeasured`, `training_ready=false` and `trading_enabled=false`. NinjaTrader additionally retains unverified feed entitlement/realtime status. Demo quotes do not measure real-account fills or commissions.

## Verification and remaining work

The baseline complete suite passed 3,079 tests with one optional Nautilus skip. After implementation, the complete suite passed 3,123 tests with the same optional skip in 147.51 seconds; Ruff checks passed. The 44 focused tests cover incomplete-file handling, clocks, session identity, price precision, fresh-side requirements, crossed-state invalidation, no future backfill, dishonest bound footers and non-overwriting source packaging.

Both original and bundled NinjaTrader sources compiled against the installed NinjaTrader Core, Gui and Custom assemblies. Both cTrader sources passed a C# API compatibility compile against the .NET 4.0 reference assembly in `cTrader.Automate` 1.0.21. That compatibility check emitted a duplicate `CallerMemberNameAttribute` warning from the legacy reference. It is not a verified .NET 6 `.algo` build: this machine has .NET runtimes but no standalone SDK, and the cBot still needs its platform build and demo smoke test.

An isolated C# smoke harness wrote explicitly synthetic files and exercised timed shutdown and the event-count limit. Python accepted their transport structure and correctly left training disabled. No trading platform was loaded by that harness; these files are not market data. The NuGet reference package used for compilation has SHA256 `571bb550d5b81e9efaf6ae8381bfddba2209ed308c209a4fff770ae88dd96b37` and remains local in ignored logs.

Next, verify the NinjaTrader connection and CME depth entitlement, build/import the indicator, and audit one minute of real observations. Then verify the cTrader demo broker and gather a concurrent pair with explicit clock evidence. Only after those checks should we build a strict depth reconstructor and evaluate futures signals against broker-specific EURUSD prices and costs. The previous cost-model rejection remains unchanged.

## Update 16 Oct 2026: M6E and full-session capture (roadmap P1)

The NinjaTrader indicator now accepts the micro **M6E** contract (tick 0.0001) as well as **6E** (tick 0.00005). The offline auditor checks the tick grid for each. Every other contract, and continuous `##-##` charts, are still refused.

For longer sessions, set **Total hours with rotating files** to 1–24. Each file keeps the same per-file limits: at most 60 minutes, 1,000,000 events and 64 MiB. When a file ends cleanly at one of those limits, the next market event opens a fresh file with a new session ID. Rotation continues until the total hours have passed, with at most 2,000 files.

Any failure ends the whole capture and opens no new file. Failures include a feed reset, a platform state change, a clock jump or a writer error. The default is 0, which captures a single file as before. Every rotated file is an ordinary, independently auditable capture. Expect a short gap between files: a new file opens only at the next market event.

Suggested first runs:

1. **Smoke:** Enable capture on, 1 minute, Total hours 0, on a dated 6E or M6E chart with Level 2 visible. Audit the file.
2. **Session:** 60-minute files, Total hours 8, during liquid hours (for example 08:00–16:00 Lisbon). Audit every file and keep all of them, including failures.

C# changes are not compiled in this repository. Compile in the NinjaScript Editor and report any compiler message.
