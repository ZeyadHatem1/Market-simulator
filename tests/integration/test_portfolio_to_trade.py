import pytest

from market_sim.core.engine.runtime_engine import RuntimeEngine
from market_sim.core.models import EventType, OrderType, Side
from market_sim.events import market_update, order_submit
from market_sim.exchange import build_exchange
from market_sim.portfolio import PortfolioManager
from market_sim.strategies import MomentumStrategy


def test_two_strategies_trade_independently_with_isolated_portfolios():
    """
    Two MomentumStrategy instances (different lookback) both plugged into the
    same exchange, each with its own Portfolio under one PortfolioManager.
    Proves fills are attributed to the right strategy's portfolio only, and
    that PortfolioManager.on_market_update/on_fill fan-out is sufficient
    wiring — no strategy_id needed on the Event schema.
    """
    runtime = RuntimeEngine()
    book, _trade_log, gateway = build_exchange(runtime)
    manager = PortfolioManager()

    strategy_a = MomentumStrategy(
        strategy_id="fast",
        initial_cash=10_000.0,
        clock=runtime.clock,
        order_id_factory=runtime.next_order_id,
        lookback=1,
        trade_size=5.0,
    )
    portfolio_a = manager.register_strategy("fast", initial_cash=10_000.0)

    strategy_b = MomentumStrategy(
        strategy_id="slow",
        initial_cash=20_000.0,
        clock=runtime.clock,
        order_id_factory=runtime.next_order_id,
        lookback=3,
        trade_size=8.0,
    )
    portfolio_b = manager.register_strategy("slow", initial_cash=20_000.0)

    def make_market_update_handler(strategy, portfolio):
        def handler(event):
            for order_event in strategy.on_market_update(event):
                runtime.queue.push(order_event)
                portfolio.track_order(order_event.data["order_id"])

        return handler

    runtime.loop.register_handler(
        EventType.MARKET_UPDATE, make_market_update_handler(strategy_a, portfolio_a)
    )
    runtime.loop.register_handler(
        EventType.MARKET_UPDATE, make_market_update_handler(strategy_b, portfolio_b)
    )
    runtime.loop.register_handler(EventType.MARKET_UPDATE, manager.on_market_update)

    runtime.loop.register_handler(EventType.TRADE_EXECUTION, strategy_a.on_fill)
    runtime.loop.register_handler(EventType.TRADE_EXECUTION, strategy_b.on_fill)
    runtime.loop.register_handler(EventType.TRADE_EXECUTION, manager.on_fill)

    # Standing liquidity both strategies' eventual BUY market orders can cross
    # against. Rising prices mean "fast" (lookback=1) re-signals BUY on every
    # tick once its 1-tick window is full (ticks 2, 3, 4 -> 3 * 5 = 15
    # units), while "slow" (lookback=3) only signals once its window fills
    # (tick 4 -> 8 units) -- 23 units total, sized to exactly deplete this
    # resting order so the book ends up empty.
    runtime.queue.push(
        order_submit(
            timestamp=0.0,
            sequence=runtime.clock.next_sequence(),
            order_id=runtime.next_order_id(),
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            price=101.0,
            quantity=23.0,
        )
    )

    for i, price in enumerate([100.0, 101.0, 102.0, 105.0]):
        runtime.queue.push(
            market_update(
                timestamp=float(i + 1),
                sequence=runtime.clock.next_sequence(),
                price=price,
                instrument="SIM",
            )
        )

    runtime.start()

    assert gateway.rejected_orders == []
    assert book.is_empty()

    assert strategy_a.position == 15.0
    assert portfolio_a.position_quantity == 15.0
    assert portfolio_a.cash == pytest.approx(10_000.0 - 101.0 * 15.0)

    assert strategy_b.position == 8.0
    assert portfolio_b.position_quantity == 8.0
    assert portfolio_b.cash == pytest.approx(20_000.0 - 101.0 * 8.0)

    # each portfolio only ever saw its own fill
    assert len(portfolio_a.equity_curve) > 0
    assert len(portfolio_b.equity_curve) > 0
