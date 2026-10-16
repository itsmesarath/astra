# Non-executing numerical model shadow

`research/event_shadow.py` records predictions from a sealed numerical event baseline on one later
research capture. It does not train, read label artifacts, evaluate outcomes, open a trading journal,
create proposals, execute orders or change the default paper runtime. Verification is synthetic only.

## Model availability is an explicit boundary

`seal_event_shadow_model` accepts a completed **single-baseline** result and an independently pinned
result checksum. It checks the current training registration, split, recipe, passing fold provenance
and data-only model schema. No training capture is reopened. The seal stores the model/recipe/scope
hashes and the current wall-clock nanosecond timestamp. There is no backdating parameter.

The seal must follow both registration and the end of every research source used in that experiment,
including validation. This conservatively accounts for model-selection evidence, not only gradient
training. It is not permissible to replay an old session as though today's model already existed.
A walk-forward report is deliberately not accepted as a single deployable model, and no best fold
is selected. A separately specified final-fit protocol remains future work.

`replay_event_shadow` requires explicit `enable_shadow=True` before any input access, plus the sealed
bundle's independently pinned checksum. It reloads current-code training metadata and a separate
registration for the later source. Before opening the capture, it requires:

- A research source, never a reserved or unknown source.
- A source starting strictly after seal availability plus the original split embargo.
- No source-ID reuse, byte-hash reuse or time overlap with any original training, validation **or
  reserved** source. Renaming a reserved source does not clear this check.
- Exactly matching reconstruction/features and hypothetical outcome/cost protocol.
- No future-dated seal or capture.

Checksums and the local clock are not tamper-proof authentication or proof of prospective human
research decisions. Pin hashes in trusted records, maintain clock discipline and retain all trials.
Code/environment changes invalidate these artifacts; do not edit fingerprints to bypass the checks.

## Causal features, abstention and availability

Capture bytes are bounded and pinned once, then processed in receipt order by the existing replay
engine. Each observation is checked against its tick/hash/configuration. The adapter reuses the
event-label builder's feature allowlist and eligibility checks, without invoking its outcome logic.
Missing feature values remain missing. The model receives an X-only partition with empty target,
outcome-time and provenance arrays; stored preprocessing is never refitted.

Every frame is retained, including warmup, trade-only frames, attribution ambiguity, stale inputs,
spread violations, sequence faults and session closure. Only eligible new depth observations receive
three class probabilities in `[-1, 0, +1]` order: hypothetical costed long loss/breakeven/profit.
These are not SELL/HOLD/BUY instructions or calibrated trading confidence.

Prediction availability is `observation_receipt + decision_latency_ns`; exclusive expiry is
`observation_receipt + prediction_ttl_ns`. If availability reaches expiry or makes the quote/trade
input stale, the adapter abstains. Latency is an explicit simulation setting, not measured service
latency. A later consumer would still need current-state, source, health, expiry, risk and execution
checks. Each record explicitly states `order_authorized=false`; this module has no execution adapter.

Later faults cannot retroactively remove earlier predictions. A faulted or truncated run is
`incomplete`; no pooled success score or profitability claim is produced. A fully consumed fault-free
run can complete with zero predictions; this means processing completed, not model readiness.

## Bounds and safe commands

Frame budget: 1–10,000. Capture limit: 32 MiB. Seals: 1,000,000 bytes. Reports: 16 MiB. Inputs reject
quarantined partial paths. Reports use exclusive staged publication; existing files/partials are not
overwritten. Corrupt inputs, invalid probabilities, code drift or exhausted output bounds fail without
a final report. No native model dependency is installed or imported.

```powershell
.venv\Scripts\python.exe -m ai_trader.research.event_shadow seal --help
.venv\Scripts\python.exe -m ai_trader.research.event_shadow replay --help
.venv\Scripts\python.exe -m pytest -q tests/test_event_shadow.py
```

Operator workflow, not executed on actual data during development:

1. Validate approved research data, freeze a recipe and train/evaluate an approved single baseline.
2. Seal that completed result now, retaining the result and seal hashes independently.
3. Obtain a separately approved later research capture and register its source/configuration.
4. Run explicit shadow replay with a fixed processing budget, modeled delay and expiry.
5. Review quality/abstentions separately from subsequent predictive and economic evidence.

The CLI requires the training registration and split for both operations. `seal` additionally
requires `--result`, `--expected-result-sha256` and a new `--output`. `replay` requires `--seal`,
`--expected-seal-sha256`, `--source-registration`, `--source-session`, `--capture`, `--max-frames`,
`--decision-latency-ns`, `--prediction-ttl-ns`, a new `--output` and `--enable-shadow`.
Replay exit 0 means completed processing; exit 2 means an incomplete diagnostic report.

Real-data readiness, supervised capture/forward operation, final-fit/paper promotion and local Qwen
training remain separate gates. Live connectivity is still unavailable.
