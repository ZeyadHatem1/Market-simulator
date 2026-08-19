from scipy.optimize import brentq

from market_sim.derivatives.black_scholes import OptionType, black_scholes_price


def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: OptionType,
    q: float = 0.0,
    sigma_bounds: tuple[float, float] = (1e-6, 5.0),
) -> float:
    """
    Solves for the sigma that makes black_scholes_price(..., sigma, ...)
    equal market_price, via Brent's method (bracketed root-finding — robust
    and derivative-free, unlike Newton-Raphson, which can diverge for deep
    in/out-of-the-money contracts where vega is tiny).

    Raises ValueError if market_price isn't attainable for any sigma in
    sigma_bounds (e.g. a price that violates a no-arbitrage bound, or a
    genuinely higher/lower implied vol than the default (0.0001%, 500%)
    search range covers).
    """
    if market_price <= 0:
        raise ValueError(f"market_price must be > 0, got {market_price}")

    def objective(sigma: float) -> float:
        return black_scholes_price(S, K, T, r, sigma, option_type, q) - market_price

    lo, hi = sigma_bounds
    f_lo, f_hi = objective(lo), objective(hi)
    if f_lo * f_hi > 0:
        raise ValueError(
            f"market_price {market_price} not attainable for sigma in {sigma_bounds} "
            f"(S={S}, K={K}, T={T}, r={r}, q={q})"
        )

    return brentq(objective, lo, hi)
