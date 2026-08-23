import itertools

import pytest

from market_sim.core.clock import SimulationClock
from market_sim.core.models import Side
from market_sim.events import market_update
from market_sim.strategies import MeanReversionStrategy


def make_order_id_factory():
    counter = itertools.count(1)
    return lambda: f"order-{next(counter)}"


def make_strategy(**overrides) -> MeanReversionStrategy:
    base = dict(
        strategy_id="mean-reversion",
        initial_cash=10_000.0,
        clock=SimulationClock(),
        order_id_factory=make_order_id_factory(),
        lookback=3,
        threshold=2.0,
        trade_size=10.0,
    )
    base.update(overrides)
    return MeanReversionStrategy(**base)


def feed(strategy: MeanReversionStrategy, prices: list[float]):
    results = []
    for i, price in enumerate(prices):
        event = market_update(
            timestamp=float(i + 1), sequence=i, price=price, instrument="SIM"
        )
        results.append(strategy.on_market_update(event))
    return results


def test_no_orders_until_full_lookback_window():
    strategy = make_strategy(lookback=3)
    results = feed(strategy, [100.0, 100.0])
    assert all(r == [] for r in results)


def test_buys_when_price_is_far_below_mean():
    strategy = make_strategy(lookback=3, threshold=2.0)
    # mean of [100, 100, 100] = 100; new price 90 is 10 below -> BUY
    results = feed(strategy, [100.0, 100.0, 100.0, 90.0])
    assert len(results[3]) == 1
    assert results[3][0].data["side"] == Side.BUY


def test_sells_when_price_is_far_above_mean():
    strategy = make_strategy(lookback=3, threshold=2.0)
    results = feed(strategy, [100.0, 100.0, 100.0, 110.0])
    assert len(results[3]) == 1
    assert results[3][0].data["side"] == Side.SELL


def test_flat_when_deviation_within_threshold():
    strategy = make_strategy(lookback=3, threshold=5.0)
    results = feed(strategy, [100.0, 100.0, 100.0, 102.0])
    assert results[3] == []


def test_order_quantity_matches_trade_size():
    strategy = make_strategy(lookback=2, threshold=1.0, trade_size=15.0)
    results = feed(strategy, [100.0, 90.0])
    assert results[1][0].data["quantity"] == 15.0


def test_invalid_lookback_raises():
    with pytest.raises(ValueError):
        make_strategy(lookback=0)


def test_invalid_threshold_raises():
    with pytest.raises(ValueError):
        make_strategy(threshold=0.0)


def test_invalid_trade_size_raises():
    with pytest.raises(ValueError):
        make_strategy(trade_size=0.0)
