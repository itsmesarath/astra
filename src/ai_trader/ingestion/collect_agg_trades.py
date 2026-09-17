"""Collect public BTCUSDT aggregate trades into a raw JSONL file."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from websockets.asyncio.client import connect

STREAM_NAME = "btcusdt@aggTrade"
STREAM_URL = f"wss://data-stream.binance.vision/ws/{STREAM_NAME}"
OUTPUT_DIRECTORY = Path("data/raw")


def parse_args() -> argparse.Namespace:
    """Read and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Collect public BTCUSDT aggregate trades.",
    )
    parser.add_argument(
        "--seconds",
        type=int,
        default=30,
        help="Number of seconds to collect before stopping (default: 30).",
    )
    args = parser.parse_args()

    if args.seconds <= 0:
        parser.error("--seconds must be greater than zero")

    return args


def create_output_path() -> Path:
    """Create a unique UTC-stamped output path."""
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    return OUTPUT_DIRECTORY / f"btcusdt_aggtrade_{timestamp}.jsonl"


async def collect(seconds: int) -> tuple[Path, int]:
    """Collect raw events for a fixed duration."""
    output_path = create_output_path()
    event_count = 0
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds

    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        async with connect(STREAM_URL, open_timeout=10) as websocket:
            print(f"Connected. Collecting for {seconds} seconds...")

            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break

                try:
                    message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=remaining,
                    )
                except TimeoutError:
                    break

                received_at_ns = time.time_ns()
                event = json.loads(message)

                record = {
                    "schema_version": 1,
                    "source": "binance_spot",
                    "stream": STREAM_NAME,
                    "received_at_ns": received_at_ns,
                    "event": event,
                }

                output_file.write(json.dumps(record, separators=(",", ":")) + "\n")
                event_count += 1

    return output_path, event_count


def main() -> None:
    """Run the command-line collector."""
    args = parse_args()
    output_path, event_count = asyncio.run(collect(args.seconds))

    print(f"Finished: saved {event_count} events.")
    print(f"Output: {output_path.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
