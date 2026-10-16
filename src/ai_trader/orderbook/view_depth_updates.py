"""Display BTCUSDT differential order-book updates."""

from __future__ import annotations

import asyncio
import json

from websockets.asyncio.client import connect

from ai_trader.orderbook.depth_update import DepthUpdate

STREAM_URL = "wss://data-stream.binance.vision/ws/btcusdt@depth@100ms"
SAMPLE_SIZE = 10


async def main() -> None:
    """Receive and summarize a finite sample of depth updates."""
    print("Connecting to the public BTCUSDT differential-depth stream...")
    previous_final_update_id: int | None = None

    async with connect(STREAM_URL, open_timeout=10) as websocket:
        print("Connected. Waiting for depth updates...")

        for number in range(1, SAMPLE_SIZE + 1):
            message = await asyncio.wait_for(websocket.recv(), timeout=30)
            event = json.loads(message)
            update = DepthUpdate.from_event(event)

            if number == 1:
                print("\nFirst raw differential-depth event:")
                print(json.dumps(event, indent=2))
                print("\nUpdate summaries:")

            status = (
                "START"
                if previous_final_update_id is None
                else update.sequence_relation(previous_final_update_id)
            )

            print(
                f"{number:02d} | "
                f"ids={update.first_update_id}-{update.final_update_id} | "
                f"sequence={status:7} | "
                f"bid_changes={len(update.bid_changes)} "
                f"(removals={update.bid_removals}) | "
                f"ask_changes={len(update.ask_changes)} "
                f"(removals={update.ask_removals})"
            )

            previous_final_update_id = update.final_update_id

    print("Finished: received 10 differential-depth events.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
