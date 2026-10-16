"""Causal reference states, never fills, execution labels, live feeds or training inputs."""

from __future__ import annotations

import numpy as np

from ai_trader.research import six_e_bracket_targets as targets

VERSION = "six_e_completed_quote_reference_v1"
MAX_QUOTES = 12_000_000


def age_band(age_ns: int) -> str:
    if type(age_ns) is not int or age_ns < 0:
        raise ValueError("Reference age must be a nonnegative integer")
    if age_ns <= 100_000_000:
        return "at_most_100ms"
    if age_ns <= 250_000_000:
        return "over_100_through_250ms"
    if age_ns <= 1_000_000_000:
        return "over_250_through_1000ms"
    return "over_1000ms"


def reference(
    quotes: np.ndarray,
    *,
    source_session: str,
    contract: str,
    request_ts_ns: int,
    published_cursor: int,
) -> dict:
    """Choose the last state in a published prefix, including native equal-time order.

    Caller must supply an explicit last-published event cursor; receive timestamps
    alone cannot prove local publication or broker receipt. Array validation is
    not a source-file lineage check. This function has no I/O or model calls.
    """
    start, end = targets.window(source_session)  # Reserved guard BEFORE quote access.
    if contract != targets.previous.census.dated_contract(source_session):
        raise ValueError("Reference contract is not the declared development contract")
    if type(request_ts_ns) is not int or not start <= request_ts_ns < end:
        raise ValueError("Reference request must belong to the original UTC decision window")
    if (
        not isinstance(quotes, np.ndarray)
        or quotes.dtype != np.dtype(np.int64)
        or quotes.ndim != 2
        or quotes.shape[1] != 3
        or len(quotes) > MAX_QUOTES
    ):
        raise ValueError("Reference quotes require bounded native int64 time/bid/ask columns")
    if type(published_cursor) is not int or not -1 <= published_cursor < len(quotes):
        raise ValueError("An explicit valid last-published cursor is required")
    if len(quotes):
        targets.validate_quotes(quotes, source_session)
    result = {
        "version": VERSION,
        "status": "no_published_completed_reference",
        "source_session": source_session,
        "contract": contract,
        "request_ts_ns": request_ts_ns,
        "published_cursor": published_cursor,
        "reference_cursor": None,
        "reference_ts_ns": None,
        "age_ns": None,
        "age_band": None,
        "bid_nano": None,
        "ask_nano": None,
        "source_identity_verified": False,
        "local_or_broker_receipt_verified": False,
        "execution_confirmed": False,
        "training_eligible": False,
        "promotion_allowed": False,
        "trading_enabled": False,
    }
    if published_cursor < 0:
        return result
    prefix = quotes[: published_cursor + 1]
    index = int(np.searchsorted(prefix[:, 0], request_ts_ns, side="right")) - 1
    if index < 0:
        return result
    ts, bid, ask = map(int, prefix[index])
    age = request_ts_ns - ts
    result.update(
        status="completed_quote_reference_only_not_fill",
        reference_cursor=index,
        reference_ts_ns=ts,
        age_ns=age,
        age_band=age_band(age),
        bid_nano=bid,
        ask_nano=ask,
    )
    return result
