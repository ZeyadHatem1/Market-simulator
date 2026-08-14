import numpy as np

from market_sim.core.config import ShockConfig


class ShockModel:
    """
    Generates a liquidity-multiplier path via a Poisson-triggered shock
    process: shocks arrive at rate `shock_intensity` (expected shocks per
    unit time); each shock has a magnitude (drawn uniformly from
    `magnitude_range`, applied as a multiplier on normal liquidity — smaller
    means a more severe shock) and a duration in steps (drawn uniformly from
    `duration_range`). Overlapping shocks combine via the minimum multiplier
    (the worst active shock wins).

    This models liquidity shocks only — price jumps already live in
    JumpDiffusionProcess (market/generators), a different concept from a
    transient liquidity withdrawal layered onto an already-running
    simulation. See docs/decisions/ADR-001-jump-diffusion-placement.md.

    Like PoissonArrivalProcess, this has no MARKET_UPDATE-style event to
    wrap shocks in and no clock to advance, and deliberately does not touch
    OrderBook/MatchingEngine itself — it only produces the multiplier path;
    application (e.g. scaling the liquidity SlippageModel sees) is left to
    the consumer (Monte Carlo stress tests, notebooks). See
    docs/decisions/ADR-006-shock-model-placement.md.

    Determinism guarantee: all randomness flows through a seeded numpy RNG
    sourced from ShockConfig.seed. Same config = identical shock path.
    """

    def __init__(self, config: ShockConfig) -> None:
        self._config = config

    def liquidity_multiplier_path(self) -> np.ndarray:
        """
        Return a length-n_steps array of liquidity multipliers, one per step.
        1.0 = normal liquidity; values below 1.0 indicate an active shock.
        Pure function of the seeded config — fresh RNG each call, no clock
        dependency, same result on every call for a given config.
        """
        cfg = self._config
        rng = np.random.default_rng(cfg.seed)
        multiplier = np.ones(cfg.n_steps)

        total_time = cfg.n_steps * cfg.dt
        n_shocks = rng.poisson(cfg.shock_intensity * total_time)

        for _ in range(n_shocks):
            start = rng.integers(0, cfg.n_steps)
            duration = rng.integers(cfg.duration_range[0], cfg.duration_range[1] + 1)
            magnitude = rng.uniform(cfg.magnitude_range[0], cfg.magnitude_range[1])
            end = min(start + duration, cfg.n_steps)
            multiplier[start:end] = np.minimum(multiplier[start:end], magnitude)

        return multiplier
