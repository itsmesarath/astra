"""Display BTCUSDT top-five order-book snapshots."""

from __future__ import annotations

import asyncio
import json

from websockets.asyncio.client import connect

from ai_trader.orderbook.snapshot import PartialDepthSnapshot

STREAM_URL = "wss://data-stream.binance.vision/ws/btcusdt@depth5@100ms"
SAMPLE_SIZE = 10


async def main() -> None:
    """Receive and summarize a finite sample of top-five snapshots."""
    print("Connecting to the public BTCUSDT top-five depth stream...")

    async with connect(STREAM_URL, open_timeout=10) as websocket:
        print("Connected. Waiting for order-book snapshots...")

        for number in range(1, SAMPLE_SIZE + 1):
            message = await asyncio.wait_for(websocket.recv(), timeout=30)
            event = json.loads(message)
            snapshot = PartialDepthSnapshot.from_event(event)

            if number == 1:
                print("\nFirst raw depth snapshot:")
                print(json.dumps(event, indent=2))
                print("\nSnapshot summaries:")

            print(
                f"{number:02d} | update={snapshot.update_id} | "
                f"bid={snapshot.best_bid.price} "
                f"({snapshot.best_bid.quantity} BTC) | "
                f"ask={snapshot.best_ask.price} "
                f"({snapshot.best_ask.quantity} BTC) | "
                f"spread={snapshot.spread} | "
                f"midpoint={snapshot.midpoint} | "
                f"top5_imbalance={snapshot.imbalance:+.4f}"
            )

    print("Finished: received 10 top-five snapshots.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
