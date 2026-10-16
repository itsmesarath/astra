"""Display interleaved BTCUSDT trades and depth updates."""

from __future__ import annotations

import asyncio
import json
import time

from websockets.asyncio.client import connect

from ai_trader.ingestion.agg_trade import AggTrade
from ai_trader.orderbook.depth_update import DepthUpdate

STREAM_URL = "wss://data-stream.binance.vision/stream?streams=btcusdt@aggTrade/btcusdt@depth@100ms"
SAMPLE_SIZE = 20


async def main() -> None:
    """Display a finite sample from two combined public streams."""
    print("Connecting to combined BTCUSDT trade and depth streams...")

    trade_count = 0
    depth_count = 0

    async with connect(
        STREAM_URL,
        open_timeout=10,
        max_queue=1024,
    ) as websocket:
        print("Connected. Waiting for interleaved events...\n")

        for number in range(1, SAMPLE_SIZE + 1):
            message = await asyncio.wait_for(websocket.recv(), timeout=30)
            received_at_ns = time.time_ns()
            wrapper = json.loads(message)

            if not isinstance(wrapper, dict):
                raise TypeError("Combined message must be a JSON object.")

            stream_name = wrapper.get("stream")
            event = wrapper.get("data")

            if not isinstance(stream_name, str):
                raise TypeError("Combined message must contain a stream name.")
            if not isinstance(event, dict):
                raise TypeError("Combined message must contain event data.")

            event_time_ms = int(str(event["E"]))
            receipt_delay_ms = received_at_ns / 1_000_000 - event_time_ms

            if stream_name == "btcusdt@aggTrade":
                trade = AggTrade.from_event(event)
                trade_count += 1

                print(
                    f"{number:02d} | TRADE | "
                    f"id={trade.aggregate_trade_id} | "
                    f"side={trade.aggressor_side:4} | "
                    f"price={trade.price} | "
                    f"quantity={trade.quantity} | "
                    f"delay={receipt_delay_ms:.1f} ms"
                )

            elif stream_name == "btcusdt@depth@100ms":
                update = DepthUpdate.from_event(event)
                depth_count += 1

                print(
                    f"{number:02d} | DEPTH | "
                    f"ids={update.first_update_id}-"
                    f"{update.final_update_id} | "
                    f"changes={update.total_changes} | "
                    f"removals="
                    f"{update.bid_removals + update.ask_removals} | "
                    f"delay={receipt_delay_ms:.1f} ms"
                )

            else:
                raise ValueError(f"Unexpected stream: {stream_name}")

    print(f"\nFinished: received {trade_count} trade events and {depth_count} depth events.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
