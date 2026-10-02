"""Same causal cohort, train-only nonlinear fits and complete research-only outputs."""

from copy import deepcopy

import numpy as np
import pytest
from test_historical_6e_archive import census_root as census_root
from test_historical_6e_cohort import metadata_root as metadata_root
from test_historical_6e_cohort import write_json
from test_historical_6e_manifest import manifest_evidence as manifest_evidence
from test_historical_6e_manifest import protected_evidence as protected_evidence
from test_historical_6e_resource_replay import evidence as evidence

from ai_trader.training import train_6e_context as t


@pytest.fixture
def context_evidence(manifest_evidence, monkeypatch):
    root, manifest_path, manifest_pin, manifest = manifest_evidence
    for name in ("MIN_LEAF", "MIN_SESSIONS", "MIN_SESSION_ROWS"):
        monkeypatch.setattr(t.tree, name, 1)
    path = root / "context-registration.json"
    t.prepare(root, manifest_path, manifest_pin, path)
    return root, path, t.common.hash_file(path, t.data.MAX_MANIFEST_BYTES), manifest


def toy_samples():
    samples = [
        {"source_session": "2025-04-07", "status": "resolved", "targets": [1.0, -5.0]}
        for _ in range(30)
    ]
    features = np.zeros((30, len(t.context.FEATURES)))
    features[15:, 0] = 1
    for row in samples[15:]:
        row["targets"] = [-5.0, 1.0]
    samples[-1].update(status="no_entry_quote_timeout", targets=None)
    return features, samples


def toy_fit(monkeypatch):
    for name in ("MIN_LEAF", "MIN_SESSIONS", "MIN_SESSION_ROWS"):
        monkeypatch.setattr(t.tree, name, 1)
    return t.fit_models(*toy_samples())


def test_two_fixed_fits_use_same_resolved_cases_and_context_keeps_original_columns(monkeypatch):
    bundle = toy_fit(monkeypatch)
    assert set(bundle["models"]) == set(t.MODELS)
    assert all(spec["fit_rows"] == 29 for spec in bundle["models"].values())
    features, _ = toy_samples()
    before = t.common.digest(bundle)
    monkeypatch.setattr(t.tree, "fit", lambda *a: pytest.fail("evaluation fitted"))
    for name in t.MODELS:
        forecast = t.predictions(bundle, features, name)
        np.testing.assert_allclose(forecast[:15], np.tile([1.0, -5.0], (15, 1)))
        np.testing.assert_allclose(forecast[15:], np.tile([-5.0, 1.0], (15, 1)))
    assert t.common.digest(bundle) == before


@pytest.mark.parametrize("day", ["2025-10-01", "2026-01-01"])
def test_later_and_reserved_cases_cannot_fit(day, monkeypatch):
    features, samples = toy_samples()
    samples[-1]["source_session"] = day
    monkeypatch.setattr(t.tree, "fit", lambda *a: pytest.fail("prohibited fit"))
    with pytest.raises(ValueError):
        t.fit_models(features, samples)


def test_unknown_targets_cannot_be_replaced_by_zero_or_no_trade(monkeypatch):
    features, samples = toy_samples()
    samples[-1]["targets"] = [0.0, 0.0]
    monkeypatch.setattr(t.tree, "fit", lambda *a: pytest.fail("unknown learned"))
    with pytest.raises(ValueError, match="aligned causal"):
        t.fit_models(features, samples)


def test_modified_parameters_or_feature_order_refused(monkeypatch):
    bundle = toy_fit(monkeypatch)
    bundle["models"]["context_tree"]["parameters"]["nodes"][0]["mean"][0] += 1
    with pytest.raises(ValueError, match="Frozen"):
        t.predictions(bundle, toy_samples()[0], "context_tree")


def test_training_reader_opens_only_training_full_rows_and_cases(context_evidence, monkeypatch):
    root, _, _, manifest = context_evidence
    original = t.data.read_rows
    seen = []

    def guarded(root, entry, kind):
        assert entry["role"] == "train"
        seen.append((entry["utc_date"], kind))
        return original(root, entry, kind)

    monkeypatch.setattr(t.data, "read_rows", guarded)
    matrix, samples, stats = t.training_cases(root, manifest)
    assert matrix.shape == (len(samples), len(t.context.FEATURES))
    assert stats["unknown"] > 0 and stats["context"]["rows"] > stats["cases"]
    assert seen == [(day, kind) for day in stats["sessions"] for kind in ("rows", "cases")]
    assert all(set(row) == {"source_session", "status", "targets"} for row in samples)


def test_case_cohort_mismatch_fails_before_fit(context_evidence, monkeypatch):
    root, _, _, manifest = context_evidence
    original = t.data.read_rows

    def altered(root, entry, kind):
        rows = original(root, entry, kind)
        if kind == "cases":
            rows[0]["features"]["queue_imbalance"] += 0.1
        return rows

    monkeypatch.setattr(t.data, "read_rows", altered)
    with pytest.raises(ValueError, match="causal decision cohort"):
        t.training_cases(root, manifest)


def test_audit_is_metadata_only_retains_all_accepted_days_and_checks_conservation(
    context_evidence, monkeypatch
):
    root, _, _, manifest = context_evidence
    monkeypatch.setattr(t.data, "read_rows", lambda *a: pytest.fail("audit opened outcomes"))
    result = t.audit_reports(root, manifest)
    assert len(result["sessions"]) == manifest["coverage"]["decision_sessions"]
    assert result["conservation_verified"] is True
    assert result["confirmed_iceberg_labels"] is False


def test_complete_context_experiment_is_pinned_and_no_reserved_or_later_cases_opened(
    context_evidence, monkeypatch
):
    root, path, pin, manifest = context_evidence
    original = t.data.read_rows

    def guarded(root, entry, kind):
        assert entry["role"] in t.data.ROLES
        assert kind == "rows" or entry["role"] == "train"
        return original(root, entry, kind)

    monkeypatch.setattr(t.data, "read_rows", guarded)
    output = root / "data/processed/context"
    result = t.run(root, path, pin, output)
    assert result["status"] == "completed_context_development_not_promoted"
    assert result["coverage"] == manifest["coverage"]
    bundle = t.data.review.pinned(output / "models.json", result["models_file_sha256"])
    assert t.common.digest(bundle) == result["models_content_sha256"]
    expected = [e["utc_date"] for e in manifest["ledger"] if e["role"] in t.data.ROLES[1:]]
    assert [d["source_session"] for d in result["daily_reports"]] == expected
    for item in result["daily_reports"]:
        day = t.data.review.pinned(output / f"{item['source_session']}.json", item["sha256"])
        assert day["no_trade"]["selected"] == 0
    assert all(
        result[k] is False
        for k in (
            "qwen_trained",
            "trading_enabled",
            "promotion_enabled",
            "reserved_outcomes_opened",
        )
    )
    assert not (output / "failure.json").exists()
    with pytest.raises(ValueError, match="new"):
        t.run(root, path, pin, output)


@pytest.mark.parametrize("change", ["purpose", "threshold", "implementation", "manifest"])
def test_registration_drift_refuses_before_any_read_or_fit(context_evidence, monkeypatch, change):
    root, path, pin, _ = context_evidence
    if change == "purpose":
        monkeypatch.setattr(t, "PURPOSE", "new-purpose")
    elif change == "threshold":
        monkeypatch.setattr(t.baseline, "THRESHOLD", 0.0)
    elif change == "implementation":
        monkeypatch.setattr(t, "fingerprints", lambda: {})
    else:
        record = t.data.review.pinned(path, pin)
        write_json(root / record["manifest"]["path"], {})
    monkeypatch.setattr(t, "training_cases", lambda *a: pytest.fail("data opened"))
    with pytest.raises(ValueError):
        t.run(root, path, pin, root / "data/processed/context")


def test_partial_evaluation_keeps_failure_never_subset_success(context_evidence, monkeypatch):
    root, path, pin, _ = context_evidence
    original = t.evaluate_day
    count = 0

    def fail_second(*args):
        nonlocal count
        count += 1
        if count == 2:
            raise ValueError("second context day failed")
        return original(*args)

    monkeypatch.setattr(t, "evaluate_day", fail_second)
    output = root / "data/processed/context"
    with pytest.raises(ValueError, match="second context day"):
        t.run(root, path, pin, output)
    assert (output / "failure.json").exists()
    assert (output / "models.json").exists()
    assert not (output / "completion.json").exists()


def test_future_changes_cannot_change_predictions(context_evidence):
    root, _, _, manifest = context_evidence
    features, samples, _ = t.training_cases(root, manifest)
    bundle = t.fit_models(features, samples)
    entry = next(e for e in manifest["ledger"] if e["role"] == "validation_development")
    rows = t.data.read_rows(root, entry, "rows")
    first, _ = t.context.transform(rows)
    changed = deepcopy(rows)
    for row in changed:
        row.update(
            eligible=False,
            outcome=None,
            hindsight_action=-1,
            net_targets_long_short_ticks=[999, -1000],
        )
    second, _ = t.context.transform(changed)
    for name in t.MODELS:
        np.testing.assert_array_equal(
            t.predictions(bundle, first, name), t.predictions(bundle, second, name)
        )


def test_input_changed_after_read_prevents_completion(context_evidence, monkeypatch):
    root, path, pin, manifest = context_evidence
    entry = next(e for e in manifest["ledger"] if e["role"] == "train")
    original = t.fit_models

    def alter_input(features, samples):
        bundle = original(features, samples)
        file = root / entry["artifacts"]["rows"]["path"]
        file.write_bytes(file.read_bytes() + b"changed")
        return bundle

    monkeypatch.setattr(t, "fit_models", alter_input)
    output = root / "data/processed/context"
    with pytest.raises(ValueError, match="changed census artifact"):
        t.run(root, path, pin, output)
    assert (output / "failure.json").exists()
    assert not (output / "completion.json").exists()


def test_no_resolved_evaluation_rows_keep_unknowns_without_mse(context_evidence):
    root, _, _, manifest = context_evidence
    features, samples, _ = t.training_cases(root, manifest)
    bundle = t.fit_models(features, samples)
    entry = next(e for e in manifest["ledger"] if e["role"] == "validation_development")
    rows = t.data.read_rows(root, entry, "rows")
    for row in rows:
        row.update(outcome={"status": "no_entry_quote_timeout"}, net_targets_long_short_ticks=None)
    result = t.evaluate_day(bundle, rows)
    assert result["resolved"] == 0
    assert all(
        model["mean_squared_error_long_short"] is None for model in result["models"].values()
    )
    assert t.aggregate([result])["unknown"] == len(rows)


def test_execution_audit_rejects_double_used_reload_credit(context_evidence, monkeypatch):
    root, _, _, manifest = context_evidence
    original = t.data.review.pinned

    def corrupt_report(path, pin, *args):
        result = original(path, pin, *args)
        if "quality" in result:
            values = result["quality"]["execution_flow"][0]["audit_including_warmup"]
            values["A_other_id_reload_volume"] = values.get("A_linked_decrease_volume", 0) + 1
        return result

    monkeypatch.setattr(t.data.review, "pinned", corrupt_report)
    with pytest.raises(ValueError, match="conservation"):
        t.audit_reports(root, manifest)
