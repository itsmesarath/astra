"""Footprint ("cluster") diagnostic for the thick-book reversal candidate on 6E.

For every historical candidate trade (the shadow rule replayed on the development store) we look
at the bid/ask volume per price around the failed breakout, from the per-minute ``tpx`` map in the
book-minute store (volume by price split into buyer- and seller-initiated), and ask whether what
footprint traders call *absorption* at the extreme separates winners from losers:

- ``sell_at_low``: seller-initiated volume at the lowest two price levels of the 15-minute stop-run
  window (for shorts: buyer-initiated volume at the highest two levels) — aggressive volume that
  failed to move price further.
- ``low_sell_share``: that volume as a share of all volume at those levels.
- ``window_delta``: buy minus sell volume over the window, signed in the trade direction
  (negative = the market was being hit against the eventual trade direction).
- ``entry_delta``: same for the entry minute alone (the snap-back minute).
- ``imbalance_levels``: number of price levels in the window where one side is at least 3x the
  other (stacked imbalances).
- ``volume_window`` / ``volume_ratio``: window volume and its ratio to the trailing 60-minute mean.

The same features are computed for random entries with the same filters (control). With ~45
candidate trades the output is descriptive: feature means for winners vs losers, a rank AUC per
feature, and the same for the control. It cannot tune the rule; it says whether a footprint
confirmation deserves to be logged from day one in the live loop.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ai_trader.live import shadow_signals as ss
from ai_trader.research import six_e_session_pa_study as ps
from ai_trader.research.six_e_hindsight_study import auc

WINDOW = 15
FEATURES = ("sell_at_low", "low_sell_share", "window_delta", "entry_delta", "imbalance_levels",
            "volume_window", "volume_ratio")


def tpx_window(book, m0: int, m1: int) -> dict[int, list[int]]:
    acc: dict[int, list[int]] = {}
    for m in range(max(0, m0), min(1440, m1 + 1)):
        t = book["tpx"][m]
        if not t:
            continue
        for p, (b, s) in t.items():
            slot = acc.setdefault(int(p), [0, 0])
            slot[0] += b
            slot[1] += s
    return acc


def features(book, i_day: int, d: int, bars_vol: np.ndarray) -> dict | None:
    """Footprint features for a trade entered at minute-of-day i_day in direction d (+1 long)."""
    win = tpx_window(book, i_day - WINDOW, i_day - 1)
    entry = tpx_window(book, i_day, i_day)
    if not win:
        return None
    prices = sorted(win)
    extreme = prices[:2] if d > 0 else prices[-2:]
    against = 1 if d > 0 else 0  # for longs the aggressive side at the low is the seller (index 1)
    vol_ext = sum(win[p][0] + win[p][1] for p in extreme)
    hit_ext = sum(win[p][against] for p in extreme)
    buy = sum(v[0] for v in win.values())
    sell = sum(v[1] for v in win.values())
    e_buy = sum(v[0] for v in entry.values())
    e_sell = sum(v[1] for v in entry.values())
    imb = sum(1 for b, s in win.values() if (b >= 3 * s and b >= 5) or (s >= 3 * b and s >= 5))
    trailing = bars_vol[max(0, i_day - 75):max(1, i_day - WINDOW)]
    trail_mean = float(trailing.mean()) if trailing.size else float("nan")
    return {
        "sell_at_low": hit_ext,
        "low_sell_share": hit_ext / vol_ext if vol_ext else float("nan"),
        "window_delta": d * (buy - sell),
        "entry_delta": d * (e_buy - e_sell),
        "imbalance_levels": imb,
        "volume_window": buy + sell,
        "volume_ratio": (buy + sell) / (WINDOW * trail_mean) if trail_mean else float("nan"),
    }


def trades_with_features(m: dict, days_list, rule_sig_kind: str, rng) -> list[dict]:
    """Replay the rule (or random entries with the same filters) and attach footprint features."""
    c, h, l = m["close"], m["high"], m["low"]
    n = c.size
    ps._ADJ = np.zeros(n)
    ps._MONTHS = np.array([d.year * 100 + d.month for d in m["dates"]])
    mod = ps.minute_of_day(n)
    dayk = np.repeat(np.arange(len(m["dates"])), 1440)
    a = ps.atr_minutes(h, l, c)
    trend4 = np.sign(c - np.concatenate([np.full(240, np.nan), c[:-240]]))
    if rule_sig_kind == "reversal":
        sig = ps.pattern_signals(c, h, l, a, "reversal", lookback=ss.RULE["lookback"], bounce=ss.RULE["bounce"])
    else:
        sig = ps.pattern_signals(c, h, l, a, "random", rng)
    sig[sig != trend4] = 0
    ok = np.zeros(n, dtype=bool)
    for lo, hi in ss.RULE["window"]:
        ok |= (mod >= lo) & (mod < hi)
    sig[~ok] = 0
    sig[~np.isfinite(c)] = 0
    from numpy.lib.stride_tricks import sliding_window_view
    med = np.full(n, np.nan)
    med[60:] = np.nanmedian(sliding_window_view(m["depth"], 60)[:-1], axis=1)
    depth_ok = m["depth"] >= med
    trades = ps.simulate(c, h, l, a, mod, dayk, m["books"], sig, "market", ss.RULE["stop_k"], ss.RULE["rr"],
                         ss.RULE["hold"], False, depth_ok, cost=ss.RULE["cost"])
    out = []
    for t in trades:
        k = int(dayk[t["i"]])
        book = m["books"][k]
        if book is None:
            continue
        i_day = int(mod[t["i"]])
        vol = book["buy_vol"] + book["sell_vol"]
        f = features(book, i_day, t["d"], vol)
        if f is None:
            continue
        out.append({"date": m["dates"][k].isoformat(), "minute": i_day, "side": t["d"], "net": t["net"],
                    "win": t["net"] > 0, **f})
    return out


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {}
    win = np.array([r["win"] for r in rows])
    net = np.array([r["net"] for r in rows])
    out = {"trades": len(rows), "win_rate": round(float(win.mean()), 3), "mean_net": round(float(net.mean()), 2), "features": {}}
    for f in FEATURES:
        x = np.array([r[f] for r in rows], dtype=float)
        good = np.isfinite(x)
        if good.sum() < 10 or win[good].all() or (~win[good]).all():
            continue
        out["features"][f] = {
            "winners_mean": round(float(x[good & win].mean()), 3),
            "losers_mean": round(float(x[good & ~win].mean()), 3),
            "auc_win": round(float(auc(x[good], win[good])), 3),
            "corr_net": round(float(np.corrcoef(x[good], net[good])[0, 1]), 3),
        }
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bars", type=Path, default=Path("data/processed/6e_minute_bars_dev_1"))
    p.add_argument("--book", type=Path, default=Path("data/processed/6e_book_minutes_dev_1"))
    p.add_argument("--output", type=Path, default=Path("data/processed/6e_footprint_diagnostic_1.json"))
    a = p.parse_args(argv)
    days: dict = {}
    ss.load_store(a.bars, a.book, days)
    m = ss.arrays(days)
    rng = np.random.default_rng(5)
    result = {"candidate": summarize(trades_with_features(m, days, "reversal", rng)),
              "random_control": summarize(trades_with_features(m, days, "random", rng))}
    a.output.write_text(json.dumps(result, indent=1))
    for name, s in result.items():
        print(f"\n{name}: {s.get('trades')} trades, win rate {s.get('win_rate')}, mean net {s.get('mean_net')}")
        for f, v in s.get("features", {}).items():
            print(f"  {f:17s} winners {v['winners_mean']:>9} losers {v['losers_mean']:>9}  AUC {v['auc_win']:.3f}  corr(net) {v['corr_net']:+.3f}")


if __name__ == "__main__":
    main()
