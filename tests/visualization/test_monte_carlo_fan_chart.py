import numpy as np
import pytest

from market_sim.analytics.monte_carlo import MonteCarloResult
from market_sim.visualization import plot_monte_carlo_fan_chart


def _make_result(equity_curves):
    return MonteCarloResult(
        final_pnl=np.zeros(len(equity_curves)),
        equity_curves=equity_curves,
        mean=0.0,
        median=0.0,
        std=0.0,
        percentiles={},
        prob_of_loss=0.0,
    )


def test_median_line_matches_hand_computed_values():
    curves = [
        [(1.0, 100.0), (2.0, 110.0), (3.0, 120.0)],
        [(1.0, 100.0), (2.0, 90.0), (3.0, 80.0)],
        [(1.0, 100.0), (2.0, 100.0), (3.0, 100.0)],
    ]
    result = _make_result(curves)

    fig = plot_monte_carlo_fan_chart(result)

    median_line = fig.axes[0].lines[0]
    values = np.array(
        [[100.0, 110.0, 120.0], [100.0, 90.0, 80.0], [100.0, 100.0, 100.0]]
    )
    np.testing.assert_allclose(median_line.get_ydata(), np.median(values, axis=0))
    np.testing.assert_allclose(median_line.get_xdata(), [1.0, 2.0, 3.0])


def test_band_matches_hand_computed_percentiles():
    curves = [
        [(1.0, 100.0), (2.0, 110.0)],
        [(1.0, 100.0), (2.0, 90.0)],
        [(1.0, 100.0), (2.0, 100.0)],
        [(1.0, 100.0), (2.0, 130.0)],
    ]
    result = _make_result(curves)

    fig = plot_monte_carlo_fan_chart(result, percentile_band=(25, 75))

    # fill_between's exact vertex ordering/duplication is a matplotlib
    # implementation detail, so check per-x membership rather than assuming
    # a fixed layout: at each timestamp, the drawn polygon's y-values must
    # include both the expected lower and upper bound.
    band = fig.axes[0].collections[0]
    vertices = band.get_paths()[0].vertices
    xs, ys = vertices[:, 0], vertices[:, 1]

    values_at_t2 = np.array([110.0, 90.0, 100.0, 130.0])
    expected = {
        1.0: (100.0, 100.0),
        2.0: (np.percentile(values_at_t2, 25), np.percentile(values_at_t2, 75)),
    }

    for x, (exp_lower, exp_upper) in expected.items():
        ys_at_x = ys[np.isclose(xs, x)]
        assert np.any(np.isclose(ys_at_x, exp_lower)), f"lower bound missing at x={x}"
        assert np.any(np.isclose(ys_at_x, exp_upper)), f"upper bound missing at x={x}"


def test_runs_with_different_sample_counts_do_not_crash():
    # mimics runs whose strategy fills a different number of times per run,
    # same reason analytics.statistics.correlation_matrix can't zip positionally
    curves = [
        [(1.0, 100.0), (2.0, 101.0), (3.0, 102.0)],
        [(1.0, 100.0), (1.0, 99.0), (2.0, 98.0), (2.0, 97.0), (3.0, 96.0)],
    ]
    result = _make_result(curves)

    fig = plot_monte_carlo_fan_chart(result)

    assert len(fig.axes[0].lines[0].get_xdata()) == 3


def test_invalid_percentile_band_raises():
    result = _make_result([[(1.0, 100.0)]])
    with pytest.raises(ValueError):
        plot_monte_carlo_fan_chart(result, percentile_band=(75, 25))


def test_empty_equity_curves_raises():
    result = _make_result([])
    with pytest.raises(ValueError):
        plot_monte_carlo_fan_chart(result)
