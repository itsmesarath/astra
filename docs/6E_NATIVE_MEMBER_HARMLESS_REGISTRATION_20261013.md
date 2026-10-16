# Provider harmless-control registration — 2026-10-13

This closes the separate test-only variant of the [production execution registration](6E_NATIVE_MEMBER_EXECUTION_REGISTRATION_20261013.md) before T4 source/control creation. It is a prospective declaration, not observed qualification. All seventeen controls remain UNEXECUTED at save. The six-hour [window](6E_NATIVE_MEMBER_DEVELOPMENT_WINDOW_20261013.md) and all production resource/parser/identity/cleanup policies remain unchanged.

## Fixed variant

Exactly eight fields: `schema,provider_execution_manifest_sha256,control_id,worker,argument_template,request_template_sha256,expected_outcome,native_codec_imports`. Schema=`native_member_harmless_execution_v1`; native_codec_imports=literalFalse. The production manifest is complete and separately pinned before any launch. Worker is exactly `{logical_id,relative_path,raw_bytes,raw_sha256}` with logical_id=`harmless_worker`, relative_path=`tests/native_member_provider_control_worker_20261013.py`, actual positive raw_bytes<=1048576 and actual raw SHA256. No caller path, arbitrary command, reduced limit or environment override is accepted. Argument template is exactly `["--mapping-handle","HOST_GENERATED_UINT","--mapping-size","1048576","--control",control_id]`.

The request template is a complete canonical eleven-field production request with attempt_token exactly64zeros. Host substitutes only a fresh32-byte token; actual full request bytes/H are retained. Control variant H is mandatory before creation. Production cannot select this test worker or control grammar. Harmless response retains exact seven production envelope keys and framing but schema=`native_member_harmless_response_v1`; production rejects it. `complete` evidence is exactly `{schema,control_id,request_body,mapping_sha256,result}`, schema=`native_member_harmless_observation_v1`; request_body is the full actual copied eleven-field request and mapping_sha256 binds all1048576bytes. Root/tests compare with independently constructed expected bytes/body, not adopted child output.

`ordinary_refusal` has status=`refused`, evidence=null, failure_kind=`invalid_member`, exit2. Complete responses have status=`complete`, failure_kind=null, exit0 except the explicitly declared corruption/nonzero controls. Worker-reported unmaps/handle closes are never relabelled as parent-observed cleanup. Failed streams retain their complete deterministic intended byte declaration plus actual bounded channel receipts; no parsed response is manufactured.

## Exact observation bodies

Mapping result has exactly: `mapping_bytes=1048576,inherited_handle_flags=1,read_access="FILE_MAP_READ",shared_write_denied=true,shared_write_winerror=5,copy_view_created=true,copy_offset=1048575,copy_before=0,copy_after=165,shared_after=0,shared_after_sha256=<original full mapping H>,copy_view_unmapped=true,read_view_unmapped=true,mapping_handle_closed=true,native_codec_imported=false`. COPY writes are private; successful shared WRITE mapping fails qualification. This is not a malicious-child security sandbox.

Basic result exactly `{step:"response_ready",native_codec_imported:false}`.

Memory-pressure result exactly `{attempted_bytes:536870912,attempted:true,memory_error_caught:true,allocation_returned:false,allocation_length:null,retained_allocation_object:false,native_codec_imported:false}`. Independently attempt `bytearray(536870912)` under unchanged268435456-byte process/job memory limits. Only caught MemoryError qualifies; return the full observation and exit0. Unexpected allocation success releases that object and exits74 without qualifying evidence. Any other exception, crash, kill, timeout or unknown code fails, never inferred as MemoryError. No returned allocation object exists in the qualifying branch.

Grandchild result exactly `{executable:<fixed registered interpreter>,argv:[<same>,"-I","-S","-B","-c","pass"],creation_attempted:true,create_returned:false,winerror:<actual positive u32>,returned_process_handle:false,returned_thread_handle:false,resumed:false,native_codec_imported:false}`. Fixed suspended/no-breakaway attempt only. Invalid-parameter/ABI/identity failures do not qualify; retain actual error, not an invented universal Windows code or sole-causation claim. Unexpected creation is never resumed, is cleaned by retained handles and fails qualification. [Official job-limit semantics](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information) distinguish active-process policy from a guaranteed API error.

## Seventeen exact control IDs

Pre-launch static-review refinement (no control executed): qualifying grandchild refusal is narrowed to actual CreateProcessW=False, both returned handles zero and error in the exact set `{5,1816}`. These are the documented [access-denied](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--0-499-) and [quota](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--1700-3999-) categories, not a promised active-process-limit return code. The fixed interpreter raw guard and actual host active_process_limit=1/in-job observations are also required. This establishes only observed access/quota-class denial under the queried policy, not sole causation. Every other error, including2/3/87/193, and any returned handle fail qualification. The harmless parser independently enforces the same lexical depth64/node128/integer20 and strict UTF8/no-BOM/no-float/nonfinite bounds before JSON allocation, plus duplicate/canonical checks; it does not import the production parser.

| ID | Complete declared behavior | Expected host outcome |
| --- | --- | --- |
| mapping_roundtrip | Mapping result above, complete response, exit0 | complete |
| ordinary_refusal | Exact harmless refusal envelope, exit2 | input_refused |
| never_read | No mapping/copy; sleep60seconds | timeout |
| respond_then_wait | Basic complete response/flush then sleep60seconds | timeout |
| stdout_excess | Exactly4194305 X bytes, bounded writes | transport_failed |
| stderr_excess | Exactly65537 X bytes on stderr | transport_failed |
| stderr_nonempty | Basic complete response plus one E byte on stderr, exit0 | transport_failed |
| truncated_response | Basic complete frame minus final byte, exit0 | transport_failed |
| trailing_response | Basic complete frame plus one X byte, exit0 | transport_failed |
| duplicate_response | Basic complete frame twice, exit0 | transport_failed |
| wrong_token | Flip first token hex digit:0→1, otherwise→0; basic response, exit0 | transport_failed |
| wrong_request_hash | Same deterministic mutation of request hash only, exit0 | transport_failed |
| wrong_manifest_hash | Same deterministic mutation of manifest hash only, exit0 | transport_failed |
| valid_then_exit_73 | Complete basic frame/flush then explicit exit73 | worker_failed |
| memory_error_71 | No response, deliberate exit71; classification-only | resource_failed |
| memory_pressure | Genuine512MiB attempt and exact caught-MemoryError observation | complete |
| grandchild_denied | Fixed suspended creation denial observation above | complete |

Overflow cases require actual cap detection, termination.reason=`output_limit`, bounded retained prefixes, exact-owned cleanup; malformed JSON alone is insufficient. Child exit/termination races retain actual code. Every passing cohort requires unchanged queried limits, exact owned identity, complete applicable channel accounting, final empty job and successful cleanup. Native-codec imports remain absent. Native-free fake-API setup/cancellation/cleanup failure tests are separate: no deliberate real leaked handle/process to simulate a failure. Malformed mapping/header/length/padding/parser controls are independently declared native-free worker-parser cases; no arbitrary public mapping override is introduced.

The frozen prior containment code is read-only source evidence, not a provider control result. Harmless acceptance must precede any provider native import initialization. Unknown crashes are failures, not resource proofs; all28public authority flags remainFalse and no historical/account authority follows.
