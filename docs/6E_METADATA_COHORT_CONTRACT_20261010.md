# Constructed metadata cohort contract

This is a closed **prospective design**, not source release, a historical reader or a completed experiment. Root must accept this document and independently release new implementation and tests. All current 408 Python files stay unchanged. Only invented in-memory metadata is allowed; no historical files, packets, prices, feature vectors, outcomes, accounts or calendars are read.

The smallest useful increment is a stdlib-only validator for a complete caller-declared inventory ledger and its exact first accepted train prefix. It can reject inconsistent metadata before a later, separately authorized reader touches rich data. It cannot establish that the supplied ledger is the real complete collection, authenticate an asserted source reference, or derive any of the 37 features.

## Fixed scope and bounds

New proposed module: `src/ai_trader/research/six_e_metadata_cohort.py`. Proposed tests are separate. No other source is changed or imported. The module may import Python standard-library modules only; no existing loader, synthetic funded walker, accounting, model, history, network, filesystem, process, wall clock, CLI or order hook.

Constants are exactly:

| Name | Value |
| --- | --- |
| `VERSION` | `six_e_metadata_cohort_v1` |
| `STATUS` | `constructed_metadata_consistency_not_provenance` |
| `MAX_INVENTORY_SESSIONS` | 16 |
| `MAX_SELECTED_SESSIONS` | 3 |
| `MAX_SELECTED_PUBLICATIONS` | 64 |
| `MAX_SESSION_PUBLICATIONS` | 14400 |
| `MAX_SESSION_QUOTES` | 2000000 |
| `MAX_SESSION_EVENTS` | 4000000 |
| `MAX_CANONICAL_BYTES` | 262144 |
| `MAX_INT` | 9223372036854775807 |
| `SECOND_NS`, `DAY_NS` | 1000000000, 86400000000000 |
| `WINDOW_START_SECONDS`, `WINDOW_END_SECONDS` | 43200, 57600 |
| `MIN_PUBLICATION_CADENCE_NS` | 1000000000 |
| `DECLARED_FEATURE_COUNT` | 37 |
| `SUPPORTED_CONTRACTS` | `("6EM5", "6EU5", "6EZ5", "6EH6")` |
| `ROLES` | `("train", "validation", "test", "reserved")` |
| `DISPOSITIONS` | `("decision_session", "degraded", "empty", "reconstruction_only", "reserved_metadata")` |

The small 16-ledger/3-selected/64-publication envelope is constructed acceptance scope, **not capacity for a historical session or the real inventory**. A larger declared input refuses completely. Do not select 64 rows from a real session or split it into artificial sessions to fit these bounds. Later historical support requires its own capacity and provenance contract. No quantity, monetary, execution, loss, cooldown or model parameter exists here.

All new dataclasses are frozen and slotted. Exact classes and exact field sets are required, not subclasses, dictionaries or duck types. Scalars are exact types: `int` excludes bool, `bool` is never inferred, tuples are exact `tuple`, strings exact `str`. Every field is revalidated even if a frozen object was poisoned or a field removed. Error: `MetadataCohortError(ValueError)`; deliberate malformed inputs, canonical encoding or arithmetic failures become this declared error, not a raw `TypeError`, `AttributeError` or `OverflowError`.

Identifiers match ASCII `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`. `cohort_id` and every `source_session` have `synthetic-` plus a nonempty suffix. Publication IDs use the same ASCII rule without the synthetic-prefix requirement. All SHA256 strings are exact lowercase 64-character hex. There are no paths, bytes of source events, floats or feature values.

## Exact input schemas

Each field order below is normative. Input constructors validate their own scalar metadata and tuple container shapes only; they do not traverse child objects. Full cohort validation supplies complete nested validation in the order below.

```text
InventorySession
  source_session: str
  utc_date: str
  role: str
  partition: str
  disposition: str
  contract: str
  source_sha256: str
  start_ns: int
  end_ns: int
  quote_count: int | None
  publication_count: int | None
  completed_event_count: int | None

PublicationMetadata
  publication_id: str
  source_session: str
  original_row_ordinal: int
  received_at_ns: int
  original_first_quote_cursor: int
  first_quote_received_at_ns: int
  preceding_quote_received_at_ns: int | None
  completed_event_cursor: int
  completed_event_received_at_ns: int
  completed_event_prefix_sha256: str
  completion_marker: str
  feature_publication_ref_sha256: str

SessionPublications
  source_session: str
  publications: tuple[PublicationMetadata, ...]

MetadataCohort
  cohort_id: str
  collection_registration_sha256: str
  collection_receipt_sha256: str
  source_schema_sha256: str
  feature_schema_sha256: str
  feature_derivation_sha256: str
  declared_feature_count: int
  declared_inventory_count: int
  declared_selected_count: int
  declared_publication_count: int
  inventory: tuple[InventorySession, ...]
  selected_session_ids: tuple[str, ...]
  selected_publications: tuple[SessionPublications, ...]
```

Registration, receipt, schemas, derivation and publication references are **opaque retained reference pins**. No referent is opened or checked. `declared_feature_count == 37` asserts the intended schema width, not that a vector or source actually contains 37 valid causal fields. There is deliberately no genesis, account, fee, margin, limit, row envelope, feature value, selected trade, prediction, outcome or submitted plan.

### Complete inventory semantics

Require 1–16 inventory entries, exact `declared_inventory_count == len(inventory)`, unique source-session IDs and unique canonical ISO UTC dates in chronological order. Dates must round-trip through stdlib `date.fromisoformat` and `isoformat`. Compute their UTC civil-day nanoseconds from the 1970-01-01 epoch using integer days; require nonnegative bounded timestamps. Every declared window is exactly that date's 12:00–16:00 UTC, `0 <= start_ns < end_ns <= MAX_INT`. This is arithmetic consistency with the fixed declared research window, **not an exchange-calendar, holiday, trading-date, DST, contract-expiry or source-timezone proof**. Never infer the correct contract from the date; only require membership in the fixed supported tuple.

Role and partition agree: `reserved` pairs only with `reserved`, every other role with `development`. Disposition agrees as follows:

| Disposition | Role/partition and complete count constraints |
| --- | --- |
| `decision_session` | nonreserved/development; `1 <= publication_count <= MAX_SESSION_PUBLICATIONS`, `publication_count <= quote_count <= MAX_SESSION_QUOTES`, `quote_count <= completed_event_count <= MAX_SESSION_EVENTS` |
| `degraded` or `reconstruction_only` | nonreserved/development; publication count exactly zero; quote count 0–MAX_SESSION_QUOTES; event count 1–MAX_SESSION_EVENTS; quote count <= event count |
| `empty` | nonreserved/development; all three counts exactly zero |
| `reserved_metadata` | reserved/reserved only; all three counts exactly null, not invented zero |

`reserved` is equivalent to `reserved_metadata` for this invented schema; no other reserved payload exists. Every entry still retains its source reference pin, dated-contract assertion and window. Excluded, empty, degraded, reconstruction-only and reserved metadata cannot be removed when calculating the ledger identity or disposition/role counts. Null reserved counts mean unknown/not exposed, not measured absence. A ledger containing no accepted decision session cannot satisfy a selected-prefix request.

Selection is **the exact first prefix of accepted `decision_session` entries in the complete supplied inventory**, not a filter for convenient train dates. Let `accepted_ids` be every such entry's source-session ID in original inventory order. Require 1–3 selected IDs and `selected_session_ids == accepted_ids[:declared_selected_count]`; require count equality and every selected entry to retain role `train`, partition `development`, disposition `decision_session`. A selected validation/test/reserved entry or skipped earlier accepted entry refuses. The unselected inventory retains every role/disposition. A forged role that differs from the original independently retained cohort pin refuses; a caller who coherently replaces all assertions and expectations is not detectable or authenticated.

### Complete selected publication assertions

`selected_publications` has exactly one bundle per selected ID, in the same order, and no unselected or reserved bundle. Bundle source IDs are unique and exactly equal to the selection. Each exact tuple has exactly its inventory publication count; their sum equals `declared_publication_count` and is 1–64. This rejects omissions, extra rows and successful-prefix coverage **relative to the asserted inventory**, not external completeness. Unselected ledger publication counts may exceed 64 because no such assertion payload is inspected here.

Publication IDs are globally unique across selected bundles. Source-session identity matches its bundle and inventory. `original_row_ordinal` is exactly zero-based contiguous tuple position; no duplicate or skipped row. Received timestamps satisfy `start_ns <= now < end_ns`, chronological order and at least one-second cadence inside each session. Native first-quote cursors strictly increase within the session and satisfy `0 <= cursor < quote_count`.

`first_quote_received_at_ns == received_at_ns`. For cursor zero, preceding timestamp is null. For any positive cursor it is a bounded exact int with `start_ns <= preceding_quote_received_at_ns < received_at_ns`. For each later publication in the same bundle, its preceding timestamp is at least the prior publication's received timestamp; when its first-quote cursor is exactly the prior first-quote cursor plus one, that preceding timestamp equals the prior publication's received timestamp. These are internal implications of the declared nondecreasing quote order. This structurally asserts that the immediately preceding quote is strictly earlier; a later equal-time cursor cannot be declared first while honestly retaining its immediate predecessor's same timestamp. There is no quote array to prove the assertion or inspect an equal-time suffix, and legitimate equal-time rows are not deduplicated.

Completed-event cursors are zero-based, strictly increase within a session, and satisfy `0 <= cursor < completed_event_count`. They also satisfy `original_first_quote_cursor <= completed_event_cursor`, the explicitly declared invented mapping assumption that each native quote consumes at least one ordered source completion. Between successive publications, the completed-event cursor delta is at least the first-quote cursor delta. At every publication, `completed_event_count - completed_event_cursor - 1 >= quote_count - original_first_quote_cursor - 1`, so the declared remaining events can contain all declared remaining quotes. These absolute, delta and suffix inequalities check internal consistency of the invented mapping, not the truth of event types or quote derivation. `completed_event_received_at_ns == received_at_ns`, `completion_marker == "asserted_F_LAST"`, and both event-prefix and feature-publication reference pins have valid syntax. These are received-time metadata assertions, not an event-time versus receive-time clock equivalence, original decoded flag verification or event-prefix recomputation. The 64 selected publication reference pins are neither feature vectors nor proofs that depth/trades/CVD/reload/absorption were derived from the stated prefix.

## Complete validation ordering

Every cohort-taking public assessment or hash call performs the following phases before producing any cohort body. `protocol_sha256()` has no cohort and only encodes/hashes the complete literal protocol under its canonical bound. Public verifiers additionally check their expected result pin's syntax in phase 1. No partial assessment is returned.

1. Validate all independently supplied expected-pin syntax before touching the cohort, then compare `expected_protocol_sha256`, when supplied, against the complete literal protocol identity before any cohort or publication access. Validate exact outer class and complete field access, all top-level reference-pin syntax, scalar/tuple container types and outer count bounds. Do not traverse publications.
2. Validate **all** inventory entry exact classes, fields, metadata, dates/windows, source pins, counts, role/partition/disposition and whole ordering/uniqueness. An invalid last session refuses here before any earlier `PublicationMetadata` object's field is read. Calculate the accepted prefix and check all selected IDs and complete declared selection counts.
3. Validate every bundle class/field, its source ID and exact tuple container/length, complete bundle ordering and total publication bound/count, still without reading a publication object's fields. Thus a wrong last bundle/count refuses before an earlier publication assertion.
4. Validate all exact publication objects and their complete scalar metadata/reference pins, identities, ordinals, times/cursors, previous-time assertions and within-session ordering. There is no later numeric price/vector/outcome phase.
5. Encode the complete canonical input and check its byte bound. `cohort_sha256` hashes that complete input body and stops, without building or enforcing an assessment body. For `assess_cohort` and `verify_cohort`, compare the independently retained expected cohort pin, then build the exact summary and complete result below; encode its full canonical body and enforce its separate applicable bound. No truncated or successful subset is acceptable.

An input hash call has no external expectation and performs complete input validation/encoding only. It must not fail solely because an assessment body's additional fields would exceed the cap. `protocol_sha256` likewise encodes/hashes only its complete literal protocol body. Assessment and verification enforce all applicable complete protocol, input and result body guards; exact equality passes for each independently enforced body. Full content hashes include every retained reference and later assertion; that does not make a future event or publication available at an earlier cursor. The module never computes, verifies or normalizes a rich feature vector.

## Pure APIs and canonical identities

```text
protocol_sha256() -> str
cohort_sha256(cohort: MetadataCohort) -> str
assess_cohort(
  cohort: MetadataCohort, *,
  expected_protocol_sha256: str,
  expected_cohort_sha256: str,
) -> MetadataAssessment
verify_cohort(
  cohort: MetadataCohort, *,
  expected_protocol_sha256: str,
  expected_cohort_sha256: str,
  expected_assessment_sha256: str,
) -> MetadataAssessment
```

All independent expectations must match, never be adopted or replaced. Verification rebuilds from the original complete cohort and compares its full result pin; it accepts no submitted assessment. No mutable protocol, partial cohort, future plan or externally supplied summary is trusted.

Canonical encoding is UTF-8 ASCII JSON using sorted keys, compact separators and `allow_nan=False`. Tuples become JSON lists; complete exact dataclass projections use `asdict`. SHA256 hashes the complete bounded bytes. All new canonical bodies use the 262144-byte runtime guard; equality passes, excess refuses completely. The declared protocol literal remains 262144 when a defensive test lowers the enforcement cap. There are no float coercions, datetime objects or source bytes in canonical bodies.

Protocol body has exactly these keys and literal values:

```text
version: VERSION
status: STATUS
bounds: {
  max_inventory_sessions: 16, max_selected_sessions: 3,
  max_selected_publications: 64, max_session_publications: 14400,
  max_session_quotes: 2000000, max_session_events: 4000000,
  max_int: 9223372036854775807, max_canonical_bytes: 262144
}
scope: {
  identifier_pattern: "[A-Za-z0-9][A-Za-z0-9_-]{0,63}",
  synthetic_prefix: "synthetic-", roles: ROLES, dispositions: DISPOSITIONS,
  partitions: ["development", "reserved"], contracts: SUPPORTED_CONTRACTS,
  selected_role: "train", selection: "first_accepted_decision_session_prefix",
  window_start_seconds: 43200, window_end_seconds: 57600,
  min_publication_cadence_ns: 1000000000, declared_feature_count: 37,
  completion_marker: "asserted_F_LAST",
  reference_scope: "opaque_assertions_not_source_or_feature_verification"
}
schemas: {
  InventorySession: [the complete twelve field names above in order],
  PublicationMetadata: [the complete twelve field names above in order],
  SessionPublications: ["source_session", "publications"],
  MetadataCohort: [the complete thirteen field names above in order],
  MetadataAssessment: [the complete twelve field names below in order]
}
authority_flags: AUTHORITY_FLAGS
```

The input body has exactly `version: VERSION`, `status: STATUS`, `protocol_sha256: protocol_sha256()`, `cohort: asdict(cohort)`. There is no source-pin runtime lookup. The declared reference pins are input fields, not fixed executable helper pins; the module uses no project helper.

Exact result fields, in order:

```text
MetadataAssessment
  version: str
  status: str
  protocol_sha256: str
  cohort_sha256: str
  cohort: MetadataCohort
  inventory_count: int
  selected_count: int
  publication_count: int
  role_counts: tuple[tuple[str, int], ...]
  disposition_counts: tuple[tuple[str, int], ...]
  assessment_sha256: str
  authority_flags: tuple[tuple[str, bool], ...]
```

Counts are exact lengths of the full retained ledger, selection and selected publication tuples. `role_counts` contains every `ROLES` entry in literal order, including zeros; `disposition_counts` every `DISPOSITIONS` entry likewise. The result retains the entire original cohort, including every excluded/reserved metadata entry and publication assertion. Its canonical body is full `asdict(result)` with only `assessment_sha256` removed. No true completion/provenance flag, calculated trade count, return, account state or richer-data permission is added.

`AUTHORITY_FLAGS` is exactly the alphabetically sorted tuple of these twenty names, each paired with exact `False`:

```text
accounting_admission_authorized
calendar_verified
cohort_externally_complete
collection_receipt_authenticated
event_prefix_verified
execution_authorized
feature_derivation_verified
feature_publication_verified
feed_authenticated
first_cursor_verified
historical_access_authorized
independent_validation
input_authenticated
metadata_assertions_authenticated
promotion_allowed
source_integrity_verified
source_runtime_verified
storage_resume_authorized
trading_enabled
training_enabled
```

Structurally consistent assertions remain assertions. No local metadata hash can authenticate an upstream source, externally retained complete receipt, calendar, feature prefix, full runtime graph or coherent replacement of all values and pins. An assessment is not the missing historical feature-proof seam, funded-path adapter or registration.

## Independent constructed acceptance

Require root and independent full-source/test review, manual literal protocol/input/result bodies and canonical pins, all focused/adjacent tests, Ruff/formatting and a fresh source-frozen complete suite before acceptance. No historical input is used to test this component.

- Construct a full ordered ledger with each disposition and every role, retain excluded and reserved metadata, and select exactly its first one-to-three accepted train sessions. Omitted/reordered/duplicate sessions, skipped accepted prefix, later-role selection, role/partition/disposition contradictions and wrong complete counts refuse.
- Poison the last inventory entry or last bundle while placing forbidden field-access sentinels in an earlier publication assertion. Demonstrate phase-2/3 refusal before publication fields, complete scalar/pin preflight, exact types/removed fields and complete class/tuple guards. No sentinel price/vector/outcome payload exists or is traversed.
- Construct nonzero first cursors, honest equal-time predecessor rejection, predecessor timestamps before a prior publication, wrong predecessor equality for adjacent first cursors, exact one-second cadence, source/session/ordinal mismatch, decreasing event/quote cursors, too-small event deltas or remaining-event suffix counts, malformed completion marker/prefix references and off-window timestamps. These test metadata consistency, not original event truth.
- Changing any excluded metadata, later publication or opaque proof reference changes the correct complete identity. The returned original earlier assertions are not normalized or rewritten, but no prior consumed-event digest or derived feature is claimed because neither is recomputed here.
- Match independently retained expected pins; wrong pins refuse without updating them. Rebuilding every full result field, exact role/disposition zero counts, all twenty false flags and the complete cohort is required; identical headline counts alone do not suffice.
- Measure a complete 16-inventory/3-selected/64-publication envelope and result with maximum identifier, pin, cursor and timestamp shapes that satisfy this contract. Cover exact/excess canonical limits and every input bound. Do not claim a universal maximum-size proof from that measurement or silently enlarge the cap.
- Prove stdlib-only imports and refusal of filesystem, process, network, source-file hashing, history, loader, clock, accounting, model, CLI and order hooks. No implementation reads richer data or grants permission to read it.

After this metadata gate, separate reviewed implementation still must bind genuine original event-prefix/feature-publication evidence, derive all 37 fields under declared causal-window/warmup/reset semantics, support complete historical-session capacity and original policy decisions, preserve one-genesis liabilities/UNKNOWN across sessions and independently rebuild the whole historical experiment under fresh registration. No automatic training, scoring, promotion or trading follows.
