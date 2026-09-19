"""Apply validation-only safety gates before paper-model promotion."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

from ai_trader.backtesting.paper_simulation import (
    SimulationReport,
    default_validation_path,
    run_paper_simulation,
)
from ai_trader.models.checkpoint import (
    LoadedLinearCheckpoint,
    load_linear_checkpoint,
)
from ai_trader.models.predict_csv import (
    find_latest_checkpoint,
    run_inference,
)
from ai_trader.risk.engine import RiskLimits
from ai_trader.trading.decision_policy import DecisionPolicy
from ai_trader.trading.evaluate_decision_policy import (
    PolicyEvaluation,
    evaluate_prediction_file,
)
from ai_trader.trading.execution import ExecutionCosts
from ai_trader.trading.paper_broker import PaperBroker
from ai_trader.trading.paper_portfolio import PaperPortfolio

DEFAULT_OUTPUT_DIRECTORY = Path("data/processed/promotion")


@dataclass(frozen=True, slots=True)
class PromotionCriteria:
    """Minimum validation evidence required for paper promotion."""

    minimum_validation_rows: int = 1000
    minimum_balanced_accuracy: float = 0.45
    minimum_macro_f1: float = 0.40
    minimum_directional_signals: int = 30
    minimum_directional_coverage: float = 0.01
    minimum_directional_precision: float = 0.55
    minimum_net_pnl_usdt: Decimal = Decimal("0")
    maximum_drawdown_usdt: Decimal = Decimal("10")
    require_flat_final_position: bool = True

    def __post_init__(self) -> None:
        if self.minimum_validation_rows <= 0:
            raise ValueError("Minimum validation rows must be positive.")
        if self.minimum_directional_signals <= 0:
            raise ValueError("Minimum directional signals must be positive.")
        for name, value in (
            ("minimum_balanced_accuracy", self.minimum_balanced_accuracy),
            ("minimum_macro_f1", self.minimum_macro_f1),
            ("minimum_directional_coverage", self.minimum_directional_coverage),
            ("minimum_directional_precision", self.minimum_directional_precision),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between zero and one.")
        if self.maximum_drawdown_usdt < 0:
            raise ValueError("Maximum drawdown cannot be negative.")


@dataclass(frozen=True, slots=True)
class GateCheck:
    """One auditable promotion requirement."""

    name: str
    passed: bool
    actual: str
    requirement: str


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    """Aggregate result of every validation-only gate."""

    approved: bool
    checks: tuple[GateCheck, ...]

    @property
    def failed_checks(self) -> tuple[GateCheck, ...]:
        """Return checks that prevented promotion."""
        return tuple(check for check in self.checks if not check.passed)


def checkpoint_validation_metrics(
    checkpoint: LoadedLinearCheckpoint,
) -> tuple[int, float, float]:
    """Read validation rows, balanced accuracy, and macro F1."""
    training = checkpoint.metadata.get("training")
    if not isinstance(training, dict):
        raise ValueError("Checkpoint does not contain training metadata.")

    validation = training.get("validation")
    if not isinstance(validation, dict):
        raise ValueError("Checkpoint does not contain validation metrics.")

    try:
        rows = int(validation["total"])
        balanced_accuracy = float(validation["balanced_accuracy"])
        macro_f1 = float(validation["macro_f1"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Checkpoint validation metrics are invalid.") from error

    if rows <= 0:
        raise ValueError("Checkpoint validation row count must be positive.")
    if not 0 <= balanced_accuracy <= 1:
        raise ValueError("Checkpoint balanced accuracy must be between zero and one.")
    if not 0 <= macro_f1 <= 1:
        raise ValueError("Checkpoint macro F1 must be between zero and one.")

    return rows, balanced_accuracy, macro_f1


def evaluate_promotion(
    *,
    validation_rows: int,
    balanced_accuracy: float,
    macro_f1: float,
    policy_report: PolicyEvaluation,
    simulation_report: SimulationReport,
    criteria: PromotionCriteria,
) -> PromotionDecision:
    """Evaluate every promotion gate without consulting test data."""
    checks = (
        GateCheck(
            name="validation_rows",
            passed=validation_rows >= criteria.minimum_validation_rows,
            actual=str(validation_rows),
            requirement=f">= {criteria.minimum_validation_rows}",
        ),
        GateCheck(
            name="balanced_accuracy",
            passed=balanced_accuracy >= criteria.minimum_balanced_accuracy,
            actual=f"{balanced_accuracy:.6f}",
            requirement=f">= {criteria.minimum_balanced_accuracy:.6f}",
        ),
        GateCheck(
            name="macro_f1",
            passed=macro_f1 >= criteria.minimum_macro_f1,
            actual=f"{macro_f1:.6f}",
            requirement=f">= {criteria.minimum_macro_f1:.6f}",
        ),
        GateCheck(
            name="directional_signals",
            passed=(policy_report.directional_signals >= criteria.minimum_directional_signals),
            actual=str(policy_report.directional_signals),
            requirement=f">= {criteria.minimum_directional_signals}",
        ),
        GateCheck(
            name="directional_coverage",
            passed=policy_report.coverage >= criteria.minimum_directional_coverage,
            actual=f"{policy_report.coverage:.6f}",
            requirement=f">= {criteria.minimum_directional_coverage:.6f}",
        ),
        GateCheck(
            name="directional_precision",
            passed=(policy_report.directional_precision >= criteria.minimum_directional_precision),
            actual=f"{policy_report.directional_precision:.6f}",
            requirement=f">= {criteria.minimum_directional_precision:.6f}",
        ),
        GateCheck(
            name="net_pnl_usdt",
            passed=(simulation_report.net_pnl_usdt >= criteria.minimum_net_pnl_usdt),
            actual=str(simulation_report.net_pnl_usdt),
            requirement=f">= {criteria.minimum_net_pnl_usdt}",
        ),
        GateCheck(
            name="maximum_drawdown_usdt",
            passed=(simulation_report.maximum_drawdown_usdt <= criteria.maximum_drawdown_usdt),
            actual=str(simulation_report.maximum_drawdown_usdt),
            requirement=f"<= {criteria.maximum_drawdown_usdt}",
        ),
        GateCheck(
            name="flat_final_position",
            passed=(
                not criteria.require_flat_final_position
                or simulation_report.final_position_btc == 0
            ),
            actual=str(simulation_report.final_position_btc),
            requirement=("== 0" if criteria.require_flat_final_position else "not required"),
        ),
    )

    return PromotionDecision(
        approved=all(check.passed for check in checks),
        checks=checks,
    )


def create_default_broker() -> PaperBroker:
    """Create the fixed-cost broker used by promotion evaluation."""
    return PaperBroker(
        portfolio=PaperPortfolio.create(Decimal("10000")),
        risk_limits=RiskLimits(
            max_position_btc=Decimal("0.001"),
            max_order_btc=Decimal("0.001"),
            max_order_notional_usdt=Decimal("200"),
            max_position_notional_usdt=Decimal("200"),
            max_daily_loss_usdt=Decimal("10"),
            max_drawdown_usdt=Decimal("20"),
        ),
        execution_costs=ExecutionCosts(
            taker_fee_bps=Decimal("10"),
            slippage_bps=Decimal("2"),
        ),
    )


def write_decision_report(
    path: Path,
    *,
    checkpoint_path: Path,
    validation_path: Path,
    predictions_path: Path,
    ledger_path: Path,
    criteria: PromotionCriteria,
    decision: PromotionDecision,
) -> None:
    """Write an auditable JSON promotion decision."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "checkpoint": str(checkpoint_path.resolve()),
        "validation_dataset": str(validation_path.resolve()),
        "validation_predictions": str(predictions_path.resolve()),
        "validation_paper_ledger": str(ledger_path.resolve()),
        "approved_for_paper_trading": decision.approved,
        "criteria": {
            **asdict(criteria),
            "minimum_net_pnl_usdt": str(criteria.minimum_net_pnl_usdt),
            "maximum_drawdown_usdt": str(criteria.maximum_drawdown_usdt),
        },
        "checks": [asdict(check) for check in decision.checks],
    }

    with path.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump(payload, output_file, indent=2)
        output_file.write("\n")


def parse_args() -> argparse.Namespace:
    """Read an optional checkpoint and output directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="Checkpoint directory; defaults to the newest.",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
    )
    return parser.parse_args()


def main() -> None:
    """Run the fixed validation-only promotion process."""
    args = parse_args()
    checkpoint_path = args.checkpoint or find_latest_checkpoint()
    checkpoint = load_linear_checkpoint(checkpoint_path)
    validation_path = default_validation_path(checkpoint)
    output_directory = args.output_directory
    output_directory.mkdir(parents=True, exist_ok=True)

    predictions_path = output_directory / (f"{checkpoint_path.name}_validation_predictions.csv")
    ledger_path = output_directory / (f"{checkpoint_path.name}_validation_paper.csv")
    report_path = output_directory / (f"{checkpoint_path.name}_promotion.json")

    run_inference(
        checkpoint,
        validation_path,
        predictions_path,
    )
    policy = DecisionPolicy(
        minimum_direction_probability=0.55,
        minimum_probability_margin=0.10,
    )
    policy_report = evaluate_prediction_file(
        predictions_path,
        policy,
    )
    simulation_report = run_paper_simulation(
        checkpoint=checkpoint,
        input_path=validation_path,
        output_path=ledger_path,
        broker=create_default_broker(),
        policy=policy,
        entry_quantity_btc=Decimal("0.001"),
    )
    validation_rows, balanced_accuracy, macro_f1 = checkpoint_validation_metrics(checkpoint)
    criteria = PromotionCriteria()
    decision = evaluate_promotion(
        validation_rows=validation_rows,
        balanced_accuracy=balanced_accuracy,
        macro_f1=macro_f1,
        policy_report=policy_report,
        simulation_report=simulation_report,
        criteria=criteria,
    )
    write_decision_report(
        report_path,
        checkpoint_path=checkpoint_path,
        validation_path=validation_path,
        predictions_path=predictions_path,
        ledger_path=ledger_path,
        criteria=criteria,
        decision=decision,
    )

    print("Mode: VALIDATION-ONLY MODEL PROMOTION GATE")
    print(f"Checkpoint: {checkpoint_path.resolve()}")
    for check in decision.checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"{status:4s} | {check.name}: actual={check.actual}, requirement={check.requirement}")
    verdict = "APPROVED" if decision.approved else "BLOCKED"
    print(f"Paper-trading promotion: {verdict}")
    print(f"Report: {report_path.resolve()}")


if __name__ == "__main__":
    main()
