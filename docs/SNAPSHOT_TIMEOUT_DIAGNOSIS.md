# Snapshot timeout: offline diagnosis and deadline hardening

## What the failed diagnostic establishes

The [startup diagnostic](CAPTURE_STARTUP_DIAGNOSTIC.md) ended with `snapshot.timeout` while
271 events were staged, queue high-water 2/256 and no snapshot availability. The old failure
code cannot distinguish response opening from body reading or elapsed-budget expiry. It does
not establish a Binance outage, DNS/TLS/proxy problem, rate limit or local network fault.
The evidence remains unchanged; no failed raw partial or historical/reserved/model data was
opened during this follow-up. No new network request or capture was made.

Local source inspection and synthetic responses found two independent gaps:

- The 10-second elapsed budget was checked before each body read, but not after the final EOF
  or parsing/validation. A valid response completing at/after the deadline could be accepted.
  The new tests reproduced actual acceptance after late EOF/validation before the fix.
- The installed Python 3.12 executor bridge copies exact `TimeoutError` instances and drops
  custom attributes. In addition, urllib can wrap an opening timeout in `URLError.reason`,
  which the previous generic handler classified as a transport error. These facts explain
  lost diagnostic specificity, not the cause of the historical request timeout.

## Implemented changes

The existing fixed endpoint, snapshot depth, request/socket timeout, byte cap, payload validation,
capture duration, receipt clocks and freshness rules are unchanged. There is no retry, endpoint
fallback, larger deadline, new dependency or credential handling.

The elapsed budget is now checked before and after each read, after response closure and after
payload validation. Late results fail rather than being published as an available snapshot.
The check still cannot interrupt blocked OS/socket work: an individual read retains its original
socket timeout, and cancellation cannot kill urllib's worker thread. This is a late-result
rejection guarantee, not a hard total-runtime guarantee or a remedy for slow connectivity.

A small `SnapshotTimeout` subclass preserves fixed failure codes through the worker boundary;
its message contains no URL, headers, response body or original exception text. Wrapped timeout
classification inspects only the exception type, not text. HTTP error response bodies are closed
without reading them. An error during that cleanup is reported in its own right.

| New failure reason (stage remains `snapshot`) | Observed operation |
| --- | --- |
| `open_timeout` | Timeout during URL opening, including a wrapped timeout; this phase includes connection setup and waiting for response headers |
| `read_timeout` | Timeout within the acquired response's body/context lifecycle |
| `deadline` | The fixed elapsed budget was reached when checking a returned result |
| `acquisition_timeout` | The outer capture deadline ended snapshot waiting |
| `open_transport_error` | Non-timeout opening IO failure |
| `read_transport_error` | Non-timeout body/context IO failure |
| `http_error` | HTTP status rejection; error body is closed, not retained/read |
| `close_error` | Failure closing an HTTP error response |

These are operation labels, not root-cause diagnoses. Legacy generic codes remain supported;
old reports are not reclassified. Failure envelope schema remains version 1 with an extended
allowlist. Existing report/audit writers still export only allowlisted type/stage/reason values.
Other exception text may exist in process memory but is not exported by these report paths.

## Offline verification

Initial full baseline: **2,682 Python passes, one optional Nautilus skip** (186.87 s).
The first 12 new regression cases failed against the old code as expected; late EOF and late
validation actually returned a snapshot, while the remaining cases lacked phase specificity.

Added 26 snapshot regressions covering opening/body timeouts directly and through the real
executor bridge, wrapped timeouts versus other transport errors, HTTP-body cleanup and cleanup
faults, exact/late deadline boundaries, valid completion just before the deadline, and actual
collector/timing report propagation without retries, payload leakage, publication or leaked tasks.
Existing fixed-code serialization coverage also exercises all eight new failure codes. The
focused collector/burst/failure run passed 185 cases; a later focused request/failure/deadline/
collector run passed 162 before the final positive-boundary case was added. All 26 snapshot
cases then passed on three consecutive runs (1.39 s, 0.34 s, 0.32 s).

Final verification: **2,716 Python tests passed, one optional Nautilus skip** (185.01 s),
**38 JavaScript tests passed**, Ruff lint/format and `git diff --check` passed. Source fingerprint
was rechecked after the full suite and remained unchanged.

Implementation SHA256:
`5c1c3dfc6c57f198271546c77b81a43198e3d80f818e1944b4c34575d621625b`.
Historical failed diagnostic source remains
`cd760be6f423feddb22af9a29a17c7fa2fe192f5e526032c3928b011166d333b`.
No historical plan/configuration was re-pinned; the dirty worktree and all retained campaign
files were preserved. Changes remain local and uncommitted.

## Next step

A separately declared, single public snapshot-only probe can use this classification to narrow
the next observed failure without opening a WebSocket or running another research campaign.
Keep its original timeout/byte limits, prohibit retries and stop after one outcome. A success
would establish only that one snapshot request worked, not continuous capture reliability or
model-training readiness. No such probe was prepared or executed in this offline slice.
