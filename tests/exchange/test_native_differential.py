"""
Differential tests: the native (C++/pybind11) engine must behave identically
to the pure-Python one for every scenario. Python is the correctness oracle
(see docs/decisions/ADR-005-native-matching-engine-boundary.md) -- these
tests exist to prove that, not to test either engine's behavior in isolation
(that's what test_order_book.py / test_matching_engine.py are for).

Skipped entirely when the extension hasn't been built, so this file never
breaks a run that hasn't `pip install pybind11 && pip install -e .`'d.
"""

import numpy as np
import pytest

from market_sim.core.models import OrderType, Side
from market_sim.exchange.matching import MatchingEngine
from market_sim.exchange.native import NATIVE_AVAILABLE

if NATIVE_AVAILABLE:
    from market_sim.exchange.native import NativeMatchingEngine, NativeOrderBook
from market_sim.exchange.orderbook import Order, OrderBook
from market_sim.market.microstructure import SlippageModel

pytestmark = pytest.mark.skipif(
    not NATIVE_AVAILABLE,
    reason="native extension not built -- see docs/decisions/ADR-005-native-matching-engine-boundary.md",
)


def make_limit(
    order_id: str,
    side: Side,
    price: float,
    quantity: float = 10.0,
    timestamp: float = 1.0,
) -> Order:
    return Order(order_id, side, OrderType.LIMIT, quantity, timestamp, price)


def make_market(
    order_id: str, side: Side, quantity: float = 10.0, timestamp: float = 1.0
) -> Order:
    return Order(order_id, side, OrderType.MARKET, quantity, timestamp, None)


def make_engines(slippage_coefficient: float | None = None):
    py_slip = (
        SlippageModel(coefficient=slippage_coefficient)
        if slippage_coefficient is not None
        else None
    )
    native_slip = (
        SlippageModel(coefficient=slippage_coefficient)
        if slippage_coefficient is not None
        else None
    )
    return (
        OrderBook(),
        MatchingEngine(slippage_model=py_slip),
        NativeOrderBook(),
        NativeMatchingEngine(slippage_model=native_slip),
    )


def assert_fills_equal(py_fills, native_fills):
    assert len(py_fills) == len(native_fills)
    for pf, nf in zip(py_fills, native_fills):
        assert pf.data["price"] == pytest.approx(nf.data["price"])
        assert pf.data["quantity"] == pytest.approx(nf.data["quantity"])
        assert pf.data["buy_order_id"] == nf.data["buy_order_id"]
        assert pf.data["sell_order_id"] == nf.data["sell_order_id"]


def assert_books_equal(py_book, native_book):
    assert py_book.is_empty() == native_book.is_empty()
    assert py_book.bid_depth() == native_book.bid_depth()
    assert py_book.ask_depth() == native_book.ask_depth()
    assert py_book.bid_liquidity() == pytest.approx(native_book.bid_liquidity())
    assert py_book.ask_liquidity() == pytest.approx(native_book.ask_liquidity())

    py_spread, native_spread = py_book.spread(), native_book.spread()
    assert (py_spread is None) == (native_spread is None)
    if py_spread is not None:
        assert py_spread == pytest.approx(native_spread)

    for accessor in ("best_bid", "best_ask"):
        po, no = getattr(py_book, accessor)(), getattr(native_book, accessor)()
        assert (po is None) == (no is None)
        if po is not None:
            assert po.order_id == no.order_id
            assert po.price == pytest.approx(no.price)
            assert po.remaining_quantity == pytest.approx(no.remaining_quantity)
            assert po.seq == no.seq  # time priority must be preserved identically


# --- scripted scenarios, mirroring the highest-value cases in test_matching_engine.py ---


def test_multi_level_sweep():
    py_book, py_engine, native_book, native_engine = make_engines()
    for book in (py_book, native_book):
        book.insert(make_limit("a1", Side.SELL, 100.0, 5.0))
        book.insert(make_limit("a2", Side.SELL, 101.0, 5.0))

    py_fills = py_engine.match(make_market("m1", Side.BUY, 10.0), py_book, 2.0, 0, "t1")
    native_fills = native_engine.match(
        make_market("m1", Side.BUY, 10.0), native_book, 2.0, 0, "t1"
    )

    assert_fills_equal(py_fills, native_fills)
    assert_books_equal(py_book, native_book)


def test_time_priority_at_same_price():
    py_book, py_engine, native_book, native_engine = make_engines()
    for book in (py_book, native_book):
        book.insert(make_limit("a1", Side.SELL, 100.0, 5.0))
        book.insert(make_limit("a2", Side.SELL, 100.0, 5.0))

    py_fills = py_engine.match(make_market("m1", Side.BUY, 5.0), py_book, 2.0, 0, "t1")
    native_fills = native_engine.match(
        make_market("m1", Side.BUY, 5.0), native_book, 2.0, 0, "t1"
    )

    assert_fills_equal(py_fills, native_fills)
    assert py_fills[0].data["sell_order_id"] == "a1"
    assert_books_equal(py_book, native_book)


def test_partial_fill_preserves_seq_on_requeue():
    py_book, py_engine, native_book, native_engine = make_engines()
    for book in (py_book, native_book):
        book.insert(make_limit("a1", Side.SELL, 100.0, 10.0))
        book.insert(make_limit("a2", Side.SELL, 100.0, 5.0))

    py_engine.match(make_market("m1", Side.BUY, 5.0), py_book, 2.0, 0, "t1")
    native_engine.match(make_market("m1", Side.BUY, 5.0), native_book, 2.0, 0, "t1")
    assert_books_equal(py_book, native_book)

    py_fills = py_engine.match(make_market("m2", Side.BUY, 5.0), py_book, 3.0, 10, "t2")
    native_fills = native_engine.match(
        make_market("m2", Side.BUY, 5.0), native_book, 3.0, 10, "t2"
    )

    assert_fills_equal(py_fills, native_fills)
    assert py_fills[0].data["sell_order_id"] == "a1"  # seq preserved -> still first
    assert_books_equal(py_book, native_book)


def test_cancelled_order_skipped_at_same_price_level():
    py_book, py_engine, native_book, native_engine = make_engines()
    for book in (py_book, native_book):
        book.insert(make_limit("a1", Side.SELL, 100.0, 5.0))
        book.insert(make_limit("a2", Side.SELL, 100.0, 5.0))
        book.cancel("a1")

    py_fills = py_engine.match(make_market("m1", Side.BUY, 5.0), py_book, 2.0, 0, "t1")
    native_fills = native_engine.match(
        make_market("m1", Side.BUY, 5.0), native_book, 2.0, 0, "t1"
    )

    assert_fills_equal(py_fills, native_fills)
    assert py_fills[0].data["sell_order_id"] == "a2"
    assert_books_equal(py_book, native_book)


def test_cancelled_order_skipped_across_levels():
    py_book, py_engine, native_book, native_engine = make_engines()
    for book in (py_book, native_book):
        book.insert(make_limit("a1", Side.SELL, 100.0, 5.0))
        book.insert(make_limit("a2", Side.SELL, 101.0, 5.0))
        book.cancel("a1")

    py_fills = py_engine.match(make_market("m1", Side.BUY, 5.0), py_book, 2.0, 0, "t1")
    native_fills = native_engine.match(
        make_market("m1", Side.BUY, 5.0), native_book, 2.0, 0, "t1"
    )

    assert_fills_equal(py_fills, native_fills)
    assert py_fills[0].data["price"] == 101.0
    assert_books_equal(py_book, native_book)


def test_limit_order_rests_when_not_crossing():
    py_book, py_engine, native_book, native_engine = make_engines()
    for book in (py_book, native_book):
        book.insert(make_limit("a1", Side.SELL, 102.0, 5.0))

    py_fills = py_engine.match(
        make_limit("b1", Side.BUY, 100.0, 10.0), py_book, 2.0, 0, "t1"
    )
    native_fills = native_engine.match(
        make_limit("b1", Side.BUY, 100.0, 10.0), native_book, 2.0, 0, "t1"
    )

    assert_fills_equal(py_fills, native_fills)
    assert_books_equal(py_book, native_book)


def test_slippage_moves_buy_price_up():
    py_book, py_engine, native_book, native_engine = make_engines(
        slippage_coefficient=100.0
    )
    for book in (py_book, native_book):
        book.insert(make_limit("a1", Side.SELL, 100.0, 10.0))

    py_fills = py_engine.match(make_market("m1", Side.BUY, 10.0), py_book, 2.0, 0, "t1")
    native_fills = native_engine.match(
        make_market("m1", Side.BUY, 10.0), native_book, 2.0, 0, "t1"
    )

    assert_fills_equal(py_fills, native_fills)
    assert py_fills[0].data["price"] == pytest.approx(101.0)


def test_slippage_moves_sell_price_down():
    py_book, py_engine, native_book, native_engine = make_engines(
        slippage_coefficient=100.0
    )
    for book in (py_book, native_book):
        book.insert(make_limit("b1", Side.BUY, 100.0, 10.0))

    py_fills = py_engine.match(
        make_market("m1", Side.SELL, 10.0), py_book, 2.0, 0, "t1"
    )
    native_fills = native_engine.match(
        make_market("m1", Side.SELL, 10.0), native_book, 2.0, 0, "t1"
    )

    assert_fills_equal(py_fills, native_fills)
    assert py_fills[0].data["price"] == pytest.approx(99.0)


def test_slippage_uses_pretrade_snapshot_across_levels():
    py_book, py_engine, native_book, native_engine = make_engines(
        slippage_coefficient=100.0
    )
    for book in (py_book, native_book):
        book.insert(make_limit("a1", Side.SELL, 100.0, 5.0))
        book.insert(make_limit("a2", Side.SELL, 101.0, 5.0))

    py_fills = py_engine.match(make_market("m1", Side.BUY, 10.0), py_book, 2.0, 0, "t1")
    native_fills = native_engine.match(
        make_market("m1", Side.BUY, 10.0), native_book, 2.0, 0, "t1"
    )

    assert_fills_equal(py_fills, native_fills)
    assert [f.data["price"] for f in py_fills] == pytest.approx([101.0, 102.01])
    assert_books_equal(py_book, native_book)


# --- seeded random fuzz ---


@pytest.mark.parametrize("seed", [0, 1, 2, 7, 42])
@pytest.mark.parametrize("slippage_coefficient", [None, 25.0])
def test_native_matches_python_fuzz(seed, slippage_coefficient):
    rng = np.random.default_rng(seed)
    py_book, py_engine, native_book, native_engine = make_engines(slippage_coefficient)
    live_ids: list[str] = []
    mid = 100.0

    for step in range(500):
        if live_ids and rng.random() < 0.1:
            order_id = live_ids[rng.integers(len(live_ids))]
            py_book.cancel(order_id)
            native_book.cancel(order_id)
            assert_books_equal(py_book, native_book)
            continue

        side = Side.BUY if rng.random() < 0.5 else Side.SELL
        order_type = OrderType.LIMIT if rng.random() < 0.8 else OrderType.MARKET
        quantity = float(rng.integers(1, 20))
        price = (
            round(max(0.01, mid + rng.normal(0, 2.0)), 2)
            if order_type == OrderType.LIMIT
            else None
        )
        order_id = f"o{step}"

        py_fills = py_engine.match(
            Order(order_id, side, order_type, quantity, float(step), price),
            py_book,
            float(step),
            step * 10,
            f"t{step}",
        )
        native_fills = native_engine.match(
            Order(order_id, side, order_type, quantity, float(step), price),
            native_book,
            float(step),
            step * 10,
            f"t{step}",
        )

        assert_fills_equal(py_fills, native_fills)
        assert_books_equal(py_book, native_book)
        live_ids.append(order_id)
