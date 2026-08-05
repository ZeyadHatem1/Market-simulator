import pytest

from market_sim.portfolio.risk import RiskState


def test_initial_state():
    risk = RiskState(peak_equity=10_000.0)
    assert risk.current_drawdown == 0.0
    assert risk.max_drawdown == 0.0


def test_peak_equity_rises_with_new_highs():
    risk = RiskState(peak_equity=10_000.0)
    risk.update(10_500.0)
    assert risk.peak_equity == 10_500.0
    assert risk.current_drawdown == 0.0


def test_drawdown_computed_relative_to_peak():
    risk = RiskState(peak_equity=10_000.0)
    risk.update(9_000.0)
    assert risk.current_drawdown == pytest.approx(0.1)
    assert risk.max_drawdown == pytest.approx(0.1)


def test_max_drawdown_persists_after_recovery():
    risk = RiskState(peak_equity=10_000.0)
    risk.update(9_000.0)  # 10% drawdown
    risk.update(9_800.0)  # recovers to 2% drawdown
    assert risk.current_drawdown == pytest.approx(0.02)
    assert risk.max_drawdown == pytest.approx(0.1)


def test_new_peak_after_drawdown_resets_current_drawdown():
    risk = RiskState(peak_equity=10_000.0)
    risk.update(9_000.0)
    risk.update(11_000.0)
    assert risk.current_drawdown == 0.0
    assert risk.peak_equity == 11_000.0
    assert risk.max_drawdown == pytest.approx(0.1)


def test_exposure_is_absolute_notional():
    assert RiskState.exposure(quantity=-5.0, price=100.0) == 500.0
    assert RiskState.exposure(quantity=5.0, price=100.0) == 500.0
    assert RiskState.exposure(quantity=0.0, price=100.0) == 0.0
