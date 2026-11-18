import numpy as np

from .boundaries import ghost
from .config import Config


def integrals(
    h: np.ndarray, u: np.ndarray, v: np.ndarray, c: Config
) -> tuple[float, float]:
    area = (c.lx_m / c.nx) * (c.ly_m / c.ny)
    energy = 0.5 * (h * (u * u + v * v) + c.g * (h - c.depth_m) ** 2)
    return float(area * h.sum()), float(area * energy.sum())


def vorticity(h: np.ndarray, u: np.ndarray, v: np.ndarray, c: Config) -> np.ndarray:
    # Tangential velocities have even parity at a free-slip wall.
    fields = np.stack((h, u, v))

    def derivative(direction: int, boundary: str, spacing: float) -> np.ndarray:
        component = 2 - direction
        axis = 2 - direction
        edges = [
            ghost(fields, direction, side, boundary)[component]
            for side in (False, True)
        ]
        line = np.concatenate((edges[0], fields[component], edges[1]), axis=axis - 1)
        line = line.swapaxes(axis - 1, -1)
        return ((line[..., 2:] - line[..., :-2]) / (2 * spacing)).swapaxes(-1, axis - 1)

    return derivative(0, c.boundary_x, c.lx_m / c.nx) - derivative(
        1, c.boundary_y, c.ly_m / c.ny
    )


def potential_vorticity(
    h: np.ndarray, u: np.ndarray, v: np.ndarray, c: Config
) -> np.ndarray:
    return (vorticity(h, u, v, c) + c.rotation) / h
