import numpy as np
import pytest

from market_sim.derivatives.vol_surface import VolSurface
from market_sim.visualization import plot_vol_surface


def _make_surface():
    strikes = np.array([90.0, 100.0, 110.0])
    maturities = np.array([0.25, 1.0])
    implied_vols = np.array([[0.22, 0.20, 0.22], [0.21, 0.19, 0.21]])
    return VolSurface(strikes=strikes, maturities=maturities, implied_vols=implied_vols)


def test_surface_trace_matches_input_grid():
    surface = _make_surface()

    fig = plot_vol_surface(surface)

    assert len(fig.data) == 1
    trace = fig.data[0]
    assert trace.type == "surface"
    np.testing.assert_allclose(trace.x, surface.strikes)
    np.testing.assert_allclose(trace.y, surface.maturities)
    np.testing.assert_allclose(trace.z, surface.implied_vols)


def test_title_and_axis_labels():
    surface = _make_surface()

    fig = plot_vol_surface(surface, title="My Surface")

    assert fig.layout.title.text == "My Surface"
    assert fig.layout.scene.xaxis.title.text == "Strike"
    assert fig.layout.scene.yaxis.title.text == "Maturity"
    assert fig.layout.scene.zaxis.title.text == "Implied Volatility"


def test_empty_strikes_raises():
    surface = VolSurface(
        strikes=np.array([]),
        maturities=np.array([1.0]),
        implied_vols=np.empty((1, 0)),
    )
    with pytest.raises(ValueError):
        plot_vol_surface(surface)


def test_empty_maturities_raises():
    surface = VolSurface(
        strikes=np.array([100.0]),
        maturities=np.array([]),
        implied_vols=np.empty((0, 1)),
    )
    with pytest.raises(ValueError):
        plot_vol_surface(surface)
