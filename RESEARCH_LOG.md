# Research Log

## Pinned public spot archive intake; training remains blocked (2026-09-25)

The user authorized dataset downloads and training. Preserved the existing dirty
worktree and did not open any prior reserved capture, model or label artifact.
Baseline: 2,780 Python tests passed, one optional Nautilus skip, 38 JavaScript tests
passed, Ruff clean. Installed only the optional binary PyArrow 25.0.1 reader in
the project virtual environment and declared a `historical` dependency extra.

Added a bounded, explicit-opt-in public Hugging Face intake and schema/footer audit.
The pilot pins Goooddy/crypto-lob-stream revision
`2b8c544ae5b46dd57c6f8807a51965d61ea4b20c`, Binance spot BTCUSDT June files,
their publisher raw-file SHA256s and sizes, and a 512-MiB aggregate ceiling. It
does not execute publisher code, use tokens, impersonate native capture records,
create labels, train, promote models or trade. Partial/failure evidence is retained;
destinations and reports are exclusive and never overwritten.

Four explicit attempts failed with transport resets before any complete file.
Public CDN/HEAD probes were intermittent; an IPv4-only curl probe succeeded. A
client-local IPv4 HTTPS option, preserving TLS hostname/certificate verification,
then completed all three files in `data/raw/hf_btcusdt_lob_june_20260925_5`:
**446,107,380 verified bytes**. No OS/network/security/clock setting changed. This
is a demonstrated workaround, not proof of the underlying network fault's cause.

The actual archive schema has sequence IDs but **no separate exchange/receipt
timestamps**. Footer counts: **68,905,191 depth rows**, **8,118,466 trades** and
**34,000 snapshot-level rows**. These are not training-example/independent-sample
counts. No price/volume rows, labels, historical reserved sources or model contents
were inspected. The checksummed schema audit reports `blocked_training_intake`:
missing timing provenance, unverified continuity/availability, and no qualified
historical adapter or frozen label/split/recipe for this archive. Training remained
at **zero epochs**, with no active-model changes or new trading authority.

See [HF_LOB_INTAKE.md](docs/HF_LOB_INTAKE.md) for exact pins, commands, limitations
and the staged historical-adapter prerequisite. Focused intake regressions cover
48 cases, including pins, byte/deadline limits, no-replacement publication, failures,
redirect scope, IPv4-local TLS safeguards and metadata-only inspection. Final full
suite: **2,828 Python tests passed, one optional Nautilus skip** (187.50 seconds),
**38 JavaScript tests passed**. Ruff lint/format, dependency and whitespace checks
passed. Final metadata reread verified receipt/audit plan and per-file identity
agreement, three completed files, no final-run partials and zero training epochs.
No commit or push was made; unrelated accumulated changes were not staged.

The latest registered historical sequence audit then scanned all **77,057,657**
stored rows in order. It recorded **647 forward-ID gaps** in both trades and depth,
**47,993** trade source-time idle gaps and **649** depth idle gaps; no source-time
regressions or nonadvancing IDs were found. The sparse snapshot stream collapsed to
17 diagnostic groups with 16 long idle gaps. These are diagnostics, not repaired
market history or missing-trade estimates. The audit retained no price/quantity
values and did not reconstruct receipt time, the book, CVD, labels or training
examples. Its status is `sequence_audit_complete_training_blocked`; training remains
at zero epochs. Report SHA256:
`b319308ae749655a1eae5e43b9bb2766899433f8399f473b98a67e50883764d4`.

The bounded report also counted 17 snapshot segments, 47,994 trade segments and
650 depth segments. It retained the first 256 trade/depth segment records and marked
those lists truncated. These are diagnostic runs between observed faults, not
training sessions; no segment was selected for fitting.

Next: implement and test a source-time-only replay/segmentation contract that treats
each gap as a hard boundary, excludes cross-boundary labels, and creates exclusive
whole-session splits before any outcome inspection. It must remain separate from the
receipt-causal live/paper adapter; no Qwen or numerical model fit is authorized by
this audit result.

## Snapshot transfer reduction and acquisition deadline fix (2026-09-25)

The user requested diagnosis and repair, not another campaign. Preserved the dirty worktree
and historical raw/partial, reserved, label and model files. Fresh complete baseline:
**2,716 Python passes, one optional Nautilus skip** (141.48 seconds), **38 JavaScript passes**.

Three read-only NTP samples found about **156 ms** of local lag against the configured
`time.google.com` reference. The user explicitly approved one Windows Time resynchronization.
After checking no capture/model/training process was active, the command failed with
**Access denied (0x80070005)**. The user performed it as administrator and reported success;
Windows confirmed a new successful sync at 14:58:59 UTC. Verification still found 154-156 ms
of offset, then about **140 ms at 15:09 UTC**. Small corrections can be gradual; no registry,
time-server, service, security or adapter setting was changed. Command success is not clock
clearance; this remains separate from nonadjustable snapshot timeout accounting.

A newly declared single instrumented snapshot succeeded in **9.331 seconds**, dominated by
**8.018 seconds of body reading**. DNS/TCP/TLS completed; this localizes that observation's
delay but does not prove the historical timeout's network root cause. A distinct bounded gzip
experiment validated the same depth in 1.006 seconds with **9,885 wire / 64,047 decoded bytes**.
Implemented gzip negotiation, identity compatibility and strict bounded single-member decoding.
Compressed wire and decoded payload each retain the original 1.9-MB ceiling; no timeout, depth
or freshness limit increased and no retry/fallback was added. Invalid encodings, checksum/framing
errors, over-expansion and late decoding fail safely.

Independent code review also reproduced a successful snapshot accepted after its outer capture
deadline. Two new tests failed before the fix. A snapshot-specific post-await QPC check now
raises `snapshot.acquisition_timeout` before availability/publication, preserving dependency
error precedence and shared queue-get receipt handling. Added eight acquisition cases and
56 compression cases. Focused suites and all 64 new cases passed; an independent bounded-memory
review found no blocking decoding defect.

Final full suite: **2,780 Python passes, one optional Nautilus skip** (174.30 seconds), **38
JavaScript passes**, Ruff lint/format and whitespace checks clean. Final production source:
`33c45b41a059681220c5dab3e695a77042b1463fc6be524f4d3f9bce8469b238`.
One separately declared final production snapshot-only verification passed in **7.3634931
seconds**, **9,950 wire / 64,047 decoded bytes**, 1,000 levels per side. Its raw result SHA256:
`c1526ded5a61961e733c4b136df744511a82bf8c506c68178604b4dbf13cdd53`.
This confirms smaller payloads but also continuing network latency variability, not a guaranteed
one-second response or a fully resolved connectivity problem. No payload was retained.

[Diagnosis, source/metadata pins and limits](docs/SNAPSHOT_TRANSFER_FIX.md) include all three
new single-request diagnostics. Bounded metadata rereads verified their claims/results and
disabled authority; no historical campaign was resumed or relabeled. No WebSocket capture,
training, model call or trade occurred. The code repairs are verified; clock suitability and
full-feed reliability remain prerequisites for a new separately declared diagnostic. Work
remains local and uncommitted; no unrelated files were staged or overwritten.

## Single snapshot and clock probe: snapshot passed, clock inconclusive (2026-09-25)

The user asked whether the earlier small time difference is affecting the system before
continuing. Read-only clock/source inspection distinguishes adjustable UTC receipt timestamps
from nonadjustable elapsed deadlines: absolute offset can affect freshness guards but does not
itself explain the 10-second snapshot timeout. Windows Time reported a 0.1847164-s phase offset
and a last successful sync about 43 minutes earlier, not a fresh exchange-relative measurement.

Predeclared exactly two public REST operations and then ran them once each at 14:51 UTC:
one bounded exchange-time request and the unchanged production snapshot fetcher. The snapshot
validated 1,000 levels per side in **1.5021237 s**; price-level payload was not retained. The time
request took **3.0448463 s**, yielding an **inconclusive [-1.0194720, +2.0588209]-s**
server-minus-local offset interval. Elapsed wall/QPC disagreement was 0.1966 ms, which is not
absolute clock accuracy. The historical timeout cause remains unknown. See
[the diagnostic report](docs/SNAPSHOT_CLOCK_PROBE.md) for method, limitations and all pins.

The one-use plan raw SHA256 is
`433922f1cc25996c27a297f9d5a61f4b0a9e3165e2c7477b8086c1dc54b0bfa9`;
terminal result raw SHA256 is
`52ab11601f8ce51a97b9478f565426a65e9c5634f5d6f6fc767ac5a92a353a30`.
Bounded metadata rereads verified the plan/intent/result/source bindings and interval arithmetic
after normal process exit. No production changes, retries, WebSockets, captures, clock changes,
guard relaxation, historical raw reads, labels, training, model calls or trades. Ruff remains
clean; the last complete suite remains 2,716 Python passes, one optional skip and 38 JavaScript
passes from the prior turn, not a new full-suite run. Work remains local and uncommitted.
Next obtain a tighter read-only clock assessment before another separately declared startup
capture; this single successful REST response is not a passing full capture or training source.

## Offline snapshot phase diagnosis and deadline hardening (2026-09-25)

Continued after the snapshot-timeout diagnostic without retrying it or making any new public
request. Checked the dirty worktree and absence of an active ingestion process. Initial complete
baseline passed **2,682 Python tests, one optional Nautilus skip** (186.87 s). Historical raw
partials, reserved data, labels and model files remained unopened and unchanged.

Source inspection and synthetic responses identified a deadline-check gap: the fetcher checked
before each read but could accept a valid snapshot whose EOF/validation returned at or after
the 10-second budget. Two initial red cases demonstrated late-result acceptance. The first
12 snapshot regressions also showed missing phase specificity: direct/threaded opening or body
timeouts, wrapped timeouts, transport failures and HTTP status errors lacked distinct codes.
Installed Python 3.12 source confirms its executor adapter copies exact TimeoutError instances;
the urllib path can also wrap an opening timeout inside URLError.reason. These observations do
not establish the cause of the earlier real network timeout.

Implemented [snapshot deadline and failure-phase hardening](docs/SNAPSHOT_TIMEOUT_DIAGNOSIS.md):
check the same elapsed budget before/after reads, after response closure and after validation;
preserve sanitized phase codes through a TimeoutError subclass; classify wrapped timeout types
without inspecting exception text; close HTTP error bodies without reading them. Distinguish
open/body IO timeouts, elapsed deadline, outer acquisition deadline, phase-specific transport,
HTTP rejection and error-response cleanup failure. Existing generic failure codes remain valid.
No retry, fallback endpoint, timeout increase, new dependency or credential handling was added.
This rejects late results; it cannot forcibly interrupt OS/socket work or terminate the worker.

Added 26 synthetic snapshot cases, plus coverage of eight new allowlisted failure codes through
the existing generic tests. Actual collector/timing-report tests assert one request invocation,
closed resources, no published capture, preserved partials, no task leaks, disabled authority
and no original URL/header/body/error text in exported reports. Exact-deadline rejection and
valid completion just before the budget are both covered. Existing startup tests now expect
the more specific outer acquisition-timeout code, without changing their timeout behavior.

Final full suite: **2,716 Python passes, one optional Nautilus skip** (185.01 s), **38 JavaScript
passes**, clean Ruff lint/format and `git diff --check`. All 26 snapshot cases passed three
consecutive runs (1.39 s, 0.34 s, 0.32 s). Source SHA256, verified after testing:
`5c1c3dfc6c57f198271546c77b81a43198e3d80f818e1944b4c34575d621625b`.
The previous failed diagnostic remains bound to its original
`cd760be6f423feddb22af9a29a17c7fa2fe192f5e526032c3928b011166d333b` source and is not reclassified.

No new network diagnostic, capture, feature export, labels, training, model call or order was
started. The real timeout cause remains unknown. Next consider one separately declared public
snapshot-only probe with original limits and no WebSocket, retry or research-fold use; none was
prepared/executed here. No old plans were re-pinned or resumed. Unrelated accumulated changes
were preserved; work remains local and uncommitted.

## Single startup diagnostic: snapshot timeout, no retry (2026-09-25)

The user authorized the next diagnostic. Froze one 120-second public BTCUSDT attempt and its
assessment before launch in `logs/btcusdt_startup_diagnostic_20260925_1_plan.json`, raw SHA256
`d6f9afe900ee37eda1fb7429a8ecbd3b47c237eccf386e770269c08726d70a98`. Reused the existing
opt-in timing runner under source
`cd760be6f423feddb22af9a29a17c7fa2fe192f5e526032c3928b011166d333b` and unchanged runtime.
Fresh Ruff checks passed, no conflicting ingestion/model/training process was found, the exact
destination was absent and about 772 GB was free. No source/dependency/configuration edits;
the preceding 2,682-pass full regression remained the baseline, not a newly executed full suite.

Launched at 14:27:47.446 UTC, PID 23672, into the new exclusive
`data/raw/btcusdt_startup_diagnostic_20260925_1/`. The command exited with code 1 at
14:28:00.494 UTC: `CaptureInterrupted` / `snapshot.timeout`. It did not complete 120 seconds.
Post-exit process checks confirmed the runner was absent. No restart, retry or replacement.

The timing report records 271 received/enqueued/parsed-staged messages, queue high-water 2/256,
271 startup queue samples (maximum 0.2927 ms), parse/stage maximum 1.787 ms and 181 watchdog
samples (maximum lag 28.164 ms). Both snapshot-availability timestamps remain null; no streaming
queue samples exist. More than the old capacity was successfully staged while pending, without
overflow, but missing snapshot/complete-session coverage fails the frozen acceptance. Zero
observed alert counters do not make this a pass. The cause of snapshot timeout remains unproven.

Bounded strict-JSON metadata verification checked declaration/intent/report raw hashes, canonical
report digest, intent reference, source/runtime, limits, diagnostic-only role and disabled
authority. Intent raw SHA256:
`26ce3d6027deea540599da3b4554e0e6880f7ce9543d69df71b860e5f1538460`.
Timing raw SHA256:
`c0db253ca887eddf21ccca212d2932ffe3ed708bffd0a794137c0754c37c71d3`.
Payload SHA256: `05955c3c05ea68e4fb2894907be24f463323913a0a6e842c29565974401a9e2c`.

Both raw partials are retained unchanged: primary 181 bytes, stream staging 223,847 bytes.
Only their filesystem metadata was inspected; no partial contents were opened, hashed or
processed, and no post-failure raw replay was performed. No historical/reserved contents,
label datasets or models were opened. No feature export, fitting, Qwen call or order occurred;
no automation was created. See [full declaration/outcome](docs/CAPTURE_STARTUP_DIAGNOSTIC.md).
Next investigate the snapshot-fetch path offline; further network checking requires its own
bounded declaration, not a silent timeout increase or another attempt at the failed claim.
All changes and evidence remain local/uncommitted.

## Offline snapshot-pending recording repair (2026-09-25)

Continued from the failed earlier-start campaign without opening its raw partial or any
reserved/label/model contents. Checked the dirty working tree and absence of acquisition
processes before source edits. The complete initial baseline produced 2,659 passes, one
failure and one optional Nautilus skip (176.49 s): the existing timed burst fixture's watchdog
advanced its synthetic receipt clock and broke an exact timestamp assertion. Made only that
fixture's watchdog deterministic; independent production watchdog coverage remains intact.

Two new synthetic pending-snapshot tests reproduced the old failure at received message 257,
with 256 queued and zero processed. The writer did not run until snapshot acquisition finished.
This does not determine why the real snapshot was delayed or the original burst arrived.

Implemented [bounded disk staging and final assembly](docs/CAPTURE_STARTUP_REPAIR.md): start
the writer alongside snapshot acquisition, retain FIFO receipt timestamps, observe writer
failures during snapshot waits, and assemble the unchanged snapshot-first raw format only
after acquisition stops. Queue remains 256; event/message ceilings, causal replay, freshness,
costs and training gates are unchanged. Idle monitoring now covers startup too. Reserve staged
bytes and their final copy within the same 32-MiB ceiling; final-file byte capacity is therefore
more conservative, not enlarged. Copy at most 64 KiB per cooperative assembly step. Failures
retain evidence; acquisition intake refuses residual stream staging. Successful validation
allows removing only this run's redundant stage before no-overwrite publication.

Timing counters measure successful parsing/staging, not final assembly/fsync. Snapshot-pending
events remain in the snapshot-buffered queue-wait bucket, whose wait now ends at staging;
disk residence is not queue latency. No pre-snapshot CVD or feature warmup is admitted.

Final full suite: **2,682 passed, one optional Nautilus skip** (171.65 s), **38 JavaScript
passes**, Ruff lint/format and `git diff --check` passed. Added 22 startup regression cases,
including timed/untimed 257/1,024/4,096-message bursts, receipt order, pending-snapshot faults,
timeouts, stale/malformed input, cancellation, quotas, real causal replay/CVD exclusion,
staging collisions, residual-stage intake, disk bounds and incomplete/canceled assembly.
The collector/timing/failure focused run passed 191 cases; the expanded startup/campaign/intake
run passed 198. All 45 startup/burst cases also passed on three consecutive runs
(14.76 s, 15.10 s, 16.56 s). Implementation SHA256:
`cd760be6f423feddb22af9a29a17c7fa2fe192f5e526032c3928b011166d333b`.

No acquisition, network request, retry, labels, fitting, Qwen call or order was started.
Historical schedules/settings/source pins remain unchanged and cannot be reused under this
code. Real-feed startup and multi-window reliability remain unverified. Next consider one
distinct predeclared operational diagnostic, not a repaired/restarted campaign or selected
training source. Existing unrelated changes are preserved; work remains local/uncommitted.

## Earlier-start campaign failed during startup buffering (2026-09-25)

Campaign -3 dispatched its first train slot at 14:03:00 UTC, connected at 14:03:01.052 UTC,
and failed at 14:03:03.979 UTC with `CaptureInterrupted` / `receiver.queue_overflow`.
The pinned four-row audit, failure receipt and timing payload agree: first train failed;
second train, validation and reserved never started. There is no completion receipt. Both
recorded process IDs were absent at the 14:07 UTC check, and the subsequent process inventory
found no windowed Python runner. Reported failure and deleted `check-bounded-binance-capture`.

Read only bounded schedule/failure/audit/research-timing metadata, verifying strict JSON, raw
hashes, schedule/session/role bindings and canonical timing payload hash with the project venv.
Source remains `e49d701cd7f6ccc7cf02f0ad2bc0f4a4e24f0617925d93103cb4bf75680b65d5`.
Timing shows 257 received, 256 enqueued, zero processed, high-water 256/256 and both snapshot
availability timestamps null. Failure occurred 2.926 seconds after connection; sampled loop
lag peaked at 15.06 ms and message-receipt gap at 450.52 ms. This establishes overflow before
snapshot availability to the collector, not the cause of snapshot delay or the incoming burst.
The earlier passing diagnostic is not sustained reliability evidence.

The 181-byte raw partial was stat-only: no content read, hash, repair, labeling or replay.
All campaign files remain retained unchanged; no retries, replacements, successful subsets,
models or orders. See [terminal result and evidence pins](docs/WINDOWED_CAMPAIGN_20260925_3.md).
Next diagnose the startup buffering path offline before proposing any new acquisition. No
source/configuration/dependency edits or test reruns were needed for this scheduling and
documentation-only turn; the earlier 2,660-pass Python/38-pass JavaScript/Ruff verification is
historical, not a new test execution. No prior failure or research-quality gate was relaxed.

## User-requested earlier start before acquisition (2026-09-25)

The user asked to start now and said the system would remain awake. Campaign -2 was still
waiting: only its copied schedule and 288-byte, one-row `started` audit existed; no session had
begun and no capture file existed. Paused its read-only follow-up during the transition. The
initial PowerShell guard refused before any process mutation because UTC/local DateTime values
were compared inconsistently; inspected exact ISO UTC creation times, corrected that diagnostic
comparison and revalidated PID, creation time, executable, command pin and parent relation.

Stopped only the waiting Python child PID 24740; its venv launcher PID 31412 also exited.
Verified both absent at **14:01:20.5082052 UTC**, still well before the old first window. Original
claim/schedule/audit remain unchanged and must not resume. The retained audit raw SHA256 is
`2bc214664003d591c8b840171d9e7ea3edfe986d59229b74ea404cba818cc0b5`. No runner-generated
failure receipt was invented. The separate operator note in
`logs/btcusdt_windowed_20260925_2_operator_cancellation.json` has raw SHA256
`1476dac6c709efe3ab3eeff93bf7da937540986ef5c403eae75e907160d82864`.

Prepared a distinct campaign -3 before any new capture, choosing the first whole-minute UTC
window at least 90 seconds ahead and subsequent windows one hour apart. This is an explicit
user-directed pre-acquisition rescheduling, not outcome-based replacement of a failed source.
Four 120-second train/train/validation/reserved slots now open at **14:03, 15:03, 16:03 and
17:03 UTC** (15:03/16:03/17:03/18:03 Lisbon), with unchanged 30-second dispatch windows.
Last footer: 17:05:45 UTC; completion grace: 17:06:15 UTC. Original acquisition limits, research
settings, processing-cap risk, fees, quality gates and disabled model/execution authority remain.

Schedule `logs/btcusdt_windowed_plan_20260925_3.json`, raw SHA256
`4232b60b17fbd0410107d2f525009bff6b8c2cf4c05620e7ffac04e9e332cd68`.
Source unchanged: `e49d701cd7f6ccc7cf02f0ad2bc0f4a4e24f0617925d93103cb4bf75680b65d5`.
Launched at **14:02:04 UTC**, venv PID **22796**, Python child **27840**, claimed directory
`data/raw/btcusdt_windowed_20260925_3/`. Checked the pinned schedule, absence of any other
windowed runner, matching new process identities and initial audit before first dispatch.
No source/dependency/configuration edits were made; prior full regression remains applicable.

Using OpenAI Docs, updated the same 15-minute read-only follow-up to the new IDs/pin/windows,
then reactivated it. It may only inspect metadata/process presence and verify all-window intake
after exit. It must report terminal evidence and delete itself; no restart, repair, raw/reserved
inspection, labels, fitting, Qwen calls, orders or later-date continuation. No source edits while
the new campaign is active. See [current campaign details](docs/WINDOWED_CAMPAIGN_20260925_3.md).
The original failed campaign, canceled waiting campaign and operational diagnostic are excluded
from this new fold. All historical evidence is retained; changes remain local/uncommitted.

## Distinct post-repair windowed campaign launched (2026-09-25)

After the user confirmed the corrected Lisbon availability window, froze and launched exactly
one new public-data campaign, `btcusdt-windowed-20260925-2`, under the repaired collector source.
The first schedule question contained an inconsistent finish time; it was corrected before
the user confirmed the four 15:15/16:15/17:15/18:15 Lisbon starts. Latest accepted completion
including grace is 18:18:15 Lisbon; allow until about 18:20 for final checks.

Baseline before launch: **2,660 Python tests passed, one optional Nautilus skip** (125.84 s),
**38 JavaScript tests passed**, Ruff lint/format and `git diff --check` clean. Preserved the
dirty/untracked tree. Host was on AC with AC idle sleep already disabled, about 772 GB free and
no conflicting ingestion/training/model process. No power/source/dependency/configuration change.

Four 120-second UTC windows open at 14:15, 15:15, 16:15 and 17:15 on September 25, each with
30 seconds for dispatch; roles are train, train, validation, reserved. Last footer: 17:17:45 UTC;
completion grace: 17:18:15 UTC. Raw budgets remain 480 nominal seconds, 128 MiB, 399,988 events.
Research stays capped at 3,000 frames/source, 9,000 total and 600,000 declared row-epochs, with
unchanged fees, slippage, labels, freshness and quality/class-diversity gates. No fitting is granted.

Before launch, explicitly disclosed that the preceding diagnostic's 6,311 replay frames would
exceed this recipe's 3,000-frame/source allowance. Future volume is unknown; a busy source must
fail the complete-session gate. Do not silently truncate, raise the budget after seeing results,
substitute quiet sources or treat acquisition success as training eligibility.

Original schedule: `logs/btcusdt_windowed_plan_20260925_2.json`, raw SHA256
`b9d7cf06b3c7466a387083f8cdcad7ad140a392a7c6150a625236cb02114d743` (5,676 bytes).
Settings raw SHA256: `9fb76e9fd3f6b1467a76dd666ba3b813c82f2e6d2d682d0d52f2d604fa79b05a`.
Frozen source: `e49d701cd7f6ccc7cf02f0ad2bc0f4a4e24f0617925d93103cb4bf75680b65d5`.
Runtime: Python 3.12.10, NumPy 2.5.3, websockets 17.1. The offline inspector passed and no
acquisition directory existed before launch. The new claimed directory is
`data/raw/btcusdt_windowed_20260925_2/`; copied schedule matches the original raw hash.

Started hidden runner at 13:52:59 UTC, launcher PID 31412 / Python child PID 24740. Checked
their matching creation times, command lines and schedule pin, plus the durable initial `started`
audit row. No session had begun and no receipt/failure existed at that check. This records
launch, not completion. Do not modify source/dependencies until the campaign terminates.

Used OpenAI Docs and the [official scheduled-task page](https://learn.chatgpt.com/docs/automations?surface=app)
to configure a read-only 15-minute task follow-up (`check-bounded-binance-capture`). It stays
quiet on normal progress, verifies all-window metadata only after process exit, reports failure/
completion/overdue evidence, then deletes itself. It cannot restart, repair, open raw/reserved
contents, prepare research, fit a model or trade. Local follow-ups require the app to remain open.
Full launch details and the terminal verification contract are in
[the campaign note](docs/WINDOWED_CAMPAIGN_20260925_2.md).

The previous failed campaign, successful diagnostic and all old datasets remain untouched and
excluded from this fold. No labels, fitting, model calls, credentials or orders were involved.
Only this one campaign was launched; no later-date continuation or automatic promotion is allowed.
Changes remain local/uncommitted.

## Prospective post-repair operational diagnostic passed (2026-09-25)

The user continued from the bounded scheduling repair. Rechecked the dirty/untracked tree,
source/runtime, destination uniqueness, free disk and absence of conflicting ingestion/training/
model processes. Full regression: **2,660 Python tests passed, one optional Nautilus skip**
(123.19 seconds), **38 JavaScript tests passed**, Ruff lint/format and `git diff --check` clean.
No source, dependencies, configuration or previous campaign artifact was changed this turn.

Before acquisition, froze one 120-second diagnostic-only sample in
`logs/btcusdt_burst_diagnostic_20260925_1_plan.json`, raw SHA256
`fcaa53ea39321d95758274c059f98583aca8ecfc23207fdaff0793018cd96162`. The declaration fixes
purpose, source/runtime, unchanged quotas, accounting/integrity checks, maximum receipt/depth
gaps of 500 ms, maximum streaming-queue/parse/loop/clock-gap metrics of 50 ms and terminal
no-retry policy. Startup snapshot-buffer waiting is explicitly assessed separately. This is a
single-diagnostic declaration, not a runnable windowed research plan or model-training grant.

Invoked the existing instrumented runner exactly once. It completed at 13:44:12 UTC; the raw
session spans 13:42:07.908541–13:44:07.913083 UTC (120.004542 seconds). It received, enqueued
and processed all 6,358 messages (5,158 aggregate trades / 1,200 depth events), writing 5,129,165
bytes. The process exited successfully and no partial publications remain.

Verified bounded intent/report/capture bytes, SHA references, report payload digest, source/runtime,
exact budgets and disabled authority; replayed only this new diagnostic through the unchanged
receipt-causal integrity validator. Counts agree with the raw footer. All predeclared diagnostic
checks pass: queue high-water 49/256, maximum QPC depth gap 326.6413 ms, all-message gap
259.7606 ms, streaming queue wait 2.0376 ms, parse/write 1.9372 ms and loop lag 25.2460 ms.
The 49 startup-buffer waits peaked at 1,389.0913 ms, separately reported as declared. No other
alert category fired; wall/depth-exchange regressions were zero. No feature dataset or labels
were exported, and no order simulation, live order, model call or fitting occurred.

Artifacts under `data/raw/btcusdt_burst_diagnostic_20260925_1/`:

- Intent: `9a48df46eb39d90343f00186e0aeb44204dfb1dde5ed0a6ea7dcc1686f353071`.
- Capture: `1dceec829cfba669c2481c03cc2239677672f580073b7d6f191826917c72f576`.
- Timing file: `673bbdef5da9570e1f6d783920e046bef43de23cc73e06fbee3d5960fdbd376f`.
- Timing payload: `38656ca4a57dfdb350d1c84b49a99ada0d770b72ba9736807e4a2781c71e164b`.
- Unchanged source: `e49d701cd7f6ccc7cf02f0ad2bc0f4a4e24f0617925d93103cb4bf75680b65d5`.

See [full declaration, verification and limitations](docs/CAPTURE_BURST_DIAGNOSTIC.md).
This operational sample did not reproduce the prior overflow/gaps; it does not prove their
cause, sustained reliability, statistical sufficiency or profitability. It must not become a
training source selected after inspection. The failed windowed campaign remains quarantined,
with no raw/reserved reads, repairs, replacements or successful-subset processing.
Next prepare a distinct prospectively assigned multi-window research fold under the repaired
source, with unchanged gates and newly agreed future windows/host availability. None was started
after this one terminal diagnostic. Artifacts are local/Git-ignored; changes remain uncommitted.

## Bounded reader/writer burst repair (2026-09-25)

Preserved the accumulated dirty/untracked tree and first ran the complete baseline:
**2,637 Python tests passed, one optional Nautilus skip** (122.11 seconds). Implemented the
next offline step identified in the diagnosis below. No real capture, failed partial, reserved
content, label dataset or model file was opened. No capture/retry, network request, model call,
training or order ran; the failed campaign and all its historical pins remain unchanged.

The receiver now stamps/enqueues then explicitly hands off per message, retaining `put_nowait`
and overflow refusal. The writer drains ready FIFO entries directly instead of creating a watched
task per item; an empty queue retains the existing watched wait and idle/early-timer handling.
Writer batches yield after 64 events or an observed 5 ms, with deadline/dependency checks between
events. The finite post-cancellation shutdown tail is cooperative too. These are scheduling
quanta, not hard deadlines inside a synchronous disk operation. Queue/event/byte/message budgets,
receipt semantics, snapshot causality, timing schema, freshness/cost/quality rules are unchanged.

The current assembler harness passes 256/257/1,024/4,096-frame production-writer cases in order,
with high-water 2/256. The old per-item-watched consumer still overflows at received message 385;
a blocked consumer still fails at 257. All seven revised scenarios repeated identically three
times. Historical harness results remain separately identified, not reinterpreted as repaired data.
Added 23 synthetic regression cases, including repeated bursts, count/time fairness, timestamp/
object identity, overload/slow snapshot, observer/receiver failure, deadline/cancellation, final
tail draining and actual receipt-causal publication/refusal under malformed data and quotas.

Final full suite: **2,660 Python tests passed, one optional Nautilus skip** (124.34 seconds),
**38 JavaScript tests passed**, Ruff lint/format and `git diff --check` clean. Production source
fingerprint is now `e49d701cd7f6ccc7cf02f0ad2bc0f4a4e24f0617925d93103cb4bf75680b65d5`;
the prior campaign source remains `c38b89a86e1be5b25f94d5e23fa66fd9cf04846d4b9d9f7315f5bbae6ced7d8a`.
See [repair details and limitations](docs/CAPTURE_BURST_REPAIR.md). Changes remain local/uncommitted.

This proves the synthetic scheduling repair, not real-feed reliability or the cause of the
2.87-second receipt gap. Next consider one distinct predeclared bounded diagnostic acquisition
under the new source pin, not a replacement window or successful-subset research. None was
prepared/launched here. Model training still needs eligible prospective data and its own gates.

## Windowed campaign failure and offline burst diagnosis (2026-09-25)

The first windowed campaign stopped during the 12:30 UTC validation session with
`receiver.queue_overflow`. Two train slots were recorded complete; reserved never started.
The runner exited, no completed receipt was published, and its scheduled follow-up was removed.
No restart, replacement or successful-subset processing followed. This turn is diagnosis only:
production code, parameters, original artifacts and historical source pins remain unchanged.

Verified the failed validation timing report's raw and canonical payload digests and its
plan/session bindings. It reports 402 received, 401 enqueued, 145 processed and a queue high-water
of 256. The retained queue was full. Maximum receipt gap was 2,868.7162 ms; maximum measured
event-loop lag 27.2741 ms, processed streaming queue wait 5.2399 ms and parse/write 1.276 ms.
These are application measurements and exclude processing latency of the unprocessed tail.
Snapshot availability preceded the overflow. No raw capture, label or reserved content was read;
the 151,623-byte validation partial was only statted, not opened or repaired.

An offline harness using installed websockets 17.1 frames/assembler and the unchanged recorder
reproduced overflow from 257 immediately buffered messages before a ready consumer processed any.
The library's 16-frame high-water requests a transport pause, not a hard cap on an already-parsed
batch. Receiver enqueueing can run without yielding; the watched writer also incurs several
scheduling turns per item. Yielding the synthetic source per message handled 257 frames but still
overflowed at received message 385 in a 1,024-frame burst (128 consumed / 256 pending). A simple
one-line yield is therefore not a sufficient general repair. A deliberately blocked consumer
still failed at the unchanged capacity. All seven scenarios repeated identically three times.

This establishes a local scheduling weakness consistent with the real telemetry, not the source
of the earlier receipt gap or the exact real transport batch. See
[evidence, reproduction and repair requirements](docs/CAPTURE_BURST_DIAGNOSIS.md). Next implement
bounded scheduling/draining with unchanged timing, ordering, causality, quotas and refusal rules,
then verify a distinct future experiment. Do not enlarge budgets or reinterpret this failed run.

Full regression: **2,637 Python tests passed, one optional Nautilus skip** (124.55 seconds),
**38 JavaScript tests passed**, Ruff lint/format clean. Source remained
`c38b89a86e1be5b25f94d5e23fa66fd9cf04846d4b9d9f7315f5bbae6ced7d8a`.
Only documentation and a synthetic diagnostic harness were added/updated. No new Binance
connection, plan, training, Qwen call or order occurred; changes remain local and uncommitted.

## First real windowed campaign launched (2026-09-25)

After the user confirmed availability for roughly 3.25 hours, froze and launched one bounded
public-data-only campaign, `btcusdt-windowed-20260925-1`. Readiness checks found the host on AC
power with AC idle sleep disabled, about 772 GB free disk space and no matching ingestion/model/
training process. No power settings changed. The immediately preceding full regression passed
**2,637 Python tests, one optional Nautilus skip** (120.58 seconds), **38 JavaScript tests** and
Ruff lint/format. Source and dependency bindings were rechecked before plan preparation/launch.

| Role | UTC dispatch window, 2026-09-25 | Lisbon start time | Nominal duration |
| --- | --- | --- | --- |
| Train 1 | 10:30:00–10:30:30 | 11:30 | 120 seconds |
| Train 2 | 11:30:00–11:30:30 | 12:30 | 120 seconds |
| Validation | 12:30:00–12:30:30 | 13:30 | 120 seconds |
| Reserved | 13:30:00–13:30:30 | 14:30 | 120 seconds |

These are predeclared observation times, not outcome-selected windows or evidence of independence.
Last accepted footer: 13:32:45 UTC; completion grace ends 13:33:15 UTC. Budgets: 480 nominal
recording seconds, 128 MiB raw captures, 399,988 stream events, 9,000 research frames and 600,000
declared training row-epochs (no fitting authorized). Costs, labels and quality gates are unchanged.

Schedule: `logs/btcusdt_windowed_plan_20260925_1.json`, raw SHA256
`8d997c8389fbe3a14e6b5d44b969d9ba3c7080d6f4dcaf7d47dc53ead80b4f73`.
Frozen source: `c38b89a86e1be5b25f94d5e23fa66fd9cf04846d4b9d9f7315f5bbae6ced7d8a`.
Settings raw pin: `9fb76e9fd3f6b1467a76dd666ba3b813c82f2e6d2d682d0d52f2d604fa79b05a`.
Environment: Python 3.12.10, NumPy 2.5.3, websockets 17.1.

Started the hidden local runner at 10:26:12 UTC, launcher PID 8488, with separate stdout/stderr
files under `logs/btcusdt_windowed_20260925_1.*.log`. Verified process presence, exclusive directory
`data/raw/btcusdt_windowed_20260925_1` and the durable `started` audit record binding the schedule
copy. At this launch check no session had begun: this entry records dispatch of the runner, not
successful acquisition. All source/dependency edits must wait until the campaign terminates.

Added a 15-minute, read-only task follow-up (`check-bounded-binance-capture`), guided by the
[official scheduled-task documentation](https://learn.chatgpt.com/docs/automations?surface=app).
It stays quiet during normal progress, verifies complete metadata only after the process exits,
and reports completion, failure or an overdue result. It must remove itself after that report.
It may not restart/repair captures, open raw or reserved contents, generate labels, prepare a
trial, call Qwen, train or trade. The collector runs independently; follow-ups require the app
to remain running. Any failed slot ends the entire campaign without a replacement or subset.

## Single-use window capture runtime and frozen-settings intake (2026-09-25)

Preserved the accumulated dirty/untracked tree. Baseline: **2,560 Python tests passed, one
optional Nautilus skip** (113.15 seconds). Added explicit runnable V2 window plans while keeping
V1 metadata-only and both wrappers incompatible with the old back-to-back runner. Preparation
still does not connect, start a timer or create an acquisition directory.

The separate public-only runner requires explicit opt-in, exclusively claims a fresh directory,
and records fsynced intent before each collector call. It checks wall time plus a fixed monotonic
origin, rejects missed windows/regressions, checks admission after connection and again after
binding/audit IO, and enforces the original raw footer bounds plus a fixed 30-second completion
grace. Cancellation drains its task, but blocked OS calls/cleanup are not hard-kill guarantees.
Every failure is terminal: no automatic resume, retry, replacement or successful-subset use.
Sanitized failure evidence uses the last valid clock sample; abrupt death/disk failure may
prevent that record, so the durable claim remains authoritative for preventing a restart.

The new metadata-only intake requires pinned schedule/receipt/audit, exact all-slot chronological
evidence and matching research timing reports. It rejects partials, failures, a legacy-plan alias,
altered clock/role/guard evidence and reserved sidecars without opening reserved contents.
Only settings embedded before capture can create the research registration/split/recipe; there
is no settings override. Historical acquisition bindings remain distinct from current research
bindings, and normal source reproduction/quality/training guards remain mandatory.

Added 67 dedicated runtime/intake cases plus expanded failure-code coverage. Tests include
virtual multi-hour waits, missed windows, clock faults, slow admission, fsync stalls, active/waiting
cancellation, watchdog cleanup, competing claims, actual synthetic subprocess death, publication
failure after receipt bytes exist, rehashed inconsistent metadata and reserved-read exclusion.
Focused new/related checks: **407 passed** (18.85 seconds). All **38 JavaScript tests passed**.

The first full suite had **2,636 passes, one optional skip and one failure** (120.46 seconds):
an existing collector test assumed strict snapshot/first-event timestamp ordering from real
clock resolution and thread scheduling; both observed timestamps were identical. Made that
test's synthetic clock and snapshot-first delivery explicit, preserving its strict assertion
and leaving recorder behavior unchanged. The corrected test passed five repeated runs.

Final full regression: **2,637 Python tests passed, one optional Nautilus skip** (121.38 seconds),
**38 JavaScript tests passed**, Ruff lint/format and diff checks passed (existing CRLF advisories
only). Source remained frozen through both full runs at
`c38b89a86e1be5b25f94d5e23fa66fd9cf04846d4b9d9f7315f5bbae6ced7d8a`.

No real windowed plan, capture, background job, historical-data read, Qwen call, training or order
occurred. Qwen remains installed but untrained, the previous numerical trial remains blocked by
one-class training data, and execution remains paper-only. Next freeze one fresh bounded
campaign against verified source/environment and choose its windows before outcomes; do not
collect until profitable or modify inspected labels/costs to pass gates. See
[runtime/intake contract and commands](docs/WINDOWED_CAPTURE_RUNTIME.md). Changes remain local
and uncommitted; earlier unrelated work remains intact.

## Bounded UTC acquisition-window contract (2026-09-25)

Preserved the accumulated dirty/untracked tree. Baseline: **2,470 Python tests passed, one
optional Nautilus skip** (112.97 seconds). Implemented offline time-window plan preparation,
strict historical metadata validation, pinned current-code loading, unstarted-plan assessment
and pure all-slot completion-time checks. The plan embeds the exact pinned research-settings
bytes, whole-session roles, inclusive UTC dispatch windows, finite deadlines/resource caps,
research-only timing contract and no-replacement/no-resume failure policy.

Windows open at least an hour apart, the first at least 60 seconds after preparation, and the
full deadline fits within seven days. Each latest capture footer plus the stricter pause/embargo
must precede the next opening. Snapshot allowance + warmup + TTL + horizon must fit the declared
duration. Existing capture quotas, 10,000 research frames and 2,000,000 row-epochs remain caps.
Time spacing/UTC date counts do not prove independence, regime coverage or future data quality.

Added `configs/windowed_event_trial_v1.json` for a candidate two-train/one-validation/one-reserved
campaign: 3,000 frames per research source, 9,000 aggregate, 600,000 declared row-epochs and
480 nominal recording seconds at 120 seconds/session. Tests lock its only differences from the
previous recipe to trial identity and per-source frame quota. All fees, slippage, labels,
freshness, quality thresholds and optimization settings are unchanged. The quota is not a
volume forecast; an incomplete source must still fail, never silently increase its budget.

Candidate settings raw SHA256:
`9fb76e9fd3f6b1467a76dd666ba3b813c82f2e6d2d682d0d52f2d604fa79b05a`.
There is no runtime, timer, daemon, actual scheduled campaign, collection or training in this
slice. Existing back-to-back execution rejects the wrapper before any collector or output-directory
access. Pure caller-supplied completion times cannot authorize research or authenticate custody.
No source declarations/hashes were fabricated to preflight the recipe. Historical data remains
unopened and unchanged; Qwen and trading gates are unchanged.

Added 90 synthetic tests; focused scheduling/acquisition/intake checks **251 passed**
(5.80 seconds). Ruff lint/format and all **38 JavaScript tests passed**. See
[the contract and commands](docs/CAPTURE_WINDOWS.md). Next: a bounded window-aware runner and
durable claims/audits plus intake that verifies the full fixed schedule and embedded settings.
Only after synthetic deadline/failure checks and a stable implementation should a new real
campaign be frozen. Changes remain local and uncommitted.

Final full regression: **2,560 Python tests passed, one optional Nautilus skip** (113.70 seconds),
**38 JavaScript tests passed**, Ruff lint/format and diff checks passed (existing CRLF advisories
only). Source was frozen through the suite at
`d85f04c2da3fe450cb64415fe18182dd9b094159613ec8616c26dd93f8817049`.

## Historical training-corpus coverage and cost audit (2026-09-25)

Preserved the dirty/untracked workspace; baseline **2,401 Python tests passed, one optional
Nautilus skip** (103.41 seconds). Added a bounded offline, explicit-pin training-artifact audit.
It checks supported historical registration/split/dataset bindings, row accounting, source-local
causality, declared quality, class diversity, overlap and frozen fee arithmetic. It opens no raw
captures, validation labels or reserved datasets and returns no training partition/model.
Historical implementation/environment remain distinct from the current auditor. Normal fitting
and replay guards are unchanged: this is descriptive historical evidence, not permission to
resume a stale trial. Even an empty observed-blocker list never grants training authority.

Audited only the pinned registration, split and training labels of campaign 20260925_2:
2,958,205 input bytes. One 119.994169-second training session, one UTC start date, 856 resolved
outcomes and class counts [856, 0, 0]. Only nine disjoint feature-to-outcome intervals can be
formed; this is not effective sample size or independent trades. All resolved exits were at the
frozen 10-second horizon. Algebraically inferred pre-cost exit-bid/entry-ask moves ranged from
-0.03084 to +1.10076 bps, versus +24.02883 bps required to break even with the frozen 10-bps
per-side fee and 2-bps per-side slippage. Mean net label return was -23.76226 bps.
These explain the quiet sample's all-loss class, not every regime or a portfolio result.
No costs/targets changed, baseline retry, Qwen call/fitting, network operation or order occurred.

Report: `logs/btcusdt_event_corpus_audit_20260925_1.json`; raw SHA256
`b4edfd3157de34fbc331eba26d2a6e50048ef0f7f73af1f9617b7abb10d37b10`.
Historical source pin remains `e07e992f614382bef00e4340739b471732bf1699b520ef72dbd6d2da21bf8022`;
auditor pin `df6df3386d071f56bf4f02505164545b04e07d70133f5835af120fa2c8e963fa`.

Added 69 synthetic audit regressions; focused audit/fold/baseline tests **184 passed**
(23.06 seconds). The first full suite had 2,469 passes, one optional skip and an existing
capture-timing test race: a worker-thread snapshot and fake stream could consume fake timestamps
in different orders. The test now synchronizes synthetic receipt with snapshot availability,
keeping exact byte equality. Recorder code/behavior is unchanged. Focused timing/audit tests:
**106 passed** (12.08 seconds).

The synchronized byte-equality test also passed five repeated runs. Final full regression:
**2,470 Python tests passed, one optional Nautilus skip** (112.96 seconds), **38 JavaScript
tests passed**, Ruff lint/format and diff checks passed (existing CRLF advisories only).
The audit implementation pin remained unchanged; only tests/docs changed after its report.

See [the audit contract and results](docs/EVENT_CORPUS_AUDIT.md). Next implement a fixed,
bounded multi-window acquisition contract before more collection: separated times/dates,
predeclared assignments/quotas/failure handling and no outcome-based replacement or stopping.
Any alternate horizon hypothesis needs a separate preregistered fresh-data experiment. Broader
market labels do not substitute for Qwen's separate protected-case/custody gates. No acquisition
schedule/service was created. Changes remain local and uncommitted.

## Safe failure evidence and a quality-passing, one-class corpus (2026-09-25)

Preserved the accumulated dirty/untracked worktree. Baseline: **2,331 Python tests passed,
one optional Nautilus skip** (100.69 seconds), **38 JavaScript tests passed**, Ruff clean.
Added allowlisted failure-stage/reason evidence without serializing messages, reprs, stack traces,
packet contents, socket close text or unrecognized exception type names. Explicit cause chains
are bounded to eight; unknown failures stay unclassified and later cleanup failures retain their
own code. Existing exception classes and failure/cleanup behavior remain unchanged.

Recorder, prospective failure receipts/audits, diagnostic sidecars and legacy supervisor now
use safe evidence; CLI runtime errors avoid raw tracebacks. Completed capture/timing/plan formats
and all training/execution gates are unchanged. Synthetic tests exposed timeout-attribute loss
across Python's worker-Future adaptation; snapshot classification now happens after that boundary.
Added 70 synthetic tests. Focused suite: **332 passed** (22.48 seconds). Full final verification:
**2,401 Python tests passed, one optional skip** (104.48 seconds), **38 JavaScript tests passed**,
Ruff lint/format clean (257 files). No source edits occurred during the suite or actual experiment.

Prepared a new campaign and research intent before collection, with unchanged two-minute settings,
one train/validation/reserved slot each and five-second pauses. One attempt per slot; no retries.
Original plan: `logs/btcusdt_instrumented_plan_20260925_2.json`, raw pin
`07e953a452821fc379c5fb215f7c26b54029b8075ffa91d9c8d3a3c05dee44f7`.
Implementation throughout: `e07e992f614382bef00e4340739b471732bf1699b520ef72dbd6d2da21bf8022`.

All three sessions **completed**. Train: 485 trades / 1,199 depth events / 1,083,763 bytes;
validation: 580 / 1,199 / 1,090,501; reserved acquisition metadata: 607 / 1,200 / 1,223,917.
No partials remain in the new campaign. The earlier failed campaign and all historical reserved
sources remain untouched. Acquisition checks reserved integrity, but research/training never open
its raw contents. This successful sample does not establish the earlier interruption's cause or
sustained operational reliability.

The training stream reproduced two >500-ms QPC depth-receipt gaps (517.5469 / 566.5150 ms),
each with adjacent exchange-event times only 100 ms apart. Measured loop lag peaked at 25.9057 ms,
streaming queue wait 3.4660 ms. Validation depth gap peaked at 228.1435 ms, loop lag 26.7279 ms,
queue wait 5.1136 ms. No large measured consumer backlog accompanies those receipt stalls, but
network versus internal WebSocket buffering and other causes remain unproven. No gap was repaired.

Metadata-only research preparation froze the original source split and unchanged recipe before
labeling. Both research sources were fully consumed and reproduced with zero replay market-fault
frames. Train: 1,671 frames, 1,079 eligible, 856 resolved (79.3327%), 223 censored, 592 excluded.
Validation: 1,763 frames, 1,076 eligible, 974 resolved (90.5204%), 102 censored, 687 excluded.
Both pass the original 50%-resolved/50-example gates. Training censored 201 labels at stale quotes
and 22 at session end; validation censored 102 at session end. Reserved research reads: zero.

The one fixed NumPy attempt returned **`blocked_training_classes`**, not a fitted model.
All 856 training labels were net losses: class counts [856, 0, 0]. Zero epochs, training_started
false, model null and validation evaluation null. No preprocessing fit, optimization, Qwen calls,
Qwen training, model promotion, orders or credentials. Training-only readout: net counterfactual
returns -24.0020 to -22.8731 bps, mean -23.7623 bps, under frozen research costs. These are
overlapping unit-long sampled-quote labels from a quiet two-minute window, not portfolio PnL,
independent trades or a universal market conclusion. No costs/targets were tuned after outcomes.

Raw directory `data/raw/btcusdt_instrumented_20260925_2/`; research directory
`data/processed/btcusdt_instrumented_events_20260925_2/`. Full pins and interpretation are in
[the failure-evidence and follow-up report](docs/CAPTURE_FAILURE_EVIDENCE.md).
Baseline raw file pin: `3b1867a81f2d83d0079d0ae54b81e928a5bca05c9cda6cbd32c6289ebd3db2ac`;
canonical result digest: `a11fec79d5e930d443556c54921035eb7962c4b2af4582d95bcd3877c0f4bc9c`.

Next: bounded corpus coverage/class-readiness and training-only cost/target feasibility auditing,
then a prospective plan for independent time windows/regimes. Do not borrow validation/reserved
examples, duplicate positives, weaken costs, or change inspected labels to force a fit. Qwen's
separate protected-case/custody gate remains. Changes remain local and uncommitted.

## Instrumented prospective campaign and timer-expiry regression (2026-09-25)

Preserved the accumulated dirty/untracked worktree. Baseline: **2,281 Python tests passed,
one optional Nautilus skip** (100.30 seconds), **38 JavaScript tests passed**, Ruff clean.
Added an opt-in version-2 acquisition plan that freezes timing diagnostics for train/validation
only. Every research slot receives a fresh bounded observer; sidecar publication is required,
and its byte/hash/source/plan binding is recorded in the receipt and audit. Reserved slots
receive no timing observer or sidecar. Metadata-only research intake verifies the research
reports and refuses reserved telemetry without opening it. Legacy v1 behavior remains supported.

Added 41 synthetic regressions for contract immutability, count reconciliation, report identity,
no raw/reserved opens in preparation, cancellation/failure retention, no retries, malformed or
re-pinned reports and unchanged research settings. The new two-minute-session configuration
changes only trial identity and processing allowance (5,000 frames/source, 10,000 total); costs,
500-ms freshness, 10-second horizon, 50% resolved fraction, embargo and all other rules remain.
Pre-capture verification: **2,322 Python tests passed / one optional skip** (98.04 seconds).

Froze one 3 x 120-second train/validation/reserved campaign plus five-second pauses, under
`data/raw/btcusdt_instrumented_20260925_1/`. Plan raw pin:
`338ac61ea820f6e19003d4fa4d8dabacb64d584cb7001781e13328c6f67b7c49`.
The pre-capture research intent pinned the longer-session settings and at most one gated NumPy
attempt after complete acquisition. Historical acquisition implementation:
`78154d9de71b15671c6307bf2a1b300ee525c034891dab9eb9b36e76437760a1`.

The campaign **failed and remains quarantined**. Train completed (978 trades, 1,200 depth
updates, 1,556,048 bytes). Validation stopped with `CaptureInterrupted`, retaining 1,188 trades
and 1,199 depth events in a 1,712,962-byte partial with no footer; last receipt was 119.9408186
seconds after its header. Reserved was never started. There was no retry, replacement, labeling,
fold creation, NumPy attempt, Qwen call/training, order or reserved-source research read.

Both measured streams had zero depth-receipt gaps above 500 ms. Maximum QPC depth gaps were
145.9673 / 139.9890 ms, loop lag 26.9258 / 27.5383 ms, streaming queue wait 2.7503 / 1.7011 ms
(train/validation). Validation's startup-buffer wait peaked at 3,398.1491 ms, separate from normal
streaming. Read-only validation-partial inspection found zero event/trade ages above two seconds;
maximum event age was 853.9245 ms and trade execution age 829.4511 ms. The complete replay loader
correctly refused the missing footer. No repaired footer, substituted timestamps or usable dataset
was generated. Recorded exception type alone does not establish the real interruption's branch
or cause; this is not a proven stale-data failure, nor a reproduction of the old depth stalls.

Separately reproduced an early-timer-wakeup defect with a failing synthetic test: the old wait
immediately timed out and canceled its pending queue get even though its budget had not expired.
The installed asyncio scheduler can release timers within one loop-clock resolution early.
Corrected session/wait deadlines to QPC-backed `perf_counter`, retaining the same pending task
until actual expiry. A resolution-sized repeat wait avoids sub-tick spinning; a private elapsed-
budget exception distinguishes our timer from dependency failures. No raw timestamp or freshness
gate changed. This confirmed code defect is not proof of the real campaign's cause. No second
public acquisition was run under the correction; original artifacts/pins remain unchanged.

Added nine further synthetic deadline regressions. Final: **2,331 Python tests passed, one
optional skip** (100.90 seconds), **38 JavaScript tests passed**, Ruff lint/format and diff checks
passed. Focused capture suite: 247 passed. Current implementation:
`5515070a8e29487e6b9f990a03a58a9b8b8a4001d34339b47d55c24a45b66e52`.
Detailed contract, limits, pins and measured results: [instrumented campaign](docs/INSTRUMENTED_CAMPAIGN.md).

Next add sanitized failure-stage/reason evidence, then a separately pinned bounded campaign under
the corrected code and unchanged quality settings. Only a complete campaign can enter label and
class-diversity checks. All earlier failed-quality results and reserved sources remain untouched.
Changes remain local and uncommitted.

## Bounded capture timing and one measured diagnostic session (2026-09-24)

Preserved the existing dirty/untracked worktree. Baseline: **2,244 Python tests passed, one
optional Nautilus skip** (97.92 seconds). Added opt-in `CaptureTiming` counters to the existing
collector and a single-attempt diagnostic wrapper in `ingestion.capture_timing`. Raw capture
schema and wall-clock receipts stay unchanged; a deterministic test compares complete raw
bytes with instrumentation enabled/disabled. No timestamps were interpolated or repaired.

Local Python reports `GetSystemTimeAsFileTime()` and `GetTickCount64()` clocks at 15.625-ms
resolution, versus monotonic `QueryPerformanceCounter()` at 100 ns. Diagnostics therefore use
`perf_counter_ns`, not the coarser `monotonic_ns`, while retaining original UTC/wall receipts.
Reported clock resolution is metadata, not measured end-to-end accuracy or proof of stall cause.

Fixed histograms and first-32-per-metric anomaly caps cover dual-clock receipt gaps, clock-gap
differences, depth-event cadence, event-loop wakeup lateness, queue high-water/wait and stream
parse/write duration. Snapshot-buffer waiting is separate. A 50-ms probe skips missed periods,
never catches up in a busy loop; it excludes connection setup, offline validation and shutdown.
No per-message diagnostic disk writes or payload logging. Capture/observer failures stop and
clean up both tasks; a diagnostic-publication failure preserves any already-valid capture.
Explicit opt-in, new directory, 1–300 seconds, fixed existing recorder limits, no retry/resume.

Added **37 synthetic tests** for metrics, exact raw parity, startup/streaming accounting, clocks,
bounded samples, cancellation, observer failures, quotas, publication errors, drift and CLI
class identity. Final verification: **2,281 Python tests passed, one optional skip** (99.06
seconds); **38 JavaScript tests passed**; Ruff lint/format passed.

Ran exactly one new 60-second public-data diagnostic session in
`data/raw/btcusdt_timing_20260924_1/`. It completed with 224 aggregate trades and 599 depth events,
823 received/enqueued/processed messages and 508,583 raw bytes. No partials remain. Largest QPC
depth-receipt gap 437.0970 ms; no gap exceeded 500 ms. Maximum event-loop probe lag 29.0149 ms
across 1,087 samples; streaming queue wait 1.8903 ms across 807 messages; stream parse/write
0.3462 ms. Sixteen startup-buffered messages waited up to 1,420.7636 ms for the snapshot, which
must not be confused with streaming backlog. Queue high-water 47/256; 129 equal adjacent wall
receipts; no wall/depth-exchange timestamp regressions; maximum clock-gap difference 1.5033 ms.

The earlier >500-ms gaps **were not reproduced**. This one differently loaded sample does not
prove their cause, a latency fix, sustained reliability or training eligibility. No freshness
or label gates were changed, and the previous failed-quality fold was not recomputed or repaired.
Intent/source/report hashes and exact measurement semantics are in [the diagnostic report](docs/CAPTURE_TIMING.md).
Implementation stayed `4723ec60ff1901e91300eabfd6d95ad1938ed828dab089e93e05682da33529c0`;
timing report raw SHA256 `cd8d585a55dd2bc4c2367feb59534a551655b65a6491f0ccef1ef3d811b2383c`.

Next: longer newly planned multi-session acquisition carrying the optional diagnostics, then
unchanged event-label quality checks. Keep failures and all split assignments; do not select
successful intervals. This diagnostic source is inspected research data, not an independent
holdout. No old reserved source, credentials, model fitting, Qwen calls or orders were involved.
Changes remain local and uncommitted.

## Prospective event-label handoff and honest quality refusal (2026-09-24)

Preserved the existing dirty/untracked worktree. Baseline: **2,192 Python tests passed, one
optional Nautilus skip** (93.63 seconds). Added `research.prospective_trial` and a fixed first
configuration. The handoff verifies pinned acquisition metadata/audit without opening raw data,
derives all source assignments and the training-session count from the original plan, and freezes
research registration, fold and baseline recipe in a new directory. It retains historical
acquisition fingerprints separately from the current research implementation; no original
manifest or source hash is rewritten. Existing source-reproduction and reserved-source gates remain.

Added **52 synthetic tests**, including re-pinned bad receipts, role changes, aliases, chronology,
audit corruption, partial publications, budgets, final code/runtime drift, no network/raw opens and
no fitting during preparation. Final verification: **2,244 Python tests passed, one optional skip**
(99.07 seconds), all **38 JavaScript tests passed**, Ruff lint/format passed.

Before opening research outcomes, froze `configs/prospective_event_trial_v1.json` at raw SHA256
`2e7e72ade98388aa4f928f2166bb8dc9328baa7c5b3b88febaae659dae12fdc7`: top-five/10-second CVD context,
10-bps liquidity band, 500-ms quote age/gap, 2-second trade age, 1-second entry TTL, 10-second hold,
20-bps stop, 40-bps target, assumed 10-bps fee and 2-bps slippage each side. These are declared
research assumptions, not verified account fees or a recommended trading policy. The strategy
control is abstain; labels sample all eligible observations independently of strategy thresholds.
Per-source cap 2,500 frames, five-second embargo, at least 50 resolved labels and 50% resolved
fraction; NumPy recipe 100 fixed epochs, LR 0.05, L2 0.01, with the existing two-class gate.

Prepared at `1790284791337740400` ns and labeled only train/validation, then reproduced both via
the source verifier. Complete sessions, zero replay market faults: training 1,599 frames, 474
eligible, 151 resolved, 323 censored and 1,125 excluded; validation 924 frames, 414 eligible,
247 resolved, 167 censored and 510 excluded. Training resolved fraction **31.8565%** failed the
fixed 50% rule; validation **59.6618%** passed. As designed, neither partition was released.
One explicit bounded baseline invocation returned `blocked_source_quality`, with null model/fit/
validation and `training_started=false`. **No fitting, retries, retuning or source substitutions.**

Read-only diagnostics found three stale-quote instants at 682.0311, 571.7663 and 1,039.2908 ms
that censored 222 pending training examples; session end censored 101 more. A 580.3005-ms gap
during warmup had no pending eligible labels. Validation had a 533.6426-ms interquote gap censoring
87 examples, plus 80 at session end. Adjacent depth exchange-event timestamps across all these
gaps were only 100 ms apart. This demonstrates bursty application receipts, not their underlying
network/OS/scheduling cause or one-way latency. Equal receipt times were neither interpolated nor
reordered. The two-second transport integrity gate is not the stricter 500-ms label-continuity gate.

Artifacts are local/Git-ignored in `data/processed/btcusdt_prospective_events_20260924_1/`.
Research implementation remained `1911d4139f455a5b64ae0e6c57e91c26393ca486be3ca937f5f09f3701e14b92`.
Baseline refusal raw file SHA256 `5ca1a50c2f2a71238cb96930b9b931256aa40d305cd038cb990711f55c1b53cb`;
canonical result digest `00a0ef43f17d20013b09fa7f34dc03cc7517455c6ad7b91d7933477719cdb0aa`.
See [full settings, source results and pins](docs/PROSPECTIVE_EVENT_TRIAL.md).

Next: bounded timing/queue/event-loop diagnostics, then longer prospectively assigned captures
without relaxing quote continuity or resolved-fraction requirements. Longer data reduces boundary
censoring but does not cure stalled receipts. Reserved raw data stayed unopened; no Qwen calls,
optimizations, account credentials, feed connections or orders occurred this turn. Qwen fitting
still needs separate evaluation/custody evidence. Changes remain local and uncommitted.

## Prospective whole-session acquisition and first three-way capture (2026-09-24)

Preserved the existing dirty/untracked worktree. Baseline: **2,124 passed, one optional Nautilus
skip** (91.47 seconds). Implemented `ingestion.planned_capture`: offline preparation freezes
train/validation/reserved session IDs, exact paths, chronology, limits and code/runtime before
capture. The runner requires the byte-pinned plan and explicit public-data opt-in, claims a new
directory, fsyncs intents and uses the existing integrity-checked recorder once per slot.

Budgets: 3–8 sessions, 30–300 seconds each, at most 1,200 seconds of acquisition, 0–60-second gaps,
fixed 32 MiB/session and existing buffer/event/freshness limits. Any interruption, cancellation,
quota, clock, source drift or publication failure stops the whole campaign. No retry, replacement,
reassignment, resume or successful-subset selection. Partial and completed files are retained.
Metadata publication uses fsynced exclusive partials and no-overwrite hard links. Local disk/OS
stalls and independent custody are not solved by this finite application budget.

Added **68 synthetic tests** for schema/budgets, immutable assignments, no network before opt-in,
pin/runtime drift, receipt timing, gaps, freshness/sequence faults, cancellation, existing files,
disk/publication failures and private-payload-free metadata. One full-suite attempt caught a source
edit made during an existing registration test; this was the intended source-drift guard. Stopped
source edits and reran cleanly: **2,192 passed, one optional skip** (92.61 seconds). Ruff lint/format
and all **38 JavaScript workbench tests** passed. No guard was weakened.

Then prepared `logs/btcusdt_prospective_plan_20260924_1.json`, raw SHA256
`697f53f53227097d1370d9fc2458769b04f245b1b5d7167fe7d73d2ebcacbc44`, and ran exactly the frozen
three 60-second sessions with five-second minimum gaps. All completed under unchanged code and
limits: train 1,025 trades/600 depth events; validation 338/599; reserved 381/599. Total raw bytes
2,599,220. Actual gaps were 9.587 and 9.402 seconds. No retry, feature/label export, fitting,
model call or order. The acquisition process checked the reserved raw bytes for the same fixed
transport integrity rules; research saw metadata only. Do not call this authenticated independent
Qwen holdout custody or adequate training coverage.

Complete artifacts remain local/Git-ignored in `data/raw/btcusdt_prospective_20260924_1/`.
Receipt raw SHA256 `c4c1a10b2fdcf504f27030ffb72e6ce36e39df8e53b62e1d16feecac5bbf3baf` matches
the final audit's publication intent; no partial/failure files remain in this campaign. The prior
quarantined capture and superseded artifacts were neither deleted nor included. See
[the exact source pins and contract](docs/PROSPECTIVE_CAPTURE_PLAN.md).

Next: register causal event-label and numerical baseline settings against the fixed research
split, validate quality without opening reserved content, and report insufficient-data outcomes
without tuning away failures. Qwen fitting and its protected-case/custody requirement remain
pending. No credentials, account connectivity, training/promotion permission or live execution
was added. Changes remain local and uncommitted.

## Fresh market-data readiness and snapshot-lookahead fix (2026-09-24)

Preserved the accumulated dirty/untracked worktree. Baseline: **2,090 passed, one optional
Nautilus skip** (91.71 seconds). No independent evaluation payload was available, so addressed
the operational data prerequisite: one new bounded 60-second public BTCUSDT capture, one attempt,
no automatic retries, credentials or orders. It passed the unchanged recorder integrity and
2-second lag/100-ms future-skew checks. Captured 622 aggregate-trade and 600 depth events in
892,653 bytes. Maximum receipt-minus-event difference was 168.2362 ms; maximum receipt-minus-
trade-time difference was 195.2362 ms. These are not one-way latency or long-run stability claims.

The offline kill-switch-armed paper smoke consumed all 1,206 frames with zero market faults or
orders; simulated cash remained 1,000 USDT and position zero. Initial standalone feature export
produced 590 observations and its old audit reported 500 usable rows. A deeper comparison found
the first feature preceded recorded snapshot receipt by **402.941 ms**. Both exporter and audit
shared this snapshot-lookahead bug; a reproduction pass was not enough. The paper replay already
handled the boundary correctly and did not consume these premature standalone rows.

Fixed exporter and audit to require explicit ordered integer snapshot availability. Buffered depth
bridges book state only; receipts at or before snapshot receipt emit no features and cannot seed
causal CVD, warmup or attribution. A fresh post-snapshot engine starts strictly later. A separate
validation-only engine retains full-stream numeric/chronology/coverage/buffer safeguards, including
ignored buffered events; its rows/state are never used as causal features. This uses two bounded
engine states and does not introduce new workers or change the trading replay algorithm.

Standalone artifacts now have envelope version 2, explicit snapshot availability/policy and a
post-snapshot CVD policy. Numeric observation fields remain unchanged. `capture_quality_v2` counts
buffered applied-depth updates and ignored trades separately. Its count invariant includes buffered
updates; it rejects version-1 standalone artifacts rather than silently endorsing old semantics.
Legacy captures lacking snapshot timing must not receive invented metadata. Other CSV loaders were
not changed. Older generated files are retained for diagnosis and must not be used for training.

Rebuilt into a new v2 artifact: **585 observations, 484 passing the retrospective feature-quality
checks**, 101 warmup observations, five buffered applied-depth updates and three buffered trades.
There is one invalid interval, 28 unmatched trades, no incomplete depth coverage and no trailing or
pending trades. These QA conditions are not the stricter event-label eligibility rule. Every one
of the 585 rows exactly matches the independent existing `CaptureReplay` reconstruction; none is
at/before snapshot availability. A new dedicated v2 paper-smoke journal again passed all 1,206
frames with zero orders. The pre-fix journal was not resumed under changed implementation hashes.

Added **34 regression tests** for boundary equality, retained book state, cold CVD/warmup,
independence from excluded trade sizes, exact replay parity, required metadata, legacy/tampered
artifact rejection and preserved validation of corrupt buffered events. Corrected one synthetic
expectation to use configured top-one depth (9), rather than summing two book levels (12); the
production depth logic was unchanged. Final full suite: **2,124 passed, one optional Nautilus skip**
(92.16 seconds). Ruff lint/format and tracked whitespace checks pass.

See [REAL_DATA_READINESS.md](docs/REAL_DATA_READINESS.md) for exact local artifact pins and measured
results. The first artifact's 500-row QA result is superseded, not training evidence. This new
session is an inspected operational research sample, never a retroactively named final holdout.
The earlier failed partial remains quarantined. No Qwen calls, fitting, model downloads, account
connections or live trading occurred; public market data was the only network activity.

Next: freeze a bounded chronological multi-session acquisition/split plan, collect more research
sessions and separately reserve future evaluation data before inspecting outcomes. Then validate
real causal event labels and baselines. Qwen's protected-case registry is still empty and its
existing LoRA launch remains gated by actual independent evaluation/custody. This change removes
a real data-leakage defect; it does not establish a profitable or unattended bot. Work remains
local/uncommitted; no unrelated changes were staged or published.

## Protected evaluation payload intake (2026-09-24)

Preserved the accumulated dirty/untracked worktree. Baseline: **2,039 passed, one optional
Nautilus skip** (89.06 seconds). The 14-target delegated review is complete, but the current
protected reservation is still empty. Identified a concrete missing component: existing training
gates checked declared evaluation metadata without a tool to derive it from actual payloads.

Added `research/protected_intake.py`, with separate prepare/verify commands for evaluation custody.
It reads one explicit, bounded, raw-SHA-pinned protected dataset, shares the existing strict case
parser and preserves default development/training split restrictions. Protected cases use their
own envelope and `protected_eval` split; they cannot enter the ordinary development-suite loader.
The intake checks schema, citation references, real input refusals, exact numeric target agreement,
support/veto/refusal coverage, declared session ownership and normalized duplicates/overlap against
all 25 exposed cases. Renaming IDs, equivalent decimal formatting, evidence ordering or shifting
absolute time cannot conceal an exact duplicate. Semantic near-duplicates remain unverified.

Output is a pending metadata-only registry plus an aggregate receipt, with no evidence values,
rationale text, per-case labels or private dataset paths. Verification rereads the pinned private
source and reconstructs both artifacts; even rationale-only source drift fails the raw hash check.
All checks precede exclusive output-directory creation; writes are fsynced, the receipt is last,
failures preserve partials, and there is no retry or overwrite. CLI errors do not print private
parser details. This is a separate component, not an OS sandbox or proof that nobody saw the data.

The intake does not invent independent examples, attest an identity, review target semantics or
complete custody. `reservation_complete`, semantic/independence claims and all training/promotion/
execution permissions remain false. It does not reintroduce manual curriculum target review.
Only the pending registry belongs in the metadata-only training interface; that interface still
does not read private evaluation payloads. No actual protected data or custodian approval was
created, and no weights, training, capture, downloads or orders were started.

Added **51 synthetic regression tests**, including private-target non-disclosure, changed pins,
authority tampering, shared-session and normalized-content overlap, source-only rationale drift,
exclusive outputs, malformed/oversized JSON and preserved partials after simulated disk failure.
The oversized parameter initially produced test-harness setup/teardown errors with its enormous
generated identifier; an explicit short test ID fixes this without changing the input-size guard.
All 51 focused cases pass. Final full suite: **2,090 passed, one optional Nautilus skip**
(89.82 seconds). Ruff lint/format and tracked whitespace checks pass.

Independently reverified the unchanged real V2 candidate: 14 examples, `human_reviewed: false`.
The frozen suite, original proposal and empty protected reservation retain their recorded raw
hashes. Shared parser refactoring changes the training implementation hash, so future launches
must be prepared anew; no new native tiny-model or Qwen compatibility result is claimed.
Work remains local/uncommitted; no unrelated changes were staged or published.

See [the intake contract and commands](docs/QWEN_PROTECTED_INTAKE.md). Next is separately sourced
evaluation data with substantiated targets/custody, then a fresh bounded Qwen CUDA LoRA trial.
Actual-market learning still needs eligible causal order-book/CVD/microstructure sessions, and
the failed public capture stays quarantined. The software remains paper-only.

## User-delegated AI target review and verified candidate (2026-09-24)

The user explicitly stated: "no need for manual review. you can take the decision." Preserved
the accumulated dirty/untracked worktree. Baseline: **2,004 passed, one optional Nautilus skip**
(88.13 seconds). Implemented a versioned delegated-agent curriculum workflow; this supersedes
the previous entry's manual-target-review next step, without fabricating any human approval.

Added a bounded, suite-pinned delegation record with the user's actual instruction, agent identity,
UTC timestamp and curriculum-only scope. `prepare-delegated` requires its raw-file hash and
produces pending decisions/null checks, not automatic approvals. The V2 audit requires a confirmed
matching agent, a non-predating timestamp, explicit decisions/reasons and the existing per-case
schema/citation/verdict/arithmetic and class-coverage gates. It refuses human relabeling. Legacy
V1 operator-review shapes and semantics remain unchanged; a V1 agent proposal is still ineligible.

Read all 14 full evidence packets and proposed answers. Accepted the 11 veto and 3 conditional
support targets as a synthetic language-review curriculum, writing individual findings about
missing returns, exact net/stress arithmetic, proxy uncertainty, injection resistance and reported
kill/loss flags. Target strings are unchanged from the earlier reviewed proposal. No hidden orders,
calibration, realized profits, verified account state or execution authority were inferred.

Created and audited the V2 review, exported the candidate and independently reconstructed it
from the pinned inputs. All 14 cases are agent-approved; zero are operator-approved. The audit
and candidate explicitly record `human_reviewed: false`. Identity/delegation authentication and
machine verification of rationale semantics remain false. These are fallible local judgments,
not independent certification; the actual user message, not a self-asserted JSON field, is the
authority for delegation. See [the artifact/hash record](docs/QWEN_DELEGATED_REVIEW.md).

Ran a real CPU tokenizer preflight in the existing `.venv-qwen-train`: all 14 reviewed targets
fit the completion-only protocol and the incomplete-review blocker is gone. No Qwen weights,
GPU worker, fitting, downloads or trades were started. The saved protected-evaluation registry
remains empty. The draft planner's legacy worker/environment blocker strings were preserved;
they are not current scans of the separate implemented worker/pinned training environment.

Added **35 tests** for strict delegation and provenance, missing/pending/rejected decisions,
preserved semantic/mechanical requirements, legacy behavior, CLI pins/exclusive outputs and V2
candidate integration with the training launcher. That integration still refuses an empty
reservation before any dispatch. Full suite: **2,039 passed, one optional Nautilus skip**
(90.18 seconds); Ruff lint/format pass. The core suite includes the existing JavaScript bridge.

The curriculum source change alters training implementation hashes: prepare fresh source-pinned
launches when ready. Prior tiny CPU native-smoke results remain historical under their recorded
source hash; optimization/save/reload methods were unchanged and no new native run is claimed.
Frozen suite/proposal/reservation artifacts are preserved, as are the manual workbench and old
pending records. Current documentation now reflects the completed AI review. Work is local and
uncommitted; no unrelated changes were staged or published.

Next: genuinely independent protected evaluation with reliable metadata/target provenance, then
one bounded Qwen CUDA adapter trial. No protected labels or custodian approvals were invented.
Real-market learning separately requires eligible causal order-book/CVD/microstructure sessions;
the failed public capture remains quarantined. Execution remains paper-only.

## Offline operator target-review workbench (2026-09-24)

Preserved the accumulated dirty/untracked worktree. Baseline: **1,985 passed, one optional-Nautilus
skip** (87.92 s). Actual Qwen fitting is still gated by human target decisions and a genuine
protected evaluation reservation. Added a self-contained offline review page to make the first
of those steps practical without editing a large JSON artifact by hand.

`training/review_workbench.py` binds the frozen suite and proposal by raw file hashes, rebuilds
the existing review/fact bindings and mechanically checks every proposed target before generating
an exclusive, fsynced, at-most-1-MiB HTML file. Only the 14 curriculum cases are included, with
their full model-visible evidence, numeric assessment, original draft, proposed answer/citations,
agent note and source/prompt pins. No development or protected evaluation payloads were added.

Every human decision starts pending, all four case attestations start null, notes start blank,
and reviewer identity/time/confirmation are unset. Agent findings are presented separately and
cannot populate human approvals. Operators can approve or reject each case, save an unconfirmed
draft, resume matching operator review JSON and explicitly download a confirmed review. Resume
refuses binding/target/case/type drift and agent attestations; identity/final confirmation reset.
Any case edit clears final confirmation, as does browser initialization/history-form restoration.

Kept review completion separate from candidate eligibility: operators may complete and attest
an all-rejected review without being forced to approve examples. Final review export requires
resolved decisions/reasons and four positive confirmations for each approval. The separate Python
audit still requires approved support/veto coverage before candidate export, and always denies
training/execution authority. No candidate, model or trading action is produced by the page.

The UI is self-contained, uses no external libraries/fonts/network/storage/server, escapes JSON
HTML delimiters and renders evidence with textContent. Hash-based CSP permits the bundled source
only and denies connections/resources/form actions. These controls do not authenticate identity,
prove prose semantics or make a modified local HTML file trustworthy. Download success is not
assumed merely because the browser was asked to save a Blob. Independent pinned Python auditing
remains mandatory before any candidate workflow.

Attempted a read-only browser preview using the computer-use workflow. The browser tool blocked
the local-file URL by security policy. No alternate browser, local server, raw browser commands
or policy workaround was attempted. **Visual layout, real-browser CSP and download behavior are
not verified**. Instead, tested the generator and pure state/DOM-event fixtures offline; the
operator must inspect the actual page. No real case was approved through automation.

Added **19 Python regression cases** and **38 JavaScript tests**, using Node v24.19.0. They cover
reset/blank approvals, drift, invalid target proposals, injection escaping, CSP hashes, file limits,
exclusive output, typed resume, rejected-only reviews, identity/confirmation controls, synthetic
DOM events and JavaScript-export/Python-audit roundtrips. Synthetic approvals exist only in tests,
never as real saved reviews. The Python bridge runs the JS suite when Node is available; it skips
on Python-only systems. Full suite: **2,004 passed, one optional-Nautilus skip** (91.15 s). All
38 JS tests pass independently; Ruff lint/format and tracked whitespace checks pass.

Added the three HTML/CSS/JS files as package resources and verified their bytes in the final
locally built wheel. No packages were downloaded or installed; existing runtimes were preserved.

- Ready workbench: `logs/qwen_operator_workbench_v1_20260924.html`, 68,005 bytes, raw SHA256
  `106de7abfeb390f5bedd787a65a1b2cc3c85ea1c0be4596a7ee0e50ef3a7ab55`.
- Final packaging check: `logs/review_workbench_package_verified_20260924/ai_trader-0.1.0-py3-none-any.whl`,
  raw SHA256 `d2e6e224c9a576add1ce0c9c10aa33f6ca90140ef16ef8192673c151f65d5cfa`.

Earlier development HTML/wheel outputs remain preserved and superseded. The final generated page
was independently checked to contain exactly 14 pending decisions, empty notes/checks and no
operator confirmation. Frozen suite, agent-review proposal and empty protected-reservation pins
remain unchanged. The previously tested native LoRA implementation hash and training-runtime
metadata also remain unchanged. No Qwen/model calls, training, market capture, paper/live orders,
new holdout labels or operator attestations occurred. Work remains local/uncommitted.

See [QWEN_REVIEW_WORKBENCH.md](docs/QWEN_REVIEW_WORKBENCH.md). Next human step: inspect the local
page, decide each case and return the downloaded review JSON for independent audit. Protected
evaluation still needs genuinely independent data; it cannot be manufactured by calling the
visible development cases a holdout. Eligible causal order-book/CVD data remains necessary for
actual-market model learning, separately from this synthetic language-review curriculum.

## Isolated training environment and native tiny LoRA validation (2026-09-24)

Preserved the accumulated dirty/untracked worktree. Baseline: **1,943 passed, one optional-Nautilus
skip** (101.57 s). Created `.venv-qwen-train` with Python 3.12.10 and no system site packages;
neither core nor inference environment was modified. Added a self-contained Windows CPython 3.12
39-wheel training lock, preserving existing compatible pins and adding PEFT 0.21.0 and Accelerate
1.15.0. Official metadata/dependency resolution, hash-enforced offline installation, all 39
installation-report version/hash comparisons and `pip check` passed. The local project was installed
editable without dependency resolution or build isolation; pip/project are outside the wheel lock.

Recovered the exact 1,993,738,732-byte official CUDA Torch wheel from existing pip cache after
verifying SHA256 `c7883d0c3426136dce06aabbb7f6924c15ffa0aa79e2d2a3d9bdcd84bbccd54c`. Other existing
wheels were cached too; only PEFT/Accelerate were newly downloaded. Provisioning used official
public package sources without credentials; native worker execution remained offline/local.
See [QWEN_NATIVE_LORA_SMOKE.md](docs/QWEN_NATIVE_LORA_SMOKE.md) for reproduction and trust limits.

Added an explicit, supervised native smoke command and private tiny CPU backend. They bind the
dependency lock, selected source files and interpreter, verify installed versions before native
imports and use the existing credential-scrubbed/offline pipe transport with a 120-second deadline.
No checkpoint, model ID, tokenizer, dataset, device or adjustable step budget is accepted. One
randomly initialized Qwen3-shaped model has only 13,424 base parameters and 896 rank-8 q/v adapter
parameters. A fixed 16-token synthetic example exercises completion/EOS-only masking and exactly
three AdamW steps through the actual production backend step/state/probe/save/reload methods.
Production Qwen size/checkpoint/CUDA gates are unchanged; this is not a fallback or trading path.

The first native smoke failed its CPU-only invariant after the first optimizer call, with no
completed step recorded. The failed directory remains quarantined with unknown completed count.
A supervised forward/backward-only diagnostic passed; a separate bounded one-step diagnostic
identified CUDA initialization despite CPU tensors. Inspection of installed Torch showed Adam's
accelerator graph-capture health check requests the current accelerator stream. Fixed the tiny
worker by hiding GPU devices before native imports and added a regression assertion at backend
initialization. No Qwen model/market data was used by these diagnostics; no automatic retries.

One fresh corrected smoke passed in **5.125 s**: three finite loss/gradient pairs, observed adapter
updates, exact frozen-base equality/no gradients, no CUDA initialization, adapter-only safetensors
and a fresh-base inference-only reload. Adapter tensors matched exactly; reload probe losses were
both 4.171200275421143. The adapter tensor file is 4,120 bytes (10,402 bytes including config/README).
This proves a tiny CPU API/numerical path, not Qwen CUDA memory feasibility, learned review quality,
trading edge or readiness for continuous training. The tiny adapter is never eligible for Qwen use.

Added **42 regression tests** for strict opt-in, fixed synthetic masks, lazy native imports, lock/
source/runtime pins, exclusive outputs, durable step intent, CPU visibility, malformed/false-authority
results, file tampering, reload failure, deadlines/interruption and no retry. These protocol tests
use fakes; native evidence is the separately recorded run. Focused smoke/backend tests: **53 passed**.
Full suite: **1,985 passed, one optional-Nautilus skip** (89.52 s). Ruff lint/format and tracked
whitespace checks pass. The new environment, wheelhouse and generated run artifacts are Git-ignored.

Important raw SHA256 bindings:

- Training lock: `8aedce7455c963753e0c8c5339e8abea7cc74ea0bddfb4c93390d4530d43af57`.
- `logs/qwen_training_install_20260924.json`:
  `d7377d90bfe46ea6163f57257f720441201187f603e0a9485bc8b3f58b860ad8`.
- `logs/qwen_training_runtime_versions_20260924.json`:
  `4840c478f76734ca6a9a5eec678a6dfbc314772a3a53a1e278b78f7e80e7a6bb`.
- `logs/tiny_native_lora_cpu_20260924_fixed/run.json`:
  `03b43e40e666f7e2ce5fd5e85d2e9030663c79dec8f84216f2fca4c413954f7d`.

Rechecked the unchanged Qwen checkpoint byte manifest, earlier inference runtime metadata, frozen
suite, agent review proposal and empty protected-reservation template. No Qwen weights were loaded
for inference/fitting, no market capture or order was attempted, and no targets/holdout/approvals
were invented. Next: resolve operator target decisions and reserve independent protected evaluation
before a bounded CUDA Qwen LoRA resource trial. Actual-market model learning still needs eligible
causal order-book/CVD/microstructure sessions. Changes remain local/uncommitted; nothing was staged,
pushed or removed from the existing worktree.

## Bounded LoRA worker and adapter persistence contracts (2026-09-24)

Preserved the pre-existing dirty worktree. Baseline: **1,878 passed, 1 optional-Nautilus skip**
(81.68 s). Added the supervised launch module, private training worker and optional PEFT backend.
Preparation reconstructs the operator-reviewed candidate and requires complete declared protected
metadata. It binds six input files, checkpoint/tokenizer pins, fixed recipe, new output directory,
interpreter/runtime and selected implementation source files. Dependency locks must be bounded,
self-contained, hash-qualified version pins; the child compares every declared installed version.
These checks do not authenticate operators, verify installed package-file hashes or establish
native compatibility. The worker never opens held-out payloads or labels.

Actual launch requires explicit opt-in and a new output directory. The supervisor uses the existing
bounded-pipe, scrubbed/offline single-child transport with a 600-second deadline and no retries.
The inner fixed 20-step loop fsyncs intent before each optimizer call and completion afterward.
The optional CUDA BF16 backend restricts trainability and AdamW to default q_proj/v_proj LoRA A/B
parameters, rejects non-finite loss/gradients and requires an observed adapter update. It saves
adapter-only safetensors, releases the old CUDA model/optimizer, reloads a fresh pinned Base plus
adapter, compares state exactly and verifies a training-example loss probe within 0.00001. Base
and adapter disk hashes are rechecked; the parent validates result fields/pins and saved manifest.
No adapter merging, Base overwrite, checkpoint resume, held-out evaluation or model promotion.
Failures retain partial artifacts with unknown final step count, rather than claiming no update.

Consulted official PEFT configuration/save/load/state documentation for the optional backend API.
Added **65 regression tests** using synthetic approvals, fake transports and fake model libraries.
They cover input/source/runtime/recipe drift, locks/opt-in, fixed step ordering and durable intents,
deadline/overflow/interruption, non-finite metrics, adapter-only parameter constraints, exclusive
outputs, reload mismatch and parent result validation. They do not verify native gradients,
PEFT/Transformers interoperability, GPU memory feasibility or actual adapter training. Focused:
**65 passed**. Full suite: **1,943 passed, 1 optional-Nautilus skip** (86.71 s). Ruff lint/format
and tracked whitespace checks pass.

Captured installed-version metadata only in the existing Qwen environment. Python is 3.12.10;
Torch 2.14.0+cu132 and Transformers 5.17.0 are present, but PEFT and Accelerate are absent.
`logs/qwen_lora_runtime_versions_20260924.json`, raw SHA256
`0c022b6a42f6d9470543f9c54aa51bd0377c0bdaef44088668d2d44f3dd8a638`, was verified to fail the launch
dependency gate before native imports. No real launch, runtime approval or training output was
created. The suite, agent target-review proposal and pending protected-registry byte pins remain
unchanged. No package/model downloads, GPU/model calls, captures, fitting, paper/live orders or
promotion occurred; development consulted public API docs, while application runtime stays local.

See [QWEN_LORA_WORKER.md](docs/QWEN_LORA_WORKER.md) for the launch contract and limits. Next:
provision/test a separate pinned training environment and a tiny native adapter save/reload check,
then a bounded Qwen trial only after target sign-off and actual protected reservation. The draft
v1 tokenizer-preflight record is preserved; the new worker has its own launch contract. Changes
remain local/uncommitted, with unrelated accumulated work neither staged nor overwritten.

## Protected metadata boundary and measured training-tokenizer preflight (2026-09-24)

Preserved the accumulated dirty worktree. Baseline: **1,808 passed, 1 optional-Nautilus skip**
(80.97 s). Added `training/advisory_holdout.py`: an exposure inventory of all 25 declared cases,
an empty pending reservation template and a metadata-only overlap audit. IDs, families, source
sessions, input hashes and normalized evidence fingerprints must be disjoint from every exposed
case, including rejected/visible development examples. Duplicate protected IDs/inputs/content and
cross-family sessions fail closed. No held-out payload/target/path field is accepted or opened.
Custodian attestations remain unverified local claims, not proof of independent data or semantic
deduplication. No genuine final holdout was fabricated or registered.

Extracted the evaluator's existing normalized fingerprint helper without changing its behavior,
and shared the exact historical Base completion-prompt builder with inference. Added
`training/advisory_training_plan.py`: static draft recipe/readiness reports, proposal checks even
for pending reviews, optional pinned local CPU tokenizer loading and unshifted completion-only
loss-mask records. Prompt/padding labels are -100; reply and appended EOS remain supervised even
when EOS equals padding. The token protocol separately encodes prompt/reply to preserve the
inference prefix. Empty/oversized/embedded-special sequences are refused, never truncated. Reports
store hashes/counts, not exported tensors or target text. The proposed 20-step/600-second LoRA
recipe is not an optimization worker, measured VRAM budget or authority to train.

Added **70 regression cases**. Focused review/worker/preflight regression: **171 passed**. Final
complete suite: **1,878 passed, 1 optional-Nautilus skip** (82.44 s). Ruff lint/format and tracked
whitespace checks pass. Coverage includes all exposure partitions, normalized relabeling, strict
metadata shape/pins, whole-session boundaries, missing/agent attestations, EOS/pad masking, exact
token limits, pending/rejected/invalid proposals, separate prompt/completion encoding, byte-pinned
local tokenizer loading and exclusive CLI artifacts.

Ran one CPU-only tokenizer preflight on the 14 already-proposed curriculum replies using the
installed 7,031,645-byte tokenizer JSON, SHA256
`c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539`. All fit: prompts **707-818**
tokens, replies **56-72**, supervised tokens including EOS **57-73**. A separate local-files-only
comparison against the installed inference AutoTokenizer matched all 28 prompt/reply encodings
exactly; EOS is 151643. No model weights, generation, GPU work or optimizer were invoked. Exact
offline rescoring reproduced both original V1/V2 scores after helper extraction. Frozen case,
prompt and proposal-review bytes remain unchanged.

The saved report still blocks fitting on incomplete curriculum review, incomplete protected
reservation, absent optimization worker and unverified training environment. New artifacts/pins
and limitations are in [QWEN_TRAINING_PREFLIGHT.md](docs/QWEN_TRAINING_PREFLIGHT.md). Next: build
and test the bounded optimization/save-reload worker and isolated training setup, while completing
target sign-off and real evaluation reservation. No packages/downloads, captures, fitting, paper/
live orders or promotion occurred. The failed capture remains quarantined. Work remains local/
uncommitted; unrelated changes were not staged or overwritten.

## Pinned curriculum review, target proposals and candidate gates (2026-09-24)

Preserved the pre-existing dirty worktree. Baseline: **1,744 passed, 1 optional-Nautilus skip**
(79.06 s). Added `training/advisory_curriculum.py`: pending template preparation, review audit,
operator-gated candidate export and independent candidate reconstruction. Reviews bind the exact
suite, packet, prompt/check version and original case inputs/targets/facts. Coverage is exact;
development cases, duplicate/missing rows and changed bindings fail closed. Candidate export
requires complete decisions, mechanical checks, semantic attestations, notes, both verdict classes
and an explicit operator identity/time attestation. An agent review cannot stand in for the latter.
Rejected cases remain accounted for; no case is silently dropped. Candidate input/target fields
stay separate from labels and review metadata. Even valid candidates cannot authorize training,
model promotion or execution. Hashes/local attestations do not authenticate a human or grade prose.

Performed an agent semantic review of all 14 curriculum cases and saved separate proposed targets,
expanded citations and case-specific notes. The g002_c original incorrectly specifies 'cost stress'
without an evidenced stress mechanism; the proposal states +5-bps baseline net and -1-bps stressed
net without inventing that mechanism. Other revisions make arithmetic, missing estimates and proxy
uncertainty explicit without changing verdicts. All 14 proposed responses pass schema/verdict/
required-citation checks. Prose/checklist judgments are agent attestations, not operator approval.
Every case decision is still pending and the saved audit blocks candidate export. No real candidate
or operator sign-off was created. Frozen references, suite/prompt versions and model scores remain
unchanged. See [QWEN_CURRICULUM_APPROVAL.md](docs/QWEN_CURRICULUM_APPROVAL.md) for findings and pins.

Added **64 regression cases** covering default denial, exact bindings/coverage, strict typed
attestations, agent/operator separation, target schema/citations/verdicts, rejected/pending cases,
both-class coverage, numeric/refusal conflicts, revised targets without original mutation, no
target leakage in model inputs, tampered candidate reconstruction, byte budgets and pinned CLI
lifecycle with exclusive writes. Synthetic approval records are test fixtures only. Final full
suite: **1,808 passed, 1 optional-Nautilus skip** (80.75 s). Ruff lint and formatting pass.

Read-only inspection confirms the local Qwen environment remains inference-only: Torch and
Transformers distributions are present; PEFT, Accelerate and bitsandbytes distributions are not.
No packages, weights or model runtimes were loaded/installed. No GPU inference, market capture,
training, paper/live orders or promotion occurred. The quarantined capture remains untouched.
Next: resolve target review, register protected final evaluation, implement/test a bounded adapter
training plan and isolated dependency recipe, then run a limited save/reload/evaluation trial.
Changes remain local/uncommitted; unrelated accumulated work was not staged or overwritten.

## Independent numeric checks and pending curriculum facts (2026-09-24)

Preserved the pre-existing dirty worktree. Baseline: **1,670 passed, 1 optional-Nautilus skip**
(78.38 s). Added `research/spot_long_checks.py`, version `spot_long_numeric_v1`: a model/label-free
checker for scoped, fresh BTCUSDT evidence and unique gross/cost/net/stress estimates. Missing,
duplicate, inconsistent or nonpositive net/stress estimates veto; costs must be nonnegative.
Optional kill/daily-loss flags veto if nonzero or duplicated. CVD/liquidity/replenishment proxies
cannot stand in for estimates. Unknown metrics still pass input preflight before being ignored.
Bounded decimal representation, timestamp and byte limits precede exact subtraction in an isolated
context; unsupported extremes are refused, not rounded. Facts retain supplied IDs/values separately
from computed net. Conditional support is a research-rubric result, not risk clearance or market edge.

Added `research/advisory_fact_audit.py` with two SHA-pinned, exclusive-output CLI modes. The numeric
sidecar preserves the complete existing score/raw replies; only schema-valid, input-bound model
verdicts are compared, without overriding them. Curriculum mode includes only 14 draft cases,
excludes 11 development cases, and separates inputs/facts/original targets. Every example remains
pending operator review and ineligible for training, even when its draft verdict agrees. No prose
semantic grader or approval/export mechanism is claimed. No change to model inputs, prompts,
weights, frozen cases/targets, production risk or paper execution.

Offline audits of both saved batches reproduced the exact SHA-pinned original scores. V1 has five
valid-model support conflicts and two conditional agreements. V2 has four veto agreements, three
invalid uncomparable replies and no valid-support conflicts; this is not a safety improvement or
promotion. Uninvoked curriculum/preflight cases remain separately uncomparable. Full model checks
are unchanged: V1 **2/7**, V2 **1/7**. The g006_a facts show **35 - 30 = +5 bps**, costs not greater
than gross, and a separate **-4-bps stress veto**. This neither edits the false explanation nor
automatically detects its prose error. All 25 numeric outcomes are five conditional supports,
16 vetoes and four preflight refusals; the 14 draft curriculum verdicts agree but are not approved.

Added **74 regression cases**, including context-independent exact arithmetic, numeric/time/scope
boundaries, missing/duplicate evidence, risk flags, non-authoritative proxies, label independence,
ungraded false prose, unchanged scores/raw replies, split isolation, pending review and pinned
non-overwriting CLI artifacts. Focused tests: **74 passed**. Final full suite: **1,744 passed,
1 optional-Nautilus skip** (79.36 s). Ruff lint and formatting pass; tracked
whitespace checks pass. See [SPOT_LONG_EVIDENCE_CHECKS.md](docs/SPOT_LONG_EVIDENCE_CHECKS.md) for
commands, exact sidecar/review-packet hashes, limitations and the next review/approval gate.

No inference, network capture, downloads, training, policy promotion or paper/live orders occurred.
The quarantined public capture remains untouched. Next: semantic curriculum review, versioned
approval and protected evaluation before any separate adapter-training resource trial. Changes
remain local/uncommitted; the wider pre-existing worktree was not staged or overwritten.

## Versioned Spot-long review contract and approved V2 comparison (2026-09-24)

Preserved the existing dirty worktree. Baseline: **1,637 passed, 1 optional-Nautilus skip**
(77.95 s). Added static `models/review_contracts.py` with the opt-in `spot_long_v2` hypothesis,
after-cost/stress rubric, abstention rules and conditional-support meaning. `legacy_v1` remains
the default, with its configuration selector omitted from the historical wire format so original
request bytes/hashes are preserved. V2 adds a fixed task, protocol identifier and explicit selector.
The worker reconstructs the contract and uses the selected prompt in both Base/chat paths.
Unknown/mixed/tampered contracts fail closed; the historical smoke stays V1-only.

Extended the runner/scorer with versioned input bindings and V2 response/score/run envelopes.
V2 recordings require the selected prompt hash; cross-version case rows cannot pass input checks.
Neither the case file, targets, references, budgets, weights nor production risk/runtime changed.
The new rubric is a fallible model instruction, not deterministic arithmetic or semantic validation.
Training export and promotion remain false. Offline checks reproduced the exact old V1 plan and
full score, and validated the original one-call smoke's request binding without new inference.

Before real inference, the complete suite passed: **1,670 passed, 1 optional-Nautilus skip**
(80.92 s), with Ruff lint/format checks passing. Added 33 regression cases across contract tests
and fake model-loading tests. Focused related regression: **221 passed**. V2 prompt SHA256:
`303e86702ea20f5f44de3920533a1f45466023211c44476f9ee353b79b15c7ea`.

The operator explicitly approved one V2 comparison on the same development cases: at most seven
local GPU calls, 120 seconds each, plus four input refusals; no downloads, training, trading or
retries. Prepared `logs/qwen_development_plan_v2_20260924_approval3.json`, raw-file SHA256
`fb70c7cdc5cdff25462bae00dc5c41cea004182fef6a82719ddc472f40a537cd`. Canonical plan digest:
`ebf7e9637aedf1ddca5edbfa11a5cee05eb2576875c5705146ebd3a480aa436f`.
Executed exactly one batch in **291.406 seconds**, with seven completed cold worker calls
(39.922–46.656 seconds each) and four correct deterministic input refusals. No retry or fallback.

V2 produced **4/7 valid reports**, four valid draft veto matches, but **only 1/7 full model
schema/verdict/citation passes**, compared with V1's 2/7. Balanced verdict accuracy fell from
0.5 to 0.4. Both positive controls were invalid outputs, not valid vetoes. Four preflight passes
are reported separately; including them gives 5/11 development machine-check passes, not success.
The remaining 14 curriculum cases were not invoked. Zero valid-report unsafe supports does not
mean the rejected output was safe: one invalid reply still returned unsupported support.

Failure inspection found a 1,213-character rationale (limit 512), a copied schema placeholder
followed by another object, and an appended critic report from one analyst call. All were retained
and rejected without repair. Three otherwise valid vetoes lacked required citations. One of those
also falsely claimed that 30 exceeded 35 and that the supplied +5-bps net estimate was −5.
The sole mechanical pass still described costs as relatively high without a comparison. These
are agent observations, not operator-approved semantic grades; the scorer leaves prose ungraded.
An interim commentary initially misattributed the second reply's veto to both early cases; it
was corrected immediately after reading the first raw response. Artifacts/scores were not altered.

V2 is not an overall improvement and is not promoted. Preserve both frozen experiments rather
than repeatedly tuning against these exposed cases. Next: deterministic evidence/arithmetic
checks and reviewed, fact-checked curriculum, keeping validator decisions distinct from raw model
outputs. Do not relax schemas, relabel failures, train on development cases or automatically start
LoRA. See [QWEN_REVIEW_CONTRACTS.md](docs/QWEN_REVIEW_CONTRACTS.md) for the comparison and exact pins.
Artifacts remain under ignored `logs/qwen_development_v2_20260924_approval3/`; response SHA256:
`384e8d199891d396e60d3e1ebceb3637f8c3da8984ccec042facf14bcf9a4f6d`.
No weights, prompt versions, validation rules or targets were changed after viewing the results.
No market-data capture, training, policy promotion or paper/live order occurred. All owned workers
exited and no model service remains. Changes remain local/uncommitted.

## Frozen-plan Qwen runner and approved development batch (2026-09-24)

Preserved the dirty worktree. Baseline: **1,589 passed, 1 optional-Nautilus skip** (76.34 s).
Added `research/advisory_runner.py` and 48 fake-transport tests. Preparation freezes the entire
development selection and its input/request hashes, prompt/checkpoint/interpreter and fixed
CUDA Base-model budgets without loading weights. Execution requires a pinned plan plus explicit
opt-in, claims a new output directory, fsyncs case intent before dispatch and retains bounded raw
replies/failures. At most seven cold analyst workers, 120 seconds and 256 generated tokens each;
four invalid-input cases require no worker. No retry, fallback, warm server or automatic resume.
Worker/protocol/deadline failures stop the batch; malformed report JSON remains available for
scoring. Persistence errors prevent further dispatch. Keyboard interruption retains partial
results. Hard termination/disk failure can leave only a partial event log, not a completed report.

Before any new real inference: **1,637 passed, 1 optional-Nautilus skip** (78.30 s); Ruff lint and
formatting pass (207 Python files), whitespace checks pass. The operator explicitly approved
one batch of up to seven GPU calls plus four preflight checks, with no training, downloads,
trading or retries. Prepared the unchanged v1 prompt/fixture plan at
`logs/qwen_development_plan_20260924_approval2.json`, raw-file SHA256
`54a52e45a1a235a37749e0bc20814258b251b6664a7cb1f09bd70ac1d5c65ec4`.
The plan's canonical JSON digest (without file newline) is
`c17d9dee4f10ebcb4d57b584b43dea3b982e0a80dab10e9a1c67167f9962e32e`.

Executed exactly that one batch using the previously pinned checkpoint and isolated `.venv-qwen`:
**276.406 seconds**, seven completed worker calls (37.453–40.781 seconds each), four correct
preflight refusals, no retries/failures/timeouts. All seven model reports were valid JSON and
returned `support`. Only the two conditional positive controls matched the draft verdicts:
**2/7 model verdict matches**, **0/5 expected vetoes**, **0.5 balanced verdict accuracy** and
6/7 required citation-group coverage. Development machine checks were 6/11 only because that
includes the four deterministic refusals; this is not a successful model evaluation. Fourteen
curriculum cases were deliberately not invoked, and no sealed final holdout was claimed.

Agent inspection of the raw replies found invented bearish/net-loss hypotheses, unsupported
claims that 14-bps costs were low, an uncalibrated score treated as strong confidence, and −4-bps
stressed expectancy described as resilience. Even a positive-control reply claimed downside
protection without supporting evidence. The scorer does not grade these prose semantics and
the targets still require operator review. The v1 prompt also underspecifies the task: it says
"existing hypothesis" without supplying one and omits the fixture's exact stressed-net rule.
Thus the tiny draft result does not isolate fine-tuning need or intrinsic model ability.

Raw plan, events, responses and scores are retained in the ignored directory
`logs/qwen_development_20260924_approval2/`. Raw-file response SHA256:
`98ad8f2cb7cdb67295b96599a9f078b166b5e8f40faebcfd87bf8d690b396ad3`.
Detailed case-by-case findings and reproducible commands are in
[QWEN_ADVISORY_EVALUATION.md](docs/QWEN_ADVISORY_EVALUATION.md). Next: preserve this baseline,
version an explicit Spot-long research question and cost/stress rubric with v1 replay compatibility,
then obtain a new bounded evaluation approval. Do not relabel failures, train on development
examples or launch fine-tuning from this result. No training, data capture, prompt/weight update,
paper/live order or promotion occurred. Both environments passed dependency checks unchanged.
All owned inference workers exited; no model service remains. A separate offline rescore reproduced
the split metrics and case rows exactly; it made no model calls. Final focused regression:
**101 passed** across evaluation/runner tests, with Ruff lint/format and whitespace checks still
passing. Changes remain local/uncommitted.

## Draft Qwen advisory curriculum and offline response scoring (2026-09-24)

Preserved the existing dirty worktree and ran the complete baseline before implementation:
**1,536 passed, 1 optional-Nautilus skip** (75.52 s). This slice used synthetic fixtures and the
already-recorded Qwen smoke only. It did not invoke Qwen again, load weights, download anything,
capture market data, train, change the model prompt, start a service or place orders.

Added `configs/qwen_review_cases_v1.json`: 25 agent-authored cases in 10 families, split into
14 `curriculum_draft` and 11 `development_eval` cases. Each family/session stays in one split;
exact normalized duplicate evidence is rejected even after renaming identifiers. This is not
semantic deduplication, chronological market data, an approved training set or a sealed holdout.
All targets require operator review. Cases cover insufficient edge from CVD/book imbalance,
costs/break-even/stress, conflicting flow, liquidity proxies, untrusted strings, risk flags,
conditional positive controls and deterministic input-boundary refusal. Labels/references/split
metadata stay outside the model-visible analyst payload. LF is explicitly preserved for the
raw-byte-pinned suite using a narrow Git attribute.

Added `research/advisory_evaluation.py`: bounded pinned-artifact loading, exact response schemas,
input/prompt/checkpoint bindings, strict role-report parsing, separate verdict/citation checks,
and full declared-case accounting. Missing/failed rows remain in verdict denominators. Both
constant-support and constant-veto controls score 0.5 balanced accuracy, not a full pass.
Rationale semantics remain explicitly unassessed even on a mechanical pass. Training export and
promotion are always false. The command never invokes a model and reports zero new model calls.
Outputs are exclusive; a completed score with failures/incomplete coverage returns exit 2.

The existing real-Qwen smoke artifact SHA256 is
`caa9f21c6c67c5e7e0a9d013e5dbd1aeeba2fbdba99c6d35e5acfcbbcd6d72dc`.
Offline rescoring reconstructed its original request/prompt and matched only case `g001_a`:
valid JSON/citations, observed `support` versus draft target `veto`, one unsupported support,
and **24 missing cases**. This is a retrospective regression authored after viewing that smoke,
not a completed independent Qwen benchmark. The separate authored-reference demo passed 25/25
mechanical checks; this is harness verification, not model-quality evidence. Reports are retained
under `logs/qwen_advisory_smoke_review_20260924.json` and
`logs/qwen_advisory_reference_demo_20260924.json`, both Git-ignored.

See [the advisory evaluation contract](docs/QWEN_ADVISORY_EVALUATION.md) for pins, commands,
limitations and next gates. Next is operator review and a separately approved bounded development
evaluation, before an isolated LoRA/QLoRA training-resource trial. The invalid public capture
remains quarantined; paper/live integration and training authorization are unchanged.

Verification: **53 focused tests pass**; the complete suite finishes with **1,589 passed,
1 optional-Nautilus skip** (77.05 s). Ruff lint, formatting (205 Python files) and tracked
whitespace checks pass. The original local work is preserved; changes remain uncommitted.

## Qwen3-4B-Base provisioned and measured on CUDA (2026-09-24)

After the operator reported successful Chrome access, ordinary terminal IPv4 HTTPS requests to
both official download hosts worked. Read-only proxy checks found no configured proxy to reuse.
This does not establish the earlier reset's root cause or prove an IPv6 problem. No security,
TLS verification, DNS, proxy or firewall setting was changed, and no browser automation or
credentials were needed. Continued the already approved isolated setup and single smoke test.

Pinned official `Qwen/Qwen3-4B-Base` revision
`906bfd4b4dc7f14ee4320094d8b41684abff8539` in `configs/qwen3_4b_base_source.json`. Downloaded
12 files (8,056,519,973 bytes including license/model card) into
`checkpoints/qwen3-4b-base-906bfd4b4dc7` in 116.06 seconds. Downloads had bounded bytes,
timeouts and HTTPS-only redirects; every file matched its pinned size and publisher LFS SHA256
or Git-blob metadata hash before publication from `.partial`. The production checkpoint
inspector validated all loadable files and architecture, yielding manifest SHA256
`8a1a0f20ba8a2c6d4480309f0f442114c4fa310018d143ee610061b1ecf47d3c`.
Weights remain Git-ignored. Exact hashes identify downloaded content, not independent publisher
attestation or proof of trading capability.

Installed the official Windows CUDA wheel into `.venv-qwen`: Torch 2.14.0+cu132, alongside
Transformers 5.17.0, tokenizers 0.23.2, safetensors 0.8.0 and psutil 7.2.2. The full 37-wheel
dependency closure is pinned with SHA256 in `requirements/qwen-inference-win-py312.txt`, using
the existing staging base layer. The CUDA wheel uses its exact official PyTorch URL; remaining
wheels use official PyPI. `pip check`, native Qwen-class import, CUDA/BF16 discovery and a tiny
BF16 matrix probe passed. The core environment and Python/system/security configuration were
not modified. No accelerator, PEFT or bitsandbytes training stack was installed.

Added `models/qwen_smoke.py`, an explicit one-call, synthetic-only GPU diagnostic using the
existing bounded process transport and actual local reviewer worker function. Optional Torch
and measurement imports stay in the child. Artifact creation is exclusive before dispatch;
no retries, repair, downloads, policy changes or orders occur. It preserves raw output and
separates generation completion from JSON/citation validity. Disabled library progress bars in
the worker environment so they do not consume bounded diagnostic pipes; limits were not relaxed.

Executed exactly one real-model analyst call: CUDA BF16, input ceiling 2,048 tokens, output
ceiling 256 tokens, deadline/reply lifetime 120 seconds. It completed in **40.281 seconds**
end-to-end (38.141 seconds after CUDA initialization for loading/inference/hashing). Peak
Torch-allocated VRAM was **8,245,496,320 bytes (7.68 GiB)**, reserved VRAM 8,308,916,224 bytes,
and Windows process working set 8,930,152,448 bytes (8.32 GiB). Allocator statistics do not
include all CUDA overhead or other applications; these are not fine-tuning memory measurements.
The worker exited normally and GPU memory was released. The bounded artifact is
`logs/qwen_base_smoke_20260924_approval1.json`, with raw response, hashes, configuration and metrics.

The response passed strict schema/citation validation but returned `support` for synthetic
positive CVD/imbalance plus 12-bps costs without any calibrated return or net expectancy.
Describing that cost as low and the environment as favorable is unsupported economic inference.
Record this as a content-quality warning and future abstention/cost-stress regression, **not**
a profitable signal, approved reasoning target or permission to trade. No training, market-data
capture, actual-market evaluation, paper/live order or promotion took place. Next work is a
reviewed content/abstention evaluation and curriculum, not automatically enabling the model.

Initial full suite this turn: **1,520 passed, 1 optional-Nautilus skip** (74.67 s). Added 16
synthetic smoke-harness tests; the focused harness/reviewer group passes 72 tests. Final full suite:
**1,536 passed, 1 optional-Nautilus skip** (82.61 s). Ruff lint/formatting and whitespace checks
pass, dependency checks pass, and model/environment/artifact paths are confirmed Git-ignored.
Core tests never load the installed model; its runtime metadata remains unchanged. All source
changes remain local/uncommitted. No download, model service or inference worker remains running.

## Approved Qwen setup: isolated staging ready, downloads blocked (2026-09-24)

The operator explicitly approved the isolated Qwen3-4B-Base installation and one bounded
synthetic inference smoke test. Checked the dirty worktree and preserved all existing changes.
Baseline regression: **1,520 passed, 1 optional-Nautilus skip** (75.74 s). Read-only capacity
check found 774,328,856,576 free bytes on C:, RTX 5080 Laptop / 16,303 MiB VRAM with 14,570 MiB
free, and driver 617.14. Free capacity is a point-in-time observation, not an inference guarantee.

Created `.venv-qwen`, added its ignore entry, and installed 30 exact-version/SHA256-pinned
official-PyPI wheel dependencies plus the local editable project. The reproducible staging list
is `requirements/qwen-staging-win-py312.txt`; it intentionally excludes CUDA Torch and is not a
complete inference-runtime lock. `pip check`, native tokenizer/safetensors imports and the
synthetic-veto subprocess demo pass. Observed Transformers 5.17.0, tokenizers 0.23.2,
safetensors 0.8.0 and numpy 2.5.0. No core `.venv` site path is inherited. Core metadata remains
Torch 2.14.0+cu132 with no Transformers/safetensors installation; it was not changed. The PyPI
CPU Torch candidate downloaded into pip's cache during resolution was not installed or used.

Local requests to Hugging Face reset during TLS setup using PowerShell, curl and Python.
The official PyTorch cu132 index request also fails with connection reset (Windows 10054).
Both hosts resolve in DNS and PyPI wheel downloads succeed. This does not locate the failure
within the local network, security software or upstream service; no cause is claimed proven.
The pip index's final no-matching-distribution message is a transport failure, not evidence
that the requested CUDA version does not exist. No security/TLS/proxy/DNS setting was weakened,
no credential was accessed and no unofficial mirror or alternate checkpoint was used.

Model metadata/revision and expected asset hashes remain unavailable, no Qwen weights were
downloaded, and no real-model inference, public capture, training or order took place. The
operator was asked whether the two official hosts open normally in the local browser. Resume
the approved setup after connectivity is restored, first completing the CUDA lock/probe and
model source/hash verification. Retained ignored pip reports:
`logs/qwen_runtime_resolution_20260924.json`, `logs/qwen_staging_resolution_20260924.json` and
`logs/qwen_staging_install_20260924.json`. The setup is incomplete, not successful Qwen deployment.
Final regression remains **1,520 passed, 1 optional-Nautilus skip** (76.93 s); Ruff lint,
formatting and whitespace checks pass. A core-parent to isolated-worker synthetic call also
passes with zero orders, confirming the process bridge without loading a model. All changes
remain local/uncommitted; no network service or inference process is left running.

## Local Qwen reviewer boundary and offline receipt diagnosis (2026-09-24)

Added `models/local_checkpoint.py`, `models/local_reviewer.py` and the private one-request
`models/_local_review_worker.py`. The existing research council now accepts this optional
Reviewer implementation without changing its default or connecting it to paper execution.
One explicitly enabled instance permits at most an analyst/critic sequence with the same
single-session causal snapshot and exact supporting prior. Inputs, generation, pipe outputs,
deadlines, reply lifetime and audit retention are bounded; malformed/late/unsupported output
fails closed, and the deterministic risk veto remains first. No retries, tools, network fallback,
policy mutation, sizing or order authority were introduced.

Local safetensors/config/tokenizer assets are bounded and hashed before and after model use,
against an independently caller-pinned manifest digest. Unknown loadable files, pickle/code,
custom tokenizer paths, unreviewed quantization and escaping shard indexes are rejected.
The lazy optional Transformers backend uses local-only loading without remote code, explicit
CPU FP32 or CUDA BF16, fixed greedy generation and separate Base versus post-trained prompting.
It is not an OS sandbox, process-tree manager, provenance authentication or hard RAM/VRAM quota.
The initial worker cold-loads each role; actual model latency/quality remains unmeasured.

Observed synthetic subprocess demo: a schema-valid `synthetic-veto` report, zero orders and no
promotion. Metadata-only preflight again found Python 3.12.10 and Torch 2.14.0+cu132; Transformers,
safetensors, accelerate, PEFT and bitsandbytes remain absent. Optional loading/generation tests
use fakes, not Qwen weights. No dependency installation, model download, real-weight inference,
fine-tuning, actual-market training, public capture retry or credentials/account operation occurred.
See [local Qwen reviewer](docs/LOCAL_QWEN_REVIEWER.md) for commands, limits and the next separately
approved isolated-runtime/checkpoint smoke-test gate. Model setup need not wait for profitability;
training and paper deployment still need their independent data/evidence gates.

Rechecked the exact retained partial from the prior entry against its SHA256, without modifying
or promoting it. Among 576 stream events, the largest receipt-timestamp gap is 2,053.7164 ms while
the adjacent exchange-event times advance 100 ms. Receipt-minus-event difference rises from
450.8375 to 2,404.5539 ms there. There are 112 distinct receipt timestamps; the largest identical
timestamp group contains 35 events. These observations suggest delayed delivery/processing but
do not distinguish network buffering, receiver scheduling stalls, timestamp resolution or clock
changes. The existing recording has no monotonic receipt/loop-lag instrumentation. All 85 events
over 2 seconds remain invalid; freshness limits were not relaxed and no smoke/training ran on it.

Verification: baseline **1,416 passed, 1 optional-Nautilus skip** (75.15 s); final **1,520 passed,
1 optional-Nautilus skip** (76.85 s). Added 104 synthetic tests across checkpoint, reviewer and
worker contracts, including actual subprocess deadlines/overflow/cleanup, stripped environment,
strict schemas/citations, source/sequence binding, checkpoint drift, no native eager imports,
dependency/CUDA failures and no cloud/stub fallback. Ruff lint and formatting pass.
Real-model compatibility, durable audit/memory, warm-worker throughput, resource quotas,
Qwen curriculum/adapter training and operational capture freshness remain unproven or incomplete.

## Approved single public capture and Qwen environment preflight (2026-09-24)

The operator approved one 30-second public BTCUSDT Spot capture (one attempt, existing 32 MiB
cap) followed by offline quality and zero-order checks. Ran the existing capture supervisor with
`data/raw/capture_audit_20260924_165918.jsonl`. The public connection worked, but receipt-causal
validation rejected the completed recording before final publication: event latency exceeded
the existing 2-second bound. The supervisor retained a quarantined partial and recorded failure.
There was no retry, account connection, credential access, order, training or relaxed safety guard.

Diagnostic-only inspection of that explicitly approved partial found 533,900 bytes, 579 physical
records, 281 aggTrade events and 295 depth events. Receipt-minus-exchange-event differences range
from 49.4879 ms to 2,404.5539 ms; 85 events exceed 2 seconds. The initial PowerShell diagnostic
parser rejected Binance's case-distinct e/E JSON fields; rerunning with case-sensitive hashtables
produced these counts. No conclusion is drawn from that failed initial parse. The receipt times
alone cannot identify network buffering versus process scheduling stalls or clock error. Windows
Time reported a successful synchronization immediately before the run; this does not establish
sub-100-ms clock accuracy throughout it. No clock/security setting was changed.

Retained `data/raw/btcusdt_4c93f88756bd4840877f30c9f80b7eef_attempt_1.jsonl.partial`, SHA256
`8a2958606b5807f89e97624bcb33b114ece3e19b6a60b906d0d834845941eb59`, and a local diagnostic summary at
`data/processed/capture_check_20260924_165918.json`. The partial is not a passing source and was
not renamed, fed to training, turned into features or passed to the paper-smoke command. Thus the
operational smoke gate remains incomplete, not passed. Existing/held-out datasets stayed unopened.

For the user's Qwen timing question, read-only hardware/runtime checks verified NVIDIA RTX 5080
Laptop GPU, 16,303 MiB reported VRAM, driver 617.14; project PyTorch 2.14.0+cu132 reports CUDA 13.2
and CUDA available. Transformers, Accelerate, PEFT, bitsandbytes and safetensors are not installed
in this project environment. No package, model or adapter was downloaded/installed, and no GPU
fit was run. This preflight does not verify Qwen inference, quantization or QLoRA compatibility.

The next local-model preparation task is an isolated dependency/checkpoint review and the bounded
non-executing reviewer interface, then an explicitly approved Qwen download and inference smoke
test. Synthetic Qwen integration can progress independently of the failed feed capture; useful
fine-tuning still needs validated, sufficient data and separate review. Preserve Qwen3-4B-Base
as the pretraining-stage fine-tuning candidate, distinct from post-trained Qwen3-4B, per the
[official Base model card](https://huggingface.co/Qwen/Qwen3-4B-Base). No silent model substitution.

Verification: the focused recorder/supervisor/paper-smoke/capture-quality suite passes **97 tests**
(8.23 s), and repository Ruff lint/format checks pass. No Python source was changed in this step;
the prior full-suite result remains 1,416 passed with one optional-Nautilus skip. Local diagnostics
and logs only; no commit/push. Investigate receive timing before seeking another bounded capture.

## Sealed model shadow and mechanical post-trade reviews (2026-09-24)

Added `research/event_shadow.py`: seal a completed single-baseline result against its independently
pinned hash, current registration/split/recipe and model schema. Sealing samples the current clock,
with no backdating argument; availability must follow registration and all research evidence,
including validation. A later source must begin strictly after model availability plus embargo,
match reconstruction/feature/outcome/cost settings, and not reuse IDs, byte hashes or time intervals
from any original research or reserved source. Future-dated seals/captures are refused. The seal is
an availability record, not tamper-proof authentication, a final-fit policy or paper promotion.

Explicit shadow replay reads one bounded capture once and shares the causal feature extractor and
eligibility checks without invoking labels or training. Inference receives feature-only input with
empty target/outcome/provenance arrays. Every frame and abstention is retained. Declared simulated
prediction latency and exclusive expiry are checked against input freshness. Later faults cannot
rewrite earlier predictions. Faulted/truncated runs remain incomplete, and every record has no order
authority. This single-baseline path does not select or deploy a walk-forward fold. It leaves paper
runtime behavior unchanged and imports no Torch/Transformers. Model decoding was factored into
shared private helpers without changing the existing baseline reload contract.

Added `research/post_trade.py`: a fixed mechanical rubric reviews every case without outcomes,
then joins verified paper lifecycles and closed-trade PnL. All abstentions, risk/order rejections,
unsubmitted entries, open positions and closed trades remain visible. Structural checks cover
policy/feature/risk bindings, evidence timing, plan expiry and approved sizing. Decision quality
stays UNKNOWN: neither a win nor a loss establishes thesis quality. Closed trades use the existing
typed PostTradeReview, and all lessons remain ANECDOTE. Open/unfilled outcomes and unimplemented
per-trade MAE/MFE stay null, not zero. Review availability is creation time, never the historical
trade time. This report is not automatic learning or approved decision memory.

The paper evaluator's consistent read-only snapshot was extracted into a shared internal helper.
Source/ledger verification, account reconstruction, sealed cases and review joins now stay inside
the same transaction; the original evaluator interface/result remains unchanged. Review publication
uses a new exclusive bounded artifact, not writes to the original journal. Reserved sources,
insufficient budgets, corruption and drift continue to fail closed.

Verification: initial full suite **1,355 passed, 1 optional-Nautilus skip** (56.69 s); after shadow,
**1,397 passed, 1 optional-Nautilus skip** (71.15 s); final **1,416 passed, 1 optional-Nautilus skip**
(74.62 s). Added 42 shadow and 19 review tests. Focused baseline/shadow group passes 92 tests;
review/evaluation group passes 55. Coverage includes metadata-only sealing, independent checksum
pins, no-label/no-fit inference, availability/expiry/freshness, future-outcome independence, source
reuse/protocol refusal, failed-prefix visibility, outcome/process separation, all-case retention,
read-only same-snapshot review, unknown inventory, resource bounds, drift and CLI status. Ruff lint
and formatting pass (192 Python files), as do CLI help, isolated no-Torch/Transformers import and
whitespace checks. Formatting fixes did not relax production gates.

See [model shadow](docs/EVENT_SHADOW.md) and [post-trade review](docs/POST_TRADE_REVIEW.md). All fits
and executions used synthetic temporary fixtures. Only real-data filename metadata was inspected:
the processed directory contains legacy feature artifacts, not current event-training results.
No actual dataset/reserved capture was read; no feed, credential, real-data fit, live order, model
installation or security-setting change occurred. Existing work remains local and uncommitted.

The requested autonomous continuation reaches the plan's separate real-data approval gate, not
project completion or usage exhaustion. Next requested operational authority: one 30-second public
BTCUSDT Spot capture, one attempt, existing 32 MiB cap, followed by offline quality and zero-order
paper smoke checks. This would not authorize training, live orders or an unattended service.
Point-in-time memory, final-fit policy, independent quality reviews, supervised operation and Qwen
remain outstanding work; no profitable strategy or finished bot is claimed.

## Registered expanding-session event evaluation (2026-09-24)

Added `training/event_walk_forward.py`: metadata-only registration of an entire expanding-prefix
schedule followed by explicitly activated offline evaluation. Each fold freshly fits the same
frozen NumPy recipe on earlier whole research sessions and predicts one later session exactly once.
An earlier evaluation session can join a later training prefix after the strict availability/embargo
boundary; reserved sources never enter training or evaluation. Existing fixed-split manifests,
legacy trainers, default runtime and trading permissions are unchanged.

The runner reproduces every research artifact from its registered capture bytes once, with the
64 MiB aggregate read budget and full-source accounting. It enforces source/row availability and
strict embargo at every later fold boundary. Quality failures block affected folds; fewer than two
training classes blocks fitting that fold. Every scheduled fold remains visible. Any blocked fold
makes the whole result incomplete and withholds pooled metrics, while retaining completed folds
as diagnostics. Integrity/provenance errors abort without publishing a final report.

Complete runs pool once-only out-of-sample probabilities and targets and recompute classification,
log loss, Brier and calibration diagnostics, not arithmetic means of fold scores. Training-majority,
Laplace-prior and uniform controls remain frozen to each fold's earlier data. Duplicate prediction
identities are rejected. Baseline configuration decoding and probability/scoring helpers are shared
with the single-fold trainer; no additional numerical framework or dependency is installed.

One checksum-protected report retains schedule, sources, per-fold models/fit/evaluation and status.
All calls require explicit training activation. Total repeated-prefix declared frame-epochs are
bounded at 2,000,000, not just the last fold's work; plans/results retain 1,000,000-byte/8 MiB caps.
There is no best-fold selection, final refit, standalone model promotion, trading threshold, PnL
claim or test-set evaluation. Overlapping event outcomes remain dependent research observations.

Verification: baseline **1,310 passed, 1 optional-Nautilus skip** (46.67 s); final full suite
**1,355 passed, 1 optional-Nautilus skip** (57.13 s). All 45 new tests pass, covering metadata-only
registration, fixed recipe/schedule, future-outcome independence, repeated fresh fitting, unequal-size
pooled arithmetic, failed-fold retention, strict internal embargo, aggregate compute/read/output
bounds, source scope, rehashed tampering, activation, availability, repeatability, drift and CLI
complete/incomplete status. The existing 50 baseline tests also pass after helper extraction.
Ruff lint and format checks pass for the whole repository (186 Python files); CLI help, isolated
import without Torch/Transformers and tracked/new-file whitespace checks pass. Overlong limitation
strings were split for Ruff; no production quality or risk threshold was relaxed.

See the [walk-forward guide](docs/EVENT_WALK_FORWARD.md). All fitting used synthetic temporary test
fixtures. No actual market/reserved dataset, feed, credential, live order, deployment or security
setting was accessed or changed. Work remains local and uncommitted; no push. Next: a separately
gated, receipt-causal model shadow adapter and actual-data readiness review before real fitting.

## Registered numerical event baseline (2026-09-24)

Added `training/train_event_baseline.py`: metadata-only baseline recipe registration and an explicit
opt-in NumPy research trainer using the source-verified event fold. The recipe binds registration,
split, code/environment, class/feature meaning, preprocessing, optimizer settings and controls.
Fixed-epoch fitting consumes training data only, without validation checkpoint selection or random
initialization. The existing train-only standardizer and classification metrics are reused; the
legacy Torch/candle trainer and default runtime are unchanged. No new dependency was installed.

Training medians handle missing feature values and 30 additional indicators preserve missingness.
The 60-channel matrix uses training population statistics, inactive constant channels and fixed
standardized clipping. All-missing training columns cannot become unexpected validation signals.
Targets/provenance never enter X. Float64 full-batch softmax gradient descent predicts the sign of
costed hypothetical Spot-long return, not a trading action. Exact breakeven may be absent; fewer
than two observed training classes blocks fitting rather than fabricating examples or labels.

Evaluation reports aggregate/per-session classification, log loss, multiclass Brier and ten-bin
calibration diagnostics against training-majority, Laplace training-prior and uniform controls.
Validation IDs/times/labels/probabilities remain separate evidence. These are dependent event-level
prediction diagnostics, not portfolio PnL, statistical significance or a profitable trading edge.
No calibration model, trade threshold, hyperparameter sweep, paper integration or promotion is added.

Every public training call requires explicit activation before input IO. Quality/class failures
publish blocked diagnostics without fitting; corrupt provenance/numerical errors abort publication.
Recipes enforce at most 1,000 epochs and 2,000,000 declared training-frame/epoch operations; existing
source limits remain. One exclusively published result contains data-only model parameters and
evidence, capped at 8 MiB. Reload requires a caller-pinned result hash and validates schema, shape,
finite parameters, positive scales and active-channel types; no pickle or executable model loading.

Verification: baseline **1,260 passed, 1 optional-Nautilus skip** (41.48 s); final full suite
**1,310 passed, 1 optional-Nautilus skip** (47.71 s). All 50 new tests pass; the combined event-data
and baseline group passes **161 tests**. Tests cover synthetic separability, a hand-calculated
gradient step, two/three-class fitting, median/missing/constant behavior, training-only statistics,
unchanged global RNG, fixed epochs, validation-outcome independence, inference without labels,
control/metric arithmetic, exact JSON reload predictions, tampering, limits, activation, failed
quality/classes, code drift, exclusive publication and both CLI modes. A fresh interpreter imports
the baseline without Torch or Transformers. Ruff lint/format, CLI help and whitespace checks pass.
An overlong test command literal was split for Ruff; no production threshold was relaxed.

See the [event baseline guide](docs/EVENT_BASELINE.md). Only synthetic fixtures were fitted, writing
temporary test results. No actual market/held-out dataset, public feed, account credential, live
connection, model deployment, dependency or security setting was accessed or changed. Qwen is not
installed or trained by this slice. Next: registered walk-forward event evaluation and a separately
gated receipt-causal model shadow adapter. Actual-data fitting still requires approved data and
meaningful predeclared quality/sample gates. Existing work remains local and uncommitted; no push.

## Source-verified event datasets and whole-session folds (2026-09-24)

Added `training/event_training_data.py`: metadata-only, write-once event split registration and
explicit-path source-reproduced loading. The first declared N research sessions are training, the
remaining research sessions are validation, and reserved sessions remain metadata-only. Every
research source must be supplied exactly once in registration order before market-file access.
The manifest freezes feature columns/units, label protocol, processing budgets, minimum resolved
count/fraction and strict nanosecond embargo at both partition boundaries. It is not a new test-set
evaluation interface, automatic model-selection procedure or proof of prospective preregistration.

Verification rejects malformed/duplicate/non-finite JSON, wrong identities/budgets, quarantined
partials and changed artifacts even when their checksums are recomputed. It rebuilds each entire
label artifact from registered capture bytes and compares exact canonical contents, including
numeric types and unknown outcomes. The label builder now shares its deterministic pinned-replay
derivation so captures are read once, not reopened during reproduction. Combined capture/label
reads are capped at 64 MiB; 2–32 research sources share at most 10,000 declared processing frames.
The existing exclusive staged publisher also supports manifest and verification-report envelopes.

Each source must be complete, market-fault-free and meet its declared resolved count and fraction.
All sources remain in the report; one failure blocks both partitions rather than dropping failed
sessions or selecting a passing subset. Available immutable feature matrices contain only resolved
rows, including losses, with targets and provenance separate; unknown feature values stay None.
Nothing fits a scaler, imputes values, balances classes, trains a model or accesses a trading journal.
Per-row maturity checks preserve feature order even when a later barrier outcome resolves earlier.
This uses strict session/cutoff invariants without incorrectly requiring monotonic outcome times.

Verification: baseline **1,195 passed, 1 optional-Nautilus skip** (34.30 s); final full suite
**1,260 passed, 1 optional-Nautilus skip** (41.30 s). All 65 new tests pass, covering metadata-only
registration, exclusive assignments, source reproduction, rehashed tampering, reserved/unknown/
omitted/reordered input refusal, embargo equality, variable outcome maturity, whole-fold quality
failure, actual byte accounting, single-read capture handling, immutability, repeatability, drift,
bounded inputs, publication and both CLI modes. Existing 46 label-builder tests remain passing.
Review fixed a returned manifest alias to the shared feature-unit map, with a regression test;
an unused test import was removed. Ruff lint/format, tracked/new-file whitespace checks and CLI
help pass. No production risk check or quality threshold was loosened to make tests pass.

See the [event training-data guide](docs/EVENT_TRAINING_DATA.md). Next: a bounded numerical baseline
with frozen training-only preprocessing, simple controls, reproducible artifacts and validation
metrics. Actual fitting still requires meaningful approved data/sample checks; engineering gate
success on tiny synthetic folds does not establish readiness, statistical independence or an edge.
Only synthetic fixtures and temporary files were used; no actual market/held-out dataset, feed,
model training, credential, live account, dependency or security setting was accessed or changed.
Default runtime is unchanged. Existing work remains local and uncommitted; no push.

## Receipt-causal microstructure event labels (2026-09-24)

Added `training/microstructure_data.py`: an explicit-path, one-registered-research-source dataset
builder with no journal access, fitting or execution. It retains every emitted replay frame,
selects ready unambiguous depth observations independently of strategy signal/sizing gates, and
separates a versioned 30-field causal feature allowlist/units from future outcomes and provenance.
Reserved/unknown sources are rejected before capture access; source bytes/framing and frozen
registration/code/environment are verified. Negative CVD/imbalance examples are not selected away.

The fixed protocol uses a strictly later depth quote for hypothetical unit-long entry, an exclusive
TTL, feature-bid stop/target anchors, entry-relative hold horizon and an actual later bid exit.
Fees are counted once on each side; spread/slippage are embedded in entry/exit prices. Barrier hits
and after-cost direction are separate: hitting a target can still lose money. Session ends, market
faults, stale/interquote gaps and processing cutoffs censor incomplete windows, preserving any known
entry but leaving numeric targets null. Unknown and not-entered outcomes are not breakeven labels.

Source-local windows never cross a session or processing prefix. Whole-session fold construction
and training remain future work; overlapping hypothetical returns are not additive portfolio PnL
or an execution-realistic backtest. Feature values/hashes are invariant to changed future quotes.
The builder enforces frame/pending limits and checks publication size, with exclusive fsynced staging
and atomic no-replacement final publication. Incomplete prefixes and market faults return CLI status
2 with a diagnostic artifact, not a training-readiness claim. Existing partials/final outputs survive
retry and publication races without overwrite.

Verification: baseline **1,149 passed, 1 optional-Nautilus skip**; final full suite **1,195 passed,
1 optional-Nautilus skip** (35.30 s). All 46 new tests pass. Tests cover timing/barriers, exact modeled
breakeven, losing targets, unknown outcomes, cost arithmetic, signal-independent sampling, missing
evidence, future-feature isolation, source identity/protection, bounded iteration, Decimal-context
reproducibility, drift, staging failures/races, resource limits and CLI status. Review removed a
per-frame whole-capture recount; a regression test verifies the physical count is computed once.
Ruff lint, formatting and whitespace checks pass; CLI help works. No dependency/security change was
needed. Only synthetic captures and temporary files were used; no actual market capture/dataset,
paper journal, network feed, credentials or live-account connection was accessed or changed.

See the [event-label guide](docs/MICROSTRUCTURE_EVENT_LABELS.md) for commands, units, publication and
limitations. Next: a verified artifact loader and frozen whole-session training/validation manifest,
then a bounded numerical baseline after data-quality/sample gates. Supervised capture/smoke and
forward-runtime checks require separate operational validation. No model was trained or promoted;
the default runtime remains unchanged. Existing work remains local and uncommitted; no push.

## Registered multi-session offline paper continuity (2026-09-24)

Added `trading/microstructure_campaign.py` and `research/campaign_evaluation.py`, sharing the existing
single-session executor and read-only fixed valuation protocol. A campaign supplies all registered
research captures in their immutable chronological order, with one funded journal and no conversion
of earlier single-session accounts. Unknown/reserved, omitted, duplicate or reordered sources fail
before capture access. Hash/framing/time and aggregate byte checks precede paper writes. Input limits
are 2–32 sources, 64 MiB aggregate bytes and a 10,000-frame global prefix, not an unattended run.

Book/CVD/trade sequencing and feature warmup restart per capture; cash, inventory, cost basis,
realized PnL, equity peak, original protection plans and kill state remain continuous. Snapshot-only
quotes cannot execute. Existing positions can exit on the first fresh synchronized quote before
new entry warmup completes. Holding time includes disconnects; daily-loss baselines advance only
at UTC-day boundaries. Same-day loss/drawdown vetoes and kill state cannot be cleared by a new file.

Activation is required on every simulation call. Exact retries reuse original decisions and fills;
smaller campaign prefixes than already committed history are refused. Stored tick order must match
the declared prefix. Atomic failure rollback spans session boundaries but preserves prior committed
invocations. Combined evaluation remains read-only and does not reset initial cash, exposure or
sampled drawdown between sources. Unknown equity during disconnects remains unknown even after a
later flat close; the strict comparison gate does not silently discard these gaps.

Verification: baseline **1,106 passed, 1 optional-Nautilus skip**; final full suite **1,149 passed,
1 optional-Nautilus skip**. All 43 new campaign tests pass, alongside single-session regression tests.
Coverage includes two/three-session completion, carried-position stops and maximum hold, fresh CVD,
cash/peak/kill retention, UTC rollover, subsequent entry vetoes, source/byte budgets, changed
registration/tick identity, atomic cross-session crashes, repeat reads and both CLIs. Fixture fixes
distinguished aggregate-trade `a` IDs from depth ask arrays and set a synthetic adverse quote far
enough to trigger pre-exit drawdown rather than stop loss. No production risk rule was loosened.
Ruff lint/format and whitespace checks pass.

See [multi-session campaign guide](docs/MICROSTRUCTURE_CAMPAIGN.md) for commands, report scope and
remaining limits. This verifies recorded offline transitions, not network reconnection performance,
L2 execution realism or a supervised forward service. Only synthetic captures and temporary journals
were used; no actual dataset, public feed, market-data training job, credential, live connectivity,
dependency/security setting or runtime default changed. Existing work remains uncommitted; no push.

Next: separately authorized small public capture/zero-order smoke validation, receipt-causal event
labels with explicit source-session isolation/censoring, and supervised forward-runtime verification.

## Read-only cost-aware paper lifecycle evaluation (2026-09-24)

Added `research/paper_evaluation.py` to audit an existing registered microstructure paper journal
without policy execution, orders, forced liquidation or input mutations. It opens SQLite read-only
under one consistent snapshot, verifies the full committed tick/case/order/event scope against the
registered capture and quote-cost model, and reconstructs account state using the durable ledger.
Unknown/reserved sessions are refused before capture access. A budget cannot select an earlier
subset of a journal to hide later losses; incomplete simulated captures are explicitly truncated.

The fixed, fingerprinted protocol samples bid-valued equity before and after each tick's orders,
reports net PnL/return, realized/unrealized amounts, actual fees/embedded slippage, turnover, time
in position and sampled drawdown. Costs already embedded in fills/cash are not subtracted twice.
Open inventory with an unhealthy quote has unknown value, not a forwarded last price. A separate
hypothetical terminal exit-cost scenario never books a fill or changes realized trade statistics.
Only closed lots enter the win fraction; rejected orders and open lots remain separate.

The holding-cash control uses the same initial funding without interest/trades. Excess-return
comparison is exposed only for fully consumed, fault-free, flat-ended runs with a fully valued
sampled path. Missing comparison values must not be used to silently discard failed/incomplete
experiments. No profitable edge, statistical significance, training readiness or promotion is claimed.
One-capture scope, quote-only full fills, sampling gaps and unbenchmarked reconstruction remain limits.

Verification: baseline **1,070 passed, 1 optional-Nautilus skip**; final complete suite **1,106 passed,
1 optional-Nautilus skip**. All 36 new tests pass: hand-calculated cost/PnL checks, stops/gaps,
pre/post-fill peaks, a closed loss followed by an open lot, truncation/unknown footer marks,
rejected orders, SQLite read-only enforcement, stable fingerprints, protected-source rejection,
corrupt tick/request bindings, fixed protocol, numerical context and CLI status. A first test
compared equivalent Decimal zero strings; it was corrected to compare numerical amounts.
Ruff lint/format pass. No risk checks were loosened.

See [paper lifecycle evaluation](docs/PAPER_EVALUATION.md) for commands, fields and limitations.
Only synthetic captures and temporary journals were used. No actual dataset, feed, training job,
model, credential, live connection, dependency/security setting or runtime default changed.
Existing work remains preserved and uncommitted; no push performed.

Next: separately authorized public capture/zero-order smoke validation, supervised multi-session
continuity, and receipt-causal event-label datasets with session-isolated splits before training.

## Explicit offline microstructure paper simulation (2026-09-24)

Connected the registered bid-replenishment/absorption, CVD, OFI and liquidity hypothesis to the
durable paper controller through a trusted synchronous case-builder seam. Context is captured
after quote marks and protective exits, before entries. Fresh paper cases use actual ledger cash,
inventory, daily realized PnL, peak equity, unresolved orders and kill state; prior research cases
and the registration's research-only authority are unchanged. The gateway independently vetoes
unsafe orders even if a generated case is approved. Entry policy is skipped on protection ticks.

The adapter requires explicit offline-simulation activation on every invocation, including resume.
It rejects unknown/reserved sources before capture access, pins code/environment/configuration and
capture identity, never resets an existing account/kill state, and deduplicates exact retries
without reassessing history using later balances. Changed frame evidence fails closed. The bounded
prefix invocation is atomic; failures roll back only newly simulated outcomes, preserving earlier
committed prefixes. First-call failures can leave metadata-only journals for diagnosis.

Reports separate requested-prefix counts/order IDs from latest committed ledger balances. Footer
inventory stays open; gapped/stale feeds block unsafe fills. Immediate quote fills are not an L2
backtester, forward paper service, strategy promotion or profitability result. One source per run,
a 10,000-frame absolute prefix cap, reconstruction performance and explicit terminal valuation
remain limitations. See [offline microstructure paper simulation](docs/MICROSTRUCTURE_PAPER.md).

Verification: baseline **1,022 passed, 1 optional-Nautilus skip**; final full suite **1,070 passed,
1 optional-Nautilus skip**. The 48 new synthetic tests cover fee/slippage/PnL arithmetic, protective
exits, actual account/risk state, restart/deduplication, gateway veto, source conflicts, CLI fault
reporting and callback/transaction failures. A new test initially expected the wrong kill-switch
reason label; its assertion was corrected to the existing `risk_rejected:` contract. No risk
threshold or check was loosened. Ruff lint/format and whitespace checks pass.

Only synthetic captures and temporary journals were used. No real capture, reserved dataset,
market-data training job, model, dependency/security change, execution default, credentials or live
connectivity was introduced. Existing work was preserved; no commit or push performed.

Next: separately authorized small public capture/zero-order smoke validation and a frozen,
cost-aware lifecycle evaluation report with explicit truncation/open-inventory handling and
controls. Then supervised multi-session continuity and event-label datasets before model training.

## Registered microstructure policy-to-case baseline (2026-09-24)

Added a pure research-only bid-replenishment/absorption hypothesis requiring positive rolling CVD,
best-level OFI, book imbalance and bid-side liquidity, with opposing ask absorption as a veto.
All thresholds are explicit, uncalibrated declarations; `abstain` is an alternative no-trade control.
Warmup, stale/gapped streams, incomplete coverage and ambiguous trade attribution produce no-action
records. Malformed evidence fails closed. Planned size includes entry fees, spread, both-side
slippage and modeled stop loss; existing hard-risk/cash/projected-drawdown checks retain rejected
proposals rather than silently resizing them. These stop-loss estimates are not fill guarantees.

Added exclusive registration of source-session/hash/time/role declarations, feature/policy/risk/cost
configuration, hypothetical cash, source code and environment fingerprints. Unknown/reserved sessions
are refused before capture loading. Chronological research/reserved declarations cannot overlap or
alias the same bytes. This remains local reproducibility metadata, not trusted preregistration or
a global holdout lockbox. No protected datasets were opened.

The bounded offline evaluator stores every emitted frame's case in the existing research journal,
including abstentions and rejections, with registration/source-bound identity, explicit exact prefix
resume and atomic failure rollback. No journal schema changed. It assumes a fixed flat hypothetical
account each frame: proposal counts are not executed trades, PnL, backtest results or promotion.
All cases remain `research_only`; paper journals refuse them, including risk-approved proposals.

Verification: 99 new synthetic tests pass; final full suite **1,022 passed, 1 optional-Nautilus skip**.
Ruff lint/format pass. Baseline was 923 passed, one skip. No dependencies, security
policy, actual datasets, training jobs, feeds, execution defaults or live-account connectivity changed.
Prior work was preserved; no commit or push performed.

See [registered microstructure policy](docs/MICROSTRUCTURE_POLICY.md) for units, commands and limits.
Next: separately authorized capture/smoke validation and a bounded strategy-to-paper adapter with
ledger-derived risk, exits-first sequencing and explicit activation. No profitable strategy claimed.

## Bounded capture supervision and offline paper smoke (2026-09-24)

Hardened the existing combined collector with bounded application/library buffers, immediate
application receipt timestamps, explicit overflow/idle/disconnect failure, snapshot byte/chunk
deadlines, recording quotas and awaited receiver shutdown. Exclusive `.partial` files remain
quarantined on failure; only receipt-causally validated sessions publish through no-overwrite
hard links. Oversized protocol messages and disk/quota failures do not trigger automatic retries.
OS DNS/disk stalls and an in-progress HTTP worker are not hard real-time bounded.

Added an opt-in finite retry supervisor with a fresh snapshot/session per attempt and exclusively
created, flushed audit records. Added an offline, explicitly selected/hash-pinned paper smoke CLI:
dedicated flat-start journal, active kill switch, no candidate cases, no order history, atomic
invocation rollback and explicit idempotent prefix resume. Reports distinguish faults, full
consumption and incomplete budgets; they do not measure strategy quality or profitability.

Verification: 73 new synthetic tests; final complete suite **923 passed, 1 optional-Nautilus skip**.
Ruff lint/format pass (159 Python files). The initial baseline had 731 passing tests and ten
Windows/PyTorch collection errors. Both final full runs loaded PyTorch successfully without this
task changing the environment/security policy; the cause is unknown. This does not verify the
separate Nautilus environment. No real capture, reserved-dataset access, market-data training job,
credentials, live trading, dependency installation or automatic strategy promotion occurred.

Commands, limits and recovery semantics: [capture supervision and smoke workflow](docs/CAPTURE_SUPERVISION_AND_SMOKE.md).
Next: explicitly authorized small capture/smoke validation and a registered deterministic
microstructure policy-to-case adapter. No unattended campaign was started.

## 2025-01-01 through 2025-01-14 BTCUSDT Spot study

This is a validation-only linear-baseline experiment over 14 UTC source sessions containing 20,160
verified one-minute candles. January 13 and January 14 were reserved and were not used by model
fitting, model selection, or reported metrics.

Label assumptions:

- next-candle-open long entry;
- 10 bps taker fee and 2 bps slippage per side (24 bps estimated round trip);
- 20 bps net take profit, 40 bps net stop loss, and 5 bps time-exit neutral band;
- ambiguous same-candle profit/stop touches resolved as stop first.

Validation configuration:

- five initial training sessions and seven expanding validation folds;
- two final held-out sessions;
- linear classifier, maximum 150 epochs, patience 20, class-weight power 0.5;
- Spot-compatible policy: long/flat only, minimum direction probability 0.55, margin 0.10.

| Horizon | Validation rows | Balanced accuracy | Macro F1 | Long signals | Coverage | Long precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 minute | 9,653 | 0.5420 | 0.4068 | 12 | 0.12% | 8.33% |
| 5 minutes | 9,625 | 0.4923 | 0.4088 | 275 | 2.86% | 20.73% |
| 15 minutes | 9,555 | 0.4633 | 0.4079 | 692 | 7.24% | 26.30% |

Decision: reject all three candidates. The 15-minute target is the best of this comparison for Spot
long-signal coverage and precision, but its fold results are unstable and its precision is too low
for autonomous paper promotion. The unevaluated held-out sessions remain available for a frozen
candidate, but two days are not sufficient as a durable final test.

Next evidence should cover substantially more regimes, reserve a larger final block, and evaluate
net PnL, drawdown, and turnover in addition to label precision. These results must not be presented
as evidence of a profitable strategy.

## 2025-01-01 through 2025-03-01 BTCUSDT Spot study

This follow-up expanded the same 15-minute candidate to 60 UTC source sessions and 86,400 verified
one-minute candles. The first 20 sessions seeded training, the next 30 sessions were evaluated by
expanding walk-forward folds, and the final 10 sessions (February 20 through March 1) were excluded
from fitting, selection, and reported metrics.

The labeling, linear-model, and Spot decision thresholds remained consistent with the earlier
study. Economic simulation allocated 10% of current balance per trade, allowed one long position at
a time, and used the already cost-adjusted label return. Signals arriving during an open trade were
skipped. Drawdown is measured at closed-trade equity points because candle data cannot reconstruct
the exact intrabar equity path.

| Metric | Result |
| --- | ---: |
| Validation rows | 40,950 |
| Balanced accuracy | 0.4052 |
| Macro F1 | 0.3988 |
| Long signals | 764 |
| Non-overlapping trades | 370 |
| Winning / losing trades | 97 / 273 |
| Starting / ending balance | $10,000.00 / $9,168.75 |
| Net PnL | -$831.25 (-8.31%) |
| Maximum closed-trade drawdown | 8.33% |
| Turnover | 70.93x starting capital |
| Exposure | 3.17% |
| Profit factor | 0.179 |

Decision: reject the 15-minute candidate. Expanding the evidence made the economic failure clearer,
so the final 10 sessions must not be spent evaluating this rejected configuration. The next research
iteration should change the setup economics or feature hypothesis using training/validation evidence
and retain the final block for a genuinely frozen successor.

### Lower-turnover policy comparison

Three fixed policy variants were compared on the same 30 validation sessions. This is exploratory
model-selection evidence, not a new independent test. All variants used 10% position allocation;
the final 10 sessions remained excluded.

| Policy | Trades | Net PnL | Drawdown | Turnover |
| --- | ---: | ---: | ---: | ---: |
| Original probability 0.55 / margin 0.10 | 370 | -$831.25 (-8.31%) | 8.33% | 70.93x |
| Probability 0.65 / margin 0.15 | 209 | -$475.97 (-4.76%) | 4.78% | 40.80x |
| Stricter policy plus 30-minute re-entry delay | 32 | -$80.38 (-0.80%) | 0.82% | 6.38x |
| Delayed, maximum 3 trades/day, $10 session targets | 24 | -$48.58 (-0.49%) | 0.51% | 4.79x |

Decision: reject every filter variant. The controls successfully bound activity and loss, but they
do not convert the underlying negative expectancy into a profitable strategy. Further threshold
tuning on these same sessions would increase selection bias. The next candidate must change the
label/feature hypothesis, beginning with causal volatility-scaled barriers.

## 2026-09-19 independent methodology audit

The [strategy research reset](STRATEGY_RESEARCH_PLAN.md) supersedes the previous immediate next
step. No new historical strategy trial or final-block evaluation was run during this audit.

Corrections to interpreting the studies above:

- Each reported walk-forward session also selected its model's best epoch. These are exploratory,
  validation-selected results, not independent forward estimates. Rejected candidates remain
  rejected; no corrected profitability claim is available yet.
- Stop fills ignore adverse opening gaps. A synthetic fixture returned a 99.84 exit on a candle
  with a 99.10 high. Economic reports inherit this labeling limitation.
- Per-session dollar controls reset capital, whereas aggregate PnL compounds capital. Future
  trade PnL is recognized at selection time; the rejection-reason ledger is not causal.
- The February 20-March 1 block was excluded from fitting, selection and reported performance,
  but its labels were parsed and contributed to aggregate dataset counts. Earlier wording must
  not be read as a claim of zero access. January 13-14 was subsequently reused as training data
  and is no longer an independent holdout.

Implementation priority: nested chronological fit/tune/evaluate partitions, gap-aware execution
and continuous capital accounting, then a preregistered trend-pullback experiment. Qwen adaptation
remains conditional on trustworthy evaluation and a demonstrated improvement over simpler models.
This commit records the audit and plan only; the identified implementation issues remain open.

### Follow-up: separate fitting, checkpoint tuning and evaluation

The walk-forward evaluator now reserves a configurable past-only tuning block. Fitting expands
over older sessions; early stopping and best-epoch selection use only tuning sessions; the next
session supplies evaluation metrics. Schema 2 reports distinguish tuning from evaluation while
retaining legacy `validation` field names for evaluation metrics. The CLI minimum-training count
excludes tuning sessions, so 15 fit + 5 tune preserves a 20-session initial prefix.

Synthetic regressions check that changing evaluation labels cannot alter that fold's model or
predictions, and that later-session changes cannot alter earlier results. No historical dataset,
final-block performance or new strategy was evaluated. Offline/paper-only behavior is unchanged.

Next session: enforce chronological timestamps and label boundaries, exclude lockbox outcomes
before parsing, and finish provenance manifests. Then fix gap fills and continuous portfolio
accounting before any strategy comparison. Existing economic results remain unsuitable for
promotion; this checkpoint addresses selection leakage only.

## 2026-09-20 TradingAgents architecture review

Reviewed upstream commit `2d17df8da1536c121e4d7395ac5a5dcec9e96d6f`; see
[findings and adoption plan](TRADINGAGENTS_REVIEW.md). Local keyless model inference is supported
upstream, but its default data vendors are online. Its reflection is prompt memory, not model
training, and its recommendation backtest is not our cash-and-fills economic simulation.

Implemented a small independent offline research council with typed timestamped evidence,
bounded structured analyst/critic reports, provenance citations, input fingerprints and existing
hard-risk vetoes. The included cost-stress reviewer is deterministic, not an LLM. No broker
integration, live connection, credentials, cloud calls, model download or dependency additions.

Synthetic tests and a demonstration exercise the safety contract. No historical strategy trial,
held-out dataset evaluation, Qwen inference or performance improvement is claimed. Existing
timestamp/split and simulator repairs remain prerequisites for economic comparisons.

### Execution-mode foundation

Added explicit `paper`, `spot_testnet` and `spot_live` startup configuration and a common Spot
request/receipt interface. The working paper adapter wraps existing risk/fill/accounting code,
rejects short intentions and insufficient cash, serializes duplicate submissions, and preserves
kill-switch flattening. Receipt states accommodate future asynchronous exchange outcomes.

Testnet and live modes fail before any connection, credentials lookup or paper fallback. No live
adapter or real-money arming is implemented. Deduplication remains process-local and mode
namespaces are preparation for persistence, not durable ledgers. See [details](EXECUTION_MODES.md).
Local agents can consume online public Binance data; offline is not a bot-wide networking ban.
Paper outcomes can feed versioned training, but no profitability gate automatically enables live.

### Walk-forward timestamp boundaries and reserved-data loading

Schema 3 adds a metadata-first loader. Session names, row counts and first/last feature timestamps
are inventoried before choosing the research/held-out boundary. Only research rows reach feature,
target and economic-outcome conversion. A poisoned-holdout regression verifies that malformed
reserved features/labels do not reach the trainer, including through `run_walk_forward`.

Research outcomes must follow their features and end strictly before the next session's first
feature timestamp, including the first held-out session. `--embargo-ms` adds a configurable gap.
Crossing rows are rejected, not purged silently. Every outcome is checked, so an early entry with
a late exit cannot evade the boundary check; valid nonmonotonic exits are accepted. Entry timestamps
for economic rows must follow features and increase strictly. Feature times may tie within one
session but sessions must be strictly ordered and nonoverlapping.

Reports retain the input SHA-256, metadata inventory, configuration and boundary policy. Changes
between loading passes abort before fitting. Depth-label datasets containing future timestamps but
no entry/return columns are accepted again; those timestamps no longer imply incomplete economics.

Limitations: the combined CSV is still read/tokenized, held-out session metadata is inspected and
the raw file is hashed. This is value-conversion exclusion, not zero-byte access or a physically
sealed lockbox. Input timestamps are trusted provenance, not proof that upstream features were
causal. Historical holdout exposure remains recorded. No real historical dataset was loaded or
evaluated during this change; only synthetic fixtures were used. Next: gap fills and capital ledger.

## Gap-aware kline labels

Kline labeling version 2 checks each candle's opening price before its high/low. Opening at or
beyond a stop/target exits at that open and records the open timestamp, with distinct `gap_stop`
and `gap_target` counts. Unknown intrabar ordering remains conservative stop-first, timestamped
at bar close. A prior exit cannot be replaced by a later gap. This models idealized market-triggered
barriers and fixed-bps costs, not limit-order execution or guaranteed slippage. An adverse gap can
lose more than the configured stop amount.

The common CSV row schema remains 1 for splitter compatibility; `labeling_version=2` identifies
the changed semantics. The kline manifest is schema 2 and records fill/timing policies. Legacy
datasets are unchanged and must be regenerated into a new directory before using the new rules;
do not mix old and new labels in an experiment.

Verification: baseline 278 tests passed; completed suite 288 passed, with Ruff lint and format
checks passing. Regression coverage includes adverse/favorable gaps, exact barrier opens, opening
precedence when both levels later touch, unchanged intrabar fills, prior-exit precedence, and
generated-dataset session splitting. Only synthetic fixtures were used; no historical datasets,
held-out sessions, training runs, or live-order connectivity were touched. Next: a causal execution
ledger with continuous capital accounting.

## Continuous settlement accounting

Walk-forward report schema 4 carries balance and last-exit cooldown state across evaluation
sessions. Session trade counts and PnL limits reset against the carried starting balance. An
accepted outcome remains pending until its exit; subsequent signals cannot use its future PnL.
Settlement runs before later decisions, including flat rows, and the final pending trade settles
at its exit. Inclusive holding intervals still prohibit entry at the exact exit millisecond.

An in-memory `SettledTrade` ledger records entry/exit times, entry notional, net return, PnL and
before/after balances. Summaries use these settlements instead of recompounding an independent
capital path. Aggregation rejects reset capital/cooldown state and overlapping session intervals.
The observation interval uses the maximum outcome exit, including unselected rows, and aggregate
duration includes elapsed gaps between sessions. JSON summaries identify these accounting rules;
they do not embed individual ledger records.

Verification: 299 tests pass, Ruff lint/format and diff checks pass. Fixtures cover future-PnL
rejection invariance, final settlement, same-timestamp exits, carried capital under profit/loss
limits, reset counters, cooldown through flat sessions, nonmonotonic exits, invalid session chains,
ledger reconciliation and two-fold walk-forward continuity. No real historical dataset, reserved
block or research training run was used; model fitting occurred only in synthetic unit tests.

This closes the capital-path inconsistency, not the full execution milestone. Inputs are still
precomputed outcome labels; turnover remains twice entry notional and drawdown is closed-trade
only. Next: independent candle replay, candle-close marked equity, simulated buy/sell turnover and
entry-latency stress scenarios. Execution remains paper-only and live adapters remain disabled.

## Independent candle execution replay

Added a separate `backtesting.candle_replay` API accepting raw candle sessions and ordered
completed-close long-signal timestamps. It does not read precomputed outcomes or call their
calculator. Signals enter at the next open plus an optional full-bar delay. Entry sizing reserves
fees inside the cash budget and rounds base quantity down; cash and cooldown carry across sessions.
Each session resets only its entry count and realized-PnL gate reference. Open positions liquidate
at the final close, and signals whose scheduled entry falls outside the session expire.

Stop/target reference geometry matches labeling v2: opening hits first, then conservative
intrabar stop-first ordering. Replay independently charges per-fill quote fees and adverse price
slippage, so costed returns are not forced to equal additive-bps labels. Stop losses remain subject
to gap/slippage risk. Marks value open positions at each candle close without a hypothetical exit
fee reserve. Reports include both marked-close and closed-trade drawdown, actual simulated buy/sell
notional turnover, exposure, fills, trade PnL, signal decisions, session balances and configuration.
Input-content hashes cover candles and supplied signals; new JSON reports refuse overwrites.

Verification: clean baseline of 299 tests; completed suite 338 tests, Ruff lint/format and diff
checks passing. Synthetic fixtures verify independent calculation, zero-cost label-reference
parity, hand-calculated fees/slippage/turnover, cash conservation, adverse gaps, ambiguous touches,
unrealized drawdown, entry delays, session liquidation, risk resets, carried cooldowns, future-suffix
invariance, invalid inputs and report persistence. No historical data, held-out block, live
connectivity or research training was used.

Scope: research API only, not yet used by walk-forward reports or promotion gates. Supplied
signals must be generated causally; timestamp checks cannot prove that. Intrabar equity, queues,
volume-dependent execution and exchange-specific filters remain unmodeled. Next connect frozen
walk-forward predictions to explicit research candle sessions and compare next-open/delayed replay,
without opening reserved sessions or claiming profitability from these engineering tests.

## Frozen-prediction walk-forward replay integration

Schema-5 walk-forward reports now save immutable per-fold probability tuples and their feature
timestamps, captured once before scoring. An opt-in raw candle manifest and explicit holding-bar
configuration enable independent next-open and one-full-bar-delayed replay. Both scenarios use
identical frozen probabilities and the same long/flat decision policy, with no scenario winner
selection, refitting or promotion. Legacy label economics remain separate. Replay capital/risk
settings must match the walk-forward economic configuration.

The verified archive loader filters by exact evaluation session names before opening or hashing
archive files, rejects missing selections before archive loading, and checks selected files and
manifest hashes across reads. Other archive dates/names remain visible in the manifest. This does
not change the combined labeled CSV's metadata-only holdout conversion policy or its physical
tokenization limitations. All replay prediction times, even flat decisions, must align to unique
candle closes; extra/reordered sessions and holdout overlap fail closed.

Reports embed both replay ledgers/marks/configurations, prediction-policy hashes and candle/signal
input hashes. Frozen predictions can be replayed through a standalone API without fitting again.
Schema-5 report writing refuses overwrites, and the CLI checks an existing output before fitting.
Policy serialization rejects a policy different from the one actually used.

Verification: clean baseline 338 tests; completed suite 359 tests, Ruff lint/format and diff checks
passing. Synthetic tests cover single prediction calls per fold, two-scenario shared inputs,
saved-prediction replay equivalence, continuous balances, invalid alignment/scope, poisoned held-out
CSV values and unopened non-evaluation archives, changed source files and overwrite protection.
No real historical experiment, reserved-block evaluation, live connectivity or model promotion ran.

Next: bind feature-generation provenance to the exact raw candle inputs, then freeze the research
protocol/cost stresses before a registered research-only trial. Timestamps and separate data hashes
do not alone establish feature derivation lineage. Execution realism limitations remain unchanged.

## Evaluation feature-to-candle consistency gate

Schema-6 replay-enabled walk-forward runs now recompute every evaluation feature before any model
fit. Verification uses the already selected/validated raw candle sessions, requires exact session
and candle-close timestamp alignment, and rejects missing in-session warmup. Each calculator call
receives exactly the 60 preceding bars plus the current completed bar: no future bars and no
cross-session warmup. Values are compared exactly after the existing generator's 12-significant-digit
serialization and float64 conversion. Mismatches are errors, not repairs or tolerated drift.

The report records verification scope/policy, feature names, warmup size, calculation-module hash,
and each evaluation session's row count, timestamp boundaries, raw-candle content hash and model
feature content hash. This binds tested numeric consistency to the actual inputs used by the run.
It is not historical authenticity proof or a record of the original generation process. Fit/tuning
features and outcome labels are not checked by this gate. Standalone frozen-prediction replay has
no feature matrix and does not gain this guarantee; non-replay walk-forward reports record null.

Verification: baseline 359 tests; completed suite 371 tests, Ruff lint/format and diff checks pass.
Synthetic tests cover exact agreement, one-float-step mismatches across different feature types,
changed warmup activity, insufficient warmup, invalid shape/schema/timestamps, finite inputs,
causal calculator windows, future-suffix independence and rejection before any fitting. Existing
poisoned holdout/unopened archive tests still pass. No actual historical or held-out data was used;
model fitting occurred only inside synthetic tests. Execution remains paper-only.

Next: verify the remaining research-session features and label-generation settings, then freeze
the protocol and cost scenarios before a registered research-only experiment. No profitability
or promotion inference follows from these consistency checks.

## All-research feature and label consistency

Schema-7 replay-enabled walk-forward runs extend pre-fit verification to every non-held-out
research session, including fit and tuning inputs. The raw archive allowlist now includes those
sessions, but still excludes held-out/unrelated archives; only evaluation candles enter replay.
Feature verification retains the same exact causal-window rules and records its expanded scope.

Selected CSV rows additionally retain immutable label evidence when replay verification is
requested. Held-out rows are skipped before evidence collection/conversion. Complete labeling-v2
columns are required, with one consistent declared horizon, neutral threshold, barriers, fees and
slippage across research rows. The checker regenerates outcomes using the existing label generator
and checks every non-feature output field: targets, prices, timestamps, durations, gross/net returns,
barrier outcomes, identity and configuration. Parsed training targets and economic outcomes must
also agree with that evidence. Labels whose full horizon exceeds a session fail closed.

Label provenance records declared settings, per-session label-evidence/candle hashes and the
calculation-module hash. Base label settings are separate from replay stress assumptions; neither
is silently rewritten. This establishes consistency with the current generator, not independent
algorithm correctness, historical authenticity, original-generation proof or economic edge.
Legacy/incomplete labels require explicit regeneration into new artifacts. Without replay enabled,
the existing loading path remains compatible and provenance fields remain null.

Verification: clean baseline 371 tests; completed suite 415 tests, Ruff lint/format and diff checks
pass. Synthetic tests cover changed features across fit/tune/evaluate roles, corrupt labels/costs/
identity/version across those roles, mixed declared settings, parsed-target/outcome disagreement,
invalid timing/nonfinite values, insufficient label horizon, deterministic evidence hashes and
poisoned held-out label metadata. All fail-before-fitting and reserved-archive exclusion tests pass.
No real historical dataset, held-out evaluation, live connection or promotion was used.

Next freeze the research protocol, data selection and cost/latency scenarios before a registered
research-only trial. Remaining realism/environment/physical-isolation limitations stay explicit.

## Fixed trend-pullback hypothesis and six-scenario paper replay

Implemented a research-only EMA20/EMA60 crossing hypothesis on completed five-minute candles.
EMA seeds use simple means; ATR14 seeds from true ranges at bars 1-14, then uses Wilder smoothing.
Indicators reset per session, gaps fail closed, and the six-bar slow-EMA slope delays earliest
eligibility to index 65. The 2-ATR target must cover three times the fixed 24-bps reference cost,
using signal-close price because the next entry is not yet known. ATR freezes at signal time.

Paper replay schema 2 adds explicit absolute signal-distance geometry, anchored at the entry
bar open before execution slippage. Existing label-reference behavior remains the default.
Distances must match all signals exactly; nonpositive entry stop prices reject without a fill.
An opt-in full-horizon rule rejects entries without the complete within-session holding window.
The trend study runs all six cost/delay scenarios with identical frozen signals, 24 holding bars,
10% fee-inclusive capital allocation, no leverage, and no scenario selection. Costs hold per-side
fees at 10 bps and stress per-side slippage to 2/8/14 bps. These are assumptions, not measured fees.

Verification: baseline 416 tests; completed suite 449 passed, including causal prefix invariance,
hand-calculated indicator seeds, gaps, cost-independent barriers, delayed-entry anchoring, complete
horizons, invalid evidence, and unchanged legacy replay checks. No historical returns or held-out
archives were inspected. No LLM training, live connectivity, or promotion was introduced.

Next: register immutable data/code/configuration provenance before loading a historical study.
Cash/buy-and-hold/random controls, uncertainty estimation, numerical evidence gates, and physical
lockbox separation remain prerequisites to any promotion decision. This API alone does not enforce
dataset selection or prevent callers from supplying reserved sessions.

## Metadata-only registration and registered study runner

Added write-once registration for the fixed five-minute BTCUSDT pullback rule. The record freezes
explicit chronological research/reserved lists, all excluded names, source-manifest bytes, declared
research archive hashes, all project Python source hashes, Python/dependency versions, and all six
cost/delay configurations. Reserved sessions must follow research sessions; duplicate/overlapping
or missing selections fail. Registration never opens normalized archives, including research ones.

The registered runner checks the record before candle loading, supplies only research names to
the existing verified archive loader, requires exact returned coverage, and rechecks provenance
after replay. It saves indicator/signal evidence and all six complete paper ledgers without winner
selection or promotion. Output paths are write-once. Failures after initial verification leave a
failure record; interrupted disk writes can still leave partial files. Users can create new paths
and registrations, so this is not a globally enforced trial counter or append-only trusted ledger.

Verification: 470 tests pass (416 baseline before this development batch), including metadata-only
registration with nonexistent research and poisoned reserved paths, drift/overwrite rejection,
exact loader allowlisting, all-scenario persistence, failure retention and mid-run registration
changes. No actual historical trial, reserved-data inspection, model training or promotion ran.

Next: add cash, declared allocation buy-and-hold, and seeded matched random-entry controls; quantify
session-level uncertainty and freeze numerical evidence gates. Only then run an explicitly selected
research trial. Physical lockbox isolation, cross-machine environment reproducibility, execution
volume/queue constraints, exchange filters and independent external timestamping remain open.

## Reproducibility review follow-up

A regression test changing the ambient Decimal rounding mode reproduced differing indicator
values despite fixed precision. Signal generation and the complete six-scenario study now use an
explicit 28-digit ROUND_HALF_EVEN context; registration records that arithmetic policy. Tests
compare entire studies under changed caller precision/rounding. Added rejection tests for invalid
distance-mode configuration and corrupt archive declarations. Final suite: 478 passing tests,
Ruff lint/format clean. Changes are local commits; no historical trial has been launched.

## Order-book-first direction and receipt-causal microstructure features

The maintainer clarified the primary strategy direction: order-book state, CVD, liquidity,
iceberg/replenishment evidence and absorption. The candle pullback study is now explicitly a
comparison baseline. MICROSTRUCTURE_PLAN.md governs the next implementation sequence.

Added a separate stateful microstructure engine and explicit-capture JSONL builder. Features
include session base/quote CVD, receipt-window buy/sell volume and CVD, observed liquidity bands,
top-N/band coverage, best-queue OFI and per-side exact-best-price replenishment/absorption proxies.
No hidden-order identity or size is claimed. Defaults use a ten-second rolling window, ten-bps
liquidity bands, one-second maximum attribution interval, 80% retained displayed depth and three
consecutive replenishment intervals. These are research settings, not validated trading thresholds.

The first applied depth establishes the evidence baseline. Event-time eligibility and receipt
availability are distinct: late trades affect current CVD but never revise previous attribution;
future-time trades wait in a bounded buffer. Gaps, malformed events, duplicate trade IDs, reverse
receipt times and buffer overflow invalidate the engine. Equal-time/long depth intervals suppress
attribution. Snapshot boundaries remain fixed; sparse updates cannot claim deeper complete coverage.
Best quotes outside known coverage require resynchronization. Decimal calculations use explicit
28-digit half-even arithmetic. New session instances reset CVD and all evidence state.

The builder validates the capture, binds unchanged input bytes and project source hashes, and
publishes only complete versioned output using no-overwrite hard-link creation. Temporary files
are cleaned on failure; racing existing destinations are preserved. A completed artifact requires
its end footer. Existing model schemas and CSV datasets remain unchanged. No account connection,
live order, historical strategy evaluation, LLM training or promotion was performed.

Verification: clean baseline 478 tests; 52 new synthetic tests cover signed/rolling CVD, precise
window endpoints, OFI quote changes, both-side evidence, depleted/add-only books, stale/late/future
events, prefix invariance, snapshot coverage, failures, immutable prior rows, arithmetic context,
source drift and exclusive artifact publication. Full suite: 530 passed. CPU-only suite: 529 passed,
one CUDA smoke test skipped. Ruff lint/format and diff checks passed. Next validate selected capture
quality, then preregister a microstructure event hypothesis
and build L2/trade execution evaluation rather than using candle fills as proof of microstructure
profitability.

## Explicit capture-to-paper replay bridge (2026-09-24)

Added `capture_replay.py` and schema-6 immutable source/config/code/candidate bindings. Bounded,
explicit-path bytes feed fresh book/microstructure engines and the paper controller in receipt order.
Pre-snapshot-availability messages may stitch depth but cannot produce features, warmup or CVD.
Depth/trade gaps, malformed market events and delay/skew violations invalidate the rest of the session.
New separately identified captures reset book/CVD/warmup while preserving paper holdings/risk; a fresh
synchronized quote can protect old positions before feature warmup permits new entries. No signal,
network reconnect service, derived-artifact rewrite or training task was added.

Verification: 40 new replay tests pass; 233 combined replay/controller/gateway/account tests pass.
Full attempt: 731 passed, one optional-Nautilus skip, ten unchanged PyTorch/Application Control
collection errors. Ruff lint/format and diff checks pass. Tests include a synthetic capture-to-CVD
entry/target round trip, snapshot buffers, sticky gap faults, reconnect protection, prefix invariance,
failure/restart deduplication, binding conflicts, corruption/budgets and migration. All captures and
databases are synthetic temporary fixtures. No real/reserved data access, public capture, external
orders, credentials, training or security-policy changes. Next harden ingestion supervision and an
explicit bounded operator workflow before unattended paper operation. Quote fills are not L2 execution
realism or strategy profitability evidence; native-library and training gates remain unresolved.

## Bounded paper controller and per-tick protection (2026-09-24)

Added `paper_runner.py`, receipt-time health contracts and schema-5 immutable tick/results. Each
tick commits quote health, risk marking, protective exits and an optional case-bound entry together.
Entries require ready causal microstructure evidence and an exact session/observation-bound approved
case; exits bypass entry feature/trade/spread gates. Fresh synchronized quotes can trigger daily-loss,
drawdown, stop, target and max-hold exits. Bad quotes defer execution and report exposed lots instead
of inventing a fill. Existing reserved exit inventory is never double-sold. Explicit bounded runs do
not fetch data, poll, sleep or start a service. No new signal strategy or model was introduced.

Verification: 45 new tests pass; 193 combined ledger/account/gateway/runner tests pass. Full attempt:
691 passed, one optional-Nautilus skip, ten unchanged PyTorch/Application Control collection errors.
Ruff lint/format and diff checks pass. Tests include causal warmup/coverage bridging, exact protective
boundaries, gap-stop prices, between-trade peak/restart protection, stale-feed recovery, concurrent
duplicate ticks and abrupt process exit before/after commit. No market download, external trading,
credentials, security-policy changes or training. Next: validated capture/replay adapter with end-to-end
gap, resynchronization, warmup and real receipt-time propagation tests. Quote-only execution remains
unvalidated for order-book strategy profitability; unattended operation is not yet enabled.

## Opt-in durable paper execution and risk checkpoints (2026-09-24)

Added `durable_paper_gateway.py` and schema-4 request/config/risk checkpoint tables, with explicit
v1/v2/v3 upgrade. The prepared-order API simulates one full quote fill or rejection atomically with
its risk checkpoint. No mutable broker balance or external order side effect exists. Exact retries
recover receipts; changed quote requests/configuration conflict. Pre-fill gates check cash including
fees, current risk, case expiry/config and quote freshness. Kill state, UTC realized-loss baseline
and bid-marked peak equity persist; reducing exits bypass entry gates. Uncheckpointed external ledger
events fail closed. The legacy gateway/default runner is unchanged; no live connection is introduced.

Verification: 38 new gateway tests, 148 combined persistence/account/gateway tests pass. Full attempt:
646 passed, one optional-Nautilus skip, ten unchanged PyTorch/Application Control collection errors.
Ruff lint/format and diff checks pass. Synthetic tests cover concurrent duplicates/cash claims,
daily/peak/kill recovery, configured slippage/fees, migration rollback, checkpoint-insert failure and
abrupt process exit before and after commit. No credentials, market feed, training, real trading,
native-policy bypass or dependency changes. This remains quote-only simulation, not a microstructure
execution proof. Next: a data-health-gated paper runner with continuous risk marks/protective exits.

## Paper exits and funded account reconstruction (2026-09-24)

Added schema-3 paper exit records tied to entry-specific filled BTC and immutable, opt-in flat-start
USDT funding. Account reconstruction calculates cash, position, remaining fee-inclusive cost,
realized net PnL, fees and exit reservations from one consistent event snapshot. Exits need no new
analyst verdict or unexpired entry case. Unknown/canceled exits retain inventory reservations until
explicit cancellation reconciliation; this prevents competing exits from double-selling BTC.
All checks and event inserts share a transaction. V1/v2 migrations preserve existing evidence and
order/fill bytes; no automatic funding or broker restoration occurs.

Verification: 33 account tests added; 110 focused journal/lifecycle/account tests pass. Coverage
includes partial/full closes, fees counted once, proportional cost residuals, concurrent exit claims,
snapshot consistency during a concurrent fill, overdraw rollback, populated migration rollback and
abrupt process interruption. Ruff lint/format and diff checks pass. Full regression attempt:
608 passed, one optional-Nautilus skip, ten unchanged Windows Application Control/PyTorch collection
errors. No external data, network, credentials, trades, training or native-policy changes. Next:
opt-in gateway integration, pre-fill buying-power/risk checks and durable risk-state recovery.

## Durable paper-entry orders and incremental fills (2026-09-24)

Added immutable paper-entry order/event contracts and schema-2 journal persistence. Each entry
binds to one exact, unexpired approved paper case and its quantity cap. Incremental fill IDs are
run-unique; retries do not double-count quantity/notional/fees. Transactional replay validation
rejects overfills and invalid transitions. UNKNOWN requires explicit reconciliation, not automatic
resubmission. Late fills after cancellation preserve the canceled remainder or complete the order.
Version-1 case/review access remains supported; explicit upgrade is atomic and separately tested.

Verification: 47 new lifecycle tests passed, 77 combined journal tests passed. Tests include concurrent
duplicate/overfill attempts, injected rollback, explicit migration failure, caller Decimal precision,
and abrupt child-process exit with committed fills and an uncommitted event. Ruff lint/format and
diff checks passed. Full suite attempt: 575 passed, one optional-Nautilus skip, ten unchanged
Windows/PyTorch collection errors. No native-policy bypass, network/data collection, credentials,
orders, training or new dependencies. Gateway behavior is unchanged. Entry records are not portfolio
recovery or exactly-once execution; next add risk-reducing exits/accounting before opt-in integration.

## Durable case/review journal (2026-09-24)

Added explicit-create/open SQLite storage with research/paper run identity, schema/application
checks, full-synchronous transactions, exact retry idempotency, conflicting-ID rejection and
append-only SQL triggers. Reads validate checksums and reconstruct typed immutable records.
Reviews bind to the exact stored pre-trade case; one trade ID cannot cross cases. Revisions use
new review IDs without overwriting earlier evidence. No order gateway or position ledger changed.

Verification: 30 new tests passed, including separate concurrent connections and abrupt child
process termination with an uncommitted transaction. Ruff lint/format passed. Full regression
attempt: 528 passed, one optional-Nautilus skip and the same ten Windows/PyTorch collection errors.
No new dependencies, credentials, native-policy changes, market capture, orders or training.
This is durable evidence storage, not restart-safe execution or point-in-time model memory.
Next: request/order/fill lifecycle contracts and opt-in paper reconciliation integration.

## Capture-quality audit and immutable case contracts (2026-09-24)

Added read-only, explicit-path capture/artifact quality assessment. Each feature observation must
reproduce from source bytes under the recorded configuration; header/footer/count, typed values,
source hashes and final input hashes are checked. Reports distinguish warmup, interval validity,
band/top-N coverage, unmatched/pending/trailing trades and current versus recorded code manifests.
These are whole-session QA metrics, not point-in-time trading features or profitability gates.

Added minimal immutable pre-trade evidence/plans/cases and post-trade review contracts, including
finite Decimal checks, expiry, no future evidence, no live mode, and explicit no-action semantics.
Recorded risk verdicts are not execution authorization. Outcome is separate from decision quality;
a single lesson remains anecdotal. A synthetic capture-to-observation-to-no-order rejection test
uses only the selected observation's causal warmup flag, not retrospective report information.

Verification: 62 new tests passed; Ruff lint/format passed. Full regression attempted with continued
collection: 498 passed, one optional native-engine skip, ten PyTorch collection errors due to
Windows Application Control. No security bypass, real dataset access, orders, training, new
dependencies or live activation. Durable journal/unique IDs, full fill lifecycle/metrics and
recorder recovery remain next work. See docs/QUALITY_AND_CASES.md for scope and commands.
