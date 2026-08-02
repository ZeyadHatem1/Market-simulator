from .config import JumpDiffusionConfig, OUConfig, SimConfig


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