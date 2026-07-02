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