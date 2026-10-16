"""Offline paper portfolio with explicit fills, fees, and PnL."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

FillSide = Literal["BUY", "SELL"]


@dataclass(frozen=True, slots=True)
class PaperFill:
    """One simulated execution."""

    side: FillSide
    quantity_btc: Decimal
    price_usdt: Decimal
    fee_usdt: Decimal
    event_time_ms: int

    def __post_init__(self) -> None:
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("Fill side must be BUY or SELL.")
        if self.quantity_btc <= 0:
            raise ValueError("Fill quantity must be greater than zero.")
        if self.price_usdt <= 0:
            raise ValueError("Fill price must be greater than zero.")
        if self.fee_usdt < 0:
            raise ValueError("Fill fee cannot be negative.")
        if self.event_time_ms < 0:
            raise ValueError("Fill event time cannot be negative.")

    @property
    def signed_quantity_btc(self) -> Decimal:
        """Return positive BUY or negative SELL quantity."""
        return self.quantity_btc if self.side == "BUY" else -self.quantity_btc

    @property
    def notional_usdt(self) -> Decimal:
        """Return execution notional."""
        return self.quantity_btc * self.price_usdt


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """Marked-to-market paper portfolio state."""

    mark_price_usdt: Decimal
    cash_usdt: Decimal
    position_btc: Decimal
    average_entry_price_usdt: Decimal
    gross_realized_pnl_usdt: Decimal
    unrealized_pnl_usdt: Decimal
    fees_paid_usdt: Decimal
    net_realized_pnl_usdt: Decimal
    equity_usdt: Decimal
    peak_equity_usdt: Decimal
    drawdown_usdt: Decimal


@dataclass(slots=True)
class PaperPortfolio:
    """Mutable single-symbol paper portfolio."""

    initial_cash_usdt: Decimal
    cash_usdt: Decimal
    position_btc: Decimal
    average_entry_price_usdt: Decimal
    gross_realized_pnl_usdt: Decimal
    fees_paid_usdt: Decimal
    peak_equity_usdt: Decimal
    fill_count: int = 0

    @classmethod
    def create(
        cls,
        initial_cash_usdt: Decimal,
    ) -> PaperPortfolio:
        """Create an empty paper portfolio."""
        if initial_cash_usdt <= 0:
            raise ValueError("Initial cash must be greater than zero.")

        return cls(
            initial_cash_usdt=initial_cash_usdt,
            cash_usdt=initial_cash_usdt,
            position_btc=Decimal("0"),
            average_entry_price_usdt=Decimal("0"),
            gross_realized_pnl_usdt=Decimal("0"),
            fees_paid_usdt=Decimal("0"),
            peak_equity_usdt=initial_cash_usdt,
        )

    @property
    def net_realized_pnl_usdt(self) -> Decimal:
        """Return gross realized PnL minus all paid fees."""
        return self.gross_realized_pnl_usdt - self.fees_paid_usdt

    def apply_fill(self, fill: PaperFill) -> None:
        """Apply one fill while rejecting position reversals."""
        old_position = self.position_btc
        signed_quantity = fill.signed_quantity_btc
        new_position = old_position + signed_quantity

        flips_position = (
            old_position != 0 and new_position != 0 and (old_position > 0) != (new_position > 0)
        )
        if flips_position:
            raise ValueError("One fill cannot reverse the paper position.")

        same_direction_or_opening = old_position == 0 or (old_position > 0) == (signed_quantity > 0)

        if same_direction_or_opening:
            old_cost = abs(old_position) * self.average_entry_price_usdt
            added_cost = fill.quantity_btc * fill.price_usdt
            self.average_entry_price_usdt = (old_cost + added_cost) / abs(new_position)
        else:
            closed_quantity = min(
                abs(old_position),
                fill.quantity_btc,
            )

            if old_position > 0:
                realized_change = (
                    fill.price_usdt - self.average_entry_price_usdt
                ) * closed_quantity
            else:
                realized_change = (
                    self.average_entry_price_usdt - fill.price_usdt
                ) * closed_quantity

            self.gross_realized_pnl_usdt += realized_change

            if new_position == 0:
                self.average_entry_price_usdt = Decimal("0")

        if fill.side == "BUY":
            self.cash_usdt -= fill.notional_usdt + fill.fee_usdt
        else:
            self.cash_usdt += fill.notional_usdt - fill.fee_usdt

        self.position_btc = new_position
        self.fees_paid_usdt += fill.fee_usdt
        self.fill_count += 1

    def unrealized_pnl(
        self,
        mark_price_usdt: Decimal,
    ) -> Decimal:
        """Calculate unrealized PnL at one mark price."""
        if mark_price_usdt <= 0:
            raise ValueError("Mark price must be greater than zero.")
        if self.position_btc > 0:
            return (mark_price_usdt - self.average_entry_price_usdt) * self.position_btc
        if self.position_btc < 0:
            return (self.average_entry_price_usdt - mark_price_usdt) * abs(self.position_btc)
        return Decimal("0")

    def mark_to_market(
        self,
        mark_price_usdt: Decimal,
    ) -> PortfolioSnapshot:
        """Create a reconciled snapshot and update peak equity."""
        unrealized = self.unrealized_pnl(mark_price_usdt)
        equity = self.cash_usdt + self.position_btc * mark_price_usdt
        reconciled_equity = (
            self.initial_cash_usdt + self.gross_realized_pnl_usdt + unrealized - self.fees_paid_usdt
        )

        if equity != reconciled_equity:
            raise RuntimeError("Paper portfolio equity failed reconciliation.")

        if equity > self.peak_equity_usdt:
            self.peak_equity_usdt = equity

        return PortfolioSnapshot(
            mark_price_usdt=mark_price_usdt,
            cash_usdt=self.cash_usdt,
            position_btc=self.position_btc,
            average_entry_price_usdt=(self.average_entry_price_usdt),
            gross_realized_pnl_usdt=(self.gross_realized_pnl_usdt),
            unrealized_pnl_usdt=unrealized,
            fees_paid_usdt=self.fees_paid_usdt,
            net_realized_pnl_usdt=(self.net_realized_pnl_usdt),
            equity_usdt=equity,
            peak_equity_usdt=self.peak_equity_usdt,
            drawdown_usdt=self.peak_equity_usdt - equity,
        )
