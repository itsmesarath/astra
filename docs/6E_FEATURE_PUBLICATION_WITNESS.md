# Constructed feature publication witness

Current status: complete static review, all 541 new constructed tests, all 752 adjacent cases and the complete frozen-source project suite passed. At 16:31:39 UTC, complete verification accepted **8,806 passes and three expected skips**, with zero failures/errors, every old test identity preserved and every source/test/contract pin unchanged. This is constructed regression acceptance, not historical validation or permission for training.

The new component reconstructs a small invented MBO record stream from an empty order book. It records each order's actual state before an update, groups only source-closed events, and derives all 37 existing causal features at the original publication cursor. Quotes supplied by a caller are not accepted as a substitute for order events.

## What this adds

The preceding metadata gate checked complete invented reference assertions. This component computes the underlying book, flow, depth and execution proxies from invented records and binds each publication to its consumed record prefix.

| Layer | Constructed check | Still not established |
| --- | --- | --- |
| Source records | Exact target-record ordering, complete event ranges, reconstructed pre-update states | Original DBN byte offsets, decoding, instrument mapping or collection authenticity |
| Feature publication | All 37 values, original cadence and first equal-time completed cursor | Historical publication evidence or authenticated full-session feed |
| Identity | Complete input/result hashes and causal prefix/event/publication hashes | Detection of a coherent replacement of the input and all expected pins |
| Helper source | Nine fixed raw-file hashes and used numerical constants | Complete import graph or in-memory/native runtime authenticity |
| Readiness | Spread, feature warmup and original window-end buffer | A selected trade, broker fill, profit, account funding or model improvement |

The broad authority flags remain false. Correct arithmetic on invented inputs does not grant historical, execution, trading, training or promotion authority.

## Standalone constructed example

The following corrected example completed successfully after full static and focused/adjacent review. It invents a ten-unit bid and ask, three warmup completions and a six-unit buy-side T/F/decrease/replenishment event. It reads only the nine fixed helper implementation sources through the witness API. It does not open an archive, write a dataset or call a model. The initial local exit-code variable falsely reported failure inside a child script block; the explicit global native exit-code guard below fixes that scope issue and retains failed-launch diagnostics.

From PowerShell in the project directory:

```powershell
Set-Location -LiteralPath 'C:\Users\pabta\Projects\ai-trader' -ErrorAction Stop
if ((Get-Location).ProviderPath -ne 'C:\Users\pabta\Projects\ai-trader') {
    throw 'Wrong project directory.'
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe' -PathType Leaf)) {
    throw 'Project Python is missing.'
}
$taskWitnessExample = @'
import json
import math
from ai_trader.research import six_e_feature_publication_witness as w

rows = []
def record(now, action, side, price=0, size=0, order_id=0, last=False):
    rows.append(w.ConstructedMboRecord(
        record_ordinal=len(rows)+1, instrument_id=1,
        ts_recv=now, ts_event=now, ts_in_delta=0, sequence=len(rows),
        action=action, side=side, flags=128 if last else 0,
        price=price, size=size, order_id=order_id,
    ))

start = 1744027200000000000
record(start-10000000001, 'R', 'N', last=True)
record(start-10000000000, 'A', 'B', 1000000000, 10, 1)
record(start-10000000000, 'A', 'A', 1000050000, 10, 2, True)
record(start-5000000000, 'N', 'N', last=True)
record(start-1000000000, 'N', 'N', last=True)
record(start, 'T', 'B', 1000050000, 6, 99)
record(start, 'F', 'A', 1000050000, 6, 2)
record(start, 'C', 'A', 1000050000, 6, 2)
record(start, 'A', 'A', 1000050000, 6, 3, True)
fixture = w.FeatureWitnessFixture(
    fixture_id='synthetic-guide-buy', source_session='synthetic-guide-session',
    utc_date='2025-04-07', contract='6EM5', instrument_id=1,
    records=tuple(rows),
)
protocol_body = w.protocol()
assert protocol_body['scope'] == 'constructed_target_mbo_prefix_only'
assert len(protocol_body['feature_names']) == 37
protocol_pin = w.protocol_sha256()
fixture_pin = w.fixture_sha256(fixture, expected_protocol_sha256=protocol_pin)
result = w.replay(fixture, expected_fixture_sha256=fixture_pin,
                  expected_protocol_sha256=protocol_pin)
w.verify(result, fixture, expected_fixture_sha256=fixture_pin,
         expected_protocol_sha256=protocol_pin,
         expected_witness_sha256=result.witness_sha256)
assert (result.record_count, result.completed_event_count,
        result.quote_count, result.publication_count) == (9, 4, 4, 1)
pub = result.publications[0]
values = dict(pub.feature_values)
assert len(values) == 37 and pub.eligible is True
assert pub.cvd == 6 and pub.known_trade_count == 1
assert values['normalized_cvd_5s'] == 0.6
assert values['log_quote_events_5s'] == math.log1p(3)
assert values['ask_linked_decrease_5s'] == 0.3
assert values['ask_other_id_reload_5s'] == 0.3
assert all(flag is False for _, flag in result.authority_flags)
print(json.dumps({'status': result.status, 'fixture_sha256': fixture_pin,
                  'witness_sha256': result.witness_sha256,
                  'records': result.record_count, 'events': result.completed_event_count,
                  'publications': result.publication_count,
                  'all_authority_flags_false': True}, sort_keys=True))
'@
$global:LASTEXITCODE = $null
$taskWitnessOutput = & '.\.venv\Scripts\python.exe' -B -c $taskWitnessExample 2>&1
$taskWitnessExit = $global:LASTEXITCODE
if (($taskWitnessOutput | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] }) -or
    $taskWitnessExit -isnot [int] -or $taskWitnessExit -ne 0) {
    $taskWitnessOutput | Write-Output
    throw 'Constructed example failed or could not launch; diagnostics are retained above.'
}
$taskWitnessOutput
```

The demonstrated fixture pin is `90be467896023b941c5bd16905b5732f2ee48e34a3949daac585e973a6829cd2`, and witness pin is `2fa7aa0a24fe0eed0569fb52495441c65b670f54a8caa0220ee00cace8c9bf15`. These are locally calculated identities, not independent authentication. The example's few arithmetic checks do not substitute for the complete independent test suite or a historical bridge.

## Event and publication timing

Every post-genesis record belongs to exactly one event ending at its actual F_LAST record. A T record becomes visible in signed flow only when that event completes. An F record is not counted as a second trade. The book is updated from every record, and each completed event must leave a two-sided, strictly uncrossed book.

The first completed quote at or after a due publication time is published immediately. A later equal-time event can affect later helper state, but cannot alter that earlier publication. A completion skipped by the one-second cadence still updates all helpers and retains its event witness. There is no timer-only, standing-quote or EOF publication.

The exact five-second boundaries matter. Rolling observations at the cutoff remain; inactivity resets only when the gap is greater than five seconds. A non-completing incoming record can fire the inactivity timer and reset OFI; quote history resets at the next completed quote. Signed flow expires through its own window, and the actual prior quote gap is retained. An event spanning more than five seconds is excluded from execution metrics, but its completed T records still enter signed flow. These are original helper semantics, not a new trading rule.

A one-quote history has an empty travel sum. The held helper represents that one value as integer zero; the witness promotes only that exact zero to `0.0` to meet its float transport contract. It does not scale, round or change any feature calculation. Every existing float, including signed zero, is retained unchanged; other non-float values are refused.

## Complete verification

The API has five calls: `protocol`, `protocol_sha256`, `fixture_sha256`, `replay` and `verify`. There is no CLI, loader, account hook or storage/resume interface.

Fixture calls first validate every supplied expected pin and the fixed helper sources, then validate metadata for every record before reading any price, size or order ID. Numerical payloads and the entire input pin are checked before reconstruction. A bad later record refuses the entire fixture; no successful prefix is returned.

`verify` independently rebuilds from the original fixture. It does not adopt the submitted order states, quotes, features, event boundaries or digests. Acceptance requires exact nested types, complete canonical bodies, every identity and every false flag to match. The result retains the full original fixture, all record audits, all completed events, every publication's 37 values, complete helper audit and terminal counts.

Whole-input and whole-result hashes change when a suffix changes. Earlier consumed-prefix, event and publication hashes must remain unchanged under identical context/helpers and identical consumed records. The causal seed deliberately excludes total counts and the whole-input hash.

## Boundaries and next gate

This invented component is limited to 256 records, 128 completed events and 32 publications, with a 1 MiB complete canonical input/result cap. It uses one fixed calendar-valid example date and contract; it does not verify their real-world mapping. Never thin, split or relabel historical data to fit these bounds.

A historical bridge still needs original decoded MBO inputs, authentic mapping/calendar and complete session scope, source-bound event/publication evidence, parity with the original feature rows, and one-genesis multi-session continuity where applicable. Timestamp/bid/ask columns alone cannot reconstruct CVD, order replenishment, depth or absorption. A separately reviewed implementation and fresh prospective registration must precede any historical experiment.

No training, trading, downloads or BTC/cloud collector changes are part of this component. See `6E_FEATURE_PROVENANCE_WINDOW_20261010.md` for the current authorized window and acceptance evidence.
