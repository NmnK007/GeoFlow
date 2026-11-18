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
    left: np.ndarray, right: np.ndarray, g: float, direction: int
) -> np.ndarray:
    speed = np.maximum(
        signal_speed(left, g, direction), signal_speed(right, g, direction)
    )
    return 0.5 * (
        flux(left, g, direction) + flux(right, g, direction) - speed * (right - left)
    )


def rotate(q: np.ndarray, angle: float) -> np.ndarray:
    h, mx, my = q
    c, s = math.cos(angle), math.sin(angle)
    return np.stack((h, c * mx + s * my, c * my - s * mx))
