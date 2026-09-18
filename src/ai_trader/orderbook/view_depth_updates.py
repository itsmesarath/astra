"""Display BTCUSDT differential order-book updates."""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal

from websockets.asyncio.client import connect

STREAM_URL = "wss://data-stream.binance.vision/ws/btcusdt@depth@100ms"
SAMPLE_SIZE = 10


def count_removals(raw_levels: list[list[str]]) -> int:
    """Count price levels whose new quantity is zero."""
    return sum(Decimal(quantity_text) == 0 for _, quantity_text in raw_levels)


def sequence_status(
    first_update_id: int,
    previous_final_update_id: int | None,
) -> str:
    """Describe continuity relative to the previous event."""
    if previous_final_update_id is None:
        return "START"
    if first_update_id == previous_final_update_id + 1:
        return "OK"
    if first_update_id <= previous_final_update_id:
        return "OVERLAP"
    return "GAP"


async def main() -> None:
    """Receive and summarize a finite sample of depth updates."""
    print("Connecting to the public BTCUSDT differential-depth stream...")
    previous_final_update_id: int | None = None

    async with connect(STREAM_URL, open_timeout=10) as websocket:
        print("Connected. Waiting for depth updates...")

        for number in range(1, SAMPLE_SIZE + 1):
            message = await asyncio.wait_for(websocket.recv(), timeout=30)
            event = json.loads(message)

            if number == 1:
                print("\nFirst raw differential-depth event:")
                print(json.dumps(event, indent=2))
                print("\nUpdate summaries:")

            first_update_id = event["U"]
            final_update_id = event["u"]
            bid_changes = event["b"]
            ask_changes = event["a"]

            status = sequence_status(
                first_update_id,
                previous_final_update_id,
            )

            print(
                f"{number:02d} | ids={first_update_id}-{final_update_id} | "
                f"sequence={status:7} | "
                f"bid_changes={len(bid_changes)} "
                f"(removals={count_removals(bid_changes)}) | "
                f"ask_changes={len(ask_changes)} "
                f"(removals={count_removals(ask_changes)})"
            )

            previous_final_update_id = final_update_id

    print("Finished: received 10 differential-depth events.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
