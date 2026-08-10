from market_sim.portfolio.pnl import PnLTracker


def test_initial_state():
    tracker = PnLTracker(initial_cash=10_000.0)
    assert tracker.realized_pnl == 0.0
    assert tracker.equity_curve == []
    assert tracker.total_pnl == 0.0


def test_add_realized_accumulates():
    tracker = PnLTracker(initial_cash=10_000.0)
    tracker.add_realized(50.0)
    tracker.add_realized(-20.0)
    assert tracker.realized_pnl == 30.0


def test_add_realized_appends_to_history():
    tracker = PnLTracker(initial_cash=10_000.0)
    tracker.add_realized(0.0)
    tracker.add_realized(50.0)
    tracker.add_realized(-20.0)
    assert tracker.realized_pnl_history == [0.0, 50.0, -20.0]


def test_record_equity_appends_to_curve():
    tracker = PnLTracker(initial_cash=10_000.0)
    tracker.record_equity(1.0, 10_000.0)
    tracker.record_equity(2.0, 10_050.0)
    assert tracker.equity_curve == [(1.0, 10_000.0), (2.0, 10_050.0)]


def test_total_pnl_uses_latest_equity_sample():
    tracker = PnLTracker(initial_cash=10_000.0)
    tracker.record_equity(1.0, 10_500.0)
    assert tracker.total_pnl == 500.0
    tracker.record_equity(2.0, 9_800.0)
    assert tracker.total_pnl == -200.0
