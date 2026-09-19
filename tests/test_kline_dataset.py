"""Tests for causal, session-safe historical kline datasets."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from ai_trader.features.kline_dataset import (
    KLINE_SOURCE_COLUMNS,
    Kline,
    TripleBarrierConfig,
    build_historical_kline_datasets,
    calculate_kline_features,
    calculate_triple_barrier_outcome,
    read_kline_session,
)
from ai_trader.training.split_dataset import split_labeled_dataset

INTERVAL_MS = 60_000


def make_kline(
    index: int,
    *,
    start_ms: int = 0,
    open_price: str = "100",
    high: str = "100.01",
    low: str = "99.99",
    close: str = "100",
) -> Kline:
    """Create one valid minute candle."""
    open_time_ms = start_ms + index * INTERVAL_MS
    return Kline(
        open_time_ms=open_time_ms,
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("10"),
        close_time_ms=open_time_ms + INTERVAL_MS - 1,
        quote_asset_volume=Decimal("1000"),
        trade_count=20,
        taker_buy_base_asset_volume=Decimal("4"),
    )


def epoch_ms(day: date) -> int:
    """Return the UTC epoch milliseconds at the start of a day."""
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)


def write_normalized_session(path: Path, day: date, *, rows: int = 80) -> None:
    """Write one continuous normalized kline session."""
    path.parent.mkdir(parents=True, exist_ok=True)
    start_ms = epoch_ms(day)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=KLINE_SOURCE_COLUMNS)
        writer.writeheader()
        for index in range(rows):
            open_price = Decimal("100") + Decimal(index) / Decimal("100")
            close = open_price + Decimal("0.005")
            writer.writerow(
                {
                    "open_time_ms": start_ms + index * INTERVAL_MS,
                    "open": open_price,
                    "high": open_price + Decimal("0.01"),
                    "low": open_price - Decimal("0.01"),
                    "close": close,
                    "volume": Decimal("10") + index,
                    "close_time_ms": start_ms + (index + 1) * INTERVAL_MS - 1,
                    "quote_asset_volume": Decimal("1000") + index,
                    "trade_count": 20 + index,
                    "taker_buy_base_asset_volume": Decimal("4") + Decimal(index) / Decimal("2"),
                    "taker_buy_quote_asset_volume": Decimal("400") + index,
                    "ignore": 0,
                }
            )


def write_source_manifest(root: Path, days: list[date]) -> Path:
    """Create normalized daily files and a downloader-compatible manifest."""
    archives = []
    for day in days:
        normalized_path = root / f"BTCUSDT-1m-{day.isoformat()}.csv"
        write_normalized_session(normalized_path, day)
        archives.append(
            {
                "date": day.isoformat(),
                "normalized_path": str(normalized_path),
                "normalized_sha256": hashlib.sha256(normalized_path.read_bytes()).hexdigest(),
            }
        )
    manifest_path = root / "source_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": "binance_public_data",
                "market": "spot",
                "symbol": "BTCUSDT",
                "data_type": "klines",
                "interval": "1m",
                "archives": archives,
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read generated dataset rows."""
    with path.open(encoding="utf-8", newline="") as input_file:
        return list(csv.DictReader(input_file))


def test_features_use_only_current_and_prior_bars() -> None:
    """Changing a future price must not affect the current feature vector."""
    klines = [make_kline(index) for index in range(63)]
    original = calculate_kline_features(klines, 60)
    klines[61] = make_kline(61, high="200", close="150")

    assert calculate_kline_features(klines, 60) == original
    assert Decimal(original["taker_buy_ratio"]) == Decimal("0.4")
    assert Decimal(original["base_volume_ratio_5"]) == Decimal("1")


def test_triple_barrier_resolves_same_bar_ambiguity_as_stop() -> None:
    """When candle ordering is unknowable, loss-first treatment prevents optimistic bias."""
    klines = [
        make_kline(0),
        make_kline(1, high="101", low="99"),
    ]
    outcome = calculate_triple_barrier_outcome(
        klines,
        0,
        horizon_bars=1,
        config=TripleBarrierConfig(
            take_profit_bps=Decimal("50"),
            stop_loss_bps=Decimal("50"),
            neutral_threshold_bps=Decimal("1"),
            taker_fee_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        ),
    )

    assert outcome is not None
    assert outcome.barrier_hit == "ambiguous_stop"
    assert outcome.direction == -1
    assert outcome.net_return_bps == Decimal("-50.000")


def test_time_barrier_classifies_cost_adjusted_return() -> None:
    """A vertical exit must subtract both entry and exit costs before classification."""
    klines = [
        make_kline(0),
        make_kline(1, high="100.2", low="99.9", close="100.15"),
    ]
    outcome = calculate_triple_barrier_outcome(
        klines,
        0,
        horizon_bars=1,
        config=TripleBarrierConfig(
            take_profit_bps=Decimal("100"),
            stop_loss_bps=Decimal("50"),
            neutral_threshold_bps=Decimal("5"),
            taker_fee_bps=Decimal("5"),
            slippage_bps=Decimal("1"),
        ),
    )

    assert outcome is not None
    assert outcome.barrier_hit == "time"
    assert outcome.gross_return_bps == Decimal("15.0000")
    assert outcome.net_return_bps == Decimal("3.0000")
    assert outcome.direction == 0


def test_rejects_stop_loss_that_is_consumed_by_round_trip_costs() -> None:
    """A stop above the effective entry value would trigger immediately and is invalid."""
    with pytest.raises(ValueError, match="Stop loss must exceed"):
        TripleBarrierConfig(
            stop_loss_bps=Decimal("20"),
            taker_fee_bps=Decimal("10"),
            slippage_bps=Decimal("2"),
        ).validate()


def test_rejects_kline_gaps_within_a_source_session(tmp_path: Path) -> None:
    """Rolling windows cannot silently span missing source bars."""
    day = date(2025, 1, 2)
    path = tmp_path / "gap.csv"
    write_normalized_session(path, day, rows=3)
    rows = read_rows(path)
    rows[2]["open_time_ms"] = str(int(rows[2]["open_time_ms"]) + INTERVAL_MS)
    rows[2]["close_time_ms"] = str(int(rows[2]["close_time_ms"]) + INTERVAL_MS)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=KLINE_SOURCE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="gap or duplicate"):
        read_kline_session(path, interval_ms=INTERVAL_MS, expected_day=day)


def test_builds_each_horizon_without_crossing_daily_sessions(tmp_path: Path) -> None:
    """Every feature warmup and future barrier window must stay inside one UTC day."""
    days = [date(2025, 1, 2), date(2025, 1, 3)]
    manifest_path = write_source_manifest(tmp_path, days)
    report = build_historical_kline_datasets(
        manifest_path,
        tmp_path / "output",
        horizons_minutes=(1, 5, 15),
        config=TripleBarrierConfig(
            take_profit_bps=Decimal("100"),
            stop_loss_bps=Decimal("100"),
            neutral_threshold_bps=Decimal("2"),
            taker_fee_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        ),
    )

    assert report.input_rows == 160
    assert [horizon.rows for horizon in report.horizons] == [38, 30, 10]
    for horizon in report.horizons:
        rows = read_rows(horizon.output_path)
        assert {row["source_session"] for row in rows} == {
            "binance_spot_BTCUSDT_2025-01-02",
            "binance_spot_BTCUSDT_2025-01-03",
        }
        for row in rows:
            feature_day = datetime.fromtimestamp(
                int(row["depth_event_time_ms"]) / 1000, tz=UTC
            ).date()
            future_day = datetime.fromtimestamp(
                int(row["future_event_time_ms"]) / 1000, tz=UTC
            ).date()
            assert future_day == feature_day

    with report.output_manifest.open(encoding="utf-8") as input_file:
        output_manifest = json.load(input_file)
    assert output_manifest["direction"] == "long_only"
    assert output_manifest["source_sessions"] == [
        "binance_spot_BTCUSDT_2025-01-02",
        "binance_spot_BTCUSDT_2025-01-03",
    ]
    assert output_manifest["warmup_rows_per_session"] == 60


def test_rejects_tampered_normalized_source(tmp_path: Path) -> None:
    """Feature generation must bind normalized bytes to the downloader manifest."""
    manifest_path = write_source_manifest(tmp_path, [date(2025, 1, 2)])
    normalized_path = tmp_path / "BTCUSDT-1m-2025-01-02.csv"
    with normalized_path.open("a", encoding="utf-8") as output_file:
        output_file.write("tampered\n")

    with pytest.raises(ValueError, match="Normalized SHA-256 mismatch"):
        build_historical_kline_datasets(
            manifest_path,
            tmp_path / "output",
            horizons_minutes=(1,),
            config=TripleBarrierConfig(),
        )


def test_generated_sessions_remain_exclusive_during_split(tmp_path: Path) -> None:
    """The common dataset columns must drive whole-day train/validation/test assignment."""
    first_day = date(2025, 1, 2)
    days = [first_day + timedelta(days=index) for index in range(3)]
    manifest_path = write_source_manifest(tmp_path, days)
    report = build_historical_kline_datasets(
        manifest_path,
        tmp_path / "output",
        horizons_minutes=(1,),
        config=TripleBarrierConfig(
            taker_fee_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        ),
    )

    split = split_labeled_dataset(
        report.horizons[0].output_path,
        tmp_path / "split",
        train_fraction=0.6,
        validation_fraction=0.2,
    )

    assert split.train.source_sessions == ("binance_spot_BTCUSDT_2025-01-02",)
    assert split.validation.source_sessions == ("binance_spot_BTCUSDT_2025-01-03",)
    assert split.test.source_sessions == ("binance_spot_BTCUSDT_2025-01-04",)
