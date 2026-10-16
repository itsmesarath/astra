# Snapshot transfer diagnosis and fixes (2026-09-25)

## What was observed

The historical generic `snapshot.timeout` cannot be assigned a root cause retrospectively.
A new, single instrumented request did identify a current bottleneck: **8.018 seconds reading
the response body**, out of **9.331 seconds total**, close to the unchanged 10-second budget.
DNS took 23 ms, TCP connection 271 ms, TLS setup/handshake 502 ms, and response headers 499 ms.
The slow body reads took approximately 1.25, 3.57 and 3.20 seconds. This was a successful
request, not a reproduced timeout, and does not distinguish exchange, route, ISP or local
transport causes. It is not evidence of a DNS failure or a clock-triggered socket timeout.

A separate one-request compression experiment used the same public host and 1,000-level depth,
with `Accept-Encoding: gzip`. The server returned **9,885 compressed bytes**, expanding to
**64,047 bytes**, and passed the existing snapshot validation in **1.006 seconds**. This shows
about 85% less body data to transfer. These sequential observations are not a controlled latency
benchmark or a reliability guarantee. Neither probe opened a WebSocket or saved price levels.

## Implemented fixes

- Negotiate gzip for the single snapshot request. An identity response is still accepted; there
  is no fallback request or retry. Preserve the URL, depth, socket/elapsed deadlines and all
  capture/freshness limits.
- Cap compressed wire bytes and decompressed bytes independently at the original **1,900,000
  bytes**. Use bounded zlib output without an unbounded flush. Require one complete gzip member
  and reject corrupt checksums, truncation, trailing bytes, concatenated members, duplicate or
  unsupported content encodings. Sanitize decoding errors before failure reporting.
- Check elapsed time after decoding as well as reading and validation. Refuse late success.
- Fix a separately reproduced acquisition race: a successful snapshot observed at or after the
  overall capture deadline previously could be accepted. Now reject it as
  `snapshot.acquisition_timeout` before snapshot availability or publication. Keep this check
  snapshot-specific: changing the shared queue wait could otherwise discard an already-dequeued
  receipt. Dependency failures retain their original precedence.

Python's [bounded zlib decompression API](https://docs.python.org/3.12/library/zlib.html)
provides the output ceiling and stream-completion indicators used here. Memory may hold both
bounded compressed and decoded buffers; this is not a claim of a single-buffer allocation.

## Clock findings and user-authorized resynchronization

Three read-only checks against the computer's configured `time.google.com` reference at
14:56 UTC reported **+155.9374, +155.2911 and +156.3061 ms**: the local computer was behind
that reference. These are NTP offset estimates, not authenticated Binance-clock measurements.

After confirming no matching capture/model/training process, the authorized local
`w32tm /resync` request failed with **0x80070005, Access denied**. No privilege bypass was
attempted. The user then ran it as administrator and reported success. Windows subsequently
reported a successful sync at **14:58:59 UTC**, but the first verification samples still showed
**+156.0795, +154.2892 and +153.7995 ms**. A successful resync command does not establish
that the offset is already gone.

Final verification at **15:09 UTC** reported **+139.2404, +141.0228 and +140.4476 ms**.
The offset had reduced, but remained above 100 ms. Do not represent this as a fully corrected
clock or as proof of a current Binance freshness violation. No further resync was requested.

Read-only local registry values include `MaxAllowedPhaseOffset=1`, `PhaseCorrectRate=1` and
`UpdateInterval=360000`. Small offsets can be corrected gradually rather than stepped, per
[Microsoft's Windows Time documentation](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/Windows-Time-Service-Tools-and-Settings?tabs=config).
That is consistent with the remaining offset; no correction rate or completion time is inferred.
No time-server, registry, service, timezone or security setting was changed by the assistant.
No historical timestamps were corrected and freshness tolerances remain unchanged. Clock
suitability for the next capture still requires fresh evidence, not just command success.

## Bounded diagnostic evidence

Each new diagnostic exclusively claimed its own directory and froze its method before its
single request. Neither resumes or replaces a failed campaign; all historical raw/partial,
reserved, label and model files remain untouched and unopened.

Transport diagnostic: `logs/btcusdt_snapshot_transport_20260925_1/`

- Plan raw SHA256: `6cacf6ca2304a92d8046d45c6833b1a136bfaf2372eaff7de4f110e432e9c259`
- Result raw SHA256: `9d1e1182720782027f7b9ff1b2620bd17cdf6563e92fef77b8629bd6bc2c5400`
- Run: 14:59:29.394297 to 14:59:38.725580 UTC.
- Source remained `5c1c3dfc6c57f198271546c77b81a43198e3d80f818e1944b4c34575d621625b`.
- Transparent timing wrappers existed only in this diagnostic process and were restored in
  `finally`. Phase durations can overlap; they must not all be summed. No addresses, headers,
  payload contents or original exception text were exported.

Compression experiment: `logs/btcusdt_snapshot_compression_20260925_1/`

- Plan raw SHA256: `c1a51b86752911226687639c052db599edda5166873f942d4121dad1917e180a`
- Result raw SHA256: `b3326049797b0742deb674296e41f2638c0dcb84484d15ef0925901cc6234e46`
- Completed at 15:01:19.295837 UTC. This experimental invocation preceded the production gzip
implementation; it is not a test of the final production source.

Final production verification: `logs/btcusdt_snapshot_fixed_verification_20260925_1/`

- Plan raw SHA256: `a96b59325f8668aea61b5849c29ae342d8cb22e0090d494639423f6557e8825a`
- Result raw SHA256: `c1526ded5a61961e733c4b136df744511a82bf8c506c68178604b4dbf13cdd53`
- Run: 15:09:16.208434 to 15:09:23.617672 UTC, after the complete regression suite.
- One production fetch passed in **7.3634931 seconds**, with **9,950 wire bytes**, **64,047
  decoded bytes** and **1,000 levels per side**. Gzip was confirmed; no payload was retained.
- Source SHA256: `33c45b41a059681220c5dab3e695a77042b1463fc6be524f4d3f9bce8469b238`.
- Bounded metadata rereads verified all three diagnostic plan/result pins, single-invocation
  counts, terminal status and disabled authority. Final source remained stable after tests
  and the request. All output directories contain only their plan and result metadata.

The final **7.36-second** result is important counterevidence to any claim that compression
guarantees one-second responses. Network timing remains variable and its external root cause
unresolved. Read-only adapter diagnostics showed Wi-Fi up at a negotiated 650 Mbps and zero
reported receive/transmit error/discard counters; those counters do not rule out radio retries,
upstream loss, congestion or remote delays. No adapter, route, proxy or router setting changed.

## Verification and remaining boundary

The pre-change full baseline passed **2,716 Python tests, one optional Nautilus skip**
(141.48 seconds) and **38 JavaScript tests**. Two new acquisition-boundary regressions first
failed against the old code with actual late acceptance; six controls passed. The minimal
deadline fix then passed 128 focused cases and its eight new cases on three additional runs.

Added **56 gzip cases** covering identity compatibility, strict encodings, wire/output boundaries,
compression bombs, framing/checksum corruption, post-decode deadlines, JSON validation, response
closure and sanitized failures through the asynchronous worker. The focused compression/request/
collector run passed **122 cases**. All **64 new cases** also passed together in 0.41 seconds.
An independent read-only review exercised real 1.9-MB decoder boundaries and found no blocking
resource or correctness defect.

Final full verification: **2,780 Python passes, one optional Nautilus skip** (174.30 seconds),
**38 JavaScript passes**, Ruff lint/format clean, and `git diff --check` clean. Existing fake
responses now expose HTTP headers, and request assertions verify URL, gzip negotiation and
unchanged timeout. One deadline fake advances its clock on IO rather than depending on the
number of clock checks. Production changes are confined to the snapshot collector. Unrelated
accumulated worktree changes were preserved; all changes remain local and uncommitted.

No automatic research capture, dataset export, label generation, model training or trading
follows these diagnostics. A smaller response reduces network demand, not the requirement for
complete causal stream/snapshot validation. The previous failed sessions remain quarantined.
