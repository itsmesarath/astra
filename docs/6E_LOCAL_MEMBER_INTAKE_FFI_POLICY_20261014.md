# Local intake FFI error policy candidate — 2026-10-14

PROPOSED / UNIMPLEMENTED / UNEXECUTED. This closes a source-selection question in the [preparation packet](6E_LOCAL_MEMBER_INTAKE_PROOF_PREPARATION_20261014.md), not T1/T2, an installed-runtime identity or a filesystem gate. No Python import or DLL load was performed.

The complete [CPython ctypes documentation](reference_corpus/local_member_intake_20261014_1/ffi_ctypes.rst) and [licence](reference_corpus/local_member_intake_20261014_1/ffi_python_LICENSE.txt) are retained at commit `caad9047cb13a4e60eb708ce07578576ce9a84c9`, with raw identities in [supplement4](../logs/local_member_intake_proof_20261014_1/retained_reference_supplement_4.json). This was the commit returned for the latest `Doc/library/ctypes.rst` change on the official3.12branch; it does not identify the installed interpreter build.

## Source-backed policy

The retained selectors `class:: WinDLL`, `use_last_error`, `function:: get_last_error`, `function:: GetLastError`, `attribute:: restype` and `attribute:: argtypes` distinguish ctypes' thread-local saved error from a direct Windows error query. The proposed binding uses `WinDLL` with `use_last_error=True`, explicit argument/result types and registered absolute DLL paths. Preserve each raw result. When the named API defines a valid last-error observation, immediately retrieve `ctypes.get_last_error()` on the same thread before another foreign call; otherwise the error field is null. Do not substitute `ctypes.GetLastError()`, which reads the OS slot rather than the saved copy. Do not use automatic HRESULT translation or an error hook that discards the raw result. [Official ctypes documentation](https://docs.python.org/3.12/library/ctypes.html#loading-shared-libraries).

## Still required

This is a proposed wrapper policy inferred from the documented mechanism. T1/T2 must still fix every named function signature, pointer/buffer lifetime, return sentinel, saved-error integer-to-native-DWORD representation and validity predicate; the complete runtime dependency identities, exact loader policy and controlled error/ABI oracles remain unregistered. A saved error is not evidence that an API failed, and null/unobserved must not become a guessed zero. Import initialization and DLL loading remain future runtime work behind the new containment/registration boundary. Parent-side limitations remain explicit. All authorities stay false; no current-runtime, ABI, source or historical authentication follows.
