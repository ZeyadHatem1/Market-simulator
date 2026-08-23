import heapq
import itertools

from market_sim.events import Event


class EventQueue:
    def __init__(self) -> None:
        self._heap: list[tuple[float, int, Event]] = []
        self._counter = itertools.count()

    def push(self, event: Event) -> None:
        heapq.heappush(self._heap, (event.timestamp, event.sequence, event))

    def pop(self) -> Event:
        if self.is_empty():
            raise IndexError("pop from empty EventQueue")
        _, _, event = heapq.heappop(self._heap)
        return event

    def peek(self) -> Event | None:
        if self.is_empty():
            return None
        return self._heap[0][2]

    def is_empty(self) -> bool:
        return len(self._heap) == 0

    def __len__(self) -> int:
        return len(self._heap)
