"""State arrays are ordered (h, hu, hv), each field indexed [y, x]."""

import numpy as np


def conserved(h: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    return np.array([h, h * u, h * v], dtype=np.float64)


def primitive(q: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    h, mx, my = q
    return h, mx / h, my / h


def valid(q: np.ndarray, floor: float) -> bool:
    return bool(np.isfinite(q).all() and np.min(q[0]) > floor)
