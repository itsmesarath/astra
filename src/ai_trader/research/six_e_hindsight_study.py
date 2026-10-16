"""Hindsight-first study: find the profitable 6E trades of 2025, then ask what preceded them.

Step 1 (hindsight, uses the future on purpose). For every decision minute (06:00-17:00
UTC), check the next 60 minutes:
- **long opportunity:** price rises +20 ticks above entry before falling -10 ticks below it
  (a 2:1 reward-to-risk trade);
- **short opportunity:** the mirror image;
- **neither:** everything else.
The path is checked on minute high/low. If both thresholds are touched in the same minute,
the outcome is not counted as an opportunity.

Step 2 (reverse-engineering, uses only the past). Compare the 19 causal features at those
minutes with all other minutes:
- the per-feature AUC on 2025 (Mar-Dec);
- whether the same direction holds on Jan-Jun 2026;
- a logistic model fitted on 2025 and scored on Jan-Jun 2026.
An AUC of 0.5 means the feature carries no information about the opportunity.
Only data before the Jul-Sep 2026 lockbox is used.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ai_trader.research import six_e_minute_model as mm

UP, DOWN, WINDOW = 20, 10, 60


def opportunities(day: dict) -> np.ndarray:
    rows = mm.day_rows(day)
    start = int(np.datetime64(day["utc_date"], "s").astype(np.int64)) * 10**9
    hi = np.full(1440, np.nan); lo = np.full(1440, np.nan); cl = np.full(1440, np.nan)
    for minute, _o, h, l, c, *_ in day["bars"]:
        i = (minute - start) // mm.MINUTE_NS
        hi[i], lo[i], cl[i] = h / mm.TICK, l / mm.TICK, c / mm.TICK
    label = np.zeros(1440)
    for i in np.flatnonzero(rows["usable"]):
        entry = cl[i]
        long_res = short_res = 0
        for j in range(i + 1, min(i + 1 + WINDOW, 1440)):
            if not np.isfinite(hi[j]):
                continue
            if long_res == 0:
                up, dn = hi[j] >= entry + UP, lo[j] <= entry - DOWN
                long_res = -1 if dn else (1 if up else 0)
            if short_res == 0:
                up, dn = lo[j] <= entry - UP, hi[j] >= entry + DOWN
                short_res = -1 if dn else (1 if up else 0)
            if long_res and short_res:
                break
        label[i] = 1 if long_res == 1 else (-1 if short_res == 1 else 0)
    return rows, label


def auc(score: np.ndarray, positive: np.ndarray) -> float:
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty(len(score)); ranks[order] = np.arange(1, len(score) + 1)
    n1 = positive.sum(); n0 = len(positive) - n1
    return float((ranks[positive].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main() -> None:
    days = mm.load_days(Path("data/processed/6e_minute_bars_dev_1"))
    feats, labels, months = [], [], []
    for day in days:
        rows, label = opportunities(day)
        u = rows["usable"]
        feats.append(np.column_stack([rows[f][u] for f in mm.FEATURES]))
        labels.append(label[u]); months.append(np.full(u.sum(), int(day["utc_date"][:4]) * 100 + int(day["utc_date"][5:7])))
    x, y, mo = np.vstack(feats), np.concatenate(labels), np.concatenate(months)
    train, test = mo <= 202512, mo >= 202601
    report = {"rows": int(len(y)), "long_opportunity_share": round(float((y == 1).mean()), 4),
              "short_opportunity_share": round(float((y == -1).mean()), 4), "features": {}}
    print(f"decision minutes {len(y)}; long opportunities {int((y==1).sum())} ({(y==1).mean():.1%}), "
          f"short {int((y==-1).sum())} ({(y==-1).mean():.1%})")
    for side, val in (("long", 1), ("short", -1)):
        rows = []
        for k, name in enumerate(mm.FEATURES):
            a_tr = auc(x[train, k], y[train] == val); a_te = auc(x[test, k], y[test] == val)
            rows.append((abs(a_tr - 0.5), name, round(a_tr, 3), round(a_te, 3)))
        rows.sort(reverse=True)
        report["features"][side] = [{"feature": n, "auc_2025": a, "auc_h1_2026": b} for _, n, a, b in rows]
        print(side, "top features (AUC 2025 -> H1 2026):", [(n, a, b) for _, n, a, b in rows[:6]])
        # Logistic model on all features, fit 2025, score H1 2026.
        mean, std = x[train].mean(0), x[train].std(0); std[std == 0] = 1
        z_tr, z_te = (x[train] - mean) / std, (x[test] - mean) / std
        t = (y[train] == val).astype(float); w = np.zeros(z_tr.shape[1]); b = np.log(t.mean() / (1 - t.mean()))
        for _ in range(300):
            p = 1 / (1 + np.exp(-(z_tr @ w + b)))
            g = z_tr.T @ (p - t) / len(t) + 1e-3 * w
            w -= 0.5 * g; b -= 0.5 * (p - t).mean()
        s_te = z_te @ w + b
        a_model = auc(s_te, y[test] == val)
        top = np.argsort(-s_te)[: int(0.05 * len(s_te))]
        hit = float((y[test][top] == val).mean())
        base = float((y[test] == val).mean())
        report[f"{side}_model"] = {"auc_h1_2026": round(a_model, 3), "top5pct_hit": round(hit, 4), "base_rate": round(base, 4)}
        print(f"{side} logistic model H1-2026 AUC {a_model:.3f}; top-5% picks are real opportunities {hit:.1%} vs base {base:.1%}"
              f" (a 2:1 trade needs >33.3% plus costs)")
    Path("data/processed/6e_hindsight_study_dev_1.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
