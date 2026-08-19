from dataclasses import dataclass

import numpy as np

from market_sim.derivatives.black_scholes import OptionType
from market_sim.derivatives.implied_volatility import implied_volatility


@dataclass
class VolSurface:
    strikes: np.ndarray
    maturities: np.ndarray
    implied_vols: np.ndarray  # shape (len(maturities), len(strikes))


def build_vol_surface(
    market_prices: np.ndarray,
    strikes,
    maturities,
    S: float,
    r: float,
    option_type: OptionType,
    q: float = 0.0,
) -> VolSurface:
    """
    Inverts a grid of market option prices (shape (len(maturities),
    len(strikes))) into a grid of implied vols via implied_volatility(),
    one solve per (maturity, strike) cell.

    Deliberately takes market_prices as plain input rather than generating
    them from an assumed smile/skew shape: this simulator has no real
    options market data, but a caller can synthesize an example grid by
    calling black_scholes_price with a hand-picked vol smile and feeding
    the resulting prices back in here as a round-trip demonstration —
    keeping this function equally usable for that and for real market data,
    rather than baking in an invented smile parameterization.
    """
    strikes = np.asarray(strikes, dtype=float)
    maturities = np.asarray(maturities, dtype=float)
    market_prices = np.asarray(market_prices, dtype=float)

    expected_shape = (len(maturities), len(strikes))
    if market_prices.shape != expected_shape:
        raise ValueError(
            f"market_prices must have shape (len(maturities), len(strikes)) = "
            f"{expected_shape}, got {market_prices.shape}"
        )

    implied_vols = np.empty_like(market_prices)
    for i, T in enumerate(maturities):
        for j, K in enumerate(strikes):
            implied_vols[i, j] = implied_volatility(
                market_prices[i, j], S, float(K), float(T), r, option_type, q
            )

    return VolSurface(strikes=strikes, maturities=maturities, implied_vols=implied_vols)
