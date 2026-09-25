"""Read-only, cost-aware audit of one registered offline paper journal.

No policy execution, order submission, forced liquidation, fitting or promotion.
Only the entire committed prefix is evaluated; a budget cannot hide later losses.
"""

import argparse
import json
from collections import Counter
from dataclasses import replace
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from itertools import chain, islice
from pathlib import Path
from types import MappingProxyType

from ai_trader.research.microstructure_trial import _environment, load_registration
from ai_trader.trading.capture_replay import CaptureReplay, _implementation_hash
from ai_trader.trading.durable_paper_gateway import DurablePaperGateway, _decode_request
from ai_trader.trading.execution import MarketQuote, simulate_market_fill
from ai_trader.trading.microstructure_paper import _case_id, _verify_replayed_case, paper_run_id
from ai_trader.trading.paper_account import PaperAccountSeed, recover_account
from ai_trader.trading.paper_lifecycle import PaperEntryOrder
from ai_trader.trading.paper_runner import PaperRunner, PaperRunnerConfig
from ai_trader.trading.trade_journal import JournalError, TradeJournal, _encode, _hash, _read

EVALUATION_VERSION = "registered_quote_paper_evaluation_v1"
# Fixed protocol, fingerprinted with the registration's source implementation. No
# post-outcome selection of valuation, benchmark, costs or terminal liquidation.
PROTOCOL = MappingProxyType(
    {
        "version": EVALUATION_VERSION,
        "scope": "entire_committed_prefix",
        "marks": "fresh_synchronized_bid_before_and_after_tick_orders",
        "terminal": "retain_inventory_no_forced_liquidation",
        "unhealthy_open_inventory": "unknown_equity_no_forward_fill",
        "costs": "recorded_fees_and_slipped_fills_once",
        "control": "same_initial_cash_no_interest_no_trades",
        "fills": "atomic_full_quote_fills_only",
        "comparison": "complete_fault_free_flat_run_only",
    }
)
DECIMAL_CONTEXT = Context(prec=100, rounding=ROUND_HALF_EVEN)


def _json(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, default=str)


def _number(value):
    return None if value is None else str(value)


def _quote_health(tick, config):
    if not tick.book_synchronized:
        return "book_unsynchronized"
    if tick.observed_at_ns - tick.quote_received_at_ns > config.max_quote_age_ns:
        return "stale_quote"
    return "healthy"


def _read_order(journal, tick, order_id, config):
    """Bind each atomic lifecycle to its exact recorded quote and cost assumptions."""
    order = journal.get_order(order_id)
    row = journal._db.execute(
        "SELECT payload, sha256 FROM paper_gateway_requests WHERE order_id=?", (order_id,)
    ).fetchone()
    if order is None or row is None or order.requested_at_ns != tick.observed_at_ns:
        raise JournalError("Order has no matching tick/request.")
    request = _read(*row, _decode_request)
    if request != PaperRunner._request(tick, order_id):
        raise JournalError("Order quote request differs from its tick.")
    entry = type(order) is PaperEntryOrder
    expected_id = (
        "runner-entry-" + _hash(tick.candidate_case_id)
        if entry
        else "runner-exit-" + _hash(_encode(tick) + order.entry_order_id)
    )
    if order_id != expected_id or (entry and order.case_id != tick.candidate_case_id):
        raise JournalError("Order identity differs from its tick/case.")
    events = journal.order_events(order_id)
    if tuple(e.kind for e in events) not in (("REJECTED",), ("SUBMITTED", "FILL")):
        raise JournalError("Evaluation supports only atomic quote-fill/rejection lifecycles.")
    if any(e.observed_at_ns != tick.observed_at_ns for e in events):
        raise JournalError("Order event time differs from its tick.")
    slippage = Decimal(0)
    if events[-1].kind == "FILL":
        event = events[-1]
        expected = simulate_market_fill(
            side="BUY" if entry else "SELL",
            quantity_btc=order.quantity_btc,
            quote=MarketQuote(tick.bid_usdt, tick.ask_usdt, tick.quote_received_at_ns // 10**6),
            costs=config.costs,
        )
        if _quote_health(tick, config) != "healthy" or (
            event.executed_at_ns,
            event.quantity_btc,
            event.price_usdt,
            event.fee_usdt,
        ) != (
            tick.observed_at_ns,
            expected.quantity_btc,
            expected.price_usdt,
            expected.fee_usdt,
        ):
            raise JournalError("Fill disagrees with registered quote/cost model.")
        slippage = event.quantity_btc * (
            event.price_usdt - tick.ask_usdt if entry else tick.bid_usdt - event.price_usdt
        )
    return order, events, slippage


class _Marks:
    def __init__(self, initial_cash):
        self.peak = initial_cash
        self.max_drawdown = Decimal(0)
        self.max_drawdown_fraction = Decimal(0)
        self.points = []
        self.unvalued = 0
        self.last_known = None

    def sample(self, account, tick, healthy, stage):
        equity = (
            account.cash_usdt + account.position_btc * tick.bid_usdt
            if healthy or account.position_btc == 0
            else None
        )
        point = {
            "tick_id": tick.tick_id,
            "observed_at_ns": tick.observed_at_ns,
            "stage": stage,
            "equity_usdt": _number(equity),
        }
        self.points.append(point)
        if equity is None:
            self.unvalued += 1
        else:
            self.peak = max(self.peak, equity)
            drawdown = self.peak - equity
            self.max_drawdown = max(self.max_drawdown, drawdown)
            self.max_drawdown_fraction = max(self.max_drawdown_fraction, drawdown / self.peak)
            self.last_known = point
        return equity


def _trades(orders, events, account):
    """Closed-lot statistics only; open inventory is never counted as a winner."""
    fills = {e.order_id: e for e in events if e.kind == "FILL"}
    positions = {p.entry_order_id: p for p in account.positions}
    result = []
    for order in orders:
        if type(order) is not PaperEntryOrder or order.order_id not in fills:
            continue
        entry = fills[order.order_id]
        exits = [
            fills[o.order_id]
            for o in orders
            if type(o) is not PaperEntryOrder
            and o.entry_order_id == order.order_id
            and o.order_id in fills
        ]
        closed = positions[order.order_id].quantity_btc == 0
        pnl = (
            sum((e.quantity_btc * e.price_usdt - e.fee_usdt for e in exits), Decimal(0))
            - entry.quantity_btc * entry.price_usdt
            - entry.fee_usdt
            if closed
            else None
        )
        result.append(
            {
                "entry_order_id": order.order_id,
                "case_id": order.case_id,
                "status": "closed" if closed else "open",
                "opened_at_ns": entry.executed_at_ns,
                "closed_at_ns": max(e.executed_at_ns for e in exits) if closed else None,
                "quantity_btc": str(entry.quantity_btc),
                "remaining_btc": str(positions[order.order_id].quantity_btc),
                "net_realized_pnl_usdt": _number(pnl),
                "fees_usdt": str(entry.fee_usdt + sum((e.fee_usdt for e in exits), Decimal(0))),
            }
        )
    return result


def _evaluate_snapshot(journal, registration, replays, max_frames):
    count = journal._db.execute("SELECT count(*) FROM paper_runner_ticks").fetchone()[0]
    if not 1 <= count <= max_frames:
        raise JournalError(
            "Budget must cover every committed tick; empty journals cannot evaluate."
        )
    gateway = DurablePaperGateway(journal, registration.gateway)
    runner = PaperRunner(
        gateway,
        PaperRunnerConfig(
            registration.policy.maximum_trade_age_ns, registration.policy.maximum_spread_bps
        ),
    )
    checkpoint = gateway.risk_checkpoint()
    seed = journal.account_seed()
    frames = list(islice(chain.from_iterable(r.frames() for r in replays), count))
    if len(frames) != count or seed != PaperAccountSeed(
        registration.initial_cash_usdt, frames[0].tick.observed_at_ns
    ):
        raise JournalError("Committed ticks/account seed do not match the capture.")
    account = recover_account(seed, (), ())
    orders, events, case_ids, order_ids, case_hashes, tick_hashes = [], [], [], set(), [], []
    marks = _Marks(seed.initial_cash_usdt)
    exposure_ns, faults, previous_time = 0, 0, seed.initialized_at_ns
    slippage = Decimal(0)
    reasons = Counter()
    sessions = {
        r.source_session: {
            "source_session": r.source_session,
            "source_sha256": r.source_sha256,
            "frames_evaluated": 0,
            "session_consumed": False,
            "market_fault_frames": 0,
        }
        for r in replays
    }
    last_lines = {r.source_session: r.record_count for r in replays}
    rows = journal._db.execute(
        "SELECT tick_id, payload, sha256, result, result_sha256 "
        "FROM paper_runner_ticks ORDER BY sequence"
    ).fetchall()
    for frame, row in zip(frames, rows, strict=True):
        tick, result = runner._read_result(row[1:])
        expected = replace(frame.tick, candidate_case_id=_case_id(registration, frame.tick))
        if row[0] != tick.tick_id or tick != expected or tick.observed_at_ns < previous_time:
            raise JournalError("Committed tick sequence differs from the registered replay.")
        case = journal.get_case(tick.candidate_case_id)
        runner._validate_built_case(case, tick)
        _verify_replayed_case(case, registration, frame)
        case_ids.append(case.case_id)
        case_hashes.append(case.sha256)
        tick_hashes.append([row[2], row[4]])
        reasons[case.risk_reason] += 1
        health = _quote_health(tick, registration.gateway)
        if result.quote_health != health:
            raise JournalError("Recorded quote health differs from the replay.")
        faults += frame.status.startswith("resync_required:")
        session = sessions[tick.source_session]
        session["frames_evaluated"] += 1
        session["session_consumed"] = frame.line_number == last_lines[tick.source_session]
        session["market_fault_frames"] += frame.status.startswith("resync_required:")
        if account.position_btc:
            exposure_ns += tick.observed_at_ns - previous_time
        previous_time = tick.observed_at_ns
        marks.sample(account, tick, health == "healthy", "before_orders")
        new_ids = result.exit_order_ids + (
            (result.entry_order_id,) if result.entry_order_id else ()
        )
        for order_id in new_ids:
            if order_id in order_ids:
                raise JournalError("Order attributed to multiple ticks.")
            order, new_events, cost = _read_order(journal, tick, order_id, registration.gateway)
            if (type(order) is PaperEntryOrder) != (order_id == result.entry_order_id):
                raise JournalError("Tick result has an incorrect entry/exit binding.")
            orders.append(order)
            events.extend(new_events)
            order_ids.add(order_id)
            slippage += cost
        if new_ids:
            account = recover_account(seed, tuple(orders), tuple(events))
        terminal_equity = marks.sample(account, tick, health == "healthy", "after_orders")
    # No manual or hidden lifecycle may fall outside the reconstructed tick scope.
    if (
        set(case_ids) != {r[0] for r in journal._db.execute("SELECT case_id FROM cases")}
        or len(set(case_ids)) != count
        or order_ids != set(journal.order_ids())
        or order_ids
        != {r[0] for r in journal._db.execute("SELECT order_id FROM paper_gateway_requests")}
        or [e.event_id for e in events]
        != [
            r[0] for r in journal._db.execute("SELECT event_id FROM paper_events ORDER BY sequence")
        ]
        or account != journal.account_state()
    ):
        raise JournalError("Journal contains state outside the evaluated tick lifecycles.")
    complete = all(s["session_consumed"] for s in sessions.values())
    comparison = complete and not faults and not marks.unvalued and account.position_btc == 0
    duration = tick.observed_at_ns - seed.initialized_at_ns
    pnl = None if terminal_equity is None else terminal_equity - seed.initial_cash_usdt
    net_return = None if pnl is None else pnl / seed.initial_cash_usdt
    liquidation = None
    if terminal_equity is not None:
        fee = registration.gateway.costs.taker_fee_bps / Decimal(10000)
        slip = registration.gateway.costs.slippage_bps / Decimal(10000)
        liquidation = account.cash_usdt + account.position_btc * tick.bid_usdt * (1 - slip) * (
            1 - fee
        )
    trades = _trades(orders, events, account)
    closed_pnl = [Decimal(t["net_realized_pnl_usdt"]) for t in trades if t["status"] == "closed"]
    gross_notional = sum(
        (e.quantity_btc * e.price_usdt for e in events if e.kind == "FILL"), Decimal(0)
    )
    ledger_fingerprint = _hash(
        _json(
            {
                "seed": _hash(_encode(seed)),
                "checkpoint": _hash(_encode(checkpoint)),
                "ticks": tick_hashes,
                "cases": case_hashes,
                "orders": [_hash(_encode(o)) for o in orders],
                "events": [_hash(_encode(e)) for e in events],
            }
        )
    )
    return {
        "evaluation_version": EVALUATION_VERSION,
        "protocol": dict(PROTOCOL),
        "protocol_sha256": _hash(_json(dict(PROTOCOL))),
        "registration_sha256": registration.sha256,
        "source_session": replays[0].source_session if len(replays) == 1 else None,
        "source_sha256": replays[0].source_sha256 if len(replays) == 1 else None,
        "source_sessions": list(sessions.values()),
        "journal_run_id": journal.run_id,
        "ledger_snapshot_sha256": ledger_fingerprint,
        "frames_evaluated": count,
        "session_consumed": complete,
        "truncated": not complete,
        "market_fault_frames": faults,
        "started_at_ns": seed.initialized_at_ns,
        "ended_at_ns": tick.observed_at_ns,
        "kill_switch_active": checkpoint.kill_switch_active,
        "risk_checkpoint_observed_at_ns": checkpoint.observed_at_ns,
        "case_reason_counts": dict(reasons),
        "filled_entries": len(trades),
        "closed_trades": len(closed_pnl),
        "open_trades": len(trades) - len(closed_pnl),
        "rejected_orders": sum(e.kind == "REJECTED" for e in events),
        "winning_closed_trades": sum(p > 0 for p in closed_pnl),
        "losing_closed_trades": sum(p < 0 for p in closed_pnl),
        "breakeven_closed_trades": sum(p == 0 for p in closed_pnl),
        "closed_trade_win_fraction": _number(
            Decimal(sum(p > 0 for p in closed_pnl)) / len(closed_pnl) if closed_pnl else None
        ),
        "trades": trades,
        "initial_cash_usdt": str(seed.initial_cash_usdt),
        "cash_usdt": str(account.cash_usdt),
        "position_btc": str(account.position_btc),
        "cost_basis_usdt": str(account.cost_basis_usdt),
        "realized_pnl_usdt": str(account.realized_pnl_usdt),
        "unrealized_pnl_usdt": _number(
            terminal_equity - account.cash_usdt - account.cost_basis_usdt
            if terminal_equity is not None
            else None
        ),
        "fees_paid_usdt": str(account.fees_usdt),
        "slippage_embedded_usdt": str(slippage),
        "gross_filled_notional_usdt": str(gross_notional),
        "turnover_over_initial_cash": str(gross_notional / seed.initial_cash_usdt),
        "exposure_ns": exposure_ns,
        "observed_duration_ns": duration,
        "time_in_position_fraction": _number(Decimal(exposure_ns) / duration if duration else None),
        "terminal_equity_usdt": _number(terminal_equity),
        "net_pnl_usdt": _number(pnl),
        "net_return_fraction": _number(net_return),
        "hypothetical_terminal_exit_equity_usdt": _number(liquidation),
        "sampled_max_drawdown_usdt": str(marks.max_drawdown),
        "sampled_max_drawdown_fraction": str(marks.max_drawdown_fraction),
        "drawdown_path_fully_valued": marks.unvalued == 0,
        "unvalued_equity_samples": marks.unvalued,
        "equity_curve": marks.points,
        "last_valued_sample": marks.last_known,
        "cash_control": {"terminal_equity_usdt": str(seed.initial_cash_usdt), "net_pnl_usdt": "0"},
        "full_session_flat_comparison_available": comparison,
        "excess_return_vs_cash_fraction": _number(net_return if comparison else None),
        "promotion_allowed": False,
        "live_trading_available": False,
        "limitations": (
            "Sampled bid marks, not continuous equity; unknown marks are not forward-filled. "
            "Fees/slippage already reduce cash/PnL and must not be subtracted again. "
            "Hypothetical terminal exit is a separate cost scenario, never a booked trade. "
            "Quote-only full fills; no queue, impact, latency or partial-fill realism. "
            "Cash control is arithmetic, not an independent strategy trial or evidence of an edge."
        ),
    }


def _with_registered_paper_snapshot(
    *,
    registration_path: Path,
    capture_path: Path,
    source_session: str,
    journal_path: Path,
    max_frames: int,
    transform,
) -> dict:
    """Internal read-only snapshot shared by evaluation and deterministic review."""
    if type(max_frames) is not int or not 1 <= max_frames <= 10_000:
        raise ValueError("Frame budget must be an integer in [1, 10000].")
    registration = load_registration(registration_path)
    source = registration.research_source(source_session)  # Before capture or journal access.
    replay = CaptureReplay.from_path(
        capture_path,
        expected_sha256=source.source_sha256,
        source_session=source_session,
        config=registration.replay,
    )
    framing = replay._framing()
    if (framing[0]["started_at_ns"], framing[-1]["ended_at_ns"]) != (
        source.started_at_ns,
        source.ended_at_ns,
    ):
        raise ValueError("Capture times differ from registration.")
    with (
        TradeJournal(
            journal_path,
            run_id=paper_run_id(registration, source_session),
            mode="paper",
            read_only=True,
        ) as journal,
        localcontext(DECIMAL_CONTEXT),
    ):
        journal._db.execute("BEGIN")
        try:
            report = _evaluate_snapshot(journal, registration, (replay,), max_frames)
            result = transform(journal, registration, report)
            if (
                registration.implementation_sha256 != _implementation_hash()
                or registration.environment_json != _environment()
            ):
                raise ValueError("Source/environment changed during evaluation.")
            return result
        finally:
            journal._db.execute("ROLLBACK")


def evaluate_registered_paper(
    *,
    registration_path: Path,
    capture_path: Path,
    source_session: str,
    journal_path: Path,
    max_frames: int,
) -> dict:
    """Read one consistent snapshot; refuse subset selection or any execution mutation."""
    return _with_registered_paper_snapshot(
        registration_path=registration_path,
        capture_path=capture_path,
        source_session=source_session,
        journal_path=journal_path,
        max_frames=max_frames,
        transform=lambda journal, registration, report: report,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--source-session", required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, required=True)
    args = parser.parse_args()
    report = evaluate_registered_paper(
        registration_path=args.registration,
        capture_path=args.capture,
        source_session=args.source_session,
        journal_path=args.journal,
        max_frames=args.max_frames,
    )
    print(json.dumps(report, sort_keys=True))
    if not report["full_session_flat_comparison_available"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
