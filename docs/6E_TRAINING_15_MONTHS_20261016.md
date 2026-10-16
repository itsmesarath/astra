# Training on 15 months (Mar 2025 – Jun 2026) — results (16 Oct 2026)

Owner decision (16 Oct 18:01): train on 15 months and keep **Jul–Sep 2026 sealed** as the one-time final exam. Code changes:
- The lockbox cut-off moved from 2026-01-01 to 2026-07-01.
- The 2026 contract rolls were added (6EH6 → 6EM6 on 9 Mar, → 6EU6 on 8 Jun).

Data: 389 days decoded into `data/processed/6e_minute_bars_dev_1/`, with 0 decode errors. Runner: `scripts/run/run_6e_dev_bars.cmd`, log in `logs/six_e_dev_bars_1/run.log`.

All tests below are walk-forward: refit monthly on all earlier months, then test each month from July 2025 to June 2026 (12 months) once.

| Model | Trades | Net ticks/trade | Losing months |
|---|---:|---:|---:|
| Minute ridge, 15-min horizon, top 10% (cost 2) | 2,963 | −1.96 | 11/12 |
| Minute ridge, 30-min horizon, top 10% (cost 2) | 1,786 | −1.75 | 9/12 |
| Reversal r15, 60-min horizon (cost 2) | 2,793 | −1.70 | 11/12 |
| **Trained opportunity model** (+20/−10 bracket, top 5% picks, cost 2.6) | 903 | −2.62 | **12/12** |
| Hourly trend, best (momentum, limit −2, 3 ATR) | 527 | −2.56 | — (2025 −812, H1-2026 −536) |

The hindsight study on 15 months gave the same answer:
- Volatility and activity predict *that* a big move comes, with AUC 0.55–0.59.
- One split showed short picks hitting 36%. Under monthly walk-forward that did not survive: the win rate was 33.6%, gross about 0.

**Conclusion.** With 15 months, the result is unchanged from 9 months. Using the data and model types tried, 6E's own price and order-flow history gives no directional edge after costs. More of the same data does not create the missing information.

No candidate is frozen. The lockbox stays sealed.
