"""Run chronological offline paper simulation from a checkpoint."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ai_trader.models.checkpoint import (
    LoadedLinearCheckpoint,
    load_linear_checkpoint,
)
from ai_trader.models.predict_csv import (
    find_latest_checkpoint,
    read_inference_rows,
)
from ai_trader.risk.engine import RiskLimits
from ai_trader.trading.decision_policy import (
    DecisionPolicy,
    decide_position,
)
from ai_trader.trading.execution import (
    ExecutionCosts,
    MarketQuote,
)
from ai_trader.trading.paper_broker import PaperBroker
from ai_trader.trading.paper_portfolio import PaperPortfolio
from ai_trader.training.model_data import MODEL_FEATURE_NAMES

DEFAULT_OUTPUT_DIRECTORY = Path("data/processed/backtests")

LEDGER_COLUMNS = (
    "schema_version",
    "source_row_index",
    "depth_event_time_ms",
    "update_id",
    "best_bid_price",
    "best_ask_price",
    "midpoint",
    "probability_down",
    "probability_neutral",
    "probability_up",
    "predicted_direction",
    "position_intent",
    "decision_reason",
    "decision_confidence",
    "decision_probability_margin",
    "executed",
    "broker_reason",
    "risk_reason",
    "fill_side",
    "fill_quantity_btc",
    "fill_price_usdt",
    "fill_fee_usdt",
    "position_btc",
    "cash_usdt",
    "equity_usdt",
    "drawdown_usdt",
    "actual_direction",
)


@dataclass(frozen=True, slots=True)
class SimulationReport:
    """Summary of a chronological offline paper simulation."""

    rows: int
    short_intents: int
    flat_intents: int
    long_intents: int
    fills: int
    risk_rejections: int
    initial_equity_usdt: Decimal
    final_equity_usdt: Decimal
    net_pnl_usdt: Decimal
    return_fraction: Decimal
    maximum_drawdown_usdt: Decimal
    gross_realized_pnl_usdt: Decimal
    fees_paid_usdt: Decimal
    net_realized_pnl_usdt: Decimal
    final_position_btc: Decimal


def default_validation_path(
    checkpoint: LoadedLinearCheckpoint,
) -> Path:
    """Return the validation partition recorded by a checkpoint."""
    training_metadata = checkpoint.metadata.get("training")
    if not isinstance(training_metadata, dict):
        raise ValueError("Checkpoint does not contain training metadata.")

    source_directory = training_metadata.get("source_split_directory")
    if not isinstance(source_directory, str) or not source_directory:
        raise ValueError("Checkpoint does not identify its source split.")

    return Path(source_directory) / "validation.csv"


def create_output_path(
    input_path: Path,
    checkpoint_path: Path,
) -> Path:
    """Create a default paper-simulation ledger path."""
    DEFAULT_OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )
    return DEFAULT_OUTPUT_DIRECTORY / (f"{input_path.stem}_{checkpoint_path.name}_paper.csv")


def run_paper_simulation(
    *,
    checkpoint: LoadedLinearCheckpoint,
    input_path: Path,
    output_path: Path,
    broker: PaperBroker,
    policy: DecisionPolicy,
    entry_quantity_btc: Decimal,
) -> SimulationReport:
    """Run model, policy, risk, and accounting chronologically."""
    if checkpoint.feature_names != MODEL_FEATURE_NAMES:
        raise ValueError("Checkpoint feature schema does not match the current model-input schema.")
    if entry_quantity_btc <= 0:
        raise ValueError("Entry quantity must be greater than zero.")

    rows, features, _ = read_inference_rows(input_path)

    for required_column in (
        "best_bid_price",
        "best_ask_price",
    ):
        if required_column not in rows[0]:
            raise ValueError(f"{input_path.name} is missing {required_column}.")

    probabilities = checkpoint.predict_probabilities(features)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    short_intents = 0
    flat_intents = 0
    long_intents = 0
    fills = 0
    risk_rejections = 0
    maximum_drawdown = Decimal("0")
    final_snapshot = None

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=LEDGER_COLUMNS,
        )
        writer.writeheader()

        for index, (row, probability_row) in enumerate(zip(rows, probabilities, strict=True)):
            try:
                quote = MarketQuote(
                    best_bid_usdt=Decimal(row["best_bid_price"]),
                    best_ask_usdt=Decimal(row["best_ask_price"]),
                    event_time_ms=int(row["depth_event_time_ms"]),
                )
            except (ValueError, KeyError) as error:
                raise ValueError(
                    f"{input_path.name} row {index + 2} contains an invalid market quote."
                ) from error

            decision = decide_position(
                probability_row.tolist(),
                policy,
            )

            if decision.intent == "SHORT":
                short_intents += 1
            elif decision.intent == "LONG":
                long_intents += 1
            else:
                flat_intents += 1

            broker_result = broker.process_intent(
                intent=decision.intent,
                entry_quantity_btc=entry_quantity_btc,
                quote=quote,
            )
            final_snapshot = broker_result.snapshot
            maximum_drawdown = max(
                maximum_drawdown,
                final_snapshot.drawdown_usdt,
            )

            if broker_result.executed:
                fills += 1
            if broker_result.risk_decision is not None and not broker_result.risk_decision.approved:
                risk_rejections += 1

            fill = broker_result.fill
            risk_reason = (
                broker_result.risk_decision.reason
                if broker_result.risk_decision is not None
                else ""
            )

            writer.writerow(
                {
                    "schema_version": 1,
                    "source_row_index": index,
                    "depth_event_time_ms": row["depth_event_time_ms"],
                    "update_id": row["update_id"],
                    "best_bid_price": row["best_bid_price"],
                    "best_ask_price": row["best_ask_price"],
                    "midpoint": row["midpoint"],
                    "probability_down": (f"{probability_row[0]:.10f}"),
                    "probability_neutral": (f"{probability_row[1]:.10f}"),
                    "probability_up": (f"{probability_row[2]:.10f}"),
                    "predicted_direction": (decision.predicted_direction),
                    "position_intent": decision.intent,
                    "decision_reason": decision.reason,
                    "decision_confidence": (f"{decision.confidence:.10f}"),
                    "decision_probability_margin": (f"{decision.probability_margin:.10f}"),
                    "executed": int(broker_result.executed),
                    "broker_reason": broker_result.reason,
                    "risk_reason": risk_reason,
                    "fill_side": (fill.side if fill is not None else ""),
                    "fill_quantity_btc": (str(fill.quantity_btc) if fill is not None else ""),
                    "fill_price_usdt": (str(fill.price_usdt) if fill is not None else ""),
                    "fill_fee_usdt": (str(fill.fee_usdt) if fill is not None else ""),
                    "position_btc": str(final_snapshot.position_btc),
                    "cash_usdt": str(final_snapshot.cash_usdt),
                    "equity_usdt": str(final_snapshot.equity_usdt),
                    "drawdown_usdt": str(final_snapshot.drawdown_usdt),
                    "actual_direction": row.get(
                        "target_direction",
                        "",
                    ),
                }
            )

    if final_snapshot is None:
        raise RuntimeError("Paper simulation produced no portfolio snapshot.")

    initial_equity = broker.portfolio.initial_cash_usdt
    final_equity = final_snapshot.equity_usdt
    net_pnl = final_equity - initial_equity

    return SimulationReport(
        rows=len(rows),
        short_intents=short_intents,
        flat_intents=flat_intents,
        long_intents=long_intents,
        fills=fills,
        risk_rejections=risk_rejections,
        initial_equity_usdt=initial_equity,
        final_equity_usdt=final_equity,
        net_pnl_usdt=net_pnl,
        return_fraction=net_pnl / initial_equity,
        maximum_drawdown_usdt=maximum_drawdown,
        gross_realized_pnl_usdt=(final_snapshot.gross_realized_pnl_usdt),
        fees_paid_usdt=final_snapshot.fees_paid_usdt,
        net_realized_pnl_usdt=(final_snapshot.net_realized_pnl_usdt),
        final_position_btc=final_snapshot.position_btc,
    )


def parse_args() -> argparse.Namespace:
    """Read simulation paths, costs, policy, and limits."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="Checkpoint directory; defaults to the newest.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help=("Feature CSV; defaults to the checkpoint's validation partition."),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional ledger CSV path.",
    )
    parser.add_argument(
        "--initial-equity-usdt",
        type=Decimal,
        default=Decimal("10000"),
    )
    parser.add_argument(
        "--entry-quantity-btc",
        type=Decimal,
        default=Decimal("0.001"),
    )
    parser.add_argument(
        "--taker-fee-bps",
        type=Decimal,
        default=Decimal("10"),
    )
    parser.add_argument(
        "--slippage-bps",
        type=Decimal,
        default=Decimal("2"),
    )
    parser.add_argument(
        "--minimum-direction-probability",
        type=float,
        default=0.55,
    )
    parser.add_argument(
        "--minimum-probability-margin",
        type=float,
        default=0.10,
    )
    return parser.parse_args()


def main() -> None:
    """Run one offline validation paper simulation."""
    args = parse_args()
    checkpoint_path = args.checkpoint or find_latest_checkpoint()
    checkpoint = load_linear_checkpoint(checkpoint_path)
    input_path = args.input or default_validation_path(checkpoint)
    output_path = args.output or create_output_path(input_path, checkpoint_path)

    policy = DecisionPolicy(
        minimum_direction_probability=(args.minimum_direction_probability),
        minimum_probability_margin=(args.minimum_probability_margin),
    )
    broker = PaperBroker(
        portfolio=PaperPortfolio.create(args.initial_equity_usdt),
        risk_limits=RiskLimits(
            max_position_btc=Decimal("0.001"),
            max_order_btc=Decimal("0.001"),
            max_order_notional_usdt=Decimal("200"),
            max_position_notional_usdt=Decimal("200"),
            max_daily_loss_usdt=Decimal("10"),
            max_drawdown_usdt=Decimal("20"),
        ),
        execution_costs=ExecutionCosts(
            taker_fee_bps=args.taker_fee_bps,
            slippage_bps=args.slippage_bps,
        ),
    )

    report = run_paper_simulation(
        checkpoint=checkpoint,
        input_path=input_path,
        output_path=output_path,
        broker=broker,
        policy=policy,
        entry_quantity_btc=args.entry_quantity_btc,
    )

    print("Mode: OFFLINE PAPER SIMULATION")
    print(f"Checkpoint: {checkpoint_path.resolve()}")
    print(f"Input: {input_path.resolve()}")
    print(f"Rows: {report.rows}")
    print(
        "Intents: "
        f"short={report.short_intents}, "
        f"flat={report.flat_intents}, "
        f"long={report.long_intents}"
    )
    print(f"Paper fills: {report.fills}")
    print(f"Risk rejections: {report.risk_rejections}")
    print(f"Initial equity: {report.initial_equity_usdt}")
    print(f"Final equity: {report.final_equity_usdt}")
    print(f"Net PnL: {report.net_pnl_usdt}")
    print(f"Return: {report.return_fraction * Decimal('100'):.6f}%")
    print(f"Maximum drawdown: {report.maximum_drawdown_usdt}")
    print(f"Gross realized PnL: {report.gross_realized_pnl_usdt}")
    print(f"Fees paid: {report.fees_paid_usdt}")
    print(f"Net realized PnL: {report.net_realized_pnl_usdt}")
    print(f"Final position BTC: {report.final_position_btc}")
    print(f"Ledger: {output_path.resolve()}")


if __name__ == "__main__":
    main()
