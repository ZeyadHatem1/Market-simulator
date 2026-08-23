import pytest

from market_sim.events import market_update, trade_execution
from market_sim.portfolio import Portfolio


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


# --- initial state ---


def test_initial_state():
    portfolio = Portfolio(strategy_id="s1", initial_cash=10_000.0)
    assert portfolio.cash == 10_000.0
    assert portfolio.position_quantity == 0.0
    assert portfolio.realized_pnl == 0.0
    assert portfolio.unrealized_pnl == 0.0
    assert portfolio.equity == 10_000.0
    assert portfolio.equity_curve == []


# --- fill attribution ---


def test_fill_for_tracked_order_updates_position_and_cash():
    portfolio = Portfolio(strategy_id="s1", initial_cash=10_000.0)
    portfolio.track_order("my-order")

    portfolio.on_fill(
        make_fill(100.0, 10.0, buy_order_id="my-order", sell_order_id="other")
    )

    assert portfolio.position_quantity == 10.0
    assert portfolio.cash == pytest.approx(10_000.0 - 1_000.0)


def test_fill_for_untracked_order_is_ignored():
    portfolio = Portfolio(strategy_id="s1", initial_cash=10_000.0)

    portfolio.on_fill(
        make_fill(100.0, 10.0, buy_order_id="not-mine", sell_order_id="also-not-mine")
    )

    assert portfolio.position_quantity == 0.0
    assert portfolio.cash == 10_000.0
    assert portfolio.equity_curve == []


def test_fill_for_tracked_sell_order_updates_position_and_cash():
    portfolio = Portfolio(strategy_id="s1", initial_cash=10_000.0)
    portfolio.track_order("my-sell")

    portfolio.on_fill(
        make_fill(50.0, 4.0, buy_order_id="other", sell_order_id="my-sell")
    )

    assert portfolio.position_quantity == -4.0
    assert portfolio.cash == pytest.approx(10_000.0 + 200.0)


# --- unrealized / realized pnl ---


def test_unrealized_pnl_after_price_moves():
    portfolio = Portfolio(strategy_id="s1", initial_cash=10_000.0)
    portfolio.track_order("my-order")
    portfolio.on_fill(
        make_fill(100.0, 10.0, buy_order_id="my-order", sell_order_id="other")
    )

    portfolio.on_market_update(make_tick(110.0, timestamp=2.0))

    assert portfolio.unrealized_pnl == pytest.approx(100.0)
    assert portfolio.equity == pytest.approx(10_000.0 - 1_000.0 + 10.0 * 110.0)


def test_realized_pnl_accumulates_on_closing_fill():
    portfolio = Portfolio(strategy_id="s1", initial_cash=10_000.0)
    portfolio.track_order("buy-order")
    portfolio.track_order("sell-order")

    portfolio.on_fill(
        make_fill(100.0, 10.0, buy_order_id="buy-order", sell_order_id="other-1")
    )
    portfolio.on_fill(
        make_fill(110.0, 10.0, buy_order_id="other-2", sell_order_id="sell-order")
    )

    assert portfolio.position_quantity == 0.0
    assert portfolio.realized_pnl == pytest.approx(100.0)


def test_realized_pnl_history_records_each_fills_realization():
    portfolio = Portfolio(strategy_id="s1", initial_cash=10_000.0)
    portfolio.track_order("buy-order")
    portfolio.track_order("sell-order")

    # opens a position: no realization yet
    portfolio.on_fill(
        make_fill(100.0, 10.0, buy_order_id="buy-order", sell_order_id="other-1")
    )
    # closes it at a profit
    portfolio.on_fill(
        make_fill(110.0, 10.0, buy_order_id="other-2", sell_order_id="sell-order")
    )

    assert portfolio.realized_pnl_history == [0.0, pytest.approx(100.0)]


# --- equity curve / drawdown ---


def test_market_update_records_equity_curve_sample():
    portfolio = Portfolio(strategy_id="s1", initial_cash=10_000.0)
    portfolio.on_market_update(make_tick(100.0, timestamp=1.0))
    assert portfolio.equity_curve == [(1.0, 10_000.0)]


def test_drawdown_tracks_through_losing_and_recovering_price_path():
    portfolio = Portfolio(strategy_id="s1", initial_cash=10_000.0)
    portfolio.track_order("my-order")
    portfolio.on_fill(
        make_fill(100.0, 10.0, buy_order_id="my-order", sell_order_id="other")
    )

    portfolio.on_market_update(make_tick(90.0, timestamp=2.0))  # equity down to 9,900
    assert portfolio.drawdown > 0
    peak_drawdown = portfolio.drawdown

    portfolio.on_market_update(make_tick(100.0, timestamp=3.0))  # equity back to 10,000
    assert portfolio.drawdown < peak_drawdown
    assert portfolio.max_drawdown == pytest.approx(peak_drawdown)


def test_exposure_reflects_position_notional():
    portfolio = Portfolio(strategy_id="s1", initial_cash=10_000.0)
    portfolio.track_order("my-order")
    portfolio.on_fill(
        make_fill(100.0, 10.0, buy_order_id="my-order", sell_order_id="other")
    )
    portfolio.on_market_update(make_tick(105.0, timestamp=2.0))
    assert portfolio.exposure == pytest.approx(1_050.0)
