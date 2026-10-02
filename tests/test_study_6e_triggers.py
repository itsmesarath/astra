"""Causal episodes, train-only calibration, unknown retention and sealed complete studies."""

import math
from copy import deepcopy

import numpy as np
import pytest
from test_causal_6e_context import DAY, observation
from test_historical_6e_archive import census_root as census_root
from test_historical_6e_cohort import metadata_root as metadata_root
from test_historical_6e_manifest import manifest_evidence as manifest_evidence
from test_historical_6e_manifest import protected_evidence as protected_evidence
from test_historical_6e_resource_replay import evidence as evidence

from ai_trader.training import study_6e_triggers as t


def bundle():
    return {"cutoffs": {"activity": 2.0, "absolute_cvd": 1.0, "held_passive": 0.5}}


def active(offset=0, sign=1):
    row = observation(offset, 2.0 * sign)
    row["features"].update(
        log_known_trades_5s=3.0, mid_change_5s_ticks=2.0 * sign, normalized_ofi_5s=sign
    )
    return row


def state():
    return t.TriggerState(DAY, observation()["contract"], bundle())


def test_rising_edges_sign_changes_and_inactive_rearming():
    s = state()
    assert s.observe(active())["sweep_proxy"] == 1
    assert all(s.observe(active(1))[key] == 0 for key in ("activity",))
    assert s.observe(active(2, -1))["burst"] == -1
    quiet = active(3)
    quiet["features"]["log_known_trades_5s"] = 0
    assert s.observe(quiet)["activity"] == 0
    assert s.observe(active(4))["activity"] == 1


def test_families_rearm_independently_without_new_activity_episode():
    s = state()
    first = active()
    first["features"]["normalized_ofi_5s"] = -1
    assert s.observe(first)["sweep_proxy"] == 0
    next_event = s.observe(active(1))
    assert next_event["sweep_proxy"] == 1 and next_event["activity"] == 0


@pytest.mark.parametrize("sign,side", [(1, "ask"), (-1, "bid")])
def test_absorption_requires_aggression_side_held_passive_and_reload(sign, side):
    row = active(sign=sign)
    row["features"]["mid_change_5s_ticks"] = 0
    row["execution_features"][f"{side}_held_top_passive_5s"] = 0.5
    assert state().observe(row)["absorption_reload_proxy"] == 0
    row["execution_features"][f"{side}_other_id_reload_5s"] = 0.01
    assert state().observe(row)["absorption_reload_proxy"] == sign
    unsupported = bundle()
    unsupported["cutoffs"]["held_passive"] = None
    assert (
        t.TriggerState(DAY, row["contract"], unsupported).observe(row)["absorption_reload_proxy"]
        == 0
    )


def test_unknown_aggressors_and_zero_activity_or_cvd_do_not_trigger():
    for feature, value in (
        ("unknown_trade_fraction_5s", 0.10001),
        ("log_known_trades_5s", 0),
        ("normalized_cvd_5s", 0),
    ):
        row = active()
        row["features"][feature] = value
        assert all(state().observe(row)[key] == 0 for key in t.FAMILIES)


def test_exact_cutoff_and_one_tick_proxy_boundary():
    row = active()
    row["features"].update(log_known_trades_5s=2, normalized_cvd_5s=1, mid_change_5s_ticks=1)
    assert state().observe(row)["sweep_proxy"] == 1
    row["features"]["mid_change_5s_ticks"] = 0.999
    assert state().observe(row)["sweep_proxy"] == 0


@pytest.mark.parametrize(
    "gap,quote_gap,reset",
    [(5, 0, False), (6, 0, True), (1, math.log1p(5000), False), (1, math.log1p(5001), True)],
)
def test_gap_reset_uses_only_current_causal_metadata(gap, quote_gap, reset):
    s = state()
    s.observe(active())
    row = active(gap)
    row["features"]["log_prior_quote_gap_ms"] = quote_gap
    assert bool(s.observe(row)["activity"]) is reset
    assert s.resets == int(reset)


def test_prefix_invariance_poisoned_future_fields_and_same_event_controls():
    rows = [active(i, 1 if i < 8 else -1) for i in range(20)]
    signs, _ = t.directions(rows, bundle())
    poisoned = deepcopy(rows)
    for row in poisoned:
        row.update(
            outcome="poison",
            eligible="poison",
            net_targets_long_short_ticks="poison",
            hindsight_action="poison",
            path_horizons="poison",
        )
    for row in poisoned[10:]:
        row["features"]["log_known_trades_5s"] = 0
    changed, _ = t.directions(poisoned, bundle())
    prefix, _ = t.directions(rows[:10], bundle())
    for name in t.POLICIES:
        np.testing.assert_array_equal(signs[name][:10], changed[name][:10])
        np.testing.assert_array_equal(signs[name][:10], prefix[name])
    for family in t.FAMILIES:
        np.testing.assert_array_equal(signs[f"{family}_reverse"], -signs[f"{family}_follow"])
        assert not np.any(signs[f"{family}_queue"][signs[f"{family}_follow"] == 0])


@pytest.mark.parametrize(
    "change", ["time", "session", "contract", "partition", "allowlist", "nan", "negative_execution"]
)
def test_invalid_identity_order_or_features_refuse(change):
    row = active(1)
    if change == "time":
        row["decision_ts_ns"] -= t.SECOND
    elif change == "session":
        row["source_session"] = "2025-04-08"
    elif change == "contract":
        row["contract"] = "6EU5"
    elif change == "partition":
        row["partition"] = "reserved"
    elif change == "allowlist":
        row["features"]["future_return"] = 10
    elif change == "nan":
        row["features"]["normalized_cvd_5s"] = float("nan")
    else:
        row["execution_features"]["bid_passive_5s"] = -1
    s = state()
    s.observe(active())
    with pytest.raises(ValueError):
        s.observe(row)


@pytest.mark.parametrize("value", [float("nan"), -1, True])
def test_invalid_cutoffs_are_rejected(value):
    changed = bundle()
    changed["cutoffs"]["activity"] = value
    with pytest.raises(ValueError, match="cutoffs"):
        t.TriggerState(DAY, observation()["contract"], changed)


@pytest.mark.parametrize("day", ["2025-10-01", "2026-01-01"])
def test_later_or_reserved_cannot_calibrate_even_before_feature_access(day):
    with pytest.raises(ValueError):
        t.calibrate([{"source_session": day}])


def test_calibration_is_feature_only_unknowns_cannot_be_zero_labels():
    rows = [active(i) for i in range(10)]
    rows[0]["execution_features"]["bid_held_top_passive_5s"] = 1
    rows[1]["execution_features"]["ask_held_top_passive_5s"] = 3
    result = t.calibrate(rows)
    assert result["cutoffs"] == {"activity": 3.0, "absolute_cvd": 2.0, "held_passive": 2.8}
    assert result["positive_held_side_observations"] == 2
    assert result["targets_used"] is False
    rows[0]["outcome"] = None
    with pytest.raises(ValueError, match="causal projections"):
        t.calibrate(rows)


def test_all_event_summary_keeps_ineligible_loss_and_unknown():
    rows = [
        {
            "eligible": True,
            "outcome": {"status": "resolved"},
            "net_targets_long_short_ticks": [3.0, -7.0],
        },
        {
            "eligible": True,
            "outcome": {"status": "resolved"},
            "net_targets_long_short_ticks": [-2.0, -2.0],
        },
        {
            "eligible": False,
            "outcome": {"status": "not_eligible"},
            "net_targets_long_short_ticks": None,
        },
        {
            "eligible": True,
            "outcome": {"status": "no_entry_quote_timeout"},
            "net_targets_long_short_ticks": None,
        },
    ]
    summary = t.trigger_summary(rows, np.array([1, -1, 1, 1]), np.array([1, 0, 0, -1]))
    assert summary["detected"] == 4 and summary["eligible"] == 3
    assert summary["resolved"] == summary["unknown"] == 2
    assert summary["follow_positive"] == summary["neither_positive"] == 1
    assert summary["follow_net_ticks_sum"] == 1 and summary["queue_ties"] == 2


@pytest.fixture
def trigger_evidence(manifest_evidence):
    root, manifest_path, manifest_pin, manifest = manifest_evidence
    path = root / "trigger-registration.json"
    t.prepare(root, manifest_path, manifest_pin, path)
    return root, path, t.common.hash_file(path, t.data.MAX_MANIFEST_BYTES), manifest


def test_calibration_reader_only_training_cases_includes_unknowns(trigger_evidence, monkeypatch):
    root, _, _, manifest = trigger_evidence
    original, opened = t.data.read_rows, []

    def guarded(root, entry, kind):
        assert entry["role"] == "train" and kind == "cases"
        opened.append(entry["utc_date"])
        return original(root, entry, kind)

    monkeypatch.setattr(t.data, "read_rows", guarded)
    samples, accounting = t.calibration_cases(root, manifest)
    fitted = t.calibrate(samples)
    assert accounting["unknown"] > 0
    assert fitted["calibration_cases"] == accounting["cases"]
    assert set(fitted["cases_by_session"]) == set(opened)
    assert all("outcome" not in row and "eligible" not in row for row in samples)


def test_full_study_keeps_all_roles_no_fitting_and_pins_every_day(trigger_evidence, monkeypatch):
    root, path, pin, manifest = trigger_evidence
    original, opened = t.data.read_rows, []

    def guarded(root, entry, kind):
        assert entry["role"] in t.data.ROLES
        assert kind == "rows" or entry["role"] == "train"
        opened.append((entry["utc_date"], kind))
        return original(root, entry, kind)

    monkeypatch.setattr(t.data, "read_rows", guarded)
    monkeypatch.setattr(t.prior.baseline, "fit", lambda *a: pytest.fail("Model fitted"))
    output = root / "data/processed/triggers"
    result = t.run(root, path, pin, output)
    assert result["status"] == "completed_trigger_development_not_promoted"
    expected = [entry["utc_date"] for entry in manifest["ledger"] if entry["role"] in t.data.ROLES]
    assert [item["source_session"] for item in result["daily_reports"]] == expected
    assert [day for day, kind in opened if kind == "rows"] == expected
    thresholds = t.data.review.pinned(output / "thresholds.json", result["thresholds_file_sha256"])
    assert t.common.digest(thresholds) == result["thresholds_content_sha256"]
    days = []
    for item in result["daily_reports"]:
        day = t.data.review.pinned(output / f"{item['source_session']}.json", item["sha256"])
        assert day["policies"]["no_trade"]["selected"] == 0
        days.append(day)
    for role in t.data.ROLES:
        assert t.aggregate([day for day in days if day["role"] == role]) == result["by_role"][role]
    assert all(
        result[key] is False
        for key in (
            "model_fitted",
            "qwen_trained",
            "trading_enabled",
            "promotion_enabled",
            "reserved_outcomes_opened",
        )
    )
    assert not (output / "failure.json").exists()
    with pytest.raises(ValueError, match="new"):
        t.run(root, path, pin, output)


@pytest.mark.parametrize("change", ["purpose", "quantile", "implementation"])
def test_registration_drift_refuses_before_reads_or_output(trigger_evidence, monkeypatch, change):
    root, path, pin, _ = trigger_evidence
    if change == "purpose":
        monkeypatch.setattr(t, "PURPOSE", "unregistered")
    elif change == "quantile":
        monkeypatch.setattr(t, "QUANTILE", 0.8)
    else:
        monkeypatch.setattr(t, "fingerprints", lambda: {})
    monkeypatch.setattr(t.data, "read_rows", lambda *a: pytest.fail("drifted reads"))
    output = root / "data/processed/drifted"
    with pytest.raises(ValueError, match="changed"):
        t.run(root, path, pin, output)
    assert not output.exists()


def test_failure_retains_evidence_and_never_completes_subset(trigger_evidence, monkeypatch):
    root, path, pin, _ = trigger_evidence
    original = t.data.read_rows

    def broken(root, entry, kind):
        if kind == "rows":
            raise ValueError("retained source failure")
        return original(root, entry, kind)

    monkeypatch.setattr(t.data, "read_rows", broken)
    output = root / "data/processed/failed"
    with pytest.raises(ValueError, match="source failure"):
        t.run(root, path, pin, output)
    assert (output / "failure.json").exists() and not (output / "completion.json").exists()


def test_end_of_run_rechecks_consumed_sources(trigger_evidence, monkeypatch):
    root, path, pin, manifest = trigger_evidence
    original, count = t.evaluate_day, 0
    total = manifest["coverage"]["decision_sessions"]

    def mutate(bundle, rows):
        nonlocal count
        result = original(bundle, rows)
        count += 1
        if count == total:
            entry = next(entry for entry in manifest["ledger"] if entry["role"] == "train")
            source = root / entry["artifacts"]["rows"]["path"]
            source.write_bytes(source.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(t, "evaluate_day", mutate)
    output = root / "data/processed/mutated"
    with pytest.raises(ValueError):
        t.run(root, path, pin, output)
    assert (output / "failure.json").exists() and not (output / "completion.json").exists()
