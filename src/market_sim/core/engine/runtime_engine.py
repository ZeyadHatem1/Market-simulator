from market_sim.core.clock import SimulationClock
from market_sim.core.queue import EventQueue
from market_sim.core.engine.event_loop import EventLoop


class RuntimeEngine:
    def __init__(self) -> None:
        self.clock = SimulationClock()
        self.queue = EventQueue()
        self.loop = EventLoop()
        self._order_counter = 0
        self._trade_counter = 0
        self._running = False

    def next_order_id(self) -> str:
        self._order_counter += 1
        return f"order-{self._order_counter}"

    def next_trade_id(self) -> str:
        self._trade_counter += 1
        return f"trade-{self._trade_counter}"

    def start(self) -> None:
        self._running = True
        self.loop.run_until_empty(self.queue)

    def stop(self) -> None:
        self._running = False
