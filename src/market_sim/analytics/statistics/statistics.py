import pandas as pd

EquityCurve = list[tuple[float, float]]


def align_equity_curves(curves: dict[str, EquityCurve]) -> pd.DataFrame:
    """
    Turns a set of equity curves into one timestamp-aligned DataFrame
    (columns = curve keys, index = union of all timestamps, forward-filled).

    Curves cannot be zipped positionally: each Portfolio records an extra
    equity sample on every one of its own fills, on top of the shared
    MARKET_UPDATE ticks, so two strategies (or two Monte Carlo runs) that
    trade a different number of times end up with differently-sized curves.
    Instead, each curve is turned into a timestamp-indexed Series (later
    samples win ties at the same timestamp — the post-fill equity is the
    accurate one), aligned on the union of all timestamps, and
    forward-filled: equity is unchanged between recorded samples, so
    holding the last known value forward until the next sample is correct,
    not an approximation.
    """
    series = {
        key: pd.Series({timestamp: equity for timestamp, equity in curve})
        for key, curve in curves.items()
    }
    return pd.DataFrame(series).sort_index().ffill()


def correlation_matrix(curves: dict[str, EquityCurve]) -> pd.DataFrame:
    """Pairwise Pearson correlation of period returns across strategies' equity curves."""
    equity = align_equity_curves(curves)
    return equity.pct_change().corr()
