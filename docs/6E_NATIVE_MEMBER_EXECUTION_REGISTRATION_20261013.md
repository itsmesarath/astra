# Native-member execution registration — 2026-10-13

## T1 schema closure, not runtime acceptance

This exact preparation refines the [reviewed design](6E_NATIVE_MEMBER_EXECUTION_DESIGN_20261013.md) for the [six-hour implementation window](6E_NATIVE_MEMBER_DEVELOPMENT_WINDOW_20261013.md). Existing public protocol, closed profile and 13-artifact native RuntimeManifest remain unchanged. No technical gate is replaced by routine human approval. New source hashes are taken from actual stable files before each launch, never guessed here.

The parent remains native-codec-free. Production has one fixed worker and no public path, command, callback, resource-policy or diagnostic-output hook. A separate fixed test-only control worker, `tests/native_member_provider_control_worker_20261013.py`, is added to the prospectively registered new paths. It exercises the SAME internal host mapping/job/channel/cleanup machinery under a separate pinned harmless registration; production's fixed entry point and decode-only grammar cannot select it. This is the twelfth new path, not an accepted old-file edit. Root owns facade/types/resources; distinct authors own engine, host/worker and independent tests/control worker. Every writer holds during every runtime launch.

## Exact ProviderExecutionManifest

All dictionaries have exactly the declared keys. Integers are exact ints, not bool; SHA256 values are exact lowercase64hex. H is complete canonical JSON, sorted keys, comma/colon separators, ASCII escaping, no floats/nonfinite. The manifest has exactly these13 fields:

`schema, protocol_sha256, profile_sha256, runtime_manifest_sha256, platform, entry_point, launch_policy, artifacts, bootstrap_exclusions, transport_policy, parser_policy, resource_policy, exit_policy`.

Schema=`native_member_provider_execution_v1`; platform=`windows_amd64_cpython312`; entry_point=`_native_member_worker.py`. Three identity fields are the complete public protocol H, held profile H `5016b1dc56537fdefdac74e56154ceb410307f3677fb08d8455cba8f54c86b0d`, and held runtime H `4aab559ab26a25cf35579dc723cb00d06db933ea65c63d9793a34939191c2ec3`.

`launch_policy` exact keys/values:

```json
{"python_logical_id":"python.exe","switches":["-I","-S","-B"],"worker_arguments":["--mapping-handle","HOST_GENERATED_UINT","--mapping-size","1048576"],"inherit_handles":["mapping_read","stdout_write","stderr_write","nul_read"],"environment_keys":["SystemRoot"],"cwd_policy":"fixed_installation_root"}
```

Only the locally validated SystemRoot value enters the child environment; no PATH/PYTHONPATH/caller data. Fixed checkout and base-interpreter locations are implementation installation choices, not byte-derived inputs. This first provider is source-checkout scoped; held pyproject/package data are unchanged, so no wheel/deployment claim is made.

`artifacts` is six rows, sorted ordinally by logical_id, each exactly `{logical_id,relative_path,kind,raw_bytes,raw_sha256}`. Positive raw_bytes<=4MiB. Exact names: engine→`_native_member_engine.py`, host→`_native_member_host.py`, profile→`_native_member_profile_20261012.json`, protocol→`_native_member_protocol_v1.json`, types→`_native_member_types.py`, worker→`_native_member_worker.py`. Kinds are `python_module_source` or `canonical_json_resource` as appropriate. No arbitrary path lookup. `bootstrap_exclusions` exactly `["six_e_native_member_decode_evidence.py","_native_member_execution_v1.json"]`. The façade anchors manifest H and is excluded from that manifest, avoiding a self-hash cycle. Root independently pins both excluded files in run/whole-source evidence. Worker recomputes manifest H against the parent's anchored request value, then checks every registered artifact. This is not self-authentication or complete import-graph proof.

`transport_policy` exact literal:

```json
{"request_schema":"native_member_worker_request_v1","response_schema":"native_member_worker_response_v1","request_magic":"NMREQ001","response_magic":"NMRES001","length_encoding":"uint32_le","mapping_bytes":1048576,"request_json_max_bytes":1048564,"response_json_max_bytes":2097152,"stderr_max_bytes":65536,"combined_output_max_bytes":4194304,"read_quantum_bytes":65536,"request_padding":"all_zero","response_count":1,"attempt_token_bytes":32}
```

Request has the exact ELEVEN fields in the design. Response has its exact seven fields; no optional/extra transport fields. Positive evidence body retains its stricter1MiB public cap. No literal resource body or semantic input is omitted to meet caps.

`parser_policy` exact literal:

```json
{"encoding":"strict_utf8_no_bom","canonical_json_required":true,"duplicate_keys":"refuse","floats_and_nonfinite":"refuse","max_depth":64,"max_integer_digits":20,"integer_sign":"optional_single_leading_minus","resource_max_bytes":4194304,"execution_manifest_max_bytes":65536,"resource_max_nodes":1048576,"request_max_nodes":128,"response_max_nodes":1048576,"node_definition":"each_object_array_key_and_scalar_once","bounds_checked":"lexically_before_json_object_allocation"}
```

Check byte/depth/node/numeric-token limits BEFORE allocating a parsed JSON tree, then duplicate-key and exact schema/domain validation and canonical re-encoding equality. Complete member_hex has at most524288 lowercase hex characters. Canonical resource generation normalizes only JSON formatting while preserving the full held profile envelope/body. Independently measured read-only T1 resource facts: complete protocol block50627UTF8bytes/2550nodes/depth6/maxintegerdigits7; held profile envelope2761162bytes/164152nodes/depth14/maxintegerdigits20; zero duplicate keys in either. These are observed resource sizes, not universal maxima.

`resource_policy` exact literal:

```json
{"limit_flags":8974,"active_process_limit":1,"process_memory_bytes":268435456,"job_memory_bytes":268435456,"process_user_time_100ns":50000000,"job_user_time_100ns":50000000,"work_ns":12000000000,"teardown_ns":3000000000,"birth_job_assignment":true,"start_suspended":true,"native_in_parent":false,"uncontained_fallback":false,"parent_memory_sandbox":false,"filesystem_sandbox":false,"network_sandbox":false}
```

`exit_policy` exactly `[[0,"complete","complete"],[2,"refused","ValueError"],[70,null,"RuntimeError_identity"],[71,null,"MemoryError"],[72,null,"RuntimeError_private_protocol"]]`. Exit0/complete and exit2/refused BOTH require valid full response/binding, empty stderr, complete channels, exact owned exit, empty job and successful cleanup. Only validated2 becomes public ValueError.70 is identity/runtime uncertainty;71 is explicitly caught MemoryError;72 is malformed private protocol. Unknown codes/uncaught assertions/native crashes are RuntimeError with their actual code retained, not guessed causes. A measured host deadline produces TimeoutError. Cleanup/ownership failure vetoes success and ordinary refusal. KeyboardInterrupt/SystemExit/parent MemoryError clean exact-owned work then propagate; no AssertionError is turned into an ordinary invalid-member response.

## Exact OwnedProviderExecutionReceipt

Exactly21 top-level fields:

`schema,operation,execution_manifest_sha256,attempt_token,started_utc,finished_utc,elapsed_ns,request,parent,child,command,mapping,limits,job,channels,implementation_checks,response,exit,termination,cleanup,outcome`.

Schema=`native_member_provider_owned_receipt_v1`; operation=`decode` for production. Harmless receipts use operation=`control` and a separately registered closed control ID in their registration, never a public provider response. Times are UTC ISO strings with Z; elapsed_ns nonnegative exact int. Entire stages are null if never attempted; within an attempted record unobserved values are null, never fabricated False/zero. Every declared key remains present. Text UTF8<=32768bytes; argv<=16entries. PID/TID positiveu32; FILETIME/u64 counters retain full integers. Receipt hashes/tokens exact64hex.

Nested exact records (all listed keys required):

```text
request = {canonical_bytes, canonical_sha256, member_bytes, member_sha256}
parent = {pid, creation_filetime, image}
child = {pid, tid, parent_pid, creation_filetime, image, in_job_before_resume, resume_previous_count}
command = {executable, argv, cwd, environment}  # environment exactly {SystemRoot}
mapping = {bytes, inherited_access, writable_parent_view_unmapped, write_capable_parent_handle_closed, explicit_inherited_handle_count}
limits = {configured, queried_before_resume, queried_final}
job = {pids_initial, pids_before_resume, pids_final, accounting_initial, accounting_before_resume, accounting_final}
channels = {stdout, stderr}
implementation_checks = {before, after}
response = {parsed_body, canonical_bytes, canonical_sha256, binding_validated, evidence_validated}
exit = {created, resumed, observed, code, creation_filetime, exit_filetime, user_time_100ns, kernel_time_100ns}
termination = {requested, reason, job_attempted, job_winerror, process_fallback_attempted, process_winerror}
cleanup = {completed, closed_handles, unmapped_views, errors}
```

Limits is the six exact nonnegative integer fields `limit_flags,active_process_limit,process_memory_bytes,job_memory_bytes,process_user_time_100ns,job_user_time_100ns`. Accounting has `total_user_time_100ns,total_kernel_time_100ns,total_processes,active_processes,terminated_processes,page_faults` (nonnegativeints). PID collections are complete ordered arrays; no successful-subset removal. Channel has `retained_bytes,raw_sha256,eof,hash_scope`, with hash_scope=`complete` only for observed EOF, otherwise `retained_prefix`. ObservedArtifact has `logical_id,raw_bytes,raw_sha256`; implementation_checks are complete actual registered observations, not invented worker-loaded observations.

request/member counts nonnegativeints; parsed_body is complete seven-field WorkerResponse or null; mapping bytes=1048576, inherited_access=`FILE_MAP_READ`; all observed predicate fields are exactbool. Error codes u32 or null. reason is null or one of `deadline,output_limit,identity_error,protocol_error,host_exception,cancellation,cleanup_failure,memory_error`. Fixed handle names are `job,process,thread,request_write,request_read,stdout_read,stdout_write,stderr_read,stderr_write,nul`, plus `artifact_` followed by one exact registered logical ID or `bootstrap`/`execution`. View names=`parent_write,child_read`. SanitizedError exactly `{operation,kind,winerror}`; operation is one of `CloseHandle,UnmapViewOfFile,DeleteProcThreadAttributeList,TerminateJobObject,TerminateProcess,WaitForSingleObject,QueryInformationJobObject,ReadFile,PeekNamedPipe,CreateProcessW,ResumeThread,identity_check,protocol_check,host`; kind is one of `OSError,RuntimeError,TimeoutError,MemoryError,AssertionError,KeyboardInterrupt,SystemExit,ValueError`; no arbitrary exception message/input value.

outcome is exactly one of `complete,input_refused,setup_failed,transport_failed,identity_failed,worker_failed,resource_failed,timeout,cancelled,cleanup_failed`. Cleanup uncertainty wins over a positive outcome; cancellation/MemoryError still propagate their original exception with secondary cleanup evidence. Receipt never enters deterministic MemberDecodeEvidence or the qualified profile. Private host returns response and receipt for root/test capture; the five public APIs have no persistent writer or receipt-selection hook.

Exact ledger clarification before the first lifecycle test: each nonnull implementation_checks.before/after is exactly the six production artifact observations in manifest order, with the declared three fields. The separately pinned harmless worker (when selected), execution JSON and facade/bootstrap exclusions are held/checked as identity guards, not silently added as seventh native or production artifact rows. Execution JSON is anchored by its own expected H; root retains separate pre/post facade and execution raw pins to break the documented hash cycle. Holding an excluded facade file is not a self-authentication claim. The fixed cleanup logical IDs also permit `artifact_harmless_worker` only for that separately registered test variant. No public evidence or native RuntimeManifest changes.

## Win32 mapping and lifetime declarations

Before the first lifecycle launch, the fixed interpreter guard also uses the already registered native RuntimeManifest `python.exe` row: bounded pre/post raw checks and a retained deny-write/delete read handle. Cleanup permits the exact additional guard name `artifact_python.exe`; the implementation_checks ledger remains exactly six production artifacts. This does not add a new native artifact, import, loaded-identity claim or public evidence field.

The bounded Toolhelp parent-identity query also retains and cleans its own snapshot handle under the exact cleanup name `identity_snapshot`; it scans at most4096 process entries solely to match the just-created owned child's parent. Checked close/retry belongs in the same attempt cleanup ledger. This is not an unrestricted process inventory or a PID-only ownership substitute.

Fixed WindowsAMD64 LLP64 ABI: BOOL/LONG=int32, DWORD=uint32, HANDLE/LPVOID=voidpointer, SIZE_T=uintptr64; validate structure sizes/offsets before process creation. kernel32 is loaded as a system DLL, not caller input. Added signatures:

```text
CreateFileMappingW(HANDLE, SECURITY_ATTRIBUTES*, DWORD, DWORD, DWORD, LPCWSTR) -> HANDLE
MapViewOfFile(HANDLE, DWORD, DWORD, DWORD, SIZE_T) -> LPVOID
UnmapViewOfFile(LPCVOID) -> BOOL
DuplicateHandle(HANDLE,HANDLE,HANDLE,HANDLE*,DWORD,BOOL,DWORD) -> BOOL
GetCurrentProcess() -> HANDLE
GetHandleInformation(HANDLE,DWORD*) -> BOOL
CloseHandle(HANDLE) -> BOOL
```

Use INVALID_HANDLE_VALUE for pagefile backing, NULL name, PAGE_READWRITE=4, fixed size1048576; initial handle noninheritable. Parent fills via FILE_MAP_WRITE=2, then DuplicateHandle to same process with desired FILE_MAP_READ=4, inherit=True, options=0 (NOT DUPLICATE_SAME_ACCESS=2). Unmap writable view and close write-capable handle before childcreation; explicit inherited list contains only readmapping/stdout/stderr/NUL. Child maps FILE_MAP_READ over exactsize, copies then unmaps/closes. No executable pages/large pages/security elevation. SECURITY_ATTRIBUTES natural x64 offsets are0/8/16, size24, never packed. GetHandleInformation checks inheritance flags, not access rights; it cannot substitute for the shared-write denial control. All attribute backing arrays stay alive through CreateProcessW, which requires bInheritHandles=True with the explicit HANDLE_LIST and birth JOB_LIST.

Important corrected guarantee: FILE_MAP_READ permits read-only or **private copy-on-write** views. Harmless control requires denial of SHARED FILE_MAP_WRITE and unchanged shared bytes under any private COPY view, not an impossible blanket denial of private writes. This is trusted-host transport consistency, not a malicious-child/same-user security sandbox.

Authoritative declarations: [CreateFileMappingW](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-createfilemappingw), [MapViewOfFile](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-mapviewoffile), [DuplicateHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-duplicatehandle), [mapping rights](https://learn.microsoft.com/en-us/windows/win32/memory/file-mapping-security-and-access-rights). Existing birth-job/attribute/pipe/accounting declarations are source-grounded in the frozen [prior containment implementation](../scripts/native_profile_containment_20261012_1.py) and its pinned official reference corpus, not imported or relabelled as new acceptance. New host must independently validate actual ABI and harmless controls before native calls.

## Initial preservation and staged release

At09:22:40UTC, the new implementation baseline checked the exact428registered paths/hashes against held freeze H`ea97ad13f0cc254b10f377a68bdec4e00e31140e3ba9ca3241cac8a83693fa0e`; all11original proposed paths absent, zero staged. Contract/annex/profile/freeze hashes matched their held values. Newly added test-control path must also be checked absent before author release. Existing source/plan/profile hashes are recorded in the [baseline](../logs/native_member_provider_20261013_1/baseline_1.json).

T1 is preparation only. First release is independent collected interface RED, then native-free types/resources/preflight GREEN. No decoder or process control launches until their separate cohort, source pins, declared expectations, and preceding checkpoint are registered. No native-output-as-oracle, weakened cap or automatic history/account release follows.
