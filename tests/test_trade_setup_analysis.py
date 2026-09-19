"""Tests for training-only Spot trade-setup analysis."""

from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path

import pytest

from ai_trader.research.trade_setup_analysis import (
    analyze_trade_setups,
    load_analysis_rows,
    write_report,
)

FIELDNAMES = (
    "source_session",
    "depth_event_time_ms",
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
    "future_return_bps",
)


def make_rows(sessions: tuple[str, ...]) -> list[dict[str, str]]:
    """Create session rows with feature values predictive of winners."""
    rows = []
    returns = ("3", "-2", "-1", "2")
    for session_index, session in enumerate(sessions):
        for row_index, future_return in enumerate(returns):
            winner_feature = "0.8" if Decimal(future_return) > 0 else "-0.8"
            rows.append(
                {
                    "source_session": session,
                    "depth_event_time_ms": str(session_index * 1000 + row_index * 100),
                    "spread": "0.01",
                    "midpoint": "100",
                    "microprice": "100",
                    "bid_depth": "10",
                    "ask_depth": "10",
                    "book_imbalance": winner_feature,
                    "total_base_volume": "5",
                    "trade_imbalance": winner_feature,
                    "aggregate_trade_count": "2",
                    "underlying_trade_count": "3",
                    "target_direction": "1" if Decimal(future_return) > 0 else "-1",
                    "future_return_bps": future_return,
                }
            )
    return rows


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    """Write one combined labeled fixture."""
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def test_analyzes_training_sessions_and_excludes_holdout(tmp_path: Path) -> None:
    """Future held-out sessions must not influence discovered feature effects."""
    source_path = tmp_path / "combined.csv"
    report_path = tmp_path / "report.json"
    write_rows(source_path, make_rows(("one", "two", "three", "holdout")))

    report = analyze_trade_setups(
        source_path,
        exclude_final_sessions=1,
        minimum_net_return_bps=Decimal("1"),
        taker_fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        embargo_ms=100,
    )
    write_report(report_path, report)

    assert report.analyzed_sessions == ("one", "two", "three")
    assert report.excluded_sessions == ("holdout",)
    assert report.sampled_rows == 12
    assert report.winning_rows == 6
    assert report.winner_rate == pytest.approx(0.5)
    assert report.feature_signals[0].feature in {"book_imbalance", "trade_imbalance"}
    assert report.feature_signals[0].standardized_difference > 1

    with report_path.open(encoding="utf-8") as input_file:
        payload = json.load(input_file)

    assert payload["market"] == "spot"
    assert payload["direction"] == "long_only"
    assert payload["excluded_sessions"] == ["holdout"]


def test_embargo_removes_overlapping_observations(tmp_path: Path) -> None:
    """Closely spaced rows must not masquerade as independent opportunities."""
    source_path = tmp_path / "combined.csv"
    write_rows(source_path, make_rows(("one", "two")))

    report = analyze_trade_setups(
        source_path,
        exclude_final_sessions=1,
        minimum_net_return_bps=Decimal("1"),
        taker_fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        embargo_ms=200,
    )

    assert report.sampled_rows == 2
    assert report.winning_rows == 1


def test_rejects_noncontiguous_sessions(tmp_path: Path) -> None:
    """A session identifier may occupy only one chronological block."""
    source_path = tmp_path / "combined.csv"
    write_rows(source_path, make_rows(("first", "second", "first")))

    with pytest.raises(ValueError, match="not contiguous"):
        load_analysis_rows(source_path)


def test_reports_when_costs_remove_every_winner(tmp_path: Path) -> None:
    """An economically empty setup set is evidence, not an analysis failure."""
    source_path = tmp_path / "combined.csv"
    write_rows(source_path, make_rows(("train", "holdout")))

    report = analyze_trade_setups(
        source_path,
        exclude_final_sessions=1,
        minimum_net_return_bps=Decimal("1"),
        taker_fee_bps=Decimal("10"),
        slippage_bps=Decimal("2"),
        embargo_ms=100,
    )

    assert report.winning_rows == 0
    assert report.non_winning_rows == report.sampled_rows
    assert report.feature_signals == ()
