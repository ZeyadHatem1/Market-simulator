import numpy as np

from market_sim.core.config import OUConfig
from market_sim.core.clock import SimulationClock
from market_sim.events import Event, market_update


class OrnsteinUhlenbeckProcess:
    """
    Generates a synthetic mean-reverting series via the Ornstein-Uhlenbeck process,
    using its exact discrete-time solution (not an Euler-Maruyama approximation,
    which would introduce discretization bias at larger dt):

        X(t+dt) = X(t) * exp(-theta*dt) + mu * (1 - exp(-theta*dt))
                  + sigma * sqrt((1 - exp(-2*theta*dt)) / (2*theta)) * Z

    where:
        theta = speed of mean reversion
        mu    = long-run mean
        sigma = volatility
        Z     ~ N(0, 1) standard normal random variable

    Determinism guarantee: all randomness flows through a seeded numpy RNG
    sourced from OUConfig.seed. Same config = identical path.
    """

    def __init__(self, config: OUConfig, clock: SimulationClock) -> None:
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

        value = cfg.initial_value
        random_draws: np.ndarray = self._rng.standard_normal(cfg.n_steps)

        decay = np.exp(-cfg.theta * cfg.dt)
        diffusion_scale = cfg.sigma * np.sqrt(
            (1 - np.exp(-2 * cfg.theta * cfg.dt)) / (2 * cfg.theta)
        )

        for i in range(cfg.n_steps):
            timestamp = (i + 1) * cfg.dt
            self._clock.advance(timestamp)

            value = value * decay + cfg.mu * (1 - decay) + diffusion_scale * random_draws[i]

            event = market_update(
                timestamp=timestamp,
                sequence=self._clock.next_sequence(),
                price=float(value),
                instrument=cfg.instrument,
            )
            events.append(event)

        return events

    def value_path(self) -> np.ndarray:
        """
        Return the raw value path as a numpy array without wrapping in events.
        Useful for notebooks and visualization — does not advance the clock or
        consume sequences, uses a fresh seeded RNG each call.
        """
        cfg = self._config
        rng = np.random.default_rng(cfg.seed)

        values = np.empty(cfg.n_steps + 1)
        values[0] = cfg.initial_value

        random_draws = rng.standard_normal(cfg.n_steps)
        decay = np.exp(-cfg.theta * cfg.dt)
        diffusion_scale = cfg.sigma * np.sqrt(
            (1 - np.exp(-2 * cfg.theta * cfg.dt)) / (2 * cfg.theta)
        )

        for i in range(cfg.n_steps):
            values[i + 1] = values[i] * decay + cfg.mu * (1 - decay) + diffusion_scale * random_draws[i]

        return values
