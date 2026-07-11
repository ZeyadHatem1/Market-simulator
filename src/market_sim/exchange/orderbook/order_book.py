import heapq
from collections import defaultdict

from market_sim.exchange.orderbook.order import Order
from market_sim.core.models import Side


class OrderBook:
    def __init__(self) -> None:
        # bids: max heap — negate price so heapq (min heap) pops highest bid
        self._bids: list[tuple[float, str, Order]] = []
        # asks: min heap — price used directly
        self._asks: list[tuple[float, str, Order]] = []
        self._cancelled: set[str] = set()

    def insert(self, order: Order) -> None:
        if order.side == Side.BUY:
            heapq.heappush(self._bids, (-order.price, order.order_id, order))
        else:
            heapq.heappush(self._asks, (order.price, order.order_id, order))

    def cancel(self, order_id: str) -> None:
        self._cancelled.add(order_id)

    def best_bid(self) -> Order | None:
        self._clean(self._bids)
        if not self._bids:
            return None
        return self._bids[0][2]

    def best_ask(self) -> Order | None:
        self._clean(self._asks)
        if not self._asks:
            return None
        return self._asks[0][2]

    def pop_best_bid(self) -> Order | None:
        while self._bids:
            _, order_id, order = heapq.heappop(self._bids)
            if order_id not in self._cancelled:
                return order
        return None

    def pop_best_ask(self) -> Order | None:
        while self._asks:
            _, order_id, order = heapq.heappop(self._asks)
            if order_id not in self._cancelled:
                return order
        return None

    def _clean(self, heap: list) -> None:
        while heap and heap[0][1] in self._cancelled:
            heapq.heappop(heap)

    def bid_depth(self) -> int:
        return sum(1 for _, oid, _ in self._bids if oid not in self._cancelled)

    def ask_depth(self) -> int:
        return sum(1 for _, oid, _ in self._asks if oid not in self._cancelled)

    def is_empty(self) -> bool:
        return self.bid_depth() == 0 and self.ask_depth() == 0