"""A direction is 0 for x, 1 for y. A face array has one extra normal index."""

import numpy as np

from .physics import rusanov


def ghost(q: np.ndarray, direction: int, upper: bool, boundary: str) -> np.ndarray:
    axis = 2 - direction
    index = (0 if upper else -1) if boundary == "periodic" else (-1 if upper else 0)
    edge = np.take(q, [index], axis=axis)
    if boundary == "wall":
        edge[direction + 1] *= -1
    return edge


def faces(q: np.ndarray, g: float, direction: int, boundary: str) -> np.ndarray:
    axis = 2 - direction
    # Periodic seam occurs twice in the divergence array but is evaluated once.
    pieces = [ghost(q, direction, False, boundary), q]
    if boundary == "wall":
        pieces.append(ghost(q, direction, True, boundary))
    padded = np.concatenate(pieces, axis=axis).swapaxes(axis, -1)
    fluxes = rusanov(padded[..., :-1], padded[..., 1:], g, direction)
    if boundary == "periodic":
        fluxes = np.concatenate((fluxes, fluxes[..., :1]), axis=-1)
    return fluxes.swapaxes(axis, -1)
