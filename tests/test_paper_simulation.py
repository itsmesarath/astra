"""Tests for chronological offline paper simulation."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from ai_trader.backtesting.paper_simulation import (
    run_paper_simulation,
)
from ai_trader.risk.engine import RiskLimits
from ai_trader.trading.decision_policy import DecisionPolicy
from ai_trader.trading.execution import ExecutionCosts
from ai_trader.trading.paper_broker import PaperBroker
from ai_trader.trading.paper_portfolio import PaperPortfolio
from ai_trader.training.model_data import MODEL_FEATURE_NAMES


class FakeCheckpoint:
    """Checkpoint stub returning predetermined probabilities."""

    feature_names = MODEL_FEATURE_NAMES

    def __init__(
        self,
        probabilities: np.ndarray,
    ) -> None:
        self.probabilities = probabilities

    def predict_probabilities(
        self,
        features: np.ndarray,
    ) -> np.ndarray:
        """Return one configured probability row per feature row."""
        if features.shape[0] != self.probabilities.shape[0]:
            raise ValueError("Probability row count does not match.")
        return self.probabilities


def make_row(
    *,
    event_time_ms: int,
    update_id: int,
    bid: str,
    ask: str,
) -> dict[str, str]:
    """Create one causal feature row."""
    midpoint = (Decimal(bid) + Decimal(ask)) / Decimal("2")

    return {
        "depth_event_time_ms": str(event_time_ms),
        "update_id": str(update_id),
        "best_bid_price": bid,
        "best_ask_price": ask,
        "spread": str(Decimal(ask) - Decimal(bid)),
        "midpoint": str(midpoint),
        "microprice": str(midpoint),
        "bid_depth": "2",
        "ask_depth": "2",
        "book_imbalance": "0",
        "total_base_volume": "0",
        "trade_imbalance": "0",
        "aggregate_trade_count": "0",
        "underlying_trade_count": "0",
        "target_direction": "0",
    }


def write_rows(
    path: Path,
    rows: list[dict[str, str]],
) -> None:
    """Write chronological simulation rows."""
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=list(rows[0]),
        )
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read paper ledger rows."""
    with path.open(encoding="utf-8", newline="") as input_file:
        return list(csv.DictReader(input_file))


def make_broker(
    *,
    max_order_btc: str = "1",
) -> PaperBroker:
    """Create a zero-cost broker for exact accounting tests."""
    return PaperBroker(
        portfolio=PaperPortfolio.create(Decimal("10000")),
        risk_limits=RiskLimits(
            max_position_btc=Decimal("1"),
            max_order_btc=Decimal(max_order_btc),
            max_order_notional_usdt=Decimal("10000"),
            max_position_notional_usdt=Decimal("10000"),
            max_daily_loss_usdt=Decimal("100"),
            max_drawdown_usdt=Decimal("100"),
        ),
        execution_costs=ExecutionCosts(
            taker_fee_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        ),
    )


def test_runs_chronological_model_policy_and_portfolio(
    tmp_path: Path,
) -> None:
    """The simulator should process rows without future leakage."""
    input_path = tmp_path / "features.csv"
    output_path = tmp_path / "ledger.csv"
    write_rows(
        input_path,
        [
            make_row(
                event_time_ms=1000,
                update_id=1,
                bid="100",
                ask="101",
            ),
            make_row(
                event_time_ms=1100,
                update_id=2,
                bid="102",
                ask="103",
            ),
            make_row(
                event_time_ms=1200,
                update_id=3,
                bid="99",
                ask="100",
            ),
        ],
    )
    checkpoint = FakeCheckpoint(
        np.asarray(
            [
                [0.10, 0.20, 0.70],
                [0.10, 0.80, 0.10],
                [0.70, 0.20, 0.10],
            ],
            dtype=np.float32,
        )
    )

    report = run_paper_simulation(
        checkpoint=checkpoint,
        input_path=input_path,
        output_path=output_path,
        broker=make_broker(),
        policy=DecisionPolicy(
            minimum_direction_probability=0.55,
            minimum_probability_margin=0.10,
        ),
        entry_quantity_btc=Decimal("0.1"),
    )
    ledger = read_rows(output_path)

    assert report.rows == 3
    assert report.long_intents == 1
    assert report.flat_intents == 1
    assert report.short_intents == 1
    assert report.fills == 3
    assert report.risk_rejections == 0
    assert report.final_position_btc == Decimal("-0.1")
    assert report.gross_realized_pnl_usdt == Decimal("0.1")
    assert report.fees_paid_usdt == Decimal("0")
    assert report.final_equity_usdt == Decimal("10000.05")
    assert report.net_pnl_usdt == Decimal("0.05")
    assert report.maximum_drawdown_usdt == Decimal("0.10")

    assert len(ledger) == 3
    assert [row["position_intent"] for row in ledger] == [
        "LONG",
        "FLAT",
        "SHORT",
    ]
    assert [row["fill_side"] for row in ledger] == [
        "BUY",
        "SELL",
        "SELL",
    ]
    assert [row["executed"] for row in ledger] == [
        "1",
        "1",
        "1",
    ]


def test_records_risk_rejection_without_fill(
    tmp_path: Path,
) -> None:
    """A rejected entry must leave portfolio equity unchanged."""
    input_path = tmp_path / "features.csv"
    output_path = tmp_path / "ledger.csv"
    write_rows(
        input_path,
        [
            make_row(
                event_time_ms=1000,
                update_id=1,
                bid="100",
                ask="101",
            )
        ],
    )
    checkpoint = FakeCheckpoint(
        np.asarray(
            [[0.10, 0.20, 0.70]],
            dtype=np.float32,
        )
    )

    report = run_paper_simulation(
        checkpoint=checkpoint,
        input_path=input_path,
        output_path=output_path,
        broker=make_broker(max_order_btc="0.05"),
        policy=DecisionPolicy(
            minimum_direction_probability=0.55,
            minimum_probability_margin=0.10,
        ),
        entry_quantity_btc=Decimal("0.1"),
    )
    ledger = read_rows(output_path)

    assert report.fills == 0
    assert report.risk_rejections == 1
    assert report.final_position_btc == Decimal("0")
    assert report.final_equity_usdt == Decimal("10000")
    assert ledger[0]["executed"] == "0"
    assert ledger[0]["risk_reason"] == "order_quantity_limit_exceeded"


def test_rejects_checkpoint_feature_schema_mismatch(
    tmp_path: Path,
) -> None:
    """Simulation must reject incompatible checkpoint schemas."""
    input_path = tmp_path / "unused.csv"
    output_path = tmp_path / "unused_output.csv"
    checkpoint = FakeCheckpoint(np.asarray([[0.1, 0.8, 0.1]]))
    checkpoint.feature_names = tuple(reversed(MODEL_FEATURE_NAMES))

    with pytest.raises(
        ValueError,
        match="feature schema does not match",
    ):
        run_paper_simulation(
            checkpoint=checkpoint,
            input_path=input_path,
            output_path=output_path,
            broker=make_broker(),
            policy=DecisionPolicy(),
            entry_quantity_btc=Decimal("0.1"),
        )
