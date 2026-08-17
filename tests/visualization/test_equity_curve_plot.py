import pytest

from market_sim.visualization import plot_equity_curves


def test_plots_one_line_per_strategy():
    curves = {
        "momentum": [(1.0, 100.0), (2.0, 101.0), (3.0, 99.0)],
        "random": [(1.0, 100.0), (2.0, 100.5)],
    }

    fig = plot_equity_curves(curves)

    ax = fig.axes[0]
    assert len(ax.lines) == 2
    _, labels = ax.get_legend_handles_labels()
    assert set(labels) == {"momentum", "random"}


def test_line_data_matches_input_curve():
    curves = {"a": [(1.0, 100.0), (2.0, 110.0), (3.0, 105.0)]}

    fig = plot_equity_curves(curves)

    line = fig.axes[0].lines[0]
    assert list(line.get_xdata()) == [1.0, 2.0, 3.0]
    assert list(line.get_ydata()) == [100.0, 110.0, 105.0]


def test_empty_curves_dict_raises():
    with pytest.raises(ValueError):
        plot_equity_curves({})


def test_empty_individual_curve_is_skipped_not_crashed():
    curves = {"a": [(1.0, 100.0), (2.0, 101.0)], "b": []}

    fig = plot_equity_curves(curves)

    assert len(fig.axes[0].lines) == 1


def test_custom_title_applied():
    fig = plot_equity_curves({"a": [(1.0, 100.0)]}, title="My Title")

    assert fig.axes[0].get_title() == "My Title"
