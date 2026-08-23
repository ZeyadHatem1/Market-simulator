from dataclasses import dataclass


@dataclass
class RiskState:
    """
    Live risk state for one Portfolio: running peak equity, current and
    max drawdown, and notional exposure. Tracks state only — it does not
    enforce limits (nothing in the runtime yet consumes a limit breach;
    enforcement is deferred until a caller actually needs it).
    """

    peak_equity: float
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0

    def update(self, equity: float) -> None:
        self.peak_equity = max(self.peak_equity, equity)
        self.current_drawdown = (
            0.0
            if self.peak_equity == 0
            else (self.peak_equity - equity) / self.peak_equity
        )
        self.max_drawdown = max(self.max_drawdown, self.current_drawdown)

    @staticmethod
    def exposure(quantity: float, price: float) -> float:
        return abs(quantity) * price
