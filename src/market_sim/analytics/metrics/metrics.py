import numpy as np

EquityCurve = list[tuple[float, float]]


def _equity_values(equity_curve: EquityCurve) -> np.ndarray:
    return np.array([equity for _, equity in equity_curve], dtype=float)


def _returns(equity_curve: EquityCurve) -> np.ndarray:
    values = _equity_values(equity_curve)
    if len(values) < 2:
        return np.array([])
    return values[1:] / values[:-1] - 1.0


def sharpe(equity_curve: EquityCurve, periods_per_year: float, risk_free_rate: float = 0.0) -> float:
    """
    Annualized Sharpe ratio of period-over-period equity returns.
    periods_per_year converts per-step statistics to an annualized figure —
    the caller supplies it (e.g. 1/SimConfig.dt) rather than a hardcoded
    252, since the simulation's step size is configurable.
    """
    returns = _returns(equity_curve)
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free_rate / periods_per_year
    std = excess.std(ddof=1)
    if std == 0:
        return 0.0
    return float(excess.mean() / std * np.sqrt(periods_per_year))


def max_drawdown(equity_curve: EquityCurve) -> float:
    """Worst peak-to-trough decline as a positive fraction of the peak (0.2 == 20%)."""
    values = _equity_values(equity_curve)
    if len(values) == 0:
        return 0.0
    running_peak = np.maximum.accumulate(values)
    drawdowns = np.where(running_peak > 0, (running_peak - values) / running_peak, 0.0)
    return float(drawdowns.max())


def calmar(equity_curve: EquityCurve, periods_per_year: float) -> float:
    """Annualized return divided by max drawdown. 0.0 when there's no drawdown to divide by."""
    values = _equity_values(equity_curve)
    if len(values) < 2:
        return 0.0
    n_periods = len(values) - 1
    total_return = values[-1] / values[0] - 1.0
    annualized_return = (1.0 + total_return) ** (periods_per_year / n_periods) - 1.0
    mdd = max_drawdown(equity_curve)
    if mdd == 0:
        return 0.0
    return float(annualized_return / mdd)


def rolling_volatility(equity_curve: EquityCurve, window: int) -> list[float]:
    """Sample std of returns over a trailing window, one value per window-end period."""
    if window < 2:
        raise ValueError(f"window must be >= 2, got {window}")
    returns = _returns(equity_curve)
    if len(returns) < window:
        return []
    return [
        float(returns[i - window + 1 : i + 1].std(ddof=1)) for i in range(window - 1, len(returns))
    ]


def var_95(equity_curve: EquityCurve) -> float:
    """Historical 95% Value-at-Risk of period returns, as a positive loss fraction."""
    returns = _returns(equity_curve)
    if len(returns) == 0:
        return 0.0
    return float(-np.percentile(returns, 5))


def win_rate(realized_pnl_history: list[float]) -> float:
    """
    Fraction of closing fills that were profitable. Entries of exactly 0.0
    (a fill that only opened/added to a position, never closed one) are
    excluded from both the numerator and denominator — they're neither a
    win nor a loss.
    """
    closed = [amount for amount in realized_pnl_history if amount != 0.0]
    if not closed:
        return 0.0
    wins = sum(1 for amount in closed if amount > 0)
    return wins / len(closed)
