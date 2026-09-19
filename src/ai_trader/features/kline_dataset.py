"""Build causal, session-safe Spot datasets from verified historical klines."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

BASIS_POINTS_PER_UNIT = Decimal("10000")
FEATURE_WINDOWS = (5, 15, 60)
SUPPORTED_SOURCE_INTERVALS_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
}
KLINE_SOURCE_COLUMNS = (
    "open_time_ms",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time_ms",
    "quote_asset_volume",
    "trade_count",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
)
KLINE_FEATURE_COLUMNS = (
    "log_return_1_bps",
    "return_3_bps",
    "return_5_bps",
    "return_15_bps",
    "realized_volatility_5_bps",
    "realized_volatility_15_bps",
    "realized_volatility_60_bps",
    "distance_from_sma_5_bps",
    "distance_from_sma_15_bps",
    "distance_from_sma_60_bps",
    "base_volume_ratio_5",
    "base_volume_ratio_15",
    "trade_count_ratio_5",
    "trade_count_ratio_15",
    "taker_buy_ratio",
    "candle_body_bps",
    "candle_range_bps",
    "close_location",
)
OUTPUT_COLUMNS = (
    "schema_version",
    "symbol",
    "source_session",
    "depth_event_time_ms",
    "update_id",
    "midpoint",
    *KLINE_FEATURE_COLUMNS,
    "label_horizon_ms",
    "neutral_threshold_bps",
    "future_update_id",
    "future_event_time_ms",
    "actual_horizon_ms",
    "future_midpoint",
    "future_return_bps",
    "net_return_bps",
    "target_direction",
    "barrier_hit",
    "entry_time_ms",
    "entry_price",
    "exit_price",
    "holding_period_ms",
    "taker_fee_bps",
    "slippage_bps",
    "round_trip_cost_bps",
    "take_profit_bps",
    "stop_loss_bps",
)
BarrierHit = Literal["target", "stop", "ambiguous_stop", "time"]


@dataclass(frozen=True, slots=True)
class Kline:
    """One validated historical Spot candlestick."""

    open_time_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time_ms: int
    quote_asset_volume: Decimal
    trade_count: int
    taker_buy_base_asset_volume: Decimal


@dataclass(frozen=True, slots=True)
class TripleBarrierConfig:
    """Net-PnL barrier and deterministic market-order cost assumptions."""

    take_profit_bps: Decimal = Decimal("20")
    stop_loss_bps: Decimal = Decimal("40")
    neutral_threshold_bps: Decimal = Decimal("5")
    taker_fee_bps: Decimal = Decimal("10")
    slippage_bps: Decimal = Decimal("2")

    @property
    def round_trip_cost_bps(self) -> Decimal:
        """Return estimated entry plus exit fees and slippage."""
        return Decimal("2") * (self.taker_fee_bps + self.slippage_bps)

    def validate(self) -> None:
        """Reject economically or numerically inconsistent barriers."""
        values = (
            self.take_profit_bps,
            self.stop_loss_bps,
            self.neutral_threshold_bps,
            self.taker_fee_bps,
            self.slippage_bps,
        )
        if any(not value.is_finite() for value in values):
            raise ValueError("Barrier and cost values must be finite.")
        if self.take_profit_bps <= 0 or self.stop_loss_bps <= 0:
            raise ValueError("Take-profit and stop-loss barriers must be positive.")
        if self.neutral_threshold_bps < 0:
            raise ValueError("Neutral threshold cannot be negative.")
        if self.taker_fee_bps < 0 or self.slippage_bps < 0:
            raise ValueError("Trading costs cannot be negative.")
        if self.stop_loss_bps <= self.round_trip_cost_bps:
            raise ValueError("Stop loss must exceed estimated round-trip costs.")


@dataclass(frozen=True, slots=True)
class BarrierOutcome:
    """Cost-adjusted result of one hypothetical long Spot entry."""

    future_index: int
    future_event_time_ms: int
    entry_time_ms: int
    entry_price: Decimal
    exit_price: Decimal
    gross_return_bps: Decimal
    net_return_bps: Decimal
    direction: int
    barrier_hit: BarrierHit


@dataclass(frozen=True, slots=True)
class HorizonReport:
    """Output and class counts for one prediction horizon."""

    horizon_minutes: int
    output_path: Path
    rows: int
    down_labels: int
    neutral_labels: int
    up_labels: int
    target_hits: int
    stop_hits: int
    ambiguous_stop_hits: int
    time_exits: int


@dataclass(frozen=True, slots=True)
class KlineDatasetReport:
    """Summary of a multi-horizon historical build."""

    source_manifest: Path
    output_manifest: Path
    symbol: str
    source_interval: str
    source_sessions: tuple[str, ...]
    input_rows: int
    warmup_rows_per_session: int
    horizons: tuple[HorizonReport, ...]


def file_sha256(path: Path) -> str:
    """Hash a source or generated dataset without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for block in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _decimal(row: dict[str, str], column: str, line_number: int) -> Decimal:
    try:
        value = Decimal(row[column])
    except (InvalidOperation, KeyError) as error:
        raise ValueError(f"Line {line_number}: {column} must be a decimal.") from error
    if not value.is_finite():
        raise ValueError(f"Line {line_number}: {column} must be finite.")
    return value


def _integer(row: dict[str, str], column: str, line_number: int) -> int:
    try:
        return int(row[column])
    except (KeyError, ValueError) as error:
        raise ValueError(f"Line {line_number}: {column} must be an integer.") from error


def read_kline_session(path: Path, *, interval_ms: int, expected_day: date) -> list[Kline]:
    """Read one normalized archive and enforce exact within-session chronology."""
    with path.open(encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        if tuple(reader.fieldnames or ()) != KLINE_SOURCE_COLUMNS:
            raise ValueError(f"{path.name} has an unexpected normalized kline schema.")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path.name} contains no kline rows.")

    klines = []
    for line_number, row in enumerate(rows, start=2):
        kline = Kline(
            open_time_ms=_integer(row, "open_time_ms", line_number),
            open=_decimal(row, "open", line_number),
            high=_decimal(row, "high", line_number),
            low=_decimal(row, "low", line_number),
            close=_decimal(row, "close", line_number),
            volume=_decimal(row, "volume", line_number),
            close_time_ms=_integer(row, "close_time_ms", line_number),
            quote_asset_volume=_decimal(row, "quote_asset_volume", line_number),
            trade_count=_integer(row, "trade_count", line_number),
            taker_buy_base_asset_volume=_decimal(row, "taker_buy_base_asset_volume", line_number),
        )
        if min(kline.open, kline.high, kline.low, kline.close) <= 0:
            raise ValueError(f"Line {line_number}: OHLC prices must be positive.")
        if kline.high < max(kline.open, kline.close) or kline.low > min(kline.open, kline.close):
            raise ValueError(f"Line {line_number}: inconsistent OHLC range.")
        if kline.volume < 0 or kline.quote_asset_volume < 0 or kline.trade_count < 0:
            raise ValueError(f"Line {line_number}: volumes and trade count cannot be negative.")
        if not Decimal("0") <= kline.taker_buy_base_asset_volume <= kline.volume:
            raise ValueError(f"Line {line_number}: taker-buy volume is outside total volume.")
        if kline.close_time_ms != kline.open_time_ms + interval_ms - 1:
            raise ValueError(f"Line {line_number}: kline duration does not match the manifest.")
        if klines and kline.open_time_ms != klines[-1].open_time_ms + interval_ms:
            raise ValueError(f"Line {line_number}: kline sequence contains a gap or duplicate.")
        observed_day = datetime.fromtimestamp(kline.open_time_ms / 1000, tz=UTC).date()
        if observed_day != expected_day:
            raise ValueError(f"Line {line_number}: kline falls outside source session date.")
        klines.append(kline)
    return klines


def _bps_ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    return (numerator / denominator - Decimal("1")) * BASIS_POINTS_PER_UNIT


def calculate_kline_features(klines: list[Kline], index: int) -> dict[str, str]:
    """Calculate stationary features using only bars at or before ``index``."""
    if index < max(FEATURE_WINDOWS):
        raise ValueError("Feature index does not have the required causal warmup.")
    current = klines[index]
    log_returns = [
        math.log(float(klines[position].close / klines[position - 1].close))
        for position in range(index - 59, index + 1)
    ]

    def realized_volatility(window: int) -> float:
        values = log_returns[-window:]
        return math.sqrt(sum(value * value for value in values) / len(values)) * 10_000

    def sma_distance(window: int) -> Decimal:
        values = [bar.close for bar in klines[index - window + 1 : index + 1]]
        average = sum(values, Decimal("0")) / Decimal(window)
        return _bps_ratio(current.close, average)

    def activity_ratio(column: str, window: int) -> Decimal:
        values = [
            Decimal(str(getattr(bar, column))) for bar in klines[index - window + 1 : index + 1]
        ]
        average = sum(values, Decimal("0")) / Decimal(window)
        current_value = Decimal(str(getattr(current, column)))
        return current_value / average if average > 0 else Decimal("0")

    taker_buy_ratio = (
        current.taker_buy_base_asset_volume / current.volume if current.volume > 0 else Decimal("0")
    )
    price_range = current.high - current.low
    close_location = (
        (current.close - current.low) / price_range if price_range > 0 else Decimal("0.5")
    )
    values: dict[str, Decimal | float] = {
        "log_return_1_bps": log_returns[-1] * 10_000,
        "return_3_bps": _bps_ratio(current.close, klines[index - 3].close),
        "return_5_bps": _bps_ratio(current.close, klines[index - 5].close),
        "return_15_bps": _bps_ratio(current.close, klines[index - 15].close),
        "realized_volatility_5_bps": realized_volatility(5),
        "realized_volatility_15_bps": realized_volatility(15),
        "realized_volatility_60_bps": realized_volatility(60),
        "distance_from_sma_5_bps": sma_distance(5),
        "distance_from_sma_15_bps": sma_distance(15),
        "distance_from_sma_60_bps": sma_distance(60),
        "base_volume_ratio_5": activity_ratio("volume", 5),
        "base_volume_ratio_15": activity_ratio("volume", 15),
        "trade_count_ratio_5": activity_ratio("trade_count", 5),
        "trade_count_ratio_15": activity_ratio("trade_count", 15),
        "taker_buy_ratio": taker_buy_ratio,
        "candle_body_bps": (current.close - current.open) / current.open * BASIS_POINTS_PER_UNIT,
        "candle_range_bps": price_range / current.open * BASIS_POINTS_PER_UNIT,
        "close_location": close_location,
    }
    return {name: format(float(values[name]), ".12g") for name in KLINE_FEATURE_COLUMNS}


def calculate_triple_barrier_outcome(
    klines: list[Kline],
    feature_index: int,
    *,
    horizon_bars: int,
    config: TripleBarrierConfig,
) -> BarrierOutcome | None:
    """Label a next-open long entry without allowing a future session to enter the window."""
    config.validate()
    if horizon_bars <= 0:
        raise ValueError("Horizon must contain at least one bar.")
    entry_index = feature_index + 1
    final_index = feature_index + horizon_bars
    if entry_index >= len(klines) or final_index >= len(klines):
        return None

    entry = klines[entry_index]
    entry_price = entry.open
    cost_bps = config.round_trip_cost_bps
    target_gross_bps = config.take_profit_bps + cost_bps
    stop_gross_bps = cost_bps - config.stop_loss_bps
    target_price = entry_price * (Decimal("1") + target_gross_bps / BASIS_POINTS_PER_UNIT)
    stop_price = entry_price * (Decimal("1") + stop_gross_bps / BASIS_POINTS_PER_UNIT)

    future_index = final_index
    exit_price = klines[final_index].close
    barrier_hit: BarrierHit = "time"
    for index in range(entry_index, final_index + 1):
        target_hit = klines[index].high >= target_price
        stop_hit = klines[index].low <= stop_price
        if target_hit and stop_hit:
            future_index = index
            exit_price = stop_price
            barrier_hit = "ambiguous_stop"
            break
        if stop_hit:
            future_index = index
            exit_price = stop_price
            barrier_hit = "stop"
            break
        if target_hit:
            future_index = index
            exit_price = target_price
            barrier_hit = "target"
            break

    gross_return_bps = _bps_ratio(exit_price, entry_price)
    net_return_bps = gross_return_bps - cost_bps
    if barrier_hit == "target":
        direction = 1
    elif barrier_hit in {"stop", "ambiguous_stop"}:
        direction = -1
    elif net_return_bps > config.neutral_threshold_bps:
        direction = 1
    elif net_return_bps < -config.neutral_threshold_bps:
        direction = -1
    else:
        direction = 0

    return BarrierOutcome(
        future_index=future_index,
        future_event_time_ms=klines[future_index].close_time_ms,
        entry_time_ms=entry.open_time_ms,
        entry_price=entry_price,
        exit_price=exit_price,
        gross_return_bps=gross_return_bps,
        net_return_bps=net_return_bps,
        direction=direction,
        barrier_hit=barrier_hit,
    )


def _resolve_manifest_path(raw_path: str, manifest_path: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute() or path.exists():
        return path
    return manifest_path.parent / path


def load_verified_sessions(
    manifest_path: Path,
) -> tuple[str, str, int, list[tuple[str, list[Kline]]]]:
    """Load normalized daily sessions only after binding them to manifest hashes."""
    with manifest_path.open(encoding="utf-8") as input_file:
        manifest = json.load(input_file)
    if manifest.get("source") != "binance_public_data" or manifest.get("market") != "spot":
        raise ValueError("Expected a Binance public Spot manifest.")
    if manifest.get("data_type") != "klines":
        raise ValueError("Historical kline dataset requires a kline manifest.")
    symbol = manifest.get("symbol")
    interval = manifest.get("interval")
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("Manifest symbol is invalid.")
    if interval not in SUPPORTED_SOURCE_INTERVALS_MS:
        raise ValueError("Manifest kline interval is not supported for feature generation.")
    interval_ms = SUPPORTED_SOURCE_INTERVALS_MS[interval]
    archives = manifest.get("archives")
    if not isinstance(archives, list) or not archives:
        raise ValueError("Manifest contains no source archives.")

    sessions = []
    seen_days: set[date] = set()
    for archive in archives:
        if not isinstance(archive, dict):
            raise ValueError("Manifest archive entry must be an object.")
        try:
            session_day = date.fromisoformat(str(archive["date"]))
            normalized_path = _resolve_manifest_path(str(archive["normalized_path"]), manifest_path)
            expected_digest = str(archive["normalized_sha256"])
        except (KeyError, ValueError) as error:
            raise ValueError("Manifest archive entry is incomplete.") from error
        if session_day in seen_days:
            raise ValueError("Manifest contains a duplicate source session date.")
        if file_sha256(normalized_path) != expected_digest:
            raise ValueError(f"Normalized SHA-256 mismatch for {normalized_path.name}.")
        seen_days.add(session_day)
        sessions.append(
            (
                f"binance_spot_{symbol}_{session_day.isoformat()}",
                read_kline_session(
                    normalized_path, interval_ms=interval_ms, expected_day=session_day
                ),
            )
        )
    sessions.sort(key=lambda item: item[1][0].open_time_ms)
    return symbol, interval, interval_ms, sessions


def _build_output_row(
    *,
    symbol: str,
    session_name: str,
    klines: list[Kline],
    feature_index: int,
    horizon_ms: int,
    config: TripleBarrierConfig,
    outcome: BarrierOutcome,
) -> dict[str, object]:
    current = klines[feature_index]
    future = klines[outcome.future_index]
    return {
        "schema_version": 1,
        "symbol": symbol,
        "source_session": session_name,
        "depth_event_time_ms": current.close_time_ms,
        "update_id": current.open_time_ms,
        "midpoint": str(current.close),
        **calculate_kline_features(klines, feature_index),
        "label_horizon_ms": horizon_ms,
        "neutral_threshold_bps": str(config.neutral_threshold_bps),
        "future_update_id": future.open_time_ms,
        "future_event_time_ms": outcome.future_event_time_ms,
        "actual_horizon_ms": outcome.future_event_time_ms - current.close_time_ms,
        "future_midpoint": str(outcome.exit_price),
        "future_return_bps": str(outcome.gross_return_bps),
        "net_return_bps": str(outcome.net_return_bps),
        "target_direction": outcome.direction,
        "barrier_hit": outcome.barrier_hit,
        "entry_time_ms": outcome.entry_time_ms,
        "entry_price": str(outcome.entry_price),
        "exit_price": str(outcome.exit_price),
        "holding_period_ms": outcome.future_event_time_ms - outcome.entry_time_ms + 1,
        "taker_fee_bps": str(config.taker_fee_bps),
        "slippage_bps": str(config.slippage_bps),
        "round_trip_cost_bps": str(config.round_trip_cost_bps),
        "take_profit_bps": str(config.take_profit_bps),
        "stop_loss_bps": str(config.stop_loss_bps),
    }


def build_historical_kline_datasets(
    manifest_path: Path,
    output_directory: Path,
    *,
    horizons_minutes: tuple[int, ...],
    config: TripleBarrierConfig,
) -> KlineDatasetReport:
    """Build one session-aware labeled CSV per requested prediction horizon."""
    config.validate()
    if not horizons_minutes or any(horizon <= 0 for horizon in horizons_minutes):
        raise ValueError("At least one positive horizon is required.")
    if len(set(horizons_minutes)) != len(horizons_minutes):
        raise ValueError("Prediction horizons must be unique.")
    symbol, interval, interval_ms, sessions = load_verified_sessions(manifest_path)
    horizon_specs = []
    for horizon_minutes in sorted(horizons_minutes):
        horizon_ms = horizon_minutes * 60_000
        if horizon_ms % interval_ms != 0:
            raise ValueError("Each prediction horizon must be a multiple of the source interval.")
        horizon_specs.append((horizon_minutes, horizon_ms, horizon_ms // interval_ms))

    output_directory.mkdir(parents=True, exist_ok=True)
    reports = []
    for horizon_minutes, horizon_ms, horizon_bars in horizon_specs:
        output_path = output_directory / f"{symbol}_{interval}_h{horizon_minutes}m_labeled.csv"
        temporary_path = output_path.with_name(f"{output_path.name}.part")
        counts = {-1: 0, 0: 0, 1: 0}
        hits = {"target": 0, "stop": 0, "ambiguous_stop": 0, "time": 0}
        rows_written = 0
        try:
            with temporary_path.open("w", encoding="utf-8", newline="") as output_file:
                writer = csv.DictWriter(output_file, fieldnames=OUTPUT_COLUMNS)
                writer.writeheader()
                for session_name, klines in sessions:
                    for feature_index in range(max(FEATURE_WINDOWS), len(klines)):
                        outcome = calculate_triple_barrier_outcome(
                            klines,
                            feature_index,
                            horizon_bars=horizon_bars,
                            config=config,
                        )
                        if outcome is None:
                            continue
                        writer.writerow(
                            _build_output_row(
                                symbol=symbol,
                                session_name=session_name,
                                klines=klines,
                                feature_index=feature_index,
                                horizon_ms=horizon_ms,
                                config=config,
                                outcome=outcome,
                            )
                        )
                        counts[outcome.direction] += 1
                        hits[outcome.barrier_hit] += 1
                        rows_written += 1
            if rows_written == 0:
                raise ValueError(f"Horizon {horizon_minutes}m produced no labeled rows.")
            os.replace(temporary_path, output_path)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
        reports.append(
            HorizonReport(
                horizon_minutes=horizon_minutes,
                output_path=output_path,
                rows=rows_written,
                down_labels=counts[-1],
                neutral_labels=counts[0],
                up_labels=counts[1],
                target_hits=hits["target"],
                stop_hits=hits["stop"],
                ambiguous_stop_hits=hits["ambiguous_stop"],
                time_exits=hits["time"],
            )
        )

    output_manifest = output_directory / "manifest.json"
    payload = {
        "schema_version": 1,
        "source_manifest": str(manifest_path.resolve()),
        "source_manifest_sha256": file_sha256(manifest_path),
        "market": "spot",
        "direction": "long_only",
        "symbol": symbol,
        "source_interval": interval,
        "source_sessions": [name for name, _ in sessions],
        "input_rows": sum(len(klines) for _, klines in sessions),
        "warmup_rows_per_session": max(FEATURE_WINDOWS),
        "feature_columns": list(KLINE_FEATURE_COLUMNS),
        "labeling": {**asdict(config), "round_trip_cost_bps": config.round_trip_cost_bps},
        "horizons": [
            {
                **asdict(report),
                "output_path": str(report.output_path.resolve()),
                "sha256": file_sha256(report.output_path),
            }
            for report in reports
        ],
    }
    output_manifest.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return KlineDatasetReport(
        source_manifest=manifest_path,
        output_manifest=output_manifest,
        symbol=symbol,
        source_interval=interval,
        source_sessions=tuple(name for name, _ in sessions),
        input_rows=payload["input_rows"],
        warmup_rows_per_session=max(FEATURE_WINDOWS),
        horizons=tuple(reports),
    )


def parse_args() -> argparse.Namespace:
    """Parse historical feature and label configuration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--horizons-minutes", type=int, nargs="+", default=(1, 5, 15))
    parser.add_argument("--take-profit-bps", type=Decimal, default=Decimal("20"))
    parser.add_argument("--stop-loss-bps", type=Decimal, default=Decimal("40"))
    parser.add_argument("--neutral-threshold-bps", type=Decimal, default=Decimal("5"))
    parser.add_argument("--taker-fee-bps", type=Decimal, default=Decimal("10"))
    parser.add_argument("--slippage-bps", type=Decimal, default=Decimal("2"))
    return parser.parse_args()


def main() -> None:
    """Build and describe historical multi-horizon datasets."""
    args = parse_args()
    config = TripleBarrierConfig(
        take_profit_bps=args.take_profit_bps,
        stop_loss_bps=args.stop_loss_bps,
        neutral_threshold_bps=args.neutral_threshold_bps,
        taker_fee_bps=args.taker_fee_bps,
        slippage_bps=args.slippage_bps,
    )
    report = build_historical_kline_datasets(
        args.manifest,
        args.output_directory,
        horizons_minutes=tuple(args.horizons_minutes),
        config=config,
    )
    print(f"Source sessions: {len(report.source_sessions)}")
    print(f"Input rows: {report.input_rows}")
    for horizon in report.horizons:
        print(
            f"{horizon.horizon_minutes}m: rows={horizon.rows}, "
            f"down={horizon.down_labels}, neutral={horizon.neutral_labels}, "
            f"up={horizon.up_labels}"
        )
    print(f"Manifest: {report.output_manifest.resolve()}")


if __name__ == "__main__":
    main()
