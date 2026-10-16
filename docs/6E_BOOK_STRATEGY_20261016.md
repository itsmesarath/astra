# Order-book strategy study — the last untested information in the existing data (16 Oct 2026)

Owner request: "figure out a better strategy using existing data." Everything tested before
used trade prices and volumes only. The Databento archive is order-by-order (MBO), so this
study rebuilt the full limit order book for every minute of Mar 2025 – Jun 2026 (389 days,
`six_e_book_minutes.py`, run on the owner's PC in about 4 minutes, 0 errors) and used it in
two ways: as model inputs, and to simulate limit-order (passive) entries with real queue
positions (`six_e_book_strategy.py`).

**Book inputs tested** (all causal, at the decision minute): best-quote size imbalance,
5-level depth imbalance, microprice offset, order-flow imbalance over 1/5/15 minutes,
cancellation imbalance, spread, and large-trade imbalance.

**Result 1: the book carries no directional information at 15–60 minutes.**
Every book feature scored an AUC of 0.49–0.51 for predicting +20-before-−10 winners, in
both 2025 and 2026 (0.5 = coin flip). Adding book features to the walk-forward ridge model
made its monthly information coefficient slightly *worse* (h=60: +0.006 → +0.000).

**Result 2: passive entries save about 0.8 ticks per trade, not enough.**
Limit orders at the best bid/ask (queue = resting size, fill only when traded through or
when enough volume prints at our price, 15-minute wait, cancellations ahead ignored) filled
96.8% of the time. Per-trade result went from −2.21 ticks (market entry, 2.6 cost) to
−1.41 ticks (passive entry, 1.6 cost): the cost saving is 1.0 tick, of which about 0.2 is
lost to adverse selection. Both years agree (2025 −1.28, 2026 −1.56).

**Conclusion.** With this dataset, roughly 250 configurations across seven approaches
(seconds-scale scalps, minute models, session breakouts, news windows, hourly trend,
hindsight reverse-engineering, order-book features with passive entries) all lose after
costs. The one thing the data predicts reliably is *when* volatility rises, never
*which way* price goes. No further single-market 6E study on this archive is likely to
change that; a profitable strategy needs directional information from outside this
market's own history, or an instrument that pays for volatility itself.
