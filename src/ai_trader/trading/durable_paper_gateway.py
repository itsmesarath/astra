"""Opt-in atomic quote simulator backed by the journal, never an exchange adapter.

Uses prepared case-bound orders, not the legacy intent-only gateway protocol.
No mutable broker balance is maintained: the journal is the accounting authority.
"""

from contextlib import contextmanager
from dataclasses import dataclass, fields, replace
from decimal import Decimal, localcontext

from ai_trader.risk.engine import OrderIntent, PortfolioRiskState, RiskLimits, evaluate_order
from ai_trader.trading.execution import ExecutionCosts, MarketQuote, simulate_market_fill
from ai_trader.trading.gateway import ExecutionMode, ExecutionReceipt, ExecutionStatus
from ai_trader.trading.paper_lifecycle import PaperEntryOrder, PaperOrderEvent, _money, _timestamp
from ai_trader.trading.trade_journal import (
    JournalConflict,
    JournalError,
    TradeJournal,
    _decimal,
    _encode,
    _hash,
    _identifier,
    _read,
    _shape,
)

DAY_NS = 86_400_000_000_000


@dataclass(frozen=True, slots=True)
class PaperGatewayConfig:
    limits: RiskLimits
    costs: ExecutionCosts
    max_quote_age_ns: int

    def __post_init__(self):
        if type(self.limits) is not RiskLimits or type(self.costs) is not ExecutionCosts:
            raise ValueError("Typed limits and costs required.")
        for field in fields(self.limits):
            _money(getattr(self.limits, field.name))
        for field in fields(self.costs):
            _money(getattr(self.costs, field.name), zero=True)
        _timestamp(self.max_quote_age_ns)
        if self.max_quote_age_ns == 0:
            raise ValueError("Quote age limit must be positive.")

    @property
    def risk_config_sha256(self):
        return _hash(_encode(self.limits))


@dataclass(frozen=True, slots=True)
class PaperQuoteRequest:
    order_id: str
    bid_usdt: Decimal
    ask_usdt: Decimal
    quote_at_ns: int
    observed_at_ns: int

    def __post_init__(self):
        _identifier(self.order_id)
        _money(self.bid_usdt)
        _money(self.ask_usdt)
        _timestamp(self.quote_at_ns)
        _timestamp(self.observed_at_ns)
        if self.bid_usdt >= self.ask_usdt or self.quote_at_ns > self.observed_at_ns:
            raise ValueError("Crossed quote or future quote timestamp.")


@dataclass(frozen=True, slots=True)
class PaperRiskCheckpoint:
    observed_at_ns: int
    peak_equity_usdt: Decimal
    utc_day: int
    day_start_realized_usdt: Decimal
    cumulative_realized_usdt: Decimal
    last_event_sequence: int
    kill_switch_active: bool

    def __post_init__(self):
        _timestamp(self.observed_at_ns)
        if type(self.utc_day) is not int or self.utc_day != self.observed_at_ns // DAY_NS:
            raise ValueError("Checkpoint day does not match its observation time.")
        if type(self.last_event_sequence) is not int or self.last_event_sequence < 0:
            raise ValueError("Invalid event cursor.")
        if type(self.kill_switch_active) is not bool:
            raise ValueError("Kill switch must be boolean.")
        for value in (
            self.peak_equity_usdt,
            self.day_start_realized_usdt,
            self.cumulative_realized_usdt,
        ):
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError("Checkpoint amounts must be finite Decimal.")
        if self.peak_equity_usdt <= 0:
            raise ValueError("Peak equity must be positive.")


def _decode_config(value):
    value = _shape(value, PaperGatewayConfig)
    for name, cls in (("limits", RiskLimits), ("costs", ExecutionCosts)):
        value[name] = cls(**{k: _decimal(v) for k, v in _shape(value[name], cls).items()})
    return PaperGatewayConfig(**value)


def _decode_request(value):
    value = _shape(value, PaperQuoteRequest)
    for key in ("bid_usdt", "ask_usdt"):
        value[key] = _decimal(value[key])
    return PaperQuoteRequest(**value)


def _decode_checkpoint(value):
    value = _shape(value, PaperRiskCheckpoint)
    for key in ("peak_equity_usdt", "day_start_realized_usdt", "cumulative_realized_usdt"):
        value[key] = _decimal(value[key])
    return PaperRiskCheckpoint(**value)


class DurablePaperGateway:
    """One connection per thread. Initialize explicitly once; reopening never resets risk."""

    mode = ExecutionMode.PAPER

    def __init__(self, journal: TradeJournal, config: PaperGatewayConfig):
        self.journal = journal
        self.config = config
        journal._account_schema()
        if journal._db.execute("PRAGMA user_version").fetchone()[0] not in (4, 5, 6):
            raise JournalError("Explicit schema upgrade required for durable gateway.")
        with self._snapshot():
            row = journal._db.execute(
                "SELECT payload, sha256 FROM paper_gateway_config WHERE singleton=1"
            ).fetchone()
            if row is None:
                raise JournalError("Durable gateway must be initialized explicitly.")
            stored = _read(*row, _decode_config)
            if type(config) is not PaperGatewayConfig or _encode(stored) != _encode(config):
                raise JournalConflict("Gateway config differs from the recorded run configuration.")
            self.risk_checkpoint()

    @classmethod
    def initialize(cls, journal: TradeJournal, config: PaperGatewayConfig):
        journal._account_schema()
        if journal._db.execute("PRAGMA user_version").fetchone()[0] not in (4, 5, 6):
            raise JournalError("Explicit schema upgrade required for durable gateway.")
        if type(config) is not PaperGatewayConfig:
            raise JournalError("Expected typed gateway configuration.")
        payload = _encode(config)
        _read(payload, _hash(payload), _decode_config)
        with journal._write():
            if journal._db.execute("SELECT 1 FROM paper_gateway_config").fetchone() is None:
                state = journal.account_state()
                if journal.order_ids():
                    raise JournalError("Initialize gateway before preparing any orders.")
                journal._db.execute(
                    "INSERT INTO paper_gateway_config VALUES (1, ?, ?)", (payload, _hash(payload))
                )
                checkpoint = PaperRiskCheckpoint(
                    state.last_observed_at_ns,
                    state.initial_cash_usdt,
                    state.last_observed_at_ns // DAY_NS,
                    Decimal(0),
                    Decimal(0),
                    0,
                    False,
                )
                cls._save_checkpoint(journal, checkpoint)
            # Validate an existing binding before committing initialization/retry.
            cls(journal, config)
        return cls(journal, config)

    @contextmanager
    def _snapshot(self):
        owns = not self.journal._db.in_transaction
        if owns:
            self.journal._db.execute("BEGIN")
        try:
            yield
        finally:
            if owns:
                self.journal._db.execute("ROLLBACK")

    @staticmethod
    def _save_checkpoint(journal, checkpoint):
        payload = _encode(checkpoint)
        _read(payload, _hash(payload), _decode_checkpoint)
        journal._db.execute(
            "INSERT INTO paper_risk_checkpoints (payload, sha256) VALUES (?, ?)",
            (payload, _hash(payload)),
        )

    def _event_sequence(self):
        return self.journal._db.execute(
            "SELECT COALESCE(MAX(sequence), 0) FROM paper_events"
        ).fetchone()[0]

    def risk_checkpoint(self):
        with self._snapshot():
            config_row = self.journal._db.execute(
                "SELECT payload, sha256 FROM paper_gateway_config WHERE singleton=1"
            ).fetchone()
            if config_row is None:
                raise JournalError("Missing durable gateway configuration.")
            stored_config = _read(*config_row, _decode_config)
            if _encode(stored_config) != _encode(self.config):
                raise JournalConflict("Gateway configuration changed during the run.")
            row = self.journal._db.execute(
                "SELECT payload, sha256 FROM paper_risk_checkpoints ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            if row is None:
                raise JournalError("Missing durable risk checkpoint.")
            checkpoint = _read(*row, _decode_checkpoint)
            state = self.journal.account_state()
            if (
                checkpoint.last_event_sequence != self._event_sequence()
                or checkpoint.cumulative_realized_usdt != state.realized_pnl_usdt
                or checkpoint.observed_at_ns < state.last_observed_at_ns
            ):
                raise JournalError(
                    "Uncheckpointed ledger events; explicit reconciliation required."
                )
            return checkpoint

    def set_kill_switch(self, active: bool, *, observed_at_ns: int):
        if type(active) is not bool:
            raise ValueError("Kill switch must be boolean.")
        _timestamp(observed_at_ns)
        with self.journal._write():
            previous = self.risk_checkpoint()
            updated = self._advance(previous, observed_at_ns)
            self._save_checkpoint(self.journal, replace(updated, kill_switch_active=active))

    def heartbeat(self, *, observed_at_ns: int):
        """Advance durable risk time without marking an untrusted/stale market price."""
        _timestamp(observed_at_ns)
        with self.journal._write():
            updated = self._advance(self.risk_checkpoint(), observed_at_ns)
            self._save_checkpoint(self.journal, updated)
            return updated

    def mark_quote(self, *, bid_usdt, ask_usdt, quote_at_ns, observed_at_ns):
        """Sample a fresh quote without an order; caller must also verify book health."""
        quote = PaperQuoteRequest("risk-mark", bid_usdt, ask_usdt, quote_at_ns, observed_at_ns)
        if observed_at_ns - quote_at_ns > self.config.max_quote_age_ns:
            raise JournalError("Cannot mark stale quote.")
        with self.journal._write(), localcontext() as context:
            context.prec = 100
            updated = self._advance(self.risk_checkpoint(), observed_at_ns)
            account = self.journal.account_state()
            equity = account.cash_usdt + account.position_btc * quote.bid_usdt
            updated = replace(updated, peak_equity_usdt=max(updated.peak_equity_usdt, equity))
            self._save_checkpoint(self.journal, updated)
            return updated

    @staticmethod
    def _advance(previous, observed_at_ns):
        if observed_at_ns < previous.observed_at_ns:
            raise JournalError("Risk observation time regressed.")
        day = observed_at_ns // DAY_NS
        baseline = previous.day_start_realized_usdt
        if day != previous.utc_day:
            baseline = previous.cumulative_realized_usdt
        return replace(
            previous, observed_at_ns=observed_at_ns, utc_day=day, day_start_realized_usdt=baseline
        )

    def get_receipt(self, order_id: str) -> ExecutionReceipt | None:
        _identifier(order_id)
        with self._snapshot():
            self.risk_checkpoint()
            row = self.journal._db.execute(
                "SELECT payload, sha256 FROM paper_gateway_requests WHERE order_id=?", (order_id,)
            ).fetchone()
            if row is None:
                return None
            request = _read(*row, _decode_request)
            if request.order_id != order_id:
                raise JournalError("Gateway request binding mismatch.")
            state = self.journal.order_state(order_id)
            if state.status not in ("FILLED", "REJECTED"):
                raise JournalError("Incomplete atomic gateway outcome.")
            last = self.journal.order_events(order_id)[-1]
            filled = state.status == "FILLED"
            return ExecutionReceipt(
                order_id,
                self.mode,
                ExecutionStatus.FILLED if filled else ExecutionStatus.REJECTED,
                last.reason,
                state.filled_quantity_btc,
                last.price_usdt if filled else None,
                ("BUY" if type(state.order) is PaperEntryOrder else "SELL") if filled else None,
                state.fee_usdt if filled else None,
            )

    def execute(self, request: PaperQuoteRequest) -> ExecutionReceipt:
        """Atomically decide/book one full simulated fill or a durable rejection.

        Retrying the exact original request recovers its result even after expiry.
        Changed quote/time content under that order ID is a conflict, not a new fill.
        """
        if type(request) is not PaperQuoteRequest:
            raise JournalError("Expected typed paper quote request.")
        payload = _encode(request)
        _read(payload, _hash(payload), _decode_request)
        with self.journal._write(), localcontext() as context:
            context.prec = 100
            checkpoint = self.risk_checkpoint()
            previous = self.journal._db.execute(
                "SELECT payload, sha256 FROM paper_gateway_requests WHERE order_id=?",
                (request.order_id,),
            ).fetchone()
            if previous is not None:
                _read(*previous, _decode_request)
                if previous[0] != payload:
                    raise JournalConflict(
                        "Order was already executed with a different quote request."
                    )
                return self.get_receipt(request.order_id)
            order_state = self.journal.order_state(request.order_id)
            if order_state.status != "PREPARED":
                raise JournalError("Only untouched PREPARED orders can be simulated.")
            order = order_state.order
            if request.observed_at_ns < order.requested_at_ns:
                raise JournalError("Execution observation predates prepared order.")
            checkpoint = self._advance(checkpoint, request.observed_at_ns)
            state = self.journal.account_state()
            is_entry = type(order) is PaperEntryOrder
            side = "BUY" if is_entry else "SELL"
            reason = None
            # Stale quotes must not mark a new peak or generate synthetic fills.
            fresh = request.observed_at_ns - request.quote_at_ns <= self.config.max_quote_age_ns
            if not fresh:
                reason = "stale_quote"
            if is_entry:
                case = self.journal.get_case(order.case_id)
                if request.observed_at_ns >= case.plan.expires_at_ns:
                    reason = "entry_case_expired"
                elif case.risk_config_sha256 != self.config.risk_config_sha256:
                    reason = "case_risk_config_mismatch"
            fill = None
            equity = state.cash_usdt + state.position_btc * request.bid_usdt
            peak = (
                max(checkpoint.peak_equity_usdt, equity) if fresh else checkpoint.peak_equity_usdt
            )
            if reason is None:
                fill = simulate_market_fill(
                    side=side,
                    quantity_btc=order.quantity_btc,
                    quote=MarketQuote(
                        request.bid_usdt, request.ask_usdt, request.quote_at_ns // 10**6
                    ),
                    costs=self.config.costs,
                )
                if is_entry and fill.notional_usdt + fill.fee_usdt > state.cash_usdt:
                    reason = "insufficient_spot_cash"
                else:
                    decision = evaluate_order(
                        OrderIntent(
                            side, order.quantity_btc, fill.price_usdt, reduce_only=not is_entry
                        ),
                        PortfolioRiskState(
                            state.position_btc,
                            state.realized_pnl_usdt - checkpoint.day_start_realized_usdt,
                            equity,
                            peak,
                            checkpoint.kill_switch_active,
                        ),
                        self.config.limits,
                    )
                    if not decision.approved:
                        reason = f"risk_rejected:{decision.reason}"
                if is_entry and reason is None:
                    projected = (
                        state.cash_usdt
                        - fill.notional_usdt
                        - fill.fee_usdt
                        + (state.position_btc + order.quantity_btc) * request.bid_usdt
                    )
                    if peak - projected >= self.config.limits.max_drawdown_usdt:
                        reason = "risk_rejected:projected_drawdown_limit"
            self.journal._db.execute(
                "INSERT INTO paper_gateway_requests VALUES (?, ?, ?)",
                (request.order_id, payload, _hash(payload)),
            )
            prefix = "paper-" + _hash(request.order_id)
            if reason is not None:
                self.journal.append_order_event(
                    PaperOrderEvent(
                        prefix + "-reject",
                        order.order_id,
                        "REJECTED",
                        request.observed_at_ns,
                        reason,
                    )
                )
            else:
                self.journal.append_order_event(
                    PaperOrderEvent(
                        prefix + "-submit",
                        order.order_id,
                        "SUBMITTED",
                        request.observed_at_ns,
                        "atomic_paper_simulation",
                    )
                )
                self.journal.append_order_event(
                    PaperOrderEvent(
                        prefix + "-fill",
                        order.order_id,
                        "FILL",
                        request.observed_at_ns,
                        "paper_fill_applied",
                        prefix + "-fill",
                        request.observed_at_ns,
                        fill.quantity_btc,
                        fill.price_usdt,
                        fill.fee_usdt,
                    )
                )
            after = self.journal.account_state()
            if fresh:
                peak = max(peak, after.cash_usdt + after.position_btc * request.bid_usdt)
            self._save_checkpoint(
                self.journal,
                replace(
                    checkpoint,
                    peak_equity_usdt=peak,
                    cumulative_realized_usdt=after.realized_pnl_usdt,
                    last_event_sequence=self._event_sequence(),
                ),
            )
            result = self.get_receipt(request.order_id)
        return result
