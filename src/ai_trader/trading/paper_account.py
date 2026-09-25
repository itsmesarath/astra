"""Deterministic, funded, flat-start BTCUSDT paper-account reconstruction.

Arrival/commit order is authoritative, not backdated execution time. Fees are USDT
only. Entry fees enter cost basis; exit fees reduce realized proceeds exactly once.
No mark price, daily loss reset, external balance reconciliation or broker mutation.
"""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from ai_trader.trading.paper_lifecycle import (
    PaperEntryOrder,
    PaperExitOrder,
    PaperOrderEvent,
    _money,
    _timestamp,
    reconstruct,
)


@dataclass(frozen=True, slots=True)
class PaperAccountSeed:
    initial_cash_usdt: Decimal
    initialized_at_ns: int

    def __post_init__(self):
        _money(self.initial_cash_usdt)
        _timestamp(self.initialized_at_ns)


@dataclass(frozen=True, slots=True)
class PaperPosition:
    entry_order_id: str
    quantity_btc: Decimal
    cost_basis_usdt: Decimal
    reserved_exit_btc: Decimal


@dataclass(frozen=True, slots=True)
class PaperAccountState:
    initial_cash_usdt: Decimal
    cash_usdt: Decimal
    position_btc: Decimal
    cost_basis_usdt: Decimal
    realized_pnl_usdt: Decimal
    fees_usdt: Decimal
    positions: tuple[PaperPosition, ...]
    unresolved_order_ids: tuple[str, ...]
    last_observed_at_ns: int


def recover_account(
    seed: PaperAccountSeed,
    orders: tuple[PaperEntryOrder | PaperExitOrder, ...],
    events: tuple[PaperOrderEvent, ...],
) -> PaperAccountState:
    """Replay one consistent journal snapshot; invalid inventory/cash fails closed."""
    by_id = {order.order_id: order for order in orders}
    if len(by_id) != len(orders):
        raise ValueError("Duplicate account order.")
    lots = {o.order_id: [Decimal(0), Decimal(0)] for o in orders if type(o) is PaperEntryOrder}
    histories = {order_id: [] for order_id in by_id}
    cash, fees = seed.initial_cash_usdt, Decimal(0)
    last = seed.initialized_at_ns
    event_ids, fill_ids = set(), set()
    with localcontext() as context:
        context.prec = 100
        for order in orders:
            if order.requested_at_ns < seed.initialized_at_ns:
                raise ValueError("Order predates account seed.")
            if type(order) is PaperExitOrder and order.entry_order_id not in lots:
                raise ValueError("Exit does not reference an entry order.")
        for event in events:
            if event.order_id not in by_id or event.observed_at_ns < last:
                raise ValueError("Missing order or regressed account observation time.")
            if event.event_id in event_ids or (event.fill_id and event.fill_id in fill_ids):
                raise ValueError("Duplicate account event/fill.")
            event_ids.add(event.event_id)
            if event.fill_id:
                fill_ids.add(event.fill_id)
            last = event.observed_at_ns
            order = by_id[event.order_id]
            histories[event.order_id].append(event)
            if event.kind != "FILL":
                continue
            notional = event.quantity_btc * event.price_usdt
            fees += event.fee_usdt
            if type(order) is PaperEntryOrder:
                cash -= notional + event.fee_usdt
                lot = lots[order.order_id]
                lot[0] += event.quantity_btc
                lot[1] += notional + event.fee_usdt
            else:
                lot = lots[order.entry_order_id]
                if event.quantity_btc > lot[0]:
                    raise ValueError("Exit would short its entry inventory.")
                # Full close consumes the exact residual, avoiding stranded rounding dust.
                cost = (
                    lot[1]
                    if event.quantity_btc == lot[0]
                    else (lot[1] * event.quantity_btc / lot[0])
                )
                proceeds = notional - event.fee_usdt
                cash += proceeds
                lot[0] -= event.quantity_btc
                lot[1] -= cost
            if cash < 0:
                raise ValueError("Paper fill would overdraw cash.")
        reserved = dict.fromkeys(lots, Decimal(0))
        unresolved = []
        for order in orders:
            state = reconstruct(order, tuple(histories[order.order_id]))
            if state.status not in ("FILLED", "REJECTED", "CANCEL_CONFIRMED"):
                unresolved.append(order.order_id)
                if type(order) is PaperExitOrder:
                    reserved[order.entry_order_id] += order.quantity_btc - state.filled_quantity_btc
        positions = tuple(
            PaperPosition(entry_id, *lots[entry_id], reserved[entry_id])
            for entry_id in sorted(lots)
        )
        if any(p.reserved_exit_btc > p.quantity_btc for p in positions):
            raise ValueError("Exit reservations exceed remaining entry inventory.")
        total_cost = sum((p.cost_basis_usdt for p in positions), Decimal(0))
        # Conservation form avoids accumulating cost-allocation rounding residuals
        # in realized PnL, and makes a fully closed run equal cash minus funding.
        realized = cash + total_cost - seed.initial_cash_usdt
        return PaperAccountState(
            seed.initial_cash_usdt,
            cash,
            sum((p.quantity_btc for p in positions), Decimal(0)),
            total_cost,
            realized,
            fees,
            positions,
            tuple(sorted(unresolved)),
            last,
        )
