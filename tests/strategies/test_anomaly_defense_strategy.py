import itertools

import pytest

from market_sim.core.clock import SimulationClock
from market_sim.core.models import Side
from market_sim.events import market_update
from market_sim.strategies import AnomalyDefenseStrategy


def make_order_id_factory():
    counter = itertools.count(1)
    return lambda: f"order-{next(counter)}"


def make_strategy(**overrides) -> AnomalyDefenseStrategy:
    base = dict(
        strategy_id="anomaly-defense",
        initial_cash=10_000.0,
        clock=SimulationClock(),
        order_id_factory=make_order_id_factory(),
        window=4,
        threshold=1.5,
        trade_size=10.0,
    )
    base.update(overrides)
    return AnomalyDefenseStrategy(**base)


def feed(strategy: AnomalyDefenseStrategy, prices: list[float]):
    results = []
    for i, price in enumerate(prices):
        event = market_update(
            timestamp=float(i + 1), sequence=i, price=price, instrument="SIM"
        )
        results.append(strategy.on_market_update(event))
    return results


def fill(strategy: AnomalyDefenseStrategy, order_event, price: float, quantity: float):
    """Simulate a full fill of `order_event` at `price`, attributed correctly
    regardless of side, mirroring how TRADE_EXECUTION events are shaped."""
    from market_sim.events import trade_execution

    order_id = order_event.data["order_id"]
    side = order_event.data["side"]
    buy_id = order_id if side == Side.BUY else "counterparty"
    sell_id = order_id if side == Side.SELL else "counterparty"
    event = trade_execution(
        timestamp=order_event.timestamp,
        sequence=order_event.sequence,
        trade_id="t1",
        buy_order_id=buy_id,
        sell_order_id=sell_id,
        price=price,
        quantity=quantity,
    )
    strategy.on_fill(event)


def test_enters_target_position_once_window_is_full_and_no_anomaly():
    # AnomalyDetector needs window+1 price updates before is_ready (its
    # first update only seeds last_price, with no return to append yet).
    strategy = make_strategy(window=4, trade_size=10.0)
    results = feed(strategy, [100.0, 100.0, 100.0, 100.0, 100.0])
    assert results[:4] == [[], [], [], []]
    assert len(results[4]) == 1
    order = results[4][0]
    assert order.data["side"] == Side.BUY
    assert order.data["quantity"] == 10.0


def test_stays_flat_before_window_is_full():
    strategy = make_strategy(window=4)
    results = feed(strategy, [100.0, 100.0, 100.0, 100.0])
    assert results == [[], [], [], []]


def test_flattens_on_detected_anomaly():
    strategy = make_strategy(window=4, threshold=1.5, trade_size=10.0)
    results = feed(strategy, [100.0, 100.0, 100.0, 100.0, 100.0])
    fill(strategy, results[4][0], price=100.0, quantity=10.0)
    assert strategy.position == 10.0

    spike_results = feed(strategy, [110.0])
    assert len(spike_results[0]) == 1
    flatten_order = spike_results[0][0]
    assert flatten_order.data["side"] == Side.SELL
    assert flatten_order.data["quantity"] == 10.0


def test_refuses_new_entry_while_anomaly_persists():
    strategy = make_strategy(window=4, threshold=1.5, trade_size=10.0)
    feed(strategy, [100.0, 100.0, 100.0, 100.0, 100.0])
    # Never filled -> position stays 0, but the detector is now primed with
    # a spike as the incoming return.
    results = feed(strategy, [110.0])
    # Position is already 0 (never filled), and the tick is anomalous, so no
    # new entry order is submitted.
    assert results == [[]]


def test_re_enters_once_the_anomaly_clears():
    strategy = make_strategy(window=4, threshold=1.5, trade_size=10.0)
    entry_results = feed(strategy, [100.0, 100.0, 100.0, 100.0, 100.0])
    fill(strategy, entry_results[4][0], price=100.0, quantity=10.0)

    flatten_results = feed(strategy, [110.0])
    fill(strategy, flatten_results[0][0], price=110.0, quantity=10.0)
    assert strategy.position == 0.0

    # Next tick's return (110 -> 110, i.e. 0) is no longer the spike, so the
    # detector clears and the strategy re-enters its target position.
    re_entry_results = feed(strategy, [110.0])
    assert len(re_entry_results[0]) == 1
    order = re_entry_results[0][0]
    assert order.data["side"] == Side.BUY
    assert order.data["quantity"] == 10.0


def test_invalid_trade_size_raises():
    with pytest.raises(ValueError):
        make_strategy(trade_size=0.0)


def test_invalid_detector_params_propagate():
    with pytest.raises(ValueError):
        make_strategy(window=1)
    with pytest.raises(ValueError):
        make_strategy(threshold=0.0)
