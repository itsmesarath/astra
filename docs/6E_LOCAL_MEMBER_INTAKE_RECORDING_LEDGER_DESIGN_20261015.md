# Whole-record recording ledger design — 2026-10-15

Status: **PROPOSED / UNIMPLEMENTED / NOT QUALIFIED**. This is a concrete source-design proposal for the new finite harmless bootstrap, not a recording-budget certificate or a native release. It responds to the complete static source review of the initial host/worker drafts. No producer import, native call, process launch, file fixture, test, dependency or accepted-source change is performed by this document. The existing window ends at2026-10-15T14:59:08Z. Routine permission is established; the open issue is technical evidence, not human approval.

## 1. Fixed inputs and unchanged boundaries

Read this with the [recording correction](6E_LOCAL_MEMBER_INTAKE_RECORDING_RESERVATION_20261015.md), [bootstrap declarations](6E_LOCAL_MEMBER_INTAKE_BOOTSTRAP_DECLARATIONS_20261015.md), [source/API crosswalk](6E_LOCAL_MEMBER_INTAKE_BOOTSTRAP_CROSSWALK_20261015.md), [identity transport](6E_LOCAL_MEMBER_INTAKE_IDENTITY_TRANSPORT_20261015.md), and [binding](6E_LOCAL_MEMBER_INTAKE_BOOTSTRAP_BINDING_20261015.md). The corrected EOF rule is that PeekNamedPipe FALSE/error109 is only a trigger: a same-handle one-byte ReadFile FALSE/error109, with complete storage-only outputs, establishes the selected closure observation. The separately bound P3/D3/R3 revision must supply that rule before source release; this document does not silently edit P2/D2/R2, P1/S1/S3, or an old accepted record.

The unchanged host category ceilings are D4,194,313; B12,582,912; H2,097,152; R1,048,576; M8,388,608 bytes. Its conservative complete-body expression is `2D + 2B + 2H + R + M <= 47,185,938`; the complete actual host record separately remains at most67,108,864 bytes. The root actual artifact container has its separate335,544,320-byte aggregate ceiling. These are recording limits, not total process RAM, native allocation, filesystem/network, synchronous-call interruptibility or a parent sandbox.

The accepted controls are a fixed finite cohort, not every theoretically possible partition or exceptional runtime. Admission may refuse before an operation if the exact prospective envelope cannot fit. Such refusal is not a successful registered control. No truncation, hash deduplication, field omission, invented standalone BindingObservation cap, or changed first-excess boundary is allowed to make a control qualify.

## 2. The unit is a serialized occurrence, not a Python object

An occurrence identifier is an ordered tuple whose first element is one of `Host`, `Worker`, `Marker`, `ResultPayload`, or `RootExternal`; subsequent elements are exact record keys or exact nonnegative integer array indices. A boolean is not an index. Keys and indices are resolved against the selected closed record before use. There is no wildcard, dotted-name interpretation, expression evaluation, caller-selected callback, address/hash-based aliasing, or path normalization. The `i` and `j` symbols in the tables below are documentation metavariables only; a real ledger entry contains its actual index.

Two occurrences remain different when they share one in-memory object, equal bytes, a pointer, a digest or an underlying native allocation. Native initialized-before storage and complete-after storage are two occurrences even if identical or storage-only. A copied module buffer, copied path, copied GO return/buffer wrapper or second serialized initialization array is another occurrence at its actual destination. A temporary decoded tree which is not serialized/retained as another carrier is not invented as another persisted occurrence.

Selected atomic carrier boundaries are explicit:

- `Host.result`, when present, is one complete R occurrence: the entire canonical Worker13 record. Do not simultaneously recurse into that same host occurrence and charge its internals to host B/H/M. The real serialized result bytes in `Host.stdout.retained_hex` are a different D occurrence, and each real host ReadFile allocation remains separately B.
- `Worker.payload_hex` is one H occurrence containing the entire canonical ResultPayload byte body. Validate its complete decoded schema and262144-byte cap separately. A temporary decoding of those same bytes is not another serialized worker tree. The worker's top-level pre-emission trace is separately typed B/H/M; its bytes are genuinely repeated when the payload contains GO copies.
- Marker13 contains a direct typed `go_observation`: its initialization, bindings, reads, returns and postbuffers really are duplicate M/B occurrences. The marker's complete physical serialization inside host stdout is D; there is no fictional parsed-marker field in Host20.
- An artifact's own hash does not excuse omitted body bytes. Host M measures the canonical body excluding **only** `receipt_sha256`, preserving the accepted S3 body boundary. Reserve the fixed64-hex digest and its exact key/wrapper additionally for the complete-record64MiB check. Do not generically remove other `*_sha256` fields. Marker ownhash is excluded only for its own hash calculation: its complete body, including `marker_sha256`, must fit262144. Worker13 has no ownhash field.

These rules select separate container ledgers. Do not sum the entire Worker local ledger into Host after already charging the complete same Worker record to Host R. The root container independently charges its real persisted host-body copy, physical LMF1 bytes and read-buffer artifacts; no duplicate carrier is eliminated by a digest.

## 3. Complete root-field coverage

`M` below includes exact keys, braces, brackets, commas, colons, string quoting/escaping, pointer integers, counts, enum/text tokens and retained hashes. For a field containing categorized raw bodies, its nonraw wrappers remain M. `Typed` means apply the complete nested-family table; it never means skip the field.

### Host20

| Exact field | Category / expansion | Admission owner |
|---|---|---|
| version | M fixed selected attempt-v3 token | Initial host envelope |
| case_id | M exact registered case | Initial host envelope |
| packet | Typed entire actual admitted packet: nonce/control-literal raw hex H, remaining complete wrappers/flags/hashes M; exact null in the three refusal cases | Packet admission |
| packet_sha256 | M complete submitted-raw hash | Initial host envelope |
| registration_sha256 | M externally fixed complete canonical identity | Initial host envelope |
| oracle_sha256 | M externally fixed complete raw identity | Initial host envelope |
| declared_policy | M complete23-field selected policy | Initial host envelope |
| runtime_pins | M all33 complete fixed4-field rows, in registered order | Initial host envelope |
| parent_identity | Typed ParentIdentity or honest unobserved null | Self observation / ACK transaction |
| creation | Typed complete23-key Creation, including all transport/initialization/snapshot occurrences | Creation owner |
| job_observations | Typed every actually attempted19-key query group, including raw copies | Query transaction |
| api_trace | Typed every complete actual10-key pre-seal row | Native-call transaction |
| lifecycle | M every complete actual4-key event and related-ordinal array | Event transaction |
| stdout | D retained physical bytes plus M complete8-field Stream, or null when unobserved | Drain transaction |
| stderr | D retained physical bytes plus M complete8-field Stream, or null when unobserved | Drain transaction |
| result | Atomic R complete Worker13 or null | Complete result admission |
| fault_observation | Typed complete12-key fault, or null for the other19 cases | Selected fault transaction |
| terminal | Typed complete14-key Terminal and each actual ParentClose | Cleanup / terminal transaction |
| authority_flags | M all28 exact ordered literalFalse pairs | Initial host envelope |
| receipt_sha256 | Full-record M-width reserve, excluded only from Host M body measure and ownhash preimage as stated above | Final seal |

### Worker13

| Exact field | Category / expansion | Admission owner |
|---|---|---|
| version | M fixed result-v3 token | Initial worker envelope |
| case_id | M exact admitted case | Initial worker envelope |
| packet_sha256 | M complete actual submitted hash | Initial worker envelope |
| nonce_hex | H complete16-byte nonce occurrence plus M wrapper | Initial worker envelope |
| status | M finite completed / controlled_failure variant | Result branch envelope |
| worker_pid | M actual positiveU32, prospective width bounded before observation | Identity transaction |
| observed_parent_pid | M exact root-CIM→ACK→GO observation, not a worker parent-query invention | GO transaction |
| started_monotonic_ns | M U64 actual clock | Initial worker envelope |
| ended_monotonic_ns | M U64 actual clock at seal | Finalization reserve |
| payload_hex | Atomic H entire encoded ResultPayload, complete independent local cap/schema check | GO / payload transactions |
| worker_pre_emission_api_trace | Typed complete actual prefix, including completed cleanup | Native-call / cleanup transactions |
| worker_cleanup | M every actual WorkerClose; copied return associations remain complete | Close transaction |
| authority_flags | M complete28 literalFalse pairs | Initial worker envelope |

Worker local B/H/M and complete1MiB result checks are both mandatory. A raw parser/diagnostic/invalid-byte control has no returned Worker13 carrier; it does not fabricate this record. Its final raw emission is sealed/external-only, with complete actual host physical output/ReadFile evidence. This is a selected protocol branch, not dropping a required returned trace.

### Marker13

| Exact field | Category / expansion | Admission owner |
|---|---|---|
| version | M fixed pending-read-v2 token | Initial marker envelope |
| case_id | M fixed blocked_owned_pipe_read | Initial marker envelope |
| packet_sha256 | M complete actual submitted hash | Initial marker envelope |
| nonce_hex | H complete nonce occurrence | Initial marker envelope |
| worker_pid | M actual positiveU32 | Identity transaction |
| observed_parent_pid | M delivered, independently associated hostPID | GO transaction |
| started_monotonic_ns | M actual U64 clock | Initial marker envelope |
| go_observation | Typed complete direct GoObservation, with every real duplicate occurrence | GO transactions |
| owned_handles | M exact ordered two owned-handle rows | Private-pipe transaction |
| completed_api_trace | Typed every actual completed pre-marker row | Native-call transactions |
| pending_call | Typed prepared5-key ReadFile lower-bound record; no return or postbuffer is invented | Pending-call preparation |
| authority_flags | M all28 exact literalFalse pairs | Initial marker envelope |
| marker_sha256 | M fixed64-hex width reserve and full actual digest at seal | Final marker seal |

Full Marker13, including its ownhash, must fit262144. Its timestamp is a pre-call lower bound before its own marker write, never a fabricated exact later blocking-call entry. Its sealed own-emission calls are excluded from its completed trace and externally observed only. Actual complete synchronous marker-write success precedes the next blocking read; host complete-marker observation precedes timeout/termination, not necessarily read entry.

## 4. Nested occurrence families

| Family / exact destination | Raw category and complete wrappers | Transaction / bounded association |
|---|---|---|
| ApiTrace.arguments[j].value.storage_before_hex | B for allocated output/input-output/mutable pointers; H for the exact pure-input set below; null is M, not a zero-byte fabricated allocation | Exact native parameter ordinal, actual allocation extent, before foreign entry |
| ApiTrace.output_buffers[j].full_buffer_hex | Same B/H category as its associated parameter's before storage; full capacity even on failure | Same row/parameter; complete post storage; no prefix substitution |
| ApiTrace remaining fields, Pointer, ApiReturn, SavedErrorSeedObservation, BufferObservation wrappers | M complete closed forms, actual addresses/widths/error/seed; raw fields replaced only in a sizing view | One10-key row, all source-selected variants |
| Creation.command_utf16le_hex / environment_utf16le_hex / observed_image_utf16le_hex | H each actual separate prepared/query projection; the mutable native command buffer's own ApiTrace copies are separately B | Entire exact NUL-bearing prepared command/environment; image raw code units |
| Creation.inherited_handles_u64 and attribute selector fields | M actual full values; selectors are131074/131085 only when their calls were entered | Attribute and creation transactions |
| Creation.initialization and binding_initialization | M all complete constructor/lookup observations; source/library/API strings fixed for successful variants, actual handles/clocks retained | Two-phase owned initialization, described below |
| Creation.module_observations[i].raw_module_buffer_hex | H complete separate1024-byte other-hex copy; actual enum before/after allocation remains separately B | Reserve this copy before the associated enum call |
| ModuleEntry.path_utf16le_hex | H complete path projection; static hash/ordinal/base/path association wrappers M | Exact snapshot role/index/entry index and associated path query; no unknown path adoption |
| JobObservation extended_limit_bytes_hex / accounting_bytes_hex / pid_list_bytes_hex | H separate complete144/48/16-byte copies; original QueryInformation before/after buffers separately B | Full3-query group, including invalid projections |
| JobObservation parsed limits/accounting/PIDs/returns/ordinals/states | M complete19-key group and all nested semantic fields | Observed valid versus attempted invalid versus unattempted are not conflated |
| ParentIdentity image/command, IdentityRequest host/worker image/command, IdentityAck CimObservation image/command | H each complete code-unit occurrence; all other query/identity/date fields M | Full request/ACK and3 independent CIM tuples, not PID-only |
| IdentityTransport request/ack | Expand their typed fields normally; each repeated CIM body in Creation is another actual occurrence | ACK is bounded complete frame, parsed only after raw capture; same borrowed stdin closure confirmation, never an invented close |
| BootstrapPacket / IdentityRequest / IdentityAck nonce_hex and BootstrapPacket.control.literal_hex | H each complete actual nonce/literal byte occurrence; other complete packet/control/association fields M | Exact registered nonce/literal, no shared-object deduplication |
| IdentityTransport ready_hex / go_hex | H exact8/48-byte occurrences; ordinal arrays and ParentClose copies M | Actual complete physical write/read associations |
| GoObservation.packet_hex | H exact48-byte occurrence | Entire magic/PID/ACKhash frame |
| GoObservation.initialization / binding_initialization | M complete copied worker records when direct typed JSON; atomic encoded-payload handling follows section2 | Same actual initialization facts, distinct serialized destination |
| GoObservation.data_reads[i] / eof_probe | M complete7-key wrappers/returns/ordinals and B every complete copied postbuffer; before storage exists separately in ApiTrace | Each actual ReadFile row, exact remaining count, positive data partition; final1-byte FALSE109 probe/storage-only |
| GoObservation.stdin_close / WorkerClose / ParentClose | M complete closed records and complete ApiReturn copy when declared | Same actual owned handle, single actual close or honest unattempted/failed state |
| FaultObservation supplied image override | H exact independent held UTF16 literal; remaining full12 fields M | Five fixed fault sites only; comparator/pre-call facts never replace actual native trace |
| PendingCall.arguments/input_buffers | B complete initialized before allocations at both separately retained destinations; M all pointer/wrapper/clock fields | Actual prepared same allocations; no nonexistent post-call output/return |
| ResultPayload.control_payload_hex | H entire actual ordinary literal or canonical memory-observation bytes; GoObservation expands normally in this local standalone body view | Entire local262144-byte cap and exact schema; temporary decoding is not another host occurrence |
| MemoryControlObservation / MemoryRelease | M all exact6 fields in each record, actual address/error/return associations; native allocation256MiB is not snapshotted | Matching VirtualAlloc→VirtualFree when actually acquired; no fake release on denied allocation |
| Lifecycle, Stream indices/counts/hashes, Terminal and complete cleanup records | M every actual key/value/array occurrence | Actual event/query/handle identities, no claims derived from a future or unentered step |

The pure-input parameter set is closed: CreateProcessW `lpApplicationName,lpEnvironment,lpCurrentDirectory,lpStartupInfo`; CreatePipe `lpPipeAttributes`; SetInformationJobObject `lpJobObjectInformation`; UpdateProcThreadAttribute `lpValue`; WriteFile `lpBuffer`; GetProcAddress `lpProcName`; explicit LoadLibraryExW `lpLibFileName` only if actually called. Every before and after occurrence in that set is H even when output_validity is storage_only. CreateProcessW `lpCommandLine` and opaque attribute-list storage remain B. There is no inference from a field name ending in `_buffer_hex`.

## 5. Exact envelope algebra

Use the same strict ASCII canonical JSON as the bound resources: exact builtin types, no nonfinite/floating values, sorted object keys, complete string escaping, separators comma/colon without whitespace. Every sizing expression is private design state, never an emitted observation or a caller hook.

The closed expression vocabulary is `Literal(actual_value)`, `Integer(lo,hi)`, `StringEnvelope(unit,minimum,maximum,alphabet_ranges,source_selector)`, `OneOf(expressions)`, `Record(exact ordered-key map)`, and `Array(exact list of expressions)`. These are six distinct private expression variants; no extra operand, implicit coercion, code evaluation or caller-selected rule is accepted. Bounded future repetitions expand to a finite exact list before admission; no unevaluated wildcard or arbitrary predicate is admitted. A `Record` always contains every field of its selected complete schema. A nullable field is an explicit OneOf with Literal(null), not omission. A future PID/handle/date/ACK value is not `Literal(actual_value)` before it has actually been observed. Broad schema Text is not silently used as a fitting success bound.

`StringEnvelope` is closed and source-qualified as follows:

- `unit` is exactly `ascii_code_units`, `unicode_scalar_values`, or `utf16_code_units`. `minimum` and `maximum` are exact nonnegative integers, not booleans, with minimum<=maximum. They count the selected units, not UTF8 raw bytes. A raw byte cap must not be relabeled a character cap without an explicit source-derived inequality and encoding policy.
- `alphabet_ranges` is an ordered list of disjoint inclusive `{lo,hi}` integer code-point ranges. Every range lies within0..1114111 and excludes every code point55296..57343. A range crossing the excluded interval must be split; a lone surrogate is never an admitted scalar. For ascii_code_units, every range additionally lies within0..127. An empty alphabet admits only the empty string when the unit interval permits it. No OS/path/case/normalization rule is inferred from this alphabet.
- `source_selector` identifies the exact bound source/registration rule giving this particular field's maximum, unit, alphabet and accepted format. A use with a missing source-qualified limit or unknown alphabet is unresolved and refuses admission. Registered fixed strings use Literal or a finite OneOf instead. An envelope can conservatively overapproximate a separately checked format, but must not replace the actual format/calendar/CIM association validation.
- An actual string must be an exact string, contain no surrogate code point, have every scalar in the registered ranges and have its selected unit count within the exact interval. Unicode-scalar units count each scalar once; UTF16 units count BMP scalars once and non-BMP scalars twice; ASCII units count each permitted ASCII code point once. No value is coerced, normalized, silently replaced or encoded with a permissive fallback.

For strict ensure_ascii canonical encoding, define escaped interior width e(c), excluding the two surrounding quotes: quote34 and backslash92 have width2; the short-escape control characters8,9,10,12,13 have width2; other controls0..31 have width6; printable ASCII32..126 excluding quote/backslash has width1;127..65535 excluding surrogates has width6;65536..1114111 has width12, the exact two-surrogate escape sequence. Each class uses the selected lowercase four-hex-digit Unicode escape spelling; slash47 is not additionally escaped. This is an exact encoding-width rule, not the Unicode scalar's UTF8 byte length.

The maximum has a realizable private sizing witness. Intersect the finite alphabet ranges with the width classes above, choosing the least permitted representative code point for each attainable pair `(unit_cost,e)`. Unicode-scalar and ASCII units have cost1 only, so repeat a highest-e representative maximum times. For UTF16 units, let a be the greatest attainable width among cost1 representatives, and b the greatest among cost2 representatives (if any). Evaluate the finitely described choices `x+2y` in the admitted unit interval with x,y>=0, x=0 when cost1 is absent and y=0 when cost2 is absent; maximize `a*x+b*y`. Here a is at most6 and any b is12, so the maximum is attained by the largest admissible unit total, with the maximal number of cost2 pairs and a cost1 remainder when available; the cost1-only branch repeats its representative. When only cost2 exists, use the largest admissible even total. If no total is realizable, the envelope is empty and refuses. U is exactly2 plus that maximum escaped width.

The private witness is the selected representative sequence, optionally stored as complete run-length pairs for sizing and expanded only after its entire canonical width fits the applicable cap. It is labeled a synthetic sizing witness, never emitted as an actual observation. A date-shaped envelope's witness need not be a real date if the alphabet/length envelope is an explicitly declared superset; actual dates still require complete strict calendar/offset/tick validation. The bound is exact for the selected envelope, not a claim that its largest synthetic string was observed. Actual canonical width is recomputed and must be <=U before commit. No large witness allocation or dynamic-programming array is needed merely to reject an oversized bound.

For future complete ACK/CIM success, the field owner must provide these particular source-qualified envelopes before the first associated native capture: query text is the complete fixed query template with a positiveU32 decimal PID; role/state/kind/conversion tokens are finite literals; round-trip dates have the selected strict28/33-character ASCII format and alphabet; image/command bodies are complete UTF16LE **hex H occurrences** at the already selected role unit caps, not unbounded M strings. Successful query error is the exact null variant. An unexpected error text, unknown field/variant or unsupported representation does not become a fitting successful ACK: retain actual raw captures and select the separately reserved incomplete path. A complete raw ACK-body cap alone does not prove an arbitrary number of broad Text copies fits M.

The author decoded and read the relevant complete retained official source selectors, without executing/importing them: immutable CPython commit `0cc81280367df838c4b199f8f0378837165071c2`, `Lib/json/encoder.py` lines18–78 (`ESCAPE_ASCII`, `ESCAPE_DCT`, `py_encode_basestring_ascii`) and `Modules/_json.c` lines103–205 (`S_CHAR`, `ascii_escape_unichar`, `ascii_escape_unicode` size loop). They directly distinguish printable ASCII, the short escapes, other BMP escapes and non-BMP pairs. The lossless nonexecutable packets are [encoder source](reference_corpus/local_member_intake_20261015_1/cpython_json_encoder_3_12_10.source.json) (physical21980bytes/SHA256`42bcefe04bce199e4c2b71d6707dc54bd88a066f10459dcbcdfd8a9e5e4af164`; complete decoded16075bytes/SHA256`52bfb1b66029cc70fa3bd7fe11df9f2e03922d413407a341b387a22c987f24f8`) and [C encoder source](reference_corpus/local_member_intake_20261015_1/cpython_json_c_3_12_10.source.json) (physical76580bytes/SHA256`d47dbcf3730d44a93a2cdf1c7e78615e544bed0f25bfd97a5718f084f61e396e`; complete decoded57033bytes/SHA256`6a0eaa8a82a30d5e35b47bda64c0a9741924c0b925fa6a9445addb3a61a5b5b9`). Packet identities are distinct from decoded source identities, not native installed/loaded/build authentication. The exact source binding and independent pure boundary/witness vectors still precede any ledger implementation release; no runtime behavior is inferred merely from retained source.

Define canonical upper width U recursively:

- Literal: `len(C(value))`.
- Integer: maximum ASCII decimal width of its interval endpoints (and zero if included). For a signed interval both endpoint signs count. These are sizing values only; no integer is fabricated in actual evidence.
- StringEnvelope: exact2 plus the maximum escaped interior width and realizable private witness defined above; actual domain/unit/width checks are mandatory before commit.
- OneOf: maximum U over its complete finite alternatives, retaining the selector association used to derive each alternative.
- Record with n keys: `2 + max(n-1,0) + sum(len(C(key)) + 1 + U(value))`. This counts every brace, comma, quoted key, colon and full value. Sorting changes order, not this exact byte count.
- Array of n entries: `2 + max(n-1,0) + sum(U(entry))`.

For categorized raw bodies, retain the exact field/key/quote wrapper in the M sizing view and replace the admitted Hex body with empty string **only there**; null stays null. Add its complete byte extent to its B/H/D category instead. An atomic R field becomes null in the host M view and is measured as the complete canonical R body in its own category. Actual evidence is never rewritten this way.

The private envelope must retain a complete serialized sizing witness for each finite scalar/enum branch and the actual field/path association; U is derived from that shape, not a guessed per-row allowance. A factored maximum of independent BufferObservation variants is an explicitly conservative product envelope, not a claim that its impossible cross-combination was observed. Complete finite return/error branches remain separate when their field sets or validity associations differ. Native I32/I64/U32/U64 endpoints, actual fixed source/parameter strings, actual allocation extents and the longest registered projection token determine the bound; no unbounded diagnostic text enters a conforming-success envelope.

## 6. Private state and transaction protocol

Maintain an artifact-owned occurrence tree and a reservation map. The tree has a sizing cell for every complete root field in section3. Each cell is `committed` (actual complete fact), `unentered` (exact schema-prescribed null/empty fact), or `reserved` (private finite envelope, not exportable evidence). An emitted record may contain no reserved cells. Immutable fixed metadata is admitted before any foreign initialization. An occurrence is attached to its final destination before it can be duplicated or a native operation can enter.

A reservation has an internal unique transaction identifier, exact destination-path set, source-selected action/family identifier, prospective occurrence envelopes, required cleanup continuation envelope and source/phase association. It is not a new public receipt field and does not itself assert execution. No two live transactions may own the same append index or replace a committed fact. One native row, its actual semantic projection/copies and its exact related lifecycle additions form one source-defined transaction group; do not reserve just the row and later append unaccounted wrappers.

The algorithm is:

1. Prepare all actual pure inputs/allocations/strings and determine their exact extents before the next foreign call. Construct its complete candidate transaction and every required duplicate destination, plus the protected cleanup continuation. Compute the complete future root envelopes by overlaying those cells on the current whole occurrence tree. Measure whole arrays/records, including punctuation; do not add guessed wrapper constants.
2. Check every category ceiling, the joint host expression, each local record/payload/full-result cap and the complete-record/root-container cap in the applicable separate container. Check API/lifecycle/snapshot/read/close cardinalities simultaneously. If any upper bound cannot fit, do not enter that new ordinary action. Select unqualified/incomplete and use only already reserved cleanup capacity. A caller's or control's expected outcome cannot override this guard.
3. Capture the actual pre-call clock/seed, enter exactly the intended foreign call, immediately save the defined error, then retain the actual end clock/return/full poststorage. Keep this actual row reachable even if its validation or semantic projection fails. Evaluate all actual values without coercion/truncation.
4. Atomically commit all actual occurrences of that transaction and source-defined bookkeeping. Verify actual categorized extents and canonical metadata width against the reservation. A successful commit releases **only unused prospective capacity**, not actual rows, buffers, duplicates, ordinals or observed failure facts. A released future branch never changes an entered branch into unattempted.
5. Before any later native call **or recording-only append/copy**, recompute admission from the entire current tree and its still-live reservations. This includes lifecycle transitions, query projection attachment, module/path copies, GO read copies, fault records, parsed result admission and terminal changes. No future call can rely on a stale API-only counter.
6. At seal, all remaining entered transactions have actual records; all genuinely unentered stages have their exact honest null/empty states; there are no outstanding reservations. Recompute complete exact categories independently from the actual final serialized shape. Verify both body and full-record caps and the ownhash preimage/result. Seal once. Its own subsequent emitter is outside that sealed prefix and externally observed; emission failure is incomplete, never a fabricated successful internal WriteFile row.

If an unexpected exception occurs between foreign return and full row commit, the attempt is unqualified. Preserve the complete actual raw row/facts where possible; do not manufacture a missing return. Source exception handling must not catch unexpected assertions as success. Failure to construct the mandatory complete carrier is explicit missing/incomplete external evidence, never positive qualification.

## 7. Initialization, bindings and retained failure ownership

Construct the recording owner and Native observation containers in a pure first phase. Attach their actual initialization/binding arrays to the appropriate artifact occurrence tree **before** calling WinDLL or looking up the first export. Only then enter a second explicit initialization phase. The current draft's `self.native = Native(...)` after a throwing constructor is insufficient: it can lose the only reachable actual rows from the temporary Native object.

Conforming constructor success has the exact fixed6 arguments/source selector/role and bounded native handle/clock fields; its complete12-key InitializationObservation obeys the existing32768-byte cap. Conforming binding success has the exact fixed export name, constructor association, source selector, completed flag, address and clock fields. All33 names are fixed by registration. There is no new32768-byte BindingObservation cap.

Actual OSError/AttributeError data is not bounded by pretending the broad Text schema is a small literal. A diagnostic exception may fit the existing complete budgets and be retained in its full typed declared record, producing an incomplete attempt. If it cannot fit, no matching positive carrier exists: preserve actual prior facts and complete admissible external diagnostics, with explicit missing/oversized carrier evidence. Do not truncate strings/args, invent error126/127 from a message, fake native-call observations for hidden ctypes work, coerce a bad optional integer, or claim every possible failure has a fitting envelope. Constructor/lookup failures before an owned job do not acquire an invented cleanup obligation for the process-lifetime WinDLL reference; actual already acquired owned handles in other stages remain subject to cleanup reservations.

## 8. Source-selected action families and duplicate destinations

Before implementation, each actual call site is assigned exactly one of these closed action families, parameterized only by admitted actual indices/extents and fixed registration literals. A family supplies the exact affected field paths from sections3–4, not a callback supplied by an input packet.

| Action family | Atomic ordinary transaction | Obligations which remain reserved |
|---|---|---|
| WinDLL / export lookup | Complete owned success observation, or actual diagnostic failure branch; fixed initialization/binding path | No positive continuation on hidden/oversized failure; actual acquired handles remain accounted |
| Direct resolver/owner/path check | ApiTrace row plus source-qualified owner/path association | Remaining binding checks before dispatch; no invented additional load/free pair |
| Self PID/time/image | ApiTrace plus ParentIdentity/IdentityRequest raw projection occurrence | Complete matching identity before child creation/dispatch |
| Fresh job creation/configuration | ApiTrace, actual owned-handle cell, lifecycle; complete prepared input copies | Close that exact acquired job once; query/empty/termination obligations appropriate to actual state |
| Job query group | All3 ApiTrace rows, full19-key JobObservation, all144/48/16 raw copies/projections and exact lifecycle additions | No validity from failed/undefined storage; final actual empty observation before positive cleanup |
| Pipe creation/inheritance | Actual CreatePipe/flags rows, exact owned endpoints and lifecycle additions | Every acquired endpoint has one actual close or honest unentered/failed disposition; no borrowed root-handle close |
| Attribute sizing/initialization/update | Full pointer before/after rows, initialized flag, selector/value copies, lifecycle | DeleteProcThreadAttributeList iff initialization actually succeeded; preserve buffers until native use ends |
| CreateProcess | Complete prepared command/environment/STARTUPINFO, row, actual process/thread/IDs/birth, lifecycle | Owned child job at birth, actual signal/exit/times/empty and exact closes; child clock never reset |
| Root request/ACK | Actual full request fields, WriteFile rows, full ACK read rows and raw/code-unit copies at each declared destination | Exact frame before closure confirmation; actual1-byte ReadFile FALSE109 on borrowed stdin; full3CIM joins before allow |
| Resume/READY/module snapshots/GO | Exact entered phase facts, complete snapshot copies/entries, actual8/48-byte carriers and ordinal links | Dispatch only after all required phase facts; no GO for resume_refusal |
| Data/EOF drain | Peek row, optional data/confirmation ReadFile row, entire actual retained physical bytes/full allocated buffers, Stream counts/indices and event | No qualified EOF from Peek failure alone; no read after first-excess just to fabricate EOF |
| GO worker read/probe/close | Each source-selected ReadFile row, separate full GoRead return/postbuffer copies and exact close | Complete48 bytes, one1-byte FALSE109 probe and actual stdin close before normal result/private pipe |
| VirtualAlloc / release | Actual allocation row/address/error, complete memory body plus matching release row when acquired | One actual VirtualFree before successful result; denied allocation has no fake release |
| Fault injection | Exact selected full12-key fault and its independently fixed supplied observation | Actual original call count/return and restoration truth; no replacement of real trace |
| Private pending pipe/marker | Actual pipe/flags trace,2 handles, prepared call storage, complete direct GO copies and marker ownhash | Complete marker before its sealed write/next blocking call; process reclamation is not individual close proof |
| Lifecycle / copy / terminal update | Full new event/projection/return/copy/terminal cells, even when no native call occurs | Admission is mandatory before this append, not postponed until final serialization |

## 9. Cleanup reserve and the limit of the guarantee

Cleanup is part of the same occurrence budget. It cannot borrow an unrecorded call, silently exceed caps, spend an ordinary record after its reservation failed, or claim process reclamation as an individually observed CloseHandle. Define a source-selected continuation graph over the actually owned state, with the following exact action order where applicable:

1. Retained-process zero-wait; if actually live, one TerminateJobObject and bounded retained-handle wait observations. Actual already-signalled and actually terminated branches remain distinct.
2. Actual GetExitCodeProcess and four-output GetProcessTimes after signal; required data/EOF drains except after the registered first-excess sentinel.
3. Complete3-query final job groups until actual empty or an honest failure/deadline; no guessed empty state.
4. Delete the initialized attribute list iff actually initialized; close every actually owned endpoint/thread/process/job exactly once with actual complete return facts.
5. Required final host module pair before the host seal, with every actual buffer/path/copy, or an explicit incomplete disposition if not established.

Worker normal cleanup is the actual GO stdin close, plus one VirtualFree for an actually acquired memory-control allocation. The blocking private-pipe control intentionally has no observed individual private-pipe close after its unreturned read; complete owned termination/process reclamation is separately associated. Raw final emissions have no returned worker trace carrier. These are distinct registered branches, not blanket permission to erase cleanup.

A continuation descriptor expands the remaining mandatory non-loop suffix and the selected loop action groups from actual state, using the existing API/lifecycle4096, snapshot6, module128, GO-read48, close16 and unchanged clock/cardinality limits. Repetition counts are integer variables under those exact coupled limits; a complete maximum of the canonical envelope is required, not a guessed number of milliseconds converted into a promised call count. Synchronous calls can overrun nominal clocks; the root-owned host supervision is a separate recorded boundary.

There is an important infeasibility boundary: the existing byte/count/clock caps do **not** guarantee that every possible short-read/wait/failure sequence has a fitting full cleanup record. A cleanup-read may return fewer bytes than requested while its whole allocation is still charged; a wait can return before the next clock interval; broad exception strings may exceed M. Therefore a schema-wide universal positive-cleanup capacity proof cannot be honestly asserted from these caps alone.

For an implementable finite accepted-variant design, the continuation certificate must distinguish (a) the full successful qualification continuation and (b) the failure/incomplete continuation using only already protected capacity. Before each optional/repeated ordinary step, protect actual owned safety actions and the complete bookkeeping for an explicit incomplete outcome. A byte/count/deadline guard may stop an ordinary drain/snapshot/query iteration only by making qualification incomplete, retaining the missing-observation fact; it must not transform it into an accepted EOF/empty/final-pair result. If capacity to attempt and retain the source-selected owned cleanup continuation cannot be demonstrated, the attempt must **not be launched**. This is a capacity obligation, not a promise that Windows calls must succeed, signal or return within a scheduling interval. This document does not choose an unregistered shorter loop, new cap, guessed fixed allowance, untraced cleanup path, or unsupported absolute cleanup guarantee.

The exact executable continuation expansion/certificate is consequently a remaining technical gate: it must list each permitted repeated action, protected suffix, raw and metadata occurrence envelope, record-count constraints and the policy for an impossible continuation. Independent pure adversarial evaluation must show that ordinary actions cannot consume that protected suffix. Merely adding `reserved_api_metadata += next_row_size` does not satisfy this requirement.

## 10. Required finite certificate before a source/runtime release

`RootExternal` is only a named separate container in this design, not a completed root-ledger proof. The Host20/Worker13/Marker13 tables do not cover the whole15-key RootObservationReceipt, every ManagedCall/task/buffer/CIM/frame/artifact occurrence, root parsing/persistence copies or observer cleanup reservation. In particular, guessed per-call allowances65536/524288 in an observer cannot inherit a proof from this host ledger. A complete independent root occurrence/envelope/admission/cleanup certificate, with the same actual raw/metadata association and unchanged335544320 aggregate accounting, remains **OPEN** before an observer/native qualification release. No statement in section6 is evidence that this separate root certificate has been supplied.

The design is reviewable without executing a producer. A later separately registered pure calculation must produce all of the following, from the bound production P/registration/source policy and independently reviewed symbolic constants, not from native actual output or D-derived production tables:

1. Complete occurrence-path coverage: every Host20/Worker13/Marker13 field and nested family is mapped once per serialized destination; atomic result/payload boundaries are explicit; every duplicate/copy is listed.
2. Exact canonical sizing expressions/witnesses for each conforming action family and each branch of return/error/output validity/seed/nullability. Full fixed strings, native integer endpoints, raw capacities and punctuation are retained.
3. Whole-artifact current+next+continuation envelopes for all24 controls, including pre-handoff refusals, first-excess, EOF confirmations, normal result and pending marker. Each is independently checked against all separate category/local/full/container/count limits; no omitted family is represented by a prose allowance.
4. Complete reserve→entered→actual-commit→unused-release histories for independent literal synthetic transition cases, including repeated GO wrappers, module-path/raw-buffer copies, lifecycle growth, failed native returns, oversized binding diagnostics and budget exhaustion before cleanup. These are pure synthetic observations, explicitly not native qualification.
5. Exact ownership-safe constructor failure behavior and a source-linked continuation certificate. A source writer cannot lose its only actual error rows in a temporary constructor object or bypass recording admission merely to close an owned resource.
6. Independent source review that every actual recording/call site uses the corresponding family and that final exact category recomputation agrees with the envelope. Every actual native cohort still independently needs full frozen source/metadata/owned/tool/body evidence and complete regression acceptance.
7. Genuine independent native-free intended RED for the newly discovered recording behavior before a source correction is released: whole-wrapper and duplicate growth, M/H/B boundary and first excess, source-selected continuation preservation, unknown string/oversized diagnostic and no-entry-before-reservation cases. The earlier G4 missing-interface RED proves only the missing producer interface and is insufficient for this new recording logic. No producer import, ctypes initialization, native call or fabricated actual cohort is permitted merely to obtain that RED. Its exact source-only/pure extraction mechanism and independent literals must be separately registered and reviewed before launch.

Until those finite obligations close, this is a saved proposed design with an explicit cleanup-certificate gap, not a positive budget bound or G4 result. The initial code remains an unqualified reviewed draft; no public provider or G1/file-intake release follows. Existing accepted code, historical inputs, all28 false authorities and UNKNOWN liabilities remain held. No source/runtime/history authentication, trading economics, profitability or model improvement follows from a recording design.
