import numpy as np
import pytest

from market_sim.derivatives.black_scholes import OptionType, black_scholes_price
from market_sim.derivatives.vol_surface import build_vol_surface


def test_recovers_a_known_smile_round_trip():
    S, r = 100.0, 0.03
    strikes = np.array([90.0, 100.0, 110.0])
    maturities = np.array([0.25, 1.0])

    # a simple synthetic smile: vol rises the further the strike is from spot
    def smile(K: float) -> float:
        return 0.20 + 0.002 * abs(K - S)

    market_prices = np.array(
        [
            [
                black_scholes_price(S, K, T, r, smile(K), OptionType.CALL)
                for K in strikes
            ]
            for T in maturities
        ]
    )

    surface = build_vol_surface(
        market_prices, strikes, maturities, S, r, OptionType.CALL
    )

    expected = np.array([[smile(K) for K in strikes] for _ in maturities])
    np.testing.assert_allclose(surface.implied_vols, expected, atol=1e-6)
    np.testing.assert_array_equal(surface.strikes, strikes)
    np.testing.assert_array_equal(surface.maturities, maturities)


def test_shape_mismatch_raises():
    strikes = np.array([90.0, 100.0, 110.0])
    maturities = np.array([0.25, 1.0])
    wrong_shape_prices = np.ones((3, 3))

    with pytest.raises(ValueError):
        build_vol_surface(
            wrong_shape_prices,
            strikes,
            maturities,
            S=100.0,
            r=0.03,
            option_type=OptionType.CALL,
        )


def test_output_shape_matches_grid():
    S, r = 100.0, 0.02
    strikes = np.array([95.0, 105.0])
    maturities = np.array([0.5])
    prices = np.array(
        [
            [black_scholes_price(S, K, T, r, 0.25, OptionType.PUT) for K in strikes]
            for T in maturities
        ]
    )

    surface = build_vol_surface(prices, strikes, maturities, S, r, OptionType.PUT)

    assert surface.implied_vols.shape == (1, 2)
