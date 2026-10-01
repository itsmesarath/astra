"""Historical diagnostic arithmetic and the boundary between signal and hindsight."""

from copy import deepcopy
from dataclasses import asdict

import numpy as np
import pytest
from test_6e_cost_baseline import ns, row
from test_6e_opportunity import cohort

from ai_trader.research import historical_6e_diagnostics as research


@pytest.mark.parametrize("ticks", [-10, -3, 0, 3, 10])
def test_decomposition_accounts_for_both_spreads_and_extra_cost(ticks):
    r = row(ticks=ticks)
    mid, burden = research.decomposition(r)
    assert mid == ticks and burden == 1
    r["outcome"]["exit_ask_nano"] += research.data.clock.TICK
    r["net_targets_long_short_ticks"], r["hindsight_action"] = research.data.base.observed_targets(
        r["outcome"]
    )
    assert research.decomposition(r) == (ticks + 0.5, 1.5)
    r["net_targets_long_short_ticks"][0] += 1
    with pytest.raises(ValueError, match="decomposition"):
        research.decomposition(r)


def test_hindsight_oracle_is_not_a_policy_and_unknowns_remain_counted():
    rows = [row(ticks=3), row(ticks=-3), row(ticks=0)]
    unknown = row()
    unknown.update(
        outcome={"status": "no_entry_quote_timeout"},
        net_targets_long_short_ticks=None,
        hindsight_action=None,
    )
    result = research.summarize([*rows, unknown])
    assert result["eligible"] == 4 and result["resolved"] == 3
    assert result["unavailable_among_eligible"] == 1
    assert result["opportunity_fraction_resolved"] == 2 / 3
    assert result["cost_sensitivity"]["1"]["long_mean_ticks"] == -2
    assert result["cost_sensitivity"]["1"]["short_mean_ticks"] == -2
    assert result["cost_sensitivity"]["4"]["hindsight_either_positive_fraction"] == 0
    assert research.summarize([unknown])["opportunity_fraction_resolved"] is None
    assert research.summarize([])["resolved"] == 0


def test_thinning_never_selects_on_future_availability_and_resets_each_session():
    rows = [row(ns(12, m, s)) for m, s in [(0, 0), (0, 1), (1, 0), (1, 1)]]
    first = research.thin_causally(rows)
    assert first == [rows[0], rows[2]]
    rows[0]["outcome"] = {"status": "no_entry_quote_timeout"}
    assert research.thin_causally(rows) == first
    following = deepcopy(rows[0])
    following["source_session"] = "2025-07-08"
    following["decision_ts_ns"] += 86400 * 10**9
    assert research.thin_causally([*rows, following])[-1] == following
    with pytest.raises(ValueError):
        research.thin_causally(rows, 0)


def test_rule_directions_only_use_features_and_test_both_orientations():
    rows = cohort()[:3]
    for index, r in enumerate(rows):
        r["features"]["normalized_bid_reload_5s"] = index
        r["features"]["normalized_ask_reload_5s"] = 1
        r["features"]["sell_absorption_proxy_5s"] = 1
        r["features"]["buy_absorption_proxy_5s"] = index
    np.testing.assert_array_equal(
        research.rule_directions(rows, "reload_difference", 1), [-1, 0, 1]
    )
    np.testing.assert_array_equal(
        research.rule_directions(rows, "absorption_difference", 1), [1, 0, -1]
    )
    before = research.rule_directions(rows, "reload_difference", -1)
    for r in rows:
        r["outcome"] = {"future": "hidden"}
        r["hindsight_action"] = 1
    np.testing.assert_array_equal(research.rule_directions(rows, "reload_difference", -1), before)
    with pytest.raises(ValueError):
        research.rule_directions(rows, "future_profit", 1)


def test_rules_keep_losses_and_enforce_nonoverlap_cooldown():
    rows = [row(ns(12, 0, s), ticks=-3) for s in (0, 1, 15, 25, 26)]
    result = research.summarize_rule(rows, np.ones(5))
    assert result["selected"] == result["closed"] == 2
    assert result["mean_net_ticks"] == -5
    assert result["mean_signed_midpoint_ticks"] == -3
    assert result["mean_spread_burden_ticks"] == 1
    assert result["cost_sensitivity_mean_ticks"]["0"] == -4
    assert result["cost_sensitivity_mean_ticks"]["4"] == -8
    assert "selections" not in result
    assert result["descriptive_daily_bootstrap_95_interval"] is None
    with pytest.raises(ValueError):
        research.summarize_rule(rows, np.array([1, 1]))


def test_session_bootstrap_is_deterministic():
    rows = cohort()
    first = research.summarize_rule(rows, np.ones(len(rows)))
    assert research.summarize_rule(rows, np.ones(len(rows))) == first
    low, high = first["descriptive_daily_bootstrap_95_interval"]
    assert low <= first["daily_equal_weight_mean_ticks"] <= high


@pytest.mark.parametrize(
    "target, score, expected",
    [
        ([0, 1], [0, 1], 1),
        ([0, 1], [1, 0], 0),
        ([0, 1], [0.5, 0.5], 0.5),
        ([0, 1, 1, 0], [0, 0.5, 0.5, 1], 0.5),
        ([1, 1], [0, 1], None),
    ],
)
def test_auc_ranks_ties_without_fitted_threshold(target, score, expected):
    assert research.auc(target, score) == expected


@pytest.mark.parametrize("target, score", [([0, 2], [0, 1]), ([0, 1], [0]), ([0, 1], [0, np.nan])])
def test_auc_invalid_input(target, score):
    with pytest.raises(ValueError):
        research.auc(target, score)


def test_feature_cuts_ignore_later_data_and_all_outcomes():
    rows = cohort()
    first = research.feature_bins(rows)
    changed = deepcopy(rows)
    for r in changed:
        if r["source_session"] in research.LATER:
            r["features"] = {f: 1e8 for f in research.data.FEATURES}
        r["outcome"] = {"status": "no_entry_quote_timeout"}
        r["net_targets_long_short_ticks"] = r["hindsight_action"] = None
    second = research.feature_bins(changed)
    for key in first:
        assert (
            first[key]["cuts_from_early_eligible_features_only"]
            == second[key]["cuts_from_early_eligible_features_only"]
        )


def test_inventory_is_metadata_only_and_refuses_duplicate_dates():
    file = {"date": "2025-03-26", "condition": "available", "dbn_header": {"partial": []}}
    inventory = {"batches": [{"archive_bytes": 100, "files": [file]}]}
    result = research.inventory_summary(inventory)
    assert result["daily_files"] == 1 and result["archive_bytes"] == 100
    assert result["full_corpus_event_replay_performed"] is False
    inventory["batches"][0]["files"].append(file)
    with pytest.raises(ValueError):
        research.inventory_summary(inventory)


def test_classifier_factorization_uses_original_development_and_does_not_fit(monkeypatch):
    rows = cohort()
    model = research.common.OpportunityModel(
        [0.0] * 23, [1.0] * 23, [[0.0, 0.0, 0.0]] * 23, np.log([0.1, 0.8, 0.1]).tolist()
    )
    report = {
        "model": asdict(model),
        "model_sha256": research.common.digest(asdict(model)),
        "training": {"prior_short_neither_long": [0.1, 0.8, 0.1]},
    }
    monkeypatch.setattr(research.common, "fit", lambda *_: pytest.fail("Diagnostic tried fitting"))
    result = research.classifier_diagnostic(rows, report)
    assert result["resolved"] == 306
    assert result["any_opportunity"]["auc"] == 0.5
    assert result["direction_given_hindsight_opportunity"]["auc"] == 0.5
    assert result["direction_given_hindsight_opportunity"]["rows"] == 204
    assert result["direction_given_hindsight_opportunity"]["accuracy_at_fixed_half"] == 0.5


def test_output_and_pin_refusals_before_analysis(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    output.write_text("keep")
    with pytest.raises(FileExistsError):
        research.run(tmp_path, output)
    assert output.read_text() == "keep"
    monkeypatch.setattr(
        research, "pinned_json", lambda *_: (_ for _ in ()).throw(ValueError("pin"))
    )
    with pytest.raises(ValueError, match="pin"):
        research.run(tmp_path, tmp_path / "new.json")
    assert not (tmp_path / "new.json").exists()
