# Capture quality and immutable trade cases: first implementation slice

Current update (2026-09-24): a [fresh public-data readiness check](REAL_DATA_READINESS.md) exposed
and fixed snapshot-availability lookahead in the standalone exporter and this audit. New artifacts
use envelope version 2 and `capture_quality_v2`; version-1 artifacts are rejected and must be
rebuilt. Buffered depth bridges the book only; CVD/warmup starts strictly after snapshot receipt.
The successful real-data smoke had no orders. Historical implementation details follow.

Implemented 2026-09-24, using synthetic tests only. No market-data collection, model training,
trading activation or Nautilus adoption is included.

## Read-only capture audit

`src/ai_trader/research/capture_quality.py` requires an explicit combined capture and its
microstructure artifact. It does not find the latest file or enumerate protected datasets.
It validates the capture, verifies source hashes, reconstructs every observation with the
artifact configuration, and compares exact typed/Decimal-string values. Missing footers,
extra rows, wrong schemas/counts, duplicate artifact JSON keys, non-finite values and changed
input files are rejected. Nothing is rewritten or automatically deleted/quarantined.

The report contains observation/trade counts, observation receipt boundaries and maximum gap,
rolling warmup, invalid attribution intervals, incomplete band/top-N coverage, unmatched trades,
pending trades at the last observation and trades arriving after that observation. It also
discloses whether the producer's code manifest matches the current package. Reproduction under
current code is required; manifest equality is not proof of origin or a signature.

`usable_observations` requires a complete rolling window, a valid evidence interval, and both-side
top-N/band coverage. It does NOT certify dataset size, regime diversity, economic value or live
readiness. Zero usable rows can still have valid artifact integrity. Full-session quality is
retrospective: never feed it into an earlier trading decision or use it to cherry-pick test outcomes.
Receipt gaps are not measured one-way network latency; monotonic timing remains future work.

For already selected research files (replace both paths with actual approved inputs):

```powershell
.venv\Scripts\python.exe -m ai_trader.research.capture_quality "path/to/capture.jsonl" "path/to/microstructure.jsonl"
```

Successful output is a `capture_quality_v2` JSON report. Invalid input emits `status: REJECTED`
and exits nonzero. No file is produced by the CLI. Do not use reserved holdout data to guide
feature/threshold selection. Capture QA is not a replacement for a registered selection policy.

## Case contracts

`src/ai_trader/trading/trade_case.py` adds deeply immutable records:

- `CaseEvidence`: stable evidence ID, availability in nanoseconds and observation hash.
- `EntryPlan`: positive finite quantity/reference/stop/target, holding horizon and expiry.
- `PreTradeCase`: source/policy/feature/state/risk identifiers, thesis, expected behavior,
  invalidation, evidence and recorded risk verdict. Only research/paper BTCUSDT is allowed.
- `PostTradeReview`: resolved outcome bound to the unchanged case, reviewer version and outcome
  evidence hash. Net PnL determines WIN/LOSS/BREAKEVEN separately from GOOD/MIXED/BAD/UNKNOWN quality.

Future evidence, duplicate IDs, mutable evidence collections, expired plans, invalid prices and
approved sizes above the proposal are rejected. `NO_ACTION` has no entry plan/approved quantity;
it never means liquidation. A review's lesson remains ANECDOTE, not a validated policy change.

These are minimal v1 records, not authenticated risk approvals or a full trade-management schema.
They do not prove a fill occurred or a case was persisted before an order. Fingerprints detect
different serialized content; they are not signatures and do not prevent constructing a new case
with the same ID. The subsequent [journal slice](TRADE_JOURNAL.md) enforces case-ID uniqueness
and append-only case/review persistence. Fill reconciliation, stop execution, MAE/MFE calculation,
risk/portfolio snapshots and management amendments remain to be implemented.
Rejected cases with unexpected fills need a separate incident-review path, not a normal resolved
trade review. Neither LLM output nor manually constructed records can authorize an order here.

## Runnable synthetic example and tests

No data download or optional native libraries are needed:

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_capture_quality.py::test_synthetic_observation_to_no_order_case
.venv\Scripts\python.exe -m pytest -q tests/test_capture_quality.py tests/test_trade_case.py
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
```

The example constructs a synthetic capture, builds and audits its artifact, then seals a no-order
warmup rejection using ONLY the first observation's available information. Expected outcome:
one passing example test, no orders and no lasting dataset outside pytest's temporary directory.

Next: order/fill lifecycle integration and recorder monotonic timing/recovery. Windows native-library
blocks still prevent full PyTorch/Nautilus verification; do not weaken security controls to bypass
them. A usable supervised paper loop has not been started by this change.

Actual verification: 62 new tests passed; Ruff lint and format checks passed. The full regression
attempt with `--continue-on-collection-errors` produced 498 passed, one optional-Nautilus skip and
the same ten PyTorch collection errors from Windows Application Control. This is not a fully
passing suite. Earlier roadmap/Nautilus edits were preserved; no commit or push was performed.
