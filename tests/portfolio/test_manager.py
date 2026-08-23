import pytest

from market_sim.events import market_update, trade_execution
from market_sim.portfolio import PortfolioManager


def make_fill(
    price: float, quantity: float, buy_order_id: str, sell_order_id: str, timestamp=1.0
):
    return trade_execution(
        timestamp=timestamp,
        sequence=1,
        trade_id="trade-1",
        price=price,
        quantity=quantity,
        buy_order_id=buy_order_id,
        sell_order_id=sell_order_id,
    )


def make_tick(price: float, timestamp: float):
    return market_update(timestamp=timestamp, sequence=1, price=price, instrument="SIM")


def test_register_strategy_returns_a_portfolio():
    manager = PortfolioManager()
    portfolio = manager.register_strategy("momentum", initial_cash=10_000.0)
    assert portfolio.strategy_id == "momentum"
    assert manager.portfolio("momentum") is portfolio


def test_registering_same_strategy_id_twice_raises():
    manager = PortfolioManager()
    manager.register_strategy("momentum", initial_cash=10_000.0)
    with pytest.raises(ValueError):
        manager.register_strategy("momentum", initial_cash=5_000.0)


def test_on_market_update_fans_out_to_all_portfolios():
    manager = PortfolioManager()
    manager.register_strategy("a", initial_cash=10_000.0)
    manager.register_strategy("b", initial_cash=5_000.0)

    manager.on_market_update(make_tick(100.0, timestamp=1.0))

    assert manager.portfolio("a").equity_curve == [(1.0, 10_000.0)]
    assert manager.portfolio("b").equity_curve == [(1.0, 5_000.0)]


def test_on_fill_only_updates_the_owning_portfolio():
    manager = PortfolioManager()
    portfolio_a = manager.register_strategy("a", initial_cash=10_000.0)
    portfolio_b = manager.register_strategy("b", initial_cash=10_000.0)
    portfolio_a.track_order("a-order")

    manager.on_fill(
        make_fill(100.0, 10.0, buy_order_id="a-order", sell_order_id="counterparty")
    )

    assert portfolio_a.position_quantity == 10.0
    assert portfolio_b.position_quantity == 0.0


def test_equity_curves_returns_all_strategies():
    manager = PortfolioManager()
    manager.register_strategy("a", initial_cash=10_000.0)
    manager.register_strategy("b", initial_cash=5_000.0)
    manager.on_market_update(make_tick(100.0, timestamp=1.0))

    curves = manager.equity_curves()
    assert set(curves.keys()) == {"a", "b"}
    assert curves["a"] == [(1.0, 10_000.0)]
    assert curves["b"] == [(1.0, 5_000.0)]
