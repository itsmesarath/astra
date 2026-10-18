"""Market-structure features on hand-built bars: swings, BOS, order block + mitigation, equal lows + sweep."""

import numpy as np

from ai_trader.research import market_structure as ms


def _bars(closes, rng=2.0, opens=None):
    """Bars with the body from open to close; opens default to the previous close (so the body spans the move)."""
    c = np.array(closes, dtype=float)
    o = np.array(opens, dtype=float) if opens is not None else np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) + rng
    l = np.minimum(o, c) - rng
    return o, h, l, c


def test_swings_and_bos():
    # rising zigzag: swing lows at troughs, swing highs at peaks, a bullish BOS after each peak is cleared
    closes = [100, 103, 106, 103, 100, 104, 108, 112, 109, 106, 110, 114, 118, 115, 112, 116, 120, 124, 121, 118, 122, 126]
    o, h, l, c = _bars(closes, rng=0.5, opens=closes)
    sh, sl = ms.swings(h, l, n=2)
    assert sh[2] and sh[7] and sl[4] and sl[9]
    bos = ms.breaks_of_structure(c, sh, sl, h, l)
    assert bos and bos[0][1] == "bullish" and bos[0][0] == 6  # close 108 > swing high 106.5


def test_order_block_detected_and_mitigated():
    # flat, one bearish candle, then a displacement up that breaks the prior swing high, then a return into the zone
    closes = [100] * 20 + [101, 103, 101, 99, 100, 101, 99, 98] + [97] + [103, 109, 115, 121, 127] + [128, 126, 118, 110, 100, 99, 104, 110]
    o, h, l, c = _bars(closes, rng=0.5)
    a = ms.atr(h, l, c, n=5)
    sh, sl = ms.swings(h, l, n=2)
    bos = ms.breaks_of_structure(c, sh, sl, h, l)
    obs = ms.order_blocks(o, h, l, c, a, bos, disp_atr=1.5, disp_bars=6)
    bull = [z for z in obs if z.side == "bullish"]
    assert bull, "a bullish order block should form on the last bearish candle before the push"
    z = bull[0]
    assert z.low <= 97 <= z.high and z.state == "mitigated"  # price came back down through the zone later


def test_equal_lows_become_liquidity_and_get_swept():
    closes = [110, 105, 100, 105, 110, 105, 100.2, 105, 110, 107, 104, 99, 103, 108, 112]
    o, h, l, c = _bars(closes, rng=0.5, opens=closes)
    a = np.full(c.size, 2.0)
    sh, sl = ms.swings(h, l, n=2)
    liq = ms.liquidity_levels(h, l, sh, sl, a, c, eq_tol=0.25, sweep_bars=3)
    lows = [z for z in liq if z.side == "support"]
    assert lows and lows[0].touches == 2 and lows[0].state == "swept"


def test_strength_and_analyse_shape():
    closes = list(np.linspace(100, 140, 60))
    o, h, l, c = _bars(closes, rng=0.5)
    out = ms.analyse(o, h, l, c, swing_n=2)
    assert set(out) >= {"last", "atr", "strength", "bos", "order_blocks", "liquidity", "sr", "nearest"}
    assert out["strength"]["label"] in ("bullish", "bearish", "choppy")


def test_five_minute_aggregation():
    rows = [[k * 60_000_000_000, 10 + k, 11 + k, 9 + k, 10.5 + k, 1] for k in range(10)]
    o, h, l, c = ms.five_minute_bars(rows)
    assert o.tolist() == [10, 15] and h.tolist() == [15, 20] and l.tolist() == [9, 14] and c.tolist() == [14.5, 19.5]
