"""Offline, non-executing research review with structured roles and hard vetoes.

This is an independently implemented architectural adaptation, not TradingAgents
code. A reviewer is advisory: it cannot create a signal, change sizing, or trade.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Literal, Protocol

from ai_trader.risk.engine import OrderIntent, PortfolioRiskState, RiskLimits, evaluate_order
from ai_trader.trading.decision_policy import Decision, DecisionPolicy, decide_position

Role = Literal["analyst", "critic"]


def _timestamp(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("Timestamps must be nonnegative integer milliseconds.")


@dataclass(frozen=True, slots=True)
class Evidence:
    """One caller-supplied numeric observation, including when it became available."""

    evidence_id: str
    symbol: str
    source_session: str
    metric: str
    value: Decimal
    event_time_ms: int
    available_time_ms: int

    def __post_init__(self) -> None:
        for value in (self.evidence_id, self.symbol, self.source_session, self.metric):
            if not isinstance(value, str) or not value.strip() or len(value) > 128:
                raise ValueError("Evidence identifiers must contain 1-128 characters.")
        if not isinstance(self.value, Decimal) or not self.value.is_finite():
            raise ValueError("Evidence values must be finite Decimals.")
        _timestamp(self.event_time_ms)
        _timestamp(self.available_time_ms)
        if self.available_time_ms < self.event_time_ms:
            raise ValueError("Evidence cannot become available before its event.")


@dataclass(frozen=True, slots=True)
class ResearchSnapshot:
    """A bounded, immutable input shared by every role."""

    symbol: str
    as_of_ms: int
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        _timestamp(self.as_of_ms)
        if self.symbol != "BTCUSDT":
            raise ValueError("This BTC-denominated research adapter supports BTCUSDT only.")
        if type(self.evidence) is not tuple or not 1 <= len(self.evidence) <= 32:
            raise ValueError("Supply an immutable tuple of 1-32 evidence items.")
        if not all(isinstance(item, Evidence) for item in self.evidence):
            raise ValueError("Snapshot entries must be Evidence items.")
        if len({item.evidence_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("Evidence IDs must be unique.")


@dataclass(frozen=True, slots=True)
class RoleReport:
    """A schema-checked opinion, not a calibrated probability or an order."""

    role: Role
    verdict: Literal["support", "veto"]
    evidence_ids: tuple[str, ...]
    rationale: str


class Reviewer(Protocol):
    """Extension point for a local model or deterministic offline baseline.

    Implementations must return only the documented JSON schema. The core has
    no network/model dependency. Supplying an arbitrary implementation is a
    caller trust boundary, not a process sandbox or an enforced timeout.
    """

    def review(
        self, role: Role, snapshot: ResearchSnapshot, prior: tuple[RoleReport, ...]
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class CouncilResult:
    """Research permission only; never pass this off as an executed order."""

    entry_allowed: bool
    reason: str
    reports: tuple[RoleReport, ...]
    as_of_ms: int
    input_fingerprint: str
    mode: str = "offline_research_only"


def parse_role_report(raw: str, role: Role, snapshot: ResearchSnapshot) -> RoleReport:
    """Reject prose fallback, extra fields, fabricated citations and oversized output."""
    if not isinstance(raw, str) or len(raw) > 2048:
        raise ValueError("Reviewer output must be a JSON string of at most 2048 characters.")

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON keys are forbidden.")
            result[key] = value
        return result

    payload = json.loads(raw, object_pairs_hook=unique_keys)
    if not isinstance(payload, dict) or set(payload) != {"verdict", "evidence_ids", "rationale"}:
        raise ValueError("Unexpected reviewer schema.")
    if payload["verdict"] not in ("support", "veto"):
        raise ValueError("Verdict must be support or veto.")
    rationale = payload["rationale"]
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 512:
        raise ValueError("Rationale must contain 1-512 characters.")
    ids = payload["evidence_ids"]
    if not isinstance(ids, list) or not 1 <= len(ids) <= 16:
        raise ValueError("Every opinion must cite 1-16 evidence IDs.")
    if not all(isinstance(item, str) for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("Citations must be unique string IDs.")
    if not set(ids) <= {item.evidence_id for item in snapshot.evidence}:
        raise ValueError("Unknown evidence citation.")
    return RoleReport(role, payload["verdict"], tuple(ids), rationale)


def review_spot_entry(
    signal: Decision,
    order: OrderIntent,
    state: PortfolioRiskState,
    limits: RiskLimits,
    snapshot: ResearchSnapshot,
    reviewer: Reviewer,
    *,
    maximum_evidence_age_ms: int = 300_000,
) -> CouncilResult:
    """Review an existing long-entry proposal; any failed check denies entry.

    A denied entry is NOT a FLAT/exit instruction. Exit handling stays outside
    this council. The paper broker must recheck cash, prices and risk at fill time.
    """
    _timestamp(maximum_evidence_age_ms)
    reports: list[RoleReport] = []
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "schema_version": 1,
                "signal": asdict(signal),
                "order": asdict(order),
                "state": asdict(state),
                "limits": asdict(limits),
                "snapshot": asdict(snapshot),
                "maximum_evidence_age_ms": maximum_evidence_age_ms,
            },
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    def result(allowed: bool, reason: str) -> CouncilResult:
        return CouncilResult(allowed, reason, tuple(reports), snapshot.as_of_ms, fingerprint)

    if signal.intent != "LONG":
        return result(False, "no_existing_long_signal")
    for item in snapshot.evidence:
        if item.symbol != snapshot.symbol:
            return result(False, "evidence_symbol_mismatch")
        if item.available_time_ms > snapshot.as_of_ms:
            return result(False, "future_evidence")
        if snapshot.as_of_ms - item.event_time_ms > maximum_evidence_age_ms:
            return result(False, "stale_evidence")

    # Pre-existing risk objects are not guaranteed to reject infinity. Fail
    # closed at this new boundary without altering the broker's existing API.
    numeric_values = (
        order.quantity_btc,
        order.price_usdt,
        state.position_btc,
        state.realized_pnl_today_usdt,
        state.equity_usdt,
        state.peak_equity_usdt,
        *asdict(limits).values(),
    )
    if any(not isinstance(value, Decimal) or not value.is_finite() for value in numeric_values):
        return result(False, "nonfinite_risk_input")
    if order.side != "BUY" or order.reduce_only or state.position_btc != 0:
        return result(False, "spot_flat_to_long_only")
    risk = evaluate_order(order, state, limits)
    if not risk.approved:
        return result(False, f"risk_veto:{risk.reason}")

    # Exactly two calls at most. No retries, debate loop, tools or free-text fallback.
    for role in ("analyst", "critic"):
        try:
            raw = reviewer.review(role, snapshot, tuple(reports))
            report = parse_role_report(raw, role, snapshot)
        except Exception:
            # Do not put arbitrary provider exceptions (possibly secrets) in artifacts.
            return result(False, f"invalid_or_failed_{role}_review")
        reports.append(report)
        if report.verdict == "veto":
            return result(False, f"{role}_veto")
    return result(True, "research_reviews_and_risk_passed")


class CostStressReviewer:
    """Deterministic reference roles, NOT an LLM or a learned trading strategy.

    Expects separately estimated baseline/stressed NET expectancy in bps. These
    are caller estimates, never label outcomes or softmax confidence converted
    to return. Positive inputs are not proof of positive true expectancy.
    """

    def review(self, role: Role, snapshot: ResearchSnapshot, prior: tuple[RoleReport, ...]) -> str:
        metric = "net_expectancy_bps" if role == "analyst" else "stressed_net_expectancy_bps"
        matching = [item for item in snapshot.evidence if item.metric == metric]
        if len(matching) != 1:
            raise ValueError("Exactly one expectancy estimate per role is required.")
        item = matching[0]
        return json.dumps(
            {
                "verdict": "support" if item.value > 0 else "veto",
                "evidence_ids": [item.evidence_id],
                "rationale": f"Supplied {metric} is {item.value}; require strictly positive.",
            }
        )


def main() -> None:
    """Run a clearly synthetic, network-free demonstration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", required=True)
    parser.parse_args()
    snapshot = ResearchSnapshot(
        "BTCUSDT",
        1000,
        (
            Evidence(
                "baseline", "BTCUSDT", "synthetic", "net_expectancy_bps", Decimal("12"), 900, 950
            ),
            Evidence(
                "stress",
                "BTCUSDT",
                "synthetic",
                "stressed_net_expectancy_bps",
                Decimal("-2"),
                900,
                950,
            ),
        ),
    )
    signal = decide_position([0.1, 0.1, 0.8], DecisionPolicy(allow_short=False))
    state = PortfolioRiskState(Decimal("0"), Decimal("0"), Decimal("10000"), Decimal("10000"))
    limits = RiskLimits(
        *(Decimal(value) for value in ("0.1", "0.02", "2000", "5000", "100", "150"))
    )
    decision = review_spot_entry(
        signal,
        OrderIntent("BUY", Decimal("0.01"), Decimal("80000")),
        state,
        limits,
        snapshot,
        CostStressReviewer(),
    )
    print(json.dumps({"synthetic_demo": True, **asdict(decision)}, indent=2))


if __name__ == "__main__":
    main()
