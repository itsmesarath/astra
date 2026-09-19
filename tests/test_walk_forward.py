"""Tests for source-session walk-forward validation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from ai_trader.features.kline_dataset import KLINE_FEATURE_COLUMNS
from ai_trader.trading.decision_policy import DecisionPolicy
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
)


def make_rows(session_names: tuple[str, ...]) -> list[dict[str, str]]:
    """Create balanced, linearly separable rows for each session."""
    rows = []
    for session in session_names:
        for _ in range(4):
            for direction in (-1, 0, 1):
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
    session_names = ("one", "two", "three", "four", "held-out")
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

    assert report.total_sessions == 5
    assert report.evaluated_sessions == ("three", "four")
    assert report.held_out_sessions == ("held-out",)
    assert len(report.folds) == 2
    assert report.folds[0].training_sessions == ("one", "two")
    assert report.folds[1].training_sessions == ("one", "two", "three")
    assert report.aggregate_validation.total == 24
    assert report.aggregate_validation.macro_f1 == pytest.approx(1.0)
    assert report.aggregate_policy.rows == 24
    assert report.aggregate_policy.directional_precision == pytest.approx(1.0)

    with output_path.open(encoding="utf-8") as input_file:
        payload = json.load(input_file)

    assert payload["held_out_sessions"] == ["held-out"]
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

    with pytest.raises(ValueError, match="requires at least 4"):
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
    for session in ("one", "two", "three", "four"):
        row_index = 0
        for direction in (-1, 0, 1):
            for _ in range(3):
                row = {name: str(direction * 0.2) for name in KLINE_FEATURE_COLUMNS}
                row["taker_buy_ratio"] = "0.5"
                row["close_location"] = "0.5"
                row["target_direction"] = str(direction)
                row["source_session"] = session
                row["entry_time_ms"] = str(row_index * 2000)
                row["future_event_time_ms"] = str(row_index * 2000 + 999)
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
    assert report.evaluated_sessions == ("three",)
    assert report.held_out_sessions == ("four",)
    assert report.aggregate_economics is not None
    assert report.aggregate_economics.net_pnl > 0
