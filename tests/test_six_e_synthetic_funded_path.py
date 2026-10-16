"""Complete invented funded-path oracles, independent of its new implementation.

Expected timelines are declared explicitly. Native chains, accounting heads,
receipt hashes, budgets and cash are reconstructed here without the new private
helpers, its submitted result, or any completed single-roundtrip plan.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import inspect
import json
import math
import socket
import subprocess
import sys
import time
from dataclasses import FrozenInstanceError, asdict, fields, replace

import pytest

from ai_trader.research import six_e_declared_admission as admission
from ai_trader.research import six_e_entry_budget as budget
from ai_trader.research import six_e_native_prefix as native
from ai_trader.research import six_e_synthetic_funded_path as walker
from ai_trader.research import six_e_synthetic_liquidity_point as point

VERSION = "six_e_synthetic_funded_path_v1"
STATUS = "constructed_funded_path_not_authenticated_execution"
SELECTOR_PROTOCOL = "d85e79987b12130f4dd54e106a247e621b96dba7ab0bdf1c9c267b4295076f6e"
START, PUB, END = 10_000_000_000, 11_000_000_000, 150_000_000_000
SECOND, DELAY, WAIT = 1_000_000_000, 100_000_000, 1_000_000_000
HOLD, COOLDOWN, BUFFER = 15_000_000_000, 10_000_000_000, 18_000_000_000
TICK, PRICE, MAX_INT = 50_000, 1_000_000_000, 2**63 - 1
SOURCE = "a" * 64
FEATURES = (
    "log_bid_qty",
    "log_ask_qty",
    "queue_imbalance",
    "normalized_ofi_5s",
    "normalized_cvd_5s",
    "log_known_trades_5s",
    "unknown_trade_fraction_5s",
    "log_prior_quote_gap_ms",
    "log_bid_depth5",
    "log_ask_depth5",
    "depth5_imbalance",
    "bid_top_share5",
    "ask_top_share5",
    "bid_span5_ticks",
    "ask_span5_ticks",
    "mid_change_5s_ticks",
    "mid_range_5s_ticks",
    "mid_travel_5s_ticks",
    "log_quote_events_5s",
    "normalized_bid_reload_5s",
    "normalized_ask_reload_5s",
    "buy_absorption_proxy_5s",
    "sell_absorption_proxy_5s",
    "bid_passive_5s",
    "bid_held_top_passive_5s",
    "bid_linked_decrease_5s",
    "bid_unlinked_decrease_5s",
    "bid_same_id_reload_5s",
    "bid_other_id_reload_5s",
    "bid_same_id_net_refresh_5s",
    "ask_passive_5s",
    "ask_held_top_passive_5s",
    "ask_linked_decrease_5s",
    "ask_unlinked_decrease_5s",
    "ask_same_id_reload_5s",
    "ask_other_id_reload_5s",
    "ask_same_id_net_refresh_5s",
)
POLICIES = ("cvd_follow", "liquidity_follow", "absorption_fade", "no_trade")
CONTRACTS = ("6EM5", "6EU5", "6EZ5", "6EH6")
AUTHORITY_NAMES = """
absence_of_eligible_fill_verified account_authenticated accounting_admission_authorized
accounting_transition_authorized admission_authorized broker_execution_confirmed
calendar_verified cash_balance_confirmed cash_confirmed causal_features_verified
cfd_execution_confirmed complete_decision_quote_audit_verified complete_records_authenticated
complete_session_verified consumer_coverage_verified cpu_training
cross_call_continuity_authenticated eligibility_verified execution_assumptions_validated
execution_authorized execution_confirmed feed_authenticated genesis_authenticated
independent_holdout independent_validation input_authenticated margin_confirmed
margin_requirement_confirmed native_accounting_history_verified
original_strategy_integration_verified original_strategy_selection_verified
prefix_authenticated promotion_allowed publication_event_authenticated qwen_training
receipt_authenticated receipt_provenance_authenticated receipt_provenance_verified
reservation_created reserved_outcomes_opened resume_authorized risk_approved risk_confirmed
runtime_authenticated scoring_authorized snapshot_prefix_authenticated source_authenticated
source_files_authenticated source_integrity_verified storage_authorized storage_resume_authorized
strategy_scoring_allowed timeout_authorized timer_elapsed_verified trading_enabled
training_eligible training_enabled
""".split()
FLAGS = tuple((name, False) for name in sorted(AUTHORITY_NAMES))
HELPER_PINS = {
    "src/ai_trader/research/six_e_native_prefix.py": (
        "ae1a7e98aec517e1aa9bcd45f869040d812cfbb19190313b240a5313dca748b5"
    ),
    "src/ai_trader/research/six_e_declared_admission.py": (
        "69f1850ab6f7721005b47bf798e1960d1b3081021f0e9b3bc8240aafe4da5abb"
    ),
    "src/ai_trader/research/six_e_entry_budget.py": (
        "be3e0b924356b1090dff802cbb8be3059aec81002d550afebc8ef1ef475b72d6"
    ),
    "src/ai_trader/research/six_e_declared_economics.py": (
        "d45137f63c82afcce41d4214546d5ec1a1402487e8f91f02fd90d6617e627c85"
    ),
    "src/ai_trader/research/six_e_native_admission_assessment.py": (
        "5810d5213ce03bf326fee97e2252dbfe197cb93400cced4fac91a80723b0fcb6"
    ),
    "src/ai_trader/research/six_e_synthetic_liquidity_point.py": (
        "4cba581af818c9fb9b5ad9aef876216350b4bff5e1368e2afb4355754c46b35e"
    ),
}
TEMPLATES = {
    "candidate_id": "synthetic-candidate-{ordinal:04d}",
    "clock_event_id": "synthetic-publication-clock-{ordinal:04d}",
    "request_event_id": "synthetic-admission-request-{ordinal:04d}",
    "admission_id": "synthetic-admission-{ordinal:04d}",
    "entry_outcome_event_id": "synthetic-entry-outcome-{ordinal:04d}",
    "entry_receipt_id": "synthetic-entry-receipt-{ordinal:04d}",
    "exit_request_event_id": "synthetic-exit-request-{ordinal:04d}",
    "exit_request_id": "synthetic-exit-{ordinal:04d}",
    "exit_outcome_event_id": "synthetic-exit-outcome-{ordinal:04d}",
    "exit_receipt_id": "synthetic-exit-receipt-{ordinal:04d}",
}


def canonical(body):
    return json.dumps(
        body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(body):
    return hashlib.sha256(canonical(body)).hexdigest()


def protocol_body():
    return {
        "version": VERSION,
        "status": STATUS,
        "selector_protocol_sha256": SELECTOR_PROTOCOL,
        "helper_source_pins": HELPER_PINS,
        "supported_contracts": CONTRACTS,
        "policies": POLICIES,
        "exit_plans": ("time_exit", "bracket_exit"),
        "tick_nano": TICK,
        "entry_delay_ns": DELAY,
        "entry_wait_ns": WAIT,
        "exit_delay_ns": DELAY,
        "exit_wait_ns": WAIT,
        "hold_ns": HOLD,
        "cooldown_ns": COOLDOWN,
        "end_buffer_ns": BUFFER,
        "min_publication_cadence_ns": SECOND,
        "target_ticks": 3,
        "stop_ticks": -3,
        "comparator_cost_ticks": 1,
        "quantity_contracts": 1,
        "max_quotes": 128,
        "min_publications": 1,
        "max_publications": 4,
        "max_accounting_records": 20,
        "max_canonical_bytes": 262144,
        "max_fixture_end_ns": 9223372026854775807,
        "selection_order": (
            "ineligible",
            "inventory_blocked",
            "pending_entry_blocked",
            "cooldown",
            "no_signal",
            "candidate",
        ),
        "quote_order": (
            "elapsed_deadlines_and_due_hold",
            "consume_quote",
            "entry_candidate",
            "bracket_trigger",
            "exit_candidate",
            "first_cursor_publication",
        ),
        "initial_cooldown_until_ns": 0,
        "candidate_budget_mapping": {
            "declared_budget_available": "entry_selected",
            "declared_budget_insufficient": "budget_denied",
            "budget_undetermined": "budget_undetermined",
        },
        "denied_candidate_effects": "consume_ordinal_clock_request_only",
        "deadline_rule": "inclusive_quote_deadline_close_when_next_timestamp_is_greater",
        "hold_rule": "actual_entry_plus_hold_wins_equality_closed_through_hold_minus_one",
        "eof_rule": "close_original_timers_no_new_account_clock",
        "unknown_rule": "terminal_inventory_no_later_accounting_mutation",
        "accounting_seed_rule": "one_fresh_immutable_genesis_no_reseed",
        "entry_execution_rule": "first_eligible_quote_one_tick_spread_or_permanent_refusal",
        "exit_execution_rule": "first_eligible_crossed_quote_widening_retained_no_budget_gate",
        "comparator_rule": "bracket_difference_ticks_minus_one_not_an_extra_money_debit",
        "identifier_templates": TEMPLATES,
        "authority_flags": FLAGS,
    }


def vector(sign=1, **changes):
    values = dict.fromkeys(FEATURES, 0)
    values.update(
        log_bid_qty=math.log1p(5),
        log_ask_qty=math.log1p(5),
        queue_imbalance=-sign,
        normalized_ofi_5s=sign,
        normalized_cvd_5s=sign,
        log_known_trades_5s=math.log1p(20),
        log_prior_quote_gap_ms=math.log1p(250),
        log_bid_depth5=math.log1p(20),
        log_ask_depth5=math.log1p(20),
        mid_change_5s_ticks=3 * sign,
        mid_range_5s_ticks=4,
        log_quote_events_5s=math.log1p(20),
        bid_held_top_passive_5s=0.25,
        ask_held_top_passive_5s=0.25,
        bid_other_id_reload_5s=0.1,
        ask_other_id_reload_5s=0.1,
    )
    values.update(changes)
    return tuple(values[name] for name in FEATURES)


def feature_point(index=1, sign=1, **changes):
    return point.SyntheticLiquidityPoint(
        f"synthetic-independent-point-{index}", vector(sign, **changes)
    )


def point_body(value):
    return {
        "version": "six_e_synthetic_liquidity_point_v1",
        "status": "constructed_liquidity_directions_not_strategy_integration",
        "protocol_sha256": SELECTOR_PROTOCOL,
        "point": asdict(value),
    }


def manual_directions(value):
    values = dict(zip(FEATURES, value.values, strict=True))
    cvd = (values["normalized_cvd_5s"] > 0) - (values["normalized_cvd_5s"] < 0)
    ofi = (values["normalized_ofi_5s"] > 0) - (values["normalized_ofi_5s"] < 0)
    move = (values["mid_change_5s_ticks"] > 0) - (values["mid_change_5s_ticks"] < 0)
    shared = (
        values["log_prior_quote_gap_ms"] <= math.log1p(250)
        and values["log_known_trades_5s"] > 0
        and values["unknown_trade_fraction_5s"] <= 0.1
        and min(values["log_bid_qty"], values["log_ask_qty"]) >= math.log1p(5)
        and min(values["log_bid_depth5"], values["log_ask_depth5"]) >= math.log1p(20)
        and max(values["bid_span5_ticks"], values["ask_span5_ticks"]) <= 8
        and values["log_quote_events_5s"] >= math.log1p(20)
        and values["log_known_trades_5s"] >= math.log1p(20)
    )
    follow = (
        cvd
        if shared
        and cvd == ofi == move != 0
        and abs(values["normalized_cvd_5s"]) >= 0.5
        and abs(values["normalized_ofi_5s"]) >= 0.5
        and abs(values["mid_change_5s_ticks"]) >= 1
        and values["mid_range_5s_ticks"] >= 4
        else 0
    )
    side = "ask" if cvd > 0 else "bid"
    imbalance = (values["queue_imbalance"] > 0) - (values["queue_imbalance"] < 0)
    fade = (
        -cvd
        if shared
        and cvd != 0
        and abs(values["normalized_cvd_5s"]) >= 0.5
        and abs(values["mid_change_5s_ticks"]) <= 1
        and values[f"{side}_held_top_passive_5s"] >= 0.25
        and values[f"{side}_other_id_reload_5s"] >= 0.1
        and imbalance == -cvd
        else 0
    )
    return (
        ("cvd_follow", cvd if values["log_known_trades_5s"] > 0 else 0),
        ("liquidity_follow", follow),
        ("absorption_fade", fade),
        ("no_trade", 0),
    )


def selection_body(value):
    body = {
        "version": "six_e_synthetic_liquidity_point_v1",
        "status": "constructed_liquidity_directions_not_strategy_integration",
        "protocol_sha256": SELECTOR_PROTOCOL,
        "point_sha256": digest(point_body(value)),
        "directions": manual_directions(value),
        "authority_flags": point.AUTHORITY_FLAGS,
    }
    return body | {"selection_sha256": digest(body)}


def quote(at, bid=PRICE, spread=TICK):
    return native.NativeQuote(at, bid, bid + spread)


def crossed_quote(at, side, entry_price, favorable_ticks, spread=TICK):
    crossed = entry_price + favorable_ticks * TICK * (1 if side == "long" else -1)
    return quote(at, crossed if side == "long" else crossed - spread, spread)


def fixture(rows=None, publications=(PUB,), *, start=START, end=END, contract="6EM5", label=None):
    rows = (
        tuple(rows)
        if rows is not None
        else (
            quote(PUB),
            quote(PUB + DELAY),
            quote(PUB + DELAY + HOLD),
            quote(PUB + 2 * DELAY + HOLD, PRICE + 2 * TICK),
        )
    )
    pubs = tuple(
        native.NativePublication(
            f"pub-{index + 1}",
            next(i for i, row in enumerate(rows) if row.received_at_ns == at),
            at,
        )
        for index, at in enumerate(publications)
    )
    return native.NativeFixture(
        label or "synthetic-funded-tape", contract, SOURCE, start, end, rows, pubs
    )


def genesis(
    *,
    balance=1000,
    entry=10,
    exit_fee=20,
    margin=100,
    buffer=5,
    loss=None,
    age=0,
    tick_value=125,
    start=START,
    label=None,
):
    declared_margin = None if margin is None else budget.economics.DeclaredMargin(margin, margin)
    return admission.DeclaredAdmissionGenesis(
        label or "synthetic-funded-account",
        budget.EconomicSeed(balance, start),
        budget.DeclaredEconomics("USD", tick_value, entry, exit_fee, declared_margin),
        budget.DeclaredBudgetLimits(buffer, age, loss),
    )


def bindings(tape, signs=None, eligible=None, points=None):
    signs = signs if signs is not None else [1] * len(tape.publications)
    eligible = eligible if eligible is not None else [True] * len(tape.publications)
    points = (
        points
        if points is not None
        else [feature_point(index + 1, sign) for index, sign in enumerate(signs)]
    )
    return tuple(
        walker.PublishedLiquidityBinding(pub.publication_id, flag, value, digest(point_body(value)))
        for pub, flag, value in zip(tape.publications, eligible, points, strict=True)
    )


def declaration(policy="liquidity_follow", exit_plan="time_exit", label="synthetic-funded-plan"):
    return walker.FundedPathDeclaration(label, policy, exit_plan)


def native_metadata(tape):
    return {
        "version": "six_e_native_prefix_v1",
        "source_session": tape.source_session,
        "contract": tape.contract,
        "source_sha256": tape.source_sha256,
        "start_ns": tape.start_ns,
        "end_ns": tape.end_ns,
        "tick_nano": TICK,
    }


def fixture_pin(tape):
    return digest(
        {
            "version": "six_e_native_prefix_v1",
            "kind": "complete_constructed_native_fixture",
            "metadata": native_metadata(tape),
            "quote_count": len(tape.quotes),
            "publication_count": len(tape.publications),
            "quotes": [[q.received_at_ns, q.bid_nano, q.ask_nano] for q in tape.quotes],
            "publications": [asdict(pub) for pub in tape.publications],
        }
    )


def genesis_pin(account):
    return digest(
        {
            "version": "six_e_declared_admission_v1",
            "scope": "constructed_declared_admission_not_authenticated",
            "delay_ns": DELAY,
            "wait_ns": WAIT,
            "quantity_contracts": 1,
            "genesis": asdict(account),
        }
    )


def bindings_body(bound):
    return {
        "version": VERSION,
        "status": STATUS,
        "selector_protocol_sha256": SELECTOR_PROTOCOL,
        "bindings": tuple(asdict(value) for value in bound),
    }


def declaration_body(proposal, fp, gp, bp):
    return {
        "version": VERSION,
        "status": STATUS,
        "protocol_sha256": digest(protocol_body()),
        "fixture_sha256": fp,
        "genesis_sha256": gp,
        "bindings_sha256": bp,
        "declaration": asdict(proposal),
    }


def arguments(tape, account, bound, proposal):
    fp, gp, bp = fixture_pin(tape), genesis_pin(account), digest(bindings_body(bound))
    return {
        "expected_protocol_sha256": digest(protocol_body()),
        "expected_fixture_sha256": fp,
        "expected_genesis_sha256": gp,
        "expected_bindings_sha256": bp,
        "expected_declaration_sha256": digest(declaration_body(proposal, fp, gp, bp)),
    }


def native_oracle(tape):
    """Independent rolling content chain and complete first-cursor prefixes."""
    fp = fixture_pin(tape)
    content = digest(
        {
            "version": "six_e_native_prefix_v1",
            "kind": "consumed_metadata_seed",
            "metadata": native_metadata(tape),
        }
    )
    prefixes, audits = [], []
    last, first = None, None
    for count in range(len(tape.quotes) + 1):
        if count:
            cursor, row = count - 1, tape.quotes[count - 1]
            if row.received_at_ns != last:
                first = cursor
            last = row.received_at_ns
            content = digest(
                {
                    "version": "six_e_native_prefix_v1",
                    "kind": "consumed_quote",
                    "previous_sha256": content,
                    "native_cursor": cursor,
                    "quote": [row.received_at_ns, row.bid_nano, row.ask_nano],
                }
            )
            audits.append(
                {
                    "cursor": cursor,
                    "received_at_ns": last,
                    "consumed_count": count,
                    "consumed_content_sha256": content,
                }
            )
        prefixes.append(
            {
                "fixture_sha256": fp,
                "source_session": tape.source_session,
                "contract": tape.contract,
                "source_sha256": tape.source_sha256,
                "start_ns": tape.start_ns,
                "end_ns": tape.end_ns,
                "total_quotes": len(tape.quotes),
                "total_publications": len(tape.publications),
                "consumed_count": count,
                "last_cursor": count - 1 if count else None,
                "last_received_at_ns": last,
                "current_timestamp_first_cursor": first,
                "consumed_content_sha256": content,
                "authority_flags": native.AUTHORITY_FLAGS,
            }
        )
    return prefixes, audits


def boundary_oracle(tape, prefixes, through):
    count = next(
        (i for i, q in enumerate(tape.quotes) if q.received_at_ns > through), len(tape.quotes)
    )
    return {
        "prefix": prefixes[count],
        "through_ns": through,
        "closure_kind": "next_timestamp" if count < len(tape.quotes) else "complete_eof",
        "next_cursor": count if count < len(tape.quotes) else None,
        "next_received_at_ns": tape.quotes[count].received_at_ns
        if count < len(tape.quotes)
        else None,
        "boundary_state": "CLOSED",
        "authority_flags": native.AUTHORITY_FLAGS,
    }


def publication_oracle(pub, prefixes):
    return {
        "publication_id": pub.publication_id,
        "published_cursor": pub.published_cursor,
        "received_at_ns": pub.received_at_ns,
        "prefix": prefixes[pub.published_cursor + 1],
        "boundary_state": "OPEN",
        "authority_flags": native.AUTHORITY_FLAGS,
    }


def manual_budget(account, state, at, contract):
    balance, seed = state["declared_realization_balance_usd_micros"], account.seed
    loss = max(0, seed.initial_balance_usd_micros - balance)
    proposed = max(
        0,
        seed.initial_balance_usd_micros
        - balance
        + account.economics.entry_fee_usd_micros_per_contract,
    )
    margin = account.economics.margin
    required = (
        None
        if margin is None
        else (
            account.economics.entry_fee_usd_micros_per_contract
            + margin.initial_usd_micros_per_contract
            + account.economics.exit_fee_usd_micros_per_contract
            + account.limits.cash_buffer_usd_micros
        )
    )
    reasons = []
    if required is None:
        disposition, met, reasons = "budget_undetermined", None, ["margin_not_declared"]
    else:
        if balance < required:
            reasons.append("insufficient_declared_cash")
        ceiling = account.limits.max_cumulative_realization_loss_usd_micros
        if ceiling is not None:
            if loss > ceiling:
                reasons.append("realization_loss_ceiling_exceeded")
            elif proposed > ceiling:
                reasons.append("proposed_entry_fee_exceeds_loss_ceiling")
        disposition = "declared_budget_insufficient" if reasons else "declared_budget_available"
        met = not reasons
    prefix = state["prefix"]
    return {
        "version": "six_e_declared_entry_budget_v1",
        "status": "declared_entry_budget_assessment_not_authenticated",
        "disposition": disposition,
        "snapshot": {
            "seed": asdict(seed),
            "declared_realization_balance_usd_micros": balance,
            "sequence": prefix["sequence"],
            "tip_sha256": prefix["head_sha256"],
            "last_event_at_ns": state["last_event_at_ns"],
            "observed_through_ns": prefix["complete_through_ns"],
            "remaining_position_contracts": 0,
            "reserved_exit_contracts": 0,
            "reservation_status": None,
            "pending_entry": False,
        },
        "proposal": {
            "decision_at_ns": at,
            "expected_sequence": prefix["sequence"],
            "expected_tip_sha256": prefix["head_sha256"],
            "contract": contract,
            "quantity_contracts": 1,
        },
        "economics": asdict(account.economics),
        "limits": asdict(account.limits),
        "snapshot_age_ns": 0,
        "realization_loss_from_original_seed_usd_micros": loss,
        "hypothetical_loss_after_entry_fee_usd_micros": proposed,
        "declared_requirement_usd_micros": required,
        "declared_balance_less_requirement_usd_micros": None
        if required is None
        else balance - required,
        "declared_budget_condition_met": met,
        "reasons": tuple(reasons),
        "authority_flags": budget.AUTHORITY_FLAGS,
    }


def candidate_spec(
    publication_index=0,
    *,
    disposition="entry_selected",
    entry_cursor=1,
    entry_outcome="constructed_entry_receipt",
    trigger_reason="hold_timer",
    trigger_cursor=None,
    exit_cursor=3,
    exit_outcome="constructed_exit_receipt",
):
    return {
        "publication_index": publication_index,
        "first_disposition": disposition,
        "entry_outcome_cursor": entry_cursor,
        "entry_execution_outcome": entry_outcome,
        "exit_trigger_reason": trigger_reason,
        "exit_trigger_cursor": trigger_cursor,
        "exit_outcome_cursor": exit_cursor,
        "exit_execution_outcome": exit_outcome,
    }


def complete_oracle(tape, account, bound, proposal, dispositions, specs):
    """Construct exact heads from explicit expected events, not another causal walker.

    Specs assert which source rows execute and which original boundaries close.
    No quote search, strategy scheduling, new private helper or held plan builder
    selects those rows. Publication visibility is filtered by its original cursor.
    """
    args = arguments(tape, account, bound, proposal)
    fp, gp, bp = (
        args[name]
        for name in (
            "expected_fixture_sha256",
            "expected_genesis_sha256",
            "expected_bindings_sha256",
        )
    )
    prefixes, audits = native_oracle(tape)
    prefix = {
        "sequence": 0,
        "head_sha256": gp,
        "complete_through_ns": account.seed.initialized_at_ns,
    }
    pending = position = pending_exit = None
    gross = entry_fees = exit_fees = 0
    receipt_pins, records, links, visibility, states, traces = [], [], [], [], [], []
    cooldown_events = []

    def state_body():
        liability = pending is not None or position is not None or pending_exit is not None
        balance = account.seed.initial_balance_usd_micros + gross - entry_fees - exit_fees
        entry_reserve = (
            account.economics.entry_fee_usd_micros_per_contract if pending is not None else 0
        )
        margin = account.economics.margin.initial_usd_micros_per_contract if liability else 0
        exit_reserve = account.economics.exit_fee_usd_micros_per_contract if liability else 0
        total = entry_reserve + margin + exit_reserve
        phase = (
            "ENTRY_PENDING"
            if pending is not None
            else "EXIT_UNKNOWN"
            if pending_exit is not None and pending_exit["status"] == "UNKNOWN"
            else "EXIT_PENDING"
            if pending_exit is not None
            else "OPEN"
            if position is not None
            else "FLAT"
        )
        return {
            "version": "six_e_declared_admission_v1",
            "status": "constructed_declared_admission_not_authenticated",
            "genesis_sha256": gp,
            "prefix": dict(prefix),
            "last_event_at_ns": prefix["complete_through_ns"] if records else None,
            "phase": phase,
            "declared_realization_balance_usd_micros": balance,
            "gross_realized_usd_micros": gross,
            "entry_fees_usd_micros": entry_fees,
            "exit_fees_usd_micros": exit_fees,
            "realization_balance_shortfall_usd_micros": max(0, -balance),
            "entry_fee_reserve_usd_micros": entry_reserve,
            "initial_margin_commitment_usd_micros": margin,
            "exit_fee_reserve_usd_micros": exit_reserve,
            "total_commitments_usd_micros": total,
            "available_balance_usd_micros": balance - total,
            "complete_declared_equity_usd_micros": None if liability else balance,
            "complete_declared_net_return_usd_micros": None
            if liability
            else balance - account.seed.initial_balance_usd_micros,
            "pending_entry": pending,
            "position": position,
            "pending_exit": pending_exit,
            "receipt_content_sha256s": tuple(receipt_pins),
            "authority_flags": admission.AUTHORITY_FLAGS,
        }

    states.append(state_body())

    def append(ids, pub, event, kind, payload, at, observed, *, boundary=None, publication=None):
        nonlocal prefix
        record = {
            "event_id": event,
            "expected_prefix": dict(prefix),
            "recorded_at_ns": at,
            "complete_through_ns": at,
            "payload": payload,
        }
        payload_type = {
            "publication": "ClockAdvanced"
            if event == ids["clock_event_id"]
            else "AdmissionRequested",
            "entry_candidate_quote": "EntryReceipt" if "receipt_id" in payload else "EntryUnfilled",
            "entry_deadline_boundary": "EntryUnfilled",
            "bracket_trigger_quote": "ExitRequested",
            "hold_boundary": "ExitRequested",
            "exit_candidate_quote": "ExitReceipt",
            "exit_deadline_boundary": "ExitUnknown",
        }[kind]
        head = digest(
            {"version": "six_e_declared_admission_v1", "kind": payload_type, "record": record}
        )
        index = len(records)
        records.append(record)
        links.append(
            {
                "record_index": index,
                "candidate_ordinal": len(traces) + 1,
                "publication_id": pub.publication_id,
                "event_id": event,
                "record_sha256": head,
                "native_prefix": observed,
                "kind": kind,
                "publication": publication,
                "boundary": boundary,
            }
        )
        visibility.append(
            (at, observed["last_cursor"], pub.publication_id if kind == "publication" else None)
        )
        prefix = {"sequence": index + 1, "head_sha256": head, "complete_through_ns": at}

    def receipt_pin(payload, liability, at):
        receipt = dict(payload)
        del receipt["receipt_id"]
        return digest(
            {
                "genesis_sha256": gp,
                "phase": "EntryReceipt" if "side" in payload else "ExitReceipt",
                "liability": liability,
                "position": position,
                "recorded_at_ns": at,
                "receipt": receipt,
            }
        )

    for ordinal, spec in enumerate(specs, 1):
        pub = tape.publications[spec["publication_index"]]
        origin = publication_oracle(pub, prefixes)
        ids = {name: template.format(ordinal=ordinal) for name, template in TEMPLATES.items()}
        direction = dict(manual_directions(bound[spec["publication_index"]].point))[
            proposal.policy_id
        ]
        side = "long" if direction == 1 else "short"
        assert direction in (-1, 1)
        start = len(records)
        append(
            ids,
            pub,
            ids["clock_event_id"],
            "publication",
            {},
            pub.received_at_ns,
            origin["prefix"],
            publication=origin,
        )
        states.append(state_body())
        decision = manual_budget(account, states[-1], pub.received_at_ns, tape.contract)
        mapped = {
            "declared_budget_available": "entry_selected",
            "declared_budget_insufficient": "budget_denied",
            "budget_undetermined": "budget_undetermined",
        }[decision["disposition"]]
        assert mapped == spec["first_disposition"]
        append(
            ids,
            pub,
            ids["request_event_id"],
            "publication",
            {
                "admission_id": ids["admission_id"],
                "contract": tape.contract,
                "side": side,
                "quantity_contracts": 1,
            },
            pub.received_at_ns,
            origin["prefix"],
            publication=origin,
        )
        if mapped == "entry_selected":
            pending = {
                "admission_id": ids["admission_id"],
                "contract": tape.contract,
                "side": side,
                "quantity_contracts": 1,
                "requested_at_ns": pub.received_at_ns,
                "ready_at_ns": pub.received_at_ns + DELAY,
                "deadline_ns": pub.received_at_ns + DELAY + WAIT,
            }
        states.append(state_body())
        trace = {
            "publication_id": pub.publication_id,
            "ordinal": ordinal,
            "identities": ids,
            "direction": direction,
            "side": side,
            "first_disposition": mapped,
            "budget_decision": decision,
            "record_start": start,
            "record_stop": None,
            "entry_execution_outcome": "no_pending_entry",
            "entry_outcome_cursor": None,
            "entry_outcome_at_ns": None,
            "hold_at_ns": None,
            "exit_trigger_reason": None,
            "exit_trigger_cursor": None,
            "exit_requested_at_ns": None,
            "exit_execution_outcome": "no_exit",
            "exit_outcome_cursor": None,
            "exit_outcome_at_ns": None,
        }
        if mapped == "entry_selected":
            outcome, cursor = spec["entry_execution_outcome"], spec["entry_outcome_cursor"]
            at = pending["deadline_ns"] if cursor is None else tape.quotes[cursor].received_at_ns
            trace.update(
                entry_execution_outcome=outcome, entry_outcome_cursor=cursor, entry_outcome_at_ns=at
            )
            if outcome == "constructed_entry_timeout":
                boundary = boundary_oracle(tape, prefixes, at)
                append(
                    ids,
                    pub,
                    ids["entry_outcome_event_id"],
                    "entry_deadline_boundary",
                    {
                        "admission_id": ids["admission_id"],
                        "reason": "timeout",
                    },
                    at,
                    boundary["prefix"],
                    boundary=boundary,
                )
                pending = None
                cooldown_events.append((at, boundary["prefix"]["last_cursor"], at + COOLDOWN))
            elif outcome == "simulator_spread_refusal":
                append(
                    ids,
                    pub,
                    ids["entry_outcome_event_id"],
                    "entry_candidate_quote",
                    {
                        "admission_id": ids["admission_id"],
                        "reason": "simulator_refusal",
                    },
                    at,
                    prefixes[cursor + 1],
                )
                pending = None
                cooldown_events.append((at, cursor, at + COOLDOWN))
            else:
                row = tape.quotes[cursor]
                price = row.ask_nano if side == "long" else row.bid_nano
                payload = {
                    "admission_id": ids["admission_id"],
                    "receipt_id": ids["entry_receipt_id"],
                    "contract": tape.contract,
                    "side": side,
                    "quantity_contracts": 1,
                    "price_nano": price,
                    "executed_at_ns": at,
                }
                receipt_pins.append(receipt_pin(payload, pending, at))
                append(
                    ids,
                    pub,
                    ids["entry_outcome_event_id"],
                    "entry_candidate_quote",
                    payload,
                    at,
                    prefixes[cursor + 1],
                )
                entry_fees += account.economics.entry_fee_usd_micros_per_contract
                position = {
                    "admission_id": ids["admission_id"],
                    "contract": tape.contract,
                    "side": side,
                    "quantity_contracts": 1,
                    "entry_price_nano": price,
                    "executed_at_ns": at,
                }
                pending = None
                trace["hold_at_ns"] = at + HOLD
            states.append(state_body())
            if position is not None:
                reason, trigger = spec["exit_trigger_reason"], spec["exit_trigger_cursor"]
                requested = (
                    trace["hold_at_ns"] if trigger is None else tape.quotes[trigger].received_at_ns
                )
                trace.update(
                    exit_trigger_reason=reason,
                    exit_trigger_cursor=trigger,
                    exit_requested_at_ns=requested,
                )
                boundary = (
                    boundary_oracle(tape, prefixes, requested - 1) if trigger is None else None
                )
                observed = boundary["prefix"] if boundary is not None else prefixes[trigger + 1]
                append(
                    ids,
                    pub,
                    ids["exit_request_event_id"],
                    "hold_boundary" if trigger is None else "bracket_trigger_quote",
                    {
                        "admission_id": ids["admission_id"],
                        "request_id": ids["exit_request_id"],
                    },
                    requested,
                    observed,
                    boundary=boundary,
                )
                pending_exit = {
                    "request_id": ids["exit_request_id"],
                    "requested_at_ns": requested,
                    "ready_at_ns": requested + DELAY,
                    "deadline_ns": requested + DELAY + WAIT,
                    "status": "PENDING",
                }
                states.append(state_body())
                outcome, cursor = spec["exit_execution_outcome"], spec["exit_outcome_cursor"]
                at = (
                    pending_exit["deadline_ns"]
                    if cursor is None
                    else tape.quotes[cursor].received_at_ns
                )
                trace.update(
                    exit_execution_outcome=outcome,
                    exit_outcome_cursor=cursor,
                    exit_outcome_at_ns=at,
                )
                if outcome == "constructed_exit_unknown":
                    boundary = boundary_oracle(tape, prefixes, at)
                    append(
                        ids,
                        pub,
                        ids["exit_outcome_event_id"],
                        "exit_deadline_boundary",
                        {
                            "request_id": ids["exit_request_id"],
                        },
                        at,
                        boundary["prefix"],
                        boundary=boundary,
                    )
                    pending_exit = pending_exit | {"status": "UNKNOWN"}
                else:
                    row = tape.quotes[cursor]
                    price = row.bid_nano if side == "long" else row.ask_nano
                    payload = {
                        "request_id": ids["exit_request_id"],
                        "receipt_id": ids["exit_receipt_id"],
                        "contract": tape.contract,
                        "quantity_contracts": 1,
                        "price_nano": price,
                        "executed_at_ns": at,
                    }
                    receipt_pins.append(receipt_pin(payload, pending_exit, at))
                    append(
                        ids,
                        pub,
                        ids["exit_outcome_event_id"],
                        "exit_candidate_quote",
                        payload,
                        at,
                        prefixes[cursor + 1],
                    )
                    ticks = (price - position["entry_price_nano"]) // TICK
                    gross += (
                        ticks
                        * account.economics.tick_value_usd_micros
                        * (1 if side == "long" else -1)
                    )
                    exit_fees += account.economics.exit_fee_usd_micros_per_contract
                    position = pending_exit = None
                    cooldown_events.append((at, cursor, at + COOLDOWN))
                states.append(state_body())
        trace["record_stop"] = len(records)
        traces.append(trace)

    publication_audit = []
    for _index, (pub, binding, disposition) in enumerate(
        zip(tape.publications, bound, dispositions, strict=True)
    ):
        visible = sum(
            at < pub.received_at_ns
            or (
                at == pub.received_at_ns
                and cursor <= pub.published_cursor
                and own != pub.publication_id
            )
            for at, cursor, own in visibility
        )
        preceding = states[visible]
        candidate = next(
            (trace for trace in traces if trace["publication_id"] == pub.publication_id), None
        )
        cooldown = next(
            (
                value
                for at, cursor, value in reversed(cooldown_events)
                if (
                    at < pub.received_at_ns
                    or at == pub.received_at_ns
                    and cursor <= pub.published_cursor
                )
            ),
            0,
        )
        publication_audit.append(
            {
                "publication": publication_oracle(pub, prefixes),
                "eligible": binding.eligible,
                "end_buffer_eligible": pub.received_at_ns < tape.end_ns - BUFFER,
                "point_sha256": digest(point_body(binding.point)),
                "point_selection": selection_body(binding.point),
                "selected_direction": dict(manual_directions(binding.point))[proposal.policy_id],
                "phase_before": preceding["phase"],
                "accounting_prefix_before": preceding["prefix"],
                "accounting_prefix_after": states[candidate["record_start"] + 2]["prefix"]
                if candidate
                else preceding["prefix"],
                "cooldown_before_ns": cooldown,
                "first_disposition": disposition,
                "candidate_ordinal": candidate["ordinal"] if candidate else None,
                "candidate_id": candidate["identities"]["candidate_id"] if candidate else None,
                "budget_decision": candidate["budget_decision"] if candidate else None,
                "decision_record_start": candidate["record_start"] if candidate else None,
                "decision_record_stop": candidate["record_start"] + 2 if candidate else None,
            }
        )
        if candidate is not None:
            assert candidate["first_disposition"] == disposition
    body = {
        "version": VERSION,
        "status": STATUS,
        "protocol_sha256": args["expected_protocol_sha256"],
        "fixture_sha256": fp,
        "genesis_sha256": gp,
        "bindings_sha256": bp,
        "declaration_sha256": args["expected_declaration_sha256"],
        "declaration": asdict(proposal),
        "bindings": tuple(asdict(binding) for binding in bound),
        "publication_audit": publication_audit,
        "candidates": traces,
        "records": records,
        "record_links": links,
        "quote_audit": audits,
        "terminal_native_prefix": prefixes[-1],
        "terminal_accounting_state": states[-1],
        "terminal_cooldown_until_ns": cooldown_events[-1][2] if cooldown_events else 0,
        "authority_flags": FLAGS,
    }
    return body | {"plan_sha256": digest(body)}


def assert_complete(tape, account, bound, proposal, dispositions, specs):
    expected = complete_oracle(tape, account, bound, proposal, dispositions, specs)
    args = arguments(tape, account, bound, proposal)
    result = walker.build_funded_path_plan(tape, account, bound, proposal, **args)
    assert canonical(asdict(result)) == canonical(expected)
    assert result.plan_sha256 == expected["plan_sha256"]
    assert (
        walker.verify_funded_path_plan(
            tape, account, bound, proposal, **args, expected_plan_sha256=expected["plan_sha256"]
        )
        == result
    )
    assert len(result.quote_audit) == len(tape.quotes)
    assert len(result.publication_audit) == len(tape.publications)
    assert len(result.records) == len(result.record_links)
    assert result.authority_flags == FLAGS and all(flag is False for _, flag in FLAGS)
    stop = 0
    for candidate in result.candidates:
        assert candidate.record_start == stop
        stop = candidate.record_stop
        audit = next(
            a
            for a in result.publication_audit
            if a.publication.publication_id == candidate.publication_id
        )
        assert audit.decision_record_start == candidate.record_start
        assert audit.decision_record_stop == candidate.record_start + 2
        assert audit.budget_decision == candidate.budget_decision
        assert audit.first_disposition == candidate.first_disposition
    assert stop == len(result.records)
    return result


def baseline():
    tape, account, proposal = fixture(), genesis(), declaration()
    return tape, account, bindings(tape), proposal


def changed(value, **changes):
    """Poison a frozen retained value without eager constructor masking."""
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(result, field.name, getattr(value, field.name))
    for name, replacement in changes.items():
        object.__setattr__(result, name, replacement)
    return result


def subclass_copy(value):
    cls = type("InventedSubclass", (type(value),), {})
    result = object.__new__(cls)
    for field in fields(value):
        object.__setattr__(result, field.name, getattr(value, field.name))
    return result


class IntSubclass(int):
    pass


class StrSubclass(str):
    pass


class TupleSubclass(tuple):
    pass


def forbidden(*args, **kwargs):
    raise AssertionError("Forbidden numeric traversal, account mutation or external operation")


def safe_id(value):
    return (
        repr(value) if type(value) in (str, int, float, bool, type(None)) else type(value).__name__
    )


def invoke(tape, account, bound, proposal, args=None, *, output=None):
    args = arguments(tape, account, bound, proposal) if args is None else args
    if output is None:
        return walker.build_funded_path_plan(tape, account, bound, proposal, **args)
    return walker.verify_funded_path_plan(
        tape, account, bound, proposal, **args, expected_plan_sha256=output
    )


def test_literal_closed_protocol_source_pins_schema_and_authority_union():
    assert len(FLAGS) == len(set(AUTHORITY_NAMES)) == 57
    assert point.protocol_sha256() == SELECTOR_PROTOCOL
    assert walker.protocol_sha256() == digest(protocol_body())
    for name, expected in {
        "VERSION": VERSION,
        "STATUS": STATUS,
        "MAX_QUOTES": 128,
        "MIN_PUBLICATIONS": 1,
        "MAX_PUBLICATIONS": 4,
        "MAX_ACCOUNTING_RECORDS": 20,
        "MAX_CANONICAL_BYTES": 262144,
        "TICK_NANO": TICK,
        "ENTRY_DELAY_NS": DELAY,
        "EXIT_DELAY_NS": DELAY,
        "ENTRY_WAIT_NS": WAIT,
        "EXIT_WAIT_NS": WAIT,
        "HOLD_NS": HOLD,
        "COOLDOWN_NS": COOLDOWN,
        "END_BUFFER_NS": BUFFER,
        "MIN_PUBLICATION_CADENCE_NS": SECOND,
        "TARGET_TICKS": 3,
        "STOP_TICKS": -3,
        "COMPARATOR_COST_TICKS": 1,
        "QUANTITY_CONTRACTS": 1,
    }.items():
        assert getattr(walker, name) == expected
    assert walker.AUTHORITY_FLAGS == FLAGS
    schemas = {
        "PublishedLiquidityBinding": "publication_id eligible point point_sha256",
        "FundedPathDeclaration": "declaration_id policy_id exit_plan",
        "CandidateIdentifiers": (
            "candidate_id clock_event_id request_event_id admission_id entry_outcome_event_id "
            "entry_receipt_id exit_request_event_id exit_request_id exit_outcome_event_id "
            "exit_receipt_id"
        ),
        "PublicationAudit": (
            "publication eligible end_buffer_eligible point_sha256 point_selection "
            "selected_direction phase_before accounting_prefix_before accounting_prefix_after "
            "cooldown_before_ns first_disposition candidate_ordinal candidate_id budget_decision "
            "decision_record_start decision_record_stop"
        ),
        "CandidateTrace": (
            "publication_id ordinal identities direction side first_disposition budget_decision "
            "record_start record_stop entry_execution_outcome entry_outcome_cursor "
            "entry_outcome_at_ns hold_at_ns exit_trigger_reason exit_trigger_cursor "
            "exit_requested_at_ns exit_execution_outcome exit_outcome_cursor exit_outcome_at_ns"
        ),
        "QuoteAudit": "cursor received_at_ns consumed_count consumed_content_sha256",
        "AccountingLink": (
            "record_index candidate_ordinal publication_id event_id record_sha256 native_prefix "
            "kind publication boundary"
        ),
        "FundedPathPlan": (
            "version status protocol_sha256 fixture_sha256 genesis_sha256 bindings_sha256 "
            "declaration_sha256 declaration bindings publication_audit candidates records "
            "record_links quote_audit terminal_native_prefix terminal_accounting_state "
            "terminal_cooldown_until_ns plan_sha256 authority_flags"
        ),
    }
    for name, expected in schemas.items():
        cls = getattr(walker, name)
        assert [field.name for field in fields(cls)] == expected.split()
        assert cls.__dataclass_params__.frozen
        assert tuple(cls.__slots__) == tuple(expected.split())
    for name in (
        "bindings_sha256",
        "declaration_sha256",
        "build_funded_path_plan",
        "verify_funded_path_plan",
    ):
        signature = inspect.signature(getattr(walker, name))
        assert all(
            parameter.default is inspect.Parameter.empty
            for parameter in signature.parameters.values()
        )
        assert not {"records", "state", "plan", "packet", "expected_terminal"} & set(
            signature.parameters
        )


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("exit_plan", ("time_exit", "bracket_exit"))
@pytest.mark.parametrize("sign", (-1, 1))
def test_every_fixed_policy_side_exit_is_complete_and_separate(policy, exit_plan, sign):
    tape, account = fixture(), genesis()
    value = feature_point(sign=sign, mid_change_5s_ticks=sign)
    bound, proposal = bindings(tape, points=[value]), declaration(policy, exit_plan)
    selected = dict(manual_directions(value))[policy]
    assert dict(manual_directions(value)) == {
        "cvd_follow": sign,
        "liquidity_follow": sign,
        "absorption_fade": -sign,
        "no_trade": 0,
    }
    specs = [candidate_spec()] if selected else []
    result = assert_complete(
        tape, account, bound, proposal, ["entry_selected" if selected else "no_signal"], specs
    )
    assert result.publication_audit[0].selected_direction == selected
    if not selected:
        assert result.terminal_accounting_state.last_event_at_ns is None


def test_denial_recomputes_every_publication_instead_of_filtering_unfunded_fills():
    times = tuple(PUB + index * SECOND for index in range(4))
    tape = fixture(
        tuple(quote(at, PRICE + index * 100 * TICK) for index, at in enumerate(times)), times
    )
    account, proposal = genesis(balance=1), declaration()
    bound = bindings(tape, [1, -1, 0, 1], [True, True, True, False])
    result = assert_complete(
        tape,
        account,
        bound,
        proposal,
        ["budget_denied", "budget_denied", "no_signal", "ineligible"],
        [
            candidate_spec(0, disposition="budget_denied"),
            candidate_spec(1, disposition="budget_denied"),
        ],
    )
    assert len(result.records) == 4 and result.terminal_cooldown_until_ns == 0
    assert [c.ordinal for c in result.candidates] == [1, 2]
    assert all(c.entry_execution_outcome == "no_pending_entry" for c in result.candidates)
    assert result.terminal_accounting_state.declared_realization_balance_usd_micros == 1
    assert result.terminal_accounting_state.receipt_content_sha256s == ()


def test_missing_margin_repeatedly_undetermined_without_fees_or_cooldown():
    tape = fixture((quote(PUB), quote(PUB + SECOND)), (PUB, PUB + SECOND))
    account, proposal, bound = genesis(margin=None), declaration(), bindings(tape)
    result = assert_complete(
        tape,
        account,
        bound,
        proposal,
        ["budget_undetermined", "budget_undetermined"],
        [
            candidate_spec(0, disposition="budget_undetermined"),
            candidate_spec(1, disposition="budget_undetermined"),
        ],
    )
    assert [c.budget_decision.reasons for c in result.candidates] == [
        ("margin_not_declared",),
        ("margin_not_declared",),
    ]
    assert all(c.budget_decision.snapshot_age_ns == 0 for c in result.candidates)
    assert len(result.records) == 4 and result.terminal_cooldown_until_ns == 0
    assert result.terminal_accounting_state.total_commitments_usd_micros == 0


def test_explicit_zero_margin_and_zero_fees_are_not_missing_margin():
    tape, account, proposal = (
        fixture(),
        genesis(balance=1, margin=0, entry=0, exit_fee=0, buffer=0),
        declaration(),
    )
    result = assert_complete(
        tape, account, bindings(tape), proposal, ["entry_selected"], [candidate_spec()]
    )
    assert result.candidates[0].budget_decision.declared_requirement_usd_micros == 0
    assert result.terminal_accounting_state.phase == "FLAT"
    assert result.terminal_accounting_state.complete_declared_net_return_usd_micros == 125


@pytest.mark.parametrize("sign", (-1, 1))
def test_same_cursor_refusal_before_publication_keeps_original_selected_disposition(sign):
    later = PUB + 11 * SECOND
    rows = (
        quote(PUB),
        quote(PUB + SECOND, spread=2 * TICK),
        quote(PUB + SECOND, PRICE + 100 * TICK),
        quote(later),
        quote(later + DELAY),
        quote(later + DELAY + HOLD),
        quote(later + 2 * DELAY + HOLD),
    )
    tape = fixture(rows, (PUB, PUB + SECOND, later))
    result = assert_complete(
        tape,
        genesis(),
        bindings(tape, [sign, 0, sign]),
        declaration(),
        ["entry_selected", "cooldown", "entry_selected"],
        [
            candidate_spec(0, entry_cursor=1, entry_outcome="simulator_spread_refusal"),
            candidate_spec(2, entry_cursor=4, exit_cursor=6),
        ],
    )
    assert result.publication_audit[1].phase_before == "FLAT"
    assert result.publication_audit[1].accounting_prefix_before.sequence == 3
    assert result.publication_audit[1].selected_direction == 0
    assert result.candidates[0].first_disposition == "entry_selected"
    assert result.candidates[0].entry_outcome_cursor == 1
    assert result.candidates[1].ordinal == 2


@pytest.mark.parametrize("delta", (-1, 0, 1))
@pytest.mark.parametrize("sign", (-1, 1))
def test_cooldown_before_equality_and_after_use_valid_separate_complete_fixtures(delta, sign):
    refused, later = PUB + DELAY, PUB + DELAY + COOLDOWN + delta
    rows = (quote(PUB), quote(refused, spread=2 * TICK), quote(later))
    specs = [candidate_spec(0, entry_cursor=1, entry_outcome="simulator_spread_refusal")]
    if delta >= 0:
        rows += (quote(later + DELAY), quote(later + DELAY + HOLD), quote(later + 2 * DELAY + HOLD))
        specs.append(candidate_spec(1, entry_cursor=3, exit_cursor=5))
    tape = fixture(rows, (PUB, later))
    result = assert_complete(
        tape,
        genesis(),
        bindings(tape, [sign, sign]),
        declaration(),
        ["entry_selected", "cooldown" if delta < 0 else "entry_selected"],
        specs,
    )
    assert result.publication_audit[1].cooldown_before_ns == refused + COOLDOWN
    assert result.publication_audit[1].candidate_ordinal == (None if delta < 0 else 2)


def test_supplied_ineligibility_and_inventory_take_priority_over_zero_or_nonzero_signal():
    times = (PUB, PUB + SECOND, PUB + 2 * SECOND, PUB + 3 * SECOND)
    rows = (
        quote(PUB),
        quote(PUB + DELAY),
        *(quote(at) for at in times[1:]),
        quote(PUB + DELAY + HOLD),
        quote(PUB + 2 * DELAY + HOLD),
    )
    tape = fixture(rows, times)
    result = assert_complete(
        tape,
        genesis(),
        bindings(tape, [1, 0, 0, -1], [True, False, True, True]),
        declaration(),
        ["entry_selected", "ineligible", "inventory_blocked", "inventory_blocked"],
        [candidate_spec(entry_cursor=1, exit_cursor=6)],
    )
    assert [a.selected_direction for a in result.publication_audit] == [1, 0, 0, -1]
    assert len(result.candidates) == 1
    assert all(
        a.accounting_prefix_before == a.accounting_prefix_after
        for a in result.publication_audit[1:]
    )


@pytest.mark.parametrize("sign", (-1, 1))
@pytest.mark.parametrize("exit_plan", ("time_exit", "bracket_exit"))
def test_hold_and_inclusive_widened_exit_before_same_cursor_publication_and_suffix(sign, exit_plan):
    entry_at, hold = PUB + DELAY, PUB + DELAY + HOLD
    deadline = hold + DELAY + WAIT
    side, entry_price = ("long", PRICE + TICK) if sign == 1 else ("short", PRICE)
    rows = (
        quote(PUB),
        quote(entry_at),
        quote(hold - 1),
        crossed_quote(hold, side, entry_price, 100),
        crossed_quote(deadline, side, entry_price, -4, 3 * TICK),
        crossed_quote(deadline, side, entry_price, 1000),
        quote(deadline + SECOND),
    )
    tape = fixture(rows, (PUB, hold, deadline))
    result = assert_complete(
        tape,
        genesis(),
        bindings(tape, [sign, sign, 0]),
        declaration(exit_plan=exit_plan),
        ["entry_selected", "inventory_blocked", "cooldown"],
        [candidate_spec(entry_cursor=1, exit_cursor=4)],
    )
    trace = result.candidates[0]
    assert trace.exit_trigger_reason == "hold_timer" and trace.exit_trigger_cursor is None
    assert trace.exit_outcome_at_ns == deadline and trace.exit_outcome_cursor == 4
    assert result.record_links[3].boundary.through_ns == hold - 1
    assert result.record_links[3].native_prefix.last_cursor == 2
    assert result.publication_audit[1].phase_before == "EXIT_PENDING"
    assert result.publication_audit[2].phase_before == "FLAT"
    assert result.publication_audit[2].accounting_prefix_before.sequence == 5
    assert result.terminal_accounting_state.gross_realized_usd_micros == -500
    assert result.terminal_accounting_state.complete_declared_net_return_usd_micros == -530


def test_timeout_boundary_precedes_later_publication_and_cooldown_equality_recomputes():
    deadline = PUB + DELAY + WAIT
    later = deadline + COOLDOWN
    rows = (
        quote(PUB),
        quote(deadline + 1),
        quote(later),
        quote(later + DELAY),
        quote(later + DELAY + HOLD),
        quote(later + 2 * DELAY + HOLD),
    )
    tape = fixture(rows, (PUB, deadline + 1, later))
    result = assert_complete(
        tape,
        genesis(),
        bindings(tape),
        declaration(),
        ["entry_selected", "cooldown", "entry_selected"],
        [
            candidate_spec(0, entry_cursor=None, entry_outcome="constructed_entry_timeout"),
            candidate_spec(2, entry_cursor=3, exit_cursor=5),
        ],
    )
    assert result.candidates[0].entry_outcome_at_ns == deadline
    assert result.record_links[2].boundary.through_ns == deadline
    assert result.publication_audit[1].accounting_prefix_before.sequence == 3
    assert result.publication_audit[1].cooldown_before_ns == later


@pytest.mark.parametrize("endpoint", ("readiness", "deadline"))
@pytest.mark.parametrize("delta", (-1, 0, 1))
def test_entry_inclusive_endpoints_are_not_no_quote_timeout(endpoint, delta):
    at = PUB + DELAY + (WAIT if endpoint == "deadline" else 0) + delta
    rows = (quote(PUB), quote(at))
    tape = fixture(rows)
    eligible = PUB + DELAY <= at <= PUB + DELAY + WAIT
    spec = candidate_spec(
        entry_cursor=1 if eligible else None,
        entry_outcome="constructed_entry_receipt" if eligible else "constructed_entry_timeout",
        exit_cursor=None,
        exit_outcome="constructed_exit_unknown",
    )
    result = assert_complete(
        tape, genesis(), bindings(tape), declaration(), ["entry_selected"], [spec]
    )
    assert result.candidates[0].entry_execution_outcome == spec["entry_execution_outcome"]


@pytest.mark.parametrize("zero", (False, True))
@pytest.mark.parametrize("eof", (False, True))
def test_unknown_zero_or_nonzero_liability_is_terminal_without_late_accounting(zero, eof):
    deadline = PUB + DELAY + HOLD + DELAY + WAIT
    rows, times = (quote(PUB), quote(PUB + DELAY)), (PUB,)
    if not eof:
        rows += (
            quote(deadline + 1, PRICE + 1000 * TICK),
            quote(PUB + 30 * SECOND, PRICE + 2000 * TICK),
        )
        times += (deadline + 1, PUB + 30 * SECOND)
    tape = fixture(rows, times)
    account = genesis(balance=1, margin=0, entry=0, exit_fee=0, buffer=0) if zero else genesis()
    result = assert_complete(
        tape,
        account,
        bindings(tape),
        declaration(),
        ["entry_selected"] + ["inventory_blocked"] * (len(times) - 1),
        [candidate_spec(entry_cursor=1, exit_cursor=None, exit_outcome="constructed_exit_unknown")],
    )
    terminal = result.terminal_accounting_state
    assert terminal.phase == "EXIT_UNKNOWN"
    assert terminal.complete_declared_equity_usd_micros is None
    assert terminal.complete_declared_net_return_usd_micros is None
    assert terminal.prefix.sequence == 5 and terminal.last_event_at_ns == deadline
    assert terminal.pending_exit.status == "UNKNOWN"
    assert result.terminal_cooldown_until_ns == 0
    if zero:
        assert terminal.total_commitments_usd_micros == 0 and terminal.position is not None
    assert all(a.accounting_prefix_before.sequence == 5 for a in result.publication_audit[1:])


def test_one_seed_fee_loss_continuity_denies_later_fee_without_daily_reset():
    later = PUB + 30 * SECOND
    rows = (
        quote(PUB),
        quote(PUB + DELAY),
        quote(PUB + DELAY + HOLD),
        quote(PUB + 2 * DELAY + HOLD, PRICE + TICK),
        quote(later),
    )
    tape = fixture(rows, (PUB, later))
    result = assert_complete(
        tape,
        genesis(loss=30),
        bindings(tape),
        declaration(),
        ["entry_selected", "budget_denied"],
        [candidate_spec(), candidate_spec(1, disposition="budget_denied")],
    )
    decision = result.candidates[1].budget_decision
    assert (
        decision.snapshot.sequence == 6
        and decision.snapshot.seed.initial_balance_usd_micros == 1000
    )
    assert decision.snapshot.declared_realization_balance_usd_micros == 970
    assert decision.realization_loss_from_original_seed_usd_micros == 30
    assert decision.hypothetical_loss_after_entry_fee_usd_micros == 40
    assert decision.reasons == ("proposed_entry_fee_exceeds_loss_ceiling",)
    assert len(result.records) == 7


@pytest.mark.parametrize("sign", (-1, 1))
def test_owned_exit_is_not_suppressed_by_later_loss_ceiling_or_negative_cash(sign):
    side, entry_price = ("long", PRICE + TICK) if sign == 1 else ("short", PRICE)
    later = PUB + 30 * SECOND
    rows = (
        quote(PUB),
        quote(PUB + DELAY),
        quote(PUB + DELAY + HOLD),
        crossed_quote(PUB + 2 * DELAY + HOLD, side, entry_price, -4, 3 * TICK),
        quote(later),
    )
    tape = fixture(rows, (PUB, later))
    result = assert_complete(
        tape,
        genesis(balance=135, loss=100),
        bindings(tape, [sign, sign]),
        declaration(),
        ["entry_selected", "budget_denied"],
        [candidate_spec(), candidate_spec(1, disposition="budget_denied")],
    )
    assert result.candidates[0].exit_execution_outcome == "constructed_exit_receipt"
    assert result.terminal_accounting_state.declared_realization_balance_usd_micros == -395
    assert result.terminal_accounting_state.complete_declared_net_return_usd_micros == -530
    assert result.candidates[1].budget_decision.reasons == (
        "insufficient_declared_cash",
        "realization_loss_ceiling_exceeded",
    )


def capacity_context(*, large=False, idle=False):
    start = MAX_INT - 200 * SECOND if large else START
    first = start + SECOND
    end = MAX_INT - COOLDOWN if large else END
    price = MAX_INT // TICK * TICK - 1000 * TICK if large else PRICE
    rows, times, specs = [], [], []
    for index in range(4):
        at = first + index * 30 * SECOND
        times.append(at)
        rows.append(quote(at, price))
        rows.extend([quote(at + DELAY, price)] * 29)
        rows.append(quote(at + DELAY + HOLD, price))
        rows.append(quote(at + 2 * DELAY + HOLD, price + 2 * TICK))
        specs.append(
            candidate_spec(index, entry_cursor=32 * index + 1, exit_cursor=32 * index + 31)
        )
    label = "synthetic-" + "x" * 54 if large else None
    tape = fixture(rows, times, start=start, end=end, label=label)
    account = genesis(start=start, label=label)
    proposal = declaration(
        "no_trade" if idle else "cvd_follow", label=label or "synthetic-funded-plan"
    )
    points = None
    if large:
        pubs = tuple(
            replace(pub, publication_id="p" * 63 + str(index))
            for index, pub in enumerate(tape.publications)
        )
        tape = replace(tape, publications=pubs)
        maximum = int(sys.float_info.max)
        values = [maximum] * 37
        for name in (
            "unknown_trade_fraction_5s",
            "bid_top_share5",
            "ask_top_share5",
            "queue_imbalance",
            "depth5_imbalance",
        ):
            values[FEATURES.index(name)] = 1
        points = [
            point.SyntheticLiquidityPoint("synthetic-" + "x" * 53 + str(index), tuple(values))
            for index in range(4)
        ]
    return tape, account, bindings(tape, points=points), proposal, [] if idle else specs


@pytest.mark.parametrize("large", (False, True))
def test_complete_four_roundtrips_128_quotes_twenty_records_and_full_body_capacity(large):
    tape, account, bound, proposal, specs = capacity_context(large=large)
    result = assert_complete(tape, account, bound, proposal, ["entry_selected"] * 4, specs)
    assert len(result.quote_audit) == 128 and len(result.publication_audit) == 4
    assert len(result.records) == len(result.record_links) == 20
    assert [c.budget_decision.snapshot.sequence for c in result.candidates] == [1, 6, 11, 16]
    assert result.terminal_accounting_state.gross_realized_usd_micros == 500
    assert result.terminal_accounting_state.entry_fees_usd_micros == 40
    assert result.terminal_accounting_state.exit_fees_usd_micros == 80
    assert result.terminal_accounting_state.complete_declared_net_return_usd_micros == 380
    assert result.terminal_accounting_state.total_commitments_usd_micros == 0
    body = asdict(result)
    del body["plan_sha256"]
    measured = len(canonical(body))
    assert measured <= 262144
    print(
        f"constructed funded128/4/20 large={large}: "
        f"complete canonical body {measured} bytes <=262144"
    )
    # This is the exact constructed shape, not a universal maximum JSON proof.


@pytest.mark.parametrize("large", (False, True))
def test_idle_full_coverage_retains_genesis_frontier_and_does_not_evaluate_unused_products(large):
    tape, account, bound, proposal, specs = capacity_context(large=large, idle=True)
    if large:
        account = replace(
            account, economics=replace(account.economics, tick_value_usd_micros=MAX_INT)
        )
        assert tape.quotes[0].bid_nano * account.economics.tick_value_usd_micros > MAX_INT
    result = assert_complete(tape, account, bound, proposal, ["no_signal"] * 4, specs)
    assert len(result.quote_audit) == 128 and len(result.publication_audit) == 4
    assert result.candidates == result.records == result.record_links == ()
    terminal = result.terminal_accounting_state
    assert terminal.prefix == admission.DeclaredPrefix(0, genesis_pin(account), tape.start_ns)
    assert terminal.last_event_at_ns is None and result.terminal_cooldown_until_ns == 0
    assert terminal.complete_declared_equity_usd_micros == account.seed.initial_balance_usd_micros
    assert terminal.complete_declared_net_return_usd_micros == 0


@pytest.mark.parametrize("sign", (-1, 1))
@pytest.mark.parametrize(
    "reason,delta",
    (("target", 3), ("target", 4), ("target", 5), ("stop", -1), ("stop", -2), ("stop", -3)),
)
def test_bracket_neighboring_ticks_equalities_both_sides_and_delayed_crossed_overshoot(
    sign, reason, delta
):
    side, entry_price = ("long", PRICE + TICK) if sign == 1 else ("short", PRICE)
    trigger = PUB + SECOND
    triggered = delta >= 4 or delta <= -2
    rows = (quote(PUB), quote(PUB + DELAY), crossed_quote(trigger, side, entry_price, delta))
    if triggered:
        rows += (
            crossed_quote(
                trigger + DELAY, side, entry_price, 7 if reason == "target" else -6, 3 * TICK
            ),
        )
        spec = candidate_spec(
            entry_cursor=1, trigger_reason=reason, trigger_cursor=2, exit_cursor=3
        )
    else:
        rows += (
            quote(PUB + DELAY + HOLD),
            crossed_quote(PUB + 2 * DELAY + HOLD, side, entry_price, 2, 3 * TICK),
        )
        spec = candidate_spec(entry_cursor=1, exit_cursor=4)
    tape = fixture(rows)
    result = assert_complete(
        tape,
        genesis(),
        bindings(tape, [sign]),
        declaration(exit_plan="bracket_exit"),
        ["entry_selected"],
        [spec],
    )
    trace = result.candidates[0]
    assert trace.exit_trigger_reason == (reason if triggered else "hold_timer")
    assert trace.exit_requested_at_ns == (trigger if triggered else PUB + DELAY + HOLD)
    expected_ticks = (7 if reason == "target" else -6) if triggered else 2
    assert result.terminal_accounting_state.gross_realized_usd_micros == expected_ticks * 125
    assert (
        result.terminal_accounting_state.complete_declared_net_return_usd_micros
        == expected_ticks * 125 - 30
    )


@pytest.mark.parametrize("sign", (-1, 1))
@pytest.mark.parametrize("endpoint", ("readiness", "deadline"))
@pytest.mark.parametrize("delta", (-1, 0, 1))
def test_exit_inclusive_endpoints_unknown_and_actual_crossed_side(sign, endpoint, delta):
    side, entry_price = ("long", PRICE + TICK) if sign == 1 else ("short", PRICE)
    requested = PUB + DELAY + HOLD
    at = requested + DELAY + (WAIT if endpoint == "deadline" else 0) + delta
    rows = (
        quote(PUB),
        quote(PUB + DELAY),
        quote(requested),
        crossed_quote(at, side, entry_price, -5, 3 * TICK),
    )
    tape = fixture(rows)
    eligible = requested + DELAY <= at <= requested + DELAY + WAIT
    spec = candidate_spec(
        exit_cursor=3 if eligible else None,
        exit_outcome="constructed_exit_receipt" if eligible else "constructed_exit_unknown",
    )
    result = assert_complete(
        tape, genesis(), bindings(tape, [sign]), declaration(), ["entry_selected"], [spec]
    )
    assert result.candidates[0].exit_execution_outcome == spec["exit_execution_outcome"]


def test_prior_losses_are_offset_by_realized_gains_not_sum_of_losers_or_peak_drawdown():
    rows, times, specs = [], [], []
    for index, favorable in enumerate((-1, 3, 0)):
        at = PUB + index * 30 * SECOND
        times.append(at)
        rows += [
            quote(at),
            quote(at + DELAY),
            quote(at + DELAY + HOLD),
            crossed_quote(at + 2 * DELAY + HOLD, "long", PRICE + TICK, favorable),
        ]
        specs.append(candidate_spec(index, entry_cursor=4 * index + 1, exit_cursor=4 * index + 3))
    tape = fixture(rows, times)
    result = assert_complete(
        tape, genesis(loss=200), bindings(tape), declaration(), ["entry_selected"] * 3, specs
    )
    assert (
        result.candidates[1].budget_decision.realization_loss_from_original_seed_usd_micros == 155
    )
    assert result.candidates[2].budget_decision.realization_loss_from_original_seed_usd_micros == 0
    assert result.candidates[2].budget_decision.hypothetical_loss_after_entry_fee_usd_micros == 0
    assert result.terminal_accounting_state.complete_declared_net_return_usd_micros == 160


@pytest.mark.parametrize("delta", (-1, 0, 1))
def test_strict_end_buffer_is_disposition_not_whole_fixture_rejection(delta):
    end = PUB + BUFFER + delta
    tape = fixture((quote(PUB), quote(PUB + DELAY)), end=end)
    bound, account, proposal = bindings(tape), genesis(), declaration()
    eligible = delta == 1
    specs = (
        [candidate_spec(entry_cursor=1, exit_cursor=None, exit_outcome="constructed_exit_unknown")]
        if eligible
        else []
    )
    result = assert_complete(
        tape, account, bound, proposal, ["entry_selected" if eligible else "ineligible"], specs
    )
    assert result.publication_audit[0].end_buffer_eligible is eligible
    assert result.publication_audit[0].eligible is True


def test_near_integer_limit_late_publication_avoids_unused_end_buffer_addition():
    end, start = MAX_INT - COOLDOWN, MAX_INT - 100 * SECOND
    at = end - 1
    assert at + BUFFER > MAX_INT
    tape = fixture((quote(at),), (at,), start=start, end=end)
    result = assert_complete(
        tape, genesis(start=start), bindings(tape), declaration(), ["ineligible"], []
    )
    assert result.publication_audit[0].selected_direction == 1
    assert result.terminal_accounting_state.phase == "FLAT" and result.records == ()


@pytest.mark.parametrize("contract", CONTRACTS)
def test_held_contract_preserved_in_every_entry_exit_receipt_and_budget(contract):
    tape = fixture(contract=contract)
    result = assert_complete(
        tape, genesis(), bindings(tape), declaration(), ["entry_selected"], [candidate_spec()]
    )
    assert all(
        record.payload.contract == contract
        for record in result.records
        if hasattr(record.payload, "contract")
    )
    assert result.candidates[0].budget_decision.proposal.contract == contract


BAD_PINS = (None, True, 7, "", "a" * 63, "a" * 65, "A" * 64, "g" * 64, StrSubclass("a" * 64))
INPUT_PIN_NAMES = (
    "expected_protocol_sha256",
    "expected_fixture_sha256",
    "expected_genesis_sha256",
    "expected_bindings_sha256",
    "expected_declaration_sha256",
)


def forbid_numeric_and_mutation(monkeypatch):
    monkeypatch.setattr(native, "_quote_fields", forbidden)
    monkeypatch.setattr(point.math, "isfinite", forbidden)
    monkeypatch.setattr(admission, "advance", forbidden)


@pytest.mark.parametrize("name", INPUT_PIN_NAMES)
@pytest.mark.parametrize("bad", BAD_PINS, ids=safe_id)
@pytest.mark.parametrize("verify", (False, True))
def test_every_expectation_syntax_precedes_prices_features_and_account_mutation(
    monkeypatch, name, bad, verify
):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    expected = complete_oracle(
        tape, account, bound, proposal, ["entry_selected"], [candidate_spec()]
    )
    args[name] = bad
    forbid_numeric_and_mutation(monkeypatch)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(
            tape, account, bound, proposal, args, output=expected["plan_sha256"] if verify else None
        )


@pytest.mark.parametrize("bad", BAD_PINS, ids=safe_id)
def test_retained_output_expectation_syntax_precedes_all_deep_inputs(monkeypatch, bad):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    forbid_numeric_and_mutation(monkeypatch)
    with pytest.raises(walker.SyntheticFundedPathError):
        walker.verify_funded_path_plan(
            tape, account, bound, proposal, **args, expected_plan_sha256=bad
        )


@pytest.mark.parametrize("name", (*INPUT_PIN_NAMES, "expected_plan_sha256"))
def test_valid_but_wrong_complete_expectation_is_never_adopted(name):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    args["expected_plan_sha256"] = complete_oracle(
        tape, account, bound, proposal, ["entry_selected"], [candidate_spec()]
    )["plan_sha256"]
    args[name] = "0" * 64
    with pytest.raises(walker.SyntheticFundedPathError):
        walker.verify_funded_path_plan(tape, account, bound, proposal, **args)


@pytest.mark.parametrize(
    "where", ("fixture", "genesis", "declaration", "binding", "point", "quote", "publication")
)
@pytest.mark.parametrize("kind", ("subclass", "missing", "mapping"))
def test_complete_exact_outer_and_nested_types_precede_price_and_feature_access(
    monkeypatch, where, kind
):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    values = {
        "fixture": tape,
        "genesis": account,
        "declaration": proposal,
        "binding": bound[0],
        "point": bound[0].point,
        "quote": tape.quotes[0],
        "publication": tape.publications[0],
    }
    value = values[where]
    if kind == "subclass":
        poisoned = subclass_copy(value)
    elif kind == "mapping":
        poisoned = asdict(value)
    else:
        poisoned = changed(value)
        object.__delattr__(poisoned, fields(value)[0].name)
    if where == "fixture":
        tape = poisoned
    elif where == "genesis":
        account = poisoned
    elif where == "declaration":
        proposal = poisoned
    elif where == "binding":
        bound = (poisoned,)
    elif where == "point":
        bound = (changed(bound[0], point=poisoned),)
    elif where == "quote":
        tape = changed(tape, quotes=(poisoned, *tape.quotes[1:]))
    else:
        tape = changed(tape, publications=(poisoned,))
    forbid_numeric_and_mutation(monkeypatch)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)


@pytest.mark.parametrize(
    "field,bad",
    (
        ("source_session", "real-archive-session"),
        ("source_session", "synthetic-"),
        ("source_session", StrSubclass("synthetic-funded-tape")),
        ("source_session", "synthetic-é"),
        ("source_session", "synthetic-" + "x" * 55),
        ("contract", "EURUSD"),
        ("contract", "6EM6"),
        ("contract", StrSubclass("6EM5")),
        ("source_sha256", "A" * 64),
        ("source_sha256", True),
        ("start_ns", True),
        ("start_ns", -1),
        ("start_ns", IntSubclass(START)),
        ("end_ns", 2**63),
        ("end_ns", START),
        ("end_ns", IntSubclass(END)),
        ("quotes", []),
        ("publications", []),
    ),
    ids=safe_id,
)
def test_fixture_metadata_every_field_refuses_before_numbers(monkeypatch, field, bad):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    tape = changed(tape, **{field: bad})
    forbid_numeric_and_mutation(monkeypatch)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)


@pytest.mark.parametrize(
    "field,bad",
    (
        ("publication_id", True),
        ("publication_id", "bad/id"),
        ("publication_id", StrSubclass("pub-1")),
        ("published_cursor", True),
        ("published_cursor", -1),
        ("published_cursor", 4),
        ("published_cursor", IntSubclass(0)),
        ("received_at_ns", True),
        ("received_at_ns", START - 1),
        ("received_at_ns", END),
        ("received_at_ns", PUB + 1),
        ("received_at_ns", IntSubclass(PUB)),
    ),
    ids=safe_id,
)
def test_publication_exact_scalar_and_timestamp_alignment_precedes_prices(monkeypatch, field, bad):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    tape = changed(tape, publications=(changed(tape.publications[0], **{field: bad}),))
    forbid_numeric_and_mutation(monkeypatch)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)


@pytest.mark.parametrize(
    "field,bad",
    (
        ("declaration_id", "real-policy"),
        ("declaration_id", "synthetic-"),
        ("declaration_id", "synthetic-" + "x" * 55),
        ("declaration_id", "synthetic-é"),
        ("declaration_id", StrSubclass("synthetic-funded-plan")),
        ("policy_id", "voting"),
        ("policy_id", True),
        ("policy_id", StrSubclass("cvd_follow")),
        ("exit_plan", "live_exit"),
        ("exit_plan", True),
        ("exit_plan", StrSubclass("time_exit")),
    ),
    ids=safe_id,
)
def test_declaration_closed_fields_before_numeric_context(monkeypatch, field, bad):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    proposal = changed(proposal, **{field: bad})
    forbid_numeric_and_mutation(monkeypatch)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)


@pytest.mark.parametrize(
    "field,bad",
    (
        ("publication_id", True),
        ("publication_id", "bad/id"),
        ("publication_id", StrSubclass("pub-1")),
        ("publication_id", "other-pub"),
        ("eligible", 0),
        ("eligible", 1),
        ("eligible", None),
        ("point_sha256", "A" * 64),
        ("point_sha256", "a" * 63),
        ("point_sha256", True),
    ),
    ids=safe_id,
)
def test_binding_metadata_fields_and_complete_alignment_before_numbers(monkeypatch, field, bad):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    bound = (changed(bound[0], **{field: bad}),)
    forbid_numeric_and_mutation(monkeypatch)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)


@pytest.mark.parametrize(
    "kind", ("id", "missing_id", "missing_values", "short", "long", "list", "tuple_subclass")
)
def test_point_complete_metadata_guards_precede_all_feature_values(monkeypatch, kind):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    value = changed(bound[0].point)
    if kind == "id":
        object.__setattr__(value, "point_id", "real-features")
    elif kind.startswith("missing_"):
        object.__delattr__(value, "point_id" if kind == "missing_id" else "values")
    else:
        replacements = {
            "short": value.values[:-1],
            "long": (*value.values, 0),
            "list": list(value.values),
            "tuple_subclass": TupleSubclass(value.values),
        }
        object.__setattr__(value, "values", replacements[kind])
    bound = (changed(bound[0], point=value),)
    forbid_numeric_and_mutation(monkeypatch)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)


@pytest.mark.parametrize(
    "kind", ("binding_id", "point_id", "point_pin", "quote_time", "publication_cursor")
)
def test_invalid_last_metadata_is_found_before_earlier_numeric_feature_or_quote_traversal(
    monkeypatch, kind
):
    tape, account, bound, proposal, _ = capacity_context(idle=True)
    args = arguments(tape, account, bound, proposal)
    if kind == "binding_id":
        bound = (*bound[:-1], changed(bound[-1], publication_id="unmatched"))
    elif kind == "point_id":
        bound = (
            *bound[:-1],
            changed(bound[-1], point=changed(bound[-1].point, point_id="ordinary")),
        )
    elif kind == "point_pin":
        bound = (*bound[:-1], changed(bound[-1], point_sha256="A" * 64))
    elif kind == "quote_time":
        tape = changed(
            tape, quotes=(*tape.quotes[:-1], changed(tape.quotes[-1], received_at_ns=END))
        )
    else:
        pubs = (*tape.publications[:-1], changed(tape.publications[-1], published_cursor=127))
        tape = changed(tape, publications=pubs)
    forbid_numeric_and_mutation(monkeypatch)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)


@pytest.mark.parametrize(
    "kind",
    (
        "zero_quotes",
        "129_quotes",
        "zero_publications",
        "five_publications",
        "quote_tuple_subclass",
        "pub_tuple_subclass",
        "bindings_list",
        "bindings_tuple_subclass",
        "bindings_empty",
        "bindings_five",
        "bindings_omit",
        "bindings_reorder",
        "duplicate_point_id",
        "duplicate_pub_id",
        "cadence_short",
        "cursor_reordered",
        "quote_timestamp_reordered",
        "later_equal_cursor",
    ),
)
def test_complete_count_tuple_uniqueness_cadence_and_cursor_guards_before_prices(monkeypatch, kind):
    tape, account, bound, proposal, _ = capacity_context(idle=True)
    args = arguments(tape, account, bound, proposal)
    if kind == "zero_quotes":
        tape = changed(tape, quotes=())
    elif kind == "129_quotes":
        tape = changed(tape, quotes=(*tape.quotes, tape.quotes[-1]))
    elif kind == "zero_publications":
        tape = changed(tape, publications=())
    elif kind == "five_publications":
        tape = changed(tape, publications=(*tape.publications, tape.publications[-1]))
    elif kind == "quote_tuple_subclass":
        tape = changed(tape, quotes=TupleSubclass(tape.quotes))
    elif kind == "pub_tuple_subclass":
        tape = changed(tape, publications=TupleSubclass(tape.publications))
    elif kind == "bindings_list":
        bound = list(bound)
    elif kind == "bindings_tuple_subclass":
        bound = TupleSubclass(bound)
    elif kind == "bindings_empty":
        bound = ()
    elif kind == "bindings_five":
        bound = (*bound, bound[-1])
    elif kind == "bindings_omit":
        bound = bound[:-1]
    elif kind == "bindings_reorder":
        bound = (bound[1], bound[0], *bound[2:])
    elif kind == "duplicate_point_id":
        bound = (
            *bound[:-1],
            changed(bound[-1], point=changed(bound[-1].point, point_id=bound[0].point.point_id)),
        )
    elif kind == "duplicate_pub_id":
        pubs = (
            *tape.publications[:-1],
            changed(tape.publications[-1], publication_id=tape.publications[0].publication_id),
        )
        tape = changed(tape, publications=pubs)
    elif kind == "cadence_short":
        pubs = (
            tape.publications[0],
            changed(tape.publications[1], received_at_ns=PUB + SECOND - 1),
            *tape.publications[2:],
        )
        tape = changed(tape, publications=pubs)
    elif kind == "cursor_reordered":
        pubs = (tape.publications[1], tape.publications[0], *tape.publications[2:])
        tape = changed(tape, publications=pubs)
    elif kind == "quote_timestamp_reordered":
        tape = changed(tape, quotes=(tape.quotes[1], tape.quotes[0], *tape.quotes[2:]))
    else:
        # Cursor1 is the first row at readiness; cursor2 is its equal-time suffix.
        pub = changed(tape.publications[0], published_cursor=2, received_at_ns=PUB + DELAY)
        tape = changed(tape, publications=(pub, *tape.publications[1:]))
    forbid_numeric_and_mutation(monkeypatch)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)


@pytest.mark.parametrize("bad", (True, -1, START - 1, END, IntSubclass(PUB)))
def test_quote_timestamp_metadata_precedes_bid_ask_inspection(monkeypatch, bad):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    tape = changed(tape, quotes=(changed(tape.quotes[0], received_at_ns=bad), *tape.quotes[1:]))
    forbid_numeric_and_mutation(monkeypatch)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)


@pytest.mark.parametrize(
    "kind", ("scenario", "initialization", "seed", "economics", "margin", "limits")
)
def test_fresh_genesis_complete_revalidation_before_price_or_feature_traversal(monkeypatch, kind):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    if kind == "scenario":
        account = changed(account, scenario_id="ordinary-account")
    elif kind == "initialization":
        account = changed(account, seed=replace(account.seed, initialized_at_ns=START + 1))
    elif kind == "seed":
        account = changed(account, seed=changed(account.seed, initial_balance_usd_micros=True))
    elif kind == "economics":
        account = changed(account, economics=changed(account.economics, tick_value_usd_micros=True))
    elif kind == "margin":
        economics = changed(
            account.economics,
            margin=changed(account.economics.margin, initial_usd_micros_per_contract=True),
        )
        account = changed(account, economics=economics)
    else:
        account = changed(account, limits=changed(account.limits, max_snapshot_age_ns=True))
    forbid_numeric_and_mutation(monkeypatch)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)


def test_binding_constructor_is_metadata_only_but_hash_consumption_revalidates_numeric_values():
    value = feature_point()
    bad = changed(value, values=(object(),) * 37)
    declared = walker.PublishedLiquidityBinding("pub-1", True, bad, "0" * 64)
    assert declared.point is bad
    with pytest.raises(walker.SyntheticFundedPathError):
        walker.bindings_sha256((declared,))


@pytest.mark.parametrize("index", range(37))
@pytest.mark.parametrize("bad", (True, float("nan"), float("inf"), "1"), ids=safe_id)
def test_every_feature_is_completely_validated_even_for_ineligible_idle_publication(index, bad):
    tape, account, bound, proposal = baseline()
    proposal = declaration("no_trade")
    args = arguments(tape, account, bound, proposal)
    values = list(bound[0].point.values)
    values[index] = bad
    poisoned = changed(bound[0].point, values=tuple(values))
    bound = (changed(bound[0], point=poisoned, eligible=False),)
    if type(bad) in (bool, str):
        # These malformed scalars have canonical bytes. Matching independently
        # retained pins prevent a stale-pin mismatch from masking type refusal.
        bound = (changed(bound[0], point_sha256=digest(point_body(poisoned))),)
        args = arguments(tape, account, bound, proposal)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)


@pytest.mark.parametrize(
    "field,bad",
    (
        ("bid_nano", 0),
        ("bid_nano", True),
        ("bid_nano", PRICE + 1),
        ("bid_nano", IntSubclass(PRICE)),
        ("ask_nano", PRICE),
        ("ask_nano", PRICE - TICK),
        ("ask_nano", PRICE + TICK + 1),
        ("ask_nano", IntSubclass(PRICE + TICK)),
    ),
    ids=safe_id,
)
def test_every_original_quote_price_revalidated_even_without_trades(field, bad):
    tape, account, bound, proposal = baseline()
    proposal = declaration("no_trade")
    rows = (*tape.quotes[:-1], changed(tape.quotes[-1], **{field: bad}))
    tape = changed(tape, quotes=rows)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, arguments(tape, account, bound, proposal))


@pytest.mark.parametrize("bad", BAD_PINS, ids=safe_id)
def test_late_individual_retained_pin_syntax_precedes_all_binding_numbers(monkeypatch, bad):
    tape, _, bound, _, _ = capacity_context(idle=True)
    bound = (*bound[:-1], changed(bound[-1], point_sha256=bad))
    monkeypatch.setattr(point.math, "isfinite", forbidden)
    with pytest.raises(walker.SyntheticFundedPathError):
        walker.bindings_sha256(bound)
    assert len(tape.publications) == 4


def test_individual_point_content_pin_and_complete_binding_pin_are_both_retained():
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    changed_point = replace(bound[0].point, values=vector(1, mid_travel_5s_ticks=1))
    stale_individual = (replace(bound[0], point=changed_point),)
    with pytest.raises(walker.SyntheticFundedPathError):
        walker.bindings_sha256(stale_individual)
    coherent_individual = (
        replace(bound[0], point=changed_point, point_sha256=digest(point_body(changed_point))),
    )
    assert walker.bindings_sha256(coherent_individual) == digest(bindings_body(coherent_individual))
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, coherent_individual, proposal, args)


@pytest.mark.parametrize("delta", (0, 1))
def test_cooldown_metadata_scope_near_integer_bound_before_price_access(monkeypatch, delta):
    start, end = MAX_INT - 100 * SECOND, MAX_INT - COOLDOWN + delta
    at = end - 30 * SECOND
    tape = fixture((quote(at), quote(at + DELAY)), (at,), start=start, end=end)
    account, bound, proposal = genesis(start=start), bindings(tape), declaration()
    if delta == 0:
        result = assert_complete(
            tape,
            account,
            bound,
            proposal,
            ["entry_selected"],
            [
                candidate_spec(
                    entry_cursor=1, exit_cursor=None, exit_outcome="constructed_exit_unknown"
                )
            ],
        )
        assert result.candidates[0].exit_outcome_at_ns < end
    else:
        args = arguments(tape, account, bound, proposal)
        forbid_numeric_and_mutation(monkeypatch)
        with pytest.raises(walker.SyntheticFundedPathError):
            invoke(tape, account, bound, proposal, args)


@pytest.mark.parametrize("favorable", (-2, 2))
def test_used_realization_overflow_refuses_whole_plan_without_clipping_or_seed_mutation(favorable):
    tape, account, bound, proposal = baseline()
    account = replace(account, economics=replace(account.economics, tick_value_usd_micros=MAX_INT))
    tape = replace(
        tape,
        quotes=(
            *tape.quotes[:-1],
            crossed_quote(PUB + 2 * DELAY + HOLD, "long", PRICE + TICK, favorable),
        ),
    )
    args = arguments(tape, account, bound, proposal)
    original = canonical(
        [asdict(tape), asdict(account), [asdict(b) for b in bound], asdict(proposal)]
    )
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)
    assert (
        canonical([asdict(tape), asdict(account), [asdict(b) for b in bound], asdict(proposal)])
        == original
    )


def test_complete_bindings_byte_guard_exact_body_and_size_minus_one_with_valid_point_pins(
    monkeypatch,
):
    tape, account, bound, proposal, _ = capacity_context(large=True, idle=True)
    expected, size = digest(bindings_body(bound)), len(canonical(bindings_body(bound)))
    assert size > len(canonical(protocol_body()))
    assert all(len(canonical(point_body(b.point))) < size - 1 for b in bound)
    assert walker.bindings_sha256(bound) == expected
    monkeypatch.setattr(walker, "MAX_CANONICAL_BYTES", size)
    assert walker.protocol_sha256() == digest(protocol_body())
    assert walker.bindings_sha256(bound) == expected
    monkeypatch.setattr(walker, "MAX_CANONICAL_BYTES", size - 1)
    assert walker.protocol_sha256() == digest(protocol_body())
    with pytest.raises(walker.SyntheticFundedPathError):
        walker.bindings_sha256(bound)
    assert account.seed.initialized_at_ns == tape.start_ns and proposal.policy_id == "no_trade"


def test_complete_result_byte_guard_exact_size_and_size_minus_one_preserve_fixed_protocol(
    monkeypatch,
):
    tape, account, bound, proposal, specs = capacity_context(large=True)
    expected = complete_oracle(tape, account, bound, proposal, ["entry_selected"] * 4, specs)
    body = dict(expected)
    del body["plan_sha256"]
    size = len(canonical(body))
    args = arguments(tape, account, bound, proposal)
    assert len(canonical(bindings_body(bound))) < size - 1
    monkeypatch.setattr(walker, "MAX_CANONICAL_BYTES", size)
    assert walker.protocol_sha256() == args["expected_protocol_sha256"]
    assert canonical(asdict(invoke(tape, account, bound, proposal, args))) == canonical(expected)
    assert canonical(
        asdict(invoke(tape, account, bound, proposal, args, output=expected["plan_sha256"]))
    ) == canonical(expected)
    monkeypatch.setattr(walker, "MAX_CANONICAL_BYTES", size - 1)
    assert walker.protocol_sha256() == args["expected_protocol_sha256"]
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args, output=expected["plan_sha256"])


def test_fixed_protocol_complete_byte_guard_exact_and_excess(monkeypatch):
    expected = digest(protocol_body())
    size = len(canonical(protocol_body()))
    monkeypatch.setattr(walker, "MAX_CANONICAL_BYTES", size)
    assert walker.protocol_sha256() == expected
    monkeypatch.setattr(walker, "MAX_CANONICAL_BYTES", size - 1)
    with pytest.raises(walker.SyntheticFundedPathError):
        walker.protocol_sha256()


@pytest.mark.parametrize("name,cap", (("MAX_QUOTES", 3), ("MAX_PUBLICATIONS", 0)))
def test_lowered_runtime_input_caps_precede_numbers_without_changing_protocol_identity(
    monkeypatch, name, cap
):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    monkeypatch.setattr(walker, name, cap)
    assert walker.protocol_sha256() == args["expected_protocol_sha256"]
    forbid_numeric_and_mutation(monkeypatch)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)


@pytest.mark.parametrize("cap", (2, 3, 4, 19))
def test_lowered_record_cap_never_returns_successful_subset_or_reseeds(monkeypatch, cap):
    tape, account, bound, proposal, _ = capacity_context()
    args = arguments(tape, account, bound, proposal)
    original = canonical(
        [asdict(tape), asdict(account), [asdict(b) for b in bound], asdict(proposal)]
    )
    monkeypatch.setattr(walker, "MAX_ACCOUNTING_RECORDS", cap)
    assert walker.protocol_sha256() == args["expected_protocol_sha256"]
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)
    assert (
        canonical([asdict(tape), asdict(account), [asdict(b) for b in bound], asdict(proposal)])
        == original
    )
    # A genuinely complete two-record denied path remains legal at every tested cap.
    tape = fixture((quote(PUB),))
    account, bound, proposal = genesis(balance=1), bindings(tape), declaration()
    denied = assert_complete(
        tape,
        account,
        bound,
        proposal,
        ["budget_denied"],
        [candidate_spec(disposition="budget_denied")],
    )
    assert len(denied.records) == 2


@pytest.mark.parametrize("component", ("quote", "point", "eligibility"))
def test_future_suffix_changes_only_correct_complete_component_pins_and_not_prior_causal_values(
    component,
):
    tape, account, bound, proposal, specs = capacity_context()
    original = assert_complete(tape, account, bound, proposal, ["entry_selected"] * 4, specs)
    original_args = arguments(tape, account, bound, proposal)
    if component == "quote":
        tape = replace(
            tape,
            quotes=(*tape.quotes[:-1], quote(tape.quotes[-1].received_at_ns, PRICE + 10 * TICK)),
        )
        dispositions = ["entry_selected"] * 4
    elif component == "point":
        value = replace(bound[-1].point, values=vector(-1))
        bound = (
            *bound[:-1],
            replace(bound[-1], point=value, point_sha256=digest(point_body(value))),
        )
        dispositions = ["entry_selected"] * 4
    else:
        bound = (*bound[:-1], replace(bound[-1], eligible=False))
        dispositions = ["entry_selected"] * 3 + ["ineligible"]
        specs = specs[:-1]
    altered = assert_complete(tape, account, bound, proposal, dispositions, specs)
    altered_args = arguments(tape, account, bound, proposal)
    if component == "quote":
        assert altered_args["expected_fixture_sha256"] != original_args["expected_fixture_sha256"]
        assert altered_args["expected_bindings_sha256"] == original_args["expected_bindings_sha256"]
    else:
        assert altered_args["expected_fixture_sha256"] == original_args["expected_fixture_sha256"]
        assert altered_args["expected_bindings_sha256"] != original_args["expected_bindings_sha256"]
    assert (
        altered.declaration_sha256 != original.declaration_sha256
        and altered.plan_sha256 != original.plan_sha256
    )
    for before, after in zip(
        original.publication_audit[:3], altered.publication_audit[:3], strict=True
    ):
        assert before.first_disposition == after.first_disposition
        assert before.selected_direction == after.selected_direction
        assert before.accounting_prefix_before == after.accounting_prefix_before
        assert before.accounting_prefix_after == after.accounting_prefix_after
        assert before.budget_decision == after.budget_decision
        assert (
            before.publication.prefix.consumed_content_sha256
            == after.publication.prefix.consumed_content_sha256
        )
        if component == "quote":
            assert (
                before.publication.prefix.fixture_sha256 != after.publication.prefix.fixture_sha256
            )
    assert original.quote_audit[:96] == altered.quote_audit[:96]
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, original_args, output=original.plan_sha256)


@pytest.mark.parametrize(
    "kind",
    (
        "omit_quote",
        "insert_equal_quote",
        "omit_binding",
        "change_genesis",
        "change_policy",
        "change_source_metadata",
    ),
)
def test_retained_complete_context_never_adopts_omitted_reordered_or_changed_inputs(kind):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    original = complete_oracle(
        tape, account, bound, proposal, ["entry_selected"], [candidate_spec()]
    )
    if kind == "omit_quote":
        tape = replace(tape, quotes=tape.quotes[:-1])
    elif kind == "insert_equal_quote":
        rows = (quote(PUB), quote(PUB, PRICE + TICK), *tape.quotes[1:])
        tape = fixture(rows)
    elif kind == "omit_binding":
        bound = ()
    elif kind == "change_genesis":
        account = replace(account, seed=replace(account.seed, initial_balance_usd_micros=1001))
    elif kind == "change_policy":
        proposal = replace(proposal, policy_id="no_trade")
    else:
        tape = replace(tape, source_sha256="b" * 64)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args, output=original["plan_sha256"])


@pytest.mark.parametrize(
    "field",
    (
        "authority_flags",
        "terminal_cooldown_until_ns",
        "terminal_fee",
        "budget",
        "candidate_range",
        "record_link",
        "quote_audit",
        "first_disposition",
        "point_selection",
        "entry_cursor",
        "terminal_native",
    ),
)
def test_verifier_rebuilds_every_complete_field_not_just_closed_cash_or_headline_counts(field):
    tape, account, bound, proposal = baseline()
    expected = complete_oracle(
        tape, account, bound, proposal, ["entry_selected"], [candidate_spec()]
    )
    altered = json.loads(canonical(expected))
    del altered["plan_sha256"]
    if field == "authority_flags":
        altered[field][0][1] = True
    elif field == "terminal_cooldown_until_ns":
        altered[field] += 1
    elif field == "terminal_fee":
        altered["terminal_accounting_state"]["entry_fees_usd_micros"] += 1
    elif field == "budget":
        altered["candidates"][0]["budget_decision"]["snapshot"]["sequence"] = 0
    elif field == "candidate_range":
        altered["candidates"][0]["record_stop"] = 4
    elif field == "record_link":
        altered["record_links"][0]["candidate_ordinal"] = 2
    elif field == "quote_audit":
        altered["quote_audit"][-1]["consumed_count"] -= 1
    elif field == "first_disposition":
        altered["publication_audit"][0]["first_disposition"] = "budget_denied"
    elif field == "point_selection":
        altered["publication_audit"][0]["point_selection"]["directions"][0][1] = 0
    elif field == "entry_cursor":
        altered["candidates"][0]["entry_outcome_cursor"] = 0
    else:
        altered["terminal_native_prefix"]["consumed_count"] -= 1
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(
            tape,
            account,
            bound,
            proposal,
            arguments(tape, account, bound, proposal),
            output=digest(altered),
        )


@pytest.mark.parametrize(
    "api",
    (
        "protocol_sha256",
        "bindings_sha256",
        "declaration_sha256",
        "build_funded_path_plan",
        "verify_funded_path_plan",
    ),
)
@pytest.mark.parametrize("exception", (ValueError, TypeError, AttributeError, OverflowError))
def test_new_canonical_failures_become_declared_errors(api, exception, monkeypatch):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    output = complete_oracle(
        tape, account, bound, proposal, ["entry_selected"], [candidate_spec()]
    )["plan_sha256"]

    def fail(*unused_args, **unused_kwargs):
        raise exception("Invented canonical encoder failure")

    monkeypatch.setattr(walker.json, "dumps", fail)
    with pytest.raises(walker.SyntheticFundedPathError):
        if api == "protocol_sha256":
            walker.protocol_sha256()
        elif api == "bindings_sha256":
            walker.bindings_sha256(bound)
        elif api == "declaration_sha256":
            walker.declaration_sha256(
                proposal,
                fixture_sha256=args["expected_fixture_sha256"],
                genesis_sha256=args["expected_genesis_sha256"],
                bindings_sha256=args["expected_bindings_sha256"],
            )
        else:
            invoke(
                tape,
                account,
                bound,
                proposal,
                args,
                output=output if api == "verify_funded_path_plan" else None,
            )


def test_frozen_slotted_pure_repeatable_complete_calls_do_not_mutate_supplied_inputs():
    tape, account, bound, proposal = baseline()
    original = canonical(
        [asdict(tape), asdict(account), [asdict(b) for b in bound], asdict(proposal)]
    )
    first = assert_complete(tape, account, bound, proposal, ["entry_selected"], [candidate_spec()])
    second = invoke(tape, account, bound, proposal)
    assert second == first and second is not first
    assert (
        canonical([asdict(tape), asdict(account), [asdict(b) for b in bound], asdict(proposal)])
        == original
    )
    for value in (
        bound[0],
        proposal,
        first,
        first.publication_audit[0],
        first.candidates[0],
        first.candidates[0].identities,
        first.quote_audit[0],
        first.record_links[0],
    ):
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)


def test_complete_build_rebuild_and_hashes_use_no_files_process_network_or_wall_clock(monkeypatch):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    expected = complete_oracle(
        tape, account, bound, proposal, ["entry_selected"], [candidate_spec()]
    )
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)
    monkeypatch.setattr(time, "perf_counter", forbidden)
    assert walker.protocol_sha256() == args["expected_protocol_sha256"]
    assert walker.bindings_sha256(bound) == args["expected_bindings_sha256"]
    assert (
        walker.declaration_sha256(
            proposal,
            fixture_sha256=args["expected_fixture_sha256"],
            genesis_sha256=args["expected_genesis_sha256"],
            bindings_sha256=args["expected_bindings_sha256"],
        )
        == args["expected_declaration_sha256"]
    )
    assert canonical(asdict(invoke(tape, account, bound, proposal, args))) == canonical(expected)
    assert canonical(
        asdict(invoke(tape, account, bound, proposal, args, output=expected["plan_sha256"]))
    ) == canonical(expected)


def test_source_imports_only_standard_library_and_permitted_held_pure_helpers():
    tree = ast.parse(inspect.getsource(walker))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] in sys.stdlib_module_names for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "ai_trader.research":
                assert all(
                    alias.name
                    in {
                        "six_e_native_prefix",
                        "six_e_declared_admission",
                        "six_e_entry_budget",
                        "six_e_declared_economics",
                        "six_e_native_admission_assessment",
                        "six_e_synthetic_liquidity_point",
                    }
                    for alias in node.names
                )
            else:
                assert node.module.split(".")[0] in sys.stdlib_module_names
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"open", "eval", "exec", "compile", "__import__"}


@pytest.mark.parametrize("bad", ("A" * 64, "a" * 63))
def test_declared_helper_pin_syntax_precedes_invalid_binding_metadata(monkeypatch, bad):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    retained = tuple(HELPER_PINS.items())
    poisoned = (*retained[:-1], (retained[-1][0], bad))
    monkeypatch.setattr(walker, "_HELPER_SOURCE_PINS", poisoned)
    bound = (changed(bound[0], eligible=1),)
    forbid_numeric_and_mutation(monkeypatch)
    with pytest.raises(walker.SyntheticFundedPathError, match="SHA256"):
        invoke(tape, account, bound, proposal, args)


def test_long_gap_closes_hold_then_unknown_before_consuming_late_quote(monkeypatch):
    hold, deadline = PUB + DELAY + HOLD, PUB + 2 * DELAY + HOLD + WAIT
    rows = (quote(PUB), quote(PUB + DELAY), quote(deadline + 1), quote(PUB + 30 * SECOND))
    tape = fixture(rows, (PUB, deadline + 1, PUB + 30 * SECOND))
    account, bound, proposal = genesis(), bindings(tape), declaration()
    expected = complete_oracle(
        tape,
        account,
        bound,
        proposal,
        ["entry_selected", "inventory_blocked", "inventory_blocked"],
        [candidate_spec(entry_cursor=1, exit_cursor=None, exit_outcome="constructed_exit_unknown")],
    )
    calls = []
    consume, advance = native.consume_next, admission.advance

    def consumed(*args, **kwargs):
        calls.append(("consume", kwargs["expected_cursor"]))
        return consume(*args, **kwargs)

    def advanced(*args, **kwargs):
        record = args[2]
        calls.append(("event", record.event_id, record.recorded_at_ns))
        return advance(*args, **kwargs)

    monkeypatch.setattr(native, "consume_next", consumed)
    monkeypatch.setattr(admission, "advance", advanced)
    result = invoke(tape, account, bound, proposal, arguments(tape, account, bound, proposal))
    assert canonical(asdict(result)) == canonical(expected)
    ids = {name: value.format(ordinal=1) for name, value in TEMPLATES.items()}
    assert calls == [
        ("consume", 0),
        ("event", ids["clock_event_id"], PUB),
        ("event", ids["request_event_id"], PUB),
        ("consume", 1),
        ("event", ids["entry_outcome_event_id"], PUB + DELAY),
        ("event", ids["exit_request_event_id"], hold),
        ("event", ids["exit_outcome_event_id"], deadline),
        ("consume", 2),
        ("consume", 3),
        # Final verification replays the retained request on its old prefix;
        # it does not append a new record to the terminal UNKNOWN history.
        ("event", ids["request_event_id"], PUB),
    ]
    assert result.record_links[3].boundary.through_ns == hold - 1
    assert result.record_links[4].boundary.through_ns == deadline
    assert result.record_links[3].native_prefix == result.record_links[4].native_prefix


@pytest.mark.parametrize("sign", (-1, 1))
def test_nonzero_publication_global_cursor_and_first_candidate_ignore_future_equal_suffix(sign):
    side, entry_price = ("long", PRICE + TICK) if sign == 1 else ("short", PRICE)
    hold, exit_at = PUB + DELAY + HOLD, PUB + 2 * DELAY + HOLD
    rows = (
        quote(START),
        quote(PUB - 1),
        quote(PUB),
        quote(PUB, PRICE + 100 * TICK),
        quote(PUB + DELAY - 1),
        quote(PUB + DELAY),
        quote(PUB + DELAY, PRICE + 200 * TICK),
        quote(hold),
        crossed_quote(exit_at, side, entry_price, -4, 3 * TICK),
        crossed_quote(exit_at, side, entry_price, 1000),
    )
    tape = fixture(rows)
    result = assert_complete(
        tape,
        genesis(),
        bindings(tape, [sign]),
        declaration(),
        ["entry_selected"],
        [candidate_spec(entry_cursor=5, exit_cursor=8)],
    )
    assert result.publication_audit[0].publication.published_cursor == 2
    assert result.publication_audit[0].publication.prefix.consumed_count == 3
    assert result.record_links[0].native_prefix.consumed_count == 3
    assert result.record_links[2].native_prefix.last_cursor == 5
    assert result.record_links[-1].native_prefix.last_cursor == 8
    assert result.terminal_accounting_state.gross_realized_usd_micros == -500


def test_idle_missing_margin_is_valid_and_does_not_invent_admission_or_margin():
    tape, account, bound, proposal, _ = capacity_context(idle=True)
    account = replace(account, economics=replace(account.economics, margin=None))
    result = assert_complete(tape, account, bound, proposal, ["no_signal"] * 4, [])
    assert result.records == result.candidates == ()
    assert result.terminal_accounting_state.total_commitments_usd_micros == 0
    assert (
        result.terminal_accounting_state.complete_declared_equity_usd_micros
        == account.seed.initial_balance_usd_micros
    )


NONNEGATIVE_FEATURES = tuple(
    name
    for index, name in enumerate(FEATURES)
    if (
        index >= 23
        or name.startswith("log_")
        or name
        in {
            "bid_span5_ticks",
            "ask_span5_ticks",
            "mid_range_5s_ticks",
            "mid_travel_5s_ticks",
            "normalized_bid_reload_5s",
            "normalized_ask_reload_5s",
            "buy_absorption_proxy_5s",
            "sell_absorption_proxy_5s",
        }
    )
)
DOMAIN_FAILURES = (
    tuple((name, -1) for name in NONNEGATIVE_FEATURES)
    + tuple(
        (name, value)
        for name in ("unknown_trade_fraction_5s", "bid_top_share5", "ask_top_share5")
        for value in (-1, 2)
    )
    + tuple((name, value) for name in ("queue_imbalance", "depth5_imbalance") for value in (-2, 2))
)


@pytest.mark.parametrize("name,bad", DOMAIN_FAILURES)
def test_original_numeric_domains_with_matching_complete_malformed_point_pin(name, bad):
    tape, account, bound, proposal = baseline()
    proposal = declaration("no_trade")
    values = list(bound[0].point.values)
    values[FEATURES.index(name)] = bad
    poisoned = changed(bound[0].point, values=tuple(values))
    bound = (changed(bound[0], point=poisoned, point_sha256=digest(point_body(poisoned))),)
    args = arguments(tape, account, bound, proposal)
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)


@pytest.mark.parametrize("api", ("bindings_sha256", "build_funded_path_plan"))
def test_unrepresentably_large_integer_becomes_declared_error_not_raw_overflow(api):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    values = list(bound[0].point.values)
    values[FEATURES.index("normalized_cvd_5s")] = 10**10000
    poisoned = changed(bound[0].point, values=tuple(values))
    bound = (changed(bound[0], point=poisoned),)
    with pytest.raises(walker.SyntheticFundedPathError):
        if api == "bindings_sha256":
            walker.bindings_sha256(bound)
        else:
            invoke(tape, account, bound, proposal, args)


@pytest.mark.parametrize("left,right", ((1, 1.0), (0, -0.0)))
def test_numeric_representation_identity_is_preserved_not_coerced(left, right):
    tape, account, bound, proposal = baseline()
    values = list(bound[0].point.values)
    index = FEATURES.index("mid_travel_5s_ticks")
    outputs = []
    for scalar in (left, right):
        values[index] = scalar
        value = point.SyntheticLiquidityPoint(bound[0].point.point_id, tuple(values))
        altered = (replace(bound[0], point=value, point_sha256=digest(point_body(value))),)
        outputs.append(
            assert_complete(
                tape, account, altered, proposal, ["entry_selected"], [candidate_spec()]
            )
        )
    assert outputs[0].bindings_sha256 != outputs[1].bindings_sha256
    assert outputs[0].plan_sha256 != outputs[1].plan_sha256
    assert (
        outputs[0].publication_audit[0].selected_direction
        == outputs[1].publication_audit[0].selected_direction
    )


@pytest.mark.parametrize("name", ("fixture_sha256", "genesis_sha256", "bindings_sha256"))
@pytest.mark.parametrize("bad", BAD_PINS, ids=safe_id)
def test_prospective_declaration_rejects_every_context_pin_syntax_before_encoding(
    monkeypatch, name, bad
):
    tape, account, bound, proposal = baseline()
    args = arguments(tape, account, bound, proposal)
    context = {
        "fixture_sha256": args["expected_fixture_sha256"],
        "genesis_sha256": args["expected_genesis_sha256"],
        "bindings_sha256": args["expected_bindings_sha256"],
    }
    context[name] = bad
    monkeypatch.setattr(walker.json, "dumps", forbidden)
    with pytest.raises(walker.SyntheticFundedPathError):
        walker.declaration_sha256(proposal, **context)


@pytest.mark.parametrize(
    "field,bad",
    (
        ("publication_id", "bad/id"),
        ("publication_id", StrSubclass("pub-1")),
        ("eligible", True + 0),
        ("eligible", None),
        ("point_sha256", "A" * 64),
        ("point_sha256", StrSubclass("a" * 64)),
        ("point", None),
    ),
)
def test_binding_constructor_validates_its_metadata_without_any_numeric_access(
    monkeypatch, field, bad
):
    value = changed(feature_point(), values=(object(),) * 37)
    context = {
        "publication_id": "pub-1",
        "eligible": True,
        "point": value,
        "point_sha256": "a" * 64,
    }
    context[field] = bad
    monkeypatch.setattr(point.math, "isfinite", forbidden)
    with pytest.raises(walker.SyntheticFundedPathError):
        walker.PublishedLiquidityBinding(**context)


@pytest.mark.parametrize(
    "field,bad",
    (
        ("declaration_id", "ordinary"),
        ("declaration_id", "synthetic-"),
        ("declaration_id", StrSubclass("synthetic-funded-plan")),
        ("policy_id", "vote"),
        ("policy_id", StrSubclass("cvd_follow")),
        ("exit_plan", "broker_exit"),
        ("exit_plan", StrSubclass("time_exit")),
    ),
)
def test_declaration_constructor_validates_closed_metadata(field, bad):
    context = {
        "declaration_id": "synthetic-funded-plan",
        "policy_id": "cvd_follow",
        "exit_plan": "time_exit",
    }
    context[field] = bad
    with pytest.raises(walker.SyntheticFundedPathError):
        walker.FundedPathDeclaration(**context)


@pytest.mark.parametrize("component", ("margin", "fee", "buffer"))
def test_used_budget_requirement_overflow_refuses_complete_plan_without_clipping(component):
    tape, _, bound, proposal = baseline()
    context = {"balance": MAX_INT, "margin": 1, "entry": 1, "exit_fee": 1, "buffer": 1}
    context[{"margin": "margin", "fee": "entry", "buffer": "buffer"}[component]] = MAX_INT
    account = genesis(**context)
    args = arguments(tape, account, bound, proposal)
    original = canonical(
        [asdict(tape), asdict(account), [asdict(value) for value in bound], asdict(proposal)]
    )
    with pytest.raises(walker.SyntheticFundedPathError):
        invoke(tape, account, bound, proposal, args)
    assert (
        canonical(
            [asdict(tape), asdict(account), [asdict(value) for value in bound], asdict(proposal)]
        )
        == original
    )
