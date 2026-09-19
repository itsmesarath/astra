"""Download and normalize checksum-verified Binance Spot history archives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import urllib.request
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import BinaryIO, Literal, Protocol, cast

ARCHIVE_ROOT = "https://data.binance.vision/data/spot/daily"
DEFAULT_OUTPUT_DIRECTORY = Path("data/raw/binance_spot_history")
CHECKSUM_PATTERN = re.compile(r"^(?P<digest>[0-9a-fA-F]{64})\s+\*?(?P<filename>\S+)$")
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{2,20}$")
KLINE_INTERVALS = frozenset(
    {
        "1s",
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "4h",
        "6h",
        "8h",
        "12h",
        "1d",
        "3d",
        "1w",
        "1mo",
    }
)
DataType = Literal["aggTrades", "klines"]


class ReadableResponse(Protocol):
    """Minimum response interface required from ``urlopen``."""

    def read(self, size: int = -1) -> bytes: ...

    def __enter__(self) -> ReadableResponse: ...

    def __exit__(self, *args: object) -> None: ...


UrlOpener = Callable[..., ReadableResponse]


@dataclass(frozen=True, slots=True)
class ArchiveSpec:
    """One immutable Binance daily archive and its local destinations."""

    symbol: str
    data_type: DataType
    day: date
    interval: str | None
    url: str
    checksum_url: str
    archive_path: Path
    checksum_path: Path
    normalized_path: Path


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Verified and normalized result for one source archive."""

    date: str
    archive_path: str
    checksum_path: str
    normalized_path: str
    sha256: str
    normalized_sha256: str
    archive_bytes: int
    rows: int
    source_timestamp_unit: str
    downloaded: bool


def validate_request(
    *,
    symbol: str,
    data_type: str,
    interval: str | None,
    start_date: date,
    end_date: date,
) -> tuple[str, DataType, str | None]:
    """Validate and canonicalize a bounded historical-data request."""
    normalized_symbol = symbol.upper()
    if not SYMBOL_PATTERN.fullmatch(normalized_symbol):
        raise ValueError("Symbol must contain only 2-20 ASCII letters or digits.")
    if data_type not in {"aggTrades", "klines"}:
        raise ValueError("Data type must be 'aggTrades' or 'klines'.")
    normalized_type = cast(DataType, data_type)
    if start_date > end_date:
        raise ValueError("Start date cannot be after end date.")
    if end_date >= datetime.now(UTC).date():
        raise ValueError("End date must be a completed UTC day before today.")
    if normalized_type == "klines":
        if interval not in KLINE_INTERVALS:
            raise ValueError("A supported --interval is required for kline data.")
    elif interval is not None:
        raise ValueError("--interval is valid only for kline data.")
    return normalized_symbol, normalized_type, interval


def iter_days(start_date: date, end_date: date) -> Iterator[date]:
    """Yield each calendar day in an inclusive date range."""
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def build_archive_spec(
    *,
    symbol: str,
    data_type: DataType,
    day: date,
    interval: str | None,
    output_directory: Path,
) -> ArchiveSpec:
    """Build official remote URLs and deterministic local paths."""
    date_text = day.isoformat()
    if data_type == "klines":
        if interval is None:
            raise ValueError("Kline archives require an interval.")
        relative_directory = f"klines/{symbol}/{interval}"
        stem = f"{symbol}-{interval}-{date_text}"
        local_directory = output_directory / "klines" / symbol / interval
    else:
        relative_directory = f"aggTrades/{symbol}"
        stem = f"{symbol}-aggTrades-{date_text}"
        local_directory = output_directory / "aggTrades" / symbol

    url = f"{ARCHIVE_ROOT}/{relative_directory}/{stem}.zip"
    archive_path = local_directory / f"{stem}.zip"
    return ArchiveSpec(
        symbol=symbol,
        data_type=data_type,
        day=day,
        interval=interval,
        url=url,
        checksum_url=f"{url}.CHECKSUM",
        archive_path=archive_path,
        checksum_path=archive_path.with_suffix(".zip.CHECKSUM"),
        normalized_path=local_directory / "normalized" / f"{stem}.csv",
    )


def parse_checksum(content: str, *, expected_filename: str) -> str:
    """Parse Binance's SHA-256 checksum response and bind it to the archive name."""
    match = CHECKSUM_PATTERN.fullmatch(content.strip())
    if match is None:
        raise ValueError("Malformed Binance checksum response.")
    if Path(match.group("filename")).name != expected_filename:
        raise ValueError("Checksum response names an unexpected archive.")
    return match.group("digest").lower()


def sha256_file(path: Path) -> str:
    """Calculate a file SHA-256 without loading the archive into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_url(opener: UrlOpener, url: str) -> ReadableResponse:
    request = urllib.request.Request(url, headers={"User-Agent": "ai-trader-history/1"})
    return opener(request, timeout=30)


def fetch_text(url: str, *, opener: UrlOpener = urllib.request.urlopen) -> str:
    """Fetch a small UTF-8 metadata file."""
    with _open_url(opener, url) as response:
        return response.read().decode("utf-8")


def download_file(
    url: str,
    destination: Path,
    *,
    opener: UrlOpener = urllib.request.urlopen,
) -> None:
    """Stream a URL to an atomic local file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_name(f"{destination.name}.part")
    try:
        with _open_url(opener, url) as response, temporary_path.open("wb") as output_file:
            shutil.copyfileobj(response, output_file, length=1024 * 1024)
        os.replace(temporary_path, destination)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def normalize_timestamp_ms(raw_value: str) -> str:
    """Normalize Binance millisecond or microsecond epoch fields to milliseconds."""
    value = int(raw_value)
    if value < 0:
        raise ValueError("Timestamp cannot be negative.")
    if value >= 100_000_000_000_000:
        value //= 1_000
    return str(value)


def _normalized_header(data_type: DataType) -> tuple[str, ...]:
    if data_type == "aggTrades":
        return (
            "aggregate_trade_id",
            "price",
            "quantity",
            "first_trade_id",
            "last_trade_id",
            "trade_time_ms",
            "buyer_is_maker",
            "best_price_match",
        )
    return (
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


def _normalize_row(row: list[str], data_type: DataType) -> list[str]:
    expected_columns = 8 if data_type == "aggTrades" else 12
    if len(row) != expected_columns:
        raise ValueError(f"Expected {expected_columns} columns, found {len(row)}.")
    result = list(row)
    timestamp_indexes = (5,) if data_type == "aggTrades" else (0, 6)
    for index in timestamp_indexes:
        result[index] = normalize_timestamp_ms(result[index])
    return result


def normalize_archive(spec: ArchiveSpec) -> int:
    """Extract one expected CSV and atomically write a stable-header millisecond CSV."""
    spec.normalized_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = spec.normalized_path.with_name(f"{spec.normalized_path.name}.part")
    rows_written = 0
    try:
        with zipfile.ZipFile(spec.archive_path) as archive:
            members = [member for member in archive.infolist() if not member.is_dir()]
            expected_member_name = spec.archive_path.stem + ".csv"
            if len(members) != 1 or Path(members[0].filename).name != expected_member_name:
                raise ValueError("Archive must contain exactly its expected CSV file.")
            member = members[0]
            if Path(member.filename).name != member.filename:
                raise ValueError("Nested archive paths are not accepted.")

            with (
                archive.open(member) as binary_input,
                temporary_path.open("w", encoding="utf-8", newline="") as output_file,
            ):
                text_input = _DecodedCsvStream(binary_input)
                reader = csv.reader(text_input)
                writer = csv.writer(output_file, lineterminator="\n")
                writer.writerow(_normalized_header(spec.data_type))
                for line_number, row in enumerate(reader, start=1):
                    try:
                        writer.writerow(_normalize_row(row, spec.data_type))
                    except (TypeError, ValueError) as error:
                        raise ValueError(f"Invalid archive row {line_number}: {error}") from error
                    rows_written += 1

        if rows_written == 0:
            raise ValueError("Archive contains no data rows.")
        os.replace(temporary_path, spec.normalized_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return rows_written


class _DecodedCsvStream:
    """Minimal iterable text adapter for a binary ZIP member."""

    def __init__(self, source: BinaryIO) -> None:
        self._source = source

    def __iter__(self) -> Iterator[str]:
        for line in self._source:
            yield line.decode("utf-8")


def acquire_archive(
    spec: ArchiveSpec,
    *,
    opener: UrlOpener = urllib.request.urlopen,
) -> DownloadResult:
    """Download, authenticate, and normalize one archive, reusing valid local bytes."""
    checksum_text = fetch_text(spec.checksum_url, opener=opener)
    expected_digest = parse_checksum(
        checksum_text,
        expected_filename=spec.archive_path.name,
    )
    already_valid = (
        spec.archive_path.is_file() and sha256_file(spec.archive_path) == expected_digest
    )
    if not already_valid:
        download_file(spec.url, spec.archive_path, opener=opener)

    actual_digest = sha256_file(spec.archive_path)
    if actual_digest != expected_digest:
        spec.archive_path.unlink(missing_ok=True)
        raise ValueError(f"SHA-256 mismatch for {spec.archive_path.name}.")

    spec.checksum_path.write_text(checksum_text.strip() + "\n", encoding="utf-8")
    rows = normalize_archive(spec)
    normalized_digest = sha256_file(spec.normalized_path)
    source_timestamp_unit = "microseconds" if spec.day >= date(2025, 1, 1) else "milliseconds"
    return DownloadResult(
        date=spec.day.isoformat(),
        archive_path=str(spec.archive_path),
        checksum_path=str(spec.checksum_path),
        normalized_path=str(spec.normalized_path),
        sha256=actual_digest,
        normalized_sha256=normalized_digest,
        archive_bytes=spec.archive_path.stat().st_size,
        rows=rows,
        source_timestamp_unit=source_timestamp_unit,
        downloaded=not already_valid,
    )


def download_history(
    *,
    symbol: str,
    data_type: str,
    interval: str | None,
    start_date: date,
    end_date: date,
    output_directory: Path = DEFAULT_OUTPUT_DIRECTORY,
    opener: UrlOpener = urllib.request.urlopen,
) -> Path:
    """Acquire an inclusive range and write an auditable request manifest."""
    normalized_symbol, normalized_type, interval = validate_request(
        symbol=symbol,
        data_type=data_type,
        interval=interval,
        start_date=start_date,
        end_date=end_date,
    )
    results = []
    for day in iter_days(start_date, end_date):
        spec = build_archive_spec(
            symbol=normalized_symbol,
            data_type=normalized_type,
            day=day,
            interval=interval,
            output_directory=output_directory,
        )
        results.append(acquire_archive(spec, opener=opener))

    interval_tag = f"_{interval}" if interval else ""
    manifest_path = output_directory / (
        f"manifest_{normalized_symbol}_{normalized_type}{interval_tag}_"
        f"{start_date.isoformat()}_{end_date.isoformat()}.json"
    )
    manifest = {
        "schema_version": 1,
        "source": "binance_public_data",
        "market": "spot",
        "symbol": normalized_symbol,
        "data_type": normalized_type,
        "interval": interval,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "timestamp_unit": "milliseconds",
        "archives": [asdict(result) for result in results],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = manifest_path.with_name(f"{manifest_path.name}.part")
    temporary_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_path, manifest_path)
    return manifest_path


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected an ISO date in YYYY-MM-DD format.") from error


def parse_args() -> argparse.Namespace:
    """Parse historical-download CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--data-type", choices=("aggTrades", "klines"), required=True)
    parser.add_argument("--interval", choices=sorted(KLINE_INTERVALS))
    parser.add_argument("--start-date", type=_parse_iso_date, required=True)
    parser.add_argument("--end-date", type=_parse_iso_date, required=True)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    return parser.parse_args()


def main() -> None:
    """Run the public historical-data download."""
    args = parse_args()
    try:
        manifest_path = download_history(
            symbol=args.symbol,
            data_type=args.data_type,
            interval=args.interval,
            start_date=args.start_date,
            end_date=args.end_date,
            output_directory=args.output_directory,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(f"Verified download manifest: {manifest_path.resolve()}")


if __name__ == "__main__":
    main()
