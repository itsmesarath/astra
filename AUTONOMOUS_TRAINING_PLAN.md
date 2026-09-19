# Autonomous Paper-Trading and Training Plan

## Objective

Build a recoverable system that can ingest read-only public market data, validate and store it,
train candidate models offline, promote only candidates that pass fixed validation gates, and run
the selected model through simulated paper execution.

The system must never submit a live order, hold exchange credentials, or expose a code path that
can be switched into live execution.

## Safety boundary

- Market-data access is read-only and uses public endpoints only.
- Raw captures are immutable once a session is closed.
- Feature generation, labeling, training, and evaluation run on local files.
- Model output is only a position intention: `SHORT`, `FLAT`, or `LONG`.
- The deterministic risk engine remains authoritative.
- The only broker implementation is the local `PaperBroker`.
- No API keys, secrets, authenticated exchange clients, or live-order adapters are permitted.
- A kill switch must stop new paper exposure while still allowing simulated flattening.
- Candidate promotion is atomic and reversible; a failed cycle leaves the previous paper model in
  place.

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

### Phase C: autonomous paper inference

1. Replay new completed captures through the current paper champion.
2. Persist an append-only decision, risk, fill, and equity ledger.
3. Add session-level monitoring, forced paper flattening, and kill-switch tests.
4. Keep training and paper inference isolated so model replacement is atomic.

### Phase D: sustained evidence

1. Run many autonomous cycles without manual repair.
2. Require stable results across independent future sessions.
3. Diagnose drift, data failures, and model regressions.
4. Keep the project paper-only; live execution is outside this roadmap.

## Tomorrow's milestone

Start Phase A by implementing the cycle manifest and state machine around local, already-captured
session files. The first version will not download anything or run continuously. It will prove that
one offline cycle is deterministic, resumable, auditable, and unable to reach live execution.

After that foundation is tested, decide which operating mode is intended:

1. **Strict offline:** external files are placed into an inbox and the local cycle processes them.
2. **Read-only online data, paper-only trading:** an isolated public-data collector creates inbox
   files, but training and execution remain local and no authenticated exchange capability exists.

This decision changes only data arrival. It does not change the paper-only execution boundary.
