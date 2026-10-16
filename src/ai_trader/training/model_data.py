"""Leakage-resistant model input construction."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np

from ai_trader.features.kline_dataset import KLINE_FEATURE_COLUMNS

MODEL_FEATURE_NAMES = (
    "spread_bps",
    "microprice_offset_bps",
    "book_imbalance",
    "log1p_bid_depth",
    "log1p_ask_depth",
    "log1p_total_base_volume",
    "trade_imbalance",
    "log1p_aggregate_trade_count",
    "log1p_underlying_trade_count",
)

REQUIRED_SOURCE_COLUMNS = {
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
}

KLINE_MODEL_FEATURE_NAMES = tuple(KLINE_FEATURE_COLUMNS)

BASIS_POINTS_PER_UNIT = Decimal("10000")


@dataclass(frozen=True, slots=True)
class ModelPartition:
    """Numeric feature matrix and target vector for one partition."""

    features: np.ndarray
    targets: np.ndarray
    feature_names: tuple[str, ...] = ()

    @property
    def rows(self) -> int:
        """Return the number of observations."""
        return self.features.shape[0]

    @property
    def columns(self) -> int:
        """Return the number of model features."""
        return self.features.shape[1]


def read_decimal(
    row: dict[str, str],
    column: str,
) -> Decimal:
    """Read one finite decimal value from a CSV row."""
    try:
        value = Decimal(row[column])
    except (InvalidOperation, KeyError) as error:
        raise ValueError(f"Column {column!r} must contain a decimal value.") from error

    if not value.is_finite():
        raise ValueError(f"Column {column!r} must contain a finite value.")

    return value


def read_nonnegative_integer(
    row: dict[str, str],
    column: str,
) -> int:
    """Read one nonnegative integer from a CSV row."""
    try:
        value = int(row[column])
    except (ValueError, KeyError) as error:
        raise ValueError(f"Column {column!r} must contain an integer.") from error

    if value < 0:
        raise ValueError(f"Column {column!r} cannot be negative.")

    return value


def row_to_model_features(
    row: dict[str, str],
) -> np.ndarray:
    """Transform one causal CSV row into stationary model features."""
    spread = read_decimal(row, "spread")
    midpoint = read_decimal(row, "midpoint")
    microprice = read_decimal(row, "microprice")
    bid_depth = read_decimal(row, "bid_depth")
    ask_depth = read_decimal(row, "ask_depth")
    book_imbalance = read_decimal(row, "book_imbalance")
    total_base_volume = read_decimal(
        row,
        "total_base_volume",
    )
    trade_imbalance = read_decimal(row, "trade_imbalance")
    aggregate_trade_count = read_nonnegative_integer(
        row,
        "aggregate_trade_count",
    )
    underlying_trade_count = read_nonnegative_integer(
        row,
        "underlying_trade_count",
    )

    if midpoint <= 0:
        raise ValueError("Midpoint must be positive.")
    if spread < 0:
        raise ValueError("Spread cannot be negative.")
    if bid_depth < 0 or ask_depth < 0:
        raise ValueError("Book depths cannot be negative.")
    if total_base_volume < 0:
        raise ValueError("Total base volume cannot be negative.")
    if not Decimal("-1") <= book_imbalance <= Decimal("1"):
        raise ValueError("Book imbalance must be between -1 and 1.")
    if not Decimal("-1") <= trade_imbalance <= Decimal("1"):
        raise ValueError("Trade imbalance must be between -1 and 1.")

    spread_bps = spread / midpoint * BASIS_POINTS_PER_UNIT
    microprice_offset_bps = (microprice - midpoint) / midpoint * BASIS_POINTS_PER_UNIT

    return np.asarray(
        [
            float(spread_bps),
            float(microprice_offset_bps),
            float(book_imbalance),
            math.log1p(float(bid_depth)),
            math.log1p(float(ask_depth)),
            math.log1p(float(total_base_volume)),
            float(trade_imbalance),
            math.log1p(aggregate_trade_count),
            math.log1p(underlying_trade_count),
        ],
        dtype=np.float64,
    )


def row_to_kline_model_features(row: dict[str, str]) -> np.ndarray:
    """Read the explicit stationary historical-kline feature schema."""
    values = []
    for column in KLINE_MODEL_FEATURE_NAMES:
        value = read_decimal(row, column)
        values.append(float(value))

    features = np.asarray(values, dtype=np.float64)
    if not np.isfinite(features).all():
        raise ValueError("Kline model features must be finite.")

    taker_buy_ratio = features[KLINE_MODEL_FEATURE_NAMES.index("taker_buy_ratio")]
    close_location = features[KLINE_MODEL_FEATURE_NAMES.index("close_location")]
    if not 0 <= taker_buy_ratio <= 1:
        raise ValueError("Taker-buy ratio must be between 0 and 1.")
    if not 0 <= close_location <= 1:
        raise ValueError("Close location must be between 0 and 1.")
    return features


def infer_model_feature_names(fieldnames: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Select one unambiguous supported causal feature schema from a CSV header."""
    columns = set(fieldnames)
    has_orderbook_schema = REQUIRED_SOURCE_COLUMNS <= columns
    has_kline_schema = set(KLINE_MODEL_FEATURE_NAMES) <= columns and "target_direction" in columns
    if has_orderbook_schema and has_kline_schema:
        raise ValueError("Dataset contains multiple supported model feature schemas.")
    if has_orderbook_schema:
        return MODEL_FEATURE_NAMES
    if has_kline_schema:
        return KLINE_MODEL_FEATURE_NAMES
    raise ValueError("Dataset does not contain a supported model feature schema.")


def row_to_schema_features(
    row: dict[str, str],
    feature_names: tuple[str, ...],
) -> np.ndarray:
    """Transform a row using its already-detected causal feature schema."""
    if feature_names == MODEL_FEATURE_NAMES:
        return row_to_model_features(row)
    if feature_names == KLINE_MODEL_FEATURE_NAMES:
        return row_to_kline_model_features(row)
    raise ValueError("Unsupported model feature schema.")


def load_model_partition(path: Path) -> ModelPartition:
    """Load a split CSV using only the explicit causal schema."""
    feature_rows = []
    targets = []

    with path.open(encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)

        if reader.fieldnames is None:
            raise ValueError(f"{path.name} does not contain a header.")

        try:
            feature_names = infer_model_feature_names(reader.fieldnames)
        except ValueError as error:
            raise ValueError(f"{path.name}: {error}") from error

        for line_number, row in enumerate(reader, start=2):
            try:
                features = row_to_schema_features(row, feature_names)
                target = int(row["target_direction"])
            except ValueError as error:
                raise ValueError(f"{path.name} line {line_number}: {error}") from error

            if target not in {-1, 0, 1}:
                raise ValueError(
                    f"{path.name} line {line_number}: target_direction must be -1, 0, or 1."
                )

            feature_rows.append(features)
            targets.append(target)

    if not feature_rows:
        raise ValueError(f"{path.name} contains no data rows.")

    feature_matrix = np.vstack(feature_rows).astype(
        np.float64,
        copy=False,
    )
    target_vector = np.asarray(targets, dtype=np.int64)

    if not np.isfinite(feature_matrix).all():
        raise ValueError(f"{path.name} produced non-finite model features.")

    return ModelPartition(
        features=feature_matrix,
        targets=target_vector,
        feature_names=feature_names,
    )
