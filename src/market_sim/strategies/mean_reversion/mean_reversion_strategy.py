from typing import Callable

from market_sim.core.clock import SimulationClock
from market_sim.core.models import OrderType, Side
from market_sim.events import Event
from market_sim.strategies.base import Strategy


class MeanReversionStrategy(Strategy):
    """
    Fades deviations from the rolling mean: buys when price sits more than
    `threshold` below the mean of the last `lookback` prices (expecting it to
    revert up), sells when it sits more than `threshold` above. Flat once
    there isn't yet a full window of history, or the deviation is within
    threshold.
    """

    def __init__(
        self,
        strategy_id: str,
        initial_cash: float,
        clock: SimulationClock,
        order_id_factory: Callable[[], str],
        lookback: int,
        threshold: float,
        trade_size: float,
    ) -> None:
        if lookback <= 0:
            raise ValueError(f"lookback must be > 0, got {lookback}")
        if threshold <= 0:
            raise ValueError(f"threshold must be > 0, got {threshold}")
        if trade_size <= 0:
            raise ValueError(f"trade_size must be > 0, got {trade_size}")
        super().__init__(
            strategy_id, initial_cash, clock, order_id_factory, history_maxlen=lookback
        )
        self._lookback = lookback
        self._threshold = threshold
        self._trade_size = trade_size

    def on_market_update(self, event: Event) -> list[Event]:
        price = event.data["price"]
        self._record_price(price)

        if len(self._price_history) < self._lookback:
            return []

        mean = sum(self._price_history) / len(self._price_history)
        deviation = price - mean
        if deviation < -self._threshold:
            side = Side.BUY
        elif deviation > self._threshold:
            side = Side.SELL
        else:
            return []

        return [self._submit(event.timestamp, side, OrderType.MARKET, self._trade_size)]

    def on_fill(self, event: Event) -> None:
        self._apply_fill(event)
