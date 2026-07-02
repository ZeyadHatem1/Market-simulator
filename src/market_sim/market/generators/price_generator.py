import numpy as np

from market_sim.core.config import SimConfig
from market_sim.core.clock import SimulationClock
from market_sim.events import Event, market_update


class PriceGenerator:
    """
    Generates synthetic price paths via Geometric Brownian Motion (GBM).

    GBM discrete update formula:
        S(t+1) = S(t) * exp((mu - 0.5 * sigma^2) * dt + sigma * sqrt(dt) * Z)

    where:
        mu    = annualized drift
        sigma = annualized volatility
        dt    = length of one time step in years
        Z     ~ N(0, 1) standard normal random variable

    The (mu - 0.5 * sigma^2) term is the Ito correction: without it, the
    expected value of the log-price would be biased upward. This keeps the
    expected price path consistent with the drift mu under the physical measure.

    Determinism guarantee: all randomness flows through a seeded numpy RNG
    sourced from SimConfig.seed. Same config = identical price path.
    """

    def __init__(self, config: SimConfig, clock: SimulationClock) -> None:
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

        # Pre-generate all normal draws at once — more efficient than
        # drawing one at a time, and keeps RNG state changes predictable.
        random_draws: np.ndarray = self._rng.standard_normal(cfg.n_steps)

        # GBM constant terms factored out of the loop
        drift = (cfg.mu - 0.5 * cfg.sigma ** 2) * cfg.dt
        diffusion_scale = cfg.sigma * np.sqrt(cfg.dt)

        for i in range(cfg.n_steps):
            # Advance simulation time by one step
            timestamp = (i + 1) * cfg.dt
            self._clock.advance(timestamp)

            # Apply GBM update
            price = price * np.exp(drift + diffusion_scale * random_draws[i])

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
        Return raw price path as a numpy array without wrapping in events.
        Useful for notebooks and visualization — does not advance the clock
        or consume sequences, uses a fresh seeded RNG each call.
        """
        cfg = self._config
        rng = np.random.default_rng(cfg.seed)

        prices = np.empty(cfg.n_steps + 1)
        prices[0] = cfg.initial_price

        random_draws = rng.standard_normal(cfg.n_steps)
        drift = (cfg.mu - 0.5 * cfg.sigma ** 2) * cfg.dt
        diffusion_scale = cfg.sigma * np.sqrt(cfg.dt)

        for i in range(cfg.n_steps):
            prices[i + 1] = prices[i] * np.exp(drift + diffusion_scale * random_draws[i])

        return prices