"""Synthetic-only reference states preserve causality and cannot imply execution."""

from copy import deepcopy

import numpy as np
import pytest

from ai_trader.research import six_e_quote_reference as reference

DAY = "2025-04-07"
START = reference.targets.window(DAY)[0]
TICK = reference.targets.TICK


def quotes():
    return np.array(
        [
            [START, 100 * TICK, 101 * TICK],
            [START + 100_000_000, 101 * TICK, 102 * TICK],
            [START + 100_000_000, 102 * TICK, 103 * TICK],
            [START + 2_000_000_000, 103 * TICK, 105 * TICK],
        ],
        dtype=np.int64,
    )


def select(q=None, **kwargs):
    defaults = dict(
        source_session=DAY,
        contract="6EM5",
        request_ts_ns=START + 100_000_000,
        published_cursor=2,
    )
    return reference.reference(quotes() if q is None else q, **(defaults | kwargs))


def test_equal_time_states_require_publication_cursor_and_not_timestamp_alone():
    earlier = select(published_cursor=1)
    later = select(published_cursor=2)
    assert earlier["reference_cursor"] == 1 and later["reference_cursor"] == 2
    assert earlier["reference_ts_ns"] == later["reference_ts_ns"]
    assert earlier["bid_nano"] == 101 * TICK and later["bid_nano"] == 102 * TICK
    assert not any(
        earlier[k]
        for k in (
            "source_identity_verified",
            "local_or_broker_receipt_verified",
            "execution_confirmed",
            "training_eligible",
            "promotion_allowed",
            "trading_enabled",
        )
    )
    assert "net_ticks" not in earlier and "fill" not in earlier


def test_future_suffix_cannot_change_an_earlier_published_reference_or_mutate_input():
    q = quotes()
    original = deepcopy(q)
    assert select(q[:3]) == select(q)
    np.testing.assert_array_equal(q, original)
    assert select(request_ts_ns=START + 50_000_000)["reference_cursor"] == 0


def test_empty_unpublished_and_not_yet_observed_state_never_invent_prices():
    for value in (
        select(np.empty((0, 3), dtype=np.int64), published_cursor=-1),
        select(published_cursor=-1),
        select(quotes()[1:], request_ts_ns=START, published_cursor=0),
    ):
        assert value["status"] == "no_published_completed_reference"
        assert value["bid_nano"] is None and value["age_ns"] is None
        assert value["execution_confirmed"] is False


@pytest.mark.parametrize(
    "age,band",
    [
        (0, "at_most_100ms"),
        (100_000_000, "at_most_100ms"),
        (100_000_001, "over_100_through_250ms"),
        (250_000_000, "over_100_through_250ms"),
        (250_000_001, "over_250_through_1000ms"),
        (1_000_000_000, "over_250_through_1000ms"),
        (1_000_000_001, "over_1000ms"),
    ],
)
def test_age_bands_are_exact_descriptive_boundaries_not_execution_thresholds(age, band):
    assert reference.age_band(age) == band


def test_old_or_widened_quote_remains_a_reference_not_a_fill_or_training_label():
    value = select(request_ts_ns=START + 4_000_000_000, published_cursor=3)
    assert value["age_ns"] == 2_000_000_000 and value["age_band"] == "over_1000ms"
    assert value["ask_nano"] - value["bid_nano"] == 2 * TICK
    assert value["status"] == "completed_quote_reference_only_not_fill"
    assert value["execution_confirmed"] is False and value["training_eligible"] is False


@pytest.mark.parametrize("value", [True, -1, 1.5, float("nan")])
def test_invalid_age_is_refused(value):
    with pytest.raises(ValueError):
        reference.age_band(value)


@pytest.mark.parametrize("change", ["reserved", "contract", "timestamp", "bool_timestamp"])
def test_identity_guard_precedes_quote_access(change):
    class Poison:
        def __len__(self):
            pytest.fail("identity refusal touched quotes")

    kwargs = (
        {"source_session": "2026-01-01"}
        if change == "reserved"
        else {"contract": "6EU5"}
        if change == "contract"
        else {"request_ts_ns": START - 1}
        if change == "timestamp"
        else {"request_ts_ns": True}
    )
    with pytest.raises(ValueError):
        select(Poison(), **kwargs)


@pytest.mark.parametrize("cursor", [True, -2, 4, 1.5, None])
def test_missing_or_invalid_publication_cursor_is_refused(cursor):
    with pytest.raises(ValueError):
        select(published_cursor=cursor)


@pytest.mark.parametrize(
    "change",
    ["float", "unsigned", "shape", "reversed", "cross_session", "crossed", "off_tick", "bound"],
)
def test_invalid_quote_columns_never_produce_a_reference(change, monkeypatch):
    q = quotes()
    if change == "float":
        q = q.astype(float)
    elif change == "unsigned":
        q = q.astype(np.uint64)
    elif change == "shape":
        q = q[:, :2]
    elif change == "reversed":
        q = q[::-1]
    elif change == "cross_session":
        q[-1, 0] = START + 86400 * 1_000_000_000
    elif change == "crossed":
        q[0, 2] = q[0, 1]
    elif change == "off_tick":
        q[0, 1] += 1
    else:
        monkeypatch.setattr(reference, "MAX_QUOTES", 3)
    with pytest.raises(ValueError):
        select(q)
