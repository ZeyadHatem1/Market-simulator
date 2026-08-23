import pytest

from market_sim.exchange.orderbook import Order, OrderBook
from market_sim.exchange.matching import MatchingEngine
from market_sim.core.models import Side, OrderType
from market_sim.core.models import EventType
from market_sim.market.microstructure import SlippageModel


def make_limit(
    order_id: str, side: Side, price: float, quantity: float = 10.0
) -> Order:
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


def match(
    incoming: Order, book: OrderBook, slippage_model: SlippageModel | None = None
) -> list:
    engine = MatchingEngine(slippage_model=slippage_model)
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


def test_limit_buy_sweeps_multiple_levels():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0, quantity=5.0))
    book.insert(make_limit("a2", Side.SELL, 101.0, quantity=5.0))
    fills = match(make_limit("b1", Side.BUY, 102.0, quantity=10.0), book)
    assert len(fills) == 2
    assert fills[0].data["price"] == 100.0
    assert fills[1].data["price"] == 101.0
    assert book.is_empty()


def test_time_priority_at_same_price():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0, quantity=5.0))
    book.insert(make_limit("a2", Side.SELL, 100.0, quantity=5.0))
    fills = match(make_market("m1", Side.BUY, quantity=5.0), book)
    assert fills[0].data["sell_order_id"] == "a1"


def test_partial_fill_keeps_time_priority_on_requeue():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0, quantity=10.0))
    book.insert(make_limit("a2", Side.SELL, 100.0, quantity=5.0))
    match(make_market("m1", Side.BUY, quantity=5.0), book)
    fills = match(make_market("m2", Side.BUY, quantity=5.0), book)
    assert fills[0].data["sell_order_id"] == "a1"


def test_cancelled_order_is_skipped_at_same_price_level():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0, quantity=5.0))
    book.insert(make_limit("a2", Side.SELL, 100.0, quantity=5.0))
    book.cancel("a1")

    fills = match(make_market("m1", Side.BUY, quantity=5.0), book)

    assert len(fills) == 1
    assert fills[0].data["sell_order_id"] == "a2"
    assert fills[0].data["quantity"] == 5.0
    assert book.is_empty()


def test_cancelled_order_is_skipped_mid_sweep_across_levels():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0, quantity=5.0))
    book.insert(make_limit("a2", Side.SELL, 101.0, quantity=5.0))
    book.cancel("a1")

    fills = match(make_market("m1", Side.BUY, quantity=5.0), book)

    assert len(fills) == 1
    assert fills[0].data["sell_order_id"] == "a2"
    assert fills[0].data["price"] == 101.0
    assert book.is_empty()


def test_no_slippage_model_market_fill_uses_exact_resting_price():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0, quantity=10.0))
    fills = match(make_market("m1", Side.BUY, quantity=10.0), book)
    assert fills[0].data["price"] == 100.0


def test_slippage_moves_market_buy_price_against_aggressor():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0, quantity=10.0))
    model = SlippageModel(coefficient=100.0)  # order == full depth -> 1% impact
    fills = match(
        make_market("m1", Side.BUY, quantity=10.0), book, slippage_model=model
    )
    assert fills[0].data["price"] == pytest.approx(101.0)


def test_slippage_moves_market_sell_price_against_aggressor():
    book = OrderBook()
    book.insert(make_limit("b1", Side.BUY, 100.0, quantity=10.0))
    model = SlippageModel(coefficient=100.0)
    fills = match(
        make_market("m1", Side.SELL, quantity=10.0), book, slippage_model=model
    )
    assert fills[0].data["price"] == pytest.approx(99.0)


def test_slippage_uses_pretrade_liquidity_snapshot_across_levels():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0, quantity=5.0))
    book.insert(make_limit("a2", Side.SELL, 101.0, quantity=5.0))
    # total ask liquidity = 10, order size = 10 -> 1% impact applied to each level's
    # own reference price, using the same pre-trade snapshot for both fills
    model = SlippageModel(coefficient=100.0)
    fills = match(
        make_market("m1", Side.BUY, quantity=10.0), book, slippage_model=model
    )
    assert len(fills) == 2
    assert fills[0].data["price"] == pytest.approx(101.0)
    assert fills[1].data["price"] == pytest.approx(102.01)


def test_slippage_model_does_not_apply_to_limit_orders():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0, quantity=10.0))
    model = SlippageModel(coefficient=100.0)
    fills = match(
        make_limit("b1", Side.BUY, 100.0, quantity=10.0), book, slippage_model=model
    )
    assert fills[0].data["price"] == 100.0


def test_cancelled_order_is_skipped_during_limit_sweep():
    book = OrderBook()
    book.insert(make_limit("a1", Side.SELL, 100.0, quantity=5.0))
    book.insert(make_limit("a2", Side.SELL, 101.0, quantity=5.0))
    book.cancel("a1")

    fills = match(make_limit("b1", Side.BUY, 101.0, quantity=5.0), book)

    assert len(fills) == 1
    assert fills[0].data["sell_order_id"] == "a2"
    assert fills[0].data["price"] == 101.0
    assert book.is_empty()
