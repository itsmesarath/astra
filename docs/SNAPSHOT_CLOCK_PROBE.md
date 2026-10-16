# Snapshot and clock diagnostic (2026-09-25)

## Outcome

The single snapshot-only request passed the existing response validation in **1.5021237 s**,
with 1,000 bid and 1,000 ask levels. Its 10-second timeout, elapsed deadline, endpoint and
1,900,000-byte cap were unchanged. Price levels were discarded rather than saved. This proves
one request worked, not continuous connectivity, stream/snapshot bridging or research readiness.
It does not explain or retroactively reclassify the earlier failed capture's snapshot timeout.

The separate exchange-time request also succeeded, but its **3.0448463-s** QPC duration made
the offset estimate **inconclusive**. The server-minus-local interval was
**[-1.0194720 s, +2.0588209 s]**, including measurement uncertainty. A positive offset would
mean the computer is behind the exchange. This interval overlaps both acceptable and
unacceptable offsets for the existing 100-ms future-skew guard; its midpoint is not an exact
clock measurement. Neither clock correctness nor a current clock fault is established.

The process ran from **14:51:09.982745 to 14:51:14.532519 UTC**, exited normally, and stopped
after the two predeclared urllib invocations. No retry, fallback, WebSocket, capture, credentials,
training, model call, trade, OS clock change or historical timestamp correction occurred.

## Why the earlier timing difference still matters

These are separate mechanisms:

- Windows' advertised `time.time` resolution is **15.625 ms**; resolution is not clock offset.
  UTC receipt timestamps feed exchange-event freshness checks, so absolute clock error can
  affect the 100-ms future-skew and 2-second lag guards. Network delay and local scheduling
  also contribute to receipt-minus-event time.
- The snapshot deadline uses nonadjustable `time.monotonic`; capture scheduling also uses
  QPC/performance-counter elapsed time. A small constant wall-clock offset does not itself
  consume a 10-second elapsed/socket timeout. The prior early-wakeup repair addressed elapsed
  waiting, not clock synchronization.
- Read-only Windows Time status at about 14:45 UTC reported phase offset **0.1847164 s**, no
  last-sync error, and last successful synchronization at **14:01:54 UTC**, roughly 43 minutes
  earlier. Its source was `time.google.com,0x8`. This local service state is not a fresh Binance
  measurement or a guarantee of present absolute error. Root dispersion was 0.4258501 s.
- The previous failed diagnostic's wall/QPC gap difference (at most 1.5173 ms, no regressions)
  described elapsed agreement, not absolute UTC accuracy. This new time probe's elapsed
  disagreement was just **0.1966 ms**, which likewise cannot establish absolute accuracy.

No freshness guard was enlarged, no timestamps were shifted, and neither this result nor the
earlier phase value clears clock suitability for a new research campaign.

## Frozen measurement method and scope

The plan was pinned before output-directory creation and any request. One public
`/api/v3/time` invocation (10-s timeout, 4,096-byte response ceiling) preceded one invocation
of unchanged production `fetch_snapshot()`. The plan required skipping the latter after an
HTTP rejection of the former; no rejection occurred. Default urllib opening behavior was
unchanged, so invocation counts are not claims about individual transport packets.

The time response was bounded and strictly parsed without duplicate/nonfinite JSON. With
server time S, local send T0 and receive T1, the declared interval is
`[S - T1 - U, S - T0 + U]`. U is the larger of elapsed wall/QPC disagreement and advertised
wall-clock resolution plus one millisecond of server timestamp granularity: **16.625 ms**
here. It assumes the server timestamp was generated during the request and no hidden clock
discontinuity. Wall regression or elapsed disagreement above 50 ms invalidates the estimate.
The acceptance classification was frozen at +/-100 ms before either request.

Binance documents the [server-time endpoint](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/general)
and the unauthenticated [market-data-only host](https://developers.binance.com/en/docs/products/spot/faqs/market_data_only).
Windows status was queried, not synchronized or reconfigured; see Microsoft's
[Windows Time tools documentation](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/Windows-Time-Service-Tools-and-Settings?tabs=config).

## Evidence pins and checks

Local metadata paths under the repository:

- Plan: `logs/btcusdt_snapshot_clock_probe_20260925_1_plan.json`
  - Raw SHA256: `433922f1cc25996c27a297f9d5a61f4b0a9e3165e2c7477b8086c1dc54b0bfa9`
- Exclusive claim: `logs/btcusdt_snapshot_clock_probe_20260925_1/started.json`
  - Raw SHA256: `13d118ef435a4ebbea30d4260d1776e44bfdb9443a4d302d4990573d9b32a6c5`
- Terminal result: `logs/btcusdt_snapshot_clock_probe_20260925_1/result.json`
  - Raw SHA256: `52ab11601f8ce51a97b9478f565426a65e9c5634f5d6f6fc767ac5a92a353a30`
- Production source SHA256:
  `5c1c3dfc6c57f198271546c77b81a43198e3d80f818e1944b4c34575d621625b`
- Runtime: Python 3.12.10, NumPy 2.5.3, websockets 17.1.

After process exit, bounded pinned reads verified plan/intent/result bindings, operation counts,
disabled authority, clock interval arithmetic, chronological metadata, unchanged source and
the output directory containing only the two metadata files (no payload or partials). These are
local integrity pins, not independent custody/authentication. Historical raw captures, failed
partials, reserved contents, labels and model files remained unopened and unchanged.

Production code did not change in this diagnostic turn. Ruff lint/format passed. The last
complete regression run remains **2,716 Python passes, one optional Nautilus skip and 38
JavaScript passes**, from the preceding source change; it was not rerun for this metadata-only
probe. Accumulated worktree changes remain local and uncommitted.

## Next boundary

Stop this one-use diagnostic regardless of success. Before another separately declared startup
capture, obtain a tighter, read-only clock-offset assessment. Do not infer an adjustment amount
from this wide interval, silently correct timestamps, relax guards, reuse failed campaign
subsets or start model training. A later capture still needs to demonstrate snapshot acquisition,
stream bridging, causal freshness and complete-session quality under unchanged limits.
