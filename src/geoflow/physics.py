"""Flux direction 0 means east, 1 means north. f is in inverse seconds."""

import math

import numpy as np

OMEGA = 7.292115e-5


def coriolis(latitude_deg: float) -> float:
    return 2 * OMEGA * math.sin(math.radians(latitude_deg))


def flux(q: np.ndarray, g: float, direction: int) -> np.ndarray:
    normal = direction + 1
    velocity = q[normal] / q[0]
    result = q * velocity
    result[0] = q[normal]
    result[normal] += 0.5 * g * q[0] ** 2
    return result


def signal_speed(q: np.ndarray, g: float, direction: int) -> np.ndarray:
    return np.abs(q[direction + 1] / q[0]) + np.sqrt(g * q[0])


def rusanov(
    left: np.ndarray,
    right: np.ndarray,
    g: float,
    direction: int,
    speed: np.ndarray | None = None,
) -> np.ndarray:
    if speed is None:
        speed = np.maximum(
            signal_speed(left, g, direction), signal_speed(right, g, direction)
        )
    if (
        left.dtype != right.dtype
        or left.dtype != np.asarray(speed).dtype
        or left.shape != right.shape
    ):
        # Let NumPy promote mixed types and broadcast public API inputs.
        return 0.5 * (
            flux(left, g, direction)
            + flux(right, g, direction)
            - speed * (right - left)
        )
    result = flux(left, g, direction)
    result += flux(right, g, direction)
    jump = right - left
    jump *= speed
    result -= jump
    result *= 0.5
    return result


def rotate(q: np.ndarray, angle: float | np.ndarray) -> np.ndarray:
    h, mx, my = q
    c, s = np.cos(angle), np.sin(angle)
    return np.stack((h, c * mx + s * my, c * my - s * mx))
