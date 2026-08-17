import matplotlib.pyplot as plt
from matplotlib.figure import Figure

EquityCurve = list[tuple[float, float]]


def plot_equity_curves(
    equity_curves: dict[str, EquityCurve], title: str = "Equity Curves"
) -> Figure:
    """
    One line per strategy, x = timestamp, y = equity. Takes the same
    dict[strategy_id, equity_curve] shape PortfolioManager.equity_curves()
    and analytics.statistics.correlation_matrix already use, so no new
    coupling to Portfolio/PortfolioManager is introduced here.

    Returns the Figure rather than saving it — the caller decides whether
    and how to persist it (fig.savefig(path)), same as notebooks already do
    with matplotlib directly.
    """
    if not equity_curves:
        raise ValueError("equity_curves must not be empty")

    fig, ax = plt.subplots()
    for strategy_id, curve in equity_curves.items():
        if not curve:
            continue
        timestamps, equities = zip(*curve)
        ax.plot(timestamps, equities, label=strategy_id)

    ax.set_xlabel("Time")
    ax.set_ylabel("Equity")
    ax.set_title(title)
    ax.legend()
    return fig
