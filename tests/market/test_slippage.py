import pytest

from market_sim.core.config import SlippageConfig
from market_sim.core.models import Side
from market_sim.market.microstructure import SlippageModel, slippage_model_from_config


def test_bps_scales_linearly_with_order_size_relative_to_liquidity():
    model = SlippageModel(coefficient=10.0)
    assert model.bps(order_quantity=100.0, available_liquidity=100.0) == 10.0
    assert model.bps(order_quantity=50.0, available_liquidity=100.0) == 5.0
    assert model.bps(order_quantity=200.0, available_liquidity=100.0) == 20.0


def test_bps_zero_when_no_liquidity():
    model = SlippageModel(coefficient=10.0)
    assert model.bps(order_quantity=100.0, available_liquidity=0.0) == 0.0


def test_apply_moves_buy_price_up():
    model = SlippageModel(coefficient=100.0)  # 1% at full depth, for easy arithmetic
    price = model.apply(
        reference_price=100.0,
        order_quantity=100.0,
        available_liquidity=100.0,
        side=Side.BUY,
    )
    assert price == pytest.approx(101.0)


def test_apply_moves_sell_price_down():
    model = SlippageModel(coefficient=100.0)
    price = model.apply(
        reference_price=100.0,
        order_quantity=100.0,
        available_liquidity=100.0,
        side=Side.SELL,
    )
    assert price == pytest.approx(99.0)


def test_apply_with_zero_coefficient_is_a_no_op():
    model = SlippageModel(coefficient=0.0)
    price = model.apply(
        reference_price=100.0,
        order_quantity=50.0,
        available_liquidity=10.0,
        side=Side.BUY,
    )
    assert price == 100.0


def test_slippage_model_from_config():
    model = slippage_model_from_config(SlippageConfig(coefficient=7.5))
    assert model.coefficient == 7.5


def test_negative_coefficient_rejected():
    with pytest.raises(ValueError):
        SlippageConfig(coefficient=-1.0)
