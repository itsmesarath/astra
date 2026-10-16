"""Optional 1.231.0 synthetic backtest binding. No live clients or credentials.

Native execution is pending environment verification; see docs/adr/trading_engine.md.
Never register this experimental probe as an execution gateway.
"""

from decimal import Decimal

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.models import LatencyModel
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig, StrategyConfig
from nautilus_trader.model.currencies import BTC, USDT
from nautilus_trader.model.data import BookOrder, OrderBookDelta, OrderBookDeltas, TradeTick
from nautilus_trader.model.enums import (
    AccountType,
    AggressorSide,
    BookAction,
    BookType,
    OmsType,
    OrderSide,
    RecordFlag,
    TimeInForce,
)
from nautilus_trader.model.identifiers import InstrumentId, Symbol, TradeId, Venue
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.trading.strategy import Strategy

from ai_trader.research.nautilus_probe import (
    FEE_RATE,
    INITIAL_CASH,
    LIMIT_PRICE,
    BookImage,
    case_parameters,
    fixture,
    risk_verdict,
)

VENUE = Venue("SIM")
INSTRUMENT_ID = InstrumentId.from_str("BTCUSDT.SIM")


def _instrument():
    # Deliberately synthetic filters: never advertised as current Binance metadata.
    return CurrencyPair(
        instrument_id=INSTRUMENT_ID,
        raw_symbol=Symbol("BTCUSDT"),
        base_currency=BTC,
        quote_currency=USDT,
        price_precision=2,
        size_precision=6,
        price_increment=Price.from_str("0.01"),
        size_increment=Quantity.from_str("0.000001"),
        min_quantity=Quantity.from_str("0.000001"),
        min_notional=Money(Decimal("1"), USDT),
        maker_fee=FEE_RATE,
        taker_fee=FEE_RATE,
        ts_event=0,
        ts_init=0,
    )


def _events():
    data = []
    for row in fixture():
        if isinstance(row, BookImage):
            changes = [
                OrderBookDelta.clear(INSTRUMENT_ID, row.sequence, row.event_ns, row.received_ns)
            ]
            levels = [(OrderSide.BUY, p, q) for p, q in row.bids]
            levels += [(OrderSide.SELL, p, q) for p, q in row.asks]
            for index, (side, price, size) in enumerate(levels):
                flags = int(RecordFlag.F_SNAPSHOT)
                if index == len(levels) - 1:
                    flags |= int(RecordFlag.F_LAST)
                changes.append(
                    OrderBookDelta(
                        INSTRUMENT_ID,
                        BookAction.ADD,
                        BookOrder(side, Price.from_str(price), Quantity.from_str(size), 0),
                        flags,
                        row.sequence,
                        row.event_ns,
                        row.received_ns,
                    )
                )
            data.append(OrderBookDeltas(INSTRUMENT_ID, changes))
        else:
            data.append(
                TradeTick(
                    INSTRUMENT_ID,
                    Price.from_str(row.price),
                    Quantity.from_str(row.quantity),
                    AggressorSide.BUYER,
                    TradeId(row.trade_id),
                    row.event_ns,
                    row.received_ns,
                )
            )
    return data


class _ProbeStrategy(Strategy):
    def __init__(self, case):
        super().__init__(StrategyConfig())
        self.case = case
        self.decision_ask = None
        self.received = []
        self.fills = []
        self.order = None
        self.verdict = None

    def on_start(self):
        self.subscribe_order_book_deltas(INSTRUMENT_ID, BookType.L2_MBP)
        self.subscribe_trade_ticks(INSTRUMENT_ID)

    def on_trade_tick(self, tick):
        self.received.append(self.clock.timestamp_ns())
        if self.verdict is not None:
            return
        book = self.cache.order_book(INSTRUMENT_ID)
        self.decision_ask = str(book.best_ask_price())
        self.verdict = risk_verdict(self.case)
        if not self.verdict.approved:
            return
        quantity, _, _ = case_parameters(self.case)
        self.order = self.order_factory.limit(
            instrument_id=INSTRUMENT_ID,
            order_side=OrderSide.BUY,
            quantity=Quantity.from_str(f"{quantity:.6f}"),
            price=Price.from_str(str(LIMIT_PRICE)),
            time_in_force=TimeInForce.IOC,
        )
        self.submit_order(self.order)

    def on_order_filled(self, event):
        if event.commission.currency != USDT:
            raise ValueError("Synthetic fee must be denominated in USDT")
        self.fills.append(
            {
                "price": str(event.last_px),
                "quantity": str(event.last_qty),
                "fee_usdt": str(event.commission.as_decimal()),
            }
        )


def run_case(case: str) -> dict:
    _, _, delay = case_parameters(case)
    engine = BacktestEngine(config=BacktestEngineConfig(logging=LoggingConfig(bypass_logging=True)))
    try:
        engine.add_venue(
            venue=VENUE,
            oms_type=OmsType.NETTING,
            account_type=AccountType.CASH,
            starting_balances=[Money(INITIAL_CASH, USDT), Money(0, BTC)],
            book_type=BookType.L2_MBP,
            latency_model=LatencyModel(base_latency_nanos=delay),
            trade_execution=False,
            bar_execution=False,
            liquidity_consumption=True,
            allow_cash_borrowing=False,
        )
        engine.add_instrument(_instrument())
        events = _events()
        # add_data requires a homogeneous list; the engine merges by ts_init.
        engine.add_data([event for event in events if isinstance(event, OrderBookDeltas)])
        engine.add_data([event for event in events if isinstance(event, TradeTick)])
        strategy = _ProbeStrategy(case)
        engine.add_strategy(strategy)
        engine.run()
        account = engine.cache.account_for_venue(VENUE)
        if strategy.verdict is None or account is None:
            raise RuntimeError("Replay did not produce the required decision/account")
        return {
            "case": case,
            "risk_reason": strategy.verdict.reason,
            "submitted": int(strategy.order is not None),
            "decision_ask": strategy.decision_ask,
            "fills": strategy.fills,
            "filled_btc": str(account.balance_total(BTC).as_decimal()),
            "cash_usdt": str(account.balance_total(USDT).as_decimal()),
            "fee_usdt": str(sum((Decimal(row["fee_usdt"]) for row in strategy.fills), Decimal(0))),
            "terminal_status": strategy.order.status.name if strategy.order else "NOT_SUBMITTED",
            "trade_receipts_ns": strategy.received,
        }
    finally:
        engine.dispose()
