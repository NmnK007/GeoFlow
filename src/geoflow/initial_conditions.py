import numpy as np

from .config import Config
from .state import conserved, valid


def initial_state(c: Config, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    h = np.full((c.ny, c.nx), c.depth_m, dtype=float)
    u, v = np.zeros_like(h), np.zeros_like(h)
    if c.experiment == "wave":
        eta = c.depth_m * c.epsilon * np.sin(2 * np.pi * (x / c.lx_m))
        h += eta
        u[:] = np.sqrt(c.g * c.depth_m) * eta / c.depth_m
    elif c.experiment == "gaussian":
        radius2 = ((x - c.lx_m / 2) / c.sigma_m) ** 2 + (
            (y[:, None] - c.ly_m / 2) / c.sigma_m
        ) ** 2
        h += c.amplitude_m * np.exp(-0.5 * radius2)
    elif c.experiment == "uniform":
        u.fill(c.u0_m_s)
        v.fill(c.v0_m_s)
    elif c.experiment in (
        "rossby",
        "kelvin",
        "poincare",
        "balanced",
        "shear",
        "vortices",
    ):
        eta, u, v = mode_fields(c, x, y)
        h += eta
        u, v = np.broadcast_arrays(u + np.zeros_like(h), v + np.zeros_like(h))
    q = conserved(h, u, v)
    if not valid(q, c.min_depth_m):
        raise ValueError("initial state nonfinite or depth below threshold")
    return q


def mode_fields(c: Config, x: np.ndarray, y: np.ndarray):
    """Primitive perturbations at t=0; phases use radians and velocities m/s."""
    k = 2 * np.pi / c.lx_m
    l = np.pi / c.ly_m
    y = y[:, None]
    a = c.epsilon * c.depth_m
    speed = np.sqrt(c.g * c.depth_m)
    if c.experiment == "rossby":
        eta = a * np.cos(k * x) * np.sin(l * y)
        return (
            eta,
            -c.g / c.f * a * l * np.cos(k * x) * np.cos(l * y),
            -c.g / c.f * a * k * np.sin(k * x) * np.sin(l * y),
        )
    if c.experiment == "kelvin":
        eta = a * np.cos(k * x) * np.exp(-abs(c.f) * y / speed)
        return eta, np.sign(c.f) * speed * eta / c.depth_m, 0.0
    if c.experiment == "poincare":
        omega = np.hypot(c.f, speed * k)
        return (
            a * np.cos(k * x),
            omega * a / (k * c.depth_m) * np.cos(k * x),
            c.f * a / (k * c.depth_m) * np.sin(k * x),
        )
    if c.experiment == "balanced":
        return a * np.cos(2 * l * y), c.g / c.f * a * 2 * l * np.sin(2 * l * y), 0.0
    if c.experiment == "shear":
        center = (y - c.ly_m / 2) / c.sigma_m
        return (
            0.0,
            c.u0_m_s * np.tanh(center),
            0.01 * c.u0_m_s * np.sin(k * x) * np.sin(l * y) * np.exp(-(center**2)),
        )
    # Smooth periodic same-signed pair. Use analytic geostrophic derivatives.
    eta = np.zeros((c.ny, c.nx))
    u, v = np.zeros_like(eta), np.zeros_like(eta)
    for center_x in (0.39 * c.lx_m, 0.61 * c.lx_m):
        X, Y = k * (x - center_x), 2 * l * (y - c.ly_m / 2)
        blob = a * np.exp(
            (np.cos(X) - 1) / (k * c.sigma_m) ** 2
            + (np.cos(Y) - 1) / (2 * l * c.sigma_m) ** 2
        )
        eta += blob
        u += c.g / c.f * blob * np.sin(Y) / (2 * l * c.sigma_m**2)
        v -= c.g / c.f * blob * np.sin(X) / (k * c.sigma_m**2)
    return eta, u, v
