# Next gate for decoded payload binding

## Design status

This native/historical adapter remains design only. No adapter, native import, decoder, serialization experiment or historical input is released. Root inspected the installed local `databento_dbn/_lib.pyi`, `__init__.py` and `v3.py` as text, not through Python imports. Type annotations are not runtime or source authenticity proof. The old cursor metadata assessor accepts invented opaque payload pins; the subsequently accepted [constructed payload-binding layer](6E_RECORD_PAYLOAD_BINDING.md) now independently recomputes all sixteen invented JSON fields and checks those pins. It still proves no original native bytes, decoder/header completeness, book acceptance or source authentication. [Current project status](../PROJECT_STATUS.md) separates that completed layer from this unreleased adapter.

## Three representations must stay distinct

| Representation | Future binding requirement | Must not be called |
| --- | --- | --- |
| Original compressed member | Complete raw bytes, resource bounds, original pinned source and accepted EOF | Decoded object serialization |
| Yielded native object | Original yielded order, full declared header/type context and version/upgrade semantics | Compressed/uncompressed byte offset |
| Numerical engine input | Original raw integer fields and exact target/foreign disposition, followed by accepted book/event processing | An opaque payload hash assertion |

The local annotations expose `Metadata.__bytes__` and `MBOMsg.__bytes__`, plus `record_size`. This is not evidence that reserializing a yielded object reproduces the original input byte range. Decoder version upgrades are explicitly configurable, and the existing loader uses its default decoder policy. A future contract must lock input version, upgrade policy, output representation and ts_out behavior rather than assume byte equivalence from an object method name. The documented decoder `write_and_decode` yields lists of objects and `buffer` exposes its internal buffer; neither supplies compressed record offsets.

## Complete native metadata and record fields

The current constructed header includes only declared dataset/schema/parent/not_found/day/mappings. Native Metadata also exposes version, stype_in/stype_out, partial, limit and ts_out. A later complete native projection needs to specify all relevant fields, representation rules and refusal behavior. Missing fields cannot be silently defaulted, and an opaque header/member pin cannot fill that gap.

The local MBOMsg constructor and fields include publisher_id, instrument_id, ts_event, order_id, raw integer price, size, action, side, ts_recv, flags, channel_id, ts_in_delta, sequence and ts_out, with rtype and record size exposed separately. A future projection must bind its exact full field set and native representation, not an ad hoc subset that ignores publisher/channel/version or converts raw integer price through a float. Constructor annotations are not proof of native integer bounds; those bounds and refusal behavior need their own reviewed evidence and constructed tests.

Do not sort by the annotated ts_index convenience field: the original research engine preserves yielded receive order and equal-time order. Foreign items remain part of complete decoded provenance while bypassing target clocks, timers, book and flow. Their complete representation still needs binding even when their values are invalid for a target. Native target acceptance requires original daily/quality/clock/reset rules and successful book application, which the present candidate ordinal cannot prove.

## Event and publication evidence

The later adapter must retain the actual UTC-day initialization path, not transplant the target-only witness's fixed instrument-1 empty R genesis. A mapped non-1 instrument cannot be silently relabeled as 1 to bypass that witness's guard. Successful target ordinals must be established after original book application and linked separately from the existing decoded positions and candidates.

Full native event/T provenance and original protected execution capture remain separate. Earlier T records may complete at an in-window F_LAST while execution metrics retain only their original protected capture suffix. Foreign F_LAST cannot flush target trades. Resets without F_LAST need their original separate disposition, not an invented ordinary event closure. The first due completed quote must publish before following equal-time records; native completion, timer, warmup, inactivity and cadence semantics must remain fixed.

## Prospective acceptance gates

Before numerical traversal, a separately closed adapter contract must validate complete source roles, header/mapping/version metadata, capacities and expected source identities. A final malformed declaration must refuse the whole constructed fixture. Its first stage can use invented fully typed records and independent hand-built event/publication oracles; native decoding tests and any source read remain separate explicit releases.

Require complete original target and foreign coverage, independently reconstructed pre-state and event/publication links, original row representation and a causal seed excluding future member hashes. Changing only an unconsumed suffix may change final source identity but cannot alter a preceding publication under unchanged context, used sources and consumed prefix. Accepted complete EOF is a terminal source check, not permission to leak future data into an earlier decision.

Whole-member capacity, mapping/calendar support, original feature-row parity and one-genesis multi-session continuity remain unresolved. Real historical access requires a separately reviewed implementation and fresh prospective complete-cohort registration. Do not thin, split, omit foreign messages, relabel historical inputs synthetic, filter old fills or reset funding to fit current component bounds. No profitable strategy, broker economics, training, scoring or promotion authority follows from these designs.
