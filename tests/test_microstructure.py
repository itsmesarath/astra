"""Hand-calculated receipt-causal order-flow evidence, never actual market data."""

from dataclasses import replace
from decimal import ROUND_UP, Decimal, localcontext

import pytest

from ai_trader.features.microstructure import MicrostructureConfig, MicrostructureEngine
from ai_trader.ingestion.agg_trade import AggTrade
from ai_trader.orderbook.depth_update import DepthChange, DepthUpdate
from ai_trader.orderbook.local_book import LocalOrderBook, SequenceGapError

D = Decimal


def book():
    return LocalOrderBook("BTCUSDT", 100, {D(100): D(2), D(99): D(3)}, {D(101): D(3), D(102): D(4)})


def engine(**kwargs):
    return MicrostructureEngine("test-session", book(), MicrostructureConfig(levels=1, **kwargs))


def depth(identifier=101, time=1000, bids=(), asks=()):
    return DepthUpdate(
        time,
        "BTCUSDT",
        identifier,
        identifier,
        tuple(DepthChange(D(p), D(q)) for p, q in bids),
        tuple(DepthChange(D(p), D(q)) for p, q in asks),
    )


def trade(identifier=1, time=1050, price="101", quantity="3", sell=False):
    return AggTrade(
        time, "BTCUSDT", identifier, D(price), D(quantity), identifier, identifier, time, sell
    )


def baseline(subject):
    return subject.apply_depth(depth(), received_at_ns=1_000_000_000)


def test_baseline_has_no_attribution_and_does_not_mutate_callers_book():
    source = book()
    subject = MicrostructureEngine("one", source, MicrostructureConfig(levels=1))
    first = baseline(subject)
    assert first.bid is None and first.ask is None
    assert not first.evidence_interval_valid
    assert first.top_level_order_flow_imbalance is None
    assert first.bid_band_depth == D(2)
    assert first.ask_band_depth == D(3)
    assert first.bid_band_covered and first.ask_band_covered
    subject.apply_depth(depth(102, 1100, bids=(("100", "4"),)), received_at_ns=1_100_000_000)
    assert source.bids[D(100)] == D(2)


def test_signed_cvd_quote_and_rolling_window_half_open_boundary():
    subject = engine(rolling_window_ms=100)
    baseline(subject)
    subject.add_trade(trade(quantity="3"), received_at_ns=1_050_000_000)
    subject.add_trade(trade(2, 1070, "100", "1", True), received_at_ns=1_070_000_000)
    first = subject.apply_depth(depth(102, 1100), received_at_ns=1_100_000_000)
    assert first.session_cvd_base == first.rolling_cvd_base == D(2)
    assert first.session_cvd_quote == D(203)
    assert first.rolling_trade_count == 2
    assert first.rolling_window_complete
    second = subject.apply_depth(depth(103, 1150), received_at_ns=1_150_000_000)
    assert second.rolling_buy_base == 0
    assert second.rolling_sell_base == 1
    assert second.session_cvd_base == 2
    assert second.rolling_cvd_base == -1


def test_ask_absorption_and_repeated_replenishment_evidence():
    subject = engine()
    baseline(subject)
    for i in range(3):
        subject.add_trade(trade(i + 1, 1050 + i * 100), received_at_ns=(1050 + i * 100) * 1_000_000)
        row = subject.apply_depth(
            depth(102 + i, 1100 + i * 100), received_at_ns=(1100 + i * 100) * 1_000_000
        )
        assert row.ask.price == 101
        assert row.ask.net_addition_proxy == 3
        assert row.ask.aggressive_volume_at_price == 3
        assert row.ask.absorption_candidate
        assert row.ask.consecutive_replenishment_intervals == i + 1
        assert row.ask.repeated_replenishment_candidate == (i == 2)
        assert not row.bid.absorption_candidate
    row = subject.apply_depth(depth(105, 1400), received_at_ns=1_400_000_000)
    assert row.ask.consecutive_replenishment_intervals == 0


def test_bid_absorption_requires_selling_at_exact_old_best_bid():
    subject = engine()
    baseline(subject)
    subject.add_trade(trade(price="100", quantity="2", sell=True), received_at_ns=1_050_000_000)
    row = subject.apply_depth(depth(102, 1100), received_at_ns=1_100_000_000)
    assert row.bid.absorption_candidate
    assert row.bid.net_addition_proxy == 2
    assert row.session_cvd_base == -2


def test_depletion_or_price_movement_is_not_absorption():
    subject = engine()
    baseline(subject)
    subject.add_trade(trade(), received_at_ns=1_050_000_000)
    row = subject.apply_depth(depth(102, 1100, asks=(("101", "0"),)), received_at_ns=1_100_000_000)
    assert not row.ask.absorption_candidate
    assert row.ask.net_addition_proxy == 0
    assert row.ask.consecutive_replenishment_intervals == 0


def test_addition_without_trades_is_not_iceberg_or_absorption():
    subject = engine()
    baseline(subject)
    row = subject.apply_depth(depth(102, 1100, asks=(("101", "9"),)), received_at_ns=1_100_000_000)
    assert row.ask.net_addition_proxy == 6
    assert not row.ask.absorption_candidate
    assert not row.ask.repeated_replenishment_candidate
    assert row.ask.consecutive_replenishment_intervals == 0
    assert row.top_level_order_flow_imbalance == -6


@pytest.mark.parametrize(
    "bids,asks,expected",
    [
        ((("100", "5"),), (), "3"),
        ((), (("101", "1"),), "2"),
        ((("100.5", "4"),), (), "4"),
        ((("100", "0"),), (), "-2"),
        ((), (("100.5", "4"),), "-4"),
        ((), (("101", "0"),), "3"),
    ],
)
def test_best_level_ofi_price_changes(bids, asks, expected):
    subject = engine()
    baseline(subject)
    row = subject.apply_depth(depth(102, 1100, bids, asks), received_at_ns=1_100_000_000)
    assert row.top_level_order_flow_imbalance == D(expected)


def test_late_trade_never_rewrites_previous_evidence():
    subject = engine()
    baseline(subject)
    first = subject.apply_depth(depth(102, 1100), received_at_ns=1_100_000_000)
    subject.add_trade(trade(time=1050), received_at_ns=1_110_000_000)
    second = subject.apply_depth(depth(103, 1200), received_at_ns=1_200_000_000)
    assert first.session_cvd_base == 0
    assert second.session_cvd_base == 3
    assert second.unmatched_trade_count == 1
    assert second.ask.aggressive_volume_at_price == 0
    assert not second.ask.absorption_candidate


def test_future_exchange_time_waits_for_eligible_depth_interval():
    subject = engine()
    baseline(subject)
    subject.add_trade(trade(time=1150), received_at_ns=1_090_000_000)
    first = subject.apply_depth(depth(102, 1100), received_at_ns=1_100_000_000)
    second = subject.apply_depth(depth(103, 1200), received_at_ns=1_200_000_000)
    assert first.pending_trade_count == 1
    assert first.ask.aggressive_volume_at_price == 0
    assert second.pending_trade_count == 0
    assert second.ask.aggressive_volume_at_price == 3


def test_stale_depth_does_not_consume_pending_flow():
    subject = engine()
    baseline(subject)
    subject.add_trade(trade(), received_at_ns=1_050_000_000)
    assert subject.apply_depth(depth(101, 1060), received_at_ns=1_060_000_000) is None
    row = subject.apply_depth(depth(102, 1100), received_at_ns=1_100_000_000)
    assert row.ask.aggressive_volume_at_price == 3


@pytest.mark.parametrize("time", [1000, 2100])
def test_equal_depth_time_or_long_interval_suppresses_evidence(time):
    subject = engine()
    baseline(subject)
    row = subject.apply_depth(depth(102, time), received_at_ns=2_100_000_000)
    assert row.bid is None and row.ask is None
    assert not row.evidence_interval_valid


def test_depth_gap_invalidates_engine_until_new_snapshot():
    subject = engine()
    baseline(subject)
    with pytest.raises(SequenceGapError):
        subject.apply_depth(depth(103, 1100), received_at_ns=1_100_000_000)
    with pytest.raises(ValueError, match="invalidated"):
        subject.apply_depth(depth(102, 1200), received_at_ns=1_200_000_000)
    assert baseline(engine()).session_cvd_base == 0


@pytest.mark.parametrize(
    "change",
    [
        {"quantity": D("NaN")},
        {"price": D("Infinity")},
        {"quantity": D("-1")},
        {"buyer_is_maker": 1},
        {"trade_time_ms": True},
        {"symbol": "ETHUSDT"},
    ],
)
def test_invalid_trade_invalidates_engine(change):
    subject = engine()
    with pytest.raises(ValueError):
        subject.add_trade(replace(trade(), **change), received_at_ns=1_000_000_000)
    assert not subject.valid


@pytest.mark.parametrize("identifier", [1, 3])
def test_duplicate_or_missing_trade_id_invalidates_cvd(identifier):
    subject = engine()
    subject.add_trade(trade(), received_at_ns=1_050_000_000)
    with pytest.raises(ValueError, match="contiguous"):
        subject.add_trade(trade(identifier, 1060), received_at_ns=1_060_000_000)


def test_backwards_receipt_and_buffer_overflow_fail_closed():
    subject = engine(maximum_buffered_trades=1)
    subject.add_trade(trade(), received_at_ns=1_050_000_000)
    with pytest.raises(ValueError, match="buffer"):
        subject.add_trade(trade(2, 1060), received_at_ns=1_060_000_000)
    subject = engine()
    baseline(subject)
    with pytest.raises(ValueError, match="backwards"):
        subject.add_trade(trade(), received_at_ns=999)


def test_outer_depth_change_does_not_expand_known_snapshot_coverage():
    subject = engine(liquidity_band_bps=D("200"))
    first = baseline(subject)
    assert not first.bid_band_covered and not first.ask_band_covered
    row = subject.apply_depth(
        depth(102, 1100, (("97", "5"),), (("105", "5"),)), received_at_ns=1_100_000_000
    )
    assert not row.bid_band_covered and not row.ask_band_covered


def test_decimal_context_does_not_change_observations():
    a, b = engine(), engine()
    baseline(a)
    baseline(b)
    expected = a.apply_depth(
        depth(102, 1100, bids=(("100", "3.3333333333"),)), received_at_ns=1_100_000_000
    )
    with localcontext() as context:
        context.prec = 7
        context.rounding = ROUND_UP
        assert (
            b.apply_depth(
                depth(102, 1100, bids=(("100", "3.3333333333"),)), received_at_ns=1_100_000_000
            )
            == expected
        )


def test_best_quote_beyond_snapshot_requires_resynchronization():
    subject = engine()
    baseline(subject)
    with pytest.raises(ValueError, match="snapshot coverage"):
        subject.apply_depth(
            depth(102, 1100, bids=(("100", "0"), ("99", "0"), ("97", "4"))),
            received_at_ns=1_100_000_000,
        )
    assert not subject.valid


def test_observed_top_n_depth_can_be_incomplete_even_with_known_best():
    subject = MicrostructureEngine("one", book(), MicrostructureConfig(levels=2))
    first = baseline(subject)
    assert first.bid_top_n_covered and first.ask_top_n_covered
    row = subject.apply_depth(
        depth(102, 1100, bids=(("99", "0"), ("97", "4"))), received_at_ns=1_100_000_000
    )
    assert not row.bid_top_n_covered
    assert row.ask_top_n_covered
    assert row.bid_band_covered


def test_pre_baseline_trades_contribute_cvd_but_not_attribution():
    subject = engine()
    subject.add_trade(trade(time=950), received_at_ns=950_000_000)
    row = baseline(subject)
    assert row.session_cvd_base == 3
    assert row.unmatched_trade_count == 1
    assert row.bid is None and row.ask is None


def test_same_timestamp_trade_boundary_is_unmatched_not_reused():
    subject = engine()
    baseline(subject)
    subject.add_trade(trade(time=1000), received_at_ns=1_050_000_000)
    row = subject.apply_depth(depth(102, 1100), received_at_ns=1_100_000_000)
    assert row.unmatched_trade_count == 1
    assert row.ask.aggressive_volume_at_price == 0
    second = subject.apply_depth(depth(103, 1200), received_at_ns=1_200_000_000)
    assert second.unmatched_trade_count == 0


@pytest.mark.parametrize(
    "changes",
    [
        (("101", "NaN"),),
        (("101", "Infinity"),),
        (("101", "-1"),),
        (("101", "2"), ("101", "3")),
    ],
)
def test_malformed_depth_changes_invalidate_engine(changes):
    subject = engine()
    baseline(subject)
    with pytest.raises(ValueError):
        subject.apply_depth(depth(102, 1100, asks=changes), received_at_ns=1_100_000_000)
    assert not subject.valid


def test_locked_book_invalidates_engine_without_changing_old_observation():
    subject = engine()
    first = baseline(subject)
    with pytest.raises(ValueError, match="locked or crossed"):
        subject.apply_depth(depth(102, 1100, bids=(("101", "2"),)), received_at_ns=1_100_000_000)
    assert first.book.best_bid_price == 100
    assert not subject.valid


@pytest.mark.parametrize(
    "config",
    [
        MicrostructureConfig(levels=0),
        MicrostructureConfig(levels=True),
        MicrostructureConfig(rolling_window_ms=0),
        MicrostructureConfig(repeated_intervals=0),
        MicrostructureConfig(retained_depth_fraction=D("NaN")),
        MicrostructureConfig(liquidity_band_bps=D("10000")),
        MicrostructureConfig(retained_depth_fraction=D("1.1")),
    ],
)
def test_invalid_configuration_is_rejected(config):
    with pytest.raises(ValueError):
        MicrostructureEngine("one", book(), config)
