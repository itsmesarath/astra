# T4.2 — pure Host bootstrap-owner support contract — 2026-10-16

Status: **PROPOSED / UNIMPLEMENTED / PURE SUPPORT ONLY**. This contract defines one small test-first support slice for the real temporary-owner loss in the held Host draft. It does not integrate that draft, repair the Worker or Root protocol, close R1/R2, qualify native behavior or release any implementation. Only this new Markdown file is authorized by this assignment. Save, present for independent review, then HOLD. Routine human permission is already established; no repeated approval question is required.

The current window remains **2026-10-16T07:28:38Z–15:28:38Z /16:28:38 Lisbon hard end**. See the [window](6E_LOCAL_MEMBER_INTAKE_RECORDING_WINDOW_20261016.md), [execution board](../tasks/local_member_intake_recording_execution_20261016.md), [diagnostic derivation](6E_LOCAL_MEMBER_INTAKE_DIAGNOSTIC_ENVELOPES_20261016.md), [Host candidate](6E_LOCAL_MEMBER_INTAKE_HOST_CERTIFICATE_CANDIDATE_20261016.md), [protected-envelope recipe](6E_LOCAL_MEMBER_INTAKE_HOST_PROTECTED_ENVELOPE_RECIPE_20261016.md), [Root bound](6E_LOCAL_MEMBER_INTAKE_ROOT_TERMINAL_COUPLED_BOUND_20261016.md) and [ordinary Owned bound](6E_LOCAL_MEMBER_INTAKE_ORDINARY_OWNED_BOUND_20261016.md). Their conditional bounds and open gates are unchanged.

## 1. Objective, assumptions and exact source boundary

The useful property is **caller-visible retention before later synchronous Python bookkeeping fails**: the caller already owns the support object and the two original destination arrays when a fake constructor or lookup is invoked. Raw library/callable/exception references survive the explicitly modeled failure cuts, separately from any committed typed observation. Exactly one fake invocation is permitted per selected slot; an unknown or failed attempt is never retried by this support.

The source defect is concrete. In [Host897–902](../scripts/local_member_intake_bootstrap_host_20261015_1.py), `self.native=Native(...)` completes before Creation receives its initialization/binding arrays. Native creates its lists at291–293, enters initialization at320, constructs records at327–364, and can raise before the outer assignment completes. [Worker775–781](../scripts/local_member_intake_bootstrap_worker_20261015_1.py) has the analogous temporary-owner cut before any GO/result carrier exists. This support models the Host ownership handoff only; it does not import or invoke either source.

Selected held identities, not freshly rehashed native/runtime identities: Host96,913bytes/SHA256`518e75be61be5fdc5535d9619b790822a5bed8fa7f4607f1b5bfe936f2e69b7f`; Worker47,826bytes/SHA256`7adaf7f42fc97a0221bf792ff657c6f23b625355e348697301bdfcd9d5d00279`; [P3](../scripts/local_member_intake_bootstrap_protocol_20261015_3.json)171,369bytes/SHA256`2252ebefe2d38b14f5c915b3a1b9fbb2c8bc960a02477372bb1dd0ea7114c31f`; [R3](../logs/local_member_intake_proof_20261015_1/bootstrap_registration_3.json)261,698bytes/SHA256`8cd142cb57af0d509d306057a9fe66152f58f9ebfa8e036f10d61170e23d938c`.

Assumptions are deliberately narrow: one thread, trusted exact Python-function fakes, ordinary synchronous `Exception` outcomes and explicit cut sentinels; no external mutation of owner records during an admitted operation. A fake can inspect the owner reentrantly but cannot mutate it. This is not a sandbox for arbitrary callbacks. No clock, address, hidden loader result, native error, DLL identity, EOF, release or real stdout capability is obtained or inferred.

## 2. Proposed files and five-operation API

The only possible later support files are NEW `scripts/local_member_intake_bootstrap_owner_20261016_1.py`, independent NEW `tests/test_local_member_intake_bootstrap_owner_20261016.py` and NEW `tests/local_member_intake_bootstrap_owner_oracles_20261016.py`. They do not exist by virtue of this proposal and must not be created now. The old Host/Worker/Root/validator, accepted production, all existing Python/resources/contracts/plans and earlier test-deadline literals remain unchanged. This document is not an execution registration.

These signatures are interface declarations, not implementation code:

```text
new_owner(carrier) -> Owner
run_constructor(owner, pending_record, invoke, convert, *, cut=None) -> StepView
run_lookup(owner, api_name, pending_record, invoke, convert, *, cut=None) -> StepView
inspect_owner(owner) -> OwnerView
select_paths(owner) -> PathSelection
```

`carrier` is an exact two-key dict, `initialization` and `binding_initialization`, whose values are two distinct exact empty lists. It is a view of the caller's existing Creation arrays, not a new P3 record. `new_owner` retains those exact list objects without copying, replacing or appending to them. The caller binds the returned Owner before calling either run operation. A prospective Host integration must separately prove that its real Creation lists are these objects; this helper does not modify or validate a complete Creation record.

Owner is an opaque, single-use support object. It has one constructor slot and a fixed tuple of33 lookup slots, the two original array references, the original carrier reference, `next_lookup` in0..33, `in_progress` and `stopped`. No event log, scheduler, growing retry/history structure, serializer, transport, native resource manager or callback registry is introduced. Object/array identities are part of this API; equal cloned values do not satisfy them.

The fixed lookup order is the exact R3 order:

```text
CreateJobObjectW, SetInformationJobObject, QueryInformationJobObject,
InitializeProcThreadAttributeList, UpdateProcThreadAttribute,
DeleteProcThreadAttributeList, CreateProcessW, ResumeThread,
WaitForSingleObject, GetProcessTimes, GetExitCodeProcess,
QueryFullProcessImageNameW, GetCurrentProcess, GetCurrentProcessId,
TerminateJobObject, CreatePipe, PeekNamedPipe, ReadFile, WriteFile,
GetStdHandle, GetFileType, GetHandleInformation, SetHandleInformation,
CloseHandle, LoadLibraryExW, GetProcAddress, GetModuleHandleExW,
GetModuleFileNameW, K32EnumProcessModulesEx, K32GetModuleFileNameExW,
FreeLibrary, VirtualAlloc, VirtualFree
```

No operation loops through or invokes the roster automatically. The caller explicitly requests each next lookup, at most33 total. A constructor is admitted only once; lookup0 requires its committed-success state, and lookup j>0 requires every earlier lookup committed-success. Wrong names/order, duplicates, calls after stop/completion, reentrant run calls and detached/replaced carrier arrays refuse before invoking any fake. Refusal leaves all owner state, arrays and raw references unchanged.

All admission refusals raise the support's exact `OwnerRefusal(ValueError)` with an exact string `reason` from `owner,carrier,pending_record,callback,cut,order,stopped,reentrant`; no callback body exception is confused with this pre-admission refusal. Check order is owner type, carrier/row identities, pending_record exact dict, callback exact-function types, cut shape, reentrant, stopped, operation/order. new_owner checks only its carrier shape/two distinct empty lists. inspect_owner/select_paths check only exact owner type and perform no transition. Error details contain only that closed reason, never raw object repr/str. Ordinary admitted fake/conversion/cut outcomes return StepView instead of being thrown as admission failures.

Literal boundary guards precede value operations: every carrier key must be exact str before key-set construction/equality; a converter status must be exact str before token membership; api_name must be exact str before any roster/order comparison, with a bad type using the existing order reason. Carrier rows are compared only by `is`, never value equality, including equal cloned dicts. Cut phase is exact str before membership as already required. No rejected object is coerced, repr'd, hashed or passed to equality hooks by the support. Existing caller-side object construction is not attributed to this helper. OwnerRefusal.reason remains an ordinary attribute; no read-only/frozen-error guarantee is added.

## 3. Closed retained state, views and trust boundary

Each of the34 slots has exactly these eleven retained fields:

| Field | Closed meaning |
| --- | --- |
| `call_state` | `not_entered`, `entered`, `returned` or `raised`. |
| `record_state` | `absent`, `reserved`, `committed` or `unqualified`. |
| `attempts` | Exact integer0 or1; bool is not an integer input. |
| `raw_return` | The actual fake return object by identity, otherwise None. A returned None is distinguished by `call_state=returned`. |
| `raw_error` | The actual fake invocation Exception object by identity, otherwise None. Never stringified, inspected for args, flattened or replaced. |
| `conversion_error` | The actual converter Exception object by identity, otherwise None. It does not overwrite `raw_error`. |
| `conversion_result` | The actual converter return object by identity, including a malformed proposal, otherwise None. |
| `pending_record` | The supplied complete trusted pending-record dict by identity, otherwise None. |
| `committed_record` | The separately supplied complete trusted committed-record dict by identity, otherwise None. |
| `cut_ref` | The submitted opaque cut sentinel by identity when its selected cut is reached, otherwise None. |
| `reason` | None, `complete_error`, `cut_before_entry`, `cut_after_outcome`, `cut_before_commit`, `cut_after_commit`, `conversion_exception`, `conversion_protocol`, `unsupported` or `oversize`. |

Unused slots have call_state not_entered/record_state absent/attempts0 and all reference/reason fields None. A slot ordinal and kind are its fixed constructor/lookup position, not extra mutable records. The constructor's raw_return is the retained fake library; each lookup's raw_return is its retained fake callable. There is no second library/callable collection that can lose or replace these owners.

`inspect_owner` returns an exact dict with keys `next_lookup,in_progress,stopped,constructor,lookups`. Constructor is an exact eleven-key StepView; lookups is a33-element tuple of such views in the fixed order. The views copy only fixed scalar metadata. All reference-valued fields retain the actual original objects; views do not walk, deepcopy, serialize, compare, hash, repr or coerce their object graphs. Inspecting does not invoke a fake/converter, append a record, consume a slot or change state. Views cannot mutate owner's scalar fields; trusted callers must not mutate the referenced raw objects or records.

Fixed reference-slot/record counts are **not** byte, heap, RAM, traceback, exception-context/cause, foreign-object or arbitrary graph bounds. An exception reference can retain an arbitrarily large graph. This helper neither claims to measure it nor serializes it to obtain an invented bound. Scope does not include concurrent mutation or arbitrary hostile caller objects.

## 4. Invocation, conversion and commit semantics

`invoke` and `convert` are trusted exact Python functions supplied by independent in-memory tests; no callable-object adapters are admitted. Neither fake may import or call ctypes, Native, a producer, project validator, OS/native API, filesystem, network, subprocess, environment or clock. A function type check is not a sandbox: source review and the fixed pure test registration establish these restrictions.

`pending_record` is an exact dict supplied as a complete source-shaped literal by the test oracle. Before invocation the selected array receives that exact dict once and the slot retains the same reference. It is not altered in place by the support. The constructor array can have at most one row; the lookup array is the complete actually reserved prefix, at most33. Earlier rows and their identities remain unchanged. At every new run admission, carrier keys must still name the original lists and their complete row-identity sequences must equal the owner's retained current sequence; detachment, equal-clone replacement or an extra/missing row refuses without calling a fake.

The support sets attempts1/call_state entered immediately before its one `invoke()` call, with in_progress true. A callback inspecting the Owner sees this state. Here **entered means the controlled Python fake invocation boundary**, not exact entry into any hidden ctypes or native operation. The explicit synchronous model contains no interruption between that assignment and the fake call; arbitrary real interruptions there are excluded.

On ordinary fake return, retain raw_return by identity and set call_state returned before later conversion/commit work. On an ordinary fake Exception, retain raw_error by identity and set call_state raised before conversion. Do not read its message, args, attributes, traceback, cause/context/notes or class name. No retry, replacement constructor, fallback lookup or extra validation call occurs. An unexpected BaseException outside Exception is not caught/converted into success; its last retained state can remain entered/reserved with in_progress true. That state is semantically unqualified, not a promised transition to record_state unqualified, and no complete-state guarantee is claimed.

`convert(call_state, raw_object)` is called once after a returned/raised outcome unless an earlier cut stopped the operation. raw_object is exactly raw_return or raw_error. The converter returns an exact two-element tuple `(status, record)` with status one of `complete_success,complete_error,unsupported,oversize`:

- `complete_success` requires call_state returned and an exact dict record distinct from pending_record.
- `complete_error` requires call_state raised and an exact dict record distinct from pending_record.
- `unsupported` or `oversize` requires record None; it is an explicit unsuccessful conversion decision, not a zero-sized typed observation. The complete raw return/error remains retained.
- Any other shape/type/status/outcome mismatch is conversion_protocol, with the returned proposal retained in conversion_result and no typed commit.

The converter is trusted to supply the complete correct P3-shaped record and a separately justified fit decision. **This support does not validate P3 semantics, compute canonical bytes, enforce P3/whole-carrier budgets, infer native error classes or authenticate that decision.** Fake complete_success means only a supported model commit, not native success. An oracle may intentionally use a semantic-invalid P3-shaped body to demonstrate that this module is not a validator; tests must label that limitation rather than count it as native evidence. Real diagnostic conversion/fit/source qualification remains a separate unresolved integration obligation.

An ordinary converter Exception is retained separately as conversion_error and yields unqualified/conversion_exception. A returned unsupported/oversize/protocol failure yields unqualified with its exact reason. All set stopped true; raw outcomes and the prior pending row remain. No conversion failure is translated into a ConstructorError or BindingLookupError containing an invented return/error, and no partial new record replaces the pending one.

For an admitted complete decision, commit consists of replacing the one selected array element with the complete distinct record and retaining that same object as committed_record; record_state becomes committed only with those associations established in the synchronous model. The old pending object remains retained in pending_record. The support never mutates either record's body. A complete_error commit sets reason complete_error/stopped true and cannot enable later lookups. A complete_success constructor enables lookup0; a complete_success lookup advances next_lookup by exactly one. Finishing lookup32 permits no further constructor or lookup.

Every ordinary admitted return path clears in_progress before returning its view. Any unsupported/oversize/protocol/conversion/cut outcome stops the owner without changing earlier completed slots. Complete success is the only path that permits the next operation; the completed model's extra-call refusal does not undo its successful slots. An ordinary operation cannot reinitialize, reset, reseed or clear this owner.

## 5. Explicit synchronous cut sentinels, not arbitrary atomicity

`cut` is None or an exact two-element tuple `(phase,sentinel)`. Phase is an exact string from `before_entry,after_outcome,before_commit,after_commit`; sentinel is an opaque trusted in-memory test object, retained without inspecting it. Invalid cut admission refuses before any owner mutation or callback. A reached cut stops the operation, retains sentinel as cut_ref, records the matching cut_* reason, clears in_progress and returns StepView without further callback or retry. No generic failure-hook system is added.

| Cut | Retained state and effects |
| --- | --- |
| before_entry | Pending row already reserved; attempts0, call_state not_entered, record_state unqualified, no invocation/conversion, owner stopped. The reservation is consumed; no retry. |
| after_outcome | Exactly one fake invocation has returned or raised; raw outcome reference and state are retained; no converter; pending row remains and record_state unqualified. |
| before_commit | Exactly one invocation and converter have completed; conversion_result and raw outcome retained; complete proposed record has not replaced pending; record_state unqualified. This cut is reached only for an otherwise complete decision. |
| after_commit | Exact typed record is already in both the array and committed_record. Preserve record_state committed, raw outcome, previous pending object and completed lookup advancement; then stop. This models later caller bookkeeping failure, not a lost completed call. |

There is no injected instruction-level cut inside a dict/list/ref assignment, no rollback claim after actual MemoryError and no atomicity claim against KeyboardInterrupt/SystemExit, cancellation, thread/process death, interpreter corruption or an asynchronous exception between Python instructions. Actual exception construction/conversion/recording can itself fail. The helper proves only its admitted ordinary synchronous transitions and selected explicit sentinels. Pending/reserved is not proof that an operation happened; an unqualified pending row must never be promoted to a complete failed/successful native record.

## 6. Capability-aware path selection without dispatch

`select_paths` is pure and returns exactly `bootstrap_recording_complete,native_cleanup_allowed,native_emission_allowed,cleanup_route,emission_route`:

- bootstrap_recording_complete is true only if the constructor and all33 lookup slots have committed complete_success, next_lookup33, in_progress false and stopped false. It is a model recording predicate, **not actual native usability**.
- native_cleanup_allowed and native_emission_allowed are always literalFalse in this bootstrap-only support.
- cleanup_route is exactly `no_explicit_native_owners`; emission_route is exactly `existing_python_stdout_only` for every admitted state.

No cleanup/emission callback is accepted or invoked by this API. Even a complete fake bootstrap does not establish Host std-handle values, callable behavior, self identity, job membership, actual acquired resources, end-to-end delivery or native stdout capability. In a future integration, those require separately qualified source dependencies. This conservative selection prevents merely publishing an owner earlier from selecting `_cleanup`'s unavailable snapshot dependencies or main1499's uninitialized Native.write/host_stdout path.

No CreateJobObject/CreatePipe/CreateProcess/direct-control acquisition has occurred within the two modeled constructor cuts. No job query, empty-job/EOF assertion, synthetic close, FreeLibrary obligation or15-call native tail is introduced. Existing R3 bootstrap DLL references remain process-lifetime. No-op local explicit cleanup is not a claim that Root's already-started Host process/streams/tasks are settled or that a real Worker/Host has exited.

## 7. Scope and unavoidable protocol gaps

The exact arrays are prospective Host Creation destinations only. P3 InitializationObservation's unresolved state, complete OSError alternative and BindingObservation's complete AttributeError/success associations retain their existing meanings. A structural pending lookup is not a new qualified interruption/error variant. Unsupported diagnostics, invalid exposed handles/addresses, oversized conversion, missing end clock or failed bookkeeping remain unqualified; no record, field, cap or relation is added to P3/R3.

Worker initialization precedes READY/GO. Existing BootstrapResult requires canonical ResultPayload→GoObservation, real GO48/read/EOF/stdin-close associations and a complete nonempty direct-call prefix. PendingReadMarker also requires its actual blocked-read control. Neither is a valid early Worker error carrier. Internal retention cannot make untransmitted Worker facts externally observable.

Generic early Host LMF1 delivery is also not repaired. [Root1300–1310](../scripts/local_member_intake_bootstrap_observer_20261015_1.ps1) expects LMR1 first outside the six fixed NoHandoff controls; [Root1405–1443](../scripts/local_member_intake_bootstrap_observer_20261015_1.ps1) only builds its parsed Host range on the accepted-control delivery path. Raw artifacts with a null parsed carrier remain honest incomplete evidence. This support must not relabel that evidence or change the fixed framing/qualification branch.

Thus T4.2 cannot claim all constructor cuts, universal fitting diagnostics, complete whole-prefix/protected reservations, entered/returned native latches, complete cleanup certificates or a positive filesystem profile. Real draft integration remains R2/source work, distinct from these pure tests. All authority flags and UNKNOWN liabilities remain held/false.

## 8. Independent literal oracles, intended RED/GREEN and acceptance

Every item below is **UNEXECUTED**. Root must separately register exact new paths/source pins, full literal case-sensitive IDs, expected outcomes, report/capture guards, all held-source identities, launcher/owned identities and the original hard end before any collection or runtime. Every writer holds during a root launch. No current whole-project regression or deadline amendment is released.

1. Independent test/oracle authoring precedes behavior implementation. Literal cases cover new-owner publication and two distinct exact array aliases; all34 initial slots; supported constructor/error/lookup-prefix states; all33 ordered successful lookups; every reached cut and every conversion status/Exception; raw library/callable/error/conversion-error/cut identity retention; None returns; exact committed/pending identities; no record-body mutation; detached arrays/equal clones/extra rows; duplicate/wrong-order/reentrant/stopped/completed refusals before callbacks; and every PathSelection value.
2. Trusted fakes count their own invocations and inspect exact owner state from inside invocation/conversion. At most one invocation and converter call occurs per admitted slot; forbidden callback sentinels must remain uncalled. State/identity assertions, not call-count labels alone, establish the promised outcome. Independent expected views and complete P3-shaped literals are not derived from the new implementation or an old producer/validator.
3. Register initial interface stub separately. Each behavioral test must invoke it through a wrapper that catches **only NotImplementedError**, then raises the registered explicit intended missing-behavior AssertionError. This intended RED assertion must occur inside the test case, not a setup fixture that pytest reports as an error. Guards cannot accept missing implementation as successful refusal. Use a safe custom BaseException sentinel for the excluded-BaseException demonstration, not pytest-interrupting KeyboardInterrupt or SystemExit. Derive the full RED ID list before launch, accept actual assertion failures/zero errors-skips/owned exits and all pins, then release only the new helper's corresponding behavior. The same identities must genuinely GREEN afterward.
4. Full evidence captures retain every supplied/expected/actual record body plus a complete deterministic typed node/edge/reference table for each small trusted fake graph, all slot/view values and every alias edge. Raw exceptions are captured using the independently declared fake class/args/attributes and every constructed edge, not repr/str/hashes-only or an unbounded runtime traceback walk. This proves the invented graph only; no arbitrary exception-graph completeness/budget is claimed. No prefixes, sampled fields or graph-destroying value-only equality substitute for identity checks.
5. Review at least one owner-loss sensitivity mutation (drop/clone an original array or raw-return reference) and one retry/gating mutation against existing fixed cases, preserving the exact base snapshot. A mutant must produce the intended state/identity/call-count AssertionError, not an import/error/timeout. Restore exact base after fully settled owned execution; same affected identities GREEN before final pure acceptance.
6. Review new helper/test/oracle source completely. Run only separately registered quality actions on those new files, retain exact manual deltas/full unnormalized AST formatter equality and complete diagnostics; old held lint findings are not silently fixed or called whole-project green. Final pure adjacent acceptance includes every previously accepted pure identity plus the exact derived new identities, full bodies/graphs, zero failure/error/skip, real tool/owned exit and all old/new pins. Component acceptance is not full-project/native acceptance.

For project-style consistency, future source uses explicit snake_case names, exact type tests at this API boundary, closed string tokens and ordinary explicit loops over the fixed slots; no dynamic import/plugin/decorator registry, exception coercion, generic serializer or hidden helper role. In the **raised-diagnostic oversize example**, the view has `call_state=raised,record_state=unqualified,reason=oversize`, the original raw_error retained and no committed_record. A **returned-outcome oversize** view instead preserves `call_state=returned`, the original raw_return, raw_error None, record_state unqualified/reason oversize and no committed_record. A separate supported-error view has `call_state=raised,record_state=committed,reason=complete_error`, retains its original raw_error and the complete distinct committed_record. None of these views is substituted for another.

Prospective pytest payload, **not authorized to launch from this document** (root must materialize its reviewed bounded ownership wrapper first):

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q tests/test_local_member_intake_bootstrap_owner_20261016.py -o junit_logging=all -o junit_log_passing_tests=true --junitxml=logs/local_member_intake_recording_20261016_1/bootstrap_owner_focused_1.xml
```

The exact adjacent/collection IDs, source-release gate and sensitivity commands are future registration, not guessed here. Final success is limited to the independently tested finite pure retention contract. All native/G4/filesystem/provider/history/account/model/full-regression gates stay OPEN/UNEXECUTED. No dependency, security setting, market data, raw/archive packet, account/broker/order/model/training, staging/commit or unrelated cleanup is in scope. At15:28:38Z launch nothing and follow root's truthful handoff/deletion/stop; never autoextend, archive, shut down or carry another day.
