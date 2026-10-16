# Constructed decoded cursor metadata

The gate distinguishes the position of every declared decoded object from the occurrence number of a mapped target instrument. Implementation, complete independent static review and source-frozen regression acceptance are finished: **9,395 passed and three expected skips**, with every old case identity, exactly the 589 new cases and all source/contract hashes verified. The 589 focused and 1,212 adjacent cases, whole Ruff and new-pair formatting also passed. This is constructed metadata-component acceptance, not native decoding or historical strategy validation. See the current handoff for the complete report and retained pins.

The original streaming engine counts a target transition only after applying it to the book. This metadata-only gate cannot do that. It reports `target_candidate_ordinal` instead, and never labels a candidate an accepted transition, completed event or feature publication.

## Complete positions and mapping

Position 1 includes the single declared metadata header. Each later position is an MBO assertion. Every foreign-instrument item remains in the complete ordered input and hash chain; only mapped target occurrences receive consecutive candidate ordinals. Repeated payload assertions are retained, not treated as duplicate-message evidence.

The header fixes one invented UTC day, requested parent and dated contract. Exactly one requested mapping interval must cover that day using an end-exclusive boundary. A target instrument ID other than 1 is supported. Unrelated mappings remain present, while all declarations meet the new bounded ASCII transport rules. These rules are deliberately narrower than the inspected original loader; they are not a claim of full native-loader parity.

| Identity | Constructed meaning | Not established |
| --- | --- | --- |
| Decoded position | One-based occurrence including header and foreign assertions | Byte offset or authenticated decoder yield |
| Target candidate ordinal | One-based mapped occurrence | Successful book application or native accepted-target counter |
| Consumed prefix hash | Header/context plus every declared item through that cursor | Feature/event closure or original first publication |
| Complete fixture hash | Every declared item, count and member assertion | Original member bytes, EOF or source authenticity |

## Opaque assertions and causal identity

There is no record body, timestamp, flag, action, side, order ID, price or size. Payload and member SHA256 values are opaque caller assertions, not recomputed native record hashes. The declared header is a closed constructed subset, not a complete native Metadata projection: native version, stype_in/stype_out, partial, limit and ts_out assertions are not fields here. The gate therefore performs no timer, book, flow, F_LAST or numerical feature operation. Passing it cannot make a foreign poison test, historical replay or profitable strategy claim true.

The complete fixture identity includes the asserted member pin and all items. The consumed-prefix seed excludes that future complete-member assertion, total count, whole-input pin and terminal summaries. With identical context and consumed items, changing a future suffix changes complete identity while leaving earlier prefixes unchanged. Changing a foreign item before the cursor changes prefix identity even if target candidates are unchanged.

## Interface and limits

The five in-memory APIs are `protocol`, `protocol_sha256`, `fixture_sha256`, `assess` and `verify`. Complete validation rejects a bad suffix rather than returning a successful prefix. Verification rebuilds every audit, count, mapping and digest from the original complete fixture; it never adopts a submitted summary. Exact types and every false-authority flag are checked as well as canonical bodies.

Fixtures contain 2 through 128 complete items, up to eight mapping groups and 32 total intervals. Each complete canonical fixture/result body has a defensive 65,536-byte cap. Independent tests exercise the shared byte guard with literal boundary JSON; those arbitrary bodies are not valid public fixtures or a proof that all legal fixture envelopes attain the maximum. Never truncate, thin, split or relabel real history to fit constructed limits.

The module has no file reader/writer, native or project-helper import, CLI, history, account, model, order or resume hook. All 26 authorities remain false, including native decoding/EOF, successful target transitions, mapping/calendar/source/runtime authentication, feature/publication proof and trading/training/promotion. A coherent replacement of the entire caller fixture and expected pins is not authenticated or detectable.

## Next bridge gates

Actual native decoding, dated mapping/calendar, reconstructed target state, full native event/T prefix, original protected execution-capture scope and first equal-time publication still require a separate reviewed adapter. Complete source EOF is distinct from causal prefix identity. Whole-session capacity and one-genesis multi-session continuity need their own evidence and fresh prospective registration before any historical experiment.

See `6E_NATIVE_CURSOR_METADATA_CONTRACT_20261011.md` for the closed schema and `6E_NATIVE_CURSOR_DEVELOPMENT_WINDOW_20261011.md` for the owned run and verified acceptance. Existing historical inputs, results, UNKNOWN liabilities and BTC/cloud collectors remain unchanged.

## Invented example

Root executed this sole invented example once before the full-suite freeze and rebuilt all five APIs successfully: fixture SHA256 `cd9478ca855bf9d470abe676ef68256370aba9c2f6f8da9ae9d96717a0ad572c`, assessment SHA256 `abc133605986f4eb37a9ce03efc420a51dc00a7288fec04d8aa7440e8ce975f1`. Do not repeat it merely for status. It declares target ID 731 rather than hard-coding 1. Its two target candidates occur at decoded positions 2 and 4; position 3 is retained as a foreign item. No archive, actual decoded message or feature row is read, and every source/payload identity is only an invented assertion.

```powershell
Set-Location -LiteralPath 'C:\Users\pabta\Projects\ai-trader' -ErrorAction Stop
if ((Get-Location).ProviderPath -ne 'C:\Users\pabta\Projects\ai-trader') {
    throw 'Wrong project directory.'
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe' -PathType Leaf)) {
    throw 'Project Python is missing.'
}
$taskCursorExample = @'
import json
from ai_trader.research import six_e_native_cursor_metadata as c

header = c.DeclaredHeader(
    dataset='GLBX.MDP3', schema='mbo', symbols=('6E.FUT',), not_found=(),
    start_ns=1743984000000000000, end_ns=1744070400000000000,
    mappings=(c.MappingGroup('6EM5', (
        c.MappingInterval('2025-03-01', '2025-06-01', '731'),
    )),),
)
fixture = c.CursorFixture(
    fixture_id='synthetic-guide-cursor', source_session='synthetic-guide-session',
    utc_date='2025-04-07', contract='6EM5', header=header,
    asserted_member_sha256='f'*64, declared_item_count=4,
    items=(
        c.DecodedItem(1, 'metadata', None, None),
        c.DecodedItem(2, 'mbo', 731, 'a'*64),
        c.DecodedItem(3, 'mbo', 999, 'b'*64),
        c.DecodedItem(4, 'mbo', 731, 'c'*64),
    ),
)
assert c.protocol()['scope'] == 'invented_header_mapping_and_decoded_item_assertions_only'
protocol_pin = c.protocol_sha256()
fixture_pin = c.fixture_sha256(fixture, expected_protocol_sha256=protocol_pin)
result = c.assess(fixture, expected_fixture_sha256=fixture_pin,
                  expected_protocol_sha256=protocol_pin)
c.verify(result, fixture, expected_fixture_sha256=fixture_pin,
         expected_protocol_sha256=protocol_pin,
         expected_assessment_sha256=result.assessment_sha256)
assert (result.decoded_item_count, result.target_candidate_count, result.foreign_count) == (4, 2, 1)
assert [(a.decoded_position, a.target_candidate_ordinal) for a in result.audits
        if a.disposition == 'target_candidate'] == [(2, 1), (4, 2)]
assert len(result.authority_flags) == 26
assert all(flag is False for _, flag in result.authority_flags)
print(json.dumps({'status': result.status, 'fixture_sha256': fixture_pin,
                  'assessment_sha256': result.assessment_sha256,
                  'mapped_id': result.mapped_instrument_id,
                  'decoded_items': result.decoded_item_count,
                  'target_candidates': result.target_candidate_count,
                  'foreign_items': result.foreign_count,
                  'all_authority_flags_false': True}, sort_keys=True))
'@
$global:LASTEXITCODE = $null
$taskCursorOutput = & '.\.venv\Scripts\python.exe' -B -c $taskCursorExample 2>&1
$taskCursorExit = $global:LASTEXITCODE
if (($taskCursorOutput | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] }) -or
    $taskCursorExit -isnot [int] -or $taskCursorExit -ne 0) {
    $taskCursorOutput | Write-Output
    throw 'Constructed example failed or could not launch; diagnostics retained above.'
}
$taskCursorOutput
```
