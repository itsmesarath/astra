# Flow-pressure capture failure, 2026-09-25

The single-use `btcusdt-flow-pressure-v1-20260925-1` campaign failed during
its first, 120-second training window. The second train, validation and reserved
windows never started. Its original schedule SHA256 is
`8e5ca9b4a30d11d4427eeb89860869b26ed4758292c5dd99dc5552788a8502c2`;
the frozen acquisition source fingerprint is
`d691df0753dcb46d29ccecd50d034f7f88ad28128b2e6732ac9f1cc177cae88d`.
The failed campaign is not a completed dataset and must not be resumed or used
as a successful subset.

The original failure metadata reported `CaptureInterrupted` at
`integrity.rejected`. Read-only replay of the retained first training partial
identified the first rejected frame (capture line 523): an aggregate trade's
application receipt was 2,596.850 ms after its exchange event timestamp,
exceeding the frozen 2,000-ms limit. The preceding application receipt gap was
about 2,196 ms. A bounded aggregate scan found 256 trade events and 83 depth
events over the same limit; the largest lag was about 5.45 and 5.57 seconds,
respectively. Both streams were affected.

The timing sidecar reports an application queue high-water of 2/256, maximum
queue wait 2.430 ms, maximum parse/write 2.231 ms and maximum measured event-loop
lag 29.955 ms. The wall-clock and high-resolution receipt gaps agreed within
about 2 ms; no wall-clock regression was recorded. This evidence supports a
delivery hiatus before the application queue, not an observed writer backlog or
clock-step explanation. It cannot distinguish exchange, network, operating
system or WebSocket-library buffering, so none is asserted as the root cause.

The code correction makes this previously generic integrity rejection report
the allowlisted `integrity.stale_event` code for excessive event or trade-time
lag. It leaves the replay freshness bounds, capture contents, no-retry behavior,
paper/live controls and research gates unchanged. A future stale feed still
fails closed; the correction does **not** make the data fresh or make this
campaign pass. The retained original receipt and audit remain unchanged.

Raw SHA256 pins for the retained evidence:

| File in `data/raw/btcusdt_flow_pressure_v1_20260925_1/` | SHA256 |
| --- | --- |
| `failure.json` | `45578e04e98cc542d99aa4c2bb18fe56a38791af35fc3fee9a64d76f2873d9e2` |
| `audit.jsonl` | `6234433a832c7b0f75cbdcdbb48848a99b9fdd516787a3f12f08196589c668f7` |
| `btcusdt-flow-pressure-v1-01-train.jsonl.partial` | `88131e9c26ed386e733a3de0b4a0ed99fcf8f6d6e2c765bd22f67c6cbbcc1a0d` |
| `btcusdt-flow-pressure-v1-01-train.jsonl.timing.json` | `b3e7eb64be02d39b3af28fb063c8faead36c7bb12b5ac03eefb70dd7d947d478` |

Any later acquisition requires a new prospective plan, source fingerprint and
fresh output directory. A new result cannot retroactively repair this one.
