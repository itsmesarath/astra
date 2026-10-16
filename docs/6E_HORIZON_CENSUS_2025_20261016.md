# 6E horizon feasibility census — 2025 development data (16 Oct 2026)

Roadmap §8 step 1. Code: `src/ai_trader/research/six_e_horizon_census.py`, with tests in `tests/test_six_e_horizon_census.py`. Run with `scripts/run/run_6e_horizon_census.cmd`.

The run took about 35 s on the owner's PC. Unit tests: 57 passed.

Outputs (not tracked in git):
- `data/processed/6e_minute_bars_2025_1/`: one bar file per day, 238 days.
- `data/processed/6e_horizon_census_2025_1.json`: the census results.
- `logs/six_e_horizon_census_1/run.log`: the run log.

**Scope:**
- **Data:** Databento GLBX.MDP3 MBO, 2025-03-26 to 2025-12-31. Only days the vendor marked "available" were used: 238 days, 0 decode errors.
- **Contract:** the declared front contract (6EM5 → 6EU5 → 6EZ5 → 6EH6, rolling 8 Jun / 8 Sep / 8 Dec). The Dec 8 roll is early, so a few days around 8–12 Dec have low volume.
- **Prices:** trade prices only, using 1-minute closes. No order-book reconstruction.
- **Reserved data:** every 2026 date is refused by filename before any archive member is opened. Jan–Sep 2026 stays untouched.

**Result: absolute move from one minute's last trade to the minute h later, in 6E ticks** (1 tick = 0.00005 = $6.25 per contract)

| Horizon | Median | 75th pct | 90th pct | Share ≥ 4 ticks | Share ≥ 6 | Share ≥ 12 |
|---|---:|---:|---:|---:|---:|---:|
| 1 min | 1 | 3 | 5 | 17% | 6% | 1% |
| 5 min | 3 | 6 | 10 | 46% | 28% | 7% |
| 15 min | 6 | 10 | 17 | 66% | 50% | 22% |
| 30 min | 8 | 15 | 25 | 75% | 62% | 35% |
| 60 min | 11 | 21 | 35 | 82% | 72% | 49% |
| 240 min | 24 | 44 | 73 | 92% | 87% | 73% |

**By time of day (UTC), 60-minute horizon:**
- The median move is largest at 12:00–15:00, the US open, with 16–20 ticks.
- 06:00–08:00, the European open, is next with 13–15.
- It falls to 7–8 in the Asian hours (02:00–04:00) and is lowest at 20:00–23:00.
- The 15-minute horizon shows the same pattern.

**What this means:**
- Round-trip cost when taking liquidity is roughly 2–3 ticks: the spread, commission and exchange fees, and some slippage.
- At the 15-second to 1-minute horizons tested before, the typical move (about 1 tick) is smaller than the cost. That explains the earlier uniform losses.
- At 15–60 minutes, the typical move is 2–5× the cost. An edge is therefore *possible* there, if direction can be predicted better than chance.
- This census measures only the size of moves, not whether direction is predictable. A random direction still loses the cost on average.

**Caveats:**
- Closes are last-trade prices, so bid/ask bounce adds up to about 1 tick of noise.
- Minutes with no trade are skipped, not filled.
- This is descriptive only: nothing was trained or traded.

**Next step (§8 steps 2–4).** Build the training dataset on 2025:
- one decision row per minute, 06:00–17:00 UTC;
- causal features that NinjaTrader can also produce live (returns, range, volume, signed volume/CVD by bid/ask rule, time of day, and later 10-level depth);
- labels: forward 15/30/60-minute return net of a fixed cost, in ticks.

Fit with chronological walk-forward on 2025 against simple baselines. Open Jan–Mar 2026 only once a candidate is frozen.
