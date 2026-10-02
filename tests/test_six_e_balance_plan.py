"""Synthetic train-only imbalance plans and CPU controls; no market/native model calls."""

import copy
import json
import subprocess
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest
from test_six_e_forecast import observation
from test_six_e_forecast_eval import candidate as candidate
from test_six_e_forecast_eval import trial_request as trial_request
from test_six_e_lora_trial import encoder, fake_result, pin, write
from test_six_e_lora_trial import gpu_request as gpu_request

from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.training import prepare_6e_qwen_data as builder
from ai_trader.training import six_e_balance_plan as b


@pytest.fixture
def samples():
    result = []
    for day in range(8):
        session = (date(2025, 4, 7) + timedelta(days=day)).isoformat()
        for repeat in range(8):
            for state, move in enumerate((0, 3, 4, 6, -3, -4, -6)):
                source = observation(day=session, offset=(repeat * 7 + state) * 60, move=move)
                source["features"]["log_bid_qty"] = float(state)
                row, status = builder.example(source, "train")
                assert status == "supervised"
                assert b.state_of(row) == b.STATES[state]
                result.append(row)
    return result


@pytest.fixture
def original(candidate, samples):
    directory, _, _ = candidate
    request = json.loads((directory / "request.json").read_text())
    dataset = Path(request["dataset"])
    train = dataset / "train.jsonl"
    train.write_text("".join(canonical(row) + "\n" for row in samples), encoding="utf-8")
    receipt = json.loads((dataset / "completion.json").read_text())
    receipt["files"][train.name] = {
        "count": len(samples),
        "bytes": train.stat().st_size,
        "sha256": pin(train),
    }
    receipt["by_role"]["train"]["supervised"] = len(samples)
    request["dataset_sha256"] = write(dataset / "completion.json", receipt)
    token = json.loads(Path(request["token_preflight"]).read_text())
    token["dataset_completion_sha256"] = request["dataset_sha256"]
    token["by_role"]["train"]["examples"] = len(samples)
    request["token_preflight_sha256"] = write(Path(request["token_preflight"]), token)
    reservation = json.loads(Path(request["reservation"]).read_text())
    reservation["dataset_completion_sha256"] = request["dataset_sha256"]
    request["reservation_sha256"] = write(Path(request["reservation"]), reservation)
    selected = b.trial.selected_examples(request, receipt)
    request["selection"], _ = b.trial.encode_selection(request, selected, encoder)
    directory = directory.parent / "balance-original-trial"
    directory.mkdir()
    request["output_dir"] = str(directory)
    request_pin = write(directory / "request.json", request)
    report = {
        "status": "completed_20_update_market_trial_not_validated",
        "adapter_quarantined": True,
        "full_training_epoch": False,
        "result": fake_result(request),
        **b.trial.NO_AUTHORITY,
    }
    return directory, request_pin, write(directory / "run.json", report)


@pytest.fixture
def frozen(original):
    directory, request_pin, report_pin = original
    path = directory.parent / "balance-plan.json"
    value = b.freeze(directory, request_pin, report_pin, path)
    return path, pin(path), value


def test_import_does_not_load_native_models_or_dbn():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; from ai_trader.training import six_e_balance_plan; "
            "assert not ({'torch', 'peft', 'transformers', 'tokenizers', "
            "'databento', 'databento_dbn'} & set(sys.modules))",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_protocol_is_planning_only_and_old_twenty_profile_unchanged():
    value = b.protocol()
    assert all(value[key] is False for key in b.FLAGS)
    recipe = value["qwen_curriculum"]["recipe"]
    assert recipe["max_optimizer_steps"] == 224
    assert recipe["max_wall_time_seconds"] == 1800
    assert recipe["limits_enforced_by_training_worker"] is False
    assert value["qwen_curriculum"]["native_runner_implemented"] is False
    assert b.trial.profile()["max_optimizer_steps"] == 20
    for state in b.STATES:
        assert b.task.parse_completion(canonical(b.forecast(state))) == b.forecast(state)
    with pytest.raises(ValueError):
        b.forecast("NLL")


def test_whole_session_split_and_balanced_unique_fit_curriculum(samples):
    split = b.session_split(samples)
    assert len(split["fit"]) == 6 and len(split["check"]) == 2
    assert set(split["fit"]).isdisjoint(split["check"])
    selected = b.curriculum(samples, split)
    assert len(selected) == len({r["case_id"] for r in selected}) == 224
    assert Counter(r["joint_state"] for r in selected) == dict.fromkeys(b.STATES, 32)
    assert all(r["source_session"] in split["fit"] for r in selected)
    assert [r["joint_state"] for r in selected[:7]] == list(b.STATES)
    assert selected == b.curriculum(samples, split)
    for spec in selected:
        row = samples[spec["example_index"]]
        assert row["case_id"] == spec["case_id"] and b.state_of(row) == spec["joint_state"]


def test_rank_sampler_spreads_single_cases_across_all_supported_dates(samples):
    rows = []
    for i in range(40):
        session = (date(2025, 4, 7) + timedelta(days=i)).isoformat()
        for offset, move in enumerate((0, 3, 4, 6, -3, -4, -6)):
            rows.append(
                builder.example(observation(day=session, offset=offset * 60, move=move), "train")[0]
            )
    # Forty sessions leave only thirty fit sessions and cannot supply thirty-two per state.
    with pytest.raises(ValueError, match="thirty-two"):
        b.curriculum(rows, b.session_split(rows))
    # Replicated timestamps are prohibited instead of silently oversampled.
    with pytest.raises(ValueError, match="chronological"):
        b.curriculum(samples + samples, b.session_split(samples))


@pytest.mark.parametrize("count,quota", [(0, 1), (5, 0), (5, 6), (True, 1), (5, True), (5.0, 2)])
def test_invalid_rank_counts_refused(count, quota):
    with pytest.raises(ValueError):
        b.even_indices(count, quota)


def test_rank_selection_includes_endpoints_and_has_no_duplicates():
    assert b.even_indices(100, 1) == [49]
    assert b.even_indices(112, 32)[::31] == [0, 111]
    assert len(set(b.even_indices(112, 32))) == 32


def test_large_session_pool_spreads_each_state_without_cherry_picking():
    rows = []
    for day in range(80):
        session = (date(2025, 4, 7) + timedelta(days=day)).isoformat()
        for offset, move in enumerate((0, 3, 4, 6, -3, -4, -6)):
            rows.append(
                builder.example(observation(day=session, offset=offset * 60, move=move), "train")[0]
            )
    split = b.session_split(rows)
    selected = b.curriculum(rows, split)
    expected = [split["fit"][i] for i in b.even_indices(60, 32)]
    for state in b.STATES:
        assert [r["source_session"] for r in selected if r["joint_state"] == state] == expected


def test_gate_refuses_nontrain_before_poison_access():
    class Poison(dict):
        def __getitem__(self, key):
            if key != "role":
                pytest.fail("Accessed poison before training role gate")
            return "test_development"

    with pytest.raises(ValueError):
        b.fit([Poison()], 0.0)


def test_prediction_input_does_not_access_targets_or_metadata(samples):
    row = samples[0]

    class FeaturesOnly(dict):
        def __getitem__(self, key):
            if key != "prompt":
                pytest.fail("Prediction accessed target or metadata")
            return row["prompt"]

    assert b.feature_values(FeaturesOnly()) == b.feature_values(row)


def test_feature_prompt_refuses_extra_or_invalid_features(samples):
    bad = copy.deepcopy(samples[0])
    bad["prompt"] += " future price"
    with pytest.raises(ValueError):
        b.feature_values(bad)


def test_insufficient_sessions_or_state_support_refused(samples):
    first_day = samples[:56]
    with pytest.raises(ValueError, match="eight"):
        b.session_split(first_day)
    missing = [r for r in samples if b.state_of(r) != "SSS"]
    with pytest.raises(ValueError, match="thirty-two"):
        b.curriculum(missing, b.session_split(missing))
    with pytest.raises(ValueError, match="Every joint"):
        b.fit(missing, 0.0)


def test_training_audit_accounts_every_state_and_cost(samples):
    value = b.audit(samples)
    assert value["examples"] == 448
    assert value["joint_counts"] == dict.fromkeys(b.STATES, 64)
    assert value["joint_session_support"] == dict.fromkeys(b.STATES, 8)
    assert value["by_cost"]["extra_1_tick"] == {
        "long_positive": 192,
        "short_positive": 192,
        "neither_positive": 64,
    }
    assert value["by_cost"]["extra_4_ticks"]["neither_positive"] == 320


@pytest.mark.parametrize("power", [0, True, 1.0, "0.5", float("nan")])
def test_only_fixed_weight_controls_accepted(samples, power):
    with pytest.raises(ValueError):
        b.fit(samples, power)


def test_models_use_fit_only_statistics_and_remain_immutable(samples):
    split = b.session_split(samples)
    fit_rows = [r for r in samples if r["source_session"] in split["fit"]]
    model = b.fit(fit_rows, 0.0)
    expected = np.asarray([b.feature_values(r) for r in fit_rows], dtype=float)
    np.testing.assert_array_equal(model["means"], expected.mean(axis=0))
    assert np.isfinite(model["scales"]).all() and min(model["scales"]) > 0
    before = digest(model)
    p = b.predict(model, np.full((10, 37), 10000.0))
    assert p.shape == (10, 7) and np.allclose(p.sum(axis=1), 1)
    assert digest(model) == before
    assert b.fit(fit_rows, 0.0) == model


@pytest.mark.parametrize("mutation", ["shape", "nonfinite", "scale", "power", "extra"])
def test_model_or_feature_tampering_refused(samples, mutation):
    model = b.fit(samples, 0.0)
    if mutation == "shape":
        model["weights"].pop()
    elif mutation == "nonfinite":
        model["bias"][0] = float("inf")
    elif mutation == "scale":
        model["scales"][0] = 0.0
    elif mutation == "power":
        model["weight_power"] = True
    else:
        model["execution_allowed"] = True
    with pytest.raises(ValueError):
        b.predict(model, [b.feature_values(samples[0])])


def test_weighted_control_changes_parameters_without_changing_scaler(samples):
    imbalanced = [
        r for r in samples if b.state_of(r) == "NNN" or r["source_session"] < "2025-04-09"
    ]
    plain, weighted = (b.fit(imbalanced, power) for power in (0.0, 0.5))
    assert plain["means"] == weighted["means"] and plain["scales"] == weighted["scales"]
    assert plain["bias"] != weighted["bias"]


def test_deadline_refuses_partial_fit(samples):
    with pytest.raises(TimeoutError):
        b.fit(samples, 0.0, deadline=0.0)


def test_scores_keep_directional_misses_and_consistent_costs(samples):
    p = np.tile(np.eye(7)[0], (len(samples), 1))
    scores = b.scores(samples, p)
    assert scores["by_cost"]["extra_1_tick"]["directional_recall"] == 0
    assert scores["by_cost"]["extra_1_tick"]["correct"] == 64
    assert scores["by_cost"]["extra_4_ticks"]["correct"] == 320
    assert scores["coverage"] == 1
    assert scores["joint_log_loss"] > 0 and scores["joint_brier_score"] > 0
    with pytest.raises(ValueError):
        b.scores(samples, p[:, :3])


def test_freeze_reads_only_train_and_protected_metadata(original, monkeypatch):
    directory, request_pin, report_pin = original
    old = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name not in {
            "validation_development.jsonl",
            "test_development.jsonl",
            "unavailable.jsonl",
        }
        assert path.suffix not in {".dbn", ".zip"}
        return old(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    output = directory.parent / "train-only.json"
    value = b.freeze(directory, request_pin, report_pin, output)
    assert value["audits"]["all_train"]["examples"] == 448
    assert value["audits"]["original_twenty"]["examples"] == 20
    assert len(value["curriculum"]) == 224
    report = b.run(
        output, pin(output), directory.parent / "train-only-controls", enable_cpu_controls=True
    )
    assert report["reserved_outcomes_opened"] is False
    with pytest.raises(FileExistsError):
        b.freeze(directory, request_pin, report_pin, output)


@pytest.mark.parametrize(
    "change", ["source", "protocol", "authority", "runtime", "split", "audit", "selection"]
)
def test_registration_tampering_refused(frozen, change):
    path, _, value = frozen
    bad = copy.deepcopy(value)
    if change == "source":
        bad["source_sha256"] = "0" * 64
    elif change == "protocol":
        bad["protocol"]["cpu_controls"]["epochs"] += 1
    elif change == "authority":
        bad["qwen_training_authorized"] = True
    elif change == "runtime":
        bad["cpu_runtime"]["numpy"] = "different"
    elif change == "split":
        bad["session_split"]["fit"].append(bad["session_split"]["check"][0])
    elif change == "audit":
        bad["audits"]["inner_fit"]["joint_counts"]["NNN"] += 1
    else:
        bad["curriculum"][0] = bad["curriculum"][1]
    with pytest.raises(ValueError):
        b.registration(path, write(path, bad))


def test_changed_training_bytes_prevent_plan_completion(original):
    directory, request_pin, report_pin = original
    request = json.loads((directory / "request.json").read_text())
    train = Path(request["dataset"]) / "train.jsonl"
    train.write_bytes(train.read_bytes() + b"\n")
    output = directory.parent / "refused.json"
    with pytest.raises(ValueError):
        b.freeze(directory, request_pin, report_pin, output)
    assert not output.exists()


def test_refuses_outputs_inside_original_inputs(original):
    directory, request_pin, report_pin = original
    with pytest.raises(ValueError):
        b.freeze(directory, request_pin, report_pin, directory / "bad.json")


def test_run_opt_in_is_checked_before_any_input_access(tmp_path):
    with pytest.raises(ValueError, match="opt-in"):
        b.run(tmp_path / "absent", "bad", tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_complete_cpu_run_is_quarantined_and_does_not_change_inputs(frozen):
    path, frozen_pin, plan = frozen
    output = path.parent / "cpu-run"
    report = b.run(path, frozen_pin, output, enable_cpu_controls=True)
    assert report["cpu_controls_fitted"] == 2
    assert report["fit_examples"] == 336 and report["check_examples"] == 112
    assert report["fit_sessions"] == 6 and report["check_sessions"] == 2
    assert report["models_quarantined"] is True
    assert all(report[key] is False for key in b.FLAGS)
    assert set(report["scores"]) == {"no_opportunity", "inner_fit_joint_prior", *b.MODES}
    assert set(report["per_session_scores"]) == set(plan["session_split"]["check"])
    assert report == json.loads((output / "run.json").read_text())
    models = json.loads((output / "models.json").read_text())
    assert digest(models) == report["model_content_sha256"]
    assert pin(path) == frozen_pin
    assert b.registration(path, frozen_pin)[0] == plan
    with pytest.raises(FileExistsError):
        b.run(path, frozen_pin, output, enable_cpu_controls=True)


def test_failure_after_first_control_has_no_successful_subset_scores(frozen, monkeypatch):
    path, frozen_pin, _ = frozen
    output = path.parent / "failed-run"
    original_fit, calls = b.fit, []

    def fail_second(rows, power, **kwargs):
        calls.append(power)
        if len(calls) == 2:
            raise TimeoutError("private native message must not persist")
        return original_fit(rows, power, **kwargs)

    monkeypatch.setattr(b, "fit", fail_second)
    with pytest.raises(TimeoutError):
        b.run(path, frozen_pin, output, enable_cpu_controls=True)
    assert calls == [0.0, 0.5]
    assert not (output / "run.json").exists() and not (output / "models.json").exists()
    failure = (output / "failure.json").read_text()
    assert "private" not in failure and "TimeoutError" in failure


def test_final_input_revalidation_refuses_completion(frozen, monkeypatch):
    path, frozen_pin, _ = frozen
    output = path.parent / "drifted"
    original_registration, calls = b.registration, []

    def drift(*args):
        calls.append(1)
        if len(calls) == 2:
            raise ValueError("Pinned training inputs changed")
        return original_registration(*args)

    monkeypatch.setattr(b, "registration", drift)
    with pytest.raises(ValueError):
        b.run(path, frozen_pin, output, enable_cpu_controls=True)
    assert (output / "failure.json").exists() and not (output / "run.json").exists()
