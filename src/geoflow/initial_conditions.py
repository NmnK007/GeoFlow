import numpy as np

from .config import Config
from .state import conserved, valid


def initial_state(c: Config, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    h = np.full((c.ny, c.nx), c.depth_m, dtype=float)
    u, v = np.zeros_like(h), np.zeros_like(h)
    if c.experiment == "wave":
        eta = c.depth_m * c.epsilon * np.sin(2 * np.pi * (x / c.lx_m))
        h += eta
        u[:] = np.sqrt(c.gravity_m_s2 * c.depth_m) * eta / c.depth_m
    elif c.experiment == "gaussian":
        radius2 = ((x - c.lx_m / 2) / c.sigma_m) ** 2 + (
            (y[:, None] - c.ly_m / 2) / c.sigma_m
        ) ** 2
        h += c.amplitude_m * np.exp(-0.5 * radius2)
    elif c.experiment == "uniform":
        u.fill(c.u0_m_s)
        v.fill(c.v0_m_s)
    q = conserved(h, u, v)
    if not valid(q, c.min_depth_m):
        raise ValueError("initial state nonfinite or depth below threshold")
    return q
