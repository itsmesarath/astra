# Protected incomplete-tail row derivation — 2026-10-16 (post-handover)

Status: **SOURCE-LINKED DERIVATION / INDEPENDENT SYNTHETIC WIDTHS / NOT A CERTIFICATE, NOT A REGISTERED COMPONENT, NOT EXECUTED PROJECT CODE**. This was written after the [Claude handover](CLAUDE_HANDOVER_20261016.md). It advances whole-R1 (board T4/C1) by sizing the protected safety tail rows that the [Host protected-envelope recipe](6E_LOCAL_MEMBER_INTAKE_HOST_PROTECTED_ENVELOPE_RECIPE_20261016.md) §5–9 and [Host candidate](6E_LOCAL_MEMBER_INTAKE_HOST_CERTIFICATE_CANDIDATE_20261016.md) §7.2 name but do not size. The only rows already sized are the CloseHandle trace, ParentClose and Lifecycle group, in the accepted [late-close component](../scripts/local_member_intake_late_close_component_20261015_1.json). No producer, test, oracle, resource, contract, P/D/R revision or accepted file was changed. Nothing was imported, run or launched in the project environment. All authority flags stay literal False, and UNKNOWN liabilities stay held.

## 1. Basis

- Held Host draft: `scripts/local_member_intake_bootstrap_host_20261015_1.py`, 96,913 bytes, SHA256 `518e75be61be5fdc5535d9619b790822a5bed8fa7f4607f1b5bfe936f2e69b7f` (read-only hash on 2026-10-16; this equals the reviewed static basis).
- P3 protocol: `scripts/local_member_intake_bootstrap_protocol_20261015_3.json`, 171,369 bytes, SHA256 `2252ebefe2d38b14f5c915b3a1b9fbb2c8bc960a02477372bb1dd0ea7114c31f`.
- Schemas used: `ApiTrace`, `ApiArgument`, `Pointer`, `ApiReturn`, `BufferObservation`, `Lifecycle`, `LifecycleToken`, `ParentClose`, `Terminal`, `Outcome`, `FailureCode`, and the `ApiContracts` rows at protocol file lines 249 (DeleteProcThreadAttributeList), 252 (WaitForSingleObject), 253 (GetProcessTimes), 254 (GetExitCodeProcess) and 258 (TerminateJobObject).
- Host sites: Native.call 387–453; process_times 484–492; `_event` 814–818; `_choose` 820–823; `_close` 834–844; `_unattempted_closes` 846–850; held `_cleanup` 1322–1382 (wait 1329–1330, termination 1333–1336, wait loop 1337–1341, exit/times 1346–1347, attribute delete 1368–1370, close loop 1371–1377); `_receipt` 1390–1398; run catch/finally 1444–1452.

## 2. Method and independence

Every width below is the canonical ASCII JSON length of a **concrete maximizing value**: sorted keys, `,`/`:` separators, `ensure_ascii`. The values are built in the Host M sizing view, with raw hex interiors set to `""` as in recipe §3. The witnesses were generated with Python's standard `json` module in a separate scratch workspace. That generator does not use the project calculator, the producers, the reflection of any serializer or any native output.

Method check: the same generator reproduces the accepted late-close values exactly. ApiReturn is 77/73, CloseHandle ApiTrace 436/432, ParentClose 239/241 and Lifecycle 106 (success/failure). The complete witness bodies and widths are in [protected_tail_row_witnesses_1.json](../logs/local_member_intake_r1_tail_20261016_1/protected_tail_row_witnesses_1.json).

The witnesses are synthetic sizing inputs. They are not observations and do not describe jointly reachable histories. They fix the phase to the longest LifecycleToken (`termination_requested`, 21 characters), which is the same conservative superset the late-close component used. Ordinals are 0..4095, ParentClose ordinal 0..15, and handles, clocks and pointer addresses use the full U64 domain.

## 3. Complete per-row templates and maxima

The ApiTrace fields are the full 10-key roster. Every row has `saved_error_seed` null: the P3 seed rule requires a seed only for GetFileType.

| Row (P3 line) | Arguments | Return alternatives | Output buffers (M view) | Max width |
|---|---|---|---|---|
| WaitForSingleObject (252), signal | hHandle handle64 1..U64; dwMilliseconds u32 = 0 | dword32 raw_u64 0, error null | none | 474 |
| Wait, timeout | same | raw_u64 258, error null | none | 476 |
| Wait, other | same | raw_u64 1..257 or 259..4294967294, error null | none | 483 |
| Wait, failure | same | raw_u64 4294967295, error U32 | none | 489 |
| TerminateJobObject (258) | hJob handle64; uExitCode u32 = 3758096455 | bool32 nonzero I32 / null, or 0 / U32 | none | 506 / 502 |
| GetExitCodeProcess (254) | hProcess; lpExitCode pointer (addr U64, before "", 4, dword_out) | bool32 success / failure | one post: documented_valid/4/4/u32, or storage_only/null/null/none | 803 / 802 |
| GetProcessTimes (253), P3 form | hProcess + four filetime_out pointers of 8 bytes | bool32 success / failure | four posts: success documented_valid/**null**/8/filetime_u64; failure storage_only/null/null/none | 1,847 / 1,807 |
| GetProcessTimes, held 8/8 form (not P3) | same | success | four posts with returned_bytes 8 | 1,835 |
| DeleteProcThreadAttributeList (249) | lpAttributeList pointer (before "", A, opaque_attribute_list) | void, all null | one post storage_only/null/null/none, capacity A | 793 (A=65,536); 785 (A=1) |
| CloseHandle trace (accepted) | hObject | bool32 | none | 436 / 432 |
| ParentClose closed / close_failed / not_attempted | — | close_return copy or null | — | 239 / 241 / 174 |
| Lifecycle termination_requested / process_signalled / handle_closed (one related ordinal) | — | — | — | 114 / 110 / 106 |
| Lifecycle failure_selected / finished (related `[]`, per 820–823 and 1391) | — | — | — | 105 / 97 |

The 1,847 − 1,835 = 12-byte gap between the two Times forms independently confirms the recipe's +12 for the open P3 null/8 versus held 8/8 conflict. The P3 form is the normative one for the tail.

## 4. Branch table for one fixed post-action state

Each head's rows are appended in order; a comma is charged for every row, which is the all-nonfirst case. Terminal scalar growth is measured against a null/false prefix value. That gives an upper bound, not an actual delta.

| Head (recipe §6) | Rows | Bodies + commas | Terminal scalar growth ≤ |
|---|---|---|---|
| B0 no eligible process | 0 | 0 | 0 |
| B1 W1=0, Q0 (exit failed) | W1, signalled, Exit | 1,389 | −3 (wait_result null→0) |
| B1 W1=0, Q1 | + Exit ok, Times failed | 3,198 | −3 |
| B1 W1=0, Q2 | + Exit ok, Times ok | 3,238 | 51 (exit U32 +6, three U64 +16 each) |
| B2 W1=258, T, W2=0, Q0 / Q1 / Q2 | W1, T, termination_requested, W2, signalled + Q | 2,488 / 4,297 / 4,337 | 69 / 69 / 123 (termination_requested −1, termination_return +73, wait −3, Q2 +54) |
| B3 W1=258, T, W2 nonsignal | W1, T, termination_requested, W2 | 1,589 | 72 |
| B4 W1 other/failure | W1 | 490 | 0 |
| B5 no job, W1=258 | W1 | 477 | 0 |

The common suffix follows:

- Attribute delete, if the list is initialized and the delete has not been entered: at most 794.
- Each completed close group, coupled success/failure as in the accepted component: at most 781 + 3 commas = 784. Up to 9 roles.
- Each genuinely unentered owned role: 175 instead. c + u ≤ 9 roles, and the public cap is p + c + u ≤ 16.
- One new failure_selected, if not already recorded: 106. Terminal stage and code from null add ≤ 19 + 26, and outcome adds ≤ +1.
- finished: 98. cleanup_complete null→false: +1.

**Immediate appended M growth upper bound (process + job + attributes, 9 completed closes, new failure_selected): 4,460 + 794 + 7,056 + 106 + 46 + 98 + 1 = 12,561 ASCII bytes.**

The count vector matches the recipe: at most 15 native rows (2 waits, 1 termination, exit, times, delete, 9 closes), at most 13 lifecycle rows and at most 9 ParentClose rows. The raw delta is `B = 8e + 64t + 2Aa ≤ 72 + 2A`, with D/H/R = 0. Each appended row is a distinct physical occurrence, and the termination ApiReturn is charged twice (trace and Terminal), matching the CloseHandle return copy.

This bound covers immediate tail rows only. It is not `U_M`, not `U_full` and not a fit proof. The recipe requires evaluating each **complete future Host record** (prefix + N + tail) against D/B/H/R/M, the 47,185,938 combined limit and the 67,108,864 full-record limit, plus the count limits. Before such a record exists, this table bounds how much the tail can add. It does not prove that any particular prefix leaves room.

## 5. Source-linked gaps between the held `_cleanup` and the protected tail

These are source-text observations, not executed anomalies. They do not change the held drafts.

1. 1330 and 1340: `_require(wait in (0, 258))` raises on a Wait "other" or failure return. The tail must retain that row and stop at head B4 instead.
2. 1336: `_require(returned != 0)` aborts after a failed TerminateJobObject. The tail keeps the failure and still performs one W2.
3. 1337–1341: an unbounded wait loop with up to 20 ms waits. The tail uses exactly one 0 ms W2.
4. 1346: `require_call` raises when GetExitCodeProcess fails. The tail retains Q0 and skips Times.
5. 490: Times emits 8/8, against the P3 null/8 form (the existing open conflict; +12 bytes per Times success row).
6. 1369–1370: attribute delete has no entered/returned latch. `attributes_initialized` is cleared only after the wrapper returns, so a bookkeeping failure inside Native.call (444–452) leaves the list looking undeleted to a later path.
7. 843 inside the 1371 loop: a failed close raises and abandons every later role. The tail must continue the remaining eligible roles.
8. **New finding — first-cause loss, 820–823 and 1444–1452.** A primary BootstrapFailure first runs `_choose("failed_control", reason)`, which records the stage/code and appends failure_selected. If `_cleanup` then raises, 1450 calls `_choose("incomplete", reason2)` again. That second call overwrites `failure_code` with the cleanup reason, sets `failure_stage` to `lifecycle[-1].event` (which is the earlier `failure_selected` token or a later cleanup event, not the original stage), and appends a second failure_selected. Lifecycle events carry no code, so the original failure code then survives nowhere in the Host record. This contradicts recipe §8 item 1 (an immutable first cause, with no duplicate failure_selected). Only `BootstrapFailure` is caught at 1444 and 1449. Any other exception type escapes without `_unattempted_closes` or a receipt; this is consistent with the existing "no universal recovery" boundary.

Items 1–7 restate gaps already implied by the recipe and candidates, now tied to exact lines. Item 8 is not stated in the candidates read for this derivation. It should go into the correcting-source requirements before any R3 producer edit.

## 6. What this does and does not close

It closes, as a derivation input:

- Complete per-row templates and independent maxima for all five unsized protected-tail native families and their events.
- The unattempted ParentClose, with a branch-coupled bound on the tail's immediate growth.
- An exact source-line gap list.

It does not close:

- The whole-R1 certificate (C1).
- The complete future-record evaluation.
- Ordinary-success continuations.
- Worker, Marker, Payload or RootExternal tails.
- Registration as a component packet in the late-close-v1 format.
- Calculator evaluation, independent review, sensitivity, the R2 governor, producer correction, G4/filesystem, regression or profile.

Next steps in dependency order:

1. Independent static review of this derivation and its witness JSON. A reviewer may regenerate the witnesses from §2–3 without using the project calculator.
2. With a bounded window, register a component packet that encodes these templates in the six-kind grammar, with independent literals equal to §3. Its pure data checks would run under the existing workflow.
3. Derive the same tail for the Worker (owned stdin/private pipe/allocation only) and the RootExternal observer.
4. Compose complete future-record branch evaluations once the corrected classifier/occurrence data exists.

## 7. Independent static review and corrections (appended; sections 1–6 above are unchanged from the original 49ee71c4… text)

A separate reviewer re-derived every width from P3 and the Host source text before reading this document, without the project calculator. It calibrated on the late-close maxima. All §3 rows, all §4 heads and the 12,561 arithmetic matched. All §1/§5 line citations and claims 1–8 were confirmed true of the source text. There were **no Required findings**. The witness JSON was not re-checked by the reviewer: it was not staged to them. Advisory corrections, adopted here:

- **A1 (bound raised).** P3 line 254 fixes the GetExitCodeProcess success `valid_prefix_bytes` = 4 but does not fix `returned_bytes`. The conservative maximum takes `returned_bytes` null: an Exit success row of **806**, not 803. Q1/Q2 heads rise by 3, so B2-Q2 is 4,340 + 123. The immediate tail upper bound becomes **12,564** ASCII bytes. The held source emits 4/4 (803), and which form is normative stays an open selector, like Times.
- **A2 (item 8 scope).** First-cause loss and a duplicate failure_selected occur whenever *any* earlier coded `_choose` precedes a `_cleanup` BootstrapFailure at 1450. That covers 1008, 1017, 1232–1245, 1270, 1277, 1297, 1415, 1425, 1430, and also 1377 (close_refusal `_choose` inside `_cleanup`). It is not limited to the 1445 catch.
- **A3 (item 8 last sentence).** For a non-BootstrapFailure primary exception, `finally` still runs `_cleanup`. If that cleanup raises BootstrapFailure, 1450–1452 including `_unattempted_closes` still run. What is lost is the receipt, because the original exception propagates past `return self._receipt()`.
- **A4 (item 3).** The loop at 1337–1342 has an unbounded iteration count but is time-bounded: `_remaining(end)` caps it at about 3 s and raises `work_deadline`. The break is at 1342.
- **A5 (item 6).** Bookkeeping that can fail after target return spans 427–452 (classification/error 427–443 plus 444–452), not only 444–452.
