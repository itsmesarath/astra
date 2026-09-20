"""Frozen prediction replay and file-level evaluation-session selection."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from ai_trader.backtesting.candle_replay import CandleSession, ReplayConfig
from ai_trader.backtesting.economic_metrics import EconomicConfig
from ai_trader.features import kline_dataset
from ai_trader.features.kline_dataset import (
    KLINE_FEATURE_COLUMNS,
    KLINE_SOURCE_COLUMNS,
    Kline,
    TripleBarrierConfig,
    load_verified_sessions,
)
from ai_trader.trading.decision_policy import DecisionPolicy
from ai_trader.training import walk_forward
from ai_trader.training.replay_evaluation import FrozenPredictions, replay_frozen_predictions
from ai_trader.training.train_linear import TrainingConfig

D = Decimal
LONG = (0.05, 0.05, 0.9)
FLAT = (0.05, 0.9, 0.05)
POLICY = DecisionPolicy(allow_short=False)


def bar(index, price="100", start=0):
    price = D(price)
    return Kline(
        start + index * 60000,
        price,
        price,
        price,
        price,
        D("10"),
        start + (index + 1) * 60000 - 1,
        price * 10,
        10,
        D("5"),
    )


def compare(predictions=None, candles=None, **kwargs):
    return replay_frozen_predictions(
        predictions if predictions is not None else (FrozenPredictions("eval", (59999,), (LONG,)),),
        candles
        if candles is not None
        else (CandleSession("eval", tuple(bar(i) for i in range(4))),),
        POLICY,
        ReplayConfig(holding_bars=1),
        evaluated_sessions=("eval",),
        held_out_sessions=("held-out",),
        **kwargs,
    )


def test_same_predictions_and_signals_drive_both_scenarios():
    predictions = (FrozenPredictions("eval", (59999, 119999), (LONG, FLAT)),)
    report = compare(predictions)
    assert report.next_open.input_sha256 == report.delayed_one_bar.input_sha256
    assert report.next_open.trades[0].signal_time_ms == 59999
    assert report.delayed_one_bar.trades[0].signal_time_ms == 59999
    assert report.next_open.trades[0].entry.event_time_ms == 60000
    assert report.delayed_one_bar.trades[0].entry.event_time_ms == 120000
    assert report == compare(predictions)
    assert len(report.predictions_sha256) == 64
    changed = (replace(predictions[0], probabilities=((0.04, 0.06, 0.9), FLAT)),)
    assert compare(changed).predictions_sha256 != report.predictions_sha256


@pytest.mark.parametrize(
    "predictions",
    [
        (),
        (FrozenPredictions("held-out", (59999,), (LONG,)),),
        (
            FrozenPredictions("eval", (59999,), (LONG,)),
            FrozenPredictions("extra", (59999,), (LONG,)),
        ),
    ],
)
def test_rejects_wrong_prediction_scope(predictions):
    with pytest.raises(ValueError, match="exactly the ordered evaluation"):
        compare(predictions)


def test_rejects_extra_holdout_before_inspecting_candles():
    with pytest.raises(ValueError, match="not holdouts"):
        compare(candles=(CandleSession("eval", (bar(0),)), CandleSession("held-out", None)))


@pytest.mark.parametrize(
    "times,probabilities",
    [
        ((60000,), (FLAT,)),  # Even flat decisions require close alignment.
        ((59999, 59999), (LONG, LONG)),
        ((119999, 59999), (LONG, LONG)),
        ((59999,), ()),
        ((), ()),
        ((59999,), ((float("nan"), 0, 1),)),
        ((59999,), ((0, 0, 0),)),
    ],
)
def test_invalid_predictions_fail_closed(times, probabilities):
    with pytest.raises(ValueError):
        compare((FrozenPredictions("eval", times, probabilities),))


def test_rejects_external_signals():
    with pytest.raises(ValueError, match="must not supply signals"):
        compare(candles=(CandleSession("eval", (bar(0), bar(1)), (59999,)),))


@pytest.mark.parametrize(
    "policy,config,heldout",
    [
        (DecisionPolicy(), ReplayConfig(), ("held-out",)),
        (POLICY, ReplayConfig(entry_delay_bars=1), ("held-out",)),
        (POLICY, ReplayConfig(), ("eval",)),
    ],
)
def test_rejects_short_policy_nonstandard_delay_and_holdout_overlap(policy, config, heldout):
    with pytest.raises(ValueError):
        replay_frozen_predictions(
            (FrozenPredictions("eval", (59999,), (LONG,)),),
            (CandleSession("eval", (bar(0), bar(1))),),
            policy,
            config,
            evaluated_sessions=("eval",),
            held_out_sessions=heldout,
        )


def research_fixture(tmp_path):
    """Only evaluation candle files exist; every other manifest entry is poisoned."""
    rows, archives, names = [], [], []
    first_day = datetime(2025, 1, 1, tzinfo=UTC)
    for day_index in range(6):
        day = first_day + timedelta(days=day_index)
        start = int(day.timestamp() * 1000)
        name = f"binance_spot_BTCUSDT_{day.date().isoformat()}"
        names.append(name)
        for index, direction in enumerate((-1, 0, 1)):
            event = start + (index + 1) * 60000 - 1
            row = {feature: str(direction * 0.1) for feature in KLINE_FEATURE_COLUMNS}
            row.update(
                taker_buy_ratio="0.5",
                close_location="0.5",
                source_session=name,
                depth_event_time_ms=str(event),
                future_event_time_ms=str(event + 60000),
                entry_time_ms=str(event + 1),
                net_return_bps=str(direction * 10),
                target_direction=str(direction),
            )
            if day_index == 5:
                row.update(
                    net_return_bps="poison", target_direction="poison", return_3_bps="poison"
                )
            rows.append(row)
        archive = {"date": day.date().isoformat()}
        if day_index in (3, 4):
            path = tmp_path / f"{day.date()}.csv"
            with path.open("w", encoding="utf-8", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=KLINE_SOURCE_COLUMNS)
                writer.writeheader()
                for index in range(6):
                    candle = bar(index, str(100 + index), start)
                    writer.writerow(
                        {
                            "open_time_ms": candle.open_time_ms,
                            "open": candle.open,
                            "high": candle.high,
                            "low": candle.low,
                            "close": candle.close,
                            "volume": candle.volume,
                            "close_time_ms": candle.close_time_ms,
                            "quote_asset_volume": candle.quote_asset_volume,
                            "trade_count": 10,
                            "taker_buy_base_asset_volume": 5,
                            "taker_buy_quote_asset_volume": candle.close * 5,
                            "ignore": 0,
                        }
                    )
            archive.update(
                normalized_path=path.name,
                normalized_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        else:
            archive.update(normalized_path="MUST_NOT_OPEN.csv", normalized_sha256="poison")
        archives.append(archive)
    dataset = tmp_path / "dataset.csv"
    with dataset.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source": "binance_public_data",
                "market": "spot",
                "data_type": "klines",
                "symbol": "BTCUSDT",
                "interval": "1m",
                "archives": archives,
            }
        ),
        encoding="utf-8",
    )
    return dataset, manifest, tuple(names)


def test_walk_forward_freezes_once_replays_both_and_never_opens_reserved_archives(
    tmp_path, monkeypatch
):
    dataset, manifest, names = research_fixture(tmp_path)
    loaded = []
    predictions_called = []
    original_read = kline_dataset.read_kline_session

    def track_read(path, **kwargs):
        loaded.append(path.name)
        assert path.name != "MUST_NOT_OPEN.csv"
        return original_read(path, **kwargs)

    def predict(model, features):
        predictions_called.append(len(features))
        return np.asarray([LONG] * len(features))

    monkeypatch.setattr(kline_dataset, "read_kline_session", track_read)
    monkeypatch.setattr(walk_forward, "predict_probabilities", predict)
    training = TrainingConfig(max_epochs=2, patience=1, device="cpu")
    capital = EconomicConfig(starting_balance=1000)
    replay_config = ReplayConfig(
        capital=capital,
        holding_bars=1,
        barriers=TripleBarrierConfig(
            taker_fee_bps=D("0"),
            slippage_bps=D("0"),
        ),
    )
    report = walk_forward.run_walk_forward(
        dataset,
        training,
        policy=POLICY,
        economic_config=capital,
        replay_manifest=manifest,
        replay_config=replay_config,
    )
    assert predictions_called == [3, 3]  # No fitting/predicting again per replay scenario.
    assert loaded == ["2025-01-04.csv", "2025-01-05.csv"]
    assert report.evaluated_sessions == names[3:5]
    assert report.held_out_sessions == names[5:]
    replay = report.candle_replay
    assert replay.next_open.input_sha256 == replay.delayed_one_bar.input_sha256
    for scenario in (replay.next_open, replay.delayed_one_bar):
        assert tuple(item.source_session for item in scenario.sessions) == names[3:5]
        assert scenario.sessions[1].starting_balance == scenario.sessions[0].ending_balance
    assert report.folds[0].predictions.probabilities == (LONG,) * 3
    output = tmp_path / "walk_forward.json"
    walk_forward.write_walk_forward_report(output, report, training, POLICY)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 5
    assert payload["candle_replay"]["predictions_sha256"] == replay.predictions_sha256
    assert payload["candle_replay"]["next_open"]["config"]["entry_delay_bars"] == 0
    assert payload["candle_replay"]["delayed_one_bar"]["config"]["entry_delay_bars"] == 1
    assert payload["aggregate_economics"] is not None
    # Standalone comparison of frozen values performs no model or file access.
    _, _, _, sources = load_verified_sessions(manifest, selected_sessions=names[3:5])
    restored = replay_frozen_predictions(
        tuple(
            FrozenPredictions(
                fold["predictions"]["source_session"],
                tuple(fold["predictions"]["event_times_ms"]),
                tuple(tuple(row) for row in fold["predictions"]["probabilities"]),
            )
            for fold in payload["folds"]
        ),
        tuple(CandleSession(name, tuple(candles)) for name, candles in sources),
        POLICY,
        replay_config,
        evaluated_sessions=names[3:5],
        held_out_sessions=names[5:],
    )
    assert restored == replay
    with pytest.raises(FileExistsError):
        walk_forward.write_walk_forward_report(output, report, training, POLICY)
    with pytest.raises(ValueError, match="policy must match"):
        walk_forward.write_walk_forward_report(output, report, training, DecisionPolicy())


def test_selected_loader_rejects_missing_names_before_opening_archives(tmp_path, monkeypatch):
    _, manifest, names = research_fixture(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("No archive should be opened")

    monkeypatch.setattr(kline_dataset, "read_kline_session", forbidden)
    with pytest.raises(ValueError, match="missing selected"):
        load_verified_sessions(manifest, selected_sessions=(names[3], "unknown"))


def test_replay_requires_matching_capital_before_fitting(tmp_path, monkeypatch):
    dataset, manifest, _ = research_fixture(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid replay settings must fail before fitting")

    monkeypatch.setattr(walk_forward, "fit_linear_baseline", forbidden)
    with pytest.raises(ValueError, match="identical capital"):
        walk_forward.run_walk_forward(
            dataset,
            TrainingConfig(device="cpu"),
            replay_manifest=manifest,
            replay_config=ReplayConfig(capital=EconomicConfig(starting_balance=10)),
        )


def test_cli_requires_explicit_replay_horizon(monkeypatch):
    monkeypatch.setattr("sys.argv", ["walk_forward", "unused.csv", "--replay-manifest", "raw.json"])
    with pytest.raises(SystemExit):
        walk_forward.parse_args()


def test_selected_loader_rejects_archive_changed_during_read(tmp_path, monkeypatch):
    _, manifest, names = research_fixture(tmp_path)
    original_read = kline_dataset.read_kline_session

    def changing_read(path, **kwargs):
        candles = original_read(path, **kwargs)
        path.write_text("changed", encoding="utf-8")
        return candles

    monkeypatch.setattr(kline_dataset, "read_kline_session", changing_read)
    with pytest.raises(ValueError, match="changed during session loading"):
        load_verified_sessions(manifest, selected_sessions=names[3:5])
