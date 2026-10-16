"""Synchronize and display a live BTCUSDT local order book."""

from __future__ import annotations

import asyncio
import json
import urllib.request

from websockets.asyncio.client import connect

from ai_trader.features.orderbook import OrderBookFeatures
from ai_trader.orderbook.depth_update import DepthUpdate
from ai_trader.orderbook.local_book import LocalOrderBook, SequenceGapError

SYMBOL = "BTCUSDT"
STREAM_URL = "wss://data-stream.binance.vision/ws/btcusdt@depth@100ms"
SNAPSHOT_URL = "https://data-api.binance.vision/api/v3/depth?symbol=BTCUSDT&limit=1000"
DISPLAY_UPDATES = 10
MAX_SNAPSHOT_ATTEMPTS = 5


def fetch_snapshot() -> dict[str, object]:
    """Fetch one public BTCUSDT depth snapshot."""
    with urllib.request.urlopen(SNAPSHOT_URL, timeout=10) as response:
        payload = json.load(response)

    if not isinstance(payload, dict):
        raise TypeError("Snapshot response must be a JSON object.")

    return payload


async def receive_update(websocket) -> DepthUpdate:
    """Receive and parse one differential-depth event."""
    message = await asyncio.wait_for(websocket.recv(), timeout=30)
    event = json.loads(message)

    if not isinstance(event, dict):
        raise TypeError("Depth event must be a JSON object.")

    return DepthUpdate.from_event(event)


async def synchronize(websocket) -> LocalOrderBook:
    """Align a REST snapshot with buffered WebSocket updates."""
    first_update = await receive_update(websocket)
    print(f"First buffered update: {first_update.first_update_id}-{first_update.final_update_id}")

    snapshot_event: dict[str, object] | None = None

    for attempt in range(1, MAX_SNAPSHOT_ATTEMPTS + 1):
        candidate = await asyncio.to_thread(fetch_snapshot)
        snapshot_update_id = int(str(candidate["lastUpdateId"]))

        print(f"Snapshot attempt {attempt}: lastUpdateId={snapshot_update_id}")

        if snapshot_update_id >= first_update.first_update_id:
            snapshot_event = candidate
            break

        await asyncio.sleep(0.1)

    if snapshot_event is None:
        raise RuntimeError("Could not obtain a snapshot new enough for synchronization.")

    book = LocalOrderBook.from_snapshot(SYMBOL, snapshot_event)
    print(
        f"Loaded snapshot: bids={len(book.bids)}, asks={len(book.asks)}, update_id={book.update_id}"
    )

    skipped_updates = 0
    update = first_update

    while update.final_update_id <= book.update_id:
        skipped_updates += 1
        update = await receive_update(websocket)

    print(f"Skipped {skipped_updates} update(s) covered by snapshot.")
    print(f"Bridge update: {update.first_update_id}-{update.final_update_id}")

    book.apply(update)

    print(
        f"Synchronized at update {book.update_id}: "
        f"bid={book.best_bid.price}, "
        f"ask={book.best_ask.price}, "
        f"spread={book.spread}"
    )

    return book


async def main() -> None:
    """Synchronize the book and display several continuous updates."""
    print("Opening BTCUSDT differential-depth stream...")

    async with connect(
        STREAM_URL,
        open_timeout=10,
        max_queue=1024,
    ) as websocket:
        book = await synchronize(websocket)
        print("\nLive synchronized book features:")

        for number in range(1, DISPLAY_UPDATES + 1):
            update = await receive_update(websocket)
            book.apply(update)

            features = OrderBookFeatures.from_book(
                book,
                levels=5,
            )

            print(
                f"{number:02d} | update={features.update_id} | "
                f"bid={features.best_bid_price} | "
                f"ask={features.best_ask_price} | "
                f"spread={features.spread} | "
                f"microprice={features.microprice:.8f} | "
                f"depth5={features.bid_depth}/"
                f"{features.ask_depth} BTC | "
                f"imbalance5={features.imbalance:+.4f}"
            )

    print("Finished: local book remained continuous.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SequenceGapError as error:
        raise SystemExit(f"Synchronization failed because of a sequence gap: {error}") from error
    except KeyboardInterrupt:
        print("\nStopped by user.")
