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