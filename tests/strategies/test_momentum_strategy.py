import itertools

import pytest

from market_sim.core.clock import SimulationClock
from market_sim.core.models import Side
from market_sim.events import market_update
from market_sim.strategies import MomentumStrategy


def make_order_id_factory():
    counter = itertools.count(1)
    return lambda: f"order-{next(counter)}"


def make_strategy(**overrides) -> MomentumStrategy:
    base = dict(
        strategy_id="momentum",
        initial_cash=10_000.0,
        clock=SimulationClock(),
        order_id_factory=make_order_id_factory(),
        lookback=3,
        trade_size=10.0,
    )
    base.update(overrides)
    return MomentumStrategy(**base)


def feed(strategy: MomentumStrategy, prices: list[float]):
    results = []
    for i, price in enumerate(prices):
        event = market_update(timestamp=float(i + 1), sequence=i, price=price, instrument="SIM")
        results.append(strategy.on_market_update(event))
    return results


def test_no_orders_until_full_lookback_window():
    strategy = make_strategy(lookback=3)
    results = feed(strategy, [100.0, 101.0, 102.0])
    assert all(r == [] for r in results)


def test_buys_when_price_has_risen_over_lookback():
    strategy = make_strategy(lookback=3)
    results = feed(strategy, [100.0, 101.0, 102.0, 105.0])
    assert results[:3] == [[], [], []]
    assert len(results[3]) == 1
    assert results[3][0].data["side"] == Side.BUY


def test_sells_when_price_has_fallen_over_lookback():
    strategy = make_strategy(lookback=3)
    results = feed(strategy, [100.0, 99.0, 98.0, 95.0])
    assert len(results[3]) == 1
    assert results[3][0].data["side"] == Side.SELL


def test_flat_when_momentum_is_exactly_zero():
    strategy = make_strategy(lookback=3)
    results = feed(strategy, [100.0, 105.0, 95.0, 100.0])
    assert results[3] == []


def test_order_quantity_matches_trade_size():
    strategy = make_strategy(lookback=1, trade_size=25.0)
    results = feed(strategy, [100.0, 105.0])
    assert results[1][0].data["quantity"] == 25.0


def test_invalid_lookback_raises():
    with pytest.raises(ValueError):
        make_strategy(lookback=0)


def test_invalid_trade_size_raises():
    with pytest.raises(ValueError):
        make_strategy(trade_size=0.0)
