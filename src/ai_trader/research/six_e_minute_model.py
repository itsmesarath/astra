"""6E minute-level training set and walk-forward baselines on 2025 data (roadmap §8, steps 2-4).

One decision row per minute (06:00-17:00 UTC). The features are causal: they use only
bars that closed at or before the decision. They are computable from NinjaTrader live data:
- returns, range and realized variation from last-trade prices;
- volume;
- buy/sell volume imbalance (Databento's aggressor flag here; a bid/ask rule on live data);
- time of day.

Labels are forward 15/30/60-minute price changes in ticks. The walk-forward refits on all
earlier calendar months and tests the next month once. Trades are non-overlapping and pay a
fixed round-trip cost. Only 2025 bar files are accepted; reserved 2026 data is refused.
Research tier T1: nothing here places orders.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

TICK = 50_000
MINUTE_NS = 60_000_000_000
RESERVED_FROM = date(2026, 7, 1)  # Jul-Sep 2026 lockbox stays sealed
HORIZONS = (15, 30, 60)
DECISION_HOURS = (6, 17)  # [start, end) UTC
FEATURES = (
    "r1", "r5", "r15", "r30", "r60", "r240",
    "rv15", "rv60", "range15", "range60",
    "logvol1", "logvol15", "logvol60",
    "imb5", "imb15", "imb60", "dev60",
    "hour_sin", "hour_cos",
)


def load_days(directory: Path) -> list[dict]:
    days = []
    for path in sorted(directory.glob("*.json")):
        day = json.loads(path.read_text())
        if date.fromisoformat(day["utc_date"]) >= RESERVED_FROM:
            raise ValueError("Reserved lockbox day found; refusing")
        days.append(day)
    return days


def _window_sum(values: np.ndarray, k: int) -> np.ndarray:
    """Sum of the last k values ending at each index (fewer at the start)."""
    c = np.concatenate([[0.0], np.cumsum(values)])
    idx = np.arange(1, len(values) + 1)
    return c[idx] - c[np.maximum(idx - k, 0)]


def _rolling(values: np.ndarray, k: int, fn) -> np.ndarray:
    out = np.full(len(values), np.nan)
    for i in range(len(values)):
        window = values[max(0, i - k + 1) : i + 1]
        window = window[np.isfinite(window)]
        if window.size:
            out[i] = fn(window)
    return out


def day_rows(day: dict) -> dict[str, np.ndarray]:
    """Return per-minute feature/label arrays for one UTC day (1440 minutes)."""
    start = int(datetime.fromisoformat(day["utc_date"]).replace(tzinfo=timezone.utc).timestamp()) * 10**9
    n = 1440
    close = np.full(n, np.nan)
    high = np.full(n, np.nan)
    low = np.full(n, np.nan)
    vol = np.zeros(n)
    buy = np.zeros(n)
    sell = np.zeros(n)
    traded = np.zeros(n, dtype=bool)
    for minute, _o, h, l, c, v, _t, b, s in day["bars"]:
        i = (minute - start) // MINUTE_NS
        if not 0 <= i < n:
            raise ValueError("Bar outside its day")
        close[i], high[i], low[i] = c / TICK, h / TICK, l / TICK
        vol[i], buy[i], sell[i], traded[i] = v, b, s, True
    # Carry the last traded close forward (past information only).
    filled = close.copy()
    for i in range(1, n):
        if not np.isfinite(filled[i]):
            filled[i] = filled[i - 1]
    out: dict[str, np.ndarray] = {}
    for k in (1, 5, 15, 30, 60, 240):
        lagged = np.full(n, np.nan)
        lagged[k:] = filled[:-k]
        out[f"r{k}"] = filled - lagged
    step = np.abs(np.diff(filled, prepend=np.nan))
    step[~np.isfinite(step)] = 0.0
    for k in (15, 60):
        out[f"rv{k}"] = _window_sum(step, k)
        hi = np.where(traded, high, filled)
        lo = np.where(traded, low, filled)
        out[f"range{k}"] = _rolling(hi, k, np.max) - _rolling(lo, k, np.min)
    for k in (1, 15, 60):
        out[f"logvol{k}"] = np.log1p(_window_sum(vol, k))
    for k in (5, 15, 60):
        b, s = _window_sum(buy, k), _window_sum(sell, k)
        total = b + s
        out[f"imb{k}"] = np.divide(b - s, total, out=np.zeros(n), where=total > 0)
    out["dev60"] = filled - _rolling(filled, 60, np.mean)
    minute_of_day = np.arange(n)
    angle = 2 * math.pi * minute_of_day / 1440
    out["hour_sin"], out["hour_cos"] = np.sin(angle), np.cos(angle)
    for h in HORIZONS:
        future = np.full(n, np.nan)
        future[:-h] = filled[h:]
        out[f"fwd{h}"] = future - filled
    hour = minute_of_day // 60
    usable = traded & (hour >= DECISION_HOURS[0]) & (hour < DECISION_HOURS[1])
    for name in FEATURES + tuple(f"fwd{h}" for h in HORIZONS):
        usable &= np.isfinite(out[name])
    out["usable"] = usable
    out["minute"] = minute_of_day
    return out


def build_dataset(days: list[dict]) -> dict[str, np.ndarray]:
    parts: dict[str, list] = {name: [] for name in FEATURES + tuple(f"fwd{h}" for h in HORIZONS)}
    parts["month"], parts["day"], parts["minute"] = [], [], []
    for d, day in enumerate(days):
        rows = day_rows(day)
        mask = rows["usable"]
        for name in parts:
            if name == "month":
                parts[name].append(np.full(mask.sum(), int(day["utc_date"][:4]) * 100 + int(day["utc_date"][5:7])))
            elif name == "day":
                parts[name].append(np.full(mask.sum(), d))
            else:
                parts[name].append(rows[name][mask])
    return {name: np.concatenate(values) for name, values in parts.items()}


def fit_ridge(x: np.ndarray, y: np.ndarray, alpha: float = 10.0):
    mean, std = x.mean(axis=0), x.std(axis=0)
    std[std == 0] = 1.0
    z = (x - mean) / std
    a = z.T @ z + alpha * np.eye(z.shape[1])
    w = np.linalg.solve(a, z.T @ (y - y.mean()))
    return mean, std, w, y.mean()


def predict_ridge(model, x: np.ndarray) -> np.ndarray:
    mean, std, w, b = model
    return ((x - mean) / std) @ w + b


def simulate(signal: np.ndarray, fwd: np.ndarray, day: np.ndarray, minute: np.ndarray,
             horizon: int, cost: float) -> dict:
    """Non-overlapping trades: enter on nonzero signal when flat, exit after `horizon` minutes."""
    pnl = []
    busy_until = (-1, -1)
    for i in np.argsort(day * 10_000 + minute, kind="stable"):
        if signal[i] == 0:
            continue
        if (day[i], minute[i]) < busy_until:
            continue
        pnl.append(np.sign(signal[i]) * fwd[i] - cost)
        busy_until = (day[i], minute[i] + horizon)
    pnl = np.asarray(pnl)
    return {
        "trades": int(pnl.size),
        "mean_net_ticks": round(float(pnl.mean()), 3) if pnl.size else None,
        "total_net_ticks": round(float(pnl.sum()), 1),
        "hit_rate": round(float((pnl > 0).mean()), 3) if pnl.size else None,
    }


def walk_forward(data: dict[str, np.ndarray], horizon: int, cost: float,
                 first_test_month: int = 202507) -> dict:
    x = np.column_stack([data[name] for name in FEATURES])
    y = data[f"fwd{horizon}"]
    month = data["month"]
    results = {"horizon_min": horizon, "cost_ticks": cost, "months": {}}
    pooled: dict[str, list] = {}
    for m in sorted(int(v) for v in np.unique(month) if v >= first_test_month):
        train, test = month < m, month == m
        if not test.any() or train.sum() < 1000:
            continue
        model = fit_ridge(x[train], y[train])
        pred_train = predict_ridge(model, x[train])
        pred = predict_ridge(model, x[test])
        threshold = float(np.quantile(np.abs(pred_train), 0.9))  # chosen on training only
        ic = float(np.corrcoef(pred, y[test])[0, 1]) if pred.std() > 0 else 0.0
        args = (y[test], data["day"][test], data["minute"][test], horizon, cost)
        r60, r15 = data["r60"][test], data["r15"][test]
        policies = {
            "ridge_top10pct": np.where(np.abs(pred) > threshold, np.sign(pred), 0),
            "ridge_beats_cost": np.where(np.abs(pred) > cost, np.sign(pred), 0),
            "momentum_r60": np.sign(r60),
            "reversal_r15": -np.sign(r15),
            "always_long": np.ones(test.sum()),
            "always_short": -np.ones(test.sum()),
        }
        row = {"rows": int(test.sum()), "ic": round(ic, 4), "threshold_ticks": round(threshold, 2)}
        for name, signal in policies.items():
            row[name] = simulate(signal, *args)
            pooled.setdefault(name, []).append(row[name])
        results["months"][str(m)] = row
    results["pooled"] = {
        name: {
            "trades": sum(r["trades"] for r in rows),
            "total_net_ticks": round(sum(r["total_net_ticks"] for r in rows), 1),
            "mean_net_ticks": round(
                sum(r["total_net_ticks"] for r in rows) / max(1, sum(r["trades"] for r in rows)), 3
            ),
            "negative_months": sum(1 for r in rows if r["total_net_ticks"] < 0),
            "months": len(rows),
        }
        for name, rows in pooled.items()
    }
    return results


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bars", type=Path, default=Path("data/processed/6e_minute_bars_dev_1"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/6e_minute_model_dev_1.json"))
    parser.add_argument("--cost", type=float, nargs="+", default=[2.0, 3.0])
    args = parser.parse_args(argv)
    days = load_days(args.bars)
    data = build_dataset(days)
    report = {"days": len(days), "rows": int(data["r1"].size), "features": list(FEATURES), "runs": []}
    for horizon in HORIZONS:
        for cost in args.cost:
            report["runs"].append(walk_forward(data, horizon, cost))
    args.output.write_text(json.dumps(report, indent=1))
    for run in report["runs"]:
        line = ", ".join(
            f"{k}={v['mean_net_ticks']:+.2f}x{v['trades']}({v['negative_months']}/{v['months']} neg)"
            for k, v in run["pooled"].items()
        )
        print(f"h={run['horizon_min']} cost={run['cost_ticks']}: {line}")


if __name__ == "__main__":
    main()
