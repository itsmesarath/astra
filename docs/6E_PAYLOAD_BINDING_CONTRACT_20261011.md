# Proposed constructed record-payload binding contract

## Status, objective and approval gate

**PROPOSED SPECIFICATION; UNIMPLEMENTED.** This document fixes draft choices for human review, not implementation authority. The user authorized an offline four-hour **contract** window from **2026-10-11T11:01:40Z** to **15:01:40Z, 16:01:40 Lisbon**. All 414 accepted Python source/test files, preceding closed contracts and old inputs/results remain immutable. No staging or commits.

No new source/test file, import, test, example, verifier, decoder, historical input or network call is released. Following the installed `spec-driven-development` workflow, root presents the specification for human approval and stops before implementation planning, tasks or code. Approval of this specification alone does not release source, native or historical work in this contract-only window.

The objective is to independently recompute each complete **invented MBO JSON body** pin, match every retained target and foreign cursor item, reconstruct unchanged cursor metadata and retain explicitly contextual causal identities. Completion of this request means a complete, internally consistent, independently statically reviewed specification that the human can approve. It does not mean implemented behavior, runtime acceptance, native decoding or historical validation.

## Scope, existing structure and dependency

The proposed pure in-memory component may eventually use the standard library plus the unchanged public interface of `ai_trader.research.six_e_native_cursor_metadata`. Its held source metadata pin is `c7bc0102073fa61f1d69411479331cf1e434616cb80faa6bbc266377745dcf91`. This is one used-helper identity, not authentication of the complete import/runtime graph. No runtime filesystem reader is proposed to authenticate that pin.

The old literal cursor protocol, fixed invented `2025-04-07`/`6EM5` declarations, mapping rules and candidate semantics stay unchanged. Its payload pins retain their original opaque-assertion meaning; this separate layer adds checked constructed-body binding. Do not change the old module, widen its guards, relabel a mapped instrument as 1 or coerce an invented genesis/window into the feature witness.

Proposed later paths are `src/ai_trader/research/six_e_record_payload_binding.py` and `tests/test_six_e_record_payload_binding.py`. Neither is created or released now. The existing `docs/6E_*` contract convention is retained rather than creating a second generic `SPEC.md` or task-plan convention.

There is no native import, reader/writer, CLI, book, timer, flow, event, feature-publication, account, order, model, history or resume hook. No native ABI, original wire-byte/offset/EOF, broker or strategy claim follows from checked JSON consistency.

## Literal protocol and constructed limits

Version is exactly `constructed_record_payload_binding_v1`; scope is exactly `invented_complete_mbo_json_bodies_and_contextual_cursor_binding_only`; status is exactly `constructed_record_payload_binding_not_native_verification`.

Context has exact `codec_id` `constructed_mbo_json_v1`, exact integer `schema_version` 1 and exact string `ts_out_mode` `absent` or `present`. These name a constructed JSON representation only. Native input version, decoder upgrade policy, complete native header, stypes, partial/limit and native `ts_out` metadata are **not** declared or authenticated by this context.

There are 2 through 128 complete positions including the header, with at most 127 MBO payloads. The unchanged old mapping limits and **65,536-byte complete old fixture and assessment caps** remain independently enforced. Each new complete bundle and result body has a **262,144-byte** canonical cap. Equality passes; greater refuses. No larger new cap overrides an old refusal.

Every limit is constructed, not historical capacity. Never truncate, thin, split, relabel or deduplicate history to fit. Public-fixture capacity has not been measured for this unimplemented layer.

All new dataclasses are exact frozen/slotted types, every field is required and constructors retain supplied values without normalization or defaults. Containers are exact tuples. Bool/int aliases, subclasses, dictionary/list substitutions, missing or poisoned slots and unsupported fields refuse.

Declared integer domains are deliberately **not native widths**:

| Fields | Exact constructed integer domain |
| --- | --- |
| `instrument_id` | 0 through 4,294,967,295, inherited from the old item transport |
| `publisher_id`, `order_id`, `size`, `flags`, `channel_id`, `sequence`, `rtype` | U64: 0 through 18,446,744,073,709,551,615 |
| `price`, `ts_event`, `ts_recv`, `ts_in_delta`, present `ts_out` | S64: -9,223,372,036,854,775,808 through 9,223,372,036,854,775,807 |
| `record_size` | 1 through 65,536 |

`action` and `side` are exact one-character strings with ASCII codepoint 0 through 127, including escaped controls. No enum semantic acceptance or whitespace trimming is performed. Target and foreign records obey identical structural rules. Negative/zero prices, negative or nonmonotone clocks and unusual structural flags/actions/sides/sizes are retained within these domains, not labelled book-valid. Out-of-domain values refuse the whole result; no coercion, float conversion, sentinel replacement or arithmetic normalization.

## Exact field order and positional coverage

The five new frozen/slotted dataclasses have exactly these required fields in this order:

1. `PayloadContext(codec_id, schema_version, ts_out_mode)`.
2. `MboPayload(publisher_id, instrument_id, ts_event, order_id, price, size, action, side, ts_recv, flags, channel_id, ts_in_delta, sequence, ts_out, rtype, record_size)`.
3. `PayloadBundle(context, cursor_fixture, payloads)`.
4. `PayloadAudit(decoded_position, disposition, instrument_id, target_candidate_ordinal, payload_sha256, cursor_item_sha256, cursor_prefix_sha256, bound_prefix_sha256)`.
5. `BindingAssessment(status, protocol_sha256, context_sha256, cursor_protocol_sha256, cursor_fixture_sha256, bundle_sha256, bundle, cursor_assessment, audits, authority_flags, assessment_sha256)`.

Cursor fields retain exact old dataclass types. The payload tuple length equals the complete old items tuple and declared count. Position 1 is exactly `None`; every later position has exactly one `MboPayload`, including every foreign occurrence. Position is tuple index plus one and the corresponding old item's decoded position; there is no independent payload position field. Repeated equal bodies remain separate occurrences, not duplicate-message evidence.

Each payload's instrument ID must equal its corresponding old item ID after payload-value validation. The `ts_out` field always exists: exactly `None` under `absent`, or exact S64 integer under `present`. Never default it to zero or infer the mode. `rtype` and `record_size` are structural declarations, not verified native type/header size or equality with JSON byte length.

## Primitive projections and complete identities

Canonical JSON is `json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')`, with no newline. `H(value)` denotes lowercase SHA256 of those bytes. Use explicit field-by-field projection; exact dataclass/type identity must be checked independently of JSON equality.

The context body contains exactly its three named fields. `C = H(context_body)`. A payload body contains exactly all sixteen named fields, including explicit `ts_out`; `P_i = H(payload_body)`. Do not put context, position, complete member or complete bundle in this raw constructed body pin. The corresponding old item payload pin must equal `P_i` at each MBO. New contextual identities below bind the interpretation context separately.

The complete bundle body is exactly `{context: <complete context body>, cursor_fixture: <complete old fixture projection>, payloads: [null, <every complete payload body in order>]}`. Its SHA binds the complete canonical body after the new cap. The old fixture and assessment caps remain independently enforced.

The complete result body contains every `BindingAssessment` field except `assessment_sha256`: the entire bundle, the entire reconstructed old cursor assessment **including its own `assessment_sha256`**, every new audit and every false flag. Flags project to a dictionary; tuples project to lists. No summary-only representation or omitted bodies. Result SHA binds its complete canonical body after the cap.

A shared private `_bounded_canonical` must enforce the same 262,144-byte rule for complete new bundle and result bodies. Guard equality/overflow tests do not establish the largest legal public fixture.

## Complete protocol identity

`protocol()` returns a fresh dictionary with exactly these keys and values:

- `version`, `scope`, `status`, `codec_id` and `schema_version`: the literals above.
- `ts_out_modes`: JSON list `['absent', 'present']`.
- `record_field_order`: the sixteen-field list above.
- `integer_bounds`: dictionary from each integer field name to its exact `[minimum, maximum]` pair above; `ts_out` denotes its present-mode range.
- `action_side_length`: 1; `action_side_codepoint_min`: 0; `action_side_codepoint_max`: 127.
- `min_items`: 2; `max_items`: 128; `max_payloads`: 127; `max_body_bytes`: 262144; `max_cursor_body_bytes`: 65536.
- `metadata_payload`: `literal_none`.
- `context_pin_scheme`: `sha256_canonical_context_body`.
- `payload_pin_scheme`: `sha256_canonical_complete_record_body`.
- `contextual_prefix_scheme`: `sha256_binding_protocol_context_cursor_prefix`.
- `prefix_complete_member_pin`: `excluded`.
- `cursor_protocol_sha256`: computed by unchanged `cursor.protocol_sha256()`.
- `cursor_source_sha256`: the held used-helper metadata pin above.
- `dataclass_fields`: dictionary from the five new dataclass names to their exact field-order lists above.
- `authority_flags`: dictionary of the 31 names below to literal `False`.

`P = H(this complete protocol dictionary)`. Immutable enforcement and literal body construction cannot depend on mutable exported constants or a caller-mutated returned dictionary. Function/code replacement is outside authentication claims. A later root preflight must hold the old source unchanged; this specification does not manufacture runtime source authentication from its metadata pin.

## Public in-memory interface

These are proposed signatures, not implemented APIs or executable examples. All expected pins are mandatory exact lowercase ASCII 64-character hexadecimal strings.

```text
protocol() -> dict
protocol_sha256() -> str
context_sha256(context, *, expected_protocol_sha256) -> str
payload_sha256(payload, context, *, expected_protocol_sha256,
               expected_context_sha256) -> str
bundle_sha256(bundle, *, expected_protocol_sha256, expected_context_sha256,
              expected_cursor_protocol_sha256, expected_cursor_fixture_sha256) -> str
assess(bundle, *, expected_protocol_sha256, expected_context_sha256,
       expected_cursor_protocol_sha256, expected_cursor_fixture_sha256,
       expected_bundle_sha256) -> BindingAssessment
verify(assessment, bundle, *, expected_protocol_sha256, expected_context_sha256,
       expected_cursor_protocol_sha256, expected_cursor_fixture_sha256,
       expected_bundle_sha256, expected_assessment_sha256) -> None
```

Every supplied pin's syntax is checked before any caller-object traversal; then independently known new/old literal protocol identities are compared. Context equality follows complete context validation and precedes payload fields. The complete old fixture pin can be recomputed from metadata-only fields and compared before new payload fields. Complete new bundle/result equality follows value projection, never an impossible pre-read equality with the values it binds.

Single-payload hashing validates its entire body and context but establishes no cursor mapping or book claim. Bundle hashing runs the full bundle pipeline, including old assessment reconstruction and capacity, rather than being a lenient serializer. Callers construct context pin, individual payload pins, old cursor fixture pin, complete bundle pin and assessment in that acyclic order. No auto-fill or repair of retained caller pins.

Malformed-object/shape/value refusal paths normalize `ValueError`, `TypeError`, `AttributeError` and `OverflowError` to `ValueError`. Exception wording is diagnostic, not a semantic acceptance commitment. `AssertionError` is not caught: independent poison sentinels must escape. There is no mutation, I/O or external effect; repeated pure verification does not provide account/order exactly-once, storage or resume semantics.

## Normative validation phases

The full phases below apply to `bundle_sha256`, `assess` and `verify`. The protocol/context/single-payload helpers execute only their applicable portions and establish no cursor claim.

**Deferred slots mean all sixteen `MboPayload` fields**, including instrument ID, `rtype`, `record_size`, action, side and `ts_out`, in both the original and retained submitted payloads. Existing cursor/audit metadata IDs are distinct from these deferred body slots. No eager generic all-field `getattr` is allowed before complete metadata preflight.

### Phase 0: expectations

Inspect every expected pin's syntax even if an earlier one is wrong, then compare known literal protocol identities before caller traversal. Inspecting syntax does not claim recomputed whole-input equality.

### Phase 1: complete metadata preflight

Validate the exact context type, all three context values and its expected hash before payload values. Preflight the complete original bundle envelopes, old cursor fixture/header/mappings/items/counts/opaque pins, payload tuple count, first `None` and exact type of every subsequent payload. Recompute and compare the old fixture pin. Reconstruct the complete old cursor assessment using unchanged public APIs, retaining both old byte caps. Its IDs and opaque item pins are metadata, not reads of new `MboPayload` slots.

For `verify`, also preflight the **entire submitted-result metadata** before reading any original or submitted deferred slot:

- Exact new result/bundle/context/audit types and tuple containers, exact status and every retained pin's syntax.
- Recompute the submitted retained context and compare it with the expected context; check its old fixture envelopes, payload tuple length/types and header `None` semantics.
- Validate its nested old `CursorAssessment` through unchanged `cursor.verify`, against the reconstructed original old fixture/assessment and the rebuilt old assessment pin. This checks every old audit/count/flag/body and both old caps without reading new payload fields.
- New audit count equals the original old declared item count; positions equal tuple order. Dispositions/IDs/ordinals agree with reconstructed old metadata.
- Header audit has disposition `header` and exact `None` payload pin, instrument ID and target ordinal. Every later audit has an exact lowercase payload pin, old bounded ID and disposition `foreign` or `target_candidate`. Foreign ordinal is exactly `None`; target ordinal is exact integer 1 through 127.
- Every cursor item, cursor prefix and bound prefix pin is exact lowercase hexadecimal. Available metadata contradictions may be rejected against reconstructed original metadata now; numerical body equality remains later.
- All 31 top-level and all 26 old nested authority pairs are exact, alphabetically ordered, complete and literal `False`, never integer zero.

A malformed **final** envelope/status/flag must refuse before **any** original or submitted deferred slot. Missing/deleted body slots and body instrument agreement wait for phase 2. No complete new bundle/result equality is claimed at this stage, and no submitted summary is adopted as independent truth.

### Phase 2: complete constructed bodies

Read, validate and explicitly project each original target and foreign payload's sixteen fields. Check context-specific `ts_out`, instrument agreement, recomputed body pin and equality to the corresponding old retained opaque pin. For `verify`, also validate/project every retained submitted payload after both complete metadata preflights have finished.

Any numerical defect or mismatch refuses the whole output; no successful prefix is returned. A malformed numerical suffix may require numerical access to discover; this is not an early-metadata claim. There is no target semantic filter or clock/book/flow/event/feature-witness call.

### Phase 3: complete identity and verification

Bound/hash the complete original bundle and compare the expected bundle pin. Reconstruct every new audit from the rebuilt old assessment and checked payload pins. Bound/hash the complete new result; in `verify`, compare the expected assessment pin.

Validate every submitted retained body/type/field/pin/flag, recompute its actual complete-result body SHA, and require both actual canonical bytes and supplied assessment digest to equal the completely rebuilt original result. Return only after all applicable phases succeed. `bundle_sha256` requires the dependent old assessment to fit but does not emit a new assessment.

These are access-order and refusal guarantees, not protection against adversarial in-memory mutation, races or coherent caller replacement.

## Contextual causal audits

Each new audit has the same position, disposition, ID and candidate ordinal as the rebuilt old audit. Its payload pin is `None` for the header and checked `P_i` for each MBO. `cursor_item_sha256` and `cursor_prefix_sha256` retain exact old meanings.

For **every audit, including the header at position 1**:

```text
bound_prefix_sha256 = H({binding_protocol_sha256: P,
                        context_sha256: C,
                        cursor_prefix_sha256: old_prefix})
```

This is a contextual digest of the old rolling chain, not a second body chain, successful-book ordinal, native header hash, byte offset or authenticated publication cursor. Old item/prefix pins bind constructed bodies transitively only after complete body-pin comparisons succeed. Context-independent raw body pins are safe here because the new protocol/context are separately included in the contextual and complete identities.

The contextual wrapper excludes the complete member assertion, old fixture pin, complete bundle pin, declared total count, final counts/result heads and future payloads. With unchanged protocol/context, fixture identifiers, complete known header/mapping and consumed items/bodies, a changed valid future suffix or complete-only member assertion changes complete bundle/result identities while preserving preceding old/new prefixes.

Changing a preceding foreign body with correctly recomputed payload/item pins changes following old/new prefixes even when target candidates are identical. Changing valid `ts_out` context and the corresponding required body representations changes `C` and the bound header identity: the old header prefix alone does not bind new context. Invariance compares fully valid bundles; every complete malformed suffix still refuses. No future terminal state drives earlier behavior.

## Exact false authorities

There are exactly 31 alphabetically sorted `(name, False)` pairs at the top level. The old nested 26 remain unchanged. The names are:

```text
account_authenticated
book_application_verified
broker_economics_measured
byte_offsets_verified
calendar_authenticated
codec_context_authenticated
decoded_source_authenticated
event_closure_verified
execution_allowed
feature_derivation_verified
funding_authenticated
historical_access_allowed
historical_validation_allowed
mapping_authenticated
model_call_allowed
native_decoding_verified
native_eof_verified
native_header_verified
native_payloads_verified
native_record_semantics_verified
native_target_ordinals_verified
original_bytes_verified
promotion_allowed
publication_cursor_verified
runtime_authenticated
scoring_allowed
source_authenticated
storage_resume_allowed
strategy_integration_allowed
trading_enabled
training_allowed
```

Constructed consistency success never switches these to `True`. Coherent replacement of the whole caller context, bundle and expected pins remains unauthenticated and undetectable.

## Independent, unexecuted acceptance groups

All twelve groups are prospective. None is implemented, collected or executed in this contract window.

1. Exact complete schema: every field required; context/types/tuples/header-`None` rules; reject bool/int aliases, subclasses, missing/extra fields and container substitutions.
2. Raw integer preservation: each declared minimum/maximum, equality/outside, values around `2**53`, signed values and ASCII controls; no floats, coercion, sentinel replacement or trimming.
3. Explicit `ts_out`: absent `None` versus present exact S64; independent `rtype`/`record_size` binding, with no JSON-size or native-layout claim.
4. Change each of the sixteen fields independently and require a changed body pin; complete valid paired bundle adjustments affect subsequent identities. Keep repeated bodies as occurrences.
5. Full target/foreign coverage, including negative prices, bad semantic clocks/actions and unusual flags within constructed bounds; refuse mismatches, gaps, omissions, reordering and final missing bodies.
6. Real access-order sentinels: uncaught `AssertionError` on actual reads of all sixteen deferred slots in original/submitted payloads. Malformed expected pins/protocol/context/final envelope/status/flags refuse first. Generic `ValueError`-only tests cannot prove this. Bad numerical suffixes may require value access but never return a partial result.
7. Hand-project complete literal protocol/context/record/bundle/old-cursor/audit/result bodies using independent ASCII sorted compact JSON and SHA256. Never derive expected bodies from production serializers or dataclass reflection.
8. Shared new-cap equality/overflow separately from a prospectively chosen cap-compliant 128-position envelope with allowed mappings and transport-bound integers in both modes. Measure such envelopes independently; do not call them largest legal/all-maxima cases or a universal maximum. Preserve both old caps.
9. Fully valid future target/foreign suffix and complete-only member variants preserve preceding contextual identity. Cover context-aware header identity and changed preceding foreign payloads.
10. Reject every status/flag/pin/count/nested-cursor/body/audit/type tamper through complete reconstruction; adopt no submitted summaries. Pure rebuilding is deterministic, not authenticated state continuity.
11. Mutable exported constants and returned protocol dictionaries cannot change literal enforcement/identity. Used-helper metadata is not full runtime/native authentication.
12. A later independently registered implementation must preserve all 414 old source/test entries and all old 9,398 case-sensitive JUnit identities, plus exactly its independently authored new cases. Preserve `GZIP`/`gzip`, exact three old skips/full XML reasons, zero failures/errors, matching process exit and frozen-pin reconciliation before any later acceptance claim. No count is guessed and no accepted suite is rerun for status now.

## Style and prospective verification commands

Style follows the existing exact-type frozen/slotted cursor interface, keyword-only expected pins and explicit literal projections. For example, the unchanged source already defines this type; it is not a new implementation:

```python
@dataclass(frozen=True, slots=True)
class DecodedItem:
    decoded_position: int
    kind: str
    instrument_id: int | None
    payload_sha256: str | None
```

No runtime commands are released in this contract window. Read-only PowerShell `Get-Content`/`Get-FileHash` and Git status serve documentation inspection, not runtime acceptance.

The following are **unexecuted future command shapes**, not runnable approvals. The `<fresh-registration>` placeholders must be replaced only in a later explicit registration after implementation release, stable independent source/test review and frozen sources. Proposed source/test files do not yet exist.

```text
.venv/Scripts/python.exe -B -m pytest -q tests/test_six_e_record_payload_binding.py --junitxml=logs/payload_binding_focused_<fresh-registration>.xml
.venv/Scripts/python.exe -B -m ruff check src tests
.venv/Scripts/python.exe -B -m ruff format --check src/ai_trader/research/six_e_record_payload_binding.py tests/test_six_e_record_payload_binding.py
.venv/Scripts/python.exe -B -m pytest -q --junitxml=logs/project_full_suite_<fresh-registration>.xml
```

Adjacent selection, actual run names/counts/source pins, process ownership and complete JUnit acceptance must be registered before launch. Root alone may own later launches under a separate release. No suite, example, import or numerical experiment is started by saving this spec.

## Decisions, trade-offs and remaining gates

The raw sixteen-field JSON pin keeps existing cursor item meaning intact. A separately labelled contextual wrapper binds the new interpretation without replacing old prefixes or adding an unnecessary second body chain. `ts_out` stays an explicit field in both modes rather than silently inheriting a native default. Broad declared transport domains preserve exact invented values and semantic poison cases without falsely asserting native enum/width validity.

Alternatives not selected are original wire-byte binding, native decoder context reconstruction, a duplicate rolling body chain, automatic payload-pin repair and feature-witness coercion. The first two require evidence outside this request; the others obscure old identities or defeat caller-pin/refusal boundaries. No alternatives are declared impossible for a separately reviewed later native layer.

Always preserve exact values, complete coverage, false flags, old pins and dirty work. Ask before later implementation, native/historical/cohort access or broader capacity/context. Never introduce credentials/orders/network, dependencies/security changes/bypasses, commits, reseeding/daily resets, UNKNOWN cancellation/reconciliation, subset scoring, old-fill filtering or future terminal-plan stitching. BTC/cloud collectors stay untouched. Disabled App Security is not a demonstrated fix and is not inspected or altered.

Native decoding/full header/version/upgrade/native widths/original bytes/EOF/book/event/publication/calendar, complete historical capacity and one-genesis multi-session continuity remain separately reviewed and prospectively registered gates. Existing cursor regression acceptance is complete, not pending, and is never repeated for status.

**Human approval questions:** approve the constructed U64/S64 domains and 262,144-byte new cap; approve explicit absent/present `ts_out` and the contextual-prefix scheme; and decide separately whether to authorize a later implementation window. Until that approval, this specification remains **PROPOSED**.

See `6E_RECORD_PAYLOAD_BINDING_DESIGN_20261011.md`, `6E_DECODED_PAYLOAD_NEXT_GATE_20261011.md` and the unchanged `6E_NATIVE_CURSOR_METADATA_CONTRACT_20261011.md` for prior design and dependency context. The older design's then-pending regression wording is chronology, not the current accepted cursor result.
