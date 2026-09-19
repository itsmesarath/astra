"""Tests for checksum-verified Binance Spot history downloads."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.request import Request

import pytest

from ai_trader.ingestion.download_binance_history import (
    acquire_archive,
    build_archive_spec,
    download_history,
    normalize_archive,
    normalize_timestamp_ms,
    parse_checksum,
    validate_request,
)


class FakeResponse(io.BytesIO):
    """Context-managed byte response used by the fake URL opener."""

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class FakeOpener:
    """Serve deterministic URL payloads and record each request."""

    def __init__(self, payloads: dict[str, bytes]) -> None:
        self.payloads = payloads
        self.requested_urls: list[str] = []

    def __call__(self, request: Request, *, timeout: int) -> FakeResponse:
        assert timeout == 30
        self.requested_urls.append(request.full_url)
        return FakeResponse(self.payloads[request.full_url])


def make_zip(filename: str, rows: list[list[str]]) -> bytes:
    """Build an in-memory single-member CSV ZIP."""
    csv_buffer = io.StringIO(newline="")
    writer = csv.writer(csv_buffer, lineterminator="\n")
    writer.writerows(rows)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, csv_buffer.getvalue())
    return zip_buffer.getvalue()


def make_payloads(spec_url: str, archive_bytes: bytes) -> dict[str, bytes]:
    """Return matching archive and checksum HTTP bodies."""
    filename = spec_url.rsplit("/", maxsplit=1)[-1]
    digest = hashlib.sha256(archive_bytes).hexdigest()
    return {
        spec_url: archive_bytes,
        f"{spec_url}.CHECKSUM": f"{digest}  {filename}\n".encode(),
    }


def completed_day() -> date:
    """Return a stable completed UTC day for request validation."""
    return datetime.now(UTC).date() - timedelta(days=2)


def test_builds_official_daily_archive_paths(tmp_path: Path) -> None:
    """Remote and local paths must encode market, kind, symbol, interval, and date."""
    spec = build_archive_spec(
        symbol="BTCUSDT",
        data_type="klines",
        day=date(2024, 12, 31),
        interval="5m",
        output_directory=tmp_path,
    )

    assert spec.url == (
        "https://data.binance.vision/data/spot/daily/klines/BTCUSDT/5m/BTCUSDT-5m-2024-12-31.zip"
    )
    assert spec.checksum_url == f"{spec.url}.CHECKSUM"
    assert spec.normalized_path == (
        tmp_path / "klines/BTCUSDT/5m/normalized/BTCUSDT-5m-2024-12-31.csv"
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"symbol": "../BTC", "data_type": "aggTrades", "interval": None},
            "Symbol",
        ),
        (
            {"symbol": "BTCUSDT", "data_type": "trades", "interval": None},
            "Data type",
        ),
        (
            {"symbol": "BTCUSDT", "data_type": "klines", "interval": None},
            "interval",
        ),
        (
            {"symbol": "BTCUSDT", "data_type": "aggTrades", "interval": "1m"},
            "interval",
        ),
    ],
)
def test_rejects_unsafe_or_inconsistent_requests(
    kwargs: dict[str, str | None],
    message: str,
) -> None:
    """Invalid paths and incompatible data options must fail before network access."""
    day = completed_day()
    with pytest.raises(ValueError, match=message):
        validate_request(start_date=day, end_date=day, **kwargs)


def test_rejects_current_or_future_utc_days() -> None:
    """Incomplete daily archives must not enter a reproducible download request."""
    today = datetime.now(UTC).date()
    with pytest.raises(ValueError, match="completed UTC day"):
        validate_request(
            symbol="BTCUSDT",
            data_type="aggTrades",
            interval=None,
            start_date=today,
            end_date=today,
        )


def test_checksum_is_bound_to_expected_filename() -> None:
    """A valid digest for a different filename must not authenticate an archive."""
    digest = "a" * 64
    assert parse_checksum(f"{digest}  expected.zip", expected_filename="expected.zip") == digest
    with pytest.raises(ValueError, match="unexpected archive"):
        parse_checksum(f"{digest}  other.zip", expected_filename="expected.zip")


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("1735689599999", "1735689599999"),
        ("1735689599999999", "1735689599999"),
    ],
)
def test_normalizes_millisecond_and_microsecond_timestamps(
    raw_value: str,
    expected: str,
) -> None:
    """The 2025 archive precision change must produce a stable millisecond schema."""
    assert normalize_timestamp_ms(raw_value) == expected


def test_downloads_verifies_normalizes_and_manifests_aggregate_trades(
    tmp_path: Path,
) -> None:
    """An end-to-end request must retain provenance and normalize microseconds."""
    day = date(2025, 1, 2)
    spec = build_archive_spec(
        symbol="BTCUSDT",
        data_type="aggTrades",
        day=day,
        interval=None,
        output_directory=tmp_path,
    )
    archive_bytes = make_zip(
        "BTCUSDT-aggTrades-2025-01-02.csv",
        [
            ["10", "100.5", "0.1", "20", "21", "1735776000123456", "True", "True"],
            ["11", "100.6", "0.2", "22", "22", "1735776001123456", "False", "True"],
        ],
    )
    opener = FakeOpener(make_payloads(spec.url, archive_bytes))

    manifest_path = download_history(
        symbol="btcusdt",
        data_type="aggTrades",
        interval=None,
        start_date=day,
        end_date=day,
        output_directory=tmp_path,
        opener=opener,
    )

    with manifest_path.open(encoding="utf-8") as input_file:
        manifest = json.load(input_file)
    with spec.normalized_path.open(encoding="utf-8", newline="") as input_file:
        normalized_rows = list(csv.DictReader(input_file))

    assert opener.requested_urls == [spec.checksum_url, spec.url]
    assert manifest["source"] == "binance_public_data"
    assert manifest["market"] == "spot"
    assert manifest["timestamp_unit"] == "milliseconds"
    assert manifest["archives"][0]["rows"] == 2
    assert manifest["archives"][0]["source_timestamp_unit"] == "microseconds"
    assert manifest["archives"][0]["downloaded"] is True
    assert (
        manifest["archives"][0]["normalized_sha256"]
        == hashlib.sha256(spec.normalized_path.read_bytes()).hexdigest()
    )
    assert normalized_rows[0]["trade_time_ms"] == "1735776000123"
    assert spec.archive_path.read_bytes() == archive_bytes
    assert spec.checksum_path.is_file()


def test_reuses_only_an_existing_archive_with_the_expected_hash(tmp_path: Path) -> None:
    """Idempotent reruns may skip archive bytes but must revalidate published checksum data."""
    day = date(2024, 12, 31)
    spec = build_archive_spec(
        symbol="BTCUSDT",
        data_type="klines",
        day=day,
        interval="1m",
        output_directory=tmp_path,
    )
    row = [
        "1735603200000",
        "100",
        "101",
        "99",
        "100.5",
        "3",
        "1735603259999",
        "301",
        "7",
        "1.5",
        "150",
        "0",
    ]
    archive_bytes = make_zip("BTCUSDT-1m-2024-12-31.csv", [row])
    spec.archive_path.parent.mkdir(parents=True)
    spec.archive_path.write_bytes(archive_bytes)
    payloads = make_payloads(spec.url, archive_bytes)
    opener = FakeOpener({spec.checksum_url: payloads[spec.checksum_url]})

    result = acquire_archive(spec, opener=opener)

    assert opener.requested_urls == [spec.checksum_url]
    assert result.downloaded is False
    assert result.source_timestamp_unit == "milliseconds"
    with spec.normalized_path.open(encoding="utf-8", newline="") as input_file:
        normalized_rows = list(csv.DictReader(input_file))
    assert normalized_rows[0]["open_time_ms"] == "1735603200000"
    assert normalized_rows[0]["close_time_ms"] == "1735603259999"


def test_deletes_archive_when_downloaded_bytes_fail_checksum(tmp_path: Path) -> None:
    """Corrupt downloads must not remain available for later processing."""
    spec = build_archive_spec(
        symbol="BTCUSDT",
        data_type="aggTrades",
        day=date(2025, 1, 2),
        interval=None,
        output_directory=tmp_path,
    )
    archive_bytes = make_zip(
        "BTCUSDT-aggTrades-2025-01-02.csv",
        [["1", "100", "1", "1", "1", "1735776000000000", "True", "True"]],
    )
    wrong_digest = "0" * 64
    opener = FakeOpener(
        {
            spec.checksum_url: f"{wrong_digest}  {spec.archive_path.name}\n".encode(),
            spec.url: archive_bytes,
        }
    )

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        acquire_archive(spec, opener=opener)

    assert not spec.archive_path.exists()
    assert not spec.normalized_path.exists()


def test_rejects_nested_zip_member(tmp_path: Path) -> None:
    """ZIP members cannot escape or introduce an unexpected directory structure."""
    spec = build_archive_spec(
        symbol="BTCUSDT",
        data_type="aggTrades",
        day=date(2025, 1, 2),
        interval=None,
        output_directory=tmp_path,
    )
    spec.archive_path.parent.mkdir(parents=True)
    with zipfile.ZipFile(spec.archive_path, "w") as archive:
        archive.writestr(
            "nested/BTCUSDT-aggTrades-2025-01-02.csv",
            "1,100,1,1,1,1735776000000000,True,True\n",
        )

    with pytest.raises(ValueError, match="Nested archive paths"):
        normalize_archive(spec)

    assert not spec.normalized_path.exists()
