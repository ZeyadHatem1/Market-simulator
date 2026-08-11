from market_sim.core.models import OrderType, Side
from market_sim.events import Event, trade_execution
from market_sim.exchange.orderbook import Order
from market_sim.market.microstructure import SlippageModel

_SIDE_TO_INT = {Side.BUY: 0, Side.SELL: 1}
_INT_TO_SIDE = {0: Side.BUY, 1: Side.SELL}
_ORDER_TYPE_TO_INT = {OrderType.MARKET: 0, OrderType.LIMIT: 1}
_INT_TO_ORDER_TYPE = {0: OrderType.MARKET, 1: OrderType.LIMIT}


def _to_native(order: Order):
    from . import _core

    native = _core.NativeOrder()
    native.order_id = order.order_id
    native.side = _SIDE_TO_INT[order.side]
    native.order_type = _ORDER_TYPE_TO_INT[order.order_type]
    native.quantity = order.quantity
    native.timestamp = order.timestamp
    native.price = order.price
    native.filled_quantity = order.filled_quantity
    native.seq = order.seq
    return native


def _from_native(native) -> Order:
    return Order(
        order_id=native.order_id,
        side=_INT_TO_SIDE[native.side],
        order_type=_INT_TO_ORDER_TYPE[native.order_type],
        quantity=native.quantity,
        timestamp=native.timestamp,
        price=native.price,
        filled_quantity=native.filled_quantity,
        seq=native.seq,
    )


class NativeOrderBook:
    """
    Drop-in for exchange.orderbook.OrderBook, backed by the compiled C++
    extension. Same public method signatures, same Order objects in and out
    -- the pybind11 boundary crossing is confined to this adapter.
    """

    def __init__(self) -> None:
        from . import _core

        self._impl = _core.NativeOrderBook()

    def insert(self, order: Order) -> None:
        order.seq = self._impl.insert(_to_native(order))

    def cancel(self, order_id: str) -> None:
        self._impl.cancel(order_id)

    def best_bid(self) -> Order | None:
        native = self._impl.best_bid()
        return _from_native(native) if native is not None else None

    def best_ask(self) -> Order | None:
        native = self._impl.best_ask()
        return _from_native(native) if native is not None else None

    def pop_best_bid(self) -> Order | None:
        native = self._impl.pop_best_bid()
        return _from_native(native) if native is not None else None

    def pop_best_ask(self) -> Order | None:
        native = self._impl.pop_best_ask()
        return _from_native(native) if native is not None else None

    def bid_depth(self) -> int:
        return self._impl.bid_depth()

    def ask_depth(self) -> int:
        return self._impl.ask_depth()

    def bid_liquidity(self) -> float:
        return self._impl.bid_liquidity()

    def ask_liquidity(self) -> float:
        return self._impl.ask_liquidity()

    def spread(self) -> float | None:
        return self._impl.spread()

    def is_empty(self) -> bool:
        return self._impl.is_empty()


class NativeMatchingEngine:
    """
    Drop-in for exchange.matching.MatchingEngine, backed by the compiled C++
    extension. The native engine itself is slippage-agnostic (always fills
    at the resting order's exact price); this adapter applies the existing,
    unmodified SlippageModel to the returned fills using a liquidity
    snapshot taken once before crossing into C++ -- see
    docs/decisions/ADR-005-native-matching-engine-boundary.md.
    """

    def __init__(self, slippage_model: SlippageModel | None = None) -> None:
        from . import _core

        self._impl = _core.NativeMatchingEngine()
        self._slippage_model = slippage_model

    def match(
        self,
        incoming: Order,
        book: NativeOrderBook,
        timestamp: float,
        sequence: int,
        trade_id: str,
    ) -> list[Event]:
        if not isinstance(book, NativeOrderBook):
            raise TypeError(
                "NativeMatchingEngine requires a NativeOrderBook, got "
                f"{type(book).__name__}; use build_native_exchange() or "
                "construct a NativeOrderBook explicitly."
            )

        needs_slippage = (
            self._slippage_model is not None and incoming.order_type == OrderType.MARKET
        )
        available_liquidity = None
        if needs_slippage:
            available_liquidity = (
                book.ask_liquidity() if incoming.side == Side.BUY else book.bid_liquidity()
            )

        outcome = self._impl.match(
            _to_native(incoming), book._impl, timestamp, sequence, trade_id
        )

        incoming.filled_quantity += outcome.incoming_fill_delta
        if outcome.incoming_seq is not None:
            incoming.seq = outcome.incoming_seq

        events: list[Event] = []
        for fill in outcome.fills:
            price = fill.price
            if needs_slippage:
                price = self._slippage_model.apply(
                    reference_price=price,
                    order_quantity=incoming.quantity,
                    available_liquidity=available_liquidity,
                    side=incoming.side,
                )
            events.append(
                trade_execution(
                    timestamp=fill.timestamp,
                    sequence=fill.sequence,
                    trade_id=fill.trade_id,
                    price=price,
                    quantity=fill.quantity,
                    buy_order_id=fill.buy_order_id,
                    sell_order_id=fill.sell_order_id,
                )
            )
        return events
