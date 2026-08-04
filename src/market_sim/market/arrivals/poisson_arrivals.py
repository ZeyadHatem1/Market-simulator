import numpy as np

from market_sim.core.config import PoissonArrivalConfig


class PoissonArrivalProcess:
    """
    Generates order arrival timestamps via a homogeneous Poisson process with
    rate `rate` (expected arrivals per unit time). Inter-arrival gaps are iid
    Exponential(rate); arrival times are their cumulative sum.

    This process determines only *when* orders arrive — not their content
    (side, quantity, price), which is a strategy concern, and not what happens
    once one arrives (validation/routing/matching), which stays in
    exchange/gateway. See docs/decisions/ADR-003-poisson-arrivals-placement.md.

    Unlike the generators in market/generators, this has no MARKET_UPDATE-style
    event to wrap arrivals in and no clock to advance, so both methods below are
    pure: each draws from a fresh seeded RNG and returns the same result on
    every call for a given config.

    Determinism guarantee: all randomness flows through a seeded numpy RNG
    sourced from PoissonArrivalConfig.seed. Same config = identical arrivals.
    """

    def __init__(self, config: PoissonArrivalConfig) -> None:
        self._config = config

    def inter_arrival_times(self) -> np.ndarray:
        """iid Exponential(rate) gaps between consecutive arrivals."""
        cfg = self._config
        rng = np.random.default_rng(cfg.seed)
        return rng.exponential(scale=1.0 / cfg.rate, size=cfg.n_arrivals)

    def arrival_times(self) -> np.ndarray:
        """Cumulative arrival timestamps, strictly increasing."""
        return np.cumsum(self.inter_arrival_times())
