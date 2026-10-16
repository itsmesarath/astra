# R1.1 exact envelope calculator — 2026-10-15

Status: **PROSPECTIVE PURE CERTIFICATE SUPPORT / NOT A GOVERNOR OR WHOLE CERTIFICATE**. This implements only the six-expression mathematics already specified in section5 of the [reviewed recording design](6E_LOCAL_MEMBER_INTAKE_RECORDING_LEDGER_DESIGN_20261015.md), within the [15:12:58–19:12:58UTC window](6E_LOCAL_MEMBER_INTAKE_RECORDING_WINDOW_20261015.md). R1's complete source-linked host/worker/marker/root action and protected-cleanup certificates stay open. R2's governor and runtime-role integration cannot be released by this support slice.

## Exact isolated files and boundary

- Source only: `scripts/local_member_intake_recording_20261015_1.py`.
- Independent tests only: `tests/test_local_member_intake_recording_20261015.py`.
- Complete independent literals only: `tests/local_member_intake_recording_oracles_20261015.py`.

All three must be absent at initial admission. No old file, producer, P/D/R resource, accepted test-support deadline or production code changes. Stdlib only; no import of producers, ctypes, subprocess, framework/native helper, project package, side-effecting I/O or caller callbacks. This support file is not a seventh runtime-source role and is not imported by the held producers. Any later integration retains the explicit R2 gate. All input/output bodies are constructed mathematical data, not observations.

## API and result contracts

`RecordingRefusal(ValueError)` exposes `reason` as a read-only exact string. Refusals emitted by the functions use only `source_rules`, `expression`, `actual` or `capacity`. Arbitrary external construction of this exception is outside that emitted-reason guarantee. Do not catch/relabel unexpected AssertionError or other implementation faults.

`evaluate_envelope(expr, *, source_rules) -> {"upper_ascii_bytes": int, "witness": dict}`.

`check_actual(expr, actual, *, source_rules) -> {"actual_ascii_bytes": int, "upper_ascii_bytes": int}`.

Source-rule validation precedes complete expression validation; all OneOf branches are validated, including unused branches, before actual traversal. Only after both are fully valid may check_actual examine the supplied actual value. Return complete fresh outputs; no mutation of any submitted expression, rule or actual object, and no mutable output alias back into inputs. Unexpected assertions propagate uncaught. A malformed unselected branch cannot hide behind a matched actual branch.

Exact builtins only: no bool-as-int, subclass, tuple-as-list, coercion, normalization, permissive Unicode replacement, nonfinite/float, callback or arbitrary object. Null/bool/int/string/list/dict are allowed only in Literal/actual JSON values as appropriate. Integer scalar domain is **−9,223,372,036,854,775,808..18,446,744,073,709,551,615**, covering I64/U64 endpoints. Range minimum/maximum and repetition counts are exact nonnegative integers at mostU64max. Width totals are arbitrary exact Python integers; no machine-overflow wrap or cap on a computed prospective width is inferred.

Every Literal/actual nested string and dictionary key is an exact `str` consisting only of Unicode scalar values0..1114111 excluding55296..57343. Dictionary keys must be strings; empty keys and empty string values are allowed. Dictionary values recurse through the same strict JSON domain. JSON escape syntax that can represent a lone surrogate does not admit one here. Literal equality is type-strict recursively: true never equals1, false never equals0, and dictionary order does not affect equality. The same key/scalar rules apply to Record keys; source-selector names retain their stricter nonempty ASCII rule.

## Closed expression grammar

Expressions are exact dictionaries with exactly the following fields and no extras:

1. `{"kind":"literal","value":<complete strict JSON value>}`.
2. `{"kind":"integer","lo":<int>,"hi":<int>}` with lo<=hi.
3. `{"kind":"string","unit":<unit>,"minimum":<int>,"maximum":<int>,"alphabet_ranges":[{"lo":<codepoint>,"hi":<codepoint>},...],"source_selector":<selector>}`.
4. `{"kind":"one_of","items":[<expr>,...]}` with at least one branch.
5. `{"kind":"record","fields":[[<unique scalar-string key>,<expr>],...]}`.
6. `{"kind":"array","items":[<expr>,...]}`.

Record fields are an exact ordered list of two-element exact lists, with no duplicate key even when values coincide. Field order determines witness association; canonical actual encoding still sorts keys. All array positions and repeated aliases are distinct physical serialized occurrences; shared object identity does not discount size. A cycle along the current recursion path refuses; a repeated noncyclic subtree is visited/charged separately.

`source_rules` is an exact dictionary from nonempty ASCII selector string (at most256characters) to exact four-field dictionaries `unit,minimum,maximum,alphabet_ranges`. Validate every supplied rule, not only referenced ones. A string expression's four source-qualified fields must equal its externally selected rule completely. A nonempty label alone is insufficient. This proves declared equality, not external provenance, OS semantics or authentication. Rule entries are finite constructed registration data, not adopted from actual output.

Unit is exactly `ascii_code_units`, `unicode_scalar_values` or `utf16_code_units`. Ordered disjoint nonoverlapping inclusive ranges lie in0..1,114,111 and exclude55296..57343; a surrogate-crossing range is invalid, not split implicitly. ASCII ranges additionally lie within0..127. An actual string contains exact scalar code points in those ranges and has an admitted selected-unit count. Empty alphabet admits only empty string if minimum=0. A nonrealizable length/domain refuses as expression, not a fabricated witness.

## Width and deterministic witness

Use strict ASCII canonical JSON: sorted string keys, no whitespace, comma/colon separators, lowercase Unicode hex, no noninteger numbers. String quotes add2. Interior widths: quote/backslash/short escapes8,9,10,12,13 each2; other controls0..31 each6; printable32..126 except quote/backslash each1;127..65535 excluding surrogates each6; non-BMP65536..1114111 each12. Slash is not escaped. This follows the exact pinned CPython encoder selectors in the reviewed design; UTF8 byte length is not substituted for canonical ASCII width.

- Literal: exact complete canonical width, retaining every field including `receipt_sha256` and every duplicate occurrence. No category assignment/ownhash-body stripping occurs in this calculator.
- Integer: greater decimal width of its endpoints; on tie select the lower endpoint as witness.
- String: choose the least admitted representative code point at each attainable `(unit_cost,escaped_width)`. For each unit cost choose greatest escaped width, then smallest code point on tie. For scalar/ASCII units repeat the highest-width representative maximum times. For UTF16, take the greatest realizable total units in the interval, maximizing cost2 count, then cost1 remainder; cost2 runs come first. If only cost2 exists, use the largest admitted even total. Empty permitted domain has no runs. No DP array or giant string expansion is allowed merely to compute/reject an upper bound.
- OneOf: greatest branch width; lowest branch index on tie.
- Record with n fields: `2+max(n−1,0)+sum(canonical_key_width+1+child_width)`.
- Array with n items: `2+max(n−1,0)+sum(child_width)`.

Witness is a complete closed tagged tree: Literal/Integer use `{"kind":"value","value":<fresh complete selected value>}`; String uses `{"kind":"string_runs","runs":[[<codepoint>,<positive count>],...]}`; OneOf uses `{"kind":"one_of","selected_index":<int>,"witness":<tree>}`; Record uses `{"kind":"record","fields":[[<key>,<tree>],...]}`; Array uses `{"kind":"array","items":[<tree>,...]}`. Do not expand RLE strings. Runs select cost2 then cost1 as above and omit zero counts. These witnesses are **synthetic sizing inputs**, never actual observations or real-date claims. Actual date/calendar/path/native semantics remain independently unverified by this algebra.

check_actual requires complete domain membership, not just smaller byte count: exact Literal type/value throughout; Integer interval and exact integer type; String scalar/alphabet/unit limits; Record exact field set/types; Array exact length/items; OneOf membership in at least one fully valid branch. Return the upper width of the whole expression even if the actual matches a smaller OneOf alternative. A correct width never excuses an invalid domain.

## Finite calculation guards — not changed production limits

The exact **input-tree work** function is `W(null|bool|int)=1`, `W(str)=1+len(str)`, `W(list)=1+sum(W(item))`, and `W(dict)=1+sum(1+len(key)+W(value))`, with scalar-string keys. Count every physical occurrence, including expression grammar dictionaries, tag/selector strings, range dictionaries, fields/items lists and two-element field pairs. Noncyclic aliases are revisited/charged fully; an active-path cycle refuses in its current validation phase. Source_rules, expression and, for check_actual only, actual each have root depth1; a dictionary key and value are both children at depth+1, and every list element is a child at depth+1. No extra semantic-expression depth replaces these structural edges. Maximum depth is64 and every collection length is at most65,536. Refuse at the first depth/length excess before descending further.

One shared input-work budget is **1,048,576**: evaluate admits iff `W(source_rules)+W(expr)<=limit`; check_actual additionally requires `+W(actual)<=limit`. Validate/charge source_rules first, then validate/charge the complete expression, then traverse actual. A node whose addition would exceed the remaining budget refuses before its children are visited or a large copy is allocated. This exact logical charge is independent of implementation pass count; no arbitrary additional conservative input charge is allowed. Malformed builtin/type/string/key/cycle/semantic data refuses with its current phase's `source_rules`, `expression` or `actual`; depth/length/work excess refuses `capacity`. Per-selector nonempty ASCII length<=256; counters/minima/maxima are at mostU64max.

check_actual has a **separate deterministic matching-work** budget of1,048,576 to bound repeated OneOf attempts; it does not change W. A call to match an expression against a value costs1. A String match additionally charges len(value) iff value is an exactstr, before scanning it. Literal matching delegates to type-strict equality: each compared value pair costs1; a same-type string pair additionally charges len(expected)+len(actual) before comparing; dict/list pairs first require matching exact type and key set/length, then compare child pairs in sorted-key/index order until the first mismatch. Dictionary key-set comparison charges no extra matching units (keys were completely charged/validated in W); values do. Integer matching has no additional cost. Record first requires exactdict/complete key set, then matches fields in registered fields-list order until first mismatch; Array first requires exactlist/length then matches items in index order. OneOf tries branches left-to-right until the first matching branch, with every attempted branch's full actual matching cost retained; all branches were already structurally/semantically validated. A type/key-set/length mismatch visits no children. Refuse `capacity` before a matching charge would exceed its separate limit. No arbitrary extra matching charge is allowed. This distinguishes exact valid-at-input-limit cases from cases that legitimately exhaust a second, explicitly defined matching budget.

These guards define only this invented calculator's supported corpus, not historical capacity, Host/Root byte caps or a silent simplification of a too-large certificate. An unsupported certificate remains open; it is not thinned/split and declared complete.

Compute widths before any canonical serialization/witness copy that could expand a large graph. A large StringEnvelope maximum must remain compact even when its computed prospective width exceeds every production cap. Unqualified broad error strings/source selectors are not made source-qualified by a calculator result. Complete certificates needing unsupported complexity remain unresolved rather than being thinned or split and relabeled complete.

## Test-first registration and acceptance

Before a behavioral RED, source author may create only the reviewed callable baseline: RecordingRefusal plus the two exact functions which raise explicit NotImplementedError, with no implementation. Independent tests import this valid native-free baseline, directly call the APIs and compare complete literal width/witness results. They may convert only that explicit NotImplementedError to an uncaught AssertionError naming the missing behavior; no broad catch, missing-file fallback, skipped import or collection error is intended RED. Root records complete collected/executed identities/tool/Python exit/owned lifecycle/pre-post raw pins. Only accepted RED releases matching implementation; run the same identities GREEN.

Independent complete literal vectors include all six variants, exact escaped classes/native integer endpoints/empty and nonrealizable domains, same-object duplicate occurrences, source rule mismatch, malformed unselected branch, full body/digest keys, mutation/output aliasing and strict type/cycle/work/depth first-excess cases. Expected constants never call production serializers/evaluator/reflection/native output. A test-local canonical serializer may check only independently registered synthetic witness expansion at small sizes, not generate the expected width/witness constants. Exact mutation/restore sensitivity evidence and full independent source/test read precede narrow acceptance. Derive test count/identities from actual complete collection, never guess. New-source Ruff/format, proportionate adjacent checks and complete report/owned/pin reconciliation remain required; whole project/native qualification is not inferred.

This calculator gives no B/H/M/raw category classifier, occurrence governor/reservation/commit enforcement, native EOF/cleanup/source correction or six-role runtime integration. R1 whole-source certificates, R2 recording behavior and all actual G4/filesystem/full-regression/profile gates remain separate.
