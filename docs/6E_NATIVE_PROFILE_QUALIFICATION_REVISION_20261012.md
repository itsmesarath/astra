# Native-profile qualification revision — 2026-10-12

## Status and decision boundary

**CANDIDATE — PENDING COMPLETE QUALIFICATION/REGRESSION; NOT CLOSED.** This is the exact bounded proof-profile candidate for the new registered harness, not an implemented `native-member-witness` provider, a positive closed-profile receipt or authority to use historical inputs. The [active execution board](../tasks/native_profile_execution_20261012.md) and [proof window](6E_NATIVE_PROFILE_PROOF_WINDOW_20261012.md) control current progress. The human's six-hour renewal is **2026-10-12T13:59:46Z–19:59:46Z (20:59:46 Lisbon)**; this document does not renew that deadline.

The [approved source-evidence contract](6E_NATIVE_SOURCE_EVIDENCE_CONTRACT_20261012.md), [approved P1–P5 plan](../tasks/native_source_evidence_p1_p5_plan_20261012.md), all 418 accepted Python files, earlier contracts/plans and all old source/target/input/result/control pins/UNKNOWN liabilities remain unchanged. Their earlier UNEXECUTED/offline-only wording records the preceding scope; the later direct renewal releases official source retrieval and separately registered invented-input proof work, not archive/history/provider/account integration.

This revision records source-derived exact representations and the registered mechanism so a later closure decision cannot silently choose defaults or adopt returned values as its oracle. Complete native proof, frozen whole regressions, independent review and final pin/owned-exit reconciliation remain required. **Do not emit `closed_profile.json`, a positive closed-profile digest or a CLOSED revision while any required P1–P5 item remains unresolved.** A partial or failed attempt requires an explicitly incomplete/blocked receipt instead.

Snapshot for the evidence table below: root's complete boundary acceptance and capacity/source-partition acceptance through **2026-10-12T16:36:07Z**. Later supplements are PENDING until their actual registered results reconcile. This snapshot is not a claim to have rerun any completed test.

## Immutable references and independent inputs

The [reference decision packet](6E_NATIVE_PROFILE_REFERENCES_20261012_1.md) links the complete official source corpus. Fixed upstream identities are:

| Reference | Immutable identity | Used for |
| --- | --- | --- |
| Databento DBN v0.70.0 | `aa012adc6502e01b01d7b5c7836742dde21e93d8` | DBN v3 layout, FSM, native getter/enum/date translation |
| python-zstandard 0.25.0 | `7a77a7510b8ce068e4a103d29aea1b5ec829d8b6` | C backend reader, one-shot terminal behavior and allocation branches |
| Zstd v1.5.7 | `f8745da6ff1ad1e7bab384bd1f9d742439278e99` | Complete standard-frame/block format and reference decompressor |

Source identities are not proof that installed artifacts were built from those exact commits. Artifact equality, package declarations and finite codec observations are separate evidence; none authenticates the source/feed/build chain.

Independently authored invented packets, retained as complete bytes and bodies:

| Packet | Raw SHA256 | Contribution |
| --- | --- | --- |
| [Primary wire/format oracles](../tests/native_profile_oracles_20261012_1.py) | `48151a01cccf54df8815f934e160c2c75e848cbf82f6b04f4bdbcd54106b3c0a` | Full DBN wire/native bodies, all STypes, complete Zstd physical descriptors, raw/RLE/compressed match/Huffman/checksum and output-bound cases |
| [Known Action/Side oracles](../tests/native_profile_enum_oracles_20261012_1.py) | `7a6965b8a75ddc43d8a845a379d3edaa1d103c25221b6a9e426ca3f584161857` | 20 complete members: seven Actions and three Sides in both ts_out modes |
| [Composed oracles](../tests/native_profile_composed_oracles_20261012_1.py) | `4e05f037621cd3b5ac6fc96b45114da87f7633d0b4f41be0a386a0e457d2a8e5` | Three complete Zstd/DBN members, including a frame split inside the Metadata length integer |
| [Native direct negative oracles](../tests/native_profile_native_negative_oracles_20261012_1.py) | `634d320bfc7701dd8876627cb11b1d798c55ac8c7e9b15192b270994ecc18425` | 14 DBN malformed/partial controls, one complete-prefix identity distinction, three empty-frame controls and three one-shot terminal negatives |
| [Metadata/capacity oracles](../tests/native_profile_capacity_oracles_20261012_1.py) | `6b0513c82c54863f91c8221bc12fdbd623529da57d51ee1bb7f6a4ae9cedeb99` | Three complete members: end=0, Metadata u64 extrema, simultaneous 128-position/list/mapping limits with UTF-8/leap-day values |

These hashes identify source declarations, not empirical results. No SDK encoder, native reserialization, production serializer, dataclass reflection or returned native body defines an expected value. Mock/sentinel tests qualify wrapper ordering only. The native evidence compares every complete body with these independent expectations. Old market/raw/history/control packets are not inputs.

## Narrow codec profile

Candidate profile identifier: `dbn_v3_asis_zstd_cext_invented_bounded_20261012_candidate`. It is deliberately not a closed-profile ID.

The eligible positive DBN string begins with exactly one v3 Metadata and contains only complete MBO records from all instruments in original order. No target selection, dated market admission, book acceptance, successful-event ordinal, quote, feature, publication or account state is inferred.

Each DBN case and each tested partition creates a fresh `DBNDecoder` with exactly:

```text
has_metadata=True
input_version=None
upgrade_policy=VersionUpgradePolicy.AS_IS
compression=Compression.NONE
ts_out=False   (constructor choice; actual Metadata controls presence)
```

State is continuous across every chunk within that partition, including across a concatenated-frame boundary after decompression. It is never reset per frame/record. Actual framed header version and yielded Metadata version must both be 3; merely passing a constructor argument does not establish the input version. The explicit AS_IS choice avoids the source default UPGRADE_TO_V3. Metadata-bearing input overrides the native input-version/ts_out controls. The default is documented, not relied on.

The ordinary DBN feed partitions are exact complete input, seven-byte chunks and bytewise chunks. Complete/chunks7 call write then decode; bytewise calls write_and_decode. A final decode and exact-byte buffer observation are retained. A returned empty buffer is **not complete EOF proof**: the codec-direct eight-byte-prelude control consumes that prelude and has an empty buffer while the entire Metadata body is still absent.

Positive Zstd processing uses only the registered C backend and standard frames. Zstd source-read sizes 1, 7 and 65,536 are distinct tested source partitions; source read-through is not native consumed position. A different recompression/reframing is a different supplied member identity, even if its logical observations agree.

## Exact DBN wire and logical observations

### Complete independent wire bodies

Metadata starts with three bytes `DBN`, version u8=3 and body length little-endian u32. The body length excludes the eight-byte prelude and must be eight-aligned under this narrow profile. Absolute half-open decompressed offsets are:

```text
magic 0..3; version 3..4; length_body 4..8;
dataset 8..24; schema 24..26;
start 26..34; end 34..42; limit 42..50;
stype_in 50..51; stype_out 51..52; ts_out 52..53;
symbol_cstr_len 53..55; reserved 55..108;
schema_definition_length 108..112; complete variable sections thereafter.
```

Dataset is a 16-byte UTF-8 C-string field. The three list sections are u32 count followed by every fixed 71-byte C string. Mapping sections preserve every original group, its raw symbol, u32 interval count and every interval: u32 YYYYMMDD start, u32 YYYYMMDD end and fixed 71-byte symbol. Original group/interval order and duplicates of intervals are retained. Duplicate original raw-symbol group keys refuse under the narrow profile because the native dictionary getter can coalesce them. Reserved bytes, schema-definition length and alignment padding must be zero; unexplained tails refuse.

Each C string must have a NUL terminator, strict valid UTF-8 and entirely zero padding after the first NUL. This is stricter than the native getter's trim-trailing-NUL behavior; no embedded NUL/nonzero suffix is accepted. The 71-byte field allows at most 70 non-NUL encoded bytes, not 70 Unicode characters. UTF-8 byte limits and native text types are separate checks.

The first Metadata is at least 128 complete bytes. The retained independent field-span ledger covers every byte, including reserved/padding/count/date fields. A complete shorter input ending at a full record boundary can be a different syntactically complete member; it cannot be called detectably truncated without a held whole-input identity/count.

MBO wire fields are explicit, not reflected from a native object:

| Field | Wire domain / half-open relative span |
| --- | --- |
| length_words, rtype | u8 0..1, u8 1..2; exact MBO rtype160 and length14/16 |
| publisher_id, instrument_id | u16 2..4, u32 4..8 |
| ts_event, order_id | u64 8..16, u64 16..24 |
| price | signed i64 24..32, retained raw integer |
| size | u32 32..36 |
| flags, channel_id, action, side | u8 spans36..37,37..38,38..39,39..40 |
| ts_recv | u64 40..48 |
| ts_in_delta | signed i32 48..52 |
| sequence | u32 52..56 |
| present ts_out | u64 56..64; absent mode has no appended field |

The base record is 56 bytes; Metadata-present ts_out extends it to 64. The source-defined length word multiplier is four. This independently source-proven rule is not inferred from observed `record_size()`. Original field spans, raw bytes/hash and decoded occurrence positions remain distinct.

### Metadata: 14 native getters plus kind

The candidate harness observation has exactly these 15 keys:

```text
kind, version, dataset, schema, start, end, limit,
stype_in, stype_out, ts_out, symbol_cstr_len,
symbols, partial, not_found, mappings
```

`kind="Metadata"` is a harness discriminator, not a fifteenth SDK getter. Adding `symbol_cstr_len` makes this an explicit correction to the old proposed 13-field logical projection; it does not silently mutate the approved contract or any accepted component.

Exact rules:

- version is exact int3; dataset is exact str. schema is the exact native Schema.MBO observation with code0/textmbo. The native type supports None in general, but null schema is outside this narrow positive profile and is refused by independent preflight; no untested null-schema admission is claimed.
- start is exact u64 int, including U64_MAX. Native end is None for original UNDEF_TIMESTAMP=18,446,744,073,709,551,615 **or** original zero through the separate NonZeroU64 branch. Every other end value is the exact positive u64 int. The wire body retains which original representation occurred; logical None never replaces the raw body.
- limit is None for raw0; otherwise the exact positive u64 int, including U64_MAX. No datetime/float conversion, clamp, signed64 coercion or start<end market-admission rule is invented.
- stype_in supports exact native SType codes0..15 plus raw255→None; stype_out supports codes0..15 only. All 16 source-defined names/texts remain fixed in the primary oracle: INSTRUMENT_ID, RAW_SYMBOL, SMART, CONTINUOUS, PARENT, NASDAQ_SYMBOL, CMS_SYMBOL, ISIN, US_CODE, BBG_COMP_ID, BBG_COMP_TICKER, FIGI, FIGI_TICKER, LISTING_ID, ISSUER_ID, SECURITY_ID. Invalid codes refuse before construction. No PARENT-only restriction is silently imposed.
- ts_out is exact bool determined by the original header's canonical0/1 mode; symbol_cstr_len is exact int71. symbols/partial/not_found are actual native lists of exact strings, projected as full ordered tuple bodies without thinning/deduplication.
- mappings is an actual native dictionary of exact string keys and lists of exact interval dictionaries. The observation projects groups sorted by key, while the independent wire body retains original group order. Each interval preserves start_date,end_date,symbol; dates are exact Python date objects projected to kind=python_date with exact year/month/day, not a pretty formatter.

The capacity case retains 16 items in EACH list, 16 unique groups and 32 interval occurrences. Its valid U+00E9 UTF-8 and 2024-02-29→2024-03-01 dates qualify decoder/getter translation. Official `MetadataEncoder::encode_fixed_len_cstr` instead requires ASCII. This decoder-only byte corpus is not an SDK encoder roundtrip or a claim of encoder admissibility.

### MBO: 17 native observations plus kind

Exact harness keys are:

```text
kind, rtype, publisher_id, instrument_id, ts_event, order_id,
price, size, flags, channel_id, action, side, ts_recv,
ts_in_delta, sequence, ts_out, record_size, ts_index
```

kind=MBO is a discriminator. Every integer is exact int, never bool/subclass or float. Domains follow the explicit wire widths above; ts_out and ts_index are u64 observations. Absent native ts_out is the exact UNDEF_TIMESTAMP integer, **not None**; the wire body's absence is separately represented as None. Present ts_out is unchanged. record_size is observed56/64 for the corresponding complete record; ts_index equals ts_recv for this MBO type and is never used to sort or derive a byte offset.

Known native enums project exactly `kind,class_name,name,code,text`; unknown Action/Side characters project exactly `kind="str",value` containing one character. No generic string/int coercion may substitute for exact native class validation. The current independent observer checks the class first, then explicitly reads name/index/text.

Known Actions are MODIFY77/M, TRADE84/T, FILL70/F, CANCEL67/C, ADD65/A, CLEAR82/R and NONE78/N. Sides are ASK65/A, BID66/B and NONE78/N. RType.MBO is160/mbo. All known Action/Side branches are tested in both ts_out modes; unknown-character controls remain separate. These values are observations/consistency rules, not valid book transitions or trade admission.

## Zstd physical framing, termination and limits

The independent physical frame descriptor has exactly this ordered 16-field tuple:

```text
frame_ordinal, compressed_start, compressed_end, header_start, header_end,
descriptor, window_descriptor, content_size_flag, single_segment,
dictionary_id_flag, checksum_flag, content_size, window_bytes,
dictionary_id, checksum_value, blocks
```

Each block has exactly eight fields: block_ordinal,header_start,header_end,last,block_type,block_size,payload_start,payload_end. All offsets are zero-based half-open within exact supplied Zstd member-content bytes, not ZIP bytes, decompressed offsets, native emitted batches or source-read calls. Descriptor/boolean/int/None types are exact. The independent parser covers every header, block payload and optional checksum with no unexplained tail.

Only standard magic28b52ffd, canonical reserved/unused descriptor bits zero, dictionary-ID flag0 and supported raw/RLE/compressed block types are admitted. Skippable frames and all dictionary-ID fields (including a zero-valued ID field) refuse. Absence of such a field does not authenticate how an encoder originally operated; no dictionary is supplied to the decoder. Maximum block size is min(window_bytes,131072). The source-specified single-segment/content-size/window rules are explicit in the primary oracle; no guessed parameter units replace them.

Physical framing is not content validation: a physically complete wrong checksum or wrong decoded-content-size assertion must be caught by native consistency/terminal checks. A syntactically complete prefix ending at a whole-frame boundary is a different complete input until compared with its external held whole-member identity.

Registered positive mechanism, per independently framed exact frame:

1. Loaded C-backend identity matches before the first corresponding constructor. Create a fresh ZstdDecompressor with max_window_size argument1,048,576 and no supplied dictionary. The independent parsed window bound is1,048,576 **bytes**. That parsed bound and the process/job controls, not an unresolved documentation-unit assumption, are the enforcement argument.
2. Feed only that exact frame slice to a reader with read_across_frames=False and read_size65,536. Each output request is exactly min(65,536,1,048,576−cumulative_output+1). Require exact bytes no longer than that request. The one excess byte can be observed and causes refusal; it is never returned as a positive complete result.
3. Retain every full output byte. Require complete source read-through of the exact frame slice, but do not call that native consumed-position/EOF proof. Close the reader. Each individual frame output must be nonempty, not merely the concatenated total.
4. Require actual frame output length equal its known FCS, when present. On the SAME decompressor after reader closure, call decompress(exact_frame,max_output_size=exact_positive_frame_output_length,read_across_frames=False,allow_extra_data=False). Require exact bytes equal the complete reader output. Retain per-frame terminal options/count/equality.
5. The pinned C source requires complete native termination in this branch. For unknown FCS, the exact positive allocation avoids the shorter-output resize branch bypassing the no-extra-data check. For known FCS, allocation comes from the independently bounded header, not a supposed universal max_output_size ceiling. Empty FCS0 is refused before one-shot because the source zero-size shortcut is not a generic terminal proof.
6. Continue frame processing without omitting a foreign/tail frame. Only after every frame passes, independently frame the entire decompressed DBN and compare complete native observations with the wire bodies. A fresh DBN decoder stays continuous across the full DBN string.

Positive frames may use raw/RLE or compressed sequence/Huffman paths qualified by the independent packet. A finite packet establishes the registered profile/case agreement, not proof of all possible native behavior or independent semantic decoding of arbitrary compressed blocks.

| Bound | Exact candidate value / scope |
| --- | --- |
| Compressed supplied member | 1..262,144 complete bytes |
| Complete decompressed string / parsed frame window | At most1,048,576 bytes each |
| Nonempty frames | 1..16; any empty frame refuses positive composition |
| DBN positions including first Metadata | 2..128 |
| Complete DBN Metadata | 128..65,536 bytes, including prelude; eight-aligned |
| Each symbols/partial/not_found list | 0..16 |
| Mapping groups / total interval occurrences | 0..16 / 0..32 |
| Wire text fields | Dataset16bytes, symbol fields71bytes, canonical NUL/zero padding |
| Future public canonical Context/result body | Old proposed65,536/1,048,576-byte caps; NOT measured/provider-implemented by this harness |
| Parent captured child output | 4,194,304 bytes; complete success stream required, failed prefix separately labeled |

Equality is allowed. A first excess refuses without thinning, truncating, splitting or relabeling input. The 16-unknown-frame exact-total/excess and exact262,144-byte compressed-member supplemental cases remain required PENDING rows below; no claim of their empirical acceptance is made in this candidate snapshot.

## Process-birth containment: qualified scope, not inherited provider safety

The [registered controller](../scripts/native_profile_containment_20261012_1.py) launches the fixed direct Python executable with `-I -S -B`, exact registered child script and one allowlisted mode. No shell, caller path/command, inherited site setup or arbitrary fixture execution is accepted. A process-local package path/backend choice is explicit inside the child; no dependency or Windows/security setting is changed.

Fresh job assignment occurs during suspended process creation using JOB_LIST. Before ResumeThread, the controller verifies retained child image/creation/parent, exact own-job membership [retained_child], queried limits and the remaining work/teardown reserve. The process begins in the job, including native import initialization.

| Enforced/registered control | Value |
| --- | --- |
| Process and job committed-memory limits | 268,435,456 bytes each |
| Process and job user-time limits | 50,000,000 100ns units =5seconds each |
| Active-process limit | 1 |
| Queried limit flags |0x230E: PROCESS_TIME,JOB_TIME,ACTIVE_PROCESS,PROCESS_MEMORY,JOB_MEMORY,KILL_ON_JOB_CLOSE |
| Parent work / total reserve |12seconds work, at most3seconds teardown,15seconds total policy |
| Output read quantum / captured cap |65,536 /4,194,304 bytes |
| Hard-end guards | Exact canonical UTC, sufficient reserve before creation AND immediately before resume |

The configured/queried user-time policy and actual timeout/memory/output controls are not interchangeable evidence. No separate CPU-exhaustion control or parent-death experiment is claimed here; KILL_ON_JOB_CLOSE is a queried configured rule and parent-death empirical testing is explicitly false. Observed memory peaks are measurements, not the enforcement mechanism. These controls bound committed memory/user-time for the registered child, not all RAM, parent allocations, precise real-time termination, filesystem or network access.

Termination uses retained job/process handles, not a PID-only kill. Successful own-job termination is not immediately raced by redundant TerminateProcess; fallback is reserved for failed job termination or unproven membership, with API outcomes retained. Acceptance requires held-handle process exit, final own-job PID list[], active0, complete successful output and no unresolved cleanup errors. Cumulative TotalProcesses is an observation and is not a magic equality1/2 invariant.

**This process-birth policy qualifies this fixed experimental harness only.** It is not automatically inherited by a future in-process byte-only provider. Before such provider implementation, a separate exact resource architecture/containment policy must preserve the required guarantees or the provider remains blocked. No sandbox, full import graph, security health, source/runtime authentication or failproof parent-death guarantee follows.

## Runtime identity: deterministic core versus attempt receipts

The [static registry](../logs/native_profile_20261012_1/artifacts_static.json) is provisional, raw SHA256 `74b2044bba66e8c229669ac2dd2731ecd89205275a9d24ebaf54febbc9edd139`; it is not a closed-profile digest. It registers exactly the following13 artifacts:

| Logical ID | Raw bytes | Raw SHA256 |
| --- | ---: | --- |
| python.exe |104952|`4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a`|
| python312.dll |6945272|`9a0e3435aaa680d868150f87ab3e388ad2eebc22f87e036155c7b4eda8cd2120`|
| pyvenv.cfg |325|`b1a1e44d494a290b40de7b4030ab3852f66b8c31ad89f4851806127f10d2c493`|
| dbn_init |763|`62996cdfe11d8690d6d6d9b7973ae81add3b7864232fd5f56d74e177eee571f7`|
| dbn_metadata |1118|`a5f7b49b299e6a8a39af190805c83fb12f9346f32892cc0579235764fe24c189`|
| dbn_v1 |733|`71503b977417b9fb7771e32aa1af4422c22db4f3223dafa730bd000974769e30`|
| dbn_v2 |682|`2cc50301be2d0043ebe80dce98baa38ea665b61302ac723db8761cae8d48cc24`|
| dbn_v3 |647|`ef5410748580eadc1f0e69622f0e9eee5e23df0e0e830ef0aeecda1883765d54`|
| dbn_extension |3709952|`c48c57974ca83d68ae67522e6e191e3ae7fe9ae353fe78a59ab020a49cbef64a`|
| dbn_package_metadata |2337|`9d09394583e65c34e7d9715d8a9c5bb9128e10d3efce0afeb9aa7ecc5ba90543`|
| zstd_init |7452|`5c229d937b3f8420234f3baac08d8abc0ade34a17bbfbbac98fcd4f9349492d6`|
| zstd_extension |525312|`2ce792041f2bf7d8a8f514f0fb5adfc7778e56e988491e6ac7f3438c2e8cb3d3`|
| zstd_package_metadata |3339|`bbf8cb63171274854c72777372376d31d7b52447359a538c1c2b47aae49c2b3c`|

Recognized versions are Python3.12.10, databento-dbn0.70.0, zstandard0.25.0, C backend and underlying Zstd1.5.7. DBN's package version comes from its pinned distribution metadata, not an invented exposed package __version__. Actual DBN_VERSION=3, Zstd package/backend/library observations reconcile separately.

Ten named loaded associations are retained: python.exe↔sys.executable; python312.dll↔sys.dllhandle; dbn_init↔databento_dbn; dbn_metadata↔databento_dbn.metadata; dbn_v1/v2/v3↔their modules; dbn_extension↔databento_dbn._lib; zstd_init↔zstandard; zstd_extension↔zstandard.backend_c. For native associations, retained mapped paths are checked against the fixed deployment registry; Python DLL handle association is checked against sys.dllhandle. Before/after registered artifact equality and final loaded association equality are required.

Candidate deterministic RuntimeManifest has the old proposed exact top-level fields `schema,interpreter,packages,artifacts`. Its frozen recognized-set values must project interpreter implementation/version/executable SHA, the two sorted package names/versions/metadata SHAs and all13 sorted logical artifact IDs/kinds/raw byte counts/SHAs. Exact implementation/schema/kind/ordering literals and their independent observed comparison must be finalized at T12; no positive runtime-manifest SHA is emitted by this draft. The10-association policy belongs in the complete profile rules; actual file/spec/mapped paths and addresses remain full attempt evidence.

Fresh PID/TID, creation/exit times, command/cwd/hard end, actual elapsed/peak/accounting, native module handles/ASLR addresses and attempt-specific paths are retained in complete experiment receipts but **excluded from deterministic profile/member identity**. They must not be discarded from process ownership evidence, nor included in a stable member hash that would change on repetition. Hashing a complete attempt receipt is valid as that receipt's identity, not as the deterministic RuntimeManifest identity.

The13 registered artifacts and10 loaded associations are not a full DLL/import graph, memory-code authentication, package vulnerability audit or source/feed authentication. A file's known hash does not prove its loaded instructions or its build provenance. Coherent whole-context replacement remains unauthenticated/undetectable.

## Evidence table: qualified contributions and remaining gates

Counts below are nested corpus observations, not additive pytest totals. Parent-owned complete acceptance receipts/report hashes are the authoritative runtime evidence. Source declarations alone never close a gate.

| Gate / required row | Current registered evidence | Closure status |
| --- | --- | --- |
| P1 references/literals | Immutable DBN/Zstd sources and independently reviewed full packets above | Reference contribution accepted; final frozen profile/regression PENDING |
| P1 independent framing |17 DBN framing RED→same GREEN, subsequent full ordinary178case cohort, complete literal bodies/field spans and malformed/duplicate/type/cap boundaries | Harness contribution accepted; provider framer composition UNIMPLEMENTED |
| P5-static/C1 containment | Eight complete harmless checks after retained failed attempt; exact limits/member lists/owned exits and regression sentinel | Harness contribution accepted; future provider containment separate |
| P5 loaded identity |14same-identity checks, including actual contained imports; all13 artifacts/10 associations/versions and exact owned exit | Bounded identity contribution accepted; final stable-artifact/profile reconciliation PENDING |
| P2/P4 uncompressed DBN |42complete positive members ×3partitions, full14 Metadata/17 MBO values, all33SType cases;11independent-preflight refusals | Complete registered cohort accepted; preflight refusals are NOT native-error evidence |
| P2 known Action/Side |20complete independent members ×3partitions, both ts_out modes; enum_native_green_1.xml,148719bytes SHA2562de8b23df1ac672b696714902a3c569a27579239c490ff15fe9ee4ee9cfe1a02 | Complete enum contribution accepted |
| P3 positive/refusal Zstd |12positive complete outputs/ledgers/terminal checks +7refusals; known/unknown exact1MiB, unknown excess, checksum error | Complete registered cohort accepted; no all-format behavior claim |
| P2/P3/P4 codec-direct boundaries |15DBN controls (14negative+1different complete prefix),3empty-frame controls,3terminal negatives; boundaries_native_green_1.xml,60356bytes SHA2565cf370574c1b775e13bb90c91caf523e8c22ceec3b0640edf037fe9583a8632b | Root accepted complete outputs/errors/buffers; none admit a positive provider member |
| P2 capacity/absence/date/UTF-8 |3complete independent members ×3partitions; simultaneous128positions/16perlist/16groups/32intervals, rawend0/u64extrema, UTF-8/leapday | Root accepted at16:36:07Z; finite invented bounds, not historical capacity |
| P3 source partition invariance |RAW AB/match/Huffman fixed inputs ×source sizes1,7,65536; complete physical ledgers/output/terminal checks and actual bounded source-read traces | Root accepted with capacity row; shared capacity_partitions_native_green_1.xml name requires final receipt confirmation, report464515bytes SHA2562feb14a71c6295ae5a4b4a8a33c9f159f7e8087c6d01fa201c2bd795ec93db9e |
| P3 supplemental cumulative/input boundaries |16unknown-size frames totalexact1MiB; same total+1 refusal; exact262144compressedRAW member | PENDING independent literals/review/RED→GREEN/complete reconciliation |
| C2/P4 composed decoder |Three source-derived Zstd/DBN cases, one frame boundary inside Metadata length; held composed packet and intended missing-dispatch RED | PENDING C2 prerequisites/review and actual composed GREEN |
| T10/C3 independent final review |New stable harness/controllers/tests/oracles and exact candidate revision, all required findings closed | PENDING final complete review/freeze |
| T11/P5-final complete regression |Every12,206held old case-sensitive identity +every actual independently collected new identity; exact three old skip XML representations; all new mandatory native checks; zeroF/E, tool/owned exits and allpins | PENDING; no new count guessed and no mandatory native skip permitted |
| T12/C4 closure decision |Complete exact canonical profile/schema/RuntimeManifest/evidence body/expected pins plus retained qualified evidence | PENDING; no CLOSED artifact while any row remains unresolved |

The shared capacity/source-partition report name in the row above is a prospective link label, not an asserted saved-path fact; root must replace it with the exact retained path at final handoff. No case is accepted from dots, process presence/absence, passed subsets or a pin label alone. Failed attempts remain retained. Full final acceptance must also establish unchanged418old files/old contracts/plans/container pins, complete new-file/package/registration/oracle/report pins and every exact identity/skip reason, with GZIP/gzip distinct.

## Public provider and downstream residuals — UNIMPLEMENTED

P1–P5 qualification contributes mechanisms to A1–A15; it does not implement those public acceptance groups. In particular the following remain unimplemented/unreleased:

- Actual bytes-only public protocol/Context/expected-pin preflight, including all expected syntaxes/held equalities before native work. The fixed child allowlist/provisional registry is not the public API.
- Exact public Metadata14-getter projection integration, complete framing report/hash/occurrence output and all old-contract bodies/canonical exclusions. Candidate native getter corrections need the final reviewed revision before code.
- Public all-or-nothing positive return, no callbacks/yields/cache/prefix adoption, complete late failure refusal and future in-process resource architecture. A harness JSON observation emitted after traversal does not prove a nonexistent provider's atomicity.
- Submitted-evidence verifier with every outer shape/status/pin/count/authority alias mutation and independent fresh complete reconstruction. A fixed qualification test comparing literals is not that verifier.
- Public complete-body/envelope cap measurement and independent complete input/output hash namespaces. Native decoded bytes/observations, raw wire header, logical Metadata, full member and attempt receipts remain separate.
- Archive/source-intake selection and fresh whole-archive/member collection evidence; atomic source-bound publication integration; original native/event/37feature parity; complete historical capacity/cohort/calendar; one-genesis multi-session account continuity; independent untouched validation/economics/training/scoring/promotion.

There is no causal publication API in this profile proof. Complete source/member/runtime/EOF/totals are terminal facts and cannot enter an earlier causal seed. A later bridge must separately bind declared codec/header and actually consumed causal prefix while excluding future terminal state. Native DBN values may be outside the held signed64 constructed transport; never clamp/coerce them or invent instrument1/genesis/window to fit old gates.

No historical source read, native market replay, account/broker evidence, profitable strategy or model improvement follows. No latefill/UNKNOWN cancellation/reconciliation/reseed/daily reset/old-fill filtering/subset scoring/terminal-plan stitching is released. Accepted code remains held; BTC/cloud collectors are untouched.

## Exact all-false authorities and handoff

The old contract's exact ordered28 names remain literalFalse:

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

Exact policy/finite consistency/terminal success never turns one True. No credentials, broker/order hooks, signing service, permissions service, dependency install, Windows/security bypass or Graphify scan is part of the revision. User-disabled AppSecurity is not inspected/changed/claimed causal.

This candidate is ready for root/independent STATIC documentation review only. Root must finalize pending evidence/path/schema fields after actual gates, not use document review as runtime closure. At unchanged19:59:46Z launch nothing, retain incomplete proof honestly, summarize verified work/gaps, delete the follow-up and stop.

