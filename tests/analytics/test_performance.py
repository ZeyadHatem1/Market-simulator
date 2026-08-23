import pytest

from market_sim.analytics.performance import build_report, compare
from market_sim.events import market_update, trade_execution
from market_sim.portfolio import Portfolio, PortfolioManager


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


def test_build_report_reflects_portfolio_state():
    portfolio = Portfolio(strategy_id="s1", initial_cash=10_000.0)
    portfolio.track_order("buy-1")
    portfolio.on_fill(
        make_fill(100.0, 10.0, buy_order_id="buy-1", sell_order_id="other")
    )
    portfolio.on_market_update(make_tick(110.0, timestamp=2.0))

    report = build_report(portfolio, periods_per_year=252)

    assert report.strategy_id == "s1"
    assert report.equity == pytest.approx(portfolio.equity)
    assert report.realized_pnl == 0.0
    assert report.unrealized_pnl == pytest.approx(100.0)
    assert report.win_rate == 0.0  # no closed trade yet


def test_compare_returns_one_row_per_strategy():
    manager = PortfolioManager()
    fast = manager.register_strategy("fast", initial_cash=10_000.0)
    slow = manager.register_strategy("slow", initial_cash=20_000.0)

    fast.track_order("f1")
    fast.on_fill(make_fill(100.0, 10.0, buy_order_id="f1", sell_order_id="other-1"))
    manager.on_market_update(make_tick(105.0, timestamp=1.0))

    slow.track_order("s1")
    slow.on_fill(make_fill(50.0, 4.0, buy_order_id="other-2", sell_order_id="s1"))
    manager.on_market_update(make_tick(48.0, timestamp=2.0))

    result = compare(manager, periods_per_year=252)

    assert set(result.index) == {"fast", "slow"}
    assert result.loc["fast", "equity"] == pytest.approx(fast.equity)
    assert result.loc["slow", "equity"] == pytest.approx(slow.equity)
