"""Synthetic-only, registered expanding-prefix event evaluations."""

import json
import socket
import sys
from dataclasses import replace
from decimal import Decimal

import numpy as np
import pytest
from test_event_training_data import setup as setup_fold
from test_event_training_data import tamper
from test_microstructure_campaign import shifted
from test_microstructure_data import rows_with_quote
from test_microstructure_policy import MS

from ai_trader.training import event_training_data as data_module
from ai_trader.training import event_walk_forward as module

D = Decimal


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("Network access"))


def captures_for(outcomes=(False, True, True, False)):
    return [
        shifted(
            rows_with_quote(bid="101.2" if up else "100", ask="101.21" if up else "100.01"),
            ms=i * 1000,
        )
        for i, up in enumerate(outcomes)
    ]


def two_resolved_rows():
    rows = rows_with_quote()
    footer = rows.pop()
    rows.append(
        {
            "schema_version": 1,
            "record_type": "stream_event",
            "stream": "btcusdt@depth@100ms",
            "received_at_ns": 1400 * MS,
            "event": {
                "e": "depthUpdate",
                "E": 1400,
                "s": "BTCUSDT",
                "U": 105,
                "u": 105,
                "b": [["100", "8"]],
                "a": [["100.01", "3"]],
            },
        }
    )
    footer.update(ended_at_ns=1500 * MS, depth_events=5)
    return [*rows, footer]


def setup(tmp_path, *, captures=None, build=True, initial=2, epochs=30, **settings):
    args, record, _ = setup_fold(
        tmp_path, captures=captures or captures_for(), build=build, **settings
    )
    config = module.EventBaselineConfig(epochs, D("0.1"), D("0.001"))
    plan_path = tmp_path / "walk-forward.json"
    registration_args = dict(
        registration_path=args["registration_path"],
        output_path=plan_path,
        config=config,
        initial_training_sessions=initial,
        **(
            dict(
                max_frames_per_session=100,
                embargo_ns=0,
                minimum_resolved_per_session=1,
                minimum_resolved_fraction=D("0.25"),
            )
            | settings
        ),
    )
    plan = module.register_event_walk_forward(**registration_args)
    return (
        dict(
            registration_path=args["registration_path"],
            plan_path=plan_path,
            sources=args["sources"],
            output_path=tmp_path / "walk-result.json",
            enable_training=True,
        ),
        plan,
        record,
        registration_args,
    )


def test_metadata_only_registration_freezes_all_folds_and_shared_recipe(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "_load_dataset", lambda *a, **k: pytest.fail("Data read"))
    args, plan, record, options = setup(tmp_path, build=False)
    assert not any(s.dataset_path.exists() for s in args["sources"])
    assert len(plan["folds"]) == 2 and plan["registration_sha256"] == record.sha256
    first, second = (f["manifest"] for f in plan["folds"])
    assert first["train_sessions"] == ["research-0", "research-1"]
    assert first["validation_sessions"] == ["research-2"]
    assert first["future_research_sessions"] == ["research-3"]
    assert second["train_sessions"] == ["research-0", "research-1", "research-2"]
    assert second["validation_sessions"] == ["research-3"]
    assert second["reserved_sessions"] == ["reserved"]
    assert plan["declared_training_row_epochs"] == 5 * 100 * 30
    assert all(f["recipe"]["configuration"] == plan["configuration"] for f in plan["folds"])
    before = args["plan_path"].read_bytes()
    with pytest.raises(FileExistsError):
        module.register_event_walk_forward(**options)
    assert args["plan_path"].read_bytes() == before
    first["feature_units"]["rolling_cvd_btc"] = "incorrect"
    assert second["feature_units"]["rolling_cvd_btc"] == "BTC"


def test_each_fold_fits_only_earlier_whole_sessions_and_restarts_model_fit(tmp_path, monkeypatch):
    args, plan, _, _ = setup(tmp_path)
    original, calls = module._fit, []

    def traced(train, config):
        calls.append((train.source_sessions, train.known_at_ns))
        return original(train, config)

    monkeypatch.setattr(module, "_fit", traced)
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    result = module.evaluate_registered_event_walk_forward(**args)
    assert result["status"] == "completed" and result["completed_folds"] == 2
    assert result["blocked_folds"] == result["reserved_sources_opened"] == 0
    assert [c[0] for c in calls] == [
        ("research-0", "research-1"),
        ("research-0", "research-1", "research-2"),
    ]
    assert result["sources"][0]["outcome_counts"] == {"excluded": 9, "resolved": 1, "censored": 2}
    ids = []
    for fold, declared, call in zip(result["folds"], plan["folds"], calls, strict=True):
        assert (
            fold["training_outcomes_available_by_ns"]
            == max(call[1])
            < declared["manifest"]["train_outcome_cutoff_ns"]
        )
        assert fold["validation_session"] not in fold["train_sessions"]
        assert fold["fit"]["epochs_completed"] == 30
        assert fold["model_sha256"] == module._hash(module._json(fold["model"]))
        ids += [r["example_id"] for r in fold["validation"]["predictions"]]
    assert len(ids) == len(set(ids)) == result["out_of_sample_rows_in_completed_folds"] == 2
    assert not result["promotion_allowed"] and not result["live_trading_available"]
    assert {p: p.read_bytes() for p in before} == before


def test_all_source_bytes_are_read_once_not_per_fold(tmp_path, monkeypatch):
    args, _, _, _ = setup(tmp_path)
    original, reads = data_module._read_bytes, []

    def traced(path, limit):
        reads.append(path)
        return original(path, limit)

    monkeypatch.setattr(data_module, "_read_bytes", traced)
    result = module.evaluate_registered_event_walk_forward(**args)
    inputs = [p for s in args["sources"] for p in (s.dataset_path, s.capture_path)]
    assert reads == [args["plan_path"], *inputs]
    assert result["verified_input_bytes"] == sum(p.stat().st_size for p in inputs)


@pytest.mark.parametrize("change_index", [2, 3])
def test_future_outcomes_do_not_change_prior_fits_but_can_train_later_folds(tmp_path, change_index):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    outcomes = [False, True, True, False]
    a, _, _, _ = setup(left, captures=captures_for(outcomes))
    outcomes[change_index] = not outcomes[change_index]
    b, _, _, _ = setup(right, captures=captures_for(outcomes))
    first = module.evaluate_registered_event_walk_forward(**a)
    changed = module.evaluate_registered_event_walk_forward(**b)
    assert first["folds"][0]["model"] == changed["folds"][0]["model"]
    assert (first["folds"][1]["model"] == changed["folds"][1]["model"]) is (change_index == 3)
    target_fold = change_index - 2
    assert (
        first["folds"][target_fold]["validation"]["predictions"][0]["actual_direction"]
        != changed["folds"][target_fold]["validation"]["predictions"][0]["actual_direction"]
    )


def test_pooled_metrics_use_concatenated_rows_not_unweighted_fold_averages(tmp_path):
    captures = captures_for()
    captures[3] = shifted(two_resolved_rows(), ms=3000)
    args, _, _, _ = setup(tmp_path, captures=captures)
    result = module.evaluate_registered_event_walk_forward(**args)
    folds = result["folds"]
    assert [f["validation"]["aggregate"]["model"]["total"] for f in folds] == [1, 2]
    actual, probabilities = [], []
    for fold in folds:
        for row in fold["validation"]["predictions"]:
            actual.append(row["actual_direction"] + 1)
            probabilities.append(row["probabilities"])
    expected = module._metrics(np.array(actual), np.array(probabilities))
    assert result["aggregate"]["model"] == json.loads(module._json(expected))
    for name in result["aggregate"]:
        losses = [f["validation"]["aggregate"][name]["log_loss"] for f in folds]
        assert result["aggregate"][name]["log_loss"] == pytest.approx(
            (losses[0] + 2 * losses[1]) / 3
        )
    losses = [f["validation"]["aggregate"]["model"]["log_loss"] for f in folds]
    assert result["aggregate"]["model"]["log_loss"] != pytest.approx(sum(losses) / 2)


@pytest.mark.parametrize("fault_index", [0, 2, 3])
def test_failed_source_remains_visible_and_blocks_affected_folds_without_pooled_subset(
    tmp_path, fault_index
):
    captures = captures_for()
    captures[fault_index] = shifted(
        rows_with_quote(timestamp=1200, gap=True), ms=fault_index * 1000
    )
    args, _, _, _ = setup(tmp_path, captures=captures)
    result = module.evaluate_registered_event_walk_forward(**args)
    assert result["status"] == "incomplete"
    assert result["aggregate"] is None and not result["pooled_metrics_available"]
    assert len(result["sources"]) == 4 and len(result["folds"]) == 2
    assert result["sources"][fault_index]["gate_failures"]
    assert result["completed_folds"] == (1 if fault_index == 3 else 0)
    for fold in result["folds"]:
        if fold["status"] != "completed":
            assert fold["blocked_sources"] == [f"research-{fault_index}"]
            assert fold["model"] is fold["validation"] is None


def test_single_class_early_fold_is_not_deleted_when_later_training_gets_second_class(tmp_path):
    args, _, _, _ = setup(tmp_path, captures=captures_for((False, False, True, True)))
    result = module.evaluate_registered_event_walk_forward(**args)
    first, second = result["folds"]
    assert first["status"] == "blocked_training_classes" and first["fit"]["epochs_completed"] == 0
    assert second["status"] == "completed" and second["fit"]["training_class_counts"] == [2, 0, 1]
    assert result["aggregate"] is None and result["training_started"] is True


@pytest.mark.parametrize(
    "settings",
    [
        {"initial": 0},
        {"initial": True},
        {"initial": 3},
        {"initial": 4},
        {"max_frames_per_session": 2501},
        {"minimum_resolved_per_session": 0},
        {"minimum_resolved_fraction": D("NaN")},
        {"embargo_ns": True},
    ],
)
def test_invalid_schedule_or_source_gates_never_publish_plan(tmp_path, settings):
    with pytest.raises(ValueError):
        setup(tmp_path, build=False, **settings)
    assert not (tmp_path / "walk-forward.json").exists()


def test_every_internal_evaluation_boundary_obeys_strict_embargo(tmp_path):
    captures = [shifted(rows_with_quote(), ms=offset) for offset in (0, 1000, 2000, 2501)]
    # Initial split boundaries have ample room, but evaluation 2 -> 3 has exactly 1 ms.
    with pytest.raises(ValueError, match="Walk-forward boundary"):
        setup(tmp_path, captures=captures, build=False, embargo_ns=MS)
    assert not (tmp_path / "walk-forward.json").exists()


def test_global_work_budget_counts_repeated_prefix_fits_not_only_last_fold(tmp_path, monkeypatch):
    args, _, _, options = setup(tmp_path, build=False)
    monkeypatch.setattr(module, "MAX_ROW_EPOCHS", 12000)  # Each fold <= 9000, total is 15000.
    with pytest.raises(ValueError, match="Aggregate.*compute budget"):
        module.register_event_walk_forward(
            **(options | {"output_path": tmp_path / "new-plan.json"})
        )
    assert not args["output_path"].exists() and not (tmp_path / "new-plan.json").exists()


@pytest.mark.parametrize(
    "fault", ["omit", "reorder", "duplicate", "reserved", "unknown", "mutable"]
)
def test_entire_source_scope_checked_before_any_data_read(tmp_path, monkeypatch, fault):
    args, _, _, _ = setup(tmp_path)
    sources = args["sources"]
    if fault == "omit":
        sources = sources[:-1]
    elif fault == "reorder":
        sources = sources[::-1]
    elif fault == "duplicate":
        sources = (*sources[:-1], sources[0])
    elif fault == "mutable":
        sources = list(sources)
    else:
        sources = (replace(sources[0], source_session=fault), *sources[1:])
    monkeypatch.setattr(
        module, "_load_dataset", lambda *a, **k: pytest.fail("Invalid scope reached data")
    )
    with pytest.raises(ValueError, match="every research source"):
        module.evaluate_registered_event_walk_forward(**(args | {"sources": sources}))
    assert not args["output_path"].exists()


@pytest.mark.parametrize(
    "fault",
    ["omit_fold", "train_on_future", "different_recipe", "aggregate_policy", "bad_decimal", "type"],
)
def test_rehashed_plan_tampering_rejected_before_source_read(tmp_path, monkeypatch, fault):
    args, _, _, _ = setup(tmp_path)

    def change(plan):
        if fault == "omit_fold":
            plan["folds"].pop()
        elif fault == "train_on_future":
            plan["folds"][0]["manifest"]["train_sessions"].append("research-3")
        elif fault == "different_recipe":
            plan["folds"][1]["recipe"]["configuration"]["epochs"] = 31
        elif fault == "aggregate_policy":
            plan["failure_policy"] = "skip_failed"
        elif fault == "bad_decimal":
            plan["source_settings"]["minimum_resolved_fraction"] = "invalid"
        else:
            plan["schema_version"] = True

    tamper(args["plan_path"], "manifest", change)
    monkeypatch.setattr(
        module, "_load_dataset", lambda *a, **k: pytest.fail("Invalid plan reached data")
    )
    with pytest.raises(ValueError):
        module.evaluate_registered_event_walk_forward(**args)
    assert not args["output_path"].exists()


@pytest.mark.parametrize("enabled", [False, 1, "yes", None])
def test_training_opt_in_precedes_all_input_access(tmp_path, monkeypatch, enabled):
    args, _, _, _ = setup(tmp_path)
    monkeypatch.setattr(
        module, "load_registration", lambda *a: pytest.fail("Unexpected input read")
    )
    with pytest.raises(ValueError, match="enable_training"):
        module.evaluate_registered_event_walk_forward(**(args | {"enable_training": enabled}))


def test_forged_dataset_or_outcome_time_never_reaches_training(tmp_path, monkeypatch):
    args, _, _, _ = setup(tmp_path)
    tamper(args["sources"][0].dataset_path, "dataset", lambda d: d.update(training_started=True))
    monkeypatch.setattr(module, "_fit", lambda *a: pytest.fail("Corrupt input reached fitting"))
    with pytest.raises(ValueError, match="source-reproduced"):
        module.evaluate_registered_event_walk_forward(**args)
    assert not args["output_path"].exists()


def test_availability_guards_are_independent_of_the_artifact_rebuilder(tmp_path, monkeypatch):
    args, _, _, _ = setup(tmp_path)
    original = module._load_dataset

    def late(*a, **k):
        dataset, size = original(*a, **k)
        dataset["examples"][0]["outcome"]["known_at_ns"] = dataset["source_ended_at_ns"] + 1
        return dataset, size

    monkeypatch.setattr(module, "_load_dataset", late)
    with pytest.raises(ValueError, match="source boundary"):
        module.evaluate_registered_event_walk_forward(**args)
    with pytest.raises(ValueError, match="embargo"):
        module._fold_partition({"s": [{"outcome": {"known_at_ns": 5}}]}, ["s"], 7, 2)


def test_repeat_run_reproduces_all_models_predictions_and_checksum(tmp_path):
    args, _, _, _ = setup(tmp_path)
    first = module.evaluate_registered_event_walk_forward(**args)
    other = tmp_path / "other-result.json"
    assert module.evaluate_registered_event_walk_forward(**(args | {"output_path": other})) == first
    assert other.read_bytes() == args["output_path"].read_bytes()
    envelope = json.loads(other.read_bytes())
    assert envelope["report_sha256"] == module._hash(module._json(first))
    with pytest.raises(FileExistsError):
        module.evaluate_registered_event_walk_forward(**args)


@pytest.mark.parametrize("fault", ["bytes", "result_size", "drift"])
def test_resource_limits_or_mid_run_drift_never_publish_success(tmp_path, monkeypatch, fault):
    args, _, _, _ = setup(tmp_path)
    if fault == "bytes":
        size = sum(
            p.stat().st_size for s in args["sources"][:1] for p in (s.capture_path, s.dataset_path)
        )
        monkeypatch.setattr(module, "MAX_INPUT_BYTES", size + 1)
    elif fault == "result_size":
        monkeypatch.setattr(module, "MAX_RESULT_BYTES", 1)
    else:
        original = module._fit

        def changed(*a):
            result = original(*a)
            monkeypatch.setattr(
                module, "_check_current", lambda *a: (_ for _ in ()).throw(ValueError("drift"))
            )
            return result

        monkeypatch.setattr(module, "_fit", changed)
    with pytest.raises(ValueError):
        module.evaluate_registered_event_walk_forward(**args)
    assert not args["output_path"].exists()


@pytest.mark.parametrize("blocked", [False, True])
def test_cli_evaluation_compact_status_and_no_promotion(tmp_path, monkeypatch, capsys, blocked):
    args, _, _, _ = setup(tmp_path, minimum_resolved_per_session=2 if blocked else 1)
    argv = [
        "walk-forward",
        "evaluate",
        "--registration",
        str(args["registration_path"]),
        "--plan",
        str(args["plan_path"]),
        "--output",
        str(args["output_path"]),
        "--enable-training",
    ]
    for source in args["sources"]:
        argv += [
            "--source",
            source.source_session,
            str(source.capture_path),
            str(source.dataset_path),
        ]
    monkeypatch.setattr(sys, "argv", argv)
    if blocked:
        with pytest.raises(SystemExit) as error:
            module.main()
        assert error.value.code == 2
    else:
        module.main()
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == ("incomplete" if blocked else "completed")
    assert "predictions" not in report and report["promotion_allowed"] is False


def test_cli_registration_is_metadata_only(tmp_path, monkeypatch, capsys):
    args, _, _, _ = setup(tmp_path, build=False)
    output = tmp_path / "another-plan.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "walk-forward",
            "register",
            "--registration",
            str(args["registration_path"]),
            "--output",
            str(output),
            "--initial-training-sessions",
            "2",
            "--max-frames-per-session",
            "100",
            "--embargo-ns",
            "0",
            "--minimum-resolved-per-session",
            "1",
            "--minimum-resolved-fraction",
            "0.25",
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
    assert report["folds"] == 2 and report["training_started"] is False
    assert output.exists() and not any(s.dataset_path.exists() for s in args["sources"])
