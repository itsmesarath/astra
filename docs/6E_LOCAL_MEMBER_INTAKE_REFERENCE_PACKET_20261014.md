# Local member intake official reference packet — 2026-10-14

## Status and evidence boundary

**T1 PARTIAL: reference availability and initial semantic extraction are complete; exact candidate ABI/schema/mechanism definitions remain unresolved.** This advances the [G1–G4 plan](../tasks/local_member_intake_g1_g4_plan_20261014.md) as documentation under the direct continuation and standing routine permission. No proof task/checkpoint is complete. G1–G4 and every L1–L15 acceptance group remain unexecuted.

At2026-10-14T15:08:34.4146663Z, root retrieved thirteen complete official SDK documentation Markdown bodies at immutable MicrosoftDocs/sdk-api commit `656e9656bfaef34dd29cd7ee9e1146aec17e924c` (commit time2026-10-09T20:25:44Z). The [source pin manifest](../logs/local_member_intake_reference_sources_20261014_1.json) retains every exact repository path/URL, full raw byte count and SHA256: **148832bytes total**. Bodies were read in memory for documentation and were **not saved as a local source mirror**. Hashes identify the complete remote documentation bodies, not native DLLs, SDK headers, observed platform behavior or a closed filesystem profile. Immutable source URLs can be retrieved later and compared before registration; offline source-body retention is still future preparation.

Microsoft Learn rendered pages were also read for their parameter, return, member and remarks sections. Their section selectors below are navigation aids; the immutable repository paths/body hashes supply the source identities. No Windows version/filesystem/privilege/ABI query, caller-member file read, native constructor, test or decoder ran. A short PowerShell HTTP retrieval completed exit0; it fetched only named official text sources.

The [contract](6E_LOCAL_MEMBER_INTAKE_CONTRACT_20261014.md) stays fixed. This packet supplies documented constraints for an experiment design, not protection claims. Current hard end remains **2026-10-14T16:09:49Z /17:09:49 Lisbon**.

## Source selectors and decisions they constrain

| Source | Rendered sections | Documented fact and planning consequence |
| --- | --- | --- |
| [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew) | Parameters:dwDesiredAccess,dwShareMode,lpSecurityAttributes,dwCreationDisposition,dwFlagsAndAttributes;Return value;Remarks:Symbolic Link Behavior,Directories,Synchronous and Asynchronous I/O Handles | Existing-only opening, access/sharing compatibility and handle inheritance are distinct controls. A leaf reparse flag does not establish this contract's entire ancestry mechanism. T5/T6 must prove that mechanism and competing mappings/handles. |
| [ReadFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-readfile) | Parameters:nNumberOfBytesToRead,lpNumberOfBytesRead,lpOverlapped;Return value;Remarks:Synchronization and File Position | Requested length, returned count and completion/error state need separate fields. Pending asynchronous I/O is not a completed read; synchronous calls can block. T7/T8 must resolve one exact supported mode, buffer ownership and failure dispositions. |
| [GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex) | Parameters:FileInformationClass,lpFileInformation,dwBufferSize;Return value;Remarks | Query class determines the output structure. Some class behavior depends on OS/drivers. T1/T4 must pin exact class/type/layout/size/error associations rather than accept arbitrary dictionaries. The correct reference is under winbase.h. |
| [GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew) | Parameters:cchFilePath,dwFlags;Return value;Remarks | Buffer units, successful length and insufficient-buffer length have different null-terminator treatment. Opened/normalized and DOS/GUID/NT outputs are distinct representations. T4 preserves the complete observed name and relates it to exact supplied spelling through a qualified rule. |
| [FILE_ID_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info) | Syntax;Members:VolumeSerialNumber,FileId;Requirements | Volume identity and a128-bit file identifier form the documented object identity fields. Full native-to-logical conversion and target compatibility still need exact authoritative definitions plus actual registered observations. |
| [FILE_STANDARD_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_standard_info) | Syntax;Members:AllocationSize,EndOfFile,NumberOfLinks,DeletePending,Directory | Allocation size and logical EOF are distinct; link count, pending deletion and directory status are separate observations. T4/T5/T7 require exact domains and initial/post-read facts. |
| [FILE_ATTRIBUTE_TAG_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_attribute_tag_info) | Syntax;Members:FileAttributes,ReparseTag | Attribute and reparse-tag fields are distinct. T1 still needs the complete chosen attribute/tag/placeholder policies and unavailable-query dispositions. |
| [FILE_BASIC_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_basic_info) | Syntax;Members:CreationTime,LastAccessTime,LastWriteTime,ChangeTime,FileAttributes | The time fields use FILETIME representation; ChangeTime tracks metadata changes separately from LastWriteTime's data-stream changes. Exact signed/domain/absence/projection and stability rules remain T1/T4 work. |
| [GetVolumeInformationByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationbyhandlew) | Parameters:lpVolumeSerialNumber,lpMaximumComponentLength,lpFileSystemFlags,lpFileSystemNameBuffer;Return value | Returned serial information belongs to the formatted volume, not manufacturer hardware identity. Filesystem names/flags are observations to register; this packet does not establish the machine's filesystem. |
| [GetFileType](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfiletype) | Return value;Remarks | Unknown type can represent an unknown object or a call error; the error result distinguishes them. Disk type alone is not the complete regular-file/local-filesystem admission proof. |
| [CloseHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-closehandle) | Return value;Remarks | Closing a process/thread handle does not terminate that process/thread. Closing a mapping handle can leave views open. T8 must separately account for owned processes, mapping views and every handle disposition. |
| [CancelSynchronousIo](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelsynchronousio) | Parameters:hThread;Return value;Remarks | Cancellation marks operations and does not wait for their completion. A request can finish normally, be canceled or fail. T3/T8 must observe completion/cleanup and cannot equate a successful cancel call with termination. |
| [CancelIoEx](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex) | Parameters:hFile,lpOverlapped;Return value;Remarks | Cancellation applies to operations in the calling process and requests cancellation without waiting. Associated OVERLAPPED state must survive until completion. The exact candidate architecture and terminal receipts remain unqualified. |

Each row maps to the same named SDK file in the complete source manifest. These are semantic source definitions, not selected operational flags or ABI layouts for a provider.

## EOF cross-reference that must survive implementation

The separate official [Testing for the End of a File](https://learn.microsoft.com/en-us/windows/win32/FileIO/testing-for-the-end-of-a-file) page distinguishes synchronous zero-byte successful EOF from asynchronous ERROR_HANDLE_EOF completion. This supplemental conceptual page was consulted but **is not one of the thirteen immutable raw-body pins**; it requires its own immutable source/body capture in a future complete reference corpus.

The contract's one1-byte probe requires the chosen profile's exact qualified EOF disposition. It does not prescribe that every mode returns the same Boolean/error pair. The read mode, completion association and count/status handling must be locked together. An empty buffer, pending call or a cancel-request success cannot establish complete EOF. T7 will compare independent exact transcripts and actual contained I/O outcomes.

## Exact unresolved preparation work

| Item | Required next evidence | Gate/task |
| --- | --- | --- |
| Complete SDK/header ABI crosswalk | Authoritative chosen header definitions for every typedef,enum,constant,alignment,offset,size,pointer-width and calling convention, reconciled with registered runtime | G1;T1/T4 |
| Platform and filesystem support | Exact candidate support policy, actual runtime/build/filesystem observations under qualified containment and refusal of unsupported cases | G1;T4 |
| Whole path admission mechanism | Official basis and finite controls for root/volume/ancestor/leaf substitution, namespace/alias/reparse/link/recall cases; handle lifetimes and comparison rules | G2;T5/T6 |
| Existing writer/mapping effects | Exact permitted/refused access and mapping schedules; prevention or refusal demonstrated before accepting bytes | G2/G3;T6/T7/T9 |
| Raw observation schemas | Full field order/types/domains/absence/error handling and exact native-to-logical conversions; no inferred numeric struct layout | G1;T1/T4/T10 |
| Resource/lifecycle architecture | New independently registered birth/initialization/open/read/close/transport/cancel/owned-exit mechanism and limits | G4;T2/T3/T8 |
| Complete reference corpus retention | Preserve complete official bodies/selector crosswalk for all chosen APIs and supplemental conceptual references before future execution; current source manifest is metadata only | T1/T2 |
| Independent fixture/read oracles | Complete invented bytes, precise count/status/buffer association, every ledger/slice/EOF/control body and trusted pre-acquisition request pin | G3;T2/T7 |
| Future regression deadline | Supported current registered deadline handling with narrowly reviewed harness change/snapshot if needed; accepted13:33:18literal stays held today | T2/T11 |

T1 is therefore **partial and unchecked**. Reference availability progressed; complete exact definitions and candidate mechanism still need work. No gate can close from these pages alone. The immediate next useful work is the documented ABI/schema/mechanism crosswalk, followed by reviewed prospective proof registration. All actual OS/file/race/resource experiments remain unexecuted.

## Preservation and claims

No accepted code/resource/contract/plan was edited to collect references. Source retrieval did not inspect native binaries, Windows security settings or protected data. All existing authorities and UNKNOWN liabilities stay held. The packet does not authenticate the OS, file owner/vendor, source, receipt or historical content. Later public provider/L1–L15 acceptance, archives, historical parity/capacity/calendar/one-genesis continuity and account/economic validation remain separate.

The source-driven skill guided official-source retrieval and explicit unresolved claims. Routine permission is already established; the outstanding work is technical definition and finite evidence, not another approval question.

