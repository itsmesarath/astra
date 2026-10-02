"""Past-only publication, explicit missingness, bounded state and daily isolation."""

import math
from copy import deepcopy
from datetime import UTC, datetime

import numpy as np
import pytest

from ai_trader.training import causal_6e_context as c

DAY = "2025-04-07"
START = int(datetime.fromisoformat(DAY).replace(hour=12, tzinfo=UTC).timestamp()) * c.SECOND


def observation(offset=0, value=1.0):
    f = {key: 0.0 for key in c.data.census.study.data.FEATURES}
    f["normalized_cvd_5s"] = value
    f["queue_imbalance"] = value
    f["mid_change_5s_ticks"] = 2.0
    return {
        "source_session": DAY,
        "contract": c.data.census.dated_contract(DAY),
        "partition": "development",
        "decision_ts_ns": START + offset * c.SECOND,
        "features": f,
        "execution_features": {key: 0.0 for key in c.data.census.study.flow.FEATURES},
    }


def index(name):
    return c.FEATURES.index(name)


def test_original_features_exact_and_context_excludes_current_from_past_means():
    rows = [observation(i, float(i + 1)) for i in range(3)]
    matrix, report = c.transform(rows)
    np.testing.assert_array_equal(matrix[:, index("normalized_cvd_5s")], [1, 2, 3])
    np.testing.assert_array_equal(matrix[:, index("past_mean_normalized_cvd_5s_5s")], [0, 1, 1.5])
    np.testing.assert_array_equal(matrix[:, index("past_samples_30s")], [0, 1, 2])
    np.testing.assert_array_equal(
        matrix[:, index("current_minus_past_mean_normalized_cvd_5s_5s")], [1, 1, 1.5]
    )
    assert report["no_prior_30s_samples"] == 1
    assert matrix.shape == (3, 109)


def test_prefix_invariance_and_no_future_targets_paths_or_eligibility_access():
    rows = [observation(i, float(i)) for i in range(40)]
    original, _ = c.transform(rows)
    prefix, _ = c.transform(rows[:17])
    np.testing.assert_array_equal(original[:17], prefix)
    changed = deepcopy(rows)
    for row in changed:
        row.update(
            outcome={"status": "resolved"},
            net_targets_long_short_ticks=[999, -1000],
            path_horizons={"future": "poison"},
            hindsight_action=1,
            eligible=False,
        )
    for row in changed[17:]:
        row["features"]["normalized_cvd_5s"] = -10_000.0
    result, _ = c.transform(changed)
    np.testing.assert_array_equal(original[:17], result[:17])
    changed, _ = c.transform([dict(row, outcome=None, eligible="poison") for row in rows])
    np.testing.assert_array_equal(original, changed)


def test_inclusive_history_expiry_is_exact_without_carry_forward():
    state = c.CausalContext(DAY, observation()["contract"])
    state.observe(observation(0, 9.0))
    at_five = state.observe(observation(5, 1.0))
    assert at_five[index("past_mean_normalized_cvd_5s_5s")] == 9.0
    at_six = state.observe(observation(6, 3.0))
    assert at_six[index("past_mean_normalized_cvd_5s_5s")] == 1.0
    assert at_six[index("past_mean_normalized_cvd_5s_15s")] == 5.0


@pytest.mark.parametrize("cause", ["decision_gap", "quote_gap"])
def test_causal_gaps_clear_every_window(cause):
    state = c.CausalContext(DAY, observation()["contract"])
    state.observe(observation(0, 9.0))
    row = observation(6 if cause == "decision_gap" else 1, 1.0)
    if cause == "quote_gap":
        row["features"]["log_prior_quote_gap_ms"] = math.log1p(5001)
    result = state.observe(row)
    assert all(result[index(f"past_samples_{w}s")] == 0 for w in c.WINDOWS)
    assert state.resets == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_session", "2025-04-08"),
        ("contract", "6EU5"),
        ("partition", "test_reserved"),
        ("decision_ts_ns", START - c.SECOND),
        ("decision_ts_ns", float(START)),
    ],
)
def test_cross_session_contract_window_and_clock_refusals(field, value):
    row = observation()
    row[field] = value
    state = c.CausalContext(DAY, observation()["contract"])
    with pytest.raises(ValueError):
        state.observe(row)


def test_reserved_context_refuses_before_touching_any_features():
    with pytest.raises(ValueError, match="Reserved"):
        c.CausalContext("2026-01-01", "unused")


@pytest.mark.parametrize("offset", [0, -1, 0.5])
def test_duplicate_regressed_or_too_dense_decisions_refused(offset):
    state = c.CausalContext(DAY, observation()["contract"])
    state.observe(observation(10))
    row = observation(10)
    row["decision_ts_ns"] += int(offset * c.SECOND)
    with pytest.raises(ValueError, match="sampling interval"):
        state.observe(row)


@pytest.mark.parametrize("value", [True, float("nan"), float("inf")])
def test_nonfinite_or_boolean_features_refused(value):
    row = observation(value=value)
    with pytest.raises(ValueError, match="allowlist"):
        c.transform([row])


def test_future_feature_columns_and_negative_execution_proxies_refused():
    row = observation()
    row["features"]["hindsight_action"] = 1
    with pytest.raises(ValueError, match="allowlist"):
        c.transform([row])
    row = observation()
    row["execution_features"]["bid_passive_5s"] = -1
    with pytest.raises(ValueError, match="allowlist"):
        c.transform([row])


def test_context_is_bounded_and_stores_no_outcome_payload(monkeypatch):
    state = c.CausalContext(DAY, observation()["contract"])
    for i in range(120):
        row = observation(i)
        row["path_horizons"] = {"future": object()}
        state.observe(row)
    assert len(state.history[30]) == 31
    assert all(
        len(vector) == len(c.HISTORY) for queue in state.history.values() for _, vector in queue
    )
    monkeypatch.setattr(c, "MAX_OBSERVATIONS", 1)
    with pytest.raises(ValueError, match="bound"):
        state.observe(observation(120))


def test_support_proxy_orientations_are_explicit_and_not_iceberg_labels():
    row = observation(value=3)
    row["execution_features"].update(
        ask_passive_5s=4,
        bid_passive_5s=1,
        bid_held_top_passive_5s=2,
        ask_held_top_passive_5s=1,
        bid_other_id_reload_5s=5,
        ask_other_id_reload_5s=3,
    )
    row["features"].update(normalized_bid_reload_5s=4, normalized_ask_reload_5s=1)
    result, _ = c.transform([row])
    assert [result[0, index(key)] for key in c.DERIVED] == [3, 1, 2, 3]
    assert result[0, index("cvd_price_product")] == 6
    assert result[0, index("cvd_held_support_product")] == 3
    assert not any("iceberg" in key for key in c.FEATURES)
