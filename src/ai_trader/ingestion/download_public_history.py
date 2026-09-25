"""Download bounded public candle/trade history from supported spot venues.

The downloader uses unauthenticated HTTPS endpoints only.  Each venue is kept in
its own normalized JSONL file and manifest; rows from different venues are never
silently merged.  Binance's checksum-verified daily archives remain available
through :mod:`download_binance_history` and are preferred for long archive jobs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, Protocol

Provider = Literal["binance", "okx", "coinbase"]
DataType = Literal["candles", "trades"]
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_PAGES = 1_000
MAX_ROWS = 1_000_000
BINANCE_PAGE_SIZE = 1_000
OKX_PAGE_SIZE = 300
COINBASE_WINDOW_CANDLES = 299


class ReadableResponse(Protocol):
    def read(self, size: int = -1) -> bytes: ...

    def __enter__(self) -> ReadableResponse: ...

    def __exit__(self, *args: object) -> None: ...


Opener = Callable[..., ReadableResponse]


@dataclass(frozen=True, slots=True)
class PublicHistoryRequest:
    provider: Provider
    product: str
    data_type: DataType
    start_ms: int
    end_ms: int
    interval_seconds: int = 60
    max_pages: int = 100

    def __post_init__(self) -> None:
        if self.provider not in ("binance", "okx", "coinbase"):
            raise ValueError("provider must be binance, okx, or coinbase.")
        if self.data_type not in ("candles", "trades"):
            raise ValueError("data_type must be candles or trades.")
        if type(self.product) is not str or not 2 <= len(self.product) <= 30:
            raise ValueError("product must contain 2-30 characters.")
        if any(
            character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for character in self.product
        ):
            raise ValueError("product may contain only letters, digits, '-' and '_'.")
        if type(self.start_ms) is not int or type(self.end_ms) is not int:
            raise ValueError("start_ms and end_ms must be integers.")
        if not 0 <= self.start_ms < self.end_ms:
            raise ValueError("Require 0 <= start_ms < end_ms.")
        if self.interval_seconds not in (60, 300, 900, 1_800, 3_600, 21_600, 86_400):
            raise ValueError("Unsupported candle interval in seconds.")
        if self.provider == "coinbase" and self.interval_seconds == 1_800:
            raise ValueError("Coinbase Exchange does not support 30-minute candles.")
        if type(self.max_pages) is not int or not 1 <= self.max_pages <= MAX_PAGES:
            raise ValueError(f"max_pages must be an integer in [1, {MAX_PAGES}].")
        if self.provider in ("okx", "coinbase") and self.data_type == "trades":
            raise ValueError(
                "Only Binance public trades are supported; add a venue-specific adapter "
                "before introducing another trade schema."
            )


@dataclass(frozen=True, slots=True)
class PublicHistoryResult:
    provider: str
    product: str
    data_type: str
    rows: int
    pages: int
    output_path: Path
    manifest_path: Path
    sha256: str


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _interval_name(seconds: int, provider: Provider) -> str:
    if provider == "binance":
        names = {
            60: "1m",
            300: "5m",
            900: "15m",
            1_800: "30m",
            3_600: "1h",
            21_600: "6h",
            86_400: "1d",
        }
    else:
        names = {
            60: "1m",
            300: "5m",
            900: "15m",
            1_800: "30m",
            3_600: "1H",
            21_600: "6Hutc",
            86_400: "1Dutc",
        }
    return names[seconds]


def _iso8601(milliseconds: int) -> str:
    return (
        datetime.fromtimestamp(milliseconds / 1_000, UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def build_page_url(request: PublicHistoryRequest, *, cursor_ms: int | None = None) -> str:
    """Build the next public request without credentials or authorization headers."""
    interval = _interval_name(request.interval_seconds, request.provider)
    if request.provider == "binance":
        endpoint = (
            "https://data-api.binance.vision/api/v3/klines"
            if request.data_type == "candles"
            else "https://data-api.binance.vision/api/v3/aggTrades"
        )
        params: dict[str, str | int] = {
            "symbol": request.product.upper(),
            "limit": BINANCE_PAGE_SIZE,
        }
        if request.data_type == "candles":
            params["startTime"] = request.start_ms if cursor_ms is None else cursor_ms
            params["endTime"] = request.end_ms - 1
            params["interval"] = interval
        elif cursor_ms is None:
            params["startTime"] = request.start_ms
            params["endTime"] = request.end_ms - 1
        else:
            # Trade IDs, rather than milliseconds, preserve all trades sharing a timestamp.
            params["fromId"] = cursor_ms
    elif request.provider == "okx":
        endpoint = "https://www.okx.com/api/v5/market/history-candles"
        params = {
            "instId": request.product.upper(),
            "bar": interval,
            "after": request.end_ms if cursor_ms is None else cursor_ms,
            "before": max(0, request.start_ms - 1),
            "limit": OKX_PAGE_SIZE,
        }
    else:
        endpoint = f"https://api.exchange.coinbase.com/products/{request.product.upper()}/candles"
        start = request.start_ms if cursor_ms is None else cursor_ms
        params = {
            "granularity": request.interval_seconds,
            "start": _iso8601(start),
            "end": _iso8601(
                min(
                    start + COINBASE_WINDOW_CANDLES * request.interval_seconds * 1_000,
                    request.end_ms,
                )
            ),
        }
    return endpoint + "?" + urllib.parse.urlencode(params)


def _fetch_json(url: str, *, opener: Opener) -> Any:
    request = urllib.request.Request(
        url, headers={"User-Agent": "ai-trader-public-history/1", "Accept": "application/json"}
    )
    with opener(request, timeout=30) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError("Public response exceeds the bounded response budget.")
    try:
        return json.loads(payload.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Public response was not valid UTF-8 JSON.") from error


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON constant: {value}")


def _number(value: object) -> str:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Expected a finite numeric public-data field.")
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        try:
            parsed = Decimal(str(value))
        except InvalidOperation as error:
            raise ValueError("Expected a finite numeric public-data field.") from error
        if parsed.is_finite():
            return str(value)
    raise ValueError("Expected a finite numeric public-data field.")


def _integer(value: object) -> int:
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    raise ValueError("Expected a nonnegative integer public-data field.")


def _candle_rows(request: PublicHistoryRequest, payload: Any) -> list[dict[str, Any]]:
    if request.provider == "okx":
        if (
            not isinstance(payload, dict)
            or payload.get("code") != "0"
            or not isinstance(payload.get("data"), list)
        ):
            raise ValueError("OKX returned an unsuccessful candle response.")
        raw_rows = payload["data"]
        rows = []
        for raw in raw_rows:
            if not isinstance(raw, list) or len(raw) < 6:
                raise ValueError("Malformed OKX candle row.")
            rows.append((_integer(raw[0]), raw[1], raw[2], raw[3], raw[4], raw[5]))
    elif request.provider == "coinbase":
        if not isinstance(payload, list):
            raise ValueError("Coinbase returned an unsuccessful candle response.")
        rows = []
        for raw in payload:
            if not isinstance(raw, list) or len(raw) < 6:
                raise ValueError("Malformed Coinbase candle row.")
            rows.append((_integer(raw[0]) * 1_000, raw[3], raw[2], raw[1], raw[4], raw[5]))
    else:
        if not isinstance(payload, list):
            raise ValueError("Binance returned an unsuccessful candle response.")
        rows = []
        for raw in payload:
            if not isinstance(raw, list) or len(raw) < 6:
                raise ValueError("Malformed Binance candle row.")
            rows.append((_integer(raw[0]), raw[1], raw[2], raw[3], raw[4], raw[5]))
    normalized = []
    for timestamp, opening, high, low, close, volume in rows:
        if not request.start_ms <= timestamp < request.end_ms:
            continue
        normalized.append(
            {
                "venue": request.provider,
                "product": request.product,
                "data_type": "candles",
                "timestamp_ms": timestamp,
                "open": _number(opening),
                "high": _number(high),
                "low": _number(low),
                "close": _number(close),
                "volume": _number(volume),
            }
        )
    return normalized


def _trade_rows(request: PublicHistoryRequest, payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("Binance returned an unsuccessful trade response.")
    normalized = []
    for raw in payload:
        if not isinstance(raw, dict) or not {"a", "p", "q", "T", "m"}.issubset(raw):
            raise ValueError("Malformed Binance aggregate-trade row.")
        timestamp = _integer(raw["T"])
        if type(raw["m"]) is not bool:
            raise ValueError("Malformed Binance maker-side flag.")
        normalized.append(
            {
                "venue": "binance",
                "product": request.product,
                "data_type": "trades",
                "trade_id": _integer(raw["a"]),
                "timestamp_ms": timestamp,
                "price": _number(raw["p"]),
                "quantity": _number(raw["q"]),
                "buyer_is_maker": raw["m"],
            }
        )
    return normalized


def _next_cursor(
    request: PublicHistoryRequest, rows: list[dict[str, Any]], cursor: int | None
) -> int | None:
    if request.provider == "coinbase":
        start = request.start_ms if cursor is None else cursor
        next_start = min(
            start + COINBASE_WINDOW_CANDLES * request.interval_seconds * 1_000,
            request.end_ms,
        )
        return next_start if next_start < request.end_ms else None
    if not rows:
        return None
    if request.provider == "okx":
        if len(rows) < OKX_PAGE_SIZE:
            return None
        candidate = min(row["timestamp_ms"] for row in rows) - 1
        if candidate < request.start_ms:
            return None
        if cursor is not None and candidate >= cursor:
            raise ValueError("OKX candle pagination did not move backward.")
        return candidate
    if request.data_type == "trades":
        if rows[-1]["timestamp_ms"] >= request.end_ms or len(rows) < BINANCE_PAGE_SIZE:
            return None
        candidate = rows[-1]["trade_id"] + 1
    else:
        if len(rows) < BINANCE_PAGE_SIZE:
            return None
        candidate = max(row["timestamp_ms"] for row in rows) + request.interval_seconds * 1_000
        if candidate >= request.end_ms:
            return None
    if cursor is not None and candidate <= cursor:
        raise ValueError("Binance history pagination did not advance.")
    return candidate


def download_public_history(
    request: PublicHistoryRequest,
    output_path: Path,
    *,
    opener: Opener = urllib.request.urlopen,
) -> PublicHistoryResult:
    """Fetch a finite range and atomically publish normalized rows plus a manifest."""
    if type(request) is not PublicHistoryRequest:
        raise TypeError("PublicHistoryRequest is required.")
    output_path = Path(output_path)
    if output_path.suffix != ".jsonl":
        raise ValueError("output_path must end in .jsonl.")
    if output_path.exists():
        raise FileExistsError(output_path)
    manifest_path = output_path.with_suffix(".manifest.json")
    if manifest_path.exists():
        raise FileExistsError(manifest_path)
    pages = 0
    cursor = None
    rows_by_key: dict[int, dict[str, Any]] = {}
    while pages < request.max_pages:
        payload = _fetch_json(build_page_url(request, cursor_ms=cursor), opener=opener)
        page = (
            _trade_rows(request, payload)
            if request.data_type == "trades"
            else _candle_rows(request, payload)
        )
        pages += 1
        for row in page:
            if not request.start_ms <= row["timestamp_ms"] < request.end_ms:
                continue
            key = int(row.get("trade_id", row["timestamp_ms"]))
            if key in rows_by_key and rows_by_key[key] != row:
                raise ValueError("Conflicting public history row at the same source key.")
            rows_by_key[key] = row
            if len(rows_by_key) > MAX_ROWS:
                raise ValueError("Public history exceeds the bounded row budget.")
        next_cursor = _next_cursor(request, page, cursor)
        if next_cursor is None:
            break
        if pages >= request.max_pages:
            raise ValueError("Page budget reached before the public range was exhausted.")
        cursor = next_cursor
    rows = sorted(
        rows_by_key.values(), key=lambda row: (row["timestamp_ms"], row.get("trade_id", 0))
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=".history-",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary_path = Path(output.name)
            for row in rows:
                output.write(
                    json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
                )
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary_path, output_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    digest = _sha256(output_path)
    manifest = {
        "schema_version": 1,
        "source": "public_rest",
        "credentials_used": False,
        "request": asdict(request),
        "rows": len(rows),
        "pages": pages,
        "output_path": str(output_path),
        "sha256": digest,
    }
    temporary_manifest: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=manifest_path.parent,
            prefix=".history-manifest-",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary_manifest = Path(output.name)
            output.write(json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n")
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary_manifest, manifest_path)
    finally:
        if temporary_manifest is not None:
            temporary_manifest.unlink(missing_ok=True)
    return PublicHistoryResult(
        request.provider,
        request.product,
        request.data_type,
        len(rows),
        pages,
        output_path,
        manifest_path,
        digest,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("binance", "okx", "coinbase"), required=True)
    parser.add_argument("--product", required=True)
    parser.add_argument("--data-type", choices=("candles", "trades"), default="candles")
    parser.add_argument("--start-ms", type=int, required=True)
    parser.add_argument("--end-ms", type=int, required=True)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    request = PublicHistoryRequest(
        args.provider,
        args.product,
        args.data_type,
        args.start_ms,
        args.end_ms,
        args.interval_seconds,
        args.max_pages,
    )
    result = download_public_history(request, args.output)
    print(
        json.dumps(
            {
                "output": str(result.output_path.resolve()),
                "rows": result.rows,
                "pages": result.pages,
            }
        )
    )


if __name__ == "__main__":
    main()
