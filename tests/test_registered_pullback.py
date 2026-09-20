"""Registered runner orchestration, using synthetic candles only."""

import json
from decimal import Decimal

import pytest

from ai_trader.features.kline_dataset import Kline
from ai_trader.research import registered_pullback as runner
from ai_trader.research.registration import register_pullback

NAME = "binance_spot_BTCUSDT_2025-01-01"
RESERVED = "binance_spot_BTCUSDT_2025-01-02"


def setup(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source": "binance_public_data",
                "market": "spot",
                "data_type": "klines",
                "symbol": "BTCUSDT",
                "interval": "5m",
                "archives": [
                    {
                        "date": "2025-01-01",
                        "normalized_path": "fake.csv",
                        "normalized_sha256": "a" * 64,
                    },
                    {"date": "2025-01-02", "normalized_path": "MUST-NOT-OPEN.csv"},
                ],
            }
        ),
        encoding="utf-8",
    )
    registration = tmp_path / "registration.json"
    register_pullback(
        manifest,
        registration,
        trial_id="synthetic",
        research_sessions=(NAME,),
        reserved_sessions=(RESERVED,),
    )
    d = Decimal
    candles = [
        Kline(
            i * 300000, d(100), d(101), d(99), d(100), d(10), (i + 1) * 300000 - 1, d(1000), 1, d(5)
        )
        for i in range(100)
    ]
    calls = []

    def loader(path, *, selected_sessions):
        calls.append(selected_sessions)
        assert path == manifest
        assert selected_sessions == (NAME,)
        return "BTCUSDT", "5m", 300000, [(NAME, candles)]

    monkeypatch.setattr(runner, "load_verified_sessions", loader)
    return manifest, registration, tmp_path / "result.json", calls


def test_registered_run_selects_only_research_and_saves_every_scenario(tmp_path, monkeypatch):
    _, registration, output, calls = setup(tmp_path, monkeypatch)
    result = runner.run_registered_pullback(registration, output)
    assert calls == [(NAME,)]
    assert result == json.loads(output.read_text())
    assert len(result["scenarios"]) == 6
    assert result["promotion_allowed"] is False
    assert result["status"] == "completed_research_only"
    assert result["signal_evidence"][0]["source_session"] == NAME
    with pytest.raises(FileExistsError):
        runner.run_registered_pullback(registration, output)
    assert len(calls) == 1


def test_changed_manifest_blocks_before_loader(tmp_path, monkeypatch):
    manifest, registration, output, calls = setup(tmp_path, monkeypatch)
    manifest.write_text(manifest.read_text() + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="manifest changed"):
        runner.run_registered_pullback(registration, output)
    assert not calls
    assert not output.exists()


def test_failed_trial_persists_non_overwritable_failure(tmp_path, monkeypatch):
    _, registration, output, _ = setup(tmp_path, monkeypatch)

    def fail(*args, **kwargs):
        raise ValueError("synthetic failure")

    monkeypatch.setattr(runner, "load_verified_sessions", fail)
    with pytest.raises(ValueError):
        runner.run_registered_pullback(registration, output)
    assert json.loads(output.read_text())["status"] == "failed"
    with pytest.raises(FileExistsError):
        runner.run_registered_pullback(registration, output)


def test_wrong_loaded_scope_rejected(tmp_path, monkeypatch):
    _, registration, output, _ = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        runner,
        "load_verified_sessions",
        lambda *a, **kw: ("BTCUSDT", "5m", 300000, [(RESERVED, [])]),
    )
    with pytest.raises(ValueError, match="selection"):
        runner.run_registered_pullback(registration, output)
    assert json.loads(output.read_text())["status"] == "failed"


def test_changed_registration_during_replay_is_not_success(tmp_path, monkeypatch):
    _, registration, output, _ = setup(tmp_path, monkeypatch)
    original = runner.replay_pullback_scenarios

    def changed(sessions):
        result = original(sessions)
        registration.write_text(registration.read_text() + " ", encoding="utf-8")
        return result

    monkeypatch.setattr(runner, "replay_pullback_scenarios", changed)
    with pytest.raises(ValueError, match="changed during"):
        runner.run_registered_pullback(registration, output)
    assert json.loads(output.read_text())["status"] == "failed"
