# Fixed synthetic liquidity directions

This prospectively reviewed contract is implemented in the two new source/test paths below, following fully verified complete suite 5 at 17:57:06 UTC. Independent and root complete-file review, all 2,270 corrected adjacent tests including 646 new cases, whole Ruff and new-file formatting passed. At **19:00:59 UTC**, root fully verified complete suite 6: **7,376 passed, three expected skips, zero failures/errors**, all 7,379 case-sensitive unique cases including all 646 point cases, owned-process exit and unchanged pins. Report `logs/project_full_suite_20261009_6.xml` is 1,127,782 bytes, SHA256 `6e8c6a85fcc5ed5c8ddbbd2b527fff4270e771755fdad614cc1985b0d36e865d`. All 406 Python source/test files remain frozen for the rest of this window, ending at 20:56:32 UTC; do not repeat completed tests, examples or verifiers. No historical input, model, accounting integration or order hook is released.

Independent scope, architecture and testability reviewers read the complete contract and found no actionable correction. Their contract review is not runtime acceptance. Independent tests must retain the unchanged calendar guard for invented normative controls.

The component isolates the existing three numerical rules and idle control from calendar, historical-loader and model dependencies. It supplies independently checkable directions for a future funded-path adapter; it does not implement that adapter. Numerical agreement is not a strategy improvement, feature provenance, historical validation or a trading signal authorized for use.

## Closed pure interface

New paths are `src/ai_trader/research/six_e_synthetic_liquidity_point.py` and `tests/test_six_e_synthetic_liquidity_point.py`. The module may import only Python standard-library modules. No historical module, NumPy, I/O, CLI, clock, source-file hashing, network, model, policy fitting, account or order hook exists.

Constants are `VERSION = "six_e_synthetic_liquidity_point_v1"`, `STATUS = "constructed_liquidity_directions_not_strategy_integration"`, `MAX_CANONICAL_BYTES = 16384`. Error is `SyntheticLiquidityPointError(ValueError)`.

Frozen slotted `SyntheticLiquidityPoint` has exactly `point_id: str` and `values: tuple[int | float, ...]`. Require the exact class, both complete fields and an exact tuple of length 37, including when a frozen object has been deliberately poisoned. Identifier is exact ASCII string matching `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`, starting `synthetic-` with a nonempty suffix. There is no date, session, contract, timestamp, cursor, price, outcome, eligibility or funding input.

Frozen slotted `PointSelection` fields in order are `version`, `status`, `protocol_sha256`, `point_sha256`, `directions`, `selection_sha256`, `authority_flags`. Directions are exact immutable pairs in order `cvd_follow`, `liquidity_follow`, `absorption_fade`, `no_trade`, each exact integer -1, 0 or +1; idle is always 0. Keep these separate even if they disagree. There is no selected winner, vote or tie resolution.

Pure APIs are:

```python
protocol_sha256()
point_sha256(point)
select_point(point, *, expected_point_sha256)
verify_point_selection(point, *, expected_point_sha256, expected_selection_sha256)
```

Both select and verifier require independently retained original lowercase 64-character SHA256 expectations. Check expectation syntax before reading numeric values. Then validate complete metadata, complete numerical input and its original pin, without taking a submitted selection as authority. The verifier rebuilds the entire selection and compares its canonical output pin. Coherent replacement of all invented context and expectations is not authenticated or detectable.

## Exact 37-feature order

`FEATURES` is the following literal tuple, not dynamically imported from the historical graph:

```python
(
    "log_bid_qty", "log_ask_qty", "queue_imbalance", "normalized_ofi_5s",
    "normalized_cvd_5s", "log_known_trades_5s", "unknown_trade_fraction_5s",
    "log_prior_quote_gap_ms", "log_bid_depth5", "log_ask_depth5",
    "depth5_imbalance", "bid_top_share5", "ask_top_share5", "bid_span5_ticks",
    "ask_span5_ticks", "mid_change_5s_ticks", "mid_range_5s_ticks",
    "mid_travel_5s_ticks", "log_quote_events_5s", "normalized_bid_reload_5s",
    "normalized_ask_reload_5s", "buy_absorption_proxy_5s",
    "sell_absorption_proxy_5s", "bid_passive_5s", "bid_held_top_passive_5s",
    "bid_linked_decrease_5s", "bid_unlinked_decrease_5s", "bid_same_id_reload_5s",
    "bid_other_id_reload_5s", "bid_same_id_net_refresh_5s", "ask_passive_5s",
    "ask_held_top_passive_5s", "ask_linked_decrease_5s", "ask_unlinked_decrease_5s",
    "ask_same_id_reload_5s", "ask_other_id_reload_5s", "ask_same_id_net_refresh_5s",
)
```

All values are exact `int` or `float`, finite under `math.isfinite`; reject bools, subclasses, NaN and infinities. An unrepresentably huge integer or serialization failure must become the declared error, not an unhandled overflow. All execution14 values and every `log_` field are nonnegative. Unknown-trade fraction and both top-share fields lie in [0,1]; queue and depth5 imbalance lie in [-1,1]. The eight span/range/travel/reload/absorption fields already constrained by the original inputs are nonnegative. Signed midpoint change, CVD and OFI are otherwise finite-only. No new semantic consistency, clipping, normalization, proxy upper bound or threshold search. Preserve int versus float and signed zero in canonical identity; never silently coerce the vector.

## Fixed formulas, with equality preserved

Use `math.log1p` for the original count thresholds. Sign is exactly `int(v > 0) - int(v < 0)`. The CVD control returns sign(CVD) if `log_known_trades_5s > 0`, otherwise 0. It ignores the liquidity gate and the 20-trade threshold.

The liquidity gate requires prior quote log <= log1p(250), known-trade log > 0, unknown fraction <= 0.1, minimum top-quantity log >= log1p(5), minimum visible-depth5 log >= log1p(20), maximum five-level span <= 8, and quote-event log >= log1p(20). Follow and fade additionally require known-trade log >= log1p(20).

Follow returns CVD sign only when CVD, OFI and midpoint-change signs are equal and nonzero, absolute CVD and OFI are each >= 0.5, absolute midpoint change >= 1, and midpoint range >= 4. Otherwise it returns 0.

Fade uses attacked ask side for positive CVD and bid side for negative CVD. It returns the opposite CVD sign only when CVD sign is nonzero, absolute CVD >= 0.5, absolute midpoint change <= 1, attacked-side held-top-passive proxy >= 0.25, attacked-side other-ID-reload proxy >= 0.1, and queue-imbalance sign equals the fade direction. Otherwise it returns 0. At absolute midpoint change exactly 1, follow and fade may both be nonzero and opposite. Do not combine or suppress either output. These are conservative proxies, not proof of icebergs or absorption.

## Complete canonical identities

All hashes use UTF-8 ASCII JSON with sorted keys, compact separators and `allow_nan=False`; bound complete encoded bodies by 16 KiB before hashing. Do not truncate, resize automatically or serialize partial input. Fixed protocol constants do not change when a defensive test lowers a runtime enforcement cap.

Protocol body has exactly `version`, `status`, `features`, `policies`, `numeric_domains`, `thresholds`, `source_pins`, `max_canonical_bytes`. Features and policies are complete lists in the orders above. Numeric domains are exactly this dictionary:

```python
{
    "exact_types": ["int", "float"], "finite": True,
    "execution_nonnegative": True, "log_nonnegative": True,
    "unit_interval": ["unknown_trade_fraction_5s", "bid_top_share5", "ask_top_share5"],
    "signed_unit_interval": ["queue_imbalance", "depth5_imbalance"],
    "nonnegative": ["bid_span5_ticks", "ask_span5_ticks", "mid_range_5s_ticks",
                    "mid_travel_5s_ticks", "normalized_bid_reload_5s",
                    "normalized_ask_reload_5s", "buy_absorption_proxy_5s",
                    "sell_absorption_proxy_5s"],
}
```

Thresholds are exactly `prior_quote_gap_ms:250`, `top_quantity:5`, `depth5_quantity:20`, `max_span_ticks:8`, `quote_events:20`, `known_trades:20`, `unknown_fraction:0.1`, `abs_cvd:0.5`, `abs_ofi:0.5`, `follow_abs_move_ticks:1`, `follow_range_ticks:4`, `fade_abs_move_ticks:1`, `held_top_passive:0.25`, `other_id_reload:0.1`. They describe the fixed inclusive formulas above; no learned threshold exists. `max_canonical_bytes` is 16384.

Source pins are exactly the following four repository-relative declared original numerical/schema sources, retained read-only in the held 402-file baseline:

- `src/ai_trader/training/six_e_liquidity.py`: `0c3643695b50c0758b7ff73c8e4bb010bafa7ef492e25e5e8f408e28edc0a3ec`
- `src/ai_trader/research/databento_6e_cost_targets.py`: `ebc4c1dc0a44e71362cd96bed0a699dac6ebc04a66fc7f568d2bf4898d427b2b`
- `src/ai_trader/research/databento_6e_microdepth.py`: `8964b20a5de8104a0f7831cf827c1c736f3c11b6a2d61dbe0206521ee3b451c4`
- `src/ai_trader/research/databento_6e_execution_flow.py`: `7f777a19518378dd3b2a0371b7f3ddcf3077f51555faffa5e589de6255239b75`

The pure module declares these pins; it never reads source files to authenticate them or attests the complete import/runtime graph. Root source-manifest checks and independent normative parity tests are separate evidence. Point body has exactly `version`, `status`, `protocol_sha256`, `point` (full asdict). Selection body is full asdict minus only `selection_sha256`. No mutable protocol argument or submitted result is accepted.

`AUTHORITY_FLAGS` is a sorted immutable tuple of these exact names with every value false: `input_authenticated`, `source_integrity_verified`, `causal_features_verified`, `calendar_verified`, `eligibility_verified`, `complete_session_verified`, `original_strategy_integration_verified`, `accounting_admission_authorized`, `execution_authorized`, `storage_resume_authorized`, `trading_enabled`, `training_enabled`, `scoring_authorized`, `independent_validation`, `promotion_allowed`. Every complete result includes them.

## Independent acceptance

Independent tests freeze the literal 37 names, original source pins, full protocol/input/result bodies and false flags. Manual expected outputs must cover both directions, signed zero, no known trades, nonliquid CVD, every gate equality and `math.nextafter` neighbour, attacked-side asymmetry, unused-feature changes, opposing simultaneous follow/fade, exact numerical domains, caps, malformed identifiers/classes/tuples/pins and poisoned frozen fields. Metadata or bad expectation syntax must fail before sentinel numeric inspection. Valid but mismatching complete pins must fail without adopting replacement expectations. Demonstrate complete accepted worst-shape canonical input/output size, finite scalar limits and lowered runtime cap refusal; do not auto-resize.

Normative parity may call unchanged `six_e_liquidity.rules` on invented one-row, calendar-valid development controls using the already established 2025-04-07 / 12:00 UTC / 6EM5 label. Never pass historical data under synthetic labels, disable reserved/calendar guards or load any archive. Compare all three outputs and held literal order against independent expectations. This establishes numerical one-point parity only: cadence, complete-session calendar and eligibility remain outside this contract. Guard the new production module's stdlib-only imports and forbidden I/O/network/process/clock/model/order hooks.

These acceptance requirements are now satisfied: root full-file review, independent source/test review, new and adjacent tests, whole Ruff, new-file formatting and a fresh complete frozen-source suite with every old/new identity, exact skips, unchanged held baseline and complete output report verification. The verified evidence is recorded at the beginning of this guide and in the development-window handoff; no further suite is required or released for this window. No integration, historical scoring, fitting, promotion or trading follows automatically. The causal multi-candidate funded strategy walker is a separate future contract, not this module.

## Invented in memory example

Root executed and rebuilt this invented example once at 18:01:59 UTC after complete static source review and before focused or full-suite acceptance. An initial launcher-path typo failed before Python started; the corrected launch was the sole actual example invocation. Source SHA256 `4cba581af818c9fb9b5ad9aef876216350b4bff5e1368e2afb4355754c46b35e` matched before and after. Do not repeat the completed example for status. Its generated pins identify invented in-memory values only; they are not source, market or strategy authority.

```python
import math
from ai_trader.research import six_e_synthetic_liquidity_point as selector

values = dict.fromkeys(selector.FEATURES, 0)
values.update(
    log_bid_qty=math.log1p(5), log_ask_qty=math.log1p(5),
    log_bid_depth5=math.log1p(20), log_ask_depth5=math.log1p(20),
    log_known_trades_5s=math.log1p(20), log_quote_events_5s=math.log1p(20),
    log_prior_quote_gap_ms=math.log1p(250), unknown_trade_fraction_5s=0.1,
    normalized_cvd_5s=0.5, normalized_ofi_5s=0.5,
    mid_change_5s_ticks=1, mid_range_5s_ticks=4, queue_imbalance=-0.5,
    ask_held_top_passive_5s=0.25, ask_other_id_reload_5s=0.1,
)
point = selector.SyntheticLiquidityPoint(
    "synthetic-liquidity-guide", tuple(values[name] for name in selector.FEATURES),
)
input_pin = selector.point_sha256(point)
selection = selector.select_point(point, expected_point_sha256=input_pin)
assert selection.directions == (
    ("cvd_follow", 1), ("liquidity_follow", 1), ("absorption_fade", -1), ("no_trade", 0),
)
assert all(value is False for _, value in selection.authority_flags)
assert selector.verify_point_selection(
    point, expected_point_sha256=input_pin,
    expected_selection_sha256=selection.selection_sha256,
) == selection
print(selection.status, selection.directions, selection.selection_sha256)
```

The opposing directions are intentionally retained for separate policies. This block has no file input, archive, key, clock, network, model, accounting transition or order. It cannot assess a trade's return, execution or profitability.

The verified result has protocol SHA256 `d85e79987b12130f4dd54e106a247e621b96dba7ab0bdf1c9c267b4295076f6e`, point SHA256 `bcc95f27288fb969cacaf77a8e766a36902e082d933f3ab9141d417c9a59d66a` and selection SHA256 `895797b0b0d6d3f1703df9aac51605dab669a0368d259c803e46f2f6e726a9d7`. All fifteen authority flags remain false.
