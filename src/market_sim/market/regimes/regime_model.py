import numpy as np

from market_sim.core.config import RegimeConfig
from market_sim.core.clock import SimulationClock
from market_sim.events import Event, market_update


class VolatilityRegimeModel:
    """
    Generates a synthetic price path via regime-switching GBM: a discrete-time
    Markov chain over named regimes (e.g. low_vol/high_vol), each with its own
    (mu, sigma), driving the same GBM update PriceGenerator uses:

        S(t+dt) = S(t) * exp((mu_r - 0.5*sigma_r^2)*dt + sigma_r*sqrt(dt)*Z)

    where r is the regime active at step t, drawn each step from
    RegimeConfig.transition_matrix conditioned on the previous step's regime.

    Determinism guarantee: all randomness (both the GBM noise and the regime
    transitions) flows through a single seeded numpy RNG sourced from
    RegimeConfig.seed. Same config = identical regime path and price path.
    With a transition matrix that always self-loops (row = 1.0 on the
    diagonal), this reduces exactly to PriceGenerator's plain GBM for that
    regime's (mu, sigma), since the GBM noise draws happen in the same
    up-front batch call before any transition is sampled.
    """

    def __init__(self, config: RegimeConfig, clock: SimulationClock) -> None:
        self._config = config
        self._clock = clock
        self._rng = np.random.default_rng(config.seed)

    def generate(self) -> list[Event]:
        """
        Generate n_steps MarketUpdate events and return them in timestamp order.
        Each event's timestamp advances by dt per step.
        """
        cfg = self._config
        prices, _ = self._simulate(self._rng)
        events: list[Event] = []

        for i in range(cfg.n_steps):
            timestamp = (i + 1) * cfg.dt
            self._clock.advance(timestamp)

            event = market_update(
                timestamp=timestamp,
                sequence=self._clock.next_sequence(),
                price=float(prices[i + 1]),
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
        rng = np.random.default_rng(self._config.seed)
        prices, _ = self._simulate(rng)
        return prices

    def regime_path(self) -> np.ndarray:
        """
        Return the raw regime label path as a numpy array of strings, one
        entry per step (length n_steps, not n_steps + 1 — there is no
        "regime before step 1" concept the way price_path() has an initial
        price). Uses a fresh seeded RNG, so it is consistent with price_path()
        called on the same config: both are deterministic functions of the
        same seed via the same simulation routine.
        """
        rng = np.random.default_rng(self._config.seed)
        _, regimes = self._simulate(rng)
        return np.array(regimes, dtype=object)

    def _simulate(self, rng: np.random.Generator) -> tuple[np.ndarray, list[str]]:
        cfg = self._config
        regime_names = list(cfg.regimes.keys())
        index_of = {name: i for i, name in enumerate(regime_names)}

        prices = np.empty(cfg.n_steps + 1)
        prices[0] = cfg.initial_price
        regimes_used: list[str] = []

        current = cfg.initial_regime
        diffusion_draws = rng.standard_normal(cfg.n_steps)

        for i in range(cfg.n_steps):
            regimes_used.append(current)

            mu, sigma = cfg.regimes[current]
            drift = (mu - 0.5 * sigma**2) * cfg.dt
            diffusion_scale = sigma * np.sqrt(cfg.dt)
            prices[i + 1] = prices[i] * np.exp(
                drift + diffusion_scale * diffusion_draws[i]
            )

            current = rng.choice(
                regime_names, p=cfg.transition_matrix[index_of[current]]
            )

        return prices, regimes_used
