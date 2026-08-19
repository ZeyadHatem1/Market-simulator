import pytest

from market_sim.derivatives.black_scholes import OptionType, black_scholes_price
from market_sim.derivatives.implied_volatility import implied_volatility


@pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
@pytest.mark.parametrize("true_sigma", [0.10, 0.25, 0.60])
def test_round_trips_to_the_sigma_that_produced_the_price(option_type, true_sigma):
    S, K, T, r = 100.0, 105.0, 0.5, 0.03
    price = black_scholes_price(S, K, T, r, true_sigma, option_type)

    recovered_sigma = implied_volatility(price, S, K, T, r, option_type)

    assert recovered_sigma == pytest.approx(true_sigma, abs=1e-6)


def test_round_trip_with_dividend_yield():
    S, K, T, r, q, true_sigma = 100.0, 95.0, 1.0, 0.04, 0.02, 0.35
    price = black_scholes_price(S, K, T, r, true_sigma, OptionType.CALL, q)

    recovered_sigma = implied_volatility(price, S, K, T, r, OptionType.CALL, q)

    assert recovered_sigma == pytest.approx(true_sigma, abs=1e-6)


def test_unattainable_price_raises():
    # a call price above the underlying's spot violates a no-arbitrage
    # upper bound and is unattainable for any sigma
    with pytest.raises(ValueError):
        implied_volatility(
            200.0, S=100.0, K=100.0, T=1.0, r=0.05, option_type=OptionType.CALL
        )


def test_non_positive_price_raises():
    with pytest.raises(ValueError):
        implied_volatility(
            0.0, S=100.0, K=100.0, T=1.0, r=0.05, option_type=OptionType.CALL
        )
