# Declared admission packet boundary

The separate pure codec is implemented, independently reviewed and fully verified. It passed 219 constructed cases, including a complete valid 2,000-record round trip; root's adjacent run passed 587 cases with no skips. Ruff, formatting and the exact standalone example passed. Complete-project suite 7 passed 5,693 tests with three expected skips; root reconciled the full JUnit, process exit and unchanged source/test pins. No persistence, restart, history or trading integration is implemented.

The purpose is lossless in-memory transport of an entire constructed declaration for future independent operation. It is not a checkpoint file, persistent account, automatic restart, resumed trader, historical-data adapter or model input. The existing core, its tests and every old result remain unchanged.

The final expanded project suite 8 also passed 5,804 tests and three expected skips after the read-only checker was added. Complete case, process-exit and unchanged-source verification is recorded in `docs/6E_ADMISSION_DEVELOPMENT_WINDOW_20261008.md`; the packet source/tests stayed held throughout.

## Pure interface

The separate `six_e_declared_admission_packet.py` module has two functions:

```python
raw = encode_packet(
    genesis, complete_records,
    expected_genesis_sha256=retained_genesis_pin,
    expected_terminal=retained_terminal_prefix,
)
decoded = decode_packet(
    raw, expected_packet_sha256=retained_raw_pin,
    expected_genesis_sha256=retained_genesis_pin,
    expected_terminal=retained_terminal_prefix,
)
```

All three expectations are independently supplied by the caller. Embedded witnesses must match them, never define them. A caller who invents an entire coherent declaration and replaces every expectation can still produce a valid local packet; no account, funding or receipt authenticity follows.

Encoding verifies the complete typed tuple through the held admission core before producing bytes. Decoding requires exact `bytes`, checks its size and externally retained raw SHA256 before UTF-8 decoding or JSON parsing, verifies strict schema and witnesses, rebuilds exact typed inputs and calls the same core reconstruction. It requires byte-perfect canonical re-encoding.

The immutable decoded result may expose original typed genesis, complete tuple, matching genesis/terminal witnesses and a freshly reconstructed state. No cached state is serialized or accepted as an input. There is no load/save command, filesystem access, lock, storage path, resume process, broker, model, quote or strategy call.

## Closed wire contract

Top-level fields are exactly `version`, `scope`, `core_version`, `genesis`, `expected_genesis_sha256`, `expected_terminal` and `records`. Header values are fixed to the packet protocol, unauthenticated constructed scope and held admission-core version.

Genesis and nested seed, economics, margin and limits use the held exact fields. Missing margin and loss ceiling are explicit JSON null, not omitted keys or zero defaults. Each prefix has exactly sequence, head and completeness frontier. A record has the five held envelope fields plus a `kind` tag; its payload is an exact dictionary for one of the seven explicit held payload types. Unknown kinds, extra or missing keys, cached cash, liabilities and authority fields are refused rather than ignored.

The case-sensitive wire tags are `AdmissionRequested`, `EntryReceipt`, `EntryUnfilled`, `ExitRequested`, `ExitReceipt`, `ExitUnknown` and `ClockAdvanced`. The decoded `DeclaredAdmissionPacket` contains typed genesis, the complete immutable record tuple, matching expected genesis/terminal witnesses, `reconstructed_state` and all-false `authority_flags`. `PacketError` is the controlled refusal type. Manually constructing an object does not authenticate it; encoding accepts only the typed genesis/records and independent witnesses, not a decoded result or cached state.

Canonical encoding is sorted-key, compact, ASCII JSON with no BOM, newline, trailing content, nonfinite values or alternate numeric representations. Duplicate keys are refused at every object depth, including escaped aliases. Integers remain exact bounded integers: no Boolean coercion, float, exponent, NaN, infinity or accepted negative-zero spelling.

## Resource contract

The reviewed independent packet cap is 4 MiB, applied before raw hashing. A quote/escape-aware pre-parse scan caps nesting at eight and counts at most 100,000 structural markers outside strings (`{`, `}`, `[`, `]`, `,`, `:`). This is a marker budget, not a claim to count every JSON node. Integer tokens have at most 19 decimal digits excluding an optional minus sign; lexical magnitude checks enforce the held bound from `-(2**63 - 1)` through `2**63 - 1` before conversion, followed by field-specific constraints. Parser/resource/type errors become controlled packet errors, never repairs or retries.

Independent read-only schema arithmetic places a maximal entry-receipt wire record below 1 KiB, a 2,000-record packet below roughly 2 MiB, its outside-string markers below 72,100 and valid nesting at depth four. The reviewed caps therefore leave room for the current closed schema. This is design review, not implementation or a promise to accept arbitrary JSON up to those limits. Private boundary tests must be distinguished from valid public packets.

The held core's 2,000-record and 8 KiB canonical-record guards remain unchanged. This is a complete tuple, not a successful subset or an incremental account reset. An oversized transport is refused; it is not segmented or truncated to fit.

## Synthetic acceptance

Use only constructed small tapes, including all seven payload kinds and five phases, all-zero commitments, explicit refusals, UNKNOWN carry and negative cash. Verify lossless canonical round trips and re-encoding; raw-pin failure before parser/core calls; independently retained witness mismatches; omitted/reordered/changed records; duplicate/unknown nested keys; extra cached state; unsupported tags/types; UTF-8/BOM/escaping/order/whitespace variants; numeric ambiguity; and byte/depth/marker/integer/count boundaries. Avoid quadratic construction of thousands of transitions merely to test a resource refusal.

Purity tests must forbid filesystem, source-file hashing, network, history, policy, model and storage/resume hooks. Every source/genesis/prefix/receipt/account/cash/margin/risk/trading/training/scoring/independent-validation/promotion authority remains false. A raw hash verifies consistency with a supplied byte pin, not external provenance.

Actual persistence, source-version verification, safe paths, durable claims, externally retained pins and restart semantics are later integration work. A funded historical experiment additionally needs its own causal complete-cohort contract and fresh registration before outcomes. This packet cannot reinterpret old controls, manufacture a late fill or release UNKNOWN.

## Constructed in-memory example

Root parsed and executed this exact PowerShell block successfully using its invented values. It creates an OPEN declaration, transports the complete records in memory and reconstructs the same open liability. It writes no checkpoint or output file and starts no order, model, strategy or historical process. The retained pins are supplied separately, not trusted because they appear inside the packet. These locally generated expectations are consistency witnesses only. This small example does not replace focused or complete-project acceptance tests.

```powershell
Set-Location -LiteralPath 'C:\Users\pabta\Projects\ai-trader' -ErrorAction Stop
@'
import hashlib
from ai_trader.research import six_e_declared_admission as a
from ai_trader.research import six_e_declared_admission_packet as p
from ai_trader.research.six_e_declared_economics import (
    EconomicSeed, DeclaredEconomics, DeclaredMargin,
)
from ai_trader.research.six_e_bracket_targets import TICK

start = 1_000_000_000
genesis = a.DeclaredAdmissionGenesis(
    "constructed-packet-example",
    EconomicSeed(100_000_000, start),
    DeclaredEconomics(
        "USD", 1_000_000, 100_000, 100_000,
        DeclaredMargin(10_000_000, 5_000_000),
    ),
    a.DeclaredBudgetLimits(1_000_000, 1_000_000_000, None),
)
genesis_pin = a.genesis_sha256(genesis)
records = ()
state = a.reconstruct(
    genesis, records, expected_genesis_sha256=genesis_pin,
    expected_terminal=a.DeclaredPrefix(0, genesis_pin, start),
)
entry_at = start + 100_000_000
steps = (
    ("request", start, a.AdmissionRequested("admission", "6EM5", "long", 1)),
    ("receipt", entry_at, a.EntryReceipt(
        "admission", "entry", "6EM5", "long", 1, 20_000 * TICK, entry_at,
    )),
)
for event_id, at, payload in steps:
    result = a.advance(
        genesis, records, a.DeclaredRecord(event_id, state.prefix, at, at, payload),
        expected_genesis_sha256=genesis_pin, expected_terminal=state.prefix,
    )
    records, state = result.records, result.state

terminal_witness = state.prefix
raw = p.encode_packet(
    genesis, records, expected_genesis_sha256=genesis_pin,
    expected_terminal=terminal_witness,
)
raw_pin = hashlib.sha256(raw).hexdigest()
decoded = p.decode_packet(
    raw, expected_packet_sha256=raw_pin,
    expected_genesis_sha256=genesis_pin, expected_terminal=terminal_witness,
)
assert decoded.records == records
assert decoded.reconstructed_state == state
assert p.encode_packet(
    decoded.genesis, decoded.records,
    expected_genesis_sha256=genesis_pin, expected_terminal=terminal_witness,
) == raw
assert state.phase == "OPEN"
assert state.total_commitments_usd_micros == 10_100_000
assert state.complete_declared_net_return_usd_micros is None
assert all(value is False for _, value in decoded.authority_flags)
assert all(value is False for _, value in state.authority_flags)
print(state.phase)
print(f"Declared balance (USD): {state.declared_realization_balance_usd_micros / 1_000_000:.2f}")
print("Complete net return:", state.complete_declared_net_return_usd_micros)
print("All authority flags false:", all(value is False for _, value in decoded.authority_flags))
'@ | .\.venv\Scripts\python.exe -
if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Constructed packet example failed or did not launch; do not continue.' }
```

Expected output is `OPEN`, declared balance `99.90`, complete net return `None`, and all authority flags false `True`. The ten-cent entry fee is charged once; hypothetical margin plus the remaining exit fee remain committed. No closed return or profitability follows from this open position.
