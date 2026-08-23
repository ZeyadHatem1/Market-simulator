import itertools

import pytest

from market_sim.core.clock import SimulationClock
from market_sim.core.models import EventType, OrderType, Side
from market_sim.events import market_update, trade_execution
from market_sim.strategies.base import Strategy


class _AlwaysBuyStrategy(Strategy):
    """Minimal concrete Strategy for exercising the shared base-class logic."""

    def on_market_update(self, event):
        price = event.data["price"]
        self._record_price(price)
        return [self._submit(event.timestamp, Side.BUY, OrderType.MARKET, 10.0)]

    def on_fill(self, event):
        self._apply_fill(event)


def make_order_id_factory():
    counter = itertools.count(1)
    return lambda: f"order-{next(counter)}"


def make_strategy(**overrides) -> _AlwaysBuyStrategy:
    base = dict(
        strategy_id="test-strategy",
        initial_cash=10_000.0,
        clock=SimulationClock(),
        order_id_factory=make_order_id_factory(),
    )
    base.update(overrides)
    return _AlwaysBuyStrategy(**base)


def make_market_update(timestamp: float, price: float, sequence: int = 0):
    return market_update(
        timestamp=timestamp, sequence=sequence, price=price, instrument="SIM"
    )


# --- initial state ---


def test_initial_state():
    strategy = make_strategy(initial_cash=5_000.0)
    assert strategy.position == 0.0
    assert strategy.cash == 5_000.0
    assert strategy.pnl == 0.0


# --- _submit() ---


def test_submit_produces_order_submit_event():
    strategy = make_strategy()
    events = strategy.on_market_update(make_market_update(1.0, 100.0))
    assert len(events) == 1
    order = events[0]
    assert order.event_type == EventType.ORDER_SUBMIT
    assert order.data["side"] == Side.BUY
    assert order.data["order_type"] == OrderType.MARKET
    assert order.data["quantity"] == 10.0


def test_submit_assigns_unique_order_ids():
    strategy = make_strategy()
    order_a = strategy.on_market_update(make_market_update(1.0, 100.0))[0]
    order_b = strategy.on_market_update(make_market_update(2.0, 101.0))[0]
    assert order_a.data["order_id"] != order_b.data["order_id"]


def test_submit_uses_clock_for_sequence():
    clock = SimulationClock()
    strategy = make_strategy(clock=clock)
    order = strategy.on_market_update(make_market_update(1.0, 100.0))[0]
    assert order.sequence == 0
    order_2 = strategy.on_market_update(make_market_update(2.0, 101.0))[0]
    assert order_2.sequence == 1


# --- on_fill() / fill attribution ---


def test_fill_for_own_buy_order_updates_position_and_cash():
    strategy = make_strategy(initial_cash=10_000.0)
    order = strategy.on_market_update(make_market_update(1.0, 100.0))[0]

    fill = trade_execution(
        timestamp=1.0,
        sequence=1,
        trade_id="trade-1",
        price=100.0,
        quantity=10.0,
        buy_order_id=order.data["order_id"],
        sell_order_id="someone-else-order",
    )
    strategy.on_fill(fill)

    assert strategy.position == 10.0
    assert strategy.cash == pytest.approx(10_000.0 - 100.0 * 10.0)


def test_fill_for_own_sell_order_updates_position_and_cash():
    strategy = make_strategy(initial_cash=10_000.0)
    strategy._own_order_ids.add("my-sell-order")

    fill = trade_execution(
        timestamp=1.0,
        sequence=1,
        trade_id="trade-1",
        price=50.0,
        quantity=4.0,
        buy_order_id="someone-else-order",
        sell_order_id="my-sell-order",
    )
    strategy.on_fill(fill)

    assert strategy.position == -4.0
    assert strategy.cash == pytest.approx(10_000.0 + 50.0 * 4.0)


def test_fill_for_someone_elses_order_is_ignored():
    strategy = make_strategy(initial_cash=10_000.0)
    strategy.on_market_update(make_market_update(1.0, 100.0))

    fill = trade_execution(
        timestamp=1.0,
        sequence=1,
        trade_id="trade-1",
        price=100.0,
        quantity=10.0,
        buy_order_id="not-mine",
        sell_order_id="also-not-mine",
    )
    strategy.on_fill(fill)

    assert strategy.position == 0.0
    assert strategy.cash == 10_000.0


# --- mark-to-market pnl ---


def test_pnl_marks_to_market_on_every_tick_even_without_fills():
    strategy = make_strategy(initial_cash=10_000.0)
    strategy.on_market_update(make_market_update(1.0, 100.0))
    assert strategy.pnl == pytest.approx(0.0)


def test_pnl_reflects_unrealized_gain_after_fill():
    strategy = make_strategy(initial_cash=10_000.0)
    order = strategy.on_market_update(make_market_update(1.0, 100.0))[0]
    fill = trade_execution(
        timestamp=1.0,
        sequence=1,
        trade_id="trade-1",
        price=100.0,
        quantity=10.0,
        buy_order_id=order.data["order_id"],
        sell_order_id="counterparty",
    )
    strategy.on_fill(fill)

    # price rises to 110 on the next tick -> 10 units * $10 unrealized gain
    strategy.on_market_update(make_market_update(2.0, 110.0, sequence=2))
    assert strategy.pnl == pytest.approx(100.0)
