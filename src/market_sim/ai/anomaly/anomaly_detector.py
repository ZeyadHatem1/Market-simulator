import statistics
from collections import deque


class AnomalyDetector:
    """
    Rolling z-score anomaly detector over price returns. A step is flagged
    anomalous when the latest return's z-score, against the population
    mean/std of the trailing `window` returns (itself included), exceeds
    `threshold` in magnitude. Returns rather than raw price, since price
    carries trend/drift that would make an ordinary rally or selloff look
    anomalous against a rolling price window.
    """

    def __init__(self, window: int, threshold: float) -> None:
        if window <= 1:
            raise ValueError(f"window must be > 1, got {window}")
        if threshold <= 0:
            raise ValueError(f"threshold must be > 0, got {threshold}")
        self._window = window
        self._threshold = threshold
        self._last_price: float | None = None
        self._returns: deque[float] = deque(maxlen=window)

    def update(self, price: float) -> bool:
        if self._last_price is not None:
            self._returns.append((price - self._last_price) / self._last_price)
        self._last_price = price

        if len(self._returns) < self._window:
            return False

        std = statistics.pstdev(self._returns)
        if std == 0:
            return False

        mean = statistics.fmean(self._returns)
        z = (self._returns[-1] - mean) / std
        return abs(z) > self._threshold

    @property
    def is_ready(self) -> bool:
        """True once enough returns have accumulated to compute a z-score."""
        return len(self._returns) == self._window
