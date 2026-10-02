"""Train-only activity/scalers, frozen fits, unknown accounting and proxy economics."""

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from test_historical_6e_archive import census_root as census_root
from test_historical_6e_cohort import metadata_root as metadata_root
from test_historical_6e_manifest import manifest_evidence as manifest_evidence
from test_historical_6e_manifest import protected_evidence as protected_evidence
from test_historical_6e_resource_replay import evidence as evidence

from ai_trader.training import train_6e_activity_direction as trainer


@pytest.fixture
def training_evidence(manifest_evidence, monkeypatch):
    root, manifest_path, manifest_pin, manifest = manifest_evidence
    for name in ("MIN_RESOLVED", "MIN_GATED", "MIN_GATED_SESSIONS"):
        monkeypatch.setattr(trainer, name, 1)
    path = root / "training-registration.json"
    trainer.prepare(root, manifest_path, manifest_pin, path)
    pin = trainer.common.hash_file(path, trainer.data.MAX_MANIFEST_BYTES)
    return root, path, pin, root / "data/processed/training", manifest


def synthetic_cases():
    result = []
    for i in range(30):
        feature = {k: 0.0 for k in trainer.census.study.data.FEATURES}
        feature[trainer.ACTIVITY_FEATURE] = float(i)
        feature["queue_imbalance"] = (i - 15) / 30
        feature["normalized_cvd_5s"] = i / 10
        result.append(
            {
                "source_session": "2025-04-07",
                "features": feature,
                "execution_features": {k: 0.0 for k in trainer.census.study.flow.FEATURES},
                "outcome": {"status": "resolved" if i < 29 else "no_entry_quote_timeout"},
                "net_targets_long_short_ticks": [i / 10 - 2, -i / 10 - 2] if i < 29 else None,
            }
        )
    return result


def fit_toy(monkeypatch):
    for name in ("MIN_RESOLVED", "MIN_GATED", "MIN_GATED_SESSIONS"):
        monkeypatch.setattr(trainer, name, 1)
    return trainer.fit_models(synthetic_cases())


def test_activity_cutoff_includes_unknown_causal_training_features_and_four_fixed_fits(monkeypatch):
    bundle = fit_toy(monkeypatch)
    assert bundle["activity_cutoff"] == float(np.quantile(np.arange(30), 0.7))
    assert bundle["gate_training_cases"] == 9
    assert bundle["models"]["activity_microstructure"]["fit_rows"] == 8
    assert all(
        bundle["models"][k]["fit_rows"] == 29
        for k in trainer.MODELS
        if k != "activity_microstructure"
    )
    rows = synthetic_cases()
    gated = [
        r
        for r in rows
        if r["features"][trainer.ACTIVITY_FEATURE] >= bundle["activity_cutoff"]
        and r["outcome"]["status"] == "resolved"
    ]
    expected_means = trainer.matrix(gated, trainer.FEATURES).mean(axis=0)
    assert np.array_equal(
        bundle["models"]["activity_microstructure"]["parameters"]["means"], expected_means
    )


def test_validation_or_reserved_rows_cannot_fit_even_if_repinned(monkeypatch):
    rows = synthetic_cases()
    for day in ("2025-10-01", "2026-01-01"):
        rows[-1]["source_session"] = day
        with pytest.raises(ValueError):
            trainer.fit_models(rows)


@pytest.mark.parametrize(
    "feature", ["hindsight_action", "outcome", "source_session", "net_targets_long_short_ticks"]
)
def test_target_or_metadata_columns_cannot_become_features(feature):
    with pytest.raises(ValueError, match="allowlist"):
        trainer.matrix(synthetic_cases(), (feature,))


def test_predictions_do_not_depend_on_future_outcomes_or_mutate_the_model(monkeypatch):
    bundle = fit_toy(monkeypatch)
    rows = synthetic_cases()
    before = trainer.common.digest(bundle)
    a = trainer.predictions(bundle, rows, "activity_microstructure")
    changed = deepcopy(rows)
    for row in changed:
        row["outcome"] = {"status": "unresolved_exit_window_end"}
        row["net_targets_long_short_ticks"] = None
        row["hindsight_action"] = 1
    monkeypatch.setattr(trainer.baseline, "fit", lambda *a: pytest.fail("evaluation fitted"))
    b = trainer.predictions(bundle, changed, "activity_microstructure")
    assert all(np.array_equal(x, y) for x, y in zip(a, b, strict=True))
    assert trainer.common.digest(bundle) == before
    active = trainer.matrix(rows, (trainer.ACTIVITY_FEATURE,))[:, 0] >= bundle["activity_cutoff"]
    assert np.all(a[1][~active] == 0)
    assert np.array_equal(a[0][active], a[1][active])


def test_changed_model_or_feature_order_refused(monkeypatch):
    bundle = fit_toy(monkeypatch)
    bundle["models"]["cvd_only"]["parameters"]["bias"][0] += 1
    with pytest.raises(ValueError, match="Frozen"):
        trainer.predictions(bundle, synthetic_cases(), "cvd_only")


@pytest.mark.parametrize("cutoff", [float("nan"), float("inf"), True])
def test_nonfinite_or_boolean_activity_cutoff_refused(monkeypatch, cutoff):
    bundle = fit_toy(monkeypatch)
    bundle["activity_cutoff"] = cutoff
    with pytest.raises(ValueError, match="cutoff must be finite"):
        trainer.predictions(bundle, synthetic_cases(), "activity_microstructure")


def test_insufficient_support_never_fits_a_model(monkeypatch):
    monkeypatch.setattr(trainer.baseline, "fit", lambda *a: pytest.fail("unsupported fit"))
    with pytest.raises(ValueError, match="support"):
        trainer.fit_models(synthetic_cases())


def test_training_reader_never_opens_later_or_reserved_cases(training_evidence, monkeypatch):
    root, _, _, _, manifest = training_evidence
    original = trainer.data.read_rows
    seen = []

    def guarded(root, entry, kind):
        assert entry["role"] == "train"
        assert kind == "cases"
        seen.append(entry["utc_date"])
        return original(root, entry, kind)

    monkeypatch.setattr(trainer.data, "read_rows", guarded)
    rows, stats = trainer.training_cases(root, manifest)
    assert seen == stats["sessions"]
    assert stats["unknown"] > 0
    assert stats["cases"] == len(rows)
    assert all("path_horizons" not in row for row in rows)
    assert all(trainer.data.role_for_day(row["source_session"]) == "train" for row in rows)


def test_complete_cpu_experiment_is_pinned_research_only_and_keeps_every_evaluation_day(
    training_evidence,
):
    root, path, pin, output, manifest = training_evidence
    result = trainer.run(root, path, pin, output)
    assert result["status"] == "completed_development_experiment_not_promoted"
    bundle = trainer.data.review.pinned(output / "models.json", result["models_file_sha256"])
    assert trainer.common.digest(bundle) == result["models_content_sha256"]
    assert len(bundle["models"]) == 4
    expected = [e["utc_date"] for e in manifest["ledger"] if e["role"] in trainer.data.ROLES[1:]]
    assert [d["source_session"] for d in result["daily_reports"]] == expected
    for day in result["daily_reports"]:
        report = trainer.data.review.pinned(output / f"{day['source_session']}.json", day["sha256"])
        assert report["no_trade"]["selected"] == 0
        assert report["rows"] > report["resolved"]
    assert all(
        result[k] is False
        for k in (
            "qwen_trained",
            "trading_enabled",
            "promotion_enabled",
            "reserved_outcomes_opened",
        )
    )
    assert result["training"]["unknown"] > 0
    assert result["decision"] == "development_only_not_ready_for_promotion"
    assert not (output / "failure.json").exists()
    with pytest.raises(ValueError, match="new"):
        trainer.run(root, path, pin, output)


def test_fixed_policy_reports_unknowns_and_recosts_all_closed_trades(training_evidence):
    root, _, _, _, manifest = training_evidence
    entry = next(e for e in manifest["ledger"] if e["role"] == "validation_development")
    rows = trainer.data.read_rows(root, entry, "rows")
    forecasts = np.zeros((len(rows), 2))
    first = next(i for i, r in enumerate(rows) if r["outcome"]["status"] == "resolved")
    unresolved = next(
        i for i, r in enumerate(rows) if r["outcome"]["status"] == "unresolved_exit_window_end"
    )
    forecasts[[first, unresolved]] = [3.0, -1.0]
    summary = trainer.policy_summary(rows, forecasts)
    assert summary["unresolved_entered"] > 0
    assert summary["closed"] > 0
    assert (
        summary["extra_cost_ticks"]["2"]["total_closed_net_ticks"]
        == summary["total_closed_net_ticks"] - summary["closed"]
    )
    assert (
        summary["extra_cost_ticks"]["4"]["total_closed_net_ticks"]
        == summary["total_closed_net_ticks"] - 3 * summary["closed"]
    )
    combined = trainer.pooled_policy([summary, summary])
    assert combined["closed"] == 2 * summary["closed"]
    assert combined["mean_net_ticks"] == summary["mean_net_ticks"]


def test_evaluation_with_no_resolved_targets_keeps_unknown_accounting(training_evidence):
    root, _, _, _, manifest = training_evidence
    fit_rows, _ = trainer.training_cases(root, manifest)
    bundle = trainer.fit_models(fit_rows)
    entry = next(e for e in manifest["ledger"] if e["role"] == "validation_development")
    rows = trainer.data.read_rows(root, entry, "rows")
    for row in rows:
        row["outcome"] = {"status": "no_entry_quote_timeout"}
        row["net_targets_long_short_ticks"] = None
    result = trainer.evaluate_day(bundle, rows)
    assert result["resolved"] == 0
    assert all(r["mean_squared_error_long_short"] is None for r in result["models"].values())
    assert trainer.aggregate([result])["unknown"] == len(rows)


@pytest.mark.parametrize("change", ["protocol", "implementation", "manifest"])
def test_registration_drift_refuses_before_any_fit(training_evidence, monkeypatch, change):
    root, path, pin, output, _ = training_evidence
    if change == "protocol":
        monkeypatch.setattr(trainer, "GATE_QUANTILE", 0.9)
    elif change == "implementation":
        monkeypatch.setattr(trainer, "fingerprints", lambda: {})
    else:
        value = trainer.data.review.pinned(path, pin)
        Path(value["manifest"]["path"]).write_bytes(b"{}")
    monkeypatch.setattr(trainer, "fit_models", lambda *a: pytest.fail("fit started"))
    with pytest.raises(ValueError):
        trainer.run(root, path, pin, output)
    assert not output.exists()


def test_partial_evaluation_stays_failed_never_successful_subset(training_evidence, monkeypatch):
    root, path, pin, output, _ = training_evidence
    original = trainer.evaluate_day
    calls = 0

    def fail_after_one(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("synthetic second-day error")
        return original(*args)

    monkeypatch.setattr(trainer, "evaluate_day", fail_after_one)
    with pytest.raises(ValueError, match="second-day"):
        trainer.run(root, path, pin, output)
    assert (output / "models.json").exists()
    assert (output / "failure.json").exists()
    assert not (output / "completion.json").exists()


def test_input_changed_after_read_prevents_completion(training_evidence, monkeypatch):
    root, path, pin, output, manifest = training_evidence
    original = trainer.fit_models
    entry = next(e for e in manifest["ledger"] if e["role"] == "train")

    def alter_input(rows):
        bundle = original(rows)
        file = root / entry["artifacts"]["cases"]["path"]
        file.write_bytes(file.read_bytes() + b"changed")
        return bundle

    monkeypatch.setattr(trainer, "fit_models", alter_input)
    with pytest.raises(ValueError, match="changed census artifact"):
        trainer.run(root, path, pin, output)
    assert (output / "failure.json").exists()
    assert not (output / "completion.json").exists()
