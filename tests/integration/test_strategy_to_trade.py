from market_sim.core.engine.runtime_engine import RuntimeEngine
from market_sim.core.models import EventType, OrderType, Side
from market_sim.events import market_update, order_submit
from market_sim.exchange import build_exchange
from market_sim.strategies import MomentumStrategy


def test_strategy_drives_orders_into_exchange_end_to_end():
    """
    A strategy plugged directly into build_exchange(): MARKET_UPDATE events
    drive MomentumStrategy.on_market_update(), whose returned ORDER_SUBMIT
    events are pushed onto the queue, and TRADE_EXECUTION events are routed
    back to the strategy's on_fill() via the same generic
    EventLoop.register_handler used by every other handler in the system —
    no new wiring primitive needed.
    """
    runtime = RuntimeEngine()
    book, trade_log, gateway = build_exchange(runtime)

    strategy = MomentumStrategy(
        strategy_id="momentum-1",
        initial_cash=10_000.0,
        clock=runtime.clock,
        order_id_factory=runtime.next_order_id,
        lookback=3,
        trade_size=5.0,
    )

    def on_market_update(event):
        for order_event in strategy.on_market_update(event):
            runtime.queue.push(order_event)

    runtime.loop.register_handler(EventType.MARKET_UPDATE, on_market_update)
    runtime.loop.register_handler(EventType.TRADE_EXECUTION, strategy.on_fill)

    # Seed the book with standing liquidity the strategy's eventual BUY
    # market order can cross against.
    runtime.queue.push(
        order_submit(
            timestamp=0.0,
            sequence=runtime.clock.next_sequence(),
            order_id=runtime.next_order_id(),
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            price=101.0,
            quantity=5.0,
        )
    )

    # Rising price series: momentum triggers a BUY once the lookback=3
    # window is full, on the 4th tick.
    for i, price in enumerate([100.0, 101.0, 102.0, 105.0]):
        runtime.queue.push(
            market_update(
                timestamp=float(i + 1),
                sequence=runtime.clock.next_sequence(),
                price=price,
                instrument="SIM",
            )
        )

    runtime.start()

    assert runtime.queue.is_empty()
    assert gateway.rejected_orders == []
    assert trade_log.trade_count() == 1
    assert book.is_empty()

    assert strategy.position == 5.0
    assert strategy.cash == 10_000.0 - 101.0 * 5.0
