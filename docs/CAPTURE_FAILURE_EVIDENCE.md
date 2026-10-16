# Safe capture failure evidence and bounded follow-up

## Contract

Capture failures now carry an allowlisted `failure` object containing only schema version,
stage and reason. The fixed codes distinguish connection, snapshot, receiver, observer, idle
stream, message parsing, resource quotas, writing/finalization, integrity and publication failures.
Unknown errors remain explicitly unclassified. A code identifies the operation that failed,
not a verified network, exchange, operating-system or hardware root cause.

No exception messages, packet contents, exception `repr`, stack traces, socket close text,
paths from exceptions or credentials are serialized. Exception type names are separately
allowlisted; an unknown/custom name becomes `OtherError`. Classification never parses message
strings. Existing exception classes and failure/cleanup behavior are retained.

An inner code survives an explicit wrapping cause chain, bounded to eight exceptions, including
cycles. Implicit exception context is not traversed: a later cleanup or disk error reports its own
failure rather than claiming the earlier event caused it. Cancellation retains its observed stage.
This is diagnostic evidence, not a complete exception tree or an authorization signal.

The snapshot operation is classified **after** the worker-thread boundary. Python can recreate a
`TimeoutError` during Future adaptation and drop custom attributes; classifying only inside the
worker would lose the more specific reason. Synthetic injection tests cover this behavior.

The prospective campaign's failed timing sidecar, failure receipt and terminal audit row include
the same evidence for the escaping collection error. Diagnostic publication failures instead
report their own stage and may prevent a timing report. Disk failure can also prevent the campaign
audit/failure receipt itself. Never infer completion from a missing failure file.

Successful timing reports, capture schema, wall-clock receipts and v1/v2 plan contracts are
unchanged. Failed reports alone gain this evidence. The older opt-in retry supervisor also no
longer saves raw exception text. Its explicit retry budget is unchanged; the prospective runner
still makes one attempt per slot with no retries, substitution, successful-subset selection or
automatic resume. CLI runtime failures now print sanitized JSON rather than packet-bearing
tracebacks. Argument-parser errors retain normal usage errors.

## Verification and experiment

Baseline: **2,331 Python tests passed, one optional Nautilus skip** (100.69 seconds), all **38
JavaScript tests passed**, Ruff passed. Added 70 synthetic regressions covering all fixed codes,
invalid/forged/cyclic/over-deep evidence, unknown class names, no stringification, cancellation,
real collector error branches, report/audit agreement, retained partials and sanitized CLIs.
Focused capture tests: **332 passed** (22.48 seconds). Final full regression: **2,401 Python
tests passed, one optional Nautilus skip** (104.48 seconds), **38 JavaScript tests passed**,
Ruff lint/format passed (257 files). The frozen source remained unchanged during the full suite.

The implementation frozen for the next experiment is
`e07e992f614382bef00e4340739b471732bf1699b520ef72dbd6d2da21bf8022`.
One newly planned campaign uses three 120-second sessions (train, validation, reserved), with
five-second pauses. It uses the previous two-minute settings without changes: settings raw hash
`48f9d29d84f62fc1927c1ad8b38d2276cc374e3bea0ea73d55021c07efbd8126`.

Research processing remains capped at 5,000 frames/source and 10,000 total. It requires full
source consumption, unchanged 500-ms quote continuity/freshness, cost assumptions and a 50%
resolved fraction per source. A complete campaign may enter one fixed, gated NumPy baseline
attempt. Qwen fitting, promotion, credentials, orders and ongoing capture are not authorized by
these artifacts. Reserved bytes are checked only by acquisition integrity code, not by research.

The [earlier incomplete campaign](INSTRUMENTED_CAMPAIGN.md) and its original source pins remain
untouched. Its exact interruption cause was not established. A new successful sample would not
prove that the early-timeout correction caused success or establish sustained feed reliability.

### Pre-capture pins

Plan: `logs/btcusdt_instrumented_plan_20260925_2.json`, prepared at `1790325834738398500` ns;
raw SHA256 `07e953a452821fc379c5fb215f7c26b54029b8075ffa91d9c8d3a3c05dee44f7`.
New output directory: `data/raw/btcusdt_instrumented_20260925_2/`.

The separate research intent `logs/btcusdt_instrumented_research_intent_20260925_2.json` was
written before capture. Its raw SHA256 is
`e69078fb018a25436b43d1ea7517ab12377b28c96f00eeb026e4c771c008914f`.
It fixes source assignments, settings and at most one later gated NumPy attempt, never Qwen
training or execution. No previous capture is reclassified or used to replace a slot.

### Completed capture and first passing real-data quality fold

All three slots completed once, without retries or leftover partials. Acquisition integrity code
checked every slot. Research preparation then verified metadata/sidecars without opening raw
captures and retained the original assignments. Reserved raw data was not opened by labeling,
fold verification or the baseline attempt.

| Acquisition slot | Aggregate trades | Depth updates | Raw bytes |
| --- | --- | --- | --- |
| Train | 485 | 1,199 | 1,083,763 |
| Validation | 580 | 1,199 | 1,090,501 |
| Reserved (metadata only) | 607 | 1,200 | 1,223,917 |

Train telemetry recorded two QPC depth-receipt gaps above 500 ms: **517.5469 and 566.5150 ms**,
each spanning 100 ms of adjacent exchange-event time. Maximum measured loop lag was 25.9057 ms
and streaming queue wait 3.4660 ms. Validation's maximum depth gap was 228.1435 ms, loop lag
26.7279 ms and streaming queue wait 5.1136 ms. These measurements reproduce receipt stalling
without a correspondingly large measured loop/consumer backlog; they do not identify network
versus WebSocket-internal buffering or prove the root cause. No timestamps or gates changed.

Research preparation froze registration/split/recipe at `1790326363498453100` ns. Both research
sources were fully labeled and reproduced by the existing fold verifier:

| Fixed quality measure | Train | Validation |
| --- | --- | --- |
| Replay frames, full session | 1,671 | 1,763 |
| Eligible labels | 1,079 | 1,076 |
| Resolved | 856 | 974 |
| Censored | 223 | 102 |
| Excluded | 592 | 687 |
| Resolved / eligible | 79.3327% | 90.5204% |
| Replay market-fault frames | 0 | 0 |
| Original count/fraction gates | Pass | Pass |

Training censored 201 pending labels at stale-quote boundaries and 22 at session end; validation
censored 102 at session end. All 856/974 resolved outcomes used the frozen 10-second horizon.
The fold is available with 856 training rows and 974 validation rows, **reserved research reads
zero**. Passing these engineering gates is not statistical sufficiency or a trading edge:
overlapping labels from adjacent minutes are not independent trades or broad regime coverage.

### Baseline refused: one training class

The one predeclared NumPy attempt returned **`blocked_training_classes`**. Training class counts
were `[856, 0, 0]` in net-loss / exact-breakeven / net-profit order. It completed **zero epochs**:
`training_started=false`, model null and validation evaluation null. No preprocessing fit,
parameter optimization, model promotion, Qwen call/training or order occurred.

Read-only inspection of training labels found net unit-long returns of approximately
**-24.0020 to -22.8731 bps**, mean -23.7623 bps, under frozen fee/slippage assumptions. Even
exit/entry ratios before fees (but still including slippage) were -4.0300 to -2.8989 bps. These
are overlapping sampled-quote counterfactuals for one quiet two-minute session, not portfolio
PnL or a claim about every regime. Validation labels did not select costs, horizons, thresholds
or model parameters. No settings changed to manufacture positive examples.

The data-quality obstruction improved in this sample; **class diversity is the current numerical-
fitting gate**. Qwen's separate protected-case/custody requirements remain unchanged. This is
not a trained AI model or a profitable strategy.

### Artifact pins

Raw directory: `data/raw/btcusdt_instrumented_20260925_2/`.

| Artifact | Raw SHA256 |
| --- | --- |
| Receipt | `7753185e23610c31a015289417543b8d99214be0fea9cbe327d1cc3619de5947` |
| Audit | `94bdb80577df093da52f435d706008ec881f40d16b5ab51d57ca9c5f50240d1c` |
| Train capture | `8f0ecd27e110c4ff25e66ea53b73f3b2c49af579a68c170e5676cc1b21eb49ba` |
| Train timing | `ab13db797fc7dcc26a45f2e281816e5be0a7a2f61601e1e63ce66f40a9a4c315` |
| Validation capture | `9e6703070b38a430dfd6c59a1a38edcfaa9f280d71aaefa8b7eb794bd7817916` |
| Validation timing | `f585cb382ce5141dcff9a761f833d51a57a78f0f9b61c471ad9db875a15a0050` |
| Reserved capture, from acquisition receipt only | `d4d9fa0e11a7112716c618ec9ae6e8f556a1705b63b4f5613c788c0c85b38b38` |

Research directory: `data/processed/btcusdt_instrumented_events_20260925_2/`.

| Artifact | Raw SHA256 |
| --- | --- |
| Prepared receipt | `8eb22a1e25a91ff6a887c9a521d7318665b181e2ffb51c828737d04c51d38f85` |
| Registration | `bb4c3032f4d211747df0d49e35690fd9b826f86ffd502710c8bbea896b38278e` |
| Split | `cf18ff9e8dd80d2ce6d6edf00475eb64f7770948414fc1c751502687b6ea4b79` |
| Recipe | `f2331319bfbd72af08211f77ecd277e74527666f0a8c57688639f6c8c91a07f6` |
| Train labels | `b01f6bbb918cdad9ea72229adf4697009f7b9ae7005aff863bfda5d4360f46bf` |
| Validation labels | `6ba9957fe9fa0c5a9f8ed725cdc5253ee1c6b92f4883f3dc2e793b71993afd39` |
| Fold report | `1bf632810dcbf19cf7a2d57363b17bb6d116dc6eccda6f552b826910e5550783` |
| Baseline refusal | `3b1867a81f2d83d0079d0ae54b81e928a5bca05c9cda6cbd32c6289ebd3db2ac` |

Baseline canonical payload digest (not its raw file hash):
`a11fec79d5e930d443556c54921035eb7962c4b2af4582d95bcd3877c0f4bc9c`.
The frozen `e07e992...` implementation remained unchanged through collection, labels and refusal.
Do not rewrite pins to resume under later source changes; retain historical failed results.

Next: a bounded corpus-coverage/class-readiness report and a prospective plan for more independent
time windows/regimes. More rows from the same quiet minutes, duplicated positives or borrowing
validation/reserved examples cannot satisfy that need. Any new label hypothesis must be separately
predeclared and tested on fresh data, not tuned until this inspected fold looks profitable.
Changes remain local and uncommitted.
