"""Mode-independent Spot execution contract and an offline paper adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from threading import Lock
from typing import Literal, Protocol, runtime_checkable

from ai_trader.trading.execution import MarketQuote, simulate_market_fill
from ai_trader.trading.paper_broker import PaperBroker


class ExecutionMode(StrEnum):
    PAPER = "paper"
    SPOT_TESTNET = "spot_testnet"
    SPOT_LIVE = "spot_live"


class ExecutionStatus(StrEnum):
    """An acknowledgement or timeout must never be mistaken for a fill."""

    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELED = "canceled"
    UNKNOWN = "unknown"
    NOOP = "noop"


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """One immutable strategy intent, independent of its broker implementation."""

    request_id: str
    intent: Literal["LONG", "FLAT"]
    entry_quantity_btc: Decimal
    quote: MarketQuote
    symbol: str = "BTCUSDT"

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,36}", self.request_id
        ):
            raise ValueError(
                "Request ID must contain 1-36 letters, digits, underscores or hyphens."
            )
        if self.intent not in ("LONG", "FLAT") or self.symbol != "BTCUSDT":
            raise ValueError("Execution supports BTCUSDT Spot LONG/FLAT only.")
        values = (self.entry_quantity_btc, self.quote.best_bid_usdt, self.quote.best_ask_usdt)
        if any(not isinstance(v, Decimal) or not v.is_finite() or v <= 0 for v in values):
            raise ValueError("Quantity and quote prices must be finite positive Decimals.")
        if type(self.quote.event_time_ms) is not int or self.quote.event_time_ms < 0:
            raise ValueError("Quote time must be a nonnegative integer.")


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    """Latest cumulative execution information, not a command to book another fill.

    Future adapters must reconcile UNKNOWN/PARTIALLY_FILLED/SUBMITTED states.
    Consumers must not apply cumulative quantities again when polling or retrying.
    """

    request_id: str
    mode: ExecutionMode
    status: ExecutionStatus
    reason: str
    filled_quantity_btc: Decimal = Decimal("0")
    average_fill_price_usdt: Decimal | None = None
    fill_side: Literal["BUY", "SELL"] | None = None
    # Future live adapters must account for commission in assets other than USDT.
    fee_usdt: Decimal | None = None


@runtime_checkable
class ExecutionGateway(Protocol):
    """Strategies depend on this contract, never on exchange credentials or HTTP."""

    @property
    def mode(self) -> ExecutionMode: ...

    def submit(self, request: ExecutionRequest) -> ExecutionReceipt: ...

    def get_receipt(self, request_id: str) -> ExecutionReceipt | None: ...

    def set_kill_switch(self, active: bool) -> None: ...


@dataclass(slots=True)
class PaperExecutionGateway:
    """Spot-only wrapper; retries are idempotent within this process instance.

    The cache is not restart-safe. It is never reused as live order reconciliation.
    Historical simulators can keep using PaperBroker directly; this adapter is
    the execution boundary for the future online market-data runner.
    """

    _broker: PaperBroker
    _requests: dict[str, ExecutionRequest] = field(default_factory=dict, init=False)
    _receipts: dict[str, ExecutionReceipt] = field(default_factory=dict, init=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    @property
    def mode(self) -> ExecutionMode:
        return ExecutionMode.PAPER

    def set_kill_switch(self, active: bool) -> None:
        with self._lock:
            self._broker.set_kill_switch(active)

    def get_receipt(self, request_id: str) -> ExecutionReceipt | None:
        with self._lock:
            return self._receipts.get(request_id)

    def submit(self, request: ExecutionRequest) -> ExecutionReceipt:
        with self._lock:
            previous = self._requests.get(request.request_id)
            if previous is not None:
                if previous != request:
                    raise ValueError("Request ID was already used for a different intent.")
                return self._receipts[request.request_id]
            if len(self._requests) >= 10_000:
                raise RuntimeError(
                    "Paper request cache is full; archive the run before restarting."
                )

            reason = None
            if self._broker.portfolio.position_btc < 0:
                reason = "spot_short_position_not_supported"
            elif request.intent == "LONG" and self._broker.portfolio.position_btc == 0:
                fill = simulate_market_fill(
                    side="BUY",
                    quantity_btc=request.entry_quantity_btc,
                    quote=request.quote,
                    costs=self._broker.execution_costs,
                )
                if fill.notional_usdt + fill.fee_usdt > self._broker.portfolio.cash_usdt:
                    reason = "insufficient_spot_cash"

            if reason is not None:
                receipt = ExecutionReceipt(
                    request.request_id,
                    self.mode,
                    ExecutionStatus.REJECTED,
                    reason,
                )
            else:
                result = self._broker.process_intent(
                    intent=request.intent,
                    entry_quantity_btc=request.entry_quantity_btc,
                    quote=request.quote,
                )
                fill = result.fill
                status = ExecutionStatus.FILLED if result.executed else ExecutionStatus.NOOP
                if result.risk_decision is not None and not result.risk_decision.approved:
                    status = ExecutionStatus.REJECTED
                receipt = ExecutionReceipt(
                    request.request_id,
                    self.mode,
                    status,
                    result.reason,
                    filled_quantity_btc=fill.quantity_btc if fill else Decimal("0"),
                    average_fill_price_usdt=fill.price_usdt if fill else None,
                    fill_side=fill.side if fill else None,
                    fee_usdt=fill.fee_usdt if fill else None,
                )
            self._requests[request.request_id] = request
            self._receipts[request.request_id] = receipt
            return receipt
