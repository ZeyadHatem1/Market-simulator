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
            # Plotly's default camera distance and full-width scene domain
            # clip the far axis tick labels (e.g. the last strike/maturity
            # value) against the figure edge for typical vol-surface aspect
            # ratios. Pulling the camera back and leaving margin on the
            # right/top of the scene's domain keeps every tick label
            # inside the frame.
            domain=dict(x=[0.0, 0.92], y=[0.0, 0.92]),
            camera=dict(eye=dict(x=1.7, y=1.7, z=1.2)),
        ),
        margin=dict(l=20, r=20, b=20, t=60),
    )
    return fig
