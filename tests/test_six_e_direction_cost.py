"""Synthetic objective math, causal timestamp isolation and frozen CPU-only studies."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import test_six_e_balance_plan as balance_tests
from test_six_e_balance_plan import original as original
from test_six_e_balance_plan import samples as samples
from test_six_e_forecast_eval import candidate as candidate
from test_six_e_forecast_eval import trial_request as trial_request
from test_six_e_lora_trial import gpu_request as gpu_request
from test_six_e_lora_trial import pin, write

from ai_trader.models.local_checkpoint import digest
from ai_trader.training import six_e_direction_cost as d

balance_frozen = balance_tests.frozen


@pytest.fixture
def frozen(balance_frozen):
    path, prior_pin, _ = balance_frozen
    output = path.parent / "direction-cost-plan.json"
    value = d.freeze(path, prior_pin, output)
    return output, pin(output), value


def test_import_is_cpu_only_without_native_or_exchange_packages():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; "
            "from ai_trader.training import six_e_direction_cost; "
            "assert not ({'torch', 'peft', 'transformers', 'tokenizers', 'databento', "
            "'databento_dbn'} & set(sys.modules))",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_protocol_preserves_priors_and_never_grants_trading_or_qwen_authority():
    protocol = d.protocol()
    assert protocol["models"] == {"natural_cross_entropy": 0.0, "natural_direction_penalty": 1.0}
    assert "natural frequencies" in protocol["fit"]
    assert "argmax" in protocol["decisions"]
    assert "NOT ticks" in protocol["penalty_units"]
    assert all(protocol[k] is False for k in d.FLAGS)
    assert d.balance.protocol()["cpu_controls"]["modes"] == {
        "joint_linear_unweighted": 0.0,
        "joint_linear_inverse_sqrt": 0.5,
    }


def test_penalty_matrix_orientation_and_three_cost_average():
    costs = d.cost_matrix()
    assert costs.shape == (7, 7)
    np.testing.assert_array_equal(np.diag(costs), np.zeros(7))
    assert costs[0, 3] == 4  # NNN truth, LLL call.
    assert costs[3, 0] == 1  # LLL truth, NNN call.
    assert costs[3, 6] == 6  # LLL truth, SSS call.
    assert costs[1, 3] == 8 / 3  # LNN -> LLL creates two extra false calls.
    assert costs[3, 1] == 2 / 3  # LLL -> LNN misses two opportunities.
    assert np.all(costs >= 0)


@pytest.mark.parametrize("strength", [0.0, 1.0])
def test_exact_objective_gradient_matches_central_difference(strength):
    logits = np.random.default_rng(42).normal(size=(4, 7))
    targets = np.array([0, 1, 4, 6])
    loss, gradient = d.objective(logits, targets, strength)
    np.testing.assert_allclose(gradient.sum(axis=1), 0, atol=1e-15)
    numerical = np.empty_like(logits)
    for index in np.ndindex(logits.shape):
        plus, minus = logits.copy(), logits.copy()
        plus[index] += 1e-6
        minus[index] -= 1e-6
        numerical[index] = (
            d.objective(plus, targets, strength)[0]["objective_without_l2"]
            - d.objective(minus, targets, strength)[0]["objective_without_l2"]
        ) / 2e-6
    np.testing.assert_allclose(gradient, numerical, atol=1e-9, rtol=1e-7)
    assert loss["objective_without_l2"] == (
        loss["cross_entropy"] + strength * loss["expected_class_penalty"]
    )


def test_penalty_increases_gradient_against_false_direction_without_resampling():
    logits = np.zeros((1, 7))
    plain, gradient = d.objective(logits, [0], 0.0)
    penalized, cost_gradient = d.objective(logits, [0], 1.0)
    assert penalized["cross_entropy"] == plain["cross_entropy"]
    assert penalized["objective_without_l2"] > plain["objective_without_l2"]
    assert cost_gradient[0, 3] > gradient[0, 3]
    assert cost_gradient[0, 0] < gradient[0, 0]


def test_stable_loss_keeps_extreme_wrong_class_finite_and_shift_invariant():
    logits = np.array([[1000.0, -1000.0, -1000.0, -1000.0, -1000.0, -1000.0, -1000.0]])
    loss, gradient = d.objective(logits, [6], 1.0)
    assert loss["cross_entropy"] == 2000
    assert loss["expected_class_penalty"] == 1
    assert np.isfinite(gradient).all()
    shifted, same_gradient = d.objective(logits + 123, [6], 1.0)
    assert shifted == loss
    np.testing.assert_array_equal(gradient, same_gradient)


@pytest.mark.parametrize("targets", [[True], [1.0], [-1], [7], [[1]], [1, 2], ["1"]])
def test_invalid_objective_labels_refused(targets):
    with pytest.raises(ValueError):
        d.objective(np.zeros((1, 7)), targets, 1.0)


@pytest.mark.parametrize("strength", [True, 1, 0.5, "1.0", float("nan")])
def test_nonregistered_strength_refused(samples, strength):
    with pytest.raises(ValueError):
        d.objective(np.zeros((1, 7)), [0], strength)
    with pytest.raises(ValueError):
        d.fit(samples, strength)


def test_logit_shape_and_nonfinite_values_refused():
    for logits in (np.zeros((1, 6)), np.full((1, 7), np.inf), np.zeros(7)):
        with pytest.raises(ValueError):
            d.objective(logits, [0], 1.0)


def test_sparse_training_snapshots_cannot_supply_short_context(samples):
    value = d.context_audit(samples)
    assert value["rows"] == 448 and value["source_sessions"] == 8
    assert value["minimum_spacing_seconds"] == 60
    assert value["same_session_intervals"] == 440
    assert value["gap_resets"] == 440
    assert value["rows_with_prior_timestamp_upper_bound"] == {"5": 0, "15": 0, "30": 0}


def test_context_audit_reads_only_identity_and_role_not_prompt_or_targets(samples):
    allowed = {"role", "source_session", "contract", "decision_ts_ns"}

    class IdentityOnly(dict):
        def __getitem__(self, key):
            assert key in allowed, "Context accessed features or future labels"
            return super().__getitem__(key)

    assert d.context_audit([IdentityOnly(row) for row in samples]) == d.context_audit(samples)


def test_context_inclusive_lower_boundary_and_session_gap_resets(samples):
    rows = [copy.deepcopy(samples[i]) for i in range(4)]
    start = rows[0]["decision_ts_ns"]
    for row, seconds in zip(rows, [0, 5, 6, 12], strict=True):
        row["decision_ts_ns"] = start + seconds * d.task.SECOND
    value = d.context_audit(rows)
    assert value["rows_with_prior_timestamp_upper_bound"] == {"5": 2, "15": 2, "30": 2}
    assert value["gap_resets"] == 1
    assert d.context_audit([samples[0], samples[56]])["same_session_intervals"] == 0
    assert (
        d.context_audit([samples[0], samples[56]])["rows_with_prior_timestamp_upper_bound"]["30"]
        == 0
    )


def test_nontrain_role_is_refused_before_poison_payload_access():
    class Poison(dict):
        def __getitem__(self, key):
            assert key == "role", "Payload touched before role refusal"
            return "validation_development"

    for action in (d.context_audit, lambda rows: d.fit(rows, 1.0)):
        with pytest.raises(ValueError):
            action([Poison()])


@pytest.mark.parametrize("change", ["reserved", "date_role", "contract", "duplicate", "regression"])
def test_context_invalid_provenance_or_chronology_refused(samples, change):
    rows = copy.deepcopy(samples[:2])
    if change == "reserved":
        rows[0]["source_session"] = "2026-04-07"
    elif change == "date_role":
        rows[0]["source_session"] = "2025-10-07"
    elif change == "contract":
        rows[0]["contract"] = "6EZ5"
    elif change == "duplicate":
        rows[1]["decision_ts_ns"] = rows[0]["decision_ts_ns"]
    else:
        rows.reverse()
    with pytest.raises(ValueError):
        d.context_audit(rows)


def test_zero_strength_matches_original_natural_control_and_fit_only_scaler(samples):
    split = d.balance.session_split(samples)
    rows = [r for r in samples if r["source_session"] in split["fit"]]
    model = d.fit(rows, 0.0)
    old = d.balance.fit(rows, 0.0)
    for key in ("means", "scales", "weights", "bias"):
        np.testing.assert_allclose(model[key], old[key], atol=1e-14, rtol=1e-13)
    risk = d.fit(rows, 1.0)
    assert model["means"] == risk["means"] and model["scales"] == risk["scales"]
    assert model["weights"] != risk["weights"]
    before = digest(risk)
    p = d.predict(risk, [d.balance.feature_values(r) for r in rows])
    assert p.shape == (336, 7) and np.allclose(p.sum(axis=1), 1)
    assert digest(risk) == before


@pytest.mark.parametrize("change", ["shape", "scale", "nonfinite", "strength", "authority"])
def test_invalid_model_parameters_refused(samples, change):
    model = d.fit(samples, 1.0)
    if change == "shape":
        model["weights"].pop()
    elif change == "scale":
        model["scales"][0] = 0
    elif change == "nonfinite":
        model["bias"][0] = float("nan")
    elif change == "strength":
        model["strength"] = True
    else:
        model["execution_allowed"] = True
    with pytest.raises(ValueError):
        d.predict(model, [d.balance.feature_values(samples[0])])


def test_deadline_and_missing_class_fail_without_partial_fit(samples):
    with pytest.raises(TimeoutError):
        d.fit(samples, 1.0, deadline=0.0)
    with pytest.raises(ValueError, match="Every joint"):
        d.fit([r for r in samples if d.balance.state_of(r) != "SSS"], 1.0)


def test_error_penalties_reconcile_confusions_without_hiding_abstention(samples):
    idle = d.scores(samples, np.tile(np.eye(7)[0], (len(samples), 1)))
    cost = idle["class_penalty"]["by_cost"]["extra_1_tick"]
    assert cost["missed_opportunity"] == 384 and cost["incorrect_directional_calls"] == 0
    assert idle["by_cost"]["extra_1_tick"]["directional_precision"] is None
    always_long = d.scores(samples, np.tile(np.eye(7)[3], (len(samples), 1)))
    cost = always_long["class_penalty"]["by_cost"]["extra_1_tick"]
    assert cost["no_opportunity_overcall"] == 64 and cost["wrong_side"] == 192
    assert cost["incorrect_directional_calls"] == 256 and cost["missed_opportunity"] == 0
    penalty = always_long["class_penalty"]
    assert penalty["mean_argmax_penalty"] == pytest.approx(
        sum(v["mean_class_penalty"] for v in penalty["by_cost"].values()) / 3
    )
    assert penalty["mean_expected_penalty"] == penalty["mean_argmax_penalty"]


def test_freeze_and_run_open_only_train_and_reservation_metadata(balance_frozen, monkeypatch):
    path, prior_pin, _ = balance_frozen
    original_open = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name not in {
            "validation_development.jsonl",
            "test_development.jsonl",
            "unavailable.jsonl",
        }
        assert path.suffix not in {".dbn", ".zip"}
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    output = path.parent / "safe-plan.json"
    value = d.freeze(path, prior_pin, output)
    assert value["partitions"]["fit"]["examples"] == 336
    assert value["partitions"]["check"]["examples"] == 112
    result = d.run(output, pin(output), path.parent / "safe-run", enable_cpu_study=True)
    assert result["models_quarantined"] and not result["reserved_outcomes_opened"]


@pytest.mark.parametrize(
    "change", ["source", "protocol", "runtime", "authority", "split", "context", "cases"]
)
def test_registration_tampering_refused(frozen, change):
    path, _, value = frozen
    bad = copy.deepcopy(value)
    if change == "source":
        bad["source_sha256"] = "0" * 64
    elif change == "protocol":
        bad["protocol"]["class_penalties"]["wrong_side"] = 0
    elif change == "runtime":
        bad["cpu_runtime"]["numpy"] = "different"
    elif change == "authority":
        bad["trading_enabled"] = True
    elif change == "split":
        bad["session_split"]["fit"].append(bad["session_split"]["check"][0])
    elif change == "context":
        bad["partitions"]["fit"]["context"]["gap_resets"] -= 1
    else:
        bad["partitions"]["check"]["ordered_cases_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        d.registration(path, write(path, bad))


def test_explicit_opt_in_before_input_access_and_output_overlap_refusal(frozen, tmp_path):
    with pytest.raises(ValueError, match="opt-in"):
        d.run(tmp_path / "absent", "invalid", tmp_path / "unused")
    assert not (tmp_path / "unused").exists()
    path, study_pin, plan = frozen
    with pytest.raises(ValueError):
        d.run(path, study_pin, Path(plan["dataset"]["directory"]) / "bad", enable_cpu_study=True)


def test_run_fits_only_whole_inner_fit_and_reconciles_frozen_artifacts(frozen, monkeypatch):
    path, study_pin, plan = frozen
    output = path.parent / "study"
    original_fit, calls = d.fit, []

    def guarded(rows, strength, **kwargs):
        days = {row["source_session"] for row in rows}
        assert days == set(plan["session_split"]["fit"])
        assert days.isdisjoint(plan["session_split"]["check"])
        calls.append(strength)
        return original_fit(rows, strength, **kwargs)

    monkeypatch.setattr(d, "fit", guarded)
    result = d.run(path, study_pin, output, enable_cpu_study=True)
    assert calls == [0.0, 1.0] and result["cpu_controls_fitted"] == 2
    assert result["fit_examples"] == 336 and result["check_examples"] == 112
    assert set(result["per_session_scores"]) == set(plan["session_split"]["check"])
    assert set(result["scores"]) == {*d.MODES, "no_opportunity", "inner_fit_joint_prior"}
    assert result["winner_selected"] is False
    assert all(result[key] is False for key in d.FLAGS)
    assert result == json.loads((output / "run.json").read_text())
    assert result["models_content_sha256"] == digest(
        json.loads((output / "models.json").read_text())
    )
    assert result["models_file"]["sha256"] == pin(output / "models.json")
    assert pin(path) == study_pin and d.registration(path, study_pin)[0] == plan
    with pytest.raises(FileExistsError):
        d.run(path, study_pin, output, enable_cpu_study=True)


@pytest.mark.parametrize("failure", ["second_fit", "final_input", "mutated_model"])
def test_failed_study_retains_failure_without_successful_subset(frozen, monkeypatch, failure):
    path, study_pin, _ = frozen
    output = path.parent / "failed"
    if failure == "second_fit":
        original_fit = d.fit

        def fail(rows, strength, **kwargs):
            if strength == 1.0:
                raise TimeoutError("private error text should not persist")
            return original_fit(rows, strength, **kwargs)

        monkeypatch.setattr(d, "fit", fail)
    elif failure == "final_input":
        original_registration, calls = d.registration, []

        def drift(*args):
            calls.append(1)
            if len(calls) == 2:
                raise ValueError("private input changed")
            return original_registration(*args)

        monkeypatch.setattr(d, "registration", drift)
    else:
        original_predict = d.predict

        def mutate(model, features):
            p = original_predict(model, features)
            model["bias"][0] += 1
            return p

        monkeypatch.setattr(d, "predict", mutate)
    with pytest.raises((TimeoutError, ValueError)):
        d.run(path, study_pin, output, enable_cpu_study=True)
    assert not (output / "run.json").exists()
    assert (output / "failure.json").exists()
    assert "private" not in (output / "failure.json").read_text()
