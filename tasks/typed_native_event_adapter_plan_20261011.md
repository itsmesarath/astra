# Typed native/event adapter execution plan — 2026-10-11

## Current state and authority

**PROPOSED EXECUTION PLAN — awaiting direct human plan/task-list approval. No implementation is released.** The human approved the [exact contract](../docs/6E_TYPED_NATIVE_EVENT_ADAPTER_CONTRACT_20261011.md) at the direct turn recorded **15:24:39 UTC**, then explicitly chose **new dated files in tasks/** while leaving the payload plan intact. Root checked actual UTC for that placement request at **2026-10-11T18:09:49Z**. The plan target is this file; its sole checklist target is [typed_native_event_adapter_todo_20261011.md](typed_native_event_adapter_todo_20261011.md), not the occupied defaults. [Payload plan](plan.md) and [payload tasks](todo.md) are preserved byte-for-byte, including superseded historical closure items; no external tracker is used.

This request releases **offline planning documentation only**. The current [documentation window](../docs/6E_TYPED_NATIVE_EVENT_ADAPTER_WINDOW_20261011.md) still ends **2026-10-11T18:41:15Z (19:41:15 Lisbon)**. It is not an implementation deadline or a renewed four-hour window. Stop for human plan review after static acceptance. Even plan approval alone does not release source/tests/runtime/native/history: future implementation requires an explicit scope/window and its own registered stop budget. No code, tests, imports, examples, simulations or model processes are launched now.

The approved specification is held at raw SHA256 `accd50090637597f5cd327a56c34f41f1671e5b41e55ae935e306fc6c0a61822` (57,138 bytes). Its PROPOSED/pre-planning language is the earlier chronology; this plan records later specification approval without editing it. Ambiguity between its prose and its nine held numerical rule references is a finding to raise, never permission to choose different behavior.

## One bounded capability and architecture decisions

Build, only after a separate implementation release, a pure in-memory **invented typed event/37-feature publication reconstruction and complete submitted-result verification**. One `AdapterFixture(context, payload_bundle)` wraps the accepted complete target/foreign record sequence. Six public APIs and all exact frozen/slotted types come from the contract. Original ordering, raw integer representations, explicit absent/present `ts_out`, mapped IDs, source-grounded daily initialization and full state are retained.

- Dependency direction: stdlib + unchanged public cursor/payload APIs -> local source-grounded numerical reconstruction -> complete canonical assessment -> independent submitted verification. No dependency on the old instrument-1 feature witness, funded/account drivers or native/historical producers.
- The nine numerical helpers are **source-text rule references only**; their transitive native/historical imports prohibit using them as runtime shortcuts. No monkeypatch/coercion, replacement genesis, starting checkpoint or native object constructor is added. Existing binding/cursor modules stay unchanged; no private dependency API is used.
- Complete metadata preflight precedes **both** original and submitted numerical traversal. Public `cursor.verify` is safe at that metadata gate. Public `binding.assess`, `binding.bundle_sha256`, `binding.verify` are invoked only afterwards and retain their full verification; metadata preflight is not a substitute.
- Full ordinary event/T provenance is distinct from the protected execution-capture suffix. Publication is feature-only at the first eligible completed quote; no policy eligibility filter, orders, account, outcomes, holds or cooldowns are added.
- Canonical projection uses literal field bodies, not reflection/production serializers in expected oracles. Preserve original float operation order, signed zero and single-history-quote exact-int-zero travel. Hash consistency is not native/source/runtime authentication.
- All **34 adapter / 31 binding / 26 cursor** authority flags remain literal False. Preserve both old 65,536-byte caps, both binding 262,144-byte caps, outer fixture/result and state 1,048,576-byte caps, complete 2–128 positions and 1–32 publications. No salvage, partial output, cap override or historical thinning/splitting/relabeling.

These choices retain the existing dated `docs/6E_*` decision convention. This plan explains their execution implications; it is not a second specification or a new generic ADR scheme.

## Dependency graph and slice order

```text
Human plan approval + separate future implementation scope/window
  -> T1 preservation, independent oracle registration, intended RED
  -> T2 exact public protocol/context/type slice
  -> T3 complete original/submitted metadata gate
     [Checkpoint A: phase-order boundary]
  -> T4 target/foreign day/clock/book transitions
  -> T5 complete events, flow and protected capture
     [Checkpoint B: ordered transition/event behavior]
  -> T6 quote/OFI and first eight features
  -> T7 history/depth and next fifteen features
  -> T8 execution observer and final fourteen features
     [Checkpoint C: numerical feature semantics]
  -> T9 complete publications, finish and canonical replay
  -> T10 complete submitted verification and causal controls
  -> T11 intersected capacity boundaries
     [Checkpoint D: complete six-API contract]
  -> T12 independent stable-pair, focused/adjacent/lint/docs gates
  -> T13 frozen complete regression and terminal handoff
     [Checkpoint E: fully reconciled acceptance, then stop]
```

Each task has at most three acceptance criteria, explicit verification, dependencies and likely files in the [dated task list](typed_native_event_adapter_todo_20261011.md). Tasks exercise a narrow observable behavior with its independent tests, not all production code followed by all tests. Early protocol/helper/refusal slices may be GREEN without complete replay being accepted: `fixture_sha256`/`replay` positive return requires T9's full numerical/publication/finish assembly with **every inherited/new/state cap already enforced**. Canonical guards are installed as their bodies/state are introduced, not postponed to T11. Complete submitted verification remains T10; T11 comprehensively challenges the already-enforced capacity boundaries; full six-API contract acceptance is Checkpoint D. No placeholder feature rows, lenient serializer or partial assessment is returned to make a slice look green. A missing later capability remains explicitly incomplete.

**Build order is not runtime order.** After complete metadata gating and full raw binding checks, route target/foreign records. For a protected non-snapshot target, the original wrapper captures pre-update state **before parent validation/application**. The parent then performs day/quality/incomplete checks -> ClockAudit -> ordinary feature timers -> book application -> successful target ordinal -> event completion/quote/helper observation -> first-cursor publication, with reset/snapshot/exception branches exactly as specified. Foreign records never enter target processing. A capture followed by a parent refusal aborts the whole assessment; it is not partial successful evidence. Closing-only links never annotate earlier members with future artifacts.

## Ownership, concurrency and test-first evidence

Future implementation may write only:

- `src/ai_trader/research/six_e_typed_native_event_adapter.py`: one source author.
- `tests/test_six_e_typed_native_event_adapter.py`: a separate independent test author.

Root owns runtime launches, registration/evidence and documentation; a third reviewer is read-only. The test author independently projects full protocol/context/header/mapping/payload/cursor/adapter/state/audit/event/quote/publication/result bodies and numerical expected values from the approved contract and held source rules. Production serializers, returned protocol dictionaries, dataclass reflection and production replay are not expected-body oracles. Fixture construction may use exact dependency dataclasses/public calls, but their returned bodies/results are not copied into the expected oracle. Expected dependency protocol bodies/pins must also be independently literal.

Source author is held until root diagnoses an intended collected/executed missing-behavior RED. Every changed slice has corresponding intended RED -> smallest implementation -> same behavior GREEN evidence. Missing-module import/collection accidents, broken constructors and generic exception catches do not count. Record failed attempts without replacing them. Real uncaught `AssertionError` read sentinels must cover all sixteen original/submitted raw fields and every submitted deferred numeric/observed-boolean/generation family. A deliberate **new-file-only** eager-read mutant must be killed; restore the exact held source and rerun the same controls for GREEN. Register the mutant, selected cases, affected file hash and exact restoration in advance; never mutate old accepted code or tests.

Safe parallelism is separate-file source/test authoring after each slice's independent test contract, and read-only review of a stable pair. Source stages sharing reconstructed state are sequential. Both writers confirm **HOLD** for every root launch, including RED/slice/focused/adjacent/lint/format checks. No edit/addition/format occurs while a matching run is active. All Python sources/tests are frozen for the complete suite; reviewers never silently fix files. Root reads complete final files and corrections itself.

## Acceptance-group coverage

All fifteen specification groups are still **UNEXECUTED** for this adapter. This mapping is a plan, not evidence of test coverage or a new test count.

| Contract group | Planned task coverage |
| --- | --- |
| 1 exact protocol/context/types/flags | T2, T3, T10 |
| 2 metadata phasing and real sentinels/mutant | T3, T10 |
| 3 complete literal bodies/mappings/IDs | T1, T2, T4, T9, T10 |
| 4 initialization/reset/strict book/prestate | T4, T5 |
| 5 foreign poison/provenance/no target effect | T4, T5, T10 |
| 6 day/quality/closed clear/clock | T4, T9 |
| 7 non-T incompleteness/T flow/terminal refusal | T5, T9 |
| 8 full event versus protected capture | T5, T8 |
| 9 quote grid/gap/OFI/inactivity equality | T6, T7, T9 |
| 10 exact 8+15+14 features/execution | T6, T7, T8 |
| 11 warmup/first equal-time cursor/cadence/end | T6, T9 |
| 12 complete state/membership/tampering/finish | T9, T10 |
| 13 suffix/member versus consumed foreign | T9, T10 |
| 14 every inner/outer/state cap | T11 |
| 15 independent review/full frozen acceptance | T1, T12, T13 |

## Prospective runtime registration — UNEXECUTED

These templates are **not commands authorized in the current window**. After future release, root substitutes fresh registered names/selected test identities, confirms output paths are absent and retains every failed report. Never overwrite an occupied report or reuse old completed reports as a new run. Existing Python 3.12/pytest/Ruff environment is used; no build/install/dependency/environment change is needed.

```powershell
.venv/Scripts/python.exe -B -m pytest -q tests/test_six_e_typed_native_event_adapter.py -k '<registered-slice-selection>' --junitxml=logs/typed_native_event_slice_<fresh-registration>.xml
.venv/Scripts/python.exe -B -m pytest -q tests/test_six_e_typed_native_event_adapter.py --junitxml=logs/typed_native_event_focused_<fresh-registration>.xml
.venv/Scripts/python.exe -B -m pytest -q tests/test_six_e_typed_native_event_adapter.py tests/test_six_e_record_payload_binding.py tests/test_six_e_native_cursor_metadata.py tests/test_six_e_feature_publication_witness.py --junitxml=logs/typed_native_event_adjacent_<fresh-registration>.xml
.venv/Scripts/python.exe -B -m ruff check src tests
.venv/Scripts/python.exe -B -m ruff format --check src/ai_trader/research/six_e_typed_native_event_adapter.py tests/test_six_e_typed_native_event_adapter.py
.venv/Scripts/python.exe -B -m pytest -q --junitxml=logs/project_full_suite_typed_native_event_<fresh-registration>.xml
```

Call selected behavior verification **V-slice**, whole new-file verification **V-focused**, selected neighboring-file regression **V-adjacent**, and complete suite **V-full** in the task list. Root records exact collected case-sensitive identities before each launch, not merely the `-k` expression. The adjacent proposal includes all three full old files; their expected identities are derived from the retained accepted report, not guessed counts/classes. Any change to selection is registered before launch. No standalone guide example is required; no example is automatically authorized by this plan.

Registration includes scope/deadline/resources, stage/selection/expected pass-fail-skip outcome, source/test/approved-contract/dependency pins, baseline/whole ordinal manifest and raw container, exact command, unique report path, writer HOLD confirmations, launcher and actual child **command/executable/UTC creation/parent** identities, tool session, and bounded report read limits. PIDs alone, progress dots and process presence/absence are not acceptance. Root alone polls an active owned session; no duplicate suite or polling after verified completion. Normal checks have bounded timeouts/stop budgets; no uncontrolled background work.

T13 must reconcile every **10,872 old case-sensitive unique identity** from [the accepted payload report](../logs/project_full_suite_20261011_payload_binding_1.xml), plus exactly all independently accepted new focused identities. Do not guess a new count or allow replacement hidden by equal totals; retain intentional GZIP/gzip distinctions. Require declared totals, zero failures/errors, exact three old skip identities and **full XML reason representations**, tool exit zero, exact owned-process exit, raw report byte count/SHA and unchanged whole/old/new/source-test/package/approved-contract/raw-container pins. New focused cases have zero skips. The three old skips remain the optional Nautilus evaluation dependency and two unavailable Windows symlink privilege cases, with no dependency/security bypass.

Held baseline: whole416 map `41e1231c387ffa0e3f45112d83456743133dfa6504be6de6ed4c57d74286cfb5`, package `8965a6cd845d10c740e6dab7f5377e2f9e24c78b2a5da1e52968f17cc9590170`; [payload freeze container](../logs/payload_binding_full_freeze_20261011_1.json) raw SHA `cddb1d7f0576bd4547c732f46c7c70038dacfe6f35b02692a2153a086dd055b4`. Accepted report is 1,738,377 bytes, SHA `1ea007b40b5ec87ccf2a3058c7427a4fe9ab48be320f897990b3fad54de0eabb`, accepted14:16:22Z. These are retained completed evidence, not a request to rerun them now. A later implementation's baseline/freeze checks are new preservation evidence, not repeated acceptance of the old suite.

## Timing and stop gates

**No implementation schedule is established today.** All tasks remain pending until human plan approval and a separately authorized offline implementation window. Register that window's actual start S, hard end D, author edit-freeze F, latest complete-suite launch L and identity-matched owned-job stop checkpoint before dispatch. Current18:41:15Zdoes not release runtime work; even immediate plan approval cannot make a late launch permissible.

The last accepted full suite took **2,473.06 seconds** (about41minutes), not a guarantee for this larger component. A future registration reserves **at least72minutes** from full-suite launch to D, increased if measured focused/capacity workloads or review/reconciliation/contingency require more. L <= D−that reserve; F is earlier by enough time for final review/focused/adjacent/lint/freeze. If readiness cannot fit, retain incomplete work and stop instead of dropping cases/controls, weakening gates or launching late. At D−2minutes, stop only a still-running exact retained command/executable/creation/parent-matched owned job within the window and mark acceptance incomplete; unrelated collectors are never targeted. At D launch nothing, summarize verified/incomplete evidence, delete the follow-up and stop; no automatic next-day continuation.

## Risks and mitigations

| Risk | Planned mitigation |
| --- | --- |
| Imported convenience helper brings native/history dependencies | Stdlib + unchanged public cursor/binding only; source-text normative rules, static import review. |
| Early numerical access defeats fail-closed ordering | T3/T10 real all-field/family read sentinels; final metadata fault first, valid numeric truth later; uncaught eager-read mutant. |
| Numerical agreement copied from implementation | Independent complete literal bodies and hand-derived values, source arithmetic order, no serializers/reflection/results reused as expectations. |
| Snapshot R/exception/reset/foreign paths are conflated | Separate day/clock/transition controls; original ClockQuality aliases and closing-only links; foreign never drives target timers. |
| Full T event silently becomes protected execution evidence | Separate exact memberships, crossing-warmup controls, original fill_without_trade and stale-suffix semantics. |
| Equal-time future updates or member metadata enter earlier identity | First-cursor cadence; valid suffix/member versus consumed-foreign paired controls with qualified numerical/provenance assertions. |
| Toy caps masquerade as historical capacity | All old/outer/state intersections and legal measured envelopes; no universal maximum or truncation claim. |
| Race or equal test counts conceal changed evidence | Every-launch writer HOLD, full source freeze, every old/new ordinal identity and exact skip representation reconciliation. |
| Deadline causes false completion | Separate future scope/time registration, conservative reserve, incomplete handoff rather than late launch or reduced quality. |

## Definition of done and human decisions

Planning done now means ordered small tasks with dependencies/acceptance/verification, complete15group mapping, static independent review, accurate local links, preserved payload files/approved contract and honest scope/status. Runtime criteria above are **prospective**, not checked off merely because the plan is saved. The installed planning/documentation skills guide these artifacts; generic commit/deploy/health checks do not broaden permission. Graphify scans are not needed or released.

Later implementation done requires exact six-API behavior, meaningful RED/GREEN/mutation evidence, complete independent/root pair review, all new/adjacent/lint/format gates, frozen complete reconciliation and accurate current guide/handoff. No native ABI/bytes/header/EOF/source/runtime authentication, historical row parity/calendar/full capacity, multi-session continuity, profitable strategy, broker economics or model improvement follows. Those require separate reviewed contracts/implementation and fresh prospective whole-cohort registration where relevant.

**Decisions still required:** direct approval/edits of this execution plan and task list; then a separate explicit implementation scope/window if desired. Existing contract and file placement approvals are complete and must not be asked again. Until those later gates, no source/test writers or runtime launch is released.

Preserve all416 accepted Python files, old source/target/input/result/control pins, UNKNOWN liabilities and dirty/untracked work. No staging/commits/cleanup, raw/historical/reserved inputs or old packets/controls/experiments, native decoder calls, Qwen/models/training, market-data network/captures/downloads, credentials/broker APIs, actual paper/live orders, dependencies or Windows/security changes/bypasses. BTC/cloud collectors untouched. No late fills, UNKNOWN cancellation/reconciliation, reseed/daily reset, successful-subset scoring, old-fill filtering, quote-manufactured funding recovery or future terminal-plan stitching. Disabled AppSecurity is not inspected or treated as a proven fix.
