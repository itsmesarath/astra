"""Finite rich bridge oracles derived from the held contract and test text.

No production or old-test module is imported. The caller supplies the independent
base oracle module explicitly. The thirteen-transition script is adapted from
the held typed-adapter test's literal script (lines 2712--3065), not its runtime.
Native absent/present record widths are independently fixed at 56/64 bytes.
"""

import copy
import math

RICH_VARIANTS = (
    "thirteen-transition",
    "thirteen-transition-two-frames",
    "after-window-event",
    "max-complete-positions",
    "cross-warmup-trade",
    "cadence-off-grid",
    "inactivity-equality",
    "inactivity-plus-one",
)


def _record(
    base, mode, action="N", side="N", *, recv=None, oid=0, price=0, size=0, flags=128, sequence=1
):
    if recv is None:
        recv = base.NOON
    return {
        "publisher_id": 111,
        "instrument_id": 7,
        "ts_event": recv - 1,
        "order_id": oid,
        "price": price,
        "size": size,
        "action": action,
        "side": side,
        "ts_recv": recv,
        "flags": flags,
        "channel_id": 2,
        "ts_in_delta": 0,
        "sequence": sequence,
        "ts_out": recv + 20 if mode else None,
        "rtype": 160,
        "record_size": 64 if mode else 56,
    }


def _fixture(base, records, member, mode):
    return {
        "context": {
            "input_version": 3,
            "upgrade_policy": "AS_IS",
            "yielded_version": 3,
            "stype_in": "parent",
            "stype_out": "instrument_id",
            "partial": [],
            "limit": None,
            "ts_out": mode,
        },
        "payload_bundle": {
            "context": {
                "codec_id": "constructed_mbo_json_v1",
                "schema_version": 1,
                "ts_out_mode": "present" if mode else "absent",
            },
            "cursor_fixture": base.cursor_fixture_body(records, member),
            "payloads": [None, *copy.deepcopy(records)],
        },
    }


def _prelude(base, fixture):
    protocol = base.expected_protocol()["dependencies"]["adapter"]
    protocol_pin, context_pin = base.digest(protocol), base.digest(fixture["context"])
    bound = base.binding_assessment_body(fixture["payload_bundle"])
    prefixes = {
        audit["decoded_position"]: base.digest(
            {
                "adapter_protocol_sha256": protocol_pin,
                "context_sha256": context_pin,
                "binding_prefix_sha256": audit["bound_prefix_sha256"],
            }
        )
        for audit in bound["audits"]
    }
    return protocol, protocol_pin, context_pin, bound, prefixes


def _finish(
    base, fixture, prelude, transitions, events, quotes, publications, intervals, quality, state
):
    protocol, protocol_pin, context_pin, bound, prefixes = prelude
    audits = []
    for audit in bound["audits"]:
        ordinal = audit["target_candidate_ordinal"]
        audits.append(
            {
                "decoded_position": audit["decoded_position"],
                "disposition": "header"
                if ordinal is None
                else transitions[ordinal - 1]["disposition"],
                "instrument_id": audit["instrument_id"],
                "target_candidate_ordinal": ordinal,
                "target_transition_ordinal": ordinal,
                "binding_prefix_sha256": audit["bound_prefix_sha256"],
                "adapter_prefix_sha256": prefixes[audit["decoded_position"]],
            }
        )
    result = {
        "status": protocol["status"],
        "protocol_sha256": protocol_pin,
        "context_sha256": context_pin,
        "binding_protocol_sha256": bound["protocol_sha256"],
        "cursor_protocol_sha256": bound["cursor_protocol_sha256"],
        "fixture_sha256": base.digest(fixture),
        "fixture": fixture,
        "binding_assessment": bound,
        "audits": audits,
        "transitions": transitions,
        "events": events,
        "quotes": quotes,
        "publications": publications,
        "inactivity_intervals": intervals,
        "clock_quality": quality,
        "exceptional_clear_count": 0,
        "terminal_state": state,
        "authority_flags": copy.deepcopy(protocol["authority_flags"]),
    }
    return result | {"assessment_sha256": base.digest(result)}


def _quality(targets, snapshots):
    return {
        "target_records": targets,
        "snapshot_records": snapshots,
        "non_snapshot_records": targets - snapshots,
        "event_after_receive": 0,
        "negative_send_delta": 0,
        "event_after_sending": 0,
        "clamped_delta": 0,
        "clock_disagreement_records": 0,
        "protected_disagreement_records": 0,
        "outside_disagreement_records": 0,
        "min_event_ahead_ns": None,
        "max_event_ahead_ns": None,
        "min_negative_delta_ns": None,
        "samples": [],
    }


def _book(orders):
    """Project this finite script's explicit order table, never a replay engine."""
    entries = [{"order_id": oid, "state": copy.deepcopy(orders[oid])} for oid in sorted(orders)]
    levels = {"A": {}, "B": {}}
    for order in orders.values():
        side, price = order["side"], order["price"]
        levels[side][price] = levels[side].get(price, 0) + order["size"]
    bids = [{"price": p, "size": levels["B"][p]} for p in sorted(levels["B"], reverse=True)]
    asks = [{"price": p, "size": levels["A"][p]} for p in sorted(levels["A"])]
    return entries, bids, asks


def _thirteen_records(base, mode):
    before = base.WARMUP - base.SECOND
    records = [_record(base, mode, "R", recv=before, flags=0)]
    for sequence, (oid, side, price, size) in enumerate(
        (
            (11, "B", 1_000_000, 10),
            (12, "A", 1_100_000, 20),
            (14, "B", 950_000, 5),
            (15, "A", 1_150_000, 10),
        ),
        2,
    ):
        records.append(
            _record(
                base,
                mode,
                "A",
                side,
                recv=before + sequence - 1,
                oid=oid,
                price=price,
                size=size,
                flags=32,
                sequence=sequence,
            )
        )
    records.append(_record(base, mode, recv=base.NOON - base.SECOND, sequence=6))
    for sequence, (action, side, oid, price, size) in enumerate(
        (
            ("T", "B", 900, 1_100_000, 4),
            ("F", "A", 12, 1_100_000, 4),
            ("C", "A", 12, 1_100_000, 4),
            ("A", "A", 13, 1_100_000, 2),
            ("M", "A", 12, 1_100_000, 18),
            ("M", "B", 11, 1_000_000, 8),
            ("N", "N", 0, 0, 0),
        ),
        7,
    ):
        records.append(
            _record(
                base,
                mode,
                action,
                side,
                oid=oid,
                price=price,
                size=size,
                flags=128 if action == "N" else 0,
                sequence=sequence,
            )
        )
    assert len(records) == 13
    return records


def _thirteen_features(base):
    values = (
        math.log1p(8),
        math.log1p(20),
        -12 / 28,
        -4 / 28,
        8 / 28,
        math.log1p(1),
        0.0,
        math.log1p(base.SECOND / 1_000_000),
        math.log1p(13),
        math.log1p(30),
        -17 / 43,
        8 / 13,
        20 / 30,
        1.0,
        1.0,
        0.0,
        0.0,
        0.0,
        math.log1p(2),
        0.0,
        0.0,
        4 / 28,
        0.0,
        0.0,
        0.0,
        0.0,
        2 / 28,
        0.0,
        0.0,
        0.0,
        4 / 28,
        4 / 28,
        4 / 28,
        0.0,
        2 / 28,
        2 / 28,
        2 / 28,
    )
    names = base.expected_protocol()["dependencies"]["adapter"]["feature_names"]
    assert len(values) == len(names) == 37
    return [[name, value] for name, value in zip(names, values, strict=True)]


def _thirteen_assessment(base, fixture):
    """Exactly thirteen transitions with literal mutation positions and metrics."""
    prelude = _prelude(base, fixture)
    prefixes = prelude[-1]
    state, orders, transitions, events, quotes, publications = (
        base.empty_state(),
        {},
        [],
        [],
        [],
        [],
    )
    metrics = {
        "A_passive": 4,
        "A_held_top_passive": 4,
        "A_linked_decrease": 4,
        "A_other_id_reload": 2,
        "A_same_id_reload": 2,
        "A_same_id_net_refresh": 2,
        "B_unlinked_decrease": 2,
    }
    execution_audit = {
        "temporal_resets": 1,
        "completed_events": 2,
        "trade_B_volume": 4,
        "fill_matched_passive_records": 1,
        "fill_matched_passive_volume": 4,
        "fill_above_displayed_volume": 0,
        "A_passive_volume": 4,
        "A_held_top_passive_volume": 4,
        "A_linked_decrease_volume": 4,
        "A_other_id_reload_volume": 2,
        "A_same_id_reload_volume": 2,
        "A_same_id_net_refresh_volume": 2,
        "B_unlinked_decrease_volume": 2,
    }
    records = fixture["payload_bundle"]["payloads"][1:]
    assert len(records) == 13
    for index, raw in enumerate(records):
        position = index + 2
        before = copy.deepcopy(orders.get(raw["order_id"]))
        last_before, initialized_before = state["last_recv_ns"], state["initialized"]
        if index == 0:
            state.update(initialized=True, last_recv_ns=base.WARMUP - base.SECOND)
        elif index < 5:
            orders[raw["order_id"]] = {
                "side": raw["side"],
                "price": raw["price"],
                "size": raw["size"],
            }
        else:
            state["last_recv_ns"] = raw["ts_recv"]
            if index >= 6:
                state["pending_target_positions"].append(position)
                state["execution_capture_positions"].append(position)
                if index == 6:
                    state["pending_trade_positions"] = [8]
                if index == 8:
                    orders[12]["size"] = 16
                elif index == 9:
                    orders[13] = {"side": "A", "price": 1_100_000, "size": 2}
                elif index == 10:
                    orders[12]["size"] = 18
                elif index == 11:
                    orders[11]["size"] = 8
        entries, bids, asks = _book(orders)
        state.update(orders=entries, bid_levels=bids, ask_levels=asks)
        event_ordinal = quote_ordinal = publication_ordinal = None
        if index in (5, 12):
            main = index == 12
            ordinal = 2 if main else 1
            time = base.NOON if main else base.NOON - base.SECOND
            members = list(range(8, 15)) if main else [7]
            event = {
                "event_ordinal": ordinal,
                "closing_decoded_position": position,
                "closing_target_transition_ordinal": index + 1,
                "ts_recv_ns": time,
                "target_positions": members,
                "trade_positions": [8] if main else [],
                "execution_capture_positions": members,
                "quote_ordinal": ordinal,
                "adapter_prefix_sha256": prefixes[position],
            }
            events.append(event | {"event_sha256": base.digest(event)})
            quote = {
                "quote_ordinal": ordinal,
                "event_ordinal": ordinal,
                "decoded_position": position,
                "ts_recv_ns": time,
                "bid": 1_000_000,
                "ask": 1_100_000,
                "bid_qty": 8 if main else 10,
                "ask_qty": 20,
                "prior_quote_gap_ns": base.SECOND if main else 0,
                "ofi_generation": 2,
                "bid_depth5": copy.deepcopy(bids),
                "ask_depth5": copy.deepcopy(asks),
                "adapter_prefix_sha256": prefixes[position],
            }
            quotes.append(quote | {"quote_sha256": base.digest(quote)})
            state.update(
                last_quote_ordinal=ordinal,
                ofi_generation=2,
                ofi_previous_quote_ordinal=ordinal,
                ofi_first_ts_ns=base.NOON - base.SECOND,
                ofi_events=[[base.NOON, -2]] if main else [],
                ofi_total=-2 if main else 0,
                history_ofi_generation=2,
                history_quote_ordinals=[1, 2] if main else [1],
                history_reloads=[[base.NOON - base.SECOND, 0, 0], [base.NOON, 0, 0]]
                if main
                else [[base.NOON - base.SECOND, 0, 0]],
                bid_depletions=[[base.NOON, 2]] if main else [],
                execution_last_ts_ns=time,
                execution_audit=copy.deepcopy(execution_audit)
                if main
                else {"completed_events": 1, "temporal_resets": 1},
                execution_events=[[base.NOON, metrics]] if main else [],
                execution_totals=metrics if main else {},
                next_publication_ns=base.NOON + base.SECOND if main else base.NOON,
                watch_since_ns=time,
                pending_target_positions=[],
                pending_trade_positions=[],
                execution_capture_positions=[],
                flow_events=[[base.NOON, 4, 1, 0]] if main else [],
                cvd=4 if main else 0,
                known_trades=1 if main else 0,
            )
            if main:
                publication = {
                    "publication_ordinal": 1,
                    "quote_ordinal": 2,
                    "event_ordinal": 2,
                    "decoded_position": 14,
                    "ts_recv_ns": base.NOON,
                    "adapter_prefix_sha256": prefixes[14],
                    "features": _thirteen_features(base),
                }
                publications.append(publication | {"publication_sha256": base.digest(publication)})
            event_ordinal = quote_ordinal = ordinal
            publication_ordinal = 1 if main else None
        transitions.append(
            {
                "decoded_position": position,
                "target_transition_ordinal": index + 1,
                "disposition": "target_reset"
                if index == 0
                else "target_snapshot"
                if index < 5
                else "target_record",
                "snapshot": 1 <= index < 5,
                "exceptional_closed_clear": False,
                "order_id": raw["order_id"],
                "before": before,
                "after": copy.deepcopy(orders.get(raw["order_id"])),
                "initialized_before": initialized_before,
                "initialized_after": True,
                "last_recv_before": last_before,
                "last_recv_after": state["last_recv_ns"],
                "event_ordinal": event_ordinal,
                "quote_ordinal": quote_ordinal,
                "publication_ordinal": publication_ordinal,
                "state_sha256": base.digest(state),
            }
        )
    state.update(
        ofi_generation=3,
        ofi_previous_quote_ordinal=None,
        ofi_first_ts_ns=None,
        ofi_events=[],
        ofi_total=0,
        window_closed=True,
    )
    intervals = [
        {
            "start_ns": base.WARMUP,
            "timer_fired_ns": base.WARMUP + 5 * base.SECOND + 1,
            "end_ns": base.NOON - base.SECOND,
            "recovered": True,
            "trigger_decoded_position": 7,
        },
        {
            "start_ns": base.NOON,
            "timer_fired_ns": base.NOON + 5 * base.SECOND + 1,
            "end_ns": base.END,
            "recovered": False,
            "trigger_decoded_position": None,
        },
    ]
    return _finish(
        base,
        fixture,
        prelude,
        transitions,
        events,
        quotes,
        publications,
        intervals,
        _quality(13, 4),
        state,
    )


def _first_idle_fixture(fixture):
    first = copy.deepcopy(fixture)
    bundle = first["payload_bundle"]
    bundle["payloads"] = bundle["payloads"][:5]
    bundle["cursor_fixture"]["items"] = bundle["cursor_fixture"]["items"][:5]
    bundle["cursor_fixture"]["declared_item_count"] = 5
    return first


def _after_window_assessment(base, fixture):
    """Literal noon event plus END event; no protected quote at the right edge.

    Derived from held test text expected_two_event_assessment, not an execution.
    The baseline contains the actual complete member assertion even though its
    first-five declaration is used only to construct the common prefix states.
    """
    result = base.adapter_assessment_body(_first_idle_fixture(fixture))
    prelude = _prelude(base, fixture)
    bound, prefixes = prelude[3:]
    result.update(fixture=fixture, fixture_sha256=base.digest(fixture), binding_assessment=bound)
    final_bound = bound["audits"][-1]
    prefix = prefixes[6]
    result["audits"].append(
        {
            "decoded_position": 6,
            "disposition": "target_record",
            "instrument_id": 7,
            "target_candidate_ordinal": 5,
            "target_transition_ordinal": 5,
            "binding_prefix_sha256": final_bound["bound_prefix_sha256"],
            "adapter_prefix_sha256": prefix,
        }
    )
    result["terminal_state"]["last_recv_ns"] = base.END
    result["transitions"].append(
        {
            "decoded_position": 6,
            "target_transition_ordinal": 5,
            "disposition": "target_record",
            "snapshot": False,
            "exceptional_closed_clear": False,
            "order_id": 0,
            "before": None,
            "after": None,
            "initialized_before": True,
            "initialized_after": True,
            "last_recv_before": base.NOON,
            "last_recv_after": base.END,
            "event_ordinal": 2,
            "quote_ordinal": None,
            "publication_ordinal": None,
            "state_sha256": base.digest(result["terminal_state"]),
        }
    )
    event = {
        "event_ordinal": 2,
        "closing_decoded_position": 6,
        "closing_target_transition_ordinal": 5,
        "ts_recv_ns": base.END,
        "target_positions": [6],
        "trade_positions": [],
        "execution_capture_positions": [],
        "quote_ordinal": None,
        "adapter_prefix_sha256": prefix,
    }
    result["events"].append(event | {"event_sha256": base.digest(event)})
    result["inactivity_intervals"][-1]["trigger_decoded_position"] = 6
    result["clock_quality"] = _quality(5, 2)
    result.pop("assessment_sha256")
    return result | {"assessment_sha256": base.digest(result)}


def _many_noop_assessment(base, fixture):
    """Exact R/two-snapshot/124-N script from held independent literal test text.

    First 32 N clocks are one second apart; the next 92 equal clock 32. The
    five-second boundary includes equality. This is one finite measured example
    after root execution, never a universal capacity claim or historical input.
    """
    assert len(fixture["payload_bundle"]["payloads"]) == 128
    first = base.adapter_assessment_body(_first_idle_fixture(fixture))
    prelude = _prelude(base, fixture)
    prefixes = prelude[-1]
    transitions = copy.deepcopy(first["transitions"][:3])
    state = base.empty_state()
    state.update(
        initialized=True,
        last_recv_ns=base.WARMUP - base.SECOND,
        orders=[
            {"order_id": 11, "state": {"side": "B", "price": 1_000_001, "size": 10}},
            {"order_id": 12, "state": {"side": "A", "price": 1_100_001, "size": 20}},
        ],
        bid_levels=[{"price": 1_000_001, "size": 10}],
        ask_levels=[{"price": 1_100_001, "size": 20}],
    )
    events, quotes, publications = [], [], []
    times = [base.NOON + min(index, 31) * base.SECOND for index in range(124)]
    for index, time in enumerate(times):
        ordinal, position = index + 1, index + 5
        last_receive = state["last_recv_ns"]
        gap = 0 if index == 0 else time - times[index - 1]
        history = [
            previous + 1
            for previous in range(index + 1)
            if times[previous] >= time - 5 * base.SECOND
        ]
        ofi = [
            [times[previous], 0]
            for previous in range(1, index + 1)
            if times[previous] >= time - 5 * base.SECOND
        ]
        event = {
            "event_ordinal": ordinal,
            "closing_decoded_position": position,
            "closing_target_transition_ordinal": ordinal + 3,
            "ts_recv_ns": time,
            "target_positions": [position],
            "trade_positions": [],
            "execution_capture_positions": [position],
            "quote_ordinal": ordinal,
            "adapter_prefix_sha256": prefixes[position],
        }
        events.append(event | {"event_sha256": base.digest(event)})
        quote = {
            "quote_ordinal": ordinal,
            "event_ordinal": ordinal,
            "decoded_position": position,
            "ts_recv_ns": time,
            "bid": 1_000_001,
            "ask": 1_100_001,
            "bid_qty": 10,
            "ask_qty": 20,
            "prior_quote_gap_ns": gap,
            "ofi_generation": 2,
            "bid_depth5": [{"price": 1_000_001, "size": 10}],
            "ask_depth5": [{"price": 1_100_001, "size": 20}],
            "adapter_prefix_sha256": prefixes[position],
        }
        quotes.append(quote | {"quote_sha256": base.digest(quote)})
        if index < 32:
            features = base.idle_features()
            features[7][1] = math.log1p(gap / 1_000_000)
            features[17][1] = 0 if len(history) == 1 else 0.0
            features[18][1] = math.log1p(len(history))
            publication = {
                "publication_ordinal": ordinal,
                "quote_ordinal": ordinal,
                "event_ordinal": ordinal,
                "decoded_position": position,
                "ts_recv_ns": time,
                "adapter_prefix_sha256": prefixes[position],
                "features": features,
            }
            publications.append(publication | {"publication_sha256": base.digest(publication)})
        state.update(
            last_recv_ns=time,
            last_quote_ordinal=ordinal,
            ofi_generation=2,
            ofi_previous_quote_ordinal=ordinal,
            ofi_first_ts_ns=base.NOON,
            ofi_events=ofi,
            ofi_total=0,
            history_ofi_generation=2,
            history_quote_ordinals=history,
            history_reloads=[[times[previous - 1], 0, 0] for previous in history],
            execution_last_ts_ns=time,
            execution_audit={"completed_events": ordinal, "temporal_resets": 1},
            next_publication_ns=base.NOON + min(ordinal, 32) * base.SECOND,
            watch_since_ns=time,
        )
        transitions.append(
            {
                "decoded_position": position,
                "target_transition_ordinal": ordinal + 3,
                "disposition": "target_record",
                "snapshot": False,
                "exceptional_closed_clear": False,
                "order_id": 0,
                "before": None,
                "after": None,
                "initialized_before": True,
                "initialized_after": True,
                "last_recv_before": last_receive,
                "last_recv_after": time,
                "event_ordinal": ordinal,
                "quote_ordinal": ordinal,
                "publication_ordinal": ordinal if index < 32 else None,
                "state_sha256": base.digest(state),
            }
        )
    state.update(
        ofi_generation=3,
        ofi_previous_quote_ordinal=None,
        ofi_first_ts_ns=None,
        ofi_events=[],
        ofi_total=0,
        window_closed=True,
    )
    intervals = [
        copy.deepcopy(first["inactivity_intervals"][0]),
        {
            "start_ns": times[-1],
            "timer_fired_ns": times[-1] + 5 * base.SECOND + 1,
            "end_ns": base.END,
            "recovered": False,
            "trigger_decoded_position": None,
        },
    ]
    return _finish(
        base,
        fixture,
        prelude,
        transitions,
        events,
        quotes,
        publications,
        intervals,
        _quality(127, 2),
        state,
    )


def _cross_warmup_assessment(base, fixture):
    """Five literal transitions; full T/F event differs from captured F suffix.

    Held test text 3181--3203 fixes target(5,6), trade(5), capture(6), CVD3,
    absorption3/30 and fill-without-trade. The complete pre/post states below
    follow the documented day/timer rules: T/F do not mutate standing orders;
    the pre-warmup T is queued, not captured; completion timestamps its flow.
    No production engine or runtime output supplies any expected state.
    """
    assert len(fixture["payload_bundle"]["payloads"]) == 6
    prelude = _prelude(base, fixture)
    prefixes = prelude[-1]
    before = base.WARMUP - base.SECOND
    bid = {"side": "B", "price": 1_000_001, "size": 10}
    ask = {"side": "A", "price": 1_100_001, "size": 20}
    state, transitions = base.empty_state(), []
    state.update(initialized=True, last_recv_ns=before)
    for index in range(3):
        if index == 1:
            state.update(
                orders=[{"order_id": 11, "state": copy.deepcopy(bid)}],
                bid_levels=[{"price": 1_000_001, "size": 10}],
            )
        elif index == 2:
            state["orders"].append({"order_id": 12, "state": copy.deepcopy(ask)})
            state["ask_levels"] = [{"price": 1_100_001, "size": 20}]
        transitions.append(
            {
                "decoded_position": index + 2,
                "target_transition_ordinal": index + 1,
                "disposition": "target_reset" if index == 0 else "target_snapshot",
                "snapshot": index != 0,
                "exceptional_closed_clear": False,
                "order_id": (0, 11, 12)[index],
                "before": None,
                "after": copy.deepcopy((None, bid, ask)[index]),
                "initialized_before": index != 0,
                "initialized_after": True,
                "last_recv_before": None if index == 0 else before,
                "last_recv_after": before,
                "event_ordinal": None,
                "quote_ordinal": None,
                "publication_ordinal": None,
                "state_sha256": base.digest(state),
            }
        )
    # T at WARMUP-1 contributes to pending event/trade lists, not capture/flow yet.
    state.update(
        last_recv_ns=base.WARMUP - 1, pending_target_positions=[5], pending_trade_positions=[5]
    )
    transitions.append(
        {
            "decoded_position": 5,
            "target_transition_ordinal": 4,
            "disposition": "target_record",
            "snapshot": False,
            "exceptional_closed_clear": False,
            "order_id": 900,
            "before": None,
            "after": None,
            "initialized_before": True,
            "initialized_after": True,
            "last_recv_before": before,
            "last_recv_after": base.WARMUP - 1,
            "event_ordinal": None,
            "quote_ordinal": None,
            "publication_ordinal": None,
            "state_sha256": base.digest(state),
        }
    )
    # The noon F is the sole captured row, so its audit cannot match the earlier T.
    event = {
        "event_ordinal": 1,
        "closing_decoded_position": 6,
        "closing_target_transition_ordinal": 5,
        "ts_recv_ns": base.NOON,
        "target_positions": [5, 6],
        "trade_positions": [5],
        "execution_capture_positions": [6],
        "quote_ordinal": 1,
        "adapter_prefix_sha256": prefixes[6],
    }
    event["event_sha256"] = base.digest(event)
    quote = {
        "quote_ordinal": 1,
        "event_ordinal": 1,
        "decoded_position": 6,
        "ts_recv_ns": base.NOON,
        "bid": 1_000_001,
        "ask": 1_100_001,
        "bid_qty": 10,
        "ask_qty": 20,
        "prior_quote_gap_ns": 0,
        "ofi_generation": 2,
        "bid_depth5": [{"price": 1_000_001, "size": 10}],
        "ask_depth5": [{"price": 1_100_001, "size": 20}],
        "adapter_prefix_sha256": prefixes[6],
    }
    quote["quote_sha256"] = base.digest(quote)
    features = base.idle_features()
    features[4][1] = 2 * 3 / 30
    features[5][1] = math.log1p(1)
    features[21][1] = 3 / 30
    publication = {
        "publication_ordinal": 1,
        "quote_ordinal": 1,
        "event_ordinal": 1,
        "decoded_position": 6,
        "ts_recv_ns": base.NOON,
        "adapter_prefix_sha256": prefixes[6],
        "features": features,
    }
    publication["publication_sha256"] = base.digest(publication)
    state.update(
        last_recv_ns=base.NOON,
        pending_target_positions=[],
        pending_trade_positions=[],
        execution_capture_positions=[],
        last_quote_ordinal=1,
        flow_events=[[base.NOON, 3, 1, 0]],
        cvd=3,
        known_trades=1,
        ofi_generation=2,
        ofi_previous_quote_ordinal=1,
        ofi_first_ts_ns=base.NOON,
        history_ofi_generation=2,
        history_quote_ordinals=[1],
        history_reloads=[[base.NOON, 0, 0]],
        execution_last_ts_ns=base.NOON,
        execution_audit={
            "temporal_resets": 1,
            "completed_events": 1,
            "fill_without_trade_records": 1,
            "fill_without_trade_volume": 3,
        },
        next_publication_ns=base.NOON + base.SECOND,
        watch_since_ns=base.NOON,
    )
    transitions.append(
        {
            "decoded_position": 6,
            "target_transition_ordinal": 5,
            "disposition": "target_record",
            "snapshot": False,
            "exceptional_closed_clear": False,
            "order_id": 12,
            "before": copy.deepcopy(ask),
            "after": copy.deepcopy(ask),
            "initialized_before": True,
            "initialized_after": True,
            "last_recv_before": base.WARMUP - 1,
            "last_recv_after": base.NOON,
            "event_ordinal": 1,
            "quote_ordinal": 1,
            "publication_ordinal": 1,
            "state_sha256": base.digest(state),
        }
    )
    state.update(
        ofi_generation=3, ofi_previous_quote_ordinal=None, ofi_first_ts_ns=None, window_closed=True
    )
    intervals = [
        {
            "start_ns": base.WARMUP,
            "timer_fired_ns": base.WARMUP + 5 * base.SECOND + 1,
            "end_ns": base.NOON,
            "recovered": True,
            "trigger_decoded_position": 6,
        },
        {
            "start_ns": base.NOON,
            "timer_fired_ns": base.NOON + 5 * base.SECOND + 1,
            "end_ns": base.END,
            "recovered": False,
            "trigger_decoded_position": None,
        },
    ]
    return _finish(
        base,
        fixture,
        prelude,
        transitions,
        [event],
        [quote],
        [publication],
        intervals,
        _quality(5, 2),
        state,
    )


def _timing_rows(base, variant):
    """Closed literal schedules, not scheduling logic applied to arbitrary input.

    Each row is (NOON offset, bid quantity, publication ordinal or None,
    OFI generation, retained quote ordinals, OFI event ordinal/quantity pairs,
    OFI first quote ordinal, cumulative execution temporal resets, next-due offset).
    """
    second = base.SECOND
    if variant == "cadence-off-grid":
        return (
            (123, 10, 1, 2, (1,), (), 1, 1, second + 123),
            (123, 12, None, 2, (1, 2), ((2, 2),), 1, 1, second + 123),
            (second + 122, 12, None, 2, (1, 2, 3), ((2, 2), (3, 0)), 1, 1, second + 123),
            (
                second + 123,
                12,
                2,
                2,
                (1, 2, 3, 4),
                ((2, 2), (3, 0), (4, 0)),
                1,
                1,
                2 * second + 123,
            ),
            (
                4 * second + 140,
                12,
                3,
                2,
                (1, 2, 3, 4, 5),
                ((2, 2), (3, 0), (4, 0), (5, 0)),
                1,
                1,
                5 * second + 140,
            ),
        )
    if variant == "inactivity-equality":
        return (
            (0, 10, 1, 2, (1,), (), 1, 1, second),
            (5 * second, 10, 2, 2, (1, 2), ((2, 0),), 1, 1, 6 * second),
        )
    assert variant == "inactivity-plus-one"
    return (
        (0, 10, 1, 2, (1,), (), 1, 1, second),
        (5 * second + 1, 10, 2, 3, (2,), (), 2, 2, 6 * second + 1),
    )


def _timing_records(base, mode, variant):
    rows = _timing_rows(base, variant)
    records = base.minimal_payloads(mode)[:3]
    for index, row in enumerate(rows):
        time, bid_quantity = base.NOON + row[0], row[1]
        if variant == "cadence-off-grid" and index == 1:
            records.append(
                _record(
                    base,
                    mode,
                    "M",
                    "B",
                    recv=time,
                    oid=11,
                    price=1_000_001,
                    size=bid_quantity,
                    sequence=index + 4,
                )
            )
        else:
            records.append(_record(base, mode, recv=time, sequence=index + 4))
    return records


def _timing_features(base, bid_quantity, ofi_total, gap, history_count):
    """Complete fixed-standing-book numerical row for these three schedules."""
    depth = bid_quantity + 20
    imbalance = (bid_quantity - 20) / depth
    values = (
        math.log1p(bid_quantity),
        math.log1p(20),
        imbalance,
        2 * ofi_total / depth,
        0.0,
        0.0,
        0.0,
        math.log1p(gap / 1_000_000),
        math.log1p(bid_quantity),
        math.log1p(20),
        imbalance,
        1.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0 if history_count == 1 else 0.0,
        math.log1p(history_count),
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    )
    names = base.expected_protocol()["dependencies"]["adapter"]["feature_names"]
    assert len(values) == len(names) == 37
    return [[name, value] for name, value in zip(names, values, strict=True)]


def _timing_assessment(base, fixture, variant):
    """Complete expectations for explicit cadence and strict-inactivity rows.

    Source grounding: held typed-adapter tests 3375--3425, _advance_timers strict
    greater-than rule, actual-time next-publication assignment, five-second
    inclusive history/OFI expiry and execution temporal-reset equality rule.
    Every publication, generation and retained queue is fixed in _timing_rows.
    """
    rows = _timing_rows(base, variant)
    assert len(fixture["payload_bundle"]["payloads"]) == len(rows) + 4
    prelude = _prelude(base, fixture)
    prefixes = prelude[-1]
    before = base.WARMUP - base.SECOND
    bid = {"side": "B", "price": 1_000_001, "size": 10}
    ask = {"side": "A", "price": 1_100_001, "size": 20}
    state, transitions = base.empty_state(), []
    state.update(initialized=True, last_recv_ns=before)
    for index in range(3):
        if index == 1:
            state.update(
                orders=[{"order_id": 11, "state": copy.deepcopy(bid)}],
                bid_levels=[{"price": 1_000_001, "size": 10}],
            )
        elif index == 2:
            state["orders"].append({"order_id": 12, "state": copy.deepcopy(ask)})
            state["ask_levels"] = [{"price": 1_100_001, "size": 20}]
        transitions.append(
            {
                "decoded_position": index + 2,
                "target_transition_ordinal": index + 1,
                "disposition": "target_reset" if index == 0 else "target_snapshot",
                "snapshot": index != 0,
                "exceptional_closed_clear": False,
                "order_id": (0, 11, 12)[index],
                "before": None,
                "after": copy.deepcopy((None, bid, ask)[index]),
                "initialized_before": index != 0,
                "initialized_after": True,
                "last_recv_before": None if index == 0 else before,
                "last_recv_after": before,
                "event_ordinal": None,
                "quote_ordinal": None,
                "publication_ordinal": None,
                "state_sha256": base.digest(state),
            }
        )
    times = [base.NOON + row[0] for row in rows]
    events, quotes, publications = [], [], []
    for index, row in enumerate(rows):
        _, quantity, publication_ordinal, generation, history, ofi, first_quote, resets, due = row
        time, ordinal, position = times[index], index + 1, index + 5
        last_receive = state["last_recv_ns"]
        gap = 0 if index == 0 else time - times[index - 1]
        modified = variant == "cadence-off-grid" and index == 1
        old_order = copy.deepcopy(state["orders"][0]["state"]) if modified else None
        bid = {"side": "B", "price": 1_000_001, "size": quantity}
        state["orders"][0]["state"] = copy.deepcopy(bid)
        state["bid_levels"] = [{"price": 1_000_001, "size": quantity}]
        event = {
            "event_ordinal": ordinal,
            "closing_decoded_position": position,
            "closing_target_transition_ordinal": ordinal + 3,
            "ts_recv_ns": time,
            "target_positions": [position],
            "trade_positions": [],
            "execution_capture_positions": [position],
            "quote_ordinal": ordinal,
            "adapter_prefix_sha256": prefixes[position],
        }
        events.append(event | {"event_sha256": base.digest(event)})
        quote = {
            "quote_ordinal": ordinal,
            "event_ordinal": ordinal,
            "decoded_position": position,
            "ts_recv_ns": time,
            "bid": 1_000_001,
            "ask": 1_100_001,
            "bid_qty": quantity,
            "ask_qty": 20,
            "prior_quote_gap_ns": gap,
            "ofi_generation": generation,
            "bid_depth5": [{"price": 1_000_001, "size": quantity}],
            "ask_depth5": [{"price": 1_100_001, "size": 20}],
            "adapter_prefix_sha256": prefixes[position],
        }
        quotes.append(quote | {"quote_sha256": base.digest(quote)})
        ofi_events = [[times[event_ordinal - 1], amount] for event_ordinal, amount in ofi]
        ofi_total = sum(amount for _, amount in ofi)
        if publication_ordinal is not None:
            publication = {
                "publication_ordinal": publication_ordinal,
                "quote_ordinal": ordinal,
                "event_ordinal": ordinal,
                "decoded_position": position,
                "ts_recv_ns": time,
                "adapter_prefix_sha256": prefixes[position],
                "features": _timing_features(base, quantity, ofi_total, gap, len(history)),
            }
            publications.append(publication | {"publication_sha256": base.digest(publication)})
        state.update(
            last_recv_ns=time,
            last_quote_ordinal=ordinal,
            ofi_generation=generation,
            ofi_previous_quote_ordinal=ordinal,
            ofi_first_ts_ns=times[first_quote - 1],
            ofi_events=ofi_events,
            ofi_total=ofi_total,
            history_ofi_generation=generation,
            history_quote_ordinals=list(history),
            history_reloads=[[times[previous - 1], 0, 0] for previous in history],
            execution_last_ts_ns=time,
            execution_audit={"completed_events": ordinal, "temporal_resets": resets},
            next_publication_ns=base.NOON + due,
            watch_since_ns=time,
        )
        transitions.append(
            {
                "decoded_position": position,
                "target_transition_ordinal": ordinal + 3,
                "disposition": "target_record",
                "snapshot": False,
                "exceptional_closed_clear": False,
                "order_id": 11 if modified else 0,
                "before": old_order,
                "after": copy.deepcopy(bid) if modified else None,
                "initialized_before": True,
                "initialized_after": True,
                "last_recv_before": last_receive,
                "last_recv_after": time,
                "event_ordinal": ordinal,
                "quote_ordinal": ordinal,
                "publication_ordinal": publication_ordinal,
                "state_sha256": base.digest(state),
            }
        )
    # Only the fixed plus-one family crossed a strict inactivity boundary before
    # its second quote; no elapsed-gap algorithm generates these expected rows.
    intervals = [
        {
            "start_ns": base.WARMUP,
            "timer_fired_ns": base.WARMUP + 5 * base.SECOND + 1,
            "end_ns": times[0],
            "recovered": True,
            "trigger_decoded_position": 5,
        }
    ]
    if variant == "inactivity-plus-one":
        intervals.append(
            {
                "start_ns": base.NOON,
                "timer_fired_ns": base.NOON + 5 * base.SECOND + 1,
                "end_ns": times[1],
                "recovered": True,
                "trigger_decoded_position": 6,
            }
        )
    intervals.append(
        {
            "start_ns": times[-1],
            "timer_fired_ns": times[-1] + 5 * base.SECOND + 1,
            "end_ns": base.END,
            "recovered": False,
            "trigger_decoded_position": None,
        }
    )
    state.update(
        ofi_generation=4 if variant == "inactivity-plus-one" else 3,
        ofi_previous_quote_ordinal=None,
        ofi_first_ts_ns=None,
        ofi_events=[],
        ofi_total=0,
        window_closed=True,
    )
    return _finish(
        base,
        fixture,
        prelude,
        transitions,
        events,
        quotes,
        publications,
        intervals,
        _quality(len(rows) + 3, 2),
        state,
    )


def rich_case(base, mode=False, variant="thirteen-transition"):
    """Return a complete declared fixture for one exact finite family selector."""
    assert type(mode) is bool and variant in RICH_VARIANTS
    if variant.startswith("thirteen-transition"):
        records, assessment = _thirteen_records(base, mode), _thirteen_assessment
    elif variant == "after-window-event":
        records = base.minimal_payloads(mode) + [_record(base, mode, recv=base.END, sequence=5)]
        assessment = _after_window_assessment
    elif variant == "max-complete-positions":
        records = base.minimal_payloads(mode)[:3] + [
            _record(base, mode, recv=base.NOON + min(index, 31) * base.SECOND, sequence=index + 4)
            for index in range(124)
        ]
        assessment = _many_noop_assessment
    elif variant == "cross-warmup-trade":
        records = base.minimal_payloads(mode)[:3] + [
            _record(
                base,
                mode,
                "T",
                "B",
                recv=base.WARMUP - 1,
                price=1_100_001,
                size=3,
                oid=900,
                flags=0,
                sequence=4,
            ),
            _record(
                base,
                mode,
                "F",
                "A",
                recv=base.NOON,
                price=1_100_001,
                size=3,
                oid=12,
                flags=128,
                sequence=5,
            ),
        ]
        assessment = _cross_warmup_assessment
    else:
        records = _timing_records(base, mode, variant)
        assessment = None
    case = base.native_case_from_records(
        records,
        mode,
        two_frames=variant == "thirteen-transition-two-frames",
    )
    fixture = _fixture(base, records, case["member"], mode)
    adapter = (
        _timing_assessment(base, fixture, variant)
        if assessment is None
        else assessment(base, fixture)
    )
    return case | {
        "adapter": adapter,
        "bridge": base.bridge_evidence_body(case["native"], adapter, mode),
    }
