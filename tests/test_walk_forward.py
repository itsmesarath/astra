"""Tests for source-session walk-forward validation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from ai_trader.features.kline_dataset import KLINE_FEATURE_COLUMNS
from ai_trader.trading.decision_policy import DecisionPolicy
from ai_trader.training import walk_forward
from ai_trader.training.model_data import KLINE_MODEL_FEATURE_NAMES
from ai_trader.training.train_linear import TrainingConfig
from ai_trader.training.walk_forward import (
    load_session_partitions,
    run_walk_forward,
    write_walk_forward_report,
)

FIELDNAMES = (
    "spread",
    "midpoint",
    "microprice",
    "bid_depth",
    "ask_depth",
    "book_imbalance",
    "total_base_volume",
    "trade_imbalance",
    "aggregate_trade_count",
    "underlying_trade_count",
    "target_direction",
    "source_session",
    "depth_event_time_ms",
    "future_event_time_ms",
)


def make_rows(session_names: tuple[str, ...]) -> list[dict[str, str]]:
    """Create balanced, linearly separable rows for each session."""
    rows = []
    for session_index, session in enumerate(session_names):
        for _ in range(4):
            for direction in (-1, 0, 1):
                event_time = session_index * 100_000 + (len(rows) % 12) * 2000
                rows.append(
                    {
                        "spread": "0.01",
                        "midpoint": "100",
                        "microprice": str(100 + direction * 0.01),
                        "bid_depth": str(10 + direction),
                        "ask_depth": str(10 - direction),
                        "book_imbalance": str(direction),
                        "total_base_volume": "5",
                        "trade_imbalance": str(direction),
                        "aggregate_trade_count": "2",
                        "underlying_trade_count": "3",
                        "target_direction": str(direction),
                        "source_session": session,
                        "depth_event_time_ms": str(event_time),
                        "future_event_time_ms": str(event_time + 999),
                    }
                )
    return rows


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    """Write a combined labeled-session fixture."""
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def test_runs_expanding_validation_and_reserves_final_session(tmp_path: Path) -> None:
    """Only intermediate sessions may contribute walk-forward metrics."""
    source_path = tmp_path / "combined.csv"
    output_path = tmp_path / "walk_forward.json"
    session_names = ("one", "two", "three", "four", "five", "held-out")
    write_rows(source_path, make_rows(session_names))
    config = TrainingConfig(
        max_epochs=80,
        patience=10,
        learning_rate=0.1,
        weight_decay=0,
        device="cpu",
    )
    policy = DecisionPolicy()

    report = run_walk_forward(
        source_path,
        config,
        minimum_training_sessions=2,
        held_out_session_count=1,
        policy=policy,
    )
    write_walk_forward_report(output_path, report, config, policy)

    assert report.total_sessions == 6
    assert report.evaluated_sessions == ("four", "five")
    assert report.held_out_sessions == ("held-out",)
    assert len(report.folds) == 2
    assert report.folds[0].training_sessions == ("one", "two")
    assert report.folds[1].training_sessions == ("one", "two", "three")
    assert report.folds[0].tuning_sessions == ("three",)
    assert report.folds[1].tuning_sessions == ("four",)
    assert report.folds[0].tuning_rows == 12
    for fold in report.folds:
        assert set(fold.training_sessions).isdisjoint(fold.tuning_sessions)
        assert fold.validation_session not in (*fold.training_sessions, *fold.tuning_sessions)
    assert report.aggregate_validation.total == 24
    assert report.aggregate_validation.macro_f1 == pytest.approx(1.0)
    assert report.aggregate_policy.rows == 24
    assert report.aggregate_policy.directional_precision == pytest.approx(1.0)

    with output_path.open(encoding="utf-8") as input_file:
        payload = json.load(input_file)

    assert payload["held_out_sessions"] == ["held-out"]
    assert payload["schema_version"] == 6
    assert payload["replay_feature_provenance"] is None
    assert payload["prediction_class_order"] == [-1, 0, 1]
    assert payload["candle_replay"] is None
    assert len(payload["folds"][0]["predictions"]["probabilities"]) == 12
    assert len(payload["source_sha256"]) == 64
    assert payload["embargo_ms"] == 0
    assert payload["session_metadata"][-1]["name"] == "held-out"
    assert payload["held_out_access"] == "csv_metadata_scanned_no_feature_or_outcome_conversion"
    assert payload["validation_fields_mean"] == "evaluation_only"
    assert payload["folds"][0]["tuning_sessions"] == ["three"]
    assert payload["folds"][0]["tuning"]["total"] == 12
    assert payload["aggregate_validation"]["total"] == 24
    assert payload["aggregate_policy"]["directional_precision"] == pytest.approx(1.0)


def test_rejects_noncontiguous_source_sessions(tmp_path: Path) -> None:
    """A source session cannot reappear after a later session begins."""
    source_path = tmp_path / "combined.csv"
    rows = make_rows(("first", "second", "first"))
    write_rows(source_path, rows)

    with pytest.raises(ValueError, match="is not contiguous"):
        load_session_partitions(source_path)


def test_rejects_too_few_sessions_for_configuration(tmp_path: Path) -> None:
    """Training, validation, and held-out groups must all exist."""
    source_path = tmp_path / "combined.csv"
    write_rows(source_path, make_rows(("one", "two", "three")))

    with pytest.raises(ValueError, match="requires at least 5"):
        run_walk_forward(
            source_path,
            TrainingConfig(device="cpu"),
            minimum_training_sessions=2,
            held_out_session_count=1,
        )


def test_walk_forward_accepts_historical_kline_schema(tmp_path: Path) -> None:
    """The same validation engine must retain the explicit kline feature order."""
    source_path = tmp_path / "kline.csv"
    rows = []
    for session_index, session in enumerate(("one", "two", "three", "four", "five", "six")):
        row_index = 0
        for direction in (-1, 0, 1):
            for _ in range(3):
                row = {name: str(direction * 0.2) for name in KLINE_FEATURE_COLUMNS}
                row["taker_buy_ratio"] = "0.5"
                row["close_location"] = "0.5"
                row["target_direction"] = str(direction)
                row["source_session"] = session
                event_time = session_index * 100_000 + row_index * 2000
                row["depth_event_time_ms"] = str(event_time)
                row["entry_time_ms"] = str(event_time + 1)
                row["future_event_time_ms"] = str(event_time + 999)
                row["net_return_bps"] = str(direction * 10)
                rows.append(row)
                row_index += 1
    with source_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=(
                *KLINE_FEATURE_COLUMNS,
                "target_direction",
                "source_session",
                "entry_time_ms",
                "depth_event_time_ms",
                "future_event_time_ms",
                "net_return_bps",
            ),
        )
        writer.writeheader()
        writer.writerows(rows)

    report = run_walk_forward(
        source_path,
        TrainingConfig(
            max_epochs=40,
            patience=5,
            learning_rate=0.1,
            weight_decay=0,
            device="cpu",
        ),
        minimum_training_sessions=2,
        held_out_session_count=1,
    )

    assert report.feature_names == KLINE_MODEL_FEATURE_NAMES
    assert report.evaluated_sessions == ("four", "five")
    assert report.held_out_sessions == ("six",)
    assert report.aggregate_economics is not None
    assert report.aggregate_economics.net_pnl > 0
    first = report.folds[0].economics
    second = report.folds[1].economics
    assert first.accepted_trades > 0
    assert second.starting_balance == first.ending_balance
    assert second.previous_exit_time_ms == first.last_exit_time_ms
    assert report.aggregate_economics.ending_balance == second.ending_balance
    assert report.aggregate_economics.trade_ledger == first.trade_ledger + second.trade_ledger


@pytest.mark.parametrize("tuning_count", [0, -1])
def test_rejects_nonpositive_tuning_count(tmp_path: Path, tuning_count: int) -> None:
    """A missing tuning block must not restore evaluation-day selection."""
    with pytest.raises(ValueError, match="Tuning session count must be positive"):
        run_walk_forward(
            tmp_path / "unused.csv",
            TrainingConfig(device="cpu"),
            tuning_session_count=tuning_count,
        )


def test_multiple_tuning_sessions(tmp_path: Path) -> None:
    """The configured tuning window slides while fitting expands."""
    source = tmp_path / "combined.csv"
    write_rows(source, make_rows(("a", "b", "c", "d", "e", "f", "g")))
    report = run_walk_forward(
        source,
        TrainingConfig(max_epochs=2, patience=1, device="cpu"),
        minimum_training_sessions=2,
        tuning_session_count=2,
    )
    assert report.evaluated_sessions == ("e", "f")
    assert report.folds[0].training_sessions == ("a", "b")
    assert report.folds[0].tuning_sessions == ("c", "d")
    assert report.folds[1].training_sessions == ("a", "b", "c")
    assert report.folds[1].tuning_sessions == ("d", "e")
    assert report.folds[0].tuning_rows == 24


@pytest.mark.parametrize("changed_session", ["evaluation", "future", "held-out"])
def test_future_targets_cannot_select_current_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_session: str,
) -> None:
    """Changing outcomes unavailable at fit time cannot affect the first fold."""
    source = tmp_path / "combined.csv"
    rows = make_rows(("fit-one", "fit-two", "tune", "evaluation", "future", "held-out"))
    config = TrainingConfig(max_epochs=30, patience=5, learning_rate=0.1, device="cpu")
    captured_fits = []
    captured_predictions = []
    original_fit = walk_forward.fit_linear_baseline
    original_predict = walk_forward.predict_probabilities

    def capture_fit(*args, **kwargs):
        fitted = original_fit(*args, **kwargs)
        captured_fits.append(fitted)
        return fitted

    def capture_predictions(*args, **kwargs):
        probabilities = original_predict(*args, **kwargs)
        captured_predictions.append(probabilities.copy())
        return probabilities

    monkeypatch.setattr(walk_forward, "fit_linear_baseline", capture_fit)
    monkeypatch.setattr(walk_forward, "predict_probabilities", capture_predictions)
    write_rows(source, rows)
    original = run_walk_forward(source, config)
    for row in rows:
        if row["source_session"] == changed_session:
            row["target_direction"] = str(-int(row["target_direction"]))
            if changed_session != "evaluation":
                row["book_imbalance"] = "0.321"
    write_rows(source, rows)
    changed = run_walk_forward(source, config)

    first, second = captured_fits[0], captured_fits[2]
    assert first.best_epoch == second.best_epoch
    assert first.epochs_trained == second.epochs_trained
    for name, tensor in first.model.state_dict().items():
        assert tensor.equal(second.model.state_dict()[name])
    np.testing.assert_array_equal(captured_predictions[0], captured_predictions[2])
    assert original.folds[0].tuning == changed.folds[0].tuning
    if changed_session == "evaluation":
        assert original.folds[0].validation != changed.folds[0].validation
    else:
        assert original.folds[0] == changed.folds[0]


def test_walk_forward_skips_poisoned_holdout_values(tmp_path: Path) -> None:
    """Exercise the real training entry point, not just the standalone loader."""
    source = tmp_path / "combined.csv"
    rows = make_rows(("fit-one", "fit-two", "tune", "evaluate", "held-out"))
    for row in rows:
        if row["source_session"] == "held-out":
            row.update(
                book_imbalance="not a feature",
                target_direction="not a label",
                future_event_time_ms="not an outcome",
            )
    write_rows(source, rows)
    report = run_walk_forward(source, TrainingConfig(max_epochs=2, patience=1, device="cpu"))
    assert report.held_out_sessions == ("held-out",)
    assert report.evaluated_sessions == ("evaluate",)


def test_boundary_failure_happens_before_any_fit(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "combined.csv"
    rows = make_rows(("fit-one", "fit-two", "tune", "evaluate", "held-out"))
    rows[0]["future_event_time_ms"] = rows[12]["depth_event_time_ms"]
    write_rows(source, rows)

    def forbidden_fit(*args, **kwargs):
        raise AssertionError("No model may be fitted on invalid chronology")

    monkeypatch.setattr(walk_forward, "fit_linear_baseline", forbidden_fit)
    with pytest.raises(ValueError, match="crosses the next session boundary"):
        run_walk_forward(source, TrainingConfig(device="cpu"))
