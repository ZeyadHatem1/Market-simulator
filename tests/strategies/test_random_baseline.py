import itertools

import pytest

from market_sim.core.clock import SimulationClock
from market_sim.core.models import Side
from market_sim.events import market_update
from market_sim.strategies import RandomBaseline


def make_order_id_factory():
    counter = itertools.count(1)
    return lambda: f"order-{next(counter)}"


def make_strategy(**overrides) -> RandomBaseline:
    base = dict(
        strategy_id="random",
        initial_cash=10_000.0,
        clock=SimulationClock(),
        order_id_factory=make_order_id_factory(),
        trade_size=10.0,
        seed=42,
    )
    base.update(overrides)
    return RandomBaseline(**base)


def feed(strategy: RandomBaseline, n_ticks: int):
    results = []
    for i in range(n_ticks):
        event = market_update(timestamp=float(i + 1), sequence=i, price=100.0, instrument="SIM")
        results.append(strategy.on_market_update(event))
    return results


def test_same_seed_produces_identical_decisions():
    results_a = feed(make_strategy(seed=7), 50)
    results_b = feed(make_strategy(seed=7), 50)
    sides_a = [r[0].data["side"] if r else None for r in results_a]
    sides_b = [r[0].data["side"] if r else None for r in results_b]
    assert sides_a == sides_b


def test_different_seeds_produce_different_decisions():
    results_a = feed(make_strategy(seed=1), 50)
    results_b = feed(make_strategy(seed=2), 50)
    sides_a = [r[0].data["side"] if r else None for r in results_a]
    sides_b = [r[0].data["side"] if r else None for r in results_b]
    assert sides_a != sides_b


def test_decisions_roughly_evenly_split_over_many_ticks():
    # Law of large numbers: with enough ticks, BUY/SELL/HOLD should each land
    # near 1/3 of the time.
    results = feed(make_strategy(seed=42), 30_000)
    n_buy = sum(1 for r in results if r and r[0].data["side"] == Side.BUY)
    n_sell = sum(1 for r in results if r and r[0].data["side"] == Side.SELL)
    n_hold = sum(1 for r in results if not r)

    assert n_buy / 30_000 == pytest.approx(1 / 3, abs=0.02)
    assert n_sell / 30_000 == pytest.approx(1 / 3, abs=0.02)
    assert n_hold / 30_000 == pytest.approx(1 / 3, abs=0.02)


def test_order_quantity_matches_trade_size():
    strategy = make_strategy(seed=42, trade_size=7.0)
    results = feed(strategy, 50)
    traded = [r[0] for r in results if r]
    assert traded  # sanity: at least one order fired in 50 ticks
    assert all(order.data["quantity"] == 7.0 for order in traded)


def test_invalid_trade_size_raises():
    with pytest.raises(ValueError):
        make_strategy(trade_size=0.0)
