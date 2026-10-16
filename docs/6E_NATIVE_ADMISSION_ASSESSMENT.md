# Native quote and declared funding assessments

This accepted contract is for a separate pure synthetic assessment bridge. Implementation, independent source/test review, 221 focused cases and root's 1,224 adjacent cases pass. Complete project suite 3 is fully verified: 6,330 passed, three expected skips and zero failures/errors, with unchanged source/test pins. It pairs the held native-prefix witness with reconstructed hypothetical admission accounting. It does not append an accounting record, generate a fill, select a strategy or authorize trading.

The first assessment explains affordability at an original first-quote publication. The second checks supplied quote coverage at the original deadline of a reconstructed pending entry or PENDING exit. Both retain independently supplied expectations; neither accepts a submitted publication or closure certificate as authority.

## Complete independently retained inputs

The proposed module is `ai_trader.research.six_e_native_admission_assessment`. It may use standard-library modules plus the held native-prefix, admission and budget modules. Do not change those held implementations or introduce a historical loader, CLI, I/O, persistence, resume, account, model, policy, execution or order hook.

Both APIs require one exact `NativeFixture`, one exact `DeclaredAdmissionGenesis`, the complete immutable tuple of preceding constructed `DeclaredRecord` objects, an externally retained complete fixture SHA256, an externally retained original genesis SHA256, an exact retained `NativePrefix` and an exact retained `DeclaredPrefix`. They revalidate and reconstruct, rather than trusting frozen objects or caller caches. No function takes a replacement cash balance, derived deadline certificate or reusable prepared authority object.

Before inspecting quote or record prices, refuse non-exact top-level types, malformed retained pin syntax, non-immutable or oversized record tuples and a missing or invalid `synthetic-` label on both fixture session and genesis scenario. Synthetic labels are exact ASCII identifiers of at most 64 characters with a nonempty suffix, using the held native identifier syntax. They do not authenticate invented origin. Validate scalar retained-prefix schemas before deep content reconstruction. Complete admitted accounting reconstruction and native reconstruction must both match their original external expectations.

Preflight also requires exact immutable fixture quote/publication tuples within the held 1,024/64 limits before either deep reconstruction. After exact scalar prefix validation, require `expected_accounting_prefix.sequence == len(records) <= 128`, `expected_native_prefix.total_quotes == len(fixture.quotes)`, `expected_native_prefix.total_publications == len(fixture.publications)` and `expected_native_prefix.consumed_count <= len(fixture.quotes)`. The retained native fixture pin and declared session/contract/source/window fields must exactly match the separate fixture pin and metadata. No changed expectation is adopted to satisfy these checks.

Both contexts retain the held supported contracts: `6EM5`, `6EU5`, `6EZ5`, `6EH6`. Refuse other fixture contract labels during preflight; the native module's broader label syntax does not expand admission compatibility. The deadline branch additionally checks the reconstructed liability's exact original contract.

The new local accounting cap is 128 complete preceding records, narrower than the held reducer's 2,000-record limit. Keep the held native bounds of 1,024 quotes, 64 publications and 256 KiB canonical input. Never slice an excessive tuple or replace its retained terminal with a successful prefix. Validate resource counts before traversing records. The canonical link envelope has a separate 256 KiB bound. A bound failure is an error, never a partial result.

## First publication affordability

```python
assess_publication_budget(
    fixture, genesis, records, *,
    expected_fixture_sha256, expected_native_prefix,
    expected_genesis_sha256, expected_accounting_prefix,
    publication_id,
) -> NativeBudgetAssessment
```

Reconstruct the complete constructed accounting state. Regenerate the original OPEN publication through `native.publication_witness` with the retained native prefix and original publication ID. Its consumed count must be precisely the first cursor plus one; an already consumed equal-time suffix refuses.

Build the held `DeclaredCapitalSnapshot` from that reconstructed state and original genesis. Build its one-contract `EntryProposal` at the regenerated publication's time, contract and exact accounting sequence/head. Run the existing budget assessor with the bound economics and limits. Never set the accounting frontier to the publication time merely to make a stale snapshot fresh. Future accounting frontiers refuse; age equality, cash equality, loss equality, missing margin and typed liabilities keep the held semantics.

Return the regenerated publication, reconstructed state, held budget decision and a canonical link digest binding the complete paired contexts. The result explains hypothetical next-entry affordability only. There is no side selection, admission ID, pending creation, fee charge, debit or reservation; original strategy selection and across-call continuity remain unverified. An available declared budget is not admission approval.

## Pending deadline coverage

```python
assess_pending_deadline_boundary(
    fixture, genesis, records, *,
    expected_fixture_sha256, expected_native_prefix,
    expected_genesis_sha256, expected_accounting_prefix,
    expected_deadline_ns,
) -> NativeDeadlineAssessment
```

Reconstruct the accounting state before choosing a boundary. Only `ENTRY_PENDING` or an original exit whose status is `PENDING` supplies a request identity, dated contract, ready time and deadline. FLAT, OPEN without a pending exit and terminal EXIT_UNKNOWN refuse. Derive those values from the reconstructed liability, not a certificate or caller's replacement request.

The prospectively retained `expected_deadline_ns` must be an exact bounded integer equal to that original derived deadline. The fixture's contract must match. Require `fixture.start_ns <= ready_at_ns <= deadline_ns < fixture.end_ns`: the entire inclusive eligible execution interval must lie inside the declared quote interval. A deadline exactly at excluded `end_ns` refuses rather than claiming that no deadline row exists.

Regenerate `native.close_through` at the derived deadline. A still-unconsumed quote at or before it refuses, including every equal-time suffix. A previously consumed later quote also refuses. The exact next strictly later timestamp/cursor may prove supplied boundary coverage, but its prices are not exposed or consumed. Complete pinned EOF may prove supplied coverage inside the declared interval, not wall-clock passage or real market completeness.

Return the reconstructed state, original liability kind/identity/contract/ready/deadline, regenerated boundary and canonical link digest. Closure does not prove that no eligible fill exists, that execution rules were followed, that real time elapsed or that timeout/UNKNOWN is authorized. No outcome is stamped and no valid declared receipt is suppressed.

## Immutable linked results

Define frozen slotted result dataclasses and a dedicated `NativeAdmissionAssessmentError(ValueError)`. Reject integer, string, tuple and dataclass subclasses and deliberately poisoned inputs at consuming boundaries. Preserve normal held refusals as assessment errors; do not silently repair a context or broaden an interval.

The closed protocol constants are `VERSION = "six_e_native_admission_assessment_v1"`, `MAX_ACCOUNTING_RECORDS = 128`, `MAX_LINK_BYTES = 256 * 1024`, `BUDGET_STATUS = "constructed_native_budget_assessment_not_authenticated"` and `DEADLINE_STATUS = "constructed_native_deadline_assessment_not_authenticated"`.

The exact ordered dataclass fields are:

- `NativeBudgetAssessment`: `version`, `status`, `fixture_sha256`, `genesis_sha256`, `native_prefix`, `accounting_state`, `publication`, `budget_decision`, `link_sha256`, `authority_flags`.
- `NativeDeadlineAssessment`: `version`, `status`, `fixture_sha256`, `genesis_sha256`, `native_prefix`, `accounting_state`, `liability_kind`, `liability_id`, `contract`, `ready_at_ns`, `deadline_ns`, `boundary`, `link_sha256`, `authority_flags`.

`liability_kind` is exactly `"entry"` or `"exit"`. Its ID is respectively the original pending admission ID or original PENDING exit request ID. Native prefix and publication/boundary use the held native types; accounting state and budget decision use the held admission/budget types. Fixture and genesis pins are the externally retained expectations, not new replacements. The accounting prefix is explicitly included as `accounting_state.prefix`, and the native prefix is included both directly and inside the regenerated witness.

The exact canonical digest body is the complete `dataclasses.asdict(result)` object with only the `link_sha256` key removed. No other envelope key, inferred omission or source-file digest is added. JSON serialization uses `ensure_ascii=True`, `sort_keys=True`, `separators=(",", ":")`, `allow_nan=False`, then UTF-8 encoding and SHA256. Check `MAX_LINK_BYTES` before hashing. An internal well-formed placeholder digest may be replaced purely after calculating the closed body; it supplies no input expectation or authority.

Each result has a version, an assessment-only status, regenerated context, a canonical link SHA256 and the exact immutable false authority tuple. Its digest includes version, original fixture/genesis pins, complete paired prefixes and the complete returned assessment context with every false flag; omit only the digest's own field. Use closed schemas with canonical UTF-8 JSON, sorted keys, compact separators and no non-finite values. Output hash/total counts are integrity metadata, not policy features or authenticated cash.

Combine the held authority flags with explicit false native-accounting-history, original-strategy-selection, timer-elapsed, timeout and accounting-transition authorities. Existing accounting receipts are still constructed and not linked to native history. All source, feed, genesis, prefix, receipt, account, cash, margin, risk, execution, storage, resume, trading, training, scoring, independent-validation and promotion authorities remain false. Return the held state and its liabilities unchanged, including zero-valued commitments and null complete equity/return. Do not double-charge fees or the old round-trip tick.

`AUTHORITY_FLAGS` is the ordinal-name-sorted tuple merging every held native and admission authority name with these exact additional false names: `native_accounting_history_verified`, `original_strategy_selection_verified`, `timer_elapsed_verified`, `timeout_authorized`, `accounting_transition_authorized`, `cross_call_continuity_authenticated`, `absence_of_eligible_fill_verified` and `complete_decision_quote_audit_verified`. Every value is the exact Boolean `False`; never confuse an ordinary hypothetical budget-condition Boolean with an authority flag.

No current API accepts a returned result as authority. A future consumer must regenerate it from independently retained original fixture/genesis/prefix/publication/deadline expectations and compare every exact canonical field. Repeated pure calls are reproducible, not persisted progression, global exactly-once consumption or authenticated continuity. A caller that deliberately replaces its entire coherent declaration and expectations cannot be detected here.

## Acceptance and remaining integration

Require independent contract/source/test review, a complete constructed adversarial suite, focused tests with adjacent held accounting/native tests, whole `src`/`tests` Ruff, new-file formatting and a complete source-frozen project suite. Test strict types, complete pin and prefix drift, omitted/reordered inputs, both synthetic guards before price access, exact 128/129 accounting bounds, first-cursor OPEN behavior, future/stale/equality snapshots, missing/zero margin, liabilities and fee conservation. Compare the budget result with an independently built held-assessor control.

Deadline cases must cover entry and exit identities, contract mismatch, exact retained deadline, one-nanosecond readiness/end boundaries, equal-time suffixes, later consumed rows, next-timestamp and complete-EOF closure, source/prefix corruption and terminal UNKNOWN including zero commitments. Independent canonical result-link controls and forbidden I/O/process/network hooks must pass. A bounded synthetic performance check must cover the complete maximum accounting and native inputs without truncation.

Complete prior-record/native linkage, one-genesis event advancement, original policy recomputation over the newly funded path, denial ID/cooldown rules, receipt/fill/timer enforcement and every-decision/quote audit remain later work. Historical use additionally needs a separately reviewed implementation and fresh prospective complete-cohort registration. The old controls, sources, targets, results and UNKNOWN exit stay unchanged.

## Invented in-memory example

Root executed this example once successfully before complete suite 3; do not duplicate it merely to report progress. Its result status was `constructed_native_budget_assessment_not_authenticated`, link SHA256 `bca2c0ff16989755b91539bd3c7d418402687843f9b570593d016e6e68849938`. It creates one invented quote and a hypothetical USD declaration entirely in memory; it reads no input files, calls no model and creates no pending entry. Its tiny monetary values are toy arithmetic, not a broker recommendation. A locally generated pin is suitable for this example but is not independently authenticated market or account evidence.

```python
from ai_trader.research import six_e_declared_admission as admission
from ai_trader.research import six_e_declared_economics as economics
from ai_trader.research import six_e_entry_budget as budget
from ai_trader.research import six_e_native_prefix as native
from ai_trader.research import six_e_native_admission_assessment as assessment

start = 1_000_000_000_000
fixture = native.NativeFixture(
    "synthetic-guide", "6EM5", "1" * 64, start, start + 10_000_000_000,
    (native.NativeQuote(start, 1_000_000_000, 1_000_050_000),),
    (native.NativePublication("publication-1", 0, start),),
)
fixture_pin = native.fixture_sha256(fixture)
empty_native = native.initial_prefix(fixture, expected_fixture_sha256=fixture_pin)
observed = native.consume_next(
    fixture, expected_fixture_sha256=fixture_pin,
    expected_prefix=empty_native, expected_cursor=0,
).prefix
genesis = admission.DeclaredAdmissionGenesis(
    "synthetic-guide", economics.EconomicSeed(135, start),
    economics.DeclaredEconomics("USD", 125, 10, 20, economics.DeclaredMargin(100, 80)),
    budget.DeclaredBudgetLimits(5, 1_000_000_000, None),
)
genesis_pin = admission.genesis_sha256(genesis)
accounting = admission.DeclaredPrefix(0, genesis_pin, start)
result = assessment.assess_publication_budget(
    fixture, genesis, (), expected_fixture_sha256=fixture_pin,
    expected_native_prefix=observed, expected_genesis_sha256=genesis_pin,
    expected_accounting_prefix=accounting, publication_id="publication-1",
)
assert result.budget_decision.disposition == "declared_budget_available"
assert result.accounting_state.prefix == accounting
assert result.accounting_state.phase == "FLAT"
assert result.accounting_state.pending_entry is None
assert all(value is False for _, value in result.authority_flags)
print(result.status, result.link_sha256)
```

Do not treat the printed available-budget disposition as permission to enter. There is no state advancement, replay, strategy selection, account connection or historical validation in this example.
