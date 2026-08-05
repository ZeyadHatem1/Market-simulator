from dataclasses import dataclass, field


@dataclass
class PnLTracker:
    """
    Realized PnL accumulator and equity-curve history for one Portfolio.
    Separate from Position (current holdings) because this is a time series
    plus a running total, not a point-in-time snapshot.
    """

    initial_cash: float
    realized_pnl: float = 0.0
    equity_curve: list[tuple[float, float]] = field(default_factory=list)

    def add_realized(self, amount: float) -> None:
        self.realized_pnl += amount

    def record_equity(self, timestamp: float, equity: float) -> None:
        self.equity_curve.append((timestamp, equity))

    @property
    def total_pnl(self) -> float:
        if not self.equity_curve:
            return 0.0
        return self.equity_curve[-1][1] - self.initial_cash
