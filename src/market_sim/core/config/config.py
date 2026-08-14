from dataclasses import dataclass, field


@dataclass
class SimConfig:
    instrument: str
    initial_price: float
    mu: float
    sigma: float
    n_steps: int
    dt: float
    seed: int
    initial_capital: float

    def __post_init__(self) -> None:
        if self.initial_price <= 0:
            raise ValueError(f"initial_price must be > 0, got {self.initial_price}")
        if self.sigma < 0:
            raise ValueError(f"sigma must be >= 0, got {self.sigma}")
        if self.n_steps <= 0:
            raise ValueError(f"n_steps must be > 0, got {self.n_steps}")
        if self.dt <= 0:
            raise ValueError(f"dt must be > 0, got {self.dt}")
        if self.initial_capital <= 0:
            raise ValueError(f"initial_capital must be > 0, got {self.initial_capital}")


@dataclass
class OUConfig:
    instrument: str
    initial_value: float
    theta: float
    mu: float
    sigma: float
    n_steps: int
    dt: float
    seed: int

    def __post_init__(self) -> None:
        if self.theta <= 0:
            raise ValueError(f"theta must be > 0, got {self.theta}")
        if self.sigma < 0:
            raise ValueError(f"sigma must be >= 0, got {self.sigma}")
        if self.n_steps <= 0:
            raise ValueError(f"n_steps must be > 0, got {self.n_steps}")
        if self.dt <= 0:
            raise ValueError(f"dt must be > 0, got {self.dt}")


@dataclass
class PoissonArrivalConfig:
    rate: float
    n_arrivals: int
    seed: int

    def __post_init__(self) -> None:
        if self.rate <= 0:
            raise ValueError(f"rate must be > 0, got {self.rate}")
        if self.n_arrivals <= 0:
            raise ValueError(f"n_arrivals must be > 0, got {self.n_arrivals}")


@dataclass
class SlippageConfig:
    coefficient: float

    def __post_init__(self) -> None:
        if self.coefficient < 0:
            raise ValueError(f"coefficient must be >= 0, got {self.coefficient}")


@dataclass
class RegimeConfig:
    instrument: str
    initial_price: float
    regimes: dict[str, tuple[float, float]]  # name -> (mu, sigma), ordered
    transition_matrix: list[list[float]]  # row i = P(regime i -> regime j), aligned to regimes order
    initial_regime: str
    n_steps: int
    dt: float
    seed: int

    def __post_init__(self) -> None:
        if self.initial_price <= 0:
            raise ValueError(f"initial_price must be > 0, got {self.initial_price}")
        if not self.regimes:
            raise ValueError("regimes must not be empty")
        for name, (_, sigma) in self.regimes.items():
            if sigma < 0:
                raise ValueError(f"sigma for regime {name!r} must be >= 0, got {sigma}")
        if self.initial_regime not in self.regimes:
            raise ValueError(f"initial_regime {self.initial_regime!r} not in regimes")

        n = len(self.regimes)
        if len(self.transition_matrix) != n:
            raise ValueError(
                f"transition_matrix must have one row per regime ({n}), "
                f"got {len(self.transition_matrix)}"
            )
        for row in self.transition_matrix:
            if len(row) != n:
                raise ValueError(f"transition_matrix rows must have length {n}, got {len(row)}")
            if any(p < 0 for p in row):
                raise ValueError(f"transition probabilities must be >= 0, got {row}")
            row_sum = sum(row)
            if abs(row_sum - 1.0) > 1e-8:
                raise ValueError(f"transition_matrix rows must sum to 1, got {row_sum}")

        if self.n_steps <= 0:
            raise ValueError(f"n_steps must be > 0, got {self.n_steps}")
        if self.dt <= 0:
            raise ValueError(f"dt must be > 0, got {self.dt}")


@dataclass
class ShockConfig:
    shock_intensity: float  # expected shocks per unit time (Poisson rate)
    magnitude_range: tuple[float, float]  # liquidity multiplier during a shock, e.g. (0.1, 0.4)
    duration_range: tuple[int, int]  # shock length in steps, e.g. (3, 15)
    n_steps: int
    dt: float
    seed: int

    def __post_init__(self) -> None:
        if self.shock_intensity <= 0:
            raise ValueError(f"shock_intensity must be > 0, got {self.shock_intensity}")

        mag_lo, mag_hi = self.magnitude_range
        if not (0 < mag_lo <= mag_hi <= 1.0):
            raise ValueError(
                f"magnitude_range must satisfy 0 < lo <= hi <= 1.0, got {self.magnitude_range}"
            )

        dur_lo, dur_hi = self.duration_range
        if not (1 <= dur_lo <= dur_hi):
            raise ValueError(
                f"duration_range must satisfy 1 <= lo <= hi, got {self.duration_range}"
            )

        if self.n_steps <= 0:
            raise ValueError(f"n_steps must be > 0, got {self.n_steps}")
        if self.dt <= 0:
            raise ValueError(f"dt must be > 0, got {self.dt}")


@dataclass
class JumpDiffusionConfig:
    instrument: str
    initial_price: float
    mu: float
    sigma: float
    jump_intensity: float
    jump_mean: float
    jump_std: float
    n_steps: int
    dt: float
    seed: int

    def __post_init__(self) -> None:
        if self.initial_price <= 0:
            raise ValueError(f"initial_price must be > 0, got {self.initial_price}")
        if self.sigma < 0:
            raise ValueError(f"sigma must be >= 0, got {self.sigma}")
        if self.jump_intensity < 0:
            raise ValueError(f"jump_intensity must be >= 0, got {self.jump_intensity}")
        if self.jump_std < 0:
            raise ValueError(f"jump_std must be >= 0, got {self.jump_std}")
        if self.n_steps <= 0:
            raise ValueError(f"n_steps must be > 0, got {self.n_steps}")
        if self.dt <= 0:
            raise ValueError(f"dt must be > 0, got {self.dt}")