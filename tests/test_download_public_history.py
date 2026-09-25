"""Tests for bounded provider-separated public history downloads."""

from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
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


def test_interval_names_follow_each_venue_utc_convention() -> None:
    start = 1_700_000_000_000
    binance = PublicHistoryRequest(
        "binance", "BTCUSDT", "candles", start, start + 86_400_000, 86_400
    )
    okx = PublicHistoryRequest("okx", "BTC-USDT", "candles", start, start + 86_400_000, 86_400)
    assert "interval=1d" in build_page_url(binance)
    assert "bar=1Dutc" in build_page_url(okx)
    with pytest.raises(ValueError, match="30-minute"):
        PublicHistoryRequest("coinbase", "BTC-USD", "candles", start, start + 60_000, 1_800)


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


def test_binance_trade_pages_use_id_to_keep_shared_millisecond(tmp_path: Path) -> None:
    start = 1_700_000_000_000
    first = [
        {"a": number, "p": "100", "q": "0.1", "T": start, "m": False} for number in range(1000)
    ]
    second = [
        {"a": number, "p": "100", "q": "0.1", "T": start, "m": False}
        for number in range(1000, 1002)
    ]

    class PagingOpener:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def __call__(self, request: Request, *, timeout: int) -> FakeResponse:
            self.urls.append(request.full_url)
            params = parse_qs(urlparse(request.full_url).query)
            payload = second if params.get("fromId") == ["1000"] else first
            return FakeResponse(json.dumps(payload).encode())

    opener = PagingOpener()
    request = PublicHistoryRequest("binance", "BTCUSDT", "trades", start, start + 2, max_pages=2)
    result = download_public_history(request, tmp_path / "trades.jsonl", opener=opener)
    assert result.rows == 1002 and result.pages == 2
    assert "fromId=1000" in opener.urls[1]
    assert "startTime=" not in opener.urls[1]


def test_page_budget_refuses_incomplete_history_without_publishing(tmp_path: Path) -> None:
    start = 1_700_000_000_000
    payload = [
        {"a": number, "p": "100", "q": "0.1", "T": start, "m": False} for number in range(1000)
    ]
    output = tmp_path / "partial.jsonl"
    request = PublicHistoryRequest("binance", "BTCUSDT", "trades", start, start + 2, max_pages=1)
    with pytest.raises(ValueError, match="Page budget reached"):
        download_public_history(request, output, opener=FakeOpener(payload))
    assert not output.exists() and not output.with_suffix(".manifest.json").exists()


def test_coinbase_splits_long_range_into_bounded_windows(tmp_path: Path) -> None:
    start = 1_700_000_000_000
    period = 60_000

    class PagingOpener:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def __call__(self, request: Request, *, timeout: int) -> FakeResponse:
            self.urls.append(request.full_url)
            row_time = start if len(self.urls) == 1 else start + 300 * period
            return FakeResponse(json.dumps([[row_time // 1000, 90, 110, 100, 105, 2]]).encode())

    opener = PagingOpener()
    request = PublicHistoryRequest(
        "coinbase", "BTC-USD", "candles", start, start + 400 * period, max_pages=2
    )
    result = download_public_history(request, tmp_path / "coinbase.jsonl", opener=opener)
    assert result.rows == 2 and result.pages == 2
    assert len(opener.urls) == 2
    assert "granularity=60" in opener.urls[0]
