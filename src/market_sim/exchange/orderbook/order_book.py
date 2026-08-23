import heapq
import itertools
from market_sim.exchange.orderbook.order import Order
from market_sim.core.models import Side


class OrderBook:
    def __init__(self) -> None:
        # bids: max heap — negate price so heapq (min heap) pops highest bid
        self._bids: list[tuple[float, int, Order]] = []
        # asks: min heap — price used directly
        self._asks: list[tuple[float, int, Order]] = []
        self._cancelled: set[str] = set()
        self._seq_counter = itertools.count()

    def insert(self, order: Order) -> None:
        # preserve original time priority if this order is being re-queued
        # after a partial fill; otherwise assign a fresh sequence number
        if order.seq is None:
            order.seq = next(self._seq_counter)

        if order.side == Side.BUY:
            heapq.heappush(self._bids, (-order.price, order.seq, order))
        else:
            heapq.heappush(self._asks, (order.price, order.seq, order))

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
            _, _, order = heapq.heappop(self._bids)
            if order.order_id not in self._cancelled:
                return order
        return None

    def pop_best_ask(self) -> Order | None:
        while self._asks:
            _, _, order = heapq.heappop(self._asks)
            if order.order_id not in self._cancelled:
                return order
        return None

    def _clean(self, heap: list) -> None:
        while heap and heap[0][2].order_id in self._cancelled:
            heapq.heappop(heap)

    def bid_depth(self) -> int:
        return sum(1 for _, _, o in self._bids if o.order_id not in self._cancelled)

    def ask_depth(self) -> int:
        return sum(1 for _, _, o in self._asks if o.order_id not in self._cancelled)

    def bid_liquidity(self) -> float:
        return sum(
            o.remaining_quantity
            for _, _, o in self._bids
            if o.order_id not in self._cancelled
        )

    def ask_liquidity(self) -> float:
        return sum(
            o.remaining_quantity
            for _, _, o in self._asks
            if o.order_id not in self._cancelled
        )

    def spread(self) -> float | None:
        bb, ba = self.best_bid(), self.best_ask()
        if bb is None or ba is None:
            return None
        return ba.price - bb.price

    def is_empty(self) -> bool:
        return self.bid_depth() == 0 and self.ask_depth() == 0
