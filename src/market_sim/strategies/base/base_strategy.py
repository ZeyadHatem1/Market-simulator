from abc import ABC, abstractmethod
from collections import deque
from typing import Callable

from market_sim.core.clock import SimulationClock
from market_sim.core.models import OrderType, Side
from market_sim.events import Event, order_submit


class Strategy(ABC):
    """
    Abstract base for measurable trading strategies. Strategies react to
    MARKET_UPDATE events and emit ORDER_SUBMIT events; they never touch the
    order book or portfolio state directly (see ARCHITECTURE.md's strategies/
    rule). position/cash/pnl here is strategy-local bookkeeping only — the
    shared Portfolio layer (portfolio/, not yet built) is a separate concern.

    Fill attribution: on_fill only updates state for fills whose buy/sell
    order_id was actually submitted by this strategy (tracked in
    `_own_order_ids`), since TRADE_EXECUTION is broadcast to every registered
    handler regardless of who submitted the order.
    """

    def __init__(
        self,
        strategy_id: str,
        initial_cash: float,
        clock: SimulationClock,
        order_id_factory: Callable[[], str],
        history_maxlen: int = 1,
    ) -> None:
        self.strategy_id = strategy_id
        self.position: float = 0.0
        self.cash: float = initial_cash
        self.pnl: float = 0.0
        self._initial_cash = initial_cash
        self._clock = clock
        self._order_id_factory = order_id_factory
        self._own_order_ids: set[str] = set()
        self._price_history: deque[float] = deque(maxlen=history_maxlen)

    @abstractmethod
    def on_market_update(self, event: Event) -> list[Event]: ...

    @abstractmethod
    def on_fill(self, event: Event) -> None: ...

    def _record_price(self, price: float) -> None:
        self._price_history.append(price)
        self._mark_to_market(price)

    def _submit(
        self,
        timestamp: float,
        side: Side,
        order_type: OrderType,
        quantity: float,
        price: float | None = None,
    ) -> Event:
        order_id = self._order_id_factory()
        self._own_order_ids.add(order_id)
        return order_submit(
            timestamp=timestamp,
            sequence=self._clock.next_sequence(),
            order_id=order_id,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
        )

    def _apply_fill(self, event: Event) -> None:
        data = event.data
        if data["buy_order_id"] in self._own_order_ids:
            self.position += data["quantity"]
            self.cash -= data["price"] * data["quantity"]
        elif data["sell_order_id"] in self._own_order_ids:
            self.position -= data["quantity"]
            self.cash += data["price"] * data["quantity"]
        else:
            return
        self._mark_to_market(data["price"])

    def _mark_to_market(self, price: float) -> None:
        self.pnl = self.cash + self.position * price - self._initial_cash
