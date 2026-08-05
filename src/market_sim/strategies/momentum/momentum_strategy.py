from typing import Callable

from market_sim.core.clock import SimulationClock
from market_sim.core.models import OrderType, Side
from market_sim.events import Event
from market_sim.strategies.base import Strategy


class MomentumStrategy(Strategy):
    """
    Trend-following: goes long when price has risen over the lookback window,
    sells when it has fallen. Momentum = current price - price `lookback`
    ticks ago. Flat (no order) once there isn't yet a full window of history,
    or momentum is exactly zero.
    """

    def __init__(
        self,
        strategy_id: str,
        initial_cash: float,
        clock: SimulationClock,
        order_id_factory: Callable[[], str],
        lookback: int,
        trade_size: float,
    ) -> None:
        if lookback <= 0:
            raise ValueError(f"lookback must be > 0, got {lookback}")
        if trade_size <= 0:
            raise ValueError(f"trade_size must be > 0, got {trade_size}")
        super().__init__(
            strategy_id, initial_cash, clock, order_id_factory, history_maxlen=lookback + 1
        )
        self._lookback = lookback
        self._trade_size = trade_size

    def on_market_update(self, event: Event) -> list[Event]:
        price = event.data["price"]
        self._record_price(price)

        if len(self._price_history) <= self._lookback:
            return []

        momentum = price - self._price_history[0]
        if momentum > 0:
            side = Side.BUY
        elif momentum < 0:
            side = Side.SELL
        else:
            return []

        return [self._submit(event.timestamp, side, OrderType.MARKET, self._trade_size)]

    def on_fill(self, event: Event) -> None:
        self._apply_fill(event)
