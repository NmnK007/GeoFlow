"""Finite-volume time integration and output sampling."""

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from time import perf_counter

import numpy as np

from . import __version__
from .boundaries import faces
from .config import Config
from .diagnostics import integrals
from .grid import centers
from .initial_conditions import initial_state
from .physics import rotate, signal_speed
from .state import primitive, valid


@dataclass
class SimulationResult:
    config: Config
    time: np.ndarray
    x: np.ndarray
    y: np.ndarray
    h: np.ndarray
    u: np.ndarray
    v: np.ndarray
    diagnostics: list[dict]
    metadata: dict


def metadata(c: Config) -> dict:
    return {
        "version": __version__,
        "config": asdict(c),
        "resolved_f_s_inv": c.f,
        "scheme": "first-order unsplit Rusanov, Euler flux then exact Coriolis rotation",
        "units": {
            "time": "s",
            "x": "m",
            "y": "m",
            "h": "m",
            "u": "m/s",
            "v": "m/s",
            "volume": "m^3",
            "energy": "m^5/s^2",
        },
    }


def trial(q: np.ndarray, c: Config, dt: float) -> np.ndarray:
    fx = faces(q, c.gravity_m_s2, 0, c.boundary_x)
    fy = faces(q, c.gravity_m_s2, 1, c.boundary_y)
    transported = (
        q
        - dt / (c.lx_m / c.nx) * np.diff(fx, axis=2)
        - dt / (c.ly_m / c.ny) * np.diff(fy, axis=1)
    )
    return rotate(transported, c.f * dt)


def advance(
    q: np.ndarray, c: Config, t: float, dt: float
) -> tuple[np.ndarray, float, int]:
    for rejected in range(c.max_retries + 1):
        if dt <= 0 or not math.isfinite(dt) or t + dt == t:
            raise RuntimeError(f"cannot advance time at t={t:g}, dt={dt:g}")
        with np.errstate(over="ignore", invalid="ignore"):
            candidate = trial(q, c, dt)
        if valid(candidate, c.min_depth_m):
            return candidate, dt, rejected
        dt *= 0.5
    raise RuntimeError(f"invalid trial state at t={t:g} after {c.max_retries} retries")


def run_simulation(
    config: Config, progress_callback: Callable[[float], None] | None = None
) -> SimulationResult:
    """Integrate to each output target. Callback receives simulated fraction [0,1]."""
    c = config
    start = perf_counter()
    x, y = centers(c)
    q = initial_state(c, x, y)
    times = np.arange(c.intervals + 1, dtype=float)
    times[:-1] *= c.sample_s
    times[-1] = c.duration_s
    h, u, v = (np.empty((len(times), c.ny, c.nx)) for _ in range(3))
    rows = []
    steps = rejects = 0
    t = dt = courant = 0.0
    for index, target in enumerate(times):
        while t < target:
            if steps >= c.max_steps:
                raise RuntimeError(f"step limit {c.max_steps} exhausted at t={t:g}")
            rate = signal_speed(q, c.gravity_m_s2, 0).max() / (
                c.lx_m / c.nx
            ) + signal_speed(q, c.gravity_m_s2, 1).max() / (c.ly_m / c.ny)
            if not 0 < rate < math.inf:
                raise RuntimeError(f"invalid CFL rate at t={t:g}")
            rotation_cap = 0.1 / abs(c.f) if c.f else math.inf
            remaining = target - t
            q, dt, rejected = advance(
                q, c, t, min(c.cfl / rate, rotation_cap, remaining)
            )
            t = target if dt == remaining else t + dt
            courant = dt * rate
            rejects += rejected
            steps += 1
        h[index], u[index], v[index] = primitive(q)
        volume, energy = integrals(h[index], u[index], v[index], c)
        if index == 0:
            v0, e0 = volume, energy
        row = {
            "time_s": float(target),
            "dt_s": float(dt),
            "cfl": float(courant),
            "steps": steps,
            "rejected_steps": rejects,
            "volume_m3": volume,
            "volume_drift": abs(volume - v0) / v0,
            "energy": energy,
            "energy_change": energy - e0,
            "relative_energy_change": (energy - e0) / e0 if e0 else None,
            "min_h_m": float(h[index].min()),
            "max_h_m": float(h[index].max()),
            "max_speed_m_s": float(np.hypot(u[index], v[index]).max()),
            "wall_time_s": perf_counter() - start,
        }
        if any(
            value is not None and not math.isfinite(value) for value in row.values()
        ):
            raise RuntimeError(f"nonfinite diagnostic at t={t:g}")
        rows.append(row)
        if progress_callback:
            progress_callback(float(target / c.duration_s))
    info = dict(
        metadata(c), status="completed", error=None, runtime_s=perf_counter() - start
    )
    return SimulationResult(c, times, x, y, h, u, v, rows, info)
