"""Piecewise-linear conserved states and two unsplit SSP-RK stages."""

import numpy as np

from .boundaries import ghost
from .config import Config
from .physics import rusanov, signal_speed
from .state import valid


class InvalidStage(ArithmeticError):
    """Retry from the accepted state using a shorter step."""


def slope(back: np.ndarray, forward: np.ndarray, limiter: str) -> np.ndarray:
    magnitude = np.minimum(abs(back), abs(forward))
    if limiter == "mc":
        magnitude = np.minimum(2 * magnitude, abs(0.5 * (back + forward)))
    return np.where(np.sign(back) == np.sign(forward), np.sign(back) * magnitude, 0.0)


def interfaces(q, c, direction, boundary):
    axis = 2 - direction
    padded = np.concatenate(
        (ghost(q, direction, False, boundary), q, ghost(q, direction, True, boundary)),
        axis=axis,
    )
    jumps = np.diff(padded, axis=axis).swapaxes(axis, -1)
    dq = slope(jumps[..., :-1], jumps[..., 1:], c.limiter).swapaxes(axis, -1)
    dq *= 0.5
    lo, hi = q - dq, q + dq
    if boundary == "periodic":
        left, right = np.roll(hi, 1, axis=axis), lo
    else:
        # The exterior wall trace mirrors the reconstructed interior.
        left = np.concatenate((ghost(lo, direction, False, boundary), hi), axis=axis)
        right = np.concatenate((lo, ghost(hi, direction, True, boundary)), axis=axis)
    if not valid(left, c.min_depth_m) or not valid(right, c.min_depth_m):
        raise InvalidStage("invalid face state")
    speeds = np.maximum(
        signal_speed(left, c.g, direction), signal_speed(right, c.g, direction)
    )
    flux = rusanov(left, right, c.g, direction, speeds)
    speed = speeds.max()
    if boundary == "periodic":
        flux = np.concatenate((flux, np.take(flux, [0], axis=axis)), axis=axis)
    return np.diff(flux, axis=axis), speed


def euler(q, c, dt):
    dx, dy = c.lx_m / c.nx, c.ly_m / c.ny
    fx, ax = interfaces(q, c, 0, c.boundary_x)
    fy, ay = interfaces(q, c, 1, c.boundary_y)
    if dt * (ax / dx + ay / dy) > 0.5 * (1 + 1e-14):
        raise InvalidStage("reconstructed CFL exceeds 0.5")
    result = q - (dt / dx) * fx - (dt / dy) * fy
    if not valid(result, c.min_depth_m):
        raise InvalidStage("invalid Euler stage")
    return result


def rk2(q: np.ndarray, c: Config, dt: float) -> np.ndarray:
    return 0.5 * q + 0.5 * euler(euler(q, c, dt), c, dt)
