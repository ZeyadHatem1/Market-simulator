import numpy as np
import pytest

from market_sim.events import market_update
from market_sim.exchange.orderbook import OrderBook
from market_sim.market.liquidity import SyntheticLiquidityProvider


def _tick(price: float, sequence: int = 0, timestamp: float = 1.0):
    return market_update(
        timestamp=timestamp, sequence=sequence, price=price, instrument="SIM"
    )


def test_on_market_update_inserts_two_sided_quote():
    book = OrderBook()
    lp = SyntheticLiquidityProvider(book, spread_bps=20.0, quantity=1_000.0)

    lp.on_market_update(_tick(price=100.0))

    assert book.best_bid().price == pytest.approx(99.8)
    assert book.best_ask().price == pytest.approx(100.2)
    assert book.best_bid().quantity == 1_000.0
    assert book.best_ask().quantity == 1_000.0


def test_bid_ask_liquidity_reflects_quantity():
    book = OrderBook()
    lp = SyntheticLiquidityProvider(book, quantity=500.0)

    lp.on_market_update(_tick(price=50.0))

    assert book.bid_liquidity() == pytest.approx(500.0)
    assert book.ask_liquidity() == pytest.approx(500.0)


def test_successive_ticks_use_unique_order_ids():
    book = OrderBook()
    lp = SyntheticLiquidityProvider(book, quantity=100.0)

    lp.on_market_update(_tick(price=100.0, sequence=0))
    lp.on_market_update(_tick(price=101.0, sequence=1))

    assert book.bid_depth() == 2
    assert book.ask_depth() == 2


def test_no_multiplier_path_always_full_quantity():
    book = OrderBook()
    lp = SyntheticLiquidityProvider(book, quantity=1_000.0)

    for i in range(5):
        lp.on_market_update(_tick(price=100.0, sequence=i))

    assert book.bid_liquidity() == pytest.approx(5_000.0)


def test_multiplier_path_scales_quantity_per_step():
    book = OrderBook()
    path = np.array([1.0, 0.5, 0.1])
    lp = SyntheticLiquidityProvider(
        book, quantity=1_000.0, liquidity_multiplier_path=path
    )

    lp.on_market_update(_tick(price=100.0, sequence=0))
    assert book.bid_liquidity() == pytest.approx(1_000.0)

    lp.on_market_update(_tick(price=100.0, sequence=1))
    assert book.bid_liquidity() == pytest.approx(1_500.0)

    lp.on_market_update(_tick(price=100.0, sequence=2))
    assert book.bid_liquidity() == pytest.approx(1_600.0)


def test_multiplier_path_clamps_to_last_value_beyond_length():
    book = OrderBook()
    path = np.array([0.2])
    lp = SyntheticLiquidityProvider(
        book, quantity=1_000.0, liquidity_multiplier_path=path
    )

    for i in range(3):
        lp.on_market_update(_tick(price=100.0, sequence=i))

    assert book.bid_liquidity() == pytest.approx(600.0)
    assert book.ask_liquidity() == pytest.approx(600.0)
