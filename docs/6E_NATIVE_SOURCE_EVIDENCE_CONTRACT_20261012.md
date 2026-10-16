# Proposed complete native member/source-evidence contract

## Status, objective and authority

**PROPOSED SPECIFICATION — UNIMPLEMENTED; native profile unverified.** Module ID: `native-member-witness`. The user directly approved a new four-hour OFFLINE documentation window at **2026-10-12T11:12:16Z**, ending **2026-10-12T15:12:16Z (16:12:16 Lisbon)**. This closes an architectural contract and its proof obligations, not a native experiment or implementation. The earlier routine-approval waiver avoids duplicate approval pauses; it does not enlarge this documentation-only scope.

One capability is proposed: bind **one complete in-memory Zstd-encoded member-content byte string** to the complete decoded Metadata/MBO observations under an explicit codec profile, independent framing checks and terminal consistency gates. The later consumer is an independently registered evidence verifier. It is not a price loader, archive selector, feature engine, account, broker, model or strategy. Success now means a source-backed, statically reviewed specification with native unknowns explicit. Every proposed case below is UNEXECUTED.

The [window and capability boundary map](6E_NATIVE_SOURCE_EVIDENCE_WINDOW_20261012.md) separates later `native-intake-binding`, `native-publication-bridge` and `historical-continuity`. Only this first provider receives a specification. No new execution plan/task list or source/test file is released. All418 accepted Python files, approved contracts, old plans, dirty/untracked work and old source/target/input/result/control pins/UNKNOWN liabilities remain held.

## Existing evidence and what it does not prove

The [accepted constructed typed adapter](6E_TYPED_NATIVE_EVENT_ADAPTER.md) is complete:12,203passes+exact3skips, all12,206case-sensitive identities=10,872old+1,334new, accepted09:59:34UTC. Its report and [terminal receipt](../logs/typed_native_event_terminal_acceptance_20261012_1.json) are closed evidence, not pending jobs. Do not rerun or poll them.

Source-only observations:

- [Existing member reader](../src/ai_trader/research/databento_6e_training_data.py), lines290–322: `archive.open` returns logical ZIP member contents. Here those contents are Zstd-encoded DBN bytes, **not ZIP-container bytes or ZIP-layer compressed bytes**. One default `DBNDecoder()` persists across concatenated Zstd frames. Reads are64KiB; decompressed feed pieces are at most1MiB.
- The existing3GiB decompressed guard is checked after `decompress(block)` returns. This is a cumulative acceptance bound, not evidence of a pre-allocation memory limit.
- The reader yields native objects before final frame termination, `decoder.decode()`, empty-buffer and compressed-member SHA checks. The new provider's all-or-nothing positive return is proposed NEW behavior; it is not a claim that the old generator never mutates downstream state before a late failure.
- The old mapping check (lines273–287) requires daily GLBX.MDP3/mbo/6E.FUT declarations and one active end-exclusive dated mapping, but does not close complete codec/version/upgrade/stype/limit/partial/ts_out/ABI rules. That check and book/event processing belong to later composition, not this decoder provider.
- The old builder exhausts members before returning a cohort, but its receipt copies archive SHA from intake and its publication writes rows then manifest separately. Neither fresh whole-archive authentication nor filesystem transactional publication follows.

Installed text, not loaded native observations:

- Local `databento-dbn` metadata declares0.70.0 and `zstandard` metadata declares0.25.0. Their [DBN stub](../.venv/Lib/site-packages/databento_dbn/_lib.pyi), [initialization](../.venv/Lib/site-packages/databento_dbn/__init__.py), [v3 aliases](../.venv/Lib/site-packages/databento_dbn/v3.py), [mapping types](../.venv/Lib/site-packages/databento_dbn/metadata.py) and [Zstd stub](../.venv/Lib/site-packages/zstandard/__init__.pyi) were read as text. No import, native method, constructor, decoder or protected input was used.
- DBNDecoder exposes constructor/buffer/decode/write/write_and_decode; no EOF/finalize/finish API is exposed. Empty `buffer()` is a necessary proposed check, **not sufficient evidence of complete wire input or compressed EOF**.
- DBN docstrings say default UPGRADE, while the exposed policy variants are AS_IS/UPGRADE_TO_V2/UPGRADE_TO_V3. Default policy remains unresolved; explicitly selected AS_IS is mandatory for this proposal. `v3.py` reexports native classes and does not prove arbitrary input was v3.
- With metadata present, the stub says constructor `input_version` and `ts_out` controls are only needed for metadata-less input. Passing a value is not proof that it overrides or verifies the actual header; native tests must establish actual behavior.
- Metadata end/limit constructors accept None but getters are annotated int; unset numeric representations are not supplied. MBO `ts_out` is documented to return UNDEF_TIMESTAMP when unset, but the constant's numeric value is only an int declaration in the inspected text.
- RecordHeader/length/padding are not exposed MBO properties. `record_size()`, `ts_index`, `__bytes__`, type hints and class-field declarations do not establish original header bytes, field widths, raw length word, native integer bounds, original offsets or reserialization equality.
- Zstd annotations expose eof/unused_data/unconsumed_tail and bounded-reader/decompress options, but do not prove pre-allocation bounds, frame completeness, trailing-byte or unknown-content-size behavior. Those require the later closed profile.

These facts are grounded in the local snapshot, not authoritative wire-layout documentation, installed-package authenticity, dependency security health or loaded-runtime authentication. No remote documentation was fetched in this offline window.

## Five blocked native-proof gates

**This proposal is not implementation-ready until every gate is separately closed and prospectively pinned.** No caller-supplied receipt or passing encoder/decoder self-roundtrip can replace these obligations.

| Gate | Evidence needed in a later separately authorized scope |
| --- | --- |
| P1 — v3 wire/framing profile | An authoritative, version-bound header/record layout; independent complete-byte fixtures; exact type/length/padding/extension rules; a complete-input framing verifier that detects truncated final metadata/records and unexplained trailing bytes even when the native buffer is empty. |
| P2 — native representations | Independently verified integer domains, enum/index/string rules, Metadata unset end/limit, all mapping/date/list rules, present/absent ts_out, reported record_size vs original wire size and derived ts_index. No guessed numeric constants or invented length=record_size/4 rule. |
| P3 — decompression termination/resources | Complete concatenated-frame handling, forbidden trailing/skippable/dictionary modes, boundary crossing, reliable terminal EOF and fail-closed expansion/window limits before unsafe allocation; explicit native failure/time/memory containment for later experiments. |
| P4 — native decode/profile context | Exact explicit constructor policy, actual observed input/yielded versions, complete header occurrence/order, unsupported types, chunk/frame-invariant semantic output and native error behavior under the closed profile. |
| P5 — runtime identity and registration | Fresh independent expected codec/artifact/proof-case pins and owned experimental command/executable/creation/parent metadata; observed loaded extension/runtime identities consistent with the registered profile. This is runtime consistency, not full import-graph/source/feed authentication. |

P1 requires independent evidence about the format, not just native encode→decode agreement. P3 is not closed by checking output length after a native allocation. If an installed API cannot establish a required guarantee, refuse the profile and retain the blocker; do not silently weaken the bar or install/upgrade/bypass protections. All five gates are UNEXECUTED here.

A closed profile must record exact source references, independently authored byte/body oracles, complete passed/failed identities and proof-case/resource evidence, artifact manifest, expected enum/domain/absence/layout rules and a canonical profile SHA. No open values such as “whatever the library returns”, automatic defaults, guessed sentinel values or caller-defined callbacks are allowed. Once the profile is actually closed, its exact values must be incorporated into a fresh reviewed contract revision before any provider implementation release. This document intentionally does not manufacture an ABI registry.

## Proposed boundary, interfaces and structure

The provider has no path/archive/network/CLI/writer/resume/book/model/order input. Input is exact immutable `bytes`, not bytearray, memoryview, a source path, iterator, ZIP object or a native caller-supplied object list. Each computation creates fresh native state and retains complete bytes/order; no checkpoint adoption, cursor continuation or successful-prefix result.

Proposed later paths, currently absent/unreleased:

- `src/ai_trader/research/six_e_native_member_decode_evidence.py`
- `tests/test_six_e_native_member_decode_evidence.py`
- This contract and the existing dated window under `docs/`; no replacement of old task files.

Five proposed public APIs:

```python
protocol() -> dict
protocol_sha256() -> str
context_sha256(context, *, expected_protocol_sha256) -> str

decode_member(member_bytes, context, *,
    expected_protocol_sha256, expected_profile_sha256,
    expected_runtime_manifest_sha256, expected_member_sha256,
    expected_metadata_sha256) -> MemberDecodeEvidence

verify(evidence, member_bytes, context, *,
    expected_protocol_sha256, expected_profile_sha256,
    expected_runtime_manifest_sha256, expected_member_sha256,
    expected_metadata_sha256, expected_evidence_sha256) -> None
```

All expected pins are mandatory keyword-only exact lowercase64-character ASCII SHA256 hex. Public protocol version is proposed `native_member_decode_evidence_v1`; scope `invented_complete_in_memory_native_member_consistency_only`; result status `complete_member_consistency_not_source_authentication`. “Protocol” here is an interface proposal, not a verified native ABI.

Context contains exact fields `profile_id, member_compression, input_version, upgrade_policy, expected_ts_out`. Narrow proposed choices are ZSTD_CONCAT,3,AS_IS and an exact bool. `profile_id` must name the later closed fixed profile, not a caller-injected registry. Protocol/profile/loaded-runtime expectations remain separate pins. The input version is a claim to check against independently framed bytes and the actual Metadata observation, not a value assumed to force a metadata-bearing decoder.

Style example is a declaration, not executed code:

```python
@dataclass(frozen=True, slots=True)
class MemberDecodeContext:
    profile_id: str
    member_compression: str
    input_version: int
    upgrade_policy: str
    expected_ts_out: bool
```

Use exact frozen/slotted records, explicit field projections and consistent ValueError refusal. Do not reflect dataclasses or serialize pretty timestamps/prices to define a raw oracle. No truthy bool/int alias, foreign object `__str__`, native-object caller hook or mutable exported alias may silently determine validation.

## Proposed complete projections

The future native profile, not current annotations, fixes all conversion/domain rules. The following named *logical observation* schemas are proposed; they are not a native memory-layout specification.

**MetadataProjection** has thirteen fields: version,dataset,schema,start,end_observed,limit_observed,stype_in,stype_out,ts_out,symbols,partial,not_found,mappings. Native end/limit integers are retained exactly as observed; neither is silently converted to None/zero. schema must be the profile's exact MBO schema observation. symbols/partial/not_found preserve every occurrence and list order, including duplicates.

Mappings in MetadataProjection retain every group/interval actually exposed by the native getter, including unrelated/inactive declarations. Getter groups are canonically sorted by raw-symbol string because the API exposes a dictionary; each interval sequence and duplicates remain in observed order. This is NOT a claim that the getter dictionary preserves original wire group occurrences or ordering. The complete independent DBN framing report separately retains every original ordered wire mapping group and interval. This narrow profile requires duplicate wire raw-symbol group keys to refuse, even if the SDK silently coalesces them; interval count/order/multiplicity must also agree with the profile-proven getter translation. Never hide a lossy dictionary projection behind a full-byte hash. MappingInterval retains the three exposed start_date,end_date,symbol fields; exact native date rules remain P2-blocked. Unknown projection fields refuse. No target contract/day/mapped-ID admission is performed here.

**MboObservation** has seventeen fields: rtype,publisher_id,instrument_id,ts_event,order_id,price,size,action,side,ts_recv,flags,channel_id,ts_in_delta,sequence,ts_out_observed,record_size_observed,ts_index_observed. price remains the raw integer, not pretty_price/float. ts_index is retained as a derived observation but **never used for sorting**. record_size is an observed method result, not an inferred original length field.

Enum observations retain a verified native representation tag, exact logical symbol and native code where the closed profile proves it is exposed. Exact native enum vs exact string observations cannot be confused by a generic `str()` or `int()` coercion. The closed profile must specify each allowed getter path and exact canonical body; until P2 closes, enum/absence/layout serialization values remain blocked, not guessed. The original wire bytes remain independently bound.

Absent ts_out requires the profile-proven actual native observation to be retained alongside the Metadata presence mode. It is not automatically the accepted payload layer's None convention. Present ts_out is retained unchanged. Native unsigned/undefined timestamps cannot be clamped, wrapped or widened into the held signed64 transport; a future bridge must explicitly refuse an unrepresentable transport. This provider does not call or alter cursor/payload/typed-adapter APIs.

**DecodedOccurrence** contains one-based decoded_position,kind,wire_span_ordinal,projection and projection_sha256. Exactly one first Metadata is position1; positions2..N are every yielded MBO in original decoder order. A duplicate/missing header or unsupported non-MBO type refuses the complete result, including at the final occurrence. No target/foreign filtering, target candidate ordinal, successful book ordinal, event, quote or publication is manufactured. decoded_position is not a byte offset. Its wire_span_ordinal links to a separate, later profile-proven decompressed-wire span; never infer that span from a yield/feed-chunk position or record_size. Native MBO from any instrument remains represented.

**Complete independent framing reports** are required output, not optional status summaries:

- ZstdFramingReport contains compressed_bytes,compressed_sha256,decompressed_bytes,decompressed_sha256,frames,report_sha256. Each FrameSpan contains frame_ordinal,compressed_start,compressed_end,decompressed_start,decompressed_end,compressed_span_sha256,decompressed_span_sha256. Both coordinates are explicitly zero-based half-open offsets within the exact supplied member-content string and exact concatenated decompressed string, respectively. Frame ledgers cover each string from0toitsfull length exactly once, without gaps/overlap/extra/unexplained tail; nonempty frame output is required. Positions come ONLY from the later P3-proven framing mechanism, not invented read-loop/chunk accounting. Dictionary/skippable/trailing rules remain P3 proof blockers.
- DbnFramingReport contains decompressed_bytes,decompressed_sha256,spans,report_sha256. Each WireSpan contains wire_span_ordinal,kind,decompressed_start,decompressed_end,wire_sha256,wire_fields,wire_fields_sha256. Complete original header/record boundaries cover the full decompressed string without gaps/overlap/extra data. wire_fields is the complete ordered profile-defined wire body, including original mapping occurrence/order, optional extensions and reserved/padding rules; its exact unavailable native layout/schema remains P1/P2-blocked and must be frozen in the reviewed profile revision. Original wire bodies cannot be replaced by native getters or reserialization.
- Every decoded occurrence links bijectively to one span of the same kind/order. All raw logical fields must match the native observation through the exact P2-proven translation, including signedness, enum/absence conventions and derived observations. Equal counts, SHA labels or terminal statuses alone are insufficient. Header getter-map canonical sorting must not erase original wire occurrences from the framing report. Wire reports retain raw-span hashes and complete independently interpreted bodies; verification rebuilds both from the original immutable bytes.

These are proposed evidence-envelope fields, not already proven offset/layout facts. Decoded ordinals, P3 compressed-member coordinates, P1 decompressed-wire coordinates, native emission/feed chunks and ZIP coordinates are distinct namespaces. No ZIP/archive offset is proposed; actual per-span values and interpretations remain BLOCKED until P1–P3 close.

**TerminalEvidence** contains compressed_bytes,compressed_sha256,decompressed_bytes,decompressed_sha256,frame_count,decoded_positions,metadata_count,mbo_count,dbn_remaining_buffer_bytes,zstd_framing_sha256,dbn_framing_sha256,framing_status,zstd_status. Complete hashes identify the exact full supplied/decompressed strings, not an archive, authenticated feed or early publication. The later profile must specify exact terminal statuses and independent framing evidence representation; empty native buffer is only one necessary observation.

**MemberDecodeEvidence** contains status,protocol_sha256,profile_sha256,runtime_manifest,runtime_manifest_sha256,context_sha256,member_sha256,metadata_sha256,occurrences,zstd_framing,dbn_framing,terminal,authorities,evidence_sha256. It includes complete observations/counts/bodies, not selected totals. Evidence SHA is H(the complete named body excluding only evidence_sha256). There is no partial result or readiness/promotion flag.

H is SHA256 of UTF8 canonical JSON with sorted keys, separators comma/colon, ensure_ascii=True, allow_nan=False; named tuples project to lists only under explicit schema rules. Binary identity uses raw SHA256 of bytes, not the JSON encoding of a hash or reserialized native objects. The later profile must define all enum/date/native observations before canonical body/pin values can be locked.

### Exact hash namespaces and exclusions

All canonical bodies are complete named bodies under the stated H rule; no implicit version/field omission, arbitrary sorted subset or own-digest cycle is allowed. The following namespaces are distinct even when a test happens to produce matching digests:

| Pin | Exact meaning |
| --- | --- |
| protocol_sha256 | H(the complete literal public protocol body): version,scope,status,context_fields,metadata_fields,mbo_fields,occurrence_fields,zstd_framing_fields,dbn_framing_fields,terminal_fields,evidence_fields,authority_names,limits,canonicalization,decoder_options. Lists retain specified order. There is no self-hash field in this body. Exact native-dependent nested schemas/values must be added/frozen by the reviewed P1–P5 profile revision before implementation, not silently chosen by code. |
| context_sha256 | H(the complete five-field MemberDecodeContext body), with no omitted field and no self-hash field. |
| profile_sha256 | H(the COMPLETE closed profile_body fixed by P1–P5, excluding only a stored profile_sha256 if its envelope has one). All source/layout/enum/domain/absence/termination/bounding rules, proof-case identities/resource observations and artifact expectations belong to that later exact body. Its currently unavailable schema/values must be frozen in the reviewed contract revision; an opaque caller pin is not profile closure. |
| runtime_manifest_sha256 | H(the complete observed RuntimeManifest body), without attempt/PID/time fields or a self-hash. Proposed top-level fields are schema,interpreter,packages,artifacts. interpreter has implementation,version,executable_sha256; each complete sorted package entry has name,version,metadata_sha256; each complete sorted artifact entry has logical_id,kind,raw_bytes,raw_sha256. P5 freezes the exact required recognized package/artifact set, fixed provenance/read/loaded-association rules and schema value. Submitted/missing/extra entries refuse; arbitrary payload paths are not an artifact registry. This bounded manifest is identity consistency for that registered set, not full DLL/import-graph/memory/source authentication. Owned attempt/command/executable/creation/parent evidence is stored separately by the experimental harness and never makes deterministic member identity depend on a new PID or time. |
| expected_member_sha256/member_sha256/compressed_sha256 | RAW SHA256 of the entire exact supplied Zstd-encoded member-content bytes; not ZIP/container/ZIP-layer bytes. |
| decompressed_sha256 | RAW SHA256 of the entire exact concatenated decompressed DBN byte string. |
| projection_sha256 | H(the complete named logical MetadataProjection or MboObservation body). |
| expected_metadata_sha256/metadata_sha256 | H(the complete logical MetadataProjection body), identical to the first decoded occurrence's projection_sha256; NOT the original wire-header bytes hash. |
| wire_sha256 | RAW SHA256 of the exact original decompressed-string span selected by the independently proven framer; the first Metadata span is the original framed-header byte hash, separately named. |
| wire_fields_sha256 | H(the complete profile-defined independently interpreted original wire_fields body), distinct from native logical projection hashing. |
| compressed_span_sha256/decompressed_span_sha256 | RAW SHA256 of the corresponding complete original FrameSpan byte slice in the separately named compressed/decompressed coordinate space. |
| report_sha256/zstd_framing_sha256/dbn_framing_sha256 | H(the respective COMPLETE framing report body), excluding only its own report_sha256; terminal references equal those exact report identities. |
| evidence_sha256/expected_evidence_sha256 | H(the complete MemberDecodeEvidence body), excluding ONLY evidence_sha256; includes full observed runtime manifest, every occurrence/projection, both full framing reports, terminal facts and every literal-false authority. |

All count/length/hash/header/occurrence/span/report/runtime references must reconcile exactly. A logical Metadata pin cannot substitute for an original wire-header pin, and no complete terminal/member/runtime hash is inserted into a causal publication identity. The protocol/profile/native-dependent representations are still proposals: attaching a profile SHA alone is insufficient. Closure requires a reviewed exact schema/status/representation revision.

## Required phase order and complete refusal

1. Validate *all* expected-pin syntaxes, known interface/profile equality, exact Context and the complete independently held runtime/profile registration using non-native declaration checks. Verify the P5-registered recognized on-disk/static artifact identities before native load. This is not already-loaded-runtime proof. No arbitrary path/URL, callback, environment variable or command comes from source bytes or submitted evidence.
2. Validate exact bytes and complete input length; compare raw full-member SHA with the held expectation before decode. A bad complete expected pin refuses without opening any archive or adopting any yielded prefix.
3. Native module import/extension initialization is itself native execution in the later authorized, contained P5 scope, not code-free preflight. After controlled load (or for an already-loaded component), verify the actual registered loaded Zstd/DBN identity associations and complete RuntimeManifest equality BEFORE the first corresponding native constructor/parser invocation. P5 must define fail-closed behavior for import/load/identity uncertainty and check/use mutation; no unverifiable component is invoked. Then, under the later proven P3 mechanism, traverse the entire compressed content with bounded expansion, all concatenated frame termination and no unexplained tail. Preserve one continuous decompressed DBN string, complete length/hash and the COMPLETE P3 ZstdFramingReport with independently proven frame spans. An empty/partial/skippable/unsupported-dictionary/trailing-junk member refuses under the narrow proposed profile.
4. P1's independently verified framing must establish one complete v3 metadata header and every complete supported MBO structure in the full decompressed string, including ts_out mode/extensions and capacity. Build the COMPLETE DbnFramingReport/wire bodies with exact no-gap/no-extra coverage, reject duplicate wire raw-symbol mapping group keys under this narrow profile, and retain all remaining original mapping occurrences/order. It cannot be replaced by native buffer emptiness or encoder roundtrips. This is framing validation, not a metadata-only numerical-read barrier.
5. Reconfirm the actual registered loaded DBN codec context before its first constructor/parser call (this is NOT the first loaded-context check after decompression), and create fresh DBNDecoder with explicit has_metadata=True,upgrade_policy=AS_IS,compression=NONE,input_version=None and the registered expected ts_out constructor choice. That argument does not stand in for the actual header. One decoder persists across the entire decompressed member; concatenated frames do not reset it.
6. Preserve all decoder outputs in original order. Fully validate/project the first actual Metadata and its profile/context/expected metadata hash before the wrapper reads any later MBO raw property. A native batch may already contain parsed Metadata and records: **this wrapper ordering is not proof that the native decoder did not parse record values earlier**. No whole-stream native metadata-before-values claim is made.
7. Project every exact supported MBO occurrence with profile-proven domains/enum/absence/size/index rules. Bind each occurrence to its exact independently proven wire span and compare EVERY complete profile-interpreted raw field/native translation, not only counts, retaining the full framing reports and complete positions; unsupported final types or values refuse all output. Native allocation before wrapper count checks remains a resource-proof issue, not a hidden guarantee.
8. After full input traversal, final decode and terminal framing/frame checks, require no native buffered bytes, exact independent occurrence/span/count/header/body/tail agreement across both COMPLETE framing reports and native observations, full registered RuntimeManifest equality, complete output body/caps and all literal-false authorities. Only then return the complete result. No callback/public yield/publish occurs before these guards.
9. Submitted verification checks all outer Context/status/pins/counts/occurrence shapes/authority literals and full canonical submitted-body constraints, then independently reconstructs from the original immutable member with fresh state and compares every complete body/hash. A same hash claim or subset summary does not short-circuit reconstruction.

Malformed shape/type/value/native codec failures refuse with ValueError, without logging full bytes/price fields or returning partial success. Do not catch AssertionError from intentional read sentinels; KeyboardInterrupt/SystemExit and critical resource failures are not disguised as successful refusal. Exact diagnostic wording is not promised. Native failures must be contained under the later registered experiment/resource policy; no security bypass or unrelated process termination.

## Proposed capacities and honest resource claims

Proposed complete-member acceptance limits:

| Resource | Limit |
| --- | ---: |
| Supplied compressed member bytes | 262,144 |
| Complete decompressed DBN bytes | 1,048,576 |
| Concatenated nonempty frames | 1..16 |
| Complete decoded positions including first Metadata | 2..128 |
| symbols/partial/not_found entries, each complete list | 0..16 |
| Mapping groups / total intervals | 0..16 / 0..32 |
| Any projected metadata text, UTF8 bytes per complete value | 128 |
| Complete canonical Context / result body | 65,536 / 1,048,576 |

Equality is allowed; the first excess refuses all output. These are new narrow **invented-member limits**, not historical-session capacity and not inherited overrides. No public-envelope measurement has run. No thinning, truncation, splitting, resampling, omitting foreign records, relabeling history synthetic or retrying a shorter successful prefix.

Input/output limits do not by themselves establish native peak allocation or CPU bounds. Neither old post-expansion3GiB checks nor Zstd option names prove pre-allocation safety. P3 requires a specific reviewed, measured and registered bounding/containment mechanism before a native experiment or public implementation release. A future experimental harness needs explicit wall-time/memory budgets, exact owned command/executable/creation/parent records and exact-owned shutdown rules; it is not created here. No process or filesystem hook is added to the public byte-only API.

For IDENTICAL supplied bytes/context/profile/runtime manifest, different feed-chunk partitions may affect diagnostic batching but must not change any semantic decoded occurrence order/projection, original physical frame/wire-span ledger or COMPLETE evidence identity. Reframing/recompressing produces DIFFERENT supplied bytes and may preserve logical observations while changing frame_count, compressed frame spans/hash and complete evidence identity; that is a separate comparison, not an invariance requirement. Do not encode feed-chunk positions as original record offsets. A different compressed encoding can change compressed-member/evidence identity even when decompressed logical values agree; no source-equivalence assertion follows.

## Trust boundaries and all-false authorities

Untrusted bytes, Context and submitted evidence cross into a native parser and a consistency verifier. Threats are spoofed source/profile claims, altered bytes/enum/absence context, zip/Zstd expansion and pathological parser cost, unsupported/truncated tails, successful-prefix adoption, malicious paths/commands in text and retrospective complete-hash leakage. Mitigations are exact closed-profile/expected pins, immutable full inputs, independently verified framing, strict complete limits/contained native proof, no path/network/command interpretation and no partial positive result. Hashes prove equality against held expectations; they do not authenticate those expectations.

The proposed authority tuple has these exact28 ordered names, each literalFalse:

```text
source_authenticated, collection_receipt_authenticated,
native_runtime_authenticated, native_abi_authenticated,
native_wire_authenticated, native_header_authenticated,
native_eof_authenticated, feed_authenticated, calendar_authenticated,
historical_read_authorized, historical_validation_authorized,
book_acceptance_authorized, event_acceptance_authorized,
feature_acceptance_authorized, account_authorized, funding_authorized,
receipt_authorized, cash_authorized, margin_authorized, risk_authorized,
storage_authorized, resume_authorized, execution_authorized,
trading_authorized, training_authorized, scoring_authorized,
independent_validation_authorized, promotion_authorized
```

Terminal success observations do not turn any authorityTrue. Same native outputs/hash/profile can be coherently replaced by a caller with its expectations; this is unauthenticated and not detected. Native runtime identity consistency is not full DLL/import-graph authentication or proof of package security. No authentication service, signing key, credentials, broker or permissions system is designed here.

Complete source/hash/EOF checks are terminal facts. They cannot be inserted into an earlier causal policy/publication seed. No causal publication interface is released by this provider; the later bridge must bind protocol/context/header and actually consumed prefix while excluding future terminal/member/total state. Native decode consistency establishes no book/event/feature parity, original day initialization, calendar, historical cohort, account continuity, broker economics, profitable strategy or model improvement.

## Fifteen proposed acceptance groups — UNEXECUTED

| Group | Independent required observation |
| --- | --- |
| A1 Context/preflight | All pin syntaxes, fixed closed profile, exact Context and registered codec expectations refuse before native call; no default upgrade or arbitrary callbacks/paths. |
| A2 Complete input | Exact immutable bytes only, empty/oversized/hash-mismatched source refuses; no ZIP/container/member identity substitution. |
| A3 Zstd completeness | One/multiple complete frames, cross-frame DBN structures, truncated final frame, trailing junk, empty/skippable/dictionary modes and exact frame-count rules. |
| A4 Expansion/resources | At/over each boundary, unknown claimed content size and expansion attacks; prove the actual P3 mechanism, not only a post-allocation length check. |
| A5 Wire framing | Independent literal full header/record fixtures; incomplete header/record and unsupported/tail structures refuse even when native buffer happens empty. |
| A6 Explicit codec | V3/AS_IS/NONE/metadata-present choices and actual observed versions; older/future/implicit-upgrade/ts_out mismatches refuse under the closed profile. |
| A7 Native header | All13logical properties, unset end/limit, each exact profile-proven schema/stype observation (including permitted None/string/native-enum distinctions), getter lists/dictionaries vs original ordered wire mapping occurrences; duplicate wire-group refusal, full interval multiplicity/order, dates and logical Metadata hash distinct from raw header-byte hash. |
| A8 Complete positions | Exactly one first Metadata, every MBO and foreign occurrence retained; missing/duplicate/late header and unsupported final decoded type refuse whole result. |
| A9 Raw observations | All17MBO observations, native enum vs string, signed/unsigned boundaries, undefined clocks/prices, present/absent ts_out; no pretty/float/datetime substitution. |
| A10 Size/index separation | Observed record_size/derived ts_index vs independently framed original bytes; no guessed native length or sorting/byte-offset assertion. |
| A11 Chunk invariance | Identical supplied bytes/context under different feed partitions give identical complete evidence/physical framing ledgers; differently reframed/recompressed bytes may preserve logical observations while changing frame_count, compressed hash/spans and whole identity. No duplicate/drop from buffering. |
| A12 Terminal atomicity | Late frame/hash/header/record/tail/count failure returns nothing; no public callback/yield/cache/prefix adoption; fresh repetition requires full checks. |
| A13 Submitted verification | Mutate every Context/projection/count/status/authority/body/hash/type family, including equal-canonical-value aliases; complete reconstruction rejects it. |
| A14 Identity/no hindsight | Raw-vs-decompressed-vs-projection identities stay separate; source encoding changes/full terminal hashes never become earlier publication authority; no historical transport coercion. |
| A15 Full qualified handoff | All new identities from actual independent collection, every12,206held old identity and exact3held skip XML representations, stable whole/pair/package/contracts/native-profile pins, native-owned exit/resource evidence, independent review and accurate limitations. No guessed new count or skipped mandatory native tests. |

Expected native/wire/projection bodies must be independent literal format/reference oracles, not production serializers, reflection, native encode→decode self-consistency or returned observations adopted as truth. Native encoder-generated fixtures may be supplemental cases only after a later explicit native release. A controlled mock can demonstrate wrapper phase order but cannot close P1–P5 or count as native proof. New mandatory native tests must not be skipped to make a cohort green. Existing three held optional skips are a separate old-suite fact.

## Commands, verification and three-tier boundaries

The current documentation verification is read-only source comparison, exact held-file preservation, local Markdown target checking and independent static contract review. **No runtime commands below are launched now.** Future templates require a separately authorized implementation/native-experiment scope, closed P1–P5, stable writers and fresh complete prospective registration; report suffixes must be fresh/checked, counts collected rather than guessed:

```powershell
.venv/Scripts/python.exe -B -m pytest -q tests/test_six_e_native_member_decode_evidence.py --junitxml=logs/native_member_focused_FRESH.xml
.venv/Scripts/python.exe -B -m pytest -q --junitxml=logs/project_full_suite_native_member_FRESH.xml
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/python.exe -m ruff format --check src/ai_trader/research/six_e_native_member_decode_evidence.py tests/test_six_e_native_member_decode_evidence.py
```

Do not run FRESH literally or use these as an execution plan. Root owns future launches and complete reconciliation; independent authors hold every file during every check. Full JUnit declared totals/every ordinal identity/exact skip XML/raw hashes/tool-owned exits/whole-old-new-package-contract-profile-runtime pins are necessary. Passing this proposed provider still is not historical validation or deployment.

- **Always:** preserve all held code/contracts/plans/UNKNOWN; ground facts in exact sources; record proposed behavior and uncertainty; require full no-subset identity/body/resource checks and allfalse authorities.
- **Separate scope first:** native constructor/codec/resource experiments, authoritative wire evidence acquisition, dependencies/runtime changes, implementation plans/code, actual source/archive intake, calendar/history/publication/account integration, tests/models/training/scoring/promotion. Routine approval waiver never turns these into this window's work.
- **Never:** raw/reserved/historical source reads or old packets here; decoder/default/ABI/source-authentication claims from annotations; unsafe allocation claims from post-checks; implicit ts_out/limit/length normalization; omitted foreign/tail data; relabel/thin/split history; future-terminal stitching; latefill/UNKNOWN cancellation/reconciliation/reseed/dailyreset/subsetscoring/oldfillfiltering; credentials/broker/orders, Windows/security bypass or Graphify scans.

## Open questions, alternatives and stopping point

No factual native uncertainty is “answered” by this document: P1–P5 remain explicit release blockers. The proposed API/body/budget choices are reviewable architecture, not observed capacity. Before implementing, native proof closure may require a separate contract revision when exact enum/domain/absence/framing/bounding rules are known.

Rejected alternatives: importing/calling the old historical builder (unreleased sources/default codec/state/labels); wrapping its generator and calling an early prefix success (late checks remain); treating native object bytes as original bytes (unproved lossless/layout equivalence); treating an empty buffer as EOF (unsupported); connecting directly to the typed adapter by inventing a length/None/genesis/instrument/window/cap fit (breaks held contracts); a broad archive+decoder+feature+account implementation (bundles independent gates).

Save and present this PROPOSED specification, its unresolved proof gates and the capability map, then stop before execution planning/tasks/code. No heartbeat, static review or broad access setting is a native/history release. At the unchanged15:12:16UTC deadline launch nothing, summarize verified documentation/gaps, delete the follow-up and stop.
