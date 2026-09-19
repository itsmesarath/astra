"""Analyze causal feature states preceding cost-adjusted Spot opportunities."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np

from ai_trader.training.model_data import (
    BASIS_POINTS_PER_UNIT,
    MODEL_FEATURE_NAMES,
    row_to_model_features,
)

SOURCE_SESSION_COLUMN = "source_session"
REQUIRED_COLUMNS = {
    SOURCE_SESSION_COLUMN,
    "depth_event_time_ms",
    "future_return_bps",
}


@dataclass(frozen=True, slots=True)
class FeatureSetupSignal:
    """Difference between winning and non-winning precursor features."""

    feature: str
    winner_mean: float
    non_winner_mean: float
    difference: float
    standardized_difference: float
    net_return_correlation: float


@dataclass(frozen=True, slots=True)
class TradeSetupReport:
    """Summary of cost-adjusted, training-only Spot setup analysis."""

    source_path: Path
    input_rows: int
    total_sessions: int
    analyzed_sessions: tuple[str, ...]
    excluded_sessions: tuple[str, ...]
    sampled_rows: int
    winning_rows: int
    non_winning_rows: int
    winner_rate: float
    minimum_net_return_bps: Decimal
    taker_fee_bps: Decimal
    slippage_bps: Decimal
    embargo_ms: int
    mean_net_return_bps: float
    feature_signals: tuple[FeatureSetupSignal, ...]


def read_decimal(row: dict[str, str], column: str, line_number: int) -> Decimal:
    """Read one finite decimal with a line-specific error."""
    try:
        value = Decimal(row[column])
    except (InvalidOperation, KeyError) as error:
        raise ValueError(f"Line {line_number}: {column} must be a decimal.") from error
    if not value.is_finite():
        raise ValueError(f"Line {line_number}: {column} must be finite.")
    return value


def load_analysis_rows(
    path: Path,
) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    """Read rows and validate contiguous source-session ordering."""
    with path.open(encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            raise ValueError(f"{path.name} does not contain a header.")

        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))
            raise ValueError(f"{path.name} is missing columns: {missing_text}.")
        rows = list(reader)

    if not rows:
        raise ValueError(f"{path.name} contains no data rows.")

    sessions = []
    completed_sessions: set[str] = set()
    current_session: str | None = None
    for line_number, row in enumerate(rows, start=2):
        session = row[SOURCE_SESSION_COLUMN]
        if not session:
            raise ValueError(f"Line {line_number}: source_session cannot be empty.")
        if session == current_session:
            continue
        if current_session is not None:
            completed_sessions.add(current_session)
        if session in completed_sessions:
            raise ValueError(f"Line {line_number}: source_session {session!r} is not contiguous.")
        sessions.append(session)
        current_session = session

    return rows, tuple(sessions)


def calculate_feature_signals(
    feature_matrix: np.ndarray,
    net_returns_bps: np.ndarray,
    winning_mask: np.ndarray,
) -> tuple[FeatureSetupSignal, ...]:
    """Rank causal features by standardized winner/non-winner separation."""
    signals = []
    for column, feature_name in enumerate(MODEL_FEATURE_NAMES):
        values = feature_matrix[:, column]
        winner_mean = float(values[winning_mask].mean())
        non_winner_mean = float(values[~winning_mask].mean())
        difference = winner_mean - non_winner_mean
        standard_deviation = float(values.std())
        standardized_difference = difference / standard_deviation if standard_deviation > 0 else 0.0
        if standard_deviation > 0 and float(net_returns_bps.std()) > 0:
            correlation = float(np.corrcoef(values, net_returns_bps)[0, 1])
        else:
            correlation = 0.0
        signals.append(
            FeatureSetupSignal(
                feature=feature_name,
                winner_mean=winner_mean,
                non_winner_mean=non_winner_mean,
                difference=difference,
                standardized_difference=standardized_difference,
                net_return_correlation=correlation,
            )
        )

    return tuple(
        sorted(
            signals,
            key=lambda signal: abs(signal.standardized_difference),
            reverse=True,
        )
    )


def analyze_trade_setups(
    path: Path,
    *,
    exclude_final_sessions: int,
    minimum_net_return_bps: Decimal,
    taker_fee_bps: Decimal,
    slippage_bps: Decimal,
    embargo_ms: int,
) -> TradeSetupReport:
    """Analyze long-entry precursors using only non-held-out sessions."""
    if exclude_final_sessions <= 0:
        raise ValueError("At least one final session must be excluded.")
    if minimum_net_return_bps < 0:
        raise ValueError("Minimum net return cannot be negative.")
    if taker_fee_bps < 0 or slippage_bps < 0:
        raise ValueError("Trading costs cannot be negative.")
    if embargo_ms <= 0:
        raise ValueError("Embargo must be positive.")

    rows, sessions = load_analysis_rows(path)
    if len(sessions) <= exclude_final_sessions:
        raise ValueError("Excluded sessions must leave at least one analysis session.")

    analyzed_sessions = sessions[:-exclude_final_sessions]
    excluded_sessions = sessions[-exclude_final_sessions:]
    analyzed_set = set(analyzed_sessions)
    feature_rows = []
    net_returns = []
    next_allowed_time_by_session: dict[str, int] = {}

    for line_number, row in enumerate(rows, start=2):
        session = row[SOURCE_SESSION_COLUMN]
        if session not in analyzed_set:
            continue
        try:
            event_time_ms = int(row["depth_event_time_ms"])
        except ValueError as error:
            raise ValueError(f"Line {line_number}: invalid depth_event_time_ms.") from error

        if event_time_ms < next_allowed_time_by_session.get(session, event_time_ms):
            continue

        future_return_bps = read_decimal(row, "future_return_bps", line_number)
        spread = read_decimal(row, "spread", line_number)
        midpoint = read_decimal(row, "midpoint", line_number)
        if midpoint <= 0:
            raise ValueError(f"Line {line_number}: midpoint must be positive.")

        spread_bps = spread / midpoint * BASIS_POINTS_PER_UNIT
        estimated_cost_bps = spread_bps + Decimal("2") * (taker_fee_bps + slippage_bps)
        net_return_bps = future_return_bps - estimated_cost_bps

        try:
            features = row_to_model_features(row)
        except ValueError as error:
            raise ValueError(f"Line {line_number}: {error}") from error

        feature_rows.append(features)
        net_returns.append(float(net_return_bps))
        next_allowed_time_by_session[session] = event_time_ms + embargo_ms

    if len(feature_rows) < 2:
        raise ValueError("Analysis produced fewer than two embargoed rows.")

    feature_matrix = np.vstack(feature_rows).astype(np.float64, copy=False)
    net_returns_array = np.asarray(net_returns, dtype=np.float64)
    winning_mask = net_returns_array >= float(minimum_net_return_bps)
    winning_rows = int(winning_mask.sum())
    non_winning_rows = int((~winning_mask).sum())
    feature_signals = (
        calculate_feature_signals(
            feature_matrix,
            net_returns_array,
            winning_mask,
        )
        if winning_rows > 0 and non_winning_rows > 0
        else ()
    )

    return TradeSetupReport(
        source_path=path,
        input_rows=len(rows),
        total_sessions=len(sessions),
        analyzed_sessions=analyzed_sessions,
        excluded_sessions=excluded_sessions,
        sampled_rows=len(feature_rows),
        winning_rows=winning_rows,
        non_winning_rows=non_winning_rows,
        winner_rate=winning_rows / len(feature_rows),
        minimum_net_return_bps=minimum_net_return_bps,
        taker_fee_bps=taker_fee_bps,
        slippage_bps=slippage_bps,
        embargo_ms=embargo_ms,
        mean_net_return_bps=float(net_returns_array.mean()),
        feature_signals=feature_signals,
    )


def write_report(path: Path, report: TradeSetupReport) -> None:
    """Write an auditable JSON trade-setup report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "market": "spot",
        "direction": "long_only",
        "source_dataset": str(report.source_path.resolve()),
        "input_rows": report.input_rows,
        "total_sessions": report.total_sessions,
        "analyzed_sessions": list(report.analyzed_sessions),
        "excluded_sessions": list(report.excluded_sessions),
        "sampled_rows": report.sampled_rows,
        "winning_rows": report.winning_rows,
        "non_winning_rows": report.non_winning_rows,
        "winner_rate": report.winner_rate,
        "minimum_net_return_bps": str(report.minimum_net_return_bps),
        "taker_fee_bps": str(report.taker_fee_bps),
        "slippage_bps": str(report.slippage_bps),
        "embargo_ms": report.embargo_ms,
        "mean_net_return_bps": report.mean_net_return_bps,
        "feature_signals": [asdict(signal) for signal in report.feature_signals],
        "limitations": [
            "Future returns define outcomes only and are not model inputs.",
            "Round-trip spread cost uses the entry spread as a future-spread proxy.",
            "This is exploratory training-session evidence, not a trading rule.",
        ],
    }
    with path.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump(payload, output_file, indent=2)
        output_file.write("\n")


def parse_args() -> argparse.Namespace:
    """Read source, cost, embargo, and output arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exclude-final-sessions", type=int, default=2)
    parser.add_argument("--minimum-net-return-bps", type=Decimal, default=Decimal("1"))
    parser.add_argument("--taker-fee-bps", type=Decimal, default=Decimal("10"))
    parser.add_argument("--slippage-bps", type=Decimal, default=Decimal("2"))
    parser.add_argument("--embargo-ms", type=int, default=10000)
    return parser.parse_args()


def main() -> None:
    """Analyze and record cost-adjusted Spot setup precursors."""
    args = parse_args()
    report = analyze_trade_setups(
        args.path,
        exclude_final_sessions=args.exclude_final_sessions,
        minimum_net_return_bps=args.minimum_net_return_bps,
        taker_fee_bps=args.taker_fee_bps,
        slippage_bps=args.slippage_bps,
        embargo_ms=args.embargo_ms,
    )
    write_report(args.output, report)

    print("Mode: TRAINING-ONLY SPOT TRADE-SETUP ANALYSIS")
    print(f"Analyzed sessions: {len(report.analyzed_sessions)}")
    print(f"Excluded sessions: {len(report.excluded_sessions)}")
    print(f"Embargoed rows: {report.sampled_rows}")
    print(f"Winning rows: {report.winning_rows} ({report.winner_rate:.4f})")
    print(f"Mean estimated net return: {report.mean_net_return_bps:.6f} bps")
    print("Strongest precursor differences:")
    for signal in report.feature_signals[:5]:
        print(
            f"  {signal.feature}: standardized_difference="
            f"{signal.standardized_difference:.6f}, "
            f"net_return_correlation={signal.net_return_correlation:.6f}"
        )
    print(f"Report: {args.output.resolve()}")


if __name__ == "__main__":
    main()
