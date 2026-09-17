"""Display a small sample of public BTCUSDT aggregate trades."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal

from websockets.asyncio.client import connect

STREAM_URL = "wss://data-stream.binance.vision/ws/btcusdt@aggTrade"
SAMPLE_SIZE = 10


async def main() -> None:
    """Connect to Binance and display a finite sample of aggregate trades."""
    print("Connecting to the public BTCUSDT aggregate-trade stream...")

    async with connect(STREAM_URL, open_timeout=10) as websocket:
        print("Connected. Waiting for trades...")

        for number in range(1, SAMPLE_SIZE + 1):
            message = await asyncio.wait_for(websocket.recv(), timeout=30)
            event = json.loads(message)

            if number == 1:
                print("\nFirst raw Binance event:")
                print(json.dumps(event, indent=2))
                print("\nParsed trades:")

            trade_time = datetime.fromtimestamp(
                event["T"] / 1000,
                tz=UTC,
            ).isoformat(timespec="milliseconds")

            price = Decimal(event["p"])
            quantity = Decimal(event["q"])

            # m=True means the buyer was the resting maker,
            # so the incoming aggressive order was a sell.
            aggressor_side = "SELL" if event["m"] else "BUY"

            print(
                f"{number:02d} | id={event['a']} | {trade_time} | "
                f"{aggressor_side:4} | price={price} | quantity={quantity}"
            )

    print("Finished: received 10 aggregate trades.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
