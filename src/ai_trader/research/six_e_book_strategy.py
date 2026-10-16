"""Order-book strategy study for 6E: book features + passive (limit) entries, walk-forward.

Inputs: ``6e_book_minutes_dev_1`` (book features per minute) and ``6e_minute_bars_dev_1``
(price features and forward labels from ``six_e_minute_model``). Lockbox Jul-Sep 2026 is
never read.

Book features at the decision minute (all causal):
- l1_imb: (bid_sz - ask_sz) / (bid_sz + ask_sz) at the best quotes
- d5_imb: same over 5 levels of depth
- micro: microprice minus mid, in ticks (where the size-weighted quote sits)
- ofi_1, ofi_5, ofi_15: order-flow imbalance summed over 1, 5 and 15 minutes, scaled by
  the 60-minute average depth
- cxl_imb_5: (cancels on ask side - cancels on bid side) over 5 minutes, scaled
- spread: ask - bid in ticks
- big_imb_15: (buy big trades - sell big trades) over 15 minutes
- plus the 19 price/volume features from six_e_minute_model

Walk-forward: monthly refit on all earlier months; ridge for the forward return and a
logistic "+20 before -10 within 60 min" opportunity model, as before. Policies:
- market entry with 2.6 ticks cost (as before), and
- passive entry: a limit at the best bid (long) or best ask (short) at the decision close.
  The queue ahead is the resting size at that level. The order fills in a later minute
  when sell-aggressor (for a bid) volume at that price since placement exceeds the queue,
  or when the best ask trades at or below the limit (traded through). Cancellations ahead
  of us are ignored (conservative). Unfilled after 15 minutes: no trade. Filled trades
  pay 1.6 ticks (fees 0.6 + 1 tick exit slippage; no spread paid on entry) and use the
  same +20/-10 bracket from the fill price with a 60-minute time exit.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ai_trader.research import six_e_minute_model as mm
from ai_trader.research.six_e_hindsight_study import DOWN, UP, WINDOW, opportunities
from ai_trader.research.six_e_opportunity_model import fit_logistic

BOOK_FEATURES = ("l1_imb", "d5_imb", "micro", "ofi_1", "ofi_5", "ofi_15", "cxl_imb_5",
                 "spread", "big_imb_15")
LIMIT_WAIT = 15


def book_arrays(day_book: dict) -> dict:
    n = 1440
    cols = {k: np.full(n, np.nan) for k in ("bid", "ask", "bid_sz", "ask_sz", "bid_d5", "ask_d5",
                                              "min_ask", "max_bid")}
    flows = {k: np.zeros(n) for k in ("ofi", "cxl_b", "cxl_a", "big_buy", "big_sell", "buy_vol", "sell_vol")}
    tpx = [None] * n
    for ms, row in day_book["minutes"].items():
        i = int(ms)
        for k in cols:
            v = row.get(k)
            cols[k][i] = np.nan if v is None else v
        flows["ofi"][i] = row["ofi"]; flows["cxl_b"][i] = row["cxl_b"]; flows["cxl_a"][i] = row["cxl_a"]
        flows["buy_vol"][i] = row["buy_vol"]; flows["sell_vol"][i] = row["sell_vol"]
        # big trades are not split by side in the decoder; use aggressor volume sign as proxy
        flows["big_buy"][i] = row["big_trades"] if row["buy_vol"] >= row["sell_vol"] else 0
        flows["big_sell"][i] = row["big_trades"] if row["sell_vol"] > row["buy_vol"] else 0
        tpx[i] = {int(p): v for p, v in row["tpx"].items()}
    # carry last quotes forward for minutes without events
    for k in ("bid", "ask", "bid_sz", "ask_sz", "bid_d5", "ask_d5"):
        a = cols[k]
        for i in range(1, n):
            if np.isnan(a[i]):
                a[i] = a[i - 1]
    return {**cols, **flows, "tpx": tpx}


def book_features(b: dict) -> dict[str, np.ndarray]:
    n = 1440
    bs, as_, bd, ad = b["bid_sz"], b["ask_sz"], b["bid_d5"], b["ask_d5"]
    out = {}
    out["l1_imb"] = np.divide(bs - as_, bs + as_, out=np.zeros(n), where=(bs + as_) > 0)
    out["d5_imb"] = np.divide(bd - ad, bd + ad, out=np.zeros(n), where=(bd + ad) > 0)
    mid = (b["bid"] + b["ask"]) / 2
    micro = np.divide(b["ask"] * bs + b["bid"] * as_, bs + as_, out=np.full(n, np.nan), where=(bs + as_) > 0)
    out["micro"] = micro - mid
    out["spread"] = b["ask"] - b["bid"]
    depth = mm._window_sum(np.nan_to_num(bd + ad), 60) / 60
    depth[depth <= 0] = np.nan
    for k in (1, 5, 15):
        out[f"ofi_{k}"] = mm._window_sum(b["ofi"], k) / depth
    out["cxl_imb_5"] = (mm._window_sum(b["cxl_a"], 5) - mm._window_sum(b["cxl_b"], 5)) / depth
    out["big_imb_15"] = mm._window_sum(b["big_buy"], 15) - mm._window_sum(b["big_sell"], 15)
    return out


def passive_fill(b: dict, i: int, d: int):
    """Return (fill_minute, fill_price_ticks) for a limit placed at the close of minute i, or None."""
    if d > 0:
        price, queue = b["bid"][i], b["bid_sz"][i]
    else:
        price, queue = b["ask"][i], b["ask_sz"][i]
    if not np.isfinite(price) or not np.isfinite(queue):
        return None
    price = int(price)
    done = 0.0
    for j in range(i + 1, min(i + 1 + LIMIT_WAIT, 1440)):
        t = b["tpx"][j]
        if d > 0:
            if np.isfinite(b["min_ask"][j]) and b["min_ask"][j] <= price:
                return j, price
            done += t.get(price, (0, 0))[1] if t else 0
        else:
            if np.isfinite(b["max_bid"][j]) and b["max_bid"][j] >= price:
                return j, price
            done += t.get(price, (0, 0))[0] if t else 0
        if done >= queue + 1:
            return j, price
    return None


def bracket_from(hi, lo, cl, j, d, entry, cost, horizon):
    for k in range(j + 1, min(j + 1 + horizon, 1440)):
        if not np.isfinite(hi[k]):
            continue
        if d > 0:
            if lo[k] <= entry - DOWN: return -DOWN - cost, k
            if hi[k] >= entry + UP: return UP - cost, k
        else:
            if hi[k] >= entry + DOWN: return -DOWN - cost, k
            if lo[k] <= entry - UP: return UP - cost, k
    last = min(j + horizon, 1439)
    while last > j and not np.isfinite(cl[last]):
        last -= 1
    return d * (cl[last] - entry) - cost, last


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=Path, default=Path("data/processed/6e_minute_bars_dev_1"))
    parser.add_argument("--book", type=Path, default=Path("data/processed/6e_book_minutes_dev_1"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/6e_book_strategy_dev_1.json"))
    args = parser.parse_args(argv)
    days = mm.load_days(args.bars)
    X, Y, MO, DAY, MIN, FWD = [], [], [], [], [], {15: [], 30: [], 60: []}
    books, paths = [], []
    for d_i, day in enumerate(days):
        bp = args.book / f"{day['utc_date']}.json"
        if not bp.exists():
            continue
        rows, label = opportunities(day)
        b = book_arrays(json.loads(bp.read_text()))
        bf = book_features(b)
        u = rows["usable"].copy()
        for name in BOOK_FEATURES:
            u &= np.isfinite(bf[name])
        X.append(np.column_stack([rows[f][u] for f in mm.FEATURES] + [bf[f][u] for f in BOOK_FEATURES]))
        Y.append(label[u]); MO.append(np.full(u.sum(), int(day["utc_date"][:4]) * 100 + int(day["utc_date"][5:7])))
        DAY.append(np.full(u.sum(), len(books))); MIN.append(np.flatnonzero(u))
        for h in FWD: FWD[h].append(rows[f"fwd{h}"][u])
        books.append(b)
        start = int(np.datetime64(day["utc_date"], "s").astype(np.int64)) * 10**9
        hi = np.full(1440, np.nan); lo = np.full(1440, np.nan); cl = np.full(1440, np.nan)
        for minute, _o, h_, l_, c_, *_ in day["bars"]:
            k = (minute - start) // mm.MINUTE_NS
            hi[k], lo[k], cl[k] = h_ / mm.TICK, l_ / mm.TICK, c_ / mm.TICK
        paths.append((hi, lo, cl))
    x, y, mo, dd, mi = np.vstack(X), np.concatenate(Y), np.concatenate(MO), np.concatenate(DAY), np.concatenate(MIN)
    fwd = {h: np.concatenate(v) for h, v in FWD.items()}
    names = list(mm.FEATURES) + list(BOOK_FEATURES)
    print(f"{len(books)} days with book data; {len(y)} decision rows")

    # 1. Does the book add information? Per-feature AUC for the opportunity label, 2025 -> 2026.
    from ai_trader.research.six_e_hindsight_study import auc
    tr, te = mo <= 202512, mo >= 202601
    print("\nBook features: AUC for long winners (2025 / 2026) and short winners (2025 / 2026)")
    for k, nm in enumerate(names):
        if nm in BOOK_FEATURES:
            print(f"  {nm:12s} long {auc(x[tr, k], y[tr] == 1):.3f}/{auc(x[te, k], y[te] == 1):.3f}   "
                  f"short {auc(x[tr, k], y[tr] == -1):.3f}/{auc(x[te, k], y[te] == -1):.3f}")

    # 2. Walk-forward: ridge IC with and without book features, 15/30/60 min.
    print("\nWalk-forward ridge IC (prediction vs forward return), monthly refit:")
    bookcols = [names.index(n) for n in BOOK_FEATURES]
    pricecols = [k for k in range(len(names)) if k not in bookcols]
    months = sorted(v for v in np.unique(mo) if v >= 202507)
    for h in (15, 30, 60):
        for label_, cols in (("price only", pricecols), ("price + book", list(range(len(names))))):
            ics = []
            for m in months:
                train, test = mo < m, mo == m
                model = mm.fit_ridge(x[train][:, cols], fwd[h][train])
                p = mm.predict_ridge(model, x[test][:, cols])
                ics.append(np.corrcoef(p, fwd[h][test])[0, 1])
            ics = np.array(ics)
            print(f"  h={h:2d} {label_:13s} mean IC {ics.mean():+.4f}  positive months {int((ics > 0).sum())}/{len(ics)}")

    # 3. Opportunity model with book features, market vs passive entry.
    print("\nOpportunity model (top 5% picks), bracket +20/-10, 60 min:")
    results = {}
    for entry in ("market", "passive"):
        pnl, yrs, fills, attempts = [], [], 0, 0
        for m in months:
            train, test = mo < m, mo == m
            mean, std = x[train].mean(0), x[train].std(0); std[std == 0] = 1
            zt, ze = (x[train] - mean) / std, (x[test] - mean) / std
            sig = np.zeros(test.sum())
            for side in (1, -1):
                w, b = fit_logistic(zt, (y[train] == side).astype(float))
                pick = (ze @ w + b) > np.quantile(zt @ w + b, 0.95)
                sig = np.where(pick & (sig == 0), side, np.where(pick & (sig != 0), 0, sig))
            idx = np.flatnonzero(test)
            busy = (-1, -1)
            for o in np.lexsort((mi[idx], dd[idx])):
                k = idx[o]; s = int(sig[o])
                if s == 0 or (dd[k], mi[k]) < busy:
                    continue
                hi, lo, cl = paths[dd[k]]
                if entry == "market":
                    v, ex = bracket_from(hi, lo, cl, mi[k], s, cl[mi[k]], 2.6, WINDOW)
                else:
                    attempts += 1
                    f = passive_fill(books[dd[k]], mi[k], s)
                    if f is None:
                        continue
                    fills += 1
                    j, px = f
                    v, ex = bracket_from(hi, lo, cl, j, s, px, 1.6, WINDOW)
                pnl.append(v); yrs.append(m // 100); busy = (dd[k], ex)
        p, yr = np.array(pnl), np.array(yrs)
        results[entry] = {"trades": int(p.size), "mean_net": round(float(p.mean()), 2),
                          "mean_2025": round(float(p[yr == 2025].mean()), 2), "mean_2026": round(float(p[yr == 2026].mean()), 2),
                          "win_rate": round(float((p > 0).mean()), 3),
                          "fill_rate": round(fills / attempts, 3) if attempts else None}
        print(f"  {entry:8s} {results[entry]}")
    args.output.write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
