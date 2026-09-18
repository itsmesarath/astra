"""Display BTCUSDT top-five order-book snapshots."""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal

from websockets.asyncio.client import connect

STREAM_URL = "wss://data-stream.binance.vision/ws/btcusdt@depth5@100ms"
SAMPLE_SIZE = 10


def parse_levels(raw_levels: list[list[str]]) -> list[tuple[Decimal, Decimal]]:
    """Convert Binance price and quantity strings to exact decimals."""
    return [
        (Decimal(price_text), Decimal(quantity_text)) for price_text, quantity_text in raw_levels
    ]


async def main() -> None:
    """Receive and summarize a finite sample of top-five snapshots."""
    print("Connecting to the public BTCUSDT top-five depth stream...")

    async with connect(STREAM_URL, open_timeout=10) as websocket:
        print("Connected. Waiting for order-book snapshots...")

        for number in range(1, SAMPLE_SIZE + 1):
            message = await asyncio.wait_for(websocket.recv(), timeout=30)
            event = json.loads(message)

            if number == 1:
                print("\nFirst raw depth snapshot:")
                print(json.dumps(event, indent=2))
                print("\nSnapshot summaries:")

            bids = parse_levels(event["bids"])
            asks = parse_levels(event["asks"])

            if not bids or not asks:
                raise ValueError("Snapshot must contain bids and asks.")

            best_bid_price, best_bid_quantity = bids[0]
            best_ask_price, best_ask_quantity = asks[0]

            spread = best_ask_price - best_bid_price
            midpoint = (best_bid_price + best_ask_price) / 2

            total_bid_quantity = sum(
                (quantity for _, quantity in bids),
                Decimal("0"),
            )
            total_ask_quantity = sum(
                (quantity for _, quantity in asks),
                Decimal("0"),
            )
            total_quantity = total_bid_quantity + total_ask_quantity

            imbalance = (
                (total_bid_quantity - total_ask_quantity) / total_quantity
                if total_quantity
                else Decimal("0")
            )

            print(
                f"{number:02d} | update={event['lastUpdateId']} | "
                f"bid={best_bid_price} ({best_bid_quantity} BTC) | "
                f"ask={best_ask_price} ({best_ask_quantity} BTC) | "
                f"spread={spread} | midpoint={midpoint} | "
                f"top5_imbalance={imbalance:+.4f}"
            )

    print("Finished: received 10 top-five snapshots.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
