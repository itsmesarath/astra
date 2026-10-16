# One constructed entry and causal exit

This prospectively reviewed contract describes a separate pure synthetic roundtrip driver. Implementation, independent complete review, all 1,624 root adjacent tests and complete suite 5 are accepted. The full suite passed 6,730 tests with three expected skips; complete coverage, process exit and unchanged pins were verified at 17:57:06 UTC. It extends constructed entry provenance through one original-style exit, retaining declared fees, reserves and unresolved inventory. It does not select a strategy, validate historical performance, trade or train a model.

## Complete retained context

The new module is `ai_trader.research.six_e_single_roundtrip_driver`. Existing sources and results remain unchanged. Allowed dependencies are the standard library and held native-prefix, declared-admission, budget, assessment and single-entry modules. There is no I/O, CLI, wall clock, historical loader, policy/model hook, account storage, resume or order connection.

Require exact complete `NativeFixture` and fresh `DeclaredAdmissionGenesis` objects plus frozen slotted `SingleRoundtripDeclaration(declaration_id, publication_id, admission_id, side, exit_plan)`. Session, scenario and declaration have the exact held nonempty ASCII `synthetic-` label. Side is exactly `long` or `short`; exit plan is exactly `time_exit` or `bracket_exit`. Only `6EM5`, `6EU5`, `6EZ5`, `6EH6` are supported. Genesis initialization equals fixture start. One sole prospective publication must identify its original first native row, with strict publication time plus 18 seconds less than fixture end.

Limits are 128 complete quotes, exactly one publication, at most five accounting records and 64 KiB complete canonical result. Reject excessive complete inputs; never truncate. Exact types, field completeness, labels, scalar metadata, all retained pin syntax, immutable tuple caps and publication identity precede quote-price access. Revalidate poisoned frozen objects at the consuming boundary. Derive and bound every readiness, hold and deadline timestamp, and keep entire inclusive execution intervals inside the fixture's half-open interval.

Require independently retained original fixture, genesis and declaration SHA256 expectations on both build and verifier. Do not accept a submitted old entry plan, its terminal EOF prefix or a returned boundary as authority. Walk the complete fixture freshly and causally from the single original seed. A coherent replacement of all invented context and expectations is not authenticated or detectable.

## Entry and immutable disposition

Consume every quote contiguously through the held native APIs. At the original publication's first cursor, regenerate its OPEN witness before an equal-time suffix. Append `ClockAdvanced` then `AdmissionRequested` at publication time, with exact source links and the original genesis.

Retain the original request transition's sequence-one budget decision and immutable first disposition, separately from later outcomes. Denied or undetermined funding creates no pending entry, fee, exit or liability. It still retains the complete request and native audit. Do not reset funding or replace the decision with a reassessment of pending state.

Preserve original 100 ms readiness and inclusive one-second wait. The first eligible entry row alone is a candidate: a spread other than 50,000 nanounits permanently refuses entry, including before a later narrow equal-time row. Otherwise construct one full-contract receipt at ask for long or bid for short. Charge declared entry fee once and retain margin and exit-fee reserve. This quantity and price crossing are explicit supplied-top-of-book assumptions, without size, depth, queue, venue or broker evidence.

If no eligible row exists, close through the original entry deadline after all deadline rows, before consuming later prices or at complete pinned EOF. Only then construct entry timeout at that original deadline. A denied, refused or timed-out entry has no exit.

## Causal exit requests and execution

Hold time is exactly the actual constructed entry receipt time plus 15 seconds. It wins equality: request an exit before consuming the first row at or after that hold time. Regenerate a CLOSED boundary through **hold time minus one nanosecond**, then append `ExitRequested` at the derived hold time. This proves the supplied strictly earlier interval; it is not real elapsed time or a broker timer. A boundary through hold time would incorrectly require consuming an at-hold row before the timer. At complete pinned EOF, generate the same strict-before-hold boundary and original request. Never retime the hold from publication, next observed quote or known outcomes.

For `bracket_exit`, inspect each consumed quote while OPEN, including the constructed entry row and later equal-time rows, strictly before hold time. Compute the original comparison: long `(bid - entry) // 50000 - 1`, short `(entry - ask) // 50000 - 1`. The first comparison reaching at least +3 or at most -3 requests an exit at that exact consumed row, reason `target` or `stop`. Do not clamp to a barrier. `time_exit` ignores these comparisons and requests only the original hold timer. Once requested, no later trigger changes its reason or time.

Exit readiness is request time plus 100 ms and its deadline is readiness plus one second, inclusive. Construct a receipt at the **first** consumed eligible row: bid for long, ask for short. Unlike entries, widened exits remain eligible; retain overshoot and actual crossed price without searching for a better row. An exit cannot execute on the request row because delay is strictly positive. No entry-budget gate may suppress an existing position's otherwise valid exit, even if declared final cash becomes negative.

If no eligible exit exists, consume all rows at its original deadline, regenerate CLOSED coverage through that deadline before any later row or at complete pinned EOF, then append `ExitUnknown` exactly at the deadline. Retain original inventory, margin and exit reserve forever in this plan. Later quotes only extend the complete audit, not a fill, reference, reconciliation, cancellation or account clock. UNKNOWN remains a liability even with zero monetary commitments, and complete equity and return stay null.

An exit receipt charges the declared exit fee exactly once, realizes the actual signed crossed-price difference at the declared USD tick value and releases commitments. The old extra tick belongs solely to bracket comparison, never a second monetary debit. Complete hypothetical flat equity/return is arithmetic, not measured broker or CFD economics, trading profitability or independent validation.

## Closed schema and canonical identity

Constants are `VERSION = "six_e_single_roundtrip_driver_v1"`, `STATUS = "constructed_single_roundtrip_plan_not_trading"`, `SingleRoundtripDriverError(ValueError)`, `MAX_DRIVER_QUOTES = 128`, `MAX_DRIVER_PUBLICATIONS = 1`, `MAX_ACCOUNTING_RECORDS = 5`, `MAX_RESULT_BYTES = 65536`, `END_BUFFER_NS = 18000000000`, `HOLD_NS = 15000000000`, `TARGET_TICKS = 3`, `STOP_TICKS = -3`, `COMPARATOR_COST_TICKS = 1`.

Generated ID constants are `CLOCK_EVENT_ID = "publication-clock"`, `REQUEST_EVENT_ID = "admission-request"`, `ENTRY_OUTCOME_EVENT_ID = "entry-outcome"`, `ENTRY_RECEIPT_ID = "constructed-entry-receipt"`, `EXIT_REQUEST_EVENT_ID = "exit-request"`, `EXIT_REQUEST_ID = "constructed-exit-request"`, `EXIT_OUTCOME_EVENT_ID = "exit-outcome"`, `EXIT_RECEIPT_ID = "constructed-exit-receipt"`. Original declaration admission ID remains separate. `AUTHORITY_FLAGS` equals the assessment's exact immutable false tuple.

Frozen slotted `QuoteAudit` fields are `cursor`, `received_at_ns`, `consumed_count`, `consumed_content_sha256`. Frozen slotted `AccountingLink` fields are `record_index`, `event_id`, `record_sha256`, `native_prefix`, `kind`, `publication`, `boundary`. Native and admission result field types are the held types; budget decision is the held type.

Ordered `SingleRoundtripPlan` fields are `version`, `status`, `fixture_sha256`, `genesis_sha256`, `declaration_sha256`, `declaration`, `publication`, `budget_decision`, `first_disposition`, `entry_execution_outcome`, `entry_outcome_cursor`, `entry_outcome_at_ns`, `hold_at_ns`, `exit_trigger_reason`, `exit_trigger_cursor`, `exit_requested_at_ns`, `exit_execution_outcome`, `exit_outcome_cursor`, `exit_outcome_at_ns`, `records`, `record_links`, `quote_audit`, `terminal_native_prefix`, `terminal_accounting_state`, `plan_sha256`, `authority_flags`.

Entry outcome is exactly `constructed_entry_receipt`, `simulator_spread_refusal`, `constructed_entry_timeout` or `no_pending_entry`. Candidate outcomes use their exact cursor and receive time; timeout has null cursor and original deadline; no pending entry has both null. `hold_at_ns` is original receipt plus hold, or null without a receipt, and is retained even after an exit request. Exit trigger is null without an entry, otherwise exactly `hold_timer`, `target` or `stop`. Hold trigger cursor is null; bracket trigger cursor is exact. Request time is null only without entry. Exit outcome is exactly `constructed_exit_receipt`, `constructed_exit_unknown` or `no_exit`; receipt uses exact cursor/time, UNKNOWN null cursor/original deadline, no exit both null. Every entered position ends either FLAT after receipt or EXIT_UNKNOWN after the supplied original deadline; there is no pending or arbitrarily OPEN terminal shortcut.

Link kinds are exactly `publication`, `entry_candidate_quote`, `entry_deadline_boundary`, `bracket_trigger_quote`, `hold_boundary`, `exit_candidate_quote`, `exit_deadline_boundary`. Publication links have the original OPEN witness and null boundary; all candidate/trigger quote links have both witnesses null; boundary links have null publication and the regenerated CLOSED boundary. Hold boundary through is request time minus one; other deadline boundary through is record time. Record indices and IDs are exact, contiguous and one-for-one; record SHA is the resulting held accounting head.

Every source-link prefix must exactly equal its matching complete audit row's cursor, receive time, consumed count and digest. Regenerate each native prefix/witness/closure and reconstruct each complete accounting prefix and final state. Candidate prices and trigger predicates must match the exact consumed original row and side. Hold and deadline records derive time from original retained liability/entry, never a supplied replacement certificate. Complete audits include all input quotes after FLAT or UNKNOWN without account advancement.

Pure APIs are:

```python
declaration_sha256(declaration, *, fixture_sha256, genesis_sha256)
build_single_roundtrip_plan(fixture, genesis, declaration, *,
    expected_fixture_sha256, expected_genesis_sha256, expected_declaration_sha256)
verify_single_roundtrip_plan(fixture, genesis, declaration, *,
    expected_fixture_sha256, expected_genesis_sha256,
    expected_declaration_sha256, expected_plan_sha256)
```

The declaration digest uses exactly keys `version`, `scope`, `protocol`, `fixture_sha256`, `genesis_sha256`, `declaration`; scope equals STATUS and declaration is full `asdict`. Fixed versioned protocol keys are `tick_nano:50000`, `entry_delay_ns:100000000`, `entry_wait_ns:1000000000`, `exit_delay_ns:100000000`, `exit_wait_ns:1000000000`, `hold_ns:15000000000`, `target_ticks:3`, `stop_ticks:-3`, `comparator_cost_ticks:1`, `end_buffer_ns:18000000000`, `quantity_contracts:1`, `max_quotes:128`, `max_publications:1`, `max_accounting_records:5`, `max_result_bytes:65536`. The eight generated ID keys are exactly `clock_event_id`, `request_event_id`, `entry_outcome_event_id`, `entry_receipt_id`, `exit_request_event_id`, `exit_request_id`, `exit_outcome_event_id`, `exit_receipt_id`, with their constant literal values above. These versioned values do not change when a defensive test lowers a runtime enforcement cap.

The plan digest is full `dataclasses.asdict(plan)` minus only `plan_sha256`. Both identities use ASCII canonical UTF-8 JSON, sorted keys, compact separators and `allow_nan=False`; check 64 KiB before hashing. Verifier checks retained output-pin syntax before deep quote access, rebuilds the entire result from original inputs and compares its complete canonical pin. It does not consume a submitted plan or refresh expectations.

All source, account, receipt, native-history, timer, execution, cash, margin, risk, storage/resume, original-policy, trading, training, scoring, validation and promotion flags remain exact false. Reproducible in-memory reconstruction is not persisted exactly-once progression or cross-call continuity.

## Acceptance and remaining work

Independent tests must rederive complete native digests, accounting records/heads/states, sequence-one budget, all links and full canonical bodies. Cover both sides/plans, first-cursor and equal-time suffixes, entry spread refusal, target/stop thresholds and hold equality, hold-minus-one closure, readiness/deadline one-nanosecond boundaries, widened/overshooting exits, long gaps, EOF, UNKNOWN terminal, denied/missing funding, zero-valued liabilities, negative cash, exactly-once fees and reserve release. Invalid metadata, caps, strict types and pin syntax must refuse before price inspection; mismatching otherwise-valid complete-input pins refuse during full reconstruction. Guard forbidden I/O, processes, clocks, network, models and order hooks. Exercise full 128-quote build and rebuild with a generous synthetic runtime bound, not a latency claim; 129 refuses without truncation.

Require independent complete source/test review, root focused and adjacent tests, whole Ruff, new-file formatting, unchanged held 402-file baseline and a fresh complete frozen-source project suite. Do not interpret focused tests or progress dots as full acceptance.

This is one prospectively declared entry and its constructed exit only. Complete funded-path original strategy recomputation, multiple opportunities, denial and cooldown policy, multi-session continuity, historical input/calendar support and historical experiments remain separately reviewed and prospectively registered work. No collector, model, original UNKNOWN liability or old result changes.

## Invented in memory example

Root ran and rebuilt this four-quote example once at 17:15:53 UTC, before focused or complete-suite acceptance. Its tiny USD micro-unit values are toy accounting inputs, not broker fees, margin or a trading recommendation. Locally generated demonstration pins are not authenticated market or account evidence. Do not repeat this completed example merely for status.

```python
from ai_trader.research import six_e_declared_admission as admission
from ai_trader.research import six_e_declared_economics as economics
from ai_trader.research import six_e_entry_budget as budget
from ai_trader.research import six_e_native_prefix as native
from ai_trader.research import six_e_single_roundtrip_driver as driver

start = 10_000_000_000
publication = start + 1_000_000_000
entry = publication + 100_000_000
hold = entry + 15_000_000_000
price = 1_000_000_000
fixture = native.NativeFixture(
    "synthetic-roundtrip-guide", "6EM5", "1" * 64, start, start + 90_000_000_000,
    (native.NativeQuote(publication, price, price + 50_000),
     native.NativeQuote(entry, price, price + 50_000),
     native.NativeQuote(hold, price + 500_000, price + 550_000),
     native.NativeQuote(hold + 100_000_000, price, price + 200_000)),
    (native.NativePublication("publication-1", 0, publication),),
)
genesis = admission.DeclaredAdmissionGenesis(
    "synthetic-roundtrip-guide", economics.EconomicSeed(135, start),
    economics.DeclaredEconomics("USD", 125, 10, 20, economics.DeclaredMargin(100, 80)),
    budget.DeclaredBudgetLimits(5, 0, 10),
)
declaration = driver.SingleRoundtripDeclaration(
    "synthetic-roundtrip-guide", "publication-1", "entry-1", "long", "time_exit",
)
fixture_pin = native.fixture_sha256(fixture)
genesis_pin = admission.genesis_sha256(genesis)
declaration_pin = driver.declaration_sha256(
    declaration, fixture_sha256=fixture_pin, genesis_sha256=genesis_pin,
)
expected = dict(expected_fixture_sha256=fixture_pin, expected_genesis_sha256=genesis_pin,
                expected_declaration_sha256=declaration_pin)
plan = driver.build_single_roundtrip_plan(fixture, genesis, declaration, **expected)
assert driver.verify_single_roundtrip_plan(
    fixture, genesis, declaration, **expected, expected_plan_sha256=plan.plan_sha256,
) == plan
state = plan.terminal_accounting_state
assert len(plan.records) == 5 and len(plan.quote_audit) == 4
assert plan.exit_trigger_reason == "hold_timer" and plan.exit_requested_at_ns == hold
assert plan.record_links[3].boundary.through_ns == hold - 1
assert plan.exit_execution_outcome == "constructed_exit_receipt" and state.phase == "FLAT"
assert state.gross_realized_usd_micros == -125
assert state.entry_fees_usd_micros == 10 and state.exit_fees_usd_micros == 20
assert state.total_commitments_usd_micros == 0
assert state.complete_declared_equity_usd_micros == -20
assert state.complete_declared_net_return_usd_micros == -155
assert all(flag is False for _, flag in plan.authority_flags)
print(plan.status, plan.exit_execution_outcome, state.phase, plan.plan_sha256)
```

The printed result is `constructed_single_roundtrip_plan_not_trading constructed_exit_receipt FLAT`, plan SHA256 `813aeedbfc9ca4431dd6c11d51e8f2e729e02b8ff6cd66fe9f38994630079774`. Run only in the installed project virtual environment. The example has no file input, key, download, network, model or actual order. Its fabricated negative cash and complete return demonstrate accounting behavior, not actual financial performance, account solvency or a strategy edge.
