# Complete member-to-publication bridge — proposed contract, 2026-10-13

## 1. Status, objective and capability boundary

**PROPOSED / UNIMPLEMENTED — independently statically reviewed.** Two complete independent composition reviews and the exact required receipt-observation correction are closed, with no Required finding remaining. This is specification work under the [extended documentation window](6E_SOURCE_PUBLICATION_BRIDGE_WINDOW_20261013.md), ending **2026-10-13T18:06:41Z / 19:06:41 Lisbon**. No API, test, native call, historical experiment or new performance result described below has been implemented or executed. The accepted provider remains complete: 13,540 passes and three expected skips; no owned runtime is pending. The human's routine-approval waiver avoids repetitive approval requests, not evidence requirements or expansion beyond documentation.

The single capability is **complete supplied invented-member bytes → byte-bound reconstructed publications**. Its consumer is the next research integration layer. Success would associate every unchanged typed-adapter publication with the complete verified native member and its exact consumed native prefix, without changing either dependency's meaning. “Source intake” in this contract means in-memory argument admission only. It does not open files, extract archives, fetch URLs, authenticate a vendor/collection receipt, read history or stream an early publication.

The capability boundary is deliberately smaller than the longer roadmap:

| Capability | Relationship | Current disposition |
| --- | --- | --- |
| `native-member-evidence` | Complete in-memory native member consistency | Accepted dependency; unchanged |
| `member-publication-bridge` | Compose that evidence with unchanged typed reconstruction and new causal links | This proposed contract only |
| `archive-source-intake` | Admit owned source/container/collection evidence and complete archive members | Separate future capability; no reader here |
| `historical-session-integration` | Original-row parity, complete capacity/calendar and one-genesis multi-session continuity | Separate future capability; not released |
| `economic-validation` | Accounts, fills/costs/risk and untouched validation | Separate future capability; not released |

These are scope boundaries, not an implementation plan. Archive intake can later supply complete bytes; the bridge does not depend on an archive reader and must not pretend it has one. No cyclical dependence on historical outcomes, policy scores or account state is introduced.

## 2. Existing evidence and source-grounded constraints

The [provider guide](6E_NATIVE_MEMBER_DECODE_EVIDENCE.md), [typed-adapter guide](6E_TYPED_NATIVE_EVENT_ADAPTER.md), [payload guide](6E_RECORD_PAYLOAD_BINDING.md) and [cursor guide](6E_NATIVE_CURSOR_METADATA.md) describe accepted separate components. Their earlier contracts retain historical prospective wording; later accepted source and handoffs establish their current behavior. This proposal adds only composition, complete association and causal provenance links.

| Existing boundary | Inspected source and relevant entry points | Constraint on the new bridge |
| --- | --- | --- |
| Native evidence | [public facade](../src/ai_trader/research/six_e_native_member_decode_evidence.py), `decode_member`, `verify`; [typed records](../src/ai_trader/research/_native_member_types.py), records and `wire_projection` | Mandatory complete original bytes; exact observed and wire representations; `verify` performs fresh contained native execution |
| Native framing/observations | [engine](../src/ai_trader/research/_native_member_engine.py), independent framing and complete observed-body comparison | Original wire order and sorted logical mapping order are different; native getter projection is not a byte blob |
| Cursor metadata | [cursor](../src/ai_trader/research/six_e_native_cursor_metadata.py), `_header_body`, `_fixture_body`, `_construct` | Fixed invented date/contract, all positions and mappings, synthetic labels, metadata prefix excluding complete member/count |
| Payload binding | [binding](../src/ai_trader/research/six_e_record_payload_binding.py), `_payload_body`, public pin/assess/verify APIs | All sixteen raw fields, ASCII characters, signed timestamp intersection, explicit absent/present ts_out |
| Typed publications | [adapter](../src/ai_trader/research/six_e_typed_native_event_adapter.py), context, `_Engine`, public fixture/replay/verify APIs | Fixed day/window, real reconstructed initialization, full event versus protected capture, first due publication and complete finish |

Held definitions are the [native contract](6E_NATIVE_SOURCE_EVIDENCE_CONTRACT_20261012.md), [qualified schema annex](6E_NATIVE_PROFILE_SCHEMA_ANNEX_20261012.md), [typed contract](6E_TYPED_NATIVE_EVENT_ADAPTER_CONTRACT_20261011.md), [binding contract](6E_PAYLOAD_BINDING_CONTRACT_20261011.md) and [cursor contract](6E_NATIVE_CURSOR_METADATA_CONTRACT_20261011.md). Preserve them; a composition mismatch refuses the new bridge instead of changing an accepted dependency.

Known native protocol SHA256 is `baef653d21535c864a889e1299332b1b182421cbd154cd3247d81705f10133e1`; qualified profile-body SHA256 is `5016b1dc56537fdefdac74e56154ceb410307f3677fb08d8455cba8f54c86b0d`; RuntimeManifest SHA256 is `4aab559ab26a25cf35579dc723cb00d06db933ea65c63d9793a34939191c2ec3`; fixed execution manifest is `2db856c8c85a1d9d268819b9c7e7246478342d86c419c6e64f889f18cee103b2`. The complete registered 437-file map is held at `bcfd7c24f524a1fda112aa833edc8b1f15c34f70cbaa4db6c1545db2a269dd9a`. These are retained evidence identities, not a fresh runtime check or authentication claim.

## 3. Public surface and complete new types

Proposed source: `src/ai_trader/research/six_e_source_publication_bridge.py`. Proposed independent test: `tests/test_six_e_source_publication_bridge.py`. Both remain absent. No package-init, dependency, native worker, accepted source/test/resource or old contract change is part of this specification.

Exactly five public functions and four new frozen/slotted record classes are proposed. Exact built-in scalar types and exact tuple/record classes are required; subclasses, dict substitutes, booleans as integers, extra/missing fields, mutable sequences and coercion refuse. Every field is mandatory, with no defaults. The original bytes must be exact immutable `bytes`, not a path, buffer callback, iterable or memoryview.

```text
BridgeContext(fixture_id: str, source_session: str,
              native_context: native.MemberDecodeContext)

NativePrefixLink(decoded_position: int, kind: str, wire_span_ordinal: int,
                 decompressed_start: int, decompressed_end: int,
                 wire_sha256: str, wire_fields_sha256: str,
                 projection_sha256: str, previous_prefix_sha256: str,
                 prefix_sha256: str)

PublicationLink(publication_ordinal: int, quote_ordinal: int, event_ordinal: int,
                decoded_position: int, ts_recv_ns: int,
                adapter_prefix_sha256: str, publication_sha256: str,
                native_prefix_sha256: str, link_sha256: str)

BridgeEvidence(status: str, protocol_sha256: str, context_sha256: str,
               context: BridgeContext,
               native_evidence: native.MemberDecodeEvidence,
               adapter_assessment: adapter.AdapterAssessment,
               native_prefixes: tuple[NativePrefixLink, ...],
               publication_links: tuple[PublicationLink, ...],
               authorities: tuple[tuple[str, bool], ...],
               evidence_sha256: str)

protocol() -> dict
protocol_sha256() -> str
context_sha256(context, *, expected_protocol_sha256) -> str
replay(member_bytes, context, *, expected_protocol_sha256,
       expected_context_sha256, expected_member_sha256,
       expected_metadata_sha256) -> BridgeEvidence
verify(evidence, member_bytes, context, *, expected_protocol_sha256,
       expected_context_sha256, expected_member_sha256,
       expected_metadata_sha256, expected_evidence_sha256) -> None
```

All expected arguments are mandatory keyword-only exact lowercase ASCII 64-hex strings. No optional expected value, caller-selected protocol/profile/runtime, mutable expected-dictionary, worker hook, path, URL, codec option, checkpoint, ready-made fixture, selected-publication subset or supplied initial book is accepted. Fixed dependency protocols/profile/runtime are included in the new complete protocol, not redefined through caller knobs. `expected_metadata_sha256` means the complete native **logical MetadataProjection**, never the raw header-span hash.

`fixture_id` and `source_session` follow the existing cursor's exact ASCII `synthetic-[A-Za-z0-9._:-]+` rule and complete maximum length 64. They are prospectively assigned stable labels, not authentic source identifiers. Never derive them from the complete member/evidence/result digest, terminal facts, future records or outcomes: the old prefix binds these labels. Their independence is a caller/prospective-registration requirement, not something string syntax authenticates. The fixed native context must have profile_id `dbn_v3_asis_zstd_cext_invented_20261012_v1`, member_compression `ZSTD_CONCAT`, input_version exact int 3, upgrade_policy `AS_IS`, and an exact `expected_ts_out` bool.

The new status is exactly `complete_invented_member_publication_consistency_not_source_authentication`. Every nested native/adapter/binding/cursor status stays unchanged; the bridge does not relabel any of them “authenticated” or “historically verified”. NativePrefixLink positions and span ordinals are 1..128, contiguous and equal; kinds are exact `Metadata` at position1 then `MBO`. Offsets are original decompressed coordinates, 0..1,048,576, start < end; first starts0, every next starts at the previous end. PublicationLink ordinals are complete 1..N with N1..32, quote/event ordinals1..127, position2..128; all values must equal the corresponding reconstructed publication, not only fit a range. Timestamp is an exact signed-int64 value, further constrained by the unchanged publication window. All hash fields have the exact SHA syntax and recomputed meaning below.

## 4. Complete metadata intersection and projection

The provider admits a broader domain than the typed adapter. A valid native member outside their intersection **refuses the whole bridge**. No smaller subset, normalized replacement or fallback succeeds.

Before constructing old MBO payloads, require the fully reconstructed native Metadata/wire header and context to agree on all the following:

| Field | Exact requirement and old projection |
| --- | --- |
| Version and upgrade | Original input3, yielded Metadata version3, `AS_IS`; no v1/v2 upgrade |
| Dataset/schema | `GLBX.MDP3`; complete native SchemaMbo row and raw schema0; old string `mbo` |
| Symbols | Complete original tuple exactly `("6E.FUT",)`; no partial or not-found symbols |
| Start/end | Actual raw start and logical start `1743984000000000000`; actual raw end and logical end `1744070400000000000`. Absent end0/U64_MAX is not replaced with this end |
| Symbology | Exact registered native `PARENT`/code4/text`parent` and `INSTRUMENT_ID`/code0/text`instrument_id`, matching raw fields; not null input symbology |
| Limit/partial | Raw limit0 and observed limitNone; complete partial tuple empty. Do not turn a nonzero cap into unlimited |
| ts_out | Exact raw mode0/1, Metadata bool, and native_context.expected_ts_out agree |
| Complete mappings | Use **wire-order** groups and original interval order for the old DeclaredHeader. Preserve complete logical sorted groups separately in native_evidence |

Mapping conversion is representation-only: each wire `raw_symbol` becomes old `contract`, each raw valid YYYYMMDD becomes zero-padded canonical `YYYY-MM-DD`, and each interval `symbol` becomes `instrument_symbol` unchanged. No whitespace trimming, date clipping, interval sorting/merging, alias resolution or numeric symbol normalization. The verified native logical projection must still match the same complete wire declarations with only its already-defined group sorting. Old constraints apply to **every** group, including unrelated and inactive groups: 1..8 groups; <=16 intervals/group, <=32 total; unique bounded ASCII group names; dates2000-01-01..2100-12-31, strictly increasing intervals; bounded ASCII symbols; exactly one active end-exclusive `6EM5` interval on `2025-04-07`, with ASCII-decimal symbol fitting U32. Leading decimal zeros remain in the declaration; the old public cursor's mapping logic supplies the numeric target unchanged. No substitution with instrument1.

Construct `DeclaredHeader(dataset, "mbo", symbols, not_found, start, end, mappings)` from these actual admitted values. Construct `AdapterContext(3,"AS_IS",3,"parent","instrument_id",(),None,actual_ts_out)` only after their equality is established. The implicit old fixture date/contract remain `2025-04-07`/`6EM5`. These are fixed invented scope, not metadata-derived permission to use real April7 history. A fixture label cannot turn historical data into an invented member.

All omitted old-header native fields remain in the full native_evidence and causal wire/projection chain: complete raw header bytes' hash, counts/length/reserved/alignment fields, symbol_cstr_len, version/upgrade context, all fourteen logical Metadata observations and original wire group order. Logical Metadata hash is not a raw-header hash. `FrameSpan` retains coordinates/raw hashes, not embedded raw bytes; `WireSpan` retains structured wire fields/raw hashes, not original byte strings. Fresh verification always needs the complete original compressed member argument.

## 5. Every position and raw payload

Preserve all native `occurrences` and corresponding DBN spans, including header, foreign instruments, records outside the observation window and the complete suffix. One Metadata at decoded position1 maps to `DecodedItem(1,"metadata",None,None)` and payloadNone. Every remaining occurrence maps at the **same original position** to one exact `MboPayload` and one `DecodedItem(position,"mbo",actual_instrument_id,actual_payload_hash)`. Declared item count equals the complete actual occurrence count; asserted_member_sha256 equals the complete raw compressed-member hash. There is no caller-supplied opaque assertion left unassociated at this outer boundary.

For each target and foreign MBO, require its verified wire/observed correspondence, then map:

| Old payload field | Value, never a pretty/native float conversion |
| --- | --- |
| publisher_id, instrument_id, ts_event, order_id, price, size | Exact corresponding raw integer; observed value equal |
| action, side | One ASCII character with `ord(character)==raw_u8`, equal to the verified native enum text or UnknownChar value; refuse codepoints128..255, never replace with N |
| ts_recv, flags, channel_id, ts_in_delta, sequence | Exact raw integer; observed value equal |
| ts_out absent | Actual wireNone and native observedU64_MAX, projected to literalNone because the field is absent; retain both native representations |
| ts_out present | Exact actual raw/observed integer; must fit old signed-int64, including distinguishing presentU64_MAX from absence and refusing it |
| rtype | Actual wire160, equal to complete observed RtypeMbo code |
| record_size | Actual observed56/64, equal to4*wire.length_words and span length; never infer a new position from it |

Native U64 ts_event/ts_recv/present-ts_out must also fit old signed-int64. Undefined/out-of-range values refuse instead of clamping, wrapping or replacing. All other native and old exact domains remain enforced; old types being wider does not relax native wire bounds. The extra `ts_index_observed` and all enum discriminants remain in native_evidence and native prefix identity even though old MboPayload has only sixteen fields.

Use unchanged public binding `payload_sha256` to compute each complete old record pin with `PayloadContext("constructed_mbo_json_v1",1,"present" if actual_ts_out else "absent")`; then construct the complete CursorFixture with prospective labels, actual header, actual member hash, count and full items. Use public cursor fixture hashing/assessment/verification and all its old caps; use public binding bundle hashing and public adapter fixture hashing/replay/verification as described in section8. Do not call private dependency serializers or use dataclass reflection as an oracle. The new projection code may use explicit literal field mappings only. The new bridge does not modify old prefix algorithms, statuses, flags or numerical rules.

## 6. Unchanged event/publication semantics

The existing [typed contract](6E_TYPED_NATIVE_EVENT_ADAPTER_CONTRACT_20261011.md) and held adapter source remain normative for numerical reconstruction. All times in this section are UTC. In particular:

- Begin with the unchanged empty **uninitialized** book; no supplied checkpoint or manufactured R. Actual target reset/snapshot/day/quality/book admission controls still run. Target-candidate ordinal is not successful-transition ordinal, event ordinal, quote ordinal, publication ordinal or byte offset.
- Foreign bodies remain structurally checked and prefix-bound but never drive target receive clocks, timers, book, flow, events, quotes or publications. Do not sort by timestamps or ts_index.
- Full ordinary target event/T provenance is distinct from protected execution capture `[11:59:50,16:00)` on the fixed day. Ordinary target F_LAST closes an event; foreign F_LAST does not. Reset/snapshot dispositions are separate even without F_LAST; incomplete events cannot be discarded across them.
- Retain original target-clock quality rules, snapshot and exceptional closed-clear handling, monotonic ordinary receive clocks, pre-update execution capture, five-second equality/+1ns behavior and strict book faults. Do not add a new absolute-price-grid rule or treat observed F records as broker fills.
- Only the first due completed quote inside `[12:00,16:00)` publishes the complete37 features, then sets next due to actual receive+1s. Later equal-time events cannot rewrite that row. No grid backfill, strategy eligibility, policy vote, favorable-subset selection, future state or outcome enters the bridge.
- Preserve every feature name, exact scalar type and float representation; the typed adapter's single-history-quote `mid_travel_5s_ticks` is exact int0, not the older synthetic witness's promoted0.0.
- Require unchanged full finish: at least one successful target, 1..32 publications, no incomplete target event/T/capture, matching clock coverage and all terminal queues/orders/state. Records after the observation window remain in complete identity. Invalid suffix means no bridge result, even if an earlier prefix looks useful.

The complete native EOF/framing checks and typed finish are different requirements. Neither proves historical receipt/publication availability at the receive clock, full-day historical coverage or original producer row parity.

## 7. Canonical identities and exact protocol

`H(body)` means SHA256 of exact UTF-8 `json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)`, with no newline. Exact scalar/type validation is independent of JSON equality. Tuples become ordered lists. New authorities become ordered lists of two-element lists in the native authority order. Nested objects retain **their own** accepted canonicalization: native authorities remain lists; adapter/binding/cursor authority tuples and their specified sorted counter-pairs project to dictionaries. Preserve complete nested own hashes, finite floats, negative zero and int/float distinctions. No generic “drop all hash fields” or “normalize numbers” operation exists.

The BridgeContext body has exactly `fixture_id`, `source_session`, `native_context`; native_context uses its five exact field names. `context_sha256=H(complete_context_body)` after complete validation and the independent65,536-byte cap.

`protocol()` returns a fresh complete literal dictionary with exactly these top-level keys: `version`, `scope`, `status`, `dataclass_fields`, `dependencies`, `fixed_scope`, `projection_rules`, `limits`, `hash_schemes`, `phase_order`, `authority_names`. The values are the rules in this contract, not caller-set globals. Version is `invented_member_publication_bridge_v1`; scope is `complete_invented_in_memory_native_member_to_typed_publication_consistency_only`; status is section3's literal. Dataclass field orders are exactly section3. `dependencies` contains complete frozen protocol bodies under `native`, `adapter`, `binding`, `cursor`, plus the known `profile_sha256`, `runtime_manifest_sha256` and `execution_manifest_sha256` from section2. The complete old bodies are the literal definitions fixed by their held source/contracts, not newly invented abbreviated summaries; their exact canonical hashes are derived before future implementation and independently asserted. All referenced native schemas and adapter field/rule definitions must resolve in full. Future implementation registration must retain the complete literal expected new protocol body, including these dependency bodies and every rule/limit/hash/phase list; no unresolved placeholder/hash or reflection-derived expectation can pass the interface gate.

`fixed_scope` carries the exact date, contract, dataset, schema, symbols, day/warmup/window bounds from sections4/6. `projection_rules`, `hash_schemes` and `phase_order` enumerate the exact ordered rules of sections4–8, not a free-form runtime policy. `limits` is section9's proposed outer limits and unchanged inner limits. `authority_names` is the exact section10 list. This document fixes semantic requirements; the later literal protocol representation/independent oracle must be statically reviewed before code, not improvised after tests. The new protocol SHA is **not yet an observed artifact**.

Let P be the checked complete bridge protocol SHA, C the checked BridgeContext SHA, and NC the checked native context SHA. The native-prefix seed is exactly:

```text
H({domain:"member_publication_native_prefix_seed_v1",
   bridge_protocol_sha256:P, bridge_context_sha256:C,
   native_context_sha256:NC,
   native_protocol_sha256:fixed_native_protocol_sha,
   profile_sha256:fixed_profile_sha,
   runtime_manifest_sha256:fixed_runtime_sha})
```

For each complete occurrence1..N, NativePrefixLink is populated from the corresponding actual occurrence and DBN span. Its `previous_prefix_sha256` is the seed for1, otherwise the preceding link's prefix. Its `prefix_sha256` is exactly `H({domain:"member_publication_native_prefix_link_v1", link:all_NativePrefixLink_fields_except_prefix_sha256})`. Thus the first link binds the complete original header wire/projection hashes and subsequent links bind every complete consumed target/foreign representation and association. Decompressed coordinates refer only to that consumed span. The complete observed/structured bodies that these hashes name remain present in native_evidence and are reverified; a chain of caller assertions alone cannot succeed.

For every old publication in original complete order, create one PublicationLink whose ordinal, quote/event references, decoded position, receive clock, adapter prefix and publication hash equal that publication. native_prefix_sha256 equals the native link at the same consumed position. `link_sha256=H({domain:"member_publication_link_v1", bridge_protocol_sha256:P, bridge_context_sha256:C, link:all_PublicationLink_fields_except_link_sha256})`. No selected subset or extra link is accepted.

The old adapter/cursor/binding chains stay unchanged. These new wrappers **exclude** whole compressed/decompressed-member hashes, physical frame hashes/ends (a frame may contain future records), native full evidence/report/terminal hashes, full fixture/bundle/assessment hashes, final counts/state, later publications and receipts. Stable protocol/profile/runtime context is already fixed before input, not a per-attempt loaded-identity report. The header is an actual initial input declaration, not proof of future collection. Complete member hashes bind only the complete association below.

For two wholly valid inputs with identical context/header/consumed prefix, an altered unconsumed suffix must change complete association identity while preserving earlier native prefixes, original publication bodies and new publication-link hashes. A different physical compression partition of identical decompressed bytes likewise preserves causal links but changes the complete member/framing association. Changing a consumed foreign record may preserve target numerical features but must change provenance. Changing original header wire order may preserve logical Metadata hash while changing native and old wire-order header prefixes. These are proposed metamorphic assertions, not already tested results. No causal identity proves an online receipt time or authenticity.

Complete BridgeEvidence body is **all fields except only its own evidence_sha256**. It includes the entire context, entire native evidence with its own hash, entire adapter assessment with its own hash and all nested fixture/binding/cursor/state bodies, every native prefix and publication link, all false authorities. `evidence_sha256=H(complete_body)`. The full artifact including that own hash has a separate cap but no second public hash field. Original complete compressed bytes are not embedded; native member_sha256 binds them and they remain mandatory input to verify. No transient PID/path/timing/host receipt appears in deterministic semantics; future execution records retain those separately without weakening complete native verification.

## 8. Required public phase order and atomic refusal

Helpers `protocol`, `protocol_sha256` and `context_sha256` perform no native decode. Replay and verify each have **exactly one** unchanged native-provider invocation on a positive path: replay calls public `native.decode_member`; verify calls public `native.verify`. Refusals may occur before that call. No automatic retry, fallback, extra provider decode, independent native constructor or new child/worker is added. The contained provider's execution behavior remains unchanged.

### Replay

1. Check every expected-pin syntax before caller-object traversal. Check new and dependency complete protocol equality, fixed native profile/runtime/execution context, then exact complete BridgeContext and its expected digest/cap. Require exact immutable complete bytes/type/size and raw expected_member_sha256. These are early checks, not full Metadata verification.
2. Call unchanged public native.decode_member with the fixed native protocol/profile/runtime pins, actual native_context, expected complete member and expected logical Metadata pins. Do not inspect provider internals, call its private worker directly or treat a self-reported evidence hash as native verification. The provider checks actual Metadata before wrapper MBO getter access; native decoder batches may already have parsed MBOs. No stronger native-parser deferral claim is made.
3. After full native return/owned cleanup, admit complete actual Metadata intersection. Only then construct all MBO projections/old payload pins, cursor fixture and adapter fixture. Independently preserve every original body and all narrower domains. Cursor public fixture hash/assessment/verify must accept the complete metadata under both old caps. Binding public context/payload/bundle APIs provide complete body identities, not replacements for adapter admission.
4. Call adapter.context_sha256, adapter.fixture_sha256 and adapter.replay with fixed dependency pins and the exact computed complete original cursor/bundle/fixture identities. `adapter.fixture_sha256` performs full reconstruction and finish; it is not a cheap serializer. This sequence has two complete pure adapter engine reconstructions and one native invocation, not a streaming path. The unchanged adapter's early metadata/cursor gate and later binding/body gate remain intact.
5. Construct all native prefix links and all publication links from the fully accepted dependencies. Check all cross-references, nested exact types/own hashes, all authorities, full original canonical bodies and independent inner/outer caps before any return. Return one complete BridgeEvidence only.

### Verify

1. Perform replay step1 and expected_evidence_sha256 syntax. Before native invocation, require exact BridgeEvidence top envelope/status/context equality and top pins; exact native/adapter record envelopes, bounded complete prefix/publication tuple types, complete new-link structural positions/hash syntax and all **new top authorities**. This is an explicitly limited bridge preflight, not a promise that every deep numerical slot has already been checked.
2. Call unchanged native.verify on submitted native_evidence, original complete member_bytes and native_context, with fixed native pins and original expected member/Metadata pins. Its expected_evidence_sha256 is the submitted native own digest after exact syntax/top-pin validation; fresh complete byte reconstruction and equality, not that submitted string, establish acceptance. Native.verify necessarily projects the entire submitted native body, including MBO fields, before dispatch. It is **not metadata-only or native-free**. All native authorities/cross-relations/body caps and actual reconstruction remain mandatory.
3. Derive the original adapter fixture anew from that now fully verified native evidence using sections4/5. Compute its complete cursor/binding/context/fixture identities through the same public APIs. Do not use the submitted adapter fixture as the original or repair any submitted value/pin.
4. Call unchanged adapter.verify with the submitted adapter_assessment and this fresh original fixture, fixed protocols and fresh complete original identities. The supplied adapter own hash is a checked claim passed to this public verifier; the verifier reconstructs all complete bodies and proves equality. Within this call its full original/submitted metadata/status/audit/reference/false-flag gate precedes either old raw-payload or submitted numerical traversal. This is the dependency's own boundary, **not a global claim that new native projection happened after every submitted adapter metadata check**. No private metadata helper or generic eager serializer substitutes for public verification.
5. Recompute complete native-prefix and publication-link tuples against the fully verified dependency bodies; compare every field, reference, scalar type and canonical byte. Independently reproject the entire submitted BridgeEvidence and context, apply all caps, recompute every new own digest and require expected_evidence_sha256 equality. ReturnNone only after full equality. Reusing an object after its complete public reconstruction/equality check is not adopting an unchecked checkpoint; no supplied state influences original reconstruction.

Malformed shape/value/type errors normalize to ValueError without partial success. Preserve provider RuntimeError/setup/identity/transport/resource/timeout/cleanup failures as operational failures, not “invalid data accepted elsewhere”. Do not catch AssertionError, KeyboardInterrupt, SystemExit or MemoryError; any already-owned provider resources retain the unchanged cleanup guarantee before propagation. No callback, prefix result, optional missing-stage flag, successful-subset report or resumption token exists. Human-readable diagnostics are not stable hashes. Tests use real uncaught getter sentinels to distinguish the explicitly scoped preflights from deferred body access; do not overclaim phase ordering that the accepted APIs do not provide.

## 9. Resource intersection and future execution evidence

These are proposed finite contracts, **not measured new capacity or historical coverage**:

| Scope | Bound / required behavior |
| --- | --- |
| BridgeContext canonical body | <=65,536 bytes |
| Complete proposed bridge protocol | <=262,144 canonical bytes |
| Complete BridgeEvidence body and full artifact | Each independently <=4,194,304 canonical bytes; equality allowed, first excess refuses |
| Native input/decompressed/header/framing | Preserve1..262,144 compressed bytes, <=1,048,576 decompressed bytes,128..65,536 framed header bytes and1..16 nonempty physical frames |
| Complete native evidence body | Preserve1,048,576 canonical-byte limit |
| Positions and new native links |2..128, one header plus1..127 MBOs, exact complete equality |
| Mappings | Intersection1..8 groups, <=16 intervals/group, <=32 total; no dropping declarations |
| Old cursor/binding | Both old65,536-byte cursor caps; both262,144-byte binding caps unchanged |
| Adapter fixture/result/state | Each original1,048,576-byte cap; original127 transition/event/quote/order/queue limits,1..32 publications,128 inactivity intervals,8 clock samples,32 exceptional clears |
| New publication links | Exactly the complete1..32 old publications; no optional omissions |
| Native execution per replay/verify | At most one fixed provider invocation; no retries; inherited256MiB committed-memory/5s queried CPU/12s work+3s teardown and fixed transport limits apply only to that provider worker |
| Pure bridge/adapter work | Explicit complete cardinality/byte caps; at most two full adapter reconstructions. No asserted parent-memory/CPU/wall-time containment or hard total runtime guarantee |

The new4MiB envelope cannot override an inner refusal. Do not serialize an unbounded object and call the output cap a pre-allocation sandbox; future implementation needs exact envelope/cardinality/type traversal before complete serialization, with malicious nesting/subclass/reflection rejected. Counts/caps bound the schema, not all Python allocator overhead. Fixed dependency protocol material must also be bounded before recursive processing. There is no generic recursive JSON input or arbitrary schema supplied by a caller.

Any later implementation plan must prospectively register the complete bridge import/source set, complete literal oracles, aggregate wall/resource observation strategy, exact native invocation counts and per-call provider receipts before runtime. Accepted provider containment qualifies its unchanged worker, not a new parent or extra process. New entry-point containment changes would need separate design/controls. Do not modify the accepted test deadline, backdate the environment or omit expired qualification cases: a future regression window requires an explicit supported registration or a separately authorized narrow amendment with original snapshot. None is made here.

**Future test-only receipt observation:** the public native facade returns evidence or None and discards the host's success receipt; no public receipt getter exists. Production bridge code stays public-API-only. A separately registered, pinned and reviewed test-only observer may wrap the unchanged private host `run_decode` return/error seam solely to retain the original `(response, receipt)` pair or an exception's existing `receipt` attribute. It must invoke the original exactly once, forward the exact arguments and original return/exception without mutation, preserve cleanup and counts, and restore the original callable exactly. It must not launch through the private seam instead of public decode/verify, replace the provider/worker, fabricate missing receipt stages or grant a caller hook. This is a narrow test-instrumentation exception to the production private-import prohibition, not a released observer or native experiment today. Its own identity/restoration and all complete receipts are future acceptance evidence.

Fixed-checkout qualification is not installed-wheel/deployment qualification. No full RAM/filesystem/network sandbox, empirical CPU-burn or parent-death proof follows. Reachable legal boundary examples must later have independent complete expected bodies and measured bytes; arbitrary guard controls are not valid member maxima. Never truncate, thin, split or relabel real history to pass constructed caps.

## 10. Threat boundaries and all-false authority

The caller controls bytes, labels, context, expected pins and submitted evidence. Hash consistency does not authenticate the source; coherent replacement of the entire caller context remains undetectable. Native dependencies and loaded identities provide only the already-qualified finite checks, not complete ABI/build/import-graph authenticity. Assets protected here are exact provenance, causality, process/resource ownership and the integrity of held work—not an account or execution permission.

Top `authorities` is an exact tuple in the provider's following order, every value literalFalse, no duplicates/missing/extra entries:

```text
source_authenticated, collection_receipt_authenticated,
native_runtime_authenticated, native_abi_authenticated,
native_wire_authenticated, native_header_authenticated, native_eof_authenticated,
feed_authenticated, calendar_authenticated, historical_read_authorized,
historical_validation_authorized, book_acceptance_authorized,
event_acceptance_authorized, feature_acceptance_authorized,
account_authorized, funding_authorized, receipt_authorized, cash_authorized,
margin_authorized, risk_authorized, storage_authorized, resume_authorized,
execution_authorized, trading_authorized, training_authorized,
scoring_authorized, independent_validation_authorized, promotion_authorized
```

All nested native28, adapter34, binding31 and cursor26 false sets remain complete and unchanged. A new causal link is not a permission token; old flags do not becomeTrue because an outer component supplies extra consistency evidence.

| Abuse case | Required response |
| --- | --- |
| Substitute valid shorter member or alter foreign/suffix data while retaining expected full hash | Refuse complete member/association equality; never score only the successful prefix |
| Present fabricated provider hash/typed assessment with internally matching summaries | Full public native and adapter reconstruction, every nested field/type and independent outer body equality |
| Smuggle future information through full frame/member hashes or derived synthetic labels | Exclude complete-only hashes from causal chain; retain stable prospective labels; test suffix/partition invariance |
| Map U64 undefined/present ts_out to None, change instrument/day, drop extra groups | Refuse outside intersection; exact explicit representation mapping only |
| Deep mutable/poisoned shapes, huge tuples or changing caller-selected protocol | Exact classes/cardinality/literal protocol/expected-pin preflight; no generic hooks or private serializer bypass |
| Inherit historical/authentication/account authority from a successful member decode | All authorities remainFalse; separate later scope/evidence gates |

No shell/path/URL/database/HTML/LLM interface, personal-data store, persistent cache, credentials or external fetch is introduced. Thus web authentication/CORS/SSRF controls, retention/deletion and dependency installation are not part of this bounded API; adding any would be a distinct design. Offline documentation does not perform vulnerability audits, network reference retrieval, native imports or Windows/security inspection. Disabled App Security is neither inspected nor claimed to explain or fix anything.

## 11. Fifteen proposed acceptance groups — all UNEXECUTED

| ID | Independently expected evidence for a later implementation |
| --- | --- |
| B1 interface/protocol | Exact five signatures/four records, complete literal protocol/dependency schemas/flags, fresh returned containers, mutation isolation, all expected-pin syntax and no placeholders; intended collected missing-behavior RED |
| B2 context/top preflight | Wrong/last pin, context, label, new top status, link envelope or topFalse flag refuses before provider invocation; exact types and uncaught native/adapter deferred-slot sentinels prove only the declared early scope |
| B3 native reconstruction | Positive and tampered complete member/Metadata cases, unchanged public provider used exactly once, mandatory original bytes, all framing/terminal/native bodies and receipts; native failure cannot become a partial bridge |
| B4 complete metadata intersection | Fixed date/day/version/symbology/partial/not-found/limit, actual end versus absent sentinel, exact ts_out; all unrelated mappings and intersection limits, invalid dates and active mapping ambiguity |
| B5 wire/logical order | Unsorted valid wire groups versus sorted logical projection; exact interval order and original symbol strings retained, no lost header fields; reordered header affects correct identities |
| B6 raw-field projection | Every16 field target/foreign,17 native observations and complete wire body; enum/unknown ASCII including unknown controls, non-ASCII refusal, U64/S64 boundaries, absent versus present ts_out/U64_MAX, original positions/record_size/ts_index |
| B7 complete dependency gates | Public cursor/binding/adapter calls and all original caps; malformed submitted nested statuses/flags/audits plus exact scalar aliases rejected; verify cannot adopt submitted fixture/state or private serializer output |
| B8 day/book/event composition | Actual reset/init/snapshot/quality/receive rules, foreign F_LAST, incomplete event/reset refusals, full T prefix versus protected capture, records after observation end and complete terminal queues |
| B9 first publication/features | Warmup, first due equal-time cursor, actual+1s cadence, all37 exact literal feature/state bodies including int0/float distinctions; no backfill/eligibility/outcome/quote-manufactured policy |
| B10 complete causal chains | Every header/foreign/target link exactly reconstructed; consumed foreign changes provenance while relevant numerics can stay equal; every publication binds actual same-position native and old adapter prefixes |
| B11 suffix/compression metamorphism | Wholly valid suffix-only changes preserve earlier links but change complete association; altered physical compression partitions preserve decompressed causal links; invalid suffix always refuses entire result; future-derived labels excluded by fixture registration |
| B12 submitted full tampering | Missing/extra/reordered body/audit/link, changed original header versus logical projection, nested hash/status/flag/enum/terminal/feature/offset tampering, matching stale outer digest and caller whole-context limitation distinguished |
| B13 limits/atomicity | Every inner and outer equality/first-excess guard, legal measured complete-capacity fixtures where reachable, arbitrary byte guards labelled honestly, no thin/split/partial/retry; parent aggregate observations separate from worker bounds |
| B14 operational boundary | One actual native invocation per positive replay/verify, fixed contained provider/owned exit/cleanup/complete receipts, no new worker hook; preserve operational/cancellation/invariant failure taxonomy and fake-versus-native evidence distinction |
| B15 complete regression/handoff | Genuine independent RED/GREEN and exact new-only mutant restoration; full focused/adjacent sets, every13,543 old case plus exactly collected new identities, exact three old skip XML reasons, no mandatory new-native skips, all held pins/tool-owned exits/reviews/docs reconciled |

Independent expected wire/Metadata/payload/cursor/book/event/37-feature/state/bridge bodies must be literal contract/reference-derived oracles. Never call production serialization, reflect dataclasses, derive expected results from actual native output or copy a passing result into an expected fixture. New raw-field-drop and future-hash-in-prefix mutants should produce their intended failures, and exact restoration the same-case GREEN. Preserve every failed attempt and distinguish harness/collection mistakes from behavioral RED. Existing provider/component tests are dependencies, not substitutes for these composition cases.

## 12. Style, commands, decisions and remaining gates

Follow current stdlib Python style: explicit exact types, frozen/slotted dataclasses, snake_case names, pure literal canonical projection and closed exceptions. A declaration-only example of style, **not implemented code**, is `@dataclass(frozen=True, slots=True) class BridgeContext: fixture_id: str; source_session: str; native_context: native.MemberDecodeContext`. Do not import the nine native-transitive historical producers. Use only unchanged public native/cursor/binding/adapter modules; no dynamic plugin or callback surface.

Current-window commands are read-only documentation/source inspection and local Markdown-link/preservation checks. No build/dev/server command applies. The following is only an **UNEXECUTED future focused-test template**, not permission to run it or a complete regression prescription:

```powershell
.venv/Scripts/python.exe -B -m pytest -q tests/test_six_e_source_publication_bridge.py --junitxml=logs/source_publication_bridge_focused_NEW_REGISTRATION.xml
```

A later approved execution scope must replace that report placeholder with a prospectively registered fresh path, register current deadline/owned-process identity and mandatory native controls/complete expected set, and define exact lint/format/adjacent/full commands. Never run today's frozen qualification tests after their deadline merely by changing the clock or environment. Documentation acceptance needs independent complete static review, source-backed claims, preservation and working local links; it does not need another accepted code suite.

Decisions and rejected alternatives:

- **Compose public providers, don't reimplement native parsing or numerical features.** This preserves accepted behavior and narrows new proof work to conversion and association. It still requires new complete composition acceptance.
- **One complete in-memory member, not file/archive intake.** Source paths, ownership, traversal, container/member completeness and collection authentication are independent problems and remain later gates.
- **Use the domain intersection, not a generic historical adapter.** Broader native records refuse rather than changing old schemas, relabeling date/instrument/genesis or dropping foreign data. Historical capacity cannot be manufactured by many toy members.
- **Retain old prefixes and add a native causal wrapper.** Whole-member/frame/evidence identities belong only in complete evidence; a single full-file hash is not a safe publication prefix.
- **Explicitly limited phase promises.** Public provider verification is native and full-body; adapter's strong metadata-before-values guarantee is local to its own API. No copied private preflight or misleading global deferral claim.
- **No native result cache or partial return.** Every verify rechecks complete original bytes once through the accepted contained provider. An earlier result cannot replace fresh equality.

Always retain every original position/body/context, all current false authorities, complete errors and old source/target/input/result/control pins/UNKNOWN liabilities. Changes to accepted dependencies, new readers, runtime/containment, historical/native execution, dependencies, credentials/accounts or security settings require distinct explicit scope and their own evidence; routine approval waiver does not erase these boundaries. Never late-fill/cancel/reconcile UNKNOWN, reseed/daily-reset accounts, filter old fills, score successful subsets or stitch future terminal plans into earlier state. BTC/cloud collectors and Graphify are untouched.

Remaining gates are concrete: this bridge implementation and B1–B15; actual archive/source/collection intake and authentication; source-bound historical receipt/availability and original-row parity; complete historical capacity/calendar/one-genesis multi-session/account continuity; broker economics and untouched validation. This proposal establishes none of them. The exact future literal protocol packet, aggregate execution registration and current regression-deadline support are required implementation preparation, not observed results today. Save/present this reviewed proposal and stop before planning/tasks/code within this documentation-only window.
