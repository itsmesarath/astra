# Autonomous Paper-Trading and Training Plan

## Objective

Build a recoverable Binance Spot system that can ingest public market data, validate and store it,
train candidate models offline, promote only candidates that pass fixed validation gates, and run
the selected model through paper, Spot Testnet, or explicitly armed Spot live execution.

## Safety boundary

Implementation status (2026-09-20): the [execution-mode foundation](EXECUTION_MODES.md) now
provides explicit environment selection, a shared intent/receipt interface and a Spot paper
adapter. Testnet/live configuration is recognized but unconditionally blocked; authenticated
adapters and arming are not implemented. Public data ingestion may use internet access while
agents/inference remain local. A future live adapter should use this boundary without replacing
the strategy, but still requires the operational work in Phase D.

- Paper mode remains the default and requires no credentials.
- Execution modes are explicit: `paper`, `spot_testnet`, and `spot_live`.
- Spot intentions are long or flat only; the system cannot create short exposure.
- Raw captures are immutable once a session is closed.
- Feature generation, labeling, training, and evaluation run on local files.
- Model output is only a Spot position intention: `FLAT` or `LONG`.
- The deterministic risk engine remains authoritative.
- Every broker implementation must pass the same deterministic risk decision before execution.
- Credentials come only from environment or an OS secret store and are never written to artifacts.
- API keys must have withdrawals disabled and should use IP restrictions and minimum permissions.
- Live mode requires a separate arming flag and cannot be enabled by a model output.
- A kill switch must stop new exposure in every mode while still allowing flattening.
- Candidate promotion is atomic and reversible; model promotion never automatically enables live
  mode.

## Intended autonomous cycle

```text
read-only capture
    -> validate raw session
    -> build causal features
    -> wait for label horizon
    -> label completed session
    -> append to versioned multi-session dataset
    -> session-aware walk-forward training
    -> validation policy and paper-cost evaluation
    -> reject candidate or atomically promote paper champion
    -> record cycle manifest, metrics, and failures
```

Training should be periodic rather than per tick. A cycle should begin only after a configurable
number of new, fully labeled sessions exists. This avoids incomplete labels, excessive GPU churn,
and repeatedly fitting almost identical data.

## Model progression

### Stage 1: trustworthy baselines

- Keep the majority and linear classifiers as reference models.
- Add recent-return, realized-volatility, imbalance-change, and trade-flow momentum windows.
- Measure stability across source sessions, not only aggregate row accuracy.
- Tune class weighting and decision thresholds with walk-forward validation only.

### Stage 2: first neural model

- Implement a small regularized multilayer perceptron using the same causal feature schema.
- Use deterministic seeds, early stopping, train-only standardization, and versioned checkpoints.
- Compare it against the linear baseline under identical folds and paper costs.
- Reject it unless improvement is consistent across sessions.

### Stage 3: temporal model

- Build fixed-length causal sequences that never cross source-session boundaries.
- Compare a small temporal convolution or GRU with the MLP and linear baselines.
- Keep model size deliberately small until the dataset covers substantially more market regimes.

No model advances because it is more complex. It advances only when validation-only economic
evidence improves without unacceptable drawdown or unstable fold results.

### Stage 4: Qwen3-4B-Base meta-policy

- Run the base model quantized and train versioned QLoRA adapters rather than all parameters.
- Serialize causal, embargoed market windows and deterministic numeric-model outputs.
- Restrict output to validated long/flat regime JSON; reject malformed or out-of-range output.
- Treat Qwen as a slower regime/meta-policy model, never as the broker or risk engine.
- Compare it with numeric baselines under identical walk-forward and cost assumptions.

## Promotion requirements

A candidate may replace the current paper champion only when all fixed gates pass:

- minimum independent validation sessions and rows;
- minimum macro F1 and balanced accuracy;
- minimum directional signal count and coverage;
- minimum directional precision after policy thresholds;
- positive net paper PnL after spread, fees, slippage, and modeled latency;
- acceptable maximum drawdown;
- acceptable turnover and exposure concentration;
- no failed data-integrity checks;
- no open final paper position;
- no regression versus the current champion across walk-forward folds.

The final test session is evaluated once only after model and policy choices are frozen. Any session
used to compare candidates becomes validation data and can no longer serve as a final test.

## Data requirements

The current six sessions are enough to validate the pipeline but not enough to establish a durable
edge. Before treating results as meaningful, accumulate many independent sessions across:

- different hours of day;
- multiple days and weekdays;
- quiet and volatile markets;
- rising, falling, and range-bound periods;
- different spread and liquidity conditions.

Dataset manifests must retain source hashes, capture times, schemas, feature configuration, label
configuration, and exact session assignments.

The public Binance Spot archive downloader is now the historical-data entry point. Daily source
archives are checksum verified, retained unchanged, and normalized to millisecond CSVs with a
request manifest. Archived klines and aggregate trades do not reproduce historical order-book
depth, so historical models must not silently substitute them for depth features.

## Automation and recovery

The autonomous runner should be a finite-state cycle, not an unstructured collection of scripts.
Each cycle receives an ID and writes an append-only manifest containing:

- state and timestamps;
- input and output paths with hashes;
- configuration and code revision;
- completed session IDs;
- checkpoint identity;
- validation and paper-simulation metrics;
- promotion or rejection reason;
- failure details and safe retry point.

Required operational controls:

- one-process lock to prevent overlapping cycles;
- atomic temporary outputs followed by rename;
- idempotent restart after interruption;
- disk-space and data-freshness checks;
- quarantine for corrupt captures;
- bounded retention for generated artifacts while preserving manifests;
- explicit GPU/CPU resource limits;
- health summary and failure notification without autonomous live action.

## Delivery phases

### Phase A: autonomous offline research cycle

1. Add a cycle configuration and append-only run manifest.
2. Implement a `run_cycle` orchestrator around existing validated components.
3. Add locking, idempotency, atomic outputs, and resume behavior.
4. Trigger training only after enough new completed sessions exist.
5. Run walk-forward validation and the paper promotion gate.
6. Maintain `candidate` and `paper_champion` checkpoint aliases atomically.

### Phase B: richer features and MLP

1. Add causal rolling features without crossing session boundaries.
2. Add a small MLP checkpoint format and trainer.
3. Put linear and MLP candidates through identical walk-forward folds.
4. Record champion-versus-candidate comparisons.

Before model training, run cost-adjusted trade-setup studies on training sessions only. Future
returns define outcomes, while model inputs remain strictly causal. Embargo overlapping windows and
reserve final sessions so discovered patterns can be falsified out of sample.

### Phase C: autonomous paper inference

1. Replay new completed captures through the current paper champion.
2. Persist an append-only decision, risk, fill, and equity ledger.
3. Add session-level monitoring, forced paper flattening, and kill-switch tests.
4. Keep training and paper inference isolated so model replacement is atomic.

### Phase D: Spot Testnet and live execution

1. Define a shared broker protocol and add an authenticated, read-only account client.
2. Reconcile balances, symbol filters, open orders, and fills before permitting new exposure.
3. Add Spot Testnet execution with deterministic long/flat sizing, stop loss, take profit, session
   profit target, session loss limit, drawdown limit, and maximum trade count.
4. Require sustained Testnet evidence and explicit operator arming before `spot_live` is available.
5. Keep live credentials outside the repository and prevent withdrawal permission.
6. Fail closed on time drift, stale data, ambiguous order state, reconciliation failure, or network
   timeout.

### Phase E: sustained evidence

1. Run many autonomous cycles without manual repair.
2. Require stable results across independent future sessions.
3. Diagnose drift, data failures, and model regressions.
4. Keep paper and Testnet available at all times; live mode remains explicitly armed and bounded.

## Next milestone

Repair experimental validity before replacing the rejected strategy. The
[strategy research reset](STRATEGY_RESEARCH_PLAN.md) documents checkpoint-selection leakage,
impossible gap-stop fills, capital-accounting inconsistencies, and holdout provenance limitations.
Fitting, tuning and forward evaluation are now separated. Schema-3 loading also enforces feature
chronology and outcome boundaries, skips held-out value conversion, and records data provenance.
Kline labeling version 2 now handles opening stop/target gaps before intrabar touches, using the
opening price and timestamp. Existing datasets have not been regenerated.
Schema-4 walk-forward economics now carry capital/cooldowns and settle label-based trade PnL at
exit. Session limits reset against carried session-start equity; aggregate metrics use the same
settlements. A separate candle-replay API now provides independent raw-candle exits, candle-close
marked equity, fee-inclusive cash sizing, simulated buy/sell turnover and full-bar entry delays.
Schema-7 walk-forward integration records frozen evaluation probabilities/timestamps and can opt
into next-open/one-bar-delayed replay alongside separate label economics. All non-held-out research
candle archives are verified for feature and label consistency before fitting; only evaluation
sessions enter replay. Declared labeling-v2 horizons, costs, barriers and outcomes are recomputed,
and reports record feature/candle/label/calculation-module hashes. No held-out archive or real
historical experiment was used to verify the integration. Next freeze the research protocol,
data selection and cost/latency scenarios before running a registered research-only trial.
Do not load the final reserved block or automatically promote a model.
Keep physical lockbox isolation and full code/environment manifests on the remaining hardening list.
After those gates, test the registered slower trend-pullback hypothesis with volatility-scaled
price barriers and explicit cost stresses. No live connectivity is part of this milestone.

The final 10 sessions have no reported performance evaluation, but were parsed and included in
aggregate label counts; they are not a pristine lockbox. Keep them unopened and reserve fresh
confirmation data after freezing the protocol. Only credible out-of-sample economics should lead
to model expansion, QLoRA examples, or autonomous paper promotion.
