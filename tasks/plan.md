# Payload-binding implementation plan

## Status and authority

**Current: implementation and complete regression acceptance finished at 2026-10-11T14:16:22Z.**
All seven APIs, 1,474 new cases and the complete 10,869-pass/three-expected-skip suite are accepted.
No owned runtime remains pending; no further increment is released. The approved procedures below
are retained chronology, not instructions to restart them. Only deadline closure remains open.
**Later chronology:** the direct14:41:15UTCrenewal superseded the original15:57:08stop with an18:41:15UTCdocumentation-only typed adapter contract window. This approved payload plan remains completed history; no new implementation plan is released. See [the new window](../docs/6E_TYPED_NATIVE_EVENT_ADAPTER_WINDOW_20261011.md).
The later documentation-only status request is recorded in [the project status](../PROJECT_STATUS.md);
its future gates are proposals, not a replacement execution plan.

The human explicitly approved `docs/6E_PAYLOAD_BINDING_CONTRACT_20261011.md` and requested implementation using the installed skills for four hours. Actual UTC was checked at **2026-10-11T11:57:08Z**. This new window ends at **2026-10-11T15:57:08Z (16:57:08 Lisbon)** and replaces the preceding contract-window deadline; it is never extended automatically.

**Execution plan and task list HUMAN APPROVED.** At 2026-10-11T13:08:06Z root checked UTC after the direct approval: "i approve the payload-binding execution plan and task list. start implementing it using the new skills and continue until the current deadline". The original 15:57:08Z hard end is unchanged. Independent test author is released first; source author is read-only until root diagnoses intended RED. A static reviewer or heartbeat cannot supply new authority.

The approved contract remains unchanged at its held raw SHA256 `9acb65a5e8b2aa2ef2670a92fffa47d7b81a1380bf2ef73e1173820811f4c6f1`. Its original contract-only/proposed wording records that earlier window; this plan and the new development-window handoff record the later human approval. A discovered behavioral ambiguity must be raised, not silently resolved or used to lower the contract.

## One bounded capability

Implement only the pure, constructed in-memory binding of all sixteen target/foreign MBO JSON fields to the unchanged cursor metadata interface. Preserve exact raw integers, explicit absent/present `ts_out`, complete positional coverage, metadata-before-payload access, complete verification, contextual causal prefixes, both old 65,536-byte caps, the new 262,144-byte caps and all 31 top-level/26 nested false authorities.

No native ABI, decoding, original bytes/header/EOF, book/event/feature acceptance, authenticated source/runtime, historical validation, account or trading claim follows. Do not coerce inputs into the old instrument-1 feature witness.

## Dependency and ownership

Approved contract + unchanged public cursor APIs -> independent test oracles/RED -> new protocol/context/body helpers -> complete bundle assessment -> submitted-state verification -> independent review -> focused/adjacent/lint gates -> frozen complete regression acceptance.

Only these two new Python paths may be written after human plan approval:

- `src/ai_trader/research/six_e_record_payload_binding.py`: one source author.
- `tests/test_six_e_record_payload_binding.py`: a separate test author.

Root owns the plan/task list, new guide/window documentation, run registration, process ownership and runtime launches. A third agent may independently read the complete stable new source/test files; it writes neither. Test expected bodies come from the approved contract and literal independent projections, not production serializers or dataclass reflection. No shared-file writers.

Both authors must hold their files fixed for **every** root runtime launch. All 414 old Python source/test files remain immutable, including dirty/untracked files. No staging or commits. The skills' generic commit steps do not override this project constraint. Graphify scanning/graph creation, native calls, dependencies, network or model activity are not required or released.

## Ordered slices and checkpoints

Detailed tasks and acceptance checklists live in `tasks/todo.md`; no external tracker is used.

1. **Preservation and independent RED.** After plan approval, register the unchanged 414-file/package/contract baseline without repeating an accepted suite. Independently author the new test file. Root records a collected and executed test failing for the intended absent behavior, not an accidental import/collection/harness failure. Source implementation remains held until that RED is diagnosed.
2. **Protocol, context and exact body helpers.** The source author adds the smallest contract-consistent slice. Root exercises the selected independent helper tests after both writers freeze. All-field preservation, both `ts_out` modes and exact expected-pin handling must pass before the next slice. Remaining unimplemented APIs are not represented as complete.
3. **Complete metadata preflight and assessment.** Register and observe genuine phase-order/raw-body RED evidence for this slice where applicable, then implement complete old cursor reconstruction, original bundle validation and contextual audits. Independent AssertionError sentinels must prove that malformed final metadata precedes all sixteen payload fields. Root runs only the selected tests for this changed slice.
4. **Submitted-result verification.** Before original or submitted payload-field access, validate submitted status/context/envelopes/all audits/all false flags and the entire nested old cursor assessment through unchanged `cursor.verify`. Complete rebuilt body bytes, actual hashes and exact types must reconcile. This checkpoint is mandatory and cannot be replaced by equal totals or generic ValueError tests.
5. **Stable pair acceptance and documentation.** Independent complete source/test review and root full-file read; resolve findings only in the new pair. Verify every new constructed case, the complete adjacent selection, whole `src/tests` Ruff and new-pair formatting. Document the seven APIs, limits, access phases and non-authorities. A guide example is optional and may run once only if explicitly registered and useful; tests already provide runtime behavior evidence.
6. **Final frozen complete regression.** Freeze every Python source/test file; register exact new case identities/count and process ownership, then launch one fresh complete suite. Require every old 9,398 case-sensitive identity plus exactly all independently accepted new identities, exact old skip identities/full XML reasons, zero failures/errors, tool exit zero, owned-process exit and unchanged source/test/package/contract/manifest-container pins. Only then call the increment fully accepted. Do not start a further increment after passing.

No completed unchanged check is repeated for reassurance. A changed slice or correction gets relevant new evidence; full acceptance always refers to the exact frozen pair that ran.

## Prospective command registration

The repository uses Python 3.12, pytest and Ruff through its existing `.venv`. No installation/build/dependency change is needed. Before each launch, require the new output path not to exist and register stable source/test pins, selected identities and ownership. If a path is already occupied, stop and choose a fresh registered name; never overwrite it.

Commands below are **not executed while plan approval is pending**. Root alone later chooses exact `::test_name`/`-k` selections for the genuinely changed slice and registers that choice before launch.

```powershell
.venv/Scripts/python.exe -B -m pytest -q tests/test_six_e_record_payload_binding.py --junitxml=logs/payload_binding_focused_20261011_1.xml
.venv/Scripts/python.exe -B -m pytest -q tests/test_six_e_record_payload_binding.py tests/test_six_e_native_cursor_metadata.py tests/test_six_e_feature_publication_witness.py tests/test_six_e_metadata_cohort.py --junitxml=logs/payload_binding_adjacent_20261011_1.xml
.venv/Scripts/python.exe -B -m ruff check src tests
.venv/Scripts/python.exe -B -m ruff format --check src/ai_trader/research/six_e_record_payload_binding.py tests/test_six_e_record_payload_binding.py
.venv/Scripts/python.exe -B -m pytest -q --junitxml=logs/project_full_suite_20261011_payload_binding_1.xml
```

RED/slice/corrected reports require their own fresh registered paths. Focused and adjacent JUnit comparisons must enumerate all complete case-sensitive identities; no new test count is guessed. Intentional GZIP/gzip parameter identities stay distinct. Final source/test/package reconciliation occurs only after the matching full suite exits; progress dots and process presence/absence prove nothing by themselves.

## Time budget and stop behavior

Previous accepted complete regression took **2,120.67 seconds**, about 35 minutes. That is a planning observation, not a guarantee. Reserve **at least 72 minutes** from the latest full-suite launch to the hard end for runtime, terminal reconciliation and contingencies.

- Stop new Python edits by **14:35 UTC**, earlier if review/focused work needs more time.
- Latest complete-suite launch is **14:45 UTC**, and only if readiness plus measured runtime leaves a credible acceptance budget. If readiness misses this gate, retain the unaccepted increment; do not compress review, remove tests or launch late.
- At **15:55 UTC**, if an owned job still runs, use its retained exact command/executable/creation/parent identity to stop only that owned job before the hard end and mark acceptance incomplete. Never target a PID alone or touch BTC/cloud collectors or unrelated processes.
- At **15:57:08 UTC**, launch nothing, report verified work and gaps, delete the heartbeat and stop. Never archive this chat, shut down the computer or carry work into another day.

A direct human stop/pause cancels this window and deletes the follow-up. Silence or a heartbeat is not further authority.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Eager traversal defeats refusal ordering | Real uncaught AssertionError sentinels across all sixteen fields; complete submitted-metadata checkpoint before either body's traversal. |
| Hash tests repeat production mistakes | Literal independent protocol/context/record/bundle/old-cursor/audit/result bodies and complete reconstruction. |
| A new cap hides an old refusal | Require both old public caps and the shared new cap; separate boundary guard tests from measured valid public-envelope capacity. |
| Context/member/suffix identity leakage | Explicit context wrapper including the header; paired fully valid suffix/member and changed-foreign controls. |
| Concurrent edits invalidate test evidence | Both writers hold during every launch; all Python frozen throughout complete regression; final pin reconciliation. |
| Equal counts conceal replaced tests | Compare every old identity and exactly the accepted new identities, preserving case and complete skip representations. |
| Deadline pressure lowers quality | Fixed edit/launch/stop gates; report incomplete instead of implying acceptance. |

## Standing definition of done and remaining gates

Each slice must meet its specific acceptance criteria and the installed Definition of Done: real runtime evidence, deterministic refusals, no regression, scoped changes, stable interfaces, input-boundary review and accurate guide/handoff. No commit, deployment, account/storage logging or trading instrumentation is introduced into this pure component.

Preserve all old sources/targets/inputs/results/control pins and UNKNOWN liabilities. No raw/historical/reserved inputs, old packets, historical controls/experiments, native decoders, training/Qwen/model calls, market-data network/download/capture, credentials/broker API, paper/live orders, dependency/security changes/bypasses, force pushes, reseeding/daily resets, late fills, UNKNOWN cancellation/reconciliation, successful-subset scoring, old-fill filtering or terminal-plan stitching. Disabled App Security is neither inspected nor treated as a proven fix.

Approval gates were closed by direct human messages. The approved payload contract itself is not being re-opened or redesigned. Implementation and independent/runtime acceptance are complete. Only the unchanged deadline closure remains; no code, tests or further increment is released by the status/roadmap update.
