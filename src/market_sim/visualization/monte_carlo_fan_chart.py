import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from market_sim.analytics.monte_carlo import MonteCarloResult
from market_sim.analytics.statistics import align_equity_curves


def plot_monte_carlo_fan_chart(
    result: MonteCarloResult,
    percentile_band: tuple[int, int] = (5, 95),
    title: str = "Monte Carlo Fan Chart",
) -> Figure:
    """
    Median equity path across every MonteCarloRunner run, with a shaded
    percentile band (default 5th-95th) around it.

    Runs cannot be stacked positionally for the same reason
    analytics.statistics.correlation_matrix's curves can't be zipped: each
    run's Portfolio records an extra equity sample on every fill, so runs
    that trade a different number of times produce differently-sized
    curves even though they share the same underlying MARKET_UPDATE tick
    timestamps (same price_generator_factory config, just a different
    seed per run). Reuses align_equity_curves to align all runs onto one
    shared timestamp axis before computing percentiles.
    """
    lo, hi = percentile_band
    if not (0 <= lo < hi <= 100):
        raise ValueError(
            f"percentile_band must satisfy 0 <= lo < hi <= 100, got {percentile_band}"
        )
    if not result.equity_curves:
        raise ValueError("result.equity_curves must not be empty")

    curves = {str(i): curve for i, curve in enumerate(result.equity_curves)}
    frame = align_equity_curves(curves)
    timestamps = frame.index.to_numpy()
    values = frame.to_numpy()

    median = np.median(values, axis=1)
    lower = np.percentile(values, lo, axis=1)
    upper = np.percentile(values, hi, axis=1)

    fig, ax = plt.subplots()
    ax.fill_between(
        timestamps, lower, upper, alpha=0.3, label=f"{lo}th-{hi}th percentile"
    )
    ax.plot(timestamps, median, label="Median")
    ax.set_xlabel("Time")
    ax.set_ylabel("Equity")
    ax.set_title(title)
    ax.legend()
    return fig
