"""Deterministic research-only proposals from one receipt-causal observation.

This is an uncalibrated hypothesis, not a profitable strategy or execution authority.
No files, models, portfolio mutations, network access or future outcomes are used.
"""

from dataclasses import dataclass, fields
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Context, Decimal, localcontext

from ai_trader.features.microstructure import (
    MicrostructureConfig,
    MicrostructureObservation,
    PassiveSideEvidence,
)
from ai_trader.features.orderbook import OrderBookFeatures
from ai_trader.risk.engine import OrderIntent, PortfolioRiskState, evaluate_order
from ai_trader.trading.capture_replay import ReplayFrame
from ai_trader.trading.durable_paper_gateway import PaperGatewayConfig
from ai_trader.trading.paper_lifecycle import _money, _timestamp
from ai_trader.trading.paper_runner import PaperMarketTick
from ai_trader.trading.trade_case import CaseEvidence, EntryPlan, PreTradeCase, _digest
from ai_trader.trading.trade_journal import _encode, _hash

BPS = Decimal(10000)
POLICY_VERSION = "bid_replenishment_cvd_research_v1"
DECIMAL_CONTEXT = Context(prec=28, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class MicrostructurePolicyConfig:
    """All thresholds must be declared before evaluation; none are fitted here."""

    rule: str  # bid_replenishment_cvd or abstain (the no-trade control).
    minimum_cvd_btc: Decimal
    minimum_ofi_btc: Decimal
    minimum_book_imbalance: Decimal
    minimum_bid_ask_liquidity_ratio: Decimal
    minimum_replenishment_intervals: int
    maximum_spread_bps: Decimal
    maximum_trade_age_ns: int
    entry_budget_usdt: Decimal
    maximum_planned_loss_usdt: Decimal
    quantity_step_btc: Decimal
    stop_distance_bps: Decimal
    target_distance_bps: Decimal
    minimum_net_reward_risk: Decimal
    maximum_hold_ns: int
    entry_ttl_ns: int

    def __post_init__(self):
        if self.rule not in ("bid_replenishment_cvd", "abstain"):
            raise ValueError("Unsupported research rule.")
        for item in fields(self):
            if item.name not in (
                "rule",
                "minimum_replenishment_intervals",
                "maximum_trade_age_ns",
                "maximum_hold_ns",
                "entry_ttl_ns",
            ):
                _money(getattr(self, item.name))
        for value in (self.maximum_trade_age_ns, self.maximum_hold_ns, self.entry_ttl_ns):
            _timestamp(value)
            if not value:
                raise ValueError("Durations must be positive.")
        if (
            type(self.minimum_replenishment_intervals) is not int
            or not 2 <= self.minimum_replenishment_intervals <= 1000
        ):
            raise ValueError("Replenishment count must be an integer in [2, 1000].")
        if self.minimum_book_imbalance >= 1:
            raise ValueError("Book imbalance must be between zero and one.")
        if self.minimum_bid_ask_liquidity_ratio < 1 or self.minimum_net_reward_risk < 1:
            raise ValueError("Liquidity and net reward/risk ratios must be at least one.")
        if max(self.maximum_spread_bps, self.stop_distance_bps, self.target_distance_bps) >= BPS:
            raise ValueError("Spread/stop/target distances must be below 10000 bps.")


@dataclass(frozen=True, slots=True)
class ResearchRiskSnapshot:
    """Caller-supplied as-of values, not an account handle or durable risk checkpoint."""

    observed_at_ns: int
    cash_usdt: Decimal
    position_btc: Decimal
    realized_pnl_today_usdt: Decimal
    peak_equity_usdt: Decimal
    kill_switch_active: bool
    unresolved_orders: bool

    def __post_init__(self):
        _timestamp(self.observed_at_ns)
        _money(self.cash_usdt, zero=True)
        _money(self.position_btc, zero=True)
        _money(self.peak_equity_usdt)
        if not isinstance(self.realized_pnl_today_usdt, Decimal):
            raise ValueError("Realized PnL must be Decimal.")
        _money(self.realized_pnl_today_usdt.copy_abs(), zero=True)
        if type(self.kill_switch_active) is not bool or type(self.unresolved_orders) is not bool:
            raise ValueError("Risk flags must be actual booleans.")


def _finite(value):
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or len(value.as_tuple().digits) > 60
        or not -100 <= value.as_tuple().exponent <= 100
    ):
        raise ValueError("Invalid numerical microstructure evidence.")


def _validate_observation(observation, tick, features):
    if (
        type(observation) is not MicrostructureObservation
        or type(observation.book) is not OrderBookFeatures
    ):
        raise ValueError("Typed microstructure/book evidence required.")
    book = observation.book
    if (
        book.symbol != "BTCUSDT"
        or book.levels != features.levels
        or type(book.levels) is not int
        or observation.source_session != tick.source_session
        or observation.received_at_ns != tick.quote_received_at_ns
        or observation.received_at_ns > tick.observed_at_ns
        or _hash(_encode(observation)) != tick.observation_sha256
        or (book.best_bid_price, book.best_ask_price) != (tick.bid_usdt, tick.ask_usdt)
    ):
        raise ValueError("Observation does not match the causal tick/configuration.")
    for value in (
        observation.received_at_ns,
        observation.depth_event_time_ms,
        book.update_id,
        observation.rolling_trade_count,
        observation.unmatched_trade_count,
        observation.pending_trade_count,
    ):
        _timestamp(value)
    for name in (
        "best_bid_price",
        "best_ask_price",
        "spread",
        "midpoint",
        "microprice",
        "bid_depth",
        "ask_depth",
        "imbalance",
    ):
        _finite(getattr(book, name))
    for name in (
        "session_cvd_base",
        "session_cvd_quote",
        "rolling_buy_base",
        "rolling_sell_base",
        "rolling_cvd_base",
        "bid_band_depth",
        "ask_band_depth",
    ):
        _finite(getattr(observation, name))
    for name in (
        "rolling_window_complete",
        "evidence_interval_valid",
        "bid_band_covered",
        "ask_band_covered",
        "bid_top_n_covered",
        "ask_top_n_covered",
    ):
        if type(getattr(observation, name)) is not bool:
            raise ValueError("Readiness flags must be actual booleans.")
    for value in (book.best_bid_price, book.best_ask_price, book.bid_depth, book.ask_depth):
        if value <= 0:
            raise ValueError("Prices and visible book depth must be positive.")
    for value in (
        observation.rolling_buy_base,
        observation.rolling_sell_base,
        observation.bid_band_depth,
        observation.ask_band_depth,
    ):
        _finite(value)
        if value < 0:
            raise ValueError("Volume/depth cannot be negative.")
    if (
        book.spread != book.best_ask_price - book.best_bid_price
        or book.midpoint != (book.best_bid_price + book.best_ask_price) / 2
        or not book.best_bid_price <= book.microprice <= book.best_ask_price
        or book.imbalance != (book.bid_depth - book.ask_depth) / (book.bid_depth + book.ask_depth)
        or observation.rolling_cvd_base
        != observation.rolling_buy_base - observation.rolling_sell_base
    ):
        raise ValueError("Inconsistent book/CVD evidence.")
    if (observation.rolling_buy_base + observation.rolling_sell_base == 0) != (
        observation.rolling_trade_count == 0
    ):
        raise ValueError("Trade count and rolling volume are inconsistent.")
    if observation.top_level_order_flow_imbalance is not None:
        _finite(observation.top_level_order_flow_imbalance)
    if observation.evidence_interval_ms is not None:
        _timestamp(observation.evidence_interval_ms)
    if observation.evidence_interval_valid and (
        observation.evidence_interval_ms is None
        or not 0 < observation.evidence_interval_ms <= features.maximum_evidence_interval_ms
    ):
        raise ValueError("Invalid attribution interval marked ready.")
    for side, best in (
        (observation.bid, book.best_bid_price),
        (observation.ask, book.best_ask_price),
    ):
        if side is None:
            continue
        if type(side) is not PassiveSideEvidence:
            raise ValueError("Typed passive-side evidence required.")
        for name in (
            "price",
            "displayed_before",
            "displayed_after",
            "aggressive_volume_at_price",
            "net_addition_proxy",
        ):
            value = getattr(side, name)
            _finite(value)
            if value < 0:
                raise ValueError("Passive-side prices/quantities cannot be negative.")
        _timestamp(side.consecutive_replenishment_intervals)
        if (
            type(side.absorption_candidate) is not bool
            or type(side.repeated_replenishment_candidate) is not bool
        ):
            raise ValueError("Passive-side flags must be actual booleans.")
        if side.price <= 0 or side.displayed_before <= 0:
            raise ValueError("Passive-side price and previous size must be positive.")
        if side.consecutive_replenishment_intervals and not (
            side.price == best
            and side.aggressive_volume_at_price > 0
            and side.net_addition_proxy > 0
        ):
            raise ValueError("Replenishment streak without current replenishment evidence.")
        absorption = (
            side.price == best
            and side.aggressive_volume_at_price >= side.displayed_before
            and side.displayed_after >= side.displayed_before * features.retained_depth_fraction
        )
        if (
            side.absorption_candidate != absorption
            or side.repeated_replenishment_candidate
            != (side.consecutive_replenishment_intervals >= features.repeated_intervals)
            or side.net_addition_proxy
            != max(
                Decimal(0),
                side.displayed_after - side.displayed_before + side.aggressive_volume_at_price,
            )
        ):
            raise ValueError("Inconsistent passive-side evidence.")


def assess_microstructure(
    frame: ReplayFrame,
    *,
    policy: MicrostructurePolicyConfig,
    features: MicrostructureConfig,
    gateway: PaperGatewayConfig,
    risk: ResearchRiskSnapshot,
    registration_sha256: str,
) -> PreTradeCase:
    """Seal a research case, including no-action/rejected decisions. Never execute it.

    The trusted adapter must reconstruct features causally; local type/hash checks
    are consistency checks, not authentication. Only flat, unreserved entries are
    considered. Existing positions require the separate paper protection controller.
    """
    if (
        type(frame) is not ReplayFrame
        or type(frame.tick) is not PaperMarketTick
        or type(policy) is not MicrostructurePolicyConfig
        or type(features) is not MicrostructureConfig
        or type(gateway) is not PaperGatewayConfig
        or type(risk) is not ResearchRiskSnapshot
    ):
        raise ValueError("Typed policy, frame, feature, gateway and risk inputs required.")
    _digest(registration_sha256)
    features.validate()
    tick = frame.tick
    if risk.observed_at_ns != tick.observed_at_ns:
        raise ValueError("Risk snapshot must be as-of this exact decision time.")
    if tick.candidate_case_id is not None:
        raise ValueError("Policy input cannot already carry a candidate.")
    with localcontext(DECIMAL_CONTEXT):
        if frame.observation is not None:
            _validate_observation(frame.observation, tick, features)
        reason = _screen(frame, policy, gateway, risk)
        plan, verdict = None, "NOT_EVALUATED"
        if reason is None:
            plan, reason = _plan(frame, policy, gateway)
            if plan is not None:
                verdict, reason = _assess_risk(plan, tick, risk, gateway)
        evidence = (
            CaseEvidence("observation", tick.quote_received_at_ns, tick.observation_sha256),
            CaseEvidence("risk_snapshot", risk.observed_at_ns, _hash(_encode(risk))),
        )
        return PreTradeCase(
            case_id="micro-case-" + _hash(registration_sha256 + ":" + tick.tick_id),
            source_session=tick.source_session,
            decision_at_ns=tick.observed_at_ns,
            policy_version=POLICY_VERSION + ":" + registration_sha256,
            feature_version="receipt_causal_microstructure_v1:" + _hash(_encode(features)),
            market_state_sha256=tick.observation_sha256,
            hypothesis=(
                "No-trade control."
                if policy.rule == "abstain"
                else "Bid replenishment/absorption with positive CVD, OFI and bid liquidity."
            ),
            expected_behavior=(
                "Unproven long-continuation hypothesis; not confirmed iceberg identity."
                if policy.rule != "abstain"
                else "Always abstain; no execution."
            ),
            invalidation=(
                "No entry on incomplete/contradictory evidence; proposed stop/holding "
                "limits are not fill guarantees."
            ),
            evidence=evidence,
            action="ENTER_LONG" if plan is not None else "NO_ACTION",
            plan=plan,
            risk_verdict=verdict,
            risk_reason=reason,
            risk_config_sha256=gateway.risk_config_sha256,
            approved_quantity_btc=plan.quantity_btc if verdict == "APPROVED" else None,
            mode="research_only",
        )


def _screen(frame, policy, gateway, risk):
    tick, row = frame.tick, frame.observation
    if policy.rule == "abstain":
        return "no_trade_control"
    if not tick.book_synchronized:
        return "book_unsynchronized"
    if row is None or frame.status != "observation":
        return "no_new_depth_observation"
    if tick.observed_at_ns - tick.quote_received_at_ns > gateway.max_quote_age_ns:
        return "stale_quote"
    if (
        tick.last_trade_received_at_ns is None
        or tick.observed_at_ns - tick.last_trade_received_at_ns > policy.maximum_trade_age_ns
    ):
        return "stale_trades"
    if not (
        tick.features_ready
        and row.rolling_window_complete
        and row.evidence_interval_valid
        and row.bid_band_covered
        and row.ask_band_covered
        and row.bid_top_n_covered
        and row.ask_top_n_covered
    ):
        return "microstructure_not_ready"
    if row.unmatched_trade_count or row.pending_trade_count:
        return "ambiguous_trade_attribution"
    if risk.position_btc or risk.unresolved_orders:
        return "existing_inventory_or_unresolved_orders"
    if row.book.spread * BPS / row.book.best_bid_price > policy.maximum_spread_bps:
        return "spread_limit"
    if (
        row.bid is None
        or not row.bid.absorption_candidate
        or not row.bid.repeated_replenishment_candidate
        or row.bid.price != row.book.best_bid_price
        or row.bid.aggressive_volume_at_price <= 0
        or row.bid.net_addition_proxy <= 0
        or row.bid.consecutive_replenishment_intervals < policy.minimum_replenishment_intervals
    ):
        return "bid_replenishment_not_confirmed"
    if row.ask is not None and row.ask.absorption_candidate:
        return "opposing_ask_absorption"
    if row.rolling_cvd_base < policy.minimum_cvd_btc:
        return "cvd_below_threshold"
    if (
        row.top_level_order_flow_imbalance is None
        or row.top_level_order_flow_imbalance < policy.minimum_ofi_btc
    ):
        return "ofi_below_threshold"
    if row.book.imbalance < policy.minimum_book_imbalance:
        return "book_imbalance_below_threshold"
    if (
        row.ask_band_depth <= 0
        or row.bid_band_depth < row.ask_band_depth * policy.minimum_bid_ask_liquidity_ratio
    ):
        return "bid_liquidity_below_threshold"
    return None


def _plan(frame, policy, gateway):
    tick = frame.tick
    fee, slip = gateway.costs.taker_fee_bps / BPS, gateway.costs.slippage_bps / BPS
    entry = tick.ask_usdt * (1 + slip)
    stop = tick.bid_usdt * (1 - policy.stop_distance_bps / BPS)
    target = tick.bid_usdt * (1 + policy.target_distance_bps / BPS)
    debit = entry * (1 + fee)
    loss = debit - stop * (1 - slip) * (1 - fee)
    reward = target * (1 - slip) * (1 - fee) - debit
    if not stop < entry < target or reward <= 0 or reward < loss * policy.minimum_net_reward_risk:
        return None, "net_target_after_costs_insufficient"
    size = min(policy.entry_budget_usdt / debit, policy.maximum_planned_loss_usdt / loss)
    quantity = (size / policy.quantity_step_btc).to_integral_value(
        rounding=ROUND_DOWN
    ) * policy.quantity_step_btc
    if quantity <= 0:
        return None, "quantity_below_research_step"
    _money(quantity)
    expires = tick.observed_at_ns + policy.entry_ttl_ns
    _timestamp(expires)
    return EntryPlan(quantity, entry, stop, target, policy.maximum_hold_ns, expires), None


def _assess_risk(plan, tick, risk, gateway):
    equity = risk.cash_usdt + risk.position_btc * tick.bid_usdt
    peak = max(risk.peak_equity_usdt, equity)
    if equity <= 0:
        return "REJECTED", "nonpositive_equity"
    fee = gateway.costs.taker_fee_bps / BPS
    debit = plan.quantity_btc * plan.reference_price_usdt * (1 + fee)
    decision = evaluate_order(
        OrderIntent("BUY", plan.quantity_btc, plan.reference_price_usdt),
        PortfolioRiskState(
            risk.position_btc, risk.realized_pnl_today_usdt, equity, peak, risk.kill_switch_active
        ),
        gateway.limits,
    )
    if not decision.approved:
        return "REJECTED", "risk_rejected:" + decision.reason
    if debit > risk.cash_usdt:
        return "REJECTED", "insufficient_spot_cash"
    projected_equity = equity - debit + plan.quantity_btc * tick.bid_usdt
    if peak - projected_equity >= gateway.limits.max_drawdown_usdt:
        return "REJECTED", "risk_rejected:projected_drawdown_limit"
    return "APPROVED", "research_risk_checks_passed_not_execution_authority"
