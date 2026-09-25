"""Immutable typed records, causal evidence and outcome/quality independence."""

import json
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from ai_trader.trading.trade_case import CaseEvidence, EntryPlan, PostTradeReview, PreTradeCase

D = Decimal


def case():
    return PreTradeCase(
        "case-1",
        "session-1",
        1000,
        "rule-v1",
        "features-v1",
        "a" * 64,
        "Bid replenishment hypothesis",
        "Upward continuation",
        "Bid evidence disappears",
        (CaseEvidence("obs-1", 900, "b" * 64),),
        "ENTER_LONG",
        EntryPlan(D("0.001"), D("60000"), D("59000"), D("61000"), 5000, 1500),
        "APPROVED",
        "limits_passed",
        "c" * 64,
        D("0.001"),
    )


def review(**kwargs):
    values = dict(
        case=case(),
        trade_id="trade-1",
        outcome_resolved_at_ns=2000,
        reviewed_at_ns=3000,
        net_pnl_usdt=D("-1"),
        decision_quality="GOOD",
        summary="Compliant loss",
        reviewer_version="rubric-v1",
        outcome_evidence_sha256="d" * 64,
    )
    return PostTradeReview(**(values | kwargs))


def test_deep_immutability_and_stable_fingerprint():
    value = case()
    for obj, key, change in [
        (value, "hypothesis", "new"),
        (value.plan, "quantity_btc", D("9")),
        (value.evidence[0], "available_at_ns", 9999),
    ]:
        with pytest.raises(FrozenInstanceError):
            setattr(obj, key, change)
    assert value.sha256 == case().sha256
    assert value.sha256 != replace(value, hypothesis="Different thesis").sha256
    assert json.loads(value.to_json())["plan"]["quantity_btc"] == "0.001"


@pytest.mark.parametrize(
    "changes",
    [
        {"evidence": []},
        {"evidence": ()},
        {"evidence": ({},)},
        {"evidence": (CaseEvidence("future", 1001, "b" * 64),)},
        {"evidence": (CaseEvidence("same", 900, "b" * 64),) * 2},
        {"mode": "spot_live"},
        {"symbol": "ETHUSDT"},
        {"schema_version": True},
        {"decision_at_ns": True},
        {"market_state_sha256": "bad"},
        {"policy_version": ""},
        {"action": "CLOSE"},
        {"action": "NO_ACTION"},
        {"plan": None},
        {"plan": {}},
        {"risk_verdict": "unknown"},
        {"risk_verdict": "REJECTED"},
        {"approved_quantity_btc": D("0.002")},
        {"approved_quantity_btc": None},
        {"approved_quantity_btc": D("NaN")},
    ],
)
def test_invalid_pretrade_contract_rejected(changes):
    with pytest.raises(ValueError):
        replace(case(), **changes)


def test_expired_plan_and_mutable_no_action_are_rejected():
    value = case()
    with pytest.raises(ValueError, match="unexpired"):
        replace(value, plan=replace(value.plan, expires_at_ns=1000))
    no_action = replace(
        value,
        action="NO_ACTION",
        plan=None,
        risk_verdict="NOT_EVALUATED",
        approved_quantity_btc=None,
    )
    assert no_action.plan is None
    assert no_action.approved_quantity_btc is None


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity_btc": D("Infinity")},
        {"stop_price_usdt": D("NaN")},
        {"take_profit_price_usdt": D("59000")},
        {"quantity_btc": 0.1},
        {"maximum_hold_ns": 0},
        {"maximum_hold_ns": True},
        {"expires_at_ns": -1},
    ],
)
def test_invalid_entry_plan_rejected(changes):
    with pytest.raises(ValueError):
        replace(case().plan, **changes)


def test_outcome_is_not_decision_quality_and_review_cannot_rewrite_case():
    loss = review()
    win = review(net_pnl_usdt=D("1"), decision_quality="BAD", summary="Rule violation win")
    assert (loss.outcome, loss.decision_quality) == ("LOSS", "GOOD")
    assert (win.outcome, win.decision_quality) == ("WIN", "BAD")
    assert review(net_pnl_usdt=D("0")).outcome == "BREAKEVEN"
    assert loss.case.sha256 == win.case.sha256
    with pytest.raises(FrozenInstanceError):
        loss.case.hypothesis = "hindsight"


@pytest.mark.parametrize(
    "changes",
    [
        {"outcome_resolved_at_ns": 999},
        {"reviewed_at_ns": 1001},
        {"net_pnl_usdt": D("NaN")},
        {"decision_quality": "WIN"},
        {"lesson_status": "VALIDATED"},
        {"case": {}},
        {"outcome_evidence_sha256": "bad"},
    ],
)
def test_invalid_review_rejected(changes):
    with pytest.raises(ValueError):
        review(**changes)


def test_rejected_case_requires_separate_incident_not_filled_trade_review():
    rejected = replace(case(), risk_verdict="REJECTED", approved_quantity_btc=None)
    with pytest.raises(ValueError, match="incident"):
        review(case=rejected)
