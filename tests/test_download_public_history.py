"""Tests for bounded provider-separated public history downloads."""

from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.request import Request

import pytest

from ai_trader.ingestion.download_public_history import (
    PublicHistoryRequest,
    build_page_url,
    download_public_history,
)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class FakeOpener:
    def __init__(self, payload: object) -> None:
        self.payload = json.dumps(payload).encode()
        self.urls: list[str] = []
        self.requests: list[Request] = []

    def __call__(self, request: Request, *, timeout: int) -> FakeResponse:
        assert timeout == 30
        self.requests.append(request)
        self.urls.append(request.full_url)
        return FakeResponse(self.payload)


def test_provider_request_has_no_credentials_and_uses_public_url() -> None:
    request = PublicHistoryRequest(
        "okx", "BTC-USDT", "candles", 1_700_000_000_000, 1_700_000_060_000
    )
    url = build_page_url(request)
    assert url.startswith("https://www.okx.com/api/v5/market/history-candles?")
    assert "instId=BTC-USDT" in url
    assert "apiKey" not in url
    assert "Authorization" not in url


def test_coinbase_candles_are_normalized_and_manifest_is_written(tmp_path: Path) -> None:
    start = 1_700_000_000_000
    opener = FakeOpener([[1_700_000_000, 90, 110, 100, 105, 2]])
    request = PublicHistoryRequest("coinbase", "BTC-USD", "candles", start, start + 60_000)
    result = download_public_history(request, tmp_path / "coinbase.jsonl", opener=opener)

    row = json.loads(result.output_path.read_text().strip())
    assert row == {
        "close": "105",
        "data_type": "candles",
        "high": "110",
        "low": "90",
        "open": "100",
        "product": "BTC-USD",
        "timestamp_ms": start,
        "venue": "coinbase",
        "volume": "2",
    }
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["credentials_used"] is False
    assert manifest["rows"] == 1
    assert len(opener.requests) == 1
    assert "Authorization" not in opener.requests[0].headers


def test_binance_aggregate_trades_are_supported(tmp_path: Path) -> None:
    start = 1_700_000_000_000
    opener = FakeOpener([{"a": 7, "p": "100", "q": "0.2", "T": start, "m": True}])
    request = PublicHistoryRequest("binance", "BTCUSDT", "trades", start, start + 1_000)
    result = download_public_history(request, tmp_path / "trades.jsonl", opener=opener)
    row = json.loads(result.output_path.read_text().strip())
    assert row["trade_id"] == 7
    assert row["buyer_is_maker"] is True


def test_okx_and_coinbase_trades_are_rejected_until_a_schema_is_added() -> None:
    with pytest.raises(ValueError, match="Only Binance public trades"):
        PublicHistoryRequest("okx", "BTC-USDT", "trades", 1, 2)


def test_output_is_not_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "history.jsonl"
    output.write_text("existing\n", encoding="utf-8")
    request = PublicHistoryRequest(
        "binance", "BTCUSDT", "candles", 1_700_000_000_000, 1_700_000_060_000
    )
    with pytest.raises(FileExistsError):
        download_public_history(request, output, opener=FakeOpener([]))
