from market_sim.exchange.orderbook.order import Order
from market_sim.exchange.orderbook.order_book import OrderBook
from market_sim.core.models import Side, OrderType
from market_sim.events import Event, trade_execution


class MatchingEngine:
    def match(
        self,
        incoming: Order,
        book: OrderBook,
        timestamp: float,
        sequence: int,
        trade_id: str,
    ) -> list[Event]:
        if incoming.order_type == OrderType.LIMIT:
            return self._match_limit(incoming, book, timestamp, sequence, trade_id)
        return self._match_market(incoming, book, timestamp, sequence, trade_id)

    def _match_limit(
        self,
        incoming: Order,
        book: OrderBook,
        timestamp: float,
        sequence: int,
        trade_id: str,
    ) -> list[Event]:
        fills: list[Event] = []

        if incoming.side == Side.BUY:
            resting = book.best_ask()
            if resting is None or incoming.price < resting.price:
                book.insert(incoming)
                return fills
            resting = book.pop_best_ask()
        else:
            resting = book.best_bid()
            if resting is None or incoming.price > resting.price:
                book.insert(incoming)
                return fills
            resting = book.pop_best_bid()

        fill_price = resting.price
        fill_qty = min(incoming.quantity, resting.quantity)

        buy_id = incoming.order_id if incoming.side == Side.BUY else resting.order_id
        sell_id = incoming.order_id if incoming.side == Side.SELL else resting.order_id

        fills.append(
            trade_execution(
                timestamp=timestamp,
                sequence=sequence,
                trade_id=trade_id,
                price=fill_price,
                quantity=fill_qty,
                buy_order_id=buy_id,
                sell_order_id=sell_id,
            )
        )

        remaining_incoming = incoming.quantity - fill_qty
        remaining_resting = resting.quantity - fill_qty

        if remaining_resting > 0:
            resting.quantity = remaining_resting
            book.insert(resting)

        if remaining_incoming > 0:
            incoming.quantity = remaining_incoming
            book.insert(incoming)

        return fills

    def _match_market(
        self,
        incoming: Order,
        book: OrderBook,
        timestamp: float,
        sequence: int,
        trade_id: str,
    ) -> list[Event]:
        fills: list[Event] = []
        remaining = incoming.quantity

        while remaining > 0:
            if incoming.side == Side.BUY:
                resting = book.pop_best_ask()
            else:
                resting = book.pop_best_bid()

            if resting is None:
                break

            fill_qty = min(remaining, resting.quantity)
            fill_price = resting.price

            buy_id = incoming.order_id if incoming.side == Side.BUY else resting.order_id
            sell_id = incoming.order_id if incoming.side == Side.SELL else resting.order_id

            fills.append(
                trade_execution(
                    timestamp=timestamp,
                    sequence=sequence,
                    trade_id=trade_id,
                    price=fill_price,
                    quantity=fill_qty,
                    buy_order_id=buy_id,
                    sell_order_id=sell_id,
                )
            )

            remaining -= fill_qty
            leftover = resting.quantity - fill_qty
            if leftover > 0:
                resting.quantity = leftover
                book.insert(resting)

        return fills