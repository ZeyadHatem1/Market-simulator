from market_sim.exchange.orderbook.order import Order
from market_sim.exchange.orderbook.order_book import OrderBook
from market_sim.core.models import Side, OrderType
from market_sim.events import Event, trade_execution
from market_sim.market.microstructure import SlippageModel


class MatchingEngine:
    def __init__(self, slippage_model: SlippageModel | None = None) -> None:
        self._slippage_model = slippage_model

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
        fill_count = 0

        while not incoming.is_filled:
            if incoming.side == Side.BUY:
                resting = book.best_ask()
                if resting is None or incoming.price < resting.price:
                    break
                resting = book.pop_best_ask()
            else:
                resting = book.best_bid()
                if resting is None or incoming.price > resting.price:
                    break
                resting = book.pop_best_bid()

            fills.append(
                self._execute(incoming, resting, timestamp, sequence, trade_id, fill_count)
            )
            fill_count += 1

            if not resting.is_filled:
                book.insert(resting)  # re-queued, seq preserved -> keeps time priority

        if not incoming.is_filled:
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
        fill_count = 0
        # snapshot taken once, before any fills for this order, so the model
        # is a pure function of the incoming order and the pre-trade book —
        # slippage does not compound across an order's own fills
        available_liquidity = (
            book.ask_liquidity() if incoming.side == Side.BUY else book.bid_liquidity()
        )

        while not incoming.is_filled:
            resting = book.pop_best_ask() if incoming.side == Side.BUY else book.pop_best_bid()
            if resting is None:
                break

            fill_price = resting.price
            if self._slippage_model is not None:
                fill_price = self._slippage_model.apply(
                    reference_price=fill_price,
                    order_quantity=incoming.quantity,
                    available_liquidity=available_liquidity,
                    side=incoming.side,
                )

            fills.append(
                self._execute(
                    incoming, resting, timestamp, sequence, trade_id, fill_count, fill_price
                )
            )
            fill_count += 1

            if not resting.is_filled:
                book.insert(resting)

        return fills

    def _execute(
        self,
        incoming: Order,
        resting: Order,
        timestamp: float,
        sequence: int,
        trade_id: str,
        fill_count: int,
        fill_price: float | None = None,
    ) -> Event:
        fill_qty = min(incoming.remaining_quantity, resting.remaining_quantity)
        if fill_price is None:
            fill_price = resting.price

        incoming.filled_quantity += fill_qty
        resting.filled_quantity += fill_qty

        buy_id = incoming.order_id if incoming.side == Side.BUY else resting.order_id
        sell_id = incoming.order_id if incoming.side == Side.SELL else resting.order_id

        return trade_execution(
            timestamp=timestamp,
            sequence=sequence + fill_count,
            trade_id=f"{trade_id}-{fill_count}",
            price=fill_price,
            quantity=fill_qty,
            buy_order_id=buy_id,
            sell_order_id=sell_id,
        )