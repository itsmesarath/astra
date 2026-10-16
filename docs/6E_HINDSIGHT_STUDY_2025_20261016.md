# Hindsight-first "find the winners, then reverse-engineer" study — 2025 (16 Oct 2026)

Owner's idea: first find the profitable trades with hindsight, then work out what preceded them.

Code: `src/ai_trader/research/six_e_hindsight_study.py`. Results are in `data/processed/6e_hindsight_study_2025_1.json`.

**Step 1: hindsight.** At each decision minute (06:00–17:00 UTC), would a 2:1 trade have worked within 60 minutes? That means +20 ticks before −10.
- Of 129,063 minutes, **25.4% were winning long trades and 27.8% were winning short trades.** Profitable trades exist in large numbers.
- With hindsight, picking only these would make a fortune. The question is whether they can be recognised *before* they happen.

**Step 2: reverse-engineer.** Compare the 19 causal features at winning-trade minutes with all other minutes, using AUC (0.5 = no information).
- Features fitted on April–August 2025, scored on September–December 2025.
- The informative features are **all volatility and activity measures**: recent realized variation, range and volume. Their AUC was 0.53–0.58 for both long *and* short winners.
- These features say "a big move is coming", not *which way* it will go.
- The direction features (past returns, buy/sell imbalance) were near 0.5.
- A logistic model on all features reached AUC 0.55 out-of-sample.

| Side | Model's top-5% picks that were real winners | Base rate | Needed to break even on a 2:1 trade (before costs) |
|---|---:|---:|---:|
| Long | 28.5% | 22.7% | >33.3% |
| Short | 31.5% | 23.8% | >33.3% |

**Conclusion:**
- In 6E's own data, *when* big moves happen is somewhat predictable.
- *Which direction* they go is not, at least not enough to pass the 33.3% break-even of a 2:1 trade, let alone after costs.
- This explains all the earlier losses. Reverse-engineering finds the volatility, but no directional clue.

To profit from predictable volatility without knowing direction, one would need instruments that pay for movement itself, such as options strategies. Otherwise, directional information has to come from outside this one market's price history: other markets, scheduled news, or daily cross-market trend.
