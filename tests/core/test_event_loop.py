from market_sim.core.engine.event_loop import EventLoop
from market_sim.core.queue import EventQueue
from market_sim.core.models import EventType
from market_sim.events import market_update, trade_execution


def test_dispatch_calls_registered_handler():
    loop = EventLoop()
    received = []

    loop.register_handler(EventType.MARKET_UPDATE, lambda e: received.append(e))

    event = market_update(timestamp=1.0, sequence=0, price=100.0, instrument="SIM")
    loop.dispatch(event)

    assert received == [event]


def test_multiple_handlers_all_fire():
    loop = EventLoop()
    calls = []

    loop.register_handler(EventType.MARKET_UPDATE, lambda e: calls.append("a"))
    loop.register_handler(EventType.MARKET_UPDATE, lambda e: calls.append("b"))

    event = market_update(timestamp=1.0, sequence=0, price=100.0, instrument="SIM")
    loop.dispatch(event)

    assert calls == ["a", "b"]


def test_run_until_empty_dispatches_in_order():
    loop = EventLoop()
    queue = EventQueue()
    order = []

    loop.register_handler(
        EventType.MARKET_UPDATE, lambda e: order.append(("market", e.sequence))
    )
    loop.register_handler(
        EventType.TRADE_EXECUTION, lambda e: order.append(("trade", e.sequence))
    )

    queue.push(market_update(timestamp=2.0, sequence=1, price=100.0, instrument="SIM"))
    queue.push(
        trade_execution(
            timestamp=1.0,
            sequence=0,
            trade_id="t1",
            price=100.0,
            quantity=1.0,
            buy_order_id="b1",
            sell_order_id="s1",
        )
    )

    loop.run_until_empty(queue)

    assert order == [("trade", 0), ("market", 1)]
    assert queue.is_empty()
