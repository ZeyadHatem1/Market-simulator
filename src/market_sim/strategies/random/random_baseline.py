from typing import Callable

import numpy as np

from market_sim.core.clock import SimulationClock
from market_sim.core.models import OrderType, Side
from market_sim.events import Event
from market_sim.strategies.base import Strategy


class RandomBaseline(Strategy):
    """
    Benchmark strategy: on each tick, independently draws BUY / SELL / HOLD
    with equal probability from a seeded RNG. Exists to sanity-check that
    other strategies actually beat noise, not to model any real order flow.

    Determinism guarantee: all randomness flows through a seeded numpy RNG
    sourced from `seed`. Same seed + same tick sequence = identical decisions.
    """

    def __init__(
        self,
        strategy_id: str,
        initial_cash: float,
        clock: SimulationClock,
        order_id_factory: Callable[[], str],
        trade_size: float,
        seed: int,
    ) -> None:
        if trade_size <= 0:
            raise ValueError(f"trade_size must be > 0, got {trade_size}")
        super().__init__(strategy_id, initial_cash, clock, order_id_factory)
        self._trade_size = trade_size
        self._rng = np.random.default_rng(seed)

    def on_market_update(self, event: Event) -> list[Event]:
        price = event.data["price"]
        self._record_price(price)

        choice = self._rng.integers(3)  # 0 = hold, 1 = buy, 2 = sell
        if choice == 0:
            return []

        side = Side.BUY if choice == 1 else Side.SELL
        return [self._submit(event.timestamp, side, OrderType.MARKET, self._trade_size)]

    def on_fill(self, event: Event) -> None:
        self._apply_fill(event)
