"""Paper order contracts; records are not execution authority."""

from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Literal


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise ValueError("Expected nonempty text of at most 2048 characters.")


def _timestamp(value):
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ValueError("Expected a nonnegative signed-64-bit nanosecond timestamp.")


def _money(value, *, zero=False):
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("Expected finite Decimal.")
    if value < 0 or (not zero and value == 0):
        raise ValueError("Invalid amount sign.")
    if len(value.as_tuple().digits) > 28 or not -18 <= value.as_tuple().exponent <= 18:
        raise ValueError("Amount exceeds ledger precision bounds.")


@dataclass(frozen=True, slots=True)
class PaperEntryOrder:
    order_id: str
    case_id: str
    case_sha256: str
    quantity_btc: Decimal
    requested_at_ns: int

    def __post_init__(self):
        _text(self.order_id)
        _text(self.case_id)
        if (
            not isinstance(self.case_sha256, str)
            or len(self.case_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.case_sha256)
        ):
            raise ValueError("Expected lowercase SHA256.")
        _money(self.quantity_btc)
        _timestamp(self.requested_at_ns)


@dataclass(frozen=True, slots=True)
class PaperExitOrder:
    """Reduce one entry's filled inventory, independently of entry/analyst gates."""

    order_id: str
    entry_order_id: str
    quantity_btc: Decimal
    requested_at_ns: int
    reason: str

    def __post_init__(self):
        for value in (self.order_id, self.entry_order_id, self.reason):
            _text(value)
        if self.order_id == self.entry_order_id:
            raise ValueError("Exit cannot reference itself.")
        _money(self.quantity_btc)
        _timestamp(self.requested_at_ns)


@dataclass(frozen=True, slots=True)
class PaperOrderEvent:
    event_id: str
    order_id: str
    kind: Literal["SUBMITTED", "UNKNOWN", "CANCELED", "CANCEL_CONFIRMED", "REJECTED", "FILL"]
    observed_at_ns: int
    reason: str
    fill_id: str | None = None
    executed_at_ns: int | None = None
    quantity_btc: Decimal | None = None
    price_usdt: Decimal | None = None
    fee_usdt: Decimal | None = None

    def __post_init__(self):
        for value in (self.event_id, self.order_id, self.reason):
            _text(value)
        _timestamp(self.observed_at_ns)
        if self.kind not in (
            "SUBMITTED",
            "UNKNOWN",
            "CANCELED",
            "CANCEL_CONFIRMED",
            "REJECTED",
            "FILL",
        ):
            raise ValueError("Unknown paper event kind.")
        if self.kind == "FILL":
            _text(self.fill_id)
            _timestamp(self.executed_at_ns)
            if self.executed_at_ns > self.observed_at_ns:
                raise ValueError("Fill cannot be observed before execution.")
            _money(self.quantity_btc)
            _money(self.price_usdt)
            _money(self.fee_usdt, zero=True)
        elif any(
            value is not None
            for value in (
                self.fill_id,
                self.executed_at_ns,
                self.quantity_btc,
                self.price_usdt,
                self.fee_usdt,
            )
        ):
            raise ValueError("Only FILL events may contain incremental fill data.")


@dataclass(frozen=True, slots=True)
class PaperOrderState:
    order: PaperEntryOrder | PaperExitOrder
    status: str
    filled_quantity_btc: Decimal
    fill_notional_usdt: Decimal
    fee_usdt: Decimal
    last_observed_at_ns: int


def reconstruct(
    order: PaperEntryOrder | PaperExitOrder, events: tuple[PaperOrderEvent, ...]
) -> PaperOrderState:
    """Replay append order. UNKNOWN never grants permission to resubmit.

    SUBMITTED after UNKNOWN records explicit reconciliation, not a new submission.
    Late fills after CANCELED remain canceled for the unfilled remainder, or become
    FILLED at full quantity. A partial fill alone cannot resolve UNKNOWN.
    """
    status, quantity, notional, fees = "PREPARED", Decimal(0), Decimal(0), Decimal(0)
    last = order.requested_at_ns
    event_ids, fill_ids = set(), set()
    with localcontext() as context:
        context.prec = 100
        for event in events:
            if event.order_id != order.order_id or event.observed_at_ns < last:
                raise ValueError("Wrong order or nonmonotonic observation time.")
            if event.event_id in event_ids or (event.fill_id and event.fill_id in fill_ids):
                raise ValueError("Duplicate event/fill in replay.")
            event_ids.add(event.event_id)
            last = event.observed_at_ns
            if event.kind == "FILL":
                if status not in ("SUBMITTED", "PARTIALLY_FILLED", "UNKNOWN", "CANCELED"):
                    raise ValueError("Fill requires an outstanding or canceled order.")
                if event.executed_at_ns < order.requested_at_ns:
                    raise ValueError("Fill predates request.")
                fill_ids.add(event.fill_id)
                quantity += event.quantity_btc
                notional += event.quantity_btc * event.price_usdt
                fees += event.fee_usdt
                if quantity > order.quantity_btc:
                    raise ValueError("Fill exceeds requested quantity.")
                if quantity == order.quantity_btc:
                    status = "FILLED"
                elif status not in ("UNKNOWN", "CANCELED"):
                    status = "PARTIALLY_FILLED"
            else:
                allowed = {
                    "SUBMITTED": ("PREPARED", "UNKNOWN"),
                    "UNKNOWN": ("PREPARED", "SUBMITTED", "PARTIALLY_FILLED", "CANCELED"),
                    "CANCELED": ("SUBMITTED", "PARTIALLY_FILLED", "UNKNOWN"),
                    "CANCEL_CONFIRMED": ("CANCELED", "UNKNOWN"),
                    "REJECTED": ("PREPARED", "SUBMITTED", "UNKNOWN"),
                }
                if status not in allowed[event.kind] or (event.kind == "REJECTED" and quantity):
                    raise ValueError(f"Invalid order transition: {status} -> {event.kind}.")
                status = event.kind
                if status == "SUBMITTED" and quantity:
                    status = "PARTIALLY_FILLED"
    return PaperOrderState(order, status, quantity, notional, fees, last)
