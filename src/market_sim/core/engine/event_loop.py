from collections import defaultdict
from typing import Callable

from market_sim.core.models import EventType
from market_sim.core.queue import EventQueue
from market_sim.events import Event

Handler = Callable[[Event], None]


class EventLoop:
    def __init__(self) -> None:
        self._handlers: dict[EventType, list[Handler]] = defaultdict(list)

    def register_handler(self, event_type: EventType, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def dispatch(self, event: Event) -> None:
        for handler in self._handlers.get(event.event_type, []):
            handler(event)

    def run_until_empty(self, queue: EventQueue) -> None:
        while not queue.is_empty():
            event = queue.pop()
            self.dispatch(event)