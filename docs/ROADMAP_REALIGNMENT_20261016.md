# Roadmap realignment: NinjaTrader live data → paper → controlled learning → live

Date: 16 October 2026. Status: **ADOPTED by the owner on 16 Oct 2026, 17:02 Lisbon** (decisions in §7). This file replaces no existing plan. Nothing was deleted, and the paused work is preserved. The snapshot and these changes are committed only on the local branch `wip/2026-10-16-snapshot`.

## 1. Verdict: the project has drifted off track

The owner's goals are:

1. Use NinjaTrader's live market-data subscription.
2. Paper trade through NinjaTrader.
3. Trade live later.
4. Build a bot that improves itself from its own evidence.

The foundation built up to about 4 October points at these goals. The work since 8 October does not.

| Period | Main work | Moves toward the goals? |
|---|---|---|
| Sep – 4 Oct | Capture/validation, order-book reconstruction, causal features, paper ledger/risk/journal, walk-forward training, 6E historical classifier, Qwen pilots, **NinjaTrader capture indicator (1 Oct)** | Yes. This is the right foundation. |
| 8 – 16 Oct | The 6E "evidence pipeline": payload binding, native decoder qualification, then proofs about reading **one invented local file** through a Windows subprocess bootstrap. That includes byte-exact recording-budget certificates, owner/cleanup proofs and 2,447 pure tests of helpers. | Almost not at all. |

Measured from the folder:

- From 8 to 16 October, 355 of 363 new or changed files in docs/tasks/scripts/src/tests concern 6E/native/local intake.
- `logs/` holds 4.2 GB.
- Since 4 October, no market data was captured, no model was trained, no paper trade was made, and the NinjaTrader indicator was never run.
- The intake contract itself says: *"A plain file reader would be shorter."*
- **Nothing has been committed since 4 October.** About 400 changed or untracked files exist only in the working tree.

The obligations now open (whole-R1 certificates, R2 governor, six-role integration, G4/G1–G3 filesystem qualification, L1–L15) would take many more weeks. Even when complete, they would prove only that a local file was read correctly. They do not bring the NinjaTrader path any closer, because live NinjaTrader data never goes through that intake chain.

### Why it happened

Each step was locally reasonable: never trust data you haven't verified. But the verification standard meant for the money boundary (orders, live accounts) was applied to every helper. Every slice then needed:

- a registration,
- a time window,
- independent literal oracles,
- RED/GREEN runs,
- sensitivity mutants,
- an independent review,
- reconciliation of whole-repository pins.

Each review found a new edge case, and each edge case became a new proof obligation. The loop feeds itself and produces almost no product. My own derivation earlier today, on the protected cleanup tail, continued that loop. It is correct, but it is part of the same drift.

## 2. What to keep (aligned and valuable)

- Causal, no-lookahead features. Visible gaps and quarantine instead of silent repair. Source/config identity on data.
- Deterministic code owns risk, sizing and execution. AI proposes or abstains; it never places an order directly.
- Paper ledger, journal, stop/target/max-hold handling, kill/daily-loss checkpoints, post-trade reviews.
- Chronological walk-forward, training-only preprocessing, comparison against simple baselines, costs included.
- Live trading fails closed and needs explicit manual arming.
- "Self-learning" means **controlled batch retraining with promotion gates**. The live policy is frozen while it is being evaluated. Weights are not changed after every trade. That is the right definition, and it is kept.
- The NinjaTrader indicator `integrations/ninjatrader/AiTraderSixEDataCapture.cs`, the shared `BoundedCaptureWriter.cs` and the offline audit `ai_trader.research.platform_capture` ([guide](NINJATRADER_CTRADER_CAPTURE.md)).

## 3. What to pause, not delete

- The local-member intake proof chain: R1 certificates, R2 governor, producer corrections, G4/filesystem, L1–L15, and its execution boards and windows.
- It stays preserved exactly as it is and can be resumed later if historical-archive provenance becomes the bottleneck.
- Historical Databento data that is already decoded and in use can stay available as research input, with its known limits documented. It must not block live work.

## 4. Proportional rigor (proposed rule)

| Tier | Applies to | Required evidence |
|---|---|---|
| T1 Research code | Features, labels, notebooks, analysis, converters | Ordinary unit tests and a code review. No windows, registrations or literal-oracle packets. |
| T2 Paper path | Decision engine, Python↔NinjaTrader bridge, journal reconciliation | Tests plus a recorded Sim101 session and a fill reconciliation report. |
| T3 Money boundary | Live account selection, order sizing caps, kill switch, arming | Today's full discipline: independent review, adversarial tests, manual arming, written go/no-go. |

## 5. Realigned roadmap, with exit criteria

**P0 — Secure the work (owner action needed).**
- Commit the current working tree to a new branch, for example `wip/2026-10-16-snapshot`, so 12 days of work are not lost.
- Mark the intake chain PAUSED.

Exit: nothing exists only in the working tree.

**P1 — NinjaTrader live data capture (start here).**
- The owner connects the NinjaTrader data feed. Check that the subscription covers CME depth for the chosen contract and that its terms allow personal automated use.
- Run the existing indicator once for a 1-minute smoke capture.
- Audit the file with `platform_capture`.
- Then run daily bounded sessions during liquid hours.

Exit: at least 10 clean sessions; gap/reset/heartbeat statistics reported; depth updates confirmed.

**P2 — Converter + features from NinjaTrader data.**
- Map the NinjaTrader JSONL into the existing causal feature pipeline.
- NinjaTrader does not give confirmed aggressor side, so classify trades with a documented rule (trade at/above ask = buy, at/below bid = sell, otherwise tick rule) and flag that as approximate.

Exit: features reproduce on replay; quality reports work per session.

**P3 — Strategy research on NinjaTrader sessions (+ Databento history as context).**
- Event labels with real CME tick size, commission, exchange fees and at least 1 tick of slippage.
- Simple baselines first, then the existing NumPy classifier, then walk-forward.

Exit: a pre-registered after-cost result on sessions that were not used for fitting. If there is no edge, report that honestly and iterate on research. Do not move on to P4 with a losing policy.

**P4 — Paper trading through NinjaTrader Sim101.** Architecture:

```text
NinjaTrader (OnMarketData/OnMarketDepth) ──► capture/feature stream ──► Python decision engine
        ▲                                                                   │ proposal
        │ fills/positions                                                   ▼
NinjaScript strategy (Sim101 only) ◄── local bridge (named pipe/socket) ◄── deterministic risk
```

- Run shadow mode first: decisions are logged and no orders are sent.
- Then send orders to Sim101. NinjaScript keeps hard guards of its own:
  - account name must be a Sim account,
  - max 1 contract,
  - daily loss stop,
  - a flatten-on-disconnect rule.
- Fills are reconciled into the existing journal.

Exit: at least 4 weeks of supervised paper; fills reconciled with no discrepancy; results within the costs assumed in P3.

**P5 — Controlled learning loop ("self-learning").**
- On a regular schedule (for example weekly): add new clean sessions, retrain a challenger, run walk-forward against the frozen champion.
- Promote only if gates written in advance pass: after-cost PnL, drawdown and calibration. Every promotion is recorded and can be rolled back.
- The language model (Qwen) stays an optional reviewer of evidence. It is not the trader.

Exit: at least one challenger cycle completes end to end. "No promotion" is an acceptable result.

**P6 — Live pilot.**
- Same bridge, live account only after manual arming.
- Micro contracts only (for example micro EUR/USD), 1 contract, a hard daily loss cap and a kill switch.
- Futures margin for a micro contract is normally far above EUR 100. Confirm with your broker. Never raise capital automatically to meet a minimum.

Exit: an owner-signed go/no-go after the P4/P5 evidence.

## 6. Market focus

The authoritative plan (`AUTONOMOUS_SYSTEM_PLAN.md`) is centred on BTCUSDT Spot via Binance. The owner's stated goal is NinjaTrader. **Proposed: make NinjaTrader futures (6E/M6E first) the primary track.** BTC Spot becomes a secondary research track; its components are reused where they are generic (ledger, risk, features, training). The owner must confirm this.

## 7. Owner decisions (16 Oct 2026)

1. Intake proof chain: **PAUSED** (preserved; resume only if archive provenance becomes the bottleneck).
2. Primary track: **NinjaTrader 6E**, with **M6E** for the eventual live pilot. BTC Spot becomes secondary.
3. Snapshot: **committed** on local branch `wip/2026-10-16-snapshot` (commit 87c6a8f; not pushed; `main` unchanged).
4. Rigor: **three tiers adopted**; `AGENTS.md` updated.

Original questions as asked:

1. Pause the intake proof chain (recommended), or continue it in parallel?
2. Make NinjaTrader 6E/M6E the primary track, and choose the instrument (6E, M6E or another CME contract)?
3. Approve a commit of the current working tree to a WIP branch?
4. Adopt the three-tier rigor rule, so `AGENTS.md` can be updated to match?

## 8. Amendment — historical-first training (owner request, 16 Oct 2026 17:10 Lisbon)

The owner asked to train on the downloaded 6E history *before* connecting NinjaTrader live data. P3 (research and training) therefore moves ahead of P1. P1 capture can start whenever convenient: it is not needed for this phase.

**The data on disk.** Three Databento GLBX.MDP3 **MBO** batch downloads in `downloads/` (`GLBX-20260926-*.zip`). Together they hold 471 daily files of all 6E contracts from **2025-03-26 to 2026-09-25**, with full 24-hour sessions. The existing session manifest `data/processed/6e_training_manifest_20261002_1.json` splits them as follows:

| Period | Status | Use from now on |
|---|---|---|
| Mar–Dec 2025 (196 decision sessions + 45 excluded) | Already exposed by earlier research | Research, feature design, training, walk-forward |
| Jan–Mar 2026 (77 dates) | Reserved, never opened | Validation, opened once a candidate is frozen |
| Apr–Jun 2026 (78 dates) | Reserved, never opened | Test, opened once |
| Jul–Sep 2026 (75 dates) | Lockbox, never opened | Final go/no-go before paper |

**What the earlier research found (4–8 Oct).**

- Every tested intraday rule lost money after costs on the 2025 sample. Cost was modelled as crossing bid/ask on entry and exit plus 1 tick, with exits at a ±3-tick bracket or after 15 seconds:
  - CVD-follow, liquidity-follow, absorption-fade, failed-auction, breakout and burst-follow all lost roughly −2.1 to −2.8 ticks per trade over thousands of trades.
  - Every month was negative.
- The ridge model's best predicted return was about −1.8 ticks everywhere, so it always abstained.
- The earlier opportunity classifier predicted *activity* better than *direction*: balanced accuracy 34.88%.
- Only the 12:00–16:00 UTC window was studied.

**Why that matters for the next training.** At a ±3-tick, 15-second horizon, the cost of taking liquidity is about the same size as the typical move. Training a bigger AI model on the same labels will not fix that. The next study changes the *problem*, not just the model:

1. **Feasibility census first.** For horizons of 1, 5, 15, 30, 60 and 240 minutes, and for each UTC hour, measure on 2025 data how often the move exceeds round-trip cost. This tells us where an edge is even possible.
2. **NinjaTrader-compatible features only.** Live NinjaTrader gives aggregated 10-level depth and trades without an aggressor flag. Databento MBO is richer. To make a model trained on history run on live data, features are computed from an MBP-10-equivalent book plus trades classified by bid/ask, exactly as the live converter will do it.
3. **Labels in cost units at the feasible horizons.** Compare taking liquidity with passive limit entries (modelled with conservative queue assumptions).
4. **Models:** the existing NumPy baseline and walk-forward machinery; gradient-boosted trees or a small torch sequence model only if the baseline shows signal. PyTorch is already installed in `.venv`. Fit on 2025 only; open Jan–Mar 2026 once to validate.
5. **Compute:** heavy decoding runs on the Windows machine, from a PowerShell command the owner starts. The linked VM is too small, with 2 CPUs and 3 GB RAM.

## 9. Amendment 16 Oct 2026 (evening): execution venue and data — owner decisions

Owner statements: wants intraday trading, 5–10 trades a day, patterns (breakouts, reversals,
trends) combined with Level 2 "so entries are more perfect and losses smaller", a better P/L
ratio; has an IC Markets account; intends to **take Level 2 from NinjaTrader (CME 6E book,
customised CME plan ≈ €16/month) and execute on cTrader (IC Markets)**.

Evidence that shaped the plan (docs/6E_SESSION_PRICE_ACTION_STUDY_20261016.md):
- At sub-hour holds every pattern loses the cost; P/L ratio is a dial (wider target ⇒ lower
  win rate, same expectancy). Trade count must come from breadth (many instruments), not from
  lowering the bar on one.
- The book carries no direction but works as a *filter*: the failed-breakout reversal with
  the 4-hour trend, in the London window, only when the book is thick, is the first
  non-negative candidate (~70 trades, CI includes zero).
- IC Markets Raw Spread costs ≈ half of 6E round trip; micro lots allow live learning at
  cents of risk; one account covers FX majors, gold, indices.

Plan changes:
- **P1 (capture)** unchanged: NinjaTrader `AiTraderSixEDataCapture` streams the 6E book.
  Add a rolling 6E-minus-spot basis estimate so book levels map onto spot EURUSD.
- **P3 (strategy research)**: multi-market, multi-year test on free Dukascopy 1-minute
  history (`scripts/data/fetch_dukascopy_minutes.py`, `pa_multi_market_study.py`) with the
  IC Markets cost model; the 6E archive remains the testbed for the book filters.
- **P4 (paper)**: replace Sim101 with an **IC Markets cTrader demo via the cTrader Open
  API**: engine reads the NinjaTrader book tail + cTrader prices, places bracket orders,
  the auditor logs every decision with the book state that justified it. Trade only when
  both feeds are live; flat before CME/CFD session gaps.
- **P6 (live pilot)**: 0.01-lot live on IC Markets after a recorded demo period passes the
  T2/T3 gates; NinjaTrader/CME futures execution deferred.
- Entries are market-like at the CFD (no CME queue position); the 0.8-tick passive saving
  does not transfer and is no longer assumed.
