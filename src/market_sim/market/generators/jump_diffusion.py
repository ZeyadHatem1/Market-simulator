import numpy as np

from market_sim.core.config import JumpDiffusionConfig
from market_sim.core.clock import SimulationClock
from market_sim.events import Event, market_update


class JumpDiffusionProcess:
    """
    Generates a synthetic price path via the Merton jump-diffusion model:
    continuous GBM diffusion plus a compound Poisson jump component.

        S(t+dt) = S(t) * exp(
            (mu - 0.5*sigma^2 - lambda*k) * dt + sigma*sqrt(dt)*Z + J
        )

    where:
        mu     = annualized drift
        sigma  = annualized diffusion volatility
        lambda = jump intensity (expected jumps per unit time)
        k      = exp(jump_mean + 0.5*jump_std^2) - 1, the drift compensator that
                 keeps the realized drift at mu despite the added jump component
        Z      ~ N(0, 1)
        J      ~ N(N*jump_mean, N*jump_std^2), N ~ Poisson(lambda*dt) — the sum of
                 N iid lognormal jump log-sizes landing in this step. This is exact,
                 not an approximation: a sum of N iid normals is itself normal.

    Determinism guarantee: all randomness flows through a seeded numpy RNG sourced
    from JumpDiffusionConfig.seed. Same config = identical path. With
    jump_intensity=0, N is always 0 and this reduces exactly to plain GBM.
    """

    def __init__(self, config: JumpDiffusionConfig, clock: SimulationClock) -> None:
        self._config = config
        self._clock = clock
        self._rng = np.random.default_rng(config.seed)

    def generate(self) -> list[Event]:
        """
        Generate n_steps MarketUpdate events and return them in timestamp order.
        Each event's timestamp advances by dt per step.
        """
        cfg = self._config
        events: list[Event] = []

        price = cfg.initial_price
        diffusion_draws, jump_counts, jump_draws = self._draw(cfg)
        drift, diffusion_scale = self._constants(cfg)

        for i in range(cfg.n_steps):
            timestamp = (i + 1) * cfg.dt
            self._clock.advance(timestamp)

            jump_component = self._jump_component(cfg, jump_counts[i], jump_draws[i])
            price = price * np.exp(
                drift + diffusion_scale * diffusion_draws[i] + jump_component
            )

            event = market_update(
                timestamp=timestamp,
                sequence=self._clock.next_sequence(),
                price=float(price),
                instrument=cfg.instrument,
            )
            events.append(event)

        return events

    def price_path(self) -> np.ndarray:
        """
        Return the raw price path as a numpy array without wrapping in events.
        Useful for notebooks and visualization — does not advance the clock or
        consume sequences, uses a fresh seeded RNG each call.
        """
        cfg = self._config
        rng = np.random.default_rng(cfg.seed)

        prices = np.empty(cfg.n_steps + 1)
        prices[0] = cfg.initial_price

        diffusion_draws, jump_counts, jump_draws = self._draw(cfg, rng)
        drift, diffusion_scale = self._constants(cfg)

        for i in range(cfg.n_steps):
            jump_component = self._jump_component(cfg, jump_counts[i], jump_draws[i])
            prices[i + 1] = prices[i] * np.exp(
                drift + diffusion_scale * diffusion_draws[i] + jump_component
            )

        return prices

    def _draw(self, cfg: JumpDiffusionConfig, rng: np.random.Generator | None = None):
        rng = rng or self._rng
        diffusion_draws = rng.standard_normal(cfg.n_steps)
        jump_counts = rng.poisson(cfg.jump_intensity * cfg.dt, size=cfg.n_steps)
        jump_draws = rng.standard_normal(cfg.n_steps)
        return diffusion_draws, jump_counts, jump_draws

    @staticmethod
    def _constants(cfg: JumpDiffusionConfig) -> tuple[float, float]:
        compensator = np.exp(cfg.jump_mean + 0.5 * cfg.jump_std**2) - 1
        drift = (
            cfg.mu - 0.5 * cfg.sigma**2 - cfg.jump_intensity * compensator
        ) * cfg.dt
        diffusion_scale = cfg.sigma * np.sqrt(cfg.dt)
        return drift, diffusion_scale

    @staticmethod
    def _jump_component(cfg: JumpDiffusionConfig, n: int, z: float) -> float:
        return n * cfg.jump_mean + cfg.jump_std * np.sqrt(n) * z
