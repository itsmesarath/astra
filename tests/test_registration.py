"""Registration works on metadata even when reserved archives cannot be opened."""

import json
from pathlib import Path

import pytest

from ai_trader.research import registration as module

FIRST = "binance_spot_BTCUSDT_2025-01-01"
LAST = "binance_spot_BTCUSDT_2025-01-02"


def manifest(tmp_path):
    source = tmp_path / "manifest.json"
    source.write_text(
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
                        "normalized_path": "missing-research.csv",
                        "normalized_sha256": "a" * 64,
                    },
                    {"date": "2025-01-02", "normalized_path": "poisoned-reserved.csv"},
                ],
            }
        ),
        encoding="utf-8",
    )
    return source


def register(source, output, **kwargs):
    return module.register_pullback(
        source,
        output,
        trial_id="test-001",
        research_sessions=kwargs.get("research", (FIRST,)),
        reserved_sessions=kwargs.get("reserved", (LAST,)),
    )


def test_metadata_only_registration_and_verification(tmp_path, monkeypatch):
    source = manifest(tmp_path)
    output = tmp_path / "registration.json"
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert path.suffix != ".csv", "No candle archives may be opened"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    envelope = register(source, output)
    verified = module.verify_registration(output)
    assert verified == envelope["registration"]
    assert verified["excluded_sessions"] == [LAST]
    assert verified["protocol"]["round_trip_cost_scenarios_bps"] == [24, 36, 48]
    assert verified["promotion_allowed"] is False
    assert len(envelope["registration_sha256"]) == 64
    assert verified["implementation_sha256"]["research/trend_pullback.py"]


@pytest.mark.parametrize(
    "research,reserved",
    [
        ((FIRST,), (FIRST,)),
        ((LAST,), (FIRST,)),
        ((FIRST, FIRST), (LAST,)),
        ((), (LAST,)),
        ((FIRST,), ()),
        (("bad",), (LAST,)),
        ((FIRST,), ("binance_spot_BTCUSDT_2025-01-03",)),
    ],
)
def test_bad_scope_rejected_before_write(tmp_path, research, reserved):
    output = tmp_path / "registration.json"
    with pytest.raises(ValueError):
        register(manifest(tmp_path), output, research=research, reserved=reserved)
    assert not output.exists()


def test_write_once_and_manifest_change(tmp_path):
    source = manifest(tmp_path)
    output = tmp_path / "registration.json"
    register(source, output)
    with pytest.raises(FileExistsError):
        register(source, output)
    source.write_text(source.read_text() + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="manifest changed"):
        module.verify_registration(output)


def test_registration_change_detected(tmp_path):
    output = tmp_path / "registration.json"
    envelope = register(manifest(tmp_path), output)
    envelope["registration"]["protocol"]["holding_bars"] = 1
    output.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        module.verify_registration(output)


@pytest.mark.parametrize("function", ["implementation_fingerprint", "environment_fingerprint"])
def test_changed_implementation_or_environment_rejected(tmp_path, monkeypatch, function):
    output = tmp_path / "registration.json"
    register(manifest(tmp_path), output)
    monkeypatch.setattr(module, function, lambda: {"changed": "yes"})
    with pytest.raises(ValueError, match="changed"):
        module.verify_registration(output)


@pytest.mark.parametrize(
    "change",
    [
        {"interval": "1m"},
        {"symbol": "ETHUSDT"},
        {"market": "futures"},
        {"archives": []},
    ],
)
def test_wrong_manifest_rejected(tmp_path, change):
    source = manifest(tmp_path)
    payload = json.loads(source.read_text())
    payload.update(change)
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        register(source, tmp_path / "registration.json")


@pytest.mark.parametrize("corruption", ["duplicate", "bad_hash", "missing_path"])
def test_bad_archive_metadata_rejected_without_registration(tmp_path, corruption):
    source = manifest(tmp_path)
    payload = json.loads(source.read_text())
    if corruption == "duplicate":
        payload["archives"].append(payload["archives"][0])
    elif corruption == "bad_hash":
        payload["archives"][0]["normalized_sha256"] = "not-a-digest"
    else:
        del payload["archives"][0]["normalized_path"]
    source.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "registration.json"
    with pytest.raises(ValueError):
        register(source, output)
    assert not output.exists()
