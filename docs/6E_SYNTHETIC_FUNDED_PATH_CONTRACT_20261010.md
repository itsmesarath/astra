# Synthetic funded path implementation contract

This is the closed prospective contract for one complete invented funded path. It is not an implemented component, a historical experiment, a paper exchange or permission to train or trade. Source release requires root review of this contract and enough time for independent implementation, tests, review and a fresh frozen-source complete suite. The accepted 406-file baseline and every old source, result, input and UNKNOWN liability remain unchanged.

The proposed new module is `src/ai_trader/research/six_e_synthetic_funded_path.py`, with a separate new test file. It must walk one fresh synthetic quote fixture from one immutable declared genesis. It may use the held native, admission, budget and point helpers; it must not compose completed single-entry or roundtrip plans. Their terminal states already consumed future quotes. All schemas, literals and rules below are normative for this version; implementation changes to them require another reviewed contract, not silently refreshed expectations.

## Scope and fixed limits

The module has no file, clock, process, model, history, calendar, broker, network, account store, CLI, resume or order hook. Imported held helpers may have a larger transitive import graph; these six declared helper pins do not authenticate that graph or runtime. There is no execution of a loader, model or source-file hash operation in this module.

Use these exact constants:

| Constant | Literal value |
| --- | --- |
| `VERSION` | `six_e_synthetic_funded_path_v1` |
| `STATUS` | `constructed_funded_path_not_authenticated_execution` |
| `MAX_QUOTES` | 128 |
| `MIN_PUBLICATIONS`, `MAX_PUBLICATIONS` | 1, 4 |
| `MAX_ACCOUNTING_RECORDS` | 20 |
| `MAX_CANONICAL_BYTES` | 262144 |
| `TICK_NANO` | 50000 |
| `ENTRY_DELAY_NS`, `EXIT_DELAY_NS` | 100000000, 100000000 |
| `ENTRY_WAIT_NS`, `EXIT_WAIT_NS` | 1000000000, 1000000000 |
| `HOLD_NS`, `COOLDOWN_NS`, `END_BUFFER_NS` | 15000000000, 10000000000, 18000000000 |
| `MIN_PUBLICATION_CADENCE_NS` | 1000000000 |
| `TARGET_TICKS`, `STOP_TICKS`, `COMPARATOR_COST_TICKS` | 3, -3, 1 |
| `QUANTITY_CONTRACTS` | 1 |
| Supported contracts | `6EM5`, `6EU5`, `6EZ5`, `6EH6`, in that order |

The complete fixture has 1–128 quotes and 1–4 publications in original order, at least one second apart. Retain the held native first-cursor, exact-type, timestamp, price-grid and synthetic-label guards. Require `fixture.end_ns <= native.MAX_INT - COOLDOWN_NS` and `genesis.seed.initialized_at_ns == fixture.start_ns`. A publication may be late and ineligible; do not require every publication to pass the entry buffer.

All new canonical bodies use one 262144-byte runtime guard. The protocol's declared literal limit stays 262144 if a test lowers the runtime guard. Nested native, admission and point bodies retain their smaller or independent held limits. Exact-cap equality passes; excess refuses the complete body. Measure a complete 128-quote, four-publication, twenty-record result with maximum identifier shapes and retained point contexts before accepting the cap. A passing ordinary example is not that capacity proof.

## Exact immutable inputs and APIs

Every new dataclass is frozen and slotted. Every public function requires exact classes and complete fields, not subclasses, duck types, omitted slots or dictionaries. Tuples must have exact type `tuple`; booleans exact type `bool`; timestamps, cursors, ordinals, counts and directions exact type `int`, never bool. Point values keep the held finite exact-int/exact-float rules and preserve int/float and signed-zero identities. Existing typed payloads are revalidated even if a frozen instance was deliberately poisoned.

The new input types have exactly these fields, in this order:

```text
PublishedLiquidityBinding
  publication_id: str
  eligible: bool
  point: point.SyntheticLiquidityPoint
  point_sha256: str

FundedPathDeclaration
  declaration_id: str
  policy_id: str
  exit_plan: str
```

`bindings` is an exact ordered tuple of 1–4 `PublishedLiquidityBinding` objects. Publication IDs match every original fixture publication one-for-one and in order. Publication IDs and point IDs are separately unique. Binding constructors validate metadata and retained-pin syntax without traversing numeric point values. The declaration ID, fixture session, genesis scenario and point IDs are nonempty `synthetic-` identifiers under the held ASCII identifier bound. Ordinary publication IDs retain the native ASCII identifier rule. Policy is exactly one of `cvd_follow`, `liquidity_follow`, `absorption_fade`, `no_trade`; exit plan is exactly `time_exit` or `bracket_exit`. Neither changes by publication. Eligibility and features are caller assertions, not authenticated or derived market evidence.

The public APIs have no defaults, no submitted plan argument and no supplied earlier records/state:

```text
protocol_sha256() -> str

bindings_sha256(
  bindings: tuple[PublishedLiquidityBinding, ...]
) -> str

declaration_sha256(
  declaration: FundedPathDeclaration, *,
  fixture_sha256: str,
  genesis_sha256: str,
  bindings_sha256: str
) -> str

build_funded_path_plan(
  fixture: native.NativeFixture,
  genesis: admission.DeclaredAdmissionGenesis,
  bindings: tuple[PublishedLiquidityBinding, ...],
  declaration: FundedPathDeclaration, *,
  expected_protocol_sha256: str,
  expected_fixture_sha256: str,
  expected_genesis_sha256: str,
  expected_bindings_sha256: str,
  expected_declaration_sha256: str
) -> FundedPathPlan

verify_funded_path_plan(
  fixture: native.NativeFixture,
  genesis: admission.DeclaredAdmissionGenesis,
  bindings: tuple[PublishedLiquidityBinding, ...],
  declaration: FundedPathDeclaration, *,
  expected_protocol_sha256: str,
  expected_fixture_sha256: str,
  expected_genesis_sha256: str,
  expected_bindings_sha256: str,
  expected_declaration_sha256: str,
  expected_plan_sha256: str
) -> FundedPathPlan
```

Prospective hash functions produce local identities, never independently retained expectations. `bindings_sha256` validates complete binding metadata, every individual pin's syntax, uniqueness and tuple bounds before numeric content; it then verifies each complete point pin and hashes the complete ordered bindings. It cannot check fixture alignment because it has no fixture. `declaration_sha256` binds the four original context identities below but does not claim to validate their absent objects. Build verifies every original input, every context pin and complete alignment before walking. Verify checks all expectation syntax first, rebuilds through build from the same original inputs, and compares the rebuilt complete plan pin. No result, packet, prior state or updated expectation is adopted.

Public failures normalize `ValueError`, `TypeError`, `AttributeError` and `OverflowError` into `SyntheticFundedPathError(ValueError)`. Return no partial plan, mutate no supplied object and do not retry, truncate, clip money or refresh pins. Absence of a generated receipt is not a broker cancellation claim.

## Preflight before numeric content

Build and verify apply these phases in order:

1. Require complete exact outer classes/tuples and count bounds. Check the syntax of **every** expected pin, each binding's retained point pin and declared helper pin: exact lowercase 64-character SHA256. Verify checks the expected plan pin here, before any quote price or feature number.
2. Validate declaration, synthetic labels, contract, native metadata, binding IDs/eligibility/point metadata and the complete ordered publication-to-binding relationship. Point metadata means exact class, complete fields, bounded synthetic point ID and an exact 37-value tuple; do not traverse its numeric values yet.
3. Inspect every quote's exact class/field presence and timestamp metadata only. Check bounded ordered receive timestamps inside `[start_ns, end_ns)`, every publication's first-cursor timestamp match, no preceding equal-time row, unique/increasing publication cursors and at-least-one-second cadence. This outer metadata pass is required: held `native.prepare_fixture` alone checks the final first-cursor linkage only after quote-price traversal.
4. Check the metadata-only end/cooldown bound, fresh seed identity and complete declared protocol identity. For each publication passing `now < fixture.end_ns - END_BUFFER_NS`, bound entry readiness/deadline, latest possible actual-entry hold and latest exit readiness/deadline strictly before fixture end. Do not compute an unused `now + END_BUFFER_NS` for a late publication. Do not inspect bid/ask or numeric features during these phases.
5. Revalidate the complete genesis/seed/economics/limits and its retained hash, every point's complete content against its pin, complete bindings content, complete fixture through `native.prepare_fixture`, and context-bound declaration content. All complete bodies obey their byte guards. Complete input identity includes future values; it must not control earlier causal state, identifiers or selection.

Only after complete input acceptance may the causal walk begin. A poisoned feature/price accessor combined with a malformed late metadata/pin must fail for metadata/pin without accessing that number. Constructors may have validated caller objects earlier; public-function revalidation still enforces this ordering on poisoned retained objects.

## Canonical bodies and declared provenance

Canonical bytes are exactly `json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")`, under the full byte bound, hashed with SHA256. Dataclasses project with `dataclasses.asdict`; tuples project as JSON arrays; `None` as null. No key is omitted except the result's own `plan_sha256` while calculating that result pin. Do not format, round, sanitize NaN, collapse numeric types, change signed zero, reorder tuple entries or replace complete content with a summary.

The fixed protocol body has exactly these fields. Values in the tables/blocks are literals except `selector_protocol_sha256`, obtained from the held pure `point.protocol_sha256()` and required to equal the retained fixed point protocol `d85e79987b12130f4dd54e106a247e621b96dba7ab0bdf1c9c267b4295076f6e`:

```text
version: VERSION
status: STATUS
selector_protocol_sha256: fixed held point protocol pin
helper_source_pins: object with exactly the six path/pin pairs below
supported_contracts: ["6EM5", "6EU5", "6EZ5", "6EH6"]
policies: ["cvd_follow", "liquidity_follow", "absorption_fade", "no_trade"]
exit_plans: ["time_exit", "bracket_exit"]
tick_nano: 50000
entry_delay_ns: 100000000
entry_wait_ns: 1000000000
exit_delay_ns: 100000000
exit_wait_ns: 1000000000
hold_ns: 15000000000
cooldown_ns: 10000000000
end_buffer_ns: 18000000000
min_publication_cadence_ns: 1000000000
target_ticks: 3
stop_ticks: -3
comparator_cost_ticks: 1
quantity_contracts: 1
max_quotes: 128
min_publications: 1
max_publications: 4
max_accounting_records: 20
max_canonical_bytes: 262144
max_fixture_end_ns: 9223372026854775807
selection_order: ["ineligible", "inventory_blocked", "pending_entry_blocked",
                  "cooldown", "no_signal", "candidate"]
quote_order: ["elapsed_deadlines_and_due_hold", "consume_quote",
              "entry_candidate", "bracket_trigger", "exit_candidate",
              "first_cursor_publication"]
initial_cooldown_until_ns: 0
candidate_budget_mapping: {"declared_budget_available": "entry_selected",
                          "declared_budget_insufficient": "budget_denied",
                          "budget_undetermined": "budget_undetermined"}
denied_candidate_effects: "consume_ordinal_clock_request_only"
deadline_rule: "inclusive_quote_deadline_close_when_next_timestamp_is_greater"
hold_rule: "actual_entry_plus_hold_wins_equality_closed_through_hold_minus_one"
eof_rule: "close_original_timers_no_new_account_clock"
unknown_rule: "terminal_inventory_no_later_accounting_mutation"
accounting_seed_rule: "one_fresh_immutable_genesis_no_reseed"
entry_execution_rule: "first_eligible_quote_one_tick_spread_or_permanent_refusal"
exit_execution_rule: "first_eligible_crossed_quote_widening_retained_no_budget_gate"
comparator_rule: "bracket_difference_ticks_minus_one_not_an_extra_money_debit"
identifier_templates: exact ten template object below
authority_flags: exact sorted 57-pair false tuple below
```

The declared helper source map is:

| Path | Raw source SHA256 |
| --- | --- |
| `src/ai_trader/research/six_e_native_prefix.py` | `ae1a7e98aec517e1aa9bcd45f869040d812cfbb19190313b240a5313dca748b5` |
| `src/ai_trader/research/six_e_declared_admission.py` | `69f1850ab6f7721005b47bf798e1960d1b3081021f0e9b3bc8240aafe4da5abb` |
| `src/ai_trader/research/six_e_entry_budget.py` | `be3e0b924356b1090dff802cbb8be3059aec81002d550afebc8ef1ef475b72d6` |
| `src/ai_trader/research/six_e_declared_economics.py` | `d45137f63c82afcce41d4214546d5ec1a1402487e8f91f02fd90d6617e627c85` |
| `src/ai_trader/research/six_e_native_admission_assessment.py` | `5810d5213ce03bf326fee97e2252dbfe197cb93400cced4fac91a80723b0fcb6` |
| `src/ai_trader/research/six_e_synthetic_liquidity_point.py` | `4cba581af818c9fb9b5ad9aef876216350b4bff5e1368e2afb4355754c46b35e` |

These are declared literals retained from the accepted baseline, not source-file checks in the proposed module. They are neither the entire import/runtime graph nor the old 47-wrapper or 40-replay source sets. The point protocol separately retains its original four rule/source pins. The old single-roundtrip module is a reviewed behavior reference only: do not import or call its driver/build/verify to obtain a preceding state.

The complete bindings body is exactly:

```text
{version: VERSION,
 status: STATUS,
 selector_protocol_sha256: fixed held point protocol pin,
 bindings: asdict projection of every ordered binding}
```

It has no fixture/genesis/declaration identity. A future quote change with unchanged bindings must not change this body. Each full binding includes its complete point and retained point pin, not just a direction or summary.

The complete declaration body is exactly:

```text
{version: VERSION,
 status: STATUS,
 protocol_sha256: hash of the fixed complete protocol body,
 fixture_sha256: supplied original fixture pin,
 genesis_sha256: supplied original genesis pin,
 bindings_sha256: supplied original complete bindings pin,
 declaration: asdict projection of FundedPathDeclaration}
```

A coherent whole-context replacement with new retained expectations is not authenticated or detectable. A content pin is local identity, not source/funding/receipt provenance.

## Generated identities

Only an eligible, unblocked nonzero candidate consumes the next ordinal, before budgeting, starting at 1 and ending no later than 4. Denied and undetermined requests consume their ordinal. Blocked, cooldown, ineligible and no-signal publications consume none. IDs depend only on that ordinal, never input pins, prices, budget outcome or future selection.

`CandidateIdentifiers` is a frozen slotted dataclass with exactly these ten string fields, in this order. Its canonical protocol templates are the literal strings in the second column; replacement uses the four-digit zero-padded ordinal, such as `0001`, not a variable-width number:

| Field and protocol template key | Literal template |
| --- | --- |
| `candidate_id` | `synthetic-candidate-{ordinal:04d}` |
| `clock_event_id` | `synthetic-publication-clock-{ordinal:04d}` |
| `request_event_id` | `synthetic-admission-request-{ordinal:04d}` |
| `admission_id` | `synthetic-admission-{ordinal:04d}` |
| `entry_outcome_event_id` | `synthetic-entry-outcome-{ordinal:04d}` |
| `entry_receipt_id` | `synthetic-entry-receipt-{ordinal:04d}` |
| `exit_request_event_id` | `synthetic-exit-request-{ordinal:04d}` |
| `exit_request_id` | `synthetic-exit-{ordinal:04d}` |
| `exit_outcome_event_id` | `synthetic-exit-outcome-{ordinal:04d}` |
| `exit_receipt_id` | `synthetic-exit-receipt-{ordinal:04d}` |

A trace retains every generated name even when no associated event/receipt occurs. Unused names are not records, reservations, receipts or receipt-content hashes. All event IDs are unique across the complete walk; admission, request and the shared entry/exit receipt namespaces remain unique under the held accounting helper. Input publication/point/declaration IDs occupy their own metadata namespaces, not event IDs.

## Exact output schema

All output dataclasses are frozen/slotted. Their field order below is normative, although sorted-key canonical serialization does not rely on dataclass field order. Nested held objects retain every original field and flag. No nullable field is replaced with zero, an empty object or an invented witness.

```text
PublicationAudit
  publication: native.PublicationWitness
  eligible: bool
  end_buffer_eligible: bool
  point_sha256: str
  point_selection: point.PointSelection
  selected_direction: int
  phase_before: str
  accounting_prefix_before: admission.DeclaredPrefix
  accounting_prefix_after: admission.DeclaredPrefix
  cooldown_before_ns: int
  first_disposition: str
  candidate_ordinal: int | None
  candidate_id: str | None
  budget_decision: budget.DeclaredBudgetDecision | None
  decision_record_start: int | None
  decision_record_stop: int | None

CandidateTrace
  publication_id: str
  ordinal: int
  identities: CandidateIdentifiers
  direction: int
  side: str
  first_disposition: str
  budget_decision: budget.DeclaredBudgetDecision
  record_start: int
  record_stop: int
  entry_execution_outcome: str
  entry_outcome_cursor: int | None
  entry_outcome_at_ns: int | None
  hold_at_ns: int | None
  exit_trigger_reason: str | None
  exit_trigger_cursor: int | None
  exit_requested_at_ns: int | None
  exit_execution_outcome: str
  exit_outcome_cursor: int | None
  exit_outcome_at_ns: int | None

QuoteAudit
  cursor: int
  received_at_ns: int
  consumed_count: int
  consumed_content_sha256: str

AccountingLink
  record_index: int
  candidate_ordinal: int
  publication_id: str
  event_id: str
  record_sha256: str
  native_prefix: native.NativePrefix
  kind: str
  publication: native.PublicationWitness | None
  boundary: native.ClosedNativeBoundary | None

FundedPathPlan
  version: str
  status: str
  protocol_sha256: str
  fixture_sha256: str
  genesis_sha256: str
  bindings_sha256: str
  declaration_sha256: str
  declaration: FundedPathDeclaration
  bindings: tuple[PublishedLiquidityBinding, ...]
  publication_audit: tuple[PublicationAudit, ...]
  candidates: tuple[CandidateTrace, ...]
  records: tuple[admission.DeclaredRecord, ...]
  record_links: tuple[AccountingLink, ...]
  quote_audit: tuple[QuoteAudit, ...]
  terminal_native_prefix: native.NativePrefix
  terminal_accounting_state: admission.DeclaredAdmissionState
  terminal_cooldown_until_ns: int
  plan_sha256: str
  authority_flags: tuple[tuple[str, bool], ...]
```

The result canonical body is the complete `asdict(plan)` projection with only `plan_sha256` removed. The returned `plan_sha256` is its SHA256. Version/status/protocol/input pins are exact; every binding, publication, candidate, record/link, quote audit and terminal field is retained. Full original quote prices are in the separately required original fixture; the result binds that complete fixture and audits every consumed row. No prior input is recovered from a result or replaced by its copied bindings.

Publication audits are in exact original publication order. Compute and retain all four point directions even for blocked or ineligible publications, then choose the one fixed policy's direction. `selected_direction` is -1, 0 or 1; it does not change because eligibility/accounting blocks it. `phase_before` is exactly one held phase: `FLAT`, `ENTRY_PENDING`, `OPEN`, `EXIT_PENDING`, `EXIT_UNKNOWN`. It and `accounting_prefix_before` describe the state **after existing effects of that same consumed quote but before this publication's own candidate clock/request**. The publication witness is regenerated at its original first cursor, with `boundary_state == "OPEN"`, before any equal-time suffix.

`first_disposition` is exactly one of `ineligible`, `inventory_blocked`, `pending_entry_blocked`, `cooldown`, `no_signal`, `entry_selected`, `budget_denied`, `budget_undetermined`. The last three alone have a candidate ordinal/ID, budget and decision-record range. Their audit range is exactly two records `[start, start + 2)`, and `accounting_prefix_after` is the resulting post-request prefix. Every other audit has all five candidate/budget/range fields null and equal before/after prefixes. These enum names are not the helper's budget dispositions.

Every candidate range is zero-based, half-open and complete. Ranges in ordinal order are contiguous, start at zero, end at `len(records)` and partition every record exactly once. Length is 2 for denial/undetermined, 3 for selected refusal/timeout, or 5 for selected receipt plus resolved/UNKNOWN exit. Complete traces have no pending or unfinished outcome. Direction is -1 or 1, with side `short` or `long` respectively. Their originating audit, initial budget and first disposition match exactly; later outcome never rewrites the audit or initial disposition.

| Initial disposition and later outcome | Entry fields | Exit fields |
| --- | --- | --- |
| `budget_denied` or `budget_undetermined` | `no_pending_entry`; cursor/time/hold null | `no_exit`; trigger/cursor/request/outcome cursor/time all null |
| `entry_selected`, widened first quote | `simulator_spread_refusal`; actual cursor/time, hold null | `no_exit`; all remaining exit fields null |
| `entry_selected`, original no-quote timeout | `constructed_entry_timeout`; cursor null, time original deadline, hold null | `no_exit`; all remaining exit fields null |
| `entry_selected`, actual receipt | `constructed_entry_receipt`; actual cursor/time, hold exactly receipt time + 15s | Exit request and complete resolved/UNKNOWN outcome required |

For a received entry, trigger reason is `hold_timer`, `target` or `stop`. Hold trigger has null trigger cursor and request time equal to actual hold; target/stop has its consumed trigger cursor and request time equal to that quote's time, strictly before hold. Exit outcome is `constructed_exit_receipt` with actual cursor/time, or `constructed_exit_unknown` with null cursor and original deadline time. Its recorded trigger/request fields remain present in both cases. Neither a no-exit trace nor a denied trace carries an unused hold or exit timestamp.

## One causal walk and immutable first dispositions

Start with `native.initial_prefix(fixture, expected_fixture_sha256=...)`, empty records/links/audits, literal cooldown zero and `admission.reconstruct(genesis, (), expected_genesis_sha256=..., expected_terminal=admission.DeclaredPrefix(0, genesis_pin, seed.initialized_at_ns))`. There is exactly one original genesis; do not initialize an account again by candidate, timer, session or verification.

For every next quote timestamp, process due original timers chronologically before consuming that quote: an entry/exit deadline closes only when `next_time > deadline`, while an owned OPEN hold fires when `next_time >= hold`. After a hold request, reevaluate its newly established exit deadline against the same next timestamp; a long gap may close both, at their own original times. Stop timer processing at UNKNOWN. A quote at the inclusive deadline remains a possible candidate. A hold at H wins equality before a quote at H, using a CLOSED boundary through H-1, never the quote at H or its suffix as preceding evidence.

Consume exactly the next native cursor through `native.consume_next`, append its quote audit, then perform eligible current entry, bracket and exit effects in that order. Evaluate the original publication at this cursor only after those effects and before any later equal-time row. A newly received entry's same quote may be checked for a bracket predicate, but no delayed entry/exit can receive before readiness. The 100ms readiness prevents a newly requested exit from receiving on its request quote.

Publication precedence is strict:

1. Ineligible when the supplied flag is false or `now < fixture.end_ns - END_BUFFER_NS` is false.
2. Inventory blocked if any position or exit reservation exists, including zero-valued commitments and UNKNOWN.
3. Pending-entry blocked if a pending entry exists.
4. Cooldown if `now < cooldown_until_ns`; equality passes.
5. No signal if the fixed selected direction is zero.
6. Otherwise consume the next ordinal and append its same-time source-linked `ClockAdvanced`, then `AdmissionRequested(admission_id, fixture.contract, side, 1)` through `admission.advance` with the complete preceding records and exact current prefix.

`AdmissionRequested` supplies the budget decision from the immediately preceding **post-clock** accounting snapshot, naturally sequence 1, 6, 11 and 16 for four complete five-record roundtrips. Map `declared_budget_available` to `entry_selected`; `declared_budget_insufficient` to `budget_denied`; `budget_undetermined` to `budget_undetermined`. At this candidate stage, `entry_blocked_by_liability` is an inconsistent complete walk and refuses the plan, not another publication disposition. The candidate clock makes snapshot age zero even when the maximum age is zero; it does not observe or renew broker margin. Missing margin stays undetermined, while an explicitly zero margin is distinct.

Denied/undetermined requests create exactly two records, no pending entry, debit, reservation, hold or cooldown. Selected entry readiness/deadline comes from the held accounting helper. The first eligible quote is permanent: exactly one tick of spread permits a full-contract constructed entry at ask for long or bid for short; wider spread appends `EntryUnfilled(..., "simulator_refusal")` and does not wait for a better quote. No eligible quote closes `EntryUnfilled(..., "timeout")` at the original deadline, with complete CLOSED native boundary coverage. Both refusal and timeout set cooldown to their actual outcome time + 10s.

Actual receipt sets hold to actual entry time + 15s. In bracket mode, before hold use `(bid - entry_price) // TICK_NANO - 1` for long or `(entry_price - ask) // TICK_NANO - 1` for short. Target is >=3, stop <=-3, otherwise none. On grid this is four favorable ticks or two adverse ticks. At hold equality the timer wins, even if the quote would cross a bracket. The comparator tick is a selection condition only, not another monetary charge.

Every owned exit uses the original request's 100ms readiness and inclusive one-second wait. Receive at the first eligible quote, at bid for long or ask for short, retaining widening and overshoot without an entry budget/loss gate. Append the held full-contract `ExitReceipt`, charge its declared fee once and set cooldown at receipt time + 10s. No eligible exit closes `ExitUnknown` at the original deadline; inventory and reservations remain terminal. UNKNOWN adds no cooldown and permits no subsequent accounting event, clock, receipt, cancellation, late fill, quote reference or reconciliation. Held `admission.advance` alone does not enforce that last no-mutation rule; this walk must enforce it explicitly while still auditing all later quotes and publications.

At complete EOF close remaining original entry/hold/exit timers with held native boundary evidence in chronological order, without consuming another quote or adding an EOF accounting clock. Complete terminal phase is only `FLAT` or `EXIT_UNKNOWN`. Terminal native prefix covers all original quotes and `close_through(..., through_ns=fixture.end_ns)` can establish complete EOF coverage for checking; it does not change the accounting prefix. Keep the accounting frontier and last event time independent from EOF and terminal cooldown. Idle state remains the genesis prefix, last event null, no cooldown change and complete equity equal to the original seed.

## Complete accounting and witness links

Each append creates `DeclaredRecord(event_id, current_state.prefix, now, now, payload)` and calls the held `admission.advance` with **all** preceding records, the original genesis pin and exact current terminal prefix. Retain its returned records/state/budget. Every new record has one `AccountingLink` at the same zero-based index, original candidate ordinal/publication ID and returned state head as `record_sha256`; there is no invented extra previous-hash field.

Only these link kinds occur:

| `kind` | Held payload and native witness |
| --- | --- |
| `publication` | Candidate clock or admission request; original first-cursor OPEN publication, boundary null |
| `entry_candidate_quote` | Entry receipt or simulator refusal; exact consumed candidate quote prefix, both witness fields null |
| `entry_deadline_boundary` | Timeout; original deadline CLOSED boundary through deadline, publication null |
| `bracket_trigger_quote` | Exit request; exact consumed bracket quote prefix, both witness fields null |
| `hold_boundary` | Exit request recorded at H; CLOSED boundary through H-1, publication null |
| `exit_candidate_quote` | Exit receipt; exact consumed candidate quote prefix, both witness fields null |
| `exit_deadline_boundary` | ExitUnknown; original deadline CLOSED boundary through deadline, publication null |

Every link's native prefix must regenerate through `native.verify_prefix` and match the exact quote-audit row at `last_cursor`; every boundary regenerates through `native.close_through` at its unchanged boundary time and carries that same prefix. Link quote prices/cursors/intervals match their actual held payloads and first-candidate trace. Publication links regenerate through `native.publication_witness`. Reconstruct every complete preceding and resulting accounting prefix through the held helper and check every head, sequence/frontier, payload type, generated event/receipt/request ID and one-to-one link.

Retain every quote audit in cursor order with `consumed_count == cursor + 1` and the exact native rolling content digest. Publication/candidate traces link every initial decision to complete outcomes without altering a past disposition. Independently reconstruct terminal accounting state from all original records and compare every field, including receipt-content hashes, fees, reserves and liabilities. All records belong to a candidate; blocked/no-signal observations append none. A forged plan or changed budget/result cannot be supplied to verify because its only outcome expectation is the separately retained full plan pin.

## Money and authority limits

Use the unchanged USD declared economics, positive original seed and tick value, zero-or-positive fees, immutable margin and immutable budget limits. Gross realization is signed crossed-price ticks times the original tick value; charge entry and exit fees exactly once on their respective receipts. Preserve negative realization cash, original-seed net loss, margin/exit reserves and complete null equity/return during any liability, even when all monetary commitments are zero. Gains may offset prior losses under the held net-original-seed loss definition; this is not peak drawdown or the sum of losing trades. A cash buffer is an entry threshold, not a debit. Only the proposed entry fee affects hypothetical next admission loss. No quote movement restores an initially unaffordable flat seed by itself.

Check arithmetic when it is actually used. Overflow in a used money, timer, record or canonical body refuses the whole plan. Do not precompute an unused extreme price-times-tick product and reject a valid idle fixture, clip a liability, skip a losing exit, reduce quantity or reset funding. `DeclaredMargin` has no observation timestamp; no timestamped broker margin freshness is claimed.

Top-level `authority_flags` is exactly the sorted union of the held assessment and point flag tuples: the following **57** names, each paired with exact `False`. Nested held flags are not replaced with this union and retain their own exact tuples. There are no extra flags and no true flag:

```text
absence_of_eligible_fill_verified
account_authenticated
accounting_admission_authorized
accounting_transition_authorized
admission_authorized
broker_execution_confirmed
calendar_verified
cash_balance_confirmed
cash_confirmed
causal_features_verified
cfd_execution_confirmed
complete_decision_quote_audit_verified
complete_records_authenticated
complete_session_verified
consumer_coverage_verified
cpu_training
cross_call_continuity_authenticated
eligibility_verified
execution_assumptions_validated
execution_authorized
execution_confirmed
feed_authenticated
genesis_authenticated
independent_holdout
independent_validation
input_authenticated
margin_confirmed
margin_requirement_confirmed
native_accounting_history_verified
original_strategy_integration_verified
original_strategy_selection_verified
prefix_authenticated
promotion_allowed
publication_event_authenticated
qwen_training
receipt_authenticated
receipt_provenance_authenticated
receipt_provenance_verified
reservation_created
reserved_outcomes_opened
resume_authorized
risk_approved
risk_confirmed
runtime_authenticated
scoring_authorized
snapshot_prefix_authenticated
source_authenticated
source_files_authenticated
source_integrity_verified
storage_authorized
storage_resume_authorized
strategy_scoring_allowed
timeout_authorized
timer_elapsed_verified
trading_enabled
training_eligible
training_enabled
```

## Required independent acceptance

The twelve prospective integrated timelines in `6E_FUNDED_PATH_ACCEPTANCE_MATRIX_20261009.md` remain required, with their exact causal and accounting controls. Independent oracles must manually derive complete fixture/point/protocol/bindings/declaration/result bytes, all native chains, record/receipt heads, budget snapshots and crossed-price fees without calling the new builder's private helpers, adopting its result, or composing complete old roundtrip plans. Cover both time/bracket exits and both sides, inclusive endpoints, hold equality, first-cursor suffix exclusion, multi-timer gaps, fresh ordinal effects, denial/undetermined recomputation and negative cash owned exits.

Pending-entry priority is defensive but a positive publication disposition is unreachable under at-least-one-second cadence, 100ms readiness and quote-effects-before-publication ordering. Do not violate cadence or bypass the walk to manufacture public coverage. All other public first dispositions and outcomes need integrated complete fixtures. No historical session may be relabeled synthetic to bypass the boundary.

Future-suffix controls mutate only the future component: a quote change changes fixture/declaration/result pins but not unchanged bindings; a point change changes bindings/declaration/result pins but not an unchanged fixture. With unchanged metadata and earlier rows, earlier causal scalars, accounting prefixes and consumed-content digests stay unchanged. Full fixture-bound native witness identity may change, and changing native metadata/source pin may change its seeded rolling digest. Test these distinctions instead of demanding incorrect full-object equality.

Test malformed every-field metadata/pin syntax before poisoned numeric traversal, exact classes/subclasses/bools, counts/cadence/synthetic labels, missing-versus-zero margin, all nullability/range/ID/flags/body shapes, complete-cap exact/excess behavior, money/timer overflow and whole-plan refusal. Retain full 128 quotes, four publications and twenty records at capacity; no successful subset, daily reset, reseed, continuation or partial result. Complete source/test review, Ruff/new-file formatting, root adjacent tests and a complete frozen-source suite with every ordinal case/skip/process/source pin reconciled remain release requirements, not already-passing evidence for this proposed component.

Later historical/calendar/multi-session support, authenticated features, broker economics, live/paper execution, storage/resume and model learning need separately reviewed implementation and fresh explicit complete-cohort registration. This contract grants none of those authorities.
