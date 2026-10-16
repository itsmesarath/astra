"""Synthetic checks: causality of features, label alignment, non-overlapping simulation."""

import json
from copy import deepcopy

import numpy as np
import pytest

from ai_trader.research import six_e_minute_model as model

DAY0 = 1_745_366_400 * 10**9  # 2025-04-23 00:00 UTC
M = model.MINUTE_NS
T = model.TICK


def synthetic_day(seed=0):
    rng = np.random.default_rng(seed)
    price = 1_100_000_000
    bars = []
    for i in range(1440):
        if i % 7 == 3:
            continue  # some minutes without trades
        price += int(rng.integers(-2, 3)) * T
        buy, sell = int(rng.integers(0, 20)), int(rng.integers(0, 20))
        bars.append([DAY0 + i * M, price, price + T, price - T, price, buy + sell + 1, 3, buy, sell])
    return {"utc_date": "2025-04-23", "bars": bars}


def test_features_never_use_future_bars_but_labels_do():
    day = synthetic_day()
    base = model.day_rows(day)
    changed = deepcopy(day)
    cut = 9 * 60  # change every bar after 09:00
    for bar in changed["bars"]:
        if bar[0] >= DAY0 + cut * M:
            bar[4] += 40 * T
            bar[2] += 40 * T
            bar[3] += 40 * T
            bar[7] += 50
    after = model.day_rows(changed)
    for name in model.FEATURES:
        a, b = base[name][: cut], after[name][: cut]
        assert np.allclose(a, b, equal_nan=True), name
    # The 15-minute label 10 minutes before the cut sees the changed future.
    assert not np.isclose(base["fwd15"][cut - 10], after["fwd15"][cut - 10])


def test_label_is_future_minus_current_close_in_ticks():
    day = synthetic_day(1)
    rows = model.day_rows(day)
    closes = {(b[0] - DAY0) // M: b[4] / T for b in day["bars"]}
    i = 8 * 60 + 1  # a traded minute
    assert i in closes
    later = max(k for k in closes if k <= i + 30)
    assert rows["fwd30"][i] == pytest.approx(closes[later] - closes[i])
    assert rows["r5"][i] == pytest.approx(closes[i] - closes[max(k for k in closes if k <= i - 5)])
    hours = rows["minute"][rows["usable"]] // 60
    assert hours.min() >= 6 and hours.max() < 17


def test_simulation_is_non_overlapping_and_pays_cost():
    signal = np.array([1, 1, -1, 0, 1])
    fwd = np.array([5.0, 9.0, -4.0, 0.0, 1.0])
    day = np.zeros(5, dtype=int)
    minute = np.array([0, 10, 15, 20, 31])
    result = model.simulate(signal, fwd, day, minute, horizon=15, cost=2.0)
    # Trades at minute 0 (+5-2) and 15 (+4-2) and 31 (1-2); minute 10 is skipped while busy.
    assert result["trades"] == 3
    assert result["total_net_ticks"] == pytest.approx(3 + 2 - 1)


def test_reserved_days_refused(tmp_path):
    (tmp_path / "2026-02-02.json").write_text(json.dumps({"utc_date": "2026-02-02", "bars": []}))
    with pytest.raises(ValueError, match="Reserved"):
        model.load_days(tmp_path)


def test_walk_forward_runs_and_tests_only_later_months():
    days = []
    for month, dom in ((4, 23), (5, 14), (6, 11), (7, 9)):
        d = synthetic_day(month)
        start = int(np.datetime64(f"2025-{month:02d}-{dom:02d}", "s").astype(int)) * 10**9
        d["utc_date"] = f"2025-{month:02d}-{dom:02d}"
        for bar in d["bars"]:
            bar[0] = bar[0] - DAY0 + start
        days.append(d)
    data = model.build_dataset(days)
    result = model.walk_forward(data, horizon=15, cost=2.0, first_test_month=6)
    assert set(result["months"]) == {"6", "7"}
    assert result["pooled"]["always_long"]["months"] == 2
