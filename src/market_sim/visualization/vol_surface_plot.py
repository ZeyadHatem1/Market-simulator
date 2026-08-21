import plotly.graph_objects as go

from market_sim.derivatives.vol_surface import VolSurface


def plot_vol_surface(
    surface: VolSurface,
    title: str = "Implied Volatility Surface",
) -> go.Figure:
    """
    3D surface plot of VolSurface.implied_vols over (strike, maturity).
    Plotly rather than matplotlib, unlike the other visualization/ charts —
    the stack table earmarks plotly specifically for interactive 3D
    rendering, which a vol surface is the first (and only) consumer of.
    """
    if surface.strikes.size == 0 or surface.maturities.size == 0:
        raise ValueError("surface must have at least one strike and one maturity")

    fig = go.Figure(
        data=[
            go.Surface(
                x=surface.strikes,
                y=surface.maturities,
                z=surface.implied_vols,
            )
        ]
    )
    fig.update_layout(
        title=title,
        scene=dict(
            xaxis_title="Strike",
            yaxis_title="Maturity",
            zaxis_title="Implied Volatility",
        ),
    )
    return fig
