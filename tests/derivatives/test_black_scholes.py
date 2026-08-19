import numpy as np
import pytest

from market_sim.derivatives.black_scholes import (
    OptionType,
    black_scholes_greeks,
    black_scholes_price,
)

# Hull, "Options, Futures, and Other Derivatives": S=42, K=40, r=10%, sigma=20%,
# T=0.5 years, no dividends -> call ~= 4.76, put ~= 0.81. An external,
# independently-published reference, not re-derived from this implementation.
HULL_S, HULL_K, HULL_T, HULL_R, HULL_SIGMA = 42.0, 40.0, 0.5, 0.10, 0.20


def test_call_price_matches_textbook_reference():
    price = black_scholes_price(
        HULL_S, HULL_K, HULL_T, HULL_R, HULL_SIGMA, OptionType.CALL
    )
    assert price == pytest.approx(4.76, abs=0.01)


def test_put_price_matches_textbook_reference():
    price = black_scholes_price(
        HULL_S, HULL_K, HULL_T, HULL_R, HULL_SIGMA, OptionType.PUT
    )
    assert price == pytest.approx(0.81, abs=0.01)


def test_put_call_parity_holds():
    # C - P = S*e^{-qT} - K*e^{-rT}, a structural identity independent of the
    # specific pricing formula's internals.
    S, K, T, r, sigma, q = 55.0, 60.0, 0.75, 0.03, 0.35, 0.02
    call = black_scholes_price(S, K, T, r, sigma, OptionType.CALL, q)
    put = black_scholes_price(S, K, T, r, sigma, OptionType.PUT, q)
    expected_diff = S * np.exp(-q * T) - K * np.exp(-r * T)
    assert (call - put) == pytest.approx(expected_diff)


@pytest.mark.parametrize(
    "S,K,T,sigma",
    [
        (0.0, 100.0, 1.0, 0.2),
        (100.0, -1.0, 1.0, 0.2),
        (100.0, 100.0, 0.0, 0.2),
        (100.0, 100.0, 1.0, -0.1),
    ],
)
def test_price_validates_inputs(S, K, T, sigma):
    with pytest.raises(ValueError):
        black_scholes_price(S, K, T, 0.05, sigma, OptionType.CALL)


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
def test_delta_matches_finite_difference(option_type):
    S, K, T, r, sigma = 100.0, 105.0, 0.8, 0.04, 0.25
    h = 1e-4
    price_up = black_scholes_price(S + h, K, T, r, sigma, option_type)
    price_down = black_scholes_price(S - h, K, T, r, sigma, option_type)
    delta_fd = (price_up - price_down) / (2 * h)

    greeks = black_scholes_greeks(S, K, T, r, sigma, option_type)
    assert greeks.delta == pytest.approx(delta_fd, abs=1e-4)


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
def test_gamma_matches_finite_difference(option_type):
    S, K, T, r, sigma = 100.0, 95.0, 1.2, 0.03, 0.3
    h = 1e-2
    price_up = black_scholes_price(S + h, K, T, r, sigma, option_type)
    price_mid = black_scholes_price(S, K, T, r, sigma, option_type)
    price_down = black_scholes_price(S - h, K, T, r, sigma, option_type)
    gamma_fd = (price_up - 2 * price_mid + price_down) / h**2

    greeks = black_scholes_greeks(S, K, T, r, sigma, option_type)
    assert greeks.gamma == pytest.approx(gamma_fd, abs=1e-3)


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
def test_vega_matches_finite_difference(option_type):
    S, K, T, r, sigma = 100.0, 100.0, 0.5, 0.05, 0.2
    h = 1e-4
    price_up = black_scholes_price(S, K, T, r, sigma + h, option_type)
    price_down = black_scholes_price(S, K, T, r, sigma - h, option_type)
    vega_fd = (price_up - price_down) / (2 * h)

    greeks = black_scholes_greeks(S, K, T, r, sigma, option_type)
    assert greeks.vega == pytest.approx(vega_fd, abs=1e-4)


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
def test_rho_matches_finite_difference(option_type):
    S, K, T, r, sigma = 100.0, 100.0, 0.5, 0.05, 0.2
    h = 1e-4
    price_up = black_scholes_price(S, K, T, r + h, sigma, option_type)
    price_down = black_scholes_price(S, K, T, r - h, sigma, option_type)
    rho_fd = (price_up - price_down) / (2 * h)

    greeks = black_scholes_greeks(S, K, T, r, sigma, option_type)
    assert greeks.rho == pytest.approx(rho_fd, abs=1e-4)


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
def test_theta_matches_finite_difference(option_type):
    # theta = -dPrice/dT (time decay as calendar time passes, T shrinks)
    S, K, T, r, sigma = 100.0, 100.0, 0.5, 0.05, 0.2
    h = 1e-4
    price_up = black_scholes_price(S, K, T + h, r, sigma, option_type)
    price_down = black_scholes_price(S, K, T - h, r, sigma, option_type)
    theta_fd = -(price_up - price_down) / (2 * h)

    greeks = black_scholes_greeks(S, K, T, r, sigma, option_type)
    assert greeks.theta == pytest.approx(theta_fd, abs=1e-3)


def test_put_delta_equals_call_delta_minus_one():
    # put-call parity's derivative w.r.t. S: delta_call - delta_put = e^{-qT}
    S, K, T, r, sigma, q = 100.0, 90.0, 1.0, 0.05, 0.2, 0.0
    call_greeks = black_scholes_greeks(S, K, T, r, sigma, OptionType.CALL, q)
    put_greeks = black_scholes_greeks(S, K, T, r, sigma, OptionType.PUT, q)
    assert (call_greeks.delta - put_greeks.delta) == pytest.approx(1.0)
