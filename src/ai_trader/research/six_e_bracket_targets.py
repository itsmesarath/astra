"""Fixed, latency-aware quote liquidation targets, never broker fills or a policy."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from ai_trader.research import six_e_crossing_study as previous

SECOND, TICK = previous.events.tape.SECOND, previous.events.tape.TICK
ENTRY_DELAY = EXIT_DELAY = 100_000_000
WAIT = SECOND
HOLD = 15 * SECOND
MARGIN = 18 * SECOND
TARGET, STOP, COST = 3, -3, 1
MAX_PATH_QUOTES = 100_000
PLANS = ("time_exit", "bracket_exit")
SIDES = ("long", "short")
STATES = ("long_only", "short_only", "both_positive", "no_positive", "unknown")


def protocol() -> dict:
    return {
        "version": "six_e_latency_bracket_targets_v1",
        "plans": list(PLANS),
        "entry": "First completed quote >= decision+100ms and <= that target+1s; "
        "first widened spread refuses entry, no searching for a better later quote",
        "eligibility": "Original causal eligibility AND decision+18s strictly before 16 UTC",
        "holding_seconds": HOLD // SECOND,
        "exit": "Market liquidation quote at first completed event >= request+100ms, "
        "within a 1s wait; widened exits and overshoot retained; no exact barrier fills",
        "bracket_net_ticks_after_one_extra_tick": {"target": TARGET, "stop": STOP},
        "trigger": "First observed liquidation quote reaching target/stop strictly BEFORE "
        "entry+15s; otherwise timer at entry+15s; equal-time events keep native order",
        "entry_quote": "Both directions and plans share the same eligible entry quote",
        "costs": "Cross bid/ask plus one assumed round-trip tick; not measured broker costs",
        "unknown": "Missing entry or exit is unknown, not no trade or zero profit; "
        "joint state needs BOTH directional exits resolved; both-positive is not forced "
        "into a unique hindsight direction",
        "states": list(STATES),
        "gap": "Strictly >5s from entry through exit or missing-exit deadline; retained",
        "bounds": {
            "path_quotes": MAX_PATH_QUOTES,
            "quotes_per_day": previous.census.paths.MAX_QUOTES,
        },
        "interpretation": "Overlapping counterfactual labels, not a simultaneous oracle portfolio",
        "training_allowed": False,
        "trading_enabled": False,
    }


def window(session: str) -> tuple[int, int]:
    previous.data.role_for_day(session)  # Refuse reserved before any price access.
    start = int(datetime.fromisoformat(session).replace(tzinfo=UTC).timestamp()) * SECOND
    return start + 12 * 3600 * SECOND, start + 16 * 3600 * SECOND


def validate_quotes(quotes: np.ndarray, session: str) -> int:
    start, end = window(session)
    previous.census.paths.validate_quotes(quotes, end)
    if np.any(quotes[:, 0] < start):
        raise ValueError("Bracket quotes outside declared decision session")
    return end


def _empty(status: str) -> dict:
    return {
        "status": status,
        "trigger": None,
        "trigger_ts_ns": None,
        "trigger_net_ticks": None,
        "exit_target_ts_ns": None,
        "exit_deadline_ts_ns": None,
        "exit_ts_ns": None,
        "exit_bid_nano": None,
        "exit_ask_nano": None,
        "gross_ticks": None,
        "net_ticks": None,
        "inactivity_exposed": False,
        "hold_seconds": None,
        "exit_spread_ticks": None,
    }


def _entry(quotes: np.ndarray, now: int, eligible: bool) -> tuple[dict, int | None]:
    target, deadline = now + ENTRY_DELAY, now + ENTRY_DELAY + WAIT
    entry = {
        "status": "not_eligible" if not eligible else "no_entry_quote_timeout",
        "target_ts_ns": target if eligible else None,
        "deadline_ts_ns": deadline if eligible else None,
        "ts_ns": None,
        "bid_nano": None,
        "ask_nano": None,
        "rejection_ts_ns": None,
    }
    if not eligible:
        return entry, None
    i = int(np.searchsorted(quotes[:, 0], target, side="left"))
    if i >= len(quotes) or quotes[i, 0] > deadline:
        return entry, None
    ts, bid, ask = map(int, quotes[i])
    if ask - bid != TICK:
        entry.update(status="no_entry_spread_widened", rejection_ts_ns=ts)
        return entry, None
    entry.update(status="entered", ts_ns=ts, bid_nano=bid, ask_nano=ask)
    return entry, i


def _resolve(quotes: np.ndarray, entry: dict, i: int | None, side: str, plan: str) -> dict:
    if i is None:
        return _empty(entry["status"])
    times = quotes[:, 0]
    timeout = entry["ts_ns"] + HOLD
    stop = int(np.searchsorted(times, timeout, side="left"))
    if stop - i > MAX_PATH_QUOTES:
        raise ValueError("Bracket native path bound exceeded; no truncation")
    request, trigger, trigger_net = timeout, "timeout", None
    if plan == "bracket_exit":
        path = quotes[i:stop]
        net = (
            (path[:, 1] - entry["ask_nano"]) / TICK - COST
            if side == "long"
            else (entry["bid_nano"] - path[:, 2]) / TICK - COST
        )
        hits = np.flatnonzero((net >= TARGET) | (net <= STOP))
        if len(hits):
            k = int(hits[0])
            request, trigger_net = int(path[k, 0]), float(net[k])
            trigger = "target" if trigger_net >= TARGET else "stop"
    target, deadline = request + EXIT_DELAY, request + EXIT_DELAY + WAIT
    j = int(np.searchsorted(times, target, side="left"))
    resolved = j < len(quotes) and times[j] <= deadline
    last = j + 1 if resolved else int(np.searchsorted(times, deadline, side="right"))
    if last - i > MAX_PATH_QUOTES:
        raise ValueError("Bracket exit path bound exceeded; no truncation")
    path_times = times[i:last]
    span_gap = int(np.diff(path_times).max()) if len(path_times) > 1 else 0
    if not resolved:
        span_gap = max(span_gap, deadline - int(path_times[-1]))
    outcome = _empty("resolved" if resolved else "unresolved_exit_quote_timeout")
    outcome.update(
        trigger=trigger,
        trigger_ts_ns=request,
        trigger_net_ticks=trigger_net,
        exit_target_ts_ns=target,
        exit_deadline_ts_ns=deadline,
        inactivity_exposed=span_gap > 5 * SECOND,
    )
    if resolved:
        ts, bid, ask = map(int, quotes[j])
        gross = (
            (bid - entry["ask_nano"]) / TICK if side == "long" else (entry["bid_nano"] - ask) / TICK
        )
        outcome.update(
            exit_ts_ns=ts,
            exit_bid_nano=bid,
            exit_ask_nano=ask,
            gross_ticks=gross,
            net_ticks=gross - COST,
            hold_seconds=(ts - entry["ts_ns"]) / SECOND,
            exit_spread_ticks=(ask - bid) / TICK,
        )
    return outcome


def targets(rows: list[dict], quotes: np.ndarray) -> list[dict]:
    if not rows:
        raise ValueError("Bracket targets need a complete decision session")
    session = rows[0]["source_session"]
    end = validate_quotes(quotes, session)
    contract = previous.census.dated_contract(session)
    result, last = [], None
    for row in rows:
        now = row["decision_ts_ns"]
        if (
            row["source_session"] != session
            or row["contract"] != contract
            or row["partition"] != "development"
            or type(row["eligible"]) is not bool
            or type(now) is not int
            or not window(session)[0] <= now < end
            or (last is not None and now - last < SECOND)
        ):
            raise ValueError("Bracket decision identity, eligibility or order differs")
        eligible = row["eligible"] and now + MARGIN < end
        reason = (
            row["eligibility_reason"]
            if not row["eligible"]
            else "insufficient_window_for_exit_latency"
            if not eligible
            else None
        )
        entry, i = _entry(quotes, now, eligible)
        outcomes = {p: {s: _resolve(quotes, entry, i, s, p) for s in SIDES} for p in PLANS}
        states = {}
        for plan, sides in outcomes.items():
            if any(o["status"] != "resolved" for o in sides.values()):
                states[plan] = "unknown"
            else:
                long, short = [sides[s]["net_ticks"] > 0 for s in SIDES]
                states[plan] = (
                    "both_positive"
                    if long and short
                    else "long_only"
                    if long
                    else "short_only"
                    if short
                    else "no_positive"
                )
        result.append(
            {
                "source_session": session,
                "contract": contract,
                "partition": "development",
                "decision_ts_ns": now,
                "eligible": eligible,
                "eligibility_reason": reason,
                "entry": entry,
                "outcomes": outcomes,
                "hindsight_states": states,
            }
        )
        last = now
    return result
