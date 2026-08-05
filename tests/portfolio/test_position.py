import pytest

from market_sim.core.models import Side
from market_sim.portfolio.positions import Position


def test_opening_a_long_position():
    position = Position()
    realized = position.apply_fill(Side.BUY, price=100.0, quantity=10.0)
    assert position.quantity == 10.0
    assert position.avg_price == 100.0
    assert realized == 0.0


def test_opening_a_short_position():
    position = Position()
    realized = position.apply_fill(Side.SELL, price=100.0, quantity=10.0)
    assert position.quantity == -10.0
    assert position.avg_price == 100.0
    assert realized == 0.0


def test_adding_to_a_long_position_updates_weighted_average_price():
    position = Position()
    position.apply_fill(Side.BUY, price=100.0, quantity=10.0)
    realized = position.apply_fill(Side.BUY, price=110.0, quantity=5.0)
    assert position.quantity == 15.0
    assert position.avg_price == pytest.approx((100.0 * 10 + 110.0 * 5) / 15)
    assert realized == 0.0


def test_partial_close_of_long_position_realizes_pnl_and_keeps_avg_price():
    position = Position()
    position.apply_fill(Side.BUY, price=100.0, quantity=10.0)
    realized = position.apply_fill(Side.SELL, price=110.0, quantity=4.0)
    assert position.quantity == 6.0
    assert position.avg_price == 100.0  # unchanged on a partial close
    assert realized == pytest.approx(40.0)  # 4 units * $10 gain


def test_full_close_of_long_position_zeroes_avg_price():
    position = Position()
    position.apply_fill(Side.BUY, price=100.0, quantity=10.0)
    realized = position.apply_fill(Side.SELL, price=90.0, quantity=10.0)
    assert position.quantity == 0.0
    assert position.avg_price == 0.0
    assert realized == pytest.approx(-100.0)  # 10 units * -$10 loss


def test_closing_a_short_position_realizes_pnl_with_correct_sign():
    position = Position()
    position.apply_fill(Side.SELL, price=110.0, quantity=5.0)
    realized = position.apply_fill(Side.BUY, price=105.0, quantity=5.0)
    assert position.quantity == 0.0
    assert realized == pytest.approx(25.0)  # shorted at 110, covered at 105


def test_flip_from_long_to_short_realizes_pnl_on_closed_portion_and_resets_avg_price():
    position = Position()
    position.apply_fill(Side.BUY, price=100.0, quantity=10.0)
    realized = position.apply_fill(Side.SELL, price=110.0, quantity=15.0)
    assert position.quantity == -5.0
    assert position.avg_price == 110.0  # the new short leg opens at the fill price
    assert realized == pytest.approx(100.0)  # closed 10 long units at $10 gain each


def test_flip_from_short_to_long_realizes_pnl_on_closed_portion_and_resets_avg_price():
    position = Position()
    position.apply_fill(Side.SELL, price=100.0, quantity=10.0)
    realized = position.apply_fill(Side.BUY, price=95.0, quantity=15.0)
    assert position.quantity == 5.0
    assert position.avg_price == 95.0
    assert realized == pytest.approx(50.0)  # covered 10 short units at $5 gain each
