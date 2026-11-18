"""Analytical height references in their stated small-amplitude limits."""

import numpy as np

from .config import Config


def height_reference(c: Config, x: np.ndarray, y: np.ndarray, t: float):
    k = 2 * np.pi / c.lx_m
    l = np.pi / c.ly_m
    speed = np.sqrt(c.g * c.depth_m)
    a = c.epsilon * c.depth_m
    if c.experiment == "balanced":
        return a * np.cos(2 * l * y[:, None]) + np.zeros_like(x)
    if (
        c.experiment == "wave"
        and c.plane == "f"
        and not c.f
        and c.boundary_x == "periodic"
    ):
        return a * np.sin(k * (x - speed * t)) + np.zeros((len(y), 1))
    if c.experiment == "poincare":
        omega = np.sqrt(c.f**2 + (speed * k) ** 2)
        return a * np.cos(k * x - omega * t) + np.zeros((len(y), 1))
    if c.experiment == "kelvin":
        return (
            a
            * np.cos(k * (x - np.sign(c.f) * speed * t))
            * np.exp(-abs(c.f) * y[:, None] / speed)
        )
    if c.experiment == "rossby":
        omega = -c.beta * k / (k * k + l * l + (c.f / speed) ** 2)
        return a * np.cos(k * x - omega * t) * np.sin(l * y[:, None])
    return None
