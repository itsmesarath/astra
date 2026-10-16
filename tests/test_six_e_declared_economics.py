"""Synthetic declared tapes only: no quotes, history, model, network or account."""

import builtins
import hashlib
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, replace
from decimal import Decimal
from pathlib import Path

import pytest

from ai_trader.research import six_e_declared_economics as e

r, ledger = e.replay, e.ledger
DAY, NEXT_DAY = "2025-04-07", "2025-04-08"
START, END = r.target.window(DAY)
SECOND, TICK, MS = r.target.SECOND, r.target.TICK, r.target.SECOND // 1000


def assumptions(**changes):
    # Deliberately synthetic amounts, not asserted current 6E/broker economics.
    return replace(e.DeclaredEconomics("USD", 125, 8, 11, None), **changes)


def seed(**changes):
    return replace(e.EconomicSeed(1000, START), **changes)


def reconstruct(plan, events=None, receipts=None, source_pins=None, config=None):
    events = plan.events if events is None else tuple(events)
    config = plan.config if config is None else config
    pins = plan.source_pins if source_pins is None else source_pins
    genesis = ledger._hash(
        ledger._canonical(
            {
                "config": asdict(config),
                "protocol": ledger.protocol(),
                "source_sha256": {
                    key: value for key, value in pins.items() if key != "six_e_continuous_replay.py"
                },
            }
        )
    )
    state = ledger.LedgerState(0, genesis, None, 0, None, None, None, 0, 0, 0, 0)
    for event in events:
        tip = ledger._hash(state.tip_sha256.encode() + b"\n" + ledger._record(event))
        state = replace(
            ledger._apply(state, event, config), sequence=state.sequence + 1, tip_sha256=tip
        )
    return replace(
        plan,
        config=config,
        source_pins=pins,
        events=events,
        receipts=plan.receipts if receipts is None else tuple(receipts),
        terminal_state=state,
    )


def tape(
    *, side="long", close=True, unknown=False, carry=False, two=False, no_trade=False, exit_tick=104
):
    days = (DAY, NEXT_DAY) if carry else (DAY,)
    manifest = {
        "version": "six_e_feature_quote_fixture_v1",
        "sessions": [
            {
                "source_session": day,
                "contract": r.study.census.dated_contract(day),
                "role": r.study.data.role_for_day(day),
                "source_sha256": "a" * 64,
                "decisions": 0,
                "decisions_sha256": "b" * 64,
                "quotes": 20,
                "quotes_sha256": "c" * 64,
            }
            for day in days
        ],
    }
    config = ledger.ScenarioConfig(
        "synthetic-economics-1",
        "no_trade" if no_trade else "cvd_follow",
        "bracket_exit",
        r._digest(r._json(manifest)),
        r.protocol()["version"],
    )
    pins = {name: hashlib.sha256(name.encode()).hexdigest() for name in e.SOURCE_NAMES}
    events, receipts = [], []

    def event(cls, now, **values):
        events.append(cls(f"event-{len(events) + 1:06d}", DAY, now, **values))

    def receipt(phase, now, price, position):
        raw = {
            "version": r.protocol()["version"],
            "phase": phase,
            "source_manifest_sha256": config.source_manifest_sha256,
            "scenario_id": config.scenario_id,
            "policy_id": config.policy_id,
            "exit_plan": config.exit_plan,
            "source_session": DAY,
            "contract": "6EM5",
            "native_cursor": len(receipts),
            "executed_at_ns": now,
            "price_nano": price,
            "quantity_contracts": 1,
            "position_id": position,
            "execution_confirmed": False,
            "broker_execution_confirmed": False,
        }
        pin = r._digest(r._json(raw))
        evidence = f"receipt-{len(receipts) + 1:06d}"
        receipts.append({"evidence_id": evidence, "sha256": pin, "receipt": raw})
        return {"evidence_id": evidence, "paper_receipt_sha256": pin}

    event(ledger.SessionBoundary, START)
    if not no_trade:
        for index in range(2 if two else 1):
            offset = index * 30 * SECOND
            position, request = f"position-{index + 1}", f"exit-{index + 1}"
            entry_at = START + offset + 100 * MS
            entry_price = 101 * TICK
            event(
                ledger.EntryFill,
                entry_at,
                position_id=position,
                contract="6EM5",
                side=side,
                quantity_contracts=1,
                price_nano=entry_price,
                executed_at_ns=entry_at,
                **receipt("entry", entry_at, entry_price, position),
            )
            if close or unknown:
                requested = START + offset + 200 * MS
                event(
                    ledger.ExitIntent,
                    requested,
                    request_id=request,
                    position_id=position,
                    quantity_contracts=1,
                )
                if unknown:
                    event(
                        ledger.UnresolvedExit,
                        requested + r.target.EXIT_DELAY + r.target.WAIT,
                        request_id=request,
                        reason="Synthetic unresolved observation",
                    )
                else:
                    exited = START + offset + 300 * MS
                    price = exit_tick * TICK
                    event(
                        ledger.ExitFill,
                        exited,
                        request_id=request,
                        contract="6EM5",
                        quantity_contracts=1,
                        price_nano=price,
                        executed_at_ns=exited,
                        **receipt("exit", exited, price, position),
                    )
    event(ledger.SessionBoundary, END)
    if carry:
        for stamp in r.target.window(NEXT_DAY):
            events.append(ledger.SessionBoundary(f"event-{len(events) + 1:06d}", NEXT_DAY, stamp))
    checkpoint = {
        "pending_entry": None,
        "hold_at_ns": None if close or unknown or no_trade else START + 100 * MS + r.target.HOLD,
        "exit_deadline_ns": None,
        "cooldown_until_ns": 0,
    }
    # The opaque fields prove project() does not access inputs, quotes or policy rows.
    plan = r.ReplayPlan(
        config,
        (object(),),
        manifest,
        pins,
        tuple(events),
        tuple(receipts),
        (object(),),
        (object(),),
        ledger.LedgerState(0, "0" * 64, None, 0, None, None, None, 0, 0, 0, 0),
        checkpoint,
    )
    return reconstruct(plan)


def repin_receipt(plan, index, mutation):
    receipts = deepcopy(plan.receipts)
    mutation(receipts[index]["receipt"])
    new_pin = r._digest(r._json(receipts[index]["receipt"]))
    old = receipts[index]["sha256"]
    receipts[index]["sha256"] = new_pin
    events = tuple(
        replace(event, paper_receipt_sha256=new_pin)
        if getattr(event, "paper_receipt_sha256", None) == old
        else event
        for event in plan.events
    )
    return reconstruct(plan, events=events, receipts=receipts)


@pytest.mark.parametrize(
    "side,exit_tick,gross",
    [
        ("long", 104, 3),
        ("short", 98, 3),
        ("long", 98, -3),
        ("short", 104, -3),
    ],
)
def test_mirrored_realized_conversion_and_no_old_friction_double_charge(side, exit_tick, gross):
    plan = tape(side=side, exit_tick=exit_tick)
    result = e.project(plan, seed(), assumptions())
    expected = 1000 + gross * 125 - 8 - 11
    assert result.gross_realized_usd_micros == gross * 125
    assert result.declared_realization_balance_usd_micros == expected
    assert result.complete_declared_equity_usd_micros == expected
    assert result.complete_declared_net_return_usd_micros == gross * 125 - 19
    assert result.original_complete_simulated_net_contract_ticks == gross - r.target.COST
    assert result.entry_fees_usd_micros == 8 and result.exit_fees_usd_micros == 11
    assert len(result.path) == len(plan.events)
    assert result.terminal_state == plan.terminal_state
    assert result.status == e.STATUS and all(value is False for _, value in result.authority_flags)


def test_entry_fee_is_immediate_and_every_unknown_carry_event_retained():
    plan = tape(close=False, unknown=True, carry=True)
    margin = e.DeclaredMargin(500, 300)
    result = e.project(plan, seed(), assumptions(margin=margin))
    entry = next(point for point in result.path if point.event_kind == "EntryFill")
    assert entry.entry_fee_debit_usd_micros == 8
    assert entry.declared_realization_balance_usd_micros == 992
    assert result.entry_fees_usd_micros == 8 and result.exit_fees_usd_micros == 0
    assert result.declared_realization_balance_usd_micros == 992
    assert result.complete_declared_equity_usd_micros is None
    assert result.complete_declared_net_return_usd_micros is None
    assert result.original_complete_simulated_net_contract_ticks is None
    assert result.declared_initial_margin_reserved_usd_micros == 500
    assert result.declared_maintenance_margin_required_usd_micros == 300
    assert result.balance_less_declared_initial_margin_usd_micros == 492
    assert result.path[-1].source_session == NEXT_DAY
    assert result.path[-1].reservation_status == "UNKNOWN"
    assert [p.event_id for p in result.path] == [v.event_id for v in plan.events]
    assert all(p.declared_initial_margin_reserved_usd_micros == 500 for p in result.path[1:])


def test_exit_reservation_does_not_double_count_margin_and_full_exit_releases_it():
    result = e.project(tape(), seed(), assumptions(margin=e.DeclaredMargin(500, 300)))
    points = {p.event_kind: p for p in result.path}
    assert points["EntryFill"].declared_initial_margin_reserved_usd_micros == 500
    assert points["ExitIntent"].reserved_exit_contracts == 1
    assert points["ExitIntent"].declared_initial_margin_reserved_usd_micros == 500
    assert points["ExitFill"].declared_initial_margin_reserved_usd_micros == 0
    assert result.declared_initial_margin_reserved_usd_micros == 0
    assert (
        result.balance_less_declared_initial_margin_usd_micros
        == result.complete_declared_equity_usd_micros
    )


def test_multiple_sequential_positions_have_exact_conservation():
    result = e.project(tape(two=True), seed(), assumptions())
    assert result.matched_receipt_count == 4
    assert result.terminal_state.closed_positions == 2
    assert result.gross_realized_usd_micros == 6 * 125
    assert result.entry_fees_usd_micros == 16 and result.exit_fees_usd_micros == 22
    assert result.declared_realization_balance_usd_micros == 1000 + 750 - 38


@pytest.mark.parametrize("margin", [None, e.DeclaredMargin(500, 300), e.DeclaredMargin(0, 0)])
def test_no_trade_keeps_seed_without_claiming_predictive_skill(margin):
    result = e.project(tape(no_trade=True), seed(), assumptions(margin=margin))
    assert len(result.path) == 2 and result.matched_receipt_count == 0
    assert result.declared_realization_balance_usd_micros == 1000
    assert result.complete_declared_net_return_usd_micros == 0
    assert result.complete_declared_equity_usd_micros == 1000
    assert result.declared_initial_margin_reserved_usd_micros == (None if margin is None else 0)
    assert result.entry_fees_usd_micros == result.exit_fees_usd_micros == 0
    assert dict(result.authority_flags)["promotion_allowed"] is False


def test_negative_balance_retained_without_successful_prefix_filter():
    result = e.project(
        tape(exit_tick=100),
        seed(initial_balance_usd_micros=5),
        assumptions(entry_fee_usd_micros_per_contract=10, exit_fee_usd_micros_per_contract=10),
    )
    assert len(result.path) == 5
    assert result.path[1].declared_realization_balance_usd_micros == -5
    assert result.path[1].realization_balance_shortfall_usd_micros == 5
    assert result.declared_realization_balance_usd_micros == -140
    assert result.realization_balance_shortfall_usd_micros == 140
    assert result.complete_declared_net_return_usd_micros == -145
    assert result.complete_declared_equity_usd_micros == -140


def test_delayed_imported_receipt_tapes_are_unsupported():
    plan = tape()
    events = tuple(
        replace(v, observed_at_ns=v.observed_at_ns + 50 * MS) if type(v) is ledger.EntryFill else v
        for v in plan.events
    )
    plan = reconstruct(plan, events=events)
    with pytest.raises(ValueError, match="immediate native fill clock"):
        e.project(plan, seed(), assumptions())


def test_unreserved_open_inventory_preserves_timer_and_null_complete_values():
    plan = tape(close=False)
    result = e.project(plan, seed(), assumptions())
    assert result.declared_checkpoint.hold_at_ns == plan.checkpoint["hold_at_ns"]
    assert result.complete_declared_equity_usd_micros is None
    assert result.complete_declared_net_return_usd_micros is None


def test_declared_pending_simulator_intention_remains_explicit_and_unknown():
    plan = tape(no_trade=True)
    plan = reconstruct(plan, config=replace(plan.config, policy_id="cvd_follow"))
    pending = {
        "position_id": "position-pending",
        "side": "long",
        "decision_ts_ns": END - 50 * MS,
        "target_ns": END + 50 * MS,
        "deadline_ns": END + 50 * MS + r.target.WAIT,
    }
    plan = replace(plan, checkpoint={**plan.checkpoint, "pending_entry": pending})
    result = e.project(plan, seed(), assumptions())
    assert asdict(result.declared_checkpoint.pending_entry) == pending
    assert result.complete_declared_equity_usd_micros is None
    assert result.complete_declared_net_return_usd_micros is None
    assert result.declared_realization_balance_usd_micros == 1000
    assert dict(result.authority_flags)["broker_execution_confirmed"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("pending_entry", True),
        ("pending_entry", {}),
        ("hold_at_ns", True),
        ("hold_at_ns", -1),
        ("hold_at_ns", 1),
        ("exit_deadline_ns", 1),
        ("cooldown_until_ns", False),
    ],
)
def test_malformed_checkpoint_refused(field, value):
    plan = tape()
    with pytest.raises(ValueError):
        e.project(
            replace(plan, checkpoint={**plan.checkpoint, field: value}), seed(), assumptions()
        )


def test_extra_checkpoint_claim_and_unknown_new_deadline_refused():
    plan = tape(unknown=True)
    with pytest.raises(ValueError):
        e.project(
            replace(plan, checkpoint={**plan.checkpoint, "healthy": True}), seed(), assumptions()
        )
    with pytest.raises(ValueError):
        e.project(
            replace(plan, checkpoint={**plan.checkpoint, "exit_deadline_ns": END + SECOND}),
            seed(),
            assumptions(),
        )


@pytest.mark.parametrize("value", [True, 1.0, "1", Decimal("1"), -1, e.MAX_MONEY + 1])
@pytest.mark.parametrize(
    "field",
    [
        "tick_value_usd_micros",
        "entry_fee_usd_micros_per_contract",
        "exit_fee_usd_micros_per_contract",
    ],
)
def test_invalid_declared_amounts_refused(field, value):
    with pytest.raises(ValueError):
        assumptions(**{field: value})


@pytest.mark.parametrize("currency", ["EUR", "USDT", "XAUUSD", "usd", "EURUSD", 0, None])
def test_no_currency_or_cfd_substitution(currency):
    with pytest.raises(ValueError):
        assumptions(account_currency=currency)


@pytest.mark.parametrize("value", [0, -1, True, 1.0, "1", e.MAX_MONEY + 1])
def test_invalid_seed_refused(value):
    with pytest.raises(ValueError):
        seed(initial_balance_usd_micros=value)


@pytest.mark.parametrize("initial,maintenance", [(1, 2), (-1, 0), (True, 0), (1, False), (1.0, 0)])
def test_invalid_margin_refused(initial, maintenance):
    with pytest.raises(ValueError):
        e.DeclaredMargin(initial, maintenance)


def test_margin_requires_exact_type_and_explicit_zero_fees_are_not_measured():
    with pytest.raises(ValueError):
        assumptions(margin={"initial": 1, "maintenance": 0})
    result = e.project(
        tape(),
        seed(),
        assumptions(entry_fee_usd_micros_per_contract=0, exit_fee_usd_micros_per_contract=0),
    )
    assert result.declared_realization_balance_usd_micros == 1375
    assert dict(result.authority_flags)["cash_balance_confirmed"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("phase", "exit"),
        ("version", "other"),
        ("contract", "EURUSD"),
        ("scenario_id", "different"),
        ("policy_id", "no_trade"),
        ("exit_plan", "time_exit"),
        ("source_manifest_sha256", "d" * 64),
        ("source_session", NEXT_DAY),
        ("price_nano", 102 * TICK),
        ("quantity_contracts", 2),
        ("quantity_contracts", True),
        ("position_id", "position-other"),
        ("executed_at_ns", START + 101 * MS),
        ("execution_confirmed", True),
        ("execution_confirmed", 0),
        ("broker_execution_confirmed", True),
        ("native_cursor", True),
        ("native_cursor", 20),
    ],
)
def test_repinned_receipt_mutations_do_not_bypass_content_contract(field, value):
    plan = repin_receipt(tape(), 0, lambda raw: raw.update({field: value}))
    with pytest.raises(ValueError):
        e.project(plan, seed(), assumptions())


@pytest.mark.parametrize("field", ["side", "observed_at_ns", "fill_confirmed", "healthy"])
def test_unsupported_added_receipt_fields_refused_even_when_repinned(field):
    plan = repin_receipt(tape(), 0, lambda raw: raw.update({field: True}))
    with pytest.raises(ValueError):
        e.project(plan, seed(), assumptions())


def test_missing_duplicate_changed_and_unused_receipt_coverage_refused():
    plan = tape()
    for receipts in (
        plan.receipts[:1],
        plan.receipts + (deepcopy(plan.receipts[0]),),
        (plan.receipts[0], plan.receipts[0]),
        tuple(reversed(plan.receipts)),
    ):
        with pytest.raises(ValueError):
            e.project(replace(plan, receipts=receipts), seed(), assumptions())
    changed = deepcopy(plan.receipts)
    changed[0]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        e.project(replace(plan, receipts=changed), seed(), assumptions())


@pytest.mark.parametrize(
    "field,value",
    [
        ("closed_gross_contract_ticks", 4),
        ("closed_net_contract_ticks", 4),
        ("closed_positions", True),
        ("closed_contracts", 2),
        ("sequence", 99),
        ("tip_sha256", "f" * 64),
        ("execution_watermark_ns", START),
    ],
)
def test_terminal_totals_and_declared_head_cannot_replace_full_reconstruction(field, value):
    plan = tape()
    with pytest.raises(ValueError):
        e.project(
            replace(plan, terminal_state=replace(plan.terminal_state, **{field: value})),
            seed(),
            assumptions(),
        )


def test_omitted_event_prefix_missing_session_boundary_and_extra_event_refused():
    plan = tape()
    for events in (plan.events[1:], plan.events[:-1], plan.events + (plan.events[-1],)):
        with pytest.raises(ValueError):
            e.project(replace(plan, events=events), seed(), assumptions())


@pytest.mark.parametrize("change", ["missing", "extra", "wrong_pin", "path_key"])
def test_source_key_and_bounded_pin_contract(change):
    plan, pins = tape(), None
    pins = dict(plan.source_pins)
    if change == "missing":
        pins.pop("six_e_position_ledger.py")
    elif change == "extra":
        pins["invented.py"] = "a" * 64
    elif change == "path_key":
        pins["../six_e_position_ledger.py"] = pins.pop("six_e_position_ledger.py")
    else:
        pins["six_e_position_ledger.py"] = "A" * 64
    with pytest.raises(ValueError):
        e.project(replace(plan, source_pins=pins), seed(), assumptions())


def test_declared_source_drift_changes_genesis_and_is_not_claimed_source_authentication():
    plan = tape()
    pins = {**plan.source_pins, "six_e_position_ledger.py": "d" * 64}
    with pytest.raises(ValueError):
        e.project(replace(plan, source_pins=pins), seed(), assumptions())
    internally_rechained = reconstruct(plan, source_pins=pins)
    result = e.project(internally_rechained, seed(), assumptions())
    assert result.status == e.STATUS
    assert dict(result.authority_flags)["source_files_authenticated"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_position_contracts", 2),
        ("extra_round_trip_ticks_per_contract", 2),
        ("simulator_version", "synthetic-alternative-v2"),
        ("policy_id", "undeclared"),
    ],
)
def test_unsupported_protocol_variants_refused(field, value):
    plan = tape()
    with pytest.raises(ValueError):
        e.project(
            replace(plan, config=replace(plan.config, **{field: value})), seed(), assumptions()
        )


def test_multi_contract_tape_refused_without_reinterpreting_original_protocol():
    plan = tape()
    events = tuple(
        replace(v, quantity_contracts=2) if hasattr(v, "quantity_contracts") else v
        for v in plan.events
    )
    with pytest.raises(ValueError, match="One full contract"):
        e.project(replace(plan, events=events), seed(), assumptions())


def test_cancellation_and_partial_protocol_variants_refused():
    plan = tape(unknown=True)
    cancel = ledger.CancelIntent("event-000005", DAY, START + 2 * SECOND, "exit-1")
    with pytest.raises(ValueError, match="cancellation variants"):
        e.project(
            replace(plan, events=plan.events[:4] + (cancel,) + plan.events[4:]),
            seed(),
            assumptions(),
        )
    # A partial close needs an initial multi-contract position, forbidden above.
    with pytest.raises(ValueError, match="partial/multi scope"):
        e.project(
            replace(plan, config=replace(plan.config, max_position_contracts=2)),
            seed(),
            assumptions(),
        )


def test_duplicate_position_identity_refused_even_with_consistent_terminal_totals():
    plan = tape(two=True)
    events = tuple(
        replace(v, position_id="position-1")
        if hasattr(v, "position_id") and v.position_id == "position-2"
        else v
        for v in plan.events
    )
    receipts = deepcopy(plan.receipts)
    for index in (2, 3):
        receipts[index]["receipt"]["position_id"] = "position-1"
        pin = r._digest(r._json(receipts[index]["receipt"]))
        old = receipts[index]["sha256"]
        receipts[index]["sha256"] = pin
        events = tuple(
            replace(v, paper_receipt_sha256=pin)
            if getattr(v, "paper_receipt_sha256", None) == old
            else v
            for v in events
        )
    plan = reconstruct(plan, events=events, receipts=receipts)
    with pytest.raises(ValueError, match="Position identity"):
        e.project(plan, seed(), assumptions())


def reindex(events):
    return tuple(replace(v, event_id=f"event-{i + 1:06d}") for i, v in enumerate(events))


def retime_exit(plan, stamp):
    receipts = deepcopy(plan.receipts)
    receipts[1]["receipt"]["executed_at_ns"] = stamp
    pin = r._digest(r._json(receipts[1]["receipt"]))
    receipts[1]["sha256"] = pin
    events = tuple(
        replace(v, observed_at_ns=stamp, executed_at_ns=stamp, paper_receipt_sha256=pin)
        if type(v) is ledger.ExitFill
        else v
        for v in plan.events
    )
    return reconstruct(plan, events=events, receipts=receipts)


@pytest.mark.parametrize(
    "offset,accepted", [(-1, False), (0, True), (r.target.WAIT, True), (r.target.WAIT + 1, False)]
)
def test_original_exit_wait_is_inclusive_without_late_reconciliation(offset, accepted):
    plan = tape()
    ready = next(v for v in plan.events if type(v) is ledger.ExitIntent).observed_at_ns
    ready += r.target.EXIT_DELAY
    plan = retime_exit(plan, ready + offset)
    if accepted:
        assert e.project(plan, seed(), assumptions()).matched_receipt_count == 2
    else:
        with pytest.raises(ValueError, match="inclusive wait"):
            e.project(plan, seed(), assumptions())


@pytest.mark.parametrize("offset", [-1, 1])
def test_unknown_has_exact_deadline(offset):
    plan = tape(unknown=True)
    events = tuple(
        replace(v, observed_at_ns=v.observed_at_ns + offset)
        if type(v) is ledger.UnresolvedExit
        else v
        for v in plan.events
    )
    plan = reconstruct(plan, events=events)
    with pytest.raises(ValueError, match="exact original exit timeout"):
        e.project(plan, seed(), assumptions())


def test_duplicate_unknown_refused_even_with_rechained_internal_ledger():
    plan = tape(unknown=True)
    events = reindex(plan.events[:-1] + (plan.events[-2], plan.events[-1]))
    plan = reconstruct(plan, events=events)
    with pytest.raises(ValueError, match="PENDING exit"):
        e.project(plan, seed(), assumptions())


def test_generic_ledger_late_fill_after_unknown_is_not_original_replay_scope():
    plan = tape(unknown=True)
    stamp = plan.events[-2].observed_at_ns + 100 * MS
    receipt = deepcopy(tape().receipts[1])
    receipt["receipt"]["executed_at_ns"] = stamp
    receipt["sha256"] = r._digest(r._json(receipt["receipt"]))
    fill = ledger.ExitFill(
        "event-000005",
        DAY,
        stamp,
        "exit-1",
        "6EM5",
        1,
        104 * TICK,
        stamp,
        receipt["evidence_id"],
        receipt["sha256"],
    )
    events = reindex(plan.events[:-1] + (fill, plan.events[-1]))
    plan = reconstruct(plan, events=events, receipts=plan.receipts + (receipt,))
    with pytest.raises(ValueError, match="PENDING exit"):
        e.project(plan, seed(), assumptions())


def reference_plan():
    plan = tape(unknown=True)
    reference = ledger.QuoteReference(
        "event-000005",
        DAY,
        END,
        "6EM5",
        END - 100 * MS,
        19,
        100 * TICK,
        101 * TICK,
    )
    return reconstruct(plan, events=reindex(plan.events[:-1] + (reference, plan.events[-1])))


def test_end_reference_is_a_cash_neutral_path_point_not_a_fill():
    plan = reference_plan()
    result = e.project(plan, seed(), assumptions(margin=e.DeclaredMargin(500, 300)))
    reference = result.path[-2]
    assert reference.event_kind == "QuoteReference"
    assert reference.gross_delta_usd_micros == 0
    assert reference.entry_fee_debit_usd_micros == reference.exit_fee_debit_usd_micros == 0
    assert reference.declared_realization_balance_usd_micros == 992
    assert reference.declared_initial_margin_reserved_usd_micros == 500
    assert result.complete_declared_net_return_usd_micros is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_cursor", 20),
        ("native_cursor", 18),
        ("observed_at_ns", END - 1),
        ("quote_at_ns", END),
        ("quote_at_ns", START - 1),
    ],
)
def test_reference_requires_final_native_cursor_and_original_quote_window(field, value):
    plan = reference_plan()
    events = tuple(
        replace(v, **{field: value}) if type(v) is ledger.QuoteReference else v for v in plan.events
    )
    with pytest.raises(ValueError, match="final native reference"):
        e.project(replace(plan, events=events), seed(), assumptions())


def test_equal_time_event_after_footer_cannot_be_hidden():
    plan = reference_plan()
    events = reindex(plan.events[:-2] + (plan.events[-1], plan.events[-2]))
    plan = reconstruct(plan, events=events)
    with pytest.raises(ValueError, match="final event"):
        e.project(plan, seed(), assumptions())


def test_initial_boundary_precedes_equal_time_first_fill():
    plan = tape()
    receipts = deepcopy(plan.receipts)
    receipts[0]["receipt"]["executed_at_ns"] = START
    receipts[0]["sha256"] = r._digest(r._json(receipts[0]["receipt"]))
    entry = replace(
        plan.events[1],
        observed_at_ns=START,
        executed_at_ns=START,
        paper_receipt_sha256=receipts[0]["sha256"],
    )
    events = reindex((entry, plan.events[0], *plan.events[2:]))
    plan = reconstruct(plan, events=events, receipts=receipts)
    with pytest.raises(ValueError, match="start boundary"):
        e.project(plan, seed(), assumptions())


def test_same_session_fill_native_cursors_must_advance():
    plan = repin_receipt(tape(), 1, lambda raw: raw.update(native_cursor=0))
    with pytest.raises(ValueError, match="fill cursors"):
        e.project(plan, seed(), assumptions())


def test_idle_policy_cannot_hide_a_trade_under_repinned_declared_receipts():
    plan = tape()
    config = replace(plan.config, policy_id="no_trade")
    receipts = deepcopy(plan.receipts)
    events = plan.events
    for receipt in receipts:
        old_pin = receipt["sha256"]
        receipt["receipt"]["policy_id"] = "no_trade"
        receipt["sha256"] = r._digest(r._json(receipt["receipt"]))
        events = tuple(
            replace(v, paper_receipt_sha256=receipt["sha256"])
            if getattr(v, "paper_receipt_sha256", None) == old_pin
            else v
            for v in events
        )
    plan = reconstruct(plan, config=config, events=events, receipts=receipts)
    with pytest.raises(ValueError, match="idle policy"):
        e.project(plan, seed(), assumptions())


def pending_plan(*, policy="cvd_follow", position="position-pending", day=DAY):
    plan = tape(no_trade=True)
    plan = reconstruct(plan, config=replace(plan.config, policy_id=policy))
    decision = r.target.window(day)[1] - 50 * MS
    pending = {
        "position_id": position,
        "side": "long",
        "decision_ts_ns": decision,
        "target_ns": decision + r.target.ENTRY_DELAY,
        "deadline_ns": decision + r.target.ENTRY_DELAY + r.target.WAIT,
    }
    return replace(plan, checkpoint={**plan.checkpoint, "pending_entry": pending})


def test_idle_policy_pending_intention_is_not_a_supported_native_checkpoint():
    with pytest.raises(ValueError, match="Idle policy"):
        e.project(pending_plan(policy="no_trade"), seed(), assumptions())


@pytest.mark.parametrize(
    "mutation",
    [
        {"side": "EURUSD"},
        {"target_ns": END},
        {"deadline_ns": True},
        {"broker_order_id": "fake"},
        {"decision_ts_ns": START - 1},
    ],
)
def test_pending_shape_and_clock_mutations_cannot_drop_uncertainty(mutation):
    plan = pending_plan()
    pending = {**plan.checkpoint["pending_entry"], **mutation}
    with pytest.raises(ValueError):
        e.project(
            replace(plan, checkpoint={**plan.checkpoint, "pending_entry": pending}),
            seed(),
            assumptions(),
        )


def test_positive_balance_below_declared_margin_is_not_called_cash_deficit_or_risk_approval():
    result = e.project(tape(unknown=True), seed(), assumptions(margin=e.DeclaredMargin(2000, 1500)))
    assert result.declared_realization_balance_usd_micros == 992
    assert result.balance_less_declared_initial_margin_usd_micros == -1008
    assert result.realization_balance_shortfall_usd_micros == 0
    assert result.complete_declared_equity_usd_micros is None
    assert dict(result.authority_flags)["risk_approved"] is False


@pytest.mark.parametrize("field,value", [("initialized_at_ns", True), ("initialized_at_ns", -1)])
def test_seed_clock_requires_bounded_integer(field, value):
    with pytest.raises(ValueError):
        seed(**{field: value})


def test_economic_overflow_and_post_event_seed_refused():
    with pytest.raises(ValueError):
        e.project(tape(), seed(), assumptions(tick_value_usd_micros=e.MAX_MONEY))
    with pytest.raises(ValueError, match="after funding"):
        e.project(tape(), seed(initialized_at_ns=START + 1), assumptions())


def test_pure_projection_does_not_read_files_replay_policy_quotes_or_modify_inputs(monkeypatch):
    plan, initial, declared = tape(), seed(), assumptions()
    before = r._json(
        {
            "manifest": plan.manifest,
            "pins": plan.source_pins,
            "events": [asdict(v) for v in plan.events],
            "receipts": plan.receipts,
            "terminal": asdict(plan.terminal_state),
            "checkpoint": plan.checkpoint,
        }
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Pure projection attempted external access or replay")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(ledger, "_metadata", forbidden)
    monkeypatch.setattr(ledger, "_fingerprints", forbidden)
    monkeypatch.setattr(r, "fingerprints", forbidden)
    monkeypatch.setattr(r, "build_plan", forbidden)
    monkeypatch.setattr(r, "_freeze", forbidden)
    monkeypatch.setattr(r.rules, "rules", forbidden)
    result = e.project(plan, initial, declared)
    after = r._json(
        {
            "manifest": plan.manifest,
            "pins": plan.source_pins,
            "events": [asdict(v) for v in plan.events],
            "receipts": plan.receipts,
            "terminal": asdict(plan.terminal_state),
            "checkpoint": plan.checkpoint,
        }
    )
    assert before == after
    assert all(flag is False for _, flag in result.authority_flags)
    with pytest.raises(FrozenInstanceError):
        result.declared_realization_balance_usd_micros = 0
    with pytest.raises(FrozenInstanceError):
        result.path[0].sequence = 0


def test_actual_synthetic_replay_plan_matches_declared_genesis():
    # This tiny empty synthetic input invokes only the already-existing planner,
    # before the pure assessor; no historical data or real orders are involved.
    import numpy as np

    source = r.ReplaySession(DAY, "6EM5", "a" * 64, (), np.empty((0, 3), dtype=np.int64))
    inputs = (source,)
    config = ledger.ScenarioConfig(
        "synthetic-original-plan",
        "no_trade",
        "bracket_exit",
        r.manifest_pin(inputs),
        r.protocol()["version"],
    )
    plan = r.build_plan(inputs, config)
    result = e.project(plan, seed(), assumptions())
    assert result.terminal_state == plan.terminal_state
    assert result.matched_receipt_count == 0 and result.complete_declared_equity_usd_micros == 1000


def test_actual_planner_closed_position_interoperability():
    from test_six_e_exit_diagnostics import closed_source, plan_for

    source = closed_source()
    plan = plan_for(source)
    initial = e.EconomicSeed(1000, r.target.window(source.source_session)[0])
    result = e.project(plan, initial, assumptions())
    assert result.terminal_state == plan.terminal_state
    assert result.matched_receipt_count == len(plan.receipts) == 2
    assert len(result.path) == len(plan.events)
    assert result.gross_realized_usd_micros == 3 * 125
    assert result.complete_declared_net_return_usd_micros == 3 * 125 - 19
    assert result.original_complete_simulated_net_contract_ticks == 2


def test_actual_planner_unknown_cross_session_carry_interoperability():
    from test_six_e_exit_diagnostics import NEXT_DAY as fixture_next_day
    from test_six_e_exit_diagnostics import closed_source, plan_for, unknown_source

    first = unknown_source()
    plan = plan_for((first, closed_source(fixture_next_day)))
    initial = e.EconomicSeed(1000, r.target.window(first.source_session)[0])
    result = e.project(plan, initial, assumptions(margin=e.DeclaredMargin(500, 300)))
    assert result.terminal_state == plan.terminal_state
    assert result.terminal_state.reservation.status == "UNKNOWN"
    assert result.matched_receipt_count == len(plan.receipts) == 1
    assert len(result.path) == len(plan.events)
    assert result.entry_fees_usd_micros == 8 and result.exit_fees_usd_micros == 0
    assert result.declared_realization_balance_usd_micros == 992
    assert result.declared_initial_margin_reserved_usd_micros == 500
    assert result.complete_declared_equity_usd_micros is None
    assert result.complete_declared_net_return_usd_micros is None
    assert result.path[-1].source_session == fixture_next_day
