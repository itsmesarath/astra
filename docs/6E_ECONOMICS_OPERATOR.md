# Declared economics operator

This offline command reconstructs a frozen 6E simulation and projects explicitly hypothetical USD charges over its complete saved event tape. Entry fees are charged when an entry receipt is observed, including when the exit remains unresolved. It does not run another strategy, create fills, place orders, train a model or approve risk.

The source passed independent review, whole-package Ruff and 225 synthetic tests, with one expected Windows symlink-privilege skip. Two explicitly toy projections on the completed carry and no-trade controls also passed separate canonical verification and independent path-by-path accounting review. Current source SHA256 is `be97902072b039817775964378db8bcce7ddad33af49e4fe688d6add60fa109d`. The final complete project suite, including the separate pure entry-budget assessor, passed 5,301 tests with three expected skips and no failures or errors. Its complete-result and unchanged-source verification is recorded in `docs/6E_DEVELOPMENT_WINDOW_20261008.md`.

## Supported controls

Only the three completed local controls are accepted. Their original registration, request and completion hashes, exact dates, settings and source maps are fixed in the operator. A newly repinned experiment, changed policy, different wait or profitable subset cannot be substituted.

| Control | Train windows from 12 to 16 UTC | Decisions | Quotes |
| --- | --- | ---: | ---: |
| `original` | 26 and 27 March 2025 | 22,311 | 1,229,040 |
| `carry` | 26 to 28 March 2025 | 33,966 | 1,985,498 |
| `no_trade` | 26 to 28 March 2025 | 33,966 | 1,985,498 |

The command needs the existing completed local control artifacts. A Git clone without those artifacts must refuse rather than download data, fabricate a journal or select other sessions. BTC collectors and reserved price rows are outside its scope.

## Explicit hypothetical amounts

USD values are integer micro-dollars: one dollar is 1,000,000 units. Supply the seed balance, tick value, entry fee and exit fee explicitly. These are hypothetical futures assumptions, not measured broker charges, current CME specifications or cTrader EURUSD CFD costs. The seed timestamp must equal the first original window start: `1742990400000000000` nanoseconds, 26 March 2025 at 12:00 UTC.

Declare margin as `none`, or as `fixed` with both hypothetical initial and maintenance amounts per contract. Without a margin declaration, margin fields stay null. Balance minus declared initial margin is arithmetic, not available equity or proof of margin adequacy.

The original extra round-trip tick remains a separate simulation comparator. It is not deducted again or split into the explicit entry and exit fees. All original events and negative balances are retained. An UNKNOWN exit retains inventory and its reservation; complete declared equity and return remain null. Reference prices never close or mark that position into a complete return.

## Prepare inspect and verify

Run from PowerShell inside the project. `prepare` reads pinned metadata only and writes a fresh registration; it does not open historical prices or project outcomes. Choose unused registration, report and failure filenames under an existing `logs` directory. The derived report-stem `_attempt.json` must also be unused.

These commands describe a later authorized calculation. The current development window's carry and no-trade projections are already complete and verified; do not repeat their inspections or verifications during this window.

This example declares a deliberately toy $100 seed, $1 per tick, ten-cent entry and exit fees, and no margin assumption. It is not a suggested trading budget or realistic broker configuration.

```powershell
Set-Location C:\Users\pabta\Projects\ai-trader
$economicsArguments = @(
    'prepare', '--control', 'carry',
    '--initial-balance-usd-micros', '100000000',
    '--initialized-at-ns', '1742990400000000000',
    '--account-currency', 'USD',
    '--tick-value-usd-micros', '1000000',
    '--entry-fee-usd-micros-per-contract', '100000',
    '--exit-fee-usd-micros-per-contract', '100000',
    '--margin', 'none',
    '--registration', 'logs/my_economics_1_registration.json',
    '--report', 'logs/my_economics_1_report.json',
    '--failure', 'logs/my_economics_1_failure.json'
)
$economicsRegistration = & .\.venv\Scripts\python.exe -m ai_trader.research.six_e_economics_operator @economicsArguments | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $economicsRegistration.status -ne 'registered_declared_economics_not_projected') {
    throw 'Registration failed or returned an unexpected status; retain evidence and stop.'
}
```

Check that the command exited successfully and returned `registered_declared_economics_not_projected`. Its returned registration hash is required for inspection. Inspection first claims a durable exclusive attempt, then verifies the complete original simulation and projects its event tape. It writes the registered attempt marker, new report and any retained failure evidence.

```powershell
$economicsInspection = & .\.venv\Scripts\python.exe -m ai_trader.research.six_e_economics_operator inspect --registration logs/my_economics_1_registration.json --registration-sha256 $economicsRegistration.registration_sha256 | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $economicsInspection.status -ne 'verified_local_declared_economic_projection_not_validation') {
    throw 'Inspection failed or returned an unexpected status; do not retry or delete the attempt.'
}
```

Check a successful exit and `verified_local_declared_economic_projection_not_validation`. That status establishes local reconstruction, not profitability. Use the returned report hash for a separate read-only verification:

```powershell
$economicsVerification = & .\.venv\Scripts\python.exe -m ai_trader.research.six_e_economics_operator verify --registration logs/my_economics_1_registration.json --registration-sha256 $economicsRegistration.registration_sha256 --report-sha256 $economicsInspection.report_sha256 | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $economicsVerification.status -ne 'verified_declared_economics_artifact_not_validation') {
    throw 'Complete verification failed or returned an unexpected status; the result is unverified.'
}
$economicsVerification
```

Expected status is `verified_declared_economics_artifact_not_validation`. It must reconstruct and compare the entire canonical report, not just its displayed balance. A changed report with a new hash cannot authenticate altered fees, omitted points, modified authority or a manufactured closure.

## Failure and scope safeguards

Inspection admits one attempt per registration. The attempt marker is claimed before original historical verification and remains on success, failure or interruption. An existing report, failure or attempt blocks another inspection. Do not delete partial evidence, retry automatically, rename outputs to hide a failed attempt or resume from a successful subset.

The operator checks the original metadata before historical dispatch, then calls the original complete verifier. Its event-only plan retains the original 40-key replay source map and journal genesis; the wrapper separately authenticates 47 source files. After projection it rechecks the registration, all original sidecars, read-only journal state, metadata and sources. Bounds remain three sessions, 2,000 events, 300 seconds and 16 MiB per JSON/sidecar. The existing read-only SQLite ledger retains its separate 128 MiB bound.

Fresh paths must be distinct JSON files beneath existing project `logs` directories. Links, junctions, alternate data streams, Windows device names and trailing-name aliases are refused, with path safety rechecked before writes. These checks do not establish immunity to an adversarial concurrent ancestor replacement.

Cash confirmation, margin confirmation, broker/CFD execution, trading, training, independent validation, strategy scoring, risk approval and promotion authorities remain false. Declaring assumptions on already-exposed outcomes is a sensitivity calculation, not independent preregistration. Funded simulation, measured execution evidence and defensible independent model validation remain separate work.
