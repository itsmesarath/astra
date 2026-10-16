# Next gate: native decoded cursors and publication evidence

## Status

This is **prospective design only**. It was written while the complete feature-witness project suite was running. No adapter, reader, test, example or historical experiment is released here. No archive, stored feature row, packet or outcome was opened. Source inspection does not verify a real session.

The new constructed witness computes all 37 features from a complete invented target-record stream. Its target ordinal is not an original DBN member cursor. Its mandatory empty-book genesis, fixed date/contract and 256-record limit must not be transplanted onto historical input by relabeling or truncating it.

The next useful component would connect native decoded order records to the original publication cursor, while retaining the distinction between complete source identity and causal information available at that cursor. It needs its own closed contract, independent invented acceptance and later separately authorized historical registration. Schemas, counter origins, IDs, native runtime pins and capacity are **not locked** by this document.

## Source-backed distinctions

Root and a read-only specialist inspected the unchanged source; neither called a loader or builder. The relevant locations are:

- `databento_6e_receive_clock.py:120`: one metadata header precedes MBO messages; foreign instrument IDs return before target clock/timer/book processing.
- `databento_6e_training_data.py:273`: the daily metadata must match GLBX.MDP3/mbo, `6E.FUT`, exact UTC-day bounds and one active mapping for the dated outright. Hard-coded instrument ID 1 is not a substitute for this check.
- `databento_6e_receive_clock.py:131`: target daily bounds, snapshots, quality flags, closed-clear exceptions and clock audit precede ordinary book mutation. Target receive order is preserved, never sorted or corrected.
- `databento_6e_execution_flow.py:258`: protected non-snapshot target records are captured against the old book before the parent validates/applies them. A submitted order pre-state is not evidence.
- `databento_6e_event_scalp.py:45`: timers advance before an incoming target record, clamp at window end minus one and close the window when crossed. Foreign messages do not drive those target timers.
- `databento_6e_receive_clock.py:191`: pending T records become signed flow at the enclosing F_LAST receive time. An F record is not a second trade.
- `databento_6e_event_scalp.py:105`: the first due completed quote publishes, then sets the next publication time to its receive time plus one second. Following equal-time records must not alter that publication.
- `databento_6e_event_scalp.py:196` and `databento_6e_receive_clock.py:234`: native day completion checks incomplete events, complete decision coverage/cadence and target clock-audit counts.
- `databento_6e_training_data.py:290`: the existing member decoder checks complete Zstandard/DBN termination and the compressed-member hash after complete consumption. It yields decoded objects, not a source-byte-offset witness.

These are facts about the inspected implementation, not authenticated feed, exchange calendar or native decoder/runtime claims. The nine helper pins in the constructed witness do not cover the entire native loading/import graph.

## Keep the identities separate

| Identity | What it identifies | Not interchangeable with |
| --- | --- | --- |
| Header/mapping identity | Exact declared source day, schema, requested parent and dated target mapping | A fixed invented instrument ID |
| Decoded-object position | Original yielded order, with explicit header/type/foreign/target dispositions | Target ordinal or compressed byte offset |
| Target-record ordinal | Ordered target MBO transitions after mapping | Every decoded object in the member |
| Native event closure | Actual target F_LAST boundaries and full preceding native event records | A timestamp or a clipped capture range |
| Execution capture range | Original protected, non-snapshot records used by execution metrics | An automatically extended full native event |
| Quote/publication cursor | Exact completed quote and first due equal-time publication | Any later equal-time quote |
| Complete member identity | Bound source bytes and accepted decoder EOF | An early consumed-prefix hash alone |

A future contract must specify precisely whether each position includes the header, where numbering starts and how non-MBO records fail rather than merely disappear. This table does not lock those counters. Do not call a decoded ordinal a byte offset: the current loader does not expose a correspondence between its yielded objects and compressed/uncompressed byte positions.

## The original initialization and warmup boundary

The original engine starts the UTC day with an empty book, then consumes its native initialization path. Earlier target snapshots, resets and transitions establish the book used at warmup. The historical bridge must reconstruct that path or accept a separately verified complete checkpoint proof; it may not manufacture the constructed witness's pre-warmup R or adopt a caller-supplied order dictionary.

There is a second boundary to preserve. Original signed-flow buffering and original execution capture have different scopes. A native event can start before the protected warmup boundary and complete inside it. The flow buffer can carry preceding T records into completion, while execution capture includes only protected non-snapshot records. A proof must retain the full native event provenance **and** the exact original execution-capture disposition. Silently extending the execution helper's input to the whole earlier event changes its metrics; silently calling the captured suffix a complete native event also misstates the evidence. The future contract must resolve this with independently constructed boundary cases before any historical use.

Keep the original one-second cadence, strict five-second inactivity/expiry equality, actual prior quote gap, OFI/history reset order and execution stale-span semantics. Do not choose a longer wait, different warmup or new capture scope from known outcomes.

## Prospective acceptance and release gates

First validate complete declared roles, dates, member/source/schema identities, resource limits and mapping requirements before numerical traversal. A bad last declaration must refuse before earlier price access. Only a later explicit release may authorize opening an exact already-exposed train/development prefix; reserved price rows and outcomes remain out of scope.

That complete-fixture metadata-first gate is proposed **new bridge behavior**, not a description of the old streaming producer. The old target counter advances after successful book application and includes clears/snapshots; it is not an existing global decoded cursor. Extra unrelated mapping entries are not automatically invalid under the inspected dated-target mapping check.

Then independently construct mixed native-message fixtures. Require complete decoded dispositions, reconstructed target pre-state, every native event closure, original protected capture ranges and all original publications. Foreign messages may change complete native cursors and source identity, but must not mutate target book/flow/timers. Missing headers, duplicate headers and unexpected non-MBO messages must refuse under the original rules, not become silently ignored data.

For causal suffix checks, hold metadata/mapping/used-source identity and the consumed prefix constant. A changed later suffix must alter the complete input/member identity but not an earlier consumed publication. Future complete-member hashes must not be embedded in an early causal seed in a way that makes suffix invariance impossible. Final source acceptance may occur only after complete verified EOF; it must not retroactively make future records available to an earlier decision.

Whole-session capacity, decompressed/decoded bounds, runtime, durable fresh attempts and fail-closed complete verification need separately tested semantics. The current 256/128/32 component limits and the older metadata gate's 16/3/64 limits cannot fit arbitrary historical sessions. Exceeding them is a blocker, not permission to select a convenient interval, omit foreign records, thin publications, shard/reseed accounting or report a successful prefix.

No outcome or old selected trade is needed to prove feature derivation. If original feature rows contain outcomes in the same record, a future target-free projection needs a separately reviewed allowlist and source identity. Never manufacture default-zero CVD/depth/reload fields because only timestamp/bid/ask columns are available. Preserve the original row representation separately from the constructed witness's sole integer-zero travel-to-float adjustment; no old row or target is edited.

Passing a local native cursor proof would still not authenticate transport or validate a strategy. Complete policy recomputation, broker fills/fees/margin, EURUSD spot/CFD mapping, one-genesis funded multi-session continuity, untouched validation and model promotion remain separate gates. Every historical, account, execution, trading, training, scoring and promotion authority remains false here. BTC/cloud collectors and existing UNKNOWN liabilities are untouched.

## Twelve unexecuted invented cases

These are a prospective bridge matrix, not additions to the 541 passing witness cases and not a new implementation release.

| Case | Independent required observation |
| --- | --- |
| Header order | Missing/duplicate headers and unexpected non-MBO messages refuse; a complete-fixture metadata-first gate must be explicitly specified as new behavior. |
| Mapping identity | Exact daily metadata and one active end-exclusive dated-target mapping, with mapped ID other than 1; unrelated mapping entries are not automatically rejected. |
| Foreign interleaving | Decoded positions advance separately from contiguous target ordinals; every foreign disposition remains bound to the complete source. |
| Foreign poison/gap | Foreign timestamp/flag/price/F_LAST changes do not alter target clocks, timers, book, flow or publication. |
| Completion boundaries | Warmup quotes update helpers but do not publish; ordinary non-F_LAST records and reset records do not manufacture completed quotes. |
| Warmup-crossing event | A T before warmup completes inside it; independently retain full native event prefix and original protected execution-capture suffix without broadening metrics. |
| Foreign F_LAST | Cannot flush pending target trades or close an incomplete target event. |
| Equal-time suffix | The first due completion fixes the publication; later equal-time completions update helpers but cannot change it or immediately publish again. |
| Inactivity ordering | Five-second equality retains state; plus one nanosecond fires before an incoming non-final target record; foreign records do not fire target timers. |
| Invalid target | Protected bad clock/day/quality metadata refuses the whole result even if the old execution wrapper had already captured that record. |
| Reset/snapshot distinctions | Incomplete target events refuse reset/snapshot; selected-window snapshots/live clears refuse. An accepted outside-window reset may lack F_LAST and is a separate reset disposition, not an ordinary incomplete event. The selected-window snapshot-quote branch is unreachable for accepted input; exceptional closed-period clears remain separate. |
| Complete prefix identities | Independently rebuild decoded/target/event/publication links and mapping context; unchanged consumed context/prefix preserves earlier publication digests under a changed future suffix. |

The future contract still must lock header inclusion, numbering origins, rejected-item dispositions and which target transitions receive ordinals. Never force every reset through an ordinary F_LAST-only event closure to make this matrix simpler.

## Review and evidence limits

This document combines root source reads with separate read-only native-seam and acceptance-planning recommendations. A complete independent static document review, followed by review of the added twelve-case matrix and reset qualification, accepted these distinctions with no unresolved wording blocker. Proposed cases are not executed tests. Complete metadata/calendar/history/native runtime schemas remain unimplemented and unreleased. See `6E_FEATURE_PROVENANCE_WINDOW_20261010.md` for the actual constructed acceptance and owned full-suite process, and `6E_HISTORICAL_BRIDGE_NEXT_GATE_20261010.md` for the broader historical and continuity design.
