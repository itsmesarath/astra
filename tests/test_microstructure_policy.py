"""Hand-built market receipts only: no actual source datasets or model training."""

import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from decimal import ROUND_UP, Decimal, localcontext

import pytest

from ai_trader.features.microstructure import MicrostructureConfig
from ai_trader.risk.engine import RiskLimits
from ai_trader.trading.capture_replay import CaptureReplay, CaptureReplayConfig
from ai_trader.trading.durable_paper_gateway import PaperGatewayConfig
from ai_trader.trading.execution import ExecutionCosts
from ai_trader.trading.microstructure_policy import (
    MicrostructurePolicyConfig,
    ResearchRiskSnapshot,
    assess_microstructure,
)
from ai_trader.trading.paper_runner import PaperMarketTick

D = Decimal
MS = 1_000_000


def policy():
    return MicrostructurePolicyConfig(
        rule="bid_replenishment_cvd",
        minimum_cvd_btc=D("1"),
        minimum_ofi_btc=D("1"),
        minimum_book_imbalance=D("0.2"),
        minimum_bid_ask_liquidity_ratio=D("1.5"),
        minimum_replenishment_intervals=3,
        maximum_spread_bps=D("5"),
        maximum_trade_age_ns=200 * MS,
        entry_budget_usdt=D("100"),
        maximum_planned_loss_usdt=D("2"),
        quantity_step_btc=D("0.001"),
        stop_distance_bps=D("30"),
        target_distance_bps=D("120"),
        minimum_net_reward_risk=D("1"),
        maximum_hold_ns=10_000 * MS,
        entry_ttl_ns=100 * MS,
    )


def replay_config():
    return CaptureReplayConfig(features=MicrostructureConfig(levels=1, rolling_window_ms=100))


def gateway_config():
    return PaperGatewayConfig(
        RiskLimits(D("3"), D("2"), D("1000"), D("3000"), D("20"), D("50")),
        ExecutionCosts(D("10"), D("5")),
        200 * MS,
    )


def capture_rows():
    rows = [
        {
            "schema_version": 1,
            "record_type": "session_start",
            "started_at_ns": 900 * MS,
            "symbol": "BTCUSDT",
            "streams": ["btcusdt@aggTrade", "btcusdt@depth@100ms"],
        },
        {
            "schema_version": 1,
            "record_type": "depth_snapshot",
            "requested_at_ns": 910 * MS,
            "received_at_ns": 950 * MS,
            "event": {
                "lastUpdateId": 100,
                "bids": [["100", "2"], ["99", "10"]],
                "asks": [["100.01", "10"], ["101", "10"]],
            },
        },
    ]

    def append(event, stream):
        rows.append(
            {
                "schema_version": 1,
                "record_type": "stream_event",
                "stream": stream,
                "received_at_ns": event["E"] * MS,
                "event": event,
            }
        )

    def depth(identifier, timestamp, bid, ask):
        append(
            {
                "e": "depthUpdate",
                "E": timestamp,
                "s": "BTCUSDT",
                "U": identifier,
                "u": identifier,
                "b": [["100", str(bid)]],
                "a": [["100.01", str(ask)]],
            },
            "btcusdt@depth@100ms",
        )

    depth(101, 1000, 2, 10)
    for i in range(3):
        for identifier, timestamp, qty, sell in [
            (2 * i + 1, 1040 + i * 100, 2 + i * 2, True),
            (2 * i + 2, 1050 + i * 100, 8, False),
        ]:
            append(
                {
                    "e": "aggTrade",
                    "E": timestamp,
                    "T": timestamp,
                    "s": "BTCUSDT",
                    "a": identifier,
                    "f": identifier,
                    "l": identifier,
                    "q": str(qty),
                    "p": "100" if sell else "100.01",
                    "m": sell,
                },
                "btcusdt@aggTrade",
            )
        depth(102 + i, 1100 + i * 100, 4 + i * 2, [9, 8, 3][i])
    rows.append(
        {
            "schema_version": 1,
            "record_type": "session_end",
            "ended_at_ns": 1400 * MS,
            "trade_events": 6,
            "depth_events": 4,
        }
    )
    return rows


def capture_bytes(rows=None):
    return b"".join(
        json.dumps(r).encode() + b"\n" for r in (capture_rows() if rows is None else rows)
    )


def replay(rows=None):
    data = capture_bytes(rows)
    return CaptureReplay(
        data,
        expected_sha256=hashlib.sha256(data).hexdigest(),
        source_session="research-one",
        config=replay_config(),
    )


def signal_frame():
    return [f for f in replay().frames() if f.observation is not None][-1]


def risk(frame=None, **kwargs):
    frame = frame or signal_frame()
    return ResearchRiskSnapshot(
        **(
            dict(
                observed_at_ns=frame.tick.observed_at_ns,
                cash_usdt=D("1000"),
                position_btc=D(0),
                realized_pnl_today_usdt=D(0),
                peak_equity_usdt=D("1000"),
                kill_switch_active=False,
                unresolved_orders=False,
            )
            | kwargs
        )
    )


def assess(frame=None, **kwargs):
    frame = frame or signal_frame()
    options = dict(
        policy=policy(),
        features=replay_config().features,
        gateway=gateway_config(),
        risk=risk(frame),
        registration_sha256="a" * 64,
    )
    return assess_microstructure(frame, **(options | kwargs))


def bind(frame, observation):
    return replace(
        frame,
        observation=observation,
        tick=PaperMarketTick.from_observation(
            observation,
            tick_id=frame.tick.tick_id,
            observed_at_ns=frame.tick.observed_at_ns,
            last_trade_received_at_ns=frame.tick.last_trade_received_at_ns,
            book_synchronized=True,
        ),
    )


def test_engine_evidence_produces_costed_research_case():
    frame = signal_frame()
    assert frame.observation.bid.absorption_candidate
    assert frame.observation.bid.consecutive_replenishment_intervals == 3
    assert frame.observation.rolling_cvd_base == 2
    assert frame.observation.top_level_order_flow_imbalance == 7
    case = assess(frame)
    assert case.action == "ENTER_LONG" and case.risk_verdict == "APPROVED"
    assert case.mode == "research_only"
    assert case.plan.reference_price_usdt == D("100.060005")
    assert case.plan.stop_price_usdt == D("99.7")
    assert case.plan.take_profit_price_usdt == D("101.2")
    assert case.plan.quantity_btc == D("0.998")
    assert case.plan.expires_at_ns == 1400 * MS
    assert case.plan.quantity_btc * case.plan.reference_price_usdt * D("1.001") <= 100
    assert case.evidence[0].available_at_ns <= case.decision_at_ns
    assert case.risk_config_sha256 == gateway_config().risk_config_sha256
    assert assess(frame) == case


def test_loss_budget_accounts_for_spread_fees_and_both_slippages():
    settings = replace(policy(), maximum_planned_loss_usdt=D("0.05"))
    case = assess(policy=settings)
    entry_cost = case.plan.reference_price_usdt * D("1.001")
    stop_proceeds = case.plan.stop_price_usdt * D("0.9995") * D("0.999")
    loss = case.plan.quantity_btc * (entry_cost - stop_proceeds)
    assert loss <= D("0.05")
    assert (case.plan.quantity_btc + settings.quantity_step_btc) * (entry_cost - stop_proceeds) > D(
        "0.05"
    )


@pytest.mark.parametrize(
    "changes, reason",
    [
        ({"minimum_cvd_btc": D("3")}, "cvd_below_threshold"),
        ({"minimum_ofi_btc": D("8")}, "ofi_below_threshold"),
        ({"minimum_book_imbalance": D("0.5")}, "book_imbalance_below_threshold"),
        ({"minimum_bid_ask_liquidity_ratio": D("3")}, "bid_liquidity_below_threshold"),
        ({"minimum_replenishment_intervals": 4}, "bid_replenishment_not_confirmed"),
        ({"maximum_spread_bps": D("0.5")}, "spread_limit"),
        ({"target_distance_bps": D("10")}, "net_target_after_costs_insufficient"),
        ({"minimum_net_reward_risk": D("10")}, "net_target_after_costs_insufficient"),
        ({"quantity_step_btc": D("2")}, "quantity_below_research_step"),
        ({"rule": "abstain"}, "no_trade_control"),
    ],
)
def test_evidence_and_cost_gates_retain_explicit_abstention(changes, reason):
    case = assess(policy=replace(policy(), **changes))
    assert case.action == "NO_ACTION" and case.plan is None
    assert case.risk_verdict == "NOT_EVALUATED" and case.risk_reason == reason


@pytest.mark.parametrize(
    "changes, reason",
    [
        ({"kill_switch_active": True}, "risk_rejected:kill_switch_active"),
        ({"realized_pnl_today_usdt": D("-20")}, "risk_rejected:daily_loss_limit_reached"),
        ({"peak_equity_usdt": D("1050")}, "risk_rejected:drawdown_limit_reached"),
        ({"cash_usdt": D("50"), "peak_equity_usdt": D("50")}, "insufficient_spot_cash"),
        ({"cash_usdt": D(0)}, "nonpositive_equity"),
    ],
)
def test_risk_rejections_keep_original_proposal(changes, reason):
    case = assess(risk=risk(**changes))
    assert case.action == "ENTER_LONG" and case.plan is not None
    assert case.risk_verdict == "REJECTED" and case.risk_reason == reason
    assert case.approved_quantity_btc is None


@pytest.mark.parametrize("changes", [{"position_btc": D("0.01")}, {"unresolved_orders": True}])
def test_no_pyramiding_or_inflight_duplicates(changes):
    case = assess(risk=risk(**changes))
    assert (
        case.action == "NO_ACTION" and case.risk_reason == "existing_inventory_or_unresolved_orders"
    )


def test_hard_limits_and_projected_drawdown_are_not_silently_resized():
    config = gateway_config()
    small = replace(config, limits=replace(config.limits, max_order_btc=D("0.1")))
    case = assess(gateway=small)
    assert case.risk_verdict == "REJECTED" and case.plan.quantity_btc == D("0.998")
    assert case.risk_reason == "risk_rejected:order_quantity_limit_exceeded"
    small = replace(config, limits=replace(config.limits, max_drawdown_usdt=D("0.1")))
    assert assess(gateway=small).risk_reason == "risk_rejected:projected_drawdown_limit"


@pytest.mark.parametrize(
    "changes, reason",
    [
        ({"rolling_window_complete": False}, "microstructure_not_ready"),
        ({"bid_band_covered": False}, "microstructure_not_ready"),
        ({"ask_top_n_covered": False}, "microstructure_not_ready"),
        ({"evidence_interval_valid": False}, "microstructure_not_ready"),
        ({"unmatched_trade_count": 1}, "ambiguous_trade_attribution"),
        ({"pending_trade_count": 1}, "ambiguous_trade_attribution"),
    ],
)
def test_health_gates(changes, reason):
    frame = signal_frame()
    case = assess(bind(frame, replace(frame.observation, **changes)))
    assert case.action == "NO_ACTION" and case.risk_reason == reason


def test_receipt_age_and_no_new_observation():
    frame = signal_frame()
    stale = replace(frame, tick=replace(frame.tick, observed_at_ns=1600 * MS))
    assert assess(stale).risk_reason == "stale_quote"
    stale = replace(frame, tick=replace(frame.tick, last_trade_received_at_ns=1000 * MS))
    assert assess(stale).risk_reason == "stale_trades"
    assert (
        assess(replace(frame, observation=None, status="no_new_depth")).risk_reason
        == "no_new_depth_observation"
    )
    assert assess(next(replay().frames())).risk_reason == "book_unsynchronized"


def test_opposing_ask_absorption_veto():
    rows = capture_rows()
    rows[-2]["event"]["a"] = [["100.01", "8"]]
    frame = [f for f in replay(rows).frames() if f.observation][-1]
    assert assess(frame).risk_reason == "opposing_ask_absorption"


@pytest.mark.parametrize(
    "changes",
    [
        {"rolling_cvd_base": D("NaN")},
        {"rolling_cvd_base": D("Infinity")},
        {"rolling_cvd_base": D("9")},
        {"rolling_cvd_base": 2},
        {"rolling_window_complete": 1},
    ],
)
def test_bad_observation_never_emits_a_case(changes):
    frame = signal_frame()
    with pytest.raises(ValueError):
        # Bind without PaperMarketTick.from_observation so malformed flags reach this API too.
        from ai_trader.trading.trade_journal import _encode, _hash

        row = replace(frame.observation, **changes)
        assess(
            replace(
                frame,
                observation=row,
                tick=replace(frame.tick, observation_sha256=_hash(_encode(row))),
            )
        )


def test_hash_timestamp_and_feature_mismatches_fail_closed():
    frame = signal_frame()
    with pytest.raises(ValueError, match="match"):
        assess(replace(frame, tick=replace(frame.tick, observation_sha256="f" * 64)))
    with pytest.raises(ValueError, match="as-of"):
        assess(risk=risk(observed_at_ns=1400 * MS))
    with pytest.raises(ValueError, match="as-of"):
        assess(risk=risk(observed_at_ns=1200 * MS))
    with pytest.raises(ValueError, match="match"):
        assess(features=replace(replay_config().features, levels=2))


def test_cases_independent_of_callers_decimal_context():
    frame, config, portfolio = signal_frame(), gateway_config(), risk()
    expected = assess(frame, gateway=config, risk=portfolio)
    with localcontext() as context:
        context.prec, context.rounding = 6, ROUND_UP
        assert assess(frame, gateway=config, risk=portfolio) == expected


def test_future_market_events_do_not_change_earlier_decisions():
    original = list(replay().frames())
    rows = capture_rows()
    rows[-2]["event"]["b"] = [["100", "100"]]
    changed = list(replay(rows).frames())
    for left, right in zip(original[:-2], changed[:-2], strict=True):
        assert assess(left) == assess(right)


@pytest.mark.parametrize(
    "changes",
    [
        {"rule": "live"},
        {"minimum_cvd_btc": D(0)},
        {"minimum_cvd_btc": D("NaN")},
        {"minimum_cvd_btc": 1},
        {"minimum_book_imbalance": D(1)},
        {"minimum_replenishment_intervals": True},
        {"minimum_replenishment_intervals": 1},
        {"maximum_trade_age_ns": 0},
        {"maximum_hold_ns": False},
        {"target_distance_bps": D(10000)},
        {"minimum_net_reward_risk": D("0.5")},
        {"quantity_step_btc": D("-0.1")},
    ],
)
def test_invalid_thresholds(changes):
    with pytest.raises(ValueError):
        replace(policy(), **changes)


def test_deep_immutability():
    with pytest.raises(FrozenInstanceError):
        policy().rule = "abstain"
    with pytest.raises(FrozenInstanceError):
        assess().plan.quantity_btc = D(999)


@pytest.mark.parametrize(
    "changes",
    [
        {"evidence_interval_ms": None},
        {"evidence_interval_ms": 0},
        {"evidence_interval_ms": 1001},
        {"rolling_trade_count": 0},
    ],
)
def test_inconsistent_readiness_not_treated_as_a_signal(changes):
    frame = signal_frame()
    with pytest.raises(ValueError):
        assess(bind(frame, replace(frame.observation, **changes)))


@pytest.mark.parametrize(
    "changes",
    [
        {"absorption_candidate": False},
        {"repeated_replenishment_candidate": False},
        {"net_addition_proxy": D("100")},
        {"price": D(0)},
        {"aggressive_volume_at_price": D(0)},
    ],
)
def test_forged_passive_side_evidence_fails(changes):
    frame = signal_frame()
    row = replace(frame.observation, bid=replace(frame.observation.bid, **changes))
    with pytest.raises(ValueError):
        assess(bind(frame, row))


def test_research_case_cannot_be_inserted_into_paper_journal(tmp_path):
    from ai_trader.trading.trade_journal import TradeJournal

    with TradeJournal.create(tmp_path / "paper.sqlite", run_id="paper", mode="paper") as journal:
        with pytest.raises(ValueError, match="mode"):
            journal.append_case(assess())
        assert journal.order_ids() == ()


@pytest.mark.parametrize(
    "changes",
    [
        {"cash_usdt": D(-1)},
        {"position_btc": D(-1)},
        {"kill_switch_active": 1},
        {"realized_pnl_today_usdt": D("NaN")},
        {"observed_at_ns": True},
    ],
)
def test_invalid_risk_snapshot(changes):
    with pytest.raises(ValueError):
        risk(**changes)
