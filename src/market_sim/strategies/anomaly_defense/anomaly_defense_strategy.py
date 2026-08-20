from typing import Callable

from market_sim.ai.anomaly import AnomalyDetector
from market_sim.core.clock import SimulationClock
from market_sim.core.models import OrderType, Side
from market_sim.events import Event
from market_sim.strategies.base import Strategy


class AnomalyDefenseStrategy(Strategy):
    """
    Holds a static target long position of `trade_size` units under normal
    conditions, and flattens to cash whenever AnomalyDetector flags the
    latest return as anomalous, re-entering only once the detector clears.
    No independent alpha signal — the anomaly flag is the only trigger for
    both exiting and re-entering, making this purely risk-off rather than
    directional (contrast MomentumStrategy/MeanReversionStrategy).
    """

    def __init__(
        self,
        strategy_id: str,
        initial_cash: float,
        clock: SimulationClock,
        order_id_factory: Callable[[], str],
        window: int,
        threshold: float,
        trade_size: float,
    ) -> None:
        if trade_size <= 0:
            raise ValueError(f"trade_size must be > 0, got {trade_size}")
        super().__init__(
            strategy_id, initial_cash, clock, order_id_factory, history_maxlen=1
        )
        self._detector = AnomalyDetector(window=window, threshold=threshold)
        self._trade_size = trade_size

    def on_market_update(self, event: Event) -> list[Event]:
        price = event.data["price"]
        self._record_price(price)
        is_anomaly = self._detector.update(price)

        if not self._detector.is_ready:
            return []

        if is_anomaly and self.position != 0:
            side = Side.SELL if self.position > 0 else Side.BUY
            return [
                self._submit(
                    event.timestamp, side, OrderType.MARKET, abs(self.position)
                )
            ]

        if not is_anomaly and self.position == 0:
            return [
                self._submit(
                    event.timestamp, Side.BUY, OrderType.MARKET, self._trade_size
                )
            ]

        return []

    def on_fill(self, event: Event) -> None:
        self._apply_fill(event)
