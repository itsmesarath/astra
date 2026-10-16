# Receipt-causal microstructure event labels

Implemented in `training/microstructure_data.py`, tested with synthetic captures only. This is an
offline, one-source research artifact builder, not model training, a strategy backtest, an execution
adapter or a running paper service. It never opens a trading journal or sends orders.

## Inputs and protection

Supply an explicit [microstructure registration](MICROSTRUCTURE_POLICY.md), one declared research
session, its capture path and a finite processing budget. Reserved/unknown session IDs fail before
capture access. Capture bytes, session framing/times, registration and implementation/environment
fingerprints must agree. Code/environment drift during construction prevents publication. Existing
registrations from older code fail closed; do not edit their fingerprints to bypass that check.

The builder reuses the receipt-causal replay/feature engine and validates observations against their
ticks. Snapshot buffering, sequence faults and freshness are not repaired or retrospectively hidden.
No directory discovery, network call, model installation, fitting or default-runtime change occurs.

## Sampling and feature contract

Every **emitted replay frame** is retained, including warmup, trade-only, invalid and footer frames.
This is not one row per physical raw record: replay controls when buffered data becomes available.
Eligible examples require a new synchronized depth observation, fresh quote/trades, complete rolling
window, valid attribution interval, covered depth bands/top-N, no unmatched/pending trade attribution
and an acceptable spread. Only eligible examples receive hypothetical outcome windows.

Sampling does **not** require the policy's positive CVD/OFI/imbalance, replenishment signal, cash,
position, reward/risk or sizing gates. Bearish evidence, losing paths and abstain-rule observations
are retained. This dataset predicts a hypothetical unit-long outcome, not the policy's trade choice.

The versioned 30-field `features` allowlist contains spread, imbalance, microprice offset, visible
depth, rolling buy/sell/CVD, OFI, attribution counts/quality flags and both sides' aggression,
replenishment and absorption proxies. `feature_units` declares BTC, fractions, basis points, counts
or booleans for every field. Decimal values serialize as strings; integers/booleans retain their JSON
types. Missing evidence stays `null`, not zero or false. Replenishment and absorption are public-L2
proxies, not proof of hidden iceberg orders.

Only `features` may later become model inputs. Source/row IDs, receipt times, hashes, eligibility,
frame status and outcomes are provenance, masks or targets, never predictive columns. Features use
only evidence available at `feature_available_at_ns`; they exclude future returns, exits, policy
actions and portfolio state. Changing future quotes cannot change an earlier feature vector/hash.

## Fixed hypothetical outcome protocol

The protocol and its checksum are recorded with the code, environment and registration fingerprints.
It inherits registered entry TTL, hold duration, stop/target distances, freshness/spread limits and
fee/slippage assumptions. It has no post-outcome parameter-selection interface.

1. Anchor the stop and target to the feature-time bid. Wait for the first new healthy depth quote
   with receipt time **strictly later** than the feature time and **before** the exclusive TTL.
   Snapshot, trade-only and equal-time quotes cannot fill. Reject that entry if its bid is at/below
   the stop, its slipped ask is at/above the target, or its spread exceeds the limit. Do not wait
   for a more favorable entry after a rejected first quote.
2. Hypothetically buy one BTC at ask plus slippage. Start the hold horizon at that entry's receipt
   time. This unit is a return normalization, not a funded/sized order or liquidity-fill assertion.
3. On a strictly later healthy depth quote, check stop, then target, then elapsed hold horizon.
   Exit at the actual observed bid minus slippage, including price gaps. A horizon between depth
   observations waits for the next healthy depth; do not invent a quote at the exact deadline.
4. With fee fraction `f`, calculate `debit = entry_price * (1 + f)` and
   `net_return_fraction = (exit_price * (1 - f) - debit) / debit`. Spread and slippage are already
   embedded in the prices; each side's fee is counted once. `direction` is the sign (-1, 0, +1)
   of this net return. A price target hit can still be a net loss. A negative label is not a short
   trading instruction.

Outcome status is explicit:

| Status | Meaning | Numeric return/direction |
| --- | --- | --- |
| `resolved` | Later entry and exit both observed under the protocol | Present; zero only for genuine modeled breakeven |
| `not_entered` | Entry expired or its first future quote failed bracket/spread checks | Null |
| `censored` | Session end, sequence/market fault, stale quote, excessive interquote gap or processing cutoff | Null |
| `excluded` | No new eligible feature observation | Null |

`known_at_ns` records when that outcome/status became known, separately from feature availability,
entry, planned horizon and actual exit times. If entered before censoring, known entry fields remain
but no exit or numeric target is fabricated. Final artifacts contain no unresolved `pending` state.
Faults are handled before price barriers or expiry on the same frame. Quote gaps are checked even
when a newly arrived quote is itself fresh. Each invocation ends at its own session boundary or
processing prefix; it never borrows a future quote from another capture.

Windows overlap. Their returns are **not** additive portfolio PnL, independent trade samples or a
profitability test. They do not model queue position, depth, partial fills, impact or execution
latency. Future entry/exit needs quote health, not renewed strategy-signal approval. Compare actual
policy/account performance through the [paper evaluation](PAPER_EVALUATION.md) separately.

## Limits and publication

- Existing replay limits apply (32 MiB capture, 100,000 physical records).
- `max_frames` must be an integer from 1 to 10,000, counting emitted frames. Processing never pulls
  an extra frame beyond that prefix. An early prefix censors unfinished outcomes explicitly.
- At most 2,000 examples may await outcomes concurrently; exceeding this fails the build without
  silently thinning observations. Resource limits are not evidence-quality or sample-size gates.
- Published checksum envelopes are limited to 32 MiB. In-memory returns remain frame/pending-bound;
  the serialized byte cap is enforced when publication is requested.

The output parent directory must already exist. A new `.partial` staging file is written and fsynced,
then hard-linked to the final name without replacement. The final JSON has `dataset_sha256` and
`dataset`; the checksum covers canonical sorted-key JSON. Existing final files and partials are
never overwritten. Failed staging/publication leaves a quarantined partial, not a successful final
artifact. A cleanup failure after publication warns that the partial remains. Filesystems without
hard-link support fail closed; there is no unsafe overwrite/copy fallback. This is not a claim of
power-loss durability for directory metadata.

Rows bind source session/line, tick, observation/features hashes and outcomes. The header records
source bytes/times, feature/label versions, protocol, processing budget, completion and status/reason
counts. `mode=research_only`, `promotion_allowed=false`, `training_started=false` and
`live_trading_available=false` remain explicit.

## Commands and verification

Safe help and synthetic tests, from the project root:

```powershell
.venv\Scripts\python.exe -m ai_trader.training.microstructure_data --help
.venv\Scripts\python.exe -m pytest -q tests/test_microstructure_data.py
```

Operator example only; no actual capture was processed during implementation. Replace placeholders
with an existing current-code registration, its declared research session and exact capture:

```powershell
.venv\Scripts\python.exe -m ai_trader.training.microstructure_data --registration data/processed/REGISTRATION.json --capture data/raw/RESEARCH.jsonl --source-session RESEARCH_ONE --max-frames 1000 --output data/processed/NEW_EVENT_LABELS.json
```

The CLI prints a compact header without rows. Exit 2 means an incomplete processing prefix or replay
market fault; an inspection artifact may still be published. Other exceptions fail the invocation.
Exit 0 means complete artifact generation only, **not** sufficient labels, approved quality,
profitable strategy, training readiness or permission to trade. Inspect censored/excluded counts.

## Next gate before fitting

The [verified artifact loader and whole-session split manifest](EVENT_TRAINING_DATA.md) now reproduce
features/outcomes from registered source bytes, keep reserved sessions inaccessible, check outcome
availability against strict fold cutoffs and freeze feature/missingness and sample criteria. Every
declared research source remains visible; a failed source gate blocks both partitions. Do not flatten
these rows into the legacy candle/depth loaders: they do not accept this schema.

The [bounded numerical baseline](EVENT_BASELINE.md) now has synthetic-tested, training-only
preprocessing and a frozen evaluation recipe. Actual market-data fitting still requires sufficient
approved data; Qwen fine-tuning remains a later gated stage. Separately authorized capture/smoke
and supervised forward-runtime checks remain
necessary for an operational paper service. No claim of usable real data or trading edge is made.
