from .config import (
    JumpDiffusionConfig,
    OUConfig,
    PoissonArrivalConfig,
    RegimeConfig,
    ShockConfig,
    SimConfig,
    SlippageConfig,
)


def default_config() -> SimConfig:
    """
    Sensible default simulation configuration for quick testing and notebooks.

    mu=0.05:    5% annualized drift
    sigma=0.20: 20% annualized volatility (typical equity ballpark)
    dt=1/252:   one trading day per step (252 trading days/year)
    n_steps=252: one full simulated trading year
    """
    return SimConfig(
        instrument="SIM",
        initial_price=100.0,
        mu=0.05,
        sigma=0.20,
        n_steps=252,
        dt=1 / 252,
        seed=42,
        initial_capital=100_000.0,
    )


def default_ou_config() -> OUConfig:
    """
    Sensible default Ornstein-Uhlenbeck configuration for quick testing and notebooks.

    theta=5.0:  moderately fast reversion toward mu
    mu=100.0:   long-run mean level
    sigma=2.0:  volatility around the mean
    dt=1/252:   one trading day per step (252 trading days/year)
    n_steps=252: one full simulated trading year
    """
    return OUConfig(
        instrument="SIM",
        initial_value=100.0,
        theta=5.0,
        mu=100.0,
        sigma=2.0,
        n_steps=252,
        dt=1 / 252,
        seed=42,
    )


def default_jump_diffusion_config() -> JumpDiffusionConfig:
    """
    Sensible default Merton jump-diffusion configuration for quick testing and notebooks.

    mu=0.05, sigma=0.20: same diffusion assumptions as the plain GBM default
    jump_intensity=1.0:  ~1 jump per simulated year on average
    jump_mean=-0.02, jump_std=0.05: jumps skew slightly negative (crash risk), moderate size
    """
    return JumpDiffusionConfig(
        instrument="SIM",
        initial_price=100.0,
        mu=0.05,
        sigma=0.20,
        jump_intensity=1.0,
        jump_mean=-0.02,
        jump_std=0.05,
        n_steps=252,
        dt=1 / 252,
        seed=42,
    )


def default_poisson_arrival_config() -> PoissonArrivalConfig:
    """
    Sensible default Poisson order-arrival configuration for quick testing and notebooks.

    rate=10.0:    10 order arrivals per unit time on average
    n_arrivals=252: matches the one-trading-year step count used elsewhere
    """
    return PoissonArrivalConfig(rate=10.0, n_arrivals=252, seed=42)


def default_regime_config() -> RegimeConfig:
    """
    Sensible default two-regime (low/high volatility) configuration for quick
    testing and notebooks.

    low_vol:  mu=0.05, sigma=0.15 — calm market drifting up gently
    high_vol: mu=0.0,  sigma=0.50 — turbulent, no net drift
    Transition matrix is sticky (regimes persist rather than flickering every
    step): 95% chance of staying in the current regime each step, 5% chance
    of switching.
    """
    return RegimeConfig(
        instrument="SIM",
        initial_price=100.0,
        regimes={
            "low_vol": (0.05, 0.15),
            "high_vol": (0.0, 0.50),
        },
        transition_matrix=[
            [0.95, 0.05],
            [0.05, 0.95],
        ],
        initial_regime="low_vol",
        n_steps=252,
        dt=1 / 252,
        seed=42,
    )


def default_shock_config() -> ShockConfig:
    """
    Sensible default liquidity-shock configuration for quick testing and
    notebooks.

    shock_intensity=2.0: ~2 shock events per simulated year on average.
    magnitude_range=(0.1, 0.4): during a shock, liquidity drops to 10-40% of
    normal (a bigger number here means a milder shock).
    duration_range=(3, 15): a shock lasts 3-15 steps once it starts.
    """
    return ShockConfig(
        shock_intensity=2.0,
        magnitude_range=(0.1, 0.4),
        duration_range=(3, 15),
        n_steps=252,
        dt=1 / 252,
        seed=42,
    )


def default_slippage_config() -> SlippageConfig:
    """
    Sensible default slippage configuration for quick testing and notebooks.

    coefficient=5.0: a market order equal in size to all resting liquidity on the
    side it's crossing moves the fill price by 5bps against the aggressor.
    """
    return SlippageConfig(coefficient=5.0)
