"""Physical coordinates in km, time in simulated hours; no interactive backend required."""

import numpy as np
from matplotlib.figure import Figure

from .diagnostics import potential_vorticity, vorticity
from .solver import SimulationResult

LABELS = {
    "Height anomaly": "m",
    "Speed": "m/s",
    "Absolute vorticity": "1/s",
    "Kinetic energy density": "m³/s²",
    "Potential energy density": "m³/s²",
    "East velocity": "m/s",
    "North velocity": "m/s",
    "Relative vorticity": "1/s",
    "Potential vorticity": "1/(m s)",
}


def field(r: SimulationResult, name: str, i: int) -> np.ndarray:
    h, u, v = r.h[i], r.u[i], r.v[i]
    if name == "Height anomaly":
        return h - r.config.depth_m
    if name == "Absolute vorticity":
        return vorticity(h, u, v, r.config) + r.config.rotation
    if name == "Kinetic energy density":
        return 0.5 * h * (u * u + v * v)
    if name == "Potential energy density":
        return 0.5 * r.config.g * (h - r.config.depth_m) ** 2
    if name == "Speed":
        return np.hypot(u, v)
    if name == "East velocity":
        return u
    if name == "North velocity":
        return v
    if name == "Relative vorticity":
        return vorticity(h, u, v, r.config)
    if name == "Potential vorticity":
        return potential_vorticity(h, u, v, r.config)
    raise ValueError(f"unknown field {name}")


def limits(r: SimulationResult, name: str) -> tuple[float, float]:
    low, high = np.inf, -np.inf
    for i in range(len(r.time)):
        a = field(r, name, i)
        low, high = min(low, a.min()), max(high, a.max())
    return float(low), float(high)


def heatmap(
    r: SimulationResult,
    name: str,
    i: int,
    arrows: bool = False,
    bounds: tuple[float, float] | None = None,
) -> Figure:
    a = field(r, name, i)
    low, high = bounds or (a.min(), a.max())
    signed = low < 0 < high
    if signed:
        high = max(abs(low), high)
        low = -high
    fig = Figure(figsize=(7, 4.5), layout="constrained")
    ax = fig.subplots()
    image = ax.imshow(
        a,
        origin="lower",
        extent=(0, r.config.lx_m / 1000, 0, r.config.ly_m / 1000),
        aspect="equal",
        cmap="RdBu_r" if signed else "viridis",
        vmin=low,
        vmax=high,
    )
    fig.colorbar(image, ax=ax, label=f"{name} ({LABELS[name]})")
    if arrows and np.any(np.hypot(r.u[i], r.v[i])):
        sx, sy = max(1, r.config.nx // 16), max(1, r.config.ny // 16)
        ax.quiver(
            r.x[::sx] / 1000,
            r.y[::sy] / 1000,
            r.u[i, ::sy, ::sx],
            r.v[i, ::sy, ::sx],
            angles="xy",
            color="black",
        )
    ax.set(
        xlabel="East (km)",
        ylabel="North (km)",
        title=f"{name} at {r.time[i] / 3600:.3g} h",
    )
    return fig


def convergence_plot(rows: list[dict]) -> Figure:
    fig = Figure(figsize=(5, 3.5), layout="constrained")
    ax = fig.subplots()
    ax.loglog([x["nx"] for x in rows], [x["relative_l2"] for x in rows], "o-")
    ax.set(xlabel="Cells per wavelength", ylabel="Relative height-anomaly L2 error")
    return fig
