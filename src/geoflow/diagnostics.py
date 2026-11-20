import numpy as np

from .config import Config


def integrals(
    h: np.ndarray, u: np.ndarray, v: np.ndarray, c: Config
) -> tuple[float, float]:
    area = (c.lx_m / c.nx) * (c.ly_m / c.ny)
    energy = 0.5 * (h * (u * u + v * v) + c.g * (h - c.depth_m) ** 2)
    return float(area * h.sum()), float(area * energy.sum())


def vorticity(h: np.ndarray, u: np.ndarray, v: np.ndarray, c: Config) -> np.ndarray:
    # Tangential velocities have even parity at a free-slip wall.
    common = np.result_type(h, u, v)

    def derivative(field, axis, boundary, spacing):
        field = field.astype(common, copy=False)
        line = field.swapaxes(axis, -1)
        result = np.empty_like(
            line, dtype=common if np.issubdtype(common, np.inexact) else float
        )
        result[..., 1:-1] = line[..., 2:] - line[..., :-2]
        result[..., 0] = line[..., 1] - line[..., -1 if boundary == "periodic" else 0]
        result[..., -1] = line[..., 0 if boundary == "periodic" else -1] - line[..., -2]
        result /= 2 * spacing
        return result.swapaxes(-1, axis)

    return derivative(v, 1, c.boundary_x, c.lx_m / c.nx) - derivative(
        u, 0, c.boundary_y, c.ly_m / c.ny
    )


def potential_vorticity(
    h: np.ndarray, u: np.ndarray, v: np.ndarray, c: Config
) -> np.ndarray:
    return (vorticity(h, u, v, c) + c.rotation) / h
