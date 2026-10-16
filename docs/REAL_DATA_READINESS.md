# Fresh-feed readiness and snapshot-causality correction

Measured 2026-09-24: one new **60-second public BTCUSDT capture**, one attempt, no reconnects
or retries. It passed the existing recorder integrity/freshness checks without changing limits.
An offline, kill-switch-armed paper smoke consumed the session successfully with zero orders.
This is an operational research sample, not held-out evaluation, a profitable strategy or training.

Verification: 34 new regression tests; full suite **2,124 passed, one optional Nautilus skip**
(92.16 seconds). Ruff lint and formatting pass.

## Observed results

| Check | Result |
| --- | --- |
| Capture size / records | 892,653 bytes / 1,225 |
| Aggregate-trade / depth events | 622 / 600 |
| Receipt minus exchange-event timestamp | 68.3923–168.2362 ms |
| Maximum receipt minus trade-execution timestamp | 195.2362 ms |
| Existing 2-second lag / 100-ms future-skew violations | 0 |
| Offline paper frames / market faults | 1,206 / 0 |
| Healthy quote frames | 1,204; the other 2 are unsynchronized boundary frames |
| Simulated orders / position / ending cash | 0 / 0 BTC / 1,000 USDT |
| Corrected feature observations | 585 |
| Snapshot-buffered applied depth updates / trades excluded from features | 5 / 3 |
| Warmup / quality-usable observations | 101 / 484 |
| Incomplete top-N / liquidity-band observations | 0 / 0 |

The feature audit also reports one invalid evidence interval and 28 unmatched trades; no trades
remain pending or arrive after the last observation. Its usable-row definition is warmed context,
valid interval and both-side depth coverage, **not** the stricter event-label eligibility rule.
Do not call all 484 rows training-ready. One minute does not establish stable latency, independent
samples, regime diversity or model quality. Receipt differences are not measured one-way network
latency and do not establish the cause of the earlier failed capture.

## Real-data test uncovered a feature-export bug

The original standalone exporter emitted its first row at `1790281315984816500` ns, while the
REST snapshot was not received until `1790281316387757500` ns: **402.941 ms later**. It also seeded
CVD and rolling warmup from buffered trades before that boundary. The previous quality audit
reproduced the same flawed algorithm, so a reproduction pass alone did not catch this lookahead.
The paper replay already handled the boundary correctly and never used those premature rows.

Fixed the standalone exporter and its quality audit:

- Require explicit, ordered integer session-start, snapshot-request and snapshot-receipt times.
  Missing availability is rejected rather than inferred from the first stream event.
- Buffered depth updates bridge book state only. Receipts at or before snapshot availability
  emit no feature rows and do not initialize the causal CVD, warmup or attribution state.
- Start an independent feature engine on the first strictly later receipt. A separate full-stream
  validation engine retains the earlier numeric, sequence, chronology, coverage and buffer guards;
  its rows and accumulated state are never exported or reused as causal feature state.
- Version the standalone artifact envelope to **2**, retaining the unchanged numeric observation
  field schema, and explicitly record snapshot time, snapshot policy and post-snapshot CVD policy.
- Return `capture_quality_v2`, with separate snapshot-buffered counts. Emitted observations plus
  buffered applied depth updates must account for all applied depth updates.

All **585 rebuilt observations** were compared field-for-field against the independent existing
`CaptureReplay` path and matched exactly. The first corrected row is 97.0991 ms after snapshot
receipt. Tests cover earlier/equal/later receipt boundaries, retained book updates, excluded trade
sizes, cold warmup, exact replay parity, missing/malformed metadata, old/tampered artifacts and
invalid buffered events. Validation uses two bounded engine states, not a new network worker.

The old 590-observation artifact and its 500-usable-row result are superseded and **must not be
used for training**. They remain on disk for diagnosis, not silently rewritten or deleted. The
current audit refuses version-1 standalone artifacts; regenerate from their original captures
under the corrected contract. A legacy capture without recorded snapshot availability cannot be
made eligible by inventing timestamps. Other legacy CSV loaders were not changed. The event-label
and paper paths already use `CaptureReplay`; their model feature fields were not changed.

## Reproducible local artifacts

All are local/Git-ignored. The source session is `readiness-btcusdt-20260924-1`. Raw SHA256 pins:

| Artifact | Raw SHA256 |
| --- | --- |
| `data/raw/capture_audit_20260924_readiness_1.jsonl` | `fda366a9c37c7f1d1e07962f0385e29001a5b42bd597b8bcfcf860b8d53e7b51` |
| `data/raw/btcusdt_13070114f0e04eb5a28f1336ea9d92c8_attempt_1.jsonl` | `26f608c341d7562602a9abfa663701af18d68430aca66fb130e599ff076bbb7c` |
| `data/processed/readiness_microstructure_20260924_1_v2.jsonl` | `8d3ffce2c6a855757361e1490e57345d5218a1736dd67634eebebee973ea911a` |
| `data/processed/readiness_paper_20260924_1_v2.sqlite` | `1c0de0823cc895976dfd6fcb173966518da12ad20a5112f2560bed450fdf07e9` |

The original v1 feature artifact has hash
`6f5004e61a68c6389fd299e192d919be969640f419833fb1335d0ccc1ebf0f4f` and is invalid for future training.
The original pre-fix smoke journal is also retained as historical evidence. A new dedicated v2
smoke journal was used after the source change; the old journal was not resumed under new code.

Read-only reproduction:

```powershell
.venv\Scripts\python.exe -m ai_trader.research.capture_quality data/raw/btcusdt_13070114f0e04eb5a28f1336ea9d92c8_attempt_1.jsonl data/processed/readiness_microstructure_20260924_1_v2.jsonl
```

Code-manifest equality may change after later edits; artifact/source hashes and actual
reconstruction remain separate checks. Do not change fingerprints on old registered experiments
or journals to bypass source drift. Capture/paper registration manifests need fresh preparation
when their bound implementation changes.

## Next

Completed next milestone: a [frozen multi-session acquisition plan](PROSPECTIVE_CAPTURE_PLAN.md)
collected three new one-minute sessions assigned train/validation/reserved before collection.
No retries or role changes were made; raw integrity checks passed. This inspected operational
sample was not relabeled or included as a final holdout. Next validate causal event labels and
numerical baselines on the declared research sources, leaving the reserved raw source unopened.
Qwen still needs separately sourced evaluation cases and substantiated custody before its existing
bounded LoRA trial; the current protected registry is empty. No Qwen fitting, downloads, credentials,
account connection or live execution was added. Only public market data used the internet.
