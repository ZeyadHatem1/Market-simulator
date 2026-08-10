import pandas as pd

EquityCurve = list[tuple[float, float]]


def correlation_matrix(curves: dict[str, EquityCurve]) -> pd.DataFrame:
    """
    Pairwise Pearson correlation of period returns across strategies'
    equity curves.

    Curves cannot be zipped positionally: each Portfolio records an extra
    equity sample on every one of its own fills, on top of the shared
    MARKET_UPDATE ticks, so two strategies that trade a different number
    of times end up with differently-sized curves. Instead, each curve is
    turned into a timestamp-indexed Series (later samples win ties at the
    same timestamp — the post-fill equity is the accurate one), aligned
    on the union of all timestamps, and forward-filled: a strategy's
    equity is unchanged between its own recorded samples, so holding the
    last known value forward until its next sample is correct, not an
    approximation.
    """
    series = {
        strategy_id: pd.Series({timestamp: equity for timestamp, equity in curve})
        for strategy_id, curve in curves.items()
    }
    equity = pd.DataFrame(series).sort_index().ffill()
    return equity.pct_change().corr()
