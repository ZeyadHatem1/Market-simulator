from .config import SimConfig


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