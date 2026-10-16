# Synthetic capital-aware path simulator

## Current status

The simulator is fully accepted on constructed data. The closed implementation contract, source and independent tests passed complete static review. All 618 new tests and 2,888 adjacent component tests passed, followed by whole-project Ruff and new-file formatting checks. The complete project suite was fully verified at 09:59:26 UTC on 10 October 2026: **7,994 passed, three expected skips and zero failures/errors**, with every old/new case identity, process exit and unchanged source pins checked. This is not permission to run historical data, train a model or trade.

See `6E_FUNDED_PATH_DEVELOPMENT_WINDOW_20261010.md` for current acceptance evidence and the fixed stop time. The normative schemas and rules are in `6E_SYNTHETIC_FUNDED_PATH_CONTRACT_20261010.md`; this short guide explains their purpose, not a replacement contract.

## What this component answers

The simulator asks a narrow question: given invented quotes, invented feature points and explicit hypothetical fees, margin and capital, what complete sequence of decisions follows from one starting balance?

It recomputes a decision when each original feature publication becomes visible. It does not first generate a finished trade list and remove trades that would have been unaffordable. Fees, realized gains/losses and unresolved positions carry forward. That distinction matters because rejecting one entry can change later decisions.

The complete result covers every supplied quote through its quote audit and complete fixture identity; original quote prices remain in the separately supplied fixture. It retains every publication, denied or undetermined candidate, constructed execution outcome, accounting record and terminal liability. It must refuse an incomplete or excessive result rather than return the successful portion.

## Inputs and outputs

| Input | Meaning | Not established |
| --- | --- | --- |
| One synthetic native fixture | Complete invented quote ordering and original publication cursors | A captured market feed or broker fill |
| One declared genesis | One starting balance and unchanged USD futures assumptions | A real funded account, margin observation or risk approval |
| One binding for each publication | Invented 37-value feature point, asserted eligibility and retained point identity | Authentic feature provenance or historical eligibility |
| One fixed declaration | One scalar policy and one exit plan for the whole fixture | Policy optimization or a profitable strategy |
| Original retained context hashes | Local identity checks for the complete supplied objects | Authentication against a coherent replacement of all inputs and expectations |

The output retains all four fixed directions (`cvd_follow`, `liquidity_follow`, `absorption_fade`, `no_trade`) even when an entry is blocked. One declared policy is selected before the walk; there is no vote, best-policy selection or model call.

The bounded component accepts one to four publications, at least one second apart, up to 128 complete quotes and 20 accounting records. It is not multi-session storage or an autonomous runner. The supplied full-contract crossing price is an explicit assumption; no size, depth, queue, venue or broker execution evidence exists.

## Decision sequence

At a publication, quote effects that were already due are processed first. The decision then checks eligibility, existing inventory, pending entry, cooldown and signal, in that order. Only an eligible, unblocked nonzero signal consumes a candidate ordinal and requests a capital assessment from its complete post-clock accounting prefix.

Denied and undetermined candidates remain in the history. They do not charge a fee, reserve an entry or create a cooldown. An admitted candidate uses the first eligible quote; a widened first entry spread refuses the entry permanently rather than waiting for a favorable quote. Owned exits retain widening and are not blocked by a new entry-budget or loss-limit check.

Inclusive execution deadlines and strict-left hold boundaries prevent a later quote from being treated as earlier evidence. The feature publication occurs at its original first cursor, before any equal-time suffix. Hold equality wins before its quote. These rules are fixed, not chosen after observing outcomes.

An exit that cannot be resolved within its original interval becomes `EXIT_UNKNOWN`. It remains inventory, including when the monetary commitments are zero. Later favorable quotes or signals do not cancel it, fill it late or add accounting events. Complete equity and return remain null. Auditing later supplied quotes and publications continues.

## Reading a result

- `publication_audit` shows every original decision, its four directions, immutable first disposition and before/after accounting prefixes.
- `candidates` separates the original admission disposition from later entry and exit outcomes. Each candidate owns its complete contiguous record range.
- `records` and `record_links` bind every accounting transition to its original publication, quote or closed boundary.
- `quote_audit` and the terminal native prefix cover every supplied quote.
- `terminal_accounting_state` carries the original-seed balance, exactly-once fees, reserves, receipt identities and any unresolved liability. Its accounting time is not automatically advanced to quote EOF.
- Every authority flag is false. A matching complete result hash establishes local reconstruction consistency, not trading, training or promotion authority.

The `no_trade` control can finish flat with zero return. That is an accounting control, not a trading edge. Positive invented gross/net arithmetic is not historical profitability, independent validation, EURUSD CFD execution economics or an improved AI model.

## Small invented example

Root executed this PowerShell example once after focused acceptance at 08:45:30 UTC on 10 October 2026. It rebuilt the complete in-memory idle result successfully: flat, zero records/return, one quote/publication audit and all 57 authority flags false. Its plan SHA256 was `7e84d9f84d129c63d35afedc1fc61c2fe2e211162554d2c175ae89fb84ab51e2`. It reads no capture/archive, writes no account or result file, and invokes no model, training or trade. Its prospective hashes identify these new toy inputs; they must not replace separately retained expectations for an old experiment. The USD values are invented assumptions, not measured broker economics.

```powershell
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath 'C:\Users\pabta\Projects\ai-trader'
$fundedIdleExample = @'
import json
from ai_trader.research import six_e_declared_admission as admission
from ai_trader.research import six_e_entry_budget as budget
from ai_trader.research import six_e_native_prefix as native
from ai_trader.research import six_e_synthetic_funded_path as funded
from ai_trader.research import six_e_synthetic_liquidity_point as point

fixture = native.NativeFixture(
    "synthetic-idle-example", "6EM5", "1" * 64, 0, 60_000_000_000,
    (native.NativeQuote(1_000_000_000, 1_100_000_000, 1_100_050_000),),
    (native.NativePublication("idle-publication", 0, 1_000_000_000),),
)
genesis = admission.DeclaredAdmissionGenesis(
    "synthetic-idle-example",
    admission.EconomicSeed(1_000_000_000, 0),
    admission.DeclaredEconomics("USD", 1_000_000, 0, 0, None),
    budget.DeclaredBudgetLimits(0, 0, None),
)
feature_point = point.SyntheticLiquidityPoint("synthetic-idle-point", (0,) * 37)
bindings = (funded.PublishedLiquidityBinding(
    "idle-publication", True, feature_point, point.point_sha256(feature_point)
),)
declaration = funded.FundedPathDeclaration("synthetic-idle-declaration", "no_trade", "time_exit")
fixture_pin = native.fixture_sha256(fixture)
genesis_pin = admission.genesis_sha256(genesis)
bindings_pin = funded.bindings_sha256(bindings)
context = {
    "expected_protocol_sha256": funded.protocol_sha256(),
    "expected_fixture_sha256": fixture_pin,
    "expected_genesis_sha256": genesis_pin,
    "expected_bindings_sha256": bindings_pin,
    "expected_declaration_sha256": funded.declaration_sha256(
        declaration, fixture_sha256=fixture_pin,
        genesis_sha256=genesis_pin, bindings_sha256=bindings_pin,
    ),
}
plan = funded.build_funded_path_plan(fixture, genesis, bindings, declaration, **context)
rebuilt = funded.verify_funded_path_plan(
    fixture, genesis, bindings, declaration,
    expected_plan_sha256=plan.plan_sha256, **context,
)
assert rebuilt == plan
assert len(plan.quote_audit) == 1 and len(plan.publication_audit) == 1
assert not plan.candidates and not plan.records
assert plan.terminal_accounting_state.phase == "FLAT"
assert plan.terminal_accounting_state.complete_declared_net_return_usd_micros == 0
assert len(plan.authority_flags) == 57 and all(flag is False for _, flag in plan.authority_flags)
print(json.dumps({
    "phase": plan.terminal_accounting_state.phase,
    "accounting_records": len(plan.records),
    "quote_audits": len(plan.quote_audit),
    "net_return_usd_micros": 0,
    "all_authorities_false": True,
    "plan_sha256": plan.plan_sha256,
}, sort_keys=True))
'@
& '.\.venv\Scripts\python.exe' -B -c $fundedIdleExample
if ($LASTEXITCODE -ne 0) { throw 'Invented funded-path example failed; do not continue.' }
```

Verified behavior: flat state, zero accounting records/return, one quote audit, one publication and all 57 authority flags false. This is an idle reconstruction example, not the independent four-trade or maximum-body acceptance test. Do not rerun the completed example merely for status.

## What comes next

After complete synthetic acceptance, historical-input/calendar support and one-genesis continuity across sessions still need separately reviewed implementations and complete synthetic coverage. A later real-session experiment requires a fresh prospective registration. Those layers must preserve causal publication timing, every decision and unresolved liability without adopting old completed outcomes or filtering fills.

Broker execution assumptions, fills, fees and EURUSD spot/CFD mapping remain separate requirements. A training dataset or model promotion does not follow automatically from this simulator. The BTC and cloud collectors remain outside this work.
