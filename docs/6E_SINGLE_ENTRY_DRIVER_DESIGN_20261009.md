# One constructed entry from contiguous native quotes

This prospectively reviewed single-entry driver is implemented and independently reviewed. All 161 constructed driver cases, root's 1,385 adjacent cases, Ruff and formatting pass. Complete suite 4 is fully verified: 6,491 passed, three expected skips, zero failures/errors and unchanged source/test pins. It is an invented in-memory entry-protocol test tool, not paper trading, strategy validation or the complete funded-path adapter.

## Narrow inputs and independently retained pins

The separate module is `ai_trader.research.six_e_single_entry_driver`. It may use the standard library and the held native-prefix, declared-admission, budget and paired-assessment modules. Existing sources and results remain unchanged. There is no CLI, file access, clock, model, policy, broker, persistent account or resume hook.

Limits are `MAX_DRIVER_QUOTES = 128`, exactly one publication, at most three generated accounting records and `MAX_RESULT_BYTES = 64 * 1024`. Larger complete fixtures refuse; no truncation or substituted expectation. The narrower quote cap bounds the held native helper's quadratic repeated-prefix reconstruction without bypassing its checks.

Inputs are one exact complete `NativeFixture`, one exact fresh `DeclaredAdmissionGenesis` and one frozen slotted `SingleEntryDeclaration(declaration_id, publication_id, admission_id, side)`. The declaration/session/scenario have exact ASCII, nonempty `synthetic-` labels; other IDs use the held native identifier syntax. Side is exactly `long` or `short`. Use only `6EM5`, `6EU5`, `6EZ5`, `6EH6`. Genesis initialization equals fixture start. There is no preceding-state, existing history or replacement cash input.

Both builder and verifier require the original fixture, genesis and declaration pins. Pin syntax, exact top-level types, all required fields, labels, scalar metadata, immutable tuple caps and declaration/publication identity are checked before quote prices. The sole publication is prospectively selected, must be the original first row at its receive timestamp and obeys the held strict `publication_time + 18 seconds < fixture.end_ns` guard. Derive bounded readiness/deadline and require the entire inclusive execution interval inside the fixture's half-open interval.

`declaration_sha256(declaration, *, fixture_sha256, genesis_sha256)` hashes the exact version, constructed nontrading entry scope (`STATUS`), fixed protocol/limits, both original input pins and complete declaration, using canonical ASCII UTF-8 JSON. This prospective helper does not authenticate a declaration. Replacing an entire coherent invented context and all its expectations is not detectable.

The pure APIs are:

```python
build_single_entry_plan(
    fixture, genesis, declaration, *, expected_fixture_sha256,
    expected_genesis_sha256, expected_declaration_sha256,
) -> SingleEntryPlan

verify_single_entry_plan(
    fixture, genesis, declaration, *, expected_fixture_sha256,
    expected_genesis_sha256, expected_declaration_sha256,
    expected_plan_sha256,
) -> SingleEntryPlan
```

Verification rebuilds the entire plan from the original retained context and compares the complete canonical result pin. It does not consume a submitted result object or adopt a new expected pin.

The verifier validates the exact lowercase expected plan-pin syntax before deep quote access, just like its input-pin preflight. A malformed output expectation is not tested only after generating constructed outcomes.

## Fixed source-linked accounting cadence

Consume every quote contiguously with the held retained-prefix APIs. Immediately after the sole publication's first native row, regenerate its OPEN publication witness. Before an equal-time suffix, append exactly one constructed `ClockAdvanced` and then `AdmissionRequested`, both at that publication time, using the held reducer and original genesis. Link each record to the source-bound prefix/publication witness. IDs for generated records/receipt are fixed protocol constants, separate from the prospectively retained admission identity.

This is a newly declared cadence for an isolated constructed test, not a repair to the earlier assessment's stale-accounting behavior. A native observation does not authenticate fresh cash or real account completeness. The preceding state starts from the single original seed; no daily/session reset, reseeding, denial filtering or hidden prior liability is supported.

Retain the complete held budget decision and its original disposition. Denial or missing margin produces no pending admission, fee or commitment, but keeps the complete generated request record. The disposition recorded at publication is immutable; it is never replaced with a later execution result.

The returned budget decision is exactly the `AdmissionRequested` transition's decision: its snapshot is after the publication clock (sequence one) and before the request, not the resulting sequence-two state with a pending liability. Independently reconstruct that preceding snapshot/head; do not reassess the already-pending state to overwrite the original decision.

## Original entry timing and later outcome

If declared budget is available, preserve the original 100 ms readiness and inclusive one-second eligible interval. The first consumed row with `ready_at_ns <= received_at_ns <= deadline_ns` is the only candidate. If its spread is not exactly 50,000 nanounits, append one `EntryUnfilled(reason="simulator_refusal")` at that row and permanently refuse the entry; never search a later equal-time narrow row. Otherwise append one constructed `EntryReceipt` at ask for long or bid for short, for one full contract. Source-link that receipt to the exact consumed candidate prefix. Charge the declared entry fee once and preserve the held margin/exit-fee commitments.

One full contract at supplied bid/ask is an explicit top-of-book assumption. The fixture has no available size, depth, queue position, venue fill, broker receipt or CFD economics evidence. Crossing a supplied quote is not proof of executable quantity or actual fill.

If no eligible row exists, regenerate `close_through` at the original deadline before consuming a later row. Its prices cannot influence the timeout. At complete pinned EOF, regenerate the same supplied deadline closure. Only then append one constructed `EntryUnfilled(reason="timeout")` at the derived deadline with that boundary link. This constructed timeout is not elapsed wall time, broker cancellation or actual fill absence.

Continue auditing every supplied native quote after the outcome, but create no further account clock/event, candidate, hold, exit, cooldown or mark-to-market action. An entry receipt leaves OPEN inventory and null complete equity/return at EOF, even with zero monetary commitments. It is not a profitable round trip or full execution terminal. Never subtract the old extra round-trip tick as another monetary debit.

## Complete bounded result and local verification

The frozen slotted types are `QuoteAudit(cursor, received_at_ns, consumed_count, consumed_content_sha256)` and `AccountingLink(record_index, event_id, record_sha256, native_prefix, kind, publication, boundary)`. Links are one-for-one with generated records; publication links hold the original OPEN witness, candidate links identify the exact consumed row, and timeout links hold the regenerated CLOSED boundary. Only the relevant witness is non-null. The record hash uses the held record-head protocol, not a new receipt authority.

For every link, its native prefix's last cursor, last receive time, consumed count and digest must exactly match the corresponding complete quote-audit row. A candidate link also matches the outcome cursor/time and that exact source quote; publication links match the original first-cursor witness. Timeout's record time is the original deadline, while its matching last quote-audit row can be earlier; its CLOSED boundary and prefix must match exactly. Each link's record index/ID/resulting head matches that exact record and the accounting prefix reconstructed immediately after it. Never infer these equalities from final totals alone.

`SingleEntryPlan` includes version/status, the three original pins and declaration, publication, complete budget decision, original first disposition, separate later outcome/cursor/time, complete records/record links/quote audit, terminal native prefix, terminal accounting state, canonical plan SHA256 and immutable false authority flags. Its exact closed version, status, field order, outcome/link enums and generated IDs were prospectively locked and independently reviewed before implementation.

For prospective author/test agreement, root accepts the following independently reviewed exact closed protocol:

- `VERSION = "six_e_single_entry_driver_v1"`, `STATUS = "constructed_single_entry_plan_not_trading"`, `SingleEntryDriverError(ValueError)` and `END_BUFFER_NS = 18_000_000_000`.
- `MAX_DRIVER_PUBLICATIONS = 1`, `MAX_ACCOUNTING_RECORDS = 3`, plus the quote/result limits above. Generated constants are `CLOCK_EVENT_ID = "publication-clock"`, `REQUEST_EVENT_ID = "admission-request"`, `OUTCOME_EVENT_ID = "entry-outcome"` and `ENTRY_RECEIPT_ID = "constructed-entry-receipt"`.
- Ordered `SingleEntryPlan` fields: `version`, `status`, `fixture_sha256`, `genesis_sha256`, `declaration_sha256`, `declaration`, `publication`, `budget_decision`, `first_disposition`, `execution_outcome`, `outcome_cursor`, `outcome_at_ns`, `records`, `record_links`, `quote_audit`, `terminal_native_prefix`, `terminal_accounting_state`, `plan_sha256`, `authority_flags`.
- `first_disposition` is the exact held budget decision's disposition. Later `execution_outcome` is exactly `constructed_entry_receipt`, `simulator_spread_refusal`, `constructed_timeout` or `no_pending_entry`. A candidate outcome uses its exact cursor/time; timeout uses null cursor and original deadline; no pending entry has both null. Outcomes never replace the original disposition.
- Link `kind` is exactly `publication`, `candidate_quote` or `deadline_boundary`. Publication links use the original OPEN witness with null boundary; candidate links use the exact consumed-row prefix with both witness fields null; timeout links use a CLOSED boundary and matching prefix with null publication. Record indices are zero-based, complete and contiguous. `record_sha256` is that record's resulting held accounting head.
- `AUTHORITY_FLAGS` equals the paired assessment's exact immutable false tuple. No new true authority or authenticated linkage claim is introduced.

The exact declaration digest body has keys `version`, `scope`, `protocol`, `fixture_sha256`, `genesis_sha256` and `declaration`. `scope` equals `STATUS`; `declaration` is its complete `asdict` value. The exact `protocol` keys/values are `tick_nano: 50000`, `entry_delay_ns: 100000000`, `entry_wait_ns: 1000000000`, `end_buffer_ns: 18000000000`, `quantity_contracts: 1`, `max_quotes: 128`, `max_publications: 1`, `max_accounting_records: 3`, `max_result_bytes: 65536`, `clock_event_id: "publication-clock"`, `request_event_id: "admission-request"`, `outcome_event_id: "entry-outcome"` and `entry_receipt_id: "constructed-entry-receipt"`. Use the same bounded canonical JSON rules as the result; include no extra envelope keys. Behavior described above is fixed by the versioned implementation, not caller options.

These protocol-body values are fixed versioned literals, distinct from runtime resource-enforcement cap variables. A defensive test may lower an enforcement cap without changing the declaration identity, but its reduced result cap must remain above the complete declaration body's size so that the probe specifically reaches the result-size guard. Production caps have the fixed values above; there is no caller cap option or automatic protocol change.

Hash exactly `dataclasses.asdict(plan)` minus only its own plan digest, with `ensure_ascii=True`, sorted keys, compact separators, `allow_nan=False`, UTF-8 and a pre-hash 64 KiB limit. All authority names from the paired assessment remain exact false, including original policy, native-history authentication, real timers/fill absence, account/cash/margin/risk, storage/resume, training/trading/scoring/validation/promotion. Reproducible pure calls are not persisted exactly-once progression or cross-call continuity.

## Acceptance and honest remaining gap

Independent expected controls must rederive every native digest, accounting record/head/state, source link, budget decision and canonical plan field. Test first-cursor publication, opposing equal-time suffixes, readiness/deadline at one nanosecond either side, wide-then-narrow permanent refusal, inclusive deadline fills, source-closed timeout before a later price, EOF, both sides, denied cash/loss and missing/zero margin, fees/reserves/zero-valued liabilities and null complete return. Invalid metadata/caps/pins/strict types must refuse before price access. Changed or omitted complete inputs and changed expected result pins must refuse.

Instrument maximum 128-quote build plus full rebuild verification without weakened prefix checks; impose a generous synthetic runtime bound, not a trading latency claim. Check 129 quotes and a second publication refuse without subsets. Disable I/O, processes, clocks, network, models and order hooks. Require independent complete source/test review, root focused/adjacent tests, whole Ruff, new-file format checks, unchanged held pins and a fresh source-frozen complete project suite before acceptance.

This connects constructed native-to-accounting entry provenance for one prospectively declared candidate only. It does not implement original policy selection, multiple opportunities, funded-state strategy recomputation, denial ID/cooldown effects, exits/holds, multi-session continuity, history or independent validation. Those remain separately reviewed future work; historical execution additionally needs fresh prospective complete-cohort registration. No existing UNKNOWN, old outcome or collector is changed.

## Invented in memory example

Root executed this two-quote example once successfully before suite 4, then verified its complete rebuild. It creates only invented in-memory inputs. Its tiny USD values are accounting-test arithmetic, not measured broker fees or margin. The declaration and pins are locally generated demonstration values, not authenticated original market/account evidence. Do not repeat this completed example merely for status.

```python
from ai_trader.research import six_e_declared_admission as admission
from ai_trader.research import six_e_declared_economics as economics
from ai_trader.research import six_e_entry_budget as budget
from ai_trader.research import six_e_native_prefix as native
from ai_trader.research import six_e_single_entry_driver as driver
start = 10_000_000_000
publication = start + 1_000_000_000
fixture = native.NativeFixture(
    "synthetic-entry-guide", "6EM5", "1" * 64, start, start + 90_000_000_000,
    (native.NativeQuote(publication, 1_000_000_000, 1_000_050_000),
     native.NativeQuote(publication + 100_000_000, 1_000_000_000, 1_000_050_000)),
    (native.NativePublication("publication-1", 0, publication),),
)
genesis = admission.DeclaredAdmissionGenesis(
    "synthetic-entry-guide", economics.EconomicSeed(135, start),
    economics.DeclaredEconomics("USD", 625, 10, 20, economics.DeclaredMargin(100, 80)),
    budget.DeclaredBudgetLimits(5, 0, 10),
)
declaration = driver.SingleEntryDeclaration("synthetic-entry-guide", "publication-1", "entry-1", "long")
fixture_pin, genesis_pin = native.fixture_sha256(fixture), admission.genesis_sha256(genesis)
declaration_pin = driver.declaration_sha256(declaration, fixture_sha256=fixture_pin, genesis_sha256=genesis_pin)
expected = dict(expected_fixture_sha256=fixture_pin, expected_genesis_sha256=genesis_pin, expected_declaration_sha256=declaration_pin)
plan = driver.build_single_entry_plan(fixture, genesis, declaration, **expected)
assert driver.verify_single_entry_plan(fixture, genesis, declaration, **expected, expected_plan_sha256=plan.plan_sha256) == plan
state = plan.terminal_accounting_state
assert len(plan.quote_audit) == 2 and len(plan.records) == 3
assert plan.first_disposition == "declared_budget_available"
assert plan.execution_outcome == "constructed_entry_receipt" and state.phase == "OPEN"
assert state.entry_fees_usd_micros == 10 and state.total_commitments_usd_micros == 120
assert state.complete_declared_equity_usd_micros is None and state.complete_declared_net_return_usd_micros is None
assert all(flag is False for _, flag in plan.authority_flags)
print(plan.status, plan.execution_outcome, state.phase, plan.plan_sha256)
```

The printed result is `constructed_single_entry_plan_not_trading constructed_entry_receipt OPEN`, plan SHA256 `0397135fff8ca5e1e498f0fc9abdeeae5494267eabae5e371716aa21534bcb06`. Run it only in the installed project virtual environment; it requires no keys, network, downloads, file inputs or model. An OPEN simulated position is retained inventory, not realized trading profit. This module has no autonomous runner or training hook.

