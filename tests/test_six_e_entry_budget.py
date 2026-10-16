"""Constructed declared-budget snapshots only; no tape, quotes or account mutation."""

import builtins
import sqlite3
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from ai_trader.research import six_e_declared_economics as economics
from ai_trader.research import six_e_entry_budget as budget

START = economics.replay.target.window("2025-03-26")[0]
SECOND = economics.replay.target.SECOND
NOW = START + 10 * SECOND
PIN = "a" * 64
MAX = economics.MAX_MONEY


def snapshot(**changes):
    return replace(
        budget.DeclaredCapitalSnapshot(
            seed=economics.EconomicSeed(1000, START),
            declared_realization_balance_usd_micros=1000,
            sequence=1,
            tip_sha256=PIN,
            last_event_at_ns=START + SECOND,
            observed_through_ns=NOW,
            remaining_position_contracts=0,
            reserved_exit_contracts=0,
            reservation_status=None,
            pending_entry=False,
        ),
        **changes,
    )


def proposal(**changes):
    return replace(
        budget.EntryProposal(
            decision_at_ns=NOW,
            expected_sequence=1,
            expected_tip_sha256=PIN,
            contract="6EM5",
            quantity_contracts=1,
        ),
        **changes,
    )


def declared(**changes):
    return replace(
        economics.DeclaredEconomics("USD", 125, 10, 20, economics.DeclaredMargin(100, 80)),
        **changes,
    )


def limits(**changes):
    return replace(budget.DeclaredBudgetLimits(5, 5, None), **changes)


def assess(s=None, p=None, e=None, bounds=None):
    return budget.assess_entry_budget(
        snapshot() if s is None else s,
        proposal() if p is None else p,
        declared() if e is None else e,
        limits() if bounds is None else bounds,
    )


def poison(value, field, changed):
    object.__setattr__(value, field, changed)
    return value


def test_available_is_declared_arithmetic_and_never_fee_payment_or_admission():
    s, p, e, bounds = snapshot(), proposal(), declared(), limits()
    result = assess(s, p, e, bounds)
    assert result.disposition == "declared_budget_available"
    assert result.declared_requirement_usd_micros == 135
    assert result.declared_balance_less_requirement_usd_micros == 865
    assert result.realization_loss_from_original_seed_usd_micros == 0
    assert result.hypothetical_loss_after_entry_fee_usd_micros == 10
    assert result.declared_budget_condition_met is True
    assert result.snapshot_age_ns == 0
    assert result.snapshot == s
    assert result.proposal == p
    assert result.economics == e
    assert result.limits == bounds
    assert s.declared_realization_balance_usd_micros == 1000
    assert s.reserved_exit_contracts == 0
    assert s.pending_entry is False


def test_valid_genesis_identity_needs_no_prior_event():
    s = snapshot(sequence=0, last_event_at_ns=None)
    result = assess(s, proposal(expected_sequence=0))
    assert result.disposition == "declared_budget_available"
    assert result.snapshot.sequence == 0
    assert result.snapshot.last_event_at_ns is None


@pytest.mark.parametrize(
    ("balance", "disposition", "remainder"),
    [
        (135, "declared_budget_available", 0),
        (134, "declared_budget_insufficient", -1),
        (-1, "declared_budget_insufficient", -136),
    ],
)
def test_exact_cash_equality_passes_and_one_unit_shortfall_fails(balance, disposition, remainder):
    result = assess(snapshot(declared_realization_balance_usd_micros=balance))
    assert result.disposition == disposition
    assert result.declared_requirement_usd_micros == 135
    assert result.declared_balance_less_requirement_usd_micros == remainder
    assert result.declared_budget_condition_met is (balance == 135)


@pytest.mark.parametrize("margin", [None, economics.DeclaredMargin(0, 0)])
def test_missing_margin_stays_null_while_explicit_zero_costs_and_margin_remain_zero(margin):
    result = assess(
        snapshot(declared_realization_balance_usd_micros=0),
        e=declared(
            entry_fee_usd_micros_per_contract=0,
            exit_fee_usd_micros_per_contract=0,
            margin=margin,
        ),
        bounds=limits(cash_buffer_usd_micros=0),
    )
    if margin is None:
        assert result.disposition == "budget_undetermined"
        assert result.declared_requirement_usd_micros is None
        assert result.declared_balance_less_requirement_usd_micros is None
        assert result.declared_budget_condition_met is None
    else:
        assert result.disposition == "declared_budget_available"
        assert result.declared_requirement_usd_micros == 0
        assert result.declared_balance_less_requirement_usd_micros == 0
        assert result.declared_budget_condition_met is True


@pytest.mark.parametrize(
    ("balance", "entry_fee", "ceiling", "loss", "after_fee", "disposition"),
    [
        (950, 0, 50, 50, 50, "declared_budget_available"),
        (950, 1, 50, 50, 51, "declared_budget_insufficient"),
        (950, 10, 60, 50, 60, "declared_budget_available"),
        (950, 10, 59, 50, 60, "declared_budget_insufficient"),
        (940, 10, 59, 60, 70, "declared_budget_insufficient"),
        (1100, 10, 0, 0, 0, "declared_budget_available"),
    ],
)
def test_net_loss_ceiling_uses_original_seed_and_proposed_entry_fee_only(
    balance, entry_fee, ceiling, loss, after_fee, disposition
):
    result = assess(
        snapshot(declared_realization_balance_usd_micros=balance),
        e=declared(entry_fee_usd_micros_per_contract=entry_fee),
        bounds=limits(max_cumulative_realization_loss_usd_micros=ceiling),
    )
    assert result.realization_loss_from_original_seed_usd_micros == loss
    assert result.hypothetical_loss_after_entry_fee_usd_micros == after_fee
    assert result.disposition == disposition
    if disposition == "declared_budget_insufficient":
        assert result.declared_balance_less_requirement_usd_micros > 0
        assert result.reasons


def test_exit_reserve_margin_and_buffer_are_requirements_not_realized_fee_losses():
    result = assess(bounds=limits(max_cumulative_realization_loss_usd_micros=10))
    assert result.declared_requirement_usd_micros == 135
    assert result.hypothetical_loss_after_entry_fee_usd_micros == 10
    assert result.disposition == "declared_budget_available"
    assert result.snapshot.declared_realization_balance_usd_micros == 1000


@pytest.mark.parametrize("kind", ["inventory", "PENDING", "UNKNOWN", "pending_entry"])
def test_any_liability_blocks_missing_margin_and_survives_new_session_and_contract(kind):
    changes = (
        {"pending_entry": True} if kind == "pending_entry" else {"remaining_position_contracts": 1}
    )
    if kind in ("PENDING", "UNKNOWN"):
        changes.update(reserved_exit_contracts=1, reservation_status=kind)
    s = snapshot(**changes)
    initial = assess(s, e=declared(margin=None))
    assert initial.disposition == "entry_blocked_by_liability"
    assert initial.declared_budget_condition_met is False
    later = economics.replay.target.window("2025-07-01")[0]
    carried = replace(s, observed_through_ns=later)
    result = assess(carried, proposal(decision_at_ns=later, contract="6EU5"))
    assert result.disposition == "entry_blocked_by_liability"
    assert result.snapshot.seed == s.seed
    assert result.snapshot.declared_realization_balance_usd_micros == 1000
    assert result.snapshot.remaining_position_contracts == s.remaining_position_contracts
    assert result.snapshot.reserved_exit_contracts == s.reserved_exit_contracts
    assert result.snapshot.reservation_status == s.reservation_status
    assert result.snapshot.pending_entry is s.pending_entry


@pytest.mark.parametrize(
    ("age", "disposition"),
    [
        (5, "declared_budget_available"),
        (6, "budget_undetermined"),
    ],
)
def test_snapshot_age_zero_and_bound_equality_pass_but_valid_stale_is_undetermined(
    age, disposition
):
    result = assess(snapshot(observed_through_ns=NOW - age))
    assert result.snapshot_age_ns == age
    assert result.disposition == disposition
    if age == 6:
        assert result.declared_budget_condition_met is None


def test_fresh_publication_frontier_is_not_the_time_of_the_last_event():
    result = assess(snapshot(last_event_at_ns=START + 1, observed_through_ns=NOW))
    assert NOW - result.snapshot.last_event_at_ns > result.limits.max_snapshot_age_ns
    assert result.snapshot_age_ns == 0
    assert result.disposition == "declared_budget_available"


def test_next_day_assessment_retains_the_supplied_seed_and_does_not_reset_loss():
    s = snapshot(declared_realization_balance_usd_micros=950)
    bounds = limits(max_cumulative_realization_loss_usd_micros=59)
    initial = assess(s, bounds=bounds)
    tomorrow = NOW + 86_400 * SECOND
    result = assess(
        replace(s, observed_through_ns=tomorrow), proposal(decision_at_ns=tomorrow), bounds=bounds
    )
    assert initial.disposition == result.disposition == "declared_budget_insufficient"
    assert result.realization_loss_from_original_seed_usd_micros == 50
    assert result.hypothetical_loss_after_entry_fee_usd_micros == 60
    assert result.snapshot.seed.initial_balance_usd_micros == 1000


def test_caller_reseeding_is_not_authenticated_or_detected_by_the_pure_assessor():
    bounds = limits(max_cumulative_realization_loss_usd_micros=59)
    original = snapshot(declared_realization_balance_usd_micros=950)
    assert assess(original, bounds=bounds).disposition == "declared_budget_insufficient"
    declared_again = replace(original, seed=economics.EconomicSeed(900, START))
    result = assess(declared_again, bounds=bounds)
    assert result.disposition == "declared_budget_available"
    assert result.realization_loss_from_original_seed_usd_micros == 0
    assert result.status == "declared_entry_budget_assessment_not_authenticated"
    assert dict(result.authority_flags)["snapshot_prefix_authenticated"] is False
    assert dict(result.authority_flags)["risk_approved"] is False
    assert original.seed.initial_balance_usd_micros == 1000


@pytest.mark.parametrize(
    "change",
    [
        "prefix_sequence",
        "prefix_head",
        "future_frontier",
        "event_after_frontier",
        "frontier_before_seed",
        "genesis_event",
        "nonzero_missing_event",
        "genesis_balance",
        "genesis_pending",
        "reservation_without_inventory",
        "status_without_reservation",
        "bad_status",
        "multi_inventory",
        "negative_frontier",
    ],
)
def test_invalid_prefix_frontier_or_liability_linkage_refuses_instead_of_budget_status(change):
    s, p = snapshot(), proposal()
    if change == "prefix_sequence":
        p = poison(p, "expected_sequence", 2)
    elif change == "prefix_head":
        p = poison(p, "expected_tip_sha256", "b" * 64)
    elif change == "future_frontier":
        s = poison(s, "observed_through_ns", NOW + 1)
    elif change == "event_after_frontier":
        s = poison(s, "last_event_at_ns", NOW + 1)
    elif change == "frontier_before_seed":
        s = poison(s, "observed_through_ns", START - 1)
    elif change in ("genesis_event", "genesis_balance", "genesis_pending"):
        s = poison(s, "sequence", 0)
        p = poison(p, "expected_sequence", 0)
        if change == "genesis_balance":
            poison(s, "last_event_at_ns", None)
            poison(s, "declared_realization_balance_usd_micros", 999)
        elif change == "genesis_pending":
            poison(s, "last_event_at_ns", None)
            poison(s, "pending_entry", True)
    elif change == "nonzero_missing_event":
        s = poison(s, "last_event_at_ns", None)
    elif change == "reservation_without_inventory":
        poison(s, "reserved_exit_contracts", 1)
        poison(s, "reservation_status", "PENDING")
    elif change == "status_without_reservation":
        s = poison(s, "reservation_status", "UNKNOWN")
    elif change == "bad_status":
        poison(s, "remaining_position_contracts", 1)
        poison(s, "reserved_exit_contracts", 1)
        poison(s, "reservation_status", "CLOSED")
    elif change == "multi_inventory":
        s = poison(s, "remaining_position_contracts", 2)
    else:
        s = poison(s, "observed_through_ns", -1)
    if change in ("prefix_sequence", "prefix_head", "future_frontier"):
        with pytest.raises(ValueError, match="prefix|nonfuture"):
            assess(
                s,
                p,
                declared(
                    entry_fee_usd_micros_per_contract=MAX,
                    exit_fee_usd_micros_per_contract=0,
                    margin=economics.DeclaredMargin(0, 0),
                ),
                limits(cash_buffer_usd_micros=1),
            )
    else:
        with pytest.raises(ValueError):
            assess(s, p)


@pytest.mark.parametrize(
    ("target", "field", "value"),
    [
        ("snapshot", "declared_realization_balance_usd_micros", True),
        ("snapshot", "declared_realization_balance_usd_micros", 1000.0),
        ("snapshot", "sequence", True),
        ("snapshot", "tip_sha256", "A" * 64),
        ("snapshot", "observed_through_ns", float(NOW)),
        ("proposal", "contract", "EURUSD"),
        ("snapshot", "pending_entry", 0),
        ("proposal", "decision_at_ns", True),
        ("proposal", "expected_sequence", True),
        ("proposal", "quantity_contracts", True),
        ("proposal", "quantity_contracts", 2),
        ("economics", "account_currency", "EUR"),
        ("economics", "entry_fee_usd_micros_per_contract", True),
        ("economics", "exit_fee_usd_micros_per_contract", -1),
        ("limits", "cash_buffer_usd_micros", True),
        ("limits", "max_snapshot_age_ns", -1),
        ("limits", "max_cumulative_realization_loss_usd_micros", True),
        ("margin", "initial_usd_micros_per_contract", 79),
    ],
)
def test_exact_types_and_declared_units_are_revalidated(target, field, value):
    s, p, e, bounds = snapshot(), proposal(), declared(), limits()
    item = {"snapshot": s, "proposal": p, "economics": e, "limits": bounds, "margin": e.margin}
    poison(item[target], field, value)
    with pytest.raises(ValueError):
        assess(s, p, e, bounds)


@pytest.mark.parametrize("change", ["individual", "requirement", "current_loss", "entry_fee_loss"])
def test_individual_and_aggregate_overflow_is_refused(change):
    s, e, bounds = snapshot(), declared(), limits()
    if change == "individual":
        poison(s, "declared_realization_balance_usd_micros", MAX + 1)
    elif change == "requirement":
        e = declared(entry_fee_usd_micros_per_contract=MAX, margin=economics.DeclaredMargin(0, 0))
        bounds = limits(cash_buffer_usd_micros=1)
    elif change == "current_loss":
        s = snapshot(
            seed=economics.EconomicSeed(MAX, START),
            declared_realization_balance_usd_micros=-1,
        )
    else:
        s = snapshot(
            seed=economics.EconomicSeed(1, START),
            declared_realization_balance_usd_micros=-MAX + 1,
        )
        e = declared(entry_fee_usd_micros_per_contract=1)
    with pytest.raises(ValueError):
        assess(s, e=e, bounds=bounds)


def test_every_disposition_retains_exact_false_authority():
    cases = [
        (snapshot(), declared(), "declared_budget_available"),
        (
            snapshot(declared_realization_balance_usd_micros=134),
            declared(),
            "declared_budget_insufficient",
        ),
        (snapshot(pending_entry=True), declared(margin=None), "entry_blocked_by_liability"),
        (snapshot(), declared(margin=None), "budget_undetermined"),
    ]
    for s, e, disposition in cases:
        result = assess(s, e=e)
        assert result.disposition == disposition
        flags = dict(result.authority_flags)
        assert flags
        assert all(value is False for value in flags.values())
        for key in (
            "trading_enabled",
            "broker_execution_confirmed",
            "cash_balance_confirmed",
            "margin_requirement_confirmed",
            "risk_approved",
            "training_eligible",
            "strategy_scoring_allowed",
            "promotion_allowed",
            "independent_holdout",
            "source_files_authenticated",
            "snapshot_prefix_authenticated",
            "reservation_created",
        ):
            assert flags[key] is False


def test_assessment_is_pure_immutable_and_deterministic_without_source_or_market_access(
    monkeypatch,
):
    s, p, e, bounds = snapshot(), proposal(), declared(), limits()
    before = deepcopy((asdict(s), asdict(p), asdict(e), asdict(bounds)))

    def forbidden(*args, **kwargs):
        raise AssertionError("Pure budget core attempted filesystem, policy or tape access")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(Path, "open", forbidden)
        patch.setattr(sqlite3, "connect", forbidden)
        patch.setattr(economics.replay, "fingerprints", forbidden)
        patch.setattr(economics.replay, "build_plan", forbidden)
        patch.setattr(economics.replay, "_freeze", forbidden)
        patch.setattr(economics, "project", forbidden)
        patch.setattr(economics.ledger, "ScenarioLedger", forbidden)
        patch.setattr(economics.replay.rules, "rules", forbidden)
        patch.setattr(economics.replay.rules.Model, "predict", forbidden)
        patch.setattr(economics.replay.study.common, "hash_file", forbidden)
        first = assess(s, p, e, bounds)
        second = assess(s, p, e, bounds)
    assert first == second
    assert (asdict(s), asdict(p), asdict(e), asdict(bounds)) == before
    assert first.snapshot.pending_entry is False
    assert first.snapshot.sequence == s.sequence
    assert first.snapshot.tip_sha256 == s.tip_sha256
