# Constructed decoded cursor metadata contract

## Status and release

This prospective contract closes the smallest metadata-only increment from the reviewed native-cursor design. It releases no historical input, native decoder, numerical feature replay or strategy integration. All 412 preceding Python source/test files remain immutable. Root may release only `src/ai_trader/research/six_e_native_cursor_metadata.py` and independently authored `tests/test_six_e_native_cursor_metadata.py` after complete independent review of this contract. Runtime acceptance is pending.

The component is stdlib-only, has no filesystem reader/writer, CLI, account, native/project-helper import, order, model, history or resume hook. Only invented in-memory fixtures are accepted. The output status is exactly `constructed_decoded_cursor_metadata_not_native_verification`.

## What is checked

Complete declared header, day, mapping and ordered decoded-item assertions are validated. Every decoded position, including the header and foreign items, receives a complete disposition and chained identity. A mapped-target occurrence is a **target candidate**, not an original successful book transition. The old engine increments its accepted target counter after successful `book.apply`; this component never applies a book.

It does not accept timestamps, flags, actions, sides, price, size, order IDs or decoded record bodies. An item payload SHA256 is an opaque caller assertion, not a checked hash of a DBN record. Consequently foreign payload assertions are retained without any target clock/timer/event operation; this is classification, not proof of the native engine's foreign-poison behavior. Header/mapping values and a member SHA256 are also assertions. No source authentication, native decoding, complete EOF, calendar, first publication, feature derivation, historical capacity or strategy validation is established.

Original inspected mapping checks exact dataset/schema/parent/day bounds and one active end-exclusive dated-target interval; it does not reject unrelated mappings wholesale. This constructed transport is deliberately narrower: fixed invented date/contract, exact primitive types, bounded ASCII names/dates and ASCII decimal active IDs. These are new declared validation rules, not complete original-loader parity.

## Fixed protocol

Version `constructed_decoded_cursor_metadata_v1`; scope `invented_header_mapping_and_decoded_item_assertions_only`. Calendar examples are fixed to UTC date `2025-04-07`, contract `6EM5`, day start `1743984000000000000` and end `1744070400000000000`. They are calendar-valid examples, not authenticated exchange calendar claims. Dataset `GLBX.MDP3`, schema `mbo`, symbols exactly `('6E.FUT',)`, not_found exactly empty tuple.

Limits: 2 through 128 complete decoded items including the header; 1 through 8 mapping groups; each group 0 through 16 intervals; at most 32 intervals across all groups; 65,536 bytes for each complete canonical fixture and result body. Integer IDs are exact ints in [0, 4,294,967,295]; bools and subclasses refuse. Name fields are exact ASCII strings of 1 through 64 characters matching `[A-Za-z0-9._:-]+`; fixture_id and source_session additionally match `synthetic-[A-Za-z0-9._:-]+`, with a nonempty suffix. Mapping keys and instrument symbols are 1 through 32 such characters. Dates are exact canonical ASCII ISO dates in [2000-01-01,2100-12-31], strictly start < end. Every supplied pin is an exact lowercase ASCII 64-character hex string. No coercion, sorting of sequences, normalization, filtering, trimming, truncation or deduplication.

Protocol returns a fresh dict with exactly version, scope, status, utc_date, contract, dataset, schema, symbols (JSON list), not_found (empty JSON list), day_start_ns, day_end_ns, max_items, max_mapping_groups, max_intervals_per_group, max_total_intervals, max_body_bytes, max_instrument_id, decoded_position_origin (1), target_candidate_ordinal_origin (1), header_included (true), payload_pins (opaque_caller_assertions), prefix_complete_member_pin (excluded), authority_flags (dict below). Enforcement and literal protocol identity must not depend on mutable exported constants or a caller-mutated returned dict. In-memory code/function replacement is outside authentication claims.

## Exact frozen slotted dataclasses

All containers are exact tuples; all dataclasses are exact types, frozen and slotted. Constructors retain values without coercion; public fixture APIs perform complete validation. Objects with subclass types, extra fields or poisoned/missing fields refuse with ValueError rather than accepting a partial result. Field names/order:

1. `MappingInterval(start_date, end_date, instrument_symbol)`.
2. `MappingGroup(contract, intervals)`.
3. `DeclaredHeader(dataset, schema, symbols, not_found, start_ns, end_ns, mappings)`.
4. `DecodedItem(decoded_position, kind, instrument_id, payload_sha256)`.
5. `CursorFixture(fixture_id, source_session, utc_date, contract, header, asserted_member_sha256, declared_item_count, items)`.
6. `CursorAudit(decoded_position, disposition, instrument_id, target_candidate_ordinal, item_sha256, prefix_sha256)`.
7. `CursorAssessment(status, protocol_sha256, fixture_sha256, fixture, mapped_instrument_id, decoded_item_count, target_candidate_count, foreign_count, audits, authority_flags, assessment_sha256)`.

Header start/end are exact ints equal to fixed daily bounds. Mapping keys are unique in supplied order. All interval declarations, including unrelated and inactive intervals, must meet transport rules. Intervals in a group retain supplied order; overlapping unrelated/inactive declarations are not sorted or blanket-rejected. The requested `6EM5` group must exist with exactly one interval active at the fixed day (`start_date <= day < end_date`). Only that active interval requires an ASCII all-decimal instrument_symbol, whose int value falls within the ID bound. Leading zeros are retained in the complete header and context identity while mapping to the corresponding integer. Inactive/unrelated symbols may be nondecimal within the name grammar. Repeated interval assertions are retained; if they make two requested active intervals they refuse.

The items tuple has exactly declared_item_count elements. Position 1 is the sole kind `metadata`, with instrument_id and payload_sha256 both exactly None. Every later position is kind `mbo`, with exact bounded ID and opaque pin; unexpected types/kinds or later metadata refuse. Positions must equal one-based supplied tuple order, including header; zero, gaps, repeats and reordering refuse. At least one MBO must match the mapped target ID. Repeated payload pins are allowed and do not imply duplicate native messages.

## Validation order and complete bodies

Expected protocol and fixture pin syntax are checked before fixture traversal; protocol equality is checked before fixture traversal. Then validate exact fixture/header/mapping/item types, scalar declarations, containers, all field constraints and counts for the **entire** fixture. This metadata-only API has no numerical payload traversal; do not claim a price-access phase. Missing/poisoned fields are normalized to ValueError. Validate every expected pin even if a preceding one is wrong. No result is returned for a bad suffix or overflow.

Project primitive bodies explicitly in the field order above; dataclass identity is retained by exact type checking, not JSON alone. JSON projection uses mappings as lists of {contract,intervals}, intervals as lists of {start_date,end_date,instrument_symbol}, items as lists of {decoded_position,kind,instrument_id,payload_sha256}, and header/fixture as dicts with exactly their declared fields. Canonical JSON is `json.dumps(ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')`. No newline. SHA256 is raw canonical bytes. Check the full fixture body bound before SHA acceptance and full assessment body bound before returning. Equality to the cap passes; greater refuses. A private `_bounded_canonical(value)` guard must enforce this exact byte rule and be shared by both complete bodies. Independent tests may call that guard with hand-constructed boundary JSON, without claiming those arbitrary bodies are valid fixtures or that public fixtures attain the universal maximum. Resource bounds do not authorize thinning/splitting historical data.

## Causal cursor identities

Fixture SHA256 binds the complete fixture body, including asserted member pin, total declared count and all items. The prefix seed is SHA256 of canonical `{protocol_sha256, fixture_id, source_session, utc_date, contract, header}`. It deliberately excludes asserted_member_sha256, declared_item_count, whole fixture pin, terminal counts and future items. The entire header/mapping is known declared context, not an incrementally discovered price stream.

For each item in original order, item_sha256 is SHA256 of its complete canonical item body. The next prefix is SHA256 of canonical `{previous_prefix_sha256, item}`. The header at position 1 is included in this chain. An audit has exactly the fields above. Its disposition is `header`, `foreign` or `target_candidate`. Header audit ID and candidate ordinal are None. Every foreign audit retains its ID with candidate ordinal None. Every mapped MBO receives consecutive one-based target_candidate_ordinal. These ordinals prove only mapped occurrences within this constructed assertion stream.

With identical protocol, fixture identifiers, header/mapping and consumed items, a changed future suffix or complete-only member assertion changes complete fixture/result identities but preserves preceding item/prefix hashes. Changing foreign data before the cursor changes decoded-prefix identity even when mapped target candidates are unchanged. Inserting an item before a cursor changes its decoded position and identity. No complete-member hash is used to seed earlier causal prefixes, and no byte offset is emitted.

## Assessment and verification

Assessment fields retain the original complete frozen fixture, all item audits, mapped ID and complete counts: decoded count includes header, target count includes every mapped MBO, foreign count includes every other MBO; decoded_item_count == 1 + target_candidate_count + foreign_count. `authority_flags` is an exact tuple of alphabetically sorted (name, False) pairs for every flag below. Body projection contains every assessment field except assessment_sha256; fixture is the complete projected fixture, audits are complete projected audit dicts and flags project to a dict. Assessment SHA256 binds that complete canonical body. There are no omitted audit items or summary-only results.

Public APIs:

- `protocol()` and `protocol_sha256()`.
- `fixture_sha256(fixture, *, expected_protocol_sha256)` validates completely and returns its complete pin.
- `assess(fixture, *, expected_fixture_sha256, expected_protocol_sha256)` validates, compares the complete input pin and returns the complete assessment.
- `verify(assessment, fixture, *, expected_fixture_sha256, expected_protocol_sha256, expected_assessment_sha256)` validates all expected pins before traversal, reconstructs the whole expected assessment from the original fixture and compares every exact field/type/body/pin/flag. It returns None only on success. It never adopts submitted audit heads, counts, mapped IDs or asserted source evidence as independent truth.

Verification must reject bool/int aliases, malformed nested types, wrong/extra/missing flags, tampered fixture/audit/count/status/digest and container substitutions even when JSON comparisons alone would look equal. Comparison includes every complete canonical field and exact nested types. Deterministic rebuilding is not authentication of a coherent replacement of fixture and expected pins.

## False authorities

Exactly these 26 names, all False: account_authenticated, book_application_verified, broker_economics_measured, byte_offsets_verified, calendar_authenticated, decoded_source_authenticated, event_closure_verified, execution_allowed, feature_derivation_verified, funding_authenticated, historical_access_allowed, historical_validation_allowed, mapping_authenticated, model_call_allowed, native_decoding_verified, native_eof_verified, native_target_ordinals_verified, promotion_allowed, publication_cursor_verified, runtime_authenticated, scoring_allowed, source_authenticated, storage_resume_allowed, strategy_integration_allowed, trading_enabled, training_allowed.

## Independent acceptance

Independent tests must hand-project literal protocol/fixture/audit/result bodies and chain hashes rather than use production serializers for expected values. Cover mapped ID other than 1; start-date equality/end exclusivity; absent/zero/two active requested mappings; unrelated/inactive declarations; exact type/ASCII/date/ID/container/pin/count/bounds refusals; metadata position/kind/None semantics; mapped candidates versus decoded positions; repeated payload assertions; complete header/foreign binding; future suffix/member-pin invariance; every result field and flag tamper; deterministic whole reconstruction and cap equality/overflow without partial acceptance. There is no foreign F_LAST test because this API contains no F_LAST field.

Root alone launches focused, adjacent, Ruff and complete suites after stable independent source/test review. Original 412 hashes must stay unchanged. Complete suite acceptance requires all 8,809 preceding ordinal JUnit identities and exactly the independent new focused identities, exact prior skips/reasons, zero failures/errors, matching owned-process exit and unchanged whole/new/old/package/contract/manifest pins. All tests and implementation must fit the original 12:30:08 UTC deadline.
