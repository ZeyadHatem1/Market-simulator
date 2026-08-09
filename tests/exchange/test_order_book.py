import pytest
from market_sim.exchange.orderbook import Order, OrderBook
from market_sim.core.models import Side, OrderType


def make_limit(order_id: str, side: Side, price: float, quantity: float = 10.0) -> Order:
    return Order(
        order_id=order_id,
        side=side,
        order_type=OrderType.LIMIT,
        price=price,
        quantity=quantity,
        timestamp=1.0,
    )


def test_best_bid_returns_highest_price():
    book = OrderBook()
    book.insert(make_limit("b1", Side.BUY, 99.0))
    book.insert(make_limit("b2", Side.BUY, 101.0))
    book.insert(make_limit("b3", Side.BUY, 100.0))
    assert book.best_bid().price == 101.0


def test_best_ask_returns_lowest_price():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 102.0))
    book.insert(make_limit("a2", Side.SELL, 100.0))
    book.insert(make_limit("a3", Side.SELL, 101.0))
    assert book.best_ask().price == 100.0


def test_cancel_removes_from_bid_side():
    book = OrderBook()
    book.insert(make_limit("b1", Side.BUY, 101.0))
    book.insert(make_limit("b2", Side.BUY, 100.0))
    book.cancel("b1")
    assert book.best_bid().price == 100.0


def test_cancel_removes_from_ask_side():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0))
    book.insert(make_limit("a2", Side.SELL, 101.0))
    book.cancel("a1")
    assert book.best_ask().price == 101.0


def test_empty_book_returns_none():
    book = OrderBook()
    assert book.best_bid() is None
    assert book.best_ask() is None


def test_is_empty():
    book = OrderBook()
    assert book.is_empty()
    book.insert(make_limit("b1", Side.BUY, 100.0))
    assert not book.is_empty()


def test_bid_depth_and_ask_depth():
    book = OrderBook()
    book.insert(make_limit("b1", Side.BUY, 100.0))
    book.insert(make_limit("b2", Side.BUY, 99.0))
    book.insert(make_limit("a1", Side.SELL, 101.0))
    assert book.bid_depth() == 2
    assert book.ask_depth() == 1


def test_bid_liquidity_and_ask_liquidity_sum_remaining_quantity():
    book = OrderBook()
    book.insert(make_limit("b1", Side.BUY, 100.0, quantity=10.0))
    book.insert(make_limit("b2", Side.BUY, 99.0, quantity=5.0))
    book.insert(make_limit("a1", Side.SELL, 101.0, quantity=7.0))
    assert book.bid_liquidity() == 15.0
    assert book.ask_liquidity() == 7.0


def test_liquidity_excludes_cancelled_orders():
    book = OrderBook()
    book.insert(make_limit("b1", Side.BUY, 100.0, quantity=10.0))
    book.insert(make_limit("b2", Side.BUY, 99.0, quantity=5.0))
    book.cancel("b1")
    assert book.bid_liquidity() == 5.0


def test_liquidity_zero_on_empty_side():
    book = OrderBook()
    assert book.bid_liquidity() == 0.0
    assert book.ask_liquidity() == 0.0


def test_invalid_quantity_raises():
    with pytest.raises(ValueError):
        Order(order_id="x", side=Side.BUY, order_type=OrderType.LIMIT,
              price=100.0, quantity=0.0, timestamp=1.0)


def test_limit_order_without_price_raises():
    with pytest.raises(ValueError):
        Order(order_id="x", side=Side.BUY, order_type=OrderType.LIMIT,
              price=None, quantity=10.0, timestamp=1.0)