import pytest

from market_sim.core.engine.runtime_engine import RuntimeEngine
from market_sim.core.models import EventType, OrderType, Side
from market_sim.events import order_submit
from market_sim.exchange import ExchangeGateway, OrderBook, TradeLog, build_exchange
from market_sim.market.microstructure import SlippageModel


def make_wired_exchange() -> tuple[RuntimeEngine, OrderBook, TradeLog, ExchangeGateway]:
    runtime = RuntimeEngine()
    book, trade_log, gateway = build_exchange(runtime)
    return runtime, book, trade_log, gateway


def submit(
    runtime: RuntimeEngine, timestamp: float, side: Side, price: float, quantity: float
):
    runtime.queue.push(
        order_submit(
            timestamp=timestamp,
            sequence=runtime.clock.next_sequence(),
            order_id=runtime.next_order_id(),
            side=side,
            order_type=OrderType.LIMIT,
            price=price,
            quantity=quantity,
        )
    )


def test_crossing_order_is_matched_and_logged_end_to_end():
    runtime, book, trade_log, _ = make_wired_exchange()

    submit(runtime, timestamp=1.0, side=Side.SELL, price=100.0, quantity=5.0)
    submit(runtime, timestamp=2.0, side=Side.BUY, price=100.0, quantity=5.0)

    runtime.start()

    assert runtime.queue.is_empty()
    assert trade_log.trade_count() == 1

    trade = trade_log.all_trades()[0]
    assert trade.event_type == EventType.TRADE_EXECUTION
    assert trade.data["price"] == 100.0
    assert trade.data["quantity"] == 5.0
    assert book.is_empty()


def test_non_crossing_order_rests_and_logs_no_trade():
    runtime, book, trade_log, _ = make_wired_exchange()

    submit(runtime, timestamp=1.0, side=Side.SELL, price=102.0, quantity=5.0)
    submit(runtime, timestamp=2.0, side=Side.BUY, price=100.0, quantity=5.0)

    runtime.start()

    assert trade_log.is_empty()
    assert book.bid_depth() == 1
    assert book.ask_depth() == 1


def test_malformed_order_is_rejected_without_crashing_the_run():
    runtime, book, trade_log, gateway = make_wired_exchange()

    malformed = order_submit(
        timestamp=1.0,
        sequence=runtime.clock.next_sequence(),
        order_id=runtime.next_order_id(),
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        price=None,  # limit order missing a price -> invalid
        quantity=5.0,
    )
    runtime.queue.push(malformed)

    submit(runtime, timestamp=2.0, side=Side.SELL, price=100.0, quantity=5.0)
    submit(runtime, timestamp=3.0, side=Side.BUY, price=100.0, quantity=5.0)

    runtime.start()  # must not raise

    assert len(gateway.rejected_orders) == 1
    assert gateway.rejected_orders[0].data["order_id"] == malformed.data["order_id"]
    assert trade_log.trade_count() == 1
    assert book.is_empty()


def test_slippage_model_wired_through_build_exchange_moves_market_fill_price():
    runtime = RuntimeEngine()
    book, trade_log, _ = build_exchange(
        runtime, slippage_model=SlippageModel(coefficient=100.0)
    )

    submit(runtime, timestamp=1.0, side=Side.SELL, price=100.0, quantity=5.0)
    runtime.queue.push(
        order_submit(
            timestamp=2.0,
            sequence=runtime.clock.next_sequence(),
            order_id=runtime.next_order_id(),
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=5.0,
        )
    )

    runtime.start()

    trade = trade_log.all_trades()[0]
    assert trade.data["price"] == pytest.approx(101.0)
    assert book.is_empty()
