# Trading-engine evaluation: NautilusTrader

Date: 2026-09-24. Decision: **EVALUATE / BLOCKED**, not ADOPT.

## Scope and evidence

The owner asked to continue development after discussing Nautilus integration. This slice adds
an isolated synthetic replay probe, not a replacement gateway, new trading policy or live adapter.
Existing capture/features/risk/gateway behavior is unchanged. Earlier uncommitted plan changes
were preserved; the evaluation environment is ignored by Git.

Selected evaluation version: `nautilus_trader==1.231.0`, the stable version returned by the package
index during this task. The Windows CPython 3.12 wheel installed in `.venv-nautilus`; the project's
`.venv` was not changed. Installed dependency versions are in
[the evaluation requirements](../../requirements/nautilus-eval.txt).
These version pins are not wheel hashes or proof of a working environment.

The version's distributed Cython/Python source was inspected for `BacktestEngine.add_data`,
venue setup, latency, fee calculation, instruments and callbacks. `add_data` expects homogeneous
lists and merges by `ts_init`; the binding supplies book batches and trades separately. No upstream
implementation was copied or vendored. Nautilus remains an optional external dependency with its
own LGPL-3.0 licensing; do not relabel or redistribute its code as our MIT code. Review distribution
requirements before bundling it in a release.

References: [pinned upstream source](https://github.com/nautechsystems/nautilus_trader/tree/v1.231.0),
[installation/version caveat](https://nautilustrader.io/docs/latest/getting_started/installation/).
Do not use latest 2.x examples as verification of this 1.x binding.

## Implemented probe

- `src/ai_trader/research/nautilus_probe.py`: immutable synthetic data, hashed fixture,
  independent Decimal reference calculations, strict result comparison, repeated-run comparison,
  dependency/version checks and machine-readable status.
- `src/ai_trader/research/_nautilus_backend.py`: experimental optional binding to the pinned
  backtest API. **Native replay has not run successfully.** Its behavior is not validated yet.
- `tests/test_nautilus_probe.py`: portable oracle, comparator, orchestration and failure tests.
- `tests/test_nautilus_native.py`: actual-engine integration test; skips only if the optional
  package is absent. An installed but blocked/broken package fails rather than silently skipping.

Synthetic instrument `BTCUSDT.SIM` uses a CASH account, no borrowing, no exchange client or keys.
Instrument filters/fees are fixture assumptions, not current Binance settings. All cases submit
at most one simulated BUY limit-IOC after our existing deterministic risk evaluation. The state
is deliberately flat initially; this is not a general portfolio/risk adapter. Trade ticks trigger
the decision, but do not manufacture executable liquidity (`trade_execution=False`).

## Fixed acceptance cases

Starting cash: 1000 USDT. Fee assumption: 0.1% in USDT per fill, eight-decimal rounding. Two asks:
0.001 BTC at 60010 and 0.002 BTC at 60020. Decision at receive time +2 s. A later book raises the
best ask to 60030 at receive time +4 s, despite its exchange timestamp preceding the decision.
One late trade also arrives out of exchange-time order. This tests receipt visibility explicitly.

| Case | Independent reference result (not observed native output) |
| --- | --- |
| Buy 0.003 BTC, limit 60020 | Two fills; cost 180.05; fee 0.18005; cash 819.76995; inventory 0.003; FILLED |
| Buy 0.005 BTC, same limit | Only 0.003 available; same cost/fees; remaining 0.002 canceled; CANCELED |
| Kill switch active | No submission/fills; cash 1000; inventory zero; NOT_SUBMITTED |
| Buy 0.003 with 2.5 s order latency | Later ask exceeds limit; no fills; cash 1000; CANCELED |

Every case must observe initial ask 60010 at decision time and trades at receipt offsets +2,+3,+5 s.
Run each twice and require identical normalized results. Compare individual fill price/quantity/
fee, cash, inventory, risk reason and terminal status, not only aggregate PnL. No strategy edge is
implied; successful tests would establish only this tiny simulation contract.

## Actual verification

- Initial full suite: ten collection errors from PyTorch's blocked native DLL (WinError 4551).
- Ruff lint: PASS. Final formatting check: PASS, 132 files already formatted.
- New portable tests: 25 passed; one native integration test skipped in the main environment
  because Nautilus is intentionally not installed there.
- Full suite with `--continue-on-collection-errors`: **436 passed, 1 skipped, 10 collection errors**.
  This is NOT a fully passing regression suite. The ten errors are the same PyTorch load blocker.
- Reference CLI: `REFERENCE_ONLY`; expected arithmetic printed successfully. It runs no engine.
- Native CLI in isolated environment: `BLOCKED`, loading pandas `indexing` failed under Windows
  Application Control. This occurs before engine creation. No result from native replay exists.
- No security settings altered, no package downgrade to evade policy, no credentials read, no
  exchange connection, no market-data download, no model training and no live orders.

## Commands

From the repository root, the portable check is available in the existing environment:

```powershell
.venv\Scripts\python.exe -m ai_trader.research.nautilus_probe --reference-only
.venv\Scripts\python.exe -m pytest -q tests/test_nautilus_probe.py tests/test_nautilus_native.py
```

The isolated environment already exists on this machine. On a new machine only, create/install:

```powershell
.venv\Scripts\python.exe -m venv .venv-nautilus
.venv-nautilus\Scripts\python.exe -m pip install --only-binary=:all: -r requirements/nautilus-eval.txt
.venv-nautilus\Scripts\python.exe -m pip install --no-deps -e .
```

After an approved resolution of the native dependency block, run:

```powershell
.venv-nautilus\Scripts\python.exe -m ai_trader.research.nautilus_probe
.venv-nautilus\Scripts\python.exe -m pytest -q tests/test_nautilus_probe.py tests/test_nautilus_native.py
```

CLI status: `REFERENCE_ONLY` = arithmetic only, `BLOCKED` = dependency unavailable,
`FAIL` = replay/comparison failure, `PASS` = all four native cases match and repeat. Failures exit
nonzero. Do not change security policy merely to turn this green. Unexpected backend API/behavior
errors must be investigated rather than changing expected results to match the engine.

## Remaining adoption gates and reversal

1. Approved environment diagnosis, then actual native execution of these cases.
2. Validated real-capture conversion retaining receipt times, update IDs, gap/quarantine and known
   snapshot bounds. The current probe uses synthetic book images, not raw Binance deltas.
3. Expand failure tests: restart persistence, ambiguous orders, cancellation/fill races, fees in
   other assets, partial entry protection, queue uncertainty and latency-clock semantics.
4. Verify authoritative project risk checks for all submission paths and instrument filters;
   document one accounting owner and a translation contract for the existing gateway.
5. Measure realistic replay throughput, memory/storage and maintainability before choosing
   build/adapt/adopt. No performance or Windows compatibility claim is established by installation.

The optional backend is reachable only through this research probe. It is not registered in
`trading/runtime.py`. The existing paper gateway remains the working default; removing the probe
and isolated dependency environment requires no runtime migration. Live remains disabled.
