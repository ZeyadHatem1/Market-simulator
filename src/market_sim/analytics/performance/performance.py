from dataclasses import dataclass

import pandas as pd

from market_sim.analytics.metrics import calmar, max_drawdown, sharpe, win_rate
from market_sim.portfolio import Portfolio, PortfolioManager


@dataclass
class PerformanceReport:
    strategy_id: str
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    sharpe: float
    max_drawdown: float
    calmar: float
    win_rate: float


def build_report(portfolio: Portfolio, periods_per_year: float) -> PerformanceReport:
    curve = portfolio.equity_curve
    return PerformanceReport(
        strategy_id=portfolio.strategy_id,
        equity=portfolio.equity,
        realized_pnl=portfolio.realized_pnl,
        unrealized_pnl=portfolio.unrealized_pnl,
        sharpe=sharpe(curve, periods_per_year),
        max_drawdown=max_drawdown(curve),
        calmar=calmar(curve, periods_per_year),
        win_rate=win_rate(portfolio.realized_pnl_history),
    )


def compare(manager: PortfolioManager, periods_per_year: float) -> pd.DataFrame:
    """One row per registered strategy, indexed by strategy_id, for side-by-side comparison."""
    reports = [
        build_report(manager.portfolio(strategy_id), periods_per_year)
        for strategy_id in manager.equity_curves()
    ]
    return pd.DataFrame([vars(r) for r in reports]).set_index("strategy_id")
