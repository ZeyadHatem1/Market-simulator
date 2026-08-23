from market_sim.events import Event
from market_sim.core.models import EventType


class TradeLog:
    def __init__(self) -> None:
        self._trades: list[Event] = []

    def record(self, event: Event) -> None:
        if event.event_type != EventType.TRADE_EXECUTION:
            raise ValueError(f"expected TRADE_EXECUTION, got {event.event_type}")
        self._trades.append(event)

    def all_trades(self) -> list[Event]:
        return list(self._trades)

    def trade_count(self) -> int:
        return len(self._trades)

    def total_volume(self) -> float:
        return sum(e.data["quantity"] for e in self._trades)

    def is_empty(self) -> bool:
        return len(self._trades) == 0
