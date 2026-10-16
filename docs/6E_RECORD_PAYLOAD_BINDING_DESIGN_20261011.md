# Prospective constructed record-payload binding

## Status and purpose

**Current chronology clarification:** This original prospective design is retained as history. Its constructed scope was subsequently closed in the human-approved payload-binding contract and fully implemented/accepted at 2026-10-11T14:16:22Z. See [the current guide](6E_RECORD_PAYLOAD_BINDING.md) and [project stage map](../PROJECT_STATUS.md). The DESIGN ONLY, unlocked-schema and pending-suite wording below describes this document's original point in time; it does not supersede the approved contract or current acceptance. Native/historical gates remain unimplemented and unreleased.

DESIGN ONLY. No new module, test, import, native decoder, serialization experiment or historical access is released by this document. The current full suite freezes every Python file. Exact schemas, integer bounds, IDs, byte caps, codec context and authority flags are not locked here. A later implementation needs a separately closed and independently reviewed contract, stable independent tests and another complete source-frozen regression suite.

The cursor component has static/focused acceptance, with complete regression acceptance still pending as this design is written. It is deliberately numerical-payload-free: its payload/member pins are caller assertions. The smallest prospective next layer would independently recompute each **constructed JSON payload** pin from complete declared integer fields, retain every decoded position and reconstruct the original cursor assessment. It would not decode DBN, recover original message bytes, apply an order book, derive features, authenticate a feed or validate a strategy.

## Complete positional binding

Retain exactly one immutable payload entry per complete decoded position. Position 1 carries literal `None` because its declared header is already represented separately. Each later target **and foreign** MBO assertion carries exactly one complete constructed record body. Require exact tuple length, original order, instrument agreement and equality of every retained payload pin with its independently recomputed body hash. Do not omit, default, filter or reorder foreign records. Identical payloads at different positions remain distinct occurrences.

The existing item chain binds decoded position, kind, instrument and payload hash. After complete-body pin recomputation and comparison, that chain can bind the constructed body transitively; a second body chain is not automatically a cryptographic necessity. However, any new codec/version/optional-field context not represented by the old seed must receive a separately defined identity and causal context binding. A later contract must label each identity precisely rather than reinterpret the old opaque-assertion prefix as proof of new native semantics. Complete fixture identity and causal prefix identity remain distinct.

## Prospective fields and representation

Local installed annotations expose fourteen MBO constructor/property fields: `publisher_id`, `instrument_id`, `ts_event`, `order_id`, raw integer `price`, `size`, `action`, `side`, `ts_recv`, `flags`, `channel_id`, `ts_in_delta`, `sequence` and `ts_out`. They also expose `rtype` and `record_size`. A future contract must enumerate an exact complete field set and explicit representation for all of them, not borrow constructor defaults. The annotations alone establish neither native ABI widths nor valid native enum values.

Preserve exact Python integers, including signed raw price, without conversion through float, `pretty_price`, sentinel replacement, arithmetic normalization or `ts_index`. Exercise values around `2**53`, negative/zero prices and both ends of whichever **declared constructed** bounds are independently locked. Native-width or sentinel-validity claims require separate evidence. If `ts_out` is optional under a declared context, its presence/absence and representation must be explicit, never silently defaulted to zero or inferred from another field.

Full native Metadata/version/upgrade/`ts_out` context remains a separate unresolved requirement. The current declared header omits native version, stype_in/stype_out, partial, limit and ts_out. A constructed full-field JSON body is not a native wire record or proof of header completeness. Calling `__bytes__` later would not establish equivalence with compressed-member bytes, original record offsets or decoder input versions.

## Structural binding is not target acceptance

Representation-valid foreign bad-clock, negative-price, unusual-flag or unsupported-target-action assertions should remain completely bound under the locked structural schema, without target clock, timer, book, flow or F_LAST processing. Structural representation bounds must not be mislabeled native semantic acceptance. The future contract must define refusal where a value is outside its own declared schema; it must not salvage a valid subset.

The old feature witness cannot serve as an unrestricted numerical destination: it forces instrument 1, an exact invented empty R genesis, protected warmup/window timestamps, flags 0 or 128, and its own positive/on-grid numerical restrictions. Never rename a mapped non-1 instrument, manufacture that genesis, normalize foreign values or replace the original daily initialization to fit it. Full target application, accepted-target counters, native event/T provenance and publication closure remain separate unimplemented gates.

## Unexecuted acceptance groups

All cases below are prospective, not collected tests or observed results.

| Group | Required observation before release |
| --- | --- |
| Complete schema | Remove or replace each field; reject subclasses, dictionary substitutions, bool/int aliases, defaults and unsupported fields. |
| Integer preservation | Preserve declared signed values and `2**53 - 1`, `2**53`, `2**53 + 1` exactly; refuse floats and conversion helpers. |
| Independent field binding | Changing publisher, channel, sequence, timestamps, quantity, price, action, side or ts_out changes its body pin and subsequent bound prefix identity. |
| Full position coverage | Refuse wrong tuple length, non-None metadata payload, missing target/foreign payload, skipped/reordered positions, instrument mismatch and wrong retained pin. |
| Foreign structural cases | Retain all schema-valid foreign bodies without target semantic filtering or timer/event effects. |
| Validation phases | All expected-pin syntax and independently known protocol/context equality precede deferred record-value traversal. A payload or complete-bundle pin must be recomputed from its fully validated values and compared before acceptance, not before reading the values it binds. Lock the exact deferred fields and use uncaught assertion sentinels, not generic ValueError-only tests. |
| Final malformed declaration | A malformed final envelope/context or independently checkable structural declaration refuses before earlier deferred-value projection. A malformed numeric value still refuses the whole result after required value traversal; no accepted successful prefix or impossible pre-read whole-input equality claim. |
| Independent canonical oracle | Hand-project every field, body, audit and result; use independent ASCII sorted compact JSON and SHA256 rather than production serializers. |
| Defensive body limits | Check literal shared-cap equality and overflow separately from valid-public-fixture capacity; do not claim a universal maximum from one measured envelope. |
| Suffix causality | Two fully valid bundles with unchanged consumed context/items/payloads but different future suffix/member assertions preserve earlier bound identity while changing complete identity. |
| Changed foreign prefix | A changed preceding foreign body changes its verified pin and the following decoded-prefix identity, even when target candidates stay identical. |
| Complete verification | Rebuild complete submitted state and reject every count, field, audit, retained-pin, status and authority tamper; never adopt caller summaries. |

## Remaining authority boundary

No reader, writer, history, native import, account, model, order, CLI or resume hook is proposed by this small binding layer. It cannot detect a coherent whole-context replacement by the caller. Native decoding, original bytes/EOF, mapping/calendar/source/runtime authentication, successful book application, event closure, first publication, complete historical capacity, one-genesis multi-session continuity, broker economics, training, scoring, promotion and profitable strategy remain unproved and must stay false.

See `6E_DECODED_PAYLOAD_NEXT_GATE_20261011.md` for the three representation layers and `6E_NATIVE_CURSOR_BRIDGE_NEXT_GATE_20261010.md` for native cursor/target/publication distinctions. Any historical experiment still requires a separate reviewed implementation and fresh prospective complete-cohort registration; no truncation, thinning, relabeling, daily resets or old-fill filtering is authorized.
