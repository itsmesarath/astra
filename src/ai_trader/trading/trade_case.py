"""Immutable research/paper case contracts; no order or model capabilities.

Version 1 seals a minimal thesis and risk assessment, then binds a later review.
It is not a durable journal, a complete fill ledger or an execution authorization.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Literal


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise ValueError("Text must contain 1-2048 characters.")


def _time(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("Time must be nonnegative integer nanoseconds.")


def _number(value: Decimal, *, positive: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or (positive and value <= 0):
        raise ValueError("Expected a finite Decimal with a valid sign.")


def _digest(value: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Expected lowercase SHA-256.")


@dataclass(frozen=True, slots=True)
class CaseEvidence:
    evidence_id: str
    available_at_ns: int
    observation_sha256: str

    def __post_init__(self):
        _text(self.evidence_id)
        _time(self.available_at_ns)
        _digest(self.observation_sha256)


@dataclass(frozen=True, slots=True)
class EntryPlan:
    """Long-entry proposal only; no-action uses None, not a zero target."""

    quantity_btc: Decimal
    reference_price_usdt: Decimal
    stop_price_usdt: Decimal
    take_profit_price_usdt: Decimal
    maximum_hold_ns: int
    expires_at_ns: int

    def __post_init__(self):
        for value in (
            self.quantity_btc,
            self.reference_price_usdt,
            self.stop_price_usdt,
            self.take_profit_price_usdt,
        ):
            _number(value, positive=True)
        if not self.stop_price_usdt < self.reference_price_usdt < self.take_profit_price_usdt:
            raise ValueError("Long plan requires stop < reference < take profit.")
        _time(self.maximum_hold_ns)
        _time(self.expires_at_ns)
        if self.maximum_hold_ns == 0:
            raise ValueError("Holding horizon must be positive.")


@dataclass(frozen=True, slots=True)
class PreTradeCase:
    case_id: str
    source_session: str
    decision_at_ns: int
    policy_version: str
    feature_version: str
    market_state_sha256: str
    hypothesis: str
    expected_behavior: str
    invalidation: str
    evidence: tuple[CaseEvidence, ...]
    action: Literal["NO_ACTION", "ENTER_LONG"]
    plan: EntryPlan | None
    risk_verdict: Literal["NOT_EVALUATED", "REJECTED", "APPROVED"]
    risk_reason: str
    risk_config_sha256: str
    approved_quantity_btc: Decimal | None = None
    mode: Literal["research_only", "paper"] = "research_only"
    symbol: str = "BTCUSDT"
    schema_version: int = 1

    def __post_init__(self):
        for value in (
            self.case_id,
            self.source_session,
            self.policy_version,
            self.feature_version,
            self.hypothesis,
            self.expected_behavior,
            self.invalidation,
            self.risk_reason,
        ):
            _text(value)
        _time(self.decision_at_ns)
        _digest(self.market_state_sha256)
        _digest(self.risk_config_sha256)
        if self.mode not in ("research_only", "paper") or self.symbol != "BTCUSDT":
            raise ValueError("Only BTCUSDT research/paper cases are supported.")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported case schema.")
        if type(self.evidence) is not tuple or not 1 <= len(self.evidence) <= 32:
            raise ValueError("Evidence must be an immutable tuple of 1-32 records.")
        if any(type(item) is not CaseEvidence for item in self.evidence):
            raise ValueError("Invalid evidence record.")
        if len({item.evidence_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("Duplicate evidence identifier.")
        if any(item.available_at_ns > self.decision_at_ns for item in self.evidence):
            raise ValueError("Future evidence cannot enter a pre-trade case.")
        if self.action not in ("NO_ACTION", "ENTER_LONG"):
            raise ValueError("Unsupported action.")
        if self.risk_verdict not in ("NOT_EVALUATED", "REJECTED", "APPROVED"):
            raise ValueError("Unsupported risk verdict.")
        if self.action == "NO_ACTION":
            if self.plan is not None or self.risk_verdict == "APPROVED":
                raise ValueError("No-action is not an approved order or liquidation.")
        elif type(self.plan) is not EntryPlan or self.plan.expires_at_ns <= self.decision_at_ns:
            raise ValueError("Entry requires a valid, unexpired plan.")
        if self.risk_verdict == "APPROVED":
            _number(self.approved_quantity_btc, positive=True)
            if self.approved_quantity_btc > self.plan.quantity_btc:
                raise ValueError("Approved quantity exceeds proposal.")
        elif self.approved_quantity_btc is not None:
            raise ValueError("Only an approved assessment may carry approved quantity.")

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str, sort_keys=True, allow_nan=False)

    @property
    def sha256(self) -> str:
        """Content fingerprint, not a signature or proof of pre-execution persistence."""
        return hashlib.sha256(self.to_json().encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class PostTradeReview:
    """Resolved paper trade outcome, bound to its unchanged original case."""

    case: PreTradeCase
    trade_id: str
    outcome_resolved_at_ns: int
    reviewed_at_ns: int
    net_pnl_usdt: Decimal
    decision_quality: Literal["GOOD", "MIXED", "BAD", "UNKNOWN"]
    summary: str
    reviewer_version: str
    outcome_evidence_sha256: str
    lesson_status: Literal["ANECDOTE"] = "ANECDOTE"

    def __post_init__(self):
        if type(self.case) is not PreTradeCase or self.case.action != "ENTER_LONG":
            raise ValueError("A filled-trade review requires an entry case.")
        if self.case.risk_verdict != "APPROVED":
            raise ValueError("Rejected/unassessed cases require a separate incident review.")
        for value in (self.trade_id, self.summary, self.reviewer_version):
            _text(value)
        _digest(self.outcome_evidence_sha256)
        _time(self.outcome_resolved_at_ns)
        _time(self.reviewed_at_ns)
        if not self.case.decision_at_ns <= self.outcome_resolved_at_ns <= self.reviewed_at_ns:
            raise ValueError("Review times must follow the decision and resolved outcome.")
        _number(self.net_pnl_usdt)
        if self.decision_quality not in ("GOOD", "MIXED", "BAD", "UNKNOWN"):
            raise ValueError("Unsupported decision-quality label.")
        if self.lesson_status != "ANECDOTE":
            raise ValueError("One review cannot validate a pattern or promote a policy.")

    @property
    def outcome(self) -> str:
        return "WIN" if self.net_pnl_usdt > 0 else "LOSS" if self.net_pnl_usdt < 0 else "BREAKEVEN"
