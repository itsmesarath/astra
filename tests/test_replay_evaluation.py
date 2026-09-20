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
    KLINE_SOURCE_COLUMNS,
    Kline,
    TripleBarrierConfig,
    load_verified_sessions,
)
from ai_trader.trading.decision_policy import DecisionPolicy
from ai_trader.training import walk_forward
from ai_trader.training.feature_provenance import verify_replay_features
from ai_trader.training.replay_evaluation import FrozenPredictions, replay_frozen_predictions
from ai_trader.training.session_data import load_session_dataset
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
        candles = [bar(index, str(100 + index), start) for index in range(66)]
        for index, direction in enumerate((-1, 0, 1)):
            event = candles[index + 60].close_time_ms
            row = kline_dataset.calculate_kline_features(candles, index + 60)
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
                for candle in candles:
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
    assert payload["schema_version"] == 6
    provenance = payload["replay_feature_provenance"]
    assert provenance["scope"] == "evaluation_features_only_not_fit_tune_or_outcomes"
    assert provenance["warmup_bars"] == 60
    assert [item["source_session"] for item in provenance["sessions"]] == list(names[3:5])
    assert all(item["rows"] == 3 for item in provenance["sessions"])
    assert len(provenance["calculation_module_sha256"]) == 64
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


def provenance_inputs(tmp_path):
    dataset, manifest, names = research_fixture(tmp_path)
    partitions = load_session_dataset(dataset, held_out_session_count=1).sessions[3:]
    _, _, _, sources = load_verified_sessions(manifest, selected_sessions=names[3:5])
    candles = tuple(CandleSession(name, tuple(bars)) for name, bars in sources)
    return partitions, candles


def test_feature_verification_is_causal_and_hashes_exact_inputs(tmp_path, monkeypatch):
    partitions, candles = provenance_inputs(tmp_path)
    original = kline_dataset.calculate_kline_features
    visited = []

    def checked_calculate(window, index):
        assert len(window) == 61
        assert index == 60
        visited.append(window[-1].close_time_ms)
        return original(window, index)

    monkeypatch.setattr(kline_dataset, "calculate_kline_features", checked_calculate)
    proof = verify_replay_features(partitions, candles)
    assert visited == [time for part in partitions for time in part.event_times_ms]
    assert proof == verify_replay_features(partitions, candles)
    assert all(
        len(item.features_sha256) == len(item.candles_sha256) == 64 for item in proof.sessions
    )
    # Future candles are hashed, but never used to recompute earlier features.
    future = replace(candles[0].candles[-1], volume=D("20"))
    changed = (replace(candles[0], candles=(*candles[0].candles[:-1], future)), candles[1])
    later = verify_replay_features(partitions, changed)
    assert later.sessions[0].candles_sha256 != proof.sessions[0].candles_sha256
    assert later.sessions[0].features_sha256 == proof.sessions[0].features_sha256


@pytest.mark.parametrize("column", ["return_3_bps", "taker_buy_ratio", "base_volume_ratio_5"])
def test_single_float_step_feature_mismatch_is_not_silently_tolerated(tmp_path, column):
    partitions, candles = provenance_inputs(tmp_path)
    features = partitions[0].partition.features.copy()
    index = partitions[0].partition.feature_names.index(column)
    features[0, index] = np.nextafter(features[0, index], np.inf)
    changed = replace(partitions[0], partition=replace(partitions[0].partition, features=features))
    with pytest.raises(ValueError, match=f"provenance mismatch in {column}"):
        verify_replay_features((changed, partitions[1]), candles)


def test_raw_warmup_activity_change_rejects_unchanged_features(tmp_path):
    partitions, candles = provenance_inputs(tmp_path)
    bars = list(candles[0].candles)
    bars[59] = replace(bars[59], volume=D("20"))
    with pytest.raises(ValueError, match="base_volume_ratio"):
        verify_replay_features(partitions, (replace(candles[0], candles=tuple(bars)), candles[1]))


def test_missing_warmup_is_not_borrowed_from_previous_session(tmp_path):
    partitions, candles = provenance_inputs(tmp_path)
    shortened = replace(candles[0], candles=candles[0].candles[1:])
    with pytest.raises(ValueError, match="insufficient in-session feature warmup"):
        verify_replay_features(partitions, (shortened, candles[1]))


@pytest.mark.parametrize("failure", ["scope", "timestamps", "shape", "schema", "nonfinite"])
def test_invalid_feature_provenance_inputs_fail_closed(tmp_path, failure):
    partitions, candles = provenance_inputs(tmp_path)
    first = partitions[0]
    if failure == "scope":
        first = replace(first, name="held-out")
    elif failure == "timestamps":
        first = replace(first, event_times_ms=(first.event_times_ms[0],) * 3)
    elif failure == "shape":
        first = replace(
            first, partition=replace(first.partition, features=first.partition.features[:1])
        )
    elif failure == "schema":
        first = replace(first, partition=replace(first.partition, feature_names=("wrong",)))
    else:
        features = first.partition.features.copy()
        features[0, 0] = np.nan
        first = replace(first, partition=replace(first.partition, features=features))
    with pytest.raises(ValueError):
        verify_replay_features((first, partitions[1]), candles)


def test_feature_mismatch_prevents_any_model_fit(tmp_path, monkeypatch):
    dataset, manifest, names = research_fixture(tmp_path)
    with dataset.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames
        rows = list(reader)
    for row in rows:
        if row["source_session"] == names[3]:
            row["return_3_bps"] = "12345"
            break
    with dataset.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    def forbidden(*args, **kwargs):
        raise AssertionError("Mismatched evaluation features must fail before fitting")

    monkeypatch.setattr(walk_forward, "fit_linear_baseline", forbidden)
    with pytest.raises(ValueError, match="feature provenance mismatch"):
        walk_forward.run_walk_forward(
            dataset,
            TrainingConfig(device="cpu"),
            replay_manifest=manifest,
            replay_config=ReplayConfig(holding_bars=1),
        )
