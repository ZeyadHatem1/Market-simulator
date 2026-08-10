import pytest

from market_sim.analytics.statistics import correlation_matrix


def test_perfectly_correlated_curves():
    # both series return +10%, then -10% -- identical returns, different scale
    curves = {
        "a": [(1.0, 100.0), (2.0, 110.0), (3.0, 99.0)],
        "b": [(1.0, 200.0), (2.0, 220.0), (3.0, 198.0)],
    }
    corr = correlation_matrix(curves)
    assert corr.loc["a", "b"] == pytest.approx(1.0)


def test_perfectly_anti_correlated_curves():
    # a's returns: +10%, -10%. b's returns: -10%, +10% -- exact mirror.
    curves = {
        "a": [(1.0, 100.0), (2.0, 110.0), (3.0, 99.0)],
        "b": [(1.0, 100.0), (2.0, 90.0), (3.0, 99.0)],
    }
    corr = correlation_matrix(curves)
    assert corr.loc["a", "b"] == pytest.approx(-1.0, abs=1e-6)


def test_self_correlation_is_one():
    curves = {"a": [(1.0, 100.0), (2.0, 105.0), (3.0, 95.0)]}
    corr = correlation_matrix(curves)
    assert corr.loc["a", "a"] == pytest.approx(1.0)


def test_curves_of_different_length_do_not_crash():
    # "b" fills more often than "a", so its equity_curve has extra samples —
    # this must not require positionally-equal-length lists
    curves = {
        "a": [(1.0, 100.0), (2.0, 101.0), (3.0, 102.0)],
        "b": [(1.0, 200.0), (1.0, 201.0), (2.0, 202.0), (2.0, 199.0), (3.0, 205.0)],
    }
    corr = correlation_matrix(curves)
    assert corr.shape == (2, 2)


def test_duplicate_timestamp_keeps_last_value():
    # a fill and a tick landing on the same timestamp: the later entry
    # (post-fill equity) should be the one that survives alignment
    curves = {
        "a": [(1.0, 100.0), (2.0, 110.0), (2.0, 108.0), (3.0, 120.0)],
        "b": [(1.0, 100.0), (2.0, 108.0), (3.0, 120.0)],
    }
    corr = correlation_matrix(curves)
    # if the earlier (110.0) sample at t=2 had won instead of 108.0, the
    # return series would diverge from "b" and this wouldn't be ~1.0
    assert corr.loc["a", "b"] == pytest.approx(1.0, abs=1e-6)
