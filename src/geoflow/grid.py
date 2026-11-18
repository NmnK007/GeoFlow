import numpy as np

from .config import Config


def centers(c: Config) -> tuple[np.ndarray, np.ndarray]:
    return (
        (np.arange(c.nx) + 0.5) * (c.lx_m / c.nx),
        (np.arange(c.ny) + 0.5) * (c.ly_m / c.ny),
    )
