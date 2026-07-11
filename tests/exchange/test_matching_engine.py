from market_sim.exchange.orderbook import Order, OrderBook
from market_sim.exchange.matching import MatchingEngine
from market_sim.core.models import Side, OrderType
from market_sim.core.models import EventType


def make_limit(order_id: str, side: Side, price: float, quantity: float = 10.0) -> Order:
    return Order(
        order_id=order_id,
        side=side,
        order_type=OrderType.LIMIT,
        price=price,
        quantity=quantity,
        timestamp=1.0,
    )


def make_market(order_id: str, side: Side, quantity: float = 10.0) -> Order:
    return Order(
        order_id=order_id,
        side=side,
        order_type=OrderType.MARKET,
        quantity=quantity,
        timestamp=1.0,
    )


def match(incoming: Order, book: OrderBook) -> list:
    engine = MatchingEngine()
    return engine.match(incoming, book, timestamp=1.0, sequence=0, trade_id="t1")


def test_limit_buy_matches_resting_ask():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0))
    fills = match(make_limit("b1", Side.BUY, 100.0), book)
    assert len(fills) == 1
    assert fills[0].data["price"] == 100.0
    assert fills[0].data["quantity"] == 10.0


def test_limit_sell_matches_resting_bid():
    book = OrderBook()
    book.insert(make_limit("b1", Side.BUY, 100.0))
    fills = match(make_limit("s1", Side.SELL, 100.0), book)
    assert len(fills) == 1
    assert fills[0].data["price"] == 100.0


def test_limit_buy_below_ask_rests_in_book():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 102.0))
    fills = match(make_limit("b1", Side.BUY, 100.0), book)
    assert fills == []
    assert book.bid_depth() == 1


def test_limit_sell_above_bid_rests_in_book():
    book = OrderBook()
    book.insert(make_limit("b1", Side.BUY, 100.0))
    fills = match(make_limit("s1", Side.SELL, 102.0), book)
    assert fills == []
    assert book.ask_depth() == 1


def test_partial_fill_leaves_remainder_in_book():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0, quantity=5.0))
    fills = match(make_limit("b1", Side.BUY, 100.0, quantity=10.0), book)
    assert len(fills) == 1
    assert fills[0].data["quantity"] == 5.0
    assert book.bid_depth() == 1


def test_market_buy_matches_best_ask():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0))
    fills = match(make_market("m1", Side.BUY), book)
    assert len(fills) == 1
    assert fills[0].data["price"] == 100.0


def test_market_sell_matches_best_bid():
    book = OrderBook()
    book.insert(make_limit("b1", Side.BUY, 100.0))
    fills = match(make_market("m1", Side.SELL), book)
    assert len(fills) == 1
    assert fills[0].data["price"] == 100.0


def test_market_order_no_liquidity_produces_no_fills():
    book = OrderBook()
    fills = match(make_market("m1", Side.BUY), book)
    assert fills == []


def test_fill_events_are_trade_executions():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0))
    fills = match(make_limit("b1", Side.BUY, 100.0), book)
    assert all(f.event_type == EventType.TRADE_EXECUTION for f in fills)


def test_fill_assigns_correct_buy_and_sell_ids():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0))
    fills = match(make_limit("b1", Side.BUY, 100.0), book)
    assert fills[0].data["buy_order_id"] == "b1"
    assert fills[0].data["sell_order_id"] == "a1"


def test_market_sweeps_multiple_levels():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0, quantity=5.0))
    book.insert(make_limit("a2", Side.SELL, 101.0, quantity=5.0))
    fills = match(make_market("m1", Side.BUY, quantity=10.0), book)
    assert len(fills) == 2
    assert fills[0].data["price"] == 100.0
    assert fills[1].data["price"] == 101.0