import pytest

from market_sim.analytics.metrics import (
    calmar,
    max_drawdown,
    rolling_volatility,
    sharpe,
    var_95,
    win_rate,
)


def curve(values: list[float]) -> list[tuple[float, float]]:
    return [(float(i), v) for i, v in enumerate(values)]


# --- sharpe ---

def test_sharpe_too_short_returns_zero():
    assert sharpe(curve([100.0]), periods_per_year=252) == 0.0
    assert sharpe(curve([100.0, 110.0]), periods_per_year=252) == 0.0


def test_sharpe_zero_variance_returns_zero():
    # constant 10% return every step -> zero std -> guarded, not division by zero
    assert sharpe(curve([100.0, 110.0, 121.0]), periods_per_year=252) == 0.0


def test_sharpe_matches_hand_computed_value():
    result = sharpe(curve([100.0, 110.0, 90.0]), periods_per_year=1)
    assert result == pytest.approx(-0.205289, abs=1e-5)


def test_sharpe_scales_with_sqrt_periods_per_year():
    one_period = sharpe(curve([100.0, 110.0, 90.0]), periods_per_year=1)
    four_periods = sharpe(curve([100.0, 110.0, 90.0]), periods_per_year=4)
    assert four_periods == pytest.approx(one_period * 2.0)  # sqrt(4) == 2


# --- max_drawdown ---

def test_max_drawdown_empty_curve_is_zero():
    assert max_drawdown([]) == 0.0


def test_max_drawdown_monotonic_increase_is_zero():
    assert max_drawdown(curve([100.0, 110.0, 120.0])) == 0.0


def test_max_drawdown_matches_hand_computed_value():
    result = max_drawdown(curve([100.0, 120.0, 90.0, 110.0]))
    assert result == pytest.approx(0.25)


# --- calmar ---

def test_calmar_no_drawdown_returns_zero():
    assert calmar(curve([100.0, 110.0, 120.0]), periods_per_year=252) == 0.0


def test_calmar_matches_hand_computed_value():
    result = calmar(curve([100.0, 120.0, 90.0, 110.0]), periods_per_year=4)
    assert result == pytest.approx(0.542033, abs=1e-5)


# --- rolling_volatility ---

def test_rolling_volatility_rejects_window_below_two():
    with pytest.raises(ValueError):
        rolling_volatility(curve([100.0, 101.0]), window=1)


def test_rolling_volatility_too_few_returns_is_empty():
    assert rolling_volatility(curve([100.0, 101.0]), window=3) == []


def test_rolling_volatility_produces_one_value_per_full_window():
    # 5 points -> 4 returns; window=2 -> 3 rolling windows
    result = rolling_volatility(curve([100.0, 110.0, 90.0, 115.0, 100.0]), window=2)
    assert len(result) == 3
    assert all(v >= 0.0 for v in result)


# --- var_95 ---

def test_var_95_empty_curve_is_zero():
    assert var_95([]) == 0.0


def test_var_95_matches_hand_computed_value():
    # returns derived from this curve: [0.05, -0.02, 0.03, -0.10, 0.01, 0.04, -0.01]
    values = [100.0]
    for r in [0.05, -0.02, 0.03, -0.10, 0.01, 0.04, -0.01]:
        values.append(values[-1] * (1 + r))
    result = var_95(curve(values))
    assert result == pytest.approx(0.076, abs=1e-3)


# --- win_rate ---

def test_win_rate_no_closed_trades_is_zero():
    assert win_rate([]) == 0.0
    assert win_rate([0.0, 0.0]) == 0.0


def test_win_rate_counts_only_nonzero_realizations():
    # 2 wins, 1 loss, 1 non-realizing (open/add) entry -> 2/3
    result = win_rate([0.0, 50.0, -20.0, 10.0])
    assert result == pytest.approx(2 / 3)


def test_win_rate_all_wins_is_one():
    assert win_rate([10.0, 5.0, 20.0]) == 1.0
