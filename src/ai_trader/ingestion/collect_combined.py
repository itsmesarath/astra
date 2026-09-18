"""Collect a synchronized BTCUSDT snapshot, trades, and depth updates."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import urllib.request
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from websockets.asyncio.client import connect

from ai_trader.ingestion.agg_trade import AggTrade
from ai_trader.orderbook.depth_update import DepthUpdate
from ai_trader.orderbook.snapshot import PartialDepthSnapshot

SYMBOL = "BTCUSDT"
TRADE_STREAM = "btcusdt@aggTrade"
DEPTH_STREAM = "btcusdt@depth@100ms"
STREAM_URL = f"wss://data-stream.binance.vision/stream?streams={TRADE_STREAM}/{DEPTH_STREAM}"
SNAPSHOT_URL = "https://data-api.binance.vision/api/v3/depth?symbol=BTCUSDT&limit=1000"
SNAPSHOT_LIMIT = 1000
OUTPUT_DIRECTORY = Path("data/raw")


def parse_args() -> argparse.Namespace:
    """Read and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Collect public BTCUSDT trades and depth data.",
    )
    parser.add_argument(
        "--seconds",
        type=int,
        default=30,
        help="Total collection duration in seconds (default: 30).",
    )
    args = parser.parse_args()

    if args.seconds <= 0:
        parser.error("--seconds must be greater than zero")

    return args


def create_output_path() -> Path:
    """Create a unique UTC-stamped session path."""
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    return OUTPUT_DIRECTORY / f"btcusdt_combined_{timestamp}.jsonl"


def fetch_snapshot() -> dict[str, object]:
    """Fetch and validate one public depth snapshot."""
    with urllib.request.urlopen(SNAPSHOT_URL, timeout=10) as response:
        payload = json.load(response)

    if not isinstance(payload, dict):
        raise TypeError("Snapshot response must be a JSON object.")

    PartialDepthSnapshot.from_event(payload)
    return payload


def write_record(
    output_file,
    record: dict[str, object],
) -> None:
    """Write one compact JSON record."""
    output_file.write(json.dumps(record, separators=(",", ":")) + "\n")


async def receive_messages(
    websocket,
    queue: asyncio.Queue[tuple[int, str | bytes]],
) -> None:
    """Timestamp incoming WebSocket messages and place them in order."""
    async for message in websocket:
        received_at_ns = time.time_ns()
        await queue.put((received_at_ns, message))


def parse_stream_record(
    received_at_ns: int,
    message: str | bytes,
) -> tuple[dict[str, object], str]:
    """Validate a combined message and create its storage envelope."""
    wrapper = json.loads(message)

    if not isinstance(wrapper, dict):
        raise TypeError("Combined message must be a JSON object.")

    stream_name = wrapper.get("stream")
    event = wrapper.get("data")

    if not isinstance(stream_name, str):
        raise TypeError("Combined message must contain a stream name.")
    if not isinstance(event, dict):
        raise TypeError("Combined message must contain event data.")

    if stream_name == TRADE_STREAM:
        AggTrade.from_event(event)
    elif stream_name == DEPTH_STREAM:
        DepthUpdate.from_event(event)
    else:
        raise ValueError(f"Unexpected stream: {stream_name}")

    record: dict[str, object] = {
        "schema_version": 1,
        "record_type": "stream_event",
        "stream": stream_name,
        "received_at_ns": received_at_ns,
        "event": event,
    }
    return record, stream_name


async def collect(seconds: int) -> tuple[Path, int, int]:
    """Collect one bounded, synchronized raw-data session."""
    output_path = create_output_path()
    message_queue: asyncio.Queue[tuple[int, str | bytes]] = asyncio.Queue(maxsize=10_000)

    trade_count = 0
    depth_count = 0

    async with connect(
        STREAM_URL,
        open_timeout=10,
        max_queue=1024,
    ) as websocket:
        loop = asyncio.get_running_loop()
        started_at_ns = time.time_ns()
        ending_at_ns = started_at_ns + seconds * 1_000_000_000
        deadline = loop.time() + seconds

        receiver_task = asyncio.create_task(receive_messages(websocket, message_queue))

        snapshot_requested_at_ns = time.time_ns()
        snapshot = await asyncio.to_thread(fetch_snapshot)
        snapshot_received_at_ns = time.time_ns()

        with output_path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as output_file:
            write_record(
                output_file,
                {
                    "schema_version": 1,
                    "record_type": "session_start",
                    "started_at_ns": started_at_ns,
                    "symbol": SYMBOL,
                    "streams": [TRADE_STREAM, DEPTH_STREAM],
                    "snapshot_limit": SNAPSHOT_LIMIT,
                },
            )

            write_record(
                output_file,
                {
                    "schema_version": 1,
                    "record_type": "depth_snapshot",
                    "requested_at_ns": snapshot_requested_at_ns,
                    "received_at_ns": snapshot_received_at_ns,
                    "event": snapshot,
                },
            )

            try:
                while True:
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        break

                    try:
                        received_at_ns, message = await asyncio.wait_for(
                            message_queue.get(),
                            timeout=remaining,
                        )
                    except TimeoutError:
                        break

                    if received_at_ns > ending_at_ns:
                        break

                    record, stream_name = parse_stream_record(
                        received_at_ns,
                        message,
                    )
                    write_record(output_file, record)

                    if stream_name == TRADE_STREAM:
                        trade_count += 1
                    else:
                        depth_count += 1
            finally:
                receiver_task.cancel()
                with suppress(asyncio.CancelledError):
                    await receiver_task

            while not message_queue.empty():
                received_at_ns, message = message_queue.get_nowait()

                if received_at_ns > ending_at_ns:
                    break

                record, stream_name = parse_stream_record(
                    received_at_ns,
                    message,
                )
                write_record(output_file, record)

                if stream_name == TRADE_STREAM:
                    trade_count += 1
                else:
                    depth_count += 1

            write_record(
                output_file,
                {
                    "schema_version": 1,
                    "record_type": "session_end",
                    "ended_at_ns": time.time_ns(),
                    "trade_events": trade_count,
                    "depth_events": depth_count,
                },
            )

    return output_path, trade_count, depth_count


def main() -> None:
    """Run the bounded combined collector."""
    args = parse_args()

    print(f"Collecting BTCUSDT trades and depth updates for {args.seconds} seconds...")

    output_path, trade_count, depth_count = asyncio.run(collect(args.seconds))

    print(f"Trade events: {trade_count}")
    print(f"Depth events: {depth_count}")
    print(f"Output: {output_path.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
