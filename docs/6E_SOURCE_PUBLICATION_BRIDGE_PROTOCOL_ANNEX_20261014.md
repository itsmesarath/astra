# Member-publication bridge literal protocol annex — 2026-10-14

## Status and scope

**Prepared documentation / pending independent packet review; bridge remains unimplemented.** This annex closes the representation choices deliberately deferred by sections 7 and 12 of the [reviewed bridge contract](6E_SOURCE_PUBLICATION_BRIDGE_CONTRACT_20261013.md). Its companion is the complete [literal protocol packet](6E_SOURCE_PUBLICATION_BRIDGE_PROTOCOL_20261014.json). The root's newly recorded six-hour continuation is 2026-10-14T07:33:18Z–13:33:18Z; this author is released only for these two documentation files. This work does not execute a native provider, import project/test Python, run a test or alter an accepted dependency.

The packet describes the same bounded capability: complete supplied **invented in-memory** native-member bytes associated with unchanged typed event/37-feature reconstruction and separate causal native-prefix/publication links. It does not introduce file/archive/network intake, historical data, source authentication, accounts, economics, model work or a broader native provider. All previous false-authority and UNKNOWN-liability boundaries remain intact.

No accepted contract is overwritten. Where the old contract says that the new protocol hash is not yet an artifact, that remains the earlier drafting state; this new packet is preparation for later root canonicalization, independent review and registration, not implementation or acceptance evidence.

## Exact packet shape

The packet has exactly eleven top-level keys:

```text
version, scope, status, dataclass_fields, dependencies, fixed_scope,
projection_rules, limits, hash_schemes, phase_order, authority_names
```

Object member order is not semantic under the specified sorted-key canonicalization. Every array order is semantic: four record field lists, the public function argument lists, mapping and raw-field projection lists, phase steps, hash-body field definitions, dependency-defined field lists and authority names must remain intact. Pretty-print whitespace and a final text-file newline are not protocol semantics; the protocol digest is SHA256 of the complete canonical JSON body with **no trailing newline**.

`version`, `scope` and `status` exactly match contract sections 3 and 7. `dataclass_fields` contains only the four declared new records and their exact complete field order. `projection_rules[0]` fixes all five signatures, mandatory keyword-only expected pins, return contracts, exact built-in types and frozen/slotted records. No public field, optional default, caller-selected profile/protocol, external path or callback has been added.

`dependencies` contains exactly the complete native, adapter, binding and cursor protocol **bodies**, followed by the three fixed profile/runtime/execution manifest identities. These are not short summaries or digest-only substitutes. The packet also records each complete dependency protocol's canonical digest in `hash_schemes.dependency_protocols`. That redundant expectation is deliberate: later interface acceptance must establish the exact bodies and their complete canonical identities, not merely a self-consistent new outer digest.

## Dependency provenance and literal construction

The preparation reads source text and the fixed native JSON resource. It does not call production `protocol()`, execute existing test helpers, import dataclasses or infer declarations through reflection. The pure PowerShell documentation assembly expanded only named literal definitions into JSON, retaining all integer digits and enum/schema strings. Three pure dependency protocols were independently expanded a second time from the existing test author's literal expectations and produced the same complete canonical hashes.

| Dependency | Complete source-text definition | Independent corroboration / retained identity |
| --- | --- | --- |
| Native | [_native_member_protocol_v1.json](../src/ai_trader/research/_native_member_protocol_v1.json), the entire 31,384-byte resource, including its complete `schemas` registry | [_native_member_types.py](../src/ai_trader/research/_native_member_types.py), `_PROTOCOL_SHA` at line 751 and `_resource`/`protocol_body` at lines 840–854; retained native hash below |
| Cursor | [six_e_native_cursor_metadata.py](../src/ai_trader/research/six_e_native_cursor_metadata.py), `_flags` lines 174–204 and `_protocol_body` lines 207–232 | [independent adapter tests](../tests/test_six_e_typed_native_event_adapter.py), `CURSOR_FLAGS` lines 34–61 and `expected_cursor_protocol` lines 312–337; also [original cursor tests](../tests/test_six_e_native_cursor_metadata.py) `_protocol_body` at line 75 |
| Binding | [six_e_record_payload_binding.py](../src/ai_trader/research/six_e_record_payload_binding.py), `_flags` lines 128–161 and `_protocol_body` lines 164–268 | [independent adapter tests](../tests/test_six_e_typed_native_event_adapter.py), `RAW_FIELDS`, `BINDING_FLAGS` and `expected_binding_protocol` lines 340–411; also [original binding tests](../tests/test_six_e_record_payload_binding.py) at lines 164–218 |
| Adapter | [six_e_typed_native_event_adapter.py](../src/ai_trader/research/six_e_typed_native_event_adapter.py), `_flags` lines 834–870, `_feature_names` lines 873–912, `_schema_fields` lines 915–1087 and `_protocol_body` lines 1090–1187 | [independent adapter tests](../tests/test_six_e_typed_native_event_adapter.py), `SCHEMAS`, `FEATURE_NAMES`, `ADAPTER_FLAGS` and `expected_protocol` lines 414–511 |

Exact dependency canonical hashes obtained by the source-text/document path, to be independently confirmed by root before implementation:

| Body | SHA256 |
| --- | --- |
| Native — retained fixed-resource identity | `baef653d21535c864a889e1299332b1b182421cbd154cd3247d81705f10133e1` |
| Cursor — both independent literal expansions agree | `1923a5d70b9bfd90a08329f882da35850b3ce522d5e22ee9d8d1442043c0d5c1` |
| Binding — both independent literal expansions agree | `8781ece9e9bc6c299dfa8127da77a1a9668aa9b61b4912d062c911ef5fe97564` |
| Adapter — both independent literal expansions agree | `d4236573e06080830247ebfcc843c42b39333a5f2b3a9cdbfb1f344483eb7cef` |

Expansion order is cursor → binding → adapter, because the latter two contain the earlier protocol hashes. The native body is a separate fixed-resource branch. Source-defined authority dictionaries retain all 26 cursor, 31 binding and 34 adapter flags. The new/native ordered authority list retains all 28 names. All 37 feature names, all fifteen adapter dataclass field lists, all nine numerical-rule source pins, complete binding raw-field bounds and complete native schema definitions remain present. The nine numerical producers are reference text only; they were not imported.

The initial temporary PowerShell helper name `H` collided with the shell's `Get-History` alias. Renaming it to `Get-BridgeHash` resolved the documentation-command issue before output was used. No project code, source file, native runtime or security setting was modified by that failed command. It is not a RED/GREEN behavior study.

## Representation decisions

### 1. Fixed scope is data, not a caller policy

`fixed_scope` carries the exact fixed day, contract, dataset/schema, parent symbol, empty symbol exceptions, half-open warmup/publication times, native version/upgrade/profile/compression, symbology codes/names/text, explicit limit representation and both ts_out modes. Nanosecond integers remain decimal JSON integer tokens, never floating-point approximations. In particular, `1743984000000000000`, signed-int64 boundaries and `18446744073709551615` retain every digit.

The new `projection_rules` is an ordered list of named rule objects. Stable rule IDs are explanatory literal protocol commitments, not dispatch hooks. The packet is not a generic caller-supplied rules engine. Every rule comes from the reviewed contract; implementation must still enforce the exact declared types, fields, semantic equality and public dependency behavior.

Wire mapping order is retained for the old `DeclaredHeader`. Logical Metadata's separately sorted mapping groups remain in complete native evidence. A raw mapping date converts to a canonical ISO date only after exact valid-calendar/range checks; each interval has start strictly before end, but no new global interval sorting or non-overlap policy is invented. Leading decimal zeros in an admitted target symbol remain in the declaration. The unchanged public cursor chooses the numeric target; no instrument-1 substitution occurs.

### 2. Dynamic value selectors are exact schema instructions, not unresolved pins

Values such as `checked_complete_BridgeContext_sha256`, `actual_admitted_metadata_ts_out_bool` and `DecodedOccurrence.projection_sha256` describe the source of a per-input value in a precisely named schema position. They are not placeholder SHA strings and are never serialized in place of actual caller-derived runtime values. Literal identity values for every fixed dependency/profile/runtime/execution reference are complete 64-character lowercase hashes.

For example, `hash_schemes.native_prefix_seed.body_fields` names the exact seven keys of the seed body and the origin of each value. The resulting seed body contains `domain`, not a key named `literal_domain`; the latter names this protocol's schema declaration. `native_prefix_link` defines exactly `domain` plus `link`, with the nine non-self-hash link fields. `publication_link` defines exactly `domain`, checked bridge protocol/context hashes and the eight non-self-hash publication-link fields. These are the exact bodies in contract section 7, not alternative hash formats.

The native source mapping uses `DecodedOccurrence` and same-position `WireSpan`, never `FrameSpan`; physical frame ends/hashes can include future records and are excluded from causal identity. New `NativePrefixLink.kind` retains `Metadata`/`MBO` case exactly. The first `previous_prefix_sha256` is the seed and later ones are the immediately preceding link hash. All native and old adapter prefixes remain distinct, and every new publication link joins the exact old publication position and ordinals.

### 3. Complete raw fields and absence semantics remain explicit

The raw-field list is in unchanged binding field order, with sixteen exact fields for every target and foreign occurrence. `record_size` derives from native `record_size_observed`, agreeing with `4 * wire.length_words` and the actual span; native `ts_index_observed` remains in the complete nested evidence. Wire-absent ts_out is None while its native observation is U64_MAX; only that absence branch becomes old None. Present U64_MAX is not absence and refuses the old signed-int64 intersection. Unknown ASCII controls remain exact characters; codes 128–255 refuse rather than becoming N. Wider old integer types never relax native U8/U16/U32/I32 constraints.

### 4. Scoped phases and atomic returns

The five replay steps and five verification steps are represented by ordered objects with explicit IDs. Replay's first metadata checks are not actual Metadata proof; the complete public provider establishes that proof. Verification's outer preflight guarantees only the new top envelope/pins/types/link structure/top flags. The public native verifier traverses the complete submitted native body before its fresh native dispatch. The adapter's stronger metadata-before-values guarantee remains local to the unchanged adapter API, after the fresh original fixture is derived. No global phase claim or private metadata bypass is introduced.

`adapter.fixture_sha256` performs complete reconstruction and finish. Therefore one positive bridge call contains exactly one public native-provider invocation and at most two complete pure adapter reconstructions; there is no cheap fixture-hash shortcut. A positive `verify` returns None only after complete public native and adapter reconstruction, all exact nested bodies, all new links and final outer equality. Operational provider failures stay operational; invariant, cancellation and memory exceptions are not converted into ordinary input refusal.

The test-only observer declaration repeats the reviewed narrow exception: intercept the unchanged private host's return/error seam only around an ordinary public call; original invoked once; arguments/return/exception/cleanup unchanged; retain the original complete receipt; restore the callable exactly. This literal rule is not implementation, an extra native invocation or permission to fabricate missing receipt fields.

### 5. Complete limits and canonicalization

Every old inner cap and every new outer cap is independently represented. The packet's 262,144-byte limit and both 4,194,304-byte outer evidence limits admit equality and refuse first excess. There is no historical-capacity or parent-containment claim. The inherited worker committed-memory/queried-CPU/work/teardown limits apply only to its unchanged worker; current native registration and full aggregate observations are later execution evidence.

New/native authority tuples project to ordered pair lists. Adapter/binding/cursor authority tuples and accepted sorted counter-pairs keep their specified dictionary projection. New canonicalization uses UTF-8, ensure_ascii=True, sort_keys=True, separators comma/colon, allow_nan=False and no newline. Runtime float handling must preserve the accepted Python serialization, finite values, negative zero and int-versus-float distinction; this preparation contains no new numerical output oracle and does not claim PowerShell serialization of floats is interchangeable.

Whole member/decompressed/frame/EOF/full-assessment/receipt/terminal identities stay out of causal links but remain bound by complete evidence. Full original bytes remain mandatory for verification and are not embedded in the deterministic BridgeEvidence. All nested own hashes are included; only the new outer own `evidence_sha256` is excluded from its body hash.

## Before implementation

Root must independently establish exact top keys, complete dependency bodies and hashes, all schema references, integer preservation, new canonical packet size/hash and correspondence to the reviewed contract. A separate static reviewer must accept the full packet and this annex. Any discovered mismatch must be corrected before source author release; a digest cannot make an incomplete or semantically different packet correct.

Remaining preparation includes complete independent invented wire/Metadata/cursor/binding/book/event/37-feature/terminal/bridge oracles, exact source/import/test/receipt registration, current regression-deadline support and credible runtime/reconciliation time. Neither the packet nor routine approval waiver changes accepted dependency files or permits deadline backdating, skipped old cases, raw/history access or another scope. All B1–B15 acceptance groups remain UNEXECUTED for the bridge. No new bridge implementation, execution result, source authentication, profitable policy or model improvement is claimed by this annex.
