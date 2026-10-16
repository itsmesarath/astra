# Constructed feature publication witness contract

This is a closed prospective contract, **not an implementation release or a historical experiment**. Root must accept the complete document, obtain independent review and separately release the new module and its tests. All 410 existing Python files remain unchanged. No original archives, retained packets, price rows, outcomes, model calls, accounts or orders are accessed.

Proposed module: `src/ai_trader/research/six_e_feature_publication_witness.py`. It reconstructs a complete, invented target-MBO prefix from an empty book and derives all 37 original causal feature values. It must not accept caller-supplied order pre-state, quotes, features, eligibility, event boundaries or publication cursors. This is a computed constructed witness, unlike the earlier opaque metadata-reference gate. It is not evidence that these invented records came from Databento or that any historical session has been witnessed.

## Fixed scope, dependencies and bounds

The module may use standard-library facilities and only the unchanged helper classes `StrictBook`, `Quote`, `FiveSecondFlow`, `OfiWindow`, `QuoteHistory`, `Record` and `ExecutionWindow` from the nine sources below. It may not instantiate any feature/target/replay builder, call a loader, read arbitrary files, access clocks, produce labels, invoke strategy/accounting/model/order hooks, or implement a CLI, storage or resume. Imports of those helpers transitively import existing modules; no import graph or native runtime is authenticated here.

Only nine fixed **implementation source** files may be read, solely to check their literal raw-file SHA256 values before accessing caller payloads. This is the sole filesystem exception. It must never follow caller paths or read data, logs, archives or outputs. Each source read is bounded to 1 MiB, refuses a symlink or non-regular file and checks stable compatible path/handle size, modification time and identity before and after reading. Windows path-versus-handle ctime is not compared; same-view handle stability and compatible fields remain checked. This is a cooperative local-filesystem check, not adversarial race freedom or proof that in-memory imported functions match those bytes. Resolve the fixed paths from the installed module's `research` directory, not caller cwd; no fallback source tree or configuration.

Constants are exactly:

| Name | Value |
| --- | --- |
| `VERSION` | `six_e_feature_publication_witness_v1` |
| `STATUS` | `constructed_feature_reconstruction_not_historical_provenance` |
| `UTC_DATE`, `CONTRACT`, `INSTRUMENT_ID` | `2025-04-07`, `6EM5`, `1` |
| `DAY_START_NS` | `1743984000000000000` |
| `WINDOW_START_NS`, `WINDOW_END_NS` | `1744027200000000000`, `1744041600000000000` |
| `WARMUP_START_NS`, `GENESIS_NS` | `1744027190000000000`, `1744027189999999999` |
| `SECOND_NS`, `FLOW_NS`, `WARMUP_NS` | `1000000000`, `5000000000`, `10000000000` |
| `MIN_PUBLICATION_CADENCE_NS`, `READINESS_END_BUFFER_NS` | `1000000000`, `17000000000` |
| `TICK_NANO`, `F_LAST` | `50000`, `128` |
| `MAX_RECORDS`, `MAX_COMPLETED_EVENTS`, `MAX_PUBLICATIONS` | `256`, `128`, `32` |
| `MAX_CANONICAL_BYTES`, `MAX_HELPER_SOURCE_BYTES` | `1048576`, `1048576` |
| `MAX_INT`, `MAX_SEQUENCE`, `MAX_SEND_DELTA` | `9223372036854775807`, `4294967295`, `2147483647` |

There must be at least three records, one post-genesis completed event and one decision-window publication. Every post-genesis completed event yields one observed quote, including warmup quotes, so observed-quote capacity is also 128. Counts are never truncated. Input or complete result exceeding any bound refuses the entire fixture, without a successful subset. These bounds do not accommodate a real session: never relabel historical records synthetic, thin them, split a real session into artificial fixtures or interpret this capacity as historical support.

This is explicitly **target-only invented record order**, not the full decoded daily-file stream. Its contiguous raw target-record ordinal, completed target-event ordinal, observed quote ordinal and publication ordinal are distinct. No ordinal is claimed to be an original DBN byte offset or full-file record cursor. Instrument mapping, date/contract/calendar truth and DBN decoding remain unverified. The fixed calendar-valid example date is only a constructed context.

## Exact public types and errors

All six new dataclasses are frozen and slotted. Exact classes and complete fields are required; no subclasses, duck inputs, dictionaries, arbitrary iterables or coerced values. Scalars use exact `str`, `int`, `bool` and `tuple` types; bool is not int. Input constructors validate their own metadata and container shapes only, without traversing another record or reading prices/sizes/order IDs. Every public call revalidates poisoned/deleted frozen fields in the phases below. Output constructors do not grant acceptance; verification rebuilds their entire content.

Identifiers match ASCII `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`. `fixture_id` and `source_session` must start `synthetic-` with a nonempty suffix. SHA256 strings are exact lowercase 64-character hex.

Declared error: `FeaturePublicationWitnessError(ValueError)`. Deliberate malformed input, helper refusal, source-file failure, conflicting expectation, canonical encoding, excessive complete body or nonfinite/arithmetic failure raises this error. Wrap `ValueError`, `TypeError`, `AttributeError`, `OverflowError` and `OSError` from public validation/replay as this error, preserving the cause; do not swallow process interrupts, silently return false, adopt partial outputs or retry. Failures publish no witness. `verify` returns `None` only on complete success.

Field order below is normative. Existing `clock.Quote` is the exact held quote class with `(ts_recv_ns, bid, ask, bid_qty, ask_qty)`; it is never supplied as input.

```text
ConstructedMboRecord
  record_ordinal: int
  instrument_id: int
  ts_recv: int
  ts_event: int
  ts_in_delta: int
  sequence: int
  action: str
  side: str
  flags: int
  price: int
  size: int
  order_id: int

FeatureWitnessFixture
  fixture_id: str
  source_session: str
  utc_date: str
  contract: str
  instrument_id: int
  records: tuple[ConstructedMboRecord, ...]

RecordAudit
  record_ordinal: int
  before: tuple[str, int, int] | None
  record_sha256: str
  preceding_prefix_sha256: str
  prefix_sha256: str

CompletedEventWitness
  event_id: str
  event_ordinal: int
  first_record_ordinal: int
  last_record_ordinal: int
  started_at_ns: int
  completed_at_ns: int
  quote_ordinal: int
  quote: clock.Quote
  prior_quote_gap_ns: int
  ofi_first_ts_ns: int
  inactivity_reset: bool
  execution_temporal_reset: bool
  execution_stale_spanning: bool
  prefix_sha256: str
  event_sha256: str

FeaturePublication
  publication_id: str
  publication_ordinal: int
  event_ordinal: int
  quote_ordinal: int
  received_at_ns: int
  quote: clock.Quote
  prefix_sha256: str
  event_sha256: str
  ofi_first_ts_ns: int
  prior_quote_gap_ns: int
  cvd: int
  known_trade_count: int
  unknown_trade_count: int
  ofi_total: int
  feature_values: tuple[tuple[str, float], ...]
  eligible: bool
  eligibility_reason: str | None
  publication_sha256: str

FeaturePublicationWitness
  version: str
  status: str
  protocol_sha256: str
  fixture_sha256: str
  fixture: FeatureWitnessFixture
  prefix_context_sha256: str
  record_audits: tuple[RecordAudit, ...]
  completed_events: tuple[CompletedEventWitness, ...]
  publications: tuple[FeaturePublication, ...]
  execution_audit: tuple[tuple[str, int], ...]
  terminal_prefix_sha256: str
  terminal_received_at_ns: int
  record_count: int
  completed_event_count: int
  quote_count: int
  publication_count: int
  authority_flags: tuple[tuple[str, bool], ...]
  witness_sha256: str
```

There are two input, three audit/publication and one complete-witness dataclasses. No unspecified field or extra type is permitted.

`RecordAudit.before` is the actual resting `(side, price, size)` retrieved immediately before applying this record. For genesis it is `None`; for T/F/N it can be an existing order if that ID actually exists, although T/F/N do not mutate the book. No caller-provided `before` is accepted. All audits have exactly the original record ordinal; no record is skipped. Source-record hashes are over the full `asdict(record)`, preserving its exact values.

Event ordinals are 1-based and contiguous after genesis. Quote ordinals are 0-based and contiguous over **all** warmup and decision-window completions. Each event's quote ordinal is its event ordinal minus one. Publication ordinals are 1-based and contiguous but may skip many quotes. Generated IDs are exactly `synthetic-completed-event-{ordinal:04d}` and `synthetic-feature-publication-{ordinal:04d}`. They never incorporate whole-input hashes or future suffix content.

Genesis is represented by its complete `RecordAudit` and consumed-prefix hash, **not** a `CompletedEventWitness`, quote or publication. Completed-event record ranges start at ordinal 2, are adjacent without overlap/gaps, partition every subsequent source record and end at an actual F_LAST. All completion/publication fields are derived, not supplied. At a quote/publication OFI has observed the quote, so `ofi_first_ts_ns` is non-null. `execution_audit` is the final `ExecutionWindow.audit` sorted lexically by string key, preserving keys with zero values; this helper audit need not count stale-excluded events as its `completed_events`. Actual event coverage is established separately by every event range.

## Whole-input preflight before numerical payload

Every fixture-taking public call uses this exact phase order. Protocol-only calls take no fixture.

1. Validate syntax of **all independently supplied expected pins** before touching fixture metadata; compare the expected protocol pin to the hash of the entire literal protocol. Validate literal helper-pin syntax and check all nine fixed source reads, plus held `clock.TICK == TICK_NANO`, `clock.FLOW_NS == FLOW_NS`, `clock.SECOND_NS == SECOND_NS` and `dbn.F_LAST == F_LAST`, before caller payload access. This is a used-source/constant guard, not full runtime authentication.
2. Validate the exact fixture class/complete fields, identifier syntax, literal date/contract/instrument, exact tuple count 3–256. Then validate **metadata for every record** before reading the price, size or order ID of any record: exact record class/fields; contiguous ordinals 1..N; matching instrument 1; timestamp/send/sequence integers and bounds; exact action/side/flags enums; all receive ordering; genesis identity; final F_LAST; complete event count limit. Detect an invalid last record before numeric traversal of the first. Record metadata validation never reads `price`, `size`, `order_id` or derives a feature.
3. Validate numerical payload for every record, then encode/enforce the **complete input body** and compare its whole fixture pin when an expectation was supplied. No helper reconstruction occurs before all supplied numerical payload passes. `fixture_sha256` ends here: it does not reconstruct a book, produce features or enforce output-body bounds. A structurally valid input hash is not a successful replay claim.
4. Only `replay`/`verify` reconstruct the entire prefix and all events/publications; enforce minimum/maximum derived counts, finite values, exact causal links, complete result encoding and result cap. No early publication or prefix is returned if a later book/event/count/result check fails. `verify` also validates submitted witness shape and canonical content only after complete independent original-input preflight/rebuild, comparing every field and every nested false flag, not supplied plan summaries.

Input metadata rules:

- Every record is target instrument 1; no foreign-ID record is ignored. All records use original supplied order. Receive times never regress; equal-time records remain in order. `sequence` is an integer in `[0, MAX_SEQUENCE]` but is **not sorted or asserted monotonic**. The supplied target ordinal is the ordering reference.
- Genesis is exactly ordinal 1, action R, side N, flags 128, timestamp/event `GENESIS_NS`, send delta 0, sequence 0; its numerical payload is exactly price/size/order ID 0. This one mandatory clear initializes an empty `StrictBook`. It is not a pending event.
- Every later record lies in `[WARMUP_START_NS, WINDOW_END_NS)`, has `0 <= ts_event <= ts_recv` and `0 <= ts_in_delta <= MAX_SEND_DELTA`. These are the original V2 protected-interval disagreement guards. Undefined timestamps, negative send deltas and exchange-event-ahead records refuse, with no correction, sorting or tolerance. The fixed genesis is also well ordered.
- Later actions are exactly A/C/M/T/F/N. A/C/M require side A or B; T/F permit A/B/N; N requires side N. Flags are exactly 0 or 128; no snapshot, reset, bad timestamp/book, TOB, MBP or exceptional closed-clear path exists. The restricted subset is explicit, not a weakening of the original guards.
- Later A/C/M/T/F prices are positive, on-grid integers at most `MAX_INT`; sizes are positive integers at most `MAX_INT`. A/C/M/F IDs are positive integers at most `MAX_INT`; T IDs allow 0..MAX_INT. N has price/size/order ID exactly 0. This deliberately refuses some broader original marker/fill encodings; it is a bounded constructed subset, not a general historical decoder.
- All records after genesis are at or after warmup start, so no partially captured event may straddle that boundary. An event starts immediately after the preceding F_LAST, includes every record through its first F_LAST and must end before window end. The final source record must have F_LAST. Do not close an incomplete suffix artificially.

Integers derived by sums across at most 256 records may exceed `MAX_INT`; they use exact Python arithmetic, are bounded by the supplied record count and input scalar limits, and must never be clipped. No aggregate quantity is recast as authenticated volume. Float conversion/finite checks must refuse a failure rather than alter a value.

## Normative causal reconstruction

Use new local helper instances, never a supplied old state. Initial state is empty `StrictBook`, `FiveSecondFlow`, `OfiWindow`, `QuoteHistory`, `ExecutionWindow`, `last_quote=None`, `watch_since=WARMUP_START_NS`, inactivity inactive and `next_publication=WINDOW_START_NS`. Apply the mandatory genesis through unchanged `StrictBook.apply`; record its derived before state and prefix head. All remaining records are processed once, in supplied order:

1. **Before applying each incoming record**, check the original inactivity timer. If inactivity is not already active and `record.ts_recv > watch_since + FLOW_NS`, replace OFI with a fresh `OfiWindow` and mark inactivity active. The strict greater-than boundary matters; a non-completing record can fire it. This reset does not clear FiveSecondFlow, does not change the actual previous completed quote and does not reset the prior-quote gap to zero. Record whether the timer fired anywhere within this event.
2. Derive `Record.capture(record, book)` before applying, including its actual prior resting order; append it to the current complete-event buffer. Call unchanged `StrictBook.apply(record)` for every record. Strict-book faults refuse the entire fixture. Capture every input record in its audit/hash chain. T/F/N do not mutate standing orders, but still belong to the complete event and can expose inactivity.
3. If F_LAST is absent, do not add signed flow, observe a quote, derive features or publish. At F_LAST, add every T in this enclosing event to `FiveSecondFlow` using **this F_LAST receive timestamp**, preserving known aggressor B positive, A negative and N unsigned. F volume is never counted as a second T. Clear pending trades only after this event completes.
4. Require the initialized final book to be two-sided, positive-quantity and strictly uncrossed; derive bid/ask/top quantities from the actual reconstructed order levels. Prices/spread must be on the 50,000-nano tick. A one-sided, locked or crossed completed state refuses rather than silently dropping a completion. This is the constructed subset's quote rule.
5. Save the old `last_quote`, derive prior quote gap (0 if none, otherwise current receive minus actual previous completion), and observe the quote through held `OfiWindow.observe`. Startup has a new OFI; after an inactivity replacement, reset `QuoteHistory` at this quote before observing it. `QuoteHistory.observe` must run on every warmup and decision-window quote. Clear inactivity and update `watch_since` to this completion; **do not** clear the old completed quote merely for inactivity.
6. Call unchanged `ExecutionWindow.complete(full_event_records, old_last_quote, quote, book)`. It resets its temporal state when last completion is absent or gap is strictly greater than 5 seconds, independently of OFI. It retains window equality. If the event itself spans strictly more than 5 seconds, execution metrics for that event are excluded, but its completed T flow remains observable in FiveSecondFlow. Record the computed temporal-reset/stale-span booleans. No fill is manufactured, and unlinked decreases/reload/absorption remain conservative proxies, not proven cancellations or hidden liquidity.
7. Assign this quote as `last_quote`. Return a completed-event witness for **every** completion, including warmup and equal-time suffixes, linked to its exact adjacent source-record range, consumed prefix, current quote and resulting OFI start. The event audit freezes now and is never changed by later records.
8. If completion receive time is at least `next_publication`, freeze a publication **immediately after this event**, before consuming any following equal-time source record. This is the first completed quote at the due timestamp. Derive all 37 values and readiness below, then set `next_publication=now+SECOND_NS`, irrespective of readiness. No publication is generated before window start, from a timer alone, at EOF or from standing quotes. A cadence-skipped event still updates every causal helper and retains its complete event witness.

The original feature hooks apply pending target outcomes before publication, but targets do not drive these feature values. This module omits all target/outcome hooks; it must not instantiate a target builder merely to obtain features. Original inactivity/book/flow/feature ordering above remains fixed. At EOF require no pending source-event/trade buffer; no artificial quote/timer/publication is added. Terminal receive time is exactly the last supplied record's timestamp.

Rolling expiry is always `< now - FLOW_NS`, so observations exactly five seconds old remain. OFI warmup equality passes. Initial clear/startup gives prior quote gap zero; inactivity retains actual prior quote gap. QuoteHistory resets when OFI resets, while FiveSecondFlow expires/adds only through its held API and is explicitly expired at each publication before the base values and microdepth absorption values are computed. OFI is also expired at each publication. These details must not be replaced by a generic all-helper reset.

## All 37 values and separate readiness

Feature names/order are exactly the 23 entries in held `microdepth.FEATURES`, followed by the 14 entries in held `execution.FEATURES`. The protocol retains the full literal list, never only a count or a digest:

```text
log_bid_qty, log_ask_qty, queue_imbalance,
normalized_ofi_5s, normalized_cvd_5s, log_known_trades_5s,
unknown_trade_fraction_5s, log_prior_quote_gap_ms,
log_bid_depth5, log_ask_depth5, depth5_imbalance,
bid_top_share5, ask_top_share5, bid_span5_ticks, ask_span5_ticks,
mid_change_5s_ticks, mid_range_5s_ticks, mid_travel_5s_ticks,
log_quote_events_5s, normalized_bid_reload_5s, normalized_ask_reload_5s,
buy_absorption_proxy_5s, sell_absorption_proxy_5s,
bid_passive_5s, bid_held_top_passive_5s, bid_linked_decrease_5s,
bid_unlinked_decrease_5s, bid_same_id_reload_5s, bid_other_id_reload_5s,
bid_same_id_net_refresh_5s,
ask_passive_5s, ask_held_top_passive_5s, ask_linked_decrease_5s,
ask_unlinked_decrease_5s, ask_same_id_reload_5s, ask_other_id_reload_5s,
ask_same_id_net_refresh_5s
```

Base eight reproduce `CostTargetBuilder._event_decision` without invoking it. For depth `D=bid_qty+ask_qty` and `K=flow.known+flow.unknown`, they are `log1p(bid_qty)`, `log1p(ask_qty)`, `(bid_qty-ask_qty)/D`, `2*ofi.total/D`, `2*flow.cvd/D`, `log1p(flow.known)`, `flow.unknown/K if K else 0.0`, `log1p(prior_quote_gap_ns/1000000)`. Then use held `QuoteHistory.features(book, flow.cvd)` for 15 and `ExecutionWindow.features(quote)` for 14. No numeric normalization, rounding or alternative formula is allowed. The sole representation adjustment is to promote an exact integer zero returned for `mid_travel_5s_ticks` by the held empty travel sum to `0.0`; no other integer, boolean, string or non-float value is coerced. Existing floats, including signed zero, are retained unchanged. The exact ordered tuple has 37 exact finite floats; zero signs/float representation are preserved by canonical JSON. Held helper schema tuples must exactly equal the literal protocol feature list/subsets.

Compute every value before readiness, even if ineligible. `eligible` is exactly `eligibility_reason is None`. Reason precedence is exactly:

1. `spread_not_one_tick` if spread is not one tick;
2. `insufficient_feature_warmup` if OFI first timestamp is later than `now-FLOW_NS`;
3. `insufficient_window_for_hold` if `now+READINESS_END_BUFFER_NS >= WINDOW_END_NS`;
4. otherwise `None`.

The end-buffer reason preserves the original metadata-based readiness rule; it does not produce a hold, future target, order or outcome. Do not claim strategy selection or profitability from eligibility.

## Complete canonical identities and protocol

Canonical bytes are UTF-8 `json.dumps(..., ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)`. Dataclass bodies use full `asdict`, tuples become JSON arrays, numeric values are not coerced, and every complete applicable body must be at most 1 MiB. SHA256 hashes these exact canonical bytes. The complete body includes all nested fields and flags; estimates, selected sections and excluding inconvenient fields do not establish acceptance. Exact cap is allowed; excess refuses. `fixture_sha256` enforces only the complete input body; it must not fail merely because later result overhead exceeds its own cap.

The literal protocol body is exactly the following mapping. `constants` includes every fixed constant from the table; `feature_names` is the literal 37-entry list above; `source_pins` is the sorted nine-pair list below; `authority_flags` is the exact ordered list below. Schema field lists are exactly those above in normative order. No derived current timestamp, actual file size, runtime version, complete input count or caller value appears in the protocol:

```text
{
  "version": VERSION,
  "status": STATUS,
  "scope": "constructed_target_mbo_prefix_only",
  "constants": {all fixed table constants by their exact uppercase names},
  "schemas": {
    "ConstructedMboRecord": [its complete ordered field names],
    "FeatureWitnessFixture": [its complete ordered field names],
    "RecordAudit": [its complete ordered field names],
    "CompletedEventWitness": [its complete ordered field names],
    "FeaturePublication": [its complete ordered field names],
    "FeaturePublicationWitness": [its complete ordered field names]
  },
  "feature_names": [all 37 literal names in their exact order],
  "source_pins": [[relative source path, lowercase raw SHA256], ...],
  "identifier_templates": {
    "event_id": "synthetic-completed-event-{ordinal:04d}",
    "publication_id": "synthetic-feature-publication-{ordinal:04d}"
  },
  "readiness_reasons": ["spread_not_one_tick", "insufficient_feature_warmup", "insufficient_window_for_hold"],
  "authority_flags": [[name, false], ...]
}
```

This mapping notation references the complete explicit tables/lists, not optional placeholders. The implemented protocol must expand every field/table/list exactly; independent tests build an entire literal expected mapping and hash, not copy implementation output.

Input body is exactly `{"version": VERSION, "protocol_sha256": protocol_sha256(), "fixture": asdict(fixture)}`. Its hash is the whole fixture pin. No partial context hash substitutes for it.

The consumed-prefix seed body is exactly:

```text
{
  "version": VERSION,
  "protocol_sha256": protocol_sha256(),
  "fixture_id": fixture.fixture_id,
  "source_session": fixture.source_session,
  "utc_date": fixture.utc_date,
  "contract": fixture.contract,
  "instrument_id": fixture.instrument_id,
  "record_schema": [all ConstructedMboRecord field names in order],
  "source_pins": [all nine literal source path/pin pairs]
}
```

Its hash is `prefix_context_sha256` and the preceding prefix for record 1. For each record, its full source-record hash is `H(asdict(record))`; next prefix is exactly `H({"preceding_prefix_sha256": previous, "record_ordinal": ordinal, "record_sha256": record_pin})`. Record audits retain all three pins and actual before state. Every completed event binds its ending prefix. Its `event_sha256` hashes its entire `asdict` body excluding **only** its own `event_sha256` field. Every publication binds that event pin and ending prefix; `publication_sha256` hashes its complete body excluding only its own digest. Future records cannot change earlier record/event/publication heads under identical metadata/protocol/helpers/consumed prefix.

Do **not** seed prefix identities with the complete fixture pin, total record/event/publication counts, declared end-of-prefix timestamp, complete result, future prices or eventual terminal state. Those are future-suffix identity, not information consumed at a publication. Outer `fixture_sha256` and full result identity still change when the suffix changes. Compare earlier causal scalar values and consumed-prefix/publication/event digests, not the whole result or fixture identity, for suffix-invariance acceptance.

Result body is exactly full `asdict(witness)` excluding only `witness_sha256`. It retains the **entire original fixture**, every record audit, every completed event, every publication's all-37 values, full final helper execution audit, terminal prefix/time/counts and all false flags. Its hash is `witness_sha256`. Terminal prefix must equal the last record audit, counts must equal complete tuple lengths, quote count equals completed event count, and the last event range must end at the final record. No abbreviated result is acceptable.

### Literal nine-source pins

Sorted by the literal relative path; all must be checked on every fixture-taking public call:

```text
src/ai_trader/research/databento_6e_cost_targets.py
  ebc4c1dc0a44e71362cd96bed0a699dac6ebc04a66fc7f568d2bf4898d427b2b
src/ai_trader/research/databento_6e_event_scalp.py
  48bd0402c2e8a7c0d8d286b8956a2f55059c71df81dc1115ee15d8adce560b3e
src/ai_trader/research/databento_6e_execution_flow.py
  7f777a19518378dd3b2a0371b7f3ddcf3077f51555faffa5e589de6255239b75
src/ai_trader/research/databento_6e_microdepth.py
  8964b20a5de8104a0f7831cf827c1c736f3c11b6a2d61dbe0206521ee3b451c4
src/ai_trader/research/databento_6e_ofi_scalp.py
  05cade0f206c06cbea93198c9fb92e591c0275ef5ac70f8ce50bcb000ad0ff24
src/ai_trader/research/databento_6e_receive_clock.py
  351b4b54fc3ac4ac905ebdbb9725f270288ac235178cb50180e2040d8fef4636
src/ai_trader/research/databento_6e_scenario_replay.py
  d5bf8e3e0ec4b1957f1a2a7ed515f1cf9530b922e5c2c3929389ed0bfeab91ff
src/ai_trader/research/databento_6e_seconds_pilot.py
  7c295b7cc3875a6955d3582368a7d28804dd318e061e0d0b3906e4a21e411b2b
src/ai_trader/research/databento_6e_training_data.py
  9d1c9190da304031113880dbfb4d002121908d35b6bc52671a65939a6e7049a3
```

These include directly used classes, their numerical schema/formula sources and the two normative timer/receive-clock sources. They are not the earlier 40 replay genesis identities, 47 operator identities, metadata gate protocol or full import/native dependency graph. No new module self-hash appears inside its own protocol. Root's separate complete source/test freeze binds the actual implementation for acceptance.

### Twenty false-authority flags

The exact tuple is lexically ordered and every value is exact `False`:

```text
accounting_admission_authorized, calendar_verified, cohort_externally_complete,
collection_receipt_authenticated, event_prefix_verified, execution_authorized,
feature_derivation_verified, feature_publication_verified, feed_authenticated,
first_cursor_verified, historical_access_authorized, independent_validation,
input_authenticated, metadata_assertions_authenticated, promotion_allowed,
source_integrity_verified, source_runtime_verified, storage_resume_authorized,
trading_enabled, training_enabled
```

These broad authority names remain false even when invented features are correctly recomputed. Computed target-only source ordering is not authenticated full-file provenance; helper byte checks are not authenticated feed or runtime execution. A coherent replacement of caller fixture plus expectations is not detectable authentication. No field is promoted from false because a synthetic example agrees with itself.

## Public API and complete verification

```python
def protocol() -> dict: ...
def protocol_sha256() -> str: ...
def fixture_sha256(fixture: FeatureWitnessFixture, *,
                   expected_protocol_sha256: str) -> str: ...
def replay(fixture: FeatureWitnessFixture, *,
           expected_fixture_sha256: str,
           expected_protocol_sha256: str) -> FeaturePublicationWitness: ...
def verify(witness: FeaturePublicationWitness,
           fixture: FeatureWitnessFixture, *,
           expected_fixture_sha256: str,
           expected_protocol_sha256: str,
           expected_witness_sha256: str) -> None: ...
```

Protocol calls only canonicalize the complete literal protocol; they do not take caller payloads or check runtime/helper files. All fixture-taking calls perform the independent expectation/source/metadata/numeric phases above. `fixture_sha256` returns the complete input pin and stops. `replay` compares that pin before constructing any helper state, rebuilds from mandatory R and returns one complete witness. `verify` checks **all three independent expected-pin syntaxes first**, checks the complete protocol and original fixture/source guards, performs the same full independent reconstruction, then requires exact expected witness digest, exact witness type/full field set, complete canonical body equality with rebuilt output and all nested identities/flags. It never seeds reconstruction from submitted event/publication/audit state. Tuple/dataclass exactness must be checked in the submitted output as well as canonical equality, so list-versus-tuple, subclass, int-versus-bool and missing fields do not pass solely through JSON equivalence.

No supplied witness can authorize historical access or feed a funded walker automatically. A later separately reviewed bridge would need actual original source decoding/mapping, complete authentic session/calendar scope, original row parity and new source-bound event/publication capture, followed by independent complete verification. The current original retained whole-day row/source-EOF/quote conservation evidence does **not** contain these event-prefix witnesses; do not manufacture them from L1 quote columns or opaque metadata hashes.

## Independent acceptance before any historical bridge

Use only invented fixtures. Independent tests must manually build complete expected protocol/input/result mappings, per-record prefix hashes, before states, event ranges/cursors, all-37 publication values and audits; do not call new private builder/hash helpers for expected outputs. Held pure helpers may supply a separately stated parity check, but parity alone is not an independent numeric oracle.

Required constructed coverage includes deep top-five book derivation; signed/unknown T and separate matched/unmatched F; strict add/modify/cancel/reprice faults; same-ID/other-ID reload and net refresh; mirrored flow and absorption; original one-second cadence; first equal-time completion exclusion and consumed-prefix suffix invariance; warmup/rolling/inactivity/end-buffer exact and adjacent boundaries; timer firing on a non-completing record; 5-second spanning execution equality versus exclusion while completed T stays in CVD; missing reset/two-sided quote/incomplete event/bad protected clocks; poisoned final metadata before earlier numeric traversal; every source pin/drift/constant refusal; full nested audit/digest/type/flag tampering; zero/default signed representations; complete count and input/result byte cap exact/excess behavior.

Measure complete canonical 256-record/128-event/32-publication capacity fixtures, including maximum identifier lengths and finite-large scalar values that retain coherent strict-book/event arithmetic. A measured fixture is not a universal maximum proof. Reconcile every constructed case, source/test snapshot and complete project suite with unchanged 410-file baseline before acceptance. No success claim from progress dots, selected rows, partial result, a single example or headline accuracy.

No implementation, tests or example have run under this contract yet. Historical, source-authenticated, calendar, full-session, account, execution, storage/resume, trading, training, independent-validation and promotion gaps remain separate. BTC/cloud collectors and all old sources, targets, outcomes and UNKNOWN liabilities are untouched.
