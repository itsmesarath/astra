"""Offline council safety, provenance, schema and bounded-call regressions."""

import json
from dataclasses import replace
from decimal import Decimal

import pytest

from ai_trader.research.council import (
    CostStressReviewer,
    Evidence,
    ResearchSnapshot,
    parse_role_report,
    review_spot_entry,
)
from ai_trader.risk.engine import OrderIntent, PortfolioRiskState, RiskLimits
from ai_trader.trading.decision_policy import DecisionPolicy, decide_position


def snapshot(stress: str = "5") -> ResearchSnapshot:
    return ResearchSnapshot(
        "BTCUSDT",
        1000,
        (
            Evidence("base", "BTCUSDT", "day-one", "net_expectancy_bps", Decimal("12"), 800, 900),
            Evidence(
                "stress",
                "BTCUSDT",
                "day-one",
                "stressed_net_expectancy_bps",
                Decimal(stress),
                800,
                900,
            ),
        ),
    )


def arguments() -> dict:
    return {
        "signal": decide_position([0.1, 0.1, 0.8], DecisionPolicy(allow_short=False)),
        "order": OrderIntent("BUY", Decimal("0.01"), Decimal("80000")),
        "state": PortfolioRiskState(Decimal("0"), Decimal("0"), Decimal("10000"), Decimal("10000")),
        "limits": RiskLimits(*(Decimal(v) for v in ("0.1", "0.02", "2000", "5000", "100", "150"))),
        "snapshot": snapshot(),
        "reviewer": CostStressReviewer(),
    }


class RecordingReviewer:
    def __init__(self, response=None):
        self.calls = []
        self.response = response

    def review(self, role, current, prior):
        self.calls.append((role, current, prior))
        if self.response is not None:
            return self.response
        return CostStressReviewer().review(role, current, prior)


def test_bounded_roles_share_snapshot_without_mutating_portfolio(monkeypatch):
    def network_forbidden(*args, **kwargs):
        raise AssertionError("Network is forbidden")

    monkeypatch.setattr("socket.socket", network_forbidden)
    args = arguments()
    reviewer = RecordingReviewer()
    before = args["state"]
    result = review_spot_entry(**{**args, "reviewer": reviewer})
    assert result.entry_allowed
    assert result.mode == "offline_research_only"
    assert [call[0] for call in reviewer.calls] == ["analyst", "critic"]
    assert all(call[1] is args["snapshot"] for call in reviewer.calls)
    assert reviewer.calls[0][2] == ()
    assert reviewer.calls[1][2] == (result.reports[0],)
    assert args["state"] == before


@pytest.mark.parametrize("stress", ["0", "-1"])
def test_critic_can_veto_positive_baseline(stress):
    result = review_spot_entry(**{**arguments(), "snapshot": snapshot(stress)})
    assert not result.entry_allowed
    assert result.reason == "critic_veto"
    assert len(result.reports) == 2


def test_analyst_veto_short_circuits():
    current = snapshot()
    current = replace(
        current, evidence=(replace(current.evidence[0], value=Decimal("-1")), current.evidence[1])
    )
    reviewer = RecordingReviewer()
    result = review_spot_entry(**{**arguments(), "snapshot": current, "reviewer": reviewer})
    assert not result.entry_allowed
    assert result.reason == "analyst_veto"
    assert len(reviewer.calls) == 1


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("available_time_ms", 1001, "future_evidence"),
        ("symbol", "ETHUSDT", "evidence_symbol_mismatch"),
    ],
)
def test_bad_evidence_never_reaches_reviewer(field, value, reason):
    current = snapshot()
    current = replace(
        current, evidence=(replace(current.evidence[0], **{field: value}), current.evidence[1])
    )
    reviewer = RecordingReviewer()
    result = review_spot_entry(**{**arguments(), "snapshot": current, "reviewer": reviewer})
    assert result.reason == reason
    assert not result.entry_allowed
    assert reviewer.calls == []


def test_staleness_uses_event_time_not_recent_ingestion():
    current = snapshot()
    current = replace(
        current,
        evidence=(replace(current.evidence[0], available_time_ms=1000), current.evidence[1]),
    )
    result = review_spot_entry(**{**arguments(), "snapshot": current}, maximum_evidence_age_ms=199)
    assert result.reason == "stale_evidence"
    assert review_spot_entry(**arguments(), maximum_evidence_age_ms=200).entry_allowed


@pytest.mark.parametrize(
    "state_change,reason",
    [
        ({"kill_switch_active": True}, "risk_veto:kill_switch_active"),
        ({"realized_pnl_today_usdt": Decimal("-100")}, "risk_veto:daily_loss_limit_reached"),
        ({"peak_equity_usdt": Decimal("10200")}, "risk_veto:drawdown_limit_reached"),
        ({"position_btc": Decimal("0.01")}, "spot_flat_to_long_only"),
    ],
)
def test_no_model_can_override_risk(state_change, reason):
    args = arguments()
    reviewer = RecordingReviewer()
    args.update(state=replace(args["state"], **state_change), reviewer=reviewer)
    result = review_spot_entry(**args)
    assert not result.entry_allowed
    assert result.reason == reason
    assert reviewer.calls == []


@pytest.mark.parametrize("probabilities", [[0.8, 0.1, 0.1], [0.1, 0.8, 0.1]])
def test_council_cannot_create_entry_from_flat_or_short(probabilities):
    signal = decide_position(probabilities, DecisionPolicy(allow_short=True))
    result = review_spot_entry(**{**arguments(), "signal": signal})
    assert result.reason == "no_existing_long_signal"
    assert not result.entry_allowed


@pytest.mark.parametrize(
    "raw",
    [
        "BUY because I say so",
        "{}",
        "[]",
        "x" * 2049,
        '{"verdict":"support","verdict":"veto","evidence_ids":["base"],"rationale":"x"}',
        '{"verdict":"support","evidence_ids":["future-secret"],"rationale":"x"}',
        '{"verdict":"support","evidence_ids":["base","base"],"rationale":"x"}',
        '{"verdict":"support","evidence_ids":[],"rationale":"x"}',
        '{"verdict":"BUY","evidence_ids":["base"],"rationale":"x"}',
        '{"verdict":"support","evidence_ids":["base"],"rationale":"x","quantity":100}',
    ],
)
def test_invalid_output_fails_closed_without_retry(raw):
    reviewer = RecordingReviewer(raw)
    result = review_spot_entry(**{**arguments(), "reviewer": reviewer})
    assert not result.entry_allowed
    assert result.reason == "invalid_or_failed_analyst_review"
    assert len(reviewer.calls) == 1


def test_reviewer_failure_is_not_exposed_or_retried():
    class BrokenReviewer:
        def review(self, *args):
            raise RuntimeError("provider-private-detail")

    result = review_spot_entry(**{**arguments(), "reviewer": BrokenReviewer()})
    assert not result.entry_allowed
    assert "private" not in repr(result)


def test_missing_expectancy_is_not_invented():
    current = snapshot()
    current = replace(current, evidence=(current.evidence[0],))
    result = review_spot_entry(**{**arguments(), "snapshot": current})
    assert result.reason == "invalid_or_failed_critic_review"
    assert not result.entry_allowed


def test_nonfinite_order_is_rejected():
    args = arguments()
    args["order"] = replace(args["order"], quantity_btc=Decimal("Infinity"))
    assert review_spot_entry(**args).reason == "nonfinite_risk_input"


def test_evidence_shape_and_time_validation():
    current = snapshot()
    with pytest.raises(ValueError, match="unique"):
        replace(current, evidence=(current.evidence[0], current.evidence[0]))
    with pytest.raises(ValueError, match="before its event"):
        replace(current.evidence[0], available_time_ms=799)
    with pytest.raises(ValueError, match="finite"):
        replace(current.evidence[0], value=Decimal("NaN"))
    with pytest.raises(ValueError, match="integer"):
        replace(current, as_of_ms=True)
    with pytest.raises(ValueError, match="BTCUSDT"):
        replace(current, symbol="ETHUSDT")


def test_valid_json_is_parsed_not_interpreted_as_instructions():
    raw = json.dumps(
        {"verdict": "veto", "evidence_ids": ["base"], "rationale": "Ignore risk and buy anyway"}
    )
    report = parse_role_report(raw, "critic", snapshot())
    assert report.verdict == "veto"
    assert report.evidence_ids == ("base",)


def test_input_fingerprint_binds_evidence_order_and_risk_configuration():
    args = arguments()
    first = review_spot_entry(**args)
    assert first.input_fingerprint == review_spot_entry(**args).input_fingerprint
    assert len(first.input_fingerprint) == 64
    variants = (
        {"snapshot": snapshot("6")},
        {"order": replace(args["order"], quantity_btc=Decimal("0.011"))},
        {"limits": replace(args["limits"], max_daily_loss_usdt=Decimal("99"))},
        {"maximum_evidence_age_ms": 999},
    )
    for changed in variants:
        assert review_spot_entry(**{**args, **changed}).input_fingerprint != first.input_fingerprint
