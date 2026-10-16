# Synthetic native quote visibility

The separate module is implemented, independently reviewed and verified. Its 305 constructed cases and 698 adjacent accounting cases pass together; Ruff and formatting checks pass. The complete source-frozen project suite finished with 6,109 passed and three expected skips, zero failures/errors and unchanged source/test pins. It checks which constructed quotes are visible at a native cursor. It is a prerequisite for the future quote-to-admission adapter, not that adapter itself. No strategy, fill, fee, account, model or historical input is involved.

The held replay decides immediately after the first quote at a receive timestamp, before any equal-time suffix. The held admission reducer's accounting frontier cannot prove that this suffix was observed. This seam provides separate visibility and closure evidence that the future adapter must enforce to keep unseen prices out of a decision and retain an incomplete deadline group.

## Complete constructed input

The standalone module uses only the Python standard library and exact immutable dataclasses and tuples. One `NativeFixture` declares a `synthetic-` session identifier, a dated 6E contract label, an asserted source SHA256, a start and end, ordered quotes and original publication cursor/time declarations. Session and publication IDs are exact ASCII strings of at most 64 characters, beginning with a letter or digit and containing only letters, digits, underscores or hyphens. A session must begin with `synthetic-` and have a nonempty suffix. The declared contract syntax is exactly `6E[HMUZ][0-9]`; it does not assert calendar mapping. Synthetic labels prevent accidental use of historical role labels; they cannot prove that rows were invented or authenticate a feed or contract.

Quotes use exact bounded integer receive times and positive on-grid bid/ask values, with bid strictly below ask. The locally declared tick is 50,000 nanounits. Receive times are nondecreasing and lie in `[start_ns, end_ns)`. Each publication identifies the first native cursor at its timestamp; IDs and cursors are unique and ordered, and successive publications are at least one second apart. Empty complete fixtures are supported only without publications.

The complete canonical input pin binds metadata, every quote in order, every publication and both counts. A consuming call must receive the separately retained expected pin. Removing or reordering an equal-time suffix, changing a publication or changing source metadata must refuse against that same expectation. Generating a hash from an invented fixture is convenient for a prospective example, but silently replacing an expected pin with a new hash would defeat this check.

The initial bounds are 1,024 quotes, 64 publications and 256 KiB of canonical input. These are synthetic precursor limits, not support for the existing million-row historical cohort. Invalid metadata and tuple-count excesses refuse before price inspection; the complete fixture is checked before returning a prefix. No truncation, larger held limits or successful subset is accepted.

## Contiguous consumed prefix

`NativePrefix` binds the complete fixture pin and counts, declared session/source/contract/window, consumed count, exact last cursor and receive time, first cursor of the current timestamp group and a digest of consumed content. At count zero, the cursor/time/group fields are null. A cursor other than the next cursor derived from the retained prefix refuses. Repeating the same pure call with the same prefix is reproducible, not exactly-once progression.

The consumed-content digest is seeded by stable protocol and declared session metadata, then chained through consumed rows only. It excludes unseen quotes, future publications, counts and the complete input hash. Separately pinned fixtures with identical metadata and consumed rows therefore share this content digest, even when their unseen prices differ. Their complete fixture identities still differ. Changing the asserted source pin intentionally changes the source-bound content identity.

Every consuming API takes an exact retained `expected_prefix`, reconstructs it from the complete fixture and compares every field. It accepts no cached progression authority. Frozen objects are revalidated; merely constructing or poisoning an object cannot bypass guards. Repeating a pure operation does not persist progression or establish globally exactly-once consumption.

## First cursor publication

`publication_witness` requires the consumed count to equal the declared first publication cursor plus one. It returns an OPEN publication witness bound to that prefix. Consuming an equal-time suffix first and then asking for the earlier decision witness refuses.

The witness exposes no unseen quote or future publication values. Its complete fixture pin and total counts are integrity bindings, not features or policy inputs. Preparing a complete fixture does not automatically close the first-row observation. A later closure leaves the original publication witness unchanged.

## Separate timestamp closure

`close_through` requires `start_ns <= through_ns <= end_ns`, every row at or before `through_ns` consumed and no later row consumed. A remaining quote at exactly the boundary refuses closure. This includes boundaries between quotes, not only timestamps that occur in the tuple.

Closure has two forms. The exact next unconsumed cursor may have a timestamp strictly greater than the boundary; the closure then exposes only that cursor and timestamp, never its bid or ask, and does not consume it. Alternatively, complete pinned EOF requires every supplied row consumed. EOF can establish supplied coverage through the declared end, but cannot establish elapsed wall time, feed freshness or permission to expire an execution deadline.

These certificates are local consistency checks. They do not authorize admission accounting, timeout or UNKNOWN transitions. The later adapter must separately link genuine observation, timer closure, accounting cadence and the original execution protocol.

## Pure interface

The module is `ai_trader.research.six_e_native_prefix`. Its functions are:

- `fixture_sha256(fixture)` for prospective constructed input hashing.
- `prepare_fixture(fixture, *, expected_fixture_sha256)` for complete input validation.
- `initial_prefix(fixture, *, expected_fixture_sha256)` for the empty prefix.
- `verify_prefix(fixture, *, expected_fixture_sha256, expected_prefix)` for complete retained-prefix reconstruction.
- `consume_next(fixture, *, expected_fixture_sha256, expected_prefix, expected_cursor)` for one quote and the new prefix.
- `publication_witness(fixture, *, expected_fixture_sha256, expected_prefix, publication_id)` for the original first-cursor observation.
- `close_through(fixture, *, expected_fixture_sha256, expected_prefix, through_ns)` for separate boundary evidence.

`prepare_fixture` returns the same validated immutable fixture, not a cached authority object. There is no CLI, input discovery, filesystem access, source-file hashing, persistence, resume, historical loader, policy, accounting reducer, model or order hook. Every returned authority flag is exactly false. Source/feed/runtime/prefix/receipt/account/cash/margin/risk/execution/storage/resume/trading/training/scoring/independent-validation/promotion claims remain disabled.

No current API consumes a publication or closure certificate as authority. A future consumer must regenerate it with separately retained fixture identity and prefix plus its original publication ID or prospectively bound deadline, then compare every field with exact canonical types or bytes. It must not adopt a submitted certificate's own `through_ns` as the requested deadline or trust its OPEN/CLOSED label. Repeated pure calls remain reproducible, not globally exactly-once events.

## Acceptance and remaining integration

Acceptance is complete: independent source and test review, constructed adversarial cases, Ruff, formatting and a complete source-frozen project suite. Cases cover opposing equal-time suffixes, readiness/deadline equality groups, gap and EOF closure, first-row publication, omitted/reordered full inputs, wrong retained prefixes, strict types and poisoned objects, exact resource bounds, immutable results and forbidden I/O or integration hooks.

Root verified all 6,112 case-sensitive unique JUnit cases, process exit and unchanged source/test/package pins at 12:20:26 UTC on 9 October 2026. The only skips are the optional Nautilus dependency and two unavailable Windows symlink privileges. Report: `logs/project_full_suite_20261009_2.xml`, 904,889 bytes, SHA256 `24b732320c9e06a9a27855b53cf8a689d716062afd58be745ba57cb94c37204c`. Source SHA256 is `ae1a7e98aec517e1aa9bcd45f869040d812cfbb19190313b240a5313dca748b5`; test SHA256 is `020235cacc3a3cc3c1145d17d24d1784c598ce12d837f794accb7574b7a1c045`. The development handoff records the complete baseline, run identities and retained manifests.

This snapshot seam cannot prove that every publication certificate was used exactly once or that a consumer audited every decision. Full funded-path recomputation, denial ID/cooldown rules, receipt generation, single-genesis fee/reserve continuity, complete decision/quote audit and canonical result reconstruction remain later work. Historical execution additionally needs separately authorized inputs and fresh prospective complete-cohort registration. All existing sources, targets, controls and UNKNOWN liabilities remain unchanged.

## Run an invented visibility example

This PowerShell example uses three invented quotes over a declared three-second interval. Two share a timestamp; the third proves a later timestamp boundary without supplying its price as closure evidence. Root executed this exact block successfully. It writes no artifact, checkpoint or account and calls no model, policy or trading process. The locally generated pin demonstrates consistency only; a later consumer must retain its original expectations independently.

```powershell
Set-Location -LiteralPath 'C:\Users\pabta\Projects\ai-trader' -ErrorAction Stop
@'
from ai_trader.research import six_e_native_prefix as n

second, tick, price = 1_000_000_000, 50_000, 1_000_000_000
fixture = n.NativeFixture(
    "synthetic-guide", "6EM5", "a" * 64, 0, 3 * second,
    (
        n.NativeQuote(second, price, price + tick),
        n.NativeQuote(second, price - 5 * tick, price - 4 * tick),
        n.NativeQuote(2 * second, price + tick, price + 2 * tick),
    ),
    (n.NativePublication("first", 0, second),),
)
# Prospective invented input pin, not authenticated source evidence.
pin = n.fixture_sha256(fixture)
empty = n.initial_prefix(fixture, expected_fixture_sha256=pin)
first = n.consume_next(
    fixture, expected_fixture_sha256=pin, expected_prefix=empty, expected_cursor=0,
)
published = n.publication_witness(
    fixture, expected_fixture_sha256=pin,
    expected_prefix=first.prefix, publication_id="first",
)
try:
    n.close_through(
        fixture, expected_fixture_sha256=pin,
        expected_prefix=first.prefix, through_ns=second,
    )
except n.NativePrefixError:
    pass  # An equal-time quote remains unseen.
else:
    raise AssertionError("Premature closure accepted")
suffix = n.consume_next(
    fixture, expected_fixture_sha256=pin,
    expected_prefix=first.prefix, expected_cursor=1,
)
closed = n.close_through(
    fixture, expected_fixture_sha256=pin,
    expected_prefix=suffix.prefix, through_ns=second,
)
assert published.boundary_state == "OPEN"
assert published.prefix.consumed_count == 1
assert closed.boundary_state == "CLOSED"
assert (closed.closure_kind, closed.next_cursor) == ("next_timestamp", 2)
assert closed.next_received_at_ns == 2 * second
assert closed.prefix.consumed_count == 2  # The later quote was NOT consumed.
assert all(value is False for _, value in published.authority_flags)
assert all(value is False for _, value in closed.authority_flags)
print("Original publication:", published.boundary_state)
print("Equal-time suffix: required before closure")
print("Closure:", closed.closure_kind, "next cursor", closed.next_cursor)
print("Later quote consumed:", closed.prefix.consumed_count > closed.next_cursor)
'@ | .\.venv\Scripts\python.exe -B -
if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Constructed example failed or did not launch.' }
```

Expected output is `OPEN`, confirmation that the equal-time suffix was required, `next_timestamp next cursor 2`, and `Later quote consumed: False`. The original publication still has one consumed row; the closure has two. This is a library demonstration, not a running bot, historical validation or timer authorization.
