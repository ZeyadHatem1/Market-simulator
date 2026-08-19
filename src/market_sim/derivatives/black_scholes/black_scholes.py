from dataclasses import dataclass
from enum import Enum

import numpy as np
from scipy.stats import norm


class OptionType(Enum):
    CALL = "CALL"
    PUT = "PUT"


@dataclass
class Greeks:
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


def _d1_d2(
    S: float, K: float, T: float, r: float, sigma: float, q: float
) -> tuple[float, float]:
    if S <= 0:
        raise ValueError(f"S must be > 0, got {S}")
    if K <= 0:
        raise ValueError(f"K must be > 0, got {K}")
    if T <= 0:
        raise ValueError(f"T must be > 0, got {T}")
    if sigma <= 0:
        raise ValueError(f"sigma must be > 0, got {sigma}")

    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return d1, d2


def black_scholes_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType,
    q: float = 0.0,
) -> float:
    """
    Black-Scholes-Merton European option price under a continuous dividend
    yield q (q=0.0 reduces to the plain Black-Scholes formula).

    S: spot price, K: strike, T: time to maturity in years, r: risk-free
    rate, sigma: annualized volatility.
    """
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    if option_type == OptionType.CALL:
        return float(
            S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        )
    return float(
        K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)
    )


def black_scholes_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType,
    q: float = 0.0,
) -> Greeks:
    """
    Closed-form Greeks for the same contract black_scholes_price prices.
    theta and rho are expressed per unit of T (i.e. per year, matching the
    same annualized convention T/r/sigma already use throughout this
    module) — divide by 365 for a per-calendar-day figure if needed, same
    "caller supplies the unit conversion" convention analytics.metrics uses
    for periods_per_year rather than assuming one.
    """
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    pdf_d1 = norm.pdf(d1)
    sqrt_T = np.sqrt(T)

    gamma = float(np.exp(-q * T) * pdf_d1 / (S * sigma * sqrt_T))
    vega = float(S * np.exp(-q * T) * pdf_d1 * sqrt_T)

    if option_type == OptionType.CALL:
        delta = float(np.exp(-q * T) * norm.cdf(d1))
        theta = float(
            -S * np.exp(-q * T) * pdf_d1 * sigma / (2 * sqrt_T)
            - r * K * np.exp(-r * T) * norm.cdf(d2)
            + q * S * np.exp(-q * T) * norm.cdf(d1)
        )
        rho = float(K * T * np.exp(-r * T) * norm.cdf(d2))
    else:
        delta = float(-np.exp(-q * T) * norm.cdf(-d1))
        theta = float(
            -S * np.exp(-q * T) * pdf_d1 * sigma / (2 * sqrt_T)
            + r * K * np.exp(-r * T) * norm.cdf(-d2)
            - q * S * np.exp(-q * T) * norm.cdf(-d1)
        )
        rho = float(-K * T * np.exp(-r * T) * norm.cdf(-d2))

    return Greeks(delta=delta, gamma=gamma, vega=vega, theta=theta, rho=rho)
