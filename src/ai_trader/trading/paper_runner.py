"""Bounded, offline tick-driven paper controller; no signal model or network loop.

Health inputs must come from a trusted receipt-causal feed adapter. A bounded call
processes only supplied ticks, prioritizes protection, and never invents prices.
"""

from dataclasses import dataclass, replace
from decimal import Decimal, localcontext
from inspect import iscoroutine
from itertools import islice

from ai_trader.features.microstructure import MicrostructureObservation
from ai_trader.trading.durable_paper_gateway import (
    DurablePaperGateway,
    PaperQuoteRequest,
    PaperRiskCheckpoint,
)
from ai_trader.trading.paper_account import PaperAccountState
from ai_trader.trading.paper_lifecycle import PaperEntryOrder, PaperExitOrder, _money, _timestamp
from ai_trader.trading.trade_case import PreTradeCase
from ai_trader.trading.trade_journal import (
    JournalConflict,
    JournalError,
    _decimal,
    _encode,
    _hash,
    _identifier,
    _read,
    _shape,
)


@dataclass(frozen=True, slots=True)
class PaperRunnerConfig:
    max_trade_age_ns: int
    max_entry_spread_bps: Decimal

    def __post_init__(self):
        _timestamp(self.max_trade_age_ns)
        _money(self.max_entry_spread_bps)
        if not self.max_trade_age_ns or self.max_entry_spread_bps >= 10000:
            raise ValueError("Positive trade age and spread below 10000 bps required.")


@dataclass(frozen=True, slots=True)
class PaperMarketTick:
    tick_id: str
    source_session: str
    observed_at_ns: int
    quote_received_at_ns: int
    last_trade_received_at_ns: int | None
    bid_usdt: Decimal
    ask_usdt: Decimal
    book_synchronized: bool
    features_ready: bool
    observation_sha256: str
    candidate_case_id: str | None = None

    def __post_init__(self):
        for value in (self.tick_id, self.source_session):
            _identifier(value)
        if self.candidate_case_id is not None:
            _identifier(self.candidate_case_id)
        PaperQuoteRequest(
            self.tick_id,
            self.bid_usdt,
            self.ask_usdt,
            self.quote_received_at_ns,
            self.observed_at_ns,
        )
        if self.last_trade_received_at_ns is not None:
            _timestamp(self.last_trade_received_at_ns)
            if self.last_trade_received_at_ns > self.observed_at_ns:
                raise ValueError("Future trade receipt.")
        if type(self.book_synchronized) is not bool or type(self.features_ready) is not bool:
            raise ValueError("Health flags must be actual booleans.")
        if (
            not isinstance(self.observation_sha256, str)
            or len(self.observation_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.observation_sha256)
        ):
            raise ValueError("Expected observation SHA256.")

    @classmethod
    def from_observation(
        cls,
        observation,
        *,
        tick_id,
        observed_at_ns,
        last_trade_received_at_ns,
        book_synchronized,
        candidate_case_id=None,
    ):
        """Bridge the existing microstructure schema, not retrospective session quality."""
        if (
            type(observation) is not MicrostructureObservation
            or observation.book.symbol != "BTCUSDT"
        ):
            raise ValueError("Expected BTCUSDT microstructure observation.")
        flags = (
            observation.rolling_window_complete,
            observation.evidence_interval_valid,
            observation.bid_band_covered,
            observation.ask_band_covered,
            observation.bid_top_n_covered,
            observation.ask_top_n_covered,
        )
        if any(type(flag) is not bool for flag in flags):
            raise ValueError("Invalid microstructure readiness flags.")
        return cls(
            tick_id,
            observation.source_session,
            observed_at_ns,
            observation.received_at_ns,
            last_trade_received_at_ns,
            observation.book.best_bid_price,
            observation.book.best_ask_price,
            book_synchronized,
            all(flags),
            _hash(_encode(observation)),
            candidate_case_id,
        )


@dataclass(frozen=True, slots=True)
class PaperTickResult:
    tick_id: str
    quote_health: str
    entry_reason: str
    entry_order_id: str | None
    exit_order_ids: tuple[str, ...]
    blocked_exit_entry_ids: tuple[str, ...]

    def __post_init__(self):
        for value in (self.tick_id, self.quote_health, self.entry_reason):
            _identifier(value)
        if self.entry_order_id is not None:
            _identifier(self.entry_order_id)
        for values in (self.exit_order_ids, self.blocked_exit_entry_ids):
            if type(values) is not tuple or len(values) != len(set(values)):
                raise ValueError("Expected unique immutable order identifiers.")
            for value in values:
                _identifier(value)


@dataclass(frozen=True, slots=True)
class PaperDecisionContext:
    """Immutable ledger snapshot AFTER marks/protection and BEFORE a possible entry."""

    tick: PaperMarketTick
    quote_health: str
    protection_active: bool
    account: PaperAccountState
    checkpoint: PaperRiskCheckpoint


def _decode_config(value):
    value = _shape(value, PaperRunnerConfig)
    value["max_entry_spread_bps"] = _decimal(value["max_entry_spread_bps"])
    return PaperRunnerConfig(**value)


def _decode_tick(value):
    value = _shape(value, PaperMarketTick)
    for key in ("bid_usdt", "ask_usdt"):
        value[key] = _decimal(value[key])
    return PaperMarketTick(**value)


def _decode_result(value):
    value = _shape(value, PaperTickResult)
    for key in ("exit_order_ids", "blocked_exit_entry_ids"):
        if not isinstance(value[key], list):
            raise JournalError("Expected stored ID list.")
        value[key] = tuple(value[key])
    return PaperTickResult(**value)


class PaperRunner:
    """Each tick commits health, marks, exits, optional entry and result atomically."""

    def __init__(self, gateway: DurablePaperGateway, config: PaperRunnerConfig):
        self.gateway, self.config = gateway, config
        self.journal = gateway.journal
        self._schema()
        self._configuration()

    def _schema(self):
        self.journal._account_schema()
        if self.journal._db.execute("PRAGMA user_version").fetchone()[0] not in (5, 6):
            raise JournalError("Explicit schema upgrade required for paper runner.")

    def _configuration(self):
        row = self.journal._db.execute(
            "SELECT payload, sha256 FROM paper_runner_config WHERE singleton=1"
        ).fetchone()
        if row is None:
            raise JournalError("Initialize the paper runner explicitly.")
        stored = _read(*row, _decode_config)
        if type(self.config) is not PaperRunnerConfig or _encode(stored) != _encode(self.config):
            raise JournalConflict("Runner configuration mismatch.")

    @classmethod
    def initialize(cls, gateway, config):
        if type(config) is not PaperRunnerConfig:
            raise JournalError("Expected typed runner configuration.")
        journal = gateway.journal
        if journal._db.execute("PRAGMA user_version").fetchone()[0] not in (5, 6):
            raise JournalError("Explicit schema upgrade required for paper runner.")
        with journal._write():
            gateway.risk_checkpoint()
            if journal._db.execute("SELECT 1 FROM paper_runner_config").fetchone() is None:
                payload = _encode(config)
                journal._db.execute(
                    "INSERT INTO paper_runner_config VALUES (1, ?, ?)", (payload, _hash(payload))
                )
            cls(gateway, config)
        return cls(gateway, config)

    def _read_result(self, row):
        tick = _read(row[0], row[1], _decode_tick)
        result = _read(row[2], row[3], _decode_result)
        if tick.tick_id != result.tick_id:
            raise JournalError("Stored tick/result binding mismatch.")
        for order_id in result.exit_order_ids + (
            (result.entry_order_id,) if result.entry_order_id else ()
        ):
            if self.gateway.get_receipt(order_id) is None:
                raise JournalError("Tick outcome has no durable receipt.")
        return tick, result

    def get_result(self, tick_id: str) -> PaperTickResult | None:
        _identifier(tick_id)
        with self.gateway._snapshot():
            self._configuration()
            self.gateway.risk_checkpoint()
            row = self.journal._db.execute(
                "SELECT payload, sha256, result, result_sha256 "
                "FROM paper_runner_ticks WHERE tick_id=?",
                (tick_id,),
            ).fetchone()
            if row is None:
                return None
            tick, result = self._read_result(row)
            if tick.tick_id != tick_id:
                raise JournalError("Stored tick identity mismatch.")
            return result

    def process(self, tick: PaperMarketTick) -> PaperTickResult:
        return self._process(tick)

    def process_with_case_builder(self, tick, *, case_id, build_case) -> PaperTickResult:
        """Opt-in trusted, synchronous policy seam; no background/model execution.

        Caller must bind policy/config identity to case_id and the journal run.
        Builder runs only on a NEW tick, after protection, in the write transaction.
        It must return a new paper case without mutating the ledger. Exact retries
        validate/reuse the recorded case, never reassess against a later balance.
        """
        if (
            type(tick) is not PaperMarketTick
            or tick.candidate_case_id is not None
            or not callable(build_case)
        ):
            raise JournalError("Expected a candidate-free tick and callable case builder.")
        _identifier(case_id)
        return self._process(replace(tick, candidate_case_id=case_id), case_builder=build_case)

    def _validate_built_case(self, case, tick):
        if (
            type(case) is not PreTradeCase
            or case.mode != "paper"
            or case.case_id != tick.candidate_case_id
            or case.source_session != tick.source_session
            or case.decision_at_ns != tick.observed_at_ns
            or case.market_state_sha256 != tick.observation_sha256
            or case.risk_config_sha256 != self.gateway.config.risk_config_sha256
        ):
            raise JournalError("Generated case does not match the paper decision context.")

    def _process(self, tick: PaperMarketTick, *, case_builder=None) -> PaperTickResult:
        if type(tick) is not PaperMarketTick:
            raise JournalError("Expected typed market tick.")
        payload = _encode(tick)
        _read(payload, _hash(payload), _decode_tick)
        with self.journal._write(), localcontext() as context:
            context.prec = 100
            self._configuration()
            self.gateway.risk_checkpoint()
            previous = self.journal._db.execute(
                "SELECT payload, sha256, result, result_sha256 "
                "FROM paper_runner_ticks WHERE tick_id=?",
                (tick.tick_id,),
            ).fetchone()
            if previous:
                stored_tick, result = self._read_result(previous)
                if stored_tick.tick_id != tick.tick_id or previous[0] != payload:
                    raise JournalConflict("Tick ID already has different content.")
                if case_builder is not None:
                    self._validate_built_case(self.journal.get_case(tick.candidate_case_id), tick)
                return result
            last = self.journal._db.execute(
                "SELECT payload, sha256 FROM paper_runner_ticks ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            if last:
                prior = _read(*last, _decode_tick)
                if tick.observed_at_ns < prior.observed_at_ns:
                    raise JournalError("Runner clock regressed.")
                if tick.source_session == prior.source_session and (
                    tick.quote_received_at_ns < prior.quote_received_at_ns
                    or (
                        tick.last_trade_received_at_ns is not None
                        and prior.last_trade_received_at_ns is not None
                        and tick.last_trade_received_at_ns < prior.last_trade_received_at_ns
                    )
                ):
                    raise JournalError("Feed receipt time regressed within session.")
            quote_health = "healthy"
            if not tick.book_synchronized:
                quote_health = "book_unsynchronized"
            elif (
                tick.observed_at_ns - tick.quote_received_at_ns
                > self.gateway.config.max_quote_age_ns
            ):
                quote_health = "stale_quote"
            if quote_health == "healthy":
                self.gateway.mark_quote(
                    bid_usdt=tick.bid_usdt,
                    ask_usdt=tick.ask_usdt,
                    quote_at_ns=tick.quote_received_at_ns,
                    observed_at_ns=tick.observed_at_ns,
                )
            else:
                self.gateway.heartbeat(observed_at_ns=tick.observed_at_ns)
            exits, blocked, protection = self._protect(tick, quote_health)
            if case_builder is not None:
                decision_context = PaperDecisionContext(
                    tick,
                    quote_health,
                    protection,
                    self.journal.account_state(),
                    self.gateway.risk_checkpoint(),
                )
                changes_before_builder = self.journal._db.total_changes
                case = case_builder(decision_context)
                if iscoroutine(case):
                    case.close()
                    raise JournalError("Case builder must be synchronous.")
                self._validate_built_case(case, tick)
                # A builder is deliberately a pure seam; do not accept a builder
                # changing cash, orders, checkpoints or cases before its return.
                if (
                    changes_before_builder != self.journal._db.total_changes
                    or decision_context.account != self.journal.account_state()
                    or decision_context.checkpoint != self.gateway.risk_checkpoint()
                ):
                    raise JournalError("Case builder changed the ledger/risk state.")
                if self.journal.get_case(case.case_id) is not None:
                    raise JournalConflict("Generated case already exists without its tick.")
                self.journal.append_case(case)
            entry_reason, entry_id = self._entry(tick, quote_health, protection)
            result = PaperTickResult(
                tick.tick_id, quote_health, entry_reason, entry_id, tuple(exits), tuple(blocked)
            )
            encoded_result = _encode(result)
            self.journal._db.execute(
                "INSERT INTO paper_runner_ticks (tick_id, payload, sha256, result, result_sha256) "
                "VALUES (?, ?, ?, ?, ?)",
                (tick.tick_id, payload, _hash(payload), encoded_result, _hash(encoded_result)),
            )
        return result

    def _protect(self, tick, quote_health):
        exits, blocked, protection = [], [], False
        for position in self.journal.account_state().positions:
            if position.quantity_btc == 0:
                continue
            if quote_health != "healthy":
                blocked.append(position.entry_order_id)
                protection = True
                continue
            order = self.journal.get_order(position.entry_order_id)
            plan = self.journal.get_case(order.case_id).plan
            first_fill = min(
                e.executed_at_ns
                for e in self.journal.order_events(order.order_id)
                if e.kind == "FILL"
            )
            checkpoint = self.gateway.risk_checkpoint()
            account = self.journal.account_state()
            equity = account.cash_usdt + account.position_btc * tick.bid_usdt
            reason = None
            if (
                account.realized_pnl_usdt - checkpoint.day_start_realized_usdt
                <= -self.gateway.config.limits.max_daily_loss_usdt
            ):
                reason = "daily_loss_limit"
            elif (
                checkpoint.peak_equity_usdt - equity >= self.gateway.config.limits.max_drawdown_usdt
            ):
                reason = "drawdown_limit"
            elif tick.bid_usdt <= plan.stop_price_usdt:
                reason = "stop_loss"
            elif tick.bid_usdt >= plan.take_profit_price_usdt:
                reason = "take_profit"
            elif tick.observed_at_ns - first_fill >= plan.maximum_hold_ns:
                reason = "maximum_hold"
            if reason is None:
                continue
            protection = True
            if position.reserved_exit_btc:
                blocked.append(position.entry_order_id)
                continue
            exit_id = "runner-exit-" + _hash(_encode(tick) + order.order_id)
            self.journal.append_exit_order(
                PaperExitOrder(
                    exit_id,
                    order.order_id,
                    position.quantity_btc,
                    tick.observed_at_ns,
                    reason,
                )
            )
            self.gateway.execute(self._request(tick, exit_id))
            exits.append(exit_id)
        return exits, blocked, protection

    @staticmethod
    def _request(tick, order_id):
        return PaperQuoteRequest(
            order_id, tick.bid_usdt, tick.ask_usdt, tick.quote_received_at_ns, tick.observed_at_ns
        )

    def _entry(self, tick, quote_health, protection):
        if protection:
            return "protective_exit_tick", None
        if quote_health != "healthy":
            return quote_health, None
        if not tick.features_ready:
            return "microstructure_not_ready", None
        if (
            tick.last_trade_received_at_ns is None
            or tick.observed_at_ns - tick.last_trade_received_at_ns > self.config.max_trade_age_ns
        ):
            return "stale_trades", None
        spread = (tick.ask_usdt - tick.bid_usdt) * Decimal(10000) / tick.bid_usdt
        if spread > self.config.max_entry_spread_bps:
            return "entry_spread_limit", None
        if tick.candidate_case_id is None:
            return "no_candidate", None
        case = self.journal.get_case(tick.candidate_case_id)
        if case is None:
            return "missing_case", None
        if case.action != "ENTER_LONG" or case.risk_verdict != "APPROVED":
            return "case_not_approved", None
        if (
            case.source_session != tick.source_session
            or case.market_state_sha256 != tick.observation_sha256
        ):
            return "case_observation_mismatch", None
        if not tick.quote_received_at_ns <= case.decision_at_ns <= tick.observed_at_ns:
            return "case_decision_time_mismatch", None
        if tick.observed_at_ns >= case.plan.expires_at_ns:
            return "entry_case_expired", None
        if self.journal._db.execute(
            "SELECT 1 FROM paper_orders WHERE case_id=?", (case.case_id,)
        ).fetchone():
            return "case_already_ordered", None
        # Do not enter outside the original protection bracket after a price jump.
        proposed_price = tick.ask_usdt * (
            Decimal(1) + self.gateway.config.costs.slippage_bps / Decimal(10000)
        )
        if (
            tick.bid_usdt <= case.plan.stop_price_usdt
            or proposed_price >= case.plan.take_profit_price_usdt
        ):
            return "entry_outside_plan", None
        order_id = "runner-entry-" + _hash(case.case_id)
        self.journal.append_order(
            PaperEntryOrder(
                order_id, case.case_id, case.sha256, case.approved_quantity_btc, tick.observed_at_ns
            )
        )
        receipt = self.gateway.execute(self._request(tick, order_id))
        return receipt.reason, order_id

    def run(self, ticks, *, max_ticks: int) -> tuple[PaperTickResult, ...]:
        """Consume no more than the explicit budget; no polling, waiting or network."""
        if type(max_ticks) is not int or not 1 <= max_ticks <= 10000:
            raise ValueError("Tick budget must be between 1 and 10000.")
        return tuple(self.process(tick) for tick in islice(ticks, max_ticks))
