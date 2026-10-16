"""Synthetic research training only; no real datasets, models, services or orders."""

import json
import socket
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext

import numpy as np
import pytest
from test_event_training_data import setup as setup_fold
from test_event_training_data import tamper
from test_microstructure_campaign import shifted
from test_microstructure_data import rows_with_quote

from ai_trader.training import train_event_baseline as module
from ai_trader.training.event_training_data import EventPartition, load_event_split

D = Decimal


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Baseline attempted network access.")

    monkeypatch.setattr(socket, "create_connection", forbidden)


def config(**changes):
    return module.EventBaselineConfig(
        **(dict(epochs=30, learning_rate=D("0.1"), l2=D("0.001")) | changes)
    )


def partition(*, values=(-3, -2, -1, 1, 2, 3), labels=(-1, -1, -1, 1, 1, 1), session="synthetic"):
    rows = []
    for value in values:
        row = [D(0)] * len(module.FEATURE_NAMES)
        row[module.FEATURE_NAMES.index("rolling_cvd_btc")] = D(value)
        rows.append(tuple(row))
    return EventPartition(
        module.FEATURE_NAMES,
        (session,) * len(rows),
        tuple(f"example-{i}" for i in range(len(rows))),
        tuple(range(len(rows))),
        tuple(i + 10 for i in range(len(rows))),
        tuple(rows),
        tuple(labels),
        tuple(D(label) / 100 for label in labels),
    )


def setup(tmp_path, *, build=True, single_class=False, validation_up=True, **fold_settings):
    captures = [
        rows_with_quote(),
        shifted(rows_with_quote(bid="101.2", ask="101.21")),
        shifted(
            rows_with_quote(
                bid="101.2" if validation_up else "99", ask="101.21" if validation_up else "99.01"
            ),
            ms=2000,
        ),
    ]
    if single_class:
        captures[1] = shifted(rows_with_quote())
    args, record, manifest = setup_fold(
        tmp_path, captures=captures, build=build, training_session_count=2, **fold_settings
    )
    recipe_path = tmp_path / "recipe.json"
    recipe = module.register_event_baseline(
        registration_path=args["registration_path"],
        manifest_path=args["manifest_path"],
        output_path=recipe_path,
        config=config(),
    )
    return args | {
        "recipe_path": recipe_path,
        "output_path": tmp_path / "baseline.json",
        "enable_training": True,
    }, recipe


def test_small_numpy_model_learns_separable_synthetic_features_with_fixed_epochs():
    train = partition()
    model, fit = module._fit(train, config(epochs=100))
    probabilities = model.predict_probabilities(train)
    assert (probabilities.argmax(axis=1) - 1).tolist() == list(train.direction)
    np.testing.assert_allclose(probabilities.sum(axis=1), 1, atol=1e-12)
    assert fit["epochs_completed"] == 100
    assert fit["final_training_cross_entropy"] < fit["initial_training_cross_entropy"]
    assert fit["training_class_counts"] == [3, 0, 3]
    with pytest.raises(FrozenInstanceError):
        model.bias = (0.0, 0.0, 0.0)


def test_single_gradient_step_matches_hand_calculation():
    train = partition(values=(-1, 1), labels=(-1, 1))
    model, _ = module._fit(train, config(epochs=1, learning_rate=D("0.1"), l2=D(0)))
    i = module.FEATURE_NAMES.index("rolling_cvd_btc")
    np.testing.assert_allclose(model.weights[i], [-0.05, 0, 0.05], atol=1e-15)
    np.testing.assert_allclose(model.bias, [1 / 60, -1 / 30, 1 / 60], atol=1e-15)


def test_three_class_fit_can_represent_exact_breakeven():
    train = partition(values=(-2, -1, 0, 0, 1, 2), labels=(-1, -1, 0, 0, 1, 1))
    model, fit = module._fit(train, config(epochs=400, l2=D(0)))
    assert fit["training_class_counts"] == [2, 2, 2]
    assert (model.predict_probabilities(train).argmax(axis=1) - 1).tolist() == list(train.direction)


def test_train_only_medians_indicators_and_inactive_channels_ignore_unseen_values():
    train = partition(values=(-1, 0, 1), labels=(-1, -1, 1))
    feature = module.FEATURE_NAMES.index("ofi_btc")
    empty = module.FEATURE_NAMES.index("bid_replenishment_proxy_btc")
    rows = [list(r) for r in train.X]
    for row, value in zip(rows, (D(1), None, D(3)), strict=True):
        row[feature], row[empty] = value, None
    train = replace(train, X=tuple(tuple(r) for r in rows))
    model, _ = module._fit(train, config())
    assert model.medians[feature] == model.means[feature] == 2
    assert model.medians[empty] == 0
    assert model.active[feature] and model.active[feature + module.INPUT_COLUMNS]
    assert not model.active[empty] and not model.active[empty + module.INPUT_COLUMNS]
    validation_rows = [list(r) for r in train.X]
    for row in validation_rows:
        row[feature], row[empty] = D("1e80"), D("1e90")
    validation = replace(train, X=tuple(tuple(r) for r in validation_rows))
    transformed = model.transform(validation)
    assert np.all(transformed[:, feature] == module.STANDARDIZED_CLIP)
    assert np.all(transformed[:, empty] == 0)
    assert np.all(transformed[:, empty + module.INPUT_COLUMNS] == 0)
    assert model.medians[feature] == 2  # Predicting never refits statistics.


def test_repeated_fit_is_deterministic_and_does_not_modify_global_rng():
    before = np.random.get_state()
    model, result = module._fit(partition(), config())
    after = np.random.get_state()
    assert before[0] == after[0] and before[2:] == after[2:]
    np.testing.assert_array_equal(before[1], after[1])
    with localcontext() as context:
        context.prec = 7
        assert module._fit(partition(), config()) == (model, result)


def test_inference_never_needs_or_reads_future_labels_and_provenance():
    train = partition()
    model, _ = module._fit(train, config())
    unlabeled = replace(
        train, direction=(), net_return_fraction=(), known_at_ns=(), source_sessions=()
    )
    np.testing.assert_array_equal(
        model.predict_probabilities(unlabeled), model.predict_probabilities(train)
    )


def test_end_to_end_publication_reload_and_controls_use_only_training_counts(tmp_path):
    args, recipe = setup(tmp_path)
    original_inputs = {p: p.read_bytes() for p in tmp_path.iterdir()}
    result = module.train_registered_event_baseline(**args)
    assert result["status"] == "completed" and result["training_started"] is True
    assert result["recipe"] == recipe and result["fit"]["training_class_counts"] == [1, 0, 1]
    assert result["fit"]["epochs_completed"] == 30
    assert result["fold_verification"]["reserved_sources_opened"] == 0
    assert result["promotion_allowed"] is result["live_trading_available"] is False
    assert {p: p.read_bytes() for p in original_inputs} == original_inputs
    evaluation = result["validation"]["aggregate"]
    assert evaluation["train_majority"]["accuracy"] == 0  # Tie -> loss, not validation majority.
    assert evaluation["train_laplace_prior"]["log_loss"] == pytest.approx(-np.log(0.4))
    assert evaluation["uniform"]["log_loss"] == pytest.approx(np.log(3))
    assert len(result["validation"]["by_session"]) == len(result["validation"]["predictions"]) == 1
    model = module.load_event_baseline_model(
        args["output_path"], expected_sha256=module._hash(module._json(result))
    )
    fold = load_event_split(
        **{k: args[k] for k in ("registration_path", "manifest_path", "sources")}
    )
    np.testing.assert_array_equal(
        model.predict_probabilities(fold.validation)[0],
        result["validation"]["predictions"][0]["probabilities"],
    )
    assert not args["output_path"].with_suffix(".json.partial").exists()


def test_changed_validation_outcomes_cannot_change_weights_or_preprocessing(tmp_path):
    up, down = tmp_path / "up", tmp_path / "down"
    up.mkdir()
    down.mkdir()
    a, _ = setup(up, validation_up=True)
    b, _ = setup(down, validation_up=False)
    first = module.train_registered_event_baseline(**a)
    second = module.train_registered_event_baseline(**b)
    assert first["model"] == second["model"] and first["fit"] == second["fit"]
    assert (
        first["validation"]["aggregate"]["model"]["accuracy"]
        != second["validation"]["aggregate"]["model"]["accuracy"]
    )


@pytest.mark.parametrize("correct", [True, False])
def test_probability_metrics_and_reliability_bins_match_hand_calculation(correct):
    probabilities = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    if not correct:
        probabilities = probabilities[::-1]
    metrics = module._metrics(np.array([0, 2]), probabilities)
    assert metrics["accuracy"] == int(correct)
    assert metrics["brier_score"] == (0 if correct else 2)
    assert metrics["log_loss"] == pytest.approx(0 if correct else -np.log(module.LOG_FLOOR))
    assert metrics["top_label_ece"] == int(not correct)
    assert metrics["reliability_bins"][-1]["count"] == 2
    assert metrics["reliability_bins"][0]["accuracy"] is None
    assert metrics["missing_actual_classes"] == [0]


@pytest.mark.parametrize(
    "changes",
    [
        {"epochs": True},
        {"epochs": 0},
        {"epochs": 1001},
        {"epochs": 2.5},
        {"learning_rate": D(0)},
        {"learning_rate": D("NaN")},
        {"learning_rate": D("Infinity")},
        {"learning_rate": D("1.1")},
        {"learning_rate": 0.1},
        {"l2": D(-1)},
        {"l2": D("1.1")},
    ],
)
def test_invalid_optimizer_configuration_is_rejected(changes):
    with pytest.raises(ValueError):
        config(**changes)


@pytest.mark.parametrize("value", [D("NaN"), D("Infinity"), D("1e101"), "123", 1.25])
def test_bad_feature_values_cannot_reach_optimizer(value):
    train = partition()
    row = list(train.X[0])
    row[0] = value
    with pytest.raises(ValueError):
        module._fit(replace(train, X=(tuple(row), *train.X[1:])), config())


def test_feature_schema_and_target_types_are_checked():
    train = partition()
    with pytest.raises(ValueError, match="schema"):
        module._fit(replace(train, feature_names=train.feature_names[::-1]), config())
    with pytest.raises(ValueError, match="integer direction"):
        module._fit(replace(train, direction=(True, *train.direction[1:])), config())
    with pytest.raises(ValueError, match="two observed"):
        module._fit(replace(train, direction=(-1,) * len(train.X)), config())


def test_recipe_registration_does_not_require_captures_or_label_files(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Recipe registration attempted to load source rows.")

    monkeypatch.setattr(module, "load_event_split", forbidden)
    args, recipe = setup(tmp_path, build=False)
    assert args["recipe_path"].exists()
    assert not any(s.dataset_path.exists() for s in args["sources"])
    assert recipe["epoch_selection"] == "fixed_budget_no_validation_selection"


@pytest.mark.parametrize("enabled", [False, 1, "yes", None])
def test_training_requires_explicit_activation_before_any_file_access(
    tmp_path, monkeypatch, enabled
):
    args, _ = setup(tmp_path)
    monkeypatch.setattr(module, "load_registration", lambda *a: pytest.fail("Unexpected file IO"))
    with pytest.raises(ValueError, match="enable_training"):
        module.train_registered_event_baseline(**(args | {"enable_training": enabled}))
    assert not args["output_path"].exists()


@pytest.mark.parametrize("single_class", [True, False])
def test_quality_and_class_failures_publish_diagnostics_without_fitting(
    tmp_path, monkeypatch, single_class
):
    args, _ = setup(
        tmp_path, single_class=single_class, minimum_resolved_per_session=1 if single_class else 2
    )
    monkeypatch.setattr(module, "_fit", lambda *a: pytest.fail("Blocked run tried to fit"))
    result = module.train_registered_event_baseline(**args)
    assert result["status"] == (
        "blocked_training_classes" if single_class else "blocked_source_quality"
    )
    assert result["model"] is result["validation"] is None
    assert result["training_started"] is False
    with pytest.raises(ValueError, match="completed"):
        module.load_event_baseline_model(
            args["output_path"], expected_sha256=module._hash(module._json(result))
        )


@pytest.mark.parametrize("fault", ["recipe", "dataset", "scope", "drift"])
def test_invalid_provenance_or_drift_never_publishes_result(tmp_path, monkeypatch, fault):
    args, _ = setup(tmp_path)
    if fault == "recipe":
        tamper(
            args["recipe_path"], "manifest", lambda d: d.update(epoch_selection="best_validation")
        )
    elif fault == "dataset":
        tamper(
            args["sources"][0].dataset_path, "dataset", lambda d: d.update(training_started=True)
        )
    elif fault == "scope":
        args["sources"] = (
            args["sources"][0],
            replace(args["sources"][1], source_session="reserved"),
            args["sources"][2],
        )
    else:
        monkeypatch.setattr(
            module, "_check_current", lambda *a: (_ for _ in ()).throw(ValueError("drift"))
        )
    if fault != "drift":
        monkeypatch.setattr(module, "_fit", lambda *a: pytest.fail("Invalid scope reached fitting"))
    with pytest.raises(ValueError):
        module.train_registered_event_baseline(**args)
    assert not args["output_path"].exists()


def test_registration_and_runtime_compute_budgets_are_bounded(tmp_path, monkeypatch):
    args, _ = setup(tmp_path)
    monkeypatch.setattr(module, "MAX_ROW_EPOCHS", 1)
    with pytest.raises(ValueError, match="compute budget"):
        module.register_event_baseline(
            registration_path=args["registration_path"],
            manifest_path=args["manifest_path"],
            output_path=tmp_path / "new-recipe.json",
            config=config(),
        )
    with pytest.raises(ValueError, match="compute budget"):
        module._fit(partition(), config())


def test_retry_never_overwrites_and_result_cap_leaves_no_artifact(tmp_path, monkeypatch):
    args, _ = setup(tmp_path)
    monkeypatch.setattr(module, "MAX_RESULT_BYTES", 1)
    with pytest.raises(ValueError, match="byte budget"):
        module.train_registered_event_baseline(**args)
    assert not args["output_path"].exists()
    args["output_path"].write_bytes(b"existing result")
    monkeypatch.setattr(
        module, "load_registration", lambda *a: pytest.fail("Retry should stop before IO")
    )
    with pytest.raises(FileExistsError):
        module.train_registered_event_baseline(**args)
    assert args["output_path"].read_bytes() == b"existing result"


@pytest.mark.parametrize(
    "fault", ["checksum", "scales", "weights", "active", "schema", "result_schema"]
)
def test_safe_model_reload_rejects_changed_or_invalid_parameters(tmp_path, fault):
    args, _ = setup(tmp_path)
    result = module.train_registered_event_baseline(**args)
    original_hash = module._hash(module._json(result))

    def change(run):
        parameters = run["model"]["parameters"]
        if fault == "checksum":
            parameters["bias"][0] += 1
        elif fault == "scales":
            parameters["scales"][0] = 0.0
        elif fault == "weights":
            parameters["weights"].pop()
        elif fault == "active":
            parameters["active"][0] = 1
        elif fault == "result_schema":
            run["schema_version"] = True
        else:
            run["model"]["feature_names"].reverse()

    tamper(args["output_path"], "report", change)
    stored = json.loads(args["output_path"].read_bytes())
    expected = original_hash if fault == "checksum" else stored["report_sha256"]
    with pytest.raises(ValueError):
        module.load_event_baseline_model(args["output_path"], expected_sha256=expected)


def test_fresh_import_does_not_load_torch_or_a_model_provider():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import ai_trader.training.train_event_baseline; "
            "assert 'torch' not in sys.modules; assert 'transformers' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_cli_recipe_registration_is_metadata_only(tmp_path, monkeypatch, capsys):
    args, _ = setup(tmp_path, build=False)
    output = tmp_path / "another-recipe.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "baseline",
            "register",
            "--registration",
            str(args["registration_path"]),
            "--manifest",
            str(args["manifest_path"]),
            "--output",
            str(output),
            "--epochs",
            "30",
            "--learning-rate",
            "0.1",
            "--l2",
            "0.001",
        ],
    )
    module.main()
    report = json.loads(capsys.readouterr().out)
    assert report["training_started"] is False and output.exists()
    assert not any(s.dataset_path.exists() for s in args["sources"])


@pytest.mark.parametrize("single_class", [False, True])
def test_cli_training_reports_completed_or_blocked_without_printing_predictions(
    tmp_path, monkeypatch, capsys, single_class
):
    args, _ = setup(tmp_path, single_class=single_class)
    argv = [
        "baseline",
        "train",
        "--registration",
        str(args["registration_path"]),
        "--manifest",
        str(args["manifest_path"]),
        "--recipe",
        str(args["recipe_path"]),
        "--output",
        str(args["output_path"]),
        "--enable-training",
    ]
    for s in args["sources"]:
        argv += ["--source", s.source_session, str(s.capture_path), str(s.dataset_path)]
    monkeypatch.setattr(sys, "argv", argv)
    if single_class:
        with pytest.raises(SystemExit) as error:
            module.main()
        assert error.value.code == 2
    else:
        module.main()
    report = json.loads(capsys.readouterr().out)
    assert report["training_started"] is not single_class
    assert "predictions" not in report and report["promotion_allowed"] is False
