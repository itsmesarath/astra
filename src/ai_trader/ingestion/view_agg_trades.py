"""Display a small sample of public BTCUSDT aggregate trades."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from websockets.asyncio.client import connect

from ai_trader.ingestion.agg_trade import AggTrade

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
            trade = AggTrade.from_event(event)

            if number == 1:
                print("\nFirst raw Binance event:")
                print(json.dumps(event, indent=2))
                print("\nParsed trades:")

            trade_time = datetime.fromtimestamp(
                trade.trade_time_ms / 1000,
                tz=UTC,
            ).isoformat(timespec="milliseconds")

            print(
                f"{number:02d} | id={trade.aggregate_trade_id} | "
                f"{trade_time} | {trade.aggressor_side:4} | "
                f"price={trade.price} | quantity={trade.quantity} | "
                f"underlying_trades={trade.underlying_trade_count}"
            )

    print("Finished: received 10 aggregate trades.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
