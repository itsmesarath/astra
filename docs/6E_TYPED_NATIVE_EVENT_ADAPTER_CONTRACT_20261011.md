# Proposed typed native-shaped event/publication adapter contract

## Status, objective and human gate

**PROPOSED SPECIFICATION — UNIMPLEMENTED; documentation only.** The direct user request is: “continue for 4 hrs.. work on the typed native/event adapter contract using the new skills. keep it offline and leave the accepted code unchanged”. Actual UTC was checked at **2026-10-11T14:41:15Z**. This contract window ends at **2026-10-11T18:41:15Z (19:41:15 Lisbon)**, replacing the preceding window's stop time without an automatic extension.

The objective is one bounded capability: independently reconstruct **invented typed target events and their 37-feature publications**, with complete foreign provenance, declared native-shaped context and the unchanged constructed payload/cursor layer. The consumer is a later independent test/review process, not a broker, model or historical loader. Success now means a source-grounded, statically reviewed specification presented for direct human approval. No behavior in this document has been implemented, collected or executed.

Actual decoding, compressed/original bytes, native EOF, historical access/capacity, strategy/account orchestration and multi-session continuity are separate capabilities and are deliberately excluded. Thus this single-capability specification does not silently bundle a native reader or historical bridge. If those are added, a separately human-approved capability map is required before their specifications.

The installed specification skill requires root to present this saved specification and **stop before implementation planning/tasks/code**. A heartbeat or static reviewer cannot approve it. Even human specification approval is not an implementation/native/history release in this documentation-only window. All **416 accepted Python source/test files**, approved older contracts, dirty/untracked work and old source/target/input/result/control pins remain unchanged; no staging or commits.

## Existing evidence, structure and dependency direction

The accepted [payload-binding contract](6E_PAYLOAD_BINDING_CONTRACT_20261011.md) and [cursor contract](6E_NATIVE_CURSOR_METADATA_CONTRACT_20261011.md) remain immutable. Their earlier prospective wording is chronology: current acceptance is recorded in [PROJECT_STATUS.md](../PROJECT_STATUS.md) and [the payload guide](6E_RECORD_PAYLOAD_BINDING.md). Latest accepted complete regression: **10,869 passed plus three expected skips**, all **10,872 case-sensitive identities**, accepted at **14:16:22 UTC**. No completed suite, verifier, example or exited process is rerun/rechecked for this specification.

The proposed later module/test paths are `src/ai_trader/research/six_e_typed_native_event_adapter.py` and `tests/test_six_e_typed_native_event_adapter.py`. Neither is created or released now. Existing `docs/6E_*` conventions are retained; no duplicate generic spec or replacement implementation plan is created.

Dependency direction is: unchanged public cursor/payload APIs -> new pure constructed reconstruction -> independently submitted verification. There is no dependency on the accepted fixed-instrument feature witness, funded/account driver or historical/native builders. The proposed module uses **stdlib plus unchanged public cursor/payload APIs only**. The numerical helpers below transitively import native/historical code, so importing them is not an acceptable native-free reuse shortcut. Their inspected, pinned rules are normative source references for a local explicitly specified reconstruction, not a release to call those builders or monkeypatch their native classes.

No reader, writer, CLI, decoder, native object constructor, archive, account, order, model, outcome/target, training, storage/resume or durable state hook is proposed. Pure repeated computation is not authenticated replay or account/order exactly-once behavior.

## Literal identity and constructed scope

Proposed version: `constructed_typed_native_event_adapter_v1`.
Scope: `invented_native_shaped_target_event_and_feature_publication_reconstruction_only`.
Status: `constructed_typed_native_event_adapter_not_native_verification`.

The old fixed invented **2025-04-07 / 6EM5** date/contract and complete daily header remain unchanged. A mapped ID other than 1 is retained; it is never relabeled. Date-valid examples are not authenticated exchange-calendar evidence. The adapter's one invented day is selected for numerical observation, with original UTC decision window **[12:00,16:00)** and ten-second warmup **[11:59:50,12:00)**. This is not a real complete historical session.

Constructed constants are fixed literals: nanoseconds per second 1,000,000,000; tick 50,000 raw units; decision cadence 1 second; flow/inactivity/execution horizon 5 seconds; `F_LAST=128`, `F_TOB=64`, `F_SNAPSHOT=32`, `F_MBP=16`, `F_BAD_TS_RECV=8`, `F_MAYBE_BAD_BOOK=4`; undefined-order-price comparison 9,223,372,036,854,775,807. These are this proposal's declared conventions, not newly verified native ABI/enum values. Unknown flag bits are retained and receive only the original inspected bit tests, not a new blanket enum allowlist.

Inherited S64 timestamp transport cannot represent native U64 undefined timestamp 18,446,744,073,709,551,615. Such a declaration is refused by unchanged binding before numerical acceptance; do not widen the accepted transport or replace the sentinel. The original engine's undefined-clock refusals remain a future native-boundary requirement. `rtype`/`record_size` remain the binding layer's exact structural declarations, not native size/type authentication.

## Exact declared native-shaped context

`AdapterContext` has these required fields, in order:

`input_version, upgrade_policy, yielded_version, stype_in, stype_out, partial, limit, ts_out`.

Exact choices are input integer 3, policy string `AS_IS`, yielded integer 3, stype-in string `parent`, stype-out string `instrument_id`, exact empty `partial` tuple, literal `None` for `limit`, and exact bool `ts_out`. `ts_out=False` requires old payload context mode `absent`; `True` requires `present`. All other combinations refuse; no decoder default or implicit upgrade is selected. These symbolic declarations are **constructed**, not a decoder's observed result.

Dataset/schema/symbols/not_found/day bounds/mappings are supplied once, in the unchanged old header; they are not independently editable duplicates. Together these fields cover the inspected metadata declarations for this narrow construction, not all future native metadata extensions. Native metadata's optional constructor limit/property representation and absent `ts_out` sentinel have not been experimentally established. `limit=None` and old absent payload `ts_out=None` are explicit constructed conventions, not verified translations of native unlimited/undefined values.

The complete context body is its eight named fields, tuples projected to lists. Its SHA is `H(context_body)`. Because limit is always None and partial is empty, the causal context contains no declared future record count, whole-member hash or discovered terminal state. New context must not retroactively enlarge the accepted `PayloadContext` or change old prefix identities.

## Complete types and resource intersection

All new dataclasses are exact frozen/slotted types; every field is required, with no defaults or constructor coercion. Exact tuples are the only sequence containers. Exact ints/bools/strings are distinguished, including bool/int aliases and subclasses. Submitted dictionaries, extra/missing fields, poisoned slots and mutable substitutes refuse. All new field-order lists below are part of the proposed literal protocol.

Input is exactly `AdapterFixture(context, payload_bundle)`. `payload_bundle` is the existing exact `PayloadBundle`: one immutable record sequence, not a second editable record list, quote list, checkpoint or submitted book.

Output types and their exact required field orders:

```text
OrderState(side, price, size)
OrderEntry(order_id, state)
PriceLevel(price, size)
AdapterAudit(decoded_position, disposition, instrument_id,
             target_candidate_ordinal, target_transition_ordinal,
             binding_prefix_sha256, adapter_prefix_sha256)
TargetTransition(decoded_position, target_transition_ordinal, disposition,
                 snapshot, exceptional_closed_clear, order_id, before, after,
                 initialized_before, initialized_after, last_recv_before,
                 last_recv_after, event_ordinal, quote_ordinal,
                 publication_ordinal, state_sha256)
EventWitness(event_ordinal, closing_decoded_position,
             closing_target_transition_ordinal, ts_recv_ns,
             target_positions, trade_positions, execution_capture_positions,
             quote_ordinal, adapter_prefix_sha256, event_sha256)
QuoteWitness(quote_ordinal, event_ordinal, decoded_position, ts_recv_ns,
             bid, ask, bid_qty, ask_qty, prior_quote_gap_ns,
             ofi_generation, bid_depth5, ask_depth5,
             adapter_prefix_sha256, quote_sha256)
InactivityInterval(start_ns, timer_fired_ns, end_ns, recovered,
                   trigger_decoded_position)
FeaturePublication(publication_ordinal, quote_ordinal, event_ordinal,
                   decoded_position, ts_recv_ns, adapter_prefix_sha256,
                   features, publication_sha256)
ClockSample(decoded_position, ts_recv, ts_event, ts_in_delta,
            flags, sequence, action, protected, event_ahead_ns, sending_ns)
ClockQuality(target_records, snapshot_records, non_snapshot_records,
             event_after_receive, negative_send_delta, event_after_sending,
             clamped_delta, clock_disagreement_records,
             protected_disagreement_records, outside_disagreement_records,
             min_event_ahead_ns, max_event_ahead_ns, min_negative_delta_ns,
             samples)
ReconstructedState(initialized, orders, bid_levels, ask_levels, last_recv_ns,
                   pending_target_positions, pending_trade_positions,
                   execution_capture_positions, last_quote_ordinal,
                   flow_events, cvd, known_trades, unknown_trades,
                   ofi_generation, ofi_previous_quote_ordinal, ofi_first_ts_ns,
                   ofi_events, ofi_total, history_ofi_generation, history_quote_ordinals,
                   bid_depletions, ask_depletions, history_reloads,
                   execution_last_ts_ns, execution_events, execution_totals,
                   bid_credits, ask_credits, execution_audit,
                   next_publication_ns, watch_since_ns, inactivity_start_ns,
                   window_closed)
AdapterAssessment(status, protocol_sha256, context_sha256,
                  binding_protocol_sha256, cursor_protocol_sha256,
                  fixture_sha256, fixture, binding_assessment, audits,
                  transitions, events, quotes, publications,
                  inactivity_intervals, clock_quality, exceptional_clear_count,
                  terminal_state, authority_flags, assessment_sha256)
```

Numeric state is reconstructed, never supplied as original input. `before`/`after` are exact `OrderState` or None for the record's order ID, including an existing order for a T/F/N or R when applicable. R's `after` is None because it clears the whole book; it is not only a deletion of that ID. Orders are exact `OrderEntry` sorted by numeric ID; levels are `PriceLevel`, bids descending and asks ascending. This deterministic **output** projection does not sort/reorder input records. Depth5 retains up to five current PriceLevels, in those same side-specific orders.

State queues have literal shapes: flow entries `(ts, signed_size, known_count, unknown_count)`; OFI entries `(ts, value)`; side depletion entries `(ts, remaining_size)`; history reloads `(ts, bid_matched, ask_matched)`; side execution credits `(ts, order_id, remaining_size)`; execution events `(ts, metric_pairs)`. Metric pairs are exact sorted `(side_metric_name, integer_quantity)` tuples, where side_metric_name is `A_` or `B_` followed by one of the seven metric names below (no `_5s`). `execution_totals` uses the same names; `execution_audit` preserves the held helper's exact audit key strings. Both are exact sorted pairs including zero keys actually retained by the normative Counter behavior, without manufacturing absent keys. Trade audit key names may retain the original single ASCII side character; arbitrary keys outside the normative helper are refused. Numeric aggregate quantities use exact ints (no float price conversion); mathematical sums are not falsely bounded to native single-field widths. Finiteness/overflow and byte caps remain fail-closed. `history_ofi_generation` is None until the first observation, then the generation last attached to history; it can differ from current OFI during an inactivity reset before the next quote.

Order side is exactly A or B, quantities strictly positive; raw order IDs/prices/sizes retain inherited integer domains. Reconstructed aggregate level sizes can exceed one raw size. Non-optional references/ordinals are exact ints in their respective stated bounds; an absent reference is exactly None. Snapshot/exception/initialized/recovered/window/protected values are exact bools (observations, not authority flags). State timestamps/queue arithmetic are exact ints or the explicitly optional None; flow/OFI signed totals may be negative, unsigned quantities/counts cannot. Quote/event/publication receives lie in the original target day; observed quote/publication intervals are as specified below. All value equality is finally determined by complete reconstruction, not these range checks alone.

The exact execution-audit key vocabulary is `temporal_resets`, `stale_spanning_events_excluded`, `fill_above_displayed_volume`, `completed_events`; `fill_<reason>_records`/`fill_<reason>_volume` for reasons exactly `without_trade`, `unknown_aggressor`, `aggressor`, `unknown_side`, `price_mismatch`, `unmatched_book`, `matched_passive`; `<side>_<metric>_volume` for side A/B and the seven literal metrics; and `trade_<one ASCII character>_volume`, preserving that character verbatim. Only keys actually touched by the held Counter appear, including +=0; no absent-zero manufacture. Event metric pairs are positive-only after unary +delta; rolling totals may retain zero after subtraction.

Normative optional/reference matrix (structural links are checked in phase1; raw-field-derived truth is checked in phase2). `trigger_decoded_position` means the position **closing** an inactivity interval, not necessarily the incoming position that first caused its timer to fire; the logical timer fire time is separately retained.

| Field family | Exact rule |
| --- | --- |
| Audit header | Position1; header; ID/candidate/transition all None. |
| Audit foreign | Old foreign ID/position; both target ordinals None. |
| Audit target | Exact old target ID/candidate; transition ordinal matches its position in transitions. For a completely accepted fixture all candidates have successful transitions; neither set is filtered. |
| Transitions | Exactly every mapped target position in original order, one per target; disposition grammar is target_reset/target_snapshot/target_record. In phase2 exceptional clear implies reset, snapshot=False; snapshot=True with R may be reset; target_snapshot always snapshot=True. Actual observed booleans/R/snapshot versus raw action/flags is phase2. |
| Transition artifact refs | Links name artifacts **created at this transition only**. Nonclosing/reset/snapshot transitions have all3 None. Ordinary closing transition has its event ordinal; quote/pub refs are None if no quote/publication was created. No later closure is retroactively attached to an earlier member. |
| Event membership | Nonempty strictly increasing target positions; target_positions[-1] equals closing_decoded_position. Independently, closing_target_transition_ordinal equals the target_transition_ordinal of the transition at that closing decoded position; decoded position is never equated with target ordinal. Events ordered by closing position, disjoint target memberships. Trade/capture positions are strictly increasing subsets of target_positions; actual T/protected predicates require raw values in phase2. Ordinary memberships cover exactly declared target_record transitions. |
| Event quote ref | None when no observation. Otherwise one exact QuoteWitness with same event and closing position; never declared reset/snapshot quote. Timestamp/numerical equality is phase2. |
| Quote refs | Every quote has one existing event and its closing position; quote/event back-links agree. Quotes ordered by created ordinal/position. |
| Publication refs | Exactly one existing quote/event at its closing position; ordered ordinals/positions and at most one publication per quote. Time equality/cadence/first due truth follows numeric replay. Features exact37 `(name, scalar)` pair envelopes in fixed name order before any scalar read. |
| Inactivity trigger | Target position for target-triggered closure/recovery; None only for terminal end closure. Trigger must exist among target transitions. Actual terminal recovery=False and all timestamps/recovered booleans are phase2. |
| Clock samples | Up to8 in strictly increasing mapped target positions. event_ahead_ns=ts_event−ts_recv; sending_ns=ts_recv−ts_in_delta, no other sending convention. Samples/quality counter truth is late. |
| Optional state values | `last_recv_ns`, `last_quote_ordinal`, `ofi_previous_quote_ordinal`, `ofi_first_ts_ns`, `history_ofi_generation`, `execution_last_ts_ns`, `inactivity_start_ns` may be exact None. All other scalar/state containers are present. Quote refs/history refs are structural and must refer to already observed quotes in order; optional numeric timestamps/generations are checked in phase2. Missing-last-quote resets do not invent a quote. |
| Before/after | Exact OrderState or None, determined solely from the record's ID in actual reconstructed book at pre/post application. No submitted checkpoint accepted. |

Early reference checks refuse syntactically malformed/out-of-range or **metadata-derivable** contradictions. A syntactically valid coherent but wrong F_LAST/T/snapshot/capture link, numerical counter, timestamp or feature requires payload/numerical traversal and is refused later; this is never advertised as an impossible metadata-only discovery.

Decoded positions include the header and every foreign occurrence. Target candidate ordinals come only from old cursor metadata. Successful target transition ordinals are independently contiguous one-based, advanced **after** valid book application, including accepted clears and snapshots. A refused transition produces no assessment or successful-subset ordinal. Event/quote/publication ordinals are each independent contiguous one-based. None is a byte offset or authenticated native target ordinal.

New limits: at most 127 target transitions, ordinary events and observed quotes; **1 through 32 publications**; at most 128 inactivity intervals; at most 127 current orders/queue records per reconstructed queue; eight clock samples; 32 exceptional clears. There are no synthetic entry/exit/cooldown rows. Each new complete fixture body and complete assessment body is capped at **1,048,576 canonical bytes**; equality passes, greater refuses, using a shared bounded-canonical guard. The unchanged old **2–128 complete positions**, mapping limits, both **65,536-byte cursor caps** and both **262,144-byte binding caps** remain independently enforced. An outer cap never overrides an inner refusal.

State hash projection is also bounded by 1,048,576 bytes. It contains every ReconstructedState field, not only order summaries. Queue/aggregate structural maxima follow the at-most-127 complete records; post-expiry retained zero totals are bounded to the helper's finite key vocabulary. Clock counters are exact nonnegative ints at most 127; extrema/samples are exact ints or specified None, retaining inspected arithmetic rather than asserting native widths. No public-envelope capacity measurement is claimed now. A later independent capacity example is not a universal maximum. Never truncate, thin, split, deduplicate or relabel historical inputs to fit these constructed limits.

## Metadata-before-values boundary

Every expected pin is mandatory, keyword-only, exact lowercase ASCII 64-character hex. Check **all** pin syntaxes before caller-object traversal, then known new/binding/cursor protocol equality. Canonical context equality follows exact context validation. Whole fixture/assessment equality follows complete value reconstruction; it cannot be proved before reading the values it binds.

Phase 1 preflights **all original and submitted metadata** before either payload traversal:

- Exact context/fixture/result/binding/cursor envelopes and complete tuple counts/types; all old header/mapping/item assertions, including the final foreign declaration; context modes and new fixed version/stype/partial/limit choices.
- All result status/pin syntax, every audit/reference position/ordinal/disposition, all exact typed record envelopes, and all literal false flag pairs at every layer. Header/foreign target-ordinal None rules are checked from rebuilt cursor metadata. Submitted numerical slots are not required to match until phase 2.
- Reconstruct the metadata-only old cursor assessment with its unchanged public APIs and both old caps. Preflight submitted nested binding metadata explicitly, and verify its nested cursor through unchanged `cursor.verify`. No private binding helper becomes a public dependency.
- Exact caller-object/entry types and tuple envelopes can be inspected without traversing a numerical slot. A numerical scalar's exact type requires reading its slot and is therefore **phase2**, never an excuse for early getattr. All independent metadata contradictions are rejected now. A malformed **last** status/authority-flag/reference envelope refuses before any original or submitted deferred numerical slot.

Deferred values are **all sixteen MboPayload fields** in both original and submitted bundles, and submitted OrderState/OrderEntry ID/PriceLevel values, transition raw order ID/before/after/receive values, event/quote/publication timestamps and quote/depth values, feature scalar values, inactivity timestamps, **all ClockQuality scalar counters/extrema and all ClockSample values except decoded_position**, numerical terminal-state queue/counter values, and **all new observed booleans/OFI-generation values** (snapshot/exception/initialized/recovered/protected/window_closed/generation fields). Their exact scalar type/value checks wait for phase2. Context ts_out is metadata and remains checked early; every literalFalse authority is also checked early. Output ordinals/positions/reference metadata and queue container/name/arity shapes have separately named structural roles above; validating those is not payload access. Checking `type(payload_object)` does not read raw slots; checking `type(payload.price)` does. Generic reflection/getattr across all fields is forbidden in phase1.

Only after the complete phase-1 gate may phase 2 invoke public `binding.assess`, `binding.bundle_sha256` or `binding.verify`, because those APIs read raw bodies. It must use their full unchanged verification; a new metadata preflight is not a substitute for accepted binding verification. Recompute all original/submitted payloads, their pins, complete binding and numerical witness. Do not call binding verification early or reuse its private preflight; do not repair caller pins or adopt submitted order/counter/feature state.

Phase 3 bounds/recomputes complete fixture, all reconstructed artifacts and result; requires exact nested types, every field, actual canonical bytes and every retained digest equal the rebuilt original assessment. `verify` returns None only after all checks. Bad numeric suffixes may require numeric access to discover, but refuse the whole result with no partial output.

Normalize malformed shape/value `ValueError`, `TypeError`, `AttributeError`, `OverflowError` to ValueError. **Do not catch AssertionError**: later real read sentinels must prove access order, not merely generic ValueError. Diagnostic wording is not the contract. This is no protection against concurrent object mutation, code replacement or coherent caller whole-context replacement.

## Normative day, quality and book semantics

The following rules are source-grounded projections of the held receive/event engine, with explicit new bounded witness envelopes. They are not already observed native parity.

1. Start the day with empty **uninitialized** book, empty flow/OFI/history/execution queues, no last quote/receive, no pending event/T/capture. Next publication is noon; watch begins at warmup. OFI generation starts at 0, increments for every actual replacement (startup is generation 0; missing-last-quote observation, inactivity reset each replace). History attaches to an OFI generation only when a quote is observed. Do not fabricate R, adopt a supplied checkpoint or force instrument 1.
2. The sole header is position 1; all later occurrences are MBO. Old header/mapping checks remain exact, including one end-exclusive active requested mapping and preserved unrelated/inactive declarations. Foreign records retain all structural body checks and provenance but **return before target day/clock/timer/book/flow/event processing**. They cannot close F_LAST, trigger inactivity, update quotes or change target receive time.
3. For a target, require day-start <= receive < day-end. Snapshot is the original bit test. Selected-window [noon,16:00) snapshot refuses. Bad quality mask is BAD_TS_RECV|MAYBE_BAD_BOOK|TOB|MBP; snapshots exempt only BAD_TS_RECV. Unknown bits are not a new refusal by themselves.
4. Exceptional closed clear requires exact flags BAD_TS_RECV, R, side N, outside the decision window, event <= receive, and the inspected fixed-day CME helper returns closed. For this fixed Monday April 7, 2025, its closed daily break is **[21:00,22:00) UTC**. At most 32; no wider holiday/calendar claim. It bypasses ordinary regression/timer/last-receive advancement, just as snapshots do.
5. Incomplete prior ordinary target event forbids an incoming R/snapshot, including non-T incompleteness. Pending T separately forbids R/snapshot. ClockAudit runs after quality and those checks, before ordinary timers/book. Non-snapshot event > receive or negative send delta refuses in protected [warmup,16:00); outside it is audited without correction. Event-after-sending (`event > receive−delta`) and clamped-delta (`delta` exactly −2**31 or 2**31−1) audit counts alone do not add refusal rules. Samples retain the first eight disagreements in target order, including original flags/sequence/action/protected predicate plus linked decoded position and exact event_ahead/event-sending arithmetic. The event-ahead min/max summarize only positive ahead values, negative-delta minimum only negative deltas, otherwise None. Snapshot clocks are not compared; inherited out-of-domain undefined receive/event values cannot reach this stage. New ClockQuality `snapshot_records` means ClockAudit's `snapshots_not_clock_compared`, **including snapshot R**, not the core's later snapshot counter which R bypasses. Thus target_records=snapshot_records+non_snapshot_records. `clock_disagreement_records` aliases ClockAudit's disagreement_records, `clamped_delta` its clamped_send_delta, and min_negative_delta_ns its negative send-delta minimum. The new flattened fields include explicit zero counts, unlike the original sparse Counter report; no original report-format parity is asserted.
6. Ordinary non-snapshot/nonexception target receive time must not regress; equality is allowed. Before incoming book mutation, advance applicable **feature inactivity/window timers** to min(receive,end−1), then close the observation window if receive >= end. Save ordinary last receive. Selected-window live R refuses. No strategy entry/exit/hold/cooldown/episode state is created: those original policy timers remain outside this target-free component.
7. Strict book R clears/initializes; T/F/N do not mutate or initialize standing orders. A/C/M require initialization, known supported side, positive size, non-undefined price and original order granularity. A refuses duplicate ID; C requires existing matching side/price and not excessive quantity, reducing/deleting; M requires known ID, same side, removes old quantity then replaces price/size. Any original Book fault refuses the whole result. Negative/off-absolute-grid order prices are not newly rejected merely for convenience: the inspected book does not impose those restrictions. Best quote restrictions and execution trade restrictions remain separate.
8. Capture each protected [warmup,end), non-snapshot target against the **pre-update** reconstructed order state before parent validation/application, preserving original wrapper order. A later refusal still aborts the whole witness. Successful book application advances target ordinal. R resets flow/last quote and returns before ordinary F_LAST; snapshot returns without ordinary F_LAST. Reset/snapshot clear protected capture while the observation window is not closed. Dispositions are `target_reset`, `target_snapshot` or `target_record`; snapshot R uses `target_reset` with snapshot=True, exceptional flag retained.

All audits retain original binding prefix. Header disposition is `header`, foreign is `foreign`, target audits use the transition's disposition. Target reset/snapshot are **not ordinary event closures**. Incomplete-event tracking applies to every ordinary non-snapshot/non-R target lacking F_LAST, not just T.

## Events, quote observation, timers and first publication

An ordinary event retains the exact ordered target decoded-position tuple from the previous ordinary completion/reset/snapshot boundary through its target F_LAST. Foreign interleaving is not a target range. Non-R snapshots are separate transitions and cannot arrive while an ordinary event is incomplete. Ordinary singleton F_LAST is an event. Full event provenance includes earlier out-of-protected target records; execution capture is a separate exact tuple of the original protected non-snapshot records, never automatically extended to that full event.

T appends to the pending trade queue; F is not a second trade. At ordinary target F_LAST, add every pending T to FiveSecondFlow at the **closing record's receive time**, then clear pending trades. Known B contributes positive size, A negative, other side zero signed volume and one unknown count. Five-second expiry removes timestamps **strictly less than** now−5s, keeping equality. The source's T/F/N no-op book behavior and execution-only trade quantity/price validation are not replaced by a global T/F filter.

Every ordinary F_LAST creates EventWitness, even when no quote is observed. EventWitness trade_positions is the full T tuple flushed at that completion; capture_positions is the separate protected tuple consumed/cleared by that boundary. No quote is observed if uninitialized or outside [warmup,end). Otherwise require two complete best sides, bid < ask, positive top quantities and tick-divisible **spread**. Do not import the old synthetic witness's extra absolute bid/ask tick-grid restriction. Quote-level prices and spread are reconstructed raw ints, not pretty-price conversions.

At an observed quote: advance inactivity at its receive time; close an open interval as recovered; retain actual prior quote gap (last_quote is **not** cleared by inactivity); replace/observe OFI as specified by source; reset/observe history if OFI generation changed; complete ExecutionWindow with original protected capture and the previous quote; set last quote; then consider publication. Warmup observations update helpers but do not publish.

Inactivity fires only at strict now > watch_since+5s, at logical watch_since+5s+1. It replaces OFI once until recovery, but does not clear last quote, flow or the execution observer. Equality retains state. First-quote/missing-last-quote observation may replace OFI again; history follows final generation. Recovered interval records start, logical fire, observed end and closing decoded position. At target-free terminal closure, advance to end−1, close any open inactivity interval at end with recovered=False and trigger_decoded_position=None, then mark window closed. Closing by an ordinary target crossing end uses that target's position for the unrecovered interval; it never makes that target a protected quote.

The **first** observed completed quote at/after next_publication and inside [noon,end) publishes all 37 current features, then sets next_publication to that quote's receive+1s. Later equal-time completions can update helpers, but cannot rewrite or republish the preceding publication. Do not backfill grid rows, wait for a later better quote or inspect future terminal states. A publication remains allowed even when original strategy eligibility would be zero; this layer publishes features only, not a strategy vote or eligible trade.

Execution's held helper rules are normative: first quote or strict >5s quote gap resets temporal state; equality does not. Expire entries/credits strictly before cutoff; stale spanning exclusion is based on the **protected captured suffix's** first receive, not the full event. Consecutive T/F links use known passive side, resting ID/pre-state, price equality and matched fill volume <= trade; T requires positive tick-grid price/size here, F positive size. Unknown/unlinked fills remain audited rather than assumed fills. Original stable-top linked decrease/reload/net-refresh rules apply; same-ID net refresh is a separate overlapping metric, not volume added again. Full event before warmup T followed by in-window F can therefore produce signed flow but `fill_without_trade` in the captured suffix. Capture clears at ordinary target F_LAST regardless of whether a quote was observed; reset/snapshot handling above remains separate.

## Exact 37 feature order and representation

At publication, expire OFI/flow at publication time; use current reconstructed depth and helpers. Features are exact tuple `(name, scalar)` in this order. Every scalar is finite exact float **except** `mid_travel_5s_ticks`, whose original one-history-quote `sum` is exact int 0; with two or more quotes it is exact float. Preserve original int/float and signed-zero canonical representation; do not apply the older synthetic witness's sole int-zero ->0.0 normalization. Raw-record integers remain exact even though original numerical feature arithmetic deliberately uses floating operations.

The first eight names/formulas are: log_bid_qty=log1p(B); log_ask_qty=log1p(A); queue_imbalance=(B−A)/D; normalized_ofi_5s=2*OFI/D; normalized_cvd_5s=2*CVD/D; log_known_trades_5s=log1p(known); unknown_trade_fraction_5s=unknown/(known+unknown), or 0.0 if no trades; log_prior_quote_gap_ms=log1p(actual_gap_ns/1,000,000). Here B/A are top sizes, D=B+A. Evaluation order follows the pinned source, not algebraically rearranged “equivalents”.

Next fifteen, in order: `log_bid_depth5`, `log_ask_depth5`, `depth5_imbalance`, `bid_top_share5`, `ask_top_share5`, `bid_span5_ticks`, `ask_span5_ticks`, `mid_change_5s_ticks`, `mid_range_5s_ticks`, `mid_travel_5s_ticks`, `log_quote_events_5s`, `normalized_bid_reload_5s`, `normalized_ask_reload_5s`, `buy_absorption_proxy_5s`, `sell_absorption_proxy_5s`.

These use the exact held QuoteHistory.observe/features definitions: first five actual levels per side; mids `(bid+ask)/(2*tick)`; last-first change, max-min range and ordered sum of absolute adjacent changes; same-price depletion FIFO credits and reload matching, clearing side credit on changed best price; normalized reload sums/D; positive/negative CVD divided by D*(1+positive/negative mid change). Entries strictly before cutoff expire; equality remains. Do not turn cancellation/depletion/reload proxies into authenticated trades or hidden liquidity.

Final fourteen names are the Cartesian order side `bid`, then `ask`, each with metrics `passive`, `held_top_passive`, `linked_decrease`, `unlinked_decrease`, `same_id_reload`, `other_id_reload`, `same_id_net_refresh`, suffixed `_5s`. Each is its held nonnegative rolling integer total divided by current D, using exact ExecutionWindow semantics. All 37 names are present, once, with no winner/vote/model or outcome field.

The held numeric functions and their pinned source identities below are normative for omitted mechanical arithmetic details (depletion FIFO, fill reason precedence, refresh calculation, OFI increments). **Only those functions**, not whole historical producers/targets, form the rule reference. A disagreement between this prose and a held rule is a contract finding requiring clarification before approval/implementation, not permission to silently choose new behavior. Later independent literal oracles must spell out complete expected rows/states from the contract and these fixed rules, not call production serializers or adopt production results.

## Complete terminal acceptance

Require exactly one complete header, at least one successful target, no incomplete ordinary event, no pending T and no protected capture. Require **1–32** complete publications, each from an observed quote with adjacent timestamps >=1s. Require clock target observations equal successful target transitions. The terminal state includes every current order/level and every helper queue/count, final next-publication/watch/inactivity/window state and audit, including records after observation end.

Close the observation window once as above. This is a **new target-free constructed finish contract**. It does not call CostTargetBuilder.finish or require resolved hindsight targets, accepted trades, profitable rows or native source EOF. Original full producers' larger coverage/strategy/outcome requirements are separate and must not be claimed fulfilled by 32 toy publications. Caller-member assertions stay assertions. No terminal-success marker proves actual decoder EOF.

## Canonical identities, causal links and pure API

`H(x)` is SHA256 of `json.dumps(x, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')`, no newline. Explicit literal field projections only; tuples project to lists, flags and sorted counter-pairs to dictionaries. ReconstructedState orders/levels and all named records project in their stated schema; exact type checks remain separate from JSON equality. Nonfinite values refuse. Do not normalize floats or drop zero keys.

Complete fixture body is exactly `{context: complete_context, payload_bundle: complete_old_bundle}`. The complete result is every AdapterAssessment field except its own assessment_sha256, including the **entire** fixture, binding assessment with its own hash, every audit/transition/event/quote/publication/interval/quality/terminal body and false flag. No summary-only verification.

For each complete decoded position, including header:

```text
adapter_prefix_sha256 = H({adapter_protocol_sha256: P,
                           context_sha256: C,
                           binding_prefix_sha256: checked_old_bound_prefix})
```

The old contextual chain stays unchanged. P contains fixed used-rule metadata pins, not future runtime discovery. The wrapper excludes whole fixture/bundle/result/member pins, declared total count, terminal helper state, future artifacts and future record values. Full declared header/mapping and interpretation context are available at the header; their identities remain bound through the old prefix and C.

Each event/quote/publication pin is H(its complete named body excluding only its own pin). Event refers to quote **ordinal**, not quote SHA; quote refers to event ordinal; publication refers to quote/event ordinals and consumed adapter prefix. These integer references plus complete body checks avoid digest cycles. State_sha256 is H(the complete state after consuming that target, including publication/capture clearing); no future totals appear in it. Complete result equality validates every reference against actual reconstructed membership, not merely pin syntax.

For fully valid paired fixtures, changing only an **unconsumed suffix** or complete-only member assertion changes complete identity but preserves earlier prefix/publication bodies/digests when used-source metadata, context/header and consumed records stay fixed. Changing a **consumed foreign** body/position changes provenance links and publication digests even if target numerical values/time/cadence remain identical. The numerical invariance and provenance invariance claims are intentionally distinct. Invalid suffixes refuse the whole result.

Six proposed public calls, not implemented APIs:

```text
protocol() -> dict
protocol_sha256() -> str
context_sha256(context, *, expected_protocol_sha256) -> str
fixture_sha256(fixture, *, expected_protocol_sha256, expected_context_sha256,
               expected_binding_protocol_sha256, expected_cursor_protocol_sha256,
               expected_cursor_fixture_sha256, expected_binding_bundle_sha256) -> str
replay(fixture, *, expected_protocol_sha256, expected_context_sha256,
       expected_binding_protocol_sha256, expected_cursor_protocol_sha256,
       expected_cursor_fixture_sha256, expected_binding_bundle_sha256,
       expected_fixture_sha256) -> AdapterAssessment
verify(assessment, fixture, *, expected_protocol_sha256, expected_context_sha256,
       expected_binding_protocol_sha256, expected_cursor_protocol_sha256,
       expected_cursor_fixture_sha256, expected_binding_bundle_sha256,
       expected_fixture_sha256, expected_assessment_sha256) -> None
```

`fixture_sha256` executes complete reconstruction/finish/capacity checks, not a lenient serializer. Caller dependency order is context -> checked payload pins/old fixture -> accepted bundle -> adapter fixture -> replay -> verify. No implicit pin repair, default expected value or supplied state adoption. Both replay and verify are deterministic pure in-memory operations.

## Literal protocol, used-rule metadata and false authority

`protocol()` returns a fresh dictionary with exactly: `version`, `scope`, `status`; `context_values`; `utc_date`, `contract`, `day_start_ns`, `day_end_ns`, `warmup_start_ns`, `window_start_ns`, `window_end_ns`; `constants`; `limits`; `dataclass_fields` (each exact field-order list above, including AdapterContext and AdapterFixture); `feature_names` (the exact ordered37); `feature_scalar_rule`=`original_float_values_except_single_quote_int_zero_travel`; `prefix_scheme`=`adapter_protocol_context_checked_binding_prefix`; `prefix_complete_member_pin`=`excluded`; `binding_protocol_sha256`, `cursor_protocol_sha256` from unchanged public protocol calls; `binding_source_sha256`, `cursor_source_sha256`; `numerical_rule_sources` mapping the nine **full repository-relative paths** `src/ai_trader/research/<filename>` below to their held raw SHA; `authority_flags` (the exact all-false dictionary below). P=H(this literal dictionary). Day bounds come from fixed old protocol; window bounds are its fixed arithmetic. Returning/mutating a dictionary or changing exported constant variables must not alter literal enforcement or identity.

The three nested dictionaries have exactly these keys/values (JSON spellings):

```text
context_values = {input_version:3, upgrade_policy:"AS_IS", yielded_version:3,
                  stype_in:"parent", stype_out:"instrument_id", partial:[],
                  limit:null, ts_out_modes:[false,true]}
constants = {second_ns:1000000000, tick:50000, decision_interval_ns:1000000000,
             flow_ns:5000000000, inactivity_ns:5000000000,
             execution_window_ns:5000000000, F_LAST:128, F_TOB:64,
             F_SNAPSHOT:32, F_MBP:16, F_BAD_TS_RECV:8, F_MAYBE_BAD_BOOK:4,
             UNDEF_PRICE:9223372036854775807}
limits = {min_items:2, max_items:128, max_mapping_groups:8,
          max_intervals_per_group:16, max_total_intervals:32,
          max_cursor_body_bytes:65536, max_binding_body_bytes:262144,
          max_adapter_body_bytes:1048576, max_state_body_bytes:1048576,
          max_transitions:127, max_events:127, max_quotes:127,
          min_publications:1, max_publications:32, max_inactivity_intervals:128,
          max_orders:127, max_queue_entries:127,
          max_clock_samples:8, max_exceptional_clears:32}
```

Used binding source metadata: `4c5ac736a268c350389c63f0c23577fdcdd4473ea19d16aa13313cb49187be94`; cursor: `c7bc0102073fa61f1d69411479331cf1e434616cb80faa6bbc266377745dcf91`. These are source-text metadata identities, **not authenticated whole runtime/import graph proof**. No filesystem source reader is added.

| Held rule source under src/ai_trader/research | Raw SHA256 | Normative part only |
| --- | --- | --- |
| databento_6e_training_data.py | 9d1c9190da304031113880dbfb4d002121908d35b6bc52671a65939a6e7049a3 | Book; fixed-day calendar; mapped header checks |
| databento_6e_scenario_replay.py | d5bf8e3e0ec4b1957f1a2a7ed515f1cf9530b922e5c2c3929389ed0bfeab91ff | StrictBook.apply only |
| databento_6e_seconds_pilot.py | 7c295b7cc3875a6955d3582368a7d28804dd318e061e0d0b3906e4a21e411b2b | Quote/FiveSecondFlow; day initialization/quote checks |
| databento_6e_ofi_scalp.py | 05cade0f206c06cbea93198c9fb92e591c0275ef5ac70f8ce50bcb000ad0ff24 | ofi_increment/OfiWindow/quote-observation reset |
| databento_6e_event_scalp.py | 48bd0402c2e8a7c0d8d286b8956a2f55059c71df81dc1115ee15d8adce560b3e | Inactivity, incomplete-event, first due quote, window closure; no policy rows |
| databento_6e_cost_targets.py | ebc4c1dc0a44e71362cd96bed0a699dac6ebc04a66fc7f568d2bf4898d427b2b | Prior quote gap and first eight feature arithmetic only |
| databento_6e_microdepth.py | 8964b20a5de8104a0f7831cf827c1c736f3c11b6a2d61dbe0206521ee3b451c4 | QuoteHistory and history-generation observation order |
| databento_6e_execution_flow.py | 7f777a19518378dd3b2a0371b7f3ddcf3077f51555faffa5e589de6255239b75 | Record.capture/match_fills/ExecutionWindow/protected capture ordering |
| databento_6e_receive_clock.py | 351b4b54fc3ac4ac905ebdbb9725f270288ac235178cb50180e2040d8fef4636 | ClockAudit/ordered receive processing; no loader/builder calls |

Top-level flags are **exactly the accepted binding's 31 names**, all literalFalse, plus `original_feature_row_parity_verified`, `complete_history_capacity_verified`, `multi_session_continuity_verified`: exactly34 alphabetically sorted `(name,False)` pairs. The old binding31 and nested cursor26 remain complete and false. The 31 names are: account_authenticated, book_application_verified, broker_economics_measured, byte_offsets_verified, calendar_authenticated, codec_context_authenticated, decoded_source_authenticated, event_closure_verified, execution_allowed, feature_derivation_verified, funding_authenticated, historical_access_allowed, historical_validation_allowed, mapping_authenticated, model_call_allowed, native_decoding_verified, native_eof_verified, native_header_verified, native_payloads_verified, native_record_semantics_verified, native_target_ordinals_verified, original_bytes_verified, promotion_allowed, publication_cursor_verified, runtime_authenticated, scoring_allowed, source_authenticated, storage_resume_allowed, strategy_integration_allowed, trading_enabled, training_allowed. Constructed reconstruction success never turns any into True; numerical success is expressed in reconstructed bodies, not false native authority labels.

## Independent acceptance matrix — all UNEXECUTED

1. Literal full protocol/context/type/container/false-flag projection, mutable-export resistance; refuse missing/extra/subclass/bool aliases and unsupported version/stype/limit/partial/ts_out combinations.
2. Full original/submitted metadata preflight; actual uncaught read-sentinel AssertionError for every16 raw field and each submitted deferred numerical/observed-boolean/generation family. A bad final status/authority-flag/envelope or metadata-derivable reference contradiction must refuse first. A valid-shaped false numerical membership waits for value reconstruction. Demonstrate a real eager-read mutant is killed; generic ValueError and collection failures are not evidence.
3. Complete hand-built header/mapping/target/foreign/payload/body/cursor/adapter canonical oracle, independent literal hashes and all artifact memberships. Non-1 mapped ID, inactive/unrelated mappings and end-exclusive mapping edges; no manufactured fixed R.
4. Native-shaped uninitialized startup and actual earlier R/snapshot/A/C/M path; strict book faults, unknown modifies and exact pre-update order states; resets with/without F_LAST and snapshot R distinct from ordinary event closure.
5. Foreign semantic poison and gaps: all16 fields retained and structurally validated, no target clock/timer/book/flow effect; foreign F_LAST cannot close an event. Consumed foreign changes provenance, not unchanged target numeric results.
6. Day, snapshot, live-reset, quality mask and closed-clear exact predicates/bounds; protected disagreement vs outside audit; snapshot regression exemption; original equal-receive order; representability refusal instead of undefined-sentinel coercion.
7. Non-T incomplete event, pending T/reset/snapshot failure, multiple T and unknown side flow, F no double-count, exact completion clock, terminal incomplete refusal.
8. Event crossing warmup: full target/T provenance distinct from protected captured suffix; F without captured T remains original fill_without_trade despite signed flow. Snapshot/outside-window F_LAST no manufactured observed quote.
9. Spread-grid vs absolute-grid distinction, complete positive top quantities, actual prior gap, OFI generation/history replacement order and strict five-second equality/+1ns expiration/inactivity before incoming non-final mutation.
10. Independently exact eight+fifteen+fourteen feature values/types; negative/off-grid standing prices where source permits; execution's stricter trade checks, fill reason precedence/quantity caps, stale capture span/temporal gap equality, reload/refresh overlap and zero-counter retention.
11. Warmup quote observation, first due completion, following equal-time update, one-second cadence, end−1 timer closure and after-window target state without future publications. No strategy eligibility/outcome filtering.
12. Full target/clock/capture/finish coverage, 1–32 publications and all complete states; every count/link/prestate/feature/digest/flag tamper rejected without adopting caller summaries.
13. Fully valid changed future suffix/member assertion preserves earlier complete publication identity with context/prefix fixed; changed consumed foreign identity has qualified numerical-only invariance. No future totals in seed/state/publication.
14. Every nested/outer complete cap equality/overflow; independently measured legal high-count invented envelopes in both modes, distinguished from arbitrary guard bodies and universal maxima. No salvage/partial return or scope bypass.
15. A later explicitly released implementation requires independent source/test authors, full stable-pair/root review, meaningful collected/executed RED/GREEN and mutation evidence, complete new/focused/adjacent checks and source-frozen complete suite. Preserve all **416 old source/test files and 10,872 old case-sensitive identities**, plus exactly every independently registered new identity; exact three prior skips/full XML representations, zero failures/errors, raw report/hash, owned command/executable/creation/parent exit and whole/old/new/package/contract pins before acceptance. No new count is guessed or runtime launched now.

## Style, prospective commands and definition of done

Style follows the accepted exact-type, keyword-only, frozen/slotted interface. Existing accepted code, shown as a style reference rather than a new implementation:

```python
@dataclass(frozen=True, slots=True)
class PayloadContext:
    codec_id: str
    schema_version: int
    ts_out_mode: str
```

No runtime command is released in this window. These complete command **templates are UNEXECUTED**; fresh registration placeholders may be replaced only after a separate implementation release and stable source/test review:

```text
.venv/Scripts/python.exe -B -m pytest -q tests/test_six_e_typed_native_event_adapter.py --junitxml=logs/typed_native_event_focused_<fresh-registration>.xml
.venv/Scripts/python.exe -B -m ruff check src tests
.venv/Scripts/python.exe -B -m ruff format --check src/ai_trader/research/six_e_typed_native_event_adapter.py tests/test_six_e_typed_native_event_adapter.py
.venv/Scripts/python.exe -B -m pytest -q --junitxml=logs/project_full_suite_<fresh-registration>.xml
```

The proposed test file does not exist. Later adjacent selection/process identities/expected case counts/resources/contingency must be prospectively registered; this is not that execution plan. Root owns later launches under separately obtained authority, holds all writers during every run and freezes all sources/tests throughout a complete suite.

Documentation-only done now: source-backed semantics, no unresolved required static finding, accurate links/status/approval questions, current hard end and unchanged accepted files. Runtime/native correctness, throughput, largest valid envelope, full historical coverage and source/runtime authentication remain unverified. Package/dependency/security audits, deployment and commits are outside scope, not automatically required by generic skill checklists.

## Threat model, trade-offs, boundaries and approval questions

Untrusted caller fixtures/results can spoof context, tamper links/values, omit foreign data, poison lazy slots, inflate resources or falsely imply native authority. Exact schemas, metadata-first phasing, bounded complete bodies and independent reconstruction mitigate inconsistency/DoS within declared bounds; hashes do **not** authenticate a caller who coherently replaces the whole fixture/context/expected pins. No money movement, credentials, network, reader/path operations or LLM exists at this boundary. Web authentication/CORS/SQL controls are inapplicable, not silently “passed”.

The chosen interface wraps a single accepted record sequence, adds explicit interpretation context and reconstructs local numerical state. Alternatives rejected here: importing native builders for convenience, coercing the old fixed witness, supplying a starting order dictionary, widening old caps, clipping captures to make full-event claims, algebraically changing float arithmetic, filtering strategy/no-trade rows, adding native decoding/history/account workflows. Those either broaden authority or obscure evidence; later separately reviewed contracts can address real native layers.

- **Always:** preserve complete target/foreign input order/raw representation, explicit day initialization, original source-grounded numerical seams, old caps/pins/UNKNOWN, literal false authority and independent exact oracles.
- **Ask first:** approve this specification; separately authorize execution planning/implementation, new capacity/context/version policy, native/header/bytes/EOF/source access, full calendar/history/multi-session work and prospective complete-cohort registration.
- **Never in this window:** Python/source/test edits/imports/runtime tests/Ruff/examples/verifiers/native/model/training calls; raw/historical/reserved inputs or old packets/controls; network market data, dependencies, credentials/broker APIs or actual orders; Windows/security inspection/changes/bypasses; staging/commits/force pushes. Graphify scans/graphs are not released or needed. BTC/cloud collectors stay untouched. No late fill, UNKNOWN cancellation/reconciliation, reseeding/daily reset, successful-subset scoring, old-fill filtering or terminal-plan stitching. Disabled App Security is not an established fix.

**Human review choices:** approve or revise (a) this native-free invented event/37-feature scope, (b) fixed v3/AS_IS, parent/instrument_id, partial-empty/limit-None and explicit ts_out declarations, (c) original scalar representation/first-cursor/reset/capture semantics, and (d) the 1MiB outer /32-publication bounds with all inner caps held. Native wire/ABI/EOF/runtime authentication, historical feature-row parity/full capacity/calendar and one-genesis multi-session support remain separate later gates. No automatic training, scoring/promotion or profitability claim follows. Until direct approval, status remains **PROPOSED**; no implementation plan is written.

Source context: [decoded payload next gate](6E_DECODED_PAYLOAD_NEXT_GATE_20261011.md), [native cursor/publication design](6E_NATIVE_CURSOR_BRIDGE_NEXT_GATE_20261010.md), [current contract window](6E_TYPED_NATIVE_EVENT_ADAPTER_WINDOW_20261011.md).
